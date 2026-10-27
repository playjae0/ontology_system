# -*- coding: utf-8 -*-
"""칸 2.4 — **덱 구조 훅**(B125 ③) — PPT 덱 한 벌의 입력을 만들고, 주입된 판단(`deck_fn` — 코어 ⑪ 태그 `deck`)을 보존 ·
사람의 고침과 합쳐 **슬라이드마다의 결정**으로 돌려준다. 파서는 LLM을 부르지 않는다(문서 구조 훅과 같은 결).

    deck_input(raw)                 슬라이드마다 상자 글(시각 순서 · placeholder 제목 표시) · 노트 앞부분 · 표 · 차트 머리
    hook(ask, doc_id, kept=…)        보존(같은 입력 · 같은 판이면 LLM 0) → 고침(`@덱` 프레임) → decide
    decide(answer, slides)          이어진 슬라이드는 앞 슬라이드의 구획 · 다루는 것 · 공정을 잇는다(낸 것이 있으면 낸 것)

결정은 `{번호: {title, section, continues, subject, processes(문서 표기 · None = 판정 없음), no_entities}}` · 개요는 `tally["개요"]`.
덱 판단은 층 · 골격 · 문서 좌표를 모른다(B151 ①) — 공정 표기를 골격에 거는 것은 좌표 태깅(`tagger.tag` — 표와 같은 길)이다.

    block(tally, chunks)            **봉투의 덱 블록**(B143 ②) — `deck.overview` + `deck.slides[]` · 슬라이드 단위 판단의 정본
    mismatch(env)                   덱 블록 ↔ 청크 칸(추출이 쓰는 투영)의 어긋남 — 있으면 파싱 결함
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


def labels_hash(slides):
    """덱 입력의 지문 — 슬라이드 재료만(문서 좌표는 덱 판단의 입력이 아니다 — B151 ①)."""
    return hashlib.sha256(json.dumps({"slides": slides}, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()[:16]


#: 사람이 고칠 수 있는 칸(`@덱` 프레임) — 옛 기록의 `mentions`(언급 공정)는 읽지 않는다(B151 ④ — 셈만 화면에)
FIX_FIELDS = ("title", "processes", "continues", "subject", "no_entities")


def _with_fixes(ans, fixes):
    """사람의 고침이 이긴다 — 슬라이드마다 고친 칸만 덮는다 · 0행 = 덱 개요 · `(답, 고친 칸 수, 읽지 않은 옛 언급 고침 수)`."""
    if not fixes:
        return ans, 0, 0
    sl = {n: dict(d) for n, d in (ans.get("slides") or {}).items()}
    ov, n_fix, old = ans.get("overview"), 0, 0
    for k, fx in fixes.items():
        k = int(k)
        if k == 0:
            if fx.get("overview"):
                ov, n_fix = fx["overview"], n_fix + 1
            continue
        d = sl.setdefault(k, {})
        old += "mentions" in fx
        for f in FIX_FIELDS:
            if f in fx:
                d[f] = fx[f]
                d.setdefault("by", []).append(f)
                n_fix += 1
    return {**ans, "slides": sl, "overview": ov}, n_fix, old


def decide(ans, slides):
    """슬라이드마다의 결정 — 이어진 슬라이드는 앞 슬라이드의 구획 · 다루는 것 · 공정을 잇는다(그 슬라이드가 낸 것이 있으면 낸 것)."""
    out = {}
    for s in slides:
        n = s["slide"]
        d = dict((ans.get("slides") or {}).get(n) or {})
        prev = out.get(d.get("continues")) if d.get("continues") is not None else None
        if prev:
            d.setdefault("section", prev.get("section"))
            if not d.get("subject"):
                d["subject"] = prev.get("subject")
            if not d.get("processes"):                    # 비었거나 판정 없음 — 이어진 슬라이드는 앞의 공정
                d["processes"] = prev.get("processes")
            d["path_of"] = prev.get("path_of") or d["continues"]
        out[n] = d
    return out


def summary(dec, slides, dropped=None):
    """끝 줄 · 구조 표의 재료 — 수(제목 초안과 다름 · 이어짐 · 공정 하나 · 둘 이상 · 없음 · 버림)와 표 행 · 문서 좌표 밖 공정은
    그래프 단계의 좌표 대조(`coord_mismatch`)가 슬라이드마다 말한다(B151 ④ — 덱 판단 입력이 아니다)."""
    rows, n = [], {"슬라이드": len(slides), "제목다름": 0, "이어짐": 0, "공정하나": 0, "공정둘이상": 0, "공정없음": 0,
                   "버림": sum((dropped or {}).values()), "개체없음": 0}
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
        if d.get("no_entities"):
            n["개체없음"] += 1
        rows.append({"번호": i, "슬라이드": s["slide"], "제목": title or "", "초안": draft or "",
                     "이어짐": d.get("continues"), "공정": ps, "다루는것": d.get("subject"),
                     "개체없음": bool(d.get("no_entities")), "by": d.get("by") or []})
    return n, rows


def hook(ask, doc_id, *, kept=None, made=None, tally=None, fixes=None):
    """덱 구조 훅 `fn(slides) -> 결정 또는 None` — 보존분(같은 입력 · 같은 판)이면 LLM 0 · 고침은 보존분 위에 덮는다."""
    key = ask.key() if callable(getattr(ask, "key", None)) else None

    def same(old):
        # 옛 보존분의 `mode` 칸(산문 구조 방식 — 덱과 무관 · B132 전에는 덱 열쇠가 구조 열쇠를 빌려 섞여 있었다)은 견주지 않는다
        return isinstance(old, dict) and isinstance(key, dict) and \
            {k: v for k, v in old.items() if k != "mode"} == {k: v for k, v in key.items() if k != "mode"} or old == key

    def fn(slides):
        h = labels_hash(slides)
        hit = kept or {}
        if hit.get("labels") == h and same(hit.get("key")) and hit.get("answer"):
            ans, reused = hit["answer"], True
            if callable(getattr(ask, "drift", None)):
                ask.drift(ans)                  # 판 그대로 · 문면만 바뀜이면 한 줄 (B135 ③)
        else:
            ans, reused = ask(doc_id, slides), False
            if ans is None:
                return None
            if made is not None and not ans.get("failed"):
                made.update({"labels": h, "key": key, "answer": ans})
        ans = {**ans, "slides": {int(k): v for k, v in (ans.get("slides") or {}).items()}}
        ans, n_fix, n_old = _with_fixes(ans, fixes)
        dec = decide(ans, slides)
        n, rows = summary(dec, slides, ans.get("dropped"))
        if tally is not None:
            tally.update({"수": {**n, "호출": 0 if reused else ans.get("calls", 0), "재사용": int(reused), "고침": n_fix,
                                 **({"옛 언급 고침": n_old} if n_old else {}),
                                 **({"실패": ans["failed"]} if ans.get("failed") else {})},
                          "표": rows, "개요": ans.get("overview"), "버림": ans.get("dropped") or {},
                          "결정": dec})                # 슬라이드마다의 결정 — 봉투 덱 블록의 재료(B143 ②)
        return dec
    return fn


def block(tally, chunks, nodes=None):
    """**봉투의 덱 블록**(B143 ②) — `{"overview", "slides": [슬라이드 …]}` · 슬라이드 단위 판단의 정본이고 청크 칸(`process_ref` —
    태깅 전 표기 · `meta.subject` · `meta.no_entities` · `meta.section_path`)은 추출이 쓰는 투영이다(어긋나면 `mismatch`가 결함으로 잡는다).

    슬라이드마다 `slide`(번호) · `page`(보이는 쪽 — 숨김 슬라이드를 뺀 차례 · 캡처 쪽) · `title_draft`(placeholder 제목) ·
    `title`(판단 제목 — 덱 구조가 낸 것 · 없으면 None) · `section`(구획) · `continues`(이어진 앞 슬라이드) · `subject`(다루는 것 —
    B151 ①) · `processes`(다루는 공정의 **문서 표기** — None = 판정 없음 · [] = 없음 · 골격에 맞았는가는 청크 `process_ref`가 태깅 뒤
    값으로 든다) · `no_entities` · `dropped`(검사에 어긋나 버린 칸) · `fixed`(사람이 고친 칸) · `chunks`(그 슬라이드의 근거 청크 위치 —
    조각 차례 그대로) · `matched`(공정 표기마다 골격 canonical 또는 None — `processes`와 같은 차례 · 태깅이 고쳐 쓴 것은 그 값 · 아니면
    태깅과 같은 색인 · 같은 대조 함수(정확 · 접기) · 새 판정 0 — B151 ④ · 화면 · md가 읽는다). 칸 이름은 가결정이다(사내 결과를 보고
    다시 판단한다)."""
    from parser import tagger
    locs = {}
    for c in chunks or []:
        n = tagger._page_no(c)                       # 조각의 슬라이드 번호 — 쪽 그림 · 캡처가 읽는 손 하나
        if n is not None:
            locs.setdefault(n, []).append(c.get("source_locator"))
    dec = (tally or {}).get("결정") or {}
    by = {c.get("source_locator"): c for c in chunks or []}
    idx = tagger.scoped_index(nodes or [])[0]
    out = []
    for r in (tally or {}).get("표") or []:
        n = r["슬라이드"]
        d = dec.get(n) or dec.get(str(n)) or {}
        out.append({"slide": n, "page": r["번호"], "title_draft": r.get("초안") or None, "title": d.get("title"),
                    "section": d.get("section"), "continues": d.get("continues"), "subject": d.get("subject"),
                    "processes": d.get("processes"), "no_entities": bool(d.get("no_entities")),
                    "dropped": list(d.get("dropped") or []), "fixed": list(d.get("by") or []),
                    "chunks": locs.get(n, []),
                    "matched": _matched(d.get("processes"), [by[x] for x in locs.get(n, []) if x in by], idx)})
    return {"overview": (tally or {}).get("개요"), "slides": out}


def _matched(procs, chunks, idx):
    """공정 표기마다 골격 canonical 또는 None — 태깅이 고쳐 쓴 값(`meta.coord_tags` · `coord_tag_from`) · 아니면 색인(정확 · 접기)."""
    from parser import tagger
    from parser.normalizer import coord_refs
    moved = {}
    for c in chunks:
        m = c.get("meta") or {}
        for tg in m.get("coord_tags") or []:
            moved.setdefault(tg["from"], tg["to"])
        vals = coord_refs(c.get("process_ref"))
        if m.get("coord_tag_from") and len(vals) == 1:
            moved.setdefault(m["coord_tag_from"], vals[0])
    out = []
    for s in procs or []:
        n = idx.get(s) or tagger.fold_hit(s, idx)
        out.append(moved[s] if moved.get(s) not in (None, s) else (n["canonical"] if n else None))
    return out


def surfaces(chunk):
    """청크 공정의 **태깅 전 표기** — 태깅이 canonical로 고쳐 쓴 원소는 원 표기로(`meta.coord_tags` · `coord_tag_from` — B151 ②) ·
    구획 · 문서 좌표에서 온 값(덱이 공정을 내지 않은 조각)은 빈 목록. 덱 블록과 견주는 손 하나."""
    from parser.normalizer import coord_refs
    m = chunk.get("meta") or {}
    if m.get("coord_from_doc") or m.get("coord_from_section"):
        return []
    if m.get("coord_tags"):
        return [t["from"] for t in m["coord_tags"]]
    vals = coord_refs(chunk.get("process_ref"))
    if m.get("coord_tag_from") and len(vals) == 1:
        return [m["coord_tag_from"]]
    return vals


def mismatch(env):
    """덱 블록 ↔ 청크 칸의 어긋남 — 결함 문면 목록(비면 맞음 · 덱 블록이 없으면 대조 0). 공정은 태깅 전 표기로 견준다(`surfaces`)."""
    by = {c.get("source_locator"): c for c in env.get("chunks") or []}
    out = []
    for s in ((env.get("deck") or {}).get("slides")) or []:
        for loc in s.get("chunks") or []:
            c = by.get(loc)
            if c is None:
                out.append(f"덱 블록 슬라이드 {s['slide']}의 근거 '{loc}'가 청크에 없다")
                continue
            m = c.get("meta") or {}
            if surfaces(c) != list(s.get("processes") or []):
                out.append(f"슬라이드 {s['slide']} 공정 {s.get('processes')} ≠ 청크 '{loc}' {c.get('process_ref')!r}")
            if (m.get("subject") or None) != (s.get("subject") or None):
                out.append(f"슬라이드 {s['slide']} 다루는 것 {s.get('subject')!r} ≠ 청크 '{loc}' {m.get('subject')!r}")
            if bool(m.get("no_entities")) != bool(s.get("no_entities")):
                out.append(f"슬라이드 {s['slide']} 개체 없음 {s.get('no_entities')} ≠ 청크 '{loc}'")
    return out
