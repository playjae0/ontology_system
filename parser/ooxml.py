# -*- coding: utf-8 -*-
"""칸 2.1 — **OOXML을 zip + XML로 직접** 읽는 자리 — 엑셀 그림 · Word(docx) (B88 ①②).

**선택 의존을 늘리지 않는다**(요청문 원칙 · 문서 7 §7.6-B-6) — `.xlsx`·`.docx`는 zip 안의
XML이고 표준 라이브러리로 읽힌다. `python-docx`를 들이지 않는다.

**엑셀 그림을 openpyxl에 맡기지 않는 이유**: openpyxl은 그림의 위치만 주고, WMF·EMF는
읽기 전에 버린다(경고 한 줄). 그래서 엑셀 문서의 그림은 이미지 요약(④)에 한 장도 가지
않았다. 여기서는 `시트 → drawing → media`의 관계를 zip에서 직접 따라가 **바이트**를 뜬다.
바이트는 `raw["_images"]`에만 싣는다 — 계약 JSON에 바이트 0(문서 5 §5.2-2 · PPT·PDF와 같다).
"""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
}
_R_ID = f"{{{NS['r']}}}id"
_R_EMBED = f"{{{NS['r']}}}embed"
_W = f"{{{NS['w']}}}"

#: 확장자 → mime. 모델이 받는 형식은 `MODEL_MIMES`뿐이고 나머지는 변환 대상이다.
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".bmp": "image/bmp", ".tif": "image/tiff",
        ".tiff": "image/tiff", ".wmf": "image/x-wmf", ".emf": "image/x-emf",
        ".svg": "image/svg+xml"}
MODEL_MIMES = ("image/png", "image/jpeg")


