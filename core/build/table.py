# -*- coding: utf-8 -*-
"""칸 3.2 — **정형(table) 구축**: 스키마가 관계를 정한다 · LLM 0 (문서 4 §4.3).

행마다 anchor → role → 속성 → 내용 → 엣지 순으로 지난다. 이 파일에 LLM 호출은
없다 — 표는 계약이 이미 말해 주는 문서이고, 모르는 것을 물을 자리가 없다.
"""
from __future__ import annotations

from core import matcher
from core.build import gate, loop
from core.build.build import Builder
from core.build.ledger import Ledger
from core.state import log, store
from core.state.status import is_live

_LOG = log.get(__name__)


# ---------------------------------------------------------------- 정형 (1c′)
class _Row:
    """레코드 하나의 작업 상태 — 단계 함수 6개가 공유하는 그릇.

    `build_table`이 156줄·분기 35짜리 한 덩어리였다(구조 진단 2026-08-27 · 2순위).
    단계별로 떼되 **행 안에서 쌓이는 것**(해소 결과·보류·드롭·외부 그래프)은 여기 한
    곳에 둔다 — 인자로 넘기면 단계 함수 서명이 열두 개짜리가 된다.
    """
    __slots__ = ("rec", "prov", "ref", "ref_g", "et", "ctx", "parent", "anchor_pol",
                 "resolved", "external", "attrs", "contents",
                 "defer", "dropped", "pending", "dropped_ents", "coord_case")

    def __init__(self, rec, doc_id=None):
        self.rec, self.prov = rec, loop._prov(rec, doc_id)
        self.ref = self.ref_g = self.et = self.parent = self.anchor_pol = None
        self.coord_case = "present"     # present · low_res · missing ([개정] B56-2)
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
    b.ledger = Ledger(env["doc_id"])          # 판정 대장 — 행마다 적는다 (B74 ②)
    fields = schema["fields"]
    doc_id = env["doc_id"]
    envelope_ctx = loop._context(env, env.get("source_path"), doc_id)

    for rec in env.get("records", []):
        r = _Row(rec, doc_id)
        loop._check_fields(rec, fields, r.prov, doc_id)
        _row_anchor(b, r, envelope_ctx, doc_id)
        _row_roles(b, r, fields, schema, graph, cfg, doc_id)
        _row_attributes(b, r, graph)
        _row_contents(b, r, doc_id)
        _row_edges(r, schema, fields, graph, cfg, doc_id)
        _row_fallback(b, r, schema, fields, graph, cfg, doc_id)
        loop._land_deferred(r.defer, r.dropped, r.pending, doc_id,
                       dropped_entities=r.dropped_ents,
                       coord_missing=(r.coord_case == "missing"), prov=r.prov)

    b.flush()
    b.ledger.save()
    return b


