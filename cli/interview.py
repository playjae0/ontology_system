# -*- coding: utf-8 -*-
"""칸 1.3 — 생성 전 **문답** — 이해 요약과 질문, 종료는 사람 (문서 6 §6.5 · B21·B32·B43).

등록 CLI에서 떼어냈다. 문답은 생성의 앞 단계이지 생성 자체가 아니다 —
스키마·라운드 규율·mock 대체가 한 덩어리로 여기 산다. 판정 어휘는 여기서 적지
않고 `cli/prompt._vocab_excerpt`가 조립한 것을 **붙여 받는다**(정본은 템플릿 하나).
"""
from __future__ import annotations

import json
import re

from core.llm import gateway
from cli import _screen
from cli.prompt import _sent_size, _vocab_excerpt
from parser.normalizer import _col

def _ask(prompt=""):
    """문답 입력 한 줄 — 묻는 한 자리(`_screen.answer`)를 지난다(B118 ④) · 테스트가 이 이름을 갈아끼운다(대화형이라
    파이프로는 못 잰다). 답이 없으면(EOF · Ctrl-C) `EOFError` — 묻는 자리마다의 처분(「진행」)으로 간다."""
    got = _screen.answer(prompt, "text", eof=None)
    if got is None:
        raise EOFError
    return got
_RULE = "   " + "─" * 56


def _pick_option(ans, options):
    """«1» · «1번» · «1)» · «1번으로 진행»처럼 **번호로 시작하는 답**을 선택지 본문으로 푼다.

    번호가 아니거나 범위 밖이면 None — 그때는 문장 그대로 답이다. 번호만 쳐도, 문장으로
    써도 통해야 한다(등록개선 ⑤-2).
    """
    m = re.match(r"\s*(\d+)\s*(번|\)|\.)?", ans or "")
    if not m:
        return None
    i = int(m.group(1))
    return options[i - 1] if options and 1 <= i <= len(options) else None


def _rank(q):
    """중요도 정렬 키 — 높음 → 중간 → 낮음 → 표시 없음. 번호는 정렬 뒤에 붙는다."""
    s = str(q.get("importance") or "")
    return 0 if s.startswith("높") else 1 if s.startswith("중") else 2 if s.startswith("낮") else 3


INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        # **진행 재료**(B43 ⑥) — 사람이 「이제 진행해도 되나」를 판단할 근거다.
        # LLM이 세지 않으면 라운드가 끝없이 이어져도 남은 양이 안 보인다.
        "progress": {
            "type": "object",
            "properties": {"columns": {"type": "integer"},
                           "decided": {"type": "integer"},
                           "undecided": {"type": "integer"},
                           "by_role": {"type": "string"}},
            "required": ["columns", "decided", "undecided", "by_role"],
            "additionalProperties": False,
        },
        # **이해 요약이 이 설계의 심장이다** — 사람이 판정하는 대상은 "질문에 다
        # 답했나"가 아니라 **"LLM의 이해가 맞아졌나"**다.
        "understanding": {"type": "string"},
        # **열마다 한 항목**(B215 ③ — 이해 요약의 열 줄 · 위 `understanding`은 전체 한두 문장)
        "reading": {"type": "array", "items": {
            "type": "object",
            "properties": {"column": {"type": "string"}, "header": {"type": "string"}, "how": {"type": "string"}},
            "required": ["column", "header", "how"], "additionalProperties": False}},
        # **열마다 판정**(B206 ④) — 라운드 화면의 열 표(살아남은 열 · 제외 한 줄 · 바뀐 열 ✎)
        "columns": {"type": "array", "items": {
            "type": "object",
            "properties": {"column": {"type": "string"}, "role": {"type": "string"},
                           "attach": {"type": ["string", "null"]}, "store_as": {"type": ["string", "null"]},
                           "context_type": {"type": ["string", "null"]}},
            "required": ["column", "role", "attach", "store_as", "context_type"],
            "additionalProperties": False}},
        # **열마다 확인**(B217 ① — 변형 · 개정 · 스키마만: 기억 열을 포함한 모든 열에 확인 · 수정 제안 + 근거 한 줄 · 그 밖이면 빈 목록)
        "checks": {"type": "array", "items": {
            "type": "object",
            "properties": {"column": {"type": "string"}, "verdict": {"type": "string", "enum": ["확인", "수정"]},
                           "proposal": {"type": ["string", "null"]}, "why": {"type": "string"}},
            "required": ["column", "verdict", "proposal", "why"], "additionalProperties": False}},
        "questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"q": {"type": "string"},
                           "options": {"type": "array", "items": {"type": "string"}},
                           # **중요도**(B43 ⑥) — 3개씩 무한정 나오면 끝이 안 보인다.
                           "importance": {"type": "string"}},
            "required": ["q", "options", "importance"],
            "additionalProperties": False}},
    },
    "required": ["progress", "understanding", "reading", "columns", "checks", "questions"],
    "additionalProperties": False,
}
#: 문답 열 표의 「뺀다」 role(지시문 1.3 — 맞출 칸 없음)
UNMAPPABLE = "unmappable"
#: 열 기억 어긋남 문턱 — 기억과 이번 표본의 빈 칸 비율 차가 이 값 이상이면 묻는다(사내 손잡이 `memory_blank_gap` · 창작 기본값)
MEMORY_BLANK_GAP = 0.1
#: 좌표 · 필수 열 빈 칸의 처분 셋(B217 ② — 앞의 둘은 코드가 빈 칸 꼴로 제안 · 셋째는 사람이 고를 때만)
FILL = ("이어받기", "필수", "상위로 붙임")


