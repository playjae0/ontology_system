# -*- coding: utf-8 -*-
"""칸 0.3 — **명세 낱말 대조** — 정리 회차(명세를 지금 규칙만으로 다시 쓰는 회차)의 「의미 변경 0」을 기계가 재는 도구 (B158 ②).

    python tools/spec_terms.py --base <태그> <명세 파일>                          차이 목록 — 차이가 있으면 rc 1
    python tools/spec_terms.py --base <태그> <명세 파일> --account <대조 파일>     차이 전부가 대조 표에 있으면 rc 0

태그의 판(`git show <태그>:<파일>`)과 지금 판(작업 트리)에서 **규칙 낱말**을 뽑아 두 방향 차이(사라짐 · 생김)를 낸다. 낱말은
집합으로 견준다 — 같은 낱말이 다른 자리에 남아 있으면 차이가 아니다(합치기 · 중복 지우기는 그 낱말의 마지막 자리를 지울 때만 보인다).

  · 백틱 안 글 · 절 · 항 표지(§n.n · n.n-X-n 꼴 · 「문서 n」) · 조항 id(문서 1 꼴 — A10 · N3 · C38 …) · 출처 표지(B### · D-### ·
    [정정] n) · 수와 단위(숫자 뒤 자 · 행 · 줄 · 초 · 분 · MB · % · 종 · 건 · 회 · 개 …) · 명령 줄(`python …` — 백틱 밖도)
  · 머리줄(`#`로 시작하는 줄) 목록은 글자 그대로 같아야 한다

대조 파일은 표 `| 낱말 | 방향 | 까닭 · 자리 |` 하나(다른 표는 읽지 않는다) — 낱말 칸은 백틱 한 겹을 벗기고 `\\|`를 `|`로 읽는다 ·
방향은 「사라짐」 · 「생김」 · 까닭은 닫힌 넷(`REASONS` — 그 밖의 차이는 의미 변경이라 만들지 않는다). rc 1: 표에 없는 차이 ·
차이가 아닌 줄(표에만 있다) · 닫힌 값 밖 까닭 · 머리줄이 다르다. 쓰기 0.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAD = ("낱말", "방향", "까닭 · 자리")
DIRS = ("사라짐", "생김")
#: 까닭의 닫힌 값 — 칸이 이 말로 시작해야 한다(요청문 B158 ②)
REASONS = ("합침 — ", "이력 — 개정대장", "중복 — ", "꼬리로 옮김")
_UNIT = "자리|시간|MB|GB|KB|px|자|행|줄|초|분|%|종|건|회|개|쌍|칸|단|쪽|장|벌|곳|층|번|배|일|주"
PATTERNS = (
    ("백틱", re.compile(r"`([^`\n]+)`")),
    ("절", re.compile(r"§ ?\d+(?:\.\d+)*(?:-[A-Z])?(?:-\d+)?")),
    ("항", re.compile(r"(?<![\w.§])\d+\.\d+-(?:[A-Z]-)?\d+")),
    ("문서", re.compile(r"문서 ?\d+")),
    ("출처", re.compile(r"(?<![A-Za-z0-9_])B\d{2,4}(?![0-9])|D-\d{1,4}|\[정정\] ?\d+")),
    ("조항", re.compile(r"(?<![A-Za-z0-9_])[A-Z]\d{1,2}(?![0-9])")),
    ("수", re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?[ \t]?(?:" + _UNIT + ")")),
    ("명령", re.compile(r"python3?[ \t]+(?:-m[ \t]+)?[A-Za-z0-9_./]+(?:[ \t]+[A-Za-z0-9_./:@=<>$-]+)*")),
)


def terms(text):
    """규칙 낱말 `{낱말: 종류}` — 공백 묶음은 한 칸으로 · 백틱 밖 낱말(명령 · 수 · 표지)은 한 줄 안에서만 잇는다(줄을 나눠도 낱말이 달라지지 않게)."""
    out = {}
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            t = re.sub(r"\s+", " ", (m.group(1) if rx.groups else m.group(0))).strip()
            if t:
                out.setdefault(t, kind)
    return out


def heads(text):
    return [ln for ln in text.split("\n") if ln.startswith("#")]


def _cells(row):
    parts = re.split(r"(?<!\\)\|", row.strip())
    return [p.strip() for p in parts[1:-1]] if len(parts) >= 3 else None


def _term(cell):
    c = cell.replace("\\|", "|").strip()
    return c[1:-1] if len(c) >= 2 and c[0] == "`" and c[-1] == "`" else c


def account(text):
    """대조 파일의 표 → `[(낱말, 방향, 까닭)]` — 머리가 `HEAD`인 표 하나(구분 줄은 건너뛴다)."""
    rows, on = [], False
    for ln in (text or "").split("\n"):
        cs = _cells(ln) if ln.strip().startswith("|") else None
        if cs is None:
            on = False
            continue
        if tuple(cs) == HEAD:
            on = True
            continue
        if on and not all(re.fullmatch(r":?-{3,}:?", c) for c in cs) and len(cs) == 3:
            rows.append((_term(cs[0]), cs[1], cs[2]))
    return rows


def compare(old, new, account_text=None):
    """`(rc, 줄들, 차이 {(낱말, 방향): 종류})` — 쓰기 0."""
    a, b = terms(old), terms(new)
    diff = {(t, "사라짐"): a[t] for t in a.keys() - b.keys()}
    diff.update({(t, "생김"): b[t] for t in b.keys() - a.keys()})
    ha, hb = heads(old), heads(new)
    lines = [f"  머리줄 — {'같다' if ha == hb else '다르다'} ({len(ha)} → {len(hb)}줄)"]
    if ha != hb:
        lines += [f"    - {x}" for x in ha if x not in hb] + [f"    + {x}" for x in hb if x not in ha]
    n_gone = sum(1 for _t, d in diff if d == "사라짐")
    lines.append(f"  낱말 — 기준 {len(a)} · 지금 {len(b)} · 사라짐 {n_gone} · 생김 {len(diff) - n_gone}")
    bad = ha != hb
    if account_text is None:
        lines += [f"    {d} `{t}` ({k})" for (t, d), k in sorted(diff.items())]
        return (1 if bad or diff else 0), lines, diff
    rows = account(account_text)
    have = {(t, d) for t, d, _r in rows}
    miss = sorted(set(diff) - have)
    extra = sorted(have - set(diff))
    wrong = [(t, d, r) for t, d, r in rows if d not in DIRS or not r.startswith(REASONS)]
    lines.append(f"  대조 표 — 줄 {len(rows)} · 표에 없는 차이 {len(miss)} · 차이 아닌 줄 {len(extra)} · 닫힌 값 밖 {len(wrong)}")
    lines += [f"    [없음] {d} `{t}` ({diff[(t, d)]})" for t, d in miss]
    lines += [f"    [차이 아님] {d} `{t}`" for t, d in extra]
    lines += [f"    [까닭] {d} `{t}` — {r[:40]}" for t, d, r in wrong]
    return (1 if bad or miss or extra or wrong else 0), lines, diff


def _git_show(base, rel):
    r = subprocess.run(["git", "show", f"{base}:{rel}"], cwd=ROOT, capture_output=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise SystemExit(f"기준을 읽지 못했다 — {base}:{rel} ({r.stderr.decode('utf-8', 'replace').strip()[:120]})")
    return r.stdout.decode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="spec_terms", description="명세 낱말 대조 — 정리 회차의 의미 변경 0")
    ap.add_argument("--base", required=True, help="기준 태그 · 커밋")
    ap.add_argument("spec", help="명세 파일(레포 안 경로)")
    ap.add_argument("--account", help="대조 파일 — 표 | 낱말 | 방향 | 까닭 · 자리 |")
    a = ap.parse_args(argv)
    p = Path(a.spec).resolve()
    rel = p.relative_to(ROOT).as_posix()
    acc = Path(a.account).read_text(encoding="utf-8") if a.account else None
    rc, lines, _d = compare(_git_show(a.base, rel), p.read_text(encoding="utf-8"), acc)
    print(f"■ 낱말 대조 — {rel} · 기준 {a.base}" + (f" · 대조 {a.account}" if a.account else ""))
    print("\n".join(lines))
    print(f"결과: {'같다(대조 끝)' if rc == 0 else '어긋남'} · rc {rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
