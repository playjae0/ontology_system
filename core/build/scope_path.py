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


def _dict_ver(b):
    """사전의 판 — 그 사전 객체 · 고친 횟수(`Dictionary.version`) · 판이 없는 사전이면 None(기억하지 않는다)."""
    v = getattr(b.dict, "version", None)
    return None if v is None else (id(b.dict), v)


def walk(b, scope):
    """부모 경로 글자 → `(공정 id, 공정 그래프, [(소유자 id, 그래프) — 가까운 것부터])` · 공정에 닿지 못하면 공정 칸이 None.

    한 빌더 안에서는 글자마다 한 번 걷는다(닿은 것은 빌더 수명 동안 · 그 사이 노드가 지워지지 않는다). **닿지 못한 걸음도
    기억한다**(B144 ①) — 사전의 판(`_dict_ver`)이 같은 동안만: 위 노드가 새로 등재되면 다시 걷는다(못 닿던 글자가 닿을 수 있다)."""
    from core.state.bootstrap import COORD_CATEGORY
    memo = b.__dict__.setdefault("_walks", {})
    key = norm(scope or "")
    if key in memo:
        return memo[key]
    miss = b.__dict__.setdefault("_walk_miss", {})
    ver = _dict_ver(b)
    if ver is not None and key in miss and miss[key][0] == ver:
        return None, None, miss[key][1]
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
    if ver is not None:
        miss[key] = (ver, owners)
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


def names(b, n):
    """`names_of`를 빌더(문서 하나)에 노드마다 한 번(B144 ①) — 이름 · 맨 이름 · 별칭 수가 바뀌면 그 노드만 다시 잰다."""
    memo = b.__dict__.setdefault("_names", {})
    sig = (n.get("canonical"), base_name_of(n), len(n.get("aliases") or ()))
    k = n.get("id") or id(n)
    hit = memo.get(k)
    if hit is None or hit[0] != sig:
        hit = memo[k] = (sig, names_of(n))
    return hit[1]


def _emb_similar(a, b, mode):
    """두 소유자 이름의 임베딩 유사도가 문턱 이상인가 — 임베딩을 쓰는 실행에서만(`mode` — 좁히기 방법 · 겹침 실행은 False)."""
    if mode != "embed":
        return False
    from core import matcher
    from core.llm import embeddings
    na, nb = base_name_of(a) or a.get("canonical"), base_name_of(b) or b.get("canonical")
    return embeddings.cosine(matcher._vec(na), matcher._vec(nb)) * 100 >= OWNER_SIMILAR_PCT


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
        self.parent_key = norm(parent or "")
        self.apart, self.similar = [], []
        # **값 하나에 한 번**(B144 ①) — 후보마다 다시 재던 것: 좁히기 방법 · 값의 사전 조회 · 줄기 · 같은 근거와의 관계
        self._mode = self._ids = self._fold = None
        self._stem, self._rel = {}, {}

    def names(self):
        """판정 입력의 경로 — 공정부터 가장 가까운 소유자까지(이름)."""
        return [_label(self.proc[1], self.proc[0])] + [_label(g, x) for x, g in reversed(self.owners)]

    def path_of(self, nid, g):
        p, pg, ow = walk_node(self.b, nid, g)
        return ([_label(pg, p)] if p else []) + [_label(og, x) for x, og in reversed(ow)]

    def in_stem(self, p, pg):
        """그 공정이 값의 공정 줄기 안인가 — 공정마다 한 번."""
        if p not in self._stem:
            self._stem[p] = stem(self.b, self.proc, (p, pg))
        return self._stem[p]

    def relation(self, nid, g):
        """후보 하나와의 관계 — 위 표의 닫힌 다섯 · 같은 공정 · 같은 소유자 근거면 값마다 한 번 잰다."""
        n = (g.get(nid) if g is not None else None) or {}
        if self.parent and norm(scope_of(n) or "") == self.parent_key:
            return SAME
        p, pg, ow = walk_node(self.b, nid, g)
        key = (p, tuple(x for x, _g in ow))
        if key not in self._rel:
            self._rel[key] = self._relation(p, pg, ow)
        return self._rel[key]

    def _relation(self, p, pg, ow):
        if not self.in_stem(p, pg):
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
        return SIMILAR if self.owner_similar(ag.get(a) or {}, ow[0][1].get(ow[0][0]) or {}) else APART

    def owner_similar(self, a, b):
        """소유자 둘(다른 노드)의 이름이 비슷한가 — 이름 · 별칭 · 라틴 접기 겹침 · 임베딩 유사도(문턱 손잡이)."""
        if names(self.b, a) & names(self.b, b):
            return True
        if self._mode is None:
            from core.llm import narrow
            self._mode = narrow.narrow_choice()[0]
        return _emb_similar(a, b, self._mode)

    def same_name(self, nid, n, dictionary):
        """그 후보가 들어온 값과 **같은 이름**인가 — 사전 표기(원 표기 키) · 맨 이름 · 별칭 · 라틴 접기(공백 무시)."""
        if not self.base:
            return False
        if self._ids is None:
            self._ids = set(dictionary.lookup(self.base))
            self._fold = fold_latin(self.base).replace(" ", "")
        if nid in self._ids:
            return True
        return self._fold in names(self.b, n)


