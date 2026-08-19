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
from . import gate, store
from .build import Builder
from .bootstrap import load_config, open_graph
from .ingest import ingest, load_schema

STRUCTURAL = {"process_group", "process_ref", "process_no", "electrode_type",
              "source_locator", "section", "context"}

# 공정좌표 anchor의 목표 카테고리 — 공용 블록(schemas/blocks.json)이 소유한다.
COORD_CATEGORY = json.loads(
    (Path(__file__).resolve().parent.parent / "schemas" / "blocks.json")
    .read_text(encoding="utf-8"))["process_coord"]["process_ref"]["target_category"]


def _prov(rec):
    return rec.get("source_locator")


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


# ---------------------------------------------------------------- 정형 (1c′)
def build_table(env, cfg, schema, graph):
    b = Builder(graph, cfg, schema, env["doc_id"], cfg["layer"])
    fields = schema["fields"]
    envelope_ctx = _context(env, env.get("source_path"), env["doc_id"])

    for rec in env.get("records", []):
        prov = _prov(rec)
        # ③ 좌표: 부착은 process_ref 하나. process_group은 조상 대조만.
        ref, ref_g = b.resolve_anchor(rec.get("process_ref"), COORD_CATEGORY, prov)
        b.check_coord(rec.get("process_group"), ref, prov, ref_g)
        ctx = dict(envelope_ctx)
        ctx.update(_context(rec, prov, env["doc_id"]))  # 봉투 → 레코드 상속·덮어쓰기
        parent = ref_g.get(ref)["canonical"] if ref else None
        et = rec.get("electrode_type")                  # ④ 구조 필드 — 직접 읽는다
        # 부착 정합 2규칙 (A11-9): ①주소에 극성이 있으면 표면형 결합 생략
        # ②record와 좌표의 극성이 둘 다 확정인데 다르면 coord_mismatch
        anchor_pol = b.anchor_polarity(ref, ref_g)
        b.check_polarity(ref, et, prov, ref_g)

        resolved, attrs, contents, external = {}, [], [], {}
        for f, spec in fields.items():
            if f not in rec or rec[f] in (None, ""):
                continue
            role = spec.get("role")
            if role not in ("anchor", "entity", "attribute", "content", "meta"):
                # D-30 — 알 수 없는 role에 KeyError로 죽지 않는다.
                store.append_defect(
                    f"{env['doc_id']}: invalid_role '{role}' @ 필드 '{f}'")
                store.enqueue("invalid_role", f"스키마에 없는 role '{role}'",
                              env["doc_id"], {"field": f, "role": role})
                continue
            if role == "anchor":
                nid, ng = b.resolve_anchor(rec[f], spec["target_category"], prov)
                resolved[f] = nid
                if nid is not None and ng is not graph:
                    external[f] = ng
            elif role == "entity":
                resolved[f] = b.resolve_entity(
                    rec[f], spec["category"], prov,
                    electrode_type=et, parent_canonical=parent,
                    anchor_polarity=anchor_pol)
            elif role == "attribute":
                attrs.append((f, spec))
            elif role == "content":
                contents.append((f, spec))

        for f, spec in attrs:
            tgt = resolved.get(spec.get("attach_to_field"))
            if tgt is None:
                continue
            tg = external.get(spec.get("attach_to_field"), graph)
            Builder(tg, cfg, schema, env["doc_id"], cfg["layer"]).put_attribute(
                tgt, spec.get("attr_name", f), rec[f], ctx, prov,
                bool(spec.get("contextual")))
        for f, spec in contents:                        # describes — 필드별 청크(D8)
            tgt = resolved.get(spec.get("attach_to_field"))
            if tgt is not None:
                _describe(env["doc_id"], rec, f, tgt)

        # ② 경로 — 스키마 edges 선언. 게이트는 여기에 무비용이다.
        for e in schema.get("edges", []):
            src, _sg = _endpoint(e["from"], resolved, ref, ref_g, external, graph,
                                 env["doc_id"])
            dst, dg = _endpoint(e["to"], resolved, ref, ref_g, external, graph,
                                env["doc_id"])
            if src and dst:
                gate.commit_edge(graph, src, e["relation"], dst, cfg,
                                 gate.PATH_SCHEMA, [prov], env["doc_id"],
                                 dst_graph=dg)

    b.link_mirrors()
    b.flush()
    return b


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
                c["linked"] = True
            break
    store.write(store.CHUNKS, ch)


