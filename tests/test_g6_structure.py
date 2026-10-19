# -*- coding: utf-8 -*-
"""G6 — **구조와 주인** — 시트 구조는 문서마다 LLM이 · 한 유닛 아래 여러 청크 · 소속은 구조 사슬을 보고 · 사람이 고치는 구조 관문 ·
이름은 주인 아래 (B119).

창작 표본으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 실호출 갈래(⑪ 문서 구조 · ① 추출 · ⑫ 연결 보강)는 가짜
게이트웨이(`tests/fake_gateway.Live` — 전송 · 채팅만 대역 · 지시문 · 스키마 · 검사 · 보존은 실물)로 · 구조 관문 · 약한 구조 ·
값 표는 mock 힌트(`<doc>@structure.json` · `<doc>.json`)로 명령 그대로 돈다. 표본 셋(양식이 다르게) × 층 둘(process · quality —
quality는 시험 덧칠의 렌즈 `Unit`):
  ⓐ 번호 붙은 유닛 제목(stacking 꼴) ⓑ 번호 없는 유닛 줄 + 유닛마다 되풀이되는 번호 소제목(TW 꼴 — 고정 규칙은 소제목만 세운다)
  ⓒ 제목이 약하고 유닛 이름이 본문에만(패키징 꼴)
가짜 추출 LLM의 소속 규칙(지시문 「가장 구체적인 주인」의 대역): 그 줄 본문의 `… unit의` → 본문 · 아니면 사슬에서 대상이 선 가장 깊은
줄 → 제목 · 둘 다 없으면 null(한 개체는 지어낸 이름 — 버려져야 한다).

잠그는 성질:
  ⓐ 구조 — ⓑ에서 유닛 줄이 트리에 서고 경로에 든다(`시트 › 유닛 › 지정사양`) · 한 유닛 아래 청크 둘이 같은 유닛 노드 · ⓐ는 고정 규칙과
     같은 트리 · 같은 파일이면 구조 LLM 0 · 검사(목록 밖 줄 · 역할 밖 · 앞에 없는 부모 → 초안 · 글자 밖 이름 · 목록 밖 카테고리 → 대상
     버림 · 호출 실패 → 초안 그대로 · 보존 0)
  ⓑ 소속 — 세 표본 모두 주인이 있는 개체는 그 유닛에 붙는다(유닛 이하 = 주인 있는 개체 수) · 공정으로 가는 것은 주인 없는 개체뿐 ·
     지어낸 이름은 버림(후보 밖 0) · 추출 · 보강 입력에 구조 사슬 · 다른 공정 가드와 부딪힌 구조 유닛을 센다
  ⓒ 관문 — `--step` 구조 표에서 「<번호> 유닛」 → 등록 단 기록 · 다시 파싱(LLM 0) · 그 아래 개체가 그 유닛에 · 재구축이 재생 ·
     약한 구조 신호가 화면 · 인입 기록 · `show summary`에
  ⓓ 이름 — 유닛에 붙은 사양 `공정::유닛::사양`(같은 이름이 유닛마다 다른 노드) · 공정에 붙은 사양 `공정::사양` · 표(CP · PFMEA)는
     `nest_categories`가 있어도 이름이 같다
  ⑤ 화면 — 값 표의 구조 · 소속(출처) · 붙은 자리 칸 = 대장 행
네 벌(ⓔ — 바닥 C에 표본 ⓑ)은 마감 한 줄의 네 벌 단계가 잰다.
"""
from __future__ import annotations

import contextlib
import io
import re
import select
import signal
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done, overlay   # noqa: F401

from fake_gateway import CALLS, Live                    # noqa: E402
from g6_common import _register, _run, _unregister      # noqa: E402
from openpyxl import Workbook                           # noqa: E402
import run as RUN                                       # noqa: E402
from cli import _screen                                 # noqa: E402
from core.build import ledger as LG, outline as OL, reconcile as RC, structure as ST   # noqa: E402
from core.build.entry import finalize, run_document     # noqa: E402
from core.llm import gateway                            # noqa: E402
from core.state.world import World                      # noqa: E402
from parser import pipeline, struct_map, tagger as TG, tuning   # noqa: E402
from parser.adapters import basic_prose_xlsx as BX      # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="b119_"))
HINTS = ROOT / "tests" / "fixtures" / "extract_hints"
LAYERS = ("process", "quality")
#: 층마다 개체 말 다섯(창작) — 앞 넷은 유닛 아래 · 다섯째는 주인 없는 자리 · 여섯째는 지어낸 주인
WORDS = {"process": ("속도", "하중", "장력", "모터 회전수", "검사 주기", "점검 주기"),
         "quality": ("버", "들뜸", "찍힘", "주름", "검사 누락", "점검 누락")}
