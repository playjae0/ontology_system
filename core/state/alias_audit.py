# -*- coding: utf-8 -*-
"""칸 0.3 — **동의어 점검 · 규칙**(B200 ① · 결정 `결정_동의어_점검.md` §2 2) — LLM 없음 · 쓰기 0.

짝 = (표기, 대상 노드) · 대상 = **seed 별칭**(골격 `ALIASES` · 좌표 학습 승격 — `alias_book.is_seed`) + **표기 대장 별칭 갈래의
살아 있음** · 층 전부(노드가 사는 그래프). 짝마다:

  · 출처 — 골격 | 대장 출처(`alias_book.SOURCES`)
  · 공유 — 같은 표기(`ids.norm`)를 쓰는 다른 노드
  · 겹침 의심 — 이름 대조 키(`parser.namefold.key` — 공백 · 대소문자 · 전각)는 같은데 글자가 다른 표기가 다른 대상에 ·
    사전의 그 표기 키가 이 노드를 가리키지 않는다(사전 어긋남)
  · **붙은 행** — 이 노드에 닿는 출처(노드 자신 + 이 노드를 끝점으로 하는 엣지 — 층 전부)의 `문서#위치`에서 그 봉투
    (`paths.parsed("<문서>.json")`)의 그 행 칸 값이 그 표기면 그 행이 그 표기로 붙었다 · 표본 둘(문서#위치 · 그 행의 다른 칸) ·
    0이면 **죽은 별칭** · 봉투를 못 읽은 문서는 「모른다」(지어내지 않는다 — 극성이 봉투를 읽는 길과 같다 · B199 ⑤)

**보류 표기**(별칭 후보) — 지금 큐의 `orphan_anchor` 중 사람 판단 없는 것(목록 밖 · 표기 모호)의 표기 · 행 수 큰 차례.

코드에 층 어휘 0 — 층 · 카테고리 · 관계 이름은 노드 · config의 값이다.
"""
from __future__ import annotations

import json

from core import paths
from core.state import alias_book as AB, store
from core.state.ids import norm

#: 표본 수 · 표본 한 줄의 글자 상한
SAMPLES, SAMPLE_CHARS = 2, 120
#: 봉투 행에서 「칸 값」으로 보지 않는 열쇠(계약의 구조 칸 — 위치 · 문서 종류 · 원문)
_NOT_VALUE = ("source_locator", "doc_type", "text", "meta")
#: 보류 표기로 세는 보류 사유의 머리(목록 밖 · 표기 모호 — `build_coord`의 문면)
PENDING_HEADS = ("골격에 없는 좌표", "골격 밖", "표기 모호")

_ENV = {}


def _key(text):
    from parser.namefold import key
    return key(text)


# ---------------------------------------------------------------- 봉투 (붙은 행의 바탕)
def env_rows(doc):
    """그 문서 봉투의 `{위치: 행}` — 파일 판으로 기억 · 없거나 못 읽으면 None(**모른다**)."""
    p = paths.parsed(f"{doc}.json")
    k = (str(p), p.stat().st_mtime_ns if p.exists() else None)
    if (_ENV.get(doc) or (None,))[0] != k:
        rows = None
        if k[1] is not None:
            try:
                env = json.loads(p.read_text(encoding="utf-8"))
                rows = {x.get("source_locator"): x for x in list(env.get("records") or []) + list(env.get("chunks") or [])
                        if isinstance(x, dict) and x.get("source_locator")}
            except Exception:                               # noqa: BLE001 — 깨진 봉투는 모른다(지어내지 않는다)
                rows = None
        _ENV[doc] = (k, rows)
    return _ENV[doc][1]


def _values(row):
    for k, v in row.items():
        if k in _NOT_VALUE:
            continue
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str) and x.strip():
                yield k, x


def _sample(prov, row, surface):
    rest = " · ".join(f"{k} {v}" for k, v in _values(row) if _key(v) != _key(surface))
    line = f"{prov} — {rest}" if rest else prov
    return line if len(line) <= SAMPLE_CHARS else line[:SAMPLE_CHARS - 1] + "…"


