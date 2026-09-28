#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""칸 0.3 — **가이드가 다시 지저분해지지 않게** (B88 ④ⓓ · 검사 여섯째).

가이드는 회차마다 한 문단씩 덧붙어 「그때 무엇이 바뀌었나」와 「지금 무엇을 치나」가
섞였고, 지운 문서·바뀐 명령을 가리키는 줄이 남았다. 사람이 보는 것은 가이드이므로
그 줄 하나가 사람을 없는 자리로 보낸다. 셋을 기계가 본다:

  ① 가이드의 명령 줄(`python run.py …` · `python -m cli.…`)이 **실제 CLI에 있다** —
     명령은 `run.py`의 명령 표(키) · 모듈은 `cli/` 파일 · 하위 명령은 그 모듈 소스의 문자열 키
  ② 가이드·구조도 사이 **링크와 파일 이름이 실재한다** — `[…](경로)`와 `` `…md` ``
  ③ `2B_작업가이드.md`의 **시작하기·증상표 절에 회차·결정 번호 0**(`B\\d\\d` · `D-\\d+`) ·
     2B 전체에 **옛 판 서술 0**(구판 · 옛 판 · 이전에는) — 가이드는 지금 동작만 말한다
     (무엇이 언제 바뀌었나는 개정대장 몫)

사용: python docs/회귀스위트/점검_가이드.py     (위반이 있으면 exit 1)
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GUIDES = ROOT / "docs" / "가이드"
STRUCT = ROOT / "docs" / "구조도"
GUIDE_2B = GUIDES / "2B_작업가이드.md"
#: 회차·결정 번호를 두지 않는 절 — 제목의 앞머리로 찾는다
CLEAN_SECTIONS = ("## 시작하기", "## §7 증상표")
OLD_VERSION = re.compile(r"구판|옛 판|이전에는")
ROUND_NO = re.compile(r"\bB\d\d\b|\bD-\d+\b")

_RUN = re.compile(r"python3?\s+run\.py\s+([a-z][a-z0-9-]*)(?:\s+([^\s`|]+))?")
_CLI = re.compile(r"python3?\s+-m\s+cli\.([a-z_][a-z0-9_]*)(?:\s+([^\s`|]+))?")
#: `run.py <명령>`이 위임하는 모듈 — 하위 명령은 그 소스의 문자열로 찾는다
DELEGATE = {"platform": ["cli/platform.py"], "show": ["cli/show.py"], "ops": ["cli/ops.py"],
            "parse": ["cli/parse.py"], "golden": ["cli/golden.py"],
            "export": ["cli/export.py"], "register": ["cli/register"]}
_WORD = re.compile(r"^[a-z][a-z0-9_-]*$")


def run_commands():
    """`run.py` 명령 표의 키 — 문자열 키만 가진 dict 리터럴 중 가장 큰 것(`tests/exits_scan`과 같은 규칙)."""
    best = set()
    for node in ast.walk(ast.parse((ROOT / "run.py").read_text(encoding="utf-8"))):
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys):
            keys = {k.value for k in node.keys}
            if len(keys) > len(best):
                best = keys
    return best


def _src(rels):
    out = []
    for rel in rels:
        p = ROOT / rel
        files = sorted(p.rglob("*.py")) if p.is_dir() else [p]
        out += [f.read_text(encoding="utf-8") for f in files if f.exists()]
    return "\n".join(out)


def _has_word(src, word):
    return f'"{word}"' in src or f"'{word}'" in src


def check_commands(files):
    """① 명령 줄 — `[(파일, 줄, 문면, 사유)]`."""
    known = run_commands()
    hits = []
    for f in files:
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for cmd, sub in _RUN.findall(ln):
                if cmd not in known:
                    hits.append((f, i, f"run.py {cmd}", "run.py 명령 표에 없다"))
                elif sub and _WORD.match(sub) and cmd in DELEGATE \
                        and not _has_word(_src(DELEGATE[cmd]), sub):
                    hits.append((f, i, f"run.py {cmd} {sub}", f"{DELEGATE[cmd][0]}에 하위 명령이 없다"))
            for mod, sub in _CLI.findall(ln):
                cand = [ROOT / "cli" / f"{mod}.py", ROOT / "cli" / mod / "__main__.py"]
                path = next((c for c in cand if c.exists()), None)
                if path is None:
                    hits.append((f, i, f"-m cli.{mod}", "cli 모듈이 없다"))
                    continue
                if sub and _WORD.match(sub) and not sub.endswith((".py", ".md")):
                    src = _src([f"cli/{mod}"] if path.name == "__main__.py" else [f"cli/{mod}.py"])
                    if not _has_word(src, sub):
                        hits.append((f, i, f"-m cli.{mod} {sub}", "그 모듈에 하위 명령이 없다"))
    return hits


