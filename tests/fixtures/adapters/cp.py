# -*- coding: utf-8 -*-
"""참조 cp 어댑터 — S11(지문 스캔)의 재료.

**소재지가 mock/fixtures가 아닌 이유**: fixtures는 외부 LLM 실산출 스냅샷이라
손대지 않는다(D-26). 이 파일은 사람이 작성한 **참조 어댑터**다 — cp 양식의
expects·extract 실물이 레포 어디에도 없어 S11의 "확정 후 정상 파싱"이 성립하지
않았고(정식 산출은 P2 킷·P3 등록 소관), 그 공백을 mock 트랙에서 채운다.
P2의 참조 어댑터 예시(mock few-shot)가 서면 그쪽이 정본이 된다.

extract의 규격은 tests/verify_roundtrip.py의 참조 구현(read_table+normalize)과
같은 결과를 내는 것이다 — 병합 전개·상동 해소·복수값 전개(D-12 닫힌 구분자).
구조는 mock/fixtures/adapters/ipqc.py(3차 실산출)의 형태를 따른다.
"""
from parser import normalizer

ADAPTER = {
    "doc_type": "cp",
    "adapter_version": "ref-1.0",
    "payload_kind": "table",
    "expects": {
        "header_row": 3,                    # 헤더 3행 (D-16)
        "data_start_row": 4,
        # [D-29] preflight·지문 스캔 대조용 — 원본 헤더 문자열의 순서 배열
        "header_labels": [
            "공정구분", "공정번호", "공정명", "극성", "설비",
            "관리항목", "규격", "측정방법", "대응계획", "적용모델",
        ],
        # {출력 필드명: 열문자} — 키는 원본 헤더가 아니라 출력 필드명(D-29)
        "columns": {
            "process_group": "A",           # 공정구분 → 구조 필드
            "process_no": "B",              # 공정번호 → 구조 필드(meta)
            "process_ref": "C",             # 공정명 → 구조 필드(anchor는 블록 몫)
            "electrode_type": "D",          # 극성 → 구조 필드(entity 해소 코드 소비)
            "설비": "E",
            "관리항목": "F",
            "규격": "G",
            "측정방법": "H",
            "대응계획": "I",
            "context": "J",                 # 적용모델 → 구조 필드(맥락)
        },
        # `context`는 **임의 딕셔너리**가 계약이다(CH2 2.2) — 스칼라로 내면 인입이
        # `missing_field`로 표면화하고 그 필드를 버린다(D-60 실측). 키는 관찰 상수다.
        "context_key": "model",
        "ditto_mark": "〃",                 # 상동 기호 → 같은 열 직전 실값
        "multi_value_seps": [",", "/", "\n"],   # D-12 기본 닫힌 목록
        "multi_value_fields": ["설비", "관리항목"],
        # 자기완결 검사 대상 — 출력 필드명 기준 (공정명 → process_ref)
        "required": ["process_ref", "설비", "관리항목"],
    },
}



# **열문자 변환·병합 전개·상동 치환·복수값 전개는 공용 코어를 부른다**(문서 6 §6.2).
# 어댑터가 이것을 재구현하면 어댑터마다 같은 일을 하는 다른 코드가 쌓이고, 병합
# 처리에 버그가 나오면 **어댑터 전부를 고쳐야 한다** — 공용 코어 6종을 둔 설계 의도가
# 정확히 그것을 막는 것이다. 이 어댑터가 아는 것은 **이 문서의 열이 어디 있고
# 무엇인가**뿐이다.
#
# `parser.normalizer` import는 순수성 위반이 아니다 — 파일 밖 상태·네트워크·LLM이
# 아니라 **파서 내부의 순수 함수**다(어댑터 규약 1).


def extract(raw) -> list[dict]:
    """reader 원시 추출물 → 정규 조각 리스트. 조각마다 source_locator 포함.

    순서가 계약이다 — **병합 전개(셀 단계) → 행 읽기 → 상동 → 자기완결 검사 →
    복수값 전개(행 단계)**. 상동을 자기완결 검사보다 뒤에 두면 `〃`가 결측으로
    잡히고, 복수값 전개를 검사보다 앞에 두면 같은 결측이 여러 번 보고된다.
    """
    exp = ADAPTER["expects"]
    fragments = []
    for sheet in raw.get("sheets", []):
        # ② 병합 전개 — 공용 코어. 원본을 바꾸지 않고 새 dict를 돌려준다.
        cells = normalizer.expand_merged(sheet)

        rows = []                           # (행번호, 레코드) — 상동 전이라 원값 그대로
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in exp["columns"].items():
                v = cells.get("%s%d" % (col, row), "")
                rec[field] = "" if v is None else str(v).strip()
            # **빈 행은 전 열이 빈 행뿐이다.** 일부만 비었으면 그것은 여백이 아니라
            # 결측이고, 빈 행으로 삼켜 버리면 그 행이 조용히 사라진다(C14 위반 —
            # 한 칸씩 밀린 행이 정확히 그 모양이다: CP03_bad 15행).
            if all(v == "" for v in rec.values()):
                continue
            rows.append((row, rec))

        # ① 상동 해소 — 공용 코어. 마크는 이 문서의 관찰 상수를 쓴다.
        recs, _hits = normalizer.resolve_ditto(
            [r for _n, r in rows], marks={exp["ditto_mark"]})

        for (row, _raw_rec), rec in zip(rows, recs):
            miss = [c for c in exp["required"] if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")
            if rec.get("context") and exp.get("context_key"):
                rec["context"] = {exp["context_key"]: rec["context"]}
            elif "context" in rec and not rec["context"]:
                del rec["context"]          # 빈 맥락은 봉투 값을 그대로 상속한다
            rec["source_locator"] = "%s!R%d" % (sheet.get("name", "sheet"), row)
            fragments.append(rec)

    # ③ 복수값 분리 — 공용 코어. 첫 대상 필드·첫 일치 구분자 하나만 전개하고
    # `source_locator`에 `#n`을 붙인다(파서_명세 §5 규약 1).
    fragments, _mh = normalizer.split_multi(
        fragments, exp["multi_value_fields"], exp["multi_value_seps"])
    return fragments
