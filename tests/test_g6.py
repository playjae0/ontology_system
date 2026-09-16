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

import contextlib as _ctx
import hashlib
import io as _io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import platform as PF                          # noqa: E402
from cli import scan as SC                              # noqa: E402
from core import init, store                                  # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph  # noqa: E402
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
r = PF.call(["query", "노칭 다음 공정은?", "--allow-mock"])   # 회귀는 관문 비대상(B48)
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
# **`form`이 근거에 붙었다**(B58 ④ · 문서 1 C37) — 형태 판정은 선택을 바꾸지
# 않지만 **기록은 남긴다**: 문턱 조정과 애매 구간 측정의 유일한 재료다.
# 키 집합을 못박는 것은 몰래 늘어나는 것을 막는 장치라, 늘릴 때 이름을 적는다.
_hsel = IG.select(_RAW / "CP02_drift.xlsx", doc_type="cp")
show("선택 — --doc-type 지정은 스캔 없이 그것으로 (사람 지정 기록)",
     _hsel["status"] == "chosen"
     and {k: v for k, v in _hsel["basis"].items() if k != "form"}
     == {"by": "human", "doc_type": "cp"},
     str(_hsel["basis"])[:60])
show("선택 — 근거에 형태 판정이 함께 남는다 (C37 — 기록이 이 기능의 절반이다)",
     (_hsel["basis"].get("form") or {}).get("verdict") == "table"
     and len((_hsel["basis"]["form"].get("signals") or {})) == 5)
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
# **블록은 사람 화면의 것이다** — 스위트 stdout에 `[FAIL]`이 섞이면 doctor가
# 그것을 스위트의 실패로 센다(계수는 줄머리로 한다). 받아서 검사만 한다.
_buf6 = _io.StringIO()
with _ctx.redirect_stdout(_buf6):
    _rows = IG.ingest_dir(_bd)
_out6 = _buf6.getvalue()
_st = {r["doc_id"]: r["status"] for r in _rows}
show("ingest-dir — 4건 순회 · 성공 2 · 실패 1(C14 파싱 실패) · 미선택 1(지문 0건)",
     _st == {"CP01": "성공", "CP03_bad": "실패", "CP04_unlabeled": "성공", "TOC01": "미선택"}, str(_st))
show("한 건의 실패가 나머지를 멈추지 않는다 — 실패 뒤의 문서도 인입됐다",
     [r["doc_id"] for r in _rows].index("CP03_bad") < [r["doc_id"] for r in _rows].index("CP04_unlabeled")
     and _st["CP04_unlabeled"] == "성공")
show("③ 실패 문서의 화면에 블록이 떴다 (태그·다음 줄 — B61)",
     "[FAIL] P31" in _out6 and "▶ 다음 줄" in _out6
     and "python -m cli.register" in _out6)
show("끝에 모아 보이는 목록 — 성공·실패·미선택 3구획",
     all(k in IG.summary(_rows) for k in ("[성공]", "[실패]", "[미선택]")))
with _ctx.redirect_stdout(_io.StringIO()):
    _dry = IG.ingest_dir(_bd, dry_run=True)
show("ingest-dir --dry-run — 전부 선택만/미선택, 인입 0",
     all(r["status"] in ("선택만", "미선택") for r in _dry))
shutil.rmtree(_bd, ignore_errors=True)
for _f in ("CP01", "CP03_bad", "CP04_unlabeled"):
    (ROOT / "parsed" / f"{_f}.json").unlink(missing_ok=True)

# ── B61 ① 상태 거부는 원인과 다음 줄을 낸다 ──────────────────────────────
print("\n■ B61 ① — 상태 거부 문면의 계약 (사람이 치는 자리 전수)")

sys.path.insert(0, str(ROOT / "tests"))
import exits_scan as _EX                                         # noqa: E402

_rows61 = _EX.scan()
_st61 = [r for r in _rows61 if r["mark"] == "상태"]
# ⓑ **상태 거부 전건이 계약을 지킨다** — 원인만 말하고 끝내지 않는다.
def _at61(rows):
    return [r["file"] + ":" + str(r["line"]) for r in rows]


show("①ⓑ 상태 거부 전건에 그대로 칠 수 있는 다음 줄이 있다",
     _st61 and not _EX.broken(_rows61),
     f"상태 {len(_st61)}곳 · 위반 {_at61(_EX.broken(_rows61))}")
# ⓒ **분류 없는 거부가 0이다** — 새 `SystemExit`은 목록에 들거나 사용법으로 표시돼야
# 한다. 이것이 **다음 자리를 잡는 장치**다: 자리마다 고치면 다음 자리에서 또 난다.
show("①ⓒ 분류 없는 SystemExit이 0건이다 (새 거부는 표시해야 통과한다)",
     not _EX.unmarked(_rows61),
     f"{len(_rows61)}곳 전수 · 미분류 {_at61(_EX.unmarked(_rows61))}")
# ⓓ **변이** — 표시 없는 거부를 하나 넣으면 붉어진다(그리고 되돌린다).
_p61 = ROOT / "cli" / "viewer.py"
_src61 = _p61.read_text(encoding="utf-8")
_p61.write_text(_src61 + '\n\ndef _b61_probe():\n'
                         '    raise SystemExit("표시 없는 거부")\n', encoding="utf-8")
try:
    _mut61 = len(_EX.unmarked())
finally:
    _p61.write_text(_src61, encoding="utf-8")
show("①ⓓ 표시 없는 거부를 하나 넣으면 붉어진다 (되돌리면 초록)",
     _mut61 == 1 and not _EX.unmarked(), f"심었을 때 미분류 {_mut61}건")

# ── B69 ④ 다음 줄의 명령이 **실재하는가** ────────────────────────────────
#
# B68 회차 실측: `python run.py doctor`를 다음 줄로 주던 거부가 있었다 — 그런 명령이
# 없어 치면 `KeyError`다. 스캐너가 **접두만** 봐서 초록이었다. 「그대로 칠 수 있는
# 다음 줄」은 **칠 수 있어야** 계약이다(B61). 문면을 세지 않는다 — 이름의 실재만.
show("④ 다음 줄의 명령이 전부 실재한다 (run.py 명령표 · cli 모듈 · 파일)",
     not _EX.unknown_next(_rows61),
     str([r["file"] + ":" + str(r["line"]) + " " + r["cmd"]
          for r in _EX.unknown_next(_rows61)][:3]))
show("④ 명령 이름의 정본은 run.py의 명령표다 (문면을 읽지 않는다)",
     {"ingest-file", "register", "scan"} <= _EX.run_commands()
     and "doctor" not in _EX.run_commands(), f"{len(_EX.run_commands())}개")
