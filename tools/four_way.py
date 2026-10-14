# -*- coding: utf-8 -*-
"""네 벌 대조 — 기준 커밋과 지금 작업 트리의 **mock 첫 인입 산출**을 벌마다 비교한다 (D-190).

    python tools/four_way.py --base <커밋>                 기준 vs 지금 — 다른 것의 수와 앞 견본
    python tools/four_way.py --base <커밋> --keep <폴더>    덤프 둘(base.json · now.json)을 남긴다

회차 요청문 마감 줄의 「네 벌 diff」를 회차마다 손으로 다시 짜던 것을 한 자리로 모았다.

**네 벌** = 그래프(층마다 노드 · 엣지) · 사전 · 큐 · 판정 대장(`work/ingest_log/`) — 덧붙여 ③진실
`data/`의 파일 목록(새 파일이 생기면 여기 뜬다). 시각·횟수 키는 빼고, 의미 축 id는 그 노드의
`층:canonical`로 바꿔 대조한다(ULID는 실행마다 다르다).

**두 바닥** — 같은 표본을 같은 순서로 넣는다:
  A: `init --fresh --all` → bootstrap → 표 표본 다섯(`TABLE`)을 하나씩 `ingest_file`(비대화형 —
     선택이 안 되는 표본은 「미선택」 그대로가 대조 대상이다)
  B: 회귀 바닥 `tests/g65_common.fresh()`(CP01 · PFMEA01 · PPT01~03 · QPPT01 + finalize)

**자리를 가른다**: 기준은 `git archive`로, 지금은 작업 트리(커밋 안 한 변경 포함 · 무시 파일 제외)를
임시 폴더에 복사하고, 사본마다 **자기 `state_mock/`**에서 돈다 — 레포의 `state_mock/`은 건드리지
않는다. `ONTO_MOCK_HOME`은 쓰지 않는다 — 그 문은 `init --fresh`가 층 자산을 seed로 덮지 않게
바꾼다(`core/paths.py` 머리말). 덤프는 **이 파일 하나**를 두 사본에 넣어 돌린다(같은 스크립트 —
기준 커밋에 이 파일이 없어도 된다). 두 사본은 동시에 돈다. 임시 폴더는 `TMPDIR` 아래에
만들고 끝나면 지운다.

종료 코드: 0 = 전부 같다 · 1 = 다른 것이 있다(기대한 변화인지는 보고가 말한다) · 2 = 못 돌았다.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 실행마다 달라지는 키 — 대조에서 뺀다.
TS = ("created", "at", "first_seen", "last_seen", "last_tried", "last_fp", "attempts", "obsoleted_at",
      "confirmed_at", "parsed_at", "first_ingested_at", "ingested_at", "updated_at", "last_hit")
#: 바닥 A의 표 표본 — 넣는 순서 그대로.
TABLE = ("CP01.xlsx", "CP02_drift.xlsx", "PFMEA01.xlsx", "IPQC01.xlsx", "CSV01.csv")
SAMPLES = 3                          # 다른 것마다 보이는 견본 수
CUT = 300                            # 견본 한 줄 길이


# ---------------------------------------------------------------- 덤프 (사본 안에서 돈다)
def _state():
    """지금 상태 루트의 네 벌 + `data/` 파일 목록 — id·시각 없이."""
    from core import paths as P
    from core.state import store
    from core.state.world import World
    w = World()
    name = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in w.nodes()}

    def canon(x):
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items() if k not in TS}
        if isinstance(x, list):
            return [canon(v) for v in x]
        return name.get(x, x) if isinstance(x, str) else x

    def line(x):
        return json.dumps(canon(x), ensure_ascii=False, sort_keys=True)

    led = P.work("ingest_log")
    return {
        "graph": {lay: {"nodes": sorted(line(dict(n, id=None)) for n in g.nodes.values()),
                        "edges": sorted(line(e) for e in g.edges)}
                  for lay, g in sorted(w.graphs.items())},
        "dict": line(store.read(store.DICTIONARY, {})),
        "queue": sorted(line(x) for x in store.read(store.QUEUE, [])),
        "ledger": ({f.name: canon(json.loads(f.read_text(encoding="utf-8")))
                    for f in sorted(led.glob("*.json"))} if led.exists() else {}),
        "files": sorted(P.rel_to_home(x) for x in P.data().rglob("*")
                        if x.is_file() and not x.name.endswith(".lock")),
    }


def dump(out):
    """두 바닥을 차례로 세우고 덤프를 `out`에 쓴다 — 이 파일이 놓인 사본의 코드로."""
    os.environ["USE_MOCK"] = "1"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))          # 바닥 B(g65_common)
    import run as RUN
    from cli import ingest as IG
    from core.state import fixtures, init
    quiet = contextlib.redirect_stdout
    res, st = {}, {}
    with quiet(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
    for f in TABLE:
        try:
            with quiet(io.StringIO()):
                r = IG.ingest_file(str(fixtures.RAW / f), None, ask=False)
            st[f] = (r or {}).get("status")
        except SystemExit as e:
            st[f] = f"exit {e.code}"
    res["A_status"], res["A"] = st, _state()
    import g65_common as G
    with quiet(io.StringIO()):
        G.fresh()
    res["B"] = _state()
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return 0


# ---------------------------------------------------------------- 사본 · 실행
def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def _copy_base(commit, dest):
    """기준 — 그 커밋의 추적 파일 그대로."""
    kw = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
    with tarfile.open(fileobj=io.BytesIO(_git("archive", "--format=tar", commit))) as t:
        t.extractall(dest, **kw)


def _copy_now(dest):
    """지금 — 작업 트리의 추적 파일 + 새 파일(무시 파일 제외 · 커밋 안 한 변경 포함)."""
    for rel in filter(None, _git("ls-files", "-z", "-co", "--exclude-standard").split(b"\0")):
        src = ROOT / os.fsdecode(rel)
        if src.is_file():                            # 지운 추적 파일은 목록에만 남는다
            dst = dest / os.fsdecode(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _run(work, trees):
    """사본마다 덤프를 동시에 돌린다 — 환경의 `ONTO_*`는 빼고(사본마다 기본 mock 루트) · 출력은 로그 파일로."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ONTO_")}
    env["USE_MOCK"] = "1"
    procs = {}
    for side, tree in trees.items():
        me = tree / "tools" / Path(__file__).name
        me.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(__file__, me)
        with open(work / f"{side}.log", "w", encoding="utf-8") as fh:
            procs[side] = subprocess.Popen([sys.executable, str(me), "--dump", str(work / f"{side}.json")],
                                           cwd=tree, env=env, stdout=fh, stderr=subprocess.STDOUT)
    rc = {side: p.wait() for side, p in procs.items()}
    return {side: (rc[side], (work / f"{side}.log").read_text(encoding="utf-8")) for side in trees}


