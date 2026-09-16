# -*- coding: utf-8 -*-
"""**스켈레톤을 그대로 채운 최소 어댑터** — 회귀 픽스처 (B76 ④ⓒ).

사내 실측 열여섯째가 이 자리를 열었다: 참조 어댑터 셋은 전부 `ditto_mark`를
갖고 있어서, **상동 기호가 없는 문서의 어댑터**가 공용 코어에 `None`을 넘기고
죽는 경로가 **한 번도 실행되지 않았다.** 스켈레톤은 회귀에 `tests/test_p3.py`의
**호출부 문자열**로만 들어 있었다(실행 0).

그래서 이 파일은 「스켈레톤의 빈칸을 최소로 채운 것」이고, 관문 전 구간(①~⑤)을
상시로 지난다. **`ditto_mark`가 없다** — 그것이 이 픽스처의 요점이다.

**USE_MOCK=1 자산이다**(B70) — `tests/fixtures/` 아래이고 `schemas/`·
`tests/fixtures/adapters/`가 아니므로 등록부·지문 스캔의 대상이 아니다.
"""
from parser import normalizer

ADAPTER = {
    "doc_type": "skelmin",
    "adapter_version": "1.0",
    "payload_kind": "table",
    "expects": {
        "header_row": 1,
        "data_start_row": 2,
        "header_labels": ["대공정", "세부공정", "공정번호", "설비",
                          "관리항목", "규격", "측정방법"],
        # 열 셋만 읽는다 — 스켈레톤이 낼 수 있는 가장 작은 어댑터다.
        "columns": {"process_group": "A", "process_ref": "B", "설비": "D"},
        # **`ditto_mark` 없음** — 이 표본에 상동 기호가 없다(규약 10의 단서).
        "required": ["process_ref"],
    },
}


def extract(raw) -> list[dict]:
    """스켈레톤 본문 그대로 — 셀은 읽기 꼴로만 읽는다(규약 11)."""
    exp = ADAPTER["expects"]
    fragments = []
    for sheet in (raw.get("sheets") or []):
        cells = normalizer.expand_merged(sheet)
        rows = []
        for row in range(exp.get("data_start_row", 1),
                         int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in (exp.get("columns") or {}).items():
                v = ""
                for c in (col if isinstance(col, (list, tuple)) else [col]):
                    v = cells.get(f"{c}{row}", "")
                    if v is not None and str(v).strip():
                        break
                rec[field] = "" if v is None else str(v).strip()
            if all(v == "" for v in rec.values()):
                continue
            rows.append((row, rec))

        recs, _d = normalizer.resolve_ditto(
            [r for _n, r in rows],
            marks={exp["ditto_mark"]} if exp.get("ditto_mark") else set())
        for (row, _r0), rec in zip(rows, recs or []):
            miss = [c for c in (exp.get("required") or []) if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")
            rec["source_locator"] = f"{sheet.get('name', 'sheet')}!R{row}"
            fragments.append(rec)

    if exp.get("multi_value_fields"):
        fragments, _m = normalizer.split_multi(
            fragments, exp["multi_value_fields"], exp.get("multi_value_seps"))
    return fragments
