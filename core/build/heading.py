# -*- coding: utf-8 -*-
"""칸 3.4 — **제목 개체** — 문서 개요가 「대상」으로 정한 제목을 노드로 · 상위로 올라가는 폴백 사슬 (B115 ②③).

개요(`core/build/outline.py` — 지점 ⑪)가 제목마다 대상 `{name, category}` 또는 주제를 정했다. 여기서 하는 일 둘:

1. **노드로 세운다**(`land`) — 제목 트리 순서(부모 먼저)로 지금의 공통 해소 길(`Builder.resolve_at_home` — 다른 공정
   이름 가드 · 사전 → 재생 → 판정 · 다른 문서의 같은 유닛과 만나면 붙는다)을 지난다. 이름 규칙 그대로 — 가장 가까운
   위 제목 개체가 골격이면 그것이 좌표 · `nest_categories`면 그 이름 아래. 좌표 · 극성 · 증거는 그 제목 아래 **첫 조각**의
   것이다. 대장 행은 역할 `heading`(위치 = 제목 경로 · 열 = 카테고리) — 재구축이 재생한다(`replay.ROLES`).
   제목 트리의 부모-자식은 **카테고리쌍 매핑**의 관계로 잇는다(`belongs.edge_of` — 두 방향) — 매핑이 없으면 그
   위로 올라가고(결함 로그) · 맨 위까지 없으면 좌표 폴백(지금 규칙).
2. **폴백 사슬의 재료**(`chain_for`) — 조각 하나 위의 제목 개체 노드를 가까운 것부터 `[(node_id, 그래프, 단)]`.
   산문 개체가 소속 · 관계 · 스키마 어느 엣지에도 서지 못하면 `loop.fallback_untouched`가 이 사슬을 먼저 타고
   (`폴백(제목 n단)` — n은 제목 트리의 깊이 · 맨 위 = 1단) 그다음 좌표(`폴백`)로 간다.

코드에 층 어휘 0 — 카테고리 · 관계 이름은 개요의 답과 층 config(카테고리쌍 매핑)가 말한다. 표 · 산문 · 렌즈가 같은
함수를 지난다(표는 제목 계층이 없어 개요가 비고 여기도 0이다).
"""
from __future__ import annotations

from core.build import belongs, gate
from core.state import store
from core.state.ids import norm

#: 대장 행의 역할 — 재생 재료(`replay.ROLES`) · 맞춤표의 개요 줄이 센다
ROLE = "heading"
#: 제목 트리 엣지의 대장 `attached.path`
TREE = "제목"


def fallback_path(depth):
    """폴백 사슬에서 제목 개체에 붙은 자리의 이름 — `폴백(제목 n단)`."""
    return f"폴백(제목 {depth}단)"


def _first_chunks(env, ol):
    """제목 id → 그 제목 아래(서브트리) 첫 조각 — 좌표 · 극성 · 증거의 자리."""
    from core.build import outline as OL
    out = {}
    for c in env.get("chunks") or []:
        for h in OL.chain(ol, c.get("source_locator")):
            out.setdefault(h["id"], c)
    return out


def _is_coord(n):
    """골격 좌표 노드인가(Tier1 — `resolve_anchor`와 같은 기준) — 그 아래 제목은 이것을 좌표로 쓴다."""
    from core.state.bootstrap import COORD_CATEGORY
    return bool(n) and n.get("category") == COORD_CATEGORY and n.get("status") in ("seed", "confirmed")


def _kw(b, src, prov):
    """그 조각의 좌표 해소 재료 — `(좌표 id, 그래프, 부모 canonical, 극성)` (산문 pass1과 같은 순서 · 큐 0)."""
    from core.state.bootstrap import COORD_CATEGORY
    ref, ref_g = b.resolve_anchor(src.get("process_ref"), COORD_CATEGORY, prov, defer=[])
    ref = b.descend_anchor(ref, src.get("electrode_type"), ref_g)
    return ref, ref_g, (ref_g.get(ref)["canonical"] if ref else None), b.anchor_polarity(ref, ref_g)


