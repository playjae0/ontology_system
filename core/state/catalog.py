# -*- coding: utf-8 -*-
"""칸 0.1 — **층 공통 config(카테고리 카탈로그)** — 층 사이의 사실은 한 파일에 (B90 ①).

층 config는 **렌즈**다 — 그 층이 쓰는 카테고리를 **자기 정의문으로** 선언하고, 같은
카테고리를 여러 층이 선언해도 된다(공정층도 `Unit`을 말한다). 그러면 「그 카테고리의
노드는 어느 그래프에 사는가」·「무엇이 무엇을 겸하는가」·「이름 규칙」은 층 하나가
답할 수 없다 — 층 사이의 사실이다. 그 답을 `$ONTO_HOME/layers/common.json` 하나에 둔다::

    {"common_version": 1,
     "categories": {"<카테고리>": {"home": "<층>", "also": {"<카테고리>": ["sub", "detail"]},
                                  "no_path": "<사유>"}, …},
     "parent_pairs": [{"lower": "<카테고리>", "upper": "<카테고리>", "rel": "<관계>", "src": "lower|upper"}, …],
     "sep": "::"}

- `home` — home(노드가 사는 그래프). 해소는 table·prose 모두 **home 빌더**에서 한다(②).
- `also` — 겸. 「그 단(`tier`)의 이 카테고리 노드는 저 카테고리이기도 하다」(③).
  **노드에 저장하지 않는다** — 주 카테고리 + `tier`와 카탈로그에서 계산한다.
- **경로**(이름 규칙 — B174 ①): 적지 않으면 「씀」(이름에 공정 경로가 붙는다) · `no_path`(사유)면 「안 씀」 · 골격
  카테고리는 적지 않는다(층 config `skeleton`이 정본 — 이름 그대로).
- **`parent_pairs`**(`parent_pairs` — B174 ① · B185 ②): 아래 · 위 · 엣지(관계 · `src` — 엣지의 출발이 아래인가 위인가). 산문 부착 · 소속 · 재부착 ·
  표의 소유 엣지 · 이관 재배선이 이 한 곳을 읽고(`pair_relation`) · 그 층이 쓰는 두 카테고리의 쌍은 게이트가 허용한다
  (`layer_patterns`) · **위가 일반 노드(골격이 아닌 카테고리)면 아래 카테고리의 이름은 그 노드 아래다**(`naming_rule` 「nest」).
- 옛 모양(공통 `canonical_scope` · 층 `category_pair_map` · home이 아닌 층의 정의)은 `old_shape`가 말하고 `bootstrap`이 새 모양
  제안을 쓰고 멈춘다(`core/state/config_next.py`).

**코드에 층 어휘 0** — 어느 카테고리가 어느 층 home인지, 무엇이 무엇의 겸인지는 전부 이
파일의 값이다. 정의문은 여기 두지 않는다(정의문은 층의 렌즈 — 층 config `categories`).

**맞추기는 `bootstrap`이 한다**(B92 · `core/state/catalog_sync.py`): 층 config에서 결정적으로
따라 나오는 줄(한 층만 선언한 카테고리의 home · 선언도 노드도 없는 카테고리의 제거)은 자동이고,
파일이 없으면(운영) 같은 규칙으로 바로 만든다 — 여러 층이 선언한 카테고리의 home은 빈칸으로
두고 멈춘다(사람이 고른다). mock 루트에 파일이 없으면 층 선언에서 그 자리에서 세운다 — 한 층만
선언한 카테고리만 있을 때만(겹치면 멈춘다 — home을 추측하지 않는다).
"""
from __future__ import annotations

import json

from core import paths

TIERS = ("main", "sub", "detail")          # 겸이 걸리는 단 — 골격 3단 어휘(시스템 어휘)
_CACHE = {}


class CatalogError(RuntimeError):
    """카탈로그가 없거나 쓸 수 없다 — home을 추측하지 않고 멈춘다."""


#: 공통 config의 `parent_pairs` 키(B185 ② — 카테고리 사이의 소속 관계 · 그 노드를 아래 끝으로 둔 엣지가 부모 엣지)
PAIRS = "parent_pairs"


