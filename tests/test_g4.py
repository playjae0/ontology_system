# -*- coding: utf-8 -*-
"""G4 완료판정 — 정지점 4의 어서션을 실행 가능한 검사로.

  2′  : 질의 4단 + 이원 근거 채널 (queries.json 12문항 · 2홉 도달 · flow 특례
        · 링킹 미스 로그) + **순서 파생 3분기와 해상도 표기**(D-44 · CH5 5.1 규약 8)
  3′  : 품질층 = 신규 층 등록 절차의 첫 검증 대상(J10) — 수동 config 경로.
        causes 사슬 · cross 질의 · **Q1~8 회귀 무오염**(§8-6 채널분리)
  3.5′: 재인입 회귀 — 노드 중복 0 · provenance 복원 · run.py all 2회 동일 그래프

사용: python tests/test_g4.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import query as R                              # noqa: E402
from core import init, query as Q                             # noqa: E402
from core import store                                  # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph   # noqa: E402
from core.extract import EXTRACT_DIR                    # noqa: E402
from core.pipeline import finalize, run_document                  # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / "parsed" / name).read_text(encoding="utf-8"))


DOCS = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
QUERIES = json.loads((ROOT / "tests" / "fixtures" / "queries.json").read_text(encoding="utf-8"))


def full_run():
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for d in DOCS:
        run_document(load(f"{d}.json"))
    finalize()                          # 빌드 말미 패스 — 전역 재평가는 여기서 돈다


full_run()
P, QG = open_graph("process"), open_graph("quality")
CFG = load_config("process")

# ============================================================ 2′
print("\n■ 2′ — 질의 4단 + 이원 근거 채널 (CH5 5.1·5.2)")
results = {q["id"]: R.answer(q["q"]) for q in QUERIES["queries"]}
bad = [(q["id"], q["expected_path"], results[q["id"]]["path"])
       for q in QUERIES["queries"] if results[q["id"]]["path"] != q["expected_path"]]
show("queries.json 12문항이 expected_path대로 응답", not bad, str(bad))

show("flow 질의(5번)가 골격 대표 흐름을 통째로 공급",
     len(results[5]["facts"]) == sum(1 for e in P.edges if e["rel"] == "precedes"
                                     and P.get(e["src"])["polarity"] == "none"),
     f"{len(results[5]['facts'])}줄")
show("flow는 개념 레벨이다 — 축 인스턴스는 흐름에 없다 (J12)",
     not any("::cathode" in f or "::anode" in f for f in results[5]["facts"]))

# 2홉 도달: 공정 →(part_of 하향)→ 설비 →(has_property)→ 인자. 프론티어 전파의 실증.
show("2홉 도달 — part_of 하향으로 닿은 설비의 has_property 인자까지 수집",
     any("스태커의 관리인자" in f for f in results[4]["facts"]),
     str([f for f in results[4]["facts"] if "관리인자" in f][:2]))

show("링킹 미스 로그 기록 (하이브리드 도입 판정 데이터 — 5.4)",
     store.path(store.LINK_MISS).exists()
     and "리튬이온" in store.path(store.LINK_MISS).read_text(encoding="utf-8"))
show("답변 3단 — 근거 없음은 [일반지식] 표시와 함께 답한다",
     "[일반지식" in (results[12]["note"] or "") and not results[12]["facts"])
show("질의는 읽기 전용 (P6) — 질문 표기를 사전에 배우지 않는다",
     "리튬이온 배터리" not in store.read(store.DICTIONARY, {}))
show("precedes·mirrors는 기본 확장에서 제외 (5.1 규약 4)",
     "precedes" not in (CFG["query_traverse"] or {})
     and "mirrors" not in (CFG["query_traverse"] or {}))

# ---- 순서 파생 3분기 (D-44 · 틀 §4B-A11-5) ----
print("\n■ 2′ — 순서 파생 3분기와 해상도 표기 (M2 · CH5 5.1 규약 8)")
D = QUERIES["_derived_order"]
o = {k: R.answer(v) for k, v in D.items() if not k.startswith("_")}


def fact(key):
    """순서 답만 골라 본다 — 브리지는 순서 질문에도 상시 적용되므로(명세 §8-6)
    같은 답변에 걸침 사실이 함께 실린다. 그 딸림은 정상이고 판정 대상이 아니다."""
    return " / ".join(f for f in o[key]["facts"]
                      if "다음 공정" in f or "순서 정보 없음" in f)


show("① 자기 선언 — 그대로 답하고 해상도를 덧붙이지 않는다",
     fact("self") == "노칭 다음 공정은 스태킹이다", fact("self"))
show("② 부모 파생 + 동일 축값 인스턴스 하강",
     "탭용접::pre vision::cathode" in fact("derived_instance"), fact("derived_instance"))
show("② 파생 답에 **해상도 표기**", "기준)" in fact("derived_instance"))
show("② 공유 스텝 합류 자동 — 후속에 동일 축값이 없으면 개념 노드로 답한다",
     "탭용접::bead press" in fact("derived_merge"), fact("derived_merge"))
show("③ 조상까지 선언이 없으면 '순서 정보 없음' (추측 금지)",
     "순서 정보 없음" in fact("none"), fact("none"))

# ============================================================ 3′
print("\n■ 3′ — 품질층 = 신규 층 등록 절차의 첫 검증 대상 (J10 · 수동 config 경로)")
reg = store.read(store.REGISTRY, {})
show("품질층이 registry에 등록됨 (status=registered)",
     reg.get("quality", {}).get("status") == "registered", str(sorted(reg)))
show("등록 후에도 builtin 층은 공정층 1개",
     sum(1 for v in reg.values() if v["status"] == "builtin") == 1,
     str([k for k, v in reg.items() if v["status"] == "builtin"]))
show("층 등록에 코드가 없다 — config가 선언한 관계·카테고리로 registry가 선다",
     set(reg["quality"]["relations"]) == set(load_config("quality")["relations"]))

qcanon = {n["canonical"] for n in QG.nodes.values()}
show("causes 사슬 존재 (이물 유입 → 절연 파괴 → 내부 단락)",
     {"이물 유입", "절연 파괴", "내부 단락"} <= qcanon
     and any(QG.get(e["src"])["canonical"] == "절연 파괴"
             and QG.get(e["dst"])["canonical"] == "내부 단락"
             for e in QG.edges if e["rel"] == "causes"))
show("cross 9번 — occurs_in 역방향으로 노칭의 Failure들이 나온다",
     len([f for f in results[9]["facts"] if "공정에서 발생" in f]) >= 3,
     str([f for f in results[9]["facts"] if "공정에서 발생" in f][:2]))
show("cross 10번 — affects 역방향 직접 결과 + 수집 노드 간 causes 문장화",
     any("(으)로 이어질 수 있다" in f for f in results[10]["facts"])
     and any("원인이 될 수 있다" in f for f in results[10]["facts"]))
show("걸침 엣지는 출발 층(품질층) 템플릿으로 문장화 (§8-R4)",
     any("공정에서 발생한다" in f for f in results[9]["facts"]))

# ---- Q1~8 회귀 무오염 (§8-6 채널분리) ----
# 브리지를 끈 상태(= 단계 2 baseline)와 켠 상태를 대조한다. 1홉은 딸림 자체를 막지
# 못하므로(명세 §8-6) 판정은 "Failure가 안 딸려온다"가 아니라 **"직접 근거가 밀려나지
# 않는다"**다 — 브리지는 tier2로만 들어오고 잘림은 바깥부터다.
_real = Q.bridge
Q.bridge = lambda *a, **k: ({}, [])
base = {q["id"]: R.answer(q["q"]) for q in QUERIES["queries"][:8]}
Q.bridge = _real


def tier1(res):
    return {c["chunk_id"] for c in res["chunks"] if c["tier"] == 1}


drift = [q["id"] for q in QUERIES["queries"][:8]
         if base[q["id"]]["path"] != results[q["id"]]["path"]
         or tier1(base[q["id"]]) != tier1(results[q["id"]])]
show("Q1~8 회귀 무오염 — cross-layer on/off에서 경로·직접 근거 동일",
     not drift, str(drift))
show("브리지 유래 근거는 tier2로만 들어온다 (직접 근거를 밀어내지 않는다)",
     all(c["tier"] == 2 for r in results.values() for c in r["chunks"]
         if c["doc_id"] == "PFMEA01" and r is not results[9]))

# ============================================================ 3.5′
print("\n■ 3.5′ — 재인입 회귀 (노드 유일성 P4)")
before_n = len(P.nodes)
before_prov = {n["canonical"]: sorted(n["provenance"]) for n in P.nodes.values()}
for d in DOCS:
    run_document(load(f"{d}.json"))
finalize()
P2 = open_graph("process")
show("재인입 후 노드 수 불변 (중복 0)", len(P2.nodes) == before_n,
     f"{before_n} → {len(P2.nodes)}")
show("사전 재매칭으로 provenance 복원 (잃은 출처 0)",
     all(set(before_prov.get(n["canonical"], [])) <= set(n["provenance"])
         for n in P2.nodes.values()),
     str([n["canonical"] for n in P2.nodes.values()
          if not set(before_prov.get(n["canonical"], [])) <= set(n["provenance"])][:3]))
# 큐는 조건의 화면이지 이력이 아니다 — 재인입이 같은 조건을 다시 싣지 않아야 하고
# (중복 제거), 재계산하는 쪽은 해소된 조건을 내려야 한다(self-heal). 둘 다 3.5 규약 6.
q_after = store.read(store.QUEUE, [])
for d in DOCS:
    run_document(load(f"{d}.json"))
finalize()
q_again = store.read(store.QUEUE, [])
show("재인입이 큐를 증식시키지 않는다 (중복 제거 — 3.5 규약 6)",
     len(q_again) == len(q_after), f"{len(q_after)} → {len(q_again)}")
show("미검토 작업목록은 재인입에도 보존된다 (auto_node — 재검출되지 않는 상시 조건)",
     sum(1 for x in q_again if x["kind"] == "auto_node") ==
     sum(1 for x in q_after if x["kind"] == "auto_node"),
     str(sum(1 for x in q_again if x["kind"] == "auto_node")))
show("재인입 후에도 질의 응답 동일 (판정 무오염)",
     {i: R.answer(q["q"])["path"] for i, q in
      zip([q["id"] for q in QUERIES["queries"]], QUERIES["queries"])}
     == {i: r["path"] for i, r in results.items()})

# ============================================================ 근거 정렬 결정성
print("\n■ 근거 청크 정렬 — 결정적인가 (문서 5 §5.1-6)")
# 정렬 키 셋: ①tier(1이 앞) ②parsed_at 내림차순 ③chunk_id 사전순.
# 기준이 없으면 상한 8이 **무작위 축에서** 잘리고, 그 차이는 계기판 4에 잡히지
# 않는다 — 잘린 건수는 같고 잘린 대상만 다르기 때문이다.
_runs = [tuple(c["chunk_id"] for c in R.answer("노칭에서 발생할 수 있는 불량은?")["chunks"])
         for _ in range(5)]
show("같은 질문 5회의 근거 청크 집합·순서가 동일하다", len(set(_runs)) == 1,
     f"{len(set(_runs))}가지")
_res = R.answer("노칭에서 발생할 수 있는 불량은?")
_tiers = [c.get("tier") for c in _res["chunks"]]
show("tier1이 항상 tier2보다 앞이다 (정렬은 tier 안에서만)",
     _tiers == sorted(_tiers), str(_tiers))

# ============================================================ 관측 창구
print("\n■ 관측 창구 — 문서가 「직접 열람」이라 적은 자리에 명령이 있는가 (문서 7 §7.8)")
import subprocess as _sp2                                       # noqa: E402
def _run(*a):
    return _sp2.run([sys.executable, str(ROOT / "run.py"), *a],
                    capture_output=True, text=True, cwd=str(ROOT))

_ls = _run("show", "log")
show("show log — 로그 4종 요약이 돈다", _ls.returncode == 0
     and all(k in _ls.stdout for k in ("defects", "gate", "link_miss", "truncated")))
show("show log gate — 게이트 거부를 연다 (큐가 아니라 관측 신호)",
     _run("show", "log", "gate").returncode == 0)
show("show log link_miss / truncated — **두 계기판 로그를 각각** 연다",
     _run("show", "log", "link_miss").returncode == 0
     and _run("show", "log", "truncated").returncode == 0)
_se = _run("show", "extract")
show("show extract — 상태가 아니라 **내용**을 연다 (계약 B)",
     _se.returncode == 0 and "청크" in _se.stdout
     and _run("show", "extract", "PPT02").returncode == 0
     and "부착" in _run("show", "extract", "PPT02").stdout)
show("export html — 실물 파일을 낸다 (외부 CDN 없음)",
     _run("export", "html").returncode == 0
     and (ROOT / "export" / "graph.html").exists()
     and "cdn" not in (ROOT / "export" / "graph.html").read_text(
         encoding="utf-8").lower())
show("export mermaid quality — **빈 출력을 성공으로 내지 않는다**",
     _run("export", "mermaid", "quality").returncode != 0)
show("export mermaid cross — 걸침 관계를 층 구분과 함께 그린다",
     "occurs_in" in _run("export", "mermaid", "cross").stdout)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G4 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
