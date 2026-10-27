# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **구조 고침**(B126 ② · B132 ⑤) — 시트 확인의 답(판단 필요의 답 · 고침 · 사다리 고침)의 꼴과 고침 적용 · 검사.

    고침  `[{row, what, parent, to_row, role, name, why}]` — 여섯 동사(`WHATS`): 제목 더함 · 제목 뺌 · 부모 바꿈 · 역할 · 대상 · 붙임
    검사  그 줄이 시트에 있나 · 부모가 앞의 제목인가 · 이름이 줄 글자 그대로인가 · 붙임이 겹치지 않나 — **어긋난 고침만** 버리고 센다
    목록  「부모 바꿈」이 **목록 머리**(같은 부모 아래 같은 꼴의 앞 서수가 없는 줄)를 옮기면 그 목록(같은 꼴로 서수가 이어지는 형제 —
          그 자손은 형제를 따라간다)이 함께 옮긴다 · 목록 중간 줄 하나의 고침은 그 줄만(B139 ①)

바탕은 사다리로 선 목차(`parser/ladder.apply`)다 — 고칠 것이 없으면 그대로다. 자르기는 고친 목차 위의 크기 구간 + 붙임
(`parser.struct_rule.frame_chunks`). **층을 모른다**(B148 ① — 카테고리 칸 0 · 대상은 이름만 · 카테고리는 그래프 단계의 목차 노드화가
층마다 정한다 — `core/build/outline.py`).
"""
from __future__ import annotations

from core.state import log, store

_LOG = log.get(__name__)

#: 고침의 닫힌 꼴 — 제목 더함 · 제목 뺌 · 부모 바꿈 · 역할 · 대상 · 붙임
WHATS = ("제목 더함", "제목 뺌", "부모 바꿈", "역할", "대상", "붙임")
#: 사다리 고침이 거는 범위(닫힌 둘 — B137 ⑤) — 없으면 「꼴 전부」(옛 답 · 힌트)
SCOPES = ("꼴 전부", "첫 서수 목록")

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {"type": "array", "items": {
            "type": "object",
            "properties": {"row": {"type": "integer"}, "what": {"type": "string", "enum": list(WHATS)},
                           "parent": {"type": ["integer", "null"]}, "to_row": {"type": ["integer", "null"]},
                           "role": {"type": ["string", "null"]}, "name": {"type": ["string", "null"]},
                           "why": {"type": "string"}},
            "required": ["row", "what", "parent", "to_row", "role", "name", "why"],
            "additionalProperties": False}},
        "headings": {"type": "array", "items": {
            "type": "object",
            "properties": {"row": {"type": "integer"}, "role": {"type": ["string", "null"]},
                           "name": {"type": ["string", "null"]}, "why": {"type": "string"}},
            "required": ["row", "role", "name", "why"], "additionalProperties": False}},
        # **사다리 고침**(B130 ④ · B132 ⑤ — 힌트 · 판단이 서명에 걸린 규칙이면 되말한다 · `shape` = 서명 · 코드가 문서 사다리를 고쳐 그
        # 문서의 뒤 시트까지 다시 세운다 · 아니면 빈 목록) · `scope`(B137 ⑤ — 「꼴 전부」 그 서명의 단 · 「첫 서수 목록」 `parent_shape`
        # 아래에서 첫 서수로 시작하는 그 서명의 목록만 — 꼴 전부를 옮기지 않는다)
        "rules": {"type": "array", "items": {
            "type": "object",
            "properties": {"shape": {"type": "string"}, "role": {"type": ["string", "null"]},
                           "parent_shape": {"type": ["string", "null"]},
                           "scope": {"type": "string", "enum": list(SCOPES)}, "said": {"type": "string"}},
            "required": ["shape", "role", "parent_shape", "scope", "said"], "additionalProperties": False}}},
    "required": ["edits", "headings", "rules"], "additionalProperties": False,
}

# ---------------------------------------------------------------- 고침 적용 · 검사 (결정적)
def _list_tail(r, parent, heads, lab, order):
    """목록 머리 `r`의 이어지는 형제(같은 옛 부모 · 같은 꼴 · 서수 +1씩) — `r`이 머리가 아니면(앞 서수 형제가 있으면) 빈 목록."""
    sig, v = (lab.get(r) or {}).get("sig"), (lab.get(r) or {}).get("ord")
    if not sig or v is None:
        return []
    sibs = sorted((x for x in heads if x != r and heads[x].get("parent") == parent
                   and (lab.get(x) or {}).get("sig") == sig), key=lambda x: order.get(x, 1 << 30))
    if any(order.get(x, 0) < order[r] and lab[x].get("ord") == v - 1 for x in sibs):
        return []                                            # 목록 중간 줄 — 그 줄만
    out, last = [], v
    for x in (x for x in sibs if order.get(x, 0) > order[r]):
        if lab[x].get("ord") != last + 1:
            break
        out.append(x)
        last += 1
    return out


def apply_edits(doc_id, frame, labs, draft, out):
    """규칙 나무 + 고침 → `(제목 [{row, parent, role, name, why?}], 붙임 [{from_row, to_row}], 받은 고침, 버린 고침)` ·
    어긋난 고침만 버린다(결함 로그 · 셈) — 시트 전체를 버리지 않는다."""
    from core.build.outline import _span
    from parser.struct_rule import FRAME_ROW, ROLES, TARGET_ROLES
    order = {x["row"]: i for i, x in enumerate(labs)}
    text = {x["row"]: x.get("text") for x in labs}
    lab = {x["row"]: x for x in labs}
    heads = {h["row"]: dict(h) for h in draft}
    joins, took, bad = [], [], []

    def drop(e, why):
        store.append_defect(f"{doc_id}: 문서 구조 고침 버림 — {why} (시트 '{frame}' {e.get('row')}행 {e.get('what')})")
        bad.append({**e, "버림": why})

    def is_before(p, r):
        return p is None or p == FRAME_ROW or (p in heads and order.get(p, 1 << 30) < order[r])

    def target(e, r):
        if e.get("name") is None:
            return {"name": None}
        got = _span(e.get("name"), text.get(r))
        return None if got is None else {"name": got}

    phase = {"제목 더함": 0, "제목 뺌": 1, "부모 바꿈": 2, "역할": 3, "대상": 3, "붙임": 4}
    edits = [e for e in (out or {}).get("edits") or [] if isinstance(e, dict)]
    # 적용 순서는 동사로 고정한다(답 · 고침이 어느 차례로 와도 같은 나무) — 제목 더함(행 순 — 부모가 먼저 선다) → 제목 뺌 → 부모 바꿈 → 역할 · 대상 → 붙임
    edits.sort(key=lambda e: (phase.get(e.get("what"), 5), order.get(e.get("row"), 1 << 30) if e.get("what") == "제목 더함" else 0))
    for e in edits:
        r, w = e.get("row"), e.get("what")
        if r not in order or r == FRAME_ROW and w not in ("역할", "대상"):
            drop(e, "시트에 없는 줄")
            continue
        if w == "제목 더함":
            if r in heads or not is_before(e.get("parent"), r):
                drop(e, "이미 제목이다" if r in heads else f"부모 {e.get('parent')}행이 앞의 제목이 아니다")
                continue
            heads[r] = {"row": r, "parent": None if e.get("parent") == FRAME_ROW else e.get("parent"),
                        "role": e.get("role") if e.get("role") in ROLES else None, "name": None}
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
            old = heads[r].get("parent")
            heads[r]["parent"] = None if e.get("parent") == FRAME_ROW else e.get("parent")
            for f in _list_tail(r, old, heads, lab, order):
                heads[f]["parent"] = heads[r]["parent"]          # 목록 단위 — 이어지는 형제도 같은 부모로 (B139 ①)
        elif w == "역할":
            if e.get("role") not in ROLES or (r not in heads and r != FRAME_ROW):
                drop(e, f"역할 밖 '{e.get('role')}'" if e.get("role") not in ROLES else "제목이 아니다")
                continue
            h = heads.setdefault(r, {"row": r, "parent": None, "name": None})
            h["role"] = e["role"]
            if e["role"] not in TARGET_ROLES:                    # 대상이 아닌 역할 — 사다리가 단 이름을 뗀다
                h["name"] = None
        elif w == "대상":
            tg = target(e, r) if (r in heads or r == FRAME_ROW) else None
            if tg is None:
                drop(e, "제목이 아니다" if r not in heads and r != FRAME_ROW else f"줄 글자 밖 이름 '{e.get('name')}'")
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
        tg = target(h, r) if heads[r].get("role") in TARGET_ROLES else {"name": None}
        if tg is None:
            bad.append({"row": r, "what": "대상", "why": h.get("why"), "버림": f"줄 글자 밖 이름 '{h.get('name')}'"})
        elif tg.get("name") or not heads[r].get("name"):
            heads[r].update(tg)
        if h.get("why"):
            heads[r]["why"] = str(h["why"])[:200]
    out_heads = [heads[x["row"]] for x in labs if x["row"] in heads]
    return out_heads, joins, took, bad
