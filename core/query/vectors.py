# -*- coding: utf-8 -*-
"""칸 4.1·4.3 — **질의 벡터 저장** — 청크 · 노드 벡터 (B104 ②③ · B136 ③).

질문 문장 벡터와 견줄 쪽(노드 · 청크)의 벡터를 ④작업 `work/vectors/vectors.sqlite` 하나에 둔다 — **파생물**이다(진실 `data/`에
쓰지 않는다 · 질의는 읽기 전용 — P6) · **기본 fresh가 남긴다**(보존 일곱 — 재구축에도 다시 쓴다 · 클린 `--fresh --all`은 지운다).

형태: 표 `v(backend, ver, kind, v)` — **열쇠 = 판(`backend` — 임베딩 갈래 · 모델) + 글 해시(`ver`)**(내용 주소).
  · 재구축으로 노드 id가 바뀌어도 **글이 같으면 다시 쓴다** · 판이 다르면 다른 공간이다(`embeddings.backend_id`).
  · 바뀐 글만 새로 만든다 — 청크가 더해지면 그 몫만, 노드의 이름 · 별칭 · 닻까지의 길이 바뀌면 그 노드만.
  · 벡터는 float32로 접어 둔다 — 새로 만든 벡터도 **같은 접기를 거친 값**으로 쓴다(처음과 재사용의 점수가 같아야 같은 입력 같은 순위다).
  · **통째로 다시 쓰기 0 · 프로세스 사이 동시 쓰기 안전**(sqlite 파일 잠금 · 기다림 30초 · `INSERT OR IGNORE` · 묶음마다 커밋 — 뷰어의
    미리 만들기 · `run.py vectors` · 질의가 함께 쓴다) · 끊겨도 커밋한 묶음까지는 남는다(깨진 파일 0) · 일지는 기본(되돌림 일지 —
    읽는 쪽이 파일을 건드리지 않는다: WAL은 읽기도 공유 메모리 파일을 고친다).
  · 옛 `work/vectors/<종류>.json`(B136 전)이 있으면 쓰는 길이 처음 열 때 한 번 옮겨 담고 지운다(사내 청크 벡터를 다시 만들지 않게).

계측(`STATS[종류]`)은 질의 한 건(`begin`부터)의 만든 수 · 재사용 수 · 시간 · 판 · 넘어 자른 글 수 · 가장 긴 길이 — 화면 한 줄
(`cost_line` · `fit_line`)의 재료다.

**입력 한도**(B153 ③): 재료는 저장 열쇠를 셈하기 전에 한도 안으로 맞춘다(`embeddings.fit` — 앞을 지키고 꼬리를 자른다) — 열쇠는
**자른 뒤의 글**이라 같은 입력은 같은 벡터 · 다시 쓰기 그대로다.

**묶음 · 이어 저장 · 진행**(B114 ④): 만들 몫은 `BATCH`개씩 묶어 임베딩하고(로컬 모델이면 한 번에 — `embed_many`)
`SAVE_EVERY`개마다 커밋한다 — 끊겨도 다음 호출은 저장된 몫을 재사용하고 나머지만 만든다. 저장마다 진행(`core/query/status`)을
고치고 화면 손잡이 `ON_PROGRESS`(줄 하나를 받는다)를 부른다. 한 프로세스 안에서는 한 번에 하나만 만든다(잠금 — 같은 몫을 두 번
만들지 않는다 · 프로세스 사이는 저장이 받는다). 읽기 전용 조회(`lookup`)는 저장을 열기만 한다(만들지 않는다 — `show near`).
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
import time
from array import array

from core import paths
from core.llm import embeddings as E
from core.query import status

#: 마지막 호출의 계측 — `{종류: {made, reused, secs, backend, cut, longest}}`
STATS = {}
_KIND = {"nodes": "노드", "chunks": "청크"}
#: 묶음 크기 · 이어 저장(커밋) 간격(창작 값 — 사내 실측 전 · B114 ④)
BATCH = 32
SAVE_EVERY = 256
#: 진행 줄 손잡이 — `fn(line)` · 화면(CLI · 서버 콘솔)이 단다(core는 화면을 갖지 않는다)
ON_PROGRESS = None
#: 저장 파일 이름(`work/vectors/` 안)
DB = "vectors.sqlite"
_LOCK = threading.Lock()
_CHUNK = 500                                # IN 절 한 번에 묻는 열쇠 수


def _ver(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _pack(v):
    return array("f", v).tobytes()


def _unpack(b):
    a = array("f")
    a.frombytes(b)
    return list(a)


def _open(write=True):
    """저장 연결 — 쓰는 길은 자리를 만들고 표를 세우고 옛 JSON을 옮겨 담는다 · 읽는 길은 없으면 None(만들지 않는다)."""
    p = paths.vectors(DB)
    if not write:
        if not p.exists():
            return None
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
    paths.ensure(p)
    con = sqlite3.connect(str(p), timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS v (backend TEXT NOT NULL, ver TEXT NOT NULL, kind TEXT NOT NULL, "
                "v BLOB NOT NULL, PRIMARY KEY (backend, ver))")
    _migrate(con)
    return con


def _migrate(con):
    """옛 `work/vectors/<종류>.json`을 한 번 옮겨 담고 지운다 — 판 · 글 해시 · 벡터 그대로(다시 만들지 않는다)."""
    for kind in ("nodes", "chunks"):
        old = paths.vectors(f"{kind}.json")
        if not old.exists():
            continue
        try:
            d = json.loads(old.read_text(encoding="utf-8"))
            rows = [(d.get("backend"), it["ver"], kind, base64.b64decode(it["v"]))
                    for it in (d.get("items") or {}).values() if it.get("ver") and it.get("v")]
        except (ValueError, OSError, KeyError, TypeError):
            rows = []                              # 깨진 옛 캐시는 없는 것과 같다(파생물)
        with con:
            con.executemany("INSERT OR IGNORE INTO v VALUES (?, ?, ?, ?)", [r for r in rows if r[0]])
        old.unlink(missing_ok=True)


def _get(con, bid, vers):
    """`{글 해시: 벡터 바이트}` — 있는 것만."""
    out, vs = {}, sorted(set(vers))
    for s in range(0, len(vs), _CHUNK):
        part = vs[s:s + _CHUNK]
        q = f"SELECT ver, v FROM v WHERE backend = ? AND ver IN ({','.join('?' * len(part))})"
        out.update(dict(con.execute(q, [bid, *part]).fetchall()))
    return out


def _fitted(texts):
    """한도 안의 재료 — `({id: 맞춘 글}, 넘어 자른 수, 자른 글 중 가장 긴 원래 길이)` (B153 ③)."""
    lim = E.limit()
    out, cut, longest = {}, 0, 0
    for i, t in texts.items():
        out[i], n, was = E.fit(t, lim)
        if was:
            cut, longest = cut + 1, max(longest, n)
    return out, cut, longest


def _split(con, texts, bid):
    """재사용할 것과 만들 것 — `({id: 벡터 바이트}, todo[(id, ver)])`(같은 글은 한 번만 만든다)."""
    vers = {i: _ver(texts[i]) for i in texts}
    have = _get(con, bid, vers.values()) if con is not None else {}
    items, todo, seen = {}, [], set()
    for i in sorted(texts):
        if vers[i] in have:
            items[i] = have[vers[i]]
        elif vers[i] not in seen:
            seen.add(vers[i])
            todo.append((i, vers[i]))
    return items, todo, vers


def lookup(kind, texts):
    """**읽기 전용** — `{id: 벡터}` 저장에 있는 것만(만들지 않는다 · 쓰기 0 · 저장이 없으면 빈 dict)."""
    con = _open(write=False)
    if con is None:
        return {}
    try:
        items, _todo, _v = _split(con, _fitted(texts)[0], E.backend_id())
    finally:
        con.close()
    return {i: _unpack(b) for i, b in items.items()}


def count(kind=None):
    """지금 판의 저장 수(종류를 주면 그 종류만) — 저장이 없으면 0."""
    con = _open(write=False)
    if con is None:
        return 0
    try:
        q = "SELECT COUNT(*) FROM v WHERE backend = ?" + (" AND kind = ?" if kind else "")
        return con.execute(q, [E.backend_id(), *([kind] if kind else [])]).fetchone()[0]
    finally:
        con.close()


def fingerprint(kind=None):
    """지금 판 저장의 지문 — 글 해시 → 벡터 해시(시험이 「이어 만든 저장 = 처음부터 만든 저장」을 잰다)."""
    con = _open(write=False)
    if con is None:
        return {}
    try:
        q = "SELECT ver, v FROM v WHERE backend = ?" + (" AND kind = ?" if kind else "")
        return {ver: hashlib.sha256(b).hexdigest()[:16] for ver, b in con.execute(q, [E.backend_id(), *([kind] if kind else [])])}
    finally:
        con.close()


def plan(jobs):
    """`[(종류, {id: 재료})]`의 진행 계획을 먼저 세운다 — 줄이 처음부터 두 종류의 분모를 말한다(임베딩 0 · 저장은 읽기만)."""
    bid = E.backend_id()
    con = _open(write=False)
    out = {}
    try:
        for kind, texts in jobs:
            items, _todo, _v = _split(con, _fitted(texts)[0], bid)
            out[kind] = (len(items), len(texts))
    finally:
        if con is not None:
            con.close()
    status.vec_plan(out)
    return out


def vectors(kind, texts):
    """`{id: 재료 텍스트}` → `{id: 벡터}` — 글 해시가 같으면 저장 · 바뀐 몫만 임베딩(묶음 · 묶음마다 커밋)."""
    with _LOCK:
        return _vectors(kind, texts)


def _vectors(kind, texts):
    bid = E.backend_id()
    texts, cut, longest = _fitted(texts)
    con = _open()
    try:
        items, todo, vers = _split(con, texts, bid)
        t0 = time.perf_counter()
        for s in range(0, len(todo), SAVE_EVERY):
            part = todo[s:s + SAVE_EVERY]
            rows = [(bid, ver, kind, _pack(v)) for (_i, ver), v in zip(part, E.embed_many([texts[i] for i, _ in part], BATCH))]
            with con:                              # 이어 저장 — 끊겨도 여기까지는 다음 호출이 재사용한다
                con.executemany("INSERT OR IGNORE INTO v VALUES (?, ?, ?, ?)", rows)
            made = {ver: b for _b, ver, _k, b in rows}
            for i in texts:
                if i not in items and vers[i] in made:
                    items[i] = made[vers[i]]
            status.vec_step(kind, len(items), len(texts), len(part))
            if ON_PROGRESS is not None:
                ON_PROGRESS(status.vec_line())
    finally:
        con.close()
    out = {i: _unpack(items[i]) for i in sorted(texts)}
    # 한 질의 안의 합(B114 ④ — 벡터 준비가 만들고 링킹 · 문서 검색은 재사용한다 · 질의 머리에서 `begin`이 비운다)
    fresh = sum(1 for i in texts if vers[i] in {ver for _i, ver in todo})
    prev = STATS.get(kind) if STATS.get(kind, {}).get("backend") == bid else None
    made_n = fresh + (prev["made"] if prev else 0)
    STATS[kind] = {"made": made_n, "reused": max(0, len(texts) - made_n),
                   "secs": round(time.perf_counter() - t0 + (prev["secs"] if prev else 0), 2), "backend": bid,
                   "cut": cut, "longest": longest}
    return out


def begin():
    """질의 한 건의 계측을 비운다 — `cost_line`은 그 질의의 만든 수 · 재사용 수다."""
    STATS.clear()


def question(text):
    """질문 문장의 벡터 — 저장하지 않는다(같은 접기만 거친다)."""
    return _unpack(_pack(E.embed(text)))


def fit_line(stats=None):
    """한도 한 조각 — `한도 <n><단위>(<출처>) · 넘어 자른 글 — 노드 a · 청크 b(가장 긴 m)` · 0이면 `… · 넘은 글 0` (B153 ③)."""
    s = STATS if stats is None else stats
    lim = E.limit()
    head = f"한도 {lim['n']:,}{lim['unit']}({lim['from']})" + (f" · {lim['note']}" if lim["note"] else "")
    if not any(v.get("cut") for v in s.values()):
        return f"{head} · 넘은 글 0"
    parts = " · ".join(f"{_KIND.get(k, k)} {v.get('cut', 0):,}" for k, v in sorted(s.items(), reverse=True))
    return f"{head} · 넘어 자른 글 — {parts}(가장 긴 {max(v.get('longest', 0) for v in s.values()):,}{lim['unit']})"


def cost_line():
    """벡터 한 줄 — `벡터 — 노드 만든 a · 재사용 b · 청크 만든 c · 재사용 d · <판> · n.n초 · <한도 조각>` (마지막 질의 · 없으면 빈 문자열)."""
    if not STATS:
        return ""
    parts = [f"{_KIND.get(k, k)} 만든 {s['made']:,} · 재사용 {s['reused']:,}"
             for k, s in sorted(STATS.items(), reverse=True)]
    bid = next(iter(STATS.values()))["backend"]
    return (f"벡터 — {' · '.join(parts)} · {bid} · "
            f"{sum(s['secs'] for s in STATS.values()):.1f}초" + (f" · {E.cost_line()}" if E.cost_line() else "")
            + f" · {fit_line()}")
