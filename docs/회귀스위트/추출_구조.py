#!/usr/bin/env python3
"""구조 추출 — 명세에서 부품별 좌표와 지표를 뽑는다.

왜 있나: 정제본은 401KB다. **답이 있어도 못 찾으면 공백과 같은 결과를 낸다**
(2A P-B 미완 4건 중 3건이 그랬다). 그래서 명세 위에 **지도와 카드**를 얹는다.

**손으로 만들지 않는다.** 손으로 만든 요약은 명세와 어긋나고, 그것이 이미 세 번
실측된 실패다(문서 1 미러 · M9 · C13). 좌표와 지표는 **여기서 기계로** 뽑고,
서술은 그 위에 한 번 쓴 뒤 **좌표가 여전히 유효한지를 이 스크립트가 검증한다.**

사람의 판단이 들어가는 곳은 아래 `PARTS` 표 하나뿐이다 — 무엇을 부품으로 볼 것인가.
"""
import re, json, glob, os, sys

SPEC = os.environ.get("REFINED_DIR", "docs/spec")
# **산출은 구조도 자리다**(B51) — 명세 디렉터리는 정본만 둔다(자동 생성물과 섞지 않는다).
OUT = os.environ.get("STRUCT_DIR", "docs/구조도")

# ── 사람의 판단이 들어가는 유일한 자리: 무엇을 부품으로 보는가
#    (문서·절 좌표 · 사람이 개입하는가 · 파이프라인 어느 단계인가)
PARTS = [
    ("파서",          "6", ["6.1","6.2","6.4"],       "인입", "자산"),
    ("구조 지도 패스", "6", ["6.3"],                   "인입", "LLM"),
    ("계약 JSON",     "2", ["2.2","2.3"],             "인입", "기계"),
    ("매칭 스키마",    "2", ["2.4","2.5"],             "인입", "자산"),
    ("핸들러 루프",    "2", ["2.7"],                   "인입", "기계"),
    ("층 config",     "3", ["3.1","3.3"],             "자산", "자산"),
    ("골격 seed",     "3", ["3.9","3.6"],             "자산", "LLM생성·사람확정"),
    ("2-pass 빌더",   "4", ["4.1","4.2"],             "쓰기", "기계"),
    ("판정기",        "4", ["4.3"],                   "쓰기", "LLM"),
    ("커밋 게이트",    "4", ["4.4"],                   "쓰기", "기계"),
    ("이름·값 규칙",   "4", ["4.5","4.6"],             "쓰기", "기계"),
    ("수정 큐",       "4", ["4.7","4.9"],             "운영", "사람"),
    ("재인입",        "4", ["4.8"],                   "쓰기", "기계"),
    ("추출 체크포인트","4", ["4.10"],                  "쓰기", "LLM"),
    ("질의 파이프라인","5", ["5.1","5.2","5.3"],       "읽기", "LLM"),
    ("계기판·골든셋",  "5", ["5.5"],                   "운영", "사람"),
    ("저장 계층",     "7", ["7.1","7.2"],             "저장", "기계"),
    ("게이트웨이",    "7", ["7.6-B"],                  "인입", "LLM"),
    ("구축 모드",     "6", ["6.5","6.6","6.7"],       "등록", "LLM생성·사람확정"),
    ("층 등록",       "3", ["3.7"],                   "등록", "LLM생성·사람확정"),
]

DOCNAME = {"0":"기반과원칙","1":"금지와불변","2":"계약","3":"구조","4":"쓰기절차",
           "5":"읽기절차","6":"파서와구축모드","7":"구현규격과검증"}


def load():
    out = {}
    for f in glob.glob(f"{SPEC}/*.md"):
        b = os.path.basename(f)
        m = re.match(r'(?:정제본)?([0-9])[_.]', b)
        if m and "개정대장" not in b:
            out[m.group(1)] = open(f, encoding="utf-8").read()
    return out


