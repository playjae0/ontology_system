# -*- coding: utf-8 -*-
"""칸 3.3 — **사람 후보**(B140) — 추출 뒤 · 판정 전(LLM 0 · 그래프 쓰기 0)에 **이름 없는 대상**을 세고, 사람의 기록을 추출
후보에 한 줄로 보탠다 — 노드는 평소 길(`Builder.resolve_at_home`)이 세운다(노드를 만드는 연산을 새로 두지 않는다 · P2).

    Board(env, cands, cfg, graph, layer, loc2id, outline)   그 문서의 셈 · 상세(위 노드 · 카테고리 · 미리보기 · 같은 것 대상) — 읽기만
    apply(env, cands, cfg, loc2id)                           기록 → 추출 후보(메모리 — 추출 체크포인트는 바이트 그대로)
    aliases(b, doc_id, after)                                같은 것 → 별칭 등재(`ops alias`와 같은 검사 · 같은 등재 함수)
    summary(rows, doc_id)                                    인입 끝 한 줄의 재료

**이름 없는 대상** = 소속 이름 · 관계 끝점 가운데 이 문서 개체 표기 · 제목 개체 · 골격 · 사전으로 풀리지 않고(`belongs.lookup` —
구축의 끝점 조회와 한 함수) 구축이 새로 세울 소속(카테고리를 달고 좌표 있는 청크에서 나온 것)도 아닌 이름. 그 청크(본문 · 맥락
줄 · 부착 후보)에 없는 이름은 더할 수 없다(꼬리 · `source_of`). 붙이는 일은 지금 장치다 — 이 문서는 구축이 · 다른 문서의 고아는
재연결이. 골격은 건드리지 않는다 · 층 어휘 0(카테고리 · 관계 이름은 config가 말한다).
"""
from __future__ import annotations

from collections import Counter

from core.build import belongs, extract_ctx, gate
from core.state import human_candidates as HC, store
from core.state.ids import norm
from parser.normalizer import null_marker

#: 사람 후보의 표지(추출 후보 줄 · 대장 행의 `by` — 구축 `core/build/prose`가 이 이름으로 읽는다)
HUMAN = "사람"
#: 예고 목록의 줄 수(`-v`면 전부)
TOP = 10


def _src_of(env, loc2id):
    by_loc = {c["source_locator"]: c for c in env.get("chunks") or []}
    return {cid: by_loc.get(loc) or {} for loc, cid in (loc2id or {}).items()}


def _uses(cand):
    """그 청크 후보에서 이름이 쓰인 자리 — `[(이름, 종류, 재료)]`(소속 · 관계 끝점 · 사람 후보 줄은 빼고)."""
    out = []
    for e in cand.get("entities") or []:
        bel = e.get("belongs_to")
        if e.get("by") != HUMAN and bel and bel.get("name") and not null_marker(bel["name"]):
            out.append((bel["name"], "소속", {"entity": e, "cat": bel.get("category")}))
    for r in cand.get("relations") or []:
        for side in ("src", "dst"):
            if r.get(side):
                out.append((r[side], "관계", {"rel": r, "side": side}))
    return out


