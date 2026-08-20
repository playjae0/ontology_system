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


def _col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def header_labels(raw, header_row, sheet=0):
    """그 행의 실물 헤더 문자열 배열 — 지문. 빈 셀은 건너뛴다."""
    if raw.get("format") != "xlsx" or not raw.get("sheets"):
        return []
    sh = raw["sheets"][sheet]
    out = []
    for c in range(1, sh["max_col"] + 1):
        v = sh["cells"].get(f"{_col(c)}{header_row}")
        if v is not None and str(v).strip():
            out.append(str(v).strip())
    return out


PROSE_SIGNALS = ("heading_pattern", "split_on", "indent", "bold", "text_column",
                 "level", "pattern", "number", "section", "content_column",
                 "struct_map")


def check(adapter, raw):
    """(ok, detail) — detail은 사람이 판정할 차이 내역이다.

    돌려주는 것이 불리언 하나면 "무엇이 달라졌나"를 사람이 다시 찾아야 한다.
    """
    a = adapter.ADAPTER if hasattr(adapter, "ADAPTER") else adapter
    exp = a.get("expects") or {}
    detail = {"doc_type": a.get("doc_type"), "adapter_version": a.get("adapter_version")}

    if a.get("payload_kind") == "prose":
        # 비정형은 헤더 행이 없다 — 분할 신호 상수가 선언돼 있는지만 본다.
        # (구조 가변 prose는 지도 패스가 분할하므로 힌트만 있어도 성립한다 — D-58)
        has = any(any(sg in str(k).lower() for sg in PROSE_SIGNALS) for k in exp)
        detail["signals"] = sorted(exp)
        return has, detail

    hr = exp.get("header_row")
    declared = exp.get("header_labels")
    if not hr or declared is None:
        detail["reason"] = "expects에 header_row/header_labels가 없다 (D-29 필수)"
        return False, detail

    actual = header_labels(raw, hr)
    detail.update({"declared": declared, "actual": actual,
                   "missing": [h for h in declared if h not in actual],
                   "extra": [h for h in actual if h not in declared]})
    return not detail["missing"] and not detail["extra"], detail
