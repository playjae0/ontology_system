# -*- coding: utf-8 -*-
"""칸 2.8 곁 — **잠정 골격 노드의 사람 손 — 승격 · 합침 · 그대로**(B184 ② · 결정 A-승격) · 골격 `ALIASES`에 쓰는 자리 하나.

부르는 화면은 둘이다 — 인입 `--step` 좌표 단계(`cli/provisional_ask`)와 인입 뒤 한 화면(`ops review`). 둘이 같은 함수를 부른다.

| 처분 | 하는 일 |
|---|---|
| 승격 `promote` | 골격 파일에 (부모, 이름) 줄(`{"@unordered": 이름}` — 형제 순서 0) · 잠정 표시를 걷고 사람 고정(seed) · 그 자리에서
|                | 골격 심기(`bootstrap` — 다음 bootstrap과 같은 일 · 같은 노드 · id 그대로) · 이름이 바뀌는 자리(골격이 `부모::이름`을 세운다)는
|                | 거부 — 이름이 바뀌는 일은 재구축 한 길(운영 런북 6) |
| 합침 `merge`   | 그 표기를 고른 골격 노드의 `ALIASES`로 · 이미 세운 잠정이면 재구축 한 길(아래 이름이 바뀐다) · 아직 세우지 않았으면 그
|                | 자리에서 골격 심기(사전이 그 표기를 그 골격 노드로 안다 — 그 문서의 나머지 행부터) |
| 그대로 `keep`  | 쓰지 않는다 · 사람 판단 기록에 「봄」(다음 화면은 접어 둔다) |

학습 기록 승격(`coord_learn.promote` — 좌표 학습의 사람 손)도 `ALIASES`는 여기 `add_alias`로 쓴다(D-269). 골격이 config 인라인인
층은 두 손이 같은 문면으로 멈춘다(`skeleton_file`). 코드에 층 어휘 0 — 카테고리 · 관계 · 단은 config와 골격 심기의 것.
"""
from __future__ import annotations

import copy
import json

from core import paths
from core.state import store
from core.state.status import PROVISIONAL, is_live

#: 사람 판단 기록의 연산 이름(재생은 건너뛴다 — 골격 파일에 남는 판단 · 「봄」은 화면 표지 · `oplog.SKIP`)
OP_PROMOTE, OP_MERGE, OP_KEEP = "provisional:promote", "provisional:merge", "provisional:keep"
#: **골격 칸의 문**(B196 ① · 결정 A′) — 사람이 「새로」(세움) · 「drop」을 정한 표기 + 들어온 자리(부모 이름) · 노드가 없어도 적는다
OP_SEED, OP_DROP = "provisional:seed", "provisional:drop"
#: **올림**(B197 ① — 골격 단 값) — 노드를 세우지 않고 그 값 · 딸린 값을 위 공정(들어온 자리)에 바로
OP_RAISE = "provisional:raise"
#: **해석 고침**(B202 ② — 사람 말을 LLM이 읽은 「이 줄의 해석이 틀렸다」) — 카테고리 · 위 공정 · 기록은 표기 + 들어온 자리 + 고친 칸
OP_REREAD = "provisional:reread"
#: 문이 보는 사람 답 — 세움(「봄」도 세움 · 재구축 뒤에도 그 노드가 다시 선다) · drop · 올림 · 해석 고침(그 자리의 문을 떠난다)
SEEDED, DROPPED, RAISED, REREAD = "seed", "drop", "raise", "reread"
#: 큐 판단(재인입 회수가 보존한다 — `resolution`)
DEC_PROMOTE, DEC_MERGE = "승격", "합침(재구축 대기)"
REBUILD = "python run.py rebuild"


class Refused(Exception):
    """사람 손의 거부 — 문면에 다음 줄이 있다."""