def _mock():
    from core.llm import gateway            # 함수 안 import — paths와 같은 이유(순환 0)
    return gateway.use_mock()


def _layer_configs():
    """층 config **파일 그대로**(카탈로그 병합 전) — `{층: cfg}`."""
    from router import discover
    from core.state.config_grammar import read_json          # JSON 문법은 한 줄 문면(B192 ①)
    return {lay: read_json(paths.layers(lay, "config.json")) for lay in discover()}


def declared_by(configs=None):
    """카테고리 → 그것을 선언한 층 목록(이름순)."""
    out = {}
    for lay, cfg in sorted((configs or _layer_configs()).items()):
        for cat in cfg.get("categories") or {}:
            out.setdefault(cat, []).append(lay)
    return out


def draft(configs=None):
    """층 선언에서 세운 카탈로그 — 한 층만 선언한 카테고리는 그 층이 home · 여럿이면 **빈칸**(사람이 채운다) · `parent_pairs`은 빈 목록
    (사람이 적는다 — B174)."""
    configs = configs or _layer_configs()
    cats = {c: {"home": lays[0] if len(lays) == 1 else ""}
            for c, lays in sorted(declared_by(configs).items())}
    out = {"common_version": 1, "categories": cats, PAIRS: [], "sep": "::"}
    shared = {c: lays for c, lays in declared_by(configs).items() if len(lays) > 1}
    if shared:
        out["_빈칸"] = {c: f"여러 층이 선언했다 {lays} — home을 그중 하나로 채운다"
                       for c, lays in sorted(shared.items())}
    return out


def load():
    """카탈로그(dict). 운영에서 파일이 없으면 `CatalogError` — `bootstrap`이 만든다."""
    from router import discover
    p = paths.common()
    key = (str(p), p.stat().st_mtime_ns if p.exists() else None, tuple(discover()))
    if key in _CACHE:
        return _CACHE[key]
    if p.exists():
        from core.state.config_grammar import read_json
        cat = read_json(p)
    elif _mock():
        cat = draft()
        blank = sorted(c for c, v in cat["categories"].items() if not v["home"])
        if blank:
            raise CatalogError(f"공통 config 없음 · 여러 층이 선언한 카테고리 {blank} — "
                               f"home을 추측하지 않는다 ({p})")
    else:
        raise CatalogError(
            f"[상태] 층 공통 config가 없다 — {p}\n"
            f"  ▶ 다음 줄: python run.py bootstrap   (층 config에서 만든다 — 여러 층이 "
            f"선언한 카테고리의 home은 사람이 채운다)")
    _CACHE.clear()
    _CACHE[key] = cat
    return cat


def null_markers():
    """**빈칸 표시 목록**(B113 ②) — 공통 config `null_markers`(사내가 고친다) · 없거나 목록이 아니면 None
    (파서 기본값 `parser.normalizer.NULL_MARKERS`). 파일의 시각이 키다 — 고치면 그다음 값부터 따른다."""
    p = paths.common()
    if not p.exists():
        return None
    key = ("null_markers", str(p), p.stat().st_mtime_ns)
    if key not in _MARKERS:
        try:
            v = json.loads(p.read_text(encoding="utf-8")).get("null_markers")
        except ValueError:
            v = None
        _MARKERS.clear()
        _MARKERS[key] = v if isinstance(v, list) else None
    return _MARKERS[key]


_MARKERS = {}


def version():
    """`common_version` 또는 `None`(파일이 없다)."""
    p = paths.common()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("common_version")
    except ValueError:
        return None


def entry(category):
    return (load().get("categories") or {}).get(category) or {}


def home(category):
    """그 카테고리 노드가 사는 층 — 카탈로그 밖이면 `None`."""
    return entry(category).get("home") or None


def also(category):
    """겸 선언 — `{겸 카테고리: [단, …]}`."""
    return dict(entry(category).get("also") or {})


def _cat_or_none(cat):
    if cat is not None:
        return cat
    try:
        return load()
    except CatalogError:
        return None


def sep(cat=None):
    """이름의 구분자 — 공통 config `sep`(없으면 `::`)."""
    return ((_cat_or_none(cat) or {}).get("sep")) or "::"


