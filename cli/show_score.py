# -*- coding: utf-8 -*-
"""칸 0.3 — **점수표** — 사람이 만든 작은 정답표로 「좋아졌나 나빠졌나」를 수로 (B118 ② · 사내 2026-10-16 「공정마다 결과가
들쑥날쑥한데 좋아졌는지 나빠졌는지를 느낌으로만 판단한다」).

    python run.py show score <doc_id> --template   그 문서 대장의 개체 행마다 한 줄 — 위치 · 표기 · 지금 붙은 자리 · 빈 정답 칸
                                                    → `golden/score/<doc_id>.csv`(엑셀로 연다 · 있으면 덮지 않는다)
    python run.py show score <doc_id>              맞음 · 틀림 · 빈칸 · 정답률 · 틀린 목록(위치 · 표기 · 지금 · 정답)
    python run.py show score --all                 정답표가 있는 문서 전부

**사람은 정답 칸만 채운다** — 지금 자리가 맞으면 `=` 한 글자(엑셀에서는 `'=` · `o` · `ㅇ` · `맞음`도 같다 — `=`만 치면 수식으로
읽는다) · 틀리면 맞는 이름 · 비우면 채점 밖. 정답표는 판정을 바꾸지 않는다(화면만) ·
재구축 뒤에도 같은 표로 잰다(행은 위치 · 표기로 맞춘다 — 위치키가 바뀌었으면 위치 칸 · 시트 순). 자리는 `golden/`(사람이 쓴 것 ·
fresh가 남긴다 · 이관 대상). CSV는 UTF-8(BOM — 엑셀이 한글을 읽는다)로 쓰고, 엑셀이 저장한 CP949도 읽는다.
"""
from __future__ import annotations

import csv
import io
import json

from core import paths

COLS = ("번호", "위치", "표기", "지금", "정답", "위치키")
#: 「지금 자리가 맞다」 — `=` 한 글자(엑셀은 `=`를 수식 시작으로 읽으므로 `'=` · `o` · `ㅇ` · `맞음`도 같다)
SAME = ("=", "'=", "o", "ㅇ", "맞음")


def table_path(doc_id):
    return paths.golden("score", f"{doc_id}.csv")


def now_of(r):
    """개체 행의 **지금 붙은 자리** — 소속 → 연결 보강 → 제목 폴백 → 좌표 폴백 → 관계 · 보류 · 관련 링크 · 빈칸 · 엣지 없음."""
    from core.build.result import hold_reason
    why = hold_reason(r)
    if why:
        return f"보류({why})"
    if r.get("verdict") == "mention":
        return f"관련 링크 {r.get('canonical') or ''}".strip()
    if r.get("verdict") == "blank":
        return "빈칸"
    att = r.get("attached") or []
    for test in (lambda p: p.startswith("소속"), lambda p: p == "보강", lambda p: p.startswith("폴백("),
                 lambda p: p == "폴백", lambda p: p == "관계"):
        a = next((x for x in att if test(str(x.get("path") or ""))), None)
        if a:
            return str(a.get("other") or "")
    return "(엣지 없음)" if r.get("node_id") else "(노드 없음)"


def _places(doc_id):
    """봉투의 조각 위치 → `(시트, 청크 끝)` · 라벨(위치 칸)."""
    from core.build import extract_ctx
    p = paths.parsed(f"{doc_id}.json")
    try:
        env = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        env = {}
    out = {}
    for c in (env.get("chunks") or []) + (env.get("records") or []):
        if c.get("source_locator"):
            out[c["source_locator"]] = extract_ctx.place(c)
    return out


def _where(loc, places):
    from cli.ingest_screen import where_cells
    s, e = where_cells(loc, places)
    return f"{s} › {e}" if s else e


def entity_rows(doc_id):
    from core.build import ledger
    return [r for r in (ledger.read(doc_id) or {}).get("rows") or [] if r.get("role") == "entity"]


def template(doc_id):
    """정답표 초안 — 개체 행마다 한 줄(빈 정답 칸). 돌려주는 것은 `(자리, 행 수)` · 이미 있으면 `(자리, None)`(덮지 않는다)."""
    p = table_path(doc_id)
    if p.exists():
        return p, None
    places = _places(doc_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLS)
    rows = entity_rows(doc_id)
    for i, r in enumerate(rows, 1):
        w.writerow([i, _where(r.get("locator"), places), r.get("surface") or "", now_of(r), "", r.get("locator") or ""])
    from core.state.store import atomic_write_bytes
    paths.ensure(p)
    atomic_write_bytes(p, buf.getvalue().encode("utf-8-sig"))
    return p, len(rows)


