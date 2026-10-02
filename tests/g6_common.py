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
from cli import _screen as _scr                         # noqa: E402
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


# ── 산문 표본(prose 엑셀) doc_type — 시트 역할(B83)·추출 화면(B97) 두 스위트가 같은 것을 쓴다
RFQ = ROOT / "tests" / "fixtures" / "raw" / "RFQ01.xlsx"
DT = "prose_xlsx_basic"          # 레포의 기본 prose 엑셀 어댑터 — 표본용으로 등록한다
SCHEMA = {"doc_type": DT, "schema_version": 1, "layer": "process",
          "payload_kind": "prose", "use_blocks": ["common_core", "process_coord"],
          "_note": "B83 회귀 — 시트 역할 관문의 표본은 prose 엑셀이다",
          "fields": {}, "edges": []}


def _register():
    """표본 doc_type을 **등록 단에 세운다** — 인입은 미등록을 거부한다(B3).

    내장(`tests/fixtures/schemas/`)에 넣지 않는 이유: 내장 목록은 `doctor`·
    `platform doctypes` 화면에 그대로 뜬다 — 회귀용 이름을 거기 얹지 않는다.
    """
    p = _P.schemas(f"{DT}.json")
    _P.ensure(p)
    p.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[DT] = {"doc_type": DT, "status": "registered", "layer": "process",
               "schema": f"schemas/{DT}.json",
               "adapter": str(ROOT / "parser" / "adapters" / "basic_prose_xlsx.py"),
               "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _unregister():
    dts = store.read(store.DOC_TYPES, {})
    dts.pop(DT, None)
    store.write(store.DOC_TYPES, dts)
    _P.schemas(f"{DT}.json").unlink(missing_ok=True)


def _run(*argv, answers=None):
    """`run.py`를 돌린다 — `answers`가 있으면 **pty**로(관문은 tty에서만 산다)."""
    if answers is None:
        r = _sp72.run([sys.executable, str(ROOT / "run.py"), *argv],
                      capture_output=True, text=True, cwd=str(ROOT),
                      env={**os.environ, "USE_MOCK": "1"}, stdin=_sp72.DEVNULL)
        return r.stdout + r.stderr
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                             # pragma: no cover
        os.environ["USE_MOCK"] = "1"
        os.chdir(str(ROOT))
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv])
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    os.waitpid(pid, 0)
    return _scr.strip_ansi(out.decode("utf-8", "replace"))


def _ingest(*extra, answers=None):
    return _run("ingest-file", str(RFQ), "--doc-type", DT, "--allow-mock",
                *extra, answers=answers)


def done():
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", "PASS — G6 완료판정 충족" if allok else "FAIL")
    sys.exit(0 if allok else 1)

