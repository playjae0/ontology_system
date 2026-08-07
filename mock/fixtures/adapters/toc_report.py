# -*- coding: utf-8 -*-
"""doc_type: toc_report — 목차형(줄글) 현황 보고서 어댑터.

관찰 표본: mock/raw/TOC01.xlsx (3레벨 번호, 이미지 2), TOC02.xlsx (2레벨 번호, 이미지 1).

분할 규칙(관찰 근거):
  - 1행은 문서 제목(사용자 힌트). 청크로 내지 않고 meta.doc_title로만 보존한다.
  - 헤딩 판별은 **번호 패턴**이 1차 신호다: `^\\d+(\\.\\d+)*` (예: "1.", "1.1", "1.1.1").
    두 표본 모두에서 예외 없이 성립한다.
  - 굵게(bold)는 보조 신호일 뿐이다. TOC01의 3레벨 헤딩("1.1.1 설비 구성")은 굵지 않고,
    본문은 항상 굵지 않다. 즉 bold는 헤딩의 충분조건도 필요조건도 아니다.
  - 들여쓰기(indent)는 헤딩 레벨과 대체로 대응하나(L1=0, L2=1, L3=2, 본문=3)
    TOC01 A12가 indent=5로 어긋난다. 그래서 indent는 **분할에 쓰지 않는다**
    (번호 패턴만으로 계층이 결정되므로 추측 규칙을 만들 필요가 없다).
  - 청크 경계 = 헤딩 등장 지점 + 이미지 위치. 한 헤딩 아래 연속한 본문 줄은
    하나의 청크로 묶고(줄바꿈으로 결합) section에 헤딩 경로를 붙인다.
  - 하위 헤딩만 갖고 본문이 없는 헤딩(예: "1. 조립 공정 개요")은 청크를 만들지 않는다.
    본문도 하위 헤딩도 없는 잎 헤딩은 제목만으로 청크를 만든다(유실 방지).
  - 이미지는 그 위치의 section을 달아 placeholder 조각으로만 낸다(요약 호출 없음).
"""
import re

ADAPTER = {
    "doc_type": "toc_report",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        # --- 문서 지문(관찰 상수) ---
        "title_row": 1,                       # 힌트: 1행은 제목
        "text_column": "A",                   # 두 표본 모두 max_col=1 단일 열
        # --- 분할 신호 ---
        "heading_pattern": r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(\S.*)$",
        "heading_level_from": "번호 마디 수",   # "1"→1, "1.1"→2, "1.1.1"→3
        "heading_levels_observed": [1, 2, 3],  # TOC01=3레벨, TOC02=2레벨
        "split_on": ["heading", "image"],
        "section_sep": " > ",
        "body_join": "\n",
        # --- 보조(신뢰도 낮음) 신호: 분할에 사용하지 않음 ---
        "bold_hint": "L1·L2 헤딩과 제목만 굵음. L3 헤딩은 굵지 않음 → 보조 신호",
        "indent_by_level_observed": {"1": 0, "2": 1, "3": 2},
        "body_indent_observed": [3, 5],        # 5는 TOC01 A12 단발 이탈 → 규칙화 불가
        "indent_used_for_split": False,
        "multi_value_sep": None,               # 한 셀 복수값·병합셀·상동기호 없음
    },
}

_HEADING_RE = re.compile(ADAPTER["expects"]["heading_pattern"])
_ADDR_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _split_addr(addr):
    m = _ADDR_RE.match(addr)
    if not m:
        return None, None
    col, row = m.group(1), int(m.group(2))
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n, row


def _cell_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _rows_of_sheet(sheet):
    """행 번호 → (첫 셀 주소, 합쳐진 텍스트). 값 있는 셀만, 열 순서로 결합."""
    buckets = {}
    for addr, value in sheet.get("cells", {}).items():
        colnum, row = _split_addr(addr)
        if row is None:
            continue
        text = _cell_text(value)
        if not text:
            continue
        buckets.setdefault(row, []).append((colnum, addr, text))
    out = {}
    for row, items in buckets.items():
        items.sort()
        out[row] = (items[0][1], " ".join(t for _, _, t in items))
    return out


def _locator(sheet_name, col_letter, rows):
    if not rows:
        return "%s!%s" % (sheet_name, col_letter)
    if len(rows) == 1 or rows[0] == rows[-1]:
        return "%s!%s%d" % (sheet_name, col_letter, rows[0])
    return "%s!%s%d:%s%d" % (sheet_name, col_letter, rows[0], col_letter, rows[-1])


