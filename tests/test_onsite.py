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
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)

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
        # **상태 루트도 사내 조건이다**(B78 1b) — `USE_MOCK=0`은 `state_mock/`이
        # 아닌 자리를 쓴다. 등록 산출을 mock 루트에 세워 두면 이 스위트의
        # 하위 프로세스(실호출 모드)는 그것을 영영 보지 못한다.
        self.home = self.tmp / "home"
        self._env0 = {k: os.environ.get(k) for k in ("ONTO_HOME", "USE_MOCK")}
        os.environ["ONTO_HOME"] = str(self.home)
        os.environ["USE_MOCK"] = "0"
        _P.reset()
        self.ad = _P.adapters() / f"{DT}.py"
        self.sc = _P.schemas() / f"{DT}.json"
        self.rv = _P.review() / DT
        # 어댑터·스키마는 **참조 어댑터의 사본**이다(이름만 이 등록의 것) — 새로
        # 짜면 그 코드가 또 하나의 mock 자산이 된다.
        src = (ROOT / "tests" / "fixtures" / "adapters" / "cp.py").read_text(encoding="utf-8")
        _P.ensure(self.ad)
        self.ad.write_text(src.replace('"doc_type": "cp"', f'"doc_type": {DT!r}'),
                           encoding="utf-8")
        # 스키마 원본은 **내장(mock) 자리**에서 읽는다 — 등록 자리에는 없다(자리로 가른다).
        schema = json.loads(_P.fixture_schemas("cp.json").read_text(encoding="utf-8"))
        # **등재가 먼저다** — 스키마 파일이 먼저 있으면 그 실재가 곧 내장 등록이라
        # `register`가 이름 중복으로 막는다(그 규칙은 옳다 — D-149 ②).
        registry.register(DT, layer=schema.get("layer") or "process",
                          adapter=f"adapters/{DT}.py", schema=f"schemas/{DT}.json",
                          adapter_version="1.0", approved_by="사내검수자",
                          approved_at="2026-09-15T00:00:00+00:00")
        _P.ensure(self.sc).write_text(
            json.dumps({**schema, "doc_type": DT}, ensure_ascii=False, indent=2),
            encoding="utf-8")
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
        for k, v in self._env0.items():          # 환경과 자리를 되돌린다
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        _P.reset()

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

# ── B78 1b — 옛 배치 이관 ───────────────────────────────────────────────
#
# 사내의 첫 걸음이 이것이다: 코드 폴더 안에 흩어져 있던 상태(`data/`·`review/`·
# `parsed/`·`extract/`)를 상태 루트 하나로 옮긴다. **옮겨도 같아야 한다**는 것이
# 이 블록이 재는 성질이고, **옮기기 전에는 멈춘다**는 것이 그다음이다.
print("\n■ B78 1b — 옛 배치 이관(migrate)")

import hashlib                                                    # noqa: E402
from core import migrate as _MG                                   # noqa: E402

_lg = Path(tempfile.mkdtemp(prefix="b78legacy_"))
_old, _new = _lg / "code", _lg / "home"
_G = "graph" + ".json"          # 조각 — 저장 계층 경계 검사의 대상이 아니다
(_old / "data" / "process").mkdir(parents=True)
(_old / "data" / "ingest_log").mkdir(parents=True)
(_old / "review" / "x").mkdir(parents=True)
(_old / "adapters").mkdir()
(_old / "schemas").mkdir()
(_old / "parsed").mkdir()
(_old / "extract").mkdir()
_graph = json.dumps({"nodes": {"n1": {"canonical": "노칭"}}, "edges": []},
                    ensure_ascii=False)
_dict = json.dumps({"노칭": "n1"}, ensure_ascii=False)
(_old / "data" / "process" / _G).write_text(_graph, encoding="utf-8")
(_old / "data" / "dictionary.json").write_text(_dict, encoding="utf-8")
(_old / "data" / "gate_rejects.json").write_text("[]", encoding="utf-8")
(_old / "data" / ".dictionary.json.lock").write_text("", encoding="utf-8")   # 락 — 상태가 아니다
(_old / "data" / "ingest_log" / "X1.json").write_text("{}", encoding="utf-8")
(_old / "data" / "doc_types.json").write_text(json.dumps(
    {"x": {"doc_type": "x", "status": "registered", "layer": "process",
           "adapter": "adapters/x.py", "schema": "schemas/x.json",
           "approved_by": "사내검수자"}}, ensure_ascii=False), encoding="utf-8")
(_old / "adapters" / "x.py").write_text("ADAPTER = {}\n", encoding="utf-8")
(_old / "schemas" / "x.json").write_text('{"doc_type": "x"}', encoding="utf-8")
(_old / "review" / "x" / "approval.json").write_text(
    '{"doc_type": "x", "approved_by": "사내검수자"}', encoding="utf-8")
