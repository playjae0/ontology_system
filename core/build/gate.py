# -*- coding: utf-8 -*-
"""칸 3.1·3.6 — n4 커밋 게이트 — **문서 유래 엣지**가 그래프에 쓰이기 전의 관문 (CH3A 3.4).

엣지가 생기는 경로는 넷이고, 그중 **셋이 이 관문을 지난다**:
    ① seed(사람·골격) — **비경유**  ② edges 선언(스키마·정형) ③ 추출 후보(LLM·비정형)
    ④ 자동 규칙(코드)

**① seed가 비경유인 것은 우회가 아니라 설계다**(틀 §4B-A3 경로 ①): seed는 후보가
아니라 **선언**이다. 사람이 파일에 적은 골격을 코드가 다시 판정할 근거가 없고,
판정할 표(`relation_patterns`)를 골격까지 덮도록 넓히면 **경로 ③이 골격을 개정할 수
있게 된다** — A5 하향 한정·발명 금지 ③ 위반이다. 그래서 골격 관계
(`Process part_of/precedes/mirrors Process`)는 패턴표에 **넣지 않는다.**
층이 어떤 관계를 갖는지의 선언은 config `relations` 배열이 이미 하고 있고,
`relation_patterns`는 그것과 별개인 **추출용 게이트 패턴**이다.
골격 엣지는 loader(n10)가 `status="seed"`로 직접 쓴다.

분기 (CH3A 3.4):
    패턴 안                  → 커밋
    패턴과 방향만 반대        → 커밋하지 않고 `direction_conflict` 큐 (**자동으로 뒤집지 않는다**)
    같은 두 노드에 반대 방향 엣지가 이미 있음(층 전부 · 대칭 관계 밖 — B175)
                              → 위아래 쌍의 관계(구조)면 커밋하지 않고 `direction_conflict` 큐(먼저 선 것을 둔다 · 두 출처)
                                · 그 밖(사실)은 커밋하고 문서 끝 결과에 「반대 방향 공존」
    관계는 선언됐으나 패턴 밖 → 거부 + 사유 기록 (`invalid_pattern`)
    관계 자체가 미선언        → 발생 불가(③이 닫힌 목록 선택) — 방어적으로 거부 + 기록
    동종 쌍 방향성 관계의 ③   → 커밋하지 않고 `direction_unverifiable` 큐 (근거 청크 동봉)

②④는 정의상 패턴 안이라 **무비용 통과**이고, 게이트는 ③에게만 실질 관문이다.
정형 edges 선언(②)의 동종 쌍은 커밋된다 — PFMEA의 causes 연쇄가 살아 있는 근거다.

**자동 방향 교정을 하지 않는 이유**: 인과 그래프에서 방향 반전은 틀린 사실을
확신 있게 기록하는 것이다. 사람이 판정해야 한다.

**거부는 버리는 것이 아니라 기록하는 것이다.** 다만 거부 기록은 **큐가 아니라 로그**다
(D-7) — 처리 대상이 아니라 커버리지 관측 신호이기 때문이다. 거부가 잦으면 고칠 것은
코드가 아니라 config의 패턴 선언이다(I7).
"""
from __future__ import annotations

import weakref

from core.state import store

COMMIT = "commit"
DIRECTION_CONFLICT = "direction_conflict"
DIRECTION_UNVERIFIABLE = "direction_unverifiable"
INVALID_PATTERN = "invalid_pattern"
UNDECLARED = "undeclared_relation"
UNRESOLVED_ENDPOINT = "unresolved_endpoint"     # 끝점 미해소 — 큐가 아니라 로그다(D-7)
SAME_NODE = "same_node"                         # 두 끝이 같은 노드 — 세우지 않고 기록한다(문서 1 J32 · B186 ②)

# 경로 이름 — ①(seed)은 여기 없다. 이 관문에 오지 않기 때문이다(위 설명).
# 죽은 상수를 남겨 두면 다음 사람이 그것을 태워도 되는 신호로 읽는다.
PATH_SCHEMA = "schema"      # ②
PATH_EXTRACT = "extract"    # ③
PATH_AUTO = "auto"          # ④


