# -*- coding: utf-8 -*-
"""칸 0.3 — **동의어 점검 · 사람 승인 → 반영**(B200 ④ · 결정 `결정_동의어_점검.md` §2 7 · 8).

| 처분 | seed 별칭(골격 `ALIASES`) | 대장 별칭 | 보류 표기(후보) |
|---|---|---|---|
| 지움 | `ALIASES`에서 뺀다(`provisional_hand.drop_alias`) → 골격 심기(노드 · 사전은 `bootstrap.sweep_seed`가 걷는다) | `ops_mark.alias_reject` | — |
| 다른 노드로 | 빼고 · 대상이 골격 노드면 `ALIASES`에 더한다(`add_alias`) · 아니면 `ops alias` | `alias_reject` + 대상에 `ops alias` | — |
| 유지 | 판정 목록에 「사람 유지」 | 같다 | — |
| 후보 받기 | — | — | 대상이 골격 노드면 `ALIASES`에 더한다 · 아니면 `ops alias` |

  · **행위자 필수** · 처분마다 판정 목록(별칭 검토 갈래)에 사람 처분 · 사람 판단 기록(`ops_log`)에 이름으로 — 대장 손(`alias_reject` ·
    `ops alias`)은 제 기록 그대로(재구축 뒤 `ops replay`가 다시 한다) · 골격 파일 손은 파일에 남는다(재생 0 — `oplog.SKIP`) ·
    「유지」는 `alias:keep`(재생이 판정 목록에 다시 적는다)
  · **낡은 승인 거르기** — 승인 묶음에 그 화면을 만든 때의 판(`stamp` — 골격 파일 · 대장 별칭 갈래의 지문)을 싣는다 · 지금과
    다르면 지금 점검에 없는 짝(골격 · 대장이 바뀌어 사라진 짝)만 「골격이 바뀜 — 다시 점검」으로 빼고 나머지만 한다
  · 끝 — `지움 n · 옮김 m · 유지 k · 받음 j · 다시 붙일 행 r(문서 …)` + 그 문서의 원본 다시 넣기 한 줄(승인만으로 붙은 행은
    떨어지지 않는다 — 그래프를 바꾸는 긴 일은 CLI)

코드에 층 어휘 0.
"""
from __future__ import annotations

import hashlib

from core.state import alias_book as AB, alias_review as AR, store, surface_book as SB

DROP, MOVE, KEEP, TAKE = "지움", "다른 노드로", "유지", "후보 받기"
DISPOSITIONS = (DROP, MOVE, KEEP, TAKE)
STALE = "골격이 바뀜 — 다시 점검"
OP_KEEP, OP_SKELETON = "alias:keep", "alias:skeleton"


class Refused(Exception):
    """승인 거부 — 문면에 까닭."""


def _files():
    """골격 파일을 가진 층마다 `{층: 파일}`(config `skeleton.source` — 인라인 골격은 쓸 자리가 없다)."""
    from core.state import provisional_hand as PH
    from router import discover
    out = {}
    for lay in discover():
        try:
            out[lay] = PH.skeleton_file(layer=lay)[1]
        except Exception:                                   # noqa: BLE001 — 골격 없는 층 · 인라인 골격
            continue
    return out


def stamp():
    """지금 판 — 층마다 골격 파일 · 대장 별칭 갈래의 지문(화면을 만들 때 싣고 · 승인 때 대조한다)."""
    sk = {lay: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for lay, p in sorted(_files().items()) if p.is_file()}
    return {"skeleton": sk, "book": store.content_fp(SB.alias_rows())}


def _still(it):
    """화면의 짝이 지금 파일에도 그대로인가(낡은 승인 거르기) — seed 별칭은 골격 파일 `ALIASES`(그 노드의 키) 또는 짧은 이름 ·
    대장 별칭은 대장의 살아 있음 · 보류 표기는 그대로(큐가 답한다)."""
    from core.state import catalog
    if it["kind"] != AR.PAIR:
        return True
    t = it["target"]
    if it.get("source") != "골격":
        r = AB.AliasBook.open().get(it["surface"], t)
        return bool(r and r.get("status") == AB.LIVE)
    p = _files().get(t.get("layer"))
    if p is None or not p.is_file():
        return False
    import json
    al = (json.loads(p.read_text(encoding="utf-8")).get("ALIASES") or {})
    short = str(t.get("canonical")).split(catalog.sep())[-1]
    return it["surface"] == short or any(it["surface"] in (al.get(k) or []) for k in (t.get("canonical"), short))


def _skeleton_node(w, t):
    """대상 이름 → 산 골격 노드(없으면 None)."""
    from core.state.ids import norm
    from core.state.status import is_live
    for _l, n in w.nodes():
        if is_live(n) and n.get("status") == "seed" and n.get("category") == t.get("category") \
                and norm(n["canonical"]) == norm(t.get("canonical") or ""):
            return n
    return None


def _by_canonical(w, canonical, category=None):
    from core.state.ids import norm
    from core.state.status import is_live
    hit = [n for _l, n in w.nodes() if is_live(n) and norm(n["canonical"]) == norm(canonical or "")
           and (category is None or n.get("category") == category)]
    return hit[0] if len(hit) == 1 else None


