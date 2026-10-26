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
DECK = {"slides": [
    {"slide": 1, "title": "노칭 · 스태킹 점검 보고", "section": None, "continues": None, "processes": ["없는공정"],
     "mentions": [], "no_entities": True},
    {"slide": 2, "title": "노칭 금형 점검 결과", "section": None, "continues": None, "processes": ["노칭"], "mentions": [],
     "no_entities": False},
    {"slide": 3, "title": "노칭 금형 점검 결과 (계속)", "section": None, "continues": 2, "processes": [], "mentions": [],
     "no_entities": False},
    {"slide": 4, "title": "커터 사양", "section": None, "continues": None, "processes": ["노칭"], "mentions": [],
     "no_entities": False},
    {"slide": 5, "title": "노칭 · 스태킹 연동 점검", "section": None, "continues": None, "processes": ["노칭", "스태킹"],
     "mentions": ["탭용접"], "no_entities": False}],
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
        ents = [_ent("커터", "Unit", parent="노칭"), _ent("매거진", "Unit", parent="스태킹")]
    return {"entities": ents, "relations": [], "about": []}


def _live():
    return Live(by={"deck": lambda b: DECK, "extract": _extract, "outline": lambda b: {"headings": []},
                    "reinforce": lambda b: {"pick": None}})


def _parse(**kw):
    with _live():
        res = pipeline.parse(PX, DID, str(PATH), closed_list=TG.closed_list("process"), layer="process",
                             deck=DK.decker(["process"]), capture=True, structure_fixes=ST.fixes_of(DID),
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
show("B143 ⓑ 봉투 하나에 슬라이드마다 이어짐 · 제목 초안과 판단 · 공정 목록 · 언급 · 개체 없음 · 버림 · 근거 위치 · 청크 칸과 어긋나지 "
     "않는다(어긋나게 바꾸면 결함으로 잡힌다) · 개요도 블록에(옛 doc_overview 0)",
     len(_blk) == 5 and not PDK.mismatch(ENV) and _bad and "doc_overview" not in ENV
     and 2 in _vals[3] and ["노칭", "스태킹"] in _vals[5] and ["탭용접"] in _vals[5] and ["공정"] in _vals[1]
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
                     structure=ST.structurer(["process"])).envelope
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
_got = STS.parse_deck_fix("4 공정 스태킹", (_r1.report.get("deck") or {}).get("표") or [])
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

dts = store.read(store.DOC_TYPES, {})
dts.pop(DT, None)
store.write(store.DOC_TYPES, dts)
done()
