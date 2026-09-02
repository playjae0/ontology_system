#!/usr/bin/env python3
"""문서 간 정합 — 두 문서 이상이 같은 대상을 말하는 자리를 찾아낸다.

왜 있나: 250건 반영이 신규 모순 4건을 만들었고 넷 다 문서 간이었다(mirrors edges 선언
문서2 vs 문서4, 링킹 3단 순서 문서5 vs 문서7, 질의 LLM 지점 수 1 vs 2, seed-only vs 하위
part_of). 원인은 소유 문서 한 곳만 보고 반영한 것이다. README 위계는 "같은 사실은 한 문서에만
살고 나머지는 참조한다"인데, 그 위반을 잡는 검사가 없었다.

세 가지를 본다:
  ① 수치 불일치 — 같은 대상에 다른 수를 말한다 (기계 판정)
  ② 조항 참조 무결 — 본문이 가리킨 조항이 문서 1에 실재하나 (기계 판정)
  ③ 소유 중복 — 두 문서 이상이 같은 대상에 규칙을 말한다 (대조 대상 목록 — 사람이 본다)
"""
import re, glob, os, sys, json, collections
SPEC = os.environ.get("REFINED_DIR", "docs/spec")
DOCS = {os.path.basename(f).replace(".md", ""): open(f, encoding="utf-8").read()
        for f in sorted(glob.glob(f"{SPEC}/[0-9]_*.md") + glob.glob(f"{SPEC}/부록_*.md") + glob.glob(f"{SPEC}/README.md")) if "개정대장" not in f}
# 문서 1(검사기)은 이름이 아니라 **조항 표를 가진 문서**로 식별한다 — 파일명이 바뀌어도 깨지지 않는다
CLAUSE_DOC, CLAUSES = None, set()
for _d, _t in DOCS.items():
    _c = set(re.findall(r'^\| ([A-P][0-9]+) \|', _t, re.M))
    if len(_c) > len(CLAUSES): CLAUSE_DOC, CLAUSES = _d, _c
# P1~P7은 문서 1의 조항이 아니라 문서 0의 불변 원칙이다 — 유효한 참조다
PRINCIPLES = {m for _t in DOCS.values() for m in re.findall(r'\*\*(P[1-9])\b', _t)} or set(f"P{i}" for i in range(1, 8))
CLAUSES |= PRINCIPLES
findings = collections.defaultdict(list)

def secs(txt, i):
    h = re.findall(r'^#+ .*$', txt[:i], re.M)
    return h[-1].strip("# ").strip()[:46] if h else "(머리)"

# ── ① 수치 불일치 — "<대상> N종/N개/N단/N홉" 을 문서별로 모아 대조
UNIT = r'(종|개|단|홉|벌|곳|가지|지점|칸)'
MODIFIER = {"닫힌","각","총","전","이","그","저","같은","다른","위","아래","다음","최대","최소","약"}
NUM = {"하나":1,"둘":2,"셋":3,"넷":4,"다섯":5,"여섯":6,"일곱":7,"여덟":8,"아홉":9,"열":10,
       "1":1,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"12":12,"15":15,"20":20}
counts = collections.defaultdict(set)   # (대상어, 단위) -> {(수, 문서, 절)}
for doc, txt in DOCS.items():
    for m in re.finditer(r'([가-힣A-Za-z_`]{2,18})\s*(?:는|은|이|가|를|을)?\s*(?:총\s*)?([0-9]{1,2}|하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)\s*' + UNIT, txt):
        subj = m.group(1).strip("`").rstrip("는은이가를을")
        if len(subj) < 2 or subj.isdigit(): continue
        if subj in MODIFIER or subj.endswith(("한", "된", "는", "던", "인")): continue   # 수식어는 대상이 아니다
        n = NUM.get(m.group(2))
        if n is None: continue
        ctx = txt[max(0, m.start()-70):m.end()+70]
        if re.search(r'(추가|신규|늘리|더한다|\+\s*1|단계|번째|이내|이상|이하|까지)', ctx): continue  # 증분·서수는 닫힘 주장이 아니다
        if not re.search(r'(뿐|전부|닫힌|닫는다|이다|전량|모두|다음)', ctx): continue                      # 닫힘 표지가 있어야 대조 대상
        counts[(subj, m.group(3))].add((n, doc, secs(txt, m.start())))
for (subj, unit), obs in sorted(counts.items()):
    nums = {n for n, _, _ in obs}
    docs = {d for _, d, _ in obs}
    if len(nums) > 1 and len(docs) > 1:
        findings["① 수치 불일치"].append(
            f"`{subj}` {unit}  →  " + " ‖ ".join(f"{n}{unit} [{d} {s}]" for n, d, s in sorted(obs)))

# ── ② 조항 참조 무결
# **개정 번호는 조항 번호가 아니다** — 둘이 같은 문자 공간(B##)을 쓴다. 문서 1의
# 조항 `B12`와 개정 대장의 개정 `B46`은 다른 장부의 번호이므로, 대장이 발번한 것은
# 조항 미존재로 잡지 않는다. 이 구분이 없으면 개정을 인용할 때마다 거짓 검출이 난다.
_lg = os.path.join(SPEC, "개정대장.md")
LEDGER = open(_lg, encoding="utf-8").read() if os.path.isfile(_lg) else ""
REVISIONS = set(re.findall(r'\[(?:개정|복원|정정)\]\s*([A-P][0-9]{1,2})', LEDGER))

for doc, txt in DOCS.items():
    if doc == CLAUSE_DOC: continue
    for m in re.finditer(r'(?<![A-Za-z0-9])([A-P][0-9]{1,2})(?![0-9A-Za-z])', txt):
        c = m.group(1)
        if c not in CLAUSES and c not in REVISIONS and re.search(r'(조항|불변|금지|참조|지키|위반)', txt[max(0,m.start()-60):m.start()+60]):
            findings["② 조항 참조 무결"].append(f"`{c}`  ← {doc} {secs(txt, m.start())} — 문서 1에 없는 조항 번호")

# (소유 중복은 검사가 아니라 반영 도구가 답한다 — 조회_대상.py 참조.
#  "몇 문서에 나오나"는 신호가 아니다: anchor가 6문서에 나오는 것은 정상이다.)

# ── 출력
print(f"문서 간 정합 — 문서 {len(DOCS)}종 · 검사기={CLAUSE_DOC} · 조항·원칙 {len(CLAUSES)}건 · 수치 주장 {len(counts)}개")
tot = 0
for k in sorted(findings):
    print(f"\n[{k}]  {len(findings[k])}건")
    for f in findings[k][:40]: print(f"  {f}")
    if len(findings[k]) > 40: print(f"  … 외 {len(findings[k])-40}건")
    tot += len(findings[k])
print(f"\n총 {tot}건" + ("" if tot else " — 통과"))
json.dump({k: v for k, v in findings.items()}, open("문서간_결과.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