def approve(decisions, actor, made=None):
    """승인 묶음 하나 — `decisions = [{surface, target: {layer, canonical, category}, kind, disposition, to?}]` · `made` = 화면의 판.
    돌려주는 것은 `{done: {처분: 수}, stale: [표기], refused: [(표기, 까닭)], rows, docs, line, next}`."""
    from core.state import ops, ops_mark, provisional_hand as PH
    from core.state.world import World
    if not (actor or "").strip():
        raise Refused("행위자 이름이 없다 — 승인은 이름으로 남는다")
    its = {it["k"]: it for it in AR.items()}
    stale_check = made is not None and made != stamp()
    out = {"done": {d: 0 for d in DISPOSITIONS}, "stale": [], "refused": [], "rows": 0, "docs": []}
    rv = AR.Review.open()
    replant = set()
    for d in decisions:
        s, t, how = d.get("surface"), d.get("target") or {}, d.get("disposition")
        k = AR.key(s, t)
        it = its.get(k)
        if how not in DISPOSITIONS:
            out["refused"].append((s, f"처분 밖 — '{how}'"))
            continue
        if it is None or (stale_check and not _still(it)):
            out["stale" if stale_check else "refused"].append(s if stale_check else (s, "지금 점검에 없는 짝"))
            continue
        w = World()
        try:
            replant |= _one(w, it, how, d.get("to"), actor, ops, ops_mark, PH)
        except (ops.OpRefused, PH.Refused, Refused) as e:
            out["refused"].append((s, str(e).splitlines()[0]))
            continue
        out["done"][how] += 1
        if how in (DROP, MOVE):
            out["rows"] += int(it.get("rows") or 0)
            out["docs"] += [x for x in it.get("docs") or [] if x not in out["docs"]]
        rv.put(k, s, t, AR._where(it), it["kind"],
               human={"disposition": how, "to": d.get("to"), "actor": actor, "at": store._now()})
    for lay in sorted(replant):                             # 고친 골격 파일의 층마다 골격 심기 한 번(걷기는 `bootstrap.sweep_seed`)
        PH._replant(lay)
    rv.save()
    out["line"], out["next"] = _end_lines(out)
    return out


def _one(w, it, how, to, actor, ops, ops_mark, PH):
    """처분 하나 — 돌려주는 것은 골격 파일을 고친 층의 집합(끝에 층마다 골격 심기 한 번)."""
    s, t = it["surface"], it["target"]
    seed = it["kind"] == AR.PAIR and it.get("source") == "골격"
    if how == KEEP:
        ops.log_op(OP_KEEP, actor, [it.get("node_id")] if it.get("node_id") else [], "",
                   {"surface": s}, {"node": t})
        return set()
    if how in (MOVE, TAKE) and not to:
        raise Refused("옮길 노드(canonical)를 달라")
    if (how == TAKE and it["kind"] != AR.CANDIDATE) or (how in (DROP, MOVE) and it["kind"] != AR.PAIR):
        raise Refused(f"'{how}'는 {'보류 표기' if how == TAKE else '붙은 별칭'}의 처분이다")
    touched = set()
    if how in (DROP, MOVE):
        if seed:
            lay, _p, hit = PH.drop_alias(t["canonical"], s, layer=t.get("layer"))
            if not hit:
                raise Refused(f"골격 ALIASES에 '{s}'({t['canonical']})가 없다 — 짧은 이름이거나 이미 고쳐졌다")
            ops.log_op(OP_SKELETON, actor, [it.get("node_id")], "", {"surface": s, "how": "drop"}, {"node": t})
            touched.add(lay)
        else:
            ops_mark.alias_reject(t["layer"], t["canonical"], s, actor, reason="동의어 점검")
    if how in (MOVE, TAKE):
        sk = _skeleton_node(w, {"category": t.get("category"), "canonical": to})
        inline = False
        if sk is not None:
            try:
                lay, _p = PH.add_alias(sk["canonical"], s, layer=sk.get("layer"))
                ops.log_op(OP_SKELETON, actor, [sk["id"]], "", {"surface": s, "how": "add"}, {"node": AB.name(sk)})
                touched.add(lay)
            except PH.Refused:                              # 골격이 config 인라인 — `ALIASES` 자리가 없다 → 사람이 잇는 손(대장)
                inline = True
        if sk is not None and inline:
            ops_mark.alias(sk.get("layer"), sk["id"], s, actor, reason="동의어 점검")
        elif sk is None:
            n = _by_canonical(w, to)
            if n is None:
                raise Refused(f"옮길 노드 '{to}'가 없거나 여럿이다")
            ops_mark.alias(n.get("layer"), n["id"], s, actor, reason="동의어 점검")
    return touched


def _end_lines(out):
    d = out["done"]
    line = (f"지움 {d[DROP]:,} · 옮김 {d[MOVE]:,} · 유지 {d[KEEP]:,} · 받음 {d[TAKE]:,}"
            + (f" · 다시 붙일 행 {out['rows']:,}(문서 {' · '.join(out['docs'])})" if out["rows"] else "")
            + (f" · {STALE} {len(out['stale']):,}" if out["stale"] else "")
            + (f" · 거부 {len(out['refused']):,}" if out["refused"] else ""))
    nxt = None
    if out["rows"]:
        reg = store.read(store.DOC_REGISTRY, {}) or {}
        srcs = [str((reg.get(x) or {}).get("source_path") or f"<{x}의 원본>") for x in out["docs"]]
        nxt = "그 문서를 다시 넣는다: python run.py ingest-file " + " ".join(srcs)
    return line, nxt

