# -*- coding: utf-8 -*-
"""preflight — 실행 전 정합 검사 (파서_명세 §5 규약 6 · 카드 C15).

    문서의 실물 지문  ↔  ADAPTER.expects     결정적 대조 (LLM 아님 — M2의 정신)

**등록 여부 조회를 대체하지 않는다.** 조회가 모드를 가르고(등록됐나 → 운영 / 아니면
구축), preflight는 **운영 모드 안의 양식 표류**를 잡는다. 불일치면 extract를 실행하지
않고 문서를 중단한 뒤 `adapter_mismatch`로 차이 내역과 adapter_version을 제시한다 —
이후 판단은 사람 둘 중 하나다: 어댑터 개정(구축 모드 재진입) 또는 신규 doc_type 등록.

**대조 재료는 `header_labels`다**(D-29 — table 한정). `columns`는 출력 필드명 매핑이라
프롬프트가 필드명 변환을 지시한 순간 표류 감지가 무력화된다. 그래서 둘을 갈랐다.
prose는 헤더 행이 없으므로 **분할 신호 상수의 존재**를 본다.
"""
from __future__ import annotations

from .normalizer import _col
from .reader import norm_label, sheet_of



def header_labels(raw, header_row, expects=None):
    """그 행의 실물 헤더 문자열 배열 — 지문. 빈 셀은 건너뛴다.

    **`format`을 보지 않는다**(B62 ①-a). 구판은 `format != "xlsx"`면 `[]`를 돌려줬고,
    CSV 리더는 「xlsx로 위장하지 않는다」고 정직하게 `format: "csv"`를 내므로 **CSV
    table 어댑터는 preflight를 통과할 수 없었다** — 선언한 열이 전부 `missing`이 된다
    (실측: 19개 선언 · missing 19 · extra 0). 격자인가는 `sheets`가 답한다.
    """
    sh, err = sheet_of(raw, expects)
    if err:
        return []
    out = []
    for c in range(1, (sh.get("max_col") or 0) + 1):
        v = norm_label(sh.get("cells", {}).get(f"{_col(c)}{header_row}"))
        if v:
            out.append(v)
    return out


def header_row_suspect(raw, exp):
    """`columns`가 가리키는 열의 **헤더 셀이 비어 있나** — 비면 detail, 아니면 `None`.

    시스템이 헤더 문자열을 채우기 **전에** 위치를 검증하는 자리다(B62 ①-c). 채우는
    일은 결정적이지만 **`header_row`가 틀렸으면 결정적으로 틀린 값을 채운다** — 빈
    행을 읽어 `header_labels`를 `[]`로 덮어쓰면 표류 감지가 조용히 죽는다.
    """
    hr, cols = exp.get("header_row"), (exp.get("columns") or {})
    if not hr or not cols:
        return None
    sh, err = sheet_of(raw, exp)
    if err:
        return None                       # 시트 해석 실패는 check()가 따로 말한다
    cells = sh.get("cells") or {}
    empty = sorted({str(v) for v in cols.values()
                    if isinstance(v, str) and not norm_label(cells.get(f"{v}{hr}"))})
    if not empty:
        return None
    got = [norm_label(cells.get(f"{_col(c)}{hr}"))
           for c in range(1, (sh.get("max_col") or 0) + 1)]
    return {"reason": f"header_row 의심 — {sh.get('name')}!{hr}행에서 읽힌 값: "
                      f"{[g for g in got if g][:5]}",
            "empty_columns": empty, "header_row": hr}


PROSE_SIGNALS = ("heading_pattern", "split_on", "indent", "bold", "text_column",
                 "level", "pattern", "number", "section", "content_column",
                 "struct_map")


# 구조 가변 prose의 **지문 키** — 힌트와 별개다 (문서 6 §6.4-9).
# 힌트(heading_pattern 등)는 **강제가 아니므로** 지문이 따로 없으면 adapter_mismatch
# 판정이 성립하지 않는다 — "선언돼 있나"만 보면 어떤 문서를 넣어도 통과한다.
PROSE_FINGERPRINTS = ("title_row", "max_col")


def _sheet(raw, exp=None):
    """지문 검사용 시트 — **해석기는 리더 하나다**(B62 ①-b). 못 고르면 빈 dict."""
    sh, err = sheet_of(raw, exp)
    return {} if err else sh


