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
  "deck_title": "덱 제목",
  "slides": [{
      "index":  1,
      "hidden": False,                      # 숨김 슬라이드 — 어댑터가 거른다
      "title":  "노칭 설비 구성",             # 제목 플레이스홀더 (없으면 "")
      "layout": "Title and Content",        # 구획 헤더 판정에 쓴다
      "shapes": [                           # **시각 순서**(top→left) · 닫힌 8종
        {"id": "S1-T1",  "kind": "title",    "text": "…"},
        {"id": "S1-TB1", "kind": "table",    "text": "A | B\n1 | 2", "rows": 5, "cols": 2},
        {"id": "S1-CH1", "kind": "chart",    "text": "[차트: …] …", "chart_type": "LINE"},
        {"id": "S1-P1",  "kind": "picture",  "image_ref": "S1-P1",
                         "mime": "image/png", "bytes_len": 48213},
        {"id": "S1-SA1", "kind": "smartart", "text": "…"},
      ],
      "notes": "",
      "unresolved_reasons": [],
  }],
  "_images": {"S1-P1": (b"…", "image/png")},   # **바이트는 여기만** — 계약 JSON에
                                               # 나가지 않는다(문서 5 §5.2-2)
}

pdf →
{
  "format": "pdf",
  "path": "...",
  "toc":   [{"level": 1, "title": "1. 노칭", "page": 1}, ...],   # 없으면 []
  "pages": [{"index": 1, "text": "쪽 전문", "images": [{…picture 레코드…}]}],
  "_images": {"P1-P1": (b"…", "image/png")},
}
"""
import logging
import os

from .normalizer import _col

_LOG = logging.getLogger("onto.parser.reader")


def read_xlsx(path):
    """**import는 함수 안이다** (문서 7 §7.1 선택 의존의 지연 import 격리).

    최상단 import면 `parser.reader`를 import하는 것만으로 openpyxl이 필요해진다 —
    그러면 패키지 미설치 환경에서 **모델 없는 전체 실행**이 ImportError로 죽어
    "외부 의존 없이 전체가 동작한다"(문서 1 B12)가 **실측으로** 깨진다. 문면상
    "요구하지 않는다"까지만 두면 최상단 import가 위반이 아니게 되는 것이 그 구멍이다.
    같은 파일의 `read_pptx`가 이미 이 형태다.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

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


# ---------------------------------------------------------------- pptx
# **리더가 안에서 쓰는 종류**다 — 계약으로 나가는 이름이 아니다.
# 계약 A `meta.shape_kind`의 닫힌 8종은 `parser/validator.py::SHAPE_KINDS`이고,
# 거기에 `subtitle`은 없다. 부제는 본문에 합쳐져 나가므로 계약에 닿지 않는다.
READER_KINDS = ("title", "subtitle", "text", "table", "chart",
                "picture", "smartart")

# id 접두 — `S8-TB1`처럼 **원본에서 다시 열 수 있는 좌표**를 만든다(문서 6 §6.4-5).
_KIND_TAG = {"title": "T", "subtitle": "ST", "text": "B", "table": "TB",
             "chart": "CH", "picture": "P", "smartart": "SA"}

_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _pos(sh):
    """(top, left) — **시각 순서**로 정렬하기 위한 좌표.

    좌표가 없는 shape(자동 배치)는 맨 뒤로 보낸다. XML 순서는 사람이 본 순서와
    다르다 — 나중에 옮긴 상자가 XML 앞에 남아 있는 일이 흔하고, 그대로 읽으면
    근거의 순서가 화면과 어긋난다.
    """
    top = getattr(sh, "top", None)
    left = getattr(sh, "left", None)
    return (top if top is not None else 1 << 40,
            left if left is not None else 1 << 40)


