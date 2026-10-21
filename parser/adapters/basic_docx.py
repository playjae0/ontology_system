# -*- coding: utf-8 -*-
"""칸 2.6 — 기본 어댑터 (Word `.docx`) — **문단이 행이다** (B88 ② · 문서 6 §6.4-5).

`.pptx`는 슬라이드가, `.pdf`는 쪽이 경계를 주고, 스프레드시트는 계층을 읽어야 경계가
나온다. Word는 스프레드시트 쪽이다 — 문단을 행으로 보고 **B87의 분할 엔진**을 그대로
탄다(`parser.struct_rule.frame_chunks` → `struct_map.split` · 레벨 선택 · 글자 상한 · 문서
구조 훅). 분할 규칙을 새로 만들지 않는다(두 벌 금지).

**제목 근거의 순서**(초안 — 문서 구조가 엑셀과 같은 함수로 최종을 정한다 · B138 ⑤):

| 신호 | 레벨 | 근거 |
|---|---|---|
| 개요 수준(`w:outlineLvl` — 문단 또는 스타일 상속) | 수준 + 1 | 작성자가 **문서 구조로** 매긴 깊이다 — 가장 강하다 · 스타일 이름이 아니라 수준을 본다(로캘마다 id가 다르다) |
| 자동 번호(되살린 보이는 번호 · 문단 또는 스타일 상속) · 손 번호 | 목차(이어짐 · 첫 서수) | **개요 수준이 하나도 없는 문서에서만**(D-169 ③) — 번호 목록을 일괄로 본문 처리하지 않는다(사다리 · 첫 서수의 재료 · 목록인지는 판단 필요) · 목록 수준(`ilvl`)은 깊이 재료 |
| 굵게(문단 전체) | 1 | 개요·번호가 없는 문서의 마지막 신호 |
| 문단 스타일 · 들여쓰기(`w:ind`) | — | 보조 표시(서식 비교 · 단 신호가 아니다) |
| 표 행 | — | **제목이 아니다** — 표는 그 절의 본문이다 |

**문서 제목**: 첫 글 문단이 파일 이름 · 문서 속성 제목과 같으면(`parser/ladder.same_name` — 시트 제목과 같은 함수) 표시 「문서 제목」 —
목차 맨 위에 서고 단을 다투지 않는다(B138 ④). 목차 필드의 문단은 리더가 이미 거른다(B138 ③).

**어댑터는 LLM 0회다**(문서 구조 훅은 코어가 주입한다 — B119 ①).
"""
from __future__ import annotations

from pathlib import Path

from parser import ladder as PL
from parser import struct_map, struct_rule, toc

ADAPTER = {
    "doc_type": "prose_docx_basic",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        "split_on": "heading",
        "heading_signals": ["개요 수준", "번호", "굵게"],
        "section_sep": " > ",
        "frame_format": "본문!P{a}",
    },
}

FRAME = "본문"                   # Word는 프레임이 하나다 — 문서 본문
PATH_IMAGE = "image"
CONTEXT_CHARS = 1500
SIG_OUTLINE, SIG_NUM, SIG_BOLD = "개요 수준", "번호", "굵게"
MAP_SOURCE = "adapter:basic_docx"


def _lines(raw):
    """글 줄 — 문단과 표 행(그림 문단은 빠진다 — 그림은 따로 조각이 된다)."""
    return [(p["index"], p["text"]) for p in raw.get("paragraphs") or []
            if p.get("kind") in ("para", "table_row") and p.get("text")]


def _rows(raw, lines):
    """초안 판정 — 개요 수준 → 번호(되살린 자동 번호 · 손 번호 — 개요 없는 문서만) → 굵게(B138 ⑤ — 번호 목록을 일괄로 빼지 않는다)."""
    paras = {p["index"]: p for p in raw.get("paragraphs") or []}
    has_outline = any(p.get("outline") is not None for p in paras.values())
    cand = [(i, t) for i, t in lines if paras[i].get("kind") == "para"]
    nums = {} if has_outline else toc.number_levels(cand)
    rows = []
    for i, _t in lines:
        p = paras[i]
        lv, sig = 0, None
        if p.get("kind") == "para":
            if p.get("outline") is not None:
                lv, sig = p["outline"] + 1, SIG_OUTLINE
            elif i in nums:
                lv, sig = nums[i][0], SIG_NUM
            elif not has_outline and p.get("bold") and not p.get("numbered") \
                    and len(p.get("text") or "") <= struct_map.HEADING_MAX_CHARS:
                lv, sig = 1, SIG_BOLD
        rows.append({"row": i, "heading": bool(lv), "level": lv, "signal": sig})
    return rows


def _locator(a, b):
    base = ADAPTER["expects"]["frame_format"].format(a=a)
    return base if a == b else f"{base}-P{b}"


def _title(raw):
    """첫 글 문단이 문서 제목인가 — 파일 이름 · 문서 속성 제목과 `PL.same_name`(B138 ④ — 시트 제목과 같은 함수) · 그 문단 번호 또는 None."""
    first = next((p for p in raw.get("paragraphs") or [] if p.get("kind") == "para" and p.get("text")), None)
    names = [Path(str(raw.get("path") or "")).stem, raw.get("title")]
    return first["index"] if first and PL.same_name(first["text"], names) else None


