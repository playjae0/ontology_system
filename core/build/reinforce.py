# -*- coding: utf-8 -*-
"""칸 3.4 — **연결 보강** — 재연결이 멈춘 뒤에도 엣지가 없거나 공정에만 붙은 개체를 닫힌 후보 안에서 잇는다
(B115 ④ · LLM 지점 ⑫ · 사용자 2026-10-15 「LLM이 정보를 보고 연결할 수 있는 부분이 많다 — 추출과 연결 둘 다」).

  · **언제** — 빌드 말미(`entry.finalize`): 미러 · 재연결 바퀴(B113 ③ — 붙음 0에서 멈춘다)가 끝난 **뒤** · 이 실행이
    구축한 문서만(`entry.BUILT`).
  · **대상** — 그 문서 대장의 개체 행 중 노드가 **엣지 0**이거나 **골격 좌표에만 붙은** 것(노드마다 한 번 · 위치가
    청크인 행만 — 근거 원문이 있어야 한다).
  · **입력(자기 청크만)** — 개체(이름 · 카테고리) + 그 개체가 나온 청크 원문(맥락 줄 포함 · 다른 청크 본문 0) + 조상
    제목 개체(가까운 것부터) + **닫힌 후보**(`candidates` — 같은 문서 · 같은 제목 서브트리의 노드 · 가까운 것부터 ·
    상한 `CAND_MAX`) + 관계 목록.
  · **출력** — `{"pick": {id, rel|null, evidence} | null}`. 후보 밖 id · 원문에 없는 근거 문장 · 게이트를 못 지나는
    관계는 **버린다**(결함 로그) · 못 고르면 지금처럼 둔다(새 큐 kind 0).
  · **대장** — 역할 `link` 한 행(위치 = 청크 · 열 `연결` · 경로 `reinforce`(재생이면 `replay`) · 판정 `attached` |
    `pending`(못 고름) | `gate_reject`(버림 — 제안 `proposal {target, rel}`을 남긴다 · B118 ⑤) · `target` · `evidence` ·
    붙은 자리 `보강`). **재구축이 재생한다**(LLM 0 — 같은 위치 · 같은 표기의 지난 행 `PRIOR`: 붙음이면 그 이름을 지금
    후보에서 다시 찾아 같은 관계로 · **버림은 제안을 지금 후보에서 찾아 지금 config로 게이트를 다시 돈다**(통과하면 붙고
    `by: replay` · 그대로면 다시 버림) · 못 고름 · 제안 없는 버림은 그대로 · 붙었던 후보를 지금 못 찾으면 다시 묻는다 ·
    `--no-replay`면 끔).
  · **상한** — 실행당 호출 `CALL_CAP`(사내 손잡이 `reinforce_call_cap` · 0이면 끔) — 넘는 대상은 그 수를 줄로 낸다.
  · **mock** — 선별은 결정적 규칙의 주입(`SELECT` — 시험이 넣는다) · 비면 판정 없음(호출 0 · 행 0).

코드에 층 어휘 0 — 관계 이름은 층 config · 게이트(`gate.judge`) · 카테고리쌍 매핑이 말한다.
"""
from __future__ import annotations

import json

from core.build import belongs, gate
from core.llm import gateway
from core.state import log, store
from core.state.ids import norm
from core.state.status import is_live

_LOG = log.get(__name__)

#: 실행당 연결 보강 호출 상한 — 사내 손잡이 `reinforce_call_cap`(0 = 끔 · 창작 기본값 — 가결정 D-197)
CALL_CAP = 50
#: 호출 하나의 후보 상한(가까운 것부터 · 가결정 D-197)
CAND_MAX = 30
ROLE = "link"
FIELD = "연결"
PATH = "reinforce"
PROMPT = POINT = "reinforce"
#: 대장 `attached.path`
HOW = "보강"

#: mock 선별 규칙 — `(payload) -> {"id", "rel", "evidence"} | None` · 시험이 주입한다(None이면 판정 없음)
SELECT = None
#: 재구축 재생 재료 — `{doc_id: [지난 link 행]}` (`replay.begin`이 새 대장이 덮기 전에 채운다)
PRIOR = {}
#: 이 실행의 사실 — 마무리 줄
LAST = {}

SCHEMA = {
    "type": "object",
    "properties": {"pick": {"type": ["object", "null"],
                            "properties": {"id": {"type": "string"}, "rel": {"type": ["string", "null"]},
                                           "evidence": {"type": "string"}},
                            "required": ["id", "rel", "evidence"], "additionalProperties": False}},
    "required": ["pick"], "additionalProperties": False,
}


