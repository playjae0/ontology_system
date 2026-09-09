# -*- coding: utf-8 -*-
"""골든셋 — 문항 틀과 채점기 (문서 5 §5.5-2·3·4 · B54).

**골든셋은 파이프라인이 아니다**(§5.5 경계) — 없어도 인입·질의는 돈다. 여기 코드가
질의 경로에 불려 들어가면 그 경계가 무너진다.

두 명령뿐이다:

    golden init    §5.5-2 기준 구성대로 **빈 문항 틀**을 만든다 (사내 제작의 출발점)
    golden score   문항마다 `answer()` 1회 — 4축을 재고 BM-25를 나란히 낸다

**채점은 `answer()`까지만 부른다** — 답변 생성(⑧)은 부르지 않는다(§5.5-4). 재는 것은
**근거 선택**이지 문장이 아니다. 그래서 채점에 LLM 비용이 들지 않고, mock에서도
메커니즘이 도는지가 판정된다.

**채점기가 문항보다 먼저 선다.** 채점기 없이 만든 120문항은 형식이 갈리고, 갈린 뒤에
맞추려면 문항을 다시 쓴다.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from core import bm25, store

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "golden" / "queries.json"
LOG = "golden_log.json"
DEFAULT_K = 8                       # 수집 상한과 같다 (문서 5 §5.1 규약 6)

# **유형은 닫힌 값이다**(§5.5-4). 유형 → `expected_path` 파생은 §5.3 유형표의
# 「답의 소재」 열이 정한다 — 여기서 새로 판단하지 않고 그 대응을 옮긴다.
TYPE_PATH = {
    "Q1": "chunk",                  # 청크
    "Q2": "graph_fact", "Q3": "graph_fact",
    "Q4": "graph_fact", "Q5": "graph_fact",     # 엣지·노드 필드
    "Q6": "graph_fact", "Q7": "graph_fact",     # 범위 밖이나 값은 정의돼 있다
    "Q8": "general_knowledge",      # 그래프 밖
    "noanswer": "general_knowledge",            # 환각 검증 — 「근거 없음」 선언
    "multihop": "both",             # 프론티어 전파·cross 브리지
    "out": "general_knowledge",     # 범위 밖 확인 — 링킹 미스율 재료
}
TYPES = tuple(TYPE_PATH)
PATHS = ("chunk", "graph_fact", "both", "general_knowledge")

# §5.5-2 기준 구성 — 지원 유형 각 15 + 무답 10 + 멀티홉 10 + 범위 밖 10 = 120.
PLAN = (("Q1", 15), ("Q2", 15), ("Q3", 15), ("Q4", 15), ("Q5", 15), ("Q8", 15),
        ("noanswer", 10), ("multihop", 10), ("out", 10))


# ───────────────────────────────────────────────────────────── ① 틀
def blank_set():
    qs = []
    for t, n in PLAN:
        for i in range(1, n + 1):
            qs.append({"id": f"{t}-{i:02d}", "type": t, "q": "",
                       "expected_path": TYPE_PATH[t],
                       "expected_linked": [], "expected_docs": []})
    return {"version": 1,
            "_읽는 법": "q를 채우고 expected_*를 아는 만큼 적는다. "
                       "expected_linked/docs가 비면 그 축은 그 문항에서 채점하지 않는다",
            "queries": qs}


def cmd_init(args):
    """**있으면 덮지 않는다** — 사내가 채워 넣은 문항을 지우는 명령이 아니다."""
    path = Path(args[0]) if args else GOLDEN
    if path.exists():
        got = json.loads(path.read_text(encoding="utf-8")).get("queries") or []
        c = Counter(q.get("type") for q in got)
        filled = sum(1 for q in got if (q.get("q") or "").strip())
        print(f"■ 골든셋이 이미 있다 — {_rel(path)} (덮지 않는다)")
        print(f"  {len(got)}건 · q가 채워진 것 {filled}건 "
              f"({len(got) - filled}건 남음)")
        _dist(c, len(got))
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    data = blank_set()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    qs = data["queries"]
    print(f"■ 골든셋 틀 — {_rel(path)}  ({len(qs)}건 · 기준 구성 §5.5-2)")
    _dist(Counter(q["type"] for q in qs), len(qs))
    print("\n  다음 — 사내에서 채운다:")
    print("    ① q를 쓴다 (유형 정의는 문서 5 §5.3 질문 유형표)")
    print("    ② 아는 만큼 expected_linked(「층:canonical」)·expected_docs(doc_id)를 적는다")
    print("       — 비워 두면 그 축은 그 문항에서 채점하지 않는다(빈 값은 0점이 아니다)")
    print("    ③ python run.py golden score")
    return 0


def _dist(c, total):
    print(f"  유형 분포 — " + " · ".join(f"{t} {c.get(t, 0)}" for t, _ in PLAN))
    print(f"  기대 경로 — " + " · ".join(
        f"{p} {sum(c.get(t, 0) for t in TYPES if TYPE_PATH[t] == p)}" for p in PATHS))


def _rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# ───────────────────────────────────────────────────────────── 형식 검사
def load(path):
    """문항을 읽는다. **닫힌 값 밖·필수 키 누락은 문항 단위로 건너뛴다.**

    파일 전체를 거부하지 않는 것은 사내가 채워 가는 **중간 상태를 허용**하기
    위해서다 — 120건 중 3건이 덜 됐다고 채점이 통째로 안 돌면, 다 채울 때까지
    아무도 점수를 못 본다. 건너뛴 사유는 화면에 그대로 찍는다(조용히 빠뜨리지 않는다).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ok, skipped = [], []
    for i, q in enumerate(data.get("queries") or []):
        qid = q.get("id") or f"[{i}]"
        if not (q.get("q") or "").strip():
            skipped.append((qid, "q가 비었다 — 아직 안 쓴 문항"))
            continue
        if q.get("type") not in TYPE_PATH:
            skipped.append((qid, f"type이 닫힌 값 밖 — {q.get('type')!r}"))
            continue
        if q.get("expected_path") not in PATHS:
            skipped.append((qid, f"expected_path가 닫힌 4값 밖 — {q.get('expected_path')!r}"))
            continue
        ok.append(q)
    return ok, skipped


