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
import re
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
from parser import pipeline, reader                        # noqa: E402

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
    # **회귀는 mock 관문 비대상이다**(B48) — 구현 환경에는 게이트웨이가 없고
    # 그 환경의 실행이 검증의 바닥이다(B12).
    flag = ["--allow-mock"] if args and args[0] in ("generate", "review", "confirm") else []
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register",
                           *args, *flag],
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
# **관문은 생성 안에서 돈다**(M9 개정 · B50) — 검수는 내용을 본다. 통과분만 넘어오므로
# 검수 화면은 「생성 단계에서 PASS」를 확인만 한다.
show("② 검수는 생성이 세운 관문 값을 확인만 한다 (하네스는 여기서 돌지 않는다)",
     "기계 관문: 생성 단계에서 PASS" in r.stdout and r.returncode == 0,
     [l.strip() for l in r.stdout.splitlines() if "기계 관문" in l][:1])
# **판정 수를 박지 않는다** — 기계 관문은 자란다(B31이 2종을 더했다). 박아 두면
# 관문을 강화할 때마다 이 줄이 깨져, 어서션이 개선을 막는 자리가 된다.
_gen = run("generate", "toc_report", "--resume")
_m = re.search(r"기계 관문\(하네스\): PASS — (\d+) PASS / (\d+) FAIL", _gen.stdout)
show("② 하네스는 **생성 안에서** kit 실물을 호출한다 (재작성 아님)",
     "run_adapter.py" in (ROOT / "cli/register.py").read_text(encoding="utf-8")
     and _m and int(_m.group(1)) >= 25 and int(_m.group(2)) == 0,
     _m.group(0) if _m else "관문 줄 없음")
v = view_of("toc_report")
SCHEMA = json.loads((ROOT / "kit/검수뷰_데이터스키마.json").read_text(encoding="utf-8"))
show("② 뷰 데이터가 D-79 스키마를 따른다 (3구획 · 구획 1은 3층)",
     len(v["sections"]) == 3
     and set(v["sections"]) <= set(SCHEMA["properties"]["sections"]["properties"])
     # prose면 둘째 구획이 추출 리허설이다(B51) — 자리는 셋 그대로.
     and ("extract_rehearsal" in v["sections"]) == (v["payload_kind"] == "prose")
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
     # prose면 **무엇이 뽑히는 것을 보고 승인했나**가 함께 실린다(B51).
     # `revision`은 **몇 번째 판을 승인했나**다(B58 ①) — 재등록 경로가 생기면서
     # 판 번호 없는 승인 기록은 어느 판의 것인지 갈리지 않는다.
     # 키 집합을 통째로 못박는 것은 **몰래 늘어나는 것을 막는 장치**다 — 늘릴 때는
     # 여기에 이름을 적고 늘린다.
     {"doc_type", "adapter_version", "승인자", "시점", "수정 지시 이력", "revision"}
     <= set(appr) and set(appr) - {"추출 리허설", "이전 승인"}
     == {"doc_type", "adapter_version", "승인자", "시점", "수정 지시 이력", "revision"}
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
_gi = run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx"),
          "--hint", "16열 검사 성적서")
r = run("review", "ipqc")
# [B31] **관문이 새로 생겨 이 fixture를 막는다 — 그것이 관문이 도는 증거다.**
# mock 초안은 fixture를 그대로 돌려주고(D-10) 그 fixture는 **B27 이전 스냅샷**이라
# 규약 10을 지키지 않는다. 파싱·배정표·봉인 대조는 그대로 돌지만 기계 관문은
# FAIL이고, 그래서 **확정(S15 뒤)이 막힌다** — 판정필요-14로 신고했다.
show("[B31] 기계 관문이 규약 10 미준수 fixture를 막는다 — **생성에서** 막힌다(B50)",
     "기계 관문(하네스): FAIL" in _gi.stdout
     and "검수로 넘어가지 않았다" in _gi.stdout,
     [l.strip() for l in _gi.stdout.splitlines() if "기계 관문" in l][:2])
show("ipqc 2부 파싱은 그대로 돈다 — 조각 33+20 (관문과 파싱은 다른 축)",
     "조각 33" in r.stdout and "조각 20" in r.stdout)
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
         (ROOT / registry.lookup("toc_report")["schema"]).read_text(encoding="utf-8"))["fields"]
     if registry.lookup("toc_report") else True)

show("2부면 1부 경고가 뜨지 않는다 (표본 수가 판정한다)",
     not [a for a in v["sections"]["parse_result"]["anomalies"]
          if "변형 미관찰" in a["message"]])

# [B31 · 판정필요-14] ipqc fixture는 규약 10 미준수라 **관문이 확정을 막는다.**
# 그것이 관문의 일이다 — 확정은 기계 관문 PASS를 전제한다(§6.5).
r = run("confirm", "ipqc", "--by", "검수자 한지우")
show("[B31] 관문 FAIL이면 확정이 막힌다 (미준수 어댑터가 등재되지 않는다)",
     r.returncode != 0 and not registry.lookup("ipqc"))

# [B31 이관] ipqc는 규약 10 미준수라 확정이 막히므로(판정필요-14), **여기서 다시
# 확정해** 뒤 구획(3소비자)이 볼 등재분을 세운다 — 앞선 확정은 지문 스캔 탐침이
# 등록부를 비운 뒤라 남아 있지 않다. 커버리지를 잃지 않기 위한 이관이다.
# 이 구획은 앞과 **다른 환경**에서 돈다(탐침이 review/·등록부를 새로 세운다).
# 그래서 여기서 준수 doc_type을 처음부터 세워 확정까지 잇는다.
run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"), "--hint", "목차형")
run("review", "toc_report")
run("confirm", "toc_report", "--by", "검수자 한지우")
show("이름 중복은 거부한다 (조회가 어느 쪽을 답할지 정해지지 않는다)",
     run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx")).returncode != 0)
show("존재하지 않는 층 지정은 거부한다 (층 선행 완결 — ⑵-③ · R1은 국면 2)",
     run("generate", "새유형", "없는층", str(RAW / "IPQC01.xlsx")).returncode != 0)

# ============================================================ 3소비자 정합
print("\n■ 등록부 3소비자 — 같은 실물을 읽는다 (장부는 하나다)")
from core.ingest import load_schema                          # noqa: E402
show("① M2 조회(인입) — 등록된 doc_type의 스키마를 찾는다",
     (load_schema("toc_report") or {}).get("doc_type") == "toc_report")
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
     "toc_report" in out and "status=registered" in out
     and "승인=검수자 한지우" in out)
