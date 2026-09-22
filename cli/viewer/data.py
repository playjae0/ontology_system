# -*- coding: utf-8 -*-
"""칸 5.1 — 뷰어 API의 **데이터 묶음** — 그래프 · 문서 · 깔때기 (B82 ①⑤).

여기 있는 것은 **시스템이 이미 아는 것을 모으는 일**뿐이다: 그래프는 GraphStore가,
판정은 대장이, 큐는 store가 답한다. 화면이 제 계산을 하지 않는다는 규율(PF11)의
서버 쪽 절반이고, 나머지 절반은 `static/app.js`가 받은 것을 그리기만 하는 것이다.

**변환 규칙은 한 자리다** — 노드·엣지의 화면 형태는 `cli/export.py::graph_data`가
소유하고 여기서 다시 쓰지 않는다(스냅샷 반출과 뷰어가 같은 그림을 본다).
"""
from __future__ import annotations

from core import paths
from core.build import ledger
from core.llm import gateway
from core.state import sheets, store
from core.state.bootstrap import open_graph
from router import discover


def world():
    return {lay: open_graph(lay) for lay in discover()}


def health():
    """`doctor` 첫 줄과 **같은 사실** — 상태 루트·모드·등록·층·문서."""
    from core.state import registry
    dts = registry.all_doc_types()
    return {"home": str(paths.home()), "mode": "mock" if gateway.use_mock() else "실호출",
            "mock": gateway.use_mock(), "doc_types": len(dts),
            "layers": discover(),
            "docs": len(store.read(store.DOC_REGISTRY, {}))}


def graph():
    """전 층 통합 그래프 — `merged_into`는 빠지고 `obsolete`는 필드로 남는다."""
    from cli.export import graph_data
    w = world()
    nodes, edges = graph_data(w)
    return {"nodes": nodes, "edges": edges, "layers": sorted(w),
            "rels": sorted({e["rel"] for e in edges})}


def doc(doc_id):
    """문서 하나 — 대장 행 + 판정 집계 + 그 문서가 만든 노드·청크 (B82 ①④)."""
    reg = (store.read(store.DOC_REGISTRY, {}) or {}).get(doc_id)
    if reg is None:
        return None
    rows = ((ledger.read(doc_id) or {}).get("rows") or [])
    tally = {}
    for r in rows:
        tally[r.get("verdict") or "?"] = tally.get(r.get("verdict") or "?", 0) + 1
    nodes = [{"id": n["id"], "canonical": n["canonical"], "layer": lay,
              "category": n.get("category"), "status": n.get("status")}
             for lay, g in world().items() for n in g.nodes.values()
             if any(str(p).split("#")[0].split(":")[0] == doc_id
                    for p in (n.get("provenance") or []))]
    ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    # **역할은 청크가 지고 다니는 사실이다**(B83 ④) — 뷰어가 다시 판정하지 않는다.
    chunks = [{"chunk_id": cid, "source_locator": c.get("source_locator"),
               "section": c.get("section"), "text": c.get("text"),
               "sheet_role": (c.get("meta") or {}).get("sheet_role")}
              for cid, c in ch.items() if c.get("doc_id") == doc_id]
    # 원본은 `<상태>/raw/` 아래면 상대 표기다(B79 ② · B80 ②) — 링크로 풀 수 있다.
    src = reg.get("source_path")
    rel = None
    if src:
        p = paths.from_home(src)
        try:
            rel = p.relative_to(paths.raw()).as_posix()
        except ValueError:
            rel = None
    return {"doc_id": doc_id, "registry": reg, "raw_rel": rel,
            "rows": len(rows), "tally": tally,
            # 기록 그대로 — 뷰어는 읽기만이다(쓰기 0).
            "sheet_roles": (sheets.read(doc_id) or {}).get("sheets") or {},
            "nodes": sorted(nodes, key=lambda n: n["canonical"]),
            "chunks": sorted(chunks, key=lambda c: c["chunk_id"])}


#: 깔때기의 칸 — 이름은 판정 대장의 닫힌 값에서 온다(화면이 새로 해석하지 않는다).
FUNNEL_KEYS = ("값", "사전", "스코프", "LLM붙음", "NEW", "불확실", "orphan", "큐")


def funnel():
    """문서마다 `값 → 사전·스코프·LLM붙음·NEW·불확실·orphan·큐` + orphan 행 (B82 ⑤).

    수는 **판정 대장과 큐에서 센다** — 화면이 다시 세지 않는다. 「연결」의 정의도
    여기 한 줄로 둔다: 붙음 = 사전+스코프+LLM match · auto = NEW+불확실 ·
    orphan = 좌표 미해소 행.
    """
    reg = store.read(store.DOC_REGISTRY, {}) or {}
    q = [x for x in store.read(store.QUEUE, []) if not x.get("resolution")]
    rows = []
    for doc_id in sorted(reg):
        led = ((ledger.read(doc_id) or {}).get("rows") or [])
        cnt = dict.fromkeys(FUNNEL_KEYS, 0)
        cnt["값"] = len(led)
        for r in led:
            path, verdict = r.get("path"), r.get("verdict")
            if path == "dictionary":
                cnt["사전"] += 1
            elif path == "skeleton":
                cnt["스코프"] += 1
            elif verdict == "match":
                cnt["LLM붙음"] += 1
            if verdict == "new":
                cnt["NEW"] += 1
            elif verdict in ("uncertain", "lowres"):
                cnt["불확실"] += 1
            elif verdict == "orphan":
                cnt["orphan"] += 1
        cnt["큐"] = sum(1 for x in q if x.get("doc_id") == doc_id)
        rows.append({"doc_id": doc_id, **cnt})
    orphans = [{"doc_id": x.get("doc_id"),
                "locator": (x.get("payload") or {}).get("provenance"),
                "surface": (x.get("payload") or {}).get("surface"),
                "reason": x.get("reason"),
                "attempts": (x.get("payload") or {}).get("attempts", 0),
                "at": x.get("created")}
               for x in q if str(x.get("kind") or "").startswith("orphan")]
    total = {k: sum(r[k] for r in rows) for k in FUNNEL_KEYS}
    return {"keys": list(FUNNEL_KEYS), "rows": rows, "total": total,
            "orphans": orphans,
            "정의": "붙음 = 사전 + 스코프 + LLM match · auto = NEW + 불확실"
                    "(노드는 있고 확인 대기) · orphan = 좌표 미해소 행"}
