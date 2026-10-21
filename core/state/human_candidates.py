# -*- coding: utf-8 -*-
"""칸 0.3 — **사람 후보 기록** — 사람이 [5/8]에서 살린 이름 없는 대상 (B140 ④).

자리는 ②등록 `registry/human_candidates.json`이다 — 사람 판단이라 재생성되지 않고 `init --fresh`(기본 · `--all`)에도 산다
(원자 쓰기). 모양: `{"docs": {doc_id: [기록 …]}}` · 기록은 이름으로 남는다(노드 id가 아니다 — 재구축 뒤에도 읽힌다 · `ops_log`와
같은 결):

  · 새것    `{kind: "새것", name, category, upper: {name, category, kind: 제목 개체 | 노드 | 골격}, by, at}`
  · 같은 것 `{kind: "같은 것", name, target: {name, layer, category}, by, at}`

관문은 OK 즉시 쓴다 — 그래프는 [6/8]이 쓴다(추출 후보에 한 줄 · `core/build/human.apply`). 지우기는 그 문서 목록에서 번호로.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from core import paths
from core.state import store

NEW, SAME = "새것", "같은 것"
#: 위 노드의 종류(닫힌 셋)
UPPER_KINDS = ("제목 개체", "노드", "골격")
#: 기록의 행위자 — 인입 관문의 답(사람이 친 답 · 행위자 이름을 받지 않는 자리)
BY = "관문"


def path():
    return paths.registry("human_candidates.json")


def load():
    p = path()
    if not p.exists():
        return {"docs": {}}
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("docs", {})
    return d


def _save(d):
    store.atomic_write_bytes(path(), (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def of(doc_id):
    """그 문서의 기록 — 쓴 차례 그대로(없으면 빈 목록)."""
    return list(load()["docs"].get(doc_id) or [])


def names():
    """모든 문서의 새것 · 같은 것 이름 — `{정규화 이름}`(마무리의 재연결 셈)."""
    from core.state.ids import norm
    return {norm(r["name"]) for recs in load()["docs"].values() for r in recs if r.get("name")}


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def add(doc_id, rec):
    """기록 하나를 더한다 — 같은 이름의 기록은 갈아 끼운다(뒤의 판단이 이긴다) · 돌려주는 것은 그 문서 목록."""
    from core.state.ids import norm
    d = load()
    recs = [r for r in d["docs"].get(doc_id) or [] if norm(r.get("name") or "") != norm(rec["name"])]
    recs.append({**rec, "by": rec.get("by") or BY, "at": rec.get("at") or _now()})
    d["docs"][doc_id] = recs
    _save(d)
    return recs


def drop(doc_id, i):
    """그 문서 목록의 `i`번째(1부터)를 걷는다 — 걷은 기록 · 없으면 None(쓰기 0)."""
    d = load()
    recs = list(d["docs"].get(doc_id) or [])
    if not 1 <= i <= len(recs):
        return None
    gone = recs.pop(i - 1)
    if recs:
        d["docs"][doc_id] = recs
    else:
        d["docs"].pop(doc_id, None)
    _save(d)
    return gone
