# -*- coding: utf-8 -*-
"""질의 4단 — 범용 읽기 파이프라인 (CH5 5.1·5.2, 명세 §5.6.1~5.6.4).

    질문 → ①링킹 → ②확장 → ③수집 → ④답변

**시스템(코드)이 그래프 연결성으로 근거를 고르고, LLM은 받은 근거를 읽고 답한다.**
LLM은 그래프를 직접 읽지 않는다 — 그것이 이 4단을 나눈 이유다.

**질의는 읽기 전용이다(P6).** 질문에 나온 표기를 사전에 배우지 않는다 —
사용자 입력은 비검증이라 사전을 오염시킬 수 있다.

**코드에 층 어휘 0**(B1) — 확장 규칙(query_traverse)·문장 틀(fact_templates)·
질문 의도의 표기(query_intents)가 전부 층 config의 값이다. 층이 늘어도 이 파일은
그대로이고, 그것이 J3(품질층 추가에 core 무수정)의 근거다. 여기서 하는 일은
**스펙을 인자로 받아 도는 조립**뿐이다.
"""
from __future__ import annotations

import json

from . import store
from . import llm
from .ids import norm
from .status import STATUS_MERGED, STATUS_OBSOLETE, is_live, resolve_chain

COLLECT_LIMIT = 8               # ③ 수집 상한 (CH5 5.1 규약 6). 초과분은 tier2부터 자른다.

PATH_GRAPH = "graph_fact"
PATH_CHUNK = "chunk"
PATH_BOTH = "both"
PATH_GENERAL = "general_knowledge"

# 의도 이름 → 답의 소재 (CH5 5.3 질문 유형 대응표). **이름은 골격 어휘이고, 어떤 말이
# 그 의도인지는 층 config가 값으로 준다** — D-49의 "구문 N종 + 데이터에서 온 값"과 같은
# 분업이다. 이원 채널은 어느 의도에서도 둘 다 공급하지만, **답이 어디에 있는지**는
# 질문 유형이 정한다 — 서술형에 그래프 사실을 답으로 내밀면 그건 답이 아니다.
INTENT_PATH = {"flow": PATH_GRAPH, "order": PATH_GRAPH, "value": PATH_GRAPH,
               "reverse": PATH_GRAPH, "structure": PATH_GRAPH,
               "describe": PATH_CHUNK, "general": PATH_GENERAL}