def _row_anchor(b, r, envelope_ctx, doc_id):
    """⓪ 좌표·문맥 — 부착은 process_ref 하나. process_group은 조상 대조만.

    **값 부재의 처분은 사다리 셋이다**([개정] B56-2):

    | 경우 | 처분 |
    |---|---|
    | `process_ref` 있음 | 종전 그대로 (해소 실패면 `orphan_anchor`) |
    | `process_ref` null · `process_group` 있음 | **저해상도 부착** — 그룹으로 해소하고 **큐를 달지 않는다** |
    | 둘 다 null | `missing_field` + 드롭·보류 재료 동봉 |

    **검사의 자리가 여기인 이유**: 필드 검증 루프에 두면 `process_ref`가 구조 필드인
    것(§2.5 규약 3)과 부딪혀, 조각이 계약대로 달고 온 필드가 `unknown_field`로
    쏟아진다. `STRUCTURAL`을 건드려 푸는 문제가 아니다.

    저해상도에 큐를 달지 않는 이유: 그룹으로라도 붙었으면 **그 지식은 그래프에 있다.**
    큐는 사람이 처리할 것을 담는 자리이고, 여기서 사람이 할 일은 없다 —
    해상도가 낮다는 사실은 붙은 노드가 개념 노드라는 것으로 이미 드러난다.
    """
    rec = r.rec
    _ref_s, _grp_s = rec.get("process_ref"), rec.get("process_group")
    r.ref, r.ref_g = b.resolve_anchor(_ref_s, loop.COORD_CATEGORY, r.prov,
                                      defer=r.defer)
    if not _ref_s:
        if _grp_s:
            # **저해상도 부착** — 그룹은 조상 대조용이지만, 좌표가 아예 없으면
            # 그것이 이 행이 가진 유일한 좌표다. 붙이되 큐는 달지 않는다.
            r.ref, r.ref_g = b.resolve_anchor(_grp_s, loop.COORD_CATEGORY, r.prov,
                                              defer=r.defer)
            r.coord_case = "low_res" if r.ref else "missing"
        else:
            r.coord_case = "missing"
    r.et = rec.get("electrode_type")                # ④ 구조 필드 — 직접 읽는다
    r.ref = b.descend_anchor(r.ref, r.et, r.ref_g)  # ⓪ 하강 부착 (A11-9 ⓪)
    b.check_coord(rec.get("process_group"), r.ref, r.prov, r.ref_g)
    r.ctx = dict(envelope_ctx)
    r.ctx.update(loop._context(rec, r.prov, doc_id))     # 봉투 → 레코드 상속·덮어쓰기
    r.parent = r.ref_g.get(r.ref)["canonical"] if r.ref else None
    # 부착 정합 2규칙 (A11-9): ①주소에 극성이 있으면 표면형 결합 생략
    # ②record와 좌표의 극성이 둘 다 확정인데 다르면 coord_mismatch
    r.anchor_pol = b.anchor_polarity(r.ref, r.ref_g)
    b.check_polarity(r.ref, r.et, r.prov, r.ref_g)
    # **대장의 anchor 행** — 이 행이 어느 좌표에 섰는지가 뒤의 전부를 가른다(B74 ②).
    if b.ledger is not None:
        b.ledger.add(locator=rec.get("source_locator"),
                     field="process_group" if r.coord_case == "low_res"
                     else "process_ref", role="anchor",
                     surface=_grp_s if r.coord_case == "low_res" else _ref_s,
                     canonical=r.parent, layer=r.ref_g.layer if r.ref_g else None,
                     path="skeleton" if r.ref else "none",
                     verdict=("lowres" if r.coord_case == "low_res"
                              else "anchor" if r.ref else "orphan"),
                     node_id=r.ref,
                     queue_kind=None if r.ref else "orphan_anchor")


def _row_roles(b, r, fields, schema, graph, cfg, doc_id):
    """① **role만이 분기 스위치다** — 코드에 필드명이 등장하지 않는다 (문서 2 §2.7)."""
    rec = r.rec
    state = {"b": b, "graph": graph, "cfg": cfg, "prov": r.prov, "ref": r.ref,
             "locator": rec.get("source_locator"),
             "dropped_entities": r.dropped_ents,
             "ref_g": r.ref_g, "parent": r.parent, "et": r.et,
             "anchor_pol": r.anchor_pol, "external": r.external,
             "defer": r.defer, "field": None}
    hctx = loop.Ctx(graphs=b.graphs(), dic=b.dict, buffer=b.buffer, queue=store,
               record=rec, schema=schema, state=state)
    for f, spec in fields.items():
        if f not in rec or rec[f] in (None, ""):
            continue
        role = spec.get("role")
        # **attribute는 이 방어의 대상이 아니다**(문서 2 §2.7 · §2.4-③) —
        # 구조체·배열을 통째로 하나의 값으로 저장한다. 이 방어가 막는 것은
        # 리스트가 표면형 정규화(문자열 강제·포함 규칙)를 타고 기존 노드에
        # 흡수되는 **사전 오염**인데, attribute 값은 사전을 타지 않는다.
        if role in ("entity", "anchor") and not loop._scalar(rec[f], f, r.prov, doc_id):
            continue
        if role not in loop.HANDLERS:
            # D-30 — 알 수 없는 role에 KeyError로 죽지 않는다.
            store.append_defect(                    # 큐가 아니라 로그다 (D-30)
                f"{doc_id}: invalid_role '{role}' @ 필드 '{f}'")
            continue
        state["field"] = f
        r.resolved[f] = loop.HANDLERS[role](rec[f], spec, hctx)   # 반환 3형태 (문서 2 §2.7)
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
            _ledger_attach(b, r, f, "attribute", None, "pending")
            continue
        tg = r.external.get(af, graph)
        # 같은 캐시의 빌더를 쓴다 — 새로 만들면 그 그래프는 저장되지 않는다(D3).
        ab = b if tg is graph else next(s for s in b.subs.values() if s.g is tg)
        ab.put_attribute(tgt, spec.get("attr_name", f), rec[f], r.ctx, r.prov,
                         bool(spec.get("contextual")))
        _ledger_attach(b, r, f, "attribute", tgt, "attached", layer=ab.layer)


