# -*- coding: utf-8 -*-
"""어댑터 — doc_type: ipqc (공정검사성적서, 조립공정)

관찰 근거: mock/raw/IPQC01.xlsx, IPQC02.xlsx (시트명 '검사성적서')
  1행  제목(A1:P1 병합)  2행  문서정보(A2:P2 병합)  3행  헤더(굵게)  4행~ 데이터
  A 대공정 / B 공정No / C 공정명 / D 극성 / E 검사설비 / F 검사항목 / G 규격 /
  H 측정방법 / I 판정기준 / J 부적합 조치 / K 적용모델 / L 검사자 / M 검사일시 /
  N 성적서번호 / O 최근 불량 이력 / P 관련 표준문서

자기완결성 처리
  - 병합 셀(A/B/C)은 각 행에 복제한다. (IPQC01은 A4:A35·B/C 블록 병합,
    IPQC02는 A가 행마다 반복되고 B/C만 병합 — 두 표기 모두 동일 결과가 되도록 처리)
  - 상동 기호 '〃'(E열 관찰)는 같은 열의 직전 해소값으로 치환한다.
  - 한 셀 복수값(F열 '실링 폭, 실링 강도')은 행으로 전개한다.
  - 적용모델(K)이 비면 2행 문서정보의 '적용모델(기본): M1'을 상속한다.

순수 함수 — 네트워크·LLM·파일 접근 없음. 같은 입력이면 같은 출력.
"""

import re

ADAPTER = {
    "doc_type": "ipqc",
    "adapter_version": "1.0",
    "payload_kind": "table",
    "expects": {
        "sheet_name": "검사성적서",
        "title_row": 1,
        "doc_info_row": 2,
        "header_row": 3,
        "first_data_row": 4,
        "columns": {
            "process_group": "A",      # 대공정   (구조 필드 / anchor)
            "process_no": "B",         # 공정No   (구조 필드 / meta)
            "process_ref": "C",        # 공정명   (구조 필드 / anchor)
            "electrode_type": "D",     # 극성     (구조 필드, role 대상 아님)
            "검사설비": "E",
            "검사항목": "F",
            "규격": "G",
            "측정방법": "H",
            "판정기준": "I",
            "부적합 조치": "J",
            "context": "K",            # 적용모델 (구조 필드, role 대상 아님)
            "검사자": "L",
            "검사일시": "M",
            "성적서번호": "N",
            "최근 불량 이력": "O",      # UNMAPPABLE — 조각으로 내보내지 않는다
            "관련 표준문서": "P",       # UNMAPPABLE — 조각으로 내보내지 않는다
        },
        # 조각으로 내보내는 열(= 매칭 스키마 fields + 구조 필드)
        "emit_fields": [
            "process_group", "process_no", "process_ref", "electrode_type",
            "context", "검사설비", "검사항목", "규격", "측정방법",
            "판정기준", "부적합 조치", "검사자", "검사일시", "성적서번호",
        ],
        "unmappable_columns": ["최근 불량 이력", "관련 표준문서"],
        "ditto_marks": ["〃", "″", "”", "\"", "同上", "상동"],
        "merged_fill_columns": ["A", "B", "C"],
        "ditto_columns": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
        "multi_value_sep": ", ",
        "multi_value_fields": ["검사항목"],
        "context_default_pattern": r"적용모델\(기본\)\s*[:：]\s*([^\s]+)",
        "context_key": "model",
        "row_present_columns": ["E", "F", "G", "H", "I", "J", "L", "M", "N"],
    },
}

_DITTO = set(ADAPTER["expects"]["ditto_marks"])
_ADDR = re.compile(r"^([A-Z]+)([0-9]+)$")
_SPLIT = re.compile(r"\s*,\s*")


