# -*- coding: utf-8 -*-
"""P1 완료판정 — n7 파서 공용 코어 6종 + struct-map + 생성 하네스.

  S7  preflight 불일치      — CP02_drift: extract 미실행·문서 중단·adapter_mismatch
  S8  계약 위반 행           — CP03_bad: 문서 통째 미인입·parse_failure (C14)
  S9  기본 어댑터 (확장)     — PPT 임계 3경로: 슬라이드 / shape 분할 / 지도 폴백
  S14 역산 정합              — prefix CP01 12 · PFMEA01 13 (실물 파서 산출로)
  + 지도 경로 동치           — TOC01·02를 struct-map으로 → 상수 어댑터 산출과 동일
  + 지도 실패 경로           — 깨진 지도 → 평면 폴백 + 표시, 조용한 오파싱 0
  + 스냅샷 파일              — 생성·재빌드 재생성·skeleton_version 정합
  + 코어 6종 계약            — normalizer 멱등 · validator 문서 단위 · tagger 파생

사용: python tests/test_p1.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import init, store                                        # noqa: E402
from core.bootstrap import bootstrap                          # noqa: E402
from parser import normalizer, pipeline, preflight, struct_map, tagger, validator  # noqa: E402
from parser.adapters import basic_ppt                         # noqa: E402
from parser.reader import read                                # noqa: E402

allok = True
RAW = ROOT / "mock" / "raw"
SKIP = {"parsed_at", "source_path", "parser_version", "adapter_version",
        "process_no", "source_locator"}


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load_adapter(path, name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = load_adapter("mock/adapters/cp.py", "ad_cp")
PFMEA = load_adapter("mock/adapters/pfmea.py", "ad_pfmea")
TOC = load_adapter("mock/fixtures/adapters/toc_report.py", "ad_toc")
IPQC = load_adapter("mock/fixtures/adapters/ipqc.py", "ad_ipqc")


# ============================================================ 스냅샷
print("\n■ 골격 닫힌 목록 스냅샷 — 파서·에이전트 공유 자산 (D-11 확정)")
init.init(fresh_=True)              # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
for lay in ("process", "quality"):
    bootstrap(lay, echo=False)
snap_path = store.path(store.SKELETON_LIST)
show("골격 재빌드가 스냅샷 파일을 생성한다 (파생물 — P5)", snap_path.exists(),
     str(snap_path.relative_to(ROOT)))
snap = json.loads(snap_path.read_text(encoding="utf-8"))
proc = snap["process"]
show("스냅샷이 골격 전 노드를 담는다 (개념+인스턴스 — A11-6·D-45)",
     proc["count"] == 46, f"{proc['count']}노드")
show("skeleton_version 정합 (config ↔ 스냅샷)",
     proc["skeleton_version"] == json.loads(
         (ROOT / "layers/process/config.json").read_text(encoding="utf-8")
     )["skeleton_version"], proc["skeleton_version"])
show("canonical·alias·tier·polarity·parent를 함께 싣는다 (태거가 파생할 재료)",
     all({"canonical", "aliases", "tier", "polarity", "parent"} <= set(n)
         for n in proc["nodes"]))
nodes = tagger.closed_list("process")
show("파서가 그래프가 아니라 **파일**을 읽는다 (D-9 — 결합은 JSON뿐)",
     len(nodes) == 46 and tagger.SNAPSHOT == snap_path)
before = json.dumps(snap, ensure_ascii=False, sort_keys=True)
bootstrap("process", echo=False)
show("재빌드가 스냅샷을 재생성한다 (손으로 고치지 않는 파생물)",
     json.dumps(json.loads(snap_path.read_text(encoding="utf-8")),
                ensure_ascii=False, sort_keys=True) == before)

# ============================================================ 코어 6종 계약
print("\n■ 코어 6종 — 계약 대조 (파서_명세 v0.6 §3)")
show("reader는 기존 참조 구현 그대로다 (채택 확정 — 신작 없음)",
     (ROOT / "parser" / "reader.py").exists()
     and "def read(path)" in (ROOT / "parser/reader.py").read_text(encoding="utf-8"))
show("reader가 두 모드에서 같은 코드다 (운영 추출 = 등록 세션 관찰 재료 — §3 규약 4)",
     read(str(RAW / "CP01.xlsx"))["sheets"][0]["name"]
     == __import__("parser.reader", fromlist=["head"]).head(
         read(str(RAW / "CP01.xlsx")), 5)["sheets"][0]["name"])

ipqc_pieces = IPQC.extract(read(str(RAW / "IPQC01.xlsx")))
same, rep = normalizer.normalize(ipqc_pieces, multi_fields=["검사항목"], seps=[", "])
show("normalizer 멱등 — 이미 자기완결인 어댑터 산출은 무변경 (이중 전개 0)",
     same == ipqc_pieces and rep == {"ditto": 0, "multi": 0, "nested": 0}, str(rep))
d_recs, hits = normalizer.resolve_ditto(
    [{"a": "값1", "b": "x"}, {"a": "〃", "b": "y"}])
show("normalizer ① 상동 해소", d_recs[1]["a"] == "값1" and hits == 1)
m_recs, mh = normalizer.split_multi(
    [{"f": "가, 나", "source_locator": "L1"}], ["f"], [", "])
show("normalizer ③ 복수값 분리 + locator 유일성",
     [r["f"] for r in m_recs] == ["가", "나"]
     and [r["source_locator"] for r in m_recs] == ["L1#1", "L1#2"], str(mh))
f_recs, fh = normalizer.flatten([{"x": {"p": 1}, "context": {"model": "M1"}}])
show("normalizer ④ nested 평탄화 — context·meta는 펴지 않는다 (구조 필드 — C17)",
     f_recs[0] == {"x.p": 1, "context": {"model": "M1"}} and fh == 1)
merged = normalizer.expand_merged(read(str(RAW / "CP01.xlsx"))["sheets"][0])
show("normalizer ② 병합 전개 — reader는 범위만 주고 전개는 여기 몫",
     merged.get("A5") == merged.get("A4") != None)

ok, defects = validator.check({"doc_id": "X", "payload_kind": "table"})
show("validator — 봉투 결손은 문서 단위 실패 사유로 모인다 (C14)",
     not ok and len(defects) >= 3, f"{len(defects)}건")
ok2, d2 = validator.check({
    "doc_id": "X", "doc_type": "cp", "source_path": "p", "revision": "R1",
    "parsed_at": "t", "parser_version": "v", "adapter_version": "a",
    "payload_kind": "table",
    "records": [{"source_locator": "L1", "record_id": "직접부여"}]})
show("validator — 파서가 정본 id를 부여하면 실패다 (틀 A7-1)",
     not ok2 and any("정본 id" in x for x in d2), str(d2))

n = next(x for x in nodes if x["canonical"] == "탭용접::cathode")
show("tagger — process_group은 tier:main 조상 파생이다 (A11-7 · 지어내지 않는다)",
     tagger.group_of(n, nodes) == "조립")
img = tagger.complete_images([{"source_locator": "L", "image_ref": "img_001"}])
show("tagger — 이미지 요약은 코어가 완성한다 (어댑터 아님 — §5 규약 3)",
     img[0]["text"] == "MOCK 요약: img_001"
     and img[0]["meta"]["image_summary"] is True)

# ============================================================ S7 · S8
print("\n■ S7 preflight 불일치 / S8 계약 위반 행")
res = pipeline.parse(CP, "CP02", str(RAW / "CP02_drift.xlsx"))
show("S7 양식 표류 → 문서 중단 + adapter_mismatch (extract 미실행)",
     not res.ok and [f["kind"] for f in res.failures] == ["adapter_mismatch"]
     and res.envelope is None)
det = res.failures[0]["detail"]
show("S7 차이 내역과 adapter_version을 함께 제시한다",
     det["missing"] == ["관리항목"] and det["extra"] == ["관리 항목명"]
     and det["adapter_version"], f"누락 {det['missing']} · 잉여 {det['extra']}")
show("S7 정상 양식은 통과한다 (표류 감지가 과민하지 않다)",
     preflight.check(CP, read(str(RAW / "CP01.xlsx")))[0]
     and preflight.check(CP, read(str(RAW / "CP04_unlabeled.xlsx")))[0])

res = pipeline.parse(CP, "CP03", str(RAW / "CP03_bad.xlsx"))
show("S8 자기완결 위반 1행 → **문서 통째** 미인입 + parse_failure (C14)",
     not res.ok and [f["kind"] for f in res.failures] == ["parse_failure"]
     and res.envelope is None)
show("S8 사유에 해당 행과 결측 필드가 실린다",
     "row 15" in res.failures[0]["reason"]
     and "설비" in res.failures[0]["reason"], res.failures[0]["reason"][:70])

# ============================================================ S9 (확장)
print("\n■ S9 기본 어댑터 — PPT 임계 3경로 (B+C 단계형 · 카드 C13 v18)")
raw = read(str(RAW / "PPT_basic.pptx"))
show("확대분 2장이 말미에 붙었다 (D-18 — 기존 슬라이드 번호 불변)",
     len(raw["slides"]) == 11 and raw["slides"][8]["index"] == 9)
exp = basic_ppt.ADAPTER["expects"]
show("임계는 config 값이다 (코드에 숫자를 박지 않는다 — P7)",
     exp["max_chars"] == 600 and exp["max_shapes"] == 5)

pieces = basic_ppt.extract(raw, struct_map_fn=lambda k, l, loc: struct_map.apply(k, l, loc))
paths = {}
for p in pieces:
    paths.setdefault(p["meta"]["split_path"], []).append(p)
show("① 임계 이하 = 슬라이드 1장 → 청크 1개 (원래의 자명함)",
     len(paths.get("slide", [])) == 9,
     f"{len(paths.get('slide', []))}청크")
show("② 임계 초과 + 다프레임 → shape 단위 분할 (결정적)",
     len(paths.get("shape", [])) == 6
     and all(p["source_locator"].startswith("슬라이드 10#") for p in paths["shape"]),
     str([p["source_locator"] for p in paths.get("shape", [])][:3]))
show("③ 임계 초과 + 단일 거대 프레임 → struct-map 폴백 (지도 기반 분할)",
     len(paths.get("struct_map", [])) >= 5
     and all(p["source_locator"].startswith("슬라이드 11#L")
             for p in paths["struct_map"]),
     f"{len(paths.get('struct_map', []))}청크")
show("③ 지도 분할이 헤딩 경로를 section으로 싣는다",
     any(" > " in p["section"] for p in paths.get("struct_map", [])),
     str([p["section"] for p in paths.get("struct_map", [])][:2]))
noflat = basic_ppt.extract(raw)                       # 지도 훅 미주입
show("어댑터는 스스로 LLM을 부르지 않는다 — 지도 훅이 없으면 ④ 폴백 + 표시",
     any(p["meta"].get("hierarchy_unresolved") for p in noflat)
     and not any(p["meta"]["split_path"] == "struct_map" for p in noflat))

# ============================================================ S14
print("\n■ S14 역산 정합 — 실물 파서 산출 = parsed JSON prefix (D-18)")
for doc, adapter, n_prefix in (("CP01", CP, 12), ("PFMEA01", PFMEA, 13)):
    res = pipeline.parse(adapter, doc, str(RAW / f"{doc}.xlsx"))
    got = (res.envelope or {}).get("records", [])
    want = json.loads((ROOT / "mock/parsed" / f"{doc}.json").read_text(
        encoding="utf-8"))["records"]
    bad = []
    for i, (g, e) in enumerate(zip(got[:n_prefix], want[:n_prefix]), 1):
        gg = {k: v for k, v in g.items() if k not in SKIP and v not in (None, "")}
        ee = {k: v for k, v in e.items() if k not in SKIP and v not in (None, "")}
        if gg != ee:
            bad.append((i, {k: (gg.get(k), ee.get(k))
                            for k in set(gg) | set(ee) if gg.get(k) != ee.get(k)}))
    show(f"S14 {doc} — prefix {n_prefix}건 일치 (실행 시점 값·locator 표기 제외)",
         res.ok and len(got) >= n_prefix and not bad,
         f"파서 {len(got)}건 · 차이 {bad[:2]}")

res = pipeline.parse(PFMEA, "PFMEA01", str(RAW / "PFMEA01.xlsx"))
show("좌표가 닫힌 목록 밖이어도 문서를 죽이지 않는다 (판정은 인입 소관 — orphan_anchor)",
     res.ok and res.report["coords"]["outside_closed_list"] == ["레이저노칭"],
     str(res.report["coords"]))

# ============================================================ 지도 경로
print("\n■ 지도 경로 — 동치와 실패 (틀 v2.8 Q2 · D-58 · R18)")
for doc in ("TOC01", "TOC02"):
    raw = read(str(RAW / f"{doc}.xlsx"))
    sh = raw["sheets"][0]
    name = sh["name"]
    lines = [(r, str(sh["cells"][f"A{r}"]).strip())
             for r in range(2, sh["max_row"] + 1)
             if sh["cells"].get(f"A{r}") and str(sh["cells"][f"A{r}"]).strip()]
    mapped, smap, reasons = struct_map.apply(
        doc, lines,
        lambda a, b: f"{name}!A{a}" if a == b else f"{name}!A{a}:A{b}")
    ref = [p for p in TOC.extract(raw) if "text" in p]
    same = (len(mapped) == len(ref) and all(
        a["source_locator"] == b["source_locator"] and a["section"] == b["section"]
        and a["text"] == b["text"] for a, b in zip(mapped, ref)))
    show(f"지도 경로 동치 — {doc}: 상수 어댑터 산출과 청크·section 동일",
         same and not reasons, f"지도 {len(mapped)} · 어댑터 {len(ref)}")

lines = [(r, f"{r}행 본문") for r in range(2, 20)]
for r, txt in ((2, "1. 첫 장"), (4, "1.1 절"), (7, "1.2 절"), (10, "2. 둘째 장")):
    lines[r - 2] = (r, txt)
loc = (lambda a, b: f"L{a}" if a == b else f"L{a}-{b}")
ok_chunks, ok_map, ok_reasons = struct_map.apply("MAPMOCK_OK", lines, loc)
show("지도 mock 파일이 휴리스틱보다 우선한다 (증분0 §5-4 — 지위는 mock 힌트)",
     ok_map["source"].startswith("손작성") and not ok_reasons and ok_map["verdict"] == "mapped")
bad_chunks, bad_map, bad_reasons = struct_map.apply("MAPMOCK_BROKEN", lines, loc)
show("지도 실패 경로 — 레벨 비단조를 결정적으로 잡는다",
     bad_map["verdict"] == "flat" and any("비단조" in r for r in bad_reasons),
     str(bad_reasons[:1]))
show("지도 실패 → 평면 폴백 + 표시 (조용한 오파싱 0 · 문서는 산다)",
     len(bad_chunks) == 1 and bad_chunks[0]["meta"]["hierarchy_unresolved"] is True)
show("실패한 지도도 함께 돌려준다 (무엇을 보고 실패했나가 판정 재료다)",
     bad_map.get("rows") and bad_map.get("reasons"))
show("휴리스틱 폴백은 번호 패턴이다 — 구문 마커이지 층 어휘가 아니다 (B1)",
     struct_map.propose("없는문서", [(1, "1. 장"), (2, "본문")])["source"] == "heuristic")
empty = struct_map.apply("없는문서", [(1, "헤딩 없는 본문"), (2, "또 본문")], loc)
show("헤딩 0건도 결정적으로 잡는다 (평면 폴백)",
     empty[1]["verdict"] == "flat" and any("헤딩 0건" in r for r in empty[2]))

# ============================================================ 생성 하네스
print("\n■ 생성 하네스 — 구축 모드 3단 배선 (생성 → 검수 → 확정)")
from cli.parse import cmd_build                              # noqa: E402

rc = cmd_build(["mock/fixtures/adapters/ipqc.py", "ipqc_p1",
                str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx")])
outdir = ROOT / "review" / "ipqc_p1"
show("3단이 파일로 이어진다 — 입력 패키지 · 검수 뷰 데이터 · 승인 기록",
     all((outdir / f).exists() for f in
         ("input_package.json", "view.json", "approval.json")))
view = json.loads((outdir / "view.json").read_text(encoding="utf-8"))
show("검수 뷰 **데이터**까지가 P1이다 (HTML 렌더는 P2 — 경계)",
     "samples" in view and not (outdir / "view.html").exists())
show("기계 관문이 검수 앞에 선다 (preflight + 파싱 + self-check 전 표본)",
     rc == 0 and all(s["preflight"] and s["parsed"] for s in view["samples"]))
show("표본 2부면 1부 경고가 뜨지 않는다", not view["warnings"])
cmd_build(["mock/fixtures/adapters/ipqc.py", "ipqc_p1_solo", str(RAW / "IPQC01.xlsx")])
solo = json.loads((ROOT / "review/ipqc_p1_solo/view.json").read_text(encoding="utf-8"))
show("표본 1부면 '변형 미관찰 · 근거 1건일 수 있음' 경고 (D-22 확장 문구)",
     solo["warnings"] and "근거 1건" in solo["warnings"][0])
appr = json.loads((outdir / "approval.json").read_text(encoding="utf-8"))
show("확정은 승인 기록까지 — registry 등재는 P3의 몫이다 (경계 침범 0)",
     appr["machine_gate"] == "PASS" and appr["approved_by"] is None
     and "ipqc_p1" not in store.read(store.REGISTRY, {}))
shutil.rmtree(ROOT / "review" / "ipqc_p1", ignore_errors=True)
shutil.rmtree(ROOT / "review" / "ipqc_p1_solo", ignore_errors=True)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — P1 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
