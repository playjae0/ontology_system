# -*- coding: utf-8 -*-
"""n10 — 부트스트랩 seed·config (G2, 기존 1b 흡수). **seed 형식 v3.2**(D-42).

시스템 최초 가동 = **공정정보층 1개 내장**. 이 층은 R1 층 등록 절차를 거치지
않은 **내장 층**이며(카드 J10), 그 지위가 registry에 `builtin`으로 명문화된다.
품질지식층은 여기서 내장하지 않는다 — G4의 3′이 신규 층 등록 절차의 첫
검증 대상으로 추가한다. 그것이 절차 자체의 검증이기 때문이다.

**골격의 두 축**(틀 §4B-A11 · 카드 J12):
    part_of  = 구조 — 공장·제품·세대 무관 분해. 주소 체계다.
    precedes = 지식 — "대표 흐름" 한 벌. **자식 배열의 순서가 곧 선언**이며,
               비참여 3종(`::`인스턴스 자동 · `@unordered` 개별 · `@noflow` 레벨
               전체)은 건너뛰고 잇는다. 비참여 = 무주장(병렬 단정도 순차 단정도 아님).

**코드에 층 어휘 0**(B1) — 공정·노칭·스태킹은 물론 **극성 값(cathode/anode)도
이 파일에 없다.** 코드가 아는 것은 **구문 마커 4종**(`::` 접두 · `@split` ·
`@unordered` · `@noflow`)뿐이고, 축의 값은 seed의 `AXIS_LABELS` **키에서
읽는다**. 그래서 판정문의 "마커 닫힌 7종"이 코드에서는 "구문 4종 + 데이터에서 온
값 N개"로 구현된다 — 어휘 밖 마커는 명시적 실패다. 골격의 모양·카테고리·관계·
소재는 전부 `layers/<layer>/config.json`이 값으로 선언한다.

**로드 시 파생 대표 흐름을 출력한다**(A11-2 · §4 완화 3겹의 ②). 비참여 표시
누락으로 생긴 거짓 순서는 구문으로 막을 수 없고, 나열로 보면 즉시 보인다 —
이 출력이 순서 오선언의 유일한 안전망이다(M9 결과 뷰 계보).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import store
from .dictionary import Dictionary
from .graph import GraphStore
from .ids import norm
from .naming import POLARITY_NONE
from .skeleton import (KEY_ALIASES, KEY_LABELS, KEY_TREE, SEED_PROV,
                       SEED_STATUS, SeedError, _pad, _register_aliases, plant)

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT / "layers"


# ---- seed 문법: 코드가 아는 전부 -------------------------------------------
# 구문 마커 4종. 축의 **값**은 여기에 없다 — AXIS_LABELS 키에서 읽는다(B1).

# tier는 틀 §4B-A11-7이 전 층 공통으로 고정한 3단 어휘다(층 어휘가 아니다).

# seed 형식 v3.2의 블록 이름 — 전부 **축·층 중립**이다(B1).
# 구 `PROCESS_TREE`·`POLARITY_LABELS`는 형식이 특정 층·특정 축의 이름을 달고 있어
# 로더에 층 어휘가 새던 지점이라 `TREE`·`AXIS_LABELS`로 개명했다. 상수로 격리하는
# 것은 위반을 유지한 채 숨기는 것이고, seed 실물 1개·의존 코드 1곳인 지금이 가장
# 싼 시점이다. 노드 필드 `polarity`와 config의 `polarity` 블록은 그대로 둔다 —
# 그쪽은 A11-8이 정한 시스템 어휘이자 B1의 명시된 예외이며, 해소 경로는
# identity_axis 일반화로 이연되어 있다.



def load_config(layer):
    return json.loads((LAYERS / layer / "config.json").read_text(encoding="utf-8"))


def layer_of_category(category):
    """그 카테고리를 **선언한 층**을 찾는다.

    품질층 문서의 `process_ref`가 공정층 골격을 가리키는 것이 대표 사례다 —
    걸침 필드는 다른 층 그래프에 기록된다(명세 §15.7 규칙 A).
    어느 층이 무엇을 선언했는지는 config가 알고 있으므로 코드는 층 이름을 모른다(B1).
    """
    from router import discover
    for lay in discover():
        if category in load_config(lay).get("categories", {}):
            return lay
    return None


def open_graph(layer):
    """층 그래프를 연다. 경로 조립은 GraphStore가 소유한다 — 여기서 하지 않는다."""
    return GraphStore.for_layer(layer).load()


# ---------------------------------------------------------------- seed 적재
def load_seed(layer, skel):
    """골격 데이터의 **소재도 config가 값으로 가리킨다**(D-42 — 단일 파일 seed).

    config에 `source`가 있으면 그 파일이 골격이고, 없으면 선언 자체가 골격이다
    (관계 없는 flat 목록). 코드는 둘을 구별할 뿐 어느 층이 어느 쪽인지 모른다.
    """
    src = skel.get("source")
    if not src:
        return skel
    return json.loads((LAYERS / layer / src).read_text(encoding="utf-8"))


def _stale_skeleton(g, category, planted):
    """이번 seed에 없는 옛 골격 노드 — canonical 체계가 바뀌면 잔존한다.

    v3.2는 canonical 체계 자체를 바꿨다(부모 경로 접두 · `{개념}::{축값}`).
    멱등성(D-41)은 "같은 canonical의 재발급"을 막을 뿐 **체계 변경**은 막지 못한다 —
    기존 그래프 위에 그냥 돌리면 옛 골격이 살아남아 기대값이 어긋난다. 조용히
    지우지 않는다(P4 id 불변 · 엣지 보존) — 드러내고 사람이 판정한다(G5).
    """
    return sorted(n["canonical"] for n in g.nodes.values()
                  if n["status"] == SEED_STATUS and n["category"] == category
                  and n["id"] not in planted)


# ---------------------------------------------------------------- 진입점
def write_closed_list(layer, g, cfg, seed=None):
    """골격 닫힌 목록 스냅샷 — **파서·에이전트의 공유 자산**이다 (D-11 확정).

    파서는 이 레포의 그래프를 읽지 않는다(별도 프로그램 · 결합은 JSON뿐 — D-9).
    좌표 태깅이 고를 닫힌 목록을 파일 하나로 내보내야 둘이 **같은 실물**을 본다.

    목록 = **골격 전 노드**(개념 + 인스턴스)이며 canonical과 alias를 함께 싣는다
    (A11-6 · D-45 — 구 "세부공정 목록" 서술은 폐기됐다). 층 config의
    `skeleton_version`(골격 판번호)과 seed 파일의 `seed_format`(seed **문법**
    판번호)을 함께 적어 표류를 대조할 수 있게 한다 — **둘은 다른 것이고 같은
    낱말을 쓰면 안 된다**: 하나는 "이 골격이 몇 판인가", 다른 하나는 "이 파일을
    어느 문법으로 읽어야 하나"다.

    **파생물이다**(P5) — 골격을 재빌드하면 loader가 다시 만든다. 손으로 고치지 않는다.
    """
    # 구조 부모를 함께 싣는다 — 태거가 `process_group`(tier:main 조상 — A11-7)을
    # 파생하려면 부모 링크가 필요하고, 파서는 그래프를 읽지 않는다(D-9).
    child_rel = ((cfg.get("skeleton") or {}).get("relations") or {}).get("child")
    parent_of = {e["src"]: e["dst"] for e in g.edges
                 if e["rel"] == child_rel and e.get("status") == "seed"}
    entries = []
    for n in g.nodes.values():
        if n.get("status") != "seed":
            continue
        up = g.get(parent_of.get(n["id"]))
        entries.append({
            "id": n["id"], "canonical": n["canonical"], "category": n["category"],
            "tier": n.get("tier"),
            "polarity": n.get("polarity"),
            "parent": up["canonical"] if up else None,
            "aliases": sorted(a["surface"] for a in n["aliases"]),
        })
    entries.sort(key=lambda e: e["canonical"])
    snap = store.read(store.SKELETON_LIST, {})
    snap[layer] = {
        "skeleton_version": cfg.get("skeleton_version"),
        "seed_version": (seed or {}).get("seed_format"),
        "category": (cfg.get("skeleton") or {}).get("category"),
        "count": len(entries),
        "nodes": entries,
    }
    store.write(store.SKELETON_LIST, snap)
    return snap[layer]


def bootstrap(layer="process", echo=True):
    """골격을 심고 사전에 등재한 뒤 registry에 층을 올린다.

    골격의 **모양**(tree-v3.2 | flat)도 **등록 지위**(builtin | registered)도
    config가 값으로 선언한다 — 코드가 층 이름으로 가르면 그 자체가 층 어휘다(B1).
    골격을 선언하지 않은 층은 심을 것이 없으므로 건너뛴다.

    돌려주는 것은 `(graph, metrics, ids, flow_lines)`다. `flow_lines`는 파생 대표
    흐름 보고이며 `echo=True`면 로드 시 함께 출력한다(A11-2 안전망).
    """
    cfg = load_config(layer)
    skel = cfg.get("skeleton")
    if not skel:
        return None, None, {}, []

    g = GraphStore.for_layer(layer).load()
    g.build_begin()

    dictionary = Dictionary.open()          # 사전 접근은 관문 경유로만 (문서 7 §7.1)

    def register(surface, nid):
        """사전 등재는 관문이 한다 — 키 규칙과 provenance 필수가 그쪽에 있다.

        alias 항목은 **노드 레코드**에 산다(§7.2) — 사전이 아니라 그래프의 일이라
        여기서 붙인다. 두 일을 한 모듈에 합치면 사전이 그래프를 쓰게 된다.
        """
        key = dictionary.register(surface, nid, provenance=SEED_PROV[0])
        n = g.get(nid)
        if key != norm(n["canonical"]) and \
                not any(a["surface"] == surface for a in n["aliases"]):
            n["aliases"].append({"surface": surface, "provenance": list(SEED_PROV)})

    seed = load_seed(layer, skel)
    flow_lines, parsed, pairs = [], None, []

    ids, parsed, pairs, flow_lines = plant(g, seed, skel, cfg, register)

    stale = _stale_skeleton(g, skel["category"], set(ids.values()))
    if stale:
        msg = (f"{layer}: 이번 seed에 없는 옛 골격 노드 {len(stale)}건이 남아 있다 "
               f"— 깨끗한 재빌드가 필요하다 {stale}")
        store.append_defect(msg)

    metrics = g.build_end()
    dictionary.save()
    write_closed_list(layer, g, cfg, seed)

    reg = store.read(store.REGISTRY, {})
    reg[layer] = {
        "layer": layer,
        # 내장(R1 절차 불경유)인지 등록된 층인지는 **config가 값으로 선언**한다(J10·D-8).
        # 코드가 층 이름으로 가르면 그 자체가 층 어휘다.
        "status": cfg.get("registration", "registered"),
        "skeleton_version": cfg.get("skeleton_version"),
        "seed_version": seed.get("seed_format"),
        "categories": list(cfg["categories"]),
        "relations": cfg["relations"],
    }
    store.write(store.REGISTRY, reg)

    if echo and (flow_lines or stale):
        print(f"[n10] {layer} — 파생 대표 흐름 (seed 선언의 사람 대조용)")
        for line in flow_lines:
            print(line)
        if parsed is not None:
            print(f"  (순서 비참여: 인스턴스 {parsed.instance_count}종 "
                  f"— 축값 간 순서 무주장 · mirrors 쌍 {len(pairs)})")
            if parsed.ambiguous:
                print(f"  (짧은 이름 모호 — 사전 미등재, 접두 키로만 조회: "
                      f"{parsed.ambiguous})")
        if stale:
            print(f"  ⚠ 옛 골격 노드 {len(stale)}건 잔존: {stale}")
    return g, metrics, ids, flow_lines
