# -*- coding: utf-8 -*-
"""칸 5.2·5.3 — 뷰어 **브라우저 실측**: 테마 기억 · 검색 계측 · 배치 결정성 · 상호작용 (B84).

**회귀(`doctor.py`)에 넣지 않는다**(D-165 ②): 이 스위트는 Playwright와 Chromium을
요구하고 사내 클론에는 둘 다 없다 — 없는 것을 PASS로 세면 회귀가 거짓말한다.
회귀에는 브라우저 없이 재는 성질만 두고(`tests/test_viewer.py`), 여기 것은 **회차
보고에 실행 결과로** 붙인다. 브라우저가 없으면 **그 사실을 말하고** 종료한다.

재는 것은 성질이다 — 색 문자열·호출 수·좌표·요청 수. 화면 캡처를 비교하지 않는다.

사용: python tests/viewer_browser.py   (스크린샷은 `$ONTO_HOME/export/viewer_shots/`)
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import paths as _P                                         # noqa: E402
from cli.viewer import server as VS                                  # noqa: E402

allok = True
PORT = 8847
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover
    print("■ 뷰어 브라우저 실측 — **건너뛴다**: playwright가 없다.")
    print("   설치: pip install playwright && playwright install chromium")
    print("   (이 스위트는 회귀에 들어가지 않는다 — 회귀는 브라우저 없이 잰다)")
    sys.exit(0)


def _luma(hex_color):
    """상대 휘도 — WCAG 정의 그대로(대비비 계산의 재료)."""
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in parts]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def contrast(a, b):
    la, lb = _luma(a), _luma(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


SHOTS = _P.export("viewer_shots")
_P.ensure(SHOTS)                     # 폴더를 만드는 자리는 하나다 (B77 ④)

srv, url = VS.serve(PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"\n■ B84 — 뷰어 브라우저 실측 ({url})")

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME if Path(CHROME).exists() else None,
            args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}")
              if m.type == "error" else None)
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(2500)

        boot = pg.evaluate("""() => ({
            theme: document.documentElement.dataset.theme,
            sigma: !!S.sigma, warn: document.querySelector('#webgl-warn').hidden,
            stat: document.querySelector('#head-stat').textContent,
            rstat: {...RSTAT}})""")
        show("기동 — 밝은 테마로 뜨고 sigma가 한 번 선다 (경고 없음)",
             boot["theme"] == "light" and boot["sigma"] and boot["warn"]
             and boot["rstat"]["sigma"] == 1, json.dumps(boot, ensure_ascii=False))
        show("콘솔 오류 0", not errs, str(errs[:1]))
        pg.screenshot(path=str(SHOTS / "01_밝은_계층.png"))

        # ① 테마 — 대비비는 **화면이 쓰는 값**에서 잰다
        th = pg.evaluate("""() => {
            const v = (k) => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
            return {fg: v('--fg'), bg: v('--bg'), dim: v('--dim'),
                    label: S.sigma.getSetting('labelColor').color,
                    edgeLabel: S.sigma.getSetting('edgeLabelColor').color};}""")
        show("① 밝은 테마 — 라벨 색이 CSS 변수와 같고 배경 대비 ≥ 4.5",
             th["label"] == th["fg"] and contrast(th["label"], th["bg"]) >= 4.5,
             f"{th['label']} on {th['bg']} = {contrast(th['label'], th['bg']):.1f}")
        pg.click("#theme-toggle"); pg.wait_for_timeout(500)
        th2 = pg.evaluate("""() => {
            const v = (k) => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
            return {fg: v('--fg'), bg: v('--bg'), theme: document.documentElement.dataset.theme,
                    label: S.sigma.getSetting('labelColor').color,
                    stored: localStorage.getItem('onto.theme')};}""")
        show("① 어두운 테마 — 라벨이 따라 바뀌고 대비 ≥ 4.5 (토글이 라벨을 두고 가지 않는다)",
             th2["theme"] == "dark" and th2["label"] == th2["fg"]
             and contrast(th2["label"], th2["bg"]) >= 4.5,
             f"{th2['label']} on {th2['bg']} = {contrast(th2['label'], th2['bg']):.1f}")
        pg.screenshot(path=str(SHOTS / "02_어두운_계층.png"))

        # ② 검색 — 배치 0 · sigma 생성 0 (글자마다 리듀서만)
        before = pg.evaluate("() => ({...RSTAT})")
        for q in ("노", "노칭", "노칭 ", "노칭 타"):
            pg.fill("#search", q); pg.wait_for_timeout(220)
        after = pg.evaluate("() => ({...RSTAT})")
        show("② 검색 네 글자 — 배치 계산 0회 · sigma 생성 0회 · 리듀서만 돌았다",
             after["layout"] == before["layout"] and after["sigma"] == before["sigma"]
             and after["restyle"] > before["restyle"],
             f"layout {before['layout']}→{after['layout']} · sigma {after['sigma']} · "
             f"restyle +{after['restyle'] - before['restyle']}")
        hits = pg.evaluate("""() => {
            const q = '노칭';
            const now = S.graph.nodes.filter((n) => searchHit(n, q)).map((n) => n.id).sort();
            const old = S.graph.nodes.filter((n) =>
                String(n.name).toLowerCase().includes(q)
                || String(n.id).toLowerCase() === q).map((n) => n.id).sort();
            return {same: JSON.stringify(now) === JSON.stringify(old), n: now.length};}""")
        show("② 검색에 걸리는 집합이 구판과 같다 (보이는 방식만 바뀌었다 — 숨기지 않는다)",
             hits["same"] and hits["n"] > 0, f"{hits['n']}건")
        dimmed = pg.evaluate("""() => {
            const r = S.sigma.getSetting('nodeReducer');
            const q = (S.search || '').trim().toLowerCase();
            const miss = S.graph.nodes.find((n) => !searchHit(n, q));
            const hit = S.graph.nodes.find((n) => searchHit(n, q));
            const faint = getComputedStyle(document.documentElement).getPropertyValue('--faint').trim();
            const rh = r(hit.id, S.gr.getNodeAttributes(hit.id));
            const rm = r(miss.id, S.gr.getNodeAttributes(miss.id));
            // **자기 기본 크기와 견준다** — 다른 점과 견주면 tier 크기에 묻힌다.
            return {miss: rm.color, faint, missLabel: rm.label,
                    hidden: !!rm.hidden,
                    bigger: rh.size > sizeOf(hit) && !!rh.highlighted};}""")
        show("② 검색 중 — 안 걸린 점은 흐려질 뿐 숨지 않고, 걸린 점은 제 크기보다 커진다",
             dimmed["miss"] == dimmed["faint"] and dimmed["bigger"]
             and dimmed["missLabel"] == "" and not dimmed["hidden"],
             f"{dimmed['miss']} · 강조 {dimmed['bigger']} · 숨김 {dimmed['hidden']}")
        pg.fill("#search", ""); pg.wait_for_timeout(300)

        # ③ 배치 — 두 번 계산 diff 0 · 선택 기억
        det = pg.evaluate("""() => {
            const k = (p) => Object.entries(p).sort()
                .map(([i, v]) => i + ':' + v.x.toFixed(6) + ',' + v.y.toFixed(6)).join('|');
            const a1 = positions(S.graph.nodes, S.graph.edges, '계층');
            const a2 = positions(S.graph.nodes, S.graph.edges, '계층');
            const b1 = positions(S.graph.nodes, S.graph.edges, '힘');
            const b2 = positions(S.graph.nodes, S.graph.edges, '힘');
            return {계층: k(a1) === k(a2), 힘: k(b1) === k(b2), 다르다: k(a1) !== k(b1)};}""")
        show("③ 두 배치 모두 **결정적**이다 — 두 번 계산해 좌표 diff 0 (서로는 다르다)",
             det["계층"] and det["힘"] and det["다르다"], json.dumps(det, ensure_ascii=False))
        pg.click("#layout-pick input[value='힘']"); pg.wait_for_timeout(1500)
        pg.screenshot(path=str(SHOTS / "03_어두운_힘.png"))
        pg.reload(wait_until="load"); pg.wait_for_timeout(2000)
        kept = pg.evaluate("""() => ({theme: document.documentElement.dataset.theme,
            layout: S.layout, pick: document.querySelector("#layout-pick input:checked").value,
            sigma: RSTAT.sigma})""")
        show("③① 새로고침 뒤에도 테마와 배치 선택이 그대로다 (브라우저가 기억한다)",
             kept["theme"] == "dark" and kept["layout"] == "힘" and kept["pick"] == "힘"
             and kept["sigma"] == 1, json.dumps(kept, ensure_ascii=False))

        # ④ 상호작용 — hover · 드래그 · 더블클릭 · 서버 요청 0
        box = pg.locator("#canvas").bounding_box()
        info = pg.evaluate("""() => {
            const n = S.gr.nodes().find((id) => S.gr.getNodeAttribute(id, '_node').name === '노칭')
                      || S.gr.nodes()[0];
            const a = S.gr.getNodeAttributes(n);
            const v = S.sigma.graphToViewport({x: a.x, y: a.y});
            return {n, x: a.x, y: a.y, vx: v.x, vy: v.y};}""")
        reqs = []
        pg.on("request", lambda r: reqs.append(r.url))
        pg.mouse.move(box["x"] + info["vx"], box["y"] + info["vy"])
        pg.wait_for_timeout(400)
        hov = pg.evaluate("""() => {
            const r = S.sigma.getSetting('nodeReducer');
            const far = S.gr.nodes().find((id) => !S.neighbors.has(id));
            const faint = getComputedStyle(document.documentElement).getPropertyValue('--faint').trim();
            return {hover: !!S.hover, 이웃: S.neighbors.size,
                    far: r(far, S.gr.getNodeAttributes(far)).color, faint};}""")
        show("④ hover — 이웃만 남고 나머지는 흐려진다 (리듀서 결과로 잰다)",
             hov["hover"] and hov["이웃"] > 1 and hov["far"] == hov["faint"],
             f"이웃 {hov['이웃']} · 나머지 {hov['far']}")
        cam0 = pg.evaluate("() => ({...S.sigma.getCamera().getState()})")
        pg.mouse.down()
        pg.mouse.move(box["x"] + info["vx"] + 150, box["y"] + info["vy"] + 90, steps=12)
        pg.mouse.up(); pg.wait_for_timeout(400)
        drag = pg.evaluate("""(p) => { const a = S.gr.getNodeAttributes(p.n);
            return {moved: Math.hypot(a.x - p.x, a.y - p.y) > 0.01,
                    pinned: Object.keys(S.pinned).length,
                    cam: {...S.sigma.getCamera().getState()}};}""", info)
        show("④ 드래그 — 점만 움직인다: 좌표가 바뀌고 고정되며 **카메라는 그대로**다",
             drag["moved"] and drag["pinned"] == 1
             and abs(drag["cam"]["x"] - cam0["x"]) < 1e-9
             and abs(drag["cam"]["y"] - cam0["y"]) < 1e-9
             and drag["cam"]["ratio"] == cam0["ratio"],
             json.dumps({"moved": drag["moved"], "pinned": drag["pinned"],
                         "cam": drag["cam"]}, ensure_ascii=False))
        v2 = pg.evaluate("""(n) => { const a = S.gr.getNodeAttributes(n);
            return S.sigma.graphToViewport({x: a.x, y: a.y});}""", info["n"])
        pg.mouse.dblclick(box["x"] + v2["x"], box["y"] + v2["y"])
        pg.wait_for_timeout(900)
        foc = pg.evaluate("""() => { const d = S.sigma.getNodeDisplayData(S.focus.node);
            const c = S.sigma.getCamera().getState();
            return {node: S.gr.getNodeAttribute(S.focus.node, '_node').name,
                    dx: d.x, dy: d.y, cx: c.x, cy: c.y, ratio: c.ratio,
                    detail: (document.querySelector('#detail h3') || {}).textContent};}""")
        show("④ 더블클릭 — 카메라 중심이 그 점의 자리이고 상세가 그 점이다",
             abs(foc["cx"] - foc["dx"]) < 1e-6 and abs(foc["cy"] - foc["dy"]) < 1e-6
             and foc["detail"] == foc["node"],
             f"카메라({foc['cx']:.4f},{foc['cy']:.4f}) · 점({foc['dx']:.4f},{foc['dy']:.4f})"
             f" · ratio {foc['ratio']}")
        show("④ 상호작용 중 서버 요청 0 (그래프는 한 번 받는다)",
             not [u for u in reqs if "/api/" in u], str([u for u in reqs][:2]))
        pg.screenshot(path=str(SHOTS / "04_상호작용.png"))

        # ⑤ 질의 오류 — 서버 문면 그대로
        pg.click('#tabs button[data-tab="query"]')
        pg.evaluate("""() => { const real = window.fetch;
            window.fetch = (u, o) => String(u).includes('/api/query')
              ? Promise.resolve(new Response(JSON.stringify(
                  {error: 'GatewayError: HTTP 400 — POST http://gw/v1/chat — temperature'}),
                  {status: 500, headers: {'content-type': 'application/json'}}))
              : real(u, o); }""")
        pg.fill("#q", "노칭 다음 공정은?")
        pg.press("#q", "Enter")
        pg.wait_for_timeout(700)
        err = pg.evaluate("""() => ({
            card: (document.querySelector('#qanswer .err') || {}).textContent,
            btn: document.querySelector('#qform button').textContent});""")
        show("⑤ 서버가 500 {error}를 내면 그 문면이 화면에 그대로 뜬다 (조용히 비지 않는다)",
             err["card"] and "GatewayError" in err["card"] and "POST" in err["card"],
             (err["card"] or "")[:60])
        pg.screenshot(path=str(SHOTS / "05_오류_카드.png"))
        pg.reload(wait_until="load")          # 가짜 fetch를 걷는다(새로 뜬 화면)
        pg.wait_for_timeout(2000)
        pg.click('#tabs button[data-tab="query"]')
        pg.fill("#q", "노칭 다음 공정은?")
        pg.press("#q", "Enter")
        pg.wait_for_timeout(1500)
        ok = pg.evaluate("""() => ({err: !!document.querySelector('#qanswer .err'),
            ans: (document.querySelector('#qanswer .card') || {}).textContent,
            btn: document.querySelector('#qform button').textContent});""")
        show("⑤ 정상 응답이면 오류 카드 0이고 버튼이 되돌아온다",
             not ok["err"] and ok["btn"] == "묻는다" and ok["ans"],
             (ok["ans"] or "")[:50])
        pg.screenshot(path=str(SHOTS / "06_질의.png"))
        show("콘솔 오류 0 (전 구간)", not errs, str(errs[:1]))
        ctx.close(); browser.close()
finally:
    srv.shutdown()
    srv.server_close()

print(f"\n  스크린샷 — {SHOTS}")
print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어 브라우저 실측 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
