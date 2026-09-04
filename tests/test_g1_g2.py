# -*- coding: utf-8 -*-
"""G1+G2 완료판정 — 정지점 2 프롬프트의 어서션을 실행 가능한 검사로.

  st  : graph.py 밖 직접 접근 0 (grep 실증) + 계기판 7·8 출력
  n1  : S6(occ 충돌) + 멱등성 2종(2회 인입 동일 · 조각 순서 셔플 동일)
  n2  : S5(doc_hash 차단)
  n10 : **seed v3.2 골격**(Process 46 · part_of 45 · precedes 22 · polarity≠none 16
        · mirrors 쌍 8) + 파생 대표 흐름 출력 + registry에 builtin 층 1개만 존재
        — 구 기대값(8·7·6)은 골격 두 축 분리(D-42) 전 수치다.

사용: python tests/test_g1_g2.py
"""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import init, gate, store                              # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph   # noqa: E402
from core.ids import is_ulid                              # noqa: E402
from core.ingest import ingest                            # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / "parsed" / name).read_text(encoding="utf-8"))


def canon(g):
    return {n["canonical"] for n in g.nodes.values()}


def reset():
    """**깨끗한 그래프에서 전체 재빌드.** v3.2는 canonical 체계 자체가 바뀌었으므로
    (sub 이하 부모 경로 접두 · 인스턴스 `{개념}::{축값}`) 기존 그래프 위에 다시 심으면
    옛 골격이 살아남는다 — 멱등성(D-41)이 막는 것은 "같은 canonical의 재발급"이지
    "canonical 체계 변경"이 아니다. 기대값 대조는 반드시 이 경로로 한다.
    """
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    return bootstrap("process", echo=False)


# ============================================================ st
print("\n■ st — 저장 계층 경계 (틀 §4B-A8 · 카드 B6)")

# 층 그래프 파일을 아는 코드가 core/graph.py 밖에 있는가. 리뷰 규칙의 기계 실증이다.
# 패턴을 조각으로 만드는 이유: 이 파일 자신이 검사에 걸리지 않게 하기 위해서다.
PAT = re.compile("graph" + r"\." + "json")
hits = []
for p in ROOT.rglob("*.py"):
    if any(x in p.parts for x in (".venv", "__pycache__", "mock")):
        continue
    if p == ROOT / "core" / "graph.py":
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if PAT.search(line) and not line.lstrip().startswith("#"):
            hits.append(f"{p.relative_to(ROOT)}:{i}")
show("core/graph.py 밖에서 층 그래프 파일을 아는 코드 0지점", not hits, str(hits))

