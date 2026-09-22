# -*- coding: utf-8 -*-
"""G6 공용 재료 — 플랫폼·스캔 스위트 여섯이 **같은 바닥**에서 돈다 (B78 2c).

    from g6_common import *
    ...
    done()
"""
from __future__ import annotations

import contextlib as _ctx
import hashlib
import io as _io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import platform as PF                          # noqa: E402
from cli import scan as SC                              # noqa: E402
from core.state import init, store                                  # noqa: E402
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.state.bootstrap import bootstrap, load_config, open_graph  # noqa: E402
from core.build.extract import EXTRACT_DIR                    # noqa: E402
from core.state import ops                                    # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def data_hash():
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((_P.data()).rglob("*.json"))}



# ── 인입 화면 시험의 공용 재료 (B78 2c) — 두 스위트가 같은 봉투를 쓴다
import subprocess as _sp72                                         # noqa: E402
from core.build.entry import run_document as _run72                # noqa: E402


def _env72(doc_id, n=5, ref=None):
    """CP01 봉투를 앞 n행으로 줄여 쓴다 — 화면·큐 시험의 입력."""
    import json as _j
    e = _j.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
    e["doc_id"], e["records"] = doc_id, e["records"][:n]
    if ref:
        for r in e["records"]:
            r["process_ref"] = ref
    return e


def done():
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", "PASS — G6 완료판정 충족" if allok else "FAIL")
    sys.exit(0 if allok else 1)

