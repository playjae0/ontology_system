# -*- coding: utf-8 -*-
"""칸 2.6 — **프레임 한 벌 · 문서 구조의 데이터** — 엑셀 · Word 산문의 분할 순서와 구조 역할 어휘 (B88 ② · B119 ①).

    문서 구조(⑪ — 주입되면 시트마다 무조건) → 고정 규칙(번호 군 · 가로병합 · 굵게) → 통째 또는 분할

계층 규칙 선언(⑦ 안의 호출 `struct_rule` — B87 ②)은 B121 ③에서 지웠다 — 고정 규칙으로 안 선 시트는 문서 구조가 세운다.
파일 이름은 그대로 둔다(구조 역할 어휘 · 이름표 · 훅을 읽는 곳이 많다).

**파서는 core를 import하지 않는다** — 모델을 부르는 함수는 주입으로 오고(`structure`),
여기는 그 함수를 감싸 **재사용·검사·셈**만 한다.
"""
from __future__ import annotations

import hashlib
import json

from . import struct_map, toc

def frame_paths(pieces):
    """시트마다 「고정 규칙 / 통째」 — 재료는 조각의 `meta`다(새 계산 0 · 어댑터가 `split_path`로 무엇으로 잘랐는지 말한다)."""
    sheets = {}
    for p in pieces:
        m = p.get("meta") or {}
        fr = m.get("frame")
        if fr and fr not in sheets:
            sheets[fr] = "통째" if m.get("split_path") == "flat" else "고정 규칙"
    return sheets


# ---------------------------------------------------------------- 프레임 한 벌 (B88 ② — 엑셀·Word가 같이 쓴다)
def frame_chunks(name, lines, rows, locator, sep, base_meta, *, structure_fn=None, marks_fn=None, sheet=True,
                 flat_reason="계층 신호 0건 — 통째로 실었다"):
    """프레임(시트·문서 본문) 하나의 글 조각 — **문서 구조**(B119 ① — 주입되면 무조건) → 고정 규칙 → 통째 또는 분할.

    **포맷이 달라도 한 벌이다**(B88 ② — 분할 규칙 두 벌 금지): 어댑터는 줄 목록·판정
    rows · 줄 표시(`marks_fn`)만 댄다. 자르는 것은 `struct_map.split`, 레벨은 `choose_level` —
    구조가 섰으면 **설비 · 유닛 · 사양 묶음 줄 아래에서는 반드시 자른다**(같은 유닛 아래 청크가 전부 경로에 그 유닛을 든다).
    `base_meta`는 포맷의 표시(엑셀의 `content_column` 등)다. `sheet`면 이름표 0행이 시트 이름이다(Word는 없다).
    """
    path, why, info, st = "heading", None, {}, None
    if structure_fn is not None:
        st = structure_fn(name, labels(name, lines, rows, marks_fn() if marks_fn else {}, sheet))
        if st is not None:
            rows, info = structure_rows(lines, st)
            path = PATH_STRUCT
            if st.get("failed"):
                why = f"구조 호출 실패 — 초안 {st['failed'][:120]}"
    joins = (st or {}).get("joins") or []
    rows0 = rows
    if joins and info:
        rows = _demote_joins(rows, joins)            # 붙임 구간 안쪽 제목은 자르는 자리가 아니다 (B126 ②)
    if info and (st or {}).get("chunks"):
        # **구조가 낸 청크 구간**(B124 ② — 검사를 지난 것만) — 크기 · 단 규칙을 쓰지 않는다(폴백으로만)
        fi = _chain_item(info[FRAME_ROW], name) if info.get(FRAME_ROW) else None
        return range_chunks(name, lines, rows, info, st["chunks"], locator, sep, base_meta, fi)
    frame_info = _chain_item(info[FRAME_ROW], name) if info.get(FRAME_ROW) else None
    if not any(r["heading"] for r in rows):
        # **헤딩 0건 — 통째로 낸다.** 빈 산출도, 지어낸 분할도 만들지 않는다.
        meta = {"split_path": "flat", "frame": name, "section_path": name,
                **base_meta, "hierarchy_unresolved": True,
                "unresolved_reason": flat_reason + (f" · {why}" if why else "")}
        if info:
            meta["structure"] = []
        if frame_info:
            meta["structure_frame"] = frame_info
        return [{
            "source_locator": locator(lines[0][0], lines[-1][0]),
            "section": name,
            "text": "\n".join(t for _r, t in lines),
            "meta": meta,
        }]
    smap = {"rows": rows}
    stats = struct_map.level_stats(smap, lines)
    pick, reason, oor = struct_map.choose_level(stats)
    if info and (st or {}).get("mode") != "edit":       # edit은 고친 나무 위의 크기 구간 그대로(B118 — B126 ②)
        pick, reason, oor = _cut_level(info, stats, pick, reason, oor)
    smap.update({"레벨_분포": stats, "분할_레벨": pick,
                 "분할_레벨_사유": reason, "분할_레벨_구간밖": oor})
    text_of = dict(lines)
    out = []
    keep = {n for j in joins for n, _t in lines if j["from_row"] <= n <= j["to_row"]} if joins else None
    for c in struct_map.split(smap, lines, locator, sep, heads=bool(info), keep_rows=keep,
                              keep_cap=struct_map.CHUNK_MAX_CHARS * CHUNK_OVER if keep else None,
                              keep_split=lambda body: _sibling_parts(body, rows0)):
        hs = c.pop("_heads", None)
        meta = {**(c.get("meta") or {}), "split_path": path, "frame": name, **base_meta,
                "split_level": pick, "section_path": c.get("section") or name}
        if info:
            meta["structure"] = [_chain_item(info.get(r) or {}, text_of[r].strip(), r) for r in hs or []]
        if frame_info:
            meta["structure_frame"] = frame_info
        out.append({**c, "section": c.get("section") or name, "meta": meta})
    return out


