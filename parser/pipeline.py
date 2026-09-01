# -*- coding: utf-8 -*-
"""파서 진입점 — 코어 6종을 순서대로 엮는다 (파서_명세 §3 · D-2 확정 배열).

    reader → preflight → [struct-map] → adapter → normalizer → tagger → validator

**실패는 문서 단위 단일이다**(C14). 어느 단계에서 걸리든 그 문서는 통째로 나가지
않고 사유가 붙은 결과가 나온다 — 에이전트 측 인입은 그 결과를 받아 큐에 싣는다.
파서는 큐 파일을 직접 쓰지 않는다: 파서는 별도 프로그램이고 결합은 JSON뿐이다(D-9).

돌려주는 것: `ParseResult(ok, envelope, failures, report)`.
`failures`는 `[{kind, reason, detail}]`이고 kind는 **닫힌 20종 안**이다 —
`parse_failure` · `adapter_mismatch` · `hierarchy_unresolved` 셋만 쓴다(신설 0).
"""
from __future__ import annotations

import logging
import os

from . import normalizer, preflight, struct_map, tagger, validator
from .reader import head, read

PARSER_VERSION = "p1-1.0"


class ParseResult:
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.ok = False
        self.envelope = None
        self.failures: list[dict] = []
        self.report: dict = {}

    def fail(self, kind, reason, detail=None):
        self.failures.append({"kind": kind, "reason": reason, "detail": detail or {}})
        return self

    def __repr__(self):
        return (f"<Parse {self.doc_id} {'ok' if self.ok else 'fail'} "
                f"failures={[f['kind'] for f in self.failures]}>")


def _image_gate(doc_id, summarize):
    """이미지 요약(LLM 지점 ④)의 mock 허용 여부 — **판독을 한 자리에 모은다**.

    파서는 `core/`를 import하지 않으므로(P1) 여기서 환경변수를 직접 읽는다 —
    `USE_MOCK`은 런타임 계약이고 층 어휘가 아니라서 B1을 건드리지 않는다.
    MOCK이 실제로 도는 자리는 **로그로 남긴다**(문서 7 §7.8 3종 중 하나) — 표준출력으로만
    나가면 자동 점검이 세지 못해 비어 있는 지점이 구현된 것으로 보고된다.
    """
    mock = os.environ.get("USE_MOCK", "1") == "1"
    if mock and summarize is None:
        logging.getLogger("onto.parser").info(
            "MOCK ④이미지 요약 [%s] — 고정 문자열 + meta.image_summary_source=mock", doc_id)
    return mock


def _map_hook(doc_id, kept=None, made=None):
    """어댑터에 주입할 지도 패스 — **코어가 소유한다**(어댑터는 LLM을 부르지 않는다).

    `kept`는 보존분의 프레임별 지도(`{key: smap}`), `made`는 이번 인입에서 새로
    산출된 것을 담을 자리다. **한 문서가 여러 프레임(시트·슬라이드)을 가지므로 지도는
    프레임 키로 갈라 담는다** — 보존 파일은 문서 하나에 하나이고(§6.3), 그 안에서
    `maps[key]`로 나뉜다. 재사용은 호출부가 `source_hash`로 이미 판정한 뒤이므로
    여기서는 «있으면 쓴다»만 한다.
    """
    kept = kept or {}
    def hook(key, lines, locator):
        hit = kept.get(key)
        if hit is not None:
            return hit
        smap = struct_map.apply(f"{doc_id}:{key}", lines, locator)
        if made is not None:
            made[key] = smap
        return smap
    return hook


