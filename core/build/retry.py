# -*- coding: utf-8 -*-
"""칸 3.5 — orphan **재시도** — 큐에 남은 미부착·미앵커 항목을 다음 빌드 뒤에 다시 시도한다 (문서 4 §4.7-5).

`core/build/`의 문서 빌드에서 떼어냈다. 문서 빌드(표·산문 → 노드·엣지)와 「빌드가 끝난 뒤 큐를
다시 훑는 일」은 시점도 재료도 다르다 — 앞은 한 문서 안에서, 뒤는 그래프 전체를 본다.
진입점은 `retry_orphans(layers)` 하나이고 `pipeline.finalize`가 부른다.

**바꾸지 않은 것**: 큐 kind 3종(`RETRY_KINDS`) · 저해상 철회 · 게이트 통과 후에만 커밋.

**더 붙는 것이 없을 때까지**(B113 ③ — 사용자 결정 2026-10-15 「전체가 돌면서 연결될 수 있다」): 한 바퀴에 붙은 것이
있으면 다시 훑는다 · 0이면 멈춘다(같은 판에서 같은 답 — 결정적이라 끝난다) · 바퀴 상한은 사내 손잡이
`relink_rounds`. 대상은 셋 + **좌표 미해소 보류**(`missing_field` 키 `process_ref` — 그 문서의 문서 좌표 기록이 생기면
그 행의 재료로 다시 세운다 · 추출 LLM 0). 손 명령 `python run.py ops relink`가 같은 훑기를 부른다.
"""
from __future__ import annotations

from core import matcher
from core.build import gate
from core.state import log, store
from core.state.bootstrap import load_config, open_graph
from core.build.build import Builder
from core.state.status import is_live

_LOG = log.get(__name__)


# ---------------------------------------------------------------- orphan 재시도
RETRY_KINDS = ("orphan_anchor", "orphan_attach", "orphan_chunk_link")

# **재시도 상한**(B73 ②) — 넘으면 더 돌지 않고 「사람 판정 대기」다. 같은 그래프
# 상태에서 같은 답이 반복되는 것을 비용으로 바꾸지 않는다. 큐 kind는 그대로다.
ATTEMPT_MAX = 5

#: 재연결 바퀴 상한(B113 ③ — 창작 기본값 · 사내 손잡이 `relink_rounds`) — 넘으면 그 사실을 줄로 낸다
RELINK_ROUNDS = 5
#: **좌표 미해소 보류**(B113 ③) — 좌표 칸이 비어 세우지 못한 행의 큐(`missing_field` · 필드 `process_ref`) ·
#: 새 kind가 아니다 · 재료(드롭된 개체 · 엣지 · 값)가 든 항목만 대상
COORD_HOLD = "missing_field"


def is_target(item):
    """재연결 대상인가 — 셋(`RETRY_KINDS`) · 재료가 든 좌표 미해소 보류."""
    if item.get("kind") in RETRY_KINDS:
        return True
    pl = item.get("payload") or {}
    return (item.get("kind") == COORD_HOLD and pl.get("field") == "process_ref"
            and any(e.get("dropped_entities") or e.get("dropped_edges") or e.get("pending_attrs")
                    for e in (pl.get("items") or [pl])))


def _fingerprint(graphs):
    """후보 집합의 **지문** — 층마다 (노드 수 · 엣지 수). 바뀌면 다시 돌 이유가 있다.

    시각이 아니라 **수**를 쓰는 이유: mtime은 같은 초 안의 변화를 못 보고, 시험이
    그것에 기대면 빠른 실행에서 조용히 통과한다. 수는 결정적이다.
    """
    return "|".join([f"{lay}:{len(g.nodes)}:{len(g.edges)}"
                     for lay, g in sorted(graphs.items())] + [_material_print()])


def _material_print():
    """**골격 판 · 사전 판**(B100 ⑥) — 그래프 수가 그대로여도 별칭·골격 노드를 더하고 `bootstrap`
    하면 보류분이 다시 시도된다(재인입 불요). 내용의 해시다 — 시각이 아니다(같은 초 문제)."""
    import hashlib
    import json as _json
    h = hashlib.sha1()
    for name in (store.SKELETON_LIST, store.DICTIONARY, store.COORD_LEARNED):
        h.update(_json.dumps(store.read(name, {}), sort_keys=True, ensure_ascii=False,
                             default=str).encode("utf-8"))
    return "판:" + h.hexdigest()[:12]


def _item_fp(fp, item, dc):
    """항목의 지문 — 공통 지문 + **좌표 미해소 보류는 그 문서의 문서 좌표 기록**(B113 ③ — 기록이 생기면 그 문서의
    보류만 다시 본다 · 다른 문서 항목의 시도 횟수는 그대로)."""
    if item.get("kind") != COORD_HOLD:
        return fp
    return f"{fp}|문서:{(dc.get(item.get('doc_id')) or {}).get('coord')}"


def _doc_coords():
    """문서 좌표 기록(`registry/doc_coords.json` — B102 ②) `{doc_id: {coord, by, at}}` · 없으면 빈 그릇.
    좌표 미해소 보류의 재료이자 그 항목 지문의 몫이다(`_item_fp` — 기록이 생기면 그 문서의 보류를 다시 본다 · B113 ③)."""
    import json as _json
    from core import paths
    p = paths.registry("doc_coords.json")
    try:
        return _json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        return {}


