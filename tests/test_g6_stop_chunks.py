# -*- coding: utf-8 -*-
"""G6 ㉗ 사람이 멈춘 문서는 흔적이 없다 · 시험은 표준입력을 물려받지 않는다 · 닫힌 화면의 정리는 조용히 (B110 ① ② ③).

창작 표본(mock)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) × 층(process · quality):
표 CP01(cp · process) · PFMEA01(pfmea · quality) · 산문 B110SP(prose 엑셀 · process · 힌트 개체 Property) · B110SQ(같은
통합문서 사본 · quality · 힌트 개체 Failure). 관문 답은 pty로 넣는다(관문은 tty에서만 묻는다).

잠그는 성질:
  ⓐ 표준입력: 시험 · doctor의 하위 프로세스 호출 중 표준입력(`stdin` · `input`)을 정하지 않은 것 0(소스 대조 — pty 도우미는
     표준입력이 pty다)
  ⓑ 닫힌 화면: 공통 진입의 화면 스트림은 한 번 닫힌 뒤 `flush` · `close`(끝 정리)가 던지지 않는다 — 쓰기만 멈춤 신호
  ⓒ 사람 멈춤: `--step` 관문의 `q`(표 · 산문 × 층 둘) ⇒ 그 문서의 청크 · 그래프 · 사전 · 큐 = 시작 전 · `parsed/` 체크포인트는
     남는다 · 구축 안의 관문(산문 — 추출 결과)이면 문서 대장 · `extract/`도 남는다 · 구축 전의 관문(표)은 문서 대장에 쓰지 않는다 /
     `--step-every`의 `q`(표 · 산문 × 층 둘) ⇒ 같은 판 + 문서 대장 항목 · 체크포인트 남음 / 다시 치면 멈추지 않고 끝까지 · 산문은
     추출 재사용(LLM 0) · 결과 = 멈추지 않고 넣은 것
"""
from __future__ import annotations

import ast
import contextlib
import io
import re
import shutil
import tempfile
from pathlib import Path

sys_path = __import__("sys").path
sys_path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done   # noqa: F401
from g6_common import DT, RFQ, _register, _run, _unregister   # noqa: E402 — 산문 엑셀 표본 · 등록 · CLI(pty)

import run as RUN                                                  # noqa: E402
from cli import _entry                                             # noqa: E402
from core.state import log as LG                                   # noqa: E402
from core.state.world import World                                 # noqa: E402

FX = ROOT / "tests" / "fixtures"
HINTS = FX / "extract_hints"
QDT = "b110pq"
SH = "2-4:prose 5:ref *:skip"
TMP = Path(tempfile.mkdtemp(prefix="b110_"))
shutil.copy(RFQ, TMP / "B110SP.xlsx")
shutil.copy(RFQ, TMP / "B110SQ.xlsx")
#: 힌트 개체 셋 — 판정 값이 둘 이상이어야 `--step-every`가 도중에 묻는다(남은 값이 있을 때만)
_HINTED = {"B110SP": [{"surface": f"B110 산문 속성 {k}", "category": "Property"} for k in "가나다"],
           "B110SQ": [{"surface": f"B110 산문 고장 {k}", "category": "Failure"} for k in "가나다"]}
for _d, _e in _HINTED.items():
    (HINTS / f"{_d}.json").write_text(json.dumps({"사양_기계!R8-R17": {"entities": _e, "relations": []}},
                                                ensure_ascii=False), encoding="utf-8")
#: 형태 × 층 — (원본, doc_type, 추가 인자, 구축 안 관문까지의 답)
CASES = {"표 · process": (FX / "raw" / "CP01.xlsx", None, [], None),
         "표 · quality": (FX / "raw" / "PFMEA01.xlsx", None, [], None),
         "산문 · process": (TMP / "B110SP.xlsx", DT, ["--sheets", SH, "--coord", "노칭"], "c\nc\nc\nc\nq\n"),
         "산문 · quality": (TMP / "B110SQ.xlsx", QDT, ["--sheets", SH, "--coord", "노칭"], "c\nc\nc\nc\nq\n")}
