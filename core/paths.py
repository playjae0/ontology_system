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

**배치는 1b가 옮겼다** — 상태 루트 하나 아래 다섯 단이고(`state/` 기본 ·
`ONTO_HOME`이 있으면 그 아래 · `USE_MOCK=1`이면 `state_mock/`), 옛 배치(레포 루트의
`data/`·`review/`·`parsed/`…)는 **읽지 않는다**: 감지하면 `platform migrate`를
가리키며 멈춘다(`core/migrate.py`). 조용히 옛 자리를 읽는 길은 없다.

**`mkdir`은 이 파일에만 있다**(B77 ④의 연장) — 폴더를 만드는 코드가 흩어지면 자리를
옮길 때 한 곳이 남아 옛 자리를 되살린다.
"""
from __future__ import annotations

import os
from pathlib import Path

# 레포 루트 — **코드의 자리**다. 상태의 자리와 구분한다(그것이 이 모듈의 요점이다).
ROOT = Path(__file__).resolve().parent.parent

HOME_ENV = "ONTO_HOME"

# 기본 상태 루트 — **코드 폴더 안이지만 코드가 아니다**(`.gitignore`). 사내는
# `ONTO_HOME`으로 코드 밖에 둔다: 그러면 코드 교체가 상태를 건드리지 않는다.
DEFAULT_HOME = "state"
# **mock은 자리로 가른다**(B78 1b · 사용자 확정 2026-09-17). 이름만 다른 것이 아니라
# **루트가 다르다** — `USE_MOCK=1`은 `ONTO_HOME`을 무시하고 여기로 간다.
# 회귀·doctor·`init --fresh`가 전부 이 아래서 돌아 운영 상태에 한 바이트도 쓰지 않는다.
MOCK_HOME = "state_mock"

_HOME = None            # 프로세스당 한 번 정한다 — 아래 `home()` 참조


def home():
    """상태 루트 — **프로세스당 한 번** 정한다.

    규칙 셋(순서가 규율이다):
      ① `USE_MOCK=1`(기본)이면 `./state_mock` — `ONTO_HOME`을 **무시한다.**
         mock 산출이 운영 상태에 섞이는 길을 자리에서 끊는다.
      ② `ONTO_HOME`이 있으면 그 아래.
      ③ 없으면 레포 루트의 `./state`.

    **한 번만 정하는 이유**: 모드는 프로세스 시작에 정해지고(진입점이 판독한다),
    실행 도중에 루트가 바뀌면 앞 단계가 쓴 자리와 뒤 단계가 읽는 자리가 갈린다.
    시험이 모드를 갈아 끼우는 자리(`llm.use_mock`를 스텁으로 바꾸는 회귀)에서도
    상태가 따라 움직이지 않아야 한다 — `reset()`이 그 문을 명시적으로 연다.
    """
    global _HOME
    if _HOME is None:
        from . import llm            # 함수 안 import — 모듈 수준 순환을 만들지 않는다
        if llm.use_mock():
            _HOME = ROOT / MOCK_HOME
        else:
            v = os.environ.get(HOME_ENV)
            _HOME = (Path(v).expanduser().resolve() if v
                     else ROOT / DEFAULT_HOME)
    return _HOME


def reset():
    """루트 판정을 다시 하게 한다 — **시험과 `migrate`의 문**이다."""
    global _HOME
    _HOME = None
    return home()


def is_mock_home():
    """지금 루트가 mock 자리인가 — 화면이 모드와 자리를 함께 말한다(B78 1b)."""
    return home().name == MOCK_HOME


def _under(name, *parts):
    return home().joinpath(name, *parts)


# ---------------------------------------------------------------- ②등록
def registry(*parts):
    """등록 단 — **사람 승인 1회의 산출**. 재생성되지 않고 백업 1순위다.

    한 폴더에 넷이 모인다: `doc_types.json` · `adapters/<dt>.py` ·
    `schemas/<dt>.json` · `review/<dt>/`. 옛 배치에서 넷이 흩어져 있었고, 그래서
    「코드를 새로 가져오면 `review`·`data`를 다 옮겨야」 했다.
    """
    return _under("registry", *parts)


def review(*parts):
    """`registry/review/<doc_type>/` — 등록 작업·승인 기록."""
    return registry("review", *parts)


def adapters(*parts):
    """확정 어댑터의 정본 자리(문서 6 §6.4·§6.5)."""
    return registry("adapters", *parts)


def schemas(*parts):
    """등록된 매칭 스키마. **내장 mock 스키마는 여기 오지 않는다**(자리로 가른다)."""
    return registry("schemas", *parts)


def fixture_schemas(*parts):
    """내장(mock) 스키마의 자리 — `tests/fixtures/schemas/`.

    **모드가 아니라 자리가 가른다**(B78 1b): 등록은 `registry/`만 읽고 내장은
    픽스처 폴더만 읽는다 — 섞일 자리가 없다. 구판은 같은 폴더에 두고
    `use_mock()` 분기로 갈랐고, 그래서 「mock이 이름만 다르게 숨어 있다」였다.

    뿌리는 **mock 소재 단일 지점**(`core/fixtures.py`)에서 받는다 — `ONTO_FIXTURES`로
    픽스처를 통째로 갈아 끼우는 손잡이가 여기서도 같이 돌아야 한다.
    """
    from . import fixtures
    return fixtures.ROOT_DIR.joinpath("schemas", *parts)


def config_file(name="llm.json"):
    """설정 파일의 **상태 루트 자리** — `core/llm.py`가 찾는 넷째 자리다(B78 1b).

    **`home()`을 부르지 않는다.** `home()`은 `llm.use_mock()`을 묻고 `llm`의 설정
    판독이 이 함수를 부르므로, 여기서 `home()`을 부르면 서로를 기다린다. 그래서
    `ONTO_HOME`만 직접 읽는다 — 설정은 mock 세계의 것이 아니라 어느 모드에서나
    같은 자리다.
    """
    v = os.environ.get(HOME_ENV)
    base = Path(v).expanduser().resolve() if v else ROOT / DEFAULT_HOME
    return base / name


def blocks():
    """공용 블록 — **레포 자산**이다(등록 산출이 아니다 · git이 추적한다)."""
    return ROOT / "schemas" / "blocks.json"


# ---------------------------------------------------------------- ③진실
def data(*parts):
    """진실 단 — 그래프·사전·청크·큐·대장. 누적이고 백업 대상이다(§7.7)."""
    return _under("data", *parts)


# ---------------------------------------------------------------- ④작업·장부
def work(*parts):
    """작업 단 — **재생성 가능한** 단계 산출·장부·로그.

    가르는 기준(허브 확정 2026-09-17): 사람 판단이 실렸거나 재생성이 곧 재판정인
    것은 `data/`, **로그·체크포인트·장부는 `work/`**다.
    """
    return _under("work", *parts)


def parsed(*parts):
    """계약 JSON — 파서/에이전트 경계(파일 존재 = 파싱 완료)."""
    return work("parsed", *parts)


def extract(*parts):
    """추출 체크포인트(파일 존재 = 추출 완료) · 구조 지도 보존."""
    return work("extract", *parts)


# ---------------------------------------------------------------- ⑤파생·골든셋
def export(*parts):
    """파생물 — 되돌려 읽지 않는다(문서 1)."""
    return _under("export", *parts)


def golden(*parts):
    """골든셋 — 사내 실문서를 인용하므로 레포가 추적하지 않는다(D-123 ①)."""
    return _under("golden", *parts)


# ---------------------------------------------------------------- 만들기
def bind_parser():
    """**파서에 자리를 주입한다** — 방향을 뒤집는 자리(B78 1b · 허브 확정 2026-09-17).

    파서는 `core`를 import하지 않는다(문서 6 §6.7 외부 전달물 경계). 그렇다고
    파서가 제 손으로 상태 자리를 알면 자리 소유자가 둘이 되고, 상태 루트를 옮길 때
    파서만 옛 자리에 남는다 — 그래서 **경계 안에서 넣는다.** 값이 아니라 함수를
    넘기므로 `reset()` 뒤에도 파서가 따라온다.

    이 모듈을 import하면 자동으로 걸린다(아래 모듈 말미) — 부르는 곳을 기억해야
    하는 규율은 언젠가 한 진입점에서 빠진다.
    """
    from . import store
    from parser import struct_map, tagger
    struct_map.use_dir(lambda: work("struct_maps"))
    tagger.use_snapshot(lambda: data(store.SKELETON_LIST))


def ensure(path):
    """**폴더를 만드는 유일한 자리** — 파일 경로면 그 부모를 만든다.

    호출부가 `mkdir`을 직접 부르면 자리를 옮길 때 한 곳이 남는다(B77 ④의 실측).
    """
    p = Path(path)
    d = p if p.suffix == "" else p.parent
    d.mkdir(parents=True, exist_ok=True)
    return p


# **주입은 import 시점에 한 번**이다(위 `bind_parser` 머리말). 파서를 읽어 오지
# 못하는 배포는 없다 — 파서는 이 레포의 한 패키지다.
bind_parser()
