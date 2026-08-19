# -*- coding: utf-8 -*-
"""normalizer — 자기완결 보정 4기능 (파서_명세 §3 · CH2 2.2 계약 ③ · D-12 확정).

    ①상동 해소  ②병합 셀 전개  ③복수값 분리  ④nested 평탄화

**자기완결성이 계약이다**(C4): 조각 하나만 봐도 뜻이 서야 한다. "〃"는 위 행을 봐야
알고, 병합 셀은 좌상단을 봐야 알고, "실링 폭, 실링 강도"는 두 관리항목이 한 칸에
있는 것이고, 중첩 구조는 role 핸들러가 못 읽는다 — 넷 다 **인입 전에** 푼다.

**이미 자기완결인 산출은 통과시켜도 변하지 않는다**(멱등). 어댑터가 자기 안에서 상동을
풀고 복수값을 전개한 경우가 그렇다 — 여기서 또 전개하면 **이중 전개**가 되어 조각이
증식한다. 그래서 전 기능이 "풀 것이 있을 때만" 손댄다.

**구분자는 관찰 상수다**(D-12): 기본 닫힌 목록 + 어댑터 `expects`로 doc_type별 재정의.
"""
from __future__ import annotations

DITTO = {"〃", "〝", "상동", "same as above"}
DEFAULT_SEPS = [",", "/", "\n"]                 # D-12 기본 닫힌 목록


def _col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------- ② 병합 전개
def expand_merged(sheet):
    """병합 범위의 좌상단 값을 범위 내 전 셀에 복제한다 — **원본을 바꾸지 않는다.**

    reader는 병합을 전개하지 않고 범위만 준다(계약) — 전개는 여기 몫이다.
    """
    cells = dict(sheet.get("cells") or {})
    for rng in sheet.get("merged") or []:
        if ":" not in str(rng):
            continue
        tl, br = str(rng).split(":", 1)
        try:
            c1 = _idx(tl); c2 = _idx(br)
        except ValueError:
            continue
        val = cells.get(tl)
        if val is None:
            continue
        for r in range(c1[1], c2[1] + 1):
            for c in range(c1[0], c2[0] + 1):
                key = f"{_col(c)}{r}"
                if cells.get(key) in (None, ""):
                    cells[key] = val
    return cells


def _idx(addr):
    letters = "".join(ch for ch in addr if ch.isalpha())
    digits = "".join(ch for ch in addr if ch.isdigit())
    if not letters or not digits:
        raise ValueError(addr)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n, int(digits)


# ---------------------------------------------------------------- ① 상동 해소
def resolve_ditto(records, fields=None, marks=DITTO):
    """상동 기호를 **같은 필드의 직전 실값**으로 치환한다. 없으면 그대로 둔다.

    직전 값이 없으면(첫 행이 상동) 채울 근거가 없으므로 건드리지 않는다 —
    validator의 자기완결 검사가 그것을 잡는다. 여기서 추측하지 않는다.
    """
    prev, out, hits = {}, [], 0
    for rec in records:
        r = dict(rec)
        for f in (fields or r.keys()):
            v = r.get(f)
            if isinstance(v, str) and v.strip() in marks:
                if f in prev:
                    r[f] = prev[f]
                    hits += 1
            elif v not in (None, ""):
                prev[f] = v
        out.append(r)
        # 치환한 값도 다음 행의 기준이 된다(연쇄 상동)
        for f in (fields or r.keys()):
            if r.get(f) not in (None, ""):
                prev[f] = r[f]
    return out, hits


# ---------------------------------------------------------------- ③ 복수값 분리
def split_multi(records, fields, seps=None, locator_key="source_locator"):
    """한 칸의 복수값을 **행으로 전개**한다 — 첫 일치 구분자·첫 대상 필드 하나만.

    전개하면 `source_locator`에 `#n` 접미를 붙여 유일성을 지킨다(파서_명세 §5 규약 1).
    **전개할 것이 없으면 원본을 그대로 돌려준다**(멱등 — 이중 전개 방지).
    """
    seps = seps or DEFAULT_SEPS
    out, hits = [], 0
    for rec in records:
        target = None
        for f in fields:
            v = rec.get(f)
            if not isinstance(v, str):
                continue
            for sep in seps:
                if sep in v:
                    parts = [x.strip() for x in v.split(sep) if x.strip()]
                    if len(parts) > 1:
                        target = (f, parts)
                    break
            if target:
                break
        if not target:
            out.append(rec)
            continue
        f, parts = target
        hits += 1
        base = rec.get(locator_key)
        for i, p in enumerate(parts, 1):
            r = dict(rec)
            r[f] = p
            if base:
                r[locator_key] = f"{base}#{i}"
            out.append(r)
    return out, hits


# ---------------------------------------------------------------- ④ nested 평탄화
def flatten(records, sep="."):
    """중첩 딕셔너리를 `부모.자식` 키로 편다 — **role 핸들러는 단일 값만 본다**(D6).

    `context`는 임의 딕셔너리가 계약이므로(CH2 2.2) 펴지 않는다. `meta`도 같다 —
    둘은 구조 필드이고 소비자가 role 핸들러가 아니라 시스템 코드다(C17).
    """
    keep = {"context", "meta"}
    out, hits = [], 0
    for rec in records:
        r = {}
        for k, v in rec.items():
            if isinstance(v, dict) and k not in keep:
                hits += 1
                for k2, v2 in v.items():
                    r[f"{k}{sep}{k2}"] = v2
            else:
                r[k] = v
        out.append(r)
    return out, hits


# ---------------------------------------------------------------- 진입점
def normalize(records, *, ditto_fields=None, multi_fields=(), seps=None):
    """4기능을 순서대로 — 상동 → 복수값 → nested. (병합 전개는 셀 단계라 별도)

    돌려주는 것은 `(records, report)`이고 report는 기능별 적용 건수다 — **0이면
    이미 자기완결이었다는 뜻**이고, 그것이 정상이다(어댑터가 자기 안에서 풀었다).
    """
    recs, d = resolve_ditto(records, ditto_fields)
    recs, m = split_multi(recs, list(multi_fields), seps) if multi_fields else (recs, 0)
    recs, f = flatten(recs)
    return recs, {"ditto": d, "multi": m, "nested": f}
