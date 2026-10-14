# -*- coding: utf-8 -*-
"""칸 2.8 — **동의어 학습 화면** — 좌표 학습 목록 · 새 공정 후보 · 별칭 출처 (B101 ②③④) · 별칭 대장 (B108 ①).

    python run.py show learned        좌표 학습 기록(표기 · 노드 · 문서 · 적중 · 시각) + 새 공정 후보
    python run.py show aliases [층] [--source <출처>] [--node <이름|id>]
                                      별칭 대장 — 대상마다 seed 별칭과 대장 별칭(표기 · 출처 · 문서 · 횟수 · 상태)

읽기 전용이다. 승격·거부는 `run.py ops learn-promote|learn-reject <층> <표기> --actor` · 별칭 거두기는
`run.py ops alias-reject <층> <대상> <표기> --actor`.
"""
from __future__ import annotations

from core.state import coord_learn


def alias_source(a):
    """별칭 하나의 **출처**(B101 ④) — 사람(`ops` · 사람이 친 merge) · 골격(seed) · LLM 매칭 · 문서."""
    if a.get("by") == "LLM 매칭":
        return f"LLM 매칭(확신 {a.get('confidence')} · {a.get('doc')})"
    prov = [str(p) for p in (a.get("provenance") or [])]
    op = next((p for p in prov if p.startswith("op:")), None)
    if op:
        return f"사람({op.split(':')[1]} · {op.split(':')[-1]})"
    if any(p == "seed" or p.startswith("seed") for p in prov):
        return "골격"
    return "문서 표기"


def node_alias_lines(n):
    """`show node`의 별칭 줄들 — 별칭마다 출처 + 이 노드를 가리키는 좌표 학습 표기."""
    out = [f"  별칭       {a['surface']}  ← {alias_source(a)}" for a in n.get("aliases") or []]
    for s, r in coord_learn.sources_for(n):
        out.append(f"  별칭       {s}  ← 좌표 학습({r.get('doc_id')} · 적중 {int(r.get('hits') or 0):,}"
                   f" · {r.get('at')})")
    return out or ["  별칭       (없음)"]


def cmd_learned(args):
    rows = coord_learn.rows()
    print(f"■ 좌표 학습 기록 — {len(rows):,}표기 (LLM이 채택 · 바로 쓴다 · 사람 보증 아님)")
    if rows:
        print(f"  {'표기':<20} {'골격 노드':<24} {'문서':<14} {'적중':>5}  시각")
    for s, r in rows:
        print(f"  {s:<20} {r.get('canonical', ''):<24} {str(r.get('doc_id')):<14} "
              f"{int(r.get('hits') or 0):>5,}  {r.get('at')}")
    if rows:
        print("  ▶ 다음 줄 — 맞으면 승격(골격 ALIASES로): python run.py ops learn-promote <층> <표기> "
              "--actor <이름> → python run.py bootstrap")
        print("               틀리면 거부(다음엔 다시 묻는다): python run.py ops learn-reject <층> <표기> "
              "--actor <이름>")
    cands = coord_learn.candidates()
    print(f"\n■ 새 공정 후보 — {len(cands):,}표기 (태깅이 「목록에 없음」으로 답했다 · 해소에 쓰지 않는다)")
    if cands:
        print(f"  {'표기':<20} {'행':>5} {'큐 행':>5}  {'문서':<24} 처음 본 때")
    for s, r, q in cands:
        print(f"  {s:<20} {int(r.get('rows') or 0):>5,} {q:>5,}  {', '.join(r.get('docs') or [])[:24]:<24} "
              f"{r.get('first_seen')}")
    if cands:
        print("  ▶ 다음 줄 — 새 공정이면 골격 노드로, 있는 공정의 다른 이름이면 그 노드의 ALIASES에 더한다 "
              "(layers/<좌표 층>/skeleton.json) → python run.py bootstrap → 다음 인입 마무리에서 붙는다")
    return 0


# ---------------------------------------------------------------- 별칭 대장 (B108 ①)
def _opt(args, flag):
    if flag not in args:
        return None
    i = args.index(flag)
    v = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    return v


