# -*- coding: utf-8 -*-
"""칸 3.4 — **개체의 소속** — 추출이 낸 `belongs_to`를 그래프에 앉힌다 (B102 ④).

추출 계약(B102 ③): 개체마다 `belongs_to: {name, category, from} | null` — 그 개체가 「무엇의 일부 ·
무엇의 특성인가」. 여기서 하는 일 넷:

1. **읽기 한 벌**(`belongs_of`) — 새 계약의 `belongs_to`와 **옛 체크포인트의 `attach`**(관계를 못 고를 때의
   부착 이름)를 같은 뜻으로 읽는다(호환).
2. **출처 대조**(`source_of`) — 이름이 ⑴부착 후보(공정 서브트리) ⑵청크 본문 ⑶맥락 줄(경로·시트·공정) ⑷제목
   개체(B115 ③ — 제목 글자 안이라 ⑶과 같이 맞는다) 중 어디에 있는지 다시 잰다(공백·라틴 대소문자 무시). 어디에도
   없으면 **지어낸 것**이라 버린다(결함 로그).
3. **대상 해소**(`resolve_target`) — 앞 단은 **이름 조회 한 함수**(`lookup` — 소속 대상 · 관계 끝점 · 이름 없는 대상의 셈이
   같이 쓴다 · B140 ⑤): 골격(조회 전용 · 큐 0) → 같은 문서 버퍼 → 사전(살아 있는 노드 · 카테고리가 오면 그 안 · 하나 · 여럿이면
   청크 좌표 아래로 좁혀 하나) · 못 찾으면 지금의 개체 해소(`resolve_at_home` — 표·산문 같은 함수). 골격 밖 노드의 좌표는
   `coord_of`(스코프를 거슬러 닿는 골격 노드).
4. **같은 청크 안 순서** — 소속 대상이 같은 청크의 개체면 그것을 먼저(`order`) · 순환이면 소속을 버린다.

엣지 관계는 **카테고리쌍 매핑**(`category_pair_map`)이 정한다 — 코드가 관계 이름을 모른다. 매핑 키는
엣지 방향(`"src,dst"`)이라 소속은 두 방향을 본다(`edge_of` — `Unit,Property: has_property`는 대상 → 개체 ·
`Component,Unit: part_of`는 개체 → 대상).
"""
from __future__ import annotations

from core import matcher
from core.state import store
from core.build.naming import scope_of
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
    """이름이 나온 자리 — `본문` · `경로` · `시트` · `공정` · `후보`(부착 후보) 중 처음 맞는 것 · 없으면 None.

    넷째 출처 `제목`(B115 ③ — 개요가 대상으로 정한 제목 개체)은 이름이 제목 글자 안에 있으니(`outline._check`가
    그것만 남긴다) 경로 · 시트 칸에서 같이 맞는다 — 따로 재지 않는다."""
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


#: 소속 대상 판정의 대장 열(B106 ②) — 같은 청크의 개체 행(열 = 카테고리)과 열쇠가 갈린다
FIELD = "소속"


def _home(b, nid):
    """그 노드가 사는 그래프 — 이 빌드가 연 것 먼저 · 없으면 층 전부(읽기)."""
    g = b.graph_of(nid)
    if g is not None:
        return g
    from router import discover
    for lay in discover():
        g = b.for_layer(lay).g
        if g.get(nid):
            return g
    return None


def lookup(b, name, cat=None, *, coord=None, src=None, doc=None):
    """**이름 조회 한 함수**(B140 ⑤) — `(종류, node_id, 그래프)` 또는 None. 노드를 만들지 않고 판정(LLM)도 부르지 않는다 · 큐 0.

    골격(`resolve_anchor` 조회만) → 이 문서 버퍼(카테고리가 오면 그 안) → 사전(살아 있는 노드 · 카테고리가 오면 그 안 · 하나 ·
    여럿이면 `coord`(청크 좌표 id) 아래 — 스코프를 거슬러 그 좌표에 닿는 것만 — 로 좁혀 하나). `src`(청크)가 오면 골격 · 사전 조회는
    그 이름이 그 청크(본문 · 맥락 줄 · 부착 후보)에 있을 때만이다(`source_of` — 지어내지 않는다 · 버퍼는 이 문서 개체라 대조하지 않는다)."""
    from core.state.bootstrap import COORD_CATEGORY
    if not name:
        return None
    hosts = matcher._hosts(cat) if cat else None
    here = src is None or source_of(name, src, doc) is not None
    if here:
        sid, sg = b.resolve_anchor(name, COORD_CATEGORY, None, defer=[])   # 조회만 — 큐 0
        if sid:
            return SKELETON, sid, sg
    nid = b.buffer.get(norm(name))
    if nid:
        g = b.graph_of(nid) or b.g
        n = g.get(nid) or {}
        if n and (not cat or matcher._is(n, cat, hosts)):
            return NODE, nid, g
    if not here or (cat and cat not in (b.cfg.get("categories") or {})):
        return None
    hits = {}
    for x in set(b.dict.lookup(name)):
        g = b.for_category(cat).g if cat else _home(b, x)
        n = g.get(x) if g is not None else None
        if n and is_live(n) and (not cat or matcher._is(n, cat, hosts)):
            hits[x] = g
    if len(hits) > 1 and coord:
        hits = {x: g for x, g in hits.items() if (coord_of(b, x, g)[0] == coord)}
    if len(hits) == 1:
        (x, g), = hits.items()
        return NODE, x, g
    return None


