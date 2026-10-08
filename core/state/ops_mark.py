# -*- coding: utf-8 -*-
"""칸 0.3 — **모양을 바꾸지 않는 사람 판단** — 지위(확정) · 표기(별칭) · 사람이 지운 엣지 · 문서 단위 확인.

`core/state/ops.py`에서 떼어냈다(B106 ④ — §7 파일 상한 800행 · 이름 기록이 연산마다 한 줄씩 늘었다).
I축 4연산(그래프의 **모양**을 바꾸는 것)과 갈래가 다르다 — 여기 것은 모양은 그대로이고 판정의 지위나
표기가 바뀐다. 이름은 `ops`에서도 그대로 보인다(`ops.confirm` · `ops.alias` · `ops.delete_edge` · 호출 계약 유지).
기록은 노드마다 **이름으로** 남는다(B106 ③ — `ops replay`가 그 이름으로 되살린다).
"""
from __future__ import annotations

from core.state import oplog, store
from core.build.build import Builder
from core.dictionary import Dictionary
from core.state.ids import norm
from core.state.status import is_live
from core.state.world import World
from core.build.naming import scope_canonical


def _ops():
    """공통 손(`OpRefused` · `_open` · `_target` · `_cfg` · `log_op`)은 `ops`가 갖는다 — 부를 때 읽는다(순환 0)."""
    from core.state import ops
    return ops


def confirm(layer, nid, actor, reason="", dry_run=False):
    """**자동 노드의 사람 확정** — `status: auto → confirmed` + 큐 종결 (B73 ④ · H12).

    I축 4연산(그래프의 **모양**을 바꾸는 것 — 문서 1 L5)에 다섯째를 더하는 것이
    아니다: 모양은 그대로이고 **판정의 지위**가 바뀐다. 그래서 미리보기(연쇄
    계산)가 필요 없고, 되돌리는 것은 `obsolete`·`merge`다.

    이것이 없어서 `auto_node`·`uncertain_match` 큐가 **종결되지 않았다**(감사 H12 —
    `resolve_item` 호출 0 · `confirmed` 생산자 0): 사람이 「맞다」고 판단할 자리가
    코드에 없었고, 그래서 auto 노드는 영원히 auto였다. auto는 다음 판정의 후보에서
    보수적으로 다뤄지므로(B73 ③) 확정은 **판정 품질의 손잡이**이기도 하다.

    거부 셋: 행위자 없음 · 대상 없음(툼스톤·타층 id 포함) · 이미 seed·confirmed.
    기록에 **닫은 큐**(kind · 결정)를 적는다(B106 ③ — 재생이 같은 결정으로 닫는다).
    """
    ops = _ops()
    if not actor:
        raise ops.OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    _w, g, layer = ops._open(layer, nid)
    node = ops._target(g, nid)                   # 툼스톤·없는 id는 여기서 거부된다
    if node.get("status") in ("seed", "confirmed"):
        raise ops.OpRefused(f"이미 확정된 노드다 — status={node.get('status')}")
    pv = {"op": "confirm", "layer": layer, "target": nid,
          "canonical": node.get("canonical"), "from": node.get("status"),
          "to": "confirmed",
          "queue": ["auto_node", "uncertain_match"]}
    if dry_run:
        return pv
    node["status"] = "confirmed"
    node["confirmed_by"], node["confirmed_at"] = actor, store._now()
    g.save()
    at = store._now()
    closed = []
    for kind in ("auto_node", "uncertain_match"):
        # **큐를 내리지 않고 판단을 기록한다**(§7.2) — 재인입 회수가 그것을 보존한다.
        if store.resolve_item(kind, lambda pl, _n=nid: pl.get("node_id") == _n,
                              actor=actor, decision="confirmed", at=at, note=reason):
            closed.append({"kind": kind, "decision": "confirmed"})
    ops.log_op("I5:confirm", actor, [nid], reason, {"from": pv["from"], "queue": closed},
               {"node": oplog.name(node)})
    return pv


