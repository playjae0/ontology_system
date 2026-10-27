# -*- coding: utf-8 -*-
"""칸 0.3 — **진단 출력** — 「무엇이 없어서 못 붙었나」를 원인 묶음 · 목차 나무 · 문서 머리로 (B149).

못 붙은 값이 아니라 **못 찾은 것**이 판단 단위다(사용자 2026-10-27). 재료는 이미 있는 기록뿐이다 — 판정 대장 행 · 파싱 봉투
(조각 좌표와 그 출처 표시 · 제목 사슬) · 문서 좌표 기록 · 고아 큐(기다리는 이름) · 결함 로그(관계 후보 끝점 미해소) · 목차
노드화 체크포인트. **읽기만** 한다(LLM 0 · 새 판정 0 · 쓰기 0) · 표 · 산문 · 형식 전부 같은 함수 · 층 어휘 0.

**수의 단위는 「못 붙은 행」이다**(B152) — 판정 대장 행 중 좌표 행(`anchor`)을 뺀 행이 보류 · 고아 · 불확실 · 종류는 맞춤표 「보류(행)」의
행 종류(`reconcile.ROW_KIND` — 개체 · 속성·내용 · 소속 · 그 밖) · 좌표 행은 원인 판정 · 위치의 재료로만 쓴다. 원인 묶음 머리 · 원인 줄 ·
목차 나무 · 좌표 표기 목록이 같은 행 집합이라 서로 맞는다(원인 줄의 종류별 합 = 머리의 분자 = 나무 · 목록의 못 붙음 합).

원인 키(위에서부터 — 행은 가장 위 원인에서 한 번만 센다):
  1 문서 좌표 없음 — 문서 좌표가 없고 좌표가 선 조각이 하나도 없다
  2 구간 좌표 없음 — 산문은 그 아래 조각이 전부 좌표 없는 가장 위 제목 하나 · 표는 골격에 맞지 않은 좌표 표기 하나
  3 소속 이름 없음 — 기다리는 이름마다(고아 큐 `orphan_attach`)
  4 관계 끝점 없음 — 끝점 이름마다(결함 로그 · 위 원인으로 못 선 값의 이름은 빼고)
  5 그 밖 — 표기 모호 · 골격 밖 · 카테고리 밖(관문) · 부착 대상 · 불확실
줄 차례는 원인 순 → 못 붙은 행이 많은 차례 · 못 붙은 행이 0인 원인은 줄 0(`--json`에는 남는다). 처방 줄은 그 종류에 맞는 길을
그대로 쳐서 도는 꼴로 보인다(고르지 않는다).
"""
from __future__ import annotations

import json
from collections import Counter

from core import paths

#: 원인 이름(차례가 순위)
DOC, SECTION, BELONGS, ENDPOINT, OTHER = "문서 좌표 없음", "구간 좌표 없음", "소속 이름 없음", "관계 끝점 없음", "그 밖"
RANK = {DOC: 1, SECTION: 2, BELONGS: 3, ENDPOINT: 4, OTHER: 5}
#: 행 종류의 차례(맞춤표 「보류(행)」의 종류에서 좌표 행을 뺀 것 — 이름은 `kind_of`가 「행」을 뗀다)
KINDS = ("개체", "속성·내용", "소속", "그 밖")
#: 못 붙은 행의 상태(한 행은 하나 · 보류가 먼저)
STATES = ("보류", "고아", "불확실")
#: 결함 로그의 관계 후보 끝점 미해소 줄(`core/build/prose.py`가 쓴다)
ENDPOINT_MARK = "관계 후보 끝점 미해소 — "


# ---------------------------------------------------------------- 재료 (읽기만)
def material(doc_id, data=None):
    """한 문서의 진단 재료 — 대장 · 봉투 · 문서 좌표(출처) · 고아 큐 · 관계 끝점 미해소 · 목차 노드화 · 렌즈."""
    from cli import doc_coord as DC
    from core.build import ledger, reconcile as RC
    from core.state import registry, store
    data = data if data is not None else (ledger.read(doc_id) or {})
    pp = paths.parsed(f"{doc_id}.json")
    env = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
    reg = store.read(store.DOC_REGISTRY, {}).get(doc_id) or {}
    rec = DC.recorded(doc_id) or {}
    coord = rec.get("coord") or env.get("doc_coord")
    src = (f"기록 · {rec.get('by') or '사람'}" if rec.get("coord") else "파일명" if env.get("doc_coord") else "없음")
    queue = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc_id]
    dt = reg.get("doc_type") or env.get("doc_type")
    lenses = registry.lenses_of(dt) if dt and registry.lookup(dt) else []
    return {"doc_id": doc_id, "rows": data.get("rows") or [], "env": env, "doc_coord": coord, "doc_coord_src": src,
            "source": paths.from_home(reg["source_path"]) if reg.get("source_path") else f"<{doc_id} 원본>",
            "doc_type": dt or "<dt>", "orphans": [x for x in queue if x.get("kind") == "orphan_attach"],
            "endpoints": _endpoint_misses(doc_id), "by_loc": RC.by_locator(env), "lenses": lenses,
            "skeleton": RC.skeleton_nodes()}


