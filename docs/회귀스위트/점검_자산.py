#!/usr/bin/env python3
"""자산 대조 — 명세가 말하는 것과 실물 자산이 가진 것을 대조한다.

왜 있나: 정제본의 여러 조항이 실물보다 좁게 잡혀 있었다(config 키 16 vs 19,
relation_patterns 금지 단위, query_traverse 형식, 노드 레코드 필드). 원인은
승계 감사가 원천 '문면'만 보고 '자산'을 보지 않은 것이다. 자산은 자산으로 봐야 한다.

판정하지 않는다 — 차이만 낸다. 어느 쪽이 맞는지는 사람이 정한다.
"""
import json, glob, re, sys, os
SPEC = os.environ.get("REFINED_DIR", "docs/spec")
REPO = os.environ.get("REPO_DIR", ".")
DOCS = sorted(f for f in glob.glob(f"{SPEC}/[0-9]_*.md") + glob.glob(f"{SPEC}/부록_*.md") + glob.glob(f"{SPEC}/README.md") if "개정대장" not in f)
TEXT = "\n".join(open(f, encoding="utf-8").read() for f in DOCS)

def spec_has(tok):
    """명세 문면에 그 토큰이 있나 — 백틱/따옴표/맨몸 모두"""
    return re.search(r'[`"\'\s(|.]' + re.escape(tok) + r'[`"\'\s),.:|]', TEXT) is not None

def sec_of(tok):
    """그 토큰이 처음 나오는 문서·절"""
    for f in DOCS:
        s = open(f, encoding="utf-8").read()
        i = s.find(tok)
        if i < 0: continue
        head = re.findall(r'^#+ .*$', s[:i], re.M)
        return f"{os.path.basename(f).replace('.md','')} {head[-1][:44] if head else ''}"
    return "—"

findings = []
def note(kind, subject, detail):
    findings.append({"구분": kind, "대상": subject, "실태": detail})

# ── ① 층 config 최상위 키
cfg_keys, per = set(), {}
for f in sorted(glob.glob(f"{REPO}/layers/*/config.json")):
    d = json.load(open(f)); name = f.split("/")[-2]
    ks = {k for k in d if not k.startswith("_")}
    per[name] = ks; cfg_keys |= ks
for k in sorted(cfg_keys):
    if not spec_has(k): note("자산에만", f"config 키 `{k}`", f"층 {'·'.join(n for n,v in per.items() if k in v)}에 실재 · 명세 문면에 없음")
for name, ks in per.items():
    for k in sorted(cfg_keys - ks): note("층별 차이", f"config 키 `{k}`", f"{name} 층에 없음 (다른 층에는 있음)")

# ── ② 매칭 스키마 필드 spec 속성 · role 값 · 최상위 키
props, roles, tops = set(), set(), set()
for f in glob.glob(f"{REPO}/schemas/*.json"):
    d = json.load(open(f))
    tops |= {k for k in d if not k.startswith("_")}
    for spec in (d.get("fields") or {}).values():
        if isinstance(spec, dict):
            props |= {k for k in spec}
            if spec.get("role"): roles.add(spec["role"])
for tag, s in (("필드 spec 속성", props), ("role 값", roles), ("스키마 최상위 키", tops)):
    for k in sorted(s):
        if not spec_has(k): note("자산에만", f"{tag} `{k}`", "스키마 실물에 있음 · 명세 문면에 없음")

# ── ③ 관계 이름 (config.relations) 과 골격 소유 관계
rels = set()
for f in glob.glob(f"{REPO}/layers/*/config.json"):
    d = json.load(open(f))
    r = d.get("relations")
    rels |= set(r if isinstance(r, list) else (r or {}).keys())
    sk = d.get("skeleton") or {}
    if isinstance(sk.get("relations"), dict): rels |= set(sk["relations"].values())
for k in sorted(rels):
    if not spec_has(k): note("자산에만", f"관계 이름 `{k}`", "config에 실재 · 명세 문면에 없음")

# ── ④ 구조 형태 — 실물 형태와 명세 문면을 나란히 놓는다
def depth(v, d=0):
    if isinstance(v, dict): return max((depth(x, d+1) for x in v.values()), default=d)
    if isinstance(v, list): return max((depth(x, d+1) for x in v), default=d)
    return d
SHAPE_KEYS = ("query_traverse", "relation_patterns", "category_pair_map",
              "cross_layer_traverse", "fact_templates", "prompts", "skeleton", "mirrors", "polarity")
def spec_says(tok, n=2):
    """명세가 그 키의 형태를 말하는 문장 — 가장 형태 서술에 가까운 것부터"""
    hits = []
    for f in DOCS:
        for line in open(f, encoding="utf-8"):
            if tok in line and len(line.strip()) > 30:
                if sum(kk in line for kk in SHAPE_KEYS) >= 3: continue   # 키 일람 줄은 형태 서술이 아니다
                sc = sum(w in line for w in ("형태", "구조", "배열", "리스트", "dict", "중첩", "단위", "스펙", "{", "["))
                hits.append((sc, os.path.basename(f).replace("정제본","").replace(".md",""), line.strip()[:170]))
    hits.sort(key=lambda x: -x[0])
    return hits[:n]

for k in SHAPE_KEYS:
    real = {}
    for f in sorted(glob.glob(f"{REPO}/layers/*/config.json")):
        d = json.load(open(f))
        if k in d: real[f.split("/")[-2]] = f"{type(d[k]).__name__} · 깊이 {depth(d[k])} · 최상위 {len(d[k])}"
    if not real: continue
    says = spec_says(k)
    note("형태", f"`{k}`",
         " | ".join(f"{n}: {v}" for n, v in real.items())
         + ("   ▸ 명세: " + " ‖ ".join(f"[{d}] {t}" for _, d, t in says) if says else "   ▸ 명세: 형태 서술 없음"))

# ── ⑤ 명세가 말하는 파일 경로가 실재하나
for m in sorted(set(re.findall(r'`((?:core|cli|parser|layers|schemas|kit|tools)/[\w/{}.*]+\.(?:py|json))`', TEXT))):
    if "{" in m or "*" in m: continue
    if not os.path.exists(os.path.join(REPO, m)): note("명세에만", f"파일 `{m}`", "명세가 이름으로 지목 · 레포에 없음")

# ── 출력
print(f"자산 대조 — config {len(cfg_keys)}키 · 스키마 {len(props)}속성/{len(roles)}role · 관계 {len(rels)}종")
if not findings:
    print("차이 0건"); sys.exit(0)
w = max(len(f["대상"]) for f in findings)
cur = None
for f in sorted(findings, key=lambda x: (x["구분"], x["대상"])):
    if f["구분"] != cur: cur = f["구분"]; print(f"\n[{cur}]")
    loc = f"  ← {sec_of(f['대상'].split('`')[1])}" if f["구분"] == "자산에만" and "`" in f["대상"] else ""
    print(f"  {f['대상']:<{w}}  {f['실태']}{loc}")
print(f"\n총 {len(findings)}건 — 판정 대상")
json.dump(findings, open("자산대조_결과.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
