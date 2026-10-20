# -*- coding: utf-8 -*-
"""칸 1.1 — **계약 · 출처 · 규칙** — 합친 스위트 (B131 ④ — 회차 이름 스위트 4개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_g65_contract.py · part_g65_cross.py · part_g65_prov.py · part_g65_rules.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_g65_contract.py",
    "part_g65_cross.py",
    "part_g65_prov.py",
    "part_g65_rules.py",
))
