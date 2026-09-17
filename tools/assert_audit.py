# -*- coding: utf-8 -*-
"""어서션 감사 — **잰 대상**으로 분류한다 (B77 ①).

    python tools/assert_audit.py            분류 요약 + 표 (표는 docs/회귀스위트/자산/)
    python tools/assert_audit.py --list 문면  그 분류만 파일·줄·라벨로

회귀 1,300여 개가 무엇을 잠그는지가 **세어진 적이 없다.** 라벨 문자열이 아니라
`show(...)`의 **판정식**을 읽어 넷으로 가른다:

  * **문면:화면** — 화면에 그 문자열이 있는가(B59·B61의 문면 계약을 잠그는 자리가
    여기 섞인다 — 계약이면 성질이다).
  * **문면:수** — 특정 수를 박았다. 자산(seed·표본)이 자라면 붉는다 — 재조준 후보.
  * **픽스처** — 특정 표본 파일의 내용에 기댄다(그 자산을 고치면 붉는다).
  * **중복** — 정규화한 판정식이 다른 파일에도 있다.
  * **성질** — 나머지(경계·동등·불변).

**세는 것이 목적이지 지우는 것이 목적이 아니다** — 처분(재조준·삭제)은 사람이
항목마다 증명과 함께 한다(CLAUDE.md §7 삭제 3조건).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "회귀스위트" / "자산" / "어서션_감사.json"

# 화면 출력을 담는 이름들 — 이 변수를 상대로 문자열을 `in`으로 재면 문면이다.
_SCREEN = re.compile(r"getvalue\(\)|stdout|\bout\b|_out\b|screen|화면|block|print")
# 수를 박은 비교 — `== 10` · `>= 43` 따위(0·1은 경계라 성질로 둔다).
_NUMCMP = re.compile(r"(==|>=|<=|>|<)\s*([2-9]|[1-9]\d+)\b")


def _calls(path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "show" and node.args):
            continue
        label = node.args[0]
        label = label.value if isinstance(label, ast.Constant) else (
            ast.get_source_segment(src, label) or "")
        cond = (ast.get_source_segment(src, node.args[1])
                if len(node.args) > 1 else "") or ""
        yield {"file": str(path.relative_to(ROOT)), "line": node.lineno,
               "label": " ".join(str(label).split())[:90], "cond": cond}


def _norm(cond):
    """판정식의 **원문 정규형** — 공백만 정리한다(중복 판정의 키).

    문자열·수까지 지운 「꼴」로 묶으면 **다른 것을 재는 두 어서션**이 중복으로
    잡힌다(구현 중 실측: `S in (ROOT / S).read_text()` 하나에 네 건이 묶였는데
    넷이 각각 다른 파일의 다른 사실을 쟀다). 중복은 **같은 것을 두 번 재는 것**이다.
    """
    return " ".join(cond.split())


def classify(rows):
    seen = {}
    for r in rows:
        seen.setdefault(_norm(r["cond"]), []).append(r)
    for r in rows:
        cond, kinds = r["cond"], []
        lits = re.findall(r"\"([^\"]{4,})\"|'([^']{4,})'", cond)
        has_in = " in " in cond
        if lits and has_in and _SCREEN.search(cond):
            kinds.append("문면:화면")          # 화면에 그 문자열이 있는가
        if _NUMCMP.search(cond):
            kinds.append("문면:수")            # 특정 수를 박았다(자산이 자라면 붉는다)
        if "fixtures/" in cond or "RAW /" in cond or "fixtures" in cond:
            kinds.append("픽스처")
        if len(seen[_norm(r["cond"])]) > 1 and len(_norm(r["cond"])) > 30:
            kinds.append("중복")
        r["분류"] = "·".join(dict.fromkeys(kinds)) or "성질"
    return rows


def main(argv):
    rows = []
    for p in sorted((ROOT / "tests").glob("*.py")):
        try:
            rows += list(_calls(p))
        except SyntaxError:
            continue
    rows = classify(rows)
    if "--list" in argv:
        want = argv[argv.index("--list") + 1]
        for r in rows:
            if want in r["분류"]:
                print(f"{r['file']}:{r['line']:<5} [{r['분류']}] {r['label']}")
        return 0
    tally = {}
    for r in rows:
        tally[r["분류"]] = tally.get(r["분류"], 0) + 1
    print(f"어서션 {len(rows)}건 — 분류")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {k:<12} {v:>5}")
    by_file = {}
    for r in rows:
        by_file.setdefault(r["file"], {}).setdefault(r["분류"], 0)
        by_file[r["file"]][r["분류"]] += 1
    print("\n파일별")
    for f, t in sorted(by_file.items()):
        print(f"  {f:<28} " + " · ".join(f"{k} {v}" for k, v in sorted(t.items())))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n표 전량 → {OUT.relative_to(ROOT)} ({len(rows)}행)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