# ⓑ **변이** — 없는 명령을 하나 심으면 붉어진다(그리고 되돌린다).
_src69 = _p61.read_text(encoding="utf-8")
_p61.write_text(_src69 + '\n\ndef _b69_probe():\n'
                         '    raise SystemExit("[viewer] 없다\\n'
                         '  ▶ 다음 줄:\\n     python run.py nosuch")  # [상태]\n',
                encoding="utf-8")
try:
    _mut69 = _EX.unknown_next()
finally:
    _p61.write_text(_src69, encoding="utf-8")
show("④ⓑ 없는 명령을 다음 줄로 주면 붉어진다 (되돌리면 초록)",
     len(_mut69) == 1 and _mut69[0]["cmd"] == "run:nosuch"
     and not _EX.unknown_next(), str([r["cmd"] for r in _mut69]))


# ── B70 ①② — mock 자산은 운영 경로에 섞이지 않는다 · 결손은 막는다 ────────
#
# 이식 직후 사내 화면이 **cp·pfmea·ipqc**를 대조 목록에 띄웠다(실측 열째 — 「mock이랑
# 비교 돌아가는 거 뭐야」). 내장 소재지(픽스처 어댑터 폴더·`schemas/*.json`)가
# `USE_MOCK`과 무관하게 열렸기 때문이다. mock 트랙은 남는다 — 섞이는 것만 걷는다.
print("\n■ B70 ①② — 내장은 mock일 때만 · 등록부 결손은 상태 거부")

from core import llm as _L70                                       # noqa: E402
from core import registry as _RG                                   # noqa: E402

_um70 = _L70.use_mock
_reg70 = dict(store.read(store.DOC_TYPES, {}))


def _live70(on):
    """`use_mock()`만 뒤집는다 — 실호출은 하지 않는다(설정도 건드리지 않는다)."""
    _L70.use_mock = (lambda: not on)


try:
    _live70(True)                                   # USE_MOCK=0 세계
    show("① USE_MOCK=0이면 doc_type은 **등록부가 전부**다 (내장 mock 자산 제외)",
         set(_RG.all_doc_types()) == set(_reg70),
         f"조회 {sorted(_RG.all_doc_types())} · 등록부 {sorted(_reg70)}")
    show("① USE_MOCK=0이면 스캔의 대조 목록도 등록부뿐이다 (기본 소재지 제외)",
         {str(f) for f, _m in SC.adapters()}
         == {str(ROOT / e["adapter"]) for e in _reg70.values() if e.get("adapter")},
         str(sorted(Path(f).name for f, _m in SC.adapters()))[:80])
    show("① 사람이 준 경로는 그대로 쓴다 — 명시는 의도다",
         [f.name for f, _m in SC.adapters(
             [str(ROOT / "tests/fixtures/adapters/cp.py")])] == ["cp.py"])
    _live70(False)                                  # USE_MOCK=1 — 지금과 같다
    show("① USE_MOCK=1은 지금 그대로다 (내장 + 기본 소재지 · 회귀가 이 세계에서 돈다)",
         {"cp", "pfmea"} <= set(_RG.all_doc_types())
         and any(f.name == "cp.py" for f, _m in SC.adapters()))

    # ② **결손은 빼지 않고 막는다** — 빼면 지금과 같은 「조용한 화면」이다.
    _ad70 = ROOT / "adapters" / "b70x.py"
    _sc70 = ROOT / "schemas" / "b70x.json"
    # **등재가 먼저다** — `schemas/b70x.json`이 먼저 있으면 그 파일의 실재가 곧
    # 내장 등록이라 `register`가 이름 중복으로 막는다(그 규칙은 그대로 옳다).
    _RG.register("b70x", layer="process", adapter="adapters/b70x.py",
                 schema="schemas/b70x.json", adapter_version="1.0",
                 approved_by="홍길동", approved_at="2026-09-15T00:00:00+00:00")
    _ad70.parent.mkdir(exist_ok=True)
    _ad70.write_text("ADAPTER = {}\n", encoding="utf-8")
    _sc70.write_text(json.dumps({"doc_type": "b70x"}, ensure_ascii=False),
                     encoding="utf-8")
    show("② 실물이 있으면 결손 0이다 (시험의 전제)", not _RG.missing_assets())
    _ad70.unlink()                                  # 이식에서 빠진 그 상태
    _miss70 = _RG.missing_assets()
    show("② 등록부가 가리키는 실물이 없으면 결손으로 잡힌다 (조회처는 하나다)",
         [(m["doc_type"], m["kind"]) for m in _miss70] == [("b70x", "adapter")],
         str(_miss70))
    try:
        SC.adapters()
        _rc70 = ""
    except SystemExit as e:
        _rc70 = str(e)
    show("② scan·인입 진입이 **상태 거부**다 — 이름과 다음 줄이 문면에 있다",
         "b70x" in _rc70 and "adapters/b70x.py" in _rc70
         and "python -m cli.register generate b70x" in _rc70,
         _rc70.splitlines()[0] if _rc70 else "거부 없음")
    show("② 승인자·등록 시점을 함께 말한다 (누가 언제 등록한 것이 비었나)",
         "홍길동" in _rc70 and "2026-09-15" in _rc70)
    _b70 = _io.StringIO()
    with _ctx.redirect_stdout(_b70):
        PF.cmd_doctypes()
    show("② platform doctypes가 실물 유무를 표시한다 (✗가 화면에 뜬다)",
         "adapter ✗" in _b70.getvalue() and "실물 없는 등록" in _b70.getvalue(),
         [l.strip() for l in _b70.getvalue().splitlines() if "b70x" in l][:1])
finally:
    _L70.use_mock = _um70
    _RG.unregister("b70x")
    for _p70 in (ROOT / "adapters" / "b70x.py", ROOT / "schemas" / "b70x.json"):
        _p70.unlink(missing_ok=True)
show("② 뒷정리 — 결손 0 · 등록부 원상 (회귀가 남기는 것 0)",
     not _RG.missing_assets() and set(store.read(store.DOC_TYPES, {})) == set(_reg70))

# ── B72 ②③④ — 인입 화면: 예고 · 큐는 사실 단위 · 다음 줄 · 단계 ──────────
#
# 사내 첫 실인입에서 드러난 것 넷: ①「스키마에 없는 필드 'meta'」가 **행마다**
# ②골격 밖 좌표가 몇 개인지·드랍인지·어떻게 잇는지 화면이 말하지 않았다
# ③「선택만」의 뜻이 없었다 ④2만 토큰을 쓰고 나서야 비용을 알았다.
print("\n■ B72 ②③④ — 인입 화면(예고 · 큐 집계 · 다음 줄 · --step)")

