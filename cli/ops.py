# -*- coding: utf-8 -*-
"""칸 0.3 — I축 도구 CLI — n5의 사람 진입점 (CLI+파일, 구현문서 §0).

    python cli/ops.py rename <층> <id> <새 canonical> --actor <사람> [--reason …]
    python cli/ops.py merge  <층> <id> <into-id> --actor … [--canonical …] [--survivor <id>]
    python cli/ops.py split  <층> <id> <배분표.json> --actor …
    python cli/ops.py obsolete <층> <id> --actor … [--replaced-by <id>]
    python cli/ops.py delete-edge <층> <src> <rel> <dst> --actor …
    python cli/ops.py alias  <층> <node_id|canonical> <표기> --actor <사람>
    python cli/ops.py coord-ack|coord-unack all "<상위>" "<하위>" [--polarity] --actor <사람> [--reason <메모>]
    python cli/ops.py confirm all --doc <doc_id> --actor <사람> [--yes]     문서 단위 일괄 확인 (B106 ④)
    python cli/ops.py replay  all --actor <사람> [--dry-run]               사람 판단 재생 — 이름으로 (B106 ③)

**파급이 1건을 넘는 작업은 실행 전에 미리보기를 찍는다**(카드 G6). `--yes` 없이는
미리보기만 내고 멈춘다 — 승인 없는 파급은 이 도구의 설계상 존재하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


from core.state import ops


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


def _small(pv):
    """**파급 1건 이하면 미리보기·`--yes`를 생략한다** (문서 4 §4.7).

    미리보기의 목적은 **위험 제거가 아니라 가시화**다 — 사람이 실행 전에 규모를
    보고 판단한다. 차단형 승인 게이트가 아니다(승인 게이트는 폐기됐다). 1건짜리
    작업에까지 확인을 강제하면 그것이 게이트가 되고, 폐기된 것이 이름만 바꿔
    돌아온다.

    판정은 `preview()`의 **노드·엣지 계수**로 한다 — 둘 다 1 이하일 때만 작다.
    """
    return (pv.get("nodes", 99) <= 1 and pv.get("edges", 99) <= 1
            and not pv.get("canonical_chain"))


def _tidy(a):
    """**정리**(B99 ⑩) — 사라진 노드를 가리키는 큐·사전·엣지. 기본 계획만 · `--apply`에서만 지운다.

        python run.py ops tidy all --actor <이름>            # 계획
        python run.py ops tidy all --actor <이름> --apply    # 지운다
    """
    from core.state import integrity
    r = integrity.tidy(apply=a.apply)
    head = "정리했다" if r["applied"] else "정리 계획(쓰기 0)"
    print(f"■ {head} — 사라진 노드를 가리키는 큐 {r['큐']:,}(사람 판단이 있어 남김 {r['큐_남김']:,}) · "
          f"사전 표기 {len(r['사전']):,} · 끝점 없는 엣지 "
          + (" · ".join(f"{k} {v:,}" for k, v in sorted(r["엣지"].items())) or "0"))
    for s, ids in r["사전"][:10]:
        print(f"    사전 '{s}' → 없는 노드 {', '.join(i[:8] for i in ids)}")
    if not r["applied"] and (r["큐"] or r["사전"] or r["엣지"]):
        print(f"  ▶ 다음 줄 — 지운다: python run.py ops tidy all --actor {a.actor} --apply")
    return 0


def _learn(a):
    """좌표 학습 기록의 승격·거부(B101 ②) — `<층>`은 좌표 층 자리표시(기록은 좌표 층 하나다)."""
    from core.state import coord_learn
    surface = " ".join(a.args).strip()
    try:
        if a.op == "learn-promote":
            r = coord_learn.promote(surface, a.actor)
            print(f"[승격] '{surface}' → {r['canonical']} — 골격 ALIASES에 더했다 ({r['file']})")
            print("  ▶ 다음 줄 — python run.py bootstrap   (사람 보증 별칭으로 맞는다)")
        else:
            r = coord_learn.reject(surface, a.actor)
            print(f"[거부] '{surface}' → {r['canonical']} 학습 기록을 지웠다 — 다음 인입에서 다시 묻는다")
    except coord_learn.LearnRefused as e:
        print(f"[거부] {e}")
        return 1
    return 0


def replay_lines(r):
    """사람 판단 재생의 줄들(B106 ③) — 한 일 · 이미 그 상태 · 대상 없음(목록 · 기록은 남는다) · 이름 없음 ·
    재생 안 함 · 거부. 재구축 보고와 `ops replay`가 같은 줄을 낸다."""
    out = [f"사람 판단 재생 — 한 일 {len(r['done']):,} · 이미 그 상태 {len(r['already']):,} · "
           f"대상 없음 {len(r['missing']):,} · 기록에 이름 없음 {len(r['no_names']):,} · "
           f"재생 안 함 {len(r['skipped']):,} · 거부 {len(r['refused']):,}"]
    for k, head in (("missing", "대상 없음"), ("refused", "거부"), ("skipped", "재생 안 함")):
        for x in r[k]:
            out.append(f"  {head} — {x['op']} · {x['what']} · {x['actor']} · {x['at']}"
                       + (f" · {x['reason']}" if x.get("reason") else ""))
    if r["missing"]:
        out.append("  ▶ 기록은 남았다 — 이름을 되살리면(seed를 되돌리고 python run.py rebuild) 다음 재생이 다시 한다")
    return out


def _replay(a):
    """`ops replay` — 기록 순서대로 이름으로 되살린다(`--dry-run`은 계획 · 쓰기 0)."""
    from core.state import oplog
    for ln in replay_lines(oplog.replay(dry_run=a.dry_run)):
        print(ln)
    if a.dry_run:
        print(f"  (계획만 — 쓰기 0) ▶ 다음 줄 — 실행: python run.py ops replay all --actor {a.actor}")
    return 0


def _confirm_doc(a):
    """`ops confirm all --doc <doc_id>` — 그 문서 실행이 만든 auto 노드를 한 번에 확정(B106 ④)."""
    from cli._gate import approved
    pv = ops.confirm_doc(a.doc, a.actor, a.reason, dry_run=True)
    print(f"■ 문서 단위 확인 계획 — {pv['doc']}: auto 노드 {pv['nodes']:,}("
          + " · ".join(f"{c} {n:,}" for c, n in pv["by_category"].items()) + ")")
    for lay, nid, canon, cat in pv["top"]:
        print(f"    · {canon}  ({cat} · {lay} · {nid[:8]})")
    if pv["nodes"] > len(pv["top"]):
        print(f"    … {pv['nodes'] - len(pv['top']):,}개 더")
    if pv["uncertain"]:
        print(f"    불확실 {pv['uncertain']:,}건은 넣지 않는다(고르는 일) ▶ python run.py ops review all --actor {a.actor}")
    if not pv["nodes"] or not approved(a.yes, f"python run.py ops confirm all --doc {a.doc} --actor {a.actor} --yes"):
        return 0
    ops.confirm_doc(a.doc, a.actor, a.reason)
    print(f"[확정] {pv['doc']} — auto 노드 {pv['nodes']:,}개 → confirmed (by {a.actor}) · 큐 종결 auto_node")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="I축 인스턴스 변경 도구 (n5)")
    p.add_argument("op", choices=["rename", "merge", "split", "obsolete",
                                  "transfer", "delete-edge", "confirm", "alias", "tidy",
                                  "learn-promote", "learn-reject", "review",
                                  "coord-ack", "coord-unack", "replay"])
    p.add_argument("layer")
    p.add_argument("args", nargs="*")
    p.add_argument("--actor", required=True, help="행위자 — 로그 5요소 중 하나(필수)")
    p.add_argument("--reason", default="")
    p.add_argument("--canonical", help="I2 — 사람이 확정한 canonical")
    p.add_argument("--survivor", help="I2 — 생존 id override (3단 규칙의 1순위)")
    p.add_argument("--replaced-by", dest="replaced_by", help="I4 — 대체 노드 id")
    p.add_argument("--parent", help="이관 — 새 부모 노드 id (소속 변경)")
    p.add_argument("--yes", action="store_true", help="미리보기 확인 후 실행")
    p.add_argument("--apply", action="store_true", help="tidy — 계획이 아니라 실제로 지운다")
    p.add_argument("--polarity", action="store_true", help="coord-ack — 쌍이 (극성, 노드)다")
    p.add_argument("--doc", help="confirm — 그 문서 실행이 만든 auto 노드 전부(문서 단위 확인 · B106 ④)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="replay — 계획만(쓰기 0)")
    a = p.parse_args(argv)
    if a.op == "replay":
        return _replay(a)
    if a.op == "confirm" and a.doc:
        try:
            return _confirm_doc(a)
        except ops.OpRefused as e:
            print(f"■ 거부 — {e}")
            return 2
    if a.op in ("coord-ack", "coord-unack"):
        from cli import coord_queue                 # 좌표 쌍 확인 · 취소 (B105 ④ — 메모는 --reason)
        return coord_queue.run_ops(a)
    if a.op == "tidy":
        return _tidy(a)
    if a.op in ("learn-promote", "learn-reject"):
        return _learn(a)
    if a.op == "review":
        from cli import ops_review                  # 불확실 일괄 검토 (B101 ⑤)
        return ops_review.run(a)

    try:
        if a.op == "rename":
            nid, new = a.args
            pv = ops.rename(a.layer, nid, new, a.actor, a.reason, dry_run=True)
            if _small(pv):
                ops.rename(a.layer, nid, new, a.actor, a.reason)
                return 0
            show_preview(pv)
            if a.yes:
                ops.rename(a.layer, nid, new, a.actor, a.reason)
        elif a.op == "confirm":
            # **모양이 아니라 지위가 바뀐다**(B73 ④) — 연쇄가 없어 미리보기를
            # 거치지 않고 바로 확정하고, 무엇이 바뀌었는지 한 줄로 말한다.
            (nid,) = a.args
            pv = ops.confirm(a.layer, nid, a.actor, a.reason)
            print(f"[확정] {pv['canonical']} — status {pv['from']} → confirmed "
                  f"(by {a.actor}) · 큐 종결 {', '.join(pv['queue'])}")
        elif a.op == "alias":
            # **표기 하나를 잇는다** — 파급 1건이라 미리보기가 없다(문서 4 §4.7-4).
            nid, surface = a.args
            pv = ops.alias(a.layer, nid, surface, a.actor, a.reason)
            print(f"[등재] '{pv['surface']}' → {pv['canonical']} ({pv['target'][:6]}) "
                  f"· 조회 키 '{pv['key']}' · by {a.actor}")
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
        elif a.op == "transfer":
            # **이관 — 스코프 변경 연쇄**(문서 4 §4.7 미리보기 대상 · §4.9).
            # I축 4연산과 별개 작업이고 **건별 사람 판단**이다.
            nid = a.args[0]
            new_parent = a.parent or (a.args[1] if len(a.args) > 1 else None)
            if not new_parent:
                print("■ 거부 — 새 부모를 달라: --parent <node_id>")
                return 2
            pv = ops.transfer(a.layer, nid, new_parent, a.actor, a.reason, dry_run=True)
            if _small(pv):
                ops.transfer(a.layer, nid, new_parent, a.actor, a.reason)
                return 0
            show_preview(pv)
            if a.yes:
                ops.transfer(a.layer, nid, new_parent, a.actor, a.reason)
        elif a.op == "obsolete":
            (nid,) = a.args
            pv = ops.obsolete(a.layer, nid, a.actor, a.replaced_by, a.reason,
                              dry_run=True)
            if _small(pv):
                ops.obsolete(a.layer, nid, a.actor, a.replaced_by, a.reason)
                return 0
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
    if not a.yes and a.op not in ("confirm", "alias"):
        # **확정·표기 등재는 미리보기가 없다**(B73 ④ · B74 ⑤) — 연쇄가 없어
        # 그 자리에서 끝난다.
        # 이 줄을 그대로 두면 「안 됐다」로 읽힌다(실행은 이미 끝났는데).
        print("\n    (미리보기만 수행했다. 실행하려면 --yes)")
    return 0


if __name__ == "__main__":
    # **공통 진입 함수 하나**(B99 ③) — 로그 설정 · 화면 전체를 명령 로그로 · 실행 머리/끝 줄
    from cli import _entry
    sys.exit(_entry.main_module("cli.ops", main))