def pairs(cat=None):
    """**`parent_pairs`**(B174 ①) — `[{lower, upper, rel, src, 정의문?}]` · 모양이 덜 찬 줄은 읽지 않는다(지도 점검이 말한다)."""
    return [dict(p) for p in (_cat_or_none(cat) or {}).get(PAIRS) or []
            if isinstance(p, dict) and p.get("lower") and p.get("upper") and p.get("rel")]


def structural_relations(cat=None):
    """**구조 관계** — `parent_pairs`의 관계 이름(B175 · 카테고리와 무관 — 같은 관계 이름은 모든 층에서 같은 뜻) · 반대 방향은 보류된다."""
    return {p["rel"] for p in pairs(cat)}


#: 쌍의 출발 끝 — 닫힌 둘(문법 단이 이 값으로 잰다 · B192 ①)
PAIR_SRC = ("lower", "upper")


def pair_edge(p):
    """쌍의 엣지 `(출발 카테고리, 관계, 도착 카테고리)` — `src`가 `upper`면 위 → 아래 · 아니면 아래 → 위."""
    return (p["upper"], p["rel"], p["lower"]) if p.get("src") == PAIR_SRC[1] else (p["lower"], p["rel"], p["upper"])


def skeleton_categories(configs=None):
    """골격 카테고리 집합 — 층 config `skeleton.category`(골격은 이름 그대로 · 경로를 적지 않는다)."""
    return {c for cfg in (configs if configs is not None else _layer_configs()).values()
            for c in [(cfg.get("skeleton") or {}).get("category")] if c}


_NAMING = {}


def naming_rule(cat=None, configs=None):
    """**이름 규칙**(B174 ①) — `{"path": [경로 씀], "nest": [이름이 위 노드 아래인 카테고리], "sep"}`.

    경로 씀 = 카탈로그 카테고리 − 골격 카테고리 − `no_path` · nest = `parent_pairs`에서 위가 일반 노드(골격이 아닌 카테고리)인 아래
    카테고리(목록 없이 쌍에서 — 그 노드가 이어지면 그 이름 아래 · 없으면 좌표 아래). 인자가 없으면 상태 루트를 읽고 파일 시각으로
    기억한다(값마다 부르는 자리다)."""
    if cat is None and configs is None:
        from router import discover
        files = [paths.common()] + [paths.layers(lay, "config.json") for lay in discover()]
        key = tuple((str(f), f.stat().st_mtime_ns if f.exists() else None) for f in files)
        if key not in _NAMING:
            _NAMING.clear()
            _NAMING[key] = naming_rule(_cat_or_none(None) or {}, _layer_configs())
        return _NAMING[key]
    cat = cat or {}
    sk = skeleton_categories(configs or {})
    cats = cat.get("categories") or {}
    path = [c for c in sorted(cats) if c not in sk and "no_path" not in (cats[c] or {})]   # 사유가 비어도 「안 씀」(지도가 말한다)
    nest = list(dict.fromkeys(p["lower"] for p in pairs(cat) if p["upper"] not in sk and p["lower"] in path))   # 「안 씀」은 앞말도 없다
    return {"path": path, "nest": nest, "sep": sep(cat)}


def spoken(cfg):
    """층이 말하는 카테고리 = home 카테고리(`categories`) ∪ 쓰는 다른 층 카테고리(`uses`) (B174 ②)."""
    return set((cfg or {}).get("categories") or {}) | set((cfg or {}).get("uses") or [])


def definition(category):
    """그 카테고리의 **정의문 — home 층 config 한 곳**(B174 · B178 ① — 다른 층 config에 다시 적지 않는다) · home이 없거나 못 읽으면 빈 글."""
    try:
        h = home(category)
    except CatalogError:
        return ""
    p = paths.layers(h, "config.json") if h else None
    if not p or not p.exists():
        return ""
    return str((json.loads(p.read_text(encoding="utf-8")).get("categories") or {}).get(category) or "")