import subprocess as _sp72                                         # noqa: E402
from core import pipeline as _PL72                                 # noqa: E402
from core.pipeline import run_document as _run72                   # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _env72(doc_id, n=5, ref=None):
    _e = json.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
    _e["doc_id"], _e["records"] = doc_id, _e["records"][:n]
    if ref:
        for r in _e["records"]:
            r["process_ref"] = ref
    return _e


def _q72(kind, doc_id=None):
    return [x for x in store.read(store.QUEUE, [])
            if x["kind"] == kind and (doc_id is None or x["doc_id"] == doc_id)]


# ② 같은 필드 N행 → 큐 1건 · rows == N
_meta72 = _env72("B72META", 6)
for _r in _meta72["records"]:
    _r["meta"] = {"개정일": "2026-01-01"}          # 사내가 받은 그 산출의 모양
_run72(_meta72)
_uf72 = _q72("unknown_field", "B72META")
show("② 같은 필드 N행 → 큐 **1건**이고 rows == N (사람이 판정할 것은 하나다)",
     len(_uf72) == 1 and (_uf72[0]["payload"] or {}).get("rows") == 6
     and _uf72[0]["payload"].get("key") == "meta",
     f"{len(_uf72)}건 · rows {(_uf72[0]['payload'] or {}).get('rows') if _uf72 else '-'}")
show("② 값과 발자국을 버리지 않는다 — items[]·locators에 남는다 (G5)",
     len((_uf72[0]["payload"] or {}).get("items") or []) == 6
     and (_uf72[0]["payload"] or {}).get("locators"),
     str((_uf72[0]["payload"] or {}).get("locators"))[:60])

# ② orphan 표기 k종 → k건
_o72 = _env72("B72ORPH", 6)
for _i, _r in enumerate(_o72["records"]):
    _r["process_ref"] = "없는공정ZZ" if _i % 2 else "없는공정YY"
_run72(_o72)
_oa72 = _q72("orphan_anchor", "B72ORPH")
show("② 목록 밖 좌표 k표기 → 큐 k건 (행이 아니라 표기가 단위다)",
     len(_oa72) == 2
     and {(x["payload"] or {}).get("key") for x in _oa72} == {"없는공정ZZ", "없는공정YY"},
     f"{len(_oa72)}건 · {sorted((x['payload'] or {}).get('key') for x in _oa72)}")
show("② 행 단위 재시도 재료는 그대로 남는다 (items[]에 행마다)",
     all(len((x["payload"] or {}).get("items") or []) == 3 for x in _oa72),
     str([len((x['payload'] or {}).get('items') or []) for x in _oa72]))
show("② 큐 kind는 닫힌 20종 그대로다 (집계는 세는 단위만 바꾼다)",
     len(PF.QUEUE_KINDS) == 20 and not PF.queue_view()["alien"],
     str(PF.queue_view()["alien"]))

# ② 예고 종수 == 실제 판정 호출 수 (사전 히트 제외)
from core import matcher as _MT72                                  # noqa: E402
_calls72 = []
_m0 = _MT72.match


def _spy72(surface, *a, **k):
    _calls72.append(surface)
    return _m0(surface, *a, **k)


_plan72 = {}
_MT72.match = _spy72
try:
    _e72 = _env72("B72PLAN", 8)
    _run72(_e72, notice=lambda i: _plan72.update(i) if i.get("단계") == "판정예고" else None)
finally:
    _MT72.match = _m0
# **예고는 덜 말하면 안 된다** — 상한이 실제를 덮는다. 개체 판정은 행마다 돌고
# (스코프가 행마다 다르다) — 좌표 태깅(B69)의 표기 dedupe를 여기에 그대로 적용할
# 수 없는 이유다(D-151 ②). **재는 단위는 판정 함수 도달이다**(B74 ①): 사전 히트는
# `match`를 지나지만 exact에서 끊겨 LLM을 부르지 않고, 예고는 그 수를 같은 키로
# 세어 빼기 때문에 상한이 「호출」을 말한다.
show("② 예고의 상한이 실제 판정 호출을 덮는다 (덜 말하지 않는다)",
     _plan72 and _MT72.STATS["판정"] <= _plan72["예상_호출"],
     f"예고 ≤{_plan72.get('예상_호출')} · 실제 {_MT72.STATS['판정']} "
     f"(match 도달 {len(_calls72)} · 사전 {_MT72.STATS['사전']} "
     f"· 표기 {_plan72.get('표기_종수')}종)")
show("② 예고가 표기 종수·사전 히트를 함께 낸다 (반복되는 문서인지가 판단 재료다)",
     _plan72.get("표기_종수") and _plan72["표기_종수"] <= _plan72["값_수"])

# ② 요약 줄의 수가 그래프·큐 실물과 같다
_sum72 = {}
_g0 = len(open_graph("process").nodes)
_e72b = _env72("B72SUM", 4)
_run72(_e72b, notice=lambda i: _sum72.update(i) if i.get("단계") == "끝" else None)
show("② 요약의 노드 증분이 그래프 실물과 같다 (화면이 제 계산을 하지 않는다)",
     _sum72.get("노드") == len(open_graph("process").nodes) - _g0,
     f"요약 +{_sum72.get('노드')} · 실물 +{len(open_graph('process').nodes) - _g0}")
show("② 요약의 큐 집계가 큐 실물과 같다",
     _sum72.get("큐") == _PL72.doc_queue_summary("B72SUM"))

# ③ orphan_anchor의 다음 줄 — **보류이지 드랍이 아니다**
_next72 = PF.orphan_next_lines(_oa72[0])
show("③ 다음 줄이 세 줄이다 — alias 추가 · bootstrap · 재인입",
     "skeleton.json" in _next72 and "run.py bootstrap" in _next72
     and "ingest-file" in _next72)
show("③ 그대로 칠 수 있다 — 층·문서·doc_type이 자리표시자가 아니다",
     "layers/process/skeleton.json" in _next72 and "<층>" not in _next72
     and "--doc-type cp" in _next72,
     [l.strip() for l in _next72.splitlines() if "ingest-file" in l][:1])
show("③ `init --fresh`를 시키지 않는다 (그래프·사전을 지운다 — 가이드 §7 정정)",
     "--fresh" not in _next72)

