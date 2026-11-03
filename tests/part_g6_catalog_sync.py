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
  B95 골격 카테고리의 어긋난 집은 옛 집 그래프에 노드 0이면 자동 교정(있으면 노드 수 문면으로 멈춤) ·
      새 카테고리 경고에 이름 규칙 줄(적용·미적용)
  B173 config 지도(읽기만) — ⓐ 층 사이 연결 포인트 · 선언 없이 씀 ⓑ 점검은 카탈로그 · 재대조 문면 그대로 + 새 점검 줄
      ⓒ `--json` 두 번 바이트 같음 · 관계 패턴 하나를 지운 사본과의 대조가 그 하나만 ⓓ HTML 실경로 외부 주소 0 · 쓰기 0
  B174 옛 모양 → 제안 — ⓑ 옛 mock config → 제안 · 보고 · 멈춤(쓰기 0) · 지도 지금 ↔ 제안 대조 0 ⓒ (일반 노드) 아래 (경로 씀) 쌍
      → 보고의 이름이 바뀌는 카테고리 · 앞뒤 이름 꼴 ⓓ 옛 목록 밖 → 「안 씀 + 사유」 · 사유 없는 「안 씀」은 지도의 누락
      ⓕ 지도의 카테고리마다 이름 꼴 · 층끼리 같은 쌍 다른 관계는 제안 없이 멈춤
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
init.init(fresh_=True, all_=True)
_c0 = _common()
_rw(_P.common(), lambda c: c["categories"]["Process"].update(also={"Unit": ["sub"]}))   # 사람 값
_c0 = _common()
_new_layer({"Gear": "기어(창작)"})
_l0 = len(_logs())
_rc, _o = _boot()
_c1 = _common()
show("ⓐ 한 층만 선언한 새 카테고리는 자동 추가 — 집 = 그 층 · 판 +1 · 로그에 근거",
     _rc == 0 and _c1["categories"].get("Gear", {}).get("home") == NEW
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
     _rc != 0 and _common()["categories"].get("Tool", {}).get("home") == ""
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

# 기대 변경(B106 ①): 멈춤의 다음 줄 「재빌드」 → 「재구축(python run.py rebuild)」 — 아래 셋이 같은 줄을 본다
run_document(load("CP01"))                         # process 그래프에 Property·Unit 노드
_rw(_P.layers("process", "config.json"), lambda c: c["categories"].pop("Property"))
_before = _P.common().read_bytes()
_rc, _o = _boot()
show("ⓒ 노드가 남은 카테고리를 층에서 지우면 멈춘다 — 지우지 않는다",
     _rc != 0 and "Property" in _common()["categories"] and "노드" in _o and "재구축" in _o and "rebuild" in _o,
     [l for l in _o.splitlines() if "Property" in l][:1])
init.init(fresh_=True, all_=True)

print("\n■ B92 ② 노드가 있는 카테고리의 집 변경을 막는다")
_boot()                                            # 골격이 서야 문서가 노드를 만든다
run_document(load("CP01"))                         # Unit 노드가 process 그래프에
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Unit="설비"))
_rw(_P.layers("process", "config.json"), lambda c: (c["categories"].pop("Unit"), c.setdefault("uses", []).append("Unit")))   # 고침(B174 — 겹친 정의 0)
_rw(_P.common(), lambda c: c["categories"]["Unit"].update(home="quality"))
_rc, _o = _boot()
show("ⓔ 노드가 있는 카테고리의 home을 바꾸면 멈춘다 — 옛 집은 노드가 있는 그래프",
     _rc != 0 and "process → quality" in _o and "재구축" in _o and "rebuild" in _o,
     [l for l in _o.splitlines() if "home을" in l][:1])
init.init(fresh_=True, all_=True)

_new_layer({"Gear": "기어"})
_cb, _files = _P.common().read_bytes(), sorted(p.name for p in _P.data().rglob("*") if p.is_file())
_rc, _o = _boot("--dry-run")
show("ⓕ --dry-run은 계획만 보인다 — 공통 config·그래프 쓰기 0",
     _rc == 0 and "+ 'Gear'" in _o and "--dry-run" in _o and _P.common().read_bytes() == _cb
     and sorted(p.name for p in _P.data().rglob("*") if p.is_file()) == _files,
     _o.strip().splitlines()[-1][:80])