def _qid(item):
    """큐 항목의 동일성 — kind · 문서 · payload(이력 필드는 payload 밖이라 들지 않는다)."""
    import json as _json
    return (item.get("kind"), item.get("doc_id"),
            _json.dumps(item.get("payload") or {}, sort_keys=True, ensure_ascii=False, default=str))


def _write_back(seen):
    """**큐를 되살리지 않는다**(B100 ①) — 시작에 읽은 목록을 통째로 다시 쓰지 않는다.

    재시도 중에 연결된 항목은 self-heal(`store.drop`)이 이미 걷어냈고, 착지가 새 항목을
    적재했을 수도 있다. 그래서 **지금의 큐를 다시 읽어** 남은 항목에만 시도 이력(`attempts`·
    `first_seen`·`last_tried`·`last_fp`)을 옮겨 쓴다 — 걷힌 것은 그대로 없고, 새로 들어온 것은 그대로 있다.
    """
    hist = {_qid(x): x for x in seen}
    cur = store.read(store.QUEUE, [])
    for x in cur:
        h = hist.get(_qid(x))
        if h is not None:
            for k in ("attempts", "first_seen", "last_tried", "last_fp"):
                if k in h:
                    x[k] = h[k]
    store.write(store.QUEUE, cur)


def retry_orphans(layers=None):
    """**orphan 재시도 배치** — 문서 4 §4.7-5 · §4.8-5.

    **주기의 정본은 빌드 말미 sweep이다** — 한 sweep은 바퀴의 반복이고 붙은 것이 0인 바퀴에서
    멈춘다(B113 ③ · 상한 `RELINK_ROUNDS`). 별도 스케줄러는 두지 않는다 — 그래프가 자라는 시점이
    곧 재시도가 의미를 갖는 시점이고, 주기와 호출자가 비어 있으면 큐 항목이 **아무도 부르지 않는
    배치를 기다린다.** 손 명령 `ops relink --apply`는 같은 마무리 함수를 부른다(재인입 없이).

    각 항목의 보존 표면형을 **판정 파이프라인(§4.3)에 다시 태운다** — 재사용 지점이
    `matcher.match` 하나라는 것이 §7.1의 요구다. 확신되면 자동 해소하고, 불확실이면
    항목을 그대로 큐에 남긴다.

    **provenance는 큐 항목이 보유한 원 문서 발자국 그대로다** — `auto:{규칙명}`을
    쓰지 않는다(§4.7-5). 문서 발자국이 아니면 재인입 회수 대상 밖으로 나가, 개정으로
    사라진 행의 엣지가 살아남는다.

    재시도는 **같은 그래프 상태에서 같은 판정을 내는 결정적 연산**이라 「클린 2회
    동일 그래프」 판정을 깨지 않는다.

    돌려주는 것: `{kind: 해소 건수}` — 계기판·보고용이다.
    """
    from router import discover
    from core.dictionary import Dictionary

    lays = layers or discover()
    graphs = {lay: open_graph(lay) for lay in lays}
    cfgs = {lay: load_config(lay) for lay in lays}
    dic = Dictionary.open()
    healed = {k: 0 for k in RETRY_KINDS + (COORD_HOLD,)}
    # **결과를 버리지 않는다**(B99 ⑥) — 대상 · 그래프·골격·사전 그대로라 건너뜀 · 상한 도달 · 연결 · 남음 · 바퀴(B113 ③)
    LAST.clear()
    LAST.update(target={}, same=0, capped=0, healed=healed, left=0, rounds=[], cut=False)
    tried = set()
    for k in range(max(1, int(RELINK_ROUNDS))):
        got = _sweep(graphs, cfgs, dic, healed, tried, first=(k == 0))
        LAST["rounds"].append(got)
        if not got["붙음"]:
            break
    else:
        LAST["cut"] = True                    # 마지막 바퀴에도 붙었다 — 상한에서 멈췄다(다음 인입 · relink가 잇는다)

    for lay, g in graphs.items():
        g.save()
    dic.save()
    _left = [x for x in store.read(store.QUEUE, []) if is_target(x)]
    LAST["left"] = len(_left)
    LAST["left_by"] = {}
    for x in _left:
        LAST["left_by"][x["kind"]] = LAST["left_by"].get(x["kind"], 0) + 1
    # 남은 항목의 시도 횟수 분포(B102 ⑦) — 상한에 닿은 것은 「상한」으로 센다
    _d = {}
    for x in _left:
        k = "상한" if int(x.get("attempts") or 0) >= ATTEMPT_MAX else f"{int(x.get('attempts') or 0)}회"
        _d[k] = _d.get(k, 0) + 1
    LAST["dist"] = _d
    _LOG.info("orphan 재시도 — %s", line())
    return healed


