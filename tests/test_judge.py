# -*- coding: utf-8 -*-
"""칸 3.4 — **판정 · 매칭** — 합친 스위트 (B131 ④ — 회차 이름 스위트 5개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_g6_diag.py · part_g6_synonym.py · part_g6_judge2.py · part_g6_replay2.py · part_g6_narrow.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_g6_diag.py",
    "part_g6_synonym.py",
    "part_g6_judge2.py",
    "part_g6_replay2.py",
    "part_g6_narrow.py",
))
