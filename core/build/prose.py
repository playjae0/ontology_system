# -*- coding: utf-8 -*-
"""칸 3.3 곁 — **비정형(prose) 구축**: 추출 후보를 그래프에 착지시킨다 (문서 4 §4.4).

추출(칸 3.3 · `core/build/extract.py`)이 낸 후보를 받아 해소·부착한다 — 뽑는 일과
앉히는 일이 다른 파일인 이유가 그것이다(계약 B · P-1 체크포인트).
"""
from __future__ import annotations

from core.state.bootstrap import COORD_CATEGORY
from core import matcher
from core.build import loop
from core.build.build import Builder
from core.build import gate
from core.build import ledger as _lg
from core.build.ledger import Ledger
from core.build import belongs, extract_ctx, heading, human, values
from core.build.human import HUMAN                    # 사람 후보의 표지 — 추출 후보 줄 · 대장 행의 `by` (B140 ③)
from parser.normalizer import null_marker            # 빈칸 표시 — 표와 같은 함수 (B113 ②)
from core.build.naming import name_parent
from core.state.status import is_live
from core.state import log, store
from core.state.ids import fold_latin, norm

_LOG = log.get(__name__)


# ---------------------------------------------------------------- 비정형 (1d′)
def _build_prose_pass1(b, cfg, env, candidates, by_locator, ch, loc_of, landed=None, outline=None):
    """Pass 1 — 청크마다 **좌표부터** 세운다 · 소속 대상을 먼저 해소한다(B102 ④). 돌려주는 것은
    `{chunk_id: 좌표 묶음 + 소속 계획}`.

    `build_prose`에서 단계로 떼어냈다(B78 2c) — 두 패스가 한 함수에 있으면
    「어느 패스가 만든 상태인가」를 사람이 줄 번호로 가르게 된다.
    """
    coords = {}
    doc = extract_ctx.doc_info(env)
    for cand in candidates:
        cid = cand["chunk_id"]
        src = by_locator.get(loc_of.get(cid), {})
        # 비정형도 같은 조립이다 — 청크가 없으면 chunk_id가 이미 `{doc_id}:…` 꼴이라
        # 문서를 갖고 있다(§7.2). 있으면 locator에 접두를 붙인다.
        _loc = src.get("source_locator")
        prov = f"{env['doc_id']}#{_loc}" if _loc else cid
        # **공정은 목록이다**(B125 ④) — 공정마다 anchor 행 하나(하나면 지금 그대로) · 주 좌표는 하나일 때만
        res = b.resolve_coords(src.get("process_ref"), COORD_CATEGORY, prov, electrode_type=src.get("electrode_type"))
        for s, r_id, r_g, hold in res:
            # 상위·극성 대조는 구축 말미 한 자리(`coord_scan.enqueue` — 표와 같은 함수 · B105 ③④)
            # **정직한 anchor 행**(B102 ⑦) — 빈 좌표는 「좌표 없음」(큐 없음) · 목록 밖 이름만 orphan_anchor
            b.ledger.add(locator=_loc or cid, field="process_ref", role="anchor",
                         surface=s, canonical=r_g.get(r_id)["canonical"] if r_id else None,
                         layer=r_g.layer if r_g else None,
                         path="skeleton" if r_id else "none",
                         verdict="anchor" if r_id else ("orphan" if s else "pending"),
                         node_id=r_id,
                         queue_kind=None if (r_id or not s) else "orphan_anchor",
                         hold=None if r_id else hold)
        # 골격 이름 제목 아래면 그 골격 노드로 내린다(B150 ② — 내리기만 · 봉투는 그대로 · anchor 행은 봉투의 좌표)
        low = heading.coord_below(b, landed, outline, src)
        ref, ref_g = low or b.main_coord(res)
        parent = ref_g.get(ref)["canonical"] if ref else None
        anchor_pol = b.anchor_polarity(ref, ref_g)      # A11-9 ① — 비정형도 동일
        plans = _pass1_entities(b, cfg, cand, src, prov, cid, doc,
                                (ref, ref_g, parent, anchor_pol), _loc,
                                coords=[low] if low else [(r_id, r_g) for _s, r_id, r_g, _h in res if r_id])
        coords[cid] = (src, prov, ref, ref_g, parent, anchor_pol, plans)
    return coords


