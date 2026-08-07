# -*- coding: utf-8 -*-
"""n10 — 부트스트랩 seed·config (G2, 기존 1b 흡수).

시스템 최초 가동 = **공정정보층 1개 내장**. 이 층은 R1 층 등록 절차를 거치지
않은 **내장 층**이며(카드 J10), 그 지위가 registry에 `builtin`으로 명문화된다.
품질지식층은 여기서 내장하지 않는다 — G4의 3′이 신규 층 등록 절차의 첫
검증 대상으로 추가한다. 그것이 절차 자체의 검증이기 때문이다.

**코드에 층 어휘 0**(B1) — 공정·노칭·스태킹 같은 말이 이 파일에 없다.
골격 트리·카테고리 정의문·관계는 전부 `layers/<layer>/config.json`이 소유하며
여기는 그 값을 읽어 심는 절차만 갖는다. 층이 늘어도 이 코드는 그대로다.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import store
from .graph import GraphStore

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT / "layers"

SEED_STATUS = "seed"        # 사람이 파일로 심은 것 (용어 대장 status 어휘)
SEED_PROV = ["seed"]


def load_config(layer):
    return json.loads((LAYERS / layer / "config.json").read_text(encoding="utf-8"))


def open_graph(layer):
    """층 그래프를 연다. 경로 조립은 GraphStore가 소유한다 — 여기서 하지 않는다."""
    return GraphStore.for_layer(layer).load()


def bootstrap(layer="process"):
    """골격을 심고 사전에 등재한 뒤 registry에 내장 층으로 올린다."""
    cfg = load_config(layer)
    skel = cfg["skeleton"]
    child_rel = skel["relations"]["child"]      # 자식 → 부모
    sib_rel = skel["relations"]["sibling"]      # 형제 순서

    g = GraphStore.for_layer(layer).load()
    g.build_begin()

    dictionary = store.read(store.DICTIONARY, {})

    def register_surface(surface, nid):
        dictionary.setdefault(surface, [])
        if nid not in dictionary[surface]:
            dictionary[surface].append(nid)

    ids = {}
    for parent, children in skel["data"].items():
        pid = g.add_node(parent, skel["category"], SEED_STATUS,
                         attrs={"process_no": None}, provenance=SEED_PROV)
        ids[parent] = pid
        register_surface(parent, pid)
        prev = None
        for child in children:
            cid = g.add_node(child, skel["category"], SEED_STATUS,
                             attrs={"process_no": None}, provenance=SEED_PROV)
            ids[child] = cid
            register_surface(child, cid)
            g.add_edge(cid, child_rel, pid, SEED_STATUS, SEED_PROV)
            if prev is not None:
                g.add_edge(prev, sib_rel, cid, SEED_STATUS, SEED_PROV)
            prev = cid

    metrics = g.build_end()
    store.write(store.DICTIONARY, dictionary)

    reg = store.read(store.REGISTRY, {})
    reg[layer] = {
        "layer": layer,
        "status": "builtin",                    # R1 절차 불경유 (J10) — D-8
        "skeleton_version": cfg.get("skeleton_version"),
        "categories": list(cfg["categories"]),
        "relations": cfg["relations"],
    }
    store.write(store.REGISTRY, reg)
    return g, metrics, ids
