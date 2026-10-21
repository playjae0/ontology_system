# -*- coding: utf-8 -*-
"""칸 2.4 — **계층 사다리 적용** — 사다리 + 이어짐 · 첫 서수 + 들여쓰기 깊이로 목차 초안을 세우고 판단 필요를 표시한다 (B132 ④ · B137 ①②③④).

    apply(labs, ladder, doc_counts)  이름표 → `{headings, needs}` — 모든 시트에 같은 함수(엑셀 산문 · Word)
    stats(frames)                    문서 전체 서명 통계(시트마다 서명별 수 · 이어짐 · 다시 시작 자리 · 깊이별 서명) — 사다리 입력
    code(frames)                     코드 사다리(다시 시작 증거 — `parser/toc.code_ladder` · `rules` 방식 · 폴백)
    title_row(labs)                  첫 행이 시트 제목이면 그 행(B137 ②)

**초안**(코드 — LLM이 최종 · B137 ①): 번호 줄은 이어짐(같은 꼴의 열린 목록에서 바로 다음 서수) → 그 목록의 형제 · 첫 서수(그 꼴의 첫
번호) → **바로 위 제목 줄의 자식**(같은 꼴이 두 깊이에 선다) · 둘 다 아니면 사다리의 단 순서. 사다리 단 순위(`forbid`)는 근거 하나다 —
어긋나면 판단 필요. **첫 행 = 시트 제목**(번호를 붙인 채 · 뗀 채 · 공백 · 마침표 무시)이면 그 줄은 목차 맨 위에 서고 단을 다투지 않는다.

사다리 꼴: `{"levels": [{"sigs": [서명…], "role", "category"}], "unnumbered": [{"when": [조건…], "level", "role", "category"}],
"lists": [{"shape", "parent_shape", "role", "category"}], "by"}` — 위에서 아래로 단 · 역할은 닫힌 셋(대상 · 묶음 · 주제) · 번호 없는 제목의
규칙은 닫힌 조건(`WHEN`)으로만 말한다 · `lists`는 시트 확인의 규칙 「P 아래에서 첫 서수로 시작하는 S 목록」(꼴 전부를 옮기지 않는다).

**판단 필요**(코드가 정하지 않고 표시 — `NEED_KINDS`): ⓐ사다리에 없는데 제목 같은 서명 ⓑ부모보다 들여쓰기가 얕다 ⓒ이어짐이 끊김 ·
다시 시작의 부모가 둘 이상(첫 서수가 단 순서와 어긋남 · 사다리 단을 건너뜀) ⓓ빈 행 뒤 짧은 번호 없는 줄 ⓔ서식이 형제 · 앞뒤 본문과
다르다(보조 단서 — 서식만으로 깊이를 정하지 않는다) ⓕ붙은 다단 번호(`3.2출하검수` — 값일 수도). 답은 시트 확인(LLM · 사람)의 몫이다.
"""
from __future__ import annotations

from parser import sig as SG
from parser import toc

#: 번호 없는 제목 규칙의 닫힌 조건 — `빈 줄 뒤` · `짧은 줄` · `굵게` · `병합` · `깊이 n` · `시작 열 X`
WHEN = ("빈 줄 뒤", "짧은 줄", "굵게", "병합")
NEED_KINDS = {"ⓐ": "사다리에 없는 서명", "ⓑ": "들여쓰기 어긋남", "ⓒ": "이어짐 · 다시 시작", "ⓓ": "빈 행 뒤 짧은 줄",
              "ⓔ": "서식 다름", "ⓕ": "붙은 다단 번호"}
