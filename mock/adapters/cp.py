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
import re

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
        "ditto_mark": "〃",                 # 상동 기호 → 같은 열 직전 실값
        "multi_value_seps": [",", "/", "\n"],   # D-12 기본 닫힌 목록
        "multi_value_fields": ["설비", "관리항목"],
        # 자기완결 검사 대상 — 출력 필드명 기준 (공정명 → process_ref)
        "required": ["process_ref", "설비", "관리항목"],
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
    """병합 범위의 좌상단 값을 범위 내 전 셀에 복제한다(자기완결성)."""
    for rng in merged:
        try:
            tl, br = rng.split(":")
            m1, m2 = _CELL_RE.match(tl), _CELL_RE.match(br)
            if not m1 or not m2:
                continue
        except ValueError:
            continue
        c1, r1 = _col_to_idx(m1.group(1)), int(m1.group(2))
        c2, r2 = _col_to_idx(m2.group(1)), int(m2.group(2))
        val = cells.get(tl)
        if val is None:
            continue
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                key = "%s%d" % (_idx_to_col(c), r)
                if key not in cells or cells[key] in (None, ""):
                    cells[key] = val
    return cells


def extract(raw) -> list[dict]:
    """reader 원시 추출물 → 정규 조각 리스트. 조각마다 source_locator 포함."""
    exp = ADAPTER["expects"]
    fragments = []
    for sheet in raw.get("sheets", []):
        cells = dict(sheet.get("cells", {}))
        _expand_merged(cells, sheet.get("merged", []))

        prev = {}                           # 열문자 → 직전 실값 (상동 치환용)
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in exp["columns"].items():
                v = cells.get("%s%d" % (col, row), "")
                v = "" if v is None else str(v).strip()
                if v == exp["ditto_mark"]:
                    v = prev.get(col, "")
                if v != "":
                    prev[col] = v
                rec[field] = v

            if all(rec.get(c, "") == "" for c in exp["multi_value_fields"]):
                continue                    # 빈 행
            miss = [c for c in exp["required"] if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")

            base_loc = "%s!R%d" % (sheet.get("name", "sheet"), row)

            # 한 셀 복수값 → 행 전개 (첫 일치 구분자·첫 대상 열 — 참조 구현과 동일)
            expand = None
            for c in exp["multi_value_fields"]:
                v = rec.get(c, "")
                for sep in exp["multi_value_seps"]:
                    if sep in v:
                        expand = (c, [x.strip() for x in v.split(sep) if x.strip()])
                        break
                if expand:
                    break
            if not expand or len(expand[1]) <= 1:
                rec["source_locator"] = base_loc
                fragments.append(rec)
            else:
                col_name, parts = expand
                for i, part in enumerate(parts, 1):
                    r2 = dict(rec)
                    r2[col_name] = part
                    r2["source_locator"] = "%s#%d" % (base_loc, i)
                    fragments.append(r2)
    return fragments
