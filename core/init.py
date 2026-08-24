# -*- coding: utf-8 -*-
"""클린 상태를 만드는 **단일 정의** — `run.py init [--fresh]` (문서 7 §7.6-4).

**왜 진입점이어야 하나.** 클린 판정이 걸린 곳이 둘이다 — 회귀 규약(§7.5-7 "클린 상태
단독 실행")과 완료판정 4번("클린 2회 동일 그래프"). 클린을 `rm -rf data`로 각자
만들면 "클린"의 정의가 실행마다 달라져 두 판정이 서로 다른 바닥 위에서 내려진다.
실제로 이 레포는 그 상태였다 — doctor와 테스트 10종이 `shutil.rmtree`를 제 손으로
반복하고, 그 결과 클린이 **"파일 없음"**이었다.

**빈 상태는 "파일 없음"이 아니라 "빈 파일"이다**(§7.2 말미). 그 형태가 아래 `EMPTY`다.
읽기 코드가 `read(name, default)`로 기본값을 갖고 있어 둘이 대체로 같게 동작하지만,
**대체로 같은 것은 판정의 바닥이 될 수 없다.**

    python run.py init            빈 상태를 만든다 (있으면 그대로 둔다)
    python run.py init --fresh    지우고 다시 만든다
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import log, store
from .graph import GraphStore
from router import discover

ROOT = Path(__file__).resolve().parent.parent
_LOG = log.get(__name__)

# 실행 산출물 디렉터리 — 버전 추적하지 않는다(§7.8). data/만 진실이고 나머지는 파생·세션 산출.
WIPE = ("data", "extract", "review", "export")

# 빈 상태의 형태 — 문서 7 §7.2 말미가 정본이다.
EMPTY = {
    store.CHUNKS: {"chunks": {}, "describes": []},
    store.DICTIONARY: {},
    store.QUEUE: [],
}


def fresh():
    """실행 산출물 4종을 지운다. **`data/`도 지운다** — 클린의 정의가 그것이다."""
    for d in WIPE:
        shutil.rmtree(ROOT / d, ignore_errors=True)


def ensure():
    """빈 상태를 만든다 — 이미 있는 파일은 건드리지 않는다.

    층 그래프는 `GraphStore` 경유로 만든다(문서 1 B6) — **저장 파일의 경로도 이름도
    이 모듈이 알지 않는다.** 경로를 직접 조립하면 저장 계층 경계가 "여는 코드"만 막고
    "저장 위치를 아는 코드"를 놓친 상태로 되돌아간다 — 회귀 st가 그것을 잡는다.
    """
    store.DATA.mkdir(parents=True, exist_ok=True)
    made = []
    for name, empty in EMPTY.items():
        if not store.path(name).exists():
            store.write(name, empty)
            made.append(name)
    for layer in discover():
        g = GraphStore.for_layer(layer)
        if not g.exists():
            g.load()                 # nodes={}, edges=[]
            g.save()
            made.append(f"{layer} 그래프")
    return made


def init(fresh_=False):
    if fresh_:
        fresh()
    made = ensure()
    _LOG.info("init%s — 빈 상태 %d개 생성 (%s)",
              " --fresh" if fresh_ else "", len(made), ", ".join(made) or "없음")
    return made
