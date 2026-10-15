# -*- coding: utf-8 -*-
"""칸 3.x — **문서 끝 맞춤표** — 줄마다 단위 · 같은 단위는 합 = 전체 (B112 ①④⑤).

사내(2026-10-15): 결과 줄 `값 377 → 사전 연결 22 · LLM 연결 1 · 새 노드 102 · 불확실 27 · 보류 320`의 합이 472라
현황을 셀 수 없었다 — `값`은 개체 행 · `보류`는 모든 행의 사유 · `LLM 연결`은 이번 실행에 LLM을 부른 일치뿐이었다.
여기서는 **한 줄이 한 단위**다(청크 · 조각 · 개체 행 · 행 · 노드 · 큐 항목) — 그 단위의 것 하나가 칸 하나에 들고
(닫힌 표 · 표에 없는 조합은 `그 밖(경로:판정)`으로 보이게), 칸의 합을 전체와 대조한다(어긋나면 화면이 `[결함]`).

**화면은 장부의 투영이다 — 새 판정 0 · 새로 저장하는 것 0**: 재료는 판정 대장 행 · 봉투 · 추출 체크포인트 ·
그래프 · 큐다. 인입 끝(실행 사실 `run` — 부름/재사용 · 층 전 수 · 이번/이전 큐)과 `show report`(장부만)가
**같은 함수**를 지난다 — 표 · 산문 · 렌즈 · 층 전부.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePath

from core.build.result import hold_reason

#: 판정 경로(`core.matcher.PATHS`) 중 **판정을 부른 길** — 후보를 좁혀 판정(LLM · mock)에 맡긴 것
JUDGE_PATHS = ("scope+judge", "embedding+judge", "overlap+judge")
#: 판정 → 결말 칸(닫힌 표 · 밖이면 `그 밖`)
OUTCOME = {"match": "일치", "new": "새", "uncertain": "불확실", "lowres": "불확실"}
#: 판정 → 결말 줄의 칸(개체 행 하나 → 칸 하나 — 보류가 먼저)
END = {"match": "일치", "new": "새 노드", "uncertain": "불확실", "lowres": "불확실"}
#: 행 역할 → 보류 줄의 행 종류
ROW_KIND = {"anchor": "좌표 행", "entity": "개체 행", "belongs": "소속 행",
            "attribute": "속성·내용 행", "content": "속성·내용 행"}


def _sub(cnt):
    return " · ".join(f"{k} {n:,}" for k, n in cnt.items() if n)


def line(label, total, cells, note=""):
    """`{"줄", "전체", "칸": [(이름, 수, 세부)], "합", "맞음"}` — 칸은 0이 아닌 것만 화면에."""
    s = sum(n for _k, n, _d in cells)
    return {"줄": label, "전체": total, "칸": cells, "합": s, "맞음": s == total, "덧": note}


# ---------------------------------------------------------------- 청크(산문)
def chunk_line(ck, run=None, lens=None):
    """`청크(산문) N = 부름 + ref + 거름 + 재사용` · `부름(+재사용) = 개체 있음 + 개체 0 + 실패` — 체크포인트에서
    (부름 · 재사용은 그 실행의 사실 `run` — 없으면 「뽑음」 하나)."""
    cands = (ck or {}).get("candidates") or []
    ref = int((ck or {}).get("ref_skipped") or 0)
    lens_sk = sum(1 for c in cands if c.get("lens_skipped"))
    got = [c for c in cands if not c.get("lens_skipped")]
    has = sum(1 for c in got if not c.get("failed") and c.get("entities"))
    zero = sum(1 for c in got if not c.get("failed") and not c.get("entities"))
    fail = sum(1 for c in got if c.get("failed"))
    n = len(cands) + ref
    if run:
        called, reused = int(run.get("부름", 0)), int(run.get("재사용", 0))
        head = [("부름", called, ""), ("ref", ref, ""), ("거름", lens_sk, ""), ("재사용", reused, "")]
        who = "부름" + (" + 재사용" if reused else "")
    else:
        head = [("뽑음", len(got), ""), ("ref", ref, ""), ("거름", lens_sk, "")]
        who = "뽑음"
    lab = "청크(산문" + (f" · 렌즈 {lens}" if lens else "") + ")"
    return [line(lab, n, head),
            line(f"  {who}", len(got), [("개체 있음", has, ""), ("개체 0", zero, ""), ("실패", fail, "")])]


# ---------------------------------------------------------------- 조각 좌표
def coord_cells(env):
    """조각 좌표의 출처 — `(조각 수, Counter(자기 · 문서 좌표 · 학습 · LLM 태깅 · 없음), 합 밖 Counter)`.
    봉투의 `meta` 표시에서(태깅이 남긴 것 · 새 계산 0) — 표 · 산문 같은 함수."""
    pcs = (env or {}).get("records") or (env or {}).get("chunks") or []
    cell, side = Counter(), Counter()
    for p in pcs:
        m = p.get("meta") or {}
        if not p.get("process_ref"):
            cell["없음"] += 1
        elif m.get("coord_from_doc"):
            cell["문서 좌표"] += 1
        elif m.get("coord_tag_source") == "learned":
            cell["학습"] += 1
        elif m.get("coord_tag_source") == "live":
            cell["LLM 태깅"] += 1
        else:
            cell["자기"] += 1                       # 범위 안 해소(scope)도 자기 표기에서 온 좌표다
        if m.get("coord_ignored"):
            side["무시(문서 좌표 밖)"] += 1
        if m.get("coord_shared_skip"):
            side["공유 별칭 건너뜀"] += 1
    return len(pcs), cell, side


def coord_line(env):
    n, cell, side = coord_cells(env)
    order = ("자기", "문서 좌표", "학습", "LLM 태깅", "없음")
    return line("조각 좌표", n, [(k, cell.get(k, 0), "") for k in order],
                note=(_sub(side) + " — 합 밖") if side else "")


# ---------------------------------------------------------------- 값(개체 행)
def value_cell(r):
    """개체 행 하나 → `(칸, 세부)` — **닫힌 표**(요청문 ①의 칸 순서): 사전 · 골격 · 재생(결말) · 기억(결말) ·
    LLM 일치 · 새 노드(LLM 판정 · 후보 없음) · 불확실 · 보류(사유) · 그 밖(경로:판정).
    보류가 먼저다(어느 경로로 왔든 노드가 서지 않았다). `LLM`은 판정 길(`JUDGE_PATHS` — mock에서는 mock 판정)."""
    why = hold_reason(r)
    if why:
        return "보류", why
    path, verdict = r.get("path") or "none", r.get("verdict")
    out = OUTCOME.get(verdict)
    if path == "dictionary":
        return "사전", out or verdict
    if path in ("skeleton", "self_coord"):
        return "골격", out or verdict
    if path == "replay" and out:
        return "재생", out
    if path == "memo" and out:
        return "기억", out
    if path in JUDGE_PATHS and out:
        return {"일치": ("LLM 일치", ""), "새": ("새 노드", "LLM 판정")}.get(out, ("불확실", ""))
    if path == "none" and verdict == "new":
        return "새 노드", "후보 없음"
    return "그 밖", f"{path}:{verdict}"


VALUE_ORDER = ("사전", "골격", "재생", "기억", "LLM 일치", "새 노드", "불확실", "보류", "그 밖")


def value_lines(rows):
    ent = [r for r in rows if r.get("role") == "entity"]
    cells, subs = Counter(), {}
    for r in ent:
        k, d = value_cell(r)
        cells[k] += 1
        if d:
            subs.setdefault(k, Counter())[d] += 1
    det = {k: _sub(c) for k, c in subs.items() if k not in ("사전", "골격")}
    ends = Counter("보류" if hold_reason(r) else END.get(r.get("verdict"), "그 밖") for r in ent)
    return [line("값(개체 행)", len(ent), [(k, cells.get(k, 0), det.get(k, "")) for k in VALUE_ORDER]),
            line("결말(개체 행)", len(ent),
                 [(k, ends.get(k, 0), "") for k in ("일치", "새 노드", "불확실", "보류", "그 밖")])]


# ---------------------------------------------------------------- 보류(행 종류별)
def hold_line(rows):
    held = [r for r in rows if hold_reason(r)]
    by = {}
    for r in held:
        by.setdefault(ROW_KIND.get(r.get("role"), "그 밖 행"), Counter())[hold_reason(r)] += 1
    order = ("좌표 행", "개체 행", "소속 행", "속성·내용 행", "그 밖 행")
    return line("보류(행)", len(held), [(k, sum((by.get(k) or {}).values()), _sub(by.get(k) or Counter()))
                                       for k in order])


# ---------------------------------------------------------------- 부착 · 소속 대상
def _is_belongs(a):
    return str(a.get("path") or "").startswith("소속")


def attach_line(rows, skeleton):
    """`부착(개체 행) N = 소속 엣지(공정 · 유닛·부품) + 관계만 + 좌표 폴백 + 엣지 없음 + 노드 없음` —
    대상 종류는 상대 이름이 골격 이름인가로 가른다(`skeleton` — 좌표 층 골격 canonical)."""
    ent = [r for r in rows if r.get("role") == "entity"]
    c, kind = Counter(), Counter()
    for r in ent:
        att = r.get("attached") or []
        bel = [a for a in att if _is_belongs(a)]
        if bel:
            c["소속 엣지"] += 1
            kind["공정" if bel[0].get("other") in skeleton else "유닛·부품"] += 1
        elif any(a.get("path") == "관계" for a in att):
            c["관계만"] += 1
        elif any(a.get("path") == "폴백" for a in att):
            c["좌표 폴백"] += 1
        elif r.get("node_id"):
            c["엣지 없음"] += 1
        else:
            c["노드 없음"] += 1
    order = ("소속 엣지", "관계만", "좌표 폴백", "엣지 없음", "노드 없음")
    return line("부착(개체 행)", len(ent), [(k, c.get(k, 0), _sub(kind) if k == "소속 엣지" else "")
                                          for k in order])


def declared_belongs(cks, chunk_loc):
    """체크포인트에서 소속을 낸 개체 — `Counter((위치, 표기))` · 이름 `{(위치, 표기): 소속 이름}`.
    `chunk_loc`은 청크 id → 위치(봉투의 `source_locator` — 대장 행의 위치와 같은 열쇠)."""
    from core.state.ids import norm
    cnt, name = Counter(), {}
    for ck in cks or []:
        for c in ck.get("candidates") or []:
            loc = chunk_loc.get(c.get("chunk_id"), c.get("chunk_id"))
            for e in c.get("entities") or []:
                b = e.get("belongs_to")
                if isinstance(b, dict) and b.get("name"):
                    k = (loc, norm(e.get("surface") or ""))
                    cnt[k] += 1
                    name[k] = b["name"]
    return cnt, name


def belongs_line(rows, cks, chunk_loc, skeleton, orphans):
    """`소속 대상(소속을 낸 개체) N = 공정(골격) + 유닛·부품(노드) + 버림(출처 없음) + 미해소 + 매핑 없음 + 노드 없음`.
    `orphans`는 그 문서의 `orphan_attach` 큐 표기 집합(정규화)."""
    from core.state.ids import norm
    decl, _names = declared_belongs(cks, chunk_loc)
    left = Counter(decl)
    c = Counter()
    for r in rows:
        if r.get("role") != "entity":
            continue
        k = (r.get("locator"), norm(r.get("surface") or ""))
        if not left.get(k):
            continue
        left[k] -= 1
        if not r.get("from") or r.get("from") == "옛 attach":
            c["버림(출처 없음)"] += 1
            continue
        bel = [a for a in r.get("attached") or [] if _is_belongs(a)]
        if bel:
            c["공정(골격)" if bel[0].get("other") in skeleton else "유닛·부품(노드)"] += 1
        elif not r.get("node_id"):
            c["노드 없음"] += 1
        elif k[1] in orphans:
            c["미해소(orphan_attach)"] += 1
        else:
            c["매핑 없음"] += 1
    c["그 밖(대장 행 없음)"] += sum(left.values())
    order = ("공정(골격)", "유닛·부품(노드)", "버림(출처 없음)", "미해소(orphan_attach)", "매핑 없음", "노드 없음",
             "그 밖(대장 행 없음)")
    return line("소속 대상(소속을 낸 개체)", sum(decl.values()), [(k, c.get(k, 0), "") for k in order])


def belongs_trace(r, names, skeleton, orphans):
    """`show report --trace`의 한 행 — `소속 '<이름>' → <대상>(종류) → <결과>` (소속을 낸 개체만 · 아니면 None)."""
    from core.state.ids import norm
    k = (r.get("locator"), norm(r.get("surface") or ""))
    name = names.get(k)
    if not name:
        return None
    bel = [a for a in r.get("attached") or [] if _is_belongs(a)]
    if not r.get("from") or r.get("from") == "옛 attach":
        return f"소속 '{name}' → 버림(출처 없음 — 본문 · 경로 · 시트 · 공정에 없는 이름)"
    if bel:
        a = bel[0]
        kind = "공정 · 골격" if a.get("other") in skeleton else "유닛·부품 · 노드"
        return f"소속 '{name}'({r['from']}) → {a.get('other')}({kind}) → 엣지 {a.get('rel')} {a.get('dir')}"
    if not r.get("node_id"):
        return f"소속 '{name}'({r['from']}) → 노드 없음(이 개체가 보류 — 엣지를 걸 노드가 없다)"
    if k[1] in orphans:
        return f"소속 '{name}'({r['from']}) → 미해소(orphan_attach — 다음 인입 마무리가 다시 찾는다)"
    return f"소속 '{name}'({r['from']}) → 매핑 없음(카테고리쌍 매핑에 없다 — 좌표 폴백 · 결함 로그)"


# ---------------------------------------------------------------- 엣지 없는 노드
def edgeless(rows, graphs, doc_id, names, skeleton, orphans):
    """**이 문서가 만든 노드 중 엣지 없는 것**과 사유 — `[(층, canonical, 카테고리, 사유)]` (B102 ⑦ 수와 같은 집합)."""
    pre = f"{doc_id}#"
    ends = set()
    for g in graphs.values():
        for e in g.edges:
            ends |= {e["src"], e["dst"]}
    by_node = {}
    for r in rows:
        if r.get("role") == "entity" and r.get("node_id"):
            by_node.setdefault(r["node_id"], []).append(r)
    out = []
    for lay, g in sorted(graphs.items()):
        for nid, n in g.nodes.items():
            if nid in ends or not any(str(p) == doc_id or str(p).startswith(pre)
                                      for p in n.get("provenance") or []):
                continue
            why = []
            for r in by_node.get(nid) or [{}]:
                t = belongs_trace(r, names, skeleton, orphans) if r else None
                why.append(t.split(" → ", 1)[1] if t else "소속 없음")
            why = sorted(set(why)) + ["관계 없음", "좌표 폴백 없음"]
            out.append((lay, n.get("canonical"), n.get("category"), " · ".join(why)))
    return out


# ---------------------------------------------------------------- 문서 좌표 경고 (⑤)
def _fold(s):
    from core.state.ids import fold_latin, norm
    return fold_latin(norm(s or "")).replace(" ", "")


def near_coords(source_path, nodes, top=5):
    """파일 이름에 **띄어쓰기 · 라틴 대소문자를 무시하고** 든 골격 이름(canonical · 별칭 — `--coord`가 받는 이름) →
    그 노드의 canonical — 보여만 준다(자동 적용 0 · 정확 대조는 `parser.tagger.suggest_doc_coord`가 이미 했다)."""
    stem = _fold(PurePath(str(source_path or "")).stem)
    for ch in "_-.()[]":
        stem = stem.replace(ch, "")
    hits = {}
    for n in nodes or []:
        for k in [n.get("canonical")] + list(n.get("aliases") or []):
            f = _fold(k)
            if k and len(f) >= 2 and f in stem:
                hits[n["canonical"]] = max(hits.get(n["canonical"], 0), len(f))
    return sorted(hits, key=lambda c: (-hits[c], c))[:top]


def by_locator(env):
    """봉투의 조각 — 위치 → 조각(대장 행의 `locator`와 같은 열쇠)."""
    return {p.get("source_locator"): p for p in ((env or {}).get("records") or (env or {}).get("chunks") or [])}


def row_coord(r, by_loc):
    """행의 좌표 — 좌표 행이면 그 표기 자체 · 아니면 그 조각의 좌표(없으면 None) (B112 ④⑤ — 보류 목록 · 경고 같은 함수)."""
    if r.get("role") == "anchor":
        return r.get("surface")
    return (by_loc.get(r.get("locator")) or {}).get("process_ref")


def doc_coord_warning(rows, env, nodes):
    """문서 좌표가 없고 **좌표가 없어서** 「좌표 미해소」로 보류된 행(표기 없는 좌표 행 · 좌표 없는 조각의 행)이 있으면
    `{행, 후보}` · 아니면 None (B112 ⑤ — 동작 불변 · 제 좌표를 든 보류는 문서 좌표로 풀리지 않는다 — 세지 않는다)."""
    from core.build.result import HOLD_REASONS
    if (env or {}).get("doc_coord"):
        return None
    loc = by_locator(env)
    n = sum(1 for r in rows if hold_reason(r) == HOLD_REASONS[2][2] and not row_coord(r, loc))
    if not n:
        return None
    return {"행": n, "후보": near_coords((env or {}).get("source_path"), nodes)}


# ---------------------------------------------------------------- 그래프 · 큐
def graph_lines(res, after, before=None):
    """층마다 `노드 전 → 후 (이 문서 +n)` — 전 수는 그 실행의 사실(없으면 지금 수와 이 문서 몫만).
    층은 전부(이 문서가 건드리지 않은 층은 +0)."""
    out = []
    mine = (res or {}).get("층") or {}
    for lay in sorted(set(mine) | set(after)):
        d = mine.get(lay) or {"노드": 0, "엣지": 0}
        a = after.get(lay, (0, 0, 0))
        if before is not None:
            b = before.get(lay, (0, 0, 0))
            out.append(f"그래프 {lay} — 노드 {b[0]:,} → {a[0]:,}(이 문서 {d['노드']:+,}) · "
                       f"엣지 {b[1]:,} → {a[1]:,}(이 문서 {d['엣지']:+,})")
        else:
            out.append(f"그래프 {lay} — 이 문서 노드 {d['노드']:+,} · 엣지 {d['엣지']:+,}(지금 층 전체 노드 {a[0]:,} · "
                       f"엣지 {a[1]:,})")
    return out


def _rows(x):
    v = (x.get("payload") or {}).get("rows", 1)
    return v if isinstance(v, int) else len(v or [1])


def queue_text(entries):
    """`kind n(m행)` — 항목 수와 그 항목이 든 행 수."""
    c, r = Counter(), Counter()
    for x in entries:
        c[x["kind"]] += 1
        r[x["kind"]] += _rows(x)
    return (f"{len(c)}종 {sum(c.values()):,}항목({sum(r.values()):,}행)"
            + (" — " + " · ".join(f"{k} {c[k]:,}({r[k]:,}행)" for k in sorted(c)) if c else ""))


# ---------------------------------------------------------------- 한 묶음
def table(doc_id, rows, res, env, cks, graphs, queue, nodes, run=None):
    """맞춤표 한 묶음 — 화면(`cli/result_screen.reconcile_lines`)이 줄로 옮긴다.

    `cks`는 `[(렌즈 또는 None, 체크포인트)]` · `queue`는 그 문서의 큐 항목 · `nodes`는 좌표 층 골격 스냅샷의
    노드(`canonical` · `aliases`) · `run`(인입 끝만)은 `{"청크": {렌즈: {부름, 재사용}}, "층 전": …,
    "큐 이번": [...], "큐 이전": [...]}`."""
    from core.build.result import layer_counts
    from core.state import store
    # 청크 id → 위치 — 체크포인트는 청크 id를, 대장 행은 위치를 든다(청크 저장소가 둘을 잇는다)
    chunk_loc = {cid: c.get("source_locator") for cid, c in
                 (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}).items() if c.get("doc_id") == doc_id}
    orphans = {(x.get("payload") or {}).get("surface") for x in queue if x.get("kind") == "orphan_attach"}
    from core.state.ids import norm
    orphans = {norm(s or "") for s in orphans if s}
    skeleton = skeleton_names(nodes)
    names = {}
    for _l, ck in cks:
        names.update(declared_belongs([ck], chunk_loc)[1])
    lines = []
    for lens, ck in cks:
        lines += chunk_line(ck, ((run or {}).get("청크") or {}).get(lens or ""), lens)
    lines.append(coord_line(env))
    lines += value_lines(rows)
    lines.append(hold_line(rows))
    lines.append(attach_line(rows, skeleton))
    lines.append(belongs_line(rows, [ck for _l, ck in cks], chunk_loc, skeleton, orphans))
    q_new, q_old = (run or {}).get("큐 이번"), (run or {}).get("큐 이전")
    return {"doc_id": doc_id, "줄": lines,
            "그래프": graph_lines(res, layer_counts(graphs), (run or {}).get("층 전")),
            "큐": ({"이번 실행": queue_text(q_new), "이전 실행이 남긴 것": queue_text(q_old)} if q_new is not None
                  else {"지금 이 문서의 것": queue_text(queue)}),
            "엣지 없는 노드": edgeless(rows, graphs, doc_id, names, skeleton, orphans),
            "문서 좌표": doc_coord_warning(rows, env, nodes),
            "소속 이름": names, "고아": orphans}


# ---------------------------------------------------------------- 재료 모으기 (인입 끝 · show report)
def _checkpoints(doc_id):
    """그 문서의 추출 체크포인트 `[(렌즈 또는 None, dict)]` — 기본판 · 렌즈판(파일 이름 `<doc>@<렌즈>.json`)."""
    import json
    from core.build import extract
    out = []
    for p in extract.checkpoint_files(doc_id):
        lens = p.stem.split("@", 1)[1] if "@" in p.stem else None
        try:
            out.append((lens, json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def skeleton_nodes():
    """좌표 층 골격의 노드 — 소속 대상의 종류(공정)와 문서 좌표 후보의 재료(스냅샷에서 · 새 계산 0)."""
    from core.state import store
    from core.state.bootstrap import NoCoordLayer, coord_layer
    try:
        lay = coord_layer()
    except NoCoordLayer:
        return set()
    snap = store.read(store.SKELETON_LIST, {}).get(lay) or {}
    return [n for n in snap.get("nodes") or [] if n.get("canonical")]


def skeleton_names(nodes=None):
    """골격 canonical 이름 집합(소속 대상이 공정인가)."""
    return {n["canonical"] for n in (skeleton_nodes() if nodes is None else nodes)}


def for_build(doc_id, rows, res, env, graphs, run):
    """인입 끝 — 그 실행의 사실(`run`)과 함께."""
    from core.state import store
    q = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc_id]
    return table(doc_id, rows, res, env, _checkpoints(doc_id), graphs, q, skeleton_nodes(), run)


def for_report(doc_id, data):
    """`show report <doc_id>` — 장부만(대장 · 파싱 봉투 · 체크포인트 · 지금 그래프 · 지금 큐)."""
    import json
    from core import paths
    from core.state import store
    from core.state.bootstrap import open_graph
    from router import discover
    p = paths.parsed(f"{doc_id}.json")
    env = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    q = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc_id]
    return table(doc_id, data.get("rows") or [], data.get("result") or {}, env, _checkpoints(doc_id),
                 {lay: open_graph(lay) for lay in discover()}, q, skeleton_nodes())
