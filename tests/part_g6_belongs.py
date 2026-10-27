# -*- coding: utf-8 -*-
"""G6 ⑳ 소속 — 맥락 줄 · 문서 좌표 · 소속 계약 · 이름에 소속 · 좌표 없는 스코프 개체 0 · 재사용 조건 · 붙은 곳
화면 · 보존물·동명 (B102).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 산문 표본은 **엑셀**(시트가
유닛 단위 · 제목 있는 시트 「이송 유닛」 · 제목 없는 시트 「가압 유닛」)과 **Word**(제목 경로)를 실제 파일로 만들어
파서로 읽는다. 추출은 mock 힌트(문서 7 §7.5 대체 표 「추출」 행)다. 시험마다 형태(표·산문) × 층(process ·
quality)에서 같은 성질을 잰다(CLAUDE.md §4 범용성).

잠그는 성질:
  ⓐ 맥락 줄: 엑셀은 제목이 있어도 시트명이 실린다 · 문서 · 공정 칸 · 포맷 넷(엑셀·Word·PDF·PPT)이 한 함수 ·
     실호출 입력이 그 함수의 출력이다
  ⓑ 문서 좌표: 다른 공정의 이름인 시트명 · 공유 별칭 시트 — 문서 좌표면 서브트리 밖 좌표 0 · 없으면 공유 별칭 좌표 0 ·
     파일명 제안(하나일 때만) · 기록 재사용 · 비대화형 한 줄 · 표도 같은 함수
  ⓒ 소속: 「모터」가 시트·경로·본문의 유닛 이름을 소속으로 갖는다(from) · 근거 없으면 null(지어낸 이름은 버림) ·
     경로·시트 이름은 개체 후보가 아니다 · 옛 체크포인트 `attach` 호환
  ⓓ 이름에 소속: 두 유닛의 「모터」가 다른 노드 · 소속 없는 「모터」는 좌표 접두 · `Property`는 공정 스코프(CP와 같은
     키로 만난다) · `nest_categories`가 비면 지금과 같다
  ⓔ 좌표 없는 스코프 개체 0(표·산문 × 층 둘) · 재료는 큐가 든다 · 좌표를 주고 다시 넣으면 붙는다 · 엣지 없는 노드 0
  ⓕ 재사용 조건: 지시문 판·층 config 판이 바뀌면 다시 뽑는다(이유 줄)
  ⓖ 대장 `target`·`attached`·`from` · 「표기 → 붙은 노드」 · 「└ 관계 → 상대」 · `--trace` · 좌표 줄 · 끝 요약 ·
     목록 · 재시도 분포 · 표 진행 줄 분모 = 실제 값 수
  ⓗ 해시 없는 보존물 재사용 0 · 동명 다른 경로 멈춤 / `--revise`면 개정
  B140 이름 없는 대상 — [5/8] 예고(쓰기 0 · LLM 0) · 더하기(pty 관문 → 기록 → [6/8]이 평소 길로) · 다른 문서 고아 · 같은 것 ·
     다시(재인입 · 재구축 · 지우기) · 관계 끝점 사전 조회 · 소속 노드의 좌표 상속 · 막기 · 비대화형
"""
from __future__ import annotations

import contextlib
import io
import re
import zipfile
from pathlib import Path

sys_path = __import__("sys").path
sys_path.insert(0, str(Path(__file__).resolve().parent))
sys_path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done, overlay   # noqa: F401

import make_b88 as MB                                   # noqa: E402 — Word 조립 재료(창작)
from openpyxl import Workbook                           # noqa: E402
from cli import doc_coord as DC                         # noqa: E402
from cli import ingest as IG                            # noqa: E402
from core.build import extract as EX, extract_ctx as XC, ledger as LG   # noqa: E402
from core.llm import gateway                            # noqa: E402
from core.state.world import World                      # noqa: E402
from parser import pipeline, struct_map, tagger as TG   # noqa: E402
from parser.adapters import basic_docx as DX, basic_prose_xlsx as BX   # noqa: E402

from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS
TMP = Path(__import__("tempfile").mkdtemp(prefix="b102_"))   # 클린(init --fresh)이 지우지 않는 자리
XLSX_SHEETS = {"이송 유닛": ["1. 구동부", "모터는 서보 모터를 쓴다.", "2. 안전", "커버를 단다."],
               "가압 유닛": ["모터는 유압 모터를 쓴다.", "가압력은 매 시간 기록한다."]}


def _xlsx(path):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in XLSX_SHEETS.items():
        ws = wb.create_sheet(title=name)
        for r, v in enumerate(rows, 1):
            ws.cell(row=r, column=1, value=v)
    _P.ensure(path)
    wb.save(path)
    return path


def _docx(path):
    body = "".join([MB._p("이송 유닛", "1"), MB._p("모터는 서보 모터를 쓴다."),
                    MB._p("가압 유닛", "1"), MB._p("모터는 유압 모터를 쓴다. 가압력은 매 시간 기록한다.")])
    _P.ensure(path)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", MB._CT)
        z.writestr("_rels/.rels", MB._ROOT_RELS)
        z.writestr("word/document.xml", MB._doc(body))
        z.writestr("word/styles.xml", MB._STYLES)
        z.writestr("word/_rels/document.xml.rels", MB._rels([("rIdSty", "styles", "styles.xml")]))
    return path


FILES = {"엑셀": _xlsx(TMP / "B102_노칭_사양.xlsx"), "Word": _docx(TMP / "B102_노칭_설명.docx")}
ROLES = {"이송 유닛": "prose", "가압 유닛": "prose"}


def _parse(form, doc_id, doc_coord=None, layer=None):
    ad = BX if form == "엑셀" else DX
    struct_map.invalidate(doc_id)
    kw = {"sheet_roles": ROLES} if form == "엑셀" else {}
    r = pipeline.parse(ad, doc_id, str(FILES[form]), closed_list=TG.closed_list(layer or "process"),
                       doc_coord=doc_coord, **kw)
    return r.envelope


def _setup(nest=("Component",)):
    """덧칠(Component · 겸 렌즈) + 공통 `nest_categories` + 소속 엣지에 필요한 카테고리쌍 — 상태 루트에만."""
    overlay(component=True)

    def _c(c):
        c.setdefault("canonical_scope", {})["nest_categories"] = list(nest)
    _rw(_P.common(), _c)

    pats = [{"src": s_, "rel": "part_of", "dst": d_, "symmetric": False, "정의문": f"{s_}가 {d_}에 속한다"}
            for s_, d_ in (("Component", "Unit"), ("Component", "Process"), ("Unit", "Process"))]
    pairs = {f"{p_['src']},{p_['dst']}": "part_of" for p_ in pats}

    def _q(c):                                    # 품질 층도 Component·Unit을 렌즈로 쓴다(층 둘)
        c["categories"]["Component"] = "(품질층의 렌즈) 불량이 일어나는 구성 기계"
        c["relation_patterns"] += pats
        c.setdefault("category_pair_map", {}).update(pairs)

    def _p(c):                                    # 공정 층 — 이미 있는 쌍은 그대로(덧칠은 더하기만)
        have = {(p_["src"], p_["rel"], p_["dst"]) for p_ in c["relation_patterns"]}
        c["relation_patterns"] += [p_ for p_ in pats if (p_["src"], p_["rel"], p_["dst"]) not in have]
        for k, v in pairs.items():
            c.setdefault("category_pair_map", {}).setdefault(k, v)
    _rw(_P.layers("quality", "config.json"), _q)
    _rw(_P.layers("process", "config.json"), _p)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


def _hint(doc_id, by_loc):
    (HINTS / f"{doc_id}.json").write_text(json.dumps(by_loc, ensure_ascii=False), encoding="utf-8")


def _unit_of(c):
    """그 청크가 어느 유닛의 것인가 — 표본 정답(시트 또는 제목 경로에서)."""
    m = c.get("meta") or {}
    return m.get("sheet") or (m.get("section_path") or c.get("section") or "").split(" > ")[0]


def _from_of(c):
    return "시트" if (c.get("meta") or {}).get("sheet") else "경로"