# ---------------------------------------------------------------- 문서 구조 (B119 ① — 시트마다 LLM이 무조건)
#: 구조 역할 — **닫힌 셋 · 층 중립**(B124 ③ — 줄의 쓰임만 말한다 · 무엇의 대상인가는 카테고리(층 목록)가 · 층의 말은 층 config
#: `prompts.structure`가 지시문에 덧붙인다): 대상(그 아래 글이 그것의 일부 · 특성을 말한다) · 묶음(한 주인 아래 항목을 묶는
#: 소제목) · 주제(무엇에 대한 글인지 · 대상 없음)
ROLES = ("대상", "묶음", "주제")
#: 대상(이름 · 카테고리)을 갖는 역할 — 그 밖의 역할은 대상이 없다
TARGET_ROLES = ("대상",)
#: 청크를 **반드시 그 아래에서** 자르는 역할(구조가 청크 구간을 내지 않은 시트의 폴백 — B124 ②) — 같은 주인 아래 청크가
#: 전부 경로에 그 주인을 든다
CUT_ROLES = ("대상", "묶음")
#: 주인 줄 — 약한 구조 신호 「대상 0」이 센다
UNIT_ROLES = ("대상",)
SIG_STRUCT = "구조"
PATH_STRUCT = "structure"
#: 구조가 낸 청크 구간이 크기 권장값(`struct_map.CHUNK_MAX_CHARS`)의 몇 배까지 그대로인가 — 넘는 구간만 형제 줄 앞에서 나눈다
#: (B124 ② — 사내 손잡이 `structure_chunk_over` · 창작 기본값 · 자르는 자리의 값이라 구조 보존분에 싣지 않는다)
CHUNK_OVER = 3
#: 이름표의 0행 — 프레임(시트) 이름 그 자체(시트가 대상일 때의 역할 · 대상)
FRAME_ROW = 0
#: 사람이 고친 줄의 「제목 아님」
BODY = "본문"


def labels(name, lines, rows, marks, sheet=True):
    """줄 이름표 — `[{row, text, marks, draft}]`(줄마다 · `sheet`면 0행 = 시트 이름). `draft`는 고정 규칙 초안의 단(0 = 제목 아님).

    `marks[행]`은 어댑터가 채운 표시(굵게 · 들여쓰기n · 병합 · 다른 열 …) — 번호 꼴(`struct_map.number_shape` — 길이와 무관)과
    **빈 줄 자리**(바로 위에 빈 줄이 있었다 — 어댑터가 뺀 빈 행은 행 번호의 틈으로 남는다 · B124 ①)는 여기서 단다(포맷 전부 한 벌).
    글 전체를 싣는다 — 보내는 쪽(core)이 줄당 상한까지 보내고 대상 이름은 전체 글자와 대조한다."""
    draft = {r["row"]: (r.get("level") or 0) for r in rows if r.get("heading")}
    out = [{"row": FRAME_ROW, "text": name, "marks": ["시트"], "draft": 0}] if sheet else []
    prev = None
    for n, t in lines:
        mk = list(marks.get(n) or [])
        shape = struct_map.number_shape(t)
        if shape:
            mk.append(f"번호{shape}")
        if prev is not None and isinstance(n, int) and isinstance(prev, int) and n - prev > 1:
            mk.append("빈 줄")
        prev = n
        out.append({"row": n, "text": t, "marks": mk, "draft": draft.get(n, 0)})
    return out


