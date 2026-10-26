# -*- coding: utf-8 -*-
"""G6 — **숫자와 기준이 보이게** — 숫자 세 층 · 점수표 · 위치 칸 둘 · 묻는 자리 · 보강 버림 재생 · 거부 묶음 · 영향 범위 (B118).

창작 표본(mock)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 대표 둘(B121 ②ⓒ — 형태 · 층을 한 번씩): 표 CP01(cp ·
process) · 산문 B118SQ(prose 엑셀 사본 · quality · 힌트 개체 Failure). 관문 답은 pty로 — **묻는 줄이 뜬 뒤에** 하나씩 넣는다(Ctrl-C는 그때의 SIGINT).

잠그는 성질:
  ⓐ 숫자 — 문서 한 줄 요약의 수 = 맞춤표의 같은 줄(결말 · 보류 · 소속 대상)의 수 · `show summary`의 층별(골격 · auto · 확정 · 엣지 없는
     노드 · 관계별 엣지) · 문서별(노드 · 엣지 · 보류) 수 = 그래프 · 대장에서 센 수 · `--diff`는 바뀐 줄만(안 바뀐 줄은 같다)
  ⓑ 점수 — `--template` CSV의 행 = 그 문서 대장의 개체 행 · 정답을 채운 표로 맞음 · 틀림 · 빈칸 · 재구축 뒤 같은 표로 같은 수
  (ⓒ 위치 칸은 B131 ④에서 지웠다 — 화면 글자 · 값 표 칸은 md 보고서 시험이 잡는다)
  ⓓ 묻는 자리 — 저장 전 관문 전부에서 `ㅂ` · Ctrl-C · `q`는 멈춤(그래프 · 사전 · 큐 · 청크 지문 = 시작 전) · 빈 Enter · 모르는 답은
     다시 묻는다 · `c` · `ㅊ`만 계속(끝까지 = 멈추지 않고 넣은 것) · 저장 뒤 관문의 멈춤은 남은 머리를 묻지 않는다 · y/N · Y/n 규칙 ·
     `cli/`의 입력은 한 자리(`_screen.ask`)이고 그것을 부르는 것은 `_screen.answer`뿐
  ⓔ 보강 버림 재생 — 패턴 밖이라 버림된 제안(대장 `proposal`)이 config에 그 패턴을 더한 뒤 재구축에서 LLM 0으로 붙는다(`by: replay`) ·
     패턴 그대로면 다시 버림
  ⓕ 거부 묶음 · 영향 범위 — 삼항별 수 = 거부 로그 · 제안 줄을 넣으면 그 묶음이 재구축 뒤 0 · 정의문을 바꾸면 「추출 다시」 · 패턴만
     바꾸면 「LLM 0」
네 벌(ⓖ)은 마감 한 줄의 네 벌 단계가 잰다.
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import csv
import importlib.util
import io
import re
import select
import signal
import tempfile
from collections import Counter

from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _register, _run, _unregister, DT, RFQ   # noqa: F401

import run as RUN                                                  # noqa: E402
from cli import _screen, show_gate, show_score, show_summary as SS   # noqa: E402
from cli.ingest_screen import where_cells                          # noqa: E402
from core.build import extract_ctx, ledger, reconcile as RC        # noqa: E402
from core.state import config_scope as CS                          # noqa: E402
from core.state.world import World                                 # noqa: E402

FX = ROOT / "tests" / "fixtures"
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS
QDT = "b118pq"
SH = "2-4:prose 5:ref *:skip"
TMP = Path(tempfile.mkdtemp(prefix="b118_"))
shutil.copy(RFQ, TMP / "B118SP.xlsx")
shutil.copy(RFQ, TMP / "B118SQ.xlsx")
_HINTED = {"B118SP": [{"surface": f"B118 산문 속성 {k}", "category": "Property"} for k in "가나다"],
           "B118SQ": [{"surface": f"B118 산문 고장 {k}", "category": "Failure"} for k in "가나다"]}
for _d, _e in _HINTED.items():
    (HINTS / f"{_d}.json").write_text(json.dumps({"사양_기계!R8-R17": {"entities": _e, "relations": []}},
                                                ensure_ascii=False), encoding="utf-8")
CASES = {"표 · process": (FX / "raw" / "CP01.xlsx", None, []),          # 대표 둘(B121 ②ⓒ — 형태 · 층을 한 번씩 · 층 호환은
         "산문 · quality": (TMP / "B118SQ.xlsx", QDT, ["--sheets", SH, "--coord", "노칭"])}   # 층 어휘 정적 점검 + 네 벌)
#: 저장 전 관문 수(표 — 선택 · 파싱 · 좌표 · 판정 예고 / 산문 — + 구조 확인(산문 시트마다 — 기대 변경 B132: mock 힌트가 없어도
#: 코드 사다리로 구조가 선다 · 표본은 산문 시트 셋) · 추출 예고 · 추출 결과·판정 예고)
BEFORE = {"표": 4, "산문": 8}
PROMPT = "[계속 c / 멈춤 q".encode("utf-8")                # 구조 확인은 `… / 힌트 <글>]`까지 — 앞부분이 같다
TS = ("created", "at", "first_seen", "last_seen", "last_tried", "last_fp", "attempts", "obsoleted_at", "confirmed_at",
      "parsed_at", "first_ingested_at", "ingested_at", "updated_at", "last_hit")


def _argv(case, *extra):
    src, dt, more = CASES[case]
    return ["ingest-file", str(src), "--allow-mock"] + (["--doc-type", dt] if dt else []) + more + list(extra)


def _doc(case):
    return CASES[case][0].stem


def _base():
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


def _trace():
    """흔적 — 그래프(층마다) · 사전 · 큐 · 청크(id는 이름으로 · 시각 뺌)."""
    nm = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in World().nodes()}
    return json.dumps(_canon({"graph": {lay: {"nodes": [dict(n, id=None) for n in g.nodes.values()], "edges": g.edges}
                                        for lay, g in World().graphs.items()},
                              "dict": store.read(store.DICTIONARY, {}), "queue": store.read(store.QUEUE, []),
                              "chunks": store.read(store.CHUNKS, {})}, nm), ensure_ascii=False, sort_keys=True)


def _drive(argv, answers, wait=25):
    """pty로 `run.py`를 돌리며 **묻는 줄이 뜰 때마다** 다음 답을 넣는다 — `(화면, 넣은 답 수, 묻는 줄 수)`."""
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                                     # pragma: no cover
        os.environ["USE_MOCK"] = "1"
        os.chdir(str(ROOT))
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv])
    out, sent = b"", 0
    while True:
        try:
            r, _w, _x = select.select([fd], [], [], wait)
        except InterruptedError:
            continue
        if not r:
            os.kill(pid, signal.SIGKILL)                             # 답을 기다린 채 멈췄다 — 시험이 끝낸다
            break
        try:
            d = os.read(fd, 4096)
        except OSError:
            break
        if not d:
            break
        out += d
        while sent < out.count(PROMPT) and sent < len(answers):
            os.write(fd, answers[sent])
            sent += 1
    os.waitpid(pid, 0)
    return _screen.strip_ansi(out.decode("utf-8", "replace")), sent, out.count(PROMPT)


C, YES_K, STOP_K, STOP_Q, CTRL_C = "c\n".encode(), "ㅊ\n".encode(), "ㅂ\n".encode(), "q\n".encode(), b"\x03"

# ────────────────────────────────────────────────────────────── ⓐ 숫자 · ⓒ 위치 칸
print("\n■ ⓐ 숫자 세 층 — 문서 한 줄 요약 · 전체 판 · 전후 비교 (표 · 산문 × 층 둘)")
_base()
OUT = {}
for i, case in enumerate(CASES):
    if i == len(CASES) - 1:                 # 마지막 문서 앞의 판(--diff가 그 문서 몫만 바뀐 줄로 낸다)
        with contextlib.redirect_stdout(io.StringIO()):
            SS.main(["--save", "b118_3"])
    OUT[case] = _run(*_argv(case, "-v"))
    assert "[성공]" in OUT[case], (case, OUT[case][-600:])
_ok_a1 = []
for case, out in OUT.items():
    d = _doc(case)
    m = re.search(rf"요약 — {re.escape(d)} — 개체 ([\d,]+) → 새 노드 ([\d,]+) · 기존 연결 ([\d,]+)(?: · 불확실 ([\d,]+))? · "
                  rf"보류 ([\d,]+).*?\| 엣지 ([+-][\d,]+) \|", out)
    mt = RC.for_report(d, ledger.read(d) or {})
    s = mt["요약"]
    got = tuple(int((x or "0").replace(",", "").replace("+", "")) for x in m.groups()) if m else None
    want = (s["개체"], s["새 노드"], s["기존 연결"], s["불확실"], s["보류"], s["엣지"])
    end = next(ln for ln in mt["줄"] if ln["줄"] == "결말(개체 행)")
    cells = {k: n for k, n, _d in end["칸"]}
    _ok_a1.append((case, got == want and want[:3] == (end["전체"], cells.get("새 노드", 0), cells.get("일치", 0))
                   and want[4] == cells.get("보류", 0), got, want))
show("ⓐ 문서 한 줄 요약의 수 = 맞춤표의 같은 줄(결말 · 보류) · 엣지 = 이 문서 몫 (표 · 산문 × 층 둘)",
     all(ok for _c, ok, *_r in _ok_a1), " · ".join(f"{c} {g}" for c, _ok, g, _w in _ok_a1))

_lines, _raw = SS.collect()
_w = World()
_ends = {x for g in _w.graphs.values() for e in g.edges if e.get("status") != "deleted_by_user" for x in (e["src"], e["dst"])}
_lay_ok = all(_raw["층"][lay]["노드"] == len(g.nodes)
              and _raw["층"][lay]["골격"] == sum(1 for n in g.nodes.values() if n.get("status") == "seed")
              and _raw["층"][lay]["auto"] == sum(1 for n in g.nodes.values() if n.get("status") == "auto")
              and _raw["층"][lay]["엣지 없는 노드"] == sum(1 for nid in g.nodes if nid not in _ends)
              and _raw["층"][lay]["엣지"] == dict(Counter(e.get("rel") for e in g.edges if e.get("status") != "deleted_by_user"))
              for lay, g in _w.graphs.items())


def _prov(x, d):
    return any(str(p) == d or str(p).startswith(f"{d}#") for p in x.get("provenance") or [])


_doc_ok = []
for case in CASES:
    d = _doc(case)
    nn = sum(1 for g in _w.graphs.values() for n in g.nodes.values() if _prov(n, d))
    ne = sum(1 for g in _w.graphs.values() for e in g.edges if e.get("status") != "deleted_by_user" and _prov(e, d))
    held = sum(1 for r in (ledger.read(d) or {}).get("rows") or [] if r.get("role") == "entity"
               and RC.hold_reason(r))
    x = _raw["문서"].get(d) or {}
    _doc_ok.append((d, (x.get("노드"), x.get("엣지"), x.get("보류")) == (nn, ne, held), (nn, ne, held)))
show("ⓐ show summary — 층별(노드 · 골격 · auto · 엣지 없는 노드 · 관계별 엣지) · 문서별(노드 · 엣지 · 보류) = 그래프 · 대장에서 센 수",
     _lay_ok and all(ok for _d, ok, _x in _doc_ok) and len(_raw["문서"]) == len(CASES),
     " · ".join(f"{d} {x}" for d, _ok, x in _doc_ok))
_before = SS.load("b118_3")
_dd = SS.diff(_before, _lines)
_same = [k for k, v in _lines if dict(_before).get(k) == v]
_cli = _run("show", "summary", "--diff", "b118_3", "지금")
show("ⓐ --diff는 바뀐 줄만 — 넷째 문서 줄이 더해지고 · 보인 줄은 전부 다르고 · 안 보인 줄은 같다 · 화면 「바뀐 줄 n」 = 같은 수",
     any(k == f"문서 {_doc('산문 · quality')}" and a is None for k, a, _b in _dd)
     and all(a != b for _k, a, b in _dd) and len(_same) + sum(1 for _k, _a, b in _dd if b is not None) == len(_lines)
     and f"바뀐 줄 {len(_dd)}" in _cli, f"바뀐 줄 {len(_dd)} · 같은 줄 {len(_same)}")

# ⓒ 위치 칸(칸 글자 · 잘림 표지)은 지웠다(B131 ④ — 화면 글자는 재지 않는다 · 값 표 칸은 md 보고서 시험(test_judge의 조각 judge2 —
# 값 표 행 = 대장 개체 행 · 잘림 0)이 같은 칸 함수로 잡는다).

# ────────────────────────────────────────────────────────────── ⓑ 점수
print("\n■ ⓑ 점수표 — 정답표 초안 · 채점 · 재구축 뒤 같은 표")
_score_ok = []
for case in ("표 · process",):              # 대표 하나(B121 ②ⓒ — 점수표는 대장 행을 읽는 한 함수 · 형태와 무관)
    d = _doc(case)
    show_score.table_path(d).unlink(missing_ok=True)
    t_out = _run("show", "score", d, "--template")
    rows = show_score.read_table(show_score.table_path(d))
    ents = show_score.entity_rows(d)
    for i, r in enumerate(rows):          # 앞 셋은 맞음 표시(= · ㅇ · o — 엑셀에서 = 한 글자는 수식) · 다음 둘은 틀린 이름 · 나머지 빈칸
        r["정답"] = ("=", "ㅇ", "o")[i] if i < 3 else ("시험 틀린 이름" if i < 5 else "")
    buf = io.StringIO()
    wr = csv.DictWriter(buf, fieldnames=show_score.COLS)
    wr.writeheader()
    wr.writerows(rows)
    show_score.table_path(d).write_bytes(buf.getvalue().encode("utf-8-sig"))
    _score_ok.append([case, len(rows) == len(ents) > 0 and "정답표 초안" in t_out, show_score.score(d)])
_rb = _run("rebuild", "--yes", "--allow-mock")
for item in _score_ok:
    item.append(show_score.score(_doc(item[0])))
show("ⓑ --template CSV의 행 = 대장의 개체 행 · 채운 표로 맞음 3(= · ㅇ · o) · 틀림 2(틀린 이름) · 빈칸 나머지",
     all(ok and a and (a["맞음"], a["틀림"], a["빈칸"]) == (3, 2, len(show_score.entity_rows(_doc(c))) - 5)
         for c, ok, a, _b in _score_ok),
     " · ".join(f"{c} {a and (a['맞음'], a['틀림'], a['빈칸'])}" for c, _ok, a, _b in _score_ok))
show("ⓑ 재구축 뒤 같은 표로 같은 수(위치 · 표기로 맞춘다) · show summary에 정답률 칸",
     "재구축 계획" in _rb and "mock 모드입니다" not in _rb and all(a and b and (a["맞음"], a["틀림"], a["빈칸"]) == (b["맞음"], b["틀림"], b["빈칸"])
                           for _c, _ok, a, b in _score_ok)
     and all(SS.collect()[1]["문서"][_doc(c)]["정답률"] == a["정답률"] for c, _ok, a, _b in _score_ok),
     " · ".join(f"{c} {b and (b['맞음'], b['틀림'], b['빈칸'])}" for c, _ok, _a, b in _score_ok))
for case in CASES:
    show_score.table_path(_doc(case)).unlink(missing_ok=True)
SS.snap_path("b118_3").unlink(missing_ok=True)

# ────────────────────────────────────────────────────────────── ⓓ 묻는 자리
print("\n■ ⓓ 묻는 자리 한 함수 — 계속은 c(ㅊ)만 · 멈춤 q · ㅂ · Ctrl-C · 그 밖은 다시 묻는다")
FULL = {}
for case in CASES:
    _base()
    s0 = _trace()
    _run(*_argv(case))
    FULL[case] = (s0, _trace())
_go = []
for case in CASES:
    _base()
    out, _sent, n = _drive(_argv(case, "--step"), [C, YES_K] * 6)
    _go.append((case, "[성공]" in out and _trace() == FULL[case][1], n))
show("ⓓ c · ㅊ만 계속 — 관문 전부를 c와 ㅊ로 지나면 끝까지 = 멈추지 않고 넣은 것 (표 · 산문 × 층 둘)",
     all(ok for _c, ok, _n in _go), " · ".join(f"{c} 관문 {n}" for c, _ok, n in _go))
_stop = []
for case in CASES:
    k_all = BEFORE[case.split(" · ")[0]]
    # 성질 하나 = 시나리오 하나(B131 ④): 표는 관문마다 멈춤 답 하나씩 돌려(관문 전부 · 답 셋을 함께 덮는다) · 산문은 판정 예고 하나
    plan = ([(k, (STOP_K, CTRL_C, STOP_Q)[(k - 1) % 3]) for k in range(1, k_all + 1)] if case.endswith("process")
            else [(k_all, CTRL_C)])
    for k, s in plan:
        _base()
        out, _sent, n = _drive(_argv(case, "--step"), [C] * (k - 1) + [s])
        _stop.append((case, k, {STOP_K: "ㅂ", CTRL_C: "Ctrl-C", STOP_Q: "q"}[s],
                      "멈춤" in out and "[성공]" not in out and n == k and _trace() == FULL[case][0]))
show("ⓓ 저장 전 관문 전부(process — 관문마다 · quality — 판정 예고)에서 ㅂ · Ctrl-C · q는 멈춤 — 흔적(그래프 · 사전 · 큐 · 청크) = 시작 전",
     all(ok for *_x, ok in _stop) and len(_stop) >= 4 + 1
     and {a for _c, _k, a, _ok in _stop} == {"ㅂ", "Ctrl-C", "q"},
     f"{len(_stop)}회 · 어긋남 {[(c, k, a) for c, k, a, ok in _stop if not ok][:4]}")
_re = []
for case in ("표 · process",):               # 대표 하나(B131 ④ — 다시 묻기는 묻는 한 함수의 성질 · 형태와 무관)
    _base()
    out, sent, n = _drive(_argv(case, "--step"), [b"\n", b"x\n", STOP_K])
    _re.append((case, n == 3 and out.count("다시 친다") == 2 and "멈춤" in out and _trace() == FULL[case][0]))
show("ⓓ 빈 Enter · 모르는 답은 다시 묻는다(계속으로 읽지 않는다) — 같은 관문에서 세 번 묻고 ㅂ에서 멈춤",
     all(ok for _c, ok in _re), str(_re))
_base()
out, _sent, n = _drive(_argv("표 · process", "--step"), [C] * BEFORE["표"] + [STOP_K])
show("ⓓ 저장 뒤 관문의 멈춤 — 「이미 저장됐다(되돌리지 않는다)」 · 남은 머리는 묻지 않는다 · 문서는 끝까지(= 멈추지 않고 넣은 것)",
     "이미 저장됐다" in out and n == BEFORE["표"] + 1 and "[성공]" in out and _trace() == FULL["표 · process"][1],
     f"묻는 줄 {n}")


def _feed(seq, kind):
    it = iter(seq)

    def fake(_p=""):
        x = next(it)
        if isinstance(x, BaseException):
            raise x
        return x
    keep, builtins.input = builtins.input, fake
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return _screen.answer("? ", kind, eof="EOF")
    except KeyboardInterrupt:
        return "올림"
    finally:
        builtins.input = keep


_yn = [_feed(["ㅛ"], "yes"), _feed([""], "yes"), _feed(["n"], "yes"), _feed([KeyboardInterrupt()], "yes"),
       _feed([""], "Yes"), _feed(["ㅛ"], "Yes"), _feed(["ㅜ"], "Yes"), _feed(["zz", "y"], "Yes"),
       _feed([KeyboardInterrupt()], "Yes"), _feed([EOFError()], "go"), _feed([KeyboardInterrupt()], "text")]
show("ⓓ y/N — ㅛ만 예 · Enter · n · Ctrl-C 아니오 / Y/n — Enter · ㅛ 예 · ㅜ 아니오 · 모르는 답 다시 · Ctrl-C 명령 멈춤 / "
     "EOF = 그 자리의 비대화형 규칙 / 글 — Ctrl-C None",
     _yn == [True, False, False, False, True, True, False, True, "올림", "EOF", None], str(_yn))
_inputs, _asks = [], []
for _f in sorted((ROOT / "cli").rglob("*.py")):
    _rel = _f.relative_to(ROOT).as_posix()
    for _n in ast.walk(ast.parse(_f.read_text(encoding="utf-8"))):
        if not isinstance(_n, ast.Call):
            continue
        if isinstance(_n.func, ast.Name) and _n.func.id == "input":
            _inputs.append(_rel)
        if isinstance(_n.func, ast.Attribute) and _n.func.attr == "ask" and getattr(_n.func.value, "id", "") == "_screen":
            _asks.append(_rel)
_in_screen = [ln for ln in (ROOT / "cli" / "_screen.py").read_text(encoding="utf-8").split("\ndef ")
              if ln.startswith("answer(")]
show("ⓓ cli/의 입력은 한 자리 — input()은 _screen.ask 하나 · _screen.ask를 부르는 자리 0(밖) · answer가 그것을 부른다",
     _inputs == ["cli/_screen.py"] and not _asks and _in_screen and "ask(prompt)" in _in_screen[0],
     f"input {_inputs} · 밖의 ask {_asks}")

# ────────────────────────────────────────────────────────────── ⓔ 보강 버림 재생 · ⓕ 거부 묶음 · 영향 범위
print("\n■ ⓔ 연결 보강 버림의 재생 · ⓕ 거부 묶음 · 바꾸면 무엇이 다시 도나")
_spec = importlib.util.spec_from_file_location("fw118", ROOT / "tools" / "four_way.py")
FW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FW)
from core.build import reinforce as RF                             # noqa: E402
from core.state.bootstrap import load_config                       # noqa: E402
_picked = []


def _sel(p):
    """시험 선별 — 첫 후보 · 그 층 패턴에 없는 관계 하나(게이트가 막는다)."""
    cfg = load_config("process")
    pats = {(x["src"], x["rel"], x["dst"]) for x in cfg.get("relation_patterns") or []}
    ent = p["entity"]
    for c in p["candidates"]:
        for r in p["relations"]:
            if r != "mirrors" and (c["category"], r, ent["category"]) not in pats \
                    and (ent["category"], r, c["category"]) not in pats:
                _picked.append((c["category"], r, ent["category"]))
                return {"id": c["id"], "rel": r, "evidence": (p["chunk"].split("\n")[-1] or "").strip()}
    return None


FW._select = _sel
FW._prose(contextlib.redirect_stdout)


def _links():
    return [r for d in FW.PROSE for r in (ledger.read(d) or {}).get("rows") or [] if r.get("role") == "link"]


_rej = [r for r in _links() if r.get("verdict") == "gate_reject" and r.get("proposal")]
_items = show_gate._items()
_gs = show_gate.groups()
_tri = _picked[0] if _picked else None
show("ⓔ 패턴 밖 제안은 버림 — 대장 link 행에 제안(대상 · 관계) · 거부 로그 출처 「보강」",
     bool(_rej) and _rej[0]["proposal"].get("rel") == (_tri or [None, None])[1]
     and any(k == _tri and src.get("보강") for k, _n, src, _v, _l in _gs), f"제안 {[r.get('proposal') for r in _rej]}")
show("ⓕ 거부 묶음의 삼항별 수 = 거부 로그에서 센 수 · 패턴 없음 묶음엔 넣을 줄",
     dict((k, n) for k, n, *_r in _gs) == dict(Counter((x.get("src_cat"), x.get("rel"), x.get("dst_cat")) for x in _items))
     and show_gate.suggest(_tri, {"invalid_pattern": 1}) == json.dumps(
         {"src": _tri[0], "rel": _tri[1], "dst": _tri[2]}, ensure_ascii=False),
     " · ".join(f"{k} {n}" for k, n, *_r in _gs[:4]))


def _rebuild():
    from cli import rebuild as RB
    RF.SELECT = None                                  # 재구축은 판정 없이(재생만 — LLM 0)
    with contextlib.redirect_stdout(io.StringIO()):
        RB.main(["--yes", "--allow-mock"], bootstrap=RUN.cmd_bootstrap, screen=RUN.fresh_screen)
    return dict(RF.LAST)


_l0 = _rebuild()
_still = [r for r in _links() if r.get("verdict") == "gate_reject"]
show("ⓔ 패턴 그대로면 재구축(재생 · LLM 0)에서 다시 버림", bool(_still) and _l0.get("호출", 0) == 0
     and all(r.get("path") == "replay" for r in _still), f"버림 {len(_still)} · 호출 {_l0.get('호출')}")
_cfgp = _P.layers("process", "config.json")
_keep_cfg = _cfgp.read_bytes()
_c = json.loads(_keep_cfg.decode("utf-8"))
_c["relation_patterns"].append(json.loads(show_gate.suggest(_tri, {"invalid_pattern": 1})))
_cfgp.write_text(json.dumps(_c, ensure_ascii=False, indent=1), encoding="utf-8")
_imp1 = CS.lines(CS.impact())
_l1 = _rebuild()
_now = [r for r in _links() if r.get("proposal") or r.get("by") == "replay"]
_att = [r for r in _links() if r.get("verdict") == "attached" and r.get("by") == "replay"]
_edges = {(e["src"], e["rel"], e["dst"]) for g in World().graphs.values() for e in g.edges}
show("ⓔ 제안 줄을 config에 넣고 재구축 — 그 버림이 LLM 0으로 붙는다(대장 attached · by replay · 그래프에 그 관계 엣지)",
     bool(_att) and _l1.get("호출", 0) == 0 and _l1.get("버림→붙음", 0) >= 1
     and any(rel == _tri[1] and r.get("node_id") in (s, d) for r in _att for s, rel, d in _edges),
     f"붙음 {len(_att)} · 호출 {_l1.get('호출')} · 버림→붙음 {_l1.get('버림→붙음')} · 대장 {len(_now)}")
show("ⓕ 패턴만 바꾸면 bootstrap 끝 줄 「재구축 때 LLM 0으로 다시 판정」 · 그 묶음이 재구축 뒤 0",
     any("LLM 0으로 다시 판정" in ln and "process.relation_patterns" in ln for ln in _imp1)
     and not any("추출 다시" in ln for ln in _imp1) and _tri not in {k for k, *_r in show_gate.groups()},
     " | ".join(_imp1))
_c2 = json.loads(_cfgp.read_text(encoding="utf-8"))
_cat = next(iter(_c2["categories"]))
_c2["categories"][_cat] = _c2["categories"][_cat] + " (B118 시험 — 정의문을 바꿨다)"
_cfgp.write_text(json.dumps(_c2, ensure_ascii=False, indent=1), encoding="utf-8")
_imp2 = CS.lines(CS.impact())
show("ⓕ 정의문을 바꾸면 「추출 다시 — 문서 n · 판은 자동」(산문 문서만 센다)",
     any("추출 다시" in ln and "process.categories" in ln for ln in _imp2), " | ".join(_imp2))
_cfgp.write_bytes(_keep_cfg)

# B148 ⑥ — config 작성 가이드 항목 표 = 코드가 아는 층 config 키(빠진 것 0 · 남는 것 0) · 아는 키는 코드가 읽고 · seed 키는 아는 키 안
_gd148 = (ROOT / "docs/가이드/config작성_가이드.md").read_text(encoding="utf-8")
_gk148 = set(re.findall(r"^\| `([a-z_]+)` \|", _gd148[_gd148.index("## 0-b."):_gd148.index("## 0-a.")], re.M))
_ck148 = set(CS.layer_keys())
_sk148 = {k for p_ in list((ROOT / "layers").glob("*/config.json")) + list((ROOT / "tests/fixtures").rglob("layers*/*/config.json"))
          for k in json.loads(p_.read_text(encoding="utf-8")) if not k.startswith("_")}
_src148 = "\n".join(p_.read_text(encoding="utf-8") for d_ in ("core", "cli", "parser", "router")
                     for p_ in (ROOT / d_).rglob("*.py") if p_.name != "config_scope.py")
_un148 = sorted(k for k in _ck148 if f'"{k}"' not in _src148)
show("ⓗ config 작성 가이드 항목 표 = 코드가 아는 층 config 키(`config_scope.layer_keys` — 빠진 것 0 · 남는 것 0) · 아는 키는 코드가 "
     "읽는다 · seed 층 config의 키는 아는 키 안",
     _gk148 == _ck148 and _sk148 <= _ck148 and not _un148,
     f"표 {len(_gk148)} · 코드 {len(_ck148)} · 표만 {sorted(_gk148 - _ck148)} · 코드만 {sorted(_ck148 - _gk148)} · seed 밖 "
     f"{sorted(_sk148 - _ck148)} · 읽는 곳 0 {_un148}")

RF.SELECT = None
for _d in list(_HINTED) + list(FW.PROSE):
    for _p in (HINTS / f"{_d}.json", HINTS / f"{_d}@outline.json", HINTS / f"{_d}@structure.json"):
        _p.unlink(missing_ok=True)
for _dt in (DT, QDT, FW.PROSE_DT):
    _unregister(_dt)
shutil.rmtree(TMP, ignore_errors=True)
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
done()
