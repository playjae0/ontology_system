# -*- coding: utf-8 -*-
"""칸 5.3 — 뷰어 **브라우저 실측 B104**: 질의 콘솔의 링크 결과 ⓐ~ⓕ · LLM이 고른 노드 · 원문 펼치기.

`viewer_browser.py`·`viewer_browser_b103.py`와 같은 처지다(D-165 ②) — Playwright·Chromium이 있어야 하고 사내
클론에는 없어 **회귀(`doctor.py`)에 넣지 않는다**. 회귀에는 브라우저 없이 재는 성질(CLI ⓐ~ⓕ = `--json`의 수 ·
쓴 근거 표시 · 후보 밖 id 0 — `tests/test_g6_hybrid.py`)만 둔다. 여기 것은 회차 보고에 실행 결과로 붙인다.

표본은 **창작**이다 — mock 그래프(CP01·PFMEA01·PPT01~03·QPPT01) · 실호출 갈래는 가짜 게이트웨이
(`tests/fake_gateway.py` — 임베딩 동의어 표 · 선별 · 답변 대역). 수치는 메커니즘 확인이다([정정] 50).

재는 것(완료판정 ⓓ의 뷰어 몫):
  ⓐ 칸 여섯(ⓐ 링킹 · ⓑ 확장 · ⓒ 사실 · ⓓ 노드 근거 · ⓔ 문서 검색 · ⓕ 답)이 한 화면에 나란히 · 칸마다 수가
     CLI `--json`과 같다(같은 질문 · 같은 함수 `as_json(answer(q))`)
  ⓑ LLM이 고른 노드는 칩(점선 · 이유)과 그래프 색(`--hi3`)이 사전 링킹(`--hi`)과 다르다
  ⓒ 쓴 근거 표시(사실·노드 근거·문서 검색) = trace의 used · 답의 줄 수 표시
  ⓓ 청크를 누르면 원문 전부(서버 원문과 글자 그대로) · 「원본」은 문서 패널
  ⓔ mock — 링킹 0인 질문이 문서 검색 칸으로 답한다(경로 chunk · 「근거 없음」 아님)
  ⓕ 쓰기 0 · 외부 URL 0 · 콘솔 오류 0

사용: python tests/viewer_browser_b104.py   (스크린샷은 `$ONTO_HOME/export/viewer_shots/`)
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from playwright.sync_api import sync_playwright
except ImportError:                                       # pragma: no cover
    print("■ 뷰어 브라우저 실측 B104 — **건너뛴다**: playwright가 없다.")
    sys.exit(0)

from g65_common import *                                  # noqa: E402,F401,F403 — 바닥은 하나다
from g65_common import _P                                 # noqa: E402
from cli import query as CQ                               # noqa: E402
from cli.viewer import server as VS                       # noqa: E402
from fake_gateway import Live                             # noqa: E402 — 실호출 갈래의 대역(전송·채팅·설정만)

allok = True                                              # 별 import 뒤에 둔다(B103 — 덮어쓰기 사고)
PORT = 8874
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
print(f"\n■ B104 — 뷰어 브라우저 실측 · 질의 링크 결과 ({url})")

Q_LIVE = "노칭 틈새는 어떻게 관리해?"      # 사전이 「노칭」을 잡고 선별이 「노칭::금형 클리어런스」를 더한다(보충)
Q_MOCK = "육안 점검 교체 주기는?"          # 사전 미스 · BM25가 잡는다 — 문서 검색 칸으로 답한다

_DOM = """() => { const q = (s) => [...document.querySelectorAll(s)];
  const txt = (s) => (document.querySelector(s) || {}).textContent || '';
  return {heads: q('#pane-query h3').map((h) => h.textContent),
          chips: q('#qlinked .chip').length, picks: q('#qlinked .chip.pick').length,
          why: q('#qlinked .muted').map((d) => d.textContent),
          hops: q('#qhops div:not(.muted)').length,
          facts: q('#qfacts .card').length, factsUsed: q('#qfacts .card.used').length,
          chunks: q('#qchunks details.card').length, chunksUsed: q('#qchunks details.card.used').length,
          docs: q('#qdocs details.card').length, docsUsed: q('#qdocs details.card.used').length,
          answer: txt('#qanswer'), llm: txt('#qllm'), path: txt('#qpath')}; }"""


def _ask(pg, q):
    pg.fill("#q", q)
    pg.press("#q", "Enter")
    pg.wait_for_function("() => !S.asking && S.res && S.res.question === " + repr(q), timeout=20000)
    pg.wait_for_timeout(300)
    return pg.evaluate(_DOM)


def _counts(j):
    tr = j["trace"]
    edges = sum(len(h.get("edges") or []) for h in tr.get("hops") or [])
    return {"chips": len(tr["linking"]), "picks": sum(1 for x in tr["linking"] if x["method"] == "embed+llm"),
            "hops": min(30, edges),
            "facts": len(tr.get("facts") or []), "factsUsed": sum(1 for f in tr.get("facts") or [] if f["used"]),
            "chunks": len(tr.get("collection") or []),
            "chunksUsed": sum(1 for c in tr.get("collection") or [] if c.get("used")),
            "docs": len(tr.get("doc_search") or []),
            "docsUsed": sum(1 for c in tr.get("doc_search") or [] if c.get("used"))}


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

        # ── live(가짜 게이트웨이) — 같은 프로세스의 서버가 이 함수들을 부른다
        with Live():
            dom = _ask(pg, Q_LIVE)
            j = CQ.as_json(CQ.answer(Q_LIVE))           # CLI `--json`과 같은 함수 — 같은 질문
            colors = pg.evaluate("""() => { const out = {};
                (S.trace.linking || []).forEach((l) => { out[l.method] = out[l.method] || [];
                  out[l.method].push({id: l.node_id, hi: S.highlight.nodes[l.node_id],
                                      color: S.sigma.getNodeDisplayData(l.node_id).color}); });
                return {out, hi: cssVar('--hi'), hi3: cssVar('--hi3')}; }""")
        want = _counts(j)
        got = {k: dom[k] for k in want}
        show("ⓐ 칸 여섯이 한 화면에 나란히(ⓐ 링킹 · ⓑ 확장 · ⓒ 사실 · ⓓ 노드 근거 · ⓔ 문서 검색 · ⓕ 답)",
             [h[:1] for h in dom["heads"][-6:]] == ["ⓐ", "ⓑ", "ⓒ", "ⓓ", "ⓔ", "ⓕ"], " / ".join(dom["heads"][-6:]))
        show("ⓐ 칸마다 수가 CLI `--json`과 같다 — 링킹 · 선별 · 홉 엣지 · 사실(쓴 것) · 노드 근거(쓴 것) · 문서 검색(쓴 것)",
             got == want and want["picks"] >= 1 and want["docs"] >= 1,
             " · ".join(f"{k} {got[k]}={want[k]}" for k in want))
        pk, dc = colors["out"].get("embed+llm") or [], colors["out"].get("dict") or []
        show("ⓑ LLM이 고른 노드 — 칩은 점선(이유 줄) · 그래프 색 --hi3 · 사전 링킹은 --hi(색이 다르다)",
             pk and dc and all(x["hi"] == "pick" and x["color"] == colors["hi3"] for x in pk)
             and all(x["hi"] == "link" and x["color"] == colors["hi"] for x in dc) and colors["hi"] != colors["hi3"]
             and len(dom["why"]) == dom["picks"],
             f"선별 {len(pk)} {pk[0]['color'] if pk else '-'} · 사전 {len(dc)} {dc[0]['color'] if dc else '-'} · "
             f"{(dom['why'] or [''])[0][:60]}")
        a = j["trace"]["answer"]
        show("ⓒ 쓴 근거 표시 = trace의 used(사실 · 노드 근거 · 문서 검색) · 답 줄 수 · 쓴 청크 수 표시",
             dom["factsUsed"] == want["factsUsed"] and dom["chunksUsed"] + dom["docsUsed"] == len(a["used_chunks"])
             and f"{a['lines']}줄" in dom["answer"] and f"쓴 청크 {len(a['used_chunks'])}" in dom["answer"]
             and "가짜 답 첫 줄" in dom["answer"],
             dom["answer"].replace("\n", " ⏎ "))
        pg.screenshot(path=str(SHOTS / "b104_01_질의_live.png"), full_page=True)

        # ── 원문 펼치기 — 문서 검색 칸의 첫 청크
        first = j["trace"]["doc_search"][0]
        texts = {c["chunk_id"]: c["text"] for c in (j.get("doc_search") or []) + (j.get("chunks") or [])}
        pg.click("#qdocs details.card >> nth=0 >> summary")
        pg.wait_for_timeout(300)
        op = pg.evaluate("""() => { const d = document.querySelector('#qdocs details.card');
            return {open: d.open, pre: d.querySelector('pre.src').textContent,
                    shown: d.querySelector('pre.src').offsetHeight > 0}; }""")
        n0 = len(reqs)
        pg.click("#qdocs details.card >> nth=0 >> a")
        pg.wait_for_timeout(1200)
        docreq = [u for u in reqs[n0:] if "/api/doc/" in u]
        show("ⓓ 청크를 누르면 원문 전부(서버 원문과 글자 그대로) · 「원본」은 그 문서 패널을 연다",
             op["open"] and op["shown"] and op["pre"] == texts.get(first["chunk_id"])
             and any(first["doc_id"] in u for u in docreq),
             f"{first['doc_id']} {first.get('source_locator')} · 원문 {len(op['pre'])}자 · 문서 요청 {len(docreq)}")
        pg.click('#tabs button[data-tab="query"]')

        # ── mock — 링킹 0인 질문
        dm = _ask(pg, Q_MOCK)
        jm = CQ.as_json(CQ.answer(Q_MOCK))
        show("ⓔ mock — 링킹 0인 질문이 문서 검색 칸으로 답한다(경로 chunk · 「근거 없음」 아님 · 수 = --json)",
             jm["path"] == "chunk" and not jm["trace"]["linking"] and dm["chips"] == 0
             and dm["docs"] == len(jm["trace"]["doc_search"]) >= 1 and "경로 chunk" in dm["path"]
             and "근거를 찾지 못했다" not in dm["answer"],
             f"{dm['path']} · 문서 검색 {dm['docs']}={len(jm['trace']['doc_search'])} · {dm['llm'].strip()}")
        pg.screenshot(path=str(SHOTS / "b104_02_질의_문서검색.png"), full_page=True)

        # ── ⓕ
        show("ⓕ 쓰기 0 — 화면을 도는 동안 ③진실·②등록 해시 불변", _state_hash() == H0)
        ext = [u for u in reqs if not u.startswith(url)]
        show("ⓕ 외부 URL 0 — 화면이 부른 요청이 전부 이 서버", not ext, str(ext[:2]))
        show("ⓕ 콘솔 오류 0 (전 구간)", not errs, str(errs[:1]))
        ctx.close()
        browser.close()
finally:
    srv.shutdown()
    srv.server_close()

print(f"\n  스크린샷 — {SHOTS}")
print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어 브라우저 실측 B104 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
