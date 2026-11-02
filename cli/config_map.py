# -*- coding: utf-8 -*-
"""칸 0.1 — **config 지도 모델**(B173 · 읽기만): 층 · 카테고리 · 층 사이 연결 포인트 · 점검을 한 모델로 모은다.

코드가 이미 읽는 자리를 부른다 — 층 config(`bootstrap.load_config`) · 카탈로그(`catalog` — 집 · 겸 · 이름 규칙 ·
선언한 층) · 좌표 층(`bootstrap.coord_layer`) · 등록부(`registry` — 스키마 · 렌즈) · 골격(층 그래프의 seed 노드 —
GraphStore 경유 · 읽기만). **지도는 config 파일의 모양이 아니라 코드가 읽어 낸 내용**이다 — 파일 모양이 바뀌어도
모델은 그대로 쓰인다(다음 회차의 옛 모양 ↔ 새 모양 대조가 이 모델의 `--diff`다).

**판정은 있는 함수를 부른다**(같은 판정의 두 번째 자리 0): 거부 = 카탈로그 `problems`(층 이름 = 폴더 이름 ⓕ 포함) ·
등록 스키마 재대조 FAIL(`cli.register.recheck.run` — G4C · G4D · G4E) / 경고 = 카탈로그 `warnings` · `mirror_warnings` ·
재대조 ⚠. **없는 것만 더한다**(`new_checks`): 여러 층이 같은 관계 이름을 선언(표시 — 같은 이름은 모든 층에서 같은 뜻 ·
사람이 본다) · 관계 패턴의 관계가 그 층 `relations`에 없음(경고) · 정의문이 빈 카테고리(경고).

LLM 0 · 그래프 · config · 등록 쓰기 0 · 코드에 층 · 카테고리 이름 0. 모델은 이름순이고 결정적이다(같은 상태면 JSON 바이트가 같다).
"""
from __future__ import annotations

from core import paths
from core.state import catalog, registry
from core.state.bootstrap import COORD_CATEGORY, NoCoordLayer, coord_layer, load_config, open_graph
from core.state.status import is_live
from router import discover

MAP_VERSION = 1
#: 점검 갈래 — 거부(인입 · bootstrap이 멈춘다) · 경고(막지 않는다 · 고칠 거리) · 표시(사람이 본다)
LEVELS = ("거부", "경고", "표시")


def _first_line(text):
    return (str(text or "").strip().splitlines() or [""])[0].strip()


def _configs():
    """`{층: 층 config}` — 읽는 자리 하나(`load_config` — 이름 규칙은 공통 config의 것을 얹는다)."""
    return {lay: load_config(lay) for lay in sorted(discover())}


def _pattern(p):
    return {"src": p.get("src"), "rel": p.get("rel"), "dst": p.get("dst"), "symmetric": bool(p.get("symmetric"))}


def _skeleton(lay, cfg):
    """골격 — 종류 · 카테고리 · 그 층 그래프의 seed 노드 수(골격이 심긴 만큼 · 심기 전이면 0)."""
    skel = cfg.get("skeleton") or {}
    if not skel:
        return None
    cat = skel.get("category")
    g = open_graph(lay)
    n = sum(1 for x in g.nodes.values() if x.get("category") == cat and x.get("status") == "seed" and is_live(x))
    return {"type": skel.get("type"), "category": cat, "nodes": n}


def _lenses():
    """`{층: [그 층을 렌즈로 쓰는 doc_type]}` — 등록부 한 자리(`registry.lenses_of`)."""
    out = {}
    for dt in sorted(registry.all_doc_types()):
        for lay in registry.lenses_of(dt):
            out.setdefault(lay, []).append(dt)
    return out


