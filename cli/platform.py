# -*- coding: utf-8 -*-
"""4′ 플랫폼 연동 — 국면 1의 플랫폼 쪽 창구 (구현문서 §7 단계 4 · 명세 §16.2 개조 1·2).

플랫폼과 파이프라인의 결합은 **파일 계약(subprocess)**뿐이다(§16.1). build·query는
subprocess로 부르고, 표시는 data/의 JSON(진실)을 읽어서 한다 — 여기는 **관측이지
쓰기가 아니다**: 그래프·큐에 아무것도 쓰지 않는다(예외는 계기판 7·8의 재측정 저장
1건 — 내용 동일 재기록이라 그래프 해시가 변하지 않는다. run.py gauges와 같은 경로).

노출 목록 (증분0 §3 G6 + 허브 추가 지시):
  build / query      subprocess 호출 (§16.1 계약 1 — build 직렬은 호출부 보장)
  graph              2층 + cross-layer 표시
  queue              수정 큐 열람 — **닫힌 20종 전부**(0건 kind 포함)
  extract            추출 상태 (extract/{doc_id}.json 존재 = 추출 완료 — P-1)
  registry           층 등록부 조회
  ops                I축 연산 이력(ops_log) 열람 + 툼스톤 계수
  gauges             계기판 8종 (CH5 5.5 — 별도 호출로 계산, build·query 무오염)

사용: python cli/platform.py <명령> [인자...]   (또는 python run.py platform ...)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import store                                  # noqa: E402
from core.bootstrap import load_config, open_graph      # noqa: E402
from core.extract import EXTRACT_DIR                    # noqa: E402
from core.ops import is_live                            # noqa: E402
from router import discover                             # noqa: E402

# 수정 큐 kind — **닫힌 20종**(구현문서 §2.3의 13종 + 증분0 §6-5의 확장 7종 · D-54).
# 열람 화면의 상수다: 0건인 kind도 화면에 떠야 "닫힌 목록"이 보인다.
QUEUE_KINDS = [
    # 기존 13종 (구현문서 §2.3)
    "auto_node", "uncertain_match", "orphan_anchor", "orphan_chunk_link",
    "orphan_attach", "attach_conflict", "unknown_field", "missing_field",
    "invalid_category", "spec_conflict", "evidence_lost", "mirror_asymmetry",
    "structural_proposal",
    # 확정 확장 4종 (증분0 §6-5 — 계 17)
    "direction_unverifiable", "coord_mismatch", "parse_failure", "adapter_mismatch",
    # 승인 신설 3종 (D-3·D-4·D-5 — 계 20)
    "direction_conflict", "duplicate_doc_hold", "hierarchy_unresolved",
]


# ---------------------------------------------------------------- subprocess 결합
def call(args):
    """파이프라인 호출은 subprocess 하나뿐이다 — 코드 의존 0 (§16.1 계약 1)."""
    return subprocess.run([sys.executable, str(ROOT / "run.py"), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


def cmd_build():
    r = call(["all"])
    print(r.stdout, end="")
    return r.returncode


def cmd_query(args):
    r = call(["query", *args])
    print(r.stdout, end="")
    return r.returncode


# ---------------------------------------------------------------- 표시 (data/ 읽기)
def graph_view():
    """2층 + cross-layer — 층별 계수와 걸침 엣지 목록."""
    layers = discover()
    graphs = {lay: open_graph(lay) for lay in layers}
    out = {"layers": {}, "cross": []}
    for lay, g in graphs.items():
        cats, rels = {}, {}
        for n in g.nodes.values():
            if is_live(n):
                cats[n["category"]] = cats.get(n["category"], 0) + 1
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            rels[e["rel"]] = rels.get(e["rel"], 0) + 1
        out["layers"][lay] = {"nodes": sum(cats.values()), "by_category": cats,
                              "edges": rels}
        # 걸침 엣지 — 출발 층 그래프에 있고, 끝점 하나가 딴 층에서 해소된다(§2.2)
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            if e["src"] in g.nodes and e["dst"] in g.nodes:
                continue
            def _find(nid):
                if nid in g.nodes:
                    return lay, g.nodes[nid]
                for o in layers:
                    if o != lay and nid in graphs[o].nodes:
                        return o, graphs[o].nodes[nid]
                return None, None
            sl, sn = _find(e["src"])
            dl, dn = _find(e["dst"])
            if sn and dn:
                out["cross"].append(f"{sl}:{sn['canonical']} -{e['rel']}→ {dl}:{dn['canonical']}")
    return out


def cmd_graph():
    v = graph_view()
    for lay, s in v["layers"].items():
        cats = " · ".join(f"{c} {n}" for c, n in sorted(s["by_category"].items()))
        rels = " · ".join(f"{r} {n}" for r, n in sorted(s["edges"].items()))
        print(f"[{lay}] 노드 {s['nodes']} ({cats})")
        print(f"        엣지 {rels}")
    print(f"[cross-layer] 걸침 엣지 {len(v['cross'])}건")
    for line in v["cross"]:
        print(f"        {line}")


def queue_view():
    """큐 열람 — 닫힌 20종 전부. 목록 밖 kind가 실물에 있으면 그 자체가 결함 신호다."""
    q = store.read(store.QUEUE, [])
    counts = {k: 0 for k in QUEUE_KINDS}
    alien = {}
    for x in q:
        k = x.get("kind")
        if k in counts:
            counts[k] += 1
        else:
            alien[k] = alien.get(k, 0) + 1
    return {"total": len(q), "kinds": counts, "alien": alien, "items": q}


def cmd_queue(kind=None):
    v = queue_view()
    print(f"수정 큐 — {v['total']}건 · 닫힌 {len(QUEUE_KINDS)}종 (D-54)")
    for k in QUEUE_KINDS:
        print(f"  {k:<24} {v['kinds'][k]:>3}건")
    for k, n in v["alien"].items():
        print(f"  ⚠ 목록 밖 kind '{k}' {n}건 — 닫힌 20종 위반, 그 자체가 결함이다")
    if kind:
        print(f"\n[{kind}] 항목:")
        for x in v["items"]:
            if x.get("kind") == kind:
                print(f"  · {x.get('reason')}  (doc={x.get('doc_id')})")


def extract_view():
    """추출 상태 — 파일 존재 = '추출 완료'(P-1). table 문서는 추출 대상이 아니다."""
    docs = store.read(store.DOC_REGISTRY, {})
    return {doc_id: (EXTRACT_DIR / f"{doc_id}.json").exists() for doc_id in docs}


def cmd_extract():
    docs = store.read(store.DOC_REGISTRY, {})
    print(f"추출 상태 — extract/{{doc_id}}.json 존재 = 추출 완료 (체크포인트 · P-1)")
    for doc_id in docs:
        done = (EXTRACT_DIR / f"{doc_id}.json").exists()
        print(f"  {doc_id:<10} {'추출 완료' if done else '― (추출 경로 아님 — table 인입)'}")


def cmd_registry():
    reg = store.read(store.REGISTRY, {})
    print(f"층 등록부 — {len(reg)}층")
    for lay, meta in reg.items():
        print(f"  {lay:<10} status={meta.get('status')} · "
              f"categories={meta.get('categories')} · relations={meta.get('relations')}")


def ops_view():
    """I축 연산 이력 + 툼스톤 계수 — G5 산출물 노출 (D-67)."""
    log = store.read(store.OPS_LOG, [])
    tomb = {}
    for lay in discover():
        g = open_graph(lay)
        merged = sum(1 for n in g.nodes.values() if n.get("merged_into"))
        obs = sum(1 for n in g.nodes.values()
                  if n.get("status") == "obsolete" and not n.get("merged_into"))
        tomb[lay] = {"merged_into": merged, "obsolete": obs}
    return {"log": log, "tombstones": tomb}


def cmd_ops():
    v = ops_view()
    print(f"I축 연산 이력 — {len(v['log'])}건 (data/ops_log.json — 큐가 아니라 로그다)")
    for x in v["log"]:
        print(f"  · {x.get('op')} by {x.get('actor')} @ {x.get('at')} — "
              f"대상 {len(x.get('targets') or [])} · {x.get('reason') or '(사유 없음)'}")
    for lay, t in v["tombstones"].items():
        print(f"[{lay}] 툼스톤 — merged_into {t['merged_into']} · obsolete {t['obsolete']}")


# ---------------------------------------------------------------- 계기판 8종
def gauges():
    """계기판 8종 (CH5 5.5) — **별도 호출로 계산한다**: build·query 경로에 계산을
    심지 않는다(8번 지표가 자기 자신을 오염시키면 안 된다).

    국면 1 데이터 기준: 1(recall류)은 mock 스모크 12문항, 2~6은 mock 인입 실측.
    측정 중에는 운영 로그 적재를 끈다 — 측정이 재료 로그(link_miss)를 오염시키면
    다음 측정이 자기 흔적을 세게 된다.
    """
    from cli import query as R
    from core import query as Q

    queries = json.loads((ROOT / "mock" / "queries.json").read_text(encoding="utf-8"))
    smoke = queries["queries"]

    _orig = store.append_line
    store.append_line = lambda *a, **k: None            # 측정 무오염
    try:
        results = {q["id"]: R.answer(q["q"]) for q in smoke}
    finally:
        store.append_line = _orig

    linkable = [q for q in smoke if q["expected_path"] != Q.PATH_GENERAL]
    linked = [q for q in linkable if results[q["id"]]["linked"]]
    missed = [q for q in smoke if not results[q["id"]]["linked"]]
    truncated = [q for q in smoke if results[q["id"]]["truncated"]]

    layers = discover()
    graphs = {lay: open_graph(lay) for lay in layers}
    docs = list(store.read(store.DOC_REGISTRY, {}))

    # 2 plateau — 문서별 신규 개체율 (인입 순서 = doc_registry 등재 순서)
    def doc_of(loc):
        return next((d for d in docs if loc.startswith(d + "-")), None)

    plateau = []
    for d in docs:
        mentioned = new = 0
        for g in graphs.values():
            for n in g.nodes.values():
                if not is_live(n):
                    continue
                prov = n.get("provenance") or []
                if any(doc_of(p) == d for p in prov):
                    mentioned += 1
                    firsts = [p for p in prov if p != "seed"]
                    if "seed" not in prov and firsts and doc_of(firsts[0]) == d:
                        new += 1
        plateau.append({"doc": d, "mentioned": mentioned, "new": new,
                        "rate": round(new / mentioned, 3) if mentioned else None})

    # 3 판정 보류율 — 큐 유입 ÷ 발자국을 남긴 조각 수 (record locator + chunk)
    q = store.read(store.QUEUE, [])
    locs = set()
    for g in graphs.values():
        for n in g.nodes.values():
            locs |= {p for p in (n.get("provenance") or []) if p != "seed"}
        for e in g.edges:
            locs |= {p for p in (e.get("provenance") or []) if p != "seed"}
    chunks = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    pieces = len(locs | set(chunks))
    hold_rate = round(len(q) / pieces, 3) if pieces else None

    # 6 허브 노드 차수 (카드 J9) — 층별 상위 3
    hubs = {}
    for lay, g in graphs.items():
        deg = {}
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            for side in ("src", "dst"):
                deg[e[side]] = deg.get(e[side], 0) + 1
        top = sorted(((d, nid) for nid, d in deg.items() if nid in g.nodes
                      and is_live(g.nodes[nid])), reverse=True)[:3]
        hubs[lay] = [{"canonical": g.nodes[nid]["canonical"], "degree": d}
                     for d, nid in top]

    # 7·8 — 저장 계층 운영 지표. run.py gauges와 같은 재측정 경로(내용 동일 재기록).
    storage = {}
    for lay in layers:
        g = open_graph(lay)
        g.build_begin()
        storage[lay] = g.build_end()

    return {
        "1_linking_recall": {"value": round(len(linked) / len(linkable), 3) if linkable else None,
                             "linked": len(linked), "expected_linkable": len(linkable),
                             "basis": "mock 스모크 12문항 (구현문서 §6.4 — 골든셋은 국면 2)"},
        "2_plateau": {"series": plateau,
                      "last_rate": plateau[-1]["rate"] if plateau else None},
        "3_hold_rate": {"value": hold_rate, "queue": len(q), "pieces": pieces},
        "4_truncation_rate": {"value": round(len(truncated) / len(smoke), 3),
                              "truncated": len(truncated), "of": len(smoke)},
        "5_miss_rate": {"value": round(len(missed) / len(smoke), 3),
                        "missed": [q["q"] for q in missed], "of": len(smoke)},
        "6_hub_degree": hubs,
        "7_graph_size": {lay: {"mb": m["gauge7_graph_mb"], "over_alarm": m["gauge7_over_alarm"]}
                         for lay, m in storage.items()},
        "8_build_seconds": {lay: {"s": m["gauge8_build_seconds"], "over_alarm": m["gauge8_over_alarm"]}
                            for lay, m in storage.items()},
        "_alarm": {"gauge7": "200MB → R10 판정 개시 (틀 A8-3)", "gauge8": "30초 → 동상"},
    }


def cmd_gauges():
    m = gauges()
    g1 = m["1_linking_recall"]
    print(f"계기판 8종 (CH5 5.5 — P7의 실행 장치)")
    print(f"  1 링킹 recall     {g1['value']}  ({g1['linked']}/{g1['expected_linkable']} — {g1['basis']})")
    series = " → ".join(f"{p['doc']} {p['rate']}" for p in m["2_plateau"]["series"])
    print(f"  2 plateau         신규 개체율 {series}")
    g3 = m["3_hold_rate"]
    print(f"  3 판정 보류율     {g3['value']}  (큐 {g3['queue']} ÷ 조각 {g3['pieces']})")
    g4 = m["4_truncation_rate"]
    print(f"  4 청크 잘림률     {g4['value']}  ({g4['truncated']}/{g4['of']}문항)")
    g5 = m["5_miss_rate"]
    print(f"  5 링킹 미스율     {g5['value']}  ({len(g5['missed'])}/{g5['of']}문항)")
    for lay, tops in m["6_hub_degree"].items():
        line = " · ".join(f"{t['canonical']}({t['degree']})" for t in tops)
        print(f"  6 허브 차수 [{lay}] {line}")
    for lay in m["7_graph_size"]:
        s7, s8 = m["7_graph_size"][lay], m["8_build_seconds"][lay]
        a7 = " ⚠알람" if s7["over_alarm"] else ""
        a8 = " ⚠알람" if s8["over_alarm"] else ""
        print(f"  7 저장 크기 [{lay}] {s7['mb']}MB / 알람선 200MB{a7}")
        print(f"  8 build 시간 [{lay}] {s8['s']}s / 알람선 30초{a8}")
    return m


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, args = argv[0], argv[1:]
    {"build": lambda: cmd_build(),
     "query": lambda: cmd_query(args),
     "graph": lambda: cmd_graph(),
     "queue": lambda: cmd_queue(args[0] if args else None),
     "extract": lambda: cmd_extract(),
     "registry": lambda: cmd_registry(),
     "ops": lambda: cmd_ops(),
     "gauges": lambda: cmd_gauges()}[cmd]()


if __name__ == "__main__":
    main(sys.argv[1:])
