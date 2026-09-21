# -*- coding: utf-8 -*-
"""G1·G2와 **자리 스위트**의 공용 바닥 (B79 — `test_g1_g2.py` 834행 분할).

한 파일에 둘이 있었다: ①G1+G2 완료판정(저장 계층·근거 축 id·부트스트랩) ②자리와
경계(B78의 자리 소유자·모듈 머리말·코드 지도 · B79의 층 자산·미정의 이름·루트 출처).
둘은 **바뀌는 이유가 다르다** — 앞은 저장·주소 규격이, 뒤는 자리 배치가 바꾼다.

    from g1_common import *        # 헬퍼·상수
    ...
    done("G1+G2 완료판정 충족")    # 결과 줄 + 종료 코드

`allok`은 이 모듈이 소유한다 — `show()`가 갱신하고 `done()`이 읽는다.
"""
from __future__ import annotations

import ast as _ast78
import json
import os
import re
import re as _re
import shutil
import shutil as _shutil2
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from core.state import init, store                                   # noqa: E402
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.state.bootstrap import bootstrap, load_config, open_graph  # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def reset():
    """**깨끗한 그래프에서 전체 재빌드** — 클린의 정의는 진입점이 갖는다(§7.6-4)."""
    init.init(fresh_=True)
    return bootstrap("process", echo=False)


def done(what):
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", f"PASS — {what}" if allok else "FAIL")
    sys.exit(0 if allok else 1)
