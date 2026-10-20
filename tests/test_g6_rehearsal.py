# -*- coding: utf-8 -*-
"""G6 — **추출 리허설은 운영 상태를 바꾸지 않는다** — 임시 상태 루트 · 새 종류로 인입할 때 재사용 (B116 · BLOCKERS 19 처분 c).

사내 길 그대로(실호출 모양): 운영 루트는 코드 밖 임시 폴더 · 모드와 게이트웨이는 **상태 루트의 `llm.json`**(로컬 HTTP 가짜
게이트웨이 `tests/stub_gateway.py` — 리허설의 추출은 하위 프로세스라 함수 바꿔 끼우기가 닿지 않는다) · 손잡이 파일 하나.
바닥은 **렌즈판이 있는 루트**(원래 종류 `rfq`가 렌즈 process · quality로 들어가 추출 · 개요 렌즈판이 있다)다.

잠그는 성질:
  ⓐ 운영 불변 — 이미 인입된 문서를 표본으로 등록 세 단계(generate → review 추출 리허설 → confirm) ⇒ 운영 루트 지문(파일 목록
     + 바이트 — `extract/outline/` 포함)이 전후 같다. 뺀 자리는 그 등록의 검수 자리 · 확정이 쓰는 등록 자리(등록부 · 어댑터 ·
     스키마) · 명령 로그 · **그 등록의 리허설 산출 자리**(B116 ②). 검수 뷰 ②구획은 채워진다. 층 하나(quality — 리허설은 층에
     무관한 자리다 · 층 호환은 층 어휘 정적 점검 + 네 벌이 잡는다 · B121 ②ⓒ).
  ⓑ 재사용 — ⓐ 뒤 새 종류로 인입 ⇒ 추출 · 개요 LLM 0(가짜 게이트웨이의 지점별 호출 수) · 문서 대장 = 새 종류 · 그 리허설
     산출 자리가 빈다. 원래 종류로 다시 넣으면 리허설 산출을 보지 않는다(지금 규칙).
  ⓒ 같은 조건 — 임시 루트의 하위 실행이 `source: live` · 설정 파일(상태 루트의 `llm.json`) · 손잡이가 운영과 같다.
  ⓓ 끝 정리 — 부분 리허설 · 실패 · 중단(Ctrl-C) ⇒ 임시 폴더 흔적 0 · 운영 지문 그대로 · 리허설 산출 0(한 등록을 차례로 검수 —
     등록마다 생성을 다시 하지 않는다 · B121 ②ⓓ).
표는 리허설이 없다 — 배정표를 보고 승인하고 추출 단계를 지나지 않는다(문서 4 §4.1). 표본 파싱은 같은 임시 루트 안에서 돈다
(검수 한 함수 `view.cmd_review`). ⓓ는 바닥의 **사본 루트**(가짜 게이트웨이 · 임시 폴더 · HOME 따로)에서 ⓐⓒⓑ와 동시에 돈다 —
같은 루트에 두 실행을 겹치지 않는다(B121 ②ⓓ). 창작 표본이다 — 수는 메커니즘 확인이지 근거가 아니다([정정] 50).
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
from concurrent.futures import ThreadPoolExecutor
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
KNOBS = {"query_link_top_k": 7}
# 하위 실행 환경 — 격리 환경에서 **모드 · 설정 파일 판독만 되살린다**(상태 루트의 llm.json이 정한다 — 사내 런북과 같다)
BASE_ENV = {k: v for k, v in _iso.isolated_env().items() if k not in ("USE_MOCK", _iso.CONFIG_ENV)}
BASE_ENV["NO_COLOR"] = "1"
SHEETS = "1:skip 2-4:prose 5:ref *:skip"


class World:
    """운영 루트 하나 — 상태 루트 · HOME · 임시 폴더 · 하위 실행 환경(루트마다 따로 — 동시에 돌아도 섞이지 않는다 · B121 ②ⓓ)."""

    def __init__(self, name, src=None):
        self.L, self.TMP, home = T / name, T / f"{name}_tmp", T / f"{name}_home"
        for _d in (home, self.TMP):
            _d.mkdir(parents=True)
        if src is None:
            (self.L / "raw").mkdir(parents=True)
            shutil.copytree(ROOT / "layers", self.L / "layers")
            shutil.copy(ROOT / "tests/fixtures/raw/RFQ01.xlsx", self.L / "raw" / "RFQ01.xlsx")
            (self.L / "knobs.json").write_text(json.dumps(KNOBS), encoding="utf-8")
        else:
            shutil.copytree(src.L, self.L)                 # 바닥을 다시 세우지 않는다 — 다 선 운영 루트의 사본
        self.RFQ = self.L / "raw" / "RFQ01.xlsx"
        self.ENV = {**BASE_ENV, "ONTO_HOME": str(self.L), "HOME": str(home), "TMPDIR": str(self.TMP)}

    def run(self, *argv):
        r = subprocess.run([sys.executable, *argv], cwd=str(ROOT), env=self.ENV, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=600)
        return r.returncode, r.stdout + r.stderr

    def reg(self, *a):
        return self.run("-m", "cli.register", *a)

    def fp(self):
        """운영 루트 지문 — `{상대 경로: 바이트 해시}`(파일 목록 + 바이트)."""
        return {p.relative_to(self.L).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.L.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}

    def tmp_left(self):
        return sorted(p.name for p in self.TMP.iterdir() if p.name.startswith("onto_rehearsal_"))

    def carry(self, dt):
        d = self.L / "work/extract/rehearsal" / dt / "RFQ01"
        return sorted(p.relative_to(d).as_posix() for p in d.rglob("*.json")) if d.exists() else []

    def view(self, dt):
        return json.loads((self.L / "registry/review" / dt / "view.json").read_text(encoding="utf-8"))["sections"].get(
            "extract_rehearsal") or {}

    def doc_type_of(self):
        return json.loads((self.L / "data/doc_registry.json").read_text(encoding="utf-8"))["RFQ01"]["doc_type"]


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


def ex(body):
    """추출 답(창작) — 본문에 든 골격 이름을 닫힌 카테고리 하나로."""
    cats = list(body.get("categories") or {})
    cat = "Process" if "Process" in cats else (cats[0] if cats else "Process")
    text = body.get("chunk") or ""
    return {"entities": [{"surface": w, "category": cat, "parent": None, "belongs_to": None}
                         for w in ("노칭", "타발", "스태킹") if w in text], "relations": [], "about": []}


def flow_abc(w, gw):
    """ⓐ ⓒ ⓑ — 바닥 루트에서 새 종류 rfq2(층 quality) 등록 세 단계 → 새 종류 · 원래 종류로 인입. 판정 줄을 돌려준다."""
    out, dt = [], "rfq2"
    f0 = w.fp()
    steps = [w.reg("generate", dt, "quality", str(w.RFQ), "--use-basic"),
             w.reg("review", dt, "--no-llm-coord", "--extract"), w.reg("confirm", dt, "--by", "시험")]
    _ch = changed(f0, w.fp(), (dt,), (dt,))
    out.append(("ⓐ 운영 불변 — 등록 세 단계(층 quality) 전후 운영 루트 지문이 같다 "
                "(그래프 · 문서 대장 · 청크 · 큐 · 체크포인트 렌즈판 · extract/outline/ · 시트 역할 · 문서 좌표)",
                not _ch and all(rc == 0 for rc, _x in steps), _ch[:6]))
    _v = w.view(dt)
    out.append((f"ⓐ 검수 뷰 ②구획이 채워진다 — {dt}(임시 루트의 청크에서 · 개체 후보 · 본문 발췌)",
                (_v.get("totals") or {}).get("chunks", 0) > 0 and _v.get("kept") is True
                and any(c.get("excerpt") for c in _v.get("by_chunk") or []), str(_v.get("totals"))))
    out.append((f"ⓐ 리허설 산출이 ④단 자리에 함께 남는다 — {dt}(추출 · 개요 체크포인트 · 그 등록 · 그 문서)",
                "extract/RFQ01.json" in w.carry(dt) and "outline/RFQ01.json" in w.carry(dt), str(w.carry(dt))))
    _rv = steps[1][1]
    # 화면은 성질로 잰다 — 이미 인입된 표본이면 새 종류로 넣는 칠 수 있는 줄이 있다(문구는 재지 않는다 · B121 ②ⓐ)
    _next = [ln.strip() for ln in _rv.splitlines() if f"python run.py ingest-file {w.RFQ} --doc-type {dt}" in ln]
    out.append(("ⓐ 안내 줄 — 이미 인입된 문서면 새 종류로 넣는 칠 수 있는 줄을 준다", bool(_next), _next[:1]))

    # ── ⓒ 같은 조건 — 임시 루트의 하위 실행
    _c = _v.get("conditions") or {}
    out.append(("ⓒ 임시 루트에서 실호출 그대로 — source live · 모드 live(mock 강제 0)",
                _v.get("source") == "live" and _c.get("mode") == "live", str(_c.get("mode"))))
    out.append(("ⓒ 설정 파일이 그대로 보인다 — 하위 실행이 읽은 것 = 부모가 읽은 상태 루트의 llm.json",
                _c.get("config_same") is True and str(_c.get("config_file") or "").endswith("llm.json"), str(_c)))
    out.append(("ⓒ 손잡이가 운영과 같다 — 임시 루트의 파일 값 = 운영 knobs.json",
                _c.get("knobs") == KNOBS and _c.get("knobs_same") is True, str(_c.get("knobs"))))
    # 화면은 성질로 — 조건 줄이 모드와 설정 파일을 함께 말한다(문구는 재지 않는다 · B121 ②ⓐ)
    _cl = [ln.strip() for ln in _rv.splitlines() if f"모드 {_c.get('mode')}" in ln and "llm.json" in ln]
    out.append(("ⓒ 검수 화면이 조건을 말한다 — 모드 · 설정 파일이 한 줄에", bool(_cl), _cl[:1]))
    out.append(("ⓓ 끝 정리(성공) — 임시 폴더 흔적 0", not w.tmp_left(), str(w.tmp_left())))

    # ── ⓑ 새 종류로 인입 — 추출 · 개요 LLM 0
    gw.calls.clear()
    _rc, _o = w.run("run.py", "ingest-file", str(w.RFQ), "--doc-type", dt)
    out.append((f"ⓑ 새 종류({dt})로 인입 — 추출 · 개요 LLM 0 · 문서 대장 = {dt} · 리허설 산출 자리가 빈다",
                _rc == 0 and gw.calls.get("extract", 0) == 0 and gw.calls.get("outline", 0) == 0
                and w.doc_type_of() == dt and not w.carry(dt), f"호출 {gw.calls} · 대장 {w.doc_type_of()}"))
    # 화면은 성질로 — 옮긴 출처(그 등록)와 재사용 표지가 화면에 있다(문구는 재지 않는다 · B121 ②ⓐ)
    out.append((f"ⓑ 화면 — 리허설 산출의 출처({dt} 등록)와 체크포인트 재사용을 말한다",
                any(dt in ln and "리허설 산출" in ln for ln in _o.splitlines()) and "[추출 체크포인트 재사용]" in _o))
    _rc, _o = w.run("run.py", "ingest-file", str(w.RFQ), "--doc-type", "rfq")
    out.append(("ⓑ 원래 종류로 다시 넣으면 지금 규칙 — 리허설 산출을 보지 않는다 · 문서 대장 = rfq",
                _rc == 0 and "리허설 산출(" not in _o and w.doc_type_of() == "rfq"))
    return out


def flow_d(w, gw):
    """ⓓ 끝 정리 — 한 등록(rfqd)을 부분 리허설 → 실패 → 중단 차례로 검수(B121 ②ⓓ — 등록마다 생성을 다시 하지 않는다)."""
    out, dt = [], "rfqd"
    fP = w.fp()
    w.reg("generate", dt, "quality", str(w.RFQ), "--use-basic")
    # 기대 변경(B119 ① — 생성 관문의 표본 파싱도 문서 구조를 부르고 그 보존분이 리허설 산출에 남는다) — 잴 것은 「이 실행이 더한 것 0」
    _c0 = w.carry(dt)
    w.reg("review", dt, "--no-llm-coord", "--extract", "--rows", "3")
    _ch = changed(fP, w.fp(), (dt,))
    out.append(("ⓓ 부분 리허설 — 산출을 남기지 않는다 · 임시 폴더 흔적 0 · 운영 지문 그대로",
                w.view(dt).get("kept") is False and w.carry(dt) == _c0 and not w.tmp_left() and not _ch,
                f"{w.view(dt).get('note')} · {_ch[:4]} · 산출 {w.carry(dt)} · 흔적 {w.tmp_left()}"))
    gw.fail["outline"] = 500
    _rc, _o = w.reg("review", dt, "--no-llm-coord", "--extract")
    gw.fail.clear()
    _ch = changed(fP, w.fp(), (dt,))
    out.append(("ⓓ 실패(게이트웨이 500) — 「추출 리허설 실패」 · 산출 0 · 임시 폴더 흔적 0 · 운영 지문 그대로",
                "추출 리허설 실패" in _o and w.view(dt).get("source") == "none" and w.carry(dt) == _c0
                and not w.tmp_left() and not _ch, f"{_ch[:4]} · {w.tmp_left()}"))
    gw.delay["extract"] = 120
    _p = subprocess.Popen([sys.executable, "-m", "cli.register", "review", dt, "--no-llm-coord", "--extract"],
                          cwd=str(ROOT), env=w.ENV, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True)
    _seen = gw.seen.wait(180)
    os.killpg(_p.pid, signal.SIGINT)                  # 터미널의 Ctrl-C — 앞 프로세스 묶음 전부(부모 · 하위 실행)
    _out = _p.communicate(timeout=120)[0]
    gw.delay.clear()
    _ch = changed(fP, w.fp(), (dt,))
    out.append(("ⓓ 중단(Ctrl-C · 추출 도중) — 종료 코드 130 · 산출 0 · 임시 폴더 흔적 0 · 운영 지문 그대로",
                _seen and _p.returncode == 130 and w.carry(dt) == _c0 and not w.tmp_left() and not _ch,
                f"rc {_p.returncode} · {_ch[:4]} · {w.tmp_left()}"))
    out.append(("ⓓ 중단 화면에 트레이스백 0", "Traceback" not in _out, _out.strip().splitlines()[-2:]))
    return out


print("\n■ B116 — 추출 리허설은 임시 상태 루트에서 · 새 종류로 인입할 때 재사용")
show("전제 — 레포 루트에 llm.local.json이 없다(있으면 그 파일이 상태 루트의 llm.json을 이긴다)",
     not (ROOT / "llm.local.json").exists())
with Stub(by={"extract": ex}) as gw, Stub(by={"extract": ex}) as gw_d:
    A = World("운영")
    gw.config(A.L)
    # ── 바닥 — 원래 종류 rfq · 렌즈 둘로 인입(렌즈판이 있는 루트)
    steps = [A.run("run.py", "bootstrap"),
             A.reg("generate", "rfq", "process", str(A.RFQ), "--use-basic", "--sheets", SHEETS),
             A.reg("review", "rfq", "--no-llm-coord"), A.reg("confirm", "rfq", "--by", "시험"),
             A.run("run.py", "register", "lenses", "rfq", "process,quality"),
             A.run("run.py", "ingest-file", str(A.RFQ), "--doc-type", "rfq", "--coord", "노칭")]
    _lens = sorted(p.relative_to(A.L / "work/extract").as_posix() for p in (A.L / "work/extract").rglob("RFQ01@*.json"))
    show("바닥 — 렌즈판이 있는 운영 루트(원래 종류 rfq · 추출 · 개요 렌즈판)",
         all(rc == 0 for rc, _o in steps) and len(_lens) >= 3, f"{[rc for rc, _o in steps]} · {_lens}")
    # ── ⓓ는 바닥의 사본에서 — 루트 · 가짜 게이트웨이 · 임시 폴더가 따로라 ⓐⓒⓑ와 동시에 돈다(B121 ②ⓓ)
    D = World("사본", src=A)
    gw_d.config(D.L)
    with ThreadPoolExecutor(max_workers=2) as pool:
        _fa, _fd = pool.submit(flow_abc, A, gw), pool.submit(flow_d, D, gw_d)
        for _row in _fa.result() + _fd.result():
            show(*_row)

shutil.rmtree(T, ignore_errors=True)
print(f"\n{'ALL PASS' if allok else 'FAILURES ABOVE'}")
sys.exit(0 if allok else 1)
