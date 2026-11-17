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


# ── 표 판정 화면 — 판단이 있었던 행만 한 줄의 표 (B211 ①) · 관계 한 번 (B208 ②) ───────────────────
#: 좌표 칸의 기호 · 개체 칸의 결과 기호(붙음 `=` · 새로 `+새` · 애매 `?` · 보류 `✗` — 결과 색 표의 결과 하나)
SYM = {"붙음": "✓", "새로 생김": "+", "그래프에 없음": "✗", "노드 아님": "↗"}
CELL = {"붙음": "=", "새로 생김": "+새", "그래프에 없음": "✗", "노드 아님": "↗"}
#: 줄을 찍는 판단(기본) — `-v`는 「관문 끝」(새로 — LLM 0)까지 · 개체 열 상한(넘으면 「개체 열 n 더」 한 줄)
LOUD, ENT_MAX = ("LLM", "사람 문", "애매", "보류"), 4


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


def decision(r):
    """그 칸에서 **정한 방법** — LLM · 사람 문 · 애매 · 보류 · 관문 끝(새로 — LLM 0) · 판단 아님(사전 · 경로 · 앞 행이 정한 표기)은 None."""
    if r.get("role") not in ("anchor", "entity"):
        return None
    if (r.get("llm") or {}).get("calls"):
        return "LLM"
    if r.get("by"):
        return "사람 문"
    if r.get("verdict") == "uncertain":
        return "애매"
    if _screen.outcome(r)[0] == "그래프에 없음":
        return "보류"
    return "관문 끝" if r.get("verdict") == "new" else None


def _cell(r):
    res, _k, mark = _screen.outcome(r)
    return f"{r.get('surface') or r.get('canonical') or '—'} {'?' if mark == _screen.REVIEW else CELL.get(res, '·')}"


def _flat(v, n=14):
    return _screen.cut(" ".join(str(v).split()), n) if v not in (None, "") else "—"


class JudgeTable:
    """**표 판정 화면**(B211 ①) — 판단이 있었던 행만 한 줄의 표(머리 · 열 정렬 · 그룹마다 머리 한 번) · 열 = 행 · 공정 · 스키마의
    개체 열 차례 · 값(attribute · content 열의 실제 값) · 판단 · 기본은 LLM · 사람 문 · 애매 · 보류가 있는 행 · `-v`는 + 관문 끝 ·
    전부 사전인 행은 줄 0(그룹 끝 수) · LLM · 애매 · 보류 칸만 그 행 아래 `└`. 재료는 대장 행 · 봉투 레코드뿐(새 판정 0)."""

    def __init__(self, fields, recs, label, verbose):
        self.fields, self.recs, self.label, self.verbose = list(fields)[:ENT_MAX], recs, label, verbose
        self.more, self.loc, self.rows, self.t = max(0, len(fields) - ENT_MAX), None, [], None
        self.n = {"판단": 0, "사전": 0, "LLM": 0}

    def add(self, row):
        if row.get("locator") != self.loc:
            self._done()
            self.loc = row.get("locator")
        self.rows.append(row)

    def end(self, *_a):
        """그룹 · 문서 끝 — 남은 행 · 그룹 끝 수 한 줄 · 다음 그룹은 머리부터."""
        self._done()
        if any(self.n.values()):
            print(f"   [그룹 끝] 판단 있는 행 {self.n['판단']:,} · 사전으로만 붙은 행 {self.n['사전']:,}(줄 없음) · LLM {self.n['LLM']:,}")
        self.n, self.t = {k: 0 for k in self.n}, None

    def _done(self):
        rows, self.rows = self.rows, []
        ds = [d for d in map(decision, rows) if d]
        self.n["LLM"] += ds.count("LLM")
        self.n["판단" if ds else "사전"] += bool(rows)
        if ds and (self.verbose or any(d in LOUD for d in ds)):
            self._print(rows, ds)

    def _print(self, rows, ds):
        from collections import Counter
        anchors = [r for r in rows if r.get("role") == "anchor"]
        held = next((a for a in anchors if _screen.outcome(a)[0] == "그래프에 없음"), None)
        proc = " · ".join(f"{_name(a)} {SYM.get(_screen.outcome(a)[0], '·')}" for a in anchors) or "—"
        if self.t is None:
            cols = [("행", 6, False), ("공정", 14, False)] + [(f, 18, False) for f in self.fields or ["개체"]]
            self.t = _screen.Table(cols + [("값", 24, False), ("판단", 14, False)], flex=len(cols))
            if self.more:
                print(f"   (개체 열 {self.more} 더 — show report <doc_id> --md)")
        ents, rec = [r for r in rows if r.get("role") == "entity"], self.recs.get(self.loc) or {}
        cells = ([" · ".join(_cell(r) for r in ents if r.get("field") == f) for f in self.fields] if self.fields
                 else [" · ".join(map(_cell, ents))])
        vals = " · ".join(f"{r.get('field')} {_flat(rec.get(r.get('field')))}" for r in rows if r.get("role") in ("attribute", "content"))
        if held:
            cells, vals = [""] * len(cells), f"— {_screen.outcome(held)[2]} → 행 보류(값 {len(ents)})"
        self.t.row([self.label(self.loc), proc, *cells, vals, " · ".join(f"{k} {n}" for k, n in Counter(ds).items())],
                   ["aux", _screen.outcome(anchors[0])[1] if anchors else None] + [None] * (len(cells) + 2))
        for r in ([] if held else ents):
            if decision(r) in LOUD:
                print(_screen.cut(_sub(r), _screen.term_width() - 2))


def _name(a):
    return (a.get("canonical") if a.get("node_id") else a.get("surface")) or "—"


def split_info(records):
    """**원본 행 → 나눈 행**(위치의 `#n` 접미로 센다) — `(원본 수, 나눈 수, 나눈 열들)` · 나눈 열 = 같은 원본의 형제끼리 값이 다른 칸."""
    sib = {}
    for r in records or []:
        sib.setdefault(str(r.get("source_locator") or "").split("#")[0], []).append(r)
    cols = {f for rs in sib.values() if len(rs) > 1 for f in rs[0] if f != "source_locator" and isinstance(rs[0][f], str)
            and len({str(x.get(f)) for x in rs}) > 1}
    return len(sib), len(records or []), sorted(cols)
