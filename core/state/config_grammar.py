# -*- coding: utf-8 -*-
"""칸 0.1 — **config 문법 단** — 아는 키 · 값의 형과 닫힌 값 · 참조 · JSON 문법 (B192 ①).

뜻 검사(`catalog.problems` ⓑ~ⓖ · 겸 · 미러 경고)의 **앞 단**이다 — 거기서 보지 않는 것만 본다:

  · **아는 키** — 층 config는 `config_scope.layer_keys()` · 공통 config는 `config_scope.common_keys()`(최상위 · 카테고리 항목) +
    `PAIR_ITEM_KEYS`(`parent_pairs` 항목) · 골격 파일은 `config_scope.seed_keys()`(최상위만 — 트리 안은 `SeedError`) · `_`로 시작하면
    주석으로 지나간다 · 옛 키(옛 모양 · 손잡이로 옮겨 간 키)는 그 관문이 본다(두 번 말하지 않는다). **표 밖의 키는 거부** — 파일 · 키 ·
    가장 가까운 아는 키 · 다음 줄.
  · **값** — 코드가 그 형으로 읽는 칸(목록 · 딕셔너리 · 글)과 코드에 닫힌 값이 있는 칸(`CLOSED` — 값 · 읽는 자리)만.
  · **참조** — 층이 관계 패턴 · 등록 스키마에서 부르는 카테고리가 그 층 `categories`에도 `uses`에도 없으면 거부(옛 모양이면 ⓓ가 본다).
  · **JSON 문법** — `read_json`이 파일 · 행 · 열 · 무엇을 고치나 한 줄로 멈춘다(traceback 0) · config를 읽는 자리가 전부 이 함수다.

부르는 자리는 하나다 — `catalog.problems`(갈래 ⓗ 문법 · ⓘ 참조)가 `bootstrap`(`--dry-run` 포함) · 사전 점검(인입) · `export config`의
같은 판정이다. 문면은 여기서 만든다.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

from core import paths
from core.state import config_scope

TAG_GRAMMAR, TAG_REF = "ⓗ", "ⓘ"
NEXT = "python run.py bootstrap --dry-run"
#: 코드가 그 형으로 읽는 칸 — 층 config(`dict` · `list` · `str`)
LAYER_TYPES = {"categories": dict, "relations": list, "relevance_terms": list, "extract_patterns": list, "prompts": dict,
               "uses": list, "relation_patterns": list, "mirrors": dict, "polarity": dict, "skeleton": dict,
               "query_intents": dict, "query_traverse": dict, "cross_layer_traverse": dict, "fact_templates": dict}
COMMON_TYPES = {"categories": dict, "parent_pairs": list, "sep": str, "null_markers": list}
_BOOL = (True, False)
_JSON_WHAT = (("Expecting ',' delimiter", "쉼표(,)가 빠졌다 — 앞 항목 끝에 쉼표"),
              ("Expecting property name", "키 자리에 큰따옴표 이름이 없다 — 마지막 항목 뒤 쉼표를 지우거나 키를 큰따옴표로"),
              ("Expecting ':' delimiter", "키 뒤에 쌍점(:)이 없다"),
              ("Expecting value", "값이 없다 — 빈 자리 · 끝 쉼표 · 작은따옴표"),
              ("Unterminated string", "닫는 큰따옴표가 없다"),
              ("Invalid control character", "글 안에 줄바꿈 · 탭 — \\n으로 쓴다"),
              ("Extra data", "닫는 괄호 뒤에 글이 더 있다"))


def closed():
    """**닫은 칸** — `[(칸, 값들, 읽는 자리)]` · 값은 코드의 상수에서 읽는다(보고 표 · 시험이 같은 목록을 본다)."""
    from core.graph import DIRECTIONS
    from core.state.catalog import PAIR_SRC
    return [("query_traverse.<관계>.<이름>.direction", DIRECTIONS, "core/graph.py traverse"),
            ("query_traverse.<관계>.<이름>.recursive", _BOOL, "core/graph.py traverse"),
            ("cross_layer_traverse.<관계>.direction", DIRECTIONS, "core/query/query.py 층 걸침"),
            ("cross_layer_traverse.<관계>.recursive", _BOOL, "core/query/query.py 층 걸침"),
            ("relation_patterns[].symmetric", _BOOL, "core/build/gate.py"),
            ("mirrors.enabled", _BOOL, "core/state/skeleton.py 미러"),
            ("parent_pairs[].src", PAIR_SRC, "core/state/catalog.py pair_edge")]


class ConfigSyntaxError(ValueError):
    """config · 골격 파일의 JSON 문법 — 한 줄 문면(파일 · 행 · 열 · 무엇을 고치나 · 다음 줄)."""


def label(path):
    """화면의 파일 이름 — 상태 루트 아래면 `layers/<층>/config.json` 꼴 · 밖이면 경로 그대로."""
    p = Path(path)
    for base in (paths.home(), paths.layers().parent):
        try:
            return p.resolve().relative_to(Path(base).resolve()).as_posix()
        except ValueError:
            continue
    return str(p)


def read_json(path):
    """config · 골격 파일 읽기의 **한 자리** — JSON 문법이 틀리면 `ConfigSyntaxError`(traceback 대신 한 줄)."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        what = next((w for k, w in _JSON_WHAT if e.msg.startswith(k)), e.msg)
        raise ConfigSyntaxError(f"{label(path)} {e.lineno}행 {e.colno}열 — JSON 문법: {what} · "
                                f"▶ 다음 줄 — 그 자리를 고치고 {NEXT}") from None