def mismatches(mem):
    """**어긋남은 코드가 판정한다**(B217 ① — LLM에 맡기지 않는다) — 기억 열마다 `{헤더: 이유(수)}`: anchor · 필수 열에 빈 칸이 생겼다 ·
    빈 칸 비율 차가 문턱 이상 · 고유값 수가 2배 이상 · 기준 양식의 헤더가 표본에 없다."""
    out, seen, old = {}, (mem or {}).get("seen") or {}, (mem or {}).get("old") or {}
    for h, m in ((mem or {}).get("cols") or {}).items():
        s, o = seen.get(h), old.get(h) or {}
        if s is None:
            if h in (mem.get("base") or []):
                out[h] = "기억의 헤더가 표본에 없다"
            continue
        must = "anchor" if str(m.get("role") or "").lower() == "anchor" else "필수" if m.get("field") in (mem.get("required") or []) else None
        if must and s["blank"] > 0 and not o.get("blank"):
            out[h] = f"{must} 열에 빈 칸이 생겼다(빈 칸 비율 {o.get('blank', 0)} → {s['blank']})"
        elif o and abs(s["blank"] - o.get("blank", 0)) >= MEMORY_BLANK_GAP:
            out[h] = f"빈 칸 비율 {o.get('blank', 0)} → {s['blank']}"
        elif o.get("uniq") and s["uniq"] and max(o["uniq"], s["uniq"]) >= 2 * min(o["uniq"], s["uniq"]):
            out[h] = f"고유값 수 {o['uniq']} → {s['uniq']}"
    return out


def mismatch_questions(mem, bad):
    """어긋난 열마다 질문 하나(코드가 만든다 · 중요도 높음) — 빈 칸이 있는 열이면 처분 셋(제안이 먼저)."""
    qs = []
    for h, why in bad.items():
        s = ((mem or {}).get("seen") or {}).get(h) or {}
        if s.get("fill"):
            opts = [f"{s['fill']} (제안)"] + [x for x in FILL if x != s["fill"]]
            q = f"'{h}' — 기억과 어긋남: {why} · 빈 칸을 어떻게 하나(같은 상위 '{s.get('scope') or '시트 전체'}' 안)"
        else:
            opts, q = ["기억 그대로", "다르게 읽는다(교정에 적는다)", "읽지 않음"], f"'{h}' — 기억과 어긋남: {why} · 이 표본에서 어떻게 읽나"
        qs.append({"q": q, "options": opts, "importance": "높음 — 기억과 어긋남(코드 판정)"})
    return qs


