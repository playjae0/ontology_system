# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **잠정 골격 노드**(B182 ①②④ · 결정 A) — 좌표 골격 칸의 이름이 골격(사람이 고정한 것과 잠정)에 없으면 같은지
판단의 답대로 잠정 골격 노드로 세우고, 그 노드가 그 행의 좌표가 된다. **세우는 손은 `make` 하나**다 — 문서 좌표 칸의 앞 패스
(`settle` — 표의 공정 칸 · 조각 좌표(PPT 포함) — 좌표 없는 스코프 개체의 좌표 표기도 이 패스가 세운 노드를 찾는다)와 산문 · 제목의
골격 카테고리 개체(`Builder._skeleton_miss`)가 부른다. 파일명 문서 좌표 제안은 제안일 뿐이다(노드 0 — 이 손을 부르지 않는다).

| 판단 | 처분 |
|---|---|
| 사전에 있음 · 같다 | 그 노드(잠정 포함 — 조회는 `status.is_skeleton` 하나) |
| 다르다(mock — 정확 일치에 맞는 것이 없다) | 잠정 + `auto_node` |
| 애매 | 잠정 + 합칠 후보(판단이 가장 가깝다고 한 후보) + `uncertain_match` |
| 판단을 받지 못함(태깅 상한 · 실패 — 행 `meta.coord_unjudged`) | 보류(`orphan_anchor`) 그대로 |
| 맨 아래 단보다 깊어지는 자리 | 보류 「골격 아래 새 단」 |
| **문**(B196 ① · 결정 A′) — 사람이 「새로」를 정하지 않은 표기 | 세우지 않고 보류 「사람 확인 전 공정 표기」 · 「drop」이면 「사람 drop」 |

**문의 단위는 표기 + 들어온 자리(부모 이름)**다 — 사람 답은 `provisional_hand.decisions`(사람 판단 기록 — 「새로」 · 「drop」 ·
「봄」은 세움) · 사람 없는 실행은 묻지 않는다(전부 보류) · 「새로」를 고른 표기는 1행이어도 선다(출현 수를 세지 않는다).

