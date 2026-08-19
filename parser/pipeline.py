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

from . import normalizer, preflight, struct_map, tagger, validator
from .reader import read

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


def _map_hook(doc_id):
    """어댑터에 주입할 지도 패스 — **코어가 소유한다**(어댑터는 LLM을 부르지 않는다)."""
    def hook(key, lines, locator):
        return struct_map.apply(f"{doc_id}:{key}", lines, locator)
    return hook


def parse(adapter, doc_id, path, *, layer="process", revision="R1",
          context=None, closed_list=None, parsed_at="2026-01-05T00:00:00"):
    """문서 하나를 계약 JSON으로. 어댑터는 모듈(또는 ADAPTER+extract를 가진 객체)."""
    res = ParseResult(doc_id)
    a = adapter.ADAPTER
    exp = a.get("expects") or {}

    raw = read(path)

    ok, detail = preflight.check(adapter, raw)                       # ② preflight
    if not ok:
        return res.fail("adapter_mismatch",
                        f"양식 표류 — 어댑터 '{a['doc_type']}' v{a.get('adapter_version')}",
                        detail)

    try:                                                             # ③ extract
        if a.get("payload_kind") == "prose":
            try:
                pieces = adapter.extract(raw, struct_map_fn=_map_hook(doc_id))
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
    pieces = tagger.complete_images(pieces)                           # ⑤ tagger
    pieces = tagger.tag(pieces, layer=layer, nodes=nodes)

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
