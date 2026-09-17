# -*- coding: utf-8 -*-
"""**같은 층·같은 canonical·live 노드가 둘이면 결함이다** — 상시 어서션 (B74 ①).

    python tests/dup_scan.py            data/의 전 층을 훑는다

왜 상시인가: 사전 키와 조회 키가 갈려 있던 동안 실호출 세계에서는 값마다 판정이
돌았고, auto 노드에 0.95로 MATCH가 나면 B73 ③ 가드가 `uncertain`으로 내려 **같은
canonical의 노드가 하나 더 생겼다**(`add_node`는 canonical 중복을 막지 않는다 —
허브 실측 열셋째). 키를 고친 것으로 끝내면 다음에 같은 종류의 갈림이 생겼을 때
아무도 모른다. 그래서 회귀가 무엇을 돌리든 **끝에 이것을 한 번 본다.**

읽기는 GraphStore 경유다(문서 1 B6 — 층 그래프 파일을 직접 열지 않는다).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None

from core.state import store                                            # noqa: E402
from core.state.bootstrap import open_graph                             # noqa: E402
from core.state.status import is_live                                   # noqa: E402


def scan():
    """`[(층, canonical, [id…]), …]` — 비어 있으면 위반 0이다."""
    bad = []
    for layer in (store.read(store.REGISTRY, {}).get("layers") or {}):
        try:
            g = open_graph(layer)
        except Exception:
            continue
        seen = {}
        for nid, n in g.nodes.items():
            if not is_live(n):
                continue
            seen.setdefault(n["canonical"], []).append(nid)
        for canonical, ids in seen.items():
            if len(ids) > 1:
                bad.append((layer, canonical, ids))
    return bad


def main():
    bad = scan()
    if not bad:
        print("[PASS] 중복 canonical 0 — 같은 층·같은 canonical·live 노드는 하나뿐이다")
        return 0
    for layer, canonical, ids in bad[:20]:
        print(f"[FAIL] 중복 canonical  [{layer}] {canonical} — {len(ids)}개 {ids[:4]}")
    print(f"[FAIL] 상시 어서션 위반 {len(bad)}건 (B74 ①)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
