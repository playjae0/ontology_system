# -*- coding: utf-8 -*-
"""임베딩 — `embed(text) -> vector` (문서 7 §7.6-B-1 게이트웨이 2파일).

USE_MOCK=1의 대체는 **sha256 해시 → 정규화 벡터**다(§7.1 대체 표). 결정성이
우선이라 그렇게 정한다 — mock의 목적은 메커니즘 검증 한정이고(§7.5-1) 가짜
데이터의 유사도 점수는 가짜 확신이다.

**판정용 임베딩은 저장하지 않는다**(§7.2 — 재계산 파생물). 청크 인덱스는
재생성 캐시이므로 여기서 캐시 파일을 만들지 않는다.

설정 접근은 `core/llm.py`로 수렴한다 — 이 파일은 게이트웨이 주소·인증을 직접
읽지 않는다.
"""
from __future__ import annotations

import hashlib
import math

from . import llm

DIM = 64            # mock 벡터 차원. 실호출 갈래의 차원은 모델이 정한다.


def _mock_vector(text, dim=DIM):
    """sha256을 늘려 dim 바이트를 뽑고 단위 벡터로 정규화한다 — **결정적**이다."""
    buf = b""
    seed = (text or "").encode("utf-8")
    i = 0
    while len(buf) < dim:
        buf += hashlib.sha256(seed + i.to_bytes(2, "big")).digest()
        i += 1
    vals = [(b - 127.5) / 127.5 for b in buf[:dim]]
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def embed(text):
    """텍스트 하나를 벡터로. **두 갈래가 같은 반환 계약을 지킨다** — `list[float]`.

    소비부는 어느 쪽인지 몰라야 한다(§7.6-B-3). 그래야 mock 회귀가 실 연결에도
    유효하다 — 차원이 다른 것은 계약 위반이 아니다(모델이 정한다), 형태가 다른
    것이 위반이다.
    """
    if llm.use_mock():
        llm.mock("embed", f"sha256 → {DIM}차 정규화 벡터")
        return _mock_vector(text)

    cfg = llm.require("embed", need=("url", "embed_model"))
    raw = llm._post(f"{cfg['url']}/embeddings",
                    {"model": cfg["embed_model"], "input": text},
                    cfg["key"], cfg["timeout"])
    return list(raw["data"][0]["embedding"])


def cosine(a, b):
    """코사인 유사도 — 둘 다 단위 벡터가 아닐 수 있으므로 크기로 나눈다."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