def _pass1_entities(b, cfg, cand, src, prov, cid, doc, main, _loc, coords=None):
    """청크 하나의 개체 — 소속 대상 먼저(같은 청크 안 순서) → 이름 부모(골격 소속 · `nest_categories`) →
    해소(`resolve_at_home` — 표와 같은 함수) · 대장 행. 돌려주는 것은 소속 계획 `[{nid, tgt, bel, row}]`."""
    ref, ref_g, parent, anchor_pol = main
    bmap = belongs.belongs_of(cand)
    ents, cyc = belongs.order(cand.get("entities", []), bmap)
    for k in sorted(cyc):
        store.append_defect(f"{b.doc_id}: 소속 순환 — '{k}' @ {cid} → 소속을 버렸다")
    chunk_kw = dict(coord=(ref, ref_g), coords=coords, electrode_type=src.get("electrode_type"),
                    parent_canonical=parent, anchor_polarity=anchor_pol,
                    coord_surface=src.get("process_ref"))
    pcs, plans = {}, []
    for e in ents:
        if null_marker(e.get("surface")):
            # **빈칸 표시는 개체가 아니다**(B113 ② — 표와 같은 함수) — 노드 0 · 행은 남긴다
            b.ledger.add(locator=_loc or cid, field=e.get("category"), role="entity", surface=e.get("surface"),
                         layer=b.layer, path="none", verdict="blank")
            continue
        k = norm(e["surface"])
        bel = None if k in cyc else bmap.get(k)
        if bel and null_marker(bel.get("name")):
            bel = None                             # 소속 이름이 빈칸 표시 — 소속 없음(B113 ②)
        if bel and not bel.get("legacy") and e.get("by") != HUMAN:   # 사람 후보의 위 노드는 사람이 골랐다 (B140 ③)
            where = belongs.source_of(bel["name"], src, doc)
            if where is None:                      # 지어낸 소속 — 버린다(지어내지 않는다)
                belongs.drop_invented(b.doc_id, e["surface"], bel, cid)
                bel = None
        tgt = (belongs.resolve_target(b, bel, prov, chunk_kw, at=(_loc or cid, belongs.FIELD))
               if bel and not bel.get("legacy") else None)
        # **개체별 부모가 주 좌표를 이긴다**(B91 ③) — 이름을 정하기 **전에** 본다.
        e_ref, e_g, e_parent, e_pol = _entity_parent(b, e, src, prov, cid, pcs, main)
        owner = None                               # 판정의 자리 — 소속 대상 노드(B142 ③ · 이름 부모와 같은 재료)
        if tgt and tgt[0] == belongs.SKELETON and not e.get("parent"):
            e_ref, e_g = tgt[1], tgt[2]            # 골격 소속 = 그 개체의 좌표
            e_parent, e_pol = e_g.get(e_ref)["canonical"], b.anchor_polarity(e_ref, e_g)
        elif tgt and tgt[0] == belongs.NODE:      # 이름에 소속 — 골격 밖 노드 아래 (B102 ⑤ · 한 함수 B119 ④)
            if not ref and not e.get("parent"):    # 청크 좌표가 없으면 그 노드의 좌표를 물려받는다 (B140 ⑤)
                up, upg = belongs.coord_of(b, tgt[1], tgt[2])
                if up:
                    e_ref, e_g, e_parent, e_pol = up, upg, upg.get(up)["canonical"], b.anchor_polarity(up, upg)
            e_parent = name_parent(e["category"], tgt[2].get(tgt[1])["canonical"], e_parent, b.cfg)
            owner = (tgt[1], tgt[2])
        # **집에서 해소한다**(B90 ②) — table과 **같은 함수**다.
        nid, eb = b.resolve_at_home(e["surface"], e["category"], prov,
                                    coord=(e_ref, e_g), coords=coords,     # 다른 공정 가드 = 목록 전체의 계보 (B125 ④)
                                    electrode_type=src.get("electrode_type"),
                                    parent_canonical=e_parent,
                                    anchor_polarity=e_pol,
                                    coord_surface=src.get("process_ref"), belongs=bel,
                                    at=(_loc or cid, e.get("category")),       # 판정 재생의 자리 (B106 ②)
                                    chunk_text=src.get("text"),                # 2차 판정의 문장 (B123 ③)
                                    owner=owner)
        last = eb.last or {}
        row = b.ledger.add(locator=_loc or cid, field=e.get("category"),
                           role="entity", surface=e["surface"],
                           canonical=last.get("canonical"),
                           layer=last.get("layer") or b.layer,
                           path=last.get("path") or "none",
                           verdict=loop._VERDICT.get(last.get("verdict"), "pending"),
                           node_id=nid,
                           candidates_n=last.get("candidates_n", 0),
                           confidence=last.get("confidence", 0.0),
                           llm=last.get("llm"),
                           queue_kind=last.get("queue_kind"),
                           nearest=last.get("nearest"),
                           same_doc=last.get("same_doc"),
                           target=b.canonical_of(nid),
                           belongs_from=(bel or {}).get("from") or ("옛 attach" if (bel or {}).get("legacy") else None),
                           belongs_to=(bel or {}).get("name"),
                           category=last.get("category"), scope=last.get("scope"),
                           replay=last.get("replay"), judge2=last.get("judge2"),
                           apart=last.get("apart"), similar=last.get("similar"), basis=last.get("basis"),
                           by=HUMAN if e.get("by") == HUMAN else None)        # 사람 후보 표지 (B140 ③)
        if nid:
            values.land(cfg, eb, nid, e, src, prov, cid, row)    # 「항목 = 값」 → 그 노드의 속성(표와 같은 함수 · B120 ①)
            plans.append({"nid": nid, "tgt": tgt, "bel": bel, "row": row})
    return plans