def _col_letter(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _xml(z, part):
    try:
        return ET.fromstring(z.read(part))
    except (KeyError, ET.ParseError):
        return None


def _rels(z, part):
    """`part`의 관계 — `{rId: (대상 부품 경로, 종류 끝말)}`. 없으면 빈 dict."""
    d, b = posixpath.split(part)
    root = _xml(z, posixpath.join(d, "_rels", b + ".rels"))
    out = {}
    for rel in (root.findall("pr:Relationship", NS) if root is not None else []):
        tgt = rel.get("Target") or ""
        if rel.get("TargetMode") == "External":
            continue
        path = tgt.lstrip("/") if tgt.startswith("/") else posixpath.normpath(
            posixpath.join(d, tgt))
        out[rel.get("Id")] = (path, (rel.get("Type") or "").rsplit("/", 1)[-1])
    return out


def _mime(part):
    return MIME.get(posixpath.splitext(part)[1].lower(), "application/octet-stream")


# ---------------------------------------------------------------- 엑셀 그림 (B88 ①)
def xlsx_images(path):
    """`{시트 이름: [(셀, 바이트, mime), …]}` — 앵커의 **시작 셀** 순(행 → 열).

    그룹 안의 그림도 센다(앵커 하나에 blip 여럿). 읽지 못하는 zip이면 빈 dict다 —
    그림은 판독의 부속이고, 표·산문 판독을 그림 때문에 죽이지 않는다.
    """
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return {}
    with z:
        wb = _xml(z, "xl/workbook.xml")
        if wb is None:
            return {}
        wrels = _rels(z, "xl/workbook.xml")
        out = {}
        for sh in wb.findall("m:sheets/m:sheet", NS):
            part = (wrels.get(sh.get(_R_ID)) or (None,))[0]
            if not part:
                continue
            got = []
            for dpart, kind in _rels(z, part).values():
                if kind != "drawing":
                    continue
                droot = _xml(z, dpart)
                if droot is None:
                    continue
                drels = _rels(z, dpart)
                for anchor in droot:
                    fr = anchor.find("xdr:from", NS)
                    if fr is None:
                        continue
                    try:
                        col = int(fr.findtext("xdr:col", "0", NS))
                        row = int(fr.findtext("xdr:row", "0", NS))
                    except ValueError:
                        continue
                    for blip in anchor.iter(f"{{{NS['a']}}}blip"):
                        media = (drels.get(blip.get(_R_EMBED)) or (None,))[0]
                        if not media:
                            continue
                        try:
                            data = z.read(media)
                        except KeyError:
                            continue
                        got.append((row, col, f"{_col_letter(col)}{row + 1}", data,
                                    _mime(media)))
            got.sort(key=lambda g: (g[0], g[1]))
            if got:
                out[sh.get("name")] = [(c, d, m) for _r, _c, c, d, m in got]
        return out


# ---------------------------------------------------------------- Word (B88 ②)
BODY_OUTLINE = 9          # w:outlineLvl 9 = 본문(제목 아님)


def _style_outlines(z):
    """스타일 id → 개요 수준(0부터) — **상속 체인(basedOn)을 따라간다.**

    스타일 **이름**이 아니라 개요 수준을 본다: 한글 Word의 「제목 1」은 스타일 id가
    로캘마다 다르다(`Heading1` · `1` · `제목1` …) — 이름을 맞추면 로캘마다 틀린다.
    """
    root = _xml(z, "word/styles.xml")
    if root is None:
        return {}
    own, base = {}, {}
    for st in root.findall("w:style", NS):
        sid = st.get(f"{_W}styleId")
        lvl = st.find("w:pPr/w:outlineLvl", NS)
        if lvl is not None:
            own[sid] = int(lvl.get(f"{_W}val", BODY_OUTLINE))
        b = st.find("w:basedOn", NS)
        if b is not None:
            base[sid] = b.get(f"{_W}val")
    out = {}
    for sid in set(own) | set(base):
        seen, cur = set(), sid
        while cur and cur not in own and cur not in seen:
            seen.add(cur)
            cur = base.get(cur)
        if cur in own:
            out[sid] = own[cur]
    return out


def _run_text(el):
    """문단·셀의 글 — `w:t`만(삭제된 글자 `w:delText`·필드 코드 `w:instrText`는 빼고)."""
    return "".join(t.text or "" for t in el.iter(f"{_W}t"))


def _para(p, outlines):
    ppr = p.find("w:pPr", NS)
    lvl = None
    if ppr is not None:
        own = ppr.find("w:outlineLvl", NS)
        if own is not None:
            lvl = int(own.get(f"{_W}val", BODY_OUTLINE))
        else:
            sty = ppr.find("w:pStyle", NS)
            if sty is not None:
                lvl = outlines.get(sty.get(f"{_W}val"))
    runs = [r for r in p.iter(f"{_W}r") if _run_text(r).strip()]
    bold = bool(runs) and all(
        (b := r.find("w:rPr/w:b", NS)) is not None
        and b.get(f"{_W}val", "true") not in ("0", "false") for r in runs)
    return {"text": _run_text(p).strip(),
            "outline": lvl if lvl is not None and lvl < BODY_OUTLINE else None,
            "bold": bold,
            "numbered": ppr is not None and ppr.find("w:numPr", NS) is not None}


def _para_images(p):
    """문단 안 그림의 관계 id — DrawingML(`a:blip`)과 옛 VML(`v:imagedata`)."""
    ids = [b.get(_R_EMBED) for b in p.iter(f"{{{NS['a']}}}blip")]
    ids += [v.get(_R_ID) for v in p.iter(f"{{{NS['v']}}}imagedata")]
    return [i for i in ids if i]


def read_docx(path):
    """`.docx` 판독 — 본문 순서대로 문단 · 표 행 · 그림.

    `{"format": "docx", "path", "paragraphs": [{index, kind, text, outline, bold,
    numbered, image_ref?}], "_images": {ref: (바이트, mime)}}`

    - **개요 수준**(`w:outlineLvl` — 문단 또는 스타일 상속 체인)이 제목의 근거다.
    - **번호 목록**(`w:numPr`)은 목록이지 제목이 아니다 — 표시만 싣는다(어댑터가 판정).
    - **표**는 행마다 `셀 | 셀 | …` 한 줄(`kind: "table_row"`) — 그 절의 본문에 든다.
    - 머리글·바닥글·각주는 **다른 부품**이라 읽지 않는다 · 변경 추적의 삭제 글자
      (`w:del`/`w:delText`)는 본문에 넣지 않는다.
    """
    z = zipfile.ZipFile(path)
    with z:
        doc = _xml(z, "word/document.xml")
        if doc is None:
            raise ValueError(f"docx 본문(word/document.xml)이 없다: {path}")
        outlines = _style_outlines(z)
        rels = _rels(z, "word/document.xml")
        body = doc.find("w:body", NS)
        paras, images = [], {}

        def add(rec):
            rec["index"] = len(paras) + 1
            paras.append(rec)

        def walk(el):
            for ch in el:
                tag = ch.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    rec = _para(ch, outlines)
                    if rec["text"]:
                        add({"kind": "para", **rec})
                    for rid in _para_images(ch):
                        media = (rels.get(rid) or (None,))[0]
                        if not media:
                            continue
                        try:
                            data = z.read(media)
                        except KeyError:
                            continue
                        ref = f"D-IMG{len(images) + 1:03d}"
                        images[ref] = (data, _mime(media))
                        add({"kind": "image", "text": "", "outline": None, "bold": False,
                             "numbered": False, "image_ref": ref, "mime": _mime(media)})
                elif tag == "tbl":
                    for tr in ch.findall("w:tr", NS):
                        cells = [re.sub(r"\s+", " ", _run_text(tc)).strip()
                                 for tc in tr.findall("w:tc", NS)]
                        if any(cells):
                            add({"kind": "table_row", "text": " | ".join(cells),
                                 "outline": None, "bold": False, "numbered": False})
                elif tag in ("sdt", "sdtContent", "customXml", "smartTag"):
                    walk(ch)                   # 내용 컨트롤 안의 문단도 본문이다
        if body is not None:
            walk(body)
    return {"format": "docx", "path": path, "paragraphs": paras, "_images": images}
