# -*- coding: utf-8 -*-
"""칸 3.3 곁 — **비정형(prose) 구축**: 추출 후보를 그래프에 착지시킨다 (문서 4 §4.4).

추출(칸 3.3 · `core/build/extract.py`)이 낸 후보를 받아 해소·부착한다 — 뽑는 일과
앉히는 일이 다른 파일인 이유가 그것이다(계약 B · P-1 체크포인트).
"""
from __future__ import annotations

from core import matcher
from core.build import loop
from core.build.build import Builder
from core.build import gate
from core.build.ledger import Ledger
from core.state.status import is_live
from core.state import log, store

_LOG = log.get(__name__)


# ---------------------------------------------------------------- 비정형 (1d′)
def build_prose(env, cfg, graph, candidates):
    # **실패한 청크는 건너뛴다**(문서 4 §4.10 규약 9 · B55 ③). `failed`는 「보지
    # 못했다」이고 `entities: []`는 「봤는데 없었다」다 — 섞으면 결함이 「후보 0건」
    # 통계에 녹아 사라진다. 건너뛰는 사실은 이미 `defects.log`에 남아 있다(추출 시점).
    candidates = [c for c in candidates if not c.get("failed")]
    b = Builder(graph, cfg, None, env["doc_id"], cfg["layer"])
    b.ledger = Ledger(env["doc_id"])          # 판정 대장 — 비정형도 같은 표다 (B74 ②)
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    by_locator = {c["source_locator"]: c for c in env.get("chunks", [])}
    loc_of = {cid: c.get("source_locator") for cid, c in ch["chunks"].items()
              if c.get("doc_id") == env["doc_id"]}

    # ════════════════ Pass 1 (해소) ════════════════
    # **문서 전체의 anchor·entity를 먼저 전부 해소해 버퍼에 담는다**(문서 4 §4.2).
    # 부착은 해소가 끝난 뒤에만 시작한다 — 그래야 **문서 안에서 뒤에 나오는 개체를
    # 앞의 청크가 참조해도** 붙는다. 이 분리 덕에 부착 실패의 원인이 구분된다:
    # Pass 1에 없는 대상을 가리키면 진짜 미해소(큐로), 있는데 실패하면 구현 결함.
    #
    # 버퍼는 `정규화 표면형 → node_id` 맵이고 수명은 문서 하나이며 **층으로 나누지
    # 않는다**(걸침 하위 빌더가 같은 버퍼를 공유한다 — §4.2). 층 간 동명 표면형은
    # **마지막 해소가 이긴다** — 버퍼는 사전과 달리 후보 목록을 두지 않으므로,
    # 카테고리로 선별해야 하는 소비처는 사전을 함께 조회한다.
    coords = {}
    for cand in candidates:
        cid = cand["chunk_id"]
        src = by_locator.get(loc_of.get(cid), {})
        # 비정형도 같은 조립이다 — 청크가 없으면 chunk_id가 이미 `{doc_id}:…` 꼴이라
        # 문서를 갖고 있다(§7.2). 있으면 locator에 접두를 붙인다.
        _loc = src.get("source_locator")
        prov = f"{env['doc_id']}#{_loc}" if _loc else cid
        ref, ref_g = b.resolve_anchor(src.get("process_ref"), loop.COORD_CATEGORY, prov)
        ref = b.descend_anchor(ref, src.get("electrode_type"), ref_g)   # ⓪ 비정형도 동일
        parent = ref_g.get(ref)["canonical"] if ref else None
        anchor_pol = b.anchor_polarity(ref, ref_g)      # A11-9 ① — 비정형도 동일
        b.check_polarity(ref, src.get("electrode_type"), prov, ref_g)
        coords[cid] = (src, prov, ref, ref_g, parent, anchor_pol)
        b.ledger.add(locator=_loc or cid, field="process_ref", role="anchor",
                     surface=src.get("process_ref"), canonical=parent,
                     layer=ref_g.layer if ref_g else None,
                     path="skeleton" if ref else "none",
                     verdict="anchor" if ref else "orphan", node_id=ref,
                     queue_kind=None if ref else "orphan_anchor")

        for e in cand.get("entities", []):
            eb = b.for_layer(cfg["layer"])
            nid = b.resolve_entity(e["surface"], e["category"], prov,
                                   electrode_type=src.get("electrode_type"),
                                   parent_canonical=parent,
                                   anchor_polarity=anchor_pol)
            last = b.last
            b.ledger.add(locator=_loc or cid, field=e.get("category"),
                         role="entity", surface=e["surface"],
                         canonical=(last or {}).get("canonical"),
                         layer=(last or {}).get("layer") or cfg["layer"],
                         path=(last or {}).get("path") or "none",
                         verdict=loop._VERDICT.get((last or {}).get("verdict"),
                                              "pending"),
                         node_id=nid,
                         candidates_n=(last or {}).get("candidates_n", 0),
                         confidence=(last or {}).get("confidence", 0.0),
                         llm=(last or {}).get("llm"),
                         queue_kind=(last or {}).get("queue_kind"))

    # ════════════════ Pass 2 (부착) ════════════════
    # **비정형의 순회 단위는 레코드가 아니라 청크(추출 후보)다**(문서 4 §4.2).
    # 그 청크의 후보에서 **해소된 언급 전부**에 describes를 만든다 — 부착·엣지
    # 성립 여부와 무관하다. 청크의 `linked`는 그 결과의 재계산이다(§4.8-2①).
    for cand in candidates:
        cid = cand["chunk_id"]
        src, prov, ref, ref_g, parent, anchor_pol = coords[cid]

        for e in cand.get("entities", []):
            nid = b.buffer.get(loop._n(e["surface"]))
            if nid is None:
                continue                        # Pass 1이 못 세운 것 — 부착도 없다
            if {"chunk_id": cid, "node_id": nid} not in ch["describes"]:
                ch["describes"].append({"chunk_id": cid, "node_id": nid})
            ch["chunks"][cid]["linked"] = True          # 상동 — 재인입이 거짓으로 되돌리지 않는다

        # ③ 경로 — 추출 후보. 게이트의 실질 관문이다.
        for r in cand.get("relations", []):
            s = b.buffer.get(loop._n(r["src"]))
            d = b.buffer.get(loop._n(r["dst"]))
            if s and d:
                gate.commit_edge(graph, s, r["rel"], d, cfg, gate.PATH_EXTRACT,
                                 [prov], env["doc_id"], evidence_chunk=cid)
            else:                               # 게이트에 닿기도 전의 소멸 — 기록한다
                store.append_defect(
                    f"{env['doc_id']}: 관계 후보 끝점 미해소 — "
                    f"'{r['src']}' -{r['rel']}-> '{r['dst']}' @ {cid}")

        # attach — ③의 폴백. 해소 범위는 **문서 버퍼 전체 + 사전**이며 청크 경계가 없다.
        for a in cand.get("attach", []):
            child = b.buffer.get(loop._n(a["surface"]))
            name, cat = loop._attach_target(a)       # {name, category} (§4.10 규약 8 — B11)
            target = b.buffer.get(loop._n(name)) if name else None
            # **부착 시도도 같은 표에 남는다**(B74 ②) — 대상이 없어 폴백으로 간
            # 것과 자식이 미해소라 못 간 것을 종류 열이 가른다.
            _al = b.ledger.add(locator=(prov or "").split("#")[-1] or cid,
                               field=name or "(attach_to null)", role="attach",
                               surface=a.get("surface"), layer=cfg["layer"],
                               path="none", verdict="pending")
            if target is None and name and cat:
                # **카테고리가 있으니 판정기가 그것 하나로 판정한다** — 전 카테고리를
                # 훑지 않으므로 선언 순서가 답을 정하는 일이 없다.
                target = _dict_hit(b, name, graph, category=cat)
            if child is None:                   # 자식 미해소도 대상 쪽과 대칭으로 기록
                store.append_defect(
                    f"{env['doc_id']}: attach 자식 미해소 — "
                    f"'{a['surface']}' → '{name}' @ {cid}")
                continue
            if target is None:
                # **규칙 B 폴백** — 좌표에 저해상도로 붙인다(문서 4 §4.4-4).
                # 비정형의 「미해소」는 `attach_to`가 null이거나 **카테고리를 못 고른**
                # 경우까지다(§4.4-4 — B11).
                loop._fallback_attach(b, cfg, graph, child, ref, ref_g, prov,
                                 env["doc_id"], evidence_chunk=cid)
                _al.update(verdict="lowres" if ref else "pending", node_id=child)
                # **`attach_to`가 null이면 폴백만 하고 큐를 달지 않는다**(§4.7-5) —
                # null은 추출이 애초에 부착 대상을 말하지 않은 정상 케이스라,
                # 큐로 보내면 처리 불가능한 노이즈가 큐를 채운다.
                if name:
                    store.enqueue_rows(
                        "orphan_attach", f"부착 대상 미해소 — '{name}'",
                        env["doc_id"], loop._n(name),           # 집계 키 = 부착 대상 표기
                        {"node_id": child, "surface": a["surface"],
                         "attach_to": loop._n(name),            # dedup 키 (§4.7-5)
                         "attach_category": cat,
                         "provenance": prov, "chunk_id": cid},
                        locator=(prov or "").split("#")[-1] or None)
                continue
            rel = gate.pair_relation(cfg, graph.get(target)["category"],
                                 graph.get(child)["category"])
            if rel:
                gate.commit_edge(graph, target, rel, child, cfg, gate.PATH_EXTRACT,
                                 [prov], env["doc_id"], evidence_chunk=cid)
            _al.update(verdict="attached", node_id=child,
                       canonical=(graph.get(target) or {}).get("canonical"))

    store.write(store.CHUNKS, ch)
    b.flush()
    b.ledger.save()
    return b


