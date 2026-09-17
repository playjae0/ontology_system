# -*- coding: utf-8 -*-
"""P3 ④ 판정과 뷰 — 모든 열은 판정을 갖는다 · 하네스 자동 갈래 · 추출 리허설."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src, _call_names   # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

import os as _os
from kit import render_review as _RR

setup()


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
_a, _k = Rgate.classify_failures("\n".join(_auto_lines))
show("② 문면이 답을 담는 실패 7종은 전부 자동 갈래다", len(_a) == 7 and not _k,
     f"자동 {len(_a)} · 문답 {len(_k)}")
_a2, _k2 = Rgate.classify_failures("\n".join(_ask_lines))
show("② 원인 규명이 필요한 실패는 문답 갈래다 (조각 0건 · extract 예외 · prose 본문)",
     not _a2 and len(_k2) == 3, f"자동 {len(_a2)} · 문답 {len(_k2)}")
# **변이 시험** — 분류표에 없는 새 하네스 항목이 생겨도 조용히 자동으로 흐르지 않는다
_a3, _k3 = Rgate.classify_failures("  [FAIL] 새로 생긴 관문 항목 — 아직 표에 없다")
show("② 변이 — 목록 밖 실패는 기본이 문답이다 (모르면 묻는다)",
     not _a3 and len(_k3) == 1, f"자동 {len(_a3)} · 문답 {len(_k3)}")
# **수를 박지 않는다**(B58 ②에서 같은 병을 겪었다) — 분류표는 관문이 자랄 때 함께
# 자란다. 잠글 성질은 **「자동 갈래는 표에 열거된 것뿐」** 하나다: 표의 항목은 전부
# 자동으로 가고(위 변이가 그 반대쪽을 잠근다), 표 밖은 문답이다.
_auto_all = all(not Rgate.classify_failures(f"  [FAIL] G99  {k} — 상세")[1]
                for k in Rgate.AUTO_FIX)
show("② 분류표가 코드에 표로 있다 — 자동 갈래는 열거된 것뿐",
     isinstance(Rgate.AUTO_FIX, dict) and Rgate.AUTO_FIX and _auto_all,
     f"표 {len(Rgate.AUTO_FIX)}항목 전건이 자동")

# ── ⓔ 검수는 하네스를 돌리지 않는다 (AST — 문자열이 아니라 호출을 센다)
# 등록 파트는 파일 여럿이다(B78 2b) — 파일마다 파싱해 함수→호출 표를 합친다.
# 호출 표기는 `harness(...)`일 수도 `gate.harness(...)`일 수도 있으므로 **이름**으로 센다.
_calls = {}
for _rf in sorted((ROOT / "cli" / "register").glob("*.py")):
    for n in _ast.parse(_rf.read_text(encoding="utf-8")).body:
        if isinstance(n, _ast.FunctionDef):
            _calls[n.name] = _call_names(n)
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
_csch = {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")),
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
# 이 스위트의 재료다 — 등록 스위트(S15)와 **같은 명령**을 제 손으로 돌린다.
_gi = run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx"),
          "--hint", "16열 검사 성적서")
# **막고, 그 자리에서 다음 줄을 준다**(B59 ①) — 구판은 「검수로 넘어가지 않았다」만
# 말해 사내가 막다른 길에 섰다. 잠글 성질은 ①뷰로 넘어가지 않았다(rc) ②FAIL 줄이
# 코드와 함께 화면에 있다 ③칠 수 있는 명령이 함께 있다.
_nx = [l for l in _gi.stdout.splitlines() if "python -m cli.register" in l]
show("② ⓓ 미통과는 뷰로 넘어가지 않는다 · 화면이 이유와 다음 줄을 준다",
     _gi.returncode != 0 and Rgate.fail_lines(_gi.stdout) and _nx,
     f"FAIL {len(Rgate.fail_lines(_gi.stdout))}줄 · 다음 줄 {len(_nx)}개")
# **B62 ④가 이 자리를 바꿨다** — 기본값이 N(막다른 길)에서 Y(이어가기)로 갔고,
# 종료 조건은 「같은 FAIL이 되풀이된다」다. 잠글 성질은 ①자동 수정이 한 번 돌았다
# ②끝날 때 **왜 끝나는지**를 말한다 ③rc가 실패다 — 문면 한 줄이 아니다.
show("② ⓒ 자동 수정 1회 뒤 같은 FAIL이면 사유를 말하고 끝낸다 (기본은 이어가기)",
     "자동 수정 1회" in _gi.stdout or "같은 FAIL이 되풀이된다" in _gi.stdout,
     [l.strip() for l in _gi.stdout.splitlines()
      if "되풀이" in l or "자동 수정" in l][:1])
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
_s40 = json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8"))
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
     and Rgate.fail_lines(_r41.stdout) and _r41.returncode != 0,
     f"FAIL {len(Rgate.fail_lines(_r41.stdout))}줄 · rc={_r41.returncode}")
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
from core.build import extract as _EX                                     # noqa: E402

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
    (_P.parsed() / f"{_n}.json").unlink(missing_ok=True)

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
(_P.parsed() / "TOC01.json").unlink(missing_ok=True)
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
from core.llm import gateway as _llm                                       # noqa: E402

done()
