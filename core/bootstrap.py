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
from .graph import GraphStore
from .ids import norm
from .naming import POLARITY_NONE

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT / "layers"

SEED_STATUS = "seed"        # 사람이 파일로 심은 것 (용어 대장 status 어휘)
SEED_PROV = ["seed"]

# ---- seed 문법: 코드가 아는 전부 -------------------------------------------
# 구문 마커 4종. 축의 **값**은 여기에 없다 — AXIS_LABELS 키에서 읽는다(B1).
MARK_SPLIT = "@split"           # 전 축값 전개 (개념 + 인스턴스 N)
MARK_UNORDERED = "@unordered"   # 순서 비참여 래퍼 (개별)
MARK_NOFLOW = "@noflow"         # 그 부모 아래 전체 무주장 (배열 첫 요소)
MARK_PREFIX = "@"               # 축약형 마커의 접두 — `@{축값}` = 단극성

# tier는 틀 §4B-A11-7이 전 층 공통으로 고정한 3단 어휘다(층 어휘가 아니다).
TIER_BY_DEPTH = {1: "main", 2: "sub"}
TIER_DEEP = "detail"

# seed 형식 v3.2의 블록 이름 — 전부 **축·층 중립**이다(B1).
# 구 `PROCESS_TREE`·`POLARITY_LABELS`는 형식이 특정 층·특정 축의 이름을 달고 있어
# 로더에 층 어휘가 새던 지점이라 `TREE`·`AXIS_LABELS`로 개명했다. 상수로 격리하는
# 것은 위반을 유지한 채 숨기는 것이고, seed 실물 1개·의존 코드 1곳인 지금이 가장
# 싼 시점이다. 노드 필드 `polarity`와 config의 `polarity` 블록은 그대로 둔다 —
# 그쪽은 A11-8이 정한 시스템 어휘이자 B1의 명시된 예외이며, 해소 경로는
# identity_axis 일반화로 이연되어 있다.
KEY_TREE = "TREE"
KEY_LABELS = "AXIS_LABELS"
KEY_ALIASES = "ALIASES"

TYPE_TREE = "tree-v3.2"
TYPE_FLAT = "flat"


def _pad(text, width):
    """터미널 정렬용 — 한글은 한 글자가 두 칸이다. 보고서는 눈으로 읽는 물건이라
    이게 어긋나면 흐름 나열이 어긋나 보이고, 그러면 안전망이 안전망 노릇을 못 한다."""
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - w)


class SeedError(ValueError):
    """seed 문법·어휘 위반 = **명시적 실패**(§4 검증표).

    추측으로 메우면 틀린 골격이 조용히 심긴다. 골격은 전 층의 주소 체계이므로
    그 오류는 이후 전 판정을 오염시킨다 — 여기서 멈추는 것이 가장 싸다.
    """


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


# ---------------------------------------------------------------- 트리 파싱
class _Spec:
    """심기 전의 노드 사양. 파싱과 적재를 가르면 검증이 그래프를 더럽히지 않는다."""

    __slots__ = ("name", "canonical", "tier", "polarity", "parent", "instance")

    def __init__(self, name, canonical, tier, polarity, parent, instance):
        self.name = name                # 짧은 이름 (auto alias·출력용)
        self.canonical = canonical      # 층 내 유일한 이름
        self.tier = tier                # main | sub | detail
        self.polarity = polarity        # 축값 | none
        self.parent = parent            # 부모 _Spec (루트는 None)
        self.instance = instance        # 축 인스턴스인가


