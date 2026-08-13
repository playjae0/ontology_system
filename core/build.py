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
from .ids import norm
from .matcher import MATCH, NEW, UNCERTAIN, resolve
from .naming import bind_polarity, derive_polarity, is_bound, scope_canonical

ROLE_HANDLERS = ("anchor", "entity", "attribute", "content", "meta")


class Builder:
    def __init__(self, graph, cfg, schema, doc_id, layer):
        self.g = graph
        self.cfg = cfg
        self.schema = schema
        self.doc_id = doc_id
        self.layer = layer
        self.dict = store.read(store.DICTIONARY, {})
        self.buffer: dict[str, str] = {}     # 문서 해소 버퍼 (2-pass Pass 1)

    # ---------------------------------------------------------------- 사전
    def _register(self, surface, nid, prov):
        """사전 등재에는 **provenance가 필수**다 (CH3A 3.3 규약 5)."""
        self.dict.setdefault(norm(surface), [])
        if nid not in self.dict[norm(surface)]:
            self.dict[norm(surface)].append(nid)
        n = self.g.get(nid)
        if norm(surface) != norm(n["canonical"]) and \
                not any(a["surface"] == surface for a in n["aliases"]):
            n["aliases"].append({"surface": surface, "provenance": [prov]})

    def flush(self):
        store.write(store.DICTIONARY, self.dict)

    # ---------------------------------------------------------------- anchor
    def _graph_for(self, category):
        """카테고리를 선언한 층의 그래프. 같은 층이면 self.g를 그대로 쓴다."""
        if category in self.cfg.get("categories", {}):
            return self.g, self.layer
        from .bootstrap import layer_of_category, open_graph
        lay = layer_of_category(category)
        if lay is None or lay == self.layer:
            return self.g, self.layer
        return open_graph(lay), lay

    def resolve_anchor(self, surface, category, prov):
        """골격 조회 전용 — anchor는 새로 만들지 않는다.

        돌려주는 것은 **(node_id, 그 노드가 사는 그래프)**다. 걸침 anchor는 다른 층에
        살기 때문에 그래프를 함께 줘야 호출부가 카테고리를 물어볼 수 있다.

        조회 대상은 **사전 하나**다(D-47) — 좌표 닫힌 목록 = 골격 전 노드이며
        (A11-6), 개념 노드와 인스턴스가 둘 다 그 목록에 있다. 문서가 상위·개념
        해상도로 말하면("탭용접") 개념 노드가 답이고, 그것은 오류가 아니라
        **저해상도 부착**이다.

        **극성 모호(구 D5)는 구조적으로 소멸했다**(A11-6): 극성 무관 표면형의 alias는
        개념 노드가 단독 소유하고, 극성 수식 표기는 인스턴스의 auto alias다. 남는
        orphan_anchor 경로는 **"목록 밖 이름"**과 **"표기 모호"** 둘뿐이며, 후자에서도
        임의 선택하지 않는다 — 쓰기는 좁게(3.5 규약 7).
        """
        if not surface:
            return None, None
        g, _ = self._graph_for(category)          # 걸침 anchor는 다른 층에서 찾는다
        hits = [nid for nid in self.dict.get(norm(surface), [])
                if (g.get(nid) or {}).get("category") == category]
        if len(hits) == 1:
            return hits[0], g
        if len(hits) > 1:
            store.enqueue("orphan_anchor",
                          f"표기 모호 — '{surface}'가 골격 노드 여럿을 가리킨다",
                          self.doc_id,
                          {"surface": surface, "candidates":
                           [g.get(h)["canonical"] for h in hits], "provenance": prov})
            return None, None
        store.enqueue("orphan_anchor", f"골격에 없는 좌표 — '{surface}'",
                      self.doc_id, {"surface": surface, "category": category,
                                    "provenance": prov})
        return None, None

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
        for nid in self.dict.get(norm(group_surface), []):
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
        """
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
        # mirrors 짝 찾기의 키 — **결합 전** canonical이다. canonical 문자열을 되
        # 파싱하지 않기 위해(A11-8) 조립 시점에 함께 적어 둔다.
        extra["base_canonical"] = scope_canonical(
            surface, category, parent_canonical, self.cfg)[0]
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
            attrs[name] = {"value": value, "provenance": [prov]}
            return
        items = attrs.setdefault(name, [])
        if not isinstance(items, list):
            items = attrs[name] = [items]
        for it in items:
            if it.get("context") == context:
                if it.get("value") == value:
                    if prov not in it["provenance"]:
                        it["provenance"].append(prov)
                    return
                store.enqueue("spec_conflict",
                              f"{n['canonical']}의 {name}: 같은 맥락에 다른 값",
                              self.doc_id,
                              {"node_id": node_id, "attr": name, "context": context,
                               "existing": it["value"], "incoming": value,
                               "provenance": prov})
                return
        items.append({"context": context, "value": value, "provenance": [prov]})

    # ---------------------------------------------------------------- mirrors
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
        by_key = {}
        for nid, n in self.g.nodes.items():
            if n["status"] == "seed":                    # Tier1 — loader 소관
                continue
            pol = n.get("polarity")
            if pol not in vals:
                continue
            key = n.get("base_canonical") or n["canonical"]
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
            store.enqueue("mirror_asymmetry",
                          f"'{base}'가 {only} 쪽에만 있다 (극성 쌍의 구성 불일치)",
                          self.doc_id,
                          {"base": base, "present": only, "node_id": pair[only]})
