# -*- coding: utf-8 -*-
"""칸 0.1 — **config 지도 모델**(B173 · 읽기만): 층 · 카테고리 · 층 사이 연결 포인트 · 점검을 한 모델로 모은다.

코드가 이미 읽는 자리를 부른다 — 카탈로그(`catalog` — 집 · 겸 · 이름 규칙 · 위아래 쌍 · 선언한 층) · 좌표 층
(`bootstrap.coord_layer`) · 등록부(`registry` — 스키마 · 렌즈) · 골격(층 그래프의 seed 노드 — GraphStore 경유 · 읽기만).
읽는 자리는 상태 루트의 `layers/` 또는 **제안 폴더**(`--from` — B174 ④ · 상태 루트를 건드리지 않는다)이고, **옛 모양은 옛 뜻으로 ·
새 모양은 새 뜻으로 읽어 같은 「뜻」**(카테고리 · 집 · 겸 · 이름 꼴 · 관계 패턴 · 위아래 쌍 · 쓰는 카테고리 · 연결 포인트)으로 모은다
— 옛 ↔ 새 대조가 이 모델의 `--diff`다.

**판정은 있는 함수를 부른다**(같은 판정의 두 번째 자리 0): 거부 = 카탈로그 `problems`(층 이름 = 폴더 이름 ⓕ 포함) ·
등록 스키마 재대조 FAIL(`cli.register.recheck.run` — G4C · G4D · G4E) / 경고 = 카탈로그 `warnings` · `mirror_warnings` ·
재대조 ⚠. **없는 것만 더한다**(`new_checks`): 여러 층이 같은 관계 이름을 선언(표시 — 같은 이름은 모든 층에서 같은 뜻 ·
사람이 본다) · 관계 패턴의 관계가 그 층 `relations`에 없음(경고) · 정의문이 빈 카테고리(경고).

LLM 0 · 그래프 · config · 등록 쓰기 0 · 코드에 층 · 카테고리 이름 0. 모델은 이름순이고 결정적이다(같은 상태면 JSON 바이트가 같다).
"""
from __future__ import annotations

from core import paths
from core.state import catalog, registry
import json
import re
from pathlib import Path

from core.state.bootstrap import COORD_CATEGORY, NoCoordLayer, coord_layer, open_graph
from core.state.config_scope import renamed
from core.state.status import is_live

MAP_VERSION = 4                                    # 4 — 온톨로지 맵(선 · 고리 · 실제 엣지 수 · attributes) · 허용 삼항 이름 pair_edges(B186 ①)
#: 점검 갈래 — 거부(인입 · bootstrap이 멈춘다) · 경고(막지 않는다 · 고칠 거리) · 표시(사람이 본다)
LEVELS = ("거부", "경고", "표시")
#: 이름 꼴의 좌표 자리 — 좌표 카테고리 이름(등록 블록 자산 `process_coord` — 코드에 카테고리 이름 0 · B177 ①) · 이름 자리는 `<name>`
COORD_TOKEN = f"<{COORD_CATEGORY}>"
NAME_TOKEN = "<name>"


def _first_line(text):
    """정의문 첫 줄 — 꾸밈 기호(`**` · `__` · 백틱)를 걷어 보인다(B174 ④)."""
    line = (str(text or "").strip().splitlines() or [""])[0]
    return re.sub(r"\*\*|__|`", "", line).strip()


def read(src=None):
    """`(공통 config, {층: 층 config})` — 상태 루트의 `layers/`(기본) 또는 그 모양의 폴더(제안 — 읽기만)."""
    base = Path(src) if src else paths.layers()
    cp = base / "common.json"
    common = renamed(json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {})   # 옛 키 이름은 새 이름으로(B186 ⓪)
    configs = {d.name: json.loads((d / "config.json").read_text(encoding="utf-8"))
               for d in sorted(base.iterdir()) if (d / "config.json").exists()} if base.exists() else {}
    return common, configs


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


