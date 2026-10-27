# -*- coding: utf-8 -*-
"""G6 — **PPT: 슬라이드가 추출 단위 · 캡처를 추출에 · 덱 구조 1회 · 청크 공정은 목록** (B125).

대표 사례 하나씩(가벼운 회차 · 창작 표본 `make_ppt.build_report` — 수치는 근거가 아니다 [정정] 50 · 덱 구조 · 추출은 가짜
게이트웨이 — 지시문 · 조립 · 검사 · 구축은 실물):
  ⓐ 상자 — 글 상자 제목 + 작은 상자 여섯 슬라이드: 본문 근거 청크 1 · 추출 호출 1 · 상자 분할 0
  ⓑ 같은 슬라이드 — 본문 + 표 + 노트: 추출 입력 하나에 셋 다 · 표 위치 `S4-TB1` 그대로 · 그림 요약에만 있는 값은 버림
  ⓒ 캡처 — 그림 없는 슬라이드에도 추출 입력에 캡처(`capture=page`) · 렌더가 없으면 `none` + 화면 수 · 인입은 선다
  ⓓ 덱 구조 — 글 상자 제목 → 그 글이 제목 · 「(계속)」 → 앞 슬라이드의 경로 · 공정 · 덱 개요가 모든 추출 맥락 줄에 · 골격 밖 공정 버림 셈
  ⓔ 다공정 — 노칭 · 스태킹 슬라이드: 개체가 각자 제 공정 아래 · 언급만 한 공정은 노드 0 + 관련 링크 · `--coord` 없이 `ingest-dir` 성공
  ⓕ 고침 · 재생 — 공정 고침 → 기록 → 다시 파싱이 그대로(덱 구조 LLM 0)
  B151 ⓐ~ⓕ 덱 판단은 층 · 골격 · 문서 좌표를 모른다(두 상태의 입력이 같다 · 층 config를 바꿔도 재사용) · 다루는 것 · 공정 표기 검사 ·
       공정 걸기는 표와 같은 길(정확 · ⑨ 표기마다 한 번 · 목록 원소마다 · 못 맞으면 그대로 → 큐) · 공정 없는 덱 · 옛 언급 고침은 읽지 않는다
네 벌(A · B 같음 · C 바뀐 몫)은 마감 한 줄의 네 벌 단계가 잰다.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _iso, done   # noqa: F401

from fake_gateway import CALLS, Live                      # noqa: E402
from g6_common import SCHEMA                              # noqa: E402
from fixtures.make_ppt import build_report               # noqa: E402
import run as RUN                                        # noqa: E402
from cli import structure_screen as STS                  # noqa: E402
from core.build import deck as DK, extract as EX, extract_unit as EU, ledger as LG, structure as ST, values as VL  # noqa: E402
from parser import pipeline, render, struct_map, tagger as TG   # noqa: E402
from parser.adapters import basic_ppt as PX              # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="b125_"))
DT, DID = "b125_ppt", "B125D"
PATH = build_report(TMP / f"{DID}.pptx")


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


def _register():
    p = _P.schemas(f"{DT}.json")
    _P.ensure(p)
    p.write_text(json.dumps({**SCHEMA, "doc_type": DT, "layer": "process", "payload_kind": "prose"}, ensure_ascii=False),
                 encoding="utf-8")
    ad = _P.adapters(f"{DT}.py")
    _P.ensure(ad)
    ad.write_text("from parser.adapters import basic_ppt\n"
                  f"ADAPTER = {{**basic_ppt.ADAPTER, \"doc_type\": {DT!r}}}\nextract = basic_ppt.extract\n", encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[DT] = {"doc_type": DT, "status": "registered", "layer": "process", "schema": f"schemas/{DT}.json",
               "adapter": str(ad), "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


# ── 가짜 LLM의 답(창작) — 덱 구조 · 추출 · 그림 요약
# 기대 변경(B151 ① — 덱 판단의 칸: 언급 공정 0 · 다루는 것 `subject` · 공정은 문서 표기)
DECK = {"slides": [
    {"slide": 1, "title": "노칭 · 스태킹 점검 보고", "section": None, "continues": None, "subject": None, "processes": ["없는공정"],
     "no_entities": True},
    {"slide": 2, "title": "노칭 금형 점검 결과", "section": None, "continues": None, "subject": "노칭 금형", "processes": ["노칭"],
     "no_entities": False},
    {"slide": 3, "title": "노칭 금형 점검 결과 (계속)", "section": None, "continues": 2, "subject": None, "processes": [],
     "no_entities": False},
    {"slide": 4, "title": "커터 사양", "section": None, "continues": None, "subject": "커터 사양", "processes": ["노칭"],
     "no_entities": False},
    {"slide": 5, "title": "노칭 · 스태킹 연동 점검", "section": None, "continues": None, "subject": "노칭 · 스태킹 연동 점검",
     "processes": ["노칭", "스태킹"], "no_entities": False}],
    "overview": "노칭 금형과 스태킹 연동을 점검한 보고서다."}


def _ent(surface, cat, parent=None, value=None):
    return {"surface": surface, "category": cat, "parent": parent, "belongs_to": None, "value": value}


def _extract(body):
    t = body["chunk"]
    ents = []
    if "마모 0.05mm" in t:
        ents = [_ent("금형", "Unit")]
    elif "다이 균열" in t:
        ents = [_ent("다이", "Unit")]
    elif "아래 표는" in t:
        ents = [_ent("장력", "Property", value="30N"), _ent("압력", "Property", value="5bar"),
                _ent("온도", "Property", value="80도")]
    elif "매거진" in t:
        # 기대 변경(B151 ② — 다른 공정 언급은 덱 판단이 아니라 그래프 단계의 산문 함수가 잡는다: 본문의 「탭용접」이 개체로 뽑히면 가드)
        ents = [_ent("커터", "Unit", parent="노칭"), _ent("매거진", "Unit", parent="스태킹"), _ent("탭용접", "Unit")]
    return {"entities": ents, "relations": [], "about": []}


def _live():
    return Live(by={"deck": lambda b: DECK, "extract": _extract, "outline": lambda b: {"headings": []},
                    "reinforce": lambda b: {"pick": None}})


def _parse(**kw):
    with _live():
        res = pipeline.parse(PX, DID, str(PATH), closed_list=TG.closed_list("process"), layer="process",
                             deck=DK.decker(), capture=True, structure_fixes=ST.fixes_of(DID),
                             summarize=lambda ref, **k: "도면 — 온도 80도", **kw)
        calls = [p for p, _b in CALLS]
    env = res.envelope
    env["doc_type"] = DT
    for c in env["chunks"]:
        c["doc_type"] = DT
    return res, env, calls


def _run(env):
    notes = []
    with _live(), _quiet():
        run_document(dict(env), notice=notes.append)
        calls = list(CALLS)
    return notes, calls


with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()
_keep = (render.capture_path, render.render_pages)
render.capture_path = lambda path=None, probe=False: (True, "시험", None)      # 기대 변경(B128 ① — 판정 한 자리의 이름 · 답 꼴)
render.render_pages = lambda path: {n: f"PNG{n}".encode() for n in range(1, 6)}   # 보이는 슬라이드 5장의 가짜 렌더
struct_map.invalidate(DID)
RES, ENV, PCALLS = _parse()
NOTES, CALLS1 = _run(ENV)
_by = {c["source_locator"]: c for c in ENV["chunks"]}
_ext = [b for p, b in CALLS1 if p == "extract"]

# ────────────────────────────────────────────────────────────── ⓐ 상자
print("\n■ ⓐ 상자 — 슬라이드 = 추출 1회")
_s2 = [b for b in _ext if "마모 0.05mm" in b["chunk"]]
show("ⓐ 글 상자 제목 + 작은 상자 여섯 → 본문 근거 청크 1 · 추출 호출 1 · 상자 분할 0",
     "슬라이드 2" in _by and not any(k.startswith("슬라이드 2#") for k in _by) and len(_s2) == 1
     and all(x in _s2[0]["chunk"] for x in ("→ 버 발생", "점검 완료")),
     f"슬라이드 2 청크 {[k for k in _by if k.startswith('슬라이드 2')]} · 호출 {len(_s2)}")

# ────────────────────────────────────────────────────────────── ⓑ 같은 슬라이드
print("\n■ ⓑ 같은 슬라이드 — 본문 · 표 · 노트 · 그림 요약이 한 입력")
_s4 = next((b for b in _ext if "아래 표는" in b["chunk"]), {"chunk": ""})
_rows = {r.get("surface"): r for r in (LG.read(DID) or {}).get("rows") or [] if r.get("role") == "entity"}
_v = {k: (_rows.get(k) or {}).get("value", {}).get("verdict") for k in ("장력", "압력", "온도")}
show("ⓑ 추출 입력 하나에 본문 · 표 · 노트 · 표 위치 S4-TB1 그대로 · 표 · 노트의 값은 앉고 그림 요약에만 있는 값은 버린다",
     all(x in _s4["chunk"] for x in ("아래 표는", "[표 S4-TB1]", "30N", "[노트]", "5bar")) and "S4-TB1" in _by
     and _v == {"장력": VL.LANDED, "압력": VL.LANDED, "온도": VL.DROPPED},
     f"값 {_v} · 입력에 표 {'[표 S4-TB1]' in _s4['chunk']} · 노트 {'[노트]' in _s4['chunk']}")

# ────────────────────────────────────────────────────────────── ⓒ 캡처
print("\n■ ⓒ 캡처 — 그림 유무와 무관하게 추출에")
_ck = json.loads(EX.checkpoint_path(DID).read_text(encoding="utf-8"))
_cap = {c["chunk_id"]: c.get("capture") for c in _ck["candidates"] if c.get("capture")}
_pre = next((n for n in NOTES if n.get("단계") == "추출예고"), {})
EX.invalidate(DID)                                   # 렌더가 없는 환경 — 같은 문서를 다시 뽑는다
EU._PAGES.clear()
render.capture_path = lambda path=None, probe=False: (False, "없음", "soffice 없음")
_n2, _c2 = _run(ENV)
_pre2 = next((n for n in _n2 if n.get("단계") == "추출예고"), {})
_ck2 = json.loads(EX.checkpoint_path(DID).read_text(encoding="utf-8"))
render.capture_path, render.render_pages = _keep
show("ⓒ 그림 없는 슬라이드에도 캡처가 추출 입력에(capture=page) · 렌더가 없으면 none + 화면 수(사유) · 인입은 선다",
     _s2 and _s2[0].get("_images") == 1 and set(_cap.values()) == {"page"}
     and (_pre.get("캡처") or {}).get("있음") == 4
     and (_pre2.get("캡처") or {}).get("없음") == 4 and (_pre2["캡처"].get("사유") == "soffice 없음")
     and {c.get("capture") for c in _ck2["candidates"] if c.get("capture")} == {"none"}
     and not any(b.get("_images") for p, b in _c2 if p == "extract"),
     f"캡처 {_pre.get('캡처')} → 렌더 없음 {_pre2.get('캡처')}")

# ────────────────────────────────────────────────────────────── ⓓ 덱 구조
print("\n■ ⓓ 덱 구조 — 제목 · 이어짐 · 개요 · 버림")
_dk = RES.report.get("deck") or {}
show("ⓓ 글 상자 제목이 제목 · (계속)은 앞 슬라이드의 경로 · 공정 · 덱 개요가 모든 추출 맥락 줄에 · 골격 밖 공정 버림 셈",
     _by["슬라이드 2"]["section"] == "노칭 금형 점검 결과"
     and _by["슬라이드 3"]["meta"]["section_path"] == _by["슬라이드 2"]["meta"]["section_path"]
     and _by["슬라이드 3"]["process_ref"] == "노칭"
     and _ext and all("개요: 노칭 금형과 스태킹 연동을 점검한 보고서다." in b["chunk"] for b in _ext)
     and (_dk.get("버림") or {}).get("공정") == 1 and _dk["수"]["이어짐"] == 1
     and (_dk["수"]["공정둘이상"] == 1) and PCALLS.count("deck") == 1
     and any(n.get("개체없음") == 1 for n in NOTES if n.get("단계") == "추출예고"),
     f"제목 {_by['슬라이드 2']['section']!r} · 경로 {_by['슬라이드 3']['meta']['section_path']!r} · 수 {_dk.get('수')} · "
     f"버림 {_dk.get('버림')}")

# ────────────────────────────────────────────────────────────── B143 ⓑ 덱 블록
print("\n■ B143 ⓑ 덱 블록 — 덱 판단이 parsed JSON 한 곳에")
from parser import deck as PDK                           # noqa: E402
_blk = (ENV.get("deck") or {}).get("slides") or []
_vals = {i: list(x.values()) for i, x in enumerate(_blk, 1)}
_bad = PDK.mismatch({**ENV, "chunks": [dict(c, process_ref="스태킹") if c["source_locator"] == "슬라이드 2" else c
                                       for c in ENV["chunks"]]})
# 기대 변경(B151 ① — 언급 칸 0 · 다루는 것 칸)
show("B143 ⓑ 봉투 하나에 슬라이드마다 이어짐 · 제목 초안과 판단 · 공정 목록 · 다루는 것 · 개체 없음 · 버림 · 근거 위치 · 청크 칸과 "
     "어긋나지 않는다(어긋나게 바꾸면 결함으로 잡힌다) · 개요도 블록에(옛 doc_overview 0)",
     len(_blk) == 5 and not PDK.mismatch(ENV) and _bad and "doc_overview" not in ENV
     and 2 in _vals[3] and ["노칭", "스태킹"] in _vals[5] and "노칭 · 스태킹 연동 점검" in _vals[5] and ["공정"] in _vals[1]
     and not any("mentions" in x for x in _blk)
     and "노칭 금형 점검 결과" in _vals[2] and ["슬라이드 4", "S4-TB1", "S4-P1"] in _vals[4]
     and (ENV.get("deck") or {}).get("overview") == DECK["overview"],
     f"슬라이드 {len(_blk)} · 어긋남 {len(PDK.mismatch(ENV))} → 바꾸면 {len(_bad)} · 3번 {_blk[2] if len(_blk) > 2 else None}")

# ────────────────────────────────────────────────────────────── ⓔ 다공정
print("\n■ ⓔ 다공정 — 개체는 제 공정 아래 · 언급은 관련 링크")
_g = open_graph("process")
_names = {n.get("canonical") for n in _g.nodes.values()}
_tab = next(nid for nid, n in _g.nodes.items() if n.get("canonical") == "탭용접")
_ch = store.read(store.CHUNKS, {})
_s5 = next(cid for cid, c in _ch["chunks"].items() if c.get("doc_id") == DID and c.get("source_locator") == "슬라이드 5")
# `--coord` 없이 폴더째 넣기 — mock(덱 구조 힌트) 하위 실행
_dir = TMP / "dir"
_dir.mkdir()
(_dir / f"{DID}.pptx").write_bytes(PATH.read_bytes())
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
_hint = _FXR.EXTRACT_HINTS / f"{DID}@deck.json"
_hint.write_text(json.dumps(DECK, ensure_ascii=False), encoding="utf-8")
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()


def _sub(*a):
    return subprocess.run([sys.executable, "run.py", *a], cwd=str(ROOT), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, env={**_iso.isolated_env(), "USE_MOCK": "1"}, timeout=600)


# B143 ⓐ — 공정 목록(슬라이드 5 노칭 · 스태킹)이 든 덱으로 등록 실경로 — 좌표 쌍 표가 목록을 받는다
_rg = _sub("register", "generate", "b143_reg", "process", str(_dir / f"{DID}.pptx"), "--use-basic", "--allow-mock")
_rs = _sub("register", "status", "b143_reg", "--allow-mock")
show("B143 ⓐ 공정 목록이 둘 이상인 슬라이드가 든 덱 — register generate --use-basic → status가 끝까지 돈다(좌표 쌍 표 · 관문 줄)",
     _rg.returncode == 0 and "좌표 쌍 —" in _rg.stdout and "[결함]" not in _rg.stdout + _rg.stderr
     and _rs.returncode == 0 and "기계 관문(하네스): PASS" in _rs.stdout,
     f"generate rc {_rg.returncode} · status rc {_rs.returncode} · "
     + next((ln.strip() for ln in _rg.stdout.splitlines() if "좌표 쌍 —" in ln), (_rg.stdout + _rg.stderr)[-120:]))
# B143 ⓓ · ⓔ — PPT --split-only: 추출 0 · 그래프 쓰기 0 · parsed JSON과 md · md는 봉투만으로 찍은 글
from cli import envelope_md as EMD                       # noqa: E402
_so = _sub("ingest-file", str(_dir / f"{DID}.pptx"), "--doc-type", DT, "--allow-mock", "--split-only")
_md = _P.export(f"split_{DID}.md")
_pj = json.loads(_P.parsed(f"{DID}.json").read_text(encoding="utf-8")) if _P.parsed(f"{DID}.json").exists() else {}
_mdt = _md.read_text(encoding="utf-8") if _md.exists() else ""
import re as _re                                         # noqa: E402
show("B143 ⓓ PPT --split-only — 추출 호출 0 · 그래프 쓰기 0 · parsed JSON과 md가 남는다 · md 슬라이드 표 행 수 = 덱 블록 슬라이드 수",
     _so.returncode == 0 and "구조까지" in _so.stdout and not EX.checkpoint_path(DID).exists()
     and not open_graph("process").nodes.keys() - {n for n, x in open_graph("process").nodes.items() if x.get("status") == "seed"}
     and _pj.get("deck") and len([ln for ln in _mdt.splitlines() if _re.match(r"^\| \d+ \|", ln)]) == len(_pj["deck"]["slides"]),
     f"rc {_so.returncode} · md {_md.exists()} · 표 행 {len([ln for ln in _mdt.splitlines() if _re.match(r'^[|] [0-9]+ [|]', ln)])} · "
     f"덱 블록 {len((_pj.get('deck') or {}).get('slides') or [])}")
show("B143 ⓔ md ⊆ JSON — md 글자 = parsed JSON(봉투) 하나로 찍은 글(md를 쓰는 함수는 봉투 밖을 읽지 않는다)",
     bool(_mdt) and _mdt == "\n".join(EMD.lines(_pj)) + "\n", f"md {len(_mdt)}자")
_p = _sub("ingest-dir", str(_dir), "--doc-type", DT, "--allow-mock")
_hint.unlink(missing_ok=True)
show("ⓔ 노칭 · 스태킹 슬라이드의 개체가 각자 제 공정 아래 · 언급만 한 탭용접은 노드 0 + 관련 링크 · --coord 없이 ingest-dir 성공",
     {"노칭::커터", "스태킹::매거진"} <= _names and not any(x.endswith("::탭용접") for x in _names if x)
     and {"chunk_id": _s5, "node_id": _tab} in (_ch.get("about") or [])
     and _p.returncode == 0 and "덱 구조 — 슬라이드 5" in _p.stdout,
     f"노드 {sorted(x for x in _names if x and ('커터' in x or '매거진' in x))} · ingest-dir rc {_p.returncode} · "
     + (_p.stdout + _p.stderr).strip().splitlines()[-1][:120])

# ────────────────────────────────────────────────────────────── B146 ⓔ 중간 파일 지도
print("\n■ B146 ⓔ 중간 파일 지도 — 표 · 엑셀 산문 · PPT를 하나씩 넣은 상태 루트 ↔ 상태 폴더 가이드 표")
from g6_common import RFQ as _RFQ6, _register as _reg6, DT as _DT6   # noqa: E402 — 산문 엑셀 표본(B83)
with _quiet():
    init.init(fresh_=True, all_=True)                     # 클린 — 앞 절의 산출이 섞이지 않게
    RUN.cmd_bootstrap([])
_register()
_reg6()
_hint.write_text(json.dumps(DECK, ensure_ascii=False), encoding="utf-8")
_ins6 = [_sub("ingest-file", str(_dir / f"{DID}.pptx"), "--doc-type", DT, "--allow-mock").returncode,
         _sub("ingest-file", str(ROOT / "tests/fixtures/raw/CP01.xlsx"), "--doc-type", "cp", "--allow-mock").returncode,
         _sub("ingest-file", str(_RFQ6), "--doc-type", _DT6, "--allow-mock", "--sheets", "2-4:prose 5:ref *:skip").returncode]
_hint.unlink(missing_ok=True)
_files = sorted(str(f.relative_to(_P.home())) for f in _P.home().rglob("*")
                if f.is_file() and not any(x.startswith(".") or x == "__pycache__" for x in f.relative_to(_P.home()).parts))
_gd = (ROOT / "docs/가이드/상태_폴더_가이드.md").read_text(encoding="utf-8")
_rows6 = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in _gd.split("### 2-1.")[1].split("\n## ")[0].splitlines()
          if ln.startswith("| `")]


def _rx146(tok, doc=None):
    """지도의 자리 → 정규식 — `<doc_id>`는 그 문서 · 다른 `<…>`는 한 칸 · `/`로 끝나면 그 아래 전부."""
    parts = _re.split(r"(<[^>]+>)", tok)
    return _re.compile("".join((_re.escape(doc) if doc and x == "<doc_id>" else "[^/]+") if x.startswith("<") else _re.escape(x)
                               for x in parts) + (".*" if tok.endswith("/") else ""))


_toks6 = [(r, _re.findall(r"`([^`]+)`", r[0])) for r in _rows6]
_loose6 = [f for f in _files if not any(_rx146(t).fullmatch(f) for _r, ts in _toks6 for t in ts)]
_miss6 = [(t, d) for r, ts in _toks6 for col, d in ((6, "CP01"), (7, "RFQ01"), (8, DID)) if r[col] == "●"
          for t in ts if not any(_rx146(t, d).fullmatch(f) for f in _files)]
show("B146 ⓔ 중간 파일 지도 — 표 · 엑셀 산문 · PPT를 하나씩 넣은 상태 루트의 파일이 전부 가이드 표의 자리에 들고 · 표가 「생긴다(●)」고 한 "
     "자리는 그 포맷 문서의 파일이 있다",
     _ins6 == [0, 0, 0] and _files and not _loose6 and not _miss6,
     f"인입 rc {_ins6} · 파일 {len(_files)} · 표 밖 {_loose6[:4]} · 없음 {_miss6[:4]}")

# B146 ⓐ~ⓓ — 구조 블록(엑셀 · Word) · 덱 블록과 같은 읽기 함수 · md는 봉투 하나에서 · 문서 해시 · 확정 시트
from core.state import ids as _IDS6                         # noqa: E402
from parser.adapters import basic_docx as _BD6               # noqa: E402
from parser.struct_rule import labels_hash as _LH6           # noqa: E402
_rq = json.loads(_P.parsed("RFQ01.json").read_text(encoding="utf-8"))
_mdq = _P.export("split_RFQ01.md").read_text(encoding="utf-8")
_P.work("struct_maps", "RFQ01.json").unlink(missing_ok=True)       # 보고 · 캐시 없이 — 봉투(JSON)만
struct_map.invalidate("B146W")
_ew = pipeline.parse(_BD6, "B146W", str(ROOT / "tests/fixtures/raw/DOC01.docx"), closed_list=[],
                     structure=ST.structurer()).envelope
_ewj = json.loads(json.dumps(_ew, ensure_ascii=False))
_uq = (_rq.get("structure") or {}).get("units") or []
show("B146 ⓐ 구조 블록 — 엑셀 산문(시트 둘 이상) · Word 봉투에 단위마다 목차 나무 · 청크 경계 · 판단 출처 · md는 봉투(JSON) 하나로 찍은 글과 같다",
     len(_uq) >= 2 and all(u.get("headings") and u.get("chunks") and u.get("by") and u.get("source") for u in _uq)
     and EMD.text("RFQ01", _rq) == _mdq and (_ewj.get("structure") or {}).get("units")
     and EMD.text("B146W", _ewj) == EMD.text("B146W", _ew) and "## 시트" in EMD.text("B146W", _ewj),
     f"단위 {[(u['unit'], u['by'], len(u['chunks'])) for u in _uq]} · Word 단위 {len((_ewj.get('structure') or {}).get('units') or [])}")
_pj6 = json.loads(_P.parsed(f"{DID}.json").read_text(encoding="utf-8"))
show("B146 ⓑ PPT md는 B143 꼴 그대로 · 덱 블록과 구조 블록이 같은 읽기 함수(units)로 읽힌다(단위 → 그 근거 청크)",
     EMD.text(DID, _pj6) == "\n".join(EMD.lines(_pj6)) + "\n" and EMD.units(_pj6) and EMD.units(_rq)
     and all(cs for _u, cs in EMD.units(_pj6) + EMD.units(_rq)),
     f"PPT 단위 {len(EMD.units(_pj6))} · 엑셀 단위 {len(EMD.units(_rq))}")
_u0 = _uq[0]
ST.confirm("RFQ01", _u0["unit"], {**_u0, "labels": _LH6(_u0.get("labels") or [])}, ST.doc_state("RFQ01")["hints"])
_cf0 = ST.confirmed_path().read_bytes()
_x7 = _sub("ingest-file", str(_RFQ6), "--doc-type", _DT6, "--allow-mock", "--sheets", "2-4:prose 5:ref *:skip")
_rq2 = json.loads(_P.parsed("RFQ01.json").read_text(encoding="utf-8"))
show("B146 ⓒ ⓓ 같은 문서를 다시 넣으면 추출 체크포인트 재사용(문서 해시 = 구조 블록 밖) · 사람이 확정한 시트는 구조 블록에 출처 「확정」 · "
     "확정 기록 파일은 그대로",
     "체크포인트 재사용" in _x7.stdout and _IDS6.doc_hash(_rq2) == _IDS6.doc_hash({k: v for k, v in _rq2.items() if k != "structure"})
     and _rq2["structure"]["units"][0]["by"] == "확정" and ST.confirmed_path().read_bytes() == _cf0,
     f"rc {_x7.returncode} · 첫 단위 {_rq2['structure']['units'][0]['by']} · "
     + next((ln.strip() for ln in _x7.stdout.splitlines() if "체크포인트" in ln), (_x7.stdout + _x7.stderr)[-160:]))
ST.confirmed_path().unlink(missing_ok=True)

# ────────────────────────────────────────────────────────────── ⓕ 고침 · 재생
print("\n■ ⓕ 고침 · 재생")
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()
struct_map.invalidate(DID)
_r1, _e1, _c1 = _parse()                               # 덱 구조 1회(보존)
_got = STS.parse_deck_fix("4 공정 스태킹", (_r1.report.get("deck") or {}).get("표") or [], STS.deck_text_of(_e1))
DK.record_fix(DID, *_got)
_r2, _e2, _c2b = _parse()                              # 다시 파싱 — 보존분 위에 고침(LLM 0)
_s4b = next(c for c in _e2["chunks"] if c["source_locator"] == "슬라이드 4")
show("ⓕ 구조 표의 공정 고침 → 기록(@덱) → 다시 파싱이 그대로(덱 구조 LLM 0 · 재구축도 같은 기록)",
     _got == (4, {"processes": ["스태킹"]}) and "deck" not in _c2b and _s4b["process_ref"] == "스태킹"
     and (_r2.report["deck"]["수"]["고침"] == 1) and "@덱" in json.loads(ST.fixes_path().read_text(encoding="utf-8"))[DID],
     f"고침 {_got} · 다시 파싱 호출 {_c2b} · 슬라이드 4 공정 {_s4b['process_ref']}")

# ────────────────────────────────────────────────────────────── B143 ⓒ 추출 입력은 JSON + 캡처만
print("\n■ B143 ⓒ 추출 입력 — 덱 블록 고침이 맥락 줄로 · 원본은 캡처에서만")
from core.build import extract_ctx as XC                 # noqa: E402
_d4 = next((x for x in (_e2.get("deck") or {}).get("slides") or [] if 4 in x.values()), {})
_line4 = XC.context_line(_s4b, XC.doc_info(_e2))
_opened, _rendered = [], []
import builtins as _bi                                    # noqa: E402
_open0 = _bi.open
_bi.open = lambda f, *a, **k: (_opened.append(str(f)), _open0(f, *a, **k))[1]
render.capture_path = lambda path=None, probe=False: (True, "시험", None)
render.render_pages = lambda path: (_rendered.append(str(path)), {n: b"PNG" for n in range(1, 6)})[1]
EU._PAGES.clear()
EX.invalidate(DID)
try:
    _run(_e2)
finally:
    _bi.open = _open0
    render.capture_path, render.render_pages = _keep
show("B143 ⓒ 덱 블록의 공정 고침(사람)이 추출 입력 맥락 줄을 따른다 · 원본 파일은 캡처 렌더에서만 열린다(추출은 봉투 + 캡처)",
     ["스태킹"] in _d4.values() and any(isinstance(v, list) and "processes" in v for v in _d4.values())
     and "공정: 스태킹" in _line4
     and "개요: " + DECK["overview"] in _line4 and _rendered == [str(PATH)] and str(PATH) not in _opened,
     f"맥락 줄 {_line4[:80]} · 렌더 {len(_rendered)} · 원본 열기 {sum(1 for x in _opened if x == str(PATH))}")

# ────────────────────────────────────────────────────────────── B151 덱 중립화
print("\n■ B151 — 덱 판단은 층 · 골격 · 문서 좌표를 모른다 · 공정은 문서 표기 · 공정 걸기는 표와 같은 길")
from pptx import Presentation                            # noqa: E402
from pptx.util import Inches                             # noqa: E402
from cli import parse as CP                              # noqa: E402
from core.build import extract_ctx as XC151             # noqa: E402
from g65_common import _rw                               # noqa: E402
SEEN151 = []


class _Live151(Live):
    """덱 호출의 입력 실물(지시문 + 사용자 글 — 메시지 전부)을 그대로 모은다."""

    def chat(self, messages, json_schema=None, point=None, **kw):
        if point == "deck":
            SEEN151.append([dict(m) for m in messages])
        return super().chat(messages, json_schema=json_schema, point=point, **kw)


def _deck151(path, slides):
    """창작 덱 — 슬라이드마다 글 상자들(첫 상자가 제목 자리)."""
    prs = Presentation()
    for boxes in slides:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        for i, text in enumerate(boxes):
            s.shapes.add_textbox(Inches(0.5), Inches(0.3 + i * 1.2), Inches(8), Inches(0.5)).text_frame.text = text
    _P.ensure(path)
    prs.save(path)
    return path


D151 = [["B151 점검 보고"], ["노칭 커터 점검", "커터 마모 0.03mm"], ["스태킹 매거진 점검", "매거진 정렬 0.1mm"],
        ["스태킹 매거진 점검 (계속)", "정렬 핀 교체"], ["스태킹 공정 정렬 기준", "정렬 기준 0.2mm"],
        ["스태킹 공정 정렬 기준 (계속)", "기준 갱신 3월"], ["노칭 · 스태킹 공정 연동", "커터와 매거진을 함께 본다"], ["일정", "3월 착수"]]
A151 = {"slides": [
    {"slide": 1, "title": "B151 점검 보고", "section": None, "continues": None, "subject": None, "processes": [],
     "no_entities": True},
    {"slide": 2, "title": "노칭 커터 점검", "section": None, "continues": None, "subject": "노칭 커터 · 없는 말",
     "processes": ["노칭", "없는공정"], "no_entities": False},
    {"slide": 3, "title": "스태킹 매거진 점검", "section": None, "continues": None, "subject": "스태킹 매거진",
     "processes": ["스태킹"], "no_entities": False},
    {"slide": 4, "title": "스태킹 매거진 점검 (계속)", "section": None, "continues": 3, "subject": None, "processes": [],
     "no_entities": False},
    {"slide": 5, "title": "스태킹 공정 정렬 기준", "section": None, "continues": None, "subject": "정렬 기준",
     "processes": ["스태킹 공정"], "no_entities": False},
    {"slide": 6, "title": "스태킹 공정 정렬 기준 (계속)", "section": None, "continues": 5, "subject": None, "processes": [],
     "no_entities": False},
    {"slide": 7, "title": "노칭 · 스태킹 공정 연동", "section": None, "continues": None, "subject": "커터 · 매거진",
     "processes": ["노칭", "스태킹 공정"], "no_entities": False},
    {"slide": 8, "title": "일정", "section": None, "continues": None, "subject": "일정", "processes": [], "no_entities": False}],
    "overview": "노칭 · 스태킹 점검 보고서다."}
P151 = _deck151(TMP / "B151D.pptx", D151)


def _p151(doc_id, path, answer, pick=None, coord="노칭", keep=False):
    if not keep:                                         # 보존분(덱 판단은 구조 지도 보존분에 산다)을 지우고 처음부터
        struct_map.invalidate(doc_id)
    del SEEN151[:]
    with _Live151(by={"deck": lambda b: answer, "extract": lambda b: {"entities": [], "relations": [], "about": []},
                      "outline": lambda b: {"headings": []}, "reinforce": lambda b: {"pick": None}}):
        res = pipeline.parse(PX, doc_id, str(path), closed_list=TG.closed_list("process"), layer="process", deck=DK.decker(),
                             structure_fixes=ST.fixes_of(doc_id), doc_coord=coord, pick_coord=pick)
        calls = [p_ for p_, _b in CALLS]
    env = res.envelope
    env["doc_type"] = DT
    for c in env["chunks"]:
        c["doc_type"] = DT
    return res, env, calls, [list(m) for m in SEEN151]


def _judged(env):
    return [{k: s.get(k) for k in ("slide", "title", "section", "continues", "subject", "processes", "no_entities")}
            for s in (env.get("deck") or {}).get("slides") or []]


def _sl(env, n):
    return next(c for c in env["chunks"] if c["source_locator"] == f"슬라이드 {n}")


with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()
_ra, _ea, _ca, _ma = _p151("B151D", P151, A151)
_rw(_P.layers("process", "config.json"), lambda c: c.setdefault("prompts", {}).__setitem__("structure", "층 힌트 B151 — 매거진은 설비다"))
_rc151, _eb, _cb, _mb = _p151("B151D", P151, A151, keep=True)   # 같은 상태 · 층 config만 바뀜 — 보존분 재사용
_sk = _P.layers("process", "skeleton.json")
_rw(_sk, lambda s: s["ALIASES"].setdefault("스태킹", []).append("스태킹 B151"))   # 골격 판이 바뀐다
with _quiet():
    RUN.cmd_bootstrap([])                                # 별칭을 골격에(fresh 없이) — 덱 판단 보존분은 아래가 지운다
_r2b, _e2b, _c2b2, _m2b = _p151("B151D", P151, A151, coord="조립")   # 층 힌트 · 골격 판 · 문서 좌표가 다른 상태에서 다시 묻는다
_sys = [m[0]["content"] for m in _ma + _m2b]
_usr = [json.loads(m[1]["content"]) for m in _ma + _m2b]
from tools import layer_words as _LW151                  # noqa: E402
_lw = [v for v in _LW151.scan(ROOT) if "2.4_deck" in str(v)] if hasattr(_LW151, "scan") else []
show("B151 ⓐ 층 config(층 힌트) · 골격 판 · 문서 좌표를 바꾼 두 상태에서 같은 덱 — 덱 블록의 판단 칸이 같다 · 덱 호출 입력(실물)에 층 힌트 · 골격 "
     "이름 목록 · 문서 좌표 0(두 상태의 입력이 글자까지 같다) · 덱 지시문 층 어휘 0 · 추출 지시문 판 그대로(e-2.0)",
     _ma and _m2b and _judged(_ea) == _judged(_e2b) and _ma == _m2b
     and all(set(u) == {"deck", "previous", "slides"} for u in _usr)
     and not any(x in s for s in _sys for x in ("층 힌트 B151", "## 층 어휘", "탭용접", "패키징"))
     and not _lw and EX.prompt_version() == "e-2.0",
     f"호출 {len(_ma)} · {len(_m2b)} · 같은 입력 {_ma == _m2b} · 판단 같음 {_judged(_ea) == _judged(_e2b)} · 입력 열쇠 "
     f"{sorted(_usr[0]) if _usr else None} · 추출 판 {EX.prompt_version()}")
show("B151 ⓑ 층 config를 바꾼 뒤 같은 덱 재파싱 → 덱 판단 보존분 재사용(LLM 0)",
     "deck" not in _cb and (_rc151.report["deck"]["수"]["재사용"] == 1) and _judged(_eb) == _judged(_ea),
     f"호출 {_cb} · 재사용 {_rc151.report['deck']['수'].get('재사용')}")
_s2 = next(s for s in _ea["deck"]["slides"] if s["slide"] == 2)
show("B151 ⓒ 다루는 것 · 공정 검사 — 슬라이드 글에 없는 명사구 · 덱 글에 없는 공정 표기는 버려지고 dropped에 · 있는 것은 덱 블록 · "
     "청크 meta · 맥락 줄(「다루는 것」 칸)에",
     _s2["subject"] == "노칭 커터" and _s2["processes"] == ["노칭"] and {"다루는 것", "공정"} <= set(_s2["dropped"])
     and _sl(_ea, 2)["meta"].get("subject") == "노칭 커터" and "다루는 것: 노칭 커터" in XC151.context_line(_sl(_ea, 2))
     and _sl(_ea, 4)["meta"].get("subject") == "스태킹 매거진",
     f"슬라이드 2 {_s2} · 맥락 줄 {XC151.context_line(_sl(_ea, 2))[:120]}")
#: 표 · 차트 머리도 덱 글이다 — 덱 입력이 준 머리에만 있는 공정 표기 · 다루는 것은 남는다(제목 검사만 머리를 뺀다)
_hd = DK.check("B151H", [{"slide": 1, "layout": "", "boxes": [{"kind": "title", "text": "검사 결과"},
                                                              {"kind": "table", "text": "스태킹 공정 | 정렬 | 판정"}]}],
               {"slides": [{"slide": 1, "title": "검사 결과", "subject": "정렬", "processes": ["스태킹"]}]})["slides"][1]
show("B151 ⓒ 표 머리의 공정 표기 · 다루는 것 — 덱 입력이 준 표 머리에만 있어도 검사를 지난다",
     _hd.get("processes") == ["스태킹"] and _hd.get("subject") == "정렬" and not _hd.get("dropped"), _hd)
# ⓓ 공정 걸기 — mock(⑨ 없음) 그래프 단계 · ⑨ 주입(시험 pick)
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()
_rd, _ed, _cd, _md = _p151("B151D", P151, A151)
_n151, _cr151 = _run(_ed)
_q151 = [q for q in store.read(store.QUEUE, []) if q.get("doc_id") == "B151D"]
_mis = {(q.get("payload") or {}).get("provenance", "").split("#")[-1] for q in _q151 if q.get("kind") == "coord_mismatch"}
_orp = [q for q in _q151 if q.get("kind") == "orphan_anchor"]
_ASK = []
_rp, _ep, _cp, _mp = _p151("B151P", P151, A151, pick=lambda ref, cands: (_ASK.append(ref), "스태킹" if ref == "스태킹 공정" else None)[1])
_s7 = _sl(_ep, 7)
show("B151 ⓓ 공정 걸기(문서 좌표 「노칭」) — 슬라이드 4는 3을 이어 「스태킹」 · 태깅에서 골격에 맞음 · 문서 좌표 밖이라 coord_mismatch에 "
     "그 슬라이드들 · 골격 · 별칭에 없는 「스태킹 공정」은 ⑨ 없는 mock에서 그대로 → orphan_anchor 큐 · ⑨ 주입이면 같은 표기를 한 번 묻고 "
     "채택은 canonical + 원 표기 meta(목록 조각은 원소마다) · 공정 빈 슬라이드는 문서 좌표를 물려받는다",
     _sl(_ed, 3)["process_ref"] == "스태킹" and _sl(_ed, 4)["process_ref"] == "스태킹"
     and {"슬라이드 3", "슬라이드 4"} <= _mis and _sl(_ed, 5)["process_ref"] == "스태킹 공정"
     and any("스태킹 공정" in json.dumps(q, ensure_ascii=False) for q in _orp)
     and _ASK == ["스태킹 공정"] and _sl(_ep, 5)["process_ref"] == "스태킹" and _sl(_ep, 6)["process_ref"] == "스태킹"
     and (_sl(_ep, 5)["meta"].get("coord_tag_source"), _sl(_ep, 5)["meta"].get("coord_tag_from")) == ("live", "스태킹 공정")
     and _s7["process_ref"] == ["노칭", "스태킹"]
     and [(x["from"], x.get("source")) for x in _s7["meta"].get("coord_tags") or []] == [("노칭", None), ("스태킹 공정", "live")]
     and not PDK.mismatch(_ep) and _sl(_ed, 8)["process_ref"] == "노칭" and _sl(_ed, 8)["meta"].get("coord_from_doc"),
     f"3·4 {_sl(_ed, 3)['process_ref']} · {_sl(_ed, 4)['process_ref']} · 어긋남 {sorted(_mis)} · 고아 {len(_orp)} · 물음 {_ASK} · "
     f"7 {_s7['process_ref']} {_s7['meta'].get('coord_tags')} · 8 {_sl(_ed, 8)['process_ref']}")
# B154 ① 좌표 쌍 다음 줄 — 상위의 출처로(ⓓ의 덱 = 문서 좌표 상위 · 행 상위가 어긋난 표 조각 = 행)
from cli import coord_queue as CQU154, doc_coord as DC154   # noqa: E402
_ps154, _qs154, _ts154 = io.StringIO(), io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(_ps154):
    DC154.pair_screen(_ed)
with contextlib.redirect_stdout(_qs154):
    CQU154.show()
with contextlib.redirect_stdout(_ts154):
    DC154.pair_screen({"doc_id": "B154T", "doc_type": "cp", "source_path": "B154T.xlsx",
                       "records": [{"source_locator": "CP!R4", "process_group": "스태킹", "process_ref": "노칭"}]})
_nx = lambda b: [ln.strip() for ln in b.getvalue().splitlines() if ln.strip().startswith("▶ 다음 줄(")]   # noqa: E731
show("B154 ⓐ 좌표 쌍 다음 줄 — 덱(문서 좌표 상위)은 문서 좌표 줄 · 열 매핑 0 · 파싱 화면과 큐 화면이 같은 줄 · 행 상위가 어긋난 표 "
     "조각은 열 매핑 줄",
     _nx(_ps154) and _nx(_ps154) == _nx(_qs154) and all("문서 좌표 상위" in x and "열 매핑" not in x for x in _nx(_ps154))
     and "--coord <상위 공정>" in _nx(_ps154)[0] and _nx(_ts154) and all("열 매핑을 바로잡는다" in x for x in _nx(_ts154)),
     f"파싱 {_nx(_ps154)[:1]} · 큐 {len(_nx(_qs154))}줄 · 표 {[x[:40] for x in _nx(_ts154)]}")
from cli import report_cause as RC154                      # noqa: E402
_h154 = RC154.head_count(RC154.material("B151D"))[:2]
store.append_defect("B151D: 관계 후보 끝점 미해소 — '브래킷' -part_of-> '노칭' @ B151D:b154")   # 관계 끝점 표본(결함 로그의 꼴 그대로)
_l154 = [ln.strip() for ln in RC154.report("B151D")[0]]
show("B154 ⓑ 행 밖 — 값은 다 붙었고(못 붙은 행 0) 골격에 없는 공정 표기 「스태킹 공정」 · 끝점 없는 관계가 원인 묶음 아래 「행 밖」에 · "
     "머리 수 그대로(행 밖은 합에 없다)",
     _h154[0] == 0 and f"원인 묶음 — 못 붙은 행 0 / 전체 {_h154[1]}" in _l154
     and any(x.startswith("공정 표기 — 골격에 없음 '스태킹 공정' · 조각 ") for x in _l154)
     and "관계 — 끝점 없음 '브래킷' · 못 선 관계 1 · B151D:b154" in _l154
     and RC154.head_count(RC154.material("B151D"))[:2] == _h154,
     f"머리 {_h154} · {[x for x in _l154 if '—' in x][:4]}")
# B155 ⓒ 추출까지만 — 덱(B151 덱 표본) · 추출 md(맥락 줄 · 원문 · 개체 표 · 판정 예고 · 한눈에)
def _x155(body):
    t = body["chunk"]
    if "커터 마모" in t:                                  # 사전 일치 · 판정에 오름(글에 없음) · 값 글자 버림
        return {"entities": [_ent("노칭", "Process"), _ent("커터 홀더", "Unit"), _ent("마모량", "Property", value="0.09mm")],
                "relations": [], "about": []}
    if "정렬 기준 0.2mm" in t:                            # 좌표 「스태킹 공정」은 골격 밖 — 보류 예상
        return {"entities": [_ent("정렬 지그", "Unit")], "relations": [], "about": []}
    return {"entities": [], "relations": [], "about": []}   # 일정 슬라이드 — 부른 단위인데 개체 0


_r155, _e155, _c155, _m155 = _p151("B155D", P151, A151)
_P.ensure(_P.parsed("B155D.json"))
_P.parsed("B155D.json").write_text(json.dumps(_e155, ensure_ascii=False), encoding="utf-8")   # 파싱이 남기는 봉투 자리
_g155 = json.dumps(store.read(store.DOC_REGISTRY, {}), sort_keys=True)
with Live(by={"extract": _x155, "outline": lambda b: {"headings": []}}), _quiet():
    _rx155 = run_document(dict(_e155), extract_only=True)
from cli import extract_md as XMD155                    # noqa: E402
_md155 = XMD155.text("B155D") or ""
show("B155 ⓒ 덱 추출까지만 — md에 슬라이드마다 맥락 줄(다루는 것) · 원문 · 개체 표(글에서 찾은 자리 · 「글에 없음」) · 판정 예고(사전 일치 · "
     "판정에 오름 · 보류 예상 · 검사 버림) · 한눈에 ⚠ · 문서 대장 0",
     getattr(_rx155[0], "extract_stop", False) and "다루는 것: 노칭 커터" in _md155 and "커터 마모 0.03mm" in _md155
     and "| 커터 홀더 | Unit |" in _md155 and "글에 없음" in _md155 and "| 노칭 | Process |" in _md155
     and all(x in _md155 for x in ("사전 일치", "판정에 오름", "보류 예상", "검사 버림(값 글자)", "⚠ 부른 단위인데 개체 0"))
     and json.dumps(store.read(store.DOC_REGISTRY, {}), sort_keys=True) == _g155,
     f"{_rx155[0].reason} · " + " | ".join(ln for ln in _md155.splitlines() if ln.startswith("- 사전 일치")))
# ⓔ 공정이 없는 덱
D151E = [["투자 계획"], ["예산 3억", "3월 집행"], ["일정", "4월 착수"]]
A151E = {"slides": [{"slide": 1, "title": "투자 계획", "section": None, "continues": None, "subject": None, "processes": [],
                     "no_entities": True},
                    {"slide": 2, "title": "예산 3억", "section": None, "continues": None, "subject": "예산", "processes": [],
                     "no_entities": False},
                    {"slide": 3, "title": "일정", "section": None, "continues": None, "subject": "일정", "processes": [],
                     "no_entities": False}], "overview": "투자 계획서다."}
_re, _ee, _ce, _me = _p151("B151E", _deck151(TMP / "B151E.pptx", D151E), A151E, coord=None)
_ne, _cre = _run(_ee)
_qe = [q for q in store.read(store.QUEUE, []) if q.get("doc_id") == "B151E"]
show("B151 ⓔ 공정이 없는 덱 — 모든 슬라이드 공정 빈 목록 · 다루는 것은 채워진다 · 파싱 · 구축 오류 0 · 큐 0",
     _re.ok and all(s["processes"] == [] for s in _ee["deck"]["slides"])
     and [s["subject"] for s in _ee["deck"]["slides"]] == [None, "예산", "일정"]
     and not any(c.get("process_ref") for c in _ee["chunks"]) and not _qe and not PDK.mismatch(_ee),
     f"공정 {[s['processes'] for s in _ee['deck']['slides']]} · 다루는 것 {[s['subject'] for s in _ee['deck']['slides']]} · 큐 {len(_qe)}")
# ⓕ 옛 @덱 고침(공정 · 언급 칸 포함)
DK.record_fix("B151D", 3, {"title": "스태킹 매거진 점검", "processes": ["노칭"], "mentions": ["탭용접"]})
_rf, _ef, _cf, _mf = _p151("B151D", P151, A151, keep=True)
_buf151 = io.StringIO()
with contextlib.redirect_stdout(_buf151):
    CP.print_split_notes(_rf.report)
_s3f = next(s for s in _ef["deck"]["slides"] if s["slide"] == 3)
show("B151 ⓕ 옛 @덱 고침(공정 · 언급 칸 포함) — 제목 · 공정은 고침대로 · 언급 칸은 읽지 않고 화면에 한 줄",
     _s3f["title"] == "스태킹 매거진 점검" and _s3f["processes"] == ["노칭"] and "mentions" not in _s3f
     and "읽지 않은 옛 언급 고침 1" in _buf151.getvalue() and "deck" not in _cf,
     f"슬라이드 3 {_s3f.get('title')} · {_s3f.get('processes')} · 줄 "
     f"{[ln.strip() for ln in _buf151.getvalue().splitlines() if '옛 언급' in ln]}")
ST.fixes_path().unlink(missing_ok=True)

dts = store.read(store.DOC_TYPES, {})
dts.pop(DT, None)
store.write(store.DOC_TYPES, dts)
done()