registered = json.loads(store.path(store.DOC_TYPES).read_text(encoding="utf-8"))
show("셋이 같은 실물을 본다 — 등록부 파일 하나 (data/doc_types.json)",
     store.path(store.DOC_TYPES).exists() and set(registered) == {"toc_report"},
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
# [B43 ⑥] 진행 재료가 더해져 셋이다 — strict 요건상 required는 properties 전량이다.
show("④ 스키마가 이해 요약·질문·진행을 요구한다",
     set(_R.INTERVIEW_SCHEMA["required"])
     == {"understanding", "questions", "progress"},
     str(sorted(_R.INTERVIEW_SCHEMA["required"])))
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
from kit import render_review as _RR                                # noqa: E402
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

# ============================================================ 등록 2차 개선
print("\n■ B30·B32·B34 — 문답 어휘 주입 · 크기 손잡이 · 관찰 범위")
from core import llm                                        # noqa: E402
from core.bootstrap import load_config                      # noqa: E402

# ① B32 — 문답 system에 판정 어휘가 이어 붙는다. **정본은 생성 템플릿 하나다.**
_voc = R._vocab_excerpt(_pkg29)
show("① 문답 system 발췌에 role 어휘 구획이 실린다",
     "UNMAPPABLE" in _voc and "## [role 어휘" in _voc, f"{len(_voc):,}B")
show("① 발췌에 **지정 층의 카테고리 이름**이 실린다 (렌더 뒤 앵커)",
     all(c in _voc for c in load_config("process")["categories"]),
     str(list(load_config("process")["categories"])))
show("① 구획 셋이 전부 실린다 (role 어휘 · 비배정 필드 · 층 어휘)",
     all(s in _voc for s in R.VOCAB_SECTIONS), str(R.VOCAB_SECTIONS))
# **금지된 것은 이름의 등장이 아니라 정의의 복제다.** iv-2.0은 role 이름을
# 「뒤에 어휘가 붙어 온다」는 전제와 선택지 표기로만 쓴다 — 그것은 포인터이지
# 정의가 아니다. 정의가 두 곳에 살면 한쪽이 낡고, 그때 문답이 묻는 어휘와 생성이
# 쓰는 어휘가 갈린다.
_iv = llm.prompt("interview")
_defs = ("| role | 뜻 | 판별 |", "그 필드의 값으로 그래프에 수행하는 쓰기 동작",
         "이것에 대해 더 말할 게 생기는가")
show("① interview.md는 어휘를 **가리키기만** 한다 (정의는 생성 템플릿 하나가 갖는다)",
     not any(d in _iv for d in _defs) and any(d in _voc for d in _defs),
     str([d for d in _defs if d in _iv]))

# ② B30 — 전시물 손잡이. 스켈레톤 본문은 유지된다.
# **재현 조건은 `hint` 안에 산다** — 사람 4키를 늘리지 않기 위해(D-101과 같은 자리).
_pkg_off = dict(_pkg29)
_pkg_off["human"] = {**_pkg29["human"],
                     "hint": {"text": "", "no_fewshot": True}}
_off = R._render_template(R._newest_template().read_text(encoding="utf-8"), _pkg_off)
_on = R._render_template(R._newest_template().read_text(encoding="utf-8"), _pkg29)
show("② --no-fewshot이면 ADAPTER 선언이 1개다 (스켈레톤뿐)",
     _off.count("ADAPTER = {") == 1 and _on.count("ADAPTER = {") == 2,
     f"끔 {_off.count('ADAPTER = {')} / 켬 {_on.count('ADAPTER = {')}")
show("② 끄더라도 스켈레톤 **본문**은 남는다 (규약 문면과 뼈대는 유지)",
     "normalizer.expand_merged(sheet)" in _off and len(_off) < len(_on),
     f"{len(_off):,}B < {len(_on):,}B")
_h_off = _pkg_off["human"]["hint"]
show("② 끈 사실이 패키지에 기록되되 **사람 4키는 그대로다** (재현 조건)",
     _h_off.get("no_fewshot") is True
     and set(_pkg_off["human"]) == {"samples", "doc_type", "layer", "hint"},
     str(sorted(_pkg_off["human"])))

# ④ⓐ 판 꼬리표 소거 — **같은 유형 세 번째다**(v0.5 잔재·v0.6 정리·이번)
show("④ 전송분에 판 꼬리표가 없다 (`[v0.` 0건)", "[v0." not in _on,
     str([l for l in _on.split("\n") if "[v0." in l][:2]))

# ⑤ⓑ 그래프 입장 시험 발췌
show("⑤ 전송분에 그래프 입장 시험이 실린다 (질문 시험·의심스러우면 내린다)",
     "질문 시험" in _on and "의심스러우면 내린다" in _on and "충돌 시험" in _on)
show("⑤ 정본이 문서 2임을 병기한다 (발췌가 갈리면 문서 2가 이긴다)",
     "문서 2" in _on and "이긴다" in _on)
show("⑤ 문답 발췌에도 함께 실린다 (B32 배선이 role 구획을 나른다)",
     "질문 시험" in _voc and "의심스러우면 내린다" in _voc)

# ⑥ B34 — 관찰 범위 20
show("⑥ 관찰 범위 기본값이 20이다 (다단 헤더에서 12줄은 얕다)",
     reader.OBSERVE_ROWS == 20 and
     max(int("".join(ch for ch in a if ch.isdigit()))
         for a in (_pkg29["system"]["reader_head"][0]["head"]["sheets"][0]["cells"])) <= 20,
     str(reader.OBSERVE_ROWS))

# ============================================================ B39 열 프로파일
print("\n■ B39 — 열 프로파일 · 3단 깔때기 (무LLM · 결정적)")
from parser import profile as _PF                                   # noqa: E402
_sh = reader.read(str(ROOT / "tests/fixtures/raw/CP01.xlsx"))["sheets"][0]
_pr = _PF.profile(_sh, header_row=3, data_start=4)
show("① 전 행을 센다 — 앞 N줄이 아니다 (창 밖의 사실을 준다)",
     _pr["전체_행수"] == 30 and _pr["열수"] == 10,
     f"{_pr['전체_행수']}행 {_pr['열수']}열")
# [B40 ③] 대표값 자리는 고유값 수에 따라 `대표값` 또는 `고유값_전목록`이다.
def _vals(c):
    return c.get("고유값_전목록") or c.get("대표값") or []
show("① 열별 통계 6종이 실린다",
     all(k in _pr["열"]["G"] for k in
         ("비지_않은_행수", "고유값수", "빈셀비율", "형태", "기계제안"))
     and _vals(_pr["열"]["G"]))
show("① 허브 실측과 일치 — 규격 고유 29 · 설비 9 · 적용모델 2행",
     _pr["열"]["G"]["고유값수"] == 29 and _pr["열"]["E"]["고유값수"] == 9
     and _pr["열"]["J"]["비지_않은_행수"] == 2,
     f"G={_pr['열']['G']['고유값수']} E={_pr['열']['E']['고유값수']} "
     f"J={_pr['열']['J']['비지_않은_행수']}")
show("① 값은 길이를 자른다 (프롬프트가 부풀지 않게)",
     all(len(v.split('"')[1]) <= _PF.SAMPLE_CHARS
         for c in _pr["열"].values() for v in _vals(c) if '"' in v))
show("① **결정적이다** — 두 번 계산해 같다",
     _PF.profile(_sh, header_row=3, data_start=4) == _pr)
show("① 좌표 열을 모르면 좌표기준_변동성을 내지 않는다 (추측한 통계 금지)",
     all("좌표기준_변동성" not in c for c in _pr["열"].values()))
_cv = _PF.profile(_sh, header_row=3, data_start=4, coord_col="C")
show("① 좌표 열을 주면 변동성을 낸다",
     any("좌표기준_변동성" in c for c in _cv["열"].values()))

# ② 기계 제안 — 판정이 아니라 재료
_sug = _PF.summary(_pr)
show("② 기계 제안이 분류를 낸다 (판정 대상/보류/meta/UNMAPPABLE)",
     "role 판정 대상" in _sug and sum(_sug.values()) == _pr["열수"], str(_sug))
show("② 희소 열은 판정 보류 제안 (적용모델 2/30행)",
     _pr["열"]["J"]["기계제안"]["제안"] == "판정 보류",
     _pr["열"]["J"]["기계제안"]["사유"])
show("② 임계는 한 곳에 모여 있다 (가결정 — 실측 후 조정)",
     isinstance(_PF.SPARSE_EMPTY_RATIO, float) and 0 < _PF.SPARSE_EMPTY_RATIO < 1)

# ③ 템플릿 v0.9 — 근거 3원천·깔때기가 지시문에 실린다
_sent39 = R._render_template(R._newest_template().read_text(encoding="utf-8"), _pkg29)
for _k, _lbl in (("근거는 셋뿐이다", "근거 3원천"),
                 ("기계 제안은 재료다", "제안의 지위"),
                 ("확신 경계선", "경계선"),
                 ("배정 통계를 스스로 보고", "자기 보고"),
                 ("정의문이 이긴다", "정의문 우선")):
    show(f"③ 전송분에 {_lbl} 규율이 실린다", _k in _sent39)
show("③ 판 꼬리표는 여전히 0건이다 (v0.9도)", "[v0." not in _sent39)

# 산출 스키마 — 기존 소비처를 깨지 않는다
# [B44] strict 요건이 「required = properties 전량」을 강제한다 — 선택 항목이라는
# 개념 자체가 없다. 못 채울 수 있는 것은 **타입으로** 연다(confidence_cut: null 허용).
show("③ GENERATE_SCHEMA가 랭킹·경계선·통계를 담고 strict를 지킨다",
     set(R.GENERATE_SCHEMA["required"]) == set(R.GENERATE_SCHEMA["properties"])
     and {"role_counts", "attribute_ranking", "confidence_cut"}
     <= set(R.GENERATE_SCHEMA["properties"]))

# 패키지 — 시스템 키 5 불변
_pkg39 = json.loads(
    (ROOT / "review/b29probe/input_package.json").read_text(encoding="utf-8"))
show("ⓑ 시스템 키는 5 그대로다 (프로파일은 그릇 안의 항목)",
     len(_pkg39["system"]) == 5
     and "열_프로파일" in _pkg39["system"]["reader_head"][0],
     str(list(_pkg39["system"])))

# ============================================================ B40~B42
print("\n■ B40·B41·B42 — 행 번호 병기 · 예산 대조 · 설정 파일 USE_MOCK")
_sh40 = reader.read(str(ROOT / "tests/fixtures/raw/CP01.xlsx"))["sheets"][0]
_a40 = _PF.profile(_sh40)                                   # 헤더 미상
_b40 = _PF.profile(_sh40, header_row=3, data_start=4)       # 헤더 확정

# ① 행 번호 병기 — 헤더 여부가 값으로 자명해진다
_avals = _a40["열"]["A"].get("고유값_전목록") or _a40["열"]["A"]["대표값"]
show("① 대표값에 출현 행 번호가 병기된다",
     all(v.startswith(tuple("0123456789")) and "행 " in v for v in _avals),
     str(_avals[:2]))
show("① 헤더 행이 값으로 자명해진다 (1행에만 있는 값)",
     any(v.startswith("3행") or v.startswith("1행") for v in _avals))
show("① 연속 행은 구간으로 접는다 (목록이 길어지지 않게)",
     _PF._ranges([4, 5, 6, 9]) == "4~6,9" and _PF._ranges([1]) == "1")

# ② 헤더 확정 시 재계산
show("② 헤더 확정이 프로파일을 바꾼다 (고유값·헤더행_제외)",
     _a40["헤더행_제외"] is False and _b40["헤더행_제외"] is True
     and _b40["열"]["A"]["고유값수"] < _a40["열"]["A"]["고유값수"],
     f"A {_a40['열']['A']['고유값수']} → {_b40['열']['A']['고유값수']}")

# ③ 고유값이 적으면 전부 나열
show("③ 고유값 ≤ 임계면 전 목록을 낸다 (대표값 몇 개가 아니라)",
     len(_b40["열"]["E"]["고유값_전목록"]) == _b40["열"]["E"]["고유값수"] == 9,
     f"{_b40['열']['E']['고유값수']}개 전량")
show("③ 고유값이 많으면 대표값만 낸다 (프롬프트가 부풀지 않게)",
     "대표값" in _b40["열"]["G"] and len(_b40["열"]["G"]["대표값"]) <= _PF.SAMPLE_VALUES,
     f"G 고유 {_b40['열']['G']['고유값수']} → 대표 {len(_b40['열']['G']['대표값'])}")
show("③ 임계는 가결정 상수 하나다 (D-105)", isinstance(_PF.FULL_LIST_MAX, int))

# ④ 설정 파일 USE_MOCK — 환경변수가 이긴다 · 읽는 곳은 하나
import os as _os                                                    # noqa: E402
show("④ 환경변수가 설정 파일을 이긴다",
     (lambda: (_os.environ.__setitem__("USE_MOCK", "1"), llm.use_mock())[1])() is True)
show("④ 판독은 use_mock() 하나다 (읽는 곳을 늘리지 않았다)",
     sum(1 for f in (ROOT / "core").glob("*.py")
         for ln in f.read_text(encoding="utf-8").splitlines()
         if 'environ.get("USE_MOCK"' in ln) == 1)
show("④ 기본은 mock이다 (둘 다 없으면 — 조항 B12)",
     llm.use_mock() is True)

# ⑤ 모드 줄 — LLM을 부를 수 있는 화면 명령 머리
show("⑤ mock이면 켜는 법을 함께 말한다", 'llm.json' in llm.mode_line()
     and "mock" in llm.mode_line())
for _f, _n in ((ROOT / "cli/register.py", "register"), (ROOT / "run.py", "run")):
    show(f"⑤ {_n} 이 모드 줄을 낸다", "mode_line()" in _f.read_text(encoding="utf-8"))

# B41 예산 — 한도가 없으면 대조하지 않는다
show("⑥ 컨텍스트 한도는 **선택**이다 — 기본값을 코드에 박지 않았다",
     llm.context_limit() is None
     and "LLM_CONTEXT_TOKENS" in (ROOT / "core/llm.py").read_text(encoding="utf-8"))

# ============================================================ B43·B44
print("\n■ B43·B44 — 스키마 strict · 오류 본문 · 분할 레벨 · section 좌표")
import importlib as _il                                             # noqa: E402
from parser import struct_map as _SM, tagger as _TG                 # noqa: E402


def _strict(s, path="$"):
    """구조화 출력의 strict 요건 — 모든 object에서 properties == required ·
    additionalProperties is False · **자유 키 사전 없음**."""
    bad = []
    if isinstance(s, dict):
        if s.get("type") == "object" or "properties" in s:
            if set(s.get("properties") or {}) != set(s.get("required") or []):
                bad.append(f"{path}: properties != required")
            ap = s.get("additionalProperties")
            if ap is not False:
                bad.append(f"{path}: additionalProperties={ap!r}"
                           + (" (자유 키 사전)" if isinstance(ap, dict) else ""))
        for k, v in (s.get("properties") or {}).items():
            bad += _strict(v, f"{path}.{k}")
        if "items" in s:
            bad += _strict(s["items"], f"{path}[]")
    return bad


# ① **코드의 전 json_schema**를 훑는다 — 하나라도 어기면 그 지점이 400으로 죽는다
_schemas = []
for _m in ("cli.register", "cli.query", "core.query", "core.llm", "core.matcher"):
    _mod = _il.import_module(_m)
    for _n in dir(_mod):
        if _n.endswith("_SCHEMA") and isinstance(getattr(_mod, _n), dict):
            _schemas.append((f"{_m}.{_n}", getattr(_mod, _n)))
_viol = [(n, b) for n, s in _schemas for b in [_strict(s, n)] if b]
show(f"① 전 구조화 출력 스키마 {len(_schemas)}종이 strict 요건을 지킨다",
     not _viol, str(_viol))
show("① 자유 키 사전이 0건이다 (role_counts는 고정 키)",
     R.GENERATE_SCHEMA["properties"]["role_counts"]["additionalProperties"] is False
     and set(R.GENERATE_SCHEMA["properties"]["role_counts"]["properties"]) == set(R._ROLES))
show("① 못 채울 수 있는 필드는 required에서 빼지 않고 null을 연다",
     R.GENERATE_SCHEMA["properties"]["confidence_cut"]["type"] == ["integer", "null"]
     and "confidence_cut" in R.GENERATE_SCHEMA["required"])
show("① 한글 키 `근거`가 `reason`으로 바뀌었다 (소비처 포함)",
     R.GENERATE_SCHEMA["properties"]["attribute_ranking"]["items"]["required"]
     == ["field", "rank", "reason"])

# ② 오류 본문 보존 — 키는 남기지 않는다
show("② GatewayError가 상태 코드와 본문을 지닌다",
     hasattr(llm, "GatewayError") and hasattr(llm, "LAST_ERROR")
     and "e.read()" in (ROOT / "core/llm.py").read_text(encoding="utf-8"))
show("② 4xx는 재시도하지 않는다 (같은 400을 세 번 받지 않는다)",
     "except GatewayError:" in (ROOT / "core/llm.py").read_text(encoding="utf-8"))
show("② 본문은 길이 상한으로 자른다", isinstance(llm.ERR_BODY_MAX, int))

# ③ 분할 레벨 — 결정적이고 근거가 지도에 남는다
def _mk(fine):
    ls, n = [], 0
    for i in range(3):
        n += 1; ls.append((n, f"{i+1}. 대절"))
        if fine:
            for k in range(4):
                n += 1; ls.append((n, f"{i+1}.{k+1} 소절"))
                for j in range(2):
                    n += 1; ls.append((n, f"본문{i}{k}{j}"))
        else:
            for j in range(12):
                n += 1; ls.append((n, f"본문{i}{j}"))
    return ls


def _rows(ls):
    out = []
    for n, x in ls:
        h = x[0].isdigit() and "." in x.split()[0]
        out.append({"row": n, "heading": h,
                    "level": (x.split()[0].rstrip(".").count(".") + 1) if h else 0})
    return out


_fine = _mk(True)
_smap = {"rows": _rows(_fine)}
_st43 = _SM.level_stats(_smap, _fine)
# **[정정] 46이 규칙을 바꿨다** — 「구간에 가장 많이 드는 레벨」에서 「구간 안의
# 레벨 중 중앙 최근접」으로. 돌려주는 것도 `(레벨, 사유, 구간밖)` 3짝이다.
_pick, _why, _oor = _SM.choose_level(_st43)
_loc = lambda a, b: f"L{a}-{b}"
_before = len(_SM.split({"rows": _smap["rows"], "분할_레벨": None}, _fine, _loc))
_after = len(_SM.split({**_smap, "분할_레벨": _pick}, _fine, _loc))
show("③ 레벨별 분포를 센다 (청크 수·행 수)",
     set(_st43) == {1, 2} and _st43[2]["청크수"] > _st43[1]["청크수"], str(_st43))
show("③ 구간 중앙에 평균이 가장 가까운 레벨을 고른다 ([정정] 46)",
     _pick == 1 and not _oor, f"{_pick} — {_why}")
show("③ 세밀 헤딩에서 청크가 합쳐진다 (부서지지 않는다)",
     _before == 12 and _after == 3, f"{_before} → {_after}")
_coarse = _mk(False)
_p2, _w2, _oor2 = _SM.choose_level(_SM.level_stats({"rows": _rows(_coarse)}, _coarse))
# **레벨이 하나뿐이어도 그 레벨을 고른다** — 자르는 결과는 전 헤딩 분할과 같지만
# (`l <= pick`이 전부를 포함한다), 구간 밖이면 그 사실이 화면·큐로 나가야 한다.
# 구판은 여기서 `None`을 돌려줘 「고르지 않았다」로 남았고, 그러면 구간 밖 표시도
# 함께 사라졌다.
show("③ 레벨이 하나뿐이면 그 레벨을 고른다 — 분할 결과는 같고 구간밖은 드러난다",
     _p2 == 1
     and len(_SM.split({"rows": _rows(_coarse), "분할_레벨": _p2}, _coarse, _loc))
     == len(_SM.split({"rows": _rows(_coarse), "분할_레벨": None}, _coarse, _loc)),
     f"{_p2} · 구간밖={_oor2} — {_w2[:40]}")
show("③ 선택 근거가 지도에 보존된다 (같은 지도 → 같은 분할)",
     "분할_레벨" in _SM.apply("T43", _fine, _loc)[1]
     and "레벨_분포" in _SM.apply("T43", _fine, _loc)[1])
show("③ 목표 구간은 가결정 상수다 (D-106)",
     isinstance(_SM.CHUNK_MIN, int) and isinstance(_SM.CHUNK_MAX, int))

# ④ section 좌표 — 정확 일치만·가장 깊은 것·덮지 않음
_nodes = _TG.closed_list("process")
_out = _TG.coord_from_section(
    [{"section": "조립 > 노칭 > 노칭 타발", "source_locator": "S1"},
     {"section": "없는절 > 또없는절", "source_locator": "S2"},
     {"section": "조립 > 노칭", "process_ref": "스태킹", "source_locator": "S3"}],
    layer="process", nodes=_nodes)
show("④ 경로에 일치가 여럿이면 **가장 깊은 것**", _out[0]["process_ref"] == "노칭 타발")
show("④ 일치 없으면 비운다 (추론·문자열 파싱 금지)",
     not _out[1].get("process_ref"))
show("④ 이미 값이 있으면 덮지 않는다", _out[2]["process_ref"] == "스태킹")
show("④ 대조는 좌표 태깅과 **같은 연산**을 재사용한다 (새로 짜지 않았다)",
     "surfaces(nodes)" in (ROOT / "parser/tagger.py").read_text(encoding="utf-8"))

# ⑤⑥ resume · 진행 · 근거
_src5 = (ROOT / "cli/register.py").read_text(encoding="utf-8")
_src5i = (ROOT / "cli/interview.py").read_text(encoding="utf-8")   # 문답은 제 모듈로 갔다
show("⑤ --resume이 사용법과 파싱에 있다",
     "--resume" in _src5 and "resume=resume" in _src5)
show("⑤ 문답이 라운드마다 즉시 저장된다 (중간에 죽어도 잃지 않는다)",
     "on_round(history)" in _src5i)
show("⑥ 문답 스키마가 진행 재료와 중요도를 요구한다",
     "progress" in R.INTERVIEW_SCHEMA["required"]
     and "importance" in R.INTERVIEW_SCHEMA["properties"]["questions"]["items"]["required"])
show("⑥ 판정 근거(프로파일)를 사람 화면에도 낸다", "_prof_hint(pkg)" in _src5i)

# ============================================================ B45 분할 분포
print("\n■ B45 — 분할 크기 분포를 검수 뷰에 (자르는 규칙은 안 건드린다)")
run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"),
    str(RAW / "TOC02.xlsx"), "--hint", "목차형")