# ───────────────────────────────────────────────────────────── ② 채점
def score_set(queries, k=DEFAULT_K):
    """문항마다 `answer()` 1회 — 4축. **⑧은 부르지 않는다**(§5.5-4).

    측정 중 `link_miss`·`chunk_truncated` 적재를 끈다(§5.5 규율 4) — `cmd_gauges`와
    **같은 스위치**다: 측정이 재료 로그를 오염시키면 다음 측정이 제 흔적을 센다.
    """
    from cli.query import answer

    rows = []
    idx = bm25.build()                  # 인덱스는 한 번 만들어 전 문항이 쓴다
    with store.muted_material_logs():
        for q in queries:
            res = answer(q["q"])
            rows.append(_grade(q, res, idx, k))
    return rows


def _grade(q, res, idx, k):
    want_linked = q.get("expected_linked") or []
    want_docs = q.get("expected_docs") or []
    got_docs = [c["doc_id"] for c in (res.get("chunks") or [])[:k]]
    bm_docs = bm25.docs_of(bm25.search(q["q"], k, index=idx))

    r = {"id": q.get("id"), "type": q["type"], "q": q["q"],
         "path": {"want": q["expected_path"], "got": res["path"],
                  "ok": q["expected_path"] == res["path"]},
         "linking": None, "evidence": None, "bm25": None}
    if want_linked:
        got = res.get("linked") or []
        hit = [x for x in want_linked if x in got]
        r["linking"] = {"want": want_linked, "got": got,
                        "hit": len(hit), "n": len(want_linked),
                        "ok": len(hit) == len(want_linked)}
    if want_docs:
        # **적중 = 기대 문서 중 하나라도 상위 k 안에** (§5.5-4 ③).
        r["evidence"] = {"want": want_docs, "got": got_docs,
                         "ok": any(d in got_docs for d in want_docs)}
        r["bm25"] = {"want": want_docs, "got": bm_docs,
                     "ok": any(d in bm_docs for d in want_docs)}
    return r


