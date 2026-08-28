# 원본: tests/fixtures/fixtures/adapters/ipqc.py (외부 LLM 실산출 스냅샷)
# — 규약 10(공용 코어 호출) 전환본. 봉인 43판정 보존·산출 바이트 동일 실측(B27).
# 스냅샷 원문은 fixture가 보관한다 — 여기는 **모범 전시장**이다.
import re

from parser import normalizer

ADAPTER = {
    "doc_type": "ipqc",
    "adapter_version": "1.0",
    "payload_kind": "table",
    "expects": {
        "header_row": 3,
        "data_start_row": 4,
        # [D-29] preflight 표류 감지용 — 원본 헤더 문자열의 순서 배열
        "header_labels": [
            "대공정", "공정No", "공정명", "극성", "검사설비", "검사항목",
            "규격", "측정방법", "판정기준", "부적합 조치", "적용모델",
            "검사자", "검사일시", "성적서번호", "최근 불량 이력", "관련 표준문서",
        ],
        # {출력 필드명: 열문자} — 키는 원본 헤더가 아니라 출력 필드명(D-29)
        "columns": {
            "process_group": "A",   # 대공정 → 구조 필드(anchor는 process_coord 몫)
            "process_no": "B",      # 공정No → 구조 필드(meta)
            "process_ref": "C",     # 공정명 → 구조 필드(anchor는 process_coord 몫)
            "electrode_type": "D",  # 극성 → 구조 필드(entity 해소 코드가 직접 소비)
            "검사설비": "E",
            "검사항목": "F",
            "규격": "G",
            "측정방법": "H",
            "판정기준": "I",
            "부적합 조치": "J",
            "context": "K",         # 적용모델 → 구조 필드(맥락 상속 입력)
            "검사자": "L",
            "검사일시": "M",
            "성적서번호": "N",
            "관련 표준문서": "P",
            # O열(최근 불량 이력)은 UNMAPPABLE 판정 — 출력·스키마에서 제외(D-30, 산출물 3 참조)
        },
        "ditto_mark": "〃",             # 상동 기호 → 같은 열 직전 실값으로 치환
        "multi_value_sep": ", ",        # 한 셀 복수값(예: F30 "실링 폭, 실링 강도") → 행 전개
        "multi_value_field": "검사항목",
        # 문서 정보행(A2)의 "적용모델(기본): M1"에서 context 기본값을 읽는다
        "context_default_cell": "A2",
        "context_default_pattern": r"적용모델\(기본\)\s*:\s*(\S+)",
    },
}



# 열문자 변환·병합 전개·상동 치환·복수값 전개는 **공용 코어**를 부른다
# (문서 6 §6.4 규약 10). 어댑터가 아는 것은 이 문서의 열 위치와 뜻뿐이다.


def extract(raw) -> list[dict]:
    """reader 원시 추출물 → 정규 조각 리스트. 조각마다 source_locator 포함."""
    exp = ADAPTER["expects"]
    fragments = []
    for sheet in raw.get("sheets", []):
        cells = normalizer.expand_merged(sheet)          # ② 병합 전개 — 공용 코어

        # context 기본값: 문서 정보행에서 파싱 (예: "적용모델(기본): M1")
        default_ctx = ""
        info = cells.get(exp["context_default_cell"], "")
        m = re.search(exp["context_default_pattern"], str(info))
        if m:
            default_ctx = m.group(1)

        rows = []
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in exp["columns"].items():
                v = cells.get("%s%d" % (col, row), "")
                rec[field] = "" if v is None else str(v).strip()
            rows.append((row, rec))

        recs, _d = normalizer.resolve_ditto(              # ① 상동 — 공용 코어
            [r for _n, r in rows], marks={exp["ditto_mark"]})

        for (row, _r0), rec in zip(rows, recs):
            # 검사항목이 없는 행은 record가 아니다
            if rec.get("검사항목", "") == "":
                continue
            if rec.get("context", "") == "":
                rec["context"] = default_ctx
            rec["source_locator"] = "%s!R%d" % (sheet.get("name", "sheet"), row)
            fragments.append(rec)

    fragments, _m = normalizer.split_multi(               # ③ 복수값 — 공용 코어
        fragments, [exp["multi_value_field"]], [exp["multi_value_sep"]])
    return fragments
