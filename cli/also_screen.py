# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 단의 화면**(B197 ②③④) — 문에 걸린 겸 값의 표와 처분 · 확정한 공정 줄 · 쌍별 예고 · 쓰기 전 판정 결과.

core는 사실만 낸다(`core/build/entry.heading_gate` · `_notice_plan` · `_pre_write`의 `notice`) — 화면이 그리고 `--step`이면 묻는다.
처분은 B196의 물음 함수 그대로(`cli.provisional_ask.decide` — 합침 · 새로 · 승격 · drop · 올림 `u`).
"""
from __future__ import annotations

import sys

from cli import _screen

#: 이 화면이 맡는 단계
STAGES = ("골격단", "확정공정", "판정결과")
#: 쓰기 전 판정 결과를 이 문서에서 물었나(물었으면 저장 뒤 [판정] 머리는 묻지 않는다)
ASKED = {"판정결과": False}


def rows_lines(rows, indent="     "):
    """문에 걸린 겸 값 — `번호. 자리 · 이름 · 카테고리 · 판단 · 후보 둘`(후보 = 그 위 공정 아래 골격 — 판단 후보 → 자식 종류 수 → 행 수)."""
    from core.build import skeleton_review as SR
    sk = SR._Sk()
    out = []
    for i, r in enumerate(rows, 1):
        r.setdefault("candidates", SR.candidates(sk, r["surface"], r.get("up_name"), r.get("near")))
        cands = " · ".join(f"{j}.{c['name']}(경로 {c['path']} · 행 {c['rows']} · 자식 {c['kinds']}종)"
                           for j, c in enumerate(r["candidates"], 1)) or "—"
        ans = {"uncertain": "애매", "new": "다르다"}.get(r.get("answer"), r.get("answer") or "—")
        out.append(f"{indent}{i}. 자리 {r.get('place') or '—'} · {r['surface']} · {r.get('also')} · 위 공정 {r.get('up_name')} · "
                   f"판단 {ans} · 후보 {cands}")
    return out


def ask_rows(rows):
    """처분 — 번호로(`m <줄> [후보|이름]` · `k <줄>` · `p <줄>` · `d <줄> <사유>` · `u <줄>`) → 계속 c / 멈춤 q."""
    from cli import provisional_ask as PA
    who = PA.actor()
    while True:
        got = _screen.answer(PA.GATE_PROMPT, "go", eof=True, other=PA._gate_cmd, hint=PA.GATE_HELP)
        if got is True or got is False:
            return got
        k, i, name = got
        if not 1 <= i <= len(rows):
            print(f"     {i}번이 목록에 없다")
            continue
        PA.decide(rows[i - 1], who, answer=f"{k} {name}".strip())


def gate_lines(rows, where):
    head = (f"   골격 단 — {where}의 겸 값 {len(rows):,}종이 문에 걸렸다(사람 확인 전 — 노드 0 · 그 아래 값도 보류 · "
            "처분은 합침 · 새로 · 승격 · drop · 올림)")
    return [head] + rows_lines(rows)


def notice(info, step=False):
    """골격 단 화면 — `False`면 멈춤."""
    k = info["단계"]
    if k == "골격단":
        for ln in gate_lines(info["rows"], info.get("자리") or "값"):
            _screen.say(ln, "warn" if ln.startswith("   골격") else None)
        if step and sys.stdin.isatty():
            return ask_rows(info["rows"])
        return None
    if k == "확정공정":
        _screen.say(f"   {info['줄']}", "head")
        return None
    if k == "판정결과":
        _screen.close()
        _screen.say(f"   판정 결과 — 쓰기 전{' (판정까지)' if info.get('판정까지') else ''} — "
                    f"match {info['합']['match']:,} · new {info['합']['new']:,} · uncertain {info['합']['uncertain']:,}"
                    + (f" · 문에 걸림 {info['합']['문']:,}" if info["합"]["문"] else ""), "head")
        for ln in info["줄"]:
            print(ln)
        if step and not info.get("판정까지") and sys.stdin.isatty():
            ASKED["판정결과"] = True
            print("   c는 쓴다(그 뒤 [부착·엣지] · [큐·요약] 그대로) · q는 쓰지 않고 멈춘다(그래프 0 · 판정은 대장 중간 저장 — 다시 넣으면 LLM 0)")
            go = _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True)
            if not go:
                print("   멈춤 — 쓰지 않았다(그래프 · 사전 · 큐 0 · 판정은 대장 중간 저장 — 같은 명령을 다시 치면 LLM 0)")
            return go
        return None
    return None


def plan_lines(info):
    """[5/8] 머리 아래 — 쌍별 예고(③) · 본문 값의 골격 단 문(②)."""
    from core.build import also_stage as AS
    out = []
    if info.get("쌍별"):
        out.append("   쌍별 예고 — 확정한 공정 쌍마다 값 · 붙을 자리 · 연결 · 판정 예정(쓰기 0 · LLM 0)")
        out += AS.preview_lines(info["쌍별"], indent="     ")
    if info.get("골격단"):
        out += gate_lines(info["골격단"], "본문")
    return out


def step8(info, step):
    """[5/8] 머리 아래 줄과 물음 — 쌍별 예고 · 골격 단 줄(처분 먼저) · 사람 후보(B140 — 다음) · `(줄, 물음 함수 또는 None)`."""
    from cli import human_gate
    hb = info.get("사람후보")
    rows = info.get("골격단") or []

    def ask():
        if rows and not ask_rows(rows):
            return False
        return human_gate.ask(hb) if hb else True
    return plan_lines(info) + (human_gate.lines(hb, step) if hb else []), (ask if (hb or rows) else None)


def asked_pop():
    """쓰기 전 판정 결과를 이 문서에서 물었나 — 읽고 지운다(다음 문서는 새로)."""
    v = ASKED.get("판정결과", False)
    ASKED["판정결과"] = False
    return v
