# -*- coding: utf-8 -*-
"""n5 — I축 인스턴스 변경 도구 4연산 (틀 §4B-A2, 카드 L5~L9·G6).

    I1 개명 · I2 병합 · I3 분리 · I4 폐기   (+ 엣지 삭제 — 사람이 지운 엣지)

**L1~L4(구조 변경)와 직교하는 축이다.** 여기는 "무엇을 아는가"가 아니라 "그 앎을
어느 노드에 담는가"를 사후에 고치는 도구이며, 문서 재인입으로는 고칠 수 없는 것만 한다.

관통하는 원칙 넷:
  · **삭제하지 않는다.** 병합은 툼스톤, 폐기는 status 전환이다. 옛 id를 참조하는
    답변·문서가 있고, 지우면 재인입이 그것을 부활시킨다(L5·L9).
  · **정보를 잃지 않는다.** 선택되지 않은 표기는 전부 alias로 남고 provenance는
    전량 이관된다 — 그래서 "어느 문서에서 온 지식인가"가 병합 뒤에도 조회된다(L7).
  · **파급이 1건을 넘으면 실행 전에 보여준다**(G6). 미리보기 없이 도는 연산은 없다.
  · **순환은 2겹으로 막는다**(L8) — 쓰기 시점 거부 + 읽기 시점 방문집합·깊이 제한.

**코드에 층 어휘 0**(B1) — 카테고리·관계·극성 값이 이 파일에 없다. 스코프 구분자와
연쇄 대상 판정은 층 config가 값으로 준다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import store
from .dictionary import Dictionary
from .graph import STATUS_DELETED, GraphStore
from .ids import norm

# 읽기 추적의 최대 깊이 — 조절점(코드 상수, 초과는 결함 로그. L8).
MAX_CHAIN = 16

STATUS_MERGED = "merged_into"
STATUS_OBSOLETE = "obsolete"

# 병합 생존자의 status 등급 — **높은 쪽이 이긴다** (R3-⑴ 2순위).
# seed가 관여하면 생존자는 무조건 seed다. auto가 seed를 흡수하면 골격이 데이터
# 조작으로 훼손되고, 그 복구 경로는 I1 개명이나 seed 개정이지 병합이 아니다.
STATUS_RANK = {"seed": 3, "registered": 2, "auto": 1}


class OpRefused(Exception):
    """쓰기 거부 — 조용히 넘어가지 않는다. 사유를 들고 멈춘다."""


def is_live(node):
    """툼스톤인가 아닌가.

    **툼스톤은 `canonical`을 그대로 지닌다** — 옛 이름을 화면에 보여 주기 위해서다.
    그래서 canonical로 노드를 찾는 코드는 반드시 이 판정을 거쳐야 한다. 안 거치면
    옛 이름이 산 노드를 가리는 사고가 난다(실측: 병합 툼스톤을 폐기 처리해 한 노드가
    `merged_into`와 `obsolete`를 동시에 갖는 모순 상태가 됐다).
    """
    return bool(node) and node.get(STATUS_MERGED) is None


def _target(g, nid):
    """I축 연산의 대상 노드를 집는다 — **툼스톤은 대상이 아니다.**

    이미 병합·분리로 내용이 다른 곳으로 옮겨간 id를 다시 고치는 것은 의미가 없고,
    허용하면 서로 모순되는 status가 한 노드에 쌓인다. 옛 id는 리다이렉트용이다.
    """
    n = g.get(nid)
    if n is None:
        raise OpRefused(f"대상 노드가 없다: {nid}")
    if not is_live(n):
        raise OpRefused(f"툼스톤은 연산 대상이 아니다 — 생존자 {n[STATUS_MERGED]}를 쓰라")
    return n


# ---------------------------------------------------------------- 공통
def _cfg(layer):
    from .bootstrap import load_config
    return load_config(layer)


def _sep(cfg):
    return (cfg.get("canonical_scope") or {}).get("sep", "::")


def _now():
    """연산 시점 — 로그 5요소의 하나다. 상수로 두면 그 자리가 **위조값**이 된다."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_op(op, actor, targets, reason, detail=None):
    """연산 로그 — **큐가 아니라 로그다**(D-7 계보). 처리 대상이 아니라 이력이다.

    5요소를 전부 적는다: 연산 · **행위자** · 시점 · 대상 · 사유.
    행위자 없는 I축 연산은 거부한다 — 누가 그래프를 고쳤는지 모르면 로그가 로그가 아니다.
    """
    log = store.read(store.OPS_LOG, [])
    log.append({"op": op, "actor": actor, "at": _now(),
                "targets": list(targets), "reason": reason, "detail": detail or {}})
    store.write(store.OPS_LOG, log)
    return log[-1]