def _prose_env(form, lay, doc_id, belongs="unit", doc_coord="노칭"):
    env = _parse(form, doc_id, doc_coord=doc_coord)
    dt = "ppt_" + lay
    env["doc_type"] = dt
    for c in env["chunks"]:
        c["doc_type"] = dt
    hints = {}
    for c in env["chunks"]:
        if "모터" not in c.get("text", ""):
            continue
        u = _unit_of(c)
        b = ({"name": u, "category": "Unit", "from": _from_of(c)} if belongs == "unit" else
             {"name": "없는 유닛 B102", "category": "Unit", "from": "본문"} if belongs == "invented" else None)
        ents = [{"surface": "모터", "category": "Component", "belongs_to": b}]
        if "가압력" in c.get("text", "") and "Property" in load_config(lay)["categories"]:
            ents.append({"surface": "가압력", "category": "Property",
                         "belongs_to": {"name": u, "category": "Unit", "from": _from_of(c)}})
        hints[c["source_locator"]] = {"entities": ents, "relations": [], "attach": []}
    if belongs == "legacy":                        # 옛 체크포인트 — attach만 있고 belongs_to 없음
        hints = {k: {"entities": [{"surface": "모터", "category": "Component"}], "relations": [],
                     "attach": [{"surface": "모터", "attach_to": {"name": "노칭", "category": "Process"}}]}
                 for k in hints}
    _hint(doc_id, hints)
    return env


def _live(name_part, cat=None):
    return [n for _l, n in World().nodes() if name_part in n["canonical"] and ops.is_live(n)
            and (cat is None or n["category"] == cat)]


def _all_edges():
    out = []
    for lay in ("process", "quality"):
        out += [(e["rel"], e["src"], e["dst"]) for e in open_graph(lay).edges]
    return out


def _canon(nid):
    n = World().get(nid)
    return (n or {}).get("canonical")


PROSE_MATRIX = [(f, l) for f in ("엑셀", "Word") for l in ("process", "quality")]
_made = []

# ────────────────────────────────────────────────────────────── ⓐ
print("\n■ B102 ① 맥락 줄 — 한 함수 (엑셀 · Word · PDF · PPT)")
_setup()
_ok, _det = True, []
for form in ("엑셀", "Word"):
    env = _parse(form, f"B102CTX{form[0]}", doc_coord="노칭")
    doc = XC.doc_info(env)
    for c in env["chunks"]:
        line = XC.context_line(c, doc)
        need = [f"문서: {FILES[form].name}", "공정: 노칭"]
        if form == "엑셀":
            need.append(f"시트: {c['meta']['sheet']}")
        else:
            need.append(f"경로: {c['meta']['section_path']}")
        _ok &= all(x in line for x in need)
        _det.append(line)
_titled = [l for l in _det if "시트: 이송 유닛" in l]
_ok &= bool(_titled) and all("경로: " in l for l in _titled)          # 제목이 있어도 시트명
# PDF · PPT 조각 — 같은 함수(포맷 차이는 조각이 든 값이 말한다)
_pp = XC.context_line({"process_ref": None, "section": "슬라이드 3", "meta": {"section_path": "슬라이드 3"}},
                      {"name": "a.pptx", "coord": "스태킹"})
_pd = XC.context_line({"process_ref": "적층", "meta": {"section_path": "2. 사양 > 2.1 적층"}}, {"name": "b.pdf"})
_ok &= _pp == "[문서: a.pptx · 공정: 스태킹 · 경로: 슬라이드 3]" and _pd == "[문서: b.pdf · 공정: 적층 · 경로: 2. 사양 › 2.1 적층]"
# 실호출 입력 = 그 함수의 출력(가짜 게이트웨이 — 보낸 것을 잡는다)
_sent = []
_keep = (gateway.use_mock, gateway.chat, gateway.prompt)
gateway.use_mock = lambda: False
gateway.chat = lambda msgs, **k: (_sent.append(json.loads(msgs[1]["content"])), {"entities": [], "relations": []})[1]
gateway.prompt = lambda name: "지시문"
try:
    env = _parse("엑셀", "B102CTXL", doc_coord="노칭")
    EX._DOC.clear()
    EX._DOC.update(XC.doc_info(env))
    c0 = env["chunks"][0]
    EX._candidates_for("x", c0, load_config("process"), {})
finally:
    gateway.use_mock, gateway.chat, gateway.prompt = _keep
_ok &= bool(_sent) and _sent[0]["chunk"] == XC.with_context(c0, XC.doc_info(env)) \
    and _sent[0]["chunk"].startswith(XC.context_line(c0, XC.doc_info(env)))
show("ⓐ 맥락 줄 — 엑셀은 제목이 있어도 시트명 · 문서 · 공정 칸 · 엑셀·Word·PDF·PPT 한 함수 · 실호출 입력이 그 출력",
     _ok, " / ".join(_det[:3]) + f" / {_pp} / {_pd}")

# ────────────────────────────────────────────────────────────── ⓑ
print("\n■ B102 ② 문서 좌표 — 서브트리 · 공유 별칭 · 파일명 제안 · 기록 · 표도 같은 함수")
nodes = TG.closed_list("process")
pcs = [{"source_locator": "S1", "section": "적층"},            # 다른 공정(스태킹)의 이름인 시트명
       {"source_locator": "S2", "section": "비전 검사"},       # 공유 별칭(노칭·스태킹 둘)
       {"source_locator": "S3", "section": "노칭 타발"}]
_with = {p["source_locator"]: p for p in TG.coord_from_section(pcs, nodes=nodes, doc_coord="노칭")}
_none = {p["source_locator"]: p for p in TG.coord_from_section(pcs, nodes=nodes)}
_sub_idx = TG.scoped_index(nodes, "노칭")[0]            # 노칭 서브트리 안에서 하나로 풀리는 표기
# 기대 변경(B157 ① — 줄기 밖 공정 이름의 시트명 「적층」(스태킹)은 그 공정 좌표 + 쌍 대조로 · 덱 · 표와 같은 규칙 — 무시 0)
_ok_b1 = (all(p["process_ref"] in _sub_idx for k, p in _with.items() if k != "S1")
          and _with["S1"]["process_ref"] == "적층" and _with["S1"]["meta"].get("coord_other") == "적층"
          and not _with["S1"]["meta"].get("coord_ignored") and not _with["S1"]["meta"].get("coord_from_doc")
          # 기대 변경(B104 ①) — 범위 안에서 하나인 공유 별칭은 그 노드 canonical로 쓰고 원 표기는 meta에
          and _with["S2"]["process_ref"] == _sub_idx["비전 검사"]["canonical"]
          and _with["S2"]["meta"].get("coord_tag_from") == "비전 검사" and _with["S3"]["process_ref"] == "노칭 타발")
_ok_b2 = (_none["S2"].get("process_ref") is None and _none["S2"]["meta"].get("coord_shared_skip") == ["비전 검사"]
          and _none["S1"]["process_ref"] == "적층")
show("ⓑ 문서 좌표면 줄기 밖 공정 이름 시트는 그 공정(B157) · 공유 별칭은 범위 안 하나 · 없으면 공유 별칭 좌표 0",
     _ok_b1 and _ok_b2, f"좌표 있음 {[(k, p['process_ref']) for k, p in _with.items()]} · "
     f"없음 {[(k, p.get('process_ref')) for k, p in _none.items()]}")
_s1 = TG.suggest_doc_coord("B102_노칭_사양.xlsx", nodes)
_s2 = TG.suggest_doc_coord("노칭_스태킹_비교.xlsx", nodes)
_s3 = TG.suggest_doc_coord("비전 검사_기준.xlsx", nodes)
show("ⓑ 파일명 제안 — 조각 하나가 노드 하나에 맞을 때만(둘이면 없음 · 공유 별칭 없음)",
     _s1[0] == "노칭" and _s2[0] is None and _s3[0] is None, f"{_s1} · {_s2} · {_s3}")
_rec = DC._file()
_rec0 = _rec.read_bytes() if _rec.exists() else None
_b = io.StringIO()
with contextlib.redirect_stdout(_b):
    _d1 = DC.decide("x/B102DC.xlsx", "B102DC", "노칭", ask=False)
    _d2 = DC.decide("x/B102DC.xlsx", "B102DC", None, ask=False)
    _d3 = DC.decide("x/B102_노칭.xlsx", "B102DC2", None, ask=False)
    _d4 = DC.decide("x/B102무명.xlsx", "B102DC3", None, ask=False)
_lines = [l for l in _b.getvalue().splitlines() if l.strip()]
show("ⓑ 기록 재사용(사람 → 기록) · 파일명 · 없음 — 비대화형은 묻지 않고 한 줄씩",
     (_d1, _d2, _d3, _d4) == (("노칭", "사람"), ("노칭", "기록"), ("노칭", "파일명"), (None, "없음"))
     and len(_lines) == 4 and all(l.strip().startswith("문서 좌표 — ") for l in _lines), " / ".join(_lines))
