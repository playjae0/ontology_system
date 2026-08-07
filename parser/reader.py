# -*- coding: utf-8 -*-
"""파서 공용 코어 — reader (포맷별 원시 추출)

파서_명세 §3: 포맷 의존은 reader에만 격리한다. doc_type 의존은 adapter에만.
reader는 사람이 1회 작성·유지하는 공용 코드이며 LLM 생성 대상이 아니다.

출력 계약 (adapter의 extract(raw)가 받는 것):

xlsx →
{
  "format": "xlsx",
  "path": "...",
  "sheets": [{
      "name":    str,
      "max_row": int, "max_col": int,
      "cells":   {"A1": value, ...},        # 값이 있는 셀만. 병합은 **전개하지 않음**
      "merged":  ["A4:A31", "B4:B5", ...],  # 병합 범위 원본
      "indent":  {"A5": 3, ...},            # 들여쓰기 수준 (0이 아닌 셀만)
      "bold":    ["A1", "A3", ...],         # 굵은 셀
      "images":  [{"cell": "A17", "ref": "img_001"}, ...],
  }]
}

pptx →
{
  "format": "pptx",
  "path": "...",
  "slides": [{"index": 1, "shapes": ["제목", "본문 …"], "notes": ""}]
}
"""
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def read_xlsx(path):
    wb = load_workbook(path, data_only=True)
    sheets = []
    for ws in wb.worksheets:
        cells, indent, bold = {}, {}, []
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                addr = f"{get_column_letter(c.column)}{c.row}"
                cells[addr] = c.value
                ind = getattr(c.alignment, "indent", 0) or 0
                if ind:
                    indent[addr] = int(ind)
                if c.font and c.font.bold:
                    bold.append(addr)
        images = []
        for i, im in enumerate(getattr(ws, "_images", []), start=1):
            anch = getattr(im, "anchor", None)
            try:
                r = anch._from.row + 1
                col = anch._from.col + 1
                cell = f"{get_column_letter(col)}{r}"
            except Exception:
                cell = None
            images.append({"cell": cell, "ref": f"img_{i:03d}"})
        sheets.append({
            "name": ws.title,
            "max_row": ws.max_row, "max_col": ws.max_column,
            "cells": cells,
            "merged": [str(r) for r in ws.merged_cells.ranges],
            "indent": indent,
            "bold": bold,
            "images": images,
        })
    return {"format": "xlsx", "path": path, "sheets": sheets}


def read_pptx(path):
    from pptx import Presentation
    prs = Presentation(path)
    slides = []
    for i, s in enumerate(prs.slides, start=1):
        shapes = [sh.text_frame.text.strip() for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()]
        notes = ""
        if s.has_notes_slide and s.notes_slide.notes_text_frame is not None:
            notes = s.notes_slide.notes_text_frame.text.strip()
        slides.append({"index": i, "shapes": shapes, "notes": notes})
    return {"format": "pptx", "path": path, "slides": slides}


def read(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        return read_xlsx(path)
    if path.lower().endswith(".pptx"):
        return read_pptx(path)
    raise ValueError(f"지원하지 않는 포맷: {path}")


def head(raw, n=12):
    """등록 세션에 공급하는 관찰 재료 — head N행 (M5 관찰 범위 규칙)"""
    if raw["format"] != "xlsx":
        return {**raw, "slides": raw["slides"][:n]}
    out = []
    for sh in raw["sheets"]:
        cells = {a: v for a, v in sh["cells"].items()
                 if int("".join(ch for ch in a if ch.isdigit())) <= n}
        out.append({**sh, "cells": cells,
                    "indent": {a: v for a, v in sh["indent"].items()
                               if int("".join(ch for ch in a if ch.isdigit())) <= n}})
    return {**raw, "sheets": out}
