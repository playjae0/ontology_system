# -*- coding: utf-8 -*-
"""G6 ㉕ 상위 개념으로 잇기 — 문서 개요 · 제목 개체 · 상위로 올라가는 소속 · 연결 보강 (B115).

창작 표본으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 실호출 갈래(지점 ⑪ 개요 · ① 추출 · ⑫ 연결 보강)는
가짜 게이트웨이(`tests/fake_gateway.Live` — 전송 · 채팅만 대역 · 지시문 · 스키마 · 대조 · 체크포인트는 실물)로 돈다.
형태(표 · 산문) × 층(process · quality) + 포맷(엑셀 산문 · Word · PPT)에서 같은 성질을 잰다(CLAUDE.md §4). 제목 ·
카테고리 · 관계 이름은 데이터다(코드 분기 0). 청크 목표 행은 사내 손잡이 `chunk_rows`로 작게 잡는다(작은 창작 표본에서
제목 2~3단이 구획 경로에 실리게).

잠그는 성질:
  ⓐ 개요: 제목 2~3단에 유닛 · 주제가 섞인 문서 ⇒ 대상 제목만 노드(대장 `heading` 행) · 주제는 노드 0 · 제목에 없는 이름 ·
     닫힌 목록 밖 카테고리는 버림(결함 로그) · 같은 제목 계층이면 개요 재사용(LLM 0) · 추출 입력에 조상 제목 개체(가까운 것부터)
  ⓑ 상위로: 본문에 소속이 없는 청크의 개체가 가장 가까운 제목 개체에(`… › 2.1 NG unit` — NG unit이 대상이면 거기 ·
     주제면 추출부 · 둘 다 아니면 공정) · 대장 `폴백(제목 n단)` · 맞춤 「부착」 `제목 폴백` · 소속 이름이 제목 개체면 「소속
     대상」 `제목 개체` (층 둘)
  ⓒ 연결 보강: 재연결 뒤 엣지 없는(층 quality) · 공정에만 붙은(층 process) 개체가 후보 안에서 근거 문장과 함께 붙는다 ·
     후보 밖 id · 원문에 없는 근거는 버린다 · 재구축(기본 fresh → 다시 넣기)에서 재생(LLM 0 — 추출 · 개요 · 보강 호출 0)
  ⓓ 엑셀 · Word · PPT가 같은 함수(PPT는 슬라이드 제목 · 구획이 개요) · 표 문서는 제목이 없어 개요 0
  B148 ⓓ 골격 이름 제목(문서 좌표 「노칭」 · 제목 「노칭 타발」)은 목차 노드화에 묻지 않고 골격 노드 — 새 노드 0 · 그 아래 개체가 그 골격
     노드에 · 다른 공정 이름 제목(「스태킹」)은 가드 그대로(개요 = 목차 노드화 — B148 ② 용어)
  B150 ⓑ 골격 이름 제목 아래 조각은 그 골격 노드로 좌표를 내린다 — 이름이 표(process_ref = 그 노드)와 같은 노드 · 더 깊은 자기
     좌표는 그대로
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done, overlay   # noqa: F401

import make_b88 as MB                                   # noqa: E402 — Word 조립 재료(창작)
from fake_gateway import CALLS, Live                    # noqa: E402
from g6_common import _register, _unregister            # noqa: E402
from openpyxl import Workbook                           # noqa: E402
from core.build import ledger as LG, outline as OL, reconcile as RC, reinforce as RF   # noqa: E402
from core.state.world import World                      # noqa: E402
from parser import pipeline, struct_map, tagger as TG, tuning   # noqa: E402
from parser.adapters import basic_docx as DX, basic_ppt as PX, basic_prose_xlsx as BX   # noqa: E402

TMP = Path(__import__("tempfile").mkdtemp(prefix="b115_"))
XL = {"추출 사양": ["1. 개요", "본 사양은 추출 설비의 범위를 정한다.", "2. 추출부", "추출부는 셀을 꺼낸다.",
                  "2.1 NG unit", "모터는 서보 모터를 쓴다.", "실린더는 공압 실린더를 쓴다.", "2.2 일정", "3월에 납품한다.",
                  "4월에 시운전한다.",
                  "3. 이송부", "벨트는 평벨트를 쓴다. 벨트는 추출부의 셀을 옮긴다. 롤러는 고무 롤러다. 가이드는 강판이다.",
                  "4. 품질 이력", "버는 NG unit 배출부에서 생긴다."]}


def _setup():
    """덧칠(Component · 겸 렌즈) + `nest_categories` + 소속 엣지의 카테고리쌍 — 상태 루트에만(B102 시험과 같은 바닥) ·
    청크 목표 행 손잡이(작은 표본에서 제목 2~3단)."""
    overlay(component=True)
    _rw(_P.common(), lambda c: c.setdefault("canonical_scope", {}).__setitem__("nest_categories", ["Component"]))
    pats = [{"src": s_, "rel": "part_of", "dst": d_, "symmetric": False, "정의문": f"{s_}가 {d_}에 속한다"}
            for s_, d_ in (("Component", "Unit"), ("Component", "Process"), ("Unit", "Process"))]
    pairs = {f"{p_['src']},{p_['dst']}": "part_of" for p_ in pats}

    def _q(c):
        c["categories"]["Component"] = "(품질층의 렌즈) 불량이 일어나는 구성 기계"
        c["relation_patterns"] += pats
        c.setdefault("category_pair_map", {}).update(pairs)

    def _p(c):
        have = {(p_["src"], p_["rel"], p_["dst"]) for p_ in c["relation_patterns"]}
        c["relation_patterns"] += [p_ for p_ in pats if (p_["src"], p_["rel"], p_["dst"]) not in have]
        for k, v in pairs.items():
            c.setdefault("category_pair_map", {}).setdefault(k, v)
    _rw(_P.layers("quality", "config.json"), _q)
    _rw(_P.layers("process", "config.json"), _p)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
        _register(lay, f"b115_{lay}")           # 실호출 갈래는 mock 내장 doc_type을 모른다 — 등록 단에 세운다
    tuning.apply({"chunk_rows": [1, 2]})


def _xlsx(path, sheets=None):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in (sheets or XL).items():
        ws = wb.create_sheet(title=name)
        for r, v in enumerate(rows, 1):
            ws.cell(row=r, column=1, value=v)
    _P.ensure(path)
    wb.save(path)
    return path


def _docx(path):
    body = "".join([MB._p("추출부", "1"), MB._p("추출부는 셀을 꺼낸다."), MB._p("NG unit", "2"),
                    MB._p("모터는 서보 모터를 쓴다."), MB._p("실린더는 공압 실린더를 쓴다."), MB._p("일정", "2"),
                    MB._p("3월에 납품한다."), MB._p("이송부", "1"), MB._p("벨트는 평벨트를 쓴다.")])
    _P.ensure(path)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", MB._CT)
        z.writestr("_rels/.rels", MB._ROOT_RELS)
        z.writestr("word/document.xml", MB._doc(body))
        z.writestr("word/styles.xml", MB._STYLES)
        z.writestr("word/_rels/document.xml.rels", MB._rels([("rIdSty", "styles", "styles.xml")]))
    return path


def _pptx(path):
    from pptx import Presentation
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text, s.placeholders[1].text = "추출 설비 사양", "B115 창작"
    s = prs.slides.add_slide(prs.slide_layouts[2])
    s.shapes.title.text = "추출부"
    try:
        s.slide_layout.name = "Section Header"
    except Exception:                                    # noqa: BLE001
        pass
    for title, text in (("NG unit", "모터는 서보 모터를 쓴다."), ("일정", "3월에 납품한다.")):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text, s.placeholders[1].text = title, text
    _P.ensure(path)
    prs.save(path)
    return path


FILES = {"엑셀": (BX, _xlsx(TMP / "B115_추출_사양.xlsx")), "Word": (DX, _docx(TMP / "B115_추출_설명.docx")),
         "PPT": (PX, _pptx(TMP / "B115_추출_발표.pptx"))}


def _env(form, doc_id, lay):
    ad, path = FILES[form]
    struct_map.invalidate(doc_id)
    kw = {"sheet_roles": {n: "prose" for n in XL}} if form == "엑셀" else {}
    env = pipeline.parse(ad, doc_id, str(path), closed_list=TG.closed_list("process"), doc_coord="노칭", **kw).envelope
    env["doc_type"] = f"b115_{lay}"
    for c in env["chunks"]:
        c["doc_type"] = env["doc_type"]
    return env


# ── 가짜 LLM의 답(창작) — 개요 · 추출 · 연결 보강
OUT = {}             # 제목 글자 → 대상
BEL = {}             # 개체 표기 → 소속(없으면 null)
REIN = {}            # 개체 이름 → (후보 이름 또는 "밖", 근거 문장, 관계)
WORDS = (("모터", "Component"), ("실린더", "Component"), ("벨트", "Component"), ("롤러", "Component"),
         ("가이드", "Component"), ("버", "Failure"))


def _outline(body):
    # 기대 변경(B148 ② — 목차 노드화의 입력은 메타 목차 `toc[{id, path, text, parent, depth, role, name, chunks, body_lines}]` ·
    # 답은 `headings[{id, role, name, category}]` — 메타가 역할을 정한 제목은 그 역할 · 이름 그대로 · 카테고리만)
    out = []
    for h in body["toc"]:
        t = OUT.get(h["text"])
        out.append({"id": h["id"], "role": h.get("role") or ("대상" if t else "주제"),
                    "name": h.get("name") or (t or {}).get("name"), "category": (t or {}).get("category")})
    return {"headings": out}


def _extract(body):
    text = body["chunk"].split("\n", 1)[-1] if body["chunk"].startswith("[") else body["chunk"]
    ents = [{"surface": w, "category": c, "parent": None, "belongs_to": BEL.get(w)}
            for w, c in WORDS if w in text and c in body["categories"]]
    return {"entities": ents, "relations": [], "about": []}


def _reinforce(body):
    want = REIN.get(body["entity"]["name"].split("::")[-1])
    if not want:
        return {"pick": None}
    name, ev, rel = want
    cid = next((c["id"] for c in body["candidates"] if c["name"].split("::")[-1] == name), "c999")
    return {"pick": {"id": cid, "rel": rel, "evidence": ev}}


def _live():
    return Live(by={"outline": _outline, "extract": _extract, "reinforce": _reinforce})


def _run(env, outline=None, belongs=None, rein=None, fin=True):
    OUT.clear(), BEL.clear(), REIN.clear()
    OUT.update(outline or {}), BEL.update(belongs or {}), REIN.update(rein or {})
    notes = []
    with _live():
        run_document(env, notice=notes.append)
        if fin:
            finalize()
        calls = list(CALLS)
    return notes, calls


def _rows(doc_id, role="entity"):
    return [r for r in (LG.read(doc_id) or {}).get("rows") or [] if r.get("role") == role]


def _att(doc_id, surface):
    r = next((r for r in _rows(doc_id) if r["surface"] == surface), {})
    return [(a["path"], a["other"]) for a in r.get("attached") or []]


def _cell(mt, label, cell):
    ln = next(x for x in mt["줄"] if x["줄"].startswith(label))
    return dict((k, n) for k, n, _d in ln["칸"]).get(cell), ln["맞음"]


def _end(notes):
    return next(n for n in notes if n.get("단계") == "끝")["맞춤"]


def _live_names():
    return {n["canonical"] for _l, n in World().nodes() if ops.is_live(n)}


def _edges():
    """근거가 있는 엣지 전부 — `(관계, src canonical, dst canonical)` 정렬(층 전부)."""
    w = World()
    return sorted((e["rel"], w.get(e["src"])["canonical"], w.get(e["dst"])["canonical"])
                  for g in w.graphs.values() for e in g.edges if e.get("provenance"))


UNITS = {"2. 추출부": {"name": "추출부", "category": "Unit"}, "2.1 NG unit": {"name": "NG unit", "category": "Unit"}}

# ────────────────────────────────────────────────────────────── ⓐ
print("\n■ B115 ① 문서 개요 — 대상 제목만 노드 · 주제 0 · 지어낸 이름 0 · 재사용 (산문 × 층 둘)")
_oa = []
for _lay in ("process", "quality"):
    _setup()
    _did = f"B115A{_lay[0].upper()}"
    _e = _env("엑셀", _did, _lay)
    _notes, _calls = _run(_e, {**UNITS, "2.2 일정": {"name": "배출 유닛", "category": "Unit"},
                               "1. 개요": {"name": "개요", "category": "Mystery"}})
    _hr = _rows(_did, "heading")
    _ck = OL.load(_did) or {}
    _drop = sorted(h["text"] for h in _ck.get("headings") or [] if h.get("dropped"))
    _names = _live_names()
    _dp = store.path(store.DEFECTS)
    _defects = _dp.read_text(encoding="utf-8") if _dp.exists() else ""
    _xin = [b.get("heading_candidates") for p, b in _calls if p == "extract" and "모터" in b["chunk"]]
    with _live():
        _again = OL.run(_e, load_config(_lay))
        _re_calls = [p for p, _b in CALLS if p == "outline"]
    _oa.append((_lay, sorted(r["surface"] for r in _hr if r.get("node_id")) == ["NG unit", "추출부"]
                and not {"노칭::배출 유닛", "개요", "노칭::개요", "일정", "노칭::일정"} & _names
                and _drop == ["1. 개요", "2.2 일정"] and "제목에 없는 이름 '배출 유닛'" in _defects
                and "닫힌 목록 밖 카테고리 'Mystery'" in _defects
                and [p for p, _b in _calls].count("outline") == 1 and not _re_calls
                and [t["name"] for t in (_xin[0] if _xin else [])] == ["NG unit", "추출부"]
                and [h["target"]["name"] for h in _again["headings"] if h.get("target")] == ["추출부", "NG unit"],
                f"{_lay}: 제목 개체 {sorted(r['surface'] for r in _hr if r.get('node_id'))} · 버림 {_drop} · 개요 호출 "
                f"{[p for p, _b in _calls].count('outline')} → 다시 {len(_re_calls)} · 추출 입력 제목 개체 "
                f"{[t['name'] for t in (_xin[0] if _xin else [])]}"))
show("ⓐ 대상 제목만 노드(대장 heading) · 주제 노드 0 · 제목에 없는 이름 · 목록 밖 카테고리 버림(결함 로그) · 개요 1회 → 같은 "
     "제목이면 재사용(LLM 0) · 추출 입력에 조상 제목 개체(가까운 것부터) (층 둘)",
     all(o for _l, o, _d in _oa), " ‖ ".join(d for _l, _o, d in _oa))

# ────────────────────────────────────────────────────────────── ⓑ
print("\n■ B115 ③ 상위로 올라가는 폴백 사슬 — NG unit → 추출부 → 공정 (층 둘)")
_ob = []
for _lay in ("process", "quality"):
    _got = {}
    for _tag, _ans in (("둘 다", UNITS), ("추출부만", {"2. 추출부": UNITS["2. 추출부"]}), ("없음", {})):
        _setup()
        _did = f"B115B{_lay[0].upper()}{len(_got)}"
        _notes, _calls = _run(_env("엑셀", _did, _lay), _ans,
                              {"실린더": {"name": "NG unit", "category": "Unit", "from": "제목"}} if _ans else {})
        _mt = _end(_notes)
        _got[_tag] = (_att(_did, "모터"), _att(_did, "실린더"), _cell(_mt, "부착(개체 행)", "제목 폴백"),
                      _cell(_mt, "소속 대상", "제목 개체"))
    _a, _b, _c = _got["둘 다"], _got["추출부만"], _got["없음"]
    _ob.append((_lay, _a[0] == [("폴백(제목 3단)", "노칭::NG unit")] and _b[0] == [("폴백(제목 2단)", "노칭::추출부")]
                and _c[0] == [("폴백", "노칭")] and _a[1] == [("소속(제목)", "노칭::NG unit")]
                and _a[2] == (1, True) and _a[3] == (1, True) and _c[2][0] in (0, None),
                f"{_lay}: 모터 {_a[0]} / {_b[0]} / {_c[0]} · 실린더 {_a[1]} · 맞춤 제목 폴백 {_a[2]} · 소속 제목 개체 {_a[3]}"))
show("ⓑ 본문에 소속 없는 개체 — NG unit이 대상이면 거기(제목 3단) · 주제면 추출부(2단) · 둘 다 아니면 공정(좌표 폴백) · 소속 "
     "이름이 제목 개체면 그것 · 맞춤 「제목 폴백」·「제목 개체」 칸 (층 둘)",
     all(o for _l, o, _d in _ob), " ‖ ".join(d for _l, _o, d in _ob))

# ────────────────────────────────────────────────────────────── ⓒ
print("\n■ B115 ④ 연결 보강 — 후보 안 · 근거 문장 · 버림 · 재구축 재생 (층 둘)")
_oc = []
_RE = {"벨트": ("추출부", "벨트는 추출부의 셀을 옮긴다.", None), "롤러": ("밖", "롤러는 고무 롤러다.", None),
       "가이드": ("추출부", "가이드는 추출부에 붙는다.", None), "버": ("NG unit", "버는 NG unit 배출부에서 생긴다.", "occurs_in")}
for _lay in ("process", "quality"):
    _setup()
    _did = f"B115C{_lay[0].upper()}"
    _e = _env("엑셀", _did, _lay)
    _notes, _calls = _run(_e, UNITS, rein=_RE)
    _lk = {r["surface"]: r for r in _rows(_did, "link")}
    _first = {k: (v["verdict"], v.get("target"), v.get("evidence")) for k, v in _lk.items()}
    _edges1 = _edges()
    init.init(fresh_=True)                               # 시험 대상: 기본 fresh — 재구축의 바닥(대장 · 추출 · 개요는 남는다)
    for _l2 in ("process", "quality"):
        bootstrap(_l2, echo=False)
    tuning.apply({"chunk_rows": [1, 2]})
    _n2, _c2 = _run(_e, UNITS, rein={})                 # 답을 비워도 재생이 같은 연결을 되살린다
    _lk2 = {r["surface"]: r for r in _rows(_did, "link")}
    _edges2 = _edges()
    _want = "벨트" if _lay == "process" else "버"
    _oc.append((_lay, _first.get(_want, ("",))[0] == "attached" and _first.get("롤러", ("",))[0] == "gate_reject"
                and _first.get("가이드", ("",))[0] == "gate_reject"
                and not [p for p, _b in _c2 if p in ("extract", "outline", "reinforce")]
                and _lk2.get(_want, {}).get("path") == "replay" and _lk2[_want]["verdict"] == "attached"
                and _edges1 == _edges2,
                f"{_lay}: 1회 {_first} · 재구축 호출 {sorted({p for p, _b in _c2})} · 재생 "
                f"{(_lk2.get(_want) or {}).get('path')} · 엣지 같음 {_edges1 == _edges2}"))
show("ⓒ 엣지 없는(quality) · 공정에만 붙은(process) 개체가 후보 안에서 근거 문장과 함께 붙는다 · 후보 밖 id · 원문에 없는 근거는 "
     "버림 · 재구축(기본 fresh → 다시 넣기)은 추출 · 개요 · 보강 호출 0으로 같은 연결 (층 둘)",
     all(o for _l, o, _d in _oc), " ‖ ".join(d for _l, _o, d in _oc))

# B147 ④ — 마무리 화면의 LLM 사용 갈래별 한 줄(끝 표 함수 `usage_table("(마무리)")` 그대로) · 합 = 그 구간 호출 수
import contextlib as _cl147                                   # noqa: E402
import io as _io147                                           # noqa: E402
import re as _re147                                           # noqa: E402
from cli import ingest as _IG147                              # noqa: E402
from core.llm import gateway as _GW147                        # noqa: E402


class _LiveU(Live):
    """보강 시험의 주입 그대로 + 게이트웨이 누계에 한 번 센다(가짜 게이트웨이는 `chat`을 바꿔 누계를 거치지 않는다)."""

    def chat(self, messages, json_schema=None, point=None, **kw):
        out = super().chat(messages, json_schema=json_schema, point=point, **kw)
        _GW147._account(point, {"usage": {"prompt_tokens": 10, "completion_tokens": 2}})
        return out


_setup()
OUT.clear(), BEL.clear(), REIN.clear()
OUT.update(UNITS), REIN.update(_RE)
_u0147 = sum(o["calls"] for o in _GW147.usage_table(doc_id="(마무리)"))
with _LiveU(by={"outline": _outline, "extract": _extract, "reinforce": _reinforce}):
    run_document(_env("엑셀", "B147D", "process"), notice=[].append)
    _n0147, _buf147 = len(CALLS), _io147.StringIO()
    with _cl147.redirect_stdout(_buf147):
        _IG147._finalize_screen()
    _n1147 = len(CALLS)
_ln147 = [ln.strip() for ln in _buf147.getvalue().splitlines() if ln.strip().startswith("LLM 마무리 · ")]
_sum147 = sum(int(_re147.search(r"호출 ([\d,]+)", ln).group(1).replace(",", "")) for ln in _ln147)
show("ⓓ 마무리 화면 — 미러 · 재시도 · 연결 보강 줄 아래 LLM 사용 갈래별 한 줄 · 합 = 그 구간 호출 수(끝 표 함수 그대로)",
     _u0147 == 0 and _ln147 and _n1147 > _n0147 and _sum147 == _n1147 - _n0147,
     f"{_ln147} · 구간 호출 {_n1147 - _n0147}")
_GW147.set_doc(None)

# 상한 — 사내 손잡이 `reinforce_call_cap`(실행당 호출) · mock 선별 규칙이 없으면 판정 없음(호출 0 · 행 0)
_setup()
_P.knobs().write_text(json.dumps({"reinforce_call_cap": 1, "chunk_rows": [1, 2]}), encoding="utf-8")
_P.reset()                                               # 루트를 다시 정하며 손잡이를 다시 읽는다
_n3, _c3 = _run(_env("엑셀", "B115CK", "process"), UNITS, rein=_RE)
_cap = dict(RF.LAST)
_P.knobs().unlink()
_P.reset()
_setup()                                                 # 클린 — 앞 실행의 같은 표기 노드(이미 붙은 것)를 물지 않게
_em = _env("엑셀", "B115CM", "process")                 # mock — 추출 힌트(벨트 하나) · 개요 힌트 없음 · 선별 규칙 없음
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
_HINT = _FXR.EXTRACT_HINTS / "B115CM.json"
_HINT.write_text(json.dumps({c["source_locator"]: {"entities": [{"surface": "벨트", "category": "Component"}],
                                                   "relations": [], "attach": []}
                             for c in _em["chunks"] if "벨트" in c["text"]}, ensure_ascii=False), encoding="utf-8")
try:
    run_document(_em)
    finalize()
finally:
    _HINT.unlink()
show("ⓒ 상한 — 손잡이 reinforce_call_cap 1이면 호출 1 · 나머지는 「상한 밖」(조용한 절단 0) · mock은 선별 규칙이 없으면 판정 없음 "
     "(호출 0 · 대장 link 행 0 · 개요도 힌트 없으면 체크포인트 0)",
     [p for p, _b in _c3].count("reinforce") == 1 and _cap["호출"] == 1 and _cap["상한 밖"] >= 1
     and not _rows("B115CM", "link") and RF.LAST["판정 없음"] >= 1 and OL.load("B115CM") is None,
     f"상한 {_cap} · mock {dict(RF.LAST)}")

# ────────────────────────────────────────────────────────────── ⓓ
print("\n■ B115 ⓓ 포맷 — 엑셀 · Word · PPT 같은 함수 · 표는 개요 0")
_od = []
for _form, _ans, _depth in (("Word", {"추출부": UNITS["2. 추출부"], "NG unit": UNITS["2.1 NG unit"]}, 2),
                            ("PPT", {"추출부": UNITS["2. 추출부"], "NG unit": UNITS["2.1 NG unit"]}, 3)):
    _setup()
    _did = f"B115D{_form[0]}"
    _e = _env(_form, _did, "process")
    _tree = [h["path"] for h in OL.tree(_e)["headings"]]
    _notes, _calls = _run(_e, _ans)
    _od.append((_form, _att(_did, "모터") == [(f"폴백(제목 {_depth}단)", "노칭::NG unit")]
                and sorted(r["surface"] for r in _rows(_did, "heading") if r.get("node_id")) == ["NG unit", "추출부"],
                f"{_form}: 제목 {_tree} · 모터 {_att(_did, '모터')}"))
_setup()
_cp = {**TABLE, "doc_id": "B115DT", "records": [dict(CPREC, source_locator="DT-R1")]}
run_document(_cp)                                        # 표 — mock 내장 doc_type(제목 계층 없음)
_od.append(("표", OL.tree(_cp)["headings"] == [] and not _rows("B115DT", "heading") and _rows("B115DT")
            and OL.load("B115DT") is None, f"표: 제목 {OL.tree(_cp)['headings']} · 제목 개체 행 {len(_rows('B115DT', 'heading'))}"))
show("ⓓ Word(제목 스타일) · PPT(덱 › 구획 › 슬라이드 제목)도 같은 함수 — 개요가 대상으로 정한 제목에 붙는다 · 표 문서는 제목 "
     "계층이 없어 개요 · 제목 개체 0", all(o for _f, o, _d in _od), " ‖ ".join(d for _f, _o, d in _od))

# ────────────────────────────────────────────────────────────── B148 ② 골격 이름 제목
print("\n■ B148 ② 골격 이름 제목 — 좌표로(묻지 않는다 · 새 노드 0) · 다른 공정은 가드 그대로")
_XD = {"노칭 사양": ["1. 노칭 타발", "모터는 서보 모터를 쓴다.", "2. 스태킹", "벨트는 평벨트를 쓴다."]}
_setup()
struct_map.invalidate("B148D")
_ed = pipeline.parse(BX, "B148D", str(_xlsx(TMP / "B148_노칭.xlsx", _XD)), closed_list=TG.closed_list("process"),
                     doc_coord="노칭", sheet_roles={"노칭 사양": "prose"}).envelope
_ed["doc_type"] = "b115_process"
for _c in _ed["chunks"]:
    _c["doc_type"] = _ed["doc_type"]
_nodes0 = {n["id"] for _l, n in World().nodes()}
_nd, _cd = _run(_ed, {})                                 # 목차 노드화의 답 비움 — 골격 이름 제목은 묻지 않는다
_asked = [h["text"] for p, b in _cd if p == "outline" for h in b["toc"]]
_new = sorted(n["canonical"] for _l, n in World().nodes() if n["id"] not in _nodes0 and ops.is_live(n))
_hd = {r["surface"]: r.get("node_id") for r in _rows("B148D", "heading")}
_clash = RC.guard_clashes(OL.load("B148D"), _rows("B148D", "heading"))
_mo = _att("B148D", "모터")
# 기대 변경(B150 ② — 그 아래 개체는 골격 노드로 내린 좌표로 이름을 짓는다(「노칭::노칭 타발::모터」) · 제목 자신의 새 노드만 0이다)
# 기대 변경(B157 ① — 줄기 밖 공정 이름 제목 「2. 스태킹」은 그 구간의 공정 좌표 · 제목도 그 골격 노드에 앉는다(가드 부딪힘 0))
show("ⓓ 문서 좌표 「노칭」 산문의 제목 「노칭 타발」(골격 자식 단) — 목차 노드화에 묻지 않고 골격 노드로(새 노드 0 · 제목 개체 = 골격 "
     "노드) · 그 아래 개체가 그 골격 노드에 붙는다 · 「스태킹」(줄기 밖 공정)도 그 골격 노드로(부딪힘 0 · 아래 개체는 스태킹 아래)",
     "1. 노칭 타발" not in _asked and "2. 스태킹" not in _asked and not [n for n in _new if n.split("::")[-1] in ("노칭 타발", "스태킹")]
     and _hd.get("노칭 타발") and _hd.get("스태킹") and len(_mo) == 1 and _mo[0][1].endswith("노칭 타발")
     and _mo[0][0].startswith("폴백(제목") and not _clash and "스태킹::벨트" in _new,
     f"물은 제목 {_asked} · 새 노드 {_new} · 제목 개체 {_hd} · 모터 {_mo} · 부딪힘 {_clash}")

# ────────────────────────────────────────────────────────────── B150 ② 골격 이름 제목 아래 조각 좌표 하강
print("\n■ B150 ② 골격 이름 제목 아래 조각은 그 골격 노드로 좌표를 내린다 — 표와 같은 노드 · 더 깊은 자기 좌표는 그대로")
WORDS += (("모터 회전수", "Property"), ("금형 수명", "Property"))


def _prose150(doc_id, coord, rows, own=None):
    struct_map.invalidate(doc_id)
    env = pipeline.parse(BX, doc_id, str(_xlsx(TMP / f"{doc_id}.xlsx", {"사양": rows})), closed_list=TG.closed_list("process"),
                         doc_coord=coord, sheet_roles={"사양": "prose"}).envelope
    env["doc_type"] = "b115_process"
    for c in env["chunks"]:
        c["doc_type"] = env["doc_type"]
        if own and own[0] in (c.get("text") or ""):      # 그 조각의 자기 좌표(좌표 태깅이 세운 것과 같은 꼴)
            c["process_ref"], c["meta"] = own[1], {**(c.get("meta") or {}), "coord_from_doc": False}
    _run(env, {})
    return {r["surface"]: r for r in _rows(doc_id)}


_setup()
_pr = _prose150("B150P", "노칭", ["1. 노칭 타발", "모터 회전수는 3000rpm이다."])
run_document({**TABLE, "doc_id": "B150T", "records": [dict(CPREC, source_locator="B150T-R1", process_ref="노칭 타발",
                                                            관리항목="모터 회전수")]})
_tr = {r["surface"]: r for r in _rows("B150T")}
_setup()
_dp = _prose150("B150K", "조립", ["1. 노칭", "금형 수명은 10만 타다."], own=("금형 수명", "노칭 타발"))
_m, _t, _k = _pr.get("모터 회전수") or {}, _tr.get("모터 회전수") or {}, _dp.get("금형 수명") or {}
show("ⓑ 문서 좌표 「노칭」 · 제목 「1. 노칭 타발」 아래 「모터 회전수」 → 「노칭::노칭 타발::모터 회전수」 · 같은 항목의 표 행(process_ref "
     "노칭 타발)과 같은 노드 · 조각이 더 깊은 자기 좌표(「1. 노칭」 아래 「노칭 타발」)면 그대로",
     _m.get("target") == "노칭::노칭 타발::모터 회전수" and _m.get("node_id") and _m.get("node_id") == _t.get("node_id")
     and _k.get("target") == "노칭::노칭 타발::금형 수명",
     f"산문 {_m.get('target')} {_m.get('node_id')} · 표 {_t.get('target')} {_t.get('node_id')} · 자기 좌표 {_k.get('target')}")

for _lay in ("process", "quality"):
    _unregister(f"b115_{_lay}")                          # 등록 단은 클린이 남긴다 — 다음 스위트가 보지 않게 치운다
done()