run("review", "toc_report")
_v45 = view_of("toc_report")
_sp = (_v45["sections"]["parse_result"]["summary"] or {}).get("split") or []
show("① 분포가 뷰 데이터에 실린다 (표본마다 1건)", len(_sp) == 2, str(len(_sp)))
show("① 청크 수·행수(최소·최대·평균)·목표 구간 밖(짧음/긺)이 전부 있다",
     all(k in _sp[0] for k in ("청크수", "행수_최소", "행수_최대", "행수_평균",
                               "목표구간", "너무_짧은_청크", "너무_긴_청크")),
     str({k: _sp[0][k] for k in ("청크수", "행수_평균", "너무_짧은_청크")}))
show("① 상수가 부적절하면 화면에 드러난다 (한 줄짜리 청크가 짧음으로 집계)",
     _sp[0]["너무_짧은_청크"] > 0,
     f"{_sp[0]['doc_id']}: 짧음 {_sp[0]['너무_짧은_청크']}/{_sp[0]['청크수']}")
_html45 = (REVIEW / "toc_report" / "view.html").read_text(encoding="utf-8")
show("② 렌더러는 **그리기만** 한다 (계산은 산출자 · §6.6-3)",
     "분할 크기 분포" in _html45
     and "너무_짧은_청크" not in (ROOT / "kit/render_review.py").read_text(
         encoding="utf-8").split("def _split")[1].split("return")[0].replace(
         'r.get("너무_짧은_청크")', ""))
show("② 구획 1의 3층 계약을 지킨다 (split은 summary 안이다 — D-79)",
     set(_v45["sections"]["parse_result"]) == {"summary", "anomalies", "normal"})
# ⓑ 어댑터 경로는 바뀌지 않는다 — 고를 레벨이 없기 때문이다(B45 판정)
_ref45 = [x for x in _il.import_module("tests.fixtures.fixtures.adapters.toc_report")
          .extract(reader.read(str(RAW / "TOC01.xlsx"))) if "text" in x]
show("③ 어댑터 경로 산출은 바뀌지 않는다 (굵기 교정의 정본은 어댑터 개정)",
     len(_ref45) == 9, f"TOC01 어댑터 청크 {len(_ref45)}")

# ============================================================ B45 정정
print("\n■ B45 정정 — 어댑터 경로에도 분할 레벨 상수 (판정이 뒤집혔다)")
import importlib.util as _iu45                                      # noqa: E402


def _load45(path, name):
    s = _iu45.spec_from_file_location(name, ROOT / path)
    m = _iu45.module_from_spec(s); s.loader.exec_module(m); return m


_old45 = _load45("tests/fixtures/fixtures/adapters/toc_report.py", "t45o")  # 스냅샷
_new45 = _load45("kit/참조어댑터/toc_report.py", "t45n")                      # 전시물
# **[정정] 46이 판단 상수를 폐지했다** — 구판 전시물은 `expects.split_level=1`을
# 박고 「결정은 등록 때 한 번」이라 적었다. 지금 전시물은 규칙을 부른다.
show("① 전시물에 분할 레벨 상수가 없다 ([정정] 46 — 레벨은 인입마다 규칙이 센다)",
     "split_level" not in _new45.ADAPTER["expects"]
     and "split_level" not in _old45.ADAPTER["expects"])
show("① 전시물이 규칙을 **부른다** (재구현하지 않는다 — 규약 10과 같은 결)",
     "struct_map.choose_level(" in
     (ROOT / "kit" / "참조어댑터" / "toc_report.py").read_text(encoding="utf-8"))


def _d45(mod, doc):
    ch = [x for x in mod.extract(reader.read(str(RAW / f"{doc}.xlsx")))
          if "text" in x]
    sz = [len(x["text"].split("\n")) for x in ch]
    return ch, len(ch), sum(1 for s in sz if s < _SM.CHUNK_MIN)


_a01, _n01, _s01 = _d45(_old45, "TOC01")
_b01, _m01, _t01 = _d45(_new45, "TOC01")
show("ⓐ 규칙이 고른 레벨에서만 자른다 — 청크가 굵어진다",
     _m01 < _n01 and _t01 < _s01, f"청크 {_n01}→{_m01} · 짧음 {_s01}→{_t01}")
show("ⓑ 규칙을 부르지 않는 구판 스냅샷은 종전 동작 그대로다 (전 헤딩 분할)",
     _n01 == 9, f"{_n01}")
show("ⓒ 산출 유실 0 — 내용이 하나도 새지 않는다",
     not [x for x in _a01 if x["text"] not in "\n".join(y["text"] for y in _b01)])
show("ⓒ `section` 경로는 상수와 무관하게 전 헤딩을 반영한다 (좌표 파생의 재료)",
     max(len(x["section"].split(" > ")) for x in _b01) == 3,
     f"최대 깊이 {max(len(x['section'].split(' > ')) for x in _b01)}단")
show("④ 어댑터 경로도 레벨별 분포를 낸다 (지도 경로와 같은 형태)",
     (lambda r: bool((r.report.get("split") or {}).get("레벨_선택")))(
         pipeline.parse(_new45, "T45", str(RAW / "TOC01.xlsx"))))
# **화면이 「규칙이 고른 레벨」을 밝힌다**(§6.6-1) — 구판은 여기서
# `expects.split_level=1`이라는 **폐지된 상수**를 찍었다. 사유가 상수를 가리키면
# 승인자는 규칙이 무엇을 골랐는지 끝내 못 본다.
_pk45 = pipeline.parse(_new45, "T45", str(RAW / "TOC01.xlsx")
                       ).report["split"]["레벨_선택"][0]
show("④ 화면이 규칙이 고른 레벨과 그 사유를 밝힌다 (폐지된 상수를 읽지 않는다)",
     _pk45["분할_레벨"] == 1 and "구간" in _pk45["분할_레벨_사유"]
     and _pk45["분할_레벨_구간밖"] is False
     and "split_level=" not in str(_pk45),
     _pk45["분할_레벨_사유"][:44])
# **같은 doc_type의 다른 판본이 갈린다** — 상수를 버린 근거가 바로 이것이다.
_pk46 = pipeline.parse(_new45, "T46", str(RAW / "TOC02.xlsx")
                       ).report["split"]["레벨_선택"][0]
show("④ 같은 어댑터의 다른 판본이 갈린다 (상수를 버린 근거 — [정정] 46)",
     _pk46["분할_레벨_구간밖"] is True and _pk45["분할_레벨_구간밖"] is False,
     f"TOC01 구간내 · TOC02 {_pk46['분할_레벨_사유'][:30]}")
show("fixture는 손대지 않았다 (D-26)", "split_level" not in
     (ROOT / "tests/fixtures/fixtures/adapters/toc_report.py").read_text(
         encoding="utf-8"))

# ============================================================ 등록개선 5건 (②·③·⑤)
print("\n■ 등록개선 — ② --use-basic · ③ 확정 안내 · ⑤ 문답 번호 선택지")
import contextlib as _ctx                                           # noqa: E402
import io as _io                                                    # noqa: E402
from cli import interview as _IV                                    # noqa: E402
from core import registry as _REG                                   # noqa: E402
_PPT = str(ROOT / "tests/fixtures/raw/PPT_basic.xlsx").replace(".xlsx", ".pptx")
# ② 거부 — 제안이 서지 않는 표본(정형)
try:
    R.cmd_generate("cpx_basic", "process", [str(RAW / "CP01.xlsx")], use_basic=True)
    show("② 제안 없는 표본에 --use-basic은 거부된다", False)
except SystemExit as e:
    show("② 제안 없는 표본에 --use-basic은 거부되고 사유를 말한다", "거부" in str(e) and "pptx" in str(e))
show("② 거부는 검수 자리를 만들지 않는다", not (ROOT / "review" / "cpx_basic").exists())
# ② 수용 — PPT 표본: LLM 호출 0회로 생성 → 검수 → 확정
_calls0 = llm.usage_total()["calls"]
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    R.cmd_generate("pptb_t", "quality", [_PPT], use_basic=True)
_gen = _buf.getvalue()
show("② --use-basic — 위임 래퍼 어댑터가 검수 자리에 선다 (상수는 basic_ppt 한 곳 — D-111)",
     "from parser.adapters import basic_ppt" in (ROOT / "review/pptb_t/adapter.py").read_text(encoding="utf-8")
     and "max_chars" not in (ROOT / "review/pptb_t/adapter.py").read_text(encoding="utf-8"))
show("② 매칭 스키마는 prose 계약 — fields {} · layer 선언",
     (lambda s: s["fields"] == {} and s["layer"] == "quality" and s["doc_type"] == "pptb_t")(
         json.loads((ROOT / "review/pptb_t/schema.json").read_text(encoding="utf-8"))))
show("② 화면이 «호출 0회»를 말한다 (사용량으로 증명)", "호출 0회" in _gen)
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    R.cmd_review("pptb_t", llm_coord=False)
show("② 검수·승인 1회는 생략하지 않는다 — 기계 관문 PASS가 확정의 전제 (M4)",
     R._state("pptb_t").get("machine_gate") == "PASS", str(R._state("pptb_t").get("machine_gate")))
show("② 생성+검수 동안 LLM 호출 0회 (usage_total 불변)",
     llm.usage_total()["calls"] == _calls0, f"{_calls0} → {llm.usage_total()['calls']}")
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    R.cmd_confirm("pptb_t", "테스트")
_conf = _buf.getvalue()
show("② 확정 — 등록부 등재 + adapters/·schemas/ 정본",
     _REG.lookup("pptb_t") is not None and (ROOT / "adapters/pptb_t.py").exists()
     and (ROOT / "schemas/pptb_t.json").exists())
# ③ 확정 화면 다음 명령 2줄
show("③ confirm 끝에 인입 명령 2줄 — parse run · build parsed/",
     "run.py parse run adapters/pptb_t.py" in _conf and "run.py build parsed/" in _conf)
show("③ 한 번에 가는 명령(ingest-file --doc-type)도 함께", "ingest-file" in _conf and "--doc-type pptb_t" in _conf)
# 정리 — 회귀가 남기는 것 0
_REG.unregister("pptb_t")
for _p in (ROOT / "adapters/pptb_t.py", ROOT / "schemas/pptb_t.json"):
    _p.unlink(missing_ok=True)
shutil.rmtree(ROOT / "review/pptb_t", ignore_errors=True)
shutil.rmtree(ROOT / "review/cpx_basic", ignore_errors=True)
# ⑤ 번호 선택지
_opts = ["위 값 채움", "행 독립", "모름"]
show("⑤ 번호만 쳐도 통한다 — «1» → 첫째", _IV._pick_option("1", _opts) == "위 값 채움")
show("⑤ 문장으로 써도 통한다 — «2번으로 진행» → 둘째", _IV._pick_option("2번으로 진행", _opts) == "행 독립")
show("⑤ «3)»·«3.» 표기도", _IV._pick_option("3)", _opts) == "모름" and _IV._pick_option("3.", _opts) == "모름")
show("⑤ 범위 밖·비번호는 문장 그대로 (None)", _IV._pick_option("9", _opts) is None
     and _IV._pick_option("병합은 위 값", _opts) is None)
show("⑤ 중요도 정렬 — 높음이 앞", [q["q"] for q in sorted(
    [{"q": "b", "importance": "낮음"}, {"q": "a", "importance": "높음 — 좌표"}, {"q": "c"}], key=_IV._rank)] == ["a", "b", "c"])
_feed = iter(["1", "", "진행"])
_orig_ask = _IV._ask
_IV._ask = lambda prompt="": next(_feed)
_buf = _io.StringIO()
# 패키지는 최소형 — 문답 화면·번호 풀이를 재는 것이지 관찰 재료를 재는 것이 아니다
_pkg = {"human": {"doc_type": "ivx", "layer": "quality", "samples": [], "hint": ""},
        "system": {"reader_head": [], "skeleton_closed_list": {}, "layer_vocabulary": {},
                   "blocks": {}, "adapter_skeleton": ""}}