def _endpoint_misses(doc_id):
    """결함 로그의 그 문서 관계 후보 끝점 미해소 — `[(src, rel, dst, 청크)]`(같은 줄은 한 번 · 재인입이 쌓은 겹침 0)."""
    import re
    from core.state import store
    p = store.path(store.DEFECTS)
    if not p.exists():
        return []
    pat = re.compile(rf"^{re.escape(doc_id)}: {ENDPOINT_MARK}'(.*)' -(\S+)-> '(.*)' @ (\S+)\s*$")
    seen = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = pat.match(ln.split("] ", 1)[-1].strip()) or pat.match(ln.strip())
            if m and m.groups() not in seen:
                seen.append(m.groups())
    return seen


def _norm(s):
    from core.state.ids import fold_latin, norm
    return fold_latin(norm(s or "")).replace(" ", "")


def _src(piece):
    """조각 좌표의 출처 — 자기 · 문서 좌표 · 없음 · 무시 · 공유 별칭 건너뜀(봉투 표시에서 · `doc_coord.coord_counts`와 같은 표시)."""
    m = (piece or {}).get("meta") or {}
    if not (piece or {}).get("process_ref"):
        return "무시" if m.get("coord_ignored") else "공유 별칭 건너뜀" if m.get("coord_shared_skip") else "없음"
    return "문서 좌표" if m.get("coord_from_doc") else "자기"


def _coord(piece):
    from parser.normalizer import coord_text
    return coord_text((piece or {}).get("process_ref")) or None


# ---------------------------------------------------------------- 수의 단위 — 못 붙은 행 (B152 ①)
def kind_of(r):
    """행 종류 — 맞춤표 「보류(행)」의 종류 함수 그대로(`reconcile.ROW_KIND` · 없으면 그 밖)에서 「행」을 뗀 이름."""
    from core.build.reconcile import ROW_KIND
    return ROW_KIND.get(r.get("role"), "그 밖 행").removesuffix(" 행")


def _rows(mat, layer=None):
    """셈 대상 — `[(행 차례, 행)]` 좌표 행을 뺀 대장 행(렌즈면 그 층)."""
    return [(i, r) for i, r in enumerate(mat["rows"]) if r.get("role") != "anchor"
            and not (layer and r.get("layer") and r.get("layer") != layer)]


def _values(mat, layer=None):
    """못 붙은 행 — `[(행 차례, 행, 상태)]` 상태 = 보류 · 고아 · 불확실(한 행은 하나 · 보류가 먼저 · 좌표 행은 세지 않는다)."""
    key = ("_values", layer)
    if key in mat:
        return mat[key]
    from core.build.result import hold_reason
    waits = {(it.get("provenance") or "").split("#")[-1] + "\0" + _norm(it.get("surface"))
             for x in mat["orphans"] for it in (x.get("payload") or {}).get("items") or []}
    out = []
    for i, r in _rows(mat, layer):
        if hold_reason(r):
            out.append((i, r, "보류"))
        elif f"{r.get('locator')}\0{_norm(r.get('surface'))}" in waits:
            out.append((i, r, "고아"))
        elif r.get("verdict") in ("uncertain", "lowres"):
            out.append((i, r, "불확실"))
    mat[key] = out
    return out


def _kinds_text(cnt):
    """종류별 수 — `개체 2 · 속성·내용 1`(0인 칸은 뺀다)."""
    return " · ".join(f"{k} {cnt[k]:,}" for k in KINDS if cnt.get(k))


def head_count(mat, layer=None):
    """원인 묶음 머리의 재료 — `(못 붙은 행 n, 전체 N, 종류별 [(종류, 못 붙음, 전체)], 상태별 Counter)`."""
    vals = _values(mat, layer)
    tot = Counter(kind_of(r) for _i, r in _rows(mat, layer))
    lost = Counter(kind_of(r) for _i, r, _s in vals)
    return len(vals), sum(tot.values()), [(k, lost[k], tot[k]) for k in KINDS if lost.get(k)], \
        Counter(s for _i, _r, s in vals)


