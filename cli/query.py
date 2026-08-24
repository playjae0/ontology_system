# -*- coding: utf-8 -*-
"""질의 단일 진입점 라우터 (명세 §8-R1).

    전역 링킹 → layer별 core.query 호출 → cross-layer 브리지 1홉 → 두 채널 합성

**얇은 라우터다.** 확장 의미·문장 틀·질문 의도는 전부 층 config가 소유하고, 여기는
층을 발견해 순회하는 절차만 갖는다 — 층이 늘어도 이 파일은 그대로다(§3.4-(가)).
core에 두지 않는 이유: 라우팅은 조립이지 읽기 파이프라인이 아니다.

사용: python cli/query.py "<질문>"        (또는 python -m cli.query "<질문>")
"""
from __future__ import annotations

import sys


from core.dictionary import Dictionary
from core import query as Q, store
from core.ids import norm
from core.bootstrap import load_config, open_graph
from router import discover

GENERAL = "[일반지식 — 사내 검증 필요]"


def _world():
    layers = discover()
    return ({lay: open_graph(lay) for lay in layers},
            {lay: load_config(lay) for lay in layers})


def answer(question):
    """질문 하나에 대한 답 묶음을 돌려준다 — 렌더는 호출부가 한다.

    **답변 3단**(5.2 규약 3): 근거 있음 → 근거 기반 답 + 출처 / 근거 없음 →
    "사내 근거를 찾지 못했다"를 먼저 밝히고 일반지식 표시 / 링킹 미스 → 로그 축적.
    """
    graphs, configs = _world()
    dictionary = Dictionary.open()      # 사전 접근은 관문 경유로만 (문서 7 §7.1)
    hits = Q.link(question, dictionary, graphs)

    res = {"question": question, "linked": [], "facts": [], "chunks": [],
           "path": Q.PATH_GENERAL, "note": None, "truncated": 0, "transit": []}
    # 전이 — 옛 id에 닿은 링킹은 현재 노드로 옮긴다. 직접 지명한 폐기 노드는
    # 결과에서 빼되 상태를 밝힌다(R3-⑶ — 조용히 사라지지 않는다).
    kept, notes = [], []
    for h in hits:
        g = graphs[h["layer"]]
        nid, note, visible = Q.transit(g, h["node_id"], configs[h["layer"]])
        if note:
            notes.append(note)
        named = norm(h["surface"]) == norm((g.get(h["node_id"]) or {}).get("canonical", ""))
        if visible or named:
            kept.append(dict(h, node_id=nid, visible=visible))
    hits = [h for h in kept if h["visible"]]
    res["transit"] = notes
    res["linked"] = [f"{h['layer']}:{graphs[h['layer']].get(h['node_id'])['canonical']}"
                     for h in kept]
    if notes and not hits:
        res["note"] = " · ".join(notes)
        res["path"] = Q.PATH_GENERAL
        return res

    # 의도는 링킹된 층의 config가 판정한다. 링킹이 없으면 물어볼 층도 없다.
    layers_hit = {h["layer"] for h in hits}
    intent = next((i for lay in sorted(layers_hit)
                   if (i := Q.intent_of(question, configs[lay]))), None)

    if not hits or intent == "general":
        if not hits:
            Q.log_miss(question)                        # 하이브리드 판정 데이터(5.4)
        res["note"] = ("사내 문서에서 근거를 찾지 못했다. " + GENERAL if not hits
                       else "그래프 밖 지식이다. " + GENERAL)
        res["path"] = Q.PATH_GENERAL
        return res

    direct_by_layer = {}
    for h in hits:
        direct_by_layer.setdefault(h["layer"], set()).add(h["node_id"])

    collected = {}
    for lay, direct in direct_by_layer.items():
        g, cfg = graphs[lay], configs[lay]
        if intent == "flow":                            # flow 특례 — 골격 통째(5.2 규약 4)
            res["facts"] += Q.flow_chain(g, cfg)
            collected.setdefault(lay, set()).update(direct)
            continue
        if intent == "order":                           # 순서 파생(5.1 규약 8)
            res["facts"] += _order_facts(g, cfg, direct)
            collected.setdefault(lay, set()).update(direct)
            continue
        collected[lay] = Q.expand(g, direct, cfg)

    # cross-layer 브리지 1홉 — 걸침 엣지는 출발 층 그래프에 있으므로 그쪽을 훑는다
    crossed = []
    for lay, ids in list(collected.items()):
        found, edges = Q.bridge(ids, lay, graphs, configs)
        crossed += edges
        for other, more in found.items():
            collected.setdefault(other, set()).update(more)
            direct_by_layer.setdefault(other, set())
    res["facts"] += Q.cross_facts(crossed, graphs, configs)

    for lay, ids in collected.items():
        res["facts"] += Q.facts(graphs[lay], ids, configs[lay])

    all_ids = {i for ids in collected.values() for i in ids}
    direct_ids = {i for s in direct_by_layer.values() for i in s}
    res["chunks"], res["truncated"] = Q.collect_chunks(all_ids, direct_ids)

    # 답의 소재는 **질문 유형**이 정한다(5.3). 유형이 없으면 있는 채널로 판정한다.
    res["path"] = Q.INTENT_PATH.get(intent) or (
        Q.PATH_BOTH if res["facts"] and res["chunks"] else
        Q.PATH_GRAPH if res["facts"] else
        Q.PATH_CHUNK if res["chunks"] else Q.PATH_GENERAL)
    if res["path"] == Q.PATH_GENERAL:
        res["note"] = "사내 문서에서 근거를 찾지 못했다. " + GENERAL
    return res


def _order_facts(g, cfg, direct):
    """순서 파생의 문장화 — **파생 답에는 해상도를 표기한다**(A11-5).

    "(탭용접 기준) 다음 공정은 …"처럼 어느 해상도에서 나온 답인지 밝힌다. 자기 선언
    으로 나온 답에는 표기하지 않는다 — 그때는 해상도가 곧 질문의 대상이기 때문이다.
    """
    tpl = cfg.get("fact_templates") or {}
    sib = ((cfg.get("skeleton") or {}).get("relations") or {}).get("sibling")
    out = []
    for nid in sorted(direct):
        nxt, scope = Q.next_of(g, nid, cfg)
        name = g.get(nid)["canonical"]
        if nxt is None:
            out.append(tpl.get(f"{sib}:none", "{src}의 순서 정보 없음").format(src=name))
        elif scope == nid:
            out.append(tpl.get(sib, "{src} → {dst}").format(
                src=name, dst=g.get(nxt)["canonical"]))
        else:
            out.append(tpl.get(f"{sib}:derived", "({scope} 기준) {src} → {dst}").format(
                scope=g.get(scope)["canonical"], src=name, dst=g.get(nxt)["canonical"]))
    return out


def render(res):
    lines = [f"Q. {res['question']}", f"   [경로] {res['path']}"]
    if res["linked"]:
        lines.append(f"   [링킹] {', '.join(res['linked'])}")
    if res["note"]:
        lines.append(f"   {res['note']}")
    for t in res.get("transit", []):
        lines.append(f"   [전이] {t}")
    for f in res["facts"]:
        lines.append(f"   [그래프 사실] {f}")
    for c in res["chunks"]:
        lines.append(f"   [문서 근거] ({c['doc_id']} {c['source_locator']}) {c['text']}")
    if res["truncated"]:
        lines.append(f"   [잘림] 근거 {res['truncated']}건 (상한 {Q.COLLECT_LIMIT})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render(answer(" ".join(sys.argv[1:]))))
