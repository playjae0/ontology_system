# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 확인** — 계층 사다리 · 목차 · 판단 필요와 답을 보이고, 사람이 **사다리 고침 · 행 고침**을 힌트로 준다 (B119 ③ · B130 ③④ · B132 ⑦).

    파싱 끝 (산문 · 구조가 섰을 때)
      ├ 약한 구조 신호 — 늘 크게(`[약한 구조]`) · 비대화형이면 기록(인입 기록 · `show summary`)에 남기고 진행
      └ `--step`이면 시트마다 사다리 한 줄 · 들여쓰기 목차(역할 · 바뀐 줄) · 판단 필요와 LLM의 답 · 사다리 고침(적용 n줄 / 전체 m줄) ·
        청크마다 전체 경로를 보이고 묻는다: `c` 확정 · `q` 멈춤 · 힌트(문서 규칙 — 「가.는 9) 위다」 · 「가. 단은 대상 Unit」 같은 사다리
        고침은 문서 전체에 다시 · 「R36은 제목이 아니다」 같은 행 고침)

줄 고침 명령은 받지 않는다 — 옛 고침 기록(`registry/structure_fixes.json` — 등록 단)은 파싱 · 재구축이 그대로 재생한다.

**덱 구조 표**(PPT — B125 ③ · B151 ④): 번호 · 슬라이드 · 제목 · 초안(placeholder) · 이어짐 · 다루는 것 · 공정(문서 표기 → 골격) · 고침
`<번호> 공정 <a,b|없음>`(문서 표기 — 덱 글 안) · `<번호> 다루는 것 <글>` · `<번호> 제목 <글>` · `<번호> 이어짐 <슬라이드|없음>` · `개요 <글>`
→ 같은 기록 파일의 `@덱` 프레임 → 다시 파싱(LLM 0).
"""
from __future__ import annotations

from cli import _screen
from core.build import structure as ST
from core.llm import gateway

PROMPT = "   [계속 c / 멈춤 q / 힌트 <글>] "
DECK_PROMPT = ("   [계속 c / 멈춤 q / 고침 <번호> 공정 <a,b|없음> · <번호> 다루는 것 <글> · <번호> 제목 <글> · "
               "<번호> 이어짐 <슬라이드|없음> · 개요 <글>] ")
DECK_HELP = ("   c(ㅊ)는 계속 · q(ㅂ)는 멈춤 · 고침은 「<번호> 공정 <표기>,<표기>」(덱에 적힌 표기 그대로 · 없음) · 「<번호> 다루는 것 <말>」 · "
             "「<번호> 제목 <그 슬라이드 글>」 · 「<번호> 이어짐 <앞 슬라이드 번호|없음>」 · 「개요 <한 단락>」 — 다시 친다")
HELP = ("   c(ㅊ)는 이 시트 확정 · q(ㅂ)는 멈춤 · 그 밖의 글은 **힌트 — 문서 규칙**(사다리 고침 「가.는 9) 위다」 · 「가. 단은 대상이다」 — "
        "LLM이 되말하고 문서 전체에 다시 세운다 / 행 고침 「R36은 제목이 아니다」) — 다시 친다")


def weak_lines(weak):
    return [f"   [약한 구조] 시트 '{fr}' — " + " · ".join(sig) for fr, sig in (weak or {}).items()]


def print_deck(rows, block=None):
    """덱 구조 표(B125 ③) — 슬라이드마다 한 줄 · 공정 칸은 덱 블록의 문서 표기 → 골격(md와 같은 손 `envelope_md.procs_cell`) ·
    `*` = 사람이 고친 칸이 있다."""
    from cli.envelope_md import procs_cell
    by = {s.get("slide"): s for s in (block or {}).get("slides") or []}
    t = _screen.Table([("번호", 4, True), ("슬라이드", 8, True), ("제목", 30, False), ("초안", 20, False), ("이어짐", 6, True),
                       ("다루는 것", 20, False), ("공정", 24, False)], flex=2, keep=(5,))
    for r in rows:
        s = by.get(r["슬라이드"]) or {"processes": r.get("공정")}
        t.row([r["번호"], r["슬라이드"], (r.get("제목") or "—") + ("*" if r.get("by") else ""),
               "" if r.get("제목") == r.get("초안") else (r.get("초안") or "(없음)"),
               r.get("이어짐") or "", ("(개체 없음) " if r.get("개체없음") else "") + (r.get("다루는것") or ""),
               procs_cell(s)],
              [None, "aux", "warn" if r.get("by") else None, "aux", "aux", None, None])
    t.end()
    print("   초안 = placeholder 제목(덱 구조와 같으면 비운다) · 공정 — 문서 표기 · `→` 골격에 맞음 · (?) 안 맞음(그래프 단계에서 "
          "해소 · 큐) · — = 판정 없음(경로 · 문서 좌표) · * = 사람이 고쳤다")


def parse_deck_fix(answer, rows, text=None):
    """덱 고침 → `(슬라이드 번호 · 0 = 덱 개요, 고침)` · 못 읽으면 None. 공정은 **문서 표기**이고 덱 글(`text` — `core.build.deck.deck_text`
    · 덱 판단의 검사와 같은 글 · 같은 정규화) 안이어야 한다(B151 ④ — 골격 검사 0)."""
    toks = answer.split()
    if len(toks) >= 2 and toks[0] == "개요":
        return 0, {"overview": " ".join(toks[1:])}
    if len(toks) < 3 or not toks[0].isdigit():
        return None
    row = next((r for r in rows if r["번호"] == int(toks[0])), None)
    if row is None:
        return None
    if toks[1:3] == ["다루는", "것"] and len(toks) > 3:
        return row["슬라이드"], {"subject": " ".join(toks[3:])}
    rest = " ".join(toks[2:])
    if toks[1] == "제목":
        return row["슬라이드"], {"title": rest}
    if toks[1] == "이어짐":
        if rest == "없음":
            return row["슬라이드"], {"continues": None}
        return (row["슬라이드"], {"continues": int(rest)}) if rest.isdigit() and int(rest) < row["슬라이드"] else None
    if toks[1] == "공정":
        names = [] if rest == "없음" else [x.strip() for x in rest.replace("·", ",").split(",") if x.strip()]
        from core.build import deck as DK
        out = [x for x in names if text is None or DK.in_text(x, text)]
        if len(out) < len(names):
            print("   덱 글에 없는 표기 — " + " · ".join(x for x in names if x not in out) + " (덱에 적힌 표기 그대로 친다)")
            return None
        return row["슬라이드"], {"processes": out}
    return None


def deck_text_of(env):
    """덱 고침 검사의 글 — 원본을 다시 읽어 덱 입력과 같은 글(`deck_input` → `deck_text` · LLM 0)."""
    from core.build import deck as DK
    from parser import deck as PD, reader
    try:
        return DK.deck_text(PD.deck_input(reader.read(str((env or {}).get("source_path")))))
    except Exception:                                    # noqa: BLE001 — 못 읽으면 검사 없이(사람의 고침)
        return None


def _deck_gate(res, doc_id, dk, reparse):
    """덱 구조 표를 보이고 묻는다 — `(res, 계속?)` · 고치면 기록하고 다시 파싱한다(LLM 0 — 보존분 위에 고침)."""
    from core.build import deck as DK
    text = deck_text_of(res.envelope)
    while True:
        print_deck(dk.get("표") or [], (res.envelope or {}).get("deck"))
        _screen.say("   " + _screen.branch_line("덱", doc_id), "aux")      # 덱 갈래의 사용량 · 누계 (B139 ⑤)
        got = _screen.answer(DECK_PROMPT, "go", eof=True, other=lambda a: parse_deck_fix(a, dk.get("표") or [], text),
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


def _sheet_answer(answer):
    """묻는 줄의 답 — 힌트(문서 규칙 · B130 ④ — 줄 고침 명령은 받지 않는다 · 옛 고침 기록은 재생된다)."""
    a = answer.strip()
    return ("hint", a) if a else None


def _print_sheet(name, fr, res):
    from cli import split_report as SR
    blk = SR.sheet_block(name, fr, SR.chunks_of(res.envelope, name))
    _screen.say("   ── 구조 확인 — " + blk[0], "head")
    for ln in blk[1:]:
        if SR.NEED_MARK in ln:                     # 판단 필요 줄 — 터미널일 때만 색(로그 · 파이프 · md는 표지) (B137 ⑥)
            _screen.say("   " + ln, "new")
        else:
            print("   " + ln)


def gate(res, doc_id, reparse, *, ask=True, layers=None):
    """파싱 끝의 **구조 확인**(B126 ③ · B132 ⑦) — `(res, 계속?)`. `--step`이면 시트마다 전부 보이고(사다리 · 목차 · 판단 필요와 답 ·
    고침 · 청크마다 첫 줄 · 끝 줄 · 경로 — 같은 내용을 `export/split_<doc_id>.md`에) 묻는다: `c` 이 시트 확정(기록 → 재구축 재생) →
    다음 시트 · `q` 멈춤 · 힌트 → 그 시트를 다시 확인(앞 판단 + 문서 힌트 전부 · 사다리 고침은 뒤 시트에도).
    확정 기록으로 재생된 시트에 힌트를 주면 그 고리 동안 확정을 비켜 둔다(B127 ③ — 입력의 힌트 = 기록된 힌트 + 이번 힌트)."""
    from core.state.bootstrap import coord_layer
    coord_in = coord_layer() in (layers or [coord_layer()])
    try:
        res, go = _gate_loop(res, doc_id, reparse, ask, layers, coord_in)
    finally:
        ST.SUSPENDED.difference_update({k for k in ST.SUSPENDED if k[0] == doc_id})   # 비켜 둔 확정은 고리 밖으로 새지 않는다
    if res.ok and go:
        md_of(doc_id, res)
    return res, go


def md_of(doc_id, res):
    """**구조 확인 md를 쓰는 한 자리**(B141 ① — `--step`이 아니어도 · 배치 · 재구축도 이 길) — 봉투에 구조 블록(엑셀 · Word) · 덱
    블록(PPT)이 있으면 봉투만 읽어 `export/split_<doc_id>.md`(`cli/envelope_md.write` — B143 ④ · B146 ②)와 그 자리 한 줄 · 블록이
    없으면(표 · 고정 규칙) 쓰지 않는다."""
    from cli import envelope_md as EM
    from core import paths
    md = EM.write(doc_id, res.envelope)
    if md:
        _screen.say(f"   구조 확인 md — {paths.show(md)}(목차 · 청크 경계 — 문서마다)", "aux")
    return md


def _gate_loop(res, doc_id, reparse, ask, layers, coord_in):
    from cli import envelope_md as EM, split_report as SR
    from parser.struct_rule import labels_hash
    pos, said = 0, False
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
        if ask and frames and not said:
            said = True
            _screen.say("   " + SR.ladder_usage(st), "aux")       # 사다리 단계의 사용량 — 한 번 (B137 ⑦)
            if SR.toc_field_line(st):
                print("   " + SR.toc_field_line(st))               # 거른 목차 필드 (B138 ③)
        if not ask or pos >= len(frames):
            if ask and frames:
                _screen.say("   " + SR.total_usage(st) + f" / {_screen.usage_pair()}", "aux")   # 문서 끝 구조 합계 · 누계 (B137 ⑦ · B139 ⑤)
            return res, True
        name = frames[pos]
        fr = st["프레임"][name]
        _print_sheet(name, fr, res)
        md = EM.write(doc_id, res.envelope)
        got = _screen.answer(PROMPT, "go", eof=True, other=_sheet_answer, hint=HELP)
        if got is False:
            print("   멈춤 — 구조까지(파싱 산출 parsed/ · 구조 보존분은 남았다 · 그래프 쓰기 0)")
            return res, False
        if got is True:
            if not fr.get("confirmed"):              # 확정 기록 재생 그대로면 다시 쓰지 않는다
                ST.confirm(doc_id, name, {**fr, "labels": labels_hash(fr.get("labels") or [])}, ST.doc_state(doc_id)["hints"])
            ST.SUSPENDED.discard((doc_id, name))
            print(f"   확정 — 시트 '{name}' · 기록 {ST.confirmed_path().name} · md {md.name if md else '-'}"
                  + (f" · 다음 시트 '{frames[pos + 1]}'" if pos + 1 < len(frames) else ""))
            pos += 1
            continue
        _kind, val = got
        ST.add_doc_hint(doc_id, val)         # 힌트는 문서 규칙 — 그 문서의 모든 시트에 (B130 ④)
        hs = ST.doc_state(doc_id)["hints"]
        if fr.get("confirmed"):              # 확정한 시트에 다시 힌트 — 이 고리에서는 확정을 비켜 둔다(B127 ③)
            ST.SUSPENDED.add((doc_id, name))
            print(f"   확정 기록을 비켜 둔다 — 시트 '{name}'(c면 새 나무로 덮는다 · q면 그대로)")
        print(f"   힌트(문서 규칙) — 시트 '{name}'를 다시 확인한다(앞 판단 + 문서 힌트 {len(hs)} · 사다리 고침은 뒤 시트에도)")
        u0 = gateway.usage_total()
        ST.reask(doc_id, name, fr.get("labels") or [], (res.envelope or {}).get("source_path"), hints=hs,
                 # 앞 판단 전체 — 고침 목록 · 고친 나무 · 이해한 규칙 (B130 ⑤ — 확정한 시트를 다시 열어도 앞 고침이 빠지지 않는다)
                 prev={"answers": (fr.get("answer") or {}).get("answers") or [],
                       "edits": (fr.get("answer") or {}).get("edits") or [], "headings": fr.get("headings") or [],
                       "rules": fr.get("rules") or []},
                 ctx={"doc_type": (res.envelope or {}).get("doc_type"),
                                     "doc_coord": (res.envelope or {}).get("doc_coord"), "frames": frames})
        res = reparse()
        _screen.say(f"   다시 확인 끝 — {_screen.usage_line(u0)}", "aux")     # 다시 확인 한 번의 사용량 · 누계 (B139 ⑤)
