# -*- coding: utf-8 -*-
"""칸 3.4 — 판정 대장 — **문서마다, 값마다, 어떻게 해소했는가** (B74 ② · 문서 7 §7.8).

    data/ingest_log/{doc_id}.json

정본이 아니라 **장부**다: 재인입이 덮고, 그래프를 되돌려 읽지 않는다. 있는 이유는
하나다 — 「몇 개가 로직이고 몇 개가 LLM인가」와 「이 행이 어디에 붙었나」를 **사후에
셀 수 있어야** 평가가 성립한다(사용자 2026-09-16). 지금까지 판정 경로는
`matcher.STATS`(문서 단위 합계)와 로그로만 흐르고 사라졌다.

**코드가 아는 사실만 적는다** — `path`·`verdict`는 닫힌 값이고 LLM 산출이 아니다
(C38 「LLM은 고르고, 시스템이 쓴다」의 결). 적는 자리는 인입의 행 루프 하나다.
"""
from __future__ import annotations

from core.state import store
from core.matcher import PATHS

DIR = "ingest_log"

# 닫힌 값 — 밖이면 FAIL이다(완료판정 ②). 종류 열이 anchor·부착까지 같은 표에 담는다.
VERDICTS = ("match", "new", "uncertain", "anchor", "lowres", "orphan",
            "attached", "pending", "gate_reject")

_KEYS = ("locator", "field", "role", "surface", "canonical", "layer", "path",
         "verdict", "node_id", "candidates_n", "confidence", "llm", "queue_kind")


def name_of(doc_id):
    return f"{DIR}/{doc_id}.json"


class Ledger:
    """문서 하나의 대장. **행을 모으고 한 번에 쓴다** — 쓰기는 원자적이다(§7.1)."""

    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.rows: list[dict] = []

    def add(self, *, locator=None, field=None, role=None, surface=None,
            canonical=None, layer=None, path="none", verdict="pending",
            node_id=None, candidates_n=0, confidence=0.0, llm=None,
            queue_kind=None):
        """행 하나 = entity 값 하나(anchor·부착 결과도 같은 표에 — role이 가른다)."""
        if path not in PATHS:
            raise ValueError(f"대장 path가 닫힌 값 밖이다: {path!r}")
        if verdict not in VERDICTS:
            raise ValueError(f"대장 verdict가 닫힌 값 밖이다: {verdict!r}")
        self.rows.append({
            "locator": locator, "field": field, "role": role,
            "surface": surface, "canonical": canonical, "layer": layer,
            "path": path, "verdict": verdict, "node_id": node_id,
            "candidates_n": int(candidates_n or 0),
            "confidence": round(float(confidence or 0.0), 4),
            "llm": dict(llm or {"calls": 0, "in_tokens": 0, "out_tokens": 0}),
            "queue_kind": queue_kind})
        return self.rows[-1]

    def save(self):
        """**재인입이 덮는다** — 이전 대장이 남지 않는다(완료판정 ②)."""
        store.write(name_of(self.doc_id),
                    {"doc_id": self.doc_id, "rows": self.rows})
        return len(self.rows)


def read(doc_id):
    """그 문서의 대장. 없으면 None — 「인입 기록은 있는데 대장이 없다」를 가른다."""
    p = store.path(name_of(doc_id))
    if not p.exists():
        return None
    return store.read(name_of(doc_id), None)


def summary(rows):
    """머리 집계 — `show report`와 어서션이 **같은 함수로** 센다(B22의 결)."""
    ent = [r for r in rows if r.get("role") == "entity"]
    out = {"값": len(ent), "사전": 0, "스코프": 0, "임베딩": 0, "겹침": 0,
           "신규": 0, "불확실": 0, "보류": 0, "호출": 0, "토큰": 0}
    for r in rows:
        u = r.get("llm") or {}
        out["호출"] += int(u.get("calls") or 0)
        out["토큰"] += int(u.get("in_tokens") or 0) + int(u.get("out_tokens") or 0)
    for r in ent:
        p, v = r.get("path"), r.get("verdict")
        if p == "dictionary":
            out["사전"] += 1
        elif p == "scope+judge":
            out["스코프"] += 1
        elif p == "embedding+judge":
            out["임베딩"] += 1
        elif p == "overlap+judge":
            out["겹침"] += 1
        if v == "new":
            out["신규"] += 1
        elif v == "uncertain":
            out["불확실"] += 1
    out["보류"] = sum(1 for r in rows if r.get("verdict") in ("pending", "orphan"))
    return out


def made_by():
    """`node_id → 그 노드를 처음 만든 행의 path` (B74 ③ — 뷰어가 읽는다).

    「몇 개가 로직이고 몇 개가 LLM인가」를 **노드 위에서** 답하는 자리다. 대장이
    없는 노드는 여기 없다 — 호출부가 seed/unknown으로 가른다(뷰어가 그 둘을 안다).
    """
    out = {}
    d = store.path(DIR)
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        data = store.read(f"{DIR}/{f.name}", None) or {}
        for r in data.get("rows") or []:
            nid = r.get("node_id")
            if nid and r.get("verdict") in ("new", "uncertain") and nid not in out:
                out[nid] = r.get("path") or "none"
    return out