if _rec0 is None:
    _rec.unlink(missing_ok=True)
else:
    _rec.write_bytes(_rec0)
_recs = [{"source_locator": "R1", "process_ref": None}, {"source_locator": "R2", "process_ref": "노칭 타발"}]
_inh = TG.inherit_doc_coord(_recs, "노칭")
show("ⓑ 표도 같은 함수 — 빈 행만 문서 좌표를 물려받는다(있는 값은 덮지 않는다)",
     [r["process_ref"] for r in _inh] == ["노칭", "노칭 타발"] and _inh[0]["meta"].get("coord_from_doc")
     and not (_inh[1].get("meta") or {}).get("coord_from_doc"), str([r["process_ref"] for r in _inh]))

# ────────────────────────────────────────────────────────────── B157 줄기 밖 공정 이름 구간
print("\n■ B157 — 줄기 밖 공정 이름의 시트명 · 제목은 그 구간의 공정(쌍 대조로) · 조상 표기는 문서 좌표 그대로 · 본문 가드 그대로")
from core.build import structure as ST157                 # noqa: E402
_x157 = Workbook()
_x157.active.title = "사양"
for _i, _v in enumerate(["1. 노칭 타발", "타발 속도는 30spm이다.", "2. 스태킹", "적층 속도는 10ppm이다. 노칭과 연동한다.",
                         "3. Notching 공정", "공정 온도는 25도이다."], 1):
    _x157.active.cell(row=_i, column=1, value=_v)
_x157.save(TMP / "B157S.xlsx")
struct_map.invalidate("B157S")
_e157 = pipeline.parse(BX, "B157S", str(TMP / "B157S.xlsx"), closed_list=TG.closed_list("process"), doc_coord="노칭",
                       sheet_roles={"사양": "prose"}, structure=ST157.structurer()).envelope
_e157["doc_type"] = "ppt_process"
for _c in _e157["chunks"]:
    _c["doc_type"] = "ppt_process"
_hint("B157S", {"사양!R2": {"entities": [{"surface": "타발 속도", "category": "Property", "value": "30spm"}], "relations": []},
                "사양!R4": {"entities": [{"surface": "적층 속도", "category": "Property", "value": "10ppm"},
                                       {"surface": "노칭", "category": "Unit"}], "relations": []},
                "사양!R6": {"entities": [{"surface": "공정 온도", "category": "Property", "value": "25도"}], "relations": []}})
_pr157 = DC.pair_report(_e157)[0]["pairs"].get(("문서 좌표", ("노칭", "스태킹")), {}).get("rows")
with contextlib.redirect_stdout(io.StringIO()):
    run_document(dict(_e157))
_made.append("B157S")
_rf157 = {c["source_locator"]: c for c in _e157["chunks"]}
_q157 = [q for q in store.read(store.QUEUE, []) if q.get("doc_id") == "B157S" and q.get("kind") == "coord_mismatch"]
_lr157 = (LG.read("B157S") or {}).get("rows") or []
_hd157 = next((r for r in _lr157 if r.get("surface") == "스태킹" and r.get("field") == "Process"), {})
show("B157 ⓐ 허브 표본(--coord 노칭) — 「2. 스태킹」 아래 조각 좌표 = 스태킹 · 판정 전 쌍 화면과 구축 큐의 「노칭 ↛ 스태킹」 같은 수 · "
     "「적층 속도」 → 스태킹::적층 속도 · 제목 「스태킹」 착지 = 골격 노드 · 「1.」 「3.」 아래는 그대로(문서 좌표)",
     _rf157["사양!R4"]["process_ref"] == "스태킹" and _rf157["사양!R4"]["meta"].get("coord_other") == "2. 스태킹"
     and _pr157 == len(_q157) == 1 and _live("스태킹::적층 속도") and not _live("노칭::적층 속도")
     and (_hd157.get("verdict"), _hd157.get("target")) == ("match", "스태킹")
     and all(_rf157[k]["process_ref"] == "노칭" and _rf157[k]["meta"].get("coord_from_doc") for k in ("사양!R2", "사양!R6")),
     f"R4 {_rf157['사양!R4']['process_ref']} · 쌍 {_pr157} · 큐 {len(_q157)} · 제목 {_hd157.get('verdict')} → {_hd157.get('target')}")
_up157 = TG.coord_from_section([{"source_locator": "S9", "section": "노칭"}], nodes=nodes, doc_coord="노칭::노칭 타발")[0]
_cc157 = DC.coord_counts({"chunks": [_with["S1"], _up157]})
show("B157 ⓑ B102 ② 표본 — 시트명 「적층」은 그 조각 좌표 「적층」 + 쌍 어긋남 · 조상 표기(문서 좌표 「노칭 타발」 · 시트명 「노칭」)는 "
     "문서 좌표 그대로 · 화면 칸 「다른 공정 구간」 1 · 「위 공정 표기」 1",
     _with["S1"]["process_ref"] == "적층" and DC.pair_report({"doc_id": "B157B", "doc_coord": "노칭", "chunks": [_with["S1"]]})[0]["pairs"]
     and _up157["process_ref"] == "노칭::노칭 타발" and _up157["meta"].get("coord_ignored") == ["노칭"]
     and (_cc157["다른 공정 구간"], _cc157["위 공정 표기"]) == (1, 1),
     f"S1 {_with['S1']['process_ref']} · 조상 {_up157['process_ref']} {_up157['meta'].get('coord_ignored')} · 칸 {_cc157}")
# B157 리뷰 고침 — 정확 일치를 먼저(줄기 밖 「ABC」 정확 · 줄기 안 「abc」는 접기로만 맞는다 → 정확한 쪽 — 사전 조회와 같은 차례)
_nd157 = [{"canonical": "P", "parent": None}, {"canonical": "Q", "parent": None, "aliases": ["ABC"]},
          {"canonical": "P1", "parent": "P", "aliases": ["abc"]}]
_x157r = TG.coord_from_section([{"source_locator": "S1", "section": "1. ABC"}], nodes=_nd157, doc_coord="P")[0]
show("B157 리뷰 고침 ⓑ 정확 일치가 있으면 접기 대조를 섞지 않는다 — 제목 「1. ABC」(줄기 밖 Q의 별칭 정확 · 줄기 안 P1의 「abc」는 접기) → Q 쪽",
     _x157r["process_ref"] == "ABC" and _x157r["meta"].get("coord_other") == "1. ABC", f"{_x157r}")
_mn157 = next((r for r in _lr157 if r.get("surface") == "노칭" and r.get("field") == "Unit"), {})
show("B157 ⓒ 본문 가드 그대로 — 「2. 스태킹」 구간 본문의 「노칭」 개체 → 관련 링크(노드 0)",
     _mn157.get("verdict") == "mention" and not _live("스태킹::노칭"), f"노칭 {_mn157.get('verdict')}")
_n157 = _parse("엑셀", "B157N", doc_coord="노칭")
show("B157 ⓓ 다른 공정 구간이 없는 산문 표본 — 새 표시 0 · 조각 좌표는 지금처럼 문서 좌표(봉투 바이트 비교는 마감 보고)",
     not any((c.get("meta") or {}).get("coord_other") for c in _n157["chunks"])
     and all(c["process_ref"] == "노칭" and (c.get("meta") or {}).get("coord_from_doc") for c in _n157["chunks"]),
     str([c["process_ref"] for c in _n157["chunks"]]))

