# -*- coding: utf-8 -*-
"""칸 0.3 — I축 도구 CLI — n5의 사람 진입점 (CLI+파일, 구현문서 §0).

    python cli/ops.py rename <층> <id> <새 canonical> --actor <사람> [--reason …]
    python cli/ops.py merge  <층> <id> <into-id> --actor … [--canonical …] [--survivor <id>]
    python cli/ops.py split  <층> <id> <배분표.json> --actor …
    python cli/ops.py obsolete <층> <id> --actor … [--replaced-by <id>]
    python cli/ops.py delete-edge <층> <src> <rel> <dst> --actor …
    python cli/ops.py alias  <층> <node_id|canonical> <표기> --actor <사람>
    python cli/ops.py alias-reject <층> <node_id|canonical> <표기> --actor <사람> [--yes]   별칭 거두기 (B108 ①)
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


from core.state import ops, store


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
            print(f"[거부] '{surface}' → {r['canonical']} 학습 기록을 지웠다 — 다음 인입에서 다시 묻는다" if r["canonical"]
                  else f"[거부] '{surface}' 목록 밖 기억(null 답)을 지웠다 — 다음 인입에서 그 표기만 다시 묻는다 "
                       "(새 공정 후보 화면에는 남는다)")
    except coord_learn.LearnRefused as e:
        print(f"[거부] {e}")
        return 1
    return 0


def backfill_lines(bf):
    """이름 채움의 줄들(B107 ①) — 재구축 계획 · `ops replay` · 옛 자리 옮김이 같은 줄을 낸다. 이름 없음은
    목록(연산 · 그래프에서 못 찾은 id · 행위자 · 시각) — 재구축하면 그 연산은 돌아오지 않는다."""
    k = len(bf["nameless"])
    out = [f"사람 판단 기록 {bf['total']:,}건 · 이름 채움 {bf['backfilled']:,}"
           + (f"(이번에 {bf['filled']:,})" if bf["filled"] else "")
           + f" · 이름 없음 {k:,}(재구축하면 돌아오지 않는다)"]
    for x in bf["nameless"]:
        out.append(f"  이름 없음 — {x['op']} · {', '.join(map(str, x['ids']))} · {x['actor']} · {x['at']}")
    return out


def replay_lines(r):
    """사람 판단 재생의 줄들(B106 ③) — 한 일 · 이미 그 상태 · 대상 없음(목록 · 기록은 남는다) · 이름 없음 ·
    재생 안 함 · 거부. 재구축 보고와 `ops replay`가 같은 줄을 낸다."""
    out = [f"사람 판단 재생 — 한 일 {len(r['done']):,} · 이미 그 상태 {len(r['already']):,} · "
           f"대상 없음 {len(r['missing']):,} · 기록에 이름 없음 {len(r['no_names']):,} · "
           f"재생 안 함 {len(r['skipped']):,} · 거부 {len(r['refused']):,}"]
    for k, head in (("missing", "대상 없음"), ("no_names", "이름 없음"), ("refused", "거부"),
                    ("skipped", "재생 안 함")):
        for x in r[k]:
            out.append(f"  {head} — {x['op']} · {x['what']} · {x['actor']} · {x['at']}"
                       + (f" · {x['reason']}" if x.get("reason") else ""))
    if r["missing"]:
        out.append("  ▶ 기록은 남았다 — 이름을 되살리면(seed를 되돌리고 python run.py rebuild) 다음 재생이 다시 한다")
    return out


def _replay(a):
    """`ops replay` — 기록 순서대로 이름으로 되살린다(`--dry-run`은 계획 · 쓰기 0)."""
    from core.state import oplog
    r = oplog.replay(dry_run=a.dry_run)
    for ln in backfill_lines(r["backfill"]) + replay_lines(r):
        print(ln)
    if a.dry_run:
        print("  (계획만 — 그래프 쓰기 0" + (" · 채운 이름은 기록에 남았다" if r["backfill"]["filled"] else "")
              + f") ▶ 다음 줄 — 실행: python run.py ops replay all --actor {a.actor}")
    return 0


def _alias_reject(a):
    """`ops alias-reject <층> <대상> <표기>` — 별칭 거두기(B108 ①). 계획 먼저 · 비대화형은 계획만(실행은 `--yes`)."""
    from cli._gate import approved
    if len(a.args) < 2:
        print("■ 거부 — 대상과 표기를 달라: python run.py ops alias-reject <층> <node_id|canonical> <표기> --actor <이름>")
        return 2
    target, surface = a.args[0], " ".join(a.args[1:]).strip()
    pv = ops.alias_reject(a.layer, target, surface, a.actor, a.reason, dry_run=True)
    r = pv["entry"]
    print(f"■ 별칭 거두기 계획 — '{pv['surface']}' ↛ {pv['canonical']} ({pv['category']} · {pv['layer']}"
          + (" · 골격" if pv["skeleton"] else "") + ")")
    print(f"    노드 별칭 {'있음 → 뺀다' if pv['on_node'] else '없음'} · 사전 키 {len(pv['dict_keys']):,}"
          + (f"({' · '.join(pv['dict_keys'])}) → 걷는다" if pv["dict_keys"] else "")
          + " · 대장 " + (f"{r['source']} · {r['count']:,}회 · {r['status']}" if r else "없음") + " → 거부")
    if pv["already"]:
        print("    이미 거둔 별칭이다 — 할 것 없음")
        return 0
    if not approved(a.yes, f'python run.py ops alias-reject {a.layer} {target} "{surface}" --actor {a.actor} --yes'):
        return 0
    ops.alias_reject(a.layer, target, surface, a.actor, a.reason)
    print(f"[거둠] '{surface}' ↛ {pv['canonical']} — 노드 · 사전에서 뺐다 · 별칭 대장 「거부」"
          f"(다시 붙이지 않는다 · 재구축 뒤 ops replay가 다시 거둔다 · by {a.actor})")
    if pv["skeleton"]:
        print("  ▶ 다음 줄 — python run.py bootstrap   (골격 닫힌 목록에서 뺀다 — 판이 바뀐다)")
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


def _relink(a):
    """`ops relink all` — 재연결 훑기를 손으로(B113 ③ — 골격 `ALIASES` · `bootstrap` · `--coord` 기록 뒤 재인입 없이).
    계획(쓰기 0) → `--apply`면 인입 끝 마무리와 **같은 함수**(`entry.finalize` — 미러 · 재연결 바퀴)."""
    from core.build import retry as RT
    canon = None
    if a.coord:                                   # 문서 좌표를 기록하고 잇는다(재인입 없이 — `--doc` 필수)
        from cli import doc_coord as DC
        if not a.doc:
            print("■ 거부 — --coord는 문서와 같이: python run.py ops relink all --doc <doc_id> --coord <골격 이름> "
                  f"--actor {a.actor}")
            return 2
        try:
            canon = DC._resolve(a.coord.strip(), DC._nodes())
        except SystemExit as e:
            print(f"■ 거부 — {e}")
            return 2
        holds = sum(1 for x in store.read(store.QUEUE, []) if x.get("doc_id") == a.doc and RT.is_target(x)
                    and x.get("kind") == RT.COORD_HOLD)
        print(f"■ 문서 좌표 기록 — {a.doc} → {canon} (출처: 사람 · 그 문서의 좌표 미해소 보류 {holds:,}항목이 이 좌표로 다시 선다 · "
              f"아래 계획은 기록한 뒤의 판으로 센다)")
    pv = RT.plan(doc_coord=(a.doc, canon) if canon else None)
    t = pv["target"]
    print(f"■ 재연결 계획 — 대상 {sum(t.values()):,}" + (f"({' · '.join(f'{k} {v:,}' for k, v in sorted(t.items()))})"
                                                    if t else "")
          + f" · 이번에 볼 것 {pv['try']:,} · 판이 그대로라 건너뜀 {pv['same']:,} · 상한 도달 {pv['capped']:,}")
    if not a.apply:
        more = f" --doc {a.doc} --coord \"{a.coord}\"" if canon else ""
        print(f"  (계획만 — 쓰기 0) ▶ 다음 줄 — 실행: python run.py ops relink all{more} --actor {a.actor} --apply")
        return 0
    # 재연결은 판정 LLM을 부를 수 있다 — 쓰기 전에 인입과 같은 사전 점검(B98 ① · 실패면 기록 · 그래프 쓰기 0)
    from cli import preflight as PF
    from core.llm.narrow import narrow_choice
    if not PF.gate(chat=True, embed=narrow_choice()[0] == "embed", catalog=True):
        print("■ 재연결 멈춤 — 사전 점검에서 멈췄다 (문서 좌표 기록 · 그래프 쓰기 0) ▶ 위 다음 줄대로 고친 뒤 같은 명령")
        return 2
    if canon:
        from cli import doc_coord as DC
        DC.record(a.doc, canon, "사람")
    from core.build.entry import finalize
    fin = finalize()
    for ln in RT.rounds_text():
        print(f"    {ln}")
    print(f"  {fin['retry_line']}")
    print(f"  미러 — 새 짝 엣지 {fin['mirror_new']:,} · 비대칭(mirror_asymmetry) {fin['mirror_asym']:,} · by {a.actor}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="I축 인스턴스 변경 도구 (n5)")
    p.add_argument("op", choices=["rename", "merge", "split", "obsolete",
                                  "transfer", "delete-edge", "confirm", "alias", "alias-reject", "tidy",
                                  "learn-promote", "learn-reject", "review",
                                  "coord-ack", "coord-unack", "replay", "relink"])
    p.add_argument("layer")
    p.add_argument("args", nargs="*")
    p.add_argument("--actor", required=True, help="행위자 — 로그 5요소 중 하나(필수)")
    p.add_argument("--reason", default="")
    p.add_argument("--canonical", help="I2 — 사람이 확정한 canonical")
    p.add_argument("--survivor", help="I2 — 생존 id override (3단 규칙의 1순위)")
    p.add_argument("--replaced-by", dest="replaced_by", help="I4 — 대체 노드 id")
    p.add_argument("--parent", help="이관 — 새 부모 노드 id (소속 변경)")
    p.add_argument("--yes", action="store_true", help="미리보기 확인 후 실행")
    p.add_argument("--apply", action="store_true", help="tidy · relink — 계획이 아니라 실제로 한다")
    p.add_argument("--polarity", action="store_true", help="coord-ack — 쌍이 (극성, 노드)다")
    p.add_argument("--doc", help="confirm — 그 문서 실행이 만든 auto 노드 전부(문서 단위 확인 · B106 ④) · "
                                 "relink — 문서 좌표를 기록할 문서")
    p.add_argument("--coord", help="relink — 그 문서(--doc)의 문서 좌표(골격 이름)를 기록하고 잇는다(재인입 없이 · B113 ③)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="replay — 계획만(쓰기 0)")
    a = p.parse_args(argv)
    if a.op == "replay":
        return _replay(a)
    if a.op == "relink":
        return _relink(a)
    if (a.op == "confirm" and a.doc) or a.op == "alias-reject":
        try:
            return _confirm_doc(a) if a.op == "confirm" else _alias_reject(a)
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
                  f"· 조회 키 '{pv['key']}' · by {a.actor}" + (" · 거둔 별칭을 다시 이었다(거부 풂)"
                                                               if pv.get("revived") else ""))
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