def _row_contents(b, r, doc_id):
    """content — describes 연결, 필드별 청크(D8)."""
    rec = r.rec
    for f, spec in r.contents:
        af2 = spec.get("attach_to_field")
        tgt = r.resolved.get(af2)
        if tgt is not None:
            _describe(doc_id, rec, f, tgt)
            _ledger_attach(b, r, f, "content", tgt, "attached")
        elif af2 and rec.get(af2) not in (None, ""):
            _ledger_attach(b, r, f, "content", None, "pending")
            # 값은 있는데 대상이 미해소다 — 청크는 이미 보존돼 있고(링킹 0건
            # 청크도 남긴다) 연결만 못 한 것이므로 결함 로그로 드러낸다.
            # 빈 셀이면 기록하지 않는다 — 그 행에 대상이 없는 것이 정상이다(B12).
            store.append_defect(
                f"{doc_id}: content 부착 대상 미해소 — "
                f"'{f}' → '{af2}'={rec.get(af2)!r} @ {r.prov}")


def _ledger_attach(b, r, field, role, target, verdict, layer=None):
    """부착 시도 한 건의 대장 행 — **붙었나 보류인가**가 이 표의 종류 열이다(B74 ②).

    부착에는 판정이 없다(대상은 같은 행이 이미 해소한 노드다) — 그래서 `path`는
    `none`이고 LLM도 0이다. 그래도 행을 남기는 이유: 사람이 문서를 옆에 놓고 볼 때
    「이 열의 값이 어디에 갔나」가 행 단위로 답해져야 한다.
    """
    if b is None or b.ledger is None:
        return
    g = b.g
    n = (g.get(target) or {}) if target else {}
    b.ledger.add(locator=r.rec.get("source_locator"), field=field, role=role,
                 surface=None, canonical=n.get("canonical"),
                 layer=layer or (n.get("layer") if n else None),
                 path="none", verdict=verdict, node_id=target)


def _row_edges(r, schema, fields, graph, cfg, doc_id):
    """② 경로 — 스키마 edges 선언. 게이트는 여기에 무비용이다."""
    rec = r.rec
    for e in schema.get("edges", []):
        src, sg = _endpoint(e["from"], r.resolved, r.ref, r.ref_g, r.external, graph,
                            doc_id)
        dst, dg = _endpoint(e["to"], r.resolved, r.ref, r.ref_g, r.external, graph,
                            doc_id)
        if e.get("optional") and loop._blank_endpoint(e, rec, fields):
            continue        # **빈 행의 optional 엣지는 조용히 생략**(문서 2 §2.4-⑥)
        if src is None or dst is None:
            # 미해소 끝점 — 생략된 엣지의 **출발 노드를 큐 손잡이에 싣는다**
            # (문서 2 §2.4-① · 문서 4 §4.4). 게이트의 unresolved_endpoint는
            # 거부 **기록**이지 재시도 손잡이가 아니다 — 로그와 큐는 다른 자리다.
            r.dropped.append({"relation": e["relation"], "from": e["from"],
                              "to": e["to"],
                              "src": src, "dst": dst,
                              "src_surface": loop._field_surface(e["from"], rec),
                              "dst_surface": loop._field_surface(e["to"], rec)})
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
        loop._fallback_attach(b, cfg, tg, nid, r.ref, r.ref_g, r.prov, doc_id)


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
