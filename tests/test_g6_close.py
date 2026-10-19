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
     항목 이름과 함께 FAIL · `--apply`는 하나라도 어긋나면 쓰기 0(명세 사본 지문 같음) · 다 맞으면 그 문장만 바뀐다 · 점검이
     레포의 검사 결과 파일을 바꾸지 않는다
  ⓓ 명세 모양 — 지금 명세는 기준 그대로 통과 · 사본에 취소선 하나 · 칸 밖 글 하나를 더하면 둘 다 위반이고 기준은 그대로 ·
     줄어든 수는 기준을 내린다(기준 사본에 수와 기록)
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
rc, out = _run(["doctor.py", "--only", "g6_reg"])
_log = max(_LOG.log_dir().glob("doctor_*.log"), key=lambda p: p.stat().st_mtime, default=T / "없음")
_ran = re.findall(r"^\s*\[[^\]]+\] (test_[a-z0-9_]+)\s+\d+ PASS / \d+ FAIL", out, re.M)
_head = "\n".join(out.splitlines()[:4])
_sum = next((ln for ln in out.splitlines() if "합계" in ln and "PASS" in ln), "")
show("ⓐ --only 접두 하나 ⇒ 그 스위트만 돈다 · 머리와 합계 줄에 「고른 실행 — 판정 아님」",
     rc == 0 and _ran == ["test_g6_registry"] and DS.HEAD_LINE in _head and DS.HEAD_LINE in _sum,
     f"rc {rc} · 돈 스위트 {_ran} · 합계 {_sum.strip()[:80]}")
_lt = _log.read_text(encoding="utf-8") if _log.exists() else ""
_tail = _lt[_lt.rfind("===== 실행 시작"):]                         # 이번 실행 몫(클린이 지우면 다시 연 머리부터)
show("ⓐ 명령 로그에도 「고른 실행 — 판정 아님」(이번 실행의 결과 줄)",
     f"결과: {DS.HEAD_LINE}" in _tail and "--only g6_reg" in _tail, f"{_log.name} · 이번 몫 {len(_tail)}자")
rc2, out2 = _run(["doctor.py", "--only", "없는_스위트"])
show("ⓐ 모르는 이름 ⇒ 사용법 · rc 2(아무것도 돌지 않는다)", rc2 == 2 and "[사용법]" in out2 and "PASS /" not in out2,
     f"rc {rc2}")

_table = json.loads((ROOT / "docs" / "회귀스위트" / "자산" / "스위트_읽기_표본.json").read_text(encoding="utf-8"))["표본"]
_facts = DS.suite_facts(SUITES)
_lost = {f: sorted(set(want) - (DS.readers(f, _facts) or set(SUITES))) for f, want in _table.items()}
_lost = {f: v for f, v in _lost.items() if v}
show("ⓐ 실행 기록 표본의 파일마다 정적 선택 ⊇ 실제로 읽은 스위트(빠뜨림 0)",
     not _lost and len(_table) >= 5, f"표본 {len(_table)} 파일 · 빠뜨림 {_lost}")

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

# ────────────────────────────────────────────────────────────── ⓑ
# ────────────────────────────────────────────────────────────── ⓔ
print("\n■ ⓔ 네 벌 바닥 C(산문) — 같은 커밋은 같다 · 폴백 사슬을 끈 사본은 C가 다르다")


def _bottoms(text):
    """네 벌 대조 줄 중 다른 것이 있는 바닥."""
    return {m.group(1) for m in re.finditer(r"^([ABC]) .*(?:빠짐 [1-9]|더함 [1-9]|다른 파일 \['|같음 False)", text, re.M)}


rc11, out11 = _run(["tools/four_way.py", "--base", "HEAD"], cwd=BOX)
# 기대 변경(B119 ⑥ — 바닥 C에 표본 ⓑ(TW 꼴) FWC3가 더해져 산문 셋)
show("ⓔ 같은 커밋끼리 — 바닥 A · B · C 전부 같다(rc 0) · C가 넣은 산문 셋이 성공",
     rc11 == 0 and "전부 같다" in out11 and not _bottoms(out11)
     and re.search(r"지금 C 넣기 \{'FWC1': '성공', 'FWC2': '성공', 'FWC3': '성공'\}", out11),
     (out11.strip().splitlines() or [""])[-1])
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

print("\n■ ⓑ 마감 한 줄 — 첫 FAIL에서 멈추지 않고 끝까지 · rc 1")
(BOX / "doctor.py").write_text(
    "import sys\n"
    "if '--only' in sys.argv:\n"
    "    print('  [  OK ] 합계 2/2 PASS — 고른 실행 — 판정 아님')\n"
    "    sys.exit(0)\n"
    "print('  [ 필요 ] test_가짜  1 PASS / 1 FAIL')\n"
    "print('  [ 필요 ] 합계 1/2 PASS')\n"
    "sys.exit(1)\n", encoding="utf-8")