# ────────────────────────────────────────────────────────────── ⓒ ⓓ ⓔ(산문)
print("\n■ B102 ③④⑤ 소속 · 이름에 소속 · 좌표 없는 스코프 개체 0 (엑셀·Word × 층 둘)")
_oc, _od, _oe, _ol = [], [], [], []
for form, lay in PROSE_MATRIX:
    _setup()
    did = f"B102{form[0]}{lay[0].upper()}"
    _made.append(did)
    env = _prose_env(form, lay, did)
    run_document(env)
    rows = [r for r in (LG.read(did) or {}).get("rows") or [] if r.get("role") == "entity"]
    motors = {r["target"] for r in rows if r["surface"] == "모터"}
    froms = {r.get("from") for r in rows if r["surface"] == "모터"}
    want = {f"노칭::{u}::모터" for u in ROLES}
    # 모터 → 유닛(소속) · 유닛 → 골격(좌표 폴백)
    e = _all_edges()
    units = {u: next((n["id"] for n in _live(f"노칭::{u}", "Unit") if n["canonical"] == f"노칭::{u}"), None)
             for u in ROLES}
    skel = next(n["id"] for _l, n in World().nodes() if n["canonical"] == "노칭")
    mot_ids = {n["canonical"]: n["id"] for n in _live("::모터", "Component")}
    edge_ok = all(any(r == "part_of" and s == mot_ids.get(f"노칭::{u}::모터") and d == units[u] for r, s, d in e)
                  and any(units[u] in (s, d) and skel in (s, d) for r, s, d in e) for u in ROLES)
    res = (LG.read(did) or {}).get("result") or {}
    _oc.append((form, lay, motors == want and froms == {_from_of(env["chunks"][0])} and edge_ok
                and not any(r["surface"] in ROLES for r in rows),
                f"모터 → {sorted(motors)} · from {sorted(map(str, froms))} · 엣지 {edge_ok}"))
    _od.append((form, lay, len(motors) == 2
                and {r["target"] for r in rows if r["surface"] == "가압력"} == ({"노칭::가압력"} if lay == "process" else set()),
                f"가압력 → {sorted({r['target'] for r in rows if r['surface'] == '가압력'})}"))
    _ol.append((form, lay, res.get("엣지 없는 노드") == 0 and (res.get("부착") or {}).get(f"소속 {_from_of(env['chunks'][0])}", 0) >= 2,
                f"엣지 없는 노드 {res.get('엣지 없는 노드')} · 부착 {res.get('부착')}"))
    # 근거 없음 → null(지어낸 이름은 버린다) · 옛 attach
    run_document(_prose_env(form, lay, did + "N", belongs="invented"), allow_duplicate=True)
    _made.append(did + "N")
    rn = [r for r in (LG.read(did + "N") or {}).get("rows") or [] if r.get("surface") == "모터"]
    dfx = store.path(store.DEFECTS).read_text(encoding="utf-8") if store.path(store.DEFECTS).exists() else ""
    _null_ok = (rn and all(r.get("from") is None and r["target"] == "노칭::모터" for r in rn)
                and "소속 출처 없음" in dfx and not _live("없는 유닛 B102")
                and ((LG.read(did + "N") or {}).get("result") or {}).get("소속 없음 비율"))
    run_document(_prose_env(form, lay, did + "L", belongs="legacy"), allow_duplicate=True)
    _made.append(did + "L")
    rl = [r for r in (LG.read(did + "L") or {}).get("rows") or []
          if r.get("surface") == "모터" and r.get("role") == "entity"]
    _leg_ok = rl and all(r.get("from") == "옛 attach" and r["target"] == "노칭::모터" for r in rl)
    _oc[-1] = (*_oc[-1][:2], _oc[-1][2] and _null_ok and _leg_ok,
               _oc[-1][3] + f" · 지어낸 소속 → null {bool(_null_ok)} · 옛 attach {bool(_leg_ok)}")
# 경로·시트 이름은 개체 후보가 아니다 — mock 갈래는 본문만 본다(맥락 줄은 실호출의 소속 근거)
_c0 = next(c for c in _parse("엑셀", "B102MK")["chunks"] if (c.get("meta") or {}).get("sheet") == "가압 유닛")
_mk = EX._mock_candidates("x", _c0["text"], load_config("process"), {"가압 유닛": "Unit", "모터": "Component"})
show("ⓒ 소속 — 「모터」가 시트·경로의 유닛 이름을 소속으로(from) · 소속 엣지 · 유닛은 좌표에 · 근거 없으면 null"
     "(지어낸 이름은 버리고 결함 로그) · 옛 attach 호환 (엑셀·Word × 층 둘)",
     all(o for _f, _l, o, _d in _oc), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _oc))
# 기대 변경(B113 ① — 지시문 3.3 규약 10 · e-1.5 → B115 ③ — 소속 출처 넷 · e-1.6 → B119 ② — 구조 사슬 · e-1.7 → B120 ① — 값 · e-1.8 → B124 ③ — 역할 셋 · e-1.9 → B125 ①④ — 공정 목록 · 슬라이드 묶음 · 캡처 · e-2.0)
show("ⓒ 경로·시트 이름은 개체 후보가 아니다 — 본문에 없는 시트명은 후보 0 · 지시문 규칙 판 e-2.0",
     [x["surface"] for x in _mk["entities"]] == ["모터"] and EX.prompt_version() == "e-2.0",
     f"후보 {[x['surface'] for x in _mk['entities']]} · 지시문 {EX.prompt_version()}")