class Board:
    """그 문서의 사람 후보 판 — 셈 · 상세 · 미리보기는 읽기만 한다(조회 빌더는 저장하지 않는다 · 큐 0 · LLM 0)."""

    def __init__(self, env, cands, cfg, graph, layer, loc2id, outline=None):
        from core.build.build import Builder
        self.env, self.cfg, self.layer, self.ol = env, cfg, layer, outline
        self.doc_id = env["doc_id"]
        self.cands = [c for c in cands if not c.get("failed")]
        self.b = Builder(graph, cfg, None, self.doc_id, layer)
        self.doc = extract_ctx.doc_info(env)
        self.src = _src_of(env, loc2id)
        heads = [h["target"]["name"] for h in (outline or {}).get("headings") or [] if h.get("target")]
        self.local = {norm(e["surface"]) for c in self.cands for e in c.get("entities") or []
                      if e.get("surface") and e.get("by") != HUMAN} | {norm(h) for h in heads}
        self._coords = {}

    # ---------------------------------------------------------------- 셈
    def coord(self, cid):
        """그 청크의 주 좌표 `(id, 그래프)` — 구축과 같은 해소(큐 0)."""
        if cid not in self._coords:
            from core.build.heading import _kw
            src = self.src.get(cid) or {}
            ref, ref_g, _p, _pol = _kw(self.b, src, f"{self.doc_id}#{src.get('source_locator')}")
            self._coords[cid] = (ref, ref_g)
        return self._coords[cid]

    def known(self, name, cat, cid):
        """구축이 이 이름을 푸는가 — 이 문서 개체 · 제목 개체 · 골격 · 사전(`belongs.lookup`) · 새로 세울 소속."""
        if norm(name) in self.local:
            return True
        ref = self.coord(cid)[0]
        if belongs.lookup(self.b, name, cat, coord=ref, src=self.src.get(cid), doc=self.doc):
            return True
        return bool(cat and cat in (self.cfg.get("categories") or {}) and ref)

    def rows(self):
        """`(목록, 꼬리)` — 목록은 잃을 것이 많은 차례 `[{name, 소속, 소실, 관계, 고아 {문서: 행}, 청크, cats, items, rec}]` ·
        꼬리는 그 청크에 없는 이름 `{종, 관계}`."""
        recs = {norm(r["name"]): r for r in HC.of(self.doc_id)}
        found, tail = {}, {}
        for c in self.cands:
            cid = c["chunk_id"]
            for name, kind, mat in _uses(c):
                if self.known(name, mat.get("cat"), cid):
                    continue
                here = belongs.source_of(name, self.src.get(cid) or {}, self.doc) is not None
                it = (found if here else tail).setdefault(norm(name), {
                    "name": name, "소속": 0, "소실": 0, "관계": 0, "청크": set(), "cats": Counter(), "items": []})
                it[kind] += 1
                it["청크"].add(cid)
                it["items"].append((kind, cid, mat))
                if kind == "소속":
                    it["소실"] += 0 if self.coord(cid)[0] else 1
                    if mat.get("cat"):
                        it["cats"][mat["cat"]] += 1
        orph = {}
        for x in store.read(store.QUEUE, []):
            pl = x.get("payload") or {}
            if x.get("kind") == "orphan_attach" and x.get("doc_id") != self.doc_id and pl.get("key") in found:
                orph.setdefault(pl["key"], Counter())[x.get("doc_id")] += int(pl.get("rows") or 1)
        out = []
        for k, it in found.items():
            it.update(고아=dict(orph.get(k) or {}), rec=recs.get(k))
            out.append(it)
        out.sort(key=lambda x: (-(x["소속"] + x["관계"] + sum(x["고아"].values())), x["name"]))
        tl = [v for k, v in tail.items() if k not in found]
        return out, {"종": len(tl), "관계": sum(v["관계"] for v in tl)}

    # ---------------------------------------------------------------- 상세
    def uppers(self, it):
        """위 노드 후보 — 그 청크들 위의 제목 개체(가까운 것부터) → 청크 좌표(골격) · 많이 나온 차례 `[{name, category, kind, n}]`."""
        from core.build import outline as OL
        from core.state.bootstrap import COORD_CATEGORY
        heads, coords = {}, Counter()
        for cid in it["청크"]:
            loc = (self.src.get(cid) or {}).get("source_locator")
            for rank, h in enumerate(OL.heading_candidates(self.ol, loc)):
                r = heads.setdefault(norm(h["name"]), {"name": h["name"], "category": h["category"], "kind": "제목 개체",
                                                       "n": 0, "rank": rank})
                r["n"], r["rank"] = r["n"] + 1, min(r["rank"], rank)
            ref, ref_g = self.coord(cid)
            if ref:
                coords[(ref_g.get(ref) or {}).get("canonical")] += 1
        out = sorted(heads.values(), key=lambda r: (r["rank"], -r["n"], r["name"]))
        out += [{"name": n, "category": COORD_CATEGORY, "kind": "골격", "n": k}
                for n, k in sorted(coords.items(), key=lambda x: (-x[1], x[0])) if n]
        return [{k: v for k, v in r.items() if k != "rank"} for r in out]

    def direct(self, name):
        """「직접」 친 위 노드 — 골격 이름 또는 이미 있는 노드 하나 · 아니면 `(None, 이유)`."""
        hit = belongs.lookup(self.b, name)
        if not hit:
            return None, f"'{name}' — 골격에도 사전에도 없는 이름이다(이미 있는 노드나 골격 이름만)"
        kind, nid, g = hit
        n = g.get(nid) or {}
        return {"name": n.get("canonical"), "category": n.get("category"), "layer": g.layer,
                "kind": "골격" if kind == belongs.SKELETON else "노드"}, None

    def categories(self):
        """고를 수 있는 카테고리 — 추출이 고르는 목록에서 좌표 카테고리를 뺀 것(이름 차례 그대로)."""
        from core.build.extract import categories_with_also
        from core.state.bootstrap import COORD_CATEGORY
        return [c for c in categories_with_also(self.cfg) if c != COORD_CATEGORY]

    def recommend(self, it):
        """`(위 노드, 카테고리)` 추천 — 카테고리 = 추출이 그 이름의 소속에 단 것 가운데 가장 많은 것(없으면 목록 첫째) · 위 노드 =
        그 카테고리와 매핑이 있는 첫 후보(없으면 None)."""
        cats = self.categories()
        cat = next((c for c, _n in it["cats"].most_common() if c in cats), cats[0] if cats else None)
        up = next((u for u in self.uppers(it) if self.why_not(u, cat) is None), None)
        return up, cat

    def why_not(self, upper, cat):
        """그 조합을 고를 수 없는 이유 — 좌표 카테고리 · 카테고리쌍 매핑 없음(`belongs.edge_of`) · 고를 수 있으면 None."""
        if cat not in self.categories():
            return f"'{cat}'는 고를 수 없는 카테고리다(좌표 카테고리 · 목록 밖)"
        if upper is None:
            return "위 노드가 없다"
        rel, _fwd = belongs.edge_of(self.cfg, upper.get("category"), cat)
        return None if rel else f"카테고리쌍 매핑 없음({upper.get('category')} · {cat}) — 이 위 노드에 붙일 관계가 없다"

    def preview(self, it, upper, cat):
        """상세 화면의 재료 — `{node, belongs [(표기[카테고리] = 값, 지금 자리)], relations [(줄, 결말)], orphans {문서: 행}}`."""
        from core.build.build import entity_key
        from core.build.naming import name_parent
        cid = sorted(it["청크"])[0]
        ref, ref_g = self.coord(cid)
        cp = (ref_g.get(ref) or {}).get("canonical") if ref else None
        if upper["kind"] == "골격":
            parent = upper["name"]
        else:
            owner = (upper["name"] if upper["kind"] == "노드" else
                     entity_key(upper["name"], upper["category"], self.cfg, parent_canonical=cp)[0])
            parent = name_parent(cat, owner, cp, self.cfg)
        node = entity_key(it["name"], cat, self.cfg, parent_canonical=parent)[0]
        bel, rel = [], []
        for kind, ccid, mat in it["items"]:
            if kind == "소속":
                e = mat["entity"]
                v = f" = {e['value']}" if e.get("value") else ""
                bel.append((f"{e['surface']}[{e.get('category')}]{v}", self._place(ccid)))
            else:
                rel.append(self._rel_fate(mat["rel"], mat["side"], cat, ccid))
        return {"node": node, "belongs": bel, "relations": rel, "orphans": dict(it["고아"])}

    def _place(self, cid):
        """그 청크 개체의 지금 자리 — 좌표가 없으면 개체 소실 · 있으면 임시로 붙는 자리(가까운 제목 개체 → 좌표)."""
        from core.build import outline as OL
        ref, ref_g = self.coord(cid)
        if not ref:
            return "개체 소실(좌표 없는 청크)"
        hs = OL.heading_candidates(self.ol, (self.src.get(cid) or {}).get("source_locator"))
        return f"임시 — {hs[0]['name'] if hs else (ref_g.get(ref) or {}).get('canonical')}"

    def _rel_fate(self, r, side, cat, cid):
        """관계 한 줄의 결말 미리보기 — 붙음 · 상대도 없음 · 막힘(게이트 결정적 판정 `gate.judge`)."""
        other = r["dst" if side == "src" else "src"]
        line = f"{r['src']} -{r['rel']}-> {r['dst']}"
        ocat = self._cat_of(other, cid)
        if ocat is None:
            return line, "상대도 없음 — 그것도 살리면 붙음"
        sc, dc = (cat, ocat) if side == "src" else (ocat, cat)
        verdict = gate.judge(sc, r["rel"], dc, self.cfg, gate.PATH_EXTRACT)[0]
        return line, ("지금 버림 → 붙음" if verdict == gate.COMMIT else f"막힘 — 게이트 {verdict}({sc} · {dc})")

    def _cat_of(self, name, cid):
        for c in self.cands:
            if c["chunk_id"] == cid:
                for e in c.get("entities") or []:
                    if norm(e.get("surface") or "") == norm(name):
                        return e.get("category")
        hit = belongs.lookup(self.b, name, coord=self.coord(cid)[0], src=self.src.get(cid), doc=self.doc)
        return (hit[2].get(hit[1]) or {}).get("category") if hit else None

    def same_targets(self, it):
        """같은 것의 대상 — 이번에 더한 이름(새것 기록) · 사전에서 라틴 대소문자를 접어 맞는 노드 `[{name, layer, category}]`."""
        out = [{"name": r["name"], "layer": None, "category": r.get("category"), "new": True}
               for r in HC.of(self.doc_id) if r.get("kind") == HC.NEW and norm(r["name"]) != norm(it["name"])]
        for x in set(self.b.dict.lookup(it["name"])):
            g = belongs._home(self.b, x)
            n = g.get(x) if g is not None else None
            if n and n.get("status") != "deleted":
                out.append({"name": n["canonical"], "layer": g.layer, "category": n["category"]})
        return out

    def same_check(self, it, target):
        """같은 것의 검사 — `ops alias` 미리보기와 같은 함수(같은 자리 다른 노드에 붙은 표기면 이유) · 새것 대상이면 구축이 잰다."""
        if target.get("new"):
            return None
        from core.state import ops_mark
        hit = belongs.lookup(self.b, target["name"], target.get("category"))
        if not hit:
            return f"대상 '{target['name']}'이 없다"
        _k, nid, g = hit
        clash = ops_mark.alias_clash(self.b.dict, lambda x: (belongs._home(self.b, x) or g).get(x), nid, g.get(nid),
                                     it["name"], self.cfg)
        return (f"'{it['name']}'는 이미 같은 자리의 다른 노드에 붙어 있다 — '{clash[1]['canonical']}'" if clash else None)