def used(surface, provs):
    """그 표기로 붙은 행 — `{rows, docs, unknown, samples}`(출처 `문서#위치`마다 · 같은 출처는 한 번)."""
    out = {"rows": 0, "docs": [], "unknown": [], "samples": []}
    sk = _key(surface)
    for p in sorted(set(provs)):
        if "#" not in str(p) or str(p).startswith(("op:", "auto:")):
            continue
        doc, loc = str(p).split("#", 1)
        rows = env_rows(doc)
        if rows is None:
            if doc not in out["unknown"]:
                out["unknown"].append(doc)
            continue
        row = rows.get(loc)
        if row is None or not any(_key(v) == sk for _k, v in _values(row)):
            continue
        out["rows"] += 1
        if doc not in out["docs"]:
            out["docs"].append(doc)
        if len(out["samples"]) < SAMPLES:
            out["samples"].append(_sample(p, row, surface))
    return out


def provs_index(world):
    """`{node_id: [출처]}` — 노드 자신 + 그 노드를 끝점으로 하는 엣지의 출처(층 전부 · 엣지는 문서 층에 산다 — B100)."""
    idx = {}
    for _lay, n in world.nodes():
        idx.setdefault(n["id"], []).extend(n.get("provenance") or [])
    for g in world.graphs.values():
        for e in g.edges:
            for end in (e.get("src"), e.get("dst")):
                idx.setdefault(end, []).extend(e.get("provenance") or [])
    return idx


# ---------------------------------------------------------------- 노드 경로 · 형제 (LLM 재료 · 화면)
def _parents(world):
    """`{node_id: 부모 id}` — 층마다 그 층 config 골격의 자식 관계(`skeleton.relations.child`) · 골격 엣지만."""
    from core.state.bootstrap import load_config
    out = {}
    for lay, g in world.graphs.items():
        try:
            rel = ((load_config(lay).get("skeleton") or {}).get("relations") or {}).get("child")
        except Exception:                                   # noqa: BLE001 — config 없는 층(시험 루트) — 골격 부모 없음
            rel = None
        for e in g.edges if rel else []:
            if e.get("rel") == rel and e.get("status") == "seed":
                out.setdefault(e["src"], e["dst"])
    return out


def _short(canonical):
    from core.state import catalog
    try:
        sep = catalog.sep()
    except Exception:                                       # noqa: BLE001
        sep = "::"
    return str(canonical).split(sep)[-1]


def node_path(world, nid, parents):
    chain, seen = [], set()
    while nid and nid not in seen and len(chain) < 16:
        seen.add(nid)
        n = world.get(nid)
        if n is None:
            break
        chain.append(_short(n["canonical"]))
        nid = parents.get(nid)
    return " › ".join(reversed(chain))


def siblings(world, nid, parents, kids):
    up = parents.get(nid)
    return [_short(world.get(k)["canonical"]) for k in kids.get(up, []) if k != nid and world.get(k)] if up else []


