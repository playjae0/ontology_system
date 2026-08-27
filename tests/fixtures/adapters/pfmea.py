# -*- coding: utf-8 -*-
"""참조 pfmea 어댑터 — S14(역산 정합) 재료.

`mock/adapters/cp.py`와 같은 지위다(D-69): fixtures는 외부 LLM 실산출 스냅샷이라
손대지 않고(D-26), 여기는 사람이 쓴 **참조 어댑터**다. S14가 요구하는
"raw 파싱 결과 = parsed JSON prefix"를 **실물 파서로** 검증하려면 pfmea의
expects·extract가 있어야 하는데 레포에 없었다(정식 산출은 P2·P3 소관).

구조는 `cp.py`와 같다 — 두 파일이 doc_type별로 다른 것은 **expects(관찰 상수)**뿐이고
extract 본체가 같다는 것이 어댑터 계약이 의도한 모양이다(§5: 선언 1개 + 함수 1개).
"""
from parser import normalizer

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



# 열문자 변환·병합 전개·상동 치환·복수값 전개는 **공용 코어**를 부른다
# (문서 6 §6.2). 어댑터가 아는 것은 이 문서의 열 위치와 뜻뿐이다.


def extract(raw) -> list[dict]:
    exp = ADAPTER["expects"]
    ints = set(exp.get("int_fields") or ())
    fragments = []
    for sheet in raw.get("sheets", []):
        cells = normalizer.expand_merged(sheet)          # ② 병합 전개 — 공용 코어
        rows = []
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in exp["columns"].items():
                raw_v = cells.get("%s%d" % (col, row), "")
                rec[field] = "" if raw_v is None else str(raw_v).strip()
            if all(v == "" for v in rec.values()):
                continue                     # 빈 행은 **전 열이 빈** 행뿐이다 (C14)
            rows.append((row, rec))

        # ① 상동 해소 — 공용 코어. **int 변환은 그 뒤다**: `〃`가 숫자 열에 오면
        # 먼저 변환할 값 자체가 없다.
        recs, _h = normalizer.resolve_ditto(
            [r for _n, r in rows], marks={exp["ditto_mark"]})

        for (row, _r0), rec in zip(rows, recs):
            miss = [c for c in exp["required"] if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")
            for f in ints:
                v = rec.get(f)
                if isinstance(v, str) and v.isdigit():
                    rec[f] = int(v)
            rec["source_locator"] = "%s!R%d" % (sheet.get("name", "sheet"), row)
            fragments.append(rec)

    fragments, _m = normalizer.split_multi(                # ③ 복수값 — 공용 코어
        fragments, exp["multi_value_fields"], exp["multi_value_seps"])
    return fragments
