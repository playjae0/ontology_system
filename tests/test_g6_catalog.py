# -*- coding: utf-8 -*-
"""G6 ⑩ 층 겹침을 한 노드로 — 공통 config(카테고리 카탈로그) · 전역 해소 · 주·겸 (B90).

레포 `layers/`(mock seed)는 겹침도 겸도 선언하지 않는다 — 네 벌 diff 0이 「기존 동작
불변」의 증명이다. 겹침·겸의 성질은 **테스트 전용 층 덧칠**
(`tests/fixtures/layers_b90/overlay.json` — 창작 · 메커니즘 확인)로 잰다.

잠그는 성질:
  ① mock 카탈로그는 층 선언의 복사다(집 = 선언한 층 하나 · 이름 규칙은 카탈로그 한 곳) ·
     `bootstrap` 거부 다섯 갈래가 갈래 표시와 고칠 자리를 말한다 · 운영에서 없으면 초안을
     만들고(겹친 카테고리의 집은 빈칸) 멈추며 초안을 덮지 않는다 · doctor 첫 줄이 판을 말한다
  ② 층이 겹쳐도 노드는 집 하나 — prose·table 같은 결과(매칭 · 새 노드는 집에 · 큐 layer=집 ·
     엣지는 뽑은 층에 · 끝점은 집 노드) · `target_layer`가 집과 다르면 G4C FAIL
  ③ 겸 — 좌표 자신을 가리키는 설비 표기는 좌표다(새 노드 0 · 대장 self_coord) · 겸으로
     삼항이 통과한다 · 겸을 지우면 지금처럼 새 노드(겸은 데이터) · 추출 어휘에 겸 한 줄 ·
     `show node`가 겸을 보인다
  ④ 층 안 확장으로 닿은 걸침 엣지도 저장한 층의 템플릿으로 문장화된다 · 다리로도 닿으면 한 번만
  ⑤ config를 바꾸면 등록 스키마 재대조가 doc_type마다 FAIL/PASS 줄을 낸다 · prose 층의 좌표 경고
  ⑥ 등록 패키지의 쓰기는 원자적 한 자리 · 디버그 파일은 작업 단(work/)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from core.state import catalog     # noqa: E402
from core.build.table import build_table   # noqa: E402

def snapshot(doc_prefix):
    """그래프별 성질 — 품질층 Unit · 문서가 만든 공정층 Unit · 품질층에 저장된 Unit 끝점 엣지 · 큐."""
    qg, pg = open_graph("quality"), open_graph("process")

    def nm(i):
        return (qg.get(i) or pg.get(i) or {}).get("canonical")
    return {"q_units": sorted(n["canonical"] for n in qg.nodes.values() if n["category"] == "Unit"),
            "p_units": sorted(n["canonical"] for n in pg.nodes.values()
                              if n["category"] == "Unit" and doc_prefix in str(n["provenance"])),
            "q_edges": sorted((e["rel"], nm(e["src"]), nm(e["dst"])) for e in qg.edges
                              if (pg.get(e["dst"]) or {}).get("category") == "Unit"),
            "queue": sorted((x["kind"], x["payload"].get("layer"), x["payload"].get("surface"))
                            for x in store.read(store.QUEUE, [])
                            if x["doc_id"].startswith(doc_prefix) and x["kind"] == "auto_node")}


# ────────────────────────────────────────────────────────────── ①
print("\n■ B90 ① 층 공통 config — 카테고리 카탈로그")
init.init(fresh_=True)
_decl = catalog.declared_by()
show("① mock 카탈로그는 층 선언의 복사다 — 집 = 선언한 층 하나 · 거부 0 · 이름 규칙은 카탈로그에만",
     all(len(v) == 1 and catalog.home(c) == v[0] for c, v in _decl.items())
     and catalog.problems() == []
     and not any("canonical_scope" in json.loads(_P.layers(l, "config.json").read_text(encoding="utf-8"))
                 for l in _decl["Process"] + _decl["Failure"])
     and load_config("quality").get("canonical_scope") == catalog.canonical_scope(),
     str({c: catalog.home(c) for c in _decl}))


def _problem(mutate_layer=None, mutate_common=None):
    init.init(fresh_=True)
    if mutate_layer:
        _rw(_P.layers(mutate_layer[0], "config.json"), mutate_layer[1])
    if mutate_common:
        _rw(_P.common(), mutate_common)
    return catalog.problems()


_cases = {
    "ⓑ": _problem(("quality", lambda c: c["categories"].update({"Tool": "공구"}))),
    "ⓒ": _problem(mutate_common=lambda c: c["categories"]["Failure"].update(home="process")),
    "ⓓ": _problem(("quality", lambda c: c.update(canonical_scope={"sep": "::"}))),
    "ⓔ": _problem(mutate_common=lambda c: c["categories"]["Process"].update(
        also={"Tool": ["sub"], "Unit": ["floor"]})),
}
show("① 거부 네 갈래(ⓑ 카탈로그 밖 · ⓒ 선언 안 한 집 · ⓓ 층에 남은 이름 규칙 · ⓔ 겸의 대상·단) — 갈래마다 고칠 자리를 말한다",
     all(any(t == k for t, _m in v) for k, v in _cases.items())
     and any("Tool" in m for _t, m in _cases["ⓑ"])
     and any("선언하지 않은 층" in m for _t, m in _cases["ⓒ"])
     and any("에서 지운다" in m for _t, m in _cases["ⓓ"])
     and sum(1 for t, _m in _cases["ⓔ"] if t == "ⓔ") == 2,
     str({k: [t for t, _m in v] for k, v in _cases.items()}))
init.init(fresh_=True)

# ⓐ 운영 — 없으면 초안을 만들고 멈춘다(자동 채택 0) · 초안을 덮지 않는다
with tempfile.TemporaryDirectory(prefix="b90_") as _td:
    _r = Path(_td)
    shutil.copytree(ROOT / "layers" / "process", _r / "layers" / "process")
    shutil.copytree(ROOT / "layers" / "quality", _r / "layers" / "quality")
    _rw(_r / "layers" / "quality" / "config.json",
        lambda c: c["categories"].update(OV["quality"]["categories"]))
    # 사내 옛 판 모양 — 이름 규칙이 아직 층 config에 있다(초안이 그것을 옮긴다)
    _rw(_r / "layers" / "process" / "config.json",
        lambda c: c.update(canonical_scope=catalog.canonical_scope()))
    (_r / "registry").mkdir()
    (_r / "registry" / "doc_types.json").write_text("{}", encoding="utf-8")   # 이관된 루트
    _env = {**os.environ, "USE_MOCK": "0", "ONTO_HOME": str(_r)}

    def _boot():
        r = subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], cwd=str(ROOT),
                           env=_env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout + r.stderr
    _rc1, _o1 = _boot()
    _draft = _r / "layers" / "common.draft.json"
    _d = json.loads(_draft.read_text(encoding="utf-8")) if _draft.exists() else {}
    _draft.write_text(_draft.read_text(encoding="utf-8").replace('"Failure"', '"Failure" '),
                      encoding="utf-8")                                  # 사람이 채우는 중
    _mark = _draft.read_text(encoding="utf-8")
    _rc2, _o2 = _boot()
    show("① ⓐ 운영에서 없으면 초안을 만들어 보이고 멈춘다 — 겹친 카테고리의 집은 빈칸 · 이름 규칙은 옮긴다 · 초안을 덮지 않는다",
         _rc1 != 0 and not (_r / "layers" / "common.json").exists()
         and _d.get("categories", {}).get("Unit", {}).get("home") == ""
         and _d["categories"]["Process"]["home"] == "process"
         and "canonical_scope" in _d and "빈칸" in _o1
         and _rc2 != 0 and _draft.read_text(encoding="utf-8") == _mark and "덮지 않았다" in _o2,
         _o1.strip().splitlines()[0][:100] if _o1.strip() else "")
    _d["categories"]["Unit"]["home"] = "process"
    _d.pop("_빈칸", None)
    (_r / "layers" / "common.json").write_text(json.dumps(_d, ensure_ascii=False), encoding="utf-8")
    _rw(_r / "layers" / "process" / "config.json", lambda c: c.pop("canonical_scope", None))
    _rc3, _o3 = _boot()
    show("① ⓐ 빈칸을 채워 저장하면 bootstrap이 선다", _rc3 == 0, _o3.strip()[-120:])

_q = subprocess.run([sys.executable, str(ROOT / "doctor.py"), "--quick"], cwd=str(ROOT),
                    capture_output=True, text=True, env={**os.environ, "USE_MOCK": "1"},
                    stdin=subprocess.DEVNULL).stdout
show("① doctor 첫 줄이 좌표 층과 공통 config 판을 말한다",
     "좌표 층 process · 공통 config v1" in _q)

# ────────────────────────────────────────────────────────────── ②
print("\n■ B90 ② 전역 해소 — 층이 겹쳐도 노드는 집 하나 · table·prose 한 길")
overlay()
run_document(load("CP01"))
_env = dict(PROSE, doc_id="XB90P", chunks=[dict(C1, source_locator="XB90P-C001")])
run_document(_env)
_cid = next(iter(chunks_of("XB90P")))
_pb = build_prose(_env, load_config("quality"), open_graph("quality"),
                  [{"chunk_id": _cid, "attach": [],
                    "entities": [{"surface": "노칭 프레스", "category": "Unit"},
                                 {"surface": "노칭 커터", "category": "Unit"},
                                 {"surface": "칼날 마모", "category": "Failure"}],
                    "relations": [{"src": "칼날 마모", "rel": "occurs_in", "dst": "노칭 프레스"},
                                  {"src": "칼날 마모", "rel": "occurs_in", "dst": "노칭 커터"}]}])
for _g in _pb.graphs():
    _g.save()
_ps = snapshot("XB90")
_press = node_by("process", "노칭::노칭 프레스")
show("② ⓐ 품질 prose가 공정층에 이미 있는 Unit을 말하면 그 노드에 매칭 — 품질층 Unit 노드 0",
     not _ps["q_units"] and _press and "CP01" in str(_press["provenance"])
     and "XB90P" in str(_press["provenance"]), str(_ps["q_units"]))
show("② ⓑ 새 Unit은 집(공정층)에 생기고 큐 layer=process",
     "노칭::노칭 커터" in _ps["p_units"]
     and ("auto_node", "process", "노칭 커터") in _ps["queue"], str(_ps["queue"]))
show("② ⓒ 그 문서의 엣지는 품질층에 저장되고 끝점은 공정층 노드다",
     ("occurs_in", "칼날 마모", "노칭::노칭 프레스") in _ps["q_edges"]
     and ("occurs_in", "칼날 마모", "노칭::노칭 커터") in _ps["q_edges"], str(_ps["q_edges"]))
overlay()
run_document(load("CP01"))
_row = {"process_group": "조립", "process_ref": "노칭", "electrode_type": "both",
        "failure": "칼날 마모"}
_tenv = dict(TABLE, doc_type="b90q", doc_id="XB90T",
             records=[dict(_row, source_locator="XB90T-R1", unit="노칭 프레스"),
                      dict(_row, source_locator="XB90T-R2", unit="노칭 커터")])
_tb = build_table(_tenv, load_config("quality"),
                  {"doc_type": "b90q", "layer": "quality",
                   "fields": {"failure": {"role": "entity", "category": "Failure"},
                              "unit": {"role": "entity", "category": "Unit"}},
                   "edges": [{"from": "failure", "relation": "occurs_in", "to": "unit"}]},
                  open_graph("quality"))
for _g in _tb.graphs():
    _g.save()
_ts = snapshot("XB90")
show("② ⓓ 같은 것을 table 문서로 — 결과가 같다 (두 경로 한 길)",
     _ts == _ps, f"table {_ts} ‖ prose {_ps}")
_k = subprocess.run(
    [sys.executable, "-c",
     "import gate_tables as t, gate_checks as c; t.LAYERS_DIR = %r;"
     "c.check_vocab({'layer': 'quality'}, {'unit': {'role': 'entity', 'category': 'Unit',"
     " 'target_layer': 'quality'}}, 'b90')" % str(_P.layers())],
    cwd=str(ROOT / "kit"), capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
show("② table의 target_layer가 집과 다르면 등록 관문 G4C가 FAIL로 말한다",
     "[FAIL] G4C" in _k and "집 'process'" in _k,
     next((l for l in _k.splitlines() if "G4C" in l), "")[:160])
init.init(fresh_=True)

# ────────────────────────────────────────────────────────────── ③
print("\n■ B90 ③ 주·겸 카테고리 · 자기 좌표 규칙")


def self_coord_run(also):
    overlay(component=True, also=also)
    env = dict(PROSE, doc_id="XB90S", chunks=[dict(C1, source_locator="XB90S-C001")])
    run_document(env)
    cid = next(iter(chunks_of("XB90S")))
    b = build_prose(env, load_config("process"), open_graph("process"),
                    [{"chunk_id": cid, "attach": [],
                      "entities": [{"surface": "노칭 unit", "category": "Unit"},
                                   {"surface": "칼날", "category": "Component"}],
                      "relations": [{"src": "칼날", "rel": "part_of", "dst": "노칭 unit"}]}])
    for g in b.graphs():
        g.save()
    pg = open_graph("process")
    lp = Path(_P.work("ingest_log", "XB90S.json"))           # 판정 대장 (④단)
    led = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {}
    return {"units": sorted(n["canonical"] for n in pg.nodes.values()
                            if n["category"] == "Unit" and "XB90S" in str(n["provenance"])),
            "edges": sorted((e["rel"], pg.get(e["dst"])["canonical"]) for e in pg.edges
                            if (pg.get(e["src"]) or {}).get("canonical") == "칼날"),
            "path": [r.get("path") for r in led.get("rows", []) if r.get("surface") == "노칭 unit"],
            "tier": (node_by("process", "노칭") or {}).get("tier")}


_with = self_coord_run(True)
from core.build.extract import categories_with_also                  # noqa: E402
_line = categories_with_also(load_config("process")).get("Unit", "")
_sn = subprocess.run([sys.executable, str(ROOT / "run.py"), "show", "node", "노칭"], cwd=str(ROOT),
                     capture_output=True, text=True, env={**os.environ, "USE_MOCK": "1"},
                     stdin=subprocess.DEVNULL).stdout
_without = self_coord_run(False)
show("③ ⓐ 좌표 「노칭」 아래 「노칭 unit」(Unit)은 스테이션 자신이다 — 새 Unit 0 · 대장 self_coord",
     not _with["units"] and _with["path"] == ["self_coord"] and _with["tier"] == "sub", str(_with))
show("③ ⓑ 「Component part_of Unit」이 스테이션 노드에 바로 붙는다 (겸으로 삼항 통과)",
     _with["edges"] == [("part_of", "노칭")], str(_with["edges"]))
show("③ ⓒ also를 지우면 지금처럼 새 Unit이 되고 엣지는 그 노드로 (겸은 데이터다)",
     _without["units"] == ["노칭::노칭 unit"] and _without["path"] == ["none"]
     and _without["edges"] == [("part_of", "노칭::노칭 unit")], str(_without))
show("③ 추출 어휘의 Unit 정의문 끝에 겸 한 줄 · show node가 「겸 Unit」을 보인다",
     "sub·detail 단 Process도 Unit이다" in _line and "겸 Unit" in _sn,
     _line[-60:])
init.init(fresh_=True)

# ────────────────────────────────────────────────────────────── ④
print("\n■ B90 ④ 걸침 엣지 문장화 — 층 안 확장으로 닿은 것도")
overlay()
run_document(load("CP01"))
_env = dict(PROSE, doc_id="XB90Q", chunks=[dict(C1, source_locator="XB90Q-C001")])
run_document(_env)
_cid = next(iter(chunks_of("XB90Q")))
_qb = build_prose(_env, load_config("quality"), open_graph("quality"),
                  [{"chunk_id": _cid, "attach": [],
                    "entities": [{"surface": "노칭 프레스", "category": "Unit"},
                                 {"surface": "칼날 마모", "category": "Failure"}],
                    "relations": [{"src": "칼날 마모", "rel": "occurs_in", "dst": "노칭 프레스"}]}])
for _g in _qb.graphs():
    _g.save()


def _facts(question):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "query", question, "--json",
                        "--allow-mock"], cwd=str(ROOT), capture_output=True, text=True,
                       env={**os.environ, "USE_MOCK": "1"}, stdin=subprocess.DEVNULL)
    try:
        return json.loads(r.stdout[r.stdout.find("{"):]).get("facts") or []
    except ValueError:
        return ["(json 아님) " + r.stdout[-120:]]


_want = "칼날 마모는 노칭::노칭 프레스 공정에서 발생한다"
_f1 = _facts("칼날 마모는 어디서 생기나")
_f2 = _facts("칼날 마모와 노칭 프레스")
show("④ 품질층에 저장된 걸침 엣지가 품질층 확장으로 닿으면 문장이 된다 (저장한 층의 템플릿)",
     _want in _f1, str(_f1))
show("④ 다리로도 닿은 같은 엣지는 한 번만 (중복 0)", _f2.count(_want) == 1, str(_f2))
init.init(fresh_=True)

# ────────────────────────────────────────────────────────────── ⑤
print("\n■ B90 ⑤ config를 바꾸면 등록 스키마를 다시 대조한다")
from cli.register import recheck                                    # noqa: E402
init.init(fresh_=True)
_r0 = recheck.run()
_rw(_P.layers("process", "config.json"),              # 카테고리를 지운다 — 선언과 삼항 둘 다
    lambda c: (c["categories"].pop("Property"),
               c.update(relation_patterns=[p for p in c["relation_patterns"]
                                           if "Property" not in (p["src"], p["dst"])])))
_r1 = recheck.run()
init.init(fresh_=True)
_r2 = recheck.run()
_rw(_P.layers("quality", "config.json"),
    lambda c: c.update(relation_patterns=[p for p in c["relation_patterns"]
                                          if "Process" not in (p["src"], p["dst"])]))
_r3 = recheck.run()
_fail1 = {dt for dt, ok, _l in _r1 if not ok}
show("⑤ 카테고리 하나를 지우면 그것을 쓰는 doc_type이 FAIL 줄로 — 고칠 자리(층 config 키)를 말한다",
     all(ok for _dt, ok, _l in _r0) and {"cp", "pfmea"} <= _fail1
     and all("다음 줄" in l and "config.json의" in l for dt, ok, l in _r1 if not ok and "FAIL" in l)
     and any(dt == "pfmea" and "layers/process/config.json의 categories" in l
             for dt, ok, l in _r1 if not ok),
     str(sorted(_fail1)))
show("⑤ 되돌리면 전부 PASS", _r2 and all(ok for _dt, ok, _l in _r2),
     str([l.split(" — ")[0].strip() for _dt, _o, l in _r2]))
show("⑤ prose doc_type의 층이 좌표 카테고리를 말하지 않으면 경고 (좌표를 못 단다)",
     any(dt == "ppt_quality" and "⚠" in l and "좌표를 못 단다" in l for dt, _o, l in _r3),
     str([l[:80] for dt, _o, l in _r3 if dt == "ppt_quality"]))
init.init(fresh_=True)

# ────────────────────────────────────────────────────────────── ⑥
print("\n■ B90 ⑥ registry — 원자적 쓰기 · 디버그 파일은 작업 단")
import ast as _ast                                                    # noqa: E402
_direct = [f"{p.name}:{n.lineno}" for p in sorted((ROOT / "cli" / "register").glob("*.py"))
           for n in _ast.walk(_ast.parse(p.read_text(encoding="utf-8")))
           if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
           and n.func.attr in ("write_text", "write_bytes")]
show("⑥ 등록 패키지에 직접 쓰기(write_text·write_bytes 호출) 0 — 쓰기는 원자적 한 자리",
     not _direct, str(_direct))
from core.llm import gateway as _gw                                   # noqa: E402
from cli.register import draft as _draft                              # noqa: E402
_keep = _gw.LAST_ERROR
_gw.LAST_ERROR = {"status": 400, "body": "(시험)"}
try:
    _draft._note_error("b90dbg", RuntimeError("시험"))
finally:
    _gw.LAST_ERROR = _keep
show("⑥ 게이트웨이 오류 원문은 작업 단에 남고 registry(review/)에는 없다",
     _P.register_debug("b90dbg", "last_error.json").exists()
     and not _P.review("b90dbg", "last_error.json").exists(),
     _P.show(_P.register_debug("b90dbg", "last_error.json")))
init.init(fresh_=True)

done()
