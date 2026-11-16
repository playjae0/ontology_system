# -*- coding: utf-8 -*-
"""칸 2.8 — **이름 표기 대조 키**(B179 ① — 결정 D 2단계) — 이름과 이름을 견주는 곳 전부가 부르는 함수 하나.

규칙은 셋뿐이다 — **공백 무시 · 라틴 대소문자 · 전각 → 반각**(U+FF01~FF5E → ASCII · 전각 공백도 공백). 접미어 · 기호 ·
호환 문자 펼치기는 맞추지 않는다(「커터 설비」 ≠ 「커터」). 키는 대조에만 쓰고 저장하지 않는다 — 저장 원문 · 문서 id 해시는
`core.state.ids.norm` 그대로다. 파서는 core를 import하지 않으므로(P1) 자리가 파서 쪽이고 core가 이것을 부른다(같은 입력 →
같은 키). 같은 키의 후보가 하나일 때만 「같다」는 부르는 쪽 규칙이다(둘 이상이면 지금처럼 미스).

글 속에서 이름을 찾는 곳(질의 링킹 · 렌즈 어휘 · 추출 맥락 · 보고 강조)은 이 키가 아니다 — 공백을 없애면 글 속 위치가
틀어진다(그 자리는 `core.state.ids.fold_latin`).
"""
from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

#: 전각 ASCII 구간(！ ~ ～) — 반각과의 거리
_WIDE_FIRST, _WIDE_LAST, _WIDE_SHIFT = 0xFF01, 0xFF5E, 0xFEE0


@lru_cache(maxsize=65536)
def _key(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if _WIDE_FIRST <= o <= _WIDE_LAST:
            ch = chr(o - _WIDE_SHIFT)
        if ch.isspace():
            continue
        if o < 128 or "LATIN" in unicodedata.name(ch, ""):
            ch = ch.lower()
        out.append(ch)
    return "".join(out)


def key(text) -> str:
    """이름 → 대조 키 — 공백을 없애고 · 라틴 글자는 소문자 · 전각 ASCII는 반각으로. 그 밖의 글자는 그대로."""
    return _key("" if text is None else str(text))


def _fold(s):
    """글자 수를 지키는 접기(전각 → 반각 · 라틴 소문자) — 뗄 자리를 원문에서 그대로 자른다."""
    return "".join(_key(ch) or ch for ch in s)


def split_axis(name, axis):
    """**극성 떼기 한 자리**(B205 ① — 결정 1 「이름에서 극성을 뺀다」) — `(개념 이름, 축 키)` · 못 떼면 `(name, None)`.
    찾는 극성은 축(`{키: 표시 이름}` — 골격 `AXIS_LABELS`)의 키와 표시 이름 전부 · 대소문자 · 전각 무시 · 앞(`anode x`) · 뒤(`x anode`) ·
    괄호(`x(anode)` · `(anode) x`) · 구분자(공백 · `_` · `-`) · 떼고 남은 것이 비면 떼지 않는다. 파서 · core(옛 기록 재생)가 같이 부른다."""
    if not name or not axis:
        return name, None
    f, sep = _fold(str(name)), r"[\s_\-]+"
    toks = sorted(((_fold(t), k) for k, lab in axis.items() for t in (k, lab) if t), key=lambda x: -len(x[0]))
    for t, k in toks:
        t = re.escape(t)
        for pat, cut in ((rf"^[(\[]\s*{t}\s*[)\]]\s*", "head"), (rf"^{t}{sep}", "head"),
                         (rf"\s*[(\[]\s*{t}\s*[)\]]\s*$", "tail"), (rf"{sep}{t}$", "tail")):
            m = re.search(pat, f)
            rest = (str(name)[m.end():] if cut == "head" else str(name)[:m.start()]).strip() if m else ""
            if rest:
                return rest, k
    return name, None
