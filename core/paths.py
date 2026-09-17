# -*- coding: utf-8 -*-
"""**상태의 자리를 아는 유일한 모듈** (B78 1a · 칸 0.4).

왜 있나: 코드를 새로 가져올 때 `review/`·`data/`·`parsed/`를 **전부 같이 옮겨야**
정상이 됐다. 상태가 코드 폴더 안에 흩어져 있고, 그 자리를 아는 코드가 26곳(운영)·
56곳(테스트)에 복사돼 있었기 때문이다. 자리를 한 모듈이 알면 **코드 교체와 상태
이사가 갈린다.**

**다섯 단**(문서 7 §7.8 · CLAUDE.md §7):

| 단 | 무엇 | 자리 | 성질 |
|---|---|---|---|
| ①자산 | 레포 — 코드·킷·공용 블록·seed | git | 교체 대상 |
| ②등록 | `doc_types.json` · 어댑터 · 스키마 · `review/` | `registry()` | 사람 승인 1회 · 재생성 불가 |
| ③진실 | 그래프·사전·청크·큐·문서 대장·ops_log | `data()` | 누적 |
| ④작업·장부 | `parsed/` · `extract/` · `ingest_log/` · 로그 | `work()` | 재생성 가능 |
| ⑤파생 | Cypher·CSV·html | `export()` | 되돌려 읽지 않는다 |

**1a는 파일을 옮기지 않는다** — 자리를 묻는 통로만 이 모듈로 모은다. 옛 배치가
기본값이고(`ONTO_HOME`이 없으면 레포 루트의 `data/`·`review/`·…), 배치 변경은 1b다.

**`mkdir`은 이 파일에만 있다**(B77 ④의 연장) — 폴더를 만드는 코드가 흩어지면 자리를
옮길 때 한 곳이 남아 옛 자리를 되살린다.
"""
from __future__ import annotations

import os
from pathlib import Path

# 레포 루트 — **코드의 자리**다. 상태의 자리와 구분한다(그것이 이 모듈의 요점이다).
ROOT = Path(__file__).resolve().parent.parent

HOME_ENV = "ONTO_HOME"

# 5단의 폴더 이름 — 이름을 바꾸는 자리도 여기 하나다.
NAMES = {"registry": "registry", "data": "data", "work": "work",
         "export": "export", "golden": "golden"}


def home():
    """상태 루트. `ONTO_HOME`이 있으면 그것, 없으면 **레포 루트**(옛 배치)다.

    1b가 기본값을 `./state`로 옮기고 `USE_MOCK=1`을 `./state_mock`으로 가른다 —
    그 분기가 들어올 자리도 여기 하나다.
    """
    v = os.environ.get(HOME_ENV)
    return Path(v).expanduser().resolve() if v else ROOT


def _under(name, *parts):
    return home().joinpath(name, *parts)


# ---------------------------------------------------------------- ②등록
# **1a에는 `registry/` 폴더가 없다** — 옛 배치에서 등록 단은 네 자리에 흩어져 있다
# (`data/doc_types.json` · `adapters/` · `schemas/` · `review/`). 그 넷을 한 폴더로
# 모으는 것이 1b이고, 그때 이 자리에 `registry(*parts)` 하나가 선다.
def review(*parts):
    """`review/<doc_type>/` — 등록 작업·승인 기록."""
    return _under("review", *parts)


def adapters(*parts):
    """확정 어댑터의 정본 자리(문서 6 §6.4·§6.5)."""
    return _under("adapters", *parts)


def schemas(*parts):
    """매칭 스키마. 공용 블록(`blocks.json`)도 지금은 같은 자리에 있다."""
    return _under("schemas", *parts)


def blocks():
    """공용 블록 — **레포 자산**이다(등록 산출이 아니다 · 1b가 자리를 가른다)."""
    return ROOT / "schemas" / "blocks.json"


# ---------------------------------------------------------------- ③진실
def data(*parts):
    """진실 단 — 그래프·사전·청크·큐·대장. 누적이고 백업 대상이다(§7.7)."""
    return _under("data", *parts)


# ---------------------------------------------------------------- ④작업·장부
# 1a에는 `work/` 폴더도 없다 — `parsed/`·`extract/`가 레포 루트에 있고, 장부·로그는
# `data/` 안에 있다(그래서 `init.KEEP_IN_DATA` 예외가 생겼다). 모으는 것은 1b다.
def parsed(*parts):
    """계약 JSON — 파서/에이전트 경계(파일 존재 = 파싱 완료)."""
    return _under("parsed", *parts)


def extract(*parts):
    """추출 체크포인트(파일 존재 = 추출 완료) · 구조 지도 보존."""
    return _under("extract", *parts)


# ---------------------------------------------------------------- ⑤파생·골든셋
def export(*parts):
    """파생물 — 되돌려 읽지 않는다(문서 1)."""
    return _under("export", *parts)


def golden(*parts):
    """골든셋 — 사내 실문서를 인용하므로 레포가 추적하지 않는다(D-123 ①)."""
    return _under("golden", *parts)


# ---------------------------------------------------------------- 만들기
def ensure(path):
    """**폴더를 만드는 유일한 자리** — 파일 경로면 그 부모를 만든다.

    호출부가 `mkdir`을 직접 부르면 자리를 옮길 때 한 곳이 남는다(B77 ④의 실측).
    """
    p = Path(path)
    d = p if p.suffix == "" else p.parent
    d.mkdir(parents=True, exist_ok=True)
    return p
