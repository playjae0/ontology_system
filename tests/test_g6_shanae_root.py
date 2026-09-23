# -*- coding: utf-8 -*-
"""G6 ⑨ **「사내 모양」 회귀 루트** — 상태가 코드 밖 · 좌표 층이 `equipment` · 등록부터 뷰어까지 (B86 ⑥).

회귀의 바닥은 사내와 두 군데 다르다: ①상태 루트가 **코드 폴더 안**(`state_mock/`)이고
②좌표 층 폴더 이름이 **`process`**다. B85가 ②를 회귀에 넣었고(레포 사본 안의
`state_mock`), 이 스위트가 ①과 **등록 경로**를 넣는다. 그래서 「상태 경로를 코드 폴더
기준으로 계산」「주입 안 된 파서가 레포 옛 자리를 봄」「등록 표본에 시트 관문 없음」이
회귀 1,517을 초록으로 통과했다 — 이 시험이 그것을 잠근다.

**두 루트를 같은 명령으로 돌려 대조한다**:
  · 기본 모양 — 깨끗한 코드 사본 A · 상태는 그 안 `state_mock/` · 좌표 층 `process`
  · 사내 모양 — 깨끗한 코드 사본 B · 상태는 **코드 밖** 임시 폴더(시험 훅
    `ONTO_MOCK_HOME` — 운영은 보지 않는다) · 좌표 층 `equipment`(품질층 같이)

코드 사본은 **커밋될 파일만**(추적분 + 무시 규칙 밖의 새 파일)이다 — 사내가 받는 모양이고, 작업 폴더에 남은
옛 실행 산출(추적 밖)이 이관 감지를 흔들지 않는다.

잠그는 성질: 예외 0 · 코드 폴더에 새 파일 0(사내 모양) · canonical·엣지
(rel, src canonical, dst canonical)·큐 kind별 수가 기본 모양과 같다.
"""
from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def _tracked():
    """git이 추적하는 파일 + **무시 규칙 밖의 새 파일**(= 커밋될 모양) — 없으면(사내
    반입본) 상태·실행 산출을 뺀 전부. 추적 밖 옛 산출(`.gitignore`)은 들어오지 않는다."""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others",
                              "--exclude-standard"], cwd=str(ROOT), capture_output=True,
                             check=True).stdout.decode("utf-8").split("\0")
        return [f for f in out if f and (ROOT / f).is_file()]
    except (OSError, subprocess.CalledProcessError):
        skip = ("state", "state_mock", "data", "review", "extract", "parsed", ".git")
        return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                if p.is_file() and p.relative_to(ROOT).parts[0] not in skip
                and "__pycache__" not in p.parts]


def _copy_code(dst):
    for f in _tracked():
        if f.startswith("docs/"):              # 문서는 실행에 필요 없다
            continue
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst / f)


