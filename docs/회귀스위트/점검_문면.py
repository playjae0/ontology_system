#!/usr/bin/env python3
"""정제본 문면 기계 점검 — 회귀 스위트 시험 3.
사람 판단이 개입하지 않는 규칙만 본다. 위반 0이 통과 조건.
"""
import re, sys, glob, os, json, collections

BASE = os.environ.get("REFINED_DIR", "docs/spec")
# 레포 반입 시 파일명이 접두 '정제본' 없는 형태로 바뀌었다(docs/spec/) — 목록을 실물에 맞춘다.
DOCS = ["README.md", "0_기반과원칙.md", "1_금지와불변.md",
        "2_계약.md", "3_구조.md", "4_쓰기절차.md", "5_읽기절차.md",
        "6_파서와구축모드.md", "7_구현규격과검증.md", "부록_용어.md"]
BODY = [d for d in DOCS[1:9] if "금지와불변" not in d]  # 문서 0·2~7 — 문서 1은 검사기 자신이라 역참조 대상 아님
V = []
def bad(rule, doc, detail): V.append({"rule":rule,"doc":doc,"detail":detail})

texts = {}
for d in DOCS:
    p = os.path.join(BASE, d)
    if not os.path.exists(p):
        bad("파일누락", d, "정제본 10종 중 하나가 없다"); continue
    texts[d] = open(p, encoding="utf-8").read()

# 1. 역참조 블록 — 문서 0~7 전부 보유
for d in BODY:
    if d in texts and "이 문서가 지키는 불변·금지" not in texts[d]:
        bad("역참조누락", d, "말미 「이 문서가 지키는 불변·금지」 블록이 없다")

# 2. 금지 문면 통일 — 금지형 어미가 '않는다' 밖으로 새지 않는가
LEAK = [r"(?<!지 )말아야 한다", r"금지된다", r"해서는 안 된다", r"하면 안 된다"]
for d, t in texts.items():
    for pat in LEAK:
        for m in re.finditer(pat, t):
            ln = t[:m.start()].count("\n") + 1
            bad("부정형이탈", d, f"{ln}행: '{m.group(0)}' — 금지는 'X하지 않는다'로 통일")

# 3. 마크다운 표 깨짐
for d, t in texts.items():
    for i, l in enumerate(t.split("\n"), 1):
        s = l.strip()
        if s.startswith("|") and s.count("|") < 3:
            bad("표깨짐", d, f"{i}행: {s[:60]}")

# 4. 코드펜스 짝
for d, t in texts.items():
    if t.count("```") % 2:
        bad("코드펜스", d, "``` 개수가 홀수")

# 5. 절 번호 중복 (같은 문서 안에서 같은 번호의 ## 헤딩)
for d, t in texts.items():
    nums = re.findall(r"^##+\s+(\d+\.\d+(?:-[A-Z])?)\s", t, re.M)
    for n, c in collections.Counter(nums).items():
        if c > 1: bad("절번호중복", d, f"§{n} 이 {c}회")

# 6. 국면·일정 서술 금지 (README 개정 규칙)
for d, t in texts.items():
    for m in re.finditer(r"(예상\s*:\s*\d+\s*일|약\s+\d+\s*주\b(?!석)|\d+~\d+일\b)", t):
        ln = t[:m.start()].count("\n") + 1
        bad("일정서술", d, f"{ln}행: '{m.group(0)}' — 일정은 운영 기록의 몫")

# 7. 깨진 문서 상호참조 (문서 8 이상을 가리킴)
for d, t in texts.items():
    for m in re.finditer(r"문서\s*([89]|1[0-9])\b", t):
        ln = t[:m.start()].count("\n") + 1
        bad("참조깨짐", d, f"{ln}행: '{m.group(0)}' — 본문 문서는 0~7과 부록뿐")

# 8. 원천 체계 안에서 말하는 서술 — 좌표 표기(원천 칸의 "(구)명세"·"21회차 등재")는 허용,
#    본문이 자신을 카드/챕터라 부르거나 챕터에 지시하는 것은 잔재다
LEGACY = [r"챕터를 (쓸|고칠|검토)", r"챕터에서는", r"이 카드(의|를|에)", r"카드에 (추가|없는)",
          r"v\d+ 기준", r"반영\(v[\d.]+\)만 대기", r"명세 반영만 대기"]
for d, t in texts.items():
    for pat in LEGACY:
        for m in re.finditer(pat, t):
            ln = t[:m.start()].count("\n") + 1
            bad("원천어휘잔재", d, f"{ln}행: '{m.group(0)}' — 정제본은 원천 체계 안에서 말하지 않는다")

# 9. 부정형 총계 (감사 가능성 지표 — 정보 출력)
total_neg = sum(t.count("않는다") for t in texts.values())

print("=" * 62)
print("정제본 문면 기계 점검")
print("=" * 62)
if V:
    by = collections.defaultdict(list)
    for v in V: by[v["rule"]].append(v)
    for r, items in sorted(by.items()):
        print(f"\n[{r}] {len(items)}건")
        for it in items[:12]:
            print(f"  · {it['doc']}: {it['detail']}")
        if len(items) > 12: print(f"  … 외 {len(items)-12}건")
else:
    print("\n위반 0 — 통과")
print(f"\n문서 {len(texts)}종 · 부정형 문면 {total_neg}개 · 위반 {len(V)}건")
sys.exit(1 if V else 0)
