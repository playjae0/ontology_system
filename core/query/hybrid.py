# -*- coding: utf-8 -*-
"""칸 4.1·4.3 — **임베딩 후보 · 문서 검색** — 질의의 하이브리드 자리(링킹 후보 · 근거 채널) (B104 ②③).

판정과 같은 결이다 — **임베딩이 좁히고(후보) LLM이 고른다(후보 밖 id는 버린다)**. 근거 확장(그래프 순회)은
지금 그대로 코드다(`query_traverse`) — LLM은 그래프를 직접 읽지 않는다(문서 0).

두 자리:
  · **링킹 후보**(`link_candidates`) — 질문 문장 벡터 ↔ 노드 벡터 상위 k(손잡이 `query_link_top_k`). 노드 벡터의
    재료는 「맨 이름 · 카테고리 이름 · 별칭 · 위치(위 이름 사슬)」 — **어디의 무엇**(`anchor` 한 자리)이다 · 경로는 위치에 한 번 ·
    관계 이름 0(같은 카테고리 노드끼리 같아 가르는 정보 0 — B153 ②) · **카테고리 정의문은 넣지 않는다**
    (B136 ① — 같은 카테고리 노드에 같은 정의문이 붙으면 노드를 가르는 이름 사슬 · 위치가 묻힌다 · 정의문은 판정 · 선별 입력의 몫).
    고르는 것은 LLM(지점 ⑥ · `query._link_llm`) — 여기는 후보만 낸다.
  · **문서 검색 채널**(`doc_search`) — 질문 벡터 ↔ 청크 벡터 상위 k(유사도 문턱 `query_doc_min_sim` 이상) + BM25
    상위 k(공유 토큰이 있을 때만 — 점수 0은 없다) · 합쳐 중복 제거(번갈아 · 둘 다면 앞). 링킹이 빗나가도 돈다 —
    **둘 다 비면 「근거 없음」**이다(문턱이 없으면 임베딩 상위 k는 늘 k건이라 「근거 없음」이 성립하지 않는다).
    BM25는 이 채널의 한 재료이고(청크 벡터와 **같은 재료** — 머리 + 원문 · B153 ①) 골든셋 대조군(`bm25.py` — 그래프·사전·임베딩·LLM을
    읽지 않는다)은 그대로다.

mock: 임베딩은 해시 벡터(`embeddings` — 결정적 · 점수는 가짜 확신이다) · 선별은 **결정적 규칙의 주입**
(`SELECT` — 시험이 넣는다 · 비면 고르지 않는다).

**색인을 맞추는 자리는 `_ensure` 하나**(B161): 넘겨받은 내용(노드 — 층 이름 순 그래프 객체의 노드 · 엣지 · 청크 — 청크 저장의
내용)의 지문 · 재료 판 `MATERIAL_VER` · 입력 한도가 저장의 색인과 같으면 글을 조립하지 않고(재료 함수 호출 0) 색인에서
읽는다 · 다르면 재료 함수로 글을 조립해 색인을 갈아 끼운다. 벡터 준비(`warm`) · 링킹 후보 · 문서 검색이 이 함수를 지난다.
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
#: **재료 규칙의 판**(B161) — `node_texts` · `_chunk_text`의 규칙을 바꾸는 회차가 올린다(지문이 같아도 색인을 다시 쓴다)
MATERIAL_VER = "m-1"
KINDS = ("nodes", "chunks")


def _info_of(n, anc, names):
    return {"canonical": n["name"], "category": n["category"], "layer": n["layer"], "where": A.path_text(n["id"], anc, names)}


def node_info(graphs, ids=None):
    """링킹 후보 · 중복 후보의 **화면 정보** `{id: {canonical, category, layer, where}}` — 고른 id만(`None`이면 살아 있는 노드
    전부) · 글을 조립하지 않는다 · 닻 계산은 그래프 전부 한 번(B161)."""
    nodes, edges = A.lists(graphs)
    anc = A.anchors(nodes, edges)
    names = {n["id"]: n["name"] for n in nodes}
    want = None if ids is None else set(ids)
    return {n["id"]: _info_of(n, anc, names) for n in nodes if want is None or n["id"] in want}


def node_texts(graphs, configs=None):
    """노드마다 벡터의 재료와 화면 재료 — `({id: 재료}, {id: {canonical, category, layer, where}})`.

    재료 = `맨 이름 | 카테고리 | 별칭: … | 위치: 위 > … > 주인` — 맨 이름은 `base_name`(없으면 canonical의 끝 마디) · 별칭은 맨 이름과
    같은 것을 빼고 정렬 · 위치는 이름 사슬(`anchor.name_chain` — 관계 이름 0 · 비면 칸 0) · 정의문 0(B136 ① · B153 ②). 화면 재료의
    `where`는 엣지 꼴 그대로(`anchor.path_text`). `configs`는 받기만 한다(재료가 층 config를 읽지 않는다)."""
    from core.build.naming import base_name_of
    from core.state.ids import norm
    nodes, edges = A.lists(graphs)
    anc = A.anchors(nodes, edges)
    names = {n["id"]: n["name"] for n in nodes}
    raw = {n["id"]: g.nodes[n["id"]] for g in graphs.values() for n in nodes if n["id"] in g.nodes}
    base = {n["id"]: base_name_of(raw.get(n["id"])) or n["name"].split("::")[-1] for n in nodes}
    texts, info = {}, {}
    for n in nodes:
        r = raw.get(n["id"]) or {}
        bare = base[n["id"]]
        al = sorted({a for a in (x.get("surface") if isinstance(x, dict) else x for x in r.get("aliases") or [])
                     if a and norm(a) != norm(bare)})
        chain = A.name_chain(n["id"], anc, names, base)
        texts[n["id"]] = " | ".join(x for x in (
            bare, n["category"], ("별칭: " + ", ".join(al)) if al else "", f"위치: {chain}" if chain else "") if x)
        info[n["id"]] = _info_of(n, anc, names)
    return texts, info


# ---------------------------------------------------------------- 색인 맞추기 (B161)
def src_fp(kind, graphs=None, chunks=None):
    """넘겨받은 내용의 지문 — 노드: 층 이름 순 그래프 객체의 노드 · 엣지 내용(`GraphStore.content_fp`) · 청크: 청크 저장의 내용."""
    if kind == "nodes":
        return store.content_fp([[lay, graphs[lay].content_fp()] for lay in sorted(graphs or {})])
    return store.content_fp(chunks or {})


def _decide(kind, graphs, chunks, configs=None):
    """`(지문, None)` — 색인이 맞다 · `(지문, (재료, {id: (층, 문서)}))` — 다시 쓸 몫(재료 함수가 여기서만 불린다)."""
    fp = src_fp(kind, graphs, chunks)
    if V.index_ok(kind, fp, MATERIAL_VER):
        return fp, None
    if kind == "nodes":
        texts, info = node_texts(graphs, configs)
        return fp, (texts, {i: (info[i]["layer"], None) for i in texts})
    return fp, ({cid: _chunk_text(c) for cid, c in chunks.items()}, {cid: (None, c.get("doc_id")) for cid, c in chunks.items()})


def _apply(kind, fp, todo):
    if todo is None:
        V.index_fill(kind)
    else:
        V.index_write(kind, todo[0], todo[1], fp, MATERIAL_VER)


def _ensure(kind, graphs=None, chunks=None, configs=None):
    """그 종류의 색인을 지금 입력에 맞춘다 — 링킹 후보 · 문서 검색이 읽기 전에(벡터 준비가 방금 맞췄으면 지문만 잰다) ·
    돌려주는 것은 읽을 때 넘길 기대 `(지문, 재료 판)`."""
    fp, todo = _decide(kind, graphs, chunks, configs)
    _apply(kind, fp, todo)
    return fp, MATERIAL_VER


def link_candidates(question, graphs, configs, k, exclude=()):
    """질문 벡터 ↔ 노드 벡터 상위 k — `[{id, canonical, category, layer, where, score}]` (점수 내림 · 동점은 id).
    벡터는 색인에서(B161 — 노드 글을 다시 조립하지 않는다) · 화면 정보는 상위 k만. 맞춘 뒤 읽기 전에 다른 자리가 다른 입력으로
    색인을 갈아 끼웠으면 제 입력의 글로 찾는다(남의 판을 읽지 않는다)."""
    vecs = V.index_vectors("nodes", _ensure("nodes", graphs, configs=configs))
    if vecs is None:
        vecs = V.vectors("nodes", node_texts(graphs, configs)[0])
    if not vecs:
        return []
    qv = V.question(question)
    scored = sorted(((round(E.cosine(qv, v), 4), i) for i, v in vecs.items() if i not in exclude),
                    key=lambda t: (-t[0], t[1]))[:max(0, int(k))]
    info = node_info(graphs, [i for _s, i in scored])
    return [{"id": i, **info[i], "score": s} for s, i in scored if i in info]


def _chunk_text(c):
    """청크 벡터 · 문서 검색 BM25의 재료 — `[머리] 원문`(머리가 「어디의 무엇에 관한 글」을 문서의 말로 말한다 · B153 ①).

    표 content 청크(`meta.field`) = `[열 머리 글(없으면 필드 이름) · 주인 · 좌표]` — 행 위치(`section`)는 넣지 않는다 ·
    산문 청크 = `[경로 · 좌표 · 다루는 것(PPT `meta.subject`)]`. 머리가 비면 원문만."""
    from parser.normalizer import coord_text
    m = c.get("meta") or {}
    coord = coord_text(c.get("process_ref"))
    parts = (m.get("label") or m["field"], m.get("owner"), coord) if m.get("field") else (c.get("section"), coord, m.get("subject"))
    head = " · ".join(str(x) for x in parts if x)
    return f"[{head}] {c.get('text') or ''}" if head else (c.get("text") or "")


def warm(graphs=None, configs=None, kinds=None):
    """**벡터 준비** — 질의가 견줄 노드 · 청크 벡터를 미리(B114 ④ — 질의의 첫 단계 · 뷰어 시작의 미리 만들기가 이
    함수 하나). 재료는 `link_candidates` · `doc_search`와 같은 함수(`node_texts` · `_chunk_text`)라 뒤의 두 자리는
    저장을 재사용한다. 계획(두 종류의 분모)을 먼저 세우고 종류마다 만든다 — 돌려주는 것은 `{종류: (있던 수, 전체)}` · `kinds`를 주면
    그 종류만(`run.py vectors --only` — B136 ④)."""
    if graphs is None:
        from core.state.bootstrap import load_config, open_graph
        from router import discover
        graphs = {lay: open_graph(lay) for lay in discover()}
        configs = {lay: load_config(lay) for lay in graphs}
    ch = (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {})
    # 색인을 지금 입력에 맞춘다(B161) — 지문이 같은 종류는 글 조립 0 · 다른 종류만 재료 함수로 조립해 갈아 끼운다
    dec = {k: _decide(k, graphs, ch, configs or {}) for k in KINDS if kinds is None or k in kinds}
    got = V.plan([(k, todo[0]) for k, (_fp, todo) in dec.items() if todo is not None and todo[0]],
                 {k: V.index_plan(k) for k, (_fp, todo) in dec.items() if todo is None})
    for kind, (fp, todo) in dec.items():
        _apply(kind, fp, todo)
    return got


def doc_search(question, k, min_sim, trace=None):
    """**문서 검색 채널** — `[{chunk_id, doc_id, source_locator, section, text, ref, by, embed, bm25, rank}]`.

    임베딩 상위 k(유사도 ≥ `min_sim`%) · BM25 상위 k(점수 > 0)를 번갈아 합쳐 중복을 뺀다(둘 다 잡은 청크는 앞 자리 ·
    `by`에 둘 다). ref 시트 청크(「찾아볼 시트」)도 들어가고 표시가 붙는다."""
    ch = (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {})
    if not ch:
        return []
    want = _ensure("chunks", chunks=ch)            # 벡터 · BM25 재료는 색인에서(B161 — 청크 글을 다시 조립하지 않는다)
    vecs, texts = V.index_vectors("chunks", want), V.index_texts("chunks", want)
    if vecs is None or texts is None:              # 맞춘 뒤 다른 자리가 다른 입력으로 갈아 끼웠다 — 제 입력의 글로
        texts = {cid: _chunk_text(c) for cid, c in ch.items()}
        vecs = V.vectors("chunks", texts)
    qv = V.question(question)
    emb = sorted(((round(E.cosine(qv, v), 4), cid) for cid, v in vecs.items() if cid in ch), key=lambda t: (-t[0], t[1]))
    emb = [(cid, s) for s, cid in emb if s * 100 >= min_sim][:k]
    texts = {cid: t for cid, t in texts.items() if cid in ch}
    bm = bm25.search(question, k, index=bm25.Index(texts))       # 벡터와 같은 재료(B153 ① — 색인의 글이 그 재료다)
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
