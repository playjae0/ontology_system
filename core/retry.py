# -*- coding: utf-8 -*-
"""orphan **재시도** — 큐에 남은 미부착·미앵커 항목을 다음 빌드 뒤에 다시 시도한다 (문서 4 §4.7-5).

`core/pipeline.py`에서 떼어냈다. 문서 빌드(표·산문 → 노드·엣지)와 「빌드가 끝난 뒤 큐를
다시 훑는 일」은 시점도 재료도 다르다 — 앞은 한 문서 안에서, 뒤는 그래프 전체를 본다.
진입점은 `retry_orphans(layers)` 하나이고 `pipeline.finalize`가 부른다.

**바꾸지 않은 것**: 큐 kind 3종(`RETRY_KINDS`) · 저해상 철회 · 게이트 통과 후에만 커밋.
"""
from __future__ import annotations

from . import gate, log, matcher, store
from .bootstrap import load_config, open_graph
from .build import Builder
from .status import is_live

_LOG = log.get(__name__)


# ---------------------------------------------------------------- orphan 재시도
RETRY_KINDS = ("orphan_anchor", "orphan_attach", "orphan_chunk_link")


def retry_orphans(layers=None):
    """**orphan 재시도 배치** — 문서 4 §4.7-5 · §4.8-5.

    **주기의 정본은 빌드 말미 sweep 1회다.** 별도 스케줄러도 전용 서브커맨드도 두지
    않는다 — 그래프가 자라는 시점이 곧 재시도가 의미를 갖는 유일한 시점이고, 주기와
    호출자가 비어 있으면 큐 항목이 **아무도 부르지 않는 배치를 기다린다.**

    각 항목의 보존 표면형을 **판정 파이프라인(§4.3)에 다시 태운다** — 재사용 지점이
    `matcher.match` 하나라는 것이 §7.1의 요구다. 확신되면 자동 해소하고, 불확실이면
    항목을 그대로 큐에 남긴다.

    **provenance는 큐 항목이 보유한 원 문서 발자국 그대로다** — `auto:{규칙명}`을
    쓰지 않는다(§4.7-5). 문서 발자국이 아니면 재인입 회수 대상 밖으로 나가, 개정으로
    사라진 행의 엣지가 살아남는다.

    재시도는 **같은 그래프 상태에서 같은 판정을 내는 결정적 연산**이라 「클린 2회
    동일 그래프」 판정을 깨지 않는다.

    돌려주는 것: `{kind: 해소 건수}` — 계기판·보고용이다.
    """
    from router import discover
    from .dictionary import Dictionary

    lays = layers or discover()
    graphs = {lay: open_graph(lay) for lay in lays}
    cfgs = {lay: load_config(lay) for lay in lays}
    dic = Dictionary.open()
    healed = {k: 0 for k in RETRY_KINDS}

    queue = store.read(store.QUEUE, [])
    for item in list(queue):
        kind = item.get("kind")
        if kind not in RETRY_KINDS:
            continue
        pl = item.get("payload") or {}
        if kind == "orphan_attach":
            if _retry_attach(pl, item, graphs, cfgs, dic):
                healed[kind] += 1
        elif kind == "orphan_anchor":
            if _retry_anchor(pl, item, graphs, cfgs, dic):
                healed[kind] += 1
        # orphan_chunk_link의 생산자가 아직 없다 — 항목이 생기면 같은 자리에서 돈다.

    for lay, g in graphs.items():
        g.save()
    dic.save()
    if any(healed.values()):
        _LOG.info("orphan 재시도 — %s",
                  ", ".join(f"{k} {v}" for k, v in healed.items() if v))
    return healed


def _pick_cat(surface, category, graphs, dic):
    """카테고리가 **선언된** 표면형을 판정한다 (B11 — 정상 경로).

    카테고리가 하나로 정해져 있으므로 순회도 수렴 판정도 필요 없다.
    """
    for lay, g in graphs.items():
        cands = matcher.candidates(surface, category, lay, g, dic)
        if not cands:
            continue
        v = matcher.match(surface, cands, category)
        if v["type"] == matcher.MATCH and v["matched_id"]:
            return v["matched_id"], lay, g
    return None, None, None


