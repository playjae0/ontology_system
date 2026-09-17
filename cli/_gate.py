# -*- coding: utf-8 -*-
"""mock 관문 — 사람이 치는 운영 명령은 mock에서 **실행 전에 멈춘다** (문서 7 §7.6-B-1 · B48).

모드 표시(B42 ⑤)만으로는 모자랐다: 표시는 지나칠 수 있고, *"mock으로 돌아가니
괜찮구나"*가 그대로 굳는다. 그래서 표시 다음에 관문을 둔다 — 계속하려면 사람이
`--allow-mock`을 **적어야** 한다.

**자리는 CLI 진입점 한 곳이다.** 지점마다 두면 판독처가 다시 여럿이 되고, 그것이
판정필요-15가 신고한 병(파서가 따로 읽어 갈렸다)의 재발이다. 여기서 `gateway.use_mock()`
하나를 부르고 끝낸다.

**대상이 아닌 것**: `doctor`·`init`·`bootstrap`·`llm-check`·`skeleton-confirm`·회귀.
구현 환경에는 게이트웨이가 없고 **그 환경의 실행이 검증의 바닥**이기 때문이다(B12) —
회귀를 관문 뒤에 두면 mock 없이는 회귀가 돌지 않게 되어 바닥이 사라진다.
"""
from __future__ import annotations

from core.llm import gateway

FLAG = "--allow-mock"

MESSAGE = ('mock 모드입니다 — 실산출이 아닙니다.\n'
           '  ▶ 다음 줄 — 둘 중 하나:\n'
           '     (mock 산출로 진행한다)  python run.py <친 명령> --allow-mock\n'
           '     (실호출로 돌린다)      python run.py llm-check   '
           '→ gateway.json의 "USE_MOCK": 0 또는 USE_MOCK=0')


def _migrate_message(command="", pair=None):
    """이관 전 실행의 **거부 문면** — 원인 · 지금 잰 것 · 근거 · 다음 줄(B61 · B77 ③).

    문면이 한 자리인 이유: 같은 거부가 `run.py`와 각 `cli/*` 진입에서 다른 말로
    나오면 사람은 두 가지 고장을 본 것으로 읽는다. 판정은 `core/state/migrate.py`가
    하고 **화면은 여기다**(D-149 ③ — core는 화면을 갖지 않는다).
    """
    from core.state import migrate, store
    old, home = pair or migrate.needs_migration()
    mark = old / migrate.LEGACY_MARK[0] / migrate.LEGACY_MARK[1]
    return (f"[{command or '상태'}] 이관 먼저 — 옛 배치의 상태를 읽지 않는다 "
            f"(B78 1b · 문서 7 §7.8)\n"
            f"  지금 잰 것 — 옛 등록부 {mark} 있음 · 새 상태 루트 {home} 비어 있음\n"
            f"  근거 — {home / 'registry' / store.DOC_TYPES} 없음\n"
            f"  ▶ 다음 줄:\n"
            f"     python run.py platform migrate --from {old}\n"
            f"     python run.py platform migrate --from {old} --dry-run   "
            f"(무엇이 어디로 가는지만 본다)")


def require_migrated(command=""):
    """**옛 배치 그대로면 읽기 전에 멈춘다** (B78 1b · 문서 7 §7.8).

    조용히 옛 자리를 읽으면 사람은 이관한 줄 알고, 그때부터 옛 자리와 새 자리가
    갈라진 채 며칠이 간다 — B77 ③이 신고한 「옮기다 빠짐」의 상류다. 판정과 문면은
    `core/state/migrate.py`가 갖고(D-149 ③ — core는 화면을 갖지 않는다) 여기서는 멈춘다.
    """
    from core.state import migrate
    pair = migrate.needs_migration()
    if pair:
        raise SystemExit(_migrate_message(command, pair))   # [상태] 문면=_migrate_message


def require_live_or_allow(argv, *, command=""):
    """`argv`에서 플래그를 떼고 돌려준다. mock인데 플래그가 없으면 **멈춘다.**

    돌려주는 값을 호출부가 그대로 써야 한다 — 플래그가 남으면 그것이 표본 경로나
    질문 문장으로 흘러 들어간다(실측 계열: 힌트를 따옴표 없이 준 사고).
    """
    require_migrated(command)                    # 이관 먼저 — 옛 자리를 읽지 않는다
    argv = list(argv)
    allow = FLAG in argv
    while FLAG in argv:
        argv.remove(FLAG)
    if allow or not gateway.use_mock():
        return argv
    # **표시 후 멈춤**(B42 ⑤ → B48) — 무엇으로 도는지 먼저 말하고 그다음 막는다.
    print(f"  {gateway.mode_line()}")
    # **stdout으로 낸다** — 플랫폼 창구(`cli/platform.py`)가 subprocess의 stdout만
    # 넘기므로, stderr로 내면 사람 화면에 모드 줄만 뜨고 사유가 사라진다.
    print(f"[{command or 'mock 관문'}] {MESSAGE}")
    raise SystemExit(2)                          # [상태] 문면=MESSAGE
