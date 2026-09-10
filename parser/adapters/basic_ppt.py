# -*- coding: utf-8 -*-
"""기본 어댑터 (PPT) — **임계 조건화** (B+C 단계형 · 08-19 판정 · 카드 C13 v18).

    임계 이하        → 슬라이드 1장 = 청크 1개                        (원래의 자명함)
    임계 초과 + 다프레임 → ① shape 단위 분할 (결정적)
    임계 초과 + 단일 프레임 → ② struct-map 폴백 (지도 기반 분할)
    지도도 실패      → ③ 통청크 + `hierarchy_unresolved` 큐          (조용한 오파싱 0)

**왜 조건화인가.** "슬라이드 1장 = 청크 1개"는 슬라이드가 한 화면 분량일 때만 자명하다.
텍스트가 임계를 넘으면 그 청크는 근거 단위로 너무 굵어져 수집 상한(8)을 통째로 먹는다.
그렇다고 항상 쪼개면 대부분의 정상 슬라이드에서 문맥이 끊긴다 — 그래서 **임계로 가른다.**

**임계는 config 값이다**(P7 — 측정 후 조정). 코드에 숫자를 박으면 조정이 코드 변경이 된다.

어댑터는 순수 함수 계약(C11)이라 LLM을 부르지 않는다. ②의 지도는 **코어**가 산출해
넘겨준다 — `extract(raw, struct_map_fn=...)`의 훅이 그 자리다.
"""
from __future__ import annotations

ADAPTER = {
    "doc_type": "ppt_basic",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        # 분할 신호 상수 — preflight가 보는 지문(prose는 헤더 행이 없다)
        "split_on": "slide",
        # 임계 (config 값 — 초기값. P7: 측정 후 조정)
        "max_chars": 600,
        "max_shapes": 5,
        "section_format": "슬라이드 {index}",
        "frame_format": "슬라이드 {index}#{frame}",
    },
}

PATH_SLIDE = "slide"        # 임계 이하
PATH_SHAPE = "shape"        # ① shape 분할
PATH_MAP = "struct_map"     # ② 지도
PATH_FLAT = "flat"          # ③ 폴백


def _over(shapes, exp):
    """임계 초과 판정 — 글자 수 **또는** 프레임 수. 둘 중 하나면 초과다."""
    return (sum(len(s) for s in shapes) > exp["max_chars"]
            or len(shapes) > exp["max_shapes"])


_SECTION_LAYOUT = ("section", "구획")
_TOC_TITLE = ("목차", "agenda", "contents")
CONTEXT_CHARS = 1500        # ④ 맥락으로 보내는 슬라이드 텍스트 상한


def _is_section_header(s):
    """구획 헤더인가 — **셋 다 결정적이다**(LLM 판정 아님).

    ①레이아웃 이름에 `Section`/`구획` ②제목만 있고 본문이 비었다.
    (③목차 슬라이드의 항목은 아래 `_toc_items`가 따로 본다.)
    """
    lay = (s.get("layout") or "").lower()
    if any(k in lay for k in _SECTION_LAYOUT):
        return True
    body = [r for r in s.get("shapes", []) if r["kind"] not in ("title", "subtitle")]
    return bool(s.get("title")) and not body


def _is_toc(s):
    t = (s.get("title") or "").lower()
    return any(k in t for k in _TOC_TITLE)


def _sections(slides):
    """슬라이드 index → 그 슬라이드가 속한 구획 이름. **앞에서부터 흐른다.**

    구획 헤더를 만나면 그 뒤 슬라이드들이 그 구획에 속한다. 헤더가 하나도 없으면
    전부 None이고, 그러면 경로는 「덱 제목 › 슬라이드 제목」 두 단이 된다.
    """
    cur, out = None, {}
    for s in slides:
        if s.get("hidden"):
            continue
        # **덱의 표지는 구획이 아니다** — 1번 슬라이드의 제목은 이미 `deck_title`이라
        # 구획으로도 세면 경로가 「덱 › 덱 › 덱」이 된다.
        if s["index"] == 1:
            out[s["index"]] = None
            continue
        if _is_section_header(s):
            cur = s.get("title") or None
            # 헤더 슬라이드 **자신**은 그 구획에 속하지 않는다 — 속한다고 두면
            # 경로가 「구획 › 같은 이름」으로 한 단을 헛돈다.
            out[s["index"]] = None
            continue
        out[s["index"]] = cur
    return out


