# -*- coding: utf-8 -*-
"""칸 0.3 — **인입 화면** — 합친 스위트 (B131 ④ — 회차 이름 스위트 4개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_g6_ingest.py · part_g6_extract_view.py · part_g6_preflight_view.py · part_g6_numbers.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_g6_ingest.py",
    "part_g6_extract_view.py",
    "part_g6_preflight_view.py",
    "part_g6_numbers.py",
))
