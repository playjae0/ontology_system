# -*- coding: utf-8 -*-
"""칸 0.3 — **레포 쓰기 정적 점검** — 시험 소스에서 레포 경로로 쓰는 호출 0 (B133 ①).

    python tools/repo_writes.py                 레포 — 위반 0이면 rc 0 · 있으면 자리마다 한 줄 · rc 1
    python tools/repo_writes.py --root <폴더>    그 사본을 잰다(시험)

**레포는 시험이 읽기만 하는 자리다**(B133 원칙) — 쓰는 곳은 그 스위트의 임시 자리(회귀가 스위트마다 주는 픽스처 뿌리 사본 ·
작업 폴더 · mock 루트 — 자리는 `core/state/fixtures.py` · `core/paths.py`가 답한다). 병렬 회귀에서 한 스위트가 레포에 쓰고 지우는
사이 다른 스위트가 그 자리를 읽으면 흔들린다(B131 뒤 실측). 쓰고 지우는 시험은 사후 대조(회귀 앞뒤 작업 트리)가 못 잡아 여기서 잰다.

  재는 곳 = `tests/`의 `.py`(픽스처를 만드는 `tests/fixtures/` 아래는 뺀다)
  레포 경로 = `ROOT` · `__file__`에서 나온 식과 그 식을 받은 이름(같은 파일 안 · 대입을 따라간다)
  쓰기 = `write_text` · `write_bytes` · `mkdir` · `unlink` · `touch` · `rename` · `replace` · `rmdir` · `save` · 쓰기 모드 `open` ·
         `shutil` 복사 · 이동 · 지우기의 대상 · `os` 지우기 · 만들기 · 이름 바꾸기

등재 예외는 그 줄 끝 주석 `# 레포 쓰기 예외: <까닭>` — 화면이 예외 수와 자리를 따로 말한다.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = "tests"
SKIP = ("tests/fixtures/",)
MARK = "# 레포 쓰기 예외:"
_PATH_WRITES = {"write_text", "write_bytes", "mkdir", "unlink", "touch", "rename", "replace", "rmdir",
                "symlink_to", "hardlink_to", "save"}
_SHUTIL_DST = {"copy", "copy2", "copyfile", "copytree", "move"}
_SHUTIL_ONE = {"rmtree"}
_OS_ONE = {"remove", "unlink", "rmdir", "makedirs", "mkdir", "rename", "replace", "removedirs"}


_PATH_METHODS = {"resolve", "absolute", "with_suffix", "with_name", "with_stem", "joinpath", "expanduser"}


def _is_path(node, names):
    """레포 경로 식인가 — 이름 · `__file__` · `/` 결합 · `.parent(s)` · `Path(…)` · `str(…)` · `os.path.join` · 경로 메서드만
    (`read_text()` 같은 값은 경로가 아니다)."""
    if isinstance(node, ast.Name):
        return node.id in names or node.id == "__file__"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_path(node.left, names)
    if isinstance(node, ast.Attribute) and node.attr in ("parent", "parents"):
        return _is_path(node.value, names)
    if isinstance(node, ast.Subscript):
        return _is_path(node.value, names)
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) and _is_path(v.value, names) for v in node.values)
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ("Path", "str") or isinstance(f, ast.Attribute) and f.attr in ("Path", "fspath"):
            return any(_is_path(a, names) for a in node.args)
        if isinstance(f, ast.Attribute) and f.attr == "join" and isinstance(f.value, ast.Attribute) and f.value.attr == "path":
            return bool(node.args) and _is_path(node.args[0], names)
        if isinstance(f, ast.Attribute) and f.attr in _PATH_METHODS:
            return _is_path(f.value, names)
    return False


def _tainted_names(tree):
    """레포 경로를 담은 이름 — `ROOT` · `__file__`에서 시작해 경로 식의 대입을 따라 퍼진다(고정점)."""
    names = {"ROOT"}
    assigns = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    while True:
        grew = False
        for a in assigns:
            if a.value is None or not _is_path(a.value, names):
                continue
            for t in (a.targets if isinstance(a, ast.Assign) else [a.target]):
                if isinstance(t, ast.Name) and t.id not in names:
                    names.add(t.id)
                    grew = True
        if not grew:
            return names


def _mode_writes(call, pos):
    mode = call.args[pos] if len(call.args) > pos else next((k.value for k in call.keywords if k.arg == "mode"), None)
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wax+")


def writes(src, rel="?"):
    """`[(줄, 무엇, 예외 까닭 또는 None)]` — 그 소스의 레포 쓰기."""
    tree = ast.parse(src)
    names = _tainted_names(tree)
    lines = src.splitlines()
    out = []
    for c in ast.walk(tree):
        if not isinstance(c, ast.Call):
            continue
        f, what = c.func, None
        if isinstance(f, ast.Attribute):
            base = f.value
            mod = base.id if isinstance(base, ast.Name) else None
            if f.attr == "save":
                what = "save" if c.args and _is_path(c.args[0], names) else None
            elif f.attr in ("replace", "rename"):
                what = f.attr if len(c.args) == 1 and _is_path(base, names) else None    # str.replace는 인자 둘
            elif f.attr in _PATH_WRITES and _is_path(base, names):
                what = f.attr
            elif f.attr == "open" and _is_path(base, names) and _mode_writes(c, 0):
                what = "open(쓰기)"
            elif mod == "shutil" and f.attr in _SHUTIL_DST and len(c.args) > 1 and _is_path(c.args[1], names):
                what = f"shutil.{f.attr}"
            elif mod == "shutil" and f.attr in _SHUTIL_ONE and c.args and _is_path(c.args[0], names):
                what = f"shutil.{f.attr}"
            elif mod == "os" and f.attr in _OS_ONE and c.args and _is_path(c.args[0], names):
                what = f"os.{f.attr}"
        elif isinstance(f, ast.Name) and f.id == "open" and c.args and _is_path(c.args[0], names) and _mode_writes(c, 1):
            what = "open(쓰기)"
        if what:
            ln = lines[c.lineno - 1] if c.lineno <= len(lines) else ""
            why = ln.split(MARK, 1)[1].strip() if MARK in ln else None
            out.append((c.lineno, what, why))
    return sorted(out)


def scan(root=ROOT):
    """`(위반 [(경로, 줄, 무엇)], 예외 [(경로, 줄, 무엇, 까닭)], 잰 파일 수)`."""
    bad, allowed, n = [], [], 0
    for p in sorted((root / SCAN).rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        if rel.startswith(SKIP):
            continue
        n += 1
        try:
            got = writes(p.read_text(encoding="utf-8"), rel)
        except SyntaxError as e:
            bad.append((rel, e.lineno or 0, f"구문 오류 — 잴 수 없다({e.msg})"))
            continue
        for ln, what, why in got:
            (allowed.append((rel, ln, what, why)) if why else bad.append((rel, ln, what)))
    return bad, allowed, n


def main(argv):
    root = Path(argv[argv.index("--root") + 1]).resolve() if "--root" in argv else ROOT
    bad, allowed, n = scan(root)
    for rel, ln, what in bad:
        print(f"  [위반] {rel}:{ln} — {what} (레포 경로로 쓴다 — 그 스위트의 임시 자리로)")
    for rel, ln, what, why in allowed:
        print(f"  [예외] {rel}:{ln} — {what} · {why}")
    print(f"레포 쓰기 정적 점검 — 시험 파일 {n} · 위반 {len(bad)}건 · 등재 예외 {len(allowed)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