def parent_hit(b, e, src, prov, pcs, defer=None):
    """개체 `parent`의 골격 노드 `(좌표 id, 그래프)` 또는 `(None, None)` — 부모 후보(`extract.parent_candidates`) 안이고 골격 노드로
    해소될 때만 · 쓰기 0(결함 로그는 부르는 쪽 몫 · `defer`를 주면 미해소 적재도 그 자루로). 구축(`_entity_parent`)과 추출 확인 md의
    판정 예고(`cli/extract_md`)가 같은 손이다."""
    want = e.get("parent")
    if not want:
        return None, None
    if "set" not in pcs:
        from core.build.extract import parent_candidates
        pcs["set"] = {norm(x): x for x in parent_candidates(src)}
        _f = {}
        for x in pcs["set"].values():
            _f.setdefault(fold_latin(x), set()).add(x)
        pcs["fold"] = _f
    hit = pcs["set"].get(norm(want))
    if hit is None:                                  # 2차 — 라틴 대소문자 · 하나일 때만 (B96 ④)
        _c = pcs["fold"].get(fold_latin(want)) or set()
        hit = next(iter(_c)) if len(_c) == 1 else None
    if not hit:
        return None, None
    return b.resolve_anchor(hit, COORD_CATEGORY, prov, **({"defer": defer} if defer is not None else {}))


def _entity_parent(b, e, src, prov, cid, pcs, main):
    """개체 하나의 **이름 부모** — `(좌표 id, 그래프, 부모 canonical, 극성)` (B91 ③).

    추출이 `parent`를 냈고 그것이 **부모 후보**(`extract.parent_candidates` — 좌표 서브트리 +
    본문에 나오는 골격 이름 · 같은 함수로 다시 센다) 안이며 골격 노드로 해소되면 그것이다.
    후보 밖이면 null로 읽고 결함 로그에 남긴다(지어낸 부모로 이름을 만들지 않는다).
    `parent`가 없으면 주 좌표 그대로다(지금과 같다). `pcs`는 청크 안 캐시다.
    """
    want = e.get("parent")
    if not want:
        return main
    pid, pg = parent_hit(b, e, src, prov, pcs)
    if not pid:
        store.append_defect(f"{b.doc_id}: 개체 부모 후보 밖 — '{want}' (개체 '{e['surface']}' "
                            f"@ {cid}) → null · 주 좌표를 쓴다")
        return main
    pid = b.descend_anchor(pid, src.get("electrode_type"), pg)
    return pid, pg, pg.get(pid)["canonical"], b.anchor_polarity(pid, pg)