def value_attr(category):
    """그 카테고리의 **산문 값 칸 이름 — home 층 config의 `value_categories` 한 곳**(B201 — 값을 받는지는 카테고리가 정한다 · 어느 층이
    읽든 같다) · 선언이 없거나 home을 못 읽으면 None."""
    try:
        h = home(category)
    except CatalogError:
        return None
    p = paths.layers(h, "config.json") if h else None
    if not p or not p.exists():
        return None
    decl = json.loads(p.read_text(encoding="utf-8")).get("value_categories") or {}
    name = decl.get(category) if isinstance(decl, dict) else None
    return str(name) if name else None


def asked(cfg):
    """**추출이 묻는 카테고리** `{이름: 정의문}`(B178 ①) = 그 층이 말하는 카테고리(`spoken` — 받는 거름과 같은 함수) · home 카테고리는
    그 층 정의문 · `uses`는 home 층의 정의문(`definition`) · 차례는 home 카테고리(층 config 차례) → `uses`(이름순)."""
    own = dict((cfg or {}).get("categories") or {})
    return {**own, **{c: definition(c) for c in sorted(spoken(cfg) - set(own))}}


def layer_pairs(cfg, cat=None):
    """그 층에 걸리는 `parent_pairs` — 두 카테고리를 다 말하는 층(`spoken`)."""
    sp = spoken(cfg)
    return [p for p in pairs(cat) if p["lower"] in sp and p["upper"] in sp]


def layer_patterns(cfg, cat=None):
    """그 층의 **게이트 패턴** = 층 `relation_patterns` + 그 층에 걸리는 `parent_pairs`의 엣지(B174 ② — 쌍의 삼항은 층에 다시 적지 않는다)."""
    own = list((cfg or {}).get("relation_patterns") or [])
    have = {(x.get("src"), x.get("rel"), x.get("dst")) for x in own}
    for p in layer_pairs(cfg, cat):
        s, r, d = pair_edge(p)
        if (s, r, d) not in have:
            have.add((s, r, d))
            own.append({"src": s, "rel": r, "dst": d, "symmetric": False, "정의문": p.get("정의문") or "", "pair": True})
    return own


def pair_relation(cfg, src_cat, dst_cat, cat=None):
    """`src_cat` → `dst_cat` 엣지의 관계 — 그 층에 걸리는 `parent_pairs` 중 엣지가 그 방향인 것(없으면 None · 한 자리 — 표 · 산문 · 재시도 ·
    이관이 이것을 읽는다)."""
    for p in layer_pairs(cfg, cat):
        s, r, d = pair_edge(p)
        if (s, d) == (src_cat, dst_cat):
            return r
    return None


def used_by(configs=None):
    """카테고리 → 그것을 말하는 층(home 정의 · `uses`) — 결과 기록 `used_by`의 재료(B92 · B174 ②)."""
    out = {}
    for lay, cfg in sorted((configs if configs is not None else _layer_configs()).items()):
        for c in sorted(spoken(cfg)):
            out.setdefault(c, []).append(lay)
    return out


#: 옛 모양의 키(B174 ③) — 읽는 자리는 옛 모양 감지와 제안 짓기뿐이다 · 옛 이름 `pairs`(B185 ② — 뜻 그대로 `parent_pairs`)
OLD_COMMON_KEYS = ("canonical_scope", "pairs")
OLD_PAIRS = OLD_COMMON_KEYS[1]


def legacy_rule(common, configs):
    """**옛 이름 규칙** `(bind, nest, sep)` — 공통 `canonical_scope` · 없으면 층에 남은 것(공통이 새 모양 이름 규칙 — `parent_pairs`이나
    `no_path` — 을 아직 갖지 않을 때만 · 가지면 공통이 정본) · 없으면 None(제안 · 지도의 옛 뜻 해석이 같은 함수로 읽는다)."""
    common = common or {}
    sc = (common[OLD_COMMON_KEYS[0]] or {}) if OLD_COMMON_KEYS[0] in common else None   # 빈 규칙도 규칙이다(목록 빈 것)
    has_new = bool(common.get(PAIRS) or common.get(OLD_PAIRS)) or any("no_path" in (v or {}) for v in (common.get("categories") or {}).values())
    if sc is None and not has_new:
        sc = next(((c[OLD_LAYER_KEYS[1]] or {}) for _l, c in sorted((configs or {}).items()) if OLD_LAYER_KEYS[1] in c), None)
    if sc is None:
        return None
    return set(sc.get("bind_categories") or []), set(sc.get("nest_categories") or []), sc.get("sep")
