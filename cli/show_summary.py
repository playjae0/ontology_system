# -*- coding: utf-8 -*-
"""칸 0.3 — **전체 판** — 문서를 한 건씩 넣어도 「다 넣고 몇 개가 됐나」를 한 화면에 (B118 ① · 사용자 2026-10-16 「숫자 정리는
이야기하고 가자 — 몇 개를 어떻게 처리했고 최종 몇 개가 됐는지」).

    python run.py show summary                      지금의 전체 판
    python run.py show summary --save <이름>         그 판을 스냅샷 파일로(`golden/summary/<이름>.json` — 사람이 정한 기준선 ·
                                                    기본 fresh · 재구축이 지우지 않는다)
    python run.py show summary --diff <이름1> <이름2>  두 판의 같은 줄끼리 — 바뀐 줄만(`지금` = 지금 판)

**화면은 장부 · 그래프의 투영이다**(새 판정 0 · 저장은 스냅샷 파일뿐): 층별 노드(골격 · auto · 확정 · 그 밖 · 엣지 없는 노드) ·
엣지(관계별) · **문서별 줄**(노드 · 엣지 · 보류 · 유닛 이하 비율 · 연결 보강 붙음/못 고름/버림 · 정답률) · 큐(종류별 열림/닫힘) ·
보류(사유별) · 재연결 누계(붙음 — 대장의 재시도 행 · 남음 · 상한 도달 — 큐) · 불확실(사람 검토 대기 — `ops review`) · 값(attrs) 수.
문서별 수는 맞춤표(`core/build/reconcile.table`)의 같은 줄에서 온다 — 문서 끝 한 줄 요약과 같은 수다.
"""
from __future__ import annotations

import json
from collections import Counter

from core import paths
from core.state import store


def _graphs():
    from core.state.bootstrap import open_graph
    from router import discover
    return {lay: open_graph(lay) for lay in discover()}


def _live_edges(g):
    return [e for e in g.edges if e.get("status") != "deleted_by_user"]


def collect(graphs=None):
    """전체 판 — `[(열쇠, 글)]` 순서 그대로(같은 열쇠끼리 `--diff`가 대조한다) + 재료 `dict`."""
    from core.build import ledger, reconcile as RC
    from core.build.result import hold_reason
    from core.build.retry import plan
    from cli import ops_review, show_score
    graphs = graphs if graphs is not None else _graphs()
    out, raw = [], {"층": {}, "문서": {}, "큐": {}, "보류": {}}
    ends = set()
    for g in graphs.values():
        for e in _live_edges(g):
            ends |= {e["src"], e["dst"]}
    for lay, g in sorted(graphs.items()):
        st = Counter(n.get("status") for n in g.nodes.values())
        iso = sum(1 for nid in g.nodes if nid not in ends)
        other = len(g.nodes) - st["seed"] - st["auto"] - st["confirmed"]
        raw["층"][lay] = {"노드": len(g.nodes), "골격": st["seed"], "auto": st["auto"], "확정": st["confirmed"],
                         "그 밖": other, "엣지 없는 노드": iso}
        out.append((f"층 {lay} 노드", f"노드 {len(g.nodes):,} = 골격 {st['seed']:,} + auto {st['auto']:,} + 확정 "
                                       f"{st['confirmed']:,} + 그 밖 {other:,} · 엣지 없는 노드 {iso:,}"))
        rel = Counter(e.get("rel") for e in _live_edges(g))
        raw["층"][lay]["엣지"] = dict(rel)
        out.append((f"층 {lay} 엣지", f"엣지 {sum(rel.values()):,}" + (" — " + " · ".join(
            f"{k} {v:,}" for k, v in sorted(rel.items())) if rel else "")))
    q = store.read(store.QUEUE, [])
    nodes = RC.skeleton_nodes()
    holds = Counter()
    for doc_id in sorted(store.read(store.DOC_REGISTRY, {})):
        data = ledger.read(doc_id) or {}
        rows = data.get("rows") or []
        holds.update(hold_reason(r) for r in rows if hold_reason(r))
        mt = _doc_table(doc_id, data, graphs, [x for x in q if x.get("doc_id") == doc_id], nodes)
        s = mt["요약"]
        lk = next((ln for ln in mt["줄"] if ln["줄"].startswith("연결 보강")), None)
        rf = {k: n for k, n, _d in (lk or {}).get("칸", [])}
        sc = show_score.score(doc_id)
        mine = _mine(graphs, doc_id)
        raw["문서"][doc_id] = {"노드": mine[0], "엣지": mine[1], "보류": s["보류"], "유닛 이하 비율": s["유닛 이하 비율"],
                              "보강": rf, "정답률": (sc or {}).get("정답률")}
        ratio = f"{s['유닛 이하 비율']}%" if s["유닛 이하 비율"] is not None else "—"
        out.append((f"문서 {doc_id}", f"노드 {mine[0]:,} · 엣지 {mine[1]:,} · 보류 {s['보류']:,} · 유닛 이하 {ratio} · "
                                       f"연결 보강 붙음 {rf.get('붙음', 0):,}/못 고름 {rf.get('못 고름', 0):,}/버림 "
                                       f"{rf.get('버림', 0):,}"
                                       + (f" · 정답률 {sc['정답률']}%({sc['맞음']}/{sc['맞음'] + sc['틀림']})"
                                          if sc and sc.get("정답률") is not None else "")))
    kinds = sorted({x.get("kind") for x in q})
    for k in kinds:
        op = sum(1 for x in q if x.get("kind") == k and not x.get("resolution"))
        cl = sum(1 for x in q if x.get("kind") == k and x.get("resolution"))
        raw["큐"][k] = {"열림": op, "닫힘": cl}
        out.append((f"큐 {k}", f"열림 {op:,} · 닫힘 {cl:,}"))
    raw["보류"] = dict(holds)
    out.append(("보류", f"보류 {sum(holds.values()):,}(행)" + (" — " + " · ".join(
        f"{k} {v:,}" for k, v in holds.most_common()) if holds else "")))
    healed = sum(1 for d in store.read(store.DOC_REGISTRY, {}) for r in (ledger.read(d) or {}).get("rows") or []
                 if r.get("by") == "retry")
    pl = plan()
    raw["재연결"] = {"붙음 누계": healed, "남음": sum(pl["target"].values()), "상한 도달": pl["capped"]}
    out.append(("재연결", f"붙음 누계 {healed:,}(대장의 재시도 행) · 남음 {sum(pl['target'].values()):,} · "
                         f"상한 도달 {pl['capped']:,}"))
    rv = len(ops_review.items())
    raw["불확실"] = rv
    out.append(("불확실", f"사람 검토 대기 {rv:,}" + (" — python run.py ops review all --actor <이름>" if rv else "")))
    attrs = sum(len(n.get("attrs") or {}) for g in graphs.values() for n in g.nodes.values())
    raw["값"] = attrs
    out.append(("값(attrs)", f"값 {attrs:,}(노드 attrs 항목)"))
    return out, raw