def _about_hit(b, cfg, a):
    """관련 링크 하나의 노드 — **조회 전용**(B91 ③): 이 문서의 해소 버퍼 → 사전(카테고리 안 ·
    살아 있는 노드 · 유일할 때만). 노드를 만들지 않고 판정(LLM)도 부르지 않는다 — 못 찾거나
    여럿이면 `None`(호출부가 버리고 기록한다). 카테고리는 층 카테고리(겸 포함) 안이어야 한다.
    """
    surface, cat = (a or {}).get("surface"), (a or {}).get("category")
    if not surface or cat not in (cfg.get("categories") or {}):
        return None
    hosts = matcher._hosts(cat)
    nid = b.buffer.get(loop._n(surface))
    if nid:
        n = (b.graph_of(nid) or b.g).get(nid)
        if n and matcher._is(n, cat, hosts):
            return nid
    g = b.for_category(cat).g
    hits = {x for x in b.dict.lookup(surface)
            if g.get(x) and is_live(g.get(x)) and matcher._is(g.get(x), cat, hosts)}
    return next(iter(hits)) if len(hits) == 1 else None


def _link_about(b, cfg, cand, ch, doc_id):
    """청크의 **두 번째 매달림**(`chunks.json`의 `about` · B91 ③) — 관련 링크를 노드에 건다.

    키는 링크가 **있을 때만** 생긴다(새 필드가 비면 저장이 지금과 같다).
    """
    cid = cand["chunk_id"]
    for a in cand.get("about") or []:
        nid = _about_hit(b, cfg, a)
        if nid is None:
            store.append_defect(f"{doc_id}: 관련 링크 미해소 — '{(a or {}).get('surface')}'"
                                f"({(a or {}).get('category')}) @ {cid} → 버렸다(노드 0)")
            continue
        about = ch.setdefault("about", [])
        if {"chunk_id": cid, "node_id": nid} not in about:
            about.append({"chunk_id": cid, "node_id": nid})


def _attached(row, rel, other, how, arrow):
    """대장 행에 **이 값이 만든 엣지**를 단다(B102 ⑦ — 대장 한 손 `ledger.attach`)."""
    from core.build import ledger as _lg
    _lg.attach(row, rel, other, how, arrow)


def _belongs_edges(b, cfg, graph, env, plans, touched, prov, cid):
    """소속 엣지 — 대상 → 관계(카테고리쌍 매핑) → 개체 · 매핑에 없으면 결함 로그 + 폴백에 남긴다 ·
    소속 이름을 못 찾았으면 `orphan_attach`(재시도의 손잡이 — 지금 kind)."""
    for p in plans:
        bel, tgt, nid = p["bel"], p["tgt"], p["nid"]
        if not bel or bel.get("legacy"):
            continue
        if tgt is None:
            store.enqueue_rows(
                "orphan_attach", f"소속 대상 미해소 — '{bel['name']}'", env["doc_id"],
                loop._n(bel["name"]),
                {"node_id": nid, "surface": p["row"].get("surface"), "attach_to": loop._n(bel["name"]),
                 "attach_category": bel.get("category"), "belongs_from": bel.get("from"),
                 "provenance": prov, "chunk_id": cid},
                locator=(prov or "").split("#")[-1] or None)
            continue
        _kind, tid, tg = tgt
        cg = b.graph_of(nid) or graph
        rel, fwd = belongs.edge_of(cfg, (tg.get(tid) or {}).get("category"), (cg.get(nid) or {}).get("category"))
        if not rel:
            store.append_defect(f"{env['doc_id']}: 소속 엣지 — 카테고리쌍 매핑 없음 "
                                f"({(tg.get(tid) or {}).get('category')} → {(cg.get(nid) or {}).get('category')})"
                                f" @ {cid} → 폴백 사슬(제목 개체 → 좌표)")
            continue
        src, dst, sg, dg = (tid, nid, tg, cg) if fwd else (nid, tid, cg, tg)
        br = gate.commit_edge(graph, src, rel, dst, cfg, gate.PATH_EXTRACT, [prov], env["doc_id"],
                              evidence_chunk=cid, src_graph=sg, dst_graph=dg)
        if br == gate.COMMIT:
            touched.add(nid)
            # 화살표 = 실제 엣지 방향(B112 ⑥) — 대상 → 개체면 이 행 쪽으로 들어온다(←) · 개체 → 대상이면 나간다(→)
            _attached(p["row"], rel, (tg.get(tid) or {}).get("canonical"),
                      f"소속({bel.get('from') or '-'})", "←" if fwd else "→")


