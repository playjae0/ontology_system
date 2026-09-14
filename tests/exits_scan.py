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
NEXT_LINE = ("python run.py", "python -m cli.")
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
    """사람이 치는 자리 — `cli/*.py`와 `run.py`."""
    return sorted((ROOT / "cli").glob("*.py")) + [ROOT / "run.py"]


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
          f" · 계약 위반 {len(broken(rows))}")


if __name__ == "__main__":
    main()