# ---------------------------------------------------------------- 대조
def _summary(label, d):
    out = []
    for side in ("A", "B"):
        g = d[side]
        out.append(f"{label} {side}" + (f" 넣기 {d['A_status']}" if side == "A" else "")
                   + f" · 노드 { {k: len(v['nodes']) for k, v in g['graph'].items()} }"
                   + f" · 엣지 { {k: len(v['edges']) for k, v in g['graph'].items()} }"
                   + f" · 큐 {len(g['queue'])} · 대장 행 {sum(len(v.get('rows') or []) for v in g['ledger'].values())}")
    return out


def _diff(label, p, q):
    """`(줄들, 다른가)` — 목록 둘을 중복까지 센다(빠짐 = 기준에만 · 더함 = 지금에만)."""
    gone, new = Counter(p) - Counter(q), Counter(q) - Counter(p)
    out = [f"{label}: 기준 {len(p)} · 지금 {len(q)} · 빠짐 {sum(gone.values())} · 더함 {sum(new.values())}"]
    out += [f"    - {s[:CUT]}" for s in sorted(gone)[:SAMPLES]]
    out += [f"    + {s[:CUT]}" for s in sorted(new)[:SAMPLES]]
    return out, bool(gone or new)


def compare(a, b):
    """벌마다 다른 것 — `(줄들, 다른 것이 있는가)`."""
    same = a["A_status"] == b["A_status"]
    lines, differs = [f"A 넣기 결과 같음 {same}"], not same
    for side in ("A", "B"):
        x, y = a[side], b[side]
        for lay in sorted(set(x["graph"]) | set(y["graph"])):
            for part in ("nodes", "edges"):
                ls, d = _diff(f"{side} 그래프 {lay} {part}", x["graph"].get(lay, {}).get(part, []),
                              y["graph"].get(lay, {}).get(part, []))
                lines, differs = lines + ls, differs or d
        same = x["dict"] == y["dict"]
        lines, differs = lines + [f"{side} 사전 같음 {same}"], differs or not same
        ls, d = _diff(f"{side} 큐", x["queue"], y["queue"])
        lines, differs = lines + ls, differs or d
        dl = sorted(k for k in set(x["ledger"]) | set(y["ledger"]) if x["ledger"].get(k) != y["ledger"].get(k))
        lines.append(f"{side} 판정 대장: 파일 {len(y['ledger'])} · 다른 파일 {dl}")
        fx, fy = set(x["files"]), set(y["files"])
        lines.append(f"{side} data 파일: 빠짐 {sorted(fx - fy)} · 더함 {sorted(fy - fx)}")
        differs = differs or bool(dl) or fx != fy
    return lines, differs


