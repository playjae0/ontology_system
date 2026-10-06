# -*- coding: utf-8 -*-
"""칸 0.3 — **불확실 일괄 검토** — `uncertain_match`를 표로 보고 한 건씩 합침 / 별개 / 건너뜀 (B101 ⑤).

    python run.py ops review <층|all> --actor <이름>

손은 지금의 `ops.merge`·`ops.confirm`이다(두 벌 0) — 합치면 사람이 친 merge(별칭 출처 사람) ·
별개면 확정(confirmed) · 건너뜀은 아무것도 쓰지 않는다. 층에 걸친 노드도 같은 손이다(B100 —
층 전부를 연다). **비대화형(터미널 아님)은 계획만** 낸다(쓰기 0).
"""
from __future__ import annotations

import sys

from core.state import store


def items(layer=None):
    """검토 대상 — 사람 판단이 없는 `uncertain_match` · `layer`면 그 층(집) 것만."""
    out = []
    for x in store.read(store.QUEUE, []):
        if x.get("kind") != "uncertain_match" or x.get("resolution"):
            continue
        pl = x.get("payload") or {}
        if layer not in (None, "all") and pl.get("layer") != layer:
            continue
        near = pl.get("nearest") or {}
        score = next((t.get("score") for t in near.get("top") or [] if t.get("id") == near.get("id")), None)
        out.append({"doc_id": x.get("doc_id"), "surface": pl.get("surface"), "node_id": pl.get("node_id"),
                    "canonical": pl.get("canonical"), "layer": pl.get("layer"),
                    "near_id": near.get("id"), "near": near.get("canonical"), "score": score,
                    "guard": near.get("by") == "가드"})
    return out


def table(rows):
    print(f"■ 불확실 일괄 검토 — {len(rows):,}건 (판정이 확신하지 못해 새로 만든 노드 · 가장 가까운 후보)")
    if rows:
        print(f"  {'#':>3} {'표기':<18} {'새 노드':<22} {'가장 가까운 후보':<22} {'점수':>6}  {'문서':<12} 가드")
    for i, r in enumerate(rows, 1):
        sc = "" if r["score"] is None else f"{r['score']:.2f}"
        print(f"  {i:>3} {str(r['surface'])[:18]:<18} {str(r['canonical'])[:22]:<22} "
              f"{str(r['near'] or '(없음)')[:22]:<22} {sc:>6}  {str(r['doc_id'])[:12]:<12} "
              f"{'예' if r['guard'] else ''}")


def decide(r, ans, actor):
    """한 건의 답 — `m`(합침 · 가까운 후보로) · `c`(별개 · 확정) · 그 밖(건너뜀). 돌려주는 것은 한 일."""
    from core.state import ops
    if ans == "m" and r["near_id"]:
        ops.merge(r["layer"], r["node_id"], r["near_id"], actor, reason="ops review — 합침")
        store.resolve_item("uncertain_match", lambda p, _n=r["node_id"]: p.get("node_id") == _n,
                           actor=actor, decision="merged", at=store._now(), note="ops review")
        return "합침"
    if ans == "c":
        ops.confirm(r["layer"], r["node_id"], actor, reason="ops review — 별개")
        return "별개"
    return "건너뜀"


def run(a, ask=None):
    """`ops review` — 표 · 한 건씩 묻기(`ask(문면) -> 답`) · 비대화형은 계획만."""
    rows = items(a.layer)
    table(rows)
    if not rows:
        return 0
    if ask is None and not sys.stdin.isatty():
        print("  (비대화형 — 계획만 · 쓰기 0) ▶ 다음 줄 — 터미널에서: "
              f"python run.py ops review {a.layer} --actor {a.actor}")
        return 0
    ask = ask or input
    done = {"합침": 0, "별개": 0, "건너뜀": 0}
    for i, r in enumerate(rows, 1):
        q = (f"  [{i}/{len(rows)}] '{r['surface']}' — 합침(m: → {r['near'] or '후보 없음'}) / "
             f"별개(c) / 건너뜀(s) > ")
        ans = (ask(q) or "").strip().lower()[:1]
        try:
            did = decide(r, ans, a.actor)
        except Exception as e:                      # noqa: BLE001 — 거부는 그 건만 건너뛴다
            print(f"     [거부] {e}")
            did = "건너뜀"
        done[did] += 1
    print(f"■ 검토 끝 — 합침 {done['합침']:,} · 별개 {done['별개']:,} · 건너뜀 {done['건너뜀']:,}")
    return 0