#: 판단 필요의 한 마디(화면 · md의 목차 줄 — B137 ⑥)
TAGS = {"ⓐ": "사다리 밖?", "ⓑ": "깊이 어긋남", "ⓓ": "빈 행 뒤 제목?", "ⓔ": "서식 다름", "ⓕ": "붙은 번호?"}
#: 서식 표시 — 이름표 `marks` 가운데 서식(같은 문서 안 비교의 보조 단서 · B137 ③)
FORMAT = ("굵게", "크기", "채움", "글자색")
#: 시트 제목 줄의 열쇠(서명이 아니다 — 단을 다투지 않는다 · B137 ②)
TITLE = "@제목"
_OUTLINE = "개요"                               # 어댑터의 구조 단(Word 개요 수준 — 서명 없는 draft 제목)


def _short(x):
    from parser.struct_map import HEADING_MAX_CHARS
    return (x.get("len") if x.get("len") is not None else len(str(x.get("text") or "").strip())) <= HEADING_MAX_CHARS


def _flat(t):
    return "".join(ch for ch in str(t or "") if not ch.isspace() and ch not in ".|")


def title_row(labs):
    """**첫 행 = 시트 제목**(B137 ②) — 시트의 첫 글 줄이 시트 이름과 같으면 그 행 · 아니면 None. 번호를 붙인 채 · 뗀 채 둘 다 견준다
    (양쪽 모두) · 공백 · 마침표 · 셀 이음 차이는 무시한다 · 시트 이름이 없는 프레임(Word 본문)은 None."""
    frame = next((x for x in labs if x["row"] == 0), None)
    rows = [x for x in labs if x["row"] != 0]
    if frame is None or not rows:
        return None

    def forms(t):
        return {f for f in (_flat(t), _flat(SG.strip_head(t))) if f}
    return rows[0]["row"] if forms(rows[0]["text"]) & forms(frame["text"]) else None


def _body(labs):
    """시트 이름(0행)과 시트 제목 줄을 뺀 줄 — 통계 · 사다리 · 판단 필요의 재료."""
    t = title_row(labs)
    return [x for x in labs if x["row"] != 0 and x["row"] != t]


def fmt_of(x):
    """서식 열쇠 — `marks`의 서식만(크기는 정수로) · 없으면 빈 튜플."""
    out = []
    for m in x.get("marks") or []:
        m = str(m)
        if m.startswith("크기"):
            try:
                m = f"크기{round(float(m[2:]))}"
            except ValueError:
                pass
        if m.startswith(FORMAT):
            out.append(m)
    return tuple(sorted(out))


def fmt_text(x):
    """짧은 서식 표시(골격 보기 · 화면) — `크기14 굵게 채움 글자색` · 없으면 빈 글."""
    return " ".join(fmt_of(x))


def doc_counts(frames):
    """문서 전체 짧은 줄의 서명별 수 `{서명: n}` — 판단 필요 ⓐ(문서에 둘 이상)의 재료."""
    out = {}
    for labs in frames.values():
        for x in _body(labs):
            if x.get("sig") and _short(x):
                out[x["sig"]] = out.get(x["sig"], 0) + 1
    return out


def code(frames):
    """코드 사다리 — 시트들의 짧은 번호 줄에서 다시 시작 증거(`parser/toc.code_ladder`)."""
    return toc.code_ladder([[(x["row"], x["text"]) for x in _body(labs)] for labs in frames.values()])


def stats(frames):
    """**문서 전체 서명 통계**(사다리 입력 — 줄 전문 0) — `{시트: [{서명, 수, 이어짐, 다시 시작, 깊이}]}`.

    이어짐 = 같은 서명이 서수 1씩 이어진 덩어리 수 · 다시 시작 = 다른 서명 줄 바로 아래에서 첫 서수로 시작한 자리(`{아래 서명, 행}`) ·
    깊이 = 들여쓰기 깊이별 줄 수."""
    out = {}
    for name, labs in frames.items():
        rows, prev, by = _body(labs), None, {}
        last = {}
        for x in rows:
            s, v = x.get("sig"), x.get("ord")
            if not s or not _short(x):
                continue
            e = by.setdefault(s, {"서명": s, "수": 0, "이어짐": 0, "다시 시작": [], "깊이": {}})
            e["수"] += 1
            e["깊이"][str(x.get("depth") or 0)] = e["깊이"].get(str(x.get("depth") or 0), 0) + 1
            if v is not None and last.get(s) is not None and v == last[s] + 1:
                e["이어짐"] += 1
            if v == 1 and prev is not None and prev[0] != s:
                e["다시 시작"].append({"아래": prev[0], "행": x["row"]})
            if v is not None:
                last[s] = v
            prev = (s, x["row"])
        for e in by.values():
            e["다시 시작"] = e["다시 시작"][:6]
        out[name] = list(by.values())
    return out


