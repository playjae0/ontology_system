# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **골격 단의 문**(B197 ① · 결정 A″) — 겸 값은 골격 노드로만 선다(사람이 정하기 전에는 보류).

**겸 단에 선다**의 뜻(config에서만 — 코드에 층 어휘 0): 값의 카테고리를 좌표 골격 카테고리가 겸하고(공통 `also` — `catalog.hosts`)
값의 자리(좌표)가 골격 노드이며 그 아래 골격 자식이 있고 그 자식의 단이 겸 단 목록에 든다. 자리가 그 줄기의 골격 맨 아래 단이면
문 밖이다(지금처럼 자동).

| 무엇 | 자리 |
|---|---|
| 문에 드는가 — `{x, g, up, kids, under}` | `place` |
| 판정 앞 — 사전이 그 아래 골격 하나로 풀림 · 사람 답(새로 · 올림 · drop) · 앞 단계의 판단(`_PRE`) | `pre` |
| 판정 뒤 — 같다가 아니면 세우지 않고 보류(`orphan_anchor` · 사유 `HOLD_ALSO`) | `miss` · `hold` |
| 딸린 값(소속 · 제목 사슬 · 같은 행)을 그 보류에 함께 | `follow` · `held_up` · `held_name` |
| 판정 전 처분 자리의 줄([3/8] 제목 · [5/8] 본문 — 같은 함수) | `scan` |

