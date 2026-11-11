# -*- coding: utf-8 -*-
"""칸 2.4 — **본문 목록 · 형제 꼴 일관성**(B197 ⑤ — 결정적 · LLM 0) — 받은 구조 · 사람 고침 · 확정 재생 위의 한 자리(제목 범위 연속
`struct_rule.contiguous` 바로 뒤).

| 규칙 | 무엇 |
|---|---|
| 형제 꼴 일관성(먼저) | 같은 부모 아래 같은 꼴(번호 서명)의 줄은 모두 제목이거나 모두 본문 — 섞이면 많은 쪽으로(같으면 제목) · 「판단 필요 — 형제 꼴 섞임」 |
| 본문 목록 | 같은 부모 아래 같은 꼴의 제목 줄이 사이에 본문 줄 없이 셋 이상 이어지고 모두 자식이 없으면 목록 — 위 제목의 본문으로 · 「판단 필요 — 목록: 본문으로 n줄」 |

맨 위 단 · 본문 줄이 하나도 없는 프레임(B132)은 그대로 · 사람이 고친 줄(`structure_fixes`)과 이유가 붙은 고침 줄(`edits`)은 바꾸지 않는다 · 자식이 있는 제목은
본문으로 내리지 않는다. 사다리 `lists`(시트 확인의 목록 규칙 — 그 목록을 어느 제목 아래 **제목으로** 세울지)와 다른 것이다.
"""
from __future__ import annotations

#: 판단 필요 줄의 표지
TAG_LIST, TAG_MIX = "목록", "형제 꼴"
#: 목록으로 보는 최소 줄 수
LIST_MIN = 3


def _top(p, frame_row):
    return p in (None, frame_row)


def apply(st, labs, fixes=None, frame_row=0):
    """구조 `st`에 두 규칙 — 같은 구조면 그대로(바뀐 것이 없으면 같은 객체)."""
    if not st or not st.get("headings"):
        return st
    fixed = {int(k) if str(k).lstrip("-").isdigit() else k for k in (fixes or {})}
    fixed |= {e.get("row") for e in st.get("edits") or []}     # 이유가 붙은 고침(시트 확인 · 힌트)도 고친 줄이다 — 규칙이 되돌리지 않는다
    order = [x["row"] for x in labs if x["row"] != frame_row]
    sig = {x["row"]: x.get("sig") for x in labs}
    heads = {h["row"]: dict(h) for h in st["headings"]}
    body = [r for r in order if r not in heads]
    if not body:                                   # 본문 줄이 하나도 없는 프레임(B132) — 그대로
        return st
    needs = [dict(n) for n in st.get("needs") or []]
    changed = _siblings(heads, order, sig, fixed, frame_row, needs)
    changed = _lists(heads, order, sig, fixed, frame_row, needs) or changed
    if not changed:
        return st
    pos = {r: i for i, r in enumerate(order)}
    return {**st, "headings": sorted(heads.values(), key=lambda h: pos.get(h["row"], -1)), "needs": needs}


def _owner(heads, order, r):
    """본문 줄의 주인 — 그 위 가장 가까운 제목(없으면 None)."""
    up = None
    for x in order:
        if x == r:
            return up
        if x in heads:
            up = x
    return up


def _children(heads):
    return {h.get("parent") for h in heads.values()}


def _siblings(heads, order, sig, fixed, frame_row, needs):
    """형제 꼴 일관성 — 부모 · 꼴마다 제목 수와 본문 수를 견준다."""
    groups = {}
    for r in order:
        s = sig.get(r)
        if not s:
            continue
        if r in heads:
            p = heads[r].get("parent")
        else:                                      # 본문 줄의 부모 — 주인이 같은 꼴의 제목(형제가 될 줄)이면 그 부모
            p = _owner(heads, order, r)
            while p in heads and sig.get(p) == s:
                p = heads[p].get("parent")
            if p is None:
                continue
        groups.setdefault((p, s), []).append(r)
    changed = False
    for (p, _s), rows in groups.items():
        hs = [r for r in rows if r in heads]
        bs = [r for r in rows if r not in heads]
        if not hs or not bs or _top(p, frame_row):
            continue
        kids = _children(heads)
        if len(hs) >= len(bs):                     # 제목으로 — 본문 줄을 그 부모 아래 제목으로 세운다
            role = heads[hs[0]].get("role")
            moved = [r for r in bs if r not in fixed]
            for r in moved:
                heads[r] = {"row": r, "parent": p, **({"role": role} if role else {})}
        else:                                      # 본문으로 — 자식 없는 제목만
            moved = [r for r in hs if r not in fixed and r not in kids]
            for r in moved:
                heads.pop(r)
        if moved:
            changed = True
        needs.append({"row": rows[0], "kind": "ⓒ", "tag": TAG_MIX,
                      "why": f"판단 필요 — 형제 꼴 섞임: 제목 {len(hs)} · 본문 {len(bs)} → "
                             f"{'제목' if len(hs) >= len(bs) else '본문'}으로 {len(moved)}줄"})
    return changed


def _lists(heads, order, sig, fixed, frame_row, needs):
    """본문 목록 — 같은 부모 · 같은 꼴의 자식 없는 제목이 사이에 본문 없이 셋 이상 이어지면 위 제목의 본문으로."""
    kids = _children(heads)
    runs, cur = [], []
    for r in order:
        h = heads.get(r)
        if h is None:                              # 본문 줄 — 이어짐이 끊긴다
            if cur:
                runs.append(cur)
            cur = []
            continue
        key = (h.get("parent"), sig.get(r))
        if cur and (heads[cur[-1]].get("parent"), sig.get(cur[-1])) == key and sig.get(r):
            cur.append(r)
        else:
            if cur:
                runs.append(cur)
            cur = [r]
    if cur:
        runs.append(cur)
    changed = False
    for run in runs:
        p = heads[run[0]].get("parent")
        if (len(run) < LIST_MIN or _top(p, frame_row) or not sig.get(run[0])
                or any(r in kids or r in fixed for r in run)):
            continue
        for r in run:
            heads.pop(r)
        needs.append({"row": run[0], "kind": "ⓒ", "tag": TAG_LIST, "why": f"판단 필요 — 목록: 본문으로 {len(run)}줄"})
        changed = True
    return changed