OLD_LAYER_KEYS = ("category_pair_map", "canonical_scope")


def old_shape(configs=None, cat=None):
    """**옛 모양의 자리** — `[문면]` · 비면 새 모양. 공통 `canonical_scope` · 층 `category_pair_map` · 층에 남은 `canonical_scope` ·
    home이 아닌 층의 카테고리 정의(정의문은 home 한 곳 · 다른 층은 `uses`)."""
    configs = configs if configs is not None else _layer_configs()
    cat = _cat_or_none(cat) or {}
    out = [f"공통 config에 {k}가 남아 있다" + (f" — `{OLD_PAIRS}` → `{PAIRS}`(뜻 그대로 — 키 이름만)" if k == OLD_PAIRS else "")
           for k in OLD_COMMON_KEYS if k in cat]
    for lay, cfg in sorted(configs.items()):
        out += [f"층 {lay}의 config에 {k}가 남아 있다" for k in OLD_LAYER_KEYS if k in cfg]
    cats = cat.get("categories") or {}
    for c, lays in sorted(declared_by(configs).items()):
        h = (cats.get(c) or {}).get("home")
        if h and len(lays) > 1:
            out += [f"층 {lay}가 home({h})이 아닌 카테고리 '{c}'를 정의한다" for lay in lays if lay != h]
    return out


def categories_of(node):
    """노드의 카테고리 집합 = **주 ∪ 겸** (주 카테고리 + `tier`로 계산 — 저장하지 않는다)."""
    main = node.get("category")
    out = {main}
    tier = node.get("tier")
    for other, tiers in also(main).items():
        if tier in (tiers or []):
            out.add(other)
    return out


def hosts(category):
    """`category`를 겸하는 주 카테고리 → 단 목록 — 매칭 후보를 넓히는 자리가 쓴다."""
    out = {}
    for main, v in (load().get("categories") or {}).items():
        tiers = (v.get("also") or {}).get(category)
        if tiers:
            out[main] = list(tiers)
    return out


def also_lines():
    """추출 입력에 싣는 겸 문장 — `{카테고리: "(… 단 X도 C이다 …)"}` (③ · 문안은 여기서 렌더)."""
    out = {}
    for main, v in sorted((load().get("categories") or {}).items()):
        for other, tiers in sorted((v.get("also") or {}).items()):
            out.setdefault(other, []).append(
                f"{'·'.join(tiers)} 단 {main}도 {other}이다: 좌표 자신을 가리키는 {other} 표기는 좌표다")
    return {c: "(" + " · ".join(v) + ")" for c, v in out.items()}


def layer_name_problems(configs=None):
    """**층 이름 = 폴더 이름**(B99 ①) — config 안 `"layer"`가 폴더 이름과 다르면 그 문면. 층 전부를 이 함수 하나로 잰다.

    읽는 쪽(`bootstrap.load_config`)은 이미 폴더 이름을 쓰지만, 다른 값이 적혀 있으면 사람이
    다른 층을 가리켰다고 믿는다 — `bootstrap`·사전 점검·`doctor`가 같은 문면으로 거부한다.
    """
    out = []
    for lay, cfg in sorted((configs or _layer_configs()).items()):
        v = cfg.get("layer")
        if v is not None and v != lay:
            out.append(f"layers/{lay}/config.json의 \"layer\"가 '{v}'이다 — 폴더 이름 '{lay}'로 "
                       f"고친다({paths.show(paths.layers(lay, 'config.json'))}) · "
                       f"▶ 다음 줄 — 고친 뒤 python run.py bootstrap --dry-run")
    return out