def _sweep(graphs, cfgs, dic, healed, tried, first):
    """한 바퀴 — 지금의 큐에서 대상마다 한 번(지문이 지난 시도와 같으면 건너뜀 · 상한이면 건너뜀) ·
    돌려주는 것은 `{대상, 붙음, 건너뜀, 상한}`. 시도 횟수는 **한 번의 훑기(바퀴 전부)에 한 번** 센다."""
    fp0, dc = _fingerprint(graphs), _doc_coords()
    queue = store.read(store.QUEUE, [])
    got = {"대상": 0, "붙음": 0, "건너뜀": 0, "상한": 0}
    touched = False
    for item in list(queue):
        if not is_target(item):
            continue
        kind = item.get("kind")
        pl = item.get("payload") or {}
        got["대상"] += 1
        if first:
            LAST["target"][kind] = LAST["target"].get(kind, 0) + 1
        # **후보 집합이 그대로면 다시 돌지 않는다**(B73 ②) — 구판은 인입마다 큐
        # 전량을 다시 돌았고, `orphan_attach`는 그때마다 판정 LLM을 다시 불렀다
        # (같은 입력 · 같은 답). 재시도가 의미를 갖는 것은 **그래프가 자랐을
        # 때**뿐이다(§4.7-5) — 그 사실을 지문 하나로 잰다. LLM 0 조건이다.
        fp = _item_fp(fp0, item, dc)
        if item.get("last_fp") == fp:
            got["건너뜀"] += 1
            LAST["same"] += 1 if first else 0
            continue
        if int(item.get("attempts", 0)) >= ATTEMPT_MAX:
            got["상한"] += 1
            LAST["capped"] += 1 if first else 0
            continue                      # 사람 판정 대기 — 더 돌지 않는다
        # **이력은 항목에 달고 payload에는 넣지 않는다** — payload는 「같은 항목인가」의
        # 동일성 키이고(`enqueue` 중복 제거 · 멱등 판정의 대조 단위), 거기에 시각이
        # 들어가면 **클린 2회 동일 그래프**가 깨진다(실측 — 이 회차에서 한 번 깼다).
        qid = _qid(item)
        if qid not in tried:
            tried.add(qid)
            item["attempts"] = int(item.get("attempts", 0)) + 1
        item.setdefault("first_seen", item.get("created"))
        item["last_tried"], item["last_fp"] = store._now(), fp
        touched = True
        ok = False
        if kind == "orphan_attach":
            ok = _retry_attach(pl, item, graphs, cfgs, dic)
        elif kind == "orphan_anchor":
            ok = _retry_anchor(pl, item, graphs, cfgs, dic)
        elif kind == COORD_HOLD:
            ok = _retry_coord_hold(pl, item, graphs, cfgs, dic)
        if ok:
            healed[kind] += 1
            got["붙음"] += 1
    if touched:
        _write_back(queue)
        # orphan_chunk_link의 생산자가 아직 없다 — 항목이 생기면 같은 자리에서 돈다.
    return got


#: 마지막 재시도의 결과 — 화면·로그가 읽는다(B99 ⑥ · `line()`).
LAST = {}


def line():
    """`재연결 — 바퀴 k · 대상 n(kind별) · 붙음 m · 남음 r(kind별) · 그래프·골격·사전 그대로라 건너뜀 s · 상한 도달 c`
    (B113 ③ — 바퀴마다는 `rounds_text`)."""
    if not LAST:
        return "재연결 — 돌지 않았다"
    t = LAST["target"]
    kinds = " · ".join(f"{k} {v}" for k, v in sorted(t.items()))
    lb = LAST.get("left_by") or {}
    left = " · ".join(f"{k} {v}" for k, v in sorted(lb.items()))
    return (f"재연결 — 바퀴 {len(LAST.get('rounds') or []):,} · 대상 {sum(t.values()):,}"
            + (f"({kinds})" if kinds else "")
            + f" · 붙음 {sum(LAST['healed'].values()):,} · 남음 {LAST['left']:,}" + (f"({left})" if left else "")
            + f" · 그래프·골격·사전 그대로라 건너뜀 {LAST['same']:,} · 상한 도달 {LAST['capped']:,}"
            + (" · 바퀴 상한에서 멈춤(더 붙을 수 있다 — 다음 인입 또는 python run.py ops relink)"
               if LAST.get("cut") else "")
            + _dist_text(LAST.get("dist")))


def plan(layers=None, doc_coord=None):
    """손 명령의 **계획**(B113 ③ — 쓰기 0) — 대상 kind별 · 이번에 돌 것(지문이 지난 시도와 다르다) · 건너뜀 · 상한.
    `doc_coord=(doc_id, 좌표)`면 그 기록이 있는 것으로 센다(계획은 기록하기 전이다)."""
    from router import discover
    graphs = {lay: open_graph(lay) for lay in (layers or discover())}
    fp, dc = _fingerprint(graphs), _doc_coords()
    if doc_coord:
        dc[doc_coord[0]] = {"coord": doc_coord[1]}
    out = {"target": {}, "try": 0, "same": 0, "capped": 0}
    for x in store.read(store.QUEUE, []):
        if not is_target(x):
            continue
        out["target"][x["kind"]] = out["target"].get(x["kind"], 0) + 1
        if x.get("last_fp") == _item_fp(fp, x, dc):
            out["same"] += 1
        elif int(x.get("attempts", 0)) >= ATTEMPT_MAX:
            out["capped"] += 1
        else:
            out["try"] += 1
    return out