# ---------------------------------------------------------------- 대상 · 후보
def _index(graphs):
    """`({node_id: (그래프, 노드)}, {node_id: {이웃}})` — 층 전부(엣지는 문서 층에 산다 · B100)."""
    nodes, ends = {}, {}
    for g in graphs.values():
        for nid, n in g.nodes.items():
            nodes[nid] = (g, n)
    for g in graphs.values():
        for e in g.edges:
            if e.get("status") == "deleted_by_user" or not e.get("provenance"):
                continue
            ends.setdefault(e["src"], set()).add(e["dst"])
            ends.setdefault(e["dst"], set()).add(e["src"])
    return nodes, ends


def targets(rows, nodes, ends, chunk_of):
    """`[(행, node_id, 사유)]` — 엣지 0(`엣지 0`) 또는 골격 좌표에만 붙은(`공정만`) 개체 · 노드마다 처음 행 하나."""
    from core.build.heading import _is_coord
    seen, out = set(), []
    for r in rows:
        nid = r.get("node_id")
        if r.get("role") != "entity" or not nid or nid in seen or r.get("locator") not in chunk_of:
            continue
        n = (nodes.get(nid) or (None, None))[1]
        if not n or not is_live(n) or _is_coord(n):
            continue
        others = ends.get(nid) or set()
        if others and not all(_is_coord((nodes.get(o) or (None, None))[1]) for o in others):
            continue
        seen.add(nid)
        out.append((r, nid, "공정만" if others else "엣지 0"))
    return out


def candidates(r, nid, rows, nodes, ol, path_of):
    """닫힌 후보 — 같은 문서 · 같은 제목 서브트리(그 청크의 맨 위 제목 아래 · 제목이 없으면 같은 청크)의 노드 ·
    가까운 것부터(조상 제목 개체 → 같은 청크 → 공통 제목이 깊은 청크 → 그 밖) · `CAND_MAX`까지. 골격 좌표 · 자기 0."""
    from core.build import outline as OL
    from core.build.heading import _is_coord
    mine = [h["id"] for h in OL.chain(ol, r["locator"])]
    top = mine[-1] if mine else None

    def rank(hids, same):
        if same:
            return 1
        if top is None or top not in hids:
            return None
        return 2 + next(i for i, h in enumerate(mine) if h in hids)

    ranked = []
    for x in rows:
        cid = x.get("node_id")
        if not cid or cid == nid or x.get("role") not in ("entity", "heading"):
            continue
        n = (nodes.get(cid) or (None, None))[1]
        if not n or not is_live(n) or _is_coord(n):
            continue
        if x.get("role") == "heading":
            hid = path_of.get(x.get("locator"))
            k = (0, mine.index(hid)) if hid in mine else (rank([h["id"] for h in OL.chain_of(ol, hid)], False), 9)
        else:
            k = (rank([h["id"] for h in OL.chain(ol, x.get("locator"))], x.get("locator") == r["locator"]), 0)
        if k[0] is not None:
            ranked.append((k, len(ranked), cid, n))
    out, seen = [], set()
    for _k, _i, cid, n in sorted(ranked, key=lambda t: (t[0], t[1])):
        if cid not in seen:
            seen.add(cid)
            out.append({"node_id": cid, "name": n["canonical"], "category": n["category"]})
    return out[:CAND_MAX]


