# -*- coding: utf-8 -*-
"""G6 ㉘ 운영 상태 폴더 — 점검 · 시험은 쓰지 않는다 · 지우는 손이 루트를 확인한다 · 재구축은 지우기 전에 점검하고
끊기면 계획 파일에서 이어 간다 (B111).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) × 층(process ·
quality): 표 CP01(cp · process) · PFMEA01(pfmea · quality) · 산문 RFQ01(prose 엑셀 · process · 문서 좌표 노칭).
**운영 루트 모양 폴더** = 그 셋을 넣은 mock 루트의 사본(data/ · work/ · registry/ · layers/ · raw/ 채움) + `llm.json`
실호출. **운영 셸** = 격리 환경에서 `USE_MOCK` · 설정 판독 끔 · mock 세계의 시험 문을 걷고 `ONTO_HOME`을 그 폴더로 ·
`HOME`은 빈 임시 폴더(운영자의 `~/.onto/llm.json`을 물지 않는다).

잠그는 성질:
  ⓐ 운영 루트 불변: 그 폴더를 `ONTO_HOME`으로 `doctor.py --quick` — 두 갈래(설정 파일 `"USE_MOCK": 0` · 환경변수
     `USE_MOCK=0`) ⇒ 폴더 전체 지문(파일 목록 + 바이트 해시 · 락 파일 포함) 전후 같다 · rc 0 · 머리 상태 줄이 그 폴더 ·
     모드 실호출 / 격리는 한 함수다 — 회귀 스위트 전부 · doctor · 네 벌이 그 함수에 닿고(소스 대조) 정의는 하나
  ⓑ 클린 확인: 그 폴더의 `init --fresh --all` — 비대화형 거부(지문 불변 · 다음 줄 `--yes` · rc 1) · 터미널 `n`(지문 불변) ·
     `--yes`(지금의 클린 — ③④ 빈 상태 · 보존 여섯 0 · ②등록 · 층 · 원본 · 설정 바이트 그대로) / mock 루트의 클린은 묻지
     않는다 / 기본 `init --fresh`는 묻지 않고 보존 여섯을 남긴다 / 확인 없이 부른 클린(코드)은 `CleanRefused` · 쓰기 0
  ⓒ 재구축 사전 점검: 실호출 + 설정 없음으로 `rebuild --yes` ⇒ 지우기 전에 멈춤(사전 점검 문면 + 「지우기 전에 멈췄다 —
     그래프 그대로」 + 다음 줄 llm-check · rc 1) · 지문 불변 · 계획 파일 0
  ⓓ 이어 가기: 끊기지 않은 재구축이 기준(mock은 끝까지 · 계획 파일 「끝」) / 둘째 문서 도중 `kill -9` · 중단(KeyboardInterrupt) ·
     문서 하나 실패 · 끊긴 뒤의 사전 점검 실패(지문 불변) 각각 ⇒ 다음 계획이 셋 전부 + 「지난 재구축이 끝나지 않았다 —
     계획 파일에서 이어 간다 · 문서 대장 k건은 그 도중의 것」 · `--yes` 뒤 그래프 · 사전 · 큐가 기준과 같다 · 「끝」 →
     다음 계획은 문서 대장에서(이어 간다는 줄 0)

지문의 「명령 로그 제외」(ⓑ ⓒ ⓓ의 멈춤): 사람이 친 운영 명령은 그 실행의 로그를 남긴다(화면 = 로그 · B99 ③) — 지문은
`work/logs/`를 뺀 전체이고, 로그 쪽은 바뀐 것이 그 명령의 로그 파일뿐인지 따로 본다. ⓐ의 doctor는 로그까지 0이다.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다(격리 포함)
from g65_common import _P, done   # noqa: F401
from g6_common import DT, RFQ, _register, _unregister   # noqa: E402 — 산문 엑셀 표본 · 등록

import run as RUN                                    # noqa: E402
from cli import _screen as SCR, ingest as IG          # noqa: E402
from cli import rebuild as RB                         # noqa: E402
from core.llm import gateway                          # noqa: E402
from core.state.world import World                    # noqa: E402

RAWFX = ROOT / "tests" / "fixtures" / "raw"
X = "노칭"                                            # 산문의 문서 좌표
SHEETS = "2-4:prose 5:ref *:skip"
TMP = Path(tempfile.mkdtemp(prefix="b111_"))
(TMP / "home").mkdir()
ISO = dict(os.environ)                               # 이 프로세스는 격리 환경이다(도우미가 부른 gateway.isolate)


def _quiet(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return f(*a, **k)


def _sp(*argv, env=None, script="run.py"):
    r = subprocess.run([sys.executable, str(ROOT / script), *argv], cwd=str(ROOT), env=env or ISO,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def _pty(argv, env, answers):
    """터미널로 — 답을 넣는다(관문은 tty에서만 묻는다)."""
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                     # pragma: no cover
        os.chdir(str(ROOT))
        os.execve(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv], env)
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    _pid, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st), SCR.strip_ansi(out.decode("utf-8", "replace"))


def _shell(home, *, env_var=False):
    """운영 셸 — 격리를 걷고 `ONTO_HOME`을 그 폴더로(`env_var`면 모드를 환경변수 `USE_MOCK=0`으로)."""
    env = {k: v for k, v in ISO.items()
           if k not in ("USE_MOCK", gateway.CONFIG_ENV) and k not in gateway.MOCK_WORLD_ENV}
    env.update(ONTO_HOME=str(home), HOME=str(TMP / "home"), NO_COLOR="1")
    if (ROOT / gateway.CONFIG_PATHS[1]).exists():    # 코드 폴더의 설정 파일이 먼저 잡히지 않게 — 이 폴더의 것만
        env[gateway.CONFIG_ENV] = str(Path(home) / "llm.json")
    if env_var:
        env["USE_MOCK"] = "0"
    return env


def _fp(home, logs=True):
    """폴더 지문 — `{상대 경로: sha256}`(락 파일 포함 — 파일 목록 그대로) · `logs=False`면 `work/logs/`를 뺀다."""
    home = Path(home)
    return {p.relative_to(home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(home.rglob("*")) if p.is_file()
            and (logs or not p.relative_to(home).as_posix().startswith("work/logs/"))}


def _fpdiff(a, b):
    ch = sorted(k for k in a if k in b and a[k] != b[k])
    return f"바뀜 {ch[:3]} · 더함 {sorted(set(b) - set(a))[:3]} · 사라짐 {sorted(set(a) - set(b))[:3]}"


def _logs_only(a, b, cmd):
    """로그 쪽 — 바뀐 것이 그 명령의 로그 파일뿐인가."""
    moved = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
    return all(k.startswith(f"work/logs/{cmd}_") for k in moved)


def _snap():
    """canonical 기준 상태 — 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 사전(표기 → 이름) · 큐(kind ·
    문서 · payload — id는 이름으로 · 시각은 뺀다)."""
    w = World()
    nm = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in w.nodes()}

    def canon(x):
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items() if k not in ("created", "at", "first_seen", "last_seen")}
        if isinstance(x, list):
            return [canon(v) for v in x]
        return nm.get(x, x) if isinstance(x, str) else x
    return {"노드": sorted(f"{lay}:{n['canonical']}|{n['category']}|{n['status']}|"
                          + json.dumps(n.get("attrs") or {}, ensure_ascii=False, sort_keys=True)
                          for lay, n in w.nodes()),
            "별칭": sorted(f"{lay}:{n['canonical']}|{a['surface']}|{a.get('by')}" for lay, n in w.nodes()
                          for a in n.get("aliases") or []),
            "엣지": sorted(f"{e['rel']}|{nm.get(e['src'], e['src'])}|{nm.get(e['dst'], e['dst'])}|{e.get('status')}"
                          for g in w.graphs.values() for e in g.edges),
            "사전": json.dumps(canon(store.read(store.DICTIONARY, {})), ensure_ascii=False, sort_keys=True),
            "큐": sorted(json.dumps([x["kind"], x.get("doc_id"), canon(x.get("payload")),
                                    (x.get("resolution") or {}).get("decision")], ensure_ascii=False, sort_keys=True)
                        for x in store.read(store.QUEUE, []))}


def _diff(a, b):
    return {k: len(a[k]) - len(b[k]) if isinstance(a[k], list) else "다름" for k in a if a[k] != b[k]}


def _sizes(s):
    return " · ".join(f"{k} {len(v)}" for k, v in s.items() if isinstance(v, list))


def _say(out, *keys):
    """화면에서 그 줄들만 — 보고에 싣는다."""
    for ln in out.splitlines():
        if any(k in ln for k in keys):
            print(f"      {ln.rstrip()}")


# ────────────────────────────────────────────────────────────── 바닥
print("\n■ B111 바닥 — 표 · 산문 × 층 둘 (CP01 · PFMEA01 · RFQ01) — mock 루트에서 넣고 사본을 운영 루트 모양으로")
_quiet(init.init, fresh_=True, all_=True)
_quiet(RUN.cmd_bootstrap, [])
_register("process", DT)
RAWH = _P.raw()
_P.ensure(RAWH)
for _f in ("CP01.xlsx", "PFMEA01.xlsx"):
    shutil.copy(RAWFX / _f, RAWH / _f)
shutil.copy(RFQ, RAWH / "RFQ01.xlsx")
DOCS = [("CP01", "cp", None, None), ("PFMEA01", "pfmea", None, None), ("RFQ01", DT, SHEETS, X)]
_first = {did: _quiet(IG.ingest_file, str(RAWH / f"{did}.xlsx"), dt, ask=False, sheets=sh, coord=co).get("status")
          for did, dt, sh, co in DOCS}
BASE = TMP / "base"
shutil.copytree(_P.home(), BASE)
print(f"  첫 인입 — {_first} · 문서 대장 {list(store.read(store.DOC_REGISTRY, {}))}")


def _restore():
    """mock 루트를 바닥으로 — 재구축 하나하나가 같은 자리에서 시작한다."""
    shutil.rmtree(_P.home(), ignore_errors=True)
    shutil.copytree(BASE, _P.home())


T = TMP / "ops"                                      # 운영 루트 모양
shutil.copytree(BASE, T)
(T / "llm.json").write_text(json.dumps({"USE_MOCK": 0}) + "\n", encoding="utf-8")
_tops = sorted({k.split("/")[0] for k in _fp(T)})
print(f"  운영 루트 모양 {T.name}/ — {_tops} · 파일 {len(_fp(T))}")
if not (all(v == "성공" for v in _first.values()) and {"data", "work", "registry", "layers", "raw"} <= set(_tops)):
    raise SystemExit("바닥을 세우지 못했다 — 첫 인입 · 폴더 모양 (위 줄)")

# ────────────────────────────────────────────────────────────── ⓐ
print("\n■ B111 ① 점검은 운영 상태 폴더를 읽기만 한다 — doctor --quick 두 갈래")
for _label, _env_var, _cfg in (("설정 파일 \"USE_MOCK\": 0", False, {"USE_MOCK": 0}),
                               ("환경변수 USE_MOCK=0", True, {"CHAT_MODEL": "시험"})):
    (T / "llm.json").write_text(json.dumps(_cfg) + "\n", encoding="utf-8")
    _f0 = _fp(T)
    _t0 = time.time()
    _rc, _out = _sp("--quick", env=_shell(T, env_var=_env_var), script="doctor.py")
    _f1 = _fp(T)
    _head = next((ln.strip() for ln in _out.splitlines() if ln.strip().startswith("상태 폴더 ")), "")
    show(f"ⓐ {_label} — 폴더 전체 지문 전후 같다(파일 {len(_f0)} · 락 포함 · 로그 포함) · rc 0 · 머리 상태 줄 = 그 폴더 · "
         "모드 실호출",
         _rc == 0 and _f0 == _f1 and _head.startswith(f"상태 폴더 {T.resolve()} ") and "모드 실호출" in _head,
         f"rc {_rc} · {time.time() - _t0:.0f}초 · 지문 {'같음' if _f0 == _f1 else _fpdiff(_f0, _f1)}")
    print(f"      {_head}")
    _say(_out, "운영 명령의 모드", "결과:")
(T / "llm.json").write_text(json.dumps({"USE_MOCK": 0}) + "\n", encoding="utf-8")


def _first_import(src):
    """(첫 프로젝트 import의 (줄, 모듈), 첫 `isolate()` 호출 줄)."""
    t = ast.parse(src)
    imps = sorted(((n.lineno, m) for n in ast.walk(t) if isinstance(n, (ast.Import, ast.ImportFrom))
                   for m in ([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""])),
                  key=lambda x: x[0])
    iso = min((n.lineno for n in ast.walk(t) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == "isolate"), default=None)
    return imps, iso


_helpers = {p.stem for p in (ROOT / "tests").glob("*_common.py")
            if _first_import(p.read_text(encoding="utf-8"))[1] is not None}
_proj = ("core", "cli", "parser", "router", "run", "doctor")
_bad = []
import doctor as _DR                                  # noqa: E402 — 스위트 목록 (import만 — 진입점은 돌지 않는다)
for _name, _n, _w in _DR.SUITES:
    _src = (ROOT / "tests" / f"{_name}.py").read_text(encoding="utf-8")
    _imps, _iso = _first_import(_src)
    _pi = [(ln, m) for ln, m in _imps if m.split(".")[0] in _proj or m in _helpers]
    _first_p = next(((ln, m) for ln, m in _pi if m not in ("core.llm", "core.llm.gateway")), None)
    _ok = ((_first_p and _first_p[1] in _helpers) or (_iso and (not _first_p or _iso < _first_p[0]))
           or (not _pi and "run.py" not in _src and "doctor.py" not in _src))
    if not _ok:
        _bad.append(_name)
_defs = [p for p in list(ROOT.glob("*.py")) + list(ROOT.glob("*/**/*.py"))
         if "def " + "isolated_env(" in p.read_text(encoding="utf-8", errors="replace")]
_dsrc = (ROOT / "doctor.py").read_text(encoding="utf-8")
_fsrc = (ROOT / "tools" / "four_way.py").read_text(encoding="utf-8")
show("ⓐ 격리는 한 함수 — 회귀 스위트 전부가 상태를 열기 전에 닿는다(도우미 · 직접 · 상태를 열지 않는 것) · doctor 진입 · "
     "네 벌 · 정의 하나(`core/llm/gateway.py`)",
     not _bad and [p.relative_to(ROOT).as_posix() for p in _defs] == ["core/llm/gateway.py"]
     and "gateway.isolate()" in _dsrc and "gateway.isolated_env()" in _fsrc,
     f"스위트 {len(_DR.SUITES)} · 어긋남 {_bad} · 도우미 {sorted(_helpers)} · 정의 {[p.name for p in _defs]}")

# ────────────────────────────────────────────────────────────── ⓑ
print("\n■ B111 ① 지우는 손이 루트를 확인한다 — init --fresh --all")
_f0, _l0 = _fp(T, logs=False), _fp(T)
_rc, _out = _sp("init", "--fresh", "--all", env=_shell(T))
_f1, _l1 = _fp(T, logs=False), _fp(T)
show("ⓑ 운영 루트 · 비대화형 — 거부(rc 1 · 다음 줄 `--yes`) · 지울 것과 크기를 말한다 · 지문 불변(명령 로그 제외 · 로그는 그 "
     "명령의 것만)",
     _rc == 1 and _f0 == _f1 and _logs_only(_l0, _l1, "init") and "python run.py init --fresh --all --yes" in _out
     and any("지울 것 —" in ln and "판정 대장" in ln and "별칭 대장" in ln for ln in _out.splitlines())
     and f"운영 상태 폴더의 클린이다 — {T.resolve()}" in _out and "지우지 않았다" in _out,
     f"rc {_rc} · 지문 {'같음' if _f0 == _f1 else _fpdiff(_f0, _f1)}")
_say(_out, "[init --fresh --all]", "비대화형")
_rc, _out = _pty(["init", "--fresh", "--all"], _shell(T), "n\n")
_f2 = _fp(T, logs=False)
show("ⓑ 운영 루트 · 터미널 `n` — 묻고 지우지 않는다 · 지문 불변(명령 로그 제외)",
     _rc == 1 and _f0 == _f2 and "실행할까? [y/N]" in _out and "지우지 않았다" in _out,
     f"rc {_rc} · 지문 {'같음' if _f0 == _f2 else _fpdiff(_f0, _f2)}")
T3 = TMP / "ops_yes"
shutil.copytree(T, T3)
_b3 = _fp(T3)
_rc, _out = _sp("init", "--fresh", "--all", "--yes", env=_shell(T3))
_a3 = _fp(T3)
_keep = {k: h for k, h in _b3.items() if k.split("/")[0] in ("registry", "layers", "raw") or k == "llm.json"}
_left = sorted(k for k in _a3 if k.split("/")[0] in ("work", "export") and not k.startswith("work/logs/init_")
               and not k.endswith(".lock"))
_kept6 = [l for l, p in init.kept() if any(k.startswith(Path(p).relative_to(_P.home()).as_posix()) for k in _a3
                                           if not k.startswith("work/logs/init_"))]
_reg3 = json.loads((T3 / "data" / "doc_registry.json").read_text(encoding="utf-8"))
show("ⓑ 운영 루트 · `--yes` — 지금의 클린(보존 여섯 0 · ③ 빈 상태 · ④⑤ 그 명령의 로그뿐) · ②등록 · 층 · 원본 · 설정은 바이트 그대로",
     _rc == 0 and all(_a3.get(k) == h for k, h in _keep.items()) and not _left and not _kept6 and _reg3 == {},
     f"rc {_rc} · 남긴 ②·층·원본·설정 {sum(_a3.get(k) == h for k, h in _keep.items())}/{len(_keep)} · ④⑤ 남음 {_left[:3]} · "
     f"보존 여섯 남음 {_kept6} · 문서 대장 {_reg3}")
T2 = TMP / "ops_fresh"
shutil.copytree(T, T2)
_KREL = {l: Path(p).relative_to(_P.home()).as_posix() for l, p in init.kept()}
_b2 = _fp(T2)
_rc, _out = _sp("init", "--fresh", env=_shell(T2))                  # 시험 대상: 기본 fresh
_a2 = _fp(T2)
_reg2 = json.loads((T2 / "data" / "doc_registry.json").read_text(encoding="utf-8"))
_had = [l for l, r in _KREL.items() if any(k == r or k.startswith(r + "/") for k in _b2)]
_held = all(_a2.get(k) == h for k, h in _b2.items() for r in _KREL.values()
            if (k == r or k.startswith(r + "/")) and not k.startswith("work/logs/"))
show("ⓑ 운영 루트 · 기본 `init --fresh` — 묻지 않는다 · 보존 여섯(있던 것)이 바이트 그대로 남고 문서 대장은 빈다(재구축의 바닥 — "
     "지금 그대로)",
     _rc == 0 and "운영 상태 폴더의 클린" not in _out and _held and len(_had) >= 4 and _reg2 == {},
     f"rc {_rc} · 있던 보존 {_had} · 바이트 그대로 {_held}")
_rc, _out = _sp("init", "--fresh", "--all")
show("ⓑ mock 루트의 클린은 묻지 않는다(회귀 바닥 — 지금 그대로)",
     _rc == 0 and "운영 상태 폴더의 클린" not in _out and "[init --fresh --all] 지운 것(전부 — 클린)" in _out,
     next((ln for ln in _out.splitlines() if "지운 것" in ln), _out[-120:]))
_restore()
_fm0 = _fp(_P.home())
_um0 = gateway.use_mock
gateway.use_mock = lambda: False                     # 이 프로세스의 모드만 실호출로 — 루트는 이미 정해졌다
try:
    init.init(fresh_=True, all_=True)
    _refused = None
except init.CleanRefused as e:
    _refused = str(e)
finally:
    gateway.use_mock = _um0
show("ⓑ 확인 없이 부른 클린(코드 — 공통 통로 `core/state/init.fresh`)은 운영 모드에서 `CleanRefused` · 쓰기 0",
     _refused is not None and _fp(_P.home()) == _fm0, (_refused or "거부 없음")[:120])

# ────────────────────────────────────────────────────────────── ⓒ
print("\n■ B111 ② 재구축은 지우기 전에 사전 점검 — 실호출 + 설정 없음")
_f0, _l0 = _fp(T, logs=False), _fp(T)
_rc, _out = _sp("rebuild", "--yes", env=_shell(T))
_f1, _l1 = _fp(T, logs=False), _fp(T)
_i_plan, _i_pf = _out.find("■ 재구축 계획"), _out.find("사전 점검 — **")
show("ⓒ 실호출 + 설정 없음 `rebuild --yes` — 계획을 보인 뒤 지우기 전에 멈춤(사전 점검 문면 · 「지우기 전에 멈췄다 — 그래프 "
     "그대로」 · 다음 줄 llm-check · rc 1) · 지문 불변(명령 로그 제외) · 계획 파일 0",
     _rc == 1 and _f0 == _f1 and _logs_only(_l0, _l1, "rebuild") and 0 <= _i_plan < _i_pf
     and "지우기 전에 멈췄다 — 그래프 그대로" in _out and "python run.py llm-check" in _out
     and "[재구축 fresh]" not in _out and not (T / "work" / "rebuild" / "plan.json").exists(),
     f"rc {_rc} · 지문 {'같음' if _f0 == _f1 else _fpdiff(_f0, _f1)}")
_say(_out, "■ 재구축", "사전 점검", "다음 줄", "설정 파일")

# ────────────────────────────────────────────────────────────── ⓓ
print("\n■ B111 ② 끝나지 않은 재구축의 정본은 계획 파일 — 끊긴 방식마다")
REG = _P.data("doc_registry.json")


def _status():
    p = RB.plan_path()
    return json.loads(p.read_text(encoding="utf-8")).get("status") if p.exists() else None


def _plan_line(out):
    return next((ln.strip() for ln in out.splitlines() if ln.startswith("■ 재구축 계획")), "")


_restore()
_rc, _out = _sp("rebuild", "--allow-mock", "--yes")
S_REF = _snap()
show("ⓓ 기준 — 끊기지 않은 재구축(mock은 끝까지) · 계획 파일 「끝」",
     _rc == 0 and _status() == RB.DONE and "계획 파일 — 끝" in _out, f"rc {_rc} · {_sizes(S_REF)}")


def _mid(sig):
    """재구축을 띄우고 **둘째 문서가 문서 대장에 들어온 뒤** 신호를 보낸다 — 되돌림 손이 돌지 못하는 끊김(kill -9)."""
    p = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "rebuild", "--allow-mock", "--yes"], cwd=str(ROOT),
                         env=ISO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    seen, t0 = None, time.time()
    while p.poll() is None and time.time() - t0 < 300:
        try:
            keys = list(json.loads(REG.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            keys = []
        if keys[:2] == ["CP01", "PFMEA01"] and len(keys) == 2 and _status() == RB.IN_PROGRESS:
            seen = keys
            p.send_signal(sig)
            break
        time.sleep(0.01)
    p.wait()
    return seen, p.returncode


def _kill9():
    seen, rc = _mid(signal.SIGKILL)
    return f"둘째 문서 도중 kill -9(대장 {seen} · rc {rc})"


def _docfail():
    f = RAWH / "PFMEA01.xlsx"
    keep = f.read_bytes()
    f.write_bytes(b"not a workbook")
    try:
        rc, out = _sp("rebuild", "--allow-mock", "--yes")
    finally:
        f.write_bytes(keep)
    return f"문서 하나 실패(PFMEA01 원본 깨짐 · rc {rc} · 계획 파일 {_status()})"


def _preflight_after():
    _docfail()
    sp = _P.schemas(f"{DT}.json")
    keep = sp.read_text(encoding="utf-8")
    s = json.loads(keep)
    s["fields"] = {"시험 개체": {"role": "entity", "category": "없는카테고리"}}
    sp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    f0, l0 = _fp(_P.home(), logs=False), _fp(_P.home())
    try:
        rc, out = _sp("rebuild", "--allow-mock", "--yes")
        f1, l1 = _fp(_P.home(), logs=False), _fp(_P.home())
    finally:
        sp.write_text(keep, encoding="utf-8")
    show("ⓓ 끊긴 재구축 위의 사전 점검 실패(등록 스키마 재대조) — 지우기 전에 멈춤 · 지문 불변(명령 로그 제외) · 계획 파일 "
         "「진행 중」 그대로",
         rc == 1 and f0 == f1 and _logs_only(l0, l1, "rebuild") and "지우기 전에 멈췄다 — 그래프 그대로" in out
         and "스키마 재대조" in out and _status() == RB.IN_PROGRESS,
         f"rc {rc} · 지문 {'같음' if f0 == f1 else _fpdiff(f0, f1)}")
    _say(out, "스키마 재대조", "지우기 전에", "다음 줄")
    return f"문서 하나 실패 뒤 사전 점검 실패(rc {rc})"


# 끊김 둘(B121 ②ⓓ — 되돌림 손이 돌지 못하는 kill -9 · 문서 실패 뒤 사전 점검 실패 — 「이어 간다」는 끊긴 방식과 무관한 계획 파일
# 한 자리라 넷을 곱하지 않는다 · 되돌림 손이 도는 중단(Ctrl-C)은 문서 단위 되돌림 시험(test_g6_stop_chunks · test_g6_safe_log)이 잰다)
for _how in (_kill9, _preflight_after):
    _restore()
    _what = _how()
    _k = len(json.loads(REG.read_text(encoding="utf-8")))
    _rc0, _p0 = _sp("rebuild", "--allow-mock")
    _rc1, _y = _sp("rebuild", "--allow-mock", "--yes")
    _s = _snap()
    _st = _status()
    _rc2, _p2 = _sp("rebuild", "--allow-mock")
    show(f"ⓓ {_what} ⇒ 다음 계획이 셋 전부 + 이어 간다(문서 대장 {_k}건은 그 도중의 것) · `--yes` 뒤 그래프 · 사전 · 큐가 기준과 "
         "같다 · 「끝」 → 다음 계획은 문서 대장에서",
         "문서 3(다시 넣을 것 3" in _plan_line(_p0) and _st == RB.DONE and _rc1 == 0 and _s == S_REF
         and f"지난 재구축이 끝나지 않았다 — 계획 파일에서 이어 간다 · 문서 대장 {_k}건은 그 도중의 것" in _p0
         and "지난 재구축이 끝나지 않았다" not in _p2 and "문서 3(다시 넣을 것 3" in _plan_line(_p2),
         f"계획 「{_plan_line(_p0)}」 · 계획 파일 {_st} · 기준과 다른 것 {_diff(_s, S_REF) or '없음'}")
    _say(_p0, "지난 재구축이")

_restore()
_unregister(DT)                                      # ②등록 · ⓪원본은 클린이 지우지 않는다 — 다음 스위트의 바닥에 남기지 않는다
for _did, *_x in DOCS:
    (RAWH / f"{_did}.xlsx").unlink(missing_ok=True)
shutil.rmtree(TMP, ignore_errors=True)
_quiet(init.init, fresh_=True, all_=True)
done()
