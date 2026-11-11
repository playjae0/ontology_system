# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **골격 칸 검토의 재료**(B196 ③ · 결정 A′ — 쓰기 0) — 좌표 단계(판정 전)와 인입 뒤 한 화면(`ops review`)이 같은 줄을 센다.

| 무엇 | 자리 |
|---|---|
| 머리 줄의 수 일곱 — 공정 표기 · 골격에 있음(LLM 같다) · 문에 걸림 · 쌍 어긋남 · ref 빈 행 · 판단 못 받음 | `review` |
| 문에 걸린 표기(표기 + 들어온 자리 · 행 수 · 판단 · 후보 둘) | `review` · `held_from_queue`(문서를 넘어) |
| 쌍 어긋남(상위 · ref · ref의 실제 위 · 행 수 · 후보 둘) | `review` · `pairs_from_queue` |
| 후보 — 판단이 낸 후보 먼저 · 모자라면 같은 부모 아래 골격 노드를 자식 종류 수 → 행 수 순으로 | `candidates` |

계획은 구축 앞 패스와 같은 함수다(`provisional.plan` · `coord_scan.gate`) — 화면의 수 = 그 문서 구축의 보류 수. 코드에 층 어휘 0.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from core.state import store
from core.state.status import is_live, is_skeleton

#: 후보 수(판단 후보 + 채움)
TOP = 2


def _coord():
    from core.state.bootstrap import COORD_CATEGORY
    return COORD_CATEGORY


class _Sk:
    """좌표 층 골격의 조회 재료 — 부모 표 · 자식 · 행 수 · 자식 종류 수(쓰기 0)."""

    def __init__(self, g=None):
        from core.build.provisional import _parents
        from core.state.bootstrap import coord_layer, load_config, open_graph
        self.g = g or open_graph(coord_layer())
        child = ((load_config(self.g.layer).get("skeleton") or {}).get("relations") or {}).get("child")
        self.pm = _parents(self.g, child)
        from core.build.provisional import _instance
        self.sk = {nid: n for nid, n in self.g.nodes.items()
                   if is_live(n) and n.get("category") == _coord() and is_skeleton(n)}
        self.concepts = {nid for nid, n in self.sk.items() if not _instance(n)}     # 후보는 개념 노드만(극성 인스턴스 0)
        self.by_name = {n["canonical"]: nid for nid, n in self.sk.items()}
        self._kinds = None

    def kids(self, up):
        return [nid for nid in self.concepts if self.pm.get(nid) == up]

    def path(self, nid):
        out, cur = [], nid
        while cur and cur not in out and len(out) < 32:
            out.append(cur)
            cur = self.pm.get(cur)
        return " › ".join((self.g.get(x) or {}).get("canonical", "?") for x in reversed(out))

    def rows(self, nid):
        return sum(1 for p in (self.g.get(nid) or {}).get("provenance") or [] if "#" in str(p))

    def kinds(self, nid):
        """그 노드를 이름 부모(`scope`)로 둔 산 노드의 카테고리 종류 수 — 층 전부."""
        if self._kinds is None:
            from core.state.bootstrap import open_graph
            from router import discover
            acc = {}
            for lay in discover():
                for n in open_graph(lay).nodes.values():
                    if is_live(n) and n.get("scope"):
                        acc.setdefault(n["scope"], set()).add(n.get("category"))
            self._kinds = acc
        return len(self._kinds.get((self.g.get(nid) or {}).get("canonical"), ()))

    def card(self, nid):
        return {"name": self.g.get(nid)["canonical"], "path": self.path(nid), "rows": self.rows(nid), "kinds": self.kinds(nid)}

    def under(self, up):
        """그 노드의 아래(자신 제외) — 골격 노드 id 전부."""
        out, todo = [], [up]
        while todo:
            cur = todo.pop()
            for k in self.kids(cur):
                if k not in out:
                    out.append(k)
                    todo.append(k)
        return out


