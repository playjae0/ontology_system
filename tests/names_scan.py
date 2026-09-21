# -*- coding: utf-8 -*-
"""칸 0.3 — **미정의 이름 0** 정적 검사 (B79 ③ⓑ · 표준 라이브러리 AST).

왜 있나 — 사내 첫 반입 실측(2026-09-21): B78-2 분할 때 `import json`이 `points.py`로
따라가지 않아 `ingest-file`이 파싱 단계에서 죽었다. **회귀 1,362가 초록인 채로**였다 —
좌표 태깅 실호출 갈래는 `USE_MOCK=1`에서 한 번도 실행되지 않기 때문이다. 실행되지
않는 줄은 시험이 못 잡으므로 **읽어서** 잡는다.

`tests/exits_scan.py`와 같은 결이다 — 외부 의존 0(`pyflakes`를 쓰지 않는다 ·
코어 필수 외부 의존 0 규율), 문자열이 아니라 **AST**로 본다.

**흐름을 따지지 않는다**(flow-insensitive): 한 스코프 안 어디서든 묶인 이름은 묶인
것으로 본다. `try/except ImportError`로 갈아 끼우는 import가 흔해서, 순서를 따지면
거짓 검출이 는다 — 여기서 잡으려는 것은 **아무 데서도 묶이지 않은 이름**이다.

주석: 타입 표기(annotation)는 보지 않는다 — `from __future__ import annotations`가
전 모듈에 있어 실행되지 않는 문자열이다.

사용: python tests/names_scan.py        (미정의가 있으면 exit 1)
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DIRS = ("core", "cli", "parser", "kit")
ENTRIES = ("run.py", "doctor.py", "router.py")

#: 모듈이 공짜로 갖는 이름들.
MODULE_GIVENS = {"__file__", "__name__", "__doc__", "__package__", "__spec__",
                 "__loader__", "__builtins__", "__all__", "__debug__", "__path__"}
BUILTINS = set(dir(builtins)) | MODULE_GIVENS


def targets(root=None):
    """훑을 운영 모듈 — 회귀·요청문과 같은 목록이다."""
    base = Path(root or ROOT)
    out = [p for d in DIRS for p in sorted((base / d).rglob("*.py"))
           if "__pycache__" not in p.parts]
    out += [base / e for e in ENTRIES if (base / e).exists()]
    return out


class _Scope:
    """묶인 이름의 한 칸. `kind`는 module·function·class·comprehension."""

    def __init__(self, kind, parent=None):
        self.kind, self.parent, self.names = kind, parent, set()

    def bind(self, name):
        if name:
            self.names.add(name)

    def resolve(self, name):
        """파이썬의 조회 사슬 — **class 스코프는 건너뛴다**(메서드에서 안 보인다)."""
        s, first = self, True
        while s is not None:
            if (first or s.kind != "class") and name in s.names:
                return True
            s, first = s.parent, False
        return name in BUILTINS


class _Walker(ast.NodeVisitor):
    """두 벌로 돈다 — 먼저 그 스코프의 **묶임**을 전부 모으고, 그다음 **참조**를 잰다."""

    def __init__(self, rel):
        self.rel, self.bad = rel, []

    # ── 묶임 수집 (한 스코프의 본문에서, 중첩 스코프 안으로는 들어가지 않는다)
    def _bind_body(self, scope, body):
        for node in body:
            self._bind_stmt(scope, node)

    def _bind_stmt(self, scope, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope.bind(node.name)
            return                                   # 본문은 제 스코프에서 본다
        if isinstance(node, ast.Import):
            for a in node.names:
                scope.bind(a.asname or a.name.split(".")[0])
            return
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                scope.bind(a.asname or a.name)
            return
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for n in node.names:
                scope.bind(n)
            return
        for sub in ast.iter_child_nodes(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scope.bind(sub.name)
                continue
            if isinstance(sub, (ast.Lambda,)):
                continue
            self._bind_expr_targets(scope, sub)
            # `except ImportError:` 안의 import도 **모듈에 묶인다** — `ExceptHandler`는
            # `stmt`가 아니라서 빠뜨리면 `orjson` 폴백의 `import json`이 안 보인다.
            if isinstance(sub, (ast.stmt, ast.ExceptHandler)):
                self._bind_stmt(scope, sub)
        self._bind_expr_targets(scope, node)

    def _bind_expr_targets(self, scope, node):
        """`=` · `for` · `with` · `except` · `:=` · 내포 — 이름이 묶이는 자리 전부."""
        if isinstance(node, ast.Assign):
            for t in node.targets:
                self._bind_target(scope, t)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
            self._bind_target(scope, node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    self._bind_target(scope, item.optional_vars)
        elif isinstance(node, ast.ExceptHandler):
            scope.bind(node.name)
        elif isinstance(node, ast.NamedExpr):
            self._bind_target(scope, node.target)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # 내포 변수는 원래 제 스코프지만 **바깥에 묶인 것으로 본다** —
            # 거짓 검출을 만들지 않는 쪽으로 기운다(찾는 것은 아무 데도 없는 이름이다).
            for gen in node.generators:
                self._bind_target(scope, gen.target)
        for sub in ast.iter_child_nodes(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                ast.Lambda)):
                continue
            self._bind_expr_targets(scope, sub)

    def _bind_target(self, scope, t):
        if isinstance(t, ast.Name):
            scope.bind(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                self._bind_target(scope, e)
        elif isinstance(t, ast.Starred):
            self._bind_target(scope, t.value)
        # Attribute·Subscript는 이름을 묶지 않는다

    # ── 참조 검사
    def check(self, tree):
        mod = _Scope("module")
        self._bind_body(mod, tree.body)
        for node in tree.body:
            self._walk(node, mod)
        return self.bad

    def _walk(self, node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                self._walk(d, scope)
            for d in (node.args.defaults + [x for x in node.args.kw_defaults if x]):
                self._walk(d, scope)
            inner = _Scope("function", scope)
            a = node.args
            for arg in (a.posonlyargs + a.args + a.kwonlyargs
                        + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])):
                inner.bind(arg.arg)
            self._bind_body(inner, node.body)
            for st in node.body:
                self._walk(st, inner)
            return
        if isinstance(node, ast.Lambda):
            inner = _Scope("function", scope)
            a = node.args
            for arg in (a.posonlyargs + a.args + a.kwonlyargs
                        + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])):
                inner.bind(arg.arg)
            self._bind_expr_targets(inner, node.body)
            self._walk(node.body, inner)
            return
        if isinstance(node, ast.ClassDef):
            for d in node.decorator_list + list(node.bases):
                self._walk(d, scope)
            inner = _Scope("class", scope)
            self._bind_body(inner, node.body)
            for st in node.body:
                self._walk(st, inner)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if not scope.resolve(node.id):
                self.bad.append((self.rel, node.lineno, node.id))
            return
        if isinstance(node, (ast.AnnAssign,)):          # 표기는 보지 않는다
            if node.value is not None:
                self._walk(node.value, scope)
            self._walk(node.target, scope)
            return
        for sub in ast.iter_child_nodes(node):
            if isinstance(sub, ast.arg):                # 인자 표기도 보지 않는다
                continue
            self._walk(sub, scope)


def scan(root=None):
    """`[(파일, 줄, 이름)]` — 어느 스코프에서도 묶이지 않은 참조."""
    base = Path(root or ROOT)
    bad = []
    for p in targets(base):
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:                        # 파싱이 안 되는 것도 결함이다
            bad.append((p.relative_to(base).as_posix(), e.lineno or 0, f"<SyntaxError> {e.msg}"))
            continue
        bad += _Walker(p.relative_to(base).as_posix()).check(tree)
    return sorted(set(bad))


def main():
    bad = scan()
    print(f"미정의 이름 — 운영 모듈 {len(targets())}개")
    for f, ln, name in bad:
        print(f"  {f}:{ln}  {name}")
    print(f"총 {len(bad)}건" + (" — 통과" if not bad else " — 실행되면 NameError다"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
