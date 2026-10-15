# -*- coding: utf-8 -*-
"""칸 4.1·4.3 — **질의 벡터 캐시** — 청크 · 노드 벡터 (B104 ②③).

질문 문장 벡터와 견줄 쪽(노드 · 청크)의 벡터를 ④작업 `work/vectors/<종류>.json`에 둔다 — **재생성 가능한
파생물**이다(`init --fresh`가 지운다 · 지워도 다음 질의가 다시 만든다). 진실(`data/`)에는 쓰지 않는다 —
질의는 읽기 전용이다(P6).

형태: `{"backend": <벡터의 판>, "kind": <종류>, "items": {id: {"ver": <재료 해시>, "v": <float32 base64>}}}`.
  · **판(`backend`)이 다르면 통째로 무효**다 — 갈래·모델이 바뀌면 다른 공간이다(`embeddings.backend_id`).
  · **재료 해시(`ver`)가 같은 항목만 재사용**하고 바뀐 몫만 다시 만든다 — 청크가 더해지면 그 몫만, 노드의
    별칭·닻까지의 길이 바뀌면 그 노드만. 사라진 id는 버린다.
  · 벡터는 float32로 접어 둔다 — 새로 만든 벡터도 **같은 접기를 거친 값**으로 쓴다(처음과 재사용의 점수가
    같아야 같은 입력 같은 순위다).

계측(`STATS[종류]`)은 질의 한 건(`begin`부터)의 만든 수 · 재사용 수 · 시간 · 판 — 화면 한 줄(`cost_line`)의 재료다.

**묶음 · 이어 저장 · 진행**(B114 ④): 만들 몫은 `BATCH`개씩 묶어 임베딩하고(로컬 모델이면 한 번에 — `embed_many`)
`SAVE_EVERY`개마다 그때까지 만든 것을 저장한다 — 끊겨도 다음 호출은 저장된 몫을 재사용하고 나머지만 만든다(재료 해시
규칙 그대로). 저장마다 진행(`core/query/status`)을 고치고 화면 손잡이 `ON_PROGRESS`(줄 하나를 받는다)를 부른다.
한 프로세스 안에서는 한 번에 하나만 만든다(잠금 — 뷰어 시작의 미리 만들기와 첫 질의가 겹쳐도 같은 몫을 두 번 만들지
않는다).
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from array import array

from core import paths
from core.llm import embeddings as E
from core.query import status
from core.state import store

#: 마지막 호출의 계측 — `{종류: {made, reused, secs, backend}}`
STATS = {}
#: 묶음 크기 · 이어 저장 간격(창작 값 — 사내 실측 전 · B114 ④)
BATCH = 32
SAVE_EVERY = 256
#: 진행 줄 손잡이 — `fn(line)` · 화면(CLI · 서버 콘솔)이 단다(core는 화면을 갖지 않는다)
ON_PROGRESS = None
_LOCK = threading.Lock()


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


def _save(kind, bid, items):
    """원자 쓰기 · 키 순서 고정(처음 만든 판과 이어 만든 판의 파일이 같다)."""
    p = paths.vectors(f"{kind}.json")
    paths.ensure(p)
    store.atomic_write_bytes(p, json.dumps({"backend": bid, "kind": kind,
                                            "items": {k: items[k] for k in sorted(items)}},
                                           ensure_ascii=False).encode("utf-8"))


def _split(kind, texts, bid):
    """재사용할 것과 만들 것 — `(items, todo[(id, ver)], old)`."""
    old = _load(kind, bid)
    items, todo = {}, []
    for i in sorted(texts):
        ver = _ver(texts[i])
        hit = old.get(i)
        if hit and hit.get("ver") == ver:
            items[i] = hit
        else:
            todo.append((i, ver))
    return items, todo, old


def plan(jobs):
    """`[(종류, {id: 재료})]`의 진행 계획을 먼저 세운다 — 줄이 처음부터 두 종류의 분모를 말한다(쓰기 0 · 임베딩 0)."""
    bid = E.backend_id()
    out = {}
    for kind, texts in jobs:
        items, _todo, _old = _split(kind, texts, bid)
        out[kind] = (len(items), len(texts))
    status.vec_plan(out)
    return out


def vectors(kind, texts):
    """`{id: 재료 텍스트}` → `{id: 벡터}` — 재료 해시가 같으면 캐시 · 바뀐 몫만 임베딩(묶음 · 이어 저장) · 바뀐 것이
    있을 때만 쓴다."""
    with _LOCK:
        return _vectors(kind, texts)


def _vectors(kind, texts):
    bid = E.backend_id()
    items, todo, old = _split(kind, texts, bid)
    t0 = time.perf_counter()
    for s in range(0, len(todo), SAVE_EVERY):
        part = todo[s:s + SAVE_EVERY]
        for (i, ver), v in zip(part, E.embed_many([texts[i] for i, _ in part], BATCH)):
            items[i] = {"ver": ver, "v": _enc(v)}
        _save(kind, bid, items)            # 이어 저장 — 끊겨도 여기까지는 다음 호출이 재사용한다
        status.vec_step(kind, len(items), len(texts), len(part))
        if ON_PROGRESS is not None:
            ON_PROGRESS(status.vec_line())
    if not todo and set(old) != set(items):
        _save(kind, bid, items)            # 사라진 id만 버린다
    out = {i: _dec(items[i]["v"]) for i in sorted(texts)}
    # 한 질의 안의 합(B114 ④ — 벡터 준비가 만들고 링킹 · 문서 검색은 재사용한다 · 질의 머리에서 `begin`이 비운다)
    prev = STATS.get(kind) if STATS.get(kind, {}).get("backend") == bid else None
    made = len(todo) + (prev["made"] if prev else 0)
    STATS[kind] = {"made": made, "reused": max(0, len(texts) - made),
                   "secs": round(time.perf_counter() - t0 + (prev["secs"] if prev else 0), 2), "backend": bid}
    return out


def begin():
    """질의 한 건의 계측을 비운다 — `cost_line`은 그 질의의 만든 수 · 재사용 수다."""
    STATS.clear()


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
