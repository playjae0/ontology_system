# -*- coding: utf-8 -*-
"""칸 4.1·4.3 — **임베딩 후보 · 문서 검색** — 질의의 하이브리드 자리(링킹 후보 · 근거 채널) (B104 ②③).

판정과 같은 결이다 — **임베딩이 좁히고(후보) LLM이 고른다(후보 밖 id는 버린다)**. 근거 확장(그래프 순회)은
지금 그대로 코드다(`query_traverse`) — LLM은 그래프를 직접 읽지 않는다(문서 0).

두 자리:
  · **링킹 후보**(`link_candidates`) — 질문 문장 벡터 ↔ 노드 벡터 상위 k(손잡이 `query_link_top_k`). 노드 벡터의
    재료는 「canonical · 카테고리와 그 정의 · 별칭 · 닻까지의 길」 — **어디의 무엇**(`anchor` 한 자리)이다.
    고르는 것은 LLM(지점 ⑥ · `query._link_llm`) — 여기는 후보만 낸다.
  · **문서 검색 채널**(`doc_search`) — 질문 벡터 ↔ 청크 벡터 상위 k(유사도 문턱 `query_doc_min_sim` 이상) + BM25
    상위 k(공유 토큰이 있을 때만 — 점수 0은 없다) · 합쳐 중복 제거(번갈아 · 둘 다면 앞). 링킹이 빗나가도 돈다 —
    **둘 다 비면 「근거 없음」**이다(문턱이 없으면 임베딩 상위 k는 늘 k건이라 「근거 없음」이 성립하지 않는다).
    BM25는 이 채널의 한 재료이고 골든셋 대조군(`bm25.py` — 그래프·사전·임베딩·LLM을 읽지 않는다)은 그대로다.

mock: 임베딩은 해시 벡터(`embeddings` — 결정적 · 점수는 가짜 확신이다) · 선별은 **결정적 규칙의 주입**
(`SELECT` — 시험이 넣는다 · 비면 고르지 않는다).
"""
from __future__ import annotations

from core.llm import embeddings as E
from core.query import anchor as A, bm25, vectors as V
from core.state import store

#: 링킹 후보 수 — LLM 선별에 보내는 노드 수 상한(사내 손잡이 `query_link_top_k` · 가결정 D-185 — 창작 기본값)
LINK_TOP_K = 20
#: 링킹 단계 — `보충`(사전이 잡은 노드가 있어도 더 찾는다 · 사용자 결정 2026-10-07) | `폴백`(사전 미스일 때만)
LINK_MODE = "보충"
LINK_MODES = ("보충", "폴백")
#: 문서 검색 채널 — 임베딩 상위 k + BM25 상위 k(사내 손잡이 `query_doc_top_k` · 창작 기본값)
DOC_TOP_K = 8
#: 문서 검색 채널의 임베딩 유사도 문턱(%) — 넘는 청크만(사내 손잡이 `query_doc_min_sim` · 창작 기본값 ·
#: 모델마다 점수 분포가 다르다 — 사내 실측으로 정한다)
DOC_MIN_SIM = 50

#: mock 선별 규칙 — `(question, candidates) -> [{"id", "why"}]` · 시험이 주입한다(None이면 고르지 않는다)
SELECT = None


def _defs(configs):
    """카테고리 → 정의문(층 config `categories` — 집 층이 먼저 · 문자열만)."""
    out = {}
    for cfg in configs.values():
        for cat, d in (cfg.get("categories") or {}).items():
            if isinstance(d, str) and cat not in out:
                out[cat] = d
    return out


def node_texts(graphs, configs):
    """노드마다 벡터의 재료와 화면 재료 — `({id: 재료}, {id: {canonical, category, layer, where}})`."""
    nodes, edges = A.lists(graphs)
    anc = A.anchors(nodes, edges)
    names = {n["id"]: n["name"] for n in nodes}
    defs = _defs(configs)
    raw = {n["id"]: g.nodes[n["id"]] for g in graphs.values() for n in nodes if n["id"] in g.nodes}
    texts, info = {}, {}
    for n in nodes:
        r = raw.get(n["id"]) or {}
        al = [a.get("surface") if isinstance(a, dict) else a for a in r.get("aliases") or []]
        where = A.path_text(n["id"], anc, names)
        texts[n["id"]] = " | ".join(x for x in (
            n["name"], f"{n['category']}: {defs.get(n['category'], '')}".rstrip(": "),
            ("별칭: " + ", ".join(sorted({a for a in al if a}))) if al else "",
            f"위치: {where}" if where and where != n["name"] else "") if x)
        info[n["id"]] = {"canonical": n["name"], "category": n["category"], "layer": n["layer"],
                         "where": where}
    return texts, info


def link_candidates(question, graphs, configs, k, exclude=()):
    """질문 벡터 ↔ 노드 벡터 상위 k — `[{id, canonical, category, layer, where, score}]` (점수 내림 · 동점은 id)."""
    texts, info = node_texts(graphs, configs)
    if not texts:
        return []
    vecs = V.vectors("nodes", texts)
    qv = V.question(question)
    scored = sorted(((round(E.cosine(qv, v), 4), i) for i, v in vecs.items() if i not in exclude),
                    key=lambda t: (-t[0], t[1]))[:max(0, int(k))]
    return [{"id": i, **info[i], "score": s} for s, i in scored]


def _chunk_text(c):
    """청크 벡터의 재료 — 구획 · 좌표 · 본문(맥락이 「어디의 글」을 말한다)."""
    head = " · ".join(x for x in (c.get("section"), c.get("process_ref")) if x)
    return f"[{head}] {c.get('text') or ''}" if head else (c.get("text") or "")


def doc_search(question, k, min_sim, trace=None):
    """**문서 검색 채널** — `[{chunk_id, doc_id, source_locator, section, text, ref, by, embed, bm25, rank}]`.

    임베딩 상위 k(유사도 ≥ `min_sim`%) · BM25 상위 k(점수 > 0)를 번갈아 합쳐 중복을 뺀다(둘 다 잡은 청크는 앞 자리 ·
    `by`에 둘 다). ref 시트 청크(「찾아볼 시트」)도 들어가고 표시가 붙는다."""
    ch = (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {})
    if not ch:
        return []
    vecs = V.vectors("chunks", {cid: _chunk_text(c) for cid, c in ch.items()})
    qv = V.question(question)
    emb = sorted(((round(E.cosine(qv, v), 4), cid) for cid, v in vecs.items()), key=lambda t: (-t[0], t[1]))
    emb = [(cid, s) for s, cid in emb if s * 100 >= min_sim][:k]
    bm = bm25.search(question, k, index=bm25.Index({cid: c.get("text") or "" for cid, c in ch.items()}))
    es, bs = dict(emb), dict(bm)
    order, seen = [], set()
    for pair in zip(emb + [None] * len(bm), bm + [None] * len(emb)):
        for x in pair:
            if x and x[0] not in seen:
                seen.add(x[0])
                order.append(x[0])
    out = []
    for rank, cid in enumerate(order, 1):
        c = ch[cid]
        out.append({"chunk_id": cid, "doc_id": c.get("doc_id"), "source_locator": c.get("source_locator"),
                    "section": c.get("section"), "text": c.get("text") or "",
                    "ref": (c.get("meta") or {}).get("sheet_role") == "ref",
                    "by": [b for b, d in (("embed", es), ("bm25", bs)) if cid in d],
                    "embed": es.get(cid), "bm25": round(bs[cid], 4) if cid in bs else None,
                    "rank": rank})
    return out
