# -*- coding: utf-8 -*-
"""G6 ⑩ 층 겹침을 한 노드로 — 공통 config(카테고리 카탈로그) · 전역 해소 · 주·겸 (B90).

레포 `layers/`(mock seed)는 겹침도 겸도 선언하지 않는다 — 네 벌 diff 0이 「기존 동작
불변」의 증명이다. 겹침·겸의 성질은 **테스트 전용 층 덧칠**
(`tests/fixtures/layers_b90/overlay.json` — 창작 · 메커니즘 확인)로 잰다.

잠그는 성질:
  ① mock 카탈로그는 층 선언의 복사다(집 = 선언한 층 하나 · 이름 규칙은 카탈로그 한 곳) ·
     `bootstrap` 거부 다섯 갈래가 갈래 표시와 고칠 자리를 말한다 · 운영에서 없으면 층 config에서
     만들고(겹친 카테고리의 집은 빈칸) 멈춘다(B92) · doctor 첫 줄이 판을 말한다
  ② 층이 겹쳐도 노드는 집 하나 — prose·table 같은 결과(매칭 · 새 노드는 집에 · 큐 layer=집 ·
     엣지는 뽑은 층에 · 끝점은 집 노드) · `target_layer`가 집과 다르면 G4C FAIL
  ③ 겸 — 좌표 자신을 가리키는 설비 표기는 좌표다(새 노드 0 · 대장 self_coord) · 겸으로
     삼항이 통과한다 · 겸을 지우면 지금처럼 새 노드(겸은 데이터) · 추출 어휘에 겸 한 줄 ·
     `show node`가 겸을 보인다
  ④ 층 안 확장으로 닿은 걸침 엣지도 저장한 층의 템플릿으로 문장화된다 · 다리로도 닿으면 한 번만
  ⑤ config를 바꾸면 등록 스키마 재대조가 doc_type마다 FAIL/PASS 줄을 낸다 · prose 층의 좌표 경고 · B174 ⓔ G4C 문면이 uses를
     말한다(골격 카테고리 포함) · 새 모양 mock 지도의 「선언 없이 씀」 0
  ⑥ 등록 패키지의 쓰기는 원자적 한 자리 · 디버그 파일은 작업 단(work/)
  B192 ⓐ ⓑ config 문법 단 — 모르는 키 · 닫힌 값 · JSON 문법 · 없는 카테고리 참조 ⇒ bootstrap(--dry-run) · export config · 인입이 같은 거부
  B178 ⓐ 묻는 목록 = 말하는 카테고리(uses 정의문은 집 층) ⓑ 추출 판 — uses 빈 층 그대로 · 쓰는 층은 집 층 정의문까지 ⓒ 품질 산문의 공정층 값이 집 그래프에서 해소
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
init.init(fresh_=True, all_=True)
_decl = catalog.declared_by()
show("① mock 카탈로그는 층 선언의 복사다 — 집 = 선언한 층 하나 · 거부 0 · 이름 규칙은 공통 config에만(고침 B174 — 옛 모양 0)",
     all(len(v) == 1 and catalog.home(c) == v[0] for c, v in _decl.items())
     and catalog.problems() == [] and catalog.old_shape() == [],
     str({c: catalog.home(c) for c in _decl}))


def _problem(mutate_layer=None, mutate_common=None):
    init.init(fresh_=True, all_=True)
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
     and any("옛 모양" in m and "제안" in m for _t, m in _cases["ⓓ"])          # 고침 B174 — 옛 모양은 제안으로
     and sum(1 for t, _m in _cases["ⓔ"] if t == "ⓔ") == 2,
     str({k: [t for t, _m in v] for k, v in _cases.items()}))
init.init(fresh_=True, all_=True)

# B192 ⓐ ⓑ 문법 단 — 키 오타 · 공통 키 오타 · 골격 키 오타 · 닫힌 값 밖 · JSON 쉼표 · 없는 카테고리 참조 → 세 명령(+ 인입)이 같은 거부 문면
def _run192(*argv):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), *argv], cwd=str(ROOT), capture_output=True, text=True,
                       env={**os.environ, "USE_MOCK": "1"}, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


def _case192(path, edit):
    init.init(fresh_=True, all_=True)
    if callable(edit):
        _rw(path, edit)
    else:
        path.write_text(path.read_text(encoding="utf-8").replace(*edit, 1), encoding="utf-8")
    outs = [_run192("bootstrap", "--dry-run"), _run192("bootstrap"), _run192("export", "config", str(_P.export("b192.html")))]
    line = next((ln.split("ⓗ ", 1)[-1].split("ⓘ ", 1)[-1].split("[상태] ", 1)[-1] for ln in outs[0][1].splitlines()
                 if "[상태]" in ln and ("layers/" in ln)), "")
    ing = _run192("ingest-file", str(fixtures.ROOT_DIR / "raw" / "CP01.xlsx"), "--allow-mock") if "relation_patern" in line else None
    return line, outs, ing


from core.state import fixtures            # noqa: E402
_c192 = {"층 키": _case192(_P.layers("process", "config.json"),
                         lambda c: c.__setitem__("relation_patern", c.pop("relation_patterns"))),
         "공통 키": _case192(_P.common(), lambda c: c.__setitem__("parent_pair", c.pop("parent_pairs"))),
         "골격 키": _case192(_P.layers("process", "skeleton.json"), lambda c: c.__setitem__("ALIAS", c.pop("ALIASES"))),
         "닫힌 값": _case192(_P.layers("quality", "config.json"),
                          lambda c: c["cross_layer_traverse"]["occurs_in"].__setitem__("direction", "upward")),
         "JSON": _case192(_P.layers("quality", "config.json"), ('",\n', '"\n')),
         "참조": _case192(_P.layers("quality", "config.json"), lambda c: c.__setitem__("uses", [u for u in c["uses"] if u != "Process"]))}
_bad192 = {k: (bool(ln), [o[0] for o in outs[:2]], all(ln in o[1] for o in outs), ing and ln in ing[1])
           for k, (ln, outs, ing) in _c192.items()}
show("B192 ⓐ 문법 단 — 층 키 오타 · 공통 parent_pair · 골격 ALIAS · direction \"upward\" · JSON 쉼표 빠짐 ⇒ bootstrap --dry-run · "
     "bootstrap · export config가 같은 거부 문면(파일 · 키 · 다음 줄) · 인입(사전 점검)도 같은 줄 · rc 1",
     all(v[0] and v[1] == [1, 1] and v[2] for k, v in _bad192.items() if k != "참조") and _bad192["층 키"][3]
     and "relation_patterns" in _c192["층 키"][0] and "3행" in _c192["JSON"][0] and "upward" in _c192["닫힌 값"][0],
     " · ".join(f"{k} {v}" for k, v in _bad192.items()) + f" | {_c192['층 키'][0][:120]}")
show("B192 ⓑ 관계 패턴이 쓰는 카테고리가 categories에도 uses에도 없다 ⇒ 경고가 아니라 거부(세 명령 같은 줄 · rc 1)",
     _bad192["참조"][0] and _bad192["참조"][1] == [1, 1] and _bad192["참조"][2] and "'Process'" in _c192["참조"][0],
     _c192["참조"][0][:140])
init.init(fresh_=True, all_=True)

# ⓐ 운영 — 없으면 초안을 만들고 멈춘다(자동 채택 0) · 초안을 덮지 않는다
with tempfile.TemporaryDirectory(prefix="b90_") as _td:
    _r = Path(_td)
    shutil.copytree(ROOT / "layers" / "process", _r / "layers" / "process")
    shutil.copytree(ROOT / "layers" / "quality", _r / "layers" / "quality")
    _rw(_r / "layers" / "quality" / "config.json",
        lambda c: c["categories"].update(OV["quality"]["categories"]))
    # 사내 옛 판 모양 — 이름 규칙이 아직 층 config에 있다(고침 B174 — 초안은 옮기지 않고 옛 모양 제안이 읽는다)
    _rw(_r / "layers" / "process" / "config.json", lambda c: c.update(canonical_scope={
        "bind_categories": ["Failure", "Property", "Unit"], "nest_categories": ["Property"], "sep": "::"}))
    (_r / "registry").mkdir()
    (_r / "registry" / "doc_types.json").write_text("{}", encoding="utf-8")   # 이관된 루트
    _env = {**os.environ, "USE_MOCK": "0", "ONTO_HOME": str(_r)}

    def _boot():
        r = subprocess.run([sys.executable, str(ROOT / "run.py"), "bootstrap"], cwd=str(ROOT),
                           env=_env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout + r.stderr
    _rc1, _o1 = _boot()
    # **B92부터 초안 파일을 쓰지 않는다** — 같은 규칙으로 common.json을 바로 만들고 빈칸이면
    # 멈춘다(기대 변경 · B92 ① — 잠그는 성질은 그대로: 겹친 집은 사람 · 이름 규칙은 옮긴다).
    _cj = _r / "layers" / "common.json"
    _d = json.loads(_cj.read_text(encoding="utf-8")) if _cj.exists() else {}
    show("① ⓐ 운영에서 없으면 층 config에서 만들고 멈춘다 — 겹친 카테고리의 집은 빈칸 · 초안 파일 0(고침 B174 — 이름 규칙은 옮기지 않는다)",
         _rc1 != 0 and _d.get("categories", {}).get("Unit", {}).get("home") == ""
         and _d["categories"]["Process"]["home"] == "process"
         and "canonical_scope" not in _d and "빈칸" in _o1
         and not (_r / "layers" / "common.draft.json").exists(),
         _o1.strip().splitlines()[0][:100] if _o1.strip() else "")
    _d["categories"]["Unit"]["home"] = "process"
    _cj.write_text(json.dumps(_d, ensure_ascii=False), encoding="utf-8")
    _rc3, _o3 = _boot()
    show("① ⓐ 빈칸을 채워 저장하면 다음은 옛 모양(겹친 정의 · 층의 이름 규칙) — 제안 · 보고를 쓰고 멈춘다(고침 B174 — 옛: 선다)",
         _rc3 != 0 and "옛 모양" in _o3 and (_r / "work" / "config_next" / "보고.md").exists(), _o3.strip()[:120])

# doctor 머리 줄 = doctor가 하위 실행으로 그리는 화면 그 함수(`cli.doctor_view head`) — doctor 전체를 돌리지 않는다(B121 ②ⓓ)
_q = subprocess.run([sys.executable, "-m", "cli.doctor_view", "head"], cwd=str(ROOT),
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
show("② ⓒ 그 문서의 엣지는 품질층에 저장되고 끝점은 공정층 노드다",     # 기대 변경(B171 — 고장은 공정 경로 이름)
     ("occurs_in", "노칭::칼날 마모", "노칭::노칭 프레스") in _ps["q_edges"]
     and ("occurs_in", "노칭::칼날 마모", "노칭::노칭 커터") in _ps["q_edges"], str(_ps["q_edges"]))
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
# 고침(B187 ⓪ — 화면 낱말 = config 키: 「집」 → home)
show("② table의 target_layer가 home과 다르면 등록 관문 G4C가 FAIL로 말한다",
     "[FAIL] G4C" in _k and "home 'process'" in _k,
     next((l for l in _k.splitlines() if "G4C" in l), "")[:160])
init.init(fresh_=True, all_=True)

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
init.init(fresh_=True, all_=True)

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


_want = "노칭::칼날 마모는 노칭::노칭 프레스 공정에서 발생한다"     # 기대 변경(B171 — 고장은 공정 경로 이름)
_f1 = _facts("칼날 마모는 어디서 생기나")
_f2 = _facts("칼날 마모와 노칭 프레스")
show("④ 품질층에 저장된 걸침 엣지가 품질층 확장으로 닿으면 문장이 된다 (저장한 층의 템플릿)",
     _want in _f1, str(_f1))
show("④ 다리로도 닿은 같은 엣지는 한 번만 (중복 0)", _f2.count(_want) == 1, str(_f2))
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── ⑤
print("\n■ B90 ⑤ config를 바꾸면 등록 스키마를 다시 대조한다")
from cli.register import recheck                                    # noqa: E402
init.init(fresh_=True, all_=True)
_r0 = recheck.run()
_rw(_P.layers("process", "config.json"),              # 카테고리를 지운다 — 선언과 삼항 둘 다
    lambda c: (c["categories"].pop("Property"),
               c.update(relation_patterns=[p for p in c["relation_patterns"]
                                           if "Property" not in (p["src"], p["dst"])])))
_r1 = recheck.run()
init.init(fresh_=True, all_=True)
_r2 = recheck.run()
_rw(_P.layers("quality", "config.json"),                      # 고침(B174 — 말하는 카테고리는 categories ∪ uses)
    lambda c: c.update(uses=[x for x in c["uses"] if x != "Process"],
                       relation_patterns=[p for p in c["relation_patterns"] if "Process" not in (p["src"], p["dst"])]))
_r3 = recheck.run()
_fail1 = {dt for dt, ok, _l in _r1 if not ok}
show("⑤ 카테고리 하나를 지우면 그것을 쓰는 doc_type이 FAIL 줄로 — 고칠 자리(층 config 키)를 말한다",
     all(ok for _dt, ok, _l in _r0) and {"cp", "pfmea"} <= _fail1
     and all("다음 줄" in l and "config.json의" in l for dt, ok, l in _r1 if not ok and "FAIL" in l)
     and any(dt == "pfmea" and "layers/process/config.json의" in l and "categories" in l     # 고침(B174 — 고칠 자리 문면에 uses가 함께)
             for dt, ok, l in _r1 if not ok),
     str(sorted(_fail1)))
show("⑤ 되돌리면 전부 PASS", _r2 and all(ok for _dt, ok, _l in _r2),
     str([l.split(" — ")[0].strip() for _dt, _o, l in _r2]))
show("⑤ prose doc_type의 층이 좌표 카테고리를 말하지 않으면 경고 (좌표를 못 단다)",
     any(dt == "ppt_quality" and "⚠" in l and "좌표를 못 단다" in l for dt, _o, l in _r3),
     str([l[:80] for dt, _o, l in _r3 if dt == "ppt_quality"]))
init.init(fresh_=True, all_=True)
from cli import config_map as _CM174                                 # noqa: E402
_g4c174 = [l for dt, ok, l in _r3 if dt == "pfmea" and not ok and "G4C" in l]
_miss174 = _CM174.counts(_CM174.build())["선언 없이 씀"]
show("B174 ⓔ G4C — uses에 없는 다른 층 카테고리(골격 카테고리 Process)를 쓰는 스키마 FAIL · 문면이 uses를 말한다 · 적으면 PASS"
     "(⑤ 되돌림) · 새 모양 mock 지도의 「선언 없이 씀」 0",
     _g4c174 and all("uses" in l for l in _g4c174) and all(ok for dt, ok, _l in _r2 if dt == "pfmea") and _miss174 == 0,
     f"{[l[:110] for l in _g4c174]} · 선언 없이 씀 {_miss174}")

# ────────────────────────────────────────────────────────────── B178 묻는 목록 = 말하는 카테고리 · 추출 판
print("\n■ B178 추출이 묻는 카테고리 = 그 층이 말하는 카테고리(집 ∪ uses · 정의문은 집 층) · 추출 판 · 품질 산문의 공정층 값")
import contextlib                                                      # noqa: E402
import copy as _cp178                                                  # noqa: E402
import io                                                              # noqa: E402
import json as _js178                                                  # noqa: E402
from core.build.extract import categories_with_also as _ask178        # noqa: E402
from core.state import config_scope as _CS178                         # noqa: E402
from core.build import ledger as _LG178                               # noqa: E402
init.init(fresh_=True, all_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _cfg178(lay):
    return _js178.loads(_P.layers(lay, "config.json").read_text(encoding="utf-8"))


_pc178, _qc178 = _cfg178("process"), _cfg178("quality")
_qa178 = _ask178(_qc178)
show("B178 ⓐ 품질층 묻는 목록에 uses 카테고리(정의문 = 집 층 config 그대로) · uses가 빈 층의 묻는 목록은 그 층 categories 그대로",
     set(_qc178["uses"]) <= set(_qa178) and all(_qa178[c] == _pc178["categories"][c] for c in _qc178["uses"])
     and _ask178(_pc178) == _pc178["categories"] and not _pc178.get("uses"),
     f"품질층 {list(_qa178)} · 공정층 {list(_ask178(_pc178))}")
_k178 = {lay: _CS178.extract_key(c) for lay, c in (("process", _pc178), ("quality", _qc178))}
_c178 = sorted(set(_qc178["uses"]) - set(_qc178["categories"]))[0]
_p0178 = _P.layers("process", "config.json").read_bytes()
try:                                                                   # 사본 — 집 층(공정층)에서 uses 카테고리의 정의문만 고친다
    _rw(_P.layers("process", "config.json"), lambda c: c["categories"].update({_c178: c["categories"][_c178] + " (B178 시험)"}))
    _kq178 = _CS178.extract_key(_cfg178("quality"))
finally:
    _P.layers("process", "config.json").write_bytes(_p0178)
show("B178 ⓑ 추출 판 — uses가 빈 층은 uses 칸 없이 잰 판과 같다(판 그대로) · uses가 있는 층은 바뀐다 · 집 층에서 그 카테고리 정의문을 "
     "고치면 쓰는 층의 판도 바뀐다",
     _k178["process"] == _CS178.extract_key({k: v for k, v in _pc178.items() if k != "uses"})
     and _k178["quality"] != _CS178.extract_key({k: v for k, v in _qc178.items() if k != "uses"})
     and _kq178 != _k178["quality"], f"집 층 정의문 바꾼 카테고리 {_c178}")
with contextlib.redirect_stdout(io.StringIO()):
    run_document(load("CP01"))
_env178 = _cp178.deepcopy(load("QPPT01"))                             # 품질 산문 사본(창작 — 힌트 없는 doc_id라 mock 문형이 뽑는다)
_env178["doc_id"] = "QB178"
for _c in _env178["chunks"]:
    _c["doc_id"] = "QB178"
_env178["chunks"][-1].update(text="버 발생은 노칭 정밀도로 관리한다.", process_ref="노칭")
with contextlib.redirect_stdout(io.StringIO()):
    run_document(_env178)
_pg178 = open_graph("process")
_v178 = [r for r in (_LG178.read("QB178") or {}).get("rows") or [] if r.get("role") == "entity"
         and catalog.home(r.get("category")) == "process"]
show("B178 ⓒ 품질 산문 청크에서 집이 공정층인 카테고리 값이 뽑혀 공정층 그래프에서 해소된다(대장 층 = 집 · 노드는 공정층 그래프)",
     _v178 and all(r.get("layer") == "process" and r.get("node_id") in _pg178.nodes for r in _v178),
     str([(r.get("surface"), r.get("category"), r.get("verdict"), r.get("target")) for r in _v178]))

# ────────────────────────────────────────────────────────────── B180 엣지 원칙
print("\n■ B180 위치 폴백은 부모 엣지가 어느 층에도 없는 노드에만 · 같은 엣지는 그래프 전체에 한 벌(B178 ⓒ 사본 · 창작)")
from core.state import fixtures as _FX180                             # noqa: E402 — 추출 힌트 자리(시험 사본)
from core.build import gate as _GT180                                  # noqa: E402


def _q180(doc_id, text, ents, base="QPPT01"):
    """산문 사본(품질 QPPT01 · 공정 PPT01) — 마지막 조각 글 · 공정 좌표 노칭 · 그 조각의 추출 힌트(관계 0)."""
    env = _cp178.deepcopy(load(base))
    env["doc_id"] = doc_id
    for c in env["chunks"]:
        c["doc_id"] = doc_id
    last = env["chunks"][-1]
    last.update(text=text, process_ref="노칭")
    _FX180.EXTRACT_HINTS.mkdir(parents=True, exist_ok=True)
    (_FX180.EXTRACT_HINTS / f"{doc_id}.json").write_text(_js178.dumps(
        {last["source_locator"]: {"entities": ents, "relations": [], "attach": []}}, ensure_ascii=False), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        run_document(env)
    return [r for r in (_LG178.read(doc_id) or {}).get("rows") or [] if r.get("role") == "entity"]


def _ends180(nid):
    return {lay: [e for e in open_graph(lay).edges if nid in (e["src"], e["dst"])] for lay in ("process", "quality")}


def _kept180(rows, surface):
    return sum(1 for r in rows if r.get("surface") == surface
               and any(a.get("path") == _LG178.KEPT for a in r.get("attached") or []))


_PROP180 = {"category": "Property"}
_pe180 = len(open_graph("process").edges)
_nq180 = next((r.get("node_id") for r in _v178 if r.get("surface") == "노칭 정밀도"), None)
_qe180 = len(_ends180(_nq180)["quality"]) if _nq180 else 0                 # B178 ⓒ의 관계 엣지(controlled_by)는 그대로
_ra180 = _q180("QB180A", "노칭 정밀도를 매 교대 확인한다.", [{"surface": "노칭 정밀도", **_PROP180}])
_na180 = next((r.get("node_id") for r in _ra180 if r.get("surface") == "노칭 정밀도"), None)
show("B180 ⓐ 공정층 기존 노드(부모 있음)에 붙은 품질 산문 관리항목 — 품질층 파일에 그 노드의 새 엣지 0 · 공정층 엣지 수 그대로 · "
     "「부모 있음 — 폴백 안 함」 1",
     _na180 in open_graph("process").nodes and _na180 == _nq180 and len(_ends180(_na180)["quality"]) == _qe180
     and len(open_graph("process").edges) == _pe180 and _kept180(_ra180, "노칭 정밀도") == 1,
     f"품질층 엣지 {_qe180} → {len(_ends180(_na180)['quality'])} · 공정층 엣지 {_pe180} → {len(open_graph('process').edges)}")
_rb180 = _q180("QB180B", "노칭 진동을 매 교대 확인한다.", [{"surface": "노칭 진동", **_PROP180}])
_nb180 = next((r.get("node_id") for r in _rb180 if r.get("surface") == "노칭 진동"), None)
_eb180 = sum(len(v) for v in _ends180(_nb180).values())
_rc180 = _q180("QB180C", "노칭 진동을 매 교대 확인한다.", [{"surface": "노칭 진동", **_PROP180}])
show("B180 ⓑ 공정층에 없던 새 관리항목(품질 산문) — 노드는 공정층 · 부모 엣지 하나(좌표 폴백) · 다른 문서가 같은 노드를 말해도 "
     "폴백 엣지가 다시 서지 않는다(부모 있음)",
     _nb180 in open_graph("process").nodes and _eb180 == 1 and sum(len(v) for v in _ends180(_nb180).values()) == 1
     and _kept180(_rc180, "노칭 진동") == 1, f"엣지 {_eb180} → {sum(len(v) for v in _ends180(_nb180).values())}")
_bel180 = {"name": "노칭", "category": "Process", "from": "본문"}
_q180("PB180E", "노칭 공정은 노칭 온도를 관리한다.", [{"surface": "노칭 온도", **_PROP180, "belongs_to": _bel180}], base="PPT01")
_q180("QB180D", "노칭 공정은 노칭 온도를 관리한다.", [{"surface": "노칭 온도", **_PROP180, "belongs_to": _bel180}])
_q180("PB180F", "노칭 공정은 노칭 진동을 관리한다.", [{"surface": "노칭 진동", **_PROP180, "belongs_to": _bel180}], base="PPT01")
_nt180 = next((n for n, x in open_graph("process").nodes.items() if x.get("canonical") == "노칭::노칭 온도"), None)


def _own180(nid, lay):
    return [e for e in open_graph(lay).edges if e["dst"] == nid and e["rel"] == "has_property"]


_sh180 = {d: ((_LG178.read(d) or {}).get("result") or {}).get("같은 엣지 출처만") or [] for d in ("QB180D", "PB180F")}
show("B180 ⓒ 같은 엣지는 그래프 전체에 한 벌 — 공정 산문이 세운 공정층 소속 엣지를 품질 산문이 다시 말하면 품질 문서 출처만 더해지고 "
     "품질층 파일에 그 엣지 0 · 거꾸로 품질층에만 있는 폴백 엣지를 공정 문서가 말하면 그 품질층 엣지에 출처(이 빌드가 연 층으로 저장) · "
     "결과에 「다른 층의 같은 엣지에 출처만 더함」",
     len(_own180(_nt180, "process")) == 1 and not _own180(_nt180, "quality")
     and any(str(p).startswith("QB180D#") for p in _own180(_nt180, "process")[0]["provenance"])
     and not _own180(_nb180, "process") and len(_own180(_nb180, "quality")) == 1
     and any(str(p).startswith("PB180F#") for p in _own180(_nb180, "quality")[0]["provenance"])
     and [x["layer"] for x in _sh180["QB180D"]] == ["process"] and [x["layer"] for x in _sh180["PB180F"]] == ["quality"],
     f"노칭 온도 공정층 {[e['provenance'] for e in _own180(_nt180, 'process')]} · 품질층 {len(_own180(_nt180, 'quality'))} / "
     f"노칭 진동 품질층 {[e['provenance'] for e in _own180(_nb180, 'quality')]} · 공정층 {len(_own180(_nb180, 'process'))}")
import gc as _gc180                                                    # noqa: E402
import weakref as _wr180                                               # noqa: E402
from core.build.build import Builder as _B180                          # noqa: E402
_g180 = open_graph("process")
_w180 = _wr180.ref(_g180)
_B180(_g180, load_config("process"), None, "B180G", "process")
del _g180
_gc180.collect()
show("B180 ② 층 열기는 빌더 · 그래프를 약하게만 쥔다 — 빌더와 그래프를 놓으면 둘 다 풀리고 열기 표에서 빠진다(문서마다 쌓이지 않는다)",
     _w180() is None and not any(k is _w180() for k in _GT180._OPEN.keys()), f"열기 표 {len(_GT180._OPEN)}")
for _d in ("QB180A", "QB180B", "QB180C", "QB180D", "PB180E", "PB180F"):
    (_FX180.EXTRACT_HINTS / f"{_d}.json").unlink(missing_ok=True)
init.init(fresh_=True, all_=True)

# ────────────────────────────────────────────────────────────── B147 ⓑⓒ
print("\n■ B147 ①② 등록된 스키마의 부착 대상 — 재대조 ⚠ · 인입은 멈추지 않는다 · 보류 사유 · 고친 스키마")
import os as _os147                                                   # noqa: E402
import subprocess as _sp147                                           # noqa: E402
from tools import four_way as _FW147                                  # noqa: E402 — 바닥 D의 재료(창작 — 한 자리)
from core.build import ledger as _LG147, reinforce as _RF147, result as _RS147   # noqa: E402
from core.build.heading import _is_coord as _isc147                   # noqa: E402


def _run147(*argv):
    r = _sp147.run([sys.executable, str(ROOT / "run.py"), *argv], capture_output=True, text=True, cwd=str(ROOT),
                   env={**_os147.environ, "USE_MOCK": "1"}, stdin=_sp147.DEVNULL)
    return r.stdout + r.stderr


init.init(fresh_=True, all_=True)
_f147 = _FW147.CPU_SCHEMA["fields"]
_x147 = _FW147.cpu_setup({**_FW147.CPU_SCHEMA, "fields": {**_f147, "규격": {**_f147["규격"], "attach_to_field": "process_ref"}}})
_ob147 = _run147("bootstrap")
_rc147 = [l for dt, ok, l in recheck.run() if dt == _FW147.CPU_DT and not ok]       # doctor [2′]가 부르는 같은 함수
_oi147 = _run147("ingest-file", str(_x147), "--doc-type", _FW147.CPU_DT, "--allow-mock")
_h147 = ((_LG147.read("FWCPU") or {}).get("result") or {}).get("보류") or {}
_msg147 = "'규격'(attribute)의 attach_to_field 'process_ref'는 구조 필드"
show("ⓑ 등록된 위반 스키마 — bootstrap 끝 · 재대조(doctor [2′]) · 인입 사전 점검이 ⚠ 줄(필드 · 붙일 수 있는 선언 필드 · 다음 줄) · "
     "인입은 멈추지 않는다 · 보류 사유는 「개체 열이 아니다」(좌표 미해소 0)",
     # 기대 변경(B148 ⑦ — 다음 줄은 등록 층 · 표본 자리까지 · mock이면 mock 관문 플래그 · 사전 점검도 같은 줄)
     # 기대 변경(B150 ③ — 부착 대상 ⚠의 다음 줄은 스키마만 새 판 `--schema-only`)
     all(_msg147 in o and f"generate {_FW147.CPU_DT} process <표본...> --schema-only --allow-mock" in o
         for o in (_ob147, "\n".join(_rc147), _oi147))
     and "붙일 수 있는 선언 필드: 관리항목" in "\n".join(_rc147)
     and "스키마 재대조 ⚠ (멈추지 않는다)" in _oi147 and _msg147 in _oi147 and "   인입 — record" in _oi147
     and _h147.get(_RS147.ATTACH_NOT_TARGET) == len(_FW147.CPU_ROWS) and _RS147.HOLD_REASONS[2][2] not in _h147,
     f"보류 {_h147} · ⚠ {[l.split(chr(10))[0][:90] for l in _rc147]}")
# B148 ⑦ ⓘ — 재등록 다음 줄을 그대로 쳐서(셸 없이 같은 낱말) 사용법이 아니라 생성 단계로 · 표본은 그 종류 등록 상태의 표본
import shlex as _sh148                                                 # noqa: E402
import shutil as _st148                                                # noqa: E402
_P.ensure(_P.review(_FW147.CPU_DT, "state.json"))
_P.review(_FW147.CPU_DT, "state.json").write_text(json.dumps({"samples": [str(_x147)]}, ensure_ascii=False), encoding="utf-8")
_ln148 = next(p_.split("다음 줄: ", 1)[1].split(" (인입은")[0] for l in recheck.run() if l[0] == _FW147.CPU_DT and not l[1]
              for p_ in l[2].split("\n") if "다음 줄: python" in p_)
# 기대 변경(B150 ③ — 다음 줄은 스키마만 새 판 · 그대로 치면 생성 → 관문(운영 어댑터 + 새 스키마) → 확정까지 · mock 초안 = 고친 스키마)
from cli.register import FIXTURES as _FX150                            # noqa: E402 — 픽스처 뿌리(회귀가 스위트마다 주는 사본)
from core.state import registry as _RG150                              # noqa: E402
_fs150 = _FX150 / "schemas" / f"{_FW147.CPU_DT}.json"
_fs150.write_text(json.dumps(_FW147.CPU_SCHEMA, ensure_ascii=False), encoding="utf-8")
_ad150 = _RG150.at(_RG150.lookup(_FW147.CPU_DT)["adapter"])
_ab150 = _ad150.read_bytes()
_rg148 = _sp147.run(_sh148.split(_ln148), capture_output=True, text=True, cwd=str(ROOT), env={**_os147.environ, "USE_MOCK": "1"},
                    stdin=_sp147.DEVNULL)
_og148 = _rg148.stdout + _rg148.stderr
_hn150 = json.loads(_P.review(_FW147.CPU_DT, "state.json").read_text(encoding="utf-8")).get("harness_out") or ""
_cf150 = _sp147.run([sys.executable, "-m", "cli.register", "confirm", _FW147.CPU_DT, "--by", "B150", "--allow-mock"],
                    capture_output=True, text=True, cwd=str(ROOT), env={**_os147.environ, "USE_MOCK": "1"},
                    stdin=_sp147.DEVNULL)
_rc150 = [l for dt, ok, l in recheck.run() if dt == _FW147.CPU_DT and not ok]
_e150 = _RG150.lookup(_FW147.CPU_DT) or {}
_fs150.unlink()
_st148.rmtree(_P.review(_FW147.CPU_DT), ignore_errors=True)
show("ⓒ 부착 위반 스키마로 등록된 표 종류 — 재대조 ⚠의 다음 줄이 스키마만 새 판(`--schema-only`)이고 그대로 치면 생성 단계 · "
     "관문은 운영 어댑터 + 새 스키마(G4J PASS) · 확정 뒤 어댑터 파일 바이트 그대로 · 판 오름 · 재대조 ⚠ 0",
     f"generate {_FW147.CPU_DT} process {_sh148.quote(str(_x147))} --schema-only" in _ln148
     and f"■ ① 생성 — {_FW147.CPU_DT} (층 process · 표본 1부)" in _og148 and "[사용법]" not in _og148
     and "[PASS] G4J" in _hn150 and _cf150.returncode == 0 and _ad150.read_bytes() == _ab150
     and _e150.get("revision") == 1 and not _rc150,
     f"{_ln148[:90]} → 관문 G4J {'[PASS] G4J' in _hn150} · 확정 rc {_cf150.returncode} · 어댑터 같음 "
     f"{_ad150.read_bytes() == _ab150} · 판 {_e150.get('revision')} · ⚠ {[l[:80] for l in _rc150]} · "
     f"{(_og148 + _cf150.stdout + _cf150.stderr)[-300:] if _cf150.returncode else ''}")
_FW147.cpu_setup()                                                    # 고친 스키마(개체 열) — 같은 표를 다시
_oi147b = _run147("ingest-file", str(_x147), "--doc-type", _FW147.CPU_DT, "--allow-mock")
_rows147 = (_LG147.read("FWCPU") or {}).get("rows") or []
_nodes147, _ends147 = _RF147._index({lay: open_graph(lay) for lay in ("process", "quality")})
_ch147 = store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}
_cof147 = {c.get("source_locator"): (cid, c) for cid, c in _ch147.items() if c.get("doc_id") == "FWCPU"}
_items147 = {r["node_id"]: r["locator"] for r in _rows147 if r.get("role") == "entity" and r.get("node_id")}
_att147 = [r for r in _rows147 if r.get("role") in ("attribute", "content")]
_tg147 = {nid for _r, nid, _w in _RF147.targets(_rows147, _nodes147, _ends147, _cof147)}
show("ⓒ 고친 스키마 — 값이 관리항목에 붙는다(부착 보류 0) · 그 관리항목들은 좌표에만 붙었어도 스키마 엣지(문서의 진술)라 연결 보강 "
     "대상이 아니다",
     "   인입 — record" in _oi147b and _att147 and all(r.get("verdict") == "attached" for r in _att147)
     and _items147 and all(loc in _cof147 for loc in _items147.values())
     and all(_ends147.get(n) and all(_isc147(_nodes147[o][1]) for o in _ends147[n]) for n in _items147)
     and not set(_items147) & _tg147,
     f"부착 {len(_att147)} · 보류 {[r['field'] for r in _att147 if r.get('verdict') != 'attached']} · 관리항목 "
     f"{len(_items147)} · 보강 대상 {len(set(_items147) & _tg147)}")
init.init(fresh_=True, all_=True)

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
init.init(fresh_=True, all_=True)

done()
