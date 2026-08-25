# -*- coding: utf-8 -*-
"""G5 완료판정 — S4(증분0 §4.3 I-1~I-6) + 기존 단위 5 판정(계기판 제외 — 4′로 이관).

  I-1 병합 · I-2 개명 연쇄 · I-3 분리 배분표 · I-4 폐기 전이 · I-5 순환 거부 · I-6 로그
  + 단위 5: 파급 미리보기 · 엣지 삭제 enforcement · alias 이관 · 재인입 왕복

사용: python tests/test_g5.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import query as R                              # noqa: E402
from core import init, ops, registry, store                    # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph  # noqa: E402
from core.extract import EXTRACT_DIR                    # noqa: E402
from core.ids import norm                               # noqa: E402
from router import discover                            # noqa: E402
from core.pipeline import finalize, run_document        # noqa: E402

allok = True
DOCS = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
ACTOR = "tester"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / "parsed" / name).read_text(encoding="utf-8"))


def full_run():
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for d in DOCS:
        run_document(load(f"{d}.json"))
    finalize()


def nid_of(canonical, layer="process"):
    """**툼스톤은 건너뛴다** — 툼스톤도 canonical을 지니므로 옛 이름이 산 노드를 가린다."""
    g = open_graph(layer)
    return next((n["id"] for n in g.nodes.values()
                 if n["canonical"] == canonical and ops.is_live(n)), None)


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
        return None
    except ops.OpRefused as e:
        return str(e)


full_run()

# ============================================================ I-1 병합
print("\n■ I-1 병합 (I2) — 정보 손실 0 · 툼스톤 리다이렉트")
g = open_graph("process")
주액기 = nid_of("주액기")
# 상대 노드는 시나리오가 요구하는 "신규 창작 노드"다 — 같은 실물의 다른 표기.
새 = g.add_node("주액 설비", "Unit", "auto", provenance=["창작:I-1"],
                aliases=[{"surface": "주액장치", "provenance": ["창작:I-1"]}],
                polarity="none", mirror_scope=None, mirror_name=norm("주액 설비"))
g.save()
d = store.read(store.DICTIONARY, {})
d.setdefault(norm("주액 설비"), []).append(새)
d.setdefault(norm("주액장치"), []).append(새)
store.write(store.DICTIONARY, d)

pv = ops.merge("process", 주액기, 새, ACTOR, dry_run=True)
show("실행 전 파급 미리보기 (영향 노드·엣지 수 — 카드 G6)",
     pv["nodes"] >= 1 and "edges" in pv, f"노드 {pv['nodes']} · 엣지 {pv['edges']}")
show("canonical 후보가 빈도·출처 등급과 함께 제시된다 (L7 — 자동 확정 아님)",
     len(pv["canonical_candidates"]) >= 3
     and all({"canonical", "freq", "status"} <= set(c) for c in pv["canonical_candidates"]),
     str([c["canonical"] for c in pv["canonical_candidates"]][:4]))

before_prov = set(g.get(주액기)["provenance"]) | set(g.get(새)["provenance"])
ops.merge("process", 주액기, 새, ACTOR, canonical="주액기", reason="같은 설비의 다른 표기")
g = open_graph("process")
keep = 주액기 if g.get(주액기).get("status") != ops.STATUS_MERGED else 새
gone = 새 if keep == 주액기 else 주액기
show("생존자 = 정렬상 앞선 id (status 동급이면 3순위)", keep == min(주액기, 새), keep[:8])
show("provenance 전량 이관 (정보 손실 0)",
     before_prov <= set(g.get(keep)["provenance"]))
show("흡수 표기가 alias로 남는다 (선택 안 된 표기도 잃지 않는다)",
     {"주액 설비", "주액장치"} <= {a["surface"] for a in g.get(keep)["aliases"]},
     str(sorted(a["surface"] for a in g.get(keep)["aliases"])))
show("흡수 id에는 merged_into 툼스톤만 (삭제 아님)",
     g.get(gone).get(ops.STATUS_MERGED) == keep and not g.get(gone)["aliases"])
d = store.read(store.DICTIONARY, {})
show("사전 리다이렉트 — 흡수 표기 조회가 생존자를 가리킨다",
     d.get(norm("주액 설비")) == [keep] and gone not in sum(d.values(), []))
show("canonical은 사람 확정 (후보 제시와 분리 — L7)",
     g.get(keep)["canonical"] == "주액기")

# ============================================================ I-2 개명 연쇄
print("\n■ I-2 개명 (I1) — id 불변 · 옛 이름 alias 강등 · 스코프 자식 연쇄")
스태킹 = nid_of("스태킹")
pv = ops.rename("process", 스태킹, "스태킹(개선)", ACTOR, dry_run=True)
show("미리보기에 canonical 연쇄 대상 목록이 실린다",
     any("적층 정렬도" in c for c in pv["canonical_chain"]),
     f"{len(pv['canonical_chain'])}건 · {pv['canonical_chain'][:2]}")
ops.rename("process", 스태킹, "스태킹(개선)", ACTOR, reason="개선안 반영")
g = open_graph("process")
show("id 불변 (P4)", g.get(스태킹) is not None
     and g.get(스태킹)["canonical"] == "스태킹(개선)")
show("옛 canonical이 alias로 자동 강등",
     "스태킹" in {a["surface"] for a in g.get(스태킹)["aliases"]})
show("스코프 자식 canonical 연쇄 변경",
     any(n["canonical"] == "스태킹(개선)::적층 정렬도" for n in g.nodes.values())
     and not any(n["canonical"] == "스태킹::적층 정렬도" for n in g.nodes.values()))
show("옛 이름으로도 계속 찾힌다 (재매칭이 깨지지 않는다)",
     스태킹 in store.read(store.DICTIONARY, {}).get(norm("스태킹"), []))

# ============================================================ I-3 분리
print("\n■ I-3 분리 (I3) — 배분표 필수 · 잔여 있으면 거부")
tgt = keep                                              # I-1의 결과 노드를 가른다
g = open_graph("process")
node = g.get(tgt)
own_edges = [i for i, e in enumerate(g.edges) if e["src"] == tgt or e["dst"] == tgt]
show("배분표 없이는 거부 (자동 분리 경로 없음 — L5)",
     "배분표가 없다" in (refused(ops.split, "process", tgt, None, ACTOR) or ""))
half = {"targets": [{"canonical": "주액기", "aliases": ["주액장치"],
                     "provenance": node["provenance"][:1], "edges": own_edges}]}
show("잔여가 있으면 실행 거부 + 잔여 목록 출력 (조용한 유실 금지)",
     "잔여" in (refused(ops.split, "process", tgt, half, ACTOR) or ""),
     (refused(ops.split, "process", tgt, half, ACTOR) or "")[:60])
plan = {"targets": [
    {"canonical": "주액기", "aliases": [], "provenance": node["provenance"],
     "edges": own_edges},
    {"canonical": "주액 설비", "aliases": ["주액장치"], "provenance": [], "edges": []}]}
ops.split("process", tgt, plan, ACTOR, reason="다른 실물로 판정")
g = open_graph("process")
show("배분표대로 두 노드 재구성",
     {"주액기", "주액 설비"} <= {n["canonical"] for n in g.nodes.values()
                              if n.get("status") != ops.STATUS_MERGED})
show("원본은 삭제되지 않고 툼스톤으로 남는다",
     g.get(tgt).get(ops.STATUS_MERGED) is not None)

# ============================================================ I-4 폐기
print("\n■ I-4 폐기 (I4) — 삭제 아님 · 질의가 replaced_by를 전이 추적")
old = nid_of("주액 설비")
new = nid_of("주액기")
ops.obsolete("process", old, ACTOR, replaced_by=new, reason="같은 설비의 구표기")
g = open_graph("process")
show("삭제가 아니다 — 노드는 잔존하고 status만 바뀐다",
     g.get(old) is not None and g.get(old)["status"] == ops.STATUS_OBSOLETE)
show("replaced_by·사유·시점 기록", g.get(old)["replaced_by"] == new
     and g.get(old)["obsolete_reason"] and g.get(old)["obsoleted_at"])
ans = R.answer("주액 설비 관리 방법은?")
show("질의가 replaced_by를 전이 추적하고 '(대체됨: …)'을 표기한다",
     any("대체됨" in t for t in ans["transit"]), str(ans["transit"]))
show("전이 후 답은 대체 노드로 나온다",
     any("주액기" in x for x in ans["linked"]), str(ans["linked"]))
# replaced_by 없는 폐기 — 일반 결과 제외, 직접 지명은 상태 명시
lone = g.add_node("폐기 시험 노드", "Unit", "auto", provenance=["창작:I-4"],
                  polarity="none", mirror_scope=None, mirror_name=norm("폐기 시험 노드"))
g.save()
d = store.read(store.DICTIONARY, {})
d.setdefault(norm("폐기 시험 노드"), []).append(lone)
store.write(store.DICTIONARY, d)
ops.obsolete("process", lone, ACTOR, reason="대체 없음")
ans2 = R.answer("폐기 시험 노드 관리 방법은?")
show("replaced_by 없는 폐기는 '폐기됨'을 명시해 답한다 (침묵 소실 금지)",
     "폐기된 항목" in (ans2.get("note") or "") + " ".join(ans2["transit"]),
     str(ans2.get("note")))

# ============================================================ I-5 순환 거부
print("\n■ I-5 순환 방어 2겹 (L8)")
# 툼스톤(=이미 체인 위에 있는 id)을 다시 병합 대상으로 삼는 것이 순환의 입구다.
_msg = refused(ops.merge, "process", nid_of("주액기"), tgt, ACTOR) or ""
show("체인 위의 id를 다시 병합하려 하면 쓰기 시점에 거부", "툼스톤" in _msg or "순환" in _msg,
     _msg[:60])
show("replaced_by 순환도 쓰기 시점에 거부",
     "순환" in (refused(ops.obsolete, "process", new, ACTOR, old) or ""))
show("seed끼리의 병합은 거부 (골격의 정본 경로는 I1 개명·seed 개정)",
     "seed" in (refused(ops.merge, "process", nid_of("노칭"), nid_of("탭용접"), ACTOR) or ""))
show("행위자 미지정은 거부 (로그 5요소)",
     "행위자" in (refused(ops.rename, "process", nid_of("노칭"), "X", None) or ""))
show("읽기 추적은 방문집합·깊이 제한을 갖는다 (조용히 멈추지 않는다)",
     ops.MAX_CHAIN > 0 and ops.resolve_chain(open_graph("process"), tgt,
                                             ops.STATUS_MERGED) != tgt)

# ============================================================ I-6 로그
print("\n■ I-6 연산 로그 (data/ops_log.json — 큐가 아니라 로그다)")
log = store.read(store.OPS_LOG, [])
show("전 연산이 로그에 남는다 (5건 이상)", len(log) >= 5, f"{len(log)}건")
show("로그 5요소 — 연산·행위자·시점·대상·사유",
     all({"op", "actor", "at", "targets", "reason"} <= set(x) for x in log))
show("행위자가 전부 기록됨", all(x["actor"] == ACTOR for x in log))
show("4연산이 전부 로그에 등장",
     {"I1:rename", "I2:merge", "I3:split", "I4:obsolete"}
     <= {x["op"] for x in log}, str(sorted({x["op"] for x in log})))
show("큐 kind는 늘지 않았다 (I축은 로그이지 큐가 아니다 — 닫힌 20종)",
     "ops" not in {x["kind"] for x in store.read(store.QUEUE, [])})

# ============================================================ 단위 5 — 엣지 삭제
print("\n■ 단위 5 — 엣지 삭제 enforcement · 재인입 왕복")
g = open_graph("process")
e0 = next(e for e in g.edges if e["rel"] == "has_property"
          and e.get("status") != "deleted_by_user")
ops.delete_edge("process", e0["src"], e0["rel"], e0["dst"], ACTOR, "오연결")
g = open_graph("process")
show("삭제한 엣지는 툼스톤으로 남는다 (deleted_by_user)",
     any((e["src"], e["rel"], e["dst"]) == (e0["src"], e0["rel"], e0["dst"])
         and e["status"] == "deleted_by_user" for e in g.edges))
for d_ in DOCS:
    run_document(load(f"{d_}.json"))
finalize()
g = open_graph("process")
show("재인입이 사람의 삭제를 되살리지 못한다 (enforcement)",
     all(e["status"] == "deleted_by_user" for e in g.edges
         if (e["src"], e["rel"], e["dst"]) == (e0["src"], e0["rel"], e0["dst"])))

# I축 연산 후 재인입 — 사전 리다이렉트가 중복 부활을 막는가
live = [n for n in g.nodes.values() if ops.is_live(n)]
dup = [c for c in {n["canonical"] for n in live}
       if sum(1 for n in live if n["canonical"] == c) > 1]
show("개명·병합 후 재인입해도 중복 노드가 서지 않는다 (사전 리다이렉트 실증)",
     not dup, str(dup))
show("개명된 노드가 옛 이름의 문서로 재매칭된다 (id 불변 유지)",
     open_graph("process").get(스태킹)["canonical"] == "스태킹(개선)")

# ============================================================ 운영 도구 나머지
print("\n■ 이관(스코프 변경 연쇄) — I축 4연산과 별개 작업 (문서 4 §4.7·§4.9)")
import subprocess as _sp5                                       # noqa: E402
full_run()
_g = open_graph("process")
_prop = next(i for i, n in _g.nodes.items() if n["canonical"] == "노칭::노칭 정밀도")
_newp = next(i for i, n in _g.nodes.items()
             if n.get("tier") == "sub" and "스태킹" in n["canonical"])
_before = [(_g.get(e["src"])["canonical"], e["rel"]) for e in _g.edges
           if e["dst"] == _prop and e.get("status") != "deleted_by_user"]
_pv = ops.transfer("process", _prop, _newp, "시험자", dry_run=True)
show("이관이 **파급 미리보기 대상**이다 (§4.7)",
     _pv.get("op") == "transfer" and "nodes" in _pv and "edges" in _pv, str(_pv))
ops.transfer("process", _prop, _newp, "시험자", reason="회귀")
_g2 = open_graph("process")
show("이관이 canonical 스코프를 갈아 끼운다 (소속이 주소다)",
     _g2.get(_prop)["canonical"] == "스태킹::노칭 정밀도",
     _g2.get(_prop)["canonical"])
show("옛 이름이 alias로 남는다 (문서에는 옛 이름이 계속 나온다 — I1과 같은 이유)",
     any(a["surface"] == "노칭::노칭 정밀도" for a in _g2.get(_prop)["aliases"]))
_after = [(_g2.get(e["src"])["canonical"], e["rel"]) for e in _g2.edges
          if e["dst"] == _prop and e.get("status") != "deleted_by_user"]
show("**엣지가 새 부모로 재배선된다** — 개명에는 없는 일이다",
     any(s == "스태킹" for s, _r in _after), f"{_before} → {_after}")
show("옛 소속은 툼스톤으로 남는다 (조용히 지우지 않는다)",
     any(e["dst"] == _prop and e.get("status") == "deleted_by_user" for e in _g2.edges))
_ops = store.read(store.OPS_LOG, [])
show("이관이 로그 5요소를 남긴다 (연산·행위자·시점·대상·사유)",
     any(x.get("op") == "I5:transfer" and x.get("actor") and x.get("at")
         and x.get("targets") for x in _ops))
try:
    _seed = next(i for i, n in _g2.nodes.items() if n.get("status") == "seed")
    ops.transfer("process", _seed, _newp, "시험자")
    _refused = False
except ops.OpRefused:
    _refused = True
show("seed 노드의 이관은 거부한다 (골격의 원천은 사람의 파일 — §4.9-1)", _refused)

print("\n■ 파급 ≤1이면 미리보기·--yes 생략 (문서 4 §4.7 — 게이트가 아니라 가시화)")
from cli.ops import _small                                      # noqa: E402
show("파급 계수로 판정한다 (노드·엣지 둘 다 1 이하 + 연쇄 없음)",
     _small({"nodes": 1, "edges": 1, "canonical_chain": []})
     and not _small({"nodes": 1, "edges": 5, "canonical_chain": []})
     and not _small({"nodes": 1, "edges": 1, "canonical_chain": ["x"]}))

print("\n■ 플랫폼 창구 신설 2종 (갭 spec-s7-11-85 · spec-s7-11-14)")
def _pf(*a):
    return _sp5.run([sys.executable, "-m", "cli.platform", *a],
                    capture_output=True, text=True, cwd=str(ROOT))
full_run()
_sp5.run([sys.executable, str(ROOT / "run.py"), "all"], capture_output=True, cwd=str(ROOT))
_d = _pf("dashboard")
show("platform dashboard — Q7류 집계 + 수정 도구 세트 + 등록 워크플로우 등재",
     _d.returncode == 0 and "Q7 집계" in _d.stdout
     and "수정 도구 세트" in _d.stdout and "스키마 등록 워크플로우" in _d.stdout)
_ac = _pf("accuracy")
show("platform accuracy — 판정 정확도를 **계기판 8종과 별도로** 잰다",
     _ac.returncode == 0 and "별도 측정" in _ac.stdout
     and "메커니즘 점검" in _ac.stdout)

print("\n■ role 배정 실험 · 자재 열 (갭 spec-A-201 · spec-A-103)")
_r = _sp5.run([sys.executable, str(ROOT / "run.py"), "register", "roles",
               str(ROOT / "tests/fixtures/raw/IPQC01.xlsx")],
              capture_output=True, text=True, cwd=str(ROOT))
show("register roles — 등록 **전에** 돌고 UNMAPPABLE을 먼저 뽑는다",
     _r.returncode == 0 and "UNMAPPABLE" in _r.stdout and "질문할 열" in _r.stdout)
show("실행만 하고 등록부를 건드리지 않는다",
     "등록부를 건드리지 않는다" in _r.stdout
     and "ipqc" not in set(registry.all_doc_types()))
from cli.register import MATERIAL_KEYS                          # noqa: E402
show("자재 열은 개체로 만들지 않는다 (3번째 층 후보 — 미결 R5)",
     "자재" in MATERIAL_KEYS
     and "자재" in json.dumps(load_config("process")["categories"]["Property"],
                             ensure_ascii=False))

print("\n■ 근거 없음 경로 — 인접 등록 개체 제시 (갭 spec-A-153 · impl-B-19)")
from core import query as _Q                                    # noqa: E402
from core.dictionary import Dictionary as _D                    # noqa: E402
_graphs = {l: open_graph(l) for l in discover()}
_near = _Q.nearby("용접강도 기준", _D.open(), _graphs)
show("미스 질의에 비슷한 등록 개체를 제시한다 (재질문 유도)",
     _near and any("용접 강도" in x["surface"] for x in _near),
     str([x["surface"] for x in _near]))
show("제시는 판정이 아니다 — 링킹 미스율을 오염시키지 않는다",
     all(set(x) == {"surface", "node_id", "layer", "category"} for x in _near))

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G5 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
