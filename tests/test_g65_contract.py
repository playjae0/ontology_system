# -*- coding: utf-8 -*-
"""G6.5 ① 재인입·인입 검증 계약 — H1·H2 미완 공사 · 닫힌 계약 배선 · 병합 무손실."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ ① 재인입 계약 — CH3B 3.8 H1·H2의 미완 공사 (A1·A2·A3·A4·C4)")
fresh()
ch0 = len(chunks_of("CP01"))
linked0 = sum(1 for c in store.read(store.CHUNKS, {"chunks": {}})["chunks"].values()
              if c.get("linked"))
auto0 = len(q_of("auto_node"))

rev = copy.deepcopy(load("CP01"))
rev["revision"] = "R4"
rev["records"] = rev["records"][:6]                 # 12행 → 6행 개정판
run_document(rev)
finalize()

show("A1 회수 — 삭제된 행의 청크가 남지 않는다 (12 → 6)",
     len(chunks_of("CP01")) == 6, f"{ch0} → {len(chunks_of('CP01'))}")
ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
live = set(ch["chunks"])
cp_desc = [d for d in ch["describes"] if d["chunk_id"].startswith("CP01")]
show("A1 회수 — 사라진 청크를 가리키는 describes가 남지 않는다",
     all(d["chunk_id"] in live for d in ch["describes"]) and len(cp_desc) <= 6,
     f"CP01 describes {len(cp_desc)} · 유령 "
     f"{len([d for d in ch['describes'] if d['chunk_id'] not in live])}")
show("A1 회수 — 근거가 0이 된 auto 노드는 삭제가 아니라 evidence_lost 큐 (첫 발화)",
     len(q_of("evidence_lost")) >= 1, f"{len(q_of('evidence_lost'))}건")
show("A1 보존 — 살아있는 노드의 사전 엔트리는 유지된다 (③ 회수 아님)",
     node_by("process", "노칭::노칭 정밀도") is not None
     and store.read(store.DICTIONARY, {}).get(norm("노칭 프레스")))
show("A1 보존 — 미검토 작업목록(auto_node)은 재인입이 지우지 않는다",
     len(q_of("auto_node")) == auto0, f"{auto0} → {len(q_of('auto_node'))}")
fresh()
def unlinked_but_described():
    ch2 = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    has = {d["chunk_id"] for d in ch2["describes"]}
    return [cid for cid in has
            if cid in ch2["chunks"] and not ch2["chunks"][cid].get("linked")]
base_bad = len(unlinked_but_described())
for d in DOCS:
    run_document(load(d))
finalize()
show("A4 linked — 동일 내용 재인입이 관측 상태를 거짓으로 되돌리지 않는다 (R2-13)",
     len(unlinked_but_described()) == base_bad == 0,
     f"describes가 걸렸는데 linked=False: 1회 {base_bad} → 2회 "
     f"{len(unlinked_but_described())}")

# C4 — 같은 문서의 값 개정은 '교체'다. 회수가 서면 별도 코드 없이 해소된다.
fresh()
# CP01이 손대지 않는 인자를 쓴다 — 안 그러면 CP01↔XREV의 **참** 충돌을 재게 된다
SOLO = dict(CPREC, 관리항목="감사 전용 인자")
run_document(dict(TABLE, doc_id="XREV", records=[dict(SOLO, 규격="±0.1mm")]))
sc0 = len(q_of("spec_conflict", "XREV"))
run_document(dict(TABLE, doc_id="XREV", revision="R2",
                  records=[dict(SOLO, 규격="±0.5mm")]))
n = node_by("process", "노칭::감사 전용 인자")
vals = [it["value"] for it in (n["attrs"].get("spec") or [])]
show("C4 같은 문서의 값 개정이 거짓 spec_conflict를 만들지 않는다 (교체)",
     len(q_of("spec_conflict", "XREV")) == sc0 and "±0.5mm" in vals
     and "±0.1mm" not in vals, f"spec={vals} · conflict={len(q_of('spec_conflict', 'XREV'))}")

# A2 — 내용이 바뀐 재인입은 추출 체크포인트를 버린다
fresh()
base = dict(PROSE, doc_id="XQ01")
run_document(dict(base, chunks=[C1]))
c2 = dict(C1, text="금형 마모로 인해 전극 치수 불량이 발생한다.")
_r, _m, extracted = run_document(dict(base, revision="R2", chunks=[c2]))
show("A2 내용이 바뀐 재인입은 체크포인트를 무효화하고 다시 추출한다",
     extracted and "금형 마모" in checkpoint_path("XQ01").read_text(encoding="utf-8"))
_r, _m, again = run_document(dict(base, revision="R2", chunks=[c2]))
show("A2 내용이 같으면 체크포인트를 재사용한다 (P-1 유지)", not again)

# A3 — 후보성 큐의 문서 유래 항목은 재인입마다 증식하지 않는다
fresh()
before = len(q_of("direction_unverifiable", "QPPT01"))
qrev = copy.deepcopy(load("QPPT01"))
qrev["revision"] = "R2"
qrev["chunks"] = [c for c in qrev["chunks"] if not c["source_locator"].endswith("K1")]
run_document(qrev)
finalize()
after = len(q_of("direction_unverifiable", "QPPT01"))
show("A3 근거 청크가 삭제되면 그 문서발 후보성 큐가 잔존·증식하지 않는다 (R2-11)",
     after <= before, f"{before} → {after}")

# ============================================================ ② 인입 검증
print("\n■ ② 인입 검증·닫힌 계약 배선 (B1~B6)")
fresh()
e = dict(TABLE, doc_id="XUNK",
         records=[dict(CPREC, source_locator="XU-R1", 알수없는필드="이 값은 소실된다")])
run_document(e)
uf = q_of("unknown_field", "XUNK")
show("B1 스키마 밖 필드는 unknown_field 큐로 값과 함께 보존된다",
     len(uf) == 1 and "이 값은 소실된다" in json.dumps(uf[0]["payload"], ensure_ascii=False),
     str(uf[:1])[:120])
e = dict(TABLE, doc_id="XMISS",
         records=[{"source_locator": "XM-R1", "process_group": "조립",
                   "process_ref": "노칭", "electrode_type": "both", "설비": "노칭 프레스"}])
run_document(e)
show("B1 optional 미선언 필드의 부재는 missing_field 큐로 뜬다",
     any(x["payload"].get("field") == "관리항목" for x in q_of("missing_field", "XMISS")),
     str([x["payload"].get("field") for x in q_of("missing_field", "XMISS")]))

fresh()
bad = dict(TABLE, doc_id="XKIND", payload_kind="tabel", records=[dict(CPREC)])
res, _m, _x = run_document(bad)
show("B2 payload_kind 닫힌 2값 위반 → 문서 단위 미인입 + parse_failure (C14)",
     res.status == "held" and len(q_of("parse_failure", "XKIND")) == 1,
     f"status={res.status} · parse_failure={len(q_of('parse_failure', 'XKIND'))}")
show("B2 미인입 문서는 체크포인트·청크를 남기지 않는다",
     not checkpoint_path("XKIND").exists() and not chunks_of("XKIND"))

res, _m, _x = run_document(dict(PROSE, doc_id="XNEW01", doc_type="완전미등록타입",
                                chunks=[dict(C1, source_locator="XNEW01-C001")]))
show("B3 미등록 doc_type은 무음 폴백이 아니라 미인입 + parse_failure",
     res.status == "held" and len(q_of("parse_failure", "XNEW01")) == 1,
     f"status={res.status}")
show("B3 미등록 문서가 등록부에 등재되지 않는다",
     "XNEW01" not in store.read(store.DOC_REGISTRY, {}))

fresh()
env = dict(PROSE, doc_id="XCAT01", chunks=[dict(C1, source_locator="XCAT01-C001")])
run_document(env)
g = open_graph("quality")
cand = [{"chunk_id": next(iter(chunks_of("XCAT01"))), "attach": [], "relations": [],
         "entities": [{"surface": "감사표면형", "category": "발명된카테고리"}]}]
build_prose(env, load_config("quality"), g, cand)
show("B4 층 닫힌 목록 밖 카테고리는 invalid_category 큐 + 노드 미생성",
     len(q_of("invalid_category", "XCAT01")) == 1
     and not any(n["canonical"] == "감사표면형" for n in g.nodes.values()),
     str(len(q_of("invalid_category", "XCAT01"))))

core_src = "\n".join(_p.read_text(encoding="utf-8")
                      for _p in sorted((ROOT / "core" / "build").glob("*.py")))
from cli.platform import QUEUE_KINDS                          # noqa: E402
show("B5 invalid_role enqueue가 코드에서 사라진다 — 결함 로그만 (D-30 · 닫힌 20종)",
     'enqueue("invalid_role"' not in core_src and "invalid_role" not in QUEUE_KINDS
     and "invalid_role" in core_src,
     "결함 로그는 남아 있어야 한다")

fresh()
run_document(dict(TABLE, doc_id="XLIST",
                  records=[dict(CPREC, source_locator="XL-R1",
                                설비=["노칭 프레스", "보조 프레스"])]))
d = store.read(store.DICTIONARY, {})
n = node_by("process", "노칭::노칭 정밀도")
show("B6 entity 필드의 리스트 값은 드롭 + missing_field — 사전 오염 0 (D6)",
     not any("[" in k for k in d)
     and any(x["payload"].get("field") == "설비" for x in q_of("missing_field", "XLIST")),
     str([k for k in d if "[" in k])[:100])
u = node_by("process", "노칭 프레스")
show("B6 기존 노드의 alias가 리스트 객체로 오염되지 않는다",
     u is None or all(isinstance(a["surface"], str) for a in u["aliases"]))

# ============================================================ ③ 병합·값 무손실
print("\n■ ③ 병합·값의 무손실 계약 (C1·C2·C3·C5·C6)")
fresh()
# ② 물리 중복 — 같은 대상으로 affects 엣지를 각각 가진 쌍(봉인 R2-0 ②)
a = node_by("quality", "슬리팅 버")
b = node_by("quality", "버 발생")
ops.merge("quality", a["id"], b["id"], actor="시험자", reason="C2 repro ②")
g = open_graph("quality")
dup = [k for k in {(e2["src"], e2["rel"], e2["dst"]) for e2 in g.edges}
       if sum(1 for e3 in g.edges
              if (e3["src"], e3["rel"], e3["dst"]) == k) > 1]
show("C2 병합 후 (src,rel,dst) 물리 중복 0 · provenance는 합집합 (R2-0 ②)",
     not dup, f"중복 {len(dup)}건")
# ① 자기 루프 — 서로 causes 엣지를 가진 쌍(봉인 R2-0 ①)
fresh()
a = node_by("quality", "가압력 부족")
b = node_by("quality", "용접 강도 부족")
ops.merge("quality", a["id"], b["id"], actor="시험자", reason="C1·C2 repro ①")
g = open_graph("quality")
keep = node_by("quality", "용접 강도 부족") or node_by("quality", "가압력 부족")
show("C2 병합이 자기참조 엣지를 만들지 않는다 (자기 루프는 참 관계가 아니다)",
     not [e for e in g.edges if e["src"] == e["dst"]],
     str([e["rel"] for e in g.edges if e["src"] == e["dst"]]))
from cli.query import answer                                  # noqa: E402
res = answer("용접 강도 부족의 원인은?")
show("C2 질의에 자기참조 거짓 사실이 나오지 않는다",
     not any(f.count(keep["canonical"]) >= 2 for f in res["facts"]),
     str([f for f in res["facts"] if f.count(keep["canonical"]) >= 2][:1]))

# C1 — 이름이 같고 값이 다른 attr는 무음 폐기가 아니라 spec_conflict
fresh()
x = node_by("process", "노칭::노칭 정밀도")
y = node_by("process", "노칭::금형 클리어런스")
xa = copy.deepcopy(x["attrs"]); ya = copy.deepcopy(y["attrs"])
before_sc = len(q_of("spec_conflict"))
ops.merge("process", y["id"], x["id"], actor="시험자", reason="C1 repro")
keep = node_by("process", "노칭::노칭 정밀도") or node_by("process", "노칭::금형 클리어런스")
merged = keep["attrs"].get("spec") or []
vals = {it["value"] for it in merged} if isinstance(merged, list) else set()
queued = {x2["payload"].get("incoming") for x2 in q_of("spec_conflict")}
want = {it["value"] for a2 in (xa, ya) for it in (a2.get("spec") or [])}
# 계약은 "양쪽 값이 attrs에 남는다"가 아니라 **"무음으로 사라지지 않는다"**다 —
# 맥락이 다르면 병렬 저장, 같은 맥락의 충돌이면 spec_conflict 큐다(3.7 I2).
show("C1 병합이 attribute 값을 무음 폐기하지 않는다 (attrs 또는 spec_conflict)",
     want <= (vals | queued), f"기대 {sorted(want)} · attrs {sorted(vals)} · 큐 {sorted(queued)}")
show("C1 흡수측 값이 같은 맥락에서 충돌하면 spec_conflict로 뜬다",
     len(q_of("spec_conflict")) > before_sc,
     f"{before_sc} → {len(q_of('spec_conflict'))}")

# C3 — 비맥락형의 교차 출처 값 충돌
fresh()
run_document(dict(TABLE, doc_id="XATTR_A",
                  records=[dict(CPREC, source_locator="XA-R1", 측정방법="방법A")]))
run_document(dict(TABLE, doc_id="XATTR_B",
                  records=[dict(CPREC, source_locator="XB-R1", 측정방법="방법B")]))
n = node_by("process", "노칭::노칭 정밀도")
at = n["attrs"].get("측정방법")
prov = at.get("provenance") if isinstance(at, dict) else \
    [p for it in at for p in it["provenance"]]
show("C3 비맥락형 교차 출처 충돌은 spec_conflict + **기존 값 보존** (3.6 규약 5)",
     any(x2["payload"].get("attr") == "측정방법" for x2 in q_of("spec_conflict"))
     # provenance는 `{doc_id}#{locator}`다([정정] 43) — 청크 locator는 접두가 없다.
     and "CP01#C1" in prov
     and "비전 측정기" in str(at) and "방법B" not in str(at), f"{at}")

# C5 — 툼스톤은 매칭 후보가 아니다
fresh()
a = node_by("quality", "가압력 부족")
b = node_by("quality", "용접 강도 부족")
ops.merge("quality", a["id"], b["id"], actor="시험자", reason="C5 repro")
g = open_graph("quality")
tomb = next(n2 for n2 in g.nodes.values() if n2.get("merged_into"))
# 사전을 비워 ②후보 검색 경로로 보낸다 — 봉인 R2-1이 뚫은 바로 그 경로다
# 사전 접근은 관문 경유다(문서 7 §7.1) — raw dict를 넘기는 우회를 허용하면
# 관문이 강제하는 provenance 필수·키 규칙이 시험에서만 빠진다.
verdict, nid, _s, _p = resolve(tomb["canonical"] + "테스트", tomb["category"], "quality",
                               g, Dictionary({}), polarity=tomb.get("polarity"))
show("C5 후보 검색이 툼스톤에 MATCH하지 않는다 (is_live 필터 — R2-1)",
     nid != tomb["id"], f"{verdict} → {'툼스톤' if nid == tomb['id'] else '생존자/신규'}")

# C6 — 분리 리다이렉트는 배분표대로만
fresh()
a = node_by("quality", "가압력 부족")
b = node_by("quality", "용접 강도 부족")
ops.merge("quality", a["id"], b["id"], actor="시험자", reason="C6 repro 전단")
src = node_by("quality", "용접 강도 부족") or node_by("quality", "가압력 부족")
own = [i for i, e2 in enumerate(open_graph("quality").edges)
       if e2["src"] == src["id"] or e2["dst"] == src["id"]]
als = [al["surface"] for al in src["aliases"]]
# 흡수된 표기('가압력 부족')를 **두 번째** 타깃에 배분한다 — 첫 산출물이 아니다
back = [s for s in als if "가압력" in s]
plan = {"targets": [
    {"canonical": src["canonical"], "aliases": [s for s in als if s not in back],
     "provenance": list(src["provenance"]), "edges": own},
    {"canonical": "가압력 부족", "aliases": [s for s in back if s != "가압력 부족"],
     "provenance": [], "edges": []}]}
ops.split("quality", src["id"], plan, actor="시험자", reason="C6 repro")
d = store.read(store.DICTIONARY, {})
multi = {s: ids for s, ids in d.items()
         if s in {norm(t2["canonical"]) for t2 in plan["targets"]} and len(ids) > 1}
show("C6 분리 후 한 표기는 한 산출물만 가리킨다 (사전 오염 0 — R2-14)",
     not multi, str(multi))

# ============================================================ ④ 걸침층

done()
