# -*- coding: utf-8 -*-
"""P1 ④ 형태 — 스프레드시트 산문의 레벨 규칙 · table/prose 판정 · 큐 case 두 값."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from cli.register import draft as Rdraft
from core.llm import gateway as _LLM


print("\n■ B58 ③ — 스프레드시트 산문: 규칙이 레벨을 고른다")

from parser.adapters import basic_prose_xlsx as _BPX          # noqa: E402
from core.build import entry as _CP                              # noqa: E402
from core.state import registry as _RG                              # noqa: E402
from cli.parse import run_parse as _run_parse                 # noqa: E402

# **규칙 자체를 잠근다** — 화면 문구가 아니라 무엇을 고르는가다.
_C = struct_map.CHUNK_CENTER
show("③ 목표 구간의 중앙이 상수에서 파생된다 (숫자를 두 곳에 적지 않는다)",
     _C == (struct_map.CHUNK_MIN + struct_map.CHUNK_MAX) / 2
     and (struct_map.CHUNK_MIN, struct_map.CHUNK_MAX) == (5, 40),
     f"중앙 {_C}")
# 구간 안이 둘이면 **중앙 최근접**이지 청크 수 최대가 아니다 — 구판이 그랬다.
_st = {1: {"행수_평균": 6.0, "구간내_청크수": 9, "청크수": 9},
       2: {"행수_평균": 22.0, "구간내_청크수": 1, "청크수": 1}}
show("③ⓑ 구간 안에서는 중앙 최근접을 고른다 (구판의 「구간내 청크수 최대」가 아니다)",
     struct_map.choose_level(_st)[0] == 2, str(struct_map.choose_level(_st)[:1]))
_out = {2: {"행수_평균": 2.3, "구간내_청크수": 0, "청크수": 7},
        3: {"행수_평균": 1.8, "구간내_청크수": 0, "청크수": 9}}
_p, _w, _oor = struct_map.choose_level(_out)
show("③ⓓ 아무 레벨도 구간 안이 아니면 **최근접을 쓰고 구간밖을 세운다** (None이 아니다)",
     _p == 2 and _oor is True)
# 동점은 얕은 레벨 — 무엇이든 정해져 있어야 같은 문서가 같은 청크가 된다.
_tie = {1: {"행수_평균": 12.5, "구간내_청크수": 2, "청크수": 2},
        2: {"행수_평균": 32.5, "구간내_청크수": 2, "청크수": 2}}
show("③ 동점은 얕은 레벨이다 (멱등성 — 고르는 규칙에 빈틈을 두지 않는다)",
     struct_map.choose_level(_tie)[0] == 1)

# **LLM 0** — 어댑터가 지도 훅을 받고도 부르지 않는다. 문면이 아니라 호출을 센다.
_called = []
_raw01 = read(str(RAW / "TOC01.xlsx"))
_pieces = _BPX.extract(_raw01, struct_map_fn=lambda *a, **k: _called.append(a) or ([], {}, []))
show("③ⓐ 고정 어댑터가 구조 지도(⑦)를 부르지 않는다 — 인입마다 비용이 붙지 않는다",
     not _called and len(_pieces) == 3, f"호출 {len(_called)}회 · 조각 {len(_pieces)}건")
show("③ⓑ 신호 넷이 계층을 만든다 (번호·굵게·들여쓰기·가로병합)",
     _BPX.ADAPTER["expects"]["heading_signals"]
     == ["번호", "굵게", "들여쓰기", "가로병합"]
     and "split_level" not in _BPX.ADAPTER["expects"])
_rep01 = _BPX.level_report(_raw01)
show("③ⓑ 레벨별 분포와 고른 레벨·사유가 함께 나온다 (승인의 1차 근거 · §6.6-1)",
     len(_rep01) == 1 and _rep01[0]["분할_레벨"] == 1
     and _rep01[0]["분할_레벨_구간밖"] is False
     and set(_rep01[0]["레벨_분포"]) == {1, 2, 3},
     _rep01[0]["분할_레벨_사유"][:40])
_rep02 = _BPX.level_report(read(str(RAW / "TOC02.xlsx")))
show("③ⓓ 구간을 못 맞춘 표본은 그 사실을 산출에 싣는다 (TOC02 — 평균 4.3행)",
     _rep02[0]["분할_레벨_구간밖"] is True
     and all(p["meta"].get("split_level_out_of_range")
             for p in _BPX.extract(read(str(RAW / "TOC02.xlsx")))))

# **화면의 출처가 규칙이다** — 폐지된 상수(`expects.split_level`)를 읽지 않는다.
_apick = struct_map.adapter_level_picks(
    {"expects": {"heading_pattern": r"^(\d+(?:\.\d+)*)[.)]?\s+", "content_column": "A"}},
    _raw01)
show("③ⓑ 어댑터 경로의 화면도 규칙이 고른 레벨을 낸다 (「상수 없음」이 아니다)",
     _apick and _apick[0]["분할_레벨"] == 1
     and "구간" in _apick[0]["분할_레벨_사유"], str(_apick[0]["분할_레벨"]))

# **표를 이 어댑터에 넣으면 제안이 서지 않는다** — 시트당 1청크는 분할이 아니라 실패다.
show("③ 격자 포맷이라고 무조건 제안하지 않는다 (표는 거부 — 산출로 판정한다)",
     Rdraft.basic_adapter_proposal([str(RAW / "CP01.xlsx")]) is None
     and (Rdraft.basic_adapter_proposal([str(RAW / "TOC01.xlsx")]) or {}).get("adapter")
     == "parser/adapters/basic_prose_xlsx.py")

# ⓐⓒⓓ — 인입 2회로 실증한다. **클린에서 시작한다**(찌꺼기가 판정에 섞이지 않게).
init.init(fresh_=True)
bootstrap("process", echo=False)
_W = ROOT / "_b58_toc_wrapper.py"
_W.write_text("# -*- coding: utf-8 -*-\n"
              "from parser.adapters import basic_prose_xlsx\n"
              "ADAPTER = {**basic_prose_xlsx.ADAPTER, 'doc_type': 'toc_basic'}\n"
              "extract = basic_prose_xlsx.extract\n"
              "level_report = basic_prose_xlsx.level_report\n", encoding="utf-8")
# 내장(mock) 스키마의 자리는 픽스처 폴더다(B78 1b — 자리로 가른다). 등록 자리에
# 두면 등록부에 이름이 없어 조회가 답하지 않는다.
_S = _P.fixture_schemas("toc_basic.json")
_S.write_text(json.dumps({"doc_type": "toc_basic", "schema_version": 1,
                          "layer": "process", "payload_kind": "prose",
                          "use_blocks": ["common_core", "process_coord"],
                          "fields": {}, "edges": []}, ensure_ascii=False) + "\n",
              encoding="utf-8")
try:
    _u0 = _LLM.usage_total()["calls"]

    def _ingest_once(tag):
        for d in ("TOC01", "TOC02"):
            _o = _P.parsed() / f"{d}_{tag}.json"
            _run_parse(str(_W), d, str(RAW / f"{d}.xlsx"), str(_o))
            _CP.run_document(json.loads(_o.read_text(encoding="utf-8")))
            _o.unlink(missing_ok=True)

    _ingest_once("g1")
    _snap1 = json.dumps(store.read(store.CHUNKS, {"chunks": {}})["chunks"],
                        ensure_ascii=False, sort_keys=True)
    show("③ⓐ 인입에 LLM 호출 0회 (고정 어댑터 — 사용량 계기로 증명)",
         _LLM.usage_total()["calls"] == _u0,
         f"{_LLM.usage_total()['calls'] - _u0}회")
    _q = [x for x in store.read(store.QUEUE, []) if x["kind"] == "hierarchy_unresolved"]
    show("③ⓓ 구간 밖 표본이 **큐 1건**을 남긴다 (닫힌 20종 안 · 새 kind 0)",
         len(_q) == 1 and _q[0]["doc_id"] == "TOC02"
         and _q[0]["payload"]["case"] == "size_out_of_band",
         str([(x["doc_id"], x["payload"]["case"]) for x in _q]))
    # ④-후속 ([정정] 48 ①) — **판단 재료 넷**이 실린다. 없으면 사람이 큐 화면에서
    # 레벨을 얕게 할지 깊게 할지 정할 재료가 없다.
    _pl = _q[0]["payload"]
    show("③ⓓ size_out_of_band에 판단 재료 넷이 실린다 (레벨·평균·목표 구간·어느 쪽)",
         _pl["chosen_level"] == 1 and _pl["chosen_avg_rows"] == 4.3
         and _pl["target_band"] == [struct_map.CHUNK_MIN, struct_map.CHUNK_MAX]
         and _pl["side"] == "short",
         str({k: _pl[k] for k in ("chosen_level", "chosen_avg_rows",
                                  "target_band", "side")}))
    _ingest_once("g2")
    _snap2 = json.dumps(store.read(store.CHUNKS, {"chunks": {}})["chunks"],
                        ensure_ascii=False, sort_keys=True)
    show("③ⓒ 같은 문서 2회 인입 → 청크 바이트 동일 (멱등성 · §4.8-6)",
         _snap1 == _snap2 and len(json.loads(_snap1)) == 6,
         f"{len(json.loads(_snap1))}청크")
finally:
    _W.unlink(missing_ok=True)
    _S.unlink(missing_ok=True)
    _RG.unregister("toc_basic")


# ── B58 ④ 형태 판정 — table이냐 prose냐 (문서 1 C37) ─────────────────────
print("\n■ B58 ④ — 형태 판정: 결정적 · LLM 0")

from parser import form as _FM                                # noqa: E402
from cli import ingest as _IN                                 # noqa: E402

# ⓐ **픽스처 10건의 판정** — 명세가 문턱을 뽑은 표본 아홉 + 시트 여러 장짜리
# RFQ01(B83 · prose)이다. 문턱은 그대로고 표본만 늘었다(table 7 · prose 3).
_XL = sorted(RAW.glob("*.xlsx"))
_J = {p.name: _FM.judge(read(str(p))) for p in _XL}
show("④ⓐ xlsx 픽스처 10건이 전부 자동 판정된다 (사람에게 올라오는 것 0건)",
     len(_J) == 10 and all(j["auto"] for j in _J.values()),
     str([n for n, j in _J.items() if not j["auto"]]))
# ⓑ **판정이 고정이다** — 문턱을 건드리면 여기서 잡힌다. 이름을 적어 둔다:
#    무엇이 table이고 무엇이 prose인지가 이 기능의 계약이다.
_EXPECT = {"CP01.xlsx": "table", "CP02_drift.xlsx": "table", "CP03_bad.xlsx": "table",
           "CP04_unlabeled.xlsx": "table", "IPQC01.xlsx": "table",
           "IPQC02.xlsx": "table", "PFMEA01.xlsx": "table",
           "RFQ01.xlsx": "prose", "TOC01.xlsx": "prose", "TOC02.xlsx": "prose"}
show("④ⓑ 10건의 판정이 고정이다 — table 7 · prose 3",
     {n: j["verdict"] for n, j in _J.items()} == _EXPECT,
     str({n: j["verdict"] for n, j in _J.items() if _EXPECT[n] != j["verdict"]}))
# **결정적이다** — 같은 입력을 두 번 넣으면 같은 답이다(멱등성의 입구 · C37).
show("④ 같은 문서를 두 번 판정하면 같다 (입구의 비결정성 0 — 문서 4 §4.8-6)",
     all(_FM.judge(read(str(p))) == _J[p.name] for p in _XL))
# **LLM 0** — 모듈이 게이트웨이를 알지 못한다. 주석이 아니라 import를 본다.
_FSRC = (ROOT / "parser" / "form.py").read_text(encoding="utf-8")
show("④ 판정기가 LLM을 알지 못한다 (core.llm import 0 — C37의 금지)",
     "core" not in {l.split()[1].split(".")[0]
                    for l in _FSRC.splitlines()
                    if l.startswith(("import ", "from "))},
     str(sorted({l.split()[1].split(".")[0] for l in _FSRC.splitlines()
                 if l.startswith(("import ", "from "))})))


def _synth(cells, indent_ratio, cols):
    _ind = {}
    for _a in list(cells)[:int(round(len(cells) * indent_ratio))]:
        _ind[_a] = 1
    return {"format": "xlsx", "sheets": [{
        "name": "S", "max_row": max(int(a[1:]) for a in cells), "max_col": cols,
        "cells": cells, "merged": [], "indent": _ind, "bold": [], "images": []}]}


# ⓒ **애매 표본 — 열 4개 + indent 60% → 자동 prose.** 잠그는 것은 판정 자체가
# 아니라 **기권 구간이 사는가**다: 열 4개는 기권해야 하고, 기권은 거부권이
# 아니어야 한다. 기권 구간이 없으면 이 문서는 열 신호 하나에 table로 넘어간다.
_amb = {}
for _r in range(1, 21):
    _amb[f"A{_r}"] = (f"{_r}. 구획 제목 {_r}" if _r <= 6 else
                      f"본문 문장 {_r} — 공정 조건과 관리 인자를 서술한 긴 문단이다. " * 2)
    if _r % 4 == 1:
        _amb[f"B{_r}"], _amb[f"C{_r}"], _amb[f"D{_r}"] = f"작성 {_r}", f"2026-0{_r % 9 + 1}", f"비고{_r}"
_ja = _FM.judge(_synth(_amb, 0.60, 4))
show("④ⓒ 열 4개 + indent 60% → **자동 prose** (기권 구간이 거부권을 쓰지 않는다)",
     _ja["verdict"] == "prose" and _ja["auto"]
     and _ja["votes"]["column_count"] == _FM.ABSTAIN,
     _ja["why"])

# ⓓ **모순 표본 — 열 12개 + indent 85% → 사람.** 반대표 0 요건이 사는 자리다.
_con = {}
for _r in range(1, 21):
    for _i in range(12):
        _con[f"{chr(65 + _i)}{_r}"] = f"{chr(65 + _i)}{_r} 고유값 {_r}-{_i}"
_jc = _FM.judge(_synth(_con, 0.85, 12))
show("④ⓓ 열 12개 + indent 85% → **사람에게** (반대표 0 요건이 산다)",
     _jc["verdict"] is None and not _jc["auto"]
     and _jc["votes"]["column_count"] == _FM.TABLE
     and _jc["votes"]["indent_share"] == _FM.PROSE,
     _jc["why"])

# ⓔ **기록** — 선택 근거에 신호값이 실려 인입 기록으로 간다. 문턱 조정의 유일한 재료다.
_b = (_IN.select(str(RAW / "CP01.xlsx"), doc_type="cp") or {}).get("basis") or {}
show("④ⓔ 선택 근거에 신호값 다섯과 판정이 실린다 (인입 기록 → 문턱 조정의 재료)",
     set((_b.get("form") or {}).get("signals") or {}) == set(_FM.SIGNALS)
     and _b["form"]["verdict"] == "table" and _b["form"]["auto"] is True,
     str(sorted((_b.get("form") or {}).get("signals") or {})))
show("④ⓔ 격자 포맷만 판정한다 (.pptx·.pdf는 포맷이 prose를 함의한다)",
     _IN.form_of(str(RAW / "PPT_basic.pptx")) is None
     and _IN.form_of(str(RAW / "CP01.xlsx")) is not None)
# **문턱은 코어 상수 한 자리다** — 층 config 키 일람(19종) 밖이다(문서 3 §3.1).
show("④ 문턱이 한 자리에 있다 (층 config가 아니다 — 조정이 코드 수색이 되지 않게)",
     set(_FM.THRESHOLDS) == set(_FM.SIGNALS) and len(_FM.SIGNALS) == 5
     and not [k for k in _FM.THRESHOLDS
              if k in json.loads(_P.layers("process", "config.json")
                                 .read_text(encoding="utf-8"))])
# **판정이 사람의 지정을 이기지 않는다** — C37은 「어느 갈래로 읽는가」를 정할 뿐이다.
show("④ 판정은 선택을 갈아 끼우지 않는다 — 어긋나면 경고하고 지정대로 간다",
     _IN.select(str(RAW / "TOC01.xlsx"), doc_type="cp")["doc_type"] == "cp",
     "지정 우선")


# ── B58 ④-후속 — case 두 값과 side의 파생 ([정정] 48 ①) ────────────────
print("\n■ B58 ④-후속 — 큐 case는 닫힌 두 값 · side는 파생값")

from core.build.entry import _band_material as _BM                # noqa: E402

# **side를 박아 두면 절반의 문서에 틀린 처방이 나간다** — 짧은 쪽은 「레벨을 얕게」,
# 긴 쪽은 「깊게」로 처방이 **반대**다. 그래서 avg와 target_band에서 파생되는지를
# 양쪽 표본으로 본다: 한쪽만 보면 상수로 박아 두어도 초록이다.
_short = [{"split_level": 1, "split_level_band": [5, 40], "split_level_avg_rows": 4.3}]
_long = [{"split_level": 1, "split_level_band": [5, 40], "split_level_avg_rows": 91.0}]
show("④-후속 side가 avg·target_band에서 파생된다 (둘 다 short로 박혀 있지 않다)",
     _BM(_short)["side"] == "short" and _BM(_long)["side"] == "long",
     f"{_BM(_short)['side']} / {_BM(_long)['side']}")
# 프레임이 갈리면 **가장 멀리 벗어난 값**이 대표다 — 가장 급한 것이 머리에 온다.
_both = _short + _long
show("④-후속 프레임이 갈리면 가장 멀리 벗어난 값이 대표다",
     _BM(_both)["chosen_avg_rows"] == 91.0 and _BM(_both)["side"] == "long"
     and _BM(_both)["chosen_level"] == 1)
# 재료가 없으면 **지어내지 않는다** — None으로 남기고 화면이 그 사실을 보인다.
show("④-후속 재료가 없으면 지어내지 않는다 (side는 None)",
     _BM([{"split_level": 1}])["side"] is None
     and _BM([{"split_level": 1}])["target_band"] is None)

# **case는 닫힌 두 값이다** — 코드가 그 둘만 만든다.
import re as _re                                              # noqa: E402
# 구축 파트는 파일 넷이다(B78 2b) — **파트 전체**를 본다: 성질은 「코드가 그 둘만
# 만든다」이지 「어느 파일에 있다」가 아니다.
_CPSRC = " ".join(_p.read_text(encoding="utf-8")
                  for _p in sorted((ROOT / "core" / "build").glob("*.py")))
_cases = set(_re.findall(r'"(flat_fallback|size_out_of_band|level_out_of_range)"', _CPSRC))
show("④-후속 case는 flat_fallback · size_out_of_band 둘뿐이다 (옛 이름 0)",
     _cases == {"flat_fallback", "size_out_of_band"}, str(sorted(_cases)))

# **계층을 못 세운 문서는 flat_fallback이다** — 처방이 반대라 갈라져야 한다.
_noh = {"format": "xlsx", "sheets": [{
    "name": "S", "max_row": 4, "max_col": 1, "merged": [], "indent": {}, "bold": [],
    "images": [], "cells": {f"A{i}": f"헤딩 신호가 없는 줄 {i}" for i in range(1, 5)}}]}
_flat = _BPX.extract(_noh)
show("④-후속 계층 신호 0건 → flat_fallback 쪽 표시 (size 표시가 아니다)",
     len(_flat) == 1 and _flat[0]["meta"].get("hierarchy_unresolved") is True
     and not _flat[0]["meta"].get("split_level_out_of_range"))


# ── B62 ① 헤더 위치 — 선언 하나, 리더 하나, 대조는 시스템이 ────────────────

done()
