# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **자리 추정**(B183 — 유일 후보) · 문서가 자리를 아예 말하지 않은 이름 규칙 카테고리의 값.

행 · 조각의 공정 칸 · 위 칸이 비고 문서 좌표 · 목차 좌표도 없는 값은 노드도 판정도 없이 보류였다(좌표 없는 스코프 개체 0 —
B102 ⑤). 그 카테고리(주 ∪ 겸)의 산 노드 전체에서 같은 것이 **하나로 정해질 때만** 그 노드에 붙는다 — 새 노드 0(자리를 모르는
노드를 세우지 않는다 · 문서 4 §4.4).

같은지 판단은 B181의 한 절차 그대로다 — 사전 · 표기 대조로 같은 이름이 한 노드면 그 노드(LLM 0) · 둘 이상이면 보류(후보 동봉 ·
LLM 0) · 없으면 뜻 판단(`matcher.decide` — 애매면 원문으로 한 번 더 · 재구축은 대장의 답) · 같다면 그 노드 · 애매 · 다르다면 보류.
후보 묶음만 넓다(공정 줄기 관문을 걸지 않는다 — 자리를 모른다) · 상한은 손잡이 `candidate_top_n`(같은 이름은 자르지 않는다).

부르는 자리 둘이 같은 함수 `attach`를 지난다 — 표의 개체 열(`loop.h_entity`) · 산문 · 제목 · 소속의 개체(`Builder._no_coord`의
빈 좌표 갈래). 붙은 값은 그 노드의 칸 `place_guess`에 남고(출처 · 표기 · 카테고리 · 열) 재연결이 다시 본다 — `recheck`(같은 이름이
다른 노드에도 서면 그 행의 출처를 걷고 보류로 되돌린다) · `reattach`(보류였던 값은 이름이 하나로 서면 붙는다) · 둘 다 LLM 0.
"""
from __future__ import annotations

from collections import Counter

from core import matcher
from core.state import store
from core.state.ids import norm
from core.state.status import is_live

#: 대장 경로 칸의 값 — 「자리 추정 — 유일 후보」(`matcher.PATHS`)
PATH = "place_guess"
LABEL = "자리 추정 — 유일 후보"
#: 노드 칸 — 이 노드에 자리 추정으로 붙은 값 `[{prov, surface, category, field?, electrode_type?}]`(재연결 · 재인입 회수가 읽는다)
FIELD = "place_guess"
#: 못 붙인 사유(닫힌 셋 — 큐 재료의 표지 `guess.why` · 대장 `guess.why` · 맞춤표 칸)
MANY, UNSURE, NONE = "같은 이름이 둘 이상의 줄기", "애매", "후보 없음"
HOLDS = (MANY, UNSURE, NONE)
#: 빈 좌표 보류의 큐 문면(`_no_coord`와 되돌림이 같은 꼴 — 키 `process_ref`)
REASON = "좌표(process_ref)가 비어 '{surface}'({category})를 만들지 않았다 — 문서 좌표(--coord) 또는 시트·제목의 공정 이름"


# ---------------------------------------------------------------- 후보 · 같은 이름
def _key(eb, surface, category):
    """조회 키 — 판정이 사전을 여는 키와 같은 함수(`build.entity_key` — 부모 없음 · 극성은 들지 않는다 — B198)."""
    from core.build.build import entity_key
    return entity_key(surface, category, eb.cfg)[0]


def _gated(eb, key, category):
    """그 카테고리(주 ∪ 겸) · home 층의 산 노드 전체 — `matcher.gated`(관문 없음 · LLM 0)."""
    return matcher.gated(key, category, eb.layer, eb.g, eb.dict, scoped=True, cfg=eb.cfg)


def _same(eb, surface, key, pre):
    """같은 이름의 노드 id — 사전 표기 · 맨 이름 · canonical · 별칭 · 표기 대조 키(`scope_path.names` — 줄기를 묻지 않는다).
    이름은 원 표기와 조회 키 둘 다로 견준다."""
    from core.build import scope_path
    from parser.namefold import key as fold
    ks = {fold(x) for x in (surface, key) if x} - {""}
    out, pool, _g = pre
    hit = set(eb.dict.lookup(surface or ""))
    ids = {c["id"] for c in out}
    for c in pool:
        if c.get("same_name") or c["id"] in hit or ks & scope_path.names(eb, eb.g.get(c["id"]) or {}):
            ids.add(c["id"])
    return sorted(ids)


def _names(eb, ids):
    return sorted((eb.g.get(i) or {}).get("canonical") for i in ids)[:matcher.HELD_TOP]


def unique(eb, surface, category, electrode_type=None):
    """같은 이름이 **한 노드**면 그 id(사전 · 표기 대조 — LLM 0) · 아니면 None. 재연결의 다시 붙음이 이것만 본다."""
    key = _key(eb, surface, category)
    same = _same(eb, surface, key, _gated(eb, key, category))
    return same[0] if len(same) == 1 else None


# ---------------------------------------------------------------- 붙이기 (인입 · 재연결)
def attach(eb, surface, category, prov, *, electrode_type=None, row=None, field=None, at=None, judge=True):
    """자리 추정 한 번 — 붙으면 노드 id · 아니면 None. 판정의 사실은 `eb.last`(대장 행이 옮긴다 — `guess` 칸 · 붙으면 경로
    `place_guess`). `judge`가 거짓이면 뜻 판단 없이(재연결 — LLM 0). 못 붙였을 때 큐에 싣는 것은 부르는 쪽 몫(표는 행 재료 ·
    산문은 값 하나 — `hold`)이고 재료의 표지는 `mark(eb.last)`."""
    from core.llm import gateway
    u0 = gateway.usage_total()
    key = _key(eb, surface, category)
    pre = _gated(eb, key, category)
    same = _same(eb, surface, key, pre)
    info = {"n": len(pre[0]) + len(pre[1])}
    v, nid, conf = None, None, 1.0
    if len(same) == 1:
        nid = same[0]
    elif same:
        info.update(why=MANY, candidates=_names(eb, same))
    elif not judge or not pre[1]:
        info["why"] = NONE
    else:
        if len(pre[1]) > matcher.candidate_top_n():
            info["cut"] = True
        v = _judge(eb, surface, key, category, pre, row, field, at)
        conf = float((v or {}).get("confidence") or 0.0)
        if v and v.get("type") == matcher.MATCH and v.get("matched_id") in eb.g.nodes:
            nid = v["matched_id"]
        elif v and v.get("type") == matcher.UNCERTAIN:
            info.update(why=UNSURE, candidates=list(v.get("candidates") or [])[:matcher.HELD_TOP])
        else:
            info["why"] = NONE
    u1 = gateway.usage_total()
    seen = {"layer": eb.layer, "guess": info, "candidates_n": info["n"],
            "llm": {"calls": u1["calls"] - u0["calls"], "in_tokens": u1["prompt_tokens"] - u0["prompt_tokens"],
                    "out_tokens": u1["completion_tokens"] - u0["completion_tokens"]}}
    if v is not None and not v.get("replayed"):         # 이번 실행이 판단했다 — 판단 수치의 곳 「개체」(B181 ⑥)
        from core.state.surface_book import ENTITY
        seen.update(place=ENTITY, answer=v.get("type"), judge2=v.get("second"))
    if nid is None:
        eb.last = {"canonical": surface, "verdict": "pending", "path": "none", "confidence": conf if v else 0.0,
                   "queue_kind": "missing_field", "node_id": None, **seen}
        return None
    by = ({"by": "LLM 매칭", "confidence": round(conf, 4), "doc": eb.doc_id} if v is not None else None)
    _land(eb, nid, surface, category, prov, key, field, electrode_type, by)
    eb.last = {"canonical": eb.g.get(nid)["canonical"], "verdict": "match", "path": PATH, "confidence": conf,
               "queue_kind": None, "node_id": nid, "category": category, **seen}
    return nid


def _judge(eb, surface, key, category, pre, row, field, at):
    """뜻 판단 — 재구축은 대장의 답(`replay.guess_row` — LLM 0) · 아니면 `matcher.decide`(같은 이름이 없는 후보 · 좁히기 그대로)."""
    from core.build import replay
    r = replay.guess_row(at, surface, eb.layer)
    if r is not None:
        mid = replay._find(eb, r.get("target"), category) if r.get("answer") == matcher.MATCH else None
        if r.get("answer") != matcher.MATCH or mid:
            return {"type": r.get("answer"), "matched_id": mid, "confidence": r.get("confidence") or 0.0,
                    "candidates": (r.get("guess") or {}).get("candidates") or [], "replayed": True}
    from core.build.extract_ctx import source_of, value_path
    cands = matcher.candidates(key, category, eb.layer, eb.g, eb.dict, scoped=True, cfg=eb.cfg, pre=pre)
    sent = source_of(row, surface, field, matcher.context_chars()) if row else None
    return matcher.decide(surface, cands, category, eb.cfg, where=value_path(row, field, eb.doc_coord), sentence=sent)


def _land(eb, nid, surface, category, prov, key, field, electrode_type, by):
    """붙인다 — 새 노드 0 · 그 노드에 출처(개체 매칭과 같은 결) · 사전 · 문서 버퍼 · 노드 칸 `place_guess`(재연결이 다시 본다)."""
    n = eb.g.get(nid)
    if prov and prov not in n["provenance"]:
        n["provenance"].append(prov)
    eb._register(surface, nid, prov, key=key, by=by)
    eb.buffer[norm(surface)] = nid
    ent = {"prov": prov, "surface": surface, "category": category,
           **({"field": field} if field else {}), **({"electrode_type": electrode_type} if electrode_type else {})}
    if ent not in n.setdefault(FIELD, []):
        n[FIELD].append(ent)


def mark(last):
    """큐 재료의 표지(B183 ② — 재연결이 다시 볼 값) `{why, candidates?}` — 못 붙인 `attach`의 사실에서."""
    g = (last or {}).get("guess") or {}
    return {"why": g.get("why") or NONE, **({"candidates": g["candidates"]} if g.get("candidates") else {})}


def hold(doc_id, prov, item):
    """값 하나의 빈 좌표 보류 — `missing_field`(키 `process_ref` · 재료 `dropped_entities` 하나 · 표지는 그 재료의 `guess`).
    `Builder._no_coord`와 되돌림(`recheck`)이 같은 꼴로 싣는다."""
    store.enqueue_rows("missing_field", REASON.format(surface=item["surface"], category=item["category"]),
                       doc_id, "process_ref",
                       {"field": "process_ref", "provenance": prov, "dropped_entities": [item]},
                       locator=(prov or "").split("#")[-1] or None)


# ---------------------------------------------------------------- 재연결 (B183 ②)
def recheck(graphs, cfgs, dic, builder, on_row):
    """**깨질 때**(B183 ②) — 자리 추정으로 붙은 값마다 같은 이름(사전 · 표기 대조 — LLM 0)의 산 노드가 둘 이상이면 그 행의 출처를
    그 노드에서 걷고(재인입 회수와 같은 손 — 노드 · 값 · 그 노드에 닿은 엣지 · 조각 연결) 보류로 되돌린다(`hold` — 후보 동봉) ·
    대장 행을 갈아 끼운다(`on_row` — by retry). 출처가 이미 없는 칸(재인입이 걷었다)은 칸만 지운다. 돌려주는 것은 되돌린 수."""
    n = 0
    for lay, g in graphs.items():
        for nid, node in list(g.nodes.items()):
            ents = node.get(FIELD)
            if not ents or not is_live(node):
                continue
            keep = []
            for e in ents:
                if e.get("prov") not in (node.get("provenance") or []):
                    continue
                did = str(e["prov"]).split("#")[0]
                b = builder(g, cfgs[lay], did, lay, dic)
                key = _key(b, e["surface"], e["category"])
                same = _same(b, e["surface"], key, _gated(b, key, e["category"]))
                if len(same) < 2:
                    keep.append(e)
                    continue
                _strip(graphs, nid, e["prov"], did)
                item = {"surface": e["surface"], "category": e["category"], "target_layer": lay,
                        **({"field": e["field"]} if e.get("field") else {}),
                        "guess": {"why": MANY, "candidates": _names(b, same)}}
                hold(did, e["prov"], item)
                b.last = {"canonical": e["surface"], "verdict": "pending", "path": "none", "confidence": 0.0,
                          "layer": lay, "queue_kind": "missing_field", "node_id": None, "candidates_n": len(same),
                          "category": e["category"],     # 대장의 같은 키 행(붙었던 행 — 카테고리가 있다)을 갈아 끼운다
                          "guess": {"n": len(same), **item["guess"]}}
                on_row(did, e["prov"], item, lay, b, None)
                n += 1
            if keep:
                node[FIELD] = keep
            else:
                node.pop(FIELD, None)
    return n


def _strip(graphs, nid, prov, did):
    """그 행의 출처를 그 노드에서 — 노드 · 값(`ingest.strip_node` — 재인입 회수와 같은 손) · 그 노드에 닿은 엣지 · 그 조각의 연결."""
    from core.build.ingest import strip_holder, strip_node
    mine = (lambda p: p == prov)
    for g in graphs.values():
        if nid in g.nodes:
            strip_node(g.nodes[nid], mine)
        for e in g.edges:
            if nid in (e["src"], e["dst"]):
                strip_holder(e, mine)
    loc = str(prov)[len(did) + 1:] if str(prov).startswith(f"{did}#") else None
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    cids = {cid for cid, c in (ch.get("chunks") or {}).items() if c.get("doc_id") == did and c.get("source_locator") == loc}
    left = [d for d in ch.get("describes") or [] if not (d.get("node_id") == nid and d.get("chunk_id") in cids)]
    if cids and len(left) != len(ch.get("describes") or []):
        ch["describes"] = left
        store.write(store.CHUNKS, ch)


def reattach(pl, item, graphs, cfgs, dic, builder, on_row):
    """**보류였던 값이 하나로 서면 붙는다**(B183 ② — 표지 `guess`가 든 재료만 · 사전 · 표기 대조 — LLM 0). 재료가 개체뿐인 행
    (산문 · 제목 · 소속 · 되돌린 값)만 본다 — 표 행의 엣지 · 값을 함께 든 보류는 재인입 · 재구축의 자리 추정이 다시 본다(D-268).
    행의 개체가 **전부** 하나로 설 때만 붙인다(일부만 붙여 행 재료를 가르지 않는다). 붙은 행은 큐 항목에서 내리고(남은 행은 그대로)
    대장 행을 갈아 끼운다(`on_row`). 돌려주는 것은 붙은 행 수."""
    did = item.get("doc_id")
    done = []
    for ent in (pl.get("items") or [pl]):
        ds = ent.get("dropped_entities") or []
        if not ds or ent.get("dropped_edges") or ent.get("pending_attrs") or not all(d.get("guess") for d in ds):
            continue
        plan = []
        for d in ds:
            lay = d.get("target_layer")
            if lay not in graphs:
                break
            b = builder(graphs[lay], cfgs[lay], did, lay, dic)
            if unique(b, d["surface"], d["category"], ent.get("electrode_type")) is None:
                break
            plan.append((d, lay, b))
        else:
            for d, lay, b in plan:
                nid = attach(b, d["surface"], d["category"], ent.get("provenance"), electrode_type=ent.get("electrode_type"),
                             field=d.get("field"), judge=False)
                b.flush()
                on_row(did, ent.get("provenance"), d, lay, b, nid)
            done.append(ent)
    if done:
        _trim(item, pl, done)
    return len(done)


def _trim(item, pl, done):
    """붙은 행을 큐 항목에서 내린다 — 다 붙었으면 항목째(`store.drop`) · 아니면 남은 행만(행 수 · 위치 표본을 맞춘다)."""
    rest = [e for e in (pl.get("items") or [pl]) if e not in done]
    if not rest:
        store.drop(item["kind"], lambda p: p == pl)
        return
    q = store.read(store.QUEUE, [])
    for x in q:
        if x.get("kind") == item["kind"] and x.get("doc_id") == item.get("doc_id") and x.get("payload") == pl:
            x["payload"] = dict(pl, items=rest, rows=len(rest),
                                locators=[loc for loc in pl.get("locators") or []
                                          if any(str(e.get("provenance") or "").endswith("#" + str(loc)) for e in rest)])
    store.write(store.QUEUE, q)


# ---------------------------------------------------------------- 보이기 (B183 ③)
_ROLES = ("entity", "belongs", "heading")


def counts(rows):
    """「자리 없는 값」 칸 — 대장 행의 `guess` 칸에서(새 계산 0): 붙음 · 보류(사유별) · 상한에 잘림 · 한 조각에서 갈림."""
    g = [r for r in rows or [] if r.get("guess") is not None and r.get("role") in _ROLES]
    if not g:
        return None
    held = Counter((r["guess"].get("why") or NONE) for r in g if r.get("path") != PATH)
    split = {}
    for r in g:
        if r.get("path") == PATH and r.get("target"):
            split.setdefault(r.get("locator"), set()).add(str(r["target"]).split("::")[0])
    return {"값": len(g), "붙음": sum(1 for r in g if r.get("path") == PATH), "보류": sum(held.values()),
            "사유": {k: held.get(k, 0) for k in HOLDS}, "잘림": sum(1 for r in g if r["guess"].get("cut")),
            "갈림": sum(1 for s in split.values() if len(s) > 1)}


def line(c):
    """`자리 없는 값 n — 자리 추정 a(유일 후보) · 보류 b(줄기 둘 이상 c · 애매 d · 후보 없음 e) · 상한에 잘림 k` · 없으면 None."""
    if not c:
        return None
    s = c["사유"]
    return (f"자리 없는 값 {c['값']:,} — 자리 추정 {c['붙음']:,}(유일 후보) · 보류 {c['보류']:,}(줄기 둘 이상 {s[MANY]:,} · "
            f"애매 {s[UNSURE]:,} · 후보 없음 {s[NONE]:,}) · 상한에 잘림 {c['잘림']:,}"
            + (f" · 한 조각에서 다른 공정으로 갈림 {c['갈림']:,}" if c["갈림"] else ""))


# ---------------------------------------------------------------- 사람 손 (B184 ④ — 인입 뒤 한 화면)
#: 사람 판단 기록의 연산 — 맞음은 화면 표지(재생 0) · 떼기 · 고르기는 재구축 뒤 재생이 다시 한다(`oplog._HANDS`)
OP_OK, OP_DETACH, OP_PICK = "guess:confirm", "guess:detach", "guess:pick"


def _graphs():
    from core.state.bootstrap import load_config, open_graph
    from router import discover
    lays = discover()
    return {lay: open_graph(lay) for lay in lays}, {lay: load_config(lay) for lay in lays}


def _human(op):
    """그 연산의 사람 기록 `{(출처, 표기)}`(맞음 · 떼기)."""
    from core.state import oplog
    return {((r.get("detail") or {}).get("prov"), (r.get("detail") or {}).get("surface")) for r in oplog.read()
            if r.get("op") == op}


def attached(layer=None):
    """자리 추정으로 붙은 값 — 노드 칸 `place_guess` 그대로(출처가 산 것 · 쓰기 0) · 그 노드와 부딪힌 값(`spec_conflict` — 그 출처) ·
    사람이 「맞음」을 친 것은 `ok`."""
    graphs, _c = _graphs()
    ok = _human(OP_OK)
    sc = [x for x in store.read(store.QUEUE, []) if x.get("kind") == "spec_conflict" and not x.get("resolution")]
    out = []
    for lay, g in graphs.items():
        if layer not in (None, "all", lay):
            continue
        for nid, n in g.nodes.items():
            for e in n.get(FIELD) or [] if is_live(n) else []:
                if e.get("prov") not in (n.get("provenance") or []):
                    continue
                hit = [x["payload"] for x in sc if (x.get("payload") or {}).get("node_id") == nid
                       and (x.get("payload") or {}).get("provenance") == e["prov"]]
                out.append({"layer": lay, "node_id": nid, "canonical": n["canonical"], "ok": (e["prov"], e["surface"]) in ok,
                            "doc": str(e["prov"]).split("#")[0], "conflict": [f"{p['attr']} {p['incoming']} ↔ {p['existing']}"
                                                                           for p in hit], **e})
    return out


def detach(layer, nid, prov, surface, actor, reason=""):
    """**떼기** — 그 행의 출처를 그 노드에서 걷고(되돌림과 같은 손 `_strip`) 빈 좌표 보류로(`hold` — 표지 `guess` 없음: 다시 붙음이
    보지 않는다 · 사람이 뗐다) · 칸에서 내린다 · 기록(재구축 뒤 재생이 다시 뗀다). 돌려주는 것은 뗀 값(없으면 None)."""
    from core.state.ops import log_op
    graphs, _c = _graphs()
    n = graphs[layer].get(nid) or {}
    ent = next((e for e in n.get(FIELD) or [] if e.get("prov") == prov and e.get("surface") == surface), None)
    if ent is None:
        return None
    did = str(prov).split("#")[0]
    _strip(graphs, nid, prov, did)
    hold(did, prov, {"surface": surface, "category": ent["category"], "target_layer": layer,
                     **({"field": ent["field"]} if ent.get("field") else {})})
    rest = [e for e in n.get(FIELD) or [] if e != ent]          # 회수 손(`strip_node`)이 이미 내렸을 수 있다
    if rest:
        n[FIELD] = rest
    else:
        n.pop(FIELD, None)
    for g in graphs.values():
        g.save()
    log_op(OP_DETACH, actor, [nid], reason, {"prov": prov, "surface": surface, "category": ent["category"]},
           {"node": {"layer": layer, "canonical": n["canonical"], "category": n["category"]}})
    return ent


def confirm(layer, nid, prov, surface, actor, reason=""):
    """**맞음** — 확인 표지(사람 판단 기록 · 다음 화면은 접어 둔다 · 그래프 쓰기 0)."""
    from core.state.ops import log_op
    graphs, _c = _graphs()
    n = graphs[layer].get(nid) or {}
    log_op(OP_OK, actor, [nid], reason, {"prov": prov, "surface": surface},
           {"node": {"layer": layer, "canonical": n.get("canonical"), "category": n.get("category")}})


def held():
    """**후보가 있는 자리 없는 값 보류** — `missing_field` 재료 중 표지 `guess.candidates`가 든 값(사람 판단 없는 것)."""
    out = []
    for x in store.read(store.QUEUE, []):
        if x.get("kind") != "missing_field" or x.get("resolution"):
            continue
        pl = x.get("payload") or {}
        for ent in pl.get("items") or [pl]:
            for d in ent.get("dropped_entities") or []:
                c = (d.get("guess") or {}).get("candidates")
                if c:
                    out.append({"doc": x.get("doc_id"), "prov": ent.get("provenance"), "surface": d["surface"],
                                "category": d["category"], "layer": d.get("target_layer"), "candidates": list(c),
                                "why": d["guess"].get("why"), "electrode_type": ent.get("electrode_type"),
                                **({"field": d["field"]} if d.get("field") else {})})
    return out


def pick(row, target, actor, reason=""):
    """**후보 고르기** — 사람이 고른 후보(`target` canonical)에 붙인다(붙이기와 같은 손 `_land` · 출처 사람) · 그 값을 큐에서 내린다 ·
    기록(재구축 뒤 재생이 다시 고른다). 돌려주는 것은 노드 id(대상이 없으면 None)."""
    from core.build.retry import _builder
    from core.dictionary import Dictionary
    from core.state.ops import log_op
    graphs, cfgs = _graphs()
    lay = row["layer"]
    g = graphs.get(lay)
    nid = next((i for i, n in (g.nodes.items() if g else ()) if n["canonical"] == target and is_live(n)), None)
    if nid is None:
        return None
    dic = Dictionary.open()
    b = _builder(g, cfgs[lay], row["doc"], lay, dic)
    key = _key(b, row["surface"], row["category"])
    _land(b, nid, row["surface"], row["category"], row["prov"], key, row.get("field"), row.get("electrode_type"),
          {"by": "사람", "actor": actor})
    b.flush()
    g.save()
    dic.save()
    _unqueue(row)
    log_op(OP_PICK, actor, [nid], reason, {"prov": row["prov"], "surface": row["surface"], "category": row["category"],
                                           "doc": row["doc"], "field": row.get("field"), "electrode_type": row.get("electrode_type")},
           {"node": {"layer": lay, "canonical": target, "category": g.get(nid)["category"]}})
    return nid


def _unqueue(row):
    """그 값 하나를 `missing_field`에서 내린다 — 행의 재료가 비면 행째 · 항목이 비면 항목째."""
    q = store.read(store.QUEUE, [])
    keep = []
    for x in q:
        pl = x.get("payload") or {}
        if x.get("kind") == "missing_field" and x.get("doc_id") == row["doc"]:
            ents = pl.get("items") or [pl]
            for ent in ents:
                if ent.get("provenance") == row["prov"]:
                    ent["dropped_entities"] = [d for d in ent.get("dropped_entities") or [] if d.get("surface") != row["surface"]]
            ents = [e for e in ents if e.get("dropped_entities") or e.get("dropped_edges") or e.get("pending_attrs")]
            if not ents:
                continue
            if pl.get("items") is not None:
                x["payload"] = dict(pl, items=ents, rows=len(ents))
        keep.append(x)
    store.write(store.QUEUE, keep)
