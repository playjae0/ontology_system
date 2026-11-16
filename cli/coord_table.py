# -*- coding: utf-8 -*-
"""칸 0.3 — **좌표 표** — 좌표마다 한 줄: 그 좌표 아래 값이 그래프에서 어떻게 됐나 (B176).

인입 화면(표의 공정 그룹 끝 — `ingest_screen.group_gate`)과 `show report <doc_id>`가 **같은 함수**로 센다 · 재료는 판정
대장 행뿐이다(새 판정 0 · 값의 결과는 `_screen.outcome` 하나). 위치(표의 행 · 산문의 조각)의 좌표 행(`role` anchor)이
그 위치의 좌표이고, 같은 위치의 값 행(`role` entity)이 그 좌표의 값이다 — 표 · 산문이 같은 함수를 지난다.
"""
from __future__ import annotations

from cli import _screen

#: 값의 결과(`_screen.OUTCOME`) → 좌표 줄의 칸 · 결과 없음(빈칸 표시 · 표 밖 판정)은 「노드 아님」 칸
COLS = {"붙음": "붙음", "새로 생김": "새로", "그래프에 없음": "보류", "노드 아님": "노드 아님", None: "노드 아님"}
#: 위치에 이름 있는 좌표 행이 없다(빈 좌표 · 산문의 좌표 없는 조각)
NONE = "좌표 없음"


def _coord(anchors):
    """위치의 좌표 행들 → `((이름, 찾음, 사유), 저해상도)` — 앞이 좌표 키(찾음은 참 · 거짓 · None(좌표 없음)) · 저해상도는 그
    위치가 상위 공정으로 붙었는가(키에 넣지 않는다 — 같은 노드에 선 위치는 해상도와 무관하게 한 줄)."""
    named = [a for a in anchors if a.get("surface") or a.get("node_id")]
    if not named:
        return (NONE, None, None), False
    name = " · ".join(str(a.get("canonical") if a.get("node_id") else a.get("surface")) for a in named)
    miss = [a for a in named if not a.get("node_id")]
    if miss:
        return (name, False, _screen.outcome(miss[0])[2]), False
    return (name, True, None), any(a.get("verdict") == "lowres" for a in named)


def table(rows):
    """대장 행 → 좌표마다 `{좌표, 찾음, 사유, 저해상도, 행, 값, 붙음, 새로, 검토, 보류, 노드 아님}` — 처음 나온 순서.

    `행` = 그 좌표에 선 위치 수(표의 행 · 산문의 조각) · `저해상도` = 그중 상위 공정으로 붙은 위치 수 · `값` = 그 위치들의 값 행
    수 = 붙음 + 새로 + 보류 + 노드 아님."""
    anchors, values, order = {}, {}, []
    for r in rows:
        role = r.get("role")
        if role not in ("anchor", "entity"):
            continue
        loc = r.get("locator")
        if loc not in anchors and loc not in values:
            order.append(loc)
        (anchors if role == "anchor" else values).setdefault(loc, []).append(r)
    out = {}
    for loc in order:
        key, low = _coord(anchors.get(loc) or [])
        c = out.setdefault(key, {"좌표": key[0], "찾음": key[1], "사유": key[2], "저해상도": 0, "행": 0, "값": 0,
                                 "붙음": 0, "새로": 0, "검토": 0, "보류": 0, "노드 아님": 0})
        c["행"] += 1
        c["저해상도"] += low
        for v in values.get(loc) or []:
            res, _kind, mark = _screen.outcome(v)
            c["값"] += 1
            c[COLS.get(res, "노드 아님")] += 1
            c["검토"] += mark == _screen.REVIEW
    return list(out.values())


def totals(rows):
    """대장 행 → `{붙음, 새로, 검토, 보류}` 합 — 그룹 요약 줄의 칸(좌표 표와 같은 셈)."""
    t = {"붙음": 0, "새로": 0, "검토": 0, "보류": 0}
    for c in table(rows):
        for k in t:
            t[k] += c[k]
    return t


