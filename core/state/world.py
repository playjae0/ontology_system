# -*- coding: utf-8 -*-
"""칸 0.3 — **층 그래프 전부** — 노드는 집 층 · 엣지는 문서 층 (B100 ④).

B90 이후 한 노드의 엣지는 그 노드의 집이 아닌 층(그 엣지를 낸 문서의 층) 그래프에 산다.
노드 하나를 고치는 연산(`ops`)이 집 그래프 하나만 열면 다른 층에 저장된 엣지가 옛 노드를
가리킨 채 남는다(B99 ⑪ 재현 — merge 뒤 끝점 없는 엣지). 그래서 연산은 **층 그래프 전부를
한 번 열고**, 노드는 집 그래프에서 · 엣지는 어느 그래프에 있든 같은 손으로 다룬다.

코드에 층 어휘 0 — 층 목록은 `router.discover()`가 준다.
"""
from __future__ import annotations

from core.graph import STATUS_DELETED, GraphStore


class World:
    """층 그래프 전부 — 층마다 한 번 연다(B99 ① 한 빌드 한 번 열기와 같은 규율)."""

    def __init__(self, layers=None):
        from router import discover
        self.graphs = {lay: GraphStore.for_layer(lay).load() for lay in (layers or discover())}

    def home(self, nid, hint=None):
        """노드가 사는 층 — `hint` 층에 있으면 그 층(사람이 친 층이 먼저) · 없으면 처음 찾은 층 · 없으면 None."""
        if hint in self.graphs and nid in self.graphs[hint].nodes:
            return hint
        return next((lay for lay, g in self.graphs.items() if nid in g.nodes), None)

    def graph_of(self, nid, hint=None):
        """노드의 집 그래프 — 없으면 `hint` 층 그래프(대상 없음 거부는 호출부가 한다)."""
        lay = self.home(nid, hint)
        return self.graphs.get(lay) or self.graphs.get(hint) or GraphStore.for_layer(hint).load()

    def get(self, nid):
        for g in self.graphs.values():
            n = g.get(nid)
            if n is not None:
                return n
        return None

    def nodes(self):
        """`(층, 노드)` 전부."""
        for lay, g in self.graphs.items():
            for n in g.nodes.values():
                yield lay, n

    def edges_of(self, nid, *, live=True):
        """노드에 닿은 엣지 — `(층, 엣지)` · 집 층 먼저(배분표 번호가 지금과 같게) · 사람 삭제는 `live`면 뺀다."""
        home = self.home(nid)
        order = ([home] if home else []) + [l for l in self.graphs if l != home]
        out = []
        for lay in order:
            for e in self.graphs[lay].edges:
                if nid in (e["src"], e["dst"]) and not (live and e.get("status") == STATUS_DELETED):
                    out.append((lay, e))
        return out

    def dangling(self):
        """끝점이 어느 층에도 없는 엣지 수(층별) — 집 이동 동치 · merge 뒤 점검."""
        known = {i for g in self.graphs.values() for i in g.nodes}
        return {lay: n for lay, g in self.graphs.items()
                for n in [sum(1 for e in g.edges
                              if e["src"] not in known or e["dst"] not in known)] if n}

    def save(self):
        for g in self.graphs.values():
            g.save()
