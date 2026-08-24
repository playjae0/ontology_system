# -*- coding: utf-8 -*-
"""I축 도구 CLI — n5의 사람 진입점 (CLI+파일, 구현문서 §0).

    python cli/ops.py rename <층> <id> <새 canonical> --actor <사람> [--reason …]
    python cli/ops.py merge  <층> <id> <into-id> --actor … [--canonical …] [--survivor <id>]
    python cli/ops.py split  <층> <id> <배분표.json> --actor …
    python cli/ops.py obsolete <층> <id> --actor … [--replaced-by <id>]
    python cli/ops.py delete-edge <층> <src> <rel> <dst> --actor …

**파급이 1건을 넘는 작업은 실행 전에 미리보기를 찍는다**(카드 G6). `--yes` 없이는
미리보기만 내고 멈춘다 — 승인 없는 파급은 이 도구의 설계상 존재하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


from core import ops


def show_preview(pv):
    print(f"■ 파급 미리보기 — {pv['op']} / {pv['target']}")
    print(f"    영향 노드 {pv['nodes']} · 영향 엣지 {pv['edges']}")
    if pv.get("survivor"):
        print(f"    생존자 canonical: {pv['survivor']}")
    if pv.get("canonical_candidates"):
        print("    canonical 후보 (빈도·출처 등급 — 확정은 사람이 한다):")
        for c in pv["canonical_candidates"][:6]:
            print(f"      · {c['canonical']}   빈도 {c['freq']} · status {c['status']}")
    if pv.get("canonical_chain"):
        print(f"    canonical 연쇄 대상 {len(pv['canonical_chain'])}건:")
        for c in pv["canonical_chain"]:
            print(f"      · {c}")


def main(argv=None):
    p = argparse.ArgumentParser(description="I축 인스턴스 변경 도구 (n5)")
    p.add_argument("op", choices=["rename", "merge", "split", "obsolete", "delete-edge"])
    p.add_argument("layer")
    p.add_argument("args", nargs="*")
    p.add_argument("--actor", required=True, help="행위자 — 로그 5요소 중 하나(필수)")
    p.add_argument("--reason", default="")
    p.add_argument("--canonical", help="I2 — 사람이 확정한 canonical")
    p.add_argument("--survivor", help="I2 — 생존 id override (3단 규칙의 1순위)")
    p.add_argument("--replaced-by", dest="replaced_by", help="I4 — 대체 노드 id")
    p.add_argument("--yes", action="store_true", help="미리보기 확인 후 실행")
    a = p.parse_args(argv)

    try:
        if a.op == "rename":
            nid, new = a.args
            pv = ops.rename(a.layer, nid, new, a.actor, a.reason, dry_run=True)
            show_preview(pv)
            if a.yes:
                ops.rename(a.layer, nid, new, a.actor, a.reason)
        elif a.op == "merge":
            nid, into = a.args
            pv = ops.merge(a.layer, nid, into, a.actor, a.canonical, a.survivor,
                           a.reason, dry_run=True)
            show_preview(pv)
            if a.yes:
                ops.merge(a.layer, nid, into, a.actor, a.canonical, a.survivor, a.reason)
        elif a.op == "split":
            nid, planfile = a.args
            plan = json.loads(Path(planfile).read_text(encoding="utf-8"))
            pv = ops.split(a.layer, nid, plan, a.actor, a.reason, dry_run=True)
            show_preview(pv)
            if a.yes:
                ops.split(a.layer, nid, plan, a.actor, a.reason)
        elif a.op == "obsolete":
            (nid,) = a.args
            pv = ops.obsolete(a.layer, nid, a.actor, a.replaced_by, a.reason,
                              dry_run=True)
            show_preview(pv)
            if a.yes:
                ops.obsolete(a.layer, nid, a.actor, a.replaced_by, a.reason)
        else:
            src, rel, dst = a.args
            print(ops.delete_edge(a.layer, src, rel, dst, a.actor, a.reason))
            return 0
    except ops.OpRefused as e:
        print(f"■ 거부 — {e}")
        return 2
    if not a.yes:
        print("\n    (미리보기만 수행했다. 실행하려면 --yes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
