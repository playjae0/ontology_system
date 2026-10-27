# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **Builder의 좌표 손**(B113 ① · B90 ③ · B125 ④) — 다른 공정 이름 가드 · 자기 좌표 규칙 · 청크 공정 목록의 해소.

`Builder`가 이 믹스인을 상속한다(B125 — `build.py`가 800행 상한을 넘어 나눴다 · 같은 메서드 · 같은 이름).
목록 표현의 읽는 손은 `parser.normalizer.coord_refs` 하나다.
"""
from __future__ import annotations

from core.state import store
from core.state.ids import norm
from core.state.status import is_live


class CoordMixin:
    # ---------------------------------------------------------------- 다른 공정 이름 (B113 ①)
    def other_process(self, surface, coord, coords=None):
        """**다른 공정의 골격 이름**(B113 ①) — 표기가 사전(정확 · 라틴 대소문자 2차)에서 골격 노드(Tier1)에 맞고
        그 노드가 **좌표의 계보 밖**(좌표 자신 · 조상 · 서브트리 어디도 아니다)이면 `(노드 id 또는 None, 맞은
        canonical들)` · 아니면 None. 노드가 여럿이면(공유 별칭) 하나라도 계보 안이면 None · 다 밖이면 id 없이.
        좌표가 없으면 계보를 모르니 None(지금 규칙 — 좌표 없는 스코프 개체 0 등). 골격 이름은 데이터다.
        `coords`(청크 공정 목록 — B125 ④)면 목록 **전체**의 계보 밖일 때만이다(하나라도 계보 안이면 None)."""
        refs = [(r, g) for r, g in (coords or [coord or (None, None)]) if r and g is not None and g.get(r)]
        if not surface or not refs:
            return None
        from core.state.bootstrap import COORD_CATEGORY
        g, _ = self._graph_for(COORD_CATEGORY)
        hits = sorted(nid for nid in set(self.dict.lookup(surface))
                      if (g.get(nid) or {}).get("category") == COORD_CATEGORY and is_live(g.get(nid))
                      and g.get(nid).get("status") in ("seed", "confirmed"))
        if not hits:
            return None
        pm = self._parent_map(g, COORD_CATEGORY)

        def chain(c):
            out = []
            while c and c not in out and len(out) < 64:
                out.append(c)
                c = pm.get(c)
            return out
        cans = [g.get(n)["canonical"] for n in hits]
        for ref, ref_g in refs:
            rc = ref_g.get(ref)["canonical"]
            up = set(chain(rc))
            if any(c in up or rc in chain(c) for c in cans):
                return None
        return (hits[0] if len(hits) == 1 else None), cans

    def _mention(self, surface, category, prov, other):
        """다른 공정 언급 — 노드 0 · 관련 링크 재료(`mentions`) · 대장 행(경로 `skeleton` · 판정 `mention` ·
        canonical = 그 공정). 공유 별칭이 계보 밖 여럿이면 링크 없이(결함 로그)."""
        nid, cans = other
        if not hasattr(self, "mentions"):
            self.mentions = []
        loc = (prov or "").split("#", 1)[-1] if "#" in str(prov or "") else prov
        if nid:
            self.mentions.append({"locator": loc, "node_id": nid, "surface": surface})
        else:
            store.append_defect(f"{self.doc_id}: 다른 공정 이름 '{surface}'가 골격 노드 여럿({' · '.join(cans)})이라 "
                                f"관련 링크를 달지 않았다 @ {loc} (노드 0)")
        self.last = {"canonical": " · ".join(cans), "verdict": "mention", "path": "skeleton",
                     "confidence": 1.0, "layer": self.layer, "queue_kind": None, "candidates_n": 0,
                     "node_id": None, "category": category, "llm": {"calls": 0, "in_tokens": 0, "out_tokens": 0}}
        return None

    def _self_coord(self, surface, category, coord):
        """**자기 좌표 규칙**(B90 ③) — 좌표 X 아래에서 뽑힌 C 표기가 사전에서 **X 자신**으로
        해소되고(별칭 포함) X가 C를 겸하면 → X다. 자식 노드 0 · 대장 `path=self_coord`.

        스테이션 이름 + 설비어(「… unit」)는 스테이션 자신이다 — 그 아래 새 Unit을 세우면
        같은 실물이 두 노드가 된다. 겸이 없으면(카탈로그 `also` 없음) 지금처럼 일반 해소다.
        """
        ref, ref_g = coord or (None, None)
        n = ref_g.get(ref) if (ref and ref_g is not None) else None
        if not n or n.get("category") == category:
            return None
        from core.state import catalog
        try:
            if category not in catalog.categories_of(n):
                return None
        except catalog.CatalogError:
            return None
        if ref not in self.dict.lookup(surface):
            return None
        eb = self.for_layer(n.get("layer") or self.layer)
        self.buffer[norm(surface)] = ref
        eb.last = {"canonical": n["canonical"], "verdict": "match", "path": "self_coord",
                   "confidence": 1.0, "layer": eb.layer, "queue_kind": None,
                   "candidates_n": 0, "node_id": ref}
        return ref, eb


    # ---------------------------------------------------------------- 청크 공정 목록 (B125 ④)
    def resolve_coords(self, value, category, prov, *, electrode_type=None, defer=None):
        """**청크 공정 목록의 해소**(B125 ④) — `[(표기, id, 그래프, 보류 사유)]`(목록 순서 · 극성 인스턴스로 내린 것) ·
        비면 `[(None, None, None, None)]`(좌표 없음 — 지금 행 하나 그대로). 표 · 산문 · 제목 개체가 이 함수 하나."""
        from parser.normalizer import coord_refs
        out = []
        for s in coord_refs(value):
            nid, g = self.resolve_anchor(s, category, prov, defer=defer)
            hold = self.anchor_hold
            out.append((s, self.descend_anchor(nid, electrode_type, g) if nid else None, g, hold))
        if not out:
            self.resolve_anchor(None, category, prov, defer=defer)
            out = [(None, None, None, None)]
        return out

    @staticmethod
    def main_coord(resolved):
        """**주 좌표** — 공정이 하나일 때만 그 해소 `(id, 그래프)` · 둘 이상이면 `(None, None)`(개체가 `parent`로 제 공정을
        고른다 — 못 고르면 좌표 없음 · 지어내지 않는다 · B125 ④)."""
        return (resolved[0][1], resolved[0][2]) if len(resolved) == 1 else (None, None)
