# -*- coding: utf-8 -*-
"""G6 ⑲ 동의어 학습 — 같은 문서 auto 매칭 · 좌표 학습 보존 · 새 공정 후보 · 별칭 출처 · 불확실 일괄
검토 · 극성 values 경고 (B101).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 판정 점수는 시험이
유사도 함수에 주입한다(LLM 판정 대역 — 임계 이상 0.9). 형태(표·산문) × 층(process · quality)에서 같은
성질을 잰다(CLAUDE.md §4 범용성).

잠그는 성질:
  ⓐ 같은 문서: 앞 행·청크가 만든 auto 노드에 뒤의 변형 표기가 판정(임계 이상)으로 매칭 · 별칭(출처 LLM 매칭)
     · 대장 `same_doc` / 다른 문서의 auto 노드에는 가드 그대로(uncertain + 가장 가까운 후보) · 결과표의 수
  ⓑ 좌표 학습: 문서 A에서 채택한 표기가 문서 B에서 LLM 0으로 맞는다 · 예고 「학습 적중」 · null은 B에서 다시
     묻는다 · 거부 뒤 다시 묻는다 · 승격 + bootstrap 뒤 사람 보증 별칭(정확 일치)으로 맞는다
  ⓒ 새 공정 후보: null 표기가 행·문서와 함께 보이고(`show learned`) · 다음 줄대로 골격에 더하면 다음 인입
     마무리에서 붙는다
  ⓓ 별칭 출처: `show node`가 LLM 매칭 · 사람(merge) · 골격 · 좌표 학습을 가른다
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

HINTS = ROOT / "tests" / "fixtures" / "extract_hints"
MATRIX = [("표", "process", "Unit"), ("표", "quality", "Failure"),
          ("산문", "process", "Unit"), ("산문", "quality", "Failure")]
BASE, VAR = "B101 유량계", "B101 유량 감지기"
OTHERS = ["B101 유량 측정기", "B101 유량 센서", "B101 유량 검출기"]


def _fresh():
    init.init(fresh_=True, all_=True)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


_real_sim = MT._similarity


def _sim(a, b):
    """판정 대역 — 변형 표기 ↔ 기준 표기는 0.9(임계 이상 · 1.0 미만). 나머지는 원래 함수."""
    if BASE in str(b) and any(v in str(a) for v in [VAR] + OTHERS):
        return 0.9
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


print("\n■ B101 ① 같은 문서 auto 노드에 LLM 매칭 · 다른 문서는 가드 · ⑤ 일괄 검토 · ④ 별칭 출처")
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
        run_document(_env(form, lay, cat, db, OTHERS))
        res_b = (LG.read(db) or {}).get("result") or {}
        um = [x for x in store.read(store.QUEUE, []) if x["kind"] == "uncertain_match" and x["doc_id"] == db]
        near_ok = all((x["payload"].get("nearest") or {}).get("id") == base["id"]
                      and (x["payload"].get("nearest") or {}).get("by") == "가드" for x in um)
        _ok_a.append((form, lay, rows_a and rows_a[0]["verdict"] == "match" and rows_a[0].get("same_doc")
                      and rows_a[0]["node_id"] == base["id"] and (al.get(VAR) or {}).get("by") == "LLM 매칭"
                      and res_a.get("같은 문서 auto 매칭") == 1 and res_a.get("LLM 별칭", 0) >= 1
                      and len(um) == len(OTHERS) and near_ok and res_b.get("가드(다른 문서 auto)") == len(OTHERS),
                      f"A: 같은 문서 매칭 {res_a.get('같은 문서 auto 매칭')} · LLM 별칭 {res_a.get('LLM 별칭')} · "
                      f"B: 가드 {res_b.get('가드(다른 문서 auto)')} · 불확실 {len(um)}"))
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
show("ⓐ 같은 문서 auto 노드에 변형 표기 매칭(별칭 LLM 매칭 · 대장 same_doc) / 다른 문서 auto는 가드 그대로 "
     "(uncertain + 가장 가까운 후보) · 결과표의 수 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_a), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_a))
show("ⓔ 일괄 검토 — 비대화형은 계획만(쓰기 0) · 합침(m)·별개(c)·건너뜀(s)이 ops 함수로 · 끝점 없는 엣지 0 "
     "(표·산문 × 층 둘)", all(o for _f, _l, o, _d in _ok_e), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_e))

print("\n■ B101 ② 좌표 학습 보존 · ③ 새 공정 후보 (표·산문 × 층 둘)")
LEARN, NULLX = "노칭 B101공정", "없는공정 B101"
_ok_b, _ok_c = [], []
from core.state.bootstrap import coord_layer      # noqa: E402
for form, lay, _cat in MATRIX:
    _fresh()
    coord = coord_layer()
    dt = ("cp" if lay == "process" else "pfmea") if form == "표" else "ppt_" + lay
    calls = []

    def pick(ref, opts):
        calls.append(ref)
        return "노칭" if ref == LEARN else None

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
    _ok_b.append((form, lay, ca == [LEARN, NULLX] and cb == [NULLX] and pb["학습_적중"] == 1
                  and pb["학습_적중_행"] == 2 and ob[0]["process_ref"] == "노칭"
                  and ob[0]["meta"]["coord_tag_source"] == "learned" and rec.get("출처") == TG.LEARN_SOURCE
                  and rec.get("doc_id") == "DA" and cc == [LEARN, NULLX] and r.returncode == 0
                  and cd == [NULLX] and pd["학습_적중"] == 0 and od[0]["process_ref"] == LEARN
                  and LEARN not in CL.book()["채택"],
                  f"A 호출 {ca} · B 호출 {cb} 학습 적중 {pb['학습_적중']}종(행 {pb['학습_적중_행']}) · "
                  f"거부 뒤 C 호출 {cc} · 승격+bootstrap 뒤 D 호출 {cd}(정확 일치 {pd['정확_일치']})"))
    # ③ 새 공정 후보 — 표기 · 행 · 문서
    cands = {s: (r_, q) for s, r_, q in CL.candidates()}
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        SL.cmd_learned([])
    out = b.getvalue()
    c = (cands.get(NULLX) or ({}, 0))[0]
    _ok_c.append((form, lay, set(c.get("docs") or []) == {"DA", "DB", "DC", "DD"} and c.get("rows") == 4
                  and NULLX in out and "새 공정 후보" in out and "bootstrap" in out,
                  f"{NULLX} 행 {c.get('rows')} · 문서 {c.get('docs')}"))

# ③ 다음 줄대로 골격에 더하면 다음 인입 마무리에서 붙는다 — 표·산문 × 층 둘
_ok_c2 = []
for form, lay, cat in MATRIX:
    _fresh()
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
show("ⓑ 좌표 학습 — A 채택 → B LLM 0(예고 학습 적중) · null은 다시 묻는다 · 거부 뒤 다시 묻는다 · 승격+bootstrap "
     "뒤 사람 보증 정확 일치 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_b), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_b))
show("ⓒ 새 공정 후보 — null 표기 · 행 · 문서가 show learned에 · 다음 줄대로 골격에 더하면 다음 인입 마무리에서 붙는다 "
     "(표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_c + _ok_c2),
     " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_c + _ok_c2))

# ④ 별칭 출처 — 골격 · 좌표 학습 (골격 노드)
_fresh()
TG.tag([{"source_locator": "x", "process_ref": LEARN}], layer=coord_layer(), pick=lambda r, o: "노칭",
       doc_type="cp", doc_id="DS")
_sk = _show_node("노칭")
_ok_d.append(("골격", coord_layer(), "← 골격" in _sk and f"{LEARN}  ← 좌표 학습(DS" in _sk,
              " / ".join(l.strip() for l in _sk.splitlines() if "좌표 학습" in l)[:120]))
show("ⓓ 별칭 출처 — show node가 LLM 매칭(확신·문서) · 사람(merge) · 골격 · 좌표 학습을 가른다 (표·산문 × 층 둘 + 골격)",
     all(o for _f, _l, o, _d in _ok_d), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_d))

print("\n■ B101 ⑥ 극성 values 경고 (층 둘)")
from core.state import catalog as CT              # noqa: E402


def _rw_json(path, fn):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    fn(c)
    Path(path).write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


_ok_f = []
# 갈래 1 — 선언 층(축 없음)과 집(축 있음)이 다르다: quality의 Failure 집을 process로
init.init(fresh_=True, all_=True)
_rw_json(_P.layers("process", "config.json"), lambda c: c["categories"].update({"Failure": "(시험 렌즈)"}))
_rw_json(_P.common(), lambda c: c["categories"]["Failure"].update(home="process"))
w1 = [m for m, _n in CT.mirror_warnings() if "values" in m]
_rw_json(_P.common(), lambda c: c["categories"]["Failure"].update(home="quality"))
w1b = [m for m, _n in CT.mirror_warnings() if "values" in m]
_ok_f.append(("선언≠집 축", len(w1) == 1 and "unbound" in w1[0] and not w1b, f"경고 {len(w1)} → 집 되돌림 {len(w1b)}"))
# 갈래 2 — 묶은 층과 집 모두 묶었지만 values가 다르다: Property 집을 quality로
init.init(fresh_=True, all_=True)
_pc = json.loads(_P.layers("process", "config.json").read_text(encoding="utf-8"))
_rw_json(_P.layers("quality", "config.json"), lambda c: c.update(
    categories={**c["categories"], "Property": "(시험 렌즈)"}, mirrors=_pc["mirrors"],
    polarity={"bind_categories": ["Property"], "values": ["양", "음"]}))
_rw_json(_P.common(), lambda c: c["categories"]["Property"].update(home="quality"))
w2 = CT.mirror_warnings()
_rw_json(_P.layers("quality", "config.json"), lambda c: c["polarity"].update(values=_pc["polarity"]["values"]))
w2b = CT.mirror_warnings()
_ok_f.append(("묶음 values", len(w2) == 1 and "같은 polarity.values" in w2[0][0] and "config.json" in w2[0][1]
              and not w2b, f"경고 {len(w2)} → values 맞춤 {len(w2b)}"))
show("ⓕ 극성 values 경고 — 선언 층과 집의 축이 다르다 · 묶은 층과 집의 values가 다르다 · 경고 + 다음 줄 · 맞추면 0",
     all(o for _c, o, _d in _ok_f), " · ".join(f"{c}: {d}" for c, _o, d in _ok_f))
init.init(fresh_=True, all_=True)

done()
