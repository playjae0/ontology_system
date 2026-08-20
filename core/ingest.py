# -*- coding: utf-8 -*-
"""인입 — 계약 JSON을 받아 근거 축을 확정한다 (n2 · n1).

에이전트 측 검증 배열 (증분0 §3 G1 공통 · 가결정 D-2):
    ① doc_hash 대조(n2) → ② 근거 축 id 계산(n1) → ③ 필드 검증(1c — G3 소관)

파서 측 검사(preflight·validator)는 **문서 단위 실패**로 착지하고(C14),
에이전트 측 ③은 **큐**로 착지한다. 두 검사 체계는 겹치지 않고 이어진다.

이 모듈은 그래프를 만들지 않는다 — 개체 해소·엣지 생성은 1c′(G3)의 몫이다.
여기까지가 "주소 체계"이고, 주소가 먼저 있어야 나머지가 그것을 참조한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import store
from .ids import US, OccCounter, chunk_id, doc_hash, norm, record_id

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

# 재인입 회수에서 **내리지 않는** 큐 kind — 조건 판정이 아니라 상시 작업목록이다.
# 이것을 내리면 재인입 한 번에 미검토 노드 목록이 증발한다(20회차 실측 61 → 11).
# 나머지 kind는 이번 인입이 현재 스냅샷을 다시 싣는다(D-59가 가른 "싣는 쪽/내리는 쪽").
STANDING_KINDS = {"auto_node", "uncertain_match"}


def load_schema(doc_type):
    """M2 등록 여부 조회 — **등록부가 답한다**(카드 M2 · n6이 등재).

    구판은 `schemas/` 파일 실재를 직접 봤다. 그러면 n6이 등록한 doc_type을 인입이
    모르고, "묻는 곳이 셋인데 답하는 곳도 셋"이 된다 — 조회가 모드를 가르는 근거를
    잃는다. 내장(builtin)도 등록부가 함께 답하므로 기존 경로는 그대로 산다.
    """
    from .registry import schema_of
    return schema_of(doc_type)


class IngestResult:
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.status = "ok"          # ok | held
        self.reason = None
        self.chunk_ids: list[str] = []
        self.record_ids: list[str] = []
        self.defects: list[str] = []

    @property
    def ids(self):
        return set(self.chunk_ids) | set(self.record_ids)

    def __repr__(self):
        return (f"<Ingest {self.doc_id} {self.status} "
                f"chunks={len(self.chunk_ids)} records={len(self.record_ids)}>")


# ---------------------------------------------------------------- ① n2
def check_doc_hash(env):
    """같은 내용이 **다른 doc_id**로 이미 있으면 보류한다.

    같은 doc_id는 재인입(정상 경로)이므로 통과시킨다 — 개정은 revision이 가른다.
    판정 기준은 내용 해시 단일이며, 파일명·크기는 화면 표시용 참고일 뿐이다(N8).
    보류 문서는 **그래프·청크에 아무것도 쓰지 않는다.**
    """
    doc_id, dh = env["doc_id"], doc_hash(env)
    reg = store.read(store.DOC_REGISTRY, {})
    for other, rec in reg.items():
        if rec["doc_hash"] == dh and other != doc_id:
            store.enqueue(
                "duplicate_doc_hold",
                f"같은 내용이 이미 {other}로 인입되어 있다",
                doc_id,
                {"doc_id": doc_id, "existing_doc_id": other, "doc_hash": dh,
                 "source_path": env.get("source_path"),
                 "existing_source_path": rec.get("source_path"),
                 "revision": env.get("revision")},
            )
            return dh, other
    return dh, None


# ---------------------------------------------------------------- 재인입 회수
def doc_locators(env, doc_id, chunks):
    """그 문서 몫의 provenance 문자열 — **봉투(현행 개정판) + 기존 청크(구판)**.

    새 인덱스를 만들지 않는다. 조각은 전부 `source_locator`를 갖고(계약 v2 ①),
    청크는 `doc_id`를 갖는다(§2.3) — 둘의 합집합이 그 문서의 발자국이다.
    개정판에서 **삭제된 행**은 봉투에 없으므로 기존 청크가 그 자리를 메우고,
    청크를 남기지 않은 행(content 필드 없는 레코드)은 doc_id 접두로 걷는다.
    """
    locs = {r.get("source_locator") for r in env.get("records", [])}
    locs |= {c.get("source_locator") for c in env.get("chunks", [])}
    locs |= {c.get("source_locator") for c in chunks["chunks"].values()
             if c.get("doc_id") == doc_id}
    return {loc for loc in locs if loc}


def withdraw(env, doc_id):
    """재인입 회수 3분류 (CH3B 3.8 H2 — 이 절이 오래 미완이었다).

    ①**회수** — 그 문서의 청크·describes, 그리고 노드·엣지·값의 provenance 항목.
      근거가 0이 된 auto 노드·엣지는 **삭제하지 않는다**(지우면 재인입이 부활시키고
      사람이 "왜 사라졌나"를 물을 자리도 없어진다 — L9). 그 판정은 여기가 아니라
      **빌드 말미**(`pipeline.finalize`)가 한다 — 회수 직후는 아직 재적재 전이라
      "근거 0"이 참이 아니고, 그때 울리면 매 재인입마다 거짓 항목이 쌓인다(D-65와 같은 자리).
    ②**보존** — 살아있는 노드의 사전·alias, 그리고 미검토 작업목록(`STANDING_KINDS`).
    ③**재평가** — 그 문서발 조건 큐를 내리고, 이번 인입이 현재 스냅샷을 다시 싣는다.
      근거 문장이 삭제되면 그 조건도 함께 내려가야 한다 — 큐는 이력이 아니라 화면이다.
    """
    from router import discover
    from .bootstrap import open_graph

    chunks = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    locs = doc_locators(env, doc_id, chunks)

    # ③ 먼저 내린다 — 회수가 싣는 evidence_lost가 같은 손에 지워지면 안 된다.
    q = store.read(store.QUEUE, [])
    kept = [x for x in q
            if x.get("doc_id") != doc_id or x.get("kind") in STANDING_KINDS]
    if len(kept) != len(q):
        store.write(store.QUEUE, kept)

    # ① 청크·describes
    gone = {cid for cid, c in chunks["chunks"].items() if c.get("doc_id") == doc_id}
    for cid in gone:
        del chunks["chunks"][cid]
    chunks["describes"] = [d for d in chunks["describes"] if d["chunk_id"] not in gone]
    store.write(store.CHUNKS, chunks)

    def mine(p):
        return p in locs or p == doc_id or str(p).startswith(doc_id + "-")

    def strip(holder):
        """그 문서 유래 provenance 항목을 걷어낸다. 남은 개수를 돌려준다."""
        holder["provenance"] = [p for p in (holder.get("provenance") or [])
                                if not mine(p)]
        return len(holder["provenance"])

    # ① 노드·값·엣지의 provenance
    for layer in discover():
        g = open_graph(layer)
        for n in g.nodes.values():
            strip(n)
            for name, val in list((n.get("attrs") or {}).items()):
                if isinstance(val, list):               # 맥락형 — context 그룹별 항목
                    left = [it for it in val if strip(it)]
                    n["attrs"][name] = left
                    if not left:
                        del n["attrs"][name]
                elif isinstance(val, dict) and "provenance" in val:
                    if not strip(val):                  # 단순형 — 빈 그룹 하나로 취급
                        del n["attrs"][name]
        for e in g.edges:
            strip(e)
        g.save()


def register_doc(env, dh):
    reg = store.read(store.DOC_REGISTRY, {})
    doc_id = env["doc_id"]
    first = reg.get(doc_id, {}).get("first_ingested_at") or env.get("parsed_at")
    reg[doc_id] = {"doc_hash": dh, "revision": env.get("revision"),
                   "source_path": env.get("source_path"),
                   "doc_type": env.get("doc_type"),
                   "first_ingested_at": first}
    store.write(store.DOC_REGISTRY, reg)


# ---------------------------------------------------------------- ② n1
def _join_values(rec, schema):
    """join 대상 = 매칭 스키마 `fields` **선언 순서**의 값들 (D-14).

    순서가 산식의 일부다 — 미지정으로 두면 처리 순서에 따라 id가 달라진다.
    스키마가 없으면(등록 전 doc_type) source_locator를 뺀 나머지를 키 정렬해 쓴다.
    """
    if schema:
        return [rec.get(f) for f in schema["fields"]]
    return [rec[k] for k in sorted(rec) if k != "source_locator"]


def ingest(env):
    """계약 JSON 하나를 인입해 근거 축 id를 확정한다.

    **멱등**하다 — 같은 문서를 두 번 넣어도, 조각 순서를 셔플해 넣어도
    같은 id 집합이 나온다. 발급이 아니라 내용 계산이기 때문이다.
    """
    doc_id = env["doc_id"]
    res = IngestResult(doc_id)

    dh, dup = check_doc_hash(env)                       # ①
    if dup:
        res.status = "held"
        res.reason = f"duplicate_doc_hold (기존 {dup})"
        return res

    # 재인입이면 그 문서 몫을 먼저 걷어낸다 — 덮어쓰기 전에 회수해야 개정이 성립한다.
    reg = store.read(store.DOC_REGISTRY, {})
    if doc_id in reg:
        withdraw(env, doc_id)
        if reg[doc_id].get("doc_hash") != dh:           # 청크가 바뀌었다 (3.11 규약 7)
            from . import extract as extract_mod
            extract_mod.invalidate(doc_id)

    schema = load_schema(env.get("doc_type"))
    chunks = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    occ = OccCounter()
    adapter_version = env.get("adapter_version")        # 봉투 1회 → 청크로 복사(C9)

    def put_chunk(cid, text, section, src_loc, meta):
        prev = chunks["chunks"].get(cid)
        if prev is not None and prev.get("doc_id") != doc_id:
            msg = f"{doc_id}: chunk_id 충돌 {cid} @ {src_loc}"
            store.append_defect(msg)                    # 조용히 덮지 않는다
            res.defects.append(msg)
        chunks["chunks"][cid] = {
            "doc_id": doc_id,
            "text": text,                               # 원문 무손실 (카드 C8)
            "section": section,
            "source_locator": src_loc,
            "adapter_version": adapter_version,
            "meta": meta or {},
            "linked": False,                            # 링킹 0건도 보존 (카드 C6)
        }
        res.chunk_ids.append(cid)

    if env.get("payload_kind") == "table":
        content_fields = [f for f, d in (schema or {}).get("fields", {}).items()
                          if d.get("role") == "content"]
        for rec in env.get("records", []):
            vals = _join_values(rec, schema)
            joined = US.join("" if v is None else norm(v) for v in vals)
            rid = record_id(doc_id, vals, occ.next("\x02rec", joined))
            if rid in res.record_ids:
                msg = f"{doc_id}: record_id 충돌 {rid} @ {rec.get('source_locator')}"
                store.append_defect(msg)
                res.defects.append(msg)
            res.record_ids.append(rid)
            # table의 content role 필드는 **필드별 별도 청크**다 (정의서 §3.4 · D8).
            # id는 발급이 아니라 record_id에서 파생된다 — 그래야 재인입에서 같다.
            for f in content_fields:
                if rec.get(f):
                    put_chunk(f"{rid}-{f}", rec[f], rec.get("source_locator", ""),
                              rec.get("source_locator"), {"field": f})
    else:
        for c in env.get("chunks", []):
            text, section = c.get("text", ""), c.get("section", "")
            put_chunk(chunk_id(doc_id, text, section, occ.next(section, text)),
                      text, section, c.get("source_locator"), c.get("meta"))

    store.write(store.CHUNKS, chunks)
    register_doc(env, dh)
    return res
