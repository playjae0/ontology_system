# -*- coding: utf-8 -*-
"""칸 1.5 — **config를 바꾸면 등록 스키마를 다시 대조한다** (B90 ⑤).

층 config나 공통 config를 고치면 이미 등록된 doc_type의 스키마가 새 어휘 밖으로 떨어질
수 있다. 그 사실을 인입이 시작된 뒤(커밋 게이트의 조용한 거부 · 관문 FAIL)에 알면 늦다 —
`bootstrap`과 `doctor`가 등록된 doc_type **전부**를 대조해 doc_type마다 한 줄을 낸다.

판정은 **관문과 같은 함수**다(`kit/check_vocab.py` → `gate_checks.check_vocab` — G4C·G4D·
G4E). 킷은 core를 모르므로 subprocess로 부르고 층 자리를 건넨다(관문과 같은 결).

경고 하나를 더 낸다: **prose doc_type이 등록된 층이 좌표 카테고리를 말하지 않는다**
(`categories`에도 `relation_patterns`에도 없다) — 그 층의 prose 문서는 좌표를 못 단다
(prose 스키마의 좌표 블록이 그 카테고리를 부른다 — 관문 G4C가 그 자리에서 선다).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

from core import paths
from core.state import registry

KIT = paths.ROOT / "kit"
#: 판정 태그 → 고칠 자리(층 config 키)
_FIX = {"G4C": "categories(또는 relation_patterns)", "G4D": "relations",
        "G4E": "relation_patterns"}


def _speaks(cfg, category):
    return category in (cfg.get("categories") or {}) or any(
        category in (p.get("src"), p.get("dst")) for p in cfg.get("relation_patterns") or [])


def run():
    """`[(doc_type, ok, 줄)]` — 줄은 화면에 그대로 싣는다. 등록 0이면 빈 목록."""
    from core.state.bootstrap import COORD_CATEGORY, load_config
    dts = registry.all_doc_types()
    targets = [(dt, registry.schema_path(dt)) for dt in sorted(dts)]
    targets = [(dt, p) for dt, p in targets if p and p.exists()]
    if not targets:
        return []
    r = subprocess.run([sys.executable, str(KIT / "check_vocab.py"),
                        "--layers", str(paths.layers())] + [str(p) for _dt, p in targets],
                       capture_output=True, text=True, cwd=str(paths.ROOT),
                       stdin=subprocess.DEVNULL)
    got = {}
    for ln in r.stdout.splitlines():
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        got[j["schema"]] = j
    out = []
    for dt, p in targets:
        j = got.get(str(p)) or {"ok": False, "lines": [f"대조를 못 돌렸다 — {r.stderr.strip()[-160:]}"]}
        schema = json.loads(p.read_text(encoding="utf-8"))
        lay = schema.get("layer")
        if j["ok"]:
            out.append((dt, True, f"{dt:<14} PASS — 층 {lay} 어휘 안"))
        else:
            fails = [ln for ln in j["lines"] if ln.startswith("[FAIL]")] or j["lines"]
            for f in fails:
                tag = next((t for t in _FIX if t in f), None)
                # 관문 문면이 가리키는 층이 고칠 층이다(걸침 필드는 `target_layer`의 층)
                m = re.search(r"는 (\S+) (?:카테고리|관계)에 없다", f)
                fl = m.group(1) if m else lay
                fix = (f"{paths.show(paths.layers(fl, 'config.json'))}의 {_FIX[tag]}"
                       if tag else "스키마와 층 config를 대조한다")
                redo = (f" · 또는 python -m cli.register generate {dt} --revise"
                        if schema.get("payload_kind") != "prose" else "")
                out.append((dt, False, f"{dt:<14} FAIL — {f.replace('[FAIL] ', '')[:200]}\n"
                                       f"               다음 줄: {fix}{redo}"))
        if schema.get("payload_kind") == "prose" and lay:
            try:
                speaks = _speaks(load_config(lay), COORD_CATEGORY)
            except (OSError, ValueError):
                speaks = False
            if not speaks:
                out.append((dt, False, f"{dt:<14} ⚠ 층 {lay}이 {COORD_CATEGORY}를 말하지 않는다 "
                                       f"(categories에도 relation_patterns에도 없다) — 이 층의 "
                                       f"prose 문서는 좌표를 못 단다"))
    return out


def screen(title="[bootstrap] 등록 스키마 재대조"):
    """화면 블록 — 등록 0이면 아무것도 찍지 않는다. FAIL·경고 수를 돌려준다."""
    rows = run()
    if not rows:
        return 0
    print(f"{title} — doc_type {len({dt for dt, _ok, _l in rows})}종")
    for _dt, _ok, line in rows:
        print(f"  {line}")
    return sum(1 for _dt, ok, _l in rows if not ok)