CAT = {"process": "Property", "quality": "Failure"}
GHOST = "유령 unit"


def _rows_of(key, lay):
    a, b, c, d, e, g = WORDS[lay]
    if key == "A":                         # 번호 붙은 유닛 제목(stacking 꼴) — 넷째 제목은 다른 공정 이름(가드와 부딪힘)
        return ("스태킹 사양", ["1. 개요", f"{e} 기준은 1주다.", f"{g} 기준은 2주다.", "2. 공급 unit", "2.1 기본사양",
                              f"{a} 기준은 60이다.", f"{b} 기준은 3이다.", "2.2 지정사양", f"{c} 기준은 20이다.",
                              "3. 적층 unit", "3.1 기본사양", f"{a} 기준은 40이다.", f"{d} 기준은 2000이다.",
                              "4. 스태킹", "연계 조건은 따로 정한다."])
    if key == "B":                         # 번호 없는 유닛 줄 + 되풀이되는 번호 소제목(TW 꼴)
        return ("TW 사양", ["공통 사항", f"{e} 기준은 1주다.", f"{g} 기준은 2주다.", "언와인더 unit", "1) 기본사양",
                           f"{a} 기준은 100이다.", f"{b} 기준은 5이다.", "2) 지정사양", f"{c} 기준은 30이다.",
                           "리와인더 unit", "1) 기본사양", f"{a} 기준은 80이다.", "2) 지정사양", f"{d} 기준은 20이다."])
    return ("포장 사양", ["포장 사양서", f"포장 unit의 {a} 기준은 30이다.", f"포장 unit의 {b} 기준은 2이다.",
                        f"봉합 unit의 {c} 기준은 180이다.", "기타", f"{e} 기준은 육안이다.", f"{g} 기준은 매일이다."])


#: 문서 구조의 답(창작 — 가짜 LLM이 그대로 낸다) — `(줄 글자, 단, 역할, 대상 이름)`
STRUCT = {"A": [("1. 개요", 1, "주제", None), ("2. 공급 unit", 1, "유닛", "공급 unit"), ("2.1 기본사양", 2, "사양 묶음", None),
                ("2.2 지정사양", 2, "사양 묶음", None), ("3. 적층 unit", 1, "유닛", "적층 unit"),
                ("3.1 기본사양", 2, "사양 묶음", None), ("4. 스태킹", 1, "유닛", "스태킹")],
          "B": [("공통 사항", 1, "주제", None), ("언와인더 unit", 1, "유닛", "언와인더 unit"), ("1) 기본사양", 2, "사양 묶음", None),
                ("2) 지정사양", 2, "사양 묶음", None), ("리와인더 unit", 1, "유닛", "리와인더 unit"),
                ("1) 기본사양", 2, "사양 묶음", None), ("2) 지정사양", 2, "사양 묶음", None)],
          "C": [("포장 사양서", 1, "주제", None), ("기타", 1, "주제", None)]}


def _hint_struct(key, lay):
    return {_rows_of(key, lay)[0]: [{"text": t, "depth": d, "role": r, **({"name": n, "category": "Unit"} if n else {})}
                                    for t, d, r, n in STRUCT[key]]}


def _xlsx(key, lay, did):
    sheet, rows = _rows_of(key, lay)
    p = TMP / f"{did}.xlsx"
    if p.exists():                         # 같은 파일 — 다시 저장하면 바이트(시각)가 바뀌어 원본 해시가 달라진다
        return p, sheet
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(title=sheet)
    for i, v in enumerate(rows, 1):
        ws.cell(row=i, column=1, value=v)
    wb.save(p)
    return p, sheet