# 이름에 소속 — CP 표본과 같은 키 · nest가 비면 지금과 같다
_setup()
run_document(_prose_env("엑셀", "process", "B102KEY"))
_cp = {**TABLE, "doc_id": "B102CPK", "records": [dict(CPREC, source_locator="K1", 관리항목="가압력")]}
run_document(_cp)
_pk = _live("노칭::가압력", "Property")
_setup(nest=())
run_document(_prose_env("엑셀", "process", "B102FLAT"))
_flat = {r["target"] for r in (LG.read("B102FLAT") or {}).get("rows") or [] if r.get("surface") == "모터"}
_made += ["B102KEY", "B102FLAT"]
show("ⓓ 이름에 소속 — 두 유닛의 「모터」는 다른 노드 · Property는 공정 스코프(CP 행과 한 노드) · nest가 비면 지금과 같다(스코프 밖 이름 하나)",
     all(o for _f, _l, o, _d in _od) and len(_pk) == 1 and _flat == {"모터"},
     " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _od) + f" ‖ CP·산문 가압력 노드 {len(_pk)} · nest 빈 목록 → {sorted(_flat)}")

# 좌표 없는 스코프 개체 0 — 표·산문 × 층 둘
for form, lay in [("표", "process"), ("표", "quality"), ("엑셀", "process"), ("Word", "quality")]:
    _setup()
    did = f"B102NC{form[0]}{lay[0].upper()}"
    _made.append(did)
    if form == "표":
        dt = f"b102t{lay[0]}"
        p = _P.schemas(f"{dt}.json")
        _P.ensure(p)
        p.write_text(json.dumps({"doc_type": dt, "schema_version": 1, "layer": lay,
                                 "use_blocks": ["common_core", "process_coord"],
                                 "fields": {"개체": {"role": "entity", "category": "Unit"}}, "edges": []},
                                ensure_ascii=False), encoding="utf-8")
        dts = store.read(store.DOC_TYPES, {})
        dts[dt] = {"doc_type": dt, "status": "registered", "layer": lay, "schema": f"schemas/{dt}.json",
                   "adapter": "-", "schema_version": 1}
        store.write(store.DOC_TYPES, dts)
        base = {k: v for k, v in CPREC.items() if k not in ("설비", "관리항목")}
        mk = lambda ref: {**TABLE, "doc_id": did, "doc_type": dt, "records": [  # noqa: E731
            dict(base, source_locator="N1", doc_type=dt, process_ref=ref, process_group=ref and "조립",
                 개체="B102 이송 유닛")]}
        env0, env1 = mk(None), mk("노칭")
    else:
        env0 = _prose_env(form, lay, did, belongs=None, doc_coord=None)
        env1 = _prose_env(form, lay, did, belongs=None, doc_coord="노칭")
    run_document(env0)
    q = [x for x in store.read(store.QUEUE, []) if x["doc_id"] == did and x["kind"] == "missing_field"]
    mat = [d for x in q for d in (x["payload"].get("dropped_entities") or x["payload"].get("items") or [])]
    no_node = not _live("모터", "Component") and not _live("B102 이송 유닛")
    run_document(env1)
    res = (LG.read(did) or {}).get("result") or {}
    got = _live("노칭::모터", "Component") or _live("노칭::B102 이송 유닛")
    unscoped = [n for _l, n in World().nodes() if n["category"] in ("Component", "Unit", "Property")
                and "::" not in n["canonical"] and ops.is_live(n)]
    _oe.append((form, lay, no_node and bool(q) and bool(mat) and bool(got) and not unscoped
                and res.get("엣지 없는 노드") == 0,
                f"좌표 없음 → 노드 0 {no_node} · missing_field {len(q)} · 재료 {len(mat)} → 좌표 주고 다시: "
                f"{[n['canonical'] for n in got][:2]} · 엣지 없는 노드 {res.get('엣지 없는 노드')}"))
    if form == "표":
        dts = store.read(store.DOC_TYPES, {})
        dts.pop(dt, None)
        store.write(store.DOC_TYPES, dts)
        _P.schemas(f"{dt}.json").unlink(missing_ok=True)
show("ⓔ 좌표 없는 스코프 개체 0 — 노드를 만들지 않고 재료는 missing_field가 든다 · 좌표를 주고 다시 넣으면 붙는다 · "
     "스코프 카테고리에 좌표 접두 없는 노드 0 · 엣지 없는 노드 0 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _oe), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _oe))
show("ⓔ 폴백 한 함수 — 소속 대상으로 앉은 유닛도 좌표에 닿는다 · 엣지 없는 노드 0 (엑셀·Word × 층 둘)",
     all(o for _f, _l, o, _d in _ol), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ol))

# ────────────────────────────────────────────────────────────── ⓕ
print("\n■ B102 ⑥ 추출 재사용 조건 — 지시문 판 · 층 config 판")
_setup()
_of = []
for lay in ("process", "quality"):
    did = f"B102RU{lay[0].upper()}"
    _made.append(did)
    env = _prose_env("엑셀", lay, did)
    cfg = load_config(lay)
    _pv = EX.prompt_version
    EX.prompt_version = lambda name="extract": "e-1.3"
    try:
        run_document(env)
    finally:
        EX.prompt_version = _pv
    r1 = EX.reuse_check(env, cfg=cfg)
    notes = []
    run_document(env, notice=notes.append)
    r2 = EX.reuse_check(env, cfg=cfg)
    # 기대 변경(B120 ③ — 층 config 판 = 추출 갈래 칸의 해시 · 정의문이 바뀌면 다시 · config_version만은 기록이라 그대로)
    _k0 = next(iter(cfg["categories"]))
    cfg2 = dict(cfg, categories={**cfg["categories"], _k0: cfg["categories"][_k0] + " (B120 — 정의문을 바꿨다)"})
    r3 = EX.reuse_check(env, cfg=cfg2)
    r4 = EX.reuse_check(env, cfg=dict(cfg, config_version=f"{cfg.get('config_version')}-b102"))
    why = [n.get("다시") for n in notes if n.get("단계") == "추출예고"]
    _now = EX.prompt_version()                     # 지금 판(B113 — e-1.5) — 판 문자열이 아니라 「바뀌면 다시」를 잰다
    _of.append((lay, r1 == (False, f"지시문 e-1.3 → {_now}") and r2[0] and not r3[0]
                and r3[1].startswith("층 config(추출 칸) ") and r4[0]
                and why and why[0] == f"지시문 e-1.3 → {_now}",
                f"{r1} · 다시 뽑은 뒤 {r2} · 정의문 바뀜 {r3} · config_version만 {r4} · 예고 {why[:1]}"))
show("ⓕ 지시문 판이 바뀌면 다시 뽑는다(예고 줄에 이유) · 다시 뽑은 뒤 재사용 · 정의문이 바뀌면 다시 · config_version만은 그대로 "
     "(층 둘 · 표는 추출이 없다)", all(o for _l, o, _d in _of), " ‖ ".join(f"{l} {d}" for l, _o, d in _of))

# ────────────────────────────────────────────────────────────── ⓖ
print("\n■ B102 ⑦ 붙은 곳을 말한다 — 대장 · 화면 (인입 명령 그대로)")
from g6_common import _register, _unregister, _run, DT   # noqa: E402
_setup()
_register("process", DT)
xl = FILES["엑셀"]
did = IG.doc_id_of(xl)
_made.append(did)
_hint(did, {c["source_locator"]: {"entities": [{"surface": "모터", "category": "Component",
                                               "belongs_to": {"name": _unit_of(c), "category": "Unit", "from": "시트"}}],
                                  "relations": [], "attach": []}
            for c in _parse("엑셀", did, doc_coord="노칭")["chunks"] if "모터" in c.get("text", "")})
out = _run("ingest-file", str(xl), "--doc-type", DT, "--allow-mock", "--coord", "노칭",
           "--sheets", "1-2:prose")
rows = [r for r in (LG.read(did) or {}).get("rows") or [] if r.get("role") == "entity"]
att = [a for r in rows for a in r.get("attached") or []]
_ok_g1 = (rows and all(r.get("target") and r.get("from") == "시트" for r in rows)
          and any(a.get("path", "").startswith("소속") and a.get("rel") == "part_of" for a in att))
show("ⓖ 대장 — target(붙은 노드) · attached(관계 · 상대 · 경로) · from", _ok_g1,
     json.dumps([{k: r.get(k) for k in ("surface", "target", "from", "attached")} for r in rows][:2], ensure_ascii=False))
_need = ["문서 좌표 — 노칭 (출처: 사람)", "   좌표 — 조각 ", "부착 — 소속(", "     └ 모터 · part_of"]
show("ⓖ 인입 화면 — 문서 좌표 줄 · 좌표 줄 · 「└ 관계 → 상대」 · 끝 요약 부착(소속 없음 비율은 없는 것이 있을 때 — ⓒ)",
     all(x in out for x in _need), " / ".join(l.strip() for l in out.splitlines()
                                              if any(x.strip() in l for x in _need))[:600])
_tr = _run("show", "report", did, "--trace")
_ex = _run("show", "extract", did, "--full")
show("ⓖ show report --trace(표기 → 붙은 노드 · 관계 → 상대) · show extract --full(맥락 줄 · 소속)",
     "노칭::이송 유닛::모터" in _tr and "part_of" in _tr and "[문서: " in _ex and "소속" in _ex and "이송 유닛" in _ex,
     " / ".join([l.strip() for l in _tr.splitlines() if "모터" in l][:2] + [l.strip() for l in _ex.splitlines() if "[문서" in l][:1]))
_unregister(DT)
# 표 진행 줄 분모 = 실제 값 수(빈 칸은 세지 않는다 — 행 × 2 고정이 아니다)
_cpenv = load("CP01")
_cpenv["records"] = [dict(r, 관리항목=None) if i % 2 else r for i, r in enumerate(_cpenv["records"][:6])]
_v = IG._value_count(_cpenv, {"doc_type": "cp"})
_ent = sum(1 for r in _cpenv["records"] for f in ("설비", "관리항목") if r.get(f))
show("ⓖ 표 진행 줄 분모 = 판정 계획의 값 수(빈 칸 제외 — 행 × 2 고정 아님)", 0 < _v <= _ent < len(_cpenv["records"]) * 2,
     f"분모 {_v} · 값 있는 칸 {_ent} · 행×2 {len(_cpenv['records']) * 2}")

# ────────────────────────────────────────────────────────────── ⓗ
print("\n■ B102 ⑧ 보존물 · 동명")
_kp = struct_map.keep_path("B102KEEP")
_P.ensure(_kp)
_kp.write_text(json.dumps({"doc_id": "B102KEEP", "rules": {"x": 1}}, ensure_ascii=False), encoding="utf-8")
_h1 = struct_map.load_kept("B102KEEP", "abc")
_kp.write_text(json.dumps({"doc_id": "B102KEEP", "source_hash": "abc", "rules": {"x": 1}}), encoding="utf-8")
_h2 = struct_map.load_kept("B102KEEP", "abc")
_h3 = struct_map.load_kept("B102KEEP", "zzz")
_kp.unlink(missing_ok=True)
show("ⓗ 원본 해시 없는 보존물은 재사용 0 · 같은 해시면 재사용 · 다르면 0", _h1 is None and _h2 and _h3 is None,
     f"해시 없음 {_h1} · 같음 {bool(_h2)} · 다름 {_h3}")
_setup()
_register("process", DT)
a_dir, b_dir = TMP / "a", TMP / "b"
fa, fb = _xlsx(a_dir / "B102SAME.xlsx"), _xlsx(b_dir / "B102SAME.xlsx")
_made.append("B102SAME")
o1 = _run("ingest-file", str(fa), "--doc-type", DT, "--allow-mock", "--sheets", "1-2:prose")
g0 = sorted(n["id"] for _l, n in World().nodes())
o2 = _run("ingest-file", str(fb), "--doc-type", DT, "--allow-mock", "--sheets", "1-2:prose")
g1 = sorted(n["id"] for _l, n in World().nodes())
src2 = (store.read(store.DOC_REGISTRY, {}).get("B102SAME") or {}).get("source_path")
o3 = _run("ingest-file", str(fb), "--doc-type", DT, "--allow-mock", "--sheets", "1-2:prose", "--revise")
src3 = (store.read(store.DOC_REGISTRY, {}).get("B102SAME") or {}).get("source_path")
# B141 ② — 상태 폴더 안의 파일(기록은 상태 루트 기준 상대)을 작업 폴더 기준 상대 경로로 다시 넣는다
_fr = _P.ensure(_P.raw("B141REL.xlsx"))
_wbr = Workbook()
_wbr.active.title = "이송 유닛"
for _i, _v in enumerate(["1. 구동부", "모터는 리니어 모터를 쓴다."], 1):
    _wbr.active.cell(row=_i, column=1, value=_v)
_wbr.save(_fr)
_made.append("B141REL")
o4 = _run("ingest-file", str(_fr), "--doc-type", DT, "--allow-mock", "--sheets", "1:prose")
src4 = (store.read(store.DOC_REGISTRY, {}).get("B141REL") or {}).get("source_path")
o5 = _run("ingest-file", __import__("os").path.relpath(_fr, ROOT), "--doc-type", DT, "--allow-mock", "--sheets", "1:prose")
_unregister(DT)
show("ⓗ 같은 doc_id · 다른 원본 경로 — 상태 거부 + 다음 줄(이름 변경 · --revise) · 그래프·등록 그대로 / --revise면 개정",
     "[상태] 같은 doc_id(B102SAME)" in o2 and "--revise" in o2 and Path(str(src2)).parent.name == "a"
     and g1 == g0 and "개정 — " in o3 and Path(str(src3)).parent.name == "b",
     " / ".join([l.strip() for l in o2.splitlines() if "[상태]" in l or "--revise" in l][:3])
     + f" · 등록 경로 {src2} → {src3}")
show("B141 ⓑ 경로 — 같은 파일을 작업 폴더 기준 상대 경로로 다시 넣으면 멈추지 않는다(기록은 상태 루트 기준 표기 · 절대 경로와 같은 결과) · "
     "같은 이름의 다른 파일은 위 ⓗ처럼 멈춘다",
     "[성공]" in o4 and not Path(str(src4)).is_absolute() and "[상태]" not in o5 and "[성공]" in o5,
     f"기록 {src4} · 다시 넣은 줄 {[ln.strip()[:80] for ln in o5.splitlines() if '[성공]' in ln or '[상태]' in ln][:1]}")

# ────────────────────────────────────────────────────────────── B140 사람 후보 · 끝점 조회 · 좌표 상속
print("\n■ B140 이름 없는 대상 — [5/8] 예고 · 더하기 · 같은 것 · 다시 · 끝점 조회 · 좌표 상속 · 막기 · 비대화형")
import json as _js                                         # noqa: E402
import os as _os                                           # noqa: E402
import select as _sel                                      # noqa: E402
import signal as _sig                                      # noqa: E402
from core.build import belongs as BL, human as HU, outline as OL   # noqa: E402
from core.build import structure as _STR                   # noqa: E402
from core.state import human_candidates as HC              # noqa: E402
from parser import tuning as _TU                           # noqa: E402
from cli import _screen as _SC                             # noqa: E402
overlay()                                                  # 클린 · 기본 config(덧칠은 품질층 어휘뿐)
_register("process", DT)
(_P.home() / "knobs.json").write_text(_js.dumps({"chunk_rows": [1, 2]}), encoding="utf-8")   # 제목이 경로에 서게(창작 손잡이)
_TU.apply({"chunk_rows": [1, 2]})
HC.path().unlink(missing_ok=True)
#: FWC1 꼴(창작 — 네 벌 C의 표본 꼴) · 「실린더」는 소속 · 관계 끝점으로만 쓰인다
B140_ROWS = ["1. 개요", "센서가 셀 위치를 본다.", "2. 추출부", "추출부는 셀을 꺼낸다.", "2.1 NG unit",
             "모터 회전수는 3000rpm이다.", "실린더 행정은 50mm다."]
B140_OUT = {"2. 추출부": {"name": "추출부", "category": "Unit"}, "2.1 NG unit": {"name": "NG unit", "category": "Unit"}}
B140_WORDS = (("모터 회전수", "Property"), ("실린더 행정", "Property"), ("실린더봉 행정", "Property"), ("실린더 압력", "Property"),
              ("센서", "Unit"), ("모터", "Unit"))


def _b140(did, rows, uses=None, rels=(), coord="노칭"):
    """창작 엑셀 + mock 힌트(추출 · 개요) — `uses` {개체: 소속 이름(카테고리 없음)} · `rels` [(src, rel, dst)]는 그 말이 든 청크에."""
    path = TMP / f"{did}.xlsx"
    wb = Workbook()
    wb.active.title = "사양"
    for r, v in enumerate(rows, 1):
        wb.active.cell(row=r, column=1, value=v)
    wb.save(path)
    struct_map.invalidate(did)
    env = pipeline.parse(BX, did, str(path), sheet_roles={"사양": "prose"}, closed_list=[],
                         structure=_STR.structurer()).envelope
    hints = {}
    for c in env["chunks"]:
        t = c.get("text") or ""
        own = next((x for x in reversed((c.get("meta") or {}).get("structure") or []) if x.get("name")), None)
        words = [(w, k) for w, k in B140_WORDS if w in t]
        words = [(w, k) for w, k in words if not any(w != v and w in v for v, _k in words)]
        ents = []
        for w, k in words:
            bel = ({"name": (uses or {})[w], "category": None, "from": "본문"} if w in (uses or {}) else
                   {"name": own["name"], "category": (B140_OUT.get(own["text"]) or {}).get("category"), "from": "제목"}
                   if own else None)                       # 기대 변경(B148 ② — 사슬에 카테고리 0 · 카테고리는 목차 노드화 힌트)
            ents.append({"surface": w, "category": k, **({"belongs_to": bel} if bel else {})})
        rl = [{"src": a, "rel": r_, "dst": d_} for a, r_, d_ in rels if d_ in t]
        if ents or rl:
            hints[c["source_locator"]] = {"entities": ents, "relations": rl, "attach": []}
    _hint(did, hints)
    _made.append(did)
    (HINTS / f"{did}@outline.json").write_text(_js.dumps(B140_OUT, ensure_ascii=False), encoding="utf-8")
    _made.append(f"{did}@outline")
    return path, ("--coord", coord) if coord else ("--coord", "none")


def _go(path, coord, *extra, answers=None):
    return _run("ingest-file", str(path), "--doc-type", DT, "--allow-mock", "--sheets", "1:prose", *coord, *extra,
                answers=answers)


def _drive(argv, rules):
    """pty 도우미 — 묻는 줄이 뜰 때마다 그 줄의 표지에 맞는 답(`rules` [(표지, [답…])] · 없으면 c) · 끝까지."""
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                                       # pragma: no cover
        _os.environ.update(USE_MOCK="1", COLUMNS="200")
        _os.chdir(str(ROOT))
        _os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv])
    marks = ("[계속 c / 멈춤 q", "[OK o / 위 노드", "번호(Enter", "[OK o / 취소 x]", "[y/N]", "[Y/n]")
    out, used, seen = b"", {}, 0
    while True:
        r_, _w, _x = _sel.select([fd], [], [], 60)
        if not r_:
            _os.kill(pid, _sig.SIGKILL)
            break
        try:
            d_ = _os.read(fd, 4096)
        except OSError:
            break
        if not d_:
            break
        out += d_
        txt = out.decode("utf-8", "replace")
        hits = sorted((m.start(), mk) for mk in marks for m in re.finditer(re.escape(mk), txt))
        while seen < len(hits):
            pos = hits[seen][0]
            line = txt[txt.rfind("\n", 0, pos) + 1:pos + 80]
            ans = "c"
            for mk, q in rules:
                if mk in line:
                    k = used.get(mk, 0)
                    ans, used[mk] = q[min(k, len(q) - 1)], k + 1
                    break
            _os.write(fd, (ans + "\n").encode())
            seen += 1
    _os.waitpid(pid, 0)
    return _SC.strip_ansi(out.decode("utf-8", "replace"))