def candidates(sk, surface, parent, near):
    """**후보 둘**(사용자 규칙 — 추천 순서) — 판단이 낸 후보 먼저 · 모자라면 같은 부모 아래 골격 노드를 자식 종류 수 → 행 수 순으로."""
    picked = [sk.by_name[c] for c in near or [] if c in sk.by_name][:TOP]
    up = sk.by_name.get(parent) if parent else None
    pool = [n for n in (sk.kids(up) if parent else [x for x in sk.concepts if x not in sk.pm]) if n not in picked]
    pool.sort(key=lambda n: (-sk.kinds(n), -sk.rows(n), sk.g.get(n)["canonical"]))
    return [sk.card(n) for n in (picked + pool)[:TOP]]


def pair_candidates(sk, up_surface, ref_surface):
    """쌍 정정의 후보 둘 — 그 상위(골격 노드 하나로 풀릴 때) 아래 골격 노드를 이름 가까운 순으로."""
    from core.dictionary import Dictionary
    from parser.namefold import key
    ups = [n for n in Dictionary.open().lookup(up_surface or "") if n in sk.sk]
    if len(ups) != 1:
        return []
    k = key(ref_surface or "")
    pool = sk.under(ups[0])
    pool.sort(key=lambda n: (-SequenceMatcher(None, k, key(sk.g.get(n)["canonical"].rsplit("::", 1)[-1])).ratio(),
                             sk.g.get(n)["canonical"]))
    return [sk.card(n) for n in pool[:TOP]]


def review(env, outline=None):
    """**좌표 단계의 골격 칸**(B196 ③ — 판정 전 · 쓰기 0) — `{counts, held, pairs, llm_same, lowres}`. 계획 · 쌍 대조는 구축 앞 패스와
    같은 함수(`provisional.plan` · `coord_scan.gate`) — 미리보기 빌더 위에서."""
    from core.build import coord_scan, provisional
    from core.build.build import Builder
    from core.build.build_coord import coord_unjudged
    from core.state.bootstrap import coord_layer, load_config, open_graph
    from parser.namefold import key
    from parser.normalizer import coord_refs
    lay = coord_layer()
    b = Builder(open_graph(lay), load_config(lay), None, env.get("doc_id"), lay)
    b.doc_coord = env.get("doc_coord")
    plan = provisional.plan(b, env, outline)
    pair_rows = coord_scan.gate(env, b)
    sk = _Sk(b.for_category(_coord()).g)
    table = env.get("payload_kind") == "table"
    surf, found, unj, llm, low = set(), set(), set(), {}, {}
    for p in (env.get("records") if table else env.get("chunks")) or []:
        refs = coord_refs(p.get("process_ref"))
        if not refs and table and p.get("process_group"):
            low[p["process_group"]] = low.get(p["process_group"], 0) + 1
        m = p.get("meta") or {}
        for s in refs:
            surf.add(key(s))
            if coord_unjudged(p, s):
                unj.add(key(s))
            elif provisional.look(b, s):
                found.add(key(s))
            if m.get("coord_tag_source") == "live" and m.get("coord_tag_from"):
                x = llm.setdefault((m["coord_tag_from"], s), 0)
                llm[(m["coord_tag_from"], s)] = x + 1
    held = [dict(e, candidates=candidates(sk, e["surface"], e.get("up_name"), e.get("near")))
            for e in plan if e.get("hold") == provisional.HOLD_HUMAN]
    pairs = {}
    for r in pair_rows:
        if r["answer"] == "ack":
            continue
        k = (r["kind"], r["pair"][0], r["pair"][1])
        x = pairs.setdefault(k, {"kind": r["kind"], "up": r["pair"][0], "ref": r["pair"][1], "surface": r["surface"],
                                 "rows": 0, "answer": r["answer"],
                                 "real_up": sk.path(sk.pm.get(sk.by_name.get(r["pair"][1]))) if sk.by_name.get(r["pair"][1]) else "—",
                                 "candidates": pair_candidates(sk, r["pair"][0], r["surface"])})
        x["rows"] += 1
    pairs = [p for p in pairs.values() if p["answer"] is None]
    counts = {"표기": len(surf), "골격": len(found), "LLM 같다": len({k[0] for k in llm}),
              "문": len(held), "문 행": sum(e["rows"] for e in held),
              "쌍": len(pairs), "쌍 행": sum(p["rows"] for p in pairs),
              "ref 빈 행": sum(low.values()), "판단 못 받음": len(unj)}
    return {"counts": counts, "held": held, "pairs": pairs, "plan": plan,
            "llm_same": [{"from": f, "to": t, "rows": n} for (f, t), n in sorted(llm.items())],
            "lowres": sorted(low.items())}