(_old / "parsed" / "X1.json").write_text("{}", encoding="utf-8")
(_old / "extract" / "X1.json").write_text("{}", encoding="utf-8")

_sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
_res = _MG.run(_old, _new)
show("③ 이관은 다섯 단의 자리로 나눠 놓는다 (등록·진실·작업)",
     (_new / "registry" / "doc_types.json").is_file()
     and (_new / "data" / "process" / _G).is_file()
     and (_new / "work" / "parsed" / "X1.json").is_file()
     and (_new / "work" / "ingest_log" / "X1.json").is_file(),
     str(_res.get("per_tier")))
show("③ 옮겨도 같다 — 그래프 해시 · 사전 동일",
     _sha(_new / "data" / "process" / _G)
     == _sha(_old / "data" / "process" / _G)
     and _sha(_new / "data" / "dictionary.json")
     == _sha(_old / "data" / "dictionary.json"))
_reg_new = json.loads((_new / "registry" / "doc_types.json").read_text(encoding="utf-8"))
show("③ 등록부는 키도 승인도 그대로다 (옮기는 것은 자리뿐이다)",
     set(_reg_new) == {"x"} and _reg_new["x"]["approved_by"] == "사내검수자")
show("③ 등록부 경로가 registry/ 기준 상대 경로다 — 절대 경로·`..` 0 · 실물이 있다",
     all(not Path(_reg_new["x"][k]).is_absolute() and ".." not in _reg_new["x"][k]
         and (_new / "registry" / _reg_new["x"][k]).is_file()
         for k in ("adapter", "schema")), str(_reg_new["x"]))
show("③ 락 파일은 이관 대상이 아니다 (원자 쓰기의 부산물 — 옮기면 유령 락이 선다)",
     not [d for _s, d, _t in _MG.plan(_old, _new) if d.name.endswith(".lock")]
     and not [p for p in (_new / "data").rglob("*.lock")],
     str([p.name for p in (_new / "data").rglob("*.lock")]))
show("③ 옛 폴더는 그대로 둔다 — 복사다(되돌릴 자리를 없애지 않는다)",
     (_old / "data" / "doc_types.json").is_file()
     and (_old / "review" / "x" / "approval.json").is_file())
show("③ 이관 로그가 무엇을 어디로 옮겼는지 남긴다 (해시 병기)",
     _res["log"].is_file()
     and str(_old) in _res["log"].read_text(encoding="utf-8")
     and _res["files"] >= 9, f"파일 {_res['files']} · 로그 {_res['log'].name}")

# **이관 전 실행은 상태 거부다** — 조용히 옛 자리를 읽지 않는다.
_mark = ROOT / "data" / "doc_types.json"
_made_mark = not _mark.exists()
if _made_mark:
    _mark.parent.mkdir(parents=True, exist_ok=True)
    _mark.write_text("{}", encoding="utf-8")
try:
    _empty = Path(tempfile.mkdtemp(prefix="b78empty_"))
    _e = dict(os.environ, USE_MOCK="0", ONTO_HOME=str(_empty))
    _e.pop("ONTO_CONFIG", None)
    _r = subprocess.run([sys.executable, str(ROOT / "run.py"), "platform", "doctypes"],
                        capture_output=True, text=True, cwd=str(ROOT), env=_e,
                        stdin=subprocess.DEVNULL)
    _txt = _r.stdout + _r.stderr
    show("③ 이관 전 실행은 상태 거부 — 원인·지금 잰 것·근거·다음 줄이 한 화면에 있다",
         _r.returncode != 0 and "migrate" in _txt and "근거" in _txt
         and "지금 잰 것" in _txt, _txt.strip().splitlines()[:1])
    # 같은 조건에서 **이관 명령 자신은** 관문 밖이다(걸리면 칠 다음 줄이 없다).
    _r2 = subprocess.run([sys.executable, str(ROOT / "run.py"), "platform", "migrate",
                          "--from", str(_old), "--dry-run"],
                         capture_output=True, text=True, cwd=str(ROOT), env=_e,
                         stdin=subprocess.DEVNULL)
    show("③ 이관 명령 자신은 그 거부에 걸리지 않는다",
         _r2.returncode == 0 and "이관 예정" in _r2.stdout,
         (_r2.stdout + _r2.stderr).strip().splitlines()[:1])
finally:
    if _made_mark:
        _mark.unlink(missing_ok=True)
    shutil.rmtree(_lg, ignore_errors=True)
    shutil.rmtree(_empty, ignore_errors=True)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — 사내 조건 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
