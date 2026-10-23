# -*- coding: utf-8 -*-
"""칸 2.4 — **목차** — 꼴 서명의 이어짐 · 다시 시작 · 계층 사다리로 세우는 목차와 그 부모 사슬 (B130 ①② · B132 ②④).

    number_levels(lines, ladder=None)  `[(행, 글)]` → `{행: (레벨, 서명)}` — 레벨 = 목차 나무의 깊이(엑셀 산문 · Word 같은 함수)
    code_ladder(frames)                문서의 시트들(`[[(행, 글)]]`)에서 **코드 사다리** — 다시 시작 증거로 선 서명의 단 순서
    toc_chains(lines, levels)          제목마다 부모 사슬 · 줄마다 주인 제목 — 청크 경로(`struct_map.split`)가 쓴다

번호를 읽는 것은 꼴 서명 한 함수(`parser/sig.py`)다. 제목 후보는 짧은 줄만(`struct_map.HEADING_MAX_CHARS` — 넘는 번호 줄은 목록 항목 ·
자르는 자리가 아니다). 사다리(`{"levels": [{"sigs": [서명…]}…]}` — LLM 또는 코드)가 오면 그 단 순서가 목차의 방향을 정한다.
"""
from __future__ import annotations

from parser import sig as SG

#: **목차 규칙 판**(B130 ① · B132 — 꼴 서명 · 사다리 · B137 — 첫 서수 · 이어짐의 초안 · 첫 행 시트 제목) — 구조 확인의 확정 기록이
#: 이 판을 적는다 · 판이 다른 옛 확정은 재생하지 않는다(목차가 틀렸을 수 있다)
TOC_VERSION = "toc-4"


def _short(text):
    from parser.struct_map import HEADING_MAX_CHARS
    return len(str(text or "").strip()) <= HEADING_MAX_CHARS


def hits_of(lines, ladder_sigs=()):
    """목차 후보 `[(행, 서명, 서수)]` — 짧은 줄 · 서수가 있는 서명(기호 서명은 사다리에 든 것만)."""
    out = []
    for r, t in lines:
        s, v = SG.signature(t)
        if s and _short(t) and (v is not None or s in ladder_sigs):
            out.append((r, s, v))
    return out