def _index(cfg):
    from core.state import catalog
    pats = catalog.layer_patterns(cfg)                   # 층 패턴 + 그 층에 걸리는 위아래 쌍(B174 ②)
    forward = {(p["src"], p["rel"], p["dst"]): p for p in pats}
    reverse = {(p["dst"], p["rel"], p["src"]): p for p in pats
               if not p.get("symmetric")}
    declared = {p["rel"] for p in pats}
    return forward, reverse, declared


def pair_relation(cfg, src_cat, dst_cat):
    """관계는 공통 config의 위아래 쌍이 결정한다 — 게이트 패턴표의 특수형(§6-3 · B174 ① — 층마다 두지 않고 한 곳).

    표·산문·재시도 세 경로가 같은 함수를 읽는다(`catalog.pair_relation` — 그 층이 두 카테고리를 다 말할 때만)."""
    from core.state import catalog
    return catalog.pair_relation(cfg, src_cat, dst_cat)



def judge(src_cat, rel, dst_cat, cfg, path):
    """한 후보의 분기를 정한다. 그래프는 건드리지 않는다 — 판정만 한다."""
    forward, reverse, declared = _index(cfg)
    key = (src_cat, rel, dst_cat)

    if rel not in declared:
        return UNDECLARED, None

    pat = forward.get(key)
    if pat:
        # 동종 쌍 방향성 관계는 ③에게만 막힌다 — 카테고리 조합이 방향을 주지
        # 못하므로 출처가 필요하다(틀 A3). ②는 행 구조가 곧 방향이라 통과한다.
        if (path == PATH_EXTRACT and src_cat == dst_cat
                and not pat.get("symmetric")):
            return DIRECTION_UNVERIFIABLE, pat
        return COMMIT, pat

    if key in reverse:
        return DIRECTION_CONFLICT, reverse[key]

    return INVALID_PATTERN, None


def _categories(n):
    """끝점의 카테고리 집합 = 주 ∪ 겸 (B90 ③). 카탈로그를 못 읽으면 주 하나."""
    from core.state import catalog
    try:
        return catalog.categories_of(n)
    except catalog.CatalogError:
        return {n["category"]}


def _judge_also(s, rel, d, cfg, path, verdict, pat=None):
    """**겸을 인정한다**(B90 ③) — 주 카테고리 쌍이 통과하지 못했을 때만 겸 조합을 본다 · `(분기, 패턴)`.

    끝점의 카테고리 집합 = 주 ∪ 겸이고, 어느 조합이든 패턴에 있으면 통과다(스테이션
    노드에 `구성품 part_of 설비`가 바로 붙는다). 겸이 없으면 주 판정 그대로다 — 한 조합뿐이다.
    """
    sc, dc = _categories(s), _categories(d)
    if len(sc) == 1 and len(dc) == 1:
        return verdict, pat
    for a in sorted(sc):
        for b in sorted(dc):
            if (a, b) != (s["category"], d["category"]):
                v, p = judge(a, rel, b, cfg, path)
                if v == COMMIT:
                    return COMMIT, p
    return verdict, pat


#: 이번 실행의 **반대 방향 공존**(B175) — 사실 관계의 반대 방향이 함께 선 쌍 · 문서 끝 결과가 그 문서 몫을 읽는다(`entry._result`)
COEXIST = []
#: 반대 방향 판정의 범위 — 이 실행이 쓰는 그래프(층 → 살아 있는 사본) · 나머지 층은 읽기 전용 사본(`GraphStore.snapshot`)
_LIVE = {}
#: 그래프마다 엣지 색인 — 층 → `{g, n, map, node}`(엣지 목록은 빌드 동안 뒤에만 붙는다 — 늘어난 몫만 더한다)
_IDX = {}
#: 이번 실행의 **다른 층의 같은 엣지에 출처만 더함**(B180 ②) — 문서 끝 결과가 그 문서 몫을 읽는다(`entry._result`)
SHARED = []
#: 그래프 → 그 그래프를 쓰는 손의 「층 열기」(B180 ② — 다른 층의 같은 엣지에 출처를 더할 때 그 층을 **그 손이 저장하는 그래프**로
#: 연다 · `bind` · 먼저 건 손이 이긴다)
_OPEN = weakref.WeakKeyDictionary()


