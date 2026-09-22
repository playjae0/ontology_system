# -*- coding: utf-8 -*-
"""칸 0.4 — 임베딩 — `embed(text) -> vector` (문서 7 §7.6-B-1 게이트웨이 2파일).

USE_MOCK=1의 대체는 **sha256 해시 → 정규화 벡터**다(§7.1 대체 표). 결정성이
우선이라 그렇게 정한다 — mock의 목적은 메커니즘 검증 한정이고(§7.5-1) 가짜
데이터의 유사도 점수는 가짜 확신이다.

**판정용 임베딩은 저장하지 않는다**(§7.2 — 재계산 파생물). 청크 인덱스는
재생성 캐시이므로 여기서 캐시 파일을 만들지 않는다.

설정 접근은 `core/llm/gateway.py`로 수렴한다 — 이 파일은 게이트웨이 주소·인증을 직접
읽지 않는다.
"""
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

from core.llm import gateway

DIM = 64            # mock 벡터 차원. 실호출 갈래의 차원은 모델이 정한다.

_LOG = gateway.log.get(__name__)

#: 닫힌 2종 — `gateway`(API) · `local`(디스크의 모델 폴더). 다른 값은 명시적 실패다.
BACKENDS = ("gateway", "local")

#: 로컬 모델은 **프로세스당 한 번** 로드한다 — `(경로, 모델)`.
#: 매 호출 로드하면 판정 하나에 수 초가 붙는다(`paths.home()`과 같은 규율).
_LOCAL = (None, None)

#: 마지막 실행의 계측 — **화면이 비용을 숫자로 보이게** (B80 ③ 개정).
#: GPU를 요구하지 않는다(CPU 자동) — 대신 「CPU로 돌고 있고 얼마 걸린다」를 말한다.
STATS = {"backend": None, "device": None, "load_s": None, "encode_ms": None,
         "dim": None}


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


def model_dir(raw):
    """`EMBED_MODEL`을 **폴더 경로**로 읽는다 — `~`·상대 허용(`paths`와 같은 규칙)."""
    return Path(str(raw)).expanduser().resolve()


def _local_model(raw):
    """로컬 임베딩 모델 — **지연 import · 프로세스당 1회 로드** (B80 ③).

    `sentence_transformers`는 **선택 의존**이다(`parser/reader.py`의 `openpyxl`과 같은
    결): 함수 안에서 import하므로 `USE_MOCK=1` 경로는 이 패키지를 건드리지 않고,
    코어 필수 외부 의존 0이 유지된다.

    없는 것은 **조용히 넘기지 않는다** — 패키지가 없거나 폴더가 없으면 명시적
    실패다. `CANDIDATE_NARROW=auto`의 겹침 폴백은 **`EMBED_MODEL` 미설정**일 때의
    길이고(B75 ①), 설정해 놓고 못 부르는 것은 실패다.
    """
    global _LOCAL
    path = model_dir(raw)
    if _LOCAL[0] == path and _LOCAL[1] is not None:
        return _LOCAL[1]
    if not path.is_dir():
        reason = (f"EMBED_BACKEND=local인데 모델 폴더가 없다: {path} — "
                  f"EMBED_MODEL에 로컬 모델 폴더 경로를 적는다"
                  f"(게이트웨이 API를 쓰려면 EMBED_BACKEND=gateway)")
        gateway.log.explicit_fail(_LOG, "core.llm[embed]", reason)
        raise gateway.NotConfigured(reason)
    try:
        from sentence_transformers import SentenceTransformer   # 선택 의존 · 지연 import
    except ImportError as e:
        reason = ("EMBED_BACKEND=local인데 sentence-transformers가 없다 — "
                  "pip install sentence-transformers · "
                  "또는 EMBED_BACKEND=gateway")
        gateway.log.explicit_fail(_LOG, "core.llm[embed]", reason)
        raise gateway.NotConfigured(reason) from e
    t0 = time.perf_counter()
    model = SentenceTransformer(str(path))
    STATS["load_s"] = round(time.perf_counter() - t0, 2)
    # **장치는 모델이 정한다** — 스텁·구판이 이 속성을 안 가질 수 있어 물어만 본다.
    STATS["device"] = str(getattr(model, "device", "?"))
    _LOCAL = (path, model)
    _LOG.info("로컬 임베딩 모델 로드 — %s · %s · %.2fs (프로세스당 1회)",
              path, STATS["device"], STATS["load_s"])
    return model


def embed(text):
    """텍스트 하나를 벡터로. **갈래가 셋이어도 반환 계약은 하나다** — `list[float]`.

    소비부는 어느 쪽인지 몰라야 한다(§7.6-B-3). 그래야 mock 회귀가 실 연결에도
    유효하다 — 차원이 다른 것은 계약 위반이 아니다(모델이 정한다), 형태가 다른
    것이 위반이다. **갈래가 갈리는 자리는 이 함수 하나다**(B80 ③).
    """
    if gateway.use_mock():
        gateway.mock("embed", f"sha256 → {DIM}차 정규화 벡터")
        return _mock_vector(text)

    backend = gateway.config().get("embed_backend") or "gateway"
    if backend not in BACKENDS:
        reason = (f"EMBED_BACKEND가 닫힌 2종 밖이다: {backend!r} — "
                  f"{' | '.join(BACKENDS)}")
        gateway.log.explicit_fail(_LOG, "core.llm[embed]", reason)
        raise gateway.NotConfigured(reason)
    if backend == "local":
        cfg = gateway.require("embed", need=("embed_model",))
        model = _local_model(cfg["embed_model"])
        t0 = time.perf_counter()
        vec = model.encode(text, normalize_embeddings=True)
        out = [float(x) for x in vec]
        STATS.update(backend="local", encode_ms=round((time.perf_counter() - t0) * 1000),
                     dim=len(out))
        return out

    cfg = gateway.require("embed", need=("embed_url", "embed_model"))
    t0 = time.perf_counter()
    raw = gateway._post(f"{cfg['embed_url']}/embeddings",
                    {"model": cfg["embed_model"], "input": text},
                    cfg["key"], cfg["timeout"])
    out = list(raw["data"][0]["embedding"])
    STATS.update(backend="gateway", device=None, load_s=None,
                 encode_ms=round((time.perf_counter() - t0) * 1000), dim=len(out))
    return out


def cost_line():
    """마지막 임베딩 1회의 **비용 한 조각** — `llm-check` ⑥이 낸다 (B80 ③ 개정).

    로컬 갈래는 GPU가 없어도 CPU로 돈다 — 그 사실과 값이 화면에 있어야 사람이
    「느린가 · 이대로 쓸 수 있나」를 판단한다(요구하는 것이 아니라 보이는 것이다).
    """
    s = STATS
    if s.get("backend") != "local":
        return f"{s.get('dim')}차 벡터" if s.get("dim") else ""
    return (f"{s.get('dim')}차 · {s.get('device')} · 로드 {s.get('load_s')}s · "
            f"인코딩 {s.get('encode_ms')}ms")


def cosine(a, b):
    """코사인 유사도 — 둘 다 단위 벡터가 아닐 수 있으므로 크기로 나눈다."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