# ---------------------------------------------------------------- 적용 (구축 — 추출 뒤 관문 다음 한 자리)
def apply(env, cands, cfg, loc2id):
    """기록 → 추출 후보 — 새것은 그 이름이 쓰인 청크(그 청크에 이름이 있을 때만)마다 개체 후보 한 줄(표지 사람 · 위 노드는 소속) ·
    그 청크에 같은 표기의 개체가 있으면 보태지 않는다 · 카테고리가 이 층 어휘 밖이면 건너뛴다(렌즈). 돌려주는 것은 새 목록(바뀐
    청크만 사본 — 추출 체크포인트는 그대로)."""
    recs = [r for r in HC.of(env["doc_id"]) if r.get("kind") == HC.NEW
            and r.get("category") in (cfg.get("categories") or {})]
    if not recs:
        return cands
    doc, src = extract_ctx.doc_info(env), _src_of(env, loc2id)
    out = []
    for c in cands:
        names = {norm(n) for n, _k, _m in _uses(c)}
        have = {norm(e.get("surface") or "") for e in c.get("entities") or []}
        add = [{"surface": r["name"], "category": r["category"], "by": HUMAN,
                "belongs_to": {"name": r["upper"]["name"], "category": r["upper"].get("category"), "from": HUMAN}}
               for r in recs if norm(r["name"]) in names and norm(r["name"]) not in have
               and belongs.source_of(r["name"], src.get(c["chunk_id"]) or {}, doc) is not None]
        out.append({**c, "entities": add + list(c.get("entities") or [])} if add else c)
    return out


