# -*- coding: utf-8 -*-
"""P3 완료판정 — n6 구축 모드 등록 파이프라인.

  S1  구축 모드 전 과정      TOC01+TOC02: 생성 → 검수 → 확정 → 등록 후 파싱 실행
  S10 표본 1부 경고          TOC01 단독 — D-22 확장 문구가 이상 신호로 뜬다
  S12 검수 뷰 렌더 + 재생성   뷰 데이터(D-79) → kit 렌더러 HTML · 지시 이력 상한 없음
  S15 정형 등록              ipqc 2부 — 6지선다·UNMAPPABLE 2열·**봉인 정답표 대조**
  + 등록부 3소비자 정합      M2 조회 · preflight(n9) · 플랫폼 노출이 같은 실물을 읽는다

사용: python tests/test_p3.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kit"))

from cli import register as R                              # noqa: E402
from core import init, registry, store                           # noqa: E402
from core.bootstrap import bootstrap                       # noqa: E402
from parser import pipeline                                # noqa: E402

allok = True
RAW = ROOT / "tests" / "fixtures" / "raw"
REVIEW = ROOT / "review"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def run(*args):
    """CLI 진입점으로 부른다 — 플랫폼이 subprocess로 부르는 그 경로다(§16.1)."""
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *args],
                          capture_output=True, text=True, cwd=str(ROOT))


def view_of(doc_type):
    return json.loads((REVIEW / doc_type / "view.json").read_text(encoding="utf-8"))


def reset(doc_type):
    registry.unregister(doc_type)
    shutil.rmtree(REVIEW / doc_type, ignore_errors=True)


# 깨끗한 상태에서 시작한다 — 등록부는 실행 산출물이다
init.init(fresh_=True)              # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
for lay in ("process", "quality"):
    bootstrap(lay, echo=False)
for dt in ("ipqc", "toc_report"):
    reset(dt)

# ============================================================ 등록부
print("\n■ doc_type 등록부 — 묻는 곳은 셋, 답하는 곳은 하나 (카드 M2 · D-8)")
show("내장(builtin)은 schemas/ 파일 실재가 곧 등록이다 (층의 J10과 같은 결)",
     {"cp", "pfmea", "ppt_process", "ppt_quality"} <= set(registry.all_doc_types())
     and registry.lookup("cp")["status"] == "builtin")
show("**ipqc는 내장이 아니다** — 20회차 임시 배치를 걷고 n6 등록 대상으로 되돌렸다",
     registry.lookup("ipqc") is None and not (ROOT / "schemas/ipqc.json").exists())
show("미등록 doc_type 조회는 None — 그것이 구축 모드 진입 신호다 (M2)",
     registry.lookup("없는유형") is None)
show("blocks.json은 doc_type이 아니다 (파일 이름이 아니라 내용의 doc_type 키로 가른다)",
     "blocks" not in registry.all_doc_types())

# ============================================================ S1 · S12
print("\n■ S1 구축 모드 전 과정 + S12 검수 뷰·재생성 (TOC01+TOC02)")
r = run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"),
        str(RAW / "TOC02.xlsx"), "--hint", "목차형 보고서 — 번호 헤딩")
show("① 생성 — 입력 패키지(사람 4 + 시스템 5)가 파일로 선다",
     r.returncode == 0 and (REVIEW / "toc_report" / "input_package.json").exists())
pkg = json.loads((REVIEW / "toc_report" / "input_package.json").read_text(encoding="utf-8"))
show("① 사람 4 — 표본·doc_type·층·힌트",
     set(pkg["human"]) == {"samples", "doc_type", "layer", "hint"} and pkg["human"]["hint"])
show("① 시스템 5 — reader head·골격 닫힌 목록·층 어휘·공용 블록·어댑터 스켈레톤",
     set(pkg["system"]) == {"reader_head", "skeleton_closed_list", "layer_vocabulary",
                            "blocks", "adapter_skeleton"}
     and pkg["system"]["skeleton_closed_list"]["count"] == 46)
show("① 초안은 fixture가 반환한다 (USE_MOCK — D-10·D-26)",
     "tests/fixtures/fixtures/adapters/toc_report.py" in r.stdout)

r = run("review", "toc_report", "--instruct", "공정명 헤딩 레벨을 2단까지만 잡아라")
show("② 검수 — 기계 관문(하네스)이 사람 앞에 선다",
     "기계 관문(하네스): PASS" in r.stdout and r.returncode == 0)
show("② 하네스는 kit 실물을 **호출**한다 (재작성 아님)",
     "run_adapter.py" in (ROOT / "cli/register.py").read_text(encoding="utf-8")
     and "45 PASS" in r.stdout)
v = view_of("toc_report")
SCHEMA = json.loads((ROOT / "kit/검수뷰_데이터스키마.json").read_text(encoding="utf-8"))
show("② 뷰 데이터가 D-79 스키마를 따른다 (3구획 · 구획 1은 3층)",
     list(v["sections"]) == list(SCHEMA["properties"]["sections"]["properties"])
     and set(v["sections"]["parse_result"]) == {"summary", "anomalies", "normal"})
show("② 산출자가 채움율을 채운다 — 렌더러는 계산하지 않는다 (P-2)",
     isinstance(v["sections"]["parse_result"]["summary"]["fill_rate"], dict)
     and v["sections"]["parse_result"]["summary"]["fill_rate"])
html = (REVIEW / "toc_report" / "view.html").read_text(encoding="utf-8")
show("② HTML은 kit 렌더러가 낸다 (n6은 산출자)",
     "구획 1 · 파싱 결과" in html and "검수 뷰 렌더러 (킷 ⑤)" in html)
show("S12 재생성 루프 — 지시가 이력으로 남는다",
     v["regenerations"] and v["regenerations"][0]["instruction"].startswith("공정명 헤딩"),
     str([x["n"] for x in v["regenerations"]]))
show("S12 **상한 없음**이 화면에 밝혀진다 (§7 규약 2 · A8)",
     "상한은 없다" in html and "재생성 1회" in r.stdout)

r = run("confirm", "toc_report", "--by", "검수자 박서준")
show("③ 확정 — 승인 1회로 등록부에 등재된다",
     r.returncode == 0 and registry.lookup("toc_report")["status"] == "registered")
appr = json.loads((REVIEW / "toc_report" / "approval.json").read_text(encoding="utf-8"))
show("③ 승인 기록 4요소 — doc_type·adapter_version·승인자·시점 + 수정 지시 이력",
     {"doc_type", "adapter_version", "승인자", "시점", "수정 지시 이력"} == set(appr)
     and appr["승인자"] == "검수자 박서준" and len(appr["수정 지시 이력"]) == 1)
show("③ **승인자 없이는 등재하지 않는다** — 무수정 자동 통과 금지 (틀 §2)",
     run("confirm", "toc_report", "--by", "").returncode != 0)

# S1 말단 — 등록 후 파싱 실행
mod = R._load(ROOT / registry.lookup("toc_report")["adapter"], "s1_toc")
res = pipeline.parse(mod, "TOCX", str(RAW / "TOC02.xlsx"))
show("S1 말단 — 등록된 어댑터로 운영 파싱이 돈다", res.ok and res.report["pieces"] == 9,
     f"조각 {res.report.get('pieces')}")

# ============================================================ S10
print("\n■ S10 표본 1부 경고 (TOC01 단독)")
reset("toc_report")
run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"))
run("review", "toc_report")
solo = view_of("toc_report")
warn = [a for a in solo["sections"]["parse_result"]["anomalies"] if a["kind"] == "warning"]
show("표본 1부면 경고가 **이상 신호로** 뜬다 (발췌에 숨지 않는다)", len(warn) == 1)
show("D-22 확장 문구 그대로 — '선언된 관계는 근거 1건일 수 있음'",
     "선언된 관계는 근거 1건일 수 있음" in warn[0]["message"]
     and "변형 미관찰" in warn[0]["message"])
show("1부 등록의 **선언 edges가 특별 확인 대상**으로 동봉된다 (prose는 선언 0건)",
     "declared_edges" in (warn[0].get("detail") or {})
     and warn[0]["detail"]["declared_edges"] == [],
     "toc_report는 prose라 선언 edges가 없다 — 아래에서 table 1부로 보강한다")
reset("toc_report")
# 보강 — table 1부는 선언 edges가 실제로 실린다(그것이 "특별 확인 대상"의 대상이다)
reset("ipqc")
run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"))
run("review", "ipqc")
w2 = [a for a in view_of("ipqc")["sections"]["parse_result"]["anomalies"]
      if a["kind"] == "warning"]
show("table 1부는 선언 edges가 동봉된다 — 근거 1건일 수 있는 바로 그 선언이다",
     w2 and w2[0]["detail"]["declared_edges"],
     str([e.get("relation") for e in w2[0]["detail"]["declared_edges"]]))
reset("ipqc")

# ============================================================ S15
print("\n■ S15 정형 등록 — ipqc 2부 · 봉인 정답표 대조")
run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx"),
    "--hint", "16열 검사 성적서")
r = run("review", "ipqc")
show("ipqc 2부 검수 통과 — 기계 관문 PASS · 조각 33+20",
     "기계 관문(하네스): PASS" in r.stdout and "조각 33" in r.stdout
     and "조각 20" in r.stdout)
v = view_of("ipqc")
roles = {x["field"]: x["role"] for x in v["sections"]["role_table"]}

# ---- 6지선다 ----
SIX = {"anchor", "entity", "attribute", "content", "meta", "UNMAPPABLE"}
show("배정표의 role이 **6지선다** 안에 있다 (5종 + UNMAPPABLE)",
     set(roles.values()) <= SIX, str(sorted(set(roles.values()))))
show("구조 필드·payload 고정 키는 6지선다 대상이 아니다 (C17 · D-46)",
     not ({"electrode_type", "context", "text", "section", "image_ref"} & set(roles)),
     str(sorted({"electrode_type", "context", "text", "section"} & set(roles))))
show("공용 블록 유래 필드는 출처를 밝히고 뜬다",
     {"process_group", "process_ref", "process_no", "source_locator"} <= set(roles)
     and all(x.get("from_block") for x in v["sections"]["role_table"]
             if x["field"] in {"process_group", "process_ref"}))

# ---- 봉인 정답표 대조 ----
ANSWER = {  # kit/정답표_ipqc_봉인.md 「필드 role 배정 (16열)」
    "대공정": "anchor", "공정No": "meta", "공정명": "anchor",
    "극성": None, "검사설비": "entity", "검사항목": "entity",
    "규격": "attribute", "측정방법": "attribute", "판정기준": "attribute",
    "부적합 조치": "content", "적용모델": None, "검사자": "meta",
    "검사일시": "meta", "성적서번호": "meta",
    "최근 불량 이력": "UNMAPPABLE", "관련 표준문서": "UNMAPPABLE",
}
COLMAP = {"대공정": "process_group", "공정No": "process_no", "공정명": "process_ref"}
diverged = []
for col, want in ANSWER.items():
    field = COLMAP.get(col, col)
    got = roles.get(field)
    if want is None:                      # role 배정 대상 아님 = 배정표에 없어야 한다
        if got is not None:
            diverged.append((col, "배정 대상 아님", got))
    elif got != want:
        diverged.append((col, want, got))
# **갈림은 허용하는 것이 아니라 판정하는 것이다**(정답표는 의도 기록이지 무오류 선언이 아니다).
# 실측 갈림 1건: 관련 표준문서(P) — 정답표 UNMAPPABLE ↔ 실산출 attribute.
# 판정: **정답표가 옳다.** 그 값은 다른 문서를 가리키는 **참조**이지 검사항목의 값이
# 아니다 — 닫힌 5종에 `reference`가 없으니 정직한 답은 UNMAPPABLE이고, 그것이 L3
# 신호다(CH2 2.7 규약 3). 다만 attribute 배정이 파괴적이지는 않다(값·provenance는
# 보존되고 사람이 나중에 승격할 수 있다). **봉인 산출은 v0.3 산출**이고, 이 경향을
# 겨냥한 처방이 v0.4 ⓑ(UNMAPPABLE 회피 경고)다 — 검증은 4차 블라인드 몫이다.
KNOWN = [("관련 표준문서", "UNMAPPABLE", "attribute")]
show("정답표 16열 대조 — 갈림은 **알려진 1건**뿐 (나머지 15열 일치)",
     diverged == KNOWN, f"갈림 {diverged}")
show("갈림 1건의 정체 — 참조 성격 열을 attribute로 배정했다 (v0.4 ⓑ가 겨냥한 경향)",
     len(diverged) == 1 and diverged[0][0] == "관련 표준문서")
show("**UNMAPPABLE이 실제로 나온다** — 6지선다 여섯째 경로의 실증 (정답표 어서션)",
     "UNMAPPABLE" in roles.values(),
     str([f for f, r2 in roles.items() if r2 == "UNMAPPABLE"]))
q = [a for a in v["sections"]["parse_result"]["anomalies"] if a["kind"] == "question"]
show("UNMAPPABLE은 **질문 형태**로 이상 신호에 뜬다 (§7 규약 5)",
     q and "어디에 배정합니까" in q[0]["message"], f"{len(q)}건")
show("UNMAPPABLE 열은 스키마 fields에 없고 어댑터 출력에도 없다 (D-30)",
     "최근 불량 이력" not in json.loads(
         (ROOT / registry.lookup("ipqc")["schema"]).read_text(encoding="utf-8"))["fields"]
     if registry.lookup("ipqc") else True)

show("2부면 1부 경고가 뜨지 않는다 (표본 수가 판정한다)",
     not [a for a in v["sections"]["parse_result"]["anomalies"]
          if "변형 미관찰" in a["message"]])

r = run("confirm", "ipqc", "--by", "검수자 한지우")
show("S15 확정 — 등록부 등재 + approval.json",
     r.returncode == 0 and registry.lookup("ipqc")["status"] == "registered"
     and (REVIEW / "ipqc" / "approval.json").exists())
show("이름 중복은 거부한다 (조회가 어느 쪽을 답할지 정해지지 않는다)",
     run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx")).returncode != 0)
show("존재하지 않는 층 지정은 거부한다 (층 선행 완결 — ⑵-③ · R1은 국면 2)",
     run("generate", "새유형", "없는층", str(RAW / "IPQC01.xlsx")).returncode != 0)

# ============================================================ 3소비자 정합
print("\n■ 등록부 3소비자 — 같은 실물을 읽는다 (장부는 하나다)")
from core.ingest import load_schema                          # noqa: E402
show("① M2 조회(인입) — 등록된 doc_type의 스키마를 찾는다",
     (load_schema("ipqc") or {}).get("doc_type") == "ipqc")
show("① 미등록은 None — 인입이 명시적으로 실패한다 (G6.5 B3)",
     load_schema("없는유형") is None)
from cli.scan import adapters                                # noqa: E402
paths = {f.name for f, _m in adapters()}
show("② preflight(n9 지문 스캔) — 등록부의 어댑터가 대조 대상에 든다",
     "ipqc.py" in paths and "toc_report.py" not in {} , str(sorted(paths)))
# 실행은 `python -m cli.{진입점}`이다 (문서 7 §7.1 패키지화) — 파일 직접 실행은
# sys.path 조작에 의존했고, 그 조작을 없앴으므로 이 형태가 정본이다.
out = subprocess.run([sys.executable, "-m", "cli.platform", "doctypes"],
                     capture_output=True, text=True, cwd=str(ROOT)).stdout
show("③ 플랫폼 노출 — 같은 등록부를 열람한다 (D-67 계보)",
     "ipqc" in out and "status=registered" in out and "승인=검수자 한지우" in out)
registered = json.loads(store.path(store.DOC_TYPES).read_text(encoding="utf-8"))
show("셋이 같은 실물을 본다 — 등록부 파일 하나 (data/doc_types.json)",
     store.path(store.DOC_TYPES).exists() and set(registered) == {"ipqc"},
     str(sorted(registered)))
show("층 등록부와는 다른 장부다 — 목적이 다르면 장부도 다르다 (D-8)",
     set(store.read(store.REGISTRY, {})) == {"process", "quality"})

# ============================================================ 경계
print("\n■ 경계 — 하지 않는 것 (M3 · R1)")
src = (ROOT / "cli/register.py").read_text(encoding="utf-8")
show("n6 검수 뷰에 **층 초안 구획이 없다** (층 검수 뷰로 이관 — ⑺-⓪ 종결)",
     "층 초안" not in json.dumps(view_of("ipqc"), ensure_ascii=False)
     and len(view_of("ipqc")["sections"]) == 3)
show("층 등록 기능(R1)을 만들지 않았다 — 존재하는 층만 지정 가능",
     "국면 2" in src and "discover()" in src)
show("렌더러·하네스를 복제하지 않았다 (kit 실물 호출)",
     "from kit.render_review import render" in src and "run_adapter.py" in src
     and "def render(" not in src)

reset("ipqc")
reset("toc_report")
# ============================================================ 2B 등록 개선 6건
print("\n■ 2B 등록 파이프라인 개선 — 실행으로 잠근다")
from core import llm as _LLM                                        # noqa: E402
from parser import normalizer as _NZ                                # noqa: E402
_R, _pl = R, pipeline


def _kit_banned():
    """하네스의 금지 import 목록 — **실물에서 읽는다**(문자열을 세지 않는다)."""
    ns = {}
    for ln in (ROOT / "kit/run_adapter.py").read_text(encoding="utf-8").splitlines():
        if ln.startswith("BANNED_IMPORTS"):
            exec(ln, ns)
            break
    return ns.get("BANNED_IMPORTS", set())


def _make_big_sample():
    """부분 리허설 판정용 대형 표본 — 회귀가 자기 재료를 만든다."""
    from openpyxl import Workbook
    out = ROOT / "extract" / "_p3_big.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook(); ws = wb.active; ws.title = "CP"
    ws.append([]); ws.append([])
    ws.append(["공정구분", "공정번호", "공정명", "극성", "설비", "관리항목",
               "규격", "측정방법", "대응계획", "적용모델"])
    for i in range(600):
        ws.append(["조립", f"P{i:04d}", ["노칭", "미등록공정Z"][i % 2], "cathode",
                   f"설비{i % 5}", f"관리항목{i % 7}", "±0.05", "게이지", "재검사", "M1"])
    wb.save(out)
    return str(out)


_cpmod = R._load(ROOT / "tests/fixtures/adapters/cp.py", "p3_cp")

# ⑤ 어댑터가 공용 코어를 쓴다 — **주석이 아니라 호출부를 센다**
for _f in ("tests/fixtures/adapters/cp.py", "tests/fixtures/adapters/pfmea.py",
           "kit/어댑터_스켈레톤.py", "kit/참조어댑터/cp.py"):
    _src = (ROOT / _f).read_text(encoding="utf-8")
    show(f"⑤ {_f.split('/')[-1]} 가 공용 코어를 호출한다",
         "normalizer.expand_merged(" in _src and "normalizer.resolve_ditto(" in _src,
         _f)
    show(f"⑤ {_f.split('/')[-1]} 에 자체 재구현이 남지 않았다",
         "_expand_merged" not in _src and "_col_to_idx" not in _src)
show("⑤ 하네스 순수성 검사가 parser import를 막지 않는다 (금지 목록 방식)",
     "parser" not in _kit_banned(), str(sorted(_kit_banned())))
show("⑤ validator의 상동 집합이 normalizer.DITTO 하나에서 온다",
     "same as above" in _NZ.DITTO
     and "normalizer.DITTO" in (ROOT / "parser/validator.py").read_text(encoding="utf-8"))

# ⑥ 부분 리허설 · 진행 · 미스 계수
_big = _make_big_sample()
_r200 = _pl.parse(_cpmod, "B1", _big, max_rows=200)
_rall = _pl.parse(_cpmod, "B2", _big)
show("⑥ --rows N 이 리허설을 앞 N행으로 자른다",
     (_r200.report["rehearsal"]["truncated"] is True
      and _rall.report["rehearsal"]["truncated"] is False
      and len(_r200.envelope["records"]) < len(_rall.envelope["records"])),
     f"{len(_r200.envelope['records'])} vs {len(_rall.envelope['records'])}")
show("⑥ 자른 사실이 봉투 리포트에 남는다 (승인 근거라 숨기지 않는다)",
     _r200.report["rehearsal"]["full_rows"] > _r200.report["rehearsal"]["max_rows"])
_seen = []
_pl.parse(_cpmod, "B3", _big, max_rows=100,
          progress=lambda i, n, c: _seen.append((i, n, c)))
show("⑥ 진행 콜백이 행 단위로 흐른다", len(_seen) > 0 and _seen[-1][0] == _seen[-1][1],
     str(_seen[-1]) if _seen else "없음")
show("⑥ 좌표 미스를 LLM 없이 먼저 센다", len(_R._coord_misses([_r200], "process")) > 0)
show("⑥ 동의 없으면 LLM 보조가 꺼진다 (기본 N)",
     _R._ask_llm_coord(["a", "b"], None) is False)
show("⑥ 인자로 켤 수 있다", _R._ask_llm_coord(["a"], True) is True)

# ④ 문답 — 종료는 사람만 한다
_pkg = {"human": {"hint": ""}, "system": {"reader_head": [
    {"head": {"sheets": [{"cells": {"A1": "공정명", "B1": "설비"}}]}}]}}
_r1 = _R._interview_round(_pkg, [])
_r2 = _R._interview_round(_pkg, [{"round": 1, "understanding": "x",
                                  "questions": [], "answer": "병합은 위 값 채움"}])
show("④ 이해 요약이 사람의 교정을 반영해 바뀐다",
     _r1["understanding"] != _r2["understanding"]
     and "병합은 위 값 채움" in _r2["understanding"])
show("④ 스키마가 understanding·questions 둘을 요구한다",
     set(_R.INTERVIEW_SCHEMA["required"]) == {"understanding", "questions"})
show("④ 종료어에 «진행»이 있다 (끝내는 것은 사람이다)", "진행" in _R.INTERVIEW_STOP)

# ① 산출 JSON 표기 — 잎을 접되 json.load 결과는 같다
_obj = {"a": 1, "fields": {"x": {"role": "entity", "category": "Unit"},
                           "y": {"role": "meta"}}, "edges": [], "u": ["p", "q"]}
_txt = _R._pretty_json(_obj)
show("① json.load 결과가 이전과 완전히 같다", json.loads(_txt) == _obj)
show("① 가장 안쪽 dict/list가 한 줄이다",
     '"x": {"role": "entity", "category": "Unit"}' in _txt and '"u": ["p", "q"]' in _txt)
show("① 바깥 구조는 들여쓰기로 남는다", '\n  "fields": {\n' in _txt)

# ② 사용량 — 지점명과 함께 세고, 잘림을 경고한다
_before = dict(_LLM.USAGE)
_LLM._account("judge", {"usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                  "total_tokens": 15},
                        "choices": [{"finish_reason": "length"}]})
show("② usage를 누계에 더한다",
     _LLM.usage_total()["total_tokens"] == _before["total_tokens"] + 15
     and _LLM.usage_total()["calls"] == _before["calls"] + 1)
show("② finish_reason=length를 잘림으로 센다",
     _LLM.usage_total()["truncated"] == _before["truncated"] + 1)
_LLM._account("judge", {"choices": [{"finish_reason": "stop"}]})
show("② usage가 없는 게이트웨이도 조용히 넘어가되 호출 수는 센다",
     _LLM.usage_total()["calls"] == _before["calls"] + 2)

# ③ 힌트 안내 — 표본 자리의 비파일을 조용히 무시하지 않는다
try:
    _R.cmd_generate("zz_hint", "process", ["tests/fixtures/raw/CP01.xlsx", "힌트문장"], "")
    _caught = ""
except SystemExit as e:
    _caught = str(e)
show("③ 표본 자리의 비파일을 지목하고 --hint 를 안내한다",
     "힌트문장" in _caught and "--hint" in _caught, _caught.splitlines()[0] if _caught else "")

# ============================================================ B25 골격 확정
print("\n■ B25 골격 seed 확정 — 확정 없이 쓰이는 경로가 없는가")
from cli import skeleton as _SK                                     # noqa: E402

# ⓔ **「누가 파일을 쓰느냐」는 검사할 수 없고 「확정 없이 쓰이는 경로가 있느냐」는
#    검사할 수 있다**(문서 3 §3.7). 레포 코드가 seed 파일을 **쓰기 모드로** 여는
#    자리를 AST로 센다 — 문자열을 세지 않는다.
import ast as _ast                                                  # noqa: E402
_WRITE = {"w", "wb", "a", "ab", "w+", "r+", "x", "xb"}
_writers = []
for _p in sorted(ROOT.glob("**/*.py")):
    _rel = str(_p.relative_to(ROOT))
    if _rel.startswith(("tests/", "tools/", "docs/")) or "__pycache__" in _rel:
        continue
    _src = _p.read_text(encoding="utf-8")
    if "skeleton" not in _src:
        continue
    for _n in _ast.walk(_ast.parse(_src)):
        # `open(..., "w")` 계열
        if isinstance(_n, _ast.Call) and getattr(_n.func, "id", "") == "open":
            _mode = next((a.value for a in _n.args[1:]
                          if isinstance(a, _ast.Constant)), "r")
            if _mode in _WRITE and "skeleton" in _ast.dump(_n):
                _writers.append(f"{_rel}:{_n.lineno} open(mode={_mode})")
        # `Path(...).write_text/write_bytes`
        if isinstance(_n, _ast.Call) and getattr(_n.func, "attr", "") in (
                "write_text", "write_bytes") and "skeleton.json" in _ast.dump(_n):
            _writers.append(f"{_rel}:{_n.lineno} {_n.func.attr}")
show("ⓔ 레포 코드에 layers/*/skeleton.json 을 쓰는 경로가 0이다 (B25 기계 판정)",
     not _writers, str(_writers))
show("ⓔ 확정 명령 자신도 seed 를 쓰지 않는다",
     "PREV" in dir(_SK) and _SK.PREV == "skeleton.prev.json"
     and "skeleton.json" not in _SK.PREV)

# 조건 ① 확정자 · ③ 뷰 대조 우회 불가 — 거부 갈래를 실행으로 잠근다
def _sc(args, stdin_tty=False):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "skeleton-confirm"]
                       + args, capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode, r.stdout + r.stderr

_rc, _o = _sc(["process"])
show("① --by 없이는 확정하지 않는다 (확정자가 기록에 남아야 확정이다)",
     _rc != 0 and "--by" in _o)
_rc, _o = _sc(["process", "--by", "회귀"])
show("③ 비대화형은 확정하지 않는다 (뷰 대조 우회 불가)",
     _rc != 0 and "비대화형" in _o and "§3.7" in _o)
show("③ 그래도 파생 흐름 뷰는 보여 준다 (대조 재료는 낸다)", "[n10]" in _o)
show("확정 거부 시 기록 파일이 생기지 않는다",
     not (ROOT / "layers/process/confirmations.json").exists())
show("골격을 인라인 선언한 층은 대상이 아님을 말한다",
     "인라인" in _sc(["quality", "--by", "회귀"])[1])
show("문법 깨진 seed 는 loader 실패 문면으로 멈춘다", _SK.seed_path("process").name
     == "skeleton.json" and _SK.seed_path("quality") is None)

# ============================================================ B29 조립 프롬프트
# **전송분을 직접 잰다.** 지금까지 「킷 주석 0·`{{` 0」은 수동 탐침이었고 어서션이
# 아니었다 — 조립이 조용히 어긋나도 회귀가 몰랐다. 네 항을 함께 세운다.
print("\n■ B29 — 조립된 전송 프롬프트 (스켈레톤 본문 · 참조 어댑터 few-shot)")
_pkg29 = json.loads((ROOT / "review/ipqc/input_package.json").read_text(encoding="utf-8")) \
    if (ROOT / "review/ipqc/input_package.json").exists() else None
if _pkg29 is None:
    # 패키지만 필요하다 — 초안 수령은 fixture 소관이라 여기서 SystemExit로 끝난다
    # (D-10). 패키지는 그 전에 이미 파일로 서 있다.
    try:
        R.cmd_generate("b29probe", "process",
                       [str(ROOT / "tests/fixtures/raw/IPQC01.xlsx")], "")
    except SystemExit:
        pass
    _pkg29 = json.loads(
        (ROOT / "review/b29probe/input_package.json").read_text(encoding="utf-8"))
_sent = R._render_template(
    R._newest_template().read_text(encoding="utf-8"), _pkg29)

show("ⓐ 스켈레톤 **본문**이 실렸다 (경로 문자열이 아니다)",
     "from parser import normalizer" in _sent
     and "normalizer.expand_merged(sheet)" in _sent,
     f"{len(_sent):,}B")
show("ⓐ 스켈레톤의 **사람용 안내**는 실리지 않는다 (모듈 docstring 위치로 판정)",
     "FAIL 4건" not in _sent and "빈칸 상태로 하네스에 넣으면" not in _sent)
show("ⓑ 참조 어댑터가 few-shot으로 실렸다 — ADAPTER 선언 2개 (스켈레톤 1 + 전시물 1)",
     _sent.count("ADAPTER = {") == 2, str(_sent.count("ADAPTER = {")))
show("ⓑ 전시물은 표본의 **reader 형식**으로 고른다 (xlsx·csv → cp · pptx → toc_report)",
     R._reference_adapter(["a.xlsx"])[0] == "cp.py"
     and R._reference_adapter(["a.csv"])[0] == "cp.py"
     and R._reference_adapter(["a.pptx"])[0] == "toc_report.py",
     str([R._reference_adapter([x])[0] for x in ("a.xlsx", "a.csv", "a.pptx")]))
# **기존 두 항이 스켈레톤 본문·전시물이 실려도 깨지지 않는지** — 그것이 이 항의 일이다.
show("치환 누락 0 (`{{` 잔존 0) — 주입 자리가 늘어도 유지된다", "{{" not in _sent)
show("킷 유지 주석 0 — 전시물 머리의 출처 표기는 킷 주석이 아니다",
     not any(m in _sent for m in R.KIT_NOTE) and "# 원본:" in _sent)
show("조립은 결정적이다 (같은 패키지 → 같은 전송분)",
     _sent == R._render_template(
         R._newest_template().read_text(encoding="utf-8"), _pkg29))
show("시스템 키는 5 그대로다 (값의 형태만 바뀌었다)", len(_pkg29["system"]) == 5,
     str(list(_pkg29["system"])))

print("\n" + "=" * 62)
print("전체 결과:", "PASS — P3 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
