# -*- coding: utf-8 -*-
"""B87 — 산문 엑셀의 계층은 문서(시트)마다: 번호 군 · 글자 상한 · 규칙 선언 (칸 2.4·2.5·2.6).

표본은 `tests/fixtures/raw/HIER01.xlsx`·`FONT01.xlsx`(`tests/fixtures/make_b87.py`가 만든다).
잠그는 성질:
  ① 점 번호만 쓰는 시트의 레벨은 구판과 같다 · 군 사이의 레벨은 첫 등장 순서 · 60자 넘는
     번호 행과 글머리표는 제목이 아니다
  ③ 상한 이하 청크는 손대지 않는다 · 넘는 청크의 조각은 상한 이하(혼자 넘는 행 표시 제외) ·
     조각 경계는 행 경계 · 이으면 원문
  ② 안 선 시트만 선언을 묻고 데이터로 적용 · 보존되어 재인입 호출 0 · 원본이 바뀌면 다시 ·
     잘못된 선언은 버리고 통째 + 큐 · ref 시트·mock·등록 리허설은 호출 0 · 예고가 먼저
  B89 ① 셀 안 줄바꿈 — 조각의 locator는 그 조각의 첫 행~끝 행 · 조각 글은 온전한 셀의 이어붙임
     (한 단계 더 쪼개기·글자 상한 두 갈래 모두) · 행 없는 청크는 조용히 넘기지 않는다
     (표본 `NL01.xlsx` — `tests/fixtures/make_b89.py`)
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, done   # noqa: F401

from parser import struct_rule                                        # noqa: E402
from parser.adapters import basic_prose_xlsx as BX                   # noqa: E402

HIER, FONT = RAW / "HIER01.xlsx", RAW / "FONT01.xlsx"
DECL = {"heading_patterns": [{"match": r"^\S+(?: \S+)?$", "level": 1}],
        "bold_is_heading": False, "merge_is_heading": False, "heading_column": None,
        "reason": "한두 단어의 짧은 행 뒤에 문장 행이 여럿 따른다"}


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
print("\n■ B87 ② 규칙 선언 — 안 선 시트만 · 데이터로 적용 · 기록")
_calls, _order = [], []


def _stub(decl):
    def ask(frame, sample):
        _calls.append(frame)
        _order.append("호출")
        return dict(decl)
    return ask


def _parse(path, doc_id, decl=DECL, **kw):
    _calls.clear()
    _order.clear()
    return pipeline.parse(BX, doc_id, str(path), closed_list=[], infer_rules=_stub(decl),
                          rule_notice=lambda info: _order.append("예고"), **kw)


struct_map.invalidate("B87FONT")
_r1 = _parse(FONT, "B87FONT")
_rp = [c for c in _r1.envelope["chunks"]]
show("② 제목 신호가 없는 시트(글자 크기만)에 선언이 적용돼 계층이 선다",
     _r1.ok and _calls == ["사양서"] and len(_rp) > 1
     and all(c["meta"]["split_path"] == BX.PATH_RULE for c in _rp),
     f"호출 {_calls} · 청크 {len(_rp)}")
show("② 예고가 부르기 전에 온다", _order[:2] == ["예고", "호출"], str(_order))
_kept = struct_map.load_kept("B87FONT") or {}
_r2 = _parse(FONT, "B87FONT")
show("② 선언이 보존 파일에 있고 같은 파일 재인입은 호출 0 · 같은 청크",
     "사양서" in (_kept.get("rules") or {}) and not _calls
     and [c["text"] for c in _r2.envelope["chunks"]] == [c["text"] for c in _rp],
     f"보존 {sorted((_kept.get('rules') or {}))} · 재인입 호출 {len(_calls)}")
with tempfile.TemporaryDirectory(prefix="b87_") as _td:
    from openpyxl import load_workbook
    _wb = load_workbook(str(FONT))
    _wb.active["A2"] = _wb.active["A2"].value + " (개정)"
    _changed = Path(_td) / "FONT01.xlsx"
    _wb.save(str(_changed))
    _parse(_changed, "B87FONT")
show("② 원본이 바뀌면(원본 해시 다름) 다시 부른다", _calls == ["사양서"], str(_calls))
struct_map.invalidate("B87BAD")
_bad = _parse(FONT, "B87BAD", decl={**DECL, "heading_patterns": [{"match": "(개요", "level": 1}]})
_bc = _bad.envelope["chunks"]
show("② 잘못된 선언(`^` 없음·컴파일 실패)은 버려지고 통째 + 큐 표시 · 보존하지 않는다",
     _bad.ok and len(_bc) == 1 and _bc[0]["meta"].get("hierarchy_unresolved")
     and "버렸다" in _bc[0]["meta"].get("unresolved_reason", "")
     and "사양서" not in ((struct_map.load_kept("B87BAD") or {}).get("rules") or {}),
     _bc[0]["meta"].get("unresolved_reason", "")[:60])
_parse(FONT, "B87REF", sheet_roles={"사양서": "ref"})
show("② `ref` 시트는 부르지 않는다 (참조는 LLM 0 — B83)", not _calls, str(_calls))
import types                                                          # noqa: E402
_wrap = types.SimpleNamespace(ADAPTER={**BX.ADAPTER, "doc_type": "b87wrap"},
                              extract=BX.extract, level_report=BX.level_report)
struct_map.invalidate("B87WRAP")
_calls.clear()
pipeline.parse(_wrap, "B87WRAP", str(FONT), closed_list=[], infer_rules=_stub(DECL))
show("② 이미 등록된 위임 래퍼(`rule_frames`를 안 내보낸다)로도 대상 시트를 찾는다",
     _calls == ["사양서"], str(_calls))
_parse(HIER, "B87HIER")
show("② 고정 규칙으로 선 시트는 부르지 않는다 (번호 군으로 선 HIER01)", not _calls, str(_calls))

from cli import parse as _cp                                         # noqa: E402
show("② mock은 주입이 없다 — 구판과 같은 동작(통째 + 큐 · 호출 0)",
     _cp.injections().get("infer_rules") is None
     and BX.extract(read(str(FONT)))[0]["meta"]["split_path"] == BX.PATH_FLAT)

# 등록 리허설 — **주입이 와도** 리허설은 넘기지 않는다(generate는 파악만).
from cli.register import view as _view                               # noqa: E402
_seen = []
_orig_inj = _view.injections
_view.injections = lambda: {**_orig_inj(), "infer_rules": lambda f, s: _seen.append(f)}
try:
    from cli.register import generate as _gen                         # noqa: E402
    _gen.cmd_generate("b87font", "process", [str(FONT)], use_basic=True)
finally:
    _view.injections = _orig_inj
    shutil.rmtree(_P.review("b87font"), ignore_errors=True)       # 등록 단은 클린이 안 지운다
show("② 등록 리허설은 주입이 있어도 부르지 않는다 (「인입 때 선언 필요」만 보인다)",
     not _seen, str(_seen))
from cli.register import draft as _dr                                  # noqa: E402
show("② 안 선 시트만 있는 표본도 **산문 근거가 있으면** 고정 어댑터로 등록된다 · 표는 여전히 거부",
     (_dr.basic_adapter_proposal([str(FONT)], said_prose=True) or {}).get("rule_frames") == 1
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
_kit = (ROOT / "kit" / "run_adapter.py").read_text(encoding="utf-8")
show("② 킷 관문은 규칙 선언 훅을 넘기지 않는다 (완주 검사 — 주입 0)",
     "infer_rules" not in _kit and "struct_rule_fn" not in _kit)
_imp = sorted({ln.split()[1].split(".")[0]
               for f in (ROOT / "parser").rglob("*.py")
               for ln in f.read_text(encoding="utf-8").splitlines()
               if ln.startswith(("import ", "from "))})
show("② 파서 패키지에 core import 0", "core" not in _imp, str(_imp))

done()
