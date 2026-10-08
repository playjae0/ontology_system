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

run_document(load("CP01"))                         # process 그래프에 Property·Unit 노드
_rw(_P.layers("process", "config.json"), lambda c: c["categories"].pop("Property"))
_before = _P.common().read_bytes()
_rc, _o = _boot()
show("ⓒ 노드가 남은 카테고리를 층에서 지우면 멈춘다 — 지우지 않는다",
     _rc != 0 and "Property" in _common()["categories"] and "노드" in _o and "재빌드" in _o,
     [l for l in _o.splitlines() if "Property" in l][:1])
init.init(fresh_=True, all_=True)

print("\n■ B92 ② 노드가 있는 카테고리의 집 변경을 막는다")
_boot()                                            # 골격이 서야 문서가 노드를 만든다
run_document(load("CP01"))                         # Unit 노드가 process 그래프에
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Unit="설비"))
_rw(_P.common(), lambda c: c["categories"]["Unit"].update(home="quality"))
_rc, _o = _boot()
show("ⓔ 노드가 있는 카테고리의 home을 바꾸면 멈춘다 — 옛 집은 노드가 있는 그래프",
     _rc != 0 and "process → quality" in _o and "재빌드" in _o,
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
    show("ⓖ 운영 처음 — common.json을 바로 만든다(한 층 → 그 층 · 겹침 → 빈칸 + 멈춤) · 초안 파일 0 · 채우면 선다",
         _rc1 != 0 and _d.get("categories", {}).get("Unit", {}).get("home") == ""
         and _d["categories"]["Process"]["home"] == "process"
         and not (_r / "layers" / "common.draft.json").exists() and _rc2 == 0,
         _o1.strip().splitlines()[0][:90] if _o1.strip() else "")

# ────────────────────────────────────────────────────────────── B93
print("\n■ B93 ① 골격 카테고리의 집은 골격 층 — 자동")
init.init(fresh_=True, all_=True)
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Process="공정(렌즈)"))
_rw(_P.common(), lambda c: c["categories"].pop("Process"))
_rc, _o = _boot()
show("ⓐ 두 층이 골격 카테고리를 함께 선언해도 집 = 골격 층 자동(빈칸·멈춤 0)",
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
    _rw(_P.layers(EQ, "config.json"), lambda c: c.update(layer=EQ))
    _rw(_P.layers("process", "config.json"), lambda c: c.pop("skeleton")
        or c["categories"].pop("Process"))


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
     _rc != 0 and "골격은 b95eq에 있다" in _o and "노드" in _o and "재빌드" in _o
     and _common()["categories"]["Process"]["home"] == "process" and _eq_nodes == 0,
     [l for l in _o.splitlines() if "골격은" in l][:1])
shutil.rmtree(_P.layers(EQ), ignore_errors=True)
init.init(fresh_=True, all_=True)

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
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── B94
print("\n■ B94 ① 쓰는 층(used_by) — 결과 기록 · 사람이 관리하지 않는다")
from core.build import ledger as _LG       # noqa: E402
from core.build import extract as _EX      # noqa: E402
init.init(fresh_=True, all_=True)
_decl0 = catalog.declared_by()
_ub0 = {c: v.get("used_by") for c, v in _common()["categories"].items()}
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].update(Property="품질 인자(창작)"))
_v0, _l0 = _common()["common_version"], len(_logs())
_rc, _o = _boot()
_ub1 = _common()["categories"]["Property"].get("used_by")
_rw(_P.layers("quality", "config.json"), lambda c: c["categories"].pop("Property"))
_rc2, _o2 = _boot()
show("ⓐ used_by = 층 config의 선언(처음 · 선언 추가/삭제마다) · 판 +1 · 로그",
     all(_ub0[c] == _decl0[c] for c in _decl0)
     and _rc == 0 and _ub1 == ["process", "quality"] and _common()["common_version"] >= _v0 + 2
     and _common()["categories"]["Property"]["used_by"] == ["process"]
     and "used_by 'Property' + quality" in _o and "used_by 'Property' − quality" in _o2
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
_rw(_P.common(), lambda c: c["canonical_scope"]["bind_categories"].append("Component"))
_new_layer({"Component": "구성 부품(창작)", "DefectHistory": "이슈 이력의 결함(창작)"})
_rcd, _od = _boot("--dry-run")
_rc, _o = _boot()
show("ⓓ 새 카테고리 경고에 이름 규칙 줄 — 적용(bind_categories 안) · 미적용(기준과 「노드가 생기기 전에」) · 종료 코드 불변 · dry-run 같다",
     _rc == 0 and _rcd == 0
     and "이름 규칙: 'Component'는 공정 스코프 적용" in _o
     and "이름 규칙: 'DefectHistory'는 미적용" in _o and "노드가 생기기 전에 정한다" in _o
     and "이름 규칙: 'DefectHistory'는 미적용" in _od,
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

done()