def check_lines(mem, bad, checks):
    """**열마다 한 줄**(B217 ①) — ✔ 기억 그대로 · ✎ 제안(LLM 수정 · 기억에 없는 열) · ⚠ 어긋남 + 기억 · 관찰 · LLM 확인(없으면 「확인 없음」)."""
    by = {c.get("column"): c for c in checks or []}
    cols, seen, old = mem.get("cols") or {}, mem.get("seen") or {}, mem.get("old") or {}
    out = ["   열 확인 — 기억 · 이번 표본 관찰(빈 칸 비율 · 고유값 수 · 값 예) · LLM 확인"]
    for h in mem.get("headers") or []:
        m, s, o, c = cols.get(h) or {}, seen.get(h) or {}, old.get(h), by.get(h)
        mark = "⚠" if h in bad else "✎" if not m or (c or {}).get("verdict") == "수정" else "✔"
        out.append(f"   {mark} {_screen.pad(_screen.cut(h, 17), 18)}기억 {m.get('role') or '—'}/{m.get('field') or '—'}"
                   + (f"(빈 {o['blank']} · 고유 {o['uniq']})" if o else "")
                   + f" | 관찰 빈 {s.get('blank', '—')} · 고유 {s.get('uniq', '—')} · 예 {', '.join(repr(v) for v in s.get('eg') or [])}"
                   + (f" — 어긋남: {bad[h]}" if h in bad else "")
                   + (f" · LLM {c['verdict']}{': ' + c['proposal'] if c.get('proposal') else ''} — {c.get('why') or ''}" if c else " · 확인 없음"))
    return out


def _mem_of(c, mem):
    """그 열이 기억 그대로면 기억의 작업 자리 · 아니면 None(사람이 고친 열은 기억 표시를 뗀다 — B215 ②)."""
    m = ((mem or {}).get("cols") or {}).get(c.get("column"))
    ok = m and str(m.get("role") or "").lower() == str(c.get("role") or "").lower() and m.get("field") == c.get("store_as")
    return m["from"] if ok else None


def prefill(cols, mem):
    """**기억으로 시작**(B215 ②) — 표본 헤더 중 기억에 있는 열(충돌 밖)은 코드가 열 표에 채운다 · 나머지는 받은 그대로."""
    if not mem:
        return cols
    got, out = {c["column"]: c for c in cols or []}, []
    for h in mem.get("headers") or []:
        m = (mem.get("cols") or {}).get(h)
        if m and h not in (mem.get("conflicts") or {}):
            g = got.get(h) or {}
            out.append({"column": h, "role": str(m.get("role") or "").lower() if m.get("role") == "UNMAPPABLE" else m.get("role"),
                        "attach": g.get("attach"), "store_as": m.get("field"), "context_type": g.get("context_type")})
        elif h in got:
            out.append(got[h])
    return out + [c for c in cols or [] if c["column"] not in (mem.get("headers") or [])]


def cols_lines(cols, prev=None, mem=None):
    """**문답 열 표**(B206 ④ — 라운드 화면 · 생성 전 확정 확인이 같은 함수) — 살아남은 열(열 · role · 붙는 곳 · 저장명 · 맥락형 ·
    지난 라운드에서 바뀐 열 ✎) + 제외 한 줄."""
    from cli import _screen
    was = {c["column"]: c for c in prev or []}
    keep = [c for c in cols or [] if c.get("role") != UNMAPPABLE]
    out = [f"   {_screen.pad('열', 18)}{_screen.pad('role', 12)}{_screen.pad('붙는 곳', 14)}{_screen.pad('저장명', 14)}맥락형"] if keep else []
    out += [f"   {_screen.pad(_screen.cut(c['column'], 17), 18)}{_screen.pad(c['role'], 12)}{_screen.pad(c.get('attach') or '—', 14)}"
            f"{_screen.pad(c.get('store_as') or '—', 14)}{c.get('context_type') or '—'}"
            + ("  ✎" if prev is not None and was.get(c["column"]) != c else "")
            + (f"  기억 {_mem_of(c, mem)}" if _mem_of(c, mem) else "") for c in keep]
    gone = [c["column"] for c in cols or [] if c.get("role") == UNMAPPABLE]
    return out + (_screen.items(f"   제외 {len(gone)}열: ", gone) if gone else [])


INTERVIEW_STOP = ("진행", "go", "ok", "진행해", "진행합니다")

