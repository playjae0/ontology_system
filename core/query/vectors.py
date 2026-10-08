# -*- coding: utf-8 -*-
"""칸 4.2 — **질의 벡터 캐시** — 청크 · 노드 벡터 (B104 ②③).

질문 문장 벡터와 견줄 쪽(노드 · 청크)의 벡터를 ④작업 `work/vectors/<종류>.json`에 둔다 — **재생성 가능한
파생물**이다(`init --fresh`가 지운다 · 지워도 다음 질의가 다시 만든다). 진실(`data/`)에는 쓰지 않는다 —
질의는 읽기 전용이다(P6).

형태: `{"backend": <벡터의 판>, "kind": <종류>, "items": {id: {"ver": <재료 해시>, "v": <float32 base64>}}}`.
  · **판(`backend`)이 다르면 통째로 무효**다 — 갈래·모델이 바뀌면 다른 공간이다(`embeddings.backend_id`).
  · **재료 해시(`ver`)가 같은 항목만 재사용**하고 바뀐 몫만 다시 만든다 — 청크가 더해지면 그 몫만, 노드의
    별칭·닻까지의 길이 바뀌면 그 노드만. 사라진 id는 버린다.
  · 벡터는 float32로 접어 둔다 — 새로 만든 벡터도 **같은 접기를 거친 값**으로 쓴다(처음과 재사용의 점수가
    같아야 같은 입력 같은 순위다).

계측(`STATS[종류]`)은 마지막 호출의 만든 수 · 재사용 수 · 시간 · 판 — 화면 한 줄(`cost_line`)의 재료다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from array import array

from core import paths
from core.llm import embeddings as E
from core.state import store

#: 마지막 호출의 계측 — `{종류: {made, reused, secs, backend}}`
STATS = {}


def _ver(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _enc(v):
    return base64.b64encode(array("f", v).tobytes()).decode("ascii")


def _dec(s):
    a = array("f")
    a.frombytes(base64.b64decode(s))
    return list(a)


def _load(kind, bid):
    p = paths.vectors(f"{kind}.json")
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}                          # 깨진 캐시는 없는 것과 같다 — 다시 만든다(파생물)
    return (d.get("items") or {}) if d.get("backend") == bid else {}


def vectors(kind, texts):
    """`{id: 재료 텍스트}` → `{id: 벡터}` — 재료 해시가 같으면 캐시 · 바뀐 몫만 임베딩 · 바뀐 것이 있을 때만 쓴다."""
    bid = E.backend_id()
    old = _load(kind, bid)
    out, items, made = {}, {}, 0
    t0 = time.perf_counter()
    for i in sorted(texts):
        ver = _ver(texts[i])
        hit = old.get(i)
        if hit and hit.get("ver") == ver:
            items[i] = hit
        else:
            items[i] = {"ver": ver, "v": _enc(E.embed(texts[i]))}
            made += 1
        out[i] = _dec(items[i]["v"])
    if made or set(old) != set(items):
        p = paths.vectors(f"{kind}.json")
        paths.ensure(p)
        store.atomic_write_bytes(p, json.dumps({"backend": bid, "kind": kind, "items": items},
                                               ensure_ascii=False).encode("utf-8"))
    STATS[kind] = {"made": made, "reused": len(items) - made,
                   "secs": round(time.perf_counter() - t0, 2), "backend": bid}
    return out


def question(text):
    """질문 문장의 벡터 — 캐시하지 않는다(같은 접기만 거친다)."""
    return _dec(_enc(E.embed(text)))


def cost_line():
    """벡터 한 줄 — `벡터 — 노드 만든 a · 재사용 b · 청크 만든 c · 재사용 d · <판> · n.n초` (마지막 질의 · 없으면 빈 문자열)."""
    if not STATS:
        return ""
    parts = [f"{ {'nodes': '노드', 'chunks': '청크'}.get(k, k)} 만든 {s['made']:,} · 재사용 {s['reused']:,}"
             for k, s in sorted(STATS.items(), reverse=True)]
    bid = next(iter(STATS.values()))["backend"]
    return (f"벡터 — {' · '.join(parts)} · {bid} · "
            f"{sum(s['secs'] for s in STATS.values()):.1f}초" + (f" · {E.cost_line()}" if E.cost_line() else ""))