class _Index:
    """**공정 색인**(B144 ①) — 문서 하나(빌더) 동안 그래프의 노드를 `(카테고리, 단)` → 부모 경로 글자(norm) → [id]로 한 번
    나눠 둔다(골격 노드는 제 id로 — 제가 공정이다). 노드가 늘면 그 노드만 더한다(그래프 노드는 빌드 중 지워지지 않고 더해지기만 한다 ·
    줄면 다시 나눈다). 값은 같은 공정 줄기 · 같은 부모 경로 글자의 묶음만 훑는다 — 다른 줄기는 관문이 어차피 뺀다(`Place.relation`의
    `OTHER`와 같은 판정 · 결과 그대로)."""

    def __init__(self, g):
        self.g, self.n, self.pos, self.groups = g, 0, {}, {}

    def sync(self):
        nodes = self.g.nodes
        if len(nodes) < self.n:
            self.n, self.pos, self.groups = 0, {}, {}
        if len(nodes) == self.n:
            return self
        from itertools import islice
        for nid in islice(nodes, self.n, None):
            n = nodes[nid] or {}
            self.pos[nid] = len(self.pos)
            grp = self.groups.setdefault((n.get("category"), n.get("tier")), ({}, []))
            if _coord(n):
                grp[1].append(nid)
            else:
                sc = scope_of(n)
                if sc:
                    grp[0].setdefault(norm(sc), (sc, []))[1].append(nid)
        self.n = len(nodes)
        return self


def stem_nodes(pl, g, category, hosts):
    """값의 공정 줄기 안 노드 id(그래프 차례 그대로) — 그 카테고리(주 ∪ 겸)의 묶음에서 부모 경로가 값의 이름 부모와 같거나 걸음이
    줄기 안 공정에 닿는 것 · 골격 노드는 제가 줄기 안일 때. 나머지 거르기(살아 있음 · 층 · 극성 …)는 호출부(`matcher.gated`)가 그대로."""
    idx = pl.b.__dict__.setdefault("_pidx", {})
    ix = idx.get(id(g))
    if ix is None or ix.g is not g:
        ix = idx[id(g)] = _Index(g)
    ix.sync()
    out = []
    for (cat, tier), (scopes, coords) in ix.groups.items():
        if cat != category and tier not in (hosts.get(cat) or ()):
            continue
        for key, (sc, ids) in scopes.items():
            if (pl.parent and key == pl.parent_key) or pl.in_stem(*walk(pl.b, sc)[:2]):
                out += ids
        for nid in coords:
            n = g.get(nid) or {}
            if (pl.parent and norm(scope_of(n) or "") == pl.parent_key) or pl.in_stem(nid, g):
                out.append(nid)
    return sorted(out, key=ix.pos.__getitem__)


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