def resolve_chain(graph, nid, field, depth=0, seen=None):
    """툼스톤 체인 추적 — **방문집합 + 깊이 제한**, 초과는 결함 로그(L8 읽기 측).

    조용히 멈추지 않는다. 순환은 쓰기에서 이미 막지만, 읽기 측 방어를 함께 두는 것은
    데이터가 다른 경로로 오염됐을 때 질의가 무한히 도는 것을 막기 위해서다.
    """
    seen = seen or set()
    cur = nid
    while True:
        n = graph.get(cur)
        if n is None or n.get(field) in (None, ""):
            return cur
        if cur in seen:
            store.append_defect(f"ops: {field} 체인 순환 — {cur}")
            return cur
        seen.add(cur)
        if len(seen) > MAX_CHAIN:
            store.append_defect(f"ops: {field} 체인 깊이 {MAX_CHAIN} 초과 — {nid}")
            return cur
        cur = n[field]


# ---------------------------------------------------------------- 파급 미리보기
def preview(layer, op, nid, **kw):
    """실행 **전에** 파급을 제시한다 (카드 G6 — 1건을 넘는 작업은 전부 대상).

    보여주는 것 셋: 영향 노드 수 · 영향 엣지 수 · **canonical 연쇄 대상 목록**.
    개명이 무서운 이유는 자기 이름이 아니라 자식들의 이름이 함께 바뀌기 때문이고,
    그 목록을 못 보면 사람이 승인할 근거가 없다.
    """
    g = GraphStore.for_layer(layer).load()
    cfg = _cfg(layer)
    node = g.get(nid)
    if node is None:
        raise OpRefused(f"대상 노드가 없다: {nid}")
    edges = [e for e in g.edges if e["src"] == nid or e["dst"] == nid]
    chained = _scope_children(g, node["canonical"], cfg) if op == "rename" else []
    if op == "merge":
        other = g.get(kw.get("into"))
        edges += [e for e in g.edges
                  if other and (e["src"] == other["id"] or e["dst"] == other["id"])]
    return {"op": op, "target": node["canonical"], "nodes": 1 + len(chained),
            "edges": len(edges),
            "canonical_chain": [c["canonical"] for c in chained]}


def _scope_children(g, parent_canonical, cfg):
    """스코프 접두로 그 노드에 매달린 자식들 — canonical 연쇄의 대상.

    스코프가 걸린 카테고리만 본다(config `canonical_scope.bind_categories`).
    부모 개명이 자식 이름을 끌고 가는 것은 **스코프가 주소이기 때문**이며,
    주소가 아닌 카테고리는 연쇄 대상이 아니다.
    """
    sc = cfg.get("canonical_scope") or {}
    binds, sep = sc.get("bind_categories", []), _sep(cfg)
    pre = parent_canonical + sep
    return [n for n in g.nodes.values()
            if is_live(n) and n["category"] in binds
            and n["canonical"].startswith(pre)]


# ---------------------------------------------------------------- I1 개명
def rename(layer, nid, new_canonical, actor, reason="", dry_run=False):
    """I1 — canonical 변경. **id 불변**(P4) · 옛 canonical은 **alias로 자동 강등** ·
    스코프 자식 canonical **연쇄 변경**.

    옛 이름을 alias로 남기는 것이 핵심이다 — 문서에는 옛 이름이 계속 나오므로
    사라지면 재매칭이 깨져 같은 개념에 새 노드가 선다.
    """
    if not actor:
        raise OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    g = GraphStore.for_layer(layer).load()
    cfg = _cfg(layer)
    node = _target(g, nid)
    old = node["canonical"]
    if any(n["canonical"] == new_canonical and n["category"] == node["category"]
           and n["id"] != nid and is_live(n) for n in g.nodes.values()):
        raise OpRefused(f"같은 카테고리에 '{new_canonical}'가 이미 있다 — 개명이 아니라 병합이다")
    pv = preview(layer, "rename", nid)
    if dry_run:
        return pv

    children = _scope_children(g, old, cfg)
    sep = _sep(cfg)
    dictionary = Dictionary.open()       # 사전 접근은 관문 경유로만 (문서 7 §7.1)

    def _rename_one(n, new_name):
        prev = n["canonical"]
        n["canonical"] = new_name
        if not any(a["surface"] == prev for a in n["aliases"]):
            n["aliases"].append({"surface": prev, "provenance": [f"op:rename:{actor}"]})
        prov = f"op:rename:{actor}"
        dictionary.register(prev, n["id"], provenance=prov)      # 옛 이름으로도 찾힌다
        dictionary.register(new_name, n["id"], provenance=prov)

    _rename_one(node, new_canonical)
    for c in children:                                       # 연쇄 — 주소가 바뀌었으므로
        _rename_one(c, new_canonical + c["canonical"][len(old):])
    if node.get("mirror_scope") == old:
        node["mirror_scope"] = new_canonical
    for c in g.nodes.values():
        if c.get("mirror_scope") == old:
            c["mirror_scope"] = new_canonical
    dictionary.save()
    g.save()
    log_op("I1:rename", actor, [nid], reason,
           {"from": old, "to": new_canonical, "chained": pv["canonical_chain"]})
    return pv