def aliases(b, doc_id, after=False):
    """같은 것 → 별칭 — 대상 노드가 있으면 등재(`ops alias`의 검사 · 키 조립 · 등재 함수 그대로 · 출처 사람 · 문서) · 대상이
    이번 기록의 새것이면 그 노드가 선 뒤(`after`) · 끝내 없거나 검사에 걸리면 결함 한 줄. 돌려주는 것은 등재한 수."""
    from core.state import ops_mark
    done, seen = 0, b.__dict__.setdefault("_human_aliased", set())     # 이 빌드에서 이미 단 것(앞 · 뒤 두 번 부른다)
    for r in HC.of(doc_id):
        if r.get("kind") != HC.SAME or norm(r["name"]) in seen:
            continue
        t = r.get("target") or {}
        hit = belongs.lookup(b, t.get("name"), t.get("category"))
        if not hit:
            if after:
                store.append_defect(f"{doc_id}: 사람 후보 같은 것 — 대상 '{t.get('name')}'이 없다 → '{r['name']}' 등재 0")
            continue
        _k, nid, g = hit
        eb = b.for_layer(g.layer)
        node = g.get(nid)
        clash = ops_mark.alias_clash(b.dict, lambda x: (belongs._home(b, x) or g).get(x), nid, node, r["name"], eb.cfg)
        if clash:
            store.append_defect(f"{doc_id}: 사람 후보 같은 것 — '{r['name']}'는 같은 자리의 다른 노드 "
                                f"'{clash[1]['canonical']}'에 붙어 있다 → 등재 0")
            continue
        key, _parent = ops_mark.alias_key(node, r["name"], eb.cfg)
        eb._register(r["name"], nid, f"op:alias:{r.get('by') or HC.BY}", key=key)
        b.buffer[norm(r["name"])] = nid
        seen.add(norm(r["name"]))
        done += 1
    return done


