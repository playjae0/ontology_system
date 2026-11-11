# -*- coding: utf-8 -*-
"""칸 0.1 — **config 칸의 영향 범위** — 바꾸면 무엇이 다시 도나 (B118 ⑥ · 사용자 2026-10-16 「기준 바꾸는 관리가 쉽고 명확해야」).

층 config · 층 공통 config의 최상위 키를 세 갈래로 가른다 — **분류는 이 표 하나다**(B120 ③ 추출 재사용의 판이 같은 표를 읽는다):

  · 추출 — 추출 입력에 실제로 들어가는 칸: 층 `categories`(이름 · 정의문) · `relations`(관계 이름) · `relevance_terms`(렌즈
    거름) · `extract_patterns`(mock 문형) · `value_categories`(값을 받는 카테고리 — B120 ②) · `prompts`(층 힌트 — 목차 노드화 ·
    추출 · 보강 · 판정 지시문에 덧붙는 층의 말 — B124 ③ · B148 ⑤) · 공통 `categories`(겸 한 줄이
    정의문 끝에 붙는다 — 공통은 겸 칸만 잰다 · B174) → **산문 추출을 다시 뽑는다** — 추출 · 목차 노드화 보존분의 재사용 판이 이 칸들의 해시다(`extract_key` ·
    B120 ③ — 사람이 적는 `config_version`은 기록용이고 판정에 쓰지 않는다 · 메타의 구조 판단은 층 config를 읽지 않는다 — B148 ①)
  · 둘 다 — 층 `uses`(묻는 목록에 그 카테고리 · home 층 정의문이 든다 · 게이트의 걸린 쌍 — B178 ②) → 다시 뽑고 다시 판정한다
  · 구축 — 게이트 · 구축만: 층 `relation_patterns` · `skeleton` · 공통 카테고리의 home · 경로
    (`no_path`) · `parent_pairs` · `sep` → **재구축이 LLM 0으로 다시 판정한다**(판정 재생 · 게이트 · 이름 규칙이 지금 config로)
  · 그 밖 — 질의(`query_*` · `fact_templates`) · 기록(판 번호 · `registration`) · 주석(`_`로 시작) → 영향 없음
    (아는 키 전부 = 두 갈래 + `OTHER` — `layer_keys()` · config 작성 가이드 항목 표가 이것과 같다 · B148 ⑥ · **표에 없는 키는 거부** —
    `config_grammar` · B192 ①)

**지난 인입이 쓴 config**는 문서 대장(`doc_registry.json`)의 `config_parts`(칸마다 내용 해시)다 — 인입이 적고(`ingest.register_doc`)
`bootstrap` 끝 줄이 지금과 칸별로 대조한다(`impact`). 내용은 저장하지 않는다(해시만 — 바뀌었나만 안다).
"""
from __future__ import annotations

import hashlib
import json

#: 층 config — 갈래마다 키(닫힌 표 · 밖은 「그 밖」)
LAYER = {"추출": ("categories", "relations", "relevance_terms", "extract_patterns", "value_categories", "prompts", "uses"),
         "구축": ("relation_patterns", "uses", "skeleton")}
#: 두 갈래에 다 드는 칸 — `uses`는 묻는 목록(추출 · B178 ②)이자 게이트의 걸린 쌍(구축 · B174)
USES = "uses"
#: 층 config — 그 밖 갈래의 아는 키(영향 없음 · 갈래 판정은 `kind`가 「그 밖」으로 본다 · B148 ⑥ — 가이드 항목 표의 나머지)
OTHER = {"질의": ("query_intents", "query_traverse", "cross_layer_traverse", "fact_templates"),
         "기록": ("layer", "config_version", "registration", "skeleton_version")}
#: 층 공통 config(`layers/common.json`) — 카테고리 항목은 칸마다 편다(`common_view` — 추출 입력은 겸뿐 · `used_by`는 기록 · B174)
COMMON = {"추출": ("categories.also",), "구축": ("categories.home", "categories.no_path", "parent_pairs", "sep")}
COMMON_KEY = "공통"
#: 이름만 바뀐 칸(B185 ② — 지난 기록의 옛 이름은 새 이름으로 대조한다 · 값이 같으면 바뀜이 아니다)
RENAMED = {COMMON_KEY: {"pairs": "parent_pairs"}}
#: **아는 키**(B192 ① — 문법 단 `config_grammar`가 이 표 밖의 키를 거부한다 · 영향 범위 표와 한 자리) — 공통 config의 그 밖 갈래
#: (기록 · 파서가 읽는 빈칸 표시 — 영향 범위는 「그 밖」) · `parent_pairs` 항목 키 · 골격 파일 최상위 키
COMMON_OTHER = {"기록": ("common_version", "categories.used_by"), "파서": ("null_markers",)}
PAIR_ITEM_KEYS = ("lower", "upper", "rel", "src", "정의문")
SEED_FORMAT_KEY = "seed_format"