# ---------------------------------------------------------------- I2 병합
def merge_candidates(g, a, b):
    """canonical 후보 — **id 선택과 분리**한다(L7). 빈도·출처 등급을 함께 제시한다.

    빈도를 자동 규칙으로 쓰지 않는 이유: 복사·붙여넣기로 **오타가 반복 등장**할 수
    있어서다. 그래서 여기는 제시만 하고 확정은 사람이 한다. USE_MOCK의 "1추천"은
    결정적 규칙(빈도 최다 → 동률이면 status 등급 → 그래도 동률이면 정렬상 앞)이며
    실물 경로에서는 LLM이 그 자리에 온다.
    # HOOK: llm_canonical_suggest
    """
    out = []
    for n in (a, b):
        surfaces = [(n["canonical"], len(n["provenance"]), n["status"])]
        surfaces += [(al["surface"], len(al.get("provenance") or []), n["status"])
                     for al in n["aliases"]]
        for s, freq, st in surfaces:
            out.append({"canonical": s, "freq": freq, "status": st,
                        "rank": STATUS_RANK.get(st, 0)})
    out.sort(key=lambda c: (-c["freq"], -c["rank"], c["canonical"]))
    return out


def merge_targets(layer, nid, limit=5):
    """**병합 상대 후보를 제안한다** — 판정은 `matcher.match`가 한다(문서 7 §7.1).

    문서 4가 attach_to 해소·orphan 재시도·**병합 후보** 세 곳에서 판정 파이프라인
    재사용을 요구한다. 재사용 대상이 없으면 지점마다 별도 판정 코드가 생겨,
    카테고리 불일치 안전망·극성 후보 제외·생존 판정(is_live)이 한 곳에만 적용된다.

    **제안뿐이고 자동 병합은 없다**(I2는 사람 확인 연산이다 — 문서 4 §4.7).
    돌려주는 것은 `[{id, canonical, confidence}]`이고 `merge()`의 `into` 인자에
    사람이 골라 넣는다. 그래서 `uncertain`도 함께 낸다 — 확신되지 않은 후보를
    감추면 사람이 볼 것이 줄어들고, 판정을 감춘 자리에서 오병합이 난다.
    """
    from . import matcher
    from .bootstrap import open_graph
    from .dictionary import Dictionary

    g = open_graph(layer)
    node = g.get(nid)
    if node is None or not is_live(node):
        return []
    cands = [c for c in matcher.candidates(
        node["canonical"], node["category"], node.get("layer") or layer,
        g, Dictionary.open(), polarity=node.get("polarity"))
        if c["id"] != nid]
    out = []
    for c in cands:
        v = matcher.match(node["canonical"], [dict(c, exact=False)], node["category"])
        if v["type"] in (matcher.MATCH, matcher.UNCERTAIN) and v["confidence"] > 0:
            out.append({"id": c["id"], "canonical": c["canonical"],
                        "confidence": v["confidence"], "verdict": v["type"]})
    out.sort(key=lambda x: -x["confidence"])
    return out[:limit]