TS = ("created", "at", "first_seen", "last_seen", "last_tried", "last_fp", "attempts", "obsoleted_at", "confirmed_at",
      "parsed_at", "first_ingested_at", "ingested_at", "updated_at", "last_hit")


def _argv(case, *extra):
    src, dt, more, _a = CASES[case]
    return ["ingest-file", str(src), "--allow-mock"] + (["--doc-type", dt] if dt else []) + more + list(extra)


def _base():
    """클린 → bootstrap → 산문 doc_type 둘 등록(층 둘)."""
    with contextlib.redirect_stdout(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
    _register("process", DT)
    _register("quality", QDT)


def _canon(x, nm):
    if isinstance(x, dict):
        return {k: _canon(v, nm) for k, v in x.items() if k not in TS}
    if isinstance(x, list):
        return sorted((_canon(v, nm) for v in x), key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))
    return nm.get(x, x) if isinstance(x, str) else x


def _state():
    """`(흔적, 문서 대장, 판정 대장)` — 흔적 = 그래프(층마다) · 사전 · 큐 · 청크(id는 이름으로 · 시각 뺌)."""
    nm = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in World().nodes()}
    led = _P.work("ingest_log")

    def dump(x):
        return json.dumps(_canon(x, nm), ensure_ascii=False, sort_keys=True)
    trace = dump({"graph": {lay: {"nodes": [dict(n, id=None) for n in g.nodes.values()], "edges": g.edges}
                            for lay, g in World().graphs.items()},
                  "dict": store.read(store.DICTIONARY, {}), "queue": store.read(store.QUEUE, []),
                  "chunks": store.read(store.CHUNKS, {})})
    ledger = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(led.glob("*.json"))} if led.exists() else {}
    return trace, dump(store.read(store.DOC_REGISTRY, {})), dump(ledger)


def _doc(case):
    return CASES[case][0].stem


def _kept(case):
    """남은 것 — 문서 대장 항목 · parsed/ · extract/ 체크포인트."""
    d = _doc(case)
    return (d in store.read(store.DOC_REGISTRY, {}), _P.parsed(f"{d}.json").exists(), _P.extract(f"{d}.json").exists())


# ────────────────────────────────────────────────────────────── ⓐ 표준입력 — 소스 대조
print("\n■ B110 ① 시험은 표준입력을 물려받지 않는다 — 시험 · doctor의 하위 프로세스 호출(소스 대조)")
_FUNCS = {"run", "Popen", "call", "check_output", "check_call"}
_MOD = re.compile(r"^(subprocess|_?sp\w*|_sub\w*)$")             # 하위 프로세스 모듈의 이름(별칭 포함)
_calls, _open = 0, []
for _f in [ROOT / "doctor.py"] + sorted((ROOT / "tests").rglob("*.py")):
    for _n in ast.walk(ast.parse(_f.read_text(encoding="utf-8"))):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) and _n.func.attr in _FUNCS
                and isinstance(_n.func.value, ast.Name) and _MOD.match(_n.func.value.id)):
            _calls += 1
            if not {k.arg for k in _n.keywords} & {"stdin", "input"}:
                _open.append(f"{_f.relative_to(ROOT).as_posix()}:{_n.lineno}")
show("ⓐ 시험 · doctor의 하위 프로세스 호출 중 표준입력을 정하지 않은 것 0(터미널에서 쳐도 숨은 질문을 기다리지 않는다)",
     _calls and not _open, f"호출 {_calls} · 표준입력 미지정 {_open[:3] or 0}")

# ────────────────────────────────────────────────────────────── ⓑ 닫힌 화면 — 끝 정리
print("\n■ B110 ② 닫힌 화면의 정리는 조용히 — 쓰기만 멈춤 신호(Python 판 무관)")


class _Closed(io.StringIO):
    def write(self, s):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


