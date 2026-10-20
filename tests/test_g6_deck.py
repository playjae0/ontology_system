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
_hint = ROOT / "tests" / "fixtures" / "extract_hints" / f"{DID}@deck.json"
_hint.write_text(json.dumps(DECK, ensure_ascii=False), encoding="utf-8")
with _quiet():
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
_register()
_p = subprocess.run([sys.executable, "run.py", "ingest-dir", str(_dir), "--doc-type", DT, "--allow-mock"], cwd=str(ROOT),
                    capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**_iso.isolated_env(), "USE_MOCK": "1"},
                    timeout=600)
_hint.unlink(missing_ok=True)
show("ⓔ 노칭 · 스태킹 슬라이드의 개체가 각자 제 공정 아래 · 언급만 한 탭용접은 노드 0 + 관련 링크 · --coord 없이 ingest-dir 성공",
     {"노칭::커터", "스태킹::매거진"} <= _names and not any(x.endswith("::탭용접") for x in _names if x)
     and {"chunk_id": _s5, "node_id": _tab} in (_ch.get("about") or [])
     and _p.returncode == 0 and "덱 구조 — 슬라이드 5" in _p.stdout,
     f"노드 {sorted(x for x in _names if x and ('커터' in x or '매거진' in x))} · ingest-dir rc {_p.returncode} · "
     + (_p.stdout + _p.stderr).strip().splitlines()[-1][:120])

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

dts = store.read(store.DOC_TYPES, {})
dts.pop(DT, None)
store.write(store.DOC_TYPES, dts)
done()
