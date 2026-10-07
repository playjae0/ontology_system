# -*- coding: utf-8 -*-
"""칸 5.3 — 뷰어 **노드 상세의 근거** — 원문 · 위치 · 닻까지의 길 · 문서마다 붙은 자리 (B103 ④).

모으는 일만 한다(PF11): 근거 청크는 `chunks.json`의 `describes`가, 붙은 자리는 판정 대장의 행
(`target`·`attached`·`from` — B102 ⑦)이, 닻까지의 길은 `anchor.anchors`가 답한다. 새 계산 0 · 쓰기 0.
"""
from __future__ import annotations

from core.build import ledger
from core.state import store

#: 근거 청크 상한 — 화면이 한 번에 싣는 수(접어 두고 펼친다 · 넘으면 「n건 더」)
EVIDENCE_MAX = 30


def _docs(prov):
    return sorted({str(p).split("#")[0].split(":")[0] for p in prov or [] if p})


def detail(nid, nodes, edges, anc, raw_node):
    """노드 하나의 상세 — `None`이면 그 id가 지금 그래프에 없다."""
    by = {n["id"]: n for n in nodes}
    if nid not in by:
        return None
    name = lambda i: (by.get(i) or {}).get("name", i)       # noqa: E731
    a = anc.get(nid)
    path = None
    if a is not None:
        path = {"anchor": a["anchor"], "anchor_name": name(a["anchor"]), "hops": a["hops"],
                "steps": [{"rel": s["rel"], "src": s["src"], "src_name": name(s["src"]),
                           "dst": s["dst"], "dst_name": name(s["dst"])} for s in a["path"]]}
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    cids = []
    for d in ch.get("describes") or []:
        if d.get("node_id") == nid and d.get("chunk_id") not in cids:
            cids.append(d["chunk_id"])
    ev = []
    for cid in cids:
        c = (ch.get("chunks") or {}).get(cid) or {}
        m = c.get("meta") or {}
        ev.append({"chunk_id": cid, "doc_id": c.get("doc_id"), "locator": c.get("source_locator"),
                   "section": c.get("section"), "process_ref": c.get("process_ref"),
                   "image": bool(c.get("image_ref") or m.get("image_ref")),
                   "text": c.get("text") or ""})
    ev.sort(key=lambda e: (str(e["doc_id"]), str(e["locator"]), e["chunk_id"]))
    landed = []
    for doc in _docs(raw_node.get("provenance")):
        for r in (ledger.read(doc) or {}).get("rows") or []:
            if r.get("node_id") != nid or r.get("role") != "entity":   # 값 행만 — 부착·anchor 행은 그 노드의 표기가 아니다
                continue
            landed.append({"doc_id": doc, "locator": r.get("locator"), "surface": r.get("surface"),
                           "target": r.get("target") or r.get("canonical"), "verdict": r.get("verdict"),
                           "path": r.get("path"), "from": r.get("from"),
                           "attached": r.get("attached") or []})
    return {"id": nid, "name": by[nid]["name"], "anchor_path": path,
            "evidence": ev[:EVIDENCE_MAX], "evidence_total": len(ev), "landed": landed}
