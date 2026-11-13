# -*- coding: utf-8 -*-
"""G6 — **다듬기** — 잘리지 않는 md 보고서 · 붙은 자리 칸에 관계 · 불확실만 청크 문장을 보고 다시 판정 (B123).

대표 사례 하나씩(가벼운 회차 · 창작 표본 — 수치는 근거가 아니다 [정정] 50):
  ⓐ md — 산문 표본(TW 꼴 · mock 힌트) 하나의 `export/report_<id>.md`: 값 표 행 수 = 대장 개체 행 · 잘린 칸 0 ·
     카테고리 쌍별 수의 합 = 그 문서 몫 엣지(`show summary`의 문서 줄과 같은 셈)
  ⓑ 칸 — 같은 표본: 붙은 자리 칸이 관계 이름으로 시작한다 · 연결이 하나인 행은 `└` 줄 0 · 둘 이상인 행만 연결마다 한 줄
  ⓒ 2단 — 가짜 게이트웨이(실호출 갈래 · 판정 지시문 · 후보 · 계약은 실물): 1차 불확실 → 2차(청크 문장)로 매칭 · 2차도
     불확실이면 지금 동작(신규 + `uncertain_match`) · 2차는 1차 불확실에만 · 재구축(기본 fresh → 다시 인입 · 재생) 판정 LLM 0
네 벌(ⓓ)은 마감 한 줄의 네 벌 단계가 잰다(mock 판정은 문장을 읽지 않아 2차 0).
B181(같은지 판단 한 계약 — 가짜 게이트웨이 · PFMEA 꼴 표 사본 셋 행) ⓐ 세 곳이 같은 함수 · 정의문 · 값의 경로 ⓑ 닫힌 분류 같다 → 해소 ·
표기 대장 · 애매 → 보류 후보 ⓒ 표 개체의 다시 묻기 = 같은 행의 다른 칸 ⓓ 손잡이 둘 · 층 config 옛 키 ⓔ 곳별 수치 = 대장 행에서 센 수.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done   # noqa: F401

from fake_gateway import CALLS, Live                     # noqa: E402
from g6_common import _register, _unregister             # noqa: E402
from openpyxl import Workbook                            # noqa: E402
import run as RUN                                        # noqa: E402
from cli import ingest as IG, ingest_screen as SCR, report_md as MD, show_summary as SS   # noqa: E402
from core.build import ledger as LG, replay as RP, structure as ST   # noqa: E402
from parser import pipeline, struct_map, tuning          # noqa: E402
from parser.adapters import basic_prose_xlsx as BX       # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="b123_"))
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


# ────────────────────────────────────────────────────────────── ⓒ 2단 판정 (가짜 게이트웨이)
print("\n■ ⓒ 2단 판정 — 불확실만 청크 문장을 보고 다시")
_TEXT = {"S1": "노칭 정밀도는 금형 클리어런스로 정한다.", "S2": "앞서 말한 노칭 정밀도, 줄여서 정밀도는 매일 잰다.",
         "S3": "피치는 2mm로 둔다."}
_ENTS = {_TEXT["S1"]: "노칭 정밀도", _TEXT["S2"]: "정밀도", _TEXT["S3"]: "피치"}
ENV = {"source_path": "(합성) B123J.pptx", "revision": "R1", "parsed_at": "2026-10-19T00:00:00", "parser_version": "m",
       "adapter_version": "m", "context": {}, "payload_kind": "prose", "doc_type": "b123_live", "doc_id": "B123J",
       "chunks": [{"source_locator": k, "doc_type": "b123_live", "process_group": "조립", "process_ref": "노칭",
                   "electrode_type": "both", "text": t, "section": f"슬라이드 {i}", "meta": {}}
                  for i, (k, t) in enumerate(_TEXT.items(), 1)]}


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


def _live():
    return Live(by={"extract": _extract, "judge": _judge, "outline": lambda b: {"headings": []},
                    "reinforce": lambda b: {"pick": None}})


def _row(surface):
    return next((r for r in (LG.read("B123J") or {}).get("rows") or []
                 if r.get("role") == "entity" and r.get("surface") == surface), {})


with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register("process", "b123_live")                         # 실호출 갈래에서는 내장(mock) 종류가 숨는다 — 등록 단에
with _live(), _quiet():
    run_document(dict(ENV))
_judged = [b for p, b in CALLS if p == "judge"]
_r2, _r3 = _row("정밀도"), _row("피치")
_sp = (_r2.get("judge2") or {}).get("span") or [0, 0]
show("ⓒ 1차 불확실 → 2차(그 표기가 나온 청크 문장)로 매칭 · 2차도 불확실이면 신규 + uncertain_match · 2차는 불확실에만",
     _r2.get("verdict") == "match" and _r2.get("target") == "노칭::노칭 정밀도"
     and _r2["judge2"]["was"] == "uncertain" and _r2["judge2"]["now"] == "match"
     and "정밀도" in _TEXT["S2"][_sp[0]:_sp[1]]
     and _r3.get("verdict") == "uncertain" and (_r3.get("judge2") or {}).get("now") == "uncertain"
     and q_of("uncertain_match", "B123J")
     and sum(1 for b in _judged if "context" in b) == 2 and not (_row("노칭 정밀도").get("judge2")),
     f"정밀도 {_r2.get('verdict')} → {_r2.get('target')} · 2차 {_r2.get('judge2')} · 피치 {_r3.get('verdict')} · "
     f"판정 호출 {len(_judged)}(문장 {sum(1 for b in _judged if 'context' in b)})")

with _quiet():
    init.init(fresh_=True)                                # 시험 대상: 기본 fresh — 재구축의 바닥(추출 · 판정 대장이 남는다)
    RUN.cmd_bootstrap([])
RP.reset()
with _live(), _quiet():
    run_document(dict(ENV))
_again = [p for p, _b in CALLS if p in ("judge", "extract")]
show("ⓒ 재구축(기본 fresh → 다시 인입) — 최종 판정을 재생(판정 · 추출 LLM 0 · 같은 붙음)",
     not _again and _row("정밀도").get("target") == "노칭::노칭 정밀도" and _row("피치").get("verdict") == "uncertain",
     f"호출 {_again} · 정밀도 → {_row('정밀도').get('target')} · 재생 {dict(RP.DOC)}")
RP.OFF, RP.COUNT_ALL = None, False
_unregister("b123_live")

# ────────────────────────────────────────────────────────────── ⓐ md · ⓑ 칸 (mock 힌트)
print("\n■ ⓐ md 보고서 · ⓑ 붙은 자리 칸")
DT, DID, SHEET = "b123_process", "B123TW", "TW 사양"
ROWS = ["언와인더 unit", "1) 기본사양", "속도는 100ppm이다.", "2) 지정사양", "장력은 30N이다.",
        "리와인더 unit", "1) 기본사양", "속도는 80ppm이다."]
STRUCT = [{"text": "언와인더 unit", "depth": 1, "role": "대상", "name": "언와인더 unit", "category": "Unit"},
          {"text": "1) 기본사양", "depth": 2, "role": "묶음"}, {"text": "2) 지정사양", "depth": 2, "role": "묶음"},
          {"text": "리와인더 unit", "depth": 1, "role": "대상", "name": "리와인더 unit", "category": "Unit"},
          {"text": "1) 기본사양", "depth": 2, "role": "묶음"}]
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register("process", DT)
tuning.apply({"chunk_rows": [1, 2]})
_wb = Workbook()
_wb.remove(_wb.active)
_ws = _wb.create_sheet(title=SHEET)
for _i, _v in enumerate(ROWS, 1):
    _ws.cell(row=_i, column=1, value=_v)
_xp = TMP / f"{DID}.xlsx"
_wb.save(_xp)
(HINTS / f"{DID}@structure.json").write_text(json.dumps({SHEET: STRUCT}, ensure_ascii=False), encoding="utf-8")
_env = pipeline.parse(BX, DID, str(_xp), closed_list=[], sheet_roles={SHEET: "prose"},
                      structure=ST.structurer()).envelope
_hints = {}
for _c in _env["chunks"]:
    _own = next((x for x in reversed(_c["meta"].get("structure") or []) if x.get("name")), None)
    _ents = [{"surface": w, "category": "Property",
              "belongs_to": {"name": _own["name"], "category": "Unit", "from": "제목"} if _own else None}
             for w in ("속도", "장력") if w + "은" in _c["text"] or w + "는" in _c["text"]]
    # 둘째 연결(창작) — 언와인더의 장력 청크가 리와인더 unit과의 관계도 말한다(연결이 둘인 행)
    _rel = [{"src": "리와인더 unit", "rel": "has_property", "dst": "장력"}] if "장력은" in _c["text"] else []
    if _ents:
        _hints[_c["source_locator"]] = {"entities": _ents, "relations": _rel, "attach": []}
(HINTS / f"{DID}.json").write_text(json.dumps(_hints, ensure_ascii=False), encoding="utf-8")
struct_map.invalidate(DID)
with _quiet():
    IG.ingest_file(str(_xp), DT, ask=False, sheets="1:prose", coord="노칭")

_data = LG.read(DID) or {}
_ent = [r for r in _data.get("rows") or [] if r.get("role") == "entity"]
_mdp = MD.write(DID, _data)
_md = _mdp.read_text(encoding="utf-8")
_vals = _md.split("## 판정 값", 1)[-1]
_vrows = [ln for ln in _vals.splitlines() if ln.startswith("| ") and not ln.startswith("| # |")]
from core.state.bootstrap import open_graph                 # noqa: E402
from router import discover                                 # noqa: E402
_graphs = {lay: open_graph(lay) for lay in discover()}
_pairs = MD.pair_counts(_graphs, DID, _data.get("rows") or [])
show("ⓐ md — 값 표 행 = 대장 개체 행 · 잘린 칸 0 · 카테고리 쌍별 수의 합 = 그 문서 몫 엣지(show summary와 같은 셈)",
     _ent and len(_vrows) == len(_ent) and "…" not in _vals and sum(_pairs.values()) == SS._mine(_graphs, DID)[1] > 0
     and _mdp.name == f"report_{DID}.md" and _mdp.parent == _P.export(),
     f"값 행 {len(_vrows)}/{len(_ent)} · 쌍 {dict(_pairs)} · 엣지 {SS._mine(_graphs, DID)[1]} · {_mdp.name}")

_keep_loud, _cols = SCR._loud, os.environ.get("COLUMNS")
SCR._loud, os.environ["COLUMNS"] = (lambda r: True), "220"
_keep_v = SCR._screen.VERBOSE
SCR._screen.VERBOSE = True                                  # 값 줄 · └ 줄은 -v일 때만(고침 B199 ①)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _pr = SCR.row_printer(_env)
    for _r in _ent:
        _pr(_r)
    _pr.flush(None)
SCR._loud = _keep_loud
SCR._screen.VERBOSE = _keep_v
if _cols is None:
    os.environ.pop("COLUMNS", None)
else:
    os.environ["COLUMNS"] = _cols
LG.ON_CHUNK = None
# 기대 변경(B150 ① — 인입 화면은 붙은 자리를 칸이 아니라 조각 부착 때 └ 줄로 연결마다 · 칸(md 보고서 · value_cells)은 관계 상대(방식) 그대로)
_tree = [ln for ln in _buf.getvalue().splitlines() if re.match(r"\s+└ ", ln) and "└ 소속" not in ln]
_multi = [r for r in _ent if len(r.get("attached") or []) > 1]
_stuck = [SCR.value_cells(r, {}, {})[0][SCR.VALUE_HEADS.index("붙은 자리")] for r in _ent if r.get("attached")]
show("ⓑ 붙은 자리 칸(md) = 관계 상대(방식) · 인입 화면의 └ 줄은 연결마다 한 줄(조각 부착 때)",
     _multi and len(_tree) == sum(len(r.get("attached") or []) for r in _ent)
     and all(s.startswith(r["attached"][0]["rel"] + " ") for s, r in zip(_stuck, [r for r in _ent if r.get("attached")])),
     f"└ 줄 {len(_tree)} · 연결 {sum(len(r.get('attached') or []) for r in _ent)} · 칸 {_stuck[:2]}")

for _p in (HINTS / f"{DID}.json", HINTS / f"{DID}@structure.json", HINTS / f"{DID}@outline.json"):
    _p.unlink(missing_ok=True)
_unregister(DT)                                            # 등록 단은 클린이 남긴다 — 시험 몫을 치운다

# ────────────────────────────────────────────────────────────── B181 같은지 판단 한 계약 (가짜 게이트웨이 · 창작 표본)
print("\n■ B181 — 세 곳(골격 칸 · 닫힌 분류 · 개체)이 같은 판단 함수 · 같은 재료 · 애매면 원문으로 한 번 더 · 손잡이 · 곳별 수치")
from core import matcher as MT                                   # noqa: E402
from core.build import reconcile as RC                            # noqa: E402
from core.llm import gateway, points as PT                        # noqa: E402
from core.state import knobs as KN, store as STO, surface_book as SB   # noqa: E402
from core.state.bootstrap import COORD_CATEGORY, coord_layer      # noqa: E402
from parser import tagger as TG                                   # noqa: E402
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
D181 = "b181_pfmea"
_sp = _P.schemas(f"{D181}.json")
_P.ensure(_sp)
_sp.write_text(json.dumps({**json.loads(_P.fixture_schemas("pfmea.json").read_text(encoding="utf-8")),
                           "doc_type": D181}, ensure_ascii=False), encoding="utf-8")
_dts = STO.read(STO.DOC_TYPES, {})
_dts[D181] = {"doc_type": D181, "status": "registered", "layer": "quality", "schema": f"schemas/{D181}.json",
              "adapter": "parser/adapters/basic_prose_xlsx.py", "schema_version": 1}
STO.write(STO.DOC_TYPES, _dts)
_SEEN = []
_judge0 = MT.judge


def _spy(surface, pool, category, cfg=None, **kw):
    _SEEN.append((kw.get("point") or "judge", category))
    return _judge0(surface, pool, category, cfg, **kw)


def _fake181(body):
    """가짜 판단(창작) — 표기마다 정한 답 · 다시 묻기(context)여도 같은 답(바뀜 0)."""
    by = {c["canonical"]: c["id"] for c in body["candidates"]}
    m = body["mention"]
    if m == "방전 불능":
        return {"type": "match", "matched_id": by.get("방전기능상실"), "confidence": 0.93}
    if m in ("노칭공정B", "노칭공정C"):                   # 다른 두 표기가 같은 골격 노드 — 판단은 둘(리뷰 #136 P2)
        return {"type": "match", "matched_id": by.get("노칭"), "confidence": 0.9}
    if m in ("발화", "노칭공정A", "노칭::장력 과다"):
        return {"type": "uncertain", "matched_id": next(iter(by.values()), None), "confidence": 0.75}
    return {"type": "new", "matched_id": None, "confidence": 0.9}


_b181 = {"doc_type": D181, "process_group": "조립", "electrode_type": "both", "severity": 5}
_recs = [dict(_b181, source_locator="R1", process_ref="노칭", failure_mode="탭 찢김", cause="장력 과다",
              effect_category="방전 불능"),
         dict(_b181, source_locator="R2", process_ref="노칭", failure_mode="탭 찢김", cause="장력 과다", effect_category="발화"),
         dict(_b181, source_locator="R3", process_ref="노칭공정A", failure_mode="버 발생", cause="금형 마모",
              effect_category="외관 손상"),
         dict(_b181, source_locator="R4", process_ref="노칭공정B", failure_mode="버 발생", cause="금형 마모",
              effect_category="단락"),
         dict(_b181, source_locator="R5", process_ref="노칭공정C", failure_mode="버 발생", cause="금형 마모",
              effect_category="단락")]
MT.judge = _spy
try:
    with Live(by={"judge": _fake181, "coord_tag": _fake181}), _quiet():
        _tg = TG.tag(_recs, layer=coord_layer(), pick=PT.coord_picker(), doc_type=D181, doc_id="B181P")
        say_new_env({"doc_id": "B181P", "payload_kind": "table", "records": _tg})   # 사람이 「새로」(고침 B196 ① — 문)
        run_document({"doc_id": "B181P", "doc_type": D181, "source_path": "(합성) B181P.xlsx", "revision": "R1",
                      "parsed_at": "2026-11-05T00:00:00", "parser_version": "m", "adapter_version": "m", "context": {},
                      "payload_kind": "table", "records": _tg})
finally:
    MT.judge = _judge0
_bodies = {(pt, b["category"]): b for pt, b in CALLS if "category" in b and "context" not in b}
_three = [("coord_tag", COORD_CATEGORY), ("judge", "FailureEffect"), ("judge", "Failure")]
show("ⓐ 세 곳(골격 칸 · 닫힌 분류 · 개체)의 판단 입력에 정의문 · 값의 경로가 있고 같은 판단 함수(matcher.judge)를 지난다",
     all(k in _bodies and _bodies[k].get("definition") and _bodies[k].get("path") for k in _three)
     and set(_three) <= set(_SEEN),
     " · ".join(f"{pt}/{c} 경로 {(_bodies.get((pt, c)) or {}).get('path')}" for pt, c in _three))
_rows181 = (LG.read("B181P") or {}).get("rows") or []
_q181 = {(x.get("payload") or {}).get("surface"): x["payload"] for x in STO.read(STO.QUEUE, [])
         if x.get("doc_id") == "B181P" and x["kind"] == "orphan_anchor"}
_bk = [e for e in SB.entries() if e.get("표기") == "방전 불능"]
_r1 = next((r for r in _rows181 if r.get("field") == "effect_category" and r.get("surface") == "방전 불능"), {})
show("ⓑ 사전에 없는 닫힌 분류 표기 — 같다면 해소 · 표기 대장(닫힌 분류 · 기계 판단) · 애매면 보류 큐 payload에 후보 · "
     "파서가 행에 단 표지(meta)는 스키마 밖 필드가 아니다(고침 리뷰 #136 · 골격 칸 애매는 B182 ⓑ — 잠정 + 합칠 후보)",
     _r1.get("canonical") == "방전기능상실" and _r1.get("verdict") == "anchor"
     and any(e["곳"] == SB.CLOSED and e["지위"] == SB.MACHINE for e in _bk)
     and ((_q181.get("발화") or {}).get("judge") or {}).get("candidates")
     and not [x for x in STO.read(STO.QUEUE, []) if x.get("doc_id") == "B181P" and x["kind"] == "unknown_field"],
     f"방전 불능 → {_r1.get('canonical')} · 대장 {[(e['곳'], e['지위']) for e in _bk]} · 발화 {(_q181.get('발화') or {}).get('judge')}")
_ctx = [b for pt, b in CALLS if pt == "judge" and b.get("category") == "Failure" and "context" in b]
show("ⓒ 표 개체가 애매면 같은 행의 다른 칸(판단하는 칸은 뺀다)을 원문으로 한 번 더 묻는다 · mock은 원문을 읽지 않는다(0)",
     len(_ctx) == 1 and "failure_mode: 탭 찢김" in _ctx[0]["context"] and "cause:" not in _ctx[0]["context"]
     and "second" not in MT.second("x", [{"id": "a", "canonical": "a", "category": "Failure"}], "Failure", None,
                                   {"type": MT.UNCERTAIN, "matched_id": None, "confidence": 0.5}, {"text": "원문", "span": []}),
     (_ctx[0]["context"] if _ctx else "다시 묻기 0"))
_jc = RC.judge_counts(_rows181)
_cl = [r for r in _rows181 if r.get("place") == SB.CLOSED]
_cl1 = list({r["surface"]: r for r in _cl}.values())
_en = [r for r in _rows181 if r.get("role") == "entity" and str(r.get("path") or "").endswith("+judge")]
show("ⓔ 곳별 수치 줄의 수(확실도 구간 · 애매 · 다시 묻기)가 대장 행에서 센 수와 같다(닫힌 분류 · 개체 · 골격 칸 — 다른 두 표기가 "
     "같은 골격 노드로 붙어도 판단 둘 · 고침 리뷰 #136 P2)",
     _jc[SB.CLOSED]["같다"][9] == sum(1 for r in _cl1 if r["answer"] == "match" and r["confidence"] >= 0.9)
     and _jc[SB.CLOSED]["애매"] == sum(1 for r in _cl1 if r["answer"] == "uncertain")
     and _jc[SB.CLOSED]["다시"][0] == sum(1 for r in _cl1 if r.get("judge2"))
     and _jc[SB.ENTITY]["판단"] == len(_en) and _jc[SB.ENTITY]["다시"][0] == sum(1 for r in _en if r.get("judge2"))
     and _jc[SB.SKELETON]["애매"] == 1 and _jc[SB.CLOSED]["근처"]
     and _jc[SB.SKELETON]["판단"] == len({r["asked"] for r in _rows181 if r.get("place") == SB.SKELETON}) == 3
     and sum(_jc[SB.SKELETON]["같다"]) == 2,
     " · ".join(f"{k} {v['판단']}/{v['애매']}/{v['다시']}" for k, v in _jc.items()))
_kp = _P.knobs()
_kp.write_text(json.dumps({"match_threshold": 0.95, "candidate_top_n": 3}), encoding="utf-8")
KN.apply()
_keep_chat = gateway.chat
gateway.chat = lambda *a, **k: {"type": "match", "matched_id": "a", "confidence": 0.93}
try:
    _v95 = MT.judge("x", [{"id": "a", "canonical": "a"}], "Failure")
finally:
    gateway.chat = _keep_chat
_cfgq = _P.layers("quality", "config.json")
_kq = _cfgq.read_bytes()
_out = {}
for _val in (0.95, 0.8):
    _cfgq.write_text(json.dumps({**json.loads(_kq), "match_threshold": _val}, ensure_ascii=False), encoding="utf-8")
    _b = io.StringIO()
    with contextlib.redirect_stdout(_b):
        _out[_val] = (RUN._moved_keys_gate(), _b.getvalue())
_n3 = MT.candidate_top_n()
_cfgq.write_bytes(_kq)
_kp.unlink()
KN.apply()
show("ⓓ knobs.json의 match_threshold · candidate_top_n이 판정에 닿는다 · 층 config 옛 키 — 손잡이 값과 같으면 한 줄(rc 0) · 다르면 멈춤(rc 1)",
     _v95["type"] == MT.UNCERTAIN and _n3 == 3 and MT.threshold() == MT.THRESHOLD and _out[0.95][0] == 0
     and "지워도 된다" in _out[0.95][1]
     and _out[0.8][0] == 1 and "[상태]" in _out[0.8][1],
     f"0.93 → {_v95['type']} · 같음 rc {_out[0.95][0]} · 다름 rc {_out[0.8][0]}")

# ────────────────────────────────────────────────────────────── B182 잠정 골격 노드 (창작 표본 · mock + 가짜 게이트웨이)
print("\n■ B182 — 골격 칸 값은 찾거나, 없으면 잠정 골격 노드로 선다(다르다 auto_node · 애매 합칠 후보 + uncertain_match)")
from core.build import provisional as PV                          # noqa: E402
from core.state.status import PROVISIONAL, is_live                # noqa: E402
from parser import normalizer as NZ                               # noqa: E402
from cli import rebuild as RB                                     # noqa: E402


def _pv(canon):
    """좌표 층의 그 canonical 산 노드(없으면 None)."""
    return next((n for n in open_graph(coord_layer()).nodes.values() if n["canonical"] == canon and is_live(n)), None)


def _up(n):
    """그 노드의 부모 canonical — 골격 자식 관계 엣지(seed · 잠정)."""
    g = open_graph(coord_layer())
    child = load_config(coord_layer())["skeleton"]["relations"]["child"]
    return next(((g.get(e["dst"]) or {}).get("canonical") for e in g.edges if e["src"] == n["id"] and e["rel"] == child), None)


def _doc(did, recs, pick=None):
    tg = TG.tag(recs, layer=coord_layer(), pick=pick, doc_type=D181, doc_id=did)
    say_new_env({"doc_id": did, "payload_kind": "table", "records": tg})        # 사람이 「새로」(고침 B196 ① — 문)
    with _quiet():
        run_document({"doc_id": did, "doc_type": D181, "source_path": f"(합성) {did}.xlsx", "revision": "R1",
                      "parsed_at": "2026-11-05T00:00:00", "parser_version": "m", "adapter_version": "m", "context": {},
                      "payload_kind": "table", "records": tg})
    return (LG.read(did) or {}).get("rows") or []


_na = _pv("노칭공정A")
_um = [x for x in STO.read(STO.QUEUE, []) if x.get("doc_id") == "B181P" and x["kind"] == "uncertain_match"
       and (x.get("payload") or {}).get(PROVISIONAL)]
show("B182 ⓑ 골격 칸 애매(대역 판단) — 잠정 골격 노드(표시 애매 · 합칠 후보 = 판단의 가장 가까운 후보) · uncertain_match 1",
     bool(_na) and _na[PROVISIONAL]["answer"] == "uncertain" and (_na[PROVISIONAL].get("near") or [None])[0] == "노칭"   # 후보 둘까지(고침 B196 ③)
     and len(_um) == 1 and _um[0]["payload"].get("nearest") == {"canonical": "노칭"},
     f"노칭공정A {(_na or {}).get(PROVISIONAL)} · uncertain_match {len(_um)}")

_c = {"doc_type": D181, "electrode_type": "both", "severity": 5, "failure_mode": "버 발생", "cause": "금형 마모"}
_rc = _doc("B182C", [dict(_c, source_locator="C1", process_group="노칭", process_ref="신공정X", effect_category="단락"),
                     dict(_c, source_locator="C2", process_group="조립", process_ref="신공정X", effect_category="단락"),
                     dict(_c, source_locator="C3", process_group="스태킹", process_ref="신공정X", effect_category="단락"),
                     dict(_c, source_locator="C4", process_group=None, process_ref="신공정Y", effect_category="단락"),
                     dict(_c, source_locator="C0", process_group="스태킹", process_ref="신공정Z", effect_category="단락"),
                     dict(_c, source_locator="C5", process_group="노칭::전극 언와인딩", process_ref="신공정Z",
                          effect_category="외관 손상X")])
_y0 = _pv("신공정Y")
_up0 = _up(_y0) if _y0 else "?"
_rc2 = _doc("B182C2", [dict(_c, source_locator="D1", process_group="패키징", process_ref="신공정Y", effect_category="단락")])
_an = {r["locator"]: r for r in _rc + _rc2 if r.get("role") == "anchor"}
_x, _sx = _pv("신공정X"), _pv("스태킹::신공정X")
_rm = _doc("B182M", [dict(_c, source_locator="M1", process_group="조립", process_ref="신공정W", effect_category="단락"),
                     dict(_c, source_locator="M2", process_group="노칭", process_ref="신공정W", effect_category="단락"),
                     dict(_c, source_locator="M3", process_group="노칭", process_ref="신공정V", effect_category="단락")])
_am = {r["locator"]: r for r in _rm if r.get("role") == "anchor"}
show("B182 ⓒ 같은 잠정 이름 — 같은 줄기의 부모면 같은 노드 · 다른 줄기면 `부모::이름` 따로 · 부모 미정 노드에 부모를 말하는 행이 "
     "오면 채운다(노드 수 그대로) · 사람이 「새로」를 고른 표기는 1행이어도 선다(고침 B196 ① · 손잡이 걷음 B197 ⑥)",
     bool(_x and _sx) and _up(_x) == "노칭" and _up(_sx) == "스태킹"
     and _an["C1"]["node_id"] == _an["C2"]["node_id"] == _x["id"] and _an["C3"]["node_id"] == _sx["id"]
     and _up0 is None and _an["D1"]["node_id"] == _an["C4"]["node_id"] == _y0["id"] and _up(_pv("신공정Y")) == "패키징"
     and _pv("신공정W") and _am["M1"]["node_id"] == _am["M2"]["node_id"] == _pv("신공정W")["id"]
     and _pv("신공정V") and _am["M3"]["node_id"] == _pv("신공정V")["id"],
     f"신공정X ← {_up(_x) if _x else '-'} · 스태킹::신공정X ← {_up(_sx) if _sx else '-'} · 신공정Y {_up0} → {_up(_pv('신공정Y')) if _y0 else '-'}")

_n0 = sum(len(open_graph(lay).nodes) for lay in ("process", "quality"))
_sug = TG.suggest_doc_coord("신공정Q_관리계획서.xlsx", TG.coord_list(coord_layer()))
_n1 = sum(len(open_graph(lay).nodes) for lay in ("process", "quality"))
_cm = TG.coord_from_section(NZ.blank_coords([{"source_locator": "K1", "process_ref": "전공정", "text": "x"}]),
                            layer=coord_layer(), doc_coord="노칭")
_qz = [x for x in STO.read(STO.QUEUE, []) if x.get("doc_id") == "B182C" and x["kind"] == "orphan_anchor"]
_cat = {(x["payload"].get("surface"), x["payload"].get("category")) for x in _qz}
show("B182 ⓔ 바꾸지 않는 것 — 닫힌 분류 목록 밖은 보류 · 파일명 제안은 노드 0 · 「전 공정」 좌표 칸은 문서 좌표 · 맨 아래 단 아래 "
     "자리는 보류 + 「골격 아래 새 단」(같은 이름이 다른 줄기 행에서 섰어도 그 행은 보류 — 리뷰 #137 P2)",
     ("외관 손상X", "FailureEffect") in _cat and _n0 == _n1 and not _pv("신공정Q") and _cm[0]["process_ref"] == "노칭"
     and ("신공정Z", COORD_CATEGORY) in _cat and _an["C5"].get("hold") == PV.HOLD_DEEP and _an["C5"].get("node_id") is None
     and _an["C0"]["node_id"] == (_pv("신공정Z") or {}).get("id"),
     f"보류 {sorted(_cat)} · 제안 {_sug} · 전공정 → {_cm[0]['process_ref']} · C5 {_an['C5'].get('hold')}")
_unregister(D181)

# ⓐ ⓕ ⓓ — mock 대표 사례(CP01 → PFMEA01) · 재구축 동치 · 다음 문서
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
say_new(("레이저노칭", "조립"))                    # 사람이 「새로」(고침 B196 ① — 문 · 같은 행 공정 그룹 칸이 들어온 자리)
for _f, _dt in (("CP01.xlsx", "cp"), ("PFMEA01.xlsx", "pfmea")):
    _quiet_r = _quiet()
    with _quiet_r:
        IG.ingest_file(str(_FXR.ROOT_DIR / "raw" / _f), _dt, ask=False)
_ln = _pv("레이저노칭")
_r16 = [r for r in (LG.read("PFMEA01") or {}).get("rows") or [] if str(r.get("locator")).endswith("R16")]
_an16 = next((r for r in _r16 if r.get("role") == "anchor"), {})
_e16 = [r for r in _r16 if r.get("role") == "entity"]
_auto = [x for x in STO.read(STO.QUEUE, []) if x["kind"] == "auto_node" and (x.get("payload") or {}).get("node_id") == (_ln or {}).get("id")]
_oa = [x for x in STO.read(STO.QUEUE, []) if x["kind"] == "orphan_anchor" and (x.get("payload") or {}).get("surface") == "레이저노칭"]
show("B182 ⓐ mock PFMEA01 R16 「레이저노칭」(목록 밖) — 잠정 골격 노드(좌표 카테고리 · auto + 잠정 · 부모 「조립」 = 같은 행 공정 그룹 칸 · "
     "auto_node 1) · 같은 행의 셋이 노드로 서고 · orphan_anchor에 그 표기 0",
     bool(_ln) and _ln["category"] == COORD_CATEGORY and _ln["status"] == "auto" and _ln.get(PROVISIONAL)
     and _up(_ln) == "조립" and len(_auto) == 1 and _an16.get("node_id") == _ln["id"]
     and {r["surface"] for r in _e16} >= {"슬리팅 버", "빔 출력 편차", "빔 출력"} and all(r.get("node_id") for r in _e16)
     and not _oa,
     f"레이저노칭 {(_ln or {}).get(PROVISIONAL)} ← {_up(_ln) if _ln else '-'} · auto_node {len(_auto)} · R16 개체 "
     f"{[(r['surface'], bool(r.get('node_id'))) for r in _e16]} · orphan {len(_oa)}")


def _shape():
    """그래프 모양 — 노드(canonical · 카테고리 · status · 단 · 잠정 표시) · 엣지(관계 · 양끝 canonical · status)."""
    out = set()
    for lay in ("process", "quality"):
        g = open_graph(lay)
        out |= {("n", lay, n["canonical"], n["category"], n.get("status"), n.get("tier"), str(n.get(PROVISIONAL)))
                for n in g.nodes.values() if is_live(n)}
        out |= {("e", e["rel"], (g.get(e["src"]) or {}).get("canonical"), (g.get(e["dst"]) or {}).get("canonical"),
                 e.get("status")) for e in g.edges}
    return out


_s0 = _shape()
CALLS.clear()
_rbc, _rbo = 0, ""
_b = io.StringIO()
with contextlib.redirect_stdout(_b):
    _rbc = RB.main(["--allow-mock", "--yes"], bootstrap=RUN.cmd_bootstrap, screen=RUN.fresh_screen)
_s1 = _shape()
show("B182 ⓕ 재구축 동치 — 기본 fresh → 다시 인입 · 같은 잠정 노드(부모 · 단 · 표시) · 같은 그래프 · LLM 0",
     _rbc == 0 and _s0 == _s1 and _pv("레이저노칭") and not CALLS,
     f"rc {_rbc} · 다른 것 {sorted(_s0 ^ _s1)[:4]} · 호출 {len(CALLS)}")

_pf = {"doc_type": "pfmea", "process_group": "조립", "electrode_type": "both", "severity": 5, "cause": "빔 흔들림",
       "effect_category": "단락"}
CALLS.clear()
_ask_seen = []


def _fake182(body):
    _ask_seen.append([c["canonical"] for c in body["candidates"]])
    return {"type": "new", "matched_id": None, "confidence": 0.9}


with Live(by={"coord_tag": _fake182}):
    _tg2 = TG.tag([dict(_pf, source_locator="N1", process_ref="레이저노칭", failure_mode="빔 끊김"),
                   dict(_pf, source_locator="N2", process_ref="레이저 커팅", failure_mode="빔 끊김")],
                  layer=coord_layer(), pick=PT.coord_picker(), doc_type="pfmea", doc_id="B182N")
say_new_env({"doc_id": "B182N", "payload_kind": "table", "records": _tg2})   # 사람이 「새로」(고침 B196 ① — 문)
with _quiet():
    run_document({"doc_id": "B182N", "doc_type": "pfmea", "source_path": "(합성) B182N.xlsx", "revision": "R1",
                  "parsed_at": "2026-11-05T00:00:00", "parser_version": "m", "adapter_version": "m", "context": {},
                  "payload_kind": "table", "records": _tg2})
_rn = {r["locator"]: r for r in (LG.read("B182N") or {}).get("rows") or [] if r.get("role") == "anchor"}
show("B182 ⓓ 다음 문서의 같은 표기는 좌표 태깅 목록에서 바로(LLM 0) 그 잠정 노드에 · 다른 표기의 판단 후보에 잠정 노드가 든다",
     _rn["N1"]["node_id"] == _pv("레이저노칭")["id"] and len(_ask_seen) == 1 and "레이저노칭" in _ask_seen[0]
     and _pv("레이저 커팅") is not None,
     f"N1 → {_rn['N1'].get('canonical')} · 판단 {len(_ask_seen)}회 · 후보에 레이저노칭 {'레이저노칭' in (_ask_seen or [[]])[0]}")

# ────────────────────────────────────────────────────────────── B183 자리 추정 (창작 표본 · 가짜 게이트웨이)
print("\n■ B183 — 자리를 아예 말하지 않은 값은 그 카테고리 노드 전체에서 같은 것이 하나일 때만 붙는다(자리 추정 — 유일 후보)")
from core.build import place_guess as PG                           # noqa: E402
from core.build import retry as RT                                 # noqa: E402
D183, _E183 = "b183_live", {}


def _x183(body):
    text = body["chunk"].split("\n", 1)[-1] if body["chunk"].startswith("[") else body["chunk"]
    return {"entities": [{"surface": s, "category": "Property", "parent": None, "belongs_to": None, "value": None}
                         for s in _E183.get(text, [])], "relations": [], "about": []}


def _p183(did, chunks, ref=None):
    """산문 문서 하나 → 마무리(재연결) · 개체 행 `{표기: 행}`. `ref`가 없으면 자리를 아예 말하지 않은 문서(공정 · 그룹 · 문서 좌표 0)."""
    for _k, t, ents in chunks:
        _E183[t] = ents
    env = {"source_path": f"(합성) {did}.pptx", "revision": "R1", "parsed_at": "2026-11-05T00:00:00", "parser_version": "m",
           "adapter_version": "m", "context": {}, "payload_kind": "prose", "doc_type": D183, "doc_id": did,
           "chunks": [{"source_locator": k, "doc_type": D183, "process_group": None, "process_ref": ref, "electrode_type": "both",
                       "text": t, "section": f"슬라이드 {i}", "meta": {}} for i, (k, t, _e) in enumerate(chunks, 1)]}
    with Live(by={"extract": _x183, "judge": lambda b: {"type": "new", "matched_id": None, "confidence": 0.9},
                  "outline": lambda b: {"headings": []}, "reinforce": lambda b: {"pick": None}}), _quiet():
        run_document(env)
        finalize()
    return {r["surface"]: r for r in (LG.read(did) or {}).get("rows") or [] if r.get("role") == "entity"}


def _pn(canon):
    return next((n for n in open_graph("process").nodes.values() if n["canonical"] == canon and is_live(n)), None)


def _mf(did):
    """그 문서의 빈 좌표 보류 재료 `{표기: 개체 재료}`(missing_field · 키 process_ref)."""
    return {d["surface"]: d for x in STO.read(STO.QUEUE, []) if x.get("doc_id") == did and x["kind"] == "missing_field"
            for e in (x.get("payload") or {}).get("items") or [x.get("payload") or {}] for d in e.get("dropped_entities") or []}


_register("process", D183)
_rp1 = _p183("B183P1", [("P1", "노칭 쪽 B183정밀도와 B183장력.", ["B183정밀도", "B183장력"])], ref="노칭")
_p183("B183P2", [("P2", "스태킹 쪽 B183장력.", ["B183장력"])], ref="스태킹")
_n0 = sum(len(open_graph(lay).nodes) for lay in ("process", "quality"))
CALLS.clear()
_ru = _p183("B183U", [("U1", "B183정밀도를 잰다.", ["B183정밀도"]), ("U2", "B183장력을 잰다.", ["B183장력"]),
                      ("U3", "B183피치를 잰다.", ["B183피치"])])
_n1 = sum(len(open_graph(lay).nodes) for lay in ("process", "quality"))
_j183 = [b.get("mention") for pt, b in CALLS if pt == "judge"]
_mu = _mf("B183U")
_np = _pn("노칭::B183정밀도")
show("B183 ⓐ 좌표가 모두 빈 산문에서 그래프에 하나뿐인 이름 — 그 노드에 붙는다(새 노드 0 · 출처 + 1 · 대장 경로 「자리 추정 — 유일 후보」) · "
     "그 값의 missing_field 0",
     _ru["B183정밀도"].get("path") == PG.PATH and _ru["B183정밀도"].get("target") == "노칭::B183정밀도" and _n1 == _n0
     and "B183U#U1" in _np["provenance"] and "B183정밀도" not in _mu,
     f"U1 {_ru['B183정밀도'].get('path')} → {_ru['B183정밀도'].get('target')} · 노드 {_n0} → {_n1}")
show("B183 ⓑ 같은 이름이 두 공정 줄기에 있는 값 — 보류 · payload 후보 둘 · 판단 LLM 0",
     not _ru["B183장력"].get("node_id") and (_mu.get("B183장력") or {}).get("guess", {}).get("why") == PG.MANY
     and _mu["B183장력"]["guess"]["candidates"] == ["노칭::B183장력", "스태킹::B183장력"] and "B183장력" not in _j183,
     f"U2 {(_mu.get('B183장력') or {}).get('guess')} · 판단 {_j183}")
_rp3 = _p183("B183P3", [("P3", "스태킹 쪽 B183정밀도와 B183피치.", ["B183정밀도", "B183피치"])], ref="스태킹")
_mu2 = _mf("B183U")
_ru2 = {r["surface"]: r for r in (LG.read("B183U") or {}).get("rows") or [] if r.get("role") == "entity"}
show("B183 ⓒ 깨질 때 — 같은 이름이 다른 공정 줄기에 서면 재연결이 그 출처를 걷고 보류(missing_field + 후보 둘) · 거꾸로 보류였던 값은 "
     "이름이 하나로 서면 붙는다(LLM 0)",
     "B183U#U1" not in _pn("노칭::B183정밀도")["provenance"] and not _pn("노칭::B183정밀도").get(PG.FIELD)
     and len((_mu2.get("B183정밀도") or {}).get("guess", {}).get("candidates") or []) == 2
     and _ru2["B183피치"].get("target") == "스태킹::B183피치" and "B183피치" not in _mu2
     and RT.LAST.get("guess") == {"되돌림": 1, "다시 붙음": 1},
     f"되돌림 · 다시 붙음 {RT.LAST.get('guess')} · U1 재료 {_mu2.get('B183정밀도')} · U3 → {_ru2['B183피치'].get('target')}")
show("B183 ⓓ 바꾸지 않는 것 — 좌표가 있는 값은 지금 판정(자리 추정 칸 0) · 후보 없는 자리 없는 값은 노드 0(보류 「후보 없음」)",
     all(r.get("guess") is None and r.get("path") != PG.PATH for r in list(_rp1.values()) + list(_rp3.values()))
     and _ru["B183피치"].get("guess", {}).get("why") == PG.NONE and not _ru["B183피치"].get("node_id"),
     f"P1 {[(s, r.get('path')) for s, r in _rp1.items()]} · U3 {_ru['B183피치'].get('guess')}")
# ────────────────────────────────────────────────────────────── B184 잠정 골격 노드의 사람 손 · 인입 뒤 한 화면 (창작 표본)
print("\n■ B184 — 승격 · 합침 · 그대로(손 하나) · 인입 `--step` 좌표 단계 · 인입 뒤 한 화면(묶음 넷) · 품질층 uses에 Unit")
import builtins                                                    # noqa: E402
import json as _js184                                              # noqa: E402
from types import SimpleNamespace                                  # noqa: E402
from cli import ops_review as OR, provisional_ask as PA            # noqa: E402
from core import paths as _P184                                    # noqa: E402
from core.state import provisional_hand as PH                      # noqa: E402


def _snap184():
    return _js184.dumps([STO.read(STO.QUEUE, []), {lay: open_graph(lay).nodes for lay in ("process", "quality")}],
                        sort_keys=True, ensure_ascii=False)


_a184 = SimpleNamespace(layer="all", actor="B184시험")
_z0 = _snap184()
_b = io.StringIO()
with contextlib.redirect_stdout(_b):
    OR.run(_a184)                                  # 시험 stdin은 터미널이 아니다 — 계획만
_plan_only = _snap184() == _z0
_head = _b.getvalue().splitlines()[0] if _b.getvalue() else ""


def _ans184(q):
    if "[자리 추정" in q and "B183피치" in q:
        return "d"
    if "[보류" in q and "B183장력" in q:
        return "1"
    return ""


with contextlib.redirect_stdout(io.StringIO()):
    OR.run(_a184, ask=_ans184)
_mu3 = _mf("B183U")
_jang = _pn("노칭::B183장력")
show("B184 ⓕ 인입 뒤 한 화면 — 묶음 넷(잠정 · 애매 · 자리 추정 · 후보 있는 보류)이 한 명령의 표로 · 비대화형은 쓰기 0 · 자리 추정 떼기는 "
     "보류로(다시 붙음이 보지 않는다 — 표지 없음) · 보류의 후보 고르기는 그 노드에 붙인다(큐에서 내림)",
     _plan_only and all(w in _head for w in ("잠정 골격 노드", "애매", "자리 추정", "후보 있는 보류"))
     and not (_pn("스태킹::B183피치") or {}).get(PG.FIELD) and "B183피치" in _mu3 and not _mu3["B183피치"].get("guess")
     and "B183U#U2" in (_jang or {}).get("provenance", []) and "B183장력" not in _mu3,
     f"계획만 쓰기 0 {_plan_only} · {_head[:90]} · 피치 재료 {_mu3.get('B183피치')} · 장력 출처 {(_jang or {}).get('provenance')}")
_unregister(D183)

# ⓑ ① 품질층 uses에 Unit — 품질 산문이 설비 소속을 말한 새 값은 그 설비 아래 이름(표와 같은 규칙) · 소속 엣지는 설비에서
D184 = "b184_q"
_register("quality", D184)
_X184 = {"entities": [{"surface": "B184압력", "category": "Property", "parent": None, "value": None,
                       "belongs_to": {"name": "노칭 프레스", "category": "Unit", "from": "본문"}}], "relations": [], "about": []}
with Live(by={"extract": lambda b: _X184, "judge": lambda b: {"type": "new", "matched_id": None, "confidence": 0.9},
              "outline": lambda b: {"headings": []}, "reinforce": lambda b: {"pick": None}}), _quiet():
    run_document({"source_path": "(합성) B184Q.docx", "revision": "R1", "parsed_at": "2026-11-06T00:00:00", "parser_version": "m",
                  "adapter_version": "m", "context": {}, "payload_kind": "prose", "doc_type": D184, "doc_id": "B184Q",
                  "chunks": [{"source_locator": "Q1", "doc_type": D184, "process_group": None, "process_ref": "노칭",
                              "electrode_type": "both", "text": "노칭 프레스의 B184압력을 관리한다.", "section": "1", "meta": {}}]})
    finalize()
_pq = _pn("노칭::노칭 프레스::B184압력")
_un = _pn("노칭::노칭 프레스")
_oa184 = [x for x in STO.read(STO.QUEUE, []) if x["kind"] == "orphan_attach" and x.get("doc_id") == "B184Q"]
show("B184 ⓑ 품질층 uses에 Unit — 품질 산문이 「노칭 프레스의 ○○」를 말한 새 값이 소속 대상 「노칭 프레스」(공정층 Unit)로 풀린다 — "
     "그 설비 아래 이름 · 설비에서 소속 엣지 · orphan_attach 0",
     bool(_pq and _un) and not _oa184
     and any(e["src"] == _un["id"] and e["dst"] == _pq["id"] for lay in ("process", "quality") for e in open_graph(lay).edges),
     f"값 {(_pq or {}).get('canonical')} · orphan_attach {len(_oa184)}")
_unregister(D184)


def _mock184(step_answer=None):
    """클린 → CP01 → PFMEA01(`step_answer`면 `--step` — 좌표 단계에서 그 답 한 번(`p 1` 꼴) · 관문은 c · 그 밖은 EOF)."""
    with _quiet():
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
        IG.ingest_file(str(_FXR.ROOT_DIR / "raw" / "CP01.xlsx"), "cp", ask=False)
    if step_answer is None:
        say_new(("레이저노칭", "조립"))              # 사람이 「새로」(고침 B196 ① — 사람 없는 실행은 세우지 않는다)
        with _quiet():
            IG.ingest_file(str(_FXR.ROOT_DIR / "raw" / "PFMEA01.xlsx"), "pfmea", ask=False)
        return

    left = [step_answer]

    def _inp(q=""):
        if "말 또는 글쇠" in q and left:                     # 좌표 단계 — 골격 칸 줄 처분 한 번 · 그다음은 계속(B202 — 한 고리)
            return left.pop()
        if "계속 c" in q:
            return "c"
        raise EOFError
    _in0, _tty0 = builtins.input, sys.stdin.isatty
    builtins.input, sys.stdin.isatty = _inp, (lambda: True)          # 터미널 (`--step`은 대화형에서만 산다)
    try:
        with _quiet():
            IG.ingest_file(str(_FXR.ROOT_DIR / "raw" / "PFMEA01.xlsx"), "pfmea", step=True)
    finally:
        builtins.input, sys.stdin.isatty = _in0, _tty0


def _r16():
    rows = [r for r in (LG.read("PFMEA01") or {}).get("rows") or [] if str(r.get("locator")).endswith("R16")]
    return next((r for r in rows if r.get("role") == "anchor"), {}), [r for r in rows if r.get("role") == "entity"]


def _skel184():
    return _js184.loads(_P184.layers(coord_layer(), "skeleton.json").read_text(encoding="utf-8"))


def _provs184():
    return [n for n in open_graph(coord_layer()).nodes.values() if is_live(n) and n.get(PROVISIONAL)]


# ⓒ 승격 — 이미 세운 잠정(인입 뒤)
_mock184()
_ln0 = _pv("레이저노칭")
_g0 = open_graph(coord_layer())
_vals0 = sorted(n["canonical"] for n in _g0.nodes.values() if n["canonical"].startswith("레이저노칭::"))
_pr = PH.promote("B184시험", nid=_ln0["id"])
with _quiet():
    RUN.cmd_bootstrap([])
_g1 = open_graph(coord_layer())
_ln1 = _g1.get(_ln0["id"])
_tree = _js184.dumps(_skel184()["TREE"], ensure_ascii=False)
show("B184 ⓒ 승격 — mock PFMEA01의 잠정 「레이저노칭」 → 골격 파일에 (조립, 레이저노칭) · 같은 노드 id · 잠정 표시 0 · 사람 고정 · "
     "다음 bootstrap 뒤 노드 수 그대로(두 벌 0) · 아래 값 이름 그대로",
     _pr["parent"] == "조립" and '{"@unordered": "레이저노칭"}' in _tree and _ln1["status"] == "seed" and not _ln1.get(PROVISIONAL)
     and len(_g1.nodes) == len(_g0.nodes)
     and sum(1 for n in _g1.nodes.values() if n["canonical"] == "레이저노칭") == 1
     and sorted(n["canonical"] for n in _g1.nodes.values() if n["canonical"].startswith("레이저노칭::")) == _vals0 and _vals0,
     f"{_pr['parent']} › {_pr['canonical']} · 노드 {len(_g0.nodes)} → {len(_g1.nodes)} · 값 {_vals0[:2]}")

# ⓓ 합침 — 이미 세운 잠정을 골격 노드로 → 재구축 한 길
_mock184()
_mg = PH.merge("B184시험", target="노칭", nid=_pv("레이저노칭")["id"])
_b = io.StringIO()
with contextlib.redirect_stdout(_b):
    _rbc = RB.main(["--allow-mock", "--yes"], bootstrap=RUN.cmd_bootstrap, screen=RUN.fresh_screen)
_an, _en = _r16()
show("B184 ⓓ 합침 — 잠정을 기존 골격 노드 「노칭」으로 → 골격 별칭에 그 표기 · 재구축 안내 · 재구축 뒤 잠정 노드 0 · 아래 값이 "
     "그 골격 노드 아래 이름",
     _mg["rebuild"] and "레이저노칭" in _skel184()["ALIASES"].get("노칭", []) and _rbc == 0 and not _provs184()
     and str(_an.get("canonical")).split("::")[0] == "노칭" and _en
     and all(str((open_graph("quality").get(r["node_id"]) or open_graph("process").get(r["node_id"]) or {}).get("canonical", ""))
             .startswith("노칭::") for r in _en if r.get("node_id")),
     f"재구축 rc {_rbc} · 잠정 {len(_provs184())} · R16 → {_an.get('canonical')} · 값 {[r.get('target') for r in _en][:3]}")

# ⓔ `--step` 좌표 단계 — 정한 것은 그 문서의 나머지 행부터(재구축 0)
_mock184("p")
_an, _en = _r16()
_lp = _pn("레이저노칭")
_ok_p = not _lp and not _provs184() and not _an.get("node_id")       # B202 ③ — 문 줄의 승격 p는 거부(기록 0 · 그 행은 보류 그대로)
_mock184("m 노칭")
_an2, _en2 = _r16()
show("B184 ⓔ `--step` 좌표 단계에서 합침 — 그 골격 노드로 바로 풀린다 · 잠정 노드 0 · 재구축 0 · 문 줄의 승격 `p 1`은 거부(B202 ③ — "
     "기록 0 · 노드 0 · 그 행은 보류)",
     _ok_p and str(_an2.get("canonical")).split("::")[0] == "노칭" and not _provs184() and not _pn("레이저노칭"),
     f"p 거부 {_ok_p} · 합침 R16 → {_an2.get('canonical')} · 잠정 {len(_provs184())}")
# ────────────────────────────────────────────────────────────── B185 ① 손잡이 모으기 (기본값 = 지금 상수)
print("\n■ B185 ① — 사람이 바꿀 까닭이 있는 상수는 knobs.json · llm.json으로(적지 않으면 지금 상수 · 같은 뜻은 손잡이 하나)")
from cli import golden as GD, parse as PS                          # noqa: E402
from core.query import query as QY                                 # noqa: E402
from core.state import captures as CPT                             # noqa: E402
from parser import profile as PPF, render as RND                   # noqa: E402
from parser.adapters import basic_docx as BDX, basic_ppt as BPP, basic_prose_xlsx as BPX   # noqa: E402


def _b185():
    return (PS.coord_cap_now(), (BPP.CONTEXT_CHARS, BPX.CONTEXT_CHARS, BDX.CONTEXT_CHARS), PPF.SPARSE_EMPTY_RATIO,
            gateway.config().get("embed_batch"), RND.MAX_EDGE, CPT._size()[0], GD.default_k())


_P.knobs().unlink(missing_ok=True)
KN.apply()
_d185 = _b185()
_P.knobs().write_text(json.dumps({"coord_tag_cap": 7, "image_context_chars": 42, "profile_sparse_empty_ratio": 0.3,
                                  "collect_limit": 5}), encoding="utf-8")
os.environ.update(EMBED_BATCH="5", IMAGE_MAX_EDGE="777")
KN.apply()
_v185 = _b185()
_P.knobs().unlink()
for _k in ("EMBED_BATCH", "IMAGE_MAX_EDGE"):
    os.environ.pop(_k, None)
KN.apply()
show("B185 ⓐ 새 손잡이 — knobs.json의 값을 쓰는 자리가 읽는다(coord_tag_cap · image_context_chars — 세 어댑터 한 값 · "
     "profile_sparse_empty_ratio) · llm.json 쪽(EMBED_BATCH · IMAGE_MAX_EDGE — 파서 렌더와 core 캡처 같은 값) · 골든셋 k = collect_limit · "
     "적지 않으면 지금 상수",
     _d185 == (PS.COORD_CAP, (1500,) * 3, 0.7, None, 1600, 1600, QY.COLLECT_LIMIT) and _v185 == (7, (42,) * 3, 0.3, 5, 777, 777, 5)
     and _b185() == _d185,
     f"기본 {_d185} · 적은 값 {_v185}")
# ────────────────────────────────────────────────────────────── B186 ⓔ 두 끝이 같은 노드인 엣지 — 세우지 않고 관문 거부로 기록(문서 1 J32)
print("\n■ B186 ⓔ 같은 노드 엣지 — 원인 칸 = 모드 칸 · 표기가 다른 두 칸을 사전이 한 노드로")
import openpyxl as _ox186                                                     # noqa: E402
from core.build import gate as _G186                                          # noqa: E402
from core.state import ops_mark as _OM186                                     # noqa: E402
from cli import ops_review as _OR186                                          # noqa: E402
_t186 = Path(tempfile.mkdtemp(prefix="b186_"))                               # 사본은 시스템 임시 폴더(레포 쓰기 0)


def _pf186(name, cause):
    wb = _ox186.load_workbook(_FXR.ROOT_DIR / "raw" / "PFMEA01.xlsx")
    ws = wb.active
    ws.cell(4, 6).value = cause(ws.cell(4, 5).value)                          # R4 고장원인 칸 ← (모드 칸으로 정한 글)
    wb.save(_t186 / name)
    return str(_t186 / name)


def _same186(doc):
    return [x for x in STO.read(STO.GATE_REJECTS, {"rejects": []}).get("rejects") or []
            if x.get("verdict") == _G186.SAME_NODE and x.get("doc_id") == doc]


def _ing186(path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        IG.ingest_file(path, "pfmea", ask=False)
    return buf.getvalue()


with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
    IG.ingest_file(str(_FXR.ROOT_DIR / "raw" / "CP01.xlsx"), "cp", ask=False)
_o186 = _ing186(_pf186("PFMEAB186A.xlsx", lambda m: m))
_s186 = _same186("PFMEAB186A")
_gq186 = open_graph("quality")
_fm186 = next((n for n in _gq186.nodes.values() if n.get("canonical", "").endswith("전극 치수 불량")), {})
_e186 = [e for lay in ("process", "quality") for e in open_graph(lay).edges if e["src"] == _fm186.get("id")]
show("B186 ⓔ 원인 칸 = 모드 칸(PFMEA 사본) — 그 causes 엣지 0 · 거부 기록 1(사유 같은 노드 · 두 표기) · 인입은 끝까지 · "
     "그 행의 다른 엣지 그대로 · 인입 끝 줄 「같은 노드 엣지 1(표기가 다른 것 0」",
     len(_s186) == 1 and _s186[0]["rel"] == "causes" and _s186[0]["surfaces"] == ["전극 치수 불량"] * 2
     and not any(e["src"] == e["dst"] for lay in ("process", "quality") for e in open_graph(lay).edges)
     and {"affects", "occurs_in"} <= {e["rel"] for e in _e186} and "같은 노드 엣지 1(표기가 다른 것 0" in _o186
     and LG.read("PFMEAB186A"),
     f"거부 {[(x['rel'], x['surfaces']) for x in _s186]} · 노드 엣지 {sorted({e['rel'] for e in _e186})}")
_OM186.alias("quality", _fm186.get("id"), "B186 다른 표기", "시험", "B186 ⓔ — 두 표기를 한 노드로(대역 판단)")
_o186b = _ing186(_pf186("PFMEAB186B.xlsx", lambda m: "B186 다른 표기"))
_s186b = _same186("PFMEAB186B")
_rv186 = io.StringIO()
with contextlib.redirect_stdout(_rv186):
    _OR186.tables(_OR186.bundles("all"))
show("B186 ⓔ 표기가 다른 두 칸이 한 노드로(사전 별칭) — 「표기가 다른 것 1」 · 인입 뒤 한 화면 다섯째 묶음 1줄(두 표기 · 다음 줄)",
     len(_s186b) == 1 and sorted(_s186b[0]["surfaces"]) == sorted(["B186 다른 표기", "전극 치수 불량"])
     and "같은 노드 엣지 1(표기가 다른 것 1" in _o186b
     and [r["doc"] for r in _OR186.same_nodes("all")] == ["PFMEAB186B"] and "ops alias-reject" in _rv186.getvalue(),
     f"거부 {[x['surfaces'] for x in _s186b]} · 묶음 {_OR186.same_nodes('all')}")
shutil.rmtree(_t186, ignore_errors=True)

done()