def _pick_any(surface, graphs, cfgs, dic):
    """카테고리가 선언되지 않은 표면형(attach 대상)을 판정한다.

    **첫 히트를 임의로 고르지 않는다.** attach 대상은 카테고리가 선언돼 있지 않아
    후보가 여러 카테고리에 걸친다 — 카테고리를 순서대로 훑어 먼저 맞는 것을 쓰면
    **순회 순서가 답을 정한다.** 실측: `'정밀 노칭 프레스'`가 `Process/노칭`(0.95)과
    `Unit/노칭 프레스`(0.95) 양쪽에 걸렸고, 선언 순서상 앞선 Process가 이겨
    설비 자리에 공정이 들어갔다.

    그래서 **카테고리별로 판정하고 확신을 모은 뒤, 하나로 수렴할 때만** 쓴다.
    사전 정확 히트(`exact`)가 있으면 그것이 우선이고, 수렴하지 않으면 미해소로
    두어 항목을 큐에 남긴다 — `_dict_hit`과 같은 규율이다(문서 4 §4.4-3).
    """
    exact, fuzzy = {}, {}
    for lay, g in graphs.items():
        for cat in (cfgs[lay].get("categories") or {}):
            cands = matcher.candidates(surface, cat, lay, g, dic)
            if not cands:
                continue
            if any(c.get("exact") for c in cands):
                for c in cands:
                    if c.get("exact"):
                        exact[c["id"]] = (lay, g)
                continue
            v = matcher.match(surface, cands, cat)
            if v["type"] == matcher.MATCH and v["matched_id"]:
                fuzzy[v["matched_id"]] = (lay, g)
    pool = exact or fuzzy
    if len(pool) != 1:
        return None, None, None
    nid, (lay, g) = next(iter(pool.items()))
    return nid, lay, g


def _retry_attach(pl, item, graphs, cfgs, dic):
    """미해소 attach 재시도 — 성공하면 **저해상도 부착을 갈아끼운다**(§4.4-8 (a)).

    갈아끼움은 ①고해상도 엣지 커밋 ②저해상도 엣지의 **그 provenance만 회수**
    ③근거 0이 된 엣지의 착지(`_evidence_lost`가 다음 sweep에서 본다) 셋이다.
    회수하지 않으면 같은 지식이 두 벌로 남아 질의 근거가 중복되고, 재인입 때
    회수 대상이 어긋나 멱등성이 조용히 깨진다.
    """
    child_id, surface = pl.get("node_id"), pl.get("attach_to")
    if not child_id or not surface:
        return False
    child, clay, cg = None, None, None
    for lay, g in graphs.items():
        if child_id in g.nodes:
            child, clay, cg = g.get(child_id), lay, g
            break
    if child is None or not is_live(child):
        store.drop(item["kind"], lambda p: p == pl)     # 대상이 사라졌다 — 항목도 내린다
        return False

    # 대상 이름을 다시 해소한다. **큐 항목이 카테고리를 보유하면 그것 하나로**
    # 판정한다(B11) — 보유하지 않은 옛 항목만 수렴 판정으로 떨어진다.
    cat = pl.get("attach_category")
    if cat:
        target, tlay, tg = _pick_cat(surface, cat, graphs, dic)
    else:
        target, tlay, tg = _pick_any(surface, graphs, cfgs, dic)
    if target is None or target == child_id:
        return False                                    # 불확실 — 항목을 큐에 남긴다

    cfg = cfgs[tlay]
    rel = gate.pair_relation(cfg, tg.get(target)["category"], child["category"])
    if not rel:
        store.append_defect(
            f"orphan 재시도: 카테고리쌍 매핑 없음 "
            f"({tg.get(target)['category']} → {child['category']})")
        return False
    prov = pl.get("provenance")
    gate.commit_edge(cg, target, rel, child_id, cfg, gate.PATH_EXTRACT,
                     [prov] if prov else [], item.get("doc_id"),
                     src_graph=tg, dst_graph=cg)
    _withdraw_lowres(cg, child_id, target, prov)
    store.drop(item["kind"], lambda p: p == pl)         # self-heal
    return True


def _withdraw_lowres(g, child_id, new_target, prov):
    """저해상도 부착의 **그 provenance만** 회수한다 (§4.4-8 (a) 갈아끼움).

    엣지를 지우지 않고 발자국만 뺀다 — 다른 문서가 같은 저해상도 부착을 주장하고
    있으면 그 근거는 살아 있어야 한다. 근거가 0이 되면 다음 sweep의
    `_evidence_lost`가 그것을 표시한다(삭제가 아니라 표시 — 카드 L9).
    """
    if not prov:
        return
    for e in g.edges:
        if e["dst"] != child_id or e["src"] == new_target:
            continue
        if e.get("status") == "deleted_by_user":
            continue
        if prov in (e.get("provenance") or []):
            e["provenance"] = [x for x in e["provenance"] if x != prov]