def _toc(hits, forbid, seen=None, rank=None, first=None):
    """열린 제목의 스택으로 목차를 세운다 — `{행: 단}` · `seen`이면 다시 시작한 자리 `(자식 서명, 부모 서명, 부모 서수)`를 적는다.

    ⓐ 열린 줄 가운데 같은 서명 · 서수 − 1이 있으면 그 줄까지 닫고 형제 ⓑ 서수가 첫째면 맨 위 열린 제목의 자식(그 서명이 그 부모
    서명 아래로 가면 안 되는 방향이면 — `forbid` — 열린 줄을 닫고 그 위의 자식) ⓒ 둘 다 아니면 같은 서명이 열려 있으면 그 형제 · 그
    서명이 다시 시작한 부모 서명이 열려 있으면 그 자식 · 사다리(`rank` — 서명의 단 번호)가 있으면 단이 더 얕은 가장 가까운 열린 줄의
    자식 · 아니면 맨 위의 자식.

    `first`(**목차 초안** — 계층 사다리 적용 · B137 ①)가 오면 ⓑ의 첫 서수는 `forbid` · 사다리로 열린 줄을 닫지 않고 **바로 위 제목 줄의
    자식**이다(같은 꼴이 두 깊이에 선다) — 그 자리가 `forbid`(사다리 단 순서)와 어긋나면 **초안은 사다리를 따르고**(ⓑ의 닫기 · B139 ②)
    `first["clash"]`에 `{행: 바로 위 제목 행}`을 적는다(판단 필요의 재료) · 문서 규칙
    「P 아래에서 첫 서수로 시작하는 S 목록」(`first["lists"]` — `{(S, P)}`)에 맞으면 가장 가까운 열린 P 줄의 자식이고 그 목록의 이어지는
    줄과 함께 `first["ruled"]`(`{행: (S, P)}`)에 적는다 · 이어짐도 첫 서수도 아닌 번호 줄은 같은 꼴의 열린 줄을 찾지 않고 사다리의 단
    순서(ⓒ)로 서며 `first["loose"]`에 적는다."""
    stack, out, under = [], {}, {}
    for r, key, val in hits:
        sib = next((i for i in range(len(stack) - 1, -1, -1)
                    if stack[i][0] == key and val is not None and stack[i][1] == val - 1), None)
        if sib is None and val != 1 and not (first is not None and rank and key in rank):
            sib = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == key), None)
        if first is not None and sib is None and val not in (None, 1):
            first["loose"].append(r)                               # 이어짐도 첫 서수도 아니다 — 사다리 단 순서로 선다
        if sib is not None:
            lv = stack[sib][2]
            if first is not None and stack[sib][3] in first["ruled"]:
                first["ruled"][r] = first["ruled"][stack[sib][3]]      # 규칙이 건 목록의 이어지는 줄
            del stack[sib:]
        elif first is not None and val == 1:
            par = next((i for i in range(len(stack) - 1, -1, -1) if (key, stack[i][0]) in first["lists"]), None)
            if par is not None:
                first["ruled"][r] = (key, stack[par][0])
                del stack[par + 1:]
            elif stack and (key, stack[-1][0]) in forbid:
                first["clash"][r] = stack[-1][3]                       # 첫 서수로는 바로 위의 자식 — 단 순서와 어긋나 사다리를 따른다
                while stack and (key, stack[-1][0]) in forbid:
                    stack.pop()
            if stack:
                under.setdefault(key, set()).add(stack[-1][0])
                if seen is not None:
                    seen.append((key, stack[-1][0], stack[-1][1]))
            lv = stack[-1][2] + 1 if stack else 1
        else:
            if val != 1 and under.get(key):
                par = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] in under[key]), None)
                if par is not None:
                    del stack[par + 1:]
            while stack and (key, stack[-1][0]) in forbid:
                stack.pop()
            if rank and key in rank:                         # 사다리 — 단이 같거나 깊은 열린 줄은 부모가 아니다
                while stack and rank.get(stack[-1][0], -1) >= rank[key]:
                    stack.pop()
            if val == 1 and stack:
                under.setdefault(key, set()).add(stack[-1][0])
                if seen is not None:
                    seen.append((key, stack[-1][0], stack[-1][1]))
            lv = stack[-1][2] + 1 if stack else 1
        stack.append((key, val, lv, r))
        out[r] = lv
    return out


def evidence(frames_hits):
    """다시 시작 증거 — `(ev {(자식, 부모): (강한 수, 수)}, 처음 나온 차례 {서명: n})` · 시트를 넘어 합친다(문서 전체)."""
    ev, first = {}, {}
    for hits in frames_hits:
        for _r, s, _v in hits:
            first.setdefault(s, len(first))
        seen = []
        _toc(hits, set(), seen)
        for child, parent, pval in seen:
            if child == parent:
                continue
            strong, n = ev.get((child, parent), (0, 0))
            ev[(child, parent)] = (strong + (pval is not None and pval > 1), n + 1)
    return ev, first


def forbid_of(ev, first):
    """두 서명이 서로의 아래에서 다시 시작했다면 한 방향만 — 부모가 첫째가 아닌 다시 시작 → 횟수 → 먼저 나온 서명이 위."""
    out = set()
    for (c, p), score in ev.items():
        back = ev.get((p, c))
        if back and (back[0], back[1], -first[p]) > (score[0], score[1], -first[c]):
            out.add((c, p))                               # 반대 방향이 이긴다 — c는 p 아래로 가지 않는다
    return out