def _marks(raw):
    """줄 표시(이름표의 재료 · B119 ① · B138 ①②④) — `{문단: [굵게 · 개요n · 번호 목록 · 자동 번호 · 자동 번호 · 수준 n · 스타일 <이름> ·
    들여씀 · 문서 제목 · 표 행]}` · 문서에서 흔한 문단 스타일은 싣지 않는다(엑셀의 흔한 크기와 같다)."""
    paras = raw.get("paragraphs") or []
    names = [p.get("style") for p in paras if p.get("kind") == "para"]
    usual = max(set(names), key=names.count) if names else None
    title = _title(raw)
    out = {}
    for p in paras:
        mk = [m for m, on in (("굵게", p.get("bold")),
                              (f"개요{(p.get('outline') or 0) + 1}", p.get("outline") is not None),
                              ("번호 목록", p.get("numbered")), ("자동 번호", p.get("num")),
                              (f"{PL.NUM_UNKNOWN} {(p.get('num_level') or 0) + 1}", p.get("num_unknown")),
                              (f"스타일 {p.get('style')}", p.get("style") and p.get("style") != usual),
                              ("들여씀", p.get("indent")), (PL.DOC_TITLE, p["index"] == title),
                              ("표 행", p.get("kind") == "table_row")) if on]
        if mk:
            out[p["index"]] = mk
    return out


def _mats(raw):
    """깊이 재료 — 목록 수준(`ilvl` — 작성자가 매긴 깊이 · 엑셀의 시작 열 · 앞 공백 자리 · B138 ②) · 목록이 아닌 문단은 맨 위 단과 같은 0."""
    return {p["index"]: {"ci": 0, "indent": (p.get("num_level") or 0) if p.get("numbered") else 0, "spaces": 0}
            for p in raw.get("paragraphs") or []}


def extract(raw, struct_map_fn=None, structure_fn=None) -> list[dict]:
    """docx 원시 → 조각. `struct_map_fn`은 받되 부르지 않는다(규칙이 레벨을 정한다) · `structure_fn`은
    문서 구조 훅(B119 ① — 엑셀과 같은 함수 · 이름표에 시트 줄이 없다)."""
    lines = _lines(raw)
    out = []
    if lines:
        rows = _rows(raw, lines)
        labs = struct_rule.labels(FRAME, lines, rows, _marks(raw), False, _mats(raw))
        if structure_fn is not None and callable(getattr(structure_fn, "prepare", None)):
            structure_fn.prepare({FRAME: labs})             # 문서 사다리 — 본문 하나 (B132 ③ · 엑셀과 같은 길)
        out = struct_rule.frame_chunks(
            FRAME, lines, rows, _locator, ADAPTER["expects"]["section_sep"],
            {}, structure_fn=structure_fn, marks_fn=lambda: _marks(raw), sheet=False,
            flat_reason="계층 신호 0건 — 본문을 통째로 실었다", labs=labs)
    return out + _image_pieces(raw, out)


def _image_pieces(raw, chunks):
    """그림 = ④ placeholder — `section`·`context`는 그림 앞의 가장 가까운 청크(같은 절)."""
    spans = []
    for c in chunks:
        loc = c.get("source_locator") or ""
        a = loc.split("!P", 1)[-1].split("-P")[0]
        if a.isdigit():
            spans.append((int(a), c))
    out = []
    for p in raw.get("paragraphs") or []:
        if p.get("kind") != "image":
            continue
        host = next((c for a, c in reversed(spans) if a <= p["index"]), None) \
            or (spans[0][1] if spans else None)
        section = (host or {}).get("section") or FRAME
        meta = {"split_path": PATH_IMAGE, "frame": FRAME, "shape_kind": "picture",
                "shape_id": p["image_ref"], "section_path": section}
        if p.get("mime"):
            meta["image_mime"] = p["mime"]
        out.append({"source_locator": f"{FRAME}!P{p['index']}#{p['image_ref']}",
                    "section": section, "image_ref": p["image_ref"],
                    "context": ((host or {}).get("text") or "")[:CONTEXT_CHARS],
                    "meta": meta})
    return out


def level_report(raw):
    """레벨 선택의 판단 재료 — `basic_prose_xlsx.level_report`와 같은 형태."""
    lines = _lines(raw)
    rows = _rows(raw, lines)
    if not lines or not any(r["heading"] for r in rows):
        return []
    stats = struct_map.level_stats({"rows": rows}, lines)
    pick, why, oor = struct_map.choose_level(stats)
    cnt = {}
    for r in rows:
        if r["heading"]:
            cnt[r["signal"]] = cnt.get(r["signal"], 0) + 1
    return [{"프레임": FRAME, "분할_레벨": pick, "분할_레벨_사유": why,
             "레벨_분포": stats, "분할_레벨_구간밖": oor,
             "분할_기준": "어댑터 신호: " + " · ".join(f"{k} {v}" for k, v in cnt.items()),
             "지도_출처": MAP_SOURCE}]
