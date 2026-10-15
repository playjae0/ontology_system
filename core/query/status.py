# -*- coding: utf-8 -*-
"""칸 4.1 — 질의 **진행 상태** — 단계 · 경과 · 벡터 준비 (B114 ④).

질의 한 건이 어느 단계에 있는지(벡터 준비 → 링킹 → 확장 → 수집 → 답변)와 질의 벡터 캐시를 만드는 진행(노드 ·
청크 n/m · 경과 · 남은 예상)을 **한 자리**에 둔다 — 뷰어의 질의 상태 줄(GET 폴링 `/api/status`)과 CLI · 서버 콘솔의
진행 줄이 같은 값을 읽는다. 저장 0(메모리) · 쓰는 쪽은 질의 스레드 · 읽는 쪽은 폴링 스레드(잠금 하나).

남은 예상은 **이번에 만든 몫의 속도**로 센다(만든 수 / 경과 × 남은 수) — 재사용한 몫은 시간에 들지 않는다.
"""
from __future__ import annotations

import threading
import time

#: 질의 단계 — 닫힌 다섯(화면 · 로그가 이 이름 그대로)
STAGES = ("벡터 준비", "링킹", "확장", "수집", "답변")
#: 벡터 종류의 화면 이름
KIND_NAME = {"nodes": "노드", "chunks": "청크"}

_LOCK = threading.Lock()
_Q = {"active": False, "question": None, "stage": None, "seen": [], "t0": None, "t1": None}
_V = {"active": False, "kinds": {}, "t0": None, "made": 0, "todo": 0}


def begin(question):
    """질의 한 건의 시작 — 단계는 비어 있다."""
    with _LOCK:
        _Q.update(active=True, question=question, stage=None, seen=[], t0=time.perf_counter(), t1=None)


def stage(name):
    """지금 단계 — 닫힌 다섯 중 하나(밖이면 결함이다 — 화면이 모르는 이름을 내지 않는다)."""
    if name not in STAGES:
        raise ValueError(f"질의 단계가 닫힌 목록 밖이다: {name!r}")
    with _LOCK:
        _Q["stage"] = name
        if name not in _Q["seen"]:
            _Q["seen"].append(name)


def end():
    with _LOCK:
        if _Q["active"]:
            _Q.update(active=False, t1=time.perf_counter())


def vec_plan(plan):
    """벡터 준비의 계획 — `{종류: (이미 있는 수, 전체)}` · 만들 것이 하나라도 있으면 진행이 시작된다."""
    with _LOCK:
        kinds = {k: {"done": d, "total": t} for k, (d, t) in plan.items()}
        todo = sum(t - d for d, t in plan.values())
        _V.update(active=todo > 0, kinds=kinds, t0=time.perf_counter(), made=0, todo=todo)


def vec_step(kind, done, total, made):
    """한 묶음이 끝났다 — 그 종류의 지금 수(`done`/`total`) · 이번에 만든 수(`made` — 묶음 크기)."""
    with _LOCK:
        if _V["t0"] is None:
            _V.update(t0=time.perf_counter(), made=0, todo=max(0, total - done + made))
        _V["kinds"].setdefault(kind, {"done": 0, "total": total}).update(done=done, total=total)
        _V["made"] += made
        _V["active"] = any(v["done"] < v["total"] for v in _V["kinds"].values())


def _vec_view():
    v = _V
    el = (time.perf_counter() - v["t0"]) if v["t0"] is not None else 0.0
    left = max(0, v["todo"] - v["made"])
    eta = round(el / v["made"] * left, 1) if v["made"] and left else (0.0 if not left else None)
    return {"active": v["active"], "kinds": {k: dict(x) for k, x in v["kinds"].items()},
            "elapsed": round(el, 1), "made": v["made"], "todo": v["todo"], "eta": eta}


def vec_line():
    """`벡터 — 노드 n/m · 청크 n/m · 경과 s초 · 남은 예상 t초` (계획이 없으면 빈 문자열)."""
    with _LOCK:
        if not _V["kinds"]:
            return ""
        v = _vec_view()
    parts = [f"{KIND_NAME.get(k, k)} {x['done']:,}/{x['total']:,}" for k, x in sorted(
        v["kinds"].items(), key=lambda kv: list(KIND_NAME).index(kv[0]) if kv[0] in KIND_NAME else 9)]
    eta = "—" if v["eta"] is None else f"{v['eta']:.1f}초"
    return f"벡터 — {' · '.join(parts)} · 경과 {v['elapsed']:.1f}초 · 남은 예상 {eta}"


def get():
    """폴링 한 번의 답 — `{query: {active, question, stage, seen, elapsed}, vectors: {...}, line}`."""
    with _LOCK:
        q = dict(_Q)
        now = time.perf_counter()
        el = ((q["t1"] or now) - q["t0"]) if q["t0"] is not None else 0.0
        out = {"query": {"active": q["active"], "question": q["question"], "stage": q["stage"],
                         "seen": list(q["seen"]), "elapsed": round(el, 1)},
               "vectors": _vec_view() if _V["kinds"] else None, "stages": list(STAGES)}
    out["line"] = vec_line()
    return out