def _setup():
    """클린 → 덧칠(quality에 렌즈 `Unit`) → 소속 엣지의 카테고리쌍(층마다) · 문서 종류 둘 · 청크 목표 행 손잡이(작은 표본)."""
    with contextlib.redirect_stdout(io.StringIO()):
        overlay()
    _rw(_P.layers("quality", "config.json"),
        lambda c: c.setdefault("category_pair_map", {}).update({"Failure,Unit": "occurs_in"}))
    for lay in LAYERS:
        with contextlib.redirect_stdout(io.StringIO()):
            bootstrap(lay, echo=False)
        _register(lay, f"b119_{lay}")
    tuning.apply({"chunk_rows": [1, 2]})


# ── 가짜 LLM(창작) — 문서 구조 · 추출 · 연결 보강
ANS = {}


def _structure(body):
    """줄 글자로 답을 찾는다 — 같은 글자가 되풀이되면 차례대로 · 부모는 단으로."""
    out, stack, at = [], [], 0
    lines = body["lines"]
    for t, d, r, n in ANS.get(body["frame"]) or []:
        i = next((j for j in range(at, len(lines)) if lines[j]["text"] == t[:ST.LABEL_CHARS]), None)
        if i is None:
            continue
        at = i + 1
        while stack and stack[-1][0] >= d:
            stack.pop()
        out.append({"row": lines[i]["row"], "parent": stack[-1][1] if stack else None, "role": r,
                    "name": n, "category": ANS["@unit"] if n else None})
        stack.append((d, lines[i]["row"]))
    return {"headings": out}


def _extract(body):
    text = body["chunk"].split("\n", 1)[-1] if body["chunk"].startswith("[") else body["chunk"]
    chain = body.get("structure_chain") or []
    own = next((x for x in reversed(chain) if x.get("name")), None)
    lay = ANS["@layer"]
    ents, units = [], []
    for ln in text.split("\n"):
        m = re.match(r"(\S+ unit)의 ", ln)
        for w in WORDS[lay]:
            if not re.search(rf"(^|의 ){re.escape(w)} 기준", ln):
                continue
            if w == WORDS[lay][5]:
                bel = {"name": GHOST, "category": ANS["@unit"], "from": "본문"}     # 지어낸 이름 — 버려져야 한다
            elif m:
                bel = {"name": m.group(1), "category": ANS["@unit"], "from": "본문"}
                if m.group(1) not in units:
                    units.append(m.group(1))
            elif own:
                bel = {"name": own["name"], "category": own["category"], "from": "제목"}
            else:
                bel = None
            ents.append({"surface": w, "category": CAT[lay], "parent": None, "belongs_to": bel})
    ents = [{"surface": u, "category": ANS["@unit"], "parent": None, "belongs_to": None} for u in units] + ents
    return {"entities": ents, "relations": [], "about": []}


def _ingest_live(key, lay, did, again=False):
    """가짜 게이트웨이로 파싱(문서 구조 주입) → 인입 → 마무리. 돌려주는 것은 `(봉투, 호출 기록)`."""
    path, sheet = _xlsx(key, lay, did)
    ANS.clear()
    ANS.update({sheet: STRUCT[key], "@unit": "Unit", "@layer": lay})
    with Live(by={"structure": _structure, "extract": _extract, "reinforce": lambda b: {"pick": None}}):
        res = pipeline.parse(BX, did, str(path), closed_list=TG.closed_list("process"), doc_coord="노칭",
                             sheet_roles={sheet: "prose"}, structure=ST.structurer([lay]),
                             structure_fixes=ST.fixes_of(did))
        env = res.envelope
        env["doc_type"] = f"b119_{lay}"
        for c in env["chunks"]:
            c["doc_type"] = env["doc_type"]
        if not again:
            with contextlib.redirect_stdout(io.StringIO()):
                run_document(env)
                finalize()
        calls = list(CALLS)
    return env, res, calls


def _rows(did, role="entity"):
    return [r for r in (LG.read(did) or {}).get("rows") or [] if r.get("role") == role]


def _attached(r):
    return [(a["path"], a["other"]) for a in r.get("attached") or []]


def _mt(did):
    """그 문서의 맞춤표 — `show report`와 같은 함수(장부만)."""
    return RC.for_report(did, LG.read(did) or {})


