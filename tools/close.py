# -*- coding: utf-8 -*-
"""칸 0.3 — **마감 한 줄** — 장부 → 사전 점검 → 마감 doctor 1회 → 네 벌 → §7 상한 → 자산 해시 → 기대 수 기록 → 한 화면 요약 (B117 ① · B131).

    python tools/close.py --base <반입 커밋>                    마감 — 요약 화면을 마감 보고에 그대로 붙인다
    python tools/close.py --base <커밋> --serial                 doctor를 직렬로(레포 mock 루트 — 병렬과 대조하는 둘째 마감 · B131 ①)
    python tools/close.py --base <커밋> --why <스위트>=<사유>     기대 수보다 줄어든 스위트를 사유와 함께 기록(되풀이 · B131 ②)
    python tools/close.py --base <커밋> --only <스위트…>         doctor만 고른 실행(**판정 아님** — 시험 · 개발용 · 그 스위트의 기록만)

회차마다 손으로 치던 마감 순서를 한 자리로 모았다. **첫 FAIL에서 멈추지 않고 끝까지** 돈다 — 무엇이 몇 개 어긋났는지를 한 번에
본다. 종료 코드는 하나라도 FAIL이면 1이다. 각 단계의 전문은 시스템 임시 폴더에 남기고 요약 끝 줄이 그 자리를 말한다(레포 밖).

  0 장부(`tools/ledger.py` — PROGRESS 최근 3회차 · 안건 정리 · 결정 번호 · 자산 해시 · 무엇을 옮겼나 한 줄씩) · 코드 지도를 다시
    만든다(생성물 — `docs/회귀스위트/추출_구조.py`) · 바뀌었으면 「갱신 — 커밋에 넣는다」(FAIL 아님)
  1 사전 점검 — `test_g1_g2` · `test_places`(클린 단독 · doctor의 기대 수) · 층 어휘 정적 점검(`tools/layer_words.py` — 코드 ·
    지시문에 층 config의 카테고리 이름 · 층 폴더 이름 0 · B121 ①) · 레포 쓰기 정적 점검(`tools/repo_writes.py` — 시험 소스에서
    레포 경로로 쓰기 0 · B133 ①) · 문서 검사 일곱(`점검_*.py` — 모양 포함)
  2 마감 doctor 1회 — 회귀 명령(`doctor.py --regress` — B133 ③) · 전체 · 클린 단독 · 병렬(스위트마다 제 임시 자리 — `--serial`이면 직렬) · 완료판정 4(클린 2회 동일 그래프)
  3 네 벌 — `tools/four_way.py --base <커밋>`(0 같다 · 1 다르다 · 2 못 돌았다)
  4 §7 상한 — 코드 지도 ⓔ의 파일 · 함수 상한 위반 수
  5 자산 해시 — 레포 정본 자산(`prompts/` · `kit/` · `schemas/blocks.json` · `layers/`)이 기록과 같은가(0단계가 다시 쓴 뒤)
  6 기대 수 기록 — doctor가 초록이면 스위트마다 PASS 수를 `docs/회귀스위트/기대_수.json`에 쓴다 · 바뀐 스위트마다 「+n」 · 「−n 사유」
    (줄어든 수는 `--why`가 있어야 doctor가 지나가고 사유가 기록에 남는다 · PASS 0 · 돌지 않은 스위트는 늘 붉다 — `cli/doctor_run`)
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


_MARK = {True: "PASS", False: "FAIL", None: "갱신", "skip": "건너뜀"}


def _why_args(argv):
    """`--why <스위트>=<사유>`(되풀이) → `{스위트: 사유}`."""
    out = {}
    for i, a in enumerate(argv):
        if a == "--why" and i + 1 < len(argv) and "=" in argv[i + 1]:
            k, v = argv[i + 1].split("=", 1)
            out[k.strip()] = v.strip()
    return out


def expect_record(rec, res, suites, head, at, whole=True, serial=False):
    """기대 수 기록의 새 판 — `(새 기록, 바뀜 [{suite, from, to, why}])` · 순수 함수(마감 한 줄과 시험이 같은 것을 쓴다 · B131 ②).

    `res`는 doctor `--result`(스위트마다 `n` · `secs` · 사유 · 지운 스위트) · `suites`는 doctor의 스위트 목록(합친 스위트의 `was`).
    전체 실행이면 기록은 지금 목록 그대로(지웠거나 합친 이름은 빠진다) · 고른 실행이면 고른 스위트만 고친다 · 소요는 병렬일 때만."""
    sys.path.insert(0, str(ROOT))
    from cli import doctor_run as DR
    was = {x[0]: (x[2] if len(x) > 2 else ()) for x in suites}
    why = res.get("why") or {}
    old = rec.get("suites") or {}
    new = {} if whole else {k: dict(v) for k, v in old.items()}
    changes = []
    for name, v in (res.get("suites") or {}).items():
        exp = DR.expected(name, was.get(name, ()), rec)
        if exp != v["n"]:
            changes.append({"suite": name, "from": exp, "to": v["n"], "why": why.get(name, "")})
        prev = old.get(name, {})
        new[name] = {"n": v["n"], "secs": prev.get("secs") if serial and prev.get("secs") is not None else v.get("secs")}
        if new[name]["secs"] is None:
            new[name].pop("secs")
    for name in res.get("removed") or []:
        changes.append({"suite": name, "from": old.get(name, {}).get("n"), "to": 0, "why": why.get(name, "")})
    log = list(rec.get("log") or []) + [{"at": at, "head": head, **c} for c in changes]
    return {"_note": rec.get("_note") or "생성물 — 마감 한 줄이 쓴다", "suites": new, "log": log[-300:]}, changes


def expect_line(changes):
    """바뀜 한 줄 — `+n` · `−n 사유` · 새 스위트 · 지움."""
    def one(c):
        if c["from"] is None:
            return f"{c['suite']} 새 {c['to']}"
        d = c["to"] - c["from"]
        return f"{c['suite']} {'+' if d > 0 else '−'}{abs(d)}" + (f"(사유 {c['why']})" if d < 0 else "")
    return " · ".join(one(c) for c in changes)


def _expect_row(row, res_file, rc_doc, why, head, only, serial):
    import json
    from datetime import date
    sys.path.insert(0, str(ROOT))
    from cli import doctor_run as DR
    if rc_doc != 0 or not res_file.exists():
        row("skip", "기대 수 기록", "doctor가 붉어 기록하지 않았다(기록은 그대로)")
        return
    import doctor
    res = json.loads(res_file.read_text(encoding="utf-8"))
    rec, changes = expect_record(DR.load(), res, doctor.SUITES, head, date.today().isoformat(),
                                 whole=not only, serial=serial)
    DR.RECORD.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(v["n"] for v in rec["suites"].values())
    row(None if changes else True, "기대 수 기록" + (" (고른 스위트만)" if only else ""),
        (f"바뀜 {len(changes)} — {expect_line(changes)}"[:600] if changes else "바뀐 스위트 없음")
        + f" · 스위트 {len(rec['suites'])} · 합 {n}")


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
    serial = "--serial" in argv
    why = _why_args(argv)

    def row(ok, label, detail=""):
        rows.append((ok, label, detail))
        print(f"  [{_MARK[ok]}] {label}" + (f" — {detail}" if detail else ""), flush=True)

    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout.strip()
    dirty = len(subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True,
                               stdin=subprocess.DEVNULL).stdout.splitlines())
    print(f"■ 마감 한 줄 — 기준 {base} · HEAD {head} · 커밋 안 한 변경 {dirty}"
          + (f" · doctor 고른 실행 {' '.join(only)} — 판정 아님" if only else ""), flush=True)

    # 0 장부 — PROGRESS · 안건 · 결정 번호 · 자산 해시(손으로 하던 것 — B131 ③)
    sys.path.insert(0, str(ROOT / "tools"))
    import ledger
    for ok, label, detail in ledger.run(base):
        row(ok, label, detail)
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
    rc, t = _run([sys.executable, str(ROOT / "tools" / "layer_words.py")], logs / "1_layer_words.txt", env)
    row(rc == 0, "층 어휘 정적 점검", (t.strip().splitlines() or [""])[-1].strip()[:120])
    rc, t = _run([sys.executable, str(ROOT / "tools" / "repo_writes.py")], logs / "1_repo_writes.txt", env)
    row(rc == 0, "레포 쓰기 정적 점검", (t.strip().splitlines() or [""])[-1].strip()[:120])      # 시험은 레포에 쓰지 않는다 (B133 ①)
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
    res_file = logs / "2_doctor_result.json"
    cmd = ([sys.executable, "doctor.py"] + (["--only", *only] if only else ["--regress"]) + (["--serial"] if serial else [])
           + [x for k, v in why.items() for x in ("--why", f"{k}={v}")] + ["--result", str(res_file)])
    t_doc = time.time()
    rc_doc, t = _run(cmd, logs / "2_doctor.txt", env)
    t_doc = time.time() - t_doc
    rc = rc_doc
    got, want = _doctor_total(t)
    idem = _tail(t, r"클린 2회 동일 그래프")
    fails = [ln.strip() for ln in t.splitlines() if "[ 필요 ]" in ln][:6]
    row(rc == 0, "마감 doctor 1회" + (" (직렬)" if serial else " (병렬)") + (" (고른 실행 — 판정 아님)" if only else ""),
        f"합계 {got}/{want} PASS" + (f" · {idem.replace('[  OK ]', '').strip()}" if idem else "")
        + f" · rc {rc} · {t_doc:.0f}초" + ("".join(f"\n         {f}" for f in fails) if fails else ""))

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

    # 6 기대 수 기록 — doctor가 초록일 때만(B131 ②)
    _expect_row(row, res_file, rc_doc, why, head, only, serial)

    nfail = sum(1 for ok, _l, _d in rows if ok is False)
    print("\n" + "=" * 66)
    print(f"마감 한 줄 요약 — 기준 {base} · HEAD {head} · 커밋 안 한 변경 {dirty}"
          + (" · doctor 고른 실행 — 판정 아님" if only else ""))
    for ok, label, detail in rows:
        print(f"[{_MARK[ok]}] {label}" + (f" — {detail}" if detail else ""))
    print(f"FAIL {nfail} · 소요 {time.time() - t0:.0f}초 · 단계 전문 {logs}")
    print("=" * 66)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
