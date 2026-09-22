# -*- coding: utf-8 -*-
"""G6 ⑧ 좌표 층의 **이름 해방** — 폴더가 `equipment`여도 전 구간이 같다 (B85 ③).

사내가 골격 층을 설비층(`equipment`)으로 세우자 좌표가 **전부 목록 밖**이 됐다 —
코드가 폴더 이름 `process`를 일곱 자리에 박고 있었기 때문이다(실측 2026-09-22).
좌표 층은 **`Process` 카테고리를 선언한 층**이지 폴더 이름이 아니다.

**이름을 바꾼 루트에서 전 구간을 돌려 대조한다**: 레포를 임시 자리에 복사하고
`layers/process/` → `layers/equipment/`(config의 `layer` 키만) → `init --fresh` →
`bootstrap` → 인입 셋(공정층 표 · 품질층 표 · CSV) → 질의 → `doctor --quick`.
canonical·엣지·큐가 이름 `process`일 때와 **같아야 한다**(층 이름만 다른 그래프).

`USE_MOCK=1`의 상태 루트는 **레포 옆**이다(`ROOT/state_mock` · ONTO_HOME을 무시한다 —
D-150). 그래서 「다른 루트」는 레포 사본으로 만든다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, done, init, os    # noqa: F401

#: 두 루트에서 **같은 순서로** 돌린다 — 다른 것은 층 폴더 이름뿐이다.
DOCS = (("CP01.xlsx", "cp"), ("PFMEA01.xlsx", "pfmea"), ("CP01.csv", "cp"))
QUESTION = "노칭 다음 공정은?"

#: 상태에서 성질만 뽑는다 — **좌표 층의 이름은 `coord`로 가린다**(그것만 다르다).
DUMP = r'''
import json, sys
sys.path.insert(0, ".")
from collections import Counter
from core.state.bootstrap import coord_layer, open_graph
from core.state import store
from router import discover
coord = coord_layer()
names = {}
for lay in discover():
    for i, n in open_graph(lay).nodes.items():
        names[i] = n["canonical"]
canon, edges = [], []
for lay in discover():
    g = open_graph(lay)
    role = "coord" if lay == coord else lay
    canon += [f"{role}|{n['canonical']}|{n['category']}|{n.get('status')}"
              for n in g.nodes.values()]
    edges += [f"{e['rel']}|{names.get(e['src'], e['src'])}|{names.get(e['dst'], e['dst'])}"
              for e in g.edges]
q = Counter(x["kind"] for x in store.read(store.QUEUE, []))
print(json.dumps({"coord": coord, "layers": sorted(discover()),
                  "canon": sorted(canon), "edges": sorted(edges),
                  "queue": dict(sorted(q.items()))}, ensure_ascii=False))
'''


def run(root, *argv, script=None):
    """그 루트에서 한 번 돌린다 — 상태는 **레포 옆**이라 루트가 곧 상태다."""
    cmd = [sys.executable, "-c", script] if script else \
        [sys.executable, str(Path(root) / "run.py"), *argv]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(root),
                          env={**os.environ, "USE_MOCK": "1"},
                          stdin=subprocess.DEVNULL)


def pipeline(root):
    """클린 → 골격 → 인입 셋 → 질의. 돌려주는 것은 성질 묶음이다."""
    run(root, "init", "--fresh")
    boot = run(root, "bootstrap")
    for doc, dt in DOCS:
        run(root, "ingest-file", str(Path(root) / "tests/fixtures/raw" / doc),
            "--doc-type", dt, "--allow-mock")
    ask = run(root, "query", QUESTION, "--allow-mock")
    dump = run(root, script=DUMP)
    quick = subprocess.run([sys.executable, str(Path(root) / "doctor.py"), "--quick"],
                           capture_output=True, text=True, cwd=str(root),
                           env={**os.environ, "USE_MOCK": "1"}, stdin=subprocess.DEVNULL)
    return {"boot": boot.stdout, "ask": ask.stdout + ask.stderr,
            "dump": json.loads(dump.stdout or "{}"), "dump_err": dump.stderr[-300:],
            "quick_rc": quick.returncode, "quick": quick.stdout}


print("\n■ B85 ① — 좌표 층을 묻는 자리 하나 · 골격 파일 부재는 문면 있는 거부")

from core.state import bootstrap as BS                                # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)

show("① `coord_layer()`가 **카테고리를 선언한 층**을 답한다 (이름을 모른다)",
     BS.coord_layer() == BS.layer_of_category(BS.COORD_CATEGORY)
     and BS.COORD_CATEGORY in load_config(BS.coord_layer())["categories"],
     f"{BS.COORD_CATEGORY} → {BS.coord_layer()}")
_save = dict(BS._COORD_LAYER)
BS._COORD_LAYER.clear()
_old_cat, BS.COORD_CATEGORY = BS.COORD_CATEGORY, "없는카테고리ZZ"
try:
    BS.coord_layer()
    _raised = None
except BS.NoCoordLayer as e:
    _raised = str(e)
finally:
    BS.COORD_CATEGORY = _old_cat
    BS._COORD_LAYER.clear()
    BS._COORD_LAYER.update(_save)
show("① 선언한 층이 없으면 **시끄럽게 실패한다** — 문면에 다음 줄이 있다",
     _raised and "없는카테고리ZZ" in _raised and "config.json" in _raised
     and "bootstrap" in _raised, (_raised or "").splitlines()[0][:70])
# 공용 블록을 여는 코드는 여럿이지만(생성 패키지도 연다), **좌표 카테고리를 거기서
# 꺼내는 자리는 하나**여야 한다 — 둘이면 하나가 낡는다.
_blocks = [l for l in subprocess.run(
    ["grep", "-rn", "paths.blocks()", "--include=*.py", "core", "cli", "parser"],
    capture_output=True, text=True, cwd=str(ROOT)).stdout.splitlines()
    if "target_category" in l]
show("① 좌표 카테고리를 `blocks.json`에서 꺼내는 자리가 **하나**다 (상수의 정본)",
     len(_blocks) == 1 and _blocks[0].startswith("core/state/bootstrap.py"),
     str(_blocks))

# 골격 파일 부재 — 세 명령이 **같은 문면**으로 거부한다(traceback 0).
_seed = _P.layers("process", "skeleton.json")
_keep = _seed.read_bytes()
_seed.unlink()
try:
    _b = run(ROOT, "bootstrap")
    _s = run(ROOT, "skeleton-status", "process")
    _c = run(ROOT, "skeleton-confirm", "process", "--by", "시험")
finally:
    _seed.write_bytes(_keep)
_outs = {"bootstrap": _b.stdout + _b.stderr, "status": _s.stdout + _s.stderr,
         "confirm": _c.stdout + _c.stderr}
show("① 골격 파일이 없으면 세 명령 모두 **문면 있는 거부**다 (Traceback 0)",
     all("골격 파일이 없다" in v and "Traceback" not in v for v in _outs.values())
     and _s.returncode == 1 and _c.returncode != 0 and _b.returncode == 1,
     " · ".join(f"{k} rc={r}" for k, r in
                (("bootstrap", _b.returncode), ("status", _s.returncode),
                 ("confirm", _c.returncode))))
show("① 그 문면이 **경로와 근거**를 싣는다 — config 키 · 끄는 법 · 좌표 층이라는 사실",
     all(("skeleton.json" in v and "skeleton.source" in v and "좌표 층" in v)
         for v in _outs.values()),
     [l.strip() for l in _outs["status"].splitlines() if "좌표 층" in l][:1])

print("\n■ B85 ② — 층 이름을 박은 자리 0 (새로 박히면 여기서 붉다)")
_grep = subprocess.run(["grep", "-rn", '"process"', "--include=*.py",
                        "core", "cli", "parser", "router.py", "run.py", "doctor.py"],
                       capture_output=True, text=True, cwd=str(ROOT))
_hits = [l for l in _grep.stdout.strip().splitlines() if l]
show("② 운영 코드에 층 이름 `process`를 박은 자리가 **낱말 후보 하나**뿐이다",
     len(_hits) == 1 and _hits[0].startswith("cli/register/generate.py")
     and "anchor" in _hits[0], str(_hits))

print("\n■ B85 ③ — 좌표 층 이름을 바꿔 전 구간을 돌린다 (canonical·엣지·큐 대조)")

_tmp = Path(tempfile.mkdtemp(prefix="onto_coord_"))
_clone = _tmp / "repo"
try:
    def _skip(src, names):
        """**뿌리의 상태 폴더만** 건너뛴다 — 이름만 보면 `core/state/`가 같이 빠진다."""
        out = {n for n in names if n in ("__pycache__", ".git") or n.endswith(".pyc")}
        if Path(src) == ROOT:
            out |= {n for n in names if n in ("state", "state_mock", "docs")}
        return out

    shutil.copytree(ROOT, _clone, ignore=_skip)
    # 층 폴더의 **이름만** 바꾼다 — config의 `layer` 키도 같은 이름이어야 한다.
    _src = _clone / "layers" / "process"
    _dst = _clone / "layers" / "equipment"
    _src.rename(_dst)
    _cfg = json.loads((_dst / "config.json").read_text(encoding="utf-8"))
    _cfg["layer"] = "equipment"
    (_dst / "config.json").write_text(json.dumps(_cfg, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    # doc_type이 가리키는 층 이름도 따라간다 — **층은 데이터로 선언된다**(B1).
    # 사내 절차도 같다: 층 폴더를 바꾸면 그 층에 등록된 doc_type의 층 키가 그 이름이다.
    def _relayer(obj):
        """층을 **가리키는 키**만 바꾼다 — `process_coord`(블록 이름)·`@process_ref`
        (필드 참조)는 층 이름이 아니다."""
        if isinstance(obj, dict):
            return {k: ("equipment" if k in ("layer", "target_layer") and v == "process"
                        else _relayer(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_relayer(x) for x in obj]
        return obj

    for _s in sorted((_clone / "tests/fixtures/schemas").glob("*.json")):
        _s.write_text(json.dumps(_relayer(json.loads(_s.read_text(encoding="utf-8"))),
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    show("③ 사본에는 `process` 폴더가 없다 (이름을 진짜로 바꿨다)",
         not (_clone / "layers" / "process").exists() and _dst.is_dir()
         and json.loads((_dst / "config.json").read_text(encoding="utf-8"))["layer"]
         == "equipment")

    _base = pipeline(ROOT)             # 이름 `process` — 지금 레포
    _eq = pipeline(_clone)             # 이름 `equipment` — 사본

    show("③ 이름을 바꾼 루트에서 좌표 층을 **카테고리로** 찾는다",
         _eq["dump"].get("coord") == "equipment"
         and _base["dump"].get("coord") == "process",
         f"{_base['dump'].get('coord')} vs {_eq['dump'].get('coord')} "
         f"· {_eq.get('dump_err', '')}")
    show("③ 골격이 심긴다 — 좌표 층의 노드 수가 같다 (빈 목록이 아니다)",
         _eq["dump"].get("canon") and _base["dump"].get("canon")
         and len(_eq["dump"]["canon"]) == len(_base["dump"]["canon"]),
         f"{len(_base['dump'].get('canon') or [])} vs {len(_eq['dump'].get('canon') or [])}")
    show("③ 두 루트의 canonical 집합이 같다 (층 이름만 다른 그래프)",
         _eq["dump"].get("canon") == _base["dump"].get("canon"),
         str(sorted(set(_base["dump"].get("canon") or [])
                    ^ set(_eq["dump"].get("canon") or []))[:2]))
    _cross = [e for e in (_base["dump"].get("edges") or []) if e.startswith("occurs_in")]
    show("③ 엣지가 같다 — 걸침 엣지도 이름 바뀐 좌표 층에 붙는다",
         _eq["dump"].get("edges") == _base["dump"].get("edges") and _cross,
         f"엣지 {len(_base['dump'].get('edges') or [])} · 걸침 {len(_cross)}")
    show("③ 큐가 kind별로 같다 — orphan이 늘지 않는다",
         _eq["dump"].get("queue") == _base["dump"].get("queue"),
         f"{_base['dump'].get('queue')} vs {_eq['dump'].get('queue')}")
    show("③ 질의가 같은 경로로 답한다 (링킹은 그 층의 이름을 달고 온다)",
         "[경로]" in _eq["ask"] and "equipment:" in _eq["ask"]
         and [l for l in _eq["ask"].splitlines() if "[경로]" in l]
         == [l for l in _base["ask"].splitlines() if "[경로]" in l],
         [l.strip() for l in _eq["ask"].splitlines() if "[링킹]" in l][:1])
    show("③ `doctor --quick`이 양쪽에서 EXIT=0이고 첫 줄이 좌표 층을 말한다",
         _base["quick_rc"] == 0 and _eq["quick_rc"] == 0
         and "좌표 층 equipment" in _eq["quick"] and "좌표 층 process" in _base["quick"],
         [l.strip() for l in _eq["quick"].splitlines() if "좌표 층" in l][:1])
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

done()
