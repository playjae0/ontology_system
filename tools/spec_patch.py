# -*- coding: utf-8 -*-
"""칸 0.3 — **명세 패치** — 마감 보고의 「명세가 바뀌어야 할 문장」을 기계가 옮기는 양식 (B117 ② · 사용자 확정 2026-10-16).

    python tools/spec_patch.py --check docs/안건/B###_명세패치.md     구현 세션 — 쓰기 0
    python tools/spec_patch.py --apply docs/안건/B###_명세패치.md     **허브만** — 하나라도 어긋나면 쓰기 0

양식(항목마다 — `###` 머리 · 세 줄 · 값이 여러 줄이면 다음 열쇠 줄 전까지 이어진다 · 사이의 빈 줄은 값이고 끝의 빈 줄은 버린다):

    ### <파일> <절>
    지금: <명세에서 그대로 복사 — 그 파일에서 정확히 한 번 나오는 문자열>
    바뀔: <그 자리에 들어갈 전체 문장>
    까닭: <한 줄 — 회차 · D-###>

새 문장 끼우기는 `지금`에 앞 문장, `바뀔`에 앞 문장 + 새 문장(표의 새 행도 같다 — 앞 행 + 새 행).

`--check`가 보는 것: ①항목마다 열쇠 넷(파일 · 지금 · 바뀔 · 까닭) ②`지금`이 그 파일에서 **정확히 한 번**(앞 항목을 적용한 판에서도) ③`바뀔`의
새 몫이 **지금 규칙만** — 취소선 · 「구판」 서술 · `[개정]` 꼬리표 없이 · 출처 꼬리 `(B###)` 하나 이상 · 표 행이면 `|`로 시작하고 끝난다
④명세 사본에 전부 적용한 뒤 **문서 검사 일곱이 그대로**(위반이 늘지 않는다 — 명세 모양 점검 포함). 어긋난 항목은 이름(파일 · 절)으로 말한다.
**늘어난 것이 미러 봉인뿐이면**(미러 body · mirror 문면이 바뀌었고 앵커는 그대로) 실패가 아니라 「재봉인 대상 <쌍>」 알림이다(B121 ④) —
허브가 양쪽을 대조한 뒤 `점검_미러.py --seal`. 다른 검사가 함께 늘면 지금처럼 어긋남이다.
`--apply`는 같은 검사를 지나야만 쓴다 — 파일마다 임시 파일 + `os.replace`(원자적) · 하나라도 어긋나면 쓰기 0 · 재봉인 알림은 쓴 뒤에도 같은 줄.
**글자 증감**(B163 ⓪ — 명세 패치 규칙을 기억에 기대지 않게 · CLAUDE.md §8): 항목 줄 끝에 `(±n자)`(`바뀔` − `지금`) · 결과 줄 바로 앞에
「글자 증감 합 ±n자」(항목의 합) — 표시만이다(판정 · 종료 코드 불변).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "spec"
CHECK_DIR = ROOT / "docs" / "회귀스위트"
CHECKS = ("문면", "경로", "문서간", "가이드", "자산", "미러", "모양")
KEYS = ("지금", "바뀔", "까닭")
_TAIL = re.compile(r"\(B\d{2,4}[^)]*\)")


def parse(text):
    """패치 글 → `[{"name", "file", "지금", "바뀔", "까닭"}]` · 양식 오류는 `("오류", 줄)` 목록으로 함께."""
    items, errs, cur, key = [], [], None, None
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("### "):
            cur = {"name": line[4:].strip(), "line": i}
            items.append(cur)
            key = None
            continue
        if cur is None:
            continue
        m = re.match(r"^(지금|바뀔|까닭):\s?(.*)$", line)
        if m:
            key = m.group(1)
            if key in cur:
                errs.append((cur["name"], f"{i}행: '{key}:'가 두 번"))
            cur[key] = m.group(2)
        elif key and key != "까닭":
            cur[key] += "\n" + line                       # 빈 줄도 값이다(새 문단) — 끝의 빈 줄만 버린다
    for it in items:
        for k in ("지금", "바뀔"):
            if k in it:
                it[k] = it[k].rstrip("\n")
        it["file"] = it["name"].split()[0] if it["name"] else ""
        for k in KEYS:
            if not (it.get(k) or "").strip():
                errs.append((it["name"], f"'{k}:'가 없거나 비었다"))
    return items, errs


def _target(spec, name):
    p = Path(name)
    if p.parts[:2] == ("docs", "spec"):
        p = Path(*p.parts[2:])
    return Path(spec) / p.name


def lint(it):
    """`바뀔`의 새 몫 — 지금 규칙만인가. 돌려주는 것은 어긋남 목록."""
    old, new = it["지금"], it["바뀔"]
    added = new[len(old):] if new.startswith(old) else new
    bad = []
    if "~~" in added:
        bad.append("취소선")
    if "구판" in added:
        bad.append("「구판」 이력 서술")
    if "[개정]" in added:
        bad.append("[개정] 꼬리표(이력은 개정대장 몫)")
    if not _TAIL.search(added):
        bad.append("출처 꼬리 (B###) 없음")
    for ln in new.splitlines():
        s = ln.strip()
        if s.startswith("|") and not s.endswith("|"):
            bad.append("표 칸 밖 글")
            break
    return bad


def _signed(n):
    return f"+{n:,}" if n > 0 else f"−{-n:,}" if n < 0 else "0"


def plan(patch, spec=SPEC):
    """`(새 글 {파일: 글}, 항목 결과 [(이름, 어긋남 목록, 글자 증감)], 양식 오류)` — 쓰기 0."""
    items, errs = parse(Path(patch).read_text(encoding="utf-8"))
    texts, results = {}, []
    for it in items:
        bad = []
        delta = len(it.get("바뀔") or "") - len(it.get("지금") or "")
        p = _target(spec, it["file"])
        if not p.exists():
            bad.append(f"파일 없음 {it['file']}")
        elif it.get("지금") and it.get("바뀔"):
            t = texts.get(p) if p in texts else p.read_text(encoding="utf-8")
            n = t.count(it["지금"])
            if n != 1:
                bad.append(f"'지금'이 그 파일에서 {n}번" + (" (앞 항목 적용 뒤)" if p in texts else ""))
            else:
                texts[p] = t.replace(it["지금"], it["바뀔"], 1)
            bad += lint(it)
        results.append((it["name"], bad, delta))
    return texts, results, errs


def checks(spec_dir):
    """문서 검사 일곱 — `{검사: (rc, 끝 줄, 전문)}` · 모양 점검은 기준을 내리지 않는다(사본) · 일곱은 서로 다른 결과 파일이라 함께 돈다."""
    env = dict(os.environ, REFINED_DIR=str(spec_dir))

    def one(k):
        r = subprocess.run([sys.executable, str(CHECK_DIR / f"점검_{k}.py")], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return k, (r.returncode, ((r.stdout or "").strip().splitlines() or [""])[-1].strip(), r.stdout or "")
    with ThreadPoolExecutor(len(CHECKS)) as ex:
        return dict(ex.map(one, CHECKS))


def _mirror_ids(text):
    """미러 검사 전문 → `(봉인과 다른 쌍, 앵커를 못 찾은 쌍)`."""
    return ({m.group(1) for m in re.finditer(r"✗ (.+?) — (?:mirror|body) 쪽 문면이 봉인과 다르다", text)},
            {m.group(1) for m in re.finditer(r"✗ (.+?) — \S+에서 앵커를 못 찾음", text)})


def _reseal(after, now, worse):
    """늘어난 것이 미러 봉인뿐인가 — 재봉인 대상 쌍 목록(아니면 빈 목록) (B121 ④)."""
    if worse != ["미러"]:
        return []
    (a_seal, a_lost), (n_seal, n_lost) = _mirror_ids(after["미러"][2]), _mirror_ids(now["미러"][2])
    return [] if a_lost - n_lost else sorted(a_seal - n_seal)


def verify(patch, spec=SPEC):
    """`(통과, 줄 목록, 새 글)` — 항목 · 양식 · 사본 적용 뒤 문서 검사 일곱."""
    texts, results, errs = plan(patch, spec)
    lines, ok = [], not errs
    for name, why in errs:
        lines.append(f"[FAIL] 양식 — {name}: {why}")
    for name, bad, delta in results:
        ok = ok and not bad
        lines.append(f"[{'PASS' if not bad else 'FAIL'}] {name}" + (f" — {' · '.join(bad)}" if bad else "")
                     + f" ({_signed(delta)}자)")
    tmp = Path(tempfile.mkdtemp(prefix="spec_patch_"))
    kept = {f: f.read_bytes() for f in (CHECK_DIR / "자산").glob("*_결과.json")}   # 검사가 남기는 결과 파일 — 점검은 쓰기 0
    try:
        copy = tmp / "docs" / "spec"
        shutil.copytree(spec, copy)
        if (Path(spec).parent / "archive").exists():          # 문서간 검사가 보관 파일의 개정 번호도 읽는다
            shutil.copytree(Path(spec).parent / "archive", tmp / "docs" / "archive")
        for p, t in texts.items():
            (copy / p.name).write_text(t, encoding="utf-8")
        after = checks(copy)
        now = checks(spec)
        worse = [k for k in CHECKS if after[k][0] and not now[k][0]]
        reseal = _reseal(after, now, worse)
        if reseal:
            worse = []
        ok = ok and not worse
        lines.append(f"[{'PASS' if not worse else 'FAIL'}] 사본 적용 뒤 문서 검사 일곱 — "
                     + " · ".join(f"{k} {'위반' if after[k][0] else '0'}" for k in CHECKS)
                     + (f" — 늘었다: {' · '.join(worse)}" if worse else " (미러는 재봉인 대상)" if reseal else " (그대로)"))
        for k in worse:
            lines.append(f"       {k}: {after[k][1][:200]}")
        if reseal:
            lines.append(f"[알림] 재봉인 대상 {' · '.join(reseal)} — 허브가 양쪽을 대조한 뒤 "
                         f"python docs/회귀스위트/점검_미러.py --seal (실패 아님)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for f, b in kept.items():
            if not f.exists() or f.read_bytes() != b:
                f.write_bytes(b)
    lines.append(f"글자 증감 합 {_signed(sum(d for _n, _b, d in results))}자")     # 결과 줄 바로 앞(표시만 — 판정 불변)
    return ok, lines, texts


def apply(patch, spec=SPEC):
    """허브 — 검사를 지난 패치만 쓴다(파일마다 임시 파일 → 전부 준비된 뒤 `os.replace`) · 어긋나면 쓰기 0."""
    ok, lines, texts = verify(patch, spec)
    if not ok:
        return False, lines[:-1] + ["쓰기 0 — 위 어긋남을 고친 패치로 다시"] + lines[-1:]     # 증감 합은 결과 줄 바로 앞
    staged = []
    try:
        for p, t in texts.items():
            tmp = p.with_name(f".{p.name}.patch.tmp")
            tmp.write_text(t, encoding="utf-8")
            staged.append((tmp, p))
        for tmp, p in staged:
            os.replace(tmp, p)
    finally:
        for tmp, _p in staged:
            tmp.unlink(missing_ok=True)
    return True, lines[:-1] + [f"적용 — 파일 {len(texts)}"] + lines[-1:]


def main(argv):
    mode = next((a for a in argv if a in ("--check", "--apply")), None)
    rest = [a for a in argv if not a.startswith("--")]
    spec = Path(argv[argv.index("--spec") + 1]) if "--spec" in argv else SPEC
    rest = [a for a in rest if str(spec) != a]
    if not mode or not rest:
        print("[사용법] python tools/spec_patch.py --check|--apply docs/안건/B###_명세패치.md [--spec <명세 폴더>]")
        return 2
    patch = rest[0]
    print(f"■ 명세 패치 {'점검' if mode == '--check' else '적용'} — {patch}")
    if mode == "--check":
        ok, lines, _t = verify(patch, spec)
    else:
        ok, lines = apply(patch, spec)
    print("\n".join(lines))
    print(f"결과: {'통과' if ok else '어긋남 있음'}" + (" · 쓰기 0(점검)" if mode == "--check" else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