def aggregate(rows, k=DEFAULT_K):
    def rate(sel, axis):
        xs = [r[axis] for r in sel if r[axis] is not None]
        return (round(sum(1 for x in xs if x["ok"]) / len(xs), 3), len(xs)) if xs \
            else (None, 0)

    def recall(sel):
        xs = [r["linking"] for r in sel if r["linking"] is not None]
        n = sum(x["n"] for x in xs)
        return (round(sum(x["hit"] for x in xs) / n, 3), n) if n else (None, 0)

    out = {"n": len(rows), "k": k, "by_type": {}}
    for t in TYPES:
        sel = [r for r in rows if r["type"] == t]
        if sel:
            out["by_type"][t] = _row(sel, rate, recall)
    out.update(_row(rows, rate, recall))
    return out


def _row(sel, rate, recall):
    p, pn = rate(sel, "path")
    lr, ln = recall(sel)
    e, en = rate(sel, "evidence")
    b, bn = rate(sel, "bm25")
    return {"n": len(sel), "path_rate": p, "path_n": pn,
            "linking_recall": lr, "linking_n": ln,
            "evidence_at_k": e, "evidence_n": en, "bm25_at_k": b, "bm25_n": bn}


def _fmt(v, n):
    return "  —  " if v is None else f"{v:>5.3f}"


def render(agg, rows, *, src, is_mock, skipped, k):
    L = [f"■ 골든셋 채점 — {src} · {agg['n']}문항 · k={k}"]
    if is_mock:
        # `cmd_accuracy`와 **같은 문면**이다 — 두 화면이 다른 말을 하지 않게.
        L.append("  ※ **mock 세트다 — 품질 점수가 아니라 메커니즘 점검이다**"
                 "(가짜 데이터의 점수는 가짜 확신이다 · §7.5-1)")
    L.append("  ※ 채점은 answer()까지다 — 답변 생성(⑧)은 부르지 않는다(§5.5-4)")
    if skipped:
        L.append(f"\n  건너뛴 문항 {len(skipped)}건 (파일 전체를 거부하지 않는다):")
        for qid, why in skipped[:8]:
            L.append(f"    · {qid:<12} {why}")
        if len(skipped) > 8:
            L.append(f"    · … 외 {len(skipped) - 8}건")

    L.append("")
    L.append(f"  {'유형':<10}{'수':>4}  {'path':>7}{'linking':>9}"
             f"{'evid@k':>8}{'bm25@k':>8}   ← 대조군")
    L.append("  " + "─" * 52)
    for t, a in agg["by_type"].items():
        L.append(f"  {t:<10}{a['n']:>4}  {_fmt(a['path_rate'], 0):>7}"
                 f"{_fmt(a['linking_recall'], 0):>9}"
                 f"{_fmt(a['evidence_at_k'], 0):>8}{_fmt(a['bm25_at_k'], 0):>8}")
    L.append("  " + "─" * 52)
    L.append(f"  {'전체':<10}{agg['n']:>4}  {_fmt(agg['path_rate'], 0):>7}"
             f"{_fmt(agg['linking_recall'], 0):>9}"
             f"{_fmt(agg['evidence_at_k'], 0):>8}{_fmt(agg['bm25_at_k'], 0):>8}")
    L.append(f"    채점된 문항 — path {agg['path_n']} · linking {agg['linking_n']}(기대 링킹 수)"
             f" · evidence {agg['evidence_n']} · bm25 {agg['bm25_n']}")
    if agg["evidence_n"]:
        d = (agg["evidence_at_k"] or 0) - (agg["bm25_at_k"] or 0)
        L.append(f"    **대조군 대비 {d:+.3f}** — 이 값이 「무엇 대비」의 답이다(§5.5-3)")

    bad = [r for r in rows if not r["path"]["ok"]
           or (r["linking"] and not r["linking"]["ok"])
           or (r["evidence"] and not r["evidence"]["ok"])]
    if bad:
        L.append(f"\n  틀린 문항 {len(bad)}건:")
        for r in bad:
            L.append(f"    ✗ {r['id'] or r['q'][:12]:<12} {r['q'][:34]}")
            if not r["path"]["ok"]:
                L.append(f"        path     기대 {r['path']['want']} · 실제 {r['path']['got']}")
            if r["linking"] and not r["linking"]["ok"]:
                miss = [x for x in r["linking"]["want"] if x not in r["linking"]["got"]]
                L.append(f"        linking  못 건 것 {miss} · 실제 {r['linking']['got']}")
            if r["evidence"] and not r["evidence"]["ok"]:
                L.append(f"        evidence 기대 {r['evidence']['want']} · "
                         f"상위{agg['k']} {r['evidence']['got']}")
    return "\n".join(L)


