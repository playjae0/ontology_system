# -*- coding: utf-8 -*-
"""칸 0.1 곁 — **온톨로지 맵**(B186 ①) — config 지도의 관계 그림을 **카테고리 수준의 지도**로: 점 = 카테고리 · 선 = (src, rel, dst) 하나.

선 하나는 「어떤 카테고리가 어떤 관계로 어떤 카테고리에 이어질 수 있나」이고 출처(config 키)가 여럿이면 선 하나에 함께 적는다.
종류는 셋 — 골격 관계(층 config `skeleton.relations` · 골격 극성 짝 `mirrors`) · 소속(공통 `parent_pairs`) · 사실 관계(층
`relation_patterns` · 등록 스키마 `edges`) — 이고 끝점 카테고리의 `home`이 선언한 층과 다르면 **층을 넘는 관계**(같은 색 점선)다.
**같은 카테고리끼리의 선은 그 점에서 나가 그 점으로 돌아오는 고리**다(실제 그래프에서는 다른 두 노드 사이의 선) — 두 끝이 같은
노드인 엣지(관문이 세우지 않는다 · 문서 1 J32)와 다른 것이다.

실제 엣지 수는 지금 그래프(층 전부 · 사람이 지운 엣지 제외 · 읽기만)에서 센다 — 그래프가 없거나 비었으면(bootstrap 전) 비운다(None). 값 칸
(attributes)은 등록 스키마의 `role: attribute` 칸과 층 `value_categories`다. LLM 0 · 쓰기 0 · 외부 주소 0 · 코드에 층 · 카테고리 이름 0.
"""
from __future__ import annotations

import html
import math

from core.state import catalog

#: 선의 종류 — 앞이 이긴다(같은 삼항이 두 종류의 출처를 가지면 앞 종류로 그린다)
KINDS = ("골격 관계", "소속", "사실 관계")
CROSS = "층을 넘는 관계"
COLORS = {"골격 관계": "#8a8f98", "소속": "#3b7dd8", "사실 관계": "#e07b28"}
_RANK = {k: i for i, k in enumerate(KINDS)}


def _cat_of(fields, name, coord):
    """스키마 엣지 끝 이름 → 카테고리 — 칸이면 그 칸의 카테고리 · `@` 참조가 칸이 아니면 좌표 카테고리(좌표 참조)."""
    f = fields.get(str(name or "").lstrip("@")) or {}
    c = f.get("category") or f.get("target_category")
    return c or (coord if str(name or "").startswith("@") else None)


def lines(configs, schemas, pair_edges, cats, coord):
    """**선 목록** — `[{src, rel, dst, kind, cross, sources, layers, symmetric}]` · 이름순 · 결정적."""
    acc = {}

    def add(s, rel, d, kind, source, layer=None, symmetric=False):
        if not (s and rel and d):
            return
        x = acc.setdefault((s, rel, d), {"src": s, "rel": rel, "dst": d, "kind": kind, "sources": set(), "layers": set(),
                                         "symmetric": False})
        if _RANK[kind] < _RANK[x["kind"]]:
            x["kind"] = kind
        x["sources"].add(source)
        if layer:
            x["layers"].add(layer)
        x["symmetric"] |= bool(symmetric)

    for lay, cfg in sorted(configs.items()):
        sk = cfg.get("skeleton") or {}
        c = sk.get("category")
        if c:
            for k, rel in sorted((sk.get("relations") or {}).items()):
                add(c, rel, c, KINDS[0], f"skeleton.relations.{k}", lay)
            mir = cfg.get("mirrors") or {}
            if mir.get("enabled") and mir.get("relation") and (cfg.get("polarity") or {}).get("values"):
                add(c, mir["relation"], c, KINDS[0], "mirrors", lay, True)     # 골격이 심는 극성 짝
        for p in cfg.get("relation_patterns") or []:
            add(p.get("src"), p.get("rel"), p.get("dst"), KINDS[2], "relation_patterns", lay, p.get("symmetric"))
    for s, r, d in pair_edges:
        add(s, r, d, KINDS[1], catalog.PAIRS, (cats.get(s) or {}).get("home"))
    for dt, sc, fields in schemas:
        for e in sc.get("edges") or []:
            add(_cat_of(fields, e.get("from"), coord), e.get("relation"), _cat_of(fields, e.get("to"), coord), KINDS[2],
                f"schema: {dt}", sc.get("layer"))
    out = []
    for (s, r, d), x in sorted(acc.items()):
        homes = {(cats.get(c) or {}).get("home") for c in (s, d)}
        out.append({**x, "sources": sorted(x["sources"]), "layers": sorted(x["layers"]),
                    "cross": len(homes) > 1 or any(lay not in homes for lay in x["layers"])})
    return out


