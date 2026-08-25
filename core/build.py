# -*- coding: utf-8 -*-
"""1c′·1d′ 구축 — 계약 JSON을 그래프로 (계약 v2 정합).

변경점 닫힌 목록 5항 (증분0 §3 G3):
  ① 조각 공통 `chunk_id` → **`source_locator`**(role=meta)
  ② 봉투 `payload_kind`·`adapter_version` 소비 (에이전트가 청크에 복사)
     — `classification`은 소비 대상이 **아니다**(D-37: 자리만 있고 아무도 읽지 않는다)
  ③ process_group·process_ref 둘 다 anchor이나 **부착은 process_ref 하나**.
     process_group은 해소 후 **골격 조상 대조만** 하고, 어긋나면 `coord_mismatch` 큐(C3)
  ④ `electrode_type`은 블록에 넣지 않고 **구조 필드**로 유지 — 극성 결합은
     role 핸들러가 아니라 entity 해소 코드가 record에서 직접 읽는다(D-1)
  ⑤ 큐 kind 목록 확장 (§6-5, 계 20종)

**코드에 층 어휘 0**(B1) — 카테고리 이름·관계 이름·극성 값이 이 파일에 없다.
전부 `layers/*/config.json`과 `schemas/*.json`이 값으로 준다.
"""
from __future__ import annotations

from . import gate, store
from .dictionary import Dictionary
from .ids import norm
from .matcher import MATCH, NEW, UNCERTAIN, resolve
from .ops import is_live
from .naming import (POLARITY_NONE, bind_polarity, derive_polarity,
                     is_bound, scope_canonical)

ROLE_HANDLERS = ("anchor", "entity", "attribute", "content", "meta")