def bind(graphs, opener):
    """이 그래프들을 쓰는 손의 층 열기 `opener(층) -> 그래프 또는 None`을 건다(빌더 · 재연결 배치) — 이미 걸렸으면 그대로.
    **`opener`는 손 · 그래프를 약하게만 쥔다**(값이 키를 강하게 쥐면 약한 키가 풀리지 않아 문서마다 빌더가 쌓인다) — 손이 사라지면
    None을 돌려준다."""
    for g in graphs:
        if g is not None and g not in _OPEN:
            _OPEN[g] = opener


def _world(*graphs):
    """**층 전부**(엣지는 문서 층에 산다 — B100) — 넘겨받은 그래프 · 이 실행이 쓰던 사본(그 뒤로 파일을 쓴 자리가 없을 때) ·
    나머지는 읽기 전용 사본."""
    from router import discover
    from core.graph import GraphStore
    out = {g.layer: g for g in graphs if g is not None}
    _LIVE.update(out)
    for lay in discover():
        if lay not in out:
            g = _LIVE.get(lay)
            out[lay] = g if g is not None and g.current() else GraphStore.snapshot(lay)
    return out


def _edge_map(g):
    ix = _IDX.get(g.layer)
    if ix is None or ix["g"] is not g or ix["n"] > len(g.edges):
        ix = _IDX[g.layer] = {"g": g, "n": 0, "map": {}}
    node = ix.setdefault("node", {})
    for e in g.edges[ix["n"]:]:
        ix["map"][(e["src"], e["rel"], e["dst"])] = e
        node.setdefault(e["src"], []).append(e)
        node.setdefault(e["dst"], []).append(e)
    ix["n"] = len(g.edges)
    return ix["map"]


def _node_edges(g):
    """그 그래프의 노드 → 그 노드가 끝인 엣지 목록(같은 색인)."""
    _edge_map(g)
    return _IDX[g.layer]["node"]


def _node_in(world, nid):
    return next((g.get(nid) for _l, g in sorted(world.items()) if g.get(nid)), None)


def parent_edge(nid, *graphs):
    """**부모 엣지**(B180 ①) — 그 노드를 아래 끝으로 둔 위아래 쌍 엣지(두 끝 카테고리(주 ∪ 겸) · 관계 · 방향이 공통 config의 쌍과
    같다)가 **층 전부**(`_world` — 넘겨받은 그래프 · 이 실행이 쓰는 그래프 · 나머지는 읽기 전용 사본)에 있나 — `(관계, 위 노드 id,
    위 canonical, 위가 출발인가)` 또는 None · 사람이 지운 엣지 · 근거(출처) 0 엣지는 세지 않는다. 위치 폴백(좌표 · 제목 사슬)은 이것이 None일 때만 선다."""
    from core.graph import STATUS_DELETED
    from core.state import catalog
    world = _world(*graphs)
    me = _node_in(world, nid)
    if not me:
        return None
    mine = _categories(me)
    for p in catalog.pairs():
        if p["lower"] not in mine:
            continue
        up_src = p.get("src") == "upper"
        for lay in sorted(world):
            for e in _node_edges(world[lay]).get(nid) or ():
                if e["rel"] != p["rel"] or e.get("status") == STATUS_DELETED or not e.get("provenance"):
                    continue                        # 지운 엣지 · 근거 0 엣지(다시 넣기의 회수가 출처를 걷었다)는 부모가 아니다
                other = e["src"] if up_src and e["dst"] == nid else (e["dst"] if not up_src and e["src"] == nid else None)
                up = _node_in(world, other) if other else None
                if up and p["upper"] in _categories(up):
                    return p["rel"], other, up.get("canonical"), up_src
    return None


def _same(world, here, src, rel, dst):
    """같은 엣지(두 끝 · 관계 · 방향)가 **다른 층**에 있나 — `(층, 엣지)` 또는 None(사람이 지운 엣지도 돌려준다 — 부르는 쪽이 건너뛴다)."""
    for lay in sorted(world):
        if lay != here:
            e = _edge_map(world[lay]).get((src, rel, dst))
            if e is not None:
                return lay, e
    return None