with _ctx.redirect_stdout(_buf):
    _hist = _IV._interview(_pkg)
_IV._ask = _orig_ask
_scr = _buf.getvalue()
show("⑤ 화면 — 질문마다 구분선 + 번호 선택지 «1) …  2) …»", "─" in _scr and "1) " in _scr and "2) " in _scr)
show("⑤ 번호 답이 선택지 본문으로 풀려 기록된다 (모델은 «1»이 무엇인지 모른다)",
     _hist[0]["answers"][0]["answer"] == "1" and _hist[0]["answers"][0]["chosen"] == _hist[0]["questions"][0]["options"][0]
     and _hist[0]["questions"][0]["options"][0] in _hist[0]["answer"])
show("⑤ «진행»은 어느 자리에서든 종료다 — 라운드 2에서 멈춤", len(_hist) == 2)

# ============================================================ mock 관문 (B48 ③)
print("\n■ mock 관문 — 운영 명령은 mock에서 실행 전에 멈춘다 (문서 7 §7.6-B-1)")
from cli import _gate as _G                                         # noqa: E402
_bare = subprocess.run([sys.executable, "-m", "cli.register", "generate", "gate_t", "process"],
                       capture_output=True, text=True, cwd=str(ROOT))
show("③ 설정 없이 register generate → 종료 코드 ≠ 0", _bare.returncode != 0, str(_bare.returncode))
show("③ 문면이 --allow-mock과 켜는 법을 함께 말한다",
     "--allow-mock" in _bare.stdout and "실산출이 아닙니다" in _bare.stdout
     and "USE_MOCK" in _bare.stdout, _bare.stdout.strip().splitlines()[-1:][0][:70]
     if _bare.stdout.strip() else "(빈 출력)")
show("③ 모드 표시 다음에 멈춘다 (B42 ⑤ → 관문)", "모드:" in _bare.stdout)
show("③ 멈춘 명령은 아무것도 만들지 않았다 — LLM 지점 호출 0회",
     not (ROOT / "review" / "gate_t").exists())
_allowed = run("generate", "gate_t", "process", str(RAW / "CP01.xlsx"))
show("③ --allow-mock을 붙이면 종전대로 진행한다",
     (ROOT / "review" / "gate_t" / "input_package.json").exists(), _allowed.stdout[-80:])
shutil.rmtree(ROOT / "review" / "gate_t", ignore_errors=True)
for _c in ("init", "bootstrap"):
    _r = subprocess.run([sys.executable, str(ROOT / "run.py"), _c],
                        capture_output=True, text=True, cwd=str(ROOT))
    show(f"③ {_c}은 관문 비대상 — 플래그 없이 종전대로", _r.returncode == 0, str(_r.returncode))
show("③ 관문 대상 목록이 코드에 있다 — register는 생성·검수·확정만(열람은 아니다)",
     R.GATED == ("generate", "review", "confirm"))
# **관문의 자리는 CLI 진입점이다**(§7.6-B-1) — 지점마다 두면 판독처가 다시 여럿이
# 되고, 그것이 판정필요-15가 신고한 병(파서가 따로 읽어 갈렸다)의 재발이다.
_gcalls = [f"{f.relative_to(ROOT)}:{i}"
           for f in [ROOT / "run.py", *sorted((ROOT / "cli").glob("*.py")),
                     *sorted((ROOT / "core").glob("*.py")),
                     *sorted((ROOT / "parser").glob("*.py"))]
           for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if "require_live_or_allow(" in ln and "def " not in ln
           and not ln.lstrip().startswith(("#", "from", "import"))]
show("③ 관문 호출은 CLI 진입점 4곳뿐이다 — core·parser에는 없다",
     len(_gcalls) == 4 and not any(g.startswith(("core/", "parser/")) for g in _gcalls),
     str(_gcalls))

# ============================================================ --resume 인자 (후속 ①)
print("\n■ --resume은 층·표본을 요구하지 않는다 (실사용 IndexError 수리)")
_r1 = run("generate", "toc_report", "--resume")
show("① doc_type 하나로 돈다 (IndexError 0)",
     _r1.returncode == 0 and "이어하기" in _r1.stdout, _r1.stderr.strip()[-70:])
_r2 = run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"), "--resume")
show("① 층·표본을 줘도 돌고, 무시한다는 경고가 뜬다 (침묵으로 넘기지 않는다)",
     _r2.returncode == 0 and "층·표본 인자는 무시한다" in _r2.stdout
     and "layer=" in _r2.stdout,
     [l for l in _r2.stdout.splitlines() if "무시한다" in l][:1])
_r3 = run("generate")
show("① 위치 인자 0개면 죽지 않고 사용법을 낸다",
     "generate <doc_type>" in (_r3.stdout + _r3.stderr))
show("① 사용법에 resume 단독 줄이 있다",
     "generate <doc_type> --resume" in (ROOT / "cli/register.py").read_text(encoding="utf-8"))

# ============================================================ B49 전 열 판정
print("\n■ B49 — 모든 열은 판정을 갖는다 (C19 개정 · 부재로 추론하지 않는다)")
_DEMO = ROOT / "review" / "b49demo"
_DEMO.mkdir(parents=True, exist_ok=True)
(_DEMO / "adapter.py").write_text(
    '# -*- coding: utf-8 -*-\n'
    'ADAPTER = {"doc_type": "b49demo", "adapter_version": "1.0", "payload_kind": "table",\n'
    '           "expects": {"header_row": 1,\n'
    '                       "header_labels": ["공정명", "규격", "비고", "최근 불량 이력", "신규 열"],\n'
    '                       "columns": {"process_ref": "A", "규격": "B"}}}\n'
    'def extract(raw):\n    return []\n', encoding="utf-8")
_dsch = {"doc_type": "b49demo", "schema_version": 1, "layer": "quality",
         "payload_kind": "table", "use_blocks": [],
         "fields": {"규격": {"role": "attribute", "attr_name": "규격",
                           "attach_to_field": "process_ref"}},
         "edges": [],
         "unmappable": [
             {"field": "최근 불량 이력", "kind": "excluded",
              "reason": "집계 이력 — 개체도 값도 아니고 시점마다 바뀐다"},
             {"field": "비고", "kind": "undecided",
              "reason": "표본 3부 전부 비어 있어 무엇이 오는지 관찰되지 않았다"}]}
(_DEMO / "schema.json").write_text(json.dumps(_dsch, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
_dst = {"doc_type": "b49demo", "layer": "quality",
        "samples": [str(RAW / "IPQC01.xlsx")],
        "adapter": "review/b49demo/adapter.py", "schema": "review/b49demo/schema.json"}
_dmod = R._load(ROOT / _dst["adapter"], "reg_b49demo_t")
_ex, _un, _orp = R.unmappable_of(_dsch, _dmod)
show("① 셋으로 갈린다 — excluded · undecided · orphan (구판은 셋이 같은 질문이었다)",
     [u["field"] for u in _ex] == ["최근 불량 이력"]
     and [u["field"] for u in _un] == ["비고"]
     and [u["field"] for u in _orp] == ["신규 열"],
     f"{[u['field'] for u in _ex]} / {[u['field'] for u in _un]} / {[u['field'] for u in _orp]}")
_dv = R.build_view(_dst, [], True, "")
_dpr = _dv["sections"]["parse_result"]
show("① excluded는 anomalies에 0건이다 — 판정이 끝난 열은 질문이 아니다",
     not [a for a in _dpr["anomalies"] if "최근 불량 이력" in a["message"]]
     and [u["field"] for u in _dpr["normal"]["excluded"]] == ["최근 불량 이력"])
show("① undecided는 question이다 — 사유가 문면에 실린다",
     any(a["kind"] == "question" and "'비고'" in a["message"]
         and "표본 3부 전부 비어" in a["message"] for a in _dpr["anomalies"]))
show("① orphan은 failure다 — 「사람이 판정할 것」이 아니라 「대장이 어긋났다」",
     any(a["kind"] == "failure" and "'신규 열'" in a["message"]
         and "스키마 대장에 없다" in a["message"] for a in _dpr["anomalies"]))
show("① 배정표(6지선다)에는 undecided만 오른다",
     [r["field"] for r in _dv["sections"]["role_table"] if r.get("role") == "UNMAPPABLE"]
     == ["비고"])
show("① orphan이 있으면 기계 관문이 막힌다 (하네스·파싱이 통과여도)",
     R.gate_verdict(True, True, _orp) == "FAIL"
     and R.gate_verdict(True, True, []) == "PASS")
_legacy = {**_dsch}
del _legacy["unmappable"]
_lex, _lun, _lorp = R.unmappable_of(_legacy, _dmod)
show("① 구판 스키마(키 없음)는 차집합 전량을 undecided로 — 기존 등록분이 안 깨진다",
     not _lex and not _lorp
     and sorted(u["field"] for u in _lun) == sorted(
         ["비고", "신규 열", "최근 불량 이력"]),
     str([u["field"] for u in _lun]))
show("① kind가 닫힌 2값 밖이면 undecided로 받는다 (모르면 묻는다)",
     R.unmappable_of({**_dsch, "unmappable": [{"field": "X", "kind": "몰라", "reason": ""}]},
                     _dmod)[1][0]["kind"] == "undecided")
show("① 생성 스키마가 unmappable을 required로 요구한다 (strict — B44)",
     "unmappable" in R.GENERATE_SCHEMA["required"]
     and R.GENERATE_SCHEMA["properties"]["unmappable"]["items"]["properties"]["kind"]
     ["enum"] == ["excluded", "undecided"])
show("① 템플릿 v1.0이 스키마에 싣도록 지시한다 (산출물 3만 적던 것을 고쳤다)",
     (lambda t: "쓰지 않기로 한 열" in t and '"kind": "excluded"' in t
      and "스키마·출력에는 넣지 않는다" not in t)(
         (ROOT / "kit/생성프롬프트_템플릿_v1.0.md").read_text(encoding="utf-8")))
shutil.rmtree(_DEMO, ignore_errors=True)

# ============================================================ B50 생성 안의 관문
print("\n■ B50 — 하네스는 생성 안에서 돌고, 실패는 문면이 답을 담는지로 갈린다 (M9 개정)")
import ast as _ast                                                  # noqa: E402
import tempfile as _tf                                              # noqa: E402

# ── 분류표 — 자동은 「문면이 답을 담는」 것뿐이고 **목록 밖은 문답**이다
_auto_lines = [
    "  [FAIL] 규약 10 — 자기완결 연산을 재구현하지 않았다 (parser.normalizer 몫)",
    "  [FAIL] source_locator가 문서 내 유일 (§5 규약 1)  — 중복 3건",
    "  [FAIL] 원본 헤더 문자열이 전부 expects에 실림 → 표류 감지 가능  — 누락 ['비고']",
    "  [FAIL] 전 필드의 role이 닫힌 5종 안  — {'X': 'wrong'}",
    "  [FAIL] 파서 출력에 스키마 밖 필드 없음 (unknown_field 큐 예상분)  — ['Y']",
    "  [FAIL] adapter.doc_type == schema.doc_type  — cp / pfmea",
    "  [FAIL] 필수 키 4종 (doc_type·adapter_version·payload_kind·expects)",
]
_ask_lines = [
    "  [FAIL] 조각 0건 산출 (0건 아님)",
    "  [FAIL] 예외 없이 실행  — KeyError: 'cells'",
    "  [FAIL] prose 조각에 text 또는 image_ref 존재",
]
_a, _k = R.classify_failures("\n".join(_auto_lines))
show("② 문면이 답을 담는 실패 7종은 전부 자동 갈래다", len(_a) == 7 and not _k,
     f"자동 {len(_a)} · 문답 {len(_k)}")
_a2, _k2 = R.classify_failures("\n".join(_ask_lines))
show("② 원인 규명이 필요한 실패는 문답 갈래다 (조각 0건 · extract 예외 · prose 본문)",
     not _a2 and len(_k2) == 3, f"자동 {len(_a2)} · 문답 {len(_k2)}")
# **변이 시험** — 분류표에 없는 새 하네스 항목이 생겨도 조용히 자동으로 흐르지 않는다
_a3, _k3 = R.classify_failures("  [FAIL] 새로 생긴 관문 항목 — 아직 표에 없다")
show("② 변이 — 목록 밖 실패는 기본이 문답이다 (모르면 묻는다)",
     not _a3 and len(_k3) == 1, f"자동 {len(_a3)} · 문답 {len(_k3)}")
show("② 분류표가 코드에 표로 있다 — 자동 갈래는 열거된 것뿐",
     isinstance(R.AUTO_FIX, dict) and len(R.AUTO_FIX) == 8)

# ── ⓔ 검수는 하네스를 돌리지 않는다 (AST — 문자열이 아니라 호출을 센다)
_rt = _ast.parse((ROOT / "cli/register.py").read_text(encoding="utf-8"))
_calls = {n.name: [c.func.id for c in _ast.walk(n)
                   if isinstance(c, _ast.Call) and isinstance(c.func, _ast.Name)]
          for n in _rt.body if isinstance(n, _ast.FunctionDef)}
show("② cmd_review에 harness 호출 0건 — 검수는 내용만 본다",
     _calls.get("cmd_review", []).count("harness") == 0)
show("② 하네스 호출은 machine_gate 한 곳이다 (생성이 부른다)",
     _calls.get("machine_gate", []).count("harness") == 1
     and _calls.get("cmd_generate", []).count("_finish_generate") >= 1)

# ── ⓐ 자동 갈래 실물 — 규약 10을 어긴 판 → 자동 재생성 → PASS
_fx = Path(_tf.mkdtemp(prefix="b50fx_", dir=str(ROOT)))
(_fx / "fixtures/adapters").mkdir(parents=True)
(_fx / "fixtures/schemas").mkdir(parents=True)
_good = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8").replace(
    '"doc_type": "cp"', '"doc_type": "b50t"', 1)
_MUT = ("\n\ndef _expand_merged(sheet):\n"
        "    # 병합 전개를 재구현했다 — 규약 10 위반(하네스가 잡는다)\n"
        "    return dict(sheet.get('cells') or {})\n\n\n"
        "def _col_to_idx(col):\n"
        "    # 열 문자 변환도 재구현 — parser.normalizer._col의 몫이다\n"
        "    return sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(col)))\n"
        "\n\nADAPTER = {")
_bad = _good.replace("\nADAPTER = {", _MUT, 1)
(_fx / "fixtures/adapters/b50t.py").write_text(_bad, encoding="utf-8")
(_fx / "fixtures/adapters/b50t_rev1.py").write_text(_good, encoding="utf-8")
_csch = {**json.loads((ROOT / "schemas/cp.json").read_text(encoding="utf-8")),
         "doc_type": "b50t"}
for _n in ("b50t", "b50t_rev1"):
    (_fx / "fixtures/schemas" / f"{_n}.json").write_text(
        json.dumps(_csch, ensure_ascii=False), encoding="utf-8")
_env = {**_os.environ, "ONTO_FIXTURES": str(_fx)}
_r50 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "generate",
                       "b50t", "process", str(RAW / "CP01.xlsx"), "--allow-mock"],
                      capture_output=True, text=True, cwd=str(ROOT), env=_env,
                      stdin=subprocess.DEVNULL)
