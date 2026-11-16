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


# ── 표의 한 행 한 줄 (B208 ①②) ─────────────────────────────────────────────
#: 값 칸을 낱낱이 쓰는 열 수 상한(넘으면 `값 n`) · 값 하나의 폭 상한
VALS_MAX, VAL_W = 3, 14
#: 줄의 기호 — 인입 값 표와 같은 결과 기호(`ingest_screen.MARKS`의 짝 · 결과 없음은 `·`)
SYM = {"붙음": "✓", "새로 생김": "+", "그래프에 없음": "✗", "노드 아님": "↗"}


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


def _flat(v, n=VAL_W):
    return _screen.cut(" ".join(str(v).split()), n) if v not in (None, "") else "—"


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


def row_line(rows, rec=None, label="", width=None):
    """**표의 한 행 한 줄**(B208 ①) — 그 행의 대장 행들 → `(줄, └ 줄들)`. 좌표 · 개체 열마다 `열 이름 · 이름 · 기호` · 값은
    `열 이름 값`(원 레코드의 값 자체 — 길면 자름 · 열이 많으면 `값 n`) · 관계 수(엣지 키 — 한 번씩) · 좌표가 그래프에 없으면
    행 보류 한 칸. 색 · 기호는 `_screen.outcome` 하나(새 판정 0)."""
    rec, segs, subs = rec or {}, [(f"   {_screen.pad(label, 5)}", "aux")], []
    by = {k: [r for r in rows if r.get("role") in ks] for k, ks in
          (("a", ("anchor",)), ("e", ("entity",)), ("v", ("attribute", "content")))}
    for a in by["a"]:
        res, k, _m = _screen.outcome(a)
        segs.append((f"{a.get('canonical') if a.get('node_id') else a.get('surface') or '—'} {SYM.get(res, '·')}", k))
    held = next((a for a in by["a"] if _screen.outcome(a)[0] == "그래프에 없음"), None)
    if held:
        segs.append((f" │ {_screen.outcome(held)[2]} → 행 보류(값 {len(by['e'])})", "orphan"))
        return fit(segs, width), subs
    for e in by["e"]:
        res, k, _m = _screen.outcome(e)
        segs.append((f" │ {e.get('field') or ''} {e.get('surface') or e.get('canonical') or '—'} {SYM.get(res, '·')}", k))
        if (e.get("llm") or {}).get("calls") or e.get("verdict") == "uncertain" or res == "그래프에 없음":
            subs.append(_sub(e))
    if by["v"]:
        outs = [_screen.outcome(v) for v in by["v"]]
        body = (f"값 {len(by['v'])}" if len(by["v"]) > VALS_MAX
                else " · ".join(f"{v.get('field')} {_flat(rec.get(v.get('field')))}" for v in by["v"]))
        worst = next((o for o in outs if o[0] != "붙음"), outs[0])
        segs.append((f" │ {body} " + "".join(dict.fromkeys(SYM.get(o[0], "·") for o in outs)), worst[1]))
    rel = (f" │ 관계 {len({edge_key(r, a) for r in rows for a in r.get('attached') or []})}", "aux")
    return fit(segs, width, rel), [_screen.cut(s, (width or _screen.term_width()) - 2) for s in subs]
