# -*- coding: utf-8 -*-
"""생성 전 **문답** — 이해 요약과 질문, 종료는 사람 (문서 6 §6.5 · B21·B32·B43).

`cli/register.py`에서 떼어냈다. 문답은 생성의 앞 단계이지 생성 자체가 아니다 —
스키마·라운드 규율·mock 대체가 한 덩어리로 여기 산다. 판정 어휘는 여기서 적지
않고 `cli/prompt._vocab_excerpt`가 조립한 것을 **붙여 받는다**(정본은 템플릿 하나).
"""
from __future__ import annotations

import json
import re

from core import llm
from cli.prompt import _sent_size, _vocab_excerpt

# 입력은 이 이름을 거친다 — 테스트가 갈아끼운다(대화형이라 파이프로는 못 잰다)
_ask = input
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
        "questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"q": {"type": "string"},
                           "options": {"type": "array", "items": {"type": "string"}},
                           # **중요도**(B43 ⑥) — 3개씩 무한정 나오면 끝이 안 보인다.
                           "importance": {"type": "string"}},
            "required": ["q", "options", "importance"],
            "additionalProperties": False}},
    },
    "required": ["progress", "understanding", "questions"],
    "additionalProperties": False,
}


INTERVIEW_STOP = ("진행", "go", "ok", "진행해", "진행합니다")


def _interview_round(pkg, history):
    """문답 1라운드 — 이해 요약과 질문을 받는다. **종료를 결정하지 않는다.**

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
    if llm.use_mock():
        llm.mock("generate", f"문답 라운드 {len(history) + 1} — 규칙 요약")
        base = (f"열 {len(cols)}개를 관찰했다: {', '.join(cols[:6])}"
                if cols else "표본에서 열을 관찰하지 못했다")
        fixes = [h["answer"] for h in history if h.get("answer")]
        qs = ([] if fixes else
              [{"q": "병합된 좌측 열은 어떻게 다루나",
                "options": ["위 값 채움", "행 독립", "모름"],
                "importance": "높음 — 좌표 해소가 여기 걸린다"}])
        return {"understanding": base + ("" if not fixes else
                                         " · 교정 반영: " + " / ".join(fixes)),
                "progress": {"columns": len(cols), "decided": len(fixes),
                             "undecided": max(0, len(cols) - len(fixes)),
                             "by_role": "(mock — 규칙 요약이라 role 배정이 없다)"},
                "questions": qs}

    # **판정 어휘를 이어 붙인다**(B32) — 문답이 role·층 어휘를 모른 채 물으면
    # 「판단이 갈리는 것」의 기준이 없어 업무 사정을 묻게 된다.
    convo = [{"role": "system",
              "content": llm.prompt("interview") + "\n\n---\n\n"
                         + _vocab_excerpt(pkg)},
             {"role": "user", "content": json.dumps(
                 {"입력_패키지": pkg, "지난_문답": history}, ensure_ascii=False)}]
    _sent_size(convo, f"문답 라운드 {len(history) + 1}")
    return llm.chat(convo, json_schema=INTERVIEW_SCHEMA, point="generate")


def _prof_hint(pkg, top=6):
    """열 프로파일 요약을 **사람에게도** 보인다 (B43 ⑥-3).

    LLM은 이 재료를 이미 받아 쓰는데 사람 화면에는 없었다 — 그러면 사람은 LLM의
    판정을 근거 없이 믿거나 근거 없이 의심한다.
    """
    profs = [pp for h in ((pkg.get("system") or {}).get("reader_head") or [])
             for pp in (h.get("열_프로파일") or [])]
    cols = [(c, v) for s in profs for c, v in (s.get("열") or {}).items()]
    if not cols:
        return
    print(f"   [근거] 열 프로파일 {len(cols)}열 — 고유값/형태 (앞 {top}열)")
    for c, v in cols[:top]:
        sh = v.get("형태") or {}
        print(f"     {c}: 고유 {v['고유값수']:>3} / {v['비지_않은_행수']:>3}행 · "
              f"빈셀 {v['빈셀비율']} · 수치단위 {sh.get('수치단위_비율', '?')} · "
              f"제안 {v['기계제안']['제안']}")


def _interview(pkg, on_round=None):
    """생성 전 문답 — **끝내는 것은 사람뿐이다.** 상한 없음(§6.5 재생성 루프와 같은 원리).

    돌려주는 것은 라운드 이력이다: 매 라운드의 요약·질문·답이 전부 남는다.
    기록이 없으면 **같은 등록을 재현할 수 없다.**
    """
    history, blanks = [], 0
    print("\n■ 생성 전 문답 — 이해 요약을 보고 교정한다. "
          f"끝내려면 «{INTERVIEW_STOP[0]}» (상한 없음)")
    while True:
        out = _interview_round(pkg, history)
        n = len(history) + 1
        pg = out.get("progress") or {}
        # **진행 1줄**(B43 ⑥) — 「이제 진행해도 되나」의 판단 근거다.
        if pg:
            print(f"\n[라운드 {n}] 열 {pg.get('columns', '?')}개 · "
                  f"판정 {pg.get('decided', '?')} ({pg.get('by_role', '')}) · "
                  f"미정 {pg.get('undecided', '?')} · "
                  f"이번 질문 {len(out.get('questions') or [])}")
        else:
            print(f"\n[라운드 {n}]")
        print("이해 요약")
        print(f"   {out['understanding']}")
        _prof_hint(pkg)                       # 판정 근거를 사람에게도 보인다
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
        history.append({"round": n, "understanding": out["understanding"],
                        "questions": qs, "answers": answers, "answer": ans,
                        "progress": pg})
        if on_round:
            on_round(history)                 # **라운드마다 즉시 저장**(B43 ⑤)
        if stop:
            print(f"   → 사람이 종료했다. 라운드 {n}회 · 생성으로 간다")
            return history
        blanks = blanks + 1 if not ans else 0
        if blanks >= 2:
            print(f"   → 빈 입력 2연속 — 종료로 읽는다. 라운드 {n}회")
            return history
