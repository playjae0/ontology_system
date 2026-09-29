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
  ② 시트 관문 표에 로직·LLM 두 제안 · 기록 네 필드 · 자동 모드는 합의만 자동이고 어긋나면
     ref + 승격 후보 · LLM 제안은 플래그로 끈다(자동 모드는 LLM 없이 성립하지 않는다)
  ③ 개체별 부모가 이름 부모다(후보 밖은 null) · 관련 링크는 조회 전용(노드 0)이고 근거
     순위는 describes 뒤다
  ④ ref 근처는 직접 링킹 노드의 표기로 읽을 때 찾는다([관련 원문] · 확장 노드 0 · 상한 손잡이)
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

# ────────────────────────────────────────────────────────────── ②
print("\n■ B91 ② 시트 두 모드 — 사람 지정(기본) · 자동(합의만)")
import builtins                                    # noqa: E402
import contextlib                                  # noqa: E402
import io                                          # noqa: E402
from cli import _screen, sheet_gate as SG          # noqa: E402
from core.llm import points as PT                  # noqa: E402
from core.state import sheets as SH                # noqa: E402

_RFQ = str(ROOT / "tests/fixtures/raw/RFQ01.xlsx")


def _gate(doc_id, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = SG.gate(_RFQ, doc_id, "prose", lenses=["process"], **kw)
    return out, _screen.strip_ansi(buf.getvalue())


_isatty, _input = sys.stdin.isatty, builtins.input
sys.stdin.isatty, builtins.input = (lambda: True), (lambda *_a: "")      # 터미널 · Enter
try:
    SH.path("XB91H").unlink(missing_ok=True)
    (_hr, _hs), _ho = _gate("XB91H")
    _rh = SH.read("XB91H") or {}
finally:
    sys.stdin.isatty, builtins.input = _isatty, _input
_head = next((l for l in _ho.splitlines() if "로직" in l and "LLM" in l), "")
show("② 사람 지정 — 표에 로직·LLM 두 열 · 기록 네 필드(로직·LLM·최종·결정 주체) · mock LLM = 로직(호출 0)",
     _head and _rh.get("decided_by") == "gate" and _rh.get("llm_by") == "mock"
     and _rh.get("logic") == _rh.get("llm") and _rh.get("sheets") == _hr
     and set(_rh["logic"]) == set(_rh["sheets"]), f"{SH.summary(_rh.get('sheets'))} · {_head.split()[-3:]}")

SH.path("XB91A").unlink(missing_ok=True)
_ra, _ao = _gate("XB91A", spec=SG.AUTO)
_rec_a = SH.read("XB91A") or {}
_real_j = PT.sheet_judge
PT.sheet_judge = lambda: (lambda name, sample, info: {"role": "prose", "reason": "시험 — 전부 prose"})
try:
    SH.path("XB91B").unlink(missing_ok=True)
    _rb, _bo = _gate("XB91B", spec=SG.AUTO)
    _rec_b = SH.read("XB91B") or {}
finally:
    PT.sheet_judge = _real_j
_dis = sorted(n for n, r in (_rec_b.get("logic") or {}).items() if r == "ref")
show("② 자동 — 합의 시트는 자동 · 어긋난 시트는 ref + 승격 후보(화면·기록) · 기록 네 필드",
     _ra[0] == _rec_a.get("sheets") and _rec_a.get("decided_by") == "auto"
     and not _rec_a.get("promote")
     and sorted(_rec_b.get("promote") or []) == _dis and _dis
     and all(_rec_b["sheets"][n] == "ref" for n in _dis)
     and all(_rec_b["sheets"][n] == "prose" for n, r in _rec_b["logic"].items() if r == "prose")
     and "승격 후보" in _bo and _rec_b.get("llm_by") == "live",
     f"합의 {len(_rec_b['sheets']) - len(_dis)} · 승격 후보 {_dis}")
SG._OPTS["llm"] = False
try:
    _rc_n, _o_n = 0, ""
    try:
        _gate("XB91C", spec=SG.AUTO)
    except SystemExit as e:
        _rc_n, _o_n = 1, str(e)
    (_rd, _sd), _do = _gate("XB91D", dry_run=True)
finally:
    SG._OPTS["llm"] = True
show("② LLM 제안은 끌 수 있다(플래그) — 표의 LLM 열이 「끔」 · 자동 모드는 합의라 LLM 없이 거부",
     _rc_n == 1 and "합의" in _o_n and "끔" in _do and not SH.path("XB91D").exists(),
     _o_n.splitlines()[0][:70])
for _d in ("XB91H", "XB91A", "XB91B"):
    SH.path(_d).unlink(missing_ok=True)

# ────────────────────────────────────────────────────────────── ③
print("\n■ B91 ③ prose 좌표 셋 — 주 좌표 · 개체별 부모 · 관련 링크")
from core.state import store as _ST                # noqa: E402
from cli import query as QR                        # noqa: E402

fresh()
run_document(load("CP01"))                         # 「노칭::노칭 프레스」 — ④의 직접 링킹 노드
_HINT = {   # 추출 힌트(창작) — 두 새 필드를 준다
    "X3-C001": {"entities": [{"surface": "버", "category": "Property", "parent": "노칭"}]},
    "X3-C002": {"entities": [{"surface": "속도", "category": "Property", "parent": "탭용접"}]},
    "X3-C003": {"entities": [], "about": [{"surface": "노칭", "category": "Process"},
                                          {"surface": "스태킹", "category": "Process"},
                                          {"surface": "없는공정", "category": "Process"}]},
}


def _stub3(cid, chunk, cfg, vocab):
    h = _HINT.get(chunk.get("source_locator"), {})
    return {"chunk_id": cid, "entities": h.get("entities", []), "relations": [],
            "attach": [], **({"about": h["about"]} if h.get("about") else {})}


_real = EX._candidates_for
EX._candidates_for = _stub3
try:
    _d0 = _ST.path(_ST.DEFECTS).read_text(encoding="utf-8") if _ST.path(_ST.DEFECTS).exists() else ""
    _pg0 = len(open_graph("process").nodes)
    run_document(dict(PROSE, doc_type="ppt_process", doc_id="X3", chunks=[
        dict(C1, source_locator="X3-C001", process_ref="스태킹", section="3. 스태킹",
             text="전 공정(노칭)의 버가 스태킹 정렬 불량을 만든다."),
        dict(C1, source_locator="X3-C002", process_ref="스태킹", section="3. 스태킹",
             text="적층 속도가 떨어졌다."),
        dict(C1, source_locator="X3-C003", process_ref=None, section="주간 이슈",
             text="주간 이슈 — 노칭 버 증가 · 스태킹 정렬 불량 재발."),
        dict(C1, source_locator="X3-R001", process_ref=None, section="도면목록",
             text="도면목록: 노칭 프레스 조립도 D-001 · 노칭 프레스 금형도 D-002",
             meta={"sheet_role": "ref"}),
        dict(C1, source_locator="X3-R002", process_ref=None, section="도면목록",
             text="도면목록: 노칭 공정 배치도 D-010", meta={"sheet_role": "ref"})]))
finally:
    EX._candidates_for = _real
_pg = open_graph("process")
_canon = {n["canonical"] for n in _pg.nodes.values()}
_defx = (_ST.path(_ST.DEFECTS).read_text(encoding="utf-8") if _ST.path(_ST.DEFECTS).exists()
         else "")[len(_d0):]
show("③ⓐ 「3. 스태킹」 아래 「전 공정(노칭)의 버」 → 이름 부모가 개체별 부모다 (`노칭::버`)",
     "노칭::버" in _canon and "스태킹::버" not in _canon, sorted(c for c in _canon if c.endswith("::버")))
show("③ⓒ 부모 후보 밖 이름은 null — 주 좌표가 부모다(`스태킹::속도`) · 결함 로그",
     "스태킹::속도" in _canon and "탭용접::속도" not in _canon and "부모 후보 밖" in _defx,
     [l for l in _defx.splitlines() if "부모 후보 밖" in l][:1])
_ch3 = _ST.read(_ST.CHUNKS, {})
_ab = [a for a in _ch3.get("about") or [] if a["chunk_id"].startswith("X3")]
_abn = sorted(_pg.get(a["node_id"])["canonical"] for a in _ab)
show("③ⓓ 없는 노드를 가리키는 관련 링크는 노드 0 · 버리고 기록 (조회 전용)",
     _abn == ["노칭", "스태킹"] and "없는공정" not in _canon and "관련 링크 미해소" in _defx
     and len(_pg.nodes) == _pg0 + 2, f"매달림 {_abn} · 노드 +{len(_pg.nodes) - _pg0}")
_knobs_file({"collect_limit": 60})     # 순위를 보려면 자르지 않는다(상한은 손잡이 — ⑤)
_rn, _rs = QR.answer("노칭"), QR.answer("스태킹")
_knobs_file(None)
_c3 = next(iter(a["chunk_id"] for a in _ab))


def _rank(res, cid):
    return next((i for i, c in enumerate(res["chunks"]) if c["chunk_id"] == cid), None)


show("③ⓑ 「주간 이슈」 청크가 노칭·스태킹 양쪽 질의의 근거다 — 관련 링크 · 순위는 describes 뒤",
     all(_rank(r, _c3) is not None and r["chunks"][_rank(r, _c3)]["tier"] == 3
         and all(c["tier"] <= 2 for c in r["chunks"][:_rank(r, _c3)]) for r in (_rn, _rs)),
     f"노칭 #{_rank(_rn, _c3)} · 스태킹 #{_rank(_rs, _c3)} of {len(_rs['chunks'])} · "
     f"tier {[c['tier'] for c in _rs['chunks']]}")

# ────────────────────────────────────────────────────────────── ④
print("\n■ B91 ④ ref 노드 근처 — 읽을 때 계산 · [관련 원문]")
_ra = QR.answer("노칭 프레스")
_rel = [c["source_locator"] for c in _ra.get("related") or []]
_txt = QR.render(_ra)
show("④ 「노칭 프레스」 질의에 [관련 원문] — 직접 링킹 노드 표기가 든 ref 청크만(확장 노드 「노칭」만 든 청크는 안 딸려 온다)",
     _rel == ["X3-R001"] and "[관련 원문]" in _txt
     and not ({"X3-R001", "X3-R002"} & {c["source_locator"] for c in _ra["chunks"]})
     and any(r.get("channel") == "ref" for r in _ra["trace"]["collection"]),
     [l.strip()[:60] for l in _txt.splitlines() if "[관련 원문]" in l])
_knobs_file({"ref_limit": 0})
_r0 = QR.answer("노칭 프레스")
_knobs_file(None)
_chn = _ST.read(_ST.CHUNKS, {})
_refc = {cid for cid, c in _chn["chunks"].items() if (c.get("meta") or {}).get("sheet_role") == "ref"}
show("④ 상한은 손잡이 — ref_limit 0이면 [관련 원문] 0 · 묶음에 키도 없다 · ref 청크 매달림 0(저장 0)",
     "related" not in _r0 and _refc
     and not ({d["chunk_id"] for d in _chn["describes"] + (_chn.get("about") or [])} & _refc),
     f"ref 청크 {len(_refc)}")
init.init(fresh_=True)

done()
