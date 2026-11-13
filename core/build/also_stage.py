# -*- coding: utf-8 -*-
"""칸 0.3 곁 — **판정 전 처분 자리의 재료**(B197 ②③④ · 쓰기 0) — 골격 단의 문에 걸릴 값 · 확정한 공정 · 쌍별 예고 · 쓰기 전 판정 결과.

| 무엇 | 자리 |
|---|---|
| 제목 개체 중 겸 단에 설 것(목차 노드화 결과) — 판단은 [3/8] · 줄은 [5/8] 맨 앞 한 표(B204 ①) | `heading_items` → `also_gate.scan` |
| 버린 제목 아래 청크 — 추출 뒤 그 결과를 버린다(B204 ①) | `dropped_locators` · `drop_after` |
| 청크마다 확정한 공정 쌍 `(상위, 하위 또는 None)` · 끝 줄 | `pairs` · `pair_line` |
| 본문 값 중 겸 단에 설 것([5/8] 머리) | `body_items` → `also_gate.scan` |
| [5/8] 쌍별 예고(표 [4/7]도 같은 함수) — 붙을 자리(판정 전) · 연결 · 판정 예정 · 화면은 쌍마다 요약 · 전부는 md(B199 ①) | `preview` · `preview_lines` |
| 쓰기 전 판정 결과 — 쌍마다 match · new · uncertain · 문 · 자리가 바뀐 값(판정 전 이름 부모 ≠ 실제 — B199 ②) | `verdicts` · `moved` · `verdict_lines` |

판단은 문의 판단(`also_gate.scan` — 판정 함수 그대로 · 구축이 다시 부르지 않는다) · 그 밖은 사전 · 관문까지(LLM 0). 코드에 층 어휘 0.
"""
from __future__ import annotations

from core.state.ids import norm

#: 쌍 이름 사이 · 상위만 표시
ARROW, ONLY = " › ", "(상위만)"


def _coord():
    from core.state.bootstrap import COORD_CATEGORY
    return COORD_CATEGORY


def builder(env):
    """미리보기 빌더 — 좌표 층 그래프 · 쓰기 0(저장하지 않는다)."""
    from core.build.build import Builder
    from core.state.bootstrap import coord_layer, load_config, open_graph
    lay = coord_layer()
    b = Builder(open_graph(lay), load_config(lay), None, env.get("doc_id"), lay)
    b.doc_coord = env.get("doc_coord")
    return b


def _prov(env, src):
    loc = (src or {}).get("source_locator")
    return f"{env['doc_id']}#{loc}" if loc else env["doc_id"]


def _chunk_coord(b, src, prov):
    from core.build import heading as HD
    ref, g, _p = HD._kw(b, src, prov)
    return ref, g


# ---------------------------------------------------------------- 제목 개체
def heading_items(b, env, outline):
    """제목 개체 중 **겸 카테고리**(골격 이름 제목 밖) — `[{surface, category, coord, prov, place, hid}]` · 좌표는 위 골격 이름 제목 →
    그 아래 첫 조각의 좌표(구축 `heading.land`와 같은 재료)."""
    from core.build import also_gate, heading as HD
    heads = [h for h in (outline or {}).get("headings") or []
             if h.get("target") and not h.get("coord") and also_gate.tiers(h["target"].get("category"))]
    if not heads:
        return []
    first = HD._first_chunks(env, outline)
    by = {h["id"]: h for h in outline["headings"]}
    out = []
    for h in heads:
        src = first.get(h["id"]) or {}
        prov = _prov(env, src)
        ref, g = _chunk_coord(b, src, prov)
        cur = h.get("parent")
        while cur is not None and cur in by:
            u = by[cur]
            if u.get("coord") and u.get("target"):
                hid, hg = b.resolve_anchor(u["target"]["name"], _coord(), None, defer=[])
                if hid:
                    ref, g = hid, hg
                    break
            cur = u.get("parent")
        out.append({"surface": h["target"]["name"], "category": h["target"]["category"], "coord": (ref, g),
                    "prov": prov, "place": h["path"], "hid": h["id"]})
    return out


