# -*- coding: utf-8 -*-
"""칸 0.3 — **별칭 대장** — 쌓인 별칭을 이름으로 남기고, 재구축에서도 처음부터 쓴다 (B108 ① · 사용자 결정
2026-10-14 「별칭은 누적·호환해 활용하는 핵심 자산이다」).

    <상태>/data/alias_book.json      ③진실 — 기본 fresh가 남긴다(`init.kept()`) · `--all`(클린)이 지운다

**쓰는 손은 하나다**(`attach`) — 노드에 seed 밖 별칭이 붙는 자리 전부(인입 · `ops alias`의 `Builder._register` ·
개명 · 이관 · 병합 · 분리)가 이 함수를 지나 대장에 **이름으로** 남긴다. 항목 = 표기 · 대상(층 · canonical ·
카테고리 — id는 참고) · 출처 · 문서(처음 · 마지막) · 시각 · 횟수 · 상태(살아 있음 | 거부). 같은 표기 · 같은
대상이면 한 항목이다 — 횟수는 그 별칭을 붙이거나 쓴 **문서 수 + 사람 연산 수**(같은 문서의 재인입 · 사람 판단
재생은 늘리지 않는다).

  · 출처(닫힌 목록 `SOURCES`) — LLM 매칭 · 사람(`ops alias`) · 개명 · 이관 · 병합 · 분리 · 문서(사전 경로 · 새 노드의
    원 표기). 「문서」는 **골격 대상만** 적는다 — 엔티티의 원 표기는 재인입이 문서에서 그대로 다시 만든다. seed
    별칭(골격 `ALIASES` · 좌표 학습 승격)은 적지 않는다 — 원천이 사람의 파일이다
  · **bootstrap**은 골격을 심은 뒤 대장의 골격 대상 별칭을 먼저 싣고(`load_skeleton` — 노드 · 사전) 스냅샷을
    만든다 → 스냅샷의 별칭 = seed + 대장(거부 제외 · `snapshot_aliases`) — bootstrap을 언제 돌렸는지와 무관하다.
    대상 canonical이 골격에 없으면(이름이 바뀌었다) 싣지 않고 「대상 없음」으로 센다 — 대장은 지우지 않고,
    바뀐 이름으로 옮기지도 않는다
  · 엔티티 대상은 싣지 않는다 — 판정 재생 · 사람 판단 재생이 되살린다(대장은 기록 · 화면 · 거두기)
  · **거부**(`reject` — `ops alias-reject`)는 상태를 「거부」로 — 쓰는 손이 그 (표기, 대상)을 다시 붙이지 않고
    bootstrap도 싣지 않는다. 판정은 그대로다(행의 값은 판정대로 이어진다 — 대장은 판정을 대신하지 않는다).
    사람이 `ops alias`로 다시 이으면 살아난다(`revive`)
  · **처음 채움**(`backfill`) — 대장이 없거나 모자라면 지금 그래프(층 전부 · 산 노드)의 seed 밖 별칭을 이름으로
    (출처는 provenance로) — 지우기 전에: 첫 실행(공통 진입) · 재구축 계획(fresh 앞)
  · 연산이 노드의 이름을 바꾸면(개명 · 이관 · 병합 · 분리) 그 노드를 가리키던 항목의 대상 이름이 같이 간다
    (`retarget` — 같은 노드다)

코드에 층 어휘 0 — 대상의 층 · 카테고리는 노드가 갖는 값이다.
"""
from __future__ import annotations

from core.state import log, store
from core.state.ids import norm

_LOG = log.get(__name__)

LIVE, REJECTED = "살아 있음", "거부"
#: 출처 — 닫힌 목록 · 「문서」는 골격 대상만 적는다
SOURCES = ("LLM 매칭", "사람", "개명", "이관", "병합", "분리", "문서")
#: 연산 provenance 접두 → 출처(처음 채움의 분류 — **마지막** 연산이 이 대상에 붙였다)
OP_SOURCES = (("op:alias:", "사람"), ("op:rename:", "개명"), ("op:transfer:", "이관"),
              ("op:merge:", "병합"), ("op:split:", "분리"))
#: 처음 채움이 적은 항목의 표시 — 붙인 때가 아니라 나중에 그래프에서 읽은 것이다
FILLED = "backfill"


