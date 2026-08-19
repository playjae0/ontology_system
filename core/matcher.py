# -*- coding: utf-8 -*-
"""개체 판정 — "그것이 기존의 무엇인가" (CH3A 3.3).

    표면형 → ①사전 조회 → (미스) ②후보 검색 → ③LLM 동일성 판정 → 3분기

3분기 (규약 1):
    매칭(≥0.85)  → 기존 노드에 alias 자동 누적
    신규         → 자동 생성 (status=auto + provenance + auto_node 큐)
    불확실       → **신규로 생성** + uncertain_match 큐

불확실을 신규로 보내는 것은 비대칭 설계다 — **병합은 쉽고 분리는 어렵기 때문**이다
(I3가 "자동 불가"인 것과 같은 이유). 잘못 합치면 사람이 배분표를 써야 하지만,
잘못 나누면 병합 도구가 자동으로 되돌린다.

USE_MOCK=1에서는 ③이 문자열 정규화 규칙이다(구현문서 §8) — 네트워크·키 없이
전 루프가 돌아야 하기 때문이며, 실물 LLM 경로와 **분기점이 같다**.
"""
from __future__ import annotations

import os

from .ids import norm
from .naming import POLARITY_NONE
from .ops import is_live

THRESHOLD = 0.85        # 단일 임계. 세분화는 판정 보류율이 쌓인 뒤에만(P7·E2).

MATCH = "match"
NEW = "new"
UNCERTAIN = "uncertain"


def _use_mock():
    return os.environ.get("USE_MOCK", "1") == "1"


def _similarity(a, b):
    """USE_MOCK 판정 규칙 — 공백 제거 후 동일/포함이면 0.95 (구현문서 §8).

    "노칭정밀도"와 "노칭 정밀도"는 표기 차이라 붙어야 하고,
    "cathode 노칭 프레스"와 "anode 노칭 프레스"는 다른 실물이라 붙으면 안 된다.
    후자는 표면형 자체가 다르므로 이 규칙으로도 갈린다.
    """
    x, y = norm(a).replace(" ", ""), norm(b).replace(" ", "")
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    if x in y or y in x:
        return 0.95
    return 0.0


def _pol(value):
    """polarity 필드의 정규형. 필드가 없는 노드는 `none`으로 읽는다(닫힌 4값)."""
    return value or POLARITY_NONE


def resolve(surface, category, layer, graph, dictionary, *, scoped=True,
            polarity=None):
    """표면형 하나를 판정해 (분기, node_id 또는 None, 점수)를 돌려준다.

    `scoped=False`는 부모 미해소 Property다 — **스코프 노드와 병합을 금지**한다
    (CH3B 3.5 규약 5). 좌표를 모른 채 만든 노드를 유사도로 합치면 오병합이다.

    `polarity`는 그 표면형에서 파생한 **닫힌 4값**이다(A11-8 — cathode/anode/
    none/unbound). **극성이 다르면 감점이 아니라 후보에서 제외한다**(D-40) —
    "cathode 노칭 프레스"와 "anode 노칭 프레스"는 표기 차이가 아니라 다른 실물이고
    다른 규격을 갖는다(CH3A 3.3 경계). 문자열 포함 규칙에 맡기면 극성 노드가
    무극성 노드에 흡수되므로, 이것은 휴리스틱이 아니라 정체성 규칙으로 건다.

    **판정 근거는 canonical 문자열이 아니라 `polarity` 필드다**(A11-8 — M2 재대조
    종결 조건). 이름이 어떻게 조립됐는지는 여기서 보지 않는다.
    """
    want = _pol(polarity)
    # ① 사전 조회 — 결정적·무LLM. 층 간 표면형 충돌은 허용하고 여기서 선별한다.
    for nid in dictionary.get(norm(surface), []):
        n = graph.get(nid)
        if n and n["category"] == category and n["layer"] == layer \
                and _pol(n.get("polarity")) == want:
            return MATCH, nid, 1.0

    # ② 후보 검색 + ③ 판정
    best, score = None, 0.0
    for nid, n in graph.nodes.items():
        if not is_live(n):
            continue                                     # 툼스톤은 후보가 아니다(D-66 6번째 지점)
        if n["category"] != category or n["layer"] != layer:
            continue                                     # 카테고리 불일치 안전망(규약 3)
        if not scoped and n.get("_scoped"):
            continue                                     # 부모 미해소 ↔ 스코프 노드 금지
        if _pol(n.get("polarity")) != want:
            continue                                     # 극성이 다르면 다른 실물이다
        # canonical에는 포함 규칙까지 적용하지만(표기 변형 흡수 — "노칭정밀도" ↔
        # "노칭::노칭 정밀도"), **alias에는 정확 일치만** 적용한다.
        # alias는 조립 전 표면형이라("노칭 프레스"), 포함 규칙을 걸면
        # "cathode 노칭 프레스"가 무극성 노드에 흡수된다 — 다른 실물이 한 노드가 되는 사고다.
        scores = [_similarity(surface, n["canonical"])]
        scores += [1.0 for a in n["aliases"]
                   if norm(a["surface"]) == norm(surface)]
        s = max(scores)
        if s > score:
            best, score = nid, s

    if score >= 1.0:
        return MATCH, best, score
    if score >= THRESHOLD:
        return MATCH, best, score
    if score > 0.0:
        # 임계 아래인데 0은 아닌 구간 — 확신이 없으므로 신규로 만들고 표시한다.
        return UNCERTAIN, None, score
    return NEW, None, 0.0
