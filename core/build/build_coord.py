# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **Builder의 좌표 손**(B113 ① · B90 ③ · B125 ④ · B181 ①) — 골격 조회(`resolve_anchor` — 닫힌 분류의 같은지 판단) · 다른 공정 이름 가드 · 자기 좌표 규칙 · 청크 공정 목록의 해소.

`Builder`가 이 믹스인을 상속한다(B125 — `build.py`가 800행 상한을 넘어 나눴다 · 같은 메서드 · 같은 이름).
목록 표현의 읽는 손은 `parser.normalizer.coord_refs` 하나다.
"""
from __future__ import annotations

from core import matcher as _matcher
from core.matcher import MATCH, UNCERTAIN, held
from core.state import store
from core.state.bootstrap import COORD_CATEGORY
from core.state.ids import norm
from core.state.status import is_live

#: 좌표 보류 사유 — 표기가 골격 노드 여럿을 가리킨다(B104 ①). 목록 밖과 처방이 다르다(대장 `hold` · 큐 문면).
HOLD_AMBIGUOUS = "표기 모호(골격 노드 여럿)"


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
    def resolve_coords(self, value, category, prov, *, electrode_type=None, defer=None, piece=None):
        """**청크 공정 목록의 해소**(B125 ④) — `[(표기, id, 그래프, 보류 사유)]`(목록 순서 · 극성 인스턴스로 내린 것) ·
        비면 `[(None, None, None, None)]`(좌표 없음 — 지금 행 하나 그대로). 표 · 산문 · 제목 개체가 이 함수 하나.
        `piece`(그 조각)가 있으면 파서의 골격 칸 판단(`coord_judged`)을 보류에 싣는다(B181 ①)."""
        from parser.normalizer import coord_refs
        out = []
        for s in coord_refs(value):
            nid, g = self.resolve_anchor(s, category, prov, defer=defer, judged=coord_judged(piece, s))
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

    # ---------------------------------------------------------------- anchor
    def _graph_for(self, category):
        """카테고리의 **집** 그래프 (B90 ② — 자기 층 선언을 먼저 보지 않는다).

        여러 층이 같은 카테고리를 선언하면 「내 층도 선언했다」는 답이 되지 못한다 —
        노드는 집 하나에 산다. 같은 층이면 self.g를 그대로 쓴다.
        """
        eb = self.for_category(category)
        return eb.g, eb.layer

    def resolve_anchor(self, surface, category, prov, *, defer=None, judged=None, ask=None):
        """골격 조회 — anchor는 새로 만들지 않는다.

        돌려주는 것은 **(node_id, 그 노드가 사는 그래프)**다. 걸침 anchor는 다른 층에
        살기 때문에 그래프를 함께 줘야 호출부가 카테고리를 물어볼 수 있다.

        **사전(정확 일치·alias)이 먼저다** — 미스면 **같은지 판단**(B181 ① · 결정 D — 개체와 같은 함수 `matcher.decide`):
        골격 칸(좌표)은 파서가 이미 판단했고 그 답(`judged` — 행의 `meta.coord_judge`)을 받는다 · 닫힌 분류(좌표 층 밖
        골격 — anchor 칸)는 `ask=(행, 칸)`을 준 자리(anchor 핸들러 하나)에서만 묻는다 — 조회만 하는 자리(목차 · 소속 · 제목 ·
        예고 · 등록 관문)는 LLM 0. 같다면 해소 · 그 표기는 사전 · 표기 대장(닫힌 분류 · 기계 판단)에 남는다 · 다르다면
        보류 · 애매면 보류 + 후보 동봉(payload `judge`). 골격은 사람이 고정한 유형이다(P2 — 새로 만들지 않는다).
        좌표 닫힌 목록 = 골격 전 노드이며
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
        self.anchor_hold = None                   # 이 호출의 보류 사유(대장 anchor 행이 싣는다 · B104 ①)
        self.anchor_judge = None                  # 이 호출의 닫힌 분류 판단(B181 ① — anchor 핸들러의 대장 행이 옮긴다)
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
            # **층을 싣는다**(B72 ③) — 다음 줄이 `layers/<층>/skeleton.json`을
            # 가리키므로, 층을 모르면 사람이 그 줄을 그대로 칠 수 없다.
            payload = {"surface": surface, "category": category,
                       "provenance": prov, "layer": self.layer}
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
            # **해소된 좌표도 문서 버퍼에 싣는다**(문서 4 §4.2 Pass 1) — 버퍼는
            # `정규화 표면형 → node_id` 맵이고 anchor·entity를 **둘 다** 담는다.
            # 안 실으면 `attach_to`가 골격 노드 표기를 가리킬 때(산문이 공정에
            # 직접 붙이는 정상 경로) 버퍼 조회가 미스가 되어 사전으로 새고,
            # 같은 문서 안의 해소 결과가 재사용되지 않는다.
            self.buffer[norm(surface)] = tier1[0]
            return tier1[0], g
        if len(tier1) > 1:
            self.anchor_hold = HOLD_AMBIGUOUS
            return _hold(f"표기 모호 — '{surface}'가 골격 노드 여럿을 가리킨다",
                         {"candidates": [g.get(h)["canonical"] for h in tier1]})
        # **사전이 답하지 않았다 — 같은지 판단**(B181 ① · 결정 D 4단계) — 골격 칸은 파서의 답 · 닫힌 분류는 여기서
        v = judged
        if ask is not None and category != COORD_CATEGORY:
            v = self.anchor_judge = self._closed_judge(surface, category, g, *ask)
            if v and v.get("type") == MATCH:
                return self._closed_match(surface, category, g, v, prov), g
        extra = {"judge": held(v)} if v and v.get("type") == UNCERTAIN else {}
        if autos:
            return _hold(f"골격 밖 — '{surface}'는 auto 노드로만 있다 (Tier1 한정)", extra)
        return _hold(f"골격에 없는 좌표 — '{surface}'", extra)

    def _closed_judge(self, surface, category, g, row, field):
        """**닫힌 분류의 같은지 판단**(B181 ①) — 후보는 그 카테고리 골격 목록(골격 칸과 같은 함수 `tagger.choices` — 이름 · 별칭 ·
        부모 경로 · Tier1 산 노드만) · 같은 표기는 문서에 한 번(기억) · mock · 후보 0이면 None(지금 그대로 보류)."""
        from parser.namefold import key
        memo = self.__dict__.setdefault("_closed", {})
        k = (category, key(surface))
        if k not in memo:
            from core.build.extract_ctx import source_of
            from core.state.bootstrap import load_config
            from core.state.surface_book import CLOSED
            from parser.tagger import choices, closed_list
            lay = self.home_of(category)
            pool = [dict(c, category=category) for c in choices(closed_list(lay))[0]
                    if (g.get(c["id"]) or {}).get("category") == category and is_live(g.get(c["id"]))
                    and g.get(c["id"]).get("status") in ("seed", "confirmed")]
            sent = source_of(row, surface, field, _matcher.context_chars()) if row else None
            memo[k] = _matcher.decide(surface, pool, category, load_config(lay), sentence=sent, place=CLOSED)
        return memo[k]

    def _closed_match(self, surface, category, g, v, prov):
        """닫힌 분류 「같다」 — 그 골격 노드로 해소 · 표기는 사전 · 표기 대장에(출처 LLM 매칭 · 기계 판단 — 다음엔 사전에서 끝)."""
        nid = v["matched_id"]
        eb = self.for_category(category)
        eb._register(surface, nid, prov, by={"by": "LLM 매칭", "confidence": round(float(v.get("confidence") or 0), 4),
                                              "doc": self.doc_id})
        self.buffer[norm(surface)] = nid
        return nid

    def anchor_hold_of(self, surface, category=None):
        """좌표 표기가 왜 안 풀렸나(B104 ①) — 골격 노드 여럿을 가리키면 `(HOLD_AMBIGUOUS, [canonical…])` ·
        아니면 `(None, [])`(목록 밖). 사전 조회 한 번 — `resolve_anchor`와 같은 Tier1 기준이다."""
        from core.state.bootstrap import COORD_CATEGORY
        category = category or COORD_CATEGORY
        g, _ = self._graph_for(category)
        t1 = sorted(g.get(n)["canonical"] for n in set(self.dict.lookup(surface or ""))
                    if is_live(g.get(n) or {}) and (g.get(n) or {}).get("category") == category
                    and g.get(n).get("status") in ("seed", "confirmed"))
        return (HOLD_AMBIGUOUS, t1) if len(t1) > 1 else (None, [])


def coord_judged(piece, surface):
    """**파서의 골격 칸 판단**(B181 ①) — 조각 `meta.coord_judge {원 표기: 답 꼴}`에서 지금 표기(태깅이 canonical로 고쳐 썼으면
    원 표기 — `coord_tags` · `coord_tag_from`)의 답 · 없으면 None(이번에 판단하지 않았다 — 정확 · 학습 · 기억 · mock)."""
    m = (piece or {}).get("meta") or {}
    cj = m.get("coord_judge") or {}
    if not cj or not surface:
        return None
    if surface in cj:
        return cj[surface]
    src = next((t.get("from") for t in m.get("coord_tags") or [] if t.get("to") == surface), None) or m.get("coord_tag_from")
    return cj.get(src)


def judge_cells(v):
    """대장 anchor 행의 판단 칸(B181 ⑥ — 곳 · 답 · 확실도 · 다시 묻기) — 판단이 없으면 빈 dict(행 바이트 그대로)."""
    from core.state.surface_book import SKELETON
    if not v:
        return {}
    return {"place": SKELETON, "answer": v.get("type"), "confidence": v.get("confidence"), "judge2": v.get("second")}