_t = _entry._Tee(_Closed())
_steps = []
for _name, _fn in (("쓰기", lambda: _t.write("줄\n")), ("다시 쓰기", lambda: _t.write("줄\n")),
                   ("flush", _t.flush), ("close", _t.close)):
    try:
        _fn()
        _steps.append((_name, "조용"))
    except LG.ScreenClosed:
        _steps.append((_name, "멈춤 신호"))
    except Exception as _e:                                          # noqa: BLE001 — 무엇이 나왔는지가 판정이다
        _steps.append((_name, type(_e).__name__))
show("ⓑ 한 번 닫힌 화면 — 쓰기는 멈춤 신호(ScreenClosed) · 그 뒤 flush · close(끝 정리)는 던지지 않는다",
     [s for _n2, s in _steps] == ["멈춤 신호", "멈춤 신호", "조용", "조용"], " · ".join(f"{n} {s}" for n, s in _steps))

# ────────────────────────────────────────────────────────────── ⓒ 사람 멈춤
print("\n■ B110 ③ 사람이 멈춘 문서는 흔적이 없다 — --step q · --step-every q (표 · 산문 × 층 둘)")
REF = {}
for case in CASES:
    _base()
    s0 = _state()
    out = _run(*_argv(case))
    REF[case] = (s0, _state(), out)
    assert "[성공]" in out, (case, out[-400:])

_g, _e, _r = [], [], []
for case in CASES:
    s0, sfull, _o = REF[case]
    inside = CASES[case][3]
    for mode, extra, answers in (("관문", ("--step",), inside or "c\nc\nc\nq\n"), ("값마다", ("--step-every", "1"), "q\n")):
        _base()
        out = _run(*_argv(case, *extra), answers=answers)
        st, kept = _state(), _kept(case)
        row = (case, mode, "사람이 멈췄다" in out, st[0] == s0[0], kept)
        (_g if mode == "관문" else _e).append(row)
        again = _run(*_argv(case))
        _r.append((case, mode, "[성공]" in again, "[추출 체크포인트 재사용]" in again, _state()[0] == sfull[0]
                   and _state()[2] == sfull[2]))

show("ⓒ --step 관문의 q(표 · 산문 × 층 둘) — 청크 · 그래프 · 사전 · 큐 = 시작 전 · parsed/ 남음 · 산문(구축 안의 관문 — 추출 "
     "결과)은 문서 대장 · extract/도 남음 · 표(관문 셋이 구축 전)는 문서 대장에 쓰지 않는다",
     all(stop and same and k[1] and (k[0] and k[2] if CASES[c][3] else not k[0]) for c, _m, stop, same, k in _g),
     " · ".join(f"{c} 멈춤 {stop} · 흔적 시작 전 {same} · 문서 대장 {k[0]} · parsed {k[1]} · extract {k[2]}"
                for c, _m, stop, same, k in _g))
show("ⓒ --step-every의 q(판정 도중 · 표 · 산문 × 층 둘) — 청크 · 그래프 · 사전 · 큐 = 시작 전 · 문서 대장 항목 · parsed/ 남음 · "
     "산문은 extract/도", all(stop and same and k[0] and k[1] and (k[2] or not CASES[c][3]) for c, _m, stop, same, k in _e),
     " · ".join(f"{c} 멈춤 {stop} · 흔적 시작 전 {same} · 문서 대장 {k[0]} · parsed {k[1]} · extract {k[2]}"
                for c, _m, stop, same, k in _e))
show("ⓒ 멈춘 뒤 다시 치면 멈추지 않고 끝까지 · 산문은 추출 재사용(LLM 0) · 결과(흔적 · 판정 대장) = 멈추지 않고 넣은 것",
     all(ok and same and (reuse or not CASES[c][3]) for c, _m, ok, reuse, same in _r),
     " · ".join(f"{c}({m}) 성공 {ok} · 추출 재사용 {reuse} · 같음 {same}" for c, m, ok, reuse, same in _r))

for _d in _HINTED:
    (HINTS / f"{_d}.json").unlink(missing_ok=True)
for _dt in (DT, QDT):
    _unregister(_dt)
shutil.rmtree(TMP, ignore_errors=True)
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
done()
