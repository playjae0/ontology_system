# -*- coding: utf-8 -*-
"""칸 3.x — **문서 끝 결과** — 판정 대장 · 큐 · 관문 로그 · 게이트웨이 누계의 사실을 한 묶음으로 (B99 ⑤).

사내(2026-10-06): 「인입 끝 — 노드 +0 · 엣지 +110 · 큐 auto_node 273종」인데 뷰어 노드 135 —
끝 줄이 **문서 층만** 셌고(노드는 카테고리의 집에 산다 · B90) 큐는 그 문서의 **누적**이었다.
여기서 센다: 층마다 증감 · 이번 실행이 만든 큐와 이전 실행이 남긴 큐 · 값의 결말 · 보류 사유 ·
관계 버림 · LLM 지점별. **새 계산 0** — 재료는 이미 있는 장부다(화면은 투영).

표·산문·렌즈가 같은 함수를 지난다(`entry._finish_build`). 결과는 판정 대장 파일에 붙어
`show report <doc_id>`가 다시 읽는다.
"""
from __future__ import annotations

from collections import Counter

#: 보류 사유 — 대장 행의 (역할, 판정)에서 읽는다(닫힌 표).
HOLD_REASONS = (("anchor", "orphan", "좌표 목록 밖"),
                ("entity", "orphan", "골격 밖(골격 카테고리 · B94)"),
                (None, "pending", "좌표 미해소로 스코프 노드 미생성"),
                (None, "gate_reject", "카테고리 밖(관문)"))


def layer_counts(graphs):
    """`{층: (노드, 엣지, auto)}` — 증감의 재료."""
    return {lay: (len(g.nodes), len(g.edges),
                  sum(1 for n in g.nodes.values() if n.get("status") == "auto"))
            for lay, g in graphs.items()}


def hold_reason(row):
    if row.get("hold"):                    # 행이 사유를 든다(B104 ① — 「표기 모호」는 목록 밖과 처방이 다르다)
        return row["hold"]
    # 표의 좌표 미해소 드롭 행(`loop._ledger_entity` — 판정 전 · canonical 없음)은 골격 밖(B94)이 아니다(B104 ①)
    if row.get("role") == "entity" and row.get("verdict") == "orphan" and not row.get("canonical"):
        return HOLD_REASONS[2][2]
    for role, verdict, why in HOLD_REASONS:
        if row.get("verdict") == verdict and (role is None or row.get("role") == role):
            return why
    return None


def coord_learn(env):
    """봉투의 좌표 학습 사실(B101 ②④) — `{"새로": 표기 종수, "적중": 행 수}` (태깅이 meta에 남긴다)."""
    pcs = (env or {}).get("records") or (env or {}).get("chunks") or []
    src = [(p.get("meta") or {}) for p in pcs]
    return {"새로": len({m.get("coord_tag_from") for m in src if m.get("coord_tag_source") == "live"}),
            "적중": sum(1 for m in src if m.get("coord_tag_source") == "learned")}


