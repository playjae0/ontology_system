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


def load_schema(doc_type):
    p = SCHEMA_DIR / f"{doc_type}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


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