def name(n):
    """노드 → 대상 이름 `{layer, canonical, category}` — 사람 판단 기록(`oplog.name`)과 같은 열쇠."""
    return {"layer": n.get("layer"), "canonical": n.get("canonical"), "category": n.get("category")}


def _key(surface, t):
    return (t.get("layer"), t.get("category"), norm(t.get("canonical") or ""), surface)


def is_seed(alias):
    """seed 별칭인가 — provenance가 골격 하나뿐(골격 `ALIASES` · 좌표 학습 승격)."""
    prov = [str(p) for p in alias.get("provenance") or []]
    return bool(prov) and all(p == "seed" for p in prov)


def source_of(alias):
    """별칭 하나의 출처 — provenance의 마지막 연산 · 없으면 판정 표지(LLM 매칭) · 그 밖은 문서 · seed면 None."""
    if is_seed(alias):
        return None
    for p in reversed([str(x) for x in alias.get("provenance") or []]):
        for pre, src in OP_SOURCES:
            if p.startswith(pre):
                return src
    return "LLM 매칭" if alias.get("by") == "LLM 매칭" else "문서"


def _doc_of(alias):
    """별칭의 문서 — 판정 표지의 `doc` · 없으면 provenance의 문서 접두(`{doc}#{위치}`) · 연산이면 None."""
    if alias.get("doc"):
        return alias["doc"]
    for p in alias.get("provenance") or []:
        p = str(p)
        if "#" in p and not p.startswith("op:"):
            return p.split("#", 1)[0]
    return None


def _muted():
    from core.state import oplog
    return oplog.MUTED


