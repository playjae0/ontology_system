# -*- coding: utf-8 -*-
"""n4 커밋 게이트 — **문서 유래 엣지**가 그래프에 쓰이기 전의 관문 (CH3A 3.4).

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

from . import store

COMMIT = "commit"
DIRECTION_CONFLICT = "direction_conflict"
DIRECTION_UNVERIFIABLE = "direction_unverifiable"
INVALID_PATTERN = "invalid_pattern"
UNDECLARED = "undeclared_relation"

# 경로 이름 — ①(seed)은 여기 없다. 이 관문에 오지 않기 때문이다(위 설명).
# 죽은 상수를 남겨 두면 다음 사람이 그것을 태워도 되는 신호로 읽는다.
PATH_SCHEMA = "schema"      # ②
PATH_EXTRACT = "extract"    # ③
PATH_AUTO = "auto"          # ④


def _index(cfg):
    pats = cfg.get("relation_patterns") or []
    forward = {(p["src"], p["rel"], p["dst"]): p for p in pats}
    reverse = {(p["dst"], p["rel"], p["src"]): p for p in pats
               if not p.get("symmetric")}
    declared = {p["rel"] for p in pats}
    return forward, reverse, declared


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


def log_reject(rel, src_cat, dst_cat, verdict, path, doc_id):
    """거부 기록 — 사유별 건수. 큐가 아니라 로그다(D-7)."""
    log = store.read(store.GATE_REJECTS, {"rejects": [], "counts": {}})
    log["rejects"].append({"rel": rel, "src_cat": src_cat, "dst_cat": dst_cat,
                           "verdict": verdict, "path": path, "doc_id": doc_id})
    log["counts"][verdict] = log["counts"].get(verdict, 0) + 1
    store.write(store.GATE_REJECTS, log)


def commit_edge(graph, src, rel, dst, cfg, path, provenance, doc_id,
                evidence_chunk=None, dst_graph=None):
    """게이트를 통과시킨 뒤에만 엣지를 쓴다. 돌려주는 것은 분기 이름이다.

    `dst_graph`는 **걸침 엣지**용이다 — 도착 노드가 다른 층에 살아도 엣지 자체는
    출발 층의 그래프에 저장한다(구현문서 §2.2: src=품질층 노드, dst=공정층 노드 id).
    """
    s, d = graph.get(src), (dst_graph or graph).get(dst)
    if not s or not d:
        return None
    verdict, _ = judge(s["category"], rel, d["category"], cfg, path)

    if verdict == COMMIT:
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

    log_reject(rel, s["category"], d["category"], verdict, path, doc_id)
    return verdict