# ---------------------------------------------------------------- 판정
def _ask(payload):
    """지점 ⑫ 실호출 — `{"id", "rel", "evidence"}` 또는 None."""
    out = gateway.chat([{"role": "system", "content": gateway.prompt(PROMPT)},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                       json_schema=SCHEMA, point="reinforce")
    return out.get("pick") if isinstance(out.get("pick"), dict) else None


def _check(pick, cmap, text, cfg):
    """답의 대조 — `(후보, 관계 또는 None, 근거, 버린 이유 또는 None)`."""
    if not pick:
        return None, None, None, None
    cand = cmap.get(str(pick.get("id")))
    ev = norm(pick.get("evidence") or "")
    rel = pick.get("rel") or None
    if cand is None:
        return None, None, ev, f"후보 밖 id {pick.get('id')!r}"
    if not ev or ev not in norm(text or ""):
        return None, None, ev, "근거 문장이 청크 원문에 없다"
    if rel and rel not in (cfg.get("relations") or []):
        return None, None, ev, f"닫힌 목록 밖 관계 {rel!r}"
    return cand, rel, ev, None


#: 거부 로그의 출처(B118 ⑥ — 경로는 추출과 같다)
SOURCE = "보강"


def _connect(cfg, graph, nodes, nid, tid, rel, prov, doc_id, cid):
    """엣지 하나 — 관계를 냈으면 게이트가 받는 방향으로(판정만 먼저 · 큐 0) · 안 냈으면 카테고리쌍 매핑(두 방향) ·
    `(관계, 대상이 src인가)` 또는 `(None, 이유)`."""
    eg, en = nodes[nid]
    tg, tn = nodes[tid]
    if rel:
        for s, d, sg, dg, fwd in ((tid, nid, tg, eg, True), (nid, tid, eg, tg, False)):
            if gate.judge(sg.get(s)["category"], rel, dg.get(d)["category"], cfg, gate.PATH_EXTRACT)[0] == gate.COMMIT:
                break
        else:
            # 판정만 먼저 했다 — 거부도 기록한다(B118 ⑥ 거부 묶음 · 제안 방향 = 대상 → 개체)
            gate.log_reject(rel, tn["category"], en["category"],
                            gate.judge(tn["category"], rel, en["category"], cfg, gate.PATH_EXTRACT)[0],
                            gate.PATH_EXTRACT, doc_id, SOURCE, cfg.get("layer"))
            return None, f"관계 {rel}가 게이트를 못 지난다({tn['category']} · {en['category']})"
    else:
        rel, fwd = belongs.edge_of(cfg, tn["category"], en["category"])
        if not rel:
            return None, f"카테고리쌍 매핑 없음({tn['category']} → {en['category']})"
    s, d, sg, dg = (tid, nid, tg, eg) if fwd else (nid, tid, eg, tg)
    br = gate.commit_edge(graph, s, rel, d, cfg, gate.PATH_EXTRACT, [prov], doc_id, evidence_chunk=cid,
                          src_graph=sg, dst_graph=dg, source=SOURCE)
    return (rel, fwd) if br == gate.COMMIT else (None, f"게이트 {br}")


def _prior(doc_id, r):
    from core.build import replay
    if replay.OFF:
        return None
    return next((x for x in PRIOR.get(doc_id) or [] if x.get("locator") == r.get("locator")
                 and norm(x.get("surface") or "") == norm(r.get("surface") or "")
                 and x.get("verdict") in ("attached", "pending", "gate_reject")), None)


# ---------------------------------------------------------------- 마무리 한 번
def _say(notice, info):
    if notice is not None:
        notice(info)


def run(docs, graphs=None, notice=None):
    """이 실행이 구축한 문서(`{doc_id: 문서 층}`)의 연결 보강 — `LAST`(대상 · 붙음 · 재생 · 못 고름 · 버림 · 상한 밖)."""
    from core.state import knobs
    from core.state.bootstrap import load_config, open_graph
    from router import discover
    LAST.clear()
    LAST.update({"대상": 0, "붙음": 0, "재생": 0, "못 고름": 0, "버림": 0, "상한 밖": 0, "호출": 0, "판정 없음": 0})
    if not docs:
        return LAST
    graphs = graphs or {lay: open_graph(lay) for lay in discover()}
    nodes, ends = _index(graphs)
    ch = (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {})
    plan = []
    for doc_id, lay in docs.items():
        chunk_of = {c.get("source_locator"): (cid, c) for cid, c in ch.items() if c.get("doc_id") == doc_id}
        rows = _rows(doc_id)
        for r, nid, why in targets(rows, nodes, ends, chunk_of):
            plan.append((doc_id, lay, rows, chunk_of, r, nid, why))
    cap = knobs.get("reinforce_call_cap")
    live = not gateway.use_mock()
    asks = sum(1 for p in plan if not _prior(p[0], p[4]))
    LAST["대상"] = len(plan)
    if not plan:
        return LAST
    _say(notice, {"단계": "보강예고", "대상": len(plan), "재생": len(plan) - asks,
                  "호출": min(asks, cap) if (live or SELECT) else 0, "상한": cap, "mock": not live and SELECT is None})
    u0 = gateway.usage_total()
    cfgs, touched = {}, set()
    for i, (doc_id, lay, rows, chunk_of, r, nid, why) in enumerate(plan, 1):
        cfg = cfgs.setdefault(lay, load_config(lay))
        if not targets([r], nodes, ends, chunk_of):
            res = "이미 붙음(앞 대상이 이었다)"           # 앞 대상의 엣지가 이 노드에 닿았다 — 대상이 아니다
        else:
            res = _one(doc_id, lay, cfg, graphs, nodes, ends, rows, chunk_of, r, nid, why, cap, live)
        if res:
            touched.add(doc_id)
        _say(notice, {"단계": "보강진행", "i": i, "m": len(plan), "표기": r.get("surface"), "결과": res})
    for g in graphs.values():
        g.save()
    _say(notice, {"단계": "보강끝", **{k: LAST[k] for k in LAST}, "since": u0})
    _LOG.info("연결 보강 — %s", line())
    return LAST


def _rows(doc_id):
    from core.build import ledger
    return (ledger.read(doc_id) or {}).get("rows") or []


def _one(doc_id, lay, cfg, graphs, nodes, ends, rows, chunk_of, r, nid, why, cap, live):
    """대상 하나 — 재생 → (상한 안이면) 판정 → 대조 → 엣지 → 대장 행. 돌려주는 것은 화면의 한 마디."""
    from core.build import extract_ctx, ledger, outline as OL
    ol = OL.load_any(doc_id) or {}
    path_of = {h["path"]: h["id"] for h in ol.get("headings") or []}
    cid, chunk = chunk_of[r["locator"]]
    cands = candidates(r, nid, rows, nodes, ol, path_of)
    cmap = {f"c{i}": c for i, c in enumerate(cands, 1)}
    old = _prior(doc_id, r)
    u0 = gateway.usage_total()
    if old is not None:
        LAST["재생"] += 1
        hit = next((k for k, c in cmap.items() if c["name"] == old.get("target")), None)
        prop = old.get("proposal") or {}
        again = next((k for k, c in cmap.items() if c["name"] == prop.get("target")), None) if prop else None
        if old.get("verdict") == "gate_reject" and again:
            # 버림은 **지금 config로 게이트를 다시 돈다**(B118 ⑤ — LLM 0 · 패턴을 더했으면 붙고 그대로면 다시 버림)
            pick = {"id": again, "rel": prop.get("rel"), "evidence": old.get("evidence") or ""}
            return _apply(doc_id, lay, cfg, graphs, nodes, ends, r, nid, cid, chunk, cmap, pick, "replay", u0,
                          by="replay")
        if old.get("verdict") in ("pending", "gate_reject"):        # 못 고름 · 제안 없는 버림도 판정 결과다 — 다시 묻지 않는다
            return _row(doc_id, r, nid, old["verdict"], "replay", None, None, old.get("evidence"), u0,
                        "못 고름(재생)" if old["verdict"] == "pending" else "버림(재생)", proposal=prop or None)
        if hit:
            rel = next((a.get("rel") for a in old.get("attached") or [] if a.get("path") == HOW), None)
            pick = {"id": hit, "rel": rel if rel in (cfg.get("relations") or []) else None,
                    "evidence": old.get("evidence") or ""}
            return _apply(doc_id, lay, cfg, graphs, nodes, ends, r, nid, cid, chunk, cmap, pick, "replay", u0)
        LAST["재생"] -= 1                     # 지난 답의 후보가 지금 없다 — 다시 묻는다(대상 없음)
    if not live and SELECT is None:
        LAST["판정 없음"] += 1                 # mock · 선별 규칙 없음 — 판정이 없었다(행 0)
        return None
    if not cands:
        LAST["못 고름"] += 1
        return _row(doc_id, r, nid, "pending", PATH, None, None, None, u0, "후보 0")
    if LAST["호출"] >= cap:
        LAST["상한 밖"] += 1
        return None
    payload = {"entity": {"name": (nodes[nid][1] or {}).get("canonical"), "category": (nodes[nid][1] or {}).get("category")},
               "chunk": extract_ctx.with_context(chunk, extract_ctx.doc_info(_env(doc_id))),
               "headings": OL.heading_candidates(ol, r["locator"]),
               "structure": OL.structure_chain(ol, r["locator"]),        # 구조 사슬 (B119 ② — 위에서 아래로)
               "candidates": [{"id": k, "name": c["name"], "category": c["category"]} for k, c in cmap.items()],
               "relations": cfg.get("relations") or []}
    LAST["호출"] += 1
    try:
        pick = _ask(payload) if live else SELECT(payload)
    except gateway.GatewayError as e:
        store.append_defect(f"{doc_id}: 연결 보강 실패 — '{r.get('surface')}' @ {r['locator']} — {e}")
        return None
    return _apply(doc_id, lay, cfg, graphs, nodes, ends, r, nid, cid, chunk, cmap, pick, PATH, u0)


def _count(path, what):
    """판정한 것만 칸에 센다 — 재생(`replay`)은 `재생` 한 칸이 이미 셌다."""
    if path == PATH:
        LAST[what] += 1


def _apply(doc_id, lay, cfg, graphs, nodes, ends, r, nid, cid, chunk, cmap, pick, path, u0, by=None):
    cand, rel, ev, why = _check(pick, cmap, chunk.get("text"), cfg)
    if cand is None and why is None:
        _count(path, "못 고름")
        return _row(doc_id, r, nid, "pending", path, None, None, None, u0, "못 고름", by=by)
    named = cmap.get(str((pick or {}).get("id")))
    # 버림의 제안(B118 ⑤) — 후보 안의 대상과 낸 관계 · 재생이 지금 config로 게이트를 다시 돈다
    prop = {"target": named["name"], "rel": (pick or {}).get("rel") or None} if named else None
    if why is None:
        rel, fwd = _connect(cfg, graphs[lay], nodes, nid, cand["node_id"], rel, f"{doc_id}#{r['locator']}",
                            doc_id, cid)
        if not rel:
            why = fwd
    if why:
        store.append_defect(f"{doc_id}: 연결 보강 — 버림 '{r.get('surface')}' @ {r['locator']} — {why}")
        _count(path, "버림")
        return _row(doc_id, r, nid, "gate_reject", path, None, None, ev, u0, f"버림 — {why}", proposal=prop, by=by)
    _count(path, "붙음")
    if by == "replay":
        LAST["버림→붙음"] = LAST.get("버림→붙음", 0) + 1
    ends.setdefault(nid, set()).add(cand["node_id"])
    ends.setdefault(cand["node_id"], set()).add(nid)
    return _row(doc_id, r, nid, "attached", path, cand["name"], (rel, fwd), ev, u0,
                f"{rel} {'←' if fwd else '→'} {cand['name']}", by=by)


def _row(doc_id, r, nid, verdict, path, target, edge, ev, u0, say, proposal=None, by=None):
    """대장 한 행(역할 `link`) — 같은 열쇠의 지난 행은 갈아 끼운다(`ledger.put_row`)."""
    from core.build import ledger
    u1 = gateway.usage_total()
    row = ledger.row(locator=r["locator"], field=FIELD, role=ROLE, surface=r.get("surface"),
                     canonical=r.get("target") or r.get("canonical"), layer=r.get("layer"), path=path,
                     verdict=verdict, node_id=nid, target=target, evidence=ev or None, proposal=proposal, by=by,
                     llm={"calls": u1["calls"] - u0["calls"], "in_tokens": u1["prompt_tokens"] - u0["prompt_tokens"],
                          "out_tokens": u1["completion_tokens"] - u0["completion_tokens"]})
    if edge:
        ledger.attach(row, edge[0], target, HOW, "←" if edge[1] else "→")
        # 그 개체 행에도 붙은 자리를 단다 — 맞춤표 「부착(개체 행)」의 `연결 보강` 칸(재시도의 갈아 끼움과 같은 손)
        ent = next((dict(x) for x in (ledger.read(doc_id) or {}).get("rows") or [] if x.get("role") == "entity"
                    and x.get("locator") == r["locator"] and x.get("node_id") == nid), None)
        if ent is not None:
            ent["attached"] = [a for a in ent.get("attached") or [] if a.get("path") != HOW]
            ledger.attach(ent, edge[0], target, HOW, "←" if edge[1] else "→")
            ledger.put_row(doc_id, ent, old=lambda x: x.get("role") == "entity" and x.get("locator") == r["locator"]
                           and x.get("node_id") == nid)
    ledger.put_row(doc_id, row)
    return say


def _env(doc_id):
    """맥락 줄의 문서 칸 재료 — 파싱 봉투(없으면 빈 칸)."""
    from core import paths
    p = paths.parsed(f"{doc_id}.json")
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


def line():
    """마무리 한 줄 — `연결 보강 — 대상 n → 붙음 a · 재생 r · 못 고름 b · 버림 c · 상한 밖 d · 호출 k`."""
    if not LAST or not LAST.get("대상"):
        return "연결 보강 — 대상 0(엣지 없는 · 공정에만 붙은 개체가 없다)"
    s = (f"연결 보강 — 대상 {LAST['대상']:,} → 붙음 {LAST['붙음']:,} · 재생 {LAST['재생']:,} · "
         f"못 고름 {LAST['못 고름']:,} · 버림 {LAST['버림']:,} · 호출 {LAST['호출']:,}")
    if LAST.get("버림→붙음"):
        s += f" · 재생 중 버림→붙음 {LAST['버림→붙음']:,}(지금 config로 게이트를 다시 돌았다 — LLM 0)"
    if LAST.get("상한 밖"):
        s += f" · 상한 밖 {LAST['상한 밖']:,}(손잡이 reinforce_call_cap — 다음 인입 · 재구축이 잇는다)"
    if LAST.get("판정 없음"):
        s += f" · 판정 없음 {LAST['판정 없음']:,}(mock — 선별 규칙 없음 · 호출 0)"
    return s