def problems(configs=None, cat=None, base=None):
    """거부 갈래 ⓑ~ⓘ — `[(갈래, 문면)]`(ⓕ 층 이름 ≠ 폴더 이름 · B99 ① · ⓗ 문법 단 아는 키 · 값 · ⓘ 참조 — `config_grammar` ·
    B192 ①). 비어 있으면 통과다(ⓐ 파일 없음은 호출부가 본다). `base`는 골격 파일을 읽을 `layers/` 모양의 폴더(없으면 상태 루트).

    `cat`을 주면 그 카탈로그를 검사한다 — `bootstrap --dry-run`이 **맞춘 뒤의 계획**을 쓰지 않고
    실제 실행과 같은 판정을 받는 통로다(B96 ①). 없으면 파일의 카탈로그.
    """
    configs = configs or _layer_configs()
    out = [("ⓕ", m) for m in layer_name_problems(configs)]     # 층 이름 = 폴더 이름 (B99 ①)
    cat = cat if cat is not None else load()
    from core.state import config_grammar                       # 문법 단 ⓗ 아는 키 · 값 · ⓘ 참조(B192 ①)
    out += config_grammar.problems(configs, cat, base=base)
    cats = cat.get("categories") or {}
    decl = declared_by(configs)
    for c, lays in sorted(decl.items()):
        if c not in cats:
            out.append(("ⓑ", f"층 {lays}의 카테고리 '{c}'가 공통 config에 없다 — "
                             f"python run.py bootstrap이 맞춘다(한 층이면 자동 · 여럿이면 home을 묻는다)"))
    for c, v in sorted(cats.items()):
        h = (v or {}).get("home")
        if not h:
            out.append(("ⓒ", f"'{c}'의 home이 빈칸이다 — 선언한 층 {decl.get(c, [])} 중 하나로 채운다"))
        elif h not in decl.get(c, []):
            out.append(("ⓒ", f"'{c}'의 home '{h}'는 그 카테고리를 선언하지 않은 층이다 — "
                             f"선언한 층 {decl.get(c, [])}"))
        for other, tiers in sorted(((v or {}).get("also") or {}).items()):
            if other not in cats:
                out.append(("ⓔ", f"'{c}'의 also가 카탈로그에 없는 카테고리 '{other}'를 가리킨다"))
            bad = [t for t in (tiers or []) if t not in TIERS]
            if bad or not tiers:
                out.append(("ⓔ", f"'{c}'의 also['{other}']의 단 {bad or tiers}가 "
                                 f"{'·'.join(TIERS)} 밖이다"))
    out += [("ⓓ", f"{m} — 옛 모양이다(이름 규칙 · parent_pairs는 공통 config 한 곳 · 정의문은 home 층 · 다른 층은 uses) · "
                   f"python run.py bootstrap이 새 모양 제안을 쓰고 멈춘다") for m in old_shape(configs, cat)]
    for lay, cfg in sorted(configs.items()):
        vc = cfg.get("value_categories")                         # 값을 받는 카테고리 (B120 ②)
        if vc is not None and (not isinstance(vc, dict) or any(
                c not in (cfg.get("categories") or {}) or not isinstance(n, str) or not n.strip()
                for c, n in vc.items())):
            out.append(("ⓖ", f"층 {lay}의 value_categories는 {{그 층 카테고리: 속성 이름}}이다 — 지금 "
                             f"{json.dumps(vc, ensure_ascii=False)[:80]} · 예: {{\"<카테고리>\": \"spec\"}}"))
    return out


def warnings(cat=None):
    """경고(거부 아님) — `[문면]`. **겸의 home 불일치**(B91 ⑥ · D-171 ⑦): 주 카테고리 C가 X를
    겸하는데 X의 home이 C의 home과 다르면, 겸 후보는 판정이 보는 **home 그래프 안만** 보므로 그
    구성에서는 겸 매칭이 조용히 빠진다 — 막지 않고 말한다(사람이 의도했을 수 있다).
    """
    cats = (cat if cat is not None else load()).get("categories") or {}
    out = []
    for c, v in sorted(cats.items()):
        hc = (v or {}).get("home")
        for other in sorted(((v or {}).get("also") or {})):
            ho = (cats.get(other) or {}).get("home")
            if hc and ho and hc != ho:
                out.append(f"'{c}'(home {hc})가 '{other}'(home {ho})를 겸한다 — 겸 후보는 판정이 보는 "
                           f"home 그래프 안만 본다: '{other}' 판정({ho})에서 '{c}' 노드({hc})는 겸 후보가 "
                           f"되지 않는다(이 구성에서는 겸 매칭이 조용히 빠진다)")
    return out

