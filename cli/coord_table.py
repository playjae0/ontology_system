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


# ── 표 판정 화면 — 판별 단위 묶음을 그룹 끝에 한 번 (B212 ①) · 관계 한 번 (B208 ②) ─────────────────


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


def _short(c, sep):
    return str(c or "—").rsplit(sep, 1)[-1]


class JudgeTable:
    """**표 판정 화면**(B212 ①) — 판정 중엔 행마다 줄 0 · 그룹 끝에 그 그룹에서 정한 것을 **판별 단위**(같은 열 · 같은 표기 · 같은 자리)로
    묶어 넷: LLM이 판단한 것 → 사람이 정할 것 → 새로 선 것(관문 끝 — 행 많은 순 앞 5 · 전부는 `export/judge_<doc>.md` · `-v`면 화면도) →
    사전으로 붙은 것(열마다 수). 한 줄 = 열 · 표기 → 판정 → 붙은 노드 [부모 경로] → 엣지(앞 3 · 외 k) → 행 수(첫 행) · 단위의 갈래는
    그 그룹 첫 행의 판단(`decision`)이고 같은 단위의 뒤 행(사전 히트)은 행 수에 든다. 재료는 대장 행뿐(새 판정 0)."""
    KINDS = (("LLM", "LLM이 판단한 것"), ("사람", "사람이 정할 것"), ("관문 끝", "새로 선 것"))

    def __init__(self, doc_id, label, verbose):
        from core.state import catalog
        self.doc, self.label, self.verbose, self.sep, self.rows, self.md = doc_id, label, verbose, catalog.sep(), [], []

    def add(self, row):
        self.rows.append(row)

    def _units(self, rows):
        held = {r.get("locator") for r in rows if r.get("role") == "anchor" and decision(r)}
        coord = {r.get("locator"): _name(r) for r in rows if r.get("role") == "anchor"}
        units = {}
        for r in rows:
            if (r.get("role") == "anchor" and r.get("locator") in held) or (r.get("role") == "entity" and r.get("locator") not in held):
                k = (r.get("role"), r.get("field"), r.get("surface"), r.get("target") or r.get("canonical"))
                u = units.setdefault(k, {"r": r, "rows": [], "coord": coord.get(r.get("locator"))})
                u["rows"].append(r)
        kind = {"LLM": "LLM", "관문 끝": "관문 끝", None: "사전"}
        return {k: dict(u, kind=kind.get(decision(u["r"]), "사람")) for k, u in units.items()}, held

    def _line(self, u):
        from parser.coord_rows import VERDICT
        r, n = u["r"], len(u["rows"])
        tail = f"행 {n:,} (첫 {self.label(r.get('locator'))})"
        if r.get("role") == "anchor":
            return f"      공정 표기  {r.get('surface')}  {_screen.outcome(r)[2]}   {tail}"
        conf, near = r.get("confidence") or 0, (r.get("nearest") or {}).get("canonical")
        how = {"LLM": f"{VERDICT.get(r.get('verdict'), r.get('verdict'))[4:]} {conf:.2f} · 후보 {r.get('candidates_n') or 0}",
               "사람": (f"애매 {conf:.2f} · 후보 {r.get('candidates_n') or 0}" + (f"({near})" if near else "") + " → 보류"
                      if r.get("verdict") == "uncertain" else f"{_screen.outcome(r)[2] or decision(r)}"),
               "관문 끝": "관문 끝"}.get(u["kind"], "")
        c = r.get("target") or r.get("canonical")
        path = c.rsplit(self.sep, 1)[0] if c and self.sep in c else u["coord"]
        node = (("새로 " if r.get("verdict") in ("new", "uncertain") else "") + _short(c, self.sep)
                + (f" [{' › '.join(str(path).split(self.sep))}]" if path else "")) if c else "—"
        es = list(dict.fromkeys(f"{a['rel']} {a['dir']} {_short(a['other'], self.sep)}" for x in u["rows"] for a in x.get("attached") or []))
        edges = " · ".join(es[:3]) + (f" 외 {len(es) - 3}" if len(es) > 3 else "")
        return f"      {r.get('field')}  {r.get('surface')} → {how} → {node}   {edges}   {tail}"

    def _say(self, line):
        import sys
        print(_screen.cut(line, _screen.term_width() - 1) if sys.stdout.isatty() else line)

    def end(self, *_a):
        """그룹 · 문서 끝 — 판별 단위 묶음 넷(빈 갈래는 줄 0) · 새로 선 것은 md에 쌓아 다시 쓴다."""
        from collections import Counter
        rows, self.rows = self.rows, []
        units, held = self._units(rows)
        if not units:
            return
        by = {k: sorted((u for u in units.values() if u["kind"] == k), key=lambda u: -len(u["rows"])) for k in ("LLM", "사람", "관문 끝", "사전")}
        self._say(f"   판정 묶음 — 행 {len({r.get('locator') for r in rows}):,} · 항목 {sum(1 for r in rows if r.get('role') == 'entity'):,} · "
                  + f"LLM {len(by['LLM']):,} · 사람 {len(by['사람']):,} · 새로 {len(by['관문 끝']):,} · 사전 {sum(len(u['rows']) for u in by['사전']):,}")
        for k, title in self.KINDS:
            if not by[k]:
                continue
            lines = [self._line(u) for u in by[k]]
            self._say(f"   ── {title} {len(lines):,}" + (" (관문으로 끝 · LLM 0)" if k == "관문 끝" else ""))
            if k != "관문 끝" or self.verbose:
                for ln in lines:
                    self._say(ln)
            else:
                cnt = Counter(u["r"].get("field") for u in by[k])
                self._say("      " + " · ".join(f"{f} {n}" for f, n in cnt.items()) + " — 행 많은 순: "
                          + " · ".join(ln.split(" → ")[2].split("   ")[0].replace("새로 ", "") + f" {len(u['rows'])}"
                                       for ln, u in zip(lines[:5], by[k])) + "  전부 — md")
            if k == "관문 끝" and self.doc:
                self.md += lines
                from cli import envelope_md
                envelope_md.save(f"judge_{self.doc}.md", f"# 새로 선 것 — {self.doc}\n\n" + "\n".join(f"- {x.strip()}" for x in self.md) + "\n")
        if by["사전"]:
            cnt = Counter(u["r"].get("field") for u in by["사전"] for _ in u["rows"])
            self._say(f"   ── 사전으로 붙은 것 {sum(cnt.values()):,} (줄 없음 — " + " · ".join(f"{f} {n:,}" for f, n in cnt.items()) + ")")


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