# ③ⓑ alias 추가 + bootstrap(fresh 없이) → 노드·사전 불변 · 재인입이 보류분을 붙인다
_seed72 = ROOT / "layers" / "process" / "skeleton.json"
_orig72 = _seed72.read_text(encoding="utf-8")
_n72 = len(open_graph("process").nodes)
try:
    _sd = json.loads(_orig72)
    _sd.setdefault("ALIASES", {}).setdefault("노칭", []).append("없는공정ZZ")
    _seed72.write_text(json.dumps(_sd, ensure_ascii=False, indent=2), encoding="utf-8")
    bootstrap("process", echo=False)
    show("③ⓑ alias만 더하고 bootstrap하면 노드 수가 그대로다 (지우지 않는다)",
         len(open_graph("process").nodes) == _n72,
         f"{_n72} → {len(open_graph('process').nodes)}")
    _re72 = _env72("B72ORPH", 6)          # 같은 문서 재인입 — 보류분이 붙는다
    for _i, _r in enumerate(_re72["records"]):
        _r["process_ref"] = "없는공정ZZ" if _i % 2 else "없는공정YY"
    _run72(_re72)
    _PL72.finalize()
    _left72 = {(x["payload"] or {}).get("key") for x in _q72("orphan_anchor", "B72ORPH")}
    show("③ⓑ 재인입 뒤 이어진 표기의 보류가 내려간다 (남는 것은 아직 없는 표기뿐)",
         "없는공정ZZ" not in _left72 and "없는공정YY" in _left72, str(sorted(_left72)))
finally:
    _seed72.write_text(_orig72, encoding="utf-8")
    bootstrap("process", echo=False)

# ④ --step — 단계 7 · 비대화형 무시 · q에서 그래프 쓰기 0
from cli import ingest as _IG72                                    # noqa: E402
show("④ 단계는 7이고 문면의 자리는 진입점 옆 상수 하나다",
     len(_IG72.STEPS) == 7 and all(len(x) == 2 and x[1] for x in _IG72.STEPS),
     str([n for n, _w in _IG72.STEPS]))
_r72 = _sp72.run([sys.executable, str(ROOT / "run.py"), "ingest-file",
                  str(ROOT / "tests/fixtures/raw/CP01.xlsx"), "--doc-type", "cp",
                  "--step", "--allow-mock"], capture_output=True, text=True,
                 cwd=str(ROOT), stdin=_sp72.DEVNULL)
show("④ 비대화형에서는 무시하고 **그 사실을 말한다** (묻고 EOF로 멈추지 않는다)",
     "--step 무시" in _r72.stdout and _r72.returncode == 0,
     [l.strip() for l in _r72.stdout.splitlines() if "--step" in l][:1])
# **q에서 멈추면 그래프 쓰기 0** — 판정 예고까지는 읽기만 한다. 대화형이어야
# `--step`이 사므로 pty로 띄운다(비대화형은 위에서 무시를 잰다).
def _step_run72(answers):
    import os, pty
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), "ingest-file",
                                  str(ROOT / "tests/fixtures/raw/CP01.xlsx"),
                                  "--doc-type", "cp", "--step", "--allow-mock"])
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    os.waitpid(pid, 0)
    return out.decode("utf-8", "replace")


init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_n72q = len(open_graph("process").nodes)
_scr72 = _step_run72("c\nc\nc\nq\n")
show("④ 판정 예고에서 q → 그래프 쓰기 0 (읽기만 한 자리에서 멈춘다)",
     len(open_graph("process").nodes) == _n72q and "[4/7]" in _scr72
     and "멈춤 —" in _scr72,
     f"노드 {_n72q} → {len(open_graph('process').nodes)}")
show("④ 멈춘 화면이 **이어서 넣는 다음 줄**을 준다 (막다른 길 0 · B61)",
     "ingest-file" in _scr72.split("멈춤 —")[-1]
     and "skeleton.json" in _scr72.split("멈춤 —")[-1])
_scr72c = _step_run72("c\nc\nc\nc\nc\nc\nc\n")
show("④ 끝까지 가면 7단계가 다 뜨고 인입이 끝난다",
     all(f"[{i}/7]" in _scr72c for i in range(1, 8)) and "인입 끝" in _scr72c,
     [l.strip() for l in _scr72c.splitlines() if "인입 끝" in l][:1])

# ── B73 ①②③ — 후보는 전량이 아니다 · retry는 조건부 · auto는 표시된다 ─────
#
# 사내 실측 열두째: 판정 호출의 **입력 토큰이 누적 2만**(출력 40 이하). 후보가
# 카테고리·층 전량이라 노드가 늘수록 매 호출이 커졌다. 명세는 처음부터 다르게
# 말한다 — 문서 4 §4.2 ②「후보 검색 — 사전 미스 시 임베딩 유사도」.
print("\n■ B73 ①②③ — 후보 상한 · 조건부 retry · auto 표시")

from core import matcher as _MT73                                  # noqa: E402
from core.dictionary import Dictionary as _DIC73                   # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_g73 = open_graph("process")
_cfg73 = load_config("process")
_dic73 = _DIC73.open()
# 같은 카테고리에 노드를 많이 세운다 — 「전량이면 커진다」를 재는 조건.
for _i in range(60):
    _g73.add_node(f"노칭::설비{_i:02d}", "Unit", "auto", provenance=["t"],
                  parent="노칭" if _i % 2 else "스태킹", _scoped=True)
_g73.save()
_c73 = _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73)
show("① 후보 수가 상한 안이다 (전량이 아니다)",
     len(_c73) <= _MT73.CANDIDATE_TOP_N,
     f"후보 {len(_c73)} · 상한 {_MT73.CANDIDATE_TOP_N} · 층 노드 {len(_g73.nodes)}")
show("① 상한이 손잡이 하나다 (코드에 흩어져 있지 않다)",
     isinstance(_MT73.CANDIDATE_TOP_N, int) and _MT73.CANDIDATE_TOP_N > 0)
# **스코프 근처가 먼저다** — 같은 부모 아래 노드가 다른 부모보다 앞선다.
_cs73 = _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73,
                         parent="노칭", cfg=_cfg73)
show("① 같은 부모 아래 후보가 있으면 다른 부모는 먼저 오지 않는다 (스코프 근처)",
     _cs73 and all(c.get("parent") == "노칭" for c in _cs73),
     f"{len(_cs73)}건 · 부모 {sorted({c.get('parent') for c in _cs73})}")
show("① 스코프 단계는 임베딩을 부르지 않는다 (LLM·임베딩 0)",
     (_MT73.STATS.get("스코프", 0) + _MT73.STATS.get("스코프+", 0)) >= 1
     and _MT73.STATS.get("임베딩", 0) == 0,
     str({k: v for k, v in _MT73.STATS.items() if v}))
# **입력 크기가 노드 수와 무관하다** — 판정에 올라가는 후보 JSON의 바이트.
_b1 = len(json.dumps(_MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73),
                     ensure_ascii=False).encode())
for _i in range(60, 500):
    _g73.add_node(f"노칭::설비{_i:03d}", "Unit", "auto", provenance=["t"])
