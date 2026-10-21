# -*- coding: utf-8 -*-
"""칸 0.3 — **회귀 실행** — 스위트마다 임시 자리에서 함께 돈다(병렬) · 기대 수는 기록 파일에서 읽는다 (B131 ①② · B133 ①②).

    병렬(기본) — 스위트마다 **제 임시 자리**: 상태 루트(시험 전용 훅 `ONTO_MOCK_HOME`=<임시>/<mock 루트 이름> — 이름이 mock 자리라 레포
                 mock 루트와 같은 규칙: 층 자산을 레포 seed로 · `init --fresh --all`이 클린) · **픽스처 뿌리 사본**(`ONTO_FIXTURES` — 시험이
                 픽스처에 써도 제 사본에만 · B133 ①) · **작업 폴더** → 클린 → 스위트 → 중복 canonical 점검 · 동시에 `JOBS`개 · 지난 소요가
                 긴 것부터 넣고 화면은 스위트 목록 순서
    직렬(`--serial`) — 레포 mock 루트 하나에서 차례로(병렬 결과를 대조하는 길) · 픽스처 사본 · 작업 폴더는 병렬과 같다

**레포는 시험이 읽기만 한다**(B133 ①) — 회귀 앞뒤 작업 트리 대조(`repo_tree` — 남은 쓰기) · 쓰고 지우는 것은 정적 점검(`tools/repo_writes.py`).
**붉은 스위트는 자리를 남긴다**(B133 ②) — 그 임시 자리 + 출력 전문(`출력.txt`)을 시스템 임시 폴더의 `onto_red_<시각>_<pid>_<스위트>`로
옮기고 자리를 한 줄 · 초록은 지운다 · 지난 붉은 자리는 최근 `RED_KEEP`개만 남긴다(다음 회귀가 정리).

**기대 수는 생성물이다**(`docs/회귀스위트/기대_수.json` — 마감 한 줄 `tools/close.py`가 쓴다 · doctor는 읽기만):
  ⓐ PASS 0 · FAIL 하나 이상 · 종료 코드 ≠ 0 은 늘 붉다 — 시험이 조용히 안 돈 것
  ⓑ 기록보다 적으면 붉다 — `--why <스위트>=<사유>`가 있으면 사유와 함께 지나간다(마감 한 줄이 기록에 사유를 남긴다)
  ⓒ 기록보다 많거나 기록에 없는 새 스위트는 지나간다(「+n」 · 기록은 마감 한 줄)
  ⓓ 기록에만 있는 스위트(지웠거나 합쳤다)는 합친 스위트의 `was`(앞 이름들 — 그 기록의 합이 기대 수)가 받거나 사유가 있어야 지나간다
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: 기대 수 기록(생성물 — 마감 한 줄이 쓴다)
RECORD = ROOT / Path("docs", "회귀스위트", "기대_수.json")
#: 동시에 도는 스위트 수 — 4 근방(기계가 작으면 2) · `--jobs N`
JOBS = min(4, max(2, os.cpu_count() or 2))
#: 붉은 스위트의 자리(임시 자리 + 출력 전문)를 모으는 곳 · 남기는 수(최근 것부터 — 창작 기본값)
RED_DIR = Path(tempfile.gettempdir())
RED_PREFIX = "onto_red_"
RED_KEEP = 20
_LOW_SECS = 10                          # 소요 기록이 없는 스위트의 어림(넣는 순서에만 쓴다)


def load(path=RECORD):
    """기록 `{"suites": {이름: {"n", "secs"}}, "log": [...]}` — 없으면 빈 기록."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"suites": {}, "log": []}


def expected(name, was, rec):
    """그 스위트의 기대 PASS 수 — 기록 · 합친 앞 이름들의 합 · 없으면 None(새 스위트)."""
    s = rec.get("suites") or {}
    if name in s:
        return s[name]["n"]
    got = [s[w]["n"] for w in was if w in s]
    return sum(got) if got else None


def verdict(p, f, rc, exp, why):
    """`(통과, 덧말)` — 위 머리말의 ⓐ~ⓒ."""
    if p == 0 or f or rc:
        return False, f"PASS {p} · FAIL {f} · rc {rc} — 시험이 끝까지 돌지 않았다(늘 붉다)"
    if exp is None:
        return True, f"새 스위트 +{p}(기록은 마감 한 줄)"
    if p < exp:
        return (True, f"−{exp - p} · 사유 {why}") if why else \
            (False, f"기록 {exp}보다 {exp - p} 적다 — 사유가 없다(--why <스위트>=<사유>)")
    return True, (f"+{p - exp}(기록 {exp} — 기록은 마감 한 줄)" if p > exp else "")


