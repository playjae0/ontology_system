# -*- coding: utf-8 -*-
"""G3 완료판정 — 정지점 3의 어서션을 실행 가능한 검사로.

  1c′·1d′ : 기존 1c·1d 판정 전 항목의 계약 v2 재통과 + coord_mismatch 1건(C11)
  n3      : S2(추출) + S13(attach 청크 밖 해소) + 구축 2회 재실행 시 추출 미재호출
  n4      : S3(게이트 K1~K4) + 회귀(PFMEA causes·affects·occurs_in·controlled_by 전부 커밋)

사용: python tests/test_g3.py
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import store                                   # noqa: E402
from core.bootstrap import bootstrap, open_graph         # noqa: E402
from core.extract import EXTRACT_DIR                     # noqa: E402
from core.pipeline import run_document                   # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "mock" / "parsed" / name).read_text(encoding="utf-8"))


DOCS = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]


def full_run():
    shutil.rmtree(store.DATA, ignore_errors=True)
    shutil.rmtree(EXTRACT_DIR, ignore_errors=True)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)      # 파생 흐름 출력은 사람 대조용 — 판정은 test_g1_g2
    flags = {}
    for d in DOCS:
        _, _, extracted = run_document(load(f"{d}.json"))
        flags[d] = extracted
    return flags


def q(kind):
    return [x for x in store.read(store.QUEUE, []) if x["kind"] == kind]


def canon(g):
    return {n["canonical"] for n in g.nodes.values()}


flags = full_run()
P = open_graph("process")
Q = open_graph("quality")

# ============================================================ 1c′ (정형·공정층)
print("\n■ 1c′ — 정형 인입 (계약 v2 정합)")
show("Unit 노드 생성", any(n["category"] == "Unit" for n in P.nodes.values()))
show("Property 노드 생성", any(n["category"] == "Property" for n in P.nodes.values()))
rel = Counter(e["rel"] for e in P.edges)
show("has_property 엣지 생성", rel["has_property"] > 0, str(rel["has_property"]))
show("part_of 엣지 생성 (설비→세부공정)", rel["part_of"] > 7, str(rel["part_of"]))

show("C4 spec_conflict 1건 (같은 context 그룹, 다른 값)",
     len(q("spec_conflict")) == 1, str([x["reason"] for x in q("spec_conflict")]))
alig = [n for n in P.nodes.values() if n["canonical"].endswith("적층 정렬도")]
specs = alig[0]["attrs"]["spec"] if alig else []
show("C7 병렬 항목 (context 상이 → 충돌 아님)",
     len(specs) == 2 and {json.dumps(s["context"], sort_keys=True) for s in specs}
     == {'{"model": "M1"}', '{"model": "M2"}'},
     str([s["context"] for s in specs]))

show("C8·C9 극성 결합 canonical 2노드",
     {"cathode 노칭 프레스", "anode 노칭 프레스"} <= canon(P))
show("mirrors 엣지 생성", rel["mirrors"] > 0, str(rel["mirrors"]))
# 짝은 **polarity 필드**로 찾는다(F3 — 문자열 파싱 폐지). 스코프가 붙은 관리항목의
# 짝도 찾아야 하며, 못 찾으면 정상 쌍이 비대칭 큐로 새어 나간다.
show("C10 mirror_asymmetry 참 양성 (anode 쪽에만 '버 높이')",
     "노칭::버 높이" in [x["payload"]["base"] for x in q("mirror_asymmetry")],
     str([x["payload"]["base"] for x in q("mirror_asymmetry")]))
# ⚠ **알려진 오검출 2건** — BLOCKERS 판정필요-5. A11-9 ①로 부착된 노드는 극성이
# 이름이 아니라 **주소**에 있는데, mirrors 짝 키(base_canonical)에는 그 주소가
# 그대로 들어간다. `탭용접::cathode::용접 강도`의 짝은 `탭용접::anode::…`이므로
# 키가 달라 **둘 다 있어도 절대 페어링되지 않는다** — F3의 "부모가 mirror 쌍이면
# 하향 연쇄" 절이 미구현이다. Unit은 스코프 자체가 없어 같은 뿌리에서 갈린다.
# 고치려면 core에 새 분기가 필요하므로 **잠그고 판정을 기다린다**(고치지 않는다).
_MA_KNOWN = ["노칭::버 높이", "초음파 융착기", "탭용접::cathode::용접 강도"]
show("mirror_asymmetry 오검출 2건이 현행 그대로 (조용히 바뀌면 잡힌다 — 판정필요-5)",
     sorted(x["payload"]["base"] for x in q("mirror_asymmetry")) == sorted(_MA_KNOWN),
     str(sorted(x["payload"]["base"] for x in q("mirror_asymmetry"))))
show("스코프 붙은 관리항목의 극성 쌍도 페어링 (구 strip 방식이 놓치던 자리)",
     any(e["rel"] == "mirrors"
         and P.get(e["src"])["canonical"] == "노칭::cathode 노칭 정밀도"
         and P.get(e["dst"])["canonical"] == "노칭::anode 노칭 정밀도"
         for e in P.edges))
show("Tier1(seed) 골격은 mirror_asymmetry 대상이 아님 (A11-4)",
     not any(P.get(x["payload"]["node_id"])["status"] == "seed"
             for x in q("mirror_asymmetry")))

# ★ M2 — D5(극성 모호)는 **구조적으로 소멸**했다(A11-6). "탭용접"은 개념 노드가
# 극성 무관 alias를 단독 소유하므로 모호하지 않고 **저해상도 부착**된다.
show("C5′ 개념 해상도 anchor('탭용접') → 개념 노드에 부착 (저해상도 부착)",
     any(n["canonical"] == "탭용접::용접 가압력" for n in P.nodes.values()))
show("C5′ 극성 모호 orphan_anchor 0건 (D5 구조 소멸)",
     not any("모호" in x["reason"] for x in q("orphan_anchor")),
     str([x["reason"] for x in q("orphan_anchor")]))
show("orphan_anchor는 '목록 밖 이름'만 남음 (레이저노칭·셀 부풀음)",
     {"레이저노칭", "셀 부풀음"}
     == {x["payload"]["surface"] for x in q("orphan_anchor")},
     str(sorted({x["payload"]["surface"] for x in q("orphan_anchor")})))

# ★ M2 — 부착 정합 (A11-9)
show("A11-9 ① 부착 노드 polarity≠none이면 표면형 극성 결합 생략 (이중 표기 방지)",
     "탭용접::cathode::용접 가압력" in canon(P)
     and not any("cathode::cathode" in c or "::cathode 용접" in c for c in canon(P)))
show("A11-9 ① polarity는 부착 노드에서 상속해 기록",
     next(n for n in P.nodes.values()
          if n["canonical"] == "탭용접::cathode::용접 가압력")["polarity"] == "cathode")
show("polarity가 닫힌 4값 밖으로 새지 않음 (cathode/anode/none/unbound)",
     {n.get("polarity") for n in list(P.nodes.values()) + list(Q.nodes.values())}
     <= {"cathode", "anode", "none", "unbound"},
     str(sorted({str(n.get("polarity"))
                 for n in list(P.nodes.values()) + list(Q.nodes.values())})))
show("D-43 — electrode_type은 노드에 기록되지 않는다 (구조 필드 · polarity가 파생 필드)",
     not any("electrode_type" in n for n in
             list(P.nodes.values()) + list(Q.nodes.values())))

# ★ G3 신규 — C11(좌표축) · C12(극성축). 같은 계열의 공짜 검증 둘이다.
cm = q("coord_mismatch")
show("**C11 coord_mismatch** (스태킹/노칭 — 실존하되 조상 아님)",
     any(x["payload"].get("process_group") == "스태킹" for x in cm),
     str([x["reason"] for x in cm]))
show("**C12 coord_mismatch — A11-9 ②** (좌표 극성 cathode ↔ record 극성 anode)",
     any(x["payload"].get("node_polarity") == "cathode"
         and x["payload"].get("electrode_type") == "anode" for x in cm),
     str([x["payload"] for x in cm if "node_polarity" in x["payload"]]))
show("coord_mismatch 2건 · orphan_anchor로 새지 않음 (골격 밖과 구분)",
     len(cm) == 2 and all("스태킹" not in x["reason"] for x in q("orphan_anchor")),
     str(len(cm)))

show("Property canonical이 세부공정 스코프", any("::" in c for c in canon(P)),
     str([c for c in canon(P) if "::" in c][:1]))

# ============================================================ 1d′ (비정형)
print("\n■ 1d′ — 비정형 인입")
ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
p5 = [c for c in ch["chunks"].values()
      if c["doc_id"] == "PPT01" and c["source_locator"] == "PPT01-C005"]
show("P5 linked=false 보존 (개체 없는 청크도 버리지 않는다)",
     p5 and p5[0]["linked"] is False)
show("P6 신규 entity auto 생성 + 큐 ('주액기')",
     any(n["canonical"] == "주액기" and n["status"] == "auto"
         for n in P.nodes.values()) and len(q("auto_node")) > 0)
show("describes 연결 생성", len(ch["describes"]) > 0, f"{len(ch['describes'])}건")

# ============================================================ n3
print("\n■ n3 — 추출 단계 분리 + 체크포인트 (CH3A 3.11)")
ck = json.loads((EXTRACT_DIR / "QPPT01.json").read_text(encoding="utf-8"))
show("S2 — extract/{doc_id}.json 생성", ck["doc_id"] == "QPPT01")
show("S2 — 3.11 스키마 그대로 (표면형만·노드 id 없음)",
     all("id" not in e and "surface" in e
         for c in ck["candidates"] for e in c["entities"]))
show("S2 — confidence 필드 없음",
     not any("confidence" in e for c in ck["candidates"] for e in c["entities"]))
show("S2 — span·오프셋 필드 없음",
     not any(k in e for c in ck["candidates"] for e in c["entities"]
             for k in ("span", "offset", "start", "end")))
show("S2 — 재현성 3입력 기록 (adapter·prompt·config_version)",
     all(ck.get(k) for k in ("adapter_version", "prompt_version", "config_version")),
     f"{ck['adapter_version']} / {ck['prompt_version']} / {ck['config_version']}")
show("S2 — 관계 후보 출력 (K1 causes)",
     any(r["rel"] == "causes" for c in ck["candidates"] for r in c["relations"]))

# S13 — attach 청크 밖 해소
show("S13 — orphan_attach 0건", len(q("orphan_attach")) == 0,
     str([x["reason"] for x in q("orphan_attach")]))
nozzle = [n for n in P.nodes.values() if "노즐 세척 주기" in n["canonical"]]
juaek = [nid for nid, n in P.nodes.items() if n["canonical"] == "주액기"]
show("S13 — attach가 다른 청크(L1)의 개체로 붙어 has_property 생성",
     nozzle and juaek and any(
         e["src"] == juaek[0] and e["rel"] == "has_property"
         and e["dst"] == [nid for nid, n in P.nodes.items()
                          if n is nozzle[0]][0] for e in P.edges))

# 체크포인트 재사용
before = (EXTRACT_DIR / "QPPT01.json").read_text(encoding="utf-8")
_, _, again = run_document(load("QPPT01.json"))
show("구축 2회 재실행 시 추출이 재호출되지 않음 (체크포인트)", again is False)
show("체크포인트 내용 불변",
     (EXTRACT_DIR / "QPPT01.json").read_text(encoding="utf-8") == before)

# ============================================================ n4
print("\n■ n4 — 커밋 게이트 (CH3A 3.4)")
du = q("direction_unverifiable")
dc = q("direction_conflict")
# 경로 ②(PFMEA 정형 edges)의 causes는 **커밋되는 것이 정상**이다 — 아래 회귀가 그것을
# 확인한다. 여기서 막혀야 하는 것은 경로 ③(QPPT01 추출 후보)뿐이므로 provenance로 가른다.
extract_causes = [e for e in Q.edges if e["rel"] == "causes"
                  and any(str(pv).startswith("QPPT01") for pv in e["provenance"])]
show("S3 — K1(동종 쌍 causes, 경로 ③) → direction_unverifiable, 커밋 0",
     len(du) >= 1 and not extract_causes,
     str([x["payload"]["src_canonical"] + "→" + x["payload"]["dst_canonical"]
          for x in du]))
show("S3 — direction_unverifiable에 근거 청크 동봉",
     du and du[0]["payload"].get("evidence_chunk"))
show("S3 — K2(이종 쌍 affects) → 커밋",
     any(e["rel"] == "affects" for e in Q.edges))
show("S3 — K3(방향만 반대) → direction_conflict, 자동 반전 없음", len(dc) >= 1,
     str([x["payload"]["src_canonical"] + "→" + x["payload"]["dst_canonical"]
          for x in dc]))
k4 = [c for c in ck["candidates"] if c["chunk_id"].startswith("QPPT01")
      and not c["relations"]]
show("S3 — K4(관계 없는 서술) → 후보 0 (과추출 없음)", len(k4) >= 1)

gr = store.read(store.GATE_REJECTS, {"rejects": [], "counts": {}})
show("gate_rejects.json이 큐가 아니라 로그 (사유별 건수)",
     "counts" in gr and not any(x["kind"] in ("invalid_pattern", "undeclared_relation")
                                for x in store.read(store.QUEUE, [])))

# 회귀 — 경로 ②는 무비용 통과
qrel = Counter(e["rel"] for e in Q.edges)
show("회귀 — PFMEA causes 커밋 (정형 edges의 동종 쌍은 통과)",
     qrel["causes"] > 0, str(qrel["causes"]))
show("회귀 — PFMEA affects 커밋", qrel["affects"] > 0, str(qrel["affects"]))
show("회귀 — PFMEA occurs_in 커밋 (층간 브리지)", qrel["occurs_in"] > 0,
     str(qrel["occurs_in"]))
show("회귀 — PFMEA controlled_by 커밋", qrel["controlled_by"] > 0,
     str(qrel["controlled_by"]))

# ============================================================ 기타 계약
print("\n■ 계약 준수")
show("registry에 builtin 층은 여전히 1개",
     sum(1 for v in store.read(store.REGISTRY, {}).values()
         if v["status"] == "builtin") == 1)
show("D-30 — invalid_role 결함 로그 경로 존재 (KeyError로 죽지 않음)",
     hasattr(store, "append_defect"))
# 주석·독스트링의 언급은 소비가 아니다. **읽는 문법**이 있는지를 본다.
import re as _re
_ACCESS = _re.compile(r"""(\[["']classification["']\]|get\(["']classification["']\)"""
                      r"""|\.classification\b)""")
_reads = [f"{p.name}:{i}" for p in (ROOT / "core").glob("*.py")
          for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
          if _ACCESS.search(ln)]
show("D-37 — classification을 **읽는** 코드 0지점 (자리만 인정, 소비 로직 없음)",
     not _reads, str(_reads))
show("D-37 — 노드에 등급 필드 없음",
     not any("classification" in n for n in
             list(P.nodes.values()) + list(Q.nodes.values())))

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G3 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