# ────────────────────────────────────────────────────────────── ⓐ ⓑ ⓓ — 실호출 갈래(가짜 게이트웨이)
print("\n■ ⓐ 구조 · ⓑ 소속 · ⓓ 이름 — 표본 셋 × 층 둘 (실호출 갈래 · 가짜 게이트웨이)")
RES = {}
for lay in LAYERS:
    _setup()
    for key in "ABC":
        did = f"B119{key}{lay[0].upper()}"
        env, res, calls = _ingest_live(key, lay, did)
        ents = _rows(did)
        RES[(key, lay)] = {"env": env, "res": res, "calls": calls, "ents": ents, "heads": _rows(did, "heading"),
                           "nodes": {n["canonical"]: n for _l, n in World().nodes()}, "mt": _mt(did),
                           "clash": RC.guard_clashes(OL.load(did), _rows(did, "heading"))}
    # 같은 파일 다시 — 구조 LLM 0 (보존분 재사용)
    for key in "ABC":
        did = f"B119{key}{lay[0].upper()}"
        _e2, _r2, calls2 = _ingest_live(key, lay, did, again=True)
        RES[(key, lay)]["again"] = sum(1 for p, _b in calls2 if p == "structure")
        RES[(key, lay)]["again_same"] = [c["source_locator"] for c in _e2["chunks"]] == \
            [c["source_locator"] for c in RES[(key, lay)]["env"]["chunks"]]
    RES[("defects", lay)] = store.path(store.DEFECTS).read_text(encoding="utf-8") if store.path(store.DEFECTS).exists() else ""

_oa1 = []
for lay in LAYERS:
    r = RES[("B", lay)]
    paths = [c["section"] for c in r["env"]["chunks"]]
    under = {u: [c for c in r["env"]["chunks"] if c["section"].startswith(u + " > ")] for u in ("언와인더 unit", "리와인더 unit")}
    owners = {}
    for e in r["ents"]:
        for path, other in _attached(e):
            if path.startswith("소속"):
                owners.setdefault(other, set()).add(e["locator"])
    two = all(len(v) >= 2 for v in under.values()) and all(
        len(owners.get(f"노칭::{u}", set())) >= 2 for u in under)
    single = all(sum(1 for n in r["nodes"] if n == f"노칭::{u}") == 1 for u in under)
    _oa1.append((lay, "언와인더 unit > 2) 지정사양" in paths and two and single,
                 f"{lay}: 경로 {paths} · 유닛별 조각 {[len(v) for v in under.values()]} · 붙은 조각 "
                 f"{ {k: len(v) for k, v in owners.items()} }"))
show("ⓐ 표본 ⓑ — 번호 없는 유닛 줄이 트리에 서고 경로에 든다(`… › 유닛 › 2) 지정사양`) · 한 유닛 아래 청크 둘이 같은 유닛 노드 (층 둘)",
     all(o for _l, o, _d in _oa1), " ‖ ".join(d for _l, _o, d in _oa1))

_oa2 = []
for lay in LAYERS:
    did = f"B119A{lay[0].upper()}"
    path, sheet = _xlsx("A", lay, did + "X")
    plain = pipeline.parse(BX, did + "X", str(path), closed_list=[], sheet_roles={sheet: "prose"}).envelope
    a = [(c["source_locator"], c["section"]) for c in RES[("A", lay)]["env"]["chunks"]]
    b = [(c["source_locator"], c["section"]) for c in plain["chunks"]]
    _oa2.append((lay, a == b, f"{lay}: 구조 {len(a)} 조각 · 고정 규칙 {len(b)} 조각 · 같음 {a == b}"))
show("ⓐ 표본 ⓐ(번호 붙은 유닛) — 구조를 세워도 고정 규칙과 같은 트리(조각 위치 · 경로 같다) (층 둘)",
     all(o for _l, o, _d in _oa2), " ‖ ".join(d for _l, _o, d in _oa2))

_oa3 = [(f"{k}·{lay}", RES[(k, lay)]["again"] == 0 and RES[(k, lay)]["again_same"]
         and sum(1 for p, _b in RES[(k, lay)]["calls"] if p == "structure") >= 1) for lay in LAYERS for k in "ABC"]
show("ⓐ 같은 파일을 다시 넣으면 구조 LLM 0(보존분 · 같은 조각) — 처음은 시트마다 1회 이상 (표본 셋 × 층 둘)",
     all(o for _k, o in _oa3), str(_oa3) + " · " + str([(k, lay, RES[(k, lay)]["again"], RES[(k, lay)]["again_same"])
                                                     for lay in LAYERS for k in "ABC"]))

