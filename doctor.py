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
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 회귀 10종 — **각각을 클린 상태에서 단독 실행**한다(증분0 §8 실행 규약).
# 연속 실행은 판정 규격이 아니다: 스위트가 `data/`를 공유해 순서 의존이 관측됐다.
SUITES = [
    ("test_g1_g2", 58, "저장 계층 · 근거 축 id · 부트스트랩 · 런타임 경계 · core 경계 3종"),
    ("test_g3", 60, "인입 계약 v2 · 추출 분리 · 커밋 게이트 · 하강 부착"),
    ("test_g4", 27, "질의 4단 · 품질층 등록 · 재인입 회귀"),
    ("test_g5", 36, "I축 도구 4연산 (개명·병합·분리·폐기)"),
    ("test_g6", 30, "플랫폼 창구 · 계기판 8종 · 지문 스캔"),
    ("test_g6_5", 38, "계약 미배선 24건 수리"),
    ("test_p1", 46, "파서 공용 코어 6종 · 구조 지도 · 역산 정합"),
    ("test_p2", 45, "어댑터 생성 킷 6종 · 검수 뷰 렌더러"),
    ("test_p3", 45, "구축 모드 등록 3단 (생성·검수·확정)"),
    ("test_2a_gateway", 26, "게이트웨이 골조 — LLM 지점 8종 mock/실호출 분기"),
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

    여기서 rmtree를 제 손으로 하면 "클린"의 정의가 doctor와 테스트와 완료판정에서
    각자 달라진다. subprocess로 부르는 이유는 doctor가 core를 import하기 전에도
    돌아야 하기 때문이다 — 반입 직후 첫 확인이 이 파일의 일이다.
    """
    subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
                   capture_output=True, text=True, cwd=str(ROOT))


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

    subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
                   capture_output=True, text=True, cwd=str(ROOT))
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
def run_suites(quick=False):
    head("② 자체 검증 — 가져온 것이 온전한가 (회귀 10종)")
    if quick:
        print("  (--quick: 건너뛴다. 반입 직후에는 반드시 한 번 돌려라)")
        return None

    print("  각 스위트를 **클린 상태에서 단독 실행**한다 — 연속 실행은 판정 규격이 아니다\n"
          "  (증분0 §8 실행 규약: 스위트가 data/를 공유해 순서 의존이 관측됐다)\n")
    total_ok, results = True, []
    for name, expect, what in SUITES:
        _clean()
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
            for ln in r.stdout.splitlines():
                if "[FAIL]" in ln:
                    print(f"           {ln.strip()[:110]}")
            if r.returncode and not p:
                print(f"           {(r.stderr or '').strip().splitlines()[-1:]}")

    got = sum(p for _n, p, _f, _e, _o in results)
    want = sum(e for _n, _p, _f, e, _o in results)
    _idempotent()

    print()
    line(OK if total_ok else NG, f"합계 {got}/{want} PASS",
         "국면 1 완료판정의 회귀 기준선과 일치한다" if total_ok
         else "기준선과 다르다 — 반입이 온전하지 않거나 환경이 다르다")
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
    sys.path.insert(0, str(ROOT))
    from core import registry, store                              # noqa: E402

    # ── 1. 골격 seed ──────────────────────────────────────────────
    seed = json.loads((ROOT / "layers/process/skeleton.json").read_text(encoding="utf-8"))
    snap = (store.read(store.SKELETON_LIST, {}).get("process") or {})
    line(WARN, f"[1] 골격 seed가 아직 창작 mock이다 — 노드 {snap.get('count', '?')} · "
               f"seed 형식 v{seed.get('skeleton_version')}",
         "**사내 첫 작업이 이것이다.** layers/process/skeleton.json을 사내 공정 체계로\n"
         "         바꾸고 `python run.py bootstrap`. 코드는 한 줄도 안 바뀐다 — seed는 데이터다.\n"
         "         형식은 docs/skeleton_seed.md · 마커 4종(:: · @split · @unordered · @noflow)")

    # ── 2. doc_type 등록 ──────────────────────────────────────────
    reg = [k for k, v in registry.all_doc_types().items() if v["status"] == "registered"]
    line(WARN if not reg else OK,
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
        "link": ("core/query.py", "_link_deep"),
        "struct_map": ("parser/struct_map.py", "ask is None"),
        "answer": ("cli/query.py", "def generate"),
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
         ("게이트웨이 골조는 섰고 **설정만 비어 있다** — ONTO_LLM_URL·ONTO_LLM_MODEL을\n"
          "         주면 USE_MOCK=0으로 돈다. 미설정 상태의 USE_MOCK=0은 조용히 mock으로\n"
          "         떨어지지 않고 명시적으로 실패한다(문서 7 §7.6-B-4).\n"
          "         **USE_MOCK=1에서는 없어도 전 파이프라인이 돈다** — 정밀도만 규칙 수준이다"
          ) if not missing else
         "분기가 없는 지점:\n" + "\n".join(f"         · {m}" for m in missing))

    # ── 4. 계기판 첫 측정 ─────────────────────────────────────────
    line(WARN, "[4] 계기판은 mock 수치다 — 품질 측정이 아니다",
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
