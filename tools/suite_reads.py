# -*- coding: utf-8 -*-
"""칸 0.3 — **스위트가 실제로 읽는 파일** — `doctor --changed`의 정적 그래프를 실행으로 대조한다 (B117 ① · 도구 · 판정 아님).

    python tools/suite_reads.py            스위트 전부를 클린 단독으로 돌리며 각자 연(open) 레포 파일 · 실은 모듈을 기록 →
                                           정적 선택(`cli/doctor_select`)이 빠뜨린 (파일, 스위트) 쌍을 센다(약 6분)
    python tools/suite_reads.py --write    + 표본 표 `docs/회귀스위트/자산/스위트_읽기_표본.json`을 다시 쓴다(회귀가 그 표로 잰다)

기록 방법: 하위 실행마다 `sitecustomize`(시스템 임시 폴더 · 레포 밖)가 감사 훅(`open`)과 끝의 `sys.modules`로 레포 안 파일을 적는다 —
스위트가 부르는 하위 실행(`run.py` · `-m cli.…` · doctor)까지 `PYTHONPATH`로 따라간다. 레포가 추적하는 파일만 센다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "docs" / "회귀스위트" / "자산" / "스위트_읽기_표본.json"
#: 표본 — 코어 · CLI · 파서 · 문서 · 시험 도우미 하나씩(바꾸면 표가 따라 다시 쓰인다)
SAMPLE_FILES = ("core/build/heading.py", "core/state/rehearsal.py", "cli/register/rehearsal.py",
                "parser/struct_map.py", "cli/show_report.py", "tests/stub_gateway.py",
                "docs/구조도/00_칸_대장.md")

_SITE = '''import os, sys, atexit
_R, _O = os.environ.get("SUITE_READS_ROOT"), os.environ.get("SUITE_READS_OUT")
if _R and _O:
    _seen = set()
    def _hook(ev, args):
        if ev == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            try:
                p = os.path.realpath(os.fsdecode(args[0]))
            except Exception:
                return
            if p.startswith(_R + os.sep):
                _seen.add(p[len(_R) + 1:])
    sys.addaudithook(_hook)
    def _dump():
        for m in list(sys.modules.values()):
            f = getattr(m, "__file__", None)
            if f:
                p = os.path.realpath(f)
                if p.startswith(_R + os.sep):
                    _seen.add(p[len(_R) + 1:])
        try:
            with open(os.path.join(_O, str(os.getpid()) + ".txt"), "a", encoding="utf-8") as fh:
                fh.write("\\n".join(sorted(_seen)) + "\\n")
        except Exception:
            pass
    atexit.register(_dump)
'''


def suites():
    src = (ROOT / "doctor.py").read_text(encoding="utf-8")
    return re.findall(r'^    \("(test_[a-z0-9_]+|verify_roundtrip)"', src, re.M)


def tracked():
    out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=str(ROOT), capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return set(out.splitlines())


def record(names):
    """`{스위트: [레포 추적 파일]}` — 스위트마다 클린 → 실행(기록 켬)."""
    sys.path.insert(0, str(ROOT))
    from core.llm import gateway
    base = gateway.isolated_env()
    tmp = Path(tempfile.mkdtemp(prefix="suite_reads_"))
    try:
        (tmp / "site").mkdir()
        (tmp / "site" / "sitecustomize.py").write_text(_SITE, encoding="utf-8")
        keep, reads = tracked(), {}
        for n in names:
            subprocess.run([sys.executable, "run.py", "init", "--fresh", "--all"], cwd=str(ROOT), env=base,
                           capture_output=True, stdin=subprocess.DEVNULL)
            d = tmp / n
            d.mkdir()
            env = dict(base, PYTHONPATH=str(tmp / "site"), SUITE_READS_ROOT=str(ROOT), SUITE_READS_OUT=str(d))
            subprocess.run([sys.executable, f"tests/{n}.py"], cwd=str(ROOT), env=env, capture_output=True,
                           stdin=subprocess.DEVNULL)
            got = set()
            for f in d.glob("*.txt"):
                got |= set(f.read_text(encoding="utf-8").splitlines())
            reads[n] = sorted(x for x in got if x in keep)
            print(f"  {n:<24} 읽은 레포 파일 {len(reads[n]):>4}", flush=True)
        subprocess.run([sys.executable, "run.py", "init", "--fresh", "--all"], cwd=str(ROOT), env=base,
                       capture_output=True, stdin=subprocess.DEVNULL)
        return reads
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compare(reads):
    """`(빠뜨린 쌍 {파일: [스위트]}, 고를 수 없는 파일 수, 고른 파일 수)` — 정적 선택 ⊇ 실행 읽기인가."""
    sys.path.insert(0, str(ROOT))
    from cli import doctor_select as DS
    names = list(reads)
    facts = DS.suite_facts(names)
    miss, unpick, picked = {}, 0, 0
    for f in sorted({x for v in reads.values() for x in v}):
        hit = DS.readers(f, facts)
        if hit is None:
            unpick += 1
            continue
        picked += 1
        lost = sorted({s for s, v in reads.items() if f in v} - hit)
        if lost:
            miss[f] = lost
    return miss, unpick, picked


def main(argv):
    names = suites()
    print(f"■ 스위트 {len(names)}종이 실제로 읽는 파일 — 클린 단독 · 실행 기록(판정 아님)")
    reads = record(names)
    miss, unpick, picked = compare(reads)
    print(f"\n레포 파일(실제로 읽힌 것) {unpick + picked} · 고를 수 없음(전체) {unpick} · 고른 것 {picked} · "
          f"빠뜨림 있는 파일 {len(miss)}")
    for f, lost in list(miss.items())[:30]:
        print(f"  [빠뜨림] {f} → {' · '.join(lost)}")
    if "--write" in argv:
        table = {f: sorted(s for s, v in reads.items() if f in v) for f in SAMPLE_FILES}
        SAMPLE.write_text(json.dumps({"_출처": "tools/suite_reads.py --write — 실행 기록(창작 표본 위의 회귀) · "
                                                "회귀는 정적 선택이 이 표를 빠뜨리지 않는지 잰다",
                                      "표본": table}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"표본 표 → docs/회귀스위트/자산/{SAMPLE.name}")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