def _col_idx(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def _col_letter(idx):
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def _norm(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _fill_merged(sheet):
    """병합 범위의 좌상단 값을 범위 전체로 복제한 셀 맵을 만든다."""
    cells = dict(sheet.get("cells") or {})
    for rng in sheet.get("merged") or []:
        if ":" not in rng:
            continue
        a, b = rng.split(":", 1)
        ma, mb = _ADDR.match(a.strip()), _ADDR.match(b.strip())
        if not ma or not mb:
            continue
        c1, r1 = _col_idx(ma.group(1)), int(ma.group(2))
        c2, r2 = _col_idx(mb.group(1)), int(mb.group(2))
        src = cells.get(a.strip())
        if src is None:
            continue
        for c in range(min(c1, c2), max(c1, c2) + 1):
            for r in range(min(r1, r2), max(r1, r2) + 1):
                addr = "%s%d" % (_col_letter(c), r)
                if cells.get(addr) is None:
                    cells[addr] = src
    return cells


def _doc_context_default(cells, info_row, pattern):
    txt = cells.get("A%d" % info_row)
    if not isinstance(txt, str):
        return None
    m = re.search(pattern, txt)
    return m.group(1) if m else None


def extract(raw):
    """reader 원시 추출물 → 정규 조각 리스트. 조각마다 source_locator 포함."""
    out = []
    if not isinstance(raw, dict) or raw.get("format") != "xlsx":
        return out

    ex = ADAPTER["expects"]
    cols = ex["columns"]
    header_row = ex["header_row"]
    first_row = ex["first_data_row"]
    emit = ex["emit_fields"]

    for sheet in raw.get("sheets") or []:
        name = sheet.get("name") or "sheet"
        cells = _fill_merged(sheet)
        max_row = int(sheet.get("max_row") or 0)

        # 헤더 행이 관찰 상수와 어긋나면(다른 시트 등) 건너뛴다.
        if _norm(cells.get("A%d" % header_row)) != "대공정":
            # 이미지 placeholder만은 남긴다
            for im in sheet.get("images") or []:
                out.append({"source_locator": "%s!%s" % (name, im.get("cell")),
                            "image_ref": im.get("ref")})
            continue

        ctx_default = _doc_context_default(cells, ex["doc_info_row"],
                                           ex["context_default_pattern"])
        last = {}   # 열문자 → 직전 해소값 (상동 기호 치환용)

        for row in range(first_row, max_row + 1):
            present = any(_norm(cells.get("%s%d" % (c, row))) is not None
                          for c in ex["row_present_columns"])
            if not present:
                continue

            resolved = {}
            for field, col in cols.items():
                v = _norm(cells.get("%s%d" % (col, row)))
                if v in _DITTO and col in ex["ditto_columns"]:
                    v = last.get(col)
                if v is not None and col in ex["ditto_columns"]:
                    last[col] = v
                resolved[field] = v

            # 적용모델: 빈 칸이면 문서정보 행의 기본값을 상속
            model = resolved.get("context") or ctx_default
            resolved["context"] = {ex["context_key"]: model} if model else None

            # 한 셀 복수값 → 행으로 전개
            variants = []
            for f in ex["multi_value_fields"]:
                val = resolved.get(f)
                if isinstance(val, str) and _SPLIT.search(val):
                    parts = [p for p in _SPLIT.split(val) if p]
                    if len(parts) > 1:
                        variants.append((f, parts))
            n = max([len(p) for _, p in variants] or [1])

            for i in range(n):
                rec = {}
                for f in emit:
                    rec[f] = resolved.get(f)
                for f, parts in variants:
                    rec[f] = parts[i] if i < len(parts) else parts[-1]
                loc = "%s!R%d" % (name, row)
                if n > 1:
                    loc = "%s#%d" % (loc, i + 1)
                rec["source_locator"] = loc
                out.append(rec)

        for im in sheet.get("images") or []:
            out.append({"source_locator": "%s!%s" % (name, im.get("cell")),
                        "image_ref": im.get("ref")})

    return out