def _share(graph, world, hit, src, rel, dst, provenance, doc_id, s, d):
    """다른 층의 같은 엣지에 출처를 더한다(B180 ②) — 그 층을 **쓰는 손이 저장하는 그래프**(`bind`의 층 열기)로 연다 · 연 손이 없으면
    이 실행이 쓰는 그래프일 때만 · 아니면 False(이 층에 쓴다 — 연 손 없는 호출)."""
    lay, e = hit
    opener = _OPEN.get(graph)
    og = opener(lay) if opener is not None else None
    if og is not None:
        e = og.edge(src, rel, dst)
    elif _LIVE.get(lay) is not world[lay]:
        return False
    if e is None:
        return False
    for p in provenance or []:
        if p not in e["provenance"]:
            e["provenance"].append(p)
    SHARED.append({"doc_id": doc_id, "rel": rel, "src": s["canonical"], "dst": d["canonical"],
                   "layer": lay, "from": graph.layer})
    return True


def _opposite(world, src, rel, dst):
    """같은 두 노드 · 같은 관계의 **반대 방향** 엣지 `(층, 엣지)` — 사람이 지운 엣지는 아니다 · 없으면 None."""
    from core.graph import STATUS_DELETED
    for lay in sorted(world):
        e = _edge_map(world[lay]).get((dst, rel, src))
        if e is not None and e.get("status") != STATUS_DELETED:
            return lay, e
    return None


#: 거부의 출처 — 경로 → 이름(B118 ⑥ 거부 묶음의 칸 · 연결 보강은 `source`로 준다)
SOURCE = {PATH_SCHEMA: "정형", PATH_EXTRACT: "추출", PATH_AUTO: "자동"}


def log_reject(rel, src_cat, dst_cat, verdict, path, doc_id, source=None, layer=None, extra=None):
    """거부 기록 — 사유별 건수. 큐가 아니라 로그다(D-7). `source`는 경로보다 좁은 출처(연결 보강 — B118 ⑥) · `layer`는
    판정한 config의 층(넣을 패턴 줄의 자리) · `extra`는 사유가 더 싣는 칸(같은 노드 — 노드 · 두 표기 · B186 ②)."""
    log = store.read(store.GATE_REJECTS, {"rejects": [], "counts": {}})
    log["rejects"].append({"rel": rel, "src_cat": src_cat, "dst_cat": dst_cat,
                           "verdict": verdict, "path": path, "doc_id": doc_id,
                           "source": source or SOURCE.get(path, path), "layer": layer, **(extra or {})})
    log["counts"][verdict] = log["counts"].get(verdict, 0) + 1
    store.write(store.GATE_REJECTS, log)


