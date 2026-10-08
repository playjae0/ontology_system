# -*- coding: utf-8 -*-
"""칸 0.5 — **파서가 받는 사내 손잡이 값** (B91 ⑤) — 파서는 `core`를 import하지 않는다.

값의 자리는 코드 한 곳이다 — 각 모듈의 상수(`struct_map.CHUNK_MAX_CHARS` 등)가 **기본값**이고,
사내가 `$ONTO_HOME/knobs.json`으로 바꾼 값은 경계 밖(`core/state/knobs.py` — 운영 · 킷은
`--knobs` 플래그)에서 여기로 **주입**된다(좌표 스냅샷 자리 주입과 같은 결). 이 모듈은 값을
검증하지 않는다 — 검증(닫힌 목록 · 형)은 주입하는 쪽의 일이다.

주입은 모듈 속성을 바꾼다 — 읽는 자리가 전부 `struct_map.X`처럼 속성으로 읽으므로(값 복사
0) 한 번 넣으면 전 경로가 따라온다. 기본값은 import 시점에 한 번 잡아 두어 다시 넣으면
언제든 되돌아간다.
"""
from __future__ import annotations

from parser import coord_pairs, form, struct_map, tagger

#: 손잡이 이름 → (모듈, 속성). 속성이 둘이면 값은 두 칸짜리 목록이다.
TARGETS = {
    "heading_max_chars": (struct_map, ("HEADING_MAX_CHARS",)),
    "chunk_rows": (struct_map, ("CHUNK_MIN", "CHUNK_MAX")),
    "chunk_max_chars": (struct_map, ("CHUNK_MAX_CHARS",)),
    "sheet_thresholds": (form, ("SHEET_THRESHOLDS",)),
    "form_auto": (form, ("AUTO_MIN_FOR", "AUTO_MAX_AGAINST")),
    "sheet_min_hits": (form, ("SHEET_MIN_HITS",)),
    "skeleton_column_pct": (tagger, ("SKELETON_COLUMN_PCT",)),
    "coord_pair_pct": (coord_pairs, ("COORD_PAIR_PCT",)),
}


def _read(mod, attrs):
    vals = [getattr(mod, a) for a in attrs]
    return dict(vals[0]) if isinstance(vals[0], dict) else (vals[0] if len(vals) == 1 else vals)


_DEFAULTS = {name: _read(mod, attrs) for name, (mod, attrs) in TARGETS.items()}


def defaults():
    """코드 상수 = 기본값 (import 시점의 값 — 주입으로 바뀌지 않는다)."""
    return {k: (dict(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v))
            for k, v in _DEFAULTS.items()}


def current():
    return {name: _read(mod, attrs) for name, (mod, attrs) in TARGETS.items()}


def apply(values=None):
    """주입 — `values`에 없는 손잡이는 기본값으로 되돌린다(한 번 넣은 값이 남지 않는다)."""
    values = values or {}
    for name, (mod, attrs) in TARGETS.items():
        v = values.get(name, _DEFAULTS[name])
        if len(attrs) == 1:
            setattr(mod, attrs[0], dict(v) if isinstance(v, dict) else v)
        else:
            for a, x in zip(attrs, v):
                setattr(mod, a, x)
    # 파생값 — 구간의 중앙은 구간에서 나온다(숫자를 두 곳에 두지 않는다)
    struct_map.CHUNK_CENTER = (struct_map.CHUNK_MIN + struct_map.CHUNK_MAX) / 2