def syntax_errors(base=None):
    """상태 루트(또는 `layers/` 모양의 폴더)의 config · 골격 파일 전부를 읽어 본다 — JSON 문법 문면 목록(비면 통과 · 읽기만)."""
    root = Path(base) if base else paths.layers()
    out = []
    files = [root / "common.json"] if (root / "common.json").exists() else []
    for d in sorted(x for x in root.iterdir() if x.is_dir()) if root.exists() else ():
        if (d / "config.json").exists():
            files.append(d / "config.json")
    for f in files:
        try:
            cfg = read_json(f)
        except ConfigSyntaxError as e:
            out.append(str(e))
            continue
        src = (cfg.get("skeleton") or {}).get("source") if isinstance(cfg, dict) and isinstance(cfg.get("skeleton"), dict) else None
        if src and (f.parent / src).exists():
            try:
                read_json(f.parent / src)
            except ConfigSyntaxError as e:
                out.append(str(e))
    return out


def _unknown(where, key, known):
    near = difflib.get_close_matches(str(key), list(known), n=1, cutoff=0.0)
    return (TAG_GRAMMAR, f"{where} — 모르는 키 `{key}`" + (f" · 가장 가까운 아는 키 `{near[0]}`" if near else "")
            + f" · ▶ 다음 줄 — 키 이름을 고치거나(주석이면 `_`로 시작) 지우고 {NEXT}")


def _keys(where, obj, known, old=()):
    if not isinstance(obj, dict):
        return []
    return [_unknown(where, k, known) for k in obj if not str(k).startswith("_") and k not in known and k not in old]


def _type(where, key, val, want):
    if isinstance(val, want):
        return []
    name = {dict: "딕셔너리 {…}", list: "목록 […]", str: "글 \"…\""}[want]
    return [(TAG_GRAMMAR, f"{where}의 `{key}`는 {name}이다 — 지금 {type(val).__name__} "
                          f"{json.dumps(val, ensure_ascii=False)[:60]} · ▶ 다음 줄 — 고치고 {NEXT}")]


def _value(where, key, val, allowed):
    if val in allowed and type(val) is type(allowed[0]):
        return []
    return [(TAG_GRAMMAR, f"{where}의 `{key}` 값 {json.dumps(val, ensure_ascii=False)}는 닫힌 값 밖이다 — "
                          f"{' · '.join(json.dumps(a) for a in allowed)} 중 하나 · ▶ 다음 줄 — 고치고 {NEXT}")]


def _traverse(where, key, spec, nested):
    from core.graph import DIRECTIONS
    out = []
    for rel, rules in (spec or {}).items():
        items = (rules or {}).items() if nested else [(None, rules)]
        for name, r in items:
            at = f"{key}.{rel}" + (f".{name}" if name else "")
            if not isinstance(r, dict):
                out += _type(where, at, r, dict)
                continue
            if "direction" in r:
                out += _value(where, f"{at}.direction", r["direction"], DIRECTIONS)
            if "recursive" in r:
                out += _value(where, f"{at}.recursive", r["recursive"], _BOOL)
    return out


def layer_problems(lay, cfg):
    """층 config 하나 — 아는 키 · 형 · 닫힌 값."""
    from core.state import catalog, knobs
    where = f"layers/{lay}/config.json"
    out = _keys(where, cfg, config_scope.layer_keys(), old=(*catalog.OLD_LAYER_KEYS, *knobs.MOVED_LAYER_KEYS))
    for k, want in LAYER_TYPES.items():
        if k in cfg:
            out += _type(where, k, cfg[k], want)
    if isinstance(cfg.get("query_traverse"), dict):
        out += _traverse(where, "query_traverse", cfg["query_traverse"], nested=True)
    if isinstance(cfg.get("cross_layer_traverse"), dict):
        out += _traverse(where, "cross_layer_traverse", cfg["cross_layer_traverse"], nested=False)
    if isinstance(cfg.get("mirrors"), dict) and "enabled" in cfg["mirrors"]:
        out += _value(where, "mirrors.enabled", cfg["mirrors"]["enabled"], _BOOL)
    for i, p in enumerate(cfg.get("relation_patterns") or [] if isinstance(cfg.get("relation_patterns"), list) else []):
        if isinstance(p, dict) and "symmetric" in p:
            out += _value(where, f"relation_patterns[{i}].symmetric", p["symmetric"], _BOOL)
    return out