def _schemas():
    """`[(doc_type, 스키마, 합친 필드)]` — 등록 스키마(공용 블록 필드 포함)."""
    from kit.gate_tables import load_blocks
    out = []
    for dt in sorted(registry.all_doc_types()):
        schema = registry.schema_of(dt)
        if schema:
            out.append((dt, schema, load_blocks(schema)[0]))
    return out


def _cat_of(fields, name):
    f = fields.get(str(name).lstrip("@")) or {}
    return f.get("category") or f.get("target_category")


def _pair_edges(common, configs, old):
    """위아래 쌍의 엣지 `[(출발, 관계, 도착)]` — 새 모양은 공통 `parent_pairs` · 옛 모양은 층 매핑의 합(옛 뜻)."""
    edges = {catalog.pair_edge(p) for p in catalog.pairs(common)}           # 공통에 이미 있는 쌍 + 옛 층 매핑(옛 뜻)
    if old:
        edges |= {(k.partition(",")[0], r, k.partition(",")[2])
                  for c in configs.values() for k, r in (c.get(catalog.OLD_LAYER_KEYS[0]) or {}).items()}
    return sorted(edges)


def _uses(lay, cfg, old, schemas):
    """층이 쓰는 다른 층 카테고리 — 새 모양은 `uses` · 옛 모양은 관계 패턴 · 스키마 · 층 매핑에서 읽힌 것(옛 뜻)."""
    if not old:
        return sorted(set(cfg.get("uses") or []))
    mapped = {x for k in (cfg.get(catalog.OLD_LAYER_KEYS[0]) or {}) for x in k.split(",")}
    return sorted((_talks(lay, cfg, schemas) | mapped | set(cfg.get("uses") or [])) - set(cfg.get("categories") or {}))


def _talks(lay, cfg, schemas):
    """층이 관계 패턴 · 등록 스키마(공용 블록 · `target_layer` 필드는 그 층 몫)에서 부르는 카테고리."""
    out = {x for p in cfg.get("relation_patterns") or [] for x in (p.get("src"), p.get("dst")) if x}
    for _dt, sc, fields in schemas:
        if sc.get("layer") == lay:
            out |= {f.get(k) for f in fields.values() if isinstance(f, dict) and not f.get("target_layer")
                    for k in ("category", "target_category") if f.get(k)}
    return out


def _layer(lay, cfg, lenses, edges, old, schemas):
    pol = cfg.get("polarity") or {}
    own = sorted((_pattern(p) for p in cfg.get("relation_patterns") or []
                  if (p.get("src"), p.get("rel"), p.get("dst")) not in set(edges)),
                 key=lambda p: (p["src"] or "", p["rel"] or "", p["dst"] or ""))
    uses = _uses(lay, cfg, old, schemas)
    spk = set(cfg.get("categories") or {}) | set(uses)
    raw = {(p.get("src"), p.get("rel"), p.get("dst")) for p in cfg.get("relation_patterns") or []}
    return {
        # 이 층에 걸린 쌍 중 층 패턴에 없는 것 — 공통 `parent_pairs`에서만 온다(B177 ① 표시 「parent_pairs에서」 · 옛 모양은 층 매핑이라 0)
        "pair_edges_only": [] if old else [list(e) for e in edges if {e[0], e[2]} <= spk and tuple(e) not in raw],
        "categories": {c: _first_line(d) for c, d in sorted((cfg.get("categories") or {}).items())},
        "uses": uses,
        "skeleton": _skeleton(lay, cfg),
        "relations": sorted(cfg.get("relations") or []),
        "patterns": own,
        "pair_edges": [list(e) for e in edges if {e[0], e[2]} <= spk] if not old else
                 sorted([list(e) for e in edges if f"{e[0]},{e[2]}" in (cfg.get(catalog.OLD_LAYER_KEYS[0]) or {})]),
        "polarity": ({"bind_categories": sorted(pol.get("bind_categories") or []),
                      "values": list(pol.get("values") or [])} if pol else None),
        "mirrors": bool((cfg.get("mirrors") or {}).get("enabled")),
        "lenses": lenses.get(lay, []),
    }