_LINK = re.compile(r"\]\(([^)\s]+)\)")
_MDNAME = re.compile(r"`([^`\s]+\.md)`")


#: **상태 산출물**의 이름 — 레포 파일이 아니라 실행이 `$ONTO_HOME` 아래에 만든다.
STATE_MD = {"prompt_rendered.md"}          # registry/review/<dt>/ — 생성 프롬프트의 렌더 사본


def _repo_files():
    return [p for p in ROOT.rglob("*.md")
            if ".git" not in p.parts and not p.relative_to(ROOT).parts[0].startswith("state")]


def _exists_md(name, here, files):
    if any(c in name for c in "<{*…") or name in STATE_MD:
        return True                                   # 자리표시자 · 상태 산출물
    for base in (here, ROOT, ROOT / "docs"):
        if (base / name).exists():
            return True
    # 이름만이거나 부분 경로면 — 레포 어딘가에 그 끝을 가진 파일이 있는가
    return any(p.as_posix().endswith("/" + name.lstrip("./")) for p in files)


def check_links(files):
    """② 링크·파일 이름 — `[(파일, 줄, 문면, 사유)]`."""
    hits, repo = [], _repo_files()
    for f in files:
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for tgt in _LINK.findall(ln):
                if tgt.startswith(("http", "mailto:", "#")):
                    continue
                path = tgt.split("#", 1)[0]
                if path and not (f.parent / path).exists():
                    hits.append((f, i, tgt, "링크 대상이 없다"))
            for name in _MDNAME.findall(ln):
                if not _exists_md(name, f.parent, repo):
                    hits.append((f, i, name, "파일 이름이 실재하지 않는다"))
    return hits


def _sections(text, heads):
    """제목(앞머리)으로 시작하는 절의 `(시작 줄, 본문 줄들)` — 다음 `## `까지."""
    out, cur = [], None
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.startswith("## "):
            cur = (i, []) if ln.startswith(heads) else None
            if cur:
                out.append(cur)
            continue
        if cur:
            cur[1].append((i, ln))
    return out


def check_2b():
    """③ 2B — 시작하기·증상표에 회차·결정 번호 0 · 전체에 옛 판 서술 0."""
    text = GUIDE_2B.read_text(encoding="utf-8")
    hits = []
    for _start, body in _sections(text, CLEAN_SECTIONS):
        for i, ln in body:
            for m in ROUND_NO.findall(ln):
                hits.append((GUIDE_2B, i, m, "시작하기·증상표에 회차·결정 번호"))
    for i, ln in enumerate(text.splitlines(), 1):
        for m in OLD_VERSION.findall(ln):
            hits.append((GUIDE_2B, i, m, "옛 판 서술"))
    found = [h for h in CLEAN_SECTIONS if any(l.startswith(h) for l in text.splitlines())]
    for h in set(CLEAN_SECTIONS) - set(found):
        hits.append((GUIDE_2B, 0, h, "절이 없다"))
    return hits


def main():
    guides = sorted(GUIDES.glob("*.md"))
    structs = sorted(STRUCT.glob("*.md"))
    hits = check_commands(guides) + check_links(guides + structs) + check_2b()
    print(f"가이드 점검 — 가이드 {len(guides)}개 · 구조도 {len(structs)}개")
    for f, i, what, why in hits:
        print(f"  {f.relative_to(ROOT).as_posix()}:{i}  {what}  — {why}")
    print(f"\n총 {len(hits)}건" + (" — 통과" if not hits else " — 고친다"))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
