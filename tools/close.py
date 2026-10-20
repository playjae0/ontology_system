# -*- coding: utf-8 -*-
"""칸 0.3 — **마감 한 줄** — 사전 점검 → 마감 doctor 1회 → 네 벌 → §7 상한 · 코드 지도 → 자산 해시 → 한 화면 요약 (B117 ①).

    python tools/close.py --base <반입 커밋>                    마감 — 요약 화면을 마감 보고에 그대로 붙인다
    python tools/close.py --base <커밋> --only <스위트…>         doctor만 고른 실행(**판정 아님** — 시험 · 개발용)

회차마다 손으로 치던 마감 순서를 한 자리로 모았다. **첫 FAIL에서 멈추지 않고 끝까지** 돈다 — 무엇이 몇 개 어긋났는지를 한 번에
본다. 종료 코드는 하나라도 FAIL이면 1이다. 각 단계의 전문은 시스템 임시 폴더에 남기고 요약 끝 줄이 그 자리를 말한다(레포 밖).

  0 코드 지도를 다시 만든다(생성물 — `docs/회귀스위트/추출_구조.py`) · 바뀌었으면 「갱신 — 커밋에 넣는다」(FAIL 아님)
  1 사전 점검 — `test_g1_g2` · `test_places`(클린 단독 · doctor의 기대 수) · 문서 검사 일곱(`점검_*.py` — 모양 포함)
  2 마감 doctor 1회 — 전체 · 클린 단독 · 직렬 · 완료판정 4(클린 2회 동일 그래프) — 지금 doctor 그대로
  3 네 벌 — `tools/four_way.py --base <커밋>`(0 같다 · 1 다르다 · 2 못 돌았다)
  4 §7 상한 — 코드 지도 ⓔ의 파일 · 함수 상한 위반 수
  5 자산 해시 — 레포 정본 자산(`prompts/` · `kit/` · `schemas/blocks.json` · `layers/`)이 기록과 같은가(다르면 `--write`가 필요)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE_DIR = Path("docs", "회귀스위트")
CHECKS = ("문면", "경로", "문서간", "가이드", "자산", "미러", "모양")
PRE = ("test_g1_g2", "test_places")


def _env():
    sys.path.insert(0, str(ROOT))
    from core.llm import gateway
    return gateway.isolated_env()


def _run(cmd, out, env=None, extra=None):
    """하위 실행 하나 — 전문은 `out` 파일 · 돌려주는 것은 `(rc, 전문)`."""
    e = dict(env or _env(), **(extra or {}))
    r = subprocess.run(cmd, cwd=str(ROOT), env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    text = (r.stdout or "") + (r.stderr or "")
    out.write_text(text, encoding="utf-8")
    return r.returncode, text


def _tail(text, pat):
    """전문에서 `pat`과 맞는 마지막 줄(앞 공백 · 표지 정리)."""
    hit = [ln.strip() for ln in text.splitlines() if re.search(pat, ln)]
    return hit[-1] if hit else ""


def _doctor_total(text):
    m = re.search(r"합계 (\d+)/(\d+) PASS", text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def main(argv):
    if "--base" not in argv or argv.index("--base") + 1 >= len(argv):
        print("[사용법] python tools/close.py --base <반입 커밋> [--only <스위트…>]")
        return 2
    base = argv[argv.index("--base") + 1]
    only = []
    if "--only" in argv:
        for a in argv[argv.index("--only") + 1:]:
            if a.startswith("--"):
                break
            only.append(a)
    logs = Path(tempfile.mkdtemp(prefix="onto_close_"))
    env = _env()
    rows, t0 = [], time.time()

    def row(ok, label, detail=""):
        rows.append((ok, label, detail))
        print(f"  [{'PASS' if ok else 'FAIL' if ok is False else '갱신'}] {label}" + (f" — {detail}" if detail else ""),
              flush=True)

    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout.strip()
    dirty = len(subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True,
                               stdin=subprocess.DEVNULL).stdout.splitlines())
    print(f"■ 마감 한 줄 — 기준 {base} · HEAD {head} · 커밋 안 한 변경 {dirty}"
          + (f" · doctor 고른 실행 {' '.join(only)} — 판정 아님" if only else ""), flush=True)

    # 0 코드 지도(생성물)
    _map = ROOT / "docs" / "구조도" / "10_코드_지도.md"
    before = _map.read_bytes() if _map.exists() else b""
    rc, _t = _run([sys.executable, str(ROOT / SUITE_DIR / "추출_구조.py")], logs / "0_code_map.txt", env,
                  {"REFINED_DIR": "docs/spec"})
    after = _map.read_bytes() if _map.exists() else b""
    row(None if (rc == 0 and before != after) else rc == 0, "코드 지도 다시 만들기",
        "바뀌었다 — 커밋에 넣는다" if before != after else ("그대로" if rc == 0 else f"rc {rc}"))

    # 1 사전 점검 — 시험 둘 · 문서 검사 일곱
    rc, t = _run([sys.executable, "doctor.py", "--only", *PRE], logs / "1_pre.txt", env)
    got, want = _doctor_total(t)
    row(rc == 0, f"사전 점검 {' · '.join(PRE)}", f"{got}/{want} PASS" if got is not None else f"rc {rc}")
    parts, bad = [], []
    with ThreadPoolExecutor(len(CHECKS)) as ex:            # 일곱은 서로 다른 결과 파일 — 함께 돈다(순서는 그대로)
        got = list(ex.map(lambda k: _run([sys.executable, str(ROOT / SUITE_DIR / f"점검_{k}.py")],
                                         logs / f"1_check_{k}.txt", env, {"REFINED_DIR": "docs/spec"}), CHECKS))
    for k, (rc, t) in zip(CHECKS, got):
        last = (t.strip().splitlines() or [""])[-1].strip()
        parts.append(f"{k} {last[:60]}")
        if rc:
            bad.append(k)
    row(not bad, "문서 검사 일곱", (" · ".join(parts)) if not bad else f"위반 {' · '.join(bad)} — " + " · ".join(parts))

    # 2 마감 doctor 1회
    cmd = [sys.executable, "doctor.py"] + (["--only", *only] if only else [])
    rc, t = _run(cmd, logs / "2_doctor.txt", env)
    got, want = _doctor_total(t)
    idem = _tail(t, r"클린 2회 동일 그래프")
    fails = [ln.strip() for ln in t.splitlines() if "[ 필요 ]" in ln][:6]
    row(rc == 0, "마감 doctor 1회" + (" (고른 실행 — 판정 아님)" if only else ""),
        f"합계 {got}/{want} PASS" + (f" · {idem.replace('[  OK ]', '').strip()}" if idem else "")
        + f" · rc {rc}" + ("".join(f"\n         {f}" for f in fails) if fails else ""))

    # 3 네 벌
    rc, t = _run([sys.executable, str(ROOT / "tools" / "four_way.py"), "--base", base], logs / "3_four_way.txt", env)
    row(rc == 0, "네 벌", f"{(t.strip().splitlines() or [''])[-1].strip()} (rc {rc})")

    # 4 §7 상한 — 코드 지도 ⓔ
    m = re.search(r"파일 상한 위반 (\d+)\*\* · \*\*함수 상한 위반 (\d+)", _map.read_text(encoding="utf-8")) \
        if _map.exists() else None
    if m:
        row(m.group(1) == "0" and m.group(2) == "0", "§7 상한", f"파일 위반 {m.group(1)} · 함수 위반 {m.group(2)}")
    else:
        line = _tail(_map.read_text(encoding="utf-8") if _map.exists() else "", r"상한 위반")
        row("위반 0" in line and not re.search(r"위반 [1-9]", line), "§7 상한", line[:120] or "코드 지도에 ⓔ 줄이 없다")

    # 5 자산 해시
    sys.path.insert(0, str(ROOT / "tests"))
    from asset_hashes import diff as _diff
    chg, add, gone = _diff()
    row(not (chg or add or gone), "자산 해시",
        "기록과 같다" if not (chg or add or gone) else
        " · ".join([f"다름 {x}" for x in chg] + [f"기록 없음 {x}" for x in add] + [f"사라짐 {x}" for x in gone])[:300]
        + " — 의도한 변경이면 python tests/asset_hashes.py --write")

    nfail = sum(1 for ok, _l, _d in rows if ok is False)
    print("\n" + "=" * 66)
    print(f"마감 한 줄 요약 — 기준 {base} · HEAD {head} · 커밋 안 한 변경 {dirty}"
          + (" · doctor 고른 실행 — 판정 아님" if only else ""))
    for ok, label, detail in rows:
        print(f"[{'PASS' if ok else 'FAIL' if ok is False else '갱신'}] {label}" + (f" — {detail}" if detail else ""))
    print(f"FAIL {nfail} · 소요 {time.time() - t0:.0f}초 · 단계 전문 {logs}")
    print("=" * 66)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
