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

from parser import coord_pairs, deck, form, profile, reader, reading, reading_pick, render, struct_map, struct_rule, tagger
from parser.adapters import basic_docx, basic_ppt, basic_prose_xlsx

#: 손잡이 이름 → (모듈, 속성). 속성이 둘이면 값은 두 칸짜리 목록이다. **같은 뜻이 여러 모듈에 있으면 `[(모듈, 속성), …]`**
#: (B185 ① — 손잡이 하나가 전부에 넣는다 · 기본값은 첫 자리).
TARGETS = {
    "heading_max_chars": (struct_map, ("HEADING_MAX_CHARS",)),
    "chunk_rows": (struct_map, ("CHUNK_MIN", "CHUNK_MAX")),
    "chunk_max_chars": (struct_map, ("CHUNK_MAX_CHARS",)),
    "sheet_thresholds": (form, ("SHEET_THRESHOLDS",)),
    "form_auto": (form, ("AUTO_MIN_FOR", "AUTO_MAX_AGAINST")),
    "skeleton_column_pct": (tagger, ("SKELETON_COLUMN_PCT",)),
    "coord_pair_pct": (coord_pairs, ("COORD_PAIR_PCT",)),
    "structure_chunk_over": (struct_rule, ("CHUNK_OVER",)),
    "ppt_slide_chars": (basic_ppt, ("SLIDE_MAX_CHARS",)),
    # ── B185 ① — LLM 입력 글자 · 행 · 등록 열 프로파일 · 그림 · 변환(기본값 = 지금 상수)
    "image_context_chars": [(basic_ppt, ("CONTEXT_CHARS",)), (basic_prose_xlsx, ("CONTEXT_CHARS",)),
                            (basic_docx, ("CONTEXT_CHARS",))],
    "deck_box_chars": [(deck, ("BOX_CHARS",)), (reading, ("BOX_CHARS",))],
    "deck_note_chars": (deck, ("NOTE_CHARS",)),
    "deck_head_chars": (deck, ("HEAD_CHARS",)),
    "sheet_sample_rows": (form, ("SHEET_SAMPLE_ROWS",)),
    "sheet_sample_chars": (form, ("SHEET_SAMPLE_CHARS",)),
    "profile_sparse_empty_ratio": (profile, ("SPARSE_EMPTY_RATIO",)),
    "profile_sample_values": (profile, ("SAMPLE_VALUES",)),
    "profile_sample_chars": (profile, ("SAMPLE_CHARS",)),
    "profile_full_list_max": (profile, ("FULL_LIST_MAX",)),
    "profile_observe_rows": (reader, ("OBSERVE_ROWS",)),
    "profile_min_unique_values": (form, ("MIN_VALUES_FOR_UNIQUE",)),
    "decor_share": (reading_pick, ("DECOR_SHARE",)),
    "convert_timeout_s": (render, ("SOFFICE_TIMEOUT",)),
    # llm.json(`IMAGE_MAX_EDGE` — 그림 긴 변 · core 캡처와 같은 값)이 주는 값 — knobs.json 키가 아니다(`core.state.knobs.apply`가 넣는다)
    "image_max_edge": (render, ("MAX_EDGE",)),
}
#: knobs.json 밖에서 오는 주입(llm.json) — `show knobs`의 닫힌 목록에 들지 않는다
FROM_LLM = ("image_max_edge",)


def _sites(name):
    t = TARGETS[name]
    return t if isinstance(t, list) else [t]


def _read(mod, attrs):
    vals = [getattr(mod, a) for a in attrs]
    return dict(vals[0]) if isinstance(vals[0], dict) else (vals[0] if len(vals) == 1 else vals)


_DEFAULTS = {name: _read(*_sites(name)[0]) for name in TARGETS}


def defaults():
    """코드 상수 = 기본값 (import 시점의 값 — 주입으로 바뀌지 않는다)."""
    return {k: (dict(v) if isinstance(v, dict) else (list(v) if isinstance(v, list) else v))
            for k, v in _DEFAULTS.items()}


def current():
    return {name: _read(*_sites(name)[0]) for name in TARGETS}


def apply(values=None):
    """주입 — `values`에 없는 손잡이는 기본값으로 되돌린다(한 번 넣은 값이 남지 않는다)."""
    values = values or {}
    for name in TARGETS:
        v = values.get(name, _DEFAULTS[name])
        for mod, attrs in _sites(name):
            if len(attrs) == 1:
                setattr(mod, attrs[0], dict(v) if isinstance(v, dict) else v)
            else:
                for a, x in zip(attrs, v):
                    setattr(mod, a, x)
    # 파생값 — 구간의 중앙은 구간에서 나온다(숫자를 두 곳에 두지 않는다)
    struct_map.CHUNK_CENTER = (struct_map.CHUNK_MIN + struct_map.CHUNK_MAX) / 2