def rounds_text():
    """바퀴마다 `바퀴 i — 대상 n · 붙음 m · 건너뜀 s` (손 명령 `ops relink`의 끝 줄들)."""
    return [f"바퀴 {i} — 대상 {r['대상']:,} · 붙음 {r['붙음']:,} · 건너뜀 {r['건너뜀']:,} · 상한 {r['상한']:,}"
            for i, r in enumerate(LAST.get("rounds") or [], 1)]


def _dist_text(d):
    """「 · 시도 1회 a · 2회 b · … · 상한 c」 — 남은 것이 없으면 빈 문자열."""
    if not d:
        return ""
    keys = sorted((k for k in d if k != "상한"), key=lambda k: int(k[:-1]))
    return " · 시도 " + " · ".join(f"{k} {d[k]:,}" for k in keys + (["상한"] if "상한" in d else []))


def _pick_cat(surface, category, graphs, dic):
    """카테고리가 **선언된** 표면형을 판정한다 (B11 — 정상 경로).

    카테고리가 하나로 정해져 있으므로 순회도 수렴 판정도 필요 없다.
    """
    for lay, g in graphs.items():
        cands = matcher.candidates(surface, category, lay, g, dic)
        if not cands:
            continue
        v = matcher.match(surface, cands, category)
        if v["type"] == matcher.MATCH and v["matched_id"]:
            return v["matched_id"], lay, g
    return None, None, None


def _pick_any(surface, graphs, cfgs, dic):
    """카테고리가 선언되지 않은 표면형(attach 대상)을 판정한다.

    **첫 히트를 임의로 고르지 않는다.** attach 대상은 카테고리가 선언돼 있지 않아
    후보가 여러 카테고리에 걸친다 — 카테고리를 순서대로 훑어 먼저 맞는 것을 쓰면
    **순회 순서가 답을 정한다.** 실측: `'정밀 노칭 프레스'`가 `Process/노칭`(0.95)과
    `Unit/노칭 프레스`(0.95) 양쪽에 걸렸고, 선언 순서상 앞선 Process가 이겨
    설비 자리에 공정이 들어갔다.

    그래서 **카테고리별로 판정하고 확신을 모은 뒤, 하나로 수렴할 때만** 쓴다.
    사전 정확 히트(`exact`)가 있으면 그것이 우선이고, 수렴하지 않으면 미해소로
    두어 항목을 큐에 남긴다 — `_dict_hit`과 같은 규율이다(문서 4 §4.4-3).
    """
    exact, fuzzy = {}, {}
    for lay, g in graphs.items():
        for cat in (cfgs[lay].get("categories") or {}):
            cands = matcher.candidates(surface, cat, lay, g, dic)
            if not cands:
                continue
            if any(c.get("exact") for c in cands):
                for c in cands:
                    if c.get("exact"):
                        exact[c["id"]] = (lay, g)
                continue
            v = matcher.match(surface, cands, cat)
            if v["type"] == matcher.MATCH and v["matched_id"]:
                fuzzy[v["matched_id"]] = (lay, g)
    pool = exact or fuzzy
    if len(pool) != 1:
        return None, None, None
    nid, (lay, g) = next(iter(pool.items()))
    return nid, lay, g


