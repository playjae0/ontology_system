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

print("\n" + "=" * 62)
print("전체 결과:", "PASS — P1 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
