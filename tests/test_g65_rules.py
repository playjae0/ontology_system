# -*- coding: utf-8 -*-
"""G6.5 ④ 규칙과 계측 — 반대 방향은 연달아 적용하지 않는다 · 빌드 소요 · 재등록 승인 누적."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done
from cli.query import answer as R_answer   # noqa: E402
from core.build import entry as pipeline_mod   # noqa: E402
from cli.platform import gauges   # noqa: E402    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ B57 ③ — 방향이 반대인 규칙은 연달아 적용하지 않는다 ([개정] B56-3)")

fresh()
_b57_g = open_graph("process")
_b57_cfg = load_config("process")
_b57_spec = _b57_cfg.get("query_traverse") or {}
_b57_nid = next(i for i, n in _b57_g.nodes.items() if n["canonical"] == "노칭")
_b57_after = _b57_g.neighbors([_b57_nid], _b57_spec)


def _b57_old_neighbors(g, ids, spec):
    """구판 가드 — 프론티어가 **관계만** 들고 다닌다(방향 없음)."""
    seen = set(ids)
    fr = [(i, None) for i in ids]
    while fr:
        nxt = []
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            for sp in (spec.get(e["rel"]) or {}).values():
                d, rec = sp.get("direction", "both"), sp.get("recursive", False)
                for n, via in fr:
                    if not rec and via == e["rel"]:
                        continue
                    h = None
                    if d in ("out", "both") and e["src"] == n:
                        h = e["dst"]
                    elif d in ("in", "both") and e["dst"] == n:
                        h = e["src"]
                    if h is None or h in seen:
                        continue
                    seen.add(h)
                    nxt.append((h, e["rel"]))
        fr = nxt
    return seen


_b57_before = _b57_old_neighbors(_b57_g, [_b57_nid], _b57_spec)
_b57_name = lambda S: {_b57_g.nodes[i]["canonical"] for i in S if i in _b57_g.nodes}
_b57_gone = _b57_name(_b57_before - _b57_after)
# ③ⓐ **형제 공정이 안 들어온다** — 상향 1홉으로 도달한 부모(조립)에 하향 재귀가
# 다시 걸리면 형제 전부가 딸려 와 「부모 맥락 한 겹」이 트리 전체가 된다.
show("③ⓐ 형제 공정이 확장에서 빠진다 (before/after 나란히)",
     len(_b57_after) < len(_b57_before)
     and {"스태킹", "탭용접", "패키징"} <= _b57_gone,
     f"before {len(_b57_before)} → after {len(_b57_after)} · 빠짐 {len(_b57_gone)}")
show("③ⓑ 상향 1홉으로 도달한 **부모는 남는다** (맥락 한 겹은 유지)",
     "조립" in _b57_name(_b57_after))
show("③ⓑ 부모에서 하향 재귀가 다시 걸리지 않는다 (형제 0건)",
     not ({"스태킹", "탭용접", "패키징"} & _b57_name(_b57_after)),
     str(sorted(_b57_name(_b57_after)))[:70])
show("③ 자기 하위 트리는 그대로 들어온다 (하향 재귀는 살아 있다)",
     any(c.startswith("노칭::") for c in _b57_name(_b57_after)),
     str(sorted(c for c in _b57_name(_b57_after) if c.startswith("노칭::"))[:3]))
# ③ⓒ 스모크 12문항의 경로 판정은 변하지 않는다.
_b57_smoke = json.loads((ROOT / "tests" / "fixtures" / "queries.json")
                        .read_text(encoding="utf-8"))["queries"]
with store.muted_material_logs():
    _b57_paths = {q["id"]: (q["expected_path"], R_answer(q["q"])["path"])
                  for q in _b57_smoke}
show("③ⓒ 스모크 12문항 expected_path 변화 0",
     all(w == g for w, g in _b57_paths.values()),
     str([(i, w, g) for i, (w, g) in _b57_paths.items() if w != g]))

print("\n■ B57 ④ — 빌드가 자기 소요를 남긴다 ([정정] 44)")

_b57_bm = store.read(pipeline_mod.BUILD_METRICS, [])
show("④ⓐ build_metrics.json에 한 줄씩 쌓인다 (로그이지 큐가 아니다 · 최근 50)",
     isinstance(_b57_bm, list) and _b57_bm and len(_b57_bm) <= 50
     and {"at", "doc_id", "seconds", "bytes_by_layer"} <= set(_b57_bm[-1]),
     f"{len(_b57_bm)}줄 · {_b57_bm[-1]['doc_id']} {_b57_bm[-1]['seconds']}s")
# ④ⓑ 계기판이 **빌드가 남긴 것**을 읽는다 — `save()` 시간이 아니다.
_b57_gz = gauges()
_b57_st = _b57_gz["8_build_seconds"]
show("④ⓑ 계기판 8이 build_metrics를 출처로 밝힌다 (save() 시간이 아니다)",
     all("build_metrics" in str(v.get("source", "")) for v in _b57_st.values()),
     str({k: str(v.get("source"))[:26] for k, v in _b57_st.items()}))
# **값이 빌드가 잰 것과 같다** — 계기판이 제 수치를 만들지 않는다.
_b57_secs = {h["doc_id"]: h["seconds"] for h in _b57_bm}
show("④ⓑ 계기판 8의 값이 빌드가 기록한 소요와 같다 (save() 시간이 아니다)",
     all(v["s"] in _b57_secs.values() for v in _b57_st.values()),
     f"계기판 {[v['s'] for v in _b57_st.values()]} · 기록 {sorted(set(_b57_secs.values()))}")
# ④ⓒ **계기판이 빌드를 다시 돌리지 않는다** — 측정이 제 수치를 만들면 안 된다.
_b57_n0 = len(store.read(pipeline_mod.BUILD_METRICS, []))
gauges()
show("④ⓒ 계기판 호출이 빌드를 다시 돌리지 않는다 (기록이 안 는다)",
     len(store.read(pipeline_mod.BUILD_METRICS, [])) == _b57_n0,
     f"{_b57_n0} → {len(store.read(pipeline_mod.BUILD_METRICS, []))}")
show("④ 계기판에서 build_begin/build_end 호출이 사라졌다",
     "g.build_begin()" not in (ROOT / "cli" / "platform.py").read_text(encoding="utf-8"))

print("\n■ B57 ⑤ — F1 뒷정리 ([정정] 45)")

# **D-57이 문면으로 지키던 성질을 검사로 옮긴다** — 반례가 되살아나면 여기서 잡힌다.
_b57_dup = []
for _lay in ("process", "quality"):
    _gg = open_graph(_lay)
    _by = {}
    for _n in _gg.nodes.values():
        if not ops.is_live(_n):
            continue
        _by.setdefault(_n["canonical"], set()).add(_n.get("polarity"))
    _b57_dup += [f"{_lay}:{c}({sorted(p)})" for c, p in _by.items() if len(p) > 1]
show("⑤ⓐ polarity만 다르고 canonical이 같은 노드 0건 (D-57이 지키던 성질)",
     not _b57_dup, str(_b57_dup[:3]))
# 카테고리 이름은 **config가 갖는다** — 코드도 조항도 복제하지 않는다.
# **단정하는 문장**이 사라졌는지를 본다 — 「구판은 …라고 적어 두었다」는 설명은
# 남아야 한다(왜 고쳤는지가 기록이다). 문자열을 통째로 세면 그 설명이 걸린다.
_b57_bsrc = (ROOT / "core" / "build" / "build.py").read_text(encoding="utf-8")
show("⑤ 스코프 대상 카테고리는 config가 갖는다 (코드가 이름을 단정하지 않는다)",
     load_config("process").get("canonical_scope", {}).get("bind_categories")
     == ["Property", "Unit"]
     and "카테고리(현행 Property)뿐이다" not in _b57_bsrc
     and "bind_categories`가 정하고 코드는 그것을 읽는다" in _b57_bsrc)
show("⑤ 회귀 대조 자산이 개정본 기준이다 (감사 에이전트가 읽는 자리)",
     "현행 Property" not in
     (ROOT / "docs" / "회귀스위트" / "자산" / "조항_기준선.json").read_text(encoding="utf-8")
     and "반전] B26" in
     (ROOT / "docs" / "회귀스위트" / "자산" / "V1_정답행.json").read_text(encoding="utf-8"))

# ── B58 ① 재등록 경로 (H27) ─────────────────────────────────────────────
# **잠그는 성질: 승인 기록은 누적된다.** 새 판을 올릴 때 이전 승인자가 사라지면
# 「이 문서는 누가 승인한 판으로 들어왔나」를 되짚을 수 없다 — 옛 판으로 인입된
# 문서가 남아 있는 한(자동 재인입은 없다) 그 이력이 곧 근거다.
# 문구가 아니라 **자료의 모양**을 본다: 화면 문안은 바뀌어도 이 성질은 남아야 한다.
print("\n■ B58 ① — 재등록: 승인 기록이 누적된다")

from core.state import registry                                     # noqa: E402

_B58 = "b58revtype"
_reg0 = store.read(store.DOC_TYPES, {})
_reg0.pop(_B58, None)
store.write(store.DOC_TYPES, _reg0)

registry.register(_B58, layer="quality", adapter="adapters/b58.py", schema="schemas/b58.json",
                  adapter_version="1.0", approved_by="갑", approved_at="2026-01-01T00:00:00+00:00")
_e1 = registry.revise(_B58, adapter="adapters/b58.py", schema="schemas/b58.json",
                      adapter_version="1.1", approved_by="을",
                      approved_at="2026-02-01T00:00:00+00:00")
_e2 = registry.revise(_B58, adapter="adapters/b58.py", schema="schemas/b58.json",
                      adapter_version="1.2", approved_by="병",
                      approved_at="2026-03-01T00:00:00+00:00")

_who = [a.get("approved_by") for a in (_e2.get("approvals") or [])]
show("①ⓔ 승인 이력이 쌓인다 — 첫 승인자가 살아 있다 (덮이지 않는다)",
     _who == ["갑", "을", "병"], str(_who))
show("①ⓔ 판 번호가 기록마다 다르다 — 어느 판을 누가 승인했는지 갈린다",
     [a.get("revision") for a in _e2["approvals"]] == [0, 1, 2])
show("①ⓔ 이름은 그대로고 정본만 바뀐다 (변형 등록이 아니다)",
     _e2["doc_type"] == _B58 and _e2["revision"] == 2
     and _e2["adapter_version"] == "1.2"
     and registry.lookup(_B58)["revision"] == 2)
show("①ⓔ 한 번 쌓인 기록은 다음 판에서도 그대로다 (재계산이 아니라 누적)",
     (_e1.get("approvals") or [])[:2] == (_e2.get("approvals") or [])[:2])

# **등록되지 않은 이름에는 새 판이 없다** — revise가 register를 겸하면 오타 하나가
# 조용히 새 doc_type을 만든다(그 반대가 `--as`다).
try:
    registry.revise("b58_없는이름", adapter="a.py", schema="s.json",
                    adapter_version="1.0", approved_by="갑", approved_at="x")
    _raised = False
except ValueError:
    _raised = True
show("①ⓔ 등록되지 않은 이름에 --revise는 막힌다 (오타가 새 doc_type을 만들지 않는다)",
     _raised)

# ⓓ 화면이 세는 수의 출처 — **그 doc_type으로 인입된 문서만** 센다.
_dr = store.read(store.DOC_REGISTRY, {})
_dr["B58DOC"] = {**(_dr.get("CP01") or {}), "doc_type": _B58}
store.write(store.DOC_REGISTRY, _dr)
show("①ⓓ 인입 문서 집계는 그 doc_type의 것만 센다",
     registry.ingested_docs(_B58) == ["B58DOC"]
     and "B58DOC" not in registry.ingested_docs("cp_table"),
     str(registry.ingested_docs(_B58)))

# **시험용 등재를 걷는다** — 남기면 다음 스위트가 「등록부에 모르는 이름이 있다」로
# 걸린다(실사고). 시험은 자기가 만든 것을 자기가 치운다.
_reg9 = store.read(store.DOC_TYPES, {}); _reg9.pop(_B58, None)
store.write(store.DOC_TYPES, _reg9)
_dr9 = store.read(store.DOC_REGISTRY, {}); _dr9.pop("B58DOC", None)
store.write(store.DOC_REGISTRY, _dr9)
show("①ⓔ 시험이 자기 등재를 치웠다 (다음 스위트로 새지 않는다)",
     registry.lookup(_B58) is None and registry.ingested_docs(_B58) == [])

done()
