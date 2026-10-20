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
  ①′ **지우기 전에 사전 점검**(B111 ② — 인입 일괄과 같은 판정 함수 · 실행당 1회 묶음 · 그림은 계획의 문서
     목록) — 실패면 그래프 그대로 멈춘다(쓰기 0) · 통과한 묶음을 인입에 넘겨 다시 묻지 않는다
  ② `init --fresh`(보존) ③ `bootstrap` ④ 문서마다 같은 순서로 인입(문서 좌표 · 시트 역할은 ②등록이 갖는다)
  ⑤ `ops replay` ⑥ 보고 — 문서 수 · 판정 재생 · 재판정(사유별) · LLM 호출(추출 · 판정 · 태깅) · 사람 판단 재생 ·
     대상 없음 목록 · 원본 없음 목록 · 별칭 대장(그래프에 있음 · 없음 — 목록)

**쌓인 별칭은 지우기 전에 이름으로 남긴다**(B108 ① · ③ `data/alias_book.json` — 보존 fresh가 남긴다): 계획이 지금
그래프의 seed 밖 별칭 중 대장에 없는 것을 채우고, 재구축의 bootstrap이 골격 대상 별칭을 스냅샷 전에 싣는다.

**비대화형은 계획만**(`ops review`와 같은 규칙 — 실행은 `--yes`) · 터미널이면 묻는다. 계획은 「지울 것 ·
남길 것 · 다시 넣을 문서 순서」다. 원본이 없는 문서는 건너뛰고 목록에 남긴다(지어내지 않는다).

