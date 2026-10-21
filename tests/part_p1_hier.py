# -*- coding: utf-8 -*-
"""B87 — 산문 엑셀의 계층은 문서(시트)마다: 번호 군 · 글자 상한 (칸 2.5·2.6 — 규칙 선언 ⑦은 B121 ③에서 지웠다).

표본은 `tests/fixtures/raw/HIER01.xlsx`·`FONT01.xlsx`(`tests/fixtures/make_b87.py`가 만든다).
잠그는 성질:
  ① 점 번호만 쓰는 시트의 레벨은 구판과 같다 · 군 사이의 레벨은 첫 등장 순서 · 60자 넘는
     번호 행과 글머리표는 제목이 아니다
  ③ 상한 이하 청크는 손대지 않는다 · 넘는 청크의 조각은 상한 이하(혼자 넘는 행 표시 제외) ·
     조각 경계는 행 경계 · 이으면 원문
  ② 안 선 시트만 있는 표본도 산문 근거가 있으면 고정 어댑터로 등록 · 표는 거부
  B89 ① 셀 안 줄바꿈 — 조각의 locator는 그 조각의 첫 행~끝 행 · 조각 글은 온전한 셀의 이어붙임
     (한 단계 더 쪼개기·글자 상한 두 갈래 모두) · 행 없는 청크는 조용히 넘기지 않는다
     (표본 `NL01.xlsx` — `tests/fixtures/make_b89.py`)
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, done   # noqa: F401

from parser import sig as SG                                         # noqa: E402
from parser.adapters import basic_prose_xlsx as BX                   # noqa: E402

HIER, FONT = RAW / "HIER01.xlsx", RAW / "FONT01.xlsx"


def _sheet(path, name):
    return next(s for s in read(str(path))["sheets"] if s["name"] == name)


def _heads(sheet):
    _lines, rows, _m = BX._rows_of(sheet)
    text = dict(_lines)
    return [(text[r["row"]], r["level"]) for r in rows if r["heading"]], _lines, rows


# ────────────────────────────────────────────────────────────── ①
print("\n■ B87 ① 제목 번호 패턴 군 — LLM 0")
_same = True
for _f in ("TOC01.xlsx", "TOC02.xlsx", "RFQ01.xlsx"):
    for _sh in read(str(RAW / _f))["sheets"]:
        _col = BX._content_column(_sh)
        if not _col:
            continue
        _l, _rows, _m = BX._rows_of(_sh)
        _t = dict(_l)
        for _r in _rows:                   # 구판의 규칙: 점 번호면 레벨 = 점 개수, 아니면 0
            _m = re.match(r"^(\d+(?:\.\d+)*)[.)]?\s+", _t[_r["row"]])
            if _m and _r["signal"] in (BX.SIG_NUM, None):
                _same &= _r["level"] == len(_m.group(1).split("."))
show("① 점 번호만 쓰는 시트의 레벨은 구판 규칙과 같다 (레벨 = 점 개수)", _same)
_h, _hl, _hr = _heads(_sheet(HIER, "사양"))
_first = {}
for _txt, _lv in _h:
    _first.setdefault(_txt.split()[0][-1] if _txt[0] == "(" else _txt[:2], _lv)
show("① `Ⅰ./1./가./(1)` 혼용 — 레벨이 처음 나온 순서대로 1~4",
     [lv for _txt, lv in _h[:4]] == [1, 2, 3, 4]
     and [t.split()[0] for t, _lv in _h[:4]] == ["Ⅰ.", "1.", "가.", "(1)"], str(_h[:4]))
_long = [t for _r, t in _hl if len(t) > struct_map.HEADING_MAX_CHARS and SG.signature(t)[1] is not None]
show("① 60자 넘는 번호 행은 제목이 아니다 (목록 항목·본문)",
     _long and not any(t in dict(_h) for t in _long), f"긴 번호 행 {len(_long)}")
_bul = [t for _r, t in _hl if t[:1] in "-•·"]
show("① 글머리표 행은 제목이 아니다", _bul and not any(t in dict(_h) for t in _bul),
     f"글머리표 {len(_bul)}")

# ────────────────────────────────────────────────────────────── ③
print("\n■ B87 ③ 행 우선 + 글자 상한 — 넘는 청크만 행 경계로")
_cap = struct_map.CHUNK_MAX_CHARS


def _extract(path, cap):
    struct_map.CHUNK_MAX_CHARS = cap
    try:
        return BX.extract(read(str(path)))
    finally:
        struct_map.CHUNK_MAX_CHARS = _cap


_under = [f for f in ("TOC01.xlsx", "TOC02.xlsx", "RFQ01.xlsx")
          if all(len(p.get("text") or "") <= _cap for p in _extract(RAW / f, 10 ** 9))]
show("③ 상한 이하 청크만 있는 문서는 분할이 그대로다 (상한을 없앤 것과 같다)",
     _under and all(_extract(RAW / f, _cap) == _extract(RAW / f, 10 ** 9) for f in _under),
     str(_under))
_whole = {p["source_locator"]: p for p in _extract(HIER, 10 ** 9)}
_cut = BX.extract(read(str(HIER)))
_parts = [p for p in _cut if (p.get("meta") or {}).get("char_cap_from")]
show("③ 넘는 청크의 조각은 전부 상한 이하다 (혼자 넘는 행 — 표시된 것만 예외)",
     _parts and all(len(p["text"]) <= _cap or (p["meta"].get("over_char_cap")
                                               and "\n" not in p["text"]) for p in _parts),
     f"조각 {len(_parts)} · 최대 {max(len(p['text']) for p in _parts)}자")
_cells = {r: t for r, t in _hl}
_long_sh = _sheet(HIER, "장문")
_cl = dict(BX._rows_of(_long_sh)[0])


def _rows_of_loc(loc):
    m = re.search(r"!R(\d+)(?:-R(\d+))?$", loc)
    a = int(m.group(1))
    return a, int(m.group(2) or a)


show("③ 조각 경계는 행 경계다 — 조각 글 = 그 행 범위 셀들의 글 (셀 중간을 자르지 않는다)",
     all(p["text"] == "\n".join(t for r, t in sorted(_cl.items())
                                if _rows_of_loc(p["source_locator"])[0] <= r
                                <= _rows_of_loc(p["source_locator"])[1])
         for p in _parts))
_joined = {}
for p in _parts:
    _joined.setdefault(p["meta"]["char_cap_from"], []).append(p["text"])
show("③ 조각을 이으면 원래 청크의 글과 같다 (무손실)",
     _joined and all("\n".join(v) == _whole[k]["text"] for k, v in _joined.items()),
     str({k: len(v) for k, v in _joined.items()}))

# ────────────────────────────────────────────────────────────── ②
# 계층 규칙 선언(⑦ struct_rule)은 B121 ③에서 지웠다 — 안 선 시트는 문서 구조(⑪ — 조각 g6_structure)가 세운다.
print("\n■ 안 선 시트의 등록")


def _parse(path, doc_id, **kw):
    return pipeline.parse(BX, doc_id, str(path), closed_list=[], **kw)


from cli.register import draft as _dr                                  # noqa: E402
show("② 안 선 시트만 있는 표본도 **산문 근거가 있으면** 고정 어댑터로 등록된다 · 표는 여전히 거부",
     _dr.basic_adapter_proposal([str(FONT)], said_prose=True) is not None
     and _dr.basic_adapter_proposal([str(FONT)]) is None
     and _dr.basic_adapter_proposal([str(RAW / "CP01.xlsx")], said_prose=True) is None)

# ────────────────────────────────────────────────────────────── B89 ①
print("\n■ B89 ① 셀 안 줄바꿈 — locator를 행에서 만든다")


def _whole_cells(pieces, cells):
    """조각마다 글 = locator 범위 행들의 셀 글 이어붙임 · locator 유일 — 어긋난 조각 목록."""
    locs = [p["source_locator"] for p in pieces]
    bad = [loc for loc in locs if locs.count(loc) > 1]
    for p in pieces:
        a, b = _rows_of_loc(p["source_locator"])
        if p["text"] != "\n".join(t for r, t in sorted(cells.items()) if a <= r <= b):
            bad.append(p["source_locator"])
    return bad


_nl = _sheet(RAW / "NL01.xlsx", "사양")
_nlc = dict(BX._rows_of(_nl)[0])
_nlp = BX.extract(read(str(RAW / "NL01.xlsx")))
_rep = _parse(RAW / "NL01.xlsx", "B89NL")
show("B89 ① 글자 상한 갈래 — 조각 글 = 그 locator 행 범위의 온전한 셀들 · locator 유일 · validator 결함 0",
     any("\n" in t for t in _nlc.values()) and len(_nlp) > 1
     and not _whole_cells(_nlp, _nlc) and _rep.ok,
     f"조각 {len(_nlp)} · 어긋남 {_whole_cells(_nlp, _nlc)}")
# 한 단계 더 쪼개기(`_resplit`)는 **행 수**가 상한의 두 배를 넘어야 탄다 — 표본으로는 안 닿아
# 합성 줄 목록으로 잰다: 셀 안 줄바꿈 · 같은 글 반복(「해당 없음」) · 2레벨 제목
_n2 = struct_map.CHUNK_MAX * 2 + 6
_syn = [(1, "1. 상세")] + [
    (r, "2. 하위" if r % 20 == 2 else ("해당 없음" if r % 3 else f"항목 {r}\n둘째 줄\n셋째 줄"))
    for r in range(2, _n2 + 2)]
_sm = {"분할_레벨": 1, "rows": [{"row": r, "heading": t[:2] in ("1.", "2."),
                                  "level": 1 if t.startswith("1.") else 2} for r, t in _syn]}
_sp = struct_map.split(_sm, _syn, lambda a, b: f"S!R{a}" if a == b else f"S!R{a}-R{b}")
show("B89 ① 한 단계 더 쪼개기 갈래 — 같은 성질 (행 수로 판정 · 행 번호로 자른다)",
     len(_sp) > 1 and not _whole_cells(_sp, dict(_syn[1:])),
     f"조각 {len(_sp)} · 어긋남 {_whole_cells(_sp, dict(_syn[1:]))[:3]}")
try:
    struct_map.cap_chars([{"source_locator": "S!R1", "text": "x"}], set(), lambda a, b: "")
    _raised = False
except ValueError:
    _raised = True
show("B89 ① 행 목록 없는 청크는 결함으로 드러난다 (원래 locator를 붙여 넘기지 않는다)", _raised)
# B132 ⑥ — 넘는 조각은 깊은 제목을 차례로(한 단계 → 두 단계 … → 행 경계) · 합성 줄(창작 — 근거가 아니다)
_syn6 = [(1, "1. 상세"), (2, "가. 공급"), (3, "1) 속도"), (4, "속" * 40), (5, "2) 하중"), (6, "하" * 40), (7, "나. 적층"), (8, "짧은 본문")]
_lv6 = {1: 1, 2: 2, 3: 3, 5: 3, 7: 2}
struct_map.CHUNK_MAX_CHARS = 60
try:
    _sp6 = struct_map.split({"분할_레벨": 1, "rows": [{"row": r, "heading": r in _lv6, "level": _lv6.get(r, 0)} for r, _t in _syn6]},
                            _syn6, lambda a, b: f"S!R{a}" if a == b else f"S!R{a}-R{b}")
finally:
    struct_map.CHUNK_MAX_CHARS = _cap
_st6 = [_rows_of_loc(p["source_locator"])[0] for p in _sp6]
show("B132 ⑥ 글자 상한 — 넘는 조각은 깊은 제목을 차례로 나눈다(가. 단으로 나눠도 넘는 조각은 1) 단에서 · 행 경계는 더 깊은 제목이 없을 때만)",
     _st6 == [2, 3, 5, 7] and all(len(p["text"]) <= 60 for p in _sp6), f"조각 시작 {_st6}")

# ────────────────────────────────────────────────────────────── B130 ①② 목차 · 경로 · 제목 줄
print("\n■ B130 목차는 번호 이어짐 · 다시 시작으로 · 모든 청크가 목차 경로 전체를 · 제목 줄은 자기 청크에")
import tempfile                                                       # noqa: E402
from openpyxl import Workbook                                         # noqa: E402
from parser import toc, tuning                                        # noqa: E402
from core.build import structure as _ST                               # noqa: E402
TOC = ["1. 공정별 상세사양", "1) 적용 범위", "이 사양은 노칭 공정에 적용한다.", "가. 일반", "설비는 정해진 자리에 둔다.", "나. 생산능력",
       "1) 생산 capa", "월 100만 셀을 만든다.", "2) 설비 가동률", "가동률은 90%다.", "다. 수량", "1) 설비 수량", "두 대를 둔다.",
       "2) 예비품", "예비 금형 하나.", "라. 검사", "4) 검수방법", "A. 입고전 검수", "외관을 본다.", "B. 입고후 검수", "치수를 잰다."]
_tlines = list(enumerate(TOC, 1))
_lv = {r: v[0] for r, v in toc.number_levels(_tlines).items()}
_chain = toc.toc_chains(_tlines, _lv)[1]
_par = {r: (_chain(r)[-2] if len(_chain(r)) > 1 else None) for r in _lv}
show("ⓐ 목차 — 「나.」의 부모 = 「1.」(「1) 적용 범위」 아래에 가. · 나.가 들지 않는다) · 「나.」 아래 「1)」의 부모 = 「나.」 · 「A.」의 부모 = 「4)」",
     _par[6] == 1 and _par[4] == 1 and _par[2] == 1 and _par[7] == 6 and _par[9] == 6 and _par[12] == 11 and _par[17] == 16
     and _par[18] == 17 and _par[20] == 17, f"부모 {_par}")
_td = Path(tempfile.mkdtemp(prefix="b130_"))
_wb = Workbook()
_wb.active.title = "사양"
for _i, _t in _tlines:
    _wb.active.cell(row=_i, column=1, value=_t)
_wb.save(_td / "B130T.xlsx")


def _paths_ok(env, _lv=_lv, _chain=_chain):
    """청크마다 (경로 = 주인 사슬 전체 · 본문의 제목 줄은 전부 그 주인의 자손 — 남의 꼬리 0) · 빠진 제목 줄."""
    bad, seen = [], set()
    for c in env["chunks"]:
        _ns = [int(x) for x in re.findall(r"R(\d+)", c["source_locator"])]
        body = list(range(_ns[0], _ns[-1] + 1))
        path = [p.strip() for p in (c.get("section") or "").split(">") if p.strip()]
        rows = [r for r in _lv if TOC[r - 1] in path]
        owner = rows[-1] if rows else None
        if path != [TOC[r - 1] for r in _chain(owner)] if owner else path:
            bad.append(("경로", c["source_locator"], path))
        for r in body:
            if r in _lv and owner is not None and owner not in _chain(r):
                bad.append(("남의 꼬리", c["source_locator"], TOC[r - 1]))
        seen |= set(rows) | {r for r in body if r in _lv}
    return bad, sorted(set(_lv) - seen)


def _own(res):
    """구조가 선 시트의 목차(`rules` 방식 — 구조 경로의 초안은 첫 서수 · 이어짐 · B137 ①) — `(제목 행, chain)`."""
    par = {h["row"]: h.get("parent") for h in res.report["structure"]["프레임"]["사양"]["headings"]}

    def chain(h):
        out = []
        while h is not None:
            out.append(h)
            h = par.get(h)
        return out[::-1]
    return {r: 1 for r in par}, chain


_res_t, _tree_t = {}, {}
for _how, _knob in (("자른 단", {"chunk_rows": [1, 2]}), ("글자 상한 조각", {"chunk_rows": [1, 2], "chunk_max_chars": 12})):
    tuning.apply(_knob)
    struct_map.invalidate("B130T")
    _res_t[_how] = pipeline.parse(BX, "B130T", str(_td / "B130T.xlsx"), closed_list=[]).envelope
    struct_map.invalidate("B130T")
    _ST.MODE = "rules"                                               # 구조 방식 rules — 코드 사다리 (B132 ⑧)
    _rr = pipeline.parse(BX, "B130T", str(_td / "B130T.xlsx"), closed_list=[], structure=_ST.structurer())
    _res_t[_how + " · rules"], _tree_t[_how + " · rules"] = _rr.envelope, _own(_rr)
    _ST.MODE = "ladder"
tuning.apply({})
# 기대 변경(B139 ② — 첫 서수와 사다리 단 순서가 어긋나면 초안은 사다리라 rules 방식도 어댑터 목차와 같다 · B137 ①의 예외를 걷는다)
_chk = {k: _paths_ok(v) for k, v in _res_t.items()}
_sec = [c["section"] for c in _res_t["글자 상한 조각"]["chunks"]]
show("ⓑ 경로 — 모든 청크가 시트 아래 목차 경로 전체(자른 단 · 글자 상한 조각 · rules 방식 — 같은 목차) · 예 「… > 라. 검사 > 4) 검수방법 > A. 입고전 검수」",
     all(not b for b, _m in _chk.values()) and "1. 공정별 상세사양 > 라. 검사 > 4) 검수방법 > A. 입고전 검수" in _sec,
     f"{ {k: b[:2] for k, (b, _m) in _chk.items()} } · 조각 경로 {_sec[-3:]}")
show("ⓒ 제목 줄 — 남의 청크 끝줄에 붙은 제목 0 · 빠진 제목 줄 0(본문 첫 줄이거나 경로에)",
     all(not m for _b, m in _chk.values()), f"빠짐 { {k: m for k, (_b, m) in _chk.items()} }")

# ────────────────────────────────────────────────────────────── B139 ②① 충돌의 기본값 · 목록 단위
print("\n■ B139 첫 서수와 사다리가 어긋나면 초안은 사다리 · 부모 바꿈은 목록 단위")
from fake_gateway import Live                                         # noqa: E402
from core.build import structure_edit as _SE                          # noqa: E402
_LAD9 = {"levels": [{"sigs": [s], "role": None, "category": None, "rows": [], "why": "단"} for s in ("9.", "가.", "9)", "A.")],
         "unnumbered": []}
_m9 = {}
for _mode in ("rules", "ladder"):
    _ST.MODE = _mode
    _ST.DOC.pop("B130T", None)
    struct_map.invalidate("B130T")
    with Live(by={"structure": lambda b: _LAD9 if b.get("task") == "ladder" else {"answers": [], "edits": [], "rules": []}}):
        _m9[_mode] = pipeline.parse(BX, "B130T", str(_td / "B130T.xlsx"), closed_list=[],
                                    structure=_ST.structurer(["process"])).report["structure"]["프레임"]["사양"]
_ST.MODE = "ladder"
_tr9 = {k: {h["row"]: h.get("parent") for h in f["headings"]} for k, f in _m9.items()}
_cl9 = {k: {n["row"]: n["why"] for n in f["needs"] if n["kind"] == "ⓒ"} for k, f in _m9.items()}
show("B139 ⓑ 충돌의 기본값 — B130 꼴이 rules · ladder 둘 다 가. · 나. · 다. → 「1.」 아래(초안 = 어댑터 목차) + 판단 필요(「첫 서수로는 바로 위 "
     "2행 아래」) · 사내 꼴은 B137 ⓐ가 그대로 잰다",
     all(_tr9[k] == _par for k in _m9) and all("첫 서수로는 바로 위 2행" in _cl9[k].get(4, "") for k in _m9),
     f"가. 나. 다. 부모 { {k: [_tr9[k].get(r) for r in (4, 6, 11)] for k in _m9} } · 4행 판단 필요 { {k: _cl9[k].get(4, '')[:30] for k in _m9} }")
#: 갈린 나무가 나던 초안(15626ef — 첫 서수가 늘 이겨 가. · 나. · 다. · 라.가 「1) 적용 범위」 아래) 위에 고침 하나
_old9 = {**_par, 4: 2, 6: 2, 11: 2, 16: 2}
_lab9 = _m9["rules"]["labels"]
_ed9 = lambda row, parent: _SE.apply_edits("B130T", "사양", _lab9, [{"row": r, "parent": p, "role": None} for r, p in _old9.items()],  # noqa: E731
                                           {"edits": [{"row": row, "what": "부모 바꿈", "parent": parent}], "headings": []}, [])[0]
_hd9 = {h["row"]: h.get("parent") for h in _ed9(4, 1)}
_mid9 = {h["row"]: h.get("parent") for h in _ed9(11, 1)}
show("B139 ⓐ 목록 단위 — 「가.」를 「1.」 아래로 옮기면 「나.」 · 「다.」 · 「라.」와 그 아래 「1)」 · 「2)」가 함께(나무가 갈리지 않는다 — 어댑터 목차와 같다) · "
     "목록 중간 줄(「다.」) 하나의 고침은 그 줄만",
     _hd9 == _par and _mid9 == {**_old9, 11: 1},
     f"머리 고침 {[_hd9.get(r) for r in (4, 6, 7, 11, 12, 16)]} · 중간 줄 고침 {[_mid9.get(r) for r in (4, 6, 11, 16)]}")
shutil.rmtree(_td, ignore_errors=True)

_imp = sorted({ln.split()[1].split(".")[0]
               for f in (ROOT / "parser").rglob("*.py")
               for ln in f.read_text(encoding="utf-8").splitlines()
               if ln.startswith(("import ", "from "))})
show("② 파서 패키지에 core import 0", "core" not in _imp, str(_imp))

done()