def attributes(configs, schemas, coord):
    """**값 칸**(attributes) — `[{category, attribute, where, contextual, layer}]` · 스키마 `role: attribute` 칸 · 층 `value_categories`."""
    rows = []
    for dt, sc, fields in schemas:
        for name, f in sorted(fields.items()):
            if isinstance(f, dict) and f.get("role") == "attribute":
                rows.append({"category": _cat_of(fields, f.get("attach_to_field"), coord), "attribute": f.get("attr_name") or name,
                             "where": f"schema: {dt} · {name}", "contextual": bool(f.get("contextual")), "layer": sc.get("layer")})
    for lay, cfg in sorted(configs.items()):
        vc = cfg.get("value_categories")
        for c, a in sorted(vc.items()) if isinstance(vc, dict) else ():
            rows.append({"category": c, "attribute": a, "where": f"value_categories ({lay})", "contextual": False, "layer": lay})
    return sorted(rows, key=lambda x: (str(x["category"]), str(x["attribute"]), x["where"]))


def edge_counts(layers):
    """**실제 엣지 수** — `({(src 카테고리, rel, dst 카테고리): 수}, [(주 카테고리 삼항, 주 ∪ 겸 조합)])` · 그래프가 없거나 비면 `(None, None)`.

    층 전부를 연다(노드는 집 층 · 엣지는 문서 층 — B100) · 사람이 지운 엣지는 빼고 · 카테고리는 주 ∪ 겸(관문이 겸으로도 판정한다)."""
    from core.graph import STATUS_DELETED, GraphStore
    stores = [GraphStore.for_layer(lay) for lay in sorted(layers)]
    graphs = [s.load() for s in stores if s.exists()]
    if not any(g.nodes for g in graphs):                     # 그래프가 없다 · 비었다(bootstrap 전) — 수 칸을 비운다
        return None, None
    nodes = {nid: n for g in graphs for nid, n in g.nodes.items()}
    by, each = {}, []
    for g in graphs:
        for e in g.edges:
            a, b = nodes.get(e["src"]), nodes.get(e["dst"])
            if not a or not b or e.get("status") == STATUS_DELETED:
                continue
            combos = {(s, e["rel"], d) for s in catalog.categories_of(a) for d in catalog.categories_of(b)}
            for k in combos:
                by[k] = by.get(k, 0) + 1
            each.append(((a.get("category"), e["rel"], b.get("category")), combos))
    return by, each


def same_node_counts():
    """관문이 세우지 않은 **같은 노드 엣지** — `{(src 카테고리, rel, dst 카테고리): 수}`(거부 기록 · 읽기만)."""
    from core.build import gate
    from core.state import store
    out = {}
    for x in store.read(store.GATE_REJECTS, {"rejects": []}).get("rejects") or []:
        if x.get("verdict") == gate.SAME_NODE:
            k = (x.get("src_cat"), x.get("rel"), x.get("dst_cat"))
            out[k] = out.get(k, 0) + 1
    return out


