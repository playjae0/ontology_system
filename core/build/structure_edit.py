# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **구조 `edit` 방식**(B126 ②) — 규칙 나무(고정 규칙 초안)를 바탕으로 주고 LLM에게서 **고칠 곳만 이유와 함께** 받는다.

    입력  시트 전문(줄 · 표시) + 규칙 나무(제목 줄 · 행 · 단) + 형태 단서(형태 요약 + 번호 이어짐 · 다시 시작) + 문서 맥락
          (문서 종류 · 문서 좌표 · 다른 시트 이름) + 층 힌트 + (고리) 앞 출력 · 사람 힌트 전부
    출력  고침 `[{row, what, parent, to_row, role, name, category, why}]` + 제목마다 `{row, role, name, category, why}`
    검사  그 줄이 시트에 있나 · 부모가 앞의 제목인가 · 이름이 줄 글자 그대로인가 · 붙임이 겹치지 않나 — **어긋난 고침만** 버리고 센다

고칠 것이 없으면 규칙 나무 그대로다(B118의 결과가 바닥). 자르기는 고친 나무 위의 크기 구간 + 붙임(`parser.struct_rule.frame_chunks`).
"""
from __future__ import annotations

import json
import re

from core.llm import gateway
from core.state import log, store
from parser.toc import number_value

_LOG = log.get(__name__)

#: 고침의 닫힌 꼴 — 제목 더함 · 제목 뺌 · 부모 바꿈 · 역할 · 대상 · 붙임
WHATS = ("제목 더함", "제목 뺌", "부모 바꿈", "역할", "대상", "붙임")

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {"type": "array", "items": {
            "type": "object",
            "properties": {"row": {"type": "integer"}, "what": {"type": "string", "enum": list(WHATS)},
                           "parent": {"type": ["integer", "null"]}, "to_row": {"type": ["integer", "null"]},
                           "role": {"type": ["string", "null"]}, "name": {"type": ["string", "null"]},
                           "category": {"type": ["string", "null"]}, "why": {"type": "string"}},
            "required": ["row", "what", "parent", "to_row", "role", "name", "category", "why"],
            "additionalProperties": False}},
        "headings": {"type": "array", "items": {
            "type": "object",
            "properties": {"row": {"type": "integer"}, "role": {"type": ["string", "null"]},
                           "name": {"type": ["string", "null"]}, "category": {"type": ["string", "null"]},
                           "why": {"type": "string"}},
            "required": ["row", "role", "name", "category", "why"], "additionalProperties": False}},
        # **이해한 규칙**(B130 ④ — 힌트가 번호 꼴에 걸린 규칙이면 되말한다 · 코드가 그 문서의 같은 꼴 줄 전부에 적용 · 아니면 빈 목록)
        "rules": {"type": "array", "items": {
            "type": "object",
            "properties": {"shape": {"type": "string"}, "role": {"type": ["string", "null"]},
                           "category": {"type": ["string", "null"]}, "parent_shape": {"type": ["string", "null"]},
                           "said": {"type": "string"}},
            "required": ["shape", "role", "category", "parent_shape", "said"], "additionalProperties": False}}},
    "required": ["edits", "headings", "rules"], "additionalProperties": False,
}

# ---------------------------------------------------------------- 형태 단서 — 번호 이어짐 · 다시 시작 (코드가 센다)
def number_runs(labs):
    """**번호 이어짐 · 다시 시작**(B126 ② — 판정 아님) — 꼴마다 위에서 아래로 값이 1씩 이어지는 덩어리 ·
    `[{꼴, 시작, 끝, 수, 다시 시작, 아래}]`(`아래` = 다시 시작한 덩어리 바로 앞의 다른 꼴 번호 줄 `{꼴, 행}`)."""
    seen = []                                       # (행, 꼴, 값) 위에서 아래로
    for x in labs:
        shape = next((m[2:] for m in x.get("marks") or [] if m.startswith("번호")), None)
        if shape:
            seen.append((x["row"], shape, number_value(x.get("text"), shape)))
    runs, cur = [], {}
    for i, (r, s, v) in enumerate(seen):
        if v is None:
            continue
        last = cur.get(s)
        if last and v == last["끝값"] + 1:
            last.update(끝=r, 끝값=v, 수=last["수"] + 1)
            continue
        under = next(({"꼴": s2, "행": r2} for r2, s2, _v in reversed(seen[:i]) if s2 != s), None)
        run = {"꼴": s, "시작": r, "끝": r, "수": 1, "끝값": v,
               "다시 시작": bool(last) and v == 1, "아래": under if (last and v == 1) else None}
        runs.append(run)
        cur[s] = run
    return [{k: v for k, v in x.items() if k != "끝값"} for x in runs if x["수"] > 1 or x["다시 시작"]]


def run_lines(runs):
    """형태 단서의 사람 글 — 「'1)' 18~40행 11개 이어짐」 · 「'1.' 17행 — '가.'(14행) 아래에서 다시 시작」."""
    out = []
    for x in runs:
        if x["다시 시작"] and x.get("아래"):
            out.append(f"'{x['꼴']}' {x['시작']}행 — '{x['아래']['꼴']}'({x['아래']['행']}행) 아래에서 다시 시작"
                       + (f" · {x['시작']}~{x['끝']}행 {x['수']}개 이어짐" if x["수"] > 1 else ""))
        else:
            out.append(f"'{x['꼴']}' {x['시작']}~{x['끝']}행 {x['수']}개 이어짐")
    return out


def rules_tree(labs, draft):
    """규칙 나무(입력 · 화면) — `[{row, depth, text}]` 위에서 아래로(단 = 부모 사슬의 깊이)."""
    text = {x["row"]: x.get("text") for x in labs}
    depth = {}
    for h in draft:
        depth[h["row"]] = depth.get(h.get("parent"), 0) + 1 if h.get("parent") is not None else 1
    return [{"row": h["row"], "depth": depth[h["row"]], "text": str(text.get(h["row"]) or "")[:120]} for h in draft]


# ---------------------------------------------------------------- 실호출 · mock
def ask_edit(frame, lines, labs, draft, cats, ctx=None, cfgs=None, prev=None, hints=None, prompt="outline"):
    """지점 ⑪(태그 `structure`) `edit` 한 호출 — `{edits, headings}`(검사 전)."""
    from core.build.structure import form_summary
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(prompt, cfgs or {}, "structure")},
         {"role": "user", "content": json.dumps(
             {"mode": "edit", "categories": cats, "frame": frame, "context": ctx or {},
              "form": {**form_summary(labs), "번호 이어짐": run_lines(number_runs(labs))},
              "rules_tree": rules_tree(labs, draft), "lines": lines,
              "previous": prev, "hints": list(hints or [])}, ensure_ascii=False)}],
        json_schema=EDIT_SCHEMA, point="structure")
    return {"edits": [e for e in (out or {}).get("edits") or [] if isinstance(e, dict)],
            "headings": [h for h in (out or {}).get("headings") or [] if isinstance(h, dict)],
            "rules": [x for x in (out or {}).get("rules") or [] if isinstance(x, dict)]}


# ---------------------------------------------------------------- 고침 적용 · 검사 (결정적)
def apply_edits(doc_id, frame, labs, draft, out, cats):
    """규칙 나무 + 고침 → `(제목 [{row, parent, role, name, category, why?}], 붙임 [{from_row, to_row}], 받은 고침, 버린 고침)` ·
    어긋난 고침만 버린다(결함 로그 · 셈) — 시트 전체를 버리지 않는다."""
    from core.build.outline import _span
    from parser.struct_rule import FRAME_ROW, ROLES, TARGET_ROLES
    order = {x["row"]: i for i, x in enumerate(labs)}
    text = {x["row"]: x.get("text") for x in labs}
    heads = {h["row"]: dict(h) for h in draft}
    joins, took, bad = [], [], []

    def drop(e, why):
        store.append_defect(f"{doc_id}: 문서 구조 고침 버림 — {why} (시트 '{frame}' {e.get('row')}행 {e.get('what')})")
        bad.append({**e, "버림": why})

    def is_before(p, r):
        return p is None or p == FRAME_ROW or (p in heads and order.get(p, 1 << 30) < order[r])

    def target(e, r):
        if e.get("name") is None and e.get("category") is None:
            return {"name": None, "category": None}
        got = _span(e.get("name"), text.get(r))
        if got is None or e.get("category") not in cats:
            return None
        return {"name": got, "category": e["category"]}

    for e in (out or {}).get("edits") or []:
        r, w = e.get("row"), e.get("what")
        if r not in order or r == FRAME_ROW and w not in ("역할", "대상"):
            drop(e, "시트에 없는 줄")
            continue
        if w == "제목 더함":
            if r in heads or not is_before(e.get("parent"), r):
                drop(e, "이미 제목이다" if r in heads else f"부모 {e.get('parent')}행이 앞의 제목이 아니다")
                continue
            heads[r] = {"row": r, "parent": None if e.get("parent") == FRAME_ROW else e.get("parent"),
                        "role": e.get("role") if e.get("role") in ROLES else None, "name": None, "category": None}
        elif w == "제목 뺌":
            if r not in heads:
                drop(e, "제목이 아니다")
                continue
            up = heads.pop(r).get("parent")
            for h in heads.values():
                if h.get("parent") == r:
                    h["parent"] = up
        elif w == "부모 바꿈":
            if r not in heads or not is_before(e.get("parent"), r):
                drop(e, "제목이 아니다" if r not in heads else f"부모 {e.get('parent')}행이 앞의 제목이 아니다")
                continue
            heads[r]["parent"] = None if e.get("parent") == FRAME_ROW else e.get("parent")
        elif w == "역할":
            if e.get("role") not in ROLES or (r not in heads and r != FRAME_ROW):
                drop(e, f"역할 밖 '{e.get('role')}'" if e.get("role") not in ROLES else "제목이 아니다")
                continue
            heads.setdefault(r, {"row": r, "parent": None, "name": None, "category": None})["role"] = e["role"]
        elif w == "대상":
            tg = target(e, r) if (r in heads or r == FRAME_ROW) else None
            if tg is None:
                drop(e, "제목이 아니다" if r not in heads and r != FRAME_ROW else f"줄 글자 밖 이름 · 목록 밖 카테고리 '{e.get('name')}'")
                continue
            heads.setdefault(r, {"row": r, "parent": None, "role": TARGET_ROLES[0]}).update(
                role=TARGET_ROLES[0], **tg)
        elif w == "붙임":
            t = e.get("to_row")
            if t not in order or order[t] < order[r] or any(not (order[t] < order[j["from_row"]] or order[r] > order[j["to_row"]])
                                                             for j in joins):
                drop(e, "붙임 구간이 시트 밖 · 거꾸로 · 겹침")
                continue
            joins.append({"from_row": r, "to_row": t})
        took.append(e)
    for h in (out or {}).get("headings") or []:                  # 제목마다 역할 · 대상 · 이유
        r = h.get("row")
        if r not in heads:
            continue
        if h.get("role") in ROLES and not heads[r].get("by"):
            heads[r]["role"] = h["role"]
        tg = target(h, r) if heads[r].get("role") in TARGET_ROLES else {"name": None, "category": None}
        if tg is None:
            bad.append({"row": r, "what": "대상", "why": h.get("why"), "버림": f"줄 글자 밖 이름 · 목록 밖 카테고리 '{h.get('name')}'"})
        elif tg.get("name") or not heads[r].get("name"):
            heads[r].update(tg)
        if h.get("why"):
            heads[r]["why"] = str(h["why"])[:200]
    out_heads = [heads[x["row"]] for x in labs if x["row"] in heads]
    return out_heads, joins, took, bad


# ---------------------------------------------------------------- 문서 규칙 적용 (B130 ④ — 결정적 · 검사만)
def apply_rules(doc_id, frame, labs, heads, rules, cats):
    """이해한 규칙(`[{shape, role, category, parent_shape, said}]`)을 그 시트의 같은 꼴 줄 전부에 — `(제목, 규칙마다 셈)`.

    그 꼴의 줄은 제목으로 서고(없던 줄은 더한다 — 부모는 `parent_shape`의 가장 가까운 앞 제목 · 없으면 같은 꼴 앞 제목의 부모) 역할 ·
    대상(이름 = 줄 글자에서 번호를 뗀 것)을 받는다. 닫힌 목록 밖(꼴 · 역할 · 카테고리 · 부모 꼴)이면 **그 규칙만** 버린다(결함 로그)."""
    from parser.struct_map import NUMBER_SHAPES, number_shape, strip_number
    from parser.struct_rule import FRAME_ROW, ROLES, TARGET_ROLES
    shapes = {lab for lab, _rx in NUMBER_SHAPES}
    by = {h["row"]: dict(h) for h in heads}
    order = [x["row"] for x in labs if x["row"] != FRAME_ROW]
    text = {x["row"]: str(x.get("text") or "") for x in labs}
    shape_of = {r: number_shape(text[r]) for r in order}
    seen = []
    for rule in rules or []:
        sh, role, cat, psh = rule.get("shape"), rule.get("role"), rule.get("category"), rule.get("parent_shape")
        why = ("꼴 밖" if sh not in shapes else "역할 밖" if role is not None and role not in ROLES
               else "목록 밖 카테고리" if cat is not None and cat not in cats else "부모 꼴 밖" if psh is not None and psh not in shapes
               else None)
        rows = [r for r in order if shape_of[r] == sh]
        if why:
            store.append_defect(f"{doc_id}: 문서 규칙 버림 — {why} (시트 '{frame}' · {json.dumps(rule, ensure_ascii=False)[:120]})")
            seen.append({**rule, "적용": 0, "전체": len(rows), "버림": why})
            continue
        n = 0
        for r in rows:
            prev = [q for q in order[:order.index(r)] if q in by]
            par = next((q for q in reversed(prev) if psh and shape_of.get(q) == psh), None)
            if r not in by:
                same = next((q for q in reversed(prev) if shape_of.get(q) == sh), None)
                by[r] = {"row": r, "parent": par if psh else (by[same].get("parent") if same else None),
                         "role": None, "name": None, "category": None}
            elif psh and par is not None:
                by[r]["parent"] = par
            if role is not None:
                by[r]["role"] = role
            if role in TARGET_ROLES and cat is not None:
                by[r].update(name=strip_number(text[r]), category=cat)
            elif role is not None and role not in TARGET_ROLES:
                by[r].update(name=None, category=None)
            by[r]["by_rule"] = sh
            n += 1
        seen.append({**rule, "적용": n, "전체": len(rows)})
    out = [by[x["row"]] for x in labs if x["row"] in by]
    return out, seen


def hint_edit(doc_id, frame):
    """mock — 힌트 `<doc_id>@structure.json`의 그 시트가 `{"edits": …}` 꼴일 때만 `edit` 답 · 없으면 None(판정 없음)."""
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@structure.json"
    if not p.exists():
        return None
    hint = json.loads(p.read_text(encoding="utf-8")).get(frame)
    if not isinstance(hint, dict) or "edits" not in hint:
        return None
    gateway.mock("structure", f"힌트(edit) {p.name} · {frame}")
    return {"edits": list(hint.get("edits") or []), "headings": list(hint.get("headings") or []),
            "rules": list(hint.get("rules") or [])}