# ---------------------------------------------------------------- ① 링킹
LINK_SCHEMA = {
    "type": "object",
    "properties": {"node_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["node_ids"], "additionalProperties": False,
}


def _link_llm(question, graphs):
    """**링킹 2단 — LLM 폴백** (LLM 지점 ⑥ · 문서 5 §5.1-1).

    **1단(사전 스캔)이 미스했을 때만 돈다.** "앞 단이 히트하면 뒤 단을 돌지
    않는다" — 조건절로만 적힌 것을 항상 도는 구현으로 읽으면 사전이 답한 질의에도
    호출이 고정 비용으로 붙고, 하이브리드 도입 판정(§5.5)의 근거인 **링킹 미스율이
    실제 미스가 아닌 값으로 오염된다.**

    **3단(임베딩 검색)은 이연이다 — 지금 구현하지 않는다**(P7: 측정 없는 선반영
    금지). 미스율이 쌓인 뒤에 판정한다.

    **USE_MOCK에서는 폴백을 두지 않는다**(문서 7 §7.1 대체 표) — 사전 스캔 미스는
    그대로 링킹 미스로 `link_miss`에 적재한다. 문자열 포함·유사도 같은 임의 대체를
    만들지 않는다: 임의 대체는 미스가 아닌 값을 계기판에 실어 P7 판정이 자기
    구현에 의존하게 만들고, 12문항 스모크의 `expected_path` 채점을 구현마다 다르게
    만든다.

    실호출 갈래도 **후보 밖 id는 버린다** — 모델이 지어낸 id로 질의가 답하면
    그래프에 없는 근거를 제시하게 된다.
    """
    if llm.use_mock():
        return []
    llm.require("link")
    live = {nid: (lay, n) for lay, g in graphs.items()
            for nid, n in g.nodes.items() if is_live(n)}
    if not live:
        return []
    pool = [{"id": nid, "canonical": n["canonical"], "category": n["category"]}
            for nid, (_lay, n) in live.items()]
    out = llm.chat(
        [{"role": "system", "content": llm.prompt("link")},
         {"role": "user", "content": json.dumps(
             {"question": question, "candidates": pool}, ensure_ascii=False)}],
        json_schema=LINK_SCHEMA, point="link")
    ids = {p["id"] for p in pool}
    hits = []
    for nid in out.get("node_ids", []):
        if nid not in ids:
            continue                     # 후보 밖 id는 버린다
        lay, n = live[nid]
        hits.append({"surface": n["canonical"], "node_id": nid, "layer": lay})
    return hits


def nearby(question, dictionary, graphs, limit=5):
    """근거 없음일 때 **인접 등록 개체**를 제시한다 (갭 spec-A-153 · impl-B-19).

    **답이 아니라 재질문의 재료다.** 근거가 없다고만 말하면 사람이 표기를 바꿔
    가며 되묻고, 그 재시도가 전부 링킹 미스로 적재되어 **계기판 5(링킹 미스율)의
    분자를 오염시킨다** — 미스가 아니라 표기 탐색인데 미스로 세어진다.

    **판정 파이프라인을 쓰지 않는다** — 여기서 고르는 것은 "같은 개념인가"가
    아니라 "사람이 다시 물어볼 만한 이름인가"이고, 판정을 태우면 그 결과가
    링킹인 것처럼 보인다. 질문의 어절과 등재 표기의 **글자 겹침**으로만 고른다.

    **읽기 전용이다**(P6) — 아무것도 쓰지 않고 로그도 남기지 않는다.
    """
    q = norm(question)
    toks = [w for w in q.split() if len(w) >= 2]
    if not toks:
        return []
    scored = []
    for surface in dictionary.surfaces():
        if not surface or len(surface) < 2:
            continue
        s = max((len(set(surface) & set(w)) / max(len(set(surface)), 1)
                 for w in toks), default=0.0)
        if s < 0.5:
            continue
        for nid in dictionary.lookup(surface):
            for layer, g in graphs.items():
                n = g.get(nid)
                if n is None or not is_live(n):
                    continue
                scored.append((s, surface, nid, layer, n["category"]))
                break
    scored.sort(key=lambda x: (-x[0], x[1]))
    out, seen = [], set()
    for s, surface, nid, layer, cat in scored:
        if nid in seen:
            continue
        seen.add(nid)
        out.append({"surface": surface, "node_id": nid, "layer": layer,
                    "category": cat})
        if len(out) >= limit:
            break
    return out


def link(question, dictionary, graphs):
    """표기 → 노드. **사전 스캔 우선**(무LLM)이며 **긴 표면형이 이긴다**.

    긴 것부터 보는 이유: "노칭 정밀도"가 있는데 "노칭"이 먼저 맞으면 질문이 가리킨
    것보다 넓은 노드에 붙는다.

    **3단 구조와 그 게이팅**(문서 5 §5.1-1): ①사전 스캔(무LLM) → ②LLM 폴백 →
    ③임베딩 검색(**이연 — 구현하지 않는다**). **앞 단이 히트하면 뒤 단을 돌지
    않는다.**

    극성 링킹은 **넓게** 한다(CH5 5.1 규약 3 — 쓰기는 좁게와 대칭): 사전이 한 표기에
    여러 노드를 달고 있으면 전부 링킹한다. 극성 무관 표기는 개념 노드에 붙고,
    인스턴스는 part_of 하향이 데려온다.
    """
    q = norm(question)
    hits, taken = [], []
    # 사전 스캔은 관문 경유다 (문서 7 §7.1) — 긴 표기 우선으로 훑는다.
    for surface in sorted(dictionary.surfaces(), key=len, reverse=True):
        if not surface or surface not in q:
            continue
        if any(surface in t for t in taken):        # 이미 더 긴 표기로 잡힌 자리
            continue
        taken.append(surface)
        for nid in dictionary.lookup(surface):
            for layer, g in graphs.items():
                n = g.get(nid)
                if n is not None:
                    hits.append({"surface": surface, "node_id": nid, "layer": layer})
    if hits:
        return hits                      # **1단이 찾았으면 2·3단은 돌지 않는다**
    return _link_llm(question, graphs)   # 2단 — USE_MOCK에서는 빈 목록(미스는 로그로)


def transit(graph, nid, cfg):
    """툼스톤·폐기 전이 — 옛 id에 닿으면 **현재 노드로 옮겨** 답한다 (R3-⑶ · L5·L8).

    돌려주는 것은 `(현재 node_id, 표기 or None, 노출 여부)`다.

      · `merged_into` 체인 → 생존자로 전이(표기 없음 — 병합은 같은 것의 통합이다)
      · `obsolete` + `replaced_by` → 대체 노드로 전이 + **"(대체됨: 구명칭)" 표기**
      · `obsolete` + `replaced_by` 없음 → 일반 결과에서 **제외**하되, 정확 이름으로
        직접 지명한 질의에는 **"폐기됨"을 명시**해 답한다 — 침묵 소실 금지(D-30 계보)

    체인 추적의 순환·깊이 방어는 `core.status.resolve_chain`이 소유한다(L8 읽기 측).
    """
    tpl = cfg.get("fact_templates") or {}
    n = graph.get(nid)
    if n is None:
        return nid, None, True
    if n.get("status") == STATUS_MERGED:
        return resolve_chain(graph, nid, STATUS_MERGED), None, True
    if n.get("status") != STATUS_OBSOLETE:
        return nid, None, True
    if n.get("replaced_by"):
        tgt = resolve_chain(graph, nid, "replaced_by")
        note = tpl.get("node:replaced", "(대체됨: {old})").format(
            old=n["canonical"], new=(graph.get(tgt) or {}).get("canonical", ""))
        return tgt, note, True
    return nid, tpl.get("node:obsolete", "{node}는 폐기된 항목이다").format(
        node=n["canonical"]), False


def log_miss(question):
    """링킹 미스는 버리지 않고 쌓는다 — 하이브리드 서치 도입 판정의 데이터다(5.4)."""
    store.append_line(store.LINK_MISS, question)


# ---------------------------------------------------------------- ② 확장
def expand(graph, ids, cfg):
    """config의 `query_traverse` 스펙대로만 뻗는다.

    `precedes`는 확장에 넣지 않는다(순서는 그래프 사실 채널과 flow 특례가 담당) —
    `mirrors`도 기본 확장에 없다. 둘 다 **config가 그렇게 선언**하기 때문이며 코드는
    관계 이름을 모른다. 전파는 프론티어 방식이라 다른 관계로 도달한 노드에도 규칙이
    적용된다 — 공정→(part_of 하향)→설비→(has_property)→인자 2홉이 성립하는 근거다.
    """
    return graph.neighbors(ids, cfg.get("query_traverse") or {})


def bridge(src_ids, home_layer, graphs, configs):
    """cross-layer 브리지 **1홉·비재귀·양방향**.

    걸침 엣지는 **출발 층의 그래프**에 저장된다(구현문서 §2.2) — 그래서 공정층 노드로
    물어도 품질층 그래프를 훑어야 답이 나온다. 어느 관계가 브리지인지는 그 층의
    `cross_layer_traverse`가 값으로 선언한다.
    """
    found, crossed = {}, []
    for layer, g in graphs.items():
        # **홈층 특례를 두지 않는다**(문서 5 §5.1-4 — 허브 판정 2A P-D).
        #
        # §5.1-4의 "라우터가 **홈층이 아닌 전 층의** config에서 이 키를 읽고"는
        # **타층을 빠뜨리지 말라는 요구**이지 홈층을 빼라는 뜻이 아니다. 브리지는
        # 양방향 1홉이고 중복은 아래 방문 집합이 막는다. 특례를 두면 **같은
        # 질문이 어느 층에서 출발하느냐에 따라 다른 답을 낸다** — 홈층이 선언층인
        # 관계(quality의 occurs_in·controlled_by)가 quality발 질의에서만 사라진다.
        spec = (configs[layer].get("cross_layer_traverse") or {})
        if not spec:
            continue
        for e in g.edges:
            if e.get("status") == "deleted_by_user" or e["rel"] not in spec:
                continue
            d = spec[e["rel"]].get("direction", "both")
            hit = ((d in ("out", "both") and e["dst"] in src_ids)
                   or (d in ("in", "both") and e["src"] in src_ids))
            if not hit:
                continue
            other = e["src"] if e["dst"] in src_ids else e["dst"]
            if other in src_ids:
                continue                    # 출발 집합으로 되돌아오는 것은 확장이 아니다
            found.setdefault(layer, set()).add(other)
            crossed.append((layer, e))
    return found, crossed


def cross_facts(crossed, graphs, configs):
    """걸침 엣지의 문장화 — **출발 층의 템플릿을 쓴다**(§8-R4).

    같은 층 안의 엣지와 갈라 두는 이유: 걸침 엣지는 **dst가 다른 층 그래프에 산다.**
    한 층의 노드 집합만 보고 문장화하면 이 엣지는 양끝이 한 집합에 들어오지 않아
    영영 렌더되지 않는다 — "노칭에서 나는 불량은?"이 답을 못 내던 자리다.
    """
    out = []
    for layer, e in crossed:
        tpl = (configs[layer].get("fact_templates") or {}).get(e["rel"])
        src, dst = _find(graphs, e["src"]), _find(graphs, e["dst"])
        if tpl and src and dst:
            out.append(tpl.format(src=src["canonical"], dst=dst["canonical"]))
    return out


def _find(graphs, nid):
    """노드는 어느 층 그래프에든 있을 수 있다 — 걸침 엣지의 양끝이 그렇다."""
    for g in graphs.values():
        n = g.get(nid)
        if n is not None:
            return n
    return None


# ---------------------------------------------------------------- ③ 수집
class _desc:
    """문자열을 **내림차순**으로 비교하는 래퍼 — 정렬 키 안에서 한 축만 뒤집는다.

    `reverse=True`는 전체 키를 뒤집으므로 tier·chunk_id까지 함께 뒤집힌다.
    음수화가 안 되는 문자열 축을 뒤집는 표준 수단이 없어 비교만 뒤집는다.
    """

    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        return self.v > other.v

    def __eq__(self, other):
        return self.v == other.v


def collect_chunks(node_ids, direct):
    """2-tier(직접 링킹 > 확장) · 상한 8 · 최신순. **잘림은 로그로 남긴다**(계기판 재료)."""
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    by_node = {}
    for d in ch["describes"]:
        by_node.setdefault(d["node_id"], []).append(d["chunk_id"])
    tier1 = [(1, cid) for nid in direct for cid in by_node.get(nid, [])]
    tier2 = [(2, cid) for nid in node_ids if nid not in direct
             for cid in by_node.get(nid, [])]

    # **정렬 키는 셋이다**(문서 5 §5.1-6): ①tier(1이 항상 앞) ②청크의 `parsed_at`
    # **내림차순** ③동률은 `chunk_id` 사전순.
    #
    # 기준 필드가 없으면 구현이 파일 mtime·describes 삽입 순서를 **발명**하고,
    # 상한 8이 무작위 축에서 잘린다. 그 차이는 계기판 4(청크 잘림률)에 잡히지
    # 않는다 — **잘린 건수는 같고 잘린 대상만 다르기 때문이다.**
    def _key(item):
        tier, cid = item
        c = ch["chunks"].get(cid) or {}
        # parsed_at 내림차순 — 문자열 역순 정렬을 위해 튜플에서 뒤집는다.
        return (tier, _desc(c.get("parsed_at") or ""), cid)

    ordered, seen = [], set()
    for tier, cid in sorted(tier1 + tier2, key=_key):
        if cid in seen:
            continue
        seen.add(cid)
        c = ch["chunks"].get(cid)
        if c:
            ordered.append({"chunk_id": cid, "doc_id": c["doc_id"], "text": c["text"],
                            "tier": tier, "section": c.get("section"),
                            "source_locator": c.get("source_locator")})
    dropped = max(0, len(ordered) - COLLECT_LIMIT)
    if dropped:
        store.append_line(store.CHUNK_TRUNCATED, f"{dropped}건 잘림")
    return ordered[:COLLECT_LIMIT], dropped


# ---------------------------------------------------------------- ④ 답변 — 채널 1
def facts(graph, node_ids, cfg):
    """[그래프 사실] — 수집 노드의 엣지·값을 `fact_templates`로 문장화한다.

    **순서·규격은 이 채널에만 있다.** 청크 단채널이면 "노칭 다음은?"에 답하지 못한다.
    맥락형 attr는 context 그룹별로 한 줄씩 낸다(같은 인자의 M1·M2 규격은 충돌이
    아니라 병렬 항목이기 때문이다).
    """
    tpl = cfg.get("fact_templates") or {}
    out = []
    for e in graph.edges:
        if e.get("status") == "deleted_by_user":
            continue
        if e["src"] not in node_ids or e["dst"] not in node_ids or e["rel"] not in tpl:
            continue
        s, d = graph.get(e["src"]), graph.get(e["dst"])
        # **이 층에 없는 끝점은 여기서 문장화하지 않는다** — 걸침 엣지의 반대쪽이고
        # 그 자리는 `cross_facts`다(가리키는 층의 템플릿을 쓴다 — 문서 5 §5.4-1).
        # 홈층 브리지가 켜지면서 collected에 타층 id가 섞여 실측으로 드러났다.
        if s is None or d is None:
            continue
        out.append(tpl[e["rel"]].format(src=s["canonical"], dst=d["canonical"]))
    for nid in node_ids:
        n = graph.get(nid)
        if n is None:
            continue                        # 상동 — 타층 노드는 그 층이 문장화한다
        for name, val in (n.get("attrs") or {}).items():
            t = tpl.get(f"attr:{name}")
            if not t or val is None:
                continue
            for item in (val if isinstance(val, list) else [val]):
                if not isinstance(item, dict) or item.get("value") is None:
                    continue
                line = t.format(node=n["canonical"], value=item["value"],
                                prov=", ".join(item.get("provenance") or []))
                ctx = item.get("context")
                out.append(f"[{_ctx(ctx)}] {line}" if ctx else line)
    return out


def _ctx(ctx):
    return ", ".join(f"{k}={v}" for k, v in sorted(ctx.items()))


# ---------------------------------------------------------------- 순서 파생 (규약 8)
def next_of(graph, nid, cfg):
    """순서 파생 — **자기 선언 > 부모 파생 > "순서 정보 없음"** (틀 §4B-A11-5).

    ①노드 자신에게 `precedes` 선언이 있으면 그것이 답이다.
    ②없으면 부모로 올라가 부모의 후속 Q를 찾고, **Q에 나와 같은 축값 인스턴스가
      있으면 그리로 하강**한다 — 없으면 Q 자체다(공유 스텝 합류가 자동으로 된다).
    ③조상까지 선언이 없으면 **추측하지 않고** "순서 정보 없음"으로 답한다.

    돌려주는 것은 `(후속 노드 id 또는 None, 해상도 노드 id)`다. 해상도를 함께 주는
    이유: 인스턴스 질문에 개념 해상도로 답하는 경우를 사람이 오해하지 않게
    **답변에 그 기준을 표기**해야 하기 때문이다(fact_template).
    """
    skel = cfg.get("skeleton") or {}
    child_rel = (skel.get("relations") or {}).get("child")
    sib_rel = (skel.get("relations") or {}).get("sibling")
    if not child_rel or not sib_rel:
        return None, None
    cur, seen = nid, set()
    while cur and cur not in seen:
        seen.add(cur)
        nxt = [e["dst"] for e in graph.edges if e["src"] == cur and e["rel"] == sib_rel]
        if nxt:
            return _descend(graph, nxt[0], graph.get(nid).get("polarity"),
                            child_rel), cur
        up = [e["dst"] for e in graph.edges if e["src"] == cur and e["rel"] == child_rel]
        cur = up[0] if up else None
    return None, None


def _descend(graph, target, polarity, child_rel):
    """후속 노드에 **같은 축값 인스턴스**가 있으면 그리로 내려간다(없으면 개념 그대로).

    이것이 "공유 스텝 합류 자동"의 실체다 — 극성 가지를 타던 질문이 극성 없는
    공통 스텝을 만나면 그냥 그 스텝으로 답이 나온다.
    """
    if not polarity or polarity == "none":
        return target
    for e in graph.edges:
        if e["rel"] == child_rel and e["dst"] == target:
            child = graph.get(e["src"])
            if child and child.get("polarity") == polarity:
                return e["src"]
    return target


def flow_chain(graph, cfg):
    """flow 특례 — **개념 노드 레벨 대표 흐름 체인**을 통째로 공급한다(5.2 규약 4).

    골격이 얇아 저비용이고, 축 인스턴스는 제외한다 — 극성 인스턴스 간에는 순서가
    선언되지 않으므로(J12) 흐름의 단위는 개념 노드다.
    """
    sib = ((cfg.get("skeleton") or {}).get("relations") or {}).get("sibling")
    tpl = (cfg.get("fact_templates") or {}).get(sib, "{src} → {dst}")
    return [tpl.format(src=graph.get(e["src"])["canonical"],
                       dst=graph.get(e["dst"])["canonical"])
            for e in graph.edges
            if e["rel"] == sib
            and graph.get(e["src"]).get("polarity") in (None, "none")]


# ---------------------------------------------------------------- 의도
def intent_of(question, cfg):
    """질문 의도 — **표기 목록은 config가 소유한다**(층 어휘이기 때문이다).

    코드가 아는 것은 "의도 이름으로 갈린다"는 절차뿐이고, 어떤 말이 어떤 의도인지는
    층이 값으로 선언한다. 우선순위는 선언 순서다.

    이 표기 대조는 **USE_MOCK의 결정적 분류기**다(구현문서 §8 — 문형 규칙).
    # (LLM 지점 **8종 밖**의 여지다 — §7.6-B-2의 닫힌 목록에 질문 유형 판정은
    #  없다. 규칙 분류기로 충분한지는 미스율이 쌓인 뒤 판정한다(P7).)
    # 실물 경로에서는 LLM이 질문 유형을 판정할 수 있고, 그때도 유형의
    # 이름과 답의 소재(INTENT_PATH)는 그대로다. 바뀌는 것은 분류 수단뿐이다.
    """
    q = norm(question)
    for name, marks in (cfg.get("query_intents") or {}).items():
        if any(m in q for m in marks):
            return name
    return None
