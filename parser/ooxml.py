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


# ---------------------------------------------------------------- Word (B88 ② · B138)
BODY_OUTLINE = 9          # w:outlineLvl 9 = 본문(제목 아님)
#: 자동 번호의 꼴(`w:numFmt`) — 흔한 것만(B138 ①). 밖의 꼴은 번호 글 없이 「자동 번호 · 수준 n」 표시만(판단 필요)
_HANGUL = "가나다라마바사아자차카타파하"
_CHOSUNG = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"
_ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
          (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
NUM_FORMATS = ("decimal", "decimalZero", "upperLetter", "lowerLetter", "upperRoman", "lowerRoman", "ganada", "chosung",
               "decimalEnclosedCircle", "bullet", "none")
BULLET = "•"


def _roman(n):
    out = ""
    for v, r in _ROMAN:
        while n >= v:
            out, n = out + r, n - v
    return out


def _fmt(kind, n):
    """`n`(1부터)을 그 꼴의 글로 — 모르는 꼴 · 범위 밖은 None."""
    if n < 1 and kind not in ("bullet", "none"):
        return None
    return {"decimal": lambda: str(n), "decimalZero": lambda: f"{n:02d}",
            "upperLetter": lambda: chr(65 + (n - 1) % 26) * ((n - 1) // 26 + 1),
            "lowerLetter": lambda: chr(97 + (n - 1) % 26) * ((n - 1) // 26 + 1),
            "upperRoman": lambda: _roman(n), "lowerRoman": lambda: _roman(n).lower(),
            "ganada": lambda: _HANGUL[(n - 1) % len(_HANGUL)], "chosung": lambda: _CHOSUNG[(n - 1) % len(_CHOSUNG)],
            "decimalEnclosedCircle": lambda: chr(0x2460 + n - 1) if n <= 20 else None,
            "bullet": lambda: BULLET, "none": lambda: ""}.get(kind, lambda: None)()


def _val(el, path, default=None):
    x = el.find(path, NS) if el is not None else None
    return x.get(f"{_W}val", default) if x is not None else default


def _styles(z):
    """스타일 — `{id: {outline, num: (numId|None, ilvl|None), name, base}}` · 기본 문단 스타일 id(B138 ② — 번호 · 이름도)."""
    root = _xml(z, "word/styles.xml")
    out, default = {}, None
    for st in (root.findall("w:style", NS) if root is not None else []):
        if st.get(f"{_W}type") not in (None, "paragraph"):
            continue
        sid = st.get(f"{_W}styleId")
        lvl = _val(st, "w:pPr/w:outlineLvl")
        npr = st.find("w:pPr/w:numPr", NS)
        out[sid] = {"outline": int(lvl) if lvl is not None else None,
                    "num": (_val(npr, "w:numId"), _val(npr, "w:ilvl")) if npr is not None else None,
                    "name": _val(st, "w:name") or sid, "base": _val(st, "w:basedOn")}
        if st.get(f"{_W}default") in ("1", "true"):
            default = sid
    return out, default


def _inherit(styles, sid, key):
    """스타일 상속 체인(basedOn)을 따라 `key`의 첫 값."""
    seen = set()
    while sid and sid in styles and sid not in seen:
        seen.add(sid)
        if styles[sid].get(key) is not None:
            return styles[sid][key]
        sid = styles[sid].get("base")
    return None


def _style_outlines(z):
    """스타일 id → 개요 수준(0부터) — **상속 체인(basedOn)을 따라간다.**

    스타일 **이름**이 아니라 개요 수준을 본다: 한글 Word의 「제목 1」은 스타일 id가
    로캘마다 다르다(`Heading1` · `1` · `제목1` …) — 이름을 맞추면 로캘마다 틀린다.
    """
    styles, _d = _styles(z)
    return {sid: v for sid in styles if (v := _inherit(styles, sid, "outline")) is not None}


class _Numbers:
    """**자동 번호를 보이는 글로**(B138 ①) — 번호 정의(`word/numbering.xml`)의 단마다 글(`lvlText`) · 꼴(`numFmt`) · 시작.

    카운터는 추상 정의(`abstractNum`)마다 · 단마다 — 한 단을 세면 그 아래 단은 다시 시작한다 · 번호 인스턴스(`num`)의 시작 덮어쓰기
    (`lvlOverride/startOverride`)는 그 인스턴스를 처음 쓸 때 그 단을 그 값에서 다시 시작한다 · `isLgl`이면 모든 단을 숫자로."""

    def __init__(self, z):
        root = _xml(z, "word/numbering.xml")
        self.abstract, self.nums, self.count, self.used = {}, {}, {}, set()
        for an in (root.findall("w:abstractNum", NS) if root is not None else []):
            lv = {}
            for el in an.findall("w:lvl", NS):
                il = int(el.get(f"{_W}ilvl", "0"))
                lv[il] = {"fmt": _val(el, "w:numFmt", "decimal"), "text": _val(el, "w:lvlText", ""),
                          "start": int(_val(el, "w:start", "1") or 1), "style": _val(el, "w:pStyle"),
                          "lgl": el.find("w:isLgl", NS) is not None, "suff": _val(el, "w:suff", "tab")}
            self.abstract[an.get(f"{_W}abstractNumId")] = lv
        for n in (root.findall("w:num", NS) if root is not None else []):
            over = {int(o.get(f"{_W}ilvl", "0")): int(_val(o, "w:startOverride"))
                    for o in n.findall("w:lvlOverride", NS) if _val(o, "w:startOverride") is not None}
            self.nums[n.get(f"{_W}numId")] = (_val(n, "w:abstractNumId"), over)

    def level_of(self, num_id, style):
        """스타일에 건 번호에 단이 없으면 그 스타일을 단 스타일로 단 단(없으면 0)."""
        aid = (self.nums.get(num_id) or (None,))[0]
        return next((il for il, d in (self.abstract.get(aid) or {}).items() if style and d["style"] == style), 0)

    def next(self, num_id, ilvl):
        """`(보이는 번호 글 | None, 붙임 글)` — 그 단을 하나 센다 · 풀지 못하면 `(None, None)`(카운터는 그대로)."""
        aid, over = self.nums.get(num_id) or (None, {})
        lv = self.abstract.get(aid)
        if not lv or ilvl not in lv:
            return None, None
        cnt = self.count.setdefault(aid, {})
        if num_id not in self.used:
            self.used.add(num_id)
            for il, st in over.items():
                cnt[il] = st - 1
                for k in [k for k in cnt if k > il]:
                    cnt.pop(k)
        cnt[ilvl] = cnt.get(ilvl, lv[ilvl]["start"] - 1) + 1
        for k in [k for k in cnt if k > ilvl]:
            cnt.pop(k)                                  # 아래 단은 위 단이 바뀌면 다시 시작한다
        out, txt = [], lv[ilvl]["text"] or ""
        i = 0
        while i < len(txt):
            if txt[i] == "%" and i + 1 < len(txt) and txt[i + 1].isdigit():
                k = int(txt[i + 1]) - 1
                d = lv.get(k)
                if d is None:
                    return None, None
                kind = "decimal" if lv[ilvl]["lgl"] and d["fmt"] not in ("bullet", "none") else d["fmt"]
                g = _fmt(kind, cnt.get(k, d["start"]))
                if g is None:
                    return None, None
                out.append(g)
                i += 2
                continue
            out.append(txt[i])
            i += 1
        shown = BULLET if lv[ilvl]["fmt"] == "bullet" else "".join(out).strip()
        return shown, ("" if lv[ilvl]["suff"] == "nothing" else " ")


def _run_text(el):
    """문단·셀의 글 — `w:t`만(삭제된 글자 `w:delText`·필드 코드 `w:instrText`는 빼고)."""
    return "".join(t.text or "" for t in el.iter(f"{_W}t"))


def _in_toc_field(p, stack):
    """**목차 필드**(B138 ③) — 문단의 글이 `TOC` 필드의 결과 안에 있는가 · `stack`은 문단을 넘어 이어지는 필드 상태
    (`fldChar` begin · separate · end · `instrText` — 목차 안의 쪽 번호 필드가 겹쳐 든다) · 단순 필드(`fldSimple`)도 본다."""
    hit = False
    for el in p.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "fldChar":
            kind = el.get(f"{_W}fldCharType")
            if kind == "begin":
                stack.append({"instr": "", "sep": False})
            elif kind == "separate" and stack:
                stack[-1]["sep"] = True
            elif kind == "end" and stack:
                stack.pop()
        elif tag == "instrText" and stack:
            stack[-1]["instr"] += el.text or ""
        elif tag == "fldSimple" and str(el.get(f"{_W}instr") or "").strip().upper().startswith("TOC") and _run_text(el).strip():
            hit = True
        elif tag == "t" and (el.text or "").strip() and any(
                f["sep"] and f["instr"].strip().upper().startswith("TOC") for f in stack):
            hit = True
    return hit


def _para(p, outlines, styles=None, numbers=None, default=None):
    ppr = p.find("w:pPr", NS)
    lvl = None
    sty = _val(ppr, "w:pStyle") or default
    if ppr is not None:
        own = ppr.find("w:outlineLvl", NS)
        if own is not None:
            lvl = int(own.get(f"{_W}val", BODY_OUTLINE))
        elif sty is not None:
            lvl = outlines.get(sty)
    runs = [r for r in p.iter(f"{_W}r") if _run_text(r).strip()]
    bold = bool(runs) and all(
        (b := r.find("w:rPr/w:b", NS)) is not None
        and b.get(f"{_W}val", "true") not in ("0", "false") for r in runs)
    text = _run_text(p).strip()
    rec = {"text": text, "outline": lvl if lvl is not None and lvl < BODY_OUTLINE else None, "bold": bold,
           "numbered": False, "style": (styles or {}).get(sty, {}).get("name") or sty}
    ind = ppr.find("w:ind", NS) if ppr is not None else None
    if ind is not None and int(ind.get(f"{_W}left") or ind.get(f"{_W}start") or 0) > 0:
        rec["indent"] = True                             # 문단 들여쓰기 — 보조 표시(B138 ②)
    npr = ppr.find("w:numPr", NS) if ppr is not None else None
    num_id, ilvl = (_val(npr, "w:numId"), _val(npr, "w:ilvl")) if npr is not None else (None, None)
    snum = _inherit(styles or {}, sty, "num") if sty else None
    if num_id is None and snum:                          # 스타일 상속의 번호(B138 ①)
        num_id, ilvl = snum[0], ilvl if ilvl is not None else snum[1]
    if num_id in (None, "0") or not text:
        return rec
    lv = int(ilvl) if ilvl is not None else (numbers.level_of(num_id, sty) if numbers else 0)
    shown, sep = numbers.next(num_id, lv) if numbers else (None, None)
    rec.update(numbered=True, num_level=lv)
    if shown is None:
        rec["num_unknown"] = True                        # 풀지 못한 정의 · 모르는 꼴 — 「자동 번호 · 수준 n」(판단 필요)
    elif shown:
        rec.update(num=shown, text=f"{shown}{sep}{text}")   # 보이는 대로 — 꼴 서명 · 첫 서수 · 이어짐이 읽는다
    return rec


def _para_images(p):
    """문단 안 그림의 관계 id — DrawingML(`a:blip`)과 옛 VML(`v:imagedata`)."""
    ids = [b.get(_R_EMBED) for b in p.iter(f"{{{NS['a']}}}blip")]
    ids += [v.get(_R_ID) for v in p.iter(f"{{{NS['v']}}}imagedata")]
    return [i for i in ids if i]


def _core_title(z):
    """문서 속성 제목(`docProps/core.xml` `dc:title`) — 없으면 None (B138 ④)."""
    root = _xml(z, "docProps/core.xml")
    if root is None:
        return None
    el = root.find("{http://purl.org/dc/elements/1.1/}title")
    return (el.text or "").strip() or None if el is not None else None


def _toc_sdt(el):
    """목차 내용 컨트롤(`docPartGallery` = Table of Contents)인가."""
    g = el.find("w:sdtPr/w:docPartObj/w:docPartGallery", NS)
    return g is not None and str(g.get(f"{_W}val") or "").lower().startswith("table of contents")


def read_docx(path):
    """`.docx` 판독 — 본문 순서대로 문단 · 표 행 · 그림.

    `{"format": "docx", "path", "title", "toc_field_lines", "paragraphs": [{index, kind, text, outline, bold, numbered,
    num?, num_level?, num_unknown?, style, indent?, image_ref?}], "_images": {ref: (바이트, mime)}}`

    - **개요 수준**(`w:outlineLvl` — 문단 또는 스타일 상속 체인)이 제목의 가장 강한 근거다.
    - **자동 번호**(`w:numPr` — 문단 또는 스타일 상속 · 번호 정의 `numbering.xml`)는 **보이는 번호 글**로 되살려 글 앞에 붙인다
      (`num` · 단 `num_level`) — 풀지 못한 정의 · 모르는 꼴은 글 없이 `num_unknown`(B138 ①). 번호 목록이 제목인지는 어댑터 ·
      문서 구조가 판단한다.
    - **목차 필드**(`TOC` 필드의 결과 · 목차 내용 컨트롤)의 문단은 싣지 않고 센다(`toc_field_lines` — B138 ③).
    - **표**는 행마다 `셀 | 셀 | …` 한 줄(`kind: "table_row"`) — 그 절의 본문에 든다.
    - 머리글·바닥글·각주는 **다른 부품**이라 읽지 않는다 · 변경 추적의 삭제 글자
      (`w:del`/`w:delText`)는 본문에 넣지 않는다.
    """
    z = zipfile.ZipFile(path)
    with z:
        doc = _xml(z, "word/document.xml")
        if doc is None:
            raise ValueError(f"docx 본문(word/document.xml)이 없다: {path}")
        styles, default = _styles(z)
        outlines = {sid: v for sid in styles if (v := _inherit(styles, sid, "outline")) is not None}
        numbers = _Numbers(z)
        rels = _rels(z, "word/document.xml")
        body = doc.find("w:body", NS)
        paras, images, fields, skipped = [], {}, [], [0]

        def add(rec):
            rec["index"] = len(paras) + 1
            paras.append(rec)

        def walk(el, in_toc=False):
            for ch in el:
                tag = ch.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    if _in_toc_field(ch, fields) or in_toc:
                        skipped[0] += 1 if _run_text(ch).strip() else 0
                        continue                       # 목차 필드의 결과 — 목차 재료 · 청크에서 뺀다 (B138 ③)
                    rec = _para(ch, outlines, styles, numbers, default)
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
                elif tag == "sdt":
                    walk(ch, in_toc or _toc_sdt(ch))   # 내용 컨트롤 안의 문단도 본문이다(목차 컨트롤은 거른다)
                elif tag in ("sdtContent", "customXml", "smartTag"):
                    walk(ch, in_toc)
        if body is not None:
            walk(body)
        title = _core_title(z)
    return {"format": "docx", "path": path, "paragraphs": paras, "_images": images,
            **({"title": title} if title else {}), **({"toc_field_lines": skipped[0]} if skipped[0] else {})}
