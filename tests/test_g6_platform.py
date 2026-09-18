# -*- coding: utf-8 -*-
"""G6 ① 플랫폼 창구 — subprocess build/query · 2층+cross 표시 · 큐 열람 · 계기판 8종."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ 4′ — 기존 단위 4: subprocess build/query · 2층+cross 표시 · 큐 열람")
init.init(fresh_=True)              # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)

r = PF.call(["all"])                        # 플랫폼→파이프라인 결합은 subprocess뿐(§16.1)
show("플랫폼이 build를 subprocess로 호출 (파일 계약 — 코드 의존 0)",
     r.returncode == 0 and "[bootstrap]" in r.stdout)
r = PF.call(["query", "노칭 다음 공정은?", "--allow-mock"])   # 회귀는 관문 비대상(B48)
show("플랫폼이 query를 subprocess로 호출", r.returncode == 0
     and "노칭 다음 공정은 스태킹이다" in r.stdout)

gv = PF.graph_view()
show("2층 표시 — process·quality 양 층의 노드·엣지 계수",
     set(gv["layers"]) == {"process", "quality"}
     and all(s["nodes"] > 0 and s["edges"] for s in gv["layers"].values()),
     str({k: v["nodes"] for k, v in gv["layers"].items()}))
show("cross-layer 표시 — 걸침 엣지가 양 층 canonical로 문장화됨",
     len(gv["cross"]) >= 1 and any("occurs_in" in c for c in gv["cross"]),
     f"{len(gv['cross'])}건")

qv = PF.queue_view()
show("큐 열람 — 전 항목 kind·reason·doc_id 열람 가능",
     qv["total"] == len(qv["items"]) and all("kind" in x for x in qv["items"]),
     f"{qv['total']}건")

# ============================================================ 4′ 신규 노출
print("\n■ 4′ — 신규 산출물 노출 (증분0 §3 G6 + 허브 추가 지시)")
show("큐 kind 닫힌 20종이 전부 열람에 뜬다 — 0건 kind 포함 (D-54)",
     len(PF.QUEUE_KINDS) == 20 and set(qv["kinds"]) == set(PF.QUEUE_KINDS))
show("목록 밖 kind 0 — 실물 큐가 닫힌 목록 안", not qv["alien"], str(qv["alien"]))
fired = {k for k, n in qv["kinds"].items() if n}
show("G3~G5 발화 kind가 열람에 뜬다 (coord_mismatch·direction_*·mirror_asymmetry)",
     {"coord_mismatch", "direction_unverifiable", "direction_conflict",
      "mirror_asymmetry", "auto_node", "spec_conflict", "orphan_anchor"} <= fired,
     str(sorted(fired)))

ev = PF.extract_view()
show("추출 상태 — 파일 존재 = 추출 완료 (prose 4건 완료 · table 2건 경로 아님)",
     [d for d, done in ev.items() if done] == ["PPT01", "PPT02", "PPT03", "QPPT01"]
     and not ev["CP01"] and not ev["PFMEA01"], str(ev))

reg = store.read(store.REGISTRY, {})
show("등록부 조회 — builtin 1층 + registered 1층 (J10)",
     reg["process"]["status"] == "builtin" and reg["quality"]["status"] == "registered")

# ops_log 노출 — 실물로 실증한다: I축 연산 1건을 돌리고 열람에 뜨는지 본다
g = open_graph("process")
# [B26] Unit이 스코프 카테고리가 되어 auto 노드에 좌표 접두가 붙는다.
# **이름 전문을 박지 않는다** — 끝이름으로 찾아 접두 변화에 흔들리지 않게 한다.
nid = next(i for i, n in g.nodes.items()
           if ops.is_live(n) and n["canonical"].split("::")[-1] == "주액기"
           and n["status"] == "auto")
ops.rename("process", nid, "주액 설비 (G6 노출 검증)", actor="시험자", reason="4′ 노출 실증")
ov = PF.ops_view()
show("ops_log 열람 — I축 연산 이력이 5요소로 뜬다",
     len(ov["log"]) >= 1 and {"op", "actor", "at", "targets", "reason"}
     <= set(ov["log"][-1]), str(ov["log"][-1].get("op")))
show("툼스톤 계수 — merged_into·obsolete 층별 계수 노출",
     set(ov["tombstones"]) == {"process", "quality"}
     and all({"merged_into", "obsolete"} <= set(t) for t in ov["tombstones"].values()),
     str(ov["tombstones"]))
ops.rename("process", nid, "주액기", actor="시험자", reason="원복")

# ============================================================ 계기판 8종
print("\n■ 계기판 8종 (CH5 5.5 — 별도 호출 · 관측 무오염)")
before = data_hash()
m = PF.gauges()
after = data_hash()
show("계기판이 data/를 바꾸지 않는다 (관측이지 쓰기가 아니다 — 해시 대조)",
     before == after, str([k for k in before if before[k] != after.get(k)]))
show("8종 전부 출력 — 1~6 품질 지표 + 7 저장 크기 + 8 build 시간",
     all(k in m for k in ["1_linking_recall", "2_plateau", "3_hold_rate",
                          "4_truncation_rate", "5_miss_rate", "6_hub_degree",
                          "7_graph_size", "8_build_seconds"]))
show("1 링킹 recall — 스모크 12문항 기준 실측값",
     m["1_linking_recall"]["value"] is not None
     and m["1_linking_recall"]["expected_linkable"] > 0,
     str(m["1_linking_recall"]["value"]))
show("2 plateau — 문서별 신규 개체율이 인입 순서대로 나온다 (마지막 문서 수렴)",
     [p["doc"] for p in m["2_plateau"]["series"]] == list(store.read(store.DOC_REGISTRY, {}))
     and m["2_plateau"]["series"][-1]["rate"] == 0.0,
     str([p["rate"] for p in m["2_plateau"]["series"]]))
show("3 판정 보류율 — 큐 ÷ 조각 실측", m["3_hold_rate"]["value"] is not None
     and m["3_hold_rate"]["queue"] == qv["total"], str(m["3_hold_rate"]))
show("5 링킹 미스율 — 무근거 문항(Q12)이 미스로 잡힌다",
     any("리튬이온" in s for s in m["5_miss_rate"]["missed"]),
     str(m["5_miss_rate"]["value"]))
show("6 허브 차수 — 층별 상위 노드와 차수 (J9 폭증 조기 관측)",
     all(len(v) >= 1 and v[0]["degree"] >= v[-1]["degree"]
         for v in m["6_hub_degree"].values()),
     str({k: v[0] for k, v in m["6_hub_degree"].items()}))
show("7·8 — 실측값 + 알람선(200MB/30초) 대비, 현재 알람 없음",
     all(not s["over_alarm"] for s in m["7_graph_size"].values())
     and all(not s["over_alarm"] for s in m["8_build_seconds"].values()),
     str({k: f"{v['mb']}MB" for k, v in m["7_graph_size"].items()}))

# ============================================================ S11

done()