class _TreeParser:
    """seed 트리 → (노드 사양 목록 · 흐름 체인 · 파생 흐름 보고).

    파생 규칙은 M2 판정문 §4의 표가 정본이다:
      tier      깊이 1=main·2=sub·3+=detail. **인스턴스는 깊이 계수에서 빠지고
                자기 개념의 tier를 상속**한다.
      parent    중첩 그대로. 인스턴스의 부모 = 그 개념 노드.
      polarity  마커에서만 파생. 없으면 none.
      canonical main/sub는 이름 그대로, sub 이하는 **부모 경로 균일 접두**.
                인스턴스는 `{개념}::{축값}` — **쌍 유무와 무관하게 균일**하다
                (반대 극성이 나중에 판명돼도 기존 노드가 개명되지 않는다).
    """

    def __init__(self, labels, sep):
        self.labels = labels            # {축값: 표시 라벨} — seed 데이터
        self.sep = sep
        self.specs: list[_Spec] = []
        self.chains: list[tuple[_Spec, _Spec]] = []     # (앞, 뒤) — precedes
        self.flow_lines: list[str] = []                 # 사람이 읽는 파생 흐름
        self.instance_count = 0
        self.ambiguous: list[str] = []                  # 사전 미등재 짧은 이름

    # -- 진입점
    def parse(self, tree):
        self._level(tree, None, 1)
        self._check_name_collision()
        return self

    # -- 한 레벨(자식 배열) 처리
    def _level(self, items, parent, depth):
        if not isinstance(items, list):
            raise SeedError(f"자식은 배열이어야 한다 — {parent.canonical if parent else '루트'}")
        body = list(items)
        noflow = bool(body) and body[0] == MARK_NOFLOW
        if noflow:
            body = body[1:]
        # 자식보다 **먼저** 출력 자리를 잡는다 — 보고서는 위에서 아래로 읽혀야 한다.
        slot = len(self.flow_lines)
        self.flow_lines.append(None)
        flow, unassert = [], []
        for item in body:
            spec, participates = self._item(item, parent, depth)
            if spec is None:
                continue
            if participates and not noflow:
                flow.append(spec)
            elif not spec.instance:                 # 인스턴스는 전역 요약으로 따로 센다
                unassert.append(spec)
        for a, b in zip(flow, flow[1:]):            # 참여 항목만 건너 잇는다
            self.chains.append((a, b))
        self.flow_lines[slot] = self._report(parent, flow, unassert, noflow)

    # -- 항목 하나 → (사양, 흐름 참여 여부)
    def _item(self, item, parent, depth, wrapped=False):
        if isinstance(item, str):
            return self._str_item(item, parent, depth, wrapped)
        if isinstance(item, dict):
            return self._dict_item(item, parent, depth, wrapped)
        raise SeedError(f"항목의 형태를 알 수 없다: {item!r}")

    def _str_item(self, item, parent, depth, wrapped):
        if item.startswith(self.sep):                       # `::{축값}` — 주소 인스턴스
            value = item[len(self.sep):]
            if value not in self.labels:
                raise SeedError(f"마커 어휘 밖: '{item}' — 축값은 {list(self.labels)}뿐이다")
            if wrapped:
                raise SeedError(
                    f"{MARK_UNORDERED}를 인스턴스에 붙일 수 없다: '{item}' "
                    "— 인스턴스는 이미 순서 비참여다")
            if parent is None:
                raise SeedError(f"인스턴스에 개념 노드가 없다: '{item}'")
            self._instance(parent, value)
            return None, False
        if item.startswith(MARK_PREFIX):
            raise SeedError(f"마커 어휘 밖: '{item}'")
        return self._concept(item, parent, depth), True

    def _dict_item(self, item, parent, depth, wrapped):
        if len(item) != 1:
            raise SeedError(f"항목 객체는 키 1개여야 한다: {item!r}")
        (key, value), = item.items()
        if key == MARK_UNORDERED:                           # 순서 비참여 래퍼
            spec, _ = self._item(value, parent, depth, wrapped=True)
            return spec, False
        if isinstance(value, list):                         # 중간 노드
            spec = self._concept(key, parent, depth)
            self._level(value, spec, depth + 1)
            return spec, True
        if isinstance(value, str) and value.startswith(MARK_PREFIX):
            spec = self._concept(key, parent, depth)        # 개념은 참여
            if value == MARK_SPLIT:
                for v in self.labels:                       # 전 축값 전개
                    self._instance(spec, v)
            elif value[len(MARK_PREFIX):] in self.labels:   # 단극성 = 개념 + 인스턴스 1
                self._instance(spec, value[len(MARK_PREFIX):])
            else:
                raise SeedError(f"마커 어휘 밖: '{value}' ('{key}')")
            return spec, True
        raise SeedError(f"항목 값의 형태를 알 수 없다: {key} → {value!r}")

    # -- 노드 사양 생성
    def _concept(self, name, parent, depth):
        if name in self.labels:
            raise SeedError(
                f"축값을 공정 이름으로 쓸 수 없다: '{name}' — 리스트 표기(['{name}'])는 금지다")
        tier = TIER_BY_DEPTH.get(depth, TIER_DEEP)
        canonical = name if tier != TIER_DEEP else f"{parent.canonical}{self.sep}{name}"
        spec = _Spec(name, canonical, tier, POLARITY_NONE, parent, False)
        self.specs.append(spec)
        return spec

    def _instance(self, concept, value):
        """인스턴스는 개념의 tier를 상속하고 깊이 계수에 들어가지 않는다(A11-7)."""
        spec = _Spec(concept.name, f"{concept.canonical}{self.sep}{value}",
                     concept.tier, value, concept, True)
        self.specs.append(spec)
        self.instance_count += 1
        return spec

    # -- 검증: main·sub 이름 충돌
    def _check_name_collision(self):
        """main·sub는 canonical이 짧은 이름 그대로라 충돌하면 두 개념이 한 노드가 된다."""
        seen = {}
        for s in self.specs:
            if s.instance or s.tier == TIER_DEEP:
                continue
            if s.canonical in seen:
                raise SeedError(f"main·sub 이름 충돌: '{s.canonical}'")
            seen[s.canonical] = s

    # -- 파생 흐름 보고 (안전망)
    def _report(self, parent, flow, unassert, noflow):
        """선언할 순서가 없는 레벨(참여 1개 이하 · 무주장 없음)은 적지 않는다."""
        if len(flow) < 2 and not unassert:
            return None
        head = f"[{parent.name if parent else '(루트)'}]"
        body = " → ".join(s.name for s in flow) if flow else "(순서 무주장)"
        line = f"  {_pad(head, 12)} {body}"
        tail = []
        if noflow:
            tail.append(f"{MARK_NOFLOW} — 이 레벨 전체 무주장")
        if unassert:
            tail.append("무주장: " + ", ".join(s.name for s in unassert))
        if tail:
            line += "          (" + " / ".join(tail) + ")"
        return line