def section(text, num):
    """§num 본문을 잘라낸다 — 다음 같은 급 절머리까지."""
    m = re.search(r'^## ' + re.escape(num) + r'(?![0-9])[^\n]*$', text, re.M)
    if not m: return ""
    nxt = re.search(r'^## [0-9]', text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def metrics(body):
    """절 하나의 기계 지표."""
    return {
        "bytes": len(body.encode("utf-8")),
        "금지": len(re.findall(r'않는다', body)),
        "표": len(re.findall(r'^\|', body, re.M)),
        "조항참조": sorted(set(re.findall(r'(?<![A-Za-z0-9])([A-P][0-9]{1,2})(?![0-9A-Za-z])', body))),
        # 상태 5단(`registry/`·`work/`·`export/`·`golden/`)과 픽스처(`tests/fixtures/`)도 자산이다(B78-3) —
        # `<상태>/` 접두는 벗겨 읽는다.
        "자산": sorted(set(re.findall(r'`(?:<상태>/|\$ONTO_HOME/)?((?:layers|schemas|kit|data|mock|extract|registry|work|export|golden|tests/fixtures)/[\w/{}.*<>]+)`', body))),
        # **파트 폴더도 읽는다**(B78) — `[\w]+`만 보면 `core/llm/gateway.py`를 놓치고
        # 카드의 「실물」 줄이 조용히 비어 간다.
        "코드": sorted(set(re.findall(r'`((?:core|cli|parser|kit)/[\w/]+\.py)`', body))),
    }



# ────────────────────────────────────────────────────────── 한 장 지도
STAGE_ORDER = ["등록", "자산", "인입", "쓰기", "저장", "읽기", "운영"]
STAGE_DESC = {
    "등록": "등록 — 새 문서 종류·새 층을 시스템에 알린다 (구축 모드 · 운영과 분리된 별도 세션)",
    "자산": "자산 — 사람이 확정해 심는 것. 코드가 아니라 데이터다",
    "인입": "인입 — 문서가 계약 JSON이 되기까지",
    "쓰기": "쓰기 — 계약 JSON이 그래프가 되기까지",
    "저장": "저장 — 그래프·청크·사전·큐가 파일로 앉는 자리",
    "읽기": "읽기 — 질문이 근거 있는 답이 되기까지",
    "운영": "운영 — 사람이 자기 리듬으로 처리하는 것",
}
ACTOR_MARK = {"사람": "👤", "LLM": "🤖", "자산": "📄", "기계": "⚙", "LLM생성·사람확정": "🤖→👤"}


def make_map(parts):
    for i, p in enumerate(parts): p["_id"] = f"P{i:02d}"
    by = {}
    for p in parts: by.setdefault(p["단계"], []).append(p)
    L = ["```mermaid", "flowchart TD"]
    # 주 흐름
    L += ['  DOC["📥 실물 문서<br/>(엑셀·PPT·Word)"]']
    for st in ["인입", "쓰기", "저장", "읽기"]:
        L.append(f'  subgraph {st}["{st}"]')
        L.append("    direction TB")
        for p in by.get(st, []):
            nid = p["_id"]
            mark = ACTOR_MARK.get(p["주체"], "")
            L.append(f'    {nid}["{mark} {p["부품"]}<br/><small>§{p["절"][0]}</small>"]')
        L.append("  end")
    L.append('  ANS["💬 근거 있는 답<br/>(그래프 사실 + 청크)"]')
    # 곁가지 — 사람이 만드는 것
    for st in ["등록", "자산", "운영"]:
        L.append(f'  subgraph {st}["{st}"]')
        L.append("    direction TB")
        for p in by.get(st, []):
            nid = p["_id"]
            mark = ACTOR_MARK.get(p["주체"], "")
            L.append(f'    {nid}["{mark} {p["부품"]}<br/><small>§{p["절"][0]}</small>"]')
        L.append("  end")
    # 배선
    ids = {p["부품"]: p["_id"] for p in parts}
    E = [
        # 운영 인입 — 등록이 끝난 뒤 반복되는 주 흐름
        ("DOC", "파서", "운영 인입 (등록 뒤 반복)"),
        ("파서", "구조 지도 패스", ""), ("파서", "계약 JSON", ""),
        ("계약 JSON", "핸들러 루프", ""), ("매칭 스키마", "핸들러 루프", ""),
        ("핸들러 루프", "2-pass 빌더", ""), ("2-pass 빌더", "판정기", ""),
        ("판정기", "커밋 게이트", ""), ("커밋 게이트", "이름·값 규칙", ""),
        ("이름·값 규칙", "저장 계층", ""), ("재인입", "저장 계층", ""),
        ("추출 체크포인트", "2-pass 빌더", ""), ("게이트웨이", "판정기", ""),
        ("저장 계층", "질의 파이프라인", ""),
        ("골격 seed", "판정기", ""), ("층 config", "커밋 게이트", ""),
        ("커밋 게이트", "수정 큐", ""), ("판정기", "수정 큐", ""),
        ("저장 계층", "계기판·골든셋", ""), ("수정 큐", "저장 계층", ""),
        # 등록 — 같은 실물 문서가 먼저 표본으로 한 번 들어간다
        ("DOC", "구축 모드", "표본 (등록 때 먼저 1회)"),
        ("DOC", "층 등록", "표본 3부"),
        ("구축 모드", "파서", "어댑터 생성"),
        ("구축 모드", "매칭 스키마", "스키마 생성"),
        ("골격 seed", "층 등록", "입력 ⑤ (사람 확정)"),
        ("층 등록", "층 config", "config 생성"),
    ]
    for a, b, lb in E:
        src = "DOC" if a == "DOC" else ids.get(a)
        dst = ids.get(b)
        if not src or not dst: continue
        arrow = f' -->|"{lb}"| ' if lb else " --> "
        L.append(f"  {src}{arrow}{dst}")
    L.append(f'  {ids["질의 파이프라인"]} --> ANS')
    # 색
    L.append("  classDef human fill:#fde68a,stroke:#b45309,color:#1c1917")
    L.append("  classDef llm fill:#c7d2fe,stroke:#4338ca,color:#1e1b4b")
    L.append("  classDef asset fill:#bbf7d0,stroke:#15803d,color:#052e16")
    L.append("  classDef genconfirm fill:#fbcfe8,stroke:#9d174d,color:#500724")
    for p in parts:
        cls = {"사람": "human", "LLM": "llm", "자산": "asset", "LLM생성·사람확정": "genconfirm"}.get(p["주체"])
        if cls: L.append(f'  class {p["_id"]} {cls}')
    L.append("```")
    return "\n".join(L)



# ────────────────────────────────────────────────────────── 부품 카드
def make_cards(parts, back):
    """카드 서술(부품카드.json)을 좌표와 합쳐 문서로 낸다.

    서술은 사람/에이전트가 한 번 쓰고, **좌표·조항 참조의 유효성은 여기서 검증한다.**
    참조가 깨지면 exit 1 — 카드가 명세보다 낡았다는 신호다.
    """
    path = os.environ.get("CARDS", "docs/구조도/부품카드.json")
    if not os.path.exists(path): return None, ["부품카드.json 없음 — 서술이 아직 없다"]
    cards = {c["부품"]: c for c in json.load(open(path, encoding="utf-8"))}
    t1 = ""
    for f in glob.glob(f"{SPEC}/*.md"):
        if re.match(r'(?:정제본)?1[_.]', os.path.basename(f)): t1 = open(f, encoding="utf-8").read()
    CL = set(re.findall(r'^\| ([A-P][0-9]+) \|', t1, re.M)) | {f"P{i}" for i in range(1, 8)}
    errs, L = [], []
    STAGE = {}
    for p in parts: STAGE.setdefault(p["단계"], []).append(p)
    for st in STAGE_ORDER:
        if st not in STAGE: continue
        L.append(f"\n## {STAGE_DESC[st]}\n")
        for p in STAGE[st]:
            c = cards.get(p["부품"])
            if not c: errs.append(f"{p['부품']} — 서술 없음"); continue
            for cl in c.get("핵심조항", []):
                if cl not in CL: errs.append(f"{p['부품']} — 없는 조항 {cl}")
            mark = ACTOR_MARK.get(p["주체"], "")
            L.append(f"### {mark} {p['부품']}")
            L.append(f"> {c['한줄']}\n")
            L.append(f"| | |\n|---|---|")
            L.append(f"| **받는 것** | {c['받는것']} |")
            L.append(f"| **내는 것** | {c['내는것']} |")
            L.append(f"| **어기면** | {c['깨지면']} |")
            L.append(f"| **사람이 할 일** | {c['사람이할일']} |")
            secs = " · ".join(f"§{x}" for x in p["절"])
            cls = " · ".join(f"`{x}`" for x in c.get("핵심조항", [])) or "—"
            L.append(f"| **명세** | 문서 {p['문서']} {secs} · 조항 {cls} |")
            # 자산 정규식이 `kit/`를 이미 잡으므로 겹치는 이름을 한 번만 싣는다.
            assets = p["자산"] + [c for c in p["코드"] if c not in p["자산"]]
            if assets: L.append(f"| **실물** | {' · '.join('`'+a+'`' for a in assets[:4])} |")
            L.append(f"| **크기** | {p['bytes']//1024}KB · 금지 {p['금지']}개 |")
            if c.get("함정"): L.append(f"\n**⚠ 함정** — {c['함정']}")
            L.append("")
    return "\n".join(L), errs


def main():
    D = load()
    if not D:
        print("!! 명세를 못 찾음 — REFINED_DIR 확인"); sys.exit(1)
    parts = []
    for name, doc, secs, stage, actor in PARTS:
        t = D.get(doc, "")
        agg = {"bytes":0, "금지":0, "표":0, "조항참조":set(), "자산":set(), "코드":set()}
        missing = []
        for s in secs:
            b = section(t, s)
            if not b: missing.append(s); continue
            m = metrics(b)
            agg["bytes"] += m["bytes"]; agg["금지"] += m["금지"]; agg["표"] += m["표"]
            for k in ("조항참조","자산","코드"): agg[k] |= set(m[k])
        parts.append({
            "부품": name, "문서": f"{doc} {DOCNAME[doc]}", "절": secs, "단계": stage, "주체": actor,
            "bytes": agg["bytes"], "금지": agg["금지"], "표행": agg["표"],
            "조항": sorted(agg["조항참조"]), "자산": sorted(agg["자산"]), "코드": sorted(agg["코드"]),
            "좌표없음": missing,
        })
    # 문서별 역참조 (어기면 무엇이 깨지나)
    back = {}
    for d, t in D.items():
        i = t.find("이 문서가 지키는")
        if i > 0:
            blk = t[i:i+500].split("\n\n")[0].replace("\n", " ")
            back[d] = re.sub(r'^\S*\s*', '', blk)[:300]
    bad = [p for p in parts if p["좌표없음"]]
    print(f"구조 추출 — 부품 {len(parts)} · 문서 {len(D)} · 역참조 {len(back)}")
    if bad:
        print("★ 좌표가 깨진 부품:")
        for p in bad: print(f"   {p['부품']} — 절 {p['좌표없음']} 못 찾음")
    else:
        print("좌표 전건 유효")
    json.dump({"parts": parts, "back": back}, open(f"{OUT}/구조_추출.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n{'부품':<16}{'단계':<6}{'주체':<6}{'KB':>5}{'금지':>5}{'조항':>5}  자산·코드")
    for p in parts:
        assets = (p["자산"] + [c for c in p["코드"] if c not in p["자산"]])[:2]
        print(f"  {p['부품']:<14}{p['단계']:<6}{p['주체']:<6}{p['bytes']//1024:>5}{p['금지']:>5}{len(p['조항']):>5}  {' '.join(assets)[:44]}")
    open(f"{OUT}/구조_지도.md", "w", encoding="utf-8").write(
        "# 한 장 지도 — 문서가 답이 되기까지\n\n"
        "> **자동 생성**(`회귀스위트/추출_구조.py`). 손으로 고치지 않는다 — 명세가 바뀌면 다시 돌린다.\n"
        "> 👤 사람 · 🤖 LLM(런타임) · **🤖→👤 생성은 LLM, 확정은 사람** · 📄 자산(파일) · ⚙ 코드\n\n"
        + make_map(parts) + "\n\n## 단계가 뜻하는 것\n\n"
        + "\n".join(f"- **{k}** — {v.split(chr(8212),1)[1].strip()}" for k, v in STAGE_DESC.items()) + "\n")
    print("\n구조_지도.md 생성")
    body, cerr = make_cards(parts, back)
    if body:
        head = ("# 부품 카드 — 20장\n\n"
                "> **자동 생성**(`회귀스위트/추출_구조.py`). 좌표·조항 참조는 매 실행 검증한다 — 깨지면 exit 1.\n"
                "> 서술은 명세에서 뽑아 한 번 쓴 것이고, **명세가 바뀌면 그 부품 카드를 다시 쓴다.**\n"
                "> 👤 사람 · 🤖 LLM(런타임) · **🤖→👤 생성은 LLM, 확정은 사람** · 📄 자산(파일) · ⚙ 코드\n\n"
                "**이 카드는 명세를 대신하지 않는다** — 401KB의 **입구**다. 「어느 부품인가」를 알고 「어느 절로 들어가는가」를 대는 것이 전부이며, 판단이 갈리면 **명세가 이긴다.**\n")
        open(f"{OUT}/부품카드.md", "w", encoding="utf-8").write(head + body + "\n")
        print(f"부품카드.md 생성 — 참조 오류 {len(cerr)}건")
        for e in cerr[:6]: print("   ", e)
        if cerr: bad.append({"부품": "카드"})
    open(f"{OUT}/10_코드_지도.md", "w", encoding="utf-8").write(make_code_map())
    print("10_코드_지도.md 생성")
    sys.exit(1 if bad else 0)


# ────────────────────────────────────────────────────────── 코드 지도 (B78 3 ⑤)
# **손으로 쓰는 문장이 0이다.** 아래 전부 AST와 파일시스템에서 뽑는다 — 지도가 코드보다
# 낡는 길을 문장이 아니라 생성으로 막는다. 회귀가 이 산출을 다시 만들어 레포의 파일과
# 대조하므로(diff 0), 코드가 움직이면 지도가 붉어진다.
import ast
from pathlib import Path as _P

CODE_ROOT = _P(__file__).resolve().parent.parent.parent
CODE_DIRS = ("core", "cli", "parser", "kit")
CODE_ENTRIES = ("run.py", "doctor.py", "router.py")
LIMIT_FILE, LIMIT_FUNC = 800, 120        # CLAUDE.md §7 · 문서 7 §7.1


def _mods():
    """운영 모듈 전부 — `tests/test_g1_g2.py`의 머리말 어서션과 같은 목록이다."""
    out = [p for d in CODE_DIRS for p in sorted((CODE_ROOT / d).rglob("*.py"))
           if "__pycache__" not in p.parts]
    out += [CODE_ROOT / e for e in CODE_ENTRIES]
    return out


def _facts(path):
    """파일 하나의 사실 — 칸 번호 · 한 줄 · 행 수 · def 수 · 최장 함수."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    head = (ast.get_docstring(tree) or "").splitlines()
    first = head[0] if head else ""
    m = re.match(r'칸\s+([\d.]+(?:\s*[~·]\s*[\d.]+)*)\s*(.*)', first)
    kan, rest = (m.group(1).replace(" ", ""), m.group(2)) if m else ("", first)
    pre, dash, tail = rest.partition("—")
    what = (tail if dash else pre).strip()
    extra = pre.strip().strip("·~ ")
    kan = kan + ("·" + extra if extra else "")
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    longest = max(((n.end_lineno - n.lineno + 1, n.name) for n in funcs), default=(0, "—"))
    return {"rel": path.relative_to(CODE_ROOT).as_posix(), "칸": kan,
            "한줄": what.replace("**", "").strip().rstrip("."), "행": len(src.splitlines()),
            "def": len(funcs), "최장": longest[1], "최장행": longest[0],
            "class": sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))}


def _imports(path):
    """이 파일이 import하는 모듈 이름 — `core.graph` 꼴로 편다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
            for a in n.names:
                out.add(f"{n.module}.{a.name}")
        elif isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name)
    return out


def _run_table():
    """`run.py`의 **서브커맨드 → 위임처**. 디스패치 dict와 각 `cmd_*`를 읽는다."""
    tree = ast.parse((CODE_ROOT / "run.py").read_text(encoding="utf-8"))
    deleg = {}
    for n in tree.body:                       # ① `cmd_*`가 함수 안에서 하는 import
        if not isinstance(n, ast.FunctionDef):
            continue
        where, called = {}, []
        for k in ast.walk(n):
            if isinstance(k, ast.ImportFrom) and k.module:
                for a in k.names:
                    where[a.asname or a.name] = f"{k.module}.{a.name}"
        for k in ast.walk(n):
            if isinstance(k, ast.Call) and isinstance(k.func, ast.Name):
                got = where.get(k.func.id)
                if got and got not in called:
                    called.append(got)
        deleg[n.name] = " · ".join(f"`{x}`" for x in called)
    rows = []                                 # ② 디스패치 dict — 키가 서브커맨드
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        for key, val in zip(n.keys, n.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and isinstance(val, ast.Lambda)):
                continue
            fn = ""
            for k in ast.walk(val):
                if isinstance(k, ast.Call) and isinstance(k.func, ast.Name):
                    fn = k.func.id
            if fn.startswith("cmd_"):
                rows.append((key.value, fn, deleg.get(fn, "")))
    return sorted(set(rows))


def _module_entries():
    """`python -m cli.X`로 도는 자리 — `__main__` 블록을 가진 파일."""
    out = []
    for p in sorted((CODE_ROOT / "cli").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        if not any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test)
                   for n in tree.body):
            continue
        rel = p.relative_to(CODE_ROOT)
        name = ".".join(rel.with_suffix("").parts)
        if name.endswith(".__main__"):
            name = name[: -len(".__main__")]
        out.append((f"python -m {name}", rel.as_posix()))
    return sorted(set(out))


