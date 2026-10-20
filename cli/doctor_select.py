# -*- coding: utf-8 -*-
"""칸 0.3 — **doctor 고르기** — `--only` · `--changed` (B117 ① · 개발 중 용도 — **판정이 아니다**).

마감 doctor는 지금처럼 전체 · 클린 단독 · 직렬이다(문서 7 §7.5-7). 여기는 개발 중에 「이 변경이 닿는 스위트만」 먼저 돌리는
문이다 — 화면 머리와 명령 로그에 「고른 실행 — 판정 아님」이 선다.

  · `--only <이름…>` — 스위트 이름 또는 접두(`test_` 생략 가능) · 모르는 이름은 거부(스위트 목록 줄)
  · `--changed [<기준 커밋>]` — git이 말하는 바뀐 파일(기준 대비 작업 트리 + 추적 밖 새 파일) → **그 파일을 읽는 스위트**

**연결 방법 = 정적 그래프(넓게 잡는다 · 빠뜨림 0이 먼저 — 실행 오라클로 대조했다)**: 스위트 파일에서 시작해 레포 안 모듈을
따라간다.
  ① import — 모듈 머리뿐 아니라 함수 안의 지연 import까지 · 상대 import · 패키지 `__init__` · `tests/` · `kit/` · 회귀 스위트 폴더의
     맨이름 모듈 · 문자열 속 파이썬 코드(`-c "import doctor; …"`)
  ② 하위 실행 — 문자열 속 모듈 이름(`"cli.register"` → 그 패키지의 `__main__`까지) · 공백 없는 `.py` 경로 문자열(`"run_adapter.py"`) ·
     `run.py`는 **명령 단위 마디**(`run.py#<명령>`) — 그 스위트의 시험 쪽 파일이 적은 명령 이름의 마디만(못 찾으면 전부)
  ③ 글로 훑기 — `glob` · `rglob` 줄에 코드 폴더 이름과 `*.py`(또는 `*`)가 있으면 그 폴더 · 받는 쪽이 레포 뿌리(`ROOT.rglob`)면 레포 전부 ·
     레포를 통째로 옮기는 스위트(`git ls-files` · `copytree(ROOT …)`)는 **어느 파일이 바뀌어도** 고른다
  ④ `.py`가 아닌 파일 — 닿은 모듈에 그 파일 이름(또는 레포 기준 경로)과 같은 문자열 상수가 있거나 훑는 줄에 부모 폴더 이름이 있으면 그
     스위트 · 이름을 지어 읽는 자산 폴더(지시문 · 킷 · 층 · 스키마 · 픽스처 · 뷰어 정적 · 회귀 자산)는 **고를 수 없다 → 전체**
git을 못 부르거나 기준이 없으면 전체다. 결과는 「파일마다 무엇을 골랐나」 줄과 함께 돌려준다.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: 회귀 스위트 폴더(레포 자산 — 상태 자리가 아니다)
SUITE_DIR = Path("docs", "회귀스위트").as_posix()
#: 정적 그래프가 아는 코드 자리(레포 기준) · 맨이름으로 import되는 폴더(시험이 sys.path에 넣는다)
CODE_DIRS = ("core", "cli", "parser", "kit", "tools", "tests", SUITE_DIR)
BARE_DIRS = ("tests", "kit", SUITE_DIR)
ROOT_PY = ("run.py", "doctor.py", "router.py")
#: 이름을 지어 읽는 자산 폴더 — 여기 파일이 바뀌면 고를 수 없다(전체 · 픽스처는 `.py`도 경로로 실린다)
UNPICKABLE = ("prompts/", "kit/", "layers/", "schemas/", "tests/fixtures/", "cli/viewer/static/",
              f"{SUITE_DIR}/자산/")
HEAD_LINE = "고른 실행 — 판정 아님"
WHOLE = "*"                         # 훑는 자리 표지 — 레포 전부

_MOD = re.compile(r"^(core|cli|parser|kit|tools)(\.[A-Za-z_]\w*)+$")
_PYLIT = re.compile(r"^[\w./가-힣-]+\.py$")
_CODE_IMPORT = re.compile(r"(?:^|[;\n]\s*)(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))")
_SCAN = {"glob", "rglob", "iglob", "walk", "listdir", "scandir", "iterdir"}
_HEADER = {ast.For: ("target", "iter"), ast.AsyncFor: ("target", "iter"), ast.While: ("test",), ast.If: ("test",),
           ast.With: ("items",), ast.FunctionDef: (), ast.AsyncFunctionDef: (), ast.ClassDef: (), ast.Try: ()}


def _consts(nodes):
    return {c.value for n in nodes for c in ast.walk(n) if isinstance(c, ast.Constant) and isinstance(c.value, str)}


def _walk(tree):
    """나무를 **한 번** 돈다 — `(마디 목록(ast.walk와 같은 차례), {자식: 부모})`."""
    from collections import deque
    out, parent, todo = [], {}, deque([tree])
    while todo:
        n = todo.popleft()
        out.append(n)
        for ch in ast.iter_child_nodes(n):
            parent[ch] = n
            todo.append(ch)
    return out, parent


def _is_root(node):
    return isinstance(node, ast.Name) and node.id.upper().lstrip("_").endswith("ROOT")


class Graph:
    """레포 `.py` 파일의 정적 참조 그래프 — 한 번 짓고 스위트마다 닫힘을 센다."""

    def __init__(self):
        # 레포 코드 파일의 레포 기준 이름 — 훑은 폴더 기준으로 잇는다(상태 경로가 아니다 · 화면 표기는 `paths.show`)
        self.files = sorted({f"{d}/{p.relative_to(ROOT / d).as_posix()}" for d in CODE_DIRS
                             for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts}
                            | {f for f in ROOT_PY if (ROOT / f).exists()})
        self.by_mod, self.by_base = {}, {}
        for f in self.files:
            dotted = f[:-3].replace("/", ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[:-len(".__init__")]
            self.by_mod[dotted] = f
            for b in BARE_DIRS:
                if f.startswith(b + "/") and "/" not in f[len(b) + 1:]:
                    self.by_mod.setdefault(Path(f).stem, f)
            self.by_base.setdefault(Path(f).name, set()).add(f)
        self.info = {}                                   # 파일 → {refs · scans · consts · globc · run · whole}
        self.run_cmds = self._run_py()

    # ---------------------------------------------------------------- 이름 → 파일
    def _resolve(self, name, exact=False, main=False):
        """모듈 이름 → 파일 집합(부모 패키지의 `__init__` 포함) — 못 찾으면 위로(`exact`면 그 이름만)."""
        out, cur = set(), name
        while cur:
            if cur in self.by_mod:
                hit = self.by_mod[cur]
                out.add(hit)
                if main and hit.endswith("/__init__.py"):
                    m = hit[:-len("__init__.py")] + "__main__.py"
                    if m in self.files:
                        out.add(m)
                parts = cur.split(".")
                for k in range(1, len(parts)):
                    pkg = self.by_mod.get(".".join(parts[:k]))
                    if pkg and pkg.endswith("__init__.py"):
                        out.add(pkg)
                break
            if exact:
                break
            cur = cur.rsplit(".", 1)[0] if "." in cur else ""
        return out

    def _imports(self, nodes, pkg=""):
        return self._import_refs((n for root in nodes for n in ast.walk(root)), pkg)

    def _import_refs(self, walked, pkg=""):
        refs = set()
        for n in walked:
            if isinstance(n, ast.Import):
                for a in n.names:
                    refs |= self._resolve(a.name)
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    parts = pkg.split(".") if pkg else []
                    base = ".".join(parts[:max(0, len(parts) - n.level + 1)] + ([base] if base else []))
                refs |= self._resolve(base)
                for a in n.names:
                    refs |= self._resolve(f"{base}.{a.name}" if base else a.name, exact=True)
        return refs

    # ---------------------------------------------------------------- run.py 명령 마디
    def _run_py(self):
        """`{명령: 그 명령이 닿는 참조}` + `"#top"`(모듈 머리 · `_dispatch` 몸)."""
        if "run.py" not in self.files:
            return {}
        tree = ast.parse((ROOT / "run.py").read_text(encoding="utf-8"))
        funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

        def calls_of(node):
            return {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Name) and c.func.id in funcs}

        def fn_refs(name, seen):
            if name in seen:
                return set()
            seen.add(name)
            out = self._imports([funcs[name]])
            for c in calls_of(funcs[name]):
                out |= fn_refs(c, seen)
            return out
        out = {"#top": self._imports([n for n in tree.body if not isinstance(n, ast.FunctionDef)])}
        disp = funcs.get("_dispatch")
        if disp is not None:
            out["#top"] |= self._imports([n for n in disp.body if not isinstance(n, ast.Assign)])
            for d in (n for n in ast.walk(disp) if isinstance(n, ast.Dict)):
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        got = set()
                        for c in calls_of(v):
                            got |= fn_refs(c, set())
                        out[k.value] = got
        return out

    # ---------------------------------------------------------------- 파일 하나
    def _scan_calls(self, tree, rec, walked=None, parent=None):
        """글로 훑는 줄 — 그 줄의 문자열(부모 폴더 대조) · 코드 폴더를 훑으면 그 폴더 · 레포 뿌리면 전부 · 레포 통째 사본.
        `walked` · `parent`는 한 번 훑은 마디 · 부모(`_walk` — B121 ② 같은 결과 · 나무를 한 번만 돈다)."""
        if walked is None:
            walked, parent = _walk(tree)
        named = {}
        for n in tree.body:                               # 모듈 머리의 이름 목록(`ASSETS = ("prompts", "kit", …)`)
            if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Tuple, ast.List, ast.Set)):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        named[t.id] = _consts([n.value])
        for c in walked:
            if not isinstance(c, ast.Call):
                continue
            fn = getattr(c.func, "attr", getattr(c.func, "id", None))
            if fn == "copytree" and c.args and _is_root(c.args[0]):
                rec["whole"] = True
            if fn not in _SCAN:
                continue
            st = c
            while st in parent and not isinstance(st, ast.stmt):
                st = parent[st]
            part = [getattr(st, a) for a in _HEADER.get(type(st), ()) if getattr(st, a, None) is not None] \
                if type(st) in _HEADER else [st]
            up = st                                       # 감싼 반복 · 조건의 머리도(`for d in ("cli", "kit"): (ROOT / d).rglob(…)`)
            while up in parent:
                up = parent[up]
                if type(up) in _HEADER:
                    part += [getattr(up, a) for a in _HEADER[type(up)] if getattr(up, a, None) is not None]
            flat = []
            for x in part:
                flat += x if isinstance(x, list) else [x]
            cs = _consts(flat + [c])
            cs |= set().union(*(named.get(x.id, set()) for n in flat for x in ast.walk(n) if isinstance(x, ast.Name)))
            rec["globc"] |= cs
            pat = {x for x in cs if x.endswith(".py") or x in ("*", "**/*")}
            if isinstance(c.func, ast.Attribute) and _is_root(c.func.value) and pat:
                rec["scans"].add(WHOLE)                   # `ROOT.rglob("*.py")` — 레포 전부
                continue
            dirs = {d for d in CODE_DIRS if d in cs or d.split("/")[-1] in cs}
            if dirs and pat:
                rec["scans"] |= dirs

    def parse(self, f):
        if f in self.info:
            return self.info[f]
        rec = {"refs": set(), "scans": set(), "consts": set(), "globc": set(), "run": False, "whole": False}
        self.info[f] = rec
        try:
            tree = ast.parse((ROOT / f).read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return rec
        pkg = f[:-3].replace("/", ".").rsplit(".", 1)[0] if "/" in f else ""
        walked, parent = _walk(tree)
        refs = self._import_refs(walked, pkg)
        consts = {c.value for c in walked if isinstance(c, ast.Constant) and isinstance(c.value, str)}
        for v in consts:
            if _MOD.match(v):
                refs |= self._resolve(v, main=True)
            if _PYLIT.match(v) and Path(v).name != "run.py":
                refs |= self.by_base.get(Path(v).name, set())
            if "import" in v:                             # 문자열 속 코드(`python -c "import doctor; …"`)
                for m in _CODE_IMPORT.finditer(v):
                    refs |= self._resolve(m.group(1) or m.group(2))
            if v == "ls-files":
                rec["whole"] = True
        rec["run"] = "run.py" in consts or any(_PYLIT.match(v) and v.endswith("/run.py") for v in consts)
        self._scan_calls(tree, rec, walked, parent)
        rec["refs"], rec["consts"] = refs - {f}, consts
        return rec

    # ---------------------------------------------------------------- 스위트 하나
    def _reach(self, start, cmds):
        """`(닿는 파일, run.py를 부르나)` — 명령 마디 `cmds`까지."""
        seen, todo, launch = set(), [start] + [f"run.py#{c}" for c in cmds], False
        while todo:
            f = todo.pop()
            if f in seen:
                continue
            seen.add(f)
            if f.startswith("run.py#"):
                todo.extend(self.run_cmds.get(f[len("run.py#"):], set()) - seen)
                continue
            if f not in self.files or f == "run.py":
                continue
            rec = self.parse(f)
            if rec["run"]:
                launch = True
                todo.append("run.py#top")
            todo.extend(rec["refs"] - seen)
        files = {x for x in seen if "#" not in x and x in self.files}
        return (files | {"run.py"}) if launch else files, launch

    def facts(self, start):
        """스위트의 사실 — `{"files", "scans", "consts", "globc", "whole"}`.

        `run.py`는 명령 마디로 닿는다 — 명령 이름은 그 스위트의 시험 쪽 파일(`tests/`)과 `run.py`를 부르는 파일의 문자열에서 찾고,
        마디가 새 파일을 끌어오면 다시 센다(고정점) · 이름을 못 찾으면 명령 전부."""
        cmds = set()
        names = set(self.run_cmds) - {"#top"}
        while True:
            files, launch = self._reach(start, cmds)
            if not launch:
                break
            side = set().union(*(self.parse(f)["consts"] for f in files if f != "run.py"
                                 and (f.startswith("tests/") or self.parse(f)["run"])))
            want = (side & names) or names
            if want <= cmds:
                break
            cmds |= want
        recs = [self.parse(f) for f in files if f != "run.py"]
        return {"files": files,
                "scans": set().union(*(r["scans"] for r in recs)) if recs else set(),
                "consts": set().union(*(r["consts"] for r in recs)) if recs else set(),
                "globc": set().union(*(r["globc"] for r in recs)) if recs else set(),
                "whole": any(r["whole"] for r in recs)}


def changed_files(base="HEAD"):
    """`(바뀐 파일 목록, 문제 또는 None)` — 기준 대비 작업 트리 + 추적 밖 새 파일(git이 무시하는 것은 뺀다)."""
    try:
        a = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "--name-only", base], cwd=str(ROOT),
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        b = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard"],
                           cwd=str(ROOT), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except OSError as e:
        return [], f"git을 부르지 못했다 — {e}"
    if a.returncode:
        return [], f"기준 '{base}'로 git diff가 안 된다 — {(a.stderr or '').strip()[:120]}"
    return sorted({x for x in (a.stdout + b.stdout).splitlines() if x.strip()}), None


def suite_facts(suites):
    """스위트마다 사실 — 그래프 한 번."""
    g = Graph()
    return {s: g.facts(f"tests/{s}.py") for s in suites}


def _unpickable(f):
    return f.startswith(UNPICKABLE) and (f.startswith("tests/fixtures/") or not f.endswith(".py"))


def readers(f, facts):
    """파일 하나를 읽는 스위트 — `None`이면 고를 수 없다(전체)."""
    if _unpickable(f):
        return None
    name, up = Path(f).name, Path(f).parent.name
    top = next((d for d in sorted(CODE_DIRS, key=len, reverse=True) if f.startswith(d + "/")), None)
    hit = set()
    for s, x in facts.items():
        if x["whole"] or f == f"tests/{s}.py" or f in x["files"]:
            hit.add(s)
        elif f.endswith(".py") and (WHOLE in x["scans"] or top in x["scans"]):
            hit.add(s)
        elif not f.endswith(".py") and (name in x["consts"] or f in x["consts"] or (up and up in x["globc"])):
            hit.add(s)
    return hit


def pick_changed(suites, files, facts=None):
    """`(고른 스위트 또는 None(=전체), 줄 목록)` — 파일마다 무엇을 골랐나 · 고를 수 없는 파일이 있으면 그래프를 짓지 않는다."""
    stop = next((f for f in files if _unpickable(f)), None)
    if stop is not None:
        return None, [f"{stop} — 이름을 지어 읽는 자산 폴더 · 고를 수 없다 → 전체"]
    facts = facts if facts is not None else suite_facts(suites)
    picked, lines = set(), []
    for f in files:
        hit = readers(f, facts)
        if hit is None:
            lines.append(f"{f} — 이름을 지어 읽는 자산 폴더 · 고를 수 없다 → 전체")
            return None, lines
        lines.append(f"{f} — {len(hit)}종" + (f" ({' · '.join(sorted(hit)[:6])}{' …' if len(hit) > 6 else ''})"
                                               if hit else " (읽는 스위트 없음)"))
        picked |= hit
    return [s for s in suites if s in picked], lines


def pick_only(suites, args):
    """`(고른 스위트, 모르는 이름)` — 이름 그대로 · 접두 · `test_` 생략."""
    out, unknown = [], []
    for a in args:
        hit = [s for s in suites if s == a or s.startswith(a) or s == f"test_{a}" or s.startswith(f"test_{a}")]
        if not hit:
            unknown.append(a)
        out += [s for s in hit if s not in out]
    return [s for s in suites if s in out], unknown


def parse_args(argv):
    """`(--only 이름 목록 또는 None, --changed 기준 또는 None)` — 다른 플래그는 건드리지 않는다."""
    only = changed = None
    if "--only" in argv:
        only = []
        for a in argv[argv.index("--only") + 1:]:
            if a.startswith("--"):
                break
            only.append(a)
    if "--changed" in argv:
        i = argv.index("--changed")
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        changed = nxt if nxt and not nxt.startswith("--") else "HEAD"
    return only, changed