def line(c):
    """좌표 하나 → `(글, 색 이름)` — 찾음 초록 · 못 찾음 빨강 · 좌표 없음은 보류가 있으면 빨강."""
    head = c["좌표"] + (f" (저해상도 {c['저해상도']:,}행)" if c["저해상도"] else "")
    more = [f"{k} {c[k]:,}" for k in ("노드 아님",) if c[k]]
    if c["찾음"] is False:
        more = [f"{k} {c[k]:,}" for k in ("붙음", "새로") if c[k]] + more
        text = f"{head} — 못 찾음({c['사유'] or '목록 밖'}) · 행 {c['행']:,} · 보류 값 {c['보류']:,}"
        kind = "orphan"
    else:
        text = (f"{head} · 행 {c['행']:,} · 붙음 {c['붙음']:,} · 새로 {c['새로']:,}(검토 {c['검토']:,}) · "
                f"보류 {c['보류']:,}")
        kind = "anchor" if c["찾음"] else ("orphan" if c["보류"] else None)
    return text + "".join(f" · {m}" for m in more), kind


def show(rows, indent="     "):
    """좌표 표를 찍는다(좌표마다 한 줄 · 색은 `line`) — 인입 그룹 끝 · `show report`가 같은 손."""
    for c in table(rows):
        text, kind = line(c)
        _screen.say(indent + text, kind)


# ── 판정 화면 — 묶음 한 줄 (B209 ②) · 관계 한 번 (B208 ②) ─────────────────────────────
#: 줄의 기호 — 인입 값 표와 같은 결과 기호(`ingest_screen.MARKS`의 짝 · 결과 없음은 `·`)
SYM = {"붙음": "✓", "새로 생김": "+", "그래프에 없음": "✗", "노드 아님": "↗"}
#: 묶음 아래 `└` 줄 상한(넘으면 「그 밖 n」 — 행마다는 명령 로그 · `show report --rows`)
SUBS_MAX = 5


def edge_key(row, a):
    """붙은 자리 하나 → 엣지 키 `(앞, 관계, 뒤)` — 양 끝 행이 같은 엣지를 한 번씩 받으니 → 쪽으로 맞춘다(관계는 한 번)."""
    me = row.get("target") or row.get("canonical") or row.get("surface")
    return (me, a["rel"], a["other"]) if a.get("dir") != "←" else (a["other"], a["rel"], me)


def edge_line(row, a):
    """엣지 하나의 `└` 줄 — 늘 → 쪽(`앞 · 관계 → 뒤 (방식)`)."""
    src, rel, dst = edge_key(row, a)
    if a.get("dir") != "←":
        src = row.get("surface") or src                  # 이 행이 앞 끝이면 그 표기로
    return f"     └ {src} · {rel} → {dst} ({a['path']})"


def _sub(e):
    """LLM이 든 개체 · 애매 · 보류의 `└` 줄 — 판단 · 확실도 · 후보(가장 가까운) · 표시."""
    from parser.coord_rows import VERDICT
    calls, (_r, _k, mark) = (e.get("llm") or {}).get("calls"), _screen.outcome(e)
    near = (e.get("nearest") or {}).get("canonical")
    parts = [VERDICT.get(e.get("verdict"), e.get("verdict")) if calls else e.get("verdict")]
    parts += [f"{e.get('confidence', 0):.2f}"] if calls else []
    parts += [f"후보 {e.get('candidates_n') or 0}" + (f"({near})" if near else "")] + ([str(mark)] if mark else [])
    return f"          └ {e.get('surface') or e.get('canonical')} — " + " · ".join(str(p) for p in parts if p)


def fit(segs, width=None, tail=None):
    """칸들 `[(글, 색)]` → 터미널 폭에서 자른 한 줄(자른 뒤 칸마다 칠한다 — 파이프는 색 0) · `tail`(끝 칸)은 늘 남긴다."""
    room, out = (width or _screen.term_width()) - 1 - (_screen.w(tail[0]) if tail else 0), []
    for text, kind in segs + ([tail] if tail else []):
        if tail and (text, kind) == tail:
            room += _screen.w(text)
        if room <= 1:
            break
        text = text if _screen.w(text) <= room else _screen.cut(text, room - 1)
        out.append(_screen.paint(text, kind))
        room -= _screen.w(text)
    return "".join(out)