# **확정 요약**(B60 ②) — 문답이 끝날 때 모델이 내는 마지막 턴. **새 지점이 아니다**
# (같은 `interview` 자리). 대화는 이력이고 판단은 이 목록 하나다 — 생성 프롬프트에는
# 이것만 실린다. strict 요건상 required = properties 전량(B44).
DECISIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {"type": "array", "items": {
            "type": "object",
            "properties": {"topic": {"type": "string"},
                           "decision": {"type": "string"},
                           "reason": {"type": "string"},
                           "round": {"type": ["integer", "null"]}},
            "required": ["topic", "decision", "reason", "round"],
            "additionalProperties": False}},
    },
    "required": ["decisions"],
    "additionalProperties": False,
}


def _summarize(pkg, history, context=None):
    """마지막 턴 — 라운드 전문에서 **확정 사항 목록**을 낸다.

    mock 갈래는 **답에서 규칙으로** 만든다: 답한 질문 하나가 결정 하나다. 미리 적어
    둔 문장을 되읽으면 「답이 결정으로 옮겨지는가」를 아무것도 검증하지 않는다.
    """
    if gateway.use_mock():
        gateway.mock("generate", f"문답 확정 요약 — 라운드 {len(history)}에서 규칙 요약")
        out = []
        for r in history:
            n = r.get("round")
            for a in r.get("answers") or []:
                raw = (a.get("answer") or "").strip()
                if not raw or raw.lower() in INTERVIEW_STOP:
                    continue
                out.append({"topic": (a.get("q") or "")[:40],
                            "decision": a.get("chosen") or raw,
                            "reason": f"{n}라운드 사람 답", "round": n})
            ans = r.get("answer") or ""
            if "교정: " in ans:
                out.append({"topic": f"교정 (r{n})",
                            "decision": ans.split("교정: ", 1)[1],
                            "reason": f"{n}라운드 사람 교정", "round": n})
        if not out and history:
            last = history[-1]
            out.append({"topic": "이해 요약",
                        "decision": " · ".join([f"{x['column']} {x['header']}: {x['how']}" for x in last.get("reading") or []]
                                               + [last.get("understanding") or ""]),
                        "reason": f"{last.get('round')}라운드 이해 — 사람이 교정 없이 진행",
                        "round": last.get("round")})
        return out
    convo = [{"role": "system",
              "content": gateway.prompt("interview") + "\n\n---\n\n" + _vocab_excerpt(pkg)},
             {"role": "user", "content": json.dumps(
                 {"입력_패키지": pkg, "문답_전문": history,
                  **({"기계_관문_실패": context} if context else {}),
                  "요청": "마지막 턴 — 확정 요약을 내라 (지시문 「마지막 턴」 절)"},
                 ensure_ascii=False)}]
    _sent_size(convo, "문답 확정 요약")
    return (gateway.chat(convo, json_schema=DECISIONS_SCHEMA, point="interview")
            or {}).get("decisions") or []


def _show_decisions(decisions):
    print(f"\n■ 확정 요약 — {len(decisions)}항목 (이것이 생성의 입력이다 · 전문은 이력으로 남는다)")
    for i, d in enumerate(decisions, 1):
        rd = f" (r{d['round']})" if d.get("round") is not None else ""
        print(f"   {i}. [{d.get('topic', '')}] {d.get('decision', '')}"
              f"  — {d.get('reason', '')}{rd}")


def confirm(decisions, columns=None, retry=None):
    """**생성 전 확정 확인 한 자리**(B60 ② · B206 ⑤) — 문답 · 힌트만 · 이어가기(y) 어느 길이든 열 표 + 확정 요약을 보이고
    `[Y / 수정(번호) / 추가(문장)]` · `retry`(문답 길)면 `n` = 요약을 다시 낸다(1회) · 비대화형은 그대로 간다(한 줄) · 고침은
    같은 리스트에(부르는 쪽의 묶음이 그대로 바뀐다)."""
    while True:
        for ln in cols_lines(columns):
            print(ln)
        _show_decisions(decisions)
        try:
            raw = _ask("   확정 요약이 맞나? [Y / 수정(번호) / 추가(문장)] > ").strip()
        except (EOFError, KeyboardInterrupt, StopIteration):
            print("   (비대화형 — 확인 없이 요약 그대로 생성으로 간다)")
            return decisions
        low = raw.lower()
        if low in ("", "예") or low in _screen.YES or low in INTERVIEW_STOP:
            return decisions
        if low in _screen.NO and retry:
            print("   → 요약을 다시 낸다 (1회)")
            decisions[:], retry = retry(), None
            continue
        if raw.startswith("추가"):
            text = raw[len("추가"):].strip()
            if text:
                decisions.append({"topic": "추가", "decision": text, "reason": "사람이 확정 확인에서 추가", "round": None})
            else:
                print("   추가할 문장을 같이 적어라 — 예: 추가 헤더는 3행이다")
            continue
        m = re.match(r"\s*(?:수정\s*)?(\d+)", raw)
        idx = int(m.group(1)) if m else None
        if idx is None or not (1 <= idx <= len(decisions)):
            print(f"   항목 번호를 적어라 (1~{len(decisions)}) — 예: 수정 2 · 또는 추가 <문장>")
            continue
        d = decisions[idx - 1]
        try:
            fix = _ask(f"   [{d.get('topic', '')}] 결정을 어떻게 고칠까 > ").strip()
        except (EOFError, KeyboardInterrupt, StopIteration):
            return decisions
        if fix:
            decisions[idx - 1] = {**d, "decision": fix, "reason": f"사람이 요약 확인에서 수정 — 이전: {d.get('reason', '')}"}