def collect(doc_id, rows, before, after, q_new, q_old, rejects, usage, extra=None):
    """결과 한 묶음(dict). `before`·`after`는 `layer_counts`, `q_new`·`q_old`는 그 문서의 큐 항목,
    `rejects`는 이번 실행의 관문 거부, `usage`는 `gateway.usage_by(doc_id)`."""
    ent = [r for r in rows if r.get("role") == "entity"]
    v = Counter(r.get("verdict") for r in ent)
    hold = Counter(filter(None, (hold_reason(r) for r in rows)))
    layers = {lay: tuple(after.get(lay, (0, 0, 0))[i] - before.get(lay, (0, 0, 0))[i]
                         for i in range(3))
              for lay in sorted(set(before) | set(after))}
    return {
        "doc_id": doc_id,
        "값": len(ent),
        "사전 연결": sum(1 for r in ent if r.get("path") == "dictionary"),
        "LLM 연결": sum(1 for r in ent if r.get("verdict") == "match"
                       and (r.get("llm") or {}).get("calls", 0) > 0),
        "새 노드": v.get("new", 0),
        "불확실": v.get("uncertain", 0) + v.get("lowres", 0),
        "보류": dict(hold),
        "관계 버림": [[f"{s} {rel} {d}", n] for (s, rel, d), n in Counter(
            (x.get("src_cat"), x.get("rel"), x.get("dst_cat")) for x in rejects).most_common(5)],
        "LLM": {pt: {**u, "avg": round((u["prompt"] + u["completion"]) / u["calls"], 1)
                     if u["calls"] else 0} for pt, u in usage.items()},
        "층": {lay: {"노드": d[0], "엣지": d[1], "auto": d[2]} for lay, d in layers.items()
              if any(d)},
        "큐 이번": dict(Counter(x["kind"] for x in q_new)),
        "큐 이전": dict(Counter(x["kind"] for x in q_old)),
        # 동의어 학습(B101 ①④) — 같은 문서 auto 매칭 · 가드로 내려간 것(다른 문서 auto) · 더한 별칭
        "같은 문서 auto 매칭": sum(1 for r in ent if r.get("same_doc")),
        "가드(다른 문서 auto)": sum(1 for r in ent if (r.get("nearest") or {}).get("by") == "가드"),
        **(extra or {}),
    }


def totals(res):
    """층별 합 — `(노드, 엣지, auto)` (인입 끝 줄 · 일괄 끝 합계)."""
    ly = (res or {}).get("층") or {}
    return (sum(d["노드"] for d in ly.values()), sum(d["엣지"] for d in ly.values()),
            sum(d["auto"] for d in ly.values()))


def _k(s):
    from core.state.ids import fold_latin, norm
    return fold_latin(norm(s or "")).replace(" ", "")


def landing(rows, env, graphs, doc_id, top=5):
    """**붙은 곳 끝 요약**(B102 ⑦) — 엣지 없는 노드 · 부착 경로별 · 소속 없음 비율(시트·구획) ·
    청크 본문에 글자 그대로 없는 개체(그림 요약에서). 판정이 아니라 대조다(공백·라틴 대소문자 무시)."""
    ent = [r for r in rows if r.get("role") == "entity"]
    pre = f"{doc_id}#"
    edges = set()
    for g in graphs.values():
        for e in g.edges:
            edges |= {e["src"], e["dst"]}
    mine = {nid for g in graphs.values() for nid, n in g.nodes.items()
            if any(str(p) == doc_id or str(p).startswith(pre) for p in n.get("provenance") or [])}
    att = Counter()
    for r in ent:
        paths = [a.get("path") or "" for a in r.get("attached") or []]
        for p in paths:
            if p.startswith("소속"):
                att["소속 " + (p[3:-1] if p.endswith(")") else "-")] += 1
            else:
                att[p] += 1
        if not paths and r.get("verdict") in ("pending", "orphan"):
            att["보류"] += 1
    by_loc = {c.get("source_locator"): c for c in (env.get("chunks") or [])}
    miss = Counter()
    gone, img = 0, 0
    for r in ent:
        c = by_loc.get(r.get("locator"))
        if c is None:
            continue
        m = c.get("meta") or {}
        where = m.get("sheet") or c.get("section") or "-"
        miss[(where, "전체")] += 1
        if not r.get("from"):
            miss[(where, "없음")] += 1
        if r.get("surface") and _k(r["surface"]) not in _k(c.get("text") or c.get("context") or ""):
            gone += 1
            if m.get("shape_kind") == "picture" or c.get("image_ref"):
                img += 1
    ratio = sorted(((w, miss[(w, "없음")], n) for (w, k), n in miss.items() if k == "전체"),
                   key=lambda t: (-(t[1] / t[2] if t[2] else 0), -t[2], t[0]))[:top]
    return {"엣지 없는 노드": len(mine - edges),
            "부착": dict(att),
            "소속 없음 비율": [[w, a, n] for w, a, n in ratio if a],
            "본문에 없는 개체": {"n": gone, "그림": img}}

