# -*- coding: utf-8 -*-
"""칸 2.1 — **입구 — 지문 · 일괄 · 등록부 · 시트 · 렌즈** — 합친 스위트 (B131 ④ — 회차 이름 스위트 5개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_g6_scan.py · part_g6_batch.py · part_g6_registry.py · part_g6_sheets.py · part_g6_lens.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_g6_scan.py",
    "part_g6_batch.py",
    "part_g6_registry.py",
    "part_g6_sheets.py",
    "part_g6_lens.py",
))
