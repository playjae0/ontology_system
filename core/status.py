# -*- coding: utf-8 -*-
"""노드 **생존 판정**과 툼스톤 체인 — 어느 층·어느 연산에도 속하지 않는 잎 모듈 (문서 4 §4.7).

`core/ops.py`에서 떼어냈다. `is_live` 한 줄을 가져가려고 I축 연산 전체(ops)를 import하던
곳이 8곳이었고, 그 때문에 ops가 build를 최상단에서 import하지 못해 순환 3개가 함수 안
지연 import로 숨어 있었다(구조 진단 2026-08-27 · 1순위). 여기는 `store`만 의존한다.

**바뀌지 않은 것**: 판정 규칙(`merged_into` 툼스톤 + `status: obsolete` 둘 다 제외) ·
체인 추적의 방문집합 + 깊이 제한 · 결함 로그 문안. `core.ops`는 같은 이름을 재수출한다.
"""
from __future__ import annotations

from . import store

# 읽기 추적의 최대 깊이 — 조절점(코드 상수, 초과는 결함 로그. L8).
MAX_CHAIN = 16

STATUS_MERGED = "merged_into"
STATUS_OBSOLETE = "obsolete"


def is_live(node):
    """**매칭 후보 판정** — `merged_into` 툼스톤과 `status: obsolete`를 **둘 다** 제외한다.

    생존 판정은 두 갈래다(문서 4 §4.7). 이것은 그중 **매칭 후보** 쪽이고, 사전
    조회·후보 검색·anchor 조회 전부에 적용되며 **I4 이유 ②(재인입 부활 차단)의
    강제 지점**이다. `merged_into`만 보면 폐기 노드가 후보로 돌아와 부활 차단이
    사전에서 새어 나간다.

    연산 대상 판정(I축이 "이 노드를 만질 수 있나"를 묻는 쪽)은 `_target`이 갖는다 —
    폐기 노드도 연산 대상일 수 있으므로 그쪽은 다른 갈래다.

    **툼스톤은 `canonical`을 그대로 지닌다** — 옛 이름을 화면에 보여 주기 위해서다.
    그래서 canonical로 노드를 찾는 코드는 반드시 이 판정을 거쳐야 한다. 안 거치면
    옛 이름이 산 노드를 가리는 사고가 난다(실측: 병합 툼스톤을 폐기 처리해 한 노드가
    `merged_into`와 `obsolete`를 동시에 갖는 모순 상태가 됐다).
    """
    return (bool(node) and node.get(STATUS_MERGED) is None
            and node.get("status") != STATUS_OBSOLETE)


def resolve_chain(graph, nid, field, depth=0, seen=None):
    """툼스톤 체인 추적 — **방문집합 + 깊이 제한**, 초과는 결함 로그(L8 읽기 측).

    조용히 멈추지 않는다. 순환은 쓰기에서 이미 막지만, 읽기 측 방어를 함께 두는 것은
    데이터가 다른 경로로 오염됐을 때 질의가 무한히 도는 것을 막기 위해서다.
    """
    seen = seen or set()
    cur = nid
    while True:
        n = graph.get(cur)
        if n is None or n.get(field) in (None, ""):
            return cur
        if cur in seen:
            store.append_defect(f"ops: {field} 체인 순환 — {cur}")
            return cur
        seen.add(cur)
        if len(seen) > MAX_CHAIN:
            store.append_defect(f"ops: {field} 체인 깊이 {MAX_CHAIN} 초과 — {nid}")
            return cur
        cur = n[field]