_g73.save()
_b2 = len(json.dumps(_MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73),
                     ensure_ascii=False).encode())
show("① 노드가 8배로 늘어도 판정 입력 크기가 그대로다 (비용이 그래프에 비례하지 않는다)",
     _b2 <= _b1 * 1.2, f"노드 {len(_g73.nodes)} · {_b1:,}B → {_b2:,}B")
# **사전 히트는 상한과 무관하게 포함된다** — 결정적 경로가 잘리면 안 된다.
_nid73 = _g73.add_node("노칭::사전설비", "Unit", "auto", provenance=["t"])
_dic73.register("노칭::사전설비", _nid73, provenance="t")
_ce73 = _MT73.candidates("노칭::사전설비", "Unit", "process", _g73, _dic73)
show("① 사전 히트는 상한과 무관하게 포함된다 (결정적 경로를 자르지 않는다)",
     any(c.get("exact") and c["id"] == _nid73 for c in _ce73))
show("① mock 세계에서 좁히기에 LLM 0 (어휘 겹침으로 고른다)",
     _MT73.STATS.get("겹침", 0) >= 1 and _MT73.STATS.get("임베딩", 0) == 0,
     str({k: v for k, v in _MT73.STATS.items() if v}))
# **실호출 갈래는 임베딩을 부른다** — 배선의 증거는 미설정 실패(NotConfigured)다.
# **조건이 옮겨졌다**(B75 ①): `auto`에서는 임베딩이 없으면 겹침으로 떨어지는 것이
# 정답이라 이 지점에 닿지 않는다. 그래서 **사람이 켰을 때**(`CANDIDATE_NARROW=embed`)
# 로 잰다 — 어서션을 지우지 않고 조건을 옮긴다(문서 7 §7.6-2의 9지점 도달성).
_um73 = _MT73.llm.use_mock
_MT73.llm.use_mock = lambda: False
_MT73.llm.set_narrow("embed")
try:
    _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73)
    _emb73 = "불렀는데 조용히 통과"
except Exception as _e73:
    _emb73 = type(_e73).__name__
finally:
    _MT73.llm.set_narrow(None)
    _MT73.llm.use_mock = _um73
show("① 실호출 경로가 embed()에 닿는다 (CANDIDATE_NARROW=embed · 미설정이면 시끄럽게)",
     _emb73 == "NotConfigured", _emb73)

# ③ 후보에 status — auto는 표시되고, 유사도 매칭은 uncertain으로 내려간다
show("③ 후보가 status와 근거 건수를 싣는다 (판정이 auto를 안다)",
     all("status" in c and "evidence" in c for c in _ce73))
_auto73 = [c for c in _MT73.candidates("노칭::설비00", "Unit", "process", _g73, _dic73)
           if c.get("status") == "auto" and not c.get("exact")]
_v73 = _MT73.match("노칭::설비0", _auto73, "Unit", _cfg73)
show("③ auto 후보에 **유사도로는 붙지 않는다** (uncertain — 연쇄를 끊는다)",
     _v73["type"] == _MT73.UNCERTAIN or _v73["matched_id"] is None, str(_v73))
_conf73 = [dict(c, status="confirmed") for c in _auto73]
_v73b = _MT73.match("노칭::설비0", _conf73, "Unit", _cfg73)
show("③ confirmed 후보는 지금과 같다 (사람이 확인한 노드에는 붙는다)",
     _v73b["type"] == _MT73.MATCH, str(_v73b))
show("③ 지시문이 그 규칙을 말하고 판이 올랐다",
     "status" in (ROOT / "prompts/3.4_judge.md").read_text(encoding="utf-8")
     and "version: j-1.1" in (ROOT / "prompts/3.4_judge.md").read_text(encoding="utf-8"))

# ② retry는 조건부다 — 후보 집합이 그대로면 LLM 0
from core import retry as _RT73                                    # noqa: E402
init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_e73 = json.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
_e73["doc_id"], _e73["records"] = "B73ORPH", _e73["records"][:4]
for _r in _e73["records"]:
    _r["process_ref"] = "없는공정QQ"
_run72(_e73)
_RT73.retry_orphans()
_it73 = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
_at1 = _it73[0].get("attempts") if _it73 else None
_RT73.retry_orphans()                      # 그래프 불변 — 다시 돌 이유가 없다
_it73b = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
_at2 = _it73b[0].get("attempts") if _it73b else None
show("② 후보 집합이 그대로면 재시도가 돌지 않는다 (같은 답을 비용으로 바꾸지 않는다)",
     _at1 == _at2 and _at1, f"attempts {_at1} → {_at2}")
show("② 항목이 이력을 갖는다 — attempts · first_seen · last_tried",
     all(k in _it73b[0] for k in ("attempts", "first_seen", "last_tried")),
     str({k: v for k, v in _it73b[0].items()
          if k in ("attempts", "first_seen")})[:80])
# **이력은 payload 밖이다** — payload는 동일성 키이고 거기에 시각이 들어가면
# 「클린 2회 동일 그래프」가 깨진다(이 회차에서 한 번 깼다 · D-152).
show("② 이력이 payload를 오염시키지 않는다 (멱등 판정의 대조 단위)",
     not any(k in (_it73b[0]["payload"] or {})
             for k in ("attempts", "last_tried", "last_fp")))
_it73b[0].update({"attempts": _RT73.ATTEMPT_MAX, "last_fp": ""})
store.write(store.QUEUE, _it73b + [x for x in store.read(store.QUEUE, [])
                                   if x["kind"] != "orphan_anchor"])
_RT73.retry_orphans()
_it73c = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
show("② 상한을 넘으면 더 돌지 않는다 (사람 판정 대기)",
     _it73c[0].get("attempts") == _RT73.ATTEMPT_MAX)
_qb73 = _io.StringIO()
with _ctx.redirect_stdout(_qb73):
    PF.cmd_queue("orphan_anchor")
show("② 화면이 이력을 말한다 (몇 회 돌았고 끝났는지)",
     "회 재시도" in _qb73.getvalue() and "사람 판정 대기" in _qb73.getvalue(),
     [l.strip() for l in _qb73.getvalue().splitlines() if "재시도" in l][:1])
