# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **계층 사다리(문서당 1) · 골격 보기 · 시트 확인(시트당 1)** — LLM은 규칙을 정하고 확인한다 · 코드는 재료 · 적용 · 검사 (B132 ③⑤).

    사다리   입력 = 문서의 앞부분(사슬이 가장 깊이 내려간 첫 대목의 골격 보기 · 길어도 `FRONT_ROWS`행) + 문서 전체 서명 통계 + 코드 사다리 +
             문서 맥락 + 층 힌트 + 문서 힌트 — **줄 전문 0** · 출력 = 단마다 서명 · 역할 · 카테고리 + 번호 없는 제목의 규칙
    시트 확인 입력 = 그 시트의 골격 보기(제목 줄은 앞 `HEAD_CHARS`자 + 「…총 n자」 · 서명 · 깊이 · 시작 열 · 역할 · 본문은 접는다 · 판단
             필요 행은 이유와 앞뒤 `NEAR`줄) + 사다리 + 문서 힌트 · 출력 = 판단 필요 행마다 답(빠짐없이) + 고침(B126 여섯 동사) + 사다리 고침
    검사     서명은 그 문서에 있는 것 · 역할은 셋 · 카테고리는 닫힌 목록 · 조건은 닫힌 목록 — **어긋난 칸만** 버린다(결함 로그)
    답 꼴   `shape` 한 함수(실호출 답 · mock 힌트) — 답이 dict가 아니면 답 전체를 · 목록이어야 하는 칸이 목록이 아니면 그 칸을 버린다
             (사다리는 코드 사다리 · 시트 확인은 사다리 목차 그대로 · 결함 로그 한 줄 — B134 ②)