def common_problems(common):
    """공통 config — 아는 키(최상위 · 카테고리 항목 · `parent_pairs` 항목) · 형 · 닫힌 값."""
    from core.state import catalog
    where = "layers/common.json"
    top, entry = config_scope.common_keys()
    out = _keys(where, common, top, old=catalog.OLD_COMMON_KEYS)
    for k, want in COMMON_TYPES.items():
        if k in (common or {}):
            out += _type(where, k, common[k], want)
    cats = (common or {}).get("categories")
    for c, v in (cats.items() if isinstance(cats, dict) else ()):
        out += _keys(f"{where} categories['{c}']", v, entry)
    pairs = (common or {}).get(catalog.PAIRS)
    for i, p in enumerate(pairs if isinstance(pairs, list) else ()):
        out += _keys(f"{where} {catalog.PAIRS}[{i}]", p, config_scope.PAIR_ITEM_KEYS)
        if isinstance(p, dict) and "src" in p:
            out += _value(where, f"{catalog.PAIRS}[{i}].src", p["src"], catalog.PAIR_SRC)
    return out


def seed_problems(lay, cfg, base=None):
    """골격 파일 최상위 키 — 층 config의 `skeleton.source`가 가리키는 파일(없거나 못 읽으면 그 관문이 본다)."""
    src = ((cfg or {}).get("skeleton") or {}).get("source") if isinstance((cfg or {}).get("skeleton"), dict) else None
    p = (Path(base) / lay / src) if (src and base) else (paths.layers(lay, src) if src else None)
    if not p or not p.exists():
        return []
    return _keys(f"layers/{lay}/{src}", read_json(p), config_scope.seed_keys())


def talks(lay, cfg, schemas):
    """층이 관계 패턴 · 등록 스키마(공용 블록 · `target_layer` 필드는 그 층 몫)에서 부르는 카테고리."""
    pats = cfg.get("relation_patterns") if isinstance(cfg.get("relation_patterns"), list) else []
    out = {x for p in pats if isinstance(p, dict) for x in (p.get("src"), p.get("dst")) if x}
    for _dt, sc, fields in schemas:
        if sc.get("layer") == lay:
            out |= {f.get(k) for f in fields.values() if isinstance(f, dict) and not f.get("target_layer")
                    for k in ("category", "target_category") if f.get(k)}
    return out


def schemas():
    """`[(doc_type, 스키마, 합친 필드)]` — 등록 스키마(공용 블록 필드 포함 · 킷의 블록 전개를 지연 import)."""
    from core.state import registry
    from kit.gate_tables import load_blocks
    out = []
    for dt in sorted(registry.all_doc_types()):
        schema = registry.schema_of(dt)
        if schema:
            out.append((dt, schema, load_blocks(schema)[0]))
    return out


def ref_problems(configs, scs=None):
    """참조 — 층이 부르는 카테고리가 그 층 `categories`에도 `uses`에도 없다(B174 ② · B192 ① 경고 → 거부)."""
    scs = schemas() if scs is None else scs
    out = []
    for lay, cfg in sorted(configs.items()):
        have = set(cfg.get("categories") or {}) | set(cfg.get("uses") or [])
        for c in sorted(talks(lay, cfg, scs) - have):
            out.append((TAG_REF, f"누락 — 층 {lay}가 관계 패턴 · 스키마에서 '{c}'를 쓰는데 categories에도 uses에도 없다 · "
                                 f"▶ 다음 줄 — layers/{lay}/config.json의 uses에 적고 {NEXT}"))
    return out


def problems(configs, common, base=None, scs=None):
    """문법 단 전부 — `[(갈래, 문면)]` · 옛 모양이면 참조는 건너뛴다(ⓓ가 새 모양 제안으로 멈춘다)."""
    from core.state import catalog
    out = common_problems(common)
    for lay, cfg in sorted(configs.items()):
        out += layer_problems(lay, cfg) + seed_problems(lay, cfg, base)
    if not catalog.old_shape(configs, common):
        out += ref_problems(configs, scs)
    return out
