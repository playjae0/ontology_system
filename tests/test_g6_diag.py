# -*- coding: utf-8 -*-
"""G6 ⑰ 산문 연결 진행 · 좌표 진단 · 판정 근거·임베딩 캐시 · 정합 점검·정리·스키마 재대조 (B99 ⑦~⑩).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) ×
층(process · quality)에서 같은 성질을 잰다(B99 범용성 — 표본: CP01·PFMEA01 · PPT01·QPPT01).

잠그는 성질:
  ⓘ 산문 판정 진행의 총수 = 추출이 낸 개체 수(표는 레코드 기준 그대로) · 값 표의 위치 열 = 대장 locator
  ⓙ 좌표 진단 — 목록 밖 표기 상위(행 수 내림) 표 + 다음 줄(골격 파일 · ALIASES · bootstrap) · LLM 전
  ⓚ 후보 임베딩 인코딩 횟수 = 후보 노드 수(판정 수와 무관) · 결과 불변 · 불확실의 가장 가까운 후보(LLM · 가드)
  ⓛ 정합 점검이 주입한 어긋남을 센다 · 정리는 계획만 → --apply에서만(사람 판단 항목은 남김) ·
     스키마 재대조 어긋남 → 사전 점검에서 멈춤
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401
from g6_common import _register, _unregister    # noqa: E402

from cli import ingest_screen as SCR           # noqa: E402
from core import matcher as MT                 # noqa: E402
from core.build import ledger as LG            # noqa: E402
from core.state import integrity               # noqa: E402

MATRIX = [("표", "process", "CP01"), ("표", "quality", "PFMEA01"),
          ("산문", "process", "PPT01"), ("산문", "quality", "QPPT01")]


def _fresh():
    init.init(fresh_=True, all_=True)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


print("\n■ B99 ⑦ 산문 연결 진행 (형태 × 층)")
_ok_i = []
for form, lay, doc in MATRIX:
    _fresh()
    env = load(doc)
    stage = {"이름": "판정", "총": len(env.get("records") or []) * 2 or 1}
    buf = io.StringIO()
    MT.PROGRESS = SCR.judge_progress(stage["총"], stage=stage, stride=1)
    LG.ON_ROW = SCR.row_printer()
    try:
        with contextlib.redirect_stdout(buf):
            run_document(env, notice=SCR.build_screen(stage=stage, prose=form == "산문"))
    finally:
        MT.PROGRESS, LG.ON_ROW = None, None
    out = buf.getvalue()
    rows = (LG.read(doc) or {}).get("rows") or []
    totals = {int(m) for m in re.findall(r"\[판정\] 값 \d+/(\d+)", out)}
    ents = sum(1 for r in rows if r.get("role") == "entity")
    want = ents if form == "산문" else len(env.get("records") or []) * 2
    locs = {r.get("locator") for r in rows if r.get("locator")}
    vals = [l for l in out.splitlines() if re.match(r"\s+[✓+?✗·] \| ", l)]
    _ok_i.append((form, lay, (not totals or totals == {want}) and stage["총"] == want,
                  all(l.split(" | ")[1].strip().rstrip("…") and
                      any(x.startswith(l.split(" | ")[1].strip().rstrip("…")) for x in locs)
                      for l in vals), sorted(totals), want))
show("ⓘ 산문 판정 진행 총수 = 추출 개체 수(표는 레코드 기준) · 값 표의 위치 = 대장 locator (표·산문 × 층)",
     all(a and b for _f, _l, a, b, *_r in _ok_i),
     " · ".join(f"{f}×{l} 진행 {t} · 단계 총 → {w}" for f, l, _a, _b, t, w in _ok_i))

print("\n■ B99 ⑧ 좌표 진단")
from parser import tagger as TG                # noqa: E402
from cli.parse import coord_screen             # noqa: E402
_plans = []
_nodes = [{"canonical": "노칭", "aliases": [], "tier": "main"}]
TG.tag([{"process_ref": r} for r in ["없는A"] * 3 + ["없는B"] * 5 + ["노칭"]], nodes=_nodes,
       notice=_plans.append)
_pre = next(p for p in _plans if p.get("단계") == "예고")
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    coord_screen()[0](_pre)
_o = _buf.getvalue()
show("ⓙ 좌표 진단 — 목록 밖 표기 상위(행 수 내림) 표 + 다음 줄(골격 파일 · ALIASES · bootstrap) · LLM 전",
     _pre["목록밖_상위"] == [("없는B", 5), ("없는A", 3)]
     and _o.index("없는B") < _o.index("없는A") and "skeleton.json" in _o and "ALIASES" in _o
     and "bootstrap" in _o and _o.index("없는B") < _o.index("좌표 태깅 —"), _pre["목록밖_상위"])

print("\n■ B99 ⑨ 판정 근거 · 임베딩 캐시")
from core.llm import gateway, narrow as NR     # noqa: E402
NR.set_narrow("embed")
MT._VEC.clear()
MT.ENCODES.update(n=0, 후보=0)
_pool = [{"id": f"N{i:02d}", "canonical": f"후보 노드 {i}", "category": "Property"}
         for i in range(20)]
_tops = []
for s in ("후보노드 3", "후보노드 7", "다른 표기", "후보노드 3", "또 다른"):   # 질의는 후보 글과 다르게
    kept, how = MT._narrow(s, _pool, 12)
    _tops.append([c["id"] for c in kept])
_first = _tops[0] == _tops[3]                  # 같은 질의 → 같은 결과(캐시가 결과를 바꾸지 않는다)
NR.set_narrow(None)
_g = MT._guard_auto({"type": MT.MATCH, "matched_id": "N01", "confidence": 0.8, "path": "p"},
                    [{"id": "N01", "canonical": "후보 노드 1", "status": "auto"}])
MT.LAST_NARROW.clear()
MT.LAST_NARROW.update(how="임베딩", top=[("N01", "후보 노드 1", 0.91)])
_ev = dict(_g)
MT._evidence(_ev, [{"id": "N01", "canonical": "후보 노드 1"}])
_keep = gateway.chat
gateway.chat = lambda *a, **k: {"type": "uncertain", "matched_id": "N02", "confidence": 0.4}
try:
    _lv = MT._judge_live("표기", [{"id": "N02", "canonical": "후보 노드 2"}], "Property")
finally:
    gateway.chat = _keep
from cli.platform import auto_next_lines       # noqa: E402
_nx = auto_next_lines({"payload": {"node_id": "NEW1", "layer": "process",
                                   "nearest": _ev["nearest"]}})
show("ⓚ 후보 임베딩 인코딩 = 후보 노드 수(판정 5회와 무관) · 결과 불변 · 불확실의 가장 가까운 후보(가드 · LLM) · "
     "그 id로 칠 다음 줄",
     MT.ENCODES["후보"] == 20 and _first and how == "임베딩"
     and _g["type"] == MT.UNCERTAIN and _g.get("guarded") and _ev["nearest"]["by"] == "가드"
     and _ev["nearest"]["canonical"] == "후보 노드 1" and _ev["emb_top"] == 0.91
     and _lv.get("nearest_id") == "N02" and "ops merge    process NEW1 N01" in _nx,
     f"후보 인코딩 {MT.ENCODES['후보']} · {_ev['nearest']}")

print("\n■ B99 ⑩ 정합 점검 · 정리 · 스키마 재대조 (층 둘)")
_fresh()
run_document(load("CP01"))
run_document(load("PFMEA01"))
GHOST = "01ZZZZZZZZZZZZZZZZZZZZZZZZ"
q = store.read(store.QUEUE, [])
q += [{"kind": "auto_node", "doc_id": "X", "reason": "주입", "payload": {"node_id": GHOST}},
      {"kind": "uncertain_match", "doc_id": "X", "reason": "주입",
       "payload": {"node_id": GHOST + "1"[:0]}, "resolution": {"actor": "사람", "decision": "keep"}}]
store.write(store.QUEUE, q)
d = Dictionary.open()
d.register("유령 표기", GHOST, provenance="시험")
d.save()
for lay in ("process", "quality"):
    g = open_graph(lay)
    any_id = next(iter(g.nodes))
    g.edges.append({"src": any_id, "rel": "part_of", "dst": GHOST, "status": "auto"})
    g.save()
_c0 = integrity.count(integrity.state_scan()[0])
_q0 = json.dumps(store.read(store.QUEUE, []), sort_keys=True)
_plan = integrity.tidy(apply=False)
_same = json.dumps(store.read(store.QUEUE, []), sort_keys=True) == _q0
_done = integrity.tidy(apply=True)
_c1 = integrity.count(integrity.state_scan()[0])
_kept = [x for x in store.read(store.QUEUE, []) if x.get("resolution")]
_register("process", "bad_q")
_sp = _P.schemas("bad_q.json")
_s = json.loads(_sp.read_text(encoding="utf-8"))
_s["fields"] = {"설비": {"role": "entity", "category": "없는카테고리"}}
_sp.write_text(json.dumps(_s, ensure_ascii=False), encoding="utf-8")
from cli import preflight as PF                 # noqa: E402
_bs = io.StringIO()
with contextlib.redirect_stdout(_bs):
    _gate = PF.schema_gate("bad_q")
_unregister("bad_q")
show("ⓛ 정합이 주입한 어긋남을 센다(층 둘) · 정리는 계획만(쓰기 0) → --apply에서만 · 사람 판단 항목은 남김 · "
     "스키마 재대조 어긋남 → 사전 점검에서 멈춤",
     _c0 == (2, 1, 2) and _same and _plan["applied"] is False and _plan["큐_남김"] == 1
     and _done["applied"] and _c1 == (1, 0, 0) and len(_kept) == 1
     and _gate is False and "스키마 재대조" in _bs.getvalue(),
     f"전 {_c0} · 후 {_c1}")
init.init(fresh_=True, all_=True)

done()