def _retry_anchor(pl, item, graphs, cfgs, dic):
    """미해소 좌표 재시도 — 성공하면 **보유분을 전부 착지시킨다**(§4.4-98).

    큐 항목이 보유한 것 셋을 각각 처리한다:
    ①`dropped_edges` — 생략된 엣지를 다시 커밋
    ②`pending_attrs` — 보류된 값을 해소된 노드에 저장
    ③(연쇄 걸침 entity는 `dropped_edges`의 표면형으로 되살린다)
    """
    surface, category = pl.get("surface"), pl.get("category")
    if not surface or not category:
        return False
    # **좌표 재시도도 anchor의 해소 규칙을 그대로 쓴다 — 사전(정확 일치·alias)까지다.**
    #
    # 문서 2 §2.4-①: "사전 조회(정확 일치·alias) → 해소, 미스면 곧바로
    # orphan_anchor 큐. **anchor 해소에는 후보검색·유사도·LLM 판정을 쓰지 않는다**
    # — 골격은 사람이 고정한 유형이고(P2), 추론으로 끌어당기면 사람의 보증을 코드가
    # 뒤집는다." 좌표 태깅이 닫힌 목록의 정확 일치 대조인 것과 같은 성질이다.
    #
    # 재시도가 존재하는 이유는 **그래프가 자랐기 때문**이지 매칭이 느슨해졌기
    # 때문이 아니다(§4.7-5). anchor는 Tier1(seed·confirmed) 한정이다.
    ref, rlay, rg = None, None, None
    for lay, g in graphs.items():
        hits = [nid for nid in dic.lookup(surface)
                if nid in g.nodes and is_live(g.get(nid))
                and g.get(nid)["category"] == category
                and g.get(nid).get("status") in ("seed", "confirmed")]
        if len(hits) == 1:
            ref, rlay, rg = hits[0], lay, g
            break
    if ref is None:
        return False                                    # 아직 골격에 없다 — 남긴다
    cfg, prov = cfgs[rlay], pl.get("provenance")
    did = item.get("doc_id")
    n = 0

    # ① **연쇄 드롭된 entity를 새로 세운다**(문서 4 §4.4 — B14).
    # 좌표가 해소됐으므로 이제 스코프를 붙일 수 있다 — 미리 만들어 둔 것이
    # 없으니 중복도 없다. 세운 노드의 id를 dropped_edges 해소에 쓴다.
    revived = {}
    parent = (rg.get(ref) or {}).get("canonical")
    for d in pl.get("dropped_entities") or []:
        lay2 = d.get("target_layer") or rlay
        g2 = graphs.get(lay2)
        if g2 is None:
            continue
        b2 = Builder(g2, cfgs[lay2], None, did, lay2)
        nid2 = b2.resolve_entity(d["surface"], d["category"], prov,
                                 parent_canonical=parent)
        b2.flush()
        if nid2:
            revived[d.get("field") or d["surface"]] = nid2
            revived[d["surface"]] = nid2
            n += 1

    for d in pl.get("dropped_edges") or []:
        src, dst = d.get("src"), d.get("dst")
        if d.get("from") == "@process_ref":
            src = ref
        elif src is None:
            src = revived.get(d.get("from")) or revived.get(d.get("src_surface"))
        if d.get("to") == "@process_ref":
            dst = ref
        elif dst is None:
            dst = revived.get(d.get("to")) or revived.get(d.get("dst_surface"))
        if not src or not dst:
            continue
        sg = next((g for g in graphs.values() if src in g.nodes), rg)
        dg = next((g for g in graphs.values() if dst in g.nodes), rg)
        gate.commit_edge(sg, src, d["relation"], dst, cfg, gate.PATH_SCHEMA,
                         [prov] if prov else [], did, src_graph=sg, dst_graph=dg)
        n += 1
    for a in pl.get("pending_attrs") or []:
        b = Builder(rg, cfg, None, did, rlay)
        b.put_attribute(ref, a["attr_name"], a["value"], a.get("context") or {},
                        a.get("provenance"), bool(a.get("context")))
        b.flush()
        n += 1
    store.drop(item["kind"], lambda p: p == pl)         # self-heal
    return True
