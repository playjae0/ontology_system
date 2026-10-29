# -*- coding: utf-8 -*-
"""칸 2.4 — **쪽 판독 훅**(B156 ① ② — 메타 · 층 무관) — PPT 슬라이드 · PDF 쪽마다 캡처 · 그림 원본 · 상자 목록 · 덱 판단의 그 장 칸을
주입된 판독(`ask` — 코어 지점 ④ 태그 `reading`)에 보내고, 보존 · 사람의 고침과 합쳐 **봉투의 판독 블록**으로 돌려준다. 파서는 LLM을
부르지 않는다(덱 구조 훅과 같은 결).

    boxes(raw)                       상자 목록 — 쪽마다 상자(id · 종류 · 위치 · 크기 · 쪽 대비 비율 · 글 앞부분) · 봉투 `boxes`
    hook(ask, doc_id, path, raw, …)  쪽마다 1회 · 보존 열쇠(입력 해시 · 지시문 판 · 읽기 지식 해시 · 힌트)가 같으면 LLM 0 ·
                                     덱 판단이 개체 없음으로 정한 장 · 글 · 그림이 둘 다 없는 쪽 · 사람이 지운 장은 건너뜀

**추출 · 그래프는 바꾸지 않는다**(B156 — 메타에 더하기만) — 청크 · 그림 요약 글 · 추출 입력은 판독과 무관하다(판독을 추출에 쓰는 일은
다음 회차). 판독 입력의 상자 목록 · 그림 원본은 `parser/reading_pick`이 고른다(B168 — 표시 · 조각 그룹 · 같은 꼴 · 장식 · 예외 ·
사람의 `자세히` · `빼기` — 봉투 `boxes`는 그대로). 사람의 고침은 `@판독` 프레임(`<쪽> 다시 <힌트>` · `<쪽> 지움` · `<쪽> 자세히 <그림 id>` ·
`<쪽> 빼기 <그림 id>` — 등록 단 고침 기록 · 덱 고침과 같은 파일)이다.
"""
from __future__ import annotations

import hashlib
import json

#: 상자 글 앞부분(판독 입력 · 봉투의 상자 목록 — 창작 기본값 · 덱 입력과 같은 300)
BOX_CHARS = 300
FRAME = "@판독"
AGAIN, DELETE = "다시", "지움"
DETAIL, DROP = "자세히", "빼기"                 # 그림 하나를 원본으로 · 원본 0(B168 ③ — `reading_pick`이 읽는다)
#: 건너뜀 사유
SKIP_NONE, SKIP_EMPTY, SKIP_CAPTURE, SKIP_DELETED = "개체 없음", "빈 쪽", "캡처 없음", "지움"
_GEO = ("left", "top", "width", "height")


def _box(r, w, h):
    g = {k: r.get(k) for k in _GEO}
    ok = all(isinstance(g[k], (int, float)) for k in _GEO) and w and h
    rel = [round(g[k] / d, 4) for k, d in zip(_GEO, (w, h, w, h))] if ok else None
    return {"id": r["id"], "kind": r["kind"], **g, "rel": rel, "text": (r.get("text") or "")[:BOX_CHARS] or None}


def boxes(raw):
    """봉투의 **상자 목록**(B156 ①) `{"unit", "pages": [{page, slide, width, height, boxes: […]}]}` — PPT는 보이는 슬라이드(쪽 = 보이는
    차례 · 숨김 제외 · 단위 EMU) · PDF는 쪽(쪽 글 상자 `P<n>` + 그림 — 리더가 가진 만큼 · 단위 pt) · 쪽이 없는 포맷은 None."""
    if raw.get("slides") is not None:
        w, h = (raw.get("slide_size") or [None, None])[:2]
        vis = [s for s in raw["slides"] if not s.get("hidden")]
        return {"unit": "emu", "pages": [{"page": n, "slide": s["index"], "width": w, "height": h,
                                          "boxes": [_box(r, w, h) for r in s.get("shapes") or []]}
                                         for n, s in enumerate(vis, start=1)]}
    if raw.get("pages") is not None:
        out = []
        for p in raw["pages"]:
            w, h = (p.get("size") or [None, None])[:2]
            t = (p.get("text") or "").strip()
            bx = ([{"id": f"P{p['index']}", "kind": "page", **{k: None for k in _GEO}, "rel": None, "text": t[:BOX_CHARS]}]
                  if t else []) + [_box(im, w, h) for im in p.get("images") or []]
            out.append({"page": p["index"], "slide": None, "width": w, "height": h, "boxes": bx})
        return {"unit": "pt", "pages": out}
    return None