# **cli/에 sys.path 조작이 없는가** (문서 7 §7.1 패키지화).
# 조작으로 붙이면 CLI가 실행 위치에 의존해 "subprocess로 호출 가능한 CLI+파일"이
# 호출부의 작업 디렉터리에 따라 깨진다. 실행 규약은 `python -m cli.{진입점}`이다.
PATH_HACK = "sys" + r"\.path\.insert"
import re as _re
_pat = _re.compile(PATH_HACK)
cli_hits = [f"{p.relative_to(ROOT)}:{i}"
            for p in sorted((ROOT / "cli").glob("*.py"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _pat.search(line) and not line.lstrip().startswith("#")]
show("cli/ 8종에 sys.path 조작 0지점 — 실행은 python -m cli.{진입점}",
     not cli_hits, str(cli_hits))

# **원자적 쓰기가 배선돼 있는가** (문서 7 §7.1 저장 계층).
# 직접 덮어쓰면 build가 쓰기 도중 죽었을 때 진실이 반쯤 쓰인 채 남는다 —
# data/는 백업 대상이지 재생성 대상이 아니라 복구가 불가능하다.
_src = (ROOT / "core" / "store.py").read_text(encoding="utf-8")
_gsrc = (ROOT / "core" / "graph.py").read_text(encoding="utf-8")
show("저장 쓰기가 tmp+os.replace·flock 경유다 (직접 덮어쓰기 0)",
     "os.replace" in _src and "flock" in _src
     and "atomic_write_bytes" in _gsrc
     and "write_bytes(_dumps(" not in _gsrc)

# **빈 상태의 형태가 §7.2 말미와 같은가** — 클린의 정의가 하나여야
# 회귀 규약(§7.5-7)과 완료판정 4번이 같은 바닥 위에 선다.
from core import init as _init                                # noqa: E402
_init.init(fresh_=True)
_want = {store.CHUNKS: {"chunks": {}, "describes": []},
         store.DICTIONARY: {}, store.QUEUE: []}
_got = {n: store.read(n, "없음") for n in _want}
show("run.py init --fresh 의 빈 상태 형태가 명세와 일치 (§7.2)",
     _got == _want, str(_got))

# **클린이 승인 기록을 지우지 않는가** (§7.8 — 사람 판단 기록은 재생성되지 않는다).
# `review/{doc_type}/approval.json`이 승인의 물리 정본이라, 클린이 그것을 지우면
# 사내에서 `init --fresh` 한 번에 승인 이력이 사라진다(실증된 결함).
from core import init as _init2                                 # noqa: E402
_probe = ROOT / "review" / "_clean_probe"
_probe.mkdir(parents=True, exist_ok=True)
(_probe / "approval.json").write_text('{"approved_by": "시험자"}', encoding="utf-8")
_init2.init(fresh_=True)
_kept = (_probe / "approval.json").exists()
show("run.py init --fresh 가 review/의 승인 기록을 지우지 않는다 (§7.8)",
     _kept and "review" not in _init2.WIPE, str(_init2.WIPE))
import shutil as _sh
_sh.rmtree(_probe, ignore_errors=True)

# **core 접근 경계 3종이 관문으로 서 있는가** (문서 7 §7.1).
# 자산에 파일과 의미론만 있고 관문이 없으면 호출부마다 제 규칙으로 붙는다 —
# 실제로 사전 접근이 5곳으로 흩어져 있었고 provenance 필수는 한 곳만 지켰다.
_DICT_KEY = "store" + r"\.(?:read|write)\(store\.DICTIONARY"
import re as _re2
_dp = _re2.compile(_DICT_KEY)
_bypass = [f"{p.relative_to(ROOT)}:{i}"
           for p in sorted(list((ROOT / "core").glob("*.py")) + list((ROOT / "cli").glob("*.py")))
           if p.name != "dictionary.py"
           for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
           if _dp.search(line) and not line.lstrip().startswith("#")]
show("core/dictionary.py 밖에서 사전을 직접 여는 코드 0지점", not _bypass, str(_bypass))

from core.dictionary import Dictionary                          # noqa: E402
_d = Dictionary()
try:
    _d.register("표기", "N1", provenance=None)
    _prov_forced = False
except ValueError:
    _prov_forced = True
show("사전 등재의 provenance 필수가 관문에서 강제된다 (문서 1 G2)", _prov_forced)

from core import matcher as _M                                  # noqa: E402
show("matcher가 match(surface, candidates, category) 계약을 갖는다 (§7.1)",
     all(hasattr(_M, f) for f in ("match", "candidates", "resolve"))
     and list(_M.match.__code__.co_varnames[:3]) == ["surface", "candidates", "category"])
_v = _M.match("가", [{"id": "N9", "canonical": "가", "aliases": [],
                      "category": "Unit", "exact": False}], "Unit")
show("판정 반환이 {type, matched_id, confidence} 3키다 (문서 4 §4.3-6)",
     set(_v) == {"type", "matched_id", "confidence"} and _v["matched_id"] == "N9", str(_v))
show("카테고리 불일치는 후보에서 제외된다 — 판정이 재확인한다 (규약 3)",
     _M.match("가", [{"id": "N9", "canonical": "가", "aliases": [],
                      "category": "Property", "exact": False}], "Unit")["type"] == _M.NEW)

import core.skeleton as _SK                                     # noqa: E402
show("골격 심기가 core/skeleton.py에 산다 (§7.1 — 파생이 loader에 섞이지 않는다)",
     all(hasattr(_SK, f) for f in ("plant", "_plant_tree", "_link_seed_mirrors"))
     and "_TreeParser" in dir(_SK))
_bsrc = (ROOT / "core" / "bootstrap.py").read_text(encoding="utf-8")
show("bootstrap에 트리 파싱·모양 분기가 남아 있지 않다",
     "_TreeParser" not in _bsrc and "TYPE_FLAT" not in _bsrc)

from core import ops as _OPS                                    # noqa: E402
show("I2 병합 후보가 판정 경유로 제안된다 (문서 4 §4.3 재사용 3지점 중 하나)",
     hasattr(_OPS, "merge_targets"))

# ============================================================ 저장 레코드 스키마
print("\n■ 저장 레코드 스키마 — 문서 7 §7.2 전문 대조")
# 이 절이 이번 개정에서 **형태 전체**를 못박았다. 직렬화에서 필드가 떨어지면
# mirrors 페어링·순서 파생·process_group 파생이 전부 canonical 문자열 파싱으로
# 되돌아가고, 그것은 문서 4 §4.5와 문서 1 C10이 정면으로 금지한 것이다.
import subprocess as _sp                                       # noqa: E402
_sp.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
        capture_output=True, cwd=str(ROOT))
_sp.run([sys.executable, str(ROOT / "run.py"), "all"], capture_output=True, cwd=str(ROOT))

_g = open_graph("process")
_NODE_MIN = {"id", "canonical", "category", "layer", "status",
             "attrs", "aliases", "provenance"}
show("노드 레코드가 명세 최소 집합을 전부 보유 (§7.2)",
     all(_NODE_MIN <= set(n) for n in _g.nodes.values()))
_POL = {"cathode", "anode", "none", "unbound"}
show("polarity가 **최상위 파생 필드**이고 닫힌 4값이다 (attrs 우회 금지)",
     all(n.get("polarity") in _POL for n in _g.nodes.values())
     and not any("polarity" in (n.get("attrs") or {}) for n in _g.nodes.values()))
show("tier가 최상위이고 닫힌 3값 (골격 유래 한정)",
     all(n.get("tier") in (None, "main", "sub", "detail") for n in _g.nodes.values())
     and any(n.get("tier") for n in _g.nodes.values()))
show("alias 항목이 {surface, provenance} 형태다 (문자열 배열 금지 — G2)",
     all(isinstance(a, dict) and {"surface", "provenance"} <= set(a)
         for n in _g.nodes.values() for a in n["aliases"]))
show("엣지 레코드가 {src, rel, dst, status, provenance} 5키다",
     all({"src", "rel", "dst", "status", "provenance"} <= set(e) for e in _g.edges))

_ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})["chunks"]
_CHUNK = {"doc_id", "text", "section", "source_locator", "parsed_at",
          "meta", "adapter_version", "linked"}