def _match(rule, x):
    for w in rule.get("when") or []:
        w = str(w)
        if w == "빈 줄 뒤" and not x.get("gap"):
            return False
        if w == "짧은 줄" and not _short(x):
            return False
        if w in ("굵게", "병합") and w not in (x.get("marks") or []):
            return False
        if w.startswith("깊이 ") and str(x.get("depth") or 0) != w[3:].strip():
            return False
        if w.startswith("시작 열 ") and str(x.get("col") or "") != w[5:].strip():
            return False
    return bool(rule.get("when"))


def apply(labs, ladder, counts=None):
    """이름표 + 사다리 → `{"headings": [{row, parent, role, name, category, sig, by}], "needs": [{row, kind, why, tag}]}`.

    번호 줄 — 사다리에 든 서명만 목차에 선다(초안 — 이어짐 · 첫 서수 · 사다리의 단 순서 — `parser/toc`) · 번호 없는 줄 — 사다리의
    `unnumbered` 규칙에 맞는 줄만(그 규칙의 단) · 어댑터의 구조 단(Word 개요 수준 — 표시 `개요n`)은 사다리 위 단 · 시트 제목 줄은
    맨 위(역할 없음 — 시트 확인이 정한다) · 역할 · 카테고리는 그 단의 것(대상이면 이름 = 줄 글에서 번호를 뗀 것) · 첫 서수 목록
    규칙(`lists`)에 걸린 줄은 그 규칙의 것(`by` 「규칙」)."""
    title = title_row(labs)
    rows = _body(labs)
    by_row = {x["row"]: x for x in labs if x["row"] != 0}
    levels = (ladder or {}).get("levels") or []
    rank = toc.rank_of(ladder)
    meta = {s: lv for lv in levels for s in lv.get("sigs") or []}
    rules = [r for r in (ladder or {}).get("unnumbered") or [] if isinstance(r, dict)]
    lists = {(u.get("shape"), u.get("parent_shape")): u for u in (ladder or {}).get("lists") or [] if isinstance(u, dict)}
    hits = [(title, TITLE, None)] if title is not None else []
    if title is not None:
        rank[TITLE] = -1000                                 # 맨 위 — 어느 단도 그 위로 닫지 않는다
    for x in rows:
        s, v = x.get("sig"), x.get("ord")
        if s and s in rank and _short(x):
            hits.append((x["row"], s, v))
        elif not s and x.get("draft") and any(str(m).startswith(_OUTLINE) for m in x.get("marks") or []):
            key = f"{_OUTLINE}{x['draft']}"                 # Word 개요 수준만(작성자가 매긴 구조) — 굵게 초안은 단 신호가 아니다
            rank.setdefault(key, -100 + int(x["draft"]))
            hits.append((x["row"], key, None))
        elif not s:
            hit = next((i for i, r in enumerate(rules) if _match(r, x)), None)
            if hit is not None:
                key = f"~{hit}"
                rank.setdefault(key, float(rules[hit].get("level") or 0) - 0.5)
                hits.append((x["row"], key, None))
    forbid = {(c, p) for c in rank for p in rank if rank[c] <= rank[p]}
    first = {"lists": set(lists), "clash": [], "ruled": {}, "loose": []}
    lv = toc._toc(hits, forbid, rank=rank, first=first)
    parent, stack = {}, []
    for r, _k, _v in hits:
        while stack and stack[-1][0] >= lv[r]:
            stack.pop()
        parent[r] = stack[-1][1] if stack else None
        stack.append((lv[r], r))
    heads = []
    for r, k, _v in hits:
        if k == TITLE:
            heads.append({"row": r, "parent": None, "role": None, "name": None, "category": None, "sig": k, "by": "시트 제목"})
            continue
        lst = lists.get(first["ruled"].get(r)) if r in first["ruled"] else None
        src = (lst if lst and lst.get("role") else None) or meta.get(k) or (rules[int(k[1:])] if k.startswith("~") else {})
        role, cat = src.get("role"), src.get("category")
        h = {"row": r, "parent": parent[r], "role": role, "name": None, "category": None, "sig": k,
             "by": "규칙" if lst else "사다리", **({"rule": list(first["ruled"][r])} if lst else {})}
        if role == "대상" and cat:
            h.update(name=SG.strip_head(by_row[r]["text"]), category=cat)
        heads.append(h)
    return {"headings": heads, "needs": needs(labs, heads, rank, counts or {}, first["clash"], first["loose"])}