# ════════════════════════════════════════════════════════════════════
# B74 — 사전 키 = 조회 키 · 판정 대장 · 뷰어 재료 · 행별 report
# ════════════════════════════════════════════════════════════════════
print("\n── B74 ① 사전이 실제로 히트한다 (키 = 조회 키) ──")
from core import ledger as _LG74                                   # noqa: E402
from core import matcher as _MT74                                  # noqa: E402
from core import llm as _LL74                                      # noqa: E402
from core.build import entity_key as _KEY74                        # noqa: E402
from core.dictionary import Dictionary as _DIC74                   # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _ingest74(doc_id, n=6):
    """같은 문서를 두 번 넣는 자리 — 예고·판정·실호출 사용량을 같이 받는다."""
    seen = {"쓴_호출": _LL74.usage_total()["calls"]}
    _run72(_env72(doc_id, n), notice=lambda i: seen.setdefault(i["단계"], i))
    seen["쓴_호출"] = _LL74.usage_total()["calls"] - seen["쓴_호출"]
    return seen


_a74 = _ingest74("B74DOC")
_s1 = dict(_MT74.STATS)
_b74 = _ingest74("B74DOC")
_s2 = dict(_MT74.STATS)
show("① 2회째 인입은 **판정 함수에 도달하지 않는다** (전부 exact 경로)",
     _s2["판정"] == 0 and _s2["사전"] > 0,
     f"1회차 판정 {_s1['판정']}·사전 {_s1['사전']} → 2회차 판정 {_s2['판정']}"
     f"·사전 {_s2['사전']}")
show("① 예고의 사전 히트 == 판정의 사전 경로 수 (같은 키·같은 함수)",
     _b74["판정예고"]["사전_히트"] == _s2["사전"],
     f"예고 {_b74['판정예고']['사전_히트']} · 판정 {_s2['사전']}")
show("① 예고의 상한이 실제 호출을 덮는다 (처음 인입 — 사전이 도는 중에 찬다)",
     _a74["판정예고"]["예상_호출"] >= _s1["판정"],
     f"예고 ≤{_a74['판정예고']['예상_호출']} · 실제 {_s1['판정']}")

_g74 = open_graph("process")
_cfg74 = load_config("process")
_dic74 = _DIC74.open()
_u74 = next(n for n in _g74.nodes.values()
            if n.get("category") == "Unit" and n.get("status") == "auto")
_pa74 = _u74.get("parent") or _u74.get("mirror_scope")
_sc74 = (_cfg74.get("canonical_scope") or {}).get("bind_categories", [])
_k74, _pol74, _, _ = _KEY74(_u74["canonical"].split("::")[-1], "Unit", _cfg74,
                            parent_canonical=_pa74)
show("① 등재된 키가 **해소가 여는 키**다 (exact 후보가 선다)",
     any(c["id"] == _u74["id"] for c in
         _MT74.dict_hits(_k74, "Unit", "process", _g74, _dic74,
                         polarity=_pol74, parent=_pa74, scope_cats=_sc74)),
     f"키 {_k74!r}")
show("① 같은 표기·**다른 부모**는 exact에 들지 않는다 (notching/separator의 cutter)",
     not _MT74.dict_hits(_k74, "Unit", "process", _g74, _dic74,
                         polarity=_pol74, parent="다른공정XX",
                         scope_cats=_sc74))
show("① 원 표기 키는 그대로 남는다 (질의 링킹의 표면형 스캔)",
     any(_n74 == _u74["canonical"].split("::")[-1]
         for _n74 in _dic74.surfaces()),
     f"사전 표기 {len(list(_dic74.surfaces()))}종")
_dup74 = _sp72.run([sys.executable, str(ROOT / "tests/dup_scan.py")],
                   capture_output=True, text=True, cwd=str(ROOT))
show("① 같은 층·같은 canonical·live 노드는 하나뿐이다 (상시 어서션)",
     _dup74.returncode == 0, (_dup74.stdout or "").strip().splitlines()[-1][:70])

print("\n── B74 ② 판정 대장 ──")
_led74 = _LG74.read("B74DOC")
_rows74 = (_led74 or {}).get("rows") or []
_env74 = _env72("B74DOC", 6)
_sch74 = json.loads((ROOT / "schemas/cp.json").read_text(encoding="utf-8"))
_f74 = _sch74["fields"]
_vals74 = sum(1 for r in _env74["records"] for f, sp in _f74.items()
              if sp.get("role") == "entity" and isinstance(r.get(f), str)
              and r[f].strip())
_anc74 = len(_env74["records"])
_att74 = sum(1 for r in _env74["records"] for f, sp in _f74.items()
             if sp.get("role") in ("attribute", "content")
             and r.get(f) not in (None, "")
             and r.get(sp.get("attach_to_field")) not in (None, ""))
show("② 행 수 == entity 값 수 + anchor 행 수 + 부착 시도 수",
     len(_rows74) == _vals74 + _anc74 + _att74,
     f"{len(_rows74)} == {_vals74}+{_anc74}+{_att74}")
show("② path·verdict가 닫힌 값 밖이면 없다",
     all(r["path"] in _MT74.PATHS and r["verdict"] in _LG74.VERDICTS
         for r in _rows74),
     f"path {sorted({r['path'] for r in _rows74})}")
show("② 재인입 뒤 이전 대장이 남지 않는다 (덮는다 — 정본이 아니라 장부다)",
     all(r["verdict"] != "new" for r in _rows74)
     and sum(1 for r in _rows74 if r["role"] == "entity") == _vals74,
     f"판정 {sorted({r['verdict'] for r in _rows74})}")
show("② 대장의 llm.calls 합 == 그 인입이 실제로 부른 수 (mock 세계는 0이다)",
     sum((r.get("llm") or {}).get("calls", 0) for r in _rows74) == _b74["쓴_호출"],
     f"대장 {sum((r.get('llm') or {}).get('calls', 0) for r in _rows74)} "
     f"· 실제 {_b74['쓴_호출']}")
_v74 = _MT74.match("아무것도없는표기ZZ", [], "Unit", _cfg74)
show("② 판정 반환에 path 한 키가 늘고 계약 3키는 그대로다 (문서 4 §4.3-6)",
     set(_v74) >= {"type", "matched_id", "confidence", "path"}
     and _v74["path"] in _MT74.PATHS, str(_v74))

print("\n── B74 ③ 뷰어 재료 ──")
from cli import export as _EXP74                                   # noqa: E402
_nd74, _ed74 = _EXP74.graph_data(_EXP74._world())
show("③ 엣지가 status·prov·id를 지고 간다 (저장에는 있었는데 화면에 없었다)",
     all({"status", "prov", "id"} <= set(e) for e in _ed74))
show("③ 노드의 made_by가 닫힌 집합 ∪ {seed, unknown}이다",
     all(n["made_by"] in tuple(_MT74.PATHS) + ("seed", "unknown")
         for n in _nd74),
     str(sorted({n["made_by"] for n in _nd74})))
_html74 = _EXP74.build_html(_EXP74._world())
show("③ html의 DATA에 rel·made_by가 실리고 외부 CDN이 0이다",
     '"rel"' in _html74 and '"made_by"' in _html74
     and 'src="http' not in _html74 and 'href="http' not in _html74)