show("청크 레코드가 명세 8필드를 보유 (parsed_at 포함 — §7.2)",
     _ch and all(_CHUNK <= set(c) for c in _ch.values()),
     str(sorted(_CHUNK - set(next(iter(_ch.values()))))) if _ch else "청크 0")

# **resolution** — 사람의 판단이 기록된 항목의 표시. 회수가 그것을 보존한다.
_n = store.resolve_item("auto_node", lambda p: True, actor="시험자",
                        decision="confirmed", at="2026-01-05T00:00:00")
_q = store.read(store.QUEUE, [])
_marked = [x for x in _q if x.get("resolution")]
show("큐 항목에 resolution을 기록할 수 있다 (§7.2 · 4요소)",
     _n > 0 and all({"actor", "at", "decision", "note"} == set(x["resolution"])
                    for x in _marked), f"{_n}건")
# 회수가 그것을 보존하는가 — 판단이 기록된 항목은 재인입에 지워지지 않는다.
from core.ingest import withdraw                              # noqa: E402
_doc = next((x["doc_id"] for x in _marked if x.get("doc_id")), None)
_before = len([x for x in _q if x.get("doc_id") == _doc and x.get("resolution")])
withdraw({"doc_id": _doc, "source_path": None}, _doc)
_after = len([x for x in store.read(store.QUEUE, [])
              if x.get("doc_id") == _doc and x.get("resolution")])
show("재인입 회수가 **사람의 판단이 기록된 항목**을 보존한다 (§4.8-2③ · H6)",
     _before > 0 and _after == _before, f"{_before} → {_after}")

# ============================================================ 진입점 계약
print("\n■ 진입점 계약 — 문서 7 §7.1 「플랫폼이 subprocess로 부르는 이름은 계약이다」")
# 같은 기능을 다른 이름으로 제공하지 않는다 — 플랫폼↔파이프라인 결합이 "CLI+파일"이라
# **명령 이름이 계약의 일부**인데, 일반형만 두면 기능은 있어도 외부 스크립트와
# 호환되지 않는다.
def _rc(*argv):
    return _sp.run([sys.executable, *argv], capture_output=True, text=True,
                   cwd=str(ROOT))

_sp.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
        capture_output=True, cwd=str(ROOT))
_sp.run([sys.executable, str(ROOT / "run.py"), "bootstrap"],
        capture_output=True, cwd=str(ROOT))

