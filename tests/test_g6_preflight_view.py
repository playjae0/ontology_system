# -*- coding: utf-8 -*-
"""G6 ⑮ 비용 전 사전 점검 · 토큰 입력/출력 · 설정 파일 판정 · 색 세 층 · 이어지는 표 (B98).

창작 표본(mock · CP01 · IMG01 · RFQ01 · 실호출 갈래는 시험 주입)으로 메커니즘을 잰다 — 수치는
근거가 아니다([정정] 50).

잠그는 성질:
  ⓐ 임베딩 갈래가 막힌 설정이면 ingest-file이 **파싱 전에** 멈춘다 · LLM 추가 0 · 다음 줄 --narrow overlap
  ⓑ 그림 입력이 막히면 그림 있는 문서는 멈춤(--no-images) · 그림 없는 문서는 건너뜀
  ⓒ 공통 config 거부 상태 → 사전 점검에서 멈춘다(구축 전 · 파싱 0)
  ⓓ ingest-dir은 사전 점검 1회
  ⓔ 설정 파일 둘 → llm-check·doctor가 읽은 것과 무시된 것을 말한다
  ⓕ 토큰 표기는 한 함수(입력·출력) · 미제공이면 그 문면 · 화면에 합계만 찍는 자리 0
  ⓖ 구축 실패 → 실패 줄에 추출 체크포인트 보존 · 다음 줄
  ⓗ 표: 한글 긴 표기·줄바꿈 섞인 표기·80칸에서 칸 정렬 유지 · 30초 행이 행 중간에 끼지 않는다
  ⓘ 색: 파이프·NO_COLOR에서 ESC 0 · 새 층에 빨강·노랑 0(특이점 전용)
"""
from __future__ import annotations

import contextlib
import io
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _ingest, _register, _run, _unregister, done, json, os,   # noqa: F401
                       store)
from cli import _screen                       # noqa: E402
from cli import ingest as IG                  # noqa: E402
from cli import preflight as PF               # noqa: E402
from core.build import extract as EX          # noqa: E402
from core.llm import check as CK              # noqa: E402
from core.llm import gateway, narrow          # noqa: E402
from core.llm import preflight as PRE         # noqa: E402

RAW = ROOT / "tests" / "fixtures" / "raw"