# ---------------------------------------------------------------- 원인 묶음 ①


def _top_heading(mat):
    """산문 조각 위치 → 그 아래 조각이 전부 좌표 없는 가장 위 제목 경로(없으면 그 조각의 경로) — `outline.tree` 한 함수."""
    from core.build import outline as OL
    t = OL.tree(mat["env"])
    heads = {h["id"]: h for h in t["headings"]}
    has = Counter()
    for loc, hid in t["of"].items():
        if _coord(mat["by_loc"].get(loc)):
            while hid:
                has[hid] += 1
                hid = heads[hid]["parent"]
    out = {}
    for loc, hid in t["of"].items():
        top = None
        while hid and not has[hid]:
            top, hid = hid, heads[hid]["parent"]
        out[loc] = heads[top]["path"] if top else (mat["by_loc"].get(loc) or {}).get("section") or loc
    return out


def causes(mat, layer=None):
    """원인 묶음 — `[{원인, 못 찾은 것, 행, 종류, 위치, 처방}]`(원인 순 → 못 붙은 행 수). 행은 가장 위 원인에서 한 번만 · 큐 항목 ·
    끝점 이름처럼 대장 행이 아닌 것은 `밖`에만 센다(행 0이면 화면 줄 0)."""
    from core.build.result import ATTACH_NOT_TARGET, ATTACH_UNRESOLVED, HOLD_REASONS, hold_reason
    vals = _values(mat, layer)
    pieces = mat["env"].get("records") or mat["env"].get("chunks") or []
    any_coord = any(_coord(p) for p in pieces)
    anchor = {_norm(r.get("surface")): hold_reason(r) for r in mat["rows"] if r.get("role") == "anchor"}
    tops = _top_heading(mat) if mat["env"].get("chunks") else {}
    groups, taken = {}, set()

    rk = {i: kind_of(r) for i, r, _s in vals}

    def put(kind, what, i, loc, fix):
        """한 행(또는 큐 항목 · 끝점 하나)을 그 원인에 — `i`가 행 차례(정수)면 행으로 세고 아래 원인에서 다시 세지 않는다."""
        g = groups.setdefault((kind, what), {"원인": kind, "못 찾은 것": what, "행": 0, "종류": Counter(), "밖": 0,
                                             "위치": [], "처방": fix})
        if isinstance(i, int):
            g["행"] += 1
            g["종류"][rk[i]] += 1
            taken.add(i)
        else:
            g["밖"] += 1
        if loc and loc not in g["위치"] and len(g["위치"]) < 2:
            g["위치"].append(loc)

    doc, dt = mat["source"], mat["doc_type"]
    for i, r, kind in vals:
        loc, co = r.get("locator"), _row_coord(r, mat["by_loc"])
        if not co and not mat["doc_coord"] and not any_coord:
            put(DOC, "문서 좌표", i, loc, f"python run.py ingest-file {doc} --doc-type {dt} --coord <골격 이름>")
        elif not co:
            what = tops.get(loc) or "(좌표 칸 빈 행)"
            put(SECTION, what, i, loc, _fix_section(mat, what))
        elif kind == "보류" and anchor.get(_norm(co)) == HOLD_REASONS[0][2]:      # 표 — 골격에 맞지 않은 좌표 표기
            put(SECTION, f"좌표 표기 '{co}'", i, loc, f"골격 ALIASES[\"<골격 canonical>\"]에 \"{co}\" → python run.py bootstrap → "
                                                  f"python run.py ingest-file {doc} --doc-type {dt}")
    for x in mat["orphans"]:
        pl = x.get("payload") or {}
        name = pl.get("attach_to") or pl.get("key")
        for it in pl.get("items") or []:
            i = _row_of(mat, vals, it)
            if i is not None and i in taken:
                continue
            put(BELONGS, name, i if i is not None else ("큐", id(it)), (it.get("provenance") or "").split("#")[-1] or None,
                f"python run.py ingest-file {doc} --doc-type {dt} --step(사람 후보 [5/8]에서 이 이름을 세운다) · 다른 문서에 "
                f"섰으면 python run.py ops relink all --doc {mat['doc_id']} --actor <이름>")
    _endpoints(mat, vals, taken, put)
    for i, r, kind in vals:
        if i in taken:
            continue
        why = hold_reason(r) or kind
        fix = {ATTACH_NOT_TARGET: _revise(dt), ATTACH_UNRESOLVED: f"python run.py show report {mat['doc_id']} --trace",
               HOLD_REASONS[1][2]: f"골격 seed에 노드 · ALIASES → python run.py bootstrap → python run.py ops relink all "
                                   f"--doc {mat['doc_id']} --actor <이름>",
               HOLD_REASONS[3][2]: "층 config categories · relation_patterns → python run.py bootstrap · 버린 것은 "
                                   "python run.py show log gate --by-pattern",
               "불확실": "python run.py platform queue uncertain_match(맞다 ops confirm · 같은 것 ops merge · 아니다 ops obsolete)",
               }.get(why) or (f"python run.py ingest-file {doc} --doc-type {dt} --coord <그 공정>" if "모호" in why
                              else f"python run.py show report {mat['doc_id']} --trace")
        near = (r.get("nearest") or {}).get("canonical")
        put(OTHER, why, i, f"{r.get('surface')} → {near or '후보 없음'}" if kind == "불확실" else r.get("locator"), fix)
    out = sorted(groups.values(), key=lambda g: (RANK[g["원인"]], -g["행"], str(g["못 찾은 것"])))
    for g in out:
        g["위치"] = " · ".join(g["위치"])
        g["종류"] = dict(g["종류"])
    return out