def finalize(pkg, history, context=None):
    """문답이 끝난 자리 — **확정 요약을 내고 사람이 확인한다** (B60 ②) · 확인은 생성 전 한 자리 `confirm`.

    **대화는 이력, 판단은 정본** — 라운드 전문은 남고 생성에는 요약만 실린다(표본이 바뀐 묶음 둘에서 모델이 대화를
    재구성하다 어긋난 실측). `n`이면 모델이 요약을 다시 낸다(1회)."""
    if not history:
        return []
    return confirm(_summarize(pkg, history, context), history[-1].get("columns"),
                   retry=lambda: _summarize(pkg, history, context))


def _interview_round(pkg, history, context=None, memory=None, retry=None):
    """문답 1라운드 — 이해 요약과 질문을 받는다. **종료를 결정하지 않는다.**

    `context`는 **생성 전이 아니라 실패 뒤에 열 때** 오는 재료다(B50) — 기계 관문의
    실패 문면이다. **입력 패키지에 키를 더하지 않는다**(사람 4 + 시스템 5 불변) —
    이것은 그 라운드의 메시지에만 실린다.

    LLM은 «이해했다, 진행하겠다»를 판단하지 않는다(I4: 제어 흐름은 코드+사람
    소유). 매 라운드 요약과 질문을 낼 뿐이고, **끝내는 것은 사람**이다.

    mock 갈래는 **표본 관찰 재료와 누적 답변에서 규칙으로** 요약을 만든다 —
    미리 적어 둔 문장을 되읽으면 「교정이 반영되는가」를 아무것도 검증하지 않는다.
    """
    heads = (pkg.get("system") or {}).get("reader_head") or []
    cols = []
    for h in heads:
        for sh in (h.get("head") or {}).get("sheets") or []:
            cols += [v for a, v in (sh.get("cells") or {}).items()
                     if a.endswith("1") and isinstance(v, str)]
    # **판정 어휘를 이어 붙인다**(B32) — 문답이 role·층 어휘를 모른 채 물으면
    # 「판단이 갈리는 것」의 기준이 없어 업무 사정을 묻게 된다.
    # **이전 표본에 대한 이해는 구분해 싣는다**(B55 ②-1) — 같은 자리에 섞으면
    # 다른 문서에 대한 판단이 현재 판정에 들어오고, 빼면 재현 조건이 사라진다.
    fresh = _prior_rounds(pkg)
    convo = [{"role": "system",
              "content": gateway.prompt("interview") + "\n\n---\n\n"
                         + _vocab_excerpt(pkg)},
             {"role": "user", "content": json.dumps(
                 {"입력_패키지": pkg, "지난_문답": fresh + history,
                  **({"기계_관문_실패": context} if context else {}),
                  **({"열_기억": memory} if memory else {}),          # 승인된 양식의 열 판정 · 확정 문답 (B215 ② — 메시지에만)
                  **({"다시_묻는_까닭": retry} if retry else {})},
                 ensure_ascii=False)}]
    _sent_size(convo, f"문답 라운드 {len(history) + 1}")              # mock도 같은 크기 줄(B210 ② — 보낼 것을 잰다)
    if gateway.use_mock():
        gateway.mock("generate", f"문답 라운드 {len(history) + 1} — 규칙 요약")
        cols = list((memory or {}).get("headers") or cols)          # 기억이 있으면 표본 헤더(헤더 이름 한 함수)
        base = (f"열 {len(cols)}개를 관찰했다: {', '.join(cols[:6])}"
                if cols else "표본에서 열을 관찰하지 못했다")
        fixes = [h["answer"] for h in history if h.get("answer")]
        qs = ([] if fixes else
              [{"q": f"새 헤더 '{c}'는 무엇으로 읽나", "options": ["entity", "attribute", "읽지 않음"],
                "importance": "높음 — 기억에 없는 열"} for c in cols
               if c not in (memory.get("cols") or {}) or c in (memory.get("conflicts") or {})] if memory else
              [{"q": "병합된 좌측 열은 어떻게 다루나",
                "options": ["위 값 채움", "행 독립", "모름"],
                "importance": "높음 — 좌표 해소가 여기 걸린다"}])
        if context and not fixes:
            # 실패 뒤에 연 문답이면 **무엇이 막혔는지**를 먼저 묻는다.
            qs = [{"q": f"기계 관문이 막혔다: {context[0][:60]} — 무엇을 바꿀까",
                   "options": ["표본을 바꾼다", "힌트를 더한다", "모름"],
                   "importance": "높음 — 이것이 풀려야 산출이 선다"}] + qs
            base = f"기계 관문 실패 {len(context)}건을 보고 다시 묻는다. " + base
        # 열 판정도 규칙으로(창작 — 첫 열 anchor · 「비고」 꼴은 뺀다 · 교정에 이름이 나온 열은 context로 — ✎를 보이는 자리)
        roles = [("anchor" if i == 0 else UNMAPPABLE if any(w in c for w in ("비고", "서명", "No")) else
                  "context" if any(c in f for f in fixes) else "attribute") for i, c in enumerate(cols)]
        return {"understanding": base + ("" if not fixes else
                                         " · 교정 반영: " + " / ".join(fixes)),
                "reading": [{"column": _col(i), "header": c, "how": r} for i, (c, r) in enumerate(zip(cols, roles), 1)],
                "columns": [{"column": c, "role": r, "attach": None if r == UNMAPPABLE else cols[0],
                             "store_as": None if r == UNMAPPABLE else c, "context_type": "행" if r == "context" else None}
                            for c, r in zip(cols, roles)],
                "checks": [{"column": c, "verdict": "확인", "proposal": None,
                            "why": "기억 그대로" if c in (memory.get("cols") or {}) else "새 헤더 — 관찰로 읽는다"}
                           for c in cols] if memory else [],
                "progress": {"columns": len(cols), "decided": len(fixes),
                             "undecided": max(0, len(cols) - len(fixes)),
                             "by_role": "(mock — 규칙 요약이라 role 배정이 없다)"},
                "questions": qs}

    return gateway.chat(convo, json_schema=INTERVIEW_SCHEMA, point="interview")