# ---------------------------------------------------------------- 짝
def pairs(world=None, book=None, dic=None):
    """짝 전부 — 노드 경로 차례. 짝 = `{surface, layer, canonical, category, node_id, source, path, siblings, others, shared,
    overlap, dict_miss, rows, docs, unknown, samples, dead, key}` (`key` = (표기, 층, 카테고리, canonical) — 판정 목록의 열쇠)."""
    from core.dictionary import Dictionary
    from core.state.status import is_live
    from core.state.world import World
    w = world or World()
    book = book or AB.AliasBook.open()
    entries = (dic or Dictionary.open()).entries()
    parents = _parents(w)
    kids = {}
    for c, p in parents.items():
        kids.setdefault(p, []).append(c)
    provs = provs_index(w)
    raw = []
    for lay, n in w.nodes():
        if not is_live(n):
            continue
        for a in n.get("aliases") or []:
            s = a["surface"]
            seed = AB.is_seed(a)
            r = None if seed else book.get(s, AB.name(n))
            if not seed and not (r and r.get("status") == AB.LIVE):
                continue
            raw.append((n, s, "골격" if seed else r.get("source")))
    by_norm, by_key = {}, {}
    for n, s, _src in raw:
        by_norm.setdefault(norm(s), set()).add(n["id"])
        by_key.setdefault(_key(s), {}).setdefault(n["id"], set()).add(s)
    out = []
    for n, s, src in raw:
        nid = n["id"]
        shared = sorted(w.get(o)["canonical"] for o in by_norm[norm(s)] if o != nid)
        overlap = sorted(f"{w.get(o)['canonical']}('{t}')" for o, ts in by_key[_key(s)].items() if o != nid
                         for t in ts if norm(t) != norm(s))
        u = used(s, provs.get(nid, []))
        out.append({"surface": s, "layer": n.get("layer"), "canonical": n["canonical"], "category": n["category"],
                    "node_id": nid, "source": src, "path": node_path(w, nid, parents),
                    "siblings": siblings(w, nid, parents, kids)[:8],
                    "others": sorted(a["surface"] for a in n.get("aliases") or [] if a["surface"] != s)[:8],
                    "shared": shared, "overlap": overlap, "dict_miss": nid not in (entries.get(norm(s)) or []),
                    **u, "dead": u["rows"] == 0 and not u["unknown"],
                    "key": pair_key(s, AB.name(n))})
    out.sort(key=lambda p: (p["path"], p["surface"]))
    return out


def pair_key(surface, target):
    """판정 목록의 열쇠 — (표기, 층, 카테고리, canonical)."""
    t = target or {}
    return (surface, t.get("layer"), t.get("category"), norm(t.get("canonical") or ""))


# ---------------------------------------------------------------- 보류 표기 (별칭 후보)
def pending():
    """지금 큐의 `orphan_anchor` 중 사람 판단 없는 것(목록 밖 · 표기 모호) — 표기마다 `{surface, layer, category, rows, docs, reason,
    candidates}` · 행 수 큰 차례."""
    by = {}
    for x in store.read(store.QUEUE, []) or []:
        if x.get("kind") != "orphan_anchor" or x.get("resolution"):
            continue
        reason = str(x.get("reason") or "")
        if not reason.startswith(PENDING_HEADS):
            continue
        pl = x.get("payload") or {}
        s = pl.get("surface")
        if not s:
            continue
        e = by.setdefault((pl.get("layer"), pl.get("category"), norm(s)),
                          {"surface": s, "layer": pl.get("layer"), "category": pl.get("category"), "rows": 0, "docs": [],
                           "reason": reason.split(" — ")[0], "candidates": list(pl.get("candidates") or [])})
        e["rows"] += int(pl.get("rows") or len(pl.get("locators") or []) or 1)
        if x.get("doc_id") and x["doc_id"] not in e["docs"]:
            e["docs"].append(x["doc_id"])
    return sorted(by.values(), key=lambda e: (-e["rows"], e["surface"]))


# ---------------------------------------------------------------- 요약 (bootstrap 끝 한 줄 · 뷰어 머리)
def counts(ps, unreviewed):
    return {"pairs": len(ps), "shared": sum(1 for p in ps if p["shared"]),
            "overlap": sum(1 for p in ps if p["overlap"] or p["dict_miss"]),
            "dead": sum(1 for p in ps if p["dead"]), "unreviewed": unreviewed}


def line(c):
    """`동의어 — 공유 n · 겹침 의심 m · 검토 안 된 짝 k — 뷰어 「동의어」` · 0인 칸은 생략 · 셋 다 0이면 None."""
    parts = [f"{k} {c[v]:,}" for k, v in (("공유", "shared"), ("겹침 의심", "overlap"), ("검토 안 된 짝", "unreviewed"))
             if c.get(v)]
    return ("동의어 — " + " · ".join(parts) + " — 뷰어 「동의어」(python run.py viewer)") if parts else None
