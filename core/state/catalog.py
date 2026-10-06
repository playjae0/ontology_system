# -*- coding: utf-8 -*-
"""칸 0.1 — **층 공통 config(카테고리 카탈로그)** — 층 사이의 사실은 한 파일에 (B90 ①).

층 config는 **렌즈**다 — 그 층이 쓰는 카테고리를 **자기 정의문으로** 선언하고, 같은
카테고리를 여러 층이 선언해도 된다(공정층도 `Unit`을 말한다). 그러면 「그 카테고리의
노드는 어느 그래프에 사는가」·「무엇이 무엇을 겸하는가」·「이름 규칙」은 층 하나가
답할 수 없다 — 층 사이의 사실이다. 그 답을 `$ONTO_HOME/layers/common.json` 하나에 둔다::

    {"common_version": 1,
     "categories": {"Process": {"home": "<층>", "also": {"Unit": ["sub", "detail"]}}, …},
     "canonical_scope": {"bind_categories": [...], "sep": "::"}}

- `home` — 집(노드가 사는 그래프). 해소는 table·prose 모두 **집 빌더**에서 한다(②).
- `also` — 겸. 「그 단(`tier`)의 이 카테고리 노드는 저 카테고리이기도 하다」(③).
  **노드에 저장하지 않는다** — 주 카테고리 + `tier`와 카탈로그에서 계산한다.
- `canonical_scope` — 이름 규칙은 **여기 한 곳**이다. 층 config에 남아 있으면 거부.

**코드에 층 어휘 0** — 어느 카테고리가 어느 층 집인지, 무엇이 무엇의 겸인지는 전부 이
파일의 값이다. 정의문은 여기 두지 않는다(정의문은 층의 렌즈 — 층 config `categories`).

**맞추기는 `bootstrap`이 한다**(B92 · `core/state/catalog_sync.py`): 층 config에서 결정적으로
따라 나오는 줄(한 층만 선언한 카테고리의 집 · 선언도 노드도 없는 카테고리의 제거)은 자동이고,
파일이 없으면(운영) 같은 규칙으로 바로 만든다 — 여러 층이 선언한 카테고리의 집은 빈칸으로
두고 멈춘다(사람이 고른다). mock 루트에 파일이 없으면 층 선언에서 그 자리에서 세운다 — 한 층만
선언한 카테고리만 있을 때만(겹치면 멈춘다 — 집을 추측하지 않는다).
"""
from __future__ import annotations

import json

from core import paths

TIERS = ("main", "sub", "detail")          # 겸이 걸리는 단 — 골격 3단 어휘(시스템 어휘)
_CACHE = {}


class CatalogError(RuntimeError):
    """카탈로그가 없거나 쓸 수 없다 — 집을 추측하지 않고 멈춘다."""


def _mock():
    from core.llm import gateway            # 함수 안 import — paths와 같은 이유(순환 0)
    return gateway.use_mock()


def _layer_configs():
    """층 config **파일 그대로**(카탈로그 병합 전) — `{층: cfg}`."""
    from router import discover
    return {lay: json.loads(paths.layers(lay, "config.json").read_text(encoding="utf-8"))
            for lay in discover()}


def declared_by(configs=None):
    """카테고리 → 그것을 선언한 층 목록(이름순)."""
    out = {}
    for lay, cfg in sorted((configs or _layer_configs()).items()):
        for cat in cfg.get("categories") or {}:
            out.setdefault(cat, []).append(lay)
    return out


def draft(configs=None):
    """층 선언에서 세운 카탈로그 — 한 층만 선언한 카테고리는 그 층이 집 · 여럿이면 **빈칸**(사람이 채운다).

    `canonical_scope`는 층 config에서 옮긴다(여러 층이 서로 다르게 갖고 있으면 첫 것 +
    `_canonical_scope_note`에 사실을 적는다 — 고르지 않는다).
    """
    configs = configs or _layer_configs()
    cats = {c: {"home": lays[0] if len(lays) == 1 else ""}
            for c, lays in sorted(declared_by(configs).items())}
    out = {"common_version": 1, "categories": cats}
    scopes = [(lay, cfg["canonical_scope"]) for lay, cfg in sorted(configs.items())
              if cfg.get("canonical_scope")]
    if scopes:
        out["canonical_scope"] = scopes[0][1]
        if any(sc != scopes[0][1] for _l, sc in scopes[1:]):
            out["_canonical_scope_note"] = (
                "층마다 다른 canonical_scope가 있었다 — 첫 층의 것을 옮겼다: "
                + " · ".join(f"{lay}={json.dumps(sc, ensure_ascii=False)}" for lay, sc in scopes))
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
        cat = json.loads(p.read_text(encoding="utf-8"))
    elif _mock():
        cat = draft()
        blank = sorted(c for c, v in cat["categories"].items() if not v["home"])
        if blank:
            raise CatalogError(f"공통 config 없음 · 여러 층이 선언한 카테고리 {blank} — "
                               f"집을 추측하지 않는다 ({p})")
    else:
        raise CatalogError(
            f"[상태] 층 공통 config가 없다 — {p}\n"
            f"  ▶ 다음 줄: python run.py bootstrap   (층 config에서 만든다 — 여러 층이 "
            f"선언한 카테고리의 집은 사람이 채운다)")
    _CACHE.clear()
    _CACHE[key] = cat
    return cat


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