def _answer(b, it):
    """그 값의 지금 처분 — `(답, 노드 이름)` · 답 = 골격(사전) · 새로 · 올림 · drop · 보류 · None(문 밖)."""
    from core.build import also_gate
    from core.state import provisional_hand as PH
    p = also_gate.place(b, it["category"], it.get("coord"))
    if p is None:
        return None, None
    hit = [n for n in b.dict.lookup(it["surface"]) if n in p["under"]]
    if len(hit) == 1:
        return "골격", p["g"].get(hit[0])["canonical"]
    d = PH.decided(also_gate._book(b), it["surface"], p["up"])
    return {PH.SEEDED: "새로", PH.RAISED: "올림", PH.DROPPED: "drop"}.get(d, "보류"), it["surface"]


def dropped_locators(b, env, outline, items):
    """버린 제목 아래 조각의 위치 — 추출 뒤 그 결과를 버린다(`drop_after` — B204 ①)."""
    from core.build import outline as OL
    b.also["book"] = None                          # 처분 뒤 다시 읽는다
    hids = {it["hid"] for it in items if _answer(b, it)[0] == "drop"}
    if not hids:
        return set()
    return {c.get("source_locator") for c in env.get("chunks") or []
            if any(h["id"] in hids for h in OL.chain(outline, c.get("source_locator")))}


# ---------------------------------------------------------------- 확정한 공정
def pairs(b, env, outline=None, items=()):
    """조각마다 **확정한 공정 쌍** `{위치: (상위 이름, 하위 이름 또는 None)}` — 하위 = 가장 가까운 골격 이름 제목 · 정한 골격 단 제목
    (골격 · 새로) · 표는 그 행의 ref(위 = 골격 부모). 올림 · 보류 · drop은 상위만(drop은 따로 센다)."""
    from core.build import outline as OL
    table = env.get("payload_kind") == "table"
    by_hid = {it["hid"]: it for it in items}
    out = {}
    for p in (env.get("records") if table else env.get("chunks")) or []:
        loc = p.get("source_locator")
        prov = _prov(env, p)
        if table:
            ref, g = b.resolve_anchor(p.get("process_ref") or p.get("process_group"), _coord(), None, defer=[]) \
                if (p.get("process_ref") or p.get("process_group")) else (None, None)
            if not ref:
                out[loc] = (None, None)
                continue
            n = g.get(ref)
            up = b._parent_map(g, _coord()).get(n["canonical"])
            out[loc] = (up, n["canonical"]) if (p.get("process_ref") and up) else (n["canonical"], None)
            continue
        ref, g = _chunk_coord(b, p, prov)
        top = g.get(ref)["canonical"] if ref else None
        low = None
        for h in OL.chain(outline, loc) if outline else []:
            if h.get("coord") and h.get("target") and h["target"]["name"] != top:
                low = h["target"]["name"]
                break
            if h["id"] in by_hid:
                ans, name = _answer(b, by_hid[h["id"]])
                low = name if ans in ("골격", "새로") else ("drop" if ans == "drop" else None)
                break
        out[loc] = (top, low)
    return out


def pair_line(pm, table=False):
    """`확정한 공정 — 청크 n: <상위 › 하위> a · <상위>(상위만) b …`(표는 행)."""
    from collections import Counter
    c = Counter(pm.values())
    parts = []
    for (up, low), n in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        if up is None:
            parts.append(f"좌표 없음 {n:,}")
        elif low == "drop":
            parts.append(f"{up} › 사람 버리기 {n:,}")
        elif low:
            parts.append(f"{up}{ARROW}{low} {n:,}")
        else:
            parts.append(f"{up}{ONLY} {n:,}")
    return f"확정한 공정 — {'행' if table else '청크'} {len(pm):,}: " + (" · ".join(parts) or "없음")