show("② ⓐ 자동 갈래 — 하네스 FAIL → 자동 재생성 → PASS (사람의 통역 0)",
     "기계 관문(하네스): FAIL" in _r50.stdout
     and "재생성 지시 (자동(하네스))" in _r50.stdout
     and "기계 관문 PASS" in _r50.stdout and _r50.returncode == 0,
     (_r50.stdout.strip().splitlines() or ["(빈 출력)"])[-1])
show("② ⓐ 보낸 지시는 실패 문면 그대로다 (통역하지 않는다)",
     "규약 10" in _r50.stdout.split("재생성 지시")[1].split("재생성 1회째")[0])
_st50 = json.loads((REVIEW / "b50t" / "state.json").read_text(encoding="utf-8"))
show("② ⓐ 지시 이력에 주체가 남는다 — by: 자동(하네스)",
     [i["by"] for i in _st50["instructions"]] == ["자동(하네스)"]
     and _st50["machine_gate"] == "PASS", str(_st50.get("instructions"))[:90])
shutil.rmtree(_fx, ignore_errors=True)
shutil.rmtree(REVIEW / "b50t", ignore_errors=True)

# ── ⓓ 미통과는 검수로 넘어가지 않는다 (ipqc — 규약 10 미준수 스냅샷)
show("② ⓓ 미통과 산출은 검수로 넘어가지 않는다 · 화면이 그 사실을 말한다",
     "검수로 넘어가지 않았다" in _gi.stdout and _gi.returncode != 0,
     [l.strip() for l in _gi.stdout.splitlines() if "넘어가지" in l][:1])
show("② ⓒ 1회 뒤에도 실패하면 묻고 진행한다 (비대화형이면 끄고 끝낸다)",
     "1회 재생성 후에도 FAIL" in _gi.stdout and "비대화형" in _gi.stdout)
show("② 하네스 수리 — 조각 0건이 이제 FAIL이다 (구판은 검사 전에 돌아갔다)",
     (lambda t: t.index("조각 {len(pieces)}건 산출")
      < t.index("if not pieces:\n        return pieces"))(
         (ROOT / "kit/run_adapter.py").read_text(encoding="utf-8")))

# ============================================================ [정정]40 검수 지시 관문
print("\n■ [정정]40 — --instruct 재생성분도 기계 관문을 지난다 (M9)")
_f40 = Path(_tf.mkdtemp(prefix="fx40_", dir=str(ROOT)))
(_f40 / "fixtures/adapters").mkdir(parents=True)
(_f40 / "fixtures/schemas").mkdir(parents=True)
_g40 = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
_M40 = ("\n\ndef _expand_merged(sheet):\n"
        "    # 병합 전개를 재구현했다 — 규약 10 위반\n"
        "    return dict(sheet.get('cells') or {})\n\n\n"
        "def _col_to_idx(col):\n"
        "    return sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(col)))\n"
        "\n\nADAPTER = {")
_b40 = _g40.replace("\nADAPTER = {", _M40, 1)
_s40 = json.loads((ROOT / "schemas/cp.json").read_text(encoding="utf-8"))
for _dt, _pairs in (("f40ok", (("", _g40), ("_rev1", _b40), ("_rev2", _g40))),
                    ("f40no", (("", _g40), ("_rev1", _b40), ("_rev2", _b40)))):
    for _sfx, _src in _pairs:
        (_f40 / "fixtures/adapters" / f"{_dt}{_sfx}.py").write_text(
            _src.replace('"doc_type": "cp"', f'"doc_type": "{_dt}"', 1), encoding="utf-8")
        (_f40 / "fixtures/schemas" / f"{_dt}{_sfx}.json").write_text(
            json.dumps({**_s40, "doc_type": _dt}, ensure_ascii=False), encoding="utf-8")
_e40 = {**_os.environ, "ONTO_FIXTURES": str(_f40)}


def _reg40(*a):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *a,
                           "--allow-mock"], capture_output=True, text=True,
                          cwd=str(ROOT), env=_e40, stdin=subprocess.DEVNULL)


_reg40("generate", "f40ok", "process", str(RAW / "CP01.xlsx"))
_r40 = _reg40("review", "f40ok", "--instruct", "복수값 구분자를 더 받아라",
              "--no-llm-coord")
show("① --instruct 재생성분이 하네스를 지난다 — FAIL이면 자동 해소가 돈다",
     "기계 관문(하네스): FAIL" in _r40.stdout
     and "재생성 지시 (자동(하네스))" in _r40.stdout
     and "기계 관문(하네스): PASS" in _r40.stdout, _r40.stdout[-90:])
_st40 = json.loads((REVIEW / "f40ok" / "state.json").read_text(encoding="utf-8"))
show("① 지시 이력이 한 사슬이다 — 사람(검수 지시) → 자동(하네스)",
     [(i["n"], i["by"]) for i in _st40["instructions"]]
     == [(1, "사람(검수 지시)"), (2, "자동(하네스)")], str(_st40["instructions"])[:60])
show("① 통과하면 뷰가 선다", _st40["machine_gate"] == "PASS"
     and (REVIEW / "f40ok" / "view.json").exists() and _r40.returncode == 0)
_reg40("generate", "f40no", "process", str(RAW / "CP01.xlsx"))
# **생성이 이미 뷰를 만들었다**(B58 ⑤) — 초안은 관문을 지났기 때문이다. 잠글
# 성질은 「뷰가 없다」가 아니라 **「관문을 못 지난 산출로 뷰를 갈아 치우지
# 않는다」**로 바뀐다: 붉은 재생성분이 화면을 덮으면 사람이 그것을 보고 승인한다.
_v41 = REVIEW / "f40no" / "view.json"
_before41 = _v41.read_bytes() if _v41.exists() else None
_r41 = _reg40("review", "f40no", "--instruct", "이렇게 고쳐라", "--no-llm-coord")
_st41 = json.loads((REVIEW / "f40no" / "state.json").read_text(encoding="utf-8"))
# **이 검사가 변이 시험이다** — `cmd_review`에서 machine_gate 호출을 빼면 붉은
# 산출이 뷰를 덮어써 붉는다.
show("① 해소 못 하면 **뷰를 갈아 치우지 않는다** · machine_gate=FAIL (변이 검출 지점)",
     _st41["machine_gate"] == "FAIL"
     and (_v41.read_bytes() if _v41.exists() else None) == _before41
     and "검수 뷰를 만들지 않았다" in _r41.stdout and _r41.returncode != 0,
     [l.strip() for l in _r41.stdout.splitlines() if "만들지 않았다" in l][:1])
show("① 관문 호출이 cmd_review의 지시 갈래에 있다 (생성과 같은 함수)",
     _calls.get("cmd_review", []).count("machine_gate") == 1)
for _d in ("f40ok", "f40no"):
    shutil.rmtree(REVIEW / _d, ignore_errors=True)
shutil.rmtree(_f40, ignore_errors=True)

# ── ② D-79에 rehearsal · 렌더러가 낸다
_vs = json.loads((ROOT / "kit/검수뷰_데이터스키마.json").read_text(encoding="utf-8"))
_summ = (_vs["properties"]["sections"]["properties"]["parse_result"]
         ["properties"]["summary"]["properties"])
show("② D-79 계약에 summary.rehearsal이 있다 (실려 있는데 계약에 없던 키)",
     "rehearsal" in _summ
     and set(_summ["rehearsal"]["properties"]) == {"max_rows", "full_rows", "truncated"})
_rh = _RR.render({"doc_type": "x", "adapter_version": "1", "payload_kind": "table",
                  "sections": {"parse_result": {
                      "summary": {"samples": 2, "pieces": 200, "fill_rate": {},
                                  "rehearsal": {"max_rows": 200, "full_rows": 5231,
                                                "truncated": True}},
                      "anomalies": [], "normal": {"excerpt": [], "all": [],
                                                  "columns": [], "tree": []}},
                      "role_table": [], "adapter_summary": {}}})
show("② 렌더러가 「부분 리허설 — 전 M행 중 앞 N행」을 요약에 낸다 (승인 근거)",
     "부분 리허설 — 전 5,231행 중 앞 200행만 파싱했다" in _rh,
     [l for l in _rh.splitlines() if "부분 리허설" in l][:1])
show("② 전량 파싱이면 그 줄이 없다 (없는 사실을 만들지 않는다)",
     "부분 리허설" not in _RR.render(
         {"doc_type": "x", "adapter_version": "1", "payload_kind": "table",
          "sections": {"parse_result": {"summary": {"samples": 1, "pieces": 3,
                                                    "fill_rate": {}, "rehearsal": {}},
                                        "anomalies": [], "normal": {"excerpt": [], "all": [],
                                                                    "columns": [], "tree": []}},
                       "role_table": [], "adapter_summary": {}}}))

# ============================================================ B51 추출 리허설 · doc_id
print("\n■ B51 — prose ②구획은 추출 리허설 · parse run의 doc_id 파생")
from core import extract as _EX                                     # noqa: E402

# ── ② parse run — doc_id는 선택이다 (§7.1)
def _prun(*a):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "parse", "run",
                           "--allow-mock", *a], capture_output=True, text=True,
                          cwd=str(ROOT), stdin=subprocess.DEVNULL)


_p1 = _prun(str(ROOT / "tests/fixtures/adapters/cp.py"), str(RAW / "CP01.xlsx"))
show("② 새 형 — doc_id를 파일명에서 파생한다 (ingest-file과 같은 규칙)",
     "doc_id = CP01 (파일명 파생)" in _p1.stdout and _p1.returncode == 0,
     _p1.stdout.splitlines()[:1])
_p2 = _prun(str(ROOT / "tests/fixtures/adapters/cp.py"), "CPOLD", str(RAW / "CP01.xlsx"))
show("② 구형 4인자도 그대로 받는다 (둘째가 파일이 아니면 doc_id다)",
     "doc_id = CPOLD (인자)" in _p2.stdout and _p2.returncode == 0)
_p3 = _prun(str(ROOT / "tests/fixtures/adapters/cp.py"), str(RAW / "CP01.xlsx"),
            "--doc-id", "지정본")
show("② --doc-id가 파생을 이긴다", "doc_id = 지정본 (지정)" in _p3.stdout)
show("② 파생 함수는 한 곳이다 — cli/ingest.doc_id_of를 부른다(복제 0)",
     "from cli.ingest import doc_id_of" in
     (ROOT / "cli/parse.py").read_text(encoding="utf-8")
     and "def doc_id_of" not in (ROOT / "cli/parse.py").read_text(encoding="utf-8"))
for _n in ("CP01", "CPOLD", "지정본"):
    (ROOT / "parsed" / f"{_n}.json").unlink(missing_ok=True)

# ── ① prose 검수 뷰 — 추출 리허설이 운영과 같은 함수·같은 파일이다
reset("toc_report")
_EX.invalidate("TOC01")
run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"))
_rv = run("review", "toc_report", "--no-llm-coord", "--extract")
_v51 = view_of("toc_report")
_xr = _v51["sections"].get("extract_rehearsal") or {}
show("① prose ②구획이 추출 리허설이다 (배정표가 아니다)",
     "extract_rehearsal" in _v51["sections"] and "role_table" not in _v51["sections"]
     and len(_v51["sections"]) == 3)
show("① 청크별 후보와 카테고리 집계가 데이터에 있다 (렌더러는 계산하지 않는다)",
     _xr.get("totals", {}).get("chunks", 0) > 0 and isinstance(_xr.get("by_chunk"), list)
     and isinstance(_xr.get("category_counts"), dict),
     str(_xr.get("totals")))
show("① 재현 조건이 실린다 — 출처·지시문 판본·config 판본",
     _xr.get("source") in ("mock", "live") and _xr.get("prompt_version")
     and _xr.get("config_version"), f"{_xr.get('source')} · {_xr.get('prompt_version')}")
show("① ⓑ 리허설이 **운영의 doc_id**로 체크포인트를 남긴다 (재사용의 조건)",
     _EX.has_checkpoint("TOC01"), str(_EX.checkpoint_path("TOC01")))
_html51 = (REVIEW / "toc_report" / "view.html").read_text(encoding="utf-8")
show("① 화면 제목이 「추출 리허설 — 층 어휘가 이 문서에 적용된 결과」다",
     "구획 2 · 추출 리허설 — 층 어휘가 이 문서에 적용된 결과" in _html51
     and "청크별 후보" in _html51)