def _path(deck, section, title):
    """`meta.section_path` — 덱 제목 › 구획 › 슬라이드 제목. **판정 안 되면 두 단.**"""
    parts = []
    for x in (deck, section, title):
        if x and (not parts or parts[-1] != x):     # 연속 중복은 접는다
            parts.append(x)
    return " › ".join(parts)


def _context(s):
    """④에 딸려 보내는 맥락 — 같은 슬라이드의 제목·본문·표·차트 텍스트.

    **그림만 보내면 「무엇의 그림인가」를 모델이 지어낸다**(문서 6 §6.1). 앞뒤
    슬라이드는 넣지 않는다 — 비용 3배에 잡음이고, 사람이 쓰는 맥락은 경로다.
    """
    parts = [r.get("text", "") for r in s.get("shapes", [])
             if r["kind"] != "picture" and r.get("text")]
    return "\n".join(parts)[:CONTEXT_CHARS]


def extract(raw, struct_map_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. 조각마다 `source_locator`.

    `struct_map_fn(doc_key, lines) -> (chunks, smap, reasons)`는 **코어가 주입**한다.
    없으면 ②를 시도하지 않고 ③으로 간다 — 어댑터가 스스로 LLM을 부르지 않는다.

    **표·차트는 각각 별도 청크다**(B53). 표 하나가 3천 자를 넘는 것이 흔하고,
    슬라이드 본문에 섞이면 근거 좌표가 뭉개져 「어느 표의 어느 행인가」를 댈 수
    없다. 그림은 placeholder 조각이고 요약은 코어(tagger)가 채운다.
    """
    exp = ADAPTER["expects"]
    slides = raw.get("slides", [])
    deck = raw.get("deck_title", "")
    sec_of = _sections(slides)
    out = []
    for s in slides:
        if s.get("hidden"):                                 # 숨김은 청크에 없다
            continue
        idx = s["index"]
        recs = s.get("shapes", [])
        loc = exp["section_format"].format(index=idx)
        # **`section`은 제목이다** — 없으면 종전대로 「슬라이드 N」.
        title = s.get("title") or ""
        section = title or loc
        spath = _path(deck, sec_of.get(idx), title)
        base = {"slide": s, "loc": loc, "section": section, "path": spath}

        # ── 표·차트·그림은 본문에서 떼어 각각 낸다 ──────────────────────────
        body, extras = [], []
        for r in recs:
            k = r["kind"]
            if k == "table":
                extras.append(_shape_chunk(base, r, _rows(r)))
            elif k == "chart":
                extras.append(_shape_chunk(
                    base, r, r.get("chart_type") and f"차트 {r['chart_type']}"))
            elif k == "picture":
                extras.append(_image_chunk(base, r, _context(s)))
            elif r.get("text"):
                body.append(r["text"])

        if not body:
            out += extras
            continue
        # 본문을 먼저 내고 표·차트·그림을 뒤에 붙인다 — 사람이 읽는 순서이고,
        # `_over` 판정도 **본문만** 본다(표가 임계를 밀어 올려 본문을 쪼개지 않는다).
        _tail, extras = extras, []

        # ── 본문(텍스트 shape)은 종전 규칙 그대로다 ─────────────────────────
        # **여기 산출은 바이트 동일해야 한다**(완료판정 a-ⓕ) — 표·차트가 없는
        # 슬라이드에서 텍스트·`source_locator`가 옛 판과 한 글자도 달라지지 않는다.
        if not _over(body, exp):                            # 임계 이하 — 자명하다
            out.append(_chunk(loc, section, "\n".join(body), PATH_SLIDE, s, section_path=spath))
            out += _tail
            continue

        if len(body) > 1:                                   # ① shape 단위 분할
            for i, text in enumerate(body, 1):
                floc = exp["frame_format"].format(index=idx, frame=i)
                out.append(_chunk(floc, section, text, PATH_SHAPE, s, section_path=spath))
            out += _tail
            continue

        # 단일 거대 프레임 — shape 분할이 불성립한다
        lines = [(n, ln.strip()) for n, ln in enumerate(body[0].splitlines(), 1)
                 if ln.strip()]
        if struct_map_fn is not None:                       # ② 지도 기반 분할
            chunks, smap, reasons = struct_map_fn(
                f"{loc}", lines,
                lambda a, b: (exp["frame_format"].format(index=idx, frame=f"L{a}")
                              if a == b else
                              exp["frame_format"].format(index=idx, frame=f"L{a}-{b}")))
            if not reasons:
                for c in chunks:
                    out.append(_chunk(c["source_locator"], section, c["text"], PATH_MAP,
                                      s, section_override=c.get("section"),
                                      section_path=spath,
                                      band={k: v for k, v in (c.get("meta") or {}).items()
                                            if k.startswith("split_level")}))
                out += _tail
                continue
            out.append(_chunk(loc, section, "\n".join(body), PATH_FLAT, s,
                              unresolved=reasons, section_path=spath))
            out += _tail
            continue

        out.append(_chunk(loc, section, "\n".join(body), PATH_FLAT, s,   # ③ 폴백
                          unresolved=["구조 지도 패스 미주입 — 분할 근거가 없다"],
                          section_path=spath))
        out += _tail
    return out


def _rows(r):
    return f"표 {r.get('rows', '?')}×{r.get('cols', '?')}"


def _shape_chunk(base, r, note=None):
    """표·차트 청크 — `source_locator`가 **shape까지 내려간다**(문서 6 §6.4-5).

    `S4-TB1`처럼 원본에서 그 상자를 다시 열 수 있는 좌표여야 근거다.
    """
    s = base["slide"]
    meta = {"split_path": PATH_SHAPE, "slide": s["index"],
            "shape_kind": r["kind"], "shape_id": r["id"],
            "section_path": base["path"]}
    if s.get("notes"):
        meta["notes"] = s["notes"]
    if note:
        meta["shape_note"] = note
    return {"source_locator": r["id"], "section": base["section"],
            "text": r.get("text", ""), "meta": meta}


def _image_chunk(base, r, context):
    """그림 = **placeholder 조각**. 요약 LLM 호출은 코어(tagger) 몫이다(§6 규약 3).

    바이트는 여기 없다 — `image_ref`만 싣고, tagger가 리더 raw에서 풀어 ④에 보낸다.
    """
    s = base["slide"]
    meta = {"split_path": PATH_SHAPE, "slide": s["index"],
            "shape_kind": "picture", "shape_id": r["id"],
            "section_path": base["path"]}
    if s.get("notes"):
        meta["notes"] = s["notes"]
    if r.get("mime"):
        meta["image_mime"] = r["mime"]
    return {"source_locator": r["id"], "section": base["section"],
            "image_ref": r["image_ref"], "context": context, "meta": meta}


def _chunk(locator, slide_section, text, split, slide, section_override=None,
           unresolved=None, section_path=None, band=None):
    meta = {"split_path": split, "slide": slide["index"]}
    if band:
        # 지도가 고른 레벨이 목표 구간 밖이다([정정] 46·48) — 인입이 이 표시를
        # 보고 `hierarchy_unresolved`(case=size_out_of_band) 큐를 단다.
        # **판단 재료를 통째로 이어받는다** — 여기서 골라 담으면 재료 하나가
        # 빠졌을 때 큐 화면이 조용히 반쪽이 된다. 산문 경로 둘이 같은 표시를 쓴다.
        meta.update(band)
    if section_path:
        meta["section_path"] = section_path
    if slide.get("notes"):
        meta["notes"] = slide["notes"]
    if unresolved:
        meta["hierarchy_unresolved"] = True
        meta["unresolved_reasons"] = unresolved
    if slide.get("unresolved_reasons"):
        meta.setdefault("unresolved_reasons", []).extend(slide["unresolved_reasons"])
        meta["hierarchy_unresolved"] = True
    return {"source_locator": locator,
            "section": section_override or slide_section,
            "text": text, "meta": meta}