# ---------------------------------------------------------------- 본문 값([5/8] 머리)
def body_items(b, env, candidates, loc_of, outline=None, items=()):
    """추출이 뽑은 값 중 **겸 카테고리** — 좌표는 확정한 공정 쌍의 아래(없으면 위) · `scan`의 재료."""
    from core.build import also_gate
    by_loc = {c.get("source_locator"): c for c in env.get("chunks") or []}
    pm = pairs(b, env, outline, items)
    out = []
    for cand in candidates or []:
        loc = loc_of.get(cand["chunk_id"])
        for e in cand.get("entities") or []:
            if not also_gate.tiers(e.get("category")):
                continue
            ref, g = _pair_node(b, pm.get(loc))
            out.append({"surface": e["surface"], "category": e["category"], "coord": (ref, g),
                        "prov": _prov(env, by_loc.get(loc)), "place": _place(by_loc.get(loc))})
    return out


def _pair_node(b, pair):
    up, low = pair or (None, None)
    name = low if low and low != "drop" else up
    return b.resolve_anchor(name, _coord(), None, defer=[]) if name else (None, None)


def _place(src):
    from core.build import extract_ctx
    return extract_ctx.place(src or {})


# ---------------------------------------------------------------- 쌍별 예고 (③)
def preview(b, env, candidates=None, loc_of=None, outline=None, items=(), schema=None):
    """**쌍별 예고**(B197 ③ · 쓰기 0 · LLM 0) — `{쌍: [{surface, category, at, rel, plan}]}` · 산문은 추출 후보 · 표는 행의 개체 칸."""
    pm = pairs(b, env, outline, items)
    groups = {}
    if env.get("payload_kind") == "table":
        fields = (schema or {}).get("fields") or {}
        for r in env.get("records") or []:
            for f, spec in fields.items():
                if spec.get("role") == "entity" and r.get(f) not in (None, ""):
                    groups.setdefault(pm.get(r.get("source_locator")), []).append(
                        _line(b, r[f], spec.get("category"), pm.get(r.get("source_locator")), None))
    else:
        from core.build import outline as OL
        by_hid = {it["hid"]: it for it in items}
        for cand in candidates or []:
            loc = (loc_of or {}).get(cand["chunk_id"])
            hd = next((h for h in OL.chain(outline, loc) if h.get("target") and not h.get("coord")), None) if outline else None
            held = _answer(b, by_hid[hd["id"]])[0] if hd and hd["id"] in by_hid else None
            if held in ("골격", "새로", "올림"):           # 그 제목은 골격 노드(쌍의 아래) · 올림은 위 공정 — 제목 이름을 따로 붙이지 않는다
                hd = None
            for e in cand.get("entities") or []:
                if e.get("surface"):
                    bt = e.get("belongs_to") or {}
                    ln = _line(b, e["surface"], e.get("category"), pm.get(loc), bt.get("name") or (hd or {}).get(
                        "target", {}).get("name"), bt.get("category") or ((hd or {}).get("target") or {}).get("category"))
                    if held in ("보류", "drop"):           # 위 제목이 골격 단의 문에 걸렸다 — 그 보류와 함께
                        ln["plan"] = f"{'버리기' if held == 'drop' else '보류'} — 제목 {hd['target']['name']}(골격 단 — 이름 처분)"
                    groups.setdefault(pm.get(loc), []).append(ln)
    for k, rows in groups.items():
        seen, keep = {}, []
        for r in rows:
            kk = (norm(r["surface"]), r["category"], r["at"])
            if kk not in seen:
                seen[kk] = r
                r["n"] = 0
                keep.append(r)
            seen[kk]["n"] += 1                         # 같은 판정 단위가 나온 행 · 청크 수(요약의 「행 수 큰 차례」 — B199 ①)
        groups[k] = keep
    return groups


