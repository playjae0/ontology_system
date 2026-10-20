# -*- coding: utf-8 -*-
"""칸 2.4 — **꼴 서명** — 줄 머리의 번호를 글자 종류로 일반화한 서명과 서수 (B132 ② — 번호 패턴 한 벌).

    signature("1.기본사양")  → ("9.", 1)     signature("(가) 범위")  → ("(가)", 1)     signature("4)검수방법") → ("9)", 4)
    signature("1-1 공급부")  → ("9-9", 1)    signature("■ 개요")    → ("■", None)     signature("b. 지정")    → ("a.", 2)

**정해 둔 꼴 목록이 없다** — 숫자 → `9` · 한글 가~하 → `가` · 영문 대문자 → `A` · 소문자 → `a` · 원숫자 → `①` · 괄호 숫자 → `⑴` ·
로마 숫자 → `Ⅰ` · 장절(`제1장`) → `제9장` · 기호는 그대로. 띄어쓰기 · 줄 길이와 무관하다(번호 뒤 공백이 없어도 · 60자가 넘어도 같은
서명 — 60자 문턱은 「자르는 자리인가」에만 쓴다 · `struct_map.HEADING_MAX_CHARS`). 서수는 마지막 마디의 값(`1.2` → 2)이고 기호 · 글머리표는
서수가 없다(None).

판정은 하지 않는다 — 어느 서명이 제목의 단인지는 계층 사다리(LLM 또는 코드)가 정한다(`parser/toc.py`).
"""
from __future__ import annotations

HANGUL = "가나다라마바사아자차카타파하"
ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
_ROMAN_ASCII = {"I": 1, "V": 5, "X": 10}
#: 글머리 기호 — 서명은 기호 그대로 · 서수 없음
BULLETS = "-–•·▪▫■□◆◇○●◎※▶►▷*+"
#: 마디 뒤의 구분 글자 · 여는 괄호 · 닫는 괄호
_DELIM = ".)]-:"
_OPEN = "(["
_CLOSE = ")]"
_UNITS = "장절조편관"
MAX_ATOMS = 4


def _roman_value(s):
    if all(c in ROMAN for c in s):
        return sum(ROMAN.index(c) + 1 for c in s) if len(s) > 1 else ROMAN.index(s) + 1
    total, prev = 0, 0
    for c in reversed(s):
        v = _ROMAN_ASCII[c]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def _atom(t, i):
    """`(서명 조각, 값, 다음 자리)` 또는 None — 숫자 묶음 · 한 글자(한글 · 영문) · 로마 숫자 · 원숫자."""
    n = len(t)
    c = t[i]
    if c.isdigit() and c.isascii():
        j = i
        while j < n and t[j].isdigit() and t[j].isascii():
            j += 1
        return "9", int(t[i:j]), j
    if "①" <= c <= "⑳":
        return "①", ord(c) - 0x245F, i + 1
    if "⑴" <= c <= "⒇":
        return "⑴", ord(c) - 0x2473, i + 1
    if c in ROMAN:
        j = i
        while j < n and t[j] in ROMAN:
            j += 1
        return "Ⅰ", _roman_value(t[i:j]), j
    if c in "IVX":
        j = i
        while j < n and t[j] in "IVX" and j - i < 4:
            j += 1
        if j < n and t[j] in ".)":                    # `I.` `V.` `X.` · `IV)`는 로마로 읽는다(B87 · D-168 ①)
            return "Ⅰ", _roman_value(t[i:j]), j
    if c in HANGUL:
        return "가", HANGUL.index(c) + 1, i + 1
    if "A" <= c <= "Z":
        return "A", ord(c) - 64, i + 1
    if "a" <= c <= "z":
        return "a", ord(c) - 96, i + 1
    return None


def _head(text):
    """`(서명, 서수, 머리 길이)` 또는 None — 앞 공백은 건너뛴다(그 수는 들여쓰기 재료 · 여기서는 세지 않는다)."""
    t = str(text or "")
    lead = len(t) - len(t.lstrip())
    t = t.lstrip()
    if not t:
        return None
    if t[0] in BULLETS and not (t[0] in "-–" and len(t) > 1 and t[1].isdigit()):
        return t[0], None, lead + 1
    if t.startswith("제"):
        j = 1
        while j < len(t) and t[j] == " ":
            j += 1
        k = j
        while k < len(t) and t[k].isdigit():
            k += 1
        while k < len(t) and t[k] == " ":
            k += 1
        if k > j and k < len(t) and t[k] in _UNITS:
            return f"제9{t[k]}", int(t[j:k].strip()), lead + k + 1
        return None
    i, sig, val, atoms = 0, "", None, 0
    if t[i] in _OPEN:
        sig += t[i]
        i += 1
    while i < len(t) and atoms < MAX_ATOMS:
        got = _atom(t, i)
        if got is None:
            return None
        piece, val, j = got
        alpha = piece in ("가", "A", "a")
        nxt = t[j] if j < len(t) else ""
        if alpha and not (nxt in _DELIM or (sig[:1] in _OPEN and nxt in _CLOSE)):
            return None                                 # `가나다` · `Abc` — 글자 하나 뒤에는 구분 글자가 있어야 번호다
        sig, i, atoms = sig + piece, j, atoms + 1
        if i < len(t) and t[i] in _CLOSE + ".:":
            sig += t[i]
            i += 1
            if i < len(t) and (t[i].isdigit() and t[i].isascii()) and sig.endswith("."):
                continue                                # `1.2` · `1.2.3`
            break
        if i < len(t) and t[i] == "-" and i + 1 < len(t) and t[i + 1].isdigit():
            sig += "-"
            i += 1
            continue                                    # `1-1`
        if piece == "9" and (i >= len(t) or t[i] in " \t　"):
            break                                       # `1 개요` — 숫자 뒤 공백
        if i < len(t) and t[i] in "-–" and piece != "9":
            sig += t[i]
            i += 1
            break
        if piece == "9" and i < len(t) and not t[i].isspace():
            return None                                 # `2024년` · `1.5mm` — 숫자 뒤에 글이 붙으면 번호가 아니다
        if piece == "①" or piece == "⑴" or piece == "Ⅰ":
            break
        return None
    if not atoms or (sig[:1] in _OPEN and not sig.endswith(tuple(_CLOSE))):
        return None
    return sig, val, lead + i


def signature(text):
    """`(서명, 서수)` 또는 `(None, None)` — 판정 아님."""
    h = _head(text)
    return (h[0], h[1]) if h else (None, None)


def strip_head(text):
    """줄 글자에서 번호 머리를 뗀 이름 — 번호가 없으면 그대로(앞뒤 공백 · 셀 이음 `|`만 뗀다)."""
    t = str(text or "")
    h = _head(t)
    rest = t[h[2]:] if h else t
    out = rest.strip().lstrip("|").strip()
    return out or t.strip()