def needs(labs, heads, rank, counts, clash=(), loose=()):
    """판단 필요(머리말) — `[{row, kind, why, tag}]` 이름표 순 · 한 줄에 하나(앞의 것 — 뒤의 이유는 `why`에 덧붙인다)."""
    rows = _body(labs)
    by_row = {x["row"]: x for x in labs if x["row"] != 0}
    head = {h["row"]: h for h in heads}
    out = {}

    def add(r, kind, why, tag=None):
        if r in out:
            if why not in out[r]["why"]:
                out[r]["why"] += f" · {why}"
            return
        out[r] = {"row": r, "kind": kind, "why": why, "tag": tag or TAGS.get(kind) or NEED_KINDS[kind]}
    for x in rows:
        s = x.get("sig")
        if s and s not in rank and x["row"] not in head and _short(x) and counts.get(s, 0) >= 2:
            add(x["row"], "ⓐ", f"사다리에 없는 서명 '{SG.show(s)}'(문서에 {counts[s]}줄)")
    for h in heads:
        p = h.get("parent")
        if p in by_row and (by_row[h["row"]].get("depth") or 0) < (by_row[p].get("depth") or 0):
            add(h["row"], "ⓑ", f"들여쓰기 깊이 {by_row[h['row']].get('depth') or 0}가 부모 {p}행(깊이 "
                                f"{by_row[p].get('depth') or 0})보다 얕다")
    for r in clash:
        add(r, "ⓒ", f"첫 서수로 바로 위 {head[r].get('parent')}행 아래에 섰다 — 사다리 단 순서와 어긋남(부모 후보가 둘 이상)", "다시 시작?")
    for r in loose:
        add(r, "ⓒ", f"이어지는 목록도 첫 서수도 아니다 — 사다리 단 순서로 {head[r].get('parent')}행 아래에 섰다", "번호 끊김")
    kids = {}
    for h in heads:
        kids.setdefault((h.get("parent"), h.get("sig")), []).append(h["row"])
    for (p, s), rs in kids.items():
        prev = None
        for r in rs:
            v = by_row[r].get("ord")
            if v is not None and prev is not None and v != prev + 1:       # 첫 형제가 1이 아닌 것(발췌)은 끊김이 아니다
                add(r, "ⓒ", f"다시 시작 — 같은 부모 아래 '{SG.show(s)}'가 1부터 다시(부모 후보가 둘 이상)" if v == 1
                    else f"이어짐 끊김 — '{SG.show(s)}' {prev} 다음 {v}", "다시 시작?" if v == 1 else "번호 끊김")
            prev = v if v is not None else prev
    for h in heads:
        p = head.get(h.get("parent"))
        if by_row[h["row"]].get("ord") == 1 and p and p["sig"] != TITLE and isinstance(rank.get(h["sig"]), int) \
                and isinstance(rank.get(p["sig"]), int) and rank[h["sig"]] - rank[p["sig"]] >= 2:
            add(h["row"], "ⓒ", f"다시 시작 — 사다리 단을 건너뛰었다(부모 후보가 둘 이상 · 지금 부모 {p['row']}행)", "다시 시작?")
    t = title_row(labs)
    if t is not None and by_row[t].get("sig") and by_row[t].get("ord") is not None:
        for x in rows:
            if x.get("sig") == by_row[t]["sig"] and x.get("ord") == by_row[t]["ord"] + 1 and _short(x):
                add(x["row"], "ⓒ", "시트 제목 번호의 다음 번호 — 시트 제목의 형제일 수도", "다시 시작?")
    for x in rows:
        cand, _v = SG.attached(x.get("text"))
        if cand and not x.get("sig") and _short(x) and x["row"] not in head:
            add(x["row"], "ⓕ", f"붙은 다단 번호 '{SG.show(cand)}' — 번호인지 값(1.5배 · 2024.10월)인지")
    for x in rows:
        if not x.get("sig") and x.get("gap") and _short(x) and x["row"] not in head:
            add(x["row"], "ⓓ", "빈 행 뒤 짧은 번호 없는 줄")
    _format_needs(rows, heads, by_row, head, add)
    order = {x["row"]: i for i, x in enumerate(labs)}
    return sorted(out.values(), key=lambda n: order.get(n["row"], 0))


