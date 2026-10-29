# -*- coding: utf-8 -*-
"""G6 ⑭ 산문 추출을 보이게 — 추출 예고 · 청크별 메타 줄 · 시간 기준 누적 줄 · 청크 단위 이어 쓰기 ·
`--step` 산문 관문 (B97).

창작 표본(mock · RFQ01 · 시험 전용 후보 함수 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50).

잠그는 성질:
  ⓐ 한 렌즈 산문 인입에 추출 예고 줄 — 부를 청크 = 청크 − ref − 재사용 · 청크 줄 수와 같다
  ⓑ 청크마다 메타 줄(개체 표기·카테고리 전부 · 관계 수) · 끝 줄에 사용량
  ⓒ 누적 줄은 시간 기준(호출이 늘면 시작 한 줄 · 간격마다 누적) · mock이고 호출 0이면 말이 없다
  B135(가짜 게이트웨이 — 실호출 갈래의 호출 보존) ⓐ 청크 하나의 경로만 바꾸면 그 청크만 부른다 · 결과가 전부 다시 부른 것과 같다
     ⓒ 도입 — 호출 보존 없는 옛 체크포인트로 호출 0 · 씨앗 ⓑ 지시문 문면만 바꾸면 재호출 0과 한 줄 · 판을 올리면 전부 다시
     ⓔ 중단 뒤 다시 — 끝난 호출은 부르지 않고 실패한 호출은 다시 부른다 (B97 ③의 부분 파일 이어 쓰기를 흡수 — 그 두 어서션은 이것으로
     고치고 「어댑터 판이 다르면 처음부터」는 지웠다: 같은 입력이면 어댑터 판과 무관하게 다시 쓴다)
  ⓕ --step 산문: 추출 예고에서 멈추면 체크포인트 0 · 추출 뒤에서 멈추면 그래프·큐 쓰기 0 ·
     체크포인트 완료 · 재실행은 추출 재사용 · 표 문서의 관문은 판정 예고 그대로
  B167 ⓐ `--extract-only`는 판정까지(쓰기 0 · 중간 저장 · md 판정 절 수 = 대장) ⓑ 확정은 판정 재생 · 그래프가 플래그 없는 인입과 같다
     (B155 ⓐⓑ 고침 · ⓔ 표 거부는 지움 — 표도 판정까지 · B155 ⓕ 고침 — 추출 뒤 관문도 묻는다)
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _ingest, _register, _run, _unregister, done, json,   # noqa: F401
                       open_graph, store)
from cli import _screen                     # noqa: E402
import os as _os                             # noqa: E402
# 넓은 화면(160칸)에서 잰다 — 개체 칸은 가변 칸이라 좁으면 `…`(전체는 `-v` · 로그) · 위치 두 칸(B118 ③ — 잘리지 않는 칸)이
# 폭을 더 써서 120칸에서는 개체 칸이 두 글자 모자란다(기대 변경)
_os.environ["COLUMNS"] = "160"
from cli.extract_screen import extract_screen  # noqa: E402
from core.build import extract as EX        # noqa: E402
from core.build.entry import _vocab          # noqa: E402
from core.llm import gateway                 # noqa: E402
from core.state.bootstrap import load_config  # noqa: E402

init.init(fresh_=True, all_=True)
_register()

print("\n■ B97 ① 추출 예고 · ② 청크별 줄")
_out = _ingest("--sheets", "auto")
_pre = [l for l in _out.splitlines() if "추출 예고 —" in l]
def _chunk_rows(text):
    """추출 표의 데이터 행(`i/m | 시트 | 청크 | …` — B98 ⑥ 표 · B118 ③ 위치 두 칸 · 기대 변경)."""
    return [l for l in text.splitlines() if re.match(r"\s*\d+/\d+ \| ", l)]


_rows = _chunk_rows(_out)
# 기대 변경(B135 ① — 예고는 「부를 n · 다시 씀 m」)
_m = re.search(r"청크 (\d+)\(ref 시트 (\d+)\) → 부를 (\d+) · 다시 씀 (\d+)\(같은 입력 — LLM 0\) → LLM ≤ (\d+)회",
               _pre[0] if _pre else "")
show("ⓐ 한 렌즈 산문 인입에 추출 예고 줄 — 부를 청크 = 청크 − ref − 다시 씀 = 청크 줄 수",
     bool(_m) and int(_m[1]) - int(_m[2]) - int(_m[4]) == int(_m[3]) == int(_m[5]) == len(_rows) > 0
     and "렌즈 예고" not in _out, (_pre or [""])[0].strip())

_env = json.loads(_P.parsed("RFQ01.json").read_text(encoding="utf-8"))
_ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
_loc = {c["source_locator"]: cid for cid, c in _ch.items() if c.get("doc_id") == "RFQ01"}
_cfg = load_config("process")
_orig = EX._candidates_for
_calls = []


def _fake(cid, chunk, cfg, vocab):
    """시험 전용 후보 — 청크마다 결정적(표기 둘 · 관계 하나)."""
    _calls.append(cid)
    n = len(_calls)
    return {"chunk_id": cid, "relations": [{"src": f"부품{n}", "rel": "part_of", "dst": "노칭"}],
            "attach": [], "entities": [{"surface": f"부품{n}", "category": "Component"},
                                       {"surface": "치수", "category": "Property"}]}


def _extract(note=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, made = EX.extract(_env, _cfg, _loc, _vocab(_cfg),
                               notice=note or extract_screen())
    return out, made, buf.getvalue()


EX._candidates_for = _fake
EX.invalidate("RFQ01")
_ref, _, _txt = _extract()
_ln = _chunk_rows(_txt)
show("ⓑ 청크마다 메타 줄(개체 표기·카테고리 전부 · 관계 수) · 끝 줄에 사용량",
     len(_ln) == len(_rows) > 0 and all("부품" in l and "[Component]" in l and "치수[Property]" in l
                                    and l.split(" | ")[5].strip() == "1" for l in _ln)   # 위치 두 칸(B118 ③ · 기대 변경)
     and any("추출 끝 —" in l and "LLM 사용량 — " in l for l in _txt.splitlines()),   # 기대 변경(B139 ⑤ — 문면은 재지 않는다)
     _ln[0].strip()[:90] if _ln else "")

print("\n■ B97 ② 시간 기준 누적 줄")
_tick0 = _screen.TICK_SECONDS
_screen.TICK_SECONDS = 0.1
_b1, _b2 = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(_b1):
    with _screen.ticker("시험"):
        time.sleep(0.4)                      # mock · 호출 0 → 말이 없다
with contextlib.redirect_stdout(_b2):
    with _screen.ticker("시험", where=lambda: "추출 2/9"):
        gateway.USAGE["calls"] += 1          # 시험 주입 — 호출이 시작됐다
        time.sleep(0.6)
gateway.USAGE["calls"] -= 1
_screen.TICK_SECONDS = _tick0
_t = _b2.getvalue().splitlines()
show("ⓒ 누적 줄은 시간 기준(시작 한 줄 · 간격마다 누적 · 경과) · mock이고 호출 0이면 말이 없다",
     _b1.getvalue() == "" and sum("LLM 사용 시작" in l for l in _t) == 1
     and sum("· 추출 2/9 · 호출" in l and "경과" in l for l in _t) >= 2, _t[1:2])

EX._candidates_for = _orig

# ────────────────────────────────────────────────────────────── B135 — 호출 단위 재사용 (가짜 게이트웨이 · 실호출 갈래)
print("\n■ B135 ① 호출 단위 재사용 · ② 도입 씨앗 · ③ 판과 문면 · 중단 뒤 다시")
import copy as _cp                                           # noqa: E402
import hashlib as _hl                                        # noqa: E402
import shutil as _sh                                         # noqa: E402
import tempfile as _tf                                       # noqa: E402
from fake_gateway import CALLS as _GW, Live as _Live          # noqa: E402
from core.build import extract_calls as _EC                  # noqa: E402
_cdir = _EC.folder("RFQ01")


def _ans(body):
    """가짜 ① — 보낸 청크 글마다 결정적인 개체 하나(입력이 같으면 같은 답)."""
    h = _hl.sha256(str(body.get("chunk")).encode("utf-8")).hexdigest()[:4]
    return {"entities": [{"surface": f"부품{h}", "category": "Component", "parent": None, "belongs_to": None, "value": None}],
            "relations": [], "about": []}


def _xl(env=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, made = EX.extract(env or _env, _cfg, _loc, _vocab(_cfg), notice=extract_screen())
    return out, made, buf.getvalue()


def _n():
    return sum(1 for p, _b in _GW if p == "extract")


def _clean():
    EX.invalidate("RFQ01")
    _sh.rmtree(_cdir, ignore_errors=True)
    del _GW[:]


_clean()
_env2 = _cp.deepcopy(_env)
_c2 = next(c for c in _env2["chunks"] if c.get("source_locator") in _loc and (c.get("meta") or {}).get("sheet_role") != "ref")
_c2.setdefault("meta", {})["section_path"] = str((_c2.get("meta") or {}).get("section_path") or "") + " › 시험 경로"
with _Live(by={"extract": _ans}):
    _full, _, _ = _xl()
    _nf = _n()
    del _GW[:]
    _one, _, _t1 = _xl(_env2)
    _n1 = _n()
    _clean()
    _all2, _, _ = _xl(_env2)
show("B135 ⓐ 청크 하나의 경로만 바꾼 재추출 → 그 청크만 부른다(호출 1) · 체크포인트 후보가 전부 다시 부른 것과 같다 · 예고에 「다시 씀」",
     _nf > 1 and _n1 == 1 and json.dumps(_one["candidates"]) == json.dumps(_all2["candidates"])
     and f"부를 1 · 다시 씀 {_nf - 1}" in _t1, f"전부 {_nf} · 경로 하나 바꾼 뒤 {_n1}")
_clean()
with _Live(by={"extract": _ans}):
    _xl()
    _sh.rmtree(_cdir, ignore_errors=True)                     # B134 판처럼 — 호출 보존 없음 · 체크포인트에 문면 칸 없음
    _ck = json.loads(EX.checkpoint_path("RFQ01").read_text(encoding="utf-8"))
    EX.checkpoint_path("RFQ01").write_text(json.dumps({k: v for k, v in _ck.items() if k not in ("prompt", "prompt_text")},
                                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del _GW[:]
    _r0, _m0, _t0 = _xl()
    _n0 = _n()
    _seed = len(list(_cdir.glob("*.json"))) if _cdir.exists() else 0
    EX.invalidate("RFQ01")                                    # 재인입이 체크포인트를 버린 뒤(같은 문서)
    del _GW[:]
    _r1, _, _ = _xl()
    _nr = _n()
show("B135 ⓒ 도입 — B134 판 체크포인트(호출 보존 없음)로 같은 문서 → 호출 0 · 씨앗 청크마다 · 체크포인트를 버린 뒤에도 호출 0",
     _n0 == 0 and not _m0 and _seed == _nf and f"씨앗 {_nf}" in _t0 and _nr == 0
     and json.dumps(_r1["candidates"]) == json.dumps(_full["candidates"]), f"호출 {_n0} · 씨앗 {_seed} · 버린 뒤 {_nr}")
_pd = Path(_tf.mkdtemp(prefix="b135p_"))
_sh.copytree(ROOT / "prompts", _pd / "prompts")
_pf = next((_pd / "prompts").glob("*_extract.md"))
_pdir0 = gateway.prompts_dir
gateway.prompts_dir = lambda: str(_pd / "prompts")
gateway._DRIFT_SAID.clear()
try:
    _pf.write_text(_pf.read_text(encoding="utf-8") + "\n<!-- 시험 — 서술만 -->\n", encoding="utf-8")
    with _Live(by={"extract": _ans}):
        EX.invalidate("RFQ01")
        del _GW[:]
        _rb, _, _tb = _xl()
        _nb = _n()
        _txt = _pf.read_text(encoding="utf-8")
        _v = next(ln for ln in _txt.splitlines() if ln.startswith("version:"))
        _pf.write_text(_txt.replace(_v, _v + "-시험", 1), encoding="utf-8")
        EX.invalidate("RFQ01")
        del _GW[:]
        _xl()
        _nv = _n()
finally:
    gateway.prompts_dir = _pdir0
    _sh.rmtree(_pd, ignore_errors=True)
show("B135 ⓑ 지시문 문면만 바꾼 사본(판 그대로) → 재호출 0 · 「서술만 바뀜」 한 줄 / 판을 올린 사본 → 그 지시문의 호출 전부 다시",
     _nb == 0 and "지시문 서술만 바뀜" in _tb and _nv == _nf, f"서술만 {_nb} · 판 올림 {_nv}/{_nf}")
_clean()
_k = {"n": 0}


def _flaky(body):
    _k["n"] += 1
    if _k["n"] == 2:
        raise gateway.GatewayError(500, "가짜 실패", "fake")
    if _k["n"] == 4:
        raise KeyboardInterrupt                              # 시험 주입 — 넷째 호출에서 끊긴다
    return _ans(body)


with _Live(by={"extract": _flaky}):
    try:
        _xl()
    except KeyboardInterrupt:
        pass
_mid = (EX.has_checkpoint("RFQ01"), len(list(_cdir.glob("*.json"))) if _cdir.exists() else 0)
with _Live(by={"extract": _ans}):
    _re, _made, _ = _xl()
    _ne = _n()
show("B135 ⓔ 중단 뒤 다시 — 끝난 호출은 다시 부르지 않고(보존 둘) 실패한 호출은 다시 부른다 · 체크포인트는 끝까지 돈 뒤에만 · 한 번에 돈 것과 같다",
     _mid == (False, 2) and _ne == _nf - 2 and _made and json.dumps(_re["candidates"]) == json.dumps(_full["candidates"]),
     f"끊긴 뒤 {_mid} · 다시 부름 {_ne}/{_nf}")
_clean()

print("\n■ B97 ④ --step 산문 관문")


def _graph():
    """그래프 스냅샷 — 경계(GraphStore)를 지나 읽는다."""
    g = open_graph("process")
    return json.dumps([g.nodes, g.edges], sort_keys=True, default=str)


EX.invalidate("RFQ01")
# 기대 변경(B132 — 산문은 시트마다 구조 확인 관문 · RFQ01은 산문 시트 셋): 선택 · 구조 확인 ×3 · 파싱 · 좌표 → 추출 예고에서 q
_o1 = _ingest("--sheets", "auto", "--step", answers="c\n" * 6 + "q\n")
_ck1 = EX.has_checkpoint("RFQ01")
_q0 = json.dumps(store.read(store.QUEUE, []), sort_keys=True)
_g0 = _graph()
_o2 = _ingest("--sheets", "auto", "--step", answers="c\n" * 7 + "q\n")
_same = (json.dumps(store.read(store.QUEUE, []), sort_keys=True) == _q0 and _graph() == _g0)
_o3 = _ingest("--sheets", "auto")
_o4 = _run("ingest-file", str(ROOT / "tests/fixtures/raw/CP01.xlsx"), "--doc-type", "cp",
           "--allow-mock", "--step", answers="c\nc\nc\nq\n")
show("ⓕ --step 산문: 추출 예고 멈춤 = 체크포인트 0 · 추출 뒤 멈춤 = 그래프·큐 쓰기 0 · 완료 · "
     "재실행은 추출 재사용 · 표 문서는 판정 예고 관문 그대로",
     "[4/8] 추출 예고" in _o1 and not _ck1
     and "[5/8] 추출 결과·판정 예고" in _o2 and EX.has_checkpoint("RFQ01")
     and _same and "체크포인트 재사용(LLM 0)" in _o3 and "[4/7] 판정 예고" in _o4
     and "] 추출 예고 —" not in _o4,
     [l.strip()[:60] for l in _o2.splitlines() if "[5/8]" in l])
_unregister()
init.init(fresh_=True, all_=True)

print("\n■ B155 · B167 — 판정까지(--extract-only) · 추출 md · 확정 = 판정 재생")
import hashlib as _hl                        # noqa: E402
from core.state.bootstrap import bootstrap as _bs   # noqa: E402
for _lay in ("process", "quality"):
    _bs(_lay, echo=False)
_register()


def _writes():
    """그래프 · 사전 · 큐 · 청크 · 문서 대장의 바이트(쓰기 0을 잰다)."""
    d = _P.data()
    fs = [p for lay in ("process", "quality") for p in sorted((d / lay).rglob("*")) if p.is_file()]
    fs += [d / n for n in ("dictionary.json", "review_queue.json", "chunks.json", "doc_registry.json")]
    return {p.name + str(p.parent.name): _hl.sha256(p.read_bytes()).hexdigest() if p.exists() else None
            for p in fs if not p.name.endswith(".lock")}


from cli.extract_md import verdict_of as _vof          # noqa: E402
from core.build import ledger as _LG, replay as _RP    # noqa: E402


def _world():
    """층마다 노드(이름 · 카테고리 · status) · 엣지(이름으로) · 큐(종류 · 문서) — id 밖의 모양(플래그 없이 넣은 것과 견준다)."""
    names = {i: n.get("canonical") for lay in ("process", "quality") for i, n in open_graph(lay).nodes.items()}
    out = {lay: (sorted((n.get("canonical"), n.get("category"), n.get("status")) for n in open_graph(lay).nodes.values()),
                 sorted((names.get(e["src"]), e["rel"], names.get(e["dst"])) for e in open_graph(lay).edges))
           for lay in ("process", "quality")}
    out["queue"] = sorted((x["kind"], x.get("doc_id")) for x in store.read(store.QUEUE, []))
    return out


def _again_of(text):
    """끝 줄의 확정 줄 — `▶ 확정(…): <같은 줄>`."""
    return next((ln.split("▶ 확정", 1)[1].split("): ", 1)[-1].strip() for ln in text.splitlines() if "▶ 확정" in ln), "")


EX.invalidate("RFQ01")
_w0 = _writes()
_x1 = _ingest("--sheets", "auto", "--extract-only")
_w1 = _writes()
_md155 = _P.export("extract_RFQ01.md")
_again = _again_of(_x1)
_rows167 = [r for r in (_LG.read_partial("RFQ01") or {}).get("rows") or [] if r.get("role") in _RP.ROLES]
_mdt = _md155.read_text(encoding="utf-8") if _md155.exists() else ""
_lays = {r.get("layer") or "—" for r in _rows167}
_tally = {lay: "- " + " · ".join(f"{k} {sum(1 for r in _rows167 if (r.get('layer') or '—') == lay and _vof(r)[0] == k):,}"
                                 for k in ("기존 노드", "새 노드", "보류")) for lay in _lays}
show("B167 ⓐ (B155 ⓐ 고침) 산문 --extract-only = 판정까지 — 그래프 · 사전 · 큐 · 청크 · 문서 대장이 실행 전과 바이트 같음 · 확정 대장 0 · "
     "판정 대장은 중간 저장에 · 추출 확인 md 판정 절의 기존 · 새 · 보류 수가 대장과 같다 · 끝 줄의 확정 줄",
     EX.has_checkpoint("RFQ01") and _w0 == _w1 and _LG.read("RFQ01") is None and _rows167
     and all(f"## 판정 — 층 {lay}" in _mdt and _tally[lay] in _mdt for lay in _lays) and "판정까지 — 그래프 쓰기 0" in _x1
     and _again.startswith("python run.py ingest-file ") and "--extract-only" not in _again and "--sheets auto" in _again,
     f"확정 줄 {_again} · 바뀐 파일 {[k for k in _w1 if _w0.get(k) != _w1.get(k)]} · 수 {_tally}")
_x2 = _run(*_again.split()[2:])
def _verdicts(rows):
    """값마다 판정 — (자리 · 열 · 표기 · 판정 · 붙은 이름)."""
    return sorted((str(r.get("locator")), str(r.get("field")), str(r.get("surface")), r.get("verdict"),
                   str(r.get("target") or r.get("canonical"))) for r in rows if r.get("role") in _RP.ROLES)


_fin = (_LG.read("RFQ01") or {}).get("rows") or []
_due = [r for r in _fin if r.get("role") in _RP.ROLES and str(r.get("path")).endswith("+judge")]
_wx = _world()
init.init(fresh_=True, all_=True)
for _lay in ("process", "quality"):
    _bs(_lay, echo=False)
_register()
EX.invalidate("RFQ01")
_ingest("--sheets", "auto")                              # 처음부터 플래그 없이
show("B167 ⓑ (B155 ⓑ 고침) 확정 줄을 그대로 — 추출 재사용 · 값마다 판정이 판정까지의 대장 그대로(다시 판정한 값 0) · 중간 저장 지움 · "
     "그래프 · 큐가 처음부터 플래그 없이 넣은 것과 같다",
     "체크포인트 재사용(LLM 0)" in _x2 and _verdicts(_fin) == _verdicts(_rows167) and not _due
     and _LG.read_partial("RFQ01") is None and _wx == _world(),
     f"판정 {len(_verdicts(_fin))}값 · 다시 판정 {len(_due)}")
init.init(fresh_=True, all_=True)
for _lay in ("process", "quality"):
    _bs(_lay, echo=False)
_register()
EX.invalidate("RFQ01")
_x6 = _ingest("--sheets", "auto", "--extract-only", "--step", answers="c\n" * 9)
show("B155 ⓕ (B167 고침) --extract-only --step(pty) — 구조 관문 · 추출 예고 · 추출 뒤 관문(판정 예고)을 묻고 판정까지 가서 멈춘다",
     "구조 확인" in _x6 and "[4/8] 추출 예고" in _x6 and "[5/8] 추출 결과·판정 예고" in _x6 and "판정까지 — 그래프 쓰기 0" in _x6,
     [ln.strip()[:50] for ln in _x6.splitlines() if "/8]" in ln][:6])
_unregister()
init.init(fresh_=True, all_=True)

done()