def code_ladder(frames):
    """**코드 사다리**(B132 ③ 폴백 · `rules` 방식) — 시트들의 줄(`[[(행, 글)]]`)에서 서명의 단 순서 `{"levels": [{"sigs": [...]}], "by": "코드"}`.

    다시 시작 증거(이긴 방향만)로 목차를 한 번 더 세워 실제로 선 부모 → 자식(진 방향을 닫은 뒤의 자리 — `1) › 가.`가 지면 `가.`는
    `1.` 아래)을 사슬로 보고 서명마다 가장 긴 사슬의 깊이가 단이다 · 증거가 없는 서명은 맨 위 단 · 같은 단 안의 차례는 처음 나온
    차례 · 역할 · 카테고리는 비운다(LLM 사다리 · 사람 힌트의 몫)."""
    fh = [hits_of(lines) for lines in frames]
    ev, first = evidence(fh)
    forbid = forbid_of(ev, first)
    edges = set()
    for hits in fh:
        seen = []
        _toc(hits, forbid, seen)
        edges |= {(c, p) for c, p, _v in seen if c != p and (c, p) not in forbid}
    level = {s: 0 for s in first}
    for _i in range(len(first) + 1):                      # 가장 긴 사슬 — 고리는 이긴 방향만 남아 없다(남아도 횟수로 끊긴다)
        changed = False
        for c, p in edges:
            if level.get(c, 0) < level.get(p, 0) + 1 <= len(first):
                level[c] = level[p] + 1
                changed = True
        if not changed:
            break
    out = {}
    for s in sorted(first, key=lambda s: (level[s], first[s])):
        out.setdefault(level[s], []).append(s)
    return {"levels": [{"sigs": out[k], "role": None, "category": None} for k in sorted(out)], "by": "코드"}


def rank_of(ladder):
    """사다리 → `{서명: 단 번호}`(0부터 · 위에서 아래)."""
    return {s: i for i, lv in enumerate((ladder or {}).get("levels") or []) for s in lv.get("sigs") or []}


def number_levels(lines, ladder=None):
    """`[(행, 글)]` → `{행: (레벨, 서명)}` — **목차는 이어짐 · 다시 시작으로 세운다**(B130 ① — 사람이 목차를 읽는 방식).

    같은 서명이 서수 1씩 이어지면 형제 · 첫째 서수(1 · 가 · A · ① · Ⅰ · (1) — 점 번호는 마지막 마디)로 다시 시작하면 바로 위 열린
    제목의 자식 — 같은 서명이 여러 단에 쓰여도 맞게 선다(레벨 = 목차 나무의 깊이). 방향은 사다리가 정한다(없으면 그 줄들의 코드
    사다리 — 두 서명이 서로의 아래에서 다시 시작했다면 한 방향만 · `forbid_of`)."""
    rank = rank_of(ladder) if ladder else None
    hits = hits_of(lines, set(rank or ()))
    if rank is None:
        ev, first = evidence([hits])
        forbid = forbid_of(ev, first)
    else:
        forbid = {(c, p) for c in rank for p in rank if rank[c] <= rank[p]}
    lv = _toc(hits, forbid, rank=rank)
    return {r: (lv[r], s) for r, s, _v in hits}


def toc_chains(lines, levels, parents=None):
    """목차의 부모 사슬 — `(주인 {행: 그 줄의 주인 제목}, chain(제목) → 그 제목과 조상 전부 · 위에서 아래로)` · 주인은 그 줄이 제목이면
    그 줄 · 아니면 그 위의 가장 가까운 제목 · `levels`는 `{제목 행: 단}`(단 = 목차 깊이) (B130 ②) · `parents`(`{제목 행: 부모 행}` —
    구조가 선 프레임)가 오면 부모는 그것이다(단 차례로 되짚지 않는다 · B132)."""
    parent, owner, st, cur = {}, {}, [], None
    parents = parents or {}
    for n, _t in lines:
        if n in levels:
            while st and st[-1][0] >= levels[n]:
                st.pop()
            parent[n] = parents[n] if n in parents and (parents[n] is None or parents[n] in levels) else (st[-1][1] if st else None)
            st.append((levels[n], n))
            cur = n
        owner[n] = cur

    def chain(h):
        out = []
        while h is not None and len(out) < 64:
            out.append(h)
            h = parent.get(h)
        return out[::-1]
    return owner, chain