def build(configs, schemas, pair_edges, cats, coord, layers):
    """모델의 `ontology` 칸 — `{lines, attributes, unknown}` · 선마다 `edges`(실제 엣지 수 · 그래프 없으면 None) · `same_node`."""
    ls = lines(configs, schemas, pair_edges, cats, coord)
    by, each = edge_counts(layers)
    same = same_node_counts()
    for x in ls:
        k = (x["src"], x["rel"], x["dst"])
        x["edges"] = None if by is None else by.get(k, 0)
        x["same_node"] = same.get(k, 0)
    known = {(x["src"], x["rel"], x["dst"]) for x in ls}
    miss = {}
    for main, combos in each or ():                          # 주 ∪ 겸 조합 중 하나라도 선이면 출처가 있다(관문이 겸으로도 판정한다)
        if not combos & known:
            miss[main] = miss.get(main, 0) + 1
    unknown = sorted([list(k) + [n] for k, n in miss.items()])
    return {"lines": ls, "attributes": attributes(configs, schemas, coord), "unknown": unknown}


def check_lines(onto):
    """점검 「표시」 — 그래프에 있는데 어느 출처에도 없는 삼항(그 층 config · 스키마에 없는 관계로 선 엣지)."""
    return [("표시", f"그래프에 있는데 어느 출처에도 없는 삼항 — {s} -{r}-> {d} 엣지 {n:,} · 지도의 선이 아니다(config에 없는 길)")
            for s, r, d, n in onto.get("unknown") or []]


def counts(onto):
    """요약의 수 — 선 · 고리 · 종류별 · 층을 넘는 관계 · 선언만."""
    ls = onto.get("lines") or []
    out = {"선": len(ls), "고리": sum(1 for x in ls if x["src"] == x["dst"])}
    out.update({k: sum(1 for x in ls if x["kind"] == k) for k in KINDS})
    out[CROSS] = sum(1 for x in ls if x["cross"])
    out["선언만"] = sum(1 for x in ls if x["edges"] == 0)
    return out


# ---------------------------------------------------------------- 그림 (인라인 SVG — 외부 주소 0)
NODE_R, LOOP_OUT, LOOP_SPREAD = 22, 62, 62


def layout(model):
    """점 자리 — 원 위에 home 층 · 이름순(결정적) · `{카테고리: (x, y)}` · 크기 `(w, h)`."""
    cats = sorted(model["categories"], key=lambda c: (str(model["categories"][c].get("home") or "~"), c))
    n = max(1, len(cats))
    r = 120 + 34 * n
    w = h = 2 * (r + NODE_R + LOOP_OUT + 50)
    cx = cy = w / 2
    pos = {c: (round(cx + r * math.cos(-math.pi / 2 + 2 * math.pi * i / n), 1),
               round(cy + r * math.sin(-math.pi / 2 + 2 * math.pi * i / n), 1)) for i, c in enumerate(cats)}
    return pos, (round(w), round(h)), (cx, cy)


def loops(model, pos, center):
    """고리마다 `(선, 시작 · 끝 · 조절점 둘 · 꼭짓점)` — 한 점의 고리들은 바깥 방향을 가운데로 각도를 벌려 서로 겹치지 않는다."""
    cx, cy = center
    by = {}
    for x in model["ontology"]["lines"]:
        if x["src"] == x["dst"] and x["src"] in pos:
            by.setdefault(x["src"], []).append(x)
    out = []
    for c, ls in sorted(by.items()):
        x0, y0 = pos[c]
        base = math.atan2(y0 - cy, x0 - cx) if (x0, y0) != (cx, cy) else -math.pi / 2
        for i, ln in enumerate(ls):
            a = base + math.radians(LOOP_SPREAD) * (i - (len(ls) - 1) / 2)
            pt = lambda ang, d: (round(x0 + d * math.cos(ang), 1), round(y0 + d * math.sin(ang), 1))   # noqa: E731
            w = math.radians(12)
            out.append((ln, pt(a - w, NODE_R), pt(a + w, NODE_R), pt(a - 2.2 * w, NODE_R + LOOP_OUT * 1.25),
                        pt(a + 2.2 * w, NODE_R + LOOP_OUT * 1.25), pt(a, NODE_R + LOOP_OUT)))
    return out


