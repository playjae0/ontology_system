# -*- coding: utf-8 -*-
"""칸 2.4 — **목차** — 번호 줄의 서수 · 번호 이어짐 · 다시 시작으로 세우는 목차와 그 부모 사슬 (B130 ①②).

    number_levels(lines)      `[(행, 글)]` → `{행: (레벨, 군)}` — 레벨 = 목차 나무의 깊이(엑셀 산문 · Word 같은 함수)
    toc_chains(lines, levels)  제목마다 부모 사슬 · 줄마다 주인 제목 — 청크 경로(`struct_map.split`)가 쓴다

번호 꼴 판정(`heading_family` · `number_shape`)은 `struct_map`이 갖고 여기는 그 위에서 목차만 세운다.
"""
from __future__ import annotations

import re

from parser.struct_map import DOTTED, heading_family, number_shape

#: **목차 규칙 판**(B130 ①) — 구조 확인의 확정 기록이 이 판을 적는다 · 판이 다른 옛 확정은 재생하지 않는다(목차가 틀렸을 수 있다)
TOC_VERSION = "toc-2"
_HANGUL = "가나다라마바사아자차카타파하"
_ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"


def number_value(text, shape):
    """줄 머리 번호의 서수(1부터) — 꼴마다 · 점 번호는 마지막 마디 · 읽지 못하면 None(`-`는 세지 않는다) (B126 ② · B130 ①)."""
    t = str(text or "").strip()
    if shape == "1.1":
        m = re.match(r"\d+(?:\.\d+)+", t)
        return int(m.group().split(".")[-1]) if m else None
    if shape in ("(1)", "1)", "1.", "제1장"):
        m = re.search(r"\d+", t)
        return int(m.group()) if m else None
    if shape in ("가.", "가)"):
        return _HANGUL.index(t[0]) + 1 if t and t[0] in _HANGUL else None
    if shape == "Ⅰ.":
        return _ROMAN.index(t[0]) + 1 if t and t[0] in _ROMAN else None
    if shape == "A.":
        return ord(t[0].upper()) - 64 if t and t[0].isalpha() and t[0].isascii() else None
    if shape == "①":
        return ord(t[0]) - 0x245F if t and 0x2460 <= ord(t[0]) <= 0x2473 else None
    return None


def _toc_key(text, fam, depth):
    """목차의 꼴 열쇠 — 번호 꼴 표기(`1)` · `(1)` · `가.` …) · 점 번호는 마디 수까지(`1.` · `1.1`은 다른 꼴)."""
    return ("1.", depth) if fam == DOTTED else (number_shape(text) or fam, 1)


def _toc(hits, forbid, seen=None):
    """열린 제목의 스택으로 목차를 세운다 — `{행: 단}` · `seen`이면 다시 시작한 자리 `(자식 꼴, 부모 꼴, 부모 서수)`를 적는다.

    ⓐ 열린 줄 가운데 같은 꼴 · 서수 − 1이 있으면 그 줄까지 닫고 형제 ⓑ 서수가 첫째면 맨 위 열린 제목의 자식(그 꼴이 그 부모 꼴
    아래로 가면 안 되는 방향이면 — `forbid` — 열린 줄을 닫고 그 위의 자식) ⓒ 둘 다 아니면 같은 꼴이 열려 있으면 그 형제 · 그
    꼴이 다시 시작한 부모 꼴이 열려 있으면 그 자식 · 아니면 맨 위의 자식."""
    stack, out, under = [], {}, {}
    for r, key, val in hits:
        sib = next((i for i in range(len(stack) - 1, -1, -1)
                    if stack[i][0] == key and val is not None and stack[i][1] == val - 1), None)
        if sib is None and val != 1:
            sib = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == key), None)
        if sib is not None:
            lv = stack[sib][2]
            del stack[sib:]
        else:
            if val != 1 and under.get(key):
                par = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] in under[key]), None)
                if par is not None:
                    del stack[par + 1:]
            while stack and (key, stack[-1][0]) in forbid:
                stack.pop()
            if val == 1 and stack:
                under.setdefault(key, set()).add(stack[-1][0])
                if seen is not None:
                    seen.append((key, stack[-1][0], stack[-1][1]))
            lv = stack[-1][2] + 1 if stack else 1
        stack.append((key, val, lv))
        out[r] = lv
    return out


def number_levels(lines):
    """`[(행, 글)]` → `{행: (레벨, 군)}` — **목차는 번호 이어짐 · 다시 시작으로 세운다**(B130 ① — 사람이 목차를 읽는 방식).

    같은 꼴 번호가 1씩 이어지면 형제 · 첫째 번호(1 · 가 · A · ① · Ⅰ · (1) — 점 번호는 마지막 마디)로 다시 시작하면 바로 위 열린 제목의
    자식 — 같은 꼴이 여러 단에 쓰여도 맞게 선다(레벨 = 목차 나무의 깊이). 같은 문서에서 두 꼴이 서로의 아래에서 다시 시작했다면
    한 방향만 남긴다(부모가 첫째가 아닌 다시 시작 → 횟수 → 먼저 나온 꼴이 위) — 진 방향의 자식 관계는 세우지 않는다(열린 줄을 닫고 그
    위의 자식). 점 번호는 마디 수가 꼴을 가른다(`1.1`은 `1.`의 자식 — 점 번호만 쓰는 시트의 레벨은 마디 수 그대로)."""
    hits, fam_of, first = [], {}, {}
    for r, t in lines:
        hf = heading_family(t)
        if not hf:
            continue
        key = _toc_key(t, *hf)
        hits.append((r, key, number_value(t, key[0] if key[0] != "1." else ("1." if key[1] == 1 else "1.1"))))
        fam_of[r] = hf[0]
        first.setdefault(key, len(first))
    seen = []
    _toc(hits, set(), seen)
    ev = {}
    for child, parent, pval in seen:
        if child == parent:
            continue
        strong, n = ev.get((child, parent), (0, 0))
        ev[(child, parent)] = (strong + (pval is not None and pval > 1), n + 1)
    forbid = set()
    for (c, p), score in ev.items():
        back = ev.get((p, c))
        if back and (back[0], back[1], -first[p]) > (score[0], score[1], -first[c]):
            forbid.add((c, p))                       # 반대 방향이 이긴다 — c는 p 아래로 가지 않는다
    lv = _toc(hits, forbid)
    return {r: (lv[r], fam_of[r]) for r, _k, _v in hits}


def toc_chains(lines, levels):
    """목차의 부모 사슬 — `(주인 {행: 그 줄의 주인 제목}, chain(제목) → 그 제목과 조상 전부 · 위에서 아래로)` · 주인은 그 줄이 제목이면
    그 줄 · 아니면 그 위의 가장 가까운 제목 · `levels`는 `{제목 행: 단}`(단 = 목차 깊이) (B130 ②)."""
    parent, owner, st, cur = {}, {}, [], None
    for n, _t in lines:
        if n in levels:
            while st and st[-1][0] >= levels[n]:
                st.pop()
            parent[n] = st[-1][1] if st else None
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