def _prior_rounds(pkg):
    """**현재 표본 묶음의 라운드**를 로그에서 읽는다 (B55 ②-2 · B62 ②).

    **저장만 이어 붙이고 모델이 처음부터 물으면 사람이 두 번 답한다** — 구판은
    `history`를 빈 리스트로 시작해, 라운드가 파일에 쌓여도 다음 실행의 모델은
    그것을 본 적이 없었다. 그래서 지난 라운드를 실어 보낸다.

    **이전 표본(stale)의 전문은 싣지 않는다**(B62 ②). 구판은 「이전 표본에 대한
    이해」로 구분해 함께 보냈는데, 그러면 같은 전문이 **패키지와 이 자리 둘로**
    나간다. 이전 표본의 **판단**은 `decisions`로 남아 생성 지시문이 표시해서
    싣는다 — 대화는 이력이고 판단은 정본이라는 규율 그대로다.

    전문은 로그에 산다(`review/<doc_type>/interview_log.json`) — 패키지에 두면
    생성 user 메시지(패키지 원문 통째)에 그대로 실린다.
    """
    from cli.register.interview import _hint_batches, read_log
    human = (pkg or {}).get("human") or {}
    doc_type = human.get("doc_type")
    if not doc_type:
        return []
    log = read_log(doc_type)
    now = sorted(str(x) for x in (human.get("samples") or []))
    out = []
    for b in _hint_batches(human.get("hint")):
        if b.get("stale") or sorted(b.get("samples") or []) != now:
            continue
        out += log.get(b.get("at")) or b.get("rounds") or []
    return out


