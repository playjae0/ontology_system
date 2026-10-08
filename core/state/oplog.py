# -*- coding: utf-8 -*-
"""칸 0.3 — **사람 판단 기록** — 자리 · 이름 · 재생 (B106 ③ · 사용자 결정 2026-10-07 「CP 연결을 이력으로 남겨
기존 노드에 다시 붙게」).

    <상태>/registry/ops_log.json        ②등록 — `--actor` 필수 · 재생성 불가 · fresh가 지우지 않는다

**이름으로 남기고 이름으로 되살린다.** 기록의 대상은 노드 id(ULID)인데 재구축하면 id가 바뀐다 — 그래서
연산마다 대상 전부의 **층 · canonical · 카테고리**를 `names`에 적는다(id는 `targets`에 참고로 남는다).
`ops replay`는 기록 순서대로 이름으로 대상을 찾아 **지금 손**(`ops.*` — 두 벌 0)으로 다시 한다.

  · 이미 그 상태면 건너뛴다(멱등 — 두 번 돌려도 같다) · **재생은 기록을 늘리지 않는다**(`muted`)
  · 대상 없음(이름이 지금 그래프에 없다 — 골격 이름이 바뀌었다 등)은 하지 않고 목록으로 — **기록은 지우지
    않는다**(seed를 되돌려 다시 재구축하면 그 연산이 재생된다)
  · 구판 기록(이름 없음)은 「기록에 이름 없음」으로 따로 센다
  · `I3:split`은 재생하지 않는다 — 배분표가 엣지 **번호**라 재구축 뒤 맞지 않는다(목록 · 사람이 다시 나눈다)
  · 좌표 학습 승격·거부는 파일에 남는 판단이다(골격 `ALIASES` · `coord_learned.json`) — 재생 대상이 아니다
  · 사람이 닫은 큐 항목은 연산과 같이 다시 닫힌다(`confirm`은 그 손이 닫는다 · `ops review`의 합침은
    `queue:resolve` 기록 — 쌍 확인은 ②등록 `coord_acks.json`이 따로 갖는다)

옛 자리(③ `data/ops_log.json`)는 첫 실행에서 옮긴다(`adopt_legacy` — 공통 진입 `cli/_entry.run`이 부른다 ·
두 벌 금지 — 둘 다 있으면 합치고 옛 파일을 지운다).
"""
from __future__ import annotations

import contextlib
import json

from core import paths
from core.state import log, store

_LOG = log.get(__name__)

#: 재생 중이면 연산이 기록을 늘리지 않는다(`muted`) — 재생 보고는 재구축 보고가 한다
MUTED = False

#: 재생하지 않는 연산 — 사유(목록으로 보인다)
SKIP = {"I3:split": "split — 배분표가 엣지 번호라 재구축 뒤 맞지 않는다(사람이 다시 나눈다)",
        "learn:promote": "파일에 남는 판단(골격 ALIASES)",
        "learn:reject": "파일에 남는 판단(좌표 학습 기록)"}

KINDS = ("done", "already", "missing", "no_names", "skipped", "refused")


def read():
    return store.read(store.OPS_LOG, [])


def adopt_legacy():
    """옛 자리 ③ `data/ops_log.json`을 ②등록으로 옮긴다 — 돌려주는 것은 옮긴 기록 수(없으면 0)."""
    old = paths.data(store.OPS_LOG)
    if not old.is_file():
        return 0
    olds = json.loads(old.read_text(encoding="utf-8") or "[]") or []
    cur = read()
    merged = olds + [x for x in cur if x not in olds]       # 옛 기록이 먼저다(그 뒤에 쌓였다)
    store.write(store.OPS_LOG, merged)
    old.unlink()
    (old.parent / f".{old.name}.lock").unlink(missing_ok=True)
    _LOG.info("사람 판단 기록을 ②등록으로 옮겼다 — %d건 (%s → %s)", len(olds),
              paths.show(old), paths.show(store.path(store.OPS_LOG)))
    return len(olds)


def name(n):
    """노드 → 이름 `{layer, canonical, category}` — 재생이 찾는 열쇠(없으면 None)."""
    if not n:
        return None
    return {"layer": n.get("layer"), "canonical": n.get("canonical"), "category": n.get("category")}


