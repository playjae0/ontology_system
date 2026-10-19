# -*- coding: utf-8 -*-
"""칸 0.3 — `show report <doc_id> --md` — **잘리지 않는 인입 보고서** (B123 ①).

    <상태>/export/report_<doc_id>.md      (⑤파생 — 지우면 다시 만든다 · 되돌려 읽지 않는다)

터미널 표는 120칸에 맞춰 칸을 줄이고 자른다 — 저장된 보고서는 **칸 전부를 자르지 않고** 싣는다:
요약 · 맞춤표 · 붙은 연결의 카테고리 쌍별 수(출발 카테고리 · 관계 · 도착 카테고리 · 붙은 방식) · 추출 청크 표 · 판정 값 표.
재료는 판정 대장 · 그래프 · 청크 저장소 · 추출 체크포인트 · 파싱 봉투다 — **새 판정 0**(맞춤표는 `reconcile.for_report` ·
값 표의 칸은 화면과 같은 `ingest_screen.value_cells`).
"""
from __future__ import annotations

import json
from collections import Counter

from core import paths

#: 대장의 붙은 자리에 없는 엣지(정형 관계 · 미러 · 자동 엣지)의 방식 칸
OTHER = "그 밖(대장에 없음)"


def path_of(doc_id):
    return paths.export(f"report_{doc_id}.md")


def _cell(x):
    return str("" if x is None else x).replace("|", "\\|").replace("\n", " ").strip()


