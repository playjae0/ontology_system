# -*- coding: utf-8 -*-
"""칸 5.3 — 뷰어 **브라우저 실측 B103**: 골격+위성 · 힘 · 탐색 · 노드 상세의 근거 · 질의 배지.

`viewer_browser.py`와 같은 처지다(D-165 ②) — Playwright·Chromium이 있어야 하고 사내 클론에는 없어
**회귀(`doctor.py`)에 넣지 않는다**. 회귀에는 브라우저 없이 재는 성질(닻 규칙 · 연결 없는 노드 수 · 이웃 ·
상세 · 손잡이)만 둔다(`tests/test_viewer.py`). 여기 것은 회차 보고에 실행 결과로 붙인다.

표본은 **창작**이다 — mock 그래프(CP01·PFMEA01·PPT01~03·QPPT01) + 엣지 없는 노드 1 · 골격에 안 닿는 덩어리 1
(품질층 산문 `B103DET` — 좌표 없는 청크의 불량 · 섬은 GraphStore로 놓은 불량 둘 + `causes`). 수치는 메커니즘 확인이다([정정] 50).

재는 것(완료판정):
  ⓐ 골격+위성 — 같은 입력 두 번 같은 좌표 · 골격은 나무(부모가 자식보다 위) · 위성은 제 닻이 가장 가까운
     골격 · 닻 없는 노드는 기본 숨김 · 토글 수(엣지 없음) = 서버가 준 수 = B102 끝 요약 「엣지 없는 노드」
  ⓑ 힘 — 같은 입력 같은 좌표 · 덩어리 경계 상자 겹침 0 · 닻 없는 노드 제외
  ⓒ 탐색 — 펼치기(이웃 = 서버) · 더 펼치기 · 접기 · 빵부스러기 · 전체 복귀 · 문턱 손잡이로 첫 화면이 탐색
  ⓓ 노드 상세 — 원문 전부 · 닻까지의 길 · 붙은 자리(target · attached · from)
  ⓔ 질의 배지 — mock과 live(가짜 게이트웨이) · 링킹 LLM 폴백 문항에서 b ≥ 1
  ⓕ 쓰기 0 · 외부 URL 0

사용: python tests/viewer_browser_b103.py   (스크린샷은 `$ONTO_HOME/export/viewer_shots/`)
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover
    print("■ 뷰어 브라우저 실측 B103 — **건너뛴다**: playwright가 없다.")
    sys.exit(0)

from g65_common import *                                  # noqa: E402,F401,F403 — 바닥은 하나다
from g65_common import _P                                 # noqa: E402
from core.build import ledger as LG                       # noqa: E402
from core.llm import gateway                              # noqa: E402
from cli.viewer import server as VS                       # noqa: E402

allok = True
PORT = 8871
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


HINTS = ROOT / "tests" / "fixtures" / "extract_hints"
DET = "B103DET"


def _state_hash():
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in (_P.data(), _P.registry()) if base.exists()
            for p in sorted(base.rglob("*")) if p.is_file()}


# ── 표본 — mock 그래프 + 연결 없는 노드(엣지 없음 1 · 섬 1)
with contextlib.redirect_stdout(io.StringIO()):
    fresh()
(HINTS / f"{DET}.json").write_text(json.dumps({
    f"{DET}-C001": {"entities": [{"surface": "B103 고립 불량", "category": "Failure"}], "relations": [], "attach": []},
}, ensure_ascii=False), encoding="utf-8")
_env = {**PROSE, "doc_id": DET, "source_path": f"{DET}.pptx",
        "chunks": [{**C1, "source_locator": f"{DET}-C001", "process_ref": None, "process_group": None,
                    "text": "B103 고립 불량 이야기"}]}
with contextlib.redirect_stdout(io.StringIO()):
    run_document(_env)
(HINTS / f"{DET}.json").unlink(missing_ok=True)
# 섬 — 골격에 닿지 않는 두 노드 + 엣지 하나(GraphStore로 직접 놓는다 · 창작 표본)
_q = open_graph("quality")
_i1 = _q.add_node("B103 섬 불량 가", "Failure", "auto", provenance=["B103ISL#1"])
_i2 = _q.add_node("B103 섬 불량 나", "Failure", "auto", provenance=["B103ISL#2"])
_q.add_edge(_i1, "causes", _i2, "auto", provenance=["B103ISL#1"])
_q.save()
LANDING = ((LG.read(DET) or {}).get("result") or {}).get("엣지 없는 노드")
H0 = _state_hash()

SHOTS = _P.export("viewer_shots")
_P.ensure(SHOTS)
srv, url = VS.serve(PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"\n■ B103 — 뷰어 브라우저 실측 ({url})")

_JS_K = "(p) => Object.entries(p).sort().map(([i, v]) => i + ':' + v.x.toFixed(6) + ',' + v.y.toFixed(6)).join('|')"

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME if Path(CHROME).exists() else None,
                                     args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        pg = ctx.new_page()
        errs, reqs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        pg.on("request", lambda r: reqs.append(r.url))
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(2500)

        # ── ⓐ 골격 + 위성
        a = pg.evaluate("""(K) => { const k = eval(K);
            const on = S.graph.nodes.filter((n) => S.graph.anchor[n.id]);
            const p1 = layoutSkel(on, S.graph.edges, S.graph.anchor), p2 = layoutSkel(on, S.graph.edges, S.graph.anchor);
            const sk = on.filter((n) => n.status === 'seed');
            let tree = 0, treeBad = 0, sat = 0, satBad = 0, worst = '';
            S.graph.edges.forEach((e) => { const s = sk.find((n) => n.id === e.src), d = sk.find((n) => n.id === e.dst);
              if (e.rel === 'part_of' && s && d) { tree++; if (!(p1[d.id].y > p1[s.id].y)) treeBad++; } });
            on.filter((n) => n.status !== 'seed').forEach((n) => { sat++;
              const an = S.graph.anchor[n.id].anchor, P = p1[n.id];
              const da = Math.hypot(P.x - p1[an].x, P.y - p1[an].y);
              sk.forEach((s) => { if (s.id !== an) { const d = Math.hypot(P.x - p1[s.id].x, P.y - p1[s.id].y);
                if (d <= da) { satBad++; worst = n.name + ' ' + da.toFixed(2) + '≥' + d.toFixed(2); } } }); });
            const shown = new Set(S.gr.nodes());
            const det = S.graph.detached;
            return {same: k(p1) === k(p2), tree, treeBad, sat, satBad, worst,
                    hidden: [...det.edgeless, ...det.island].every((i) => !shown.has(i)),
                    edgeless: det.edgeless.length, island: det.island.length,
                    label: document.querySelector('#detached-label').textContent,
                    layout: S.layout, stat: document.querySelector('#head-stat').textContent}; }""", _JS_K)
        show("ⓐ 골격+위성이 기본 배치 · 두 번 계산 좌표 diff 0", a["layout"] == "골격+위성" and a["same"],
             a["stat"])
        show("ⓐ 골격은 나무 — 골격 사이 part_of의 부모가 자식보다 위 (전부)", a["tree"] > 0 and a["treeBad"] == 0,
             f"골격 part_of {a['tree']} · 어긋남 {a['treeBad']}")
        show("ⓐ 위성은 닻 둘레 — 닻까지 거리 < 다른 골격 노드까지 거리 (전부)", a["sat"] > 0 and a["satBad"] == 0,
             f"위성 {a['sat']} · 어긋남 {a['satBad']} {a['worst']}")
        show("ⓐ 닻 없는 노드는 기본 숨김 · 토글 수(엣지 없음) = 서버 수 = B102 끝 요약 「엣지 없는 노드」",
             a["hidden"] and a["edgeless"] == LANDING == 1 and a["island"] == 2
             and f"엣지 없음 {a['edgeless']}" in a["label"],
             f"{a['label'].strip()} · B102 끝 요약({DET}) 엣지 없는 노드 {LANDING}")
        pg.screenshot(path=str(SHOTS / "b103_01_골격위성.png"))
        pg.check("#show-detached"); pg.wait_for_timeout(800)
        a2 = pg.evaluate("""() => { const det = S.graph.detached; const shown = new Set(S.gr.nodes());
            const ids = [...det.edgeless, ...det.island];
            const ys = S.gr.nodes().filter((i) => !ids.includes(i)).map((i) => S.gr.getNodeAttribute(i, 'y'));
            return {all: ids.every((i) => shown.has(i)),
                    below: ids.every((i) => S.gr.getNodeAttribute(i, 'y') < Math.min(...ys))}; }""")
        show("ⓐ 토글을 켜면 연결 없는 노드가 나무 아래 띠에 모인다", a2["all"] and a2["below"], json.dumps(a2))
        pg.screenshot(path=str(SHOTS / "b103_02_연결없는노드.png"))
        pg.uncheck("#show-detached"); pg.wait_for_timeout(500)

        # ── ⓑ 힘
        b = pg.evaluate("""(K) => { const k = eval(K);
            const on = S.graph.nodes.filter((n) => S.graph.anchor[n.id]);
            const seed = layoutSkel(on, S.graph.edges, S.graph.anchor);
            const f1 = layoutForce(on, S.graph.edges, seed), f2 = layoutForce(on, S.graph.edges, seed);
            const comps = _components(on, S.graph.edges.filter((e) => f1[e.src] && f1[e.dst]));
            const bb = comps.map((c) => { const v = c.map((n) => f1[n.id]);
              return [Math.min(...v.map((q) => q.x)), Math.min(...v.map((q) => q.y)),
                      Math.max(...v.map((q) => q.x)), Math.max(...v.map((q) => q.y))]; });
            let ov = 0; for (let i = 0; i < bb.length; i++) for (let j = i + 1; j < bb.length; j++) {
              const A = bb[i], B = bb[j]; if (A[0] <= B[2] && B[0] <= A[2] && A[1] <= B[3] && B[1] <= A[3]) ov++; }
            const det = S.graph.detached;
            return {same: k(f1) === k(f2), comps: comps.length, ov, cut: LSTAT.forceCut, it: LSTAT.forceIter,
                    ms: LSTAT.forceMs, excl: [...det.edgeless, ...det.island].every((i) => !f1[i])}; }""", _JS_K)
        show("ⓑ 힘 — 같은 입력 같은 좌표(시간 예산 안) · 덩어리 경계 상자 겹침 0 · 닻 없는 노드 제외",
             b["same"] and not b["cut"] and b["ov"] == 0 and b["excl"],
             f"덩어리 {b['comps']} · 겹침 {b['ov']} · 반복 {b['it']} · {b['ms']}ms · 예산에 걸림 {b['cut']}")
        pg.click("#layout-pick input[value='힘']"); pg.wait_for_timeout(1500)
        pg.screenshot(path=str(SHOTS / "b103_03_힘.png"))
        pg.click("#layout-pick input[value='골격+위성']"); pg.wait_for_timeout(800)

        # ── ⓒ 탐색
        root = pg.evaluate("() => S.graph.roots[0]")
        n0 = len(reqs)
        pg.evaluate("(id) => exploreFrom(id)", root); pg.wait_for_timeout(800)
        c1 = pg.evaluate("""() => ({shown: S.gr.nodes().length, trail: S.explore.trail.length,
            added: S.explore.trail[0].added.slice().sort(), crumbs: document.querySelector('#crumbs').textContent,
            hidden: document.querySelector('#crumbs').hidden})""")
        nb = VS.D.neighbors(root)
        show("ⓒ 여기서 펼치기 — 그 노드 + 1홉 이웃(서버가 준 이웃 그대로) · 빵부스러기",
             c1["added"] == sorted(nb["neighbors"]) and c1["shown"] <= 1 + len(nb["neighbors"])
             and not c1["hidden"] and c1["trail"] == 1
             and any("/api/neighbors/" in u for u in reqs[n0:]),
             f"보이는 노드 {c1['shown']} · {c1['crumbs'][:80]}")
        nxt = c1["added"][0]
        pg.evaluate("(id) => exploreFrom(id)", nxt); pg.wait_for_timeout(800)
        c2 = pg.evaluate("() => ({shown: S.gr.nodes().length, trail: S.explore.trail.length})")
        pg.click("#crumbs button:has-text('접기')"); pg.wait_for_timeout(600)
        c3 = pg.evaluate("() => ({shown: S.gr.nodes().length, trail: S.explore.trail.length})")
        pg.evaluate("(id) => exploreFrom(id)", nxt); pg.wait_for_timeout(600)
        pg.click("#crumbs a.crumb >> nth=0"); pg.wait_for_timeout(600)
        c4 = pg.evaluate("() => ({trail: S.explore.trail.length, shown: S.gr.nodes().length})")
        pg.screenshot(path=str(SHOTS / "b103_04_탐색.png"))
        pg.click("#crumbs button:has-text('전체')"); pg.wait_for_timeout(800)
        c5 = pg.evaluate("() => ({explore: S.explore, shown: S.gr.nodes().length, hidden: document.querySelector('#crumbs').hidden})")
        show("ⓒ 더 펼치기 · 접기 · 빵부스러기로 돌아가기 · 전체 복귀",
             c2["trail"] == 2 and c2["shown"] >= c1["shown"] and c3 == {"shown": c1["shown"], "trail": 1}
             and c4 == {"trail": 1, "shown": c1["shown"]} and c5["explore"] is None and c5["hidden"]
             and c5["shown"] == pg.evaluate("() => S.graph.nodes.filter((n) => S.graph.anchor[n.id]).length"),
             f"펼침 {c1['shown']} → 더 {c2['shown']} → 접기 {c3['shown']} → 빵 {c4['shown']} → 전체 {c5['shown']}")

        # 문턱 손잡이 — 노드 수가 `viewer_explore_threshold`를 넘으면 첫 화면이 골격 뿌리부터 탐색 모드
        from core.state import knobs as KB
        _P.knobs().write_text(json.dumps({"viewer_explore_threshold": 10}), encoding="utf-8")
        KB.apply()
        pg.reload(wait_until="load"); pg.wait_for_timeout(2500)
        kx = pg.evaluate("""() => ({on: !!S.explore, trail: S.explore ? S.explore.trail.map((t) => t.id) : [],
            roots: S.graph.roots, th: S.graph.explore_threshold, n: S.graph.nodes.length, shown: S.gr.nodes().length})""")
        _P.knobs().unlink(missing_ok=True)
        KB.apply()
        pg.reload(wait_until="load"); pg.wait_for_timeout(2500)
        kd = pg.evaluate("() => ({on: !!S.explore, th: S.graph.explore_threshold})")
        show("ⓒ 문턱 손잡이 — knobs.json `viewer_explore_threshold` 10이면 첫 화면이 골격 뿌리부터 탐색 · 지우면 기본(1500)으로 전체",
             kx["on"] and kx["trail"] == kx["roots"] and kx["th"] == 10 and kx["shown"] < kx["n"]
             and not kd["on"] and kd["th"] == 1500,
             f"문턱 {kx['th']} · 노드 {kx['n']} → 첫 화면 {kx['shown']}(뿌리 {len(kx['roots'])}) · 지운 뒤 문턱 {kd['th']} 탐색 {kd['on']}")

        # ── ⓓ 노드 상세의 근거
        # 근거 청크가 있고 닻이 한 홉 이상인 산문 노드(서버가 준 상세로 고른다 — 화면은 그것을 그린다)
        _g = VS.D.graph()
        nid = next(n["id"] for n in sorted(_g["nodes"], key=lambda n: n["name"])
                   if (_g["anchor"].get(n["id"]) or {}).get("hops", 0) >= 1 and (VS.D.node(n["id"]) or {}).get("evidence"))
        pg.evaluate("(id) => detail(S.graph.nodes.find((n) => n.id === id))", nid)
        pg.wait_for_timeout(1200)
        api = VS.D.node(nid)
        d = pg.evaluate("""() => { const box = document.querySelector('#detail');
            const pre = [...box.querySelectorAll('pre.src')].map((p) => p.textContent);
            const path = (box.querySelector('.card.path') || {}).textContent || '';
            const landed = [...box.querySelectorAll('.card')].map((c) => c.textContent).filter((t) => t.includes(' → '));
            return {pre, path, landed, h: [...box.querySelectorAll('h3')].map((h) => h.textContent)}; }""")
        full = all(t in d["pre"] for t in (e["text"] for e in api["evidence"]))
        st = api["anchor_path"]["steps"] if api["anchor_path"] else []
        show("ⓓ 노드 상세 — 근거 원문 전부(접기 · 서버 원문과 글자 그대로) · 닻까지의 길(관계 이름 그대로)",
             api["evidence"] and full and api["anchor_path"] and all(s["rel"] in d["path"] for s in st)
             and api["anchor_path"]["anchor_name"] in d["path"],
             f"근거 {len(d['pre'])}/{api['evidence_total']} · 길 {d['path'][:90]}")
        tg = [r for r in api["landed"] if r.get("target")]
        show("ⓓ 붙은 자리 — 문서마다 「표기 → 붙은 노드 [판정 · 경로]」 + 「└ 관계 → 상대」(대장 target · attached · from)",
             tg and all(f"{r['surface']} → {r['target']}" in " ".join(d["landed"]) for r in tg)
             and any("└" in t for t in d["landed"]) == any(r["attached"] for r in tg),
             (d["landed"] or [""])[0][:120])
        pg.screenshot(path=str(SHOTS / "b103_05_노드상세.png"))

        # ── ⓔ 질의 배지 — mock
        pg.click('#tabs button[data-tab="query"]')
        pg.fill("#q", "노칭 다음 공정은?"); pg.press("#q", "Enter"); pg.wait_for_timeout(1500)
        qm = pg.evaluate("() => document.querySelector('#qllm').textContent")
        show("ⓔ 질의 배지(mock) — 모드 · 링킹 사전 a · LLM 폴백 0 · 답변 정형 나열",
             qm.startswith("mock") and "LLM 폴백 0" in qm and "정형 나열(mock)" in qm, qm)
        pg.screenshot(path=str(SHOTS / "b103_06_질의_mock.png"))
        # live — 가짜 게이트웨이(같은 프로세스의 서버가 이 함수들을 부른다)
        live_node = pg.evaluate("() => S.graph.nodes.find((n) => n.name === '노칭').id")
        keep = (gateway.use_mock, gateway.chat, gateway.require, gateway.prompt)
        calls = []

        def _chat(msgs, json_schema=None, point=None, **k):
            calls.append(point)
            if point == "link":
                return {"node_ids": [live_node]}
            if point == "answer":
                return {"answer": "가짜 게이트웨이의 답", "used_facts": []}
            return {}
        gateway.use_mock, gateway.chat = (lambda: False), _chat
        gateway.require, gateway.prompt = (lambda *x, **k: None), (lambda name: f"지시문 {name}")
        try:
            pg.fill("#q", "B103 사전에 없는 말로 묻는다"); pg.press("#q", "Enter"); pg.wait_for_timeout(2500)
            ql = pg.evaluate("() => document.querySelector('#qllm').textContent")
        finally:
            gateway.use_mock, gateway.chat, gateway.require, gateway.prompt = keep
        show("ⓔ 질의 배지(live · 가짜 게이트웨이) — 링킹 LLM 폴백 b ≥ 1 · 답변 LLM(live)",
             ql.startswith("live") and "LLM 폴백 1" in ql and "LLM(live)" in ql and "link" in calls,
             f"{ql} · 호출 {calls}")
        pg.screenshot(path=str(SHOTS / "b103_07_질의_live.png"))

        # ── ⓕ
        show("ⓕ 쓰기 0 — 화면을 도는 동안 ③진실·②등록 해시 불변", _state_hash() == H0)
        ext = [u for u in reqs if not u.startswith(url)]
        show("ⓕ 외부 URL 0 — 화면이 부른 요청이 전부 이 서버", not ext, str(ext[:2]))
        show("ⓕ 콘솔 오류 0 (전 구간)", not errs, str(errs[:1]))
        ctx.close(); browser.close()
finally:
    srv.shutdown()
    srv.server_close()

print(f"\n  스크린샷 — {SHOTS}")
print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어 브라우저 실측 B103 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