show("구축 `python run.py build <parsed.json …>` (§7.1)",
     _rc(str(ROOT / "run.py"), "build", "--allow-mock",     # 회귀는 관문 비대상(B48)
         str(ROOT / "tests/fixtures/parsed/CP01.json")).returncode == 0)
show("추출 `python -m cli.extract <parsed.json>` (§7.1)",
     _rc("-m", "cli.extract", str(ROOT / "tests/fixtures/parsed/PPT01.json")).returncode == 0)
show("지문 스캔 `python -m cli.scan <문서>` (§7.1)",
     _rc("-m", "cli.scan", str(ROOT / "tests/fixtures/raw/CP01.xlsx")).returncode == 0)
show("플랫폼 관측 `python -m cli.platform ops` · `doctypes` (§7.1)",
     _rc("-m", "cli.platform", "ops").returncode == 0
     and _rc("-m", "cli.platform", "doctypes").returncode == 0)
show("I축 전 연산에 --actor 필수 (§7.1 · 문서 4 §4.7-4)",
     _rc("-m", "cli.ops", "rename", "--layer", "process", "--node", "x",
         "--canonical", "y").returncode != 0)

_parse = _rc("-m", "cli.parse", "run", "--allow-mock",   # 회귀는 관문 비대상(B48)
             str(ROOT / "tests/fixtures/adapters/cp.py"), "CP01",
             str(ROOT / "tests/fixtures/raw/CP01.xlsx"))
show("파싱의 운영 산출 자리가 parsed/{doc_id}.json 이다 (§7.8 — 파일 존재 = 파싱 완료)",
     _parse.returncode == 0 and (ROOT / "parsed" / "CP01.json").exists())

# 클린 범위 — §7.6-4가 이번 개정에서 확정했다.
from core import init as _init3                                 # noqa: E402
show("클린 범위가 parsed/·extract/를 포함한다 (체크포인트 잔존 = 순서 의존)",
     "parsed" in _init3.WIPE and "extract" in _init3.WIPE, str(_init3.WIPE))
show("클린이 data/doc_types.json을 보존한다 (승인 1회의 등재 — 재생성 불가)",
     "doc_types.json" in _init3.KEEP_IN_DATA)
_dt = ROOT / "data" / "doc_types.json"
_dt.parent.mkdir(parents=True, exist_ok=True)
_dt.write_text('{"_probe": {"doc_type": "_probe"}}', encoding="utf-8")
_init3.init(fresh_=True)
show("실측 — init --fresh 후에도 doc_types.json이 남는다",
     _dt.exists() and "_probe" in _dt.read_text(encoding="utf-8"))
show("빈 상태에 층 등록부·문서 대장도 든다 (§7.2 빈 상태 불릿)",
     store.REGISTRY in _init3.EMPTY and store.DOC_REGISTRY in _init3.EMPTY)
# **탐침을 걷는다** — `doc_types.json`은 이제 클린이 보존하므로, 남기면 뒤의
# 등록부 조회가 필드 없는 항목을 만나 깨진다(실측).
_dt.unlink(missing_ok=True)
_init3.init(fresh_=True)

# ============================================================ 2B 감사 반영
print("\n■ 감사 확인 항목 — 명세 실물로 재확인한 것 (2B 감사 37건 중)")
# 병합 툼스톤은 `merged_into`·`target`·`at` 셋이다(문서 7 §7.2 노드 레코드) —
# 리다이렉트 포인터를 키 하나로만 두면 생존자를 찾는 코드가 kind별로 다른 키를 본다.
_src_ops = (ROOT / "core" / "ops.py").read_text(encoding="utf-8")
show("병합 툼스톤이 target 키를 함께 갖는다 (§7.2)", '"target": keep["id"]' in _src_ops)
# **등급 어휘**에서만 본다 — `registered`가 왜 금지인지를 설명하는 주석은 대상이
# 아니다(그 문장이 사라지면 다음 사람이 같은 실수를 되풀이한다).
_grade_lines = [l for l in _src_ops.splitlines()
                if "registered" in l and (">" in l or "STATUS_RANK" in l)]
show("I2 등급 어휘에 `registered`를 쓰지 않는다 (§4.7-4)",
     not _grade_lines, str(_grade_lines[:2]))