def parse(adapter, doc_id, path, *, layer="process", revision="R1",
          context=None, closed_list=None, parsed_at="2026-01-05T00:00:00",
          summarize=None, pick_coord=None, max_rows=None, progress=None):
    """문서 하나를 계약 JSON으로. 어댑터는 모듈(또는 ADAPTER+extract를 가진 객체).

    `summarize(image_ref) -> str`은 **이미지 요약 실호출 경로**다(LLM 지점 ④).
    주입되지 않으면 USE_MOCK=1에서는 고정 문자열, USE_MOCK=0에서는 명시적 실패다 —
    판단은 `_image_gate()`가 하고 `tagger.complete_images`는 계약만 지킨다.
    """
    res = ParseResult(doc_id)
    a = adapter.ADAPTER
    exp = a.get("expects") or {}

    raw = read(path)
    # **부분 리허설** — 등록 검수의 리허설 파싱을 앞 N행으로 제한한다(2B ⑥-2).
    # 전량 파싱은 좌표 미스 행마다 LLM을 부르므로 수천 행이면 몇 시간이다.
    # `reader.head`가 이미 「앞 N행」의 정의를 갖고 있어 그것을 그대로 쓴다 —
    # 자르는 규칙이 둘이면 「앞 200행」이 자리마다 다른 뜻이 된다.
    # **봉투에 잘랐다는 사실을 싣는다**: 검수 뷰가 그것을 승인 근거로 표시한다.
    full_rows = max((s.get("max_row") or 0) for s in raw["sheets"]) if raw.get("sheets") \
        else len(raw.get("slides") or [])
    truncated = False
    if max_rows and full_rows > max_rows:
        raw = head(raw, max_rows)
        truncated = True
    res.report["rehearsal"] = {"max_rows": max_rows, "full_rows": full_rows,
                               "truncated": truncated}

    # 지도와 이미지 요약은 **같은 보존 규칙**을 탄다(문서 6 §6.3) — 매 인입 새로
    # 부르면 text가 흔들려 그 문서의 chunk_id가 전량 이동한다.
    # **원본 파일 바이트 해시**로 재사용을 판정한다 — `doc_hash`는 에이전트 소유라
    # 파싱 시점에는 아직 없다(2A P-D 허브 판정 · §2.7-①).
    src_hash = struct_map.source_hash(path)
    kept_map = struct_map.load_kept(doc_id, src_hash) or {}
    kept_maps = dict(kept_map.get("maps") or {})
    made_maps = {}

    ok, detail = preflight.check(adapter, raw)                       # ② preflight
    if not ok:
        return res.fail("adapter_mismatch",
                        f"양식 표류 — 어댑터 '{a['doc_type']}' v{a.get('adapter_version')}",
                        detail)

    try:                                                             # ③ extract
        if a.get("payload_kind") == "prose":
            try:
                pieces = adapter.extract(
                    raw, struct_map_fn=_map_hook(doc_id, kept_maps, made_maps))
            except TypeError:
                pieces = adapter.extract(raw)                        # 지도 훅 없는 어댑터
        else:
            pieces = adapter.extract(raw)
    except Exception as e:                                           # C14 — 통째 실패
        return res.fail("parse_failure", f"{type(e).__name__}: {e}")

    pieces, rep = normalizer.normalize(                               # ④ normalizer
        pieces,
        multi_fields=[exp["multi_value_field"]] if exp.get("multi_value_field")
        else list(exp.get("multi_value_fields") or []),
        seps=exp.get("multi_value_seps") or (
            [exp["multi_value_sep"]] if exp.get("multi_value_sep") else None))
    res.report["normalizer"] = rep

    nodes = closed_list if closed_list is not None else tagger.closed_list(layer)
    # 지도와 이미지 요약은 **같은 보존 규칙**을 탄다(문서 6 §6.3) — 매 인입 새로
    # 부르면 text가 흔들려 그 문서의 chunk_id가 전량 이동한다.
    # **원본 파일 바이트 해시**로 재사용을 판정한다 — `doc_hash`는 에이전트 소유라
    # 파싱 시점에는 아직 없다(2A P-D 허브 판정 · §2.7-①).
    kept_img = dict(kept_map.get("image_summaries") or {})
    pieces = tagger.complete_images(pieces, summarize,               # ⑤ tagger
                                    allow_mock=_image_gate(doc_id, summarize),
                                    kept=kept_img)
    # 보존은 **새로 산출된 것이 있을 때만** 쓴다 — 매번 쓰면 재사용 갈래에서도 파일
    # mtime이 흔들려 «재사용했나»가 파일로 판정되지 않는다.
    fresh = {}
    if made_maps:
        fresh["maps"] = {**kept_maps, **made_maps}
    if kept_img and kept_img != (kept_map.get("image_summaries") or {}):
        fresh["image_summaries"] = kept_img
    if fresh:
        struct_map.keep(doc_id, {**kept_map, "doc_id": doc_id, **fresh}, src_hash)
    # **section에서 좌표를 먼저 세운다**(B43 ④) — 산문의 헤딩 경로가 골격 이름이면
    # 그것이 좌표다. 태깅보다 앞에 두는 이유: 태깅은 좌표가 **있는** 조각을 다듬고,
    # 이것은 좌표가 **없는** 조각에 세운다. 순서가 바뀌면 pick이 헛돈다.
    pieces = tagger.coord_from_section(pieces, layer=layer, nodes=nodes)
    pieces = tagger.tag(pieces, layer=layer, nodes=nodes, pick=pick_coord,
                        doc_type=a["doc_type"], progress=progress)

    # 지도 폴백은 실패가 아니라 **표시**다(D-5) — 문서는 들어가고 큐가 뜬다.
    unresolved = [p["source_locator"] for p in pieces
                  if (p.get("meta") or {}).get("hierarchy_unresolved")]
    if unresolved:
        res.fail("hierarchy_unresolved",
                 f"구조 미확정 {len(unresolved)}건 — 평면 폴백으로 실었다",
                 {"locators": unresolved[:10]})

    env = tagger.envelope(adapter, doc_id, path, pieces, revision=revision,
                          parsed_at=parsed_at, parser_version=PARSER_VERSION,
                          context=context)
    ok, defects = validator.check(env)                               # ⑥ validator
    if not ok:
        return res.fail("parse_failure", "계약 self-check 실패 (문서 단위 — C14)",
                        {"defects": defects})
    # 좌표의 목록 대조는 **보고**다 — 목록 밖 이름의 판정은 인입 소관(orphan_anchor).
    res.report["coords"] = validator.coord_report(env, nodes)

    res.ok, res.envelope = True, env
    res.report["pieces"] = len(pieces)
    return res
