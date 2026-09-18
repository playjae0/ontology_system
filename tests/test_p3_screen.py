# -*- coding: utf-8 -*-
"""P3 ⑥ 화면 — 관문 전 구간 · 막는 이유와 다음 줄 · status·confirm 재실행 · 확정 요약."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src, _call_names   # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

from cli import interview as _IV
import ast as _ast
import contextlib as _ctx
import io as _io
import os as _os
import tempfile as _tf
from core.llm import gateway

setup()


print("\n■ B58 ② — 관문이 pipeline.parse 전 구간을 돈다")

_KIT_SRC = (ROOT / "kit" / "run_adapter.py").read_text(encoding="utf-8")

# ⓐ **관문과 검수 리허설이 같은 함수를 부른다.** 이것이 「관문 PASS 뒤 검수에서
# 기계 오류가 날 자리가 없다」의 근거다 — 두 곳이 다른 함수를 부르면 한쪽만 통과하는
# 경로가 생기고, 그 틈이 곧 사내가 겪던 「검수에서 처음 깨진다」다.
# **부르는 것을 센다**(AST) — 「pipeline.parse를 돈다」는 주석은 아무것도 돌리지 않는다.
_kit_calls = {n.func.attr for n in _ast.walk(_ast.parse(_KIT_SRC))
              if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)}
_REGSRC = _reg_src()
_reg_calls = {n.func.attr for n in _ast.walk(_ast.parse(_REGSRC))
              if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)}
show("②ⓐ 관문이 pipeline.parse를 **부른다** (검수 리허설과 같은 함수)",
     "parse" in _kit_calls and "parse" in _reg_calls)
show("②ⓐ 관문은 하네스 실물을 부르는 구조 그대로다 (재작성 아님)",
     "run_adapter.py" in _REGSRC)

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
_brk_ok, _brk_out = Rgate.harness(_BRK, _BRK.with_suffix(".json"), [RAW / "CP01.xlsx"])
_stages = _brk_out.split("⑤ 파서 전 구간")
show("②ⓑ 깨지는 검체가 관문에서 FAIL이다 (검수까지 가지 않는다)",
     not _brk_ok and len(_stages) == 2)
show("②ⓑ ①~④는 통과했다 — 구판 관문이 이 어댑터를 놓친 자리다",
     "[FAIL]" not in _stages[0], str([l.strip() for l in _stages[0].splitlines()
                                      if "[FAIL]" in l][:2]))
# **코드로 잰다**(B59 ①) — 라벨 문면은 바뀔 수 있지만 `G51`은 그 검사에 박힌
# 고정값이고, 예외 원문이 상세에 실려 있다는 것이 ②의 성질이다.
_f5 = Rgate.fail_lines(_stages[1])
show("②ⓑ 잡은 자리가 ⑤다 — G51(파서 전 구간)이 예외 원문과 함께 FAIL이다",
     [c for c, _l, _d in _f5] == ["G51"] and "unhashable" in _f5[0][2],
     str(_f5[:1]))

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
     not [q for q in (_P.extract() / "struct_maps").glob("_gate_*.json")],
     str([q.name for q in (_P.extract() / "struct_maps").glob("*.json")][:4]))


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
     _reg_src())
# **생성은 LLM을 켜지 않는다** — 비용 관문은 사람이 켜는 것이고, 그 자리가 review다.
# **성질은 「생성이 비용 스위치를 켜지 않는다」이지 화면에 어느 문장이 있느냐가
# 아니다**(B69 ② — 진행 줄이 표기 단위가 되면서 옛 문면이 사라졌다). 켜는 자리는
# review이고, 생성은 둘 다 끈 채로 부른다.
show("⑤ⓐ 생성의 뷰 산출에 비용 스위치가 꺼져 있다 (좌표 보조·추출 리허설)",
     "추출 리허설 끔" in _g5.stdout
     and "cmd_review(doc_type, llm_coord=False, extract=False)" in
     _reg_src()
     and "[좌표 태깅]" not in _g5.stdout)
# **review는 남는다** — 없애면 재생성 지시·좌표 보조·추출 리허설의 자리가 사라진다.
_r5 = run("review", "toc_report", "--rows", "200", "--no-llm-coord", "--no-extract")
show("⑤ review는 선택 명령으로 남는다 (고칠 때 들어가는 자리)",
     _r5.returncode == 0
     and (REVIEW / "toc_report" / "view.json").exists())
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
    _view_amb = Rview.build_view({**_st_amb, "samples": [str(_amb_path)]},
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
     and not (_P.adapters() / "toc_report.py").exists()
     and not (_P.schemas() / "toc_report.json").exists())


# ── B58 ⑥ 산출 스키마의 계열 분기 ────────────────────────────────────────
print("\n■ B58 ⑥ — prose 스키마는 role 집계를 요구하지 않는다")

# **잠글 성질 하나**: prose 계열의 `required`에 role 키가 없다. 스키마 `required`는
# 모델이 빠져나갈 수 없는 자리라, 열이 없는 산문 문서에서 **있지도 않은 role
# 집계를 지어내게** 한다. 화면 문면이 아니라 스키마의 모양을 본다.
show("⑥ prose 산출 스키마의 required에 role 키가 없다",
     not (set(Rdraft.ROLE_KEYS) & set(Rdraft.generate_schema("prose")["required"])),
     str(sorted(set(Rdraft.ROLE_KEYS) & set(Rdraft.generate_schema("prose")["required"]))))
# **strict 요건은 「required = properties 전량」이다**(B44 실측 400) — `required`에서만
# 빼면 게이트웨이가 요청을 통째로 거부한다. 계열 전부에서 그 요건이 선다.
show("⑥ 계열 전부가 strict 요건을 지킨다 (required = properties 전량)",
     all(set(Rdraft.generate_schema(k)["required"]) == set(Rdraft.generate_schema(k)["properties"])
         for k in ("table", "prose", None)))
show("⑥ table 계열은 종전대로 role 집계를 요구한다 (해제는 prose에서만이다)",
     set(Rdraft.ROLE_KEYS) <= set(Rdraft.generate_schema("table")["required"]))


# ── B59 관문이 막을 때 사람이 다음 줄을 안다 ────────────────────────────
print("\n■ B59 — 막는 것은 맞다. 안 알려주는 게 틀렸다")

import re as _re                                              # noqa: E402
# 관문은 파일 넷이다(B78 2c — 표·화면·검사·실행기). 라벨은 **파트 전체**에서 센다.
_KIT59 = " ".join(_p.read_text(encoding="utf-8")
                  for _p in sorted((ROOT / "kit").glob("gate_*.py"))
                  ) + (ROOT / "kit" / "run_adapter.py").read_text(encoding="utf-8")
_REG59 = _reg_src()

# ①ⓑ **셋이 같은 함수를 부른다** — 문면이 세 벌이면 그중 하나만 고쳐지는 날이 오고,
# 사람은 어느 화면을 믿을지 모른다. 호출을 센다(주석이 아니다).
# 파트가 파일 여럿이므로(B78 2b) 파일마다 파싱하고, 호출 표기는 **이름**으로 센다
# (`gate_block(...)`과 `gate.gate_block(...)`은 같은 호출이다).
_calls59 = {}
for _rf59 in sorted((ROOT / "cli" / "register").glob("*.py")):
    for _n in _ast.walk(_ast.parse(_rf59.read_text(encoding="utf-8"))):
        if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            _calls59[_n.name] = set(_call_names(_n))
show("①ⓑ confirm·review·status 셋이 **같은 함수**(gate_block)를 부른다",
     all("gate_block" in _calls59.get(f, set())
         for f in ("cmd_confirm", "cmd_review", "cmd_status")),
     str({f: "gate_block" in _calls59.get(f, set())
          for f in ("cmd_confirm", "cmd_review", "cmd_status")}))

# ①ⓒ **태그는 라벨에 1:1로 박힌다** — 코드 없는 라벨 0 · 한 코드에 두 라벨 0.
# 순번이 아니라 고정값이라야 단이 늘어도 밀리지 않는다.
_labels59 = _re.findall(r'show\(\s*f?"([^"]+)"', _KIT59)
_nocode = [l for l in _labels59 if not _re.match(r"^G[0-9A-Z]{2}  ", l)]
_bycode = {}
for _l in _labels59:
    _bycode.setdefault(_l[:3], set()).add(_l[5:])
_dup59 = {c: v for c, v in _bycode.items() if len(v) > 1}
show("①ⓒ 모든 판정 라벨에 태그가 있다 (코드 없는 라벨 0)",
     not _nocode and len(_labels59) >= 40, f"라벨 {len(_labels59)} · 무태그 {len(_nocode)}")
show("①ⓒ 태그와 라벨이 1:1이다 (한 태그에 두 라벨 0)",
     not _dup59 and len(_bycode) >= 35, f"태그 {len(_bycode)}종 · 충돌 {len(_dup59)}")
# **문면 규격의 정본은 킷이다** — register가 제 정규식을 따로 갖지 않는다.
show("①ⓒ 판정 줄 문면 규격이 한 자리다 (register가 킷의 LINE_RE를 읽는다)",
     "LINE_RE" in _KIT59 and "_kit_line_re()" in _REG59
     and Rgate._kit_line_re() == _re.search(r'^LINE_RE = r"(.+)"$', _KIT59, _re.M).group(1))
# **블록이 코드·라벨·상세를 되살린다** — 사람이 state.json을 열지 않는다.
_demo59 = ('  [PASS] G11  문법 오류 없음\n'
           '  [FAIL] G13  규약 10 — 자기완결 연산을 재구현하지 않았다 (x)  — 정의 [a]\n'
           '  [FAIL] G51  파서 전 구간이 예외 없이 완주 (y)  — TypeError: boom')
show("① FAIL 줄만 코드·라벨·상세로 되살아난다 (PASS는 섞이지 않는다)",
     [x[0] for x in Rgate.fail_lines(_demo59)] == ["G13", "G51"]
     and Rgate.fail_lines(_demo59)[1][2] == "TypeError: boom")

# ①ⓓ **사람 화면에서 「검수」를 쓰지 않는다** — 사람이 할 수 없는 일의 이름이었다.
# 주석·docstring은 대상이 아니다(판 이력과 근거는 남아야 한다).
_screen59 = []
for _ln in _REG59.splitlines():
    _t = _ln.strip()
    if "검수" not in _t or _t.startswith("#"):
        continue
    if "print(" in _t or "SystemExit(" in _t:
        _screen59.append(_t[:80])
show("①ⓓ 사람 화면 문면에 「검수」가 0건이다 (기계 관문 / 뷰 확인으로 갈렸다)",
     not _screen59, str(_screen59[:2]))

# ②ⓑ **⑤단 라벨이 전부 분류돼 있다** — 어디로도 안 가는 라벨이 0이어야
# 「들어갔을 때 나갈 길」이 막히지 않는다.
_five59 = sorted({l for l in _re.findall(
    r'show\(\s*f?"([^"]+)"',
    _KIT59.split("def run_pipeline")[1].split("\n# ---")[0])})
_unclassified = [l for l in _five59
                 if l[:3] not in Rgate.GATE_SELF
                 and not any(k in l[5:] for k in Rgate.AUTO_FIX)
                 and l[:3] not in Rgate.WITH_EVIDENCE]
show("②ⓑ ⑤단 라벨 중 분류되지 않은 것이 0이다 (auto / 원문 동봉 / 관문 자체)",
     not _unclassified and len(_five59) == 4, str(_unclassified))

# ②ⓒ **원문이 지시에 실린다** — 사람이 답해도 사라지지 않는다. 둘은 짝이다.
show("②ⓒ 문답 지시에 관문 판정 원문이 함께 간다 (답만 보내지 않는다)",
     '"[관문 판정 원문]' in _REG59.replace("\\n", "").replace("\n", "")
     or "[관문 판정 원문]" in _REG59)

# ③ⓒ **전부 산문 포맷이면 LLM 호출 0** — 그 길로 안 들어가게 하는 것이 먼저다.
reset("pptx_b59")
# **플래그 없이** 부른다 — 재는 것이 「기본값이 고정 어댑터인가」다. `run()` 헬퍼는
# LLM 경로를 재려고 `--no-basic`을 붙이므로 여기서는 쓰지 않는다.
_g59 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "generate",
                       "pptx_b59", "quality", str(RAW / "PPT_basic.pptx"),
                       "--allow-mock"], capture_output=True, text=True,
                      cwd=str(ROOT), stdin=subprocess.DEVNULL)
_st59 = json.loads((REVIEW / "pptx_b59" / "state.json").read_text(encoding="utf-8"))
show("③ⓒ 전부 산문 포맷이고 플래그가 없으면 고정 어댑터로 가고 LLM 호출 0",
     _g59.returncode == 0 and _st59.get("use_basic") is True
     and "호출 0회" in _g59.stdout, _g59.stdout[-80:].strip()[:70])
show("③ⓑ --no-basic이면 LLM 생성 경로로 간다 (사람이 고를 수 있다)",
     "--no-basic" in _REG59 and "no_basic=no_basic" in _REG59)
reset("pptx_b59")

# ④ **어느 폴더·어느 판으로 돌았나**가 관문 산출 첫 줄에 있다.
_ok59, _out59 = Rgate.harness(ROOT / "tests/fixtures/adapters/cp.py",
                          ROOT / "tests/fixtures/schemas/cp.json", [RAW / "CP01.xlsx"])
show("④ 관문 산출 첫 줄이 ROOT를 밝힌다 (폴더를 나눠 쓸 때 어느 사본인가)",
     _out59.splitlines()[0].startswith("[관문] ROOT=")
     and str(ROOT) in _out59.splitlines()[0], _out59.splitlines()[0][:70])


# ── B60 ① 관문은 다시 돈다 — 저장된 판정을 믿지 않는다 ────────────────────
print("\n■ B60 ① — status·confirm은 지금 코드의 관문을 다시 돈다")

_REG60 = _reg_src()
# ①ⓑ **호출 계수** — status·confirm이 regate를 거쳐 machine_gate에 닿는다.
_calls60 = {}
for _rf60 in sorted((ROOT / "cli" / "register").glob("*.py")):
    for _n in _ast.walk(_ast.parse(_rf60.read_text(encoding="utf-8"))):
        if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            _calls60[_n.name] = set(_call_names(_n))
show("①ⓑ status·confirm이 관문을 다시 돈다 (regate → machine_gate 호출 계수)",
     all("regate" in _calls60.get(f, set()) for f in ("cmd_status", "cmd_confirm"))
     and "machine_gate" in _calls60.get("regate", set()),
     str({f: "regate" in _calls60.get(f, set()) for f in ("cmd_status", "cmd_confirm")}))
# 재실행 갈래는 **재생성·문답을 타지 않는다** — 상태를 보러 온 사람이 LLM을 시작하게
# 두지 않는다. `fix=False`가 그 갈래이고 regate가 그것을 쓴다.
show("① 재실행은 판정만 낸다 — 재생성·문답 없음 (fix=False)",
     "fix=False" in _REG60.split("def regate")[1].split("\ndef ")[0])
# ①ⓓ 폴백 문면이 없다 — 판정 줄이 없으면 그 자리에서 돈다.
show("①ⓓ 「생성을 다시 돌려라」 문면 0건 (판정 줄이 없으면 돌린다)",
     "생성을 다시 돌려라" not in _REG60)

# ①ⓒ **저장값이 PASS인데 어댑터가 디스크에서 규약 10 위반으로 바뀌면 confirm이 막는다.**
_fx60 = Path(_tf.mkdtemp(prefix="fx60_", dir=str(ROOT)))
(_fx60 / "fixtures/adapters").mkdir(parents=True)
(_fx60 / "fixtures/schemas").mkdir(parents=True)
_cp60 = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
(_fx60 / "fixtures/adapters/cp60.py").write_text(
    _cp60.replace('"doc_type": "cp"', '"doc_type": "cp60"', 1), encoding="utf-8")
(_fx60 / "fixtures/schemas/cp60.json").write_text(json.dumps(
    {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")), "doc_type": "cp60"},
    ensure_ascii=False), encoding="utf-8")
_e60 = {**_os.environ, "ONTO_FIXTURES": str(_fx60)}


def _reg60(*a):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *a,
                           "--allow-mock"], capture_output=True, text=True,
                          cwd=str(ROOT), env=_e60, stdin=subprocess.DEVNULL)


reset("cp60")
_reg60("generate", "cp60", "process", str(RAW / "CP01.xlsx"), "--no-basic")
_st60 = json.loads((REVIEW / "cp60" / "state.json").read_text(encoding="utf-8"))
_saved_pass = _st60["machine_gate"] == "PASS"
# 디스크의 어댑터만 바꾼다 — 저장값은 PASS 그대로다.
# **바꿀 곳은 작업 사본이다**(B62 ①-c) — 관문 입구에서 시스템이 `review/`로 복사해
# 거기에 채우므로, 그 뒤로 관문이 읽는 어댑터는 `state.adapter`가 가리키는 사본이다.
# fixture 원본은 손대지 않는 자리라(D-26) 거기를 고치면 아무 데도 안 닿는다.
_ad60 = Rdraft._at(_st60["adapter"])
_ad60.write_text(_ad60.read_text(encoding="utf-8").replace(
    "\nADAPTER = {",
    "\n\ndef _expand_merged(sheet):\n    return dict(sheet.get('cells') or {})\n\n\nADAPTER = {", 1),
    encoding="utf-8")
_c60 = _reg60("confirm", "cp60", "--by", "검수자")
_st60b = json.loads((REVIEW / "cp60" / "state.json").read_text(encoding="utf-8"))
show("①ⓒ 저장값 PASS + 어댑터 규약 10 위반 → confirm이 FAIL로 막는다 (저장값을 안 믿는다)",
     _saved_pass and _c60.returncode != 0 and registry.lookup("cp60") is None
     and _st60b["machine_gate"] == "FAIL"
     and "G13" in [c for c, _l, _d in Rgate.fail_lines(_c60.stdout)],
     f"저장 PASS={_saved_pass} · rc={_c60.returncode} · 지금={_st60b['machine_gate']}")
# 옛 판(태그 없는 harness_out)을 두고 status → 관문이 돌고 태그 붙은 블록이 뜬다.
_st60b["harness_out"] = _re.sub(r"(\[(?:PASS|FAIL)\])\s+G[0-9A-Z]{2}\s\s", r"\1 ", _st60b["harness_out"])
(REVIEW / "cp60" / "state.json").write_text(json.dumps(_st60b, ensure_ascii=False), encoding="utf-8")
_s60 = _reg60("status", "cp60")
show("①ⓐ 태그 없는 옛 harness_out에도 status가 관문을 돌려 태그 붙은 블록을 낸다",
     _s60.returncode != 0 and [c for c, _l, _d in Rgate.fail_lines(_s60.stdout)] == ["G13"]
     and "[관문] ROOT=" in json.loads(
         (REVIEW / "cp60" / "state.json").read_text(encoding="utf-8"))["harness_out"])
reset("cp60")
shutil.rmtree(_fx60, ignore_errors=True)


# ── B60 ② 문답의 확정 요약이 생성의 입력이다 ──────────────────────────────
print("\n■ B60 ② — 대화는 이력, 판단은 확정 요약 하나")

_fx62 = Path(_tf.mkdtemp(prefix="fx62_", dir=str(ROOT)))
(_fx62 / "fixtures/adapters").mkdir(parents=True)
(_fx62 / "fixtures/schemas").mkdir(parents=True)
(_fx62 / "fixtures/adapters/cp62.py").write_text(
    (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
    .replace('"doc_type": "cp"', '"doc_type": "cp62"', 1), encoding="utf-8")
(_fx62 / "fixtures/schemas/cp62.json").write_text(json.dumps(
    {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")), "doc_type": "cp62"},
    ensure_ascii=False), encoding="utf-8")
_e62 = {**_os.environ, "ONTO_FIXTURES": str(_fx62), "ONTO_DUMP_PROMPT": "1"}


def _reg62(*a, feed=""):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *a,
                           "--allow-mock", "--no-basic"] if a[0] == "generate" else
                          [sys.executable, str(ROOT / "run.py"), "register", *a, "--allow-mock"],
                          capture_output=True, text=True, cwd=str(ROOT), env=_e62, input=feed)


reset("cp62")
# 문답: r1 Q1=«1»(위 값 채움)·교정 빈줄 → r2 교정 문장 → r3 «진행» → 요약 확인 «Y»
_g62 = _reg62("generate", "cp62", "process", str(RAW / "CP01.xlsx"), "--interview",
              feed="1\n\n헤더 행은 2행이다 — 1행은 제목\n진행\nY\n")
_pk62 = json.loads((REVIEW / "cp62" / "input_package.json").read_text(encoding="utf-8"))
_b62 = Rivlog._hint_batches(_pk62["human"]["hint"])[-1]
_pr62 = (REVIEW / "cp62" / "prompt_rendered.md").read_text(encoding="utf-8")
_rd62 = Rivlog.read_log("cp62").get(_b62["at"]) or []

# ②ⓑ **프롬프트에는 확정 사항만** — 전문은 싣지 않는다.
show("②ⓑ 생성 프롬프트에 [확정 사항]이 있고 [문답 라운드 전문이 없다",
     "[확정 사항" in _pr62 and "[문답 라운드" not in _pr62
     and all(d["decision"] in _pr62 for d in _b62["decisions"]),
     f"확정 {len(_b62['decisions'])}항목 · 라운드 {len(_rd62)}")
# 전문은 **사라지지 않는다** — 자리가 로그로 옮겨졌을 뿐이다(B62 ②). 잠글 성질은
# 그대로다: 사람의 답은 다시 못 만드니 어딘가에 남아 있어야 한다.
show("② 라운드 전문은 로그에 그대로 남는다 (이력 · 재현 근거)",
     len(_rd62) >= 2 and all("understanding" in r for r in _rd62)
     and "rounds" not in _b62)
# ②ⓓ **사람 4키·시스템 5키 불변** — decisions는 hint 안의 묶음에 산다.
show("②ⓓ 사람 4키·시스템 5키 불변 — decisions는 human.hint 묶음 안이다",
     set(_pk62["human"]) == {"doc_type", "layer", "samples", "hint"}
     and len(_pk62["system"]) == 5 and "decisions" in _b62
     and "decisions" not in _pk62["human"] and "decisions" not in _pk62["system"])
# ②ⓒ **--instruct가 결정을 뒤집는다** — topic이 든 지시는 그 항목을 바꾼다.
_topic62 = _b62["decisions"][0]["topic"]
_old_dec = _b62["decisions"][0]["decision"]
_reg62("review", "cp62", "--instruct", f"{_topic62}: 행 독립으로 읽어라", "--no-llm-coord")
_pk62b = json.loads((REVIEW / "cp62" / "input_package.json").read_text(encoding="utf-8"))
_d62 = [d for b in Rivlog._hint_batches(_pk62b["human"]["hint"]) for d in b["decisions"]
        if d["topic"] == _topic62][0]
show("②ⓒ --instruct로 결정을 뒤집으면 decisions의 그 항목이 바뀐다 (reason에 사람 지시 rev)",
     _d62["decision"] != _old_dec and "행 독립" in _d62["decision"]
     and "사람 지시 (rev" in _d62["reason"],
     _d62["reason"][:40])
# topic이 안 든 지시는 **새 항목**으로 붙는다 — 지시를 버리지 않는다.
_n_before = sum(len(b["decisions"]) for b in Rivlog._hint_batches(_pk62b["human"]["hint"]))
_reg62("review", "cp62", "--instruct", "복수값 구분자에 슬래시도 받아라", "--no-llm-coord")
_pk62c = json.loads((REVIEW / "cp62" / "input_package.json").read_text(encoding="utf-8"))
_n_after = sum(len(b["decisions"]) for b in Rivlog._hint_batches(_pk62c["human"]["hint"]))
show("②ⓒ topic이 안 든 지시는 새 항목으로 붙는다 (지시를 버리지 않는다)",
     _n_after == _n_before + 1)
# ②ⓔ **크기** — 요약이 전문보다 짧다(변이 시험: 전문을 실었을 때와 비교).
from cli.prompt import _decisions_block as _DB                       # noqa: E402
_bs62 = Rivlog._hint_batches(_pk62c["human"]["hint"])
_summary62 = _DB(_bs62)
_log62 = Rivlog.read_log("cp62")
_transcript62 = "\n".join(
    f"[문답 라운드 {r.get('round')}] 이해: {r.get('understanding', '')}"
    + (f"\n  사람의 답/교정: {r['answer']}" if r.get("answer") else "")
    for b in _bs62 for r in (_log62.get(b["at"]) or []))
show("②ⓔ 확정 요약이 라운드 전문보다 짧다 (프롬프트가 줄어든다)",
     0 < len(_summary62) < len(_transcript62),
     f"요약 {len(_summary62)}자 · 전문 {len(_transcript62)}자")
# **힌트만 준 경우** — 힌트 문장이 그대로 한 항목. 자리는 항상 있다.
reset("cp62")
_reg62("generate", "cp62", "process", str(RAW / "CP01.xlsx"), "--hint", "3~7행 병합은 위 값 채움")
_pk62h = json.loads((REVIEW / "cp62" / "input_package.json").read_text(encoding="utf-8"))
_dh = [d for b in Rivlog._hint_batches(_pk62h["human"]["hint"]) for d in b["decisions"]]
show("② 문답 없이 --hint만 주면 힌트 문장이 확정 사항 한 항목이다 (자리는 항상 있다)",
     len(_dh) == 1 and _dh[0]["decision"] == "3~7행 병합은 위 값 채움"
     and "[확정 사항" in (REVIEW / "cp62" / "prompt_rendered.md").read_text(encoding="utf-8"))
# **LLM 지점이 늘지 않는다** — 요약은 문답 라운드와 같은 자리다. B63 ②가 호출 태그를
# `interview`로 갈랐지만 **지점은 그대로 ⑤** 하나다(문서 7 §7.6-B-2의 닫힌 9종).
_IVSRC = (ROOT / "cli" / "interview.py").read_text(encoding="utf-8")
_pt_of = lambda fn: set(_re.findall(
    r'point="([a-z_]+)"', _IVSRC.split(f"def {fn}")[1].split("\ndef ")[0]))
show("② 요약은 새 LLM 지점이 아니다 (문답 라운드와 같은 point · 지점은 ⑤ 하나)",
     _pt_of("_summarize") == _pt_of("_interview_round") != set()
     and gateway.point_label("interview") == gateway.POINTS["generate"]
     and set(_IV.DECISIONS_SCHEMA["required"]) == set(_IV.DECISIONS_SCHEMA["properties"]),
     f"{sorted(_pt_of('_summarize'))} → {gateway.point_label('interview')}")
# **수정 흐름** — «수정 2»면 그 항목만 바뀌고 나머지는 그대로다(단위 시험 · _ask 패치).
_hist62 = [{"round": 1, "understanding": "u1",
            "questions": [{"q": "헤더 행", "options": ["1행", "2행"]}],
            "answers": [{"q": "헤더 행", "answer": "1", "chosen": "1행"}],
            "answer": "헤더 행 → 1행", "progress": {}},
           {"round": 2, "understanding": "u2", "questions": [], "answers": [],
            "answer": "교정: 병합은 위 값 채움", "progress": {}}]
_feed62 = iter(["수정 1", "2행이다 — 1행은 제목", "Y"])
_ask62 = _IV._ask
_IV._ask = lambda prompt="": next(_feed62)
try:
    with _ctx.redirect_stdout(_io.StringIO()):
        _dec62 = _IV.finalize({"human": {"hint": ""}, "system": {}}, _hist62)
finally:
    _IV._ask = _ask62
show("②ⓐ 요약 확인에서 «수정 n»은 그 항목만 바꾼다 (나머지 그대로)",
     len(_dec62) == 2 and _dec62[0]["decision"] == "2행이다 — 1행은 제목"
     and "수정" in _dec62[0]["reason"] and _dec62[1]["decision"] == "병합은 위 값 채움")
reset("cp62")
shutil.rmtree(_fx62, ignore_errors=True)


# ── B62 ①ⓓ·③·④ 관문 입구에서 시스템이 쓴다 ───────────────────────────────

done()
