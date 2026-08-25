# -*- coding: utf-8 -*-
"""참조 pfmea 어댑터 — S14(역산 정합) 재료.

`mock/adapters/cp.py`와 같은 지위다(D-69): fixtures는 외부 LLM 실산출 스냅샷이라
손대지 않고(D-26), 여기는 사람이 쓴 **참조 어댑터**다. S14가 요구하는
"raw 파싱 결과 = parsed JSON prefix"를 **실물 파서로** 검증하려면 pfmea의
expects·extract가 있어야 하는데 레포에 없었다(정식 산출은 P2·P3 소관).

구조는 `cp.py`와 같다 — 두 파일이 doc_type별로 다른 것은 **expects(관찰 상수)**뿐이고
extract 본체가 같다는 것이 어댑터 계약이 의도한 모양이다(§5: 선언 1개 + 함수 1개).
"""
import re

ADAPTER = {
    "doc_type": "pfmea",
    "adapter_version": "ref-1.0",
    "payload_kind": "table",
    "expects": {
        "header_row": 3,
        "data_start_row": 4,
        "header_labels": [
            "공정구분", "공정번호", "공정명", "극성", "고장모드", "고장원인",
            "영향분류", "심각도", "관리항목(모드)", "관리항목(원인)",
            "예방관리", "검출관리", "비고",
        ],
        "columns": {
            "process_group": "A", "process_no": "B", "process_ref": "C",
            "electrode_type": "D",
            "failure_mode": "E", "cause": "F", "effect_category": "G",
            "severity": "H",
            "control_item_for_fm": "I", "control_item_for_cause": "J",
            "prevention_control": "K", "detection_control": "L",
            "비고": "M",                     # UNMAPPABLE 아님 — unknown_field 재료(D-30 계보)
        },
        "ditto_mark": "〃",
        "multi_value_seps": [",", "/", "\n"],
        "multi_value_fields": ["failure_mode", "cause"],
        "required": ["process_ref", "failure_mode", "cause"],
        "int_fields": ["severity"],          # 숫자형 — 값 그대로 보존(문자열화 금지)
    },
}

_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _col_to_idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def _idx_to_col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _expand_merged(cells, merged):
    for rng in merged:
        if ":" not in str(rng):
            continue
        tl, br = str(rng).split(":", 1)
        m1, m2 = _CELL_RE.match(tl), _CELL_RE.match(br)
        if not m1 or not m2:
            continue
        c1, r1 = _col_to_idx(m1.group(1)), int(m1.group(2))
        c2, r2 = _col_to_idx(m2.group(1)), int(m2.group(2))
        val = cells.get(tl)
        if val is None:
            continue
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                key = "%s%d" % (_idx_to_col(c), r)
                if cells.get(key) in (None, ""):
                    cells[key] = val
    return cells


def extract(raw) -> list[dict]:
    exp = ADAPTER["expects"]
    ints = set(exp.get("int_fields") or ())
    fragments = []
    for sheet in raw.get("sheets", []):
        cells = _expand_merged(dict(sheet.get("cells", {})), sheet.get("merged", []))
        prev = {}
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in exp["columns"].items():
                raw_v = cells.get("%s%d" % (col, row), "")
                v = "" if raw_v is None else str(raw_v).strip()
                if v == exp["ditto_mark"]:
                    v = prev.get(col, "")
                if v != "":
                    prev[col] = v
                rec[field] = int(v) if (field in ints and v.isdigit()) else v
            if all(v == "" for v in rec.values()):
                continue                     # 빈 행은 **전 열이 빈** 행뿐이다 (C14)
            miss = [c for c in exp["required"] if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")

            base = "%s!R%d" % (sheet.get("name", "sheet"), row)
            expand = None
            for c in exp["multi_value_fields"]:
                v = rec.get(c, "")
                if not isinstance(v, str):
                    continue
                for sep in exp["multi_value_seps"]:
                    if sep in v:
                        expand = (c, [x.strip() for x in v.split(sep) if x.strip()])
                        break
                if expand:
                    break
            if not expand or len(expand[1]) <= 1:
                rec["source_locator"] = base
                fragments.append(rec)
            else:
                col_name, parts = expand
                for i, part in enumerate(parts, 1):
                    r2 = dict(rec)
                    r2[col_name] = part
                    r2["source_locator"] = "%s#%d" % (base, i)
                    fragments.append(r2)
    return fragments