def _row_coord(r, by_loc):
    from core.build.reconcile import row_coord
    return row_coord(r, by_loc)


def _row_of(mat, vals, item):
    loc = (item.get("provenance") or "").split("#")[-1]
    s = _norm(item.get("surface"))
    return next((i for i, r, _k in vals if r.get("locator") == loc and _norm(r.get("surface")) == s), None)


def _endpoints(mat, vals, taken, put):
    """관계 끝점 없음 — 끝점 이름마다(그 문서에서 선 이름 · 골격 이름은 끝점이 섰다 · 위 원인으로 못 선 값의 이름은 빼고)."""
    stood = {_norm(r.get("surface")) for r in mat["rows"] if r.get("node_id")}
    stood |= {_norm(n.get("canonical")) for n in mat["skeleton"]}
    stood |= {_norm(a) for n in mat["skeleton"] for a in n.get("aliases") or []}
    upstream = {_norm(r.get("surface")) for i, r, _k in vals if i in taken}
    for s, _rel, d, cid in mat["endpoints"]:
        for name in (s, d):
            k = _norm(name)
            if k in stood or k in upstream:
                continue
            put(ENDPOINT, name, ("끝점", name, cid, _rel), cid,
                f"python run.py ingest-file {mat['source']} --doc-type {mat['doc_type']} --step(사람 후보 [5/8]에서 이 이름을 "
                f"세운다) · 다른 문서에 섰으면 python run.py ops relink all --doc {mat['doc_id']} --actor <이름>")


def _fix_section(mat, what):
    """좌표 없는 구간 — 산문 조각의 좌표는 파싱이 단다(좌표 없는 조각의 anchor 보류는 큐가 없어 재연결이 다시 보지 않는다) → 다시 넣는 길."""
    again = f"python run.py ingest-file {mat['source']} --doc-type {mat['doc_type']}"
    return (f"{again} --coord <골격 이름>(문서 전체가 한 공정이면) · 제목이 공정 이름이면 골격 ALIASES에 그 이름 → "
            f"python run.py bootstrap → {again}")


def _revise(dt):
    from cli.register.recheck import revise_line
    return revise_line(dt, schema_only=True)            # 부착 대상은 스키마 칸 — 운영 어댑터 그대로(B150 ③)


def head_line(mat, layer=None):
    """원인 묶음 머리 — `원인 묶음 — 못 붙은 행 n / 전체 N — 개체 a/A · … · 보류 x · 고아 y · 불확실 z`(0인 종류 · 상태는 뺀다) ·
    못 붙은 행이 0이면 None(묶음 0)."""
    n, tot, kinds, states = head_count(mat, layer)
    if not n:
        return None
    return (f"  원인 묶음 — 못 붙은 행 {n:,} / 전체 {tot:,} — " + " · ".join(f"{k} {a:,}/{b:,}" for k, a, b in kinds)
            + "".join(f" · {s} {states[s]:,}" for s in STATES if states.get(s)))


