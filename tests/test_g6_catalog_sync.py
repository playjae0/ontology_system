# -*- coding: utf-8 -*-
"""G6 ⑫ 층 공통 config를 bootstrap이 층 config에서 맞춘다 (B92 · 칸 0.1).

층(창작 · 테스트 전용)을 상태 루트에 더하고 지우며 `bootstrap`(subprocess — 사람이 치는 길)을
돌린다. 레포 `layers/`는 건드리지 않는다. 수치는 근거가 아니다([정정] 50).

잠그는 성질:
  ⓐ 한 층만 선언한 새 카테고리는 자동 추가(집 = 그 층) · 판 +1 · 로그에 근거
  ⓑ 여러 층이 함께 선언한 새 카테고리는 집 빈칸 + 멈춤
  ⓒ 층에서 지운 카테고리 — 노드 0이면 자동 제거 · 노드가 있으면 멈춤
  ⓓ 이미 있는 항목의 home·also는 맞추기 뒤에도 같다
  ⓔ 노드가 있는 카테고리의 home을 바꾸면 멈춘다(옛 집 = 노드가 있는 그래프)
  ⓕ `--dry-run`은 공통 config·그래프 쓰기 0
  ⓖ 운영 처음(파일 없음) — common.json을 바로 만든다 · 빈칸이면 멈춘다 · 초안 파일 0
  B93 골격 카테고리의 집은 골격 층(겹쳐 선언해도 자동 · 빈칸은 채움 · --dry-run 쓰기 0) ·
      두 층 골격이 같은 카테고리 / 채운 집 ≠ 골격 층은 첫 실행에서 멈춤(그래프 쓰기 0) ·
      겸 상태 세 갈래 표시(종료 코드 0 · doctor 같은 상태)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done    # noqa: F401
from core.state import catalog     # noqa: E402

NEW = "b92eq"                      # 테스트 전용 층 이름(창작)


def _boot(*args, env=None):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap", *args], cwd=str(ROOT),
                       env=env or {**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def _common():
    return json.loads(_P.common().read_text(encoding="utf-8"))


def _new_layer(cats):
    d = _P.layers(NEW)
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(
        {"layer": NEW, "categories": cats, "relations": [], "relation_patterns": [],
         "config_version": f"{NEW}-1"}, ensure_ascii=False), encoding="utf-8")


def _drop_layer():
    shutil.rmtree(_P.layers(NEW), ignore_errors=True)


def _logs():
    return "".join(p.read_text(encoding="utf-8") for p in sorted(_P.work("logs").glob("bootstrap_*.log"))) \
        if _P.work("logs").exists() else ""


print("\n■ B92 ① 카탈로그 맞추기 — bootstrap 입구")
init.init(fresh_=True)
_c0 = _common()
_rw(_P.common(), lambda c: c["categories"]["Process"].update(also={"Unit": ["sub"]}))   # 사람 값
_c0 = _common()
_new_layer({"Gear": "기어(창작)"})
_l0 = len(_logs())
_rc, _o = _boot()
_c1 = _common()
show("ⓐ 한 층만 선언한 새 카테고리는 자동 추가 — 집 = 그 층 · 판 +1 · 로그에 근거",
     _rc == 0 and _c1["categories"].get("Gear") == {"home": NEW}
     and _c1["common_version"] == _c0["common_version"] + 1
     and "Gear" in _logs()[_l0:] and f"+ 'Gear' (home {NEW}" in _o,
     [l for l in _o.splitlines() if "공통 config +" in l][:1])
show("ⓓ 이미 있는 항목의 home·also는 맞추기 뒤에도 같다",
     all(_c1["categories"][k] == v for k, v in _c0["categories"].items()),
     str(_c1["categories"]["Process"]))

_new_layer({"Gear": "기어", "Tool": "공구(창작)"})
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Tool="공구"))
_rc, _o = _boot()
show("ⓑ 여러 층이 함께 선언한 새 카테고리는 집 빈칸 + 멈춤(사람이 고른다)",
     _rc != 0 and _common()["categories"].get("Tool") == {"home": ""}
     and "여러 층이 선언" in _o and "[상태]" in _o,
     [l for l in _o.splitlines() if "Tool" in l][:1])

_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].pop("Tool"))
_new_layer({"Tool": "공구"})                      # Gear를 층에서 지웠다 · Tool은 한 층만
_rw(_P.common(), lambda c: c["categories"]["Tool"].update(home=NEW))   # 사람이 빈칸을 채웠다
_rc, _o = _boot()
_c2 = _common()
_drop_layer()
_rc_t, _ = _boot()                                 # 층째 지우면 Tool도 노드 0 → 제거
show("ⓒ 층에서 지운 카테고리는 노드 0이면 자동 제거(층째 지워도 같다)",
     _rc == 0 and "Gear" not in _c2["categories"] and "− 'Gear'" in _o
     and _rc_t == 0 and "Tool" not in _common()["categories"],
     [l for l in _o.splitlines() if "공통 config" in l][:2])

run_document(load("CP01"))                         # process 그래프에 Property·Unit 노드
_rw(_P.layers("process", "config.json"), lambda c: c["categories"].pop("Property"))
_before = _P.common().read_bytes()
_rc, _o = _boot()
show("ⓒ 노드가 남은 카테고리를 층에서 지우면 멈춘다 — 지우지 않는다",
     _rc != 0 and "Property" in _common()["categories"] and "노드" in _o and "재빌드" in _o,
     [l for l in _o.splitlines() if "Property" in l][:1])
init.init(fresh_=True)

print("\n■ B92 ② 노드가 있는 카테고리의 집 변경을 막는다")
_boot()                                            # 골격이 서야 문서가 노드를 만든다
run_document(load("CP01"))                         # Unit 노드가 process 그래프에
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Unit="설비"))
_rw(_P.common(), lambda c: c["categories"]["Unit"].update(home="quality"))
_rc, _o = _boot()
show("ⓔ 노드가 있는 카테고리의 home을 바꾸면 멈춘다 — 옛 집은 노드가 있는 그래프",
     _rc != 0 and "process → quality" in _o and "재빌드" in _o,
     [l for l in _o.splitlines() if "home을" in l][:1])
init.init(fresh_=True)

_new_layer({"Gear": "기어"})
_cb, _files = _P.common().read_bytes(), sorted(p.name for p in _P.data().rglob("*") if p.is_file())
_rc, _o = _boot("--dry-run")
show("ⓕ --dry-run은 계획만 보인다 — 공통 config·그래프 쓰기 0",
     _rc == 0 and "+ 'Gear'" in _o and "--dry-run" in _o and _P.common().read_bytes() == _cb
     and sorted(p.name for p in _P.data().rglob("*") if p.is_file()) == _files,
     _o.strip().splitlines()[-1][:80])
_drop_layer()
init.init(fresh_=True)

with tempfile.TemporaryDirectory(prefix="b92_") as _td:
    _r = Path(_td)
    shutil.copytree(ROOT / "layers" / "process", _r / "layers" / "process")
    shutil.copytree(ROOT / "layers" / "quality", _r / "layers" / "quality")
    _rw(_r / "layers" / "quality" / "config.json", lambda c: c["categories"].update(Unit="설비"))
    (_r / "registry").mkdir()
    (_r / "registry" / "doc_types.json").write_text("{}", encoding="utf-8")
    _env = {**os.environ, "USE_MOCK": "0", "ONTO_HOME": str(_r)}
    _rc1, _o1 = _boot(env=_env)
    _cj = _r / "layers" / "common.json"
    _d = json.loads(_cj.read_text(encoding="utf-8")) if _cj.exists() else {}
    _rw(_cj, lambda c: c["categories"]["Unit"].update(home="process"))
    _rc2, _o2 = _boot(env=_env)
    show("ⓖ 운영 처음 — common.json을 바로 만든다(한 층 → 그 층 · 겹침 → 빈칸 + 멈춤) · 초안 파일 0 · 채우면 선다",
         _rc1 != 0 and _d.get("categories", {}).get("Unit") == {"home": ""}
         and _d["categories"]["Process"] == {"home": "process"}
         and not (_r / "layers" / "common.draft.json").exists() and _rc2 == 0,
         _o1.strip().splitlines()[0][:90] if _o1.strip() else "")

# ────────────────────────────────────────────────────────────── B93
print("\n■ B93 ① 골격 카테고리의 집은 골격 층 — 자동")
init.init(fresh_=True)
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Process="공정(렌즈)"))
_rw(_P.common(), lambda c: c["categories"].pop("Process"))
_rc, _o = _boot()
show("ⓐ 두 층이 골격 카테고리를 함께 선언해도 집 = 골격 층 자동(빈칸·멈춤 0)",
     _rc == 0 and _common()["categories"].get("Process") == {"home": "process"}
     and "골격이 process에 있다" in _o and "빈칸" not in _o,
     [l for l in _o.splitlines() if "'Process'" in l][:1])
_rw(_P.common(), lambda c: c["categories"]["Process"].update(home=""))
_cb, _v0 = _P.common().read_bytes(), _common()["common_version"]
_rcd, _od = _boot("--dry-run")
_same = _P.common().read_bytes() == _cb
_l0 = len(_logs())
_rc, _o = _boot()
show("ⓑ 기존 빈칸은 골격 층으로 채운다 · 판 +1 · 로그 (ⓖ --dry-run은 같은 계획 · 쓰기 0)",
     _rc == 0 and _common()["categories"]["Process"]["home"] == "process"
     and _common()["common_version"] == _v0 + 1 and "빈칸 → process" in _logs()[_l0:]
     and _rcd == 0 and _same and "빈칸 → process" in _od,
     [l for l in _o.splitlines() if "빈칸" in l][:1])

print("\n■ B93 ② 골격 모순 거부 — 심기 전에")
init.init(fresh_=True)
_rw(_P.layers("quality", "config.json"), lambda c: c["skeleton"].update(category="Process")
    or c["categories"].update(Process="공정(렌즈)"))
_rc, _o = _boot()
show("ⓒ 두 층의 골격이 같은 카테고리면 멈춘다",
     _rc != 0 and "함께 가진다" in _o and "두 벌" in _o,
     [l for l in _o.splitlines() if "함께 가진다" in l][:1])
init.init(fresh_=True)
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Process="공정(렌즈)"))
_rw(_P.common(), lambda c: c["categories"]["Process"].update(home="quality"))
_rc, _o = _boot()
_pn = sum(1 for n in open_graph("process").nodes.values() if n.get("category") == "Process") \
    + sum(1 for n in open_graph("quality").nodes.values() if n.get("category") == "Process")
show("ⓓ 채운 home ≠ 골격 층이면 **첫 실행에서** 멈춘다 — 그래프 쓰기 0 · 문면이 원인(골격 층)을 말한다",
     _rc != 0 and "골격은 process에 있다" in _o and "바꿨지만" not in _o and _pn == 0,
     [l for l in _o.splitlines() if "골격은" in l][:1])
init.init(fresh_=True)

print("\n■ B93 ③ 겸 상태 — 표시일 뿐(종료 코드 0)")
_rc_off, _o_off = _boot()
_rw(_P.common(), lambda c: c["categories"]["Process"].update(also={"Unit": ["sub", "detail"]})
    or c["categories"]["FailureEffect"].update(also={"Failure": ["main"]}))
_rc_on, _o_on = _boot()
_dq = subprocess.run([sys.executable, str(ROOT / "doctor.py"), "--quick"], cwd=str(ROOT),
                     capture_output=True, text=True, env={**os.environ, "USE_MOCK": "1"},
                     stdin=subprocess.DEVNULL).stdout
show("ⓕ 겸 상태 세 갈래 — 꺼짐(겸 없음) · 켜짐(겸 + 겸 단 별칭) · 반쪽(⚠ 별칭 0) · 종료 코드 0 · doctor 같은 상태",
     _rc_off == 0 and "골격 'Process'(process): 겸 없음" in _o_off
     and _rc_on == 0 and "골격 'Process'(process): 겸 Unit(sub·detail) · 겸 단 별칭" in _o_on
     and "⚠ 골격 'FailureEffect'(quality)" in _o_on and "별칭 0" in _o_on
     and "겸 Unit(sub·detail) · 겸 단 별칭" in _dq and "별칭 0" in _dq,
     [l for l in _o_on.splitlines() if "골격 '" in l][:2])
init.init(fresh_=True)

done()
