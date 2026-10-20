# -*- coding: utf-8 -*-
"""칸 2.4 — **덱 구조 훅**(B125 ③) — PPT 덱 한 벌의 입력을 만들고, 주입된 판단(`deck_fn` — 코어 ⑪ 태그 `deck`)을 보존 ·
사람의 고침과 합쳐 **슬라이드마다의 결정**으로 돌려준다. 파서는 LLM을 부르지 않는다(문서 구조 훅과 같은 결).

    deck_input(raw)                 슬라이드마다 상자 글(시각 순서 · placeholder 제목 표시) · 노트 앞부분 · 표 · 차트 머리
    hook(ask, doc_id, kept=…)        보존(같은 입력 · 같은 판이면 LLM 0) → 고침(`@덱` 프레임) → decide
    decide(answer, slides)          이어진 슬라이드는 앞 슬라이드의 구획 · 공정을 잇는다(낸 것이 있으면 낸 것)

결정은 `{번호: {title, section, continues, processes(None = 판정 없음), mentions, no_entities}}` · 개요는 `tally["개요"]`.
"""
from __future__ import annotations

import hashlib
import json

#: 입력 상한(창작 기본값) — 상자 글 · 노트 앞부분 · 표 · 차트 머리
BOX_CHARS = 300
NOTE_CHARS = 300
HEAD_CHARS = 160
FRAME = "@덱"


def deck_input(raw):
    """reader 원시 추출물 → 덱 입력(숨김 슬라이드 제외 · 그림은 뺀다 — 캡처는 추출이 본다)."""
    out = []
    for s in raw.get("slides") or []:
        if s.get("hidden"):
            continue
        boxes = []
        for r in s.get("shapes") or []:
            t = (r.get("text") or "").strip()
            if r["kind"] == "picture" or not t:
                continue
            if r["kind"] in ("table", "chart"):
                boxes.append({"kind": r["kind"], "text": t.splitlines()[0][:HEAD_CHARS]})
            else:
                boxes.append({"kind": r["kind"], "text": t[:BOX_CHARS],
                              **({"placeholder_title": True} if r["kind"] == "title" else {})})
        out.append({"slide": s["index"], "layout": s.get("layout") or "", "boxes": boxes,
                    **({"notes": s["notes"][:NOTE_CHARS]} if s.get("notes") else {})})
    return out


def labels_hash(slides, doc_coord=None):
    return hashlib.sha256(json.dumps({"slides": slides, "coord": doc_coord}, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _with_fixes(ans, fixes):
    """사람의 고침이 이긴다 — 슬라이드마다 고친 칸만 덮는다 · 0행 = 덱 개요."""
    if not fixes:
        return ans, 0
    sl = {n: dict(d) for n, d in (ans.get("slides") or {}).items()}
    ov, n_fix = ans.get("overview"), 0
    for k, fx in fixes.items():
        k = int(k)
        if k == 0:
            if fx.get("overview"):
                ov, n_fix = fx["overview"], n_fix + 1
            continue
        d = sl.setdefault(k, {})
        for f in ("title", "processes", "continues", "mentions", "no_entities"):
            if f in fx:
                d[f] = fx[f]
                d.setdefault("by", []).append(f)
                n_fix += 1
    return {**ans, "slides": sl, "overview": ov}, n_fix


def decide(ans, slides):
    """슬라이드마다의 결정 — 이어진 슬라이드는 앞 슬라이드의 구획 · 공정을 잇는다(그 슬라이드가 낸 것이 있으면 낸 것)."""
    out = {}
    for s in slides:
        n = s["slide"]
        d = dict((ans.get("slides") or {}).get(n) or {})
        prev = out.get(d.get("continues")) if d.get("continues") is not None else None
        if prev:
            d.setdefault("section", prev.get("section"))
            if not d.get("processes"):                    # 비었거나 판정 없음 — 이어진 슬라이드는 앞의 공정
                d["processes"] = prev.get("processes")
            d["path_of"] = prev.get("path_of") or d["continues"]
        out[n] = d
    return out


def summary(dec, slides, doc_coord=None, dropped=None):
    """끝 줄 · 구조 표의 재료 — 수(제목 초안과 다름 · 이어짐 · 공정 하나 · 둘 이상 · 없음 · 문서 좌표와 다름 · 버림)와 표 행."""
    rows, n = [], {"슬라이드": len(slides), "제목다름": 0, "이어짐": 0, "공정하나": 0, "공정둘이상": 0, "공정없음": 0,
                   "좌표다름": 0, "버림": sum((dropped or {}).values()), "개체없음": 0}
    for i, s in enumerate(slides, start=1):
        d = dec.get(s["slide"]) or {}
        draft = next((b["text"] for b in s["boxes"] if b.get("placeholder_title")), None)
        title = d.get("title") or draft
        if d.get("title") and d["title"] != draft:
            n["제목다름"] += 1
        if d.get("continues") is not None:
            n["이어짐"] += 1
        ps = d.get("processes")
        if ps is not None:
            n["공정하나" if len(ps) == 1 else ("공정둘이상" if len(ps) > 1 else "공정없음")] += 1
            if doc_coord and doc_coord not in ps:
                n["좌표다름"] += 1
        if d.get("no_entities"):
            n["개체없음"] += 1
        rows.append({"번호": i, "슬라이드": s["slide"], "제목": title or "", "초안": draft or "",
                     "이어짐": d.get("continues"), "공정": ps, "언급": d.get("mentions") or [],
                     "개체없음": bool(d.get("no_entities")), "by": d.get("by") or []})
    return n, rows


def hook(ask, doc_id, *, kept=None, made=None, tally=None, fixes=None, doc_coord=None):
    """덱 구조 훅 `fn(slides) -> 결정 또는 None` — 보존분(같은 입력 · 같은 판)이면 LLM 0 · 고침은 보존분 위에 덮는다."""
    key = ask.key() if callable(getattr(ask, "key", None)) else None

    def same(old):
        # 옛 보존분의 `mode` 칸(산문 구조 방식 — 덱과 무관 · B132 전에는 덱 열쇠가 구조 열쇠를 빌려 섞여 있었다)은 견주지 않는다
        return isinstance(old, dict) and isinstance(key, dict) and \
            {k: v for k, v in old.items() if k != "mode"} == {k: v for k, v in key.items() if k != "mode"} or old == key

    def fn(slides):
        h = labels_hash(slides, doc_coord)
        hit = kept or {}
        if hit.get("labels") == h and same(hit.get("key")) and hit.get("answer"):
            ans, reused = hit["answer"], True
        else:
            ans, reused = ask(doc_id, slides, doc_coord=doc_coord), False
            if ans is None:
                return None
            if made is not None and not ans.get("failed"):
                made.update({"labels": h, "key": key, "answer": ans})
        ans = {**ans, "slides": {int(k): v for k, v in (ans.get("slides") or {}).items()}}
        ans, n_fix = _with_fixes(ans, fixes)
        dec = decide(ans, slides)
        n, rows = summary(dec, slides, doc_coord, ans.get("dropped"))
        if tally is not None:
            tally.update({"수": {**n, "호출": 0 if reused else ans.get("calls", 0), "재사용": int(reused), "고침": n_fix,
                                 **({"실패": ans["failed"]} if ans.get("failed") else {})},
                          "표": rows, "개요": ans.get("overview"), "버림": ans.get("dropped") or {}})
        return dec
    return fn
