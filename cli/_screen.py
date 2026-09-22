# -*- coding: utf-8 -*-
"""칸 0.3 — 화면 공용: **색은 특이점에만** · 전역 화면 플래그 · 색 벗기기 (B81 ③).

사내 실측(2026-09-22): 인입 화면의 글자가 다 같아서 **특이점이 안 보였다**(NEW·
불확실·orphan·실패). 색은 장식이 아니라 **판단이 갈린 자리를 눈에 넣는 장치**다 —
그래서 「전부 예쁘게」가 아니라 **특이점에만** 칠한다(사용자 확정).

**켜지는 조건 셋**(하나라도 아니면 끈다): 표준출력이 터미널이다 · `NO_COLOR`
환경변수가 없다 · `--no-color`를 주지 않았다. 파이프·리다이렉트·로그 파일에는
ESC가 한 바이트도 나가지 않는다 — 문면 검사·어서션·상태 거부 스캐너가 문자열을
그대로 읽어야 하기 때문이다(색이 문면을 바꾸지 않는다).

표준 라이브러리만 쓴다(ANSI 문자열 — 코어 필수 외부 의존 0).
"""
from __future__ import annotations

import os
import re
import sys

#: ANSI 조각 — 이름으로만 쓰고 숫자는 여기 한 자리에 둔다.
_C = {"reset": "\033[0m", "bold": "\033[1m", "reverse": "\033[7m",
      "red": "\033[31m", "yellow": "\033[33m", "green": "\033[32m",
      "dim": "\033[2m"}

#: **특이점 표** — verdict·사건 이름 → 색. 목록에 없는 것은 **칠하지 않는다**.
KINDS = {
    "new": ("yellow",),                      # 새로 생겼다 — 사람이 볼 자리
    "uncertain": ("red",),
    "lowres": ("red",),
    "orphan": ("red", "bold"),               # 좌표 미해소 — 붙지 못했다
    "gate_reject": ("red", "bold"),
    "fail": ("red", "bold"),                 # [FAIL] · [결함] · 실패 —
    "match": ("green",),                     # LLM이 붙인 값
    "banner": ("reverse",),                  # 중간·끝 요약 한 줄
    "dim": ("dim",),
}

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

#: `--no-color`를 본 적이 있는가 — 진입점이 `take_flags()`로 정한다.
_OFF = False
#: `-v`를 본 적이 있는가 — 로깅 레벨과 값 줄의 상세를 함께 가른다.
VERBOSE = False


def enabled(stream=None):
    """색을 켜는가 — 셋 다 참일 때만."""
    if _OFF or os.environ.get("NO_COLOR"):
        return False
    s = stream or sys.stdout
    try:
        return bool(s.isatty())
    except (AttributeError, ValueError):
        return False


def paint(text, kind=None, *, stream=None):
    """`kind`가 특이점 표에 있고 색이 켜져 있으면 칠한다 — 아니면 **그대로**."""
    parts = KINDS.get(kind or "")
    if not parts or not enabled(stream):
        return text
    return "".join(_C[p] for p in parts) + text + _C["reset"]


def banner(text, *, stream=None):
    """중간·끝 요약 한 줄 — 배경 반전으로 눈에 띄게(사용자 확정)."""
    return paint(text, "banner", stream=stream)


def strip_ansi(text):
    """색을 벗긴 문자열 — **어서션·문면 검사는 이것을 거쳐 잰다.**"""
    return _ANSI_RE.sub("", text or "")


def take_flags(argv):
    """전역 화면 플래그를 **떼어내고** 돌려준다 — `(argv, {verbose, no_color})`.

    떼어내는 이유는 B75의 `--allow-mock`과 같다: 남으면 그것이 표본 경로나 질문
    문장으로 흘러 들어간다. 자리는 진입점 하나다(`run.py` · `python -m cli.*`).
    """
    global _OFF, VERBOSE
    out, opts = [], {"verbose": False, "no_color": False}
    for a in list(argv):
        if a in ("-v", "--verbose"):
            opts["verbose"] = True
        elif a == "--no-color":
            opts["no_color"] = True
        else:
            out.append(a)
    _OFF = _OFF or opts["no_color"]
    VERBOSE = VERBOSE or opts["verbose"]
    return out, opts
