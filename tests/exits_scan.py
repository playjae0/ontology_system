# -*- coding: utf-8 -*-
"""상태 거부 스캐너 — `raise SystemExit(...)` 자리를 훑어 분류와 문면을 낸다 (B61 ①).

**왜 스캐너인가.** 상태 거부 문면의 계약(원인 + 칠 수 있는 다음 줄)은 자리마다
고치면 다음 자리에서 또 난다. 그래서 **코드에서 목록을 만들어** 전건을 재고, 분류가
없는 새 거부를 빨갛게 한다 — 다음 자리를 잡는 장치가 이것이다.

**분류는 자리에 박는다**(D-135 ①과 같은 결 — 라벨과 한 몸). `raise` 줄 끝에
`# [상태]` 또는 `# [사용법]`을 단다:

  * **[상태]** — 사람이 명령을 옳게 쳤는데 시스템 상태(파일·등록부·판정·seed 내용)를
    이유로 진행하지 않는다. **원인 + 그대로 칠 수 있는 다음 줄**을 문면이 담아야 한다.
  * **[사용법]** — 인자 누락·형식 오류·알 수 없는 명령. 사용법이 답이라 대상이 아니다.

문면이 상수나 **문면을 짓는 함수**에 있으면 표시가 그것을 가리킨다 —
`# [상태] 문면=MESSAGE` · `# [상태] 문면=block`.

바깥 표(파일·줄 목록)로 두지 않는 이유: 줄 번호는 편집마다 밀리고, 표와 코드가
갈리는 날 **표가 초록인 채로 거부가 늘어난다.** 표시가 코드에 있으면 편집이 diff에
보인다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 사람이 그대로 칠 수 있는 명령의 꼴 — 둘 중 하나가 문면에 있어야 한다.
# **`doctor.py`도 사람이 그대로 치는 진입점이다**(CLAUDE.md 6 · 화면 여러 곳이
# 그것을 다음 줄로 준다). 목록에 없어서 「반입물이 온전한지 본다」류의 다음 줄이
# `run.py doctor`라는 **없는 명령**으로 적혀 있었다(B68에서 실측 — 치면 KeyError).
NEXT_LINE = ("python run.py", "python -m cli.", "python doctor.py")
MARKS = {"상태", "사용법"}
_MARK_RE = re.compile(r"#.*\[(상태|사용법)\](?:\s*문면=(\w+))?")


def _named(src, name):
    """표시가 가리킨 자리의 문면 — 모듈 상수의 값 또는 함수의 원문.

    없으면 빈 문자열이다: **가리킨 것이 사라지면 계약 위반으로 걸린다.**
    """
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == name for t in node.targets):
            try:
                v = ast.literal_eval(node.value)
            except ValueError:
                return ""
            return v if isinstance(v, str) else ""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(src, node) or ""
    return ""


def targets():
    """사람이 치는 자리 — `cli/`의 전 모듈(패키지 포함)과 `run.py`."""
    return sorted((ROOT / "cli").rglob("*.py")) + [ROOT / "run.py"]


def scan():
    """`[{file, line, mark, text, ok}]` — 파일 순·줄 순.

    `text`는 `raise SystemExit(...)` 문 전체의 원문이다. **화면에 무엇이 나오나**를
    문(statement) 하나로 판정하려면 문면이 그 문 안에 있어야 한다 — 앞선 `print`로
    나눠 두면 스캐너가 못 보고, 사람이 문면을 고칠 때도 두 자리를 봐야 한다.
    """
    out = []
    for f in targets():
        src = f.read_text(encoding="utf-8")
        lines = src.splitlines()
        for node in ast.walk(ast.parse(src)):
            if not (isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and getattr(node.exc.func, "id", "") == "SystemExit"):
                continue
            m = _MARK_RE.search(lines[node.lineno - 1])
            text = ast.get_source_segment(src, node) or ""
            mark = m.group(1) if m else ""
            # **문면이 모듈 상수에 있으면 표시가 그것을 가리킨다** — 종료 코드를
            # 값으로 내는 자리(`SystemExit(2)`)는 문면을 문 안에 담을 수 없다.
            # 가리킨 상수를 함께 읽는다: 「어디에 있나」를 표시가 답하면 스캐너가
            # 찾아가고, 그 자리를 지우면 표시가 가리키는 것이 없어 빨갛다.
            if m and m.group(2):
                text += "\n" + _named(src, m.group(2))
            out.append({"file": str(f.relative_to(ROOT)), "line": node.lineno,
                        "mark": mark, "text": text,
                        "ok": mark != "상태" or any(k in text for k in NEXT_LINE)})
    return out


# 다음 줄에 등장하는 명령의 세 꼴 — 이름이 **실재하는가**만 본다 (B69 ④).
# **이름에 쓰이는 글자만 딴다** — 문면은 원문(소스)이라 뒤에 `\n`·조사·따옴표가
# 붙는다. 그것까지 이름으로 세면 실재하는 명령이 「없는 명령」으로 뜬다.
_CMD_RUN = re.compile(r"python\s+run\.py\s+([A-Za-z0-9][A-Za-z0-9._-]*)")
_CMD_CLI = re.compile(r"python\s+-m\s+cli\.([A-Za-z_][A-Za-z0-9_]*)")
_CMD_FILE = re.compile(r"python\s+([A-Za-z_][A-Za-z0-9_/-]*\.py)")
_PLACEHOLDER = ("<", "{", "…", "[")


def run_commands():
    """`run.py`가 아는 명령 이름 — **명령 표의 키가 정본이다**(문면을 읽지 않는다).

    표는 `{...}[cmd]()` 꼴로 그 자리에서 불린다 — 이름 붙은 dict가 아니다.
    그래서 **문자열 키만 가진 dict 리터럴 중 가장 큰 것**을 명령 표로 본다:
    `run.py`에 그런 표는 하나이고, 둘이 되면 그때 이 함수가 갈라져야 한다.
    """
    src = (ROOT / "run.py").read_text(encoding="utf-8")
    best = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str)
                for k in node.keys):
            keys = {k.value for k in node.keys}
            if len(keys) > len(best):
                best = keys
    return best


def next_commands(text):
    """문면이 제시한 명령 — `[(꼴, 이름)]`. 자리표시자(`<명령>`)는 세지 않는다."""
    out = []
    for kind, rx in (("run", _CMD_RUN), ("cli", _CMD_CLI), ("file", _CMD_FILE)):
        for name in rx.findall(text or ""):
            if not any(c in name for c in _PLACEHOLDER):
                out.append((kind, name))
    return out


def unknown_next(rows=None):
    """**없는 명령을 다음 줄로 주는 자리** (B69 ④).

    B68 회차 실측: `_kit_line_re`의 상태 거부가 `python run.py doctor`를 줬는데
    그런 명령이 없다(치면 `KeyError`). 스캐너가 **접두만** 봐서 초록이었다 —
    「그대로 칠 수 있는 다음 줄」(B61 계약)은 칠 수 있어야 계약이다.

    문면을 세지 않는다 — **이름의 실재**만 본다.
    """
    known = run_commands()
    bad = []
    for r in (rows if rows is not None else scan()):
        for kind, name in next_commands(r["text"]):
            # `python -m cli.x`는 **모듈이거나 패키지**다(B78 2b — `cli/register/`).
            ok = (name in known if kind == "run" else
                  ((ROOT / "cli" / f"{name}.py").exists()
                   or (ROOT / "cli" / name / "__main__.py").exists())
                  if kind == "cli" else (ROOT / name).exists())
            if not ok:
                bad.append({**r, "cmd": f"{kind}:{name}"})
    return bad


# **근거 자리** — 「무엇을 보고 그렇게 판정했나」 (B77 ③ · B61 계약 ④).
# 사내 실측: `--revise`가 「등록돼 있지 않다」만 말해, 사용자가 `review/`·`data/`를
# 복사하고도 시스템이 **어느 파일을 보는지** 몰랐다. 문면을 세지 않는다 —
# **경로 문자열이 하나 이상 있는가**만 본다(성질).
# **잰 자리도 자리다**(B78 3) — 상태 루트가 옮겨 다니므로 근거를 문자열로 박으면
# 화면이 옛 자리를 말한다. `store.path(...)`·`paths.*()`로 **실경로를 끼워 넣는**
# 문면은 근거가 있는 것으로 센다 — 사람이 보는 화면에는 진짜 경로가 뜬다.
_PATH_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*/[A-Za-z0-9_<>{}./-]+"
                      r"|[A-Za-z0-9_]+\.(?:json|md|py|log|html|xlsx|csv)"
                      r"|store\.path\(|paths\.[a-z_]+\(")


def evidence(text):
    """문면이 가리키는 자리들 — 폴더·파일 경로. 없으면 빈 목록이다."""
    return [m.group(0) for m in _PATH_RE.finditer(text or "")]


def no_evidence(rows=None):
    """**근거 자리가 없는 상태 거부** — 사람이 어디를 볼지 모른다."""
    return [r for r in (rows if rows is not None else scan())
            if r["mark"] == "상태" and not evidence(r["text"])]


def unmarked(rows=None):
    """분류가 없는 거부 — **새 거부는 여기 뜬다.**"""
    return [r for r in (rows if rows is not None else scan()) if not r["mark"]]


def broken(rows=None):
    """계약을 어긴 상태 거부 — 다음 줄이 없다."""
    return [r for r in (rows if rows is not None else scan())
            if r["mark"] == "상태" and not r["ok"]]


def main():
    rows = scan()
    for r in rows:
        head = " ".join(r["text"].split())[:96]
        print(f"{r['mark'] or '(미분류)':>6}  {r['file']}:{r['line']}  {head}")
    st = [r for r in rows if r["mark"] == "상태"]
    print(f"\n총 {len(rows)}곳 — 상태 {len(st)} · 사용법 "
          f"{len(rows) - len(st) - len(unmarked(rows))} · 미분류 {len(unmarked(rows))}"
          f" · 계약 위반 {len(broken(rows))} · 없는 명령 {len(unknown_next(rows))}"
          f" · 근거 없음 {len(no_evidence(rows))}")
    for r in no_evidence(rows):
        print(f"   근거 없음 — {r['file']}:{r['line']}  "
              f"{' '.join(r['text'].split())[:70]}")
    for r in unknown_next(rows):
        print(f"   없는 명령 — {r['file']}:{r['line']}  {r['cmd']}")


if __name__ == "__main__":
    main()
