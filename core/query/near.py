# -*- coding: utf-8 -*-
"""칸 4.1 — **중복 후보 보고**(읽기 전용) — 같은 층 · 같은 카테고리 · 같은 부모 안에서 노드 벡터가 가까운 쌍 (B136 ⑤).

같은 것이 두 노드로 갈라진 쌍(표기 변형 · 띄어쓰기 · 약어)을 사람이 고르게 후보를 낸다 — **임베딩은 후보를 내고 판단은 사람이다**
(병합 · 별칭은 지금의 `ops`). 벡터 글은 질의의 노드 벡터와 같은 함수(`hybrid.node_texts` — 이름 · 카테고리 · 별칭 · 위치)이고
**저장에 있는 벡터만 읽는다**(`vectors.lookup` — 만들지 않는다 · 쓰기 0 · 없는 노드는 센다 → `run.py vectors`).
문턱 · 상위 N은 사내 손잡이(`near_min_sim` · `near_top` — 창작 기본값 · 모델마다 유사도 분포가 다르다).
mock 해시 벡터의 유사도는 품질 근거가 아니다(가짜 확신 — 품질은 사내 첫 측정).
"""
from __future__ import annotations

from core.llm import embeddings as E
from core.query import hybrid as H, vectors as V

#: 보고 문턱(%) — 넘는 쌍만(사내 손잡이 `near_min_sim` · 창작 기본값)
MIN_SIM = 90
#: 상위 N쌍(사내 손잡이 `near_top` · 창작 기본값)
TOP = 20


def _raw(graphs):
    return {nid: n for g in graphs.values() for nid, n in g.nodes.items()}


def pairs(graphs, configs=None, *, layer=None, min_sim=None, top=None):
    """`{"pairs": [{score, a, b, layer, category, parent}], "nodes", "missing", "groups"}` — 쌍마다 노드 `{id, name, aliases, where}` ·
    점수 내림(동점은 id) · `layer`를 주면 그 층만."""
    min_sim = MIN_SIM if min_sim is None else min_sim
    top = TOP if top is None else top
    texts, info = H.node_texts(graphs, configs)
    vecs = V.lookup("nodes", texts)
    raw = _raw(graphs)
    groups = {}
    for nid, inf in info.items():
        if layer and inf["layer"] != layer:
            continue
        r = raw.get(nid) or {}
        groups.setdefault((inf["layer"], inf["category"], r.get("parent") or r.get("mirror_scope")), []).append(nid)
    found = []
    for (lay, cat, par), ids in groups.items():
        ids = sorted(i for i in ids if i in vecs)
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                s = round(E.cosine(vecs[ids[x]], vecs[ids[y]]) * 100, 1)
                if s >= min_sim:
                    found.append((s, ids[x], ids[y], lay, cat, par))
    found.sort(key=lambda t: (-t[0], t[1], t[2]))

    def node(i):
        r = raw.get(i) or {}
        al = sorted({(a.get("surface") if isinstance(a, dict) else a) for a in r.get("aliases") or []} - {None, ""})
        return {"id": i, "name": info[i]["canonical"], "aliases": al, "where": info[i]["where"]}
    scope = [i for i, inf in info.items() if not layer or inf["layer"] == layer]
    return {"pairs": [{"score": s, "a": node(a), "b": node(b), "layer": lay, "category": cat,
                       "parent": (raw.get(par) or {}).get("canonical") if par else None}
                      for s, a, b, lay, cat, par in found[:max(0, int(top))]],
            "nodes": len(scope), "missing": sum(1 for i in scope if i not in vecs), "groups": len(groups),
            "min_sim": min_sim, "top": top}
