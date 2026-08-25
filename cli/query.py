# -*- coding: utf-8 -*-
"""질의 단일 진입점 라우터 (명세 §8-R1).

    전역 링킹 → layer별 core.query 호출 → cross-layer 브리지 1홉 → 두 채널 합성

**얇은 라우터다.** 확장 의미·문장 틀·질문 의도는 전부 층 config가 소유하고, 여기는
층을 발견해 순회하는 절차만 갖는다 — 층이 늘어도 이 파일은 그대로다(§3.4-(가)).
core에 두지 않는 이유: 라우팅은 조립이지 읽기 파이프라인이 아니다.

사용: python cli/query.py "<질문>"        (또는 python -m cli.query "<질문>")
"""
from __future__ import annotations

import json

import sys


from core import llm
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


# ================================================================ ④ 답변 생성
# LLM 지점 ⑧ — §7.6-B-2. 이 지점이 목록에서 빠지면 USE_MOCK=1에서 무엇으로 도는지가
# 미정이라 답변에서만 실제 모델을 호출해 외부 의존 0(문서 1 B12)을 깨거나, 임의
# 포맷으로 나열해 12문항 스모크의 출력이 구현마다 달라진다.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"], "additionalProperties": False,
}


def generate(res):
    """두 채널을 답으로 만든다 — `if USE_MOCK: <나열> else: <실호출>`.

    **mock 갈래는 문장을 만들지 않는다**(§7.1 대체 표: "두 채널을 정형 텍스트로
    나열, 문장 생성 없음"). 그것이 `render()`이고 스모크 12문항의 출력 형태다.

    실호출 갈래는 두 채널을 **구분해** 넘긴다(문서 5 §5.4-5) — 한 덩어리로 붙이면
    답변 LLM이 둘을 동급으로 섞어, 구조·값 질문에서 청크의 옛 서술이 그래프 사실을
    덮어쓴 답이 나오고 출처 등급이 뭉개진다.

    **그래프는 답변 LLM이 직접 읽지 않는다**(문서 0) — 넘기는 것은 문장화된
    사실과 청크 원문뿐이다.
    """
    if llm.use_mock():
        llm.mock("answer", "두 채널 정형 나열 (문장 생성 없음)")
        return render(res)

    out = llm.chat(
        [{"role": "system", "content":
          "[그래프 사실]은 시스템이 보증하는 구조 정보이고 [문서 근거]는 서술 "
          "정보다. 둘을 동급으로 섞지 않는다 — 구조·순서·규격은 그래프 사실이 "
          "이긴다. 근거에 없는 것을 답하지 않고, 없으면 없다고 밝힌다. "
          "답에 출처를 함께 적는다."},
         {"role": "user", "content": json.dumps(
             {"question": res["question"],
              "그래프_사실": res["facts"],
              "문서_근거": [{"출처": f"{c['doc_id']} {c['source_locator']}",
                          "원문": c["text"]} for c in res["chunks"]]},
             ensure_ascii=False)}],
        json_schema=ANSWER_SCHEMA, point="answer")
    return out["answer"]


def render(res):
    """두 채널의 정형 나열 — **mock 갈래의 고정 형태**이자 사람이 뒷면을 보는 창구다."""
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
    print(generate(answer(" ".join(sys.argv[1:]))))
