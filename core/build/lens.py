# -*- coding: utf-8 -*-
"""칸 3.3 — **렌즈** — prose 문서를 **층마다 그 층의 어휘로** 뽑는다 (B91 ①).

doc_type은 「이 문서 종류는 어떤 정보층을 본다」는 층 목록(`registry.lenses_of`)을 갖는다.
기본은 등록 층 하나이고 그때는 이 모듈을 거치지 않는다(지금과 같다). 둘 이상이면 청크마다
렌즈마다 **그 층의 어휘**(카테고리 정의문 · 관계 · 겸 한 줄)로 따로 뽑는다 — 한 번에 전
어휘를 주지 않는다(한 번에 다 보면 무엇을 뽑을지 판단하다 놓친다 — 사용자 확정).

- 개체는 **집에서** 해소한다(B90 그대로) — 두 렌즈가 같은 뜻을 말하면 노드 하나로 모인다.
- 엣지는 **그 렌즈의 층**에 둔다(삼항 검사도 그 층의 relation_patterns).
- 체크포인트는 렌즈마다 따로다(`extract/<doc_id>@<렌즈>.json`).

**비용 장치**(렌즈가 둘 이상일 때만):
  ⓐ 관련성 사전 거름 — 청크마다 렌즈마다 결정적 점수(그 층 어휘의 사전 적중 + 층 config
     `relevance_terms` 적중) · 문턱(손잡이 `lens_min_score`) 미만이면 그 렌즈는 건너뛴다(LLM 0)
  ⓑ 호출 전 예고 — `렌즈 k × 청크 n → 거름 뒤 LLM ≤ m회`
  ⓒ 호출 상한(손잡이 `lens_call_cap`) — 넘으면 묻고, 답이 없으면(비대화형) 멈춘다(조용한 절단 0)
"""
from __future__ import annotations

from core.state.ids import fold_latin, norm

#: 관련성 문턱 — 청크에 그 층 어휘가 **몇 종** 나와야 그 렌즈를 부르나. 창작 기본값이다
#: (사내 실측으로 `knobs.json`에서 정한다 — [정정] 50). 0이면 거르지 않는다.
LENS_MIN_SCORE = 1
#: 문서당 렌즈 호출 상한 — 넘으면 묻는다. 창작 기본값이다(사내 PPT 실측 뒤 정한다).
LENS_CALL_CAP = 2000


def layer_vocab(layer, cfg, graphs, dictionary):
    """그 층의 **어휘** — 사전 표기 중 노드 카테고리가 그 층 `categories` 안인 것 + 관련어.

    관련어(`relevance_terms`)는 층 config의 선택 키다 — 사전에 아직 없는 말로도 그 층의
    청크를 알아보게 한다(예: 설비층의 「사양서」「도면」). 전부 정규화 표기다.
    """
    cats = set(cfg.get("categories") or {})
    out = set()
    for surface in dictionary.surfaces():
        for nid in dictionary.lookup(surface):
            n = next((g.get(nid) for g in graphs.values() if g.get(nid)), None)
            if n and n.get("category") in cats:
                out.add(norm(surface))
                break
    out |= {norm(t) for t in (cfg.get("relevance_terms") or []) if str(t).strip()}
    return {s for s in out if s}


def score(text, vocab):
    """관련성 점수 — 청크 본문에 나오는 그 층 어휘의 **종 수**(결정적 · LLM 0)."""
    t = norm(text or "")
    low = fold_latin(t)                      # 2차 — 라틴 대소문자 무시(B96 ④)
    return sum(1 for s in vocab if s in t or fold_latin(s) in low)


def plan(env, lenses, loc2id, cfgs, graphs, dictionary, min_score):
    """렌즈마다 부를 청크와 건너뛸 청크 — `({렌즈: 건너뛸 chunk_id 집합}, 대상 청크 수, 호출 수)`.

    참조 시트 청크(`meta.sheet_role == ref`)는 원래 부르지 않으므로 세지 않는다.
    """
    chunks = [c for c in env.get("chunks") or []
              if loc2id.get(c.get("source_locator"))
              and (c.get("meta") or {}).get("sheet_role") != "ref"]
    skip = {}
    calls = 0
    for lay in lenses:
        voc = layer_vocab(lay, cfgs[lay], graphs, dictionary) if min_score > 0 else set()
        sk = set()
        for c in chunks:
            if min_score > 0 and score(c.get("text"), voc) < min_score:
                sk.add(loc2id[c["source_locator"]])
        skip[lay] = sk
        calls += len(chunks) - len(sk)
    return skip, len(chunks), calls


def build_with_lenses(env, lenses, layer, graph, loc2id, notice=None):
    """렌즈 여럿(또는 등록 층이 아닌 렌즈)으로 추출·구축 — `(뿌리 빌더, 추출했나)`.

    뿌리는 문서 층의 빌더 하나다 — 렌즈 빌더는 `for_layer`로 받아 그래프·사전·버퍼·대장을
    공유한다(렌즈마다 그래프를 새로 열면 같은 층이 두 인스턴스로 열려 저장이 서로 덮는다).
    """
    from core.build import extract as extract_mod, prose as prose_mod
    from core.build.build import Builder
    from core.build.entry import Stopped, _vocab
    from core.build.ledger import Ledger
    from core.state import knobs
    from core.state.bootstrap import load_config, open_graph

    cfgs = {lay: load_config(lay) for lay in lenses}
    root = Builder(graph, load_config(layer), None, env["doc_id"], layer)
    root.ledger = Ledger(env["doc_id"])
    many = len(lenses) > 1
    skip = {lay: set() for lay in lenses}
    if many:
        graphs = {lay: (graph if lay == layer else open_graph(lay)) for lay in
                  set(lenses) | {layer}}
        min_score = knobs.get("lens_min_score")
        skip, n, calls = plan(env, lenses, loc2id, cfgs, graphs, root.dict, min_score)
        info = {"단계": "렌즈예고", "렌즈": list(lenses), "청크": n, "호출": calls,
                "거름": sum(len(v) for v in skip.values()), "문턱": min_score}
        if notice is not None:
            notice(info)
        cap = knobs.get("lens_call_cap")
        if calls > cap:
            go = notice({**info, "단계": "렌즈상한", "상한": cap}) if notice else None
            if not go:
                raise Stopped(f"렌즈 호출 상한 {cap} 초과 — 렌즈 {len(lenses)} × 청크 {n} → "
                              f"거름 뒤 {calls}회 · 손잡이 lens_call_cap 또는 렌즈를 줄인다")
    extracted = False
    for lay in lenses:
        ck, did = extract_mod.extract(env, cfgs[lay], loc2id, _vocab(cfgs[lay]),
                                      lens=lay, skip=skip[lay])
        extracted = extracted or did
        lb = root.for_layer(lay)
        prose_mod.build_prose(env, cfgs[lay], lb.g, ck["candidates"], builder=lb)
    return root, extracted