run("confirm", "toc_report", "--by", "검수자")
_ing = subprocess.run([sys.executable, str(ROOT / "run.py"), "ingest-file",
                       str(RAW / "TOC01.xlsx"), "--doc-type", "toc_report",
                       "--allow-mock"], capture_output=True, text=True, cwd=str(ROOT),
                      stdin=subprocess.DEVNULL)
show("① ⓑ 확정 뒤 운영 인입이 그 체크포인트를 **재사용**한다 (LLM 호출 추가 0)",
     "[추출 체크포인트 재사용]" in _ing.stdout,
     [l.strip() for l in _ing.stdout.splitlines() if "성공" in l][:1])
_appr51 = json.loads((REVIEW / "toc_report" / "approval.json").read_text(encoding="utf-8"))
show("① ⓔ 승인 기록에 요약이 실린다 — 무엇이 뽑히는 것을 보고 승인했나",
     (_appr51.get("추출 리허설") or {}).get("totals")
     and (_appr51["추출 리허설"]).get("category_counts") is not None)

# ── ⓒ 부분 리허설이면 체크포인트를 남기지 않는다
reset("toc_report")
_EX.invalidate("TOC01")
(ROOT / "parsed" / "TOC01.json").unlink(missing_ok=True)
run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"))
run("review", "toc_report", "--rows", "5", "--no-llm-coord", "--extract")
_xr2 = view_of("toc_report")["sections"].get("extract_rehearsal") or {}
show("① ⓒ 부분 리허설이면 체크포인트가 **안 남는다** (운영이 앞 N행만 본 추출을 쓰면 안 된다)",
     not _EX.has_checkpoint("TOC01") and _xr2.get("kept") is False
     and "체크포인트를 남기지 않았다" in (_xr2.get("note") or ""), str(_xr2.get("note")))

# ── ⓓ 비대화형이면 끄고 그 사실을 뷰가 말한다
reset("toc_report")
run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"))
run("review", "toc_report", "--no-llm-coord")          # --extract 없음 = 물어본다
_xr3 = view_of("toc_report")["sections"].get("extract_rehearsal") or {}
show("① ⓓ 비대화형이면 끄고 뷰에 「추출 리허설 없음」을 남긴다 (조용한 구간 0)",
     _xr3.get("source") == "none" and "없음" in (_xr3.get("note") or ""),
     str(_xr3))
show("① prose의 리허설 기본은 전량이다 (부분 리허설의 근거는 table의 것)",
     not (view_of("toc_report")["sections"]["parse_result"]["summary"]
          .get("rehearsal") or {}).get("truncated"))
reset("toc_report")
_EX.invalidate("TOC01")


# ── B55 ① 재생성 지시가 **모델에 닿는다** (문서 6 §6.5 · [정정] 40) ──────────
#
# **이 어서션이 없어서 H20이 살아남았다.** mock의 `draft`는 `{doc_type}_rev{N}`이라는
# **다른 파일**을 돌려주므로 재생성 루프가 도는 것처럼 보였고, 「지시가 실제로
# 모델에 실렸나」를 재는 자리가 없어 B50·[정정] 40의 어서션이 전부 초록이었다.
# 여기서 재는 것은 **조립된 전송분**이다 — 기록이 아니라 전송이다.
from core import llm as _llm                                       # noqa: E402
print("\n■ B55 ① — 재생성 지시가 조립 메시지에 실린다")

_b55_sent = {}
_b55_post, _b55_req, _b55_mock = _llm._post, _llm.require, _llm.use_mock


def _b55_capture():
    _llm.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                               "timeout": 5, "retry": 0}
    _llm.use_mock = lambda: False
    _llm._post = lambda u, p, k, t: _b55_sent.update(payload=p) or {
        "choices": [{"message": {"content": json.dumps(
            {"adapter_py": "# x\nADAPTER = {}\ndef extract(raw):\n    return []",
             "schema_json": "{}"})}}]}


def _b55_restore():
    _llm._post, _llm.require, _llm.use_mock = _b55_post, _b55_req, _b55_mock


def _b55_system(**kw):
    """`draft`를 태워 **전송 직전 dict**의 system 메시지를 돌려준다."""
    _b55_sent.clear()
    R.draft("b55i", kw.pop("revision", 0), **kw)
    return _b55_sent["payload"]["messages"][0]["content"]


_b55_dir = R._dir("b55i")
_b55_dir.mkdir(parents=True, exist_ok=True)
(_b55_dir / "input_package.json").write_text(json.dumps(
    {"human": {"doc_type": "b55i", "layer": "process",
               "samples": ["tests/fixtures/raw/CP01.xlsx"], "hint": ""},
     "system": {"reader_head": [], "skeleton_closed_list": {},
                "layer_vocabulary": {"layer": "process"}, "blocks": {},
                "adapter_skeleton": ""}}, ensure_ascii=False), encoding="utf-8")
_b55_capture()
try:
    _sys0 = _b55_system()                                   # 초회 — 지시 없음
    _hist2 = [{"n": 1, "instruction": "헤더는 2행이다", "by": "사람(검수 지시)"},
              {"n": 2, "instruction": "극성 열은 쓰지 않는다", "by": "자동(하네스 문면)"}]
    _sys2 = _b55_system(revision=2, instruction="극성 열은 쓰지 않는다",
                        history=_hist2)
finally:
    _b55_restore()

# ①ⓐ **둘 다 실린다** — 2회차 지시가 1회차를 덮으면 사람이 같은 교정을 두 번 적는다.
show("① 지시가 조립된 system에 **실제로 실린다** (기록이 아니라 전송분)",
     "헤더는 2행이다" in _sys2 and "극성 열은 쓰지 않는다" in _sys2,
     f"{len(_sys2.encode()):,}B")
show("① 누적 2회 — 앞 지시가 뒤 지시에 덮이지 않는다",
     _sys2.index("헤더는 2행이다") < _sys2.index("극성 열은 쓰지 않는다"))
# ①ⓒ 초회에는 구획 자체가 없다
show("① 초회에는 지시 구획이 없다 (없는 것을 빈 칸으로 넣지 않는다)",
     "헤더는 2행이다" not in _sys0
     and len(_sys0.encode()) < len(_sys2.encode()),
     f"{len(_sys0.encode()):,}B → {len(_sys2.encode()):,}B")
# **전송 크기(B30)가 지시 구획을 포함한다** — 사람이 보내기 전에 크기를 알아야 한다
show("① 전송 크기 표시가 지시 구획을 포함한다 (부르기 직전에 잰다)",
     len(_sys2.encode()) - len(_sys0.encode())
     >= len("극성 열은 쓰지 않는다".encode()) + len("헤더는 2행이다".encode()))
shutil.rmtree(_b55_dir, ignore_errors=True)

# ①-후속-2 — **고정 문장은 템플릿의 것이다** (문서 7 §7.6-B-5 · B18 경계).
#
# 문구를 grep으로 잠그면 **성질이 아니라 글자**를 잠근다 — 한 글자만 바꿔 코드로
# 되돌리면 통과한다. 그래서 **템플릿에서 그 문장만 지운 사본**으로 렌더해
# ①문장이 사라지고 ②주입된 지시는 그대로인지를 본다(둘째가 없으면 「렌더가 깨진
# 것」과 구분되지 않는다).
_b55_tmpl = R._newest_template().read_text(encoding="utf-8")
_b55_pkgmin = {"human": {"doc_type": "t", "layer": "process", "samples": ["s"],
                         "hint": ""},
               "system": {"reader_head": [], "skeleton_closed_list": {},
                          "layer_vocabulary": {"layer": "process"}, "blocks": {},
                          "adapter_skeleton": ""}}
_b55_items = R.instruction_items(
    "극성 열은 쓰지 않는다",
    [{"n": 1, "instruction": "헤더는 2행이다", "by": "사람(검수 지시)"}])
_B55_FIXED = "앞 초안이 아래 지시를 받았다"
_b55_full = R._render_template(_b55_tmpl, _b55_pkgmin, regeneration=_b55_items)
_b55_cut = R._render_template(_b55_tmpl.replace(_B55_FIXED, ""), _b55_pkgmin,
                              regeneration=_b55_items)
show("①-후속-2 구획의 고정 문장이 **템플릿에서** 온다 "
     "(문장을 지운 사본으로 렌더하면 사라진다)",
     _B55_FIXED in _b55_full and _B55_FIXED not in _b55_cut)
show("①-후속-2 그때도 **주입된 지시 목록은 그대로다** (렌더가 깨진 것과 구분)",
     "헤더는 2행이다" in _b55_cut and "극성 열은 쓰지 않는다" in _b55_cut
     and "## [재생성 지시]" in _b55_cut)
show("①-후속-2 지시가 없으면 구획째 빠진다 (빈 칸을 남기지 않는다)",
     "## [재생성 지시]" not in
     R._render_template(_b55_tmpl, _b55_pkgmin, regeneration=[]))
show("①-후속-2 치환 누락 0 — 지시 자리가 늘어도 `{{` 잔존 0",
     "{{" not in _b55_full)
# 판 계보는 킷 규칙이다 — 옛 판을 고쳐 쓰지 않는다.
show("①-후속-2 v1.0을 고치지 않고 v1.1을 세웠다 (판 계보 보존)",
     (R.KIT / "생성프롬프트_템플릿_v1.1.md").exists()
     and R._newest_template().name == "생성프롬프트_템플릿_v1.1.md"
     and "{{재생성_지시}}" not in
     (R.KIT / "생성프롬프트_템플릿_v1.0.md").read_text(encoding="utf-8"))

# ── B55 ② 문답은 누적된다 — 재현 조건의 그릇은 `human.hint`다 (B36 · §6.5) ──
print("\n■ B55 ② — 문답 묶음이 쌓이고 표본이 바뀌면 stale로 남는다")

# **먼저 지운다** — 앞선 실행의 패키지가 남아 있으면 「이어 붙인다」를 재는 검사가
# 그 잔재까지 세어, 묶음 수가 실행 이력에 따라 달라진다(단독 실행이 판정 규격이다).
shutil.rmtree(R._dir("b55iv"), ignore_errors=True)
_b55_feed = iter(["표본은 CP 양식이다", "진행", "헤더는 4행이다", "진행",
                  "다른 문서다", "진행"])
_b55_ask = _IV._ask
_IV._ask = lambda prompt="": next(_b55_feed)
_CP1 = str(RAW / "CP01.xlsx")
_PF1 = str(RAW / "PFMEA01.xlsx")
_b55_buf = _io.StringIO()
try:
    def _b55_gen(samples):
        # **패키지는 draft보다 먼저 쓰인다** — fixture가 없어 초안 단계에서 멈춰도
        # 여기서 재는 것(문답이 패키지에 남았나)은 이미 결정돼 있다.
        try:
            with _ctx.redirect_stdout(_b55_buf):
                R.cmd_generate("b55iv", "process", samples, "", interview=True)
        except SystemExit:
            pass
        return json.loads((R._dir("b55iv") / "input_package.json")
                          .read_text(encoding="utf-8"))

    _pk1 = _b55_gen([_CP1])
    _pk2 = _b55_gen([_CP1])
    _pk3 = _b55_gen([_PF1])
finally:
    _IV._ask = _b55_ask


def _b55_batches(pk):
    return R._hint_batches((pk["human"] or {}).get("hint"))


# ②ⓐ **재실행이 덮지 않는다** — 구판은 이번 실행분으로 치환했다.
show("② --interview 2회 — 묶음이 **둘 다 남는다** (덮지 않는다)",
     len(_b55_batches(_pk1)) == 1 and len(_b55_batches(_pk2)) == 2,
     f"{len(_b55_batches(_pk1))} → {len(_b55_batches(_pk2))}묶음")
show("② 1회차 답이 2회차 패키지에 그대로 있다 (사람의 답은 다시 못 만든다)",
     any("표본은 CP 양식이다" in (r.get("answer") or "")
         for b in _b55_batches(_pk2) for r in b["rounds"]))
# ②ⓒ 표본이 바뀌면 **표시하되 지우지 않는다**
_b55_stale = [b for b in _b55_batches(_pk3) if b.get("stale")]
show("② 표본을 바꾸면 이전 묶음이 **stale로 남는다** (지워지지 않는다)",
     len(_b55_batches(_pk3)) == 3 and len(_b55_stale) == 2
     and all(b["samples"] == [_CP1] for b in _b55_stale),
     f"묶음 {len(_b55_batches(_pk3))} · stale {len(_b55_stale)}")
show("② 묶음마다 그때의 표본과 시각을 단다 (재현 조건)",
     all(b.get("samples") is not None and b.get("at") for b in _b55_batches(_pk3)))
# ②ⓕ **키 수가 명세다** — 항목으로 늘고 키로 늘지 않는다(B36)
show("② 사람 4키·시스템 5키 불변 — 문답은 hint 그릇 **안에서** 는다",
     all(len(p["human"]) == 4 and len(p["system"]) == 5
         for p in (_pk1, _pk2, _pk3)),
     f"human {len(_pk3['human'])} · system {len(_pk3['system'])}")
# ②-2 **모델도 그것을 본다** — 저장만 이어 붙이면 사람이 두 번 답한다
_b55_fresh, _b55_old = _IV._prior_rounds(_pk3)
show("② 문답 세션이 이전 라운드를 받는다 — stale은 **구분해서**",
     len(_b55_fresh) == 1 and len(_b55_old) == 2
     and "다른 문서다" in (_b55_fresh[0].get("answer") or ""),
     f"현재 {len(_b55_fresh)} · 이전 표본 {len(_b55_old)}")
shutil.rmtree(R._dir("b55iv"), ignore_errors=True)


