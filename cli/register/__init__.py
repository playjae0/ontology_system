# -*- coding: utf-8 -*-
"""칸 1.1~1.8 — n6 구축 모드 등록 파이프라인 — doc_type 등록의 3단 (파서_명세 §6·§7 · 틀 §2).

    ① 생성  입력 패키지(사람 4 + 시스템 5) → reader head 공급 → 어댑터·스키마 초안
    ② 뷰 확인  기계 관문(실행 하네스)이 먼저 거르고, 사람은 그 뒤 뷰를 본다 → 재생성 루프
    ③ 확정  승인 1회 → doc_type 등록부 등재

**틀 §2가 정한 검수 수준**: 사람은 코드가 아니라 **결과 뷰**를 보고, 통과는 승인 1회다.
그래서 ②가 두 겹이다 — **기계가 먼저 거르고**(하네스), 사람은 그 뒤에 뷰를 본다.
기계 관문이 없으면 사람이 문법 오류를 읽는 자리로 내려앉는다.

**"무수정 = 자동 통과"는 금지다.** 승인자 없이는 등재하지 않는다.

경계:
  · 하네스는 `kit/run_adapter.py`를 **호출**한다 — 재작성하지 않는다.
  · 렌더러는 `kit/render_review.py`를 **호출**한다 — 뷰 데이터 스키마(D-79)가 계약이고
    여기는 산출자다. 스키마가 부족하면 고치는 것이 아니라 멈추고 보고할 자리다.
  · **층 초안 구획은 없다** — 층 등록(R1)은 국면 2 게이트이고 여기는 doc_type 전용이다.

사용:
  python cli/register.py generate <doc_type> <층> <표본...> [--hint "..."] [--interview]
       --hint       자유 텍스트. 표본만으로 안 보이는 것을 적는다("3~7행 병합은 위 값 채움")
       --interview  생성 전에 LLM의 **이해 요약**을 보고 교정한다 — 끝내는 것은 사람이다
       --no-fewshot 참조 어댑터 주입을 끈다(스켈레톤 본문은 유지) — 컨텍스트가 좁을 때
       --resume     기존 입력 패키지로 **초안만** 다시 받는다 (문답을 다시 하지 않는다)
  python cli/register.py generate <doc_type> --resume
       └ resume은 **doc_type 하나만** 필요하다 — 층·표본은 패키지에서 읽는다
       --no-basic   표본이 전부 산문 포맷이어도 **LLM 생성으로 간다** — 기본은 고정
                    어댑터를 권하고 묻는다(B59 ③). 비대화형이면 고정 어댑터로 간다
       --use-basic  분할 자명 계열(PPT)은 LLM 생성을 건너뛰고 **기본 어댑터를 정본으로**
                    등재 경로에 놓는다 (§6.4-5) — 검수·승인 1회는 그대로다(M4)
       --drop-interview  이전 문답을 **버린다.** 기본은 이어가기다 — 사람의 답은
                    다시 만들 수 없는 재료라, 버리는 쪽이 명시를 요구한다(B55)
       --revise     **등록분의 새 판.** 이름은 그대로이고 확정이 정본을 교체하며
                    revision이 오른다. 승인 기록은 누적한다 (H27)
       --as <이름>  **변형 등록.** 기존 doc_type은 그대로 두고 새 이름으로 간다
  python cli/register.py review   <doc_type> [--instruct "수정 지시"] [--rows N|all]
       --rows       리허설 파싱을 앞 N행으로 제한 (기본 200 · 전량은 all)
       --llm-coord / --no-llm-coord   좌표 LLM 보조를 미리 정한다 (기본: 물어본다)
       --extract / --no-extract       prose 추출 리허설을 미리 정한다 (기본: 물어본다)
  python cli/register.py confirm  <doc_type> --by <승인자>
  python cli/register.py status   <doc_type>   ← 관문이 막는 이유와 **다음 줄**
  python cli/register.py list
"""
from __future__ import annotations
import importlib.util
import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import paths
from core.llm import check, gateway, points
from core.state import fixtures, log, registry, store
from parser import pipeline, preflight, profile, reader, tagger
from parser.normalizer import _col
from parser import form
from parser.adapters import basic_ppt, basic_prose_xlsx
from kit.render_review import render
from kit.run_adapter import load_blocks
from router import discover

ROOT = paths.ROOT          # 레포 루트는 자리 소유자가 안다 (B78)

# **분할 뒤 재수출** — 등록 흐름은 여기 남고, 조립·문답은 제 모듈로 갔다.
# 이름을 그대로 내보내는 이유: 테스트와 외부가 `cli.register.<이름>`으로 부른다.
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.parse import injections               # 주입 조립은 한 자리다(B48)
from cli.interview import (  # noqa: F401
    INTERVIEW_SCHEMA, INTERVIEW_STOP, _interview_round, _prof_hint, _interview,
    finalize as iv_finalize)

REVIEW = paths.review()
KIT = ROOT / "kit"
FIXTURES = fixtures.ROOT_DIR / "fixtures"   # 소재는 core/state/fixtures.py가 소유

# D-22 확장 문구 — 표본 1부 등록의 경고. **문면이 규격이다.**
SOLO_WARNING = ("표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음**. "
                "1부 등록의 선언 edges는 특별 확인 대상이다")
EXCERPT = 3                                   # 정상 조각 발췌 건수(전량은 접힘에 실린다)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state(doc_type):
    p = _dir(doc_type) / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_state(doc_type, st):
    (_dir(doc_type) / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
