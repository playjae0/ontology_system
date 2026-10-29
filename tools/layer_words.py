# -*- coding: utf-8 -*-
"""칸 0.3 — **층 어휘 정적 점검** — 코드 · 지시문에 층 config의 카테고리 이름 · 층 폴더 이름 0 (B121 ①).

    python tools/layer_words.py                 레포 — 위반 0이면 rc 0 · 있으면 자리마다 한 줄 · rc 1
    python tools/layer_words.py --root <폴더>    그 사본을 잰다(시험)

**호환은 한 자리에서 잰다**(CLAUDE.md §4 · 사용자 2026-10-16): 층마다 · 표/산문마다 기능 시험을 곱하지 않고, 층 어휘가
core · parser · cli · 지시문에 들어가지 않았는가를 여기서 한 번에 잰다(층 둘 · 표 · 산문 네 벌과 함께).

  어휘 = 레포 `layers/common.json`과 `layers/<층>/config.json`의 `categories` 이름 + 층 폴더 이름
  재는 곳 = `core/` · `parser/` · `cli/`의 문자열(주석 · docstring은 뺀다 — 설명은 어휘를 말해도 된다) + `prompts/*.md`의 글
  낱말 경계 = 영숫자 · 밑줄 — `process_ref` 같은 계약 필드 이름은 걸리지 않는다

등재 예외(`ALLOW`)는 자리 · 낱말 · 까닭을 단다 — 화면이 예외 수를 따로 말한다.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = ("core", "parser", "cli")
PROMPTS = "prompts"

#: 등재 예외 — `(레포 상대 경로, 낱말): 까닭`. 지시문은 판(머리말 version)이 사내 추출 재사용의 열쇠라 글을 고치면 판이
#: 바뀌어야 하고, 판이 바뀌면 사내 재추출(LLM 비용)이 난다 — 허브가 그 지시문을 개정할 때 함께 지운다(B121 ①).
ALLOW = {
    ("cli/register/generate.py", "process"): "열 머리 영어 낱말 힌트(anchor) — 층 이름이 아니라 머리글 단어다",
    ("prompts/1.3_interview.md", "Unit"): "선택지 예시 — 지시문 판 iv-2.1 · 개정 때 자리표로",
    ("prompts/1.4_generate.md", "Process"): "킷 유지 규칙의 옛 판 서술 — 지시문 판 1.7 · 개정 때 지운다",
    ("prompts/1.4_generate.md", "Unit"): "킷 유지 규칙의 옛 판 서술 — 지시문 판 1.7 · 개정 때 지운다",
    ("prompts/1.4_generate.md", "Property"): "킷 유지 규칙의 옛 판 서술 — 지시문 판 1.7 · 개정 때 지운다",
}


def vocabulary(root=ROOT):
    """`(낱말 집합, 층 폴더 목록)` — 레포 층 자산에서 읽는다(상태 루트가 아니다)."""
    lay = Path(root) / "layers"
    words = set((json.loads((lay / "common.json").read_text(encoding="utf-8")).get("categories") or {}))
    folders = sorted(p.name for p in lay.iterdir() if (p / "config.json").is_file())
    for f in folders:
        words |= set(json.loads((lay / f / "config.json").read_text(encoding="utf-8")).get("categories") or {})
    return words | set(folders), folders


def _docstrings(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                out.add(id(b.value))
    return out


def scan(root=ROOT):
    """`(위반 [(경로, 행, 낱말, 문맥)], 예외 [(경로, 낱말, 까닭)], 낱말 수)`."""
    root = Path(root)
    words, _f = vocabulary(root)
    pat = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, words), key=len, reverse=True))
                     + r")(?![A-Za-z0-9_])")
    hits = []
    for d in CODE_DIRS:
        for f in sorted((root / d).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"))
            docs = _docstrings(tree)
            for n in ast.walk(tree):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                    hits += [(f.relative_to(root).as_posix(), n.lineno, m.group(1), n.value.strip()[:60])
                             for m in pat.finditer(n.value)]
    for f in sorted((root / PROMPTS).glob("*.md")):
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            hits += [(f.relative_to(root).as_posix(), i, m.group(1), ln.strip()[:60]) for m in pat.finditer(ln)]
    bad = [h for h in hits if (h[0], h[2]) not in ALLOW]
    allowed = sorted({(h[0], h[2], ALLOW[(h[0], h[2])]) for h in hits if (h[0], h[2]) in ALLOW})
    return bad, allowed, len(words)


def main(argv):
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv else ROOT
    bad, allowed, n = scan(root)
    for path, line, word, ctx in bad:
        print(f"  ✗ {path}:{line} — '{word}' — {ctx}")
    print(f"층 어휘 정적 점검 — 낱말 {n} · 위반 {len(bad)}건 · 등재 예외 {len(allowed)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