def commit_edge(graph, src, rel, dst, cfg, path, provenance, doc_id,
                evidence_chunk=None, src_graph=None, dst_graph=None, source=None, surfaces=None):
    """게이트를 통과시킨 뒤에만 엣지를 쓴다. 돌려주는 것은 분기 이름이다.

    `src_graph`·`dst_graph`는 **걸침 엣지**용이다 — 끝점이 다른 층에 살아도 엣지 자체는
    출발 층의 그래프에 저장한다(구현문서 §2.2). **양쪽을 같게 받는다**: `to`만 받던
    구판은 `from`이 걸침일 때 판정 전에 무음으로 사라졌다(D-61 수리의 남은 절반).

    끝점이 해소되지 않았으면 **그것도 기록한다** — 거부는 버리는 것이 아니라 기록하는
    것이고(D-7), 무기록 소멸은 아무도 모른다. **두 끝이 같은 노드면 세우지 않고 기록한다**(문서 1 J32 · B186 ②) —
    `surfaces`는 두 끝의 원래 표기(칸 · 언급 — 없으면 노드 이름) · 인입은 멈추지 않는다(그 엣지 하나만).
    """
    s = (src_graph or graph).get(src) if src else None
    d = (dst_graph or graph).get(dst) if dst else None
    if not s or not d:
        log_reject(rel, "?" if not s else s["category"], "?" if not d else d["category"],
                   UNRESOLVED_ENDPOINT, path, doc_id, source, cfg.get("layer"))
        return UNRESOLVED_ENDPOINT
    if src == dst:
        a, b = (list(surfaces or ()) + [None, None])[:2]          # 칸 값은 숫자일 수 있다 — 기록은 글자로(대조 · 화면이 같은 꼴을 읽는다)
        log_reject(rel, s["category"], d["category"], SAME_NODE, path, doc_id, source, cfg.get("layer"),
                   {"node": s["canonical"], "node_layer": s.get("layer"),
                    "surfaces": [str(x) if x not in (None, "") else s["canonical"] for x in (a, b)]})
        return SAME_NODE
    verdict, pat = judge(s["category"], rel, d["category"], cfg, path)
    if verdict != COMMIT:
        verdict, pat = _judge_also(s, rel, d, cfg, path, verdict, pat)

    if verdict == COMMIT:
        hit = None
        if graph.edge(src, rel, dst) is None:          # 이 층에 없을 때만(같은 층의 중복 · 툼스톤은 `add_edge`가 그대로)
            world = _world(graph, src_graph, dst_graph)
            same = _same(world, graph.layer, src, rel, dst)   # **같은 엣지는 그래프 전체에 한 벌**(B180 ②)
            if same is not None:
                from core.graph import STATUS_DELETED
                if same[1].get("status") == STATUS_DELETED or _share(graph, world, same, src, rel, dst, provenance,
                                                                     doc_id, s, d):
                    return COMMIT                      # 사람이 지운 엣지(어느 층이든)는 건너뛴다 · 아니면 출처만 더했다
            if not (pat or {}).get("symmetric"):
                hit = _opposite(world, src, rel, dst)
        if hit:
            from core.state import catalog
            first = {"layer": hit[0], "status": hit[1].get("status"), "provenance": list(hit[1].get("provenance") or [])}
            if rel in catalog.structural_relations():
                store.enqueue(DIRECTION_CONFLICT,
                              f"{s['category']} -{rel}-> {d['category']}: 같은 두 노드에 반대 방향이 먼저 있다(구조 관계 — "
                              f"먼저 선 것을 둔다 · 자동 반전 없음)", doc_id,
                              {"src": src, "rel": rel, "dst": dst,
                               "src_canonical": s["canonical"], "dst_canonical": d["canonical"],
                               "src_category": s["category"], "dst_category": d["category"],
                               "path": path, "evidence_chunk": evidence_chunk,
                               "provenance": provenance, "opposite": first})
                return DIRECTION_CONFLICT
            COEXIST.append({"doc_id": doc_id, "rel": rel, "src": s["canonical"], "dst": d["canonical"],
                            "new": {"layer": graph.layer, "path": path, "provenance": list(provenance or [])},
                            "first": first})
        # 이 관문을 지난 엣지는 전부 문서·규칙 유래다 — status는 `auto` 하나다.
        graph.add_edge(src, rel, dst, "auto", provenance)
        return COMMIT

    if verdict in (DIRECTION_CONFLICT, DIRECTION_UNVERIFIABLE):
        # 큐로 간다 — 처리 대상이다. 근거 청크를 동봉해 사람이 판정할 수 있게 한다.
        store.enqueue(verdict,
                      f"{s['category']} -{rel}-> {d['category']}: "
                      + ("패턴과 방향만 반대 (자동 반전 없음)"
                         if verdict == DIRECTION_CONFLICT
                         else "동종 카테고리 쌍의 방향은 출처가 필요하다"),
                      doc_id,
                      {"src": src, "rel": rel, "dst": dst,
                       "src_canonical": s["canonical"], "dst_canonical": d["canonical"],
                       "src_category": s["category"], "dst_category": d["category"],
                       "path": path, "evidence_chunk": evidence_chunk,
                       "provenance": provenance})
        return verdict

    log_reject(rel, s["category"], d["category"], verdict, path, doc_id, source, cfg.get("layer"))
    return verdict
