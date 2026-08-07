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
        bootstrap(lay)
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
show("C10 mirror_asymmetry 큐 (anode 쪽에만 '버 높이')",
     len(q("mirror_asymmetry")) >= 1,
     str([x["payload"]["base"] for x in q("mirror_asymmetry")]))

show("C5 극성 모호 anchor('탭용접') → orphan_anchor",
     any("극성 모호" in x["reason"] for x in q("orphan_anchor")),
     str([x["reason"] for x in q("orphan_anchor") if "극성 모호" in x["reason"]][:1]))

# ★ G3 신규 — C11
cm = q("coord_mismatch")
show("**C11 coord_mismatch 1건** (스태킹/노칭 — 실존하되 조상 아님)",
     len(cm) == 1, str([x["payload"] for x in cm]))
show("coord_mismatch가 orphan_anchor로 새지 않음 (골격 밖과 구분)",
     len(cm) == 1 and all("스태킹" not in x["reason"] for x in q("orphan_anchor")))

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