_doc74 = "B74DOC"
_filtered = {n["id"] for n in _nd74 if _doc74 in (n.get("docs") or [])}
_showdoc = {n["id"] for _l, _gg in _EXP74._world().items()
            for n in _gg.nodes.values()
            if ops.is_live(n) and any(str(p).startswith(_doc74)
                                  for p in n.get("provenance") or [])}
show("③ 문서 필터로 거른 노드 집합 == show doc의 노드 집합",
     _filtered == _showdoc and _filtered,
     f"{len(_filtered)}개")

print("\n── B74 ④ 행별 show report ──")
from cli import show as _SH74                                      # noqa: E402
_buf74 = _io.StringIO()
with _ctx.redirect_stdout(_buf74):
    _SH74.cmd_report([_doc74])
_out74 = _buf74.getvalue()
_su74 = _LG74.summary(_rows74)
show("④ 머리 집계의 각 수 == 대장에서 센 수",
     all(f"{k} {v}" in _out74 for k, v in
         (("값", _su74["값"]), ("사전", _su74["사전"]), ("신규", _su74["신규"]),
          ("불확실", _su74["불확실"]))),
     _out74.splitlines()[1].strip()[:70])
_jb74 = _io.StringIO()
with _ctx.redirect_stdout(_jb74):
    _SH74.cmd_report([_doc74, "--json"])
show("④ --json의 행 수 == 대장 행 수",
     len(json.loads(_jb74.getvalue())["rows"]) == len(_rows74))
try:
    _SH74.cmd_report(["없는문서ZZ"])
    _ref74 = ""
except SystemExit as e:
    _ref74 = str(e)
show("④ 없는 doc_id는 **상태 거부**다 (원인 + 칠 수 있는 다음 줄)",
     "대장" in _ref74 and "▶ 다음 줄" in _ref74
     and ("python run.py" in _ref74 or "python -m cli." in _ref74),
     _ref74.splitlines()[0][:70] if _ref74 else "거부하지 않았다")
_db74 = _io.StringIO()
with _ctx.redirect_stdout(_db74):
    _SH74.cmd_doc([_doc74])
show("④ show doc 끝이 행별 명령을 가리킨다 (진입점을 늘리지 않는다)",
     f"show report {_doc74}" in _db74.getvalue(),
     _db74.getvalue().strip().splitlines()[-1].strip()[:70])

# ════════════════════════════════════════════════════════════════════
# B75 — 임베딩은 선택 · 스코프는 하드 필터 · 비용은 실패해도 보인다
# ════════════════════════════════════════════════════════════════════
print("\n── B75 ① 임베딩은 선택이다 ──")
from core import embeddings as _EM75                              # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _env75(doc_id, names, ref="노칭"):
    """같은 공정 아래 **서로 다른 관리항목 N개** — 후보가 상한을 넘게 만드는 재료."""
    e = json.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
    base = dict(e["records"][0])
    e["doc_id"] = doc_id
    e["records"] = []
    for i, nm in enumerate(names):
        r = dict(base)
        r.update({"source_locator": f"X{i}", "process_ref": ref,
                  "process_group": "조립", "관리항목": nm, "설비": "노칭 프레스"})
        e["records"].append(r)
    return e


# 상한(12)을 넘는 후보를 같은 부모 아래 세운다 — 여기서만 좁히기가 돈다.
_run72(_env75("B75SEED", [f"노칭 항목{i:02d}" for i in range(20)]))
_MT74.reset_stats()
_run72(_env75("B75AUTO", [f"노칭 항목{i:02d}변형" for i in range(6)]))
_led75 = (_LG74.read("B75AUTO") or {}).get("rows") or []
_paths75 = {r["path"] for r in _led75}
show("① 임베딩 미설정·auto에서 인입이 끝까지 돌고 겹침으로 좁힌다",
     "overlap+judge" in _paths75 and "embedding+judge" not in _paths75
     and _MT74.STATS["겹침"] >= 1,
     f"path {sorted(_paths75)} · 겹침 {_MT74.STATS['겹침']} · "
     f"임베딩 {_MT74.STATS['임베딩']}")
show("① mock의 기본은 겹침이다 (회귀 세계 불변 — sha256 벡터를 쓰지 않는다)",
     _LL74.narrow_choice() == ("overlap", "mock"), str(_LL74.narrow_choice()))

_seen75 = []
_e0 = _EM75.embed
_EM75.embed = lambda t: _seen75.append(t) or _e0(t)
_um75 = _MT74.llm.use_mock
_MT74.llm.use_mock = lambda: False          # 실호출 세계 — 좁히기는 설정이 가른다
_MT74.llm.set_narrow("overlap")
try:
    _MT74.reset_stats()
    _cdo75 = _MT74.candidates("노칭::항목없음ZZ", "Property", "process",
                              open_graph("process"), _DIC74.open(),
                              parent="노칭", cfg=load_config("process"))
    _over75 = "돌았다"
except Exception as _x75:
    _over75 = f"{type(_x75).__name__}: {_x75}"
finally:
    _MT74.llm.set_narrow(None)
    _MT74.llm.use_mock = _um75
    _EM75.embed = _e0
show("① `overlap` 강제면 **실호출 모드에서도** embed()에 닿지 않는다",
     _over75 == "돌았다" and not _seen75 and _MT74.STATS["겹침"] >= 1,
     f"{_over75} · embed 호출 {len(_seen75)} · 겹침 {_MT74.STATS['겹침']}")

import os as _os75                                                # noqa: E402
_os75.environ["CANDIDATE_NARROW"] = "embed"
try:
    _cfg75 = _LL74.config()["narrow"]
    _LL74.set_narrow("overlap")
    _won75 = _LL74.narrow_choice()
finally:
    _LL74.set_narrow(None)
    del _os75.environ["CANDIDATE_NARROW"]
show("① 플래그가 설정을 이긴다 (한 문서만 바꿔 비교한다)",
     _cfg75 == "embed" and _won75 == ("overlap", "플래그"),
     f"설정 {_cfg75} · 플래그 뒤 {_won75}")

# --diff — 다름의 기준은 판정과 node다
_a75 = {"doc_id": "A", "rows": [
    {"locator": "R1", "field": "관리항목", "surface": "가", "canonical": "노칭::가",
     "path": "overlap+judge", "verdict": "match", "node_id": "N1",
     "candidates_n": 3, "llm": {"in_tokens": 10, "out_tokens": 5}},
    {"locator": "R2", "field": "관리항목", "surface": "나", "canonical": "노칭::나",
     "path": "overlap+judge", "verdict": "new", "node_id": "N2",
     "candidates_n": 3, "llm": {"in_tokens": 10, "out_tokens": 5}}]}