def _table_text(sh):
    """표 → 행 단위 ` | ` 이음. **병합은 전개하지 않는다** — 원문 위치 그대로.

    전개하면 파서가 「이 값이 이 행에도 해당한다」는 판정을 한 것이 된다. 그것은
    normalizer의 규약이 정할 일이고 포맷 판독의 몫이 아니다(A1 — 파서는 의미를
    판정하지 않는다). 빈 칸은 빈 문자열로 남겨 자리를 지킨다.
    """
    t = sh.table
    rows = []
    for r in t.rows:
        rows.append(" | ".join((c.text or "").strip().replace("\n", " ")
                               for c in r.cells))
    n_cols = len(t.columns._gridCol_lst) if hasattr(t.columns, "_gridCol_lst") else 0
    return "\n".join(rows), len(t.rows), (n_cols or (len(t.rows[0].cells) if t.rows else 0))


def _chart_text(sh):
    """차트 → 제목·축 제목·카테고리·계열 값을 **텍스트 표**로.

    **그림으로 찍어 요약하지 않는다**(문서 6 §6.4-5) — 값이 있는데 요약을 쓰면
    정확도를 버린다. 값은 **있는 그대로** 싣는다(반올림 금지).
    """
    ch = sh.chart
    try:
        ctype = str(ch.chart_type).split()[0]
    except Exception:                                       # noqa: BLE001
        ctype = "?"
    title = ""
    try:
        if ch.has_title:
            title = ch.chart_title.text_frame.text.strip()
    except Exception:                                       # noqa: BLE001
        pass
    axes = []
    for attr, tag in (("category_axis", "X"), ("value_axis", "Y")):
        try:
            ax = getattr(ch, attr)
            if ax.has_title:
                axes.append(f"{tag} {ax.axis_title.text_frame.text.strip()}")
        except Exception:                                   # noqa: BLE001
            continue
    head = f"[차트: {title or '제목 없음'}]"
    meta = " · ".join([f"종류 {ctype}"] + axes)

    cats, series = [], []
    try:
        for plot in ch.plots:
            cats = [str(c) for c in plot.categories]
            break
    except Exception:                                       # noqa: BLE001
        cats = []
    try:
        for s in ch.series:
            series.append((s.name, list(s.values)))
    except Exception:                                       # noqa: BLE001
        series = []

    if not series:
        # 외부 링크 차트는 값이 워크북에 없다 — **없다고 적는다**(빈 채로 두면
        # 「값이 0이다」와 구분되지 않는다).
        return f"{head} {meta} — 값 없음".strip(), ctype

    lines = [f"{head} {meta}".strip()]
    for i, cat in enumerate(cats or range(len(series[0][1]))):
        parts = []
        for name, vals in series:
            v = vals[i] if i < len(vals) else None
            parts.append(f"{name} {'' if v is None else v}".strip())
        lines.append(f"{cat}: " + " · ".join(parts))
    if not cats:
        for name, vals in series:
            lines.append(f"{name}: " + " · ".join("" if v is None else str(v) for v in vals))
    return "\n".join(lines), ctype


def _smartart_text(sh, slide):
    """SmartArt(diagram) 텍스트 — `python-pptx`가 열지 않으므로 파트를 직접 연다.

    graphicFrame의 rel에서 `diagramData` 파트를 찾아 `<a:t>`를 **문서 순서대로**
    잇는다. 실패하면 빈 텍스트로 두고 사유를 남긴다 — 조용히 빠뜨리지 않는다.
    """
    try:
        el = sh._element
        rids = [v for k, v in el.attrib.items() if k.endswith("}dm") or k.endswith("}relId")]
        blip = el.findall(f".//{{http://schemas.openxmlformats.org/drawingml/2006/diagram}}relIds")
        for b in blip:
            rids += [v for k, v in b.attrib.items()]
        part = slide.part
        for rid in rids:
            try:
                target = part.rels[rid].target_part
            except Exception:                               # noqa: BLE001
                continue
            if "diagramData" not in target.partname and "data" not in str(target.partname):
                continue
            from lxml import etree
            root = etree.fromstring(target.blob)
            texts = [t.text for t in root.iter(f"{_A_NS}t") if t.text and t.text.strip()]
            if texts:
                return "\n".join(x.strip() for x in texts), None
        return "", "SmartArt 다이어그램 파트를 찾지 못했다"
    except Exception as e:                                  # noqa: BLE001
        return "", f"SmartArt 판독 실패: {type(e).__name__}"