def labels_hash(labs):
    raw = json.dumps([(x["row"], x["text"], x["marks"], x["draft"]) for x in labs], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def draft_structure(labs):
    """고정 규칙 초안을 구조의 꼴로 — 역할 없음 · 부모 = 앞의 더 얕은 초안 제목(판정이 없을 때 · 고침의 바탕)."""
    out, stack = [], []
    for x in labs:
        lv = x.get("draft") or 0
        if x["row"] == FRAME_ROW or not lv:
            continue
        while stack and stack[-1][0] >= lv:
            stack.pop()
        out.append({"row": x["row"], "parent": stack[-1][1] if stack else None, "role": None,
                    "name": None, "category": None})
        stack.append((lv, x["row"]))
    return out


def apply_fixes(st, fixes, labs):
    """사람의 고침(등록 단 · `{행: {role, name, category} | {role: "본문"}}`)을 구조 위에 — 결정적(재구축이 같은 고침을 쓴다).

    고칠 수 있는 것은 **역할과 대상**이다(단은 그대로) — 제목이 아니던 줄을 고치면 그 앞 제목의 형제로 선다."""
    if not fixes:
        return st
    st = dict(st or {"headings": draft_structure(labs), "source": "draft"})
    heads = {h["row"]: dict(h) for h in st.get("headings") or []}
    order = [x["row"] for x in labs]
    for k, fx in fixes.items():
        r = int(k)
        if r not in order:
            continue
        if fx.get("role") == BODY:
            heads.pop(r, None)
            for h in heads.values():
                if h.get("parent") == r:
                    h["parent"] = None
            continue
        if r not in heads:
            prev = [x for x in order[:order.index(r)] if x in heads and x != FRAME_ROW]
            heads[r] = {"row": r, "parent": heads[prev[-1]].get("parent") if prev else None}
        heads[r].update(role=fx.get("role"), name=fx.get("name"), category=fx.get("category"), by="사람")
    st["headings"] = [heads[r] for r in order if r in heads]
    st["fixed"] = len(fixes)
    return st


def structure_rows(lines, st):
    """검사된 구조 → `(rows, info)` — rows는 고정 규칙과 같은 꼴(단 = 부모 사슬의 깊이 · 신호 `구조`) ·
    info는 `{행: {row, parent, role, name, category, depth}}`(0행 = 시트 자신)."""
    present = {n for n, _t in lines}
    info, depth = {}, {}
    for h in st.get("headings") or []:
        r, p = h.get("row"), h.get("parent")
        if r == FRAME_ROW:
            info[r] = {**h, "depth": 0}
            continue
        if r not in present:
            continue
        depth[r] = depth.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1
        info[r] = {**h, "depth": depth[r]}
    rows = [{"row": n, "heading": n in depth, "level": depth.get(n, 0),
             "signal": SIG_STRUCT if n in depth else None} for n, _t in lines]
    return rows, info


def _demote_joins(rows, joins):
    """붙임(`[{from_row, to_row}]`) — 구간 첫 줄 뒤의 제목은 자르는 자리에서 뺀다(글은 그 청크 본문에 남는다)."""
    inner = {r["row"] for r in rows for j in joins if j["from_row"] < r["row"] <= j["to_row"]}
    return [{**r, "heading": False, "level": 0} if r["row"] in inner and r.get("heading") else r for r in rows]


def _cut_level(info, stats, pick, reason, oor):
    """구조가 선 프레임의 분할 레벨 — 크기로 고른 레벨과 **설비 · 유닛 · 사양 묶음 줄의 가장 깊은 단** 중 깊은 것."""
    need = max((v["depth"] for r, v in info.items() if r != FRAME_ROW and v.get("role") in CUT_ROLES), default=0)
    if pick is None or need <= pick:
        return pick, reason, oor
    st = (stats or {}).get(need) or {}
    avg = st.get("행수_평균")
    oor = avg is None or not (struct_map.CHUNK_MIN <= avg <= struct_map.CHUNK_MAX)
    return need, (f"구조 — {' · '.join(CUT_ROLES)} 줄 아래에서 자른다(단 {need}"
                  + (f" · 평균 {avg}행" if avg is not None else "") + f") · 크기로는 레벨 {pick}"), oor


def _chain_of(info, owner):
    """주인 줄의 사슬 — 위에서 아래로의 제목 행(시트 0행 제외 · 주인이 시트거나 없으면 빈 목록)."""
    out, cur = [], owner
    while cur not in (None, FRAME_ROW) and cur in info and len(out) < 64:
        out.append(cur)
        cur = info[cur].get("parent")
    return list(reversed(out))


def range_chunks(name, lines, rows, info, ranges, locator, sep, base_meta, frame_info=None):
    """**구조가 낸 청크 구간**으로 자른다(B124 ②) — 구간 하나가 청크 하나 · 경로 · 사슬 = 주인 줄의 사슬(주인 줄 글은 본문에서
    빼고 경로에 둔다 — 지금 분할과 같은 꼴) · 크기 권장값의 `CHUNK_OVER`배를 넘는 구간만 형제 줄 앞에서 나눈다(`_sibling_parts` — 조각의
    주인 · 사슬은 그 구간의 것 그대로 · `meta.range_split`). 같은 구간이면 같은 청크다(LLM 0 — 재생)."""
    text_of = dict(lines)
    heads = [n for n, _t in lines if n in info and n != FRAME_ROW]
    meta0 = {"split_path": PATH_STRUCT, "frame": name, **base_meta, "split_level": "구간"}
    if frame_info:
        meta0["structure_frame"] = frame_info
    out = []
    for g in ranges:
        hs = _chain_of(info, g.get("owner_row"))
        body = [(n, t) for n, t in lines if g["from_row"] <= n <= g["to_row"] and n not in hs]
        if not body:
            continue
        over = len("\n".join(t for _n, t in body)) > struct_map.CHUNK_MAX_CHARS * CHUNK_OVER
        for part in (_sibling_parts(body, rows) if over else [body]):
            # 나뉜 조각의 경로 = 첫 줄의 주인 제목(그 줄이 제목이면 그 줄 · 아니면 그 위의 가장 가까운 제목)의 사슬 · 나뉘지 않은 구간은
            # 구간의 주인 그대로 (B130 ② — 자른 단의 청크는 연 제목 · 나눔 조각은 첫 줄의 주인)
            own = next((n for n in reversed(heads) if g["from_row"] <= n <= part[0][0]), g.get("owner_row")) if over else g.get("owner_row")
            ch = _chain_of(info, own) if over else hs
            section = sep.join(text_of[r].strip() for r in ch) or name
            meta = {**meta0, "section_path": section, "chunk_range": [g["from_row"], g["to_row"]],
                    "structure": [_chain_item(info.get(r) or {}, text_of[r].strip(), r) for r in ch]}
            if over:
                meta["range_split"] = True
            out.append({"source_locator": locator(part[0][0], part[-1][0]), "section": section,
                        "text": "\n".join(t for _n, t in part), "meta": meta})
    return out


def _sibling_parts(body, rows):
    """넘는 구간을 **형제 줄 앞에서만** 나눈다 — 그 구간의 가장 얕은 제목 단의 줄이 형제다 · 형제 덩어리를 권장값까지 이어 붙인다
    (형제 하나의 중간에서는 끊지 않는다 · 글은 그대로 — 제목 줄도 본문에 남는다 · 주인은 그 구간의 주인 그대로)."""
    level = {r["row"]: r["level"] for r in rows if r.get("heading")}
    keep = {n for n, _t in body}
    lv = min((level[n] for n in keep if n in level), default=None)
    blocks, cur = [], []
    for n, t in body:
        if cur and lv is not None and level.get(n) == lv:
            blocks.append(cur)
            cur = []
        cur.append((n, t))
    blocks += [cur] if cur else []
    out, acc = [], []
    for b in blocks:
        if acc and len("\n".join(t for _n, t in acc + b)) > struct_map.CHUNK_MAX_CHARS:
            out.append(acc)
            acc = []
        acc = acc + b
    return out + ([acc] if acc else [])


def _chain_item(h, text, row=None):
    out = {"row": h.get("row", row), "text": text, "role": h.get("role")}
    if h.get("name") and h.get("category"):
        out.update(name=h["name"], category=h["category"])
    if h.get("by"):
        out["by"] = h["by"]
    return out


def structure_hook(ask, doc_id, *, kept=None, made=None, tally=None, fixes=None, skip=(), confirmed=None, ctx=None):
    """어댑터에 건넬 **구조 훅** — 보존분(같은 원본 · 같은 이름표 · 같은 판)이면 그것(호출 0) · 아니면 `ask` 한 번.

    `ask(doc_id, frame, labels)` → 검사가 끝난 구조 `{headings: [{row, parent, role, name, category}], dropped, calls,
    failed?}` 또는 None(판정 없음 — mock 힌트 없음). `ask.key()`가 판(지시문 · config)을 말한다 · `skip`(`ref` 시트)은
    부르지 않는다. 사람의 고침(`fixes[frame]` — 등록 단)은 그 위에 덮는다. 실패한 판정은 보존하지 않는다(다음 인입이 다시 묻는다).
    **확정 시트**(`confirmed[frame]` — 구조 확인에서 사람이 확정 · B126 ③)는 같은 이름표면 그것이 이긴다(LLM 0) · `rules` 방식은
    판정 없음(고정 규칙 그대로 — 셈에는 규칙 나무를 남겨 구조 확인이 같은 꼴로 보인다) · `ctx`(문서 종류 · 문서 좌표 · 다른 시트 이름)는 받는 판정에만."""
    kept, fixes = kept or {}, fixes or {}
    tally = tally if tally is not None else {}
    key = ask.key() if callable(getattr(ask, "key", None)) else None

    doc_hints = (ask.doc_state(doc_id).get("hints") or []) if callable(getattr(ask, "doc_state", None)) else []

    def fn(frame, labs):
        if frame in skip:
            return None
        h = labels_hash(labs)
        hit = kept.get(frame)
        conf = (confirmed or {}).get(frame)
        if conf and conf.get("toc") != toc.TOC_VERSION:
            tally.setdefault("옛 확정", []).append(frame)     # 목차 판이 다른 옛 확정 — 재생하지 않고 다시 보인다 (B130 ⑤)
            conf = None
        if conf and conf.get("labels") == h:
            tally["확정"] = tally.get("확정", 0) + 1
            st = {**conf, "source": "confirmed", "calls": 0, "confirmed": True}
        elif (hit and hit.get("labels") == h and hit.get("key") == key
              and (hit.get("doc_hints") or []) == doc_hints):        # 문서 힌트가 바뀌면 다시 묻는다 (B130 ④)
            tally["재사용"] = tally.get("재사용", 0) + 1
            st = hit
        else:
            st = ask(doc_id, frame, labs, ctx=ctx) if getattr(ask, "takes_ctx", False) else ask(doc_id, frame, labs)
            if st is not None and not st.get("skip"):
                tally["호출"] = tally.get("호출", 0) + int(st.get("calls") or 0)
                st = {**st, "labels": h, "key": key}
                if made is not None and not st.get("failed"):
                    made[frame] = st
        rules = st is not None and (st.get("skip") or st.get("mode") == "rules")
        shown = {"headings": draft_structure(labs), "mode": "rules", "confirmed": (st or {}).get("confirmed")} if rules else None
        st = apply_fixes(None if rules else st, fixes.get(frame), labs)   # rules — 고정 규칙 그대로(사람의 고침만 덮는다)
        if st is not None and rules:
            st["mode"] = "rules"
        if st is not None or shown:
            v = st or shown
            tally.setdefault("프레임", {})[frame] = {
                "labels": labs, "headings": v.get("headings") or [], "dropped": v.get("dropped") or [],
                "failed": v.get("failed"), "source": v.get("source"), "fixed": v.get("fixed", 0),
                "chunks": v.get("chunks") or [], "chunks_dropped": v.get("chunks_dropped"),
                "mode": v.get("mode") or "llm", "edits": v.get("edits") or [], "edits_dropped": v.get("edits_dropped") or [],
                "joins": v.get("joins") or [], "hints": v.get("hints") or [], "answer": v.get("answer"),
                "rules": v.get("rules") or [], "doc_hints": v.get("doc_hints") or [],
                "confirmed": bool(v.get("confirmed")), "prompt_version": v.get("prompt_version")}
            tally.setdefault("방식", {})[frame] = v.get("mode") or "llm"
        return st
    return fn
