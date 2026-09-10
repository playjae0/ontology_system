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
from parser import (normalizer, pipeline, preflight, reader, struct_map, tagger,  # noqa: E402
                    validator)
from parser.adapters import basic_ppt                         # noqa: E402
from parser.reader import read                                # noqa: E402

allok = True
RAW = ROOT / "tests" / "fixtures" / "raw"
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


CP = load_adapter("tests/fixtures/adapters/cp.py", "ad_cp")
PFMEA = load_adapter("tests/fixtures/adapters/pfmea.py", "ad_pfmea")
TOC = load_adapter("tests/fixtures/fixtures/adapters/toc_report.py", "ad_toc")
IPQC = load_adapter("tests/fixtures/fixtures/adapters/ipqc.py", "ad_ipqc")


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
# **청크 수를 못박지 않는다**([정정] 46) — 레벨 규칙이 바뀌면 개수도 바뀐다.
# 구판은 「구간에 못 들면 전 헤딩 분할」이라 9청크였고 신판은 최근접 레벨이라
# 3청크다. 잠글 것은 개수가 아니라 **통청크가 아니라는 것**과 좌표의 모양이다.
show("③ 임계 초과 + 단일 거대 프레임 → struct-map 폴백 (지도 기반 분할)",
     len(paths.get("struct_map", [])) >= 2
     and all(p["source_locator"].startswith("슬라이드 11#L")
             for p in paths["struct_map"]),
     f"{len(paths.get('struct_map', []))}청크")
show("③ 지도 분할이 **헤딩을** section으로 싣는다 (슬라이드 제목이 아니다)",
     paths.get("struct_map")
     and all(p["section"] and p["section"] != p["meta"].get("section_path")
             for p in paths["struct_map"]),
     str([p["section"] for p in paths.get("struct_map", [])][:2]))
# **구간 밖으로 떨어진 사실이 조각에 실린다**([정정] 46) — 이 표본이 그 경우다
# (레벨 1의 평균 3.0행 · 목표 5~40행). 인입이 이것을 보고 큐를 단다.
show("③ 지도 경로도 구간 밖을 조각에 싣는다 (산문 두 경로가 같은 표시를 쓴다)",
     all(p["meta"].get("split_level_out_of_range")
         for p in paths.get("struct_map", [])))
noflat = basic_ppt.extract(raw)                       # 지도 훅 미주입
show("어댑터는 스스로 LLM을 부르지 않는다 — 지도 훅이 없으면 ④ 폴백 + 표시",
     any(p["meta"].get("hierarchy_unresolved") for p in noflat)
     and not any(p["meta"]["split_path"] == "struct_map" for p in noflat))