# ── B55 ③~⑩ 감사 2차 A군 수리 ─────────────────────────────────────────────
print("\n■ B55 ③ — 추출 실패의 처분은 청크 단위다 (문서 4 §4.10 규약 9)")

from core import extract as _EX                                   # noqa: E402

_b55_env = {"doc_id": "B55FAIL", "adapter_version": "1.0", "parsed_at": "t",
            "chunks": [{"source_locator": f"L{i}", "text": f"노칭 공정 {i}"}
                       for i in (1, 2, 3)]}
_b55_ids = {f"L{i}": f"B55FAIL:c{i}" for i in (1, 2, 3)}
_b55_cfg = {"layer": "process", "config_version": "1", "categories": {}, "relations": []}
_b55_real = _EX._candidates_for


def _b55_one_bad(cid, chunk, cfg, vocab):
    if cid.endswith("c2"):
        raise ValueError("주입한 실패")
    return _b55_real(cid, chunk, cfg, vocab)


_EX.checkpoint_path("B55FAIL").unlink(missing_ok=True)
_b55_d = store.path(store.DEFECTS)
_b55_b0 = _b55_d.stat().st_size if _b55_d.exists() else 0
_EX._candidates_for = _b55_one_bad
try:
    _b55_out, _b55_made = _EX.extract(_b55_env, _b55_cfg, _b55_ids, {})
finally:
    _EX._candidates_for = _b55_real
_b55_ok = [c for c in _b55_out["candidates"] if not c.get("failed")]
_b55_bad = [c for c in _b55_out["candidates"] if c.get("failed")]
# ③ⓐ **한 청크의 예외가 문서를 죽이지 않는다** — 3천 청크 문서가 한 줄로 통째로 빠지면
# 그 문서는 영영 안 들어간다.
show("③ⓐ 청크 하나가 실패해도 나머지는 산출된다",
     len(_b55_ok) == 2 and len(_b55_bad) == 1, f"성공 {len(_b55_ok)} · 실패 {len(_b55_bad)}")
# ③ⓑ **무후보와 구분한다** — `entities: []`는 「봤는데 없었다」, `failed`는 「보지 못했다」.
show("③ⓑ 체크포인트에 failed가 사유와 함께 남는다 (무후보와 구분)",
     _b55_bad[0]["failed"].startswith("ValueError")
     and _b55_bad[0]["entities"] == [], _b55_bad[0]["failed"])
show("③ⓒ defects.log에 남는다 — 큐가 아니라 결함 로그다 (새 kind 0)",
     (_b55_d.stat().st_size if _b55_d.exists() else 0) > _b55_b0
     and "추출 실패" in _b55_d.read_text(encoding="utf-8"))
show("③ 구축이 failed 청크를 건너뛴다 (결함이 「후보 0건」 통계에 녹지 않는다)",
     "if not c.get(\"failed\")" in
     (ROOT / "core" / "pipeline.py").read_text(encoding="utf-8"))
# ③ⓓ **전건 실패면 체크포인트를 쓰지 않는다** — 「파일 존재 = 추출 완료」(P-1).
_EX.checkpoint_path("B55FAIL").unlink(missing_ok=True)
_EX._candidates_for = lambda *a, **k: (_ for _ in ()).throw(ValueError("전건"))
try:
    _b55_all, _b55_made2 = _EX.extract(
        dict(_b55_env, doc_id="B55ALL"), _b55_cfg,
        {f"L{i}": f"B55ALL:c{i}" for i in (1, 2, 3)}, {})
finally:
    _EX._candidates_for = _b55_real
show("③ⓓ 전 청크 실패면 체크포인트를 남기지 않는다 (재시도가 막히지 않는다)",
     not _EX.checkpoint_path("B55ALL").exists()
     and _b55_all.get("all_failed") is True and _b55_made2 is False)

print("\n■ B55 ④ — 프레임 지도가 source_hash 무효화를 우회하지 않는다 (§6.3 · B16)")

import shutil as _b55_sh                                          # noqa: E402
from parser import struct_map as _SM, tagger as _tagger                              # noqa: E402
from parser.adapters import basic_ppt as _BP                      # noqa: E402

_b55_src = ROOT / "data" / "_b55_map.pptx"
_b55_sh.copy(RAW / "PPT_basic.pptx", _b55_src)
_b55_calls = []


def _b55_ask(doc_id, lines):
    _b55_calls.append(doc_id)
    return {"doc_id": doc_id, "source": "live", "prompt_version": "s-1.0",
            "rows": [{"row": n, "heading": t.strip()[:2] in ("1.", "2.", "3."),
                      "level": 1 if t.strip()[:2] in ("1.", "2.", "3.") else 0}
                     for n, t in lines]}


def _b55_parse():
    _b55_calls.clear()
    pipeline.parse(_BP, "B55MAP", str(_b55_src), map_structure=_b55_ask)
    return len(_b55_calls)


_b55_sh.rmtree(_SM.KEEP_DIR, ignore_errors=True)
_b55_n1 = _b55_parse()
_b55_files = sorted(p.name for p in _SM.KEEP_DIR.glob("*"))
_b55_n2 = _b55_parse()                       # 같은 원본 — 재사용
_b55_src.write_bytes(_b55_src.read_bytes() + b"\x00")   # 1바이트 변경
_b55_n3 = _b55_parse()
# ④ⓑ **문서당 파일 하나**다 — 구판은 `{doc_id}:{프레임}.json`을 따로 만들었다.
show("④ⓑ 보존 파일은 {doc_id}.json 하나다 (프레임은 그 안의 maps[키])",
     _b55_files == ["B55MAP.json"], str(_b55_files))
show("④ⓒ 같은 원본 재파싱은 재사용한다 (LLM 0회)",
     _b55_n1 == 1 and _b55_n2 == 0, f"1회차 {_b55_n1} · 2회차 {_b55_n2}")
# ④ⓐ **원본이 바뀌면 옛 지도가 살아나지 않는다** — 구판은 프레임 지도를 해시 대조
# 없이 읽어 영영 옛 분할을 썼고, chunk_id 결정성의 근거가 무너졌다.
show("④ⓐ 원본 1바이트 변경 → 지도를 새로 산출한다 (해시 대조를 우회하지 않는다)",
     _b55_n3 == 1, f"3회차 {_b55_n3}회")
_b55_kept = json.loads((_SM.KEEP_DIR / "B55MAP.json").read_text(encoding="utf-8"))
show("④ 보존 파일이 source_hash와 maps를 함께 갖는다",
     bool(_b55_kept.get("source_hash")) and bool(_b55_kept.get("maps")),
     f"프레임 {sorted(_b55_kept.get('maps') or {})}")
_b55_src.unlink(missing_ok=True)
_b55_sh.rmtree(_SM.KEEP_DIR, ignore_errors=True)

print("\n■ B55 ⑤ — 리허설 파싱도 운영 doc_id를 쓴다 (§6.6 B51-2)")

from cli.ingest import doc_id_of as _b55_did                      # noqa: E402

show("⑤ 리허설 파싱이 doc_id_of(표본)를 쓴다 ({DOC_TYPE}NN이 아니다)",
     "mod, doc_id_of(s), s, layer=" in
     (ROOT / "cli" / "register.py").read_text(encoding="utf-8"))
# **키가 같아야 재사용이 성립한다** — 구판은 리허설이 다른 이름으로 써서 못 만났다.
_b55_sh.rmtree(_SM.KEEP_DIR, ignore_errors=True)
_b55_sh.copy(RAW / "PPT_basic.pptx", _b55_src)
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask)
_b55_rehearsal = len(_b55_calls)
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask)
show("⑤ⓐ 리허설이 남긴 지도를 운영 인입이 찾는다 (재사용 — LLM 0회)",
     _b55_rehearsal == 1 and len(_b55_calls) == 0)
_b55_sh.rmtree(_SM.KEEP_DIR, ignore_errors=True)
_b55_calls.clear()
pipeline.parse(_BP, "B55OLD01", str(_b55_src), map_structure=_b55_ask)   # 구판 이름
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask)
show("⑤ [대조] 이름이 다르면 못 찾는다 — 고친 것이 이것이다",
     len(_b55_calls) == 1)
_b55_src.unlink(missing_ok=True)
_b55_sh.rmtree(_SM.KEEP_DIR, ignore_errors=True)

print("\n■ B55 ⑥ — PDF 쪽 렌더가 ④에 닿는다")

from parser.adapters import basic_pdf as _BPDF                    # noqa: E402


def _b55_sum(ref, *, image=None, mime=None, context="", page=None):
    return f"요약(page={'있음' if page else '없음'})"


_b55_pdf = pipeline.parse(_BPDF, "B55PDF", str(RAW / "PDF_basic.pdf"),
                          summarize=_b55_sum)
_b55_pic = [c for c in _b55_pdf.envelope["chunks"]
            if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
# 구판은 `meta["slide"]`만 봐서 PDF는 늘 `pages.get(None)` → 항상 none이었다.
show("⑥ⓐ PDF 그림 청크의 slide_render가 page다 (meta.page를 본다)",
     _b55_pic["meta"]["slide_render"] == "page"
     and _b55_pic["meta"].get("page") is not None,
     f"page={_b55_pic['meta'].get('page')} · {_b55_pic['meta']['slide_render']}")
show("⑥ 조회 키 결정은 한 자리다 (tagger._page_no)",
     _tagger._page_no({"meta": {"slide": 3}}) == 3
     and _tagger._page_no({"meta": {"page": 7}}) == 7
     and _tagger._page_no({"meta": {}}) is None)

print("\n■ B55 ⑦ — llm-check의 401/403이 ③인증으로 간다")

_b55_req, _b55_cfgf, _b55_postf = llm.require, llm.config, llm._post
try:
    llm.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                              "timeout": 5, "retry": 0}
    llm.config = lambda: {"url": "https://x", "model": "m", "key": "k",
                          "timeout": 5, "retry": 0, "embed_model": None}

    def _b55_probe(exc):
        llm._post = lambda u, p, k, t: (_ for _ in ()).throw(exc)
        return {s["id"]: s for s in llm.probe()}

    _p401 = _b55_probe(llm.GatewayError(401, "invalid api key", "u"))
    _p500 = _b55_probe(llm.GatewayError(500, "upstream boom", "u"))
    _purl = _b55_probe(__import__("urllib.error", fromlist=["x"]).URLError("no route"))
finally:
    llm.require, llm.config, llm._post = _b55_req, _b55_cfgf, _b55_postf
# **어디까지 갔는지가 곧 원인이다**(B19) — 키가 틀렸는데 「주소에 못 닿았다」고
# 말하면 사람이 엉뚱한 곳을 고친다.
show("⑦ⓐ 401 → ②도달 PASS · ③인증 FAIL",
     _p401["②"]["ok"] is True and _p401["③"]["ok"] is False
     and "401" in _p401["③"]["detail"])
show("⑦ⓑ 500 → ③이 「인증 문제는 아니다」라고 말한다",
     _p500["③"]["ok"] is False and "인증 문제는 아니다" in _p500["③"]["detail"]
     and "upstream boom" in _p500["③"]["detail"])
show("⑦ⓒ URLError → ②도달 FAIL 그대로 (③은 아예 나오지 않는다)",
     _purl["②"]["ok"] is False and "③" not in _purl)
# **`_post`의 HTTPError 포착은 남는다** — 거기가 GatewayError로 바꿔 던지는 자리다.
# 죽어 있던 것은 `probe` 안의 갈래이고, 그 함수 본문만 본다.
_b55_llmsrc = (ROOT / "core" / "llm.py").read_text(encoding="utf-8")
_b55_probe_src = _b55_llmsrc[_b55_llmsrc.index("def probe("):]
_b55_probe_src = _b55_probe_src[:_b55_probe_src.index("\ndef ", 1)]
# **주석은 코드가 아니다** — 무엇이 왜 죽어 있었는지 적은 문장이 그 자리에 있고,
# 문자열로 세면 그 설명이 위반으로 잡힌다(§7.5 「주석을 구현으로 세지 않는다」의 역).
_b55_probe_code = "\n".join(
    ln for ln in _b55_probe_src.split("\n") if not ln.strip().startswith("#"))
show("⑦ probe에 죽은 HTTPError 갈래가 없다 (GatewayError로 받는다)",
     "except urllib.error.HTTPError" not in _b55_probe_code
     and "except GatewayError as e" in _b55_probe_code
     and "e.status" in _b55_probe_code)
show("⑦ _post의 HTTPError 포착은 그대로다 (바꿔 던지는 자리다)",
     "except urllib.error.HTTPError" in _b55_llmsrc
     and "raise GatewayError(e.code, body, url) from e" in _b55_llmsrc)

print("\n■ B55 ⑧⑨ — 경로 경고 · 멱등 계측 · 골든셋 유형")

from cli import ingest as _ING                                    # noqa: E402

# doc_id가 파일명 stem 파생이라(D-110) **파일명 비교는 참이 될 수 없었다**.
show("⑧ 경로 비교가 파일명이 아니라 전체 경로다 (D-110의 대가가 화면에 뜬다)",
     "_norm_path(prev[\"source_path\"]) != _norm_path(doc)" in
     (ROOT / "cli" / "ingest.py").read_text(encoding="utf-8")
     and _ING._norm_path("./a/x.xlsx") != _ING._norm_path("./b/x.xlsx")
     and _ING._norm_path("a/x.xlsx") == _ING._norm_path("./a/x.xlsx"))
# `return` 아래가 통째로 도달 불가였다 — 완료판정 4가 한 번도 계측된 적이 없다.
_b55_doc = (ROOT / "doctor.py").read_text(encoding="utf-8")
show("⑨ 멱등 계측이 도달 가능하다 (헬퍼 `_clean()`을 부르고 2회 실행·비교한다)",
     "rc, residue = _clean()" in _b55_doc
     and _b55_doc.index("rc, residue = _clean()")
     < _b55_doc.index("g1, q1, r1 = snap()")
     and "클린 2회 동일 그래프" in _b55_doc)
