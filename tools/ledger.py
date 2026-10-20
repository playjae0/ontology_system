# -*- coding: utf-8 -*-
"""칸 0.3 — **장부 자동화** — 회차 마감에 손으로 하던 장부 일을 그대로 기계로 (B131 ③ · 마감 한 줄의 0단계).

    python tools/ledger.py [--base <커밋>]      쓰고 무엇을 옮겼나 한 줄씩(마감 한 줄이 부른다 — 혼자 쳐도 같다)
    python tools/ledger.py --dry [--base …]     쓰기 0 · 할 일만

  ⓐ PROGRESS 최근 3회차 — `## B### — …` 절이 셋을 넘으면 오래된 것부터 `docs/archive/장부/PROGRESS_B###.md`로 옮기고 색인에
     한 줄 · **이번 회차를 셋째로 친다**(살아 있는 요청문 — PROGRESS에 절이 없는 `docs/안건/B###_요청문.md` — 가 있으면 남기는
     절은 그만큼 적다: 마감 보고를 쓰면 셋이 된다)
  ⓑ 안건 정리 — 살아 있는 요청문 + PROGRESS에 남은 회차의 안건만 남긴다(나머지 `B###_*.md`는 지운다 — git 이력이 보관이다)
  ⓒ 결정 번호 — `DECISIONS.md`의 `D-###`가 겹침 · 빈 번호 없이 이어지는가 · 말번 · 기준 커밋 뒤 새 번호 · PROGRESS가 적은
     번호가 장부에 다 있는가(채번 전 번호를 적지 않는다 — CLAUDE.md §4)
  ⓓ 자산 해시 — 레포 정본 자산이 기록과 다르면 기록을 다시 쓴다(무엇이 달랐나 한 줄)
코드 지도는 마감 한 줄의 0단계가 따로 다시 만든다(생성물).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "PROGRESS.md"
ARCHIVE = ROOT / "docs" / "archive" / "장부"
AGENDA = ROOT / "docs" / "안건"
DECISIONS = ROOT / "DECISIONS.md"
KEEP = 3
_SEC = re.compile(r"^## (B\d+[A-Za-z0-9]*) — ", re.M)
_REQ = re.compile(r"^(B\d+[A-Za-z0-9]*)_요청문\.md$")
_ITEM = re.compile(r"^(B\d+[A-Za-z0-9]*)_")
_DEC = re.compile(r"^\| \*\*D-(\d+)\*\* \|", re.M)
_REF = re.compile(r"\bD-(\d{2,4})\b")


def _sections(text):
    """`(머리 글, [(회차, 절 글)])` — 절은 `## B### — ` 줄부터 다음 절 앞까지(끝의 `---` 줄은 뗀다)."""
    hits = list(_SEC.finditer(text))
    if not hits:
        return text, []
    out = []
    for i, m in enumerate(hits):
        body = text[m.start():hits[i + 1].start() if i + 1 < len(hits) else len(text)].rstrip()
        if body.endswith("---"):
            body = body[:-3].rstrip()
        out.append((m.group(1), body))
    return text[:hits[0].start()], out


def _index_line(rid, body):
    head = body.splitlines()[0][3:]
    m = re.match(r"^(B\S+) — (.*?)(?: \((\d{4}-\d{2}-\d{2})[^)]*\))?\s*$", head)
    title, date = (m.group(2), m.group(3)) if m else (head, None)
    return f"- {rid} — {title}" + (f" · {date}" if date else "") + f" · **완료** — 본문 `docs/archive/장부/PROGRESS_{rid}.md`"


def live_rounds(secs_ids, agenda=AGENDA):
    """살아 있는 회차 — 요청문은 있고 PROGRESS에 절이 없다(이번에 마감하는 회차)."""
    reqs = sorted(m.group(1) for p in agenda.glob("*.md") if (m := _REQ.match(p.name)))
    return [r for r in reqs if r not in secs_ids]


def progress(dry=False):
    """ⓐ — 옮긴 회차 목록 · 줄 몇 개."""
    text = PROGRESS.read_text(encoding="utf-8")
    pre, secs = _sections(text)
    live = live_rounds({r for r, _b in secs})
    keep = max(0, KEEP - len(live))
    move, stay = (secs[:-keep] if keep else secs), (secs[-keep:] if keep else [])
    if len(secs) <= keep:
        return [], live, [r for r, _b in secs]
    closing = live[0] if live else secs[-1][0]
    lines = []
    for rid, body in move:
        lines.append(_index_line(rid, body))
        if not dry:
            (ARCHIVE / f"PROGRESS_{rid}.md").write_text(
                f"# PROGRESS — {rid} (옮겨진 회차 · 본문)\n\n> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). "
                f"{rid}의 본문을 여기로 옮겼다({closing} 마감 때).\n\n{body}\n", encoding="utf-8")
    if not dry:
        idx = list(re.finditer(r"^- B\S+ — .*$", pre, re.M))
        at = idx[-1].end() if idx else len(pre.rstrip())
        pre = pre[:at] + "".join("\n" + ln for ln in lines) + pre[at:]
        PROGRESS.write_text(pre.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(b for _r, b in stay) + "\n", encoding="utf-8")
    return [r for r, _b in move], live, [r for r, _b in stay]


def agenda(keep_ids, dry=False):
    """ⓑ — 지운 안건 파일 이름 목록(살아 있는 요청문 + PROGRESS에 남은 회차만 남긴다)."""
    gone = []
    for p in sorted(AGENDA.glob("B*_*.md")):
        m = _ITEM.match(p.name)
        if m and m.group(1) not in keep_ids:
            gone.append(p.name)
            if not dry:
                p.unlink()
    return gone


def decisions(base=None):
    """ⓒ — `(통과, 한 줄)`."""
    text = DECISIONS.read_text(encoding="utf-8")
    ns = [int(x) for x in _DEC.findall(text)]
    if not ns:
        return False, "DECISIONS.md에 D-### 행이 없다"
    dup = sorted({n for n in ns if ns.count(n) > 1})
    gaps = [n for n in range(min(ns), max(ns) + 1) if n not in set(ns)]
    new = []
    if base:
        r = subprocess.run(["git", "show", f"{base}:DECISIONS.md"], cwd=str(ROOT), capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if r.returncode == 0:
            new = sorted(set(ns) - {int(x) for x in _DEC.findall(r.stdout)})
    old = set(range(1, min(ns)))                         # 옮긴 장부의 번호 — 말번 앞이면 있다고 본다
    refs = {int(x) for x in _REF.findall(PROGRESS.read_text(encoding="utf-8"))}
    unknown = sorted(n for n in refs if n not in set(ns) and n not in old)
    ok = not dup and not gaps and not unknown
    return ok, (f"말번 D-{max(ns)} · 이번 회차 새 번호 {' · '.join(f'D-{n}' for n in new) or '없음'}"
                + (f" · 겹침 {dup}" if dup else "") + (f" · 빈 번호 {gaps}" if gaps else "")
                + (f" · PROGRESS가 적은 장부에 없는 번호 {[f'D-{n}' for n in unknown]}" if unknown else ""))


def assets(dry=False):
    """ⓓ — `[달라진 것]`(다시 썼다)."""
    sys.path.insert(0, str(ROOT / "tests"))
    import asset_hashes as AH
    chg, add, gone = AH.diff()
    what = [f"다름 {x}" for x in chg] + [f"새 {x}" for x in add] + [f"사라짐 {x}" for x in gone]
    if what and not dry:
        AH.write()
    return what


def run(base=None, dry=False):
    """마감 한 줄의 0단계 — `[(통과 또는 None(갱신), 이름, 한 줄)]`."""
    rows = []
    moved, live, stay = progress(dry)
    rows.append((None if moved else True, "PROGRESS 최근 3회차",
                 (f"옮김 {' · '.join(moved)} → docs/archive/장부/PROGRESS_<회차>.md · 색인 {len(moved)}줄" if moved
                  else "그대로") + f" · 남음 {' · '.join(stay) or '없음'}" + (f" · 이번 회차 {' · '.join(live)}" if live else "")))
    gone = agenda(set(live) | set(stay), dry)
    rows.append((None if gone else True, "안건 정리", f"지움 {' · '.join(gone)}" if gone else "그대로"))
    ok, msg = decisions(base)
    rows.append((ok, "결정 번호", msg))
    what = assets(dry)
    rows.append((None if what else True, "자산 해시 다시 쓰기", ("다시 씀 — " + " · ".join(what))[:300] if what else "기록과 같다"))
    return rows


def main(argv):
    base = argv[argv.index("--base") + 1] if "--base" in argv and argv.index("--base") + 1 < len(argv) else None
    rows = run(base, "--dry" in argv)
    for ok, label, detail in rows:
        print(f"  [{'PASS' if ok else 'FAIL' if ok is False else '갱신'}] {label} — {detail}")
    return 1 if any(ok is False for ok, _l, _d in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
