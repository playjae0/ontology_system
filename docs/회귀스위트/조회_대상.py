#!/usr/bin/env python3
"""대조 조회 — 한 대상을 말하는 모든 줄을 전 문서에서 뽑는다.

왜 있나: 250건 반영이 신규 모순 4건을 만들었고 넷 다 문서 간이었다. 원인은
"소유 문서 한 곳만 보고 반영했고 다른 문서가 같은 사안을 말하는지 안 봤다"이다.
검사로는 못 잡는다 — 두 문장이 서로 다른 말인지는 자연어 판정이다.
그래서 검사가 아니라 절차로 막는다: **반영 전에 이것을 돌려 전부 읽는다.**

사용:  python3 조회_대상.py mirrors
       python3 조회_대상.py "edges 선언" --all      # 규칙 진술 아닌 줄까지
"""
import re, glob, os, sys
SPEC = os.environ.get("REFINED_DIR", "docs/spec")
RULE = re.compile(r'(않는다|해야 한다|만 한다|뿐이다|필수|금지|거부|무효|이다\.|한다\.)')

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    tok = sys.argv[1]
    every = "--all" in sys.argv
    docs = sorted(f for f in glob.glob(f"{SPEC}/[0-9]_*.md") + glob.glob(f"{SPEC}/부록_*.md") + glob.glob(f"{SPEC}/README.md") if "개정대장" not in f)
    total = 0
    for f in docs:
        name = os.path.basename(f).replace(".md", "")
        txt = open(f, encoding="utf-8").read()
        hits = []
        sec = "(머리)"
        for ln, line in enumerate(txt.split("\n"), 1):
            if re.match(r'^#+ ', line): sec = line.strip("# ").strip()[:48]
            if tok not in line: continue
            if not every and not RULE.search(line): continue
            if len(line.strip()) < 25: continue
            hits.append((ln, sec, line.strip()))
        if not hits: continue
        print(f"\n━━ {name}  ({len(hits)}줄)")
        for ln, sec, line in hits:
            print(f"  {ln:>4} §{sec}")
            print(f"       {line[:280]}")
        total += len(hits)
    print(f"\n총 {total}줄 · 문서 {sum(1 for f in docs if tok in open(f,encoding='utf-8').read())}종에서 언급")
    if total == 0: print("  (--all 로 규칙 진술 밖까지 본다)")

main()