def cause_lines(cs, limit=None, mat=None, layer=None):
    """원인 묶음 → 줄들(못 붙은 행 0이면 빈 목록) — 머리(`head_line`) + 원인마다 `<원인> — <못 찾은 것> · 못 붙은 행 m(종류별) ·
    <위치>` + `▶ 처방` · 행 0인 원인은 줄 0. `limit`이면 그 줄까지 · 넘으면 「… 외 n」."""
    cs = [g for g in cs or [] if g["행"]]
    head = head_line(mat, layer) if mat is not None else None
    if not cs or (mat is not None and not head):
        return []
    from cli import _screen
    out = ["", head or f"  원인 묶음 — 못 붙은 행 {sum(g['행'] for g in cs):,}"]
    for g in cs[:limit]:
        tail = f" · {g['위치']}" if g["위치"] else ""
        near = ""
        if g["원인"] == DOC and mat is not None:
            from core.build.reconcile import near_coords
            nc = near_coords(mat["env"].get("source_path"), mat["skeleton"])
            near = " · 가까운 골격 이름(보여만 준다): " + (" · ".join(nc) if nc else "없음")
        out.append(f"    {g['원인']} — {_screen.cut(str(g['못 찾은 것']), 60)} · 못 붙은 행 {g['행']:,}"
                   f"({_kinds_text(g['종류'])}){tail}{near}")
        out.append(f"      ▶ {g['처방']}")
    if limit is not None and len(cs) > limit:
        out.append(f"    … 외 {len(cs) - limit:,}")
    return out


# ---------------------------------------------------------------- 목차 나무 ② · 문서 머리 ③
def head_lines(mat):
    """문서 머리 — 문서 좌표와 출처 · 조각 좌표 출처별 수(`doc_coord.coord_line` 그대로)."""
    from cli.doc_coord import coord_line
    return [f"   문서 좌표 — {mat['doc_coord'] or '없음'} (출처: {mat['doc_coord_src']})", coord_line(mat["env"])]


def _counts(mat, locs, layer=None):
    """위치들의 행 — `(붙음, 못 붙음, 그 안 고아, 센 행 차례들)` — 단위는 원인 묶음과 같은 못 붙은 행(좌표 행 제외 · B152 ①) · 붙음은
    셈 대상 행 중 못 붙지 않고 노드에 닿은 것."""
    lost = {i: s for i, _r, s in _values(mat, layer)}
    a = b = o = 0
    seen = set()
    for i, r in _rows(mat, layer):
        if r.get("locator") not in locs:
            continue
        seen.add(i)
        if i in lost:
            b += 1
            o += lost[i] == "고아"
        elif r.get("node_id"):
            a += 1
    return a, b, o, seen


def _node_state(h, rows):
    from core.build.result import hold_reason
    if h is None:
        return "목차 노드화 없음"
    if h.get("coord"):
        return "좌표(골격)"
    if h.get("dropped"):
        return "버림(목차 노드화)"
    tg = h.get("target")
    if not tg:
        return "이 층의 노드 아님"
    row = next((r for r in rows if r.get("role") == "heading" and r.get("locator") == h.get("path")), None)
    if row and row.get("node_id"):
        return f"{tg.get('category')} 노드"
    return f"보류({hold_reason(row) or (row or {}).get('verdict') or '대장 행 없음'})"


