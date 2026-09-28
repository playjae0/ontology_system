# -*- coding: utf-8 -*-
"""칸 2.4·2.6 — **계층 규칙 선언** — 고정 규칙이 못 세우는 시트만 LLM이 규칙을 **데이터로** 낸다 (B87 ②).

    고정 규칙(번호 군 · 가로병합 · 굵게) → 계층이 안 선 시트만
      → 훅 `struct_rule_fn(frame, sample)` — 코어가 주입한다(⑦ 안의 호출 태그 `struct_rule`)
      → 선언 검사(결정적 — 여기) → 고정 어댑터가 선언을 **적용**
      → 선언은 구조 지도 보존 파일 `rules[<시트>]`에 원본 해시와 함께 남는다

**LLM이 코드를 짜서 실행하지 않는다**(사용자 확정 2026-09-23) — 문서마다 사람 확인
없는 코드 실행은 관문 우회이고, 버리면 재인입마다 경계가 달라져 chunk_id가 움직인다.
선언은 정규식 몇 개와 플래그 둘이다: 적용하는 것은 코드다.

**파서는 core를 import하지 않는다** — 모델을 부르는 함수는 주입으로 오고(`infer_rules`),
여기는 그 함수를 감싸 **재사용·검사·셈**만 한다.
"""
from __future__ import annotations

import logging
import re

_LOG = logging.getLogger("onto.parser.struct_rule")

# 모델이 보는 것 — 그 시트 본문 열 **앞 N행**(비어 있지 않은 행)이다. 문서 전체가 아니다:
# 비용이 문서 크기와 무관해야 예고(「LLM ≤ n회」)가 약속이 된다. 러프하게 60(요청문).
RULE_SAMPLE_ROWS = 60
RULE_SAMPLE_CHARS = 80          # 한 행의 앞자리 — ⑦ 지도 패스의 첫 폭과 같다

# 선언 검사의 문턱 — 넘으면 선언을 버린다(로그) · 통째 + 큐.
MAX_PATTERNS = 8
MAX_PATTERN_LEN = 120
LEVELS = range(1, 7)
_COL = re.compile(r"^[A-Z]{1,3}$")


def check(decl):
    """선언 검사 — 사유 목록(빈 목록이면 적용한다). **결정적**이다.

    정규식은 컴파일되고 `^`로 시작해야 한다(행 머리를 보는 규칙만 — 본문 한가운데를
    잡는 패턴은 제목 판정이 아니다) · 길이 ≤ 120 · 패턴 ≤ 8 · 레벨 1~6.
    """
    if not isinstance(decl, dict):
        return ["선언이 객체가 아니다"]
    out = []
    pats = decl.get("heading_patterns")
    if not isinstance(pats, list):
        return ["heading_patterns가 목록이 아니다"]
    if len(pats) > MAX_PATTERNS:
        out.append(f"패턴 {len(pats)}개 > {MAX_PATTERNS}")
    for i, p in enumerate(pats, 1):
        m, lv = (p or {}).get("match"), (p or {}).get("level")
        if not isinstance(m, str) or not m.startswith("^"):
            out.append(f"패턴 {i} — `^`로 시작하지 않는다: {str(m)[:40]!r}")
            continue
        if len(m) > MAX_PATTERN_LEN:
            out.append(f"패턴 {i} — 길이 {len(m)} > {MAX_PATTERN_LEN}")
        try:
            re.compile(m)
        except re.error as e:
            out.append(f"패턴 {i} — 컴파일 실패: {e}")
        if not isinstance(lv, int) or isinstance(lv, bool) or lv not in LEVELS:
            out.append(f"패턴 {i} — 레벨 {lv!r}는 1~6 밖")
    for k in ("bold_is_heading", "merge_is_heading"):
        if not isinstance(decl.get(k), bool):
            out.append(f"{k}가 참/거짓이 아니다")
    col = decl.get("heading_column")
    if col is not None and not (isinstance(col, str) and _COL.match(col)):
        out.append(f"heading_column {col!r}는 열 문자가 아니다")
    if not (pats or decl.get("bold_is_heading") or decl.get("merge_is_heading")):
        out.append("제목을 세울 규칙이 하나도 없다")
    return out


def hook(ask, *, kept=None, made=None, skip=(), tally=None):
    """어댑터에 건넬 훅 — **보존분이 있으면 그것**(호출 0), 없으면 `ask` 한 번.

    `skip`은 부르지 않는 프레임이다 — **`ref` 시트는 LLM 0**(B83 — 저장만 한다).
    검사에 떨어진 선언은 `made`에 담지 않는다(보존하면 재인입이 영영 그것을 쓴다 —
    ⑦의 사유 지도와 같은 규칙 · 문서 6 §6.3). 적용해도 계층이 안 선 선언은 담는다:
    같은 파일이면 같은 결과이고, 다시 불러도 비용만 든다(두 번째 호출 없음).
    """
    kept = kept or {}
    tally = tally if tally is not None else {}

    def fn(frame, sample):
        if frame in skip:
            return None
        if frame in kept:
            tally["재사용"] = tally.get("재사용", 0) + 1
            return kept[frame]
        tally["호출"] = tally.get("호출", 0) + 1
        decl = ask(frame, sample)
        why = check(decl)
        if why:
            tally.setdefault("버림", []).append({"프레임": frame, "사유": why})
            _LOG.warning("계층 규칙 선언을 버린다 — %s: %s", frame, "; ".join(why))
            return {"_rejected": why}
        if made is not None:
            made[frame] = decl
        return decl
    return fn


def patterns_of(decl):
    """화면·검수 뷰에 적는 선언의 모양 — 패턴 목록 + 플래그."""
    pats = [f"{p['match']}→{p['level']}" for p in decl.get("heading_patterns") or []]
    if decl.get("bold_is_heading"):
        pats.append("굵게")
    if decl.get("merge_is_heading"):
        pats.append("가로병합")
    return pats


def summary(pieces, tally, targets):
    """시트마다 「고정 규칙 / 선언(패턴 목록) / 통째」 + 예고와 결과의 수.

    재료는 조각의 `meta`다(새 계산 0) — 어댑터가 `split_path`로 무엇으로 잘랐는지 말한다.
    """
    sheets = {}
    for p in pieces:
        m = p.get("meta") or {}
        fr = m.get("frame")
        if not fr or fr in sheets:
            continue
        path = m.get("split_path")
        sheets[fr] = ("선언(" + " · ".join(m.get("rule_patterns") or []) + ")"
                      if path == "rule" else "통째" if path == "flat" else "고정 규칙")
    applied = sum(1 for f in targets if sheets.get(f, "").startswith("선언"))
    return {"대상": len(targets), "대상_시트": list(targets), "재사용": tally.get("재사용", 0),
            "호출": tally.get("호출", 0), "버림": tally.get("버림") or [],
            "적용": applied, "통째": sum(1 for f in targets if sheets.get(f) == "통째"),
            "시트": sheets}
