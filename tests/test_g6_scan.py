# -*- coding: utf-8 -*-
"""G6 ② 지문 스캔 — 후보 제안과 확정 전 미실행(S11) · mock 격리(픽스처를 들어내도 돈다)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ S11 — n9 지문 스캔 (파서_명세 §5 · 카드 C15 · P7)")
calls = []
_orig_load = SC._load


def _spy(path):
    mod = _orig_load(path)
    if hasattr(mod, "extract"):
        orig_ex = mod.extract

        def ex(*a, **k):
            calls.append(str(path))
            return orig_ex(*a, **k)
        mod.extract = ex
    return mod


SC._load = _spy
before = data_hash()
res = SC.scan(ROOT / "tests" / "fixtures" / "raw" / "CP04_unlabeled.xlsx")
cp = next(d for d in res["details"] if d["doc_type"] == "cp")
show("후보 'cp' 제안 — 유일 일치", res["candidates"] == ["cp"], str(res["candidates"]))
# **수를 박지 않는다**(B77 ① 재조준) — 성질은 「선언한 것 전부가 맞았고 남는 것이
# 없다」다. 10을 박아 두면 그 문서가 열 하나를 얻는 날 이 줄이 결함처럼 붉는다.
show("일치 내역 포함 — 선언분 전량 일치 · 누락 0 · 잉여 0",
     cp["matched"] == cp["declared"] > 0 and not cp["missing"] and not cp["extra"],
     f"{cp['matched']}/{cp['declared']}")
show("타 어댑터의 불일치 내역도 함께 제시된다 (일괄 대조)",
     any(d["doc_type"] == "ipqc" and d["eligible"] and not d["candidate"]
         for d in res["details"]))
show("비정형(prose) 어댑터는 대조 대상 아님 — 지정 필수",
     any(d["doc_type"] == "toc_report" and not d["eligible"] for d in res["details"]))
show("**확정 입력 전 파싱 미실행** — 유일 일치여도 자동 라우팅하지 않는다 (P7)",
     not calls, str(calls))

res2, pieces = SC.confirm(ROOT / "tests" / "fixtures" / "raw" / "CP04_unlabeled.xlsx", "cp")
show("확정 후 정상 파싱 — 10행 → 12 record (복수값 전개 2건)",
     len(pieces) == 12 and len(calls) == 1,
     f"{len(pieces)} record · 전개 {sum(1 for p in pieces if '#' in p['source_locator'])}행")
show("정규화 실증 — 병합 전개(공정구분)·상동 해소(설비)·복수값 분리(관리항목)",
     all(p["process_group"] == "조립" for p in pieces)
     and any(p["source_locator"].endswith("R5") and p["설비"] == "주액기" for p in pieces)
     and {"주액량", "주액 속도"} <= {p["관리항목"] for p in pieces})
show("스캔·확정이 data/를 건드리지 않는다 (편의 기능 — 그래프·큐 쓰기 0)",
     before == data_hash())

drift = SC.scan(ROOT / "tests" / "fixtures" / "raw" / "CP02_drift.xlsx")
dcp = next(d for d in drift["details"] if d["doc_type"] == "cp")
show("표류 1열 검출 — CP02_drift는 후보가 아니다 (관리항목 → 관리 항목명)",
     not drift["candidates"] and dcp["missing"] == ["관리항목"]
     and dcp["extra"] == ["관리 항목명"], f"누락 {dcp['missing']} · 잉여 {dcp['extra']}")
try:
    SC.confirm(ROOT / "tests" / "fixtures" / "raw" / "CP02_drift.xlsx", "cp")
    show("지문 불일치 확정은 거부된다 (preflight 재사용 — C15)", False)
except SystemExit as e:
    show("지문 불일치 확정은 거부된다 (preflight 재사용 — C15)", "불일치" in str(e))
SC._load = _orig_load

# ============================================================ mock 격리
print("\n■ mock 격리 — 픽스처를 들어내도 본체가 도는가 (§2-4)")
# **mock은 걷어낼 대상이 아니라 격리할 대상이다.** 물리적으로 지웠을 때 gauges·scan이
# 죽고 회귀가 붕괴한 것이 실측이고, 원인은 본체가 mock 경로를 **무조건 상수**로
# 알고 있다는 것이었다 — 분기 안에 있는 참조가 0건이었다.
import shutil as _sh2, subprocess as _sp3                       # noqa: E402
from core.state import fixtures as _FX                                # noqa: E402

_src = (ROOT / "core").rglob("*.py")
_hard = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "parser", "cli")
         for p in sorted((ROOT / d).glob("*.py"))
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         # **경로 상수만** 센다 — `image_summary_source == "mock"` 같은 **값**은
         # 격리 대상이 아니다(그것은 어느 갈래가 만들었나의 표시다).
         if ('/ "mock"' in ln or '"mock/' in ln) and not ln.lstrip().startswith("#")]
show("본체(core·parser·cli)에 mock 경로 상수 0지점", not _hard, str(_hard))
show("픽스처 소재가 core/state/fixtures.py 한 곳으로 수렴한다",
     hasattr(_FX, "PARSED") and hasattr(_FX, "QUERIES") and hasattr(_FX, "dirs"))

_away = ROOT / "_fixtures_away"
_sh2.move(str(_FX.ROOT_DIR), str(_away))
try:
    def _r(*a):
        return _sp3.run([sys.executable, str(ROOT / "run.py"), *a],
                        capture_output=True, text=True, cwd=str(ROOT))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
             capture_output=True, cwd=str(ROOT))
    _b = _r("bootstrap")
    show("픽스처 없이 bootstrap 정상", _b.returncode == 0)
    _a = _r("all")
    show("픽스처 없이 all — **조용한 무동작이 아니라 말하고 끝난다**",
         _a.returncode == 0 and "인입할 계약 JSON이 없다" in _a.stdout)
    _g = _r("gauges")
    show("픽스처 없이 gauges 정상 (queries.json 무가드 read가 죽던 자리)",
         _g.returncode == 0 and "저장 크기" in _g.stdout,
         (_g.stderr or "").strip().splitlines()[-1:] and
         (_g.stderr or "").strip().splitlines()[-1] or "")
    _s = _r("scan", str(_away / "raw" / "CP04_unlabeled.xlsx"))
    show("픽스처 없이 scan 정상 (없는 디렉터리를 모듈 로드하다 죽던 자리)",
         _s.returncode == 0)
finally:
    _sh2.move(str(_away), str(_FX.ROOT_DIR))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
             capture_output=True, cwd=str(ROOT))
    _sp3.run([sys.executable, str(ROOT / "run.py"), "all"],
             capture_output=True, cwd=str(ROOT))

# ============================================================ B46 일괄 투입

done()