def _mine(graphs, doc_id):
    """이 문서가 만든 노드 · 엣지 수(출처가 그 문서)."""
    pre = f"{doc_id}#"

    def of(x):
        return any(str(p) == doc_id or str(p).startswith(pre) for p in x.get("provenance") or [])
    n = sum(1 for g in graphs.values() for x in g.nodes.values() if of(x))
    e = sum(1 for g in graphs.values() for x in _live_edges(g) if of(x))
    return n, e


def _doc_table(doc_id, data, graphs, queue, nodes):
    """그 문서의 맞춤표 — `reconcile.for_report`와 같은 재료(그래프 · 큐 · 골격은 한 번 연 것)."""
    from core.build import reconcile as RC
    p = paths.parsed(f"{doc_id}.json")
    try:
        env = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        env = {}
    return RC.table(doc_id, data.get("rows") or [], data.get("result") or {}, env, RC._checkpoints(doc_id),
                    graphs, queue, nodes)


def snap_path(name):
    """스냅샷 자리 — `golden/summary/` (사람이 이름을 붙인 기준선 · 재구축 전후를 대조하려면 재구축이 지우면 안 된다)."""
    return paths.golden("summary", f"{name}.json")


def save(name, lines):
    from core.state.store import atomic_write_bytes
    p = snap_path(name)
    paths.ensure(p)
    atomic_write_bytes(p, json.dumps({"name": name, "at": store._now(), "lines": lines},
                                     ensure_ascii=False, indent=1).encode("utf-8"))
    return p


def load(name):
    if name == "지금":
        return collect()[0]
    p = snap_path(name)
    if not p.exists():
        raise SystemExit(f"[summary] 스냅샷 '{name}'이 없다 — {paths.show(p)} · 먼저 python run.py show summary "  # [상태]
                         f"--save {name}")
    return [tuple(x) for x in json.loads(p.read_text(encoding="utf-8"))["lines"]]


def diff(a, b):
    """같은 열쇠끼리 — 바뀐 줄 · 한쪽에만 있는 줄 `[(열쇠, 앞 글 또는 None, 뒤 글 또는 None)]`(뒤 판 순서 · 앞에만 있는 것은 끝)."""
    da, db = dict(a), dict(b)
    out = [(k, da.get(k), v) for k, v in b if da.get(k) != v]
    out += [(k, v, None) for k, v in a if k not in db]
    return out


def main(args):
    if "--diff" in args:
        i = args.index("--diff")
        if len(args) < i + 3:
            raise SystemExit("[사용법] python run.py show summary --diff <이름1> <이름2>   (지금 판은 '지금')")  # [사용법]
        a, b = args[i + 1], args[i + 2]
        got = diff(load(a), load(b))
        print(f"■ 전체 판 비교 — {a} → {b} · 바뀐 줄 {len(got):,}")
        for k, x, y in got:
            if x is None:
                print(f"  + {k}: {y}")
            elif y is None:
                print(f"  - {k}: {x}")
            else:
                print(f"  ~ {k}: {x}\n  {' ' * (len(k) + 2)}→ {y}")
        return 0
    lines, _raw = collect()
    print("■ 전체 판 — 층 · 문서 · 큐 · 보류 · 재연결 · 불확실 · 값 (장부 · 그래프에서 · 새 판정 0)")
    from cli import _screen
    width = max(_screen.w(k) for k, _v in lines) if lines else 0
    for k, v in lines:
        print(f"  {_screen.pad(k, width + 2)}{v}")
    if "--save" in args:
        i = args.index("--save")
        if len(args) < i + 2:
            raise SystemExit("[사용법] python run.py show summary --save <이름>")     # [사용법]
        p = save(args[i + 1], lines)
        print(f"  스냅샷 → {paths.show(p)} · 비교: python run.py show summary --diff {args[i + 1]} 지금")
    return 0
