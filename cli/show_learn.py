# -*- coding: utf-8 -*-
"""칸 2.8 — **동의어 학습 화면** — 좌표 학습 목록 · 새 공정 후보 · 별칭 출처 (B101 ②③④).

    python run.py show learned        좌표 학습 기록(표기 · 노드 · 문서 · 적중 · 시각) + 새 공정 후보

읽기 전용이다. 승격·거부는 `run.py ops learn-promote|learn-reject <층> <표기> --actor`.
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