def _name_forms(common, configs, old, edges):
    """카테고리마다 **경로**와 **이름 꼴**(B174 ④ — 사용자 「조건이 많으니 지도가 보여라」) — `{카테고리: (경로, 이름 꼴)}`."""
    sk = catalog.skeleton_categories(configs)
    cats = common.get("categories") or {}
    rule = catalog.legacy_rule(common, configs) if old else None             # 옛 키가 남아도 이름 규칙이 새 모양이면 새 뜻
    if rule:
        bind, nest, _sep = rule
        ups = {c: sorted({(s if d == c else d) for s, _r, d in edges if c in (s, d)} - {c} - sk) for c in nest}
        path = {c: ("골격" if c in sk else "씀" if c in bind | nest else "안 씀 — (사유 없음 · 옛 목록 밖)") for c in cats}
    else:
        ups = {}
        for p in catalog.pairs(common):
            if p["upper"] not in sk:
                ups.setdefault(p["lower"], set()).add(p["upper"])
        ups = {c: sorted(v) for c, v in ups.items()}
        path = {c: ("골격" if c in sk else "씀" if "no_path" not in (v or {}) else f"안 씀 — {(v or {}).get('no_path') or '(사유 없음)'}")
                for c, v in cats.items()}
    out = {}
    for c in sorted(cats):
        pth = path[c]
        if pth == "골격":
            form = f"{NAME_TOKEN}  (skeleton — 이름 그대로)"
        elif pth.startswith("안 씀"):
            form = f"{NAME_TOKEN}  (no_path — 이름 그대로)"
        elif ups.get(c):
            form = (" | ".join(f"{COORD_TOKEN}::<{u}>::{NAME_TOKEN}" for u in ups[c])
                    + f" | {COORD_TOKEN}::{NAME_TOKEN}  (upper 노드가 없으면)")
        else:
            form = f"{COORD_TOKEN}::{NAME_TOKEN}"
        out[c] = (pth, form)
    return out


def name_forms(common, configs):
    """`{카테고리: 이름 꼴}` — 옛 모양은 옛 뜻 · 새 모양은 새 뜻(제안 보고가 앞뒤를 지도와 같은 함수로 잰다 — B174 ③)."""
    old = bool(catalog.old_shape(configs, common))
    return {c: f for c, (_p, f) in _name_forms(common, configs, old, _pair_edges(common, configs, old)).items()}


def _categories(common, configs, old, edges):
    """카테고리마다 — 집 · 선언한 층 · 쓰는 층(`used_by`) · 겸 · 경로 · 이름 꼴 · 골격 카테고리인 층."""
    cats = common.get("categories") or {}
    decl = catalog.declared_by(configs)
    skel = {}
    for lay, cfg in configs.items():
        c = (cfg.get("skeleton") or {}).get("category")
        if c:
            skel.setdefault(c, []).append(lay)
    forms = _name_forms(common, configs, old, edges)
    out = {}
    for c in sorted(set(cats) | set(decl)):
        v = cats.get(c) or {}
        pth, form = forms.get(c, ("(공통 config 밖)", "(공통 config 밖)"))
        out[c] = {"home": v.get("home") or None, "declared_by": decl.get(c, []), "used_by": list(v.get("used_by") or []),
                  "also": {o: list(t or []) for o, t in sorted((v.get("also") or {}).items())},
                  "path": pth, "name_form": form, "skeleton_of": sorted(skel.get(c, []))}
    return out


