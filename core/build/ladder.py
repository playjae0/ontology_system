# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **계층 사다리(문서당 1) · 골격 보기 · 시트 확인(시트당 1)** — LLM은 규칙을 정하고 확인한다 · 코드는 재료 · 적용 · 검사 (B132 ③⑤).

    사다리   입력 = 문서의 앞부분(사슬이 가장 깊이 내려간 첫 대목의 골격 보기 · 길어도 `FRONT_ROWS`행) + 문서 전체 서명 통계 + 코드 사다리 +
             문서 맥락 + 층 힌트 + 문서 힌트 — **줄 전문 0** · 출력 = 단마다 서명 · 역할 · 카테고리 + 번호 없는 제목의 규칙
    시트 확인 입력 = 그 시트의 골격 보기(제목 줄은 앞 `HEAD_CHARS`자 + 「…총 n자」 · 서명 · 깊이 · 시작 열 · 역할 · 본문은 접는다 · 판단
             필요 행은 이유와 앞뒤 `NEAR`줄) + 사다리 + 문서 힌트 · 출력 = 판단 필요 행마다 답(빠짐없이) + 고침(B126 여섯 동사) + 사다리 고침
    검사     서명은 그 문서에 있는 것 · 역할은 셋 · 카테고리는 닫힌 목록 · 조건은 닫힌 목록 — **어긋난 칸만** 버린다(결함 로그)