class AliasBook:
    """`data/alias_book.json` — `{"entries": [항목 …]}`. 여는 입구 `open` · 쓰기 `save`(바뀐 것이 있을 때만)."""

    def __init__(self, data=None):
        self.rows = list((data or {}).get("entries") or [])
        self._idx = {_key(r["surface"], r["target"]): r for r in self.rows}
        self.dirty = False

    @classmethod
    def open(cls):
        return cls(store.read(store.ALIAS_BOOK, None))

    @staticmethod
    def exists():
        return store.path(store.ALIAS_BOOK).is_file()

    def save(self, force=False):
        if self.dirty or force:
            store.write(store.ALIAS_BOOK, {"entries": self.rows})
            self.dirty = False

    # ------------------------------------------------------------ 조회
    def get(self, surface, target):
        return self._idx.get(_key(surface, target))

    def live(self, surface, node):
        r = self.get(surface, name(node))
        return bool(r and r.get("status") == LIVE)

    def rejected(self, surface, node):
        r = self.get(surface, name(node))
        return bool(r and r.get("status") == REJECTED)

    def of(self, node):
        """그 노드를 대상으로 하는 항목 전부."""
        t = name(node)
        k = (t["layer"], t["category"], norm(t["canonical"] or ""))
        return [r for r in self.rows if _key(r["surface"], r["target"])[:3] == k]

    # ------------------------------------------------------------ 적기
    def note(self, node, alias, source, *, doc=None, key=None, bump=True, filled=False):
        """항목 하나를 적는다(쓰는 손 `attach` · 처음 채움이 부른다) — 돌려주는 것은 항목(적지 않으면 None)."""
        s = alias["surface"]
        if source is None or norm(s) == norm(node.get("canonical") or ""):
            return None
        skel = node.get("status") == "seed"
        tgt = name(node)
        r = self.get(s, tgt)
        now = store._now()
        if r is None:
            if source == "문서" and not skel:
                return None
            r = {"surface": s, "target": tgt, "id": node.get("id"), "source": source, "skeleton": skel,
                 "alias": {k: v for k, v in alias.items() if k != "surface"},
                 "key": key if key and norm(key) != norm(s) else None,
                 "docs": [doc] if doc else [], "first_doc": doc, "last_doc": doc,
                 "first_at": now, "last_at": now, "count": 1, "status": LIVE}
            if filled:
                r["filled"] = FILLED
            self.rows.append(r)
            self._idx[_key(s, tgt)] = r
            self.dirty = True
            return r
        if doc and doc not in r["docs"]:
            r["docs"].append(doc)
            r["first_doc"] = r.get("first_doc") or doc
            r["last_doc"] = doc
            r["count"] += 1
            r["last_at"] = now
            self.dirty = True
        elif not doc and bump and not filled and not _muted():
            r["count"] += 1
            r["last_at"] = now
            self.dirty = True
        for k, v in (("id", node.get("id")), ("key", key if key and norm(key) != norm(s) else None)):
            if v and r.get(k) != v and (k == "id" or not r.get(k)):
                r[k] = v                                   # id는 참고 — 재구축 뒤 새 id
                self.dirty = True
        if skel and not r.get("skeleton"):
            r["skeleton"] = True
            self.dirty = True
        return r

    def retarget(self, old, new, *, surfaces=None, source=None):
        """대상 이름이 바뀌었다(같은 노드 — 개명 · 이관 · 병합 · 분리) — `old` 이름 항목을 `new`로. 겹치면 합친다
        (문서 · 횟수) · `source`를 주면 출처를 바꾸고 앞 출처 · 대상을 `via`에 남긴다. 돌려주는 것은 옮긴 수."""
        k_old = _key("", old)[:3]
        moved = 0
        for r in list(self.rows):
            if _key(r["surface"], r["target"])[:3] != k_old or (surfaces is not None and r["surface"] not in surfaces):
                continue
            del self._idx[_key(r["surface"], r["target"])]
            if source and source != r["source"]:
                r.setdefault("via", []).append({"source": r["source"], "target": dict(r["target"])})
                r["source"] = source
            r["target"] = dict(new)
            dst = self._idx.get(_key(r["surface"], new))
            if dst is not None:                                # 같은 별칭이 이미 그 대상에 — 한 항목으로
                for d in r["docs"]:
                    if d not in dst["docs"]:
                        dst["docs"].append(d)
                dst["count"] += r["count"]
                self.rows.remove(r)
            else:
                self._idx[_key(r["surface"], new)] = r
            moved += 1
        if moved:
            self.dirty = True
        return moved

    def reject(self, node, surface, *, actor, reason="", alias=None, key=None):
        """「거부」 — 없으면 거부 항목을 새로 적는다(출처는 별칭의 provenance로). 돌려주는 것은 항목."""
        r = self.get(surface, name(node))
        if r is None:
            al = alias or {"surface": surface, "provenance": []}
            src = source_of(al) or "문서"
            now = store._now()
            r = {"surface": surface, "target": name(node), "id": node.get("id"), "source": src,
                 "skeleton": node.get("status") == "seed",
                 "alias": {k: v for k, v in al.items() if k != "surface"},
                 "key": key if key and norm(key) != norm(surface) else None,
                 "docs": [], "first_doc": None, "last_doc": None, "first_at": now, "last_at": now,
                 "count": 0, "status": LIVE}
            self.rows.append(r)
            self._idx[_key(surface, r["target"])] = r
        r["status"] = REJECTED
        r["rejected"] = {"actor": actor, "at": store._now(), "reason": reason}
        if key and norm(key) != norm(surface) and not r.get("key"):
            r["key"] = key
        self.dirty = True
        return r

    def revive(self, node, surface):
        """사람이 다시 잇는다(`ops alias`) — 거부 항목을 살린다. 살렸으면 True."""
        r = self.get(surface, name(node))
        if r is None or r.get("status") != REJECTED:
            return False
        r["status"] = LIVE
        r.setdefault("revived", []).append(r.pop("rejected", None))
        self.dirty = True
        return True


# ---------------------------------------------------------------- 쓰는 손 (하나)
def attach(book, node, alias, *, source, doc=None, key=None, bump=True):
    """**쓰는 손 하나**(B108 ①) — 노드에 seed 밖 별칭 하나를 붙이고(없으면) 대장에 이름으로 남긴다.

    돌려주는 것은 이번에 노드에 붙였는가. 거부된 (표기, 대상)은 붙이지 않는다(False). 노드에 이미 있으면
    붙이지 않고 대장만 센다(문서 · 횟수 — 출처는 그 별칭의 provenance로). `bump=False`는 횟수를 늘리지 않는다
    (bootstrap의 싣기 · 병합이 옮긴 것)."""
    s = alias["surface"]
    if book.rejected(s, node):
        return False
    have = next((a for a in node["aliases"] if a["surface"] == s), None)
    if have is None:
        node["aliases"].append(alias)
    book.note(node, alias if have is None else have, source if have is None else source_of(have),
              doc=doc, key=key, bump=bump)
    return have is None