def append(op, actor, targets, reason, detail=None, names=None):
    """기록 한 줄 — 5요소(연산 · 행위자 · 시점 · 대상 · 사유) + **이름**(B106 ③). 재생 중이면 쓰지 않는다."""
    rec = {"op": op, "actor": actor, "at": store._now(), "targets": list(targets),
           "reason": reason, "detail": detail or {}}
    if names:
        rec["names"] = names
    if MUTED:
        return rec
    log_ = read()
    log_.append(rec)
    store.write(store.OPS_LOG, log_)
    return rec


@contextlib.contextmanager
def muted():
    global MUTED
    prev, MUTED = MUTED, True
    try:
        yield
    finally:
        MUTED = prev


# ---------------------------------------------------------------- 재생
def _all(w, nm):
    """이름에 맞는 지금 노드 id들 — 그 층 · 같은 카테고리 · canonical(norm) · 툼스톤 제외(폐기는 포함)."""
    from core.state.ids import norm
    from core.state.status import STATUS_MERGED
    if not nm:
        return []
    g = w.graphs.get(nm.get("layer"))
    pools = [g] if g is not None else list(w.graphs.values())
    want, cat = norm(nm.get("canonical") or ""), nm.get("category")
    return [n["id"] for gg in pools for n in gg.nodes.values()
            if n.get("status") != STATUS_MERGED and (cat is None or n.get("category") == cat)
            and norm(n.get("canonical") or "") == want]


def _one(w, nm):
    """살아 있는 노드 하나 — 없거나 여럿이면 None(여럿이면 고르지 않는다)."""
    from core.state.status import is_live
    hit = [i for i in _all(w, nm) if is_live(w.get(i))]
    return hit[0] if len(hit) == 1 else None


def _names_of(n):
    return {n["canonical"]} | {a["surface"] for a in n.get("aliases") or []}


def _rename(w, nm, d, a, dry):
    from core.state import ops
    node, to = nm["node"], d.get("to")
    cur = _one(w, node)
    if cur is None:
        return ("already", f"이미 '{to}'") if _one(w, dict(node, canonical=to)) else \
            ("missing", f"'{node['canonical']}' 없음")
    if not dry:
        ops.rename(node["layer"], cur, to, a["actor"], a["reason"])
    return "done", f"'{node['canonical']}' → '{to}'"


def _transfer(w, nm, d, a, dry):
    from core.state import ops
    node, par, to = nm["node"], nm.get("parent"), d.get("to")
    pid = _one(w, par)
    if pid is None:
        return "missing", f"새 부모 '{(par or {}).get('canonical')}' 없음"
    moved = _one(w, dict(node, canonical=to))
    if moved is not None and w.get(moved).get("parent") == pid:
        return "already", f"이미 '{par['canonical']}' 아래"
    cur = _one(w, node)
    if cur is None:
        return "missing", f"'{node['canonical']}' 없음"
    if not dry:
        ops.transfer(node["layer"], cur, pid, a["actor"], a["reason"])
    return "done", f"'{node['canonical']}' → '{par['canonical']}' 아래"


def _merge(w, nm, d, a, dry):
    from core.state import ops
    gone, keep, final = nm["gone"], nm["keep"], d.get("canonical")
    kid = _one(w, keep) or (_one(w, dict(keep, canonical=final)) if final else None)
    if kid is None:
        return "missing", f"남는 쪽 '{keep['canonical']}' 없음"
    gid = _one(w, gone)
    if gid is None or gid == kid:
        return (("already", f"'{gone['canonical']}'는 이미 '{w.get(kid)['canonical']}'의 이름")
                if gone["canonical"] in _names_of(w.get(kid)) else
                ("missing", f"없어질 쪽 '{gone['canonical']}' 없음"))
    if not dry:
        ops.merge(keep["layer"], gid, kid, a["actor"],
                  canonical=final if final and final != w.get(kid)["canonical"] else None,
                  override=kid, reason=a["reason"])
    return "done", f"'{gone['canonical']}' → '{keep['canonical']}'"


def _obsolete(w, nm, d, a, dry):
    from core.state import ops
    node, rb = nm["node"], nm.get("replaced_by")
    cur = _one(w, node)
    if cur is None:
        return (("already", "이미 폐기") if any(w.get(i).get("status") == ops.STATUS_OBSOLETE
                                             for i in _all(w, node)) else
                ("missing", f"'{node['canonical']}' 없음"))
    rid = _one(w, rb) if rb else None
    if rb and rid is None:
        return "missing", f"대체 '{rb['canonical']}' 없음"
    if not dry:
        ops.obsolete(node["layer"], cur, a["actor"], rid, a["reason"])
    return "done", f"'{node['canonical']}' 폐기"


