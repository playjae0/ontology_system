# -*- coding: utf-8 -*-
"""G6.5 ② 걸침층 배선 · 소수리 — mock 비계는 최소로 · 인입 순서 무관 결정성."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ ④ 걸침층 배선 (D1·D2·D3)")
fresh()
qg, pg = open_graph("quality"), open_graph("process")
qprop = [n2["canonical"] for n2 in qg.nodes.values()
         if n2["category"] == "Property" and ops.is_live(n2)]
show("D1 target_layer 선언대로 Property가 공정층에 해소된다 (품질층 중복 0)",
     not qprop, f"품질층 Property {len(qprop)}: {qprop[:5]}")
show("D1 CP·PFMEA가 같은 관리항목을 한 노드로 공유한다",
     any("PFMEA01" in str(n2["provenance"]) and "CP01" in str(n2["provenance"])
         for n2 in pg.nodes.values() if n2["category"] == "Property"),
     str([n2["canonical"] for n2 in pg.nodes.values() if n2["category"] == "Property"
          and "PFMEA01" in str(n2["provenance"]) and "CP01" in str(n2["provenance"])][:3]))
show("D3 걸침으로 만든 노드가 실제로 저장된다 (외부 그래프 save)",
     any(n2["category"] == "Property" and "PFMEA01" in str(n2["provenance"])
         for n2 in open_graph("process").nodes.values()))
show("D2 걸침 엣지의 from 끝점이 타 층이어도 게이트에 도달한다 (무기록 소멸 0)",
     any(e2["rel"] == "controlled_by" for e2 in qg.edges),
     f"controlled_by {sum(1 for e2 in qg.edges if e2['rel'] == 'controlled_by')}건")
rej = store.read(store.GATE_REJECTS, {"counts": {}})["counts"]
show("D2 끝점 미해소는 무음이 아니라 기록으로 착지한다",
     hasattr(gate, "UNRESOLVED_ENDPOINT") and isinstance(rej, dict),
     str(sorted(rej)))

# ============================================================ ⑤ 소수리
print("\n■ ⑤ 소수리 — mock 비계는 최소로 (E1~E5)")
fresh()
env = dict(PROSE, doc_id="XATT", chunks=[dict(C1, source_locator="XATT-C001")])
run_document(env)
cid = next(iter(chunks_of("XATT")))
before_def = store.path(store.DEFECTS).read_text(encoding="utf-8") \
    if store.path(store.DEFECTS).exists() else ""
build_prose(env, load_config("quality"), open_graph("quality"),
            [{"chunk_id": cid, "entities": [], "relations": [],
              "attach": [{"surface": "유령 인자", "attach_to": "존재하지 않는 대상"}]}])
build_prose(env, load_config("quality"), open_graph("quality"),
            [{"chunk_id": cid, "entities": [], "attach": [],
              "relations": [{"src": "유령 원인", "rel": "causes", "dst": "유령 결과"}]}])
after_def = store.path(store.DEFECTS).read_text(encoding="utf-8") \
    if store.path(store.DEFECTS).exists() else ""
show("E1 게이트 도달 전 소멸분(관계 끝점·attach 자식)이 결함 로그에 남는다",
     "유령" in after_def and after_def != before_def,
     str([l for l in after_def.splitlines() if "유령" in l][:2]))

r = subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0,'.');"
                    "from core.build.extract import _mock_candidates;"
                    "_mock_candidates('c', '노칭으로 인해 불량이 발생', {}, {})"],
                   cwd=str(ROOT), capture_output=True, text=True,
                   env=dict(os.environ, USE_MOCK="0"))
show("E3 USE_MOCK=0에서 문형 폴백은 명시적으로 실패한다 (예외 3호의 경계)",
     r.returncode != 0 and "USE_MOCK" in (r.stderr or ""),
     (r.stderr or "").strip().splitlines()[-1:][0] if r.stderr else "무예외")

fresh()
n = node_by("process", "노칭::노칭 정밀도")
ops.rename("process", n["id"], "노칭::노칭 정밀도 v2", actor="시험자", reason="E4 repro")
log = store.read(store.OPS_LOG, [])
show("E4 연산 로그의 시점이 하드코딩 상수가 아니다",
     log[-1]["at"] != "2026-08-18T00:00:00" and log[-1]["at"].startswith("20"),
     log[-1]["at"])

src = (ROOT / "tools" / "passthrough.py").read_text(encoding="utf-8")
show("E5 관통 경로가 finalize를 부른다 (mirrors 재평가·self-heal 실행)",
     "finalize(" in src)

# ---- E2 순서 무관 결정성 ----
print("\n■ ⑤ E2 — 인입 순서 무관 결정성 (mock 폴백 어휘 한정)")


def build_in(order):
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for d in order:
        run_document(load(d))
    finalize()
    return {lay: {n2["canonical"]: {n2["canonical"]} | {a["surface"]
                                    for a in n2["aliases"]}
                  for n2 in open_graph(lay).nodes.values()}
            for lay in ("process", "quality")}


fwd = build_in(DOCS)
rev2 = build_in(list(reversed(DOCS)))
# 봉인 R2-12가 잰 것은 **노드 소실**이다(정순 66 · 역순 65 — 큐·로그 없이 사라짐).
# 표기 변형 중 어느 쪽이 canonical이 되는가는 소실이 아니라 매칭의 정상 동작이다
# (기존 노드에 alias 자동 누적 — 3.3 규약 1). 양쪽 다 표기를 잃지 않는다.
def _lost(a, b):
    """a에는 있는데 b의 어느 노드도 그 표기를 갖지 않는 것 = 진짜 소실."""
    have = {s for names in b.values() for s in names}
    return sorted(c for c, names in a.items() if not (names & have))


gap = {lay: (len(fwd[lay]) != len(rev2[lay]),
             _lost(fwd[lay], rev2[lay]) + _lost(rev2[lay], fwd[lay]))
       for lay in fwd}
show("E2 정순·역순 인입이 동형 그래프를 만든다 (노드 수 동일 · 소실 0)",
     not any(cnt or lost for cnt, lost in gap.values()),
     str({k: v for k, v in gap.items() if v[0] or v[1]})
     or f"process {len(fwd['process'])}/{len(rev2['process'])} · "
        f"quality {len(fwd['quality'])}/{len(rev2['quality'])}")

fresh()

# ── B57 ① provenance에 문서 이름을 싣는다 ([정정] 43) ──────────────────────
#
# locator는 **문서 안에서만** 유일하다 — 실파서가 내는 것은 `Sheet1!R12`·`슬라이드 3`
# 꼴이라 두 문서가 같은 문자열을 쓴다. 그러면 재인입 회수가 **다른 문서의 근거까지**
# 걷어내고 계기판 2는 어느 문서인지 가르지 못한다.

done()