# 큐 항목의 `created`는 **실제 시각**이다 — 명세가 멱등 판정에서 그것을 빼라고
# 못박았으므로(§7.6-4) 시각을 상수로 죽여 멱등을 살 이유가 없다.
_q0 = store.read(store.QUEUE, [])
store.enqueue("auto_node", "created 실측", "PROBE", {"probe": 1})
_it = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == "PROBE"]
show("큐 항목의 created가 실제 시각이다 (상수 위조 아님 — §7.6-4)",
     _it and _it[0]["created"].startswith("20") and _it[0]["created"] != "2026-01-05T00:00:00",
     _it[0]["created"] if _it else "")
store.drop("auto_node", lambda p: p.get("probe") == 1)

# 판정 임계는 층 config가 소유한다(문서 3 §3.1 · 문서 7 §7.1 관리 자산의 원칙).
from core import matcher as _M2                                 # noqa: E402
show("판정 임계를 층 config에서 읽는다 (코드 상수는 폴백)",
     _M2.threshold({"match_threshold": 0.9}) == 0.9
     and _M2.threshold({}) == _M2.THRESHOLD)

# 확장은 프론티어 전파다 — `recursive: false`는 **같은 관계**를 연달아 재추적하지
# 않는다는 뜻일 뿐, 다른 관계로 도달한 노드에의 적용을 막지 않는다(문서 5 §5.1-5).
# 위 클린이 그래프를 비웠으므로 다시 세운다. **2홉의 도착점(Property)은 골격이
# 아니라 문서가 만든다** — 골격만 심으면 확장할 인자가 0이다.
_sp.run([sys.executable, str(ROOT / "run.py"), "all"],
        capture_output=True, cwd=str(ROOT))
_g5 = open_graph("process")
_cfg5 = load_config("process")
_proc = next(i for i, n in _g5.nodes.items() if n["canonical"] == "노칭")
_out = _g5.neighbors([_proc], _cfg5["query_traverse"])
_props = [i for i in _out if _g5.get(i)["category"] == "Property"]
show("2홉이 성립한다 — 공정→(part_of 하향)→설비→(has_property)→인자 (§5.1-5)",
     len(_props) >= 3, f"Property {len(_props)}건")
_dt.unlink(missing_ok=True)

g, m, _, flow = reset()
show("계기판 7 (graph 저장 크기) 출력", "gauge7_graph_bytes" in m,
     f"{m['gauge7_graph_mb']}MB")
show("계기판 8 (build 소요) 출력", "gauge8_build_seconds" in m,
     f"{m['gauge8_build_seconds']}s")
show("알람선 미초과 (200MB / 30초)",
     not m["gauge7_over_alarm"] and not m["gauge8_over_alarm"])
show("직렬화 orjson (미설치 시 표준 json 폴백)", m["serializer"] in ("orjson", "json"),
     m["serializer"])

# ============================================================ n10
print("\n■ n10 — 부트스트랩 seed·config (골격 seed v3.2 · 두 축 분리)")
rels = Counter(e["rel"] for e in g.edges)
POL = [n for n in g.nodes.values() if n.get("polarity") not in (None, "none")]
show("Process 46노드",
     sum(1 for n in g.nodes.values() if n["category"] == "Process") == 46,
     str(len(g.nodes)))
show("part_of 45 (구조 — 루트 제외 전 노드)", rels["part_of"] == 45, str(rels["part_of"]))
show("precedes 22 (지식 — 참여 항목만 건너 이음)", rels["precedes"] == 22,
     str(rels["precedes"]))
show("polarity ≠ none 16 (인스턴스 4 + @split 인스턴스 12)", len(POL) == 16,
     str(len(POL)))
show("mirrors 쌍 8 (노칭 1 + 탭용접 1 + @split 6)", rels["mirrors"] == 16,
     f"엣지 {rels['mirrors']} → 쌍 {rels['mirrors'] // 2}")
show("골격 노드 status = seed",
     {n["status"] for n in g.nodes.values()} == {"seed"})
show("골격 provenance = ['seed']",
     all(n["provenance"] == ["seed"] for n in g.nodes.values()))

# tier·canonical — loader 파생이며 수기 접두가 아니다 (A11-7 · D-47)
tiers = Counter(n["tier"] for n in g.nodes.values())
show("tier가 깊이에서 파생 (main 1 · sub 8 · detail 37)",
     tiers == Counter({"main": 1, "sub": 8, "detail": 37}), str(dict(tiers)))
show("main·sub canonical은 이름 그대로 / detail은 부모 경로 접두",
     {"조립", "노칭", "탭용접"} <= canon(g)
     and "탭용접::pre용접" in canon(g) and "패키징::사이드 실링" in canon(g))