def read_table(p):
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit(f"[score] 정답표를 읽지 못했다 — {paths.show(p)} (UTF-8 · CP949가 아니다)\n"   # [상태]
                         f"  ▶ 다음 줄 — 엑셀에서 CSV로 다시 저장하거나, 지우고 초안부터: "
                         f"python run.py show score {p.stem} --template")
    return list(csv.DictReader(io.StringIO(text)))


def score(doc_id):
    """정답표로 잰다 — `{맞음, 틀림, 빈칸, 정답률, 틀린: [(위치, 표기, 지금, 정답)]}` · 정답표가 없으면 None."""
    from core.state.ids import norm
    p = table_path(doc_id)
    if not p.exists():
        return None
    places = _places(doc_id)
    cur = entity_rows(doc_id)
    by_key, by_where, by_sheet = {}, {}, {}
    for r in cur:
        s = norm(r.get("surface") or "")
        by_key.setdefault((r.get("locator"), s), []).append(r)
        by_where.setdefault((_where(r.get("locator"), places), s), []).append(r)
        by_sheet.setdefault((_where(r.get("locator"), places).split(" › ")[0], s), []).append(r)
    used = set()
    out = {"맞음": 0, "틀림": 0, "빈칸": 0, "틀린": []}
    for t in read_table(p):
        ans = (t.get("정답") or "").strip()
        if not ans:
            out["빈칸"] += 1
            continue
        truth = (t.get("지금") or "").strip() if ans.lower() in SAME else ans
        s = norm(t.get("표기") or "")
        got = None
        for pool in (by_key.get((t.get("위치키"), s)), by_where.get(((t.get("위치") or "").strip(), s)),
                     by_sheet.get(((t.get("위치") or "").split(" › ")[0].strip(), s))):
            got = next((r for r in pool or [] if id(r) not in used), None)
            if got is not None:
                break
        now = now_of(got) if got is not None else "(행 없음)"
        if got is not None:
            used.add(id(got))
        if norm(truth) == norm(now):
            out["맞음"] += 1
        else:
            out["틀림"] += 1
            out["틀린"].append((t.get("위치") or "", t.get("표기") or "", now, truth))
    n = out["맞음"] + out["틀림"]
    out["정답률"] = round(100.0 * out["맞음"] / n, 1) if n else None
    return out


def _print(doc_id, sc, limit=40):
    if sc is None:
        print(f"  {doc_id} — 정답표 없음 ▶ python run.py show score {doc_id} --template")
        return
    rate = f"{sc['정답률']}%" if sc["정답률"] is not None else "—(채점한 행 0)"
    print(f"  {doc_id} — 맞음 {sc['맞음']:,} · 틀림 {sc['틀림']:,} · 빈칸 {sc['빈칸']:,} · 정답률 {rate}")
    for w, s, now, truth in sc["틀린"][:limit]:
        print(f"     ✗ {w} · '{s}' — 지금 {now} · 정답 {truth}")
    if len(sc["틀린"]) > limit:
        print(f"     … 외 {len(sc['틀린']) - limit:,}")


def main(args):
    if "--all" in args:
        docs = sorted(p.stem for p in paths.golden("score").glob("*.csv")) if paths.golden("score").exists() else []
        print(f"■ 점수표 — 정답표가 있는 문서 {len(docs):,}")
        for d in docs:
            _print(d, score(d))
        return 0
    docs = [a for a in args if not a.startswith("--")]
    if not docs:
        raise SystemExit("[사용법] python run.py show score <doc_id> [--template] | --all")     # [사용법]
    doc_id = docs[0]
    if "--template" in args:
        p, n = template(doc_id)
        if n is None:
            print(f"■ 정답표 — 이미 있다(덮지 않는다 · 사람이 채운 칸이다) — {paths.show(p)}")
            return 1
        print(f"■ 정답표 초안 — {n:,}행(대장의 개체 행) → {paths.show(p)}")
        print("  엑셀로 열어 「정답」 칸만 채운다 — 지금 자리가 맞으면 o(또는 ㅇ · '=) · 틀리면 맞는 이름 · 비우면 채점 밖 → "
              f"python run.py show score {doc_id}")
        return 0
    print(f"■ 점수표 — {doc_id} (정답표 {paths.show(table_path(doc_id))})")
    _print(doc_id, score(doc_id))
    return 0