# 검사 — 결정적 규칙(목록 밖 줄 · 역할 밖 · 앞에 없는 부모 → 초안 · 글자 밖 이름 · 목록 밖 카테고리 → 대상 버림)
_labs = [{"row": 0, "text": "S", "marks": ["시트"], "draft": 0}, {"row": 1, "text": "1. 개요", "marks": [], "draft": 1},
         {"row": 2, "text": "언와인더 unit", "marks": [], "draft": 0}, {"row": 3, "text": "속도는 1이다.", "marks": [], "draft": 0},
         {"row": 4, "text": "2. 이송 unit", "marks": [], "draft": 1}]
_ans = [{"row": 1, "parent": None, "role": "주제", "name": None, "category": None},
        {"row": 2, "parent": 1, "role": "유닛", "name": "없는 unit", "category": "Unit"},
        {"row": 4, "parent": 9, "role": "유닛", "name": "이송 unit", "category": "Unit"},
        {"row": 3, "parent": None, "role": "몰라", "name": None, "category": None},
        {"row": 77, "parent": None, "role": "주제", "name": None, "category": None},
        {"row": 0, "parent": None, "role": "유닛", "name": "S", "category": "Mystery"}]
_heads, _drop = ST.check("B119CHK", "S", _labs, _ans, {"Unit": "정의"})
_by = {h["row"]: h for h in _heads}
with Live(by={"structure": lambda b: (_ for _ in ()).throw(gateway.GatewayError(500, "가짜 실패", "fake"))}):
    _fail = ST.structurer(["process"])("B119FAIL", "S", _labs)
show("ⓐ 검사 — 목록 밖 줄 · 역할 밖 · 앞에 없는 부모는 그 줄만 초안으로 · 글자 밖 이름 · 목록 밖 카테고리는 대상만 버림(역할 그대로) · "
     "호출 실패는 시트 전체 초안(보존 0)",
     set(_by) == {0, 1, 2, 4} and _by[2]["role"] == "유닛" and _by[2]["name"] is None and _by[4].get("draft")
     and _by[4]["role"] is None and _by[0]["name"] is None and 3 not in _by
     and sorted(d["row"] for d in _drop) == [0, 2, 3, 4, 77]
     and _fail.get("failed") and [h["row"] for h in _fail["headings"]] == [1, 4] and _fail["calls"] == 1,
     f"제목 {sorted(_by)} · 버림 {[(d['row'], d['why'][:14]) for d in _drop]} · 실패 → {[h['row'] for h in _fail['headings']]}")

# ⓑ 소속
_ob1, RATIO = [], {}
for lay in LAYERS:
    for key in "ABC":
        r = RES[(key, lay)]
        did = f"B119{key}{lay[0].upper()}"
        owned = [e for e in r["ents"] if e.get("belongs_to") and e.get("belongs_to") != GHOST
                 and e["surface"] in WORDS[lay][:4]]
        good = all(any(p.startswith("소속") and o.endswith(e["belongs_to"]) for p, o in _attached(e)) for e in owned)
        s = r["mt"]["요약"]
        RATIO[(key, lay)] = (s["유닛 이하 비율"], s["유닛 이하"], s["소속"])
        _ob1.append((f"{key}·{lay}", good and owned and s["유닛 이하"] == len(owned),
                     f"{key}·{lay} 주인 있는 개체 {len(owned)} · 유닛 이하 {s['유닛 이하']}/{s['소속']}({s['유닛 이하 비율']}%)"))
show("ⓑ 세 표본 모두 — 주인(사슬 · 본문)이 있는 개체는 그 유닛에 소속 엣지로 붙는다 · 유닛 이하 = 주인 있는 개체 수 (표본 셋 × 층 둘)",
     all(o for _k, o, _d in _ob1), " ‖ ".join(d for _k, _o, d in _ob1))

_ob2 = []
for lay in LAYERS:
    for key in "ABC":
        r = RES[(key, lay)]
        to_proc = sorted(e["surface"] for e in r["ents"] if e["surface"] in WORDS[lay]
                         and not any("::" in o for _p, o in _attached(e)))       # 유닛(골격 밖 노드)에 붙지 않은 것
        ghost = [e for e in r["ents"] if any(GHOST in o for _p, o in _attached(e))]
        _ob2.append((f"{key}·{lay}", to_proc == sorted(WORDS[lay][4:6]) and not ghost
                     and all(o == "노칭" for e in r["ents"] if e["surface"] in to_proc for _p, o in _attached(e))
                     and f"'{GHOST}'" in RES[("defects", lay)],
                     f"{key}·{lay} 공정으로 {to_proc} · 지어낸 소속에 붙은 것 {len(ghost)}"))
