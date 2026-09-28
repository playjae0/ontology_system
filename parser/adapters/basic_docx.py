# -*- coding: utf-8 -*-
"""칸 2.6 — 기본 어댑터 (Word `.docx`) — **문단이 행이다** (B88 ② · 문서 6 §6.4-5).

`.pptx`는 슬라이드가, `.pdf`는 쪽이 경계를 주고, 스프레드시트는 계층을 읽어야 경계가
나온다. Word는 스프레드시트 쪽이다 — 문단을 행으로 보고 **B87의 분할 엔진**을 그대로
탄다(`parser.struct_rule.frame_chunks` → `struct_map.split` · 레벨 선택 · 글자 상한 · 규칙
선언 훅). 분할 규칙을 새로 만들지 않는다(두 벌 금지).

**제목 판정** — 문단마다 하나를 고른다:

| 신호 | 레벨 | 근거 |
|---|---|---|
| 개요 수준(`w:outlineLvl` — 문단 또는 스타일 상속) | 수준 + 1 | 작성자가 **문서 구조로** 매긴 깊이다 — 스타일 이름이 아니라 수준을 본다(로캘마다 id가 다르다) |
| 번호 패턴 군(B87 ①) | 첫 등장 순서 | **개요 수준이 하나도 없는 문서에서만**(D-169 ③) — 개요로 짠 문서의 손 번호는 목록이다 |
| 굵게(문단 전체) | 1 | 개요·번호가 없는 문서의 마지막 신호 |
| 번호 목록(`w:numPr`) · 표 행 | — | **제목이 아니다** — 목록과 표는 그 절의 본문이다 |

**LLM 0회다**(규칙 선언 훅은 코어가 주입하고, 고정 규칙으로 안 선 문서에서만 부른다).
"""
from __future__ import annotations

from parser import struct_map, struct_rule

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
    paras = {p["index"]: p for p in raw.get("paragraphs") or []}
    has_outline = any(p.get("outline") is not None for p in paras.values())
    cand = [(i, t) for i, t in lines
            if paras[i].get("kind") == "para" and not paras[i].get("numbered")]
    nums = {} if has_outline else struct_map.number_levels(cand)
    rows = []
    for i, _t in lines:
        p = paras[i]
        lv, sig = 0, None
        if p.get("kind") == "para" and not p.get("numbered"):
            if p.get("outline") is not None:
                lv, sig = p["outline"] + 1, SIG_OUTLINE
            elif i in nums:
                lv, sig = nums[i][0], SIG_NUM
            elif not has_outline and p.get("bold") \
                    and len(p.get("text") or "") <= struct_map.HEADING_MAX_CHARS:
                lv, sig = 1, SIG_BOLD
        rows.append({"row": i, "heading": bool(lv), "level": lv, "signal": sig})
    return rows


def rule_frames(raw):
    """고정 규칙으로 안 선 프레임 — 규칙 선언의 대상(B87 ②와 같은 뜻)."""
    lines = _lines(raw)
    return [FRAME] if lines and not struct_rule.fixed_ok(_rows(raw, lines)) else []


def rule_sample(raw):
    paras = {p["index"]: p for p in raw.get("paragraphs") or []}
    return [{"row": i, "text": t[:struct_rule.RULE_SAMPLE_CHARS],
             "bold": bool(paras[i].get("bold")), "indent": 0, "merge": False}
            for i, t in _lines(raw)[:struct_rule.RULE_SAMPLE_ROWS]]


def _by_rule(raw, decl):
    paras = {p["index"]: p for p in raw.get("paragraphs") or []}
    lines = _lines(raw)
    marks = {i: {"head": t if paras[i].get("kind") == "para"
                 and not paras[i].get("numbered") else "",
                 "bold": bool(paras[i].get("bold"))} for i, t in lines}
    return lines, struct_rule.apply(lines, marks, decl)


def _locator(a, b):
    base = ADAPTER["expects"]["frame_format"].format(a=a)
    return base if a == b else f"{base}-P{b}"


def extract(raw, struct_map_fn=None, struct_rule_fn=None) -> list[dict]:
    """docx 원시 → 조각. `struct_map_fn`은 받되 부르지 않는다(규칙이 레벨을 정한다)."""
    lines = _lines(raw)
    out = []
    if lines:
        out = struct_rule.frame_chunks(
            FRAME, lines, _rows(raw, lines), _locator, ADAPTER["expects"]["section_sep"],
            {}, rule_fn=struct_rule_fn, sample_fn=lambda: rule_sample(raw),
            by_rule=lambda decl: _by_rule(raw, decl),
            flat_reason="계층 신호 0건 — 본문을 통째로 실었다")
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