def _cap(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


def _fake_chat(cfg, add):
    """시험 주입 — 채팅 왕복 통과(사용량 있음)."""
    add("②", "도달", True)
    return {"choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}}


def _fail_stage(i, label, detail):
    def stage(cfg, add):
        add(i, label, False, detail)
    return stage


init.init(fresh_=True, all_=True)
bootstrap("process", echo=False)

print("\n■ B98 ① 사전 점검 — LLM을 쓰기 전에")
_keep = (PRE._live, CK.chat_roundtrip, CK.embed_stage, CK.image_stage, narrow.narrow_choice)
PRE._live = lambda: True
CK.chat_roundtrip = _fake_chat
CK.embed_stage = _fail_stage("⑥", "임베딩", "GatewayError: HTTP 404 /embeddings")
CK.image_stage = _fail_stage("⑦", "이미지 입력", "HTTP 400 — 이미지 입력을 받지 않는다")
narrow.narrow_choice = lambda: ("embed", "설정")
os.environ.update(LLM_GATEWAY_URL="http://시험", CHAT_MODEL="m", EMBED_MODEL="e")
try:
    _c0 = gateway.usage_total()["calls"]
    _row, _o = _cap(IG.ingest_file, str(RAW / "CP01.xlsx"), "cp", ask=False)
    show("ⓐ 임베딩 갈래가 막히면 ingest-file이 파싱 전에 멈춘다 · LLM 추가 0(점검 왕복 1 외) · "
         "다음 줄 --narrow overlap",
         _row.get("preflight_fail") and not _P.parsed("CP01.json").exists()
         and "**임베딩**에서 멈춘다" in _o and "--narrow overlap" in _o
         and "좌표 태깅" not in _o and gateway.usage_total()["calls"] - _c0 == 1,
         [l.strip() for l in _o.splitlines() if "사전 점검" in l][:1])
    narrow.narrow_choice = lambda: ("overlap", "설정")
    _ok_img, _o_img = _cap(IG._preflight_once, str(RAW / "IMG01.xlsx"), None, False)
    _ok_cp, _o_cp = _cap(IG._preflight_once, str(RAW / "CP01.xlsx"), None, False)
    show("ⓑ 그림 입력이 막히면 그림 있는 문서는 멈춤(--no-images) · 그림 없는 문서는 건너뜀",
         PF.has_images(RAW / "IMG01.xlsx") and not PF.has_images(RAW / "CP01.xlsx")
         and _ok_img is False and "--no-images" in _o_img
         and _ok_cp is True and "그림(건너뜀)" in _o_cp,
         [l.strip()[:80] for l in (_o_img + _o_cp).splitlines() if "사전 점검" in l])
finally:
    PRE._live, CK.chat_roundtrip, CK.embed_stage, CK.image_stage, narrow.narrow_choice = _keep
    for k in ("LLM_GATEWAY_URL", "CHAT_MODEL", "EMBED_MODEL"):
        os.environ.pop(k, None)

_cfgp = _P.layers("process", "config.json")
_orig_cfg = _cfgp.read_text(encoding="utf-8")
_cfgp.write_text(json.dumps({**json.loads(_orig_cfg), "canonical_scope": {
    "bind_categories": ["Property"], "sep": "::"}}, ensure_ascii=False), encoding="utf-8")
_oc = _run("ingest-file", str(RAW / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock")
_cfgp.write_text(_orig_cfg, encoding="utf-8")
show("ⓒ 공통 config 거부 상태 → 사전 점검에서 멈춘다(구축 전 · 파싱 0) · 다음 줄 bootstrap --dry-run",
     "**공통 config**에서 멈춘다" in _oc and "canonical_scope" in _oc
     and "bootstrap --dry-run" in _oc and "좌표 태깅" not in _oc
     and not _P.parsed("CP01.json").exists(),
     [l.strip()[:80] for l in _oc.splitlines() if "사전 점검" in l][:1])

_dir = Path(tempfile.mkdtemp(prefix="b98dir_"))
for _n in ("CP01.xlsx", "CP01b.xlsx"):
    shutil.copy(RAW / "CP01.xlsx", _dir / _n)
_od = _run("ingest-dir", str(_dir), "--doc-type", "cp", "--allow-mock")
shutil.rmtree(_dir, ignore_errors=True)
show("ⓓ ingest-dir은 사전 점검 1회(문서 둘)",
     sum(1 for l in _od.splitlines() if "사전 점검 —" in l) == 1
     and _od.count("[투입]") == 2, _od.count("사전 점검 —"))

print("\n■ B98 ④ 설정 파일 판정 표시")
_home = Path(tempfile.mkdtemp(prefix="b98home_"))
(_home / ".onto").mkdir()
(_home / ".onto" / "llm.json").write_text('{"CHAT_MODEL": "앞"}', encoding="utf-8")
_late = _P.config_file()
_late_had, _late_dir = _late.exists(), _late.parent.exists()
if not _late_had:
    _P.ensure(_late)
    _late.write_text('{"CHAT_MODEL": "뒤"}', encoding="utf-8")
_env = {**os.environ, "HOME": str(_home), "USE_MOCK": "1"}
_env.pop("ONTO_CONFIG", None)
import subprocess as _sp        # noqa: E402
_lc = _sp.run([sys.executable, str(ROOT / "run.py"), "llm-check"], cwd=str(ROOT), env=_env,
              capture_output=True, text=True, stdin=_sp.DEVNULL, timeout=120)
_dr = _sp.run([sys.executable, str(ROOT / "doctor.py"), "--quick"], cwd=str(ROOT), env=_env,
              capture_output=True, text=True, stdin=_sp.DEVNULL, timeout=600)
if not _late_had:
    _late.unlink()
    if not _late_dir and not any(_late.parent.iterdir()):
        _late.parent.rmdir()
shutil.rmtree(_home, ignore_errors=True)
_lco, _dro = _lc.stdout + _lc.stderr, _dr.stdout + _dr.stderr
show("ⓔ 설정 파일 둘 → llm-check·doctor가 읽은 것과 무시된 것을 말한다",
     all(".onto/llm.json" in t and "**무시됨**" in t and str(_late) in t for t in (_lco, _dro)),
     [l.strip()[:90] for l in _lco.splitlines() if "무시됨" in l][:1])

print("\n■ B98 ③ 토큰 표기 한 함수")
_src = "".join(p.read_text(encoding="utf-8") for p in
               list((ROOT / "cli").rglob("*.py")) if p.name != "_screen.py")
show("ⓕ 토큰 표기는 한 함수(입력·출력) · 미제공이면 그 문면 · 화면에 합계만 찍는 자리 0",
     _screen.tokens({"total_tokens": 10, "prompt_tokens": 7, "completion_tokens": 3})
     == "토큰 10(입력 7 · 출력 3)"
     and "입출력 구분 없음" in _screen.tokens({"total_tokens": 9})
     and "total_tokens" not in _src and "입력 " in _screen.usage_line(),
     _screen.tokens({"total_tokens": 9}))

print("\n■ B98 ② 구축 실패 줄")
_register()
_ingest("--sheets", "auto")                      # 추출 체크포인트를 남긴다
from core.build import prose as _PR             # noqa: E402
_keep_bp = _PR.build_prose


def _boom(*a, **k):
    raise RuntimeError("시험 주입 — 구축 실패")


_PR.build_prose = _boom
try:
    _rf, _of = _cap(IG.ingest_file, str(RAW / "RFQ01.xlsx"), "prose_xlsx_basic", ask=False,
                    sheets="auto")
finally:
    _PR.build_prose = _keep_bp
show("ⓖ 구축 실패 → 실패 줄에 추출 체크포인트 보존(같은 명령이면 LLM 0) · 다음 줄",
     _rf["status"] != "성공" and EX.has_checkpoint("RFQ01")
     and "추출 체크포인트는 남았다" in _of and "▶ 다음 줄" in _of,
     [l.strip()[:70] for l in _of.splitlines() if "체크포인트는 남았다" in l][:1])
_unregister()

print("\n■ B98 ⑥ 이어지는 표 · ⑤ 색")
os.environ["COLUMNS"] = "80"
_t = _screen.Table([("번호", 7, True), ("표기", 60, False), ("행 수", 5, True),
                    ("결과", 24, False)], flex=1)
_buf = io.StringIO()
_tick0 = _screen.TICK_SECONDS
_screen.TICK_SECONDS = 0.02
with contextlib.redirect_stdout(_buf):
    with _screen.ticker("시험"):
        gateway.USAGE["calls"] += 1
        for _i in range(40):
            _t.row([f"{_i + 1}/40", "노칭 프레스 금형 클리어런스 아주 긴 한글 표기\n줄바꿈\t탭",
                    _i, "노칭" if _i % 2 else None])
            time.sleep(0.003)
    _t.end()
gateway.USAGE["calls"] -= 1
_screen.TICK_SECONDS = _tick0
os.environ.pop("COLUMNS", None)
_ls = _buf.getvalue().splitlines()
_data = [l for l in _ls if re.match(r"\s*\d+/40 \| ", l)]


def _cols(line):
    """구분자(` |`)의 **화면 폭** 위치 — 칸이 맞으면 모든 행이 같다(빈 끝 칸도 구분자는 남는다)."""
    t = _screen.strip_ansi(line)
    return tuple(_screen.w(t[:i]) for i in range(len(t)) if t.startswith(" |", i))


_pos = {_cols(l) for l in _data}
_bad = [l for l in _ls if l.strip() and not (re.match(r"\s*\d+/40 \| ", l) or "+--" in l
                                              or "번호 |" in l or "-+-" in l)]
show("ⓗ 표: 긴 한글·줄바꿈 섞인 표기·80칸에서 칸 정렬 유지 · 30초 행이 행 중간에 끼지 않는다",
     len(_data) == 40 and len(_pos) == 1 and len(next(iter(_pos))) == 3
     and all(_screen.w(l) <= 80 for l in _ls) and not _bad
     and any("+--" in l for l in _ls) and sum("번호 |" in l for l in _ls) == 2,
     _data[0] if _data else "")


class _TTY:
    def isatty(self):
        return True


_keep_nc = os.environ.pop("NO_COLOR", None)
_on = _screen.paint("x", "head", stream=_TTY())
os.environ["NO_COLOR"] = "1"
_off = _screen.paint("x", "head", stream=_TTY())
os.environ.pop("NO_COLOR", None)
if _keep_nc is not None:
    os.environ["NO_COLOR"] = _keep_nc
show("ⓘ 색: 파이프·NO_COLOR에서 ESC 0 · tty면 새 층이 칠해진다 · 새 층에 빨강·노랑 0(특이점 전용)",
     "\033" not in _od and "\033" not in _oc and "\033" in _on and _off == "x"
     and all(not ({"red", "yellow"} & set(_screen.KINDS[k]))
             for k in ("head", "prog", "beat", "aux")))
init.init(fresh_=True, all_=True)

done()