def canonical_scope():
    """이름 규칙 — 카탈로그 한 곳. 없으면 `None`."""
    try:
        return load().get("canonical_scope")
    except CatalogError:
        return None


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


def problems(configs=None, cat=None):
    """거부 갈래 ⓑ~ⓕ — `[(갈래, 문면)]`(ⓕ 층 이름 ≠ 폴더 이름 · B99 ①). 비어 있으면 통과다(ⓐ 파일 없음은 호출부가 본다).

    `cat`을 주면 그 카탈로그를 검사한다 — `bootstrap --dry-run`이 **맞춘 뒤의 계획**을 쓰지 않고
    실제 실행과 같은 판정을 받는 통로다(B96 ①). 없으면 파일의 카탈로그.
    """
    configs = configs or _layer_configs()
    out = [("ⓕ", m) for m in layer_name_problems(configs)]     # 층 이름 = 폴더 이름 (B99 ①)
    cat = cat if cat is not None else load()
    cats = cat.get("categories") or {}
    decl = declared_by(configs)
    for c, lays in sorted(decl.items()):
        if c not in cats:
            out.append(("ⓑ", f"층 {lays}의 카테고리 '{c}'가 공통 config에 없다 — "
                             f"python run.py bootstrap이 맞춘다(한 층이면 자동 · 여럿이면 집을 묻는다)"))
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
    for lay, cfg in sorted(configs.items()):
        if "canonical_scope" in cfg:
            out.append(("ⓓ", f"층 {lay}의 config에 canonical_scope가 남아 있다 — 공통 config로 "
                             f"옮겼다(두 곳 0) · {paths.show(paths.layers(lay, 'config.json'))}에서 지운다"))
    return out


def warnings():
    """경고(거부 아님) — `[문면]`. **겸의 집 불일치**(B91 ⑥ · D-171 ⑦): 주 카테고리 C가 X를
    겸하는데 X의 집이 C의 집과 다르면, 겸 후보는 판정이 보는 **집 그래프 안만** 보므로 그
    구성에서는 겸 매칭이 조용히 빠진다 — 막지 않고 말한다(사람이 의도했을 수 있다).
    """
    cats = load().get("categories") or {}
    out = []
    for c, v in sorted(cats.items()):
        hc = (v or {}).get("home")
        for other in sorted(((v or {}).get("also") or {})):
            ho = (cats.get(other) or {}).get("home")
            if hc and ho and hc != ho:
                out.append(f"'{c}'(집 {hc})가 '{other}'(집 {ho})를 겸한다 — 겸 후보는 판정이 보는 "
                           f"집 그래프 안만 본다: '{other}' 판정({ho})에서 '{c}' 노드({hc})는 겸 후보가 "
                           f"되지 않는다(이 구성에서는 겸 매칭이 조용히 빠진다)")
    return out


def mirror_warnings(configs=None):
    """**미러 규칙과 집의 어긋남**(B100 ④) — `[(문면, 다음 줄)]` · 경고만(막지 않는다 — 사람 판단).

    극성 결합·미러 짝 키(`mirror_scope`·`mirror_name`)는 노드를 만드는 **집 층의 빌더**가 그 층
    config로 적는다. 어떤 층 L이 카테고리 C를 `polarity.bind_categories`에 묶었는데 C의 집 H(≠L)의
    config에 그 규칙이 없으면, 이 구성에서는 C 노드의 극성·미러 짝이 조용히 빠진다(B99 ⑪ 재현 —
    집을 옮기면 mirrors 26 → 20). 규칙을 층 사이로 옮겨 읽는 코드는 넣지 않는다 — 말하고 사람이 옮긴다.
    """
    configs = configs or _layer_configs()
    cats = load().get("categories") or {}
    out = []
    for lay, cfg in sorted(configs.items()):
        pol = cfg.get("polarity") or {}
        for c in pol.get("bind_categories") or []:
            h = (cats.get(c) or {}).get("home")
            if not h or h == lay or h not in configs:
                continue
            hc = configs[h]
            hp = hc.get("polarity") or {}
            missing = []
            if c not in (hp.get("bind_categories") or []):
                missing.append("polarity.bind_categories")
            if (cfg.get("mirrors") or {}).get("enabled") and not (hc.get("mirrors") or {}).get("enabled"):
                missing.append("mirrors")
            if missing:
                out.append((f"층 {lay}이 '{c}'를 극성 짝(polarity.bind_categories)에 묶었는데 '{c}'의 집 "
                            f"{h}의 config에는 {' · '.join(missing)}가 없다 — 노드는 집 층 빌더가 만들므로 "
                            f"이 구성에서는 '{c}'의 극성·미러 짝이 빠진다",
                            f"규칙을 집 층 config로 — {paths.show(paths.layers(h, 'config.json'))}의 "
                            f"polarity(bind_categories에 '{c}' · values) · mirrors를 {lay}와 같게 → "
                            f"python run.py bootstrap"))
    return out