def _paths_table():
    """`core/paths.py`의 자리 함수 → 실경로. **불러서 잰다**(문면을 베끼지 않는다)."""
    sys.path.insert(0, str(CODE_ROOT))
    # 재실행이 같은 표를 내야 한다 — 상태 루트를 고르는 환경변수를 **여기서 고정한다**.
    for k in ("ONTO_HOME", "ONTO_FIXTURES"):
        os.environ.pop(k, None)
    os.environ["USE_MOCK"] = "1"
    from core import paths as P
    P.reset()
    stage = {"home": "—", "registry": "②등록", "review": "②등록", "adapters": "②등록",
             "schemas": "②등록", "fixture_schemas": "①자산", "blocks": "①자산",
             "config_file": "①자산", "data": "③진실", "work": "④작업·장부",
             "parsed": "④작업·장부", "extract": "④작업·장부", "export": "⑤파생",
             "golden": "⑤파생"}
    rows = []
    for name, st in stage.items():
        fn = getattr(P, name, None)
        if fn is None:
            continue
        got = _P(fn())
        try:
            shown = "<상태>/" + got.relative_to(P.home()).as_posix()
        except ValueError:
            try:
                shown = "<레포>/" + got.relative_to(P.ROOT).as_posix()
            except ValueError:
                shown = got.name
        if name == "home":
            shown = "<상태>"
        doc = (fn.__doc__ or "").splitlines()[0].replace("**", "")
        rows.append((name, st, shown, doc))
    return rows


