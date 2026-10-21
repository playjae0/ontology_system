# -*- coding: utf-8 -*-
"""칸 5.2 · 5.3 · 4.1 — 뷰어 **브라우저 실측 B114**: 힘 배치가 끝까지 퍼진다 · 크기 대비 · 짧은 라벨 · 벡터 준비와
질의 상태가 보인다.

`viewer_browser*.py`와 같은 처지다(D-165 ②) — Playwright · Chromium이 있어야 하고 사내 클론에는 없어 **회귀(`doctor.py`)에
넣지 않는다**. 회귀에는 브라우저 없이 재는 성질(벡터 이어 만들기 · 진행 줄 · 질의 단계 · 상태 라우트 · 쓰기 0 —
`tests/test_viewer.py`)만 둔다. 여기 것은 회차 보고에 실행 결과로 붙인다.

표본은 **창작**이다 — ⓐ는 화면 데이터 함수(`cli/viewer/data.graph`)를 창작 큰 그래프(공정 8 덩어리 · 노드 약 3천)로
바꿔 띄우고, ⓑ~ⓔ는 mock 그래프(CP01 · PFMEA01 · PPT01~03 · QPPT01)다. 수치는 메커니즘 확인이다([정정] 50).
고치기 전 판은 B113 마감 커밋(`BEFORE`)의 `layout.js` · `render.js`를 그대로 읽어 같은 브라우저에서 돌린다.

재는 것(완료판정):
  ⓐ 힘 배치 — 원 모양으로 굳지 않는다(지표 셋을 고치기 전과 나란히: 고리 지표 = 닻 둘레 위성 거리의 변동계수 평균 ·
     연결 쌍 평균 거리 / 연결 안 된 쌍 평균 거리 · 중심에서의 반지름 변동계수) · 화면이 멈추지 않는다(배치 중 가장 긴
     프레임 틈) · 같은 시드 · 같은 반복이면 같은 좌표
  ⓑ 크기 · 라벨 — tier마다 크기 비가 고치기 전보다 크다 · 라벨은 끝 조각 · 올린 점 · 상세 · 검색 · 「전체 이름」은 전체
  ⓒ 벡터 — 끊었다 다시 치면 이어 간다 · 진행 줄(CLI · 서버 콘솔) · 묶음이면 시간이 준다(로컬 갈래 스텁)
  ⓓ 질의 상태 줄이 단계를 따라 바뀐다 · 엔터로 묻는다
  ⓔ 쓰기 0(③진실 · ②등록 해시 불변) · 외부 URL 0 · 콘솔 오류 0 (네 벌은 `tools/four_way.py` — 회차 보고)

사용: python tests/viewer_browser_b114.py   (스크린샷은 `$ONTO_HOME/export/viewer_shots/`)
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover
    print("■ 뷰어 브라우저 실측 B114 — **건너뛴다**: playwright가 없다.")
    sys.exit(0)

from g65_common import *                                  # noqa: E402,F401,F403 — 바닥은 하나다
from g65_common import _P                                 # noqa: E402
from cli.viewer import server as VS                       # noqa: E402
from core.llm import embeddings as E, gateway             # noqa: E402
from core.query import anchor as A, hybrid as H, status as QS, vectors as V   # noqa: E402

allok = True                                              # 별 import 뒤에 둔다(B103 — 덮어쓰기 사고)
PORT = 8884
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
BEFORE = "448572d"                                        # B113 마감 — 고치기 전 판


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def _state_hash():
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in (_P.data(), _P.registry()) if base.exists()
            for p in sorted(base.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}


def _old(path):
    return subprocess.run(["git", "show", f"{BEFORE}:{path}"], cwd=ROOT, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, check=True).stdout


# ─────────────────────────────────────────── 창작 큰 그래프 (ⓐ) — 결정적 생성(LCG)
def synthetic(clusters=8, sats=360, seed=7):
    state = [seed]

    def rnd(n):
        state[0] = (state[0] * 1103515245 + 12345) % (2 ** 31)
        return state[0] % n
    nodes, edges = [], []

    def node(i, name, cat, status, tier):
        nodes.append({"id": i, "name": name, "layer": "process", "category": cat, "status": status, "tier": tier,
                      "polarity": "none", "prov": "창작", "made_by": "seed" if status == "seed" else "extract",
                      "aliases": 0, "attrs": 0, "queue": None, "docs": ["SYN"]})
    mains = []
    for c in range(clusters):
        m = f"P{c:02d}"
        node(m, f"공정{c}", "Process", "seed", "main")
        mains.append(m)
        members = [m]
        for s in range(2):
            sid = f"{m}S{s}"
            node(sid, f"공정{c}::세부{s}", "Process", "seed", "sub")
            edges.append({"src": sid, "rel": "part_of", "dst": m})
            for d in range(3):
                did = f"{sid}D{d}"
                node(did, f"공정{c}::세부{s}::단위{d}", "Process", "seed", "detail")
                edges.append({"src": did, "rel": "part_of", "dst": sid})
                members.append(did)
        for k in range(sats):
            host = members[rnd(len(members))]
            host_name = next(n["name"] for n in nodes if n["id"] == host) if k < 40 else f"공정{c}"
            nid = f"{m}X{k:03d}"
            node(nid, f"{host_name}::부품{k}", ["Unit", "Component", "Property"][rnd(3)], "auto", None)
            edges.append({"src": nid, "rel": "part_of", "dst": host})
            members.append(nid)
            if rnd(7) == 0 and len(members) > 3:
                other = members[rnd(len(members) - 1)]
                if other != nid:
                    edges.append({"src": nid, "rel": "relates", "dst": other})
    for a, b in zip(mains, mains[1:]):
        edges.append({"src": a, "rel": "precedes", "dst": b})
    anc = A.anchors(nodes, edges)
    return {"nodes": nodes, "edges": edges, "layers": ["process"], "rels": sorted({e["rel"] for e in edges}),
            "anchor": {k: {"anchor": v["anchor"], "host": v["host"], "hops": v["hops"]} for k, v in anc.items()},
            "detached": A.detached(nodes, edges, anc), "roots": A.roots(nodes, edges),
            "explore_threshold": 10 ** 9, "force": dict(VS.D.FORCE)}


def metrics(G, pos):
    """지표 셋 — 위치 `{id: {x, y}}`(배율 무관)."""
    ids = [n["id"] for n in G["nodes"] if n["id"] in pos]
    P = {i: (pos[i]["x"], pos[i]["y"]) for i in ids}
    d = lambda a, b: math.hypot(P[a][0] - P[b][0], P[a][1] - P[b][1])   # noqa: E731
    es = [(e["src"], e["dst"]) for e in G["edges"] if e["src"] in P and e["dst"] in P]
    conn = sum(d(a, b) for a, b in es) / max(1, len(es))
    link = {(a, b) for a, b in es} | {(b, a) for a, b in es}
    N = len(ids)
    far = [d(ids[i], ids[(i * 7919 + 13) % N]) for i in range(N)
           if ids[i] != ids[(i * 7919 + 13) % N] and (ids[i], ids[(i * 7919 + 13) % N]) not in link]
    unconn = sum(far) / max(1, len(far))
    kids = {}
    for i, a in G["anchor"].items():
        if a["host"] != i and i in P and a["host"] in P:
            kids.setdefault(a["host"], []).append(i)
    cvs = []
    for h, ks in kids.items():
        if len(ks) >= 6:
            r = [d(h, k) for k in ks]
            m = sum(r) / len(r)
            cvs.append((sum((x - m) ** 2 for x in r) / len(r)) ** 0.5 / m if m else 0)
    cx = sum(P[i][0] for i in ids) / N
    cy = sum(P[i][1] for i in ids) / N
    rr = [math.hypot(P[i][0] - cx, P[i][1] - cy) for i in ids]
    rm = sum(rr) / N
    return {"고리CV": round(sum(cvs) / max(1, len(cvs)), 3), "연결/비연결": round(conn / unconn, 3),
            "반지름CV": round((sum((x - rm) ** 2 for x in rr) / N) ** 0.5 / rm, 3), "호스트": len(cvs)}


_RAF = """() => { window.__gaps = []; let last = performance.now(); window.__rafOn = true;
  const tick = (t) => { window.__gaps.push(t - last); last = t; if (window.__rafOn) requestAnimationFrame(tick); };
  requestAnimationFrame(tick); }"""
_RAF_STOP = "() => { window.__rafOn = false; return Math.round(Math.max(0, ...window.__gaps)); }"

with contextlib.redirect_stdout(io.StringIO()):
    fresh()
H0 = _state_hash()
SHOTS = _P.export("viewer_shots")
_P.ensure(SHOTS)
srv, url = VS.serve(PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
SYN = synthetic()
print(f"\n■ B114 — 뷰어 브라우저 실측 ({url}) · 창작 큰 그래프 노드 {len(SYN['nodes'])} · 엣지 {len(SYN['edges'])}")

errs, ext = [], []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=CHROME, args=["--use-gl=swiftshader", "--enable-webgl",
                                                         "--ignore-gpu-blocklist"])
    # ── ⓐ 힘 배치 — 크기 둘(덩어리 8 · 16) · 고치기 전(B113 판 layout.js · 같은 브라우저 · 같은 그래프)과 나란히
    real_graph = VS.D.graph
    rows = []
    for k, G in enumerate((SYN, synthetic(clusters=16, seed=11))):
        old = br.new_page(viewport={"width": 1400, "height": 900})
        old.set_content("<html><body></body></html>")
        old.add_script_tag(content=_old("cli/viewer/static/layout.js"))
        old.evaluate(_RAF)
        old.wait_for_timeout(300)
        ob = old.evaluate("""(G) => { const on = G.nodes.filter((n) => G.anchor[n.id]);
            const t0 = performance.now(); const pos = layoutForce(on, G.edges, layoutSkel(on, G.edges, G.anchor));
            return {ms: Math.round(performance.now() - t0), cut: LSTAT.forceCut, it: LSTAT.forceIter, pos}; }""", G)
        old.wait_for_timeout(300)
        old_gap = old.evaluate(_RAF_STOP)
        m_old = metrics(G, ob["pos"])
        old.close()
        # 지금 — 화면 데이터를 창작 그래프로 바꿔 띄운다(서버 함수 하나 · 쓰기 0)
        VS.D.graph = lambda G=G: G
        pg = br.new_page(viewport={"width": 1400, "height": 900})
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: ext.append(r.url) if not r.url.startswith(url) else None)
        pg.goto(url)
        pg.wait_for_function("() => S.sigma && S.gr && S.gr.order > 0", timeout=120000)
        pg.evaluate(_RAF)
        t0 = time.perf_counter()
        pg.click("#layout-pick input[value='힘']")
        pg.wait_for_function("() => LSTAT.forceState === '끝'", timeout=600000)
        wall = round(time.perf_counter() - t0, 1)
        new_gap = pg.evaluate(_RAF_STOP)
        st = pg.evaluate("() => ({pos: S.pos, it: LSTAT.forceIter, max: LSTAT.forceMax, ms: LSTAT.forceMs, "
                         "frames: LSTAT.frames})")
        m_new = metrics(G, st["pos"])
        pg.screenshot(path=str(SHOTS / f"b114_01_힘_큰그래프_{len(G['nodes'])}.png"))
        print(f"  노드 {len(G['nodes'])} · 엣지 {len(G['edges'])}")
        print(f"    고치기 전 — {m_old} · 배치 {ob['ms']}ms(시간 예산 4000ms에 걸림 {ob['cut']} · 반복 {ob['it']}/300) · "
              f"가장 긴 프레임 틈 {old_gap}ms")
        print(f"    고친 뒤   — {m_new} · 워커 {st['ms']}ms · 반복 {st['it']}/{st['max']} · 프레임 {st['frames']} · "
              f"가장 긴 프레임 틈 {new_gap}ms · 클릭부터 끝까지 {wall}초")
        rows.append((len(G["nodes"]), m_old, m_new, ob, st, old_gap, new_gap))
        if k == 0:
            first_pg = pg
        else:
            pg.close()
    pg = first_pg
    show("ⓐ 원 모양으로 굳지 않는다(크기 둘) — 연결 쌍이 상대적으로 가깝다(연결/비연결 거리 비가 작다) · 중심에서의 반지름이 "
         "고르지 않다(반지름 변동계수가 크다 — 줄 지어 붙인 원판 · 고리가 아니다) · 반복을 끝까지 돈다",
         all(r[2]["연결/비연결"] < r[1]["연결/비연결"] and r[2]["반지름CV"] > r[1]["반지름CV"]
             and r[4]["it"] == r[4]["max"] for r in rows),
         " ‖ ".join(f"노드 {n}: 연결/비연결 {o['연결/비연결']} → {w['연결/비연결']} · 반지름CV {o['반지름CV']} → "
                    f"{w['반지름CV']} · 고리CV {o['고리CV']} → {w['고리CV']} · 고치기 전 예산에 걸림 {ob['cut']}"
                    for n, o, w, ob, _st, _g1, _g2 in rows))
    show("ⓐ 화면이 멈추지 않는다 — 배치 중 가장 긴 프레임 틈이 고치기 전(화면 스레드에서 계산)보다 짧다 · 워커가 프레임을 "
         "이어서 보낸다(크기 둘)", all(r[6] < r[5] and r[4]["frames"] >= 10 for r in rows),
         " ‖ ".join(f"노드 {n}: {g1}ms → {g2}ms · 프레임 {st['frames']}" for n, _o, _w, _ob, st, g1, g2 in rows))
    same = pg.evaluate("""async () => { const nodes = shownNodes(), ids = new Set(nodes.map((n) => n.id));
        const edges = S.graph.edges.filter((e) => ids.has(e.src) && ids.has(e.dst));
        const seed = layoutForce(nodes, edges, S.graph.anchor);
        const run = (it) => new Promise((res) => forceStart(nodes, edges, seed,
            (m) => { if (m.done) res(Array.from(m.x).join() + "|" + Array.from(m.y).join()); }, {iterations: it}));
        const a = await run(300), b = await run(300), c = await run(301);
        forceStop(); return {same: a === b, differs: a !== c, n: nodes.length}; }""")
    show("ⓐ 같은 시드 · 같은 반복이면 같은 좌표(300회 두 번 — 글자 그대로) · 반복이 다르면 다르다(301회)",
         same["same"] and same["differs"], json.dumps(same))
    VS.D.graph = real_graph
    pg.close()

    # ── ⓑ 크기 · 라벨 (mock 그래프)
    pg = br.new_page(viewport={"width": 1400, "height": 900})
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    reqs = []
    pg.on("request", lambda r: (reqs.append(r.url), ext.append(r.url) if not r.url.startswith(url) else None))
    pg.goto(url)
    pg.wait_for_function("() => S.sigma && S.gr && S.gr.order > 0", timeout=60000)
    old_src = _old("cli/viewer/static/render.js")
    ot = {k: int(v) for k, v in re.findall(r"(main|sub|detail): (\d+)", old_src.split("const TIER_SIZE", 1)[1][:80])}
    o_other = int(re.search(r"TIER_SIZE\[n\.tier\] \|\| (\d+)", old_src).group(1))
    sz = pg.evaluate("""() => { const by = {}; S.graph.nodes.forEach((n) => {
        const d = S.sigma.getNodeDisplayData(n.id); if (!d) return; by[n.tier || "그 밖"] = d.size; }); return by; }""")
    r_old = {"main/그 밖": round(ot["main"] / o_other, 2), "main/detail": round(ot["main"] / ot["detail"], 2),
             "detail/그 밖": round(ot["detail"] / o_other, 2)}
    r_new = {"main/그 밖": round(sz["main"] / sz["그 밖"], 2), "main/detail": round(sz["main"] / sz["detail"], 2),
             "detail/그 밖": round(sz["detail"] / sz["그 밖"], 2)}
    show("ⓑ 크기 — tier마다 크기 비가 고치기 전보다 크다(골격 밖이 detail보다 컸던 뒤집힘도 없다) · 범례에 크기 뜻",
         all(r_new[k] > r_old[k] for k in r_old) and r_new["detail/그 밖"] > 1
         and pg.evaluate("() => $('#size-legend').querySelectorAll('.dot').length") == 4,
         f"고치기 전 {r_old} → 고친 뒤 {r_new}(그리는 크기 · 배율 무관)")
    lb = pg.evaluate("""() => { const n = S.graph.nodes.find((x) => x.name.includes('::') && x.status !== 'seed')
            || S.graph.nodes.find((x) => x.name.includes('::'));
        const lab = () => S.sigma.getNodeDisplayData(n.id).label;
        const short = lab();
        S.hover = n.id; S.neighbors = neighborsOf(n.id); restyle(); const hover = lab();
        S.hover = null; S.neighbors = null; restyle();
        detail(n); const det = document.querySelector('#detail h3').textContent;
        S.search = n.name.split('::').slice(0, 2).join('::').toLowerCase(); restyle(); const srch = lab();
        S.search = ''; restyle();
        const fl = document.querySelector('#full-labels'); fl.click(); const full = lab(); fl.click();
        return {name: n.name, short, hover, det, srch, full, back: lab()}; }""")
    show("ⓑ 라벨 — 끝 조각(`::` 뒤) · 올린 점 · 상세 · 검색에 걸린 점 · 「전체 이름」 토글은 전체 이름",
         lb["short"] == lb["name"].split("::")[-1] and lb["hover"] == lb["det"] == lb["srch"] == lb["full"] == lb["name"]
         and lb["back"] == lb["short"], json.dumps(lb, ensure_ascii=False))
    pg.screenshot(path=str(SHOTS / "b114_02_크기_라벨.png"))

    # ── ⓓ 질의 상태 줄 · 엔터 — 단계마다 0.6초 머물게(시험 손잡이 · 서버 함수 하나) · 폴링이 단계를 따라간다
    real_stage = QS.stage

    def slow_stage(name):
        real_stage(name)
        time.sleep(0.6)
    QS.stage = slow_stage
    shutil.rmtree(_P.vectors(), ignore_errors=True)       # 벡터 준비가 실제로 돌게(파생물)
    pg.click('#tabs button[data-tab="query"]')
    pg.evaluate("""() => { window.__stages = []; const box = document.querySelector('#qstatus');
        new MutationObserver(() => { const s = box.dataset.stage; if (s && window.__stages[window.__stages.length - 1] !== s)
            window.__stages.push(s); }).observe(box, {attributes: true, childList: true, subtree: true}); }""")
    n_req = len(reqs)
    pg.fill("#q", "노칭 다음 공정은?")
    pg.press("#q", "Enter")
    pg.wait_for_function("() => !S.asking && document.querySelector('#qstatus').dataset.stage === '끝'", timeout=60000)
    QS.stage = real_stage
    seen = pg.evaluate("() => window.__stages")
    line = pg.evaluate("() => document.querySelector('#qstatus').textContent")
    asked = [u for u in reqs[n_req:] if "/api/query?q=" in u]
    polls = [u for u in reqs[n_req:] if u.endswith("/api/status")]
    show("ⓓ 엔터로 묻는다 — 버튼을 누르지 않고 입력 칸에서 Enter · 질의 요청 1건",
         len(asked) == 1, asked[0].replace(url, "/") if asked else "요청 없음")
    show("ⓓ 상태 줄이 단계를 따라 바뀐다 — 벡터 준비 → 링킹 → 확장 → 수집 → 답변 → 끝 · GET 폴링 · 경과 초",
         [s for s in seen if s] == list(QS.STAGES) + ["끝"] and len(polls) >= 5 and "경과" in line,
         f"{' → '.join(seen)} · 폴링 {len(polls)}회 · 「{line.strip()[:120]}」")
    pg.screenshot(path=str(SHOTS / "b114_03_질의_상태.png"))
    pg.close()
    br.close()

# ── ⓒ 벡터 — 이어 만들기 · 진행 줄 · 묶음 (화면 밖 — 같은 함수)
print("\n■ B114 ④ 벡터 준비 — 이어 만들기 · 진행 줄 · 묶음")
shutil.rmtree(_P.vectors(), ignore_errors=True)
lines = []
V.ON_PROGRESS = lines.append
V.SAVE_EVERY, _real_many, calls = 16, E.embed_many, [0]


def _broken(texts, batch=32):
    calls[0] += 1
    if calls[0] > 3:
        raise KeyboardInterrupt("끊음(시험)")
    return _real_many(texts, batch)


E.embed_many = _broken
try:
    V.begin()                                             # 질의 한 건처럼 — 계측은 그 질의의 몫
    H.warm()
except KeyboardInterrupt:
    pass
E.embed_many = _real_many
saved = V.count("nodes")             # 저장은 sqlite 하나(B136 ③)
V.begin()
H.warm()
again = dict(V.STATS["nodes"])
resumed = V.fingerprint("nodes")
shutil.rmtree(_P.vectors(), ignore_errors=True)
V.SAVE_EVERY = 256
V.begin()
H.warm()
clean = V.fingerprint("nodes")
total = again["made"] + again["reused"]
show("ⓒ 끊었다 다시 치면 이어 간다 — 저장된 몫은 재사용 · 만든 수가 0부터가 아니다 · 이어 만든 파일 = 처음부터 만든 파일",
     saved == 48 and again["reused"] == saved and again["made"] == total - saved and resumed == clean,
     f"끊기 전 저장 {saved} · 다시 — 만든 {again['made']} · 재사용 {again['reused']} / 전체 {total} · 파일 같음 {resumed == clean}")
pat = re.compile(r"^벡터 — 노드 [\d,]+/[\d,]+ · 청크 [\d,]+/[\d,]+ · 경과 [\d.]+초 · 남은 예상 (—|[\d.]+초)$")
show("ⓒ 진행 줄 — 「벡터 — 노드 n/m · 청크 n/m · 경과 · 남은 예상」(저장마다)",
     lines and all(pat.match(x) for x in lines), f"{len(lines)}줄 · 예 「{lines[0] if lines else ''}」")
V.ON_PROGRESS = None

shutil.rmtree(_P.vectors(), ignore_errors=True)
env = {**os.environ, "USE_MOCK": "1"}
cli1 = subprocess.run([sys.executable, str(ROOT / "run.py"), "query", "노칭 다음 공정은?", "--allow-mock"], cwd=ROOT, env=env,
                      capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
cli2 = subprocess.run([sys.executable, str(ROOT / "run.py"), "query", "노칭 다음 공정은?", "--allow-mock"], cwd=ROOT, env=env,
                      capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
p1 = [x.strip() for x in cli1.splitlines() if pat.match(x.strip())]
show("ⓒ CLI — 벡터를 만드는 질의는 진행 줄 · 다 있으면 진행 줄 0(재사용만)",
     p1 and not [x for x in cli2.splitlines() if pat.match(x.strip())] and "노드 만든 0" in cli2
     and re.search(r"노드 만든 [1-9]", cli1),
     f"{p1[-1] if p1 else ''} / 끝 줄 「{next((x.strip() for x in cli1.splitlines() if '만든' in x), '')}」 / 둘째 "
     f"「{next((x.strip() for x in cli2.splitlines() if '만든' in x), '')}」")
shutil.rmtree(_P.vectors(), ignore_errors=True)
vp = subprocess.Popen([sys.executable, str(ROOT / "run.py"), "viewer", "--no-browser", "--port", str(PORT + 1)],
                      cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                      stdin=subprocess.DEVNULL)
con = []
t_end = time.time() + 60
while time.time() < t_end:
    ln = vp.stdout.readline()
    if not ln:
        break
    con.append(ln.rstrip())
    if "벡터 준비" in ln:
        break
vp.terminate()
vp.wait(timeout=10)
addr = next((i for i, x in enumerate(con) if x.startswith("[viewer] http")), -1)
vline = [i for i, x in enumerate(con) if "[viewer] 벡터 —" in x or "벡터 준비 끝" in x]
show("ⓒ 서버 콘솔 — 주소를 먼저 띄우고 배경으로 벡터를 만든다 · 진행 줄 · 끝 줄",
     addr >= 0 and vline and min(vline) > addr and any("벡터 준비 끝" in con[i] for i in vline),
     " / ".join(con[i].strip() for i in vline[-2:]))

# 묶음 — 로컬 갈래의 스텁 모델(호출마다 4ms + 항목마다 0.2ms — 창작 · 값은 근거가 아니다)


class _ST:
    calls = 0

    def __init__(self, path):
        self.device = "cpu"

    def encode(self, texts, batch_size=32, normalize_embeddings=True):
        one = isinstance(texts, str)
        items = [texts] if one else list(texts)
        out = []
        for s in range(0, len(items), batch_size):
            part = items[s:s + batch_size]
            _ST.calls += 1
            time.sleep(0.004 + 0.0002 * len(part))
            out += [E._mock_vector(t, 16) for t in part]
        return out[0] if one else out


_mod = types.ModuleType("sentence_transformers")
_mod.SentenceTransformer = _ST
sys.modules["sentence_transformers"] = _mod
_tmp = Path(tempfile.mkdtemp(prefix="b114_model_"))
_saved = (gateway.use_mock, gateway.config, gateway.require)
gateway.use_mock = lambda: False
gateway.config = lambda: {"embed_backend": "local", "embed_model": str(_tmp)}
gateway.require = lambda point, need=(): {"embed_model": str(_tmp)}
texts = [f"창작 문장 {i}" for i in range(400)]
try:
    t1 = time.perf_counter()
    one = [E.embed(t) for t in texts]
    t_one, c_one = time.perf_counter() - t1, _ST.calls
    _ST.calls = 0
    t2 = time.perf_counter()
    many = E.embed_many(texts, V.BATCH)
    t_many, c_many = time.perf_counter() - t2, _ST.calls
finally:
    gateway.use_mock, gateway.config, gateway.require = _saved
    E._LOCAL = (None, None)
    sys.modules.pop("sentence_transformers", None)
    shutil.rmtree(_tmp, ignore_errors=True)
show("ⓒ 묶음 — 로컬 갈래는 묶어 부른다(호출 수 · 시간이 준다 · 같은 벡터) — 스텁 모델 · 창작 표본",
     c_many < c_one and t_many < t_one and many == one,
     f"한 건씩 {c_one}호출 {t_one:.2f}초 → 묶음({V.BATCH}) {c_many}호출 {t_many:.2f}초")

# ── ⓔ 쓰기 0 · 외부 URL 0 · 콘솔 오류 0
show("ⓔ 쓰기 0 — 화면 · 질의 · 벡터를 도는 동안 ③진실 · ②등록 해시 불변(벡터는 ④ 파생물)", _state_hash() == H0)
show("ⓔ 외부 URL 0 — 화면이 부른 요청이 전부 이 서버", not ext, str(ext[:3]))
show("ⓔ 콘솔 오류 0 (전 구간)", not errs, str(errs[:3]))
srv.shutdown()
print(f"\n  스크린샷 — {SHOTS}")
print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어 브라우저 실측 B114 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