# ---------------------------------------------------------------- bootstrap
def load_skeleton(book, layer, g, dictionary):
    """**bootstrap이 싣는다**(B108 ①) — 골격을 심은 뒤 · 스냅샷 전에. 대장의 살아 있는 항목 중 대상이 이 층의
    골격(seed) 노드인 것을 노드 · 사전에 싣는다(쓰는 손 `attach` · 사전 관문 — 횟수는 늘리지 않는다).

    대상은 이름(카테고리 · canonical)으로 찾는다 — 골격에 없으면 싣지 않고 「대상 없음」(골격 대상이던 항목만
    센다 · 엔티티 대상은 판정 재생 · 사람 판단 재생의 몫이다). `{loaded, already, missing, rejected}`."""
    seeds = {}
    for n in g.nodes.values():
        if n.get("status") == "seed":
            seeds.setdefault((n["category"], norm(n["canonical"])), n)
    out = {"loaded": 0, "already": 0, "missing": [], "rejected": 0}
    for r in list(book.rows):
        t = r["target"]
        if t.get("layer") != layer:
            continue
        n = seeds.get((t.get("category"), norm(t.get("canonical") or "")))
        if r.get("status") != LIVE:
            out["rejected"] += 1 if n is not None else 0
            continue
        if n is None:
            if r.get("skeleton"):
                out["missing"].append(r)
            continue
        if norm(r["surface"]) == norm(n["canonical"]):
            continue                                       # 이름 자신 — 별칭이 아니다
        al = {"surface": r["surface"], **(r.get("alias") or {})}
        prov = (al.get("provenance") or [None])[0] or "alias_book"
        al["provenance"] = list(al.get("provenance") or [prov])
        dictionary.register(r["surface"], n["id"], provenance=prov)
        if r.get("key"):
            dictionary.register(r["key"], n["id"], provenance=prov)
        out["loaded" if attach(book, n, al, source=r["source"], bump=False) else "already"] += 1
    return out


def snapshot_aliases(book, n):
    """스냅샷(골격 닫힌 목록)에 싣는 별칭 — **seed 별칭 + 대장의 살아 있는 항목**(이 노드 대상) · 정렬.

    그래프의 다른 별칭은 싣지 않는다 — 그래야 스냅샷이 bootstrap을 언제 돌렸는지와 무관하다(B108 ①)."""
    return sorted(a["surface"] for a in n.get("aliases") or [] if is_seed(a) or book.live(a["surface"], n))


# ---------------------------------------------------------------- 처음 채움
def backfill(book=None, world=None):
    """**처음 채움** — 지금 그래프(층 전부 · 산 노드)의 seed 밖 별칭 중 대장에 없는 것을 이름으로 채운다(지우기
    전에 부른다). `{total, filled, skeleton}` — total = 대장의 살아 있는 항목 · skeleton = 그중 골격 대상."""
    from core.state.status import is_live
    from core.state.world import World
    book = book or AliasBook.open()
    w = world or World()
    filled = 0
    for _lay, n in w.nodes():
        if not is_live(n):
            continue
        for a in n.get("aliases") or []:
            if book.get(a["surface"], name(n)) is None and \
                    book.note(n, a, source_of(a), doc=_doc_of(a), filled=True) is not None:
                filled += 1
    if filled:
        book.save()
        _LOG.info("별칭 대장 처음 채움 — %d건(지금 그래프에서)", filled)
    return {**counts(book), "filled": filled}


def counts(book):
    live = [r for r in book.rows if r.get("status") == LIVE]
    return {"total": len(live), "skeleton": sum(1 for r in live if r.get("skeleton")),
            "rejected": len(book.rows) - len(live)}


# ---------------------------------------------------------------- 대조
def presence(book=None, world=None):
    """대장의 살아 있는 항목이 지금 그래프에 있나 — `{total, present, missing: [항목]}`(재구축 끝 · `show aliases`).

    있음 = 대상 이름(층 · 카테고리 · canonical)의 산 노드가 그 표기를 별칭으로 갖는다."""
    from core.state.status import is_live
    from core.state.world import World
    book = book or AliasBook.open()
    w = world or World()
    have = {}
    for _lay, n in w.nodes():
        if is_live(n):
            t = name(n)
            have.setdefault((t["layer"], t["category"], norm(t["canonical"] or "")), set()).update(
                a["surface"] for a in n.get("aliases") or [])
    live = [r for r in book.rows if r.get("status") == LIVE]
    miss = [r for r in live if r["surface"] not in have.get(_key(r["surface"], r["target"])[:3], set())]
    return {"total": len(live), "present": len(live) - len(miss), "missing": miss}
