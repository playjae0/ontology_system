# -*- coding: utf-8 -*-
"""칸 0.3 · 4.1 — **`show near`** — 동의어 · 중복 후보 보고(읽기 전용 · 쓰기 0) (B136 ⑤).

    python run.py show near [<층>] [--top N]

같은 층 · 같은 카테고리 · 같은 부모 안에서 노드 벡터가 가까운 쌍 상위 N(유사도 · 이름 · 별칭 · 위치) · 줄마다 다음 줄(사람이 고르는
병합 · 별칭 — 지금의 `ops`) · 벡터가 없는 노드는 센다(`run.py vectors`로 만든다 — 이 명령은 만들지 않는다). 계산은 `core/query/near`.
"""
from __future__ import annotations


def cmd_near(args):
    from core.llm import embeddings as E
    from core.query import near as N
    from core.state.bootstrap import load_config, open_graph
    from router import discover
    top = None
    if "--top" in args:
        i = args.index("--top")
        try:
            top = int(args[i + 1])
        except (IndexError, ValueError):
            print("[사용법] python run.py show near [<층>] [--top N]")
            return 2
        args = args[:i] + args[i + 2:]
    layers = discover()
    layer = args[0] if args else None
    if layer and layer not in layers:
        print(f"[사용법] python run.py show near [<층>] [--top N] — 층은 {' · '.join(layers)}")
        return 2
    graphs = {lay: open_graph(lay) for lay in layers}
    got = N.pairs(graphs, {lay: load_config(lay) for lay in layers}, layer=layer, top=top)
    print(f"■ 중복 후보 — 같은 층 · 같은 카테고리 · 같은 부모 안에서 노드 벡터가 가까운 쌍 (읽기 전용 · 문턱 {got['min_sim']}% · "
          f"상위 {got['top']} · 손잡이 near_min_sim · near_top)")
    print(f"   {'층 ' + layer if layer else '층 전부'} — 노드 {got['nodes']:,} · 묶음 {got['groups']:,} · 판 {E.backend_id()}"
          + (f" · 벡터 없음 {got['missing']:,} — python run.py vectors" if got["missing"] else ""))
    if not got["pairs"]:
        print(f"   쌍 0 — 문턱 {got['min_sim']}% 아래(낮추려면 knobs.json near_min_sim)")
    for n, p in enumerate(got["pairs"], 1):
        a, b = p["a"], p["b"]

        def lab(x):
            return x["name"] + (f"(별칭 {', '.join(x['aliases'])})" if x["aliases"] else "")
        print(f"   {n}. {p['score']:.1f}%  {lab(a)} ↔ {lab(b)} · {p['category']} · 부모 {p['parent'] or '없음'}"
              + (f" · 위치 {a['where']}" if a["where"] and a["where"] != a["name"] else ""))
        print(f"      ▶ 같은 것이면 python run.py ops merge {p['layer']} {b['id']} {a['id']} --actor <이름>  (미리보기 · 실행은 --yes)")
        print(f"      ▶ 표기만 잇는다면 python run.py ops alias {p['layer']} {a['id']} \"{b['name']}\" --actor <이름>")
    from core.llm import gateway
    print("   (mock 해시 벡터의 유사도는 품질 근거가 아니다 — 판단은 사람 · 이 명령은 쓰지 않는다)" if gateway.use_mock()
          else "   (판단은 사람 — 이 명령은 쓰지 않는다)")
    return 0
