# -*- coding: utf-8 -*-
"""칸 0.1 — **config 칸의 영향 범위** — 바꾸면 무엇이 다시 도나 (B118 ⑥ · 사용자 2026-10-16 「기준 바꾸는 관리가 쉽고 명확해야」).

층 config · 층 공통 config의 최상위 키를 세 갈래로 가른다 — **분류는 이 표 하나다**(B120 ③ 추출 재사용의 판이 같은 표를 읽는다):

  · 추출 — 추출 입력에 실제로 들어가는 칸: 층 `categories`(이름 · 정의문) · `relations`(관계 이름) · `relevance_terms`(렌즈
    거름) · `extract_patterns`(mock 문형) · 공통 `categories`(겸 한 줄이 정의문 끝에 붙는다) → **산문 추출을 다시 뽑는다**
  · 구축 — 게이트 · 구축만: 층 `relation_patterns` · `category_pair_map` · `mirrors` · `polarity` · `skeleton` · 공통
    `canonical_scope` → **재구축이 LLM 0으로 다시 판정한다**(판정 재생 · 게이트 · 이름 규칙이 지금 config로)
  · 그 밖 — 질의(`query_*` · `fact_templates`) · 기록(판 번호 · `registration`) · 주석(`_`로 시작) · 표에 없는 키 → 영향 없음

**지난 인입이 쓴 config**는 문서 대장(`doc_registry.json`)의 `config_parts`(칸마다 내용 해시)다 — 인입이 적고(`ingest.register_doc`)
`bootstrap` 끝 줄이 지금과 칸별로 대조한다(`impact`). 내용은 저장하지 않는다(해시만 — 바뀌었나만 안다).
"""
from __future__ import annotations

import hashlib
import json

#: 층 config — 갈래마다 키(닫힌 표 · 밖은 「그 밖」)
LAYER = {"추출": ("categories", "relations", "relevance_terms", "extract_patterns"),
         "구축": ("relation_patterns", "category_pair_map", "mirrors", "polarity", "skeleton")}
#: 층 공통 config(`layers/common.json`)
COMMON = {"추출": ("categories",), "구축": ("canonical_scope",)}
COMMON_KEY = "공통"


def _h(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def kind(key, common=False):
    """키 하나의 갈래 — `추출` · `구축` · `그 밖`."""
    table = COMMON if common else LAYER
    return next((k for k, keys in table.items() if key in keys), "그 밖")


def parts(cfg):
    """config 하나의 칸 지문 `{키: 해시}` — 주석(`_`로 시작) 제외."""
    return {k: _h(v) for k, v in sorted((cfg or {}).items()) if not str(k).startswith("_")}


def snapshot(layers=None):
    """지금 config의 칸 지문 — `{층: {키: 해시}, "공통": {키: 해시}}` (층은 폴더 전부 · 공통 config가 없으면 빈 칸)."""
    from core import paths
    from core.state.bootstrap import load_config
    from router import discover
    out = {}
    for lay in layers or discover():
        try:
            out[lay] = parts(load_config(lay))
        except Exception:                                   # noqa: BLE001 — 못 읽는 층은 지문 0(대조가 「바뀜」으로 본다)
            out[lay] = {}
    p = paths.common()
    try:
        out[COMMON_KEY] = parts(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else {}
    except (OSError, ValueError):
        out[COMMON_KEY] = {}
    return out


def changed(old, new):
    """두 지문의 바뀐 칸 — `{갈래: ["층.키" …]}` (더함 · 지움 · 바뀜 전부 · 지난 기록에 없는 층은 대조하지 않는다)."""
    out = {"추출": [], "구축": [], "그 밖": []}
    for lay in sorted(set(old or {}) & set(new or {})):
        a, b = old[lay] or {}, new[lay] or {}
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                out[kind(key, lay == COMMON_KEY)].append(f"{lay}.{key}")
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
                   f"config_version을 올린다(올리지 않으면 옛 추출을 쓴다)")
    if bu["칸"]:
        out.append(f"{head} — 재구축 때 LLM 0으로 다시 판정: 문서 {len(bu['문서']):,}(바뀐 칸 {' · '.join(bu['칸'])}) · "
                   f"python run.py rebuild")
    if imp["그 밖"]["칸"]:
        out.append(f"{head} — 영향 없음: {' · '.join(imp['그 밖']['칸'])}")
    if imp["기록 없음"]:
        out.append(f"{head} — 지난 인입의 config 기록 없음 {imp['기록 없음']:,}문서(대조 밖 · 다음 인입부터 잰다)")
    return out
