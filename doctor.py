# -*- coding: utf-8 -*-
"""사내 이식 점검기 — **가져온 것이 온전한가 · 다음에 무엇을 해야 하는가** (국면 2 진입 도구).

    python doctor.py            전체 (환경 → 자체 검증 → 상태 → 사내 전환 판정)
    python doctor.py --quick    회귀 생략 (느린 기계용 — 전체도 보통 20초 안이다)
    python doctor.py --env      환경만 (반입 직후 첫 실행 — 30초)

**왜 이 파일이 있나.** 레포를 사내로 옮기면 받는 사람은 "무엇부터 돌려야 하나"를 모른다.
문서를 다 읽게 하는 것은 답이 아니다 — **한 줄을 돌리면 현재 위치와 다음 한 걸음이
나오는 것**이 답이다. 그래서 이 파일은 설명하지 않고 **측정**한다.

**네트워크를 쓰지 않는다.** `USE_MOCK=1`(기본)에서 전 경로가 로컬로 돈다 — 사내 폐쇄망
에서 그대로 돌아간다는 것이 이 점검의 첫 결론이다.

**아무것도 고치지 않는다.** 읽고 재고 보고할 뿐이다. `data/`는 회귀가 쓰고 지운다.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 회귀 10종 — **각각을 클린 상태에서 단독 실행**한다(증분0 §8 실행 규약).
# 연속 실행은 판정 규격이 아니다: 스위트가 `data/`를 공유해 순서 의존이 관측됐다.
SUITES = [
    ("test_g1_g2", 81, "저장 계층 · 근거 축 id · 부트스트랩 · 런타임 경계 · core 경계 3종"),
    ("test_g3", 79, "인입 계약 v2 · 추출 분리 · 커밋 게이트 · 하강 부착"),
    ("test_g4", 36, "질의 4단 · 품질층 등록 · 재인입 회귀"),
    ("test_g5", 51, "I축 4연산 + 이관 · 운영 도구"),
    ("test_g6", 36, "플랫폼 창구 · 계기판 8종 · 지문 스캔"),
    ("test_g6_5", 38, "계약 미배선 24건 수리"),
    ("test_p1", 62, "파서 공용 코어 6종 · 구조 지도 · CSV reader · 역산 정합"),
    ("test_p2", 48, "어댑터 생성 킷 6종 · 검수 뷰 렌더러"),
    ("test_p3", 100, "구축 모드 등록 3단 · 2B 등록 개선 6건"),
    ("test_2a_gateway", 28, "게이트웨이 골조 — LLM 지점 9종 mock/실호출 분기"),
    ("verify_roundtrip", 50, "raw 실물 ↔ 계약 JSON 역산 정합"),
]

# **필수는 없다.** 문서 포맷 패키지는 **선택 의존**이다(문서 7 §7.1) — 지연 import로
# 격리돼 있어 `USE_MOCK=1` 전 경로가 이것들 없이 완주한다. 아래 「미설치 실측」이
# 그것을 매번 실행으로 확인한다. REQUIRED로 두면 폐쇄망 반입 첫 화면이 실제로는
# 없어도 되는 것을 [필요]로 띄워 다음 사람을 헛되이 멈춰 세운다.
REQUIRED = []
OPTIONAL = [("orjson", "그래프 직렬화 가속 — 없으면 표준 json으로 돈다"),
            ("openpyxl", "xlsx 읽기 — 파서 전용·지연 import"),
            ("pptx", "pptx 읽기 — 파서 전용·지연 import (패키지명 python-pptx)")]

OK, WARN, NG = "  OK ", " 주의 ", " 필요 "
# **[다음]은 결함이 아니다.** §④는 「사내에서 남은 작업」을 적는 자리인데 §①②③과
# 같은 [주의]를 쓰고 있었고, 실제로 사용자가 그것을 고장으로 읽었다(2B 실사고).
# 마크를 갈라 「할 일」과 「고장」이 화면에서 구분되게 한다. `_fail`은 [필요]만 센다.
NEXT = " 다음 "
_fail = 0


def line(mark, label, detail=""):
    global _fail
    if mark == NG:
        _fail += 1
    print(f"  [{mark}] {label}" + (f"\n         {detail}" if detail else ""))


def head(title):
    print(f"\n{'─' * 66}\n■ {title}\n{'─' * 66}")


def _clean():
    """클린 상태 — **`run.py init --fresh`가 정의한다**(문서 7 §7.6-4).

    반환은 `(returncode, 잔재 경로 목록)`이다.

    여기서 rmtree를 제 손으로 하면 "클린"의 정의가 doctor와 테스트와 완료판정에서
    각자 달라진다. subprocess로 부르는 이유는 doctor가 core를 import하기 전에도
    돌아야 하기 때문이다 — 반입 직후 첫 확인이 이 파일의 일이다.
    """
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
                       capture_output=True, text=True, cwd=str(ROOT))
    # **지운 결과를 실제로 확인한다.** `core/init.fresh()`는 `ignore_errors=True`로
    # 지우므로 권한 문제로 실패해도 조용하다 — 그러면 체크포인트가 살아남아
    # 「클린 단독 실행」이라는 판정의 바닥이 무너진다(회귀 규약 §7.5-7).
    residue = [d for d in ("parsed", "extract")
               if (ROOT / d).exists() and any((ROOT / d).iterdir())]
    return r.returncode, residue


# ================================================================ ① 환경
def check_env():
    head("① 환경 — 이 기계에서 돌아가는가")

    v = sys.version_info
    line(OK if v >= (3, 10) else NG, f"Python {platform.python_version()}",
         "3.10 이상이 필요하다 — 코드가 sys.stdlib_module_names(3.10 신설)를\n         쓴다. 개발·검증은 3.11에서 했다"
         if v >= (3, 10) else "3.10 미만이면 돌지 않는다 (문서 7 §7.1 런타임 전제)")

    for mod, why in REQUIRED:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "")
            line(OK, f"{mod} {ver}".strip(), why)
        except ImportError:
            line(NG, f"{mod} 없음", f"{why} — 없으면 파서(parser/)가 돌지 않는다. "
                                    f"코어·질의는 이것 없이도 돈다")
    for mod, why in OPTIONAL:
        try:
            __import__(mod)
            line(OK, f"{mod} (선택)", why)
        except ImportError:
            line(OK, f"{mod} 없음 (선택 — 문제 아님)", why)
    # **CSV는 의존이 없다** — 표준 `csv` 모듈이라 선택 의존 목록에 오르지 않는다.
    line(OK, "csv/tsv 읽기 (표준 라이브러리)",
         "reader가 받는 포맷: .xlsx · .xlsm · .pptx · .csv · .tsv — "
         "CSV는 설치할 것이 없다")

    # **코어는 stdlib만 쓴다** — 반입에서 가장 중요한 사실이라 실측해 보인다.
    # 선택 의존(`try: import … except ImportError:` 폴백)은 필수가 아니므로 뺀다 —
    # 없어도 도는 것을 "예상 밖"이라 부르면 그 경고가 다음 사람을 헛되이 멈춰 세운다.
    # **포맷 패키지 미설치 상태로 전 경로가 완주하는가** — 실측한다(문서 7 §7.1).
    # "요구하지 않는다"까지만 두면 모듈 최상단 import가 문면상 위반이 아니게 되어,
    # 미설치 환경에서 USE_MOCK=1 전체 실행이 ImportError로 죽는 것을 아무도 모른다.
    guard = ROOT / "doctor_noformat"
    guard.mkdir(exist_ok=True)
    (guard / "sitecustomize.py").write_text(
        "import builtins\n_real = builtins.__import__\n"
        "def _g(n, *a, **k):\n"
        "    if n.split('.')[0] in ('openpyxl', 'pptx'):\n"
        "        raise ImportError('미설치 모사: ' + n)\n"
        "    return _real(n, *a, **k)\n"
        "builtins.__import__ = _g\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(guard), USE_MOCK="1")
    _clean()
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                       capture_output=True, text=True, cwd=str(ROOT), env=env)
    q = subprocess.run([sys.executable, str(ROOT / "run.py"), "query", "노칭 다음 공정은?"],
                       capture_output=True, text=True, cwd=str(ROOT), env=env)
    shutil.rmtree(guard, ignore_errors=True)
    ok_np = r.returncode == 0 and q.returncode == 0 and "[그래프 사실]" in q.stdout
    line(OK if ok_np else NG,
         "포맷 패키지 미설치 상태로 전 경로 완주" + ("" if ok_np else " — 실패"),
         "openpyxl·python-pptx를 import 불가로 막고 build+query를 실행했다 — "
         "선택 의존이 실제로 격리돼 있다" if ok_np
         else (r.stderr or q.stderr).strip().splitlines()[-1:] and
              (r.stderr or q.stderr).strip().splitlines()[-1])

    optional = {m for m, _why in OPTIONAL}
    hard = set()
    for f in (ROOT / "core").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for m in re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", src, re.M):
            hard.add(m)
    hard -= {"core", "router"} | optional | set(sys.stdlib_module_names)
    line(OK if not hard else WARN,
         f"코어 필수 외부 의존 {len(hard)}종",
         "core/는 표준 라이브러리만 쓴다 — **폐쇄망에서 설치 없이 돈다**"
         + (f" (선택 의존 {sorted(optional)}는 폴백 있음)" if optional else "")
         if not hard else f"예상 밖: {sorted(hard)}")

    mock = os.environ.get("USE_MOCK", "1")
    line(OK if mock == "1" else WARN, f"USE_MOCK={mock}",
         "1 = LLM 없이 전 경로가 로컬로 돈다(네트워크 0). 사내 첫 실행은 이 상태여야 한다"
         if mock == "1" else "0 = 실LLM 경로. 아직 훅이 비어 있어 추출에서 명시 실패한다")

    try:
        probe = ROOT / ".doctor_write_probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        line(OK, "레포 쓰기 권한", "data/·extract/·review/를 만들 수 있다")
    except OSError as e:
        line(NG, "레포 쓰기 권한 없음", f"{e} — 실행 산출물을 만들 수 없다")

    return _fail == 0


def _idempotent():
    """**클린 2회 동일 그래프** — 구현 국면 완료판정 4번 (문서 7 §7.6-4).

    이 판정을 세는 것이 여태 없었다. 시나리오 통과만 세면 멱등성이 조용히 깨진
    상태로도 판정이 통과한다.

    대조 단위를 셋으로 나눈다:

    - **그래프**: 바이트 동일이어야 한다. 다르면 노드가 증식했거나 id가 재발급됐다.
    - **큐**: `(kind, doc_id, payload)` **집합**으로 본다. 순서까지 같기를 요구하지
      않는 것은 재인입이 그 문서의 비상시(non-STANDING) 큐를 회수한 뒤 다시 싣기
      때문이다 — 살아남은 상시 항목은 제자리에 있고 회수분은 뒤에 붙어 순서가
      바뀐다. 증식·유실이 없다는 것이 멱등성이고, 파일 안 배열 순서는 아니다.
    - **거부 로그**: 큐가 아니라 관측 신호다(§7.8) — 계수만 본다.
    """
    def snap():
        graphs, queue, rejects = {}, set(), 0
        for f in sorted((ROOT / "data").rglob("*.json")):
            rel = str(f.relative_to(ROOT / "data"))
            if rel.endswith("graph" + ".json"):
                graphs[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        for x in json.loads((ROOT / "data" / "review_queue.json").read_text(encoding="utf-8")):
            queue.add((x["kind"], x["doc_id"],
                       json.dumps(x["payload"], sort_keys=True, ensure_ascii=False)))
        rj = ROOT / "data" / "gate_rejects.json"
        if rj.exists():
            rejects = len(json.loads(rj.read_text(encoding="utf-8")))
        return graphs, queue, rejects

    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
                       capture_output=True, text=True, cwd=str(ROOT))
    # **지운 결과를 실제로 확인한다.** `core/init.fresh()`는 `ignore_errors=True`로
    # 지우므로 권한 문제로 실패해도 조용하다 — 그러면 체크포인트가 살아남아
    # 「클린 단독 실행」이라는 판정의 바닥이 무너진다(회귀 규약 §7.5-7).
    residue = [d for d in ("parsed", "extract")
               if (ROOT / d).exists() and any((ROOT / d).iterdir())]
    return r.returncode, residue
    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT))
    g1, q1, r1 = snap()
    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT))
    g2, q2, r2 = snap()

    same_g, same_q = g1 == g2, q1 == q2
    detail = (f"그래프 {len(g1)}층 바이트 동일 · 큐 {len(q1)}항목 집합 동일 · "
              f"거부 로그 {r1}→{r2}") if same_g and same_q else (
              f"그래프 {'동일' if same_g else '다름'} · "
              f"큐 1회만 {len(q1 - q2)}건 / 2회만 {len(q2 - q1)}건")
    line(OK if same_g and same_q else NG,
         "클린 2회 동일 그래프 (완료판정 4)", detail)


# ================================================================ ② 자체 검증
def _why(name, r, p, expect):
    """실패한 스위트의 **원인을 화면에 낸다** — 사내망은 출력을 밖으로 못 가져온다.

    구판은 원인을 숨겼다: ①`[PASS]`가 하나라도 찍히면(`p > 0`) stderr를 아예 안 냈고
    ②내더라도 **마지막 1줄**이라 traceback의 원인 줄(ImportError·UnicodeEncodeError)이
    화면에 오지 않았다. 그래서 "8건 [필요]"만 뜨고 왜인지 알 방법이 없었다.
    """
    fails = [ln.strip()[:110] for ln in r.stdout.splitlines() if "[FAIL]" in ln]
    for ln in fails[:5]:
        print(f"           {ln}")
    if len(fails) > 5:
        print(f"           … 외 {len(fails) - 5}건")

    err = (r.stderr or "").strip()
    if err and (r.returncode or p != expect):
        # **마지막 15줄** — 원인 줄은 traceback 끝에 있다. p>0인지와 무관하게 낸다:
        # 스위트가 중간에 크래시하면 앞선 [PASS]가 남은 채 죽는다.
        tail = err.splitlines()[-15:]
        print(f"           ── stderr (마지막 {len(tail)}줄) ──")
        for ln in tail:
            print(f"           {ln}")
    elif not err and p < expect:
        # stderr가 비었는데 PASS가 모자라면 **조용한 조기 종료**다 —
        # 어디까지 갔는지는 stdout 끝에만 남아 있다.
        tail = r.stdout.strip().splitlines()[-10:]
        print(f"           ── stdout 끝 {len(tail)}줄 (조용한 조기 종료) ──")
        for ln in tail:
            print(f"           {ln}")
    print(f"           재현: python tests/{name}.py")


def _env_diff(clean_rc, residue):
    """②가 실패했을 때만 내는 **환경 차이 표** — 사람이 판단할 재료다.

    같은 커밋이 한 기계에서 526/526이고 다른 기계에서 아니면 원인은 코드가 아니라
    환경이다. 그 후보를 화면이 스스로 지목한다 — 사내망에서는 출력을 밖으로 가져와
    물어볼 수 없으므로, **진단이 화면에서 끝나야 한다.**
    """
    print("\n  ── 환경 차이 점검 (② 실패 시에만 낸다) ──")
    rows = []

    enc = (sys.stdout.encoding or "").lower()
    rows.append((OK if "utf" in enc else WARN, "표준 출력 인코딩", enc or "(불명)",
                 "utf-8이 아니면 한글 출력에서 스위트가 죽는다 — "
                 "PYTHONIOENCODING=utf-8 로 다시 돌려 본다"
                 if "utf" not in enc else "한글 출력이 안전하다"))

    fse = (sys.getfilesystemencoding() or "").lower()
    rows.append((OK if "utf" in fse else WARN, "파일시스템 인코딩", fse or "(불명)",
                 "한글 경로·파일명 자산이 있다 — utf-8이 아니면 못 연다"
                 if "utf" not in fse else "한글 경로를 연다"))

    v = sys.version_info
    rows.append((OK if v >= (3, 10) else NG, "Python 버전", platform.python_version(),
                 "3.10 미만은 문법부터 죽는다" if v < (3, 10) else "개발·검증은 3.11"))

    crlf = None
    for f in sorted((ROOT / "tests").glob("*.py")):
        crlf = b"\r\n" in f.read_bytes()
        break
    rows.append((WARN if crlf else OK, "줄바꿈", "CRLF" if crlf else "LF",
                 "git autocrlf가 켜져 파일이 바뀌었다 — core.autocrlf=false 로 다시 클론"
                 if crlf else "원본 그대로다"))

    cwd = os.getcwd()
    same = Path(cwd).resolve() == ROOT
    rows.append((OK if same else NG, "작업 디렉터리", cwd,
                 "레포 루트가 아니다 — 상대 경로가 깨진다. 루트에서 다시 돌린다"
                 if not same else "레포 루트와 같다"))

    rows.append((OK if (clean_rc == 0 and not residue) else NG,
                 "data/·extract/ 잔재",
                 "없음" if not residue else ", ".join(residue),
                 "클린이 조용히 실패했다(권한?) — 순서 의존이 살아 있어 "
                 "단독 실행 판정이 성립하지 않는다"
                 if (clean_rc or residue) else "run.py init --fresh가 실제로 비웠다"))

    # 한글은 터미널에서 **두 칸**을 먹는다 — `len()`으로 맞추면 열이 어긋난다.
    def _w(s):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

    w = max(_w(a) for _m, a, _b, _c in rows)
    for mark, what, val, why in rows:
        print(f"  [{mark}] {what}{' ' * (w - _w(what))}  {val}")
        print(f"         {why}")


def run_suites(quick=False):
    head("② 자체 검증 — 가져온 것이 온전한가 (회귀 10종)")
    if quick:
        print("  (--quick: 건너뛴다. 반입 직후에는 반드시 한 번 돌려라)")
        return None

    print("  각 스위트를 **클린 상태에서 단독 실행**한다 — 연속 실행은 판정 규격이 아니다\n"
          "  (증분0 §8 실행 규약: 스위트가 data/를 공유해 순서 의존이 관측됐다)\n")
    total_ok, results = True, []
    clean_rc, residue = 0, []
    for name, expect, what in SUITES:
        rc, res = _clean()
        clean_rc = clean_rc or rc
        residue = residue or res              # 한 번이라도 남았으면 그것이 신호다
        t0 = time.time()
        r = subprocess.run([sys.executable, str(ROOT / "tests" / f"{name}.py")],
                           capture_output=True, text=True, cwd=str(ROOT))
        dt = time.time() - t0
        p = r.stdout.count("[PASS]")
        f = r.stdout.count("[FAIL]")
        ok = (f == 0 and p == expect)
        total_ok &= ok
        results.append((name, p, f, expect, ok))
        mark = OK if ok else NG
        note = "" if ok else f"기대 {expect} PASS · FAIL 0"
        line(mark, f"{name:<17} {p:>3} PASS / {f} FAIL   ({dt:.0f}s)  {what}", note)
        if not ok:
            _why(name, r, p, expect)

    got = sum(p for _n, p, _f, _e, _o in results)
    want = sum(e for _n, _p, _f, e, _o in results)
    _idempotent()

    print()
    line(OK if total_ok else NG, f"합계 {got}/{want} PASS",
         "국면 1 완료판정의 회귀 기준선과 일치한다" if total_ok
         else "기준선과 다르다 — 반입이 온전하지 않거나 환경이 다르다")
    if not total_ok:
        # **성공하면 화면을 늘리지 않는다** — 실패할 때만 원인 후보를 낸다.
        _env_diff(clean_rc, residue)
    _clean()
    return total_ok


# ================================================================ ③ 현재 상태
def show_state():
    head("③ 현재 상태 — 무엇이 들어 있나")
    sys.path.insert(0, str(ROOT))
    from core import registry, store                              # noqa: E402
    from core.bootstrap import bootstrap, open_graph              # noqa: E402
    from router import discover                                   # noqa: E402

    _clean()
    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT))

    layers = discover()
    print(f"  층 {len(layers)}개 — {', '.join(layers)}")
    for lay in layers:
        g = open_graph(lay)
        seed = sum(1 for n in g.nodes.values() if n.get("status") == "seed")
        print(f"    · {lay:<10} 노드 {len(g.nodes):>3} (골격 seed {seed}) · 엣지 {len(g.edges)}")

    dts = registry.all_doc_types()
    builtin = [k for k, v in dts.items() if v["status"] == "builtin"]
    reg = [k for k, v in dts.items() if v["status"] == "registered"]
    print(f"\n  doc_type {len(dts)}종 — 내장 {len(builtin)} {builtin}")
    print(f"                    등록 {len(reg)} {reg or '(아직 없음 — n6로 등록한다)'}")

    q = store.read(store.QUEUE, [])
    from collections import Counter
    kinds = Counter(x["kind"] for x in q)
    print(f"\n  수정 큐 {len(q)}건 — {dict(kinds)}")
    print(f"  (mock 기준선 69. 사내 실데이터를 넣으면 당연히 달라진다)")

    docs = store.read(store.DOC_REGISTRY, {})
    print(f"\n  인입 문서 {len(docs)}건 — {list(docs)}")
    print("  ⚠ 전부 mock이다(mock/parsed·mock/raw). 사내 문서로 교체하는 것이 국면 2다")


# ================================================================ ④ 사내 전환
def transition():
    head("④ 사내 전환 — 다음에 무엇을 해야 하나 (실측 판정)")
    print("  아래는 결함이 아니라 사내에서 남은 작업이다. `[필요]`가 뜨면 그때가 고장이다.\n")
    sys.path.insert(0, str(ROOT))
    from core import registry, store                              # noqa: E402

    # ── 1. 골격 seed ──────────────────────────────────────────────
    seed = json.loads((ROOT / "layers/process/skeleton.json").read_text(encoding="utf-8"))
    snap = (store.read(store.SKELETON_LIST, {}).get("process") or {})
    line(NEXT, f"[1] 골격 seed가 아직 창작 mock이다 — 노드 {snap.get('count', '?')} · "
               f"seed 문법 v{seed.get('seed_format')}",
         "**사내 첫 작업이 이것이다.** layers/process/skeleton.json을 사내 공정 체계로\n"
         "         바꾸고 `python run.py bootstrap`. 코드는 한 줄도 안 바뀐다 — seed는 데이터다.\n"
         "         형식은 docs/skeleton_seed.md · 마커 4종(:: · @split · @unordered · @noflow)")

    # ── 1′. role 배정 실험 ────────────────────────────────────────
    # **등록 세션 진입 전에 이것이 먼저다**(갭 spec-A-201 · role-136).
    # 실험 없이 register generate로 가면 생성 세션이 무엇을 물어볼지 모른 채
    # 시작한다 — 6지선다의 여섯째 경로(UNMAPPABLE)가 무엇인지를 먼저 본다.
    line(NEXT, "[1′] 사내 문서로 **role 배정 실험**을 먼저 돌린다",
         "`python run.py register roles <문서.xlsx> [헤더행]`\n"
         "         실행만 하고 등록부는 건드리지 않는다 — 어느 열이 UNMAPPABLE로\n"
         "         떨어지는지가 **생성 세션의 첫 안건**이다. 답을 준비하고 [2]로 간다")

    # ── 2. doc_type 등록 ──────────────────────────────────────────
    reg = [k for k, v in registry.all_doc_types().items() if v["status"] == "registered"]
    line(NEXT if not reg else OK,
         f"[2] 사내 doc_type 등록 {len(reg)}종",
         "표본 2부를 골라 `python run.py register generate <이름> <층> <표본...>` →\n"
         "         `review` → `confirm --by <승인자>`. 검수 뷰 HTML을 브라우저로 연다"
         if not reg else f"등록됨: {reg}")

    # ── 3. LLM 지점 8종의 실호출 분기 ─────────────────────────────
    # **주석을 세지 않는다.** 여태 이 자리가 문자열 "HOOK"을 세어, 전부 주석이던
    # 5곳을 구현된 것으로 보고했다(문서 7 §7.6-B-2: 주석은 실행되지 않는다).
    # 이제 세는 것은 **실제 분기의 존재**다 — 각 지점이 `llm.use_mock()`(또는
    # 파서 쪽의 동형 판독)으로 갈리고 실호출 갈래를 갖는가.
    from core.llm import POINTS                                   # noqa: E402
    WIRED = {
        "extract": ("core/extract.py", "_candidates_for"),
        "judge": ("core/matcher.py", "_judge_live"),
        "embed": ("core/embeddings.py", "def embed"),
        "image_summary": ("parser/tagger.py", "allow_mock"),
        "generate": ("cli/register.py", "_draft_live"),
        "link": ("core/query.py", "_link_llm"),
        "struct_map": ("parser/struct_map.py", "ask is None"),
        "answer": ("cli/query.py", "def generate"),
        "coord_tag": ("parser/tagger.py", "pick is not None"),
    }
    wired, missing = [], []
    for key, label in POINTS.items():
        where, needle = WIRED.get(key, (None, None))
        src = (ROOT / where).read_text(encoding="utf-8") if where else ""
        # 분기의 조건: 실호출 갈래의 이름이 있고, mock 갈래와 갈리는 판독이 있다.
        gate = ("use_mock" in src or "USE_MOCK" in src or "allow_mock" in src)
        (wired if (needle and needle in src and gate) else missing).append(
            f"{label} ({where})")
    line(OK if not missing else NG,
         f"[3] LLM 지점 {len(wired)}/{len(POINTS)}종에 mock/실호출 분기가 서 있다",
         ("게이트웨이 골조는 섰고 **설정만 비어 있다** — LLM_GATEWAY_URL·CHAT_MODEL을\n"
          "         주면 USE_MOCK=0으로 돈다. 미설정 상태의 USE_MOCK=0은 조용히 mock으로\n"
          "         떨어지지 않고 명시적으로 실패한다(문서 7 §7.6-B-4).\n"
          "         **USE_MOCK=1에서는 없어도 전 파이프라인이 돈다** — 정밀도만 규칙 수준이다\n"
          "         연결 확인: python run.py llm-check"
          ) if not missing else
         "분기가 없는 지점:\n" + "\n".join(f"         · {m}" for m in missing))

    # ── 4. 계기판 첫 측정 ─────────────────────────────────────────
    line(NEXT, "[4] 계기판은 mock 수치다 — 품질 측정이 아니다",
         "실데이터 인입 후 `python run.py gauges`가 첫 진짜 측정이다.\n"
         "         그 수치가 P7 판정(하이브리드·랭킹·저장 전환)의 근거가 된다")

    # ── 5. 반출입 경계 ────────────────────────────────────────────
    line(OK, "[5] 반출입 경계 — 코드는 들어가고, 실물 문서는 나오지 않는다",
         "이 레포에 사내 유래 정보가 0이다(mock은 전량 창작). 반입은 자유롭고,\n"
         "         사내에서 만든 어댑터·seed·문서는 **밖으로 내보내지 않는다**")

    print(f"\n  {'권장 순서':<10} ① seed 교체 → bootstrap  ② doc_type 1종 등록  "
          f"③ 실문서 인입  ④ 질의  ⑤ 계기판")
    print(f"  {'더 볼 것':<10} 구현현황.md — 기능별 반영 수준 · 포맷 확장 · 갱신 트리거 · 반입 이력")


# ================================================================ 진입점
def main(argv):
    only_env = "--env" in argv
    quick = "--quick" in argv or only_env

    print("=" * 66)
    print("  온톨로지 시스템 — 사내 이식 점검  (국면 1 완료본)")
    print("=" * 66)

    env_ok = check_env()
    if only_env:
        print(f"\n{'=' * 66}")
        print("환경 점검만 수행했다. 전체는 `python doctor.py`")
        return 0 if env_ok else 1

    suites_ok = run_suites(quick)
    show_state()
    transition()

    print(f"\n{'=' * 66}")
    if _fail:
        print(f"결과: **{_fail}건이 조치 필요**다 — 위 [{NG.strip()}] 항목을 먼저 해결한다")
    else:
        verdict = "온전하다" if suites_ok else ("회귀 미수행" if quick else "회귀 실패")
        print(f"결과: 반입물은 {verdict}. 다음은 ④의 권장 순서다")
    print("=" * 66)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