def _retry_attach(pl, item, graphs, cfgs, dic):
    """미해소 attach 재시도 — 성공하면 **저해상도 부착을 갈아끼운다**(§4.4-8 (a)).

    갈아끼움은 ①고해상도 엣지 커밋 ②저해상도 엣지의 **그 provenance만 회수**
    ③근거 0이 된 엣지의 착지(`_evidence_lost`가 다음 sweep에서 본다) 셋이다.
    회수하지 않으면 같은 지식이 두 벌로 남아 질의 근거가 중복되고, 재인입 때
    회수 대상이 어긋나 멱등성이 조용히 깨진다.
    """
    surface = pl.get("attach_to")
    if not surface:
        return False
    # **행(청크) 단위 재료를 행마다 처리한다**(B72 ②) — 항목은 부착 대상 표기
    # 단위로 모이고, 붙일 자식 노드와 근거는 행마다 다르다.
    ents = pl.get("items") or [pl]
    if len(ents) > 1 or pl.get("items"):
        done = 0
        for e in ents:
            done += 1 if _attach_one(e, surface, graphs, cfgs, dic,
                                     item.get("doc_id")) else 0
        if done:
            store.drop(item["kind"], lambda p: p == pl)
        return bool(done)
    child_id = pl.get("node_id")
    if not child_id:
        return False
    child, clay, cg = None, None, None
    for lay, g in graphs.items():
        if child_id in g.nodes:
            child, clay, cg = g.get(child_id), lay, g
            break
    if child is None or not is_live(child):
        store.drop(item["kind"], lambda p: p == pl)     # 대상이 사라졌다 — 항목도 내린다
        return False

    # 대상 이름을 다시 해소한다. **큐 항목이 카테고리를 보유하면 그것 하나로**
    # 판정한다(B11) — 보유하지 않은 옛 항목만 수렴 판정으로 떨어진다.
    cat = pl.get("attach_category")
    if cat:
        target, tlay, tg = _pick_cat(surface, cat, graphs, dic)
    else:
        target, tlay, tg = _pick_any(surface, graphs, cfgs, dic)
    if target is None or target == child_id:
        return False                                    # 불확실 — 항목을 큐에 남긴다

    cfg = cfgs[tlay]
    # 소속 항목(`belongs_from` 키 — B102)은 인입과 같은 함수로 두 방향을 본다(`belongs.edge_of` — B113 ③: 한 방향만
    # 보면 「개체 → 대상」 매핑(`Component,Unit`)이 재시도에서만 「매핑 없음」이 된다) · 옛 부착은 지금 그대로 한 방향
    if "belongs_from" in pl:
        from core.build.belongs import edge_of
        rel, fwd = edge_of(cfg, tg.get(target)["category"], child["category"])
    else:
        rel, fwd = gate.pair_relation(cfg, tg.get(target)["category"], child["category"]), True
    if not rel:
        store.append_defect(
            f"orphan 재시도: 카테고리쌍 매핑 없음 "
            f"({tg.get(target)['category']} → {child['category']})")
        return False
    prov = pl.get("provenance")
    src, dst, sg, dg = (target, child_id, tg, cg) if fwd else (child_id, target, cg, tg)
    gate.commit_edge(cg, src, rel, dst, cfg, gate.PATH_EXTRACT,
                     [prov] if prov else [], item.get("doc_id"),
                     src_graph=sg, dst_graph=dg)
    _withdraw_lowres(graphs, child_id, target, prov, _heading_fallbacks(item.get("doc_id"), prov, pl, graphs))
    if "belongs_from" in pl:
        _ledger_belongs(item.get("doc_id"), prov, pl, rel, tg.get(target)["canonical"], fwd)
    store.drop(item["kind"], lambda p: p == pl)         # self-heal
    return True


def _ledger_belongs(did, prov, pl, rel, other, fwd):
    """붙은 소속을 **그 개체 행**에 — 좌표 폴백 자리를 소속 자리로 갈아 끼운다(B113 ③ · 대장 손 `ledger.put_row`) ·
    표시 `by: "retry"`. 행이 없으면(옛 대장) 그대로 둔다 — 엣지는 이미 섰고 대장은 판정을 대신하지 않는다."""
    from core.build import ledger
    loc = prov[len(did) + 1:] if did and prov and str(prov).startswith(f"{did}#") else None
    data = ledger.read(did) if loc else None
    r = next((dict(r) for r in (data or {}).get("rows") or [] if r.get("role") == "entity"
              and r.get("locator") == loc and r.get("node_id") == pl.get("node_id")), None)
    if r is None:
        return
    # 폴백 자리 전부(좌표 `폴백` · 제목 개체 `폴백(제목 n단)` — B115 ③)를 소속 자리로 갈아 끼운다
    r["attached"] = [a for a in r.get("attached") or [] if not str(a.get("path") or "").startswith("폴백")]
    ledger.attach(r, rel, other, f"소속({pl.get('belongs_from') or '-'})", "←" if fwd else "→")
    r["by"] = "retry"
    ledger.put_row(did, r)


def _attach_one(pl, surface, graphs, cfgs, dic, doc_id):
    """한 행(청크)의 부착 재시도 — 성공하면 True. 본문은 낱개 경로와 같다."""
    return _retry_attach({**pl, "attach_to": surface},
                         {"kind": "orphan_attach", "doc_id": doc_id,
                          "payload": None}, graphs, cfgs, dic)


def _heading_fallbacks(did, prov, pl, graphs):
    """그 개체 행이 폴백 사슬로 붙었던 **제목 개체** 노드 id(B115 ③ — 대장 `폴백(제목 n단)`의 상대 이름) — 개체 → 제목
    개체 방향의 폴백도 회수 대상이다(좌표 카테고리가 아니라 위 방향 조건에 안 걸린다)."""
    from core.build import ledger
    loc = prov[len(did) + 1:] if did and prov and str(prov).startswith(f"{did}#") else None
    r = next((r for r in (ledger.read(did) or {}).get("rows") or [] if loc and r.get("role") == "entity"
              and r.get("locator") == loc and r.get("node_id") == pl.get("node_id")), None)
    names = {a.get("other") for a in (r or {}).get("attached") or [] if str(a.get("path") or "").startswith("폴백(")}
    return {nid for g in graphs.values() for nid, n in g.nodes.items() if names and n.get("canonical") in names}