def _layer(lay, cfg, lenses):
    pol = cfg.get("polarity") or {}
    return {
        "categories": {c: _first_line(d) for c, d in sorted((cfg.get("categories") or {}).items())},
        "skeleton": _skeleton(lay, cfg),
        "relations": sorted(cfg.get("relations") or []),
        "patterns": sorted((_pattern(p) for p in cfg.get("relation_patterns") or []),
                           key=lambda p: (p["src"] or "", p["rel"] or "", p["dst"] or "")),
        "pair_map": dict(sorted((cfg.get("category_pair_map") or {}).items())),
        "polarity": ({"bind_categories": sorted(pol.get("bind_categories") or []),
                      "values": list(pol.get("values") or [])} if pol else None),
        "mirrors": bool((cfg.get("mirrors") or {}).get("enabled")),
        "lenses": lenses.get(lay, []),
    }


def _home(cat):
    try:
        return catalog.home(cat)
    except catalog.CatalogError:
        return None


def _categories(configs):
    """카테고리마다 — 집 · 선언한 층 · 겸 · 이름 규칙(`bind` · `nest` · 둘 다 · 없음) · 골격 카테고리인 층."""
    try:
        cats = catalog.load().get("categories") or {}
    except catalog.CatalogError:
        cats = {}
    sc = catalog.canonical_scope() or {}
    bind, nest = set(sc.get("bind_categories") or []), set(sc.get("nest_categories") or [])
    decl = catalog.declared_by(configs)
    skel = {}
    for lay, cfg in configs.items():
        c = (cfg.get("skeleton") or {}).get("category")
        if c:
            skel.setdefault(c, []).append(lay)
    out = {}
    for c in sorted(set(cats) | set(decl)):
        v = cats.get(c) or {}
        out[c] = {"home": v.get("home") or None, "declared_by": decl.get(c, []),
                  "also": {o: list(t or []) for o, t in sorted((v.get("also") or {}).items())},
                  "naming": " · ".join(k for k, s in (("bind", bind), ("nest", nest)) if c in s) or "없음",
                  "skeleton_of": sorted(skel.get(c, []))}
    return out


def _schema_edges():
    """`[(doc_type, 층, 출발 카테고리, 관계, 도착 카테고리)]` — 등록 스키마의 엣지 선언(공용 블록 필드 포함)."""
    from kit.gate_tables import load_blocks
    out = []
    for dt in sorted(registry.all_doc_types()):
        schema = registry.schema_of(dt)
        if not schema:
            continue
        fields, _blk = load_blocks(schema)
        for e in schema.get("edges") or []:
            src, dst = (fields.get(str(e.get(k)).lstrip("@")) or {} for k in ("from", "to"))
            out.append((dt, schema.get("layer"), src.get("category") or src.get("target_category"),
                        e.get("relation"), dst.get("category") or dst.get("target_category")))
    return out


def links(layers, cats):
    """**층 사이 연결 포인트**(B173 ①) — ⓐ 걸침이 될 수 있는 엣지(끝 카테고리의 집 ≠ 그 층 — 관계 패턴 · 스키마 엣지)
    ⓑ 선언 없이 관계 패턴에서만 쓰는 카테고리 ⓒ 여러 층이 선언한 카테고리(렌즈 겹침 — 노드는 집 하나)."""
    cross, seen = [], set()

    def _add(lay, src, rel, dst, where):
        for end, c in (("src", src), ("dst", dst)):
            h = (cats.get(c) or {}).get("home")
            key = (lay, src, rel, dst, end, where)
            if c and h != lay and key not in seen:
                seen.add(key)
                cross.append({"layer": lay, "src": src, "rel": rel, "dst": dst, "end": end, "category": c,
                              "home": h, "from": where})
    for lay, d in layers.items():
        for p in d["patterns"]:
            _add(lay, p["src"], p["rel"], p["dst"], "관계 패턴")
    for dt, lay, src, rel, dst in _schema_edges():
        _add(lay, src, rel, dst, f"스키마 {dt}")
    uses = []
    for lay, d in layers.items():
        via = {}
        for p in d["patterns"]:
            for c in (p["src"], p["dst"]):
                if c and c not in d["categories"]:
                    via.setdefault(c, set()).add(p["rel"])
        uses += [{"layer": lay, "category": c, "home": (cats.get(c) or {}).get("home"), "via": sorted(r)}
                 for c, r in sorted(via.items())]
    shared = [{"category": c, "layers": v["declared_by"], "home": v["home"]}
              for c, v in cats.items() if len(v["declared_by"]) > 1]
    return {"cross": sorted(cross, key=lambda x: (x["layer"], x["from"], x["src"] or "", x["rel"] or "",
                                                 x["dst"] or "", x["end"])),
            "uses": uses, "shared": shared}


