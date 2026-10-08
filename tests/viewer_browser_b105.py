# -*- coding: utf-8 -*-
"""칸 5.3 — 뷰어 **브라우저 실측 B105**: 질의 패널 ⓖ 노드 원 레코드.

`viewer_browser_b104.py`와 같은 처지다(D-165 ②) — Playwright·Chromium이 있어야 하고 사내 클론에는 없어 **회귀
(`doctor.py`)에 넣지 않는다**. 회귀에는 브라우저 없이 재는 성질(CLI `[원 레코드]` 줄 수 = `--json` records 수 ·
값·별칭·출처가 저장된 그대로 — `tests/test_g6_coord_pairs.py`)만 둔다. 여기 것은 회차 보고에 실행 결과로 붙인다.

표본은 **창작**이다 — mock 그래프(CP01·PFMEA01·PPT01~03·QPPT01). 재는 것:
  ⓐ ⓖ 카드 수 = CLI `--json`의 `records` 수(같은 함수 `as_json(answer(q))`) · 카드의 원문 = 레코드 그대로
  ⓑ 링킹 칩을 누르면 그 노드의 레코드가 펼쳐진다
  ⓒ 쓰기 0 · 외부 URL 0 · 콘솔 오류 0

사용: python tests/viewer_browser_b105.py   (스크린샷은 `$ONTO_HOME/export/viewer_shots/`)
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
    print("■ 뷰어 브라우저 실측 B105 — **건너뛴다**: playwright가 없다.")
    sys.exit(0)

from g65_common import *                                  # noqa: E402,F401,F403 — 바닥은 하나다
from g65_common import _P                                 # noqa: E402
from cli import query as CQ                               # noqa: E402
from cli.viewer import server as VS                       # noqa: E402

allok = True                                              # 별 import 뒤에 둔다(B103 — 덮어쓰기 사고)
PORT = 8875
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def _state_hash():
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in (_P.data(), _P.registry()) if base.exists()
            for p in sorted(base.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}


with contextlib.redirect_stdout(io.StringIO()):
    fresh()
H0 = _state_hash()
SHOTS = _P.export("viewer_shots")
_P.ensure(SHOTS)
srv, url = VS.serve(PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"\n■ B105 — 뷰어 브라우저 실측 · 질의 ⓖ 노드 원 레코드 ({url})")
Q = "노칭 정밀도 규격은?"

try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME if Path(CHROME).exists() else None,
                                     args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        pg = ctx.new_page()
        errs, reqs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        pg.on("request", lambda r: reqs.append(r.url))
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(2500)
        pg.click('#tabs button[data-tab="query"]')
        pg.fill("#q", Q)
        pg.press("#q", "Enter")
        pg.wait_for_function("() => !S.asking && S.res && S.res.question === " + repr(Q), timeout=20000)
        pg.wait_for_timeout(300)
        j = CQ.as_json(CQ.answer(Q))
        dom = pg.evaluate("""() => { const cards = [...document.querySelectorAll('#qrecords details.rec')];
            return {n: cards.length, ids: cards.map((c) => c.dataset.node),
                    raw: cards.map((c) => JSON.parse(c.querySelector('pre.src').textContent)),
                    head: (document.querySelector('#qrecords .muted') || {}).textContent || ''}; }""")
        want = [r["node_id"] for r in j["records"]]
        raw_ok = all(d["attrs"] == r["attrs"] and d["aliases"] == r["aliases"] and d["provenance"] == r["provenance"]
                     for d, r in zip(dom["raw"], j["records"]))
        show("ⓐ ⓖ 카드 수 = --json records 수 · 순서 같다 · 카드의 원문이 레코드 그대로(값 · 별칭 · 출처)",
             dom["n"] == len(want) >= 1 and dom["ids"] == want and raw_ok
             and f"{len(want)}건" in dom["head"], f"카드 {dom['n']} = records {len(want)} · {dom['head']}")
        pg.click("#qlinked .chip >> nth=0")
        pg.wait_for_timeout(600)
        first = j["trace"]["linking"][0]["node_id"]
        op = pg.evaluate("""(id) => { const c = [...document.querySelectorAll('#qrecords details.rec')]
            .find((x) => x.dataset.node === id); return c ? c.open : null; }""", first)
        show("ⓑ 링킹 칩을 누르면 그 노드의 레코드가 펼쳐진다", op is True, f"{first[:8]} open={op}")
        pg.screenshot(path=str(SHOTS / "b105_01_원레코드.png"), full_page=True)
        show("ⓒ 쓰기 0 — 화면을 도는 동안 ③진실·②등록 해시 불변", _state_hash() == H0)
        ext = [u for u in reqs if not u.startswith(url)]
        show("ⓒ 외부 URL 0 — 화면이 부른 요청이 전부 이 서버", not ext, str(ext[:2]))
        show("ⓒ 콘솔 오류 0 (전 구간)", not errs, str(errs[:1]))
        ctx.close()
        browser.close()
finally:
    srv.shutdown()
    srv.server_close()

print(f"\n  스크린샷 — {SHOTS}")
print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어 브라우저 실측 B105 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
