# -*- coding: utf-8 -*-
"""골격 심기 — seed의 중첩·순서를 관계로 파생한다 (문서 7 §7.1 「골격 심기 모듈의 자리」).

    seed의 중첩       → child 관계   (구조 — 공장·제품·세대 무관한 주소 체계)
    자식 배열 순서    → sibling 관계 (지식 — 대표 흐름 한 벌)

**자리가 지정돼야 하는 이유**: 파생이 loader·인입 코드에 흩어지면 **관계 이름을
config에서 받는 통로가 지점마다 갈리고**, 층 어휘 0(문서 1 A/B1)이 조용히 깨진다.
파생 규칙의 규범 소유는 문서 3 §3.9-⑴/⑵이고, **여기 코드는 관계 이름을 가정하지
않는다** — `child`·`sibling`이라는 역할만 알고 실제 이름은 config가 준다.

코드가 아는 것은 **구문 마커 4종**뿐이다 — `::` 접두 · `@split` · `@unordered` ·
`@noflow`. 축의 값(cathode·anode 등)은 코드에 없고 seed의 `AXIS_LABELS` 키에서 읽는다.

`bootstrap.py`는 config 로딩·적재·등록부 갱신만 남는다.
"""
from __future__ import annotations

from . import store
from .ids import norm
from .naming import POLARITY_NONE


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

SEED_STATUS = "seed"        # 사람이 파일로 심은 것 (용어 대장 status 어휘)
SEED_PROV = ["seed"]
MARK_SPLIT = "@split"           # 전 축값 전개 (개념 + 인스턴스 N)
MARK_UNORDERED = "@unordered"   # 순서 비참여 래퍼 (개별)
MARK_NOFLOW = "@noflow"         # 그 부모 아래 전체 무주장 (배열 첫 요소)
MARK_PREFIX = "@"               # 축약형 마커의 접두 — `@{축값}` = 단극성
TIER_BY_DEPTH = {1: "main", 2: "sub"}
TIER_DEEP = "detail"
KEY_TREE = "TREE"
KEY_LABELS = "AXIS_LABELS"
KEY_ALIASES = "ALIASES"


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
    # `attrs`는 attr_name별 **값 항목의 리스트**를 담는 컨테이너다(문서 7 §7.2 저장
    # 레코드 스키마). null 스칼라를 키로 실으면 형태 위반이고, 실제로 `show node`가
    # 100노드 중 50개에서 죽었다. `process_no`는 role=meta라(schemas/blocks.json)
    # 애초에 attrs에 있을 자리가 아니다 — 출처 장부에만 남는다.
    nid = g.add_node(canonical, category, SEED_STATUS,
                     provenance=SEED_PROV, **fields)
    register(canonical, nid)
    return nid


# ---------------------------------------------------------------- 모양 디스패치
TYPE_TREE = "tree-v3.2"      # seed 형식 판번호가 값에 붙는다 (config가 선언)
TYPE_FLAT = "flat"


def plant(g, seed, skel, cfg, register):
    """골격 모양에 따라 심는다 — **모양의 분기도 파생 모듈의 일이다**.

    `bootstrap`에 남기면 "어느 모양을 어떻게 파생하나"가 loader에 섞여, 새 모양을
    더할 때 config 통로가 아니라 loader를 고치게 된다(§7.1 골격 심기 모듈의 자리).

    돌려주는 것: `(ids, parsed, pairs, flow_lines)`.
    `parsed`·`pairs`는 tree 전용이고 flat에서는 None·[]이다.
    """
    kind = skel.get("type")
    if kind == TYPE_TREE:
        ids, parsed, pairs = _plant_tree(g, seed, skel, cfg, register)
        return ids, parsed, pairs, [ln for ln in parsed.flow_lines if ln]
    if kind == TYPE_FLAT:                        # 관계 없는 골격 목록
        ids = {item: _plant(g, item, skel["category"], register,
                            tier=TIER_BY_DEPTH[1], polarity=POLARITY_NONE)
               for item in seed["data"]}
        return ids, None, [], []
    raise SeedError(f"골격 모양을 알 수 없다: {kind!r}")