show("인스턴스 canonical = {개념}::{축값} — 쌍 유무 무관 균일",
     {"노칭::cathode", "노칭::anode", "탭용접::pre용접::cathode"} <= canon(g))
show("극성 인스턴스 간 precedes 0건 (구조적 미생성 — J12)",
     not [e for e in g.edges if e["rel"] == "precedes"
          and (g.get(e["src"]).get("polarity") != "none"
               or g.get(e["dst"]).get("polarity") != "none")])

# seed ALIASES → 사전 등재 (장부는 dictionary.json 하나 — 카드 B4)
D = store.read(store.DICTIONARY, {})
show("seed ALIASES가 사전에 등재 (provenance=['seed'])",
     D.get("notching") and D.get("전해액주입")
     and all(a["provenance"] == ["seed"]
             for n in g.nodes.values() for a in n["aliases"]))
show("인스턴스 auto alias 2종 ('{축값} {이름}' · '{라벨} {이름}')",
     D.get("cathode 탭용접") and D.get("양극 탭용접") and D.get("음극 노칭"))
show("짧은 이름 auto alias (detail 노드의 접두 없는 조회)",
     D.get("사이드 실링") and D.get("적층") and D.get("pre용접"))
show("모호한 짧은 이름은 미등재 ('비전검사' — 접두 키가 대신한다)",
     "비전검사" not in D and D.get("노칭 검사") and D.get("정렬 검사"))

# 파생 대표 흐름 출력 — 순서 오선언의 유일한 안전망 (A11-2 · M9 계보)
show("로드 시 파생 대표 흐름 출력 (레벨 5줄)", len(flow) == 5, f"{len(flow)}줄")
show("무주장 항목이 흐름에서 빠지고 별도 표기됨 (@unordered)",
     any("무주장" in ln and "전극 시트 공급" in ln for ln in flow)
     and not any("전극 시트 공급 →" in ln for ln in flow))

# ── seed는 후보가 아니라 선언이다 (틀 §4B-A3 경로 ①) ────────────────────────
# 골격이 게이트를 지나지 않는 것은 **설계**이며, 그 대가로 패턴표에 골격 관계를
# 넣지 않는다. 넣으면 추출 경로(③)가 골격을 개정할 수 있게 된다(A5 발명 금지 ③).
# 아래 셋은 그 균형을 **우연이 아니라 보장으로** 잠근다.
print("\n■ seed 경로 ① — 선언이지 후보가 아니다 (게이트 비경유의 잠금)")
CFG = load_config("process")
SKEL_REL = {CFG["skeleton"]["relations"]["child"],
            CFG["skeleton"]["relations"]["sibling"],
            (CFG.get("mirrors") or {}).get("relation")}
SKEL_CAT = CFG["skeleton"]["category"]
show("① 패턴표에 골격 관계가 없다 (추출이 골격을 개정할 수 없다)",
     not [p for p in CFG["relation_patterns"]
          if p["src"] == SKEL_CAT and p["dst"] == SKEL_CAT and p["rel"] in SKEL_REL],
     str([f"{p['src']} -{p['rel']}-> {p['dst']}" for p in CFG["relation_patterns"]
          if p["src"] == SKEL_CAT and p["dst"] == SKEL_CAT]))
# 표에 없다는 것만으로는 부족하다 — 실제로 어느 경로로도 커밋되지 않아야 한다.
# 특히 경로 ②(스키마 edges 선언)는 동종 쌍도 무비용 통과하므로, 패턴이 하나라도
# 남아 있으면 **정형 문서가 골격 흐름을 개정**한다(A11-2 "순서의 출처는 seed 하나뿐").
_paths = (gate.PATH_SCHEMA, gate.PATH_EXTRACT, gate.PATH_AUTO)
_verdicts = {f"{r}/{p}": gate.judge(SKEL_CAT, r, SKEL_CAT, CFG, p)[0]
             for r in SKEL_REL if r for p in _paths}
show("② 문서·규칙 경로(②③④) 어느 쪽도 골격 관계를 커밋하지 못한다",
     gate.COMMIT not in _verdicts.values(), str(_verdicts))
show("③ loader가 게이트를 부르지 않는다 (경유 자체가 없다)",
     "gate" not in (ROOT / "core" / "bootstrap.py").read_text(encoding="utf-8"))
show("골격 엣지 status = seed · 게이트 거부 로그 0건",
     {e["status"] for e in g.edges} == {"seed"}
     and not store.path(store.GATE_REJECTS).exists())