def main(argv=None):
    ap = argparse.ArgumentParser(description="네 벌 대조 — 기준 커밋 vs 지금 작업 트리(mock 첫 인입)")
    ap.add_argument("--base", help="기준 커밋 — 회차 반입 커밋 등")
    ap.add_argument("--keep", help="덤프 둘(base.json · now.json)을 남길 폴더")
    ap.add_argument("--dump", help=argparse.SUPPRESS)          # 사본 안에서 부르는 문
    a = ap.parse_args(argv)
    if a.dump:
        return dump(a.dump)
    if not a.base:
        ap.error("--base <커밋>이 필요하다")
    try:
        sha = _git("rev-parse", "--verify", "--short", f"{a.base}^{{commit}}").decode().strip()
    except subprocess.CalledProcessError:
        print(f"기준 커밋을 찾지 못했다: {a.base}")
        return 2
    dirty = len(_git("status", "--porcelain").decode().splitlines())
    print(f"기준 {sha} {_git('log', '-1', '--format=%s', sha).decode().strip()[:70]}")
    print(f"지금 작업 트리 — HEAD {_git('rev-parse', '--short', 'HEAD').decode().strip()} · 커밋 안 한 변경 {dirty}")
    t0, work = time.time(), Path(tempfile.mkdtemp(prefix="four_way_"))
    try:
        trees = {"base": work / "base", "now": work / "now"}
        _copy_base(sha, trees["base"])
        _copy_now(trees["now"])
        res = _run(work, trees)
        bad = [side for side, (rc, _) in res.items() if rc]
        for side in bad:
            print(f"── {side} 실행 실패 rc={res[side][0]} — 로그 끝 20줄")
            print("\n".join(res[side][1].splitlines()[-20:]))
        if bad:
            return 2
        d = {side: json.loads((work / f"{side}.json").read_text(encoding="utf-8")) for side in trees}
        if a.keep:
            keep = Path(a.keep)
            keep.mkdir(parents=True, exist_ok=True)
            for side in trees:
                shutil.copy2(work / f"{side}.json", keep / f"{side}.json")
        lines, differs = compare(d["base"], d["now"])
        print("\n".join(_summary("기준", d["base"]) + _summary("지금", d["now"]) + lines))
        print(f"{'다른 것이 있다' if differs else '전부 같다'} · 소요 {time.time() - t0:.0f}초"
              + (f" · 덤프 {a.keep}" if a.keep else ""))
        return 1 if differs else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
