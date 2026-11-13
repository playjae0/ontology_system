# -*- coding: utf-8 -*-
"""G6 ⑲ 동의어 학습 — auto 노드 매칭(문서를 가리지 않는다) · 좌표 학습 보존 · 새 공정 후보 · 별칭 출처 · 불확실 일괄
검토 · 극성 values 경고 (B101).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 판정 점수는 시험이
유사도 함수에 주입한다(LLM 판정 대역 — 임계 이상 0.9 · 임계 아래 0.6). 형태(표·산문) × 층(process · quality)에서 같은
성질을 잰다(CLAUDE.md §4 범용성).

잠그는 성질:
  ⓐ auto 노드에 변형 표기가 판정(임계 이상)으로 매칭 · 별칭(출처 LLM 매칭) — 같은 문서도 다른 문서도 같은 기준
     (B172 — 가드 걷음) / 임계 아래는 uncertain + 가장 가까운 후보(B172 ⓑ)
  ⓑ 좌표 학습: 문서 A에서 채택한 표기가 문서 B에서 LLM 0으로 맞는다 · 예고 「학습 적중」 · null은 같은 닫힌 목록
     판이면 B에서 다시 묻지 않는다(B107 ② 기억) · 거부 뒤 다시 묻는다 · 승격 + bootstrap 뒤 사람 보증 별칭(정확
     일치)으로 맞는다 · 판이 바뀌어 null은 다시 묻는다
  ⓒ 새 공정 후보: null 표기가 행·문서와 함께 보이고(`show learned`) · 다음 줄대로 골격에 더하면 다음 인입
     마무리에서 붙는다
  ⓓ 별칭 출처: `show node`가 LLM 매칭 · 사람(merge — 분류는 표기 대장과 같은 함수) · 골격 · 좌표 학습을 가른다
  ⓔ 일괄 검토: 비대화형은 계획만(쓰기 0) · 합침·별개·건너뜀이 `ops` 함수로 · 합침 뒤 끝점 없는 엣지 0
  ⓕ 극성 values 경고 — 묶은 층과 집의 values가 다르다 · 선언 층과 집의 축이 다르다(층 둘) · 맞추면 0
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401

from core import matcher as MT                  # noqa: E402
from core.build import ledger as LG             # noqa: E402
from core.state import coord_learn as CL        # noqa: E402
from core.state.world import World              # noqa: E402
from parser import tagger as TG                 # noqa: E402
from cli import ops_review as OR, show as SH, show_learn as SL   # noqa: E402

from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS
MATRIX = [("표", "process", "Unit"), ("표", "quality", "Failure"),
          ("산문", "process", "Unit"), ("산문", "quality", "Failure")]
BASE, VAR = "B101 유량계", "B101 유량 감지기"
VAR2 = "B101 유량 계측기"                          # 다른 문서의 변형 표기 — 임계 이상(B172 ⓐ)
OTHERS = ["B101 유량 측정기", "B101 유량 센서", "B101 유량 검출기"]   # 임계 아래(B172 ⓑ)


def _fresh():
    init.init(fresh_=True, all_=True)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


_real_sim = MT._similarity


def _sim(a, b):
    """판정 대역 — 변형 표기 ↔ 기준 표기는 0.9(임계 이상 · 1.0 미만) · 다른 표기 ↔ 기준 표기는 0.6(임계 아래).
    나머지는 원래 함수."""
    if BASE in str(b) and any(v in str(a) for v in (VAR, VAR2)):
        return 0.9
    if BASE in str(b) and any(v in str(a) for v in OTHERS):
        return 0.6
    return _real_sim(a, b)


def _reg_table(dt, layer, cat):
    p = _P.schemas(f"{dt}.json")
    _P.ensure(p)
    p.write_text(json.dumps({"doc_type": dt, "schema_version": 1, "layer": layer,
                             "use_blocks": ["common_core", "process_coord"],
                             "fields": {"개체": {"role": "entity", "category": cat}}, "edges": []},
                            ensure_ascii=False), encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[dt] = {"doc_type": dt, "status": "registered", "layer": layer, "schema": f"schemas/{dt}.json",
               "adapter": "-", "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _unreg(dts_):
    d = store.read(store.DOC_TYPES, {})
    for dt in dts_:
        d.pop(dt, None)
        _P.schemas(f"{dt}.json").unlink(missing_ok=True)
    store.write(store.DOC_TYPES, d)


def _env(form, lay, cat, doc_id, surfaces, ref="노칭"):
    """같은 모양의 창작 문서 — 표는 행마다 한 표기 · 산문은 청크마다 한 표기."""
    if form == "표":
        dt = f"b101t{lay[0]}"
        _reg_table(dt, lay, cat)
        env = load("CP01")
        base = {k: v for k, v in env["records"][0].items()
                if k not in ("설비", "관리항목", "규격", "측정방법", "대응계획")}
        recs = [dict(base, source_locator=f"S{i}", doc_type=dt, process_ref=ref, 개체=s)
                for i, s in enumerate(surfaces, 1)]
        return {**env, "doc_id": doc_id, "doc_type": dt, "records": recs}
    dt = "ppt_" + lay
    (HINTS / f"{doc_id}.json").write_text(json.dumps({
        f"{doc_id}-C{i:03d}": {"entities": [{"surface": s, "category": cat}], "relations": [], "attach": []}
        for i, s in enumerate(surfaces, 1)}, ensure_ascii=False), encoding="utf-8")
    return {"doc_id": doc_id, "doc_type": dt, "payload_kind": "prose", "source_path": f"{doc_id}.pptx",
            "revision": "R1", "parsed_at": "2026-10-06T00:00:00", "parser_version": "p1-1.0",
            "adapter_version": "b-1.0",
            "chunks": [{"source_locator": f"{doc_id}-C{i:03d}", "doc_type": dt, "process_group": "조립",
                        "process_ref": ref, "electrode_type": "both", "text": f"{s} 이야기",
                        "section": "슬라이드 1", "meta": {}} for i, s in enumerate(surfaces, 1)]}


def _node(name_part):
    return next(n for _l, n in World().nodes() if name_part in n["canonical"] and ops.is_live(n))


def _show_node(name):
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        SH.cmd_node([name])
    return b.getvalue()


print("\n■ B172 auto 노드에 LLM 매칭(같은 문서 · 다른 문서) · 임계 아래 불확실 · B101 ⑤ 일괄 검토 · ④ 별칭 출처")
_ok_a, _ok_d, _ok_e = [], [], []
MT._similarity = _sim
try:
    for form, lay, cat in MATRIX:
        _fresh()
        da, db = f"B101A{form[0] == '표' and 'T' or 'P'}{lay[0].upper()}", \
            f"B101B{form[0] == '표' and 'T' or 'P'}{lay[0].upper()}"
        run_document(_env(form, lay, cat, da, [BASE, VAR]))
        res_a = (LG.read(da) or {}).get("result") or {}
        rows_a = [r for r in (LG.read(da) or {}).get("rows") or [] if r.get("surface") == VAR]
        base = _node(BASE)
        al = {a["surface"]: a for a in base.get("aliases") or []}
        run_document(_env(form, lay, cat, db, [VAR2] + OTHERS))
        rows_b = [r for r in (LG.read(db) or {}).get("rows") or [] if r.get("surface") == VAR2]
        um = [x for x in store.read(store.QUEUE, []) if x["kind"] == "uncertain_match" and x["doc_id"] == db]
        near_ok = all((x["payload"].get("nearest") or {}).get("id") == base["id"] for x in um)
        _ok_a.append((form, lay, rows_a and rows_a[0]["verdict"] == "match" and rows_a[0]["node_id"] == base["id"]
                      and (al.get(VAR) or {}).get("by") == "LLM 매칭" and res_a.get("LLM 별칭", 0) >= 1
                      and rows_b and rows_b[0]["verdict"] == "match" and rows_b[0]["node_id"] == base["id"]
                      and _node(BASE)["status"] == "auto"
                      and len(um) == len(OTHERS) and near_ok,
                      f"A: {rows_a and rows_a[0]['verdict']} · LLM 별칭 {res_a.get('LLM 별칭')} · "
                      f"B: {VAR2} {rows_b and rows_b[0]['verdict']} · 불확실 {len(um)}"))
        # ⑤ 일괄 검토 — 비대화형은 계획만
        a = SimpleNamespace(layer="all", actor="B101시험")
        q0 = json.dumps(store.read(store.QUEUE, []), sort_keys=True, ensure_ascii=False)
        nodes0 = sorted(n["id"] for _l, n in World().nodes())
        with contextlib.redirect_stdout(io.StringIO()):
            OR.run(a)                                # 시험 stdin은 터미널이 아니다 — 계획만
        plan_only = (json.dumps(store.read(store.QUEUE, []), sort_keys=True, ensure_ascii=False) == q0
                     and sorted(n["id"] for _l, n in World().nodes()) == nodes0)
        answers = iter(["m", "c", "s"])
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            OR.run(a, ask=lambda _q: next(answers))
        left = OR.items("all")
        gone = World().get(um[0]["payload"]["node_id"]) if um else None
        conf = World().get(um[1]["payload"]["node_id"]) if len(um) > 1 else None
        _ok_e.append((form, lay, plan_only and "합침 1 · 별개 1 · 건너뜀 1" in b.getvalue()
                      and (gone or {}).get("status") == "merged_into" and (conf or {}).get("status") == "confirmed"
                      and len(left) == 1 and not World().dangling(),
                      f"계획만 쓰기 0 {plan_only} · {b.getvalue().strip().splitlines()[-1]} · 남은 검토 {len(left)} · "
                      f"끝점 없는 엣지 {World().dangling() or 0}"))
        # ④ 별칭 출처 — LLM 매칭 · 사람(merge)
        out = _show_node(BASE)
        _ok_d.append((form, lay, f"{VAR}  ← LLM 매칭(확신 0.9" in out and f"{OTHERS[0]}  ← 사람(merge" in out
                      and f"{VAR}  ← 사람" not in out,
                      " / ".join(l.strip() for l in out.splitlines() if "←" in l)[:160]))
        (HINTS / f"{da}.json").unlink(missing_ok=True)
        (HINTS / f"{db}.json").unlink(missing_ok=True)
        _unreg([f"b101t{lay[0]}"])
finally:
    MT._similarity = _real_sim
show("B172 ⓐⓑ auto 노드에 변형 표기가 임계 이상이면 붙는다 — 같은 문서도 다른 문서도(별칭 LLM 매칭) / 임계 아래는 "
     "uncertain + 가장 가까운 후보 (표·산문 × 층 둘 · 고침 — 옛 기대: 다른 문서는 가드 · 대장 same_doc · 결과표의 수)",
     all(o for _f, _l, o, _d in _ok_a), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_a))
show("ⓔ 일괄 검토 — 비대화형은 계획만(쓰기 0) · 합침(m)·별개(c)·건너뜀(s)이 ops 함수로 · 끝점 없는 엣지 0 "
     "(표·산문 × 층 둘)", all(o for _f, _l, o, _d in _ok_e), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_e))

print("\n■ B101 ② 좌표 학습 보존 · ③ 새 공정 후보 (표·산문 × 층 둘)")
LEARN, NULLX = "노칭 B101공정", "없는공정 B101"
_ok_b = []
from core.state.bootstrap import coord_layer      # noqa: E402
for form, lay, _cat in MATRIX:
    _fresh()
    coord = coord_layer()
    dt = ("cp" if lay == "process" else "pfmea") if form == "표" else "ppt_" + lay
    calls = []

    def pick(ref, cands, **_k):          # 판단 꼴(B181 ① · 고침)
        calls.append(ref)
        return ({"type": "match", "matched_id": next(c["id"] for c in cands if c["canonical"] == "노칭"), "confidence": 0.9}
                if ref == LEARN else {"type": "new", "matched_id": None, "confidence": 0.9})

    def run_tag(doc):
        notes = []
        pcs = [{"source_locator": f"{doc}-{i}", "process_ref": r, **({"text": "x"} if form == "산문" else {})}
               for i, r in enumerate([LEARN, LEARN, NULLX])]
        del calls[:]
        out = TG.tag(pcs, layer=coord, pick=pick, doc_type=dt, notice=notes.append, doc_id=doc)
        plan = next(n for n in notes if n.get("단계") == "예고")
        return out, plan, list(calls)

    oa, pa, ca = run_tag("DA")
    ob, pb, cb = run_tag("DB")
    rec = CL.book()["채택"].get(LEARN) or {}
    CL.reject(LEARN, "B101시험")
    oc, pc, cc = run_tag("DC")
    CL.promote(LEARN, "B101시험")
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], capture_output=True, text=True,
                       cwd=str(ROOT), stdin=subprocess.DEVNULL)
    od, pd, cd = run_tag("DD")
    _ok_b.append((form, lay, ca == [LEARN, NULLX] and cb == [] and pb.get("기억_종수") == 1 and pb["학습_적중"] == 1
                  and pb["학습_적중_행"] == 2 and ob[0]["process_ref"] == "노칭"
                  and ob[0]["meta"]["coord_tag_source"] == "learned" and rec.get("출처") == TG.LEARN_SOURCE
                  and rec.get("doc_id") == "DA" and cc == [LEARN] and r.returncode == 0
                  and cd == [NULLX] and pd["학습_적중"] == 0 and od[0]["process_ref"] == LEARN
                  and LEARN not in CL.book()["채택"],
                  f"A 호출 {ca} · B 호출 {cb} 학습 적중 {pb['학습_적중']}종(행 {pb['학습_적중_행']}) · 목록 밖(기억) {pb.get('기억_종수')}종 · "
                  f"거부 뒤 C 호출 {cc} · 승격+bootstrap 뒤 D 호출 {cd}(정확 일치 {pd['정확_일치']})"))
# ③ 다음 줄대로 골격에 더하면 다음 인입 마무리에서 붙는다 — 표·산문 × 층 둘
_ok_c2 = []
for form, lay, cat in MATRIX:
    _fresh()
    hold_coords()                   # 목록 밖 좌표는 보류로(B182 — 이 시험은 보류 → 골격 별칭 + bootstrap → 다음 마무리를 잰다)
    did = f"B101N{form[0] == '표' and 'T' or 'P'}{lay[0].upper()}"
    env = _env(form, lay, cat, did, ["B101 새 공정 설비"], ref=NULLX)
    run_document(env)
    finalize()

    def _mine():
        return [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == did
                and NULLX in json.dumps(x.get("payload"), ensure_ascii=False)]
    q0 = _mine()
    skp = _P.layers("process", "skeleton.json")
    sk = json.loads(skp.read_text(encoding="utf-8"))
    sk["ALIASES"].setdefault("노칭", []).append(NULLX)
    skp.write_text(json.dumps(sk, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], capture_output=True, text=True,
                   cwd=str(ROOT), stdin=subprocess.DEVNULL)
    finalize()
    q1 = _mine()
    _ok_c2.append((form, lay, bool(q0) and not q1, f"보류 {len(q0)} → {len(q1)} ({sorted({x['kind'] for x in q0})})"))
    (HINTS / f"{did}.json").unlink(missing_ok=True)
    _unreg([f"b101t{lay[0]}"])
    hold_coords(False)
show("ⓑ 좌표 학습 — A 채택 → B LLM 0(예고 학습 적중) · null은 같은 판이면 기억(B107 ②) · 거부 뒤 다시 묻는다 · "
     "승격+bootstrap 뒤 사람 보증 정확 일치 · 판이 바뀌어 null은 다시 묻는다 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_b), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_b))
show("ⓒ 보류된 좌표 표기 — 다음 줄대로 골격에 더하면 다음 인입 마무리에서 붙는다 (표·산문 × 층 둘 · 고침 B182 — 새 공정 후보 "
     "화면은 잠정 골격 노드 목록 · 옛 null 기록 화면의 어서션은 지움)",
     all(o for _f, _l, o, _d in _ok_c2),
     " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_c2))

# ④ 별칭 출처 — 골격 · 좌표 학습 (골격 노드)
_fresh()
TG.tag([{"source_locator": "x", "process_ref": LEARN}], layer=coord_layer(), pick=lambda r, c, **_k: {"type": "match", "confidence": 0.9, "matched_id": next(x["id"] for x in c if x["canonical"] == "노칭")},
       doc_type="cp", doc_id="DS")
_sk = _show_node("노칭")
_ok_d.append(("골격", coord_layer(), "← 골격" in _sk and f"{LEARN}  ← 좌표 학습(DS" in _sk,
              " / ".join(l.strip() for l in _sk.splitlines() if "좌표 학습" in l)[:120]))
show("ⓓ 별칭 출처 — show node가 LLM 매칭(확신·문서) · 사람(merge — 분류는 대장과 같은 함수) · 골격 · 좌표 학습을 가른다 (표·산문 × 층 둘 + 골격)",
     all(o for _f, _l, o, _d in _ok_d), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_d))

# ── B200 동의어 점검 — 규칙 점검 · LLM 검토(mock 창작 답) · 승인 → 반영 · 골격에서 빠진 seed 별칭 걷기 · 공유 별칭 보류 문면
from core.state import alias_approve as AP, alias_audit as AA, alias_review as AR, alias_book as AB, oplog as OL  # noqa: E402
from core.state import surface_book as SB                              # noqa: E402
from cli.viewer import alias as VA                                     # noqa: E402

fresh()
_P.ensure(_P.parsed())
for _d in ("CP01", "PFMEA01"):                       # 봉투 — 실경로의 인입이 남기는 자리(붙은 행의 바탕)
    (_P.parsed(f"{_d}.json")).write_text(json.dumps(load(_d), ensure_ascii=False), encoding="utf-8")


def _boot():
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], capture_output=True, text=True,
                          cwd=str(ROOT), stdin=subprocess.DEVNULL).stdout


def _gbytes():
    from core.graph import GraphStore
    return {lay: GraphStore.for_layer(lay)._path.read_bytes() for lay in ("process", "quality")}


# ⓐ bootstrap 끝 한 줄 · 공유에 「비전 검사」(노드 셋) · 뷰어 묶음과 같은 수 · 점검 · 화면은 그래프 바이트 0
_out = _boot()
_ln = next((l for l in _out.splitlines() if "동의어 —" in l), "")
_g0 = _gbytes()
_view = VA.aliases()
_vis = sorted({p["target"]["canonical"] for g in _view["groups"] for p in g["pairs"] if p["surface"] == "비전 검사"})
show("B200 ⓐ bootstrap 「동의어 — 공유 n …」 한 줄 · 공유 「비전 검사」 노드 셋 · 뷰어 묶음의 공유 수 같다 · 점검 · 화면 쓰기 0",
     f"공유 {_view['counts']['shared']}" in _ln and len(_vis) == 3 and _gbytes() == _g0, f"{_ln.strip()} · {_vis}")

# ⓑ 골격에서 지운 seed 별칭 → bootstrap이 노드 · 사전에서 걷는다 · 붙어 있던 행(CP01) · 재인입은 사전 연결이 아니다
_skp = _P.layers("process", "skeleton.json")
_sk = json.loads(_skp.read_text(encoding="utf-8"))
_sk["ALIASES"]["탭용접"].remove("cathode 탭용접")
_skp.write_text(json.dumps(_sk, ensure_ascii=False, indent=2), encoding="utf-8")
_out = _boot()
_tw = node_by("process", "탭용접")
_held = [x for x in q_of("orphan_anchor", "CP01")]
run_document(load("CP01"))
finalize()
_c12 = [x for x in q_of("orphan_anchor", "CP01") if (x.get("payload") or {}).get("provenance") == "CP01#C12"]
show("B200 ⓑ 골격에서 지운 seed 별칭 — 노드 · 사전에서 걷음 · 「걷음 1 — 붙어 있던 행 …(CP01)」 · 재인입에서 C12 보류(사유 한 줄)",
     "cathode 탭용접" not in [a["surface"] for a in _tw["aliases"]] and not Dictionary.open().lookup("cathode 탭용접")
     and "seed 별칭 1 걷음 — 붙어 있던 행 1(문서 CP01)" in _out and len(_c12) == 1,
     next((l.strip() for l in _out.splitlines() if "걷음" in l), "걷음 줄 없음")[:110] + f" · C12 {[x['reason'] for x in _c12]}")

# ⓒ LLM 검토(mock) — 「유지」 승인 짝은 묻지 않는다 · 첫 실행 짝 k · 둘째 실행 0 → 호출 0 · 노드 개명 뒤 열쇠가 따라간다
_keep = AP.approve([{"surface": "TW", "target": {"layer": "process", "canonical": "탭용접", "category": "Process"},
                     "kind": AR.PAIR, "disposition": AP.KEEP}], "B200시험")
_ent = node_by("process", next(n["canonical"] for n in open_graph("process").nodes.values()
                               if n.get("status") != "seed" and ops.is_live(n) and n["category"] == "Property"))
ops_mark_ = __import__("core.state.ops_mark", fromlist=["alias"])
ops_mark_.alias("process", _ent["id"], "B200 사람 표기", "B200시험")
_k0 = len(AR.targets(AR.Review.open(), AR.items()))
_r1 = AR.run()
_r2 = AR.run()
_rows = AR.Review.open()
_kept_asked = (_rows.get(AB.pair_key("TW", {"layer": "process", "canonical": "탭용접", "category": "Process"})) or {}).get("verdict")
_new = _ent["canonical"] + " B200"
ops.rename("process", _ent["id"], _new, "B200시험")
_rv = AR.Review.open()
_follow = _rv.get(AB.pair_key("B200 사람 표기", {"layer": "process", "canonical": _new, "category": "Property"}))
show("B200 ⓒ LLM 검토(mock) — 첫 실행 짝 k 판정(유지 짝 제외) · 둘째 실행 물음 0 · 호출 0 · 개명 뒤 열쇠가 따라간다(판정 그대로)",
     _r1["asked"] == _k0 and _r1["wrong"] == 1 and _r1["unsure"] >= 1 and _kept_asked is None
     and _r2["asked"] == 0 and _r2["calls"] == 0 and bool(_follow and _follow.get("verdict")),
     f"첫 {_r1} · 둘째 물음 {_r2['asked']} 호출 {_r2['calls']} · 개명 뒤 {(_follow or {}).get('verdict')}")

# ⓓ 승인 — 대장 별칭 지움 · seed 별칭 지움 · 후보 받기 · 행위자 없음 · 낡은 승인 · ops replay
_t = {"layer": "process", "canonical": _new, "category": "Property"}
_m = AP.stamp()
_a1 = AP.approve([{"surface": "B200 사람 표기", "target": _t, "kind": AR.PAIR, "disposition": AP.DROP},
                  {"surface": "anode 탭용접", "target": {"layer": "process", "canonical": "탭용접", "category": "Process"},
                   "kind": AR.PAIR, "disposition": AP.DROP}], "B200시험", made=_m)
_bk = AB.AliasBook.open().get("B200 사람 표기", _t) or {}
_sk = json.loads(_skp.read_text(encoding="utf-8"))
_tw = node_by("process", "탭용접")
_pend = AA.pending()
_cand = next((e for e in _pend if e["layer"] == "quality"), None)
_fe = next((n for n in open_graph("quality").nodes.values() if n.get("status") == "seed"
            and n["category"] == (_cand or {}).get("category")), None)
_a2 = AP.approve([{"surface": _cand["surface"], "target": {"layer": "quality", "canonical": None, "category": _cand["category"]},
                   "kind": AR.CANDIDATE, "disposition": AP.TAKE, "to": _fe["canonical"]}], "B200시험") if _cand and _fe else {}
finalize()
_took = bool(_cand and _fe) and _fe["id"] in Dictionary.open().lookup(_cand["surface"]) and not any(
    (x.get("payload") or {}).get("surface") == _cand["surface"] for x in q_of("orphan_anchor"))
try:
    AP.approve([], "")
    _noactor = False
except AP.Refused:
    _noactor = True
_m2 = AP.stamp()
_sk["ALIASES"]["탭용접"].remove("TW")                   # 사람이 골격을 손으로 고쳤다 — 화면(판 _m2)은 낡았다
_skp.write_text(json.dumps(_sk, ensure_ascii=False, indent=2), encoding="utf-8")
_a3 = AP.approve([{"surface": "TW", "target": {"layer": "process", "canonical": "탭용접", "category": "Process"},
                   "kind": AR.PAIR, "disposition": AP.KEEP},
                  {"surface": "탭 용접", "target": {"layer": "process", "canonical": "탭용접", "category": "Process"},
                   "kind": AR.PAIR, "disposition": AP.KEEP}], "B200시험", made=_m2)
_tw_t = {"layer": "process", "canonical": "탭용접", "category": "Process"}
_w_ap = (AR.Review.open().get(AB.pair_key("탭 용접", _tw_t)) or {}).get("where")   # 승인 길이 적은 「곳」
_sbc = SB.counts()                                     # 판정 목록이 찬 때 — 합 · 지위는 표기 갈래만
SB.write_review([])                                    # 판정 목록을 비운다 — 재생이 사람 처분을 다시 적는가
_rp = OL.replay()
_back = AR.Review.open().get(AB.pair_key("TW", _tw_t)) or {}
_back2 = AR.Review.open().get(AB.pair_key("탭 용접", _tw_t)) or {}
show("B200 ⓓ 승인 — 대장 지움 → 대장 거부 · seed 지움 → skeleton.json · 노드 · 사전에서 빠짐 · 후보 받기 → 다음 마무리에 사전 연결 · "
     "행위자 없음 거부 · 손으로 고친 골격 → 「골격이 바뀜」 · ops replay가 유지를 다시 적는다",
     _bk.get("status") == AB.REJECTED and "anode 탭용접" not in _sk["ALIASES"].get("탭용접", [])
     and "anode 탭용접" not in [a["surface"] for a in _tw["aliases"]] and not Dictionary.open().lookup("anode 탭용접")
     and _a1["done"][AP.DROP] == 2 and _took and _noactor and _a3["stale"] == ["TW"] and _a3["done"][AP.KEEP] == 1
     and (_back.get("human") or {}).get("disposition") == AP.KEEP,
     f"{_a1['line']} · 후보 {(_cand or {}).get('surface')} → {(_fe or {}).get('canonical')} {_took} · 낡은 승인 {_a3['line']} · "
     f"재생 유지 {(_back.get('human') or {}).get('disposition')}")

show("B200 ⓓ′ 재생이 적은 「유지」의 곳 = 승인 길의 곳(한 함수 `surface_book.place` · 고침 — 옛 재생은 곳 없음) · "
     "표기 대장 합 = 표기 갈래 셋의 합(별칭 검토 갈래는 합 · 지위 밖 · 고침)",
     _w_ap == SB.SKELETON and _back.get("where") == _w_ap and _back2.get("where") == _w_ap
     and _sbc["갈래"][SB.REVIEW] > 0 and _sbc["합"] == sum(_sbc["갈래"][k] for k in (SB.LEARN, SB.MISS, SB.ALIAS))
     and _sbc[SB.HUMAN] + _sbc[SB.MACHINE] == _sbc["합"],
     f"승인 {_w_ap} · 재생 {_back.get('where')} · {_back2.get('where')} · 대장 {_sbc}")

# ⓕ 공유 별칭 보류 문면 — 범위 밖 · 범위 없음
# (같은 문서 · 같은 표기는 큐 한 항목이라 — 행 둘을 문서 둘로)
run_document(dict(TABLE, doc_id="B200F", records=[
    {"source_locator": "F1", "process_group": "패키징", "process_ref": "비전 검사", "설비": "B200 비전기", "관리항목": "B200 정렬"}]))
run_document(dict(TABLE, doc_id="B200G", records=[
    {"source_locator": "F2", "process_ref": "비전 검사", "설비": "B200 비전기", "관리항목": "B200 정렬"}]))
_rs = {(x.get("payload") or {}).get("provenance"): x["reason"]
       for d in ("B200F", "B200G") for x in q_of("orphan_anchor", d)}
show("B200 ⓕ 공유 별칭 보류 — 「표기 모호 — '비전 검사'의 노드 여럿(…) · 이 행의 범위(패키징)에 없다」 · 범위 없는 행 → 「범위 없음 — …」",
     "이 행의 범위(패키징)에 없다" in _rs.get("B200F#F1", "") and "'비전 검사'의 노드 여럿(" in _rs.get("B200F#F1", "")
     and "범위 없음 — 문서 좌표(--coord) 또는 상위 칸" in _rs.get("B200G#F2", ""), " ‖ ".join(f"{k} {v}" for k, v in _rs.items()))

init.init(fresh_=True, all_=True)

done()