**모양**: 좌표 골격 카테고리 · home 층 · auto + 표시 필드(`status.PROVISIONAL` = `{answer, near?}`) · 이름 = 표기(같은 이름이 다른 줄기에
이미 있으면 뒤의 것이 `부모::이름`) · 부모 = 같은 행의 위 칸 → 목차의 좌표 제목 → 문서 좌표(없으면 부모 미정 — 부모를 말하는 행이
오면 채운다 · 따로 세우지 않는다) · 부모 엣지 = 골격 config의 자식 관계(출처 = 그 문서 · 형제 순서 0) · 단 = 부모 바로 아래(부모 미정이면
미정 · 극성 단 0) · 골격 파일에는 쓰지 않는다(승격은 사람 — A2). 코드에 층 어휘 0 — 카테고리 · 관계 · 단 이름은 config와 골격 심기의 것.
"""
from __future__ import annotations

from core.state import store
from core.state.ids import norm
from core.state.status import PROVISIONAL, is_live, is_skeleton

#: 보류 사유 — 대장 `hold` · 큐 문면(B182 ② — 결정 「아래로 새 단을 열지 않는다」 · 이름이 다른 노드와 같다 · 「최소 출현 수 미달」은 옛 대장
#: 행을 읽으려고만 남는다 — 그 손잡이는 B197 ⑥에서 걷혔다)
HOLD_DEEP = "골격 아래 새 단"
HOLD_FEW = "잠정 노드 최소 출현 수 미달"
HOLD_NAME = "같은 이름의 다른 노드(부모 미정)"
#: **문**(B196 ①) — 사람이 정하기 전 · 사람이 세우지 않기로 했다(재연결이 다시 열지 않는다)
HOLD_HUMAN = "사람 확인 전 공정 표기"
HOLD_DROP = "사람 drop"
HOLDS = (HOLD_DEEP, HOLD_FEW, HOLD_NAME, HOLD_HUMAN, HOLD_DROP)
GATED = (HOLD_HUMAN, HOLD_DROP)
#: 판단 후보 · 화면 후보 수(B196 ③ — 판단이 낸 후보를 둘까지)
NEAR = 2


# ---------------------------------------------------------------- 조회 (쓰기 0)
def _coord():
    from core.state.bootstrap import COORD_CATEGORY
    return COORD_CATEGORY


def look(b, surface):
    """좌표 골격 노드 조회(사전 정확 · 별칭) — 산 골격 카테고리 노드 id 목록(Tier1 + 잠정 · 쓰기 0)."""
    eb = b.for_category(_coord())
    return [nid for nid in dict.fromkeys(b.dict.lookup(surface or ""))
            if is_live(eb.g.get(nid)) and eb.g.get(nid).get("category") == _coord() and is_skeleton(eb.g.get(nid))]


def _parents(g, child_rel):
    """`{노드 id: 부모 id}` — 골격 자식 관계 엣지 전부(seed · 잠정) · 같은 노드의 부모 엣지가 여럿이면 앞의 것."""
    pm = {}
    for e in g.edges:
        if e["rel"] == child_rel and is_live(g.get(e["src"])) and is_live(g.get(e["dst"])):
            pm.setdefault(e["src"], e["dst"])
    return pm


def _instance(n):
    from core.build.build import POLARITY_NONE
    return (n or {}).get("polarity") not in (None, POLARITY_NONE)


def _depth(g, pm, nid):
    """단의 깊이 — 인스턴스는 세지 않는다(골격 심기 A11-7) · 잠정 노드의 단이 미정이면 None."""
    d, cur, seen = 0, nid, set()
    while cur and cur not in seen and len(seen) < 64:
        seen.add(cur)
        n = g.get(cur) or {}
        if n.get(PROVISIONAL) and not n.get("tier") and cur not in pm:
            return None
        d += 0 if _instance(n) else 1
        cur = pm.get(cur)
    return d


def _chain(pm, nid):
    out, cur = [], nid
    while cur and cur not in out and len(out) < 64:
        out.append(cur)
        cur = pm.get(cur)
    return out


def _same_stem(pm, a, b):
    """공정 줄기가 같은가 — 한쪽이 다른 쪽의 위 · 아래(같음 포함) · 한쪽이 부모 미정이면 참."""
    return a is None or b is None or a in _chain(pm, b) or b in _chain(pm, a)


class _Ctx:
    """한 문서 계획의 재료 — 좌표 그래프 · 부모 표 · 맨 아래 단 · 이름 집합(쓰기 0)."""

    def __init__(self, b):
        from core.state.bootstrap import load_config
        self.b, self.eb = b, b.for_category(_coord())
        g = self.eb.g
        self.child = ((load_config(self.eb.layer).get("skeleton") or {}).get("relations") or {}).get("child")
        self.pm = _parents(g, self.child)
        t1 = [nid for nid, n in g.nodes.items() if is_live(n) and n.get("category") == _coord()
              and is_skeleton(n) and not n.get(PROVISIONAL)]
        self.bottom = max((_depth(g, self.pm, nid) or 0 for nid in t1), default=0)
        self.names = {n["canonical"] for n in g.nodes.values() if is_live(n)}
        self.planned = []                         # 이 문서에 세울 것 — 뒤 행의 같은 이름 · 부모 채우기 대조
        from core.state import provisional_hand as PH
        self.book = PH.decisions()                # 문의 사람 답(B196 ①) — 문서마다 한 번 읽는다

    def gate(self, surface, up):
        """**문**(B196 ①) — `(세운다?, 보류 사유)` · 사람 답이 「새로」(봄 포함)면 세운다 · drop이면 「사람 drop」 · 없으면 「사람 확인 전」."""
        from core.state import provisional_hand as PH
        d = PH.decided(self.book, surface, self.name(up))
        if d == PH.SEEDED:
            return True, None
        return False, (HOLD_DROP if d == PH.DROPPED else HOLD_HUMAN)

    def name(self, nid):
        return (self.eb.g.get(nid) or {}).get("canonical")

    def up_of(self, piece, surface, low, outline):
        """부모 — 같은 행의 위 칸 → 목차의 좌표 제목 → 문서 좌표 · 하나로 풀리는 골격 노드만(쓰기 0) · 없으면 None."""
        from core.build import outline as OL
        hints = []
        if not low and piece.get("process_group"):
            hints.append(piece["process_group"])
        for h in OL.chain(outline, piece.get("source_locator")) if outline else []:
            if h.get("coord") and h.get("target"):
                hints.append(h["target"]["name"])
                break
        if self.b.doc_coord:
            hints.append(self.b.doc_coord)
        for s in hints:
            if norm(s) == norm(surface):
                continue
            hit = look(self.b, s)
            if len(hit) == 1:
                return self.concept(hit[0])
        return None

    def concept(self, nid):
        """극성 인스턴스면 그 개념 — 단은 개념에서 센다(인스턴스는 깊이에 들지 않는다)."""
        return self.pm.get(nid, nid) if _instance(self.eb.g.get(nid)) else nid

    def tier(self, up):
        """`(단, 보류 사유)` — 부모 바로 아래 단 · 부모 미정이면 `(None, None)` · 맨 아래 단보다 깊으면 「골격 아래 새 단」."""
        from core.state.skeleton import TIER_BY_DEPTH, TIER_DEEP
        if up is None:
            return None, None
        d = _depth(self.eb.g, self.pm, up)
        if d is None:
            return None, None
        if d + 1 > self.bottom:
            return None, HOLD_DEEP
        return TIER_BY_DEPTH.get(d + 1, TIER_DEEP), None


def _occurrences(b, env):
    """`[(표기, prov, 조각, 저해상도)]` — 조각 좌표(목록이면 원소마다) · 표의 공정 칸이 비고 그룹만 있으면 그룹(저해상도)."""
    from parser.normalizer import coord_refs
    table = env.get("payload_kind") == "table"
    out = []
    for p in (env.get("records") if table else env.get("chunks")) or []:
        loc = p.get("source_locator")
        prov = f"{b.doc_id}#{loc}" if loc else None
        refs = coord_refs(p.get("process_ref"))
        if refs:
            out += [(s, prov, p, False) for s in refs]
        elif table and p.get("process_group"):
            out.append((p["process_group"], prov, p, True))
    return out


def plan(b, env, outline=None):
    """**한 문서의 잠정 골격 노드 계획**(쓰기 0) — `[{surface, provs, rows, up, tier, answer, near, act, node, canonical, hold}]`.
    `act`: new(세운다) · use(있는 잠정 노드 · 다른 행이 부모를 말하면 `fill`) · join(이 문서에서 앞에 세울 것) · hold(보류 사유).
    좌표 화면(`[3/7]`)과 구축 앞 패스(`settle`)가 이 함수 하나다."""
    from core.build.build_coord import coord_judged, coord_unjudged
    from parser.namefold import key
    cx, groups = _Ctx(b), {}
    for s, prov, p, low in _occurrences(b, env):
        if look(b, s) and any(not (cx.eb.g.get(n) or {}).get(PROVISIONAL) for n in look(b, s)):
            continue                                              # 골격(Tier1)이 답한다 — 지금 그대로
        if coord_unjudged(p, s):
            continue                                              # 판단을 받지 못했다 — 보류 그대로
        up = cx.up_of(p, s, low, outline)
        g = groups.setdefault((key(s), up), {"surface": s, "provs": [], "up": up, "judge": coord_judged(p, s)})
        g["provs"].append(prov)
    return [_decide(cx, g) for g in groups.values()]


def _decide(cx, g):
    s, up = g["surface"], g["up"]
    v = g["judge"] or {}
    e = {"surface": s, "provs": g["provs"], "rows": len(g["provs"]), "up": up, "up_name": cx.name(up),
         "answer": "uncertain" if v.get("type") == "uncertain" else "new",
         "near": list(v.get("candidates") or [])[:NEAR], "act": None, "node": None, "canonical": None, "hold": None,
         "confidence": v.get("confidence")}
    have = [n for n in look(cx.b, s) if (cx.eb.g.get(n) or {}).get(PROVISIONAL)]
    fit = [n for n in have if _same_stem(cx.pm, cx.pm.get(n), up)]
    if len(fit) > 1 and up is not None:
        fit = [n for n in fit if cx.pm.get(n) == up] or fit
    if len(fit) == 1:
        e.update(act="use", node=fit[0])
        if up is not None and cx.pm.get(fit[0]) is None:          # 부모 미정 노드에 부모를 말하는 행 — 채운다
            t, why = cx.tier(up)
            if not why:                            # 채우지 못하는 자리(골격 아래 새 단)면 그 노드는 부모 미정 그대로 좌표다
                e.update(act="fill", tier=t)
        return e
    if len(fit) > 1:
        from core.build.build_coord import HOLD_AMBIGUOUS
        e.update(act="hold", hold=HOLD_AMBIGUOUS)
        return e
    from parser.namefold import key
    mine = [x for x in cx.planned if key(x["surface"]) == key(s) and _same_stem(cx.pm, x["up"], up)]
    if mine:
        x = mine[0]
        if x["up"] is None and up is not None:     # 부모 미정으로 세울 것에 부모를 말하는 행 — 채운다
            t, why = cx.tier(up)
            if not why:
                x.update(up=up, up_name=cx.name(up), tier=t)
        x["rows"] += e["rows"]
        e.update(act="join", node=x)
        return e
    e["tier"], e["hold"] = cx.tier(up)
    if e["hold"]:
        e["act"] = "hold"
        return e
    canon = s if s not in cx.names else (f"{cx.name(up)}::{s}" if up is not None else None)
    if canon is None or canon in cx.names:
        e.update(act="hold", hold=HOLD_NAME)
        return e
    ok, why = cx.gate(s, up)                       # 문(B196 ①) — 세우는 것은 사람의 「새로」뿐
    if not ok:
        e.update(act="hold", hold=why, canonical=canon)
        return e
    cx.names.add(canon)
    e.update(act="new", canonical=canon)
    cx.planned.append(e)
    return e


# ---------------------------------------------------------------- 쓰기 — 세우는 손 하나
def make(b, surface, prov, *, answer, canonical=None, near=None, up=None, tier=None):
    """**잠정 골격 노드를 세운다**(B182 ②) — 노드(home 층 · auto + 표시) · 사전 · 부모 엣지(골격 자식 관계 · 출처 그 문서) · 큐
    (다르다 `auto_node` · 애매 `uncertain_match` + 합칠 후보) · 이 문서의 세운 기록(`b.made` — 대장의 `made` 칸). 돌려주는 것은 id."""
    from core.build.build import POLARITY_NONE
    from core.state.bootstrap import load_config
    eb = b.for_category(_coord())
    canonical = canonical or surface
    mark = {"answer": answer, **({"near": list(near)} if near else {})}
    nid = eb.g.add_node(canonical, _coord(), "auto", provenance=[prov] if prov else [b.doc_id],
                        tier=tier, polarity=POLARITY_NONE, **{PROVISIONAL: mark})
    eb._register(surface, nid, prov or b.doc_id, key=canonical)
    if up is not None:
        child = ((load_config(eb.layer).get("skeleton") or {}).get("relations") or {}).get("child")
        eb.g.add_edge(nid, child, up, "auto", provenance=[prov or b.doc_id])
    kind = "auto_node" if answer == "new" else "uncertain_match"
    store.enqueue(kind, f"잠정 골격 노드{'' if answer == 'new' else ' — 판단 애매 · 합칠 후보'}: {canonical} ({_coord()})",
                  b.doc_id, {"node_id": nid, "canonical": canonical, "surface": surface, "provenance": prov or b.doc_id,
                             "layer": eb.layer, PROVISIONAL: True, "parent": (eb.g.get(up) or {}).get("canonical"),
                             **({"nearest": {"canonical": near[0]}} if near else {})})
    for x in (b, eb):
        x._pmaps.clear()                         # 골격이 자랐다 — 부모 표를 다시 센다
    b.made[nid] = {"answer": answer, "parent": (eb.g.get(up) or {}).get("canonical"), "first": prov, "queue": kind}
    return nid


def from_entity(b, surface, prov, verdict, nearest, coord=None):
    """**산문 · 제목의 좌표 골격 카테고리 개체**(B182 ① — `Builder._skeleton_miss`) — 판정이 다르다 · 애매면 잠정 노드(부모 = 그
    자리의 좌표 · 단은 그 바로 아래) · `(id, 보류 사유)`. 같은 이름의 잠정 노드는 판정 후보에 이미 들었다(같다면 여기 오지 않는다)."""
    cx = _Ctx(b)
    up = coord[0] if coord and coord[0] and is_skeleton(cx.eb.g.get(coord[0])) else None
    up = cx.concept(up) if up else None
    tier, why = cx.tier(up)
    if why:
        return None, why
    canon = surface if surface not in cx.names else (f"{cx.name(up)}::{surface}" if up is not None else None)
    if canon is None or canon in cx.names:
        return None, HOLD_NAME
    ok, why = cx.gate(surface, up)                 # 문(B196 ①) — 표 · 산문 · 제목 · PPT 같은 판단
    if not ok:
        b.coord_gate[(prov, surface)] = {"parent": cx.name(up), "answer": verdict,
                                         "near": [nearest["canonical"]] if (nearest or {}).get("canonical") else []}
        return None, why
    near = [nearest["canonical"]] if verdict == "uncertain" and (nearest or {}).get("canonical") else None
    return make(b, surface, prov, answer=verdict, canonical=canon, near=near, up=up, tier=tier), None


def seed_at(graphs, cfgs, dic, did, surface, parent, prov, gi=None):
    """**재연결의 「새로」**(B196 ① — 인입 뒤 처분) — 사람이 「새로」를 정한 표기의 잠정 노드를 세운다(세우는 손 `make` 그대로 ·
    부모 = 그 자리 이름의 골격 노드 · 단은 그 바로 아래) · `(id, 층, 그래프)` · 세우지 못하면 `(None, None, None)`(쓰기 0)."""
    from core.build.build import Builder
    from core.state.bootstrap import coord_layer
    lay = coord_layer()
    g = graphs.get(lay)
    if g is None:
        return None, None, None
    b = Builder(g, cfgs[lay], None, did, lay)
    b.dict = dic
    cx = _Ctx(b)
    up = next((nid for nid, n in g.nodes.items() if n.get("canonical") == parent and is_live(n) and is_skeleton(n)), None)
    if (parent is not None and up is None) or not cx.gate(surface, up)[0]:
        return None, None, None
    up = cx.concept(up) if up else None
    tier, why = cx.tier(up)
    canon = surface if surface not in cx.names else (f"{cx.name(up)}::{surface}" if up is not None else None)
    if why or canon is None or canon in cx.names:
        return None, None, None
    nid = make(b, surface, prov, answer=(gi or {}).get("answer") or "new", canonical=canon,
               near=(gi or {}).get("near") or None, up=up, tier=tier)
    return nid, lay, g


def fill(b, nid, up, tier, prov):
    """부모 미정 잠정 노드에 부모를 채운다(따로 세우지 않는다) — 부모 엣지 · 단."""
    from core.state.bootstrap import load_config
    eb = b.for_category(_coord())
    child = ((load_config(eb.layer).get("skeleton") or {}).get("relations") or {}).get("child")
    eb.g.add_edge(nid, child, up, "auto", provenance=[prov or b.doc_id])
    eb.g.get(nid)["tier"] = tier
    for x in (b, eb):
        x._pmaps.clear()


def settle(b, env, outline=None):
    """**구축 앞 패스**(B182 ①) — 이 문서의 좌표 골격 칸을 계획대로 세운다 · 행마다 그 자리(`b.coord_at[(prov, 표기)]`)와 보류
    사유(`b.coord_hold[(prov, 표기)]` · 표기 키)를 남긴다 — 뒤의 좌표 해소(`resolve_anchor`)가 그것을 먼저 본다(같은 이름 · 다른 줄기)."""
    from parser.namefold import key
    made = {}
    entries = plan(b, env, outline)
    for e in entries:
        if e["act"] == "hold":                       # 행마다(같은 이름의 다른 행이 섰어도 이 행은 보류 · 사전보다 먼저) + 표기 키(사유 표시)
            b.coord_hold[key(e["surface"])] = e["hold"]
            b.coord_hold.update({(prov, e["surface"]): e["hold"] for prov in e["provs"] if prov})
            if e["hold"] in GATED:                   # 문에 걸린 행 — 보류 재료에 자리 · 판단을 싣는다(검토 · 재연결이 읽는다)
                b.coord_gate.update({(prov, e["surface"]): gate_info(e) for prov in e["provs"] if prov})
            continue
        if e["act"] == "new":
            made[id(e)] = make(b, e["surface"], e["provs"][0], answer=e["answer"], canonical=e["canonical"],
                               near=e["near"], up=e["up"], tier=e["tier"])
            nid = made[id(e)]
        elif e["act"] == "join":
            nid = made[id(e["node"])]
        else:
            nid = e["node"]
            if e["act"] == "fill":
                fill(b, nid, e["up"], e["tier"], e["provs"][0])
        eb = b.for_category(_coord())
        n = eb.g.get(nid)
        for prov in e["provs"]:
            if prov:
                b.coord_at[(prov, e["surface"])] = nid
                if prov not in n["provenance"]:      # 그 행이 근거다 — 재인입이 걷은 출처를 되살린다(개체 매칭과 같은 결)
                    n["provenance"].append(prov)
        _restate_parent(eb, nid, e["up"], e["provs"])
    from core.build import coord_scan
    b.pair_rows = coord_scan.gate(env, b)            # 쌍 어긋남의 문(B196 ②) — 잠정 노드가 선 뒤 같은 해소로 대조한다
    return b.made


def _restate_parent(eb, nid, up, provs):
    """그 부모를 말한 행은 부모 엣지의 근거다 — 엣지가 그 부모일 때만 출처를 더한다(재인입이 걷은 출처를 되살린다 · 다른 부모는 0)."""
    from core.state.bootstrap import load_config
    if up is None:
        return
    child = ((load_config(eb.layer).get("skeleton") or {}).get("relations") or {}).get("child")
    if eb.g.edge(nid, child, up) is not None:
        eb.g.add_edge(nid, child, up, "auto", provenance=[p for p in provs if p])


def gate_info(e):
    """문에 걸린 계획 줄 → 보류 재료의 `gate` 칸 — 들어온 자리(부모 이름) · 판단 · 후보(둘까지)."""
    return {"parent": e.get("up_name"), "answer": e.get("answer"), "near": list(e.get("near") or [])}


def preview(env, outline=None):
    """좌표 화면(`[3/7]` · `--step` 표)의 계획 — 쓰기 0 · 그 문서 좌표로(구축 앞 패스와 같은 함수)."""
    from core.build.build import Builder
    from core.state.bootstrap import coord_layer, load_config, open_graph
    lay = coord_layer()
    b = Builder(open_graph(lay), load_config(lay), None, env.get("doc_id"), lay)
    b.doc_coord = env.get("doc_coord")
    return plan(b, env, outline)


def preview_text(entries):
    """`잠정 n종(부모 미정 m)` · 보류가 있으면 `· 보류 k(사유)` — 좌표 단계 줄의 칸(B182 ③)."""
    new = [e for e in entries if e["act"] == "new"]
    held = [e for e in entries if e["act"] == "hold"]
    why = sorted({e["hold"] for e in held})
    return (f"잠정 {len(new):,}종(부모 미정 {sum(1 for e in new if e['up'] is None):,})"
            + (f" · 보류 {len(held):,}({' · '.join(why)})" if held else ""))


# ---------------------------------------------------------------- 대장 · 보이기
def cells(b, nid, g, prov):
    """대장 anchor 행의 칸 — 경로(`provisional` · `skeleton` · `none`) · 이 행에서 세웠으면 `made`(답 · 부모 · 큐)."""
    n = (g.get(nid) if (g is not None and nid) else None) or {}
    out = {"path": "provisional" if n.get(PROVISIONAL) else ("skeleton" if nid else "none")}
    m = b.made.get(nid)
    if m and m["first"] == prov:
        out["made"] = {k: m[k] for k in ("answer", "parent", "queue")}
    return out


def counts(rows):
    """「잠정 골격 노드」 칸(B182 ③) — 대장 행에서(새 계산 0): 새로 · 다르다 · 애매 · 부모 미정 · 한 번만 나온 것."""
    made = [r for r in rows or [] if r.get("made")]
    if not made:
        return None
    seen = {}
    for r in rows:
        if r.get("node_id") and r.get("role") in ("anchor", "entity", "heading"):
            seen[r["node_id"]] = seen.get(r["node_id"], 0) + 1
    return {"새로": len(made), "다르다": sum(1 for r in made if r["made"]["answer"] == "new"),
            "애매": sum(1 for r in made if r["made"]["answer"] == "uncertain"),
            "부모 미정": sum(1 for r in made if not r["made"].get("parent")),
            "한 번": sum(1 for r in made if seen.get(r["node_id"], 0) <= 1)}


def line(c):
    """`잠정 골격 노드 — 새로 n(다르다 a · 애매 b) · 부모 미정 m · 한 번만 나온 것 k` · 없으면 None."""
    if not c:
        return None
    return (f"잠정 골격 노드 — 새로 {c['새로']:,}(다르다 {c['다르다']:,} · 애매 {c['애매']:,}) · 부모 미정 {c['부모 미정']:,} · "
            f"한 번만 나온 것 {c['한 번']:,}")


def about(g, n):
    """`show node`의 잠정 칸 — `{answer, near, parent, tier}`(부모는 골격 자식 관계 엣지에서) · 잠정이 아니면 None."""
    from core.state.bootstrap import load_config
    if not (n or {}).get(PROVISIONAL):
        return None
    child = ((load_config(g.layer).get("skeleton") or {}).get("relations") or {}).get("child")
    up = _parents(g, child).get(n["id"])
    return {"answer": n[PROVISIONAL].get("answer"), "near": n[PROVISIONAL].get("near") or [],
            "parent": (g.get(up) or {}).get("canonical"), "tier": n.get("tier")}


def listing(layer):
    """**파서의 좌표 태깅 목록에 더하는 잠정 노드**(B182 ② — 골격 스냅샷과 같은 꼴 · 별칭은 노드의 별칭) — core가 주입한다."""
    from core.state.bootstrap import coord_layer, load_config, open_graph
    if layer != coord_layer():
        return []
    g = open_graph(layer)
    child = ((load_config(layer).get("skeleton") or {}).get("relations") or {}).get("child")
    pm = _parents(g, child)
    out = []
    for nid, n in g.nodes.items():
        if is_live(n) and n.get(PROVISIONAL) and n.get("category") == _coord():
            out.append({"id": nid, "canonical": n["canonical"], "category": n["category"], "tier": n.get("tier"),
                        "polarity": n.get("polarity"), "parent": (g.get(pm.get(nid)) or {}).get("canonical"),
                        "aliases": sorted({a["surface"] for a in n.get("aliases") or [] if a.get("surface")}),
                        PROVISIONAL: True, "answer": n[PROVISIONAL].get("answer"), "near": n[PROVISIONAL].get("near") or [],
                        "doc": str((n.get("provenance") or [""])[0]).split("#", 1)[0] or None})
    return sorted(out, key=lambda e: e["canonical"])