def land(b, cfg, graph, env, ol, chunk_id_of):
    """제목 개체를 노드로 — `{제목 id: (node_id, 그래프, 깊이)}`. `chunk_id_of`는 위치 → 청크 id(증거)."""
    from core.build import loop
    from core.build.naming import nest_categories
    heads = [h for h in (ol or {}).get("headings") or [] if h.get("target")]
    if not heads:
        return {}
    first = _first_chunks(env, ol)
    by = {h["id"]: h for h in ol["headings"]}
    nests = nest_categories(b.cfg)
    landed = {}
    for h in heads:
        src = first.get(h["id"]) or {}
        loc = src.get("source_locator")
        prov = f"{env['doc_id']}#{loc}" if loc else env["doc_id"]
        name, cat = h["target"]["name"], h["target"]["category"]
        ref, ref_g, parent, pol = _kw(b, src, prov)
        ups = _landed_ups(h, by, landed)
        if ups:
            uid, ug, _d = ups[0]
            un = ug.get(uid) or {}
            if _is_coord(un):                       # 위 제목 개체가 골격 — 그것이 좌표다(소속 골격과 같은 결)
                ref, ref_g, parent, pol = uid, ug, un["canonical"], b.anchor_polarity(uid, ug)
            elif cat in nests:
                parent = un.get("canonical")        # 이름에 소속 — 부모 제목 개체 아래 (B102 ⑤)
        nid, eb = b.resolve_at_home(name, cat, prov, coord=(ref, ref_g), electrode_type=src.get("electrode_type"),
                                    parent_canonical=parent, anchor_polarity=pol,
                                    coord_surface=src.get("process_ref"), at=(h["path"], cat))
        last = eb.last or {}
        row = b.ledger.add(locator=h["path"], field=cat, role=ROLE, surface=name,
                           canonical=last.get("canonical"), layer=last.get("layer") or b.layer,
                           path=last.get("path") or "none",
                           verdict=loop._VERDICT.get(last.get("verdict"), "pending"), node_id=nid,
                           candidates_n=last.get("candidates_n", 0), confidence=last.get("confidence", 0.0),
                           llm=last.get("llm"), queue_kind=last.get("queue_kind"), nearest=last.get("nearest"),
                           same_doc=last.get("same_doc"), target=b.canonical_of(nid),
                           category=last.get("category"), scope=last.get("scope"), replay=last.get("replay"))
        if not nid:
            continue
        hg = b.graph_of(nid) or graph
        b.buffer[norm(name)] = nid                  # 같은 문서의 소속 이름이 이 노드를 찾는다(버퍼 · B102 ④)
        landed[h["id"]] = (nid, hg, h["depth"])
        if _is_coord(hg.get(nid)):
            continue                                # 골격 자신 — 트리 엣지 · 폴백 0(좌표는 이미 골격에 있다)
        cid = chunk_id_of.get(loc)
        if not _tree_edge(b, cfg, graph, env, nid, hg, ups, row, prov, cid, h):
            loop.fallback_untouched(b, cfg, [(nid, graph)], set(), ref, ref_g, prov, env["doc_id"],
                                    evidence_chunk=cid, rows={nid: row})
    return landed


def _landed_ups(h, by, landed):
    """그 제목 위의 **선** 제목 개체 — 가까운 것부터 `[(node_id, 그래프, 깊이)]`."""
    out, cur = [], h.get("parent")
    while cur is not None and cur in by and len(out) < 64:
        if cur in landed:
            out.append(landed[cur])
        cur = by[cur].get("parent")
    return out


def _tree_edge(b, cfg, graph, env, nid, hg, ups, row, prov, cid, h):
    """제목 트리 엣지 — 가까운 위 제목 개체부터 카테고리쌍 매핑이 있는 첫 것에(매핑 없는 칸은 결함 로그)."""
    from core.build import ledger as _lg
    me = hg.get(nid) or {}
    for uid, ug, _d in ups:
        if uid == nid:
            continue
        up = ug.get(uid) or {}
        rel, fwd = belongs.edge_of(cfg, up.get("category"), me.get("category"))
        if not rel:
            store.append_defect(f"{env['doc_id']}: 제목 트리 — 카테고리쌍 매핑 없음 ({up.get('category')} → "
                                f"{me.get('category')}) '{up.get('canonical')}' › '{me.get('canonical')}' "
                                f"@ {h['path']} → 그 위로")
            continue
        src, dst, sg, dg = (uid, nid, ug, hg) if fwd else (nid, uid, hg, ug)
        if gate.commit_edge(graph, src, rel, dst, cfg, gate.PATH_EXTRACT, [prov], env["doc_id"],
                            evidence_chunk=cid, src_graph=sg, dst_graph=dg) == gate.COMMIT:
            _lg.attach(row, rel, up.get("canonical"), TREE, "←" if fwd else "→")
            return True
    return False


def chain_for(landed, ol, locator):
    """조각 하나 위의 제목 개체 노드 — 가까운 것부터 `[(node_id, 그래프, 깊이)]` (폴백 사슬 · 연결 보강의 재료)."""
    from core.build import outline as OL
    return [landed[h["id"]] for h in OL.chain(ol, locator) if h["id"] in landed]
