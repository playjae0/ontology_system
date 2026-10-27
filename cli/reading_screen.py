# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **판독 표**(B156 ③) — `--step`의 구조 관문(PPT는 덱 표 다음 · PDF는 그 자리)에서 쪽마다 한 줄을 보이고 묻는다.

    번호(쪽) · 슬라이드 · 쪽 요약 앞부분 · 그림 · 관계 · 버림 · 상태(부름 · 재사용 · 출처 · 건너뜀 · 지움 · 사람 힌트)
    `c` 계속 · `q` 멈춤 · `<번호> 다시 <힌트>`(그 장만 힌트를 넣어 다시 판독 — 힌트는 보존 열쇠에 · 다른 장은 재사용) ·
    `<번호> 지움`(그 장 판독을 쓰지 않는다 — 봉투에 지움 표시)

고침은 `registry/structure_fixes.json`의 `@판독` 프레임(덱 고침 `@덱`과 같은 파일 · 같은 꼴 — 재파싱 · 재구축이 재생) → 다시 파싱.
`--split-only --step`이면 판독까지 보고 고친 뒤 구조까지에서 멈춘다(추출 0 · 그래프 쓰기 0).
"""
from __future__ import annotations

from cli import _screen
from cli import reading_md as RM

PROMPT = "   [계속 c / 멈춤 q / 고침 <번호> 다시 <힌트> · <번호> 지움] "
HELP = ("   c(ㅊ)는 계속 · q(ㅂ)는 멈춤 · 고침은 「<번호> 다시 <힌트>」(그 장만 힌트를 넣어 다시 읽는다 — 다른 장은 재사용) · "
        "「<번호> 지움」(그 장 판독을 쓰지 않는다) — 번호는 표의 쪽 번호 · 다시 친다")


def _state(e):
    if e.get("deleted"):
        return "지움(사람)"
    if e.get("skipped"):
        return f"건너뜀 — {e['skipped']}"
    s = ("재사용" if e.get("reused") else "부름") + f" · {e.get('source') or '—'}"
    return s + (f" · 힌트 「{e['hint'][:20]}」" if e.get("hint") else "") + (" · 실패" if e.get("failed") else "")


def print_table(env):
    """판독 표 — 쪽마다 한 줄(봉투의 판독 블록 그대로)."""
    t = _screen.Table([("번호", 4, True), ("슬라이드", 8, True), ("쪽 요약", 40, False), ("그림", 4, True), ("관계", 4, True),
                       ("버림", 4, True), ("상태", 26, False)], flex=2, keep=(6,))
    for e in RM.pages(env):
        t.row([e["page"], e.get("slide") or "", RM.short(e), len(e.get("figures") or []), len(e.get("relations") or []),
               sum((e.get("dropped") or {}).values()), _state(e)],
              [None, "aux", None, None, None, "warn" if e.get("dropped") else "aux",
               "warn" if e.get("deleted") or e.get("failed") else "aux"])
    t.end()
    print("   쪽 요약 — 판독이 낸 2~3문장의 앞부분(근거 상자 id는 md) · 전문은 export/split_<doc_id>.md의 [판독] · "
          "추출 · 그래프는 판독을 쓰지 않는다(메타 — 나란히 보는 자리)")


def parse_fix(answer, env):
    """판독 고침 → `(쪽 번호, 고침)` · 못 읽으면 None. 번호는 판독 표의 쪽 번호(판독 블록에 있는 쪽만)."""
    from parser.reading import AGAIN, DELETE
    toks = answer.split()
    if len(toks) < 2 or not toks[0].isdigit():
        return None
    page = int(toks[0])
    if RM.entry(env, page=page) is None:
        return None
    if toks[1] == DELETE and len(toks) == 2:
        return page, {"action": DELETE}
    if toks[1] == AGAIN and len(toks) > 2:
        return page, {"action": AGAIN, "hint": " ".join(toks[2:])}
    return None


def gate(res, doc_id, reparse):
    """판독 표를 보이고 묻는다 — `(res, 계속?)` · 고치면 기록하고 다시 파싱한다(그 장만 다시 · 다른 장 LLM 0)."""
    from core.build import reading as RD
    from core.build import structure as ST
    while True:
        print_table(res.envelope or {})
        _screen.say("   " + _screen.branch_line("쪽 판독", doc_id), "aux")      # 판독 갈래의 사용량 · 누계
        got = _screen.answer(PROMPT, "go", eof=True, other=lambda a: parse_fix(a, res.envelope or {}), hint=HELP)
        if got is True or got is False:
            if got is False:
                print("   멈춤 — 판독까지(파싱 산출 parsed/ · 판독 보존분은 남았다 · 그래프 쓰기 0)")
            return res, got
        page, fix = got
        RD.record_fix(doc_id, page, fix)
        print(f"   고침 — 쪽 {page} {fix['action']}" + (f" 「{fix['hint']}」" if fix.get("hint") else "")
              + f" · 기록 {ST.fixes_path().name}(@판독) · 다시 파싱한다(그 장만 다시 · 다른 장 재사용)")
        res = reparse()
        if not res.ok:
            return res, False
