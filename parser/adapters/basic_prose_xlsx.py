# -*- coding: utf-8 -*-
"""칸 2.6 — 기본 어댑터 (xlsx/csv 산문) — **줄 목록 + 계층 신호**가 전부다 (B58 ③ · 문서 6 §6.4-5).

`.pptx`는 슬라이드가, `.pdf`는 쪽이 경계를 준다. 스프레드시트에는 그런 경계가 없어
**계층을 읽어야** 자를 자리가 나온다. 읽을 재료는 리더가 이미 전부 준다
(`parser/reader.py` — `indent`·`bold`·`merged` + 셀 문자열의 번호 패턴).

**doc_type마다 만들지 않는다**([개정] B58-2) — 어댑터가 분할하지 않는 이상 prose
어댑터에 남는 일은 **포맷별 줄 목록 만들기**뿐이고, 그것은 doc_type이 아니라 포맷이
정한다. 등재는 `basic_ppt`·`basic_pdf`와 같은 **위임 래퍼**다(B47 · D-111).

**LLM 0회다.** 계층 판정도 레벨 선택도 결정적 연산이고, 지도 패스(⑦)를 부르지
않는다 — 부르면 인입마다 비용이 조용히 붙는다([개정] B58-1). 자르는 일은
`parser.struct_map`의 공용 함수가 한다: 규약 10과 같은 결이다 — **재구현하지 않는다.**
분할 규칙이 두 벌이면 지도 경로와 어댑터 경로의 청크가 갈린다.

**대가**: preflight 양식 표류 감지를 포기한다. 구조 가변 prose는 「판본마다 구조가
다른 것이 기본값」이라 표류라는 개념이 성립하지 않는다(§6.4-5).
"""
from __future__ import annotations

import re

from parser import struct_map, struct_rule, toc

ADAPTER = {
    "doc_type": "prose_xlsx_basic",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        # 분할 신호 상수 — preflight가 보는 지문(prose는 헤더 행이 없다).
        # **레벨은 여기 없다**([정정] 46) — 인입마다 규칙이 계산한다. 상수로 박으면
        # 같은 doc_type의 판본마다 다른 목차 세밀도를 구조적으로 못 따라간다.
        "split_on": "heading",
        "heading_pattern": r"^(\d+(?:\.\d+)*)[.)]?\s+",
        "heading_signals": ["번호", "굵게", "들여쓰기", "가로병합"],
        "section_sep": " > ",
        "frame_format": "{sheet}!R{a}",
    },
}

PATH_HEADING = "heading"        # 계층 분할 — 정상 경로
PATH_FLAT = "flat"              # 헤딩 0건 — 시트 통째 (조용한 오파싱을 만들지 않는다)
PATH_IMAGE = "image"            # 시트 그림 — ④ 이미지 요약 placeholder (B88 ①)
CONTEXT_CHARS = 1500            # 그림에 딸려 보내는 맥락 — 같은 청크 본문 앞부분 (PDF 쪽 맥락과 같은 폭)

_CELL = re.compile(r"^([A-Z]+)(\d+)$")

# **가로 병합만 구획 제목의 신호다.** 세로 병합(`A4:A31`)은 표의 상동 셀이지
# 제목이 아니다 — 둘을 섞으면 관리계획서의 공정구분 열이 통째로 헤딩이 된다.
MIN_MERGE_COLS = 2


def _addr(a):
    m = _CELL.match(a)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def _content_column(sheet):
    """본문 열 — **글자가 가장 많이 든 열**. 동점은 앞 열(결정적).

    산문 스프레드시트는 한 열에 글이 흐른다. 열을 `A`로 박지 않는 이유는 표지·번호
    열이 앞에 붙은 판본이 흔하기 때문이고, 「가장 긴 열」이 아니라 「가장 많이 든
    열」인 이유는 한 셀에 통째로 붙은 열이 뽑히면 줄 목록이 한 줄이 되기 때문이다.
    """
    tally = {}
    for a, v in (sheet.get("cells") or {}).items():
        col, _row = _addr(a)
        if col and str(v).strip():
            tally[col] = tally.get(col, 0) + 1
    if not tally:
        return None
    return min(sorted(tally), key=lambda c: -tally[c])