def _survivor(a, b, override=None):
    """생존자 3단 규칙 (R3-⑴).

    ①사람 override는 **항상 최상위** ②status 등급(seed > registered > auto)
    ③정렬상 앞선 id(ULID = 생성순이라 결정적).

    ②가 ③보다 위인 이유는 정확성이 아니라 **골격 보호**다 — auto가 seed를 흡수하면
    골격이 데이터 조작으로 훼손되는데, "정렬상 앞선 id" 단일 규칙은 그것을 못 막는다.
    """
    if override:
        if override not in (a["id"], b["id"]):
            raise OpRefused(f"override id가 병합 대상이 아니다: {override}")
        return (a, b) if override == a["id"] else (b, a)
    ra, rb = STATUS_RANK.get(a["status"], 0), STATUS_RANK.get(b["status"], 0)
    if ra != rb:
        return (a, b) if ra > rb else (b, a)
    return (a, b) if a["id"] <= b["id"] else (b, a)


def _merge_attrs(g, layer, keep, gone):
    """흡수 노드의 attribute를 **인입 경로의 병합 규칙으로** 생존자에 합친다.

    구판은 `setdefault` 한 줄이라 **이름이 같으면 흡수측 값을 통째로 버렸다** — 값도
    provenance도 무기록 소실이라 "정보 손실 0" 계약이 정면으로 깨졌다. 자체 병합 로직을
    새로 쓰지 않고 `Builder.put_attribute`를 그대로 부른다: 같은 이름은 context 그룹별로
    합쳐지고, 같은 그룹의 다른 값은 `spec_conflict` 큐로 간다(3.7 I2 문면 그대로).
    """
    from .build import Builder
    b = Builder(g, _cfg(layer), None, None, keep["layer"])
    for name, val in (gone.get("attrs") or {}).items():
        items = val if isinstance(val, list) else [
            {"context": {}, "value": (val or {}).get("value"),
             "provenance": (val or {}).get("provenance") or []}]
        for it in items:
            for prov in (it.get("provenance") or ["op:merge"]):
                b.put_attribute(keep["id"], name, it.get("value"),
                                it.get("context") or {}, prov, True)


def _move_edges(g, gone_id, keep_id):
    """엣지 이설 — **`add_edge` 경유**다. 치환만 하면 계약 둘이 동시에 깨진다.

    ①`(src, rel, dst)` 유일성 — 같은 대상으로 각각 엣지를 갖던 두 노드를 합치면 물리
    중복이 생기고 provenance가 갈라진다(합집합이어야 한다). ②**자기참조** — 서로를
    가리키던 두 노드가 합쳐지면 자기 루프가 되는데, 그것은 참 관계가 아니라 병합의
    부산물이다(실측: 질의가 "X는 X의 원인"을 사실로 출력). 이설하지 않고 기록만 남긴다.
    """
    moved = [e for e in g.edges if gone_id in (e["src"], e["dst"])]
    for e in moved:
        g.edges.remove(e)
    for e in moved:
        src = keep_id if e["src"] == gone_id else e["src"]
        dst = keep_id if e["dst"] == gone_id else e["dst"]
        if src == dst:
            store.append_defect(
                f"merge: 자기참조가 되는 엣지는 이설하지 않는다 — {e['rel']} @ {keep_id}")
            continue
        g.add_edge(src, e["rel"], dst, e["status"], e["provenance"])


