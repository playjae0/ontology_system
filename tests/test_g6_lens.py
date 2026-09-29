# -*- coding: utf-8 -*-
"""G6 ⑪ 추출 입구 — 사내 손잡이 · 렌즈 · 시트 두 모드 · prose 좌표 셋 · ref 근처 · 겸 집 경고 (B91).

mock 동작 불변(네 벌 diff 0)은 회귀가 잰다 — 여기는 **새 성질**을 테스트 세트로 잰다
(창작 · 메커니즘 확인 — 수치는 근거가 아니다 · [정정] 50). 층 덧칠은 B90과 같은 바닥
(`g65_common.overlay` — `tests/fixtures/layers_b90/overlay.json`).

잠그는 성질:
  ⑤ 손잡이 파일이 없으면 전부 기본값(= 코드 상수) · 값을 바꾸면 청크가 달라지고 인입 기록에
     값·출처가 남는다 · 모르는 키·형 밖은 문면으로 멈춘다 · `show knobs`가 값·출처·분포 자리를 말한다
  ① 렌즈 둘이면 청크마다 렌즈마다 그 층 어휘로 부르고 개체는 같은 노드로 모인다 · 관련성 0인
     청크는 그 렌즈 LLM 0 · 예고 · 상한을 넘으면 멈춘다(보류) · 렌즈는 등록부의 항목이다
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from core.state import knobs, registry   # noqa: E402
from core.build import extract as EX      # noqa: E402
from cli.parse import run_parse           # noqa: E402


def _run(*argv):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), *argv], cwd=str(ROOT),
                       capture_output=True, text=True, env={**os.environ, "USE_MOCK": "1"},
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def _knobs_file(obj):
    if obj is None:
        _P.knobs().unlink(missing_ok=True)
    else:
        _P.knobs().write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    _P.reset()                                        # 루트를 다시 정하며 다시 주입한다


# ────────────────────────────────────────────────────────────── ⑤
print("\n■ B91 ⑤ 사내 손잡이 — 값은 사내에서 · 분포는 사내 화면에")
init.init(fresh_=True)
_knobs_file(None)
_rows = {r["name"]: r for r in knobs.rows()}
show("⑤ 손잡이 파일이 없으면 전부 기본값이고 기본값은 코드 상수다",
     all(r["from"] == "default" and r["value"] == r["default"] for r in _rows.values())
     and _rows["chunk_max_chars"]["value"] == 3000 and _rows["collect_limit"]["value"] == 8,
     str({k: r["value"] for k, r in _rows.items()}))


def _parse_hier():
    res, _out = run_parse(str(ROOT / "parser/adapters/basic_prose_xlsx.py"), "B91K",
                          str(ROOT / "tests/fixtures/raw/HIER01.xlsx"))[:2]
    return res.envelope


_e0 = _parse_hier()
_knobs_file({"chunk_max_chars": 1000, "_메모": "시험"})
_e1 = _parse_hier()
_k1 = (_e1.get("context") or {}).get("knobs") or {}
show("⑤ 글자 상한을 파일로 바꾸면 청크가 달라지고 기록에 값·출처가 남는다 (파일 없음이면 기록 키 0)",
     len(_e1["chunks"]) > len(_e0["chunks"]) and "knobs" not in (_e0.get("context") or {})
     and _k1.get("chunk_max_chars") == {"value": 1000, "from": "file"}
     and _k1.get("chunk_rows", {}).get("from") == "default",
     f"청크 {len(_e0['chunks'])} → {len(_e1['chunks'])} · {_k1.get('chunk_max_chars')}")
_rc, _o = _run("show", "knobs")
show("⑤ show knobs — 값 · 출처 · 그 값을 정할 분포 명령", _rc == 0
     and "chunk_max_chars" in _o and "[file]" in _o and "show dist chunks" in _o, _o.splitlines()[0])
_rcd, _od = _run("show", "dist", "chunks")
_knobs_file({"chunk_max_char": 1000})
_rc2, _o2 = _run("show", "knobs")
_knobs_file({"chunk_rows": [40, 5]})
_rc3, _o3 = _run("query", "노칭", "--allow-mock")
show("⑤ 모르는 키 · 형 밖은 문면으로 멈춘다 (조용한 무시 0) · 분포 명령은 돈다",
     _rc2 != 0 and "모르는 키" in _o2 and "다음 줄" in _o2 and "Traceback" not in _o2
     and _rc3 != 0 and "형 밖" in _o3 and _rcd == 0 and "글자" in _od,
     _o2.strip().splitlines()[0][:80])
_knobs_file(None)

# ────────────────────────────────────────────────────────────── ①
print("\n■ B91 ① 렌즈 — doc_type의 층 목록")
overlay()                                  # 품질층도 Unit을 선언한다(집 = process)
run_document(load("CP01"))
if registry.lookup("b91lens"):
    registry.unregister("b91lens")         # 등록 단은 클린이 안 지운다
registry.register("b91lens", layer="quality", adapter="(시험)",
                  schema=str(ROOT / "tests/fixtures/schemas/ppt_quality.json"),
                  adapter_version="t", approved_by="시험", approved_at="t",
                  lenses=["process", "quality"])
_calls = {}
_real = EX._candidates_for


def _stub(cid, chunk, cfg, vocab):
    """층마다 다른 LLM — 두 렌즈가 같은 「노칭 프레스」를 말한다."""
    _calls.setdefault(cfg["layer"], []).append(cid)
    ents = [{"surface": "노칭 프레스", "category": "Unit"}]
    rels = []
    if cfg["layer"] == "quality":
        ents.append({"surface": "칼날 마모", "category": "Failure"})
        rels = [{"src": "칼날 마모", "rel": "occurs_in", "dst": "노칭 프레스"}]
    return {"chunk_id": cid, "entities": ents, "relations": rels, "attach": []}


_notes = []
EX._candidates_for = _stub
try:
    _env = dict(PROSE, doc_type="b91lens", doc_id="XB91L", chunks=[
        dict(C1, source_locator="XB91L-C001", text="노칭 프레스의 칼날 마모가 발생한다."),
        dict(C1, source_locator="XB91L-C002", text="오늘의 회의 안건과 참석자.")])
    _r = run_document(_env, notice=lambda i: _notes.append(i) or None)
    _pg, _qg = open_graph("process"), open_graph("quality")
    _press = [n for n in _pg.nodes.values() if n["canonical"] == "노칭::노칭 프레스"]
    _q_units = [n for n in _qg.nodes.values() if n["category"] == "Unit"]
    _cps = sorted(p.name for p in EX.EXTRACT_DIR.glob("XB91L*.json"))
    show("① 렌즈 둘 — 청크마다 렌즈마다 그 층 어휘로 부르고 개체는 **같은 노드**로 모인다",
         len(_press) == 1 and "XB91L" in str(_press[0]["provenance"]) and not _q_units
         and sorted(_calls) == ["process", "quality"]
         and _cps == ["XB91L@process.json", "XB91L@quality.json"],
         f"호출 {({k: len(v) for k, v in _calls.items()})} · 체크포인트 {_cps}")
    _pre = next((i for i in _notes if i.get("단계") == "렌즈예고"), {})
    show("① 관련성 0인 청크는 그 렌즈 LLM 0 · 호출 전 예고(렌즈 × 청크 → 거름 뒤 호출)",
         all(len(v) == 1 for v in _calls.values())
         and _pre.get("청크") == 2 and _pre.get("호출") == 2 and _pre.get("거름") == 2,
         str({k: v for k, v in _pre.items() if k != "단계"}))
    _knobs_file({"lens_call_cap": 1})
    EX.invalidate("XB91L")
    _r2 = run_document(dict(_env, revision="R2"), notice=lambda i: False if i.get("단계") == "렌즈상한" else None)
    show("① 호출 상한을 넘으면 멈춘다 — 문서는 보류(조용한 절단 0)",
         _r2[0].status == "held" and "lens_call_cap" in (_r2[0].reason or ""), _r2[0].reason)
finally:
    EX._candidates_for = _real
    _knobs_file(None)
_rcl, _ol = _run("register", "lenses", "b91lens", "process,없는층")
_rcm, _om = _run("register", "lenses", "b91lens", "quality")
show("① 렌즈는 등록부의 항목 — 없는 층은 거부 · 기본(등록 층 하나)으로 바꾸면 키가 빠진다",
     _rcl != 0 and "없는 층" in _ol and _rcm == 0
     and "lenses" not in (registry.lookup("b91lens") or {}), _om.strip().splitlines()[0])
registry.unregister("b91lens")
init.init(fresh_=True)

done()