show("ⓑ 유닛에 붙지 않는 것(공정으로 · 또는 엣지 0)은 사슬 · 본문에 주인이 없는 개체뿐(지어낸 소속은 버리고 결함 로그 — 후보 밖 이름에 "
     "붙은 것 0) (표본 셋 × 층 둘)",
     all(o for _k, o, _d in _ob2), " ‖ ".join(d for _k, _o, d in _ob2))

_ob3 = []
for lay in LAYERS:
    bodies = [b for p, b in RES[("B", lay)]["calls"] if p == "extract"]
    ch = next((b.get("structure_chain") for b in bodies if WORDS[lay][2] + " 기준" in b["chunk"]), None)
    tail = [x for x in ch or [] if x.get("role")]                     # 맨 위는 시트(역할 없음 — 시트가 대상이 아닐 때)
    _ob3.append((lay, ch and ch[0]["text"] == "TW 사양" and [x["role"] for x in tail] == ["유닛", "사양 묶음"]
                 and tail[0].get("name") == "언와인더 unit" and tail[1]["text"] == "2) 지정사양", f"{lay}: {ch}"))
show("ⓑ 추출 입력에 구조 사슬(그 청크 위의 제목 줄 — 역할 · 글자 · 대상 · 위에서 아래로) (층 둘)",
     all(o for _l, o, _d in _ob3), " ‖ ".join(d for _l, _o, d in _ob3))

_clash = {lay: RES[("A", lay)]["clash"] for lay in LAYERS}       # 그 층의 실행 안에서 잰 것(다음 층의 클린 전)
_line_a = RC.summary_text("B119AP", RES[("A", "process")]["mt"]["요약"])
show("ⓑ 다른 공정 가드와 부딪힌 구조 유닛을 센다(「4. 스태킹」 — 노드 0 · 관련 링크) · 한 줄 요약에 「구조 · 가드 부딪힘」 (층 둘)",
     all(len(v) == 1 and "스태킹" in v[0] for v in _clash.values()) and "구조 · 가드 부딪힘 1" in _line_a,
     f"{_clash} · {_line_a[-60:]}")

# ⓓ 이름
_np = RES[("A", "process")]["nodes"]
_nb = RES[("B", "process")]["nodes"]
_nc = RES[("C", "process")]["nodes"]
show("ⓓ 유닛에 붙은 사양은 `공정::유닛::사양`(같은 이름이 유닛마다 다른 노드) · 공정에 붙은 사양은 `공정::사양` (표본 셋 · process)",
     {"노칭::공급 unit::속도", "노칭::적층 unit::속도", "노칭::공급 unit::하중"} <= set(_np) and "노칭::검사 주기" in _np
     and {"노칭::언와인더 unit::속도", "노칭::리와인더 unit::속도"} <= set(_nb) and "노칭::포장 unit::속도" in _nc
     and "노칭::속도" not in set(_np) | set(_nb) | set(_nc),
     " · ".join(sorted(n for n in set(_np) | set(_nb) | set(_nc) if n.endswith("속도") or n.endswith("검사 주기"))))


def _table_names(nest):
    with contextlib.redirect_stdout(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
        if not nest:
            _rw(_P.common(), lambda c: c["canonical_scope"].pop("nest_categories", None))
        for d in ("CP01", "PFMEA01"):
            run_document(load(d))
    return sorted(n["canonical"] for _l, n in World().nodes() if n.get("status") == "auto")


_tn1, _tn0 = _table_names(True), _table_names(False)
show("ⓓ 표(CP01 · PFMEA01)의 이름 · 병합 키 — `nest_categories`가 있어도 없을 때와 같다(표는 소속이 공정)",
     _tn1 == _tn0 and _tn1, f"auto 노드 {len(_tn1)} · 같음 {_tn1 == _tn0}")

# ────────────────────────────────────────────────────────────── ⓒ 관문 · 약한 구조 · ⑤ 화면 — 명령 그대로(mock 힌트)
print("\n■ ⓒ 구조 관문 · 약한 구조 · ⑤ 값 표 칸 — 명령 그대로 (mock 힌트)")
PROMPT = "[계속 c / 멈춤 q".encode("utf-8")


def _drive(argv, answers, wait=25):
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                                     # pragma: no cover
        os.environ.update(USE_MOCK="1", COLUMNS="200")
        os.chdir(str(ROOT))
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv])
    out, sent = b"", 0
    while True:
        try:
            r, _w, _x = select.select([fd], [], [], wait)
        except InterruptedError:
            continue
        if not r:
            os.kill(pid, signal.SIGKILL)
            break
        try:
            d = os.read(fd, 4096)
        except OSError:
            break
        if not d:
            break
        out += d
        while sent < out.count(PROMPT) and sent < len(answers):
            os.write(fd, answers[sent])
            sent += 1
    os.waitpid(pid, 0)
    return _screen.strip_ansi(out.decode("utf-8", "replace")), sent


