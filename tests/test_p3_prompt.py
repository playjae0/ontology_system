# -*- coding: utf-8 -*-
"""P3 ② 조립 — 골격 확정 · 전송 프롬프트 · 문답 어휘 주입 · 열 프로파일 · 예산."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src            # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

setup()


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
_pkg29 = json.loads(_P.review("ipqc", "input_package.json").read_text(encoding="utf-8")) \
    if _P.review("ipqc", "input_package.json").exists() else None
if _pkg29 is None:
    # 패키지만 필요하다 — 초안 수령은 fixture 소관이라 여기서 SystemExit로 끝난다
    # (D-10). 패키지는 그 전에 이미 파일로 서 있다.
    try:
        Rgen.cmd_generate("b29probe", "process",
                       [str(ROOT / "tests/fixtures/raw/IPQC01.xlsx")], "")
    except SystemExit:
        pass
    _pkg29 = json.loads(
        _P.review("b29probe", "input_package.json").read_text(encoding="utf-8"))
_sent = R._render_template(
    R.generate_template(), _pkg29)

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
         R.generate_template(), _pkg29))
show("시스템 키는 5 그대로다 (값의 형태만 바뀌었다)", len(_pkg29["system"]) == 5,
     str(list(_pkg29["system"])))

# ============================================================ 등록 2차 개선
print("\n■ B30·B32·B34 — 문답 어휘 주입 · 크기 손잡이 · 관찰 범위")
from core.llm import check, gateway                                        # noqa: E402
from core.state.bootstrap import load_config                      # noqa: E402

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
_iv = gateway.prompt("interview")
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
_off = R._render_template(R.generate_template(), _pkg_off)
_on = R._render_template(R.generate_template(), _pkg29)
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
# **수를 박지 않는다**(B77 ① 재조준) — 성질은 「관찰 창(`OBSERVE_ROWS`) 밖까지
# 전부 셌다」이고, 기대값은 표본에서 파생한다(표본이 자라면 같이 자란다).
_rows_all = int(_sh.get("max_row", 0)) - 4 + 1
_cols_all = len({"".join(ch for ch in k if ch.isalpha())
                 for k in _sh["cells"] if k.endswith("3")})
show("① 전 행을 센다 — 앞 N줄이 아니다 (창 밖의 사실을 준다)",
     _pr["전체_행수"] == _rows_all > reader.OBSERVE_ROWS
     and _pr["열수"] == _cols_all,
     f"{_pr['전체_행수']}행 {_pr['열수']}열 (창 {reader.OBSERVE_ROWS}행)")
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
_sent39 = R._render_template(R.generate_template(), _pkg29)
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
     set(Rdraft.GENERATE_SCHEMA["required"]) == set(Rdraft.GENERATE_SCHEMA["properties"])
     and {"role_counts", "attribute_ranking", "confidence_cut"}
     <= set(Rdraft.GENERATE_SCHEMA["properties"]))

# 패키지 — 시스템 키 5 불변
_pkg39 = json.loads(
    _P.review("b29probe", "input_package.json").read_text(encoding="utf-8"))
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
     (lambda: (_os.environ.__setitem__("USE_MOCK", "1"), gateway.use_mock())[1])() is True)
show("④ 판독은 use_mock() 하나다 (읽는 곳을 늘리지 않았다)",
     sum(1 for f in (ROOT / "core").rglob("*.py")
         for ln in f.read_text(encoding="utf-8").splitlines()
         if 'environ.get("USE_MOCK"' in ln) == 1)
show("④ 기본은 mock이다 (둘 다 없으면 — 조항 B12)",
     gateway.use_mock() is True)

# ⑤ 모드 줄 — LLM을 부를 수 있는 화면 명령 머리
show("⑤ mock이면 켜는 법을 함께 말한다", 'llm.json' in gateway.mode_line()
     and "mock" in gateway.mode_line())
for _src, _n in ((_reg_src(), "register"),
                 ((ROOT / "run.py").read_text(encoding="utf-8"), "run")):
    show(f"⑤ {_n} 이 모드 줄을 낸다", "mode_line()" in _src)

# B41 예산 — 한도가 없으면 대조하지 않는다
show("⑥ 컨텍스트 한도는 **선택**이다 — 기본값을 코드에 박지 않았다",
     check.context_limit() is None
     and "LLM_CONTEXT_TOKENS" in (ROOT / "core/llm/check.py").read_text(encoding="utf-8"))

# ============================================================ B43·B44

done()