def _state_print():
    """상태 지문 — 상태 루트 파일마다 (자리, 크기, 바이트 해시)(로그 제외)."""
    import hashlib
    return sorted((str(f.relative_to(_P.home())), hashlib.sha256(f.read_bytes()).hexdigest()[:12])
                  for f in _P.home().rglob("*") if f.is_file() and "logs" not in f.parts)


def _board(did):
    env = _js.loads(_P.parsed(f"{did}.json").read_text(encoding="utf-8"))
    ck = _js.loads(EX.checkpoint_path(did).read_text(encoding="utf-8"))
    l2i = {c["source_locator"]: cid for cid, c in store.read(store.CHUNKS, {"chunks": {}})["chunks"].items()
           if c.get("doc_id") == did}
    from core.state.bootstrap import load_config, open_graph as _og
    return HU.Board(env, ck["candidates"], load_config("process"), _og("process"), "process", l2i, OL.load(did))


def _live_named(canon):
    return [n for _l, n in World().nodes() if n["canonical"] == canon and n.get("status") != "deleted"]


def _edges_of(nid):
    w = World()
    return [(w.get(e["src"])["canonical"], e["rel"], w.get(e["dst"])["canonical"]) for _l, g in w.graphs.items()
            for e in g.edges if nid in (e["src"], e["dst"]) and e.get("status") != "deleted"]