_rd = BOX / "docs" / "spec" / "README.md"
_rd.write_text(_rd.read_text(encoding="utf-8") + "\n~~시험 취소선~~\n", encoding="utf-8")
rc5, out5 = _run(["tools/close.py", "--base", "HEAD"], cwd=BOX)
_summ = out5.split("마감 한 줄 요약", 1)[1] if "마감 한 줄 요약" in out5 else ""
_rows = re.findall(r"^\[(PASS|FAIL|갱신)\] ([^—\n]+)", _summ, re.M)
_lab = {lab.strip(): v for v, lab in _rows}
_doc = next((v for k, v in _lab.items() if k.startswith("마감 doctor")), None)
_chk = next((ln for ln in _summ.splitlines() if "문서 검사 일곱" in ln), "")
show("ⓑ 사전 점검 → doctor → 네 벌 → §7 상한 → 자산 해시 — 단계 일곱 줄이 전부 요약에 선다",
     len(_rows) == 7 and any(k.startswith("네 벌") for k in _lab) and "§7 상한" in _lab and "자산 해시" in _lab,
     f"줄 {len(_rows)} · {list(_lab)}")
show("ⓑ 넣은 FAIL(명세 취소선 · doctor 실패)이 FAIL로 서고 그 뒤 네 벌도 돌았다 · rc 1",
     rc5 == 1 and _doc == "FAIL" and "[FAIL]" in _chk and "모양" in _chk and _lab.get("네 벌") == "PASS"
     and "전부 같다" in _summ and re.search(r"FAIL [2-9]", _summ),
     f"rc {rc5} · doctor {_doc} · {_chk[:90]}")
_steps = re.search(r"단계 전문 (\S+)", _summ)                     # 사본의 단계 전문 — 시험이 지운다
if _steps and Path(_steps.group(1)).name.startswith("onto_close_"):
    shutil.rmtree(_steps.group(1), ignore_errors=True)
rc6, out6 = _run(["tools/close.py"])
show("ⓑ --base가 없으면 사용법 · rc 2", rc6 == 2 and "[사용법]" in out6, f"rc {rc6}")

# ────────────────────────────────────────────────────────────── ⓒ
print("\n■ ⓒ 명세 패치 — --check · --apply(사본)")
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
rc7, out7 = _run(["tools/spec_patch.py", "--check", str(GOOD), "--spec", str(SP)])
show("ⓒ 지금 명세에서 고른 문장의 패치 ⇒ --check 통과(사본 적용 뒤 문서 검사 일곱 그대로) · 쓰기 0",
     rc7 == 0 and "[PASS] 사본 적용 뒤 문서 검사 일곱" in out7 and _fp(SP) == _fp0, f"rc {rc7}")
rc8, out8 = _run(["tools/spec_patch.py", "--check", str(BAD), "--spec", str(SP)])
_fl = [ln for ln in out8.splitlines() if ln.startswith("[FAIL]")]
show("ⓒ 지금이 둘 · 없음 · 바뀔에 취소선 ⇒ 그 항목 이름과 함께 FAIL · 맞는 항목은 PASS",
     rc8 == 1 and any("둘" in x and "번" in x for x in _fl) and any("없음" in x and "0번" in x for x in _fl)
     and any(x.startswith(f"[FAIL] {_name} 취소선") and "취소선" in x.split("—", 1)[-1] for x in _fl)
     and f"[PASS] {_name} 좋음" in out8, " | ".join(_fl)[:240])
rc9, out9 = _run(["tools/spec_patch.py", "--apply", str(BAD), "--spec", str(SP)])
show("ⓒ --apply는 하나라도 어긋나면 쓰기 0 — 명세 사본 지문 같음",
     rc9 == 1 and "쓰기 0" in out9 and _fp(SP) == _fp0, f"rc {rc9}")
_others = {p.name: p.read_bytes() for p in SP.glob("*.md") if p.name != _name}
rc10, out10 = _run(["tools/spec_patch.py", "--apply", str(GOOD), "--spec", str(SP)])
_after = (SP / _name).read_text(encoding="utf-8")
show("ⓒ 다 맞으면 --apply가 그 문장만 바꾼다(다른 파일 바이트 그대로 · 임시 파일 흔적 0)",
     rc10 == 0 and _after == _text.replace(_line, _line + _new, 1)
     and all((SP / n).read_bytes() == b for n, b in _others.items()) and not list(SP.glob(".*.tmp")),
     f"rc {rc10}")
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

shutil.rmtree(T, ignore_errors=True)
print("\n" + "=" * 62)
print("전체 결과:", "PASS — B117 마감 도구" if allok else "FAIL")
sys.exit(0 if allok else 1)