def _table(heads, rows):
    out = ["| " + " | ".join(_cell(h) or "·" for h in heads) + " |",
           "|" + "|".join("---" for _h in heads) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out


def _mine(x, doc_id):
    pre = f"{doc_id}#"
    return any(str(p) == doc_id or str(p).startswith(pre) for p in x.get("provenance") or [])


def doc_edges(graphs, doc_id):
    """이 문서 몫 엣지 — 출처에 그 문서가 든 살아 있는 엣지(층 전부 · `show summary`의 문서 줄과 같은 셈)."""
    return [e for g in graphs.values() for e in g.edges
            if e.get("status") != "deleted_by_user" and _mine(e, doc_id)]


def pair_counts(graphs, doc_id, rows):
    """붙은 연결의 카테고리 쌍별 수 — `Counter((출발 카테고리, 관계, 도착 카테고리, 방식))`. 방식은 대장 행의 붙은 자리
    (`attached.path` — 소속(출처) · 폴백(제목 n단) · 폴백 · 관계 · 보강 …)에서 · 대장에 없는 엣지는 `OTHER`."""
    def node(nid):
        return next((g.get(nid) for g in graphs.values() if g.get(nid)), None) or {}
    how = {}
    for r in rows:
        for a in r.get("attached") or []:
            if r.get("node_id"):
                how.setdefault((r["node_id"], a.get("rel"), a.get("other")), a.get("path"))
    out = Counter()
    for e in doc_edges(graphs, doc_id):
        s, d = node(e["src"]), node(e["dst"])
        way = (how.get((e["src"], e["rel"], d.get("canonical"))) or how.get((e["dst"], e["rel"], s.get("canonical")))
               or OTHER)
        out[(s.get("category") or "?", e["rel"], d.get("category") or "?", way)] += 1
    return out


def _chunk_rows(doc_id, env):
    """추출 청크 표의 행 — 체크포인트마다(렌즈판 포함) 청크 하나 한 행 · 개체는 전부(표기 · 카테고리)."""
    from core.build import extract_ctx as XC, reconcile as RC
    from core.state import store
    loc_of = {cid: c.get("source_locator") for cid, c in (store.read(store.CHUNKS, {"chunks": {}}).get("chunks")
                                                          or {}).items() if c.get("doc_id") == doc_id}
    by_loc = {c.get("source_locator"): c for c in (env.get("chunks") or [])}
    out = []
    for lens, ck in RC._checkpoints(doc_id):
        for i, c in enumerate(ck.get("candidates") or [], 1):
            loc = loc_of.get(c.get("chunk_id")) or c.get("chunk_id")
            piece = by_loc.get(loc) or {}
            sheet, end = XC.place(piece) if piece else ("", loc)
            ents = c.get("entities") or []
            state = ("실패 — " + str(c["failed"])) if c.get("failed") else (
                "거름" if c.get("lens_skipped") else (f"개체 {len(ents)}" if ents else "개체 0"))
            out.append([i, lens or "", sheet, end, XC.chunk_label(piece) if piece else loc,
                        " · ".join(f"{e.get('surface')}({e.get('category')})" + (f" = {e['value']}" if e.get("value") else "")
                                   for e in ents),
                        len(c.get("relations") or []), state])
    return out


def _value_rows(rows, env):
    """판정 값 표의 행 — 대장 개체 행 하나 한 행 · 칸은 화면과 같은 함수(붙은 자리는 전부 · 2차 · 값을 더한다)."""
    from cli import ingest_screen as SCR
    from core.build import extract_ctx as XC
    pieces = [c for c in (env.get("chunks") or []) + (env.get("records") or []) if c.get("source_locator")]
    places = {c["source_locator"]: XC.place(c) for c in pieces}
    prose = bool(env.get("chunks"))
    roles = SCR.struct_roles(env) if prose else {}
    out = []
    for i, r in enumerate([x for x in rows if x.get("role") == "entity"], 1):
        cells, _kinds = SCR.value_cells(r, places, roles, prose=True, wide=True)
        cells[0] = i
        cells[SCR.VALUE_HEADS.index("붙은 자리")] = " ; ".join(
            f"{a.get('rel')} {a.get('dir')} {a.get('other')}({a.get('path')})" for a in r.get("attached") or [])
        j2, val = r.get("judge2") or {}, r.get("value") or {}
        out.append(cells + [f"{j2['was']} → {j2['now']}" if j2 else "",
                            f"{val.get('attr')} {val.get('value')} ({val.get('verdict')})" if val else ""])
    return out


def build(doc_id, data):
    """보고서 글 — 대장 `data`(`ledger.read`)와 지금 그래프 · 청크 저장소 · 봉투에서."""
    from cli import ingest_screen as SCR, result_screen as RS
    from core.build import reconcile as RC
    from core.state.bootstrap import open_graph
    from router import discover
    p = paths.parsed(f"{doc_id}.json")
    env = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    rows = data.get("rows") or []
    graphs = {lay: open_graph(lay) for lay in discover()}
    mt = RC.for_report(doc_id, data)
    pairs = pair_counts(graphs, doc_id, rows)
    out = [f"# 인입 보고 — {doc_id}", "",
           f"> 재료: 판정 대장 · 그래프 · 청크 저장소 · 추출 체크포인트(새 판정 0) · 다시 만들기 "
           f"`python run.py show report {doc_id} --md`", "", "## 요약 · 맞춤", ""]
    out += [f"- {ln.strip()}" for ln in RS.reconcile_lines(mt)]
    out += ["", "## 붙은 연결 — 카테고리 쌍별", "",
            f"이 문서 몫 엣지 {len(doc_edges(graphs, doc_id)):,} = 아래 수의 합 {sum(pairs.values()):,}", ""]
    out += _table(("출발 카테고리", "관계", "도착 카테고리", "붙은 방식", "수"),
                  [[a, b, c, d, n] for (a, b, c, d), n in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))])
    ch = _chunk_rows(doc_id, env)
    out += ["", "## 추출 청크", ""]
    out += (_table(("#", "렌즈", "시트", "청크", "라벨", "개체", "관계", "상태"), ch) if ch
            else ["추출 체크포인트 없음(표 문서 · 또는 아직 뽑지 않았다)"])
    out += ["", "## 판정 값", ""]
    out += _table(("#",) + SCR.VALUE_HEADS[1:] + ("2차", "값"), _value_rows(rows, env))
    return "\n".join(out) + "\n"


def write(doc_id, data):
    """`export/report_<doc_id>.md`에 쓴다(원자 쓰기) — 돌려주는 것은 그 자리."""
    from core.state.store import atomic_write_bytes
    p = paths.ensure(path_of(doc_id))
    atomic_write_bytes(p, build(doc_id, data).encode("utf-8"))
    return p
