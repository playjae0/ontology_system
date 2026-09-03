# -*- coding: utf-8 -*-
"""파이프라인 구동 — 파싱 → **추출** → 구축의 3단 (틀 Q1, 카드 M7).

추출이 독립 단계인 이유: 구축 안에 섞여 있으면 "무엇이 언급됐나"와
"그것이 기존의 무엇인가"가 한 호출에 뭉쳐 재현도 검증도 안 된다.
분리하면 체크포인트가 생기고, 재실행이 추출을 다시 부르지 않는다(P-1).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import extract as extract_mod
from . import gate, log, matcher, store
from .build import Builder
from .bootstrap import load_config, open_graph
from .ingest import IngestResult, ingest, load_schema
from .status import is_live
from .retry import retry_orphans

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
    (Path(__file__).resolve().parent.parent / "schemas" / "blocks.json")
    .read_text(encoding="utf-8"))["process_coord"]["process_ref"]["target_category"]


def _prov(rec):
    return rec.get("source_locator")


def _check_fields(rec, fields, prov, doc_id):
    """③ 필드 검증 (CH2 2.8) — 계약 위반은 조용히 통과하지 않는다.

    스키마 밖 필드는 **값을 동봉해** `unknown_field` 큐로 간다(레코드는 어디에도
    저장되지 않으므로, 여기서 안 실으면 그 값은 영구 소실이다 — 카드 G5).
    `optional` 미선언 필드의 부재는 `missing_field` 큐다. 둘 다 닫힌 20종 안이고
    **문서를 죽이지 않는다** — 문서 단위 실패는 파서 측 계약이다(C14).
    """
    for f, v in rec.items():
        if f in fields or f in STRUCTURAL:
            continue
        store.enqueue("unknown_field", f"스키마에 없는 필드 '{f}'", doc_id,
                      {"field": f, "value": v, "provenance": prov})
    for f, spec in fields.items():
        if spec.get("optional") or f in STRUCTURAL:
            continue
        if rec.get(f) in (None, ""):
            store.enqueue("missing_field", f"필수 필드 '{f}' 부재", doc_id,
                          {"field": f, "provenance": prov})


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


def _land_deferred(defer, dropped, pending, doc_id, *, dropped_entities=None):
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
        store.enqueue("orphan_anchor", item["reason"], doc_id, pl)
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
        return None

    eb = st["b"].for_layer(lay)
    nid = eb.resolve_entity(value, spec["category"], st["prov"],
                            electrode_type=st["et"],
                            parent_canonical=st["parent"],
                            anchor_polarity=st["anchor_pol"])
    if eb is not st["b"]:
        st["external"][st["field"]] = eb.g
    if nid is not None:
        ctx.buffer[_n(value)] = nid          # 층으로 나누지 않는다 (문서 4 §4.2)
    return nid


def _scoped_category(category, layer, builder):
    """이 카테고리는 **좌표가 canonical에 들어가는가** (문서 4 §4.4 — B14의 기준).

    판정은 층 config의 `canonical_scope.bind_categories`가 한다 — **코드가 카테고리
    이름을 알지 않는다**(B1). 걸침(다른 층 선언)도 같은 기준으로 그 층 config에
    물어본다.
    """
    from .bootstrap import load_config
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


# ---------------------------------------------------------------- 정형 (1c′)
class _Row:
    """레코드 하나의 작업 상태 — 단계 함수 6개가 공유하는 그릇.

    `build_table`이 156줄·분기 35짜리 한 덩어리였다(구조 진단 2026-08-27 · 2순위).
    단계별로 떼되 **행 안에서 쌓이는 것**(해소 결과·보류·드롭·외부 그래프)은 여기 한
    곳에 둔다 — 인자로 넘기면 단계 함수 서명이 열두 개짜리가 된다.
    """
    __slots__ = ("rec", "prov", "ref", "ref_g", "et", "ctx", "parent", "anchor_pol",
                 "resolved", "external", "attrs", "contents",
                 "defer", "dropped", "pending", "dropped_ents")

    def __init__(self, rec):
        self.rec, self.prov = rec, _prov(rec)
        self.ref = self.ref_g = self.et = self.parent = self.anchor_pol = None
        self.ctx = {}
        self.resolved, self.external = {}, {}
        self.attrs, self.contents = [], []
        # **적재를 레코드 말미로 미루는 그릇 셋** (문서 2 §2.4-①·③ · 문서 4 §4.7-5).
        # 큐 항목이 재시도의 유일한 손잡이라, 그 행이 무엇을 만들었는지가 정해진
        # 뒤에 실어야 한다.
        self.defer, self.dropped, self.pending = [], [], []
        # **연쇄 드롭된 entity의 재료** — 좌표가 미해소라 만들지 않은 것들.
        # 큐 항목이 이것을 보유해야 재시도가 노드를 새로 세울 수 있다(§4.4).
        self.dropped_ents = []


def build_table(env, cfg, schema, graph):
    """정형 인입 — 레코드마다 ⓪좌표 → ①role 분기 → attribute → content → ②edges →
    규칙 B 폴백 → 말미 적재. 단계의 순서가 계약이다(문서 2 §2.4 · 문서 4 §4.4)."""
    b = Builder(graph, cfg, schema, env["doc_id"], cfg["layer"])
    fields = schema["fields"]
    doc_id = env["doc_id"]
    envelope_ctx = _context(env, env.get("source_path"), doc_id)

    for rec in env.get("records", []):
        r = _Row(rec)
        _check_fields(rec, fields, r.prov, doc_id)
        _row_anchor(b, r, envelope_ctx, doc_id)
        _row_roles(b, r, fields, schema, graph, cfg, doc_id)
        _row_attributes(b, r, graph)
        _row_contents(r, doc_id)
        _row_edges(r, schema, fields, graph, cfg, doc_id)
        _row_fallback(b, r, schema, fields, graph, cfg, doc_id)
        _land_deferred(r.defer, r.dropped, r.pending, doc_id,
                       dropped_entities=r.dropped_ents)

    b.flush()
    return b


def _row_anchor(b, r, envelope_ctx, doc_id):
    """⓪ 좌표·문맥 — 부착은 process_ref 하나. process_group은 조상 대조만."""
    rec = r.rec
    r.ref, r.ref_g = b.resolve_anchor(rec.get("process_ref"), COORD_CATEGORY, r.prov,
                                      defer=r.defer)
    r.et = rec.get("electrode_type")                # ④ 구조 필드 — 직접 읽는다
    r.ref = b.descend_anchor(r.ref, r.et, r.ref_g)  # ⓪ 하강 부착 (A11-9 ⓪)
    b.check_coord(rec.get("process_group"), r.ref, r.prov, r.ref_g)
    r.ctx = dict(envelope_ctx)
    r.ctx.update(_context(rec, r.prov, doc_id))     # 봉투 → 레코드 상속·덮어쓰기
    r.parent = r.ref_g.get(r.ref)["canonical"] if r.ref else None
    # 부착 정합 2규칙 (A11-9): ①주소에 극성이 있으면 표면형 결합 생략
    # ②record와 좌표의 극성이 둘 다 확정인데 다르면 coord_mismatch
    r.anchor_pol = b.anchor_polarity(r.ref, r.ref_g)
    b.check_polarity(r.ref, r.et, r.prov, r.ref_g)


def _row_roles(b, r, fields, schema, graph, cfg, doc_id):
    """① **role만이 분기 스위치다** — 코드에 필드명이 등장하지 않는다 (문서 2 §2.7)."""
    rec = r.rec
    state = {"b": b, "graph": graph, "cfg": cfg, "prov": r.prov, "ref": r.ref,
             "dropped_entities": r.dropped_ents,
             "ref_g": r.ref_g, "parent": r.parent, "et": r.et,
             "anchor_pol": r.anchor_pol, "external": r.external,
             "defer": r.defer, "field": None}
    hctx = Ctx(graphs=b.graphs(), dic=b.dict, buffer=b.buffer, queue=store,
               record=rec, schema=schema, state=state)
    for f, spec in fields.items():
        if f not in rec or rec[f] in (None, ""):
            continue
        role = spec.get("role")
        # **attribute는 이 방어의 대상이 아니다**(문서 2 §2.7 · §2.4-③) —
        # 구조체·배열을 통째로 하나의 값으로 저장한다. 이 방어가 막는 것은
        # 리스트가 표면형 정규화(문자열 강제·포함 규칙)를 타고 기존 노드에
        # 흡수되는 **사전 오염**인데, attribute 값은 사전을 타지 않는다.
        if role in ("entity", "anchor") and not _scalar(rec[f], f, r.prov, doc_id):
            continue
        if role not in HANDLERS:
            # D-30 — 알 수 없는 role에 KeyError로 죽지 않는다.
            store.append_defect(                    # 큐가 아니라 로그다 (D-30)
                f"{doc_id}: invalid_role '{role}' @ 필드 '{f}'")
            continue
        state["field"] = f
        r.resolved[f] = HANDLERS[role](rec[f], spec, hctx)   # 반환 3형태 (문서 2 §2.7)
        if role == "attribute":
            r.attrs.append((f, spec))
        elif role == "content":
            r.contents.append((f, spec))


def _row_attributes(b, r, graph):
    """attribute 부착 — **「미해소」와 「값 없음」을 가른다**(문서 4 §4.4-4 — B12).

    `attach_to_field`가 가리키는 필드가 그 행에서 **빈 셀이면 아무것도 하지 않는다** —
    붙일 대상 자체가 그 행에 없으므로 attribute가 성립하지 않는다. 없는 값을
    저해상도로 만들어 붙이면 **문서에 없던 사실이 그래프에 생긴다**.

    **값은 있는데 해소에 실패한 경우만** 보류한다 — 그때는 좌표가 나중에 해소되면
    붙어야 할 값이고, 조용히 버리면 그 기회가 사라진다(문서 2 §2.4-③ `pending_attrs`).
    """
    rec = r.rec
    for f, spec in r.attrs:
        af = spec.get("attach_to_field")
        tgt = r.resolved.get(af)
        if tgt is None:
            if af and rec.get(af) in (None, ""):
                continue                    # 값 없음 — 폴백도 보류도 하지 않는다
            r.pending.append({"attr_name": spec.get("attr_name", f),
                              "value": rec[f],
                              "context": r.ctx or None,
                              "provenance": r.prov,
                              "attach_to_field": af})
            continue
        tg = r.external.get(af, graph)
        # 같은 캐시의 빌더를 쓴다 — 새로 만들면 그 그래프는 저장되지 않는다(D3).
        ab = b if tg is graph else next(s for s in b.subs.values() if s.g is tg)
        ab.put_attribute(tgt, spec.get("attr_name", f), rec[f], r.ctx, r.prov,
                         bool(spec.get("contextual")))


def _row_contents(r, doc_id):
    """content — describes 연결, 필드별 청크(D8)."""
    rec = r.rec
    for f, spec in r.contents:
        af2 = spec.get("attach_to_field")
        tgt = r.resolved.get(af2)
        if tgt is not None:
            _describe(doc_id, rec, f, tgt)
        elif af2 and rec.get(af2) not in (None, ""):
            # 값은 있는데 대상이 미해소다 — 청크는 이미 보존돼 있고(링킹 0건
            # 청크도 남긴다) 연결만 못 한 것이므로 결함 로그로 드러낸다.
            # 빈 셀이면 기록하지 않는다 — 그 행에 대상이 없는 것이 정상이다(B12).
            store.append_defect(
                f"{doc_id}: content 부착 대상 미해소 — "
                f"'{f}' → '{af2}'={rec.get(af2)!r} @ {r.prov}")


def _row_edges(r, schema, fields, graph, cfg, doc_id):
    """② 경로 — 스키마 edges 선언. 게이트는 여기에 무비용이다."""
    rec = r.rec
    for e in schema.get("edges", []):
        src, sg = _endpoint(e["from"], r.resolved, r.ref, r.ref_g, r.external, graph,
                            doc_id)
        dst, dg = _endpoint(e["to"], r.resolved, r.ref, r.ref_g, r.external, graph,
                            doc_id)
        if e.get("optional") and _blank_endpoint(e, rec, fields):
            continue        # **빈 행의 optional 엣지는 조용히 생략**(문서 2 §2.4-⑥)
        if src is None or dst is None:
            # 미해소 끝점 — 생략된 엣지의 **출발 노드를 큐 손잡이에 싣는다**
            # (문서 2 §2.4-① · 문서 4 §4.4). 게이트의 unresolved_endpoint는
            # 거부 **기록**이지 재시도 손잡이가 아니다 — 로그와 큐는 다른 자리다.
            r.dropped.append({"relation": e["relation"], "from": e["from"],
                              "to": e["to"],
                              "src": src, "dst": dst,
                              "src_surface": _field_surface(e["from"], rec),
                              "dst_surface": _field_surface(e["to"], rec)})
        # 끝점 미해소도 게이트에 넘긴다 — 판정 전에 무음으로 사라지면 안 된다(D2).
        gate.commit_edge(graph, src, e["relation"], dst, cfg,
                         gate.PATH_SCHEMA, [r.prov], doc_id,
                         src_graph=sg, dst_graph=dg)


def _row_fallback(b, r, schema, fields, graph, cfg, doc_id):
    """**규칙 B 폴백 — 정형 경로**(문서 4 §4.4-4). 이 레코드가 만든 entity 중
    **어느 엣지에도 끝점으로 서지 못한 것**을 좌표에 저해상도로 붙인다.
    §2.4-②의 "attach 대상이 **없거나** 미해소면" 중 "없다"는 그 entity를
    아무 경로도 붙이지 않은 경우다. **빈 셀은 그 갈래가 아니다**(B12)."""
    if r.ref is None:
        return
    rec = r.rec
    touched = set()
    for e in schema.get("edges", []):
        for side in ("from", "to"):
            nid = r.resolved.get(e.get(side))
            if nid:
                touched.add(nid)
    for f, spec in fields.items():
        if spec.get("role") != "entity":
            continue
        nid = r.resolved.get(f)
        if nid is None or nid in touched:
            continue
        # **B12 — 빈 셀은 폴백 대상이 아니다.** 이 entity가 `attach_to_field`를
        # 선언했는데 그 필드가 이 행에서 비어 있으면, 붙을 대상이 그 행에
        # 없는 것이지 해소에 실패한 것이 아니다(문서 4 §4.4-4).
        af3 = spec.get("attach_to_field")
        if af3 and rec.get(af3) in (None, ""):
            continue
        tg = r.external.get(f, graph)
        _fallback_attach(b, cfg, tg, nid, r.ref, r.ref_g, r.prov, doc_id)


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


def _endpoint(name, resolved, ref, ref_g, external, graph, doc_id):
    """엣지 끝점 해소 — `@` 접두는 **필드가 아니라 이 레코드의 공정좌표**를 가리킨다.

    `@`는 `from`·`to` 어느 쪽에도 올 수 있다(하네스의 참조 무결성 검사도 양쪽을 같게
    본다). 한쪽만 구현하면 **스키마가 선언한 엣지가 조용히 사라진다** — A-4 관통
    실측: ipqc의 `@process_ref has_property 검사항목`이 0건 적재됐다. 조용한 누락은
    큐도 로그도 남기지 않아 아무도 모른다.

    좌표 중 부착 대상은 `process_ref` 하나다(③ — process_group은 조상 대조만 한다).
    그 밖의 `@` 표기는 해소하지 않되 **결함 로그로 드러낸다.**
    """
    if not str(name).startswith("@"):
        return resolved.get(name), external.get(name, graph)
    if name == "@process_ref":
        return ref, ref_g
    store.append_defect(f"{doc_id}: 부착 대상이 아닌 좌표 표기 '{name}' @ edges 선언")
    return None, graph


def _describe(doc_id, rec, field, node_id):
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    for cid, c in ch["chunks"].items():
        if c.get("doc_id") == doc_id and c.get("meta", {}).get("field") == field \
                and c.get("source_locator") == rec.get("source_locator"):
            if {"chunk_id": cid, "node_id": node_id} not in ch["describes"]:
                ch["describes"].append({"chunk_id": cid, "node_id": node_id})
            c["linked"] = True          # 관측 상태 — 이미 걸려 있어도 참이다(A4)
            break
    store.write(store.CHUNKS, ch)


# ---------------------------------------------------------------- 비정형 (1d′)
def build_prose(env, cfg, graph, candidates):
    b = Builder(graph, cfg, None, env["doc_id"], cfg["layer"])
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    by_locator = {c["source_locator"]: c for c in env.get("chunks", [])}
    loc_of = {cid: c.get("source_locator") for cid, c in ch["chunks"].items()
              if c.get("doc_id") == env["doc_id"]}

    # ════════════════ Pass 1 (해소) ════════════════
    # **문서 전체의 anchor·entity를 먼저 전부 해소해 버퍼에 담는다**(문서 4 §4.2).
    # 부착은 해소가 끝난 뒤에만 시작한다 — 그래야 **문서 안에서 뒤에 나오는 개체를
    # 앞의 청크가 참조해도** 붙는다. 이 분리 덕에 부착 실패의 원인이 구분된다:
    # Pass 1에 없는 대상을 가리키면 진짜 미해소(큐로), 있는데 실패하면 구현 결함.
    #
    # 버퍼는 `정규화 표면형 → node_id` 맵이고 수명은 문서 하나이며 **층으로 나누지
    # 않는다**(걸침 하위 빌더가 같은 버퍼를 공유한다 — §4.2). 층 간 동명 표면형은
    # **마지막 해소가 이긴다** — 버퍼는 사전과 달리 후보 목록을 두지 않으므로,
    # 카테고리로 선별해야 하는 소비처는 사전을 함께 조회한다.
    coords = {}
    for cand in candidates:
        cid = cand["chunk_id"]
        src = by_locator.get(loc_of.get(cid), {})
        prov = src.get("source_locator") or cid
        ref, ref_g = b.resolve_anchor(src.get("process_ref"), COORD_CATEGORY, prov)
        ref = b.descend_anchor(ref, src.get("electrode_type"), ref_g)   # ⓪ 비정형도 동일
        parent = ref_g.get(ref)["canonical"] if ref else None
        anchor_pol = b.anchor_polarity(ref, ref_g)      # A11-9 ① — 비정형도 동일
        b.check_polarity(ref, src.get("electrode_type"), prov, ref_g)
        coords[cid] = (src, prov, ref, ref_g, parent, anchor_pol)

        for e in cand.get("entities", []):
            b.resolve_entity(e["surface"], e["category"], prov,
                             electrode_type=src.get("electrode_type"),
                             parent_canonical=parent,
                             anchor_polarity=anchor_pol)

    # ════════════════ Pass 2 (부착) ════════════════
    # **비정형의 순회 단위는 레코드가 아니라 청크(추출 후보)다**(문서 4 §4.2).
    # 그 청크의 후보에서 **해소된 언급 전부**에 describes를 만든다 — 부착·엣지
    # 성립 여부와 무관하다. 청크의 `linked`는 그 결과의 재계산이다(§4.8-2①).
    for cand in candidates:
        cid = cand["chunk_id"]
        src, prov, ref, ref_g, parent, anchor_pol = coords[cid]

        for e in cand.get("entities", []):
            nid = b.buffer.get(_n(e["surface"]))
            if nid is None:
                continue                        # Pass 1이 못 세운 것 — 부착도 없다
            if {"chunk_id": cid, "node_id": nid} not in ch["describes"]:
                ch["describes"].append({"chunk_id": cid, "node_id": nid})
            ch["chunks"][cid]["linked"] = True          # 상동 — 재인입이 거짓으로 되돌리지 않는다

        # ③ 경로 — 추출 후보. 게이트의 실질 관문이다.
        for r in cand.get("relations", []):
            s = b.buffer.get(_n(r["src"]))
            d = b.buffer.get(_n(r["dst"]))
            if s and d:
                gate.commit_edge(graph, s, r["rel"], d, cfg, gate.PATH_EXTRACT,
                                 [prov], env["doc_id"], evidence_chunk=cid)
            else:                               # 게이트에 닿기도 전의 소멸 — 기록한다
                store.append_defect(
                    f"{env['doc_id']}: 관계 후보 끝점 미해소 — "
                    f"'{r['src']}' -{r['rel']}-> '{r['dst']}' @ {cid}")

        # attach — ③의 폴백. 해소 범위는 **문서 버퍼 전체 + 사전**이며 청크 경계가 없다.
        for a in cand.get("attach", []):
            child = b.buffer.get(_n(a["surface"]))
            name, cat = _attach_target(a)       # {name, category} (§4.10 규약 8 — B11)
            target = b.buffer.get(_n(name)) if name else None
            if target is None and name and cat:
                # **카테고리가 있으니 판정기가 그것 하나로 판정한다** — 전 카테고리를
                # 훑지 않으므로 선언 순서가 답을 정하는 일이 없다.
                target = _dict_hit(b, name, graph, category=cat)
            if child is None:                   # 자식 미해소도 대상 쪽과 대칭으로 기록
                store.append_defect(
                    f"{env['doc_id']}: attach 자식 미해소 — "
                    f"'{a['surface']}' → '{name}' @ {cid}")
                continue
            if target is None:
                # **규칙 B 폴백** — 좌표에 저해상도로 붙인다(문서 4 §4.4-4).
                # 비정형의 「미해소」는 `attach_to`가 null이거나 **카테고리를 못 고른**
                # 경우까지다(§4.4-4 — B11).
                _fallback_attach(b, cfg, graph, child, ref, ref_g, prov,
                                 env["doc_id"], evidence_chunk=cid)
                # **`attach_to`가 null이면 폴백만 하고 큐를 달지 않는다**(§4.7-5) —
                # null은 추출이 애초에 부착 대상을 말하지 않은 정상 케이스라,
                # 큐로 보내면 처리 불가능한 노이즈가 큐를 채운다.
                if name:
                    store.enqueue(
                        "orphan_attach", f"부착 대상 미해소 — '{name}'",
                        env["doc_id"],
                        {"node_id": child, "surface": a["surface"],
                         "attach_to": _n(name),            # dedup 키 (§4.7-5)
                         "attach_category": cat,
                         "provenance": prov, "chunk_id": cid})
                continue
            rel = gate.pair_relation(cfg, graph.get(target)["category"],
                                 graph.get(child)["category"])
            if rel:
                gate.commit_edge(graph, target, rel, child, cfg, gate.PATH_EXTRACT,
                                 [prov], env["doc_id"], evidence_chunk=cid)

    store.write(store.CHUNKS, ch)
    b.flush()
    return b


def _n(s):
    from .ids import norm
    return norm(s)


def _dict_hit(b, surface, graph, *, category):
    """attach 대상의 사전 해소 — **판정 파이프라인을 재사용한다**(문서 4 §4.4-3).

    **카테고리는 추출이 함께 낸다**(§4.10 규약 8 — B11). 그래서 여기는 그 카테고리
    하나로만 판정한다 — 전 카테고리를 훑지 않으므로 **선언 순서가 답을 정하는 일이
    없다**. 그것이 P-B의 임시 「수렴 판정」이 있던 자리이고, 추출 계약이 카테고리를
    내면서 순회도 수렴 판정도 필요 없어졌다.

    후보를 사전 히트로 **조립만** 하고 판정은 `matcher.match`가 한다 — 사전은 전 층
    단일이라(§7.1) 첫 히트를 조용히 고르면 그것이 판정을 대신하고, 카테고리 불일치
    안전망·극성 후보 제외·생존 판정이 적용되지 않은 선택이 엣지 끝점이 된다.
    """
    cands = []
    for nid in b.dict.lookup(surface):
        n = graph.get(nid)
        if not n or not is_live(n) or n["category"] != category:
            continue
        cands.append({"id": nid, "canonical": n["canonical"],
                      "aliases": [a["surface"] for a in n.get("aliases") or []],
                      "category": n["category"], "layer": n.get("layer"),
                      "polarity": n.get("polarity"), "exact": True})
    if not cands:
        return None
    v = matcher.match(surface, cands, category)
    return v["matched_id"] if v["type"] == matcher.MATCH else None


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


def run_document(path_or_env, layer=None, *, allow_duplicate=False, routing=None):
    env = path_or_env
    doc_id, doc_type = env["doc_id"], env["doc_type"]

    kind = env.get("payload_kind")
    if kind not in PAYLOAD_KINDS:                        # 닫힌 2값 (B2)
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

    extracted = False
    builder = None
    if kind == "table":
        builder = build_table(env, cfg, schema, graph)
    else:
        ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        loc2id = {c["source_locator"]: cid for cid, c in ch.items()
                  if c.get("doc_id") == env["doc_id"]}
        vocab = _vocab(cfg)
        ck, extracted = extract_mod.extract(env, cfg, loc2id, vocab)
        builder = build_prose(env, cfg, graph, ck["candidates"])

    for other in builder.graphs():          # 걸침 층에 쓴 것도 저장된다 (D3)
        if other is not graph:
            other.save()
    metrics = graph.build_end()
    return res, metrics, extracted


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
    from .ids import norm
    v = {}
    for n in skeleton_closed_list(cfg["layer"]):
        for s in [n["canonical"]] + list(n.get("aliases") or []):
            v[norm(s)] = n["category"]
    return {k: c for k, c in v.items() if k and c}