reg = store.read(store.REGISTRY, {})
show("registry에 builtin 층 1개만 존재",
     len(reg) == 1 and list(reg.values())[0]["status"] == "builtin", str(list(reg)))
show("의미 축 id가 전부 ULID (id_seq.json 없음)",
     all(is_ulid(i) for i in g.nodes) and not (store.DATA / "id_seq.json").exists())

# ============================================================ n1
print("\n■ n1 — 근거 축 id (내용 계산)")
reset()
r3 = ingest(load("PPT03.json"))
c = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
m23 = [k for k, v in c.items() if v["source_locator"] in ("PPT03-C002", "PPT03-C003")]
show("S6 — 동일 (section, text) 2건의 chunk_id가 서로 다름 (occ 0·1)",
     len(set(m23)) == 2, str(sorted(m23)))
show("S6 — 충돌 결함 로그 0건", not r3.defects and
     not (store.DATA / store.DEFECTS).exists())
show("chunk_id가 doc_id 스코프 + 12자 해시",
     all(re.fullmatch(r"PPT03:[0-9a-f]{12}", k) for k in m23), str(m23[:1]))

# 멱등성 ① — 같은 문서 2회 인입
reset()
a = ingest(load("PPT01.json"))
snap1 = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
b = ingest(load("PPT01.json"))
snap2 = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
show("멱등성 ① 같은 문서 2회 인입 — id 집합 동일", a.ids == b.ids)
show("멱등성 ① 같은 문서 2회 인입 — 청크 저장 동일", snap1 == snap2)

# 멱등성 ② — payload 조각 순서 셔플
reset()
env = load("PPT01.json")
base = ingest(env)
snap_base = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
ok_ids, ok_store = True, True
for seed in (1, 2, 3):
    reset()
    sh = json.loads(json.dumps(env))
    random.Random(seed).shuffle(sh["chunks"])
    s = ingest(sh)
    ok_ids &= (s.ids == base.ids)
    ok_store &= (json.dumps(store.read(store.CHUNKS, {}),
                            ensure_ascii=False, sort_keys=True) == snap_base)
show("멱등성 ② 조각 순서 셔플 3회 — id 집합 동일", ok_ids)
show("멱등성 ② 조각 순서 셔플 3회 — 청크 저장 동일", ok_store)

# 표 문서: record_id + content 필드별 청크(D8)
reset()
cp = ingest(load("CP01.json"))
fm = ingest(load("PFMEA01.json"))
show("CP01 record 12건", len(cp.record_ids) == 12, str(len(cp.record_ids)))
show("PFMEA01 record 13건", len(fm.record_ids) == 13, str(len(fm.record_ids)))
show("record_id 전부 유일 (충돌 접미 없이)",
     len(set(cp.record_ids)) == 12 and len(set(fm.record_ids)) == 13)
cc = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
content = [k for k in cc if "-" in k.split(":", 1)[1]]
show("table content 청크 id = {record_id}-{필드명} (D8)",
     content and all(re.fullmatch(r"[A-Z0-9]+:[0-9a-f]{12}-.+", k) for k in content),
     f"{len(content)}건")
show("청크에 adapter_version 복사됨 (봉투 1회 → 청크, 카드 C9)",
     all(v["adapter_version"] == "mock-1.0" for v in cc.values()))
show("링킹 0건 청크도 보존 (linked=false, 카드 C6)",
     all(v["linked"] is False for v in cc.values()))

# ============================================================ n2
print("\n■ n2 — doc_hash 중복 차단")
reset()
ingest(load("CP01.json"))
before = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
held = ingest(load("CP01B.json"))
after = json.dumps(store.read(store.CHUNKS, {}), ensure_ascii=False, sort_keys=True)
q = [x for x in store.read(store.QUEUE, []) if x["kind"] == "duplicate_doc_hold"]
show("S5 — 내용 같고 doc_id 다른 문서는 인입 보류", held.status == "held", held.reason)
show("S5 — duplicate_doc_hold 큐 1건", len(q) == 1, str(len(q)))
show("S5 — 큐에 파일명·기존 doc_id 동봉",
     q and q[0]["payload"]["existing_doc_id"] == "CP01"
     and q[0]["payload"]["source_path"] == "CP_사본.xlsx")
show("S5 — 보류 문서는 청크에 아무것도 쓰지 않음", before == after)
same = ingest(load("CP01.json"))
show("S5 대조 — 같은 doc_id 재인입은 통과(정상 경로)", same.status == "ok")

