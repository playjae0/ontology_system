# -*- coding: utf-8 -*-
"""P1 ⑤ 좌표 — 시스템이 아는 값은 LLM이 쓰지 않는다 · 분할 기준 기록 · 좌표 태깅 상한."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, _MAPS, _fixed_map, done   # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from core.llm import gateway as _LLM


print("\n■ B62 ① — 시스템이 아는 값은 LLM이 쓰지 않는다")

from parser import preflight as _PF                              # noqa: E402

# ①-a **`format`을 보지 않는다** — CSV 리더는 「xlsx로 위장하지 않는다」고 정직하게
# 내는데 preflight가 xlsx만 받아, CSV table 어댑터는 **통과할 수 없었다**.
_csv62 = read(str(RAW / "CSV05_wide.csv"))
show("①ⓑ csv raw로 header_labels()가 비어 있지 않다 (format을 보지 않는다)",
     _csv62["format"] == "csv" and len(_PF.header_labels(_csv62, 1, {})) == 7,
     str(_PF.header_labels(_csv62, 1, {})[:3]))
# 정규화는 **한 자리**다 — 두 곳이 다르면 같은 셀을 다르게 읽는다.
show("① 라벨 정규화가 한 자리다 (NFKC · 공백 접기 · strip · 내용은 안 바꾼다)",
     reader.norm_label("  Ａ\n B  ") == "A B" and reader.norm_label(None) == ""
     and reader.norm_label("Center") == "Center")

# ①-b **시트 해석기 하나** — 둘 이상인데 생략이면 adapter_mismatch이고 이름 목록이 온다.
_two62 = {"format": "xlsx", "sheets": [
    {"name": "앞", "max_row": 2, "max_col": 2, "cells": {"A1": "가", "B1": "나"}},
    {"name": "뒤", "max_row": 2, "max_col": 2, "cells": {"A1": "다", "B1": "라"}}]}


class _Ad62:
    ADAPTER = {"doc_type": "t62", "adapter_version": "1.0", "payload_kind": "table",
               "expects": {"header_row": 1, "header_labels": ["가", "나"],
                           "columns": {"a": "A", "b": "B"}}}


_ok62, _d62 = _PF.check(_Ad62, _two62)
show("①ⓑ 시트 둘 + sheet 생략 → adapter_mismatch · detail에 시트 이름 목록",
     not _ok62 and _d62.get("sheets") == ["앞", "뒤"] and "sheet" in _d62["reason"],
     _d62["reason"])
_Ad62.ADAPTER["expects"]["sheet"] = "뒤"
_Ad62.ADAPTER["expects"]["header_labels"] = ["다", "라"]
show("①ⓑ sheet 이름을 선언하면 그 시트를 읽는다",
     _PF.check(_Ad62, _two62)[0]
     and _PF.header_labels(_two62, 1, _Ad62.ADAPTER["expects"]) == ["다", "라"])

# ①-c **채우기 전 위치 검증** — columns가 빈 헤더 셀을 가리키면 관문 FAIL.
_susp62 = {"format": "csv", "sheets": [
    {"name": "s", "max_row": 3, "max_col": 3,
     "cells": {"A2": "가", "B2": "나", "A3": "1", "B3": "2"}}]}
_exp62 = {"header_row": 1, "columns": {"a": "A", "b": "B"}, "header_labels": []}
show("①ⓑ columns가 빈 헤더 셀을 가리키면 header_row 의심이다 (채우지 않는다)",
     (_PF.header_row_suspect(_susp62, _exp62) or {}).get("empty_columns") == ["A", "B"]
     and _PF.header_row_suspect(_susp62, {**_exp62, "header_row": 2}) is None,
     (_PF.header_row_suspect(_susp62, _exp62) or {}).get("reason", "")[:48])

# ①ⓒ **시트 0 고정은 리더 안에만** — 흩어지면 한 곳만 고쳐지는 날이 온다.
import re as _re62                                                # noqa: E402
_PAT62 = _re62.compile(r'\["sheets"\]\[0\]|sheets\[0\]|\)\[0\]\.get\("cells"\)')
_outside = [f"{f}:{i}" for d in ("parser", "cli", "kit")
            for f in sorted((ROOT / d).rglob("*.py"))
            if f.name != "reader.py"
            for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
            if _PAT62.search(ln)]
show("①ⓒ 시트 0 직접 참조가 리더 밖에 0줄이다", not _outside, str(_outside[:2]))
# 지문 스캔도 **같은 함수**를 부른다 — 구판은 제 구현을 들고 CSV에 똑같이 눈을 감았다.
show("① 지문 스캔이 preflight의 헤더 함수를 부른다 (두 벌이 아니다)",
     "preflight.header_labels(" in (ROOT / "cli" / "scan.py").read_text(encoding="utf-8"))


# ── B68 ① — 분할이 무엇을 기준으로 잘랐는지 기록한다 ──────────────────────
#
# 사내 실측 여덟째: 산문 xlsx를 고정 어댑터로 등록해 관문도 통과하고 청크도 잘
# 잘렸는데 **「무엇을 기준으로 잘랐나」가 어디에도 없었다.** `_rows_of`가 신호를
# 판정하고 버렸기 때문이다. 판정 규칙은 그대로 두고 **적기만** 한다.
print("\n■ B68 ① — 분할 기준을 기록한다 (규칙 불변 · LLM 0)")

from parser.adapters import basic_prose_xlsx as _bx68                  # noqa: E402

_raw68 = read(str(ROOT / "tests" / "fixtures" / "raw" / "TOC01.xlsx"))
_col68 = _bx68._content_column(_raw68["sheets"][0])
_lines68, _rows68 = _bx68._rows_of(_raw68["sheets"][0], _col68)
_rep68 = _bx68.level_report(_raw68)
show("① level_report 항목마다 분할_기준·지도_출처가 있다",
     _rep68 and all(x.get("분할_기준") and x.get("지도_출처") for x in _rep68),
     str([(x.get("분할_기준"), x.get("지도_출처")) for x in _rep68])[:120])
# **합이 헤딩 수와 같다** — 신호 없이 헤딩이 된 행이 있으면 기준이 거짓말을 한다.
_cnt68 = {}
for _r in _rows68:
    if _r["heading"]:
        _cnt68[_r.get("signal")] = _cnt68.get(_r.get("signal"), 0) + 1
show("① 신호별 헤딩 수의 합 == 그 프레임의 헤딩 수 (신호 없는 헤딩 0)",
     sum(_cnt68.values()) == sum(1 for r in _rows68 if r["heading"])
     and None not in _cnt68, str(_cnt68))
show("① 기준 문면이 신호별 수를 담는다 (세 신호의 이름은 코드의 상수)",
     all(str(v) in _bx68.split_basis(_rows68) for v in _cnt68.values())
     and all(k in _bx68.split_basis(_rows68) for k in _cnt68),
     _bx68.split_basis(_rows68))
# 규칙은 그대로다 — 레벨 판정이 신호 기록 전후로 같아야 한다(성질).
show("① 판정 규칙은 그대로다 — heading·level이 signal과 무관하게 선다",
     all(bool(r["level"]) == r["heading"] for r in _rows68)
     and all((r.get("signal") is None) == (not r["heading"]) for r in _rows68))
_calls68 = _LLM.usage_total()["calls"]
_bx68.level_report(_raw68)
struct_map.adapter_level_picks(_bx68.ADAPTER, _raw68)
show("① 기준 계산 경로에 LLM 호출 0 (시스템이 세는 일이다)",
     _LLM.usage_total()["calls"] == _calls68,
     f"{_calls68} → {_LLM.usage_total()['calls']}")
# **한 필드 이름, 두 경로** — 지도 경로의 pick에도 같은 키가 온다.
struct_map.invalidate("B68MAP")
_seen68 = []
lines, loc = map_lines()            # 상동
_h68 = pipeline._map_hook("B68MAP", seen=_seen68, ask=_fixed_map("MAPMOCK_OK"))
_h68("프레임1", lines, loc)
show("① 지도 경로 pick에도 분할_기준이 있다 (한 필드 이름, 두 경로)",
     _seen68 and str(_seen68[0].get("분할_기준", "")).startswith("구조 지도"),
     str([x.get("분할_기준") for x in _seen68]))
show("① 어댑터 경로의 지도_출처는 adapter:… 다 (구판은 이 자리가 비었다)",
     all(str(x.get("지도_출처")).startswith("adapter:") for x in _rep68))

# ── B69 ①③ — 묻는 단위는 행이 아니라 표기다 ─────────────────────────────
#
# 사내 실측 아홉째: CSV를 넣자 `coord_tag` 로그가 30줄 넘게 이어져 사람이 「무한」으로
# 읽고 껐다. 무한이 아니라 **행당 1회**였다 — 같은 표기가 200행에 있으면 200회이고
# 온도 0이라 답은 200번 같다. 결과는 그대로 두고 호출만 줄인다(결정적 dedupe).
print("\n■ B69 ①③ — 좌표 태깅: 표기당 1회 · 상한")

_NODES69 = [{"canonical": "노칭", "aliases": [], "tier": 1},
            {"canonical": "스태킹", "aliases": [], "tier": 1}]


def _pieces69(refs):
    return [{"source_locator": f"R{i}", "text": "x", "process_ref": r}
            for i, r in enumerate(refs, 1)]


def _picker69(log, answer=None):
    def pick(ref, choices):
        log.append(ref)
        return answer
    return pick


_log69 = []
_out69 = tagger.tag(_pieces69(["없는공정"] * 200), nodes=_NODES69,
                    pick=_picker69(_log69))
show("① 같은 목록 밖 표기 200행 → pick 호출 1회 (행이 아니라 표기가 단위다)",
     len(_log69) == 1, f"호출 {len(_log69)}회 · 조각 {len(_out69)}")
show("① 전 행의 값이 같다 — 한 번 물은 답을 배분한다",
     {p["process_ref"] for p in _out69} == {"없는공정"})
_log69b = []
tagger.tag(_pieces69(["A", "B", "C", "A", "B"]), nodes=_NODES69,
           pick=_picker69(_log69b))
show("① 서로 다른 표기 k종 → 호출 k회 (중복은 묻지 않는다 · null 답도 기억한다)",
     len(_log69b) == 3 and _log69b == ["A", "B", "C"], str(_log69b))
_log69c = []
_exact69 = tagger.tag(_pieces69(["노칭", "스태킹"] * 50), nodes=_NODES69,
                      pick=_picker69(_log69c))
show("① 정확 일치 행은 호출 0 (지금과 같다)",
     not _log69c and all(p["process_ref"] in ("노칭", "스태킹") for p in _exact69))
# **결과가 dedupe 전과 같다** — 행별 값을 그대로 비교한다(호출만 줄었다는 뜻).
_mix69 = ["노칭", "없는공정", "스태킹", "없는공정", "다른공정"]
_a69 = tagger.tag(_pieces69(_mix69), nodes=_NODES69, pick=_picker69([], "노칭"))
_want69 = ["노칭", "노칭", "스태킹", "노칭", "노칭"]   # 목록 밖은 채택 답으로 바뀐다
show("① 태깅 결과가 행별로 같다 — 채택은 전 행에, 목록 밖은 원문 그대로",
     [p["process_ref"] for p in _a69] == _want69,
     str([p["process_ref"] for p in _a69]))
_b69 = tagger.tag(_pieces69(_mix69), nodes=_NODES69, pick=_picker69([], "목록밖답"))
show("① 목록 밖 답은 버린다 — 원문이 남는다 (orphan_anchor는 인입 몫)",
     [p["process_ref"] for p in _b69] == _mix69)

# ② 예고는 **호출 전에** 무LLM으로 센 숫자다 — 비용이 화면에 오른다(B22의 정신).
_note69, _log69d = [], []
tagger.tag(_pieces69(["A", "A", "B", "노칭"]), nodes=_NODES69,
           pick=_picker69(_log69d), notice=_note69.append)
_pre69 = next(x for x in _note69 if x["단계"] == "예고")
_end69 = next(x for x in _note69 if x["단계"] == "끝")
show("② 예고의 표기 종수 == 실제 호출 횟수 (상한 미만일 때)",
     _pre69["묻는_종수"] == len(_log69d) == _end69["호출"] == 2,
     f"예고 {_pre69['묻는_종수']} · 실제 {len(_log69d)}")
show("② 예고가 조각·정확 일치·미스 행을 함께 센다 (호출 전에 안다)",
     (_pre69["조각"], _pre69["정확_일치"], _pre69["표기_종수"], _pre69["미스_행"])
     == (4, 1, 2, 3), str(_pre69))
_note69m = []
tagger.tag(_pieces69(["A", "B"]), nodes=_NODES69, notice=_note69m.append)
show("② mock(pick 없음)이면 LLM 0 — 예고가 그 사실을 값으로 말한다",
     _note69m[0]["LLM"] is False and _note69m[0]["묻는_종수"] == 0
     and _note69m[-1]["호출"] == 0)
# ③ 상한 — 넘는 표기는 **묻지 않고 그대로 둔다**(멈추지 않는다).
_log69e = []
_cap69 = tagger.tag(_pieces69(["A", "B", "C", "D"]), nodes=_NODES69,
                    pick=_picker69(_log69e, "노칭"), cap=2)
show("③ 상한 n이면 호출 ≤ n", len(_log69e) == 2, f"호출 {len(_log69e)}")
show("③ 초과분 행의 좌표는 원문 그대로다 (목록 밖 → 인입의 orphan_anchor)",
     [p["process_ref"] for p in _cap69] == ["노칭", "노칭", "C", "D"],
     str([p["process_ref"] for p in _cap69]))
_log69f = []
tagger.tag(_pieces69(["A", "B"]), nodes=_NODES69, pick=_picker69(_log69f), cap=0)
show("③ off(0)면 호출 0 — 정확 일치만", not _log69f)

done()
