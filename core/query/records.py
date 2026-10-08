# -*- coding: utf-8 -*-
"""칸 4.3 — **노드 원 레코드** — 질의가 닿은 노드를 가공 없이 그대로 싣는다 (B105 ⑤ · ⓖ).

처음 구축 단계라 사람이 눈으로 봐야 한다(사용자 결정 2026-10-08) — 링킹 노드(ⓐ)와 확장 노드(ⓑ)마다 저장된
레코드 그대로: canonical · 카테고리 · 겸(공통 config에서 계산 — 저장하지 않는다) · 상태 · 층 · 극성 · 단 ·
별칭(저장된 항목 그대로 — 출처 표기는 화면이 `alias_source`로 붙인다) · 값(`attrs` 그대로 — 이름 · 값 · 맥락 ·
출처) · 들어온 문서(`provenance`) · 닻까지의 길(`anchor` 한 자리). **문장 틀 0**(사실 문장은 ⓒ의 몫).

순서는 링킹 노드 → 확장 노드(층 · id 순 — 결정적) · 상한은 손잡이 `query_record_limit`(0 = 끔). 상한 밖 수는
`records_total`이 말한다. 계산은 이미 읽은 그래프에서만 — 판단 0 · 쓰기 0.
"""
from __future__ import annotations

import copy

from core.query import anchor as A

#: ⓖ 상한 — 노드 수(사내 손잡이 `query_record_limit` · 0 = 끔 · 가결정 D-186 — 창작 기본값)
RECORD_LIMIT = 20


def collect(direct_by_layer, collected, graphs, limit):
    """`(레코드 목록, 상한 전 수)` — 링킹 노드 먼저(`role` 링킹) · 확장 노드(`role` 확장)."""
    order, seen = [], set()
    for role, by in (("링킹", direct_by_layer), ("확장", collected)):
        for lay in sorted(by or {}):
            for nid in sorted(by[lay]):
                if nid not in seen:
                    seen.add(nid)
                    order.append((lay, nid, role))
    take = order[:max(0, int(limit))]
    if not take:
        return [], len(order)
    nodes, edges = A.lists(graphs)
    anc = A.anchors(nodes, edges)
    names = {n["id"]: n["name"] for n in nodes}
    from core.state import catalog
    out = []
    for lay, nid, role in take:
        g = graphs.get(lay)
        n = g.get(nid) if g is not None else None
        if n is None:
            n = next((g.get(nid) for g in graphs.values() if g.get(nid)), None)
        if n is None:
            continue
        try:
            also = sorted(catalog.categories_of(n) - {n.get("category")})
        except catalog.CatalogError:
            also = []
        out.append({"node_id": nid, "layer": n.get("layer") or lay, "role": role,
                    "canonical": n.get("canonical"), "category": n.get("category"), "also": also,
                    "status": n.get("status"), "polarity": n.get("polarity"), "tier": n.get("tier"),
                    "aliases": copy.deepcopy(n.get("aliases") or []),
                    "attrs": copy.deepcopy(n.get("attrs") or {}),
                    "provenance": list(n.get("provenance") or []),
                    "where": A.path_text(nid, anc, names)})
    return out, len(order)