_drop_layer()
init.init(fresh_=True, all_=True)

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
    show("ⓖ 운영 처음 — common.json을 바로 만든다(한 층 → 그 층 · 겹침 → 빈칸 + 멈춤) · 초안 파일 0 · 채우면 다음은 옛 모양 제안"
         "(고침 B174 — 겹친 정의는 uses로 옮긴다 · 옛: 선다)",
         _rc1 != 0 and _d.get("categories", {}).get("Unit", {}).get("home") == ""
         and _d["categories"]["Process"]["home"] == "process"
         and not (_r / "layers" / "common.draft.json").exists() and _rc2 != 0 and "옛 모양" in _o2,
         _o1.strip().splitlines()[0][:90] if _o1.strip() else "")

# ────────────────────────────────────────────────────────────── B93
print("\n■ B93 ① 골격 카테고리의 집은 골격 층 — 자동")
init.init(fresh_=True, all_=True)
_rw(_P.common(), lambda c: c["categories"].pop("Process"))     # 고침(B174 — 품질층은 Process를 uses로 쓴다 · 겹친 정의 0)
_rc, _o = _boot()
show("ⓐ 다른 층이 골격 카테고리를 써도(uses) 집 = 골격 층 자동(빈칸·멈춤 0)",
     _rc == 0 and _common()["categories"].get("Process", {}).get("home") == "process"
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
init.init(fresh_=True, all_=True)
_rw(_P.layers("quality", "config.json"), lambda c: c["skeleton"].update(category="Process")
    or c["categories"].update(Process="공정(렌즈)"))
_rw(_P.common(), lambda c: c["categories"].pop("Process"))     # 고침(B174 — 집이 정해진 겹친 정의는 옛 모양 관문이 먼저 멈춘다)
_rc, _o = _boot()
show("ⓒ 두 층의 골격이 같은 카테고리면 멈춘다",
     _rc != 0 and "함께 가진다" in _o and "두 벌" in _o,
     [l for l in _o.splitlines() if "함께 가진다" in l][:1])
# **채운 집 ≠ 골격 층**(B93 ⓓ → B95 ①) — 사내 첫 적용 모양: 골격을 다른 층 폴더로 옮겼는데 공통
# config는 옛 집을 가리킨다. 옛 집 그래프에 노드가 0이면 자동 교정 · 있으면 멈춘다(기대 변경 · B95).
EQ = "b95eq"


def _move_skeleton():
    """골격을 새 층 `b95eq`로 옮긴다(창작) — 공정층 config는 골격 선언을 잃는다."""
    shutil.copytree(_P.layers("process"), _P.layers(EQ))
    _rw(_P.layers(EQ, "config.json"), lambda c: c.update(layer=EQ, relation_patterns=[], uses=[], value_categories={},
                                                         categories={"Process": c["categories"]["Process"]}))
    def _p(c):                                     # 고침(B174 — 겹친 정의 0 · 공정층은 골격 카테고리를 uses로)
        c.pop("skeleton")
        c["categories"].pop("Process")
        c.setdefault("uses", []).append("Process")
    _rw(_P.layers("process", "config.json"), _p)


print("\n■ B95 ① 골격 카테고리의 어긋난 집 — 노드 0이면 자동 교정")
init.init(fresh_=True, all_=True)
_move_skeleton()
_v0, _l0 = _common()["common_version"], len(_logs())
_rcd, _od = _boot("--dry-run")
_dry_same = _common()["common_version"] == _v0
_rc, _o = _boot()
show("ⓐ 채운 집 ≠ 골격 층 · 옛 집 그래프에 노드 0 → 자동 교정 · 판 +1 · 로그 · 종료 코드 0 (ⓒ --dry-run은 계획만)",
     _rc == 0 and _common()["categories"]["Process"]["home"] == EQ
     and _common()["common_version"] == _v0 + 1 and f"home process → {EQ}" in _o
     and f"Process home process → {EQ}" in _logs()[_l0:]
     and _rcd == 0 and _dry_same and f"home process → {EQ}" in _od,
     [l for l in _o.splitlines() if "→" in l and "home" in l][:1])
shutil.rmtree(_P.layers(EQ), ignore_errors=True)
init.init(fresh_=True, all_=True)
_boot()                                            # 골격 노드가 process 그래프에 심긴다
_move_skeleton()
_rc, _o = _boot()
_eq_nodes = len(open_graph(EQ).nodes)
show("ⓑ 옛 집 그래프에 그 카테고리 노드가 있으면 멈춘다 — 노드 수 문면 · 그래프 쓰기 0",
     _rc != 0 and "골격은 b95eq에 있다" in _o and "노드" in _o and "재구축" in _o and "rebuild" in _o
     and _common()["categories"]["Process"]["home"] == "process" and _eq_nodes == 0,
     [l for l in _o.splitlines() if "골격은" in l][:1])
shutil.rmtree(_P.layers(EQ), ignore_errors=True)
init.init(fresh_=True, all_=True)

print("\n■ B93 ③ 겸 상태 — 표시일 뿐(종료 코드 0)")
_rc_off, _o_off = _boot()
_rw(_P.common(), lambda c: c["categories"]["Process"].update(also={"Unit": ["sub", "detail"]})
    or c["categories"]["FailureEffect"].update(also={"Failure": ["main"]}))
_rc_on, _o_on = _boot()
# doctor 머리 줄 = doctor가 하위 실행으로 그리는 화면 그 함수(`cli.doctor_view head`) — doctor 전체를 돌리지 않는다(B121 ②ⓓ)
_dq = subprocess.run([sys.executable, "-m", "cli.doctor_view", "head"], cwd=str(ROOT),
                     capture_output=True, text=True, env={**os.environ, "USE_MOCK": "1"},
                     stdin=subprocess.DEVNULL).stdout
show("ⓕ 겸 상태 세 갈래 — 꺼짐(겸 없음) · 켜짐(겸 + 겸 단 별칭) · 반쪽(⚠ 별칭 0) · 종료 코드 0 · doctor 같은 상태",
     _rc_off == 0 and "골격 'Process'(process): 겸 없음" in _o_off
     and _rc_on == 0 and "골격 'Process'(process): 겸 Unit(sub·detail) · 겸 단 별칭" in _o_on
     and "⚠ 골격 'FailureEffect'(quality)" in _o_on and "별칭 0" in _o_on
     and "겸 Unit(sub·detail) · 겸 단 별칭" in _dq and "별칭 0" in _dq,
     [l for l in _o_on.splitlines() if "골격 '" in l][:2])
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── B94
print("\n■ B94 ① 쓰는 층(used_by) — 결과 기록 · 사람이 관리하지 않는다")
from core.build import ledger as _LG       # noqa: E402
from core.build import extract as _EX      # noqa: E402
init.init(fresh_=True, all_=True)
_decl0 = catalog.used_by()                                     # 고침(B174 — 집 정의 ∪ uses)
_ub0 = {c: v.get("used_by") for c, v in _common()["categories"].items()}
_rw(_P.layers("quality", "config.json"), lambda c: c["uses"].remove("Property"))
_v0, _l0 = _common()["common_version"], len(_logs())
_rc, _o = _boot()
_ub1 = _common()["categories"]["Property"].get("used_by")
_rw(_P.layers("quality", "config.json"), lambda c: c["uses"].append("Property"))
_rc2, _o2 = _boot()
show("ⓐ used_by = 층 config의 집 정의 ∪ uses(처음 · 추가/삭제마다) · 판 +1 · 로그(고침 B174 — 옛: 선언만)",
     all(_ub0[c] == _decl0[c] for c in _decl0)
     and _rc == 0 and _ub1 == ["process"] and _common()["common_version"] >= _v0 + 2
     and _common()["categories"]["Property"]["used_by"] == ["process", "quality"]
     and "used_by 'Property' − quality" in _o and "used_by 'Property' + quality" in _o2
     and "used_by 'Property'" in _logs()[_l0:],
     [l for l in _o.splitlines() if "used_by" in l][:1])
_rw(_P.common(), lambda c: c["categories"]["Failure"].update(used_by=["process", "엉뚱한층"])
    or c["categories"]["Unit"].update(used_by=[]))
_rc, _o = _boot()
show("ⓑ 손으로 고친 used_by는 다음 bootstrap이 층 config 값으로 되돌린다(로그)",
     _rc == 0 and _common()["categories"]["Failure"]["used_by"] == ["quality"]
     and _common()["categories"]["Unit"]["used_by"] == ["process"] and "층 config에서 온다" in _o,
     [l for l in _o.splitlines() if "used_by" in l][:2])
_cur = _common()
_cur["categories"]["Failure"]["used_by"] = ["process"]          # 틀린 기록
_cur["categories"]["Tool"] = {"home": "quality", "used_by": ["quality", "process"]}  # 선언 0 · 노드 0
from core.state import catalog_sync as _CS    # noqa: E402
_pl = _CS.plan(current=_cur)
_pl_ok = _CS.plan(current={**_cur, "categories": {k: dict(v, used_by=_decl0.get(k, []))
                                                  for k, v in _cur["categories"].items()}})
show("ⓒ 판정은 used_by를 읽지 않는다 — 틀린 used_by여도 집·제거·멈춤 결과가 같다",
     _pl["drop"] == _pl_ok["drop"] == ["Tool"] and _pl["ask"] == _pl_ok["ask"] == []
     and {c: v["home"] for c, v in _pl["catalog"]["categories"].items()}
     == {c: v["home"] for c, v in _pl_ok["catalog"]["categories"].items()},
     str(_pl["drop"]))

print("\n■ B94 ② 새 카테고리 경고 — 기존 카탈로그를 보인다(표시)")
_new_layer({"DefectHistory": "이슈 이력의 결함(창작)"})
_rcd, _od = _boot("--dry-run")
_rc, _o = _boot()
show("ⓓ 새 카테고리를 더할 때 기존 카탈로그(home · used_by · 정의문 앞부분)가 나온다 · 종료 코드 불변",
     _rc == 0 and _rcd == 0 and "새 카테고리 'DefectHistory'" in _o and "같은 뜻의 기존 카테고리" in _o
     and "'Failure' home quality · used_by ['quality']" in _o and "새 카테고리 'DefectHistory'" in _od,
     [l.strip()[:70] for l in _o.splitlines() if "'Failure' home" in l][:1])
_drop_layer()
init.init(fresh_=True, all_=True)

print("\n■ B95 ② 새 카테고리 경고에 이름 규칙 한 줄 — 표시")
init.init(fresh_=True, all_=True)
_boot()
_new_layer({"Component": "구성 부품(창작)", "DefectHistory": "이슈 이력의 결함(창작)"})
_rcd, _od = _boot("--dry-run")
_rc, _o = _boot()
show("ⓓ 새 카테고리 경고에 이름 규칙 줄 — 경로 씀(기본 · no_path 없음) · 「노드가 생기기 전에」 · 종료 코드 불변 · dry-run 같다"
     "(고침 B174 — 목록이 아니라 기본 씀)",
     _rc == 0 and _rcd == 0
     and "이름 규칙: 'Component'는 경로 씀" in _o and "이름 규칙: 'DefectHistory'는 경로 씀" in _o
     and "노드가 생기기 전에 정한다" in _o and "공정을 모르면" not in _o
     and "이름 규칙: 'DefectHistory'는 경로 씀" in _od,
     [l.strip()[:60] for l in _o.splitlines() if "이름 규칙" in l][:2])
_drop_layer()
init.init(fresh_=True, all_=True)

print("\n■ B94 ③ 골격 카테고리 개체는 조회 전용")
_boot()
_real = _EX._candidates_for


def _stub94(cid, chunk, cfg, vocab):
    return {"chunk_id": cid, "relations": [], "attach": [], "entities": [
        {"surface": "골격에없는공정", "category": "Process"},
        {"surface": "NC", "category": "Process"},                 # 골격 별칭(노칭)
        {"surface": "새 관리 인자", "category": "Property"}]}


_EX._candidates_for = _stub94
try:
    _pg0 = {n["canonical"] for n in open_graph("process").nodes.values()}
    run_document(dict(PROSE, doc_type="ppt_process", doc_id="X94", chunks=[
        dict(C1, source_locator="X94-C001", text="골격에없는공정과 NC와 새 관리 인자.")]))
finally:
    _EX._candidates_for = _real
_pg = open_graph("process")
_new = {n["canonical"] for n in _pg.nodes.values()} - _pg0
_q94 = [x for x in store.read(store.QUEUE, []) if x["doc_id"] == "X94" and x["kind"] == "orphan_anchor"]
_rows = (_LG.read("X94") or {}).get("rows") or []
show("ⓔ 골격 카테고리로 뽑힌 골격 밖 이름 → 노드 0 · 큐 orphan_anchor +1 · 대장 행(orphan)",
     not any("골격에없는공정" in c for c in _new) and len(_q94) == 1
     and any(r.get("surface") == "골격에없는공정" and r.get("verdict") == "orphan" for r in _rows),
     f"새 노드 {sorted(_new)} · 큐 {[x['payload'].get('key') for x in _q94]}")
_nc = [r for r in _rows if r.get("surface") == "NC"]
show("ⓕ 골격 별칭이면 매칭(노드 0) · 골격이 아닌 카테고리의 신규는 그대로",
     _nc and _nc[0].get("verdict") == "match" and (_pg.get(_nc[0]["node_id"]) or {}).get("canonical") == "노칭"
     and any(c.endswith("새 관리 인자") for c in _new) and len(_new) == 1,
     f"NC → {(_pg.get((_nc or [{}])[0].get('node_id')) or {}).get('canonical')} · 새 {sorted(_new)}")
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── B173
print("\n■ B173 config 지도 — 모델 · 점검 · JSON · 대조 · HTML (읽기만)")
import contextlib                                                          # noqa: E402
import hashlib                                                             # noqa: E402
import io                                                                  # noqa: E402
from cli import config_map as CM, export_config as XC                     # noqa: E402
from cli.register import recheck as _RC173                                 # noqa: E402
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _hash173():
    """그래프 · config · 등록부 — 읽기만의 증거(B173 ⓓ)."""
    h = _P.home()
    return {str(f.relative_to(h)): hashlib.sha256(f.read_bytes()).hexdigest()
            for sub in ("data", "layers", "registry") for f in sorted((h / sub).rglob("*")) if f.is_file()}


_h173 = _hash173()
_m173 = CM.build()
_cr173 = {(x["layer"], x["rel"], x["category"], x["home"]) for x in _m173["links"]["cross"] if x["from"] == "관계 패턴"}
_us173 = {(x["layer"], x["category"]) for x in _m173["links"]["uses"]}
show("B173 ⓐ 모델 — 품질층 → 공정층 연결 포인트 둘(관계 패턴 occurs_in → Process · controlled_by → Property) · "
     "Property는 「선언 없이 관계 패턴에서만 씀」",
     _cr173 == {("quality", "occurs_in", "Process", "process"), ("quality", "controlled_by", "Property", "process")}
     and ("quality", "Property") in _us173, f"걸침 {sorted(_cr173)} · 선언 없이 씀 {sorted(_us173)}")

_qc173 = _P.layers("quality", "config.json")
_q0173 = _qc173.read_bytes()
try:                                                                       # 사본 config — 층 이름 ≠ 폴더 · 없는 관계의 패턴
    _rw(_qc173, lambda c: (c.update(layer="b173다른이름"),
                           c["relation_patterns"].append(dict(c["relation_patterns"][0], rel="b173_없는_관계"))))
    _mb173 = CM.build()
    _cat173 = [ln for _t, ln in catalog.problems()]
    _rc173 = sorted(ln for _d, ok, ln in _RC173.run() if not ok)
finally:
    _qc173.write_bytes(_q0173)


def _got173(lv, frm):
    return [x["line"] for x in _mb173["checks"][lv] if x["from"].startswith(frm)]


show("B173 ⓑ 점검 — 카탈로그 거부 · 등록 스키마 재대조 줄이 그 함수의 문면 그대로 · 새 점검(패턴의 관계가 그 층 "
     "relations에 없다)이 사본 config에서 경고 한 줄",
     _cat173 and _got173("거부", "카탈로그") == _cat173
     and sorted(_got173("거부", "등록 스키마") + _got173("경고", "등록 스키마")) == _rc173
     and len([ln for ln in _got173("경고", "지도") if "b173_없는_관계" in ln]) == 1,
     f"카탈로그 {_cat173} · 새 점검 {_got173('경고', '지도')}")

_t173 = Path(tempfile.mkdtemp(prefix="b173_"))
with contextlib.redirect_stdout(io.StringIO()):
    XC.main(["--json", str(_t173 / "a.json")])
    XC.main(["--json", str(_t173 / "a2.json")])
_lay173, _p173 = next((lay, p) for lay, d in _m173["layers"].items() for p in d["patterns"]
                      if all(_m173["categories"][c]["home"] == lay for c in (p["src"], p["dst"])))
_c173 = _P.layers(_lay173, "config.json")
_c0173 = _c173.read_bytes()
try:                                                                       # 사본 config — 층 안 관계 패턴 하나를 지운다
    _rw(_c173, lambda c: c.update(relation_patterns=[x for x in c["relation_patterns"] if (x["src"], x["rel"], x["dst"])
                                                      != (_p173["src"], _p173["rel"], _p173["dst"])]))
    with contextlib.redirect_stdout(io.StringIO()):
        XC.main(["--json", str(_t173 / "b.json")])
finally:
    _c173.write_bytes(_c0173)
_d173 = XC.diff(json.loads((_t173 / "a.json").read_text(encoding="utf-8")),
                json.loads((_t173 / "b.json").read_text(encoding="utf-8")))
show("B173 ⓒ --json 두 번이 바이트 같다 · 관계 패턴 하나를 지운 사본과의 --diff가 그 하나만 낸다",
     (_t173 / "a.json").read_bytes() == (_t173 / "a2.json").read_bytes()
     and _d173 == [f"- 관계 패턴 — {_lay173}: {_p173['src']} -{_p173['rel']}-> {_p173['dst']}"
                   + (" (대칭)" if _p173["symmetric"] else "")], f"대조 {_d173}")

_r173 = subprocess.run([sys.executable, str(ROOT / "run.py"), "export", "config"], cwd=str(ROOT),
                       env={**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True, stdin=subprocess.DEVNULL)
_html173 = _P.export("config_map.html").read_text(encoding="utf-8") if _P.export("config_map.html").exists() else ""
show("B173 ⓓ export config(실경로) — HTML 한 장을 쓰고 읽는다 · 외부 주소 0 · 관계 그림은 지금 뷰어(걸침 엣지 표시) · "
     "그래프 · config · 등록부 바이트 그대로",
     _r173.returncode == 0 and "<iframe" in _html173 and "&quot;cross&quot;: true" in _html173
     and "http://" not in _html173 and "https://" not in _html173 and _hash173() == _h173,
     f"rc {_r173.returncode} · {_r173.stdout.strip().splitlines()[:1]} · {len(_html173):,}B")
shutil.rmtree(_t173, ignore_errors=True)
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── B174
print("\n■ B174 옛 모양 → 제안 · 보고 · 멈춤 · 지도 앞뒤 (옛 mock config 사본 — 창작)")
from cli import config_next as CN                                          # noqa: E402
OLD174 = ROOT / "tests" / "fixtures" / "config_b174_old"                  # B173 판 mock config 그대로(옛 모양 — seed 층 아님)


def _old174(edit=None):
    """클린 → 새 모양으로 골격 → 상태 루트 config만 옛 mock 사본으로(그 위에 `edit`)."""
    init.init(fresh_=True, all_=True)
    _boot()
    for f in ("common.json", "process/config.json", "quality/config.json"):
        shutil.copy(OLD174 / f, _P.layers(f))
    if edit:
        edit()


def _maps174():
    """지도 지금(상태 루트) · 제안(`work/config_next/layers`) JSON → `--diff` 줄."""
    nx = _P.config_next()
    with contextlib.redirect_stdout(io.StringIO()):
        XC.main(["--json", str(nx / "지금.json")])
        XC.main(["--from", str(nx / "layers"), "--json", str(nx / "제안.json")])
    return XC.diff(*(json.loads((nx / f).read_text(encoding="utf-8")) for f in ("지금.json", "제안.json")))


_old174()
_h174 = _hash173()
_rc, _o = _boot()
_w174 = _hash173() == _h174
_pc, _pl = CM.read(_P.config_next("layers"))
_d174 = _maps174()
show("B174 ⓑ 옛 모양 mock config → bootstrap이 제안(layers 모양) · 보고를 쓰고 멈춘다 · 그래프 · config · 등록부 쓰기 0 · "
     "제안은 새 모양 · 지도 지금 ↔ 제안 --diff 0",
     _rc != 0 and "옛 모양" in _o and _P.config_next("보고.md").exists() and _w174
     and not catalog.old_shape(_pl, _pc) and _d174 == [],
     f"rc {_rc} · 쓰기 0 {_w174} · 제안 옛 모양 {catalog.old_shape(_pl, _pc)} · 대조 {_d174[:3]}")


def _edit174():                                    # 사본 config — (일반 노드) 아래 (경로 씀) 쌍 · 옛 목록 밖 카테고리
    _rw(_P.layers("quality", "config.json"), lambda c: c.setdefault("category_pair_map", {}).update({"Failure,Unit": "occurs_in"}))
    _rw(_P.common(), lambda c: c["categories"].update(Tool={"home": "process"}))
    _rw(_P.layers("process", "config.json"), lambda c: c["categories"].update(Tool="공구(창작)"))


_old174(_edit174)
_rc, _o = _boot()
_rep = _P.config_next("보고.md").read_text(encoding="utf-8") if _P.config_next("보고.md").exists() else ""
_ren = _rep.split("## 이름이 바뀌는 카테고리", 1)[-1].split("\n## ", 1)[0]
_pc, _pl = CM.read(_P.config_next("layers"))
show("B174 ⓒ (일반 노드 카테고리) 아래 (경로 쓰는 카테고리) 쌍을 더한 옛 모양 → 보고 「이름이 바뀌는 카테고리」에 그 카테고리와 "
     "앞뒤 이름 꼴 · 위 · 아래는 같은 관계의 골격 끝 삼항과 같은 쪽",
     _rc != 0 and "`Failure` — 지금 `<공정>::<이름>` → 제안 `<공정>::<Unit>::<이름>" in _ren
     and {"lower": "Failure", "upper": "Unit", "rel": "occurs_in", "src": "lower"} in _pc.get("pairs", []),
     [ln for ln in _ren.splitlines() if "Failure" in ln][:1])
_d0 = _pc["categories"].get("Tool", {}).get("no_path")
_rw(_P.config_next("layers", "common.json"), lambda c: c["categories"]["Tool"].update(no_path=""))
_miss = [x["line"] for x in CM.build(_P.config_next("layers"))["checks"]["경고"] if "'Tool'" in x["line"]]
show("B174 ⓓ 옛 목록 밖 카테고리는 제안에서 「안 씀 + 사유」 · 사유 없는 「안 씀」은 지도 점검의 누락",
     _d0 == CN.WHY_KEPT and "Tool" in _rep.split("## ⓐ", 1)[-1].split("\n## ", 1)[0]
     and len(_miss) == 1 and _miss[0].startswith("누락 — 'Tool'"), f"사유 {_d0!r} · 점검 {_miss}")

_old174(lambda: _rw(_P.layers("process", "config.json"),
                    lambda c: c["category_pair_map"].update({"Unit,Process": "located_in"})))
_rw(_P.layers("quality", "config.json"), lambda c: c.setdefault("category_pair_map", {}).update({"Unit,Process": "part_of"}))
_rc, _o = _boot()
_m174 = CM.build()
show("B174 ⓕ 지도 — 카테고리마다 이름 꼴(골격 · 경로 · 위 노드 아래) · 제안 폴더를 읽는 길(위 ⓑ) · 층끼리 같은 쌍 다른 관계면 "
     "제안 없이 문면(멈춤)",
     _m174["categories"]["Process"]["name_form"] == "이름 그대로(골격)"
     and _m174["categories"]["Property"]["name_form"].startswith("<공정>::<Unit>::<이름>")
     and _rc != 0 and "[멈춤] 쌍 Unit,Process의 관계가 층마다 다르다" in _o and not _P.config_next("layers").exists(),
     [ln for ln in _o.splitlines() if "[멈춤]" in ln][:1])

# 리뷰 고침(B174) — 섞인 모양(공통은 새 모양 · 층에 남은 겹친 정의) · 「안 씀」 카테고리의 앞말(순수 함수 — 레포 config 읽기만)
_com174 = json.loads((ROOT / "layers" / "common.json").read_text(encoding="utf-8"))
_cfg174 = {lay: json.loads((ROOT / "layers" / lay / "config.json").read_text(encoding="utf-8")) for lay in ("process", "quality")}
_cfg174["quality"]["categories"]["Property"] = "(시험) 관리항목"
_cfg174["quality"]["uses"].remove("Property")
_mx174 = CN.propose(_com174, _cfg174)
show("B174 리뷰 고침 ⓐ 섞인 모양 → 제안은 공통 쌍 · sep · 경로를 그대로 두고 겹친 정의만 uses로(이름 바뀜 0 · 제안은 새 모양)",
     not _mx174["stops"] and _mx174["common"]["pairs"] == _com174["pairs"] and _mx174["common"]["sep"] == _com174["sep"]
     and not any("no_path" in v for v in _mx174["common"]["categories"].values())
     and "Property" in _mx174["layers"]["quality"]["uses"] and not _mx174["report"]["이름 바뀜"]
     and not catalog.old_shape(_mx174["layers"], _mx174["common"]),
     f"쌍 {len(_mx174['common']['pairs'])} · quality uses {_mx174['layers']['quality']['uses']}")
_com174["categories"]["Property"]["no_path"] = "(시험) 공용 분류"
_nr174 = catalog.naming_rule(_com174, _cfg174)
show("B174 리뷰 고침 ⓑ 「안 씀」 카테고리는 위가 일반 노드인 쌍의 아래여도 앞말이 없다 — 이름 규칙과 지도 이름 꼴이 같은 답",
     "Property" not in _nr174["path"] + _nr174["nest"]
     and CM.name_forms(_com174, _cfg174)["Property"] == "이름 그대로(경로 안 씀)", str(_nr174))
_oc174 = json.loads((OLD174 / "common.json").read_text(encoding="utf-8"))
_ocf174 = {lay: json.loads((OLD174 / lay / "config.json").read_text(encoding="utf-8")) for lay in ("process", "quality")}
_oc174["canonical_scope"] = {}                                 # 옛 규칙이 있되 목록이 비었다 = 아무것도 경로를 쓰지 않았다
_em174 = CN.propose(_oc174, _ocf174)
_rv174 = json.loads(json.dumps(_cfg174))
_rv174["quality"]["uses"].append("Property")
_rv174["quality"]["categories"].pop("Property")
_rv174["quality"]["category_pair_map"] = {"Process,Unit": "part_of"}   # 공통 쌍 Unit → Process와 방향이 거꾸로
_rp174 = CN.propose(json.loads((ROOT / "layers" / "common.json").read_text(encoding="utf-8")), _rv174)
show("B174 리뷰 고침 ⓒ 빈 옛 규칙(canonical_scope {})은 규칙이다 — 골격 밖 카테고리 전부 「안 씀」 · 이름 바뀜 0 / ⓓ 공통 쌍과 "
     "방향이 거꾸로인 남은 층 매핑은 제안 없이 멈춘다",
     {c for c, v in _em174["common"]["categories"].items() if "no_path" in v} == {"Unit", "Property", "Failure"}
     and not _em174["report"]["이름 바뀜"] and not _em174["stops"]
     and len(_rp174["stops"]) == 1 and "엣지가 둘이다" in _rp174["stops"][0],
     f"안 씀 {sorted(c for c, v in _em174['common']['categories'].items() if 'no_path' in v)} · 멈춤 {_rp174['stops'][:1]}")
init.init(fresh_=True, all_=True)

done()
