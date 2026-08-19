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


def extract(raw, struct_map_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. 조각마다 `source_locator`.

    `struct_map_fn(doc_key, lines) -> (chunks, smap, reasons)`는 **코어가 주입**한다.
    없으면 ②를 시도하지 않고 ③으로 간다 — 어댑터가 스스로 LLM을 부르지 않는다.
    """
    exp = ADAPTER["expects"]
    out = []
    for s in raw.get("slides", []):
        idx = s["index"]
        shapes = [x for x in s.get("shapes", []) if x and x.strip()]
        loc = exp["section_format"].format(index=idx)
        if not shapes:
            continue

        if not _over(shapes, exp):                          # 임계 이하 — 자명하다
            out.append(_chunk(loc, loc, "\n".join(shapes), PATH_SLIDE, s))
            continue

        if len(shapes) > 1:                                 # ① shape 단위 분할
            for i, text in enumerate(shapes, 1):
                floc = exp["frame_format"].format(index=idx, frame=i)
                out.append(_chunk(floc, loc, text, PATH_SHAPE, s))
            continue

        # 단일 거대 프레임 — shape 분할이 불성립한다
        lines = [(n, ln.strip()) for n, ln in enumerate(shapes[0].splitlines(), 1)
                 if ln.strip()]
        if struct_map_fn is not None:                       # ② 지도 기반 분할
            chunks, smap, reasons = struct_map_fn(
                f"{loc}", lines,
                lambda a, b: (exp["frame_format"].format(index=idx, frame=f"L{a}")
                              if a == b else
                              exp["frame_format"].format(index=idx, frame=f"L{a}-{b}")))
            if not reasons:
                for c in chunks:
                    out.append(_chunk(c["source_locator"], loc, c["text"], PATH_MAP,
                                      s, section=c.get("section")))
                continue
            out.append(_chunk(loc, loc, "\n".join(shapes), PATH_FLAT, s,
                              unresolved=reasons))
            continue

        out.append(_chunk(loc, loc, "\n".join(shapes), PATH_FLAT, s,   # ③ 폴백
                          unresolved=["구조 지도 패스 미주입 — 분할 근거가 없다"]))
    return out


def _chunk(locator, slide_section, text, path, slide, section=None, unresolved=None):
    meta = {"split_path": path, "slide": slide["index"]}
    if slide.get("notes"):
        meta["notes"] = slide["notes"]
    if unresolved:
        meta["hierarchy_unresolved"] = True
        meta["unresolved_reasons"] = unresolved
    return {"source_locator": locator,
            "section": section or slide_section,
            "text": text, "meta": meta}