def new_checks(layers):
    """**없는 점검 셋**(B173 ①) — `[(갈래, 문면)]`."""
    out, by_rel = [], {}
    for lay, d in layers.items():
        for r in d["relations"]:
            by_rel.setdefault(r, []).append(lay)
    for r, lays in sorted(by_rel.items()):
        if len(lays) > 1:
            out.append(("표시", f"관계 '{r}'을 여러 층이 선언했다 {lays} — 같은 이름은 모든 층에서 같은 뜻이다 · "
                              f"같은 뜻인지 사람이 본다(다르면 이름을 가른다)"))
    for lay, d in layers.items():
        cfgp = paths.show(paths.layers(lay, "config.json"))
        for p in d["patterns"]:
            if p["rel"] not in d["relations"]:
                out.append(("경고", f"층 {lay}의 관계 패턴 {p['src']} -{p['rel']}-> {p['dst']}의 관계 '{p['rel']}'가 "
                                  f"그 층 relations에 없다 — {cfgp}의 relations에 더하거나 패턴을 고친다"))
        for c, line in d["categories"].items():
            if not line:
                out.append(("경고", f"층 {lay}의 카테고리 '{c}' 정의문이 비었다 — 추출 · 판정 지시문이 그 뜻을 모른다 · "
                                  f"{cfgp}의 categories['{c}']에 한 줄"))
    return out


def checks(layers):
    """점검 표 — `{갈래: [{"from", "line"}]}` · 있는 판정의 문면을 그대로 싣는다(다시 계산하지 않는다)."""
    out = {lv: [] for lv in LEVELS}
    try:
        for tag, line in catalog.problems():
            out["거부"].append({"from": f"카탈로그 {tag}", "line": line})
        out["경고"] += [{"from": "카탈로그 겸", "line": w} for w in catalog.warnings()]
        out["경고"] += [{"from": "카탈로그 극성 · 미러", "line": f"{w} · ▶ {nxt}"} for w, nxt in catalog.mirror_warnings()]
    except catalog.CatalogError as e:
        out["거부"].append({"from": "카탈로그", "line": str(e)})
    from cli.register import recheck
    for _dt, ok, line in recheck.run():
        if not ok:
            out["거부" if " FAIL — " in line else "경고"].append({"from": "등록 스키마 재대조", "line": line})
    for lv, line in new_checks(layers):
        out[lv].append({"from": "지도", "line": line})
    return out


def build():
    """지도 모델 하나 — `{map_version, coord, layers, categories, links, checks}`."""
    configs = _configs()
    lenses = _lenses()
    layers = {lay: _layer(lay, cfg, lenses) for lay, cfg in configs.items()}
    cats = _categories(configs)
    try:
        coord = coord_layer()
    except NoCoordLayer:                           # 좌표 층이 없다 — 지도는 그대로 그린다
        coord = None
    return {"map_version": MAP_VERSION, "coord": {"layer": coord, "category": COORD_CATEGORY},
            "layers": layers, "categories": cats, "links": links(layers, cats), "checks": checks(layers)}


def counts(model):
    """화면 요약의 수 — 층 · 카테고리 · 관계 패턴 · 연결 포인트(셋) · 점검 갈래마다."""
    lk = model["links"]
    return {"층": len(model["layers"]), "카테고리": len(model["categories"]),
            "관계 패턴": sum(len(d["patterns"]) for d in model["layers"].values()),
            "걸침": len(lk["cross"]), "선언 없이 씀": len(lk["uses"]), "여러 층 선언": len(lk["shared"]),
            **{lv: len(model["checks"][lv]) for lv in LEVELS}}
