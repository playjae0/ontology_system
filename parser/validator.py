# -*- coding: utf-8 -*-
"""validator — 계약 self-check (파서_명세 §8 · CH2 2.2 · 카드 C14).

    ①3층 구조  ②좌표 존재  ③자기완결  ④payload_kind 정합

**실패는 문서 단위 단일이다**(C14): 위반 하나라도 있으면 통째 미인입 + `parse_failure`.
행 단위로 건너뛰면 "13행짜리 문서가 12행으로 조용히 들어간" 상태가 되고, 그 1행이
없다는 것을 아무도 모른다. 파서 측 검사는 문서 단위 실패로 착지하고, 에이전트 측
필드 검증은 큐로 착지한다 — 두 체계는 겹치지 않고 이어진다(D-2 확정).

**계층 미확정은 실패가 아니다**(D-5): 평면 폴백 + 표시 + `hierarchy_unresolved`.
구조를 못 읽은 것과 계약을 어긴 것은 다르다.
"""
from __future__ import annotations

ENVELOPE_KEYS = ("doc_id", "doc_type", "source_path", "revision",
                 "parsed_at", "parser_version", "adapter_version", "payload_kind")
PAYLOAD_KINDS = ("table", "prose")


def check(envelope, closed_list=None):
    """(ok, defects) — defects는 문서 단위 실패의 사유 목록이다."""
    d = []
    kind = envelope.get("payload_kind")

    # ④ payload_kind 정합 — 닫힌 2값이고, 실린 몸통과 맞아야 한다
    if kind not in PAYLOAD_KINDS:
        d.append(f"payload_kind가 닫힌 2값 밖이다 — {kind!r}")
    key = "records" if kind == "table" else "chunks"
    other = "chunks" if kind == "table" else "records"
    if kind in PAYLOAD_KINDS:
        if envelope.get(other):
            d.append(f"payload_kind={kind}인데 '{other}'가 실려 있다")
        if not envelope.get(key):
            d.append(f"payload_kind={kind}인데 '{key}'가 비어 있다")

    # ① 3층 구조 — 봉투 / 조각 공통 / payload
    for k in ENVELOPE_KEYS:
        if envelope.get(k) in (None, ""):
            d.append(f"봉투 필수 키 부재 — {k}")
    ctx = envelope.get("context")
    if ctx is not None and not isinstance(ctx, dict):
        d.append(f"context는 임의 딕셔너리다 — {type(ctx).__name__}")

    locs = []
    for i, piece in enumerate(envelope.get(key) or [], 1):
        loc = piece.get("source_locator")
        if not loc:
            d.append(f"{key}[{i}]: source_locator 부재 (조각 공통 필수)")
        else:
            locs.append(loc)
        # **좌표 존재 검사** — 문서 6 §6.2-5. "좌표 존재"는 **필드의 존재**이지
        # 닫힌 목록 대조가 아니다(대조는 인입 소관 — D-77). 값이 null인 것과
        # 키가 없는 것은 다르다: 후자면 인입의 필드 검증이 "부재"를 판정할 대상을
        # 잃고, 조각 공통 층(§2.2 계약 ①)이 계약이 아니라 어댑터별 재량이 된다.
        for ck in ("doc_type", "process_group", "process_ref", "electrode_type"):
            if ck not in piece:
                d.append(f"{key}[{i}]: 조각 공통 키 부재 — {ck} "
                         f"(값 null은 허용, 키 부재는 계약 위반)")
        # 정본 id는 파서가 부여하지 않는다 (틀 A7-1 — 에이전트 계산)
        bad = {"chunk_id", "record_id", "doc_hash"} & set(piece)
        if bad:
            d.append(f"{key}[{i}]: 파서가 정본 id를 부여했다 — {sorted(bad)}")
        # ③ 자기완결 — 상동 기호·미전개 흔적이 남아 있으면 안 된다
        for f, v in piece.items():
            if isinstance(v, str) and v.strip() in {"〃", "〝", "상동"}:
                d.append(f"{key}[{i}].{f}: 상동 기호가 해소되지 않았다")
        if kind == "prose" and not (piece.get("text") or piece.get("image_ref")):
            d.append(f"{key}[{i}]: prose 조각에 text도 image_ref도 없다")

    if len(set(locs)) != len(locs):
        dup = sorted({x for x in locs if locs.count(x) > 1})
        d.append(f"source_locator가 문서 내 유일하지 않다 — {dup[:5]}")

    return not d, d


def coord_report(envelope, closed_list):
    """좌표의 닫힌 목록 대조 — **보고이지 판정이 아니다.**

    목록 밖 좌표는 문서 단위 실패가 **아니다**: 좌표 태깅은 "닫힌 목록에서 선택
    또는 null"이고(§4), 목록 밖 이름의 처리는 **인입 소관**이다(`orphan_anchor` 큐).
    파서가 여기서 문서를 죽이면 파서가 골격을 판정하게 되고, 그 큐 kind는 영영
    도달 불가능해진다 — mock의 `레이저노칭` 한 행이 정확히 그 자리다.
    """
    if not closed_list:
        return {"checked": False}
    known = set()
    for n in closed_list:
        known.add(n["canonical"])
        known.update(n.get("aliases") or [])
    key = "records" if envelope.get("payload_kind") == "table" else "chunks"
    outside = sorted({p.get("process_ref") for p in (envelope.get(key) or [])
                      if p.get("process_ref") and p["process_ref"] not in known})
    missing = sum(1 for p in (envelope.get(key) or []) if not p.get("process_ref"))
    return {"checked": True, "outside_closed_list": outside, "no_coord": missing}