def _line(b, surface, category, pair, belongs, tgt_cat=None):
    """판정 단위 한 줄 — 붙을 자리(이름 부모 경로) · 연결(관계) · 판정 예정(사전 연결 · 후보 0 → 새 노드 · 후보 n → 판정 · 문)."""
    from core import matcher
    from core.build import also_gate, belongs as BL
    from core.build.build import entity_key
    from parser.normalizer import null_marker
    up, low = pair or (None, None)
    node = low if low and low != "drop" else up
    at = ARROW.join(x for x in (node, belongs) if x) or "—"
    eb = b.for_category(category) if category else b
    rel = None
    if category:
        rel = BL.edge_of(eb.cfg, (tgt_cat if belongs else None) or _coord(), category)[0]
    if null_marker(surface):
        plan = "빈칸 표시"
    elif not category:
        plan = "—"
    else:
        ref, g = _pair_node(b, pair)
        p = also_gate.place(b, category, (ref, g))
        if p is not None and not [n for n in b.dict.lookup(surface) if n in p["under"]]:
            plan = "골격 단 — 문"
        else:
            parent = g.get(ref)["canonical"] if ref else None
            try:
                canonical, scoped, _sc = entity_key(surface, category, eb.cfg, parent_canonical=parent)
                out, pool, _g = matcher.gated(canonical, category, eb.layer, eb.g, eb.dict, scoped=scoped,
                                              parent=parent, cfg=eb.cfg)
            except Exception:                            # noqa: BLE001 — 예고는 판정을 막지 않는다
                out, pool = [], []
            plan = "사전 연결" if out else ("후보 0 → 새 노드" if not pool else f"후보 {len(pool):,} → 판정")
    return {"surface": surface, "category": category or "—", "at": at, "rel": rel or "—", "plan": plan}


#: 요약에 내는 판정 대상 수(쌍마다 — 행 수 큰 차례 · 나머지는 md · B199 ①)
TOP = 3
#: 판정 예정의 갈래 — 요약 줄의 칸(사전 연결 · 새 노드 · 판정(후보 있음) · 그 밖)
PLAN_KINDS = (("사전 연결", "사전 연결"), ("새 노드", "후보 0 → 새 노드"), ("판정(후보 있음)", "→ 판정"))


def _head(pair):
    up, low = pair or (None, None)
    return "좌표 없음" if up is None else (f"{up}{ARROW}{low}" if low and low != "drop" else f"{up} {ONLY}")


def _kind(plan):
    return next((k for k, mark in PLAN_KINDS if str(plan).endswith(mark) or plan == mark), "그 밖")


def preview_lines(groups, indent="   ", full=False):
    """쌍별 예고 줄 — `full`이면 전부(md · 묶음 머리 `상위 › 하위 (값 n)` · 줄 = 표기 · 카테고리 · 붙을 자리(판정 전) · 연결 · 판정
    예정 · 칸을 자르지 않는다) · 아니면 쌍마다 한 줄(값 n — 사전 연결 a · 새 노드 b · 판정 c(후보 있음) · 그 밖 d) + 판정 대상 위
    `TOP`(행 수 큰 차례 · 한 줄 — B199 ①)."""
    out = []
    for pair, rows in sorted(groups.items(), key=lambda kv: (kv[0] is None, str(kv[0]))):
        if full:
            out.append(f"{indent}{_head(pair)} (값 {len(rows):,})")
            w = [max([len(str(r[k])) for r in rows] + [1]) for k in ("surface", "category", "at", "rel")]
            for r in rows:
                out.append(f"{indent}  {str(r['surface']).ljust(w[0])}  {str(r['category']).ljust(w[1])}  붙을 자리(판정 전) "
                           f"{str(r['at']).ljust(w[2])}  {str(r['rel']).ljust(w[3])}  {r['plan']}")
            continue
        cnt = {}
        for r in rows:
            cnt[_kind(r["plan"])] = cnt.get(_kind(r["plan"]), 0) + 1
        kinds = [k for k, _m in PLAN_KINDS] + ["그 밖"]
        out.append(f"{indent}{_head(pair)}  값 {len(rows):,} — "
                   + " · ".join(f"{k} {cnt.get(k, 0):,}" for k in kinds if cnt.get(k) or k != "그 밖"))
        judge = sorted((r for r in rows if _kind(r["plan"]) == PLAN_KINDS[2][0]), key=lambda r: -r.get("n", 1))
        if judge:
            more = len(judge) - TOP
            out.append(f"{indent}  판정 — " + " · ".join(f"{r['surface']}({r['category']})" for r in judge[:TOP])
                       + (f" · 그 밖 {more:,}" if more > 0 else ""))
    return out