def _full_text(raw, pg):
    """그 쪽 상자 글 전부(그림 속 글자 표시의 대조 글 — 잘리지 않은 글)."""
    if pg["slide"] is not None:
        s = next((x for x in raw.get("slides") or [] if x["index"] == pg["slide"]), {})
        return "\n".join(r.get("text") or "" for r in s.get("shapes") or [])
    p = next((x for x in raw.get("pages") or [] if x["index"] == pg["page"]), {})
    return p.get("text") or ""


def _slot(d, overview):
    """덱 판단의 그 장 칸(PPT — 제목 · 구획 · 다루는 것 · 공정 표기 · 이어짐 · 덱 개요) · PDF는 None."""
    if d is None:
        return None
    return {"title": d.get("title"), "section": d.get("section"), "subject": d.get("subject"),
            "processes": d.get("processes"), "continues": d.get("continues"), "overview": overview}


def _h(b):
    return hashlib.sha256(b).hexdigest()[:16] if b else None


def _key(inp, cap, imgs, base, hint):
    return hashlib.sha256(json.dumps({"input": inp, "capture": _h(cap), "images": [_h(b) for _r, b, _m in imgs],
                                      "hint": hint, **base}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _summary_text(ans):
    return " ".join(s.get("text") or "" for s in (ans or {}).get("summary") or []) or None


def _rows(raw, bx, dec, overview, fixes, live, caps):
    """쪽마다 `{pg, slot, fix, skip, prev_page, text}` — 건너뜀 사유는 부르기 전에 정한다."""
    slide_page = {pg["slide"]: pg["page"] for pg in bx["pages"] if pg["slide"] is not None}
    out = []
    for pg in bx["pages"]:
        d = (dec.get(pg["slide"]) or dec.get(str(pg["slide"]))) if pg["slide"] is not None and dec else None
        fx = fixes.get(pg["page"]) or {}
        if fx.get("action") == DELETE:
            skip = SKIP_DELETED
        elif (d or {}).get("no_entities"):
            skip = SKIP_NONE
        elif not any(b.get("text") for b in pg["boxes"]) and not any(b["kind"] == "picture" for b in pg["boxes"]):
            skip = SKIP_EMPTY
        elif live and not caps.get(pg["page"]):
            skip = SKIP_CAPTURE
        else:
            skip = None
        out.append({"pg": pg, "slot": _slot(d if pg["slide"] is not None and dec else None, overview), "fix": fx,
                    "skip": skip, "prev_page": slide_page.get((d or {}).get("continues")),
                    "text": _full_text(raw, pg)})
    return out


def _input(r, prev):
    pg = r["pg"]
    return {"page": pg["page"], "slide": pg["slide"], "boxes": pg["boxes"], "deck": r["slot"], "previous": prev}


def _images(r, images):
    """그 쪽 그림 원본 `[(상자 id, 바이트, 형식)]` — 모델이 받는 형식(PNG · JPEG) · 고른 것(`image` 「원본」 — B168 ②)만."""
    out = []
    for b in r["pg"]["boxes"]:
        keep = b["kind"] == "picture" and not b.get("image")              # 「캡처로 봄」 표시가 없는 그림
        blob, mime = images.get(b["id"], (None, None)) if keep else (None, None)
        if blob and mime in ("image/png", "image/jpeg"):
            out.append((b["id"], blob, mime))
    return out


def _plan(rows, kept, caps, images, base, bare):
    """부르기 전의 셈(LLM 0) — 재사용은 보존분의 열쇠가 같을 때 · 이어진 장은 앞 장이 다시 불리면 부름으로 센다(부름 ≤ n)."""
    n = {"쪽": len(rows), "부름": 0, "재사용": 0, "건너뜀": 0, "지움": 0, "지식바뀜": 0}
    summ, called = {}, set()
    for r in rows:
        page = r["pg"]["page"]
        if r["skip"]:
            n["지움" if r["skip"] == SKIP_DELETED else "건너뜀"] += 1
            summ[page] = None                               # 건너뛴 앞 장 — 앞 장 요약 없음(실행과 같다)
            continue
        prev = summ.get(r["prev_page"]) if r["prev_page"] else None    # 앞 장은 보존분의 요약으로 어림한다
        hint = r["fix"].get("hint") if r["fix"].get("action") == AGAIN else None
        inp, im = _input(r, prev), _images(r, images)
        k = kept.get(str(page)) or {}
        summ[page] = _summary_text(k.get("answer"))
        if r["prev_page"] not in called and k.get("key") == _key(inp, caps.get(page), im, base, hint) and k.get("answer"):
            n["재사용"] += 1
            continue
        n["부름"] += 1
        called.add(page)
        if k.get("base") and k.get("base") == _key(inp, caps.get(page), im, bare, hint):
            n["지식바뀜"] += 1
    return n


def hook(ask, doc_id, path, raw, deck_tally=None, *, kept=None, made=None, tally=None, fixes=None, capture=False):
    """쪽 판독 — 봉투의 판독 블록(`reading`) 또는 None(판독 함수 없음 · 쪽 없음 · 어느 쪽도 판독이 없다 — mock 힌트 없음은 지금 그대로).

    `ask(doc_id, 입력, capture=, images=, hint=, text=)`가 검사가 끝난 답(또는 None — 판정 없음) · `ask.key()`가 판(지시문 판 · 읽기 지식
    해시) · `ask.pages(doc_id, path, 쪽 수)`가 캡처(`capture`가 참일 때만) · `ask.notice(셈)`이 부르기 전 예고(있으면)."""
    bx = boxes(raw) if ask is not None else None
    if not bx or not bx["pages"]:
        return None
    dec = (deck_tally or {}).get("결정") or {}
    fixes = {int(k): v for k, v in (fixes or {}).items()}
    live = bool(getattr(ask, "live", False))
    caps, cap_why = (ask.pages(doc_id, path, len(bx["pages"])) if capture and callable(getattr(ask, "pages", None))
                     else ({}, None))
    base = dict(ask.key()) if callable(getattr(ask, "key", None)) else {}
    bare = {k: v for k, v in base.items() if k != "knowledge"}
    kept, images = dict(kept or {}), raw.get("_images") or {}
    from parser import reading_pick
    sel, picked = reading_pick.pick(raw, bx, fixes, live)          # 판독 입력의 상자 · 그림 원본(B168 — 봉투 boxes는 그대로)
    rbx = {**bx, "pages": [dict(pg, boxes=sel[pg["page"]]["boxes"]) for pg in bx["pages"]]}
    rows = _rows(raw, rbx, dec, (deck_tally or {}).get("개요"), fixes, live, caps)
    plan = {**_plan(rows, kept, caps, images, base, bare), "그림": picked}
    if callable(getattr(ask, "notice", None)):
        ask.notice({**plan, "읽기지식": bool(base.get("knowledge")), "캡처": len(caps), "캡처사유": cap_why})
    n = {**plan, "부름": 0, "재사용": 0, "버림": 0, "호출": 0, "실패": 0,
         "고침": sum(1 for r in rows if r["fix"].get("action") in (AGAIN, DELETE) or r["fix"].get(DETAIL) or r["fix"].get(DROP))}
    out, summ = [], {}
    for r in rows:
        pg = r["pg"]
        e = {"page": pg["page"], "slide": pg["slide"]}
        if r["skip"]:
            out.append({**e, "skipped": r["skip"], **({"deleted": True, "fixed": DELETE} if r["skip"] == SKIP_DELETED else {})})
            continue
        hint = r["fix"].get("hint") if r["fix"].get("action") == AGAIN else None
        inp, im = _input(r, summ.get(r["prev_page"]) if r["prev_page"] else None), _images(r, images)
        key, k = _key(inp, caps.get(pg["page"]), im, base, hint), kept.get(str(pg["page"])) or {}
        if k.get("key") == key and k.get("answer"):
            ans, reused = k["answer"], True
            if callable(getattr(ask, "drift", None)):
                ask.drift(ans)
        else:
            ans, reused = ask(doc_id, inp, capture=caps.get(pg["page"]), images=im, hint=hint, text=r["text"]), False
            if ans is None:
                out.append({**e, "skipped": "판독 없음"})
                continue
            if made is not None and not ans.get("failed"):
                made[str(pg["page"])] = {"key": key, "base": _key(inp, caps.get(pg["page"]), im, bare, hint), "answer": ans}
        n["재사용" if reused else "부름"] += 1
        n["호출"] += 0 if reused else ans.get("calls", 0)
        n["실패"] += bool(ans.get("failed"))
        n["버림"] += sum((ans.get("dropped") or {}).values())
        summ[pg["page"]] = _summary_text(ans)
        cref = ask.capture_ref(doc_id, pg["page"]) if caps.get(pg["page"]) and callable(getattr(ask, "capture_ref", None)) else None
        out.append({**e, "source": ans.get("source"), "reused": reused, **({"capture": cref} if cref else {}),
                    **({"images": sel[pg["page"]]["images"]} if sel[pg["page"]]["images"] else {}),
                    **{f: ans.get(f) or [] for f in ("figures", "relations", "summary")},
                    "dropped": dict(ans.get("dropped") or {}),
                    **({"failed": ans["failed"]} if ans.get("failed") else {}),
                    **({"hint": hint, "fixed": AGAIN} if hint else {})})
    if not any("source" in x or x.get("deleted") for x in out):
        return None
    if tally is not None:
        tally.update({"수": n, "표": out})
    return {"pages": out, "knowledge": base.get("knowledge"), "prompt_version": base.get("prompt_version"),
            "capture": {"있음": len(caps), **({"사유": cap_why} if cap_why else {})}}