# ---------------------------------------------------------------- 적재
def _plant_tree(g, seed, skel, cfg, register):
    """파싱 → 검증 → 적재. 검증이 끝난 뒤에만 그래프를 건드린다."""
    labels = seed.get(KEY_LABELS) or {}
    sep = (cfg.get("canonical_scope") or {}).get("sep", "::")   # 구분자 `::` 통일(M2)
    tree = seed.get(KEY_TREE)
    if tree is None:
        raise SeedError(f"seed에 트리 블록({KEY_TREE})이 없다")

    parsed = _TreeParser(labels, sep).parse(tree)
    category = skel["category"]
    child_rel = skel["relations"]["child"]       # 자식 → 부모 (구조)
    sib_rel = skel["relations"]["sibling"]       # 앞 → 뒤 (대표 흐름)

    ids = {}
    for s in parsed.specs:
        ids[s.canonical] = _plant(g, s.canonical, category, register,
                                  tier=s.tier, polarity=s.polarity)
    for s in parsed.specs:                       # ① 구조
        if s.parent is not None:
            g.add_edge(ids[s.canonical], child_rel, ids[s.parent.canonical],
                       SEED_STATUS, SEED_PROV)
    for a, b in parsed.chains:                   # ② 대표 흐름
        g.add_edge(ids[a.canonical], sib_rel, ids[b.canonical],
                   SEED_STATUS, SEED_PROV)

    pairs = _link_seed_mirrors(g, parsed, ids, cfg, labels)
    parsed.ambiguous = _register_aliases(g, seed, parsed, ids, labels, register)
    return ids, parsed, pairs


def _link_seed_mirrors(g, parsed, ids, cfg, labels):
    """축 인스턴스의 mirrors — **polarity 필드 비교**다(F3, 문자열 파싱 폐지).

    같은 개념 아래 축값이 전부 갖춰졌을 때만 잇는다. **Tier1의 단극성 인스턴스는
    mirror_asymmetry 큐에 올리지 않는다**(A11-4) — 사람이 보증한 "짝 없음"이
    의도이기 때문이다. 그 큐는 Tier2의 문서 편측 갱신을 잡는 장치다.
    """
    rel = (cfg.get("mirrors") or {}).get("relation")
    if not rel or not (cfg.get("mirrors") or {}).get("enabled"):
        return []
    by_concept = {}
    for s in parsed.specs:
        if s.instance:
            by_concept.setdefault(s.parent.canonical, {})[s.polarity] = s
    pairs = []
    for group in by_concept.values():
        if len(group) != len(labels):
            continue                              # 단극성 — 큐 없이 넘어간다
        members = list(group.values())
        pairs.append(tuple(sorted(m.canonical for m in members)))
        for a in members:
            for b in members:
                if a is not b:
                    g.add_edge(ids[a.canonical], rel, ids[b.canonical],
                               SEED_STATUS, SEED_PROV)
    return pairs