# ---------------------------------------------------------------- 골격 파일 · ALIASES (자리 하나)
def skeleton_file(err=Refused, layer=None):
    """`(층, 골격 파일)` — 층을 주지 않으면 좌표 층(B200 ④ — 동의어 승인은 대상 노드의 층) · 골격이 config 인라인이면 `err`(학습 승격과
    같은 문면)."""
    from core.state.bootstrap import coord_layer, load_config
    lay = layer or coord_layer()
    src = ((load_config(lay).get("skeleton") or {}).get("source"))
    if not src:
        raise err(
            f"[상태] 좌표 층 {lay}의 골격이 파일이 아니다(config 인라인) — 승격할 `ALIASES` 자리가 없다\n"
            f"  ▶ 다음 줄 — 표기를 노드에 사람이 잇는다: python run.py ops alias {lay} <노드> <표기> --actor <이름>")
    return lay, paths.layers(lay, src)


def _read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _write(p, seed):
    store.atomic_write_bytes(p, (json.dumps(seed, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def add_alias(canonical, surface, err=Refused, layer=None):
    """**골격 `ALIASES`에 쓰는 자리 하나** — `canonical`(골격 노드) 아래에 `surface` · 돌려주는 것은 `(층, 파일)` · 층을 주지 않으면 좌표 층."""
    lay, p = skeleton_file(err, layer)
    seed = _read(p)
    al = seed.setdefault("ALIASES", {}).setdefault(canonical, [])
    if surface not in al:
        al.append(surface)
    _write(p, seed)
    return lay, p


def drop_alias(canonical, surface, err=Refused, layer=None):
    """골격 `ALIASES`에서 빼는 자리 하나(B200 ④ — `add_alias`의 짝) — `canonical` 키 또는 그 노드의 짧은 이름 키(짧은 키는
    다른 노드의 이름이 아닐 때만 그 노드다 — 로더 규칙)에서 `surface`를 뺀다 · 빈 키는 지운다. 돌려주는 것은 `(층, 파일, 뺐나)`."""
    from core.state import catalog
    lay, p = skeleton_file(err, layer)
    seed = _read(p)
    al = seed.get("ALIASES") or {}
    short = str(canonical).split(catalog.sep())[-1]
    names = _canonicals(seed)
    hit = False
    for k in [canonical] + ([short] if short != canonical and short not in names else []):
        if surface in (al.get(k) or []):
            al[k] = [s for s in al[k] if s != surface]
            if not al[k]:
                del al[k]
            hit = True
    if hit:
        _write(p, seed)
    return lay, p, hit


def _canonicals(seed):
    """seed 트리의 canonical 전부 — 로더의 파서 그대로(짧은 키가 다른 노드의 이름인지 가린다)."""
    from core.state import catalog
    from core.state.skeleton import _TreeParser
    return {s.canonical for s in _TreeParser(dict(seed.get("AXIS_LABELS") or {}), catalog.sep()).parse(
        seed.get("TREE") or []).specs}


def _replant(lay):
    """그 자리의 골격 심기 — 다음 `bootstrap`과 같은 일(같은 노드 · id 그대로 · 사전 · 닫힌 목록 스냅샷)."""
    from core.state.bootstrap import bootstrap
    bootstrap(lay, echo=False)


# ---------------------------------------------------------------- 골격 트리에 한 줄
def _insert(items, target, entry, up, depth, labels, sep):
    """`target`(부모 canonical) 아래에 `entry`를 더한다 — 찾으면 True. 잎(문자열)은 자식 배열로 편다(뜻 그대로)."""
    from core.state.skeleton import MARK_PREFIX, MARK_UNORDERED, TIER_BY_DEPTH

    def canon(name):
        return name if depth in TIER_BY_DEPTH else f"{up}{sep}{name}"
    for i, it in enumerate(items):
        if isinstance(it, str):
            if not it.startswith((sep, MARK_PREFIX)) and canon(it) == target:
                items[i] = {it: [entry]}
                return True
            continue
        if not isinstance(it, dict) or len(it) != 1:
            continue
        (k, v), = it.items()
        if k == MARK_UNORDERED:
            box = [v]
            if _insert(box, target, entry, up, depth, labels, sep):
                it[k] = box[0]
                return True
        elif isinstance(v, list):
            if canon(k) == target:
                v.append(entry)
                return True
            if _insert(v, target, entry, canon(k), depth + 1, labels, sep):
                return True
    return False


def _grown(seed, parent, name):
    """골격에 (부모, 이름)을 더한 새 seed와 그 사양 — `(seed, spec)` · 골격 파서가 거부하면 `Refused`."""
    from core.state import catalog
    from core.state.skeleton import MARK_UNORDERED, SeedError, _TreeParser
    sep, labels = catalog.sep(), seed.get("AXIS_LABELS") or {}
    new = copy.deepcopy(seed)
    if not _insert(new.get("TREE") or [], parent, {MARK_UNORDERED: name}, None, 1, labels, sep):
        raise Refused(f"부모 '{parent}'가 골격 파일에 없다 — 사람이 고정한 골격 노드 아래로만 승격한다(잠정 부모는 먼저 승격)")
    try:
        parsed = _TreeParser(labels, sep).parse(new["TREE"])
    except SeedError as e:
        raise Refused(f"골격 파일이 받지 않는다 — {e}") from None
    spec = next((s for s in parsed.specs if s.name == name and s.parent is not None
                 and s.parent.canonical == parent), None)
    return new, spec, parsed


# ---------------------------------------------------------------- 처분 셋
def _ctx():
    from core.state.bootstrap import COORD_CATEGORY, coord_layer, load_config, open_graph
    lay = coord_layer()
    child = ((load_config(lay).get("skeleton") or {}).get("relations") or {}).get("child")
    return lay, open_graph(lay), child, COORD_CATEGORY


def _node(g, nid, cat):
    n = g.get(nid) if nid else None
    if not (n and is_live(n) and n.get(PROVISIONAL) and n.get("category") == cat):
        raise Refused(f"잠정 골격 노드가 아니다 — {nid}")
    return n


def _names(lay, n, cat):
    return {"node": {"layer": lay, "canonical": n["canonical"], "category": cat}}


def promote(actor, *, nid=None, surface=None, parent=None, reason=""):
    """**승격** — 잠정 노드(`nid` — 이미 세웠다) 또는 이 문서에서 세울 표기(`surface` — `--step`)를 골격 파일의 (부모, 이름)으로.

    부모는 그 노드의 부모 엣지 → `parent`(부모 미정이면 사람이 정한다 — 골격 노드 canonical). 돌려주는 것
    `{canonical, parent, id, file}`. 이름이 바뀌는 자리 · 부모 미정 · 잠정 부모는 `Refused`(다음 줄 포함)."""
    from core.state import catalog
    from core.state.ops import log_op
    if not actor:
        raise Refused("행위자 미지정 — 승격은 로그에 행위자를 남긴다")
    lay, g, child, cat = _ctx()
    _lay, p = skeleton_file()
    n = _node(g, nid, cat) if nid else None
    up = None
    if n is not None:
        e = next((e for e in g.edges if e["src"] == nid and e["rel"] == child and is_live(g.get(e["dst"]))), None)
        up = (g.get(e["dst"]) or {}).get("canonical") if e else None
    up = up or parent
    if not up:
        raise Refused("부모 미정 — 부모를 정한다(골격 노드 이름)")
    sep = catalog.sep()
    canonical = n["canonical"] if n is not None else surface
    name = canonical[len(up) + len(sep):] if canonical.startswith(up + sep) else canonical
    seed, spec, _parsed = _grown(_read(p), up, name)
    if spec is None or (n is not None and spec.canonical != canonical):
        raise Refused(f"승격하면 이름이 바뀐다(지금 '{canonical}' → 골격 '{spec.canonical if spec else name}') — 이름이 바뀌는 일은 "
                      "재구축 한 길: 골격 파일에 줄 → python run.py bootstrap → python run.py rebuild (운영 런북 6)")
    _write(p, seed)
    if n is not None:
        n["status"] = "seed"
        n.pop(PROVISIONAL, None)
        for x in g.edges:                         # 부모 엣지도 사람 고정(닫힌 목록 스냅샷의 부모)
            if x["src"] == nid and x["rel"] == child and (g.get(x["dst"]) or {}).get("canonical") == up:
                x["status"] = "seed"
        g.save()
    _replant(lay)
    g = _ctx()[1]
    got = next((i for i, x in g.nodes.items() if x["canonical"] == spec.canonical and x["category"] == cat and is_live(x)), None)
    if n is not None:
        store.resolve_item("auto_node", lambda pl: pl.get("node_id") == nid, actor=actor, decision=DEC_PROMOTE,
                           at=store._now(), note="승격")
        store.resolve_item("uncertain_match", lambda pl: pl.get("node_id") == nid, actor=actor, decision=DEC_PROMOTE,
                           at=store._now(), note="승격")
    log_op(OP_PROMOTE, actor, [got], reason, {"canonical": spec.canonical, "parent": up, "skeleton": paths.show(p)},
           {"node": {"layer": lay, "canonical": spec.canonical, "category": cat}})
    return {"canonical": spec.canonical, "parent": up, "id": got, "file": p}


def merge(actor, *, target, nid=None, surface=None, reason=""):
    """**합침** — 표기를 골격 노드 `target`(canonical — 사람이 고정한 것)의 `ALIASES`로. 이미 세운 잠정(`nid`)이면 재구축이
    필요하다(`rebuild: True` — 그 자리에서 이름을 고치는 둘째 길 0) · 아직 세우지 않은 표기(`surface`)면 그 자리의 골격 심기."""
    from core.state.ops import log_op
    if not actor:
        raise Refused("행위자 미지정 — 합침은 로그에 행위자를 남긴다")
    lay, g, _child, cat = _ctx()
    t = next((x for x in g.nodes.values() if x["canonical"] == target and x["category"] == cat and is_live(x)
              and not x.get(PROVISIONAL) and x.get("status") == "seed"), None)
    if t is None:
        raise Refused(f"합칠 골격 노드 '{target}'가 없다 — 사람이 고정한 골격 노드로만 합친다")
    n = _node(g, nid, cat) if nid else None
    words = ([surface] if surface else []) + ([a["surface"] for a in n.get("aliases") or [] if a.get("surface")]
                                               if n is not None else [])
    if n is not None and not words:
        words = [n["canonical"]]
    for w in dict.fromkeys(words):
        _lay, p = add_alias(target, w)
    if n is None:
        _replant(lay)
    else:
        store.resolve_item("auto_node", lambda pl: pl.get("node_id") == nid, actor=actor, decision=DEC_MERGE,
                           at=store._now(), note=f"→ {target}")
        store.resolve_item("uncertain_match", lambda pl: pl.get("node_id") == nid, actor=actor, decision=DEC_MERGE,
                           at=store._now(), note=f"→ {target}")
    log_op(OP_MERGE, actor, [nid or t["id"]], reason, {"surfaces": list(dict.fromkeys(words)), "target": target,
                                                        "rebuild": n is not None, "skeleton": paths.show(p)},
           _names(lay, n, cat) if n is not None else {"node": {"layer": lay, "canonical": target, "category": cat}})
    return {"target": target, "surfaces": list(dict.fromkeys(words)), "rebuild": n is not None, "file": p}


def keep(actor, nid, reason=""):
    """**그대로** — 쓰지 않는다 · 「봄」 표지(사람 판단 기록 — 다음 화면은 접어 둔다 · 문에는 「세움」과 같다 — B196 ①)."""
    from core.state.ops import log_op
    lay, g, child, cat = _ctx()
    n = _node(g, nid, cat)
    e = next((e for e in g.edges if e["src"] == nid and e["rel"] == child and is_live(g.get(e["dst"]))), None)
    log_op(OP_KEEP, actor, [nid], reason, {"canonical": n["canonical"],
                                            "parent": (g.get(e["dst"]) or {}).get("canonical") if e else None},
           _names(lay, n, cat))
    return {"canonical": n["canonical"]}


def _gate_rec(op, actor, surface, parent, reason, **more):
    from core.state.ops import log_op
    if not actor:
        raise Refused("행위자 미지정 — 사람 판단은 로그에 행위자를 남긴다")
    lay, _g, _child, cat = _ctx()
    log_op(op, actor, [], reason, {"surface": surface, "parent": parent, **{k: v for k, v in more.items() if v}},
           {"node": {"layer": lay, "canonical": surface, "category": cat}})


def seed(actor, surface, parent=None, reason="", under=None, pair=False):
    """**새로 만들기(잠정)**(B196 ① · B203 ④) — 표기 + 들어온 자리(부모 이름)의 「세움」 기록 · 노드가 아직 없어도 적는다(계획이 그 기록을
    보고 세운다 — 그 문서의 나머지 행부터 · 재연결이 보류 행을 그 노드에) · `under` = 고른 부모(골격 노드 canonical — 없으면 들어온 자리) ·
    `pair` = 쌍 줄(그 이름이 골격의 다른 자리에 있어도 이 자리 밑에 `<부모>::<표기>`로 선다)."""
    _gate_rec(OP_SEED, actor, surface, parent, reason, under=under, pair=pair)
    _reopen(surface, parent)
    return {"surface": surface, "parent": parent, "under": under}


def placed():
    """「새로 만들기」의 자리 — `{(표기 키, 들어온 자리): {under, pair}}`(기록에 있을 때만 · 뒤의 기록이 앞을 덮는다 · 쓰기 0)."""
    from core.state import oplog
    from parser.namefold import key
    out = {}
    for r in oplog.read():
        d = r.get("detail") or {}
        if r.get("op") in (OP_SEED, OP_DROP, OP_RAISE, OP_REREAD) and d.get("surface"):
            out[(key(d["surface"]), d.get("parent"))] = {k: d.get(k) for k in ("under", "pair")}
    return out


def raise_up(actor, surface, parent=None, reason=""):
    """**올림**(B197 ① — 골격 단 값) — 노드 0 · 그 값 · 딸린 값은 위 공정(들어온 자리 `parent`)에 바로 · 재연결이 그 보류를 위 공정에 잇는다."""
    if not parent:
        raise Refused("올릴 위 공정이 없다(부모 미정) — 합침 · 새로 · drop 중 하나")
    _gate_rec(OP_RAISE, actor, surface, parent, reason)
    _reopen(surface, parent)
    return {"surface": surface, "parent": parent}


def drop(actor, surface, parent=None, reason=""):
    """**drop**(B196 ① — 사유 필수) — 세우지 않는다 · 그 표기의 열린 보류를 「사람 drop」으로 닫는다(재연결이 다시 열지 않는다)."""
    if not (reason or "").strip():
        raise Refused("drop은 사유가 있어야 한다 — d <줄> <사유>")
    _gate_rec(OP_DROP, actor, surface, parent, reason)
    from core.state.bootstrap import COORD_CATEGORY
    from parser.namefold import key
    k = key(surface)
    n = store.resolve_item("orphan_anchor", lambda pl: key(pl.get("surface") or "") == k
                           and pl.get("category") == COORD_CATEGORY and (pl.get("gate") or {}).get("parent") == parent,
                           actor=actor, decision=DEC_DROP, at=store._now(), note=reason)
    return {"surface": surface, "parent": parent, "closed": n}


#: 큐 판단 — drop으로 닫은 보류(재연결 대상 밖 · `retry.is_target`가 `resolution`으로 거른다)
DEC_DROP = "사람 drop"
DEC_REREAD = "사람 해석 고침"


def reread(actor, surface, parent, *, category=None, up=None, before=None, reason=""):
    """**해석 고침**(B202 ②) — 그 표기 · 그 자리의 해석을 사람이 고쳤다(`category` — 다른 카테고리 · `up` — 다른 위 공정) · 그 자리의 문을
    떠난다(문의 사람 답 `REREAD`) · 구축은 고친 해석으로 판정한다(`also_gate.reread` — `resolve_at_home` 입구 한 자리) · 열린 보류는
    「사람 해석 고침」으로 닫는다(다시 넣으면 고친 해석으로)."""
    from core.state.ops import log_op
    from parser.namefold import key
    if not actor:
        raise Refused("행위자 미지정 — 사람 판단은 로그에 행위자를 남긴다")
    if not (category or up):
        raise Refused("고칠 칸이 없다 — 카테고리 또는 위 공정")
    lay, _g, _child, cat = _ctx()
    log_op(OP_REREAD, actor, [], reason, {"surface": surface, "parent": parent, "category": category, "up": up,
                                          "before": before},
           {"node": {"layer": lay, "canonical": surface, "category": cat}})
    k = key(surface)
    n = store.resolve_item("orphan_anchor", lambda pl: key(pl.get("surface") or "") == k and pl.get("category") == cat
                           and (pl.get("gate") or {}).get("parent") == parent,
                           actor=actor, decision=DEC_REREAD, at=store._now(), note=f"{before} → {category or up}")
    return {"surface": surface, "parent": parent, "category": category, "up": up, "closed": n}


def rereads():
    """해석 고침 기록 — `{(표기 키, 들어온 자리): {category, up}}` · 뒤의 기록이 앞을 덮는다(쓰기 0)."""
    from core.state import oplog
    from parser.namefold import key
    out = {}
    for r in oplog.read():
        d = r.get("detail") or {}
        if r.get("op") == OP_REREAD and d.get("surface"):
            out[(key(d["surface"]), d.get("parent"))] = {"category": d.get("category"), "up": d.get("up")}
    return out


def _reopen(surface, parent):
    """「세움」 뒤 그 표기의 열린 보류는 다시 시도할 거리다 — 지난 시도의 지문을 걷는다(재연결이 그 행을 다시 본다)."""
    from parser.namefold import key
    k, q, hit = key(surface), store.read(store.QUEUE, []), False
    for x in q:
        pl = x.get("payload") or {}
        if x.get("kind") == "orphan_anchor" and key(pl.get("surface") or "") == k and (pl.get("gate") or {}).get("parent") == parent:
            x.pop("last_fp", None)
            hit = True
    if hit:
        store.write(store.QUEUE, q)


def decisions():
    """**문이 보는 사람 답**(B196 ① — 쓰기 0) — `{(표기 키, 부모 이름): seed|drop}` · 뒤의 기록이 앞을 덮는다. 「봄」(`OP_KEEP`)은
    세움이다(그 노드의 이름 · 부모 — 옛 기록은 부모가 없어 이름만: `(키, None)`과 `(키, "*")`)."""
    from core.state import catalog, oplog
    from parser.namefold import key
    sep, out = catalog.sep(), {}
    for r in oplog.read():
        op, d = r.get("op"), r.get("detail") or {}
        if op in (OP_SEED, OP_DROP, OP_RAISE, OP_REREAD) and d.get("surface"):
            out[(key(d["surface"]), d.get("parent"))] = {OP_SEED: SEEDED, OP_DROP: DROPPED, OP_RAISE: RAISED,
                                                         OP_REREAD: REREAD}[op]
        elif op == OP_KEEP and d.get("canonical"):
            c, up = d["canonical"], d.get("parent", "*")
            base = c[len(up) + len(sep):] if isinstance(up, str) and up != "*" and c.startswith(up + sep) else c
            out[(key(base), up)] = SEEDED
    return out


def decided(book, surface, parent):
    """그 표기 · 그 자리(부모 이름)의 사람 답 — `book`은 `decisions()` · 「봄」 옛 기록(`*`)은 자리를 가리지 않는다."""
    from parser.namefold import key
    k = key(surface or "")
    return book.get((k, parent)) or book.get((k, "*"))


def kept():
    """「봄」 표지가 있는 잠정 노드 이름 — 사람 판단 기록에서(화면이 접어 둔다)."""
    from core.state import oplog
    return {((r.get("names") or {}).get("node") or {}).get("canonical") for r in oplog.read() if r.get("op") == OP_KEEP}