_b75 = json.loads(json.dumps(_a75))
_b75["rows"][1].update(verdict="match", canonical="노칭::다", node_id="N9",
                       path="embedding+judge")
(ROOT / "data" / "b75a.json").write_text(json.dumps(_a75, ensure_ascii=False),
                                         encoding="utf-8")
(ROOT / "data" / "b75b.json").write_text(json.dumps(_b75, ensure_ascii=False),
                                         encoding="utf-8")
_db75 = _io.StringIO()
with _ctx.redirect_stdout(_db75):
    _SH74.cmd_report(["--diff", str(ROOT / "data/b75a.json"),
                      str(ROOT / "data/b75b.json")])
_want75 = sum(1 for x, y in zip(_a75["rows"], _b75["rows"])
              if x["verdict"] != y["verdict"] or x["canonical"] != y["canonical"])
show("① `--diff`의 행 수 == 판정 또는 node가 다른 값의 수",
     f"다른 행 {_want75} / 전체 2" in _db75.getvalue(),
     _db75.getvalue().splitlines()[0][:70])
show("① 경로만 달라도 답이 같으면 다른 행이 아니다 (도구는 차이만 보인다)",
     "다른 행 1 /" in _db75.getvalue())
for _f75 in ("b75a.json", "b75b.json"):
    (ROOT / "data" / _f75).unlink(missing_ok=True)      # 시험 재료는 남기지 않는다

print("\n── B75 ② 스코프는 하드 필터다 ──")
_g75 = open_graph("process")
_dic75 = _DIC74.open()
_cfg75b = load_config("process")
_sc75 = (_cfg75b.get("canonical_scope") or {}).get("bind_categories", [])
_cd75 = _MT74.candidates("노칭::없는항목ZZ", "Property", "process", _g75, _dic75,
                         parent="노칭", cfg=_cfg75b)
show("② 판정에 오른 후보 전부 parent가 값의 parent와 같다",
     _cd75 and all(c.get("parent") == "노칭" for c in _cd75),
     f"후보 {len(_cd75)}개 · 부모 {sorted({c.get('parent') for c in _cd75})}")
_MT74.reset_stats()
_cd75b = _MT74.candidates("새공정::없는항목ZZ", "Property", "process", _g75, _dic75,
                          parent="아무도없는공정ZZ", cfg=_cfg75b)
_v75 = _MT74.match("새공정::없는항목ZZ", _cd75b, "Property", _cfg75b)
show("② 같은 부모 아래가 0개면 후보 0 · LLM 0 · NEW (답이 정해져 있다)",
     not _cd75b and _v75["type"] == _MT74.NEW and _MT74.STATS["판정"] == 0
     and _MT74.STATS["스코프끝"] == 1,
     f"후보 {len(_cd75b)} · {_v75['type']} · 판정 {_MT74.STATS['판정']}")
_cd75c = _MT74.candidates("떠도는항목ZZ", "Property", "process", _g75, _dic75,
                          parent=None, cfg=_cfg75b)
show("② 부모 없는 값은 거르지 않는다 (모르는 것을 근거로 버리지 않는다)",
     len(_cd75c) > 0 and len({c.get("parent") for c in _cd75c}) >= 1,
     f"후보 {len(_cd75c)}개")
_non75 = _MT74.candidates("버 발생ZZ", "Failure", "quality", open_graph("quality"),
                          _dic75, parent="노칭", cfg=load_config("quality"))
show("② 스코프 없는 카테고리는 이전과 같다 (하드 필터는 스코프 카테고리의 것이다)",
     isinstance(_non75, list), f"후보 {len(_non75)}개")

print("\n── B75 ③ 비용은 실패해도 보인다 ──")
from cli import ingest as _IG75                                   # noqa: E402

_stage75 = {"이름": "판정", "값": 7, "총": 60}
_line75 = _IG75.spend_line(_stage75)
_u75 = _LL74.usage_total()
show("③ 실패 줄이 비용을 말하고 그 수가 `llm.usage_total()`과 같다",
     f"호출 {_u75['calls']:,}" in _line75
     and f"토큰 {_u75.get('total_tokens', 0):,}" in _line75
     and "판정 값 7/60" in _line75, _line75[:80])
_pb75 = _io.StringIO()
with _ctx.redirect_stdout(_pb75):
    _IG75.judge_progress(20)({"판정": 1})
    _IG75.judge_progress(20)({"판정": 2})
show("③ 진행 줄은 덮어쓰지 않는다 (스크롤·로그에 남는다)",
     "\r" not in _pb75.getvalue() and _pb75.getvalue().count("[판정]") == 2,
     repr(_pb75.getvalue()[:40]))
_ni75 = _io.StringIO()
with _ctx.redirect_stdout(_ni75):
    _IG75.judge_progress(20, every=1)({"판정": 5})
show("③ 비대화형에서는 묻지 않는다 (일괄이 첫 값에서 서지 않는다)",
     "[계속 c / 멈춤 q]" not in _ni75.getvalue())

# `q` — 그래프·사전·큐 쓰기 0
def _truth75():
    """되돌림의 대상 셋 — **그래프·사전·큐**다(체크포인트·인입 기록은 남는다)."""
    return (json.dumps([[sorted(open_graph(l).nodes), len(open_graph(l).edges)]
                        for l in ("process", "quality")], ensure_ascii=False),
            json.dumps(store.read(store.QUEUE, []), ensure_ascii=False,
                       sort_keys=True),
            json.dumps(_DIC74.open().entries(), ensure_ascii=False, sort_keys=True))


_before75 = _truth75()
from core.pipeline import Stopped as _ST75                        # noqa: E402


def _stop75(stats):
    if stats.get("판정", 0) >= 3:
        raise _ST75("사람이 멈췄다 — 판정 값 3/20 (그래프 쓰기 0)")


_MT74.PROGRESS = _stop75
try:
    _r75, _m75, _ = _run72(_env75("B75STOP", [f"멈춤항목{i:02d}" for i in range(8)]))
finally:
    _MT74.PROGRESS = None
_after75 = _truth75()
show("③ 판정 도중 멈추면 **그래프·큐 쓰기 0**이다 (부분 쓰기 없음)",
     _r75.status == "held" and _before75[:2] == _after75[:2],
     f"{_r75.status} · 그래프 {'같다' if _before75[0] == _after75[0] else '다르다'}"
     f" · 큐 {'같다' if _before75[1] == _after75[1] else '다르다'}")
show("③ 사전도 그대로다 (판정이 남긴 등재가 되돌려진다)",
     _before75[2] == _after75[2])

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G6 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
