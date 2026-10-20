# -*- coding: utf-8 -*-
"""칸 3.3 곁 — **산문의 값** — 「항목 = 값」을 주인 아래 노드의 속성으로 (B120 ① · 문서 4 §4.6).

    추출 개체의 `value`(청크 원문 글자 그대로 — 단위 · 범위 · 조건 꼴 그대로)
      ├ 그 카테고리가 층 config `value_categories`에 없다 → 값 아님(지금 동작 그대로 · 수에 들지 않는다)
      ├ 청크 원문에 글자 그대로 없다 → **버림**(결함 로그 — 지어낸 값 · 계산한 값)
      └ 노드가 섰다 → `Builder.put_attribute`(**표의 attribute와 같은 함수** — 같은 맥락 다른 값 = `spec_conflict` ·
        덮어쓰기 0) → **실림** 또는 **충돌**

선언은 `{카테고리: 속성 이름}`이다 — 속성 이름이 표의 등록 스키마 `attr_name`과 같으면 표와 산문의 값이 한 칸에서
만나 충돌 판정을 같이 받는다. 산문 값은 맥락 축이 없다(단순형 — 빈 맥락 한 그룹 · §4.6-4 「맥락 축은 미리 발명하지
않는다」). 결과는 개체 행의 `value`(`{attr, value, verdict}`)에 남고 맞춤표 · 한 줄 요약이 그 행에서 센다.
"""
from __future__ import annotations

from core.build.build import ATTR_CONFLICT
from core.state import store

#: 층 config 키 — 값을 받는 카테고리 → 값을 싣는 속성 이름(선택 · 없으면 산문 값 0)
KEY = "value_categories"
#: 개체 행 `value.verdict` — 닫힌 셋(맞춤표 · 한 줄 요약의 칸)
LANDED, DROPPED, CONFLICT = "실림", "버림", "충돌"
VERDICTS = (LANDED, DROPPED, CONFLICT)


def attr_name(cfg, category):
    """그 카테고리의 값을 싣는 속성 이름 — 선언이 없으면 None(값 아님)."""
    decl = (cfg or {}).get(KEY) or {}
    name = decl.get(category) if isinstance(decl, dict) else None
    return str(name) if name else None


def _flat(s):
    return " ".join(str(s or "").split())


def verbatim(value, text):
    """값이 청크 원문에 **글자 그대로** 있는가 — 공백의 줄바꿈 · 겹침만 하나로 본다(그 밖의 글자는 그대로)."""
    v = _flat(value)
    return bool(v) and v in _flat(text)


def land(cfg, eb, nid, e, chunk, prov, cid, row):
    """개체 하나의 값 — 노드 `nid`(집 빌더 `eb`)에 싣고 개체 행에 결과를 단다 · 값이 아니면 아무것도 하지 않는다.

    선언은 **추출이 본 config**(`cfg` — 그 문서 · 렌즈의 층)에서 읽는다 — 추출 입력의 `value_categories`와 추출 재사용 판이
    같은 config라 「뽑을 때의 선언」과 「실을 때의 선언」이 갈리지 않는다."""
    value = e.get("value")
    name = attr_name(cfg, e.get("category"))
    if value in (None, "") or not name or not nid:
        return None
    value = str(value)
    from core.build.extract_unit import _is_image, text_of
    # 원문 = 본문 · 표 · 차트 · 노트(그 청크가 진 것) — **그림 요약 글은 원문이 아니다**(B125 ① — 그림 · 캡처에서 온 값은 버린다)
    if not verbatim(value, "" if _is_image(chunk or {}) else text_of(chunk or {})):
        store.append_defect(f"{eb.doc_id}: 값 버림 — 청크 원문에 없다 '{value[:60]}' "
                            f"(개체 '{e.get('surface')}' @ {cid})")
        verdict = DROPPED
    else:
        got = eb.put_attribute(nid, name, value, None, prov, False)
        verdict = CONFLICT if got == ATTR_CONFLICT else LANDED
    if row is not None:
        row["value"] = {"attr": name, "value": value, "verdict": verdict}
    return verdict


def counts(rows):
    """개체 행에서 — `{실림, 버림, 충돌}`(값을 낸 개체 행만)."""
    out = {k: 0 for k in VERDICTS}
    for r in rows or []:
        v = (r.get("value") or {}).get("verdict")
        if v in out:
            out[v] += 1
    return out
