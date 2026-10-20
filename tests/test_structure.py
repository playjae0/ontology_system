# -*- coding: utf-8 -*-
"""칸 2.4 — **문서 구조 · 목차 · 개요 · 덱** — 합친 스위트 (B131 ④ — 회차 이름 스위트 6개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_g6_structure.py · part_g6_ladder.py · part_g6_split.py · part_p1_hier.py · part_g6_outline.py · part_g6_deck.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_g6_structure.py",
    "part_g6_ladder.py",
    "part_g6_split.py",
    "part_p1_hier.py",
    "part_g6_outline.py",
    "part_g6_deck.py",
))
