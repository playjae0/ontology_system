# -*- coding: utf-8 -*-
"""doc_type 등록부 — **"이 문서 유형이 등록됐는가"의 단일 조회처** (카드 M2 · D-8).

    문서 도착 → **등록 여부 조회** → 등록됨: 운영 모드 / 미등록: 구축 모드(n6)

조회 결과가 모드를 가른다. 그래서 **묻는 곳이 여럿이어도 답하는 곳은 하나**여야 한다 —
지금 그 셋은 인입(M2 조회)·지문 스캔(preflight)·플랫폼 열람(D-67)이고, 각자 자기
방식으로 파일 시스템을 뒤지면 셋의 답이 갈린다.

**두 출처, 한 조회**:
  · **내장(builtin)** — 레포가 싣고 나온 `schemas/{doc_type}.json`. 층의 J10과 같은 결이다:
    등록 절차를 거치지 않고 처음부터 있는 것.
  · **등록(registered)** — n6 구축 모드가 확정해 `data/doc_types.json`에 등재한 것.

**층 등록부(`registry.json`)와는 다른 장부다** — 그쪽은 "어떤 층이 있나", 이쪽은
"어떤 문서 유형을 읽을 수 있나"다. D-8이 이미 목적별로 장부를 나눠 두었다.

파일은 실행 산출물이라 추적하지 않는다 — 등록의 원천은 `review/{doc_type}/approval.json`
이고 이 파일은 그 색인이다.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import log, store

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"

BUILTIN = "builtin"

_LOG = log.get(__name__)
REGISTERED = "registered"


def _registered():
    return store.read(store.DOC_TYPES, {})


def _builtin():
    """레포가 싣고 나온 doc_type — 스키마 파일의 실재가 곧 등록이다.

    `blocks.json`은 doc_type이 아니라 공용 블록이므로 제외한다 — 파일 이름이 아니라
    **내용의 `doc_type` 키**로 가른다(이름으로 가르면 그 자체가 규칙의 누수다).
    """
    out = {}
    for p in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        dt = s.get("doc_type")
        if not dt:
            continue
        out[dt] = {"doc_type": dt, "status": BUILTIN, "layer": s.get("layer"),
                   "schema": str(p.relative_to(ROOT)), "adapter": None,
                   "schema_version": s.get("schema_version")}
    return out


def all_doc_types():
    """전량 조회 — 내장 + 등록. 같은 이름이면 **등록분이 이긴다**(개정이 나중이다)."""
    out = _builtin()
    out.update(_registered())
    return out


def lookup(doc_type):
    """M2 조회 — 등록됐으면 그 항목, 아니면 None(= 구축 모드 대상)."""
    return all_doc_types().get(doc_type)


def schema_of(doc_type):
    """그 doc_type의 매칭 스키마. 등록부가 가리키는 실물을 읽는다."""
    e = lookup(doc_type)
    if not e or not e.get("schema"):
        return None
    p = ROOT / e["schema"]
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def adapter_paths():
    """등록된 어댑터의 소재 — 지문 스캔(n9)이 대조할 대상이다.

    **등록부가 정본**이고, 등록부에 어댑터가 없는 내장 doc_type은 여기 오지 않는다
    (내장은 스키마만 싣고 어댑터는 mock 트랙에 있다 — P트랙 이전의 잔재).
    """
    return [(dt, ROOT / e["adapter"]) for dt, e in all_doc_types().items()
            if e.get("adapter") and (ROOT / e["adapter"]).exists()]


def register(doc_type, *, layer, adapter, schema, adapter_version, approved_by,
             approved_at, instructions=None):
    """확정 — 등록부 등재. **승인 1회의 물리적 착지점**이다(틀 §2).

    이름 중복은 거부한다 — 같은 이름의 doc_type이 둘이면 조회가 어느 쪽을 답할지
    정해지지 않고, 그것은 M2 조회가 모드를 가르는 근거를 잃는다는 뜻이다.
    **내장 이름과의 충돌도 거부**다(내장도 조회 대상이다).
    """
    if not approved_by:
        log.explicit_fail(_LOG, "core.registry.register",
                          "승인자 미지정 — 무수정 자동 통과는 금지다")
        raise ValueError("승인자 미지정 — 무수정 자동 통과는 금지다 (문서 1 §승인 게이트)")
    reg = _registered()
    if doc_type in reg or doc_type in _builtin():
        log.explicit_fail(_LOG, "core.registry.register",
                          f"doc_type 이름 중복 — '{doc_type}'")
        raise ValueError(f"doc_type 이름 중복 — '{doc_type}'은 이미 등록돼 있다")
    reg[doc_type] = {
        "doc_type": doc_type, "status": REGISTERED, "layer": layer,
        "adapter": adapter, "schema": schema, "adapter_version": adapter_version,
        "approved_by": approved_by, "approved_at": approved_at,
        "instructions": list(instructions or []),
    }
    store.write(store.DOC_TYPES, reg)
    return reg[doc_type]


def unregister(doc_type):
    """등재 취소 — 시험·복구용. 내장은 지울 수 없다(파일이 원천이다)."""
    reg = _registered()
    if doc_type in reg:
        del reg[doc_type]
        store.write(store.DOC_TYPES, reg)
        return True
    return False
