# -*- coding: utf-8 -*-
"""mock 관문 — 사람이 치는 운영 명령은 mock에서 **실행 전에 멈춘다** (문서 7 §7.6-B-1 · B48).

모드 표시(B42 ⑤)만으로는 모자랐다: 표시는 지나칠 수 있고, *"mock으로 돌아가니
괜찮구나"*가 그대로 굳는다. 그래서 표시 다음에 관문을 둔다 — 계속하려면 사람이
`--allow-mock`을 **적어야** 한다.

**자리는 CLI 진입점 한 곳이다.** 지점마다 두면 판독처가 다시 여럿이 되고, 그것이
판정필요-15가 신고한 병(파서가 따로 읽어 갈렸다)의 재발이다. 여기서 `llm.use_mock()`
하나를 부르고 끝낸다.

**대상이 아닌 것**: `doctor`·`init`·`bootstrap`·`llm-check`·`skeleton-confirm`·회귀.
구현 환경에는 게이트웨이가 없고 **그 환경의 실행이 검증의 바닥**이기 때문이다(B12) —
회귀를 관문 뒤에 두면 mock 없이는 회귀가 돌지 않게 되어 바닥이 사라진다.
"""
from __future__ import annotations

from core import llm

FLAG = "--allow-mock"

MESSAGE = ('mock 모드입니다 — 실산출이 아닙니다. 계속하려면 --allow-mock '
           '(실호출: llm.json의 "USE_MOCK": 0 또는 USE_MOCK=0)')


def require_live_or_allow(argv, *, command=""):
    """`argv`에서 플래그를 떼고 돌려준다. mock인데 플래그가 없으면 **멈춘다.**

    돌려주는 값을 호출부가 그대로 써야 한다 — 플래그가 남으면 그것이 표본 경로나
    질문 문장으로 흘러 들어간다(실측 계열: 힌트를 따옴표 없이 준 사고).
    """
    argv = list(argv)
    allow = FLAG in argv
    while FLAG in argv:
        argv.remove(FLAG)
    if allow or not llm.use_mock():
        return argv
    # **표시 후 멈춤**(B42 ⑤ → B48) — 무엇으로 도는지 먼저 말하고 그다음 막는다.
    print(f"  {llm.mode_line()}")
    # **stdout으로 낸다** — 플랫폼 창구(`cli/platform.py`)가 subprocess의 stdout만
    # 넘기므로, stderr로 내면 사람 화면에 모드 줄만 뜨고 사유가 사라진다.
    print(f"[{command or 'mock 관문'}] {MESSAGE}")
    raise SystemExit(2)
