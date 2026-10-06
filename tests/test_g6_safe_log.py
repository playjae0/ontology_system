# -*- coding: utf-8 -*-
"""G6 ⑯ 층 이름 · 되돌림 · 화면 전체를 명령 로그로 · 단계 머리 · 결과표 · 재시도 줄 (B99 ①~⑥).

창작 표본(mock)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). **같은 성질을 형태(표·산문) ×
층(둘)에서 잰다**(B99 범용성) — 표본 표:

| 형태 | 층 process | 층 quality |
|---|---|---|
| 표 | CP01(cp) | PFMEA01(pfmea) |
| 산문 | PPT01(ppt_process) · RFQ01(prose_xlsx_basic) | QPPT01(ppt_quality) · RFQ01(prose_q) |

잠그는 성질:
  ⓐ config "layer" ≠ 폴더 → bootstrap·사전 점검·doctor 거부 · 고치기 전 상태에서도 빌더가 폴더 이름을 써서 소실 0
  ⓑ 한 빌드에서 같은 층 그래프를 둘째로 열려 하면 명시적 실패
  ⓒ 구축 중 예외(일반 · KeyboardInterrupt) → 큐·청크 되돌림 · 그래프·사전 미저장 · 재실행 뒤 유령 큐 0
  ⓓ 진입점 15곳 전부 로그 · 화면 줄 ⊆ 로그 줄(표 인입 · 산문 인입 · register generate) · 실행 머리·끝으로 갈림
  ⓔ 사용량 줄의 문서 — 한 실행 두 문서 → 로그에서 센 문서별 합계 = 결과표의 합계
  ⓕ 단계 머리·끝 줄이 --step 없이 표·산문 둘 다 · --step 화면과 같은 머리
  ⓖ 결과표 — 층별 합(집이 다른 층인 노드가 셈에 든다) · 이번/이전 큐 구분 (표·산문 × 층)
  ⓗ 재시도 줄 — 연결 · 상한 도달 · 그래프 그대로라 건너뜀
"""
from __future__ import annotations

import glob
import re
import subprocess as sp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401
from g6_common import _register, _unregister, RFQ    # noqa: E402

from core.build import entry as EN                    # noqa: E402
from core.state import catalog, integrity            # noqa: E402

RAW = ROOT / "tests" / "fixtures" / "raw"
MATRIX = [("표", "process", "CP01"), ("표", "quality", "PFMEA01"),
          ("산문", "process", "PPT01"), ("산문", "quality", "QPPT01")]


def _run(*a, mod=None, stdin=sp.DEVNULL, env=None):
    cmd = [sys.executable, "-m", mod, *a] if mod else [sys.executable, str(ROOT / "run.py"), *a]
    r = sp.run(cmd, cwd=str(ROOT), env={**os.environ, "USE_MOCK": "1", **(env or {})},
               capture_output=True, text=True, stdin=stdin, timeout=900)
    return r.returncode, r.stdout + r.stderr


def _fresh():
    init.init(fresh_=True)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


def _counts():
    out = {}
    for lay in ("process", "quality"):
        g = open_graph(lay)
        out[lay] = len(g.nodes)
    found, _g = integrity.state_scan()
    return out, integrity.count(found)


def _set_layer_name(lay, value):
    p = _P.layers(lay, "config.json")
    c = json.loads(p.read_text(encoding="utf-8"))
    c["layer"] = value
    p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


print("\n■ B99 ① 층 이름 = 폴더 이름 (형태 × 층)")
_ref, _bad = {}, {}
for form, lay, doc in MATRIX:
    _fresh()
    run_document(load(doc))
    _ref[doc] = _counts()
    _fresh()
    _set_layer_name(lay, lay + "_다른이름")
    run_document(load(doc))
    _bad[doc] = _counts()