def summary(rows, doc_id):
    """인입 끝 한 줄의 재료 — `{새것, 새 노드, 있는 노드로, 못 섬, 같은 것, 소속 붙음, 관계 붙음}` · 기록이 없으면 None."""
    recs = HC.of(doc_id)
    if not recs:
        return None
    mine = {}
    for r in rows or []:
        if r.get("role") == "entity" and r.get("by") == HUMAN:
            mine.setdefault(norm(r["surface"]), r)
    names = {norm(r["name"]) for r in recs}
    tail = lambda c: norm(str(c or "").split("::")[-1])               # noqa: E731
    new = [mine.get(norm(r["name"])) or {} for r in recs if r.get("kind") == HC.NEW]
    return {"새것": len(new),
            "새 노드": sum(1 for r in new if r.get("node_id") and r.get("verdict") in ("new", "uncertain")),
            "있는 노드로": sum(1 for r in new if r.get("node_id") and r.get("verdict") == "match"),
            "못 섬": sum(1 for r in new if not r.get("node_id")),           # 대장 행이 없거나(그 청크에 이름 없음) 노드가 서지 않았다
            "같은 것": sum(1 for r in recs if r.get("kind") == HC.SAME),
            "소속 붙음": sum(1 for r in rows or [] if r.get("by") != HUMAN and norm(r.get("belongs_to") or "") in names
                          and any(str(a.get("path") or "").startswith("소속") for a in r.get("attached") or [])),
            "관계 붙음": sum(1 for r in rows or [] for a in r.get("attached") or []
                          if a.get("path") == "관계" and tail(a.get("other")) in names)}


def waiting():
    """사람 후보 이름(모든 문서)을 기다리는 고아 행 수 — 마무리 재연결 앞뒤로 센다(붙은 수 = 앞 − 뒤)."""
    names = HC.names()
    return sum(int((x.get("payload") or {}).get("rows") or 1) for x in store.read(store.QUEUE, [])
               if x.get("kind") == "orphan_attach" and (x.get("payload") or {}).get("key") in names)
