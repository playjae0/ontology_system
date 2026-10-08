# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **좌표 쌍 대조의 구축 자리** — 봉투의 조각 전부를 구축과 같은 해소로 대조한다 (B105 ③④).

판정은 `parser.coord_pairs.verdict` 하나이고(등록 리허설 · 좌표 단계 · 구축 공통), 해소는 구축의 것이다 —
사전 조회(`Builder.resolve_anchor` · Tier1 · 표기 모호는 보류 — 큐는 만들지 않는다) → 저해상도 사다리(하위가
비면 상위) → 극성 하강(`descend_anchor`) → `Builder.coord_verdicts`. 두 자리가 이 모듈을 부른다:

  · **좌표 단계**(인입 · 판정 전 — `scan`): 화면의 쌍 표 · `--step` 관문 — 큐를 만들지 않는다(LLM 0 · 쓰기 0)
  · **구축 말미**(`enqueue` — 표·산문·렌즈 세 길이 같이 · 되돌림 경계 안): 어긋남을 `coord_mismatch` 큐로
    (행마다 한 항목 · 확인된 쌍은 확인됨으로 — `core/state/coord_acks`)

같은 함수 · 같은 입력(봉투)이라 좌표 단계 화면의 쌍·행 수 = 그 문서 구축 큐의 쌍·행 수다.
"""
from __future__ import annotations

from core.state.bootstrap import COORD_CATEGORY
from parser import coord_pairs as CP


def scan(env, b):
    """조각마다 `{loc, prov, verdicts, both, node_pol}` — `both`는 상위·하위가 둘 다 골격에 맞았나(등록 관문의 분모와
    같은 뜻). `b`는 아무 층의 빌더(좌표 해소는 카테고리의 집에서 — `_graph_for`).

    **행에 상위가 없고 문서 좌표가 있으면 문서 좌표를 상위로** 같은 판정에 넣는다(B106 ⑤) — 하위가 문서 좌표
    노드 자신이거나 그 아래면 맞음 · 밖이면 어긋남(종류 `DOC_GROUP` — 쌍의 열쇠는 상위와 같다). 「행에 상위가
    없다」에는 **태깅이 하위에서 딴 상위**(`meta.group_from_ref` — 하위의 main 조상이라 하위와 늘 맞는다)도 든다.
    행이 가져온 상위가 있으면 그 상위로만 대조하고, 하위는 바꾸지 않는다(붙는 자리는 그대로 — 보이기만)."""
    doc_id = env.get("doc_id")
    dc = env.get("doc_coord")
    out = []
    for p in env.get("records") or env.get("chunks") or []:
        loc = p.get("source_locator")
        prov = f"{doc_id}#{loc}" if loc else doc_id
        ref_s, grp_s, et = p.get("process_ref"), p.get("process_group"), p.get("electrode_type")
        sink = []                                   # 보류는 구축의 몫이다 — 여기서는 버리는 자루
        ref, ref_g = b.resolve_anchor(ref_s or grp_s, COORD_CATEGORY, prov, defer=sink)
        ref = b.descend_anchor(ref, et, ref_g)
        own = None if (p.get("meta") or {}).get("group_from_ref") else grp_s   # 행이 가져온 상위만
        by_doc = bool(dc) and not own               # 상위 — 행의 것 먼저 · 없으면 문서 좌표(B106 ⑤)
        up = dc if by_doc else grp_s
        vs, gcs = b.coord_verdicts(up, ref, et, ref_g)
        if by_doc:
            vs = [(CP.DOC_GROUP if k == CP.GROUP else k, pr) for k, pr in vs]
        out.append({"loc": loc, "prov": prov, "verdicts": vs, "both": bool(ref and up and gcs),
                    "node_pol": (ref_g.get(ref) or {}).get("polarity") if ref else None})
    return out


def table(rows):
    """`scan` 행들 → 쌍 표(`parser.coord_pairs.tally` — 등록 관문과 같은 모양)."""
    return CP.tally([(r["loc"], r["verdicts"], r["both"]) for r in rows])


def enqueue(env, b):
    """구축 말미 — 어긋남을 `coord_mismatch` 큐로(상위 골격 밖은 싣지 않는다). 돌려주는 것은 실은 항목 수."""
    from core.state import coord_acks
    n = 0
    for r in scan(env, b):
        for kind, pair in r["verdicts"]:
            if kind == CP.OUTSIDE:
                continue
            coord_acks.enqueue(CP.reason(kind, pair, r["node_pol"]), env.get("doc_id"),
                               CP.payload(kind, pair, r["prov"], r["node_pol"]))
            n += 1
    return n