def judged(r):
    """**판정으로 정해진 항목** — LLM · 애매 · 보류 · 사람 문(사전 · 관문으로 끝은 수만 — B209 ②)."""
    return bool((r.get("llm") or {}).get("calls") or r.get("verdict") == "uncertain" or r.get("by")
                or _screen.outcome(r)[0] == "그래프에 없음")


def _name(a):
    return (a.get("canonical") if a.get("node_id") else a.get("surface")) or "—"


def bundle_key(rows):
    """묶음 열쇠 — `(공정, (맨 위 개체 열, 표기))` · 같은 공정 안 맨 위 개체가 같은 연속 행이 한 묶음이다."""
    ents = [r for r in rows if r.get("role") == "entity"]
    return (tuple(_name(a) for a in rows if a.get("role") == "anchor"),
            (ents[0].get("field"), ents[0].get("surface")) if ents else None)


def _syms(rs):
    from collections import Counter
    return " ".join(f"{s}{n:,}" for s, n in Counter(SYM.get(_screen.outcome(r)[0], "·") for r in rs).items())


def split_info(records):
    """**원본 행 → 나눈 행**(위치의 `#n` 접미로 센다) — `(원본 수, 나눈 수, 나눈 열들)` · 나눈 열 = 같은 원본의 형제끼리 값이 다른 칸."""
    sib = {}
    for r in records or []:
        sib.setdefault(str(r.get("source_locator") or "").split("#")[0], []).append(r)
    cols = {f for rs in sib.values() if len(rs) > 1 for f in rs[0] if f != "source_locator" and isinstance(rs[0][f], str)
            and len({str(x.get(f)) for x in rs}) > 1}
    return len(sib), len(records or []), sorted(cols)


def bundle_line(items, label=str, width=None):
    """**묶음 한 줄**(B209 ②) — `items` [(위치, 그 행의 대장 행들)] → `(줄, └ 줄들)`: 공정 › 맨 위 개체(기호별 수) · 원본 행 범위 ·
    나눈 행 · 아래 개체 열마다 수(기호별) · 보류 행 · 아래 `└`는 판정으로 정해진 항목만(같은 표기는 한 번 · 상한 SUBS_MAX)."""
    rows = [r for _l, rs in items for r in rs]
    procs, top = bundle_key(items[0][1])
    base = list(dict.fromkeys(str(l).split("#")[0] for l, _r in items))
    held = {l for l, rs in items if any(r.get("role") == "anchor" and _screen.outcome(r)[0] == "그래프에 없음" for r in rs)}
    ents = [r for r in rows if r.get("role") == "entity"]
    tops = [r for r in ents if (r.get("field"), r.get("surface")) == top]
    span = label(base[0]) + (f"~{label(base[-1])}" if len(base) > 1 else "")
    by = {}
    for r in ents:
        if (r.get("field"), r.get("surface")) != top:
            by.setdefault(r.get("field"), []).append(r)
    segs = [(f"   {' · '.join(procs) or '좌표 없음'} › {top[1] if top else '—'} ({_syms(tops)})",
             _screen.outcome(tops[0])[1] if tops else None),
            (f" — 원본 {span} {len(base):,}행" + (f" · 나눈 {len(items):,}행" if len(items) != len(base) else ""), "aux")]
    segs += [(f" · {f} {len(rs):,}({_syms(rs)})", "aux") for f, rs in by.items()]
    if held:
        a = next(r for l, rs in items if l in held for r in rs if r.get("role") == "anchor")
        segs.append((f" · 보류 {len(held):,}행({_screen.outcome(a)[2]})", "orphan"))
    subs, seen = [], set()
    for l, rs in items:
        for r in rs:
            k = (r.get("field"), r.get("surface"))
            if l not in held and r.get("role") == "entity" and judged(r) and k not in seen:
                seen.add(k)
                subs.append(_sub(r))
    more = [f"          … 그 밖 {len(subs) - SUBS_MAX:,} — 행마다는 명령 로그 · show report --rows"] if len(subs) > SUBS_MAX else []
    return fit(segs, width), [_screen.cut(x, (width or _screen.term_width()) - 2) for x in subs[:SUBS_MAX] + more]