def _shape_kind(sh):
    """플레이스홀더 타입으로 title/subtitle/text를 가른다."""
    try:
        from pptx.enum.shapes import PP_PLACEHOLDER
        if sh.is_placeholder:
            t = sh.placeholder_format.type
            if t in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                return "title"
            if t == PP_PLACEHOLDER.SUBTITLE:
                return "subtitle"
    except Exception:                                       # noqa: BLE001
        pass
    return "text"


def _walk(shapes, slide, prefix, images, counters, reasons):
    """shape 트리를 **시각 순서**로 훑어 레코드 배열을 만든다. 그룹은 재귀."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    out = []
    for sh in sorted(shapes, key=_pos):
        try:
            stype = sh.shape_type
        except Exception:                                   # noqa: BLE001
            stype = None

        if stype == MSO_SHAPE_TYPE.GROUP:
            counters["G"] = counters.get("G", 0) + 1
            out += _walk(sh.shapes, slide, f"{prefix}-G{counters['G']}",
                         images, counters, reasons)
            continue

        def _id(kind):
            tag = _KIND_TAG[kind]
            counters[tag] = counters.get(tag, 0) + 1
            return f"{prefix}-{tag}{counters[tag]}"

        if getattr(sh, "has_table", False):
            text, nr, nc = _table_text(sh)
            if text.strip():
                out.append({"id": _id("table"), "kind": "table", "text": text,
                            "rows": nr, "cols": nc})
            continue

        if getattr(sh, "has_chart", False):
            text, ctype = _chart_text(sh)
            out.append({"id": _id("chart"), "kind": "chart", "text": text,
                        "chart_type": ctype})
            continue

        if stype == MSO_SHAPE_TYPE.PICTURE or (
                stype == MSO_SHAPE_TYPE.PLACEHOLDER and getattr(sh, "image", None) is not None):
            try:
                img = sh.image
                ref = _id("picture")
                # **바이트는 raw에만 싣는다** — 계약 JSON에는 `image_ref`만 나간다
                # (문서 5 §5.2-2 원본 바이너리 비저장). 요약만 보존된다.
                images[ref] = (img.blob, img.content_type)
                out.append({"id": ref, "kind": "picture", "image_ref": ref,
                            "mime": img.content_type, "bytes_len": len(img.blob)})
            except Exception as e:                          # noqa: BLE001
                reasons.append(f"그림 판독 실패: {type(e).__name__}")
            continue

        if stype == MSO_SHAPE_TYPE.PLACEHOLDER and _is_diagram(sh):
            text, why = _smartart_text(sh, slide)
            out.append({"id": _id("smartart"), "kind": "smartart", "text": text})
            if why:
                reasons.append(why)
            continue

        if _is_diagram(sh):
            text, why = _smartart_text(sh, slide)
            out.append({"id": _id("smartart"), "kind": "smartart", "text": text})
            if why:
                reasons.append(why)
            continue

        if getattr(sh, "has_text_frame", False):
            text = sh.text_frame.text.strip()
            if not text:
                continue
            kind = _shape_kind(sh)
            out.append({"id": _id(kind), "kind": kind, "text": text,
                        "top": getattr(sh, "top", None), "left": getattr(sh, "left", None)})
    return out


def _is_diagram(sh):
    """graphicFrame이 diagram(SmartArt)인지 — 표·차트가 아닌 graphicFrame이다."""
    try:
        if getattr(sh, "has_table", False) or getattr(sh, "has_chart", False):
            return False
        el = sh._element
        return el.tag.endswith("}graphicFrame") and b"diagram" in _et_tostring(el)
    except Exception:                                       # noqa: BLE001
        return False


def _et_tostring(el):
    from lxml import etree
    return etree.tostring(el)


def read_pptx(path):
    """PPTX 판독 — **텍스트 프레임과 노트만이 아니다**(B53).

    표·차트·그림·그룹·SmartArt를 읽고 **시각 순서**(top→left)로 낸다. 표·차트를
    텍스트로 푸는 것은 **형태 변환이지 의미 판정이 아니다** — 무엇이 개체인지는
    여전히 추출(①)이 정한다(A1: 파서는 층 어휘를 모른다).

    그림 **바이트는 `raw["_images"]`에만** 있고 계약 JSON으로 나가지 않는다
    (문서 5 §5.2-2 — 원본 바이너리를 저장하지 않는다). 요약만 보존된다.
    """
    from pptx import Presentation
    prs = Presentation(path)
    slides, images = [], {}
    deck_title = ""
    for i, s in enumerate(prs.slides, start=1):
        reasons = []
        recs = _walk(s.shapes, s, f"S{i}", images, {}, reasons)
        title = next((r["text"] for r in recs if r["kind"] == "title"), "")
        if i == 1 and title:
            deck_title = title
        notes = ""
        if s.has_notes_slide and s.notes_slide.notes_text_frame is not None:
            notes = s.notes_slide.notes_text_frame.text.strip()
        try:
            layout = s.slide_layout.name or ""
        except Exception:                                   # noqa: BLE001
            layout = ""
        slides.append({
            "index": i,
            # **숨김 슬라이드는 데이터로 남기고 어댑터가 거른다** — 리더에서 빼면
            # 「없었다」와 「감췄다」가 구분되지 않는다.
            "hidden": s._element.get("show") == "0",
            "title": title, "layout": layout,
            "shapes": recs, "notes": notes,
            "unresolved_reasons": reasons,
        })
    return {"format": "pptx", "path": path, "deck_title": deck_title,
            "slides": slides, "_images": images}


def read_pdf(path):
    """PDF 판독 — PyMuPDF. **페이지가 조각의 단위다**(문서 6 §6.4-5 · B53).

    PPTX와 달리 변환이 없다 — 쪽 렌더가 원본 그대로라 ④ 맥락이 항상 붙는다.
    그림 **바이트는 `_images`에만** 있고 계약 JSON으로 나가지 않는다.

    목차(outline)가 있으면 함께 낸다 — 어댑터가 `section`을 거기서 만든다.
    없으면 「페이지 N」으로 떨어진다(조용히 비우지 않는다).
    """
    import fitz                                             # PyMuPDF — 지연 import

    doc = fitz.open(path)
    pages, images = [], {}
    try:
        toc = [{"level": lv, "title": (t or "").strip(), "page": pg}
               for lv, t, pg in (doc.get_toc() or [])]
        for i, page in enumerate(doc, start=1):
            imgs = []
            for n, info in enumerate(page.get_images(full=True), start=1):
                ref = f"P{i}-P{n}"
                try:
                    ext = doc.extract_image(info[0])
                except Exception:                           # noqa: BLE001
                    continue
                blob = ext.get("image")
                if not blob:
                    continue
                mime = f"image/{ext.get('ext') or 'png'}"
                images[ref] = (blob, mime)
                imgs.append({"id": ref, "kind": "picture", "image_ref": ref,
                             "mime": mime, "bytes_len": len(blob)})
            pages.append({"index": i, "text": page.get_text("text") or "",
                          "images": imgs})
    finally:
        doc.close()
    return {"format": "pdf", "path": path, "toc": toc,
            "pages": pages, "_images": images}


ENCODINGS = ("utf-8-sig", "cp949", "utf-8")



DELIMS = (",", "\t", ";", "|")


def _delimiter(raw, path):
    """구분자 판정 — **`csv.Sniffer`만 믿지 않는다.** 돌려주는 것은 `(구분자, 근거)`.

    Sniffer는 작은 표에서 실제로 실패한다(실측: 4행 탭 파일에서
    `Could not determine delimiter`). 그때 쉼표로 떨어지면 **탭 파일이 조용히 한 열로
    뭉개지고**, 어댑터는 헤더를 못 찾는데 원인은 화면 어디에도 없다.

    순서: ①`.tsv` 확장자는 탭이다(자명하다) ②Sniffer ③빈도 — **모든 표본 줄에서
    같은 횟수로 1회 이상** 나오는 후보 중 가장 많은 것(표의 열 구분자는 행마다
    같은 수로 나온다) ④쉼표.
    """
    if path.lower().endswith(".tsv"):
        return "\t", "확장자"
    sample = raw[:4096]
    try:
        return _csv_mod().Sniffer().sniff(sample, delimiters="".join(DELIMS)).delimiter, "Sniffer"
    except Exception:
        pass
    lines = [ln for ln in sample.splitlines() if ln.strip()][:10]
    best = None
    for d in DELIMS:
        counts = [ln.count(d) for ln in lines]
        # **모든 줄에 1회 이상** 나와야 후보다 — 값 안에 우연히 섞인 문자를 거른다.
        # 행마다 개수가 같기를 요구하지는 않는다: 열이 덜 찬 짧은 행이 흔하고,
        # 그것까지 요구하면 정상 파일이 후보에서 떨어져 쉼표로 잘못 떨어진다.
        if lines and all(c > 0 for c in counts):
            tot = sum(counts)
            if best is None or tot > best[1]:
                best = (d, tot)
    if best:
        return best[0], "빈도"
    return ",", "기본값"


def _csv_mod():
    import csv
    return csv


def read_csv(path):
    """CSV/TSV → **xlsx와 같은 구조**로 낸다 (어댑터가 포맷을 몰라도 되게).

    **`format`은 `"csv"`로 낸다** — `"xlsx"`로 위장하지 않는다: 어댑터가 포맷별
    분기를 할 수 있어야 하고, 거짓말은 나중에 드러난다. 구조만 같게 해서 xlsx
    어댑터 코드가 거의 그대로 돈다.

    `merged`·`indent`·`bold`·`images`는 **빈 값**이다 — CSV에 그 개념이 없다.
    **키는 둔다**: 어댑터가 참조해도 죽지 않아야 한다.

    **`csv` 표준 모듈에 맡긴다** — 따옴표 안의 쉼표·줄바꿈을 직접 split으로
    다루면 한 셀이 여러 셀로 갈린다.
    """
    import csv as _csv                      # 표준 라이브러리 — 외부 의존 0

    raw, enc, tried = None, None, []
    for e in ENCODINGS:
        tried.append(e)
        try:
            with open(path, encoding=e, newline="") as f:
                raw = f.read()
            enc = e
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if raw is None:
        # **시도한 인코딩을 나열한다** — "못 읽는다"만으로는 다음 수가 안 나온다.
        raise ValueError(f"CSV 인코딩을 판별하지 못했다: {path} — 시도: "
                         f"{', '.join(tried)}. 파일을 UTF-8로 다시 저장하거나 "
                         f"reader.ENCODINGS에 사내 인코딩을 더한다")

    delim, how = _delimiter(raw, path)
    # **추정 결과를 로그로 남긴다** — 탭·세미콜론 파일이 조용히 한 열로 읽히면
    # 어댑터가 헤더를 못 찾고, 그때 원인이 화면 어디에도 없다.
    _LOG.info("CSV %s — 인코딩 %s · 구분자 %r (%s)",
              os.path.basename(path), enc, delim, how)

    rows = list(_csv.reader(raw.splitlines(), delimiter=delim))
    cells, max_col = {}, 0
    for r, row in enumerate(rows, start=1):
        max_col = max(max_col, len(row))     # **최장 행 기준** — 짧은 행은 빈 셀
        for c, v in enumerate(row):
            v = v.strip() if isinstance(v, str) else v
            if v == "" or v is None:
                continue                     # xlsx와 같게 — 값 있는 셀만
            cells[f"{_col(c + 1)}{r}"] = v
    return {"format": "csv", "path": path,
            "sheets": [{"name": os.path.splitext(os.path.basename(path))[0],
                        "max_row": len(rows), "max_col": max_col,
                        "cells": cells,
                        "merged": [], "indent": {}, "bold": [], "images": []}],
            "encoding": enc, "delimiter": delim}


# **리더가 여는 확장자의 정본은 여기다.** 호출부(`cli/ingest.py`)가 제 목록을 들면
# 리더에 포맷을 더해도 투입이 「지원하지 않는 포맷」으로 막는다 — 실측: `.pdf`를
# 더한 회차에 정확히 그렇게 됐다(B53).
SUPPORTED = (".xlsx", ".xlsm", ".pptx", ".pdf", ".csv", ".tsv")
# 헤더 지문이 없는 포맷 — doc_type 지정이 필수다(§5 지문 스캔 대상 아님).
PROSE_EXT = (".pptx", ".pdf")


def read(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        return read_xlsx(path)
    if path.lower().endswith(".pptx"):
        return read_pptx(path)
    if path.lower().endswith(".pdf"):
        return read_pdf(path)
    if path.lower().endswith((".csv", ".tsv")):
        return read_csv(path)
    raise ValueError(f"지원하지 않는 포맷: {path} — "
                     f"받는 것은 {' · '.join(SUPPORTED)} 다")


# 관찰 범위 — **다단 헤더 문서에서 12줄은 얕다**(B34): 헤더 3행 + 데이터 9행이면
# 병합 블록·값 변형이 2~3회 반복해 나타나는 것을 못 본다(§6.4 관찰 범위 규칙).
# 기본값이 여러 호출부에 흩어져 있었다 — 여기 하나로 모은다.
OBSERVE_ROWS = 20


def head(raw, n=OBSERVE_ROWS):
    """등록 세션에 공급하는 관찰 재료 — head N행 (M5 관찰 범위 규칙)

    **분기는 포맷 이름이 아니라 구조로 한다.** 구판은 `format != "xlsx"`면 슬라이드로
    단정했고, 그래서 `sheets`를 가진 csv가 들어오자 `KeyError: 'slides'`로 죽었다 —
    csv가 xlsx와 같은 구조를 내는 이유가 바로 «어댑터가 포맷을 몰라도 되게»인데,
    이 함수만 이름으로 갈라 그 취지를 깨고 있었다.
    """
    if "sheets" not in raw:
        return {**raw, "slides": raw.get("slides", [])[:n]}
    out = []
    for sh in raw["sheets"]:
        cells = {a: v for a, v in sh["cells"].items()
                 if int("".join(ch for ch in a if ch.isdigit())) <= n}
        # **`max_row`도 함께 줄인다.** 안 줄이면 어댑터가 원래 행 수까지 훑고,
        # 잘린 구간의 빈 셀이 «결측»으로 잡혀 **자르지 않았으면 없었을 C14 실패**가
        # 난다(실측: 병합이 절단면을 걸치면 그 행만 부분적으로 채워진다).
        # 「앞 N행」은 셀만이 아니라 **시트의 크기**까지의 말이다.
        out.append({**sh, "cells": cells,
                    "max_row": min(int(sh.get("max_row") or 0), n),
                    "indent": {a: v for a, v in sh["indent"].items()
                               if int("".join(ch for ch in a if ch.isdigit())) <= n}})
    return {**raw, "sheets": out}