def _legacy_attach(b, cfg, graph, env, cand, touched, ref, ref_g, prov, cid):
    """**옛 체크포인트의 `attach`**(e-1.3 이전) — 지금과 같은 뜻으로 읽는다(호환 · B102 ③).
    해소 범위는 **문서 버퍼 전체 + 사전**이며 청크 경계가 없다 · 대상이 없으면 규칙 B."""
    for a in cand.get("attach", []):
        child = b.buffer.get(loop._n(a["surface"]))
        name, cat = loop._attach_target(a)       # {name, category} (§4.10 규약 8 — B11)
        target = b.buffer.get(loop._n(name)) if name else None
        _al = b.ledger.add(locator=(prov or "").split("#")[-1] or cid,
                           field=name or "(attach_to null)", role="attach",
                           surface=a.get("surface"), layer=b.layer,
                           path="none", verdict="pending")
        if target is None and name and cat:
            target = _dict_hit(b, name, b.for_category(cat).g, category=cat)
        if child is None:
            store.append_defect(
                f"{env['doc_id']}: attach 자식 미해소 — '{a['surface']}' → '{name}' @ {cid}")
            continue
        if target is None:
            loop._fallback_attach(b, cfg, graph, child, ref, ref_g, prov,
                                  env["doc_id"], evidence_chunk=cid)
            touched.add(child)
            _al.update(verdict="lowres" if ref else "pending", node_id=child)
            if name:
                store.enqueue_rows(
                    "orphan_attach", f"부착 대상 미해소 — '{name}'",
                    env["doc_id"], loop._n(name),
                    {"node_id": child, "surface": a["surface"], "attach_to": loop._n(name),
                     "attach_category": cat, "provenance": prov, "chunk_id": cid},
                    locator=(prov or "").split("#")[-1] or None)
            continue
        tg, cg = b.graph_of(target) or graph, b.graph_of(child) or graph
        rel = gate.pair_relation(cfg, tg.get(target)["category"], cg.get(child)["category"])
        if rel:
            gate.commit_edge(graph, target, rel, child, cfg, gate.PATH_EXTRACT,
                             [prov], env["doc_id"], evidence_chunk=cid,
                             src_graph=tg, dst_graph=cg)
        touched.add(child)
        _al.update(verdict="attached", node_id=child,
                   canonical=(tg.get(target) or {}).get("canonical"))