def links(layers, cats, schemas=()):
    """**층 사이 연결 포인트**(B173 ① · B174) — ⓐ 걸침이 될 수 있는 엣지(끝 카테고리의 집 ≠ 그 층 — 층 패턴 · 그 층에 걸리는
    위아래 쌍 · 스키마 엣지) ⓑ 층이 쓰는 다른 층 카테고리(`uses`) ⓒ 여러 층이 정의한 카테고리(정의문은 집 한 곳이어야 한다)."""
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
        for s, r, t in d["pair_edges"]:
            _add(lay, s, r, t, "위아래 쌍")
    for dt, sc, fields in schemas:
        for e in sc.get("edges") or []:
            _add(sc.get("layer"), _cat_of(fields, e.get("from")), e.get("relation"), _cat_of(fields, e.get("to")), f"스키마 {dt}")
    uses = [{"layer": lay, "category": c, "home": (cats.get(c) or {}).get("home")}
            for lay, d in layers.items() for c in d["uses"]]
    shared = [{"category": c, "layers": v["declared_by"], "home": v["home"]}
              for c, v in cats.items() if len(v["declared_by"]) > 1]
    return {"cross": sorted(cross, key=lambda x: (x["layer"], x["from"], x["src"] or "", x["rel"] or "",
                                                 x["dst"] or "", x["end"])),
            "uses": uses, "shared": shared}


def new_checks(layers, cats, configs, schemas=()):
    """**지도가 더한 점검**(B173 ① · B174 ④ 새 모양 규칙) — `[(갈래, 문면)]`."""
    out, by_rel = [], {}
    for lay, d in layers.items():
        for r in d["relations"]:
            by_rel.setdefault(r, []).append(lay)
    for r, lays in sorted(by_rel.items()):
        if len(lays) > 1:
            out.append(("표시", f"관계 '{r}'을 여러 층이 선언했다 {lays} — 같은 이름은 모든 층에서 같은 뜻이다 · "
                              f"같은 뜻인지 사람이 본다(다르면 이름을 가른다)"))
    for lay, d in layers.items():
        cfgp = f"layers/{lay}/config.json"
        for p in d["patterns"]:
            if p["rel"] not in d["relations"]:
                out.append(("경고", f"층 {lay}의 관계 패턴 {p['src']} -{p['rel']}-> {p['dst']}의 관계 '{p['rel']}'가 "
                                  f"그 층 relations에 없다 — {cfgp}의 relations에 더하거나 패턴을 고친다"))
        for c, line in d["categories"].items():
            if not line:
                out.append(("경고", f"층 {lay}의 카테고리 '{c}' 정의문이 비었다 — 추출 · 판정 지시문이 그 뜻을 모른다 · "
                                  f"{cfgp}의 categories['{c}']에 한 줄"))
        miss = sorted(_talks(lay, configs.get(lay, {}), schemas) - set(d["categories"]) - set(d["uses"]))
        out += [("경고", f"누락 — 층 {lay}가 관계 패턴 · 스키마에서 '{c}'를 쓰는데 categories에도 uses에도 없다 · "
                         f"{cfgp}의 uses에 적는다(B174 ②)") for c in miss]
        dup = [(p["src"], p["rel"], p["dst"]) for p in (configs.get(lay, {}).get("relation_patterns") or [])
               if [p.get("src"), p.get("rel"), p.get("dst")] in d["pair_edges"]]
        out += [("표시", f"중복 — 층 {lay} 패턴 {s} -{r}-> {t}는 위아래 쌍과 같다(쌍이 정본 · 층 패턴에서 지운다)") for s, r, t in dup]
    for c, v in cats.items():
        if v["path"].startswith("안 씀") and "(사유 없음" in v["path"]:
            out.append(("경고", f"누락 — '{c}'의 경로 「안 씀」에 사유가 없다 · 공통 config categories['{c}'].no_path에 적거나 "
                              f"지워서 「씀」으로"))
        if len(v["declared_by"]) > 1:
            out.append(("표시", f"중복 — '{c}'를 여러 층이 정의했다 {v['declared_by']} · 정의문은 집({v['home']}) 한 곳 · "
                              f"다른 층은 uses"))
    return out