def make_code_map():
    """`10_코드_지도.md` 본문 — ⓐ폴더=파트 ⓑ진입점 ⓒ경계 ⓓ자리 ⓔ크기."""
    facts = [_facts(p) for p in _mods()]
    by_dir = {}
    for f in facts:
        d = str(_P(f["rel"]).parent)
        by_dir.setdefault("(레포 루트)" if d == "." else d + "/", []).append(f)

    L = ["# 코드 지도 — 파일 하나에 자리 하나", ""]
    L.append("> **자동 생성**(`docs/회귀스위트/추출_구조.py`). 손으로 고치지 않는다 — "
             "코드가 바뀌면 다시 돌린다.")
    L.append("> 회귀가 이 파일을 **다시 만들어 레포의 것과 대조한다**(diff 0) — 낡으면 붉다.")
    L.append("> 칸 번호는 각 파일 **첫 줄 머리말**에서 읽는다 — `00_칸_대장.md`와 같은 번호다.")
    L.append("")

    L.append("## ⓐ 폴더 = 파트")
    L.append("")
    for d in sorted(by_dir):
        rows = sorted(by_dir[d], key=lambda r: r["rel"])
        kans = sorted({n for r in rows for n in re.findall(r'(\d+)\.', r["칸"])},
                      key=lambda x: (len(x), x))
        L.append(f"### `{d}` — 칸 {'·'.join(kans) or '—'} · 파일 {len(rows)} · "
                 f"{sum(r['행'] for r in rows):,}행 · def {sum(r['def'] for r in rows)}")
        L.append("")
        L.append("| 파일 | 칸 | 무엇을 맡나 | 행 | def |")
        L.append("|---|---|---|---:|---:|")
        for r in rows:
            L.append(f"| `{_P(r['rel']).name}` | {r['칸'] or '—'} | {r['한줄']} | "
                     f"{r['행']} | {r['def']} |")
        L.append("")

    L.append("## ⓑ 진입점")
    L.append("")
    L.append("**`python run.py <서브커맨드>`** — 위임처는 각 `cmd_*`가 함수 안에서 하는 "
             "import에서 읽는다.")
    L.append("")
    L.append("| 서브커맨드 | run.py | 위임처 |")
    L.append("|---|---|---|")
    for sub, fn, to in _run_table():
        L.append(f"| `{sub}` | `{fn}` | {to or '(제자리)'} |")
    L.append("")
    L.append("**`python -m …`** — `__main__` 블록을 가진 자리.")
    L.append("")
    L.append("| 명령 | 파일 |")
    L.append("|---|---|")
    for cmd, rel in _module_entries():
        L.append(f"| `{cmd}` | `{rel}` |")
    L.append("")

    L.append("## ⓒ 접근 경계 — `core/` 최상위")
    L.append("")
    L.append("경계 밖에서 직접 열지 않는다(문서 7 §7.1). **부르는 모듈 수**는 import 문을 세어 잰다 "
             "(운영 모듈 + 회귀).")
    L.append("")
    L.append("| 파일 | 칸 | 무엇을 소유하나 | 부르는 모듈 |")
    L.append("|---|---|---|---:|")
    tops = [f for f in facts if _P(f["rel"]).parent.as_posix() == "core"
            and _P(f["rel"]).name != "__init__.py"]
    imp = {p.relative_to(CODE_ROOT).as_posix(): _imports(p) for p in _mods()}
    imp.update({p.relative_to(CODE_ROOT).as_posix(): _imports(p)
                for p in sorted((CODE_ROOT / "tests").rglob("*.py"))
                if "__pycache__" not in p.parts})
    for f in sorted(tops, key=lambda r: r["rel"]):
        mod = f["rel"][:-3].replace("/", ".")
        n = sum(1 for rel, names in imp.items() if rel != f["rel"] and mod in names)
        L.append(f"| `{f['rel']}` | {f['칸']} | {f['한줄']} | {n} |")
    L.append("")

    L.append("## ⓓ 상태의 자리 — `core/paths.py`")
    L.append("")
    L.append("| 함수 | 단 | 실경로 | 무엇 |")
    L.append("|---|---|---|---|")
    for name, st, shown, doc in _paths_table():
        L.append(f"| `paths.{name}()` | {st} | `{shown}` | {doc} |")
    L.append("")

    L.append("## ⓔ 크기 — §7 상한 (파일 800행 · 함수 120행)")
    L.append("")
    over_f = [f for f in facts if f["행"] > LIMIT_FILE]
    over_x = [f for f in facts if f["최장행"] > LIMIT_FUNC]
    L.append(f"- 운영 모듈 **{len(facts)}** · 합 **{sum(f['행'] for f in facts):,}행** · "
             f"def **{sum(f['def'] for f in facts)}** · class {sum(f['class'] for f in facts)}")
    L.append(f"- **파일 상한 위반 {len(over_f)}** · **함수 상한 위반 {len(over_x)}**")
    L.append("")
    L.append("큰 파일 열 (행 순).")
    L.append("")
    L.append("| 파일 | 행 | 최장 함수 | 행 |")
    L.append("|---|---:|---|---:|")
    for f in sorted(facts, key=lambda r: (-r["행"], r["rel"]))[:10]:
        L.append(f"| `{f['rel']}` | {f['행']} | `{f['최장']}` | {f['최장행']} |")
    L.append("")
    for tag, rows in (("파일", over_f), ("함수", over_x)):
        if rows:
            L.append(f"**{tag} 상한 위반**: " + " · ".join(f"`{r['rel']}`" for r in rows))
            L.append("")
    return "\n".join(L)


main()
