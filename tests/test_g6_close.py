# -*- coding: utf-8 -*-
"""G6 — **마감 도구는 판정을 느슨하게 하지 않는다** — doctor 고르기 · 마감 한 줄 · 명세 패치 · 명세 모양 (B117 ①②③).

잠그는 성질:
  ⓐ 고르기 — `doctor --only <접두>` ⇒ 그 스위트만 돈다(스위트 줄이 그 하나 · 머리와 합계 줄에 「고른 실행 — 판정 아님」 · 명령
     로그에도) · 모르는 이름은 사용법(rc 2) · `--changed`는 바뀐 파일을 읽는 스위트를 빠뜨리지 않는다 — 실행 기록 표본
     (`docs/회귀스위트/자산/스위트_읽기_표본.json` — `tools/suite_reads.py`가 클린 단독 실행의 감사 훅으로 적은 표)의 파일마다
     정적 선택 ⊇ 실제로 읽은 스위트 · 레포 사본(git)에서 core 파일 하나를 바꾸면 `--changed --list`가 그 표본 스위트를 전부
     고른다 · 이름을 지어 읽는 자산 폴더(지시문)의 파일을 바꾸면 고를 수 없다 → 전체
  ⓔ 네 벌 바닥 C(산문 엑셀) — 레포 사본(git)에서 같은 커밋끼리 A · B · C 전부 같다 · 폴백 사슬(`heading.chain_for`)을 끈
     사본에서 다른 것은 C뿐
  ⓑ 마감 한 줄 — 레포 사본에서 doctor를 이 시험이 쓴 가짜(전체 실행은 실패를 낸다)로 바꾸고(실제 마감은 진짜를 돈다 — 여기는
     순서와 끝까지를 잰다) 명세에 취소선 하나를 넣으면 ⇒ 단계 일곱 줄이 전부 요약에 서고 · doctor FAIL 뒤에도 네 벌(진짜)이 돌아
     「전부 같다」 · rc 1 · `--base`가 없으면 rc 2
  ⓒ 명세 패치 — 지금 명세에서 고른 문장으로 만든 패치는 `--check` 통과 · 쓰기 0 · `지금`이 둘 · 없음 · `바뀔`에 취소선은 그
     항목 이름과 함께 FAIL · `--apply`는 하나라도 어긋나면 쓰기 0(명세 사본 지문 같음) · 다 맞으면 그 문장만 바뀐다 · 미러
     body만 바뀌면 「재봉인 대상 <쌍>」 알림(실패 아님 · `--apply`는 쓴다) · 다른 검사가 함께 늘면 쓰기 0(B121 ④) · 점검이
     레포의 검사 결과 파일을 바꾸지 않는다
  ⓕ 층 어휘 정적 점검(B121 ①) — 지금 레포 위반 0 · 사본 core에 카테고리 이름 하나를 넣으면 rc 1과 그 자리 · 마감 한 줄의
     사전 점검에 그 줄이 선다
  ⓕ′ 레포 쓰기 정적 점검(B133 ①) — 지금 레포 위반 0 · 사본 시험에 레포 쓰기를 심으면 rc 1과 그 자리 · ⓓ′ 붉은 기록(B133 ②) — PASS 0
     사본의 임시 루트 · 출력 전문이 남고 자리가 화면 · 명령 로그에 · ⓑ 마감 한 줄은 doctor를 회귀 명령(`--regress`)으로 부른다
  ⓓ 명세 모양 — 지금 명세는 기준 그대로 통과 · 사본에 취소선 하나 · 칸 밖 글 하나를 더하면 둘 다 위반이고 기준은 그대로 ·
     줄어든 수는 기준을 내린다(기준 사본에 수와 기록)
  ⓖ 명세 낱말 대조(B158 ②) — 기준 판(git)에서 낱말 하나를 지운 사본 ⇒ rc 1 + 그 낱말 · 대조 표에 적으면 rc 0 · 머리줄 하나를 바꾼
     사본 ⇒ rc 1
명세 사본 · 레포 사본은 시스템 임시 폴더다 — 레포와 mock 상태 폴더는 ⓐ의 고른 실행(그 스위트의 클린 단독)만 지난다.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.llm import gateway as _iso                              # noqa: E402
_iso.isolate()   # 시험은 셸 환경과 무관하게 격리 환경에서 돈다 (B111 ① · doctor와 같은 함수 · core의 다른 모듈보다 먼저)
from cli import doctor_select as DS                                # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


T = Path(tempfile.mkdtemp(prefix="b117_"))
ENV = dict(_iso.isolated_env(), NO_COLOR="1")


def _run(cmd, cwd=ROOT, env=None):
    r = subprocess.run([sys.executable, *cmd], cwd=str(cwd), env=env or ENV, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _git(cwd, *a):
    return subprocess.run(["git", "-c", "core.quotepath=off", "-c", "user.name=시험", "-c", "user.email=t@t", *a],
                          cwd=str(cwd), capture_output=True, text=True, stdin=subprocess.DEVNULL)


def _fp(d):
    """폴더 지문 — 파일 목록 + 바이트."""
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


SUITES = re.findall(r'^    \("(test_[a-z0-9_]+|verify_roundtrip)"', (ROOT / "doctor.py").read_text(encoding="utf-8"), re.M)

# ────────────────────────────────────────────────────────────── ⓐ
print("\n■ ⓐ 고르기 — --only · --changed (판정 아님)")
from core.state import log as _LOG                                  # noqa: E402 — 명령 로그 자리(그 모듈이 안다)
from core import paths as _P                                         # noqa: E402 — mock 루트 훅 이름(그 모듈이 안다)
from concurrent.futures import ThreadPoolExecutor                  # noqa: E402
_bg = ThreadPoolExecutor(2)
_facts_f = _bg.submit(DS.suite_facts, SUITES)                       # 정적 선택 그래프 — 아래 하위 실행을 기다리는 동안 짓는다
rc, out = _run(["doctor.py", "--only", "p1_wir"])
_log = max(_LOG.log_dir().glob("doctor_*.log"), key=lambda p: p.stat().st_mtime, default=T / "없음")
_ran = re.findall(r"^\s*\[[^\]]+\] (test_[a-z0-9_]+)\s+\d+ PASS / \d+ FAIL", out, re.M)
_head = "\n".join(out.splitlines()[:4])
_sum = next((ln for ln in out.splitlines() if "합계" in ln and "PASS" in ln), "")
show("ⓐ --only 접두 하나 ⇒ 그 스위트만 돈다 · 머리와 합계 줄에 「고른 실행 — 판정 아님」",
     rc == 0 and _ran == ["test_p1_wiring"] and DS.HEAD_LINE in _head and DS.HEAD_LINE in _sum,
     f"rc {rc} · 돈 스위트 {_ran} · 합계 {_sum.strip()[:80]}")
_lt = _log.read_text(encoding="utf-8") if _log.exists() else ""
_tail = _lt[_lt.rfind("===== 실행 시작"):]                         # 이번 실행 몫(클린이 지우면 다시 연 머리부터)
show("ⓐ 명령 로그에도 「고른 실행 — 판정 아님」(이번 실행의 결과 줄)",
     f"결과: {DS.HEAD_LINE}" in _tail and "--only p1_wir" in _tail, f"{_log.name} · 이번 몫 {len(_tail)}자")
rc2, out2 = _run(["doctor.py", "--only", "없는_스위트"])
show("ⓐ 모르는 이름 ⇒ 사용법 · rc 2(아무것도 돌지 않는다)", rc2 == 2 and "[사용법]" in out2 and "PASS /" not in out2,
     f"rc {rc2}")

_table = json.loads((ROOT / "docs" / "회귀스위트" / "자산" / "스위트_읽기_표본.json").read_text(encoding="utf-8"))["표본"]
_facts = _facts_f.result()
_lost = {f: sorted(set(want) - (DS.readers(f, _facts) or set(SUITES))) for f, want in _table.items()}
_lost = {f: v for f, v in _lost.items() if v}
show("ⓐ 실행 기록 표본의 파일마다 정적 선택 ⊇ 실제로 읽은 스위트(빠뜨림 0)",
     not _lost and len(_table) >= 5, f"표본 {len(_table)} 파일 · 빠뜨림 {_lost}")

# ⓒ의 재료 — 명세 사본 · 패치 표본(실행은 아래 레포 사본 실행과 함께 돈다 · B121 ②ⓓ)
SP = T / "spec_copy" / "docs" / "spec"
shutil.copytree(ROOT / "docs" / "spec", SP)
shutil.copytree(ROOT / "docs" / "archive", SP.parent / "archive")
_name = "0_기반과원칙.md"
_text = (SP / _name).read_text(encoding="utf-8")
_line = next(ln for ln in _text.splitlines() if 20 < len(ln) < 300 and not ln.lstrip().startswith(("|", "#", ">"))
             and "~~" not in ln and _text.count(ln) == 1)
_twice = next(w for w in ("문서", "규칙", "판정") if _text.count(w) > 1)
_new = " 시험으로 끼운 문장이다(B117)."
GOOD = T / "good.md"
GOOD.write_text(f"# 시험 패치\n\n### {_name} 좋음\n지금: {_line}\n바뀔: {_line}{_new}\n까닭: B117 ② 시험\n",
                encoding="utf-8")
BAD = T / "bad.md"
BAD.write_text(f"# 시험 패치\n\n### {_name} 좋음\n지금: {_line}\n바뀔: {_line}{_new}\n까닭: 시험\n\n"
               f"### {_name} 둘\n지금: {_twice}\n바뀔: {_twice}(B117)\n까닭: 시험\n\n"
               f"### {_name} 없음\n지금: 이 문장은 명세에 없다 ZQX\n바뀔: 없다(B117)\n까닭: 시험\n\n"
               f"### {_name} 취소선\n지금: {_line}\n바뀔: {_line} ~~옛 규칙~~ 새 규칙(B117)\n까닭: 시험\n",
               encoding="utf-8")
_res = {f: f.read_bytes() for f in (ROOT / "docs" / "회귀스위트" / "자산").glob("*_결과.json")}
_fp0 = _fp(SP)
# 미러 재봉인(B121 ④) — 늘어난 것이 미러 봉인뿐이면 알림(실패 아님) · 다른 검사가 함께 늘면 쓰기 0
_pair = next(x for x in json.loads((ROOT / "docs" / "회귀스위트" / "미러쌍.json").read_text(encoding="utf-8"))
             if x["body"]["kind"] == "para" and (SP / x["body"]["doc"]).read_text(encoding="utf-8").count(x["body"]["anchor"]) == 1)
_anc = _pair["body"]["anchor"]
_mir = f"### {_pair['body']['doc']} 미러 body\n지금: {_anc}\n바뀔: {_anc} 시험으로 끼운 문장이다(B121).\n까닭: 시험\n"
MIR, MIX = T / "mirror.md", T / "mirror_shape.md"
MIR.write_text("# 시험 패치\n\n" + _mir, encoding="utf-8")
MIX.write_text("# 시험 패치\n\n" + _mir + f"\n### {_name} 긴 줄\n지금: {_line}{_new}\n바뀔: {_line}{_new}\n{'가' * 1600}(B121)\n"
               "까닭: 시험\n", encoding="utf-8")

def _spec_runs():
    """ⓒ의 하위 실행 묶음 — 명세 사본(SP)에서만 돈다(레포 사본 BOX의 실행과 함께 돈다 · 어서션은 아래 ⓒ 자리에서 같은 순서로)."""
    r = {"fp0": _fp(SP)}
    r[7] = _run(["tools/spec_patch.py", "--check", str(GOOD), "--spec", str(SP)])
    r["fp7"] = _fp(SP)
    r[9] = _run(["tools/spec_patch.py", "--apply", str(BAD), "--spec", str(SP)])   # 항목 줄은 --check와 같은 함수(verify)
    r["fp9"] = _fp(SP)
    r["others"] = {p.name: p.read_bytes() for p in SP.glob("*.md") if p.name != _name}
    r[10] = _run(["tools/spec_patch.py", "--apply", str(GOOD), "--spec", str(SP)])
    r["after"] = (SP / _name).read_text(encoding="utf-8")
    r["others_after"] = {n: (SP / n).read_bytes() for n in r["others"]}
    r["tmp_left"] = list(SP.glob(".*.tmp"))
    body = SP / _pair["body"]["doc"]
    r["body0"] = body.read_bytes()
    r[13] = _run(["tools/spec_patch.py", "--check", str(MIR), "--spec", str(SP)])
    r[14] = _run(["tools/spec_patch.py", "--apply", str(MIR), "--spec", str(SP)])
    r["body14"] = body.read_bytes()
    body.write_bytes(r["body0"])
    r["fp1"] = _fp(SP)
    r[15] = _run(["tools/spec_patch.py", "--apply", str(MIX), "--spec", str(SP)])
    r["fp15"] = _fp(SP)
    return r


_spec_f = _bg.submit(_spec_runs)


# 레포 사본(git) — 작업 트리(추적 + 추적 밖 새 파일 · 무시 파일 제외)
BOX = T / "box"
_ls = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=str(ROOT),
                     capture_output=True, stdin=subprocess.DEVNULL).stdout.decode("utf-8").split("\0")
for _f in _ls:
    if _f and (ROOT / _f).is_file():
        (BOX / _f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / _f, BOX / _f)
_git(BOX, "init", "-q")
_git(BOX, "add", "-A", "-f")                    # 추적 파일은 무시 규칙에 걸려도 싣는다(픽스처 `parsed/`)
_git(BOX, "commit", "-qm", "바탕")
_core = "core/build/heading.py"
(BOX / _core).write_text((BOX / _core).read_text(encoding="utf-8") + "\n# 시험 — 바뀐 파일\n", encoding="utf-8")
rc3, out3 = _run(["doctor.py", "--changed", "--list"], cwd=BOX)
_pick = next((ln.split("—", 1)[1] for ln in out3.splitlines() if "고른 스위트 —" in ln), "")
_picked = {s.strip() for s in _pick.split("·") if s.strip()}
_want = set(_table.get(_core, []))
show(f"ⓐ 사본에서 core 파일 하나({_core})를 바꾸면 --changed가 그 파일을 읽는 표본 스위트를 전부 고른다",
     rc3 == 0 and _want and _want <= _picked and DS.HEAD_LINE in out3 and len(_picked) < len(SUITES),
     f"rc {rc3} · 고름 {len(_picked)}/{len(SUITES)} · 표본 {len(_want)} · 빠짐 {sorted(_want - _picked)}")
_git(BOX, "checkout", "-q", "--", _core)
_pr = sorted(p for p in (BOX / "prompts").glob("*.md"))[0]
_pr.write_text(_pr.read_text(encoding="utf-8") + "\n", encoding="utf-8")
rc4, out4 = _run(["doctor.py", "--changed", "--list"], cwd=BOX)
show("ⓐ 이름을 지어 읽는 자산 폴더(지시문) 파일이 바뀌면 고를 수 없다 → 전체",
     rc4 == 0 and "고를 수 없다 → 전체" in out4 and "고른 스위트 —" not in out4, f"rc {rc4} · {_pr.name}")
_git(BOX, "checkout", "-q", "--", _pr.relative_to(BOX).as_posix())

# 층 어휘 정적 점검(B121 ①) — 지금 레포 0 · 사본 core에 카테고리 이름 하나를 넣으면 붉고 그 자리를 말한다
_lw0 = _run(["tools/layer_words.py"])
_cat = sorted(json.loads((ROOT / "layers" / "common.json").read_text(encoding="utf-8"))["categories"])[0]
_lwf = BOX / "core" / "build" / "heading.py"
_lwf.write_text(_lwf.read_text(encoding="utf-8") + f'\n_B121_PROBE = "{_cat}"\n', encoding="utf-8")
_lw1 = _run(["tools/layer_words.py"], cwd=BOX)
_git(BOX, "checkout", "-q", "--", "core/build/heading.py")
show("ⓕ 층 어휘 정적 점검 — 지금 레포 위반 0(rc 0) · 사본 core에 카테고리 이름 하나를 넣으면 rc 1 · 그 파일 · 낱말을 말한다 (B121 ①)",
     _lw0[0] == 0 and "위반 0건" in _lw0[1] and _lw1[0] == 1 and f"core/build/heading.py" in _lw1[1] and f"'{_cat}'" in _lw1[1],
     f"rc {_lw0[0]} · {_lw1[0]} · {_cat}")
# 레포 쓰기 정적 점검(B133 ①) — 지금 레포 위반 0 · 사본 시험 하나에 레포 쓰기를 심으면 붉고 그 자리를 말한다
_rw0 = _run(["tools/repo_writes.py"])
_rwf = BOX / "tests" / "test_p1_wiring.py"
_rwf.write_text(_rwf.read_text(encoding="utf-8") + '\n(ROOT / "b133_probe.txt").write_text("x")\n', encoding="utf-8")
_rw1 = _run(["tools/repo_writes.py", "--root", str(BOX)])
_git(BOX, "checkout", "-q", "--", "tests/test_p1_wiring.py")
show("ⓕ 레포 쓰기 정적 점검 — 지금 레포 위반 0(rc 0) · 사본 시험에 레포 쓰기 하나를 심으면 rc 1 · 그 파일을 말한다 (B133 ①)",
     _rw0[0] == 0 and "위반 0건" in _rw0[1] and _rw1[0] == 1 and "[위반] tests/test_p1_wiring.py" in _rw1[1],
     f"rc {_rw0[0]} · {_rw1[0]}")

# ────────────────────────────────────────────────────────────── ⓑ
# ────────────────────────────────────────────────────────────── ⓔ
print("\n■ ⓔ 네 벌 바닥 C(산문) — 같은 커밋은 같다 · 폴백 사슬을 끈 사본은 C가 다르다")


def _bottoms(text):
    """네 벌 대조 줄 중 다른 것이 있는 바닥."""
    return {m.group(1) for m in re.finditer(r"^([ABC]) .*(?:빠짐 [1-9]|더함 [1-9]|다른 파일 \['|같음 False)", text, re.M)}


# 같은 커밋끼리(A · B · C 전부 같다)는 아래 ⓑ 마감 한 줄 안의 네 벌(진짜)이 잰다 — 한 번만 돈다 (B121 ②ⓓ)
_hd = BOX / "core" / "build" / "heading.py"
_src = _hd.read_text(encoding="utf-8")
_fn = next((n for n in ast.walk(ast.parse(_src)) if isinstance(n, ast.FunctionDef) and n.name == "chain_for"), None)
if _fn is not None:                                 # 독스트링 뒤에 `return []` — 폴백 사슬(제목 개체)을 끈다
    _ln = _src.splitlines(keepends=True)
    _ln.insert(_fn.body[0].end_lineno, "    return []  # 시험 — 폴백 사슬을 끈다\n")
    _hd.write_text("".join(_ln), encoding="utf-8")
rc12, out12 = _run(["tools/four_way.py", "--base", "HEAD"], cwd=BOX)
show("ⓔ 폴백 사슬(제목 개체 → 그 위 → 공정)을 끈 사본 — 다른 것은 바닥 C뿐(rc 1)",
     _fn is not None and rc12 == 1 and _bottoms(out12) == {"C"}, f"rc {rc12} · 다른 바닥 {sorted(_bottoms(out12))}")
_git(BOX, "checkout", "-q", "--", "core/build/heading.py")

print("\n■ ⓓ 기대 수는 생성물 — 늘면 「+n」 · 사유 없는 감소는 붉다 · 사유 있으면 기록 · PASS 0은 늘 붉다 (B131 ②)")
_rp = BOX / "tests" / "test_p1_wiring.py"
_rp_src = _rp.read_text(encoding="utf-8")
_rec = json.loads((ROOT / "docs" / "회귀스위트" / "기대_수.json").read_text(encoding="utf-8"))
_n0 = _rec["suites"]["test_p1_wiring"]["n"]


def _dr(src, *extra, env=None):
    """사본에서 그 스위트를 고친 판으로 doctor --only 하나 · `(rc, 화면, --result)`."""
    _rp.write_text(src, encoding="utf-8")
    _rf = T / "dr_result.json"
    _rf.unlink(missing_ok=True)
    rc, out = _run(["doctor.py", "--only", "test_p1_wiring", "--result", str(_rf), *extra], cwd=BOX, env=env)
    return rc, out, (json.loads(_rf.read_text(encoding="utf-8")) if _rf.exists() else {})


_plus = _rp_src.replace("\ndone()", '\nshow("시험 — 하나 더", True)\ndone()')
_minus = re.sub(r"\nshow\(", "\nif False: show(", _rp_src, count=1)
_zero = _rp_src.replace("from __future__ import annotations", "from __future__ import annotations\nimport sys; sys.exit(0)", 1)
_spec = importlib.util.spec_from_file_location("close_box", BOX / "tools" / "close.py")
_CL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_CL)
sys.path.insert(0, str(BOX))
import doctor as _DOC                                                   # noqa: E402 — 스위트 목록(import만)
rc7, out7, res7 = _dr(_plus)
_rec7, _ch7 = _CL.expect_record(_rec, res7, _DOC.SUITES, "시험", "2026-10-20", whole=False)
show("ⓓ 어서션 하나를 더한 사본 — doctor가 「+1」로 지나가고 마감 한 줄의 기록 함수가 그 수를 쓴다(바뀜 +1)",
     rc7 == 0 and "+1(기록" in out7 and _rec7["suites"]["test_p1_wiring"]["n"] == _n0 + 1
     and _CL.expect_line(_ch7) == "test_p1_wiring +1",
     f"rc {rc7} · {_CL.expect_line(_ch7)}")
rc8, out8, _r8 = _dr(_minus)
for _m8 in re.finditer(r"붉은 기록 — (\S+?)\(임시 루트", out8):          # 이 시험이 일부러 붉힌 자리는 거둔다(B133 ②)
    shutil.rmtree(_m8.group(1), ignore_errors=True)
rc9, out9, res9 = _dr(_minus, "--why", "test_p1_wiring=시험 — 하나를 지웠다")
_rec9, _ch9 = _CL.expect_record(_rec, res9, _DOC.SUITES, "시험", "2026-10-20", whole=False)
show("ⓓ 하나를 지운 사본 — 사유 없으면 붉다(rc 1) · 사유가 있으면 지나가고 기록에 −1과 사유가 남는다",
     rc8 == 1 and "사유가 없다" in out8 and rc9 == 0 and _rec9["suites"]["test_p1_wiring"]["n"] == _n0 - 1
     and _rec9["log"][-1]["why"] == "시험 — 하나를 지웠다" and "−1" in _CL.expect_line(_ch9),
     f"rc {rc8} → 사유 {rc9} · {_CL.expect_line(_ch9)}")
_redh = T / "red_home"                                                # 이 실행의 명령 로그 자리(그 루트 아래를 훑는다)
rc10, out10, _r10 = _dr(_zero, "--why", "test_p1_wiring=사유가 있어도", env=dict(ENV, **{_P.MOCK_HOME_ENV: str(_redh)}))
show("ⓓ 스위트가 돌지 않는 사본(PASS 0) — 사유가 있어도 붉다",
     rc10 == 1 and "늘 붉다" in out10, f"rc {rc10}")
# 붉은 기록(B133 ②) — 붉은 스위트의 임시 루트와 출력 전문이 남고 그 자리가 화면 · 명령 로그에 한 줄
_redm = re.search(r"붉은 기록 — (\S+?)\(임시 루트", out10)
_redd = Path(_redm.group(1)) if _redm else T / "없음"
_redlog = "".join(f.read_text(encoding="utf-8") for f in _redh.rglob("doctor_*.log"))
show("ⓓ 붉은 스위트는 임시 루트(픽스처 사본 · 작업 폴더)와 출력 전문을 남기고 그 자리가 화면 · 명령 로그에 있다 (B133 ②)",
     _redd.is_dir() and (_redd / "fixtures").is_dir() and "## stdout" in ((_redd / "출력.txt").read_text(encoding="utf-8")
                                                                         if (_redd / "출력.txt").exists() else "")
     and str(_redd) in _redlog, f"{_redd} · 로그 {len(_redlog)}자")
shutil.rmtree(_redd, ignore_errors=True)
_rp.write_text(_rp_src, encoding="utf-8")
sys.path.remove(str(BOX))

print("\n■ ⓑ 마감 한 줄 — 첫 FAIL에서 멈추지 않고 끝까지 · rc 1")
(BOX / "doctor.py").write_text(
    "import sys\n"
    "open(__file__ + '.argv', 'a', encoding='utf-8').write(' '.join(sys.argv[1:]) + '\\n')\n"
    "if '--only' in sys.argv:\n"
    "    print('  [  OK ] 합계 2/2 PASS — 고른 실행 — 판정 아님')\n"
    "    sys.exit(0)\n"
    "print('  [ 필요 ] test_가짜  1 PASS / 1 FAIL')\n"
    "print('  [ 필요 ] 합계 1/2 PASS')\n"
    "sys.exit(1)\n", encoding="utf-8")
_rd = BOX / "docs" / "spec" / "README.md"
_rd.write_text(_rd.read_text(encoding="utf-8") + "\n~~시험 취소선~~\n", encoding="utf-8")
# 장부(B131 ③) — 살아 있는 요청문 하나를 둔다 → PROGRESS는 둘만 남기고(이번 회차가 셋째) 가장 오래된 절을 옮긴다
(BOX / "docs" / "안건" / "B999_요청문.md").write_text("# B999 시험 요청문\n", encoding="utf-8")
_pg = BOX / "PROGRESS.md"                                  # 사본에 시험 절 하나 — 레포 장부 상태와 무관하게 옮길 절이 늘 있다
_pg.write_text(_pg.read_text(encoding="utf-8").rstrip() + "\n\n---\n\n## B998 — 시험 절\n\n- 장부가 옮길 것이 있게\n",
               encoding="utf-8")
_secs0 = re.findall(r"^## (B\d+) — ", (BOX / "PROGRESS.md").read_text(encoding="utf-8"), re.M)
_live0 = [m.group(1) for f in (BOX / "docs" / "안건").glob("*_요청문.md")
          if (m := re.match(r"(B\d+)_요청문", f.name)) and m.group(1) not in _secs0]
# 바뀐 지시문(B135 ③) — 사본에서 하나는 서술만 · 하나는 판을 올린다 → 요약 줄이 지시문마다 말한다
_pdk = next((BOX / "prompts").glob("*_deck.md"))
_pdk.write_text(_pdk.read_text(encoding="utf-8") + "\n<!-- 시험 — 서술만 -->\n", encoding="utf-8")
_piv = next((BOX / "prompts").glob("*_interview.md"))
_piv_t = _piv.read_text(encoding="utf-8")
_piv_v = next(ln for ln in _piv_t.splitlines() if ln.startswith("version:"))
_piv.write_text(_piv_t.replace(_piv_v, _piv_v + "-시험", 1), encoding="utf-8")
rc5, out5 = _run(["tools/close.py", "--base", "HEAD"], cwd=BOX)
_summ = out5.split("마감 한 줄 요약", 1)[1] if "마감 한 줄 요약" in out5 else ""
_rows = re.findall(r"^\[(PASS|FAIL|갱신|건너뜀)\] ([^—\n]+)", _summ, re.M)
_lab = {lab.strip(): v for v, lab in _rows}
_doc = next((v for k, v in _lab.items() if k.startswith("마감 doctor")), None)
_chk = next((ln for ln in _summ.splitlines() if "문서 검사 일곱" in ln), "")
# 기대 변경(B133 — 사전 점검에 레포 쓰기 정적 점검 · doctor는 회귀 명령으로 · B135 — 바뀐 지시문 줄)
_argv = (BOX / "doctor.py.argv").read_text(encoding="utf-8").split() if (BOX / "doctor.py.argv").exists() else []
show("ⓑ 장부 → 바뀐 지시문 → 사전 점검(층 어휘 · 레포 쓰기 포함) → doctor(회귀 명령) → 네 벌 → §7 상한 → 자산 해시 → 기대 수 — 단계 열다섯 줄이 요약에",
     len(_rows) == 15 and any(k.startswith("네 벌") for k in _lab) and "§7 상한" in _lab and "자산 해시" in _lab
     and "층 어휘 정적 점검" in _lab and "레포 쓰기 정적 점검" in _lab and "PROGRESS 최근 3회차" in _lab
     and _lab.get("기대 수 기록") == "건너뜀" and "--regress" in _argv,
     f"줄 {len(_rows)} · doctor 인자 {_argv} · {list(_lab)}")
_pln = next((ln for ln in _summ.splitlines() if "바뀐 지시문" in ln), "")
show("ⓑ 바뀐 지시문 줄(B135 ③) — 사본에서 서술만 바꾼 지시문은 「서술만」 · 판을 올린 지시문은 「판 올림 a → b」",
     _lab.get("바뀐 지시문") == "갱신" and f"{_pdk.name} 서술만" in _pln and f"{_piv.name} 판 올림" in _pln, _pln[:200])
show("ⓑ 넣은 FAIL(명세 취소선 · doctor 실패)이 FAIL로 서고 그 뒤 네 벌도 돌았다 · rc 1",
     rc5 == 1 and _doc == "FAIL" and "[FAIL]" in _chk and "모양" in _chk and _lab.get("네 벌") == "PASS"
     and "전부 같다" in _summ and re.search(r"FAIL [2-9]", _summ),
     f"rc {rc5} · doctor {_doc} · {_chk[:90]}")
_secs1 = re.findall(r"^## (B\d+) — ", (BOX / "PROGRESS.md").read_text(encoding="utf-8"), re.M)
_moved = [x for x in _secs0 if x not in _secs1]
_pl = next((ln for ln in _summ.splitlines() if "PROGRESS 최근 3회차" in ln), "")
# 기대 변경(B132 — 이번 회차는 살아 있는 요청문 가운데 하나 · 다음 회차 요청문이 미리 와도 남기는 절을 더 줄이지 않는다)
show("ⓔ 장부 — 마감 한 줄 한 번으로 PROGRESS가 이번 회차 포함 셋(미리 온 다음 요청문은 세지 않는다) · 밀린 절은 archive 본문 + 색인 한 줄 · "
     "그 회차의 안건은 지운다 · 무엇을 옮겼나가 요약 줄에",
     len(_secs1) == max(0, 3 - min(1, len(_live0))) and _moved and all((BOX / "docs" / "archive" / "장부" / f"PROGRESS_{x}.md").exists() for x in _moved)
     and all(f"본문 `docs/archive/장부/PROGRESS_{x}.md`" in (BOX / "PROGRESS.md").read_text(encoding="utf-8") for x in _moved)
     and not any((BOX / "docs" / "안건").glob(f"{_moved[0]}_*.md")) and "옮김" in _pl
     and (BOX / "docs" / "안건" / "B999_요청문.md").exists(),
     f"절 {_secs0} → {_secs1} · 살아 있는 {_live0} · {_pl[:120]}")
_steps = re.search(r"단계 전문 (\S+)", _summ)                     # 사본의 단계 전문 — 시험이 지운다
_fw = (Path(_steps.group(1)) / "3_four_way.txt") if _steps else None
out11 = _fw.read_text(encoding="utf-8") if _fw and _fw.exists() else ""
# 기대 변경(B119 ⑥ — 바닥 C에 표본 ⓑ(TW 꼴) FWC3가 더해져 산문 셋) · 마감 한 줄 안의 네 벌 전문으로 잰다(B121 ②ⓓ)
show("ⓔ 같은 커밋끼리 — 바닥 A · B · C 전부 같다(rc 0) · C가 넣은 산문 셋이 성공",
     "전부 같다" in out11 and not _bottoms(out11)
     and re.search(r"지금 C 넣기 \{'FWC1': '성공', 'FWC2': '성공', 'FWC3': '성공'\}", out11),
     (out11.strip().splitlines() or [""])[-1])
if _steps and Path(_steps.group(1)).name.startswith("onto_close_"):
    shutil.rmtree(_steps.group(1), ignore_errors=True)
rc6, out6 = _run(["tools/close.py"])
show("ⓑ --base가 없으면 사용법 · rc 2", rc6 == 2 and "[사용법]" in out6, f"rc {rc6}")

# ────────────────────────────────────────────────────────────── ⓒ
print("\n■ ⓒ 명세 패치 — --check · --apply(사본)")
_R = _spec_f.result()
_bg.shutdown()
rc7, out7 = _R[7]
show("ⓒ 지금 명세에서 고른 문장의 패치 ⇒ --check 통과(사본 적용 뒤 문서 검사 일곱 그대로) · 쓰기 0",
     rc7 == 0 and "[PASS] 사본 적용 뒤 문서 검사 일곱" in out7 and _R["fp7"] == _R["fp0"], f"rc {rc7}")
rc9, out9 = _R[9]
_fl = [ln for ln in out9.splitlines() if ln.startswith("[FAIL]")]
show("ⓒ 지금이 둘 · 없음 · 바뀔에 취소선 ⇒ 그 항목 이름과 함께 FAIL · 맞는 항목은 PASS",
     rc9 == 1 and any("둘" in x and "번" in x for x in _fl) and any("없음" in x and "0번" in x for x in _fl)
     and any(x.startswith(f"[FAIL] {_name} 취소선") and "취소선" in x.split("—", 1)[-1] for x in _fl)
     and f"[PASS] {_name} 좋음" in out9, " | ".join(_fl)[:240])
show("ⓒ --apply는 하나라도 어긋나면 쓰기 0 — 명세 사본 지문 같음",
     rc9 == 1 and "쓰기 0" in out9 and _R["fp9"] == _R["fp0"], f"rc {rc9}")
rc10, _out10 = _R[10]
show("ⓒ 다 맞으면 --apply가 그 문장만 바꾼다(다른 파일 바이트 그대로 · 임시 파일 흔적 0)",
     rc10 == 0 and _R["after"] == _text.replace(_line, _line + _new, 1)
     and _R["others_after"] == _R["others"] and not _R["tmp_left"], f"rc {rc10}")
(rc13, out13), (rc14, out14), (rc15, out15) = _R[13], _R[14], _R[15]
_note = f"[알림] 재봉인 대상 {_pair['id']}"
show("ⓒ 미러 body만 바꾸는 패치 ⇒ --check는 「재봉인 대상 <쌍>」 알림 · 통과 · 쓰기 0 · --apply는 쓰고 같은 줄 (B121 ④)",
     rc13 == 0 and _note in out13 and rc14 == 0 and _note in out14 and "적용 — 파일 1" in out14
     and _R["body14"] != _R["body0"], f"rc {rc13} · {rc14} · {_pair['id'][:30]}")
show("ⓒ 미러와 함께 다른 검사(모양 — 1500자+ 줄)가 늘면 ⇒ 재봉인 알림 없이 어긋남 · 쓰기 0 (B121 ④)",
     rc15 == 1 and "늘었다: 미러 · 모양" in out15 and "재봉인 대상" not in out15 and "쓰기 0" in out15
     and _R["fp15"] == _R["fp1"], f"rc {rc15}")
show("ⓒ 패치 점검 · 적용이 레포의 검사 결과 파일을 바꾸지 않는다",
     all(f.read_bytes() == b for f, b in _res.items()), f"결과 파일 {len(_res)}")

# ────────────────────────────────────────────────────────────── ⓓ
print("\n■ ⓓ 명세 모양 — 늘면 위반 · 줄면 기준을 내린다")
_spec = importlib.util.spec_from_file_location("chk_shape", ROOT / "docs" / "회귀스위트" / "점검_모양.py")
SH = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SH)
_base_bytes = Path(SH.BASE_FILE).read_bytes()
bad0, now0, base0, _lw = SH.judge(str(ROOT / "docs" / "spec"), write=False)
show("ⓓ 지금 명세는 기준 그대로 통과", not bad0, SH.line(now0, base0, bad0))
SP2 = T / "shape" / "spec"
shutil.copytree(ROOT / "docs" / "spec", SP2)
_b = SP2 / "README.md"
_b.write_text(_b.read_text(encoding="utf-8") + "\n~~시험~~\n\n| 가 | 나 | 칸 밖 글\n", encoding="utf-8")
bad1, now1, _b1, _l1 = SH.judge(str(SP2))
show("ⓓ 사본에 취소선 하나 · 칸 밖 글 하나 ⇒ 둘 다 위반 · 기준 파일은 그대로",
     now1["취소선"] == now0["취소선"] + 1 and now1["칸 밖"] == now0["칸 밖"] + 1
     and any(x.startswith("취소선") for x in bad1) and any(x.startswith("칸 밖") for x in bad1)
     and Path(SH.BASE_FILE).read_bytes() == _base_bytes, " · ".join(b[:30] for b in bad1))
_tb = T / "shape" / "기준.json"
_tb.write_text(json.dumps(dict(base0, 취소선=now0["취소선"] + 2), ensure_ascii=False), encoding="utf-8")
SH.BASE_FILE = str(_tb)
bad2, now2, _b2, low2 = SH.judge(str(ROOT / "docs" / "spec"), write=True)
_rec = json.loads(_tb.read_text(encoding="utf-8"))
show("ⓓ 줄어든 수는 기준을 그 수로 내린다(기준 사본에 수와 기록)",
     not bad2 and "취소선" in low2 and _rec["취소선"] == now2["취소선"] and _rec.get("기록")
     and "취소선" in _rec["기록"][-1]["내림"], f"내림 {low2}")

# ────────────────────────────────────────────────────────────── ⓖ
print("\n■ ⓖ 명세 낱말 대조 — 사라진 낱말은 대조 표에 있어야 · 머리줄은 그대로 (B158 ②)")
from tools import spec_terms as STM                                   # noqa: E402
_old = STM._git_show("HEAD", "docs/spec/7_구현규격과검증.md")         # 기준은 git의 판(실경로 — 작업 트리와 무관)
_word = next(t for t, k in sorted(STM.terms(_old).items()) if k == "백틱" and _old.count(t) == 1 and t.isascii() and t.isidentifier())
_gone = _old.replace(f"`{_word}`", "")                                # 문서에 한 번뿐인 백틱 낱말 하나를 지운 사본
rc_g1, _ln1, _d1 = STM.compare(_old, _gone)
_acc = f"| 낱말 | 방향 | 까닭 · 자리 |\n|---|---|---|\n| `{_word}` | 사라짐 | 중복 — 남은 자리 시험 |\n"
rc_g2, _ln2, _d2 = STM.compare(_old, _gone, _acc)
_h = next(l for l in _old.split("\n") if l.startswith("## "))
rc_g3, _ln3, _d3 = STM.compare(_old, _old.replace(_h, _h + " (바꿈)", 1), "")
show("ⓖ 낱말 하나를 지운 사본 ⇒ rc 1 + 그 낱말 · 대조 표에 적으면 rc 0 · 머리줄 하나를 바꾼 사본 ⇒ rc 1(대조 표가 비어도)",
     rc_g1 == 1 and set(_d1) == {(_word, "사라짐")} and rc_g2 == 0 and rc_g3 == 1
     and any("머리줄 — 다르다" in x for x in _ln3) and STM.compare(_old, _old)[0] == 0,
     f"낱말 {_word} · rc {rc_g1} · {rc_g2} · {rc_g3}")

shutil.rmtree(T, ignore_errors=True)
print("\n" + "=" * 62)
print("전체 결과:", "PASS — B117 마감 도구" if allok else "FAIL")
sys.exit(0 if allok else 1)
