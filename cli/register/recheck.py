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

**부착 대상 규칙**(B147 ① — 관문 G4J와 같은 함수 `parser.attach_rule`)도 같은 하위 실행이 싣는다 — 속성 · 내용의
`attach_to_field`가 개체 열이 아니면 **⚠**(멈추지 않음 — 인입하면 그 값은 보류된다) · 줄에 필드 · 대상 · 붙일 수 있는 선언
필드 · 다음 줄. 이미 등록된 스키마는 자동으로 고치지 않는다(사람이 다시 등록한다).

**재등록 다음 줄은 그대로 쳐서 도는 꼴이다**(B148 ⑦ — `revise_line` 한 자리 · 재대조 ⚠ · FAIL · 인입 사전 점검 · 인입 실패 블록이 같은
함수): `python -m cli.register generate <dt> <등록 층> <표본...> --revise` — 층은 스키마의 `layer` · 표본은 그 종류 등록 상태의 표본이
전부 있으면 그것(따옴표 처리) · 아니면 자리표시 `<표본...>` · mock이면 끝에 `--allow-mock`.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

from core import paths
from core.state import registry

KIT = paths.ROOT / "kit"
#: 판정 태그 → 고칠 자리(층 config 키)
_FIX = {"G4C": "categories(또는 relation_patterns)", "G4D": "relations",
        "G4E": "relation_patterns"}


def _exists(sample):
    p = Path(sample)
    return (p if p.is_absolute() else paths.ROOT / p).exists()


def revise_line(dt, schema=None, schema_only=False):
    """재등록 다음 줄(B148 ⑦) — `python -m cli.register generate <dt> <등록 층> <표본...> --revise` · 스키마 칸만 고치면
    (부착 대상 ⚠ — B147) `--schema-only`(운영 어댑터 그대로 · B150 ③)."""
    if schema is None:
        sc = registry.schema_path(dt)
        schema = json.loads(sc.read_text(encoding="utf-8")) if sc and sc.exists() else {}
    sp = paths.review(dt, "state.json")                      # 읽기만(폴더를 만들지 않는다 — 점검은 운영 폴더를 읽기만 · B111)
    try:
        got = [str(s) for s in (json.loads(sp.read_text(encoding="utf-8")).get("samples") or [])] if sp.exists() else []
    except (OSError, ValueError):
        got = []
    smp = " ".join(shlex.quote(s) for s in got) if got and all(_exists(s) for s in got) else "<표본...>"
    from core.llm import gateway
    allow = " --allow-mock" if gateway.use_mock() else ""        # mock이면 mock 관문의 플래그까지(그대로 쳐서 돈다)
    flag = "--schema-only" if schema_only else "--revise"
    return f"python -m cli.register generate {dt} {(schema or {}).get('layer') or '<층>'} {smp} {flag}{allow}"


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
                redo = (f" · 또는 {revise_line(dt, schema)}" if schema.get("payload_kind") != "prose" else "")
                out.append((dt, False, f"{dt:<14} FAIL — {f.replace('[FAIL] ', '')[:200]}\n"
                                       f"               다음 줄: {fix}{redo}"))
        for a in j.get("attach") or []:                    # 부착 대상 규칙 — ⚠ (B147 ①)
            out.append((dt, False, f"{dt:<14} ⚠ 부착 대상 — {a}\n"
                                   f"               다음 줄: {revise_line(dt, schema, schema_only=True)} "
                                   f"(인입은 멈추지 않는다 — 그 값은 보류된다)"))
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