def cmd_score(args):
    args = list(args)
    as_json = "--json" in args
    while "--json" in args:
        args.remove("--json")
    k = DEFAULT_K
    if "--k" in args:
        i = args.index("--k")
        try:
            k = int(args[i + 1])
        except (IndexError, ValueError):
            raise SystemExit("[golden] --k 뒤에 숫자가 필요하다")
        del args[i:i + 2]
    path = None
    if "--set" in args:
        i = args.index("--set")
        try:
            path = args[i + 1]
        except IndexError:
            raise SystemExit("[golden] --set 뒤에 파일 경로가 필요하다")
        del args[i:i + 2]

    from tests import fixtures                                    # noqa: F401
    is_mock = False
    if path is None:
        if GOLDEN.exists():
            path = GOLDEN
        else:
            path, is_mock = ROOT / "tests" / "fixtures" / "queries.json", True
    else:
        is_mock = "fixtures" in str(path)
    if not Path(path).exists():
        raise SystemExit(f"[golden] 세트가 없다 — {path}. `run.py golden init`이 틀을 만든다")

    queries, skipped = load(path)
    if not queries:
        raise SystemExit(f"[golden] 채점할 문항이 0건이다 — {_rel(path)} "
                         f"(건너뜀 {len(skipped)}건: q가 비었거나 형식 밖)")
    rows = score_set(queries, k)
    agg = aggregate(rows, k)

    entry = {"at": store._now(), "set": _rel(path), "n": agg["n"], "k": k,
             "path_rate": agg["path_rate"], "linking_recall": agg["linking_recall"],
             "evidence_at_k": agg["evidence_at_k"], "bm25_at_k": agg["bm25_at_k"],
             "mock": is_mock,
             "by_type": {t: {kk: a[kk] for kk in
                             ("n", "path_rate", "linking_recall",
                              "evidence_at_k", "bm25_at_k")}
                         for t, a in agg["by_type"].items()}}
    # **로그이지 큐가 아니다**(§5.5 규율 5) — 아무도 처리하지 않는다, 추이만 본다.
    hist = store.read(LOG, [])
    hist.append(entry)
    store.write(LOG, hist[-50:])

    if as_json:
        print(json.dumps({"summary": entry, "rows": rows,
                          "skipped": [{"id": a, "why": b} for a, b in skipped]},
                         ensure_ascii=False))
    else:
        print(render(agg, rows, src=_rel(path), is_mock=is_mock,
                     skipped=skipped, k=k))
        print(f"\n  → data/{LOG} (최근 50)")
    return 0


def main(argv):
    if not argv or argv[0] not in ("init", "score"):
        raise SystemExit('사용: run.py golden init | golden score '
                         '[--set <파일>] [--k 8] [--json]')
    return (cmd_init if argv[0] == "init" else cmd_score)(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
