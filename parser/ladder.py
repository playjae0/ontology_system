# -*- coding: utf-8 -*-
"""칸 2.4 — **계층 사다리 적용** — 사다리 + 이어짐 · 다시 시작 + 들여쓰기 깊이로 목차를 세우고 판단 필요를 표시한다 (B132 ④ · 코드).

    apply(labs, ladder, doc_counts)  이름표 → `{headings, needs}` — 모든 시트에 같은 함수(엑셀 산문 · Word)
    stats(frames)                    문서 전체 서명 통계(시트마다 서명별 수 · 이어짐 · 다시 시작 자리 · 깊이별 서명) — 사다리 입력
    code(frames)                     코드 사다리(다시 시작 증거 — `parser/toc.code_ladder` · `rules` 방식 · 폴백)

사다리 꼴: `{"levels": [{"sigs": [서명…], "role", "category"}], "unnumbered": [{"when": [조건…], "level", "role", "category"}], "by"}` —
위에서 아래로 단 · 역할은 닫힌 셋(대상 · 묶음 · 주제) · 번호 없는 제목의 규칙은 닫힌 조건(`WHEN`)으로만 말한다.

**판단 필요**(코드가 정하지 않고 표시 — 넷): ⓐ사다리에 없는데 제목 같은 서명(문서에 둘 이상 · 짧은 줄 — 본문으로 두고 표시)
ⓑ부모보다 들여쓰기가 얕다 ⓒ이어짐이 끊김(`1) 2) 4)`) · 다시 시작의 부모가 둘 이상 가능(사다리 단을 건너뛰었다)
ⓓ빈 행 뒤 짧은 번호 없는 줄(규칙에 맞지 않으면 본문으로 두고 표시). 답은 시트 확인(LLM · 사람)의 몫이다.
"""
from __future__ import annotations

from parser import sig as SG
from parser import toc

#: 번호 없는 제목 규칙의 닫힌 조건 — `빈 줄 뒤` · `짧은 줄` · `굵게` · `병합` · `깊이 n` · `시작 열 X`
WHEN = ("빈 줄 뒤", "짧은 줄", "굵게", "병합")
NEED_KINDS = {"ⓐ": "사다리에 없는 서명", "ⓑ": "들여쓰기 어긋남", "ⓒ": "이어짐 · 다시 시작", "ⓓ": "빈 행 뒤 짧은 줄"}
_OUTLINE = "개요"                               # 어댑터의 구조 단(Word 개요 수준 — 서명 없는 draft 제목)


def _short(x):
    from parser.struct_map import HEADING_MAX_CHARS
    return (x.get("len") if x.get("len") is not None else len(str(x.get("text") or "").strip())) <= HEADING_MAX_CHARS


def _body(labs):
    return [x for x in labs if x["row"] != 0]


def doc_counts(frames):
    """문서 전체 짧은 줄의 서명별 수 `{서명: n}` — 판단 필요 ⓐ(문서에 둘 이상)의 재료."""
    out = {}
    for labs in frames.values():
        for x in _body(labs):
            if x.get("sig") and _short(x):
                out[x["sig"]] = out.get(x["sig"], 0) + 1
    return out


def code(frames):
    """코드 사다리 — 시트들의 짧은 번호 줄에서 다시 시작 증거(`parser/toc.code_ladder`)."""
    return toc.code_ladder([[(x["row"], x["text"]) for x in _body(labs)] for labs in frames.values()])


def stats(frames):
    """**문서 전체 서명 통계**(사다리 입력 — 줄 전문 0) — `{시트: [{서명, 수, 이어짐, 다시 시작, 깊이}]}`.

    이어짐 = 같은 서명이 서수 1씩 이어진 덩어리 수 · 다시 시작 = 다른 서명 줄 바로 아래에서 첫 서수로 시작한 자리(`{아래 서명, 행}`) ·
    깊이 = 들여쓰기 깊이별 줄 수."""
    out = {}
    for name, labs in frames.items():
        rows, prev, by = _body(labs), None, {}
        last = {}
        for x in rows:
            s, v = x.get("sig"), x.get("ord")
            if not s or not _short(x):
                continue
            e = by.setdefault(s, {"서명": s, "수": 0, "이어짐": 0, "다시 시작": [], "깊이": {}})
            e["수"] += 1
            e["깊이"][str(x.get("depth") or 0)] = e["깊이"].get(str(x.get("depth") or 0), 0) + 1
            if v is not None and last.get(s) is not None and v == last[s] + 1:
                e["이어짐"] += 1
            if v == 1 and prev is not None and prev[0] != s:
                e["다시 시작"].append({"아래": prev[0], "행": x["row"]})
            if v is not None:
                last[s] = v
            prev = (s, x["row"])
        for e in by.values():
            e["다시 시작"] = e["다시 시작"][:6]
        out[name] = list(by.values())
    return out


def _match(rule, x):
    for w in rule.get("when") or []:
        w = str(w)
        if w == "빈 줄 뒤" and not x.get("gap"):
            return False
        if w == "짧은 줄" and not _short(x):
            return False
        if w in ("굵게", "병합") and w not in (x.get("marks") or []):
            return False
        if w.startswith("깊이 ") and str(x.get("depth") or 0) != w[3:].strip():
            return False
        if w.startswith("시작 열 ") and str(x.get("col") or "") != w[5:].strip():
            return False
    return bool(rule.get("when"))


