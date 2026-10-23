# -*- coding: utf-8 -*-
"""칸 3.4 — **부모 경로** — 공정 줄기 · 소유자 사슬 · 경로 호환 (B142 ①②③).

**이름이 기준이고 경로는 증거다**(열쇠가 아니다). 노드의 부모 경로(`naming.scope_of` — 이름 부모 canonical 글자)를 사전의
canonical 키로 풀어 **노드로** 거슬러 간다(가까운 것부터 — `walk`): 닿는 골격 노드가 그 노드의 **공정**이고 가는 길의 노드가
**소유자 사슬**이다(`belongs.coord_of`도 이 걸음이다). 판정의 관문은 카테고리와 **공정 줄기**(같은 공정이거나 골격에서 한쪽이
다른 쪽의 위 · 아래)뿐이고, 사슬은 들어온 값과 후보를 견주는 재료다(`Place.relation`):

    공정 줄기가 다름                                         OTHER    후보가 아니다(LLM 0)
    둘 다 소유자 없음 · 같은 공정                            SAME
    한쪽 경로 없음 · 공정 칸 높이만 다름                      COMPAT
    가장 가까운 소유자가 같은 노드                            SAME
    한쪽 사슬이 다른 쪽의 가까운 소유자를 품음(깊이만 다름)    COMPAT
    소유자가 다른 노드 · 이름 비슷(이름 · 별칭 · 라틴 접기 ·   SIMILAR  LLM 판정(입력에 두 경로)
      임베딩 유사도 ≥ `OWNER_SIMILAR_PCT`)
    소유자가 다른 노드 · 뚜렷이 다름                          APART    다른 것 — 후보에서 뺀다

부모 경로 글자가 들어온 값의 이름 부모와 **같으면** 걷지 않고 SAME이다(지금의 이름 규칙 그대로 — 같은 글자는 같은 자리).
후보의 공정에 닿지 못하면(사슬이 끊겼다) OTHER다 — 모르는 자리를 근거로 붙이지 않는다. 들어온 값의 소유자는 호출부가 준다
(산문 — 소속 대상 노드 · 표 — 같은 행의 소유 엣지 개체 `table_owners` · 제목 — 위 제목 개체) · 이름 규칙이 소유자를 싣는
카테고리(`nest_categories`)일 때만이다(이름과 같은 재료).
"""
from __future__ import annotations

from core.build.naming import base_name_of, nest_categories, scope_of
from core.state.ids import fold_latin, norm
from core.state.status import is_live

OTHER, SAME, COMPAT, SIMILAR, APART = "다른 줄기", "같은 소유자", "경로 호환", "소유자 갈림(이름 비슷)", "소유자 갈림"
#: 판정에 오르는 관계(나머지는 후보에서 뺀다)
KEEP = (SAME, COMPAT, SIMILAR)
#: **소유자 이름 비슷**의 임베딩 문턱(%) — 사내 손잡이 `owner_similar_pct`(창작 기본값 · 임베딩을 쓰는 실행에서만 —
#: 겹침 실행(mock 기본)은 이름 · 별칭 · 라틴 접기만 본다)
OWNER_SIMILAR_PCT = 85
#: 사슬 길이 상한(순환 방어 — 골격 깊이보다 넉넉히)
MAX_DEPTH = 16


def _coord(n):
    from core.build.heading import _is_coord
    return _is_coord(n)


def _homes(b, x):
    from core.build.belongs import _home
    return _home(b, x)


