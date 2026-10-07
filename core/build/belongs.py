# -*- coding: utf-8 -*-
"""칸 3.4 — **개체의 소속** — 추출이 낸 `belongs_to`를 그래프에 앉힌다 (B102 ④).

추출 계약(B102 ③): 개체마다 `belongs_to: {name, category, from} | null` — 그 개체가 「무엇의 일부 ·
무엇의 특성인가」. 여기서 하는 일 넷:

1. **읽기 한 벌**(`belongs_of`) — 새 계약의 `belongs_to`와 **옛 체크포인트의 `attach`**(관계를 못 고를 때의
   부착 이름)를 같은 뜻으로 읽는다(호환).
2. **출처 대조**(`source_of`) — 이름이 ⑴부착 후보(공정 서브트리) ⑵청크 본문 ⑶맥락 줄(경로·시트·공정) 중
   어디에 있는지 다시 잰다(공백·라틴 대소문자 무시). 어디에도 없으면 **지어낸 것**이라 버린다(결함 로그).
3. **대상 해소**(`resolve_target`) — 골격 이름이면 좌표(조회 전용 · 큐 0) · 골격 밖이면 같은 문서 버퍼 →
   사전(그 카테고리 · 유일할 때) → 없으면 지금의 개체 해소(`resolve_at_home` — 표·산문 같은 함수).
4. **같은 청크 안 순서** — 소속 대상이 같은 청크의 개체면 그것을 먼저(`order`) · 순환이면 소속을 버린다.

엣지 관계는 **카테고리쌍 매핑**(`category_pair_map`)이 정한다 — 코드가 관계 이름을 모른다. 매핑 키는
엣지 방향(`"src,dst"`)이라 소속은 두 방향을 본다(`edge_of` — `Unit,Property: has_property`는 대상 → 개체 ·
`Component,Unit: part_of`는 개체 → 대상).
"""
from __future__ import annotations

from core import matcher
from core.state import store
from core.state.ids import fold_latin, norm
from core.state.status import is_live

SKELETON, NODE = "골격", "노드"


def _k(s):
    return fold_latin(norm(s or "")).replace(" ", "")


def belongs_of(cand):
    """청크 후보의 소속 — `{정규화 표기: {"name", "category", "from", "legacy"?}}`.

    옛 `attach`는 같은 뜻으로 읽는다(`from` 없음 · `legacy: True` — 그때의 계약은 출처를 말하지 않았다)."""
    out = {}
    for e in cand.get("entities") or []:
        b = e.get("belongs_to")
        if b and b.get("name"):
            out[norm(e["surface"])] = {"name": b["name"], "category": b.get("category"),
                                       "from": b.get("from")}
    for a in cand.get("attach") or []:
        k = norm(a.get("surface") or "")
        t = a.get("attach_to") if isinstance(a.get("attach_to"), dict) else (
            {"name": a.get("attach_to"), "category": None} if a.get("attach_to") else None)
        if k and k not in out:
            out[k] = ({"name": t.get("name"), "category": t.get("category"), "from": None,
                       "legacy": True} if t and t.get("name") else None)
    return out


def source_of(name, src, doc=None):
    """이름이 나온 자리 — `본문` · `경로` · `시트` · `공정` · `후보`(부착 후보) 중 처음 맞는 것 · 없으면 None."""
    from core.build import extract_ctx
    from core.build.extract import attach_candidates
    k = _k(name)
    if not k:
        return None
    if k in _k(src.get("text") or ""):
        return "본문"
    for f, v in extract_ctx.context_fields(src, doc):
        if f != "문서" and k in _k(v):
            return f
    if any(_k(c) == k or _k(c).endswith(k) for c in attach_candidates(src.get("process_ref"))):
        return "후보"
    return None


def order(entities, bmap):
    """같은 청크 안 해소 순서 — 소속 대상이 그 청크의 개체면 그것을 먼저 · 순환은 소속을 버린다.

    돌려주는 것은 `(순서대로 개체, 순환으로 버린 표기 집합)`."""
    by = {norm(e["surface"]): e for e in entities}
    seen, out, cyc = set(), [], set()

    def visit(k, path):
        if k in seen:
            return
        if k in path:
            cyc.add(k)
            return
        b = bmap.get(k)
        dep = norm(b["name"]) if b else None
        if dep and dep in by and dep != k:
            visit(dep, path | {k})
        if k not in seen:
            seen.add(k)
            out.append(by[k])

    for e in entities:
        visit(norm(e["surface"]), set())
    return out, cyc


def resolve_target(b, bel, prov, chunk_kw):
    """소속 대상 — `(종류, node_id, 그래프)` 또는 None. 종류는 `골격` | `노드`.

    `chunk_kw`는 청크의 해소 재료(`coord` · `electrode_type` · `parent_canonical` · `anchor_polarity` ·
    `coord_surface`) — 골격 밖 대상을 새로 해소할 때 그 청크의 개체와 같은 규칙으로 이름을 짓는다."""
    from core.state.bootstrap import COORD_CATEGORY
    name, cat = bel.get("name"), bel.get("category")
    if not name:
        return None
    sid, sg = b.resolve_anchor(name, COORD_CATEGORY, prov, defer=[])   # 조회만 — 큐 0
    if sid:
        return SKELETON, sid, sg
    nid = b.buffer.get(norm(name))
    if nid:
        g = b.graph_of(nid) or b.g
        n = g.get(nid) or {}
        if n and (not cat or matcher._is(n, cat, matcher._hosts(cat))):
            return NODE, nid, g
    if not cat or cat not in (b.cfg.get("categories") or {}):
        return None
    g = b.for_category(cat).g
    hosts = matcher._hosts(cat)
    hits = {x for x in b.dict.lookup(name)
            if g.get(x) and is_live(g.get(x)) and matcher._is(g.get(x), cat, hosts)}
    if len(hits) == 1:
        nid = next(iter(hits))
        return NODE, nid, g
    nid, eb = b.resolve_at_home(name, cat, prov, **chunk_kw)
    if nid:
        b.buffer[norm(name)] = nid
        return NODE, nid, eb.g
    return None


def edge_of(cfg, tgt_cat, child_cat):
    """소속 엣지의 `(관계, 대상이 src인가)` — 매핑에 `대상,개체`가 있으면 대상 → 개체 · `개체,대상`이 있으면
    개체 → 대상 · 둘 다 없으면 `(None, None)`. 둘 다 있으면 앞의 것(매핑 표의 선언이 정한다)."""
    from core.build import gate
    rel = gate.pair_relation(cfg, tgt_cat, child_cat)
    if rel:
        return rel, True
    rel = gate.pair_relation(cfg, child_cat, tgt_cat)
    return (rel, False) if rel else (None, None)


def drop_invented(doc_id, surface, bel, cid):
    store.append_defect(f"{doc_id}: 소속 출처 없음 — '{surface}'의 소속 '{bel.get('name')}'"
                        f"(from {bel.get('from')})가 본문·맥락 줄·부착 후보에 없다 @ {cid} → null")