def _orph(did, key):
    return [x for x in store.read(store.QUEUE, []) if x.get("kind") == "orphan_attach" and x.get("doc_id") == did
            and (x.get("payload") or {}).get("key") == key]


# 먼저 넣은 문서(기록 없음) — 「실린더」 고아가 큐에 선다
_pP, _cP = _b140("B140P", [x.replace("셀 위치", "셀 높이") for x in B140_ROWS], {"실린더 행정": "실린더"},   # 다른 문서(같은 내용이면 보류)
                 [("실린더", "has_property", "실린더 행정")])
_go(_pP, _cP)
_pA, _cA = _b140("B140A", B140_ROWS, {"실린더 행정": "실린더"},
                 [("실린더", "has_property", "실린더 행정"), ("유령", "has_property", "모터 회전수")])
_oa0 = _go(_pA, _cA)
_bd = _board("B140A")
_u0, _s0 = gateway.usage_total()["calls"], _state_print()
_rw0, _tl0 = _bd.rows()
_it0 = next((x for x in _rw0 if x["name"] == "실린더"), {})
_up0, _cat0 = _bd.recommend(_it0) if _it0 else (None, None)
_pv0 = _bd.preview(_it0, _up0, _cat0) if _it0 else {}
show("B140 ⓐ 예고 — 「실린더」가 소속 · 관계 · 다른 문서 고아 수와 함께 목록에 · 본문에 없는 이름은 번호 없이 꼬리 · 셈 · 상세 · "
     "미리보기는 상태 지문 전후 같다(쓰기 0 · LLM 0)",
     (_it0.get("소속"), _it0.get("관계"), _it0.get("고아")) == (1, 1, {"B140P": 1}) and _tl0 == {"종": 1, "관계": 1}
     and "1. 실린더 — 소속 1" in _oa0 and "본문에 없는 이름 1종" in _oa0 and _pv0.get("node") == "노칭::실린더"
     and _state_print() == _s0 and gateway.usage_total()["calls"] == _u0,
     f"목록 {[(x['name'], x['소속'], x['관계'], x['고아']) for x in _rw0]} · 꼬리 {_tl0} · 추천 {_up0} · {_cat0} · 미리보기 {_pv0.get('node')}")
_ckb = EX.checkpoint_path("B140A").read_bytes()
_ob = _drive(["ingest-file", str(_pA), "--doc-type", DT, "--allow-mock", "--sheets", "1:prose", *_cA, "--step"],
             [("더하기 n", ["n 1", "c"]), ("[OK o / 위 노드", ["o"])])
_cy = _live_named("노칭::실린더")
_rowA = {r["surface"]: r for r in LG.read("B140A")["rows"] if r.get("role") == "entity"}
_eA = _edges_of(_cy[0]["id"]) if _cy else []
show("B140 ⓑ 더하기 — 관문(pty) n → 상세 → OK → 기록 → [6/8]이 「노칭::실린더」를 고른 위 노드(노칭) 아래 세운다 · 이 문서의 소속 개체가 "
     "그 노드에 붙고(임시 연결 0) 그 이름을 끝점으로 한 관계가 커밋 · 소속 미해소 0",
     [r["kind"] for r in HC.of("B140A")] == [HC.NEW] and _cy and ("노칭::실린더", "part_of", "노칭") in _eA
     # 기대 변경(B145 ① — 소속 미해소로 선 폴백(NG unit)은 근거가 아니고 고아가 기다리는 「실린더」가 근거: 이 문서의 「실린더
     # 행정」(소속 실린더)이 먼저 선 노칭::실린더 행정에 판정 없이 붙는다 · 실린더 아래 하나)
     and ("노칭::실린더", "has_property", "노칭::실린더 행정") in _eA and not _live_named("노칭::실린더::실린더 행정")
     and _rowA.get("실린더 행정", {}).get("path") == "path_compat"
     and not any(str(a.get("path")).startswith("폴백") for a in _rowA.get("실린더 행정", {}).get("attached") or [])
     and _rowA.get("실린더", {}).get("by") == HU.HUMAN and not _orph("B140A", "실린더") and "만들 노드 — 노칭::실린더" in _ob,
     f"기록 {HC.of('B140A')} · 엣지 {_eA} · 고아 {len(_orph('B140A', '실린더'))}")
_pPn = _live_named("노칭::실린더 행정")
show("B140 ⓒ 다른 문서 고아 — 먼저 넣은 문서의 「실린더」 고아가 그 노드를 만든 인입의 마무리 재연결에서 붙는다",
     not _orph("B140P", "실린더") and _pPn and ("노칭::실린더", "has_property", "노칭::실린더 행정") in _edges_of(_pPn[0]["id"])
     and "사람 후보 — 재연결 붙음 1" in _ob,
     f"P 고아 {len(_orph('B140P', '실린더'))} · 마무리 {[ln.strip() for ln in _ob.splitlines() if '재연결 붙음' in ln]}")
_pH, _cH = _b140("B142H", ["1. 구동", "실린더 행정은 60mm다."], {"실린더 행정": "실린더"})
_go(_pH, _cH)
_rH = next((r for r in LG.read("B142H")["rows"] if r.get("surface") == "실린더 행정" and r.get("role") == "entity"), {})
show("B142 ⓗ 재연결로 붙은 자식 — 먼저 넣은 문서의 납작한 「노칭::실린더 행정」(재연결로 실린더에 붙음)에 뒤 문서의 같은 자식이 붙는다"
     "(경로 호환 · 중복 0 · 차례 의존 0)",
     # 기대 변경(B145 ① — 실린더 아래 하나라 뒤 문서의 같은 자식은 재연결된 납작한 노드에 경로 호환으로 붙는다)
     _rH.get("target") == "노칭::실린더 행정" and _rH.get("path") == "path_compat"
     and len(_live_named("노칭::실린더 행정")) == 1 and not _live_named("노칭::실린더::실린더 행정"),
     f"뒤 문서 행 {_rH.get('path')} → {_rH.get('target')}")
_pS, _cS = _b140("B140S", ["1. 구동", "실린더봉 행정은 40mm다."], {"실린더봉 행정": "실린더봉"})
HC.add("B140S", {"kind": HC.SAME, "name": "실린더봉", "target": {"name": "노칭::실린더", "layer": "process", "category": "Unit"}})
_go(_pS, _cS)
from core.state import alias_book as _AB                   # noqa: E402
_sb = str((_AB.AliasBook.open().get("실린더봉", _AB.name(_cy[0])) or {}).get("source")) if _cy else ""
_rS = next((r for r in LG.read("B140S")["rows"] if r.get("surface") == "실린더봉 행정"), {})
_clash = _board("B140A").same_check({"name": "센서"}, {"name": "노칭::실린더", "layer": "process", "category": "Unit"})
show("B140 ⓓ 같은 것 — 별칭이 등재되고(별칭 대장 출처 사람) 그 표기의 고아가 붙는다 · 같은 자리 다른 노드에 붙은 표기는 거부(ops alias와 같은 검사)",
     _sb == "사람" and any(a.get("other") == "노칭::실린더" and str(a.get("path")).startswith("소속")
                          for a in _rS.get("attached") or []) and not _orph("B140S", "실린더봉")
     and "이미 같은 자리의 다른 노드에 붙어 있다" in str(_clash),
     f"대장 출처 {_sb} · 붙은 곳 {_rS.get('attached')} · 거부 {str(_clash)[:60]}")
