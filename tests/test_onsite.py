# -*- coding: utf-8 -*-
"""사내 조건 스위트 — `USE_MOCK=0` · 픽스처 없음 · 등록 산출만 (B71 ②).

**왜 이 스위트가 있나.** 회귀 전량이 `USE_MOCK=1`로 돈다. 사내 조건을 실행으로
밟은 것은 사용자뿐이었고, 그래서 **mock 자산이 운영 경로에 섞인 것을 사용자가
찾았다**(B70 · 실측 열째 — 「mock이랑 비교 돌아가는 거 뭐야」). 「사내에서 처음
밟는다」를 없애는 장치가 이것이다.

**조건 셋**: ①`USE_MOCK=0`(설정은 없다 — 실호출을 부르는 명령은 돌리지 않는다)
②`ONTO_FIXTURES`가 빈 폴더(mock 자산이 디스크에 없다) ③등록 산출 넷만 있다
(`data/doc_types.json` · `adapters/<dt>.py` · `schemas/<dt>.json` · `review/<dt>/`).

**판정은 성질이다** — 출력에 mock 자산 이름이 0이라는 것과 등록부 집합 등식.
문면을 세지 않는다.

**`doctor.py`는 `--env`만 돈다** — 전체를 돌리면 doctor가 이 스위트를 부르고
그 스위트가 다시 doctor를 부른다(무한). 조건에서 죽지 않는가만 본다.

사용: python tests/test_onsite.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import registry                                    # noqa: E402

allok = True
DT = "b71site"                       # 사내가 등록한 것처럼 세우는 doc_type
SAMPLE = ROOT / "tests" / "fixtures" / "raw" / "CP01.xlsx"
# **mock 자산의 이름** — 이 이름들이 사내 화면에 뜨면 그것이 결함이다.
MOCK_NAMES = ("cp", "pfmea", "ipqc", "ppt_process", "ppt_quality", "toc_report")


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def names_in(text):
    """출력에 등장한 mock 자산 이름 — **낱말 경계**로 센다(`cp`가 `cpu`에 걸리지 않게)."""
    import re
    return sorted({n for n in MOCK_NAMES
                   if re.search(rf"(?<![A-Za-z0-9_]){n}(?![A-Za-z0-9_])", text)})


class Site:
    """사내 조건 — 빈 픽스처 폴더 + 등록 산출 넷. 끝나면 되돌린다."""

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="b71site_"))
        self.ad = ROOT / "adapters" / f"{DT}.py"
        self.sc = ROOT / "schemas" / f"{DT}.json"
        self.rv = ROOT / "review" / DT
        # 어댑터·스키마는 **참조 어댑터의 사본**이다(이름만 이 등록의 것) — 새로
        # 짜면 그 코드가 또 하나의 mock 자산이 된다.
        src = (ROOT / "tests" / "fixtures" / "adapters" / "cp.py").read_text(encoding="utf-8")
        self.ad.parent.mkdir(exist_ok=True)
        self.ad.write_text(src.replace('"doc_type": "cp"', f'"doc_type": {DT!r}'),
                           encoding="utf-8")
        schema = json.loads((ROOT / "schemas" / "cp.json").read_text(encoding="utf-8"))
        # **등재가 먼저다** — 스키마 파일이 먼저 있으면 그 실재가 곧 내장 등록이라
        # `register`가 이름 중복으로 막는다(그 규칙은 옳다 — D-149 ②).
        registry.register(DT, layer=schema.get("layer") or "process",
                          adapter=f"adapters/{DT}.py", schema=f"schemas/{DT}.json",
                          adapter_version="1.0", approved_by="사내검수자",
                          approved_at="2026-09-15T00:00:00+00:00")
        self.sc.write_text(json.dumps({**schema, "doc_type": DT},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
        self.rv.mkdir(parents=True, exist_ok=True)
        (self.rv / "approval.json").write_text(
            json.dumps({"doc_type": DT, "approved_by": "사내검수자"},
                       ensure_ascii=False), encoding="utf-8")
        return self

    def __exit__(self, *a):
        registry.unregister(DT)
        for p in (self.ad, self.sc):
            p.unlink(missing_ok=True)
        shutil.rmtree(self.rv, ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, keep_fixtures=False):
        """사내 조건의 환경 — 실호출 모드 · 픽스처 없음 · 설정 없음.

        `keep_fixtures`는 **레포를 통째로 이식한 모습**이다(픽스처 폴더가 디스크에
        같이 온다 — 사내 실측이 그 상태였다). 그때도 `USE_MOCK=0`이면 섞이지
        않아야 한다: 가르는 것은 **폴더의 부재가 아니라 모드**다.
        """
        e = dict(os.environ, USE_MOCK="0",
                 ONTO_CONFIG=str(self.tmp / "_no_such_llm.json"))
        if keep_fixtures:
            e.pop("ONTO_FIXTURES", None)
        else:
            e["ONTO_FIXTURES"] = str(self.tmp)
        for k in ("LLM_GATEWAY_URL", "CHAT_MODEL", "EMBED_MODEL", "LLM_API_KEY"):
            e.pop(k, None)
        return e

    def run(self, *args, py=None, keep_fixtures=False):
        cmd = ([sys.executable, "-c", py] if py else
               [sys.executable, str(ROOT / "run.py"), *args])
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT),
                              env=self.env(keep_fixtures), stdin=subprocess.DEVNULL)


# ── B71 ① 추출 힌트도 mock 자산이다 ─────────────────────────────────────
#
# `core/extract.py`가 힌트(`tests/fixtures/extract_hints/<doc_id>.json`)를 모드와
# 무관하게 먼저 봤다. 사내 `doc_id`가 픽스처 이름과 겹치는 날 **실호출 결과가
# 조용히 mock 힌트로 바뀐다** — B70과 같은 병이고, 조용한 쪽이 더 나쁘다.
print("■ B71 ① — 추출 힌트는 USE_MOCK=1에서만")

HINT_DOC = "B71HINT"
_hint = ROOT / "tests" / "fixtures" / "extract_hints" / f"{HINT_DOC}.json"
_probe = (
    "import json,sys; sys.path.insert(0,'.')\n"
    "from core import extract as EX\n"
    "from core.bootstrap import load_config\n"
    "from core.pipeline import _vocab\n"
    f"EX.invalidate({HINT_DOC!r})\n"
    "cfg = load_config('process')\n"
    "env = {'doc_id': %r, 'doc_type': 'ppt_process', 'payload_kind': 'prose',\n"
    "       'chunks': [{'source_locator': 'C1', 'text': '노칭의 세척 노즐 압력',\n"
    "                   'section': 's1', 'meta': {}}]}\n"
    "out, _made = EX.extract(env, cfg, {'C1': 'cid1'}, _vocab(cfg))\n"
    f"EX.invalidate({HINT_DOC!r})\n"
    "print('OUT', json.dumps(out['candidates'][0], ensure_ascii=False))"
) % HINT_DOC


def _probe_run(env=None):
    r = subprocess.run([sys.executable, "-c", _probe], capture_output=True, text=True,
                       cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    ln = next((l[4:] for l in r.stdout.splitlines() if l.startswith("OUT ")), None)
    return (json.loads(ln) if ln else {}), r


_hint.parent.mkdir(parents=True, exist_ok=True)
_hint.write_text(json.dumps({"C1": {"entities": [{"surface": "세척 노즐 압력",
                                                  "category": "Property"}],
                                    "relations": [], "attach": []}},
                            ensure_ascii=False), encoding="utf-8")
try:
    with Site() as _s1:
        _live, _r1 = _probe_run(_s1.env(keep_fixtures=True))
    _mock, _r2 = _probe_run()
    show("① USE_MOCK=1이면 힌트를 쓴다 (지금과 같다 — 회귀가 이 세계에서 돈다)",
         [e.get("surface") for e in _mock.get("entities") or []] == ["세척 노즐 압력"],
         str(_mock)[:90] or _r2.stderr[-160:])
    show("① USE_MOCK=0이면 힌트 파일이 있어도 쓰지 않는다 — 실호출 경로로 간다",
         not (_live.get("entities") or [])
         and "NotConfigured" in str(_live.get("failed")),
         str(_live.get("failed"))[:110] or _r1.stderr[-160:])
finally:
    _hint.unlink(missing_ok=True)


print("\n■ B71 ② — 사내 조건(USE_MOCK=0 · 픽스처 없음 · 등록 산출만)")

with Site() as site:
    _pf = site.run("platform", "doctypes")
    show("② platform doctypes — 목록이 등록부뿐이다 (mock 자산 이름 0)",
         DT in _pf.stdout and not names_in(_pf.stdout),
         f"섞인 이름 {names_in(_pf.stdout)} · rc={_pf.returncode}")

    _sc = site.run("scan", str(SAMPLE))
    show("② scan — 대조 목록이 등록부 어댑터뿐이다",
         _sc.returncode == 0 and DT in _sc.stdout and not names_in(_sc.stdout),
         f"섞인 이름 {names_in(_sc.stdout)}")

    # **선택 근거는 값으로 본다** — 화면 문면을 세지 않는다.
    _sel = site.run(py=(
        "import json,sys; sys.path.insert(0,'.')\n"
        "from cli import ingest as I\n"
        f"s = I.select({str(SAMPLE)!r})\n"
        "print('SEL', json.dumps({'dt': s.get('doc_type'), 'st': s['status'],\n"
        "      'by': (s.get('basis') or {}).get('by')}, ensure_ascii=False))"))
    _j = json.loads(next((l[4:] for l in _sel.stdout.splitlines()
                          if l.startswith("SEL ")), "{}"))
    show("② 지정 없이 넣으면 **스캔이** 등록 doc_type을 고른다 (basis.by == scan)",
         _j.get("st") == "chosen" and _j.get("dt") == DT and _j.get("by") == "scan",
         str(_j) or _sel.stderr[-200:])

    _dry = site.run("ingest-file", str(SAMPLE), "--dry-run")
    show("② ingest-file --dry-run이 사내 조건에서 돈다 (LLM 0 · mock 이름 0)",
         _dry.returncode == 0 and DT in _dry.stdout and not names_in(_dry.stdout),
         f"섞인 이름 {names_in(_dry.stdout)} · rc={_dry.returncode}")

    _ls = site.run("register", "list")
    show("② register list — 등록 1건 (내장은 목록에 없다)",
         DT in _ls.stdout and not names_in(_ls.stdout),
         f"섞인 이름 {names_in(_ls.stdout)}")

    _dr = site.run(py=("import sys; sys.path.insert(0,'.')\n"
                       "import doctor; sys.exit(doctor.main(['--env']))"))
    show("② doctor 환경 점검이 이 조건에서 완주한다 (전체는 재귀라 돌리지 않는다)",
         _dr.returncode == 0 and not names_in(_dr.stdout), f"rc={_dr.returncode}")

    # ── 등록부 결손 — 실물 하나를 지운다(이식에서 빠진 그 상태) ──────────
    _src = site.ad.read_text(encoding="utf-8")
    site.ad.unlink()
    _miss = site.run("scan", str(SAMPLE))
    show("② 등록부 결손은 **상태 거부**다 — 이름과 다음 줄이 문면에 있다",
         _miss.returncode != 0
         and DT in (_miss.stdout + _miss.stderr)
         and "--revise" in (_miss.stdout + _miss.stderr),
         (_miss.stdout + _miss.stderr).strip().splitlines()[-3:-2])
    site.ad.write_text(_src, encoding="utf-8")

    # ── 픽스처가 **디스크에 있는** 조건 — 레포를 통째로 이식한 모습 ─────
    _keep = site.run("scan", str(SAMPLE), keep_fixtures=True)
    show("② 픽스처가 디스크에 있어도 USE_MOCK=0이면 섞이지 않는다 (이식의 실제 모습)",
         _keep.returncode == 0 and DT in _keep.stdout and not names_in(_keep.stdout),
         f"섞인 이름 {names_in(_keep.stdout)}")

    # ── 변이 — 기본 소재지의 mock 가드를 빼면 붉어진다 ────────────────
    _p = ROOT / "cli" / "scan.py"
    _orig = _p.read_text(encoding="utf-8")
    _mut = _orig.replace("(ADAPTER_DIRS if llm.use_mock() else [])", "ADAPTER_DIRS")
    assert _mut != _orig, "가드 문면이 바뀌었다 — 변이 시험이 대상을 못 찾는다"
    _p.write_text(_mut, encoding="utf-8")
    try:
        _bad = site.run("scan", str(SAMPLE), keep_fixtures=True)
    finally:
        _p.write_text(_orig, encoding="utf-8")
    show("② 변이 — 기본 소재지의 mock 가드를 빼면 mock 자산이 화면에 돌아온다",
         bool(names_in(_bad.stdout)), f"섞인 이름 {names_in(_bad.stdout)}")
    show("② 되돌리면 다시 0이다",
         not names_in(site.run("scan", str(SAMPLE), keep_fixtures=True).stdout))

print("\n" + "=" * 62)
print("전체 결과:", "PASS — 사내 조건 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