def removed(suites, rec, why):
    """기록에만 있는 스위트 `[(이름, 기록 수, 통과, 덧말)]` — 합친 스위트의 `was`가 받으면 뺀다(ⓓ)."""
    names = {s[0] for s in suites}
    taken = {w for s in suites for w in (s[2] if len(s) > 2 else ())}
    out = []
    for n, v in sorted((rec.get("suites") or {}).items()):
        if n in names or n in taken:
            continue
        w = why.get(n)
        out.append((n, v["n"], bool(w), f"지웠다 · 사유 {w}" if w else "기록에만 있다 — 돌지 않았다(사유 없음 · 늘 붉다)"))
    return out


def _residue(home):
    """클린 뒤 작업 단(parsed · extract) 잔재 — 자리는 `core/paths.py`가 안다(상대 자리만 빌린다)."""
    from core import paths
    rel = [d.relative_to(paths.home()) for d in (paths.parsed(), paths.extract())]
    return [r.name for r in rel if (home / r).exists() and any((home / r).iterdir())]


def clean(env=None, home=None):
    """클린 상태 — `run.py init --fresh --all`(문서 7 §7.6-4) · `(rc, 잔재)` · `home`이 없으면 이 프로세스의 루트."""
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh", "--all"],
                       capture_output=True, text=True, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    if home is None:
        from core import paths
        home = paths.home()
    return r.returncode, _residue(Path(home))


def _temp_root(prefix, mock=True):
    """`(임시 폴더, 그 아래 mock 루트 또는 None, 하위 실행 환경, 작업 폴더)` — 픽스처 뿌리 사본(B133 ①) · mock 루트는 `mock`일 때만(직렬은
    레포 mock 루트) · 루트 이름 · 훅 이름은 자리 소유자(`core/paths.py` · `core/state/fixtures.py`)가 안다."""
    from core import paths
    from core.state import fixtures
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    env = dict(os.environ)
    if fixtures.ROOT_DIR.is_dir():
        fx = tmp / "fixtures"
        shutil.copytree(fixtures.ROOT_DIR, fx, ignore=shutil.ignore_patterns("__pycache__"))
        env[fixtures.ENV] = str(fx)
    work = Path(tempfile.mkdtemp(prefix="work_", dir=tmp))
    home = None
    if mock:
        home = tmp / paths.MOCK_HOME
        env[paths.MOCK_HOME_ENV] = str(home)
    return tmp, home, env, work


