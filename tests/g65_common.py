# -*- coding: utf-8 -*-
"""G6.5 공용 재료 — 계약 미배선 수리 스위트 넷이 **같은 바닥**에서 돈다 (B78 2c).\n\n    from g65_common import *\n    ...\n    done()\n"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.build import gate
from core.state import init, ops, store
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.dictionary import Dictionary                            # noqa: E402
from core.state.bootstrap import bootstrap, load_config, open_graph  # noqa: E402
from core.build.build import Builder                               # noqa: E402
from core.build.extract import EXTRACT_DIR, checkpoint_path        # noqa: E402
from core.state.ids import norm                                    # noqa: E402
from core.matcher import MATCH, resolve                      # noqa: E402
from core.build.entry import finalize, run_document  # noqa: E402
from core.build.prose import build_prose

allok = True
DOCS = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / "parsed" / f"{name}.json").read_text(encoding="utf-8"))


def fresh():
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for d in DOCS:
        run_document(load(d))
    finalize()


def q_of(kind, doc=None):
    return [x for x in store.read(store.QUEUE, [])
            if x["kind"] == kind and (doc is None or x["doc_id"] == doc)]


def chunks_of(doc):
    ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    return {cid: c for cid, c in ch.items() if c["doc_id"] == doc}


def node_by(layer, canonical):
    g = open_graph(layer)
    return next((n for n in g.nodes.values()
                 if n["canonical"] == canonical and ops.is_live(n)), None)


PROSE = {"source_path": "(합성)", "revision": "R1", "parsed_at": "2026-01-05T00:00:00",
         "parser_version": "m", "adapter_version": "m", "context": {},
         "payload_kind": "prose", "doc_type": "ppt_quality"}
TABLE = {"source_path": "(합성)", "revision": "R1", "parsed_at": "2026-01-05T00:00:00",
         "parser_version": "m", "adapter_version": "m", "context": {"model": "M1"},
         "payload_kind": "table", "doc_type": "cp"}
C1 = {"source_locator": "XQ01-C001", "process_group": "조립", "process_ref": "노칭",
      "electrode_type": "both", "text": "안전 수칙을 준수한다.", "section": "본문", "meta": {}}
CPREC = {"source_locator": "XA-R1", "process_group": "조립", "process_ref": "노칭",
         "electrode_type": "both", "설비": "노칭 프레스", "관리항목": "노칭 정밀도"}



def done():
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", "PASS — G6.5 완료판정 충족" if allok else "FAIL")
    sys.exit(0 if allok else 1)


# ── 테스트 전용 층 덧칠 (B90 · B91 — 두 스위트가 같은 바닥에서 돈다) ─────────────
OV = json.loads((ROOT / "tests/fixtures/layers_b90/overlay.json").read_text(encoding="utf-8"))


def _rw(path, fn):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    fn(c)
    Path(path).write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def overlay(*, component=False, also=False):
    """클린 → 상태 루트의 층 config·카탈로그에 덧칠 → 골격. 레포 seed는 건드리지 않는다."""
    init.init(fresh_=True)
    lays = ("quality", "process") if component else ("quality",)
    for lay in lays:
        def _f(c, lay=lay):
            c["categories"].update(OV[lay]["categories"])
            c["relation_patterns"] += OV[lay]["relation_patterns"]
            c.setdefault("query_traverse", {}).update(OV[lay].get("query_traverse") or {})
        _rw(_P.layers(lay, "config.json"), _f)
    if component:
        _rw(_P.layers("process", "skeleton.json"),
            lambda c: [c["ALIASES"].setdefault(k, []).extend(v)
                       for k, v in OV["process"]["aliases"].items()])

    def _c(c):
        c["categories"].update({k: v for k, v in OV["common"]["categories"].items()
                                if component or k != "Component"})
        if also:
            for k, v in OV["also"].items():
                c["categories"][k]["also"] = v
    _rw(_P.common(), _c)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
