# -*- coding: utf-8 -*-
"""칸 3.4 — **제목 개체** — 목차 노드화가 「대상」으로 정한 제목을 노드로 · 상위로 올라가는 폴백 사슬 (B115 ②③ · B148 ②).

목차 노드화(`core/build/outline.py` — 지점 ⑪)가 제목마다 대상 `{name, category}` · 좌표(`coord` — 골격 이름 제목) 또는 주제를
정했다. 여기서 하는 일 둘:

1. **노드로 세운다**(`land`) — 제목 트리 순서(부모 먼저)로 지금의 공통 해소 길(`Builder.resolve_at_home` — 다른 공정
   이름 가드 · 사전 → 재생 → 판정 · 다른 문서의 같은 유닛과 만나면 붙는다)을 지난다. 이름 규칙 그대로 — 가장 가까운
   위 제목 개체가 골격이면 그것이 좌표 · `nest_categories`면 그 이름 아래. 좌표 · 극성 · 증거는 그 제목 아래 **첫 조각**의
   것이다. 대장 행은 역할 `heading`(위치 = 제목 경로 · 열 = 카테고리) — 재구축이 재생한다(`replay.ROLES`).
   제목 트리의 부모-자식은 **카테고리쌍 매핑**의 관계로 잇는다(`belongs.edge_of` — 두 방향) — 매핑이 없으면 그
   위로 올라가고(결함 로그) · 맨 위까지 없으면 좌표 폴백(지금 규칙). **좌표 제목**(B148 ②)은 해소 대신 다른 공정 가드(`other_process`
   — `resolve_at_home`의 첫 단계와 같은 함수) → 골격 노드(`resolve_anchor` 조회만 · 극성 하강은 그 아래 첫 조각의 극성) — 골격 자신이라
   트리 엣지 · 폴백 0 · 그 아래 청크의 소속 후보 · 폴백 사슬에 그 골격 노드가 제목 노드 자리로 선다 · 그 아래 조각의 좌표가 그
   노드의 조상이면 그 노드로 내린다(`coord_below` — 산문 Pass 1 · 제목 착지가 같은 함수 · B150 ②).
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


def _kw(b, src, prov, landed=None, ol=None):
    """그 조각의 좌표 해소 재료 — `(좌표 id, 그래프, 부모 canonical, 극성)` (산문 pass1과 같은 순서 · 큐 0 · 좌표 하강 같은 함수)."""
    from core.state.bootstrap import COORD_CATEGORY
    res = b.resolve_coords(src.get("process_ref"), COORD_CATEGORY, prov, electrode_type=src.get("electrode_type"),
                           defer=[])                       # 공정 목록 — 주 좌표는 하나일 때만 (B125 ④)
    ref, ref_g = coord_below(b, landed, ol, src) or b.main_coord(res)
    return ref, ref_g, (ref_g.get(ref)["canonical"] if ref else None), b.anchor_polarity(ref, ref_g)


def coord_below(b, landed, ol, src):
    """**조각 좌표 하강**(B150 ②) — 그 조각 위 가장 가까운 **좌표 제목**(골격 이름 제목이 골격 노드에 앉은 것)이 조각 좌표의
    아래면 그 골격 노드 `(id, 그래프)` · 아니면 None(조각 좌표 그대로). **내리기만**: 조각 좌표(문서 좌표에서 물려받은 것도 같은
    대조)가 그 노드의 조상일 때만 — 같은 노드 · 더 깊은 자기 좌표 · 다른 줄기 · 좌표 없음 · 공정 목록(주 좌표 없음)은 그대로.
    대조는 개념 노드끼리(극성 하강 전 — `resolve_anchor` 조회만) · 극성은 그 조각의 극성으로 지금 하강 함수(`descend_anchor`) ·
    메타(봉투)는 바꾸지 않는다 — 이름은 지금 이름 규칙이 이 좌표로 짓는다(표의 `process_ref`가 그 노드인 행과 같은 이름)."""
    if not landed:
        return None
    from core.build import outline as OL
    from core.state.bootstrap import COORD_CATEGORY
    from parser.normalizer import coord_refs
    refs = coord_refs(src.get("process_ref"))
    if len(refs) != 1:
        return None
    h = next((h for h in OL.chain(ol, src.get("source_locator"))
              if h.get("coord") and h["id"] in landed and _is_coord(landed[h["id"]][1].get(landed[h["id"]][0]))), None)
    if h is None:
        return None
    hid, g = b.resolve_anchor(h["target"]["name"], COORD_CATEGORY, None, defer=[])
    rid, rg = b.resolve_anchor(refs[0], COORD_CATEGORY, None, defer=[])
    if not hid or not rid or rid == hid:
        return None
    pm = b._parent_map(g, COORD_CATEGORY)
    up, c = [], pm.get(g.get(hid)["canonical"])
    while c and c not in up and len(up) < 64:      # 그 노드의 조상(가까운 것부터)
        up.append(c)
        c = pm.get(c)
    if rg.get(rid)["canonical"] not in up:
        return None
    return (b.descend_anchor(hid, src.get("electrode_type"), g) or hid), g


def _coord(b, name, cat, prov, src, ref, ref_g):
    """좌표 제목의 착지 — `(node_id, 그래프)` 또는 `(None, None)` · 다른 공정이면 관련 링크(노드 0) · 아니면 골격 노드(판정 0 · 큐 0)."""
    other = b.other_process(name, (ref, ref_g))
    if other is not None:
        b._mention(name, cat, prov, other)
        return None, None
    nid, g = b.resolve_anchor(name, cat, prov, defer=[])
    if not nid:
        b.last = {"canonical": name, "verdict": "pending", "path": "none", "layer": b.layer}
        return None, None
    nid = b.descend_anchor(nid, src.get("electrode_type"), g) or nid
    b.last = {"canonical": g.get(nid)["canonical"], "verdict": "match", "path": "skeleton", "confidence": 1.0,
              "layer": getattr(g, "layer", b.layer), "queue_kind": None, "candidates_n": 0, "node_id": nid,
              "category": cat, "llm": {"calls": 0, "in_tokens": 0, "out_tokens": 0}}
    return nid, g


def land(b, cfg, graph, env, ol, chunk_id_of):
    """제목 개체를 노드로 — `{제목 id: (node_id, 그래프, 깊이)}`. `chunk_id_of`는 위치 → 청크 id(증거)."""
    from core.build import loop
    from core.build.naming import name_parent
    heads = [h for h in (ol or {}).get("headings") or [] if h.get("target")]
    if not heads:
        return {}
    first = _first_chunks(env, ol)
    by = {h["id"]: h for h in ol["headings"]}
    landed = {}
    for h in heads:
        src = first.get(h["id"]) or {}
        loc = src.get("source_locator")
        prov = f"{env['doc_id']}#{loc}" if loc else env["doc_id"]
        name, cat = h["target"]["name"], h["target"]["category"]
        ref, ref_g, parent, pol = _kw(b, src, prov, landed, ol)
        ups = _landed_ups(h, by, landed)
        owner = None                                # 판정의 자리 — 위 제목 개체(B142 ③ · 이름 부모와 같은 재료)
        if ups:
            uid, ug, _d = ups[0]
            un = ug.get(uid) or {}
            if _is_coord(un):                       # 위 제목 개체가 골격 — 그것이 좌표다(소속 골격과 같은 결)
                ref, ref_g, parent, pol = uid, ug, un["canonical"], b.anchor_polarity(uid, ug)
            else:                                   # 이름에 소속 — 부모 제목 개체 아래 (B102 ⑤ · 한 함수 B119 ④)
                parent = name_parent(cat, un.get("canonical"), parent, b.cfg)
                owner = (uid, ug)
        cg = None
        if h.get("coord"):                          # 골격 이름 제목 — 좌표 (B148 ②)
            (nid, cg), eb = _coord(b, name, cat, prov, src, ref, ref_g), b
        else:
            nid, eb = b.resolve_at_home(name, cat, prov, coord=(ref, ref_g), electrode_type=src.get("electrode_type"),
                                        parent_canonical=parent, anchor_polarity=pol,
                                        coord_surface=src.get("process_ref"), at=(h["path"], cat), owner=owner)
        last = eb.last or {}
        row = b.ledger.add(locator=h["path"], field=cat, role=ROLE, surface=name,
                           canonical=last.get("canonical"), layer=last.get("layer") or b.layer,
                           path=last.get("path") or "none",
                           verdict=loop._VERDICT.get(last.get("verdict"), "pending"), node_id=nid,
                           candidates_n=last.get("candidates_n", 0), confidence=last.get("confidence", 0.0),
                           llm=last.get("llm"), queue_kind=last.get("queue_kind"), nearest=last.get("nearest"),
                           same_doc=last.get("same_doc"), target=b.canonical_of(nid),
                           category=last.get("category"), scope=last.get("scope"), replay=last.get("replay"),
                           apart=last.get("apart"), similar=last.get("similar"), basis=last.get("basis"))
        if not nid:
            continue
        hg = cg or b.graph_of(nid) or graph
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
