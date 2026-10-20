# -*- coding: utf-8 -*-
"""G6 — **계층 사다리** — 코드는 재료(행 전체 · 들여쓰기 깊이 · 꼴 서명 · 서수)와 적용 · 검사 · LLM은 사다리(문서당 1)와 시트 확인(시트당 1) (B132).

창작 표본(시트 둘 · 수치는 근거가 아니다 [정정] 50) — 한 시트에 사내 세 경우를 섞는다: 번호+글(띄어쓰기 섞임) · 단계마다 다른 열 ·
앞 공백. 사다리 · 시트 확인 답은 가짜 게이트웨이(실호출 갈래 — 입력 조립 · 검사 · 적용은 실물). LLM 판단의 품질은 사내
`--split-only`에서 잰다. 완료판정 하나에 대표 어서션 하나:
  ⓐ 재료 — 시작 열 · 들여쓰기 깊이 · 서명 · 서수 · 빈 행 뒤 · 다른 열의 제목이 줄에 · 한 열 시트는 줄이 셀 글 그대로
  ⓑ 서명 — 여섯 예가 정해 둔 꼴 목록 없이 · 두 벌 패턴 0
  ⓒ 사다리 — `9. › 가.(대상 · Unit) › 9) › A.`로 목차 · 단의 역할이 줄에 · 사다리 호출 문서당 1 · 입력에 줄 전문 0
  ⓓ 판단 필요 — 넷이 하나씩 표시 · 시트 확인 입력에 이유와 앞뒤 두 줄 · 답으로 바뀐다 · 코드가 혼자 정한 애매한 줄 0
  ⓔ 시트 확인 — 시트당 1 · 골격 보기(본문 접음 · 줄 전문 0) · 「대개 맞다」 0 · 사다리 고침이 둘째 시트에도
  ⓕ 폴백 — 사다리 호출 실패 · mock 힌트 없음이면 코드 사다리(`rules`와 같은 목차)
  ⓖ 화면 — 사다리 한 줄 · 들여쓰기 목차 · 판단 필요와 답 · 경로 (md 같게)
  ⓗ 방식 — `structure_mode` 값 둘 · 옛 값은 문면으로 멈춘다 · 읽는 곳 0이 된 경로 0
(B124 「구조 v2」 조각 — LLM 청크 구간 · 구간 검사 · 폴백은 경로를 지워(B132 ⑧) 이 조각으로 바꿨다 · ⓘ는 test_site · ⓙ는 네 벌 단계)
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done   # noqa: F401

from fake_gateway import CALLS, Live                     # noqa: E402
from g6_common import _run                               # noqa: E402
from openpyxl import Workbook                            # noqa: E402
import run as RUN                                        # noqa: E402
from cli import _screen, split_report, structure_screen as SS   # noqa: E402
from core.build import structure as ST, structure_edit as SE   # noqa: E402
from core.llm import gateway                             # noqa: E402
from core.state import knobs as KN                       # noqa: E402
from parser import pipeline, sig as SG, struct_map, struct_rule as SR, tuning   # noqa: E402
from parser.reader import read                           # noqa: E402
from parser.adapters import basic_prose_xlsx as BX       # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="b132_"))
DID, S1, S2 = "B132L", "공정별 상세사양", "검사 사양"
LONG = "다.패키징 unit — 파우치 포밍 · 스택 삽입 · 사이드 실링 · 전해액 주액"
#: `(행, 열, 글)` — 단계마다 다른 열(A 번호 · B 소제목 · C 본문) · 번호 뒤 띄어쓰기 섞임 · 앞 공백 · 판단 필요 넷(ⓑ 8행 · ⓐ 10행 ·
#: ⓒ 17행 · ⓓ 20행)
ROWS = {S1: [(1, "A", "6.공정별 상세사양"), (2, "A", "가."), (2, "B", "노칭 unit"), (3, "B", "1)기본사양"),
             (4, "C", "속도는 60ppm이다."), (5, "B", "2)지정사양"), (6, "B", "   A.입고전 검수"), (7, "C", "외관을 본다."),
             (8, "A", "B.입고후 검수"), (9, "C", "치수를 잰다."), (10, "A", "■ 참고"), (11, "C", "참고 본문이다."),
             (12, "A", "나.스태킹 unit"), (13, "B", "1) 기본사양"), (14, "C", "장력은 30N이다."), (15, "B", "2) 지정사양"),
             (16, "C", "폭은 20mm다."), (17, "B", "4) 검수방법"), (18, "C", "검수 본문이다."), (20, "C", "비고"),
             (21, "C", "비고 본문이다."), (22, "A", LONG), (23, "C", "패키징 본문이다.")],
        S2: [(1, "A", "7.검사 사양"), (2, "A", "가.검사 unit"), (3, "B", "1)주기"), (4, "C", "주기는 매일이다."),
             (5, "A", "■ 참고"), (6, "C", "둘째 참고 본문이다.")]}
FOLDED = "속도는 60ppm이다."                                 # 어느 판단 필요의 앞뒤도 아닌 본문 줄 — 구조 입력에 없어야 한다
_N = lambda why: {"rows": [], "why": why}
LADDER = {"levels": [{"sigs": ["9."], "role": "주제", "category": None, **_N("문서 장")},
                     {"sigs": ["가."], "role": "대상", "category": "Unit", **_N("유닛 단")},
                     {"sigs": ["9)"], "role": None, "category": None, **_N("소제목")},
                     {"sigs": ["A."], "role": None, "category": None, **_N("세목")}], "unnumbered": []}
RULE = {"shape": "9)", "role": "묶음", "category": None, "parent_shape": None, "said": "'9)' 줄은 사양 묶음"}
ANSWER = {8: {"heading": True, "parent": 5, "why": "들여쓰기만 얕다 — A.의 형제"}, 10: {"heading": False, "why": "참고는 본문"},
          17: {"heading": True, "parent": 12, "why": "3)이 빠진 발췌"}, 20: {"heading": True, "parent": None, "role": "주제",
                                                                       "why": "빈 행 뒤 비고는 주제"},
          5: {"heading": False, "why": "참고는 본문"}}


def _xlsx():
    wb = Workbook()
    wb.remove(wb.active)
    for name, cells in ROWS.items():
        ws = wb.create_sheet(title=name)
        for r, c, v in cells:
            ws[f"{c}{r}"] = v
    p = TMP / f"{DID}.xlsx"
    wb.save(p)
    return p


def _llm(body):
    """가짜 ⑪ — 사다리는 표본의 답 · 시트 확인은 판단 필요마다 답(빠짐없이) + 첫 시트에서 사다리 고침 한 줄."""
    if body.get("task") == "ladder":
        return LADDER
    ans = [{"row": n["row"], "parent": None, "role": None, "name": None, "category": None, **ANSWER[n["row"]]}
           for n in body.get("needs") or []]
    return {"answers": ans, "edits": [], "rules": [RULE] if body["frame"] == S1 else []}


def _parse(p, confirmed=None):
    return pipeline.parse(BX, DID, str(p), closed_list=[], sheet_roles={S1: "prose", S2: "prose"},
                          structure=ST.structurer(["process"]), structure_confirmed=confirmed)


def _tree(res, frame):
    return [(h["row"], h.get("parent")) for h in res.report["structure"]["프레임"][frame]["headings"]]


with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
ST.confirmed_path().unlink(missing_ok=True)
_x = _xlsx()

# ────────────────────────────────────────────────────────────── ⓐ 재료 · ⓑ 서명
print("\n■ ⓐ 재료 · ⓑ 꼴 서명")
_sh = next(s for s in read(str(_x))["sheets"] if s["name"] == S1)
_l, _rw, _m = BX._rows_of(_sh)
_lab = {x["row"]: x for x in SR.labels(S1, _l, _rw, BX._marks(_m), True, _m)}
_toc = next(s for s in read(str(ROOT / "tests" / "fixtures" / "raw" / "TOC01.xlsx"))["sheets"])
_col = BX._content_column(_toc)
_one = [(int(a[len(_col):]), str(v).strip()) for a, v in (_toc.get("cells") or {}).items()
        if a.startswith(_col) and a[len(_col):].isdigit() and str(v).strip()]
show("ⓐ 재료 — 시작 열 · 들여쓰기 깊이(열 · 앞 공백) · 서명 · 서수 · 빈 행 뒤 · 다른 열의 제목이 줄에(「가. | 노칭 unit」) · "
     "한 열 시트는 줄이 셀 글 그대로",
     [(_lab[r]["col"], _lab[r]["depth"]) for r in (1, 3, 6, 4)] == [("A", 0), ("B", 1), ("B", 2), ("C", 3)]
     and (_lab[3]["sig"], _lab[3]["ord"], _lab[8]["sig"], _lab[8]["ord"]) == ("9)", 1, "A.", 2)
     and _lab[20]["gap"] and not _lab[21]["gap"] and _lab[2]["text"] == "가. | 노칭 unit"
     and sorted(BX._rows_of(_toc)[0]) == sorted(_one),
     f"{[(r, _lab[r]['col'], _lab[r]['depth'], _lab[r]['sig']) for r in (1, 2, 3, 6, 8, 20)]}")
_six = {"1.기본사양": ("9.", 1), "(가) 범위": ("(가)", 1), "4)검수방법": ("9)", 4), "1-1 공급부": ("9-9", 1),
        "■ 개요": ("■", None), "b. 지정": ("a.", 2), "1. 기본사양": ("9.", 1)}
show("ⓑ 서명 — 여섯 예(띄어쓰기 · 길이와 무관)가 서명 · 서수로 선다 · 번호 패턴 두 벌(`HEADING_FAMILIES` · `NUMBER_SHAPES`) 0",
     all(SG.signature(t) == v for t, v in _six.items()) and SG.signature("1.기본사양 " + "가" * 80) == ("9.", 1)
     and not any(hasattr(struct_map, n) for n in ("HEADING_FAMILIES", "NUMBER_SHAPES", "heading_family")),
     str({t: SG.signature(t) for t in _six}))

# ────────────────────────────────────────────────────────────── ⓒ 사다리 · ⓓ 판단 필요 · ⓔ 시트 확인
print("\n■ ⓒ 계층 사다리 · ⓓ 판단 필요 · ⓔ 시트 확인 (가짜 게이트웨이)")
struct_map.invalidate(DID)
CALLS.clear()
with Live(by={"structure": _llm}):
    _r = _parse(_x)
_st = _r.report["structure"]
_f1, _f2 = _st["프레임"][S1], _st["프레임"][S2]
_lad = [b for p, b in CALLS if p == "structure" and b.get("task") == "ladder"]
_chk = {b["frame"]: b for p, b in CALLS if p == "structure" and b.get("task") == "check"}
_h1 = {h["row"]: h for h in _f1["headings"]}
_want = [(1, None), (2, 1), (3, 2), (5, 2), (6, 5), (8, 5), (12, 1), (13, 12), (15, 12), (17, 12), (20, None), (22, 1)]
_lin = json.dumps(_lad[0], ensure_ascii=False) if _lad else ""
show("ⓒ 사다리 답(`9. › 가.(대상 · Unit) › 9) › A.`)으로 목차가 맞고 단의 역할이 줄에(대상 이름 = 번호를 뗀 글) · 사다리 호출 문서당 1 · "
     "입력에 줄 전문 0(본문 · 긴 제목의 전문 없음)",
     _tree(_r, S1) == _want and (_h1[2]["role"], _h1[2]["name"], _h1[2]["category"]) == ("대상", "노칭 unit", "Unit")
     and _h1[12]["name"] == "스태킹 unit" and _h1[1]["role"] == "주제" and len(_lad) == 1
     and FOLDED not in _lin and LONG not in _lin and "stats" in _lad[0],
     f"목차 {_tree(_r, S1)} · 사다리 호출 {len(_lad)} · 2행 {(_h1[2].get('role'), _h1[2].get('name'))}")
_need = {n["row"]: n["kind"] for n in _f1["needs"]}
_t1 = {e.get("row"): e for e in _chk.get(S1, {}).get("toc") or []}
_toc0 = {h["row"] for h in _f1["toc0"]}
show("ⓓ 판단 필요 넷이 하나씩(ⓑ 8 · ⓐ 10 · ⓒ 17 · ⓓ 20) · 시트 확인 입력에 이유와 앞뒤 두 줄 · 답으로 바뀐다(20행 제목 · 10행 본문) · "
     "코드가 혼자 정한 애매한 줄 0(ⓐ · ⓓ 줄은 코드 목차에 없다 · 답 빠짐 0)",
     _need == {8: "ⓑ", 10: "ⓐ", 17: "ⓒ", 20: "ⓓ"}
     and all(_t1.get(r, {}).get("kind") == "판단 필요" and _t1[r].get("why") for r in _need)
     and _t1.get(9, {}).get("kind") == "앞뒤" and _t1.get(11, {}).get("kind") == "앞뒤" and _t1.get(19) is None
     and 20 in _h1 and _h1[20]["role"] == "주제" and 10 not in _h1 and not ({10, 20} & _toc0)
     and not _f1["missing"] and not _f2["missing"],
     f"판단 필요 {_need} · 입력 {[(r, _t1.get(r, {}).get('kind')) for r in (8, 9, 10, 11, 17, 20)]} · 빠짐 {_f1['missing']}")
_cin = json.dumps(_chk.get(S1) or {}, ensure_ascii=False)
_prompt = (ROOT / "prompts" / "2.4_ladder.md").read_text(encoding="utf-8")
show("ⓔ 시트 확인 — 시트당 1 · 입력은 골격 보기(본문 접음 · 줄 전문 0 · 긴 제목은 앞 40자 + 「…총 n자」) · 시트 확인 지시문에 「대개 맞다」 0 · "
     "사다리 고침(9) → 묶음)이 둘째 시트에도",
     sorted(_chk) == sorted([S1, S2]) and sum(1 for p, b in CALLS if b.get("task") == "check") == 2
     and any(e.get("kind") == "본문" for e in _chk[S1]["toc"]) and FOLDED not in _cin and LONG not in _cin
     and f"…총 {len(LONG)}자" in _cin and "대개 맞다" not in _prompt
     and [h.get("role") for h in _f2["headings"] if h["row"] == 3] == ["묶음"] and _h1[3]["role"] == "묶음",
     f"확인 호출 {sorted(_chk)} · 둘째 시트 3행 역할 {[h.get('role') for h in _f2['headings'] if h['row'] == 3]}")

# ────────────────────────────────────────────────────────────── ⓕ 폴백
print("\n■ ⓕ 폴백 — 코드 사다리")
ST.DOC.pop(DID, None)
ST.MODE = "rules"
struct_map.invalidate(DID)
_rules = _parse(_x)
ST.MODE = "ladder"
struct_map.invalidate(DID)


def _boom(_b):
    raise gateway.GatewayError(500, "가짜 실패", "fake")


with Live(by={"structure": _boom}):
    _fail = _parse(_x)
struct_map.invalidate(DID)
_bare = _parse(_x)                                       # mock · 힌트 없음
show("ⓕ 사다리 호출 실패 · mock 힌트 없음이면 코드 사다리로 목차가 선다(`rules`와 같은 목차) · 구조가 안 서는 일 0",
     all(_tree(x, f) == _tree(_rules, f) and _tree(x, f) for x in (_fail, _bare) for f in (S1, S2))
     and _fail.report["structure"]["사다리"] == "코드(호출 실패)" and _bare.report["structure"]["사다리"] == "코드(힌트 없음)",
     f"사다리 {_fail.report['structure'].get('사다리')} / {_bare.report['structure'].get('사다리')} · 목차 같음 "
     f"{[_tree(x, S1) == _tree(_rules, S1) for x in (_fail, _bare)]}")

# ────────────────────────────────────────────────────────────── ⓖ 화면
print("\n■ ⓖ 구조 확인 화면")
ST.DOC.pop(DID, None)
struct_map.invalidate(DID)
tuning.apply({"chunk_rows": [1, 2]})                     # 작은 표본이 깊은 단까지 잘리게(창작 손잡이 — 근거가 아니다)
_ask0 = _screen.ask
_it = iter(["c", "c"])
_screen.ask = lambda prompt: next(_it)
_buf = io.StringIO()
with Live(by={"structure": _llm}), contextlib.redirect_stdout(_buf):
    _rg, _go = SS.gate(_parse(_x), DID, lambda: _parse(_x), layers=["process"])
_screen.ask = _ask0
tuning.apply({})
_scr = _buf.getvalue()
_ind = {r: next((len(ln) - len(ln.lstrip()) for ln in _scr.splitlines() if ln.lstrip().startswith(f"{r}행 ")), -1) for r in (5, 6)}
_md = split_report.write_md(DID, _rg.report, _rg.envelope).read_text(encoding="utf-8")
LINE = "계층 사다리: 시트 › 9.(주제) › 가.(대상 · Unit) › 9)(묶음) › A."
show("ⓖ 화면 — 사다리 한 줄 · 들여쓰기 목차(A.가 2)보다 한 단 깊다) · 판단 필요와 답 · 청크마다 전체 경로 · md에 같은 줄",
     _go and LINE in _scr and LINE in _md and _ind[6] == _ind[5] + 2 > 2
     and "20행 ⓓ 빈 행 뒤 짧은 번호 없는 줄 · '비고' — 답 — 제목(부모 시트 · 주제)" in _scr
     and f"경로 {S1} › 6.공정별 상세사양 › 가. | 노칭 unit › 2)지정사양 › A.입고전 검수" in _scr
     and "20행 ⓓ 빈 행 뒤 짧은 번호 없는 줄" in _md,
     " / ".join(ln.strip()[:90] for ln in _scr.splitlines() if "계층 사다리" in ln or "20행 ⓓ" in ln)[:300])
ST.confirmed_path().unlink(missing_ok=True)

# ────────────────────────────────────────────────────────────── ⓗ 방식
print("\n■ ⓗ 방식 둘 · 옛 값")
_kn = _P.home() / "knobs.json"
_kn.write_text(json.dumps({"structure_mode": "edit"}), encoding="utf-8")
_out = _run("show", "knobs")
_kn.unlink()
show("ⓗ `structure_mode` 값 둘(rules · ladder) · 옛 값 edit는 명령이 문면으로 멈추고 바꿀 값을 말한다 · 읽는 곳 0이 된 경로 0"
     "(LLM 청크 구간 · 나눠 부르기 · 규칙 나무 입력)",
     KN.KNOBS["structure_mode"][2] == "choice:rules|ladder" and ST.MODES == ("rules", "ladder")
     and '"edit"는 폐기한 값' in _out and '"structure_mode": "ladder"' in _out
     and not any(hasattr(SR, n) for n in ("range_chunks", "check_chunks", "CUT_ROLES"))
     and not any(hasattr(SE, n) for n in ("number_runs", "run_lines", "rules_tree", "ask_edit"))
     and not any(hasattr(ST, n) for n in ("check", "table", "range_lines", "ask_edit")),
     " / ".join(ln.strip() for ln in _out.splitlines() if "폐기" in ln or "다음 줄" in ln)[:200])

# ────────────────────────────────────────────────────────────── ⓚ 개요 · 덱의 판은 구조와 따로
print("\n■ ⓚ 개요 · 덱 — 판이 구조와 따로 · 옛 보존분 재사용")
from core.build import deck as DK                         # noqa: E402
from core.build.extract import prompt_version             # noqa: E402
from parser import deck as PD                             # noqa: E402
_cf = ST._cfgs(["process"])
_k1 = DK.key(_cf)
ST.MODE = "rules"
_k2 = DK.key(_cf)
ST.MODE = "ladder"
_slides = [{"slide": 1, "layout": "제목", "boxes": [{"kind": "text", "text": "노칭 점검"}]}]
_asked = []
_fake = lambda doc_id, slides, doc_coord=None: _asked.append(doc_id) or {"slides": {}, "overview": ""}
_fake.key = lambda: _k1
_old = {"labels": PD.labels_hash(_slides, None), "key": {**_k1, "mode": "edit"}, "answer": {"slides": {}, "overview": "옛 개요"}}
_got = PD.hook(_fake, "B132K", kept=_old, made={}, tally={})(_slides)
show("ⓚ 개요 · 덱은 `3.3_outline.md`의 판(구조 지시문과 따로) · 덱 열쇠는 구조 방식과 무관 · 옛 보존분(열쇠에 방식 칸)이 그대로 재사용(LLM 0)",
     prompt_version("outline") != prompt_version(ST.PROMPT) and _k1 == _k2 and "mode" not in _k1 and not _asked and _got is not None,
     f"개요 판 {prompt_version('outline')} · 구조 판 {prompt_version(ST.PROMPT)} · 덱 다시 물음 {len(_asked)}")

done()
