# -*- coding: utf-8 -*-
"""칸 1.5 — **관문의 화면**: 판정 줄 규격(`LINE_RE`)·`show()`·실행 신원 한 줄.

판정 줄의 문면은 등록 화면이 **정규식으로 집는다**(`cli/register/gate.py`) — 그래서
규격의 정본이 한 자리에 있어야 하고, 그 자리가 여기다(B59 ① · B78 2c에서 옮겼다).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ok_all = True


LINE_RE = r"^\s*\[(PASS|FAIL)\]\s+(G[0-9A-Z]{2})\s\s(.*?)(?:\s\s—\s(.*))?$"


# 분할 요약 줄의 표시 — **정본은 여기다**(등록 화면이 이 이름으로 집는다).
SPLIT_MARK = "[분할요약] "


def show(label, ok, detail=""):
    """판정 한 줄. **라벨은 `G\d\w  `로 시작한다** — 그것이 코드다.

    코드 없는 라벨을 만들지 않는다: 화면이 「무엇이 막았나」를 사람이 전달할 수
    있는 형태로 말해야 하고, 빠진 한 줄은 그 줄에서만 조용히 안 말한다.
    """
    global ok_all
    ok_all = ok_all and bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


# **공개 API는 모듈이 정본이다**(B65 ①) — 목록을 여기 베끼면 normalizer가 자랄 때
# 관문이 옛 목록으로 판정하고, 그 거짓 검출을 지우려 다시 베끼게 된다.
from parser import normalizer as normalizer_mod            # noqa: E402


def _where():
    """**어느 폴더의 어느 판으로 돌았나** — 한 줄 (B59 ④).

    사내가 코드 폴더를 나눠 가며 갱신한다. 같은 표본에서 다른 결과가 나오면 가장
    먼저 가려야 할 것이 「어느 사본이 돌았나」인데, 상대 경로만 남으면 그것이
    갈리지 않는다. 그래서 **절대 경로 + 커밋**을 관문 산출의 첫 줄에 박는다.

    `state.json`의 경로가 상대인 것은 그대로 둔다 — 그건 옳다(폴더를 옮겨도 같은
    문서다 · D-110). 여기 찍는 것은 **실행 환경의 신원**이지 자산의 주소가 아니다.

    git이 없거나 레포가 아니어도 조용히 넘어간다 — 관문이 이것 때문에 멈추면 안 된다.
    """
    rev = ""
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5,
                           cwd=str(ROOT))
        if r.returncode == 0 and r.stdout.strip():
            rev = r.stdout.strip()
            d = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=5,
                               cwd=str(ROOT))
            if d.returncode == 0 and d.stdout.strip():
                rev += "+dirty"          # 커밋만 찍으면 미커밋 수정이 숨는다
    except Exception:
        pass
    return f"[관문] ROOT={ROOT}" + (f" · git {rev}" if rev else " · git 미확인")
