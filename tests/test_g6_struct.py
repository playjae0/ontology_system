# -*- coding: utf-8 -*-
"""G6 ⑱ 구조 결함 — 재시도 되살아남 · 등록이 좌표 층 골격을 본다 · 공정 이름 열 방어 · 단일 층 가정 ·
골격 밖 판정 기억 · 골격·사전이 바뀌면 재시도 (B100).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) ×
층(process · quality)에서 같은 성질을 잰다(CLAUDE.md §4 범용성).

잠그는 성질:
  ⓐ 재시도가 연결한 h건만큼 남음이 준다 · 다음 마무리의 대상에 연결된 항목이 없다 ·
     orphan_anchor(표) · orphan_attach(산문) × 층 둘
  ⓑ 골격이 다른 층인 상태에서 등록 층마다 생성 입력·검수 뷰·하네스가 좌표 층 몫 + 자기 골격을 받는다
     (시스템 5키 그대로 · 좌표 대조는 좌표 몫만)
  ⓒ 관문: 골격 값 열을 entity로 매핑 → G4H FAIL 문면 + 다음 줄 · 좌표·anchor로 매핑 → PASS ·
     문턱은 손잡이(`skeleton_column_pct`) — 표 × 층 둘(산문 스키마는 fields가 비어 대상 없음)
  ⓓ 지시문 문장(층 이름 0) · 자산 해시가 지시문 현재판과 같다
  ⓔ 「집 이동 동치」 — 카테고리의 집을 다른 층으로 옮긴 픽스처(창작)와 옮기지 않은 픽스처에서 merge(끝점 없는
     엣지 0) · rename · obsolete · split · transfer · alias · delete_edge · merge_targets · 질의 확장 · show tree·edges ·
     내보내기가 층 표시만 빼고 같다 (사람은 문서 층을 쳐도 된다 — 노드는 집에서 찾는다)
  ⓕ 미러 규칙(극성 묶음)과 집이 어긋나면 경고 + 다음 줄 · 규칙을 집 층으로 옮기면 경고 0 · 막지 않는다
  ⓖ 골격 밖 같은 표기 n행 → 판정 1회(후보·LLM 1회) · 대장 n행(둘째부터 경로 memo) · 큐 문서 × 표기 1건 —
     표·산문 × 층 둘
  ⓗ 골격 별칭 추가 + `bootstrap`(끝 줄 「보류 n건 … 다음 인입 마무리에서 다시 붙는다」) → 다음 마무리에서
     보류분 연결 — 그래프 수가 그대로여도(재시도 지문에 골격·사전의 판) · 표·산문 × 층 둘
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401

import contextlib                              # noqa: E402
import io                                      # noqa: E402
import tempfile                                # noqa: E402
from core.build import ledger as LG           # noqa: E402
from core.build import retry as RT            # noqa: E402
from core.build.retry import RETRY_KINDS, _qid  # noqa: E402

HINTS = ROOT / "tests" / "fixtures" / "extract_hints"


def _fresh(boot=True):
    init.init(fresh_=True)
    if boot:
        for lay in ("process", "quality"):
            bootstrap(lay, echo=False)


def _retry_case():
    """finalize 두 번 — (첫 줄 결과, 연결된 항목 id들, 둘째 대상)."""
    before = {_qid(x) for x in store.read(store.QUEUE, []) if x["kind"] in RETRY_KINDS}
    finalize()
    first = dict(RT.LAST)
    after = {_qid(x) for x in store.read(store.QUEUE, []) if x["kind"] in RETRY_KINDS}
    linked = before - after
    finalize()
    second = dict(RT.LAST)
    return first, linked, second, after


def _prose_attach_env(doc_id, doc_type, ref):
    """산문 한 청크 — 부착 대상 표기가 아직 없다(orphan_attach)."""
    (HINTS / f"{doc_id}.json").write_text(json.dumps({f"{doc_id}-C001": {
        "entities": [{"surface": "B100 세척 압력", "category": "Property"}],
        "relations": [],
        "attach": [{"surface": "B100 세척 압력", "attach_to": "B100 새 설비 표기"}]}},
        ensure_ascii=False), encoding="utf-8")
    return {"doc_id": doc_id, "doc_type": doc_type, "payload_kind": "prose",
            "source_path": f"{doc_id}.pptx", "revision": "R1",
            "parsed_at": "2026-10-06T00:00:00", "parser_version": "p1-1.0",
            "adapter_version": "b-1.0",
            "chunks": [{"source_locator": f"{doc_id}-C001", "doc_type": doc_type,
                        "process_group": "조립", "process_ref": ref, "electrode_type": "both",
                        "text": "세척 압력을 관리한다.", "section": "슬라이드 1", "meta": {}}]}


print("\n■ B100 ① 재시도가 연결한 항목을 되살리지 않는다 (형태 × 층)")
_res = []
# 표 × process / 표 × quality — 골격 없이 넣어 좌표 보류 → 골격을 심으면 붙는다
for doc, lay in (("CP01", "process"), ("PFMEA01", "quality")):
    _fresh(boot=False)
    bootstrap("quality", echo=False) if lay == "quality" else None
    run_document(load(doc))
    bootstrap("process", echo=False)
    _res.append(("표", lay) + _retry_case())
# 산문 × process / 산문 × quality — 부착 대상이 없다 → 사람이 별칭을 이으면 붙는다
from core.state import ops                     # noqa: E402
for doc_type, lay, did in (("ppt_process", "process", "B100AP"), ("ppt_quality", "quality", "B100AQ")):
    _fresh()
    run_document(_prose_attach_env(did, doc_type, "노칭"))
    g = open_graph("process")
    unit = next(i for i, n in g.nodes.items() if n.get("canonical") == "노칭")
    ops.alias("process", unit, "B100 새 설비 표기", "시험", "B100 ⓐ")   # 사람이 표기를 잇는다
    g2 = open_graph("process")                  # 그래프가 자랐다는 지문을 주려고 노드 하나를 더한다
    g2.add_node("B100 지문 노드", "Unit", "auto", provenance=["B100"])
    g2.save()
    _res.append(("산문", lay) + _retry_case())
    (HINTS / f"{did}.json").unlink(missing_ok=True)
_ok = []
for form, lay, first, linked, second, after in _res:
    h = sum(first["healed"].values())
    t = sum(first["target"].values())
    _ok.append((form, lay, h > 0 and first["left"] == t - h and len(linked) == h
                and not (linked & after) and sum(second["target"].values()) == t - h,
                f"대상 {t} · 연결 {h} · 남음 {first['left']} → 다음 대상 {sum(second['target'].values())}"))
show("ⓐ 재시도가 연결한 h건만큼 남음이 준다 · 다음 대상에 연결 항목 0 — orphan_anchor(표)·orphan_attach(산문) × 층 둘",
     all(o for _f, _l, o, _d in _ok), " · ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok))
init.init(fresh_=True)

print("\n■ B100 ② 등록이 좌표 층 몫 + 자기 골격을 본다 (형태 × 층)")
from core.state import bootstrap as BS          # noqa: E402
from cli.register import gate as GT, generate as GN, view as VW   # noqa: E402
from parser import tagger as TG                 # noqa: E402
from types import SimpleNamespace               # noqa: E402
RAW = ROOT / "tests" / "fixtures" / "raw"
FX = ROOT / "tests" / "fixtures"
SK = "B100골격"                                   # 골격이 다른 층(창작) — 좌표 층 이름


def _other_coord():
    """골격을 다른 층 이름으로 옮긴다 — 스냅샷 키 이름 + 좌표 층 답만(그래프는 그대로)."""
    _fresh()
    snap = store.read(store.SKELETON_LIST, {})
    snap[SK] = snap.pop("process")
    store.write(store.SKELETON_LIST, snap)
    for m in (BS, GT, VW):
        m.coord_layer = lambda: SK
    return snap


def _restore_coord(orig):
    for m in (BS, GT, VW):
        m.coord_layer = orig


_orig_coord = BS.coord_layer
_snap = _other_coord()
_n_coord = _snap[SK]["count"]
_ok_b = []
try:
    for form, lay, dt, sample in (("표", "process", "b100cp", RAW / "CP01.xlsx"),
                                   ("표", "quality", "b100pf", RAW / "PFMEA01.xlsx"),
                                   ("산문", "process", "b100pp", RAW / "PPT_basic.pptx"),
                                   ("산문", "quality", "b100pq", RAW / "PPT_basic.pptx")):
        pkg, _d = GN._cmd_generate_package(dt, lay, [sample], "", False, False, False)
        sk = pkg["system"]["skeleton_closed_list"]
        shares = {}
        for n in sk["surfaces"]:
            shares[n["몫"]] = shares.get(n["몫"], 0) + 1
        own = (_snap.get(lay) or {}).get("count") or 0
        want = {TG.SHARE_COORD: _n_coord, **({TG.SHARE_OWN: own} if own else {})}
        # 검수 뷰 — 좌표 몫 표기는 미스 0 · 자기 골격 표기는 좌표가 아니다(미스)
        own_s = [n["canonical"] for n in sk["surfaces"] if n["몫"] == TG.SHARE_OWN][:1]
        coord_s = [n["canonical"] for n in sk["surfaces"] if n["몫"] == TG.SHARE_COORD][:3]
        res = [SimpleNamespace(envelope={"records": [{"process_ref": x} for x in coord_s + own_s]})]
        miss = VW._coord_misses(res, VW.coord_layer())
        _ok_b.append((form, lay, shares == want and len(pkg["system"]) == 5 and miss == own_s
                      and sk["몫"][TG.SHARE_COORD]["층"] == SK,
                      f"몫 {shares} · 뷰 미스 {len(miss)}"))
    # 하네스 — 표 × 층 둘 (킷은 subprocess · 좌표 층 이름과 목록 파일을 건네받는다)
    for lay, ad, sc, sample in (("process", "cp", "cp", "CP01.xlsx"), ("quality", "pfmea", "pfmea", "PFMEA01.xlsx")):
        ok, out = GT.harness(FX / "adapters" / f"{ad}.py", FX / "schemas" / f"{sc}.json", [RAW / sample])
        g4h = [l for l in out.splitlines() if "G4H" in l]
        _ok_b.append(("표·하네스", lay, ok and g4h and "[PASS]" in g4h[0] and "대조 생략" not in out,
                      (g4h[0].strip() if g4h else "G4H 줄 없음")[:120]))
finally:
    _restore_coord(_orig_coord)
show("ⓑ 골격이 다른 층 — 생성 입력(좌표 몫 + 자기 골격 · 시스템 5키) · 검수 뷰(좌표 몫만 대조) · 하네스(G4H) × 형태 × 층",
     all(o for _f, _l, o, _d in _ok_b), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_b))

print("\n■ B100 ③ 공정 이름 열 방어 — 관문 G4H (표 × 층)")
_fresh()
_ok_c = []
with tempfile.TemporaryDirectory(prefix="b100_") as td:
    _n = [0]

    def _variant(ad, old, new):
        src = (FX / "adapters" / f"{ad}.py").read_text(encoding="utf-8")
        assert old in src
        _n[0] += 1                                 # 변형마다 새 이름 — 같은 초·같은 크기면 .pyc가 옛 판을 준다
        q = Path(td) / f"{ad}_bad{_n[0]}.py"
        q.write_text(src.replace(old, new), encoding="utf-8")
        return q
    cases = [("process", "좌표", "cp", '"설비": "E",', '"설비": "C",', "CP01.xlsx", "설비"),
             ("quality", "좌표", "pfmea", '"failure_mode": "E",', '"failure_mode": "C",', "PFMEA01.xlsx",
              "failure_mode"),
             ("quality", "자기", "pfmea", '"cause": "F",', '"cause": "G",', "PFMEA01.xlsx", "cause")]
    for lay, share, ad, old, new, sample, col in cases:
        bad = _variant(ad, old, new)
        ok, out = GT.harness(bad, FX / "schemas" / f"{ad}.json", [RAW / sample])
        line = next((l for l in out.splitlines() if "G4H" in l), "")
        nxt = next((l for l in out.splitlines() if "▶ 다음 줄" in l and "--revise" in l), "")
        want = "좌표(`process_group`·`process_ref`)로 매핑해야 한다" if share == "좌표" else "anchor로 매핑해야 한다"
        _ok_c.append((lay, share, not ok and "[FAIL]" in line and f"열 '{col}'의 값" in line and want in line
                      and "--hint" in nxt, line.strip()[:160]))
    # 문턱은 손잡이 — 100%면 같은 변형이 PASS(값 일부만 맞는 열 — 생성 지시문이 묻는다)
    (_P.home() / "knobs.json").write_text(json.dumps({"skeleton_column_pct": 100}), encoding="utf-8")
    from core.state import knobs as KB             # noqa: E402
    KB.reset()
    bad = _variant("pfmea", '"cause": "F",', '"cause": "G",')
    ok100, out100 = GT.harness(bad, FX / "schemas" / f"{'pfmea'}.json", [RAW / "PFMEA01.xlsx"])
    l100 = next((l for l in out100.splitlines() if "G4H" in l), "")
    (_P.home() / "knobs.json").unlink()
    KB.reset()
    _ok_c.append(("quality", "문턱100", "[PASS]" in l100 and "문턱 100%" in l100, l100.strip()[:160]))
show("ⓒ 관문 G4H — 골격 값 열을 entity로 → FAIL 문면 + 다음 줄(좌표 몫·자기 몫) · 원래 매핑은 PASS(ⓑ) · 문턱은 손잡이",
     all(o for _l, _s, o, _d in _ok_c), " ‖ ".join(f"{l}·{s} {d}" for l, s, _o, d in _ok_c))

print("\n■ B100 ③ 지시문 · 자산 해시")
_p14 = (ROOT / "prompts" / "1.4_generate.md").read_text(encoding="utf-8")
_p13 = (ROOT / "prompts" / "1.3_interview.md").read_text(encoding="utf-8")
from router import discover                       # noqa: E402
_new = [l for l in _p14.splitlines() if "열 이름이 아니라 값으로" in l or "좌표 층 몫 + 지정 층 자기 골격" in l
        or "하위 단이면 `process_ref`" in l] + [l for l in _p13.splitlines() if "상위\n" in l or "공정이 아닌가" in l]
import re                                          # noqa: E402
_lay_words = [w for w in discover()                # 층 이름 낱말(`process_ref` 같은 필드 이름은 아니다)
              if any(re.search(rf"(?<![A-Za-z_]){re.escape(w)}(?![A-Za-z_])", l) for l in _new)]
import subprocess                                 # noqa: E402
_h = subprocess.run([sys.executable, str(ROOT / "tests" / "asset_hashes.py")], capture_output=True, text=True,
                    cwd=str(ROOT))
show("ⓓ 지시문 1.4(anchor 값 기준 · 좌표 블록 상위/하위 · 킷 조립 두 몫) · 1.3(모르면 묻는다) · 층 이름 0 · 자산 해시 일치",
     len(_new) >= 4 and not _lay_words and _h.returncode == 0,
     f"새 문장 {len(_new)} · 층 이름 {_lay_words} · 해시 rc {_h.returncode}")
print("\n■ B100 ④ 집 이동 동치 (표·산문 × 층 둘 — 노드는 집 층 · 엣지는 문서 층)")
import csv as _csv                                # noqa: E402
import re as _re                                  # noqa: E402
from core.state.world import World               # noqa: E402
from cli import show as SH, export as EX, query as QY   # noqa: E402
MOVE_CAT = "Failure"                               # 옮기는 카테고리(창작 — 집을 다른 층으로)


def _rw_json(path, fn):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    fn(c)
    Path(path).write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def _world(move):
    """같은 문서 · 집만 다르다. 문서의 극성 표기는 both(창작) — 극성 규칙도 집 층에서 읽으므로
    축이 있는 층과 없는 층 사이의 이동은 극성 표기가 있으면 판정이 갈린다(규칙 차이 · 보고)."""
    init.init(fresh_=True)
    if move:
        _rw_json(_P.layers("process", "config.json"),
                 lambda c: c["categories"].update({MOVE_CAT: "(시험 렌즈) 집 이동 동치 — 창작"}))
        _rw_json(_P.common(), lambda c: c["categories"][MOVE_CAT].update(home="process"))
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for doc in ("CP01", "PFMEA01"):
        env = load(doc)
        for r in env.get("records") or []:
            r["electrode_type"] = "both"
        run_document(env)
    run_document(_prose_attach_env("B100MV", "ppt_quality", "노칭"))   # 산문 × 품질층
    finalize()


def _strip(text):
    return _re.sub(r"\[(process|quality)\]", "", text)


def _sig():
    w = World()
    nm = {n["id"]: n["canonical"] for _l, n in w.nodes()}
    return {"노드": sorted(f"{n['canonical']}|{n['category']}|{n['status']}" for _l, n in w.nodes()),
            "엣지": sorted(f"{e['rel']}|{nm.get(e['src'])}|{nm.get(e['dst'])}|{e.get('status')}"
                         for _l, g in w.graphs.items() for e in g.edges),
            "끝점없음": w.dangling()}


def _cat_names(cat):
    return sorted({n["canonical"] for _l, n in World().nodes()
                   if n["category"] == cat and ops.is_live(n)})


def _nid(name):
    return next(n["id"] for _l, n in World().nodes() if n["canonical"] == name and ops.is_live(n))


def _screens(name):
    out = {}
    for key, fn, args in (("tree", SH.cmd_tree, []), ("edges", SH.cmd_edges, ["quality"])):
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            fn(args)
        out[key] = sorted(_strip(b.getvalue()).splitlines())
    r = QY.answer(name)
    hop_nodes = {n for h in r["trace"]["hops"] for n in h["nodes"]}
    nm = {n["id"]: n["canonical"] for _l, n in World().nodes()}
    out["질의"] = (sorted(nm.get(i, i) for i in hop_nodes), sorted(r["facts"]))
    with tempfile.TemporaryDirectory() as td:
        with contextlib.redirect_stdout(io.StringIO()):
            EX.cmd_csv([td])
        rows = []
        for f in ("nodes.csv", "edges.csv"):
            with open(Path(td) / f, encoding="utf-8-sig") as fh:
                rd = list(_csv.reader(fh))
            head = rd[0]
            keep = [i for i, h in enumerate(head) if h not in ("id", "src_id", "dst_id", "layer")]
            rows += sorted("|".join(r[i] for i in keep) for r in rd[1:])
        out["내보내기"] = rows
    return out


def _ops_chain():
    """사람이 **문서 층**을 쳐서 연산한다 — 집이 어디든 같은 결과여야 한다."""
    import contextlib as _cl
    A = "B100시험"
    f = _cat_names(MOVE_CAT)
    log = {}
    ops.merge("quality", _nid(f[0]), _nid(f[1]), A, reason="동치")
    log["merge 끝점없음"] = World().dangling()
    ops.rename("quality", _nid(f[2]), f[2] + " 개명", A)
    ops.obsolete("quality", _nid(f[3]), A, reason="동치")
    n4 = _nid(f[4])
    keys = [k for k, *_r in ops.edge_keys("quality", n4)]
    node4 = World().get(n4)
    ops.split("quality", n4, {"targets": [
        {"canonical": f[4] + " 갑", "aliases": [a["surface"] for a in node4["aliases"]],
         "provenance": list(node4["provenance"]), "edges": keys},
        {"canonical": f[4] + " 을", "aliases": [], "provenance": [], "edges": []}]}, A)
    log["split 끝점없음"] = World().dangling()
    ops.alias("quality", f[5], f[5] + " 별칭", A)
    log["merge_targets"] = sorted(c["canonical"] for c in ops.merge_targets("quality", _nid(f[6])))
    w = World()
    e = next(e for e in w.graphs["quality"].edges if e["rel"] == "causes" and e.get("status") != "deleted_by_user")
    ops.delete_edge("process", e["src"], e["rel"], e["dst"], A)   # 친 층에 없는 엣지 — 층 전부에서 찾는다
    u = next(n for _l, n in w.nodes() if n["category"] == "Unit" and n.get("status") == "auto"
             and "::" in n["canonical"])
    old_p = u["canonical"].split("::")[0]
    np_ = next(n for _l, n in w.nodes() if n["category"] == "Process" and n.get("status") == "seed"
               and n["canonical"] != old_p and n.get("tier") == "sub")
    log["transfer"] = ops.transfer("quality", u["id"], np_["id"], A)["canonical"]
    return log


_eq = {}
for move in (False, True):
    _world(move)
    s0 = _sig()
    log = _ops_chain()
    _eq[move] = (s0, log, _sig(), _screens(_cat_names(MOVE_CAT)[1]))
_a, _b = _eq[False], _eq[True]
_diff = [k for k in ("노드", "엣지") if _a[0][k] != _b[0][k] or _a[2][k] != _b[2][k]]
_diff += [k for k in _a[1] if _a[1][k] != _b[1][k]]
_diff += [k for k in _a[3] if _a[3][k] != _b[3][k]]
_homes = {mv: sorted({l for l, n in World().nodes() if n["category"] == MOVE_CAT}) for mv in (True,)}
show("ⓔ 집 이동 동치 — merge·split 뒤 끝점 없는 엣지 0 · rename·obsolete·split·transfer·alias·delete_edge·"
     "merge_targets · 질의 확장 · show tree·edges · 내보내기가 층 표시만 빼고 같다(표·산문 × 층 둘)",
     not _diff and not _a[1]["merge 끝점없음"] and not _b[1]["merge 끝점없음"]
     and not _b[1]["split 끝점없음"] and not _b[2]["끝점없음"] and _homes[True] == ["process"],
     f"다름 {_diff} · 옮긴 쪽 {MOVE_CAT} 집 {_homes[True]} · 노드 {len(_b[2]['노드'])} · 엣지 {len(_b[2]['엣지'])} · "
     f"질의 노드 {len(_b[3]['질의'][0])} · 사실 {len(_b[3]['질의'][1])}")
(HINTS / "B100MV.json").unlink(missing_ok=True)

print("\n■ B100 ④ 미러 규칙 ≠ 집 — 경고 (층 둘)")
from core.state import catalog as CT              # noqa: E402
_ok_f = []
for cat, frm, to in (("Property", "process", "quality"), ("Unit", "process", "quality")):
    init.init(fresh_=True)
    _rw_json(_P.layers(to, "config.json"), lambda c, cat=cat: c["categories"].update({cat: "(시험 렌즈)"}))
    _rw_json(_P.common(), lambda c, cat=cat, to=to: c["categories"][cat].update(home=to))
    w1 = CT.mirror_warnings()
    import subprocess as _sp                       # noqa: E402
    _r = _sp.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], capture_output=True, text=True,
                 cwd=str(ROOT), stdin=_sp.DEVNULL)
    b2 = io.StringIO(_r.stdout + _r.stderr)
    src_cfg = json.loads(_P.layers(frm, "config.json").read_text(encoding="utf-8"))
    _rw_json(_P.layers(to, "config.json"), lambda c, s=src_cfg, cat=cat: c.update(
        polarity={**s["polarity"], "bind_categories": [cat]}, mirrors=s["mirrors"]))
    w2 = CT.mirror_warnings()
    _ok_f.append((cat, len(w1) == 1 and cat in w1[0][0] and "config.json" in w1[0][1]
                  and "미러 규칙" in b2.getvalue() and "▶ 다음 줄" in b2.getvalue() and _r.returncode == 0
                  and not w2,
                  f"{cat} 집 {to}: 경고 {len(w1)} → 규칙 옮김 {len(w2)}"))
show("ⓕ 미러 규칙(극성 묶음)이 집 층 config에 없으면 bootstrap·doctor 경고 + 다음 줄 · 옮기면 0 · 막지 않는다",
     all(o for _c, o, _d in _ok_f), " · ".join(d for _c, _o, d in _ok_f))
print("\n■ B100 ⑤ 골격 밖 반복 판정 기억 (표·산문 × 층 둘)")
from core.build import build as BLD             # noqa: E402
_calls = {"n": 0}
_real_resolve = BLD.resolve


def _counting(*a, **k):
    _calls["n"] += 1
    return _real_resolve(*a, **k)


def _table_env(doc_id, dt, n, surface):
    env = load("CP01")
    recs = []
    for i in range(n):
        r = dict(env["records"][0], source_locator=f"B{i + 1}", doc_type=dt)
        r = {k: v for k, v in r.items() if k not in ("설비", "관리항목", "규격", "측정방법", "대응계획")}
        r["골격열"] = surface
        recs.append(r)
    return {**env, "doc_id": doc_id, "doc_type": dt, "records": recs}


def _reg_table(dt, layer, cat):
    p = _P.schemas(f"{dt}.json")
    _P.ensure(p)
    p.write_text(json.dumps({"doc_type": dt, "schema_version": 1, "layer": layer,
                             "use_blocks": ["common_core", "process_coord"],
                             "fields": {"골격열": {"role": "entity", "category": cat}}, "edges": []},
                            ensure_ascii=False), encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[dt] = {"doc_type": dt, "status": "registered", "layer": layer, "schema": f"schemas/{dt}.json",
               "adapter": "-", "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _prose_env(doc_id, dt, n, surface, cat):
    env = _prose_attach_env(doc_id, dt, "노칭")      # 봉투 모양만 빌린다 — 힌트는 아래가 덮는다
    (HINTS / f"{doc_id}.json").write_text(json.dumps({
        f"{doc_id}-C{i:03d}": {"entities": [{"surface": surface, "category": cat}], "relations": [], "attach": []}
        for i in range(1, n + 1)}, ensure_ascii=False), encoding="utf-8")
    c0 = env["chunks"][0]
    env["chunks"] = [dict(c0, source_locator=f"{doc_id}-C{i:03d}", text=f"{surface} 이야기 {i}")
                     for i in range(1, n + 1)]
    return env


N = 3
_ok_g = []
BLD.resolve = _counting
try:
    for form, lay, cat in (("표", "process", "Process"), ("표", "quality", "FailureEffect"),
                           ("산문", "process", "Process"), ("산문", "quality", "FailureEffect")):
        _fresh()
        surf = f"골격밖 B100 {lay}"
        if form == "표":
            did = f"B100T{lay[0].upper()}"
            _reg_table(f"b100t{lay[0]}", lay, cat)
            env = _table_env(did, f"b100t{lay[0]}", N, surf)
        else:
            did = f"B100P{lay[0].upper()}"
            env = _prose_env(did, "ppt_process" if lay == "process" else "ppt_quality", N, surf, cat)
        _calls["n"] = 0
        run_document(env)
        rows = [r for r in (LG.read(did) or {}).get("rows") or [] if r.get("surface") == surf]
        q = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor" and x.get("doc_id") == did
             and (x.get("payload") or {}).get("surface") == surf]
        paths_ = [r.get("path") for r in rows]
        _ok_g.append((form, lay, _calls["n"] == 1 and len(rows) == N and paths_.count("memo") == N - 1
                      and all(r.get("verdict") == "orphan" for r in rows) and len(q) == 1,
                      f"판정 {_calls['n']} · 대장 {len(rows)}행 {paths_} · 큐 {len(q)}"))
        (HINTS / f"{did}.json").unlink(missing_ok=True)
finally:
    BLD.resolve = _real_resolve
show("ⓖ 골격 밖 같은 표기 n행 → 판정 1회 · 대장 n행(둘째부터 memo) · 큐 문서×표기 1건 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_g), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_g))
print("\n■ B100 ⑥ 골격·사전이 바뀌면 재시도가 돈다 (표·산문 × 층 둘)")
import subprocess as _sp6                         # noqa: E402
NEW = "B100별칭표기"
_ok_h = []
for form, lay in (("표", "process"), ("표", "quality"), ("산문", "process"), ("산문", "quality")):
    _fresh()
    if form == "표":
        env = load("CP01" if lay == "process" else "PFMEA01")
        env["records"][0]["process_ref"] = NEW         # 목록 밖 좌표 → orphan_anchor
        kind = "orphan_anchor"
    else:
        env = _prose_attach_env("B100H" + lay[0].upper(), "ppt_" + lay, "노칭")
        (HINTS / f"{env['doc_id']}.json").write_text(json.dumps({f"{env['doc_id']}-C001": {
            "entities": [{"surface": "B100 세척 압력", "category": "Property"}], "relations": [],
            "attach": [{"surface": "B100 세척 압력", "attach_to": NEW}]}}, ensure_ascii=False), encoding="utf-8")
        kind = "orphan_attach"
    run_document(env)
    finalize()
    finalize()
    same0 = RT.LAST["same"]                          # 그래프·골격·사전 그대로 — 건너뜀
    q0 = [x for x in store.read(store.QUEUE, []) if x["kind"] == kind and x.get("doc_id") == env["doc_id"]
          and NEW in json.dumps(x.get("payload"), ensure_ascii=False)]
    _rw_json(_P.layers("process", "skeleton.json"),
             lambda c: c["ALIASES"].setdefault("노칭", []).append(NEW))
    n0 = {l: len(g.nodes) for l, g in World().graphs.items()}
    r = _sp6.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], capture_output=True, text=True,
                 cwd=str(ROOT), stdin=_sp6.DEVNULL)
    line = next((l for l in r.stdout.splitlines() if "보류" in l and "다음 인입 마무리" in l), "")
    n1 = {l: len(g.nodes) for l, g in World().graphs.items()}
    finalize()
    q1 = [x for x in store.read(store.QUEUE, []) if x["kind"] == kind and x.get("doc_id") == env["doc_id"]
          and NEW in json.dumps(x.get("payload"), ensure_ascii=False)]
    _ok_h.append((form, lay, same0 > 0 and q0 and n0 == n1 and line and not q1
                  and sum(RT.LAST["healed"].values()) >= len(q0),
                  f"건너뜀 {same0} · 보류 {len(q0)} → {len(q1)} · 그래프 수 {'그대로' if n0 == n1 else '바뀜'} · "
                  f"「{line.strip()[:60]}」"))
    (HINTS / f"{env['doc_id']}.json").unlink(missing_ok=True)
show("ⓗ 골격 별칭 + bootstrap(보류 줄) → 다음 마무리에서 보류분 연결 · 그래프 수 그대로여도 (표·산문 × 층 둘)",
     all(o for _f, _l, o, _d in _ok_h), " ‖ ".join(f"{f}×{l} {d}" for f, l, _o, d in _ok_h))
# 등록 단(②)은 `init --fresh`가 지우지 않는다 — 이 시험이 세운 doc_type·패키지는 이 시험이 치운다
import shutil as _sh                              # noqa: E402
_dts = store.read(store.DOC_TYPES, {})
for _dt in ("b100cp", "b100pf", "b100pp", "b100pq", "b100tp", "b100tq"):
    _dts.pop(_dt, None)
    _P.schemas(f"{_dt}.json").unlink(missing_ok=True)
    _sh.rmtree(_P.review(_dt), ignore_errors=True)
store.write(store.DOC_TYPES, _dts)
init.init(fresh_=True)

done()