mock — 사다리는 힌트 `<doc_id>@ladder.json` · 시트 확인은 `<doc_id>@structure.json`의 그 시트(`{answers, edits, rules}` 또는 나무
`[{text, depth, role, name?, category?}]` — 나무는 지금 목차에 대한 고침으로 바꿔 쓴다) · 없으면 판정 없음(사다리는 코드 사다리).
"""
from __future__ import annotations

import json

from core.llm import gateway
from core.state import log, store
from parser import ladder as PL
from parser import sig as SG
from parser.struct_rule import FRAME_ROW, ROLES, TARGET_ROLES

_LOG = log.get(__name__)

#: 지시문 이름(`prompts/2.4_ladder.md` — 사다리 · 시트 확인 · 판이 따로 · 개요 · 덱은 `3.3_outline.md`)
PROMPT = "ladder"
#: 골격 보기의 제목 줄 앞부분 글자 · 판단 필요 행의 앞뒤 줄 수 · 사다리 입력의 앞부분 행 수(창작 기본값)
HEAD_CHARS = 40
NEAR = 2
FRONT_ROWS = 60

_ROLE = {"type": ["string", "null"], "enum": list(ROLES) + [None]}
LADDER_SCHEMA = {
    "type": "object",
    "properties": {
        "levels": {"type": "array", "items": {
            "type": "object",
            "properties": {"sigs": {"type": "array", "items": {"type": "string"}}, "role": _ROLE,
                           "category": {"type": ["string", "null"]}, "rows": {"type": "array", "items": {"type": "integer"}},
                           "why": {"type": "string"}},
            "required": ["sigs", "role", "category", "rows", "why"], "additionalProperties": False}},
        "unnumbered": {"type": "array", "items": {
            "type": "object",
            "properties": {"when": {"type": "array", "items": {"type": "string"}}, "level": {"type": "integer"},
                           "role": _ROLE, "category": {"type": ["string", "null"]}, "why": {"type": "string"}},
            "required": ["when", "level", "role", "category", "why"], "additionalProperties": False}}},
    "required": ["levels", "unnumbered"], "additionalProperties": False,
}


def check_schema():
    from core.build.structure_edit import EDIT_SCHEMA
    return {"type": "object",
            "properties": {
                "answers": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"row": {"type": "integer"}, "heading": {"type": "boolean"},
                                   "parent": {"type": ["integer", "null"]}, "role": _ROLE,
                                   "name": {"type": ["string", "null"]}, "category": {"type": ["string", "null"]},
                                   "why": {"type": "string"}},
                    "required": ["row", "heading", "parent", "role", "name", "category", "why"],
                    "additionalProperties": False}},
                "edits": EDIT_SCHEMA["properties"]["edits"], "rules": EDIT_SCHEMA["properties"]["rules"]},
            "required": ["answers", "edits", "rules"], "additionalProperties": False}


# ---------------------------------------------------------------- 골격 보기 (코드 — 줄 전문 0)
def _depth_of(heads):
    d = {}
    for h in heads:
        p = h.get("parent")
        d[h["row"]] = d.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1
    return d


def _head(x):
    t = str(x.get("text") or "").strip()
    return t[:HEAD_CHARS] + (f"…총 {len(t)}자" if len(t) > HEAD_CHARS else "")


def skeleton(labs, heads, needs, lo=None, hi=None):
    """그 시트의 **골격 보기** — 제목 줄 · 판단 필요 행(이유 · 앞뒤 `NEAR`줄) · 접힌 본문(`R40~R52 본문 13줄`) · `lo`~`hi` 행만."""
    rows = [x for x in labs if x["row"] != FRAME_ROW and (lo is None or lo <= x["row"]) and (hi is None or x["row"] <= hi)]
    head = {h["row"]: h for h in heads}
    need = {n["row"]: n for n in needs}
    toc = _depth_of(heads)
    near = {r for n in need for i, x in enumerate(rows) if x["row"] == n
            for r in (y["row"] for y in rows[max(0, i - NEAR):i + NEAR + 1])}
    out, body = [], []

    def flush():
        if body:
            out.append({"kind": "본문", "rows": f"R{body[0]}~R{body[-1]}" if len(body) > 1 else f"R{body[0]}", "n": len(body)})
            body.clear()
    for x in rows:
        r = x["row"]
        base = {"row": r, "sig": x.get("sig"), "head": _head(x), "depth": x.get("depth") or 0, "col": x.get("col"),
                **({"marks": x["marks"]} if x.get("marks") else {})}
        at = {"toc": toc.get(r), "parent": head[r].get("parent"), "role": head[r].get("role")} if r in head else {}
        if r in need:                                       # 판단 필요가 먼저 — 제목으로 선 줄이어도 이유를 단다
            flush()
            out.append({"kind": "판단 필요", **base, **at, "need": need[r]["kind"], "why": need[r]["why"]})
        elif r in head:
            flush()
            out.append({"kind": "제목", **base, **at})
        elif r in near:
            flush()
            out.append({"kind": "앞뒤", **base})
        else:
            body.append(r)
    flush()
    return out


def front(frames, built):
    """사다리 입력의 **앞부분** — 사슬이 가장 깊이 내려간 첫 대목(그 제목의 맨 위 조상 줄부터 · 길어도 `FRONT_ROWS`행)의 골격 보기."""
    best = None
    for name, labs in frames.items():
        heads = (built.get(name) or {}).get("headings") or []
        for r, d in _depth_of(heads).items():
            if best is None or d > best[0]:
                best = (d, name, r, heads)
    if best is None:
        name = next(iter(frames), None)
        return {"frame": name, "skeleton": skeleton(frames[name][:FRONT_ROWS + 1], [], []) if name else []}
    _d, name, r, heads = best
    parent = {h["row"]: h.get("parent") for h in heads}
    top = r
    while parent.get(top) not in (None, FRAME_ROW):
        top = parent[top]
    rows = [x["row"] for x in frames[name] if x["row"] != FRAME_ROW]
    i = rows.index(top) if top in rows else 0
    j = min(len(rows), max(rows.index(r) + 10 if r in rows else i + FRONT_ROWS, i + 1))
    span = rows[i:min(j, i + FRONT_ROWS)]
    needs = (built.get(name) or {}).get("needs") or []
    return {"frame": name, "skeleton": skeleton(frames[name], heads, needs, span[0], span[-1]) if span else []}


# ---------------------------------------------------------------- 사다리 — 호출 · mock · 검사
def ask_ladder(frames, built, code, cats, cfgs=None, ctx=None, hints=None):
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(PROMPT, cfgs or {}, "structure")},
         {"role": "user", "content": json.dumps(
             {"task": "ladder", "categories": cats, "context": ctx or {}, "front": front(frames, built),
              "stats": PL.stats(frames), "code_ladder": code, "hints": list(hints or [])}, ensure_ascii=False)}],
        json_schema=LADDER_SCHEMA, point="structure")
    return out or {}


def hint_ladder(doc_id):
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@ladder.json"
    if not p.exists():
        return None
    gateway.mock("structure", f"힌트(사다리) {p.name}")
    return json.loads(p.read_text(encoding="utf-8"))


def _when_ok(w):
    w = str(w)
    return w in PL.WHEN or w.startswith("깊이 ") or w.startswith("시작 열 ")


def check_ladder(doc_id, raw, frames, cats):
    """사다리 답의 검사 — `(사다리 또는 None, 버림 [사유])` · 서명은 그 문서에 있는 것 · 한 서명은 한 단 · 역할 셋 · 카테고리 목록 ·
    조건 닫힌 목록 — 어긋난 칸만 버린다(남은 단 · 규칙이 0이면 None → 코드 사다리 · 번호 없는 문서는 규칙만으로 선다)."""
    have = {x["sig"] for labs in frames.values() for x in labs if x.get("sig")}
    used, levels, bad = set(), [], []

    def drop(why):
        store.append_defect(f"{doc_id}: 계층 사다리 — {why}")
        bad.append(why)
    for lv in (raw or {}).get("levels") or []:
        if not isinstance(lv, dict):
            continue
        sigs = []
        for s in lv.get("sigs") or []:
            if s not in have:
                drop(f"문서에 없는 서명 '{s}'")
            elif s in used:
                drop(f"서명 '{s}'이 두 단에 있다(앞 단만)")
            else:
                sigs.append(s)
                used.add(s)
        if not sigs:
            continue
        role = lv.get("role") if lv.get("role") in ROLES else None
        if lv.get("role") not in (None, *ROLES):
            drop(f"역할 밖 '{lv.get('role')}'")
        cat = lv.get("category") if role in TARGET_ROLES else None
        if cat is not None and cat not in cats:
            drop(f"닫힌 목록 밖 카테고리 '{cat}'")
            cat = None
        levels.append({"sigs": sigs, "role": role, "category": cat, "why": str(lv.get("why") or "")[:200],
                       "rows": [r for r in lv.get("rows") or [] if isinstance(r, int)][:6]})
    rules = []
    for u in (raw or {}).get("unnumbered") or []:
        if not isinstance(u, dict) or not u.get("when") or not all(_when_ok(w) for w in u["when"]) \
                or not isinstance(u.get("level"), int) or not 0 <= u["level"] <= len(levels) \
                or u.get("role") not in (None, *ROLES):
            drop(f"번호 없는 제목 규칙 버림 {json.dumps(u, ensure_ascii=False)[:120]}")
            continue
        cat = u.get("category") if u.get("role") in TARGET_ROLES and u.get("category") in cats else None
        rules.append({"when": [str(w) for w in u["when"]], "level": u["level"], "role": u.get("role"), "category": cat,
                      "why": str(u.get("why") or "")[:200]})
    if not levels and not rules:
        return None, bad
    return {"levels": levels, "unnumbered": rules}, bad


def fix_ladder(ladder, rules, cats):
    """**사다리 고침**(시트 확인 · 사람 힌트의 규칙 `{shape, role, category, parent_shape, said}` — `shape` = 서명) — 새 사다리 · 결정적.

    그 서명의 단에 역할 · 카테고리를 건다(단에 서명이 여럿이면 그 서명만 떼어 같은 자리에 새 단) · `parent_shape`가 오면 그 서명을
    그 서명 단의 바로 아래 단으로 옮긴다 · 사다리에 없는 서명은 맨 아래(또는 부모 서명 아래)에 새 단으로 · 닫힌 목록 밖은 버린다."""
    levels = [dict(lv, sigs=list(lv.get("sigs") or [])) for lv in (ladder or {}).get("levels") or []]
    for rule in rules or []:
        s, psh = rule.get("shape"), rule.get("parent_shape")
        role = rule.get("role") if rule.get("role") in ROLES else None
        cat = rule.get("category") if role in TARGET_ROLES and rule.get("category") in cats else None
        if not s:
            continue
        at = next((i for i, lv in enumerate(levels) if s in lv["sigs"]), None)
        if at is not None:
            levels[at]["sigs"].remove(s)
            if not levels[at]["sigs"]:
                levels.pop(at)
            else:
                at += 1
        pi = next((i for i, lv in enumerate(levels) if psh in lv["sigs"]), None) if psh else None
        where = pi + 1 if pi is not None else (at if at is not None else len(levels))
        levels.insert(min(where, len(levels)), {"sigs": [s], "role": role, "category": cat,
                                                "why": str(rule.get("said") or "사람 힌트")[:200], "rows": [], "by": "고침"})
    return {**(ladder or {}), "levels": levels}


# ---------------------------------------------------------------- 시트 확인 — 호출 · mock · 답을 고침으로
def ask_check(frame, labs, built, ladder, cats, cfgs=None, ctx=None, hints=None, prev=None):
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(PROMPT, cfgs or {}, "structure")},
         {"role": "user", "content": json.dumps(
             {"task": "check", "categories": cats, "frame": frame, "context": ctx or {}, "ladder": ladder,
              "toc": skeleton(labs, built["headings"], built["needs"]),
              "needs": [{"row": n["row"], "need": n["kind"], "why": n["why"]} for n in built["needs"]],
              "hints": list(hints or []), "previous": prev}, ensure_ascii=False)}],
        json_schema=check_schema(), point="structure")
    return {"answers": [a for a in (out or {}).get("answers") or [] if isinstance(a, dict)],
            "edits": [e for e in (out or {}).get("edits") or [] if isinstance(e, dict)],
            "rules": [x for x in (out or {}).get("rules") or [] if isinstance(x, dict)]}


def hint_check(doc_id, frame, labs, heads, needs=()):
    """mock — 그 시트의 힌트 · 없으면 None. 나무 꼴(`[{text, depth, role, name?, category?}]`)은 지금 목차에 대한 고침으로 바꾼다
    (나무는 줄 전부를 말하므로 판단 필요의 답을 겸한다 — 판단 필요 행은 답으로 · 나머지는 고침으로)."""
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@structure.json"
    if not p.exists():
        return None
    hint = json.loads(p.read_text(encoding="utf-8")).get(frame)
    if hint is None:
        return None
    gateway.mock("structure", f"힌트(시트 확인) {p.name} · {frame}")
    if isinstance(hint, dict):
        return {"answers": list(hint.get("answers") or []), "edits": list(hint.get("edits") or []),
                "rules": list(hint.get("rules") or [])}
    want = _tree_rows(labs, hint)
    ask = {n["row"] for n in needs}
    answers = [{"row": r, "heading": r in want, "parent": (want.get(r) or {}).get("parent"),
                **{k: (want.get(r) or {}).get(k) for k in ("role", "name", "category")}, "why": "힌트 나무"} for r in sorted(ask)]
    return {"answers": answers, "edits": tree_edits(labs, heads, hint, skip=ask), "rules": []}


def _tree_rows(labs, tree):
    """나무 꼴 → `{행: {parent, role, name, category}}`(줄 글자로 찾는다 — 같은 글자는 차례대로 · 0단은 시트)."""
    rows = [x for x in labs if x["row"] != FRAME_ROW]
    want, stack, at = {}, [], 0
    for e in tree or []:
        d = int(e.get("depth") or 0)
        if d == 0:
            continue
        t = str(e.get("text") or "").strip()
        i = next((j for j in range(at, len(rows)) if str(rows[j]["text"]).strip() == t), None)
        if i is None:
            _LOG.warning("문서 구조 힌트 — 없는 줄 %r (건너뜀)", t)
            continue
        at = i + 1
        while stack and stack[-1][0] >= d:
            stack.pop()
        want[rows[i]["row"]] = {"parent": stack[-1][1] if stack else None, **{k: e.get(k) for k in ("role", "name", "category")}}
        stack.append((d, rows[i]["row"]))
    return want


def tree_edits(labs, heads, tree, skip=()):
    """나무 꼴 힌트 → 지금 목차에 대한 고침(제목 더함 · 제목 뺌 · 부모 바꿈 · 역할 · 대상) — 고친 뒤가 그 나무다(`skip` 행은 답이 맡는다)."""
    want = _tree_rows(labs, tree)
    frame_t = next((e for e in tree or [] if int(e.get("depth") or 0) == 0), None)
    have = {h["row"]: h for h in heads}
    edits = []
    for r in [h["row"] for h in heads if h["row"] not in want and h["row"] != FRAME_ROW and h["row"] not in skip]:
        edits.append(_e(r, "제목 뺌", why="힌트 나무에 없다"))
    for r, w in want.items():
        if r in skip:
            continue
        if r not in have:
            edits.append(_e(r, "제목 더함", parent=w["parent"], role=w["role"], why="힌트 나무"))
        elif have[r].get("parent") != w["parent"]:
            edits.append(_e(r, "부모 바꿈", parent=w["parent"], why="힌트 나무"))
        if w.get("role") in TARGET_ROLES and w.get("name"):
            edits.append(_e(r, "대상", name=w["name"], category=w.get("category"), why="힌트 나무"))
        elif w.get("role"):
            edits.append(_e(r, "역할", role=w["role"], why="힌트 나무"))
    if frame_t and frame_t.get("role"):
        edits.append(_e(FRAME_ROW, "대상" if frame_t.get("name") else "역할", role=frame_t.get("role"),
                        name=frame_t.get("name"), category=frame_t.get("category"), why="힌트 나무(시트)"))
    return edits


def _e(row, what, **kw):
    return {"row": row, "what": what, "parent": kw.get("parent"), "to_row": None, "role": kw.get("role"),
            "name": kw.get("name"), "category": kw.get("category"), "why": kw.get("why") or ""}


def answers_to_edits(doc_id, frame, heads, needs, answers):
    """판단 필요의 답 → 고침 목록 · `(고침, 답 빠진 행, 판단 필요가 아닌 줄의 답)` — 답은 **판단 필요 행마다 빠짐없이**가 원칙이다
    (빠진 행은 코드가 세운 자리 그대로 · 결함 로그)."""
    have = {h["row"]: h for h in heads}
    want = {n["row"] for n in needs}
    got, edits, stray = set(), [], []
    for a in answers or []:
        r = a.get("row")
        if r not in want:
            stray.append(r)
            continue
        got.add(r)
        why = str(a.get("why") or "판단 필요의 답")
        if a.get("heading"):
            if r not in have:
                edits.append(_e(r, "제목 더함", parent=a.get("parent"), role=a.get("role"), why=why))
            elif have[r].get("parent") != a.get("parent"):
                edits.append(_e(r, "부모 바꿈", parent=a.get("parent"), why=why))
            if a.get("role") in TARGET_ROLES and a.get("name"):
                edits.append(_e(r, "대상", name=a.get("name"), category=a.get("category"), why=why))
            elif a.get("role"):
                edits.append(_e(r, "역할", role=a.get("role"), why=why))
        elif r in have:
            edits.append(_e(r, "제목 뺌", why=why))
    missing = sorted(want - got)
    if missing:
        store.append_defect(f"{doc_id}: 시트 확인 — 판단 필요 답 빠짐 {len(missing)}(시트 '{frame}' {missing[:6]}) → 코드 자리 그대로")
    return edits, missing, stray


def rule_counts(labs, heads, rules):
    """사다리 고침마다 「적용 n줄 / 그 서명 전체 m줄」 — 그 서명 줄 가운데 그 역할의 제목으로 선 수."""
    role = {h["row"]: h.get("role") for h in heads}
    out = []
    for x in rules or []:
        rows = [y["row"] for y in labs if y.get("sig") == x.get("shape") and y["row"] != FRAME_ROW]
        out.append({**x, "적용": sum(1 for r in rows if r in role and (x.get("role") is None or role[r] == x.get("role"))),
                    "전체": len(rows)})
    return out


def name_of(text):
    return SG.strip_head(text)
