# -*- coding: utf-8 -*-
"""칸 2.6 — 기본 어댑터 (PPT) — **슬라이드가 추출 단위**(B125 ① · 카드 C13).

    본문이 임계 이하        → 본문 근거 청크 1개(슬라이드 1장)
    본문이 임계 초과        → ② struct-map 지도로 본문 근거 청크를 나눈다(지도 기반 분할)
    지도도 실패            → ③ 통청크 + `hierarchy_unresolved` 큐          (조용한 오파싱 0)

**임계는 글자 수 하나다**(B125 ① — 상자 수 조건 · 상자 단위 분할은 없다: 제목 + 작은 상자 여럿인 슬라이드가 상자마다
주인 없는 청크로 흩어졌다). 값의 자리는 `SLIDE_MAX_CHARS`(사내 손잡이 `ppt_slide_chars`).

**추출 단위와 근거 단위를 가른다** — 표 · 차트 · 그림은 지금처럼 각자 근거 청크(위치 `S#-TB1` · `S#-CH1` · `S#-P1`)이고, 한
슬라이드의 청크는 전부 `meta.extract_unit`(= 「슬라이드 N」)을 진다: 추출은 그 단위마다 한 번 묻는다(본문 · 표 · 차트 · 노트 ·
그림 요약 + 캡처 — `core/build/extract_unit`).

**덱 구조**(B125 ③ — 지점 ⑪ · 코어가 `deck_fn`으로 주입)가 있으면 슬라이드마다 제목 · 구획 · 이어짐 · 다루는 공정 · 언급 공정 ·
개체 없음을 그 결정으로 쓴다(placeholder 제목은 초안 · 이어진 슬라이드는 앞 슬라이드의 경로 · 공정). 없으면 지금 방식.

어댑터는 순수 함수 계약(C11)이라 LLM을 부르지 않는다. ②의 지도와 덱 구조는 **코어**가 산출해 넘겨준다.
"""
from __future__ import annotations

from parser import deck as DK
from parser.normalizer import coord_value

ADAPTER = {
    "doc_type": "ppt_basic",
    "adapter_version": "1.1",
    "payload_kind": "prose",
    "expects": {
        # 분할 신호 상수 — preflight가 보는 지문(prose는 헤더 행이 없다)
        "split_on": "slide",
        "section_format": "슬라이드 {index}",
        "frame_format": "슬라이드 {index}#{frame}",
    },
}

#: 본문 글자 임계(창작 기본값 — 「보통 슬라이드는 통째」 · 사내 손잡이 `ppt_slide_chars` · 사내 실측으로 정한다)
SLIDE_MAX_CHARS = 3000

PATH_SLIDE = "slide"        # 임계 이하
PATH_SHAPE = "shape"        # 표 · 차트 · 그림 근거 청크
PATH_MAP = "struct_map"     # ② 지도
PATH_FLAT = "flat"          # ③ 폴백


def _over(body):
    """임계 초과 판정 — **본문 글자 수 하나**(B125 ①)."""
    return sum(len(s) for s in body) > SLIDE_MAX_CHARS


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


def extract(raw, struct_map_fn=None, deck_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. 조각마다 `source_locator`.

    `struct_map_fn(doc_key, lines) -> (chunks, smap, reasons)` · `deck_fn(slides) -> 결정`은 **코어가 주입**한다.
    없으면 지도는 ③으로, 덱 구조는 지금 방식(placeholder 제목 · 구획 헤더)으로 간다 — 어댑터가 스스로 LLM을 부르지 않는다.

    **표·차트는 각각 별도 근거 청크다**(B53) — 근거 좌표 「어느 표의 어느 행인가」. 그림은 placeholder 조각이고 요약은
    코어(tagger)가 채운다. 한 슬라이드의 청크는 전부 같은 추출 단위다(B125 ①).
    """
    exp = ADAPTER["expects"]
    slides = raw.get("slides", [])
    deck = raw.get("deck_title", "")
    sec_of = _sections(slides)
    dec = (deck_fn(DK.deck_input(raw)) if deck_fn is not None else None) or {}
    out, path_by = [], {}
    for s in slides:
        if s.get("hidden"):                                 # 숨김은 청크에 없다
            continue
        idx = s["index"]
        recs = s.get("shapes", [])
        loc = exp["section_format"].format(index=idx)
        d = dec.get(idx) or {}
        # **`section`은 제목이다** — 덱 구조가 정한 제목(그 슬라이드 글 그대로) · 없으면 placeholder · 그것도 없으면 「슬라이드 N」.
        title = d.get("title") or s.get("title") or ""
        section = title or loc
        spath = (path_by.get(d["path_of"]) if d.get("path_of") is not None else None) \
            or _path(deck, d.get("section") or sec_of.get(idx), title)
        path_by[idx] = spath
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
        mine = _body_chunks(body, loc, section, s, spath, idx, exp, struct_map_fn) + extras
        out += [_unit(c, loc, d) for c in mine]
    return out


def _body_chunks(body, loc, section, s, spath, idx, exp, struct_map_fn):
    """본문 근거 청크 — 임계 이하면 하나 · 넘으면 지도(②) · 지도도 없거나 실패면 통청크(③ + 큐)."""
    if not body:
        return []
    if not _over(body):                                     # 임계 이하 — 자명하다
        return [_chunk(loc, section, "\n".join(body), PATH_SLIDE, s, section_path=spath)]
    lines = [(n, ln.strip()) for n, ln in enumerate("\n".join(body).splitlines(), 1) if ln.strip()]
    if struct_map_fn is not None:                           # ② 지도 기반 분할
        chunks, smap, reasons = struct_map_fn(
            f"{loc}", lines,
            lambda a, b: (exp["frame_format"].format(index=idx, frame=f"L{a}")
                          if a == b else
                          exp["frame_format"].format(index=idx, frame=f"L{a}-{b}")))
        if not reasons:
            return [_chunk(c["source_locator"], section, c["text"], PATH_MAP, s,
                           section_override=c.get("section"), section_path=spath,
                           band={k: v for k, v in (c.get("meta") or {}).items() if k.startswith("split_level")})
                    for c in chunks]
        return [_chunk(loc, section, "\n".join(body), PATH_FLAT, s, unresolved=reasons, section_path=spath)]
    return [_chunk(loc, section, "\n".join(body), PATH_FLAT, s,   # ③ 폴백
                   unresolved=["구조 지도 패스 미주입 — 분할 근거가 없다"], section_path=spath)]


def _unit(c, loc, d):
    """한 슬라이드의 청크 — 추출 단위 · 덱 구조의 공정(목록 — 판정이 섰을 때만) · 언급 공정 · 개체 없음."""
    m = {**(c.get("meta") or {}), "extract_unit": loc}
    if d.get("processes") is not None:
        c = {**c, "process_ref": coord_value(d["processes"])}
        m["deck_coord"] = True                             # 덱 구조가 정한 공정(없음 포함) — 문서 좌표 · 경로 대조는 힌트였다
    if d.get("mentions"):
        m["mentions"] = list(d["mentions"])
    if d.get("no_entities"):
        m["no_entities"] = True
    return {**c, "meta": m}


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