def _withdraw_lowres(graphs, child_id, new_target, prov, heads=()):
    """저해상도 부착의 **그 provenance만** 회수한다 (§4.4-8 (a) 갈아끼움).

    엣지를 지우지 않고 발자국만 뺀다 — 다른 문서가 같은 저해상도 부착을 주장하고
    있으면 그 근거는 살아 있어야 한다. 근거가 0이 되면 다음 sweep의
    `_evidence_lost`가 그것을 표시한다(삭제가 아니라 표시 — 카드 L9).

    폴백은 두 방향이다(B102 ④ — `belongs.edge_of`): 좌표 → 개체(지금 그대로) · **개체 → 좌표**(상대가 좌표
    카테고리일 때만 — B113 ③: 이 방향을 보지 않아 붙은 뒤에도 공정 폴백이 같은 근거로 남았다). 엣지는 문서 층에
    산다(B100) — 층 전부를 본다.
    """
    if not prov:
        return
    from core.state.bootstrap import COORD_CATEGORY
    cat = {nid: n.get("category") for g in graphs.values() for nid, n in g.nodes.items()}
    for g in graphs.values():
        for e in g.edges:
            if new_target in (e["src"], e["dst"]) or e.get("status") == "deleted_by_user":
                continue
            if not (e["dst"] == child_id or (e["src"] == child_id and (cat.get(e["dst"]) == COORD_CATEGORY
                                                                     or e["dst"] in heads))):
                continue
            if prov in (e.get("provenance") or []):
                e["provenance"] = [x for x in e["provenance"] if x != prov]


def _retry_anchor(pl, item, graphs, cfgs, dic):
    """미해소 좌표 재시도 — 성공하면 **보유분을 전부 착지시킨다**(§4.4-98).

    큐 항목이 보유한 것 셋을 각각 처리한다:
    ①`dropped_edges` — 생략된 엣지를 다시 커밋
    ②`pending_attrs` — 보류된 값을 해소된 노드에 저장
    ③(연쇄 걸침 entity는 `dropped_edges`의 표면형으로 되살린다)
    """
    surface, category = pl.get("surface"), pl.get("category")
    if not surface or not category:
        return False
    # **좌표 재시도도 anchor의 해소 규칙을 그대로 쓴다 — 사전(정확 일치·alias)까지다.**
    #
    # 문서 2 §2.4-①: "사전 조회(정확 일치·alias) → 해소, 미스면 곧바로
    # orphan_anchor 큐. **anchor 해소에는 후보검색·유사도·LLM 판정을 쓰지 않는다**
    # — 골격은 사람이 고정한 유형이고(P2), 추론으로 끌어당기면 사람의 보증을 코드가
    # 뒤집는다." 좌표 태깅이 닫힌 목록의 정확 일치 대조인 것과 같은 성질이다.
    #
    # 재시도가 존재하는 이유는 **그래프가 자랐기 때문**이지 매칭이 느슨해졌기
    # 때문이 아니다(§4.7-5). anchor는 Tier1(seed·confirmed) 한정이다.
    ref, rlay, rg = _tier1(surface, category, graphs, dic)
    if ref is None:
        # **좌표 학습 기록**(B101 ② · B113 ③) — LLM이 채택한 표기는 인입이 바로 쓴다 · 재연결도 같은 기록을 본다
        x = (store.read(store.COORD_LEARNED, {}).get("채택") or {}).get(surface) or {}
        if x.get("canonical"):
            ref, rlay, rg = _tier1(x["canonical"], category, graphs, dic)
    if ref is None:
        return False                                    # 아직 골격에 없다 — 남긴다
    cfg = cfgs[rlay]
    did = item.get("doc_id")
    n = 0
    # **행 단위 재료를 행마다 처리한다**(B72 ②) — 큐 항목은 표기 단위로 모이지만
    # 재시도의 재료(provenance · dropped_edges · pending_attrs)는 행의 것이다.
    # 하나의 provenance로 전부 착지시키면 **다른 행의 근거가 뒤섞인다.**
    # 옛 항목(집계 전 판)은 `items`가 없다 — 그때는 자기 자신이 한 행이다.
    b0 = _builder(rg, cfg, did, rlay, dic)              # 좌표 하강 · 극성(행마다 — 인입과 같은 함수)
    for _ent in (pl.get("items") or [pl]):
        n += _land_anchor_entry(_ent, ref, rlay, rg, graphs, cfgs, cfg, did, b0)
    store.drop(item["kind"], lambda p: p == pl)         # self-heal
    return True


def _tier1(surface, category, graphs, dic):
    """골격(Tier1 — seed · confirmed) 조회 — 사전(정확 · 별칭)까지 · 하나일 때만 `(id, 층, 그래프)`."""
    for lay, g in graphs.items():
        hits = [nid for nid in dic.lookup(surface)
                if nid in g.nodes and is_live(g.get(nid))
                and g.get(nid)["category"] == category
                and g.get(nid).get("status") in ("seed", "confirmed")]
        if len(hits) == 1:
            return hits[0], lay, g
    return None, None, None