def _relayer(obj, old, new):
    """층을 **가리키는 키**만 바꾼다 — `process_coord`·`@process_ref`는 층 이름이 아니다."""
    if isinstance(obj, dict):
        return {k: (new if k in ("layer", "target_layer") and v == old
                    else _relayer(v, old, new)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_relayer(x, old, new) for x in obj]
    return obj


def _files(d):
    return {p.relative_to(d).as_posix() for p in d.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


class Root:
    """루트 하나 — 코드 폴더와 (있으면) 코드 밖 상태 폴더."""

    def __init__(self, base, name, coord, outside):
        self.code = base / name / "code"
        self.code.mkdir(parents=True)
        _copy_code(self.code)
        self.coord = coord
        self.env = {**os.environ, "USE_MOCK": "1", "NO_COLOR": "1"}
        self.env.pop("ONTO_HOME", None)
        self.state = None
        if outside:
            self.state = base / name / "onto_state"            # **코드 밖**
            self.env["ONTO_MOCK_HOME"] = str(self.state)
        self.outs = []

    def run(self, *argv, answers=None, module=None):
        cmd = [sys.executable] + (["-m", module] if module else [str(self.code / "run.py")])
        cmd += list(argv)
        if answers is None:
            r = subprocess.run(cmd, cwd=str(self.code), env=self.env, capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
            out, rc = r.stdout + r.stderr, r.returncode
        else:
            pid, fd = pty.fork()
            if pid == 0:                                        # pragma: no cover
                os.chdir(str(self.code))
                os.execve(sys.executable, cmd, self.env)
            os.write(fd, answers.encode())
            buf = b""
            try:
                while True:
                    d = os.read(fd, 4096)
                    if not d:
                        break
                    buf += d
            except OSError:
                pass
            _, st = os.waitpid(pid, 0)
            out, rc = buf.decode("utf-8", "replace"), os.waitstatus_to_exitcode(st)
        self.outs.append((" ".join(argv[:2]), rc, out))
        return rc, out

    def py(self, script):
        r = subprocess.run([sys.executable, "-c", script], cwd=str(self.code), env=self.env,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.outs.append(("python -c", r.returncode, r.stdout + r.stderr))
        return r.returncode, r.stdout


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
    canon += [f"{role}|{n['canonical']}|{n['category']}|{n.get('status')}" for n in g.nodes.values()]
    edges += [f"{e['rel']}|{names.get(e['src'], e['src'])}|{names.get(e['dst'], e['dst'])}"
              for e in g.edges]
q = Counter(x["kind"] for x in store.read(store.QUEUE, []))
print(json.dumps({"coord": coord, "canon": sorted(canon), "edges": sorted(edges),
                  "queue": dict(sorted(q.items()))}, ensure_ascii=False))
'''

#: 질의 12문항 — `run.py query`와 **같은 함수**를 한 프로세스에서 돈다.
QUERIES = r'''
import json, sys
sys.path.insert(0, ".")
from cli.query import answer
from core.state import fixtures
qs = json.loads(fixtures.QUERIES.read_text(encoding="utf-8"))["queries"]
paths = [answer(q["q"])["path"] for q in qs]
print(json.dumps({"n": len(qs), "paths": paths}, ensure_ascii=False))
'''

#: 뷰어 — 서버를 띄워 **HTTP로** 두 API를 받는다(쓰기 0).
VIEWER = r'''
import json, sys, threading, urllib.request
sys.path.insert(0, ".")
from cli.viewer import server as VS
srv, _url = VS.serve(0)
url = f"http://{VS.HOST}:{srv.server_address[1]}/"     # 0번은 빈 포트를 고른다 — 실제 포트로
threading.Thread(target=srv.serve_forever, daemon=True).start()
g = json.loads(urllib.request.urlopen(url + "api/graph", timeout=60).read())
d = urllib.request.urlopen(url + "api/doc/CP01", timeout=60)
print(json.dumps({"nodes": len(g["nodes"]), "doc": d.status}))
srv.shutdown()
'''


def pipeline(r):
    """두 루트에 **같은 명령**을 돈다 — 다른 것은 상태의 자리와 좌표 층 이름뿐이다."""
    raw = r.code / "tests" / "fixtures" / "raw"
    r.run("init", "--fresh")
    r.run("bootstrap")
    r.run("skeleton-status", r.coord)
    r.run("skeleton-confirm", r.coord, "--by", "시험", answers="y\n")
    # 등록 — 산문(시트 7장 · 표본 관문은 `--sheets`) · 표(지문 스캔 초안) 각 1
    r.run("register", "generate", "rfq", r.coord, str(raw / "RFQ01.xlsx"), "--use-basic",
          "--sheets", "2-4:prose 5:ref *:skip", "--allow-mock")
    r.run("register", "status", "rfq")
    r.run("register", "confirm", "rfq", "--by", "시험", "--allow-mock")
    # 표 초안은 mock에서 **이름이 맞는 픽스처**가 낸다(D-10) — 회귀가 쓰는 `ipqc`.
    r.run("register", "generate", "ipqc", r.coord, str(raw / "IPQC01.xlsx"),
          str(raw / "IPQC02.xlsx"), "--no-basic", "--allow-mock")
    r.run("register", "status", "ipqc")
    r.run("register", "confirm", "ipqc", "--by", "시험", "--allow-mock")
    # 인입 — 표본 셋(RFQ01은 등록 때 답한 기록으로 간다 · 관문 0)
    r.run("ingest-file", str(raw / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock")
    r.run("ingest-file", str(raw / "TOC01.xlsx"), "--doc-type", "rfq", "--allow-mock")
    rc_rfq, out_rfq = r.run("ingest-file", str(raw / "RFQ01.xlsx"), "--doc-type", "rfq",
                            "--allow-mock")
    _, q = r.py(QUERIES)
    r.run("export", "html")
    r.run("golden", "init")
    _, v = r.py(VIEWER)
    rc_doc, doc_out = subprocess.run(
        [sys.executable, str(r.code / "doctor.py"), "--quick"], cwd=str(r.code), env=r.env,
        capture_output=True, text=True, stdin=subprocess.DEVNULL).returncode, ""
    _, dump = r.py(DUMP)
    return {"dump": json.loads(dump or "{}"), "queries": json.loads(q or "{}"),
            "viewer": json.loads(v or "{}"), "doctor_rc": rc_doc,
            "rfq_ingest": (rc_rfq, out_rfq)}


print("\n■ B86 ⑥ — 「사내 모양」 루트: 상태가 코드 밖 · 좌표 층 equipment · 등록부터 뷰어까지")
_tmp = Path(tempfile.mkdtemp(prefix="onto_shanae_"))
try:
    base = Root(_tmp, "base", "process", outside=False)
    sh = Root(_tmp, "shanae", "equipment", outside=True)
    # 사내 모양 — 층 자산은 **상태 루트**에 사람이 둔다(B79 ①) · 이름은 equipment
    for lay, new in (("process", "equipment"), ("quality", "quality")):
        src = sh.code / "layers" / lay
        dst = sh.state / "layers" / new
        shutil.copytree(src, dst)
        cfg = json.loads((dst / "config.json").read_text(encoding="utf-8"))
        cfg["layer"] = new
        (dst / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    # doc_type이 가리키는 층 이름도 따라간다(층은 데이터로 선언된다 — B1 · D-166 ⑨)
    for s in sorted((sh.code / "tests/fixtures/schemas").glob("*.json")):
        s.write_text(json.dumps(_relayer(json.loads(s.read_text(encoding="utf-8")),
                                         "process", "equipment"),
                                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _code_before = _files(sh.code)

    b = pipeline(base)
    s = pipeline(sh)

    _bad = [(c, rc, o[-300:]) for c, rc, o in sh.outs if "Traceback" in o]
    show("⑥ 사내 모양 전 구간에 **예외 0** — 등록·인입·질의·반출·골든·뷰어·doctor",
         not _bad, str(_bad[:1]))
    # **종료 코드가 명령마다 기본 루트와 같다** — 표 등록은 mock 픽스처(`ipqc` · 규약 10
    # 이전 스냅샷 · 판정필요-14)라 양쪽 다 관문에서 멈춘다. 잠그는 것은 「사내 모양이라서
    # 달라지는 것 0」이다.
    _rcs_b = [(c, rc) for c, rc, _o in base.outs]
    _rcs_s = [(c.replace(str(sh.code), str(base.code)), rc) for c, rc, _o in sh.outs]
    _diff = [(x, y) for x, y in zip(_rcs_b, _rcs_s) if x[1] != y[1]]
    show("⑥ 명령마다 종료 코드가 기본 루트와 같다 (사내 모양이라서 갈리는 명령 0)",
         len(_rcs_b) == len(_rcs_s) and not _diff,
         str(_diff[:2]) or f"명령 {len(_rcs_s)}")
    show("⑥ 산문 등록은 사내 모양에서 **생성 → 상태 → 확정**까지 간다",
         [rc for c, rc, _o in sh.outs[4:7]] == [0, 0, 0],
         str([(c, rc) for c, rc, _o in sh.outs[4:7]]))
    _new = sorted(_files(sh.code) - _code_before)
    show("⑥ **코드 폴더에 새 파일 0** — 상태·관문 산출이 전부 코드 밖이다",
         not _new, str(_new[:5]))
    show("⑥ 상태는 코드 밖 루트에 섰다 (등록부 · 시트 역할 · 대장)",
         (sh.state / "registry" / "doc_types.json").is_file()
         and (sh.state / "registry" / "sheet_roles" / "RFQ01.json").is_file()
         and (sh.state / "work" / "ingest_log").is_dir(),
         str(sorted(p.name for p in sh.state.iterdir())))
    show("⑥ 좌표 층을 **카테고리로** 찾는다 (process · equipment)",
         b["dump"].get("coord") == "process" and s["dump"].get("coord") == "equipment",
         f"{b['dump'].get('coord')} · {s['dump'].get('coord')}")
    show("⑥ canonical 집합이 기본 루트와 같다 (층 이름만 다른 그래프)",
         s["dump"].get("canon") and s["dump"].get("canon") == b["dump"].get("canon"),
         f"{len(b['dump'].get('canon') or [])} · {len(s['dump'].get('canon') or [])}")
    _cross = [e for e in (b["dump"].get("edges") or []) if e.startswith("occurs_in")]
    show("⑥ 엣지(rel, src canonical, dst canonical)가 같다 — 걸침 포함",
         s["dump"].get("edges") == b["dump"].get("edges"),
         f"엣지 {len(b['dump'].get('edges') or [])} · 걸침 {len(_cross)}")
    show("⑥ 큐가 kind별로 같다", s["dump"].get("queue") == b["dump"].get("queue"),
         f"{b['dump'].get('queue')} vs {s['dump'].get('queue')}")
    show("⑥ 질의 12문항이 같은 경로로 답한다",
         s["queries"].get("n") == 12 and s["queries"] == b["queries"],
         str(s["queries"].get("paths"))[:80])
    show("⑥ 뷰어 두 API가 서고 노드 수가 같다",
         s["viewer"].get("doc") == 200 and s["viewer"] == b["viewer"], str(s["viewer"]))
    show("⑥ `doctor --quick` EXIT=0 양쪽", b["doctor_rc"] == 0 and s["doctor_rc"] == 0,
         f"{b['doctor_rc']} · {s['doctor_rc']}")
    show("⑤ 등록 때 답한 시트 역할로 인입이 간다 — **관문 0**(기록대로)",
         "기록대로 진행" in s["rfq_ingest"][1] and "■ 시트 역할" not in s["rfq_ingest"][1],
         [l.strip() for l in s["rfq_ingest"][1].splitlines() if "시트 역할" in l][:1])
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — 사내 모양 루트 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
