# -*- coding: utf-8 -*-
"""칸 2.7 — normalizer — 자기완결 보정 4기능 (파서_명세 §3 · CH2 2.2 계약 ③ · D-12 확정).

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

#: **빈칸 표시**의 기본 닫힌 목록(B113 ②) — 사내는 공통 config `null_markers`로 고친다(목록이 데이터다).
#: 비교는 공백을 무시한다(「해당 없음」 = 「해당없음」). 파서는 core를 import하지 않으므로 목록은 함수로
#: 주입된다(`core.paths.bind_parser`) — 주입이 없으면(킷 · 시험) 이 기본값.
NULL_MARKERS = ("-", "—", "–", "N/A", "n/a", "해당 없음", "해당없음", "없음")
_MARKERS = None
#: 좌표 칸 — 빈칸 표시면 비워 문서 좌표를 물려받는다(계약 B `process_coord` 블록의 두 칸)
COORD_FIELDS = ("process_ref", "process_group")


def use_null_markers(fn):
    """목록을 돌려주는 함수를 주입한다(상태 루트의 공통 config)."""
    global _MARKERS
    _MARKERS = fn


def null_markers():
    if _MARKERS is None:
        return NULL_MARKERS
    try:
        got = _MARKERS()
    except Exception:                               # noqa: BLE001 — 읽지 못하면 기본값(파싱을 막지 않는다)
        return NULL_MARKERS
    return tuple(got) if got is not None else NULL_MARKERS


def null_marker(value, markers=None):
    """**빈칸 표시인가**(B113 ②) — 그렇다면 원문(앞뒤 공백 뺀 것) · 아니면 None. 문자열만 · 공백 무시 비교.
    표(좌표 칸 · 개체 칸)와 산문(추출 개체 표기 · 소속 이름)이 이 함수 하나를 쓴다."""
    if not isinstance(value, str):
        return None
    k = "".join(value.split())
    if not k:
        return None
    for m in (null_markers() if markers is None else markers):
        if k == "".join(str(m).split()):
            return value.strip()
    return None


def blank_coords(pieces, fields=COORD_FIELDS):
    """좌표 칸의 빈칸 표시 → 빈 값 — 다음 단계(`tagger.coord_from_section`)가 문서 좌표를 물려준다(지금 규칙) ·
    비운 칸은 `meta.null_marked`(있을 때만 — 표시 없는 조각은 그대로)."""
    out = []
    for p in pieces:
        hit = [f for f in fields if null_marker(p.get(f))]
        if hit:
            p = dict(p)
            m = dict(p.get("meta") or {})
            for f in hit:
                p[f] = None
            m["null_marked"] = sorted(set(m.get("null_marked") or []) | set(hit))
            p["meta"] = m
        out.append(p)
    return out


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

    **`marks=None`은 「상동 없음」이다**(B76 ④ⓐ · 사내 실측 열여섯째). 기본값은
    인자를 **안 줄 때만** 살아서, 호출자가 `None`을 계산해 넘기면 79행이
    `v.strip() in None`으로 죽었다 — 문자열 셀 하나만 있어도 터진다. 공용 코어가
    호출자의 `None`에 죽으면 그 위의 **어댑터 전부**가 죽는다(스켈레톤을 그대로
    채운 어댑터가 정확히 그 모양이었다).
    """
    marks = set(marks or ())
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
