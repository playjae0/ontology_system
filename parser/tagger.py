# -*- coding: utf-8 -*-
"""tagger — 정규 조각 → 계약 JSON (파서_명세 §3 · CH2 2.2).

    좌표 태깅 + 봉투 구성 + context + 이미지 placeholder의 요약 완성

**좌표 태깅의 닫힌 목록은 골격 전 노드다**(A11-6 · D-45 — 개념 + 인스턴스).
구 "세부공정 목록" 서술은 폐기됐다. 목록의 실물은 `data/skeleton_closed_list.json`
스냅샷이며(D-11 확정), 파서와 에이전트가 **같은 파일**을 본다 — 파서는 이 레포의
그래프를 읽지 않기 때문이다(D-9).

**상위·개념 해상도 선택은 오류가 아니라 저해상도 부착이다.** 문서가 "탭용접"이라고만
말하면 개념 노드가 답이고, 축값이 확정이면 인입 측이 인스턴스로 하강한다(A11-9 ⓪).
태거는 **문서가 말한 것**을 적을 뿐 해상도를 올리지 않는다.

`process_group`은 태거가 지어내지 않는다 — **tier:main 조상 파생**이다(A11-7).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "skeleton_closed_list.json"

MOCK_IMAGE_SUMMARY = "MOCK 요약: {image_ref}"      # USE_MOCK 고정 문자열 (증분0 §5-3)


def closed_list(layer="process", path=None):
    """골격 닫힌 목록 스냅샷을 읽는다 — 없으면 빈 목록(조용히 그래프로 가지 않는다)."""
    p = Path(path or SNAPSHOT)
    if not p.exists():
        return []
    return (json.loads(p.read_text(encoding="utf-8")).get(layer) or {}).get("nodes", [])


def surfaces(nodes):
    """닫힌 목록의 선택지 — canonical + alias 전량. LLM은 여기서 **고르기만** 한다."""
    out = {}
    for n in nodes:
        out[n["canonical"]] = n
        for a in n.get("aliases") or []:
            out.setdefault(a, n)
    return out


MAX_UP = 16                                       # 조상 추적 깊이 제한 (순환 방어)


def group_of(node, nodes):
    """`process_group` = **tier:main 조상**(A11-7) — 지어내지 않고 골격에서 딴다.

    스냅샷이 실어 준 `parent` 링크를 타고 올라간다. 자기가 이미 main이면 자기다.
    문자열을 파싱하지 않는다 — 판정 근거는 필드다(A11-8).
    """
    by_canon = {n["canonical"]: n for n in nodes}
    cur, seen = node, set()
    for _ in range(MAX_UP):
        if cur is None or cur["canonical"] in seen:
            return None
        if cur.get("tier") == "main":
            return cur["canonical"]
        seen.add(cur["canonical"])
        cur = by_canon.get(cur.get("parent"))
    return None


def tag(pieces, *, layer="present", nodes=None, ref_field="process_ref"):
    """좌표 태깅 — 조각이 든 좌표를 닫힌 목록과 대조하고 `process_group`을 파생한다.

    **목록 밖이면 비운다**(null 허용 — §4 "닫힌 목록에서 선택 또는 null").
    검증은 인입 소관이고 파서는 좌표를 판정하지 않는다 — 태거가 임의로 고쳐 넣으면
    그 순간 파서가 골격을 해석하게 된다.
    """
    nodes = nodes if nodes is not None else closed_list(layer)
    idx = surfaces(nodes)
    out = []
    for p in pieces:
        r = dict(p)
        ref = r.get(ref_field)
        node = idx.get(ref) if ref else None
        if ref and node is None:
            r[ref_field] = ref                      # 그대로 둔다 — orphan_anchor는 인입 몫
        if node is not None and not r.get("process_group"):
            g = group_of(node, nodes)
            if g:
                r["process_group"] = g
        out.append(r)
    return out


def complete_images(pieces, summarize=None):
    """이미지 placeholder의 요약 완성 — **코어가 호출한다**(어댑터 아님, §5 규약 3).

    USE_MOCK은 고정 문자열이다(증분0 §5-3). 실물 경로는 `summarize(image_ref)`.
    """
    out = []
    for p in pieces:
        r = dict(p)
        ref = r.get("image_ref")
        if ref and not r.get("text"):
            r["text"] = (summarize(ref) if summarize
                         else MOCK_IMAGE_SUMMARY.format(image_ref=ref))
            r.setdefault("meta", {})["image_summary"] = True
        out.append(r)
    return out


def envelope(adapter, doc_id, source_path, pieces, *, revision="R1",
            parsed_at="2026-01-05T00:00:00", parser_version="p1-1.0",
            context=None, struct_map=None):
    """봉투 구성 — **파서가 만든다**(CH2 2.2). 정본 id는 넣지 않는다(A7-1).

    `adapter_version`은 봉투에 **1회** 기록한다(A7-3) — 조각마다 복사하지 않는다.
    구조 지도가 있으면 함께 보존한다(같은 지도 → 같은 분할 → 같은 chunk_id).
    """
    a = adapter.ADAPTER if hasattr(adapter, "ADAPTER") else adapter
    kind = a["payload_kind"]
    env = {
        "doc_id": doc_id, "doc_type": a["doc_type"], "source_path": source_path,
        "revision": revision, "parsed_at": parsed_at,
        "parser_version": parser_version, "adapter_version": a["adapter_version"],
        "context": dict(context or {}), "payload_kind": kind,
        ("records" if kind == "table" else "chunks"): pieces,
    }
    if struct_map is not None:
        env["struct_map"] = struct_map
    return env