def _first_text(pkg):
    """열문자 → 그 열의 첫 글자 셀(헤더 행을 아직 모를 때의 이름)."""
    out = {}
    for h in ((pkg.get("system") or {}).get("reader_head") or []):
        for sh in (h.get("head") or {}).get("sheets") or []:
            for a, v in sorted((sh.get("cells") or {}).items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)):
                if isinstance(v, str) and v.strip():
                    out.setdefault(re.sub(r"\d", "", a), v.strip())
    return out


def _prof_hint(pkg, out=None):
    """열 프로파일 요약을 **사람에게도** 보인다 (B43 ⑥-3) — **주요 열만**(B215 ③): 이번 라운드에서 entity · anchor ·
    attribute로 읽은 열 + 이번 질문에 나온 열 · 줄마다 `A 공정명: …`(이름은 이해 요약의 열 항목 · 없으면 그 열의 첫 글자 셀)."""
    profs = [pp for h in ((pkg.get("system") or {}).get("reader_head") or [])
             for pp in (h.get("열_프로파일") or [])]
    names = {**_first_text(pkg), **{x["column"]: x["header"] for x in (out or {}).get("reading") or []}}
    want = {c["column"] for c in (out or {}).get("columns") or [] if c.get("role") in ("entity", "anchor", "attribute")}
    qtext = " ".join(q.get("q", "") for q in (out or {}).get("questions") or [])
    cols = [(c, v) for s in profs for c, v in (s.get("열") or {}).items()
            if names.get(c) in want or (names.get(c) and names[c] in qtext)]
    if not cols:
        return
    print(f"   [근거] 열 프로파일 — 주요 열 {len(cols)}(entity · anchor · attribute로 읽은 열 · 질문에 나온 열)")
    for c, v in cols:
        sh = v.get("형태") or {}
        print(f"     {c} {names.get(c, '')}: 고유 {v['고유값수']:>3} / {v['비지_않은_행수']:>3}행 · "
              f"빈셀 {v['빈셀비율']} · 수치단위 {sh.get('수치단위_비율', '?')} · "
              f"제안 {v['기계제안']['제안']}")