def _label(x):
    n = x["edges"]
    return f"{x['rel']} · " + ("선언만" if n == 0 else "엣지 —" if n is None else f"엣지 {n:,}")


def _stroke(x):
    return (f'stroke="{COLORS[x["kind"]]}" stroke-width="1.8" fill="none"'
            + (' stroke-dasharray="6 4"' if x["cross"] else "") + (' opacity="0.55"' if x["edges"] == 0 else "")
            + f' marker-end="url(#a-{_RANK[x["kind"]]})"' + (f' marker-start="url(#s-{_RANK[x["kind"]]})"' if x["symmetric"] else ""))


def svg(model, node_color):
    """지도 한 장(인라인 SVG) — 점 = 카테고리(색 = home 층) · 선 = 종류 색 · 층을 넘는 관계는 점선 · 고리는 점 바깥 · 선마다 rel · 엣지 수."""
    pos, (w, h), center = layout(model)
    e = html.escape
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="omap" viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'aria-label="ontology map"><defs>']
    for k, i in _RANK.items():
        out.append(f'<marker id="a-{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                   f'<path d="M0,0 L10,5 L0,10 z" fill="{COLORS[k]}"/></marker>'
                   f'<marker id="s-{i}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                   f'<path d="M10,0 L0,5 L10,10 z" fill="{COLORS[k]}"/></marker>')
    out.append("</defs>")
    pair = {}
    for x in model["ontology"]["lines"]:
        if x["src"] != x["dst"] and x["src"] in pos and x["dst"] in pos:
            pair.setdefault(frozenset((x["src"], x["dst"])), []).append(x)
    for _k, ls in sorted(pair.items(), key=lambda kv: sorted(kv[0])):
        for i, x in enumerate(ls):
            (x1, y1), (x2, y2) = pos[x["src"]], pos[x["dst"]]
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy) or 1
            ux, uy = dx / dist, dy / dist
            sx, sy, tx, ty = x1 + ux * NODE_R, y1 + uy * NODE_R, x2 - ux * NODE_R, y2 - uy * NODE_R
            side = 1 if x["src"] < x["dst"] else -1                     # 방향이 반대인 선은 반대쪽으로 휜다
            off = side * 30 * (i - (len(ls) - 1) / 2 + (0.5 if len(ls) % 2 == 0 else 0)) if len(ls) > 1 else 0
            mx, my = (sx + tx) / 2 - uy * off, (sy + ty) / 2 + ux * off
            out.append(f'<path class="line" data-line="{e(x["src"])}|{e(x["rel"])}|{e(x["dst"])}" '
                       f'd="M{sx:.1f},{sy:.1f} Q{mx:.1f},{my:.1f} {tx:.1f},{ty:.1f}" {_stroke(x)}/>'
                       f'<text x="{mx:.1f}" y="{my - 4:.1f}" class="lab" text-anchor="middle">{e(_label(x))}</text>')
    for x, a, b, c1, c2, top in loops(model, pos, center):
        out.append(f'<path class="loop" data-line="{e(x["src"])}|{e(x["rel"])}|{e(x["dst"])}" data-apex="{top[0]},{top[1]}" '
                   f'd="M{a[0]},{a[1]} C{c1[0]},{c1[1]} {c2[0]},{c2[1]} {b[0]},{b[1]}" {_stroke(x)}/>'
                   f'<text x="{top[0]}" y="{top[1]}" class="lab" text-anchor="middle">{e(_label(x))}</text>')
    for c, (x, y) in sorted(pos.items()):
        home = (model["categories"][c] or {}).get("home")
        out.append(f'<g class="cat" data-cat="{e(c)}"><circle cx="{x}" cy="{y}" r="{NODE_R}" fill="{node_color(home)}" '
                   f'fill-opacity="0.85"/><text x="{x}" y="{y + NODE_R + 14}" class="name" text-anchor="middle">{e(c)}</text></g>')
    out.append("</svg>")
    return "".join(out)
