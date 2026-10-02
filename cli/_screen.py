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
import threading as _threading
import unicodedata

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


# ── 표의 폭 — 한글은 두 칸이다 (자리 하나 · B83 ②) ──────────────────────────
def w(text):
    """동아시아 폭 — 한글은 두 칸이다. 표가 어긋나면 눈 검수가 느려진다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in str(text))


def pad(text, n):
    return str(text) + " " * max(1, n - w(text))


def cut(text, n):
    out = ""
    for c in str(text):
        if w(out) + w(c) > n:
            return out + "…"
        out += c
    return out


def usage_line(since=None):
    """**LLM 사용량 한 줄** — LLM을 부를 수 있는 사용자 명령의 끝 줄 문구는 이 함수 하나다(B96 ③).

    `since`는 명령 시작점의 `gateway.usage_total()` — 그 차이를 센다(없으면 프로세스 누계).
    mock이면 0이다. 수는 게이트웨이 누계 그대로(화면이 제 계산을 하지 않는다).
    """
    from core.llm import gateway
    u = gateway.usage_total()
    b = since or {}

    def d(k):
        return int(u.get(k, 0)) - int(b.get(k, 0))
    return (f"LLM 사용량 — 호출 {d('calls'):,}회 · 토큰 {d('total_tokens'):,}"
            f"(입력 {d('prompt_tokens'):,} · 출력 {d('completion_tokens'):,})"
            + (f" · **응답 잘림 {d('truncated')}회**" if d("truncated") else ""))


# ── 시간 기준 누적 줄 (B97 ②) ───────────────────────────────────────────────
#: 누적 줄 간격(초). 시험은 줄여서 잰다 — 사내 조정 손잡이가 아니다(화면 박자).
TICK_SECONDS = 30.0
#: 사람에게 묻는 동안은 누적 줄을 내지 않는다(입력 줄이 밀리지 않게).
HOLD = _threading.Event()


def ask(prompt):
    """사람에게 묻는다 — 묻는 동안 누적 줄을 멈춘다. EOF·중단은 호출부가 받는다."""
    HOLD.set()
    try:
        return input(prompt)
    finally:
        HOLD.clear()


class ticker:
    """**LLM을 오래 부르는 단계의 누적 줄** — 한 자리(B97 ②).

        with _screen.ticker("파싱", where=lambda: "추출 3/40"):
            ...

    - 호출이 처음 늘면 한 번: `── LLM 사용 시작 — <단계>`
    - `TICK_SECONDS`마다(한 호출이 오래 걸려도 — 시간 기준):
      `── 30초 · <어디> · 호출 n · 토큰 n · 경과 m분 s초`
    - 수는 게이트웨이 누계 그대로다(화면이 제 계산을 하지 않는다). mock이고 호출이 늘지
      않으면 아무것도 내지 않는다 — mock 화면은 그대로다.
    """

    def __init__(self, label, where=None):
        self.label, self.where = label, where or (lambda: label)
        self._stop = _threading.Event()
        self._t = None

    def __enter__(self):
        from core.llm import gateway
        import time
        self._gw, self._time = gateway, time
        self._c0 = gateway.usage_total()["calls"]
        self._t0 = time.monotonic()
        self._t = _threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t is not None:
            self._t.join(timeout=2)
        return False

    def _run(self):
        from core.state import log
        _log = log.get(__name__)
        started, last = False, self._time.monotonic()
        while not self._stop.wait(min(0.5, TICK_SECONDS / 4)):
            u = self._gw.usage_total()
            moved = u["calls"] > self._c0
            if moved and not started:
                started = True
                print(f"   ── LLM 사용 시작 — {self.label}", flush=True)
            now = self._time.monotonic()
            if now - last < TICK_SECONDS or HOLD.is_set():
                continue
            last = now
            if not (moved or not self._gw.use_mock()):
                continue
            s = int(now - self._t0)
            line = (f"   ── {int(TICK_SECONDS)}초 · {self.where()} · 호출 {u['calls']:,} · "
                    f"토큰 {u.get('total_tokens', 0):,} · 경과 {s // 60}분 {s % 60}초")
            print(line, flush=True)
            _log.info(line.strip())
