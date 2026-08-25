# -*- coding: utf-8 -*-
"""테스트 픽스처의 **소재 단일 지점** — mock 격리의 관문.

**mock은 걷어낼 대상이 아니라 격리할 대상이다.** 물리적으로 지우면 `gauges`·`scan`이
죽고 회귀가 붕괴한다(실측). 원인은 core·parser·cli 본체가 mock 경로를 **무조건
상수**로 알고 있다는 것이었다 — 분기 안에 있는 참조가 0건이었다.

그래서 경로를 여기 한 곳으로 모으고 **없을 때의 거동을 명시**한다:

| 자산 | 없으면 |
|---|---|
| `parsed/` | `run.py all`이 인입할 것이 없다고 **말하고** 끝난다 (조용한 무동작 금지) |
| `queries.json` | 계기판이 질의 스모크 항목을 **0으로 세고 계속 돈다** (`gauges` 사망 금지) |
| `fixtures/adapters` | 지문 스캔이 그 디렉터리를 **건너뛴다** (하드 크래시 금지) |
| `extract_hints` | 문형 규칙 폴백으로 간다 — **결과가 조용히 달라진다**(아래) |
| `struct_maps` | 번호 패턴 휴리스틱으로 간다 |

**`extract_hints` 부재는 크래시가 아니라 결과를 바꾼다** — 실측 대조: 동일 문서에서
`주액기`(Unit) → `주액`(Process), attach 1건 → 0건. 그래서 이 자산은 **옮기되
지우지 않는다**: 회귀 기준선이 그 위에 서 있다.

`ONTO_FIXTURES` 환경변수로 뿌리를 옮길 수 있다 — 사내에서 mock을 통째로 들어내고
실자산으로 갈아 끼울 때의 손잡이다. 기본값은 `tests/fixtures/`.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 픽스처 뿌리. 사내 반입 시 `ONTO_FIXTURES`로 갈아 끼운다.
ROOT_DIR = Path(os.environ.get("ONTO_FIXTURES") or (ROOT / "tests" / "fixtures"))

PARSED = ROOT_DIR / "parsed"
RAW = ROOT_DIR / "raw"
QUERIES = ROOT_DIR / "queries.json"
ADAPTERS = ROOT_DIR / "adapters"
FIXTURE_ADAPTERS = ROOT_DIR / "fixtures" / "adapters"
FIXTURE_SCHEMAS = ROOT_DIR / "fixtures" / "schemas"
EXTRACT_HINTS = ROOT_DIR / "extract_hints"
STRUCT_MAPS = ROOT_DIR / "struct_maps"


def available():
    """지금 이 클론에 픽스처가 있는가 — 사내에서는 없는 것이 정상이다."""
    return ROOT_DIR.is_dir()


def dirs(*paths):
    """존재하는 디렉터리만 돌려준다 — **없는 것을 모듈로 로드하려다 죽지 않게.**"""
    return [p for p in paths if p.is_dir()]
