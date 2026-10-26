# -*- coding: utf-8 -*-
"""칸 1.5 — **부착 대상 규칙** — 값(속성 · 내용)은 그 행의 개체 열(또는 선언된 anchor)에 붙는다 (B147 ①).

**판정은 `kind_of` 하나다** — 등록 관문(킷 G4J) · 등록 스키마 재대조(`kit/check_vocab.py` → `cli/register/recheck`) ·
표 구축의 보류 사유(`core/build/table`)가 같은 함수를 부른다(두 벌 금지 — 좌표 쌍 판정 `coord_pairs.verdict`와 같은 결).

표 구축은 스키마 `fields`에 **선언된** 필드만 role 핸들러로 해소한다(`table._row_roles`) — 좌표(구조 필드 `process_ref` …)는
따로 해소하고(`table._row_anchor`) 블록(`use_blocks`) 필드는 스키마가 쓴 것이 아니라 참조한 것이다. 그래서 role
`attribute` · `content`의 `attach_to_field`가 가리킬 수 있는 것은 **선언된 `entity` · `anchor` 필드**뿐이다 — 그 밖을
가리키면 값이 있는 행은 전부 보류된다(사내 CP 실측 — 2026-10-26). 좌표에 매다는 관계는 엣지 `@process_ref`로 쓴다.

파서 자리라 core를 모른다 — 구조 필드 · 블록 필드 이름은 호출자가 건넨다(킷은 `gate_tables` · 구축은 `loop.STRUCTURAL`).
코드에 층 어휘 0 · doc_type · 열 이름 분기 0.
"""
from __future__ import annotations

#: 값 role — `attach_to_field`를 갖는 것(entity의 `attach_to_field`는 이 규칙 밖)
VALUE_ROLES = ("attribute", "content")
#: 부착 대상이 될 수 있는 role
TARGET_ROLES = ("entity", "anchor")
#: 대상이 무엇인가 — 붙일 수 없는 셋(+ 선언됐지만 role이 다른 것은 `role <r>`)
KIND_STRUCT, KIND_BLOCK, KIND_UNDECLARED = "구조 필드(좌표 · 시스템이 직접 읽는다)", "블록 필드(use_blocks)", "선언 밖 이름"


def kind_of(fields, target, structural=(), blocks=()):
    """`attach_to_field`가 가리키는 `target`이 무엇인가 — None이면 붙일 수 있는 선언 필드 · 아니면 그 까닭 한 마디.

    `fields`는 스키마가 **선언한** 필드(`schema["fields"]` — 블록 전개 전) · `structural` · `blocks`는 그 이름 집합."""
    t = str(target or "")
    if t.startswith("@") or t in set(structural):
        return KIND_STRUCT
    if t in set(blocks):
        return KIND_BLOCK
    spec = (fields or {}).get(t)
    if not isinstance(spec, dict):
        return KIND_UNDECLARED
    if spec.get("role") not in TARGET_ROLES:
        return f"role {spec.get('role')} 필드"
    return None


def can(fields, structural=(), blocks=()):
    """붙일 수 있는 선언 필드 목록(선언 차례) — FAIL · ⚠ 문면이 담는다(자동 재생성 갈래)."""
    return [f for f in (fields or {}) if kind_of(fields, f, structural, blocks) is None]


def problems(fields, structural=(), blocks=()):
    """`[{field, role, target, kind, can}]` — 붙일 수 없는 대상을 가리킨 값 필드(선언 차례) · 없으면 빈 목록."""
    ok = can(fields, structural, blocks)
    out = []
    for f, spec in (fields or {}).items():
        if not isinstance(spec, dict) or spec.get("role") not in VALUE_ROLES or not spec.get("attach_to_field"):
            continue
        k = kind_of(fields, spec["attach_to_field"], structural, blocks)
        if k:
            out.append({"field": f, "role": spec["role"], "target": spec["attach_to_field"], "kind": k, "can": ok})
    return out


def line(p):
    """한 건의 문면 — 관문 FAIL 상세 · 재대조 ⚠ 줄이 같은 글이다."""
    return (f"'{p['field']}'({p['role']})의 attach_to_field '{p['target']}'는 {p['kind']} — 표 구축이 부착 대상으로 "
            f"해소하지 않는다(값이 있는 행은 전부 보류) · 붙일 수 있는 선언 필드: {', '.join(p['can']) or '없음'}")
