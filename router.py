# -*- coding: utf-8 -*-
"""층 폴더 자동 발견 — 등록 배선이 없다 (CH6 6.1).

층을 추가하는 일이 "layers/ 아래 폴더 하나 + config.json 하나"로 끝나야
config-only가 성립한다. 여기에 층 이름을 적는 순간 그것이 배선이 된다.
"""
from pathlib import Path

LAYERS = Path(__file__).resolve().parent / "layers"


def discover():
    if not LAYERS.exists():
        return []
    return sorted(p.name for p in LAYERS.iterdir()
                  if (p / "config.json").exists())