GATE = ("설비 사양", ["설비 사양", "공급부", "속도 기준은 50이다.", "적층부", "하중 기준은 3이다."])
GATE_ST = [{"text": "설비 사양", "depth": 1, "role": "주제"}, {"text": "공급부", "depth": 2, "role": "주제"},
           {"text": "적층부", "depth": 2, "role": "유닛", "name": "적층부", "category": "Unit"}]
_made = []


def _mock_doc(did, sheet, rows, struct, words, belongs=True):
    """mock 힌트 둘(구조 · 추출)과 엑셀 — 추출 힌트는 지금 구조로 자른 조각의 위치로(소속 = 사슬의 가장 깊은 대상)."""
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(title=sheet)
    for i, v in enumerate(rows, 1):
        ws.cell(row=i, column=1, value=v)
    p = TMP / f"{did}.xlsx"
    wb.save(p)
    (HINTS / f"{did}@structure.json").write_text(json.dumps({sheet: struct}, ensure_ascii=False), encoding="utf-8")
    env = pipeline.parse(BX, did, str(p), closed_list=[], sheet_roles={sheet: "prose"},
                         structure=ST.structurer(["process"])).envelope
    hints = {}
    for c in env["chunks"]:
        own = next((x for x in reversed(c["meta"].get("structure") or []) if x.get("name")), None)
        ents = [{"surface": w, "category": "Property",
                 "belongs_to": ({"name": own["name"], "category": own["category"], "from": "제목"} if own and belongs else None)}
                for w in words if w + " 기준" in c["text"]]
        if ents:
            hints[c["source_locator"]] = {"entities": ents, "relations": [], "attach": []}
    (HINTS / f"{did}.json").write_text(json.dumps(hints, ensure_ascii=False), encoding="utf-8")
    struct_map.invalidate(did)
    _made.append(did)
    return p


def _att_of(did, surface):
    return [o for e in _rows(did) if e["surface"] == surface for _p, o in _attached(e)]


with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register("process", "b119_process")
tuning.apply({"chunk_rows": [1, 2]})
ST.fixes_path().unlink(missing_ok=True)                 # 등록 단(사람의 고침)은 클린이 남긴다 — 시험 몫을 치운다
_gp = _mock_doc("B119GATE", GATE[0], GATE[1], GATE_ST, ("속도", "하중"), belongs=False)
_argv = ["ingest-file", str(_gp), "--doc-type", "b119_process", "--allow-mock", "--coord", "노칭", "--sheets", "1:prose"]
_before = _run(*_argv)
_b_att = _att_of("B119GATE", "속도")
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_out, _sent = _drive(_argv + ["--step"], [b"c\n", "2 유닛\n".encode(), b"c\n"] + [b"c\n"] * 12)
_fx = ST.fixes_of("B119GATE")
_a_att = _att_of("B119GATE", "속도")
show("ⓒ `--step` 구조 표에서 「2 유닛」 — 등록 단 기록(역할 · 줄 글자 이름 · 같은 역할의 카테고리) · 다시 파싱(LLM 0) · 그 아래 개체가 "
     "그 유닛에 붙는다(고치기 전에는 공정)",
     "고침 — 설비 사양 2행 → 유닛 '공급부'(Unit)" in _out and _fx.get(GATE[0], {}).get(2, {}).get("role") == "유닛"
     and "노칭::공급부" in _a_att and "노칭::공급부" not in _b_att and "노칭" in _b_att and "[성공]" in _out,
     f"고치기 전 {_b_att} · 고친 뒤 {_a_att} · 기록 {_fx}")
