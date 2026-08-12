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


# ---------------------------------------------------------------- 정형 (1c′)
def build_table(env, cfg, schema, graph):
    b = Builder(graph, cfg, schema, env["doc_id"], cfg["layer"])
    fields = schema["fields"]
    envelope_ctx = env.get("context", {})

    for rec in env.get("records", []):
        prov = _prov(rec)
        # ③ 좌표: 부착은 process_ref 하나. process_group은 조상 대조만.
        ref, ref_g = b.resolve_anchor(rec.get("process_ref"), COORD_CATEGORY, prov)
        b.check_coord(rec.get("process_group"), ref, prov, ref_g)
        ctx = dict(envelope_ctx)
        ctx.update(rec.get("context") or {})            # 봉투 → 레코드 상속·덮어쓰기
        parent = ref_g.get(ref)["canonical"] if ref else None
        et = rec.get("electrode_type")                  # ④ 구조 필드 — 직접 읽는다

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
                    electrode_type=et, parent_canonical=parent)
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
            src = resolved.get(e["from"])
            if e["to"] == "@process_ref":
                dst, dg = ref, ref_g
            else:
                dst, dg = resolved.get(e["to"]), external.get(e["to"], graph)
            if src and dst:
                gate.commit_edge(graph, src, e["relation"], dst, cfg,
                                 gate.PATH_SCHEMA, [prov], env["doc_id"],
                                 dst_graph=dg)

    b.link_mirrors()
    b.flush()
    return b


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

        for e in cand.get("entities", []):
            nid = b.resolve_entity(e["surface"], e["category"], prov,
                                   electrode_type=src.get("electrode_type"),
                                   parent_canonical=parent)
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