# ============================================================ S14
print("\n■ S14 역산 정합 — 실물 파서 산출 = parsed JSON prefix (D-18)")
for doc, adapter, n_prefix in (("CP01", CP, 12), ("PFMEA01", PFMEA, 13)):
    res = pipeline.parse(adapter, doc, str(RAW / f"{doc}.xlsx"))
    got = (res.envelope or {}).get("records", [])
    want = json.loads((ROOT / "tests/fixtures/parsed" / f"{doc}.json").read_text(
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
    # [B43 ③] 지도 경로는 **레벨을 골라** 자르므로 상수 어댑터(전 헤딩 분할)보다
    # 굵다 — 「청크 수 동일」은 더는 참이 아니고 참이어서도 안 된다. 지켜야 할
    # 불변은 **내용이 하나도 새지 않는가**다: 어댑터의 각 청크 본문이 지도 청크
    # 어딘가에 통째로 들어 있고, section 경로도 그 안에 있다.
    _mtext = "\n".join(c["text"] for c in mapped)
    _msec = {c["section"] for c in mapped}
    lost = [b["text"][:40] for b in ref if b["text"] not in _mtext]
    show(f"지도 경로 — {doc}: 어댑터 산출이 **하나도 새지 않는다** (굵기만 다르다)",
         not lost and not reasons,
         f"지도 {len(mapped)} · 어댑터 {len(ref)} · 유실 {lost}")
    show(f"지도 경로 — {doc}: 고른 레벨과 근거가 지도에 남는다 (같은 지도 → 같은 분할)",
         "분할_레벨" in smap and "레벨_분포" in smap,
         f"레벨 {smap.get('분할_레벨')} — {smap.get('분할_레벨_사유', '')[:50]}")

lines = [(r, f"{r}행 본문") for r in range(2, 20)]
for r, txt in ((2, "1. 첫 장"), (4, "1.1 절"), (7, "1.2 절"), (10, "2. 둘째 장")):
    lines[r - 2] = (r, txt)
loc = (lambda a, b: f"L{a}" if a == b else f"L{a}-{b}")
# **고정 지도는 시험이 주입한다**(B48 ⑤ · 문서 7 §7.1 대체 표 ⑦행) — 운영 코드는
# fixture 파일을 찾지 않는다: 미리 놓은 정답을 돌려주는 갈래는 배선이 없어도 초록이라
# 결함을 가린다(⑦ 미배선이 그렇게 숨었다). 파일은 그대로 있고 **자리만 바뀐다**(A11).
_MAPS = ROOT / "tests" / "fixtures" / "struct_maps"


def _fixed_map(name):
    """`ask=`로 주입할 고정 지도 — 실호출 경로가 타는 그 통로를 그대로 쓴다."""
    def ask(doc_id, lines):
        return json.loads((_MAPS / f"{name}.json").read_text(encoding="utf-8"))
    return ask


for _n in ("MAPMOCK_OK", "MAPMOCK_BROKEN"):
    struct_map.invalidate(f"{_n}")      # 주입분은 보존된다 — 앞 실행분을 물지 않게
ok_chunks, ok_map, ok_reasons = struct_map.apply("MAPMOCK_OK", lines, loc,
                                                 ask=_fixed_map("MAPMOCK_OK"))
show("주입된 지도가 휴리스틱보다 우선한다 (운영 코드는 fixture를 찾지 않는다 — B48)",
     ok_map["source"] == "live" and not ok_reasons and ok_map["verdict"] == "mapped",
     f"source={ok_map['source']}")
bad_chunks, bad_map, bad_reasons = struct_map.apply("MAPMOCK_BROKEN", lines, loc,
                                                    ask=_fixed_map("MAPMOCK_BROKEN"))
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

# ============================================================ 파서 무판독 (B48 ①)
print("\n■ 파서 무판독 — 모드는 진입점이 정하고 파서는 함수 유무만 본다 (문서 7 §7.6-B-1)")
_pyfiles = sorted((ROOT / "parser").rglob("*.py"))
_umock = [f"{p.relative_to(ROOT)}:{i}"
          for p in _pyfiles
          for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
          if "USE_MOCK" in ln]
show(f"파서 {len(_pyfiles)}파일 전수에 USE_MOCK 문자열 0건 (주석·docstring 포함)",
     not _umock, str(_umock[:3]))
_envread = [f"{p.relative_to(ROOT)}:{i}"
            for p in _pyfiles
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "os.environ" in ln and not ln.lstrip().startswith("#")]
show("mock 여부를 환경변수로 정하는 줄 0건 — 판독이 두 곳이면 갈린다(B42 실측)",
     not _envread, str(_envread[:3]))
_smsrc = (ROOT / "parser" / "struct_map.py").read_text(encoding="utf-8")
show("⑤ 운영 코드가 fixture 지도를 찾지 않는다 (MAPS_DIR 삭제 · KEEP_DIR 보존은 별개)",
     "MAPS_DIR" not in _smsrc and "struct_maps" in _smsrc and "KEEP_DIR" in _smsrc)
show("④·⑦·⑨가 parse()의 인자로 서 있다 — 함수가 오는 통로가 있다",
     {"summarize", "map_structure", "pick_coord"}
     <= set(pipeline.parse.__code__.co_varnames))
show("⑦의 통로가 apply()까지 이어진다 (파라미터만 있고 값이 올 길이 없으면 배선이 아니다)",
     "ask" in struct_map.apply.__code__.co_varnames
     and "ask=ask" in _smsrc)

# ============================================================ ⑦ 폴백 ([정정] 39)
print("\n■ ⑦ 예산 초과·판정 불가는 문서를 죽이지 않는다 (문서 6 §6.2·§6.3 · D-113 조정)")
from core import llm as _LLM                                        # noqa: E402
_PPTDOC = str(RAW / "PPT_basic.pptx")


def _map_run(doc_id, reply, limit):
    """실호출 갈래(`llm.map_structure`)를 **그대로 태운다** — 가짜는 게이트웨이 응답과
    한도뿐이다. 파서에 주입되는 함수는 운영과 같은 것이라 배선까지 함께 잰다."""
    struct_map.invalidate(doc_id)
    _oc, _ol = _LLM.chat, _LLM.context_limit
    _LLM.chat = lambda *a, **k: reply
    _LLM.context_limit = lambda: limit
    try:
        return pipeline.parse(basic_ppt, doc_id, _PPTDOC,
                              map_structure=_LLM.map_structure)
    finally:
        _LLM.chat, _LLM.context_limit = _oc, _ol


def _queue_reasons(res):
    return [x for c in (res.envelope or {}).get("chunks", [])
            for x in ((c.get("meta") or {}).get("unresolved_reasons") or [])]


# ⓐ 예산 초과 — 보내지 않되 문서는 산다
_a = _map_run("PPTBUDGET", {"headings": [], "note": None}, 1)
show("ⓐ 예산 초과여도 파싱은 완주한다 (문서 단위 실패가 아니다 — §6.2 폴백)",
     _a.ok and [f["kind"] for f in _a.failures] == ["hierarchy_unresolved"],
     f"ok={_a.ok} · {[f['kind'] for f in _a.failures]}")
show("ⓐ 큐 사유에 「크기 예산 초과」가 실린다 (사람이 왜를 들고 검수 화면에 간다)",
     any("크기 예산 초과" in r for r in _queue_reasons(_a)),
     str(_queue_reasons(_a))[:100])
show("ⓐ 사유 지도는 보존하지 않는다 — 보존하면 재인입이 영영 평면이다",
     not struct_map.keep_path("PPTBUDGET").exists())
show("ⓐ 사유 문면이 **다음 행동**을 낸다 — 귀결 한 줄 + 줄이는 법 두 가지",
     any("평면으로 인입된다" in r and "LLM_CONTEXT_TOKENS가 게이트웨이" in r
         and "시트·슬라이드 단위로 나눠" in r for r in _queue_reasons(_a)),
     str(_queue_reasons(_a))[:80])

# ⓑ 한도를 올리면 다시 시도된다 (ⓐ가 보존을 안 남겼다는 증명)
_b = _map_run("PPTBUDGET", {"headings": [{"row": 1, "level": 1, "title": "제목"}],
                            "note": None}, 10 ** 6)
_kept = json.loads(struct_map.keep_path("PPTBUDGET").read_text(encoding="utf-8")) \
    if struct_map.keep_path("PPTBUDGET").exists() else {}
_maps = list((_kept.get("maps") or {}).values())
show("ⓑ 한도를 올린 재인입에서 실호출 지도가 서고 **보존된다**",
     bool(_maps) and all(m[1].get("source") == "live" and not m[1].get("unavailable")
                         for m in _maps),
     f"보존 프레임 {list((_kept.get('maps') or {}).keys())}")
struct_map.invalidate("PPTBUDGET")

# ⓒ 모델의 「판정 불가」가 큐 사유에 보인다
_c = _map_run("PPTNOTE", {"headings": [], "note": "표 하나로만 된 문서"}, 10 ** 6)
show("ⓒ 헤딩 0건 + 모델 note가 큐 사유 문면에 실린다 (§6.2 「판정 불가로 올린다」)",
     any("모델: 표 하나로만 된 문서" in r for r in _queue_reasons(_c)),
     str(_queue_reasons(_c))[:100])
struct_map.invalidate("PPTNOTE")

# ============================================================ 생성 하네스
print("\n■ 생성 하네스 — 구축 모드 3단 배선 (생성 → 검수 → 확정)")
from cli.parse import cmd_build                              # noqa: E402

rc = cmd_build(["tests/fixtures/fixtures/adapters/ipqc.py", "ipqc_p1",
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
cmd_build(["tests/fixtures/fixtures/adapters/ipqc.py", "ipqc_p1_solo", str(RAW / "IPQC01.xlsx")])
solo = json.loads((ROOT / "review/ipqc_p1_solo/view.json").read_text(encoding="utf-8"))
show("표본 1부면 '변형 미관찰 · 근거 1건일 수 있음' 경고 (D-22 확장 문구)",
     solo["warnings"] and "근거 1건" in solo["warnings"][0])
appr = json.loads((outdir / "approval.json").read_text(encoding="utf-8"))
show("확정은 승인 기록까지 — registry 등재는 P3의 몫이다 (경계 침범 0)",
     appr["machine_gate"] == "PASS" and appr["approved_by"] is None
     and "ipqc_p1" not in store.read(store.REGISTRY, {}))
shutil.rmtree(ROOT / "review" / "ipqc_p1", ignore_errors=True)
shutil.rmtree(ROOT / "review" / "ipqc_p1_solo", ignore_errors=True)

# ============================================================ 조각 공통 층 (§2.2 계약 ①)
print("\n■ 조각 공통 층 — 모든 record/chunk가 달고 들어온다 (문서 2 §2.2)")
import importlib.util as _iu                                    # noqa: E402
_s = _iu.spec_from_file_location("_bp", ROOT / "parser/adapters/basic_ppt.py")
_bp = _iu.module_from_spec(_s); _s.loader.exec_module(_bp)
_r = pipeline.parse(_bp, "PPTXCOMMON", str(ROOT / "tests/fixtures/raw/PPT_basic.pptx"))
_COMMON = {"source_locator", "doc_type", "process_group", "process_ref",
           "electrode_type"}
show("기본 어댑터 산출도 조각 공통 5키를 전부 갖는다 (값 null 허용·키 부재 금지)",
     _r.ok and all(_COMMON <= set(c) for c in _r.envelope["chunks"]),
     str(sorted(_COMMON - set(_r.envelope["chunks"][0]))) if _r.ok else str(_r.failures))
show("validator가 조각 공통 키 부재를 잡는다 (§6.2-5 「좌표 존재」)",
     not validator.check({"doc_id": "X", "doc_type": "t", "payload_kind": "prose",
                          "source_path": "x", "revision": "R1",
                          "parsed_at": "t", "parser_version": "p",
                          "adapter_version": "a",
                          "chunks": [{"source_locator": "X-1", "text": "가"}]})[0])

# ⑨좌표 태깅의 mock 갈래는 **모델을 부르지 않는다** (조항 B12 · §7.1 대체 표)
_calls = []
from core import llm as _LLM                                    # noqa: E402
for _n in ("chat", "require", "_post"):
    _o = getattr(_LLM, _n)
    setattr(_LLM, _n, (lambda *a, _x=_n, _f=_o, **k: (_calls.append(_x), _f(*a, **k))[1]))
_nodes = tagger.closed_list("process")
_tagged = tagger.tag([{"source_locator": "T-1", "process_ref": "노칭"},
                      {"source_locator": "T-2", "process_ref": "없는공정zzz"}],
                     layer="process", nodes=_nodes, pick=_LLM.coord_picker())
show("⑨좌표 태깅 mock 갈래가 모델을 부르지 않는다 (조항 B12)", not _calls, str(_calls))
show("⑨목록 밖 좌표는 값을 고치지 않고 그대로 둔다 (판정은 인입 소관)",
     _tagged[1]["process_ref"] == "없는공정zzz"
     and _tagged[0]["process_group"] == "조립")

# ============================================================ CSV reader (2B 신설)
# **CSV는 xlsx와 같은 구조를 낸다** — 어댑터가 포맷을 몰라도 되게(요청 §2-1).
# `format`만 "csv"로 갈라 거짓말을 하지 않는다.
print("\n■ CSV reader — xlsx와 같은 구조 · 인코딩·구분자 판정")
_RAW = ROOT / "tests" / "fixtures" / "raw"
_c1 = reader.read(str(_RAW / "CSV01.csv"))
_s1 = _c1["sheets"][0]
show("format은 'csv'다 (xlsx로 위장하지 않는다)", _c1["format"] == "csv", _c1["format"])
show("xlsx와 같은 시트 구조 (cells·merged·indent·bold·images 키 존재)",
     all(k in _s1 for k in ("name", "max_row", "max_col", "cells",
                            "merged", "indent", "bold", "images")))
show("CSV에 없는 개념은 빈 값이되 키는 둔다",
     _s1["merged"] == [] and _s1["indent"] == {} and _s1["bold"] == []
     and _s1["images"] == [])
show("셀은 열문자 표기다 (A1 · C2)",
     _s1["cells"].get("A1") == "대공정" and _s1["cells"].get("C2") == "노칭 정밀도")
show("빈 셀은 cells에 넣지 않는다 (xlsx와 같게)", "D4" not in _s1["cells"])
show("max_col은 **최장 행** 기준이다 (짧은 행이 있어도 4)", _s1["max_col"] == 4,
     f"max_row={_s1['max_row']} max_col={_s1['max_col']}")

_c2 = reader.read(str(_RAW / "CSV02_cp949.csv"))
show("cp949 CSV를 읽는다 (BOM utf-8과 같은 결과)",
     _c2["encoding"] == "cp949"
     and _c2["sheets"][0]["cells"] == _s1["cells"], _c2["encoding"])
show("utf-8-sig(BOM) CSV의 첫 셀에 BOM이 남지 않는다",
     _c1["encoding"] == "utf-8-sig" and _s1["cells"]["A1"] == "대공정")

# **탭 파일이 한 열로 뭉개지지 않는다** — csv.Sniffer가 작은 표에서 실제로
# 실패했다(실측: 4행 탭 파일). 확장자·빈도 판정이 그 자리를 받는다.
_c3 = reader.read(str(_RAW / "CSV03_tab.tsv"))
show("탭 구분(.tsv)이 한 열로 뭉개지지 않는다",
     _c3["delimiter"] == "\t" and _c3["sheets"][0]["max_col"] == 4,
     f"delim={_c3['delimiter']!r} max_col={_c3['sheets'][0]['max_col']}")
_c4 = reader.read(str(_RAW / "CSV04_tab_in_csv.csv"))
show("확장자가 .csv인 탭 파일도 갈라 읽는다 (Sniffer/빈도)",
     _c4["delimiter"] == "\t" and _c4["sheets"][0]["max_col"] == 3)

show("head()가 csv에서 죽지 않는다 (분기는 이름이 아니라 구조)",
     "sheets" in reader.head(_c1, 2) and len(reader.head(_c1, 2)["sheets"]) == 1)
try:
    reader.read(str(_RAW / "CP01.xlsx") + ".zzz")
    _unsup = False
except ValueError as e:
    _unsup = "csv" in str(e) and "tsv" in str(e)
show("지원 포맷 목록이 실패 문장에 나온다 (.csv·.tsv 포함)", _unsup)


# ── B53 a. 결정적 판독 — 표·차트·그림·그룹·시각순서·숨김 ────────────────────
print("\n[B53 a] PPT 판독 — 텍스트 프레임과 노트만이 아니다")

import shutil as _sh                                              # noqa: E402
from core import llm                                              # noqa: E402
from parser import render                                         # noqa: E402
from parser.adapters import basic_pdf                             # noqa: E402
from cli import register as _reg, scan as _scan_mod               # noqa: E402
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_pdf, make_ppt                                         # noqa: E402

_PPTX = _RAW / "PPT_shapes.pptx"
if not _PPTX.exists():
    make_ppt.build(_PPTX)
_praw = reader.read(str(_PPTX))
_by_id = {r["id"]: r for s in _praw["slides"] for r in s["shapes"]}
_kinds = {r["kind"] for r in _by_id.values()}

show("shape 레코드로 낸다 — 문자열 배열이 아니다",
     all(isinstance(r, dict) and "id" in r and "kind" in r for r in _by_id.values()))
show("표를 읽는다 — 행 단위 ` | ` 이음 · 행·열 수",
     _by_id["S4-TB1"]["kind"] == "table" and _by_id["S4-TB1"]["rows"] == 5
     and _by_id["S4-TB1"]["cols"] == 2
     and "항목 | 규격" in _by_id["S4-TB1"]["text"])
# a-ⓑ **값이 원문 그대로다** — 반올림하면 정확도를 버린다(그림으로 찍지 않는 이유).
_ch = _by_id["S5-CH1"]["text"]
show("차트 계열 값이 원문 그대로 실린다 (반올림 0)",
     all(v in _ch for v in ("0.8", "1.1", "0.95", "1.2", "0.7", "1.05"))
     and "월별 불량률" in _ch and "1월" in _ch, _ch.split("\n")[1][:40])
show("차트 종류가 실린다", _by_id["S5-CH1"].get("chart_type") == "LINE")
show("그림은 바이트를 raw에만 싣는다 — 계약 JSON에는 image_ref만",
     _praw["_images"].get("S6-P1") is not None
     and _by_id["S6-P1"]["image_ref"] == "S6-P1"
     and "blob" not in _by_id["S6-P1"] and _by_id["S6-P1"]["bytes_len"] > 0)
show("그룹을 재귀한다 — 자식 id가 그룹 경로를 갖는다",
     "S7-G1-B1" in _by_id and "S7-G1-B2" in _by_id)
# a-ⓒ **시각 순서** — 픽스처는 아래 상자를 XML 앞에 두었다.
_s8 = [r for r in _praw["slides"][7]["shapes"] if r["kind"] == "text"]
show("shape 순서는 XML이 아니라 시각 순서(top→left)다",
     _s8[0]["text"].startswith("위 상자") and _s8[1]["text"].startswith("아래 상자"),
     " → ".join(x["text"][:6] for x in _s8))
show("숨김 슬라이드를 데이터로 표시한다 (리더는 빼지 않는다)",
     _praw["slides"][9]["hidden"] is True
     and sum(1 for s in _praw["slides"] if s.get("hidden")) == 1)

_pc = basic_ppt.extract(_praw)
_locs = {c["source_locator"]: c for c in _pc}
# a-ⓓ 숨김은 **청크에 없다**
show("숨김 슬라이드는 청크에 없다",
     not [c for c in _pc if (c["meta"].get("slide")) == 10]
     and not [c for c in _pc if "어느 청크에도 없어야" in (c.get("text") or "")])
show("표·차트는 **각각 별도 청크**다 — 근거 좌표가 shape까지 내려간다",
     _locs["S4-TB1"]["meta"]["shape_kind"] == "table"
     and _locs["S5-CH1"]["meta"]["shape_kind"] == "chart"
     and _locs["S6-P1"]["meta"]["shape_kind"] == "picture")
show("section은 슬라이드 제목이다 (없으면 「슬라이드 N」)",
     _locs["슬라이드 3"]["section"] == "노칭 설비 구성")
# a-ⓔ 구획 헤더 뒤 슬라이드에 3단 경로가 붙는다
show("section_path 3단 — 덱 › 구획 › 슬라이드 제목",
     _locs["슬라이드 3"]["meta"]["section_path"]
     == "조립 공정 판독 시험 › 노칭 구획 › 노칭 설비 구성",
     _locs["슬라이드 3"]["meta"]["section_path"])
show("구획이 없으면 경로가 두 단으로 **줄어든다** (빈 칸을 만들지 않는다)",
     _locs["슬라이드 1"]["meta"]["section_path"] == "조립 공정 판독 시험")
show("본문 청크가 표·차트보다 앞에 온다 (읽는 순서)",
     [c["source_locator"] for c in _pc].index("슬라이드 4")
     < [c["source_locator"] for c in _pc].index("S4-TB1"))

# a-ⓕ **기존 산출과 바이트 동일** — 텍스트만 있는 슬라이드는 한 글자도 안 바뀐다.
_b = basic_ppt.extract(reader.read(str(_RAW / "PPT_basic.pptx")))
_want = {("슬라이드 1", "조립공정 설비 현황\n2026년 상반기 · 조립 1라인 · 조립기술팀"),
         ("슬라이드 10#1", None)}
_got = {(c["source_locator"], c.get("text")) for c in _b}
show("기존 PPT 픽스처 — 조각 수·locator가 그대로다 (16조각)",
     len(_b) == 16 and "슬라이드 10#6" in {c["source_locator"] for c in _b})
show("기존 텍스트 청크가 **바이트 동일**하다 (회귀 유지)",
     ("슬라이드 1", "조립공정 설비 현황\n2026년 상반기 · 조립 1라인 · 조립기술팀") in _got)
show("[의도된 변화] 제목 있는 슬라이드는 section이 제목이 된다 — chunk_id가 옮겨간다",
     {c["source_locator"]: c["section"] for c in _b}["슬라이드 2"] == "노칭 공정")

# 계약 A — `shape_kind`는 **닫힌 8종**이고 validator가 검사한다
show("shape_kind 닫힌 8종 (문서 2 계약 A)",
     validator.SHAPE_KINDS == ("text", "title", "table", "chart", "picture",
                               "smartart", "notes", "page"))


# ── B53 b. ④ 이미지 요약 = 바이트 + 맥락 ──────────────────────────────────
print("\n[B53 b] ④ 이미지 요약 — 참조 문자열이 아니라 바이트")

_seen = {}


def _spy(ref, *, image=None, mime=None, context="", page=None):
    _seen.update(ref=ref, image=image, mime=mime, context=context, page=page)
    return "요약(시험)"


_res = pipeline.parse(basic_ppt, "B53PPT", str(_PPTX), summarize=_spy)
_pic = [c for c in _res.envelope["chunks"]
        if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
show("④가 **바이트**를 받는다 (구판은 참조 문자열이었다 — 개정대장 §AJ)",
     isinstance(_seen.get("image"), bytes) and len(_seen["image"]) > 0
     and _seen["mime"] == "image/png", f"{len(_seen.get('image') or b'')}바이트")
show("④가 **맥락**을 받는다 — 같은 슬라이드의 텍스트",
     _seen.get("context") == "노칭 프레스 외관")
show("④가 쪽 전체 그림을 함께 받는다 (있을 때)",
     isinstance(_seen.get("page"), bytes) and _seen["page"][:4] == b"\x89PNG")
# b-ⓐ **mock에서도** 바이트 도달을 잰다 — 실호출 없이 재는 유일한 자리다.
_mres = pipeline.parse(basic_ppt, "B53PPTM", str(_PPTX))
_mpic = [c for c in _mres.envelope["chunks"]
         if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
show("mock 갈래도 image_bytes_len을 남긴다 (바이트가 tagger까지 왔다)",
     _mpic["meta"]["image_summary_source"] == "mock"
     and _mpic["meta"]["image_bytes_len"] > 0, str(_mpic["meta"]["image_bytes_len"]))
show("쪽 렌더 여부가 데이터에 남는다 — page | none",
     _pic["meta"]["slide_render"] in validator.SLIDE_RENDER
     and _mpic["meta"]["slide_render"] in validator.SLIDE_RENDER)

# b-ⓑ chat() 멀티모달 페이로드 — 전송 직전 dict를 잡는다
_sent = {}
_real_post, _real_req = llm._post, llm.require
try:
    llm._post = lambda u, p, k, t: _sent.update(payload=p) or {
        "choices": [{"message": {"content": "요약"}}]}
    llm.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                              "timeout": 5, "retry": 0}
    llm.summarize_image("R1", image=b"\x89PNG\x00", mime="image/png",
                        context="맥락", page=b"\x89PNGpage")
    _parts = _sent["payload"]["messages"][-1]["content"]
    _imgs = [p for p in _parts if p.get("type") == "image_url"]
    show("chat() 멀티모달 — content가 리스트이고 image_url이 base64 data URI다",
         isinstance(_parts, list) and len(_imgs) == 2
         and _imgs[0]["image_url"]["url"].startswith("data:image/png;base64,"),
         _imgs[0]["image_url"]["url"][:40] if _imgs else "")
    show("맥락 텍스트가 같은 메시지에 실린다",
         any(p.get("type") == "text" and "맥락" in p.get("text", "") for p in _parts))

    # b-ⓕ 게이트웨이가 이미지를 400으로 거절하면 **NotConfigured**로 멈춘다
    def _p400(u, p, k, t):
        raise llm.GatewayError(400, "unsupported content type: image_url", u)
    llm._post = _p400
    try:
        llm.summarize_image("R1", image=b"\x89PNG", mime="image/png")
        _nc = "통과했다"
    except llm.NotConfigured as e:
        _nc = str(e)
    except Exception as e:                                        # noqa: BLE001
        _nc = f"{type(e).__name__}"
    show("게이트웨이 400(이미지 거부) → NotConfigured — 요약을 지어내지 않는다",
         "게이트웨이가 이미지 입력을 받지 않는다" in _nc, _nc[:52])
    try:                       # 이미지 없는 400은 설정 결함이 아니다 — 그대로 올린다
        llm.summarize_image("R1", context="c")
        _tc = "통과"
    except llm.NotConfigured:
        _tc = "NotConfigured(과잉)"
    except llm.GatewayError:
        _tc = "GatewayError"
    show("이미지 없는 400은 NotConfigured로 바꾸지 않는다 (원인을 옮기지 않는다)",
         _tc == "GatewayError", _tc)
finally:
    llm._post, llm.require = _real_post, _real_req

# b-ⓓ soffice가 없어도 **문서는 완주한다**
_realwhich = _sh.which
try:
    _sh.which = lambda n, *a, **k: None if "office" in n else _realwhich(n, *a, **k)
    _nres = pipeline.parse(basic_ppt, "B53NOSO", str(_PPTX), summarize=_spy)
    _npic = [c for c in _nres.envelope["chunks"]
             if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
    show("soffice 없으면 slide_render=none이고 **문서는 완주한다**",
         _nres.ok and _npic["meta"]["slide_render"] == "none"
         and len(_nres.envelope["chunks"]) == 12)
    show("렌더 부재는 진단으로 드러난다 (조용히 다르게 돌지 않는다)",
         render.available()[0] is False and "soffice" in render.available()[1])
finally:
    _sh.which = _realwhich

# b-ⓒ **표시** — 실호출로만 검증되는 항목(§7.5). mock에서 재는 것은 배관까지다.
show("[표시 · §7.5] ④ 실호출 요약 **품질**은 mock으로 판정하지 않는다 — "
     "사내 첫 실행에서 사람이 본다. 여기서 잰 것은 바이트·맥락·쪽이 ④에 닿았는가다",
     _mpic["meta"]["image_summary_source"] == "mock"
     and _pic["meta"]["image_summary_source"] == "live")
# **같은 봉투의 한 글자만 바꿔 대조한다** — 다른 이유로 붉어지면 이 검사가
# 무엇을 쟀는지 알 수 없다.
_env_ok = _mres.envelope                     # 방금 통과한 진짜 봉투
_ok_g, _ = validator.check(_env_ok)
import copy as _copy                                              # noqa: E402
_env_bad = _copy.deepcopy(_env_ok)
_env_bad["chunks"][0]["meta"]["shape_kind"] = "그림"
_ok_b, _d_b = validator.check(_env_bad)
show("닫힌 목록 밖 shape_kind를 잡는다 (검사하는 자리가 있어야 닫힌 것이다)",
     _ok_g and not _ok_b and len(_d_b) == 1 and "shape_kind" in _d_b[0],
     _d_b[0][:64] if _d_b else "")

show("지시문 판이 올랐다 — image_summary i-2.0 · extract e-1.1",
     "version: i-2.0" in (ROOT / "prompts" / "image_summary.md").read_text(encoding="utf-8")
     and "version: e-1.1" in (ROOT / "prompts" / "extract.md").read_text(encoding="utf-8"))

# ── B53 c. 기본 PDF 어댑터 ────────────────────────────────────────────────
print("\n[B53 c] 기본 PDF 어댑터 — 쪽이 청크다")

_PDF = _RAW / "PDF_basic.pdf"
if not _PDF.exists():
    make_pdf.build(_PDF)
_draw = reader.read(str(_PDF))
show(".pdf가 reader의 지원 목록에 있다 (목록의 정본은 reader다)",
     ".pdf" in reader.SUPPORTED and _draw["format"] == "pdf")
show("PDF 목차를 읽는다", [t["title"] for t in _draw["toc"]] == ["1. Notching", "2. Stacking"])
_dc = basic_pdf.extract(_draw)
_pages = [c for c in _dc if c["meta"]["shape_kind"] == "page"]
_phs = [c for c in _dc if c["meta"]["shape_kind"] == "picture"]
show("페이지 청크 3 + 그림 placeholder 1", len(_pages) == 3 and len(_phs) == 1,
     f"{len(_pages)} + {len(_phs)}")
show("source_locator가 쪽이다 — P1 · P2 · P3",
     [c["source_locator"] for c in _pages] == ["P1", "P2", "P3"])
# c-ⓑ **section이 toc에서 온다**
show("section이 목차에서 온다 (없으면 「페이지 N」)",
     _pages[0]["section"] == "1. Notching" and _pages[1]["section"] == "2. Stacking")
show("목차가 없으면 「페이지 N」으로 떨어진다 (조용히 비우지 않는다)",
     basic_pdf.extract({"pages": [{"index": 7, "text": "t", "images": []}],
                        "toc": []})[0]["section"] == "페이지 7")
# 스캔본 — 텍스트 0자 쪽은 그림 placeholder 하나로만 (빈 청크 0)
_scan = basic_pdf.extract({"toc": [], "pages": [
    {"index": 1, "text": "", "images": [
        {"id": "P1-P1", "kind": "picture", "image_ref": "P1-P1",
         "mime": "image/png", "bytes_len": 9}]}]})
show("스캔본(텍스트 0자)은 그림 placeholder 하나로 낸다 — 빈 청크를 만들지 않는다",
     len(_scan) == 1 and _scan[0]["meta"]["page_text_empty"] is True
     and _scan[0]["meta"]["shape_kind"] == "picture")
show("PDF는 지문 대상이 아니다 — 표 어댑터와 대조하지 않는다",
     _scan_mod.scan(str(_PDF)).get("not_fingerprintable") == "pdf")
show("--use-basic이 .pdf 전부에 뜬다 (섞이면 뜨지 않는다)",
     (_reg.basic_adapter_proposal([str(_PDF)]) or {}).get("adapter")
     == "parser/adapters/basic_pdf.py"
     and _reg.basic_adapter_proposal([str(_PDF), str(_PPTX)]) is None)
show("위임 래퍼가 제안이 정한 어댑터를 문다 (PDF가 PPT 어댑터를 물지 않는다)",
     "basic_pdf" in (ROOT / "cli" / "register.py").read_text(encoding="utf-8")
     and 'mod = Path(proposal["adapter"]).stem'
     in (ROOT / "cli" / "register.py").read_text(encoding="utf-8"))

# ── B58 ③ 고정 prose xlsx 어댑터 + 레벨 규칙 ([정정] 46) ──────────────────
print("\n■ B58 ③ — 스프레드시트 산문: 규칙이 레벨을 고른다")

from parser.adapters import basic_prose_xlsx as _BPX          # noqa: E402
from core import pipeline as _CP                              # noqa: E402
from core import registry as _RG                              # noqa: E402
from cli.parse import run_parse as _run_parse                 # noqa: E402

# **규칙 자체를 잠근다** — 화면 문구가 아니라 무엇을 고르는가다.
_C = struct_map.CHUNK_CENTER
show("③ 목표 구간의 중앙이 상수에서 파생된다 (숫자를 두 곳에 적지 않는다)",
     _C == (struct_map.CHUNK_MIN + struct_map.CHUNK_MAX) / 2
     and (struct_map.CHUNK_MIN, struct_map.CHUNK_MAX) == (5, 40),
     f"중앙 {_C}")
# 구간 안이 둘이면 **중앙 최근접**이지 청크 수 최대가 아니다 — 구판이 그랬다.
_st = {1: {"행수_평균": 6.0, "구간내_청크수": 9, "청크수": 9},
       2: {"행수_평균": 22.0, "구간내_청크수": 1, "청크수": 1}}
show("③ⓑ 구간 안에서는 중앙 최근접을 고른다 (구판의 「구간내 청크수 최대」가 아니다)",
     struct_map.choose_level(_st)[0] == 2, str(struct_map.choose_level(_st)[:1]))
_out = {2: {"행수_평균": 2.3, "구간내_청크수": 0, "청크수": 7},
        3: {"행수_평균": 1.8, "구간내_청크수": 0, "청크수": 9}}
_p, _w, _oor = struct_map.choose_level(_out)
show("③ⓓ 아무 레벨도 구간 안이 아니면 **최근접을 쓰고 구간밖을 세운다** (None이 아니다)",
     _p == 2 and _oor is True)
# 동점은 얕은 레벨 — 무엇이든 정해져 있어야 같은 문서가 같은 청크가 된다.
_tie = {1: {"행수_평균": 12.5, "구간내_청크수": 2, "청크수": 2},
        2: {"행수_평균": 32.5, "구간내_청크수": 2, "청크수": 2}}
show("③ 동점은 얕은 레벨이다 (멱등성 — 고르는 규칙에 빈틈을 두지 않는다)",
     struct_map.choose_level(_tie)[0] == 1)

# **LLM 0** — 어댑터가 지도 훅을 받고도 부르지 않는다. 문면이 아니라 호출을 센다.
_called = []
_raw01 = read(str(RAW / "TOC01.xlsx"))
_pieces = _BPX.extract(_raw01, struct_map_fn=lambda *a, **k: _called.append(a) or ([], {}, []))
show("③ⓐ 고정 어댑터가 구조 지도(⑦)를 부르지 않는다 — 인입마다 비용이 붙지 않는다",
     not _called and len(_pieces) == 3, f"호출 {len(_called)}회 · 조각 {len(_pieces)}건")
show("③ⓑ 신호 넷이 계층을 만든다 (번호·굵게·들여쓰기·가로병합)",
     _BPX.ADAPTER["expects"]["heading_signals"]
     == ["번호", "굵게", "들여쓰기", "가로병합"]
     and "split_level" not in _BPX.ADAPTER["expects"])
_rep01 = _BPX.level_report(_raw01)
show("③ⓑ 레벨별 분포와 고른 레벨·사유가 함께 나온다 (승인의 1차 근거 · §6.6-1)",
     len(_rep01) == 1 and _rep01[0]["분할_레벨"] == 1
     and _rep01[0]["분할_레벨_구간밖"] is False
     and set(_rep01[0]["레벨_분포"]) == {1, 2, 3},
     _rep01[0]["분할_레벨_사유"][:40])
_rep02 = _BPX.level_report(read(str(RAW / "TOC02.xlsx")))
show("③ⓓ 구간을 못 맞춘 표본은 그 사실을 산출에 싣는다 (TOC02 — 평균 4.3행)",
     _rep02[0]["분할_레벨_구간밖"] is True
     and all(p["meta"].get("split_level_out_of_range")
             for p in _BPX.extract(read(str(RAW / "TOC02.xlsx")))))

# **화면의 출처가 규칙이다** — 폐지된 상수(`expects.split_level`)를 읽지 않는다.
_apick = struct_map.adapter_level_picks(
    {"expects": {"heading_pattern": r"^(\d+(?:\.\d+)*)[.)]?\s+", "content_column": "A"}},
    _raw01)
show("③ⓑ 어댑터 경로의 화면도 규칙이 고른 레벨을 낸다 (「상수 없음」이 아니다)",
     _apick and _apick[0]["분할_레벨"] == 1
     and "구간" in _apick[0]["분할_레벨_사유"], str(_apick[0]["분할_레벨"]))

# **표를 이 어댑터에 넣으면 제안이 서지 않는다** — 시트당 1청크는 분할이 아니라 실패다.
show("③ 격자 포맷이라고 무조건 제안하지 않는다 (표는 거부 — 산출로 판정한다)",
     _reg.basic_adapter_proposal([str(RAW / "CP01.xlsx")]) is None
     and (_reg.basic_adapter_proposal([str(RAW / "TOC01.xlsx")]) or {}).get("adapter")
     == "parser/adapters/basic_prose_xlsx.py")

# ⓐⓒⓓ — 인입 2회로 실증한다. **클린에서 시작한다**(찌꺼기가 판정에 섞이지 않게).
init.init(fresh_=True)
bootstrap("process", echo=False)
_W = ROOT / "_b58_toc_wrapper.py"
_W.write_text("# -*- coding: utf-8 -*-\n"
              "from parser.adapters import basic_prose_xlsx\n"
              "ADAPTER = {**basic_prose_xlsx.ADAPTER, 'doc_type': 'toc_basic'}\n"
              "extract = basic_prose_xlsx.extract\n"
              "level_report = basic_prose_xlsx.level_report\n", encoding="utf-8")
_S = ROOT / "schemas" / "toc_basic.json"
_S.write_text(json.dumps({"doc_type": "toc_basic", "schema_version": 1,
                          "layer": "process", "payload_kind": "prose",
                          "use_blocks": ["common_core", "process_coord"],
                          "fields": {}, "edges": []}, ensure_ascii=False) + "\n",
              encoding="utf-8")
try:
    _u0 = _LLM.usage_total()["calls"]

    def _ingest_once(tag):
        for d in ("TOC01", "TOC02"):
            _o = ROOT / "parsed" / f"{d}_{tag}.json"
            _run_parse(str(_W), d, str(RAW / f"{d}.xlsx"), str(_o))
            _CP.run_document(json.loads(_o.read_text(encoding="utf-8")))
            _o.unlink(missing_ok=True)

    _ingest_once("g1")
    _snap1 = json.dumps(store.read(store.CHUNKS, {"chunks": {}})["chunks"],
                        ensure_ascii=False, sort_keys=True)
    show("③ⓐ 인입에 LLM 호출 0회 (고정 어댑터 — 사용량 계기로 증명)",
         _LLM.usage_total()["calls"] == _u0,
         f"{_LLM.usage_total()['calls'] - _u0}회")
    _q = [x for x in store.read(store.QUEUE, []) if x["kind"] == "hierarchy_unresolved"]
    show("③ⓓ 구간 밖 표본이 **큐 1건**을 남긴다 (닫힌 20종 안 · 새 kind 0)",
         len(_q) == 1 and _q[0]["doc_id"] == "TOC02"
         and _q[0]["payload"]["case"] == "size_out_of_band",
         str([(x["doc_id"], x["payload"]["case"]) for x in _q]))
    # ④-후속 ([정정] 48 ①) — **판단 재료 넷**이 실린다. 없으면 사람이 큐 화면에서
    # 레벨을 얕게 할지 깊게 할지 정할 재료가 없다.
    _pl = _q[0]["payload"]
    show("③ⓓ size_out_of_band에 판단 재료 넷이 실린다 (레벨·평균·목표 구간·어느 쪽)",
         _pl["chosen_level"] == 1 and _pl["chosen_avg_rows"] == 4.3
         and _pl["target_band"] == [struct_map.CHUNK_MIN, struct_map.CHUNK_MAX]
         and _pl["side"] == "short",
         str({k: _pl[k] for k in ("chosen_level", "chosen_avg_rows",
                                  "target_band", "side")}))
    _ingest_once("g2")
    _snap2 = json.dumps(store.read(store.CHUNKS, {"chunks": {}})["chunks"],
                        ensure_ascii=False, sort_keys=True)
    show("③ⓒ 같은 문서 2회 인입 → 청크 바이트 동일 (멱등성 · §4.8-6)",
         _snap1 == _snap2 and len(json.loads(_snap1)) == 6,
         f"{len(json.loads(_snap1))}청크")
finally:
    _W.unlink(missing_ok=True)
    _S.unlink(missing_ok=True)
    _RG.unregister("toc_basic")


# ── B58 ④ 형태 판정 — table이냐 prose냐 (문서 1 C37) ─────────────────────
print("\n■ B58 ④ — 형태 판정: 결정적 · LLM 0")

from parser import form as _FM                                # noqa: E402
from cli import ingest as _IN                                 # noqa: E402

# ⓐ **픽스처 9건의 판정** — 명세가 문턱을 뽑은 그 표본이다(table 7 · prose 2).
_XL = sorted(RAW.glob("*.xlsx"))
_J = {p.name: _FM.judge(read(str(p))) for p in _XL}
show("④ⓐ xlsx 픽스처 9건이 전부 자동 판정된다 (사람에게 올라오는 것 0건)",
     len(_J) == 9 and all(j["auto"] for j in _J.values()),
     str([n for n, j in _J.items() if not j["auto"]]))
# ⓑ **판정이 고정이다** — 문턱을 건드리면 여기서 잡힌다. 이름을 적어 둔다:
#    무엇이 table이고 무엇이 prose인지가 이 기능의 계약이다.
_EXPECT = {"CP01.xlsx": "table", "CP02_drift.xlsx": "table", "CP03_bad.xlsx": "table",
           "CP04_unlabeled.xlsx": "table", "IPQC01.xlsx": "table",
           "IPQC02.xlsx": "table", "PFMEA01.xlsx": "table",
           "TOC01.xlsx": "prose", "TOC02.xlsx": "prose"}
show("④ⓑ 9건의 판정이 고정이다 — table 7 · prose 2",
     {n: j["verdict"] for n, j in _J.items()} == _EXPECT,
     str({n: j["verdict"] for n, j in _J.items() if _EXPECT[n] != j["verdict"]}))
# **결정적이다** — 같은 입력을 두 번 넣으면 같은 답이다(멱등성의 입구 · C37).
show("④ 같은 문서를 두 번 판정하면 같다 (입구의 비결정성 0 — 문서 4 §4.8-6)",
     all(_FM.judge(read(str(p))) == _J[p.name] for p in _XL))
# **LLM 0** — 모듈이 게이트웨이를 알지 못한다. 주석이 아니라 import를 본다.
_FSRC = (ROOT / "parser" / "form.py").read_text(encoding="utf-8")
show("④ 판정기가 LLM을 알지 못한다 (core.llm import 0 — C37의 금지)",
     "core" not in {l.split()[1].split(".")[0]
                    for l in _FSRC.splitlines()
                    if l.startswith(("import ", "from "))},
     str(sorted({l.split()[1].split(".")[0] for l in _FSRC.splitlines()
                 if l.startswith(("import ", "from "))})))


def _synth(cells, indent_ratio, cols):
    _ind = {}
    for _a in list(cells)[:int(round(len(cells) * indent_ratio))]:
        _ind[_a] = 1
    return {"format": "xlsx", "sheets": [{
        "name": "S", "max_row": max(int(a[1:]) for a in cells), "max_col": cols,
        "cells": cells, "merged": [], "indent": _ind, "bold": [], "images": []}]}


# ⓒ **애매 표본 — 열 4개 + indent 60% → 자동 prose.** 잠그는 것은 판정 자체가
# 아니라 **기권 구간이 사는가**다: 열 4개는 기권해야 하고, 기권은 거부권이
# 아니어야 한다. 기권 구간이 없으면 이 문서는 열 신호 하나에 table로 넘어간다.
_amb = {}
for _r in range(1, 21):
    _amb[f"A{_r}"] = (f"{_r}. 구획 제목 {_r}" if _r <= 6 else
                      f"본문 문장 {_r} — 공정 조건과 관리 인자를 서술한 긴 문단이다. " * 2)
    if _r % 4 == 1:
        _amb[f"B{_r}"], _amb[f"C{_r}"], _amb[f"D{_r}"] = f"작성 {_r}", f"2026-0{_r % 9 + 1}", f"비고{_r}"
_ja = _FM.judge(_synth(_amb, 0.60, 4))
show("④ⓒ 열 4개 + indent 60% → **자동 prose** (기권 구간이 거부권을 쓰지 않는다)",
     _ja["verdict"] == "prose" and _ja["auto"]
     and _ja["votes"]["column_count"] == _FM.ABSTAIN,
     _ja["why"])

# ⓓ **모순 표본 — 열 12개 + indent 85% → 사람.** 반대표 0 요건이 사는 자리다.
_con = {}
for _r in range(1, 21):
    for _i in range(12):
        _con[f"{chr(65 + _i)}{_r}"] = f"{chr(65 + _i)}{_r} 고유값 {_r}-{_i}"
_jc = _FM.judge(_synth(_con, 0.85, 12))
show("④ⓓ 열 12개 + indent 85% → **사람에게** (반대표 0 요건이 산다)",
     _jc["verdict"] is None and not _jc["auto"]
     and _jc["votes"]["column_count"] == _FM.TABLE
     and _jc["votes"]["indent_share"] == _FM.PROSE,
     _jc["why"])

# ⓔ **기록** — 선택 근거에 신호값이 실려 인입 기록으로 간다. 문턱 조정의 유일한 재료다.
_b = (_IN.select(str(RAW / "CP01.xlsx"), doc_type="cp") or {}).get("basis") or {}
show("④ⓔ 선택 근거에 신호값 다섯과 판정이 실린다 (인입 기록 → 문턱 조정의 재료)",
     set((_b.get("form") or {}).get("signals") or {}) == set(_FM.SIGNALS)
     and _b["form"]["verdict"] == "table" and _b["form"]["auto"] is True,
     str(sorted((_b.get("form") or {}).get("signals") or {})))
show("④ⓔ 격자 포맷만 판정한다 (.pptx·.pdf는 포맷이 prose를 함의한다)",
     _IN.form_of(str(RAW / "PPT_basic.pptx")) is None
     and _IN.form_of(str(RAW / "CP01.xlsx")) is not None)
# **문턱은 코어 상수 한 자리다** — 층 config 키 일람(19종) 밖이다(문서 3 §3.1).
show("④ 문턱이 한 자리에 있다 (층 config가 아니다 — 조정이 코드 수색이 되지 않게)",
     set(_FM.THRESHOLDS) == set(_FM.SIGNALS) and len(_FM.SIGNALS) == 5
     and not [k for k in _FM.THRESHOLDS
              if k in json.loads((ROOT / "layers" / "process" / "config.json"
                                  ).read_text(encoding="utf-8"))])
# **판정이 사람의 지정을 이기지 않는다** — C37은 「어느 갈래로 읽는가」를 정할 뿐이다.
show("④ 판정은 선택을 갈아 끼우지 않는다 — 어긋나면 경고하고 지정대로 간다",
     _IN.select(str(RAW / "TOC01.xlsx"), doc_type="cp")["doc_type"] == "cp",
     "지정 우선")


# ── B58 ④-후속 — case 두 값과 side의 파생 ([정정] 48 ①) ────────────────
print("\n■ B58 ④-후속 — 큐 case는 닫힌 두 값 · side는 파생값")

from core.pipeline import _band_material as _BM                # noqa: E402

# **side를 박아 두면 절반의 문서에 틀린 처방이 나간다** — 짧은 쪽은 「레벨을 얕게」,
# 긴 쪽은 「깊게」로 처방이 **반대**다. 그래서 avg와 target_band에서 파생되는지를
# 양쪽 표본으로 본다: 한쪽만 보면 상수로 박아 두어도 초록이다.
_short = [{"split_level": 1, "split_level_band": [5, 40], "split_level_avg_rows": 4.3}]
_long = [{"split_level": 1, "split_level_band": [5, 40], "split_level_avg_rows": 91.0}]
show("④-후속 side가 avg·target_band에서 파생된다 (둘 다 short로 박혀 있지 않다)",
     _BM(_short)["side"] == "short" and _BM(_long)["side"] == "long",
     f"{_BM(_short)['side']} / {_BM(_long)['side']}")
# 프레임이 갈리면 **가장 멀리 벗어난 값**이 대표다 — 가장 급한 것이 머리에 온다.
_both = _short + _long
show("④-후속 프레임이 갈리면 가장 멀리 벗어난 값이 대표다",
     _BM(_both)["chosen_avg_rows"] == 91.0 and _BM(_both)["side"] == "long"
     and _BM(_both)["chosen_level"] == 1)
# 재료가 없으면 **지어내지 않는다** — None으로 남기고 화면이 그 사실을 보인다.
show("④-후속 재료가 없으면 지어내지 않는다 (side는 None)",
     _BM([{"split_level": 1}])["side"] is None
     and _BM([{"split_level": 1}])["target_band"] is None)

# **case는 닫힌 두 값이다** — 코드가 그 둘만 만든다.
import re as _re                                              # noqa: E402
_CPSRC = (ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
_cases = set(_re.findall(r'"(flat_fallback|size_out_of_band|level_out_of_range)"', _CPSRC))
show("④-후속 case는 flat_fallback · size_out_of_band 둘뿐이다 (옛 이름 0)",
     _cases == {"flat_fallback", "size_out_of_band"}, str(sorted(_cases)))

# **계층을 못 세운 문서는 flat_fallback이다** — 처방이 반대라 갈라져야 한다.
_noh = {"format": "xlsx", "sheets": [{
    "name": "S", "max_row": 4, "max_col": 1, "merged": [], "indent": {}, "bold": [],
    "images": [], "cells": {f"A{i}": f"헤딩 신호가 없는 줄 {i}" for i in range(1, 5)}}]}
_flat = _BPX.extract(_noh)
show("④-후속 계층 신호 0건 → flat_fallback 쪽 표시 (size 표시가 아니다)",
     len(_flat) == 1 and _flat[0]["meta"].get("hierarchy_unresolved") is True
     and not _flat[0]["meta"].get("split_level_out_of_range"))


print("\n" + "=" * 62)
print("전체 결과:", "PASS — P1 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