def walk(b, scope):
    """부모 경로 글자 → `(공정 id, 공정 그래프, [(소유자 id, 그래프) — 가까운 것부터])` · 공정에 닿지 못하면 공정 칸이 None.

    한 빌더 안에서는 글자마다 한 번 걷는다(닿은 것만 기억 — 문서 하나의 빌더 수명 · 그 사이 노드가 지워지지 않는다)."""
    from core.state.bootstrap import COORD_CATEGORY
    memo = b.__dict__.setdefault("_walks", {})
    key = norm(scope or "")
    if key in memo:
        return memo[key]
    owners, seen = [], set()
    while scope and norm(scope) not in seen and len(seen) < MAX_DEPTH:
        seen.add(norm(scope))
        sid, sg = b.resolve_anchor(scope, COORD_CATEGORY, None, defer=[])   # 조회만 — 큐 0
        if sid:
            memo[key] = (sid, sg, owners)
            return memo[key]
        ups = []
        for x in set(b.dict.lookup(scope)):          # 부모 경로 = 위 노드의 canonical — 사전의 조회 키로 등재돼 있다
            hg = _homes(b, x)
            hn = hg.get(x) if hg is not None else None
            if hn and is_live(hn) and norm(hn.get("canonical") or "") == norm(scope):
                ups.append((x, hg))
        if len(ups) != 1:
            break
        x, hg = ups[0]
        if _coord(hg.get(x)):
            memo[key] = (x, hg, owners)
            return memo[key]
        owners.append((x, hg))
        scope = scope_of(hg.get(x))
    return None, None, owners


def walk_node(b, nid, g):
    """노드 → `(공정 id, 그래프, 소유자 사슬)` — 골격 노드면 자기 자신이 공정이다(소유자 없음)."""
    n = (g.get(nid) if g is not None else None) or {}
    if not n:
        return None, None, []
    if _coord(n):
        return nid, g, []
    return walk(b, scope_of(n))


def _ancestors(b, pid, pg):
    """골격의 위 공정들(canonical) — 좌표 카테고리를 선언한 층의 골격 자식 관계(`Builder._parent_map`)."""
    from core.state.bootstrap import COORD_CATEGORY
    pm = b._parent_map(pg, COORD_CATEGORY)
    out, cur = [], (pg.get(pid) or {}).get("canonical")
    while cur in pm and len(out) < MAX_DEPTH:
        cur = pm[cur]
        out.append(cur)
    return out


def stem(b, p, q):
    """**공정 줄기** — 같은 공정이거나 골격에서 한쪽이 다른 쪽의 위 · 아래 · `p` · `q`는 `(id, 그래프)`."""
    if not p[0] or not q[0]:
        return False
    if p[0] == q[0]:
        return True
    pc, qc = (p[1].get(p[0]) or {}).get("canonical"), (q[1].get(q[0]) or {}).get("canonical")
    return pc in _ancestors(b, *q) or qc in _ancestors(b, *p)


def names_of(n):
    """견줄 이름들 — 맨 이름 · canonical · 별칭(라틴 접기 · 공백 무시)."""
    out = {base_name_of(n) or "", n.get("canonical") or ""} | {a.get("surface") or "" for a in n.get("aliases") or []}
    return {fold_latin(x).replace(" ", "") for x in out if x}


def _emb_similar(a, b):
    """두 소유자 이름의 임베딩 유사도가 문턱 이상인가 — 임베딩을 쓰는 실행에서만(겹침 실행은 False)."""
    from core.llm import embeddings, narrow
    if narrow.narrow_choice()[0] != "embed":
        return False
    from core import matcher
    na, nb = base_name_of(a) or a.get("canonical"), base_name_of(b) or b.get("canonical")
    return embeddings.cosine(matcher._vec(na), matcher._vec(nb)) * 100 >= OWNER_SIMILAR_PCT


def owner_similar(a, b):
    """소유자 둘(다른 노드)의 이름이 비슷한가 — 이름 · 별칭 · 라틴 접기 겹침 · 임베딩 유사도(문턱 손잡이)."""
    return bool(names_of(a) & names_of(b)) or _emb_similar(a, b)


def _label(g, nid):
    n = (g.get(nid) if g is not None else None) or {}
    return base_name_of(n) or n.get("canonical")