def _dict_hit(b, surface, graph, *, category):
    """attach 대상의 사전 해소 — **판정 파이프라인을 재사용한다**(문서 4 §4.4-3).

    **카테고리는 추출이 함께 낸다**(§4.10 규약 8 — B11). 그래서 여기는 그 카테고리
    하나로만 판정한다 — 전 카테고리를 훑지 않으므로 **선언 순서가 답을 정하는 일이
    없다**. 그것이 P-B의 임시 「수렴 판정」이 있던 자리이고, 추출 계약이 카테고리를
    내면서 순회도 수렴 판정도 필요 없어졌다.

    후보를 사전 히트로 **조립만** 하고 판정은 `matcher.match`가 한다 — 사전은 전 층
    단일이라(§7.1) 첫 히트를 조용히 고르면 그것이 판정을 대신하고, 카테고리 불일치
    안전망·극성 후보 제외·생존 판정이 적용되지 않은 선택이 엣지 끝점이 된다.
    """
    cands = []
    for nid in b.dict.lookup(surface):
        n = graph.get(nid)
        if not n or not is_live(n) or n["category"] != category:
            continue
        cands.append({"id": nid, "canonical": n["canonical"],
                      "aliases": [a["surface"] for a in n.get("aliases") or []],
                      "category": n["category"], "layer": n.get("layer"),
                      "polarity": n.get("polarity"), "exact": True})
    if not cands:
        return None
    v = matcher.match(surface, cands, category)
    return v["matched_id"] if v["type"] == matcher.MATCH else None
