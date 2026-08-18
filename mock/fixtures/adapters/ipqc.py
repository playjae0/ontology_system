import re

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
    """병합 범위의 좌상단 값을 범위 내 전 셀에 복제한다(자기완결성 규약 5)."""
    for rng in merged:
        try:
            tl, br = rng.split(":")
            m1 = _CELL_RE.match(tl)
            m2 = _CELL_RE.match(br)
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

        # context 기본값: 문서 정보행에서 파싱 (예: "적용모델(기본): M1")
        default_ctx = ""
        info = cells.get(exp["context_default_cell"], "")
        m = re.search(exp["context_default_pattern"], str(info))
        if m:
            default_ctx = m.group(1)

        prev = {}  # 열문자 → 직전 실값 (상동 기호 치환용)
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

            # 검사항목이 없는 행은 record가 아니다
            if rec.get("검사항목", "") == "":
                continue

            if rec.get("context", "") == "":
                rec["context"] = default_ctx

            base_loc = "%s!R%d" % (sheet.get("name", "sheet"), row)

            # 한 셀 복수값 → 행으로 전개 (locator에 접미사로 유일성 보장)
            parts = [p.strip() for p in rec[exp["multi_value_field"]].split(exp["multi_value_sep"]) if p.strip()]
            if len(parts) <= 1:
                rec["source_locator"] = base_loc
                fragments.append(rec)
            else:
                for i, part in enumerate(parts, 1):
                    r2 = dict(rec)
                    r2[exp["multi_value_field"]] = part
                    r2["source_locator"] = "%s#%d" % (base_loc, i)
                    fragments.append(r2)
    return fragments
