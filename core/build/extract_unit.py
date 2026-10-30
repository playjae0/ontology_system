# -*- coding: utf-8 -*-
"""칸 3.3 — **추출 단위**(B125 ①②) — 한 호출에 묶는 근거 청크들과, 답을 근거 청크로 나누는 손 · 슬라이드 캡처.

어댑터가 조각에 `meta.extract_unit`을 단다(PPT 슬라이드 · PDF 쪽 — 같은 값 = 한 호출). 없으면 청크 하나가 단위다(지금과 같다 ·
포맷 전부 한 함수). 한 단위의 호출 입력은 첫 본문 청크 + 묶음 머리를 단 나머지(`[표 S3-TB1]` · `[차트 …]` · `[그림 요약 …]`) +
노트(`[노트]` — 한 번) + 캡처(그 슬라이드 · 쪽의 렌더 — 있을 때만)다. 답의 개체는 **그 표기 · 값 글자가 든 근거 청크**로 가고
(없으면 본문 청크) 관계 · 관련 링크는 본문 청크에 남는다(엣지 끝점은 문서 버퍼가 잇는다).
캡처는 문서마다 한 번 뜬다 — 손잡이 `keep_page_captures`가 켜져 있으면 ④작업 단의 보관분(원본에서 다시 만들 수 있는 쪽 JPEG)을 쓰고
아니면 원본(`source_path`)에서 떠서 이 실행 안에서만 쓴다(`core/state/captures` — B156 ⑤ · 원본 바이너리 저장 0).
"""
from __future__ import annotations

from core.state import captures as _CAP, log
from core.state.ids import norm

_LOG = log.get(__name__)

#: 이 실행의 캡처 — `{doc_id: ({쪽 번호: 바이트}, 사유 또는 None)}`(문서마다 한 번 — 판독과 같은 판 · 자리는 `core/state/captures` — B156 ⑤)
_PAGES = _CAP._PAGES


def unit_key(c):
    return (c.get("meta") or {}).get("extract_unit")


def group(rows):
    """`[(kind, cid, c)]` → 부를 단위 `[[(cid, c), …]]` — 순서 그대로 · 같은 단위는 한 묶음(부를 것만)."""
    out, at = [], {}
    for kind, cid, c in rows:
        if kind != "call":
            continue
        k = unit_key(c)
        if k is None:
            out.append([(cid, c)])
        elif k in at:
            out[at[k]].append((cid, c))
        else:
            at[k] = len(out)
            out.append([(cid, c)])
    return out


def _is_image(c):
    return bool(c.get("image_ref")) or (c.get("meta") or {}).get("shape_kind") == "picture"


def _tag(c):
    k, loc = (c.get("meta") or {}).get("shape_kind"), c.get("source_locator")
    if _is_image(c):
        return f"[판독 그림 {loc}]" if c.get("_reading_fig") else f"[그림 요약 {loc}]"     # 판독이 있는 쪽은 판독 그림 칸(B170)
    return {"table": f"[표 {loc}]", "chart": f"[차트 {loc}]"}.get(k)


def text_of(c):
    """근거 청크의 원문 — 본문 + 노트(그 청크가 진 `meta.notes`) · 그림 요약 청크는 요약 글(원문이 아니다 — 값은 받지 않는다)."""
    notes = (c.get("meta") or {}).get("notes")
    return "\n".join(x for x in (c.get("text") or "", notes or "") if x)


def merged(unit):
    """한 호출의 청크 — `(합친 청크, 본문 청크 id)` · 본문 청크 = 묶음 머리가 없는 첫 청크(없으면 첫 청크)."""
    bid, body = next(((cid, c) for cid, c in unit if _tag(c) is None), unit[0])
    parts, notes = [body.get("text") or ""], None
    for cid, c in unit:
        notes = notes or (c.get("meta") or {}).get("notes")
        if cid != bid:
            parts.append(f"{_tag(c) or '[' + str(c.get('source_locator')) + ']'}\n{c.get('text') or ''}")
    if notes:
        parts.append(f"[노트]\n{notes}")
    return {**body, "text": "\n\n".join(p for p in parts if p)}, bid


def sent(unit, pages):
    """그 단위가 **실제로 보내는** 입력 — `(판독을 실은 단위, [(id, 청크, 캡처)], 합친 id 또는 None)` · 청크 하나 · 캡처 없음이면 그
    청크 · 그 밖은 합친 청크 + 캡처 · 판독이 있는 쪽은 판독을 실은 뒤(B170) — 호출 · 다시 쓸 단위 · 씨앗의 열쇠가 이 한 손을 쓴다."""
    from core.build import extract_reading as ER
    img = (pages or {}).get(page_of(unit))
    unit, rd = ER.apply(unit)                      # 판독이 있는 쪽 — 그림 칸 · [판독] 묶음(없으면 그대로)
    put = (lambda c: {**c, "text": f"{c.get('text') or ''}\n\n{rd}"}) if rd else (lambda c: c)
    if len(unit) == 1 and img is None:
        return unit, [(cid, put(c), None) for cid, c in unit], None
    chunk, bid = merged(unit)
    return unit, [(bid, put(chunk), img)], bid


def _source(e, unit, bid):
    """개체의 출처 청크 — 값 글자가 든 원문 청크 → 표기 글자가 든 청크(원문 먼저 · 그림 요약 다음) → 본문 청크."""
    from core.build.values import verbatim
    order = [x for x in unit if not _is_image(x[1])] + [x for x in unit if _is_image(x[1])]
    v = e.get("value")
    if v:
        for cid, c in order:
            if verbatim(v, text_of(c)):
                return cid
    s = norm(e.get("surface") or "")
    for cid, c in order:
        if s and s in norm(text_of(c)):
            return cid
    return bid


def split(entry, unit, bid):
    """한 호출의 답 → 근거 청크마다의 항목(체크포인트는 지금처럼 청크마다) · 실패면 단위의 청크 전부 실패."""
    out = {cid: {"chunk_id": cid, "entities": [], "relations": [], "attach": []} for cid, _c in unit}
    if entry.get("failed"):
        return [{**out[cid], "failed": entry["failed"]} for cid, _c in unit]
    for e in entry.get("entities") or []:
        out[_source(e, unit, bid)]["entities"].append(e)
    out[bid].update(relations=entry.get("relations") or [], attach=entry.get("attach") or [],
                    **({"about": entry["about"]} if entry.get("about") else {}))
    if entry.get("capture"):
        out[bid]["capture"] = entry["capture"]
    return [out[cid] for cid, _c in unit]


def capture(env):
    """그 문서의 캡처 `({쪽 번호: 바이트}, 사유 또는 None)` — 파싱이 켰을 때만(`env["capture"]`) · 문서마다 한 번 · 보관분(손잡이
    `keep_page_captures`)이 있으면 그것 · 없으면 원본에서 뜬다(`core/state/captures.pages` — 판독과 같은 손 · B156 ⑤) · 보이는 쪽 수와
    렌더 수가 다르면 붙이지 않는다(틀린 쪽을 보내느니 없는 편이 낫다)."""
    want = (env.get("capture") or {}).get("pages")
    if not want:
        return {}, None
    return _CAP.pages(env.get("doc_id"), env.get("source_path"), want)


def page_of(unit):
    """단위의 쪽 번호(첫 청크의 `meta.page_no`) — 없으면 None."""
    return next(((c.get("meta") or {}).get("page_no") for _cid, c in unit if (c.get("meta") or {}).get("page_no")), None)
