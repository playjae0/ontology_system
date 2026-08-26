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
        "자산": sorted(set(re.findall(r'`((?:layers|schemas|kit|data|mock|extract)/[\w/{}.*]+)`', body))),
        "코드": sorted(set(re.findall(r'`((?:core|cli|parser)/[\w]+\.py)`', body))),
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
    path = os.environ.get("CARDS", "docs/가이드/부품카드.json")
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
            assets = (p["자산"] + p["코드"])
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
    json.dump({"parts": parts, "back": back}, open(f"{SPEC}/구조_추출.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n{'부품':<16}{'단계':<6}{'주체':<6}{'KB':>5}{'금지':>5}{'조항':>5}  자산·코드")
    for p in parts:
        assets = (p["자산"] + p["코드"])[:2]
        print(f"  {p['부품']:<14}{p['단계']:<6}{p['주체']:<6}{p['bytes']//1024:>5}{p['금지']:>5}{len(p['조항']):>5}  {' '.join(assets)[:44]}")
    open(f"{SPEC}/구조_지도.md", "w", encoding="utf-8").write(
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
        open(f"{SPEC}/부품카드.md", "w", encoding="utf-8").write(head + body + "\n")
        print(f"부품카드.md 생성 — 참조 오류 {len(cerr)}건")
        for e in cerr[:6]: print("   ", e)
        if cerr: bad.append({"부품": "카드"})
    sys.exit(1 if bad else 0)

main()