def doc_auto(doc_id):
    """**그 문서 실행이 만든 auto 노드**(B106 ④) — `(확인할 것 [(층, id, canonical, 카테고리)], 불확실 수)`.

    판정은 그 문서 대장의 행이 노드를 **만들었나**다(`new`·`uncertain` 행의 `node_id` — B101 「같은 문서 실행이
    만든 auto」와 같은 기준 · `ledger.made_by`와 같은 열) · 지금 살아 있고 `auto`인 것만. 불확실이 만든 노드는
    넣지 않는다 — 고르는 일이라 `ops review`의 몫이다(수만 센다). 대장이 없으면 `(None, 0)`."""
    from core.build import ledger
    data = ledger.read(doc_id)
    if data is None:
        return None, 0
    w = World()
    out, unc, seen = [], 0, set()
    for r in data.get("rows") or []:
        nid = r.get("node_id")
        if not nid or nid in seen or r.get("verdict") not in ("new", "uncertain"):
            continue
        seen.add(nid)
        n = w.get(nid)
        if not n or not is_live(n) or n.get("status") != "auto":
            continue
        if r["verdict"] == "uncertain":
            unc += 1
            continue
        out.append((w.home(nid), nid, n["canonical"], n["category"]))
    return out, unc


def confirm_doc(doc_id, actor, reason="", dry_run=False):
    """**문서 단위 일괄 확인**(B106 ④) — 그 문서 실행이 만든 auto 노드를 한 번에 `confirmed`(손은 `confirm`
    그대로 — 큐 `resolution` · 기록은 노드마다 이름으로). 돌려주는 것은 계획 `{doc, nodes, uncertain, by_category, top}`."""
    ops = _ops()
    if not actor:
        raise ops.OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    todo, unc = doc_auto(doc_id)
    if todo is None:
        raise ops.OpRefused(f"'{doc_id}'의 판정 대장이 없다 — 그 문서를 넣은 적이 없거나 대장 이전 인입이다 "
                            f"(다시 넣으면 생긴다: python run.py ingest-file <원본>)")
    cats = {}
    for _l, _i, _c, cat in todo:
        cats[cat] = cats.get(cat, 0) + 1
    pv = {"op": "confirm-doc", "doc": doc_id, "nodes": len(todo), "uncertain": unc,
          "by_category": dict(sorted(cats.items(), key=lambda x: (-x[1], x[0]))), "top": todo[:10]}
    if dry_run:
        return pv
    for lay, nid, _c, _cat in todo:
        confirm(lay, nid, actor, reason or f"문서 단위 확인 — {doc_id}")
    return pv