def _retry_coord_hold(pl, item, graphs, cfgs, dic):
    """**좌표 미해소 보류**(B113 ③) — 좌표 칸이 비어 세우지 못한 행. 그 문서의 문서 좌표 기록(`--coord`)이 지금
    있으면 그 공정을 좌표로 **그 행의 재료**(큐 항목이 든 드롭된 개체 · 엣지 · 값 — 추출 체크포인트의 것)를 착지시킨다
    (추출 LLM 0 · 판정은 인입과 같은 함수 — LLM 판정은 지금처럼). 좌표 학습 · 별칭은 좌표 표기가 있을 때의 일이다
    (`orphan_anchor`)."""
    from core.state.bootstrap import COORD_CATEGORY
    did = item.get("doc_id")
    coord = (_doc_coords().get(did) or {}).get("coord")
    if not coord:
        return False                                    # 문서 좌표 기록이 없다 — 남긴다
    ref, rlay, rg = _tier1(coord, COORD_CATEGORY, graphs, dic)
    if ref is None:
        return False
    cfg = cfgs[rlay]
    b0 = _builder(rg, cfg, did, rlay, dic)
    for _ent in (pl.get("items") or [pl]):
        _land_anchor_entry(_ent, ref, rlay, rg, graphs, cfgs, cfg, did, b0)
    store.drop(item["kind"], lambda p: p == pl)         # self-heal
    return True


def _land_revived(revived, ends, ref, rg, graphs, cfgs, pl, prov, did, b0):
    """되살린 개체를 **인입과 같이** 잇는다(B113 ③) — 엣지(드롭된 엣지)에 서지 못한 것은 좌표에 폴백(규칙 B —
    `loop.fallback_untouched` 한 함수) · 청크 개체(열 없는 재료 — 산문)는 그 청크의 `describes`(청크 → 노드)."""
    from core.build import loop
    fields = {d.get("surface"): d for d in pl.get("dropped_entities") or []}
    att = {}
    coord = (rg.get(ref) or {}).get("canonical")
    for surface, nid in sorted({k: v for k, v in revived.items() if k in fields}.items()):
        g = next((g for g in graphs.values() if nid in g.nodes), rg)
        lay = next((lay for lay, gg in graphs.items() if gg is g), None)
        if nid not in ends:
            for _n, rel in loop.fallback_untouched(b0, cfgs.get(lay) or b0.cfg, [(nid, g)], set(), ref, rg,
                                                   prov, did):
                att.setdefault(nid, []).append({"rel": rel, "other": coord, "path": "폴백", "dir": "←"})
        if not fields[surface].get("field") and prov and str(prov).startswith(f"{did}#"):
            _describe_revived(did, str(prov)[len(did) + 1:], nid)
    return att


def _describe_revived(did, loc, nid):
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    put = False
    for cid, c in (ch.get("chunks") or {}).items():
        if c.get("doc_id") == did and c.get("source_locator") == loc:
            e = {"chunk_id": cid, "node_id": nid}
            if e not in ch.setdefault("describes", []):
                ch["describes"].append(e)
                c["linked"] = True
                put = True
    if put:
        store.write(store.CHUNKS, ch)


def _builder(g, cfg, did, lay, dic):
    """재시도의 빌더 — **사전은 재시도의 것 하나를 같이 쓴다**(B113 ③). 빌더가 제 사전을 따로 열면 되살린 노드의
    등재를 빌더가 쓴 뒤 재시도 끝의 저장(`dic.save` — 시작에 연 사본)이 덮어 등재가 사라지고, 지문(사전 판)도
    다음 실행에서 어긋나 같은 항목을 다시 돈다."""
    b = Builder(g, cfg, None, did, lay)
    b.dict = dic
    return b


def _ledger(did, prov, d, lay, b, attached=None):
    """재시도의 판정을 **그 문서 대장**에 — 같은 키(B106 재생 키) 행을 갈아 끼운다 · 없으면 더한다 · 표시
    `by: "retry"`(B107 ③ · 대장 손 `ledger.put_row`). 다음 재구축은 그 값을 재생한다(「키 없음」 0).

    키의 위치는 행의 provenance(`{doc}#{위치}` — 대장 행의 위치는 접두 없는 `source_locator`)에서 · 열은 재료의
    `field`(표의 연쇄 드롭) — 없으면 카테고리(좌표 없는 스코프 개체 `_no_coord` — 산문 대장 행의 열이 카테고리다)."""
    from core.build import ledger
    if not did or not b.last:
        return
    loc = prov[len(did) + 1:] if prov and str(prov).startswith(f"{did}#") else prov
    kw = ledger.judged(b.last, locator=loc, field=d.get("field") or d["category"], surface=d["surface"],
                       layer=lay, target=b.canonical_of(b.last.get("node_id")))
    r = ledger.row(**kw, by="retry")
    if attached:
        r["attached"] = list(attached)
    ledger.put_row(did, r)