def build_prose(env, cfg, graph, candidates, builder=None, defer_save=False, outline=None):
    # **실패한 청크는 건너뛴다**(문서 4 §4.10 규약 9 · B55 ③). `failed`는 「보지
    # 못했다」이고 `entities: []`는 「봤는데 없었다」다 — 섞으면 결함이 「후보 0건」
    # 통계에 녹아 사라진다. 건너뛰는 사실은 이미 `defects.log`에 남아 있다(추출 시점).
    candidates = [c for c in candidates if not c.get("failed")]
    # **렌즈가 여럿이면 뿌리 빌더를 나눠 쓴다**(B91 ①) — 렌즈마다 새 빌더를 열면 같은 층
    # 그래프가 두 인스턴스로 열려 저장이 서로 덮는다. 그래프·사전·버퍼·대장을 공유한다.
    # **층 이름은 연 그래프의 폴더 이름**(B99 ①) — config 안 `"layer"`는 검사 대상이지 이름이 아니다
    b = builder or Builder(graph, cfg, None, env["doc_id"], graph.layer)
    if b.ledger is None:
        b.ledger = Ledger(env["doc_id"])      # 판정 대장 — 비정형도 같은 표다 (B74 ②)
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    by_locator = {c["source_locator"]: c for c in env.get("chunks", [])}
    loc_of = {cid: c.get("source_locator") for cid, c in ch["chunks"].items()
              if c.get("doc_id") == env["doc_id"]}

    # ════════════════ Pass 1 (해소) ════════════════
    # **문서 전체의 anchor·entity를 먼저 전부 해소해 버퍼에 담는다**(문서 4 §4.2).
    # 부착은 해소가 끝난 뒤에만 시작한다 — 그래야 **문서 안에서 뒤에 나오는 개체를
    # 앞의 청크가 참조해도** 붙는다. 이 분리 덕에 부착 실패의 원인이 구분된다:
    # Pass 1에 없는 대상을 가리키면 진짜 미해소(큐로), 있는데 실패하면 구현 결함.
    #
    # 버퍼는 `정규화 표면형 → node_id` 맵이고 수명은 문서 하나이며 **층으로 나누지
    # 않는다**(걸침 하위 빌더가 같은 버퍼를 공유한다 — §4.2). 층 간 동명 표면형은
    # **마지막 해소가 이긴다** — 버퍼는 사전과 달리 후보 목록을 두지 않으므로,
    # 카테고리로 선별해야 하는 소비처는 사전을 함께 조회한다.
    # **제목 개체 먼저**(B115 ② — 문서 개요가 대상으로 정한 제목 · 트리 순서) — 같은 문서의 소속 이름이 버퍼에서
    # 찾고 · 상위로 올라가는 폴백 사슬의 칸이 된다. 개요가 없거나 대상이 없으면 0(지금 길 그대로).
    landed = heading.land(b, cfg, graph, env, outline, {loc: cid for cid, loc in loc_of.items()})
    _lg.chunk_done(None)                          # 제목 개체 행 — 붙은 자리와 함께 화면에 (B119 ⑤)
    human.aliases(b, env["doc_id"])               # 사람 후보 같은 것 — 있는 노드면 해소 앞에 (B140 ③)
    coords = _build_prose_pass1(b, cfg, env, candidates, by_locator, ch, loc_of, landed, outline)
    human.aliases(b, env["doc_id"], after=True)   # 대상이 이번 새것이면 그 노드가 선 뒤

    # ════════════════ Pass 2 (부착) ════════════════
    # **비정형의 순회 단위는 레코드가 아니라 청크(추출 후보)다**(문서 4 §4.2).
    # 그 청크의 후보에서 **해소된 언급 전부**에 describes를 만든다 — 부착·엣지
    # 성립 여부와 무관하다. 청크의 `linked`는 그 결과의 재계산이다(§4.8-2①).
    for cand in candidates:
        cid = cand["chunk_id"]
        src, prov, ref, ref_g, parent, anchor_pol, plans = coords[cid]

        for e in cand.get("entities", []):
            nid = b.buffer.get(loop._n(e["surface"]))
            if nid is None:
                continue                        # Pass 1이 못 세운 것 — 부착도 없다
            if {"chunk_id": cid, "node_id": nid} not in ch["describes"]:
                ch["describes"].append({"chunk_id": cid, "node_id": nid})
            ch["chunks"][cid]["linked"] = True          # 상동 — 재인입이 거짓으로 되돌리지 않는다

        _link_about(b, cfg, cand, ch, env["doc_id"])   # 관련 링크 — 조회 전용 (B91 ③)
        rows = {p["nid"]: p["row"] for p in plans}
        touched = set()

        # ③ 경로 — 추출 후보. 게이트의 실질 관문이다.
        doc = extract_ctx.doc_info(env)
        for r in cand.get("relations", []):
            # 끝점 = 이름 조회 한 함수(이 문서 버퍼 · 골격 · 사전 — 그 청크에 이름이 있을 때만 · B140 ⑤)
            sh, dh = (belongs.lookup(b, r[k], coord=ref, src=src, doc=doc) for k in ("src", "dst"))
            s, d = (sh or (None, None))[1], (dh or (None, None))[1]
            if s and d:
                # **엣지는 뽑은 층에**, 끝점은 제 집 그래프에서 읽는다(걸침 엣지 — B90 ②)
                br = gate.commit_edge(graph, s, r["rel"], d, cfg, gate.PATH_EXTRACT,
                                      [prov], env["doc_id"], evidence_chunk=cid,
                                      src_graph=sh[2], dst_graph=dh[2])
                if br == gate.COMMIT:
                    touched |= {s, d}
                    _attached(rows.get(s), r["rel"], b.canonical_of(d), "관계", "→")
                    _attached(rows.get(d), r["rel"], b.canonical_of(s), "관계", "←")
            else:                               # 게이트에 닿기도 전의 소멸 — 기록한다
                store.append_defect(
                    f"{env['doc_id']}: 관계 후보 끝점 미해소 — "
                    f"'{r['src']}' -{r['rel']}-> '{r['dst']}' @ {cid}")

        _belongs_edges(b, cfg, graph, env, plans, touched, prov, cid)     # 소속 엣지 (B102 ④)
        _legacy_attach(b, cfg, graph, env, cand, touched, ref, ref_g, prov, cid)   # 옛 체크포인트
        # **폴백 한 함수**(B102 ⑤ — 표와 같은 함수) — 어느 엣지에도 서지 못한 개체만 좌표에
        # 소속 대상으로 새로 앉은 골격 밖 노드(경로·시트의 유닛)도 그 좌표에 닿아야 한다 — 같은 함수
        tnodes = [(p["tgt"][1], graph) for p in plans if p["tgt"] and p["tgt"][0] == belongs.NODE]
        # 사슬 = 이 청크 위의 제목 개체(가까운 것부터) → 그다음 좌표 (B115 ③)
        loop.fallback_untouched(b, cfg, [(p["nid"], graph) for p in plans] + tnodes, touched,
                                ref, ref_g, prov, env["doc_id"], evidence_chunk=cid,
                                chain=heading.chain_for(landed, outline, src.get("source_locator")))
        _lg.chunk_done(src.get("source_locator") or cid)   # 이 조각의 값 행 — 붙은 자리까지 끝났다 (B119 ⑤)

    loop.link_mentions(b, ch)                     # 다른 공정 언급 → 관련 링크 (B113 ①)
    _lg.chunk_done(None)
    store.write(store.CHUNKS, ch)
    if not defer_save:          # 인입 경로는 그래프 저장 **뒤**에 사전을 쓴다(B99 ① — entry._finish_build)
        b.flush()
    b.ledger.save()
    return b


