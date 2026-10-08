# -*- coding: utf-8 -*-
"""칸 3.4 — **판정 재생** — 남긴 판정 대장으로 LLM 판정을 다시 부르지 않는다 (B106 ② · 사용자 결정 2026-10-07
「다시 다 LLM 판정하지 말고」).

값 판정의 순서: 골격 · 사전 → **재생** → (지금의) 좁히기 + LLM. 재료는 그 문서의 **지난 판정 대장**
(`work/ingest_log/<doc>.json` — fresh 기본이 남긴다)이고 문서 실행 시작에 한 번 읽는다(새 대장이 끝에
덮기 전에 · `begin`). 재생으로 붙은 행도 새 대장에 다시 적혀 다음 재구축의 재료가 된다(경로 `replay`).

**키** = (위치 `locator` · 열 `field` · 표기 · 부모 좌표(이름 규칙의 부모 canonical) · 층 · 카테고리) — 문서는
대장이 문서 하나의 것이라 키 밖에서 갈린다. 부모 좌표는 **이름 규칙이 canonical에 싣는 것**이라 「대장 행의
canonical(조회 키) = 지금 조립한 조회 키」로 잰다(스코프 카테고리면 부모가 다르면 키가 다르다 · 아니면 부모가
이름에 없다) — 그래서 이 열들이 없던 대장(B106 전)도 재료가 된다. 새 대장 행은 `category`·`scope`를 적는다. **재생은 판정 결과만 바꿔 끼운다** — 그 뒤(노드 생성 · 사전
등록 · 큐 · 대장 · 엣지)는 지금 코드 그대로다(`Builder.resolve_entity`의 한 자리 — 표 · 산문 · 렌즈가 다 지난다).

  · `match` → 그 행이 붙었던 노드(`target` canonical)가 지금 살아 있으면 그 노드(LLM 0 · 별칭 출처는 그때 경로대로)
  · `new` → 지금처럼 새 노드(LLM 0 — 같은 canonical이 이미 있으면 사전 단에서 이미 붙었다)
  · `uncertain` → 지금처럼 불확실(새 노드 + 큐 — LLM 0 · 가장 가까운 후보는 이름으로 다시 찾는다)
  · 그 밖(골격 밖 · 보류)은 재생하지 않는다 — 코드가 다시 판정한다

재생하지 않는 경우(→ 지금처럼 판정): 키가 대장에 없다(대장 행이 없는 판정 — 소속 대상 · 재시도도 여기) ·
대상 canonical이 없다(골격 이름·부모가 바뀌었다 등) · 끔(`--no-replay` — 문서 하나 또는 재구축 전부).
수는 문서마다(`DOC` — 판정 끝 줄)와 실행 누계(`STATS` — 재구축 보고)가 센다.
"""
from __future__ import annotations

from core.state.ids import norm
from core.state.status import is_live

#: 재생을 끈 사유(`--no-replay` → "끔") — None이면 켜져 있다
OFF = None

_ZERO = {"재생": 0, "재판정": 0, "키 없음": 0, "대상 없음": 0, "끔": 0}
#: 실행 누계 — 재구축 보고 · 문서마다는 `DOC`
STATS = dict(_ZERO)
DOC = dict(_ZERO)
#: 이번 문서의 재료 — `{키: 대장 행}`
TABLE = {}

REPLAYABLE = ("match", "new", "uncertain")


def reset(off=None):
    """실행 누계를 비우고 켜고 끈다 — 재구축 · 시험이 부른다."""
    global OFF
    OFF = off
    STATS.update(_ZERO)
    DOC.update(_ZERO)


def key(locator, field, surface, layer):
    """찾는 열쇠 — 같은 자리 · 같은 열 · 같은 표기 · 같은 집. 카테고리 · 부모 좌표는 행을 고를 때 잰다(`pick`)."""
    return (str(locator), str(field), norm(surface or ""), layer)


def begin(doc_id):
    """문서 실행 시작 — 그 문서의 지난 대장을 재료로 읽는다(새 대장이 덮기 전). 돌려주는 것은 재료 수."""
    from core.build import ledger
    DOC.update(_ZERO)
    TABLE.clear()
    data = ledger.read(doc_id) or {}
    n = 0
    for r in data.get("rows") or []:
        if r.get("role") != "entity" or r.get("verdict") not in REPLAYABLE:
            continue
        TABLE.setdefault(key(r.get("locator"), r.get("field"), r.get("surface"), r.get("layer")), []).append(r)
        n += 1
    return n


def _count(what):
    DOC[what] += 1
    STATS[what] += 1
    if what != "재생":
        DOC["재판정"] += 1
        STATS["재판정"] += 1


def _find(b, canonical, category):
    """이름 → 지금 그 집 그래프의 노드 하나(살아 있고 · 그 카테고리(겸 포함) · canonical 같음) · 없거나 여럿이면 None."""
    from core import matcher
    if not canonical:
        return None
    hosts = matcher._hosts(category)
    hit = {nid for nid in b.dict.lookup(canonical)
           if b.g.get(nid) and is_live(b.g.get(nid)) and matcher._is(b.g.get(nid), category, hosts)
           and norm(b.g.get(nid)["canonical"]) == norm(canonical)}
    return next(iter(hit)) if len(hit) == 1 else None


def _near(b, near, category):
    """불확실의 가장 가까운 후보 — 이름으로 지금 id를 다시 찾는다(옛 id는 재구축 뒤 없다)."""
    if not near:
        return None
    out = dict(near, id=_find(b, near.get("canonical"), category))
    out["top"] = [dict(t, id=_find(b, t.get("canonical"), category)) for t in near.get("top") or []]
    return out


def pick(b, at, surface, category, canonical):
    """재생 판정 — `(결과, 사유)`. 결과는 `(분기, node_id, 점수, 판정 dict)`(`matcher.resolve`와 같은 모양) 또는 None
    (지금처럼 판정) · 사유는 재생하지 못한 까닭(`키 없음` · `대상 없음` · `끔` — 대장 행 `replay`에 남는다).

    `at`은 `(위치, 열)` · `canonical`은 지금 조립한 조회 키(부모 좌표가 들어 있다). 같은 자리 · 같은 표기의 행이
    있는데 부모 좌표가 달라졌으면(골격 이름·부모가 바뀌었다) **대상 없음**이다 — 옛 이름에서 새 이름으로 옮겨
    재생하지 않는다(재판정 — 수가 보인다). 사전이 이미 답한 값에는 부르지 않는다(호출부가 사전 히트를 먼저 본다)."""
    if OFF:
        return _miss("끔")
    rows = [x for x in TABLE.get(key(at[0], at[1], surface, b.layer)) or ()
            if x.get("category") in (None, category)] if at else []
    if not rows:
        return _miss("키 없음")
    r = next((x for x in rows if norm(x.get("canonical") or "") == norm(canonical or "")), None)
    if r is None:
        return _miss("대상 없음")
    v = {"path": "replay", "replayed_path": r.get("path"), "candidates_n": 0,
         "confidence": r.get("confidence") or 0.0}
    if r["verdict"] == "match":
        nid = _find(b, r.get("target") or r.get("canonical"), category)
        if nid is None:
            return _miss("대상 없음")
        if r.get("same_doc"):
            v["same_doc"] = True
        _count("재생")
        return ("match", nid, v["confidence"], v), None
    if r["verdict"] == "uncertain":
        v["nearest"] = _near(b, r.get("nearest"), category)
    _count("재생")
    return (r["verdict"], None, v["confidence"], v), None


def _miss(why):
    _count(why)
    return None, why
