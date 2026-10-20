# -*- coding: utf-8 -*-
"""칸 0.2 — **사내 조건 · 사내 모양** — 합친 스위트 (B131 ④ — 회차 이름 스위트 3개를 칸 하나로).

조각(옛 스위트 그대로 · 조각마다 클린 상태에서): part_onsite.py · part_g6_shanae_parts.py · part_g6_shanae_root.py
잠그는 성질은 조각마다 머리말이 말한다 · 실행은 `tests/suite_parts.py`.
"""
from suite_parts import run

run((
    "part_onsite.py",
    "part_g6_shanae_parts.py",
    "part_g6_shanae_root.py",
))