_rb = _run("rebuild", "--yes", "--allow-mock")
show("ⓒ 재구축이 사람의 구조 고침을 재생 — 같은 붙음(기록은 등록 단이라 기본 fresh가 남긴다)",
     _att_of("B119GATE", "속도") == _a_att and ST.fixes_of("B119GATE") == _fx, f"재구축 뒤 {_att_of('B119GATE', '속도')}")

with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_wp = _mock_doc("B119WEAK", *_rows_of("C", "process"), [{"text": t, "depth": d, "role": r} for t, d, r, _n in STRUCT["C"]],
                WORDS["process"][:3])
_wout = _run("ingest-file", str(_wp), "--doc-type", "b119_process", "--allow-mock", "--coord", "노칭", "--sheets", "1:prose")
_reg = store.read(store.DOC_REGISTRY, {}).get("B119WEAK") or {}
_sum = _run("show", "summary")
show("ⓒ 약한 구조 신호(설비 · 유닛 0) — 화면에 크게 · 비대화형은 진행하고 인입 기록 · `show summary`에 남는다",
     "[약한 구조] 시트 '포장 사양' — 설비 · 유닛 0(제목 2)" in _wout and "[성공]" in _wout
     and (_reg.get("structure") or {}).get("약한", {}).get("포장 사양")
     and re.search(r"약한 구조\s+문서 1 · 시트 1", _sum),
     " / ".join(ln.strip() for ln in (_wout + _sum).splitlines() if "약한 구조" in ln)[:300])

with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_vp = _mock_doc("B119VIEW", *_rows_of("B", "process"), _hint_struct("B", "process")["TW 사양"], WORDS["process"][:4])
_cols = os.environ.get("COLUMNS")
os.environ["COLUMNS"] = "220"                            # 칸이 잘리지 않는 폭에서 칸 = 대장을 잰다(잘림은 B118 ⓒ가 잰다)
_vout = _run("ingest-file", str(_vp), "--doc-type", "b119_process", "--allow-mock", "--coord", "노칭", "--sheets",
             "1:prose", "-v")
if _cols is None:
    os.environ.pop("COLUMNS", None)
else:
    os.environ["COLUMNS"] = _cols
_vrows = [ln.split(" | ") for ln in _vout.splitlines() if re.match(r"\s+[✓+?✗·] \| ", ln)]
_led = {e.get("target"): e for e in _rows("B119VIEW")}       # 같은 표기가 유닛마다 — 붙은 노드로 맞춘다
_ok5 = []
for cells in _vrows:
    nm = cells[4].strip().split(" → ")[-1]
    e = _led.get(nm)
    if not e:
        continue
    full_b = f"{e['belongs_to']}(사슬)"
    full_a = f"{e['attached'][0]['dir']} {e['attached'][0]['other']}({e['attached'][0]['path']})"
    _ok5.append((cells[3].strip() == "사양 묶음" and full_b.startswith(cells[9].strip().rstrip("…"))
                 and full_a.startswith(cells[10].strip().rstrip("…")) and len(cells[10].strip()) > 3,
                 [c.strip() for c in cells[3:11]], full_b, full_a))
show("⑤ 값 표 — 구조 칸(가장 가까운 제목 줄의 역할) · 소속(출처) 칸 = 대장 belongs_to(사슬) · 붙은 자리 칸 = 대장 attached (산문 · -v)",
     len(_ok5) >= 4 and all(o for o, *_r in _ok5), f"행 {len(_ok5)} · {[x for x in _ok5 if not x[0]][:2] or _ok5[:1]}")

# ── 정리
ST.fixes_path().unlink(missing_ok=True)
for _d in _made:
    for _p in (HINTS / f"{_d}.json", HINTS / f"{_d}@structure.json"):
        _p.unlink(missing_ok=True)
for lay in LAYERS:
    _unregister(f"b119_{lay}")
shutil.rmtree(TMP, ignore_errors=True)
print("\n   표본별 유닛 이하 비율(창작 표본 — 근거가 아니다): "
      + " · ".join(f"{k}·{lay} {v[0]}%({v[1]}/{v[2]})" for (k, lay), v in sorted(RATIO.items())))
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
done()
