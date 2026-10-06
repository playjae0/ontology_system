# -*- coding: utf-8 -*-
"""칸 0.3 — **정합** — 사전·큐·엣지가 가리키는 노드 id가 그래프에 있는가 (B99 ①⑩).

사내(2026-10-06): 층 config `"layer"` ≠ 폴더 이름 → 같은 그래프를 두 번 열어 새 노드가 덮였고,
사전 별칭·큐 항목·엣지가 **그래프에 없는 노드**를 가리킨 채 남았다. 구축 중 예외로 그래프는
저장되지 않았는데 큐는 이미 디스크에 써진 경우도 같은 모양이다(유령 큐).

한 함수(`missing_refs`)가 두 자리를 잰다:
- 구축 말미(`entry._finish_build`) — **이번 실행이 남긴 것**만 · 어긋나면 `[결함]` + 그 문서 실패 + 되돌림.
- `doctor` 정합 줄 · 정리 명령(`ops tidy`) — 상태 전체 · 층별 수.

노드 참조 키는 닫힌 목록(`REF_KEYS`)이고 값은 ULID 모양일 때만 노드 id로 본다 — 코드에 층 어휘 0.
"""
from __future__ import annotations

import re

#: 큐 payload에서 노드 id를 담는 키 — 닫힌 목록.
REF_KEYS = ("node_id", "src", "dst", "matched_id")
_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def is_node_id(v):
    return isinstance(v, str) and bool(_ULID.match(v))


def queue_refs(item):
    """큐 항목 하나가 가리키는 노드 id들."""
    pl = item.get("payload") or {}
    return [pl[k] for k in REF_KEYS if is_node_id(pl.get(k))]


def missing_refs(known, *, queue=(), dict_entries=None, edges_by_layer=None):
    """`known`(노드 id 집합)에 없는 것을 센다 — `{"queue": [...], "dict": [...], "edges": {층: [...]}}`.

    - 큐: `(항목, 없는 id들)` · 사전: `(표기, 없는 id들)` · 엣지: 끝점이 없는 엣지.
    """
    out = {"queue": [], "dict": [], "edges": {}}
    for it in queue:
        miss = [i for i in queue_refs(it) if i not in known]
        if miss:
            out["queue"].append((it, miss))
    for surface, ids in (dict_entries or {}).items():
        miss = [i for i in (ids or []) if is_node_id(i) and i not in known]
        if miss:
            out["dict"].append((surface, miss))
    for lay, edges in (edges_by_layer or {}).items():
        bad = [e for e in edges if e.get("src") not in known or e.get("dst") not in known]
        if bad:
            out["edges"][lay] = bad
    return out


def count(found):
    """`missing_refs` 결과의 수 — `(큐, 사전, 엣지 합)`."""
    return (len(found["queue"]), len(found["dict"]),
            sum(len(v) for v in found["edges"].values()))


def state_scan():
    """상태 전체 — 층마다 그래프를 열어 사라진 노드를 가리키는 큐·사전·엣지를 센다(`doctor`·정리)."""
    from core.dictionary import Dictionary
    from core.state import store
    from core.state.bootstrap import open_graph
    from router import discover
    graphs = {lay: open_graph(lay) for lay in discover()}
    known = set()
    for g in graphs.values():
        known |= set(g.nodes)
    found = missing_refs(known, queue=store.read(store.QUEUE, []),
                         dict_entries=Dictionary.open().entries(),
                         edges_by_layer={lay: g.edges for lay, g in graphs.items()})
    return found, graphs
