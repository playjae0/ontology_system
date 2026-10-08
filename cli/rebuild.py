# -*- coding: utf-8 -*-
"""칸 0.3 — **재구축 한 명령** — 지우기 전에 문서 목록을 남기고, 보존 fresh → bootstrap → 처음 인입 순서로
재인입 → 사람 판단 재생 → 보고 (B106 ① · 사용자 결정 2026-10-07·08).

    python run.py rebuild [--yes] [--no-replay] [--allow-mock]

**같은 문서 · 같은 순서 · 같은 판정이면 같은 그래프다** — LLM은 판정이 비었을 때만 부른다: 판정은 남긴
대장에서 재생하고(`core/build/replay` — B106 ②) 산문 추출 · 구조 지도 · 좌표 학습은 보존 fresh가 남긴
것을 재사용 판정 그대로 쓴다. 사람 판단은 ②등록의 기록을 이름으로 되살린다(`ops replay` — B106 ③).

  ① 문서 대장(③ `doc_registry.json`)에서 문서 · **처음 인입 순서**(대장의 저장 순서 — 처음 들어온 자리에 서고
     재인입은 자리를 지킨다 · `first_ingested_at`은 봉투의 `parsed_at`이라 시각이 아니다: 운영 파싱은 파서 기본값을
     싣는다) · 원본 경로 · doc_type · 사람 판단(`duplicate_ok` · 그림 뺌) · 개정 번호를 읽어 ④ `work/rebuild/plan.json`에
     남긴다 — 지우는 동안에도 남겨(보존 fresh의 `keep`) 도중에 끊기면 다음 실행이 그 계획에서 이어 간다
     (문서 대장이 비었을 때만)
  ② `init --fresh`(보존) ③ `bootstrap` ④ 문서마다 같은 순서로 인입(문서 좌표 · 시트 역할은 ②등록이 갖는다)
  ⑤ `ops replay` ⑥ 보고 — 문서 수 · 판정 재생 · 재판정(사유별) · LLM 호출(추출 · 판정 · 태깅) · 사람 판단 재생 ·
     대상 없음 목록 · 원본 없음 목록

**비대화형은 계획만**(`ops review`와 같은 규칙 — 실행은 `--yes`) · 터미널이면 묻는다. 계획은 「지울 것 ·
남길 것 · 다시 넣을 문서 순서」다. 원본이 없는 문서는 건너뛰고 목록에 남긴다(지어내지 않는다).
"""
from __future__ import annotations

import json
from pathlib import Path

from core import paths
from core.state import store


def plan_path():
    """④ 재구축 계획 — 다시 만들 수 있는 장부다(문서 대장이 있으면 그것이 정본)."""
    return paths.work("rebuild", "plan.json")


def from_registry():
    """문서 대장 → 다시 넣을 문서 — **처음 인입 순서 = 대장의 저장 순서**(인입은 새 문서를 끝에 더하고 재인입은
    그 자리를 덮는다 — `core/build/ingest.register_doc`). 시각 열로 다시 줄 세우지 않는다(위 머리말)."""
    rows = []
    for doc_id, e in store.read(store.DOC_REGISTRY, {}).items():
        src = e.get("source_path")
        rows.append({"doc_id": doc_id, "doc_type": e.get("doc_type"), "source_path": src,
                     "path": str(paths.from_home(src)) if src else None,
                     "revision": e.get("revision"), "first_ingested_at": e.get("first_ingested_at"),
                     "duplicate_ok": bool(e.get("duplicate_ok")),
                     "images_skipped": bool(e.get("images_skipped"))})
    return rows


def make_plan():
    """계획 — `{docs, resumed}`. 문서 대장이 비었고 지난 계획이 있으면 그 계획에서 이어 간다."""
    docs, resumed = from_registry(), False
    if not docs and plan_path().exists():
        docs, resumed = json.loads(plan_path().read_text(encoding="utf-8")).get("docs") or [], True
    for d in docs:
        d["exists"] = bool(d.get("path")) and Path(d["path"]).is_file()
    return {"docs": docs, "resumed": resumed}


def show_plan(plan):
    from core.state import init as I
    docs = plan["docs"]
    go = [d for d in docs if d["exists"]]
    print(f"■ 재구축 계획 — 문서 {len(docs):,}(다시 넣을 것 {len(go):,} · 원본 없음 {len(docs) - len(go):,})"
          + (" · 지난 계획에서 이어 간다(문서 대장이 비었다)" if plan["resumed"] else ""))
    print("  지울 것 — ③진실 data/ · ④작업 work/ · ⑤파생 export/ (아래 남길 것 빼고)")
    from core.state import oplog
    print("  남길 것 — " + " · ".join(f"{l} {paths.show(p)}" for l, p in I.kept())
          + f" · ②등록 registry/(사람 판단 기록 {len(oplog.read()):,}건) · layers/ · ⓪원본 raw/ · golden/")
    print("  다시 넣을 순서(처음 인입 순서):")
    for i, d in enumerate(go, 1):
        flags = [f for f, on in (("중복 허용", d["duplicate_ok"]), ("그림 뺌", d["images_skipped"])) if on]
        print(f"    {i:>3}. {d['doc_id']:<20} {str(d['doc_type'] or '?'):<10} {d['source_path']}"
              + (f"  [{' · '.join(flags)}]" if flags else ""))
    miss = [d for d in docs if not d["exists"]]
    if miss:
        print("  원본 없음(건너뛴다 — 원본을 그 자리에 두면 다음 재구축이 넣는다):")
        for d in miss:
            print(f"     · {d['doc_id']:<20} {d['source_path']}")


