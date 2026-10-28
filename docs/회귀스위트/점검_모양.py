#!/usr/bin/env python3
"""명세 모양 점검 — 늘어나지 않게 (문서 검사 일곱째 · B117 ③).

명세 본문에 회차마다 덧붙인 흔적이 쌓였다(허브 진단 2026-10-16): 취소선 · 한 줄에 1500자가 넘는 문단 · 표 행의 마지막
칸 밖에 붙은 글(렌더링에서 안 보인다) · 본문 `[개정]` 표지(B158 — 새 개정은 패치로 지금 규칙을 고쳐 쓴다 · 표지를 덧붙이지 않는다) ·
목록 항목에 붙어 렌더되는 문단(B159 — 빈 줄 없이 이어지면 앞 항목 안으로 들어간다).
다섯 수를 세어 **기준값보다 늘면 위반**이다. 줄면 기준값을 그 수로 내리고 기록한다
(내려간 기준은 다시 오르지 않는다 — 정제 패스가 줄인 만큼 잠긴다).

  · 대상 — 명세 본문(`REFINED_DIR` 아래 `*.md` · 개정대장 제외 · 보관 파일은 `docs/archive/`라 애초에 밖이다)
  · 취소선 — 한 줄 안의 `~~…~~` 짝 수
  · 긴 줄 — 글자 수 1500 초과인 줄 수
  · 표 칸 밖 — `|`로 시작하는 표 행 중 끝이 `|`가 아닌 행 수(마지막 칸 뒤에 붙은 글)
  · 개정 표지 — 본문의 `[개정]` 수(B158)
  · 붙음 — 목록 항목(`- ` · `* ` · `n. `) 바로 다음 줄이 빈 줄 없이 들여쓰기가 같거나 얕은 일반 문단인 수(코드 울타리 안 · 표 행 ·
    머리줄 · 인용 · 다음 목록 항목은 빼고 — B159 ②)
  · 기준값 — 자산 `docs/회귀스위트/자산/명세_모양.json`

같은 함수(`measure` · `judge`)를 마감 한 줄(`tools/close.py`)과 명세 패치 점검(`tools/spec_patch.py --check`)이 부른다.
실행: `REFINED_DIR=docs/spec python3 docs/회귀스위트/점검_모양.py` (위반이면 종료 코드 1)
"""
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_SPEC = os.path.normpath(os.path.join(HERE, "..", "spec"))
BASE_FILE = os.path.join(HERE, "자산", "명세_모양.json")
LONG = 1500
KEYS = ("취소선", "긴 줄", "칸 밖", "개정 표지", "붙음")
_ITEM = re.compile(r"(?:[-*]|\d+\.)\s")
_STRIKE = re.compile(r"~~[^~\n]+?~~")


def body_files(spec):
    """명세 본문 — 개정대장은 이력이라 뺀다."""
    return [f for f in sorted(glob.glob(os.path.join(spec, "*.md"))) if "개정대장" not in os.path.basename(f)]


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _stuck(lines):
    """붙음의 자리(행 번호) — 목록 항목 바로 다음 줄이 빈 줄 없이 같거나 얕은 들여쓰기의 일반 문단(코드 울타리 안 · 표 · 머리 · 인용 ·
    다음 목록 항목은 뺀다). 마크다운은 그 줄을 앞 항목의 문단으로 이어 렌더한다."""
    out, fence = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or not _ITEM.match(line.lstrip()) or i + 1 >= len(lines):
            continue
        nxt = lines[i + 1]
        s = nxt.strip()
        if not s or s.startswith(("```", "|", "#", ">")) or _ITEM.match(s):
            continue
        if _indent(nxt) <= _indent(line):
            out.append(i + 2)
    return out


def measure(spec):
    """`{취소선 · 긴 줄 · 칸 밖 · 개정 표지 · 붙음: 수, "자리": {키: [파일:행 …]}}`."""
    out = {k: 0 for k in KEYS}
    where = {k: [] for k in KEYS}
    for f in body_files(spec):
        name = os.path.basename(f)
        lines = open(f, encoding="utf-8").read().split("\n")
        for i in _stuck(lines):
            out["붙음"] += 1
            where["붙음"].append(f"{name}:{i}")
        for i, line in enumerate(lines, 1):
            n = len(_STRIKE.findall(line))
            if n:
                out["취소선"] += n
                where["취소선"].append(f"{name}:{i}")
            if len(line) > LONG:
                out["긴 줄"] += 1
                where["긴 줄"].append(f"{name}:{i}")
            s = line.strip()
            if s.startswith("|") and not s.endswith("|"):
                out["칸 밖"] += 1
                where["칸 밖"].append(f"{name}:{i}")
            n = line.count("[개정]")
            if n:
                out["개정 표지"] += n
                where["개정 표지"].append(f"{name}:{i}")
    out["자리"] = where
    return out


def baseline():
    with open(BASE_FILE, encoding="utf-8") as f:
        return json.load(f)


def judge(spec, write=None):
    """`(위반 목록, 측정, 기준, 내린 것)` — 늘면 위반 · 줄면 기준을 내린다(`write` — 기본은 레포 명세를 잴 때만 쓴다)."""
    now, base = measure(spec), baseline()
    bad = [f"{k} {base[k]} → {now[k]} (늘었다 · 자리 {now['자리'][k][:8]})" for k in KEYS if now[k] > base[k]]
    lowered = {k: (base[k], now[k]) for k in KEYS if now[k] < base[k]}
    if write is None:
        write = os.path.normpath(os.path.abspath(spec)) == REPO_SPEC
    if lowered and write and not bad:
        rec = dict(base)
        for k, (_a, b) in lowered.items():
            rec[k] = b
        rec.setdefault("기록", []).append({"at": datetime.date.today().isoformat(),
                                           "내림": {k: f"{a} → {b}" for k, (a, b) in lowered.items()}})
        tmp = BASE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp, BASE_FILE)
    return bad, now, base, lowered


def line(now, base, bad):
    return (f"취소선 {now['취소선']} · 1500자+ 줄 {now['긴 줄']} · 표 칸 밖 {now['칸 밖']} · [개정] 표지 {now['개정 표지']} · "
            f"붙음 {now['붙음']} (기준 {base['취소선']} · {base['긴 줄']} · {base['칸 밖']} · {base['개정 표지']} · {base['붙음']}) · "
            f"위반 {len(bad)}건")


def main():
    spec = os.environ.get("REFINED_DIR", REPO_SPEC)
    bad, now, base, lowered = judge(spec)
    print("=" * 62)
    print("명세 모양 점검 — 취소선 · 긴 줄 · 표 칸 밖 글 · [개정] 표지 · 붙음이 늘지 않는가")
    print("=" * 62)
    for b in bad:
        print(f"  [위반] {b}")
    for k, (a, b) in lowered.items():
        print(f"  [내림] {k} 기준 {a} → {b}")
    print(line(now, base, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