# ---------------------------------------------------------------- 쓰기 전 판정 결과 (④)
def verdicts(rows, pm):
    """판정 대장 행 → 쌍마다 `{match, new, uncertain, 문}` + 애매 줄 `[(표기, 후보, 확신)]` · 개체 · 제목 · 소속 행만."""
    from core.build.also_gate import HOLD_ALSO
    out, unc = {}, {}
    for r in rows or []:
        if r.get("role") not in ("entity", "heading", "belongs"):
            continue
        k = pm.get(r.get("locator"), (None, None))
        c = out.setdefault(k, {"match": 0, "new": 0, "uncertain": 0, "문": 0})
        if r.get("hold") == HOLD_ALSO:
            c["문"] += 1
        elif r.get("verdict") in ("match", "new", "uncertain"):
            c[r["verdict"]] += 1
            if r["verdict"] == "uncertain":
                unc.setdefault(k, []).append((r.get("surface"), (r.get("nearest") or {}).get("canonical"),
                                              r.get("confidence")))
    return out, unc


def moved(rows, pm):
    """**자리가 바뀐 값**(B199 ②) — 판정 전 이름 부모(쌍의 노드 › 소속) ≠ 판정 뒤 실제 이름 부모(붙은 노드 canonical의 부모) ·
    쌍마다 `[{surface, before, after, path}]`(같은 표기 · 같은 두 자리는 한 번 · `n` = 나온 행 수). 좌표 없는 행은 뺀다."""
    from core.state import catalog
    sep = catalog.sep()
    out, seen = {}, {}
    for r in rows or []:
        if r.get("role") != "entity" or r.get("verdict") not in ("match", "new", "uncertain") or not r.get("target"):
            continue
        k = pm.get(r.get("locator"), (None, None))
        up, low = k
        node = low if low and low != "drop" else up
        if node is None:
            continue
        before = sep.join(x for x in (node, r.get("belongs_to")) if x)
        tgt = str(r["target"])
        after = tgt.rsplit(sep, 1)[0] if sep in tgt else None
        if after is None or norm(after) == norm(before):
            continue
        key = (k, norm(r.get("surface") or ""), before, after)
        if key in seen:
            seen[key]["n"] += 1
            continue
        seen[key] = {"surface": r.get("surface"), "before": before, "after": after, "path": r.get("path"), "n": 1}
        out.setdefault(k, []).append(seen[key])
    return out


def verdict_lines(out, unc, indent="   ", moves=None):
    """쌍마다 한 줄 — 값이 0인 쌍은 내지 않는다 · 자리가 바뀐 값의 수(B199 ②) · 애매 줄."""
    lines = []
    for k, c in sorted(out.items(), key=lambda kv: str(kv[0])):
        if not any(c.values()):
            continue
        mv = len((moves or {}).get(k) or [])
        lines.append(f"{indent}{_head(k)} — match {c['match']:,} · new {c['new']:,} · uncertain {c['uncertain']:,}"
                     + (f" · 문에 걸림 {c['문']:,}" if c["문"] else "") + (f" · 자리 바뀜 {mv:,}" if mv else ""))
        for s, near, conf in unc.get(k) or []:
            lines.append(f"{indent}  uncertain {s} ~ {near or '—'}"
                         + (f" · 확신 {conf:.2f}" if isinstance(conf, (int, float)) else ""))
    return lines


# ---------------------------------------------------------------- 구축 입구의 세 자리 (`core/build/entry`가 부른다)
def heading_gate(env, ol, notice, run):
    """**골격 단 — 제목의 판단**(B197 ② · 목차 노드화 바로 뒤 · 추출 전) — 제목 개체 중 겸 단에 설 것의 같은지 판단(여기서 한 번 —
    `_PRE` · 구축이 다시 부르지 않는다) · 처분 줄은 [5/8] 맨 앞 한 표(`plan_extra` — B204 ①) · 끝 줄 「확정한 공정」."""
    from core.build import also_gate
    b = builder(env)
    items = heading_items(b, env, ol)
    if items:
        also_gate.scan(b, items)
    if notice is not None:
        notice({"단계": "확정공정", "줄": pair_line(pairs(b, env, ol, items))})
    run.update(also_items=items, outline=ol)