def head_line(c):
    """`골격 칸 — 공정 표기 n종: 골격에 있음 a(LLM 같다 b) · 문에 걸림 c종(d행) · 쌍 어긋남 e쌍(f행) · ref 빈 행 g(상위로 붙음) · 판단 못 받음 h`."""
    return (f"골격 칸 — 공정 표기 {c['표기']:,}종: 골격에 있음 {c['골격']:,}(LLM 같다 {c['LLM 같다']:,}) · 문에 걸림 {c['문']:,}종"
            f"({c['문 행']:,}행) · 쌍 어긋남 {c['쌍']:,}쌍({c['쌍 행']:,}행) · ref 빈 행 {c['ref 빈 행']:,}(상위로 붙음) · "
            f"판단 못 받음 {c['판단 못 받음']:,}")


# ---------------------------------------------------------------- 인입 뒤 — 큐에서 (문서를 넘어)
def held_from_queue():
    """**문에 걸린 표기**(문서를 넘어 — 같은 표기 · 같은 부모는 한 줄 · 행 수는 합) — 사람 답이 아직 없는 열린 보류만."""
    from core.state import provisional_hand as PH
    from parser.namefold import key
    book, sk, out = PH.decisions(), _Sk(), {}
    for x in store.read(store.QUEUE, []):
        pl = x.get("payload") or {}
        gi = pl.get("gate")
        if x.get("kind") != "orphan_anchor" or x.get("resolution") or gi is None or pl.get("category") != _coord():
            continue
        if PH.decided(book, pl.get("surface"), gi.get("parent")):
            continue
        k = (key(pl.get("surface") or ""), gi.get("parent"))
        r = out.setdefault(k, {"kind": "gate", "surface": pl["surface"], "up_name": gi.get("parent"), "rows": 0, "docs": [],
                               "answer": gi.get("answer"), "near": gi.get("near") or [], "also": pl.get("also")})
        r["rows"] += sum(1 for it in pl.get("items") or [pl] if not it.get("follow")) or 1   # 딸린 값(B197 ①)은 행에 들지 않는다
        if x.get("doc_id") not in r["docs"]:
            r["docs"].append(x.get("doc_id"))
    rows = sorted(out.values(), key=lambda r: (-r["rows"], r["surface"]))
    for r in rows:
        r["candidates"] = candidates(sk, r["surface"], r["up_name"], r["near"])
    return rows


def pairs_from_queue():
    """**쌍 어긋남**(문서를 넘어 — 쌍 하나는 한 줄) — 사람 답(확인 · 정정 · drop)이 없는 열린 보류만."""
    from core.state import coord_acks
    book, sk, out = coord_acks.answers(), _Sk(), {}
    for x in store.read(store.QUEUE, []):
        pl = x.get("payload") or {}
        pr = pl.get("pair")
        if x.get("kind") != "orphan_anchor" or x.get("resolution") or pr is None:
            continue
        if coord_acks.key(pr["kind"], (pr["up"], pr["ref"])) in book:
            continue
        r = out.setdefault((pr["kind"], pr["up"], pr["ref"]), {
            "kind": pr["kind"], "up": pr["up"], "ref": pr["ref"], "surface": pl.get("surface"), "rows": 0, "docs": [],
            "real_up": sk.path(sk.pm.get(sk.by_name.get(pr["ref"]))) if sk.by_name.get(pr["ref"]) else "—",
            "candidates": pair_candidates(sk, pr["up"], pl.get("surface"))})
        r["rows"] += int(pl.get("rows") or 1)
        if x.get("doc_id") not in r["docs"]:
            r["docs"].append(x.get("doc_id"))
    return sorted(out.values(), key=lambda r: (-r["rows"], r["up"], r["ref"]))