def tree_lines(mat, verbose=False, layer=None):
    """목차 나무 — 제목마다 좌표(출처) · 노드 상태 · 값 · 문제 있는 가지만 펼친다(`verbose`면 전부) · 표는 좌표 표기 목록."""
    if mat["env"].get("records") is not None and not mat["env"].get("chunks"):
        return _coord_list(mat, layer)
    from core.build import outline as OL
    t = OL.tree(mat["env"])
    if not t["headings"]:
        return []
    ck = (OL.load(mat["doc_id"], layer) if layer else None) or OL.load_any(mat["doc_id"]) or {}
    by_path = {h.get("path"): h for h in ck.get("headings") or []}
    kids, own = {}, {}
    for h in t["headings"]:
        kids.setdefault(h["parent"], []).append(h)
    for loc, hid in t["of"].items():
        own.setdefault(hid, set()).add(loc)

    def sub(hid):
        s = set(own.get(hid) or ())
        for c in kids.get(hid) or []:
            s |= sub(c["id"])
        return s
    for h in t["headings"]:                     # 제목 개체 행의 위치 = 제목 경로 — 그 제목의 몫으로 센다
        own.setdefault(h["id"], set()).add(h["path"])
    out = ["", "  목차 나무 — 제목 · 좌표(출처) · 노드 · 붙음 · 못 붙음" + ("" if verbose else " · 다 붙은 가지는 접는다(-v면 전부)")]
    counted = set()

    def walk(parent, depth):
        folded = [0, 0]
        for h in kids.get(parent) or []:
            locs = sub(h["id"])
            a, b, _o, seen = _counts(mat, locs, layer)
            if not verbose and not b:
                folded[0] += 1
                folded[1] += a
                counted.update(seen)
                continue
            first = next((mat["by_loc"].get(x) for x in sorted(own.get(h["id"]) or locs) if x in mat["by_loc"]), None)
            a1, b1, o1, seen1 = _counts(mat, own.get(h["id"]) or set(), layer)
            counted.update(seen1)
            co, src = _coord(first), _src(first)
            where = f"좌표 {co}({src})" if co else "좌표 없음" + (f"({src})" if src != "없음" else "")
            out.append(f"  {'  ' * depth}{h['text']} — {where} · 노드: "
                       f"{_node_state(by_path.get(h['path']), mat['rows'])} · 붙음 {a1:,} · 못 붙음 {b1:,}"
                       + (f"(고아 {o1:,})" if o1 else ""))
            walk(h["id"], depth + 1)
        if folded[0]:
            out.append(f"  {'  ' * depth}… 다 붙은 가지 {folded[0]:,} · 붙음 {folded[1]:,}")
    walk(None, 1)
    rest = [r for i, r, _s in _values(mat, layer) if i not in counted]
    if rest:                                     # 어느 제목 아래에도 안 걸린 못 붙은 행 — 합이 머리와 맞게 그 까닭과 함께
        out.append(f"    (목차 밖) — 제목 아래 조각이 아닌 위치 · 못 붙음 {len(rest):,} · "
                   + " · ".join(dict.fromkeys(str(r.get("locator")) for r in rest[:3])))
    return out


def _coord_list(mat, layer=None):
    """표의 목차 자리 — 좌표 표기 → 골격 노드 또는 없음 · 레코드 · 붙음 · 못 붙음(못 붙은 행 단위 — B152 ④)."""
    from core.build.result import hold_reason
    recs = mat["env"].get("records") or []
    if not recs:
        return []
    by = {}
    for p in recs:
        by.setdefault(_coord(p) or "(빈칸)", set()).add(p.get("source_locator"))
    anchors = {}
    for r in mat["rows"]:
        if r.get("role") == "anchor":
            anchors.setdefault(_norm(r.get("surface")), r)
    out = ["", "  좌표 표기 목록 — 표기 → 골격 노드 또는 없음 · 레코드 · 붙음 · 못 붙음"]
    for co, locs in sorted(by.items(), key=lambda x: (-len(x[1]), x[0])):
        a, b, o, _seen = _counts(mat, locs, layer)
        ar = anchors.get(_norm(co)) or {}
        to = ar.get("canonical") if ar.get("node_id") else (hold_reason(ar) or ("문서 좌표" if mat["doc_coord"] else "없음"))
        out.append(f"    {co} → {to or '없음'} · 레코드 {len(locs):,} · 붙음 {a:,} · 못 붙음 {b:,}" + (f"(고아 {o:,})" if o else ""))
    return out


def cause_block(doc_id, limit=None):
    """인입 끝 — 원인 묶음만(층마다 · 줄 상한) · 값 중심 보류 · 불확실 목록의 자리(B149 ④)."""
    mat = material(doc_id)
    out = []
    for lay in (mat["lenses"] if len(mat["lenses"] or []) > 1 else [None]):
        cs = cause_lines(causes(mat, lay), limit, mat, lay)
        out += ([f"\n  ── 층 {lay}"] + cs) if (lay and cs) else cs
    return out


def report(doc_id, data=None, verbose=False, limit=None):
    """`show report` 기본 · 인입 끝이 부르는 한 자리 — `(줄들, json 재료)`. 렌즈가 둘 이상이면 층마다 원인 · 나무."""
    mat = material(doc_id, data)
    layers = mat["lenses"] if len(mat["lenses"] or []) > 1 else [None]
    lines, js = head_lines(mat), {"문서 좌표": mat["doc_coord"], "출처": mat["doc_coord_src"], "층": {}}
    for lay in layers:
        cs = causes(mat, lay)
        if lay:
            lines.append(f"\n  ── 층 {lay}")
        lines += cause_lines(cs, limit, mat, lay)
        tl = tree_lines(mat, verbose, lay) if limit is None else []
        lines += tl
        js["층"][lay or "-"] = {"원인": cs, "목차": tl}
    return lines, js