def _entry_line(r, miss):
    """대장 항목 한 줄 — 표기 · 출처 · 문서(처음 → 마지막 · 수) · 횟수 · 상태 · 그래프에 없음 · 처음 채움."""
    docs = r.get("docs") or []
    d = (f"문서 {docs[0]}" + (f" → {docs[-1]}" if len(docs) > 1 else "") + f"({len(docs):,})") if docs else "문서 —"
    rej = r.get("rejected") or {}
    st = r["status"] + (f"({rej.get('actor')} · {rej.get('at')})" if rej else "")
    return (f"     대장  {r['surface']}  ← {r['source']} · {d} · {int(r.get('count') or 0):,}회 · {st}"
            + (" · 그래프에 없음" if id(r) in miss else "") + (" · 처음 채움" if r.get("filled") else ""))


def cmd_aliases(args):
    """`show aliases [층] [--source <출처>] [--node <이름|id>]` — 출처별 수 = 대장 수 · 그래프에 있음/없음 ·
    대상마다 seed 별칭(그래프의 골격 노드)과 대장 별칭."""
    from core import paths
    from core.state import alias_book as AB, store
    from core.state.ids import norm
    from core.state.status import is_live
    from core.state.world import World
    args = list(args)
    src, want = _opt(args, "--source"), _opt(args, "--node")
    if src is not None and src not in AB.SOURCES:
        raise SystemExit(f"[show aliases] --source는 {' · '.join(AB.SOURCES)} 중 하나다 — '{src}'")     # [사용법]
    layer = args[0] if args else None
    book, w = AB.AliasBook.open(), World()

    def _hit(t, nid=None):
        return (layer is None or t.get("layer") == layer) and \
            (want is None or norm(t.get("canonical") or "") == norm(want) or nid == want)
    rows = [r for r in book.rows if _hit(r["target"], r.get("id")) and (src is None or r["source"] == src)]
    miss = {id(r) for r in AB.presence(book, w)["missing"]}
    live = [r for r in rows if r["status"] == AB.LIVE]
    by = {}
    for r in live:
        by[r["source"]] = by.get(r["source"], 0) + 1
    print(f"■ 별칭 대장 — 살아 있음 {len(live):,} · 거부 {len(rows) - len(live):,} · 골격 대상 "
          f"{sum(1 for r in live if r.get('skeleton')):,} ({paths.show(store.path(store.ALIAS_BOOK))} — 기본 fresh가 남긴다)"
          + "".join(f" · {k} {v}" for k, v in (("층", layer), ("출처", src), ("대상", want)) if v))
    print("  출처별 — " + " · ".join(f"{s} {by.get(s, 0):,}" for s in AB.SOURCES))
    print(f"  그래프에 있음 {sum(1 for r in live if id(r) not in miss):,} · 없음 {sum(1 for r in live if id(r) in miss):,}")
    nodes = {}
    for _l, n in w.nodes():
        if is_live(n):
            nodes.setdefault(AB._key("", AB.name(n))[:3], n)
    groups = {}
    for r in rows:
        groups.setdefault(AB._key("", r["target"])[:3], []).append(r)
    if want is not None and src is None:              # 대상을 지목하면 대장 항목이 없어도 seed 별칭을 보인다
        for k, n in nodes.items():
            if _hit(AB.name(n), n["id"]):
                groups.setdefault(k, [])
    for k in sorted(groups, key=lambda k: (str(k[0]), str(k[1]), k[2])):
        rs, n = groups[k], nodes.get(k)
        t = rs[0]["target"] if rs else AB.name(n)
        skel = (n or {}).get("status") == "seed" or any(r.get("skeleton") for r in rs)
        print(f"  ── {t['canonical']}  ({t['category']} · {t['layer']}" + (" · 골격" if skel else "")
              + ("" if n else " · 그래프에 없음") + ")")
        seeds = sorted(a["surface"] for a in (n or {}).get("aliases") or [] if AB.is_seed(a))
        if seeds:
            print("     seed  " + " · ".join(seeds))
        for r in sorted(rs, key=lambda r: (r["status"] != AB.LIVE, r["surface"])):
            print(_entry_line(r, miss))
    if live:
        print("  ▶ 다음 줄 — 틀린 별칭은 거둔다: python run.py ops alias-reject <층> <대상> <표기> --actor <이름>"
              " (다시 붙이지 않는다 · 골격 대상이면 그다음 python run.py bootstrap)")
    return 0
