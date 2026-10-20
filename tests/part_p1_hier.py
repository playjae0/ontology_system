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

from parser.adapters import basic_prose_xlsx as BX                   # noqa: E402

HIER, FONT = RAW / "HIER01.xlsx", RAW / "FONT01.xlsx"


def _sheet(path, name):
    return next(s for s in read(str(path))["sheets"] if s["name"] == name)


def _heads(sheet):
    _lines, rows = BX._rows_of(sheet, BX._content_column(sheet))
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
        _l, _rows = BX._rows_of(_sh, _col)
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
_long = [t for _r, t in _hl if len(t) > struct_map.HEADING_MAX_CHARS and struct_map.heading_family(t[:20])]
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
_cl = dict(BX._rows_of(_long_sh, BX._content_column(_long_sh))[0])


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
_nlc = dict(BX._rows_of(_nl, BX._content_column(_nl))[0])
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

# ────────────────────────────────────────────────────────────── B130 ①② 목차 · 경로 · 제목 줄
print("\n■ B130 목차는 번호 이어짐 · 다시 시작으로 · 모든 청크가 목차 경로 전체를 · 제목 줄은 자기 청크에")
import tempfile                                                       # noqa: E402
from openpyxl import Workbook                                         # noqa: E402
from parser import toc, tuning                                        # noqa: E402
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


def _paths_ok(env):
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


_res_t = {}
for _how, _knob in (("자른 단", {"chunk_rows": [1, 2]}), ("글자 상한 조각", {"chunk_rows": [1, 2], "chunk_max_chars": 12})):
    tuning.apply(_knob)
    struct_map.invalidate("B130T")
    _res_t[_how] = pipeline.parse(BX, "B130T", str(_td / "B130T.xlsx"), closed_list=[]).envelope
    struct_map.invalidate("B130T")
    _res_t[_how + " · rules"] = pipeline.parse(BX, "B130T", str(_td / "B130T.xlsx"), closed_list=[],
                                               structure=lambda d, f, labs: {"skip": True, "mode": "rules"}).envelope
tuning.apply({})
_chk = {k: _paths_ok(v) for k, v in _res_t.items()}
_sec = [c["section"] for c in _res_t["글자 상한 조각"]["chunks"]]
show("ⓑ 경로 — 모든 청크가 시트 아래 목차 경로 전체(자른 단 · 글자 상한 조각 · rules 방식 같다) · 예 「… > 라. 검사 > 4) 검수방법 > A. 입고전 검수」",
     all(not b for b, _m in _chk.values()) and "1. 공정별 상세사양 > 라. 검사 > 4) 검수방법 > A. 입고전 검수" in _sec
     and [c["section"] for c in _res_t["자른 단 · rules"]["chunks"]] == [c["section"] for c in _res_t["자른 단"]["chunks"]],
     f"{ {k: b[:2] for k, (b, _m) in _chk.items()} } · 조각 경로 {_sec[-3:]}")
show("ⓒ 제목 줄 — 남의 청크 끝줄에 붙은 제목 0 · 빠진 제목 줄 0(본문 첫 줄이거나 경로에)",
     all(not m for _b, m in _chk.values()), f"빠짐 { {k: m for k, (_b, m) in _chk.items()} }")
shutil.rmtree(_td, ignore_errors=True)

_imp = sorted({ln.split()[1].split(".")[0]
               for f in (ROOT / "parser").rglob("*.py")
               for ln in f.read_text(encoding="utf-8").splitlines()
               if ln.startswith(("import ", "from "))})
show("② 파서 패키지에 core import 0", "core" not in _imp, str(_imp))

done()