def _dict_hit(b, surface, graph, *, category):
    """attach 대상의 사전 해소 — **판정 파이프라인을 재사용한다**(문서 4 §4.4-3).

    **카테고리는 추출이 함께 낸다**(§4.10 규약 8 — B11). 그래서 여기는 그 카테고리
    하나로만 판정한다 — 전 카테고리를 훑지 않으므로 **선언 순서가 답을 정하는 일이
    없다**. 그것이 P-B의 임시 「수렴 판정」이 있던 자리이고, 추출 계약이 카테고리를
    내면서 순회도 수렴 판정도 필요 없어졌다.

    후보를 사전 히트로 **조립만** 하고 판정은 `matcher.match`가 한다 — 사전은 전 층
    단일이라(§7.1) 첫 히트를 조용히 고르면 그것이 판정을 대신하고, 카테고리 불일치
    안전망·극성 후보 제외·생존 판정이 적용되지 않은 선택이 엣지 끝점이 된다.
    """
    cands = []
    hosts = matcher._hosts(category)            # 겸도 부착 대상이다 (B90 ③ — 매칭 후보의 한 자리)
    for nid in b.dict.lookup(surface):
        n = graph.get(nid)
        if not n or not is_live(n) or not matcher._is(n, category, hosts):
            continue
        cands.append({"id": nid, "canonical": n["canonical"],
                      "aliases": [a["surface"] for a in n.get("aliases") or []],
                      "category": n["category"], "layer": n.get("layer"),
                      "polarity": n.get("polarity"), "exact": True,
                      **({"also": [category]} if n["category"] != category else {})})
    if not cands:
        return None
    v = matcher.match(surface, cands, category)
    return v["matched_id"] if v["type"] == matcher.MATCH else None
