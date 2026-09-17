# -*- coding: utf-8 -*-
"""칸 3.2·3.5 — **행 루프**: role 핸들러와 그 공용 재료 (문서 4 §4.3·§4.5).

한 행(정형)·한 청크(비정형)가 지나는 자리다 — 무엇을 노드로 세우고 무엇을 속성으로
붙이는가는 스키마의 `role`이 정하고, 그 분기가 `HANDLERS` 표 하나다. 구조 필드
(`STRUCTURAL`)는 핸들러를 타지 않고 시스템이 직접 읽는다(§2.5 규약 3).
**정형·비정형 둘 다 이 모듈을 쓴다** — 재료가 같아야 두 갈래가 같은 판정을 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.build import extract as extract_mod
from core import matcher, paths
from core.build import gate
from core.state import log, store
from core.build.build import Builder
from core.build.ledger import Ledger
from core.state.bootstrap import load_config, open_graph
from core.build.ingest import IngestResult, ingest, load_schema
from core.state.status import is_live
from core.build.retry import retry_orphans

# **구조 필드** — role 핸들러를 타지 않고 시스템이 직접 읽는다(문서 2 §2.5 규약 3).
# `doc_type`은 조각 공통 층의 일원이고(§2.2 계약 ①) 스키마 조회 키다(봉투 값의 반복) —
# 여기 없으면 조각이 계약대로 달고 온 필드가 `unknown_field` 큐로 간다.
STRUCTURAL = {"doc_type", "process_group", "process_ref", "process_no",
              "electrode_type", "source_locator", "section", "context"}

# 봉투 `payload_kind`의 **닫힌 2값**(CH2 2.2). 밖의 값은 폴백 대상이 아니라 계약 위반이다.
PAYLOAD_KINDS = ("table", "prose")

_LOG = log.get(__name__)

# 공정좌표 anchor의 목표 카테고리 — 공용 블록(schemas/blocks.json)이 소유한다.
COORD_CATEGORY = json.loads(
    paths.blocks()
    .read_text(encoding="utf-8"))["process_coord"]["process_ref"]["target_category"]


def _prov(rec, doc_id=None):
    """provenance 한 항목 — **문서 이름이 함께 실린다**(`{doc_id}#{locator}` · [정정] 43).

    구판은 locator만 실었다. 그런데 locator는 **문서 안에서만** 유일하다 —
    실파서가 내는 것은 `Sheet1!R12`·`슬라이드 3` 꼴이라 두 문서가 같은 문자열을
    쓴다. 그러면 재인입 회수(`withdraw`)가 **다른 문서의 근거까지 걷어내고**,
    계기판 2는 어느 문서 것인지 가르지 못한다.

    **접두가 붙는 것은 provenance뿐이다** — 계약 A의 `source_locator`는 끝까지
    접두가 없다([정정] 42). 청크 대응표(`by_locator`·`loc_of`·`loc2id`)는 raw
    locator로 맞추는 자리이고, 거기에 접두가 섞이면 대응이 통째로 깨진다.

    `seed`·`auto:{규칙}`은 문서 조각에서 오지 않으므로 대상이 아니다 — 이 함수가
    레코드에서만 불리므로 자연히 그렇고, 어서션이 그것을 잠근다.
    """
    loc = rec.get("source_locator")
    if not loc:
        return loc
    return f"{doc_id}#{loc}" if doc_id else loc


def _check_fields(rec, fields, prov, doc_id):
    """③ 필드 검증 (CH2 2.8) — 계약 위반은 조용히 통과하지 않는다.

    스키마 밖 필드는 **값을 동봉해** `unknown_field` 큐로 간다(레코드는 어디에도
    저장되지 않으므로, 여기서 안 실으면 그 값은 영구 소실이다 — 카드 G5).
    `optional` 미선언 필드의 부재는 `missing_field` 큐다. 둘 다 닫힌 20종 안이고
    **문서를 죽이지 않는다** — 문서 단위 실패는 파서 측 계약이다(C14).
    """
    loc = rec.get("source_locator")
    for f, v in rec.items():
        if f in fields or f in STRUCTURAL:
            continue
        # **문서 × 필드 단위 1건**(B72 ②) — 같은 열이 118행이면 사람이 판정할 것은
        # 하나다(「이 열이 스키마에 없다」). 값은 `items[]`에 그대로 남는다(G5).
        store.enqueue_rows("unknown_field", f"스키마에 없는 필드 '{f}'", doc_id, f,
                           {"field": f, "value": v, "provenance": prov},
                           locator=loc)
    for f, spec in fields.items():
        if spec.get("optional") or f in STRUCTURAL:
            continue
        if rec.get(f) in (None, ""):
            store.enqueue_rows("missing_field", f"필수 필드 '{f}' 부재", doc_id, f,
                               {"field": f, "provenance": prov}, locator=loc)


def _context(holder, prov, doc_id):
    """조각·봉투의 `context`는 **임의 딕셔너리**다(CH2 2.2) — 스칼라로 오면 계약 위반이다.

    D-30과 같은 계보로 처리한다: 인입 코드는 계약 위반에 **예외로 죽지 않고** 큐로
    표면화한 뒤 그 필드만 버리고 전진한다. 한 필드의 형태 오류로 레코드 전체를 잃으면
    "조용히 버리지 않는다"가 반대 방향으로 깨지고, 죽어 버리면 나머지 행의 정상 지식까지
    통째로 사라진다. 새 kind를 만들지 않는다 — `missing_field`가 "필수 값 부재·계약 위반"을
    이미 덮는다(CH3B 3.7 · 닫힌 20종).
    """
    c = holder.get("context")
    if c is None or isinstance(c, dict):
        return dict(c or {})
    store.enqueue("missing_field",
                  f"context가 딕셔너리가 아니다 — {type(c).__name__} {c!r} (CH2 2.2 계약 위반)",
                  doc_id, {"field": "context", "value": c, "provenance": prov})
    return {}


def _scalar(value, field, prov, doc_id):
    """**entity·anchor**의 값이 단일이라는 전제를 코드가 방어한다 (문서 2 §2.7).

    **attribute는 대상이 아니다** — §2.4-③이 "구조체·배열도 통째로 하나의 값"으로
    저장한다고 규정한다. 여기서 막는 것은 리스트가 사전을 오염시키는 경로다.

    복수값 전개는 파서 몫이지만(normalizer), 계약이 핸들러 측 방어를 따로 요구한다 —
    리스트가 그대로 오면 `norm()`의 `str()` 강제 변환과 포함 규칙을 타고 **기존 노드에
    조용히 흡수되어 사전을 오염시킨다**(실측: `dictionary`에 `"['노칭 프레스', …]"` 키).
    D-60의 `context` 방어와 같은 계보다 — 죽지 않고 그 필드만 버린 뒤 큐로 드러낸다.
    """
    if isinstance(value, (str, int, float)):
        return True
    store.enqueue("missing_field",
                  f"'{field}'가 단일 값이 아니다 — {type(value).__name__} (카드 D6)",
                  doc_id, {"field": field, "value": value, "provenance": prov})
    return False


def _attach_target(a):
    """`attach_to`를 **`{name, category}`**로 정규화한다 (문서 4 §4.10 규약 8 — B11).

    추출이 이름만 내면 판정기가 카테고리를 몰라 **후보 검색이 전 카테고리를 훑고
    선언 순서가 답을 정한다** — 실측으로 `정밀 노칭 프레스`가 Process(노칭)와
    Unit(노칭 프레스) 양쪽에 0.95로 걸렸다.

    **카테고리를 못 고르면 `null`이다** — 추측해서 채우지 않고 그 부착은 규칙 B
    폴백으로 간다(§4.4-4).

    옛 형태(문자열)도 받는다 — 힌트 자산·외부 산출이 섞여 들어올 수 있고, 그때는
    `category: None`으로 올려 폴백 갈래를 태운다. **조용히 카테고리를 지어내지 않는다.**
    """
    v = a.get("attach_to")
    if v is None:
        return None, None
    if isinstance(v, str):
        return (v or None), None
    return (v.get("name") or None), v.get("category")


# **저해상도 부착 계수** — 문서마다 0으로 시작한다(`run_document`가 리셋).
# 화면이 제 계산을 하지 않게 **세는 자리는 붙이는 자리**다.
LOWRES = {"n": 0}


def _fallback_attach(b, cfg, graph, child, ref, ref_g, prov, doc_id, evidence_chunk=None):
    """**규칙 B — 부착 폴백** (문서 4 §4.4-4).

    부착 대상이 없거나 미해소면 그 행/청크의 **공정좌표(`process_ref` 해소 노드)**에
    붙인다. 이것은 오류가 아니라 **저해상도**이고, 더 정밀한 소속이 확보되면(정형
    edges·attach 해소·재시도 성공) 보강된다.

    **좌표도 미해소면 아무것도 만들지 않는다** — 연쇄 드롭이 정상 동작이다(§4.4-97):
    좌표 없이 Property를 만들면 canonical 스코프를 붙일 수 없어 §4.5-6이 병합
    후보에서 영구 배제하는 **부모 미해소 노드**가 된다.

    관계는 카테고리쌍 매핑이 정한다 — 코드가 관계 이름을 알지 않는다(B1).
    매핑에 없는 쌍이면 엣지를 만들지 않고 결함 로그로 드러낸다.
    """
    if child is None or ref is None:
        return False
    LOWRES["n"] += 1                     # 요약 한 줄의 재료 (B72 ②)
    tg = ref_g if ref_g is not None else graph
    rel = gate.pair_relation(cfg, (tg.get(ref) or {}).get("category"),
                         (graph.get(child) or {}).get("category"))
    if not rel:
        store.append_defect(
            f"{doc_id}: 규칙 B 폴백 — 카테고리쌍 매핑 없음 "
            f"({(tg.get(ref) or {}).get('category')} → "
            f"{(graph.get(child) or {}).get('category')})")
        return False
    gate.commit_edge(graph, ref, rel, child, cfg, gate.PATH_SCHEMA,
                     [prov], doc_id, evidence_chunk=evidence_chunk,
                     src_graph=tg, dst_graph=graph)
    return True


def _field_surface(name, rec):
    """엣지 끝점이 가리키는 **원 표면형** — 재시도 배치가 다시 해소할 재료다."""
    if str(name).startswith("@"):
        return rec.get(str(name)[1:])
    return rec.get(name)


def _blank_endpoint(edge, rec, fields):
    """이 엣지의 끝점이 **빈 행**인가 — 미해소와 다르다.

    `optional: true`의 의미는 "from/to가 **빈 행**에서 해당 엣지만 조용히 생략"이다
    (문서 2 §2.4-⑥ · §2.7-③). **미해소는 빈 행이 아니다** — 값이 있는데 못 찾은
    것은 큐로 가야 할 사건이고, 그것까지 조용히 생략하면 「아무것도 조용히 버리지
    않는다」가 optional 선언 하나로 무력화된다.

    `@좌표` 표기는 구조 필드를 가리키므로 레코드에서 직접 본다.
    """
    for side in ("from", "to"):
        name = edge.get(side)
        if str(name).startswith("@"):
            if rec.get(str(name)[1:]) in (None, ""):
                return True
        elif name in fields and rec.get(name) in (None, ""):
            return True
    return False


def _land_deferred(defer, dropped, pending, doc_id, *, dropped_entities=None,
                   coord_missing=False, prov=None):
    """미뤄 둔 큐 적재를 **레코드 말미에** 착지시킨다 (문서 2 §2.4-①·③).

    큐 항목이 **재시도 배치의 유일한 손잡이**다(문서 4 §4.7-5). 그래서 항목이
    보유해야 하는 것이 셋이다:

    1. **생략된 엣지의 출발 노드** — 골격이 자라면 그 노드를 좌표에 붙인다.
    2. **연쇄 드롭된 표면형** — 끝점이 표면형으로만 남은 것. 재해소의 재료다.
    3. **보류된 attribute**(`pending_attrs`) — 좌표가 해소되면 그때 저장한다.

    보유하지 않으면 골격이 나중에 자라도 그 노드·값은 영영 붙지 않는다 —
    시스템이 자동으로 기존 문서를 다시 읽는 경로는 없다(문서 4 §4.8-7).
    """
    for item in defer:
        pl = dict(item["payload"])
        if dropped:
            pl["dropped_edges"] = dropped
        if pending:
            pl["pending_attrs"] = pending
        if dropped_entities:
            # **연쇄 드롭된 entity의 표면형·target_layer·category**(§4.4) —
            # 재시도가 좌표를 해소하면 이것으로 노드를 **새로 세운다.**
            pl["dropped_entities"] = dropped_entities
        # **표기 단위 1건**(B72 ②) — 같은 골격 밖 표기가 41행이면 사람이 할 일은
        # 하나다(그 표기를 골격에 잇는다). 행마다 다른 재시도 재료(provenance ·
        # dropped_edges · pending_attrs)는 `items[]`에 쌓여 그대로 남는다.
        store.enqueue_rows("orphan_anchor", item["reason"], doc_id,
                           pl.get("surface") or item["reason"], pl,
                           locator=(pl.get("provenance") or "").split("#")[-1] or None)
    if coord_missing and not defer:
        # **좌표 값이 아예 없는 행**([개정] B56-2). `resolve_anchor`는 표면형이
        # 없으면 일찍 돌아오므로 `defer`가 비어 있다 — 구판은 `for item in defer:`
        # 라 **0건 적재**였고, 그 행이 만든 드롭·보류가 어디에도 안 남았다.
        # **새 kind를 만들지 않는다** — `missing_field`가 「필수 값 부재」를 덮고,
        # 재시도 대상이 아니라 sweep이 물지 않는다.
        pl = {"field": "process_ref", "provenance": prov,
              "note": "process_ref·process_group이 둘 다 없다 — 좌표가 서지 않는다"}
        if dropped:
            pl["dropped_edges"] = dropped
        if pending:
            pl["pending_attrs"] = pending
        if dropped_entities:
            pl["dropped_entities"] = dropped_entities
        store.enqueue("missing_field",
                      "공정좌표 값 부재 — process_ref·process_group 둘 다 null",
                      doc_id, pl)
    return defer

# ================================================================ 핸들러 루프
# 문서 2 §2.7 — **코드에는 필드명이 등장하지 않고 role만이 분기 스위치다.**
# core는 스키마를 순회할 뿐이다("모든 문서를 수용하는 똑똑한 실행기"가 아니라
# "가정을 안 하는 단순한 순회기").


class Ctx:
    """핸들러 공통 맥락 — 문서 2 §2.7이 **여섯**으로 못박은 구성이다.

    | 이름 | 무엇 |
    |---|---|
    | `graphs` | 층별 graph 묶음 — 걸침 entity가 다른 층에 앉는다 |
    | `dic` | 전 층 공유 동의어 사전 (`core/dictionary.py` 관문) |
    | `buffer` | **문서 해소 버퍼** — `정규화 표면형 → node_id`, 수명은 문서 하나 |
    | `queue` | 수정 큐 적재 창구 |
    | `record` | 지금 처리 중인 레코드(또는 청크) |
    | `schema` | 매칭 스키마 |

    **버퍼를 열거에서 빼지 않는다** — 빠지면 핸들러가 attach_to의 해소 범위(문서 4
    §4.10-6 — 문서 해소 버퍼 전체 + 사전)에 손이 닿지 않아 그 조항이 구현 불가가 된다.
    레코드 단위 `resolved`(필드명이 키)와는 **다른 그릇**이다.

    `state`는 여섯의 확장이 아니라 **레코드 유도값 캐시**다 — 좌표(`ref`)·부모
    canonical·극성처럼 `record`+`graphs`+`dic`에서 매번 다시 계산할 수 있는 것을
    레코드당 한 번만 구해 둔다. 계약은 여섯이고 이것은 그 위의 편의다.
    """

    __slots__ = ("graphs", "dic", "buffer", "queue", "record", "schema", "state")

    def __init__(self, graphs, dic, buffer, queue, record, schema, state):
        self.graphs, self.dic, self.buffer = graphs, dic, buffer
        self.queue, self.record, self.schema, self.state = queue, record, schema, state


def h_anchor(value, spec, ctx):
    """**anchor — 닻.** 골격 노드를 *찾는다*. 새로 만들지 않는다(P2).

    반환: `resolved_id` 또는 `None`. 미해소는 `orphan_anchor`로 가되 **적재는
    레코드 말미로 미룬다**(문서 2 §2.4-①) — 그 행이 무엇을 만들었는지가 아직
    정해지지 않았고, 큐 항목이 재시도의 손잡이이기 때문이다.
    """
    st = ctx.state
    nid, ng = st["b"].resolve_anchor(value, spec["target_category"], st["prov"],
                                     defer=st["defer"])
    if nid is not None and ng is not st["graph"]:
        st["external"][st["field"]] = ng
    return nid


def h_entity(value, spec, ctx):
    """**entity — 개체.** 노드가 될 자격이 있는 것. 3분기(매칭/신규/불확실).

    **스키마가 층을 선언하면 그 층에 해소한다**(`target_layer`). 선언을 안 읽으면
    걸침 개체가 자기 층에 복제되어 문서 간 병합이 조용히 깨진다.

    해소 결과는 **문서 해소 버퍼에도 싣는다** — attach_to의 해소 범위가 청크·행
    경계를 넘기 때문이다(문서 4 §4.10-6). 층 간 동명은 **마지막 해소가 이긴다**(§4.2).
    """
    st = ctx.state
    lay = spec.get("target_layer") or st["cfg"]["layer"]

    # **좌표 없는 노드를 미리 만들어 두지 않는다**(문서 4 §4.4 — B14).
    #
    # 가르는 기준은 **좌표가 canonical에 들어가는가**다:
    #   · 스코프를 못 붙이는 노드(Property·걸침) → **만들지 않는다**
    #   · 스코프와 무관한 노드(Failure)          → 만든다 (occurs_in의 출발 노드)
    #
    # 만들면 §4.5-6이 병합 후보에서 **영구 배제**하는 부모 미해소 노드가 되고,
    # 그 배제는 영구라 나중에 좌표가 해소돼도 흡수되지 않는다. 재시도 배치는 큐
    # 항목이 보유한 재료로 노드를 **새로 세우므로** 미리 만든 것은 중복으로 남는다.
    # 실측(2A P-C): `레이저노칭` 미해소 행에서 `cathode 빔 출력`이 엣지 0·attrs
    # 빈 채로 남아 **어느 경로로도 회수되지 않았다.**
    #
    # 대신 그 재료를 `orphan_anchor` 큐 항목이 보유한다 — 그것이 재시도의 손잡이다.
    if st["ref"] is None and _scoped_category(spec["category"], lay, st["b"]):
        st["dropped_entities"].append(
            {"surface": value, "category": spec["category"],
             "target_layer": lay, "field": st["field"]})
        _ledger_entity(st, value, lay, None)
        return None

    eb = st["b"].for_layer(lay)
    nid = eb.resolve_entity(value, spec["category"], st["prov"],
                            electrode_type=st["et"],
                            parent_canonical=st["parent"],
                            anchor_polarity=st["anchor_pol"])
    _ledger_entity(st, value, lay, eb.last)
    if eb is not st["b"]:
        st["external"][st["field"]] = eb.g
    if nid is not None:
        ctx.buffer[_n(value)] = nid          # 층으로 나누지 않는다 (문서 4 §4.2)
    return nid


_VERDICT = {"match": "match", "new": "new", "uncertain": "uncertain",
            "gate_reject": "gate_reject"}


def _ledger_entity(st, surface, layer, last):
    """entity 값 하나의 대장 행 — **판정이 아는 것을 그대로 옮긴다**(B74 ②).

    `last`가 없으면 판정에 오르지도 못한 값이다(좌표 미해소로 드롭 — 그 재료는
    `orphan_anchor` 큐가 들고 있다). 그것도 **행으로 남는다**: 대장이 「이 문서의
    값 전부」를 덮지 않으면 행 단위 눈 검수가 성립하지 않는다.
    """
    b = st["b"]
    if b.ledger is None:
        return
    if not last:
        b.ledger.add(locator=st.get("locator"), field=st.get("field"),
                     role="entity", surface=surface, layer=layer,
                     path="none", verdict="orphan", queue_kind="orphan_anchor")
        return
    b.ledger.add(locator=st.get("locator"), field=st.get("field"), role="entity",
                 surface=surface, canonical=last.get("canonical"),
                 layer=last.get("layer") or layer,
                 path=last.get("path") or "none",
                 verdict=_VERDICT.get(last.get("verdict"), "pending"),
                 node_id=last.get("node_id"),
                 candidates_n=last.get("candidates_n", 0),
                 confidence=last.get("confidence", 0.0),
                 llm=last.get("llm"), queue_kind=last.get("queue_kind"))


def _scoped_category(category, layer, builder):
    """이 카테고리는 **좌표가 canonical에 들어가는가** (문서 4 §4.4 — B14의 기준).

    판정은 층 config의 `canonical_scope.bind_categories`가 한다 — **코드가 카테고리
    이름을 알지 않는다**(B1). 걸침(다른 층 선언)도 같은 기준으로 그 층 config에
    물어본다.
    """
    from core.state.bootstrap import load_config
    try:
        cfg = load_config(layer)
    except Exception:
        return False
    sc = cfg.get("canonical_scope") or {}
    return category in (sc.get("bind_categories") or [])


def h_attribute(value, spec, ctx):
    """**attribute — 속성값.** 노드를 만들지 않고 필드에 저장한다.

    반환은 **값**이다(3형태의 둘째). 저장은 Pass 2가 하고 여기서는 값을 통과시킨다 —
    부착 대상이 아직 해소되지 않았을 수 있기 때문이다(2-pass의 이유 그대로).
    """
    return value


def h_content(value, spec, ctx):
    """**content — 서술.** 청크로 보존하고 노드에 describes로 잇는다.

    반환은 **값**이다. 청크 생성은 Pass 2가 한다 — 대상 해소가 먼저다.
    """
    return value


def h_meta(value, spec, ctx):
    """**meta — 관리 정보.** 출처 장부에만 남고 **그래프에 들어가지 않는다.**

    반환은 값이다 — edges가 `@좌표필드`가 아닌 meta 필드를 끝점으로 지목하면
    게이트가 그 값을 노드 id로 보지 못해 미해소로 떨어진다(정상 동작).
    """
    return value


HANDLERS = {"anchor": h_anchor, "entity": h_entity, "attribute": h_attribute,
            "content": h_content, "meta": h_meta}


def _n(s):
    from core.state.ids import norm
    return norm(s)