class Place:
    """**들어온 값의 자리** — 공정 · 소유자 사슬 · 이름 부모 글자 · 맨 이름. 후보 조립(`matcher.candidates`)이 후보마다
    `relation`을 묻고, 판정 입력의 「경로」(`names`)를 받는다. 견준 사실(다른 소유자 아래 같은 이름 · 소유자 이름 비슷)은
    `apart` · `similar`에 쌓여 대장 행이 옮긴다(화면 줄 · `show report --md`)."""

    def __init__(self, b, coord, owner, surface, parent):
        self.b = b
        self.proc = tuple(coord) if coord and coord[0] else (None, None)
        self.owners = ([tuple(owner)] + walk_node(b, *owner)[2]) if owner and owner[0] else []
        self.base = norm(surface or "")
        self.parent = parent
        self.apart, self.similar = [], []

    def names(self):
        """판정 입력의 경로 — 공정부터 가장 가까운 소유자까지(이름)."""
        return [_label(self.proc[1], self.proc[0])] + [_label(g, x) for x, g in reversed(self.owners)]

    def path_of(self, nid, g):
        p, pg, ow = walk_node(self.b, nid, g)
        return ([_label(pg, p)] if p else []) + [_label(og, x) for x, og in reversed(ow)]

    def relation(self, nid, g):
        """후보 하나와의 관계 — 위 표의 닫힌 다섯."""
        n = (g.get(nid) if g is not None else None) or {}
        if self.parent and norm(scope_of(n) or "") == norm(self.parent):
            return SAME
        p, pg, ow = walk_node(self.b, nid, g)
        if not stem(self.b, self.proc, (p, pg)):
            return OTHER
        mine = [x for x, _g in self.owners]
        theirs = [x for x, _g in ow]
        if not mine and not theirs:
            return SAME if self.proc[0] == p else COMPAT
        if not mine or not theirs:
            return COMPAT
        if mine[0] == theirs[0]:
            return SAME
        if mine[0] in theirs or theirs[0] in mine:
            return COMPAT
        a, ag = self.owners[0]
        return SIMILAR if owner_similar(ag.get(a) or {}, ow[0][1].get(ow[0][0]) or {}) else APART

    def same_name(self, nid, n, dictionary):
        """그 후보가 들어온 값과 **같은 이름**인가 — 사전 표기(원 표기 키) · 맨 이름 · 별칭 · 라틴 접기(공백 무시)."""
        if not self.base:
            return False
        if nid in set(dictionary.lookup(self.base)):
            return True
        return fold_latin(self.base).replace(" ", "") in names_of(n)


def place(b, category, coord, owner, surface, parent):
    """판정의 자리 — 이름 규칙 카테고리이고 이름 부모가 있을 때만(아니면 None — 관문이 없다 · 지금 그대로). 소유자는 이름이
    소유자를 싣는 카테고리(`nest_categories`)일 때만 넘긴다 — 이름과 같은 재료다."""
    from core.build.naming import scope_categories
    if category not in scope_categories(b.cfg) or not parent:
        return None
    return Place(b, coord, owner if category in nest_categories(b.cfg) else None, surface, parent)


def table_owners(schema, cfg):
    """**표 행의 소유자**(B142 ③) — `{개체 열: 소유자 열}`. 같은 행에 스키마가 선언한 엣지 중 그 두 열의 카테고리쌍 매핑
    (`belongs.edge_of` — 산문 소속과 같은 표)이 정한 관계 · 방향과 같은 것만 소유 엣지다(예 `설비 has_property 관리항목`) ·
    소유를 싣는 카테고리(`nest_categories`)의 열만 · 여럿이면 스키마의 앞 엣지. 좌표(`@`) 끝점은 소유자가 아니다(공정은 이미 자리다)."""
    from core.build.belongs import edge_of
    fields = schema.get("fields") or {}
    nest = set(nest_categories(cfg))
    cat = {f: s.get("category") for f, s in fields.items() if s.get("role") == "entity"}
    out = {}
    for e in schema.get("edges") or []:
        a, z = e.get("from"), e.get("to")
        if a not in cat or z not in cat:
            continue
        for owner, child in ((a, z), (z, a)):
            if child in out or cat.get(child) not in nest:
                continue
            rel, fwd = edge_of(cfg, cat[owner], cat[child])
            if rel == e.get("relation") and fwd == (owner == a):
                out[child] = owner
    return out


def owner_first(fields, owners):
    """열 순서 — 소유자 열을 그 개체 열보다 먼저(같은 행 안 · `belongs.order`와 같은 결 · 순환이면 스키마 순서 그대로)."""
    order, seen = [], set()

    def visit(f, path):
        if f in seen or f in path:
            return
        o = owners.get(f)
        if o and o in fields:
            visit(o, path | {f})
        seen.add(f)
        order.append(f)

    for f in fields:
        visit(f, set())
    return order