mock — 사다리는 힌트 `<doc_id>@ladder.json` · 시트 확인은 `<doc_id>@structure.json`의 그 시트(`{answers, edits, rules}` 또는 나무
`[{text, depth, role, name?, category?}]` — 나무는 지금 목차에 대한 고침으로 바꿔 쓴다) · 없으면 판정 없음(사다리는 코드 사다리).
"""
from __future__ import annotations

import json

from core.llm import gateway
from core.state import log, store
from parser import ladder as PL
from parser import sig as SG
from core.build.structure_edit import SCOPES as SE_SCOPES
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
    eg = {r for n in needs for r in list(n.get("rows") or [])[:2]}       # 같은 꼴 묶음의 예시 둘도 앞뒤와 함께 (B139 ③)
    near = {r for n in set(need) | eg for i, x in enumerate(rows) if x["row"] == n
            for r in (y["row"] for y in rows[max(0, i - NEAR):i + NEAR + 1])}
    out, body = [], []

    def flush():
        if body:
            out.append({"kind": "본문", "rows": f"R{body[0]}~R{body[-1]}" if len(body) > 1 else f"R{body[0]}", "n": len(body)})
            body.clear()
    for x in rows:
        r = x["row"]
        rest = [m for m in x.get("marks") or [] if not str(m).startswith(PL.FORMAT)]
        base = {"row": r, "sig": x.get("sig"), "head": _head(x), "depth": x.get("depth") or 0, "col": x.get("col"),
                **({"fmt": PL.fmt_text(x)} if PL.fmt_text(x) else {}),        # 짧은 서식 표시 — 보조 단서 (B137 ③)
                **({"marks": rest} if rest else {})}
        at = {"toc": toc.get(r), "parent": head[r].get("parent"), "role": head[r].get("role"),
              **({"title": True} if head[r].get("sig") == PL.TITLE else {})} if r in head else {}
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


# ---------------------------------------------------------------- 답 꼴 검사 (B134 ② — 실호출 답 · mock 힌트가 같은 함수)
#: 답 종류마다 **목록이어야 하는 칸** · 칸 항목의 조건(dict 밖은 늘 뺀다)
SHAPE = {"사다리": ("levels", "unnumbered"), "시트 확인": ("answers", "edits", "rules")}
_ITEM_OK = {"rules": lambda x: isinstance(x.get("shape"), str)}


def shape(doc_id, what, out, frame=None):
    """답 꼴 검사 — `(쓸 답 또는 None, 버린 것 [사유])` · 답이 없으면 `(None, [])` · dict가 아니면 답 전체를 버린다(None) · 목록이어야
    하는 칸(`SHAPE`)이 목록이 아니면 그 칸을 빈 목록으로 · 목록 안의 꼴이 어긋난 항목은 뺀다 · 버린 것이 있으면 결함 로그 한 줄
    (문서 · 시트 · 어긋난 칸) — 정상 답은 그대로 지나간다."""
    if out is None:
        return None, []
    if not isinstance(out, dict):
        clean, bad = None, [f"답 전체({type(out).__name__})"]
    else:
        clean, bad = dict(out), []
        for k in SHAPE[what]:
            v = out.get(k)
            if v is None:
                clean[k] = []
            elif not isinstance(v, list):
                clean[k] = []
                bad.append(f"{k}({type(v).__name__})")
            else:
                ok = _ITEM_OK.get(k, lambda _x: True)
                clean[k] = [x for x in v if isinstance(x, dict) and ok(x)]
                if len(clean[k]) < len(v):
                    bad.append(f"{k} 항목 {len(v) - len(clean[k])}")
    if bad:
        store.append_defect(f"{doc_id}: {what} — 답 꼴 어긋남" + (f" · 시트 '{frame}'" if frame else "")
                            + f" · {' · '.join(bad)} → 그 칸 버림")
    return clean, bad


# ---------------------------------------------------------------- 사다리 — 호출 · mock · 검사
def ask_ladder(frames, built, code, cats, cfgs=None, ctx=None, hints=None):
    with gateway.branch("구조 사다리"):                    # 태그는 시트 확인과 같다 — 끝 표의 갈래는 따로 (B139 ⑤)
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
    raw, bad = shape(doc_id, "사다리", raw)
    if raw is None:
        return None, bad
    have = {x["sig"] for labs in frames.values() for x in labs if x.get("sig")}
    used, levels = set(), []

    def drop(why):
        store.append_defect(f"{doc_id}: 계층 사다리 — {why}")
        bad.append(why)
    for lv in raw["levels"]:
        if not isinstance(lv.get("sigs"), list):
            drop(f"단의 서명 칸 꼴({type(lv.get('sigs')).__name__}) — 그 단 버림")
            continue
        sigs = []
        for s in lv["sigs"]:
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
                       "rows": [r for r in (lv.get("rows") if isinstance(lv.get("rows"), list) else []) if isinstance(r, int)][:6]})
    rules = []
    for u in raw["unnumbered"]:
        if not isinstance(u.get("when"), list) or not u["when"] or not all(_when_ok(w) for w in u["when"]) \
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


def scope_of(rule):
    """사다리 고침의 범위 — 없으면 「꼴 전부」(옛 답 · 힌트 · B137 ⑤)."""
    return rule.get("scope") or SE_SCOPES[0]


def check_rules(doc_id, frame, rules, have):
    """사다리 고침의 검사(B137 ⑤ — 기계적) — `(쓸 규칙, 버림 [{규칙 …, 버림}])` · 서명 · 부모 서명은 그 문서에 있는 것 · 범위는 닫힌 둘 ·
    「첫 서수 목록」은 부모 서명이 있어야 한다 — 밖이면 그 규칙만 버린다(결함 로그)."""
    kept, bad = [], []
    for x in rules or []:
        why = None
        if x.get("shape") not in have:
            why = f"문서에 없는 서명 '{x.get('shape')}'"
        elif scope_of(x) not in SE_SCOPES:
            why = f"범위 밖 '{x.get('scope')}'"
        elif x.get("parent_shape") is not None and x["parent_shape"] not in have:
            why = f"문서에 없는 부모 서명 '{x['parent_shape']}'"
        elif scope_of(x) == SE_SCOPES[1] and not x.get("parent_shape"):
            why = "첫 서수 목록 규칙에 부모 서명이 없다"
        if why:
            store.append_defect(f"{doc_id}: 사다리 고침 버림 — {why} (시트 '{frame}')")
            bad.append({**x, "버림": why})
        else:
            kept.append(x)
    return kept, bad


def fix_ladder(ladder, rules, cats):
    """**사다리 고침**(시트 확인 · 사람 힌트의 규칙 `{shape, role, category, parent_shape, scope, said}` — `shape` = 서명) — 새 사다리 · 결정적.

    범위 「꼴 전부」 — 그 서명의 단에 역할 · 카테고리를 건다(단에 서명이 여럿이면 그 서명만 떼어 같은 자리에 새 단) · `parent_shape`가 오면
    그 서명을 그 서명 단의 바로 아래 단으로 옮긴다 · 사다리에 없는 서명은 맨 아래(또는 부모 서명 아래)에 새 단으로 · 닫힌 목록 밖은 버린다.
    범위 「첫 서수 목록」(B137 ⑤) — 단은 그대로 두고 `lists`에 「`parent_shape` 아래에서 첫 서수로 시작하는 그 서명의 목록」을 건다(그 목록의
    줄만 그 줄의 자식 · 역할 · 카테고리 — `parser/ladder.apply`)."""
    levels = [dict(lv, sigs=list(lv.get("sigs") or [])) for lv in (ladder or {}).get("levels") or []]
    lists = [dict(u) for u in (ladder or {}).get("lists") or []]
    for rule in rules or []:
        s, psh = rule.get("shape"), rule.get("parent_shape")
        role = rule.get("role") if rule.get("role") in ROLES else None
        cat = rule.get("category") if role in TARGET_ROLES and rule.get("category") in cats else None
        if not s:
            continue
        if scope_of(rule) == SE_SCOPES[1]:
            if psh:
                lists = [u for u in lists if (u["shape"], u["parent_shape"]) != (s, psh)] + [
                    {"shape": s, "parent_shape": psh, "role": role, "category": cat,
                     "why": str(rule.get("said") or "사람 힌트")[:200], "by": "고침"}]
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
    return {**(ladder or {}), "levels": levels, **({"lists": lists} if lists else {})}


# ---------------------------------------------------------------- 시트 확인 — 호출 · mock · 답을 고침으로
def ask_check(frame, labs, built, ladder, cats, cfgs=None, ctx=None, hints=None, prev=None):
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(PROMPT, cfgs or {}, "structure")},
         {"role": "user", "content": json.dumps(
             {"task": "check", "categories": cats, "frame": frame, "context": ctx or {}, "ladder": ladder,
              "toc": skeleton(labs, built["headings"], built["needs"]),
              "needs": [{"row": n["row"], "need": n["kind"], "why": n["why"], **({"rows": n["rows"]} if n.get("rows") else {})}
                        for n in built["needs"]],
              "hints": list(hints or []), "previous": prev}, ensure_ascii=False)}],
        json_schema=check_schema(), point="structure")
    return out                                              # 꼴 검사는 부르는 쪽이 `shape`로(mock 힌트와 같은 함수 — B134 ②)


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
    if not isinstance(hint, list):
        return hint                                         # `{answers, edits, rules}` — 꼴 검사는 `shape`(B134 ②)
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
        if not isinstance(e, dict):
            continue
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
    frame_t = next((e for e in tree or [] if isinstance(e, dict) and int(e.get("depth") or 0) == 0), None)
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
            "name": kw.get("name"), "category": kw.get("category"), "why": kw.get("why") or "",
            **({"src": kw["src"]} if kw.get("src") else {})}


def group_rules(needs, answers, labs):
    """**같은 꼴 판단 필요의 답 → 규칙 한 줄**(B139 ③) — 사다리 밖 꼴(ⓐ · `rows`)의 답이 제목이면 그 꼴을 사다리에 넣는 규칙
    (`꼴 전부` · 부모 서명 = 답의 부모 줄의 서명 — 없으면 맨 아래 단) · 본문이면 규칙 0(그 꼴 줄은 본문 그대로)."""
    sig = {x["row"]: x.get("sig") for x in labs}
    ask = {n["row"]: n for n in needs if n.get("rows") and n["kind"] == "ⓐ"}
    out = []
    for a in answers or []:
        n = ask.get(a.get("row"))
        if n and a.get("heading") and sig.get(n["row"]):
            out.append({"shape": sig[n["row"]], "role": a.get("role"), "category": a.get("category"),
                        "parent_shape": sig.get(a.get("parent")), "scope": SE_SCOPES[0],
                        "said": f"판단 필요 답 — '{SG.show(sig[n['row']])}' 줄 {len(n['rows'])}줄은 제목 · {a.get('why') or ''}"[:200]})
    return out


def answers_to_edits(doc_id, frame, heads, needs, answers):
    """판단 필요의 답 → 고침 목록 · `(고침, 답 빠진 행, 판단 필요가 아닌 줄의 답)` — 답은 **판단 필요 행마다 빠짐없이**가 원칙이다
    (빠진 행은 코드가 세운 자리 그대로 · 결함 로그) · 같은 꼴 묶음(`rows`)의 답은 그 줄 전부에(본문이면 줄마다 제목 뺌)."""
    have = {h["row"]: h for h in heads}
    want = {n["row"] for n in needs}
    rows = {n["row"]: n["rows"] for n in needs if n.get("rows")}
    got, edits, stray = set(), [], []
    for a in answers or []:
        r = a.get("row")
        if r not in want:
            stray.append(r)
            continue
        got.add(r)
        why = str(a.get("why") or "판단 필요의 답")
        if r in rows:                                       # 같은 꼴 묶음 — 답은 그 줄 전부에 (B139 ③)
            if not a.get("heading"):
                edits += [_e(x, "제목 뺌", why=why, src="답") for x in rows[r] if x in have]
            continue                                        # 제목이면 규칙(`group_rules`)이 그 꼴 줄 전부를 세웠다
        if a.get("heading"):
            if r not in have:
                edits.append(_e(r, "제목 더함", parent=a.get("parent"), role=a.get("role"), why=why, src="답"))
            elif have[r].get("parent") != a.get("parent"):
                edits.append(_e(r, "부모 바꿈", parent=a.get("parent"), why=why, src="답"))
            if a.get("role") in TARGET_ROLES and a.get("name"):
                edits.append(_e(r, "대상", name=a.get("name"), category=a.get("category"), why=why, src="답"))
            elif a.get("role"):
                edits.append(_e(r, "역할", role=a.get("role"), why=why, src="답"))
        elif r in have:
            edits.append(_e(r, "제목 뺌", why=why, src="답"))
    missing = sorted(want - got)
    if missing:
        store.append_defect(f"{doc_id}: 시트 확인 — 판단 필요 답 빠짐 {len(missing)}(시트 '{frame}' {missing[:6]}) → 코드 자리 그대로")
    return edits, missing, stray


def rule_counts(labs, heads, rules):
    """사다리 고침마다 「적용 n줄 / 그 서명 전체 m줄」 — 꼴 전부는 그 서명 줄 가운데 그 역할의 제목으로 선 수 · 첫 서수 목록은 그 규칙이
    건 줄 수(B137 ⑤)."""
    role = {h["row"]: h.get("role") for h in heads}
    out = []
    for x in rules or []:
        rows = [y["row"] for y in labs if y.get("sig") == x.get("shape") and y["row"] != FRAME_ROW]
        if scope_of(x) == SE_SCOPES[1]:
            got = sum(1 for h in heads if h.get("rule") == [x.get("shape"), x.get("parent_shape")])
        else:
            got = sum(1 for r in rows if r in role and (x.get("role") is None or role[r] == x.get("role")))
        out.append({**x, "적용": got, "전체": len(rows)})
    return out


# ---------------------------------------------------------------- 사용량 갈래 (B137 ⑦ — 지점 ⑪ 안의 사다리 · 시트 확인)
def spent(before):
    """`gateway.usage_total()` 스냅샷 이후의 사용량 — `{calls, prompt, completion, total}`(그 단계에서 정해진 몫 · 화면 한 줄의 재료)."""
    now = gateway.usage_total()
    d = {k: int(now.get(k, 0) or 0) - int((before or {}).get(k, 0) or 0)
         for k in ("calls", "prompt_tokens", "completion_tokens", "total_tokens")}
    return {"calls": d["calls"], "prompt": d["prompt_tokens"], "completion": d["completion_tokens"], "total": d["total_tokens"]}


def changed(draft, heads):
    """초안과 다른 줄 수(B137 ⑦ — LLM이 실제로 바꾼 정도) — 제목이 되거나 빠지거나 부모 · 역할이 바뀐 줄 · 시트(0행)는 세지 않는다."""
    a = {h["row"]: (h.get("parent"), h.get("role")) for h in draft or [] if h["row"] != FRAME_ROW}
    b = {h["row"]: (h.get("parent"), h.get("role")) for h in heads or [] if h["row"] != FRAME_ROW}
    return sorted(r for r in set(a) | set(b) if a.get(r) != b.get(r))


def name_of(text):
    return SG.strip_head(text)