def drop_after(env, cands, loc2id, run):
    """**버린 제목 아래 청크의 추출 결과를 버린다**(B204 ① — [5/8] 처분 뒤 · 표 · 산문 · 렌즈 한 자리) — 그 청크는 개체 · 관계 · 부착 0
    (`human_drop` — 추출 체크포인트는 그대로)."""
    items = run.get("also_items") or ()
    drop = dropped_locators(builder(env), env, run.get("outline"), items) if items else set()
    if not drop:
        return cands
    loc_of = {cid: loc for loc, cid in loc2id.items()}
    return [{"chunk_id": c["chunk_id"], "entities": [], "relations": [], "attach": [], "human_drop": True}
            if loc_of.get(c["chunk_id"]) in drop else c for c in cands]


def plan_extra(env, candidates, loc2id, outline, run):
    """[5/8] 판정 예고에 더하는 것 — 쌍별 예고(③) · 본문 값의 골격 단 문(② — 판단은 여기서 한 번)."""
    from core.build import also_gate
    b = builder(env)
    loc_of = {cid: loc for loc, cid in loc2id.items()}
    items = run.get("also_items") or ()
    bi = body_items(b, env, candidates, loc_of, outline, items)
    rows = {}                                      # 이름(겸 값) 한 표 — 제목 · 본문 · 같은 표기 · 같은 위 공정은 한 줄(B204 ①)
    for where, its in (("제목", items), ("본문", bi)):
        for r in also_gate.scan(b, its) if its else []:
            k = (norm(r["surface"]), r["up_name"])
            if k in rows:
                rows[k]["rows"] += r["rows"]
                rows[k]["where"] = " · ".join(dict.fromkeys(rows[k]["where"].split(" · ") + [where]))
            else:
                rows[k] = dict(r, where=where)
    from core.state import provisional_hand as PH
    kept = set()                                   # 앞에서 정한 표기(사람 답이 있어 줄 0 — 머리 줄의 수 · B204 ④)
    for it in list(items) + bi:
        p = also_gate.place(b, it["category"], it.get("coord"))
        if p and PH.decided(also_gate._book(b), it["surface"], p["up"]):
            kept.add(norm(it["surface"]))
    return {"쌍별": preview(b, env, candidates, loc_of, outline, items),
            "골격단": list(rows.values()), "앞에서정함": len(kept), "doc_id": env.get("doc_id")}


def pre_write(env, bld, notice, extract_only, run):
    """**쓰기 전 판정 결과**(B197 ④ — 저장 직전 · 표 · 산문 · 렌즈 한 자리) — 쌍마다 match · new · uncertain · 문 + 애매 줄 · 화면이
    `--step`이면 묻는다(`False` = 쓰지 않고 멈춤)."""
    if notice is None or bld is None or bld.ledger is None:
        return None
    pm = pairs(builder(env), env, run.get("outline"), run.get("also_items") or ())
    from core.build import heading as HD
    ol = run.get("outline")
    if ol:                                         # 제목 행의 위치는 제목 경로 — 그 아래 첫 조각의 쌍
        first = HD._first_chunks(env, ol)
        pm.update({h["path"]: pm.get((first.get(h["id"]) or {}).get("source_locator"), (None, None))
                   for h in ol.get("headings") or []})
    out, unc = verdicts(bld.ledger.rows, pm)
    mv = moved(bld.ledger.rows, pm)
    tot = {k: sum(c[k] for c in out.values()) for k in ("match", "new", "uncertain", "문")}
    return notice({"단계": "판정결과", "줄": verdict_lines(out, unc, moves=mv), "합": tot, "판정까지": extract_only,
                   "자리": [dict(x, pair=_head(k)) for k, xs in sorted(mv.items(), key=lambda kv: str(kv[0])) for x in xs],
                   "doc_id": env.get("doc_id")})


def hold_ledger(env, bld, run, doc_hash):
    """쓰지 않고 멈춤 — 확정 대장은 시작 전 그대로 · 이번 판정은 중간 저장으로(다시 넣으면 재생 — LLM 0 · B167 ①과 같은 끝)."""
    from core.build import ledger as LG
    from core.state import store
    name = LG.name_of(env["doc_id"])
    if run.get("ledger0") is None:
        store.path(name).unlink(missing_ok=True)
    else:
        store.write(name, run["ledger0"])
    bld.ledger.save_partial(doc_hash)
