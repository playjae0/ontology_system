# -*- coding: utf-8 -*-
"""G6 ㉒ 좌표 어긋남을 앞에서 잡는다 — 상위를 범위로 하위 해소 · 등록 대조 · 판정 전 쌍 표 · 쌍 단위 확인 · 질의
노드 원 레코드 (B105).

창작 표본(mock 그래프 + 시험이 만든 행·청크 · 추출은 mock 힌트 · 킷 하네스는 픽스처 어댑터의 변형)으로 메커니즘을
잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) × 층(process · quality)에서 같은 성질을 잰다(CLAUDE.md §4).

잠그는 성질:
  ⓐ 상위 범위 해소: 공유 별칭 하위 + 상위가 있는 행 → 그 상위 서브트리 노드 canonical(원 표기·범위 meta) · 보류 0 ·
     어긋남 0 / 범위 안에서도 여럿이면 보류 그대로(「표기 모호」) / 하위가 전역 단일 노드면 바꾸지 않음(어긋남이 보인다)
  ⓑ 등록 관문 G4I: 상위·하위를 바꾼 표본 → FAIL + 「열을 바꾸면 n/m」(층 둘) / 일부 어긋남 → PASS + 경고 + 쌍 표 /
     상위 이름 골격 밖 종수 / 문턱은 손잡이 / 검수 화면이 같은 표
  ⓒ 좌표 단계: 쌍 표의 쌍·행 수 = 구축 큐의 쌍·행 수(표·산문 × 층 둘) · `--step` 좌표 관문에서 멈추면 LLM 0 · 쓰기 0
  ⓓ 큐: 쌍 묶음 · 확인함 → 그 쌍 화면 수 0(목록엔 확인됨) · 재인입 · 다른 문서의 같은 쌍도 확인됨 · `init --fresh`
     뒤에도 기록이 산다 · 취소하면 다시 보인다
  ⓔ 질의 ⓖ: 링킹·확장 노드의 원 레코드(값·별칭·출처 = 저장된 그대로) · CLI 줄 수 = `--json` 수 · 상한은 손잡이
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import re
import tempfile
from pathlib import Path

sys_path = __import__("sys").path
sys_path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done, overlay   # noqa: F401

from cli import coord_queue as CQU, doc_coord as DC, ingest as IG, platform as PF, query as CQ   # noqa: E402
from cli import _screen                                                                       # noqa: E402
from cli.register import gate as GT, view as RV                                               # noqa: E402
from core.build import ledger as LG                                                           # noqa: E402
from core.state import coord_acks as CA, knobs as KB                                          # noqa: E402
from parser import coord_pairs as CP, pipeline, tagger as TG                                 # noqa: E402

FX = ROOT / "tests" / "fixtures"
RAW = FX / "raw"
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS
_made = []


def _clean_acks():
    CA.path().unlink(missing_ok=True)


def _hint(doc_id, locs):
    (HINTS / f"{doc_id}.json").write_text(json.dumps({
        loc: {"entities": [{"surface": f"B105 카메라 {loc[-1]}", "category": "Unit"}], "relations": [], "attach": []}
        for loc in locs}, ensure_ascii=False), encoding="utf-8")
    _made.append(doc_id)


def _register_table(lay):
    dt = f"b105t{lay[0]}"
    p = _P.schemas(f"{dt}.json")
    _P.ensure(p)
    p.write_text(json.dumps({"doc_type": dt, "schema_version": 1, "layer": lay,
                             "use_blocks": ["common_core", "process_coord"],
                             "fields": {"개체": {"role": "entity", "category": "Unit"}}, "edges": []},
                            ensure_ascii=False), encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[dt] = {"doc_type": dt, "status": "registered", "layer": lay, "schema": f"schemas/{dt}.json",
               "adapter": "-", "schema_version": 1}
    store.write(store.DOC_TYPES, dts)
    return dt


def _unregister(lay):
    dt = f"b105t{lay[0]}"
    dts = store.read(store.DOC_TYPES, {})
    dts.pop(dt, None)
    store.write(store.DOC_TYPES, dts)
    _P.schemas(f"{dt}.json").unlink(missing_ok=True)


#: 세 행 — A 상위 범위 안에서 하나 · B 상위 범위 안에서도 여럿 · C 하위가 전역 단일(상위 밖)
ROWS = [("A", "노칭", "비전 검사"), ("B", "조립", "비전 검사"), ("C", "스태킹", "노칭 타발")]


def _env(form, lay, did):
    """형태 하나 · 층 하나의 봉투 — 조각은 파서와 같은 함수(`tagger.tag`)를 지난다."""
    nodes = TG.closed_list("process")
    if form == "표":
        dt = _register_table(lay)
        base = {k: v for k, v in CPREC.items() if k not in ("설비", "관리항목")}
        pcs = [dict(base, source_locator=f"{did}-{t}", doc_type=dt, process_group=g, process_ref=r,
                    개체=f"B105 카메라 {t}") for t, g, r in ROWS]
        return {**TABLE, "doc_id": did, "doc_type": dt, "records": TG.tag(pcs, nodes=nodes, doc_type=dt)}
    dt = f"ppt_{lay}"
    pcs = [{**C1, "source_locator": f"{did}-{t}", "doc_type": dt, "process_group": g, "process_ref": r,
            "text": f"{t} 행 — B105 카메라 {t}를 쓴다."} for t, g, r in ROWS]
    _hint(did, [p["source_locator"] for p in pcs])
    return {**PROSE, "doc_id": did, "doc_type": dt, "source_path": f"{did}.pptx",
            "chunks": TG.tag(pcs, nodes=nodes, doc_type=dt)}


def _q(kind, did):
    return [x for x in store.read(store.QUEUE, []) if x["kind"] == kind and x["doc_id"] == did]


def _pairs_of_queue(did):
    out = {}
    for x in _q("coord_mismatch", did):
        k = CP.pair_of(x["payload"])
        out[k] = out.get(k, 0) + 1
    return out


# ────────────────────────────────────────────────────────────── ⓐ ⓒ
print("\n■ B105 ① 상위를 범위로 하위 해소 · ③ 판정 전 쌍 표 = 구축 큐 (표 · 산문 × 층 둘)")
overlay()                                         # 품질층이 Unit을 렌즈로 쓴다(층 둘)
_clean_acks()
_oa, _oc, _envs = [], [], {}
for form in ("표", "산문"):
    for lay in ("process", "quality"):
        did = f"B105{'T' if form == '표' else 'P'}{lay[0].upper()}"
        env = _env(form, lay, did)
        _envs[(form, lay)] = env
        pcs = {p["source_locator"][-1]: p for p in env.get("records") or env.get("chunks")}
        with contextlib.redirect_stdout(io.StringIO()):
            rep = DC.pair_report(env)                # 판정 전 — 구축과 같은 함수 · 큐 0
        run_document(env)
        orphans = _q("orphan_anchor", did)
        mism = _pairs_of_queue(did)
        a, b_, c = pcs["A"], pcs["B"], pcs["C"]
        ma = a.get("meta") or {}
        led = [r for r in ((LG.read(did) or {}).get("rows") or [])
               if r.get("role") == "entity" and (r.get("surface") or "").endswith(" A")]
        ok_a = (a["process_ref"] == "노칭::비전검사" and ma.get("coord_tag_from") == "비전 검사"
                and ma.get("coord_tag_scope") == "노칭"
                and not any(f"{did}-A" in str(o["payload"]) for o in orphans)
                and not any(str(x["payload"].get("provenance")).endswith("-A") for x in _q("coord_mismatch", did))
                and led and all((r.get("target") or "").startswith("노칭::비전검사::") for r in led)
                and b_["process_ref"] == "비전 검사"
                and any("표기 모호" in o["reason"] for o in orphans)
                and c["process_ref"] == "노칭 타발"
                and mism.get((CP.GROUP, ("스태킹", "노칭::노칭 타발"))) == 1)
        _oa.append((form, lay, ok_a, f"A {a['process_ref']}(범위 {ma.get('coord_tag_scope')}) → "
                                      f"{sorted({r.get('target') for r in led})} · B {b_['process_ref']} 보류 "
                                      f"{sum(1 for o in orphans if '표기 모호' in o['reason'])} · C {c['process_ref']} "
                                      f"어긋남 {dict((k[1][0] + '>' + k[1][1], v) for k, v in mism.items())}"))
        t, _acked = rep
        _oc.append((form, lay, {k: e["rows"] for k, e in t["pairs"].items()} == mism and mism,
                    f"쌍 표 {len(t['pairs'])}쌍({sum(e['rows'] for e in t['pairs'].values())}행) = "
                    f"큐 {len(mism)}쌍({sum(mism.values())}행)"))
show("ⓐ 공유 별칭 하위 + 상위 → 상위 서브트리 노드 canonical(원 표기 · 범위 meta) · 보류 0 · 어긋남 0 · 개체가 그 노드 아래 / "
     "범위 안에서도 여럿이면 보류(「표기 모호」) / 전역 단일 하위는 그대로 — 어긋남이 보인다 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _oa), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _oa))
show("ⓒ 판정 전 쌍 표의 쌍·행 수 = 그 문서 구축 큐(coord_mismatch)의 쌍·행 수 (같은 함수 · 같은 입력 · 표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _oc), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _oc))

for _lay in ("process", "quality"):                # 시험이 세운 등록은 시험이 치운다(인입의 등록부 점검이 결손을 거부한다)
    _unregister(_lay)

# ⓒ `--step` 좌표 관문에서 멈추면 — LLM 0 · 그래프·큐 쓰기 0 · 그 관문 머리가 쌍 수를 말한다
print("\n■ B105 ③ --step 좌표 관문 (판정 비용 전)")
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)                         # 빈 그래프 — 같은 doc_id의 옛 원본 경로가 없다
    for _l in ("process", "quality"):
        bootstrap(_l, echo=False)


class _Tty:
    def isatty(self):
        return True


def _graph_hash():
    h = hashlib.sha256()
    for lay in ("process", "quality"):
        h.update(json.dumps(open_graph(lay).nodes, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    h.update(json.dumps(store.read(store.QUEUE, []), sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


_h0 = _graph_hash()
_keep = (IG.sys.stdin, _screen.ask)
_asked = []
IG.sys.stdin = _Tty()
# 관문 순서: 0 선택 → 1 파싱 → **2 좌표** — 셋째 물음에서 멈춘다
_screen.ask = lambda prompt: _asked.append(prompt) or ("q" if len(_asked) == 3 else "c")
_buf = io.StringIO()
try:
    from core.llm import gateway as _gw
    _u0 = _gw.usage_total()["calls"]
    with contextlib.redirect_stdout(_buf):
        _row = IG.ingest_file(str(RAW / "CP01.xlsx"), "cp", step=True)
    _u1 = _gw.usage_total()["calls"]
finally:
    IG.sys.stdin, _screen.ask = _keep
_out = _buf.getvalue()
_g2 = next((l for l in _out.splitlines() if "좌표 —" in l and "좌표 쌍 어긋남" in l), "")
show("ⓒ --step 좌표 관문 — 쌍 표가 판정 전에 서고(머리에 「좌표 쌍 어긋남 k쌍」) 멈추면 LLM 0 · 그래프·큐 쓰기 0",
     _row.get("reason") == "사람이 멈췄다 — 좌표까지" and _u1 == _u0 and _graph_hash() == _h0
     and "좌표 쌍 — 어긋남 1쌍(1행)" in _out and "좌표 쌍 어긋남 1쌍(1행)" in _g2,   # 극성 쌍 지움(기대 변경 B198)
     f"{_row.get('reason')} · LLM {_u1 - _u0} · 머리 「{_g2.strip()[:70]}」")

# ────────────────────────────────────────────────────────────── ⓑ
print("\n■ B105 ② 등록 관문 G4I — 표본 좌표 쌍 (표 × 층 둘)")
_ok_b = []
with tempfile.TemporaryDirectory(prefix="b105_") as td:
    _n = [0]

    def _variant(ad, swaps):
        src = (FX / "adapters" / f"{ad}.py").read_text(encoding="utf-8")
        for old, new in swaps:
            assert old in src, old
            src = src.replace(old, new)
        _n[0] += 1                                 # 변형마다 새 이름 (.pyc 판 혼동 방지 — B100)
        q = Path(td) / f"{ad}_v{_n[0]}.py"
        q.write_text(src, encoding="utf-8")
        return q

    def _g4i(adapter, ad, sample):
        ok, out = GT.harness(adapter, FX / "schemas" / f"{ad}.json", [RAW / sample])
        lines = out.splitlines()
        i = next((k for k, l in enumerate(lines) if "G4I" in l), None)
        return ok, (lines[i] if i is not None else ""), lines[i + 1:i + 6] if i is not None else []

    swap = {"cp": [('"process_group": "A",', '"process_group": "C",'),
                   ('"process_ref": "C",', '"process_ref": "A",')],
            "pfmea": [('"process_group": "A", "process_no": "B", "process_ref": "C",',
                       '"process_group": "C", "process_no": "B", "process_ref": "A",')]}
    for lay, ad, sample in (("process", "cp", "CP01.xlsx"), ("quality", "pfmea", "PFMEA01.xlsx")):
        ok, line, _tail = _g4i(_variant(ad, swap[ad]), ad, sample)
        m = re.search(r"열을 바꾸면 (\d+)/(\d+) 맞는다", line)
        _ok_b.append((lay, "맞바꿈", not ok and "[FAIL]" in line and "뒤바뀌었거나 매핑이 틀렸다" in line
                      and m and int(m.group(1)) * 2 > int(m.group(2)), line.strip()[:150]))
    ok, line, tail = _g4i(FX / "adapters" / "cp.py", "cp", "CP01.xlsx")
    _ok_b.append(("process", "일부", ok and "[PASS]" in line and "어긋남 1행" in line
                  and any("상위 '스태킹' ↛ 하위 '노칭'" in t for t in tail) and any("⚠ 경고" in t for t in tail),
                  line.strip()[:150]))
    ok, line, tail = _g4i(_variant("cp", [('"process_group": "A",', '"process_group": "E",')]), "cp", "CP01.xlsx")
    mo = re.search(r"상위 이름 골격 밖 (\d+)종", line)
    _ok_b.append(("process", "골격 밖", "[PASS]" in line and mo and int(mo.group(1)) >= 1
                  and any("상위 이름 골격 밖:" in t for t in tail), line.strip()[:150]))
    # 문턱은 손잡이 — 1%면 같은 표본(어긋남 1/30)이 FAIL
    _P.knobs().write_text(json.dumps({"coord_pair_pct": 1}), encoding="utf-8")
    KB.reset()
    ok1, line1, _t = _g4i(FX / "adapters" / "cp.py", "cp", "CP01.xlsx")
    _P.knobs().unlink()
    KB.reset()
    _ok_b.append(("process", "문턱1", "[FAIL]" in line1 and "문턱 1%" in line1, line1.strip()[:110]))
show("ⓑ 관문 G4I — 상위·하위를 바꾼 표본은 FAIL + 「열을 바꾸면 n/m 맞는다」(층 둘) · 일부 어긋남은 PASS + 경고 + 쌍 표 · "
     "상위 이름 골격 밖 종수 · 문턱은 손잡이 coord_pair_pct",
     all(o for _l, _s, o, _d in _ok_b), " ‖ ".join(f"{l}·{s} {d}" for l, s, _o, d in _ok_b))
# 검수 화면은 같은 표 — 리허설 파싱(운영 파서) 위에서 같은 판정 · 같은 해소
from cli.register import _load as _rload                       # noqa: E402 — 검수 화면과 같은 로더
from core.state.bootstrap import coord_layer as _coord_layer       # noqa: E402
_res = pipeline.parse(_rload(FX / "adapters" / "cp.py", "b105_cp"), "B105REV", str(RAW / "CP01.xlsx"),
                      layer=_coord_layer())
_rt = RV.pair_table(_res)
show("ⓑ 검수 화면(register review)의 쌍 표 = 관문 G4I의 쌍 표 (같은 판정 · 닫힌 목록 해소)",
     _rt and set(CP.pair_lines(_rt)) >= {"상위 '스태킹' ↛ 하위 '노칭' · 1행 · 예 관리계획서!R14"}
     and _rt["checked"] == 30 and _rt["group_rows"] == 1, " / ".join(CP.pair_lines(_rt)))

# ────────────────────────────────────────────────────────────── ⓓ
print("\n■ B105 ④ 큐 — 쌍 묶음 · 확인함 · 재인입 · 다른 문서 · fresh · 취소")
overlay()
_clean_acks()
PAIR = (CP.GROUP, ("스태킹", "노칭::노칭 타발"))
_e1 = _env("표", "process", "B105D1")
_e2 = _env("산문", "quality", "B105D2")
run_document(_e1)


def _grp():
    return dict(CQU.groups()).get(PAIR) or {}


def _kind_count():
    return PF.queue_view()["kinds"]["coord_mismatch"]


_n0 = _kind_count()
rec, n_ack = CA.ack(*PAIR, "시험", "B105 쌍 확인")
_g1, _n1 = _grp(), _kind_count()
_sh = io.StringIO()
with contextlib.redirect_stdout(_sh):
    CQU.show()
run_document(_e1, allow_duplicate=True)                    # 재인입
_g2r = _grp()
run_document(_e2)                                          # 다른 문서(산문 · 품질층)의 같은 쌍
_g3 = _grp()
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    for _l in ("process", "quality"):
        bootstrap(_l, echo=False)
_alive = CA.path().exists() and CA.key(*PAIR) in CA.acked()
overlay()
_e1 = _env("표", "process", "B105D1")
run_document(_e1)
_g4 = _grp()
_r, n_un = CA.unack(*PAIR, "시험")
_g5 = _grp()
show("ⓓ 쌍 묶음 — 행마다의 항목이 (상위, 하위) 쌍 하나로 · 확인함 → 그 쌍 화면 수 0(목록엔 「확인됨」 · 메모)",
     _g1.get("open") == 0 and _g1.get("done") == n_ack >= 1 and _n1 == _n0 - n_ack
     and "확인됨(시험" in _sh.getvalue() and "B105 쌍 확인" in _sh.getvalue(),
     f"확인 {n_ack}행 · 화면 수 {_n0} → {_n1} · 기록 docs {rec['docs']}")
show("ⓓ 재인입 · 다른 문서(산문 × 품질층)의 같은 쌍도 확인됨 · init --fresh 뒤에도 기록이 살아 새 항목이 확인됨 · "
     "취소하면 다시 보인다",
     _g2r.get("open") == 0 and _g2r.get("rows") == _g1.get("rows")
     and _g3.get("open") == 0 and len(_g3.get("docs") or []) == 2
     and _alive and _g4.get("open") == 0 and _g4.get("done") == 1
     and n_un == 1 and _g5.get("open") == 1 and not _g5.get("rec") and CA.key(*PAIR) not in CA.acked(),
     f"재인입 열린 {_g2r.get('open')}/{_g2r.get('rows')} · 다른 문서 {_g3.get('docs')} · fresh 뒤 기록 {_alive} · "
     f"취소 → 열린 {_g5.get('open')}")
_clean_acks()
for lay in ("process", "quality"):
    _unregister(lay)

# ────────────────────────────────────────────────────────────── ⓔ
print("\n■ B105 ⑤ 질의 ⓖ 노드 원 레코드")
with contextlib.redirect_stdout(io.StringIO()):
    fresh()
_Q = "노칭 정밀도 규격은?"
_o = io.StringIO()
with contextlib.redirect_stdout(_o):
    CQ.main([_Q])
_jo = io.StringIO()
with contextlib.redirect_stdout(_jo), contextlib.redirect_stderr(io.StringIO()):
    CQ.main([_Q, "--json"])
_j = json.loads(_jo.getvalue())
_recs = _j["records"]
_graph = {n["id"]: n for lay in ("process", "quality") for n in open_graph(lay).nodes.values()}
_raw_ok = all(r["attrs"] == (_graph[r["node_id"]].get("attrs") or {})
              and r["aliases"] == (_graph[r["node_id"]].get("aliases") or [])
              and r["provenance"] == (_graph[r["node_id"]].get("provenance") or []) for r in _recs)
_linked = {x["node_id"] for x in _j["linked_nodes"]}
_ncli = sum(1 for l in _o.getvalue().splitlines() if l.strip().startswith("[원 레코드]"))
show("ⓔ 링킹·확장 노드의 원 레코드 — 값·별칭·출처가 저장된 그대로(가공 0) · 링킹 노드 먼저 · 닻까지의 길 · "
     "CLI [원 레코드] 줄 수 = --json records 수",
     _recs and _raw_ok and {r["node_id"] for r in _recs if r["role"] == "링킹"} == _linked
     and [r["role"] for r in _recs] == sorted([r["role"] for r in _recs], key=lambda x: x != "링킹")
     and any(r["attrs"] for r in _recs) and all("where" in r for r in _recs)
     and _ncli == len(_recs) == min(_j["records_total"], KB.get("query_record_limit")),
     f"레코드 {len(_recs)}(링킹 {sum(1 for r in _recs if r['role'] == '링킹')}) · CLI {_ncli} · "
     f"예 {_recs[0]['canonical']} 값 {list(_recs[0]['attrs'])}")
_P.knobs().write_text(json.dumps({"query_record_limit": 2}), encoding="utf-8")
KB.apply()                                         # core 손잡이는 읽은 값을 기억한다 — 다시 읽힌다
_j2 = CQ.answer(_Q)
_P.knobs().unlink()
KB.apply()
show("ⓔ 상한은 손잡이 query_record_limit — 2면 레코드 2 · 닿은 노드 수(records_total)는 그대로",
     len(_j2["records"]) == 2 and _j2["records_total"] == _j["records_total"],
     f"{len(_j2['records'])} / {_j2['records_total']}")

# ────────────────────────────────────────────────────────────── B196 골격 칸의 문 (창작 표본 · mock)
print("\n■ B196 — 잠정 골격 노드는 사람이 정한 것만 · 쌍 어긋남은 확인 전 보류 · 골격 칸 검토 줄 · 연결 표지")
from cli import ops_review as OR196, provisional_ask as PA196        # noqa: E402
from core.build import provisional as PV196, retry as RT196, skeleton_review as SR196   # noqa: E402
from core.build import coord_scan as CS196                          # noqa: E402
from core.state import provisional_hand as PH196                     # noqa: E402
from core.state.bootstrap import coord_layer                         # noqa: E402
from core.state.status import is_live                                # noqa: E402
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    for _l in ("process", "quality"):
        bootstrap(_l, echo=False)
_clean_acks()
_dt196 = _register_table("process")


def _env196(did, recs):
    return {**TABLE, "doc_id": did, "doc_type": _dt196, "records": TG.tag(
        [dict(r, doc_type=_dt196, electrode_type=r.get("electrode_type", "both")) for r in recs],
        layer=coord_layer(), doc_type=_dt196, doc_id=did)}


def _run196(env):
    with contextlib.redirect_stdout(io.StringIO()):
        run_document(env, allow_duplicate=True)
    return {r["locator"]: r for r in (LG.read(env["doc_id"]) or {}).get("rows") or [] if r.get("role") == "anchor"}


def _pv196(c):
    return next((n for n in open_graph(coord_layer()).nodes.values() if n["canonical"] == c and is_live(n)), None)


def _rec196(loc, ref, grp="조립", **kw):
    return {"source_locator": loc, "process_group": grp, "process_ref": ref, "개체": f"B196 카메라 {loc}", **kw}


def _ask196(env, surface, answer):
    rows = [r for r in PA196.step_rows(env) if r.get("surface") == surface or r.get("ref") == surface]
    with contextlib.redirect_stdout(io.StringIO()):
        return PA196.decide(rows[0], "시험", answer=answer)[0] if rows else None


# ⓐ 사람 없는 실행 — 다르다(mock)인 표기는 세우지 않고 보류 · ⓖ 머리 줄의 수 · 후보 차례
_judged = {"노칭공정X": {"type": "uncertain", "candidates": ["스태킹"], "confidence": 0.6}}
_ea = _env196("B196A", [_rec196("A1", "노칭공정X", meta={"coord_judge": _judged}),
                        _rec196("A2", "노칭공정X", meta={"coord_judge": _judged})])
_rv = SR196.review(_ea)
_an = _run196(_ea)
_oa = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor" and x["payload"].get("surface") == "노칭공정X"]
show("B196 ⓐ 표 행 「노칭공정X」(골격 밖 · 판단 다르다/애매) · 사람 없는 실행 → 잠정 노드 0 · 그 행들 보류(사유 「사람 확인 전 공정 표기」 · "
     "보류 재료에 들어온 자리 · 판단 · 후보)",
     _pv196("노칭공정X") is None and all(_an[k].get("hold") == PV196.HOLD_HUMAN and not _an[k].get("node_id") for k in ("A1", "A2"))
     and len(_oa) == 1 and _oa[0]["payload"]["gate"]["parent"] == "조립" and _oa[0]["payload"]["rows"] == 2,
     f"노드 {_pv196('노칭공정X')} · 보류 {[_an[k].get('hold') for k in ('A1', 'A2')]} · 재료 {(_oa or [{}])[0].get('payload', {}).get('gate')}")
_cn = [c["name"] for c in _rv["held"][0]["candidates"]]
show("B196 ⓖ 골격 칸 머리 줄의 수 = 표본의 실제(공정 표기 1종 · 골격에 0 · 문에 걸림 1종 2행 · 쌍 0 · ref 빈 행 0 · 판단 못 받음 0) · "
     "첫 판단의 후보는 판단이 낸 것만(큰 형제로 채우기 걷음 — B202 ① · 문에 걸린 뒤의 순위는 LLM)",
     (_rv["counts"]["표기"], _rv["counts"]["골격"], _rv["counts"]["문"], _rv["counts"]["문 행"], _rv["counts"]["쌍"],
      _rv["counts"]["ref 빈 행"], _rv["counts"]["판단 못 받음"]) == (1, 0, 1, 2, 0, 0, 0)
     and _cn == ["스태킹"] and "문에 걸림 1종(2행)" in SR196.head_line(_rv["counts"]),
     f"{SR196.head_line(_rv['counts'])} · 후보 {_cn}")

# ⓑ 처분 — 합침(후보 1) · 새로 · drop(사유) → 그 문서의 행부터 · drop은 재연결이 열지 않는다
_eb = _env196("B196B", [_rec196("B1", "노칭공정M", meta={"coord_judge": {"노칭공정M": _judged["노칭공정X"]}}),
                        _rec196("B2", "노칭공정K"), _rec196("B3", "노칭공정D")])
_did = (_ask196(_eb, "노칭공정M", "m 1"), _ask196(_eb, "노칭공정K", "k"), _ask196(_eb, "노칭공정D", "d 오기"))
_bn = _run196(_eb)
with contextlib.redirect_stdout(io.StringIO()):
    RT196.retry_orphans()
show("B196 ⓑ 좌표 단계 처분 — 합침(후보 1 → 스태킹 별칭 · 그 행은 스태킹) · 새로(잠정 노드 하나 · 그 행의 자리) · drop 「오기」(노드 0 · "
     "보류 「사람 drop」 · 재연결이 열지 않는다)",
     _did == ("합침", "새로", "drop") and (open_graph(coord_layer()).get(_bn["B1"]["node_id"]) or {}).get("canonical") == "스태킹"
     and bool(_pv196("노칭공정K")) and _bn["B2"]["node_id"] == (_pv196("노칭공정K") or {}).get("id")
     and _pv196("노칭공정D") is None and _bn["B3"].get("hold") == PV196.HOLD_DROP,
     f"{_did} · B1 → {(open_graph(coord_layer()).get(_bn['B1'].get('node_id')) or {}).get('canonical')} · K {bool(_pv196('노칭공정K'))} · "
     f"D {_bn['B3'].get('hold')}")

# ⓓ 처분 없이 끝난 문서 둘 → ops review 한 줄(행 수 합) → 합침 → 재연결이 보류 행을 잇는다(추출 LLM 0)
_run196(_env196("B196D1", [_rec196("D1", "노칭공정W"), _rec196("D2", "노칭공정W")]))
_run196(_env196("B196D2", [_rec196("E1", "노칭공정W")]))
_gw = [r for r in OR196.skeleton_cells("all") if r["kind"] == "gate" and r["surface"] == "노칭공정W"]
with contextlib.redirect_stdout(io.StringIO()):
    _dw = PA196.decide(_gw[0], "시험", answer="m 노칭")[0] if _gw else None
    RT196.retry_orphans()
_left = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor" and x["payload"].get("surface") == "노칭공정W"]
_cams = [n for n in open_graph("process").nodes.values() if n["canonical"].startswith("노칭::B196 카메라 ") and is_live(n)]
show("B196 ⓓ 처분 없이 끝난 문서 둘 → ops review 골격 칸 한 줄(문서 둘 · 행 3) → 합침(노칭) → ops relink가 보류 행을 잇는다 · 남은 보류 0",
     len(_gw) == 1 and _gw[0]["rows"] == 3 and sorted(_gw[0]["docs"]) == ["B196D1", "B196D2"] and _dw == "합침" and not _left
     and {n["canonical"] for n in _cams} >= {"노칭::B196 카메라 D1", "노칭::B196 카메라 D2", "노칭::B196 카메라 E1"},
     f"줄 {[(r['rows'], r['docs']) for r in _gw]} · 남은 보류 {len(_left)} · 붙은 값 {sorted(n['canonical'] for n in _cams)[:3]}")

# ⓔ 「봄」(이 회차 전에 선 잠정 노드 — 세움 기록 없이) → fresh 뒤 다시 넣어도 그 노드가 선다
PH196.seed("시험", "노칭공정V", "조립")
_ev = _env196("B196V", [_rec196("V1", "노칭공정V")])
_run196(_ev)
_nv = _pv196("노칭공정V")
store.write(store.OPS_LOG, [r for r in store.read(store.OPS_LOG, []) if r.get("op") != PH196.OP_SEED
                            or (r.get("detail") or {}).get("surface") != "노칭공정V"])       # 옛 노드처럼 — 세움 기록 없음
with contextlib.redirect_stdout(io.StringIO()):
    PH196.keep("시험", _nv["id"])
    for _l in ("process", "quality"):           # 재구축의 그래프 비움 — 사람 판단 기록(②등록)은 남는다
        _gg = open_graph(_l)
        _gg.nodes.clear()
        _gg.edges.clear()
        _gg.save()
        bootstrap(_l, echo=False)
_av = _run196(_env196("B196V", [_rec196("V1", "노칭공정V")]))
show("B196 ⓔ 「봄」 기록(세움 기록 없이 — 이 회차 전에 선 잠정 노드) → 그래프를 비우고(재구축) 다시 넣어도 그 노드가 선다",
     bool(_nv) and bool(_pv196("노칭공정V")) and _av["V1"].get("node_id") == _pv196("노칭공정V")["id"],
     f"전 {bool(_nv)} · 뒤 {bool(_pv196('노칭공정V'))} · V1 {_av['V1'].get('canonical')}")

# ⓕ 쌍 어긋남 — 확인 전 보류 · 확인(a) → ref 자리 · 정정(r) → 그 상위 아래 노드(극성 쌍은 없다 — 기대 변경 B198)
_ef = _env196("B196F", [_rec196("F1", "노칭", grp="스태킹"), _rec196("F2", "탭용접", grp="노칭"),
                        _rec196("F3", "노칭", grp="노칭", electrode_type="anode")])   # 극성 행은 그냥 붙는다(ⓗ의 재료)
_f0 = _run196(_ef)
_pr = [r for r in SR196.pairs_from_queue() if r["up"] in ("스태킹", "노칭")]
_ra = _ask196(_ef, "노칭", "a")
_rr = next((r for r in PA196.rows_of({"pairs": _pr}) if r["ref"] == "탭용접"), None)
with contextlib.redirect_stdout(io.StringIO()):
    _dr = PA196.decide(_rr, "시험", answer="m 1")[0] if _rr else None
    RT196.retry_orphans()
_f1 = {r["locator"]: r for r in (LG.read("B196F") or {}).get("rows") or [] if r.get("role") == "anchor"}
_g = open_graph(coord_layer())
_fix = (CA.answers().get(CA.key(CP.GROUP, ("노칭", "탭용접"))) or (None, {}))[1].get("target")
show("B196 ⓕ 쌍 어긋남(상위 스태킹 · ref 노칭) → 확인 전 보류 · a → 노칭에 · m 1(정정 — 노칭 아래 후보 · B202 ③) → 그 노드에",
     _f0["F1"].get("hold") == CS196.HOLD_PAIR and _f0["F2"].get("hold") == CS196.HOLD_PAIR
     and _ra == "확인" and _dr == "정정" and (_g.get(_f1["F1"].get("node_id")) or {}).get("canonical") == "노칭"
     and _fix and str(_fix).startswith("노칭::") and (_g.get(_f1["F2"].get("node_id")) or {}).get("canonical") == _fix,
     f"전 {[_f0[k].get('hold') for k in ('F1', 'F2')]} · F1 → {_f1['F1'].get('canonical')} · F2 → {_f1['F2'].get('canonical')}(정정 {_fix})")

# ⓗ 연결 표지 — 대장 칸 · 인입 끝 줄과 show report의 「연결 미성립 n(…)」 · 「좌표 폴백」 · 「ref 빈 행」
from cli import report_cause as RC196                               # noqa: E402
_lr = (LG.read("B196F") or {}).get("rows") or []
_lc = LG.link_counts(_lr)
_hl = [ln for ln in RC196.report("B196F")[0] if "연결 미성립" in ln]
show("B196 ⓗ 연결 표지 — 규칙 B 폴백으로 좌표에 선 값은 대장 연결 칸 connect=rel_fallback · show report 머리 「연결 미성립 n(소유자 미해소 · 관계 폴백 · "
     "소속 폴백)」 · 「ref 빈 행 n」이 대장에서 센 수",
     any(r.get("connect") == "rel_fallback" for r in _lr) and _lc["관계 폴백"] == sum(1 for r in _lr if r.get("connect") == "rel_fallback")
     and _hl and f"연결 미성립 {_lc['연결 미성립']:,} (소유자 미해소 {_lc['소유자 미해소']:,}" in _hl[0] and "ref 빈 행" in _hl[0],
     f"{_lc} · {(_hl or [''])[0].strip()}")
_unregister("process")
_clean_acks()

# ────────────────────────────────────────────────────────────── B197 골격 단의 문 (창작 표본 · mock · 겸 선언이 있는 시험 config)
print("\n■ B197 — 겸 값은 골격 노드로만 · 판정 전 처분 · 쌍별 예고 · 쓰기 전 판정 결과")
from core.build import also_gate as AG197, also_stage as AS197                 # noqa: E402
from cli import also_screen as ASC197                                          # noqa: E402
overlay(also=True)                                # Process가 sub · detail 단에서 Unit을 겸한다(공통 also) — 노칭(sub) 아래 detail 넷
_dt196 = _register_table("process")              # 클린이 등록부를 비웠다 — 표 문서 종류(개체 칸 = Unit)를 다시


def _prose197(did, chunks, outline=None, hints=None):
    (HINTS / f"{did}.json").write_text(json.dumps(hints or {}, ensure_ascii=False), encoding="utf-8")
    if outline:
        (HINTS / f"{did}@outline.json").write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
    _made.append(did)
    pcs = [{**C1, "source_locator": loc, "doc_type": "ppt_process", "process_ref": "노칭", "text": t,
            "meta": {"section_path": path} if path else {}} for loc, path, t in chunks]
    return {**PROSE, "doc_id": did, "doc_type": "ppt_process", "source_path": f"{did}.pptx", "doc_coord": "노칭",
            "chunks": TG.tag(pcs, nodes=TG.closed_list("process"), doc_type="ppt_process")}


def _h197(did, name="추출부"):
    """제목 「2. <name>」 — 사람 답은 표기 + 자리로 남으니 경우마다 다른 이름(같은 이름이면 앞 경우의 답이 선다 — 그것이 규칙)."""
    return _prose197(did, [("H-1", "1. 개요", "범위는 노칭이다."), ("H-2", f"2. {name}", "흡착력은 5N이다.")],
                     outline={f"2. {name}": {"name": name, "category": "Unit"}},
                     hints={"H-1": {"entities": [{"surface": "범위", "category": "Property"}], "relations": []},
                            "H-2": {"entities": [{"surface": "흡착력", "category": "Property"}], "relations": []}})


def _go197(env, answer=None, stop_at=None):
    """인입 — 골격 단 줄에 `answer`(m · k · d · u)를 그 자리에서 · `stop_at` 단계에서 False(멈춤) · 돌려주는 것은 알림 목록."""
    notes = []

    def nt(info):
        notes.append(info)
        if info.get("단계") == "골격단" and answer:
            with contextlib.redirect_stdout(io.StringIO()):
                for r in info["rows"]:
                    PA196.decide(r, "시험", answer=answer)
        return False if info.get("단계") == stop_at else None
    with contextlib.redirect_stdout(io.StringIO()):
        run_document(env, notice=nt, allow_duplicate=True)
    return notes


def _names197():
    return {n["canonical"] for n in open_graph("process").nodes.values() if is_live(n)}


# ⓐ 제목 「2. 추출부」 → 목차 노드화 Unit → [3/8] 문(노드 0 · 후보 = 노칭 아래 골격)
_na = _go197(_h197("B197A"))
_ga = [r for n in _na if n.get("단계") == "골격단" for r in n["rows"]]
from core.state import gate_judge as GJ197                                     # noqa: E402
_ca = GJ197.listing("노칭")
show("B197 ⓐ 산문 · 문서 좌표 노칭(골격 자식 넷) · 제목 「2. 추출부」 → Unit → [3/8] 골격 단 줄(위 공정 노칭) · 노드 0 · LLM이 볼 골격 목록 = "
     "노칭 아래 골격(B202 ①)",
     len(_ga) == 1 and _ga[0]["surface"] == "추출부" and _ga[0]["up_name"] == "노칭"
     and not any("추출부" in c for c in _names197()) and len(_ca) == 4 and all(c["path"].startswith("조립 › 노칭 › ") for c in _ca),
     f"{[(r['surface'], r['up_name'], r['answer']) for r in _ga]} · 목록 {[c['name'] for c in _ca]}")

# ⓑ 처분 넷 — m(골격 별칭 · 그 아래 값이 그 노드 아래) · k(잠정 골격 노드 · 그 아래 값) · d(그 아래 청크 추출 0 · 값 0) · u(노드 0 · 값은 노칭)
_out = {}
for _k, _ans in (("m", "m 노칭::노칭 타발"), ("k", "k"), ("d", "d 설계 항목"), ("u", "u")):
    _did = f"B197B{_k}"
    _go197(_h197(_did, f"추출부{_k}"), answer=_ans)
    _ck = json.loads(_P.work("extract", f"{_did}.json").read_text(encoding="utf-8"))
    _out[_k] = ({c for c in _names197() if c.endswith("흡착력")}, [c for c in _ck["candidates"] if c.get("human_drop")])
show("B197 ⓑ m → 「노칭::노칭 타발::흡착력」 · k → 잠정 「추출부」 아래 · d → 그 제목 아래 청크 추출 0(사람 drop) · 값 0 · u → 노드 0 · 값은 노칭",
     "노칭::노칭 타발::흡착력" in _out["m"][0] and "추출부k::흡착력" in _out["k"][0] and _out["d"][1]
     and _out["d"][0] == _out["k"][0] and "노칭::흡착력" in _out["u"][0] and "추출부k" in _names197()
     and not {"추출부m", "추출부d", "추출부u"} & _names197(),
     " · ".join(f"{k} {sorted(v[0])}" for k, v in _out.items()))

# ⓒ 청크 본문의 Unit 「센서」(청크 좌표 노칭) → [5/8] 머리 문 · 같은 처분(u → 소속 값이 노칭에)
_ec = _prose197("B197C", [("C-1", None, "센서는 레이저 센서다. 응답 시간은 5ms다.")], hints={"C-1": {"entities": [
    {"surface": "센서", "category": "Unit"},
    {"surface": "응답 시간", "category": "Property", "belongs_to": {"name": "센서", "category": "Unit", "from": "본문"}}],
    "relations": []}})
_nc = _go197(_ec)
_gc = [r for n in _nc if n.get("추출뒤") for r in n.get("골격단") or []]
with contextlib.redirect_stdout(io.StringIO()):
    PA196.decide(_gc[0], "시험", answer="u") if _gc else None
_go197(_ec)
show("B197 ⓒ 본문 Unit 「센서」 → [5/8] 머리 골격 단 줄 · 처분 u → 노드 0 · 소속 값 「응답 시간」은 노칭 아래",
     len(_gc) == 1 and _gc[0]["surface"] == "센서" and "노칭::응답 시간" in _names197()
     and not any(c.endswith("센서") for c in _names197()),
     f"{[(r['surface'], r['up_name']) for r in _gc]}")

# ⓓ 표 — ref 빈 행 · group 노칭 · Unit 칸 → 같은 문 · ref(맨 아래 단 노칭 타발)가 있는 행의 Unit 값 → 지금처럼 자동
_ed = _env196("B197D", [_rec196("D1", None, grp="노칭"), _rec196("D2", "노칭 타발", grp="노칭")])
_run196(_ed)
_qd = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor" and x.get("doc_id") == "B197D"
       and x["payload"].get("also")]
_d2 = next((r for r in (LG.read("B197D") or {}).get("rows") or [] if r.get("role") == "entity" and r.get("locator") == "D2"), {})
show("B197 ⓓ 표 행(ref 빈칸 · group 노칭)의 Unit 값 → 골격 단 보류(노드 0) · ref 노칭 타발(맨 아래 단) 행의 Unit 값 → 문 밖(지금처럼 판정 · 노드)",
     [x["payload"]["surface"] for x in _qd] == ["B196 카메라 D1"] and _d2.get("node_id") and not _d2.get("hold")
     and not any(c.endswith("B196 카메라 D1") for c in _names197()),
     f"보류 {[x['payload']['surface'] for x in _qd]} · D2 {_d2.get('verdict')} → {_d2.get('target')}")

# ⓔ 건너뜀 → ops review 한 줄 → 합침 → ops relink → 보류 값이 붙는다(추출 LLM 0)
_go197(_prose197("B197E", [("E-1", None, "감지기는 레이저 감지기다. 감지 거리는 5mm다.")], hints={"E-1": {"entities": [
    {"surface": "감지기", "category": "Unit"},
    {"surface": "감지 거리", "category": "Property", "belongs_to": {"name": "감지기", "category": "Unit", "from": "본문"}}],
    "relations": []}}))
_ge = [r for r in OR196.skeleton_cells("all") if r["kind"] == "gate" and r["surface"] == "감지기"]
with contextlib.redirect_stdout(io.StringIO()):
    _de = PA196.decide(_ge[0], "시험", answer="m 노칭::비전검사")[0] if _ge else None
    RT196.retry_orphans()
show("B197 ⓔ 건너뜀 → ops review 골격 단 한 줄(겸 값) → 합침(노칭::비전검사) → ops relink → 「노칭::비전검사::감지 거리」",
     len(_ge) == 1 and _ge[0].get("also") == "Unit" and _de == "합침" and "노칭::비전검사::감지 거리" in _names197(),
     f"{[(r['surface'], r.get('also')) for r in _ge]} · {_de}")

# ⓖ [3/8] 끝 줄 「확정한 공정」 · [5/8] 쌍별 예고(붙을 자리 · 연결 · 판정 예정 · 칸 안 잘림) · 표 [4/7] 같은 함수
_ng = _go197(_h197("B197G", "취출부"), answer="m 노칭::노칭 타발")
_pl = [n["줄"] for n in _ng if n.get("단계") == "확정공정"]
_pv = AS197.preview_lines(next(n for n in _ng if n.get("추출뒤"))["쌍별"], full=True)     # 전부(md 몸 — 화면은 요약 · B199 ①)
_tv = AS197.preview_lines(AS197.preview(AS197.builder(_ed), _ed, schema={"fields": {"개체": {"role": "entity", "category": "Unit"}}}),
                          full=True)
show("B197 ⓖ 확정한 공정 — 청크 2: 노칭 › 노칭::노칭 타발 1 · 노칭(상위만) 1 · 쌍별 예고 묶음 머리 = 그 쌍 · 줄에 붙을 자리 · 연결 · 판정 예정 · "
     "표 [4/7]도 같은 함수(골격 단 — 문 · 맨 아래 단 아래는 새 노드)",
     _pl and "노칭 › 노칭::노칭 타발 1" in _pl[0] and "노칭(상위만) 1" in _pl[0]
     and any(ln.strip().startswith("노칭 › 노칭::노칭 타발") for ln in _pv)
     and any("흡착력" in ln and ln.split("붙을 자리(판정 전) ")[1].startswith("노칭::노칭 타발  ") and "has_property" in ln
             and ln.rstrip().endswith(("사전 연결", "새 노드", "→ 판정")) for ln in _pv)
     and any("골격 단 — 문" in ln for ln in _tv) and any("후보 0 → 새 노드" in ln or "후보" in ln for ln in _tv),
     f"{(_pl or [''])[0]} · {[ln.strip() for ln in _pv][:3]} · 표 {[ln.strip() for ln in _tv]}")

# B199 ① 화면은 쌍마다 요약 · 전부는 export/plan_<doc>.md(같은 원자 쓰기 손 — 줄을 자르지 않는다)
from cli import also_screen as ASC199                                    # noqa: E402
from core import paths as _P199                                          # noqa: E402
_g199 = next(n for n in _ng if n.get("추출뒤"))["쌍별"]
_sc199 = ASC199.preview_screen(_g199, "B197G")
_md199 = _P199.export(ASC199.plan_md_name("B197G")).read_text(encoding="utf-8")
show("B199 ① 쌍별 예고 — 화면은 쌍마다 한 줄(값 n — 사전 연결 · 새 노드 · 판정) · md에 전부(전 줄 그대로)",
     all(ln.strip() in _md199 for ln in AS197.preview_lines(_g199, full=True))
     and any(" — 사전 연결 " in ln and " · 새 노드 " in ln for ln in _sc199) and "plan_B197G.md" in _sc199[-1]
     and not any("붙을 자리(판정 전) " in ln for ln in _sc199[1:-1]),
     f"화면 {len(_sc199)}줄 · md {len(_md199.splitlines())}줄")

# ⓗ 쓰기 전 판정 결과 → q → 그래프 · 사전 · 큐 0 · 대장 중간 저장 → 다시 넣으면 재생(판정 LLM 0) · c → 지금과 같은 그래프
from core import matcher as MT197                                    # noqa: E402
_eh = _prose197("B197H", [("Q-1", None, "노즐 압력은 3bar다.")],
                hints={"Q-1": {"entities": [{"surface": "노즐 압력", "category": "Property"}], "relations": []}})
_n0, _q0 = _names197(), len(store.read(store.QUEUE, []))
_nh = _go197(_eh, stop_at="판정결과")
_rh = [n for n in _nh if n.get("단계") == "판정결과"]
_mid = (_n0 == _names197(), len(store.read(store.QUEUE, [])) == _q0, LG.read("B197H") is None,
        store.path(LG.partial_name("B197H")).exists())
MT197.STATS["판정"] = 0
_go197(_eh)
show("B197 ⓗ 판정 결과(쓰기 전 · 쌍마다 match · new · uncertain) → q → 그래프 · 큐 0 · 확정 대장 없음 · 중간 저장 남음 → 다시 넣으면 "
     "재생(판정 LLM 0) · 노드가 선다",
     _rh and "new 1" in " ".join(_rh[0]["줄"]) and all(_mid) and MT197.STATS["판정"] == 0 and "노칭::노즐 압력" in _names197(),
     f"{_rh[0]['줄'] if _rh else '-'} · 중간 {_mid} · 판정 {MT197.STATS['판정']}")
init.init(fresh_=True, all_=True)

for d in set(_made):
    (HINTS / f"{d}.json").unlink(missing_ok=True)
    (HINTS / f"{d}@outline.json").unlink(missing_ok=True)
done()