def _wide_merges(sheet):
    """가로로 2열 이상 걸친 병합의 **시작 행 집합** — 구획 제목의 신호."""
    out = set()
    for rng in sheet.get("merged") or []:
        try:
            lo, hi = rng.split(":")
        except ValueError:
            continue
        c1, r1 = _addr(lo)
        c2, _r2 = _addr(hi)
        if c1 and c2 and r1 and len(c2) * 26 + ord(c2[-1]) - (len(c1) * 26 + ord(c1[-1])) \
                >= MIN_MERGE_COLS - 1:
            out.add(r1)
    return out


# 헤딩 신호의 이름 — 화면·기록이 같은 말을 쓴다 (B68 ①)
SIG_NUM = "번호"
MAP_SOURCE = "adapter:basic_prose_xlsx"


def _col_index(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


#: 행 안의 칸 이음 — 문서 본문(Word)의 표 행과 같은 글자(B132 ① — 단계마다 다른 열에 쓴 시트도 제목이 줄에 든다)
CELL_SEP = " | "


def _row_lines(sheet):
    """**줄 = 행 전체**(B132 ① — 판정 0) — `(줄 [(행, 글)], 재료 {행: {col, ci, spaces, indent, bold, merged, size, fill, color}})`.

    글은 그 행에서 글이 있는 칸을 열 순서로 이은 것(`CELL_SEP`) · 한 열에만 글이 있는 시트는 지금과 같은 글이다(줄 · 청크 바이트 그대로) ·
    시작 열 = 글이 처음 나오는 열 · 앞 공백 수는 `strip` 전에 센다(탭 4 · 전각 공백 2) · 셀 서식 들여쓰기 · 굵게 · 글자 크기 · 채우기 ·
    글자색은 시작 칸의 것(보조 표시 — 단 신호로 쓰지 않는다)."""
    cells = sheet.get("cells") or {}
    bold = set(sheet.get("bold") or [])
    indent = sheet.get("indent") or {}
    size = sheet.get("size") or {}
    fill = sheet.get("fill") or {}
    color = sheet.get("color") or {}
    wide = _wide_merges(sheet)
    by_row = {}
    for a, v in cells.items():
        c, r = _addr(a)
        if c and str(v).strip():
            by_row.setdefault(r, []).append((_col_index(c), c, str(v)))
    lines, mats = [], {}
    for r in sorted(by_row):
        got = sorted(by_row[r])
        _ci, col, raw = got[0]
        lead = raw[:len(raw) - len(raw.lstrip())]
        a = f"{col}{r}"
        lines.append((r, CELL_SEP.join(t.strip() for _i, _c, t in got)))
        mats[r] = {"col": col, "ci": got[0][0], "spaces": sum(4 if ch == "\t" else 2 if ch == "\u3000" else 1 for ch in lead),
                   "indent": int(indent.get(a, 0) or 0), "bold": a in bold, "merged": r in wide,
                   **({"size": size[a]} if a in size else {}), **({"fill": fill[a]} if a in fill else {}),
                   **({"color": color[a]} if a in color else {})}
    return lines, mats


def _rows_of(sheet):
    """`(줄 목록, 헤딩 판정 rows, 재료)` — 제목 판정은 **꼴 서명의 목차 하나**다(B132 ② — `parser/toc.number_levels` · 코드 사다리).

    서식(굵게 · 병합 · 글자 크기 · 색)은 사내 시트에서 정형화되어 있지 않아 **단 신호로 쓰지 않는다**(이름표의 보조 표시로만 —
    문서 구조가 본다). 짧은 번호 줄만 제목 후보다(`struct_map.HEADING_MAX_CHARS` — 넘는 번호 줄은 목록 항목)."""
    lines, mats = _row_lines(sheet)
    nums = toc.number_levels(lines)
    rows = []
    for r, _text in lines:
        lv, sg = nums.get(r, (0, None))
        # **무엇으로 정했는지를 남긴다**(B68 ①) — 구판은 결과(level)만 남기고 신호를 버려서, 사람이 「무엇을 기준으로
        # 잘랐나」를 화면 어디에서도 볼 수 없었다(사내 실측 여덟째).
        rows.append({"row": r, "heading": bool(lv), "level": lv, "signal": f"{SIG_NUM}({sg})" if lv else None})
    return lines, rows, mats


def split_basis(rows):
    """`분할_기준` 문면 — 헤딩을 **어느 신호로** 잡았나를 신호별 수로.

    합이 헤딩 수와 같다(성질) — 신호 없이 헤딩이 된 행은 없다.
    """
    cnt = {}
    for r in rows:
        if r.get("heading") and r.get("signal"):
            cnt[r["signal"]] = cnt.get(r["signal"], 0) + 1
    # 순서: 서명마다 처음 나온 순 (B132 ② — 서식은 단 신호가 아니다)
    keys = [k for k in cnt if k.startswith(SIG_NUM)]
    inner = " · ".join(f"{k} {cnt[k]}" for k in keys if cnt.get(k))
    return f"어댑터 신호: {inner or '없음'}"


def extract(raw, struct_map_fn=None, structure_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. **시트가 프레임이다.**

    `struct_map_fn`은 받되 **부르지 않는다** — 계약(§6.4-2)의 서명을 맞추기 위한
    것이고, 이 계열은 규칙이 레벨을 정하므로 지도 패스가 필요 없다([개정] B58-1).

    `structure_fn(frame, labels)`(B119 ① — 코어가 주입하는 **문서 구조** 훅 · ⑪ 호출 태그 `structure`)은 시트마다
    **무조건** 부른다 — 고정 규칙의 판정은 초안으로 이름표에 실리고, 돌아온 구조(제목 줄의 단 · 역할 · 대상)를
    **데이터로** 적용한다. 없거나 None이면(mock 힌트 없음) 고정 규칙 그대로다.
    """
    sheets = raw.get("sheets") or []
    prep = [_prep(sh) for sh in sheets]
    if structure_fn is not None and callable(getattr(structure_fn, "prepare", None)):
        structure_fn.prepare({p["name"]: p["labs"] for p in prep if p})   # 문서 사다리 — 시트보다 먼저 한 번 (B132 ③)
    out = []
    for sh, p in zip(sheets, prep):
        mine = _sheet_chunks(sh, structure_fn, p)
        out += mine + _image_pieces(sh, mine)
    return out


def _prep(sh):
    """시트 하나의 줄 · 판정 · 재료 · 이름표(한 번만 만든다) — 글이 없으면 None."""
    name = sh.get("name") or "Sheet1"
    col = _content_column(sh)
    if not col:
        return None
    lines, rows, mats = _rows_of(sh)
    if not lines:
        return None
    return {"name": name, "col": col, "lines": lines, "rows": rows, "mats": mats,
            "labs": struct_rule.labels(name, lines, rows, _marks(mats), True, mats)}


_ROWS = re.compile(r"!R(\d+)(?:-R(\d+))?$")


def _image_pieces(sheet, chunks):
    """시트 그림 = **placeholder 조각**(B88 ①) — 요약은 코어(tagger)가 ④로 한다(규약 3).

    `section`은 그림이 앉은 행이 속한 청크의 것이고 `context`는 그 청크 본문 앞부분이다 —
    PPT의 「같은 슬라이드 텍스트」와 같은 뜻. 그림 앞 청크가 없으면 첫 청크를 쓴다.
    `ref` 시트의 그림을 빼는 것은 파이프라인이다(시트 역할은 어댑터가 모른다).
    """
    name = sheet.get("name") or "Sheet1"
    spans = []
    for c in chunks:
        m = _ROWS.search(c.get("source_locator") or "")
        if m:
            spans.append((int(m.group(1)), int(m.group(2) or m.group(1)), c))
    out = []
    for im in sheet.get("images") or []:
        row = int("".join(ch for ch in str(im.get("cell") or "1") if ch.isdigit()) or 1)
        host = next((c for a, b, c in spans if a <= row <= b), None) \
            or next((c for a, _b, c in reversed(spans) if a <= row), None) \
            or (spans[0][2] if spans else None)
        section = (host or {}).get("section") or name
        meta = {"split_path": PATH_IMAGE, "frame": name, "shape_kind": "picture",
                "shape_id": im["ref"], "cell": im.get("cell"), "section_path": section, "sheet": name}
        if im.get("mime"):
            meta["image_mime"] = im["mime"]
        out.append({"source_locator": f"{name}!{im.get('cell')}#{im['ref']}",
                    "section": section, "image_ref": im["ref"],
                    "context": ((host or {}).get("text") or "")[:CONTEXT_CHARS],
                    "meta": meta})
    return out


def _marks(mats):
    """줄 표시(이름표의 보조 재료 · B119 ① · B132 ① · B137 ③) — `{행: [굵게 · 병합 · 크기n · 채움 · 글자색]}`(시작 칸 기준 · 시트에서 흔한
    크기 · 글자색은 싣지 않는다 · 서명 · 들여쓰기 깊이 · 빈 행 뒤는 공용 함수가 단다)."""
    sizes = [m["size"] for m in mats.values() if "size" in m]
    common = max(set(sizes), key=sizes.count) if sizes else None
    colors = [m.get("color") for m in mats.values()]
    usual = max(set(colors), key=colors.count) if colors else None
    out = {}
    for r, m in mats.items():
        mk = [k for k, on in (("굵게", m.get("bold")), ("병합", m.get("merged")),
                              (f"크기{m.get('size')}", m.get("size") not in (None, common)), ("채움", m.get("fill")),
                              ("글자색", m.get("color") != usual)) if on]
        if mk:
            out[r] = mk
    return out


def _sheet_chunks(sh, structure_fn=None, prep=None):
    """시트 하나의 글 조각 — 순서는 `struct_rule.frame_chunks` 한 벌이다(엑셀·Word 같이)."""
    exp = ADAPTER["expects"]
    p = prep if prep is not None else _prep(sh)
    if not p:
        return []
    name, col, lines, rows, mats = p["name"], p["col"], p["lines"], p["rows"], p["mats"]

    def locator(a, b, _n=name):
        base = exp["frame_format"].format(sheet=_n, a=a)
        return base if a == b else f"{base}-R{b}"

    return struct_rule.frame_chunks(
        # 시트명은 늘 싣는다(B102 ① — 맥락 줄의 시트 칸 · 제목이 있으면 구획 경로에 시트가 없다)
        name, lines, rows, locator, exp["section_sep"], {"content_column": col, "sheet": name},
        structure_fn=structure_fn, marks_fn=lambda: _marks(mats), mats=mats, labs=p["labs"],
        flat_reason="계층 신호 0건 — 시트를 통째로 실었다")


def level_report(raw):
    """레벨 선택의 **판단 재료** — 검수 화면과 큐가 읽는다. `extract`와 같은 계산이다.

    프레임(시트)마다 `{프레임, 분할_레벨, 분할_레벨_사유, 레벨_분포, 구간밖}`.
    `struct_map.adapter_level_picks`와 **같은 형태**를 낸다 — 화면이 둘로 갈리지 않게.
    """
    out = []
    for sh in raw.get("sheets") or []:
        col = _content_column(sh)
        if not col:
            continue
        lines, rows, _m = _rows_of(sh)
        if not lines or not any(r["heading"] for r in rows):
            continue
        stats = struct_map.level_stats({"rows": rows}, lines)
        pick, why, oor = struct_map.choose_level(stats)
        out.append({"프레임": sh.get("name"), "분할_레벨": pick,
                    "분할_레벨_사유": why, "레벨_분포": stats,
                    "분할_레벨_구간밖": oor,
                    # **한 필드 이름, 두 경로**(B68 ①) — 지도 경로의 pick도 같은
                    # 키를 낸다. 이름이 갈리면 화면이 둘로 갈린다.
                    "분할_기준": split_basis(rows),
                    "지도_출처": MAP_SOURCE})
    return out
