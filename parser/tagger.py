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

MOCK_IMAGE_SUMMARY = "MOCK 요약: {image_ref}"      # 대체 갈래의 고정 문자열 (증분0 §5-3)


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


def coord_from_section(pieces, *, layer="process", nodes=None,
                       ref_field="process_ref", sep=" > "):
    """산문 조각의 `section`(헤딩 경로)에서 좌표를 세운다 (B43 ④).

    **대조는 `surfaces()` 하나를 재사용한다** — 좌표 태깅과 같은 연산이다.
    새로 짜면 「무엇이 일치인가」가 두 곳에 살고 하나가 낡는다.

    규칙 셋:
      ①**정확 일치만** — 추론도 문자열 파싱도 하지 않는다. 일치가 없으면 비운다.
      ②경로에 일치가 여럿이면 **가장 깊은 것**(뒤쪽) — 좁은 좌표가 더 많은 것을
        말한다.
      ③**이미 값이 있으면 덮지 않는다** — 어댑터가 낸 좌표가 우선이다.

    일치 없음은 실패가 아니다: 인입이 `orphan_anchor`로 받아 사람에게 올린다.
    """
    nodes = nodes if nodes is not None else closed_list(layer)
    idx = surfaces(nodes)
    out = []
    for p in pieces:
        r = dict(p)
        if not r.get(ref_field) and r.get("section"):
            hit = [seg.strip() for seg in str(r["section"]).split(sep)
                   if seg.strip() in idx]
            if hit:
                r[ref_field] = hit[-1]          # 가장 깊은 일치
                r.setdefault("meta", {})["coord_from_section"] = True
        out.append(r)
    return out


def tag(pieces, *, layer="present", nodes=None, ref_field="process_ref",
        pick=None, doc_type=None, progress=None):
    """좌표 태깅 — 조각이 든 좌표를 닫힌 목록과 대조하고 `process_group`을 파생한다.

    **LLM 지점 ⑨다**(문서 7 §7.6-B-2). 목록에 있다는 것과 mock에서 모델을 부른다는
    것은 다른 말이다:

    | | 갈래 |
    |---|---|
    | `pick=None` | **닫힌 목록 스냅샷의 정확 일치 대조 — 모델을 부르지 않는다**(§7.1 대체 표) |
    | `pick` 주입 | 모델이 **닫힌 목록 중에서 고르거나 null**을 낸다 |

    **판정은 함수 유무 하나다**(B48) — 파서는 모드를 읽지 않는다. 대체가 선언되지
    않은 LLM 지점은 모델 없는 실행에서 실호출로 흘러 외부 의존 0(문서 1 B12)이
    깨지고 **미설치 환경에서 실행 자체가 죽는다** — 그래서 대체 갈래가 명세에
    못박혀 있고, 이 함수의 기본값이 그것이다.

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
    # **진행을 밖으로 흘린다.** `pick`은 좌표가 닫힌 목록과 정확히 일치하지 않는
    # 조각마다 불린다 — 수천 행이면 수천 회다. 그 사이 화면이 조용하면 사람은
    # «멈췄다»고 읽는다(사내 실측). 콜백은 선택이고 없으면 아무 일도 안 한다.
    total, calls = len(pieces), 0
    for i, p in enumerate(pieces, 1):
        r = dict(p)
        # **조각 공통 층을 세운다**(문서 2 §2.2 계약 ①) — 모든 record/chunk가
        # `source_locator`·`doc_type`·`process_group`·`process_ref`·
        # `electrode_type`을 달고 들어온다. 어댑터가 좌표를 못 뽑는 계열(기본
        # 어댑터의 슬라이드 분할 등)에서도 **키는 있어야 한다** — 값이 null인 것과
        # 키가 없는 것은 다르다: 후자면 인입의 필드 검증이 "부재"를 판정할 대상을
        # 잃고, 조각 공통 층이 계약이 아니라 어댑터별 재량이 된다.
        for k in ("doc_type", "process_group", "process_ref", "electrode_type"):
            r.setdefault(k, doc_type if k == "doc_type" else None)
        ref = r.get(ref_field)
        node = idx.get(ref) if ref else None
        if ref and node is None and pick is not None:
            # 실호출 갈래 — 닫힌 목록을 선택지로 넘긴다. 목록 밖 답은 버린다.
            calls += 1
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
        if progress is not None:
            progress(i, total, calls)
    return out


def complete_images(pieces, summarize=None, *, kept=None):
    """이미지 placeholder의 요약 완성 — **코어가 호출한다**(어댑터 아님, §6 규약 3).

    **갈림길은 함수 유무 하나다**(B48 · 문서 7 §7.6-B-1): `summarize`가 오면 실호출,
    안 오면 고정 문자열 + `source="mock"`. 파서는 모드를 읽지 않는다.

    **「함수 없이 실호출 모드」는 여기까지 오지 않는다** — 팩토리(`llm.image_summarizer()`)가
    미설정이면 `require()`로 파싱 전에 멈춘다. 구판은 그 검사를 여기서도 했고, 그러려면
    파서가 모드를 알아야 했다(그 판독이 설정 파일 갈래를 못 봐 갈렸다 — B42·B48).

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
            else:
                r["text"] = MOCK_IMAGE_SUMMARY.format(image_ref=ref)
                src = "mock"
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