# ============================================================ gs
print("\n■ gs — GraphStore 전용 (core/graph.py — 구조 진단 3순위: 직접 겨냥한 회귀 0)")
from core.graph import GraphStore, STATUS_DELETED, ALARM_BYTES     # noqa: E402
import tempfile                                                    # noqa: E402
_td = Path(tempfile.mkdtemp(prefix="gs_"))
gs = GraphStore.for_layer("t", data_dir=_td)
show("for_layer — 경로를 밖에 내주지 않고 exists로 답한다 (B6)", gs.exists() is False)
n1 = gs.add_node("A", "Process", "seed", tier="root")
n2 = gs.add_node("B", "Unit", "auto", attrs={"k": {"value": 1}}, aliases=["b"],
                 provenance=["p1"])
n3 = gs.add_node("C", "Property", "auto")
show("add_node — id는 ULID, 발급 후 노드에 박힌다 (P4)",
     is_ulid(n1) and gs.get(n1)["id"] == n1 and n1 != n2)
show("add_node — 기본값(attrs {} · aliases [] · provenance []) + 파생 필드 병합",
     gs.get(n1)["attrs"] == {} and gs.get(n1)["aliases"] == []
     and gs.get(n1)["provenance"] == [] and gs.get(n1)["tier"] == "root"
     and gs.get(n1)["layer"] == "t" and gs.get(n2)["aliases"] == ["b"])
show("add_edge — 첫 삽입 True · 같은 (src,rel,dst) 재삽입 False",
     gs.add_edge(n1, "part_of", n2, "auto", ["p1"]) is True
     and gs.add_edge(n1, "part_of", n2, "auto", ["p2"]) is False)
show("add_edge — 중복 엣지는 provenance만 합집합",
     len(gs.edges) == 1 and gs.edges[0]["provenance"] == ["p1", "p2"])
gs.add_edge(n2, "has_property", n3, "auto")
gs.add_edge(n3, "precedes", n1, "auto")          # 순환 — neighbors가 멈춰야 한다
show("get — 없는 id는 None", gs.get("없음") is None)
_spec = {"part_of": {"x": {"direction": "out", "recursive": False}},
         "has_property": {"y": {"direction": "out", "recursive": False}}}
show("neighbors — 비재귀 관계도 **다른 관계로 도달한 노드**에는 적용된다 (2홉, 문서 5 §5.1-5)",
     gs.neighbors([n1], _spec) == {n1, n2, n3})
show("neighbors — direction=in 은 역방향만",
     gs.neighbors([n2], {"part_of": {"x": {"direction": "in"}}}) == {n1, n2})
show("neighbors — 순환 그래프(C→A)에서 멈춘다 (방문 집합)",
     gs.neighbors([n1], {"part_of": {"x": {"direction": "both", "recursive": True}},
                         "has_property": {"y": {"direction": "both", "recursive": True}},
                         "precedes": {"z": {"direction": "both", "recursive": True}}})
     == {n1, n2, n3})
gs.build_begin()
m = gs.build_end()
show("build_end — 계기판 7·8 (bytes = 실제 파일 크기 · 알람선 미달)",
     m["gauge7_graph_bytes"] == gs._path.stat().st_size and m["gauge7_over_alarm"] is False
     and m["gauge8_over_alarm"] is False and m["nodes"] == 3 and m["edges"] == 3
     and ALARM_BYTES > m["gauge7_graph_bytes"])
gs2 = GraphStore.for_layer("t", data_dir=_td).load()
show("save → load 왕복 — 노드·엣지 동일", gs2.nodes == gs.nodes and gs2.edges == gs.edges
     and gs2.exists() is True)
gs2.edges[0]["status"] = STATUS_DELETED
gs2.save()
gs3 = GraphStore.for_layer("t", data_dir=_td).load()
show("툼스톤 — 사람이 지운 (src,rel,dst)는 재인입이 되살리지 못한다 (명세 §5.5-3)",
     gs3.add_edge(n1, "part_of", n2, "auto") is False
     and (n1, "part_of", n2) in gs3._tombstones)
show("neighbors — 삭제된 엣지는 전파에서 제외", gs3.neighbors([n1], _spec) == {n1})
shutil.rmtree(_td, ignore_errors=True)

# ============================================================
print("\n" + "=" * 62)
print("전체 결과:", "PASS — G1+G2 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