def apply(labs, ladder, counts=None):
    """이름표 + 사다리 → `{"headings": [{row, parent, role, name, category, sig, by}], "needs": [{row, kind, why}]}`.

    번호 줄 — 사다리에 든 서명만 목차에 선다(이어짐 · 다시 시작 · 사다리의 단 순서 — `parser/toc`) · 번호 없는 줄 — 사다리의
    `unnumbered` 규칙에 맞는 줄만(그 규칙의 단) · 어댑터의 구조 단(Word 개요 수준 — 표시 `개요n`)은 사다리 위 단 · 역할 ·
    카테고리는 그 단의 것(대상이면 이름 = 줄 글에서 번호를 뗀 것)."""
    rows = _body(labs)
    by_row = {x["row"]: x for x in rows}
    levels = (ladder or {}).get("levels") or []
    rank = toc.rank_of(ladder)
    meta = {s: lv for lv in levels for s in lv.get("sigs") or []}
    rules = [r for r in (ladder or {}).get("unnumbered") or [] if isinstance(r, dict)]
    hits = []
    for x in rows:
        s, v = x.get("sig"), x.get("ord")
        if s and s in rank and _short(x):
            hits.append((x["row"], s, v))
        elif not s and x.get("draft") and any(str(m).startswith(_OUTLINE) for m in x.get("marks") or []):
            key = f"{_OUTLINE}{x['draft']}"                 # Word 개요 수준만(작성자가 매긴 구조) — 굵게 초안은 단 신호가 아니다
            rank.setdefault(key, -100 + int(x["draft"]))
            hits.append((x["row"], key, None))
        elif not s:
            hit = next((i for i, r in enumerate(rules) if _match(r, x)), None)
            if hit is not None:
                key = f"~{hit}"
                rank.setdefault(key, float(rules[hit].get("level") or 0) - 0.5)
                hits.append((x["row"], key, None))
    forbid = {(c, p) for c in rank for p in rank if rank[c] <= rank[p]}
    lv = toc._toc(hits, forbid, rank=rank)
    key_of = {r: k for r, k, _v in hits}
    parent, stack = {}, []
    for r, _k, _v in hits:
        while stack and stack[-1][0] >= lv[r]:
            stack.pop()
        parent[r] = stack[-1][1] if stack else None
        stack.append((lv[r], r))
    heads = []
    for r, k, _v in hits:
        src = meta.get(k) or (rules[int(k[1:])] if k.startswith("~") else {})
        role, cat = src.get("role"), src.get("category")
        h = {"row": r, "parent": parent[r], "role": role, "name": None, "category": None, "sig": k, "by": "사다리"}
        if role == "대상" and cat:
            h.update(name=SG.strip_head(by_row[r]["text"]), category=cat)
        heads.append(h)
    return {"headings": heads, "needs": needs(labs, heads, rank, key_of, counts or {})}


def needs(labs, heads, rank, key_of, counts):
    """판단 필요 넷(머리말) — `[{row, kind, why}]` 이름표 순 · 한 줄에 하나(앞의 것)."""
    rows = _body(labs)
    by_row = {x["row"]: x for x in rows}
    head = {h["row"]: h for h in heads}
    out = {}

    def add(r, kind, why):
        out.setdefault(r, {"row": r, "kind": kind, "why": why})
    for x in rows:
        s = x.get("sig")
        if s and s not in rank and x["row"] not in head and _short(x) and counts.get(s, 0) >= 2:
            add(x["row"], "ⓐ", f"사다리에 없는 서명 '{s}'(문서에 {counts[s]}줄)")
    for h in heads:
        p = h.get("parent")
        if p in by_row and (by_row[h["row"]].get("depth") or 0) < (by_row[p].get("depth") or 0):
            add(h["row"], "ⓑ", f"들여쓰기 깊이 {by_row[h['row']].get('depth') or 0}가 부모 {p}행(깊이 "
                                f"{by_row[p].get('depth') or 0})보다 얕다")
    kids = {}
    for h in heads:
        kids.setdefault((h.get("parent"), h.get("sig")), []).append(h["row"])
    for (p, s), rs in kids.items():
        prev = None
        for r in rs:
            v = by_row[r].get("ord")
            if v is not None and prev is not None and v != prev + 1:       # 첫 형제가 1이 아닌 것(발췌)은 끊김이 아니다
                add(r, "ⓒ", f"다시 시작 — 같은 부모 아래 '{s}'가 1부터 다시(부모 후보가 둘 이상)" if v == 1
                    else f"이어짐 끊김 — '{s}' {prev} 다음 {v}")
            prev = v if v is not None else prev
    for h in heads:
        p = head.get(h.get("parent"))
        if by_row[h["row"]].get("ord") == 1 and p and isinstance(rank.get(h["sig"]), int) and isinstance(rank.get(p["sig"]), int) \
                and rank[h["sig"]] - rank[p["sig"]] >= 2:
            add(h["row"], "ⓒ", f"다시 시작 — 사다리 단을 건너뛰었다(부모 후보가 둘 이상 · 지금 부모 {p['row']}행)")
    for x in rows:
        if not x.get("sig") and x.get("gap") and _short(x) and x["row"] not in head:
            add(x["row"], "ⓓ", "빈 행 뒤 짧은 번호 없는 줄")
    order = {x["row"]: i for i, x in enumerate(rows)}
    return sorted(out.values(), key=lambda n: order.get(n["row"], 0))