def renamed(cfg, part=COMMON_KEY):
    """**옛 키 이름을 새 이름으로 읽은 사본**(B186 ⓪ — 「지금」 쪽 읽기도 `RENAMED` 한 자리) — 둘 다 있으면 목록을 잇는다 · 원본은 그대로."""
    out = dict(cfg or {})
    for o, n in RENAMED.get(part, {}).items():
        if o in out:
            old = out.pop(o)
            out[n] = (list(out.get(n) or []) + list(old or [])) if isinstance(old, list) else out.get(n, old)
    return out


def _h(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _common():
    """층 공통 config(없거나 못 읽으면 빈 칸)."""
    from core import paths
    p = paths.common()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


def common_view(com):
    """공통 config의 칸 — 카테고리 항목을 칸마다 편다(`categories.also` · `.home` · `.no_path` · 나머지 최상위 키 그대로 ·
    `used_by`는 결과 기록이라 대조 밖)."""
    cats = (com or {}).get("categories") or {}
    out = {f"categories.{k}": {c: (v or {}).get(k) for c, v in sorted(cats.items()) if (v or {}).get(k)}
           for k in ("also", "home", "no_path")}
    out.update({k: v for k, v in (com or {}).items() if k != "categories"})
    return out


def uses_view(cfg):
    """`uses` 칸이 추출에 주는 것 — 쓰는 카테고리 이름 · 그 정의문(home 층 config — `catalog.definition`)(B178 ②)."""
    from core.state import catalog
    own = (cfg or {}).get("categories") or {}
    return {USES: list((cfg or {}).get(USES) or []),
            "정의문": {c: catalog.definition(c) for c in (cfg or {}).get(USES) or [] if c not in own}}


def extract_key(cfg):
    """**추출 재사용의 층 config 판**(B120 ③) — 그 층 config와 공통 config의 **추출 갈래 칸** 내용 해시.

    bootstrap의 「추출 다시」 알림(`impact`)과 같은 표(`LAYER` · `COMMON`)를 읽으므로 알림과 실제 재추출이 늘 같다 —
    구축 갈래(`relation_patterns` · 공통 카테고리의 home · 경로 · `parent_pairs` …)와 그 밖(`config_version` · `used_by` …)은 판에
    들지 않는다. `uses`는 묻는 목록(쓰는 카테고리 · 그 home 층 정의문 — `uses_view`)으로 들고 **빈 층은 판이 그대로다**(B178 ②)."""
    com = common_view(_common())
    return _h({"층": {k: (cfg or {}).get(k) for k in LAYER["추출"] if k in (cfg or {}) and k != USES},
               COMMON_KEY: {k: com[k] for k in COMMON["추출"] if com.get(k)},
               **({USES: uses_view(cfg)} if (cfg or {}).get(USES) else {})})


def layer_keys():
    """층 config의 아는 키 전부 — 갈래 표(`LAYER`) + 그 밖(`OTHER`) · 차례는 표 그대로(두 갈래에 든 키는 한 번)."""
    return tuple(dict.fromkeys(k for table in (LAYER, OTHER) for keys in table.values() for k in keys))


def common_keys():
    """공통 config의 아는 키 — `(최상위 키, 카테고리 항목 키)` · `COMMON` + `COMMON_OTHER`를 편 것(B192 ①)."""
    flat = [k for table in (COMMON, COMMON_OTHER) for keys in table.values() for k in keys]
    top = tuple(dict.fromkeys(k.split(".", 1)[0] for k in flat))
    return top, tuple(dict.fromkeys(k.split(".", 1)[1] for k in flat if "." in k))


def seed_keys():
    """골격 파일의 아는 최상위 키 — 판 번호 + 블록 셋(`skeleton.KEY_*` — 트리 안 문법은 `SeedError`가 본다 · B192 ①)."""
    from core.state.skeleton import KEY_ALIASES, KEY_LABELS, KEY_TREE
    return (SEED_FORMAT_KEY, KEY_LABELS, KEY_TREE, KEY_ALIASES)


def kinds(key, common=False):
    """키 하나가 드는 갈래 전부 — `추출` · `구축`(둘 다일 수 있다 — `uses`) · 없으면 `그 밖`."""
    table = COMMON if common else LAYER
    return [k for k, keys in table.items() if key in keys] or ["그 밖"]


def kind(key, common=False):
    """키 하나의 갈래(첫째) — `추출` · `구축` · `그 밖`."""
    return kinds(key, common)[0]


def parts(cfg):
    """config 하나의 칸 지문 `{키: 해시}` — 주석(`_`로 시작) 제외."""
    return {k: _h(v) for k, v in sorted((cfg or {}).items()) if not str(k).startswith("_")}


def snapshot(layers=None):
    """지금 config의 칸 지문 — `{층: {키: 해시}, "공통": {키: 해시}}` (층은 폴더 전부 · 공통 config가 없으면 빈 칸)."""
    from core.state.bootstrap import load_config
    from router import discover
    out = {}
    for lay in layers or discover():
        try:
            cfg = load_config(lay)
            out[lay] = parts(cfg)
            if cfg.get(USES):                               # 쓰는 카테고리는 이름 · home 층 정의문까지(B178 ② — 빈 층은 칸 지문 그대로)
                out[lay][USES] = _h(uses_view(cfg))
        except Exception:                                   # noqa: BLE001 — 못 읽는 층은 지문 0(대조가 「바뀜」으로 본다)
            out[lay] = {}
    out[COMMON_KEY] = parts(common_view(_common()))
    return out


def changed(old, new):
    """두 지문의 바뀐 칸 — `{갈래: ["층.키" …]}` (더함 · 지움 · 바뀜 전부 · 지난 기록에 없는 층은 대조하지 않는다)."""
    out = {"추출": [], "구축": [], "그 밖": []}
    for lay in sorted(set(old or {}) & set(new or {})):
        ren = RENAMED.get(lay, {})
        a, b = {ren.get(k, k): v for k, v in (old[lay] or {}).items()}, new[lay] or {}
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                for k in kinds(key, lay == COMMON_KEY):
                    out[k].append(f"{lay}.{key}")
    return out


def impact(registry=None, now=None):
    """**바꾸면 무엇이 다시 도나** — 문서 대장의 지난 지문과 지금 지문을 칸별로 대조한다.

    `{"기록 없음": 문서 수, "추출": {"문서": [...], "칸": [...]}, "구축": {...}, "그 밖": {"칸": [...]}}`.
    추출 갈래의 문서는 **추출 체크포인트가 있는 문서**(산문)만 — 바뀐 칸이 그 문서의 층(체크포인트의 `layer`)이거나 공통일 때.
    구축 갈래는 그 층(대장 행의 층) · 공통이면 모든 문서."""
    from core.state import store
    reg = registry if registry is not None else store.read(store.DOC_REGISTRY, {})
    now = now if now is not None else snapshot()
    out = {"기록 없음": 0, "추출": {"문서": [], "칸": set()}, "구축": {"문서": [], "칸": set()}, "그 밖": {"칸": set()}}
    for doc_id, e in sorted((reg or {}).items()):
        old = (e or {}).get("config_parts")
        if not old:
            out["기록 없음"] += 1
            continue
        ch = changed(old, now)
        out["그 밖"]["칸"] |= set(ch["그 밖"])
        lays = _doc_layers(doc_id)
        for k in ("추출", "구축"):
            hit = [c for c in ch[k] if c.split(".", 1)[0] in lays | {COMMON_KEY}]
            if k == "추출" and not lays.추출:
                hit = []
            if hit:
                out[k]["문서"].append(doc_id)
                out[k]["칸"] |= set(hit)
    for k in ("추출", "구축", "그 밖"):
        out[k]["칸"] = sorted(out[k]["칸"])
    return out


class _Lays(set):
    """문서의 층 — 집합(대장 행의 층 ∪ 체크포인트의 층) + `추출`(체크포인트가 있는가)."""


def _doc_layers(doc_id):
    from core.build import extract, ledger
    rows = (ledger.read(doc_id) or {}).get("rows") or []
    lays = _Lays(r.get("layer") for r in rows if r.get("layer"))
    cps = []
    for p in extract.checkpoint_files(doc_id):
        try:
            cps.append(json.loads(p.read_text(encoding="utf-8")).get("layer"))
        except (OSError, ValueError):
            continue
    lays |= {x for x in cps if x}
    lays.추출 = bool(cps)
    return lays


def lines(imp):
    """bootstrap 끝 줄 — 갈래마다 한 줄(바뀐 것이 없으면 「지난 인입과 같다」)."""
    head = "[bootstrap] config 영향"
    if not any(imp[k]["칸"] for k in ("추출", "구축", "그 밖")):
        tail = f" · 지난 인입의 config 기록 없음 {imp['기록 없음']:,}문서(다음 인입부터 잰다)" if imp["기록 없음"] else ""
        return [f"{head} — 지난 인입과 같다{tail}"]
    out = []
    ex, bu = imp["추출"], imp["구축"]
    if ex["칸"]:
        out.append(f"{head} — 추출 다시: 문서 {len(ex['문서']):,}(바뀐 칸 {' · '.join(ex['칸'])}) · "
                   f"다음 인입 · 재구축이 그 문서를 다시 뽑는다(LLM · 판은 자동)")
    if bu["칸"]:
        out.append(f"{head} — 재구축 때 LLM 0으로 다시 판정: 문서 {len(bu['문서']):,}(바뀐 칸 {' · '.join(bu['칸'])}) · "
                   f"python run.py rebuild")
    if imp["그 밖"]["칸"]:
        out.append(f"{head} — 영향 없음: {' · '.join(imp['그 밖']['칸'])}")
    if imp["기록 없음"]:
        out.append(f"{head} — 지난 인입의 config 기록 없음 {imp['기록 없음']:,}문서(대조 밖 · 다음 인입부터 잰다)")
    return out