def _format_needs(rows, heads, by_row, head, add):
    """ⓔ **서식 다름**(보조 단서 · B137 ③④) — ①같은 꼴 · 같은 부모의 형제 가운데 흔한 서식과 다른 줄 ②다른 꼴인데 형제로 선 바로 앞
    형제와 서식이 다른 줄 ③빈 행이 없어도 서식이 앞뒤 본문과 다른 짧은 번호 없는 줄 — 같은 시트 안 비교만 · 깊이는 바꾸지 않는다."""
    fm = {r: fmt_of(x) for r, x in by_row.items()}

    def say(k):
        return " ".join(k) or "보통"
    mine = [h for h in heads if h["sig"] != TITLE]
    fam, kids = {}, {}
    for h in mine:
        fam.setdefault((h.get("parent"), h["sig"]), []).append(h["row"])
        kids.setdefault(h.get("parent"), []).append(h)
    for rs in fam.values():
        keys = [fm[r] for r in rs]
        ref = max(keys, key=lambda k: (keys.count(k), -keys.index(k)))
        for r in rs:
            if len(rs) > 1 and fm[r] != ref:
                add(r, "ⓔ", f"서식 {say(fm[r])}이 같은 꼴 형제({say(ref)})와 다르다")
    for sibs in kids.values():
        for a, b in zip(sibs, sibs[1:]):
            if a["sig"] != b["sig"] and fm[a["row"]] != fm[b["row"]]:
                add(b["row"], "ⓔ", f"다른 꼴 형제 {a['row']}행과 서식이 다르다({say(fm[a['row']])} → {say(fm[b['row']])})")
    body = [x for x in rows if x["row"] not in head]
    for i, x in enumerate(body):
        if x.get("sig") or x.get("gap") or not _short(x) or not fm[x["row"]] or SG.attached(x.get("text"))[0]:
            continue
        nb = [fm[y["row"]] for y in (body[i - 1] if i else None, body[i + 1] if i + 1 < len(body) else None) if y]
        if nb and all(k != fm[x["row"]] for k in nb):
            add(x["row"], "ⓔ", f"서식 {say(fm[x['row']])}이 앞뒤 본문과 다른 짧은 번호 없는 줄")
