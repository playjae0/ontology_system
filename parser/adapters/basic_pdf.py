# -*- coding: utf-8 -*-
"""기본 어댑터 (PDF) — **페이지가 청크다** (B53 · 문서 6 §6.4-5).

PPT의 「슬라이드 1장 = 청크 1개」와 같은 자명함이 PDF에는 **쪽 단위**로 있다.
쪽은 사람이 인용하는 단위이고(「12쪽 보세요」), 원본에서 다시 열 수 있는 좌표다.

**임계 조건화를 쓰지 않는다.** PPT의 임계는 「슬라이드가 한 화면이라 자명하다」는
전제가 깨지는 자리를 막는 장치인데, PDF 쪽은 원래 한 화면이 아니고 쪽 안의 구조는
문서마다 다르다 — 여기서 쪼개려면 지도(⑦)가 필요하고 그것은 기본 어댑터의 몫이
아니다. 굵은 쪽은 그대로 두고 **근거 좌표를 쪽으로 정확히** 대는 편을 택한다.

`section`은 **목차(outline)에서** 온다 — 그 쪽을 덮는 가장 깊은 항목의 경로다.
목차가 없으면 「페이지 N」으로 떨어진다(조용히 비우지 않는다).

**스캔본**(텍스트 0자)은 그림 placeholder 하나로 낸다 — 빈 청크를 만들지 않는다.
그 쪽의 유일한 근거는 그림이고, 쪽 렌더가 ④ 맥락으로 함께 간다.

어댑터는 순수 함수 계약(C11)이라 LLM을 부르지 않는다.
"""
from __future__ import annotations

ADAPTER = {
    "doc_type": "pdf_basic",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        # 분할 신호 상수 — preflight가 보는 지문(prose는 헤더 행이 없다)
        "split_on": "page",
        "section_format": "페이지 {index}",
        "frame_format": "P{index}",
    },
}

PATH_PAGE = "page"          # 쪽 = 청크
PATH_IMAGE = "image"        # 그림 placeholder


def _section_of(toc, page_no):
    """그 쪽을 덮는 **가장 깊은** 목차 항목의 경로(` > ` 이음).

    목차 항목은 「이 쪽부터」를 뜻하므로, 쪽 번호가 자기 이하인 항목 중 마지막이
    그 쪽의 자리다. 상위 항목을 함께 이어 경로를 만든다 — 「2. 스태킹」만으로는
    같은 이름이 여러 장에 있을 때 어디인지 갈리지 않는다.
    """
    stack = []
    for item in toc or []:
        if item["page"] > page_no:
            break
        lv = item.get("level") or 1
        stack = stack[:lv - 1]
        stack.append(item["title"])
    return " > ".join(x for x in stack if x)


def extract(raw, struct_map_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. 조각마다 `source_locator`.

    `struct_map_fn`은 받되 쓰지 않는다 — 계약(§6.4-2)의 서명을 맞추기 위한 것이고,
    쪽 안 분할은 이 어댑터의 몫이 아니다(머리말 참조).
    """
    exp = ADAPTER["expects"]
    toc = raw.get("toc") or []
    out = []
    for p in raw.get("pages", []):
        idx = p["index"]
        loc = exp["frame_format"].format(index=idx)
        section = _section_of(toc, idx) or exp["section_format"].format(index=idx)
        text = (p.get("text") or "").strip()
        # 쪽 텍스트가 그 쪽 그림의 맥락이다 — 앞뒤 쪽은 넣지 않는다(§6.4-5).
        context = text[:1500]

        if text:
            out.append({
                "source_locator": loc,
                "section": section,
                "text": text,
                "meta": {"split_path": PATH_PAGE, "page": idx,
                         "shape_kind": "page", "shape_id": loc,
                         "section_path": section},
            })

        for im in p.get("images", []):
            meta = {"split_path": PATH_IMAGE, "page": idx,
                    "shape_kind": "picture", "shape_id": im["id"],
                    "section_path": section}
            if im.get("mime"):
                meta["image_mime"] = im["mime"]
            if not text:
                # **스캔본** — 이 쪽의 유일한 근거가 그림이라는 사실을 데이터로 남긴다.
                meta["page_text_empty"] = True
            out.append({
                "source_locator": im["id"],
                "section": section,
                "image_ref": im["image_ref"],
                "context": context,
                "meta": meta,
            })
    return out
