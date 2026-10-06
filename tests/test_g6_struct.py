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
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done    # noqa: F401

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
import tempfile                                    # noqa: E402
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
init.init(fresh_=True)

done()