def checks(layers, cats, common, configs, src=None, schemas=()):
    """점검 표 — `{갈래: [{"from", "line"}]}` · 있는 판정의 문면을 그대로 싣는다(다시 계산하지 않는다)."""
    out = {lv: [] for lv in LEVELS}
    try:
        for tag, line in catalog.problems(configs, common):
            out["거부"].append({"from": f"카탈로그 {tag}", "line": line})
        out["경고"] += [{"from": "카탈로그 겸", "line": w} for w in catalog.warnings(common)]
        out["경고"] += [{"from": "카탈로그 극성 · 미러", "line": f"{w} · ▶ {nxt}"}
                       for w, nxt in catalog.mirror_warnings(configs, common)]
    except catalog.CatalogError as e:
        out["거부"].append({"from": "카탈로그", "line": str(e)})
    from cli.register import recheck
    for _dt, ok, line in recheck.run(src):
        if not ok:
            out["거부" if " FAIL — " in line else "경고"].append({"from": "등록 스키마 재대조", "line": line})
    for lv, line in new_checks(layers, cats, configs, schemas):
        out[lv].append({"from": "지도", "line": line})
    return out


def build(src=None):
    """지도 모델 하나 — `{map_version, shape, coord, layers, pair_edges, categories, links, pair_defs, ontology, checks}` · `src`는
    읽을 `layers/` 모양의 폴더(없으면 상태 루트) · `ontology`는 온톨로지 맵(`cli.ontology_map` — B186 ①)."""
    common, configs = read(src)
    old = bool(catalog.old_shape(configs, common))
    schemas = _schemas()
    edges = _pair_edges(common, configs, old)
    lenses = _lenses()
    layers = {lay: _layer(lay, cfg, lenses, edges, old, schemas) for lay, cfg in configs.items()}
    cats = _categories(common, configs, old, edges)
    try:
        coord = coord_layer()
    except NoCoordLayer:                           # 좌표 층이 없다 — 지도는 그대로 그린다
        coord = None
    from cli import ontology_map as OM
    onto = OM.build(configs, schemas, edges, cats, COORD_CATEGORY, configs)
    chk = _old_key_note(checks(layers, cats, common, configs, src, schemas), src)
    for lv, line in OM.check_lines(onto):
        chk[lv].append({"from": "지도", "line": line})
    return {"map_version": MAP_VERSION, "shape": "옛 모양" if old else "새 모양",
            "coord": {"layer": coord, "category": COORD_CATEGORY}, "layers": layers,
            "pair_edges": [list(e) for e in edges], "categories": cats, "links": links(layers, cats, schemas),
            "pair_defs": sorted(catalog.pairs(common), key=lambda p: (p["lower"], p["upper"], p["rel"])),
            "ontology": onto, "checks": chk}


def _old_key_note(chk, src):
    """옛 키 이름이 남은 공통 config — 새 이름으로 읽었다는 경고 한 줄(점검은 `--diff` 밖 · bootstrap은 제안을 쓰고 멈춘다)."""
    cp = (Path(src) if src else paths.layers()) / "common.json"
    raw = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    from core.state.config_scope import COMMON_KEY, RENAMED
    chk["경고"] += [{"from": "지도", "line": f"공통 config 키 `{o}` — `{n}`로 읽었다(뜻 그대로 · bootstrap은 제안을 쓰고 멈춘다)"}
                   for o, n in sorted(RENAMED[COMMON_KEY].items()) if o in raw]
    return chk


def counts(model):
    """화면 요약의 수 — 층 · 카테고리 · 관계 패턴 · 위아래 쌍 · 연결 포인트 · 선언 없이 씀(누락) · 점검 갈래마다."""
    lk = model["links"]
    miss = sum(1 for x in model["checks"]["경고"] if x["from"] == "지도" and x["line"].startswith("누락 — 층"))
    return {"층": len(model["layers"]), "카테고리": len(model["categories"]),
            "관계 패턴": sum(len(d["patterns"]) for d in model["layers"].values()), "위아래 쌍": len(model["pair_edges"]),
            "걸침": len(lk["cross"]), "쓰는 카테고리": len(lk["uses"]), "선언 없이 씀": miss,
            "여러 층 선언": len(lk["shared"]), **{lv: len(model["checks"][lv]) for lv in LEVELS}}
