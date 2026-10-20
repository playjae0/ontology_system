# -*- coding: utf-8 -*-
"""G6 — **재생 때 불확실은 2차를 한 번** — 2차 기록이 없는 불확실 행만 청크 문장으로 다시 · 기록이 남으면 다음은 LLM 0 (B127 ①②).

대표 사례 하나(가벼운 회차 · 창작 표본 — 수치는 근거가 아니다 [정정] 50) · 가짜 게이트웨이(실호출 갈래 — 판정 지시문 · 후보 · 계약은
실물). 「B123 전의 대장」은 2차를 끈 첫 인입(`judge_context_chars` 0)으로 만든다:
  ⓐ 2차 기록이 없는 불확실 → 재생에서 2차 한 번 → 매칭이면 그 노드(새 노드 · 큐 0) · 기록이 남는다 · 수가 부른 수와 같다
  ⓑ 2차 기록이 있는 불확실 → 재생 LLM 0 · 불확실 그대로
  ⓒ 같은 상태로 한 번 더 재구축 → 판정 LLM 0
네 벌(ⓕ)은 마감 한 줄의 네 벌 단계가 잰다(mock 판정은 문장을 읽지 않아 2차 0).
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done   # noqa: F401

from fake_gateway import CALLS, Live                     # noqa: E402
from g6_common import _register, _unregister             # noqa: E402
import run as RUN                                        # noqa: E402
from core import matcher as M                            # noqa: E402
from core.build import ledger as LG, replay as RP        # noqa: E402

DID = "B127J"
_TEXT = {"S1": "노칭 정밀도는 금형 클리어런스로 정한다.", "S2": "앞서 말한 노칭 정밀도, 줄여서 정밀도는 매일 잰다.",
         "S3": "피치는 2mm로 둔다."}
_ENTS = {_TEXT["S1"]: "노칭 정밀도", _TEXT["S2"]: "정밀도", _TEXT["S3"]: "피치"}
ENV = {"source_path": "(합성) B127J.pptx", "revision": "R1", "parsed_at": "2026-10-20T00:00:00", "parser_version": "m",
       "adapter_version": "m", "context": {}, "payload_kind": "prose", "doc_type": "b127_live", "doc_id": DID,
       "chunks": [{"source_locator": k, "doc_type": "b127_live", "process_group": "조립", "process_ref": "노칭",
                   "electrode_type": "both", "text": t, "section": f"슬라이드 {i}", "meta": {}}
                  for i, (k, t) in enumerate(_TEXT.items(), 1)]}


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


def _extract(body):
    text = body["chunk"].split("\n", 1)[-1] if body["chunk"].startswith("[") else body["chunk"]
    return {"entities": [{"surface": _ENTS[text], "category": "Property", "parent": None, "belongs_to": None,
                          "value": None}], "relations": [], "about": []}


def _judge(body):
    """가짜 판정(창작): 1차는 늘 불확실 · 2차는 문장이 후보 이름(접두 뺀)을 글로 말하면 그 후보."""
    cands = body["candidates"]
    if "context" in body:
        hit = next((c for c in cands if c["canonical"].split("::")[-1] in body["context"]
                    and c["canonical"].split("::")[-1] != body["mention"].split("::")[-1]), None)
        if hit:
            return {"type": "match", "matched_id": hit["id"], "confidence": 0.95}
    return {"type": "uncertain", "matched_id": cands[0]["id"] if cands else None, "confidence": 0.5}


def _run():
    """기본 fresh(재구축의 바닥 — 판정 대장 · 추출이 남는다) → 다시 인입(재생) · 돌려주는 것은 판정 호출 본문들."""
    with _quiet():
        init.init(fresh_=True)                            # 시험 대상: 기본 fresh — 재구축의 바닥(판정 대장 · 추출이 남는다)
        RUN.cmd_bootstrap([])
    RP.reset()
    CALLS.clear()
    with Live(by={"extract": _extract, "judge": _judge, "outline": lambda b: {"headings": []},
                  "reinforce": lambda b: {"pick": None}}), _quiet():
        run_document(dict(ENV))
    return [b for p, b in CALLS if p == "judge"]


def _row(surface):
    return next((r for r in (LG.read(DID) or {}).get("rows") or []
                 if r.get("role") == "entity" and r.get("surface") == surface), {})


with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register("process", "b127_live")
_k0, M.JUDGE_CONTEXT_CHARS = M.JUDGE_CONTEXT_CHARS, 0     # B123 전의 대장 — 불확실 행에 2차 기록이 없다
with Live(by={"extract": _extract, "judge": _judge, "outline": lambda b: {"headings": []},
              "reinforce": lambda b: {"pick": None}}), _quiet():
    run_document(dict(ENV))
M.JUDGE_CONTEXT_CHARS = _k0
_before = (_row("정밀도").get("verdict"), _row("정밀도").get("judge2"), _row("피치").get("verdict"))

print("\n■ ⓐ 재생의 불확실 — 2차 기록이 없으면 한 번")
_j1 = _run()
_r = _row("정밀도")
_q = [q for q in q_of("uncertain_match", DID) if (q.get("payload") or {}).get("surface") == "정밀도"]
show("ⓐ 2차 기록 없는 불확실 → 재생에서 2차 한 번(문장 붙은 호출만) → 매칭이면 그 노드(새 노드 · 큐 0) · 기록이 남는다 · 수 = 부른 수",
     _before == ("uncertain", None, "uncertain") and _r.get("verdict") == "match" and _r.get("target") == "노칭::노칭 정밀도"
     and (_r.get("judge2") or {}).get("replay") and (_r.get("judge2") or {}).get("now") == "match"
     and node_by("process", "노칭::정밀도") is None and not _q
     and _j1 and all("context" in b for b in _j1) and RP.DOC["2차"] == len(_j1) and RP.DOC["2차 바뀜"] == 1,
     f"전 {_before} · 뒤 {_r.get('verdict')} → {_r.get('target')} · 2차 {_r.get('judge2')} · 호출 {len(_j1)} · 재생 {dict(RP.DOC)}")

print("\n■ ⓑ 2차 기록이 있는 불확실 · ⓒ 한 번 더 재구축")
_j2 = _run()
show("ⓑ 2차 기록이 있는 불확실(피치) → 재생 LLM 0 · 불확실 그대로 · 기록은 행에 남는다",
     _row("피치").get("verdict") == "uncertain" and (_row("피치").get("judge2") or {}).get("now") == "uncertain"
     and not [b for b in _j2 if b.get("mention", "").endswith("피치")],
     f"피치 {_row('피치').get('verdict')} · 2차 {_row('피치').get('judge2')}")
show("ⓒ 같은 상태로 한 번 더 재구축 → 판정 LLM 0 · 같은 붙음",
     not _j2 and _row("정밀도").get("target") == "노칭::노칭 정밀도" and RP.DOC["2차"] == 0,
     f"판정 호출 {len(_j2)} · 재생 {dict(RP.DOC)}")
RP.OFF, RP.COUNT_ALL = None, False
_unregister("b127_live")

done()
