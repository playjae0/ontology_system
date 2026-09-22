# -*- coding: utf-8 -*-
"""칸 3.1~3.7 **진입점** — 문서 하나를 인입하고, 빌드 말미에 전역 패스를 돈다.

`run_document()`가 파이프라인의 입구다: 인입 검사(3.1) → 형태 분기(정형/비정형) →
판정 예고 → 구축 → 대장·계측. `finalize()`는 **문서 하나로는 판정할 수 없는 것**
(mirrors·고아 재시도·근거 소실)을 빌드 말미에 한 번 돈다.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import matcher
from core.build import extract as extract_mod
from core.build import loop, prose as prose_mod, table as table_mod
from core.build.build import Builder
from core.build.ingest import IngestResult, ingest, load_schema
from core.build.ledger import Ledger
from core.build.retry import retry_orphans
from core.state import log, store
from core.state.bootstrap import COORD_CATEGORY, load_config, open_graph
from core.state.status import is_live

_LOG = log.get(__name__)


def finalize(layers=None):
    """빌드 말미 패스 — **전역 재평가가 필요한 자동 규칙**은 문서 빌드가 아니라 여기서 돈다.

    문서 빌드 안에서 돌리면 **뒤에 인입되는 문서가 만드는 노드를 보지 못한다** — mirrors
    재평가가 한 박자 늦어 큐가 1회차 3건 → 2회차 4건으로 수렴했다(20회차 후속 실측).
    노드에 짝 키를 적어 두는 것(`mirror_scope`·`mirror_name`)은 그대로 층 빌드가 하고,
    **재평가와 큐 갱신만** 이쪽으로 옮긴다 — 자동 규칙 자체를 옮기는 것이 아니다.

    큐 항목의 `doc_id`는 `None`이다. 이 조건은 **어느 한 문서의 것이 아니라 그래프 전체의
    상태**이기 때문이다 — 특정 문서에 귀속시키면 그 문서를 다시 넣을 때만 갱신되는
    지금의 문제로 되돌아간다.
    """
    from router import discover
    for layer in (layers or discover()):
        g = open_graph(layer)
        g.build_begin()
        Builder(g, load_config(layer), None, None, layer).link_mirrors()
        _evidence_lost(g)
        g.build_end()
    retry_orphans(layers)


def _evidence_lost(g):
    """근거가 0이 된 auto 노드·엣지 (카드 L9) — **삭제가 아니라 표시**다.

    회수(재인입) 시점이 아니라 여기서 판정하는 이유는 mirrors와 같다(D-65):
    회수 직후는 아직 재적재 전이라 "근거 0"이 참이 아니다. 재적재가 근거를 되돌리면
    이 조건은 성립하지 않아야 하고, 그러려면 **빌드가 끝난 뒤**에 봐야 한다.
    """
    store.drop("evidence_lost",
               lambda p: p.get("node_id") in g.nodes or p.get("src") in g.nodes)
    for n in g.nodes.values():
        if n.get("status") == "auto" and not n.get("provenance"):
            store.enqueue("evidence_lost",
                          f"근거가 모두 회수됐다 — '{n['canonical']}'",
                          None, {"node_id": n["id"], "canonical": n["canonical"]})
    for e in g.edges:
        if e.get("status") == "auto" and not e.get("provenance"):
            store.enqueue("evidence_lost",
                          f"근거가 모두 회수된 엣지 — {e['rel']}",
                          None, {"src": e["src"], "rel": e["rel"], "dst": e["dst"]})


# ---------------------------------------------------------------- 진입점
def _reject(doc_id, reason, payload):
    """문서 단위 실패 (C14) — **위반 하나면 통째 미인입**이고 큐로 드러낸다.

    그래프·청크·체크포인트에 아무것도 쓰지 않는다. 무음 폴백으로 밀어 넣으면
    잘못된 자리에 적재된 지식을 나중에 아무도 찾아내지 못한다.
    """
    store.enqueue("parse_failure", reason, doc_id, payload)
    res = IngestResult(doc_id)
    res.status, res.reason = "held", reason
    return res, None, False


def _entity_surfaces(env, schema):
    """이 문서가 **판정에 올릴 언급** — table은 entity role 열의 값들이다.

    표기만이 아니라 **그 값이 선 자리**(카테고리·좌표·축값·층)를 함께 낸다(B74 ①).
    예고가 판정과 같은 키로 사전을 보려면 키 재료가 전부 있어야 하고, 그 재료는
    스키마와 레코드에 있다 — **LLM 0**으로 센다.
    """
    fields = (schema or {}).get("fields") or {}
    out = []
    for rec in env.get("records") or []:
        for f, spec in fields.items():
            if (spec or {}).get("role") != "entity":
                continue
            v = rec.get(f)
            if isinstance(v, str) and v.strip():
                out.append({"surface": v.strip(), "field": f,
                            "category": (spec or {}).get("category"),
                            "target_layer": (spec or {}).get("target_layer"),
                            # 좌표는 행이 쓰는 것과 같은 순서다 — ref 없으면 group
                            "ref": rec.get("process_ref") or rec.get("process_group"),
                            "electrode_type": rec.get("electrode_type")})
    return out


def _plan_hit(b, m, layer):
    """이 언급이 **사전에 이미 있는가** — 판정이 쓰는 키·필터 그대로다 (B74 ①).

    키를 만드는 함수(`build.entity_key`)와 사전을 보는 함수(`matcher.dict_hits`)를
    판정과 **공유한다.** 복제하면 그 순간 예고가 다른 키로 사전을 보고, 비용을
    잘못 말한다 — 고친 결함이 그것이다(허브 실측 열셋째).

    좌표 해소도 판정과 같은 경로(골격 조회 → 하강 → 극성 상속)를 지나되 **쓰지
    않는다**: 미해소 좌표는 `defer` 자루로 받아 버린다(예고가 큐를 만들지 않는다).
    """
    from core.build.build import entity_key
    from core import matcher
    surface, category = m.get("surface"), m.get("category")
    if not surface or not category:
        return False
    lay = m.get("target_layer") or layer
    et = m.get("electrode_type")
    sink = []                       # 예고는 큐를 만들지 않는다 — 버리는 자루다
    ref_id, ref_g = (b.resolve_anchor(m.get("ref"), COORD_CATEGORY, "(예고)",
                                      defer=sink)
                     if m.get("ref") else (None, None))
    if ref_id:
        ref_id = b.descend_anchor(ref_id, et, ref_g)
    parent = ref_g.get(ref_id)["canonical"] if ref_id else None
    apol = b.anchor_polarity(ref_id, ref_g) if ref_id else None
    if ref_id is None and loop._scoped_category(category, lay, b):
        return False                # 좌표 없는 스코프 개체는 판정에 오르지 않는다
    eb = b.for_layer(lay)
    key, pol, _scoped, _sc = entity_key(surface, category, eb.cfg,
                                        electrode_type=et, parent_canonical=parent,
                                        anchor_polarity=apol)
    scope_cats = (eb.cfg.get("canonical_scope") or {}).get("bind_categories", [])
    return bool(matcher.dict_hits(key, category, lay, eb.g, b.dict,
                                  polarity=pol, parent=parent,
                                  scope_cats=scope_cats))


def decision_plan(mentions, refs, layer):
    """**판정 예고** — 부르기 전에 몇 번 부를지 센다 (B72 ② · B74 ① · B22의 정신).

    넷을 센다: ①판정에 올라가는 **값의 수**(행 × entity 열) ②문서 내 중복을 제외한
    표기 종수 ③그중 **사전이 이미 아는 것**(값 단위 — 판정과 같은 키) ④골격 밖 좌표.

    **상한은 ① − ③이다**: 개체 판정은 **행마다** 돈다(같은 표기라도 부모 좌표가
    다르면 다른 노드다). 사전 히트는 `match`가 exact로 끊으므로 호출이 없고, 그
    수를 **판정과 같은 함수로** 세기 때문에 뺄 수 있다(B74 ① — 구판은 원 표기로
    세어 「31종」이라 하고 판정은 0이었다). 처음 인입은 사전이 **도는 중에** 차므로
    예고가 덜 세고, 그때도 상한은 실제를 덮는다(덜 세면 상한이 커진다).

    사전·그래프만 읽는다 — **LLM 0**이고, 큐도 만들지 않는다.
    """
    from core.dictionary import Dictionary
    from core.state.ids import norm
    from core.build.build import Builder
    dic = Dictionary.open()
    g = open_graph(layer)
    b = Builder(g, load_config(layer), None, "(판정예고)", layer)
    kinds, hits, vals = [], 0, 0
    for m in mentions:
        if isinstance(m, str):
            m = {"surface": m}
        s = m.get("surface")
        if not s:
            continue
        vals += 1
        n = norm(s)
        if n not in kinds:
            kinds.append(n)
        if _plan_hit(b, m, layer):
            hits += 1
    out_of_list = []
    for r in refs:
        n = norm(r)
        if n in out_of_list:
            continue
        if not [nid for nid in dic.lookup(r)
                if nid in g.nodes
                and (g.get(nid) or {}).get("status") in ("seed", "confirmed")]:
            out_of_list.append(n)
    return {"단계": "판정예고", "값_수": vals, "표기_종수": len(kinds),
            "사전_히트": hits, "예상_호출": max(0, vals - hits),
            "목록밖_좌표": len(out_of_list)}


def doc_queue_summary(doc_id):
    """이 문서가 남긴 큐 — `{kind: (건수, 행수)}` (B72 ② — 집계 단위가 곧 화면이다)."""
    out = {}
    for x in store.read(store.QUEUE, []):
        if x.get("doc_id") != doc_id:
            continue
        n, rows = out.get(x["kind"], (0, 0))
        out[x["kind"]] = (n + 1, rows + int((x.get("payload") or {}).get("rows", 1)))
    return out


class Stopped(Exception):
    """**사람이 판정 도중 멈췄다** (B75 ③ — `--step-every`).

    진행 콜백이 던지고 `run_document`가 받는다. 계약은 `--step`의 `q`와 같다:
    **그 문서는 그래프·사전·큐 쓰기 0**이고 체크포인트(parsed/·extract/·청크)는
    남는다. 부분 쓰기를 남기면 다음 인입이 「반쯤 들어간 문서」 위에 쌓인다.
    """


def run_document(path_or_env, layer=None, *, allow_duplicate=False,
                 routing=None, notice=None):
    env = path_or_env
    doc_id, doc_type = env["doc_id"], env["doc_type"]

    kind = env.get("payload_kind")
    if kind not in loop.PAYLOAD_KINDS:                        # 닫힌 2값 (B2)
        return _reject(doc_id, f"payload_kind가 닫힌 2값 밖이다 — {kind!r}",
                       {"payload_kind": kind, "doc_type": doc_type})
    schema = load_schema(doc_type)
    if schema is None and layer is None:                 # 미등록 doc_type (B3)
        return _reject(doc_id, f"미등록 doc_type '{doc_type}' — 구축 모드 대상이다",
                       {"doc_type": doc_type, "source_path": env.get("source_path")})
    layer = layer or schema["layer"]
    cfg = load_config(layer)

    res = ingest(env, allow_duplicate=allow_duplicate,   # ①doc_hash ①′회수 ②id ③필드
                 routing=routing)
    if res.status == "held":
        return res, None, False

    graph = open_graph(layer)
    graph.build_begin()
    # **되돌릴 자리를 먼저 잡는다**(B75 ③) — 그래프는 말미에 한 번 저장되지만
    # 큐·청크는 도중에 쓰인다. 사람이 판정 중간에 멈추면 그 둘도 되돌려야
    # 「그래프 쓰기 0」이 참이 된다.
    _q0 = store.read(store.QUEUE, [])
    _c0 = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    loop.LOWRES["n"] = 0
    from core import matcher as _mt
    _mt.reset_stats()                    # 판정 계측은 문서 단위다 (B73 ①)
    _n0 = len(graph.nodes)
    _e0 = len(graph.edges)
    _a0 = sum(1 for n in graph.nodes.values() if n.get("status") == "auto")

    try:
        _, metrics, extracted = _build_document(
            env, kind, schema, cfg, layer, graph, doc_id, notice, _n0, _e0, _a0)
        return res, metrics, extracted
    except Stopped as stop:
        # 쓴 것을 되돌린다 — 그래프는 저장 전이라 **디스크가 이미 옛 판**이고,
        # 큐·청크는 스냅샷으로 돌린다. 메모리의 그래프는 버린다(다음 호출이
        # 디스크에서 새로 연다 — `open_graph`는 캐시하지 않는다).
        store.write(store.QUEUE, _q0)
        store.write(store.CHUNKS, _c0)
        res.status, res.reason = "held", str(stop)
        return res, None, False


def _build_document(env, kind, schema, cfg, layer, graph, doc_id,
                    notice, _n0, _e0, _a0):
    """구축 본체 — 되돌림 경계 **안**이다(B75 ③). 위 함수가 그 경계를 친다."""
    from core import matcher as _mt
    extracted = False
    builder = None
    if kind == "table":
        if notice is not None:
            # **판정 전에** 예고한다 — 쓰고 나서 알면 결정할 것이 없다(B22).
            notice(decision_plan(_entity_surfaces(env, schema),
                                 [r.get("process_ref") for r in env.get("records") or []
                                  if r.get("process_ref")], layer))
        builder = table_mod.build_table(env, cfg, schema, graph)
    else:
        _land_hierarchy(env)
        ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        loc2id = {c["source_locator"]: cid for cid, c in ch.items()
                  if c.get("doc_id") == env["doc_id"]}
        vocab = _vocab(cfg)
        ck, extracted = extract_mod.extract(env, cfg, loc2id, vocab)
        if notice is not None:
            # prose의 표기는 **추출이 끝나야** 안다 — 그래서 자리가 여기다.
            _by_loc = {c["source_locator"]: c for c in env.get("chunks") or []}
            _loc_of = {cid: loc for loc, cid in loc2id.items()}
            notice(decision_plan(
                [{"surface": e.get("surface"), "category": e.get("category"),
                  "ref": (_by_loc.get(_loc_of.get(c["chunk_id"])) or {})
                  .get("process_ref"),
                  "electrode_type": (_by_loc.get(_loc_of.get(c["chunk_id"])) or {})
                  .get("electrode_type")}
                 for c in ck["candidates"]
                 for e in (c.get("entities") or []) if e.get("surface")],
                [c.get("process_ref") for c in env.get("chunks") or []
                 if c.get("process_ref")], layer))
        builder = prose_mod.build_prose(env, cfg, graph, ck["candidates"])

    for other in builder.graphs():          # 걸침 층에 쓴 것도 저장된다 (D3)
        if other is not graph:
            other.save()
    metrics = graph.build_end()
    _record_build(doc_id, metrics)
    if notice is not None:
        notice({"단계": "끝", "doc_id": doc_id,
                "노드": len(graph.nodes) - _n0, "엣지": len(graph.edges) - _e0,
                "auto": sum(1 for n in graph.nodes.values()
                            if n.get("status") == "auto") - _a0,
                "저해상도": loop.LOWRES["n"], "총_노드": metrics.get("nodes"),
                "판정": dict(_mt.STATS), "큐": doc_queue_summary(doc_id)})
    return None, metrics, extracted


def _land_hierarchy(env):
    """분할 판정의 두 표시를 **큐로 착지시킨다** (문서 4 §4.7-3 · [정정] 46).

    `hierarchy_unresolved`는 닫힌 20종에 자리가 있는데 **enqueue하는 코드가 어디에도
    없었다** — 파서가 `ParseResult.failures`로 말하면 그것은 화면에 한 번 찍히고
    사라졌고, 「아무것도 조용히 버리지 않는다」(§4.7-2)가 이 경로에서만 공문이었다.

    한 kind에 두 경우가 실리므로 payload의 `case`가 가른다 — 처방이 다르다:

    **`case`는 닫힌 두 값이다**([정정] 48 ①) — 처방이 **반대**라 갈라야 한다.
    한 kind에 뭉쳐 두면 사람이 큐 화면에서 무엇을 해야 할지 모른다.

    | case | 무슨 일 | 사람이 할 일 |
    |---|---|---|
    | `flat_fallback` | 계층 신호 0건이거나 레벨 비단조 — **계층을 못 세웠다** | 문서·지도를 본다 |
    | `size_out_of_band` | 계층은 세웠고 레벨도 골랐는데 **크기가 목표 구간 밖** | 레벨을 얕게/깊게 옮긴다 |

    `size_out_of_band`는 **판단 재료 넷**을 싣는다: 고른 레벨 · 그 레벨의 평균
    행수 · 목표 구간 · 어느 쪽으로 벗어났나(`short`/`long`). **`side`는 박지 않고
    앞 둘에서 파생한다** — 박아 두면 짧은 쪽 처방(레벨을 얕게)이 긴 쪽 문서에도
    나가고, 그 오류는 화면만 보아서는 드러나지 않는다.

    **새 kind를 만들지 않는다**(문서 1 G7 — 닫힌 20종). **자동으로 지도 패스(LLM)로
    넘기지 않는다**([정정] 46) — 넘기면 인입마다 비용이 조용히 붙는다.

    문서당 case별 1건이다 — 청크마다 달면 세밀한 목차 하나가 큐를 통째로 채운다.
    """
    doc_id = env["doc_id"]
    cases = {
        "flat_fallback": ("계층을 세우지 못해 통째로 실었다 — 문서·지도를 보고 "
                          "분할 방법을 사람이 정한다",
                          lambda m: m.get("hierarchy_unresolved")),
        "size_out_of_band": ("분할 레벨은 골랐으나 청크 크기가 목표 구간 밖이다 — "
                             "최근접 레벨로 실었다. 레벨을 옮길지는 사람이 정한다",
                             lambda m: m.get("split_level_out_of_range")),
    }
    for case, (reason, hit) in cases.items():
        got = [c for c in env.get("chunks") or [] if hit(c.get("meta") or {})]
        if not got:
            continue
        metas = [c.get("meta") or {} for c in got]
        payload = {
            "case": case,
            "doc_id": doc_id,
            "chunks": len(got),
            "locators": [c.get("source_locator") for c in got][:10],
            "frames": sorted({m["frame"] for m in metas if m.get("frame")}),
            "reasons": sorted({m["unresolved_reason"] for m in metas
                               if m.get("unresolved_reason")}),
        }
        if case == "size_out_of_band":
            payload.update(_band_material(metas))
        store.enqueue("hierarchy_unresolved", reason, doc_id, payload)


def _band_material(metas):
    """`size_out_of_band`의 판단 재료 넷 ([정정] 48 ①).

    **`side`는 파생값이다** — 평균이 하한 미만이면 `short`(레벨을 얕게 = 더 묶는다),
    상한 초과면 `long`(레벨을 깊게 = 더 쪼갠다). 처방이 반대이므로 한쪽으로 박히면
    큐 화면이 절반의 문서에 틀린 처방을 낸다.

    한 문서가 여러 프레임을 가지면 레벨이 갈릴 수 있다 — **목록으로 싣고**
    평균은 그중 구간에서 가장 멀리 벗어난 값을 대표로 쓴다(가장 급한 것이 머리에
    오는 편이 사람에게 낫다).
    """
    band = next((m["split_level_band"] for m in metas if m.get("split_level_band")),
                None)
    levels = sorted({m["split_level"] for m in metas
                     if m.get("split_level") is not None})
    avgs = [m["split_level_avg_rows"] for m in metas
            if m.get("split_level_avg_rows") is not None]
    out = {"chosen_level": levels[0] if len(levels) == 1 else (levels or None),
           "chosen_avg_rows": None, "target_band": band, "side": None}
    if not (band and avgs):
        return out
    lo, hi = band
    avg = max(avgs, key=lambda a: max(lo - a, a - hi))     # 가장 멀리 벗어난 값
    out["chosen_avg_rows"] = avg
    out["side"] = "short" if avg < lo else ("long" if avg > hi else None)
    return out


BUILD_METRICS = "build_metrics.json"


def _record_build(doc_id, metrics):
    """**빌드가 자기 소요를 남긴다** ([정정] 44).

    구판은 계기판 7·8이 `open_graph().build_begin()/build_end()`를 돌려 **`save()`
    시간**을 쟀다 — 그것은 빌드 소요가 아니라 직렬화 시간이라, 「build 30초 초과 =
    R10 판정 개시」(문서 7 · 계기판 8)의 재료가 될 수 없었다. 재는 자리는 빌드다.

    **로그이지 큐가 아니다** — 아무도 처리하지 않고 추이만 본다(§5.5 규율 5).
    규율 5(측정이 재료를 오염시키지 않는다)는 유지된다: 막는 것은 **측정의 자기
    오염**이지 빌드가 제 소요를 적는 것이 아니다(§5.5 단서).
    """
    try:
        hist = store.read(BUILD_METRICS, [])
        hist.append({"at": store._now(), "doc_id": doc_id,
                     "seconds": metrics.get("gauge8_build_seconds"),
                     "bytes_by_layer": {metrics.get("layer"):
                                        metrics.get("gauge7_graph_bytes")}})
        store.write(BUILD_METRICS, hist[-50:])
    except Exception as e:                                  # noqa: BLE001
        # 계측 실패가 빌드를 죽이지 않는다 — 남기지 못한 사실만 결함으로 드러낸다.
        store.append_defect(f"{doc_id}: 빌드 계측 기록 실패 — {type(e).__name__}: {e}")


def skeleton_closed_list(layer):
    """골격 닫힌 목록 — **스냅샷 파일이 정본**이다(D-11). 파서와 같은 실물을 본다.

    파일이 없으면(부트스트랩 전) 빈 목록이다 — 그래프로 몰래 폴백하지 않는다.
    폴백하면 "둘이 같은 실물을 본다"가 조용히 깨지고 그것이 곧 이 파일의 존재 이유다.
    """
    return (store.read(store.SKELETON_LIST, {}).get(layer) or {}).get("nodes", [])


def _vocab(cfg):
    """USE_MOCK 문형 폴백이 쓸 표면형→카테고리 표 — **골격 닫힌 목록 스냅샷만** 읽는다.

    구판은 사전과 **현재 그래프 상태**를 어휘로 넘겼다. 그러면 추출이 "지금까지 무엇이
    인입됐나"에 의존해 **문서 인입 순서에 따라 그래프가 달라지고**(실측 정순 66 · 역순 65),
    체크포인트가 그 우연을 영구히 동결한다 — 추출 계약 규약 1이 노드 id 참조를 금지한
    이유가 정확히 이 메커니즘이고, 표면형 어휘라는 뒷문으로 같은 의존이 성립해 있었다.
    재현성 3입력(adapter/prompt/config_version)에 기록되지 않는 네 번째 입력이기도 하다.

    골격(`status="seed"`)은 부트스트랩이 인입 **전에** 세우고 인입이 바꾸지 않으므로
    순서 무관이다. 좌표 닫힌 목록 = 골격 전 노드이며(A11-6 · D-45), 그 실물이
    **`data/skeleton_closed_list.json` 스냅샷**이다(D-11 확정 — P1이 실물화).
    G6.5에서는 파일이 없어 그래프의 seed 노드를 직독했는데, 그러면 파서와 에이전트가
    **다른 실물**을 보게 된다 — 파서는 이 레포의 그래프를 읽지 않기 때문이다(D-9).
    """
    from core.state.ids import norm
    v = {}
    for n in skeleton_closed_list(cfg["layer"]):
        for s in [n["canonical"]] + list(n.get("aliases") or []):
            v[norm(s)] = n["category"]
    return {k: c for k, c in v.items() if k and c}
