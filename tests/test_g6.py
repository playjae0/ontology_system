# -*- coding: utf-8 -*-
"""G6 완료판정 — 4′ 플랫폼 연동 + 계기판 8종 · n9 지문 스캔(S11).

  4′ : 기존 단위 4 판정(subprocess build/query · 2층+cross 그래프 표시 · 큐 열람)
       + 신규 산출물 노출(추출 상태 · 큐 kind 20종 · 등록부 · ops_log/툼스톤)
       + 계기판 8종 출력 — **관측이지 쓰기가 아니다**(data/ 해시 불변 실증)
  S11: CP04_unlabeled 투입 → 후보 "cp" 제안(일치 내역) → **확정 전 파싱 미실행**
       → 확정 후 정상 파싱(12 record). 유일 일치여도 자동 라우팅하지 않는다(P7).

사용: python tests/test_g6.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import platform as PF                          # noqa: E402
from cli import scan as SC                              # noqa: E402
from core import init, store                                  # noqa: E402
from core.bootstrap import load_config, open_graph      # noqa: E402
from core.extract import EXTRACT_DIR                    # noqa: E402
from core import ops                                    # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def data_hash():
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "data").rglob("*.json"))}


# ============================================================ 4′ 기존 단위 4
print("\n■ 4′ — 기존 단위 4: subprocess build/query · 2층+cross 표시 · 큐 열람")
init.init(fresh_=True)              # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)

r = PF.call(["all"])                        # 플랫폼→파이프라인 결합은 subprocess뿐(§16.1)
show("플랫폼이 build를 subprocess로 호출 (파일 계약 — 코드 의존 0)",
     r.returncode == 0 and "[bootstrap]" in r.stdout)
r = PF.call(["query", "노칭 다음 공정은?"])
show("플랫폼이 query를 subprocess로 호출", r.returncode == 0
     and "노칭 다음 공정은 스태킹이다" in r.stdout)

gv = PF.graph_view()
show("2층 표시 — process·quality 양 층의 노드·엣지 계수",
     set(gv["layers"]) == {"process", "quality"}
     and all(s["nodes"] > 0 and s["edges"] for s in gv["layers"].values()),
     str({k: v["nodes"] for k, v in gv["layers"].items()}))
show("cross-layer 표시 — 걸침 엣지가 양 층 canonical로 문장화됨",
     len(gv["cross"]) >= 1 and any("occurs_in" in c for c in gv["cross"]),
     f"{len(gv['cross'])}건")

qv = PF.queue_view()
show("큐 열람 — 전 항목 kind·reason·doc_id 열람 가능",
     qv["total"] == len(qv["items"]) and all("kind" in x for x in qv["items"]),
     f"{qv['total']}건")

# ============================================================ 4′ 신규 노출
print("\n■ 4′ — 신규 산출물 노출 (증분0 §3 G6 + 허브 추가 지시)")
show("큐 kind 닫힌 20종이 전부 열람에 뜬다 — 0건 kind 포함 (D-54)",
     len(PF.QUEUE_KINDS) == 20 and set(qv["kinds"]) == set(PF.QUEUE_KINDS))
show("목록 밖 kind 0 — 실물 큐가 닫힌 목록 안", not qv["alien"], str(qv["alien"]))
fired = {k for k, n in qv["kinds"].items() if n}
show("G3~G5 발화 kind가 열람에 뜬다 (coord_mismatch·direction_*·mirror_asymmetry)",
     {"coord_mismatch", "direction_unverifiable", "direction_conflict",
      "mirror_asymmetry", "auto_node", "spec_conflict", "orphan_anchor"} <= fired,
     str(sorted(fired)))

ev = PF.extract_view()
show("추출 상태 — 파일 존재 = 추출 완료 (prose 4건 완료 · table 2건 경로 아님)",
     [d for d, done in ev.items() if done] == ["PPT01", "PPT02", "PPT03", "QPPT01"]
     and not ev["CP01"] and not ev["PFMEA01"], str(ev))

reg = store.read(store.REGISTRY, {})
show("등록부 조회 — builtin 1층 + registered 1층 (J10)",
     reg["process"]["status"] == "builtin" and reg["quality"]["status"] == "registered")

# ops_log 노출 — 실물로 실증한다: I축 연산 1건을 돌리고 열람에 뜨는지 본다
g = open_graph("process")
# [B26] Unit이 스코프 카테고리가 되어 auto 노드에 좌표 접두가 붙는다.
# **이름 전문을 박지 않는다** — 끝이름으로 찾아 접두 변화에 흔들리지 않게 한다.
nid = next(i for i, n in g.nodes.items()
           if ops.is_live(n) and n["canonical"].split("::")[-1] == "주액기"
           and n["status"] == "auto")
ops.rename("process", nid, "주액 설비 (G6 노출 검증)", actor="시험자", reason="4′ 노출 실증")
ov = PF.ops_view()
show("ops_log 열람 — I축 연산 이력이 5요소로 뜬다",
     len(ov["log"]) >= 1 and {"op", "actor", "at", "targets", "reason"}
     <= set(ov["log"][-1]), str(ov["log"][-1].get("op")))
show("툼스톤 계수 — merged_into·obsolete 층별 계수 노출",
     set(ov["tombstones"]) == {"process", "quality"}
     and all({"merged_into", "obsolete"} <= set(t) for t in ov["tombstones"].values()),
     str(ov["tombstones"]))
ops.rename("process", nid, "주액기", actor="시험자", reason="원복")

# ============================================================ 계기판 8종
print("\n■ 계기판 8종 (CH5 5.5 — 별도 호출 · 관측 무오염)")
before = data_hash()
m = PF.gauges()
after = data_hash()
show("계기판이 data/를 바꾸지 않는다 (관측이지 쓰기가 아니다 — 해시 대조)",
     before == after, str([k for k in before if before[k] != after.get(k)]))
show("8종 전부 출력 — 1~6 품질 지표 + 7 저장 크기 + 8 build 시간",
     all(k in m for k in ["1_linking_recall", "2_plateau", "3_hold_rate",
                          "4_truncation_rate", "5_miss_rate", "6_hub_degree",
                          "7_graph_size", "8_build_seconds"]))
show("1 링킹 recall — 스모크 12문항 기준 실측값",
     m["1_linking_recall"]["value"] is not None
     and m["1_linking_recall"]["expected_linkable"] > 0,
     str(m["1_linking_recall"]["value"]))
show("2 plateau — 문서별 신규 개체율이 인입 순서대로 나온다 (마지막 문서 수렴)",
     [p["doc"] for p in m["2_plateau"]["series"]] == list(store.read(store.DOC_REGISTRY, {}))
     and m["2_plateau"]["series"][-1]["rate"] == 0.0,
     str([p["rate"] for p in m["2_plateau"]["series"]]))
show("3 판정 보류율 — 큐 ÷ 조각 실측", m["3_hold_rate"]["value"] is not None
     and m["3_hold_rate"]["queue"] == qv["total"], str(m["3_hold_rate"]))
show("5 링킹 미스율 — 무근거 문항(Q12)이 미스로 잡힌다",
     any("리튬이온" in s for s in m["5_miss_rate"]["missed"]),
     str(m["5_miss_rate"]["value"]))
show("6 허브 차수 — 층별 상위 노드와 차수 (J9 폭증 조기 관측)",
     all(len(v) >= 1 and v[0]["degree"] >= v[-1]["degree"]
         for v in m["6_hub_degree"].values()),
     str({k: v[0] for k, v in m["6_hub_degree"].items()}))
show("7·8 — 실측값 + 알람선(200MB/30초) 대비, 현재 알람 없음",
     all(not s["over_alarm"] for s in m["7_graph_size"].values())
     and all(not s["over_alarm"] for s in m["8_build_seconds"].values()),
     str({k: f"{v['mb']}MB" for k, v in m["7_graph_size"].items()}))

# ============================================================ S11
print("\n■ S11 — n9 지문 스캔 (파서_명세 §5 · 카드 C15 · P7)")
calls = []
_orig_load = SC._load


def _spy(path):
    mod = _orig_load(path)
    if hasattr(mod, "extract"):
        orig_ex = mod.extract

        def ex(*a, **k):
            calls.append(str(path))
            return orig_ex(*a, **k)
        mod.extract = ex
    return mod


SC._load = _spy
before = data_hash()
res = SC.scan(ROOT / "tests" / "fixtures" / "raw" / "CP04_unlabeled.xlsx")
cp = next(d for d in res["details"] if d["doc_type"] == "cp")
show("후보 'cp' 제안 — 유일 일치", res["candidates"] == ["cp"], str(res["candidates"]))
show("일치 내역 포함 — cp 10/10 · 누락 0 · 잉여 0",
     cp["matched"] == cp["declared"] == 10 and not cp["missing"] and not cp["extra"])
show("타 어댑터의 불일치 내역도 함께 제시된다 (일괄 대조)",
     any(d["doc_type"] == "ipqc" and d["eligible"] and not d["candidate"]
         for d in res["details"]))
show("비정형(prose) 어댑터는 대조 대상 아님 — 지정 필수",
     any(d["doc_type"] == "toc_report" and not d["eligible"] for d in res["details"]))
show("**확정 입력 전 파싱 미실행** — 유일 일치여도 자동 라우팅하지 않는다 (P7)",
     not calls, str(calls))

res2, pieces = SC.confirm(ROOT / "tests" / "fixtures" / "raw" / "CP04_unlabeled.xlsx", "cp")
show("확정 후 정상 파싱 — 10행 → 12 record (복수값 전개 2건)",
     len(pieces) == 12 and len(calls) == 1,
     f"{len(pieces)} record · 전개 {sum(1 for p in pieces if '#' in p['source_locator'])}행")
show("정규화 실증 — 병합 전개(공정구분)·상동 해소(설비)·복수값 분리(관리항목)",
     all(p["process_group"] == "조립" for p in pieces)
     and any(p["source_locator"].endswith("R5") and p["설비"] == "주액기" for p in pieces)
     and {"주액량", "주액 속도"} <= {p["관리항목"] for p in pieces})
show("스캔·확정이 data/를 건드리지 않는다 (편의 기능 — 그래프·큐 쓰기 0)",
     before == data_hash())

drift = SC.scan(ROOT / "tests" / "fixtures" / "raw" / "CP02_drift.xlsx")
dcp = next(d for d in drift["details"] if d["doc_type"] == "cp")
show("표류 1열 검출 — CP02_drift는 후보가 아니다 (관리항목 → 관리 항목명)",
     not drift["candidates"] and dcp["missing"] == ["관리항목"]
     and dcp["extra"] == ["관리 항목명"], f"누락 {dcp['missing']} · 잉여 {dcp['extra']}")
try:
    SC.confirm(ROOT / "tests" / "fixtures" / "raw" / "CP02_drift.xlsx", "cp")
    show("지문 불일치 확정은 거부된다 (preflight 재사용 — C15)", False)
except SystemExit as e:
    show("지문 불일치 확정은 거부된다 (preflight 재사용 — C15)", "불일치" in str(e))
SC._load = _orig_load

# ============================================================ mock 격리
print("\n■ mock 격리 — 픽스처를 들어내도 본체가 도는가 (§2-4)")
# **mock은 걷어낼 대상이 아니라 격리할 대상이다.** 물리적으로 지웠을 때 gauges·scan이
# 죽고 회귀가 붕괴한 것이 실측이고, 원인은 본체가 mock 경로를 **무조건 상수**로
# 알고 있다는 것이었다 — 분기 안에 있는 참조가 0건이었다.
import shutil as _sh2, subprocess as _sp3                       # noqa: E402
from core import fixtures as _FX                                # noqa: E402

_src = (ROOT / "core").rglob("*.py")
_hard = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "parser", "cli")
         for p in sorted((ROOT / d).glob("*.py"))
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         # **경로 상수만** 센다 — `image_summary_source == "mock"` 같은 **값**은
         # 격리 대상이 아니다(그것은 어느 갈래가 만들었나의 표시다).
         if ('/ "mock"' in ln or '"mock/' in ln) and not ln.lstrip().startswith("#")]
show("본체(core·parser·cli)에 mock 경로 상수 0지점", not _hard, str(_hard))
show("픽스처 소재가 core/fixtures.py 한 곳으로 수렴한다",
     hasattr(_FX, "PARSED") and hasattr(_FX, "QUERIES") and hasattr(_FX, "dirs"))

_away = ROOT / "_fixtures_away"
_sh2.move(str(_FX.ROOT_DIR), str(_away))
try:
    def _r(*a):
        return _sp3.run([sys.executable, str(ROOT / "run.py"), *a],
                        capture_output=True, text=True, cwd=str(ROOT))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
             capture_output=True, cwd=str(ROOT))
    _b = _r("bootstrap")
    show("픽스처 없이 bootstrap 정상", _b.returncode == 0)
    _a = _r("all")
    show("픽스처 없이 all — **조용한 무동작이 아니라 말하고 끝난다**",
         _a.returncode == 0 and "인입할 계약 JSON이 없다" in _a.stdout)
    _g = _r("gauges")
    show("픽스처 없이 gauges 정상 (queries.json 무가드 read가 죽던 자리)",
         _g.returncode == 0 and "저장 크기" in _g.stdout,
         (_g.stderr or "").strip().splitlines()[-1:] and
         (_g.stderr or "").strip().splitlines()[-1] or "")
    _s = _r("scan", str(_away / "raw" / "CP04_unlabeled.xlsx"))
    show("픽스처 없이 scan 정상 (없는 디렉터리를 모듈 로드하다 죽던 자리)",
         _s.returncode == 0)
finally:
    _sh2.move(str(_away), str(_FX.ROOT_DIR))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
             capture_output=True, cwd=str(ROOT))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "all"],
             capture_output=True, cwd=str(ROOT))

# ============================================================ B46 일괄 투입
print("\n■ B46 — 일괄 투입 ingest-file · ingest-dir (문서 6 §6.4 · 조건 셋)")
from cli import ingest as IG                                      # noqa: E402
import tempfile as _tf                                            # noqa: E402
_RAW = ROOT / "tests" / "fixtures" / "raw"
show("doc_id 파생 — 파일명 stem · 공백은 _ · 경로 무관 (D-110)",
     IG.doc_id_of("/a/b/관리 계획서 v3.xlsx") == "관리_계획서_v3"
     and IG.doc_id_of("x/CP01.xlsx") == IG.doc_id_of("y/CP01.xlsx") == "CP01")
_sel = IG.select(_RAW / "CP04_unlabeled.xlsx")
show("선택 — 유일 일치는 자동 (cp) · 근거가 실린다 (조건 ①)",
     _sel["status"] == "chosen" and _sel["doc_type"] == "cp" and _sel["basis"]["by"] == "scan"
     and "완전 일치 10/10" in _sel["basis"]["match"], str(_sel["basis"])[:80])
show("선택 — 표류 문서는 0건 → 사람에게 (조건 ③)",
     IG.select(_RAW / "CP02_drift.xlsx")["status"] == "none")
show("선택 — 비정형(pptx)은 스캔하지 않는다 · 지정 필수",
     IG.select(_RAW / "PPT_basic.pptx")["status"] == "none"
     and IG.select(_RAW / "PPT_basic.pptx", doc_type="ppt_quality")["status"] == "none")  # 내장 스키마만 · 어댑터 없음
show("선택 — --doc-type 지정은 스캔 없이 그것으로 (사람 지정 기록)",
     (lambda s: s["status"] == "chosen" and s["basis"] == {"by": "human", "doc_type": "cp"})(
         IG.select(_RAW / "CP02_drift.xlsx", doc_type="cp")))
# 다중 일치 — 같은 지문의 어댑터 둘
_td = Path(_tf.mkdtemp(prefix="multi_"))
_src = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
for _nm in ("cp_a", "cp_b"):
    (_td / f"{_nm}.py").write_text(_src.replace('"doc_type": "cp"', f'"doc_type": "{_nm}"', 1), encoding="utf-8")
_amb = IG.select(_RAW / "CP04_unlabeled.xlsx", adapter_paths=[str(_td)])
show("다중 일치 — 둘 이상이면 자동으로 넘기지 않고 사람에게 올린다 (조건 ③)",
     _amb["status"] == "ambiguous" and sorted(_amb["candidates"]) == ["cp_a", "cp_b"], str(_amb["candidates"]))
shutil.rmtree(_td, ignore_errors=True)
# dry-run — 선택만
_before = data_hash()
_row = IG.ingest_file(_RAW / "CP04_unlabeled.xlsx", dry_run=True)
show("--dry-run — 선택 결과만 · 파싱·인입 0 (조건 ②)",
     _row["status"] == "선택만" and data_hash() == _before
     and not (ROOT / "parsed" / "CP04_unlabeled.json").exists())
# 실제 — 파일 1건
_row = IG.ingest_file(_RAW / "CP04_unlabeled.xlsx")
_reg = store.read(store.DOC_REGISTRY, {}).get("CP04_unlabeled") or {}
show("ingest-file — 선택 → 파싱 → 인입 완주 (record 12)", _row["status"] == "성공" and "record 12" in _row["reason"])
show("인입 기록에 선택 근거가 남는다 — doc_registry.routing (조건 ① · 오배정률의 재료)",
     _reg.get("routing", {}).get("by") == "scan" and _reg["routing"]["doc_type"] == "cp", str(_reg.get("routing"))[:80])
# 경로 — 문서 단위 독립 · 성공/실패/미선택
_bd = Path(_tf.mkdtemp(prefix="batch_"))
for _f in ("CP01.xlsx", "CP03_bad.xlsx", "CP04_unlabeled.xlsx", "TOC01.xlsx"):
    shutil.copy(_RAW / _f, _bd / _f)
_rows = IG.ingest_dir(_bd)
_st = {r["doc_id"]: r["status"] for r in _rows}
show("ingest-dir — 4건 순회 · 성공 2 · 실패 1(C14 파싱 실패) · 미선택 1(지문 0건)",
     _st == {"CP01": "성공", "CP03_bad": "실패", "CP04_unlabeled": "성공", "TOC01": "미선택"}, str(_st))
show("한 건의 실패가 나머지를 멈추지 않는다 — 실패 뒤의 문서도 인입됐다",
     [r["doc_id"] for r in _rows].index("CP03_bad") < [r["doc_id"] for r in _rows].index("CP04_unlabeled")
     and _st["CP04_unlabeled"] == "성공")
show("끝에 모아 보이는 목록 — 성공·실패·미선택 3구획",
     all(k in IG.summary(_rows) for k in ("[성공]", "[실패]", "[미선택]")))
_dry = IG.ingest_dir(_bd, dry_run=True)
show("ingest-dir --dry-run — 전부 선택만/미선택, 인입 0",
     all(r["status"] in ("선택만", "미선택") for r in _dry))
shutil.rmtree(_bd, ignore_errors=True)
for _f in ("CP01", "CP03_bad", "CP04_unlabeled"):
    (ROOT / "parsed" / f"{_f}.json").unlink(missing_ok=True)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G6 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
