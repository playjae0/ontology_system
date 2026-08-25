# -*- coding: utf-8 -*-
"""tagger — 정규 조각 → 계약 JSON (파서_명세 §3 · CH2 2.2).

    좌표 태깅 + 봉투 구성 + context + 이미지 placeholder의 요약 완성

**좌표 태깅의 닫힌 목록은 골격 전 노드다**(A11-6 · D-45 — 개념 + 인스턴스).
구 "세부공정 목록" 서술은 폐기됐다. 목록의 실물은 `data/skeleton_closed_list.json`
스냅샷이며(D-11 확정), 파서와 에이전트가 **같은 파일**을 본다 — 파서는 이 레포의
그래프를 읽지 않기 때문이다(D-9).

**상위·개념 해상도 선택은 오류가 아니라 저해상도 부착이다.** 문서가 "탭용접"이라고만
말하면 개념 노드가 답이고, 축값이 확정이면 인입 측이 인스턴스로 하강한다(A11-9 ⓪).
태거는 **문서가 말한 것**을 적을 뿐 해상도를 올리지 않는다.

`process_group`은 태거가 지어내지 않는다 — **tier:main 조상 파생**이다(A11-7).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "skeleton_closed_list.json"

MOCK_IMAGE_SUMMARY = "MOCK 요약: {image_ref}"      # USE_MOCK 고정 문자열 (증분0 §5-3)


def closed_list(layer="process", path=None):
    """골격 닫힌 목록 스냅샷을 읽는다 — 없으면 빈 목록(조용히 그래프로 가지 않는다)."""
    p = Path(path or SNAPSHOT)
    if not p.exists():
        return []
    return (json.loads(p.read_text(encoding="utf-8")).get(layer) or {}).get("nodes", [])


def surfaces(nodes):
    """닫힌 목록의 선택지 — canonical + alias 전량. LLM은 여기서 **고르기만** 한다."""
    out = {}
    for n in nodes:
        out[n["canonical"]] = n
        for a in n.get("aliases") or []:
            out.setdefault(a, n)
    return out


MAX_UP = 16                                       # 조상 추적 깊이 제한 (순환 방어)


def group_of(node, nodes):
    """`process_group` = **tier:main 조상**(A11-7) — 지어내지 않고 골격에서 딴다.

    스냅샷이 실어 준 `parent` 링크를 타고 올라간다. 자기가 이미 main이면 자기다.
    문자열을 파싱하지 않는다 — 판정 근거는 필드다(A11-8).
    """
    by_canon = {n["canonical"]: n for n in nodes}
    cur, seen = node, set()
    for _ in range(MAX_UP):
        if cur is None or cur["canonical"] in seen:
            return None
        if cur.get("tier") == "main":
            return cur["canonical"]
        seen.add(cur["canonical"])
        cur = by_canon.get(cur.get("parent"))
    return None


def tag(pieces, *, layer="present", nodes=None, ref_field="process_ref", pick=None):
    """좌표 태깅 — 조각이 든 좌표를 닫힌 목록과 대조하고 `process_group`을 파생한다.

    **LLM 지점 ⑨다**(문서 7 §7.6-B-2). 목록에 있다는 것과 mock에서 모델을 부른다는
    것은 다른 말이다:

    | | 갈래 |
    |---|---|
    | `pick=None` (USE_MOCK=1) | **닫힌 목록 스냅샷의 정확 일치 대조 — 모델을 부르지 않는다**(§7.1 대체 표) |
    | `pick` 주입 (USE_MOCK=0) | 모델이 **닫힌 목록 중에서 고르거나 null**을 낸다 |

    대체가 선언되지 않은 LLM 지점은 USE_MOCK=1에서 실호출로 흘러 외부 의존 0
    (문서 1 B12)이 깨지고 **미설치 환경에서 실행 자체가 죽는다** — 그래서 mock
    갈래가 명세에 못박혀 있고, 이 함수의 기본값이 그것이다.

    **목록 밖이면 값을 고치지 않고 그대로 둔다**(null 허용 — §4 "닫힌 목록에서 선택
    또는 null"). 검증은 인입 소관이고 파서는 좌표를 판정하지 않는다 — 태거가 임의로
    고쳐 넣으면 그 순간 파서가 골격을 해석하게 된다.

    실호출 갈래도 **목록 밖 답은 버린다** — 모델이 지어낸 좌표가 태깅되면 인입의
    orphan_anchor가 그것을 골격으로 착각한다. 파서는 `core/`를 import하지 않으므로
    (P1) `pick`은 **주입**받는다.
    """
    nodes = nodes if nodes is not None else closed_list(layer)
    idx = surfaces(nodes)
    out = []
    for p in pieces:
        r = dict(p)
        ref = r.get(ref_field)
        node = idx.get(ref) if ref else None
        if ref and node is None and pick is not None:
            # 실호출 갈래 — 닫힌 목록을 선택지로 넘긴다. 목록 밖 답은 버린다.
            chosen = pick(ref, sorted(idx))
            if chosen and chosen in idx:
                r[ref_field] = chosen
                node = idx[chosen]
                r.setdefault("meta", {})["coord_tag_source"] = "live"
        if ref and node is None:
            r[ref_field] = ref                      # 그대로 둔다 — orphan_anchor는 인입 몫
        if node is not None and not r.get("process_group"):
            g = group_of(node, nodes)
            if g:
                r["process_group"] = g
        out.append(r)
    return out


def complete_images(pieces, summarize=None, *, allow_mock=True, kept=None):
    """이미지 placeholder의 요약 완성 — **코어가 호출한다**(어댑터 아님, §6 규약 3).

    **여기가 조용한 오염이 나던 자리다.** 호출부가 `summarize`를 빼먹으면 고정 문자열
    `"MOCK 요약: img_001"`이 청크 텍스트가 되어 색인되고, 답변 근거로 되돌아온다 —
    크래시가 아니라 오염이라 더 위험하다(문서 7 §7.6-B-4).

    그래서 갈림길을 **인자로 드러낸다**:

    | | `summarize` 있음 | 없음 |
    |---|---|---|
    | `allow_mock=True` (USE_MOCK=1) | 실호출 | 고정 문자열 + `source="mock"` |
    | `allow_mock=False` (USE_MOCK=0) | 실호출 | **RuntimeError** — 조용히 mock으로 떨어지지 않는다 |

    표시는 **주석이 아니라 데이터**다(§7.5 「실호출로만 검증되는 항목의 표시」와 같은 결):

    - `meta.image_summary = True` — 이 텍스트는 원문이 아니라 요약이다(§7.1 대체 표).
    - `meta.image_summary_source = "mock" | "live"` — **어느 갈래가 만들었나.**
      `image_summary`만으로는 mock 산출과 실산출이 구분되지 않아, 오염을 소비부에서
      걸러낼 근거가 데이터에 남지 않는다.

    파서는 `core/`를 import하지 않는다(P1 — 결합은 파일 계약뿐). 그래서 실호출 경로는
    **주입**받는다: 판단은 호출부(`parser/pipeline.py`)가 하고 여기는 계약만 지킨다.
    """
    out = []
    for p in pieces:
        r = dict(p)
        ref = r.get("image_ref")
        if ref and not r.get("text") and kept is not None and ref in kept:
            # **보존분 재사용** — 매 인입 새로 부르면 text가 흔들려 그 문서의
            # chunk_id가 전량 이동한다(문서 6 §6.3 · chunk_id 결정성 §7.2).
            r["text"] = kept[ref]
            m = r.setdefault("meta", {})
            m["image_summary"] = True
            m["image_summary_source"] = "kept"
            out.append(r)
            continue
        if ref and not r.get("text"):
            if summarize is not None:
                r["text"] = summarize(ref)
                src = "live"
                if kept is not None:
                    kept[ref] = r["text"]        # **보존** — 재인입에 재사용(§6.3)
            elif allow_mock:
                r["text"] = MOCK_IMAGE_SUMMARY.format(image_ref=ref)
                src = "mock"
            else:
                raise RuntimeError(
                    f"이미지 요약 실호출 경로가 비어 있다 (image_ref={ref}) — "
                    "USE_MOCK=0에서는 summarize를 주입해야 한다. mock 고정 문자열을 "
                    "청크로 실으면 그것이 답변 근거로 되돌아온다 (문서 7 §7.6-B-4)")
            m = r.setdefault("meta", {})
            m["image_summary"] = True
            m["image_summary_source"] = src
        out.append(r)
    return out


def envelope(adapter, doc_id, source_path, pieces, *, revision="R1",
            parsed_at="2026-01-05T00:00:00", parser_version="p1-1.0",
            context=None, struct_map=None):
    """봉투 구성 — **파서가 만든다**(CH2 2.2). 정본 id는 넣지 않는다(A7-1).

    `adapter_version`은 봉투에 **1회** 기록한다(A7-3) — 조각마다 복사하지 않는다.
    구조 지도가 있으면 함께 보존한다(같은 지도 → 같은 분할 → 같은 chunk_id).
    """
    a = adapter.ADAPTER if hasattr(adapter, "ADAPTER") else adapter
    kind = a["payload_kind"]
    env = {
        "doc_id": doc_id, "doc_type": a["doc_type"], "source_path": source_path,
        "revision": revision, "parsed_at": parsed_at,
        "parser_version": parser_version, "adapter_version": a["adapter_version"],
        "context": dict(context or {}), "payload_kind": kind,
        ("records" if kind == "table" else "chunks"): pieces,
    }
    if struct_map is not None:
        env["struct_map"] = struct_map
    return env