class Builder:
    def __init__(self, graph, cfg, schema, doc_id, layer):
        self.g = graph
        self.cfg = cfg
        self.schema = schema
        self.doc_id = doc_id
        self.layer = layer
        self.dict = Dictionary.open()      # 사전 접근은 관문 경유로만 (문서 7 §7.1)
        self.buffer: dict[str, str] = {}     # 문서 해소 버퍼 (2-pass Pass 1)
        self.subs: dict[str, "Builder"] = {}  # 걸침 층별 하위 빌더 — 아래 for_layer

    # ---------------------------------------------------------------- 걸침
    def for_layer(self, layer):
        """다른 층에 쓰는 하위 빌더. **층당 하나로 캐시한다.**

        캐시가 없으면 레코드마다 `open_graph`가 새 인스턴스를 물어 와서 **앞 레코드가
        쓴 것이 뒤 레코드에게 보이지 않고**, 어느 것도 저장되지 않는다(외부 그래프
        증발 — R2-9 실측). 사전과 문서 버퍼는 **공유**한다: 장부는 하나이고(B4),
        버퍼는 문서 하나의 것이지 층의 것이 아니다.
        """
        if layer == self.layer:
            return self
        if layer not in self.subs:
            from .bootstrap import load_config, open_graph
            sub = Builder(open_graph(layer), load_config(layer), self.schema,
                          self.doc_id, layer)
            sub.dict = self.dict
            sub.buffer = self.buffer
            sub.subs = self.subs
            self.subs[layer] = sub
        return self.subs[layer]

    def graphs(self):
        """이 빌드가 만진 그래프 전부 — 자기 층 + 걸침 층. 저장 대상이다."""
        return [self.g] + [s.g for s in self.subs.values()]

    # ---------------------------------------------------------------- 사전
    def _register(self, surface, nid, prov):
        """사전 등재는 관문이 한다 — **provenance 필수 강제가 그쪽에 있다**(§7.1).

        alias 항목(`{surface, provenance}`)은 노드 레코드에 살므로(§7.2) 그
        붙이기만 여기 남는다 — 사전이 그래프를 쓰면 저장 계층 경계가 무너진다.
        """
        self.dict.register(surface, nid, provenance=prov)
        n = self.g.get(nid)
        if norm(surface) != norm(n["canonical"]) and \
                not any(a["surface"] == surface for a in n["aliases"]):
            n["aliases"].append({"surface": surface, "provenance": [prov]})

    def flush(self):
        self.dict.save()

    # ---------------------------------------------------------------- anchor
    def _graph_for(self, category):
        """카테고리를 선언한 층의 그래프. 같은 층이면 self.g를 그대로 쓴다."""
        if category in self.cfg.get("categories", {}):
            return self.g, self.layer
        from .bootstrap import layer_of_category
        lay = layer_of_category(category)
        if lay is None or lay == self.layer:
            return self.g, self.layer
        return self.for_layer(lay).g, lay

    def resolve_anchor(self, surface, category, prov, *, defer=None):
        """골격 조회 전용 — anchor는 새로 만들지 않는다.

        돌려주는 것은 **(node_id, 그 노드가 사는 그래프)**다. 걸침 anchor는 다른 층에
        살기 때문에 그래프를 함께 줘야 호출부가 카테고리를 물어볼 수 있다.

        **조회 대상은 사전(정확 일치·alias)까지다** — 문서 2 §2.4-①: "미스면 곧바로
        orphan_anchor 큐. **anchor 해소에는 후보검색·유사도·LLM 판정을 쓰지 않는다**
        — 골격은 사람이 고정한 유형이고(P2), 추론으로 끌어당기면 사람의 보증을
        코드가 뒤집는다." 표기 변형은 사전의 alias가 흡수하고, 사전에 없으면 큐에서
        사람이 판단한다. 좌표 닫힌 목록 = 골격 전 노드이며
        (A11-6), 개념 노드와 인스턴스가 둘 다 그 목록에 있다. 문서가 상위·개념
        해상도로 말하면("탭용접") 개념 노드가 답이고, 그것은 오류가 아니라
        **저해상도 부착**이다.

        **극성 모호(구 D5)는 구조적으로 소멸했다**(A11-6): 극성 무관 표면형의 alias는
        개념 노드가 단독 소유하고, 극성 수식 표기는 인스턴스의 auto alias다. 남는
        orphan_anchor 경로는 **"목록 밖 이름"**과 **"표기 모호"** 둘뿐이며, 후자에서도
        임의 선택하지 않는다 — 쓰기는 좁게(3.5 규약 7).

        **적재는 즉시 하지 않고 `defer`에 미룬다**(문서 2 §2.4-① · 문서 4 §4.7-5).
        큐 항목이 재시도 배치의 **유일한 손잡이**인데, 좌표를 못 찾은 시점에는 그
        행이 무엇을 만들었는지가 아직 정해지지 않았다 — 생략된 엣지의 출발 노드도,
        연쇄 드롭된 걸침 entity도, 보류된 attribute도 레코드 처리가 끝나야 안다.
        즉시 적재하면 그것들이 payload 밖에 남아 **골격이 나중에 자라도 그 노드는
        영영 공정에 붙지 않는다.**

        `defer`가 None이면 종전대로 즉시 싣는다 — 레코드 맥락 없이 부르는 자리
        (골격 대조 등)를 위한 갈래다.
        """
        if not surface:
            return None, None
        g, _ = self._graph_for(category)          # 걸침 anchor는 다른 층에서 찾는다
        live = [nid for nid in self.dict.lookup(surface)
                if is_live(g.get(nid) or {}) and
                (g.get(nid) or {}).get("category") == category]
        # **Tier1 한정** — 조회 결과가 auto 노드뿐이면 anchor로 쓰지 않는다(문서 2 §2.4-①).
        # 산문에서 스쳐 언급된 auto 노드가 골격 행세하는 우회로를 막는다.
        tier1 = [nid for nid in live if g.get(nid).get("status") in ("seed", "confirmed")]
        autos = [nid for nid in live if nid not in tier1]

        def _hold(reason, extra):
            payload = {"surface": surface, "category": category, "provenance": prov}
            # 조회된 auto 후보를 싣는다 — 동봉하지 않으면 사람이 큐 화면에서
            # 후보를 다시 검색해야 판단할 수 있다(문서 2 §2.4-①).
            if autos:
                payload["auto_candidates"] = [
                    {"id": a, "canonical": g.get(a)["canonical"]} for a in autos]
            payload.update(extra)
            item = {"kind": "orphan_anchor", "reason": reason, "payload": payload}
            if defer is None:
                store.enqueue("orphan_anchor", reason, self.doc_id, payload)
            else:
                defer.append(item)
            return None, None

        if len(tier1) == 1:
            return tier1[0], g
        if len(tier1) > 1:
            return _hold(f"표기 모호 — '{surface}'가 골격 노드 여럿을 가리킨다",
                         {"candidates": [g.get(h)["canonical"] for h in tier1]})
        if autos:
            return _hold(f"골격 밖 — '{surface}'는 auto 노드로만 있다 (Tier1 한정)", {})
        return _hold(f"골격에 없는 좌표 — '{surface}'", {})

    def check_coord(self, group_surface, ref_id, prov, g=None):
        """③ process_group은 **부착하지 않고 골격 조상 대조만** 한다.

        둘 다 골격에 실존하되 조상 관계가 아니면 `coord_mismatch`(C3).
        골격 **밖** 값이면 coord_mismatch가 아니라 anchor 미해소 → orphan_anchor다(D3·A5).
        """
        if not group_surface or not ref_id:
            return True
        g = g or self.g
        skel_cat = (g.nodes.get(ref_id) or {}).get("category")
        gid = None
        for nid in self.dict.lookup(group_surface):
            if (g.get(nid) or {}).get("category") == skel_cat:
                gid = nid
                break
        if gid is None:
            return True                       # 골격 밖 → orphan_anchor 경로가 이미 처리
        from .bootstrap import layer_of_category, load_config
        owner = load_config(layer_of_category(skel_cat) or self.layer)
        child_rel = owner["skeleton"]["relations"]["child"]
        ancestors, cur = set(), ref_id
        while True:
            nxt = [e["dst"] for e in g.edges
                   if e["src"] == cur and e["rel"] == child_rel]
            if not nxt or nxt[0] in ancestors:
                break
            ancestors.add(nxt[0])
            cur = nxt[0]
        if gid in ancestors or gid == ref_id:
            return True
        store.enqueue("coord_mismatch",
                      f"'{group_surface}'는 골격에 실존하나 "
                      f"'{g.get(ref_id)['canonical']}'의 조상이 아니다",
                      self.doc_id,
                      {"process_group": group_surface,
                       "process_ref": g.get(ref_id)["canonical"],
                       "provenance": prov})
        return False

    def descend_anchor(self, ref_id, electrode_type, g=None):
        """⓪ **하강 부착** (틀 §4B-A11-9 ⓪ · 카드 F1 v18 · CH3B 3.5 규약 3-⓪).

        좌표가 **개념 노드**인데 record의 축값이 확정이면, 그 개념의 **동일 축값
        인스턴스가 존재할 때** 그리로 내려가 부착한다(`탭용접`+cathode → `탭용접::cathode`).
        하강 후에는 ①(표면형 결합 생략)이 그대로 적용된다.

        **인스턴스가 없으면 하강하지 않는다** — 골격은 Tier1이고 부착 코드가 임의로
        인스턴스를 만들 수 없다. 그때는 현행 F1 결합이 답이다.

        고치는 것: 같은 실물이 좌표 해상도에 따라 두 canonical로 갈리던 접점 결함이다
        (`탭용접::cathode 용접 가압력` ↔ `탭용접::cathode::용접 가압력` — 판정필요-6).
        **A11-5 순서 파생의 하강과 동형**이라 그 함수를 그대로 쓴다 — 새 로직이 아니다.
        """
        if not ref_id:
            return ref_id
        g = g or self.g
        node = g.get(ref_id) or {}
        owner = self._owner_cfg(node)
        if is_bound(node.get("polarity"), owner):      # 이미 인스턴스다 — 하강 대상 아님
            return ref_id
        if not is_bound(electrode_type, owner):        # record가 축값을 확정하지 않았다
            return ref_id
        child_rel = ((owner.get("skeleton") or {}).get("relations") or {}).get("child")
        if not child_rel:
            return ref_id
        from .query import _descend                    # A11-5와 같은 하강 (동형 재사용)
        return _descend(g, ref_id, electrode_type, child_rel)

    def anchor_polarity(self, ref_id, g=None):
        """부착 골격 노드의 polarity. 축값이 확정일 때만 돌려준다(아니면 None).

        확정이면 ①표면형 극성 결합을 생략하고 ②노드 polarity를 여기서 상속한다
        (A11-9 ①) — 극성이 이미 주소(스코프 접두)에 있으므로 표면형에 다시 붙이면
        `…::anode::anode 용접 강도` 같은 이중 표기가 된다.
        """
        if not ref_id:
            return None
        node = ((g or self.g).get(ref_id) or {})
        pol = node.get("polarity")
        return pol if is_bound(pol, self._owner_cfg(node)) else None

    def _owner_cfg(self, node):
        """그 노드를 선언한 층의 config. 축값 목록은 그 층이 소유한다(B1).

        걸침 anchor(품질층 문서 → 공정층 골격)에서 자기 층 config를 쓰면 축값
        목록이 비어 판정이 조용히 무력화된다.
        """
        if not node or node.get("layer") == self.layer:
            return self.cfg
        from .bootstrap import load_config
        return load_config(node["layer"])

    def check_polarity(self, ref_id, electrode_type, prov, g=None):
        """② record의 극성과 부착 골격 노드의 polarity 대조 (A11-9 ②).

        **둘 다 확정인데 서로 다르면** 조용히 한쪽을 택하지 않고 `coord_mismatch`
        큐로 표면화한다 — C3의 좌표 대조와 같은 계열의 공짜 검증이다. 한쪽이라도
        미확정(none·unbound·both·무표기)이면 대조 대상이 아니다.
        """
        if not ref_id:
            return True
        g = g or self.g
        node = g.get(ref_id) or {}
        owner = self._owner_cfg(node)
        node_pol = node.get("polarity")
        if not is_bound(node_pol, owner) or not is_bound(electrode_type, owner):
            return True
        if node_pol == electrode_type:
            return True
        store.enqueue("coord_mismatch",
                      f"record의 극성 '{electrode_type}'과 좌표 "
                      f"'{node['canonical']}'의 극성 '{node_pol}'이 다르다",
                      self.doc_id,
                      {"process_ref": node["canonical"],
                       "node_polarity": node_pol, "electrode_type": electrode_type,
                       "provenance": prov})
        return False

    # ---------------------------------------------------------------- entity
    def resolve_entity(self, surface, category, prov, *, electrode_type=None,
                       parent_canonical=None, anchor_polarity=None):
        """3분기 — 매칭 / 신규 / 불확실(신규+표시).

        `anchor_polarity`가 확정이면 **표면형 극성 결합을 생략**하고 polarity를
        그 노드에서 **상속**한다(A11-9 ① — 이중 표기 방지). 그렇지 않을 때만
        기존 극성 결합 3조건이 돈다(F1).

        **생략은 스코프 카테고리에 한정한다** [틀 v2.7 · CH3B v2.2 3.5 규약 3 ·
        카드 F1]. 생략의 근거는 "극성이 이미 주소에 있다"인데, 주소가 canonical에
        실리는 것은 `canonical_scope`가 걸린 카테고리(현행 Property)뿐이다.
        스코프가 없는 카테고리(Unit)에 생략을 적용하면 표면형에도 주소에도 극성이
        없어져 **polarity 필드만 다르고 canonical이 같은 노드 2개가 공존**한다
        (P4 취지 위반 — C12 실측). 그래서 Unit은 F1 극성 결합을 유지한다.
        """
        from .bootstrap import layer_of_category
        if layer_of_category(category) is None:
            # 카테고리는 **운영 중에 발명되지 않는다**(카드 I3 · CH2 2.9 금지 목록).
            # 추출→구축의 신뢰 경계에서 이것이 유일한 강제 지점이다 — 프롬프트 계약만으로는
            # 층 어휘가 아닌 이름이 그래프에 심긴다.
            store.enqueue("invalid_category",
                          f"층이 선언하지 않은 카테고리 '{category}' — 노드를 만들지 않는다",
                          self.doc_id, {"surface": surface, "category": category,
                                        "provenance": prov})
            return None
        scoped_category = category in (self.cfg.get("canonical_scope") or {}) \
            .get("bind_categories", [])
        anchor_polarity = anchor_polarity if scoped_category else None
        inherited = anchor_polarity is not None
        bound = surface if inherited else \
            bind_polarity(surface, category, electrode_type, self.cfg)       # ④
        polarity = derive_polarity(category, electrode_type, self.cfg,
                                   anchor_polarity=anchor_polarity)
        canonical, scoped = scope_canonical(bound, category,
                                            parent_canonical, self.cfg)
        verdict, nid, _ = resolve(canonical, category, self.layer,
                                  self.g, self.dict, scoped=scoped,
                                  polarity=polarity)
        if verdict == MATCH:
            self._register(surface, nid, prov)
            if prov not in self.g.get(nid)["provenance"]:
                self.g.get(nid)["provenance"].append(prov)
            self.buffer[norm(surface)] = nid
            return nid

        extra = {"_scoped": True} if scoped and self.cfg.get("canonical_scope", {}) \
            .get("bind_categories", []).count(category) else {}
        extra["polarity"] = polarity                     # 닫힌 4값을 항상 기록한다
        # mirrors 짝 키의 두 요소 — **부모**와 **주소 접두를 제외한 자기 이름부**다
        # (F3). canonical을 되 파싱하지 않기 위해(A11-8) 조립 시점에 적어 둔다.
        # 스코프가 없는 카테고리는 부모가 이름에 실리지 않으므로 부모 요소도 없다.
        extra["mirror_scope"] = parent_canonical if scoped_category else None
        extra["mirror_name"] = norm(surface)
        nid = self.g.add_node(canonical, category, "auto", provenance=[prov], **extra)
        self._register(surface, nid, prov)
        store.enqueue("auto_node" if verdict == NEW else "uncertain_match",
                      f"{'자동 생성' if verdict == NEW else '판정 불확실 — 신규로 생성'}"
                      f": {canonical} ({category})",
                      self.doc_id, {"node_id": nid, "canonical": canonical,
                                    "surface": surface, "provenance": prov})
        self.buffer[norm(surface)] = nid
        return nid

    # ---------------------------------------------------------------- attribute
    def put_attribute(self, node_id, name, value, context, prov, contextual):
        """맥락형은 `[{context, value, provenance}]`로 **병렬 저장**한다.

        충돌 판정은 **같은 context 그룹 안에서만** — deep-equal로 달라야 spec_conflict다.
        context가 다르면 충돌이 아니라 병렬 항목이고, 완전 동일이면 무시한다.
        """
        n = self.g.get(node_id)
        if n is None:
            return
        attrs = n.setdefault("attrs", {})
        if not contextual:
            # **단순형은 빈 context 그룹 하나로 취급한다**(3.6 규약 5) — 분기가 아니라
            # 특수 사례다. 구판은 deep-equal 없이 덮어써서 교차 출처의 다른 주장이
            # provenance째 소멸했다("충돌은 정보다" — 규약 6).
            context = {}
        items = attrs.setdefault(name, [])
        if not isinstance(items, list):                  # 구판 단순형 값의 승격
            items = attrs[name] = [items]
        for it in items:
            if it.get("context") == context:
                if it.get("value") == value:
                    if prov not in it["provenance"]:
                        it["provenance"].append(prov)
                    return
                # **대상 노드의 polarity를 동봉한다**(문서 4 §4.7). 무극성(`none`)
                # 건은 **I3 분리 후보**로 표시한다 — 극성이 갈린 값이 한 노드에
                # 쌓인 것일 수 있고, 그 경우 사람이 볼 것은 "값 충돌"이 아니라
                # "노드가 둘이어야 하는가"다. 표시가 없으면 두 사건이 큐에서
                # 구분되지 않아 판정자가 매번 그래프를 다시 열어야 한다.
                pol = n.get("polarity") or POLARITY_NONE
                store.enqueue("spec_conflict",
                              f"{n['canonical']}의 {name}: 같은 맥락에 다른 값",
                              self.doc_id,
                              {"node_id": node_id, "attr": name, "context": context,
                               "existing": it["value"], "incoming": value,
                               "polarity": pol,
                               "split_candidate": pol == POLARITY_NONE,
                               "provenance": prov})
                return
        items.append({"context": context, "value": value, "provenance": [prov]})

    # ---------------------------------------------------------------- mirrors
    def _mirror_scope(self, scope):
        """짝 키의 부모 요소 — **부모가 mirror 쌍이면 동일시한다**(F3 하향 연쇄).

        부모가 축 인스턴스이고 그 인스턴스가 mirrors로 이어져 있으면, 그 아래 같은
        이름의 자식들은 **같은 자리**에 있는 것이다. 그래서 부모를 개념 노드로 올려
        잡아야 `탭용접::cathode::용접 강도`와 `탭용접::anode::용접 강도`가 한 키로
        모인다. 구판은 canonical 전문을 키로 써서 둘을 영영 못 짝짓고 전부 편측
        큐로 흘렸다(D-50이 고친 것과 같은 뿌리의 남은 절반).

        **짝 없는 인스턴스는 동일시하지 않는다** — mirrors 엣지가 없으면 그 자리는
        분화 쌍이 아니고, 올려 잡으면 무관한 자식들이 한 키로 뭉친다.
        판정 근거는 전부 필드·엣지다 — canonical을 파싱하지 않는다(A11-8).
        """
        if not scope:
            return scope
        node = next((n for n in self.g.nodes.values() if n["canonical"] == scope), None)
        if node is None or not is_bound(node.get("polarity"), self.cfg):
            return scope
        mrel = (self.cfg.get("mirrors") or {}).get("relation")
        if not any(e["src"] == node["id"] and e["rel"] == mrel for e in self.g.edges):
            return scope
        child_rel = (self.cfg.get("skeleton") or {}).get("relations", {}).get("child")
        up = [e["dst"] for e in self.g.edges
              if e["src"] == node["id"] and e["rel"] == child_rel]
        return self.g.get(up[0])["canonical"] if up else scope

    def link_mirrors(self):
        """④ 자동 규칙 — 같은 이름부(결합 전 canonical) + polarity 반대 쌍.

        **판정 근거는 `polarity` 필드다**(F3 — 문자열 극성 토큰 파싱 폐지). 짝을
        찾는 키도 canonical을 되 파싱해 만들지 않고, 결합 시점에 적어 둔
        `base_canonical`(스코프는 붙고 극성은 안 붙은 이름)을 쓴다. 구판은 **앞에
        붙은** 접두만 뗄 수 있어서 스코프가 붙은 관리항목(`노칭::anode 버 높이`)의
        짝을 영영 찾지 못했고, 정상 쌍까지 비대칭 큐로 흘렸다.

        **Tier1(seed) 노드는 제외한다** — 골격의 mirrors는 loader가 이미 이었고,
        Tier1 단극성은 사람 보증이라 `mirror_asymmetry` 대상이 아니다(A11-4).
        이 큐는 **Tier2의 문서 편측 갱신**을 잡는 장치다.

        **표시만 한다.** 값을 공유하지 않으며, 한쪽에만 있는 자식은
        `mirror_asymmetry` 큐로 알린다(3.5 규약 3).
        """
        rel = (self.cfg.get("mirrors") or {}).get("relation")
        if not rel or not (self.cfg.get("mirrors") or {}).get("enabled"):
            return
        vals = (self.cfg.get("polarity") or {}).get("values") or []
        if not vals:
            return
        # **재평가 전에 이 층 소관의 옛 항목을 걷어낸다** — 매 빌드의 재평가가 곧
        # 현재 스냅샷이고, 대칭이 회복되면 큐에서 내려가야 한다(3.5 규약 6 self-heal).
        store.drop("mirror_asymmetry", lambda p: p.get("node_id") in self.g.nodes)
        by_key = {}
        for nid, n in self.g.nodes.items():
            if n["status"] == "seed":                    # Tier1 — loader 소관
                continue
            pol = n.get("polarity")
            if pol not in vals:
                continue
            key = (self._mirror_scope(n.get("mirror_scope")),
                   n.get("mirror_name") or n["canonical"])
            by_key.setdefault(key, {})[pol] = nid
        for base, pair in by_key.items():
            if len(pair) == len(vals):
                a, b = (pair[v] for v in vals)
                gate.commit_edge(self.g, a, rel, b, self.cfg, gate.PATH_AUTO,
                                 ["auto:mirror_rule"], self.doc_id)
                gate.commit_edge(self.g, b, rel, a, self.cfg, gate.PATH_AUTO,
                                 ["auto:mirror_rule"], self.doc_id)
                continue
            # 비대칭 — 한쪽 극성에만 달린 자식
            only = next(iter(pair))
            scope, name = base
            sep = (self.cfg.get("canonical_scope") or {}).get("sep", "::")
            label = f"{scope}{sep}{name}" if scope else name
            store.enqueue("mirror_asymmetry",
                          f"'{label}'가 {only} 쪽에만 있다 (극성 쌍의 구성 불일치)",
                          self.doc_id,
                          {"base": label, "scope": scope, "name": name,
                           "present": only, "node_id": pair[only]})