def _land_anchor_entry(pl, ref, rlay, rg, graphs, cfgs, cfg, did, b0):
    """좌표가 해소된 **한 행**의 보유분을 착지시킨다 — 돌려주는 것은 건수다.

    좌표는 **인입과 같이 그 행의 극성으로 하강**하고(⓪ 하강 부착 — 행 재료의 `electrode_type`) 개체는 인입과 같은
    함수(`resolve_at_home` — 자기 좌표 규칙 · 극성 상속)로 해소한다(B107 ③): 재시도가 인입과 다른 이름을 세우면
    다음 재구축의 판정 재생이 그 값을 「대상 없음」으로 다시 판정하고 그래프도 갈린다."""
    prov = pl.get("provenance")
    et = pl.get("electrode_type")
    ref = b0.descend_anchor(ref, et, rg)
    pol = b0.anchor_polarity(ref, rg)
    n = 0

    # ① **연쇄 드롭된 entity를 새로 세운다**(문서 4 §4.4 — B14).
    # 좌표가 해소됐으므로 이제 스코프를 붙일 수 있다 — 미리 만들어 둔 것이
    # 없으니 중복도 없다. 세운 노드의 id를 dropped_edges 해소에 쓴다.
    revived, rows = {}, []
    parent = (rg.get(ref) or {}).get("canonical")
    # **표 행의 소유자 → 이름 부모**(B144 ② — 인입과 같은 함수): 드롭된 개체 열 · 엣지로 그 행의 소유 엣지를 다시 읽고
    # 소유자 열을 먼저 세운다(`scope_path.table_owners` · `owner_first` · `owner_parent`)
    from core.build import scope_path
    ents = pl.get("dropped_entities") or []
    owners = scope_path.table_owners({"fields": {d["field"]: {"role": "entity", "category": d.get("category")}
                                                 for d in ents if d.get("field")},
                                      "edges": pl.get("dropped_edges") or []}, cfg)
    order = {f: i for i, f in enumerate(scope_path.owner_first([d["field"] for d in ents if d.get("field")], owners))}
    homes = {}
    for d in sorted(ents, key=lambda d: order.get(d.get("field"), len(order))):
        lay2 = d.get("target_layer") or rlay
        g2 = graphs.get(lay2)
        if g2 is None:
            continue
        b2 = _builder(g2, cfgs[lay2], did, lay2, b0.dict)
        of = owners.get(d.get("field"))
        owner = (revived[of], homes[of]) if of in homes else None
        nid2, eb2 = b2.resolve_at_home(d["surface"], d["category"], prov, coord=(ref, rg), electrode_type=et,
                                       parent_canonical=scope_path.owner_parent(b2.cfg, d["category"], owner, parent),
                                       anchor_polarity=pol, owner=owner)
        b2.flush()
        rows.append((d, lay2, eb2, nid2))         # 대장 행은 잇고 난 뒤에 — 붙은 자리까지 (B107 ③ · B113 ③)
        if nid2:
            revived[d.get("field") or d["surface"]] = nid2
            revived[d["surface"]] = nid2
            if d.get("field"):
                homes[d["field"]] = eb2.g
            n += 1

    ends = set()
    for d in pl.get("dropped_edges") or []:
        src, dst = d.get("src"), d.get("dst")
        if d.get("from") == "@process_ref":
            src = ref
        elif src is None:
            src = revived.get(d.get("from")) or revived.get(d.get("src_surface"))
        if d.get("to") == "@process_ref":
            dst = ref
        elif dst is None:
            dst = revived.get(d.get("to")) or revived.get(d.get("dst_surface"))
        if not src or not dst:
            continue
        sg = next((g for g in graphs.values() if src in g.nodes), rg)
        dg = next((g for g in graphs.values() if dst in g.nodes), rg)
        if gate.commit_edge(sg, src, d["relation"], dst, cfg, gate.PATH_SCHEMA,
                            [prov] if prov else [], did, src_graph=sg, dst_graph=dg) == gate.COMMIT:
            ends |= {src, dst}
        n += 1
    att = _land_revived(revived, ends, ref, rg, graphs, cfgs, pl, prov, did, b0)
    for d, lay2, eb2, nid2 in rows:               # 재시도도 판정이다 — 그 문서 대장의 같은 키 행에 (B107 ③)
        _ledger(did, prov, d, lay2, eb2, attached=att.get(nid2))
    for a in pl.get("pending_attrs") or []:
        b = _builder(rg, cfg, did, rlay, b0.dict)
        b.put_attribute(ref, a["attr_name"], a["value"], a.get("context") or {},
                        a.get("provenance"), bool(a.get("context")))
        b.flush()
        n += 1
    _ledger_anchor(did, prov, ref, rlay, rg)
    return n


def _ledger_anchor(did, prov, ref, rlay, rg):
    """좌표가 선 행의 **좌표 행**을 그 판정으로(B113 ③ — 못 풀린 좌표 행이 대장에 보류로 남아 맞춤표의 `보류(행)`이
    재연결 뒤에도 그대로였다). 표기는 그 행의 것(없으면 — 좌표 칸이 비었던 행 — 선 좌표의 이름) · 표시 `by: retry`."""
    from core.build import ledger
    loc = prov[len(did) + 1:] if did and prov and str(prov).startswith(f"{did}#") else None
    rows = ((ledger.read(did) or {}).get("rows") or []) if loc else []
    hit = next((r for r in rows if r.get("role") == "anchor" and r.get("locator") == loc
                and r.get("verdict") != "anchor"), None)
    if hit is None:
        return
    canon = (rg.get(ref) or {}).get("canonical")
    new = ledger.row(locator=loc, field=hit.get("field"), role="anchor", surface=hit.get("surface") or canon,
                     canonical=canon, layer=rlay, path="skeleton", verdict="anchor", node_id=ref, by="retry")
    ledger.put_row(did, new, old=lambda r: r is hit or (r.get("role") == "anchor" and r.get("locator") == loc
                                                       and r.get("verdict") != "anchor"))