def _confirm(w, nm, d, a, dry):
    from core.state import ops
    node = nm["node"]
    cur = _one(w, node)
    if cur is None:
        return "missing", f"'{node['canonical']}' 없음"
    if w.get(cur).get("status") in ("seed", "confirmed"):
        return "already", "이미 확정"
    if not dry:
        ops.confirm(node["layer"], cur, a["actor"], a["reason"])
    return "done", f"'{node['canonical']}' 확정"


def _alias(w, nm, d, a, dry):
    from core.state import ops
    from core.state.ids import norm
    node, surface = nm["node"], d.get("surface")
    cur = _one(w, node)
    if cur is None:
        return "missing", f"'{node['canonical']}' 없음"
    n = w.get(cur)
    if norm(surface) == norm(n["canonical"]) or any(x["surface"] == surface for x in n.get("aliases") or []):
        return "already", f"'{surface}'는 이미 이름"
    if not dry:
        ops.alias(node["layer"], cur, surface, a["actor"], a["reason"])
    return "done", f"'{surface}' → '{node['canonical']}'"


def _edge(w, nm, d, a, dry):
    from core.graph import STATUS_DELETED
    from core.state import ops
    s, t, rel = _one(w, nm["src"]), _one(w, nm["dst"]), d.get("rel")
    if s is None or t is None:
        return "missing", f"끝점 '{(nm['src'] if s is None else nm['dst'])['canonical']}' 없음"
    es = [e for g in w.graphs.values() for e in g.edges if (e["src"], e["rel"], e["dst"]) == (s, rel, t)]
    if not es or all(e.get("status") == STATUS_DELETED for e in es):
        return "already", "엣지가 없다(이미 지웠다)"
    if not dry:
        ops.delete_edge(nm["src"]["layer"], s, rel, t, a["actor"], a["reason"])
    return "done", f"'{nm['src']['canonical']}' —{rel}→ '{nm['dst']['canonical']}' 삭제"


def _queue(w, nm, d, a, dry):
    node, kind, dec = nm["node"], d.get("kind"), d.get("decision")

    def match(pl):
        return pl.get("canonical") == node["canonical"] and pl.get("layer") in (None, node["layer"])
    hit = [x for x in store.read(store.QUEUE, []) if x.get("kind") == kind and match(x.get("payload") or {})]
    if not hit:
        return "missing", f"큐 {kind} '{node['canonical']}' 없음"
    if all((x.get("resolution") or {}).get("decision") == dec for x in hit):
        return "already", f"이미 '{dec}'"
    if not dry:
        store.resolve_item(kind, match, actor=a["actor"], decision=dec, at=store._now(), note=a["reason"])
    return "done", f"큐 {kind} '{node['canonical']}' → '{dec}'"


_HANDS = {"I1:rename": _rename, "I5:transfer": _transfer, "I2:merge": _merge, "I4:obsolete": _obsolete,
          "I5:confirm": _confirm, "I6:alias": _alias, "edge:delete": _edge, "queue:resolve": _queue}


def replay(dry_run=False):
    """기록 순서대로 이름으로 되살린다 — `{종류: [{op, actor, at, reason, what}]}`(종류는 `KINDS`).

    `dry_run`은 계획이다(쓰기 0 — 앞 연산이 바꿀 상태를 반영하지 못하니 「할 것」의 상한이다)."""
    from core.state import ops
    from core.state.world import World
    out = {k: [] for k in KINDS}
    with muted():
        for rec in read():
            op, nm = rec.get("op"), rec.get("names")
            a = {"actor": rec.get("actor"), "reason": rec.get("reason") or ""}
            if op in SKIP:
                kind, what = "skipped", SKIP[op]
            elif not nm:
                kind, what = "no_names", "기록에 이름 없음(B106 전 기록)"
            elif op not in _HANDS:
                kind, what = "skipped", f"재생하지 않는 연산 {op}"
            else:
                try:
                    kind, what = _HANDS[op](World(), nm, rec.get("detail") or {}, a, dry_run)
                except ops.OpRefused as e:
                    kind, what = "refused", str(e).splitlines()[0]
            out[kind].append({"op": op, "actor": a["actor"], "at": rec.get("at"),
                              "reason": a["reason"], "what": what})
    return out
