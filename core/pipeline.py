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
from . import gate, matcher, store
from .build import Builder
from .bootstrap import load_config, open_graph
from .ingest import IngestResult, ingest, load_schema
from .ops import is_live

STRUCTURAL = {"process_group", "process_ref", "process_no", "electrode_type",
              "source_locator", "section", "context"}

# 봉투 `payload_kind`의 **닫힌 2값**(CH2 2.2). 밖의 값은 폴백 대상이 아니라 계약 위반이다.
PAYLOAD_KINDS = ("table", "prose")

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
    """role 핸들러는 **단일 값만 본다**는 전제를 코드가 방어한다 (카드 D6).

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


# ---------------------------------------------------------------- 정형 (1c′)
def build_table(env, cfg, schema, graph):
    b = Builder(graph, cfg, schema, env["doc_id"], cfg["layer"])
    fields = schema["fields"]
    envelope_ctx = _context(env, env.get("source_path"), env["doc_id"])

    for rec in env.get("records", []):
        prov = _prov(rec)
        _check_fields(rec, fields, prov, env["doc_id"])
        # ③ 좌표: 부착은 process_ref 하나. process_group은 조상 대조만.
        ref, ref_g = b.resolve_anchor(rec.get("process_ref"), COORD_CATEGORY, prov)
        et = rec.get("electrode_type")                  # ④ 구조 필드 — 직접 읽는다
        ref = b.descend_anchor(ref, et, ref_g)          # ⓪ 하강 부착 (A11-9 ⓪)
        b.check_coord(rec.get("process_group"), ref, prov, ref_g)
        ctx = dict(envelope_ctx)
        ctx.update(_context(rec, prov, env["doc_id"]))  # 봉투 → 레코드 상속·덮어쓰기
        parent = ref_g.get(ref)["canonical"] if ref else None
        # 부착 정합 2규칙 (A11-9): ①주소에 극성이 있으면 표면형 결합 생략
        # ②record와 좌표의 극성이 둘 다 확정인데 다르면 coord_mismatch
        anchor_pol = b.anchor_polarity(ref, ref_g)
        b.check_polarity(ref, et, prov, ref_g)

        resolved, attrs, contents, external = {}, [], [], {}
        for f, spec in fields.items():
            if f not in rec or rec[f] in (None, ""):
                continue
            role = spec.get("role")
            if role in ("entity", "attribute", "anchor") and \
                    not _scalar(rec[f], f, prov, env["doc_id"]):
                continue
            if role not in ("anchor", "entity", "attribute", "content", "meta"):
                # D-30 — 알 수 없는 role에 KeyError로 죽지 않는다.
                store.append_defect(                    # 큐가 아니라 로그다 (D-30)
                    f"{env['doc_id']}: invalid_role '{role}' @ 필드 '{f}'")
                continue
            if role == "anchor":
                nid, ng = b.resolve_anchor(rec[f], spec["target_category"], prov)
                resolved[f] = nid
                if nid is not None and ng is not graph:
                    external[f] = ng
            elif role == "entity":
                # **스키마가 층을 선언하면 그 층에 해소한다**(D1). 선언을 안 읽으면
                # 걸침 개체가 자기 층에 복제되어 CP↔PFMEA 병합이 조용히 깨진다
                # (실측: 관리항목 11종이 품질층에 중복 생성).
                eb = b.for_layer(spec.get("target_layer") or cfg["layer"])
                resolved[f] = eb.resolve_entity(
                    rec[f], spec["category"], prov,
                    electrode_type=et, parent_canonical=parent,
                    anchor_polarity=anchor_pol)
                if eb is not b:
                    external[f] = eb.g
            elif role == "attribute":
                attrs.append((f, spec))
            elif role == "content":
                contents.append((f, spec))

        for f, spec in attrs:
            tgt = resolved.get(spec.get("attach_to_field"))
            if tgt is None:
                continue
            tg = external.get(spec.get("attach_to_field"), graph)
            # 같은 캐시의 빌더를 쓴다 — 새로 만들면 그 그래프는 저장되지 않는다(D3).
            ab = b if tg is graph else next(s for s in b.subs.values() if s.g is tg)
            ab.put_attribute(tgt, spec.get("attr_name", f), rec[f], ctx, prov,
                             bool(spec.get("contextual")))
        for f, spec in contents:                        # describes — 필드별 청크(D8)
            tgt = resolved.get(spec.get("attach_to_field"))
            if tgt is not None:
                _describe(env["doc_id"], rec, f, tgt)

        # ② 경로 — 스키마 edges 선언. 게이트는 여기에 무비용이다.
        for e in schema.get("edges", []):
            src, sg = _endpoint(e["from"], resolved, ref, ref_g, external, graph,
                                env["doc_id"])
            dst, dg = _endpoint(e["to"], resolved, ref, ref_g, external, graph,
                                env["doc_id"])
            # 끝점 미해소도 게이트에 넘긴다 — 판정 전에 무음으로 사라지면 안 된다(D2).
            gate.commit_edge(graph, src, e["relation"], dst, cfg,
                             gate.PATH_SCHEMA, [prov], env["doc_id"],
                             src_graph=sg, dst_graph=dg)

    b.flush()
    return b


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

    for cand in candidates:
        cid = cand["chunk_id"]
        src = by_locator.get(loc_of.get(cid), {})
        prov = src.get("source_locator") or cid
        ref, ref_g = b.resolve_anchor(src.get("process_ref"), COORD_CATEGORY, prov)
        ref = b.descend_anchor(ref, src.get("electrode_type"), ref_g)   # ⓪ 비정형도 동일
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
            target = b.buffer.get(_n(a["attach_to"])) or _dict_hit(b, a["attach_to"], graph)
            if child is None:                   # 자식 미해소도 대상 쪽과 대칭으로 기록
                store.append_defect(
                    f"{env['doc_id']}: attach 자식 미해소 — "
                    f"'{a['surface']}' → '{a['attach_to']}' @ {cid}")
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


def _dict_hit(b, surface, graph):
    """attach 대상의 사전 해소 — **판정 파이프라인을 재사용한다**(문서 4 §4.4-3).

    여태 `hits[0]`을 무조건 골랐다. 사전은 **전 층 단일**이라 같은 표면형에 여러
    노드가 달릴 수 있고(§7.1), 첫 히트를 조용히 고르면 그것이 판정을 대신한다 —
    카테고리 불일치 안전망도 극성 후보 제외도 툼스톤 제외도 적용되지 않은 선택이
    엣지의 끝점이 된다.

    그래서 후보를 사전 히트로 **조립만** 하고 판정은 `matcher.match`가 한다.
    카테고리는 후보 자신의 것을 쓴다 — attach는 anchor 경로가 아니라 대상의
    카테고리가 정해져 있지 않고(auto 설비에도 붙는다), 관계는 그 뒤에
    카테고리쌍 매핑이 결정한다.
    """
    hits = [nid for nid in b.dict.lookup(surface) if graph.get(nid)]
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0] if is_live(graph.get(hits[0])) else None
    # 여러 개면 판정이 고른다 — 카테고리별로 갈라 각각 판정하고 확신된 것만 쓴다.
    from collections import defaultdict
    by_cat = defaultdict(list)
    for nid in hits:
        n = graph.get(nid)
        if not is_live(n):
            continue
        by_cat[n["category"]].append(
            {"id": nid, "canonical": n["canonical"],
             "aliases": [a["surface"] for a in n.get("aliases") or []],
             "category": n["category"], "layer": n.get("layer"),
             "polarity": n.get("polarity"), "exact": False})
    picked = []
    for cat, cands in by_cat.items():
        v = matcher.match(surface, cands, cat)
        if v["type"] == matcher.MATCH:
            picked.append(v["matched_id"])
    if len(picked) == 1:
        return picked[0]
    # 확신이 하나로 모이지 않았다 — **조용히 첫 히트를 고르지 않는다.**
    # 미해소로 두면 호출부가 orphan_attach 큐를 단다(문서 4 §4.4-5).
    store.append_defect(
        f"attach 대상 다중 해소 — '{surface}' → 후보 {len(hits)}건 · 확신 "
        f"{len(picked)}건. 첫 히트 임의 선택을 하지 않고 미해소로 둔다")
    return None


def _pair_relation(cfg, src_cat, dst_cat):
    """관계는 category_pair_map이 결정한다 — 게이트 패턴표의 특수형(§6-3)."""
    return (cfg.get("category_pair_map") or {}).get(f"{src_cat},{dst_cat}")


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


def run_document(path_or_env, layer=None):
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

    res = ingest(env)                                    # ① doc_hash → ② 근거 축 id
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