def alias(layer, target, surface, actor, reason="", dry_run=False):
    """**사람이 표기를 잇는다** — 사전에 표기 하나를 손으로 등재한다 (B74 ⑤ · I6).

    지금까지 사전에 표기를 넣는 사람의 길은 골격 alias(seed `ALIASES`)뿐이었고,
    entity의 alias는 **판정 결과로만** 쌓였다. 사내에서 「이 표기도 같은 것이다」를
    아는 사람이 그것을 시스템에 말할 자리가 없었다는 뜻이다.

    등재는 인입과 **같은 함수**(`Builder._register`)로 한다(B74 ①) — 원 표기와
    **조회 키**(그 표기를 이 노드의 부모 아래에서 조립한 스코프 canonical) 둘이
    같이 들어가야 다음 인입이 그 표기에서 exact로 끊는다.

    거부 셋: 행위자 없음 · 대상 없음(툼스톤·타층 id 포함 — `_target`) ·
    **같은 부모 아래 다른 live 노드에 이미 붙은 표기**. 마지막이 핵심이다:
    alias로 두 노드를 한 표기에 묶으면 **병합을 우회한 병합**이 되고, 그것은
    사람이 배분표를 써야 되돌릴 수 있는 종류의 사고다(I2가 자동 불가인 이유).

    미리보기는 없다 — 파급 1건이다(문서 4 §4.7-4 예외).
    """
    ops = _ops()
    if not actor:
        raise ops.OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    surface = (surface or "").strip()
    if not surface:
        raise ops.OpRefused("등재할 표기를 달라")
    w = World()
    if w.get(target):
        nid = target
    else:                                       # 친 층 먼저 · 없으면 층 전부(노드는 집 층)
        here = list((w.graphs[layer].nodes.values()) if layer in w.graphs else [])
        try:
            nid = _by_canonical(here, target)
        except ops.OpRefused:
            nid = _by_canonical([n for _l, n in w.nodes()], target)
    w, g, layer = ops._open(layer, nid)
    node = ops._target(g, nid)                  # 툼스톤·없는 id는 여기서 거부된다
    cfg = ops._cfg(layer)
    parent = node.get("parent") or node.get("mirror_scope")
    dic = Dictionary.open()
    key, _scoped = scope_canonical(surface, node["category"], parent, cfg)
    for other in set(dic.lookup(surface)) | set(dic.lookup(key)):
        o = w.get(other)
        if other == nid or not o or not is_live(o):
            continue
        if o["category"] != node["category"]:
            continue
        if (o.get("parent") or o.get("mirror_scope")) != parent:
            continue
        raise ops.OpRefused(
            f"'{surface}'는 이미 같은 자리의 다른 노드에 붙어 있다 — "
            f"'{o['canonical']}' ({other})\n"
            f"     합칠 것이면 alias가 아니라 병합이다: "
            f"python run.py ops merge {layer} {other} {nid} --actor {actor} --yes")
    pv = {"op": "alias", "layer": layer, "target": nid,
          "canonical": node["canonical"], "surface": surface, "key": key,
          "parent": parent, "nodes": 1, "edges": 0}
    if dry_run:
        return pv
    prov = f"op:alias:{actor}"
    b = Builder(g, cfg, None, None, layer)
    b.dict = dic
    b._register(surface, nid, prov, key=key)    # ①의 등재 함수 그대로
    b.flush()
    g.save()
    ops.log_op("I6:alias", actor, [nid], reason,
               {"surface": surface, "key": key, "canonical": node["canonical"]},
               {"node": oplog.name(node)})
    return pv


def _by_canonical(nodes, name):
    """canonical로도 집는다 — 사람이 화면에서 보는 것은 id가 아니라 이름이다."""
    hit = [n["id"] for n in nodes
           if is_live(n) and (n["canonical"] == name or norm(n["canonical"]) == norm(name))]
    if not hit:
        raise _ops().OpRefused(f"대상 노드가 없다: {name}")
    if len(hit) > 1:
        raise _ops().OpRefused(f"'{name}'이 여럿이다 — node_id로 지목하라: {hit[:4]}")
    return hit[0]


# ---------------------------------------------------------------- 엣지 삭제
def delete_edge(layer, src, rel, dst, actor, reason=""):
    """사람이 지운 엣지 — 툼스톤을 남긴다. **재인입이 되살리지 못한다**(명세 §5.5-3).

    `GraphStore.add_edge`가 툼스톤 (src,rel,dst)를 건너뛰는 것이 그 집행이며,
    여기서는 그 툼스톤을 심는다.
    """
    from core.graph import STATUS_DELETED
    ops = _ops()
    if not actor:
        raise ops.OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    # 엣지는 문서 층에 산다(B100 ④) — 친 층에 없으면 층 전부에서 찾는다
    w = World()
    lays = ([layer] if layer in w.graphs else []) + [l for l in w.graphs if l != layer]
    hit, g = [], None
    for lay in lays:
        g = w.graphs[lay]
        hit = [e for e in g.edges if (e["src"], e["rel"], e["dst"]) == (src, rel, dst)]
        if hit:
            break
    if not hit:
        raise ops.OpRefused("그런 엣지가 없다")
    for e in hit:
        e["status"] = STATUS_DELETED
    g._reindex_tombstones()
    g.save()
    ops.log_op("edge:delete", actor, [src, dst], reason, {"rel": rel},
               {"src": oplog.name(w.get(src)), "dst": oplog.name(w.get(dst))})
    return {"op": "delete_edge", "edges": len(hit)}