_g0 = sorted(_edges_of(_cy[0]["id"])) if _cy else []
_mdA = _P.export("split_B140A.md")
_mdA.unlink(missing_ok=True)
_oe = _go(_pA, _cA)
_md1 = _mdA.read_text(encoding="utf-8") if _mdA.exists() else ""
_g1 = sorted(_edges_of(_live_named("노칭::실린더")[0]["id"])) if _live_named("노칭::실린더") else []
_run("rebuild", "--yes")                                   # 재구축 = 기본 fresh(재구축 안) → 문서 대장 차례로 재인입
_g2 = sorted(_edges_of(_live_named("노칭::실린더")[0]["id"])) if _live_named("노칭::실린더") else []
_md2 = _mdA.exists()
_oc = _run("ingest-file", str(_FXR.RAW / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock")
show("B141 ⓐ md — --step 없이 넣은 산문 문서도 구조 확인 md(구조 확인 화면과 같은 함수 · 그 자리 한 줄)가 선다 · 재구축(기본 fresh) 뒤에도 "
     "있다 · 표 문서는 생기지 않는다",
     _md1.startswith("# 구조 확인 — B140A") and "계층 사다리" in _md1 and "구조 확인 md — " in _oe and _md2
     and "[성공]" in _oc and not _P.export("split_CP01.md").exists(),
     f"md {len(_md1)}자 · 재구축 뒤 {_md2} · 표 {_P.export('split_CP01.md').exists()}")
HC.drop("B140A", 1)
_go(_pA, _cA)
_hA = [r for r in LG.read("B140A")["rows"] if r.get("by") == HU.HUMAN]
show("B140 ⓔ 다시 — 같은 문서 재인입은 묻지 않고 기록을 적용해 같은 엣지 · 기본 fresh 뒤 재구축도 같다 · 지우기로 걷으면 다음 인입에서 빠진다",
     _g0 and _g0 == _g1 == _g2 and "사람 기록 1 — 적용" in _oe and "더하기 n" not in _oe and not _hA,
     f"엣지 {len(_g0)} / {len(_g1)} / {len(_g2)} · 걷은 뒤 사람 행 {len(_hA)}")
# 끝점 조회 — 다른 문서가 만든 노드를 끝점으로 · 사전 히트 둘이 좁혀도 둘이면 미해소
from core.state.bootstrap import open_graph as _og2         # noqa: E402
from core.dictionary import Dictionary as _Dc               # noqa: E402
_gp = _og2("process")
_d2 = _Dc.open()
for _par in ("노칭", "노칭::NG unit"):                       # 같은 표기 「브래킷」 둘(창작 — 같은 좌표 아래)
    _bid = _gp.add_node(f"{_par}::브래킷", "Unit", "auto", provenance=["B140 시험"], mirror_scope=_par, polarity="none")
    _d2.register("브래킷", _bid, provenance="B140 시험")
_gp.save()
_d2.save()
_pR, _cR = _b140("B140R", ["1. 구동", "실린더 압력은 5bar다. 브래킷 압력도 같다."], None,
                 [("실린더", "has_property", "실린더 압력"), ("브래킷", "has_property", "실린더 압력")])
_go(_pR, _cR)
_pr = _live_named("노칭::실린더 압력")
_eR = _edges_of(_pr[0]["id"]) if _pr else []
_dfx = _P.work("defects.log").read_text(encoding="utf-8")
show("B140 ⓕ 끝점 조회 — 다른 문서가 만든 「노칭::실린더」를 끝점으로 한 관계가 커밋 · 사전 히트 둘이고 좁혀도 둘이면 지금처럼 미해소(결함)",
     ("노칭::실린더", "has_property", "노칭::실린더 압력") in _eR and not any("브래킷" in a for a, _r, _d in _eR)
     and "B140R: 관계 후보 끝점 미해소 — '브래킷'" in _dfx,
     f"엣지 {_eR}")
_pN, _cN = _b140("B140N", ["1. 구동", "모터는 실린더에 붙는다."], {"모터": "실린더"}, coord=None)
_q0 = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == "B140N" and x.get("kind") == "missing_field"]
_go(_pN, _cN)
_mo = _live_named("노칭::모터")
show("B140 ⓖ 좌표 상속 — 좌표 없는 청크의 개체가 소속 노드(「노칭::실린더」)의 좌표로 선다(전에는 보류 — missing_field)",
     _mo and any("B140N" in p_ for p_ in _mo[0].get("provenance") or [])
     and not [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == "B140N" and x.get("kind") == "missing_field"],
     f"노드 {[n['canonical'] for n in _mo]} · 보류 {len(_q0)}")
_bA = _board("B140A")
_ngu = {"name": "NG unit", "category": "Unit", "kind": "제목 개체"}
show("B140 ⓗ 막기 — 좌표 카테고리는 고를 수 없다 · 매핑 없는 위 노드(NG unit · Unit)는 고를 수 없다(이유) · 추출 체크포인트 바이트 그대로",
     "Process" not in _bA.categories() and "매핑 없음" in str(_bA.why_not(_ngu, "Unit"))
     and EX.checkpoint_path("B140A").read_bytes() == _ckb,
     f"카테고리 {_bA.categories()} · 이유 {_bA.why_not(_ngu, 'Unit')}")
HC.add("B140A", {"kind": HC.NEW, "name": "실린더", "category": "Unit", "upper": {"name": "노칭", "category": "Process", "kind": "골격"}})
_oi = _go(_pA, _cA, "--step")
show("B140 ⓘ 비대화형 — 목록과 안내 줄만(묻지 않는다) · 지난 기록은 적용한다",
     "사람 기록 1 — 적용" in _oi and "더하기 n" not in _oi and [r for r in LG.read("B140A")["rows"] if r.get("by") == HU.HUMAN],
     " / ".join(ln.strip() for ln in _oi.splitlines() if "사람" in ln)[:200])
# ── B145 — 소속을 말했는데 미해소라 선 폴백은 소유자 근거가 아니다(기다리는 이름이 근거) · 말하지 않은 값의 폴백은 근거
B140_WORDS = B140_WORDS + (("토크", "Property"), ("밸브 개도", "Property"))
_gq, _dq = _og2("process"), _Dc.open()
_pu = _gq.add_node("노칭::펌프", "Unit", "auto", provenance=["B145 시험"], scope="노칭", base_name="펌프", polarity="none", _scoped=True)
for _k in ("펌프", "노칭::펌프"):
    _dq.register(_k, _pu, provenance="B145 시험")
_gq.save(), _dq.save()
_go(*_b140("B145P", ["1. 구동", "밸브 개도는 30%다."], {"밸브 개도": "밸브"}))       # 소속 밸브 — 미해소 → 폴백 + 고아
_go(*_b140("B145A", ["1. 구동", "펌프 밸브 개도는 40%다."], {"밸브 개도": "펌프"}))  # 소속 펌프 — 기다리는 이름과 다르다
_rb = next((r for r in LG.read("B145A")["rows"] if r.get("surface") == "밸브 개도" and r.get("role") == "entity"), {})
show("B145 ⓑ 기다리는 이름과 다른 소유자 — 소속 「밸브」를 기다리는 노드에 소속 「펌프」의 같은 이름은 붙지 않는다(소유자 갈림)",
     _rb.get("target") == "노칭::펌프::밸브 개도" and "노칭::밸브 개도" in (_rb.get("apart") or [])
     and len(_live_named("노칭::밸브 개도")) == 1, f"{_rb.get('path')} → {_rb.get('target')} · apart {_rb.get('apart')}")
_pC, _cC = _b140("B145C", B140_ROWS[:5] + ["토크는 5Nm다."])
_hc = _js.loads((HINTS / "B145C.json").read_text(encoding="utf-8"))
for _e in (e for v in _hc.values() for e in v["entities"]):
    _e.pop("belongs_to", None)                         # 소속을 말하지 않은 값 — 위 제목 개체(NG unit)로 폴백
_hint("B145C", _hc)
_go(_pC, _cC)
_go(*_b140("B145D", ["1. 구동", "펌프 토크는 7Nm다."], {"토크": "펌프"}))
_rc = next((r for r in LG.read("B145D")["rows"] if r.get("surface") == "토크" and r.get("role") == "entity"), {})
_fc = next((r for r in LG.read("B145C")["rows"] if r.get("surface") == "토크" and r.get("role") == "entity"), {})
show("B145 ⓒ 소속을 말하지 않은 값의 폴백은 근거 — 제목 개체 아래 폴백된 「토크」에 다른 소유자(펌프) 아래 「토크」는 붙지 않는다",
     any(str(a.get("path")).startswith("폴백(") for a in _fc.get("attached") or [])
     and _rc.get("target") == "노칭::펌프::토크" and len(_live_named("노칭::토크")) == 1,
     f"폴백 {_fc.get('attached')} · {_rc.get('path')} → {_rc.get('target')}")
HC.path().unlink(missing_ok=True)
(_P.home() / "knobs.json").unlink(missing_ok=True)
_TU.apply({})

# ── 정리 — 표본·힌트·등록은 남기지 않는다
for d in set(_made):
    (HINTS / f"{d}.json").unlink(missing_ok=True)
import shutil                                       # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
done()