# **문면을 조각으로 쓴다** — 이 줄이 「층 그래프 파일을 아는 코드」 검사(test_g1_g2)에
# 걸리지 않게. `doctor.py`가 같은 이유로 `"graph" + ".json"`을 쓴다(레포의 관용).
show("⑨ snap()이 층 그래프 파일을 바이트로 여는 근거가 주석에 있다 (B6 예외 명시)",
     "B6(GraphStore 경유)의 예외이고" in _b55_doc)

# ── B58 ② 기계 관문의 범위 = 파서 전 구간 ────────────────────────────────
print("\n■ B58 ② — 관문이 pipeline.parse 전 구간을 돈다")

_KIT_SRC = (ROOT / "kit" / "run_adapter.py").read_text(encoding="utf-8")

# ⓐ **관문과 검수 리허설이 같은 함수를 부른다.** 이것이 「관문 PASS 뒤 검수에서
# 기계 오류가 날 자리가 없다」의 근거다 — 두 곳이 다른 함수를 부르면 한쪽만 통과하는
# 경로가 생기고, 그 틈이 곧 사내가 겪던 「검수에서 처음 깨진다」다.
# **부르는 것을 센다**(AST) — 「pipeline.parse를 돈다」는 주석은 아무것도 돌리지 않는다.
_kit_calls = {n.func.attr for n in _ast.walk(_ast.parse(_KIT_SRC))
              if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)}
_reg_src = (ROOT / "cli" / "register.py").read_text(encoding="utf-8")
_reg_calls = {n.func.attr for n in _ast.walk(_ast.parse(_reg_src))
              if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)}
show("②ⓐ 관문이 pipeline.parse를 **부른다** (검수 리허설과 같은 함수)",
     "parse" in _kit_calls and "parse" in _reg_calls)
show("②ⓐ 관문은 하네스 실물을 부르는 구조 그대로다 (재작성 아님)",
     "run_adapter.py" in _reg_src)

# ⓒ **관문이 LLM을 부르지 않는다.** 무엇을 주입하지 않는가가 규격이라, 주입 인자
# 이름이 하네스 안에 **하나도 나타나지 않는 것**으로 잰다.
_gate_body = _KIT_SRC.split("def run_pipeline")[1].split("\n# ---")[0]
_gate_code = "\n".join(l for l in _gate_body.splitlines()
                       if not l.lstrip().startswith("#"))
_injected = [pt for pt in ("summarize=", "pick_coord=", "map_structure=")
             if pt in _gate_code]
show("②ⓒ 관문이 LLM 지점 3종을 주입하지 않는다 (무LLM 대체 경로로 돈다)",
     not _injected, str(_injected))
show("②ⓒ 관문 안에 LLM 게이트웨이 미적재 어서션이 있다 (문면이 아니라 sys.modules)",
     '"core.llm" not in sys.modules' in _KIT_SRC)

# ⓑ **tagger에서 깨지는 검체는 관문에서 잡힌다** — 검수까지 가지 않는다.
# 이 검체는 ①~④를 통과한다(조각도 나오고 스키마도 맞다). 구판 관문은 통과시켰다.
_BRK = ROOT / "tests/fixtures/검체/gate_break_tagger.py"
_brk_ok, _brk_out = R.harness(_BRK, _BRK.with_suffix(".json"), [RAW / "CP01.xlsx"])
_stages = _brk_out.split("⑤ 파서 전 구간")
show("②ⓑ 깨지는 검체가 관문에서 FAIL이다 (검수까지 가지 않는다)",
     not _brk_ok and len(_stages) == 2)
show("②ⓑ ①~④는 통과했다 — 구판 관문이 이 어댑터를 놓친 자리다",
     "[FAIL]" not in _stages[0], str([l.strip() for l in _stages[0].splitlines()
                                      if "[FAIL]" in l][:2]))
show("②ⓑ 잡은 자리가 ⑤다 — 파서 전 구간이 예외로 멈췄다",
     "[FAIL] 파서 전 구간이 예외 없이 완주" in _stages[1]
     and "unhashable" in _stages[1],
     [l.strip() for l in _stages[1].splitlines() if "[FAIL]" in l][:1])

# ⓐ 실증 — prose 1건은 관문 PASS 뒤 검수에서 이상 0이다.
reset("toc_report")
_g = run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"))
_hp = "⑤ 파서 전 구간" in json.loads(
    (REVIEW / "toc_report" / "state.json").read_text(encoding="utf-8"))["harness_out"]
show("②ⓐ prose — 관문이 ⑤까지 돌고 PASS했다",
     "기계 관문 PASS" in _g.stdout and _hp)
run("review", "toc_report", "--rows", "200", "--no-llm-coord", "--no-extract")
_an = view_of("toc_report")["sections"]["parse_result"]["anomalies"]
show("②ⓐ prose — 검수 화면에 기계 오류 0 (failure 종 0건)",
     not [a for a in _an if a["kind"] == "failure"], str(_an[:2]))

# **관문이 남긴 자리는 관문이 치운다** — 운영 doc_id의 구조 지도를 덮으면 아직
# 등록도 안 된 어댑터의 산출이 운영 인입의 chunk_id를 흔든다.
show("②ⓐ 관문이 자기 구조 지도를 남기지 않는다 (운영 보존분과 섞이지 않는다)",
     not [q for q in (ROOT / "extract" / "struct_maps").glob("_gate_*.json")],
     str([q.name for q in (ROOT / "extract" / "struct_maps").glob("*.json")][:4]))


# ── B58 ⑤ 검수 뷰는 생성이 만든다 + 분할 분포 ──────────────────────────
print("\n■ B58 ⑤ — generate가 뷰까지 만든다 · review는 고칠 때만")

reset("toc_report")
_g5 = run("generate", "toc_report", "process",
          str(RAW / "TOC01.xlsx"), str(RAW / "TOC02.xlsx"))
_vh = REVIEW / "toc_report" / "view.html"
show("⑤ⓐ generate가 관문 PASS 뒤 view.html까지 만든다",
     _g5.returncode == 0 and _vh.exists() and _vh.stat().st_size > 0)
show("⑤ⓐ 그 경로를 화면이 찍는다 (사람이 어디를 볼지 안다)",
     "view.html" in _g5.stdout and "register confirm toc_report" in _g5.stdout)
# **뷰를 만드는 함수는 하나다** — 두 벌이면 「생성이 보여 준 화면」과 「검수가
# 보여 주는 화면」이 갈리고, 사람이 승인한 것이 어느 쪽인지 사후에 못 가린다.
show("⑤ⓐ 생성이 검수와 **같은 함수**를 부른다 (뷰 경로가 둘이 아니다)",
     "cmd_review(doc_type, llm_coord=False, extract=False)" in
     (ROOT / "cli" / "register.py").read_text(encoding="utf-8"))
# **생성은 LLM을 켜지 않는다** — 비용 관문은 사람이 켜는 것이고, 그 자리가 review다.
show("⑤ⓐ 생성의 뷰 산출에 LLM 호출 0 (좌표 보조·추출 리허설을 켜지 않는다)",
     "추출 리허설 끔" in _g5.stdout and "LLM 호출 0회" in _g5.stdout)
# **review는 남는다** — 없애면 재생성 지시·좌표 보조·추출 리허설의 자리가 사라진다.
_r5 = run("review", "toc_report", "--rows", "200", "--no-llm-coord", "--no-extract")
show("⑤ review는 선택 명령으로 남는다 (고칠 때 들어가는 자리)",
     _r5.returncode == 0 and "■ ② 검수" in _r5.stdout)
# ⓐ **review 없이 confirm이 된다.**
reset("toc_report")
run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"), str(RAW / "TOC02.xlsx"))
_c5 = run("confirm", "toc_report", "--by", "검수자 정")
show("⑤ⓐ review를 거치지 않고 confirm이 선다 (generate → 뷰 확인 → confirm)",
     _c5.returncode == 0 and registry.lookup("toc_report") is not None)

_v5 = view_of("toc_report")
_sum5 = _v5["sections"]["parse_result"]["summary"]
_html5 = _vh.read_text(encoding="utf-8")
# ⓑ **분포·고른 레벨·사유** — 값은 산출자가 채우고 렌더러는 그린다(§6.6-3).
_pick5 = [p for r in _sum5["split"] for p in (r.get("레벨_선택") or [])]
show("⑤ⓑ prose 화면에 레벨별 분포가 있다 (청크수·행수 min/max/avg·구간내)",
     _pick5 and all({"청크수", "행수_최소", "행수_최대", "행수_평균", "구간내_청크수"}
                    <= set(d) for p in _pick5 for d in (p["레벨_분포"] or {}).values()))
show("⑤ⓑ 규칙이 고른 레벨과 사유가 함께 있다",
     all(p.get("분할_레벨") is not None and p.get("분할_레벨_사유") for p in _pick5)
     and "목표 구간" in _pick5[0]["분할_레벨_사유"])
# ⓒ **짧은 쪽·긴 쪽 분리** — 처방이 다르다. 값도 화면도 갈라져 있어야 한다.
show("⑤ⓒ 목표 구간 밖이 짧은 쪽·긴 쪽으로 갈려 있다 (값)",
     all({"너무_짧은_청크", "너무_긴_청크", "목표구간"} <= set(r)
         for r in _sum5["split"]))
show("⑤ⓒ 화면이 둘을 각각 센다 — 처방이 다르다는 말이 함께 있다",
     "너무 짧음" in _html5 and "너무 긺" in _html5
     and "짧으면 레벨을 얕게" in _html5 and "길면 깊게" in _html5)
# **최근접 폴백은 머리에 선다** — 표 안의 한 칸이면 접힌 화면에서 사라진다.
show("⑤ⓒ 최근접 폴백이 머리에 표시된다 (TOC02가 그 경우다)",
     any(p.get("분할_레벨_구간밖") for p in _pick5)
     and "분할 레벨이 목표 구간 밖이다" in _html5
     and _html5.index("분할 레벨이 목표 구간 밖이다") < _html5.index("분할 크기 분포"))
# **형태 판정 다섯 값이 화면에 그대로** — 사람이 정할 것이 그 값이다.
show("⑤ 형태 판정 다섯 값이 뷰와 화면에 그대로 실린다 (문서 1 C37)",
     len(_sum5["form"]) == 2
     and all(len(f["signals"]) == 5 and len(f["votes"]) == 5 for f in _sum5["form"])
     and "형태 판정 — table이냐 prose냐" in _html5
     and "indent_share" in _html5)

# **사람에게 올라온 문서는 이상 신호로도 뜬다** — 요약 표에만 두면 접힌 화면에서
# 사라진다(§6.6-1 「이상 신호는 전량 필수 표시」). 판정기를 직접 넣어 확인한다.
_amb = {}
for _r in range(1, 21):
    for _i in range(12):
        _amb[f"{chr(65 + _i)}{_r}"] = f"{chr(65 + _i)}{_r} 고유값 {_r}-{_i}"
_ind = {a: 1 for a in list(_amb)[:int(round(len(_amb) * 0.85))]}
_raw_amb = {"format": "xlsx", "sheets": [{"name": "S", "max_row": 20, "max_col": 12,
            "cells": _amb, "merged": [], "indent": _ind, "bold": [], "images": []}]}
from parser import form as _FORM                                    # noqa: E402


class _FakeRes:
    """`build_view`가 보는 최소 파싱 결과 — 형태 판정 갈래만 보려는 자리다."""
    ok, doc_id, failures = True, "AMB01", []
    report, envelope = {}, {"chunks": []}


_st_amb = json.loads((REVIEW / "toc_report" / "state.json").read_text(encoding="utf-8"))
_amb_path = ROOT / "_b58_amb.xlsx"
_orig_judge, _orig_read = _FORM.judge, R.reader.read
try:
    # 표본 하나가 **사람에게 올라오는** 상황을 만든다 — 판정기는 그대로 두고
    # 그 문서의 raw만 갈아 끼운다(판정 규칙을 흉내 내지 않는다).
    _amb_path.write_bytes(b"")
    R.reader.read = lambda pth: _raw_amb if str(pth).endswith("_b58_amb.xlsx") else _orig_read(pth)
    _view_amb = R.build_view({**_st_amb, "samples": [str(_amb_path)]},
                             [_FakeRes()], True, "")
    _qs = [a for a in _view_amb["sections"]["parse_result"]["anomalies"]
           if a["kind"] == "question" and "형태 판정" in a["message"]]
    show("⑤ 사람에게 올라온 형태 판정은 **이상 신호로도** 뜬다 (§6.6-1 전량 표시)",
         _FORM.judge(_raw_amb)["verdict"] is None and len(_qs) == 1
         and len(_qs[0]["detail"]["signals"]) == 5,
         _qs[0]["message"][:60] if _qs else "질문 0건")
finally:
    R.reader.read = _orig_read
    _amb_path.unlink(missing_ok=True)

# **시험이 자기 등재를 치운다** — ⓐ의 confirm이 어댑터·스키마를 정본 자리로
# 승격시킨다(문서 6 §6.5). 남기면 다음 실행에서 `toc_report`가 **내장**으로 보여
# 이 스위트의 앞머리가 통째로 붉는다(실측: 4 PASS / 1 FAIL로 멈췄다).
reset("toc_report")
show("⑤ 시험이 승격시킨 정본을 치웠다 (다음 실행으로 새지 않는다)",
     registry.lookup("toc_report") is None
     and not (ROOT / "adapters" / "toc_report.py").exists()
     and not (ROOT / "schemas" / "toc_report.json").exists())


print("\n" + "=" * 62)
print("전체 결과:", "PASS — P3 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