def _fp_title_row(exp, raw):
    """`title_row`: 그 행에 **내용이 있는가.** 값이 문자열이면 그 문자열과 대조한다."""
    want = exp["title_row"]
    cells = _sheet(raw, exp).get("cells") or {}
    row = want if isinstance(want, int) else 1
    got = [v for k, v in cells.items() if str(k)[1:].isdigit() and int(str(k)[1:]) == row]
    if isinstance(want, str):
        return (want in [str(v) for v in got]), {"want": want, "got": got[:3]}
    return bool(got), {"want_row": row, "got": got[:3]}


def _fp_max_col(exp, raw):
    """`max_col`: 실제 최대 열 수가 선언을 넘지 않는가 — 넘으면 양식 표류다."""
    want = exp["max_col"]
    cells = _sheet(raw, exp).get("cells") or {}
    cols = {"".join(ch for ch in str(k) if ch.isalpha()) for k in cells}
    n = max((len(c) * 26 - 26 + (ord(c[-1]) - 64) if c else 0) for c in cols) if cols else 0
    return n <= int(want), {"want_max": want, "actual_max": n}


FP_CHECKS = {"title_row": _fp_title_row, "max_col": _fp_max_col}


def _prose(exp, raw, detail):
    """prose preflight — **prose라고 생략하지 않는다** (문서 6 §6.4-9).

    두 갈래다:

    - **구조 가변 prose**: `expects`에 지문 키(`title_row`·`max_col` 등)를 두고
      **실물과 대조**한다. 지도 패스가 분할을 맡더라도 "이 문서가 그 계열이 맞나"는
      지문이 답해야 한다.
    - **분할 자명 prose**: 분할 신호 상수(`split_on`·`max_chars` 등)가 **그대로
      지문**이다. 선언이 있는지만 본다 — 슬라이드 문서에는 대조할 행·열이 없다.

    지문 키가 하나라도 선언돼 있으면 첫째 갈래로 판정한다. 지문이 어긋나면
    `adapter_mismatch`이고, detail에 **무엇이 어긋났는지**가 실린다.
    """
    fps = [k for k in PROSE_FINGERPRINTS if k in exp]
    detail["signals"] = sorted(exp)
    if fps:
        detail["fingerprints"] = {}
        ok = True
        for k in fps:
            good, info = FP_CHECKS[k](exp, raw)
            detail["fingerprints"][k] = {"ok": good, **info}
            ok = ok and good
        if not ok:
            detail["reason"] = "구조 가변 prose 지문 불일치"
        return ok, detail
    has = any(any(sg in str(k).lower() for sg in PROSE_SIGNALS) for k in exp)
    if not has:
        detail["reason"] = "분할 신호 상수가 expects에 없다 (지문이 없으면 판정 불가)"
    return has, detail


def check(adapter, raw):
    """(ok, detail) — detail은 사람이 판정할 차이 내역이다.

    돌려주는 것이 불리언 하나면 "무엇이 달라졌나"를 사람이 다시 찾아야 한다.
    """
    a = adapter.ADAPTER if hasattr(adapter, "ADAPTER") else adapter
    exp = a.get("expects") or {}
    detail = {"doc_type": a.get("doc_type"), "adapter_version": a.get("adapter_version")}

    if a.get("payload_kind") == "prose":
        return _prose(exp, raw, detail)

    hr = exp.get("header_row")
    declared = exp.get("header_labels")
    if not hr or declared is None:
        detail["reason"] = "expects에 header_row/header_labels가 없다 (D-29 필수)"
        return False, detail

    # **시트 해석 실패는 그 자체가 표류다**(B62 ①-b) — 어느 시트인지 정해지지
    # 않은 채로 헤더를 읽으면 그 선택이 어디에도 안 남는다.
    _sh, _err = sheet_of(raw, exp)
    if _err:
        detail.update(_err)
        detail["reason"] = _err["reason"]
        return False, detail
    suspect = header_row_suspect(raw, exp)
    if suspect:
        detail.update(suspect)
        return False, detail
    # **선언은 정규화해서 맞춘다** — 실물 쪽만 정규화하면 같은 셀이 다르게 읽힌다.
    declared = [norm_label(h) for h in declared]
    actual = header_labels(raw, hr, exp)
    detail.update({"declared": declared, "actual": actual, "sheet": _sh.get("name"),
                   "missing": [h for h in declared if h not in actual],
                   "extra": [h for h in actual if h not in declared]})
    return not detail["missing"] and not detail["extra"], detail
