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


def layer_of_category(category):
    """그 카테고리를 **선언한 층**을 찾는다.

    품질층 문서의 `process_ref`가 공정층 골격을 가리키는 것이 대표 사례다 —
    걸침 필드는 다른 층 그래프에 기록된다(명세 §15.7 규칙 A).
    어느 층이 무엇을 선언했는지는 config가 알고 있으므로 코드는 층 이름을 모른다(B1).
    """
    from router import discover
    for lay in discover():
        if category in load_config(lay).get("categories", {}):
            return lay
    return None


def open_graph(layer):
    """층 그래프를 연다. 경로 조립은 GraphStore가 소유한다 — 여기서 하지 않는다."""
    return GraphStore.for_layer(layer).load()


def bootstrap(layer="process"):
    """골격을 심고 사전에 등재한 뒤 registry에 층을 올린다.

    골격의 **모양**(tree | flat)도 **등록 지위**(builtin | registered)도 config가
    값으로 선언한다 — 코드가 층 이름으로 가르면 그 자체가 층 어휘다(B1).
    골격을 선언하지 않은 층은 심을 것이 없으므로 건너뛴다.
    """
    cfg = load_config(layer)
    skel = cfg.get("skeleton")
    if not skel:
        return None, None, {}

    g = GraphStore.for_layer(layer).load()
    g.build_begin()

    dictionary = store.read(store.DICTIONARY, {})

    def register_surface(surface, nid):
        dictionary.setdefault(surface, [])
        if nid not in dictionary[surface]:
            dictionary[surface].append(nid)

    def plant(canonical):
        """이미 심긴 골격은 **다시 심지 않는다** — 부트스트랩은 멱등해야 한다.

        의미 축 id는 발급(ULID)이라 다시 심으면 같은 개념에 새 id가 붙어
        노드가 배로 늘고 provenance·엣지가 갈라진다. 노드 유일성(P4) 위반이며
        `run.py all` 2회 = 동일 그래프(§8 전체 완료판정)도 깨진다.
        """
        for nid, n in g.nodes.items():
            if n["canonical"] == canonical and n["category"] == skel["category"]:
                register_surface(canonical, nid)
                return nid
        nid = g.add_node(canonical, skel["category"], SEED_STATUS,
                         attrs={"process_no": None}, provenance=SEED_PROV)
        register_surface(canonical, nid)
        return nid

    ids = {}
    # 골격의 **모양은 config가 정한다**(tree | flat) — 코드는 둘을 구별할 뿐
    # 어느 층이 어느 모양인지 모른다(B1).
    if skel.get("type") == "tree":
        child_rel = skel["relations"]["child"]      # 자식 → 부모
        sib_rel = skel["relations"]["sibling"]      # 형제 순서
        for parent, children in skel["data"].items():
            pid = ids[parent] = plant(parent)
            prev = None
            for child in children:
                cid = ids[child] = plant(child)
                g.add_edge(cid, child_rel, pid, SEED_STATUS, SEED_PROV)
                if prev is not None:
                    g.add_edge(prev, sib_rel, cid, SEED_STATUS, SEED_PROV)
                prev = cid
    else:                                            # flat — 관계 없는 골격 목록
        for item in skel["data"]:
            ids[item] = plant(item)

    metrics = g.build_end()
    store.write(store.DICTIONARY, dictionary)

    reg = store.read(store.REGISTRY, {})
    reg[layer] = {
        "layer": layer,
        # 내장(R1 절차 불경유)인지 등록된 층인지는 **config가 값으로 선언**한다(J10·D-8).
        # 코드가 층 이름으로 가르면 그 자체가 층 어휘다.
        "status": cfg.get("registration", "registered"),
        "skeleton_version": cfg.get("skeleton_version"),
        "categories": list(cfg["categories"]),
        "relations": cfg["relations"],
    }
    store.write(store.REGISTRY, reg)
    return g, metrics, ids
