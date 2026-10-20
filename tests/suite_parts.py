# -*- coding: utf-8 -*-
"""칸 0.3 — **합친 스위트의 조각 실행** — 한 칸의 시험 조각을 한 프로세스에서 차례로 (B131 ④).

    from suite_parts import run
    run(("part_a.py", "part_b.py"))                 합친 스위트 파일의 몸 전부 — 조각마다 클린 → 실행 · 종료 코드를 모은다
    python tests/test_<칸>.py [<조각 이름 일부…>]    그 조각만(개발 중 — 판정은 doctor)

조각은 `tests/part_*.py` — 옛 스위트 파일 그대로다(제 이름공간 · 제 `done()` · 어서션 그대로). **조각마다 클린 상태에서
시작한다**는 옛 전제를 지킨다: 첫 조각은 doctor의 클린 · 그 뒤 조각은 앞에 `run.py init --fresh --all`(이 프로세스와 같은 루트).
조각 하나가 붉어도 나머지를 돈다 — 무엇이 몇 개 어긋났는지를 한 번에 본다.
"""
from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.llm import gateway as _iso                              # noqa: E402
_iso.isolate()   # 시험은 셸 환경과 무관하게 격리 환경에서 돈다 (B111 ① · 조각보다 먼저)


def _clean():
    subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh", "--all"], capture_output=True,
                   cwd=str(ROOT), stdin=subprocess.DEVNULL)


def run(parts):
    pick = [a for a in sys.argv[1:] if not a.startswith("-")]
    chosen = [p for p in parts if not pick or any(k in p for k in pick)]
    rc = 0
    for i, part in enumerate(chosen):
        if i:
            _clean()
        print(f"\n{'━' * 62}\n조각 {i + 1}/{len(chosen)} — {part}")
        try:
            runpy.run_path(str(ROOT / "tests" / part), run_name="__main__")
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            rc = rc or code
    sys.exit(rc)