# ---------------------------------------------------------------- 비정형 (1d′)
def build_prose(env, cfg, graph, candidates):
    b = Builder(graph, cfg, None, env["doc_id"], cfg["layer"])
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    by_locator = {c["source_locator"]: c for c in env.get("chunks", [])}
    loc_of = {cid: c.get("source_locator") for cid, c in ch["chunks"].items()
              if c.get("doc_id") == env["doc_id"]}

    for cand in candidates:
        cid = cand["chunk_id"]
        src = by_locator.get(loc_of.get(cid), {})
        prov = src.get("source_locator") or cid
        ref, ref_g = b.resolve_anchor(src.get("process_ref"), COORD_CATEGORY, prov)
        parent = ref_g.get(ref)["canonical"] if ref else None
        anchor_pol = b.anchor_polarity(ref, ref_g)      # A11-9 ① — 비정형도 동일
        b.check_polarity(ref, src.get("electrode_type"), prov, ref_g)

        for e in cand.get("entities", []):
            nid = b.resolve_entity(e["surface"], e["category"], prov,
                                   electrode_type=src.get("electrode_type"),
                                   parent_canonical=parent,
                                   anchor_polarity=anchor_pol)
            if {"chunk_id": cid, "node_id": nid} not in ch["describes"]:
                ch["describes"].append({"chunk_id": cid, "node_id": nid})
                ch["chunks"][cid]["linked"] = True

        # ③ 경로 — 추출 후보. 게이트의 실질 관문이다.
        for r in cand.get("relations", []):
            s = b.buffer.get(_n(r["src"]))
            d = b.buffer.get(_n(r["dst"]))
            if s and d:
                gate.commit_edge(graph, s, r["rel"], d, cfg, gate.PATH_EXTRACT,
                                 [prov], env["doc_id"], evidence_chunk=cid)

        # attach — ③의 폴백. 해소 범위는 **문서 버퍼 전체 + 사전**이며 청크 경계가 없다.
        for a in cand.get("attach", []):
            child = b.buffer.get(_n(a["surface"]))
            target = b.buffer.get(_n(a["attach_to"])) or _dict_hit(b, a["attach_to"])
            if child is None:
                continue
            if target is None:
                store.enqueue("orphan_attach", f"부착 대상 미해소 — '{a['attach_to']}'",
                              env["doc_id"], {"surface": a["surface"],
                                              "attach_to": a["attach_to"]})
                continue
            rel = _pair_relation(cfg, graph.get(target)["category"],
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


def _dict_hit(b, surface):
    hits = b.dict.get(_n(surface), [])
    return hits[0] if hits else None


def _pair_relation(cfg, src_cat, dst_cat):
    """관계는 category_pair_map이 결정한다 — 게이트 패턴표의 특수형(§6-3)."""
    return (cfg.get("category_pair_map") or {}).get(f"{src_cat},{dst_cat}")


# ---------------------------------------------------------------- 진입점
def run_document(path_or_env, layer=None):
    env = path_or_env
    doc_type = env["doc_type"]
    schema = load_schema(doc_type)
    layer = layer or (schema or {}).get("layer") or "process"
    cfg = load_config(layer)

    res = ingest(env)                                    # ① doc_hash → ② 근거 축 id
    if res.status == "held":
        return res, None, False

    graph = open_graph(layer)
    graph.build_begin()

    extracted = False
    if env.get("payload_kind") == "table":
        build_table(env, cfg, schema, graph)
    else:
        ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        loc2id = {c["source_locator"]: cid for cid, c in ch.items()
                  if c.get("doc_id") == env["doc_id"]}
        vocab = _vocab(cfg)
        ck, extracted = extract_mod.extract(env, cfg, loc2id, vocab)
        build_prose(env, cfg, graph, ck["candidates"])

    metrics = graph.build_end()
    return res, metrics, extracted


def _vocab(cfg):
    """USE_MOCK 문형 폴백이 쓸 표면형→카테고리 표. 층 config에서만 나온다."""
    v = {}
    for nid, ids in store.read(store.DICTIONARY, {}).items():
        v.setdefault(nid, None)
    from .ids import norm
    g = open_graph(cfg["layer"])
    for n in g.nodes.values():
        v[norm(n["canonical"])] = n["category"]
        for a in n["aliases"]:
            v[norm(a["surface"])] = n["category"]
    return {k: c for k, c in v.items() if c}
