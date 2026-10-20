# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 표 · 구조 관문** — LLM이 세운 문서 구조를 보이고, 사람이 줄 번호로 고친다 (B119 ③).

    파싱 끝 (산문 · 구조가 섰을 때)
      ├ 약한 구조 신호 — 늘 크게(`[약한 구조]`) · 비대화형이면 기록(인입 기록 · `show summary`)에 남기고 진행
      └ `--step`이면 구조 표(번호 · 시트 · 행 · 단 · 역할 · 대상 · 줄 · 초안과 다름)를 보이고 묻는다
          `c` 계속 · `q` 멈춤 · 고침 `<번호> <카테고리>`(대상 + 그 카테고리) · `<번호> 묶음` · `<번호> 주제` · `<번호> 본문`
          → 고침은 `registry/structure_fixes.json`(등록 단 — 사람 판단 · 재생성 불가) → 같은 문서를 다시 파싱(LLM 0 —
            구조 보존분 위에 고침을 덮는다) → 표를 다시 보인다. 재구축도 같은 고침을 쓴다.

명령은 짧게(사내는 복붙이 안 된다) — 이름은 줄 글자에서 번호를 뗀 것 · `<번호> 대상`이면 카테고리는 같은 역할의 다른 줄이 쓴 것.

**덱 구조 표**(PPT — B125 ③): 번호 · 슬라이드 · 제목 · 초안(placeholder) · 이어짐 · 다루는 공정 · 언급 · 고침 `<번호> 공정 <a,b|없음>` ·
`<번호> 제목 <글>` · `<번호> 이어짐 <슬라이드|없음>` · `개요 <글>` → 같은 기록 파일의 `@덱` 프레임 → 다시 파싱(LLM 0).
"""
from __future__ import annotations

from cli import _screen
from core.build import structure as ST
from parser import struct_map
from parser.struct_rule import BODY, ROLES, TARGET_ROLES

PROMPT = "   [계속 c / 멈춤 q / 힌트 <글> · 새로 · 고침 <번호> <카테고리|묶음|주제|본문>] "
DECK_PROMPT = "   [계속 c / 멈춤 q / 고침 <번호> 공정 <a,b|없음> · <번호> 제목 <글> · <번호> 이어짐 <슬라이드|없음> · 개요 <글>] "
DECK_HELP = ("   c(ㅊ)는 계속 · q(ㅂ)는 멈춤 · 고침은 「<번호> 공정 노칭,스태킹」(골격 이름 · 없음) · 「<번호> 제목 <그 슬라이드 글>」 · "
             "「<번호> 이어짐 <앞 슬라이드 번호|없음>」 · 「개요 <한 단락>」 — 다시 친다")
HELP = ("   c(ㅊ)는 이 시트 확정 · q(ㅂ)는 멈춤 · 그 밖의 글은 **힌트**(그 시트를 앞 출력 + 힌트로 다시 묻는다) · 「새로」는 llm 방식으로 "
        "다시 · 줄 고침은 「<번호> <카테고리>」 · 「<번호> " + "」 · 「<번호> ".join([r for r in ROLES if r not in TARGET_ROLES] + [BODY])
        + "」 — 다시 친다")


def weak_lines(weak):
    return [f"   [약한 구조] 시트 '{fr}' — " + " · ".join(sig) for fr, sig in (weak or {}).items()]


def _target(r):
    if r.get("이름") and r.get("카테고리"):
        return f"{r['이름']}({r['카테고리']})"
    return "—"


def print_table(rows):
    t = _screen.Table([("번호", 4, True), ("시트", 14, False), ("행", 5, True), ("단", 3, True), ("역할", 10, False),
                       ("대상", 28, False), ("줄", 40, False), ("초안", 10, False)], flex=6, keep=(4, 5))
    for r in rows:
        diff = (("다름 " if r.get("다름") else "") + (f"초안{r['초안']} " if r.get("초안") else "")
                + (f"형제 「{r['형제']}」" if r.get("형제") else ""))
        role = "(본문)" if r.get("본문") else (r.get("역할") or "—") + ("*" if r.get("by") else "")
        t.row([r["번호"], r["시트"], r["행"] if r["행"] else "시트", r["단"] or "", role, _target(r), r.get("글") or "",
               diff.strip()], [None, None, "aux", "aux", "warn" if r.get("by") else None, None, "aux",
                               "warn" if r.get("다름") else "aux"])
    t.end()
    print("   * = 사람이 고친 줄 · 다름 = 고정 규칙 초안의 단과 다르다(초안n = 초안의 단 · (본문) = 초안은 제목인데 구조가 뺐다) · "
          "형제 「꼴」 = 같은 번호 꼴 줄의 단 · 역할이 갈렸다")


def parse_fix(answer, rows, cats):
    """`<번호> <카테고리>` · `<번호> 대상 [카테고리]` · `<번호> 묶음|주제|본문` → `(행 표의 줄, 고침)` · 못 읽으면 None."""
    toks = answer.split()
    if len(toks) < 2 or not toks[0].isdigit():
        return None
    row = next((r for r in rows if r["번호"] == int(toks[0])), None)
    if row is None or not row["행"]:
        return None
    rest = " ".join(toks[1:])
    target = TARGET_ROLES[0]
    if rest in [r for r in ROLES if r not in TARGET_ROLES] + [BODY]:
        return row, {"role": rest}
    cat = rest if rest in cats else (" ".join(toks[2:]) or _likely_category(rows, target) if toks[1] == target else None)
    if cat not in cats:
        print(f"   카테고리를 친다 — 「{toks[0]} <카테고리>」 · 목록: {' · '.join(sorted(cats))}")
        return None
    return row, {"role": target, "name": struct_map.strip_number(row.get("글")), "category": cat}


def _likely_category(rows, role):
    """같은 역할의 다른 줄이 가장 많이 쓴 카테고리(없으면 대상이 있는 줄 전부에서)."""
    for pool in ([r for r in rows if r.get("역할") == role], rows):
        got = {}
        for r in pool:
            if r.get("카테고리"):
                got[r["카테고리"]] = got.get(r["카테고리"], 0) + 1
        if got:
            return max(sorted(got), key=lambda k: got[k])
    return None


def print_deck(rows):
    """덱 구조 표(B125 ③) — 슬라이드마다 한 줄 · `*` = 사람이 고친 칸이 있다."""
    t = _screen.Table([("번호", 4, True), ("슬라이드", 8, True), ("제목", 30, False), ("초안", 20, False), ("이어짐", 6, True),
                       ("다루는 공정", 22, False), ("언급", 16, False)], flex=2, keep=(5,))
    for r in rows:
        ps = r.get("공정")
        t.row([r["번호"], r["슬라이드"], (r.get("제목") or "—") + ("*" if r.get("by") else ""),
               "" if r.get("제목") == r.get("초안") else (r.get("초안") or "(없음)"),
               r.get("이어짐") or "", ("(개체 없음) " if r.get("개체없음") else "")
               + ("—" if ps is None else (" · ".join(ps) or "없음")), " · ".join(r.get("언급") or [])],
              [None, "aux", "warn" if r.get("by") else None, "aux", "aux", None, "aux"])
    t.end()
    print("   초안 = placeholder 제목(덱 구조와 같으면 비운다) · 다루는 공정 — = 판정 없음(지금 방식 — 경로 · 문서 좌표) · * = 사람이 고쳤다")


def parse_deck_fix(answer, rows):
    """덱 고침 → `(슬라이드 번호 · 0 = 덱 개요, 고침)` · 못 읽으면 None. 공정은 골격 닫힌 목록 안이어야 한다."""
    toks = answer.split()
    if len(toks) >= 2 and toks[0] == "개요":
        return 0, {"overview": " ".join(toks[1:])}
    if len(toks) < 3 or not toks[0].isdigit():
        return None
    row = next((r for r in rows if r["번호"] == int(toks[0])), None)
    rest = " ".join(toks[2:])
    if row is None:
        return None
    if toks[1] == "제목":
        return row["슬라이드"], {"title": rest}
    if toks[1] == "이어짐":
        if rest == "없음":
            return row["슬라이드"], {"continues": None}
        return (row["슬라이드"], {"continues": int(rest)}) if rest.isdigit() and int(rest) < row["슬라이드"] else None
    if toks[1] == "공정":
        names = [] if rest == "없음" else [x.strip() for x in rest.replace("·", ",").split(",") if x.strip()]
        from core.build import deck as DK
        _nodes, idx = DK._closed()
        canon = [DK._canon(x, idx) for x in names]
        if any(c is None for c in canon):
            print("   골격 밖 공정 — " + " · ".join(x for x, c in zip(names, canon) if c is None) + " (골격 이름을 친다)")
            return None
        return row["슬라이드"], {"processes": canon}
    return None


def _deck_gate(res, doc_id, dk, reparse):
    """덱 구조 표를 보이고 묻는다 — `(res, 계속?)` · 고치면 기록하고 다시 파싱한다(LLM 0 — 보존분 위에 고침)."""
    from core.build import deck as DK
    while True:
        print_deck(dk.get("표") or [])
        got = _screen.answer(DECK_PROMPT, "go", eof=True, other=lambda a: parse_deck_fix(a, dk.get("표") or []),
                             hint=DECK_HELP)
        if got is True or got is False:
            if got is False:
                print("   멈춤 — 덱 구조까지(파싱 산출 parsed/ · 덱 구조 보존분은 남았다 · 그래프 쓰기 0)")
            return res, got
        slide, fix = got
        DK.record_fix(doc_id, slide, fix)
        print(f"   고침 — " + ("덱 개요" if slide == 0 else f"슬라이드 {slide}") + f" {', '.join(fix)} · "
              f"기록 {ST.fixes_path().name} · 다시 파싱한다(LLM 0)")
        res = reparse()
        if not res.ok:
            return res, False
        dk = (res.report or {}).get("deck") or {}


def _is_fix(answer, cats):
    """줄 고침 명령인가(옛 꼴 — `<번호> <카테고리|대상|묶음|주제|본문>`) — 아니면 힌트다(B126 ③)."""
    toks = answer.split()
    return (len(toks) >= 2 and toks[0].isdigit()
            and (" ".join(toks[1:]) in [r for r in ROLES if r not in TARGET_ROLES] + [BODY]
                 or " ".join(toks[1:]) in cats or toks[1] == TARGET_ROLES[0]))


def _sheet_answer(answer, rows, cats):
    a = answer.strip()
    if not a:
        return None
    if a == "새로":
        return "new", None
    if _is_fix(a, cats):
        got = parse_fix(a, rows, cats)
        return ("fix", got) if got else None
    return "hint", a


def _print_sheet(name, fr, res, rows, st):
    from cli import split_report as SR
    blk = SR.sheet_block(name, fr, SR.chunks_of(res.envelope, name))
    _screen.say("   ── 구조 확인 — " + blk[0], "head")
    for ln in blk[1:]:
        print("   " + ln)
    if rows:
        print_table(rows)
    for ln in ST.range_lines(st):                    # 청크 구간 · 버린 사유 (B124 ②)
        if f"'{name}'" in ln:
            print(ln)


def gate(res, doc_id, reparse, *, ask=True, layers=None):
    """파싱 끝의 **구조 확인**(B126 ③) — `(res, 계속?)`. `--step`이면 시트마다 전부 보이고(준 것 · LLM 판단과 이유 · 고친 뒤 나무 ·
    청크마다 첫 줄 · 끝 줄 · 사슬 — 같은 내용을 `export/split_<doc_id>.md`에) 묻는다: `c` 이 시트 확정(기록 → 재구축 재생) → 다음
    시트 · `q` 멈춤 · 힌트 → 그 시트를 같은 방식으로 다시(앞 출력 + 힌트 전부) · `새로` → llm 방식으로 다시 · 옛 줄 고침도 받는다.
    확정 기록으로 재생된 시트에 힌트 · `새로`를 주면 그 고리 동안 확정을 비켜 둔다(B127 ③ — 입력의 힌트 = 기록된 힌트 + 이번 힌트)."""
    from core.state.bootstrap import coord_layer
    coord_in = coord_layer() in (layers or [coord_layer()])
    try:
        return _gate_loop(res, doc_id, reparse, ask, layers, coord_in)
    finally:
        ST.SUSPENDED.difference_update({k for k in ST.SUSPENDED if k[0] == doc_id})   # 비켜 둔 확정은 고리 밖으로 새지 않는다


def _gate_loop(res, doc_id, reparse, ask, layers, coord_in):
    from cli import split_report as SR
    from parser.struct_rule import labels_hash
    pos, hints = 0, {}
    while True:
        if not res.ok:                       # 고친 뒤 다시 파싱이 실패했다 — 진행하지 않는다
            print("   다시 파싱 실패 — " + "; ".join(f["reason"] for f in res.failures)[:200])
            return res, False
        st = (res.report or {}).get("structure")
        dk = (res.report or {}).get("deck")
        if dk and not st:                    # PPT — 덱 구조 표 (B125 ③)
            return _deck_gate(res, doc_id, dk, reparse) if ask else (res, True)
        if not st:
            return res, True
        weak = ST.weak(st, (res.envelope or {}).get("chunks") or [], coord_in)
        if pos == 0:
            for ln in weak_lines(weak):
                _screen.say(ln, "warn")
        res.envelope.setdefault("context", {})["structure"] = {**ST.counts(st), "약한": weak}
        frames = list(st.get("프레임") or {})
        if not ask or pos >= len(frames):
            return res, True
        name = frames[pos]
        fr = st["프레임"][name]
        rows = [r for r in ST.table(st) if r["시트"] == name]
        _print_sheet(name, fr, res, rows, st)
        md = SR.write_md(doc_id, res.report, res.envelope)
        cats = ST.categories(ST._cfgs(layers))
        got = _screen.answer(PROMPT, "go", eof=True, other=lambda a: _sheet_answer(a, rows, cats), hint=HELP)
        if got is False:
            print("   멈춤 — 구조까지(파싱 산출 parsed/ · 구조 보존분은 남았다 · 그래프 쓰기 0)")
            return res, False
        if got is True:
            if not fr.get("confirmed"):              # 확정 기록 재생 그대로면 다시 쓰지 않는다
                ST.confirm(doc_id, name, {**fr, "labels": labels_hash(fr.get("labels") or [])}, hints.get(name))
            ST.SUSPENDED.discard((doc_id, name))
            print(f"   확정 — 시트 '{name}' · 기록 {ST.confirmed_path().name} · md {md.name if md else '-'}"
                  + (f" · 다음 시트 '{frames[pos + 1]}'" if pos + 1 < len(frames) else ""))
            pos += 1
            continue
        kind, val = got
        if kind == "fix":
            row, fix = val
            ST.record_fix(doc_id, row["시트"], row["행"], fix)
            print(f"   고침 — {row['시트']} {row['행']}행 → {fix['role']}"
                  + (f" '{fix['name']}'({fix['category']})" if fix.get("name") else "")
                  + f" · 기록 {ST.fixes_path().name} · 다시 파싱한다(LLM 0)")
            res = reparse()
            continue
        hs = hints.setdefault(name, list(fr.get("hints") or []) if fr.get("confirmed") else [])   # 기록된 힌트 + 이번 힌트
        if kind == "hint":
            hs.append(val)
        if fr.get("confirmed"):              # 확정한 시트에 다시 힌트 — 이 고리에서는 확정을 비켜 둔다(B127 ③)
            ST.SUSPENDED.add((doc_id, name))
            print(f"   확정 기록을 비켜 둔다 — 시트 '{name}'(c면 새 나무로 덮는다 · q면 그대로)")
        print(f"   {'새로(llm 방식)' if kind == 'new' else '힌트'} — 시트 '{name}'를 다시 묻는다(앞 출력 + 힌트 {len(hs)})")
        ST.reask(doc_id, name, fr.get("labels") or [], (res.envelope or {}).get("source_path"), hints=hs,
                 prev=fr.get("answer") or {"headings": fr.get("headings")},
                 mode="llm" if kind == "new" or fr.get("mode") == "llm" else None,
                 layers=layers, ctx={"doc_type": (res.envelope or {}).get("doc_type"),
                                     "doc_coord": (res.envelope or {}).get("doc_coord"), "frames": frames})
        res = reparse()