def _interview(pkg, on_round=None, context=None, memory=None):
    """문답 — **끝내는 것은 사람뿐이다.** 상한 없음(§6.5 재생성 루프와 같은 원리).

    **생성 전에도, 기계 관문 실패 뒤에도 같은 장치다**(B50) — 실패 뒤에 여는 경우
    `context`(실패 문면)를 함께 넣는다. 장치를 둘로 두면 번호 선택지·즉시 저장 같은
    규율이 한쪽에만 남는다.

    돌려주는 것은 라운드 이력이다: 매 라운드의 요약·질문·답이 전부 남는다.
    기록이 없으면 **같은 등록을 재현할 수 없다.**
    """
    history, blanks = [], 0
    print(f"\n■ {'기계 관문 실패 뒤 문답' if context else '생성 전 문답'} — "
          f"이해 요약을 보고 교정한다. 끝내려면 «{INTERVIEW_STOP[0]}» (상한 없음)")
    if context:
        print(f"   기계 관문 실패 {len(context)}건 — 문면이 답을 담지 않아 묻는다")
        for c in context[:5]:
            print(f"     · {c}")
    while True:
        out = _interview_round(pkg, history, context, memory)
        gap = [h for h in (memory or {}).get("headers") or [] if h not in {c.get("column") for c in out.get("checks") or []}]
        if gap:                                                       # 열 확인이 빠졌다 — 한 번 다시 묻는다 (B217 ①)
            out = _interview_round(pkg, history, context, memory, retry=f"checks에 열 {gap}이 없다 — 모든 열에 한 번씩") or out
        n = len(history) + 1
        bad = mismatches(memory) if memory and n == 1 else {}
        if n == 1:
            out["columns"] = prefill(out.get("columns"), memory)      # 첫 라운드 — 기억 열은 코드가 채운다 (B215 ②)
            out["questions"] = mismatch_questions(memory, bad) + list(out.get("questions") or [])   # 어긋남 질문은 코드가 (B217 ①)
        pg = out.get("progress") or {}
        # **진행 1줄**(B43 ⑥) — 「이제 진행해도 되나」의 판단 근거다.
        if pg:
            print(f"\n[라운드 {n}] 열 {pg.get('columns', '?')}개 · "
                  f"판정 {pg.get('decided', '?')} ({pg.get('by_role', '')}) · "
                  f"미정 {pg.get('undecided', '?')} · "
                  f"이번 질문 {len(out.get('questions') or [])}")
        else:
            print(f"\n[라운드 {n}]")
        for ln in cols_lines(out.get("columns"), (history[-1].get("columns") or []) if history else None, memory):
            print(ln)                         # 살아남은 열 표 · 제외 한 줄(B206 ④) · 기억 표시(B215 ②)
        for ln in check_lines(memory, bad, out.get("checks")) if memory and n == 1 else []:
            print(ln)                         # 열마다 기억 · 관찰 · LLM 확인 (B217 ①)
        print("이해 요약")
        for x in out.get("reading") or []:    # 열마다 한 줄 (B215 ③)
            print(f"   {x['column']} {_screen.paint(x['header'], 'head')}: {x['how']}")
        print(f"   {out['understanding']}")
        _prof_hint(pkg, out)                  # 판정 근거 — 주요 열(B215 ③)
        # **질문 하나 = 한 구획**(등록개선 ⑤) — 중요도 순으로 번호를 매기고, 구획마다
        # 구분선·번호 선택지·입력 한 줄. 이어 붙이면 어느 답이 어느 열 것인지 안 보인다.
        qs = sorted(out.get("questions") or [], key=_rank)
        answers, stop = [], False
        for i, q in enumerate(qs, 1):
            opts = q.get("options") or []
            imp = q.get("importance")
            print(_RULE)
            print(f"   Q{i}. {q['q']}" + (f"   [{imp}]" if imp else ""))
            if opts:
                print("       " + "  ".join(f"{k}) {o}" for k, o in enumerate(opts, 1)))
            try:
                raw = _ask(f"   Q{i} 답 (번호 또는 문장 · 빈 줄=건너뜀 · «진행»=종료) > ").strip()
            except (EOFError, KeyboardInterrupt):
                raw = INTERVIEW_STOP[0]
                print(f"   (입력 없음 — {raw})")
            chosen = _pick_option(raw, opts)
            if chosen:
                print(f"       → {chosen}")
            answers.append({"q": q["q"], "answer": raw, "chosen": chosen})
            if raw.lower() in INTERVIEW_STOP:
                stop = True
                break
        print(_RULE)
        if not stop:
            try:
                extra = _ask("   교정/추가 (없으면 빈 줄 · «진행»=종료) > ").strip()
            except (EOFError, KeyboardInterrupt):
                extra = INTERVIEW_STOP[0]
                print(f"   (입력 없음 — {extra})")
            stop = extra.lower() in INTERVIEW_STOP
        else:
            extra = ""
        # `answer`는 지난 문답으로 LLM에 되돌아가는 **한 줄 문장**이다 — 번호는 본문으로
        # 풀어 싣는다(모델은 «1»이 무엇이었는지 모른다). 낱개 답은 `answers`에 그대로.
        ans = "; ".join(f"{a['q']} → {a['chosen'] or a['answer']}"
                        for a in answers if a["answer"] and a["answer"].lower()
                        not in INTERVIEW_STOP)
        if extra and extra.lower() not in INTERVIEW_STOP:
            ans = (ans + "; " if ans else "") + f"교정: {extra}"
        history.append({"round": n, "understanding": out["understanding"], "reading": out.get("reading") or [],
                        "questions": qs, "answers": answers, "answer": ans,
                        "progress": pg, "columns": out.get("columns") or []})
        if on_round:
            on_round(history)                 # **라운드마다 즉시 저장**(B43 ⑤)
        if stop:
            print(f"   → 사람이 종료했다. 라운드 {n}회 · 생성으로 간다")
            return history
        blanks = blanks + 1 if not ans else 0
        if blanks >= 2:
            print(f"   → 빈 입력 2연속 — 종료로 읽는다. 라운드 {n}회")
            return history
