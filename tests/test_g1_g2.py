# -*- coding: utf-8 -*-
"""G1+G2 완료판정 — 정지점 2 프롬프트의 어서션을 실행 가능한 검사로.

  st  : graph.py 밖 직접 접근 0 (grep 실증) + 계기판 7·8 출력
  n1  : S6(occ 충돌) + 멱등성 2종(2회 인입 동일 · 조각 순서 셔플 동일)
  n2  : S5(doc_hash 차단)
  n10 : **seed v3.2 골격**(Process 46 · part_of 45 · precedes 22 · polarity≠none 16
        · mirrors 쌍 8) + 파생 대표 흐름 출력 + registry에 builtin 층 1개만 존재
        — 구 기대값(8·7·6)은 골격 두 축 분리(D-42) 전 수치다.

사용: python tests/test_g1_g2.py
"""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import init, gate, store                              # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph   # noqa: E402
from core.ids import is_ulid                              # noqa: E402
from core.ingest import ingest                            # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "mock" / "parsed" / name).read_text(encoding="utf-8"))


def canon(g):
    return {n["canonical"] for n in g.nodes.values()}


def reset():
    """**깨끗한 그래프에서 전체 재빌드.** v3.2는 canonical 체계 자체가 바뀌었으므로
    (sub 이하 부모 경로 접두 · 인스턴스 `{개념}::{축값}`) 기존 그래프 위에 다시 심으면
    옛 골격이 살아남는다 — 멱등성(D-41)이 막는 것은 "같은 canonical의 재발급"이지
    "canonical 체계 변경"이 아니다. 기대값 대조는 반드시 이 경로로 한다.
    """
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    return bootstrap("process", echo=False)


# ============================================================ st
print("\n■ st — 저장 계층 경계 (틀 §4B-A8 · 카드 B6)")

# 층 그래프 파일을 아는 코드가 core/graph.py 밖에 있는가. 리뷰 규칙의 기계 실증이다.
# 패턴을 조각으로 만드는 이유: 이 파일 자신이 검사에 걸리지 않게 하기 위해서다.
PAT = re.compile("graph" + r"\." + "json")
hits = []
for p in ROOT.rglob("*.py"):
    if any(x in p.parts for x in (".venv", "__pycache__", "mock")):
        continue
    if p == ROOT / "core" / "graph.py":
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if PAT.search(line) and not line.lstrip().startswith("#"):
            hits.append(f"{p.relative_to(ROOT)}:{i}")
show("core/graph.py 밖에서 층 그래프 파일을 아는 코드 0지점", not hits, str(hits))