**끝나지 않은 재구축의 정본은 계획 파일이다**(B111 ② · 사내 실측 2026-10-15 — 둘째 문서 도중에 끊긴 재구축의
다음 계획이 문서 대장 둘로 줄었다): 계획 파일에 진행 표시 — 실행 시작에 「진행 중」, **계획의 문서가 전부 성공해야**
「끝」(원본 없음도 끝이 아니다 — 원본을 두면 다음 재구축이 넣는다). 「진행 중」이면 문서 대장이 비었든 아니든 그
목록에서 이어 간다 — 끊긴 방식과 무관하다(사전 점검 실패 · 문서 실패 · 중단 · 되돌림 손이 돌지 못한 종료).
"""
from __future__ import annotations

import json
from pathlib import Path

from core import paths
from core.state import store


#: 계획 파일의 진행 표시(B111 ②) — 「끝」이거나 없으면 문서 대장이 정본 · 「진행 중」이면 계획 파일이 정본
IN_PROGRESS, DONE = "진행 중", "끝"


def plan_path():
    """④ 재구축 계획 — 다시 만들 수 있는 장부다(끝난 재구축 뒤에는 문서 대장이 정본)."""
    return paths.work("rebuild", "plan.json")


def last_plan():
    """지난 계획 파일 — `{docs, status}` 또는 None. 진행 표시 없는 옛 파일은 `status` None이다."""
    return json.loads(plan_path().read_text(encoding="utf-8")) if plan_path().exists() else None


def _write_plan(docs, status):
    store.atomic_write_bytes(plan_path(), (json.dumps({"docs": docs, "status": status}, ensure_ascii=False,
                                                      indent=2) + "\n").encode("utf-8"))


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
    """계획 — `{docs, resumed, registry_n, backfill, alias_book}`. 지난 계획이 「진행 중」이면 문서 대장과 무관하게
    그 계획에서 이어 간다(B111 ② — 대장 `registry_n`건은 그 도중의 것) · 진행 표시 없는 옛 파일은 대장이 비었을 때만.

    **사람 판단 기록의 이름을 여기서 채운다**(B107 ① — fresh 앞 · 대상 id가 그래프에 살아 있는 마지막 순간 ·
    비대화형 계획만이어도 채운다 — 채움은 기록에 남고 그래프는 건드리지 않는다). **별칭 대장도 같은 자리에서
    채운다**(B108 ① — 지금 그래프의 seed 밖 별칭 중 대장에 없는 것 · 이름으로)."""
    from core.state import alias_book, oplog
    docs, resumed, last = from_registry(), False, last_plan()
    n_reg = len(docs)
    if last and (last.get("status") == IN_PROGRESS or (not docs and last.get("status") is None)):
        docs, resumed = last.get("docs") or [], True
    for d in docs:
        d["exists"] = bool(d.get("path")) and Path(d["path"]).is_file()
    return {"docs": docs, "resumed": resumed, "registry_n": n_reg,
            "backfill": oplog.backfill(), "alias_book": alias_book.backfill()}


def show_plan(plan):
    from core.state import init as I
    docs = plan["docs"]
    go = [d for d in docs if d["exists"]]
    print(f"■ 재구축 계획 — 문서 {len(docs):,}(다시 넣을 것 {len(go):,} · 원본 없음 {len(docs) - len(go):,})")
    if plan["resumed"]:
        print(f"  지난 재구축이 끝나지 않았다 — 계획 파일에서 이어 간다 · 문서 대장 {plan['registry_n']:,}건은 "
              f"그 도중의 것 ({paths.show(plan_path())})")
    print("  지울 것 — ③진실 data/ · ④작업 work/ · ⑤파생 export/ (아래 남길 것 빼고)")
    print("  남길 것 — " + " · ".join(f"{l} {paths.show(p)}" for l, p in I.kept())
          + " · ②등록 registry/(사람 판단 기록 — 아래 줄) · layers/ · ⓪원본 raw/ · golden/")
    from cli.ops import backfill_lines
    for ln in backfill_lines(plan["backfill"]):
        print("  " + ln)
    ab = plan["alias_book"]
    print(f"  별칭 대장 {ab['total']:,}(이번에 채움 {ab['filled']:,}) · 골격 대상 {ab['skeleton']:,}"
          + (f" · 거부 {ab['rejected']:,}" if ab["rejected"] else "")
          + " — 재구축의 bootstrap이 골격 대상 별칭을 스냅샷 전에 싣는다")
    # 좌표 태깅의 null 답은 닫힌 목록 판과 함께 기억된다(B107 ②) — 판을 적기 전의 기록은 이번에 한 번 다시 묻는다
    from core.state import coord_learn
    _old = sum(1 for r in coord_learn.book()["목록밖"].values() if not r.get("list_version"))
    if _old:
        print(f"  좌표 학습 — 목록 밖 기억 판 없음 {_old:,}종(판을 적기 전의 null 답 — 이번 재구축이 한 번 다시 "
              f"묻는다 · 태깅 ≤ {_old:,} · 그 뒤는 판과 함께 기억)")
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
    """지점별 LLM 호출 수 차이 — `{추출, 판정, 태깅, 개요, 보강, 그 밖}`(개요 ⑪ · 연결 보강 ⑫ — B115 · 재구축은 재생이라 0이어야 한다)."""
    from core.llm.gateway import POINTS
    names = {POINTS["extract"]: "추출", POINTS["judge"]: "판정", POINTS["coord_tag"]: "태깅",
             POINTS["outline"]: "개요", POINTS["reinforce"]: "보강"}
    out = {"추출": 0, "판정": 0, "태깅": 0, "개요": 0, "보강": 0, "그 밖": 0}
    for pt, v in u1.items():
        out[names.get(pt, "그 밖")] += v["calls"] - (u0.get(pt) or {}).get("calls", 0)
    return out


def execute(plan, *, bootstrap, screen, replay=True):
    """계획대로 — 돌려주는 것은 보고 묶음."""
    from cli import ingest_batch
    from core.build import replay as RP
    from core.llm import gateway
    from core.state import init as I, oplog
    items = [(Path(d["path"]), {"doc_type": d["doc_type"], "no_images": d["images_skipped"],
                                "allow_duplicate": d["duplicate_ok"]})
             for d in plan["docs"] if d["exists"]]
    # **지우기 전에 끝까지 갈 수 있는지 잰다**(B111 ②) — 실패면 그래프 · 계획 파일 그대로(쓰기 0)
    ok, pf = ingest_batch.preflight_list(items)
    if not ok:
        print("■ 재구축 멈춤 — 지우기 전에 멈췄다 — 그래프 그대로 (계획 파일 · 상태 폴더 쓰기 0)")
        print("  ▶ 다음 줄 — 위 원인을 고친 뒤(연결이면 python run.py llm-check) 같은 명령: python run.py rebuild --yes")
        return {"rc": 1}
    _write_plan(plan["docs"], IN_PROGRESS)
    u0 = gateway.usage_by()
    rep = {}
    # 남길 것(명령 로그 포함 — 재구축 전 로그도 · B109 ①) + 계획
    I.init(fresh_=True, keep=[plan_path()], report=rep)
    screen(rep, False, "[재구축 fresh]")
    rc = bootstrap([])
    if rc:
        print("■ 재구축 멈춤 — bootstrap이 멈췄다(위 문면) · 계획은 남았다: 고친 뒤 python run.py rebuild --yes")
        return {"rc": rc}
    RP.reset(off=None if replay else "끔")
    rows = ingest_batch.ingest_list(items, preflight=pf)
    ops = oplog.replay()
    from cli.ingest import OK
    done = len(rows) == len(plan["docs"]) and all(x["status"] == OK for x in rows)
    if done:
        _write_plan(plan["docs"], DONE)          # 다음 재구축은 문서 대장에서 (B111 ②)
    return {"rc": 0, "rows": rows, "judge": dict(RP.STATS), "ops": ops, "done": done,
            "calls": _calls(u0, gateway.usage_by()),
            "missing": [d for d in plan["docs"] if not d["exists"]]}


def report(r):
    from cli.ingest import OK
    rows, j, ops, c = r["rows"], r["judge"], r["ops"], r["calls"]
    ok = sum(1 for x in rows if x["status"] == OK)
    print(f"■ 재구축 끝 — 문서 {len(rows) + len(r['missing']):,}(성공 {ok:,} · 실패·보류 {len(rows) - ok:,} · "
          f"원본 없음 {len(r['missing']):,})")
    print(f"  판정 — 재생 {j['재생']:,} · 재판정 {j['재판정']:,}(키 없음 {j['키 없음']:,} · 대상 없음 {j['대상 없음']:,} · "
          f"끔 {j['끔']:,}) · 재생 불확실 {j.get('불확실', 0):,} → 2차 {j.get('2차', 0):,} → 바뀜 {j.get('2차 바뀜', 0):,}")
    print(f"  LLM 호출 — 추출 {c['추출']:,} · 판정 {c['판정']:,} · 태깅 {c['태깅']:,} · 개요 {c['개요']:,} · "
          f"보강 {c['보강']:,} · 그 밖 {c['그 밖']:,}")
    from cli.ops import replay_lines
    for ln in replay_lines(ops):
        print("  " + ln)
    for d in r["missing"]:
        print(f"  원본 없음 — {d['doc_id']} · {d['source_path']} (원본을 그 자리에 두고 다시 재구축)")
    from core.state import alias_book
    ab = alias_book.presence()
    print(f"  별칭 대장 {ab['total']:,} · 그래프에 있음 {ab['present']:,} · 없음 {len(ab['missing']):,}")
    for x in ab["missing"]:
        t = x["target"]
        print(f"    없음 — '{x['surface']}' → {t['canonical']} ({t['category']} · {t['layer']}) · {x['source']}"
              " (대장에는 남는다 — 그 문서 · 이름이 돌아오면 다시 붙는다)")
    print(f"  계획 파일 — {DONE if r['done'] else IN_PROGRESS}"
          + (" (다음 재구축은 문서 대장에서)" if r["done"] else
             " (계획의 문서가 전부 성공하지 않았다 — 고친 뒤 같은 명령이 이 계획에서 이어 간다)"))


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