def _calls(u0, u1):
    """지점별 LLM 호출 수 차이 — `{추출, 판정, 태깅, 그 밖}`."""
    from core.llm.gateway import POINTS
    names = {POINTS["extract"]: "추출", POINTS["judge"]: "판정", POINTS["coord_tag"]: "태깅"}
    out = {"추출": 0, "판정": 0, "태깅": 0, "그 밖": 0}
    for pt, v in u1.items():
        out[names.get(pt, "그 밖")] += v["calls"] - (u0.get(pt) or {}).get("calls", 0)
    return out


def execute(plan, *, bootstrap, screen, replay=True):
    """계획대로 — 돌려주는 것은 보고 묶음."""
    from cli import ingest_batch
    from core.build import replay as RP
    from core.llm import gateway
    from core.state import init as I, log, oplog
    store.atomic_write_bytes(plan_path(), (json.dumps({"docs": plan["docs"]}, ensure_ascii=False, indent=2)
                                           + "\n").encode("utf-8"))
    u0 = gateway.usage_by()
    rep = {}
    # 남길 것 + 계획 + **이 실행의 명령 로그**(지우면 다시 열리지만 계획 줄이 로그에서 사라진다 — 화면에 나온 것은 로그에도)
    I.init(fresh_=True, keep=[plan_path()] + ([log.LOG_PATH] if log.LOG_PATH else []), report=rep)
    screen(rep, False, "[재구축 fresh]")
    rc = bootstrap([])
    if rc:
        print("■ 재구축 멈춤 — bootstrap이 멈췄다(위 문면) · 계획은 남았다: 고친 뒤 python run.py rebuild --yes")
        return {"rc": rc}
    RP.reset(off=None if replay else "끔")
    items = [(Path(d["path"]), {"doc_type": d["doc_type"], "no_images": d["images_skipped"],
                                "allow_duplicate": d["duplicate_ok"]})
             for d in plan["docs"] if d["exists"]]
    rows = ingest_batch.ingest_list(items)
    ops = oplog.replay()
    return {"rc": 0, "rows": rows, "judge": dict(RP.STATS), "ops": ops,
            "calls": _calls(u0, gateway.usage_by()),
            "missing": [d for d in plan["docs"] if not d["exists"]]}


def report(r):
    from cli.ingest import OK
    rows, j, ops, c = r["rows"], r["judge"], r["ops"], r["calls"]
    ok = sum(1 for x in rows if x["status"] == OK)
    print(f"■ 재구축 끝 — 문서 {len(rows) + len(r['missing']):,}(성공 {ok:,} · 실패·보류 {len(rows) - ok:,} · "
          f"원본 없음 {len(r['missing']):,})")
    print(f"  판정 — 재생 {j['재생']:,} · 재판정 {j['재판정']:,}(키 없음 {j['키 없음']:,} · 대상 없음 {j['대상 없음']:,} · "
          f"끔 {j['끔']:,})")
    print(f"  LLM 호출 — 추출 {c['추출']:,} · 판정 {c['판정']:,} · 태깅 {c['태깅']:,} · 그 밖 {c['그 밖']:,}")
    from cli.ops import replay_lines
    for ln in replay_lines(ops):
        print("  " + ln)
    for d in r["missing"]:
        print(f"  원본 없음 — {d['doc_id']} · {d['source_path']} (원본을 그 자리에 두고 다시 재구축)")


def main(argv, *, bootstrap, screen):
    """`run.py rebuild` — `bootstrap`·`screen`은 `run.py`가 넘긴다(같은 명령 · 두 벌 0)."""
    from cli._gate import require_live_or_allow
    args = require_live_or_allow(list(argv), command="rebuild")       # mock 관문 (B48)
    unknown = [a for a in args if a not in ("--yes", "--no-replay")]
    if unknown:
        raise SystemExit(f"[재구축] 모르는 인자 {unknown} — "                              # [사용법]
                         "python run.py rebuild [--yes] [--no-replay]")
    plan = make_plan()
    show_plan(plan)
    if not plan["docs"]:
        print("  다시 넣을 문서가 없다 — 문서 대장이 비었고 지난 계획도 없다(인입부터: python run.py ingest-dir)")
        return 0
    from cli._gate import approved
    if not approved("--yes" in args, "python run.py rebuild --yes"):
        return 0
    r = execute(plan, bootstrap=bootstrap, screen=screen, replay="--no-replay" not in args)
    if r.get("rc"):
        return r["rc"]
    report(r)
    return 0 if all(x["status"] == "성공" for x in r["rows"]) else 1