def merge(layer, nid, into, actor, canonical=None, override=None,
          reason="", dry_run=False):
    """I2 — 두 노드를 하나로. **정보 손실 0**이 계약이다.

    provenance·alias·엣지·attribute가 전부 생존자로 이관되고, 흡수 id에는
    `merged_into` 툼스톤만 남는다 — 내용은 생존자에 있으므로 중복 저장이 아니고,
    용도는 옛 id 참조의 리다이렉트 하나다.
    """
    if not actor:
        raise OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    g = GraphStore.for_layer(layer).load()
    a, b = _target(g, nid), _target(g, into)
    if a["id"] == b["id"]:
        raise OpRefused("자기 자신과 병합할 수 없다")
    if a["status"] == "seed" and b["status"] == "seed":
        raise OpRefused("seed끼리는 병합하지 않는다 — 골격 변경의 정본 경로는 "
                        "I1 개명 또는 seed 개정이다 (L5)")
    # 순환 방어 ① 쓰기 거부 — 상대가 이미 내 체인 위에 있으면 고리가 된다
    if resolve_chain(g, b["id"], STATUS_MERGED) == a["id"] or \
            a.get(STATUS_MERGED) or b.get(STATUS_MERGED):
        raise OpRefused("merged_into 체인에 순환이 생긴다 — 거부 (L8)")

    keep, gone = _survivor(a, b, override)
    pv = preview(layer, "merge", keep["id"], into=gone["id"])
    pv["survivor"] = keep["canonical"]
    pv["canonical_candidates"] = merge_candidates(g, a, b)
    if dry_run:
        return pv

    for p in gone["provenance"]:                             # provenance 전량 이관
        if p not in keep["provenance"]:
            keep["provenance"].append(p)
    seen = {al["surface"] for al in keep["aliases"]}
    for al in gone["aliases"] + [{"surface": gone["canonical"],
                                  "provenance": list(gone["provenance"])}]:
        if al["surface"] not in seen and al["surface"] != keep["canonical"]:
            keep["aliases"].append(al)                       # 선택 안 된 표기도 남는다
            seen.add(al["surface"])
    _merge_attrs(g, layer, keep, gone)
    _move_edges(g, gone["id"], keep["id"])                   # 엣지 이설
    if canonical and canonical != keep["canonical"]:         # 사람 확정
        if not any(a2["surface"] == keep["canonical"] for a2 in keep["aliases"]):
            keep["aliases"].append({"surface": keep["canonical"],
                                    "provenance": [f"op:merge:{actor}"]})
        keep["canonical"] = canonical
    keep["status"] = keep["status"] if STATUS_RANK.get(keep["status"], 0) >= \
        STATUS_RANK.get(gone["status"], 0) else gone["status"]

    g.nodes[gone["id"]] = {"id": gone["id"], STATUS_MERGED: keep["id"],
                           "status": STATUS_MERGED, "at": _now(),
                           "canonical": gone["canonical"], "category": gone["category"],
                           "layer": gone["layer"], "attrs": {}, "aliases": [],
                           "provenance": []}
    dictionary = Dictionary.open()
    dictionary.redirect(gone["id"], keep["id"])
    for al in keep["aliases"]:                               # 이관된 표기도 찾히게
        dictionary.register(al["surface"], keep["id"],
                            provenance=(al.get("provenance") or [f"op:merge:{actor}"])[0])
    dictionary.save()
    g.save()
    log_op("I2:merge", actor, [gone["id"], keep["id"]], reason,
           {"survivor": keep["id"], "canonical": keep["canonical"]})
    return pv


# ---------------------------------------------------------------- I3 분리
def split(layer, nid, plan, actor, reason="", dry_run=False):
    """I3 — **자동 불가**(L5). 배분표 없이는 거부한다.

    배분표(JSON): `{"targets": [{"canonical": …, "aliases": [표면형…],
    "provenance": [출처…], "edges": [엣지 인덱스…]}, …]}`

    **지정되지 않은 잔여가 있으면 실행을 거부하고 잔여 목록을 출력한다**(R3-⑵).
    조용히 한쪽에 몰아 넣으면 사람이 그것을 영영 모른다 — 분리가 어려운 이유가
    바로 "어느 것이 어느 쪽인지"이고, 그 판단을 코드가 대신할 수 없다.
    """
    if not actor:
        raise OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    if not plan or not plan.get("targets"):
        raise OpRefused("배분표가 없다 — 자동 분리 경로는 없다 (L5)")
    g = GraphStore.for_layer(layer).load()
    node = _target(g, nid)

    own_edges = [i for i, e in enumerate(g.edges)
                 if e["src"] == nid or e["dst"] == nid]
    left = {"aliases": {al["surface"] for al in node["aliases"]},
            "provenance": set(node["provenance"]), "edges": set(own_edges)}
    for t in plan["targets"]:
        # 새 노드의 canonical로 승격된 표기도 **배분된 것**이다 — 잃은 것이 아니라
        # 이름이 됐다. 그것까지 잔여로 세면 배분표를 쓸 수 없다.
        left["aliases"] -= set(t.get("aliases") or []) | {t["canonical"]}
        left["provenance"] -= set(t.get("provenance") or [])
        left["edges"] -= set(t.get("edges") or [])
    residual = {k: sorted(v) for k, v in left.items() if v}
    if residual:
        raise OpRefused(f"배분표에 지정되지 않은 잔여가 있다 — 실행 거부: {residual}")

    pv = {"op": "split", "target": node["canonical"], "nodes": len(plan["targets"]),
          "edges": len(own_edges),
          "canonical_chain": [t["canonical"] for t in plan["targets"]]}
    if dry_run:
        return pv

    dictionary = Dictionary.open()
    new_ids = []
    for t in plan["targets"]:
        new = g.add_node(t["canonical"], node["category"], node["status"],
                         attrs=dict(node.get("attrs") or {}),
                         provenance=list(t.get("provenance") or []),
                         aliases=[{"surface": s, "provenance": [f"op:split:{actor}"]}
                                  for s in (t.get("aliases") or [])],
                         polarity=node.get("polarity", "none"),
                         mirror_scope=node.get("mirror_scope"),
                         mirror_name=node.get("mirror_name"))
        new_ids.append(new)
        for i in (t.get("edges") or []):
            e = g.edges[i]
            g.add_edge(new if e["src"] == nid else e["src"], e["rel"],
                       new if e["dst"] == nid else e["dst"],
                       e["status"], e["provenance"])
        prov = f"op:split:{actor}"                  # 배분은 사람 판단이 근거다
        dictionary.register(t["canonical"], new, provenance=prov)
        for s in (t.get("aliases") or []):
            dictionary.register(s, new, provenance=prov)

    # 원본은 첫 산출물로 리다이렉트한다 — 삭제하지 않는다(옛 id 참조 보존)
    for i in own_edges:
        g.edges[i]["status"] = STATUS_DELETED
    g.nodes[nid] = {"id": nid, STATUS_MERGED: new_ids[0], "status": STATUS_MERGED,
                    "at": _now(), "canonical": node["canonical"],
                    "category": node["category"], "layer": node["layer"],
                    "attrs": {}, "aliases": [], "provenance": []}
    # 배분표가 각 표기를 자기 타깃에 이미 등재했다 — 여기서는 **옛 id만 걷는다.**
    # 병합용 리다이렉트를 그대로 쓰면 다른 타깃에 배분된 표기까지 첫 산출물을 가리켜
    # 한 표기가 두 노드를 동시에 가리킨다(사전 오염 — 조용한 유실 금지의 반대편).
    dictionary.redirect(nid, None)      # new_id=None → 걷어만 낸다
    dictionary.save()
    g.save()
    log_op("I3:split", actor, [nid] + new_ids, reason, {"targets": new_ids})
    return pv