다섯 길(`resolve_at_home`)이 `Builder.resolve_entity`의 신규 판정 갈래 한 자리에서 이 함수를 지난다 — 제목 · 본문 · 표 · 재연결 ·
소속 대상이 같은 판단이다. 겸 선언이 없으면 `place`가 늘 None이다(지금 그대로).
"""
from __future__ import annotations

from core.state import store
from core.state.ids import norm
from core.state.status import is_live, is_skeleton

#: 보류 사유 — 겸 단 값이 골격과 맞지 않았다(B197 ①)
HOLD_ALSO = "사람 확인 전 골격 단 값"
#: 판정 전 처분 자리가 낸 판단 — `(문서, 표기 키, 위 공정 이름)` → `(분기, node_id, 점수, 판정 dict)` · 구축이 같은 호출을 다시 하지 않는다
_PRE = {}


def _coord():
    from core.state.bootstrap import COORD_CATEGORY
    return COORD_CATEGORY


def tiers(category):
    """그 카테고리를 좌표 골격 카테고리가 겸하는 단 목록 — 없으면 `()`(겸 선언 없음 · 골격 카테고리 자신)."""
    from core.state import catalog
    if not category or category == _coord():
        return ()
    try:
        return tuple(catalog.hosts(category).get(_coord()) or ())
    except catalog.CatalogError:
        return ()


def _kids(b, g):
    """`{부모 canonical: [골격 개념 자식 id]}` — 빌더의 부모 표 그릇에(골격이 자라면 같이 비워진다 — `provisional.make`)."""
    k = (id(g), "also_kids")
    if k not in b._pmaps:
        pm = b._parent_map(g, _coord())
        by = {}
        for nid, n in g.nodes.items():
            if is_live(n) and n.get("category") == _coord() and is_skeleton(n):
                up = pm.get(n["canonical"])
                if up:
                    by.setdefault(up, []).append(nid)
        b._pmaps[k] = by
    return b._pmaps[k]


def place(b, category, coord):
    """**문에 드는 자리인가**(쓰기 0) — `{x: 좌표 id, g, up: 위 공정 이름, kids: 겸 단 골격 자식, under: 그 아래 골격 전부}` 또는 None."""
    ts = tiers(category)
    ref, g = coord or (None, None)
    n = g.get(ref) if (ts and ref and g is not None) else None
    if not (n and n.get("category") == _coord() and is_skeleton(n)):
        return None
    by = _kids(b, g)
    up = n["canonical"]
    kids = [k for k in by.get(up, ()) if (g.get(k) or {}).get("tier") in ts]
    if not kids:
        return None
    under, todo = set(kids), list(kids)
    while todo:
        for k in by.get(g.get(todo.pop())["canonical"], ()):
            if k not in under:
                under.add(k)
                todo.append(k)
    return {"x": ref, "g": g, "up": up, "kids": kids, "under": under}


def _book(b):
    if b.also.get("book") is None:
        from core.state import provisional_hand as PH
        b.also["book"] = PH.decisions()
    return b.also["book"]


def _land(b, surface, prov, nid, g, path, verdict="match", **extra):
    """골격 노드에 선다 — 버퍼 · 사실(`last`) · 출처(그 노드의 provenance)."""
    n = g.get(nid)
    if prov and prov not in n.setdefault("provenance", []):
        n["provenance"].append(prov)
    b.buffer[norm(surface)] = nid
    b.also["landed"][norm(surface)] = nid
    b.last = {"canonical": n["canonical"], "verdict": verdict, "path": path, "confidence": 1.0,
              "layer": getattr(g, "layer", b.layer), "queue_kind": None, "candidates_n": 0, "node_id": nid,
              "llm": {"calls": 0, "in_tokens": 0, "out_tokens": 0}, **extra}
    return nid


def pre(b, surface, category, prov, coord):
    """**판정 앞**(B197 ①) — `(True, node_id 또는 None)`(끝남) · `place`의 답(판정한 뒤 `miss`) · None(문 밖 — 지금 그대로).

    순서: ①사전이 그 아래 골격 하나로 풀린다(합침 · 승격의 별칭 — 같은 끝) ②사람 답 — 올림(위 공정) · 새로(잠정 골격 노드 —
    세우는 손 `provisional.from_entity`) · drop(세우지 않는다 · 딸린 값도) ③앞 단계([3/8] · [5/8])가 낸 판단."""
    from core.state import provisional_hand as PH
    p = place(b, category, coord)
    if p is None:
        return None
    hit = [nid for nid in dict.fromkeys(b.dict.lookup(surface)) if nid in p["under"]]
    if len(hit) == 1:
        return True, _land(b, surface, prov, hit[0], p["g"], "skeleton")
    d = PH.decided(_book(b), surface, p["up"])
    if d == PH.RAISED:
        return True, _land(b, surface, prov, p["x"], p["g"], "skeleton", raised=p["up"])
    if d == PH.SEEDED:
        from core.build import provisional
        cb = b.for_category(_coord())
        nid, why = provisional.from_entity(cb, surface, prov, "new", None, coord=(p["x"], p["g"]))
        if nid:
            m = cb.made[nid]
            return True, _land(b, surface, prov, nid, cb.g, "provisional", verdict="new", queue_kind=m["queue"],
                               made={k: m[k] for k in ("answer", "parent", "queue")})
        return True, hold(b, surface, category, prov, p, why, "new", None)
    if d == PH.DROPPED:
        from core.build.provisional import HOLD_DROP
        return True, hold(b, surface, category, prov, p, HOLD_DROP, None, None)
    got = _PRE.get((b.doc_id, _k(surface), p["up"]))
    if got is not None:
        verdict, nid, _conf, v = got
        if same(p, verdict, nid) and p["g"].get(nid) is not None:
            return True, _land(b, surface, prov, nid, p["g"], v.get("path") or "none")
        if not same(p, verdict, nid):
            return True, miss(b, surface, category, prov, p, verdict, v, nid)
    return p


def same(p, verdict, nid):
    """판정이 「같다」로 셀 끝인가 — 그 아래 골격(겸 단) 또는 골격 밖 노드만. **위 공정 자신 · 줄기 밖 골격에 붙는 판정은 같다가
    아니다**(가결정 — 그 자리는 자기 좌표 규칙(사전)과 사람의 올림이 정한다 · 애매로 문에)."""
    if verdict != "match":
        return False
    n = p["g"].get(nid)
    return nid in p["under"] or not (n and n.get("category") == _coord() and is_skeleton(n))


def miss(b, surface, category, prov, p, verdict, v, nid=None):
    """**판정 뒤 — 같다가 아니다**(다르다 · 애매 · 위 공정 자신) → 세우지 않고 문(사유 `HOLD_ALSO`) · `None`."""
    near = _near(p, (v or {}).get("nearest"))
    if verdict == "match":                         # 위 공정 자신 · 줄기 밖 골격 — 애매로(후보는 그 아래 골격만)
        verdict, near = "uncertain", None
    return hold(b, surface, category, prov, p, HOLD_ALSO, verdict, near)


def _near(p, nearest):
    """판단이 낸 가장 가까운 후보 — 그 위 공정 아래 골격일 때만(합칠 후보는 그 아래 골격 — 결정 A″)."""
    c = (nearest or {}).get("canonical")
    return nearest if c and any((p["g"].get(n) or {}).get("canonical") == c for n in p["under"]) else None


def _k(s):
    from parser.namefold import key
    return key(s or "")


def hold(b, surface, category, prov, p, why, verdict, nearest):
    """**보류 하나**(B196의 보류 꼴 — `orphan_anchor` · 카테고리는 좌표 골격 카테고리 · `also` = 값의 카테고리 · `gate` = 위 공정 ·
    판단 · 후보) · 표의 행이면 그 행의 말미 적재(`b.also["defer"]` — 같은 행의 드롭 · 보류 값이 함께 실린다) · drop이면 큐 0."""
    from core.build.provisional import HOLD_DROP
    near = [nearest["canonical"]] if (nearest or {}).get("canonical") else []
    gi = {"parent": p["up"], "answer": verdict, "near": near}
    pl = {"surface": surface, "category": _coord(), "also": category, "provenance": prov, "role": "entity",
          "layer": b.for_category(_coord()).layer, "gate": gi}
    reason = (f"골격 단 값 '{surface}'({category} · {p['up']} 아래)가 골격과 맞지 않아 세우지 않았다(사람 확인 전) — "
              "합침 · 새로 · 승격 · 올림 · drop")
    b.also["held"][norm(surface)] = {"why": why, "pl": pl, "reason": reason}
    if why != HOLD_DROP:
        if b.also.get("defer") is not None:
            pl["field"] = b.also.get("field")
            b.also["defer"].append({"payload": pl, "reason": reason})
        else:
            store.enqueue_rows("orphan_anchor", reason, b.doc_id, norm(surface), pl,
                               locator=(prov or "").split("#")[-1] or None)
    b.last = {"canonical": surface, "verdict": "orphan", "path": "none", "confidence": 0.0, "layer": b.layer,
              "queue_kind": None if why == HOLD_DROP else "orphan_anchor", "candidates_n": 0, "node_id": None,
              "hold": why, "answer": verdict, "category": category, "also": True,
              "llm": (b.last or {}).get("llm") or {"calls": 0, "in_tokens": 0, "out_tokens": 0}}
    return None


# ---------------------------------------------------------------- 딸린 값
def held_name(b, name):
    """그 이름이 이 문서에서 문에 걸렸나 — 보류 기록(`hold`) 또는 None."""
    return b.also["held"].get(norm(name or "")) if name else None


def held_up(b, outline, locator=None, heading=None):
    """그 조각(또는 제목 — 그 위 제목들) 위 제목 중 문에 걸린 가장 가까운 것의 이름 — 없으면 None(제목 사슬 · B197 ①)."""
    from core.build import outline as OL
    heads = b.also["heads"]
    if not heads:
        return None
    chain = OL.chain_of(outline, heading.get("parent")) if heading is not None else OL.chain(outline, locator)
    return next((heads[h["id"]] for h in chain if h["id"] in heads), None)


def follow(b, name, e, prov, value=None):
    """딸린 값 하나를 그 보류에 함께(`dropped_entities` — 재연결이 정해진 노드 아래 인입과 같은 함수로 세운다 · 값은 `pending_attrs`) ·
    drop이면 넣지 않는다. 돌려주는 것은 보류 기록."""
    from core.build.provisional import HOLD_DROP
    h = held_name(b, name)
    if h is None or h["why"] == HOLD_DROP:
        return h
    item = {"surface": e["surface"], "category": e["category"], "target_layer": b.home_of(e["category"])}
    pl = dict(h["pl"], provenance=prov, follow=True, dropped_entities=[item])
    pl.pop("field", None)
    if value:
        pl["pending_attrs"] = [dict(value, attach_to_field=e["surface"], provenance=prov)]
    store.enqueue_rows("orphan_anchor", h["reason"], b.doc_id, norm(h["pl"]["surface"]), pl,
                       locator=(prov or "").split("#")[-1] or None)
    return h


def ledger_row(b, loc, e, h, role="entity"):
    """딸린 값의 대장 행 — 판정에 오르지 않았다(보류 · 그 보류의 사유)."""
    if b.ledger is not None:
        from core.build.provisional import HOLD_DROP
        b.ledger.add(locator=loc, field=e.get("category"), role=role, surface=e.get("surface"), layer=b.layer,
                     path="none", verdict="orphan", queue_kind=None if h["why"] == HOLD_DROP else "orphan_anchor",
                     hold=h["why"], belongs_to=h["pl"]["surface"])


# ---------------------------------------------------------------- 판정 전 처분 자리
def scan(b, items):
    """**판정 전 처분 자리의 줄**(B197 ② — [3/8] 제목 · [5/8] 본문이 같은 함수) — `items = [{surface, category, coord, prov, place?}]`.

    문에 드는 값마다 같은지 판단(D)을 이 자리에서 한 번(판정 함수 그대로 · 결과는 `_PRE` — 구축이 다시 부르지 않는다) ·
    사전이 풀거나 사람 답이 있으면 줄 0. 돌려주는 줄 `{kind: gate, also, surface, up_name, rows, answer, near, confidence, place}`."""
    from core.state import provisional_hand as PH
    rows = {}
    for it in items:
        p = place(b, it["category"], it.get("coord"))
        if p is None:
            continue
        s = it["surface"]
        if [n for n in b.dict.lookup(s) if n in p["under"]] or PH.decided(_book(b), s, p["up"]):
            continue
        kk = (_k(s), p["up"])
        if kk in rows:
            rows[kk]["rows"] += 1
            continue
        k3 = (b.doc_id,) + kk
        if k3 not in _PRE:
            _PRE[k3] = _judge(b, s, it["category"], p)
        verdict, nid, conf, v = _PRE[k3]
        if same(p, verdict, nid):
            continue
        near = None if verdict == "match" else (_near(p, v.get("nearest")) or {}).get("canonical")
        rows[kk] = {"kind": "gate", "also": it["category"], "surface": s, "up_name": p["up"], "rows": 1,
                    "answer": "uncertain" if verdict == "match" else verdict, "confidence": conf,
                    "place": it.get("place") or "", "near": [near] if near else []}
    return list(rows.values())


def _judge(b, surface, category, p):
    """같은지 판단 하나 — 구축과 같은 판정 함수(`Builder._judge` 앞의 이름 · 관문 · 판정)를 읽기로만(쓰기 0)."""
    from core import matcher
    from core.build import scope_path
    from core.build.build import entity_key
    eb = b.for_category(category)
    canonical, scoped, _sc = entity_key(surface, category, eb.cfg, parent_canonical=p["up"])
    pl = scope_path.place(eb, category, (p["x"], p["g"]), None, surface, p["up"])
    return matcher.resolve(canonical, category, eb.layer, eb.g, eb.dict, scoped=scoped, parent=p["up"], place=pl)


def clear(doc_id=None):
    """앞 단계 판단을 비운다 — 문서 끝(같은 실행의 다음 문서가 지난 판단을 읽지 않게)."""
    for k in [k for k in _PRE if doc_id is None or k[0] == doc_id]:
        _PRE.pop(k, None)