def coord_of(b, nid, g):
    """골격 밖 노드의 **좌표** — 부모 경로(이름 부모 canonical `scope`)를 거슬러 닿는 골격 노드 `(id, 그래프)` · 없으면
    `(None, None)`(B140 ⑤ — 소속 노드의 좌표를 물려받는 재료 · 사전 조회의 좁힘)."""
    from core.build.heading import _is_coord
    from core.state.bootstrap import COORD_CATEGORY
    seen = set()
    while nid and g is not None and nid not in seen and len(seen) < 16:
        seen.add(nid)
        n = g.get(nid) or {}
        if _is_coord(n):
            return nid, g
        scope = scope_of(n)
        if not scope:
            return None, None
        sid, sg = b.resolve_anchor(scope, COORD_CATEGORY, None, defer=[])
        if sid:
            return sid, sg
        ups = []
        for x in set(b.dict.lookup(scope)):              # 스코프 = 위 노드의 canonical — 사전의 조회 키로 등재돼 있다
            hg = _home(b, x)
            hn = hg.get(x) if hg is not None else None
            if hn and is_live(hn) and norm(hn.get("canonical") or "") == norm(scope):
                ups.append((x, hg))
        nid, g = ups[0] if len(ups) == 1 else (None, None)
    return None, None


def resolve_target(b, bel, prov, chunk_kw, at=None):
    """소속 대상 — `(종류, node_id, 그래프)` 또는 None. 종류는 `골격` | `노드`.

    `chunk_kw`는 청크의 해소 재료(`coord` · `electrode_type` · `parent_canonical` · `anchor_polarity` ·
    `coord_surface`) — 골격 밖 대상을 새로 해소할 때 그 청크의 개체와 같은 규칙으로 이름을 짓는다.
    `at`은 그 청크의 자리 `(위치, 열)` — 새로 해소한 판정은 **대장에 한 행**(역할 `belongs`)으로 남아 다음
    재구축이 그 판정을 재생한다(B106 ② — 대장 행이 없던 판정은 재구축마다 LLM을 다시 불렀다)."""
    name, cat = bel.get("name"), bel.get("category")
    if not name:
        return None
    hit = lookup(b, name, cat, coord=(chunk_kw.get("coord") or (None,))[0])   # 앞 단 — 관계 끝점과 같은 함수 (B140 ⑤)
    if hit:
        return hit
    if not cat or cat not in (b.cfg.get("categories") or {}):
        return None
    nid, eb = b.resolve_at_home(name, cat, prov, at=at, **chunk_kw)
    _ledger_row(b, eb, nid, at, name, bel)
    if nid:
        b.buffer[norm(name)] = nid
        return NODE, nid, eb.g
    return None


def _ledger_row(b, eb, nid, at, name, bel):
    """소속 대상 판정 한 행 — 판정이 아는 것을 그대로(산문 개체 행과 같은 열 · 역할만 `belongs`)."""
    from core.build import loop
    last = eb.last or {}
    if b.ledger is None or not at:
        return
    b.ledger.add(locator=at[0], field=at[1], role="belongs", surface=name,
                 canonical=last.get("canonical"), layer=last.get("layer") or b.layer,
                 path=last.get("path") or "none",
                 verdict=loop._VERDICT.get(last.get("verdict"), "pending"), node_id=nid,
                 candidates_n=last.get("candidates_n", 0), confidence=last.get("confidence", 0.0),
                 llm=last.get("llm"), queue_kind=last.get("queue_kind"), nearest=last.get("nearest"),
                 same_doc=last.get("same_doc"), target=b.canonical_of(nid), belongs_from=bel.get("from"),
                 category=last.get("category"), scope=last.get("scope"), replay=last.get("replay"),
                 apart=last.get("apart"), similar=last.get("similar"), basis=last.get("basis"))


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