def extract(raw):
    """reader 원시 추출물 → prose 조각 리스트 (순수 함수)."""
    frags = []
    if not isinstance(raw, dict) or raw.get("format") != "xlsx":
        return frags

    doc_path = raw.get("path")

    for sheet in raw.get("sheets", []):
        sheet_name = sheet.get("name") or "Sheet1"
        rowmap = _rows_of_sheet(sheet)
        indent_map = sheet.get("indent", {}) or {}
        bold_set = set(sheet.get("bold", []) or [])

        images_by_row = {}
        for im in sheet.get("images", []) or []:
            cell = im.get("cell")
            _, r = _split_addr(cell) if cell else (None, None)
            if r is None:
                r = 0
            images_by_row.setdefault(r, []).append(im.get("ref"))

        if not rowmap and not images_by_row:
            continue

        title_row = ADAPTER["expects"]["title_row"]
        doc_title = rowmap.get(title_row, (None, ""))[1] if title_row in rowmap else ""

        # ---- 이벤트 시퀀스(문서 순서) ----
        events = []
        for row in sorted(rowmap):
            if row == title_row:
                continue
            addr, text = rowmap[row]
            m = _HEADING_RE.match(text)
            if m:
                number = m.group(1)
                events.append({
                    "kind": "heading", "row": row, "addr": addr, "text": text,
                    "number": number, "title": m.group(2).strip(),
                    "level": number.count(".") + 1,
                    "indent": indent_map.get(addr), "bold": addr in bold_set,
                })
            else:
                events.append({
                    "kind": "body", "row": row, "addr": addr, "text": text,
                    "indent": indent_map.get(addr), "bold": addr in bold_set,
                })
        for row in sorted(images_by_row):
            for ref in images_by_row[row]:
                events.append({"kind": "image", "row": row, "ref": ref})
        # 같은 행이면 텍스트 → 이미지 순
        order = {"heading": 0, "body": 0, "image": 1}
        events.sort(key=lambda e: (e["row"], order[e["kind"]]))

        col_letter = ADAPTER["expects"]["text_column"]
        for e in events:
            if e.get("addr"):
                c = _ADDR_RE.match(e["addr"])
                if c:
                    col_letter = c.group(1)
                    break

        stack = []          # [{number,title,level,label,row}]
        buf = []            # 현재 헤딩 아래 누적 본문 줄
        cur = None          # 현재 헤딩(dict) 또는 None
        cur_used = [False]  # 현재 헤딩이 조각을 낸 적 있는가

        def section_path():
            return [n["label"] for n in stack]

        def section_str():
            return ADAPTER["expects"]["section_sep"].join(section_path())

        def make_meta(rows, kind):
            return {
                "doc_title": doc_title,
                "sheet": sheet_name,
                "source_path": doc_path,
                "section_path": section_path(),
                "heading": cur["title"] if cur else None,
                "heading_number": cur["number"] if cur else None,
                "heading_level": cur["level"] if cur else None,
                "rows": list(rows),
                "chunk_kind": kind,
            }

        def flush():
            if not buf:
                return
            rows = [b["row"] for b in buf]
            text = ADAPTER["expects"]["body_join"].join(b["text"] for b in buf)
            frags.append({
                "source_locator": _locator(sheet_name, col_letter, rows),
                "text": text,
                "section": section_str(),
                "meta": make_meta(rows, "body"),
                # 좌표는 어댑터가 지어내지 않는다 — 코어 tagger가 닫힌 목록으로 태깅한다
                "process_group": None,
                "process_ref": None,
            })
            del buf[:]
            cur_used[0] = True

        def emit_heading_only():
            """본문도 하위 헤딩도 없는 잎 헤딩 — 제목만으로 청크."""
            if cur is None or cur_used[0]:
                return
            rows = [cur["row"]]
            frags.append({
                "source_locator": _locator(sheet_name, col_letter, rows),
                "text": cur["title"],
                "section": section_str(),
                "meta": make_meta(rows, "heading_only"),
                "process_group": None,
                "process_ref": None,
            })
            cur_used[0] = True

        for e in events:
            if e["kind"] == "heading":
                flush()
                if cur is not None and e["level"] <= cur["level"]:
                    # 새 헤딩이 자식이 아니다 → 직전 헤딩은 내용 없는 잎
                    emit_heading_only()
                while stack and stack[-1]["level"] >= e["level"]:
                    stack.pop()
                node = {
                    "number": e["number"], "title": e["title"], "level": e["level"],
                    "label": e["text"], "row": e["row"],
                }
                stack.append(node)
                cur = node
                cur_used[0] = False
            elif e["kind"] == "body":
                buf.append(e)
            else:  # image
                flush()
                frags.append({
                    "source_locator": _locator(sheet_name, col_letter, [e["row"]]),
                    "image_ref": e["ref"],
                    "section": section_str(),
                })
                cur_used[0] = True

        flush()
        emit_heading_only()

    return frags
