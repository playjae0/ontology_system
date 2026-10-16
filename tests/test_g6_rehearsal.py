# -*- coding: utf-8 -*-
"""G6 — **추출 리허설은 운영 상태를 바꾸지 않는다** — 임시 상태 루트 · 새 종류로 인입할 때 재사용 (B116 · BLOCKERS 19 처분 c).

사내 길 그대로(실호출 모양): 운영 루트는 코드 밖 임시 폴더 · 모드와 게이트웨이는 **상태 루트의 `llm.json`**(로컬 HTTP 가짜
게이트웨이 `tests/stub_gateway.py` — 리허설의 추출은 하위 프로세스라 함수 바꿔 끼우기가 닿지 않는다) · 손잡이 파일 하나.
바닥은 **렌즈판이 있는 루트**(원래 종류 `rfq`가 렌즈 process · quality로 들어가 추출 · 개요 렌즈판이 있다)다.

잠그는 성질:
  ⓐ 운영 불변 — 이미 인입된 문서를 표본으로 등록 세 단계(generate → review 추출 리허설 → confirm) ⇒ 운영 루트 지문(파일 목록
     + 바이트 — `extract/outline/` 포함)이 전후 같다. 뺀 자리는 그 등록의 검수 자리 · 확정이 쓰는 등록 자리(등록부 · 어댑터 ·
     스키마) · 명령 로그 · **그 등록의 리허설 산출 자리**(B116 ②). 검수 뷰 ②구획은 채워진다. 층 둘(quality · process).
  ⓑ 재사용 — ⓐ 뒤 새 종류로 인입 ⇒ 추출 · 개요 LLM 0(가짜 게이트웨이의 지점별 호출 수) · 문서 대장 = 새 종류 · 그 리허설
     산출 자리가 빈다. 원래 종류로 다시 넣으면 리허설 산출을 보지 않는다(지금 규칙).
  ⓒ 같은 조건 — 임시 루트의 하위 실행이 `source: live` · 설정 파일(상태 루트의 `llm.json`) · 손잡이가 운영과 같다.
  ⓓ 끝 정리 — 부분 리허설 · 실패 · 중단(Ctrl-C) ⇒ 임시 폴더 흔적 0 · 운영 지문 그대로 · 리허설 산출 0.
표는 리허설이 없다 — 배정표를 보고 승인하고 추출 단계를 지나지 않는다(문서 4 §4.1). 표본 파싱은 같은 임시 루트 안에서 돈다
(검수 한 함수 `view.cmd_review`). 창작 표본이다 — 수는 메커니즘 확인이지 근거가 아니다([정정] 50).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.llm import gateway as _iso                              # noqa: E402
_iso.isolate()   # 시험은 셸 환경과 무관하게 격리 환경에서 돈다 (B111 ① · doctor와 같은 함수 · core의 다른 모듈보다 먼저)
sys.path.insert(0, str(ROOT / "tests"))
from stub_gateway import Stub                                      # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


T = Path(tempfile.mkdtemp(prefix="b116_"))
L, H, TMP = T / "운영", T / "home", T / "tmp"
for _d in (H, TMP, L / "raw"):
    _d.mkdir(parents=True)
shutil.copytree(ROOT / "layers", L / "layers")
RFQ = L / "raw" / "RFQ01.xlsx"
shutil.copy(ROOT / "tests/fixtures/raw/RFQ01.xlsx", RFQ)
(L / "knobs.json").write_text(json.dumps({"query_link_top_k": 7}), encoding="utf-8")
KNOBS = {"query_link_top_k": 7}

# 하위 실행 환경 — 격리 환경에서 **모드 · 설정 파일 판독만 되살린다**(상태 루트의 llm.json이 정한다 — 사내 런북과 같다)
ENV = {k: v for k, v in _iso.isolated_env().items() if k not in ("USE_MOCK", _iso.CONFIG_ENV)}
ENV.update({"ONTO_HOME": str(L), "HOME": str(H), "TMPDIR": str(TMP), "NO_COLOR": "1"})
SHEETS = "1:skip 2-4:prose 5:ref *:skip"


def run(*argv):
    r = subprocess.run([sys.executable, *argv], cwd=str(ROOT), env=ENV, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout + r.stderr


def reg(*a):
    return run("-m", "cli.register", *a)


def fp():
    """운영 루트 지문 — `{상대 경로: 바이트 해시}`(파일 목록 + 바이트)."""
    return {p.relative_to(L).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(L.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def _plain(rel):
    """락 파일은 그 대상의 이름으로 본다(`.x.json.lock` → `x.json`)."""
    head, _, name = rel.rpartition("/")
    if name.startswith(".") and name.endswith(".lock"):
        name = name[1:-len(".lock")]
    return f"{head}/{name}" if head else name


def changed(a, b, dts=(), confirmed=()):
    """지문 차 — 뺀 자리(그 등록의 검수 자리 · 확정의 등록 자리 · 명령 로그 · 그 등록의 리허설 산출 자리) 밖만."""
    def out(rel):
        r = _plain(rel)
        if r.startswith("work/logs/"):
            return True
        for dt in dts:
            if r.startswith((f"registry/review/{dt}/", f"work/extract/rehearsal/{dt}/")):
                return True
        for dt in confirmed:
            if r in ("registry/doc_types.json", f"registry/adapters/{dt}.py", f"registry/schemas/{dt}.json"):
                return True
        return False
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k) and not out(k))


def tmp_left():
    return sorted(p.name for p in TMP.iterdir() if p.name.startswith("onto_rehearsal_"))


def carry(dt):
    d = L / "work/extract/rehearsal" / dt / "RFQ01"
    return sorted(p.relative_to(d).as_posix() for p in d.rglob("*.json")) if d.exists() else []


def view(dt):
    return json.loads((L / "registry/review" / dt / "view.json").read_text(encoding="utf-8"))["sections"].get(
        "extract_rehearsal") or {}


def ex(body):
    """추출 답(창작) — 본문에 든 골격 이름을 닫힌 카테고리 하나로."""
    cats = list(body.get("categories") or {})
    cat = "Process" if "Process" in cats else (cats[0] if cats else "Process")
    text = body.get("chunk") or ""
    return {"entities": [{"surface": w, "category": cat, "parent": None, "belongs_to": None}
                         for w in ("노칭", "타발", "스태킹") if w in text], "relations": [], "about": []}


print("\n■ B116 — 추출 리허설은 임시 상태 루트에서 · 새 종류로 인입할 때 재사용")
show("전제 — 레포 루트에 llm.local.json이 없다(있으면 그 파일이 상태 루트의 llm.json을 이긴다)",
     not (ROOT / "llm.local.json").exists())
with Stub(by={"extract": ex}) as gw:
    gw.config(L)
    # ── 바닥 — 원래 종류 rfq · 렌즈 둘로 인입(렌즈판이 있는 루트)
    steps = [run("run.py", "bootstrap"),
             reg("generate", "rfq", "process", str(RFQ), "--use-basic", "--sheets", SHEETS),
             reg("review", "rfq", "--no-llm-coord"), reg("confirm", "rfq", "--by", "시험"),
             run("run.py", "register", "lenses", "rfq", "process,quality"),
             run("run.py", "ingest-file", str(RFQ), "--doc-type", "rfq", "--coord", "노칭")]
    _lens = sorted(p.relative_to(L / "work/extract").as_posix() for p in (L / "work/extract").rglob("RFQ01@*.json"))
    show("바닥 — 렌즈판이 있는 운영 루트(원래 종류 rfq · 추출 · 개요 렌즈판)",
         all(rc == 0 for rc, _o in steps) and len(_lens) >= 3, f"{[rc for rc, _o in steps]} · {_lens}")
    f0 = fp()

    # ── ⓐ 이미 인입된 문서를 표본으로 — 층 둘
    outs = {}
    for dt, lay in (("rfq2", "quality"), ("rfq3", "process")):
        outs[dt] = [reg("generate", dt, lay, str(RFQ), "--use-basic"),
                    reg("review", dt, "--no-llm-coord", "--extract"), reg("confirm", dt, "--by", "시험")]
    f1 = fp()
    _ch = changed(f0, f1, ("rfq2", "rfq3"), ("rfq2", "rfq3"))
    show("ⓐ 운영 불변 — 등록 세 단계 두 벌(층 quality · process) 전후 운영 루트 지문이 같다 "
         "(그래프 · 문서 대장 · 청크 · 큐 · 체크포인트 렌즈판 · extract/outline/ · 시트 역할 · 문서 좌표)",
         not _ch and all(rc == 0 for o in outs.values() for rc, _x in o), _ch[:6])
    for dt in ("rfq2", "rfq3"):
        _v = view(dt)
        show(f"ⓐ 검수 뷰 ②구획이 채워진다 — {dt}(임시 루트의 청크에서 · 개체 후보 · 본문 발췌)",
             (_v.get("totals") or {}).get("chunks", 0) > 0 and _v.get("kept") is True
             and any(c.get("excerpt") for c in _v.get("by_chunk") or []), str(_v.get("totals")))
        show(f"ⓐ 리허설 산출이 ④단 자리에 함께 남는다 — {dt}(추출 · 개요 체크포인트 · 그 등록 · 그 문서)",
             "extract/RFQ01.json" in carry(dt) and "outline/RFQ01.json" in carry(dt), str(carry(dt)))
    _rv = outs["rfq2"][1][1]
    show("ⓐ 안내 줄 — 이미 인입된 문서 · 리허설은 임시 폴더 · 운영은 그대로 · 새 종류로 넣는 줄",
         "이미 인입된 문서다(doc_type rfq) — 리허설은 임시 폴더에서 돌아 운영은 그대로" in _rv
         and f"python run.py ingest-file {RFQ} --doc-type rfq2" in _rv and "⚠ 추출 리허설 —" not in _rv,
         [ln.strip() for ln in _rv.splitlines() if "이미 인입된" in ln][:1])

    # ── ⓒ 같은 조건 — 임시 루트의 하위 실행
    _c = view("rfq2").get("conditions") or {}
    show("ⓒ 임시 루트에서 실호출 그대로 — source live · 모드 live(mock 강제 0)",
         view("rfq2").get("source") == "live" and _c.get("mode") == "live", str(_c.get("mode")))
    show("ⓒ 설정 파일이 그대로 보인다 — 하위 실행이 읽은 것 = 부모가 읽은 상태 루트의 llm.json",
         _c.get("config_same") is True and str(_c.get("config_file") or "").endswith("llm.json"), str(_c))
    show("ⓒ 손잡이가 운영과 같다 — 임시 루트의 파일 값 = 운영 knobs.json", _c.get("knobs") == KNOBS
         and _c.get("knobs_same") is True, str(_c.get("knobs")))
    show("ⓒ 검수 화면이 조건을 말한다 — 「리허설 조건 — 임시 상태 폴더 · 모드 live · … 운영과 같다」",
         "리허설 조건 — 임시 상태 폴더 · 모드 live · 설정 파일 llm.json(운영과 같다)" in _rv)
    show("ⓓ 끝 정리(성공) — 임시 폴더 흔적 0", not tmp_left(), str(tmp_left()))

    # ── ⓑ 새 종류로 인입 — 추출 · 개요 LLM 0
    for dt in ("rfq2", "rfq3"):
        gw.calls.clear()
        _rc, _o = run("run.py", "ingest-file", str(RFQ), "--doc-type", dt)
        _reg = json.loads((L / "data/doc_registry.json").read_text(encoding="utf-8"))
        show(f"ⓑ 새 종류({dt})로 인입 — 추출 · 개요 LLM 0 · 문서 대장 = {dt} · 리허설 산출 자리가 빈다",
             _rc == 0 and gw.calls.get("extract", 0) == 0 and gw.calls.get("outline", 0) == 0
             and _reg["RFQ01"]["doc_type"] == dt and not carry(dt), f"호출 {gw.calls} · 대장 {_reg['RFQ01']['doc_type']}")
        show(f"ⓑ 화면 — 「리허설 산출({dt} 등록 검수)을 운영 자리로 옮겼다」 → 체크포인트 재사용(LLM 0)",
             f"추출 — 리허설 산출({dt} 등록 검수)을 운영 자리로 옮겼다" in _o
             and "추출 — 체크포인트 재사용(LLM 0)" in _o and "[추출 체크포인트 재사용]" in _o)
    _rc, _o = run("run.py", "ingest-file", str(RFQ), "--doc-type", "rfq")
    show("ⓑ 원래 종류로 다시 넣으면 지금 규칙 — 리허설 산출을 보지 않는다 · 문서 대장 = rfq",
         _rc == 0 and "리허설 산출(" not in _o
         and json.loads((L / "data/doc_registry.json").read_text(encoding="utf-8"))["RFQ01"]["doc_type"] == "rfq")

    # ── ⓓ 끝 정리 — 부분 리허설 · 실패 · 중단
    fP = fp()
    reg("generate", "rfqp", "quality", str(RFQ), "--use-basic")
    _rc, _o = reg("review", "rfqp", "--no-llm-coord", "--extract", "--rows", "3")
    _ch = changed(fP, fp(), ("rfqp",))
    show("ⓓ 부분 리허설 — 산출을 남기지 않는다 · 임시 폴더 흔적 0 · 운영 지문 그대로",
         view("rfqp").get("kept") is False and not carry("rfqp") and not tmp_left() and not _ch,
         f"{view('rfqp').get('note')} · {_ch[:4]}")
    reg("generate", "rfqf", "quality", str(RFQ), "--use-basic")
    gw.fail["outline"] = 500
    _rc, _o = reg("review", "rfqf", "--no-llm-coord", "--extract")
    gw.fail.clear()
    _ch = changed(fP, fp(), ("rfqp", "rfqf"))
    show("ⓓ 실패(게이트웨이 500) — 「추출 리허설 실패」 · 산출 0 · 임시 폴더 흔적 0 · 운영 지문 그대로",
         "추출 리허설 실패" in _o and view("rfqf").get("source") == "none" and not carry("rfqf")
         and not tmp_left() and not _ch, f"{_ch[:4]} · {tmp_left()}")
    reg("generate", "rfqi", "quality", str(RFQ), "--use-basic")
    gw.delay["extract"] = 120
    _p = subprocess.Popen([sys.executable, "-m", "cli.register", "review", "rfqi", "--no-llm-coord", "--extract"],
                          cwd=str(ROOT), env=ENV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True)
    _seen = gw.seen.wait(180)
    os.killpg(_p.pid, signal.SIGINT)                  # 터미널의 Ctrl-C — 앞 프로세스 묶음 전부(부모 · 하위 실행)
    _out = _p.communicate(timeout=120)[0]
    gw.delay.clear()
    _ch = changed(fP, fp(), ("rfqp", "rfqf", "rfqi"))
    show("ⓓ 중단(Ctrl-C · 추출 도중) — 종료 코드 130 · 산출 0 · 임시 폴더 흔적 0 · 운영 지문 그대로",
         _seen and _p.returncode == 130 and not carry("rfqi") and not tmp_left() and not _ch,
         f"rc {_p.returncode} · {_ch[:4]} · {tmp_left()}")
    show("ⓓ 중단 화면에 트레이스백 0", "Traceback" not in _out, _out.strip().splitlines()[-2:])

shutil.rmtree(T, ignore_errors=True)
print(f"\n{'ALL PASS' if allok else 'FAILURES ABOVE'}")
sys.exit(0 if allok else 1)
