# -*- coding: utf-8 -*-
"""G6 ⑭ 산문 추출을 보이게 — 추출 예고 · 청크별 메타 줄 · 시간 기준 누적 줄 · 청크 단위 이어 쓰기 ·
`--step` 산문 관문 (B97).

창작 표본(mock · RFQ01 · 시험 전용 후보 함수 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50).

잠그는 성질:
  ⓐ 한 렌즈 산문 인입에 추출 예고 줄 — 부를 청크 = 청크 − ref − 재사용 · 청크 줄 수와 같다
  ⓑ 청크마다 메타 줄(개체 표기·카테고리 전부 · 관계 수) · 끝 줄에 사용량
  ⓒ 누적 줄은 시간 기준(호출이 늘면 시작 한 줄 · 간격마다 누적) · mock이고 호출 0이면 말이 없다
  ⓓ 도중 중단 → 부분 파일만 · 재실행은 끝난 청크를 부르지 않고 이어서 완료 · 한 번에 돈 것과 같다
  ⓔ 재사용 조건(어댑터 판)이 다르면 부분 파일을 버리고 처음부터
  ⓕ --step 산문: 추출 예고에서 멈추면 체크포인트 0 · 추출 뒤에서 멈추면 그래프·큐 쓰기 0 ·
     체크포인트 완료 · 재실행은 추출 재사용 · 표 문서의 관문은 판정 예고 그대로
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _ingest, _register, _run, _unregister, done, json,   # noqa: F401
                       open_graph, store)
from cli import _screen                     # noqa: E402
from cli.ingest_screen import extract_screen  # noqa: E402
from core.build import extract as EX        # noqa: E402
from core.build.entry import _vocab          # noqa: E402
from core.llm import gateway                 # noqa: E402
from core.state.bootstrap import load_config  # noqa: E402

init.init(fresh_=True)
_register()

print("\n■ B97 ① 추출 예고 · ② 청크별 줄")
_out = _ingest("--sheets", "auto")
_pre = [l for l in _out.splitlines() if "추출 예고 —" in l]
_rows = [l for l in _out.splitlines() if l.strip().startswith("[추출 ")]
_m = re.search(r"청크 (\d+)\(ref 시트 (\d+) · 체크포인트 재사용 (\d+) 제외\) → LLM ≤ (\d+)회",
               _pre[0] if _pre else "")
show("ⓐ 한 렌즈 산문 인입에 추출 예고 줄 — 부를 청크 = 청크 − ref − 재사용 = 청크 줄 수",
     bool(_m) and int(_m[1]) - int(_m[2]) - int(_m[3]) == int(_m[4]) == len(_rows) > 0
     and "렌즈 예고" not in _out, (_pre or [""])[0].strip())

_env = json.loads(_P.parsed("RFQ01.json").read_text(encoding="utf-8"))
_ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
_loc = {c["source_locator"]: cid for cid, c in _ch.items() if c.get("doc_id") == "RFQ01"}
_cfg = load_config("process")
_orig = EX._candidates_for
_calls = []


def _fake(cid, chunk, cfg, vocab):
    """시험 전용 후보 — 청크마다 결정적(표기 둘 · 관계 하나)."""
    _calls.append(cid)
    n = len(_calls)
    return {"chunk_id": cid, "relations": [{"src": f"부품{n}", "rel": "part_of", "dst": "노칭"}],
            "attach": [], "entities": [{"surface": f"부품{n}", "category": "Component"},
                                       {"surface": "치수", "category": "Property"}]}


def _extract(note=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, made = EX.extract(_env, _cfg, _loc, _vocab(_cfg),
                               notice=note or extract_screen())
    return out, made, buf.getvalue()


EX._candidates_for = _fake
EX.invalidate("RFQ01")
_ref, _, _txt = _extract()
_ln = [l for l in _txt.splitlines() if l.strip().startswith("[추출 ")]
show("ⓑ 청크마다 메타 줄(개체 표기·카테고리 전부 · 관계 수) · 끝 줄에 사용량",
     len(_ln) == len(_rows) and all("부품" in l and "[Component]" in l and "치수[Property]" in l
                                    and "관계 1" in l for l in _ln)
     and any("추출 끝 —" in l and "LLM 사용량 — 호출" in l for l in _txt.splitlines()),
     _ln[0].strip()[:90] if _ln else "")

print("\n■ B97 ② 시간 기준 누적 줄")
_tick0 = _screen.TICK_SECONDS
_screen.TICK_SECONDS = 0.1
_b1, _b2 = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(_b1):
    with _screen.ticker("시험"):
        time.sleep(0.4)                      # mock · 호출 0 → 말이 없다
with contextlib.redirect_stdout(_b2):
    with _screen.ticker("시험", where=lambda: "추출 2/9"):
        gateway.USAGE["calls"] += 1          # 시험 주입 — 호출이 시작됐다
        time.sleep(0.6)
gateway.USAGE["calls"] -= 1
_screen.TICK_SECONDS = _tick0
_t = _b2.getvalue().splitlines()
show("ⓒ 누적 줄은 시간 기준(시작 한 줄 · 간격마다 누적 · 경과) · mock이고 호출 0이면 말이 없다",
     _b1.getvalue() == "" and sum("LLM 사용 시작" in l for l in _t) == 1
     and sum("· 추출 2/9 · 호출" in l and "경과" in l for l in _t) >= 2, _t[1:2])

print("\n■ B97 ③ 청크 단위 이어 쓰기")
EX.invalidate("RFQ01")
_calls.clear()


def _boom(cid, chunk, cfg, vocab):
    if len(_calls) == 3:
        raise KeyboardInterrupt              # 시험 주입 — 넷째 청크에서 끊긴다
    return _fake(cid, chunk, cfg, vocab)


EX._candidates_for = _boom
try:
    _extract()
except KeyboardInterrupt:
    pass
_mid = (EX.partial_path("RFQ01").exists(), EX.has_checkpoint("RFQ01"))
EX._candidates_for = _fake
_n0 = len(_calls)
_res, _made, _txt2 = _extract()
show("ⓓ 도중 중단 → 부분 파일만 · 재실행은 끝난 청크를 부르지 않고 이어서 완료 · 한 번에 돈 것과 같다",
     _mid == (True, False) and len(_calls) - _n0 == len(_rows) - 3 and _made
     and not EX.partial_path("RFQ01").exists()
     and json.dumps(_res["candidates"]) == json.dumps(_ref["candidates"])
     and "추출 이어서 — 끝난 청크 3" in _txt2,
     [l.strip() for l in _txt2.splitlines() if "이어서" in l or "추출 예고" in l])

EX.invalidate("RFQ01")
_calls.clear()
EX._candidates_for = _boom
try:
    _extract()
except KeyboardInterrupt:
    pass
EX._candidates_for = _fake
_env["adapter_version"] = str(_env.get("adapter_version")) + "+b97"
_n0 = len(_calls)
_, _, _txt3 = _extract()
show("ⓔ 재사용 조건(어댑터 판)이 다르면 부분 파일을 버리고 처음부터",
     len(_calls) - _n0 == len(_rows) and "이어서" not in _txt3
     and not EX.partial_path("RFQ01").exists())
EX._candidates_for = _orig

print("\n■ B97 ④ --step 산문 관문")


def _graph():
    """그래프 스냅샷 — 경계(GraphStore)를 지나 읽는다."""
    g = open_graph("process")
    return json.dumps([g.nodes, g.edges], sort_keys=True, default=str)


EX.invalidate("RFQ01")
_o1 = _ingest("--sheets", "auto", "--step", answers="c\nc\nc\nq\n")
_ck1 = EX.has_checkpoint("RFQ01")
_q0 = json.dumps(store.read(store.QUEUE, []), sort_keys=True)
_g0 = _graph()
_o2 = _ingest("--sheets", "auto", "--step", answers="c\nc\nc\nc\nq\n")
_same = (json.dumps(store.read(store.QUEUE, []), sort_keys=True) == _q0 and _graph() == _g0)
_o3 = _ingest("--sheets", "auto")
_o4 = _run("ingest-file", str(ROOT / "tests/fixtures/raw/CP01.xlsx"), "--doc-type", "cp",
           "--allow-mock", "--step", answers="c\nc\nc\nq\n")
show("ⓕ --step 산문: 추출 예고 멈춤 = 체크포인트 0 · 추출 뒤 멈춤 = 그래프·큐 쓰기 0 · 완료 · "
     "재실행은 추출 재사용 · 표 문서는 판정 예고 관문 그대로",
     "[4/8] 추출 예고" in _o1 and not _ck1
     and "[5/8] 추출 결과·판정 예고" in _o2 and EX.has_checkpoint("RFQ01")
     and _same and "체크포인트 재사용(LLM 0)" in _o3 and "[4/7] 판정 예고" in _o4
     and "] 추출 예고 —" not in _o4,
     [l.strip()[:60] for l in _o2.splitlines() if "[5/8]" in l])
_unregister()
init.init(fresh_=True)

done()