def _register_aliases(g, seed, parsed, ids, labels, register):
    """seed ALIASES는 **사전이 아니라 원천**이다(D-47).

    장부는 `dictionary.json` 하나뿐이고(카드 B4), loader가 여기에
    `provenance: ["seed"]`로 등재하면 원천의 역할은 끝난다. 운영 축적분(E5)은
    같은 장부에 쌓이며 seed 유래와는 **구역이 아니라 태그로** 구분된다.

    자동 생성 2종:
      · 짧은 이름 — 접두가 붙은 detail 노드의 원래 이름. **층 안에서 유일할 때만**
        등재한다. 모호한 짧은 이름을 등재하면 소비처가 조용히 하나를 고르게 되는데,
        그것이 바로 "임의 선택 금지"가 막는 사고다 — 모호하면 사전에 없는 것이 맞고
        접두 키가 그 자리를 대신한다.
      · 인스턴스 — `{축값} {이름}` · `{라벨} {이름}` (AXIS_LABELS).
    """
    by_canonical = {s.canonical: s for s in parsed.specs}

    short_owners = {}
    for s in parsed.specs:
        if not s.instance:
            short_owners.setdefault(s.name, []).append(s)
    ambiguous = sorted(n for n, owners in short_owners.items() if len(owners) > 1)
    for name, owners in short_owners.items():
        if len(owners) == 1 and owners[0].canonical != name:
            register(name, ids[owners[0].canonical])

    for s in parsed.specs:                       # 인스턴스 auto alias
        if s.instance:
            register(f"{s.polarity} {s.name}", ids[s.canonical])
            register(f"{labels[s.polarity]} {s.name}", ids[s.canonical])

    for key, surfaces in (seed.get(KEY_ALIASES) or {}).items():
        spec = by_canonical.get(key)
        if spec is None:                         # 짧은 키 — 유일할 때만 허용
            owners = short_owners.get(key, [])
            if not owners:
                raise SeedError(f"ALIASES 키가 트리에 없다: '{key}'")
            if len(owners) > 1:
                raise SeedError(
                    f"ALIASES 키가 모호하다: '{key}' — 접두 키를 쓰라 "
                    f"({[o.canonical for o in owners]})")
            spec = owners[0]
        for surface in surfaces:
            register(surface, ids[spec.canonical])
    return ambiguous


def _plant(g, canonical, category, register, **fields):
    """이미 심긴 골격은 **다시 심지 않는다** — 부트스트랩은 멱등해야 한다(D-41).

    의미 축 id는 발급(ULID)이라 다시 심으면 같은 개념에 새 id가 붙어 노드가 배로
    늘고 provenance·엣지가 갈라진다. 노드 유일성(P4) 위반이며 `run.py all` 2회 =
    동일 그래프(§8 전체 완료판정)도 깨진다.

    파생 필드(tier·polarity)는 재사용 시에도 갱신한다 — seed를 고치고 다시 돌리는
    것이 골격 개정의 정상 경로이기 때문이다(id는 그대로 유지된다).
    """
    for nid, n in g.nodes.items():
        if n["canonical"] == canonical and n["category"] == category:
            n.update(fields)
            register(canonical, nid)
            return nid
    nid = g.add_node(canonical, category, SEED_STATUS,
                     attrs={"process_no": None}, provenance=SEED_PROV, **fields)
    register(canonical, nid)
    return nid


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

    dictionary = store.read(store.DICTIONARY, {})

    def register(surface, nid):
        """사전 등재 — 키는 **norm된 표면형**이다(조회부와 같은 규칙이어야 한다)."""
        key = norm(surface)
        dictionary.setdefault(key, [])
        if nid not in dictionary[key]:
            dictionary[key].append(nid)
        n = g.get(nid)
        if key != norm(n["canonical"]) and \
                not any(a["surface"] == surface for a in n["aliases"]):
            n["aliases"].append({"surface": surface, "provenance": list(SEED_PROV)})

    seed = load_seed(layer, skel)
    kind = skel.get("type")
    flow_lines, parsed, pairs = [], None, []

    if kind == TYPE_TREE:
        ids, parsed, pairs = _plant_tree(g, seed, skel, cfg, register)
        flow_lines = [ln for ln in parsed.flow_lines if ln]
    elif kind == TYPE_FLAT:                      # 관계 없는 골격 목록
        ids = {item: _plant(g, item, skel["category"], register,
                            tier=TIER_BY_DEPTH[1], polarity=POLARITY_NONE)
               for item in seed["data"]}
    else:
        raise SeedError(f"골격 모양을 알 수 없다: {kind!r}")

    stale = _stale_skeleton(g, skel["category"], set(ids.values()))
    if stale:
        msg = (f"{layer}: 이번 seed에 없는 옛 골격 노드 {len(stale)}건이 남아 있다 "
               f"— 깨끗한 재빌드가 필요하다 {stale}")
        store.append_defect(msg)

    metrics = g.build_end()
    store.write(store.DICTIONARY, dictionary)

    reg = store.read(store.REGISTRY, {})
    reg[layer] = {
        "layer": layer,
        # 내장(R1 절차 불경유)인지 등록된 층인지는 **config가 값으로 선언**한다(J10·D-8).
        # 코드가 층 이름으로 가르면 그 자체가 층 어휘다.
        "status": cfg.get("registration", "registered"),
        "skeleton_version": cfg.get("skeleton_version"),
        "seed_version": seed.get("skeleton_version"),
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