def _job(name, serial):
    """스위트 하나 — 제 임시 자리에서 클린 → 실행 → 중복 점검. 임시 자리는 결과에 싣고 지우지 않는다 — 판정한 쪽이 `settle`로
    초록이면 지우고 붉으면 남긴다(B133 ②)."""
    tmp, home, env, work = _temp_root(f"onto_{name}_", mock=not serial)
    crc, res = clean(env, home)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(ROOT / "tests" / f"{name}.py")], capture_output=True, text=True,
                       cwd=str(work), env=env, stdin=subprocess.DEVNULL)
    dt = time.time() - t0
    d = subprocess.run([sys.executable, str(ROOT / "tests" / "dup_scan.py")], capture_output=True, text=True,
                       cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    lines = [ln.strip() for ln in r.stdout.splitlines()]
    return {"name": name, "r": r, "secs": dt, "clean_rc": crc, "residue": res, "tmp": tmp,
            "p": sum(1 for ln in lines if ln.startswith("[PASS]")),     # 판정 줄만 센다(B50)
            "f": sum(1 for ln in lines if ln.startswith("[FAIL]")),
            "dup": d.returncode, "dup_out": (d.stdout or "").strip()}


# ---------------------------------------------------------------- 붉은 기록 (B133 ②)
def prune_red(keep=None):
    """지난 붉은 자리를 최근 `keep`(기본 `RED_KEEP`)개만 남긴다 — 지운 수."""
    keep = RED_KEEP if keep is None else keep
    dirs = sorted((p for p in RED_DIR.glob(f"{RED_PREFIX}*") if p.is_dir()), key=lambda p: p.name)
    old = dirs[:-keep] if keep > 0 else dirs
    for p in old:
        shutil.rmtree(p, ignore_errors=True)
    return len(old)


def keep_red(tmp, name, text):
    """붉은 스위트의 임시 자리를 `RED_DIR/onto_red_<시각>_<pid>_<이름>`으로 옮기고 출력 전문(`출력.txt`)을 남긴다 — 그 자리."""
    dst = RED_DIR / f"{RED_PREFIX}{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{name}"
    shutil.move(str(tmp), str(dst))
    (dst / "출력.txt").write_text(text, encoding="utf-8")
    return dst


def settle(res, ok):
    """판정이 끝난 스위트의 임시 자리 — 초록이면 지우고 붉으면 남긴다 · 남긴 자리(또는 None)."""
    tmp = res.get("tmp")
    if tmp is None or not Path(tmp).exists():
        return None
    if ok:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    r = res["r"]
    text = (f"# {res['name']} — PASS {res['p']} · FAIL {res['f']} · rc {r.returncode} · {res['secs']:.0f}s · 클린 rc "
            f"{res['clean_rc']} · 잔재 {res['residue']} · 중복 rc {res['dup']}\n\n## stdout\n{r.stdout}\n\n## stderr\n{r.stderr}\n"
            + (f"\n## 중복 canonical\n{res['dup_out']}\n" if res.get("dup") else ""))
    return keep_red(tmp, res["name"], text)


# ---------------------------------------------------------------- 레포 작업 트리 (B133 ① — 회귀 앞뒤 대조)
def repo_tree():
    """레포 작업 트리의 지문 `{경로: 상태 · 내용 해시}`(git이 추적 · 추적하지 않는 파일 — 무시 목록 밖) · git을 못 부르면 None."""
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=str(ROOT),
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode:
        return None
    out = {}
    for ln in r.stdout.splitlines():
        rel = ln[3:].strip().strip('"')
        p = ROOT / rel
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else "-"
        out[rel] = f"{ln[:2]} {h}"
    return out


def tree_diff(before, after):
    """`(같다, 덧말)` — 둘 중 하나가 None(git 없음)이면 `(None, 사유)`."""
    if before is None or after is None:
        return None, "git을 부를 수 없어 건너뛰었다"
    diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    return (not diff), ("같다" if not diff else f"달라진 자리 {len(diff)} — {' · '.join(diff[:6])}")


def run(names, serial=False, jobs=JOBS, rec=None, extra=None):
    """고른 스위트를 돌려 **목록 순서로** 결과를 내놓는다(생성기) · 병렬은 긴 것부터 넣는다 · `extra`는 같은 풀에서 함께 도는
    일 하나(완료판정 4) — 그 결과는 마지막에 `("extra", 값)`으로."""
    rec = rec or load()
    if serial:
        for n in names:
            yield _job(n, True)
        if extra is not None:
            yield ("extra", extra())
        return
    secs = {n: (rec.get("suites") or {}).get(n, {}).get("secs", _LOW_SECS) for n in names}
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        fx = ex.submit(extra) if extra is not None else None
        futs = {n: ex.submit(_job, n, False) for n in sorted(names, key=lambda n: -secs[n])}
        for n in names:
            yield futs[n].result()
        if fx is not None:
            yield ("extra", fx.result())


# ---------------------------------------------------------------- 완료판정 4 — 클린 2회 동일 그래프
def _snap(home):
    """그래프 바이트 해시 · 큐 집합 · 거부 로그 수 — **여기서만 층 그래프 파일을 바이트로 연다** — B6(GraphStore 경유)의 예외이고
    그 근거: 재는 것이 파일 바이트의 동일성이다(GraphStore는 정규화해 그 차이를 지운다 · 그래프를 쓰거나 해석하는 경로가 아니다 — P5)."""
    from core import paths
    data = Path(home) / paths.data().relative_to(paths.home())
    graphs, queue, rejects = {}, set(), 0
    for f in sorted(data.rglob("*.json")):
        rel = str(f.relative_to(data))
        if rel.endswith("graph" + ".json"):
            graphs[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    for x in json.loads((data / "review_queue.json").read_text(encoding="utf-8")):
        queue.add((x["kind"], x["doc_id"], json.dumps(x["payload"], sort_keys=True, ensure_ascii=False)))
    rj = data / "gate_rejects.json"
    if rj.exists():
        rejects = len(json.loads(rj.read_text(encoding="utf-8")))
    return graphs, queue, rejects


def idempotent(serial=False):
    """**클린 2회 동일 그래프**(문서 7 §7.6-4) — `(통과, 덧말)`. 병렬이면 제 임시 루트에서(스위트와 함께 돈다) · 다르면 그 자리를 남긴다."""
    from core import paths
    tmp, env, home, same = None, None, paths.home(), True
    if not serial:
        tmp, home, env, _work = _temp_root("onto_idem_")
    try:
        rc, residue = clean(env, home)
        if rc or residue:
            return False, f"클린을 못 만들어 재지 않았다 — init --fresh --all rc={rc} · 잔재 {residue}"
        snaps = []
        for _i in range(2):
            subprocess.run([sys.executable, str(ROOT / "run.py"), "all"], capture_output=True, text=True,
                           cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
            snaps.append(_snap(home))
        (g1, q1, r1), (g2, q2, r2) = snaps
        same = g1 == g2 and q1 == q2
        note = (f"그래프 {len(g1)}층 바이트 동일 · 큐 {len(q1)}항목 집합 동일 · 거부 로그 {r1}→{r2}" if same else
                f"그래프 {'동일' if g1 == g2 else '다름'} · 큐 1회만 {len(q1 - q2)}건 / 2회만 {len(q2 - q1)}건")
        if not same and tmp is not None:
            note += f" · 붉은 기록 {keep_red(tmp, '클린2회', note + chr(10))}"
            tmp = None
        return same, note
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def parse_why(argv):
    """`--why <스위트>=<사유>`(되풀이) → `{스위트: 사유}`."""
    out = {}
    for i, a in enumerate(argv):
        if a == "--why" and i + 1 < len(argv) and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            out[k.strip()] = v.strip()
    return out
