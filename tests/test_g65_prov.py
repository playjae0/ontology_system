# -*- coding: utf-8 -*-
"""G6.5 ③ provenance — `{doc_id}#{locator}` · 좌표 값 부재의 처분 사다리 셋(B57)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


fresh()          # 이 스위트의 바닥 — 골격·인입이 선 상태에서 잰다(B78 2c)

print("\n■ B57 ① — provenance = {doc_id}#{locator}")

import glob as _b57_glob                                          # noqa: E402

# ①ⓑ(i) **계약 A의 locator는 끝까지 접두가 없다**([정정] 42). 픽스처만 접두를
# 갖고 있어서 계기판 2가 mock에서만 초록이었다 — §7.5-1의 교과서 사례다.
_b57_pref = []
for _f in sorted(_b57_glob.glob(str(ROOT / "tests" / "fixtures" / "parsed" / "*.json"))):
    _d = json.loads(Path(_f).read_text(encoding="utf-8"))
    _did = str(_d.get("doc_id") or "")
    for _r in (_d.get("records") or _d.get("chunks") or []):
        _L = _r.get("source_locator") or ""
        if _did and _L.startswith(_did):
            _b57_pref.append(f"{Path(_f).name}:{_L}")
show("①ⓑ(i) parsed/ 픽스처의 어느 locator도 자기 doc_id로 시작하지 않는다",
     not _b57_pref, str(_b57_pref[:3]))
# 추출 힌트는 locator를 **키로** 쓴다 — 같이 안 내리면 힌트가 통째로 안 걸린다.
_b57_hint = [f"{Path(_f).name}:{_k}"
             for _f in sorted(_b57_glob.glob(
                 str(ROOT / "tests" / "fixtures" / "extract_hints" / "*.json")))
             for _k in json.loads(Path(_f).read_text(encoding="utf-8"))
             if _k.startswith(Path(_f).stem)]
show("①ⓑ(i) 추출 힌트 키도 접두가 없다 (locator를 키로 쓰는 자리)",
     not _b57_hint, str(_b57_hint[:3]))

# ①ⓑ(ii) 그래프의 provenance는 `#`를 갖거나 seed·auto다.
_b57_bad = []
for _lay in ("process", "quality"):
    _g = json.loads((_P.data() / _lay / ("graph" + ".json")).read_text(encoding="utf-8"))
    _holders = list(_g["nodes"].values()) + list(_g["edges"])
    for _h in _holders:
        for _p in (_h.get("provenance") or []):
            if "#" in _p or _p == "seed" or _p.startswith("auto:"):
                continue
            _b57_bad.append(_p)
show("①ⓑ(ii) 그래프의 provenance는 전부 `#`를 갖거나 seed·auto:다",
     not _b57_bad, str(sorted(set(_b57_bad))[:4]))
# **seed·auto는 대상이 아니다** — 문서 조각에서 오는 것에만 붙는다.
_b57_seed = [p for _lay in ("process",)
             for _g in [json.loads((_P.data() / _lay / ("graph" + ".json"))
                                   .read_text(encoding="utf-8"))]
             for n in _g["nodes"].values()
             for p in (n.get("provenance") or []) if p == "seed"]
show("①ⓑ(ii) seed 항목에는 접두를 붙이지 않는다 (문서 조각이 아니다)",
     bool(_b57_seed), f"seed {len(_b57_seed)}건")

# ①ⓑ(iii) **이 건의 본체** — 같은 locator를 가진 두 문서 중 하나를 재인입해도
# 다른 문서의 근거가 남는다. 구판은 locator만 보고 남의 근거까지 걷어냈다.
fresh()
# **두 문서가 같은 locator를 쓴다** — 실파서가 내는 `Sheet1!R12`가 바로 그 꼴이다.
_b57_base = load("CP01")
_b57_rec = dict(_b57_base["records"][0])
_b57_rec.update({"source_locator": "Sheet1!R12", "관리항목": "공유좌표시험"})
_b57_env = dict(_b57_base, doc_id="SAMEA", source_path="a.xlsx",
                records=[_b57_rec])
# B는 **같은 locator의 같은 행 + 제 행 하나**다 — 내용이 완전히 같으면
# `duplicate_doc_hold`로 잡혀 두 번째 문서가 아예 안 들어간다.
_b57_extra = dict(_b57_rec, source_locator="Sheet1!R99", 관리항목="B전용항목")
_b57_envB = dict(_b57_base, doc_id="SAMEB", source_path="b.xlsx",
                 records=[dict(_b57_rec), _b57_extra])
run_document(_b57_env); finalize()
run_document(_b57_envB); finalize()
_b57_node = node_by("process", "노칭::공유좌표시험")   # canonical_scope가 붙는다
_b57_before = list(_b57_node["provenance"])
run_document(_b57_envB); finalize()          # SAMEB만 재인입
_b57_after = list(node_by("process", "노칭::공유좌표시험")["provenance"])
show("①ⓑ(iii) 같은 locator의 두 문서 — 하나를 재인입해도 **다른 문서 근거가 남는다**",
     "SAMEA#Sheet1!R12" in _b57_after,
     f"전 {_b57_before} → 후 {_b57_after}")
show("①ⓑ(iii) 두 문서의 근거가 애초에 갈려 실린다 (locator만이면 한 항목이었다)",
     len({p for p in _b57_before if "#" in p}) == 2, str(sorted(_b57_before)))

# ①ⓒ 계기판 2가 **실파서 꼴** locator에서 값을 낸다.
from cli.platform import gauges as _b57_gauges                    # noqa: E402
_b57_g = _b57_gauges()
_b57_series = _b57_g["2_plateau"]["series"]
show("①ⓒ 계기판 2가 실파서 꼴 locator에서 None이 아닌 값을 낸다",
     bool(_b57_series) and all(s.get("doc") for s in _b57_series)
     and any(s["mentioned"] for s in _b57_series),
     f"{[(s['doc'], s['mentioned']) for s in _b57_series][:3]}")

# ①ⓓ `doc_locators()`는 삭제됐다 — 접두가 문서를 말하므로 발자국 인덱스가 필요 없다.
_b57_ing = (ROOT / "core" / "build" / "ingest.py").read_text(encoding="utf-8")
show("①ⓓ doc_locators()가 삭제됐다 (순감소)",
     "def doc_locators" not in _b57_ing
     and 'p == doc_id or str(p).startswith(doc_id + "#")' in _b57_ing)
# **계약 A의 locator는 손대지 않는다** — 대응표 셋이 raw locator로 맞추는 자리다.
_b57_pipe = " ".join(_p.read_text(encoding="utf-8")
                     for _p in sorted((ROOT / "core" / "build").glob("*.py")))
show("① 청크 대응표는 raw locator 그대로다 (접두를 섞지 않는다)",
     'by_locator = {c["source_locator"]: c' in _b57_pipe
     and 'loc2id = {c["source_locator"]: cid' in _b57_pipe)
_b57_ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
show("① 청크 저장소의 source_locator에 접두가 없다 (계약 A 불변)",
     not [c for c in _b57_ch.values()
          if "#" in (c.get("source_locator") or "")])


# ── B57 ② 공정좌표 값 부재의 처분 사다리 ([개정] B56-2) ────────────────────
print("\n■ B57 ② — 좌표 값 부재의 처분 사다리 셋")

_b57_cp = load("CP01")


def _b57_ladder(**over):
    fresh()
    _r = dict(_b57_cp["records"][0])
    _r.update(over)
    _r["관리항목"] = "사다리시험"
    run_document(dict(_b57_cp, doc_id="LAD", records=[_r]))
    finalize()
    _g = open_graph("process")
    _n = next((x for x in _g.nodes.values() if "사다리시험" in x["canonical"]), None)
    _q = [x for x in store.read(store.QUEUE, []) if x["doc_id"] == "LAD"]
    return _n, _q


_b57_n1, _b57_q1 = _b57_ladder()                                   # 정상
_b57_n2, _b57_q2 = _b57_ladder(process_ref=None)                   # 저해상도
_b57_n3, _b57_q3 = _b57_ladder(process_ref=None, process_group=None)   # 둘 다 null


def _b57_coordq(q):
    return [x for x in q if x["kind"] in ("orphan_anchor", "missing_field",
                                          "coord_mismatch")]


show("②ⓐ process_ref 있음 — 종전 그대로 좌표에 붙는다",
     _b57_n1 and _b57_n1["canonical"] == "노칭::사다리시험"
     and not _b57_coordq(_b57_q1), _b57_n1 and _b57_n1["canonical"])
# **저해상도는 큐를 달지 않는다** — 그룹으로라도 붙었으면 그 지식은 그래프에 있고,
# 사람이 할 일이 없다. 해상도가 낮다는 사실은 붙은 노드가 개념 노드인 것으로 드러난다.
show("②ⓒ process_group만 있으면 **저해상도 부착** — 그룹에 붙고 좌표 큐 0건",
     _b57_n2 and _b57_n2["canonical"] == "조립::사다리시험"
     and not _b57_coordq(_b57_q2),
     f"{_b57_n2 and _b57_n2['canonical']} · 좌표 큐 {len(_b57_coordq(_b57_q2))}건")
# 저해상도에서 늘어난 큐가 있다면 **노드 생성 통지(auto_node)뿐**이다 — 그룹 좌표에
# 붙으면서 `조립::노칭 프레스`가 새로 서기 때문이고, 좌표에 대한 불평이 아니다.
show("②ⓒ 저해상도가 늘리는 큐는 auto_node(노드 생성 통지)뿐이다",
     {x["kind"] for x in _b57_q2} <= {"auto_node"},
     f"{len(_b57_q1)} → {len(_b57_q2)}건 · "
     f"{sorted({x['kind'] for x in _b57_q2})}")
# **둘 다 null** — 재료를 동봉해 착지시킨다. 구판은 `for item in defer:`라 0건이었다.
_b57_mf = [x for x in _b57_q3 if x["kind"] == "missing_field"]
show("②ⓑ 좌표가 둘 다 null이면 missing_field 1건",
     len(_b57_mf) == 1 and "공정좌표 값 부재" in _b57_mf[0]["reason"],
     _b57_mf[0]["reason"][:44] if _b57_mf else str(_b57_q3))
_b57_pl = _b57_mf[0]["payload"] if _b57_mf else {}
show("②ⓑ payload에 **드롭된 entity 표면형**이 실려 있다 (재시도의 재료)",
     any(e.get("surface") == "노칭 프레스"
         for e in (_b57_pl.get("dropped_entities") or [])),
     str([e.get("surface") for e in (_b57_pl.get("dropped_entities") or [])])[:56])
show("②ⓑ payload에 dropped_edges·pending_attrs도 함께 실린다",
     bool(_b57_pl.get("dropped_edges")) and bool(_b57_pl.get("pending_attrs")),
     f"edges {len(_b57_pl.get('dropped_edges') or [])} · "
     f"attrs {len(_b57_pl.get('pending_attrs') or [])}")
# **새 kind 0** — 재시도 대상이 아니다(sweep이 물지 않는다).
show("②ⓑ 새 큐 kind를 만들지 않는다 (missing_field가 「필수 값 부재」를 덮는다)",
     {x["kind"] for x in _b57_q3} <= {"auto_node", "missing_field", "uncertain_match",
                                      "orphan_anchor", "orphan_attach", "spec_conflict",
                                      "coord_mismatch", "evidence_lost"},
     str(sorted({x["kind"] for x in _b57_q3})))
# **STRUCTURAL을 건드리지 않았다** — 검사의 자리는 좌표 해소 지점이다.
show("② process_ref는 여전히 구조 필드다 (unknown_field로 쏟아지지 않는다)",
     not [x for x in _b57_q3 if x["kind"] == "unknown_field"]
     and "coord_case" in (ROOT / "core" / "build" / "table.py").read_text(encoding="utf-8"))


# ── B57 ③④⑤ ────────────────────────────────────────────────────────────
from core.build import entry as pipeline_mod                          # noqa: E402
from cli.platform import gauges                                    # noqa: E402
from cli.query import answer as R_answer                           # noqa: E402

done()
