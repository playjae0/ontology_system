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
HINTS = FX / "extract_hints"
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
     and "좌표 쌍 — 어긋남 2쌍(2행)" in _out and "좌표 쌍 어긋남 2쌍(2행)" in _g2,
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

for d in set(_made):
    (HINTS / f"{d}.json").unlink(missing_ok=True)
done()
