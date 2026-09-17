# -*- coding: utf-8 -*-
"""P3 공용 재료 — 등록 파이프라인 스위트 7종이 **같은 바닥**에서 돈다 (B78 2b).

파일 하나가 3,484행이었다. 칸별로 나누되 **바닥은 하나여야** 한다 — 초기화·헬퍼가
파일마다 복제되면 그중 하나만 고쳐지는 날이 오고, 그날 두 스위트가 다른 상태를
바닥으로 판정한다.

    from p3_common import *        # 헬퍼·상수
    setup()                        # 클린 + 골격 + 등록 초기화
    ...
    done()                         # 결과 줄 + 종료 코드

`allok`은 이 모듈이 소유한다 — `show()`가 그것을 갱신하고 `done()`이 읽는다.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kit"))

from cli import register as R                              # noqa: E402
from cli.register import (__main__ as Rmain, confirm as Rconfirm,   # noqa: E402
                          draft as Rdraft, gate as Rgate, generate as Rgen,
                          interview as Rivlog, ledger as Rledger, view as Rview)
from core.state import init, registry, store                           # noqa: E402
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.state.bootstrap import bootstrap                       # noqa: E402
from parser import pipeline, reader                        # noqa: E402

allok = True
RAW = ROOT / "tests" / "fixtures" / "raw"
REVIEW = _P.review()


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)

def _reg_src():
    """등록 파트의 소스 전량 — **파트가 파일 여럿이다**(B78 2b). 성질은 「등록 코드가
    그렇게 한다」이지 「어느 파일에 있다」가 아니므로, 파트를 통째로 읽는다."""
    return " ".join(_p.read_text(encoding="utf-8")
                    for _p in sorted((ROOT / "cli" / "register").glob("*.py")))


def run(*args):
    """CLI 진입점으로 부른다 — 플랫폼이 subprocess로 부르는 그 경로다(§16.1)."""
    # **회귀는 mock 관문 비대상이다**(B48) — 구현 환경에는 게이트웨이가 없고
    # 그 환경의 실행이 검증의 바닥이다(B12).
    flag = ["--allow-mock"] if args and args[0] in ("generate", "review", "confirm") else []
    # **LLM 생성 경로를 재는 시험은 `--no-basic`을 붙인다**(B59 ③). 표본이 전부 산문
    # 포맷이면 `generate`는 이제 **고정 어댑터로 간다** — 그것이 새 기본값이고,
    # TOC 표본은 형태 판정이 prose다. 이 헬퍼로 도는 시험들은 생성 세션(초안·
    # 재생성·문답)을 재므로 그 경로를 명시해야 한다. ③의 기본값 자체를 재는
    # 어서션은 이 헬퍼를 쓰지 않고 플래그 없이 직접 부른다.
    if args and args[0] == "generate":
        flag.append("--no-basic")
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register",
                           *args, *flag],
                          capture_output=True, text=True, cwd=str(ROOT))


def view_of(doc_type):
    return json.loads((REVIEW / doc_type / "view.json").read_text(encoding="utf-8"))


def reset(doc_type):
    registry.unregister(doc_type)
    shutil.rmtree(REVIEW / doc_type, ignore_errors=True)


def _call_names(node):
    """함수 하나가 부르는 이름들 — **표기를 가리지 않는다**(B78 2b).

    `harness(...)`와 `gate.harness(...)`는 같은 호출이다: 파트가 파일로 갈리면서
    표기가 갈렸을 뿐이고, 성질은 「그 함수가 그것을 부른다」이다.
    """
    import ast as _a
    out = []
    for c in _a.walk(node):
        if not isinstance(c, _a.Call):
            continue
        f = c.func
        out.append(f.id if isinstance(f, _a.Name)
                   else (f.attr if isinstance(f, _a.Attribute) else ""))
    return out


def setup():
    """깨끗한 상태에서 시작한다 — 등록부는 실행 산출물이다."""
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for dt in ("ipqc", "toc_report"):
        reset(dt)


def done():
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", "PASS — P3 완료판정 충족" if allok else "FAIL")
    sys.exit(0 if allok else 1)
