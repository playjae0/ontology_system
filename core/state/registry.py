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

from core import paths
from core.llm import llm
from core.state import log, store

ROOT = paths.ROOT                  # 레포 루트는 자리 소유자가 안다 (B78)
SCHEMA_DIR = paths.schemas()           # **등록된** 스키마의 자리 (②등록 단)
FIXTURE_SCHEMA_DIR = paths.fixture_schemas()   # **내장(mock)** — 자리로 가른다

BUILTIN = "builtin"

_LOG = log.get(__name__)
REGISTERED = "registered"


def _registered():
    return store.read(store.DOC_TYPES, {})


def _builtin():
    """레포가 싣고 나온 doc_type — 스키마 파일의 실재가 곧 등록이다.

    **자리가 가른다**(B78 1b): 내장은 `tests/fixtures/schemas/`에만 있고 등록은
    `registry/schemas/`에만 있다 — 섞일 자리가 없다. 구판은 같은 폴더에 두고
    모드(`use_mock()`)로 갈랐고, 그래서 「mock이 이름만 다르게 숨어 있다」였다.

    `blocks.json`은 doc_type이 아니라 공용 블록이므로 레포 `schemas/`에 남는다 —
    파일 이름이 아니라 **내용의 `doc_type` 키**로 가른다(이름으로 가르면 그 자체가
    규칙의 누수다).
    """
    out = {}
    if not FIXTURE_SCHEMA_DIR.exists():
        return out
    for p in sorted(FIXTURE_SCHEMA_DIR.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        dt = s.get("doc_type")
        if not dt:
            continue
        out[dt] = {"doc_type": dt, "status": BUILTIN, "layer": s.get("layer"),
                   "schema": str(p.relative_to(ROOT)), "adapter": None,
                   # 내장은 **레포 기준** 경로다(등록분은 `registry/` 기준 — B78 1b).
                   "root": "repo",
                   "schema_version": s.get("schema_version")}
    return out


def all_doc_types():
    """전량 조회 — **mock 트랙일 때만** 내장 + 등록. 같은 이름이면 등록분이 이긴다.

    **내장은 mock 자산이다**(B70 ① · 문서 7 §7.5). 레포가 싣고 나온
    `schemas/{cp,pfmea,…}.json`은 회귀·골든셋·CSV 등가가 쓰는 창작물이고, 사내가
    등록한 적 없는 이름이다. 그런데 `USE_MOCK`과 무관하게 조회에 섞여, 이식 직후
    사내 화면이 **cp·pfmea·ipqc를 대조 목록에 띄웠다**(실측 열째 — 「mock이랑 비교
    돌아가는 거 뭐야」). `USE_MOCK=0`이면 **등록부가 doc_type의 전부다.**

    자리가 여기인 이유: `lookup`·`schema_of`·`adapter_paths`·`platform doctypes`가
    전부 이 함수를 지난다 — 조건을 호출부마다 두면 그중 하나가 빠지는 날이 온다.
    """
    # **자리가 가르므로 모드 분기는 안전망이다**(B78 1b) — 내장은 픽스처 폴더에만
    # 있어서 운영 배치에는 그 폴더가 아예 없다. 그래도 분기를 남기는 이유: 레포를
    # 통째로 이식하면 픽스처가 디스크에 같이 오고(사내 실측), 그때 가르는 것은
    # 모드다(D-150 ① — 「모드가 0이다」가 핵심이지 「폴더가 없다」가 아니다).
    out = _builtin() if llm.use_mock() else {}
    out.update(_registered())
    return out


def lookup(doc_type):
    """M2 조회 — 등록됐으면 그 항목, 아니면 None(= 구축 모드 대상)."""
    return all_doc_types().get(doc_type)


def _abs(entry, rel):
    """등록부의 상대 경로 → 실물 자리 (B78 1b).

    **등록분은 `registry/` 기준**이다 — 그래야 상태 루트를 옮겨도 등록부를 고칠
    필요가 없다(옛 항목은 `platform migrate`가 재작성한다). 내장은 레포 기준이다.
    """
    base = ROOT if (entry or {}).get("root") == "repo" else paths.registry()
    return base / rel


def at(rel):
    """**상태에 실린 상대 경로 → 실물 자리** — registry 먼저, 레포 나중(B78 1b).

    `_abs`가 등록부 항목의 규칙이라면 이것은 **검수 상태(`review/<dt>/state.json`)의
    규칙**이다: 그 초안은 검수 자리(`registry/review/…`)일 수도, 레포의 픽스처·킷
    전시물일 수도 있다. 규칙이 한 자리에 있어야 쓰는 쪽(`cli/register._rel`)과 읽는
    쪽이 갈리지 않는다.
    """
    p = Path(rel)
    if p.is_absolute():
        return p
    under = paths.registry() / p
    return under if under.exists() else ROOT / p


def schema_of(doc_type):
    """그 doc_type의 매칭 스키마. 등록부가 가리키는 실물을 읽는다."""
    e = lookup(doc_type)
    if not e or not e.get("schema"):
        return None
    p = _abs(e, e["schema"])
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def adapter_paths():
    """등록된 어댑터의 소재 — 지문 스캔(n9)이 대조할 대상이다.

    **등록부가 정본**이고, 등록부에 어댑터가 없는 내장 doc_type은 여기 오지 않는다
    (내장은 스키마만 싣고 어댑터는 mock 트랙에 있다).

    **없는 파일을 건너뛰지 않는다**(B70 ② — 구판은 `if exists`로 걸렀다). 등록
    산출(`data/doc_types.json` · `adapters/<dt>.py` · `schemas/<dt>.json` ·
    `review/<dt>/`)은 git 추적 밖이라 **코드만 옮기면 따라오지 않는데**, 조용히
    거르면 화면이 「내장 셋만 있다」로 보인다. 결손의 판정은 `missing_assets()`가
    하고, 막는 자리는 사람이 치는 진입(`cli/scan.py::adapters`)이다.
    """
    return [(dt, _abs(e, e["adapter"])) for dt, e in all_doc_types().items()
            if e.get("adapter")]


def missing_assets():
    """등록부가 가리키는데 **실물이 없는** 것 — `[{doc_type, kind, path, …}]`.

    조회처는 하나다(이 모듈) — 화면(`platform doctypes`)과 관문(스캔 진입)이 같은
    판정을 읽는다. 내장은 스키마 파일의 실재가 곧 등록이라 대상이 아니다.
    """
    out = []
    for dt, e in sorted(_registered().items()):
        for key in ("adapter", "schema"):
            rel = e.get(key)
            if rel and not _abs(e, rel).exists():
                out.append({"doc_type": dt, "kind": key, "path": rel,
                            "approved_by": e.get("approved_by"),
                            "approved_at": e.get("approved_at"),
                            "layer": e.get("layer")})
    return out


def orphan_reviews():
    """**등록부에 없는데 `review/<dt>/approval.json`만 있는 이름** (B77 ③).

    `missing_assets()`의 **역방향**이다: 그쪽은 「등록부가 가리키는데 실물이 없다」를
    재고, 이쪽은 「사람이 승인한 산출은 있는데 등록부에 이름이 없다」를 잰다.
    사내 실측: `review/`를 옮기고도 `data/doc_types.json`을 안 옮겨 등록부가 비었고,
    화면은 그 사실을 말하지 않았다 — 사람은 「등록이 사라졌다」고만 알았다.

    승인 기록(`approval.json`)이 있는 것만 센다 — 작업 중인 `review/`는 등록이
    아니다(문서 7 §7.8: 승인 기록이 등록의 물리 정본이다).
    """
    reg = _registered()
    out = []
    review = paths.review()
    if not review.exists():
        return out
    for d in sorted(x for x in review.iterdir() if x.is_dir()):
        ap = d / "approval.json"
        if d.name in reg or not ap.exists():
            continue
        try:
            meta = json.loads(ap.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        out.append({"doc_type": d.name, "path": str(ap),
                    "approved_by": meta.get("approved_by") or meta.get("by"),
                    "approved_at": meta.get("approved_at") or meta.get("at")})
    return out


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


def revise(doc_type, *, adapter, schema, adapter_version, approved_by,
           approved_at, instructions=None):
    """**등록된 doc_type의 새 판** — 이름은 그대로, 정본을 교체하고 `revision`을 올린다.

    구판은 재등록 경로가 아예 없었다(H27): `register`가 이름 중복을 거부하고
    `cli.register`의 generate 진입도 막아, **어댑터를 고쳐 다시 등록할 길이 없었다.**
    사내가 지금 그 자리에서 멈춰 있다.

    **승인 기록은 덮지 않고 누적한다** — 「누가 언제 무엇을 승인했나」가 판 하나로
    줄어들면 옛 판으로 인입된 문서의 근거가 사라진다. `approvals`가 그 이력이고
    최상위 `approved_by`·`approved_at`은 **현행 판**의 것이다.

    **기존 인입분을 자동으로 다시 읽지 않는다**(문서 4 §4.8-7) — 재인입은 사람이 정한다.
    """
    reg = _registered()
    if doc_type not in reg:
        log.explicit_fail(_LOG, "core.registry.revise",
                          f"등록되지 않은 doc_type — '{doc_type}'")
        raise ValueError(f"'{doc_type}'은 등록돼 있지 않다 — 새 판은 등록분에만 낸다")
    if not approved_by:
        raise ValueError("승인자 미지정 — 무수정 자동 통과는 금지다 (문서 1 §승인 게이트)")
    cur = reg[doc_type]
    hist = list(cur.get("approvals") or [])
    if not hist and cur.get("approved_by"):     # 구판 항목의 첫 승인을 이력에 옮긴다
        hist.append({"revision": cur.get("revision", 0),
                     "approved_by": cur["approved_by"],
                     "approved_at": cur.get("approved_at"),
                     "adapter_version": cur.get("adapter_version")})
    rev = int(cur.get("revision", 0)) + 1
    hist.append({"revision": rev, "approved_by": approved_by,
                 "approved_at": approved_at, "adapter_version": adapter_version})
    reg[doc_type] = {**cur, "adapter": adapter, "schema": schema,
                     "adapter_version": adapter_version, "revision": rev,
                     "approved_by": approved_by, "approved_at": approved_at,
                     "approvals": hist,
                     "instructions": list(instructions or [])}
    store.write(store.DOC_TYPES, reg)
    return reg[doc_type]


def ingested_docs(doc_type):
    """그 doc_type으로 **이미 인입된 문서** 목록 — 재인입 판단의 재료다.

    새 판을 확정해도 시스템이 자동으로 다시 읽지 않으므로(§4.8-7), 무엇이 옛 판으로
    들어와 있는지를 화면이 말해야 사람이 정할 수 있다.
    """
    reg = store.read(store.DOC_REGISTRY, {})
    return sorted(d for d, v in reg.items() if (v or {}).get("doc_type") == doc_type)


def unregister(doc_type):
    """등재 취소 — 시험·복구용. **레포가 싣고 나온 내장은 지울 수 없다**(파일이 원천이다).

    다만 **확정이 승격시킨 실물은 함께 걷는다** — 확정은 어댑터·스키마를 검수 자리에서
    정본 자리(`adapters/{doc_type}.py`·`schemas/{doc_type}.json`)로 옮기고(문서 6 §6.5),
    승격된 스키마는 그 순간부터 **내장 출처**가 된다. 등재만 지우고 파일을 남기면
    조회에는 계속 잡히면서 등록부에는 없는 반쪽 상태가 되고, 같은 이름의 재등록이
    「내장 중복」으로 영영 막힌다(실측).

    **등재 항목이 가리키는 경로만** 지운다 — 레포가 싣고 나온 `tests/fixtures/schemas/cp.json` 같은
    것은 등재 항목이 없으므로 대상이 아니다.
    """
    reg = _registered()
    entry = reg.get(doc_type)
    if entry is None:
        return False
    for key, base in (("adapter", "adapters"), ("schema", "schemas")):
        rel = entry.get(key) or ""
        p = _abs(entry, rel)
        if rel.startswith(base + "/") and p.exists():
            p.unlink()
    del reg[doc_type]
    store.write(store.DOC_TYPES, reg)
    return True