_probs = [t for t, _m in catalog.problems()]
_rc_b, _o_b = _run("bootstrap")
_rc_i, _o_i = _run("ingest-file", str(RAW / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock")
_dr = sp.run([sys.executable, str(ROOT / "doctor.py"), "--quick"], cwd=str(ROOT),
             env={**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True,
             stdin=sp.DEVNULL, timeout=900)
show("ⓐ config \"layer\" ≠ 폴더 → bootstrap·사전 점검·doctor 거부 · 표·산문 × 층 넷 모두 소실 0(정상 config와 같다)",
     all(_bad[d] == _ref[d] and _bad[d][1] == (0, 0, 0) for _f, _l, d in MATRIX)
     and "ⓕ" in _probs and _rc_b != 0 and "폴더 이름 'quality'로" in _o_b
     and "**공통 config**에서 멈춘다" in _o_i and "폴더 이름" in _o_i
     and "층 config \"layer\" = 폴더 이름" in _dr.stdout and "quality_다른이름" in _dr.stdout,
     " · ".join(f"{f}×{l} {_bad[d][0]}" for f, l, d in MATRIX))

_fresh()
from core.build.build import Builder         # noqa: E402
_b = Builder(open_graph("process"), load_config("process"), None, "B99X", "process")
_b.for_layer("quality")
_b.subs["다른키"] = _b.subs.pop("quality")    # 키가 폴더 이름과 어긋난 상태(결함 주입)
try:
    _b.for_layer("quality")
    _twice = None
except RuntimeError as e:
    _twice = str(e)
show("ⓑ 한 빌드에서 같은 층 그래프를 둘째로 열려 하면 명시적 실패([결함])",
     bool(_twice) and "[결함]" in _twice and "두 번" in _twice, (_twice or "")[:60])

print("\n■ B99 ② 어떤 이유로 멈춰도 되돌린다 (형태 × 층)")
_ok_c = []
_keep_fin = EN._finish_build
for (form, lay, doc), exc in zip(MATRIX, (RuntimeError, KeyboardInterrupt,
                                          RuntimeError, KeyboardInterrupt)):
    _fresh()
    _q0 = json.dumps(store.read(store.QUEUE, []), sort_keys=True)
    _d0 = json.dumps(Dictionary.open().entries(), sort_keys=True)
    _n0 = _counts()[0]

    def _boom(*a, _e=exc, **k):
        raise _e("시험 주입 — 구축 실패")
    EN._finish_build = _boom
    try:
        run_document(load(doc))
        _got = "예외 없음"
    except BaseException as e:            # noqa: BLE001 — KeyboardInterrupt까지 받는다
        _got = type(e).__name__
    finally:
        EN._finish_build = _keep_fin
    _same = (json.dumps(store.read(store.QUEUE, []), sort_keys=True) == _q0
             and json.dumps(Dictionary.open().entries(), sort_keys=True) == _d0
             and _counts()[0] == _n0)
    run_document(load(doc))                 # 이어서 재실행 — 성공
    _ok_c.append((form, lay, _got == exc.__name__, _same, _counts()[1]))
show("ⓒ 구축 중 예외(일반 · Ctrl-C) → 큐·사전·그래프 그대로 · 재실행 뒤 유령 큐·사전·엣지 0 (표·산문 × 층)",
     all(g and s and c == (0, 0, 0) for _f, _l, g, s, c in _ok_c),
     " · ".join(f"{f}×{l} {g and s} {c}" for f, l, g, s, c in _ok_c))

print("\n■ B99 ③ 화면 전체를 명령 로그로")
_fresh()
_register()
_register("quality", "prose_q")
_logs = _P.work("logs")


def _screen_in_log(out, cmd):
    """화면 줄(색 뺀 것)이 그 명령의 로그(화면 복사 줄)에 전부 있나."""
    f = sorted(glob.glob(str(_logs / f"{cmd}_*.log")))
    if not f:
        return False, "로그 없음"
    txt = Path(f[-1]).read_text(encoding="utf-8")
    got = {re.sub(r"^\S+ \S+ INFO\s+onto\.screen  ", "", l) for l in txt.splitlines()
           if " onto.screen  " in l}
    miss = [l for l in out.splitlines() if l.strip() and l not in got]
    return not miss, miss[:2]


_c1, _o1 = _run("ingest-file", str(RAW / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock")
_t1 = _screen_in_log(_o1, "ingest-file")
_c2, _o2 = _run("ingest-file", str(RFQ), "--doc-type", "prose_q", "--allow-mock", "--sheets", "auto")
_t2 = _screen_in_log(_o2, "ingest-file")
_c3, _o3 = _run("generate", "b99gen", "quality", str(RAW / "TOC01.xlsx"), "--allow-mock",
                mod="cli.register")
_t3 = _screen_in_log(_o3, "register")
_ilog = Path(sorted(glob.glob(str(_logs / "ingest-file_*.log")))[-1]).read_text(encoding="utf-8")
_ENTRY = [(None, ["show", "knobs"], "show"), ("cli.export", [], "export"),
          ("cli.extract", [], "extract"), ("cli.golden", [], "golden"),
          ("cli.ingest", [], "ingest-dir"), ("cli.llmcheck", [], "llm-check"),
          ("cli.ops", [], "ops"), ("cli.parse", [], "parse"), ("cli.platform", [], "platform"),
          ("cli.query", [], "query"), ("cli.scan", [], "scan"), ("cli.show", [], "show"),
          ("cli.skeleton", [], "skeleton-confirm"), ("cli.register", [], "register")]
_miss_e = []
for mod, argv, name in _ENTRY:
    _run(*argv, mod=mod)
    f = sorted(glob.glob(str(_logs / f"{name}_*.log")))
    t = Path(f[-1]).read_text(encoding="utf-8") if f else ""
    if "===== 실행 시작" not in t or "===== 실행 끝" not in t:
        _miss_e.append(mod or "run.py")
sp.run([sys.executable, str(ROOT / "doctor.py"), "--env"], cwd=str(ROOT),          # 클린을 만들며 로그를 지운다
       env={**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True,
       stdin=sp.DEVNULL, timeout=900)
_dlog = sorted(glob.glob(str(_logs / "doctor_*.log")))
_dt = Path(_dlog[-1]).read_text(encoding="utf-8") if _dlog else ""
if "===== 실행 시작" not in _dt:
    _miss_e.append("doctor.py")
shutil.rmtree(_P.registry("review", "b99gen"), ignore_errors=True)
show("ⓓ 진입점 15곳 전부 로그(머리·끝) · 화면 줄 ⊆ 로그 줄(표 인입 · 산문 인입 · register generate) · "
     "같은 날 두 실행이 머리·끝 줄로 갈린다",
     not _miss_e and _t1[0] and _t2[0] and _t3[0]
     and _ilog.count("===== 실행 시작") >= 2 and _ilog.count("===== 실행 끝") >= 2,
     f"빠진 진입점 {_miss_e} · 표 {_t1[1]} · 산문 {_t2[1]} · 등록 {_t3[1]}")

_us = sp.run([sys.executable, "-c", """
import sys; sys.argv=["x"]
from cli import _entry
from core.llm import gateway
def main(argv):
    for doc, n in (("B99A", 3), ("B99B", 2)):
        _entry.doc_header(doc, "t", "table")
        for i in range(n):
            gateway._account("judge", {"usage": {"prompt_tokens": 10 + i, "completion_tokens": 2,
                                                  "total_tokens": 12 + i}})
    print({d: sum(u["prompt"] for u in gateway.usage_by(d).values()) for d in ("B99A", "B99B")})
    return 0
sys.exit(_entry.run("b99usage", main, []))
"""], cwd=str(ROOT), env={**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True)
_ulog = Path(sorted(glob.glob(str(_logs / "b99usage_*.log")))[-1]).read_text(encoding="utf-8")
_bydoc = {}
for m in re.finditer(r"LLM 사용량 .* · 문서 (\S+) — 입력 (\d+)", _ulog):
    _bydoc[m[1]] = _bydoc.get(m[1], 0) + int(m[2])
show("ⓔ 사용량 줄에 문서가 달린다 — 한 실행 두 문서 → 로그에서 센 문서별 입력 합계 = 결과표(usage_by)",
     _bydoc == {"B99A": 33, "B99B": 21} and str({"B99A": 33, "B99B": 21}) in _us.stdout, _bydoc)

print("\n■ B99 ④ 단계 머리·끝 줄 (표 · 산문)")
_heads_t = re.findall(r"^── \[(\d+)/7\] (\S+)", _o1, re.M)
_heads_p = re.findall(r"^── \[(\d+)/8\] (\S+)", _o2, re.M)
_ends = len(re.findall(r"^   └ [\d.]+초 · LLM 호출 \d+ · 토큰", _o1, re.M))
from cli import ingest_screen as _SCR       # noqa: E402
import contextlib as _ctx, io as _io        # noqa: E401,E402
_b1, _b2 = _io.StringIO(), _io.StringIO()
with _ctx.redirect_stdout(_b1):
    _SCR._step_gate(2, "x", ask=False)
import builtins as _bi                      # noqa: E402
_keep_in, _bi.input = _bi.input, (lambda *_a: "c")     # 시험 주입 — 사람이 c를 친다
try:
    with _ctx.redirect_stdout(_b2):
        _SCR._step_gate(2, "x", ask=True)
finally:
    _bi.input = _keep_in
show("ⓕ 단계 머리·끝 줄이 --step 없이 표(7)·산문(8) 둘 다 · --step 화면과 같은 머리(한 함수)",
     len(_heads_t) == 7 and len(_heads_p) == 8 and _ends >= 7
     and "[사전 점검]" in _o1 and "[마무리]" in _o1
     and _b1.getvalue().strip().splitlines()[0] in _b2.getvalue(),
     f"표 {[h[1] for h in _heads_t]} · 산문 {len(_heads_p)}")

print("\n■ B99 ⑤ 결과표 (형태 × 층)")
_res = {}
for form, lay, doc in MATRIX:
    _fresh()
    r1 = []
    EN.run_document(load(doc), notice=r1.append)
    a = next(x for x in r1 if x.get("단계") == "끝")
    r2 = []
    EN.run_document(load(doc), notice=r2.append)
    b = next(x for x in r2 if x.get("단계") == "끝")
    led = json.loads((_P.work("ingest_log") / f"{doc}.json").read_text(encoding="utf-8"))
    _res[(form, lay)] = (a["노드"] == sum(d["노드"] for d in a["결과"]["층"].values()),
                         sum(a["결과"]["큐 이전"].values()) == 0
                         # 재인입이 내리지 않는 kind(auto_node·uncertain_match)는 「이전 실행이 남긴 것」이다
                         and sum(b["결과"]["큐 이전"].values()) == sum(
                             n for k, n in a["결과"]["큐 이번"].items()
                             if k in ("auto_node", "uncertain_match")),
                         "result" in led, len(a["결과"]["층"]))
_cross = any(n > 1 for *_x, n in _res.values())
show("ⓖ 결과표 — 끝 줄 노드 = 층별 합 · 집이 다른 층인 노드가 셈에 든다 · 이번/이전 큐 구분 · 대장에 남는다 "
     "(표·산문 × 층)",
     all(a and b and c for a, b, c, _n in _res.values()) and _cross,
     " · ".join(f"{f}×{l} 층 {v[3]}" for (f, l), v in _res.items()))

print("\n■ B99 ⑥ 재시도 줄")
init.init(fresh_=True)               # 골격 없이 넣는다 — 좌표가 전부 orphan_anchor
run_document(load("CP01"))
_qa = store.read(store.QUEUE, [])
_oa = [x for x in _qa if x["kind"] == "orphan_anchor"]
_oa[0]["attempts"] = 5               # 상한 도달 주입
store.write(store.QUEUE, _qa)
bootstrap("process", echo=False)     # 그래프가 자랐다 — 재시도가 의미를 갖는다
from core.build import retry as RT    # noqa: E402
_f1 = finalize()
_l1 = dict(RT.LAST)
finalize()                           # 연결이 그래프를 바꿨다 — 한 번 더 돈다
_f2 = finalize()                     # 그래프 그대로 — 건너뛴다
_l2 = dict(RT.LAST)
show("ⓗ 재시도 줄 — 이번에 연결 · 상한 도달 · 그래프 그대로라 건너뜀 · 결과를 버리지 않는다",
     sum(_l1["healed"].values()) > 0 and _l1["capped"] == 1 and _l2["same"] > 0
     and "이번에 연결" in _f1["retry_line"] and "건너뜀" in _f2["retry_line"],
     f"{_f1['retry_line']} / {_f2['retry_line']}")
_unregister()
_unregister("prose_q")
init.init(fresh_=True)

done()
