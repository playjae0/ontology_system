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
from .naming import bind_polarity, scope_canonical, strip_polarity

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

        극성 모호(극성 제거 표면형이 양 극성 골격 노드를 함께 가리킴)면
        **임의 선택하지 않고** orphan_anchor 큐로 보낸다 — 쓰기는 좁게(3.5 규약 7).
        """
        if not surface:
            return None, None
        g, _ = self._graph_for(category)          # 걸침 anchor는 다른 층에서 찾는다
        hits = [nid for nid in self.dict.get(norm(surface), [])
                if (g.get(nid) or {}).get("category") == category]
        if hits:
            return hits[0], g
        amb = [nid for nid, n in g.nodes.items()
               if n["category"] == category
               and strip_polarity(n["canonical"], self.cfg) == norm(surface)]
        if len(amb) > 1:
            store.enqueue("orphan_anchor",
                          f"극성 모호 — '{surface}'가 양 극성 골격 노드를 함께 가리킨다",
                          self.doc_id,
                          {"surface": surface, "candidates":
                           [g.get(a)["canonical"] for a in amb], "provenance": prov})
            return None, None
        if len(amb) == 1:
            return amb[0], g
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

    # ---------------------------------------------------------------- entity
    def resolve_entity(self, surface, category, prov, *, electrode_type=None,
                       parent_canonical=None):
        """3분기 — 매칭 / 신규 / 불확실(신규+표시)."""
        bound = bind_polarity(surface, category, electrode_type, self.cfg)   # ④
        polarity = electrode_type if bound != surface else None
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
        if polarity:
            extra["electrode_type"] = polarity
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
        """④ 자동 규칙 — 같은 부모 아래 (극성 제거 canonical 동일 + 극성 반대) 쌍.

        **표시만 한다.** 값을 공유하지 않으며, 한쪽에만 있는 자식은
        `mirror_asymmetry` 큐로 알린다(3.5 규약 3).
        """
        pol = self.cfg.get("polarity")
        rel = (self.cfg.get("mirrors") or {}).get("relation")
        if not pol or not rel or not (self.cfg.get("mirrors") or {}).get("enabled"):
            return
        vals = pol["values"]
        by_key = {}
        for nid, n in self.g.nodes.items():
            et = n.get("electrode_type")
            if et not in vals:
                continue
            by_key.setdefault(strip_polarity(n["canonical"], self.cfg), {})[et] = nid
        for base, pair in by_key.items():
            if len(pair) == len(vals):
                a, b = (pair[v] for v in vals)
                gate.commit_edge(self.g, a, rel, b, self.cfg, gate.PATH_AUTO,
                                 ["auto:mirror_rule"], self.doc_id)
                gate.commit_edge(self.g, b, rel, a, self.cfg, gate.PATH_AUTO,
                                 ["auto:mirror_rule"], self.doc_id)
        # 비대칭 — 한쪽 극성에만 달린 자식
        sep = (self.cfg.get("canonical_scope") or {}).get("sep", "::")
        for base, pair in by_key.items():
            if len(pair) == len(vals):
                continue
            only = next(iter(pair))
            store.enqueue("mirror_asymmetry",
                          f"'{base}'가 {only} 쪽에만 있다 (극성 쌍의 구성 불일치)",
                          self.doc_id,
                          {"base": base, "present": only,
                           "node_id": pair[only], "sep": sep})