# ---------------------------------------------------------------- I4 폐기
def obsolete(layer, nid, actor, replaced_by=None, reason="", dry_run=False):
    """I4 — **삭제하지 않는다.** `status: obsolete` + `replaced_by` + 사유 + 시점.

    이유 둘: ①옛 문서·답변이 그 id를 참조한다 ②지우면 재인입이 부활시킨다(L5·L9).
    질의 노출은 R3-⑶ — 기본 비노출·전이 답변이며 침묵 소실은 금지다.
    """
    if not actor:
        raise OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    g = GraphStore.for_layer(layer).load()
    node = _target(g, nid)
    if replaced_by:
        if g.get(replaced_by) is None:
            raise OpRefused(f"replaced_by 대상이 없다: {replaced_by}")
        if resolve_chain(g, replaced_by, "replaced_by") == nid:
            raise OpRefused("replaced_by 체인에 순환이 생긴다 — 거부 (L8)")
    pv = preview(layer, "obsolete", nid)
    if dry_run:
        return pv
    node["status"] = STATUS_OBSOLETE
    node["replaced_by"] = replaced_by
    node["obsoleted_at"] = _now()
    node["obsolete_reason"] = reason
    g.save()
    log_op("I4:obsolete", actor, [nid], reason, {"replaced_by": replaced_by})
    return pv


# ---------------------------------------------------------------- 엣지 삭제
def delete_edge(layer, src, rel, dst, actor, reason=""):
    """사람이 지운 엣지 — 툼스톤을 남긴다. **재인입이 되살리지 못한다**(명세 §5.5-3).

    `GraphStore.add_edge`가 툼스톤 (src,rel,dst)를 건너뛰는 것이 그 집행이며,
    여기서는 그 툼스톤을 심는다.
    """
    if not actor:
        raise OpRefused("행위자 미지정 — I축 연산은 로그에 행위자를 남긴다")
    g = GraphStore.for_layer(layer).load()
    hit = [e for e in g.edges if (e["src"], e["rel"], e["dst"]) == (src, rel, dst)]
    if not hit:
        raise OpRefused("그런 엣지가 없다")
    for e in hit:
        e["status"] = STATUS_DELETED
    g._reindex_tombstones()
    g.save()
    log_op("edge:delete", actor, [src, dst], reason, {"rel": rel})
    return {"op": "delete_edge", "edges": len(hit)}
