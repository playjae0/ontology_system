# -*- coding: utf-8 -*-
"""칸 5.3 — 뷰어 **닻** — 골격 밖 노드가 골격의 어디에 붙었나 (B103 ①④).

「골격 + 위성」 배치와 노드 상세의 「닻까지의 길」이 **같은 사실**을 읽는다 — 그래서 계산은
서버 한 자리다(화면이 다시 찾지 않는다 · PF11). 그래프의 사실만 쓴다: 골격 여부는 노드의
`status`(`seed`) · 길은 엣지의 관계 이름 그대로.

규칙(결정적 — 같은 입력 같은 답 · D-184):
  ①골격 노드에서 동시에 넓이 우선으로 퍼진다(다중 출발 BFS) — 출발 순서는 골격 canonical 순.
  ②엣지는 방향 없이 따라간다 · 골격 노드는 출발점일 뿐 지나가지 않는다(골격 사이 길은 골격 트리가 말한다).
  ③처음 닿은 골격이 닻이다 — 거리가 같으면 출발 순서가 앞선 것(= canonical 순) · 같은 층의
    이웃은 (관계, 상대 canonical) 순으로 연다.
  ④홉 상한 `ANCHOR_HOPS`를 넘으면 닻이 없다 — 엣지가 하나도 없는 노드와 함께 「연결 없는 노드」.
"""
from __future__ import annotations

from collections import deque

#: 닻을 찾는 홉 상한(가결정 D-184 — 창작 표본 수치는 근거가 아니다 · 위성의 위성의 … 깊이)
ANCHOR_HOPS = 6


def is_skeleton(n):
    return n.get("status") == "seed"


def anchors(nodes, edges, hops=ANCHOR_HOPS):
    """노드마다 닻 — `{id: {"anchor", "host", "hops", "path": [{rel, src, dst}]}}`.

    `host`는 BFS의 앞 노드(위성의 위성은 그 위성 둘레에 놓인다) · 골격 노드는 자기 자신(hops 0) ·
    닻이 없는 노드는 빠진다(`detached`가 센다)."""
    by = {n["id"]: n for n in nodes}
    adj = {i: [] for i in by}
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if s in by and d in by and s != d:
            adj[s].append((e["rel"], s, d, d))
            adj[d].append((e["rel"], s, d, s))
    for i in adj:
        adj[i].sort(key=lambda t: (t[0], by[t[3]]["name"], t[3]))
    sk = sorted((n for n in nodes if is_skeleton(n)), key=lambda n: (n["name"], n["id"]))
    out = {n["id"]: {"anchor": n["id"], "host": n["id"], "hops": 0, "path": []} for n in sk}
    q = deque(n["id"] for n in sk)
    while q:
        cur = q.popleft()
        here = out[cur]
        if here["hops"] >= hops:
            continue
        for rel, s, d, other in adj[cur]:
            if other in out or is_skeleton(by[other]):
                continue
            out[other] = {"anchor": here["anchor"], "host": cur, "hops": here["hops"] + 1,
                          "path": [{"rel": rel, "src": s, "dst": d}] + here["path"]}
            q.append(other)
    return out


def detached(nodes, edges, anc):
    """닻 없는 노드 — `{"edgeless": [id…], "island": [id…]}`(엣지 없음 · 골격에 닿지 않는 덩어리)."""
    ends = {x for e in edges for x in (e.get("src"), e.get("dst"))}
    rest = sorted((n for n in nodes if n["id"] not in anc), key=lambda n: (n["name"], n["id"]))
    return {"edgeless": [n["id"] for n in rest if n["id"] not in ends],
            "island": [n["id"] for n in rest if n["id"] in ends]}


def roots(nodes, edges):
    """골격 뿌리 — 골격 사이 `part_of`의 부모가 없는 골격 노드(이름 순) · 탐색 모드의 첫 화면."""
    sk = {n["id"]: n for n in nodes if is_skeleton(n)}
    child = {e["src"] for e in edges if e.get("rel") == "part_of" and e["src"] in sk and e["dst"] in sk}
    return [i for i, _n in sorted(((i, n) for i, n in sk.items() if i not in child),
                                  key=lambda t: (t[1]["name"], t[0]))]