# **cli/에 sys.path 조작이 없는가** (문서 7 §7.1 패키지화).
# 조작으로 붙이면 CLI가 실행 위치에 의존해 "subprocess로 호출 가능한 CLI+파일"이
# 호출부의 작업 디렉터리에 따라 깨진다. 실행 규약은 `python -m cli.{진입점}`이다.
PATH_HACK = "sys" + r"\.path\.insert"
import re as _re
_pat = _re.compile(PATH_HACK)
cli_hits = [f"{p.relative_to(ROOT)}:{i}"
            for p in sorted((ROOT / "cli").glob("*.py"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _pat.search(line) and not line.lstrip().startswith("#")]
show("cli/ 8종에 sys.path 조작 0지점 — 실행은 python -m cli.{진입점}",
     not cli_hits, str(cli_hits))

# **원자적 쓰기가 배선돼 있는가** (문서 7 §7.1 저장 계층).
# 직접 덮어쓰면 build가 쓰기 도중 죽었을 때 진실이 반쯤 쓰인 채 남는다 —
# data/는 백업 대상이지 재생성 대상이 아니라 복구가 불가능하다.
_src = (ROOT / "core" / "store.py").read_text(encoding="utf-8")
_gsrc = (ROOT / "core" / "graph.py").read_text(encoding="utf-8")
show("저장 쓰기가 tmp+os.replace·flock 경유다 (직접 덮어쓰기 0)",
     "os.replace" in _src and "flock" in _src
     and "atomic_write_bytes" in _gsrc
     and "write_bytes(_dumps(" not in _gsrc)

# **빈 상태의 형태가 §7.2 말미와 같은가** — 클린의 정의가 하나여야
# 회귀 규약(§7.5-7)과 완료판정 4번이 같은 바닥 위에 선다.
from core import init as _init                                # noqa: E402
_init.init(fresh_=True)
_want = {store.CHUNKS: {"chunks": {}, "describes": []},
         store.DICTIONARY: {}, store.QUEUE: []}
_got = {n: store.read(n, "없음") for n in _want}
show("run.py init --fresh 의 빈 상태 형태가 명세와 일치 (§7.2)",
     _got == _want, str(_got))

g, m, _, flow = reset()
show("계기판 7 (graph 저장 크기) 출력", "gauge7_graph_bytes" in m,
     f"{m['gauge7_graph_mb']}MB")
show("계기판 8 (build 소요) 출력", "gauge8_build_seconds" in m,
     f"{m['gauge8_build_seconds']}s")
show("알람선 미초과 (200MB / 30초)",
     not m["gauge7_over_alarm"] and not m["gauge8_over_alarm"])
show("직렬화 orjson (미설치 시 표준 json 폴백)", m["serializer"] in ("orjson", "json"),
     m["serializer"])

# ============================================================ n10
print("\n■ n10 — 부트스트랩 seed·config (골격 seed v3.2 · 두 축 분리)")
rels = Counter(e["rel"] for e in g.edges)
POL = [n for n in g.nodes.values() if n.get("polarity") not in (None, "none")]
show("Process 46노드",
     sum(1 for n in g.nodes.values() if n["category"] == "Process") == 46,
     str(len(g.nodes)))
show("part_of 45 (구조 — 루트 제외 전 노드)", rels["part_of"] == 45, str(rels["part_of"]))
show("precedes 22 (지식 — 참여 항목만 건너 이음)", rels["precedes"] == 22,
     str(rels["precedes"]))
show("polarity ≠ none 16 (인스턴스 4 + @split 인스턴스 12)", len(POL) == 16,
     str(len(POL)))
show("mirrors 쌍 8 (노칭 1 + 탭용접 1 + @split 6)", rels["mirrors"] == 16,
     f"엣지 {rels['mirrors']} → 쌍 {rels['mirrors'] // 2}")
show("골격 노드 status = seed",
     {n["status"] for n in g.nodes.values()} == {"seed"})
show("골격 provenance = ['seed']",
     all(n["provenance"] == ["seed"] for n in g.nodes.values()))

# tier·canonical — loader 파생이며 수기 접두가 아니다 (A11-7 · D-47)
tiers = Counter(n["tier"] for n in g.nodes.values())
show("tier가 깊이에서 파생 (main 1 · sub 8 · detail 37)",
     tiers == Counter({"main": 1, "sub": 8, "detail": 37}), str(dict(tiers)))
show("main·sub canonical은 이름 그대로 / detail은 부모 경로 접두",
     {"조립", "노칭", "탭용접"} <= canon(g)
     and "탭용접::pre용접" in canon(g) and "패키징::사이드 실링" in canon(g))
show("인스턴스 canonical = {개념}::{축값} — 쌍 유무 무관 균일",
     {"노칭::cathode", "노칭::anode", "탭용접::pre용접::cathode"} <= canon(g))
show("극성 인스턴스 간 precedes 0건 (구조적 미생성 — J12)",
     not [e for e in g.edges if e["rel"] == "precedes"
          and (g.get(e["src"]).get("polarity") != "none"
               or g.get(e["dst"]).get("polarity") != "none")])

# seed ALIASES → 사전 등재 (장부는 dictionary.json 하나 — 카드 B4)
D = store.read(store.DICTIONARY, {})
show("seed ALIASES가 사전에 등재 (provenance=['seed'])",
     D.get("notching") and D.get("전해액주입")
     and all(a["provenance"] == ["seed"]
             for n in g.nodes.values() for a in n["aliases"]))
show("인스턴스 auto alias 2종 ('{축값} {이름}' · '{라벨} {이름}')",
     D.get("cathode 탭용접") and D.get("양극 탭용접") and D.get("음극 노칭"))
show("짧은 이름 auto alias (detail 노드의 접두 없는 조회)",
     D.get("사이드 실링") and D.get("적층") and D.get("pre용접"))
show("모호한 짧은 이름은 미등재 ('비전검사' — 접두 키가 대신한다)",
     "비전검사" not in D and D.get("노칭 검사") and D.get("정렬 검사"))

# 파생 대표 흐름 출력 — 순서 오선언의 유일한 안전망 (A11-2 · M9 계보)
show("로드 시 파생 대표 흐름 출력 (레벨 5줄)", len(flow) == 5, f"{len(flow)}줄")
show("무주장 항목이 흐름에서 빠지고 별도 표기됨 (@unordered)",
     any("무주장" in ln and "전극 시트 공급" in ln for ln in flow)
     and not any("전극 시트 공급 →" in ln for ln in flow))

# ── seed는 후보가 아니라 선언이다 (틀 §4B-A3 경로 ①) ────────────────────────
# 골격이 게이트를 지나지 않는 것은 **설계**이며, 그 대가로 패턴표에 골격 관계를
# 넣지 않는다. 넣으면 추출 경로(③)가 골격을 개정할 수 있게 된다(A5 발명 금지 ③).
# 아래 셋은 그 균형을 **우연이 아니라 보장으로** 잠근다.
print("\n■ seed 경로 ① — 선언이지 후보가 아니다 (게이트 비경유의 잠금)")
CFG = load_config("process")
SKEL_REL = {CFG["skeleton"]["relations"]["child"],
            CFG["skeleton"]["relations"]["sibling"],
            (CFG.get("mirrors") or {}).get("relation")}
SKEL_CAT = CFG["skeleton"]["category"]
show("① 패턴표에 골격 관계가 없다 (추출이 골격을 개정할 수 없다)",
     not [p for p in CFG["relation_patterns"]
          if p["src"] == SKEL_CAT and p["dst"] == SKEL_CAT and p["rel"] in SKEL_REL],
     str([f"{p['src']} -{p['rel']}-> {p['dst']}" for p in CFG["relation_patterns"]
          if p["src"] == SKEL_CAT and p["dst"] == SKEL_CAT]))
# 표에 없다는 것만으로는 부족하다 — 실제로 어느 경로로도 커밋되지 않아야 한다.
# 특히 경로 ②(스키마 edges 선언)는 동종 쌍도 무비용 통과하므로, 패턴이 하나라도
# 남아 있으면 **정형 문서가 골격 흐름을 개정**한다(A11-2 "순서의 출처는 seed 하나뿐").
_paths = (gate.PATH_SCHEMA, gate.PATH_EXTRACT, gate.PATH_AUTO)
_verdicts = {f"{r}/{p}": gate.judge(SKEL_CAT, r, SKEL_CAT, CFG, p)[0]
             for r in SKEL_REL if r for p in _paths}
show("② 문서·규칙 경로(②③④) 어느 쪽도 골격 관계를 커밋하지 못한다",
     gate.COMMIT not in _verdicts.values(), str(_verdicts))
show("③ loader가 게이트를 부르지 않는다 (경유 자체가 없다)",
     "gate" not in (ROOT / "core" / "bootstrap.py").read_text(encoding="utf-8"))
show("골격 엣지 status = seed · 게이트 거부 로그 0건",
     {e["status"] for e in g.edges} == {"seed"}
     and not store.path(store.GATE_REJECTS).exists())

reg = store.read(store.REGISTRY, {})
show("registry에 builtin 층 1개만 존재",
     len(reg) == 1 and list(reg.values())[0]["status"] == "builtin", str(list(reg)))
show("의미 축 id가 전부 ULID (id_seq.json 없음)",
     all(is_ulid(i) for i in g.nodes) and not (store.DATA / "id_seq.json").exists())

# ============================================================ n1
print("\n■ n1 — 근거 축 id (내용 계산)")
reset()
r3 = ingest(load("PPT03.json"))
c = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
m23 = [k for k, v in c.items() if v["source_locator"] in ("PPT03-C002", "PPT03-C003")]
show("S6 — 동일 (section, text) 2건의 chunk_id가 서로 다름 (occ 0·1)",
     len(set(m23)) == 2, str(sorted(m23)))
show("S6 — 충돌 결함 로그 0건", not r3.defects and
     not (store.DATA / store.DEFECTS).exists())
show("chunk_id가 doc_id 스코프 + 12자 해시",
     all(re.fullmatch(r"PPT03:[0-9a-f]{12}", k) for k in m23), str(m23[:1]))

# 멱등성 ① — 같은 문서 2회 인입
reset()
a = ingest(load("PPT01.json"))
snap1 = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
b = ingest(load("PPT01.json"))
snap2 = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
show("멱등성 ① 같은 문서 2회 인입 — id 집합 동일", a.ids == b.ids)
show("멱등성 ① 같은 문서 2회 인입 — 청크 저장 동일", snap1 == snap2)

# 멱등성 ② — payload 조각 순서 셔플
reset()
env = load("PPT01.json")
base = ingest(env)
snap_base = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
ok_ids, ok_store = True, True
for seed in (1, 2, 3):
    reset()
    sh = json.loads(json.dumps(env))
    random.Random(seed).shuffle(sh["chunks"])
    s = ingest(sh)
    ok_ids &= (s.ids == base.ids)
    ok_store &= (json.dumps(store.read(store.CHUNKS, {}),
                            ensure_ascii=False, sort_keys=True) == snap_base)
show("멱등성 ② 조각 순서 셔플 3회 — id 집합 동일", ok_ids)
show("멱등성 ② 조각 순서 셔플 3회 — 청크 저장 동일", ok_store)

# 표 문서: record_id + content 필드별 청크(D8)
reset()
cp = ingest(load("CP01.json"))
fm = ingest(load("PFMEA01.json"))
show("CP01 record 12건", len(cp.record_ids) == 12, str(len(cp.record_ids)))
show("PFMEA01 record 13건", len(fm.record_ids) == 13, str(len(fm.record_ids)))
show("record_id 전부 유일 (충돌 접미 없이)",
     len(set(cp.record_ids)) == 12 and len(set(fm.record_ids)) == 13)
cc = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
content = [k for k in cc if "-" in k.split(":", 1)[1]]
show("table content 청크 id = {record_id}-{필드명} (D8)",
     content and all(re.fullmatch(r"[A-Z0-9]+:[0-9a-f]{12}-.+", k) for k in content),
     f"{len(content)}건")
show("청크에 adapter_version 복사됨 (봉투 1회 → 청크, 카드 C9)",
     all(v["adapter_version"] == "mock-1.0" for v in cc.values()))
show("링킹 0건 청크도 보존 (linked=false, 카드 C6)",
     all(v["linked"] is False for v in cc.values()))

# ============================================================ n2
print("\n■ n2 — doc_hash 중복 차단")
reset()
ingest(load("CP01.json"))
before = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
held = ingest(load("CP01B.json"))
after = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
q = [x for x in store.read(store.QUEUE, []) if x["kind"] == "duplicate_doc_hold"]
show("S5 — 내용 같고 doc_id 다른 문서는 인입 보류", held.status == "held", held.reason)
show("S5 — duplicate_doc_hold 큐 1건", len(q) == 1, str(len(q)))
show("S5 — 큐에 파일명·기존 doc_id 동봉",
     q and q[0]["payload"]["existing_doc_id"] == "CP01"
     and q[0]["payload"]["source_path"] == "CP_사본.xlsx")
show("S5 — 보류 문서는 청크에 아무것도 쓰지 않음", before == after)
same = ingest(load("CP01.json"))
show("S5 대조 — 같은 doc_id 재인입은 통과(정상 경로)", same.status == "ok")

# ============================================================
print("\n" + "=" * 62)
print("전체 결과:", "PASS — G1+G2 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
