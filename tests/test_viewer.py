# -*- coding: utf-8 -*-
"""칸 5.1~5.4 — 뷰어(세미 플랫폼) · 질의 trace (B82).

**headless로 잰다** — 서버를 띄우고 API·정적 파일을 파싱한다(브라우저 의존 0).
재는 것은 성질이다: 서버가 주는 수가 시스템의 수와 같은가 · 쓰기가 0인가 ·
trace가 질의의 계산과 같은 것을 말하는가 · 화면 코드가 그 trace를 쓰는가.

사용: python tests/test_viewer.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import urllib.error as _ue
import urllib.parse as _up
import urllib.request as _ur
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.query import answer, as_json                                # noqa: E402
from cli.viewer import data as VD, server as VS                      # noqa: E402
from core import paths as _P                                         # noqa: E402
from core.build import ledger                                        # noqa: E402
from core.state import fixtures, init, store                         # noqa: E402
from core.state.bootstrap import bootstrap, load_config, open_graph   # noqa: E402
from router import discover                                          # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def _state_hash():
    """③진실·②등록의 실물 해시 — **쓰기 0**을 잰다(읽기 도구다)."""
    h = hashlib.sha256()
    for d in (_P.data(), _P.registry()):
        for p in sorted(d.rglob("*")) if d.exists() else []:
            if p.is_file() and not p.name.endswith(".lock"):
                h.update(p.relative_to(d).as_posix().encode("utf-8"))
                h.update(p.read_bytes())
    return h.hexdigest()


# ── 바닥: 클린 + 골격 + mock 문서 인입 ────────────────────────────────────
init.init(fresh_=True)
for _lay in discover():
    bootstrap(_lay, echo=False)
from cli.parse import run_parse                                      # noqa: E402
from core.build.entry import finalize, run_document                  # noqa: E402

for _doc in ("CP01", "PFMEA01"):
    _env = json.loads((ROOT / "tests" / "fixtures" / "parsed"
                       / f"{_doc}.json").read_text(encoding="utf-8"))
    run_document(_env)
finalize()

print("\n■ B82 ③ — 질의 trace는 계측이다 (answer()의 세 자리 + ⑧의 번호)")
_QS = [q for q in json.loads(fixtures.QUERIES.read_text(encoding="utf-8"))["queries"]]
_rows = []
for _q in _QS:
    _res = answer(_q["q"])
    _tr = _res.get("trace") or {}
    _rows.append((_q, _res, _tr))
show("스모크 12문항 전부가 trace를 낸다 (키 일곱 — 계약 ㉠)",
     len(_rows) == 12 and all(
         {"intent", "linking", "hops", "collection", "facts", "answer", "miss"}
         <= set(tr) for _q, _r, tr in _rows),
     str(sorted((_rows[0][2] or {}).keys())))
show("trace.linking의 노드가 linked와 같다 (화면이 칠하는 것이 답의 링킹이다)",
     all([l["node_id"] for l in tr["linking"]]
         == [n["node_id"] for n in r["linked_nodes"]] for _q, r, tr in _rows))
_graphs = {lay: open_graph(lay) for lay in discover()}
_all_edges = {(e["src"], e["rel"], e["dst"]) for g in _graphs.values() for e in g.edges}
_bad_edge = [(q["q"], e) for q, _r, tr in _rows for h in tr["hops"]
             for e in h["edges"] if (e["src"], e["rel"], e["dst"]) not in _all_edges]
show("hops의 엣지가 전부 그래프에 실재한다 (화면이 없는 선을 그리지 않는다)",
     not _bad_edge, str(_bad_edge[:1]))
_rules = {lay: set((load_config(lay).get("query_traverse") or {}).keys())
          for lay in discover()}
_bad_rel = [e["rel"] for _q, _r, tr in _rows for h in tr["hops"]
            if h["kind"] == "expand" for e in h["edges"]
            if not any(e["rel"] in v for v in _rules.values())]
show("expand 홉의 관계가 config의 query_traverse 안이다 (코드가 관계를 모른다)",
     not _bad_rel, str(sorted(set(_bad_rel))[:3]))
_cross = [tr for _q, _r, tr in _rows
          if any(h["kind"] == "cross" for h in tr["hops"])]
show("cross 홉의 엣지는 bridge 표시를 지고 온다",
     _cross and all(e["bridge"] for tr in _cross for h in tr["hops"]
                    if h["kind"] == "cross" for e in h["edges"]),
     f"cross 문항 {len(_cross)}건")
show("collection의 kept=false 수가 truncated와 같다 (상한에서 떨어진 것을 센다)",
     all(sum(1 for c in tr["collection"] if not c["kept"]) == r["truncated"]
         for _q, r, tr in _rows))
show("facts 수가 사실 채널 수와 같다",
     all(len(tr["facts"]) >= len(r["facts"]) for _q, r, tr in _rows))
# **trace를 켜고 끈 답이 같다** — 계측이 판단을 건드리지 않는다.
_h0 = _state_hash()
_plain = [answer(q["q"]) for q in _QS]
show("trace가 있어도 답·경로·사실 수가 같다 (계측은 판단을 바꾸지 않는다)",
     all(a["path"] == b["path"] and a["facts"] == b["facts"]
         and a["chunks"] == b["chunks"] for a, (_q, b, _t) in zip(_plain, _rows)))
show("질의는 ③진실·②등록에 쓰지 않는다 (해시 불변)", _state_hash() == _h0)

print("\n■ B82 ① — 서버: 데이터는 서버가 준다 · 쓰기 0 · 자리 탈출 거부")
_h_before = _state_hash()
_srv, _url = VS.serve(8830)
threading.Thread(target=_srv.serve_forever, daemon=True).start()
_port = int(_url.rsplit(":", 1)[1].rstrip("/"))


def _get(path, method="GET", data=None):
    # 한글 경로는 **퍼센트 인코딩**으로 보낸다(HTTP 요청 줄은 ascii다).
    url = f"http://{VS.HOST}:{_port}" + _up.quote(path, safe="/?=&%")
    req = _ur.Request(url, method=method, data=data)
    try:
        with _ur.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except _ue.HTTPError as e:
        return e.code, e.read()


try:
    show("바인드는 127.0.0.1이다 (바깥에 열지 않는다)",
         VS.HOST == "127.0.0.1" and _srv.server_address[0] == "127.0.0.1",
         str(_srv.server_address))
    _sc, _b = _get("/api/graph")
    _g = json.loads(_b)
    _nodes_live = sum(1 for lay in discover() for n in open_graph(lay).nodes.values()
                      if n.get("status") != "obsolete" and not n.get("merged_into"))
    show("/api/graph의 노드가 GraphStore의 살아 있는 노드와 같은 수다",
         _sc == 200 and len(_g["nodes"]) == _nodes_live,
         f"{len(_g['nodes'])} vs {_nodes_live}")
    show("/api/graph가 층과 관계 목록을 함께 준다 (화면이 토글을 만들 재료)",
         _g["layers"] == sorted(discover()) and _g["rels"], str(_g["rels"][:4]))
    # 문서 · 원본
    _doc_id = sorted(store.read(store.DOC_REGISTRY, {}))[0]
    _sc_d, _b_d = _get(f"/api/doc/{_doc_id}")
    _d = json.loads(_b_d)
    show("/api/doc — 대장 집계·노드·청크를 함께 준다 (원본 추적의 한쪽 끝)",
         _sc_d == 200 and _d["rows"] > 0 and _d["nodes"] and _d["chunks"],
         f"{_doc_id} · 행 {_d['rows']} · 노드 {len(_d['nodes'])} · 청크 {len(_d['chunks'])}")
    show("/api/doc — 없는 문서는 404 (조용히 빈 것을 내지 않는다)",
         _get("/api/doc/없는문서")[0] == 404)
    # `/raw/` — 자리 안의 파일만
    _raw = _P.raw(); _raw.mkdir(parents=True, exist_ok=True)
    (_raw / "표본.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    show("/raw/ — 원본 자리 아래 파일은 그대로 내준다",
         _get("/raw/표본.csv")[0] == 200)
    _escapes = ["/raw/../../etc/passwd", "/raw//etc/passwd", "/raw/%2e%2e%2fsecret",
                "/raw/없는파일.csv"]
    show("/raw/ — `..`·절대 경로·없는 파일은 4xx (자리 밖으로 한 바이트도 안 나간다)",
         all(_get(p)[0] >= 400 for p in _escapes),
         str([(p, _get(p)[0]) for p in _escapes[:2]]))
    show("쓰기 라우트 없음 — POST는 501 · do_POST가 없다",
         _get("/", method="POST", data=b"{}")[0] == 501
         and not hasattr(VS.Handler, "do_POST"))
    _sc_f, _b_f = _get("/api/funnel")
    _f = json.loads(_b_f)
    # ⑤ **오류는 문면으로 올라온다**(B84 ⑤) — 실제로 터뜨려 잰다(문자열 검사가 아니다).
    _sc_ok, _b_ok = _get("/api/query?q=" + _up.quote("노칭 다음 공정은?"))
    show("⑤ 정상 질의는 200이고 오류 키가 없다",
         _sc_ok == 200 and "error" not in json.loads(_b_ok))
    import cli.query as _CQ                                          # noqa: E402
    _real = _CQ.answer
    _CQ.answer = lambda q: (_ for _ in ()).throw(
        RuntimeError("GatewayError: HTTP 400 — POST http://gw/v1/chat — temperature"))
    try:
        _sc_e, _b_e = _get("/api/query?q=" + _up.quote("노칭 다음 공정은?"))
    finally:
        _CQ.answer = _real
    _err = json.loads(_b_e).get("error", "")
    show("⑤ 게이트웨이가 죽으면 500 + 사유 문면이다 (조용한 500이 아니다)",
         _sc_e == 500 and "GatewayError" in _err and "POST" in _err, _err[:60])
    show("서버가 어떤 요청에도 상태를 쓰지 않는다 (해시 불변)",
         _state_hash() == _h_before)
finally:
    _srv.shutdown()
    _srv.server_close()

print("\n■ B82 ② — 벤더링 · 색 축 · 렌더러 인터페이스")
_ST = ROOT / "cli" / "viewer" / "static"
_V = _ST / "vendor"
#: 화면 코드는 **세 파일**이다(B84 — `app.js` 351행을 갈랐다). 문면을 재는 어서션은
#: 셋을 합쳐 본다 — 이름이 옮겨 간 것은 사라진 것이 아니다.
_SRC = {n: (_ST / n).read_text(encoding="utf-8")
        for n in ("app.js", "render.js", "query.js")}
_app = "\n".join(_SRC.values())
_idx = (_ST / "index.html").read_text(encoding="utf-8")
_css = (_ST / "style.css").read_text(encoding="utf-8")
_vend = sorted(p.name for p in _V.glob("*.js"))
show("렌더러가 고정 버전으로 벤더링돼 있다 (파일명에 버전)",
     any("sigma-" in n for n in _vend) and any("graphology-" in n for n in _vend)
     and all(any(c.isdigit() for c in n) for n in _vend), str(_vend))
show("라이선스와 출처·해시가 함께 있다",
     (_V / "LICENSE.sigma.txt").is_file() and (_V / "LICENSE.graphology.txt").is_file()
     and "sha256" in (_V / "README.md").read_text(encoding="utf-8").lower())
_readme = (_V / "README.md").read_text(encoding="utf-8")
_real = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in _V.glob("*.js")}
show("README의 해시가 실물과 같다 (바꿔치기를 기록이 잡는다)",
     all(h in _readme for h in _real.values()), str(list(_real)[:1]))
show("정적 화면이 vendor를 로컬 경로로만 부른다 (외부 URL 0)",
     "/static/vendor/" in _idx
     and not any(x in _idx + _app for x in ("http://", "https://", "//cdn")))
show("색 축 기본값이 category다",
     'axis: "category"' in _app and 'AXES = ["layer", "category"' in _app)
show("렌더러는 자리 둘 뒤에 있다 — 다시 만들기와 다시 칠하기 (B84 ②)",
     _SRC["render.js"].count("function rebuild(") == 1
     and _SRC["render.js"].count("function restyle(") == 1 and "S.sigma" in _app)
show("화면이 trace의 키를 그대로 쓴다 (오버레이는 계약을 읽는다)",
     all(k in _app for k in ("trace", "linking", "hops", "collection", "facts", "miss"))
     and "bridge" in _app or "cross" in _app)

print("\n■ B84 ①②③④⑤ — 뷰어 손보기 (브라우저 없이 재는 성질)")
# **색의 정본은 CSS 변수 하나다** — 대비비는 그 값에서 계산한다(화면 캡처가 아니다).
import re as _re                                                     # noqa: E402


def _vars(block):
    return dict(_re.findall(r"--([a-z0-9]+)\s*:\s*(#[0-9a-fA-F]{3,6})", block))


def _luma(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    xs = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in xs]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def _contrast(a, b):
    la, lb = _luma(a), _luma(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


_light = _vars(_css.split(":root {", 1)[1].split("}", 1)[0])
_dark = _vars(_css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0])
show("① 테마 둘이 **같은 변수 집합**을 정의한다 (한쪽에만 있는 색 0)",
     set(_light) == set(_dark) and {"bg", "fg", "dim", "line", "hi", "faint"} <= set(_light),
     f"{sorted(_light)}")
_cs = {name: (_contrast(v["fg"], v["bg"]), _contrast(v["dim"], v["bg"]))
       for name, v in (("light", _light), ("dark", _dark))}
show("① 두 테마 모두 라벨(--fg)·부라벨(--dim)이 배경 대비 4.5 이상이다",
     all(a >= 4.5 and b >= 4.5 for a, b in _cs.values()),
     " · ".join(f"{k} fg {a:.1f} dim {b:.1f}" for k, (a, b) in _cs.items()))
show("① 밝은 테마가 기본이고 어두운 테마는 토글이다 (사내 실측 — 어두운 바탕에 검정 라벨)",
     '<button id="theme-toggle"' in _idx
     and _css.index(":root {") < _css.index(':root[data-theme="dark"]')
     and 'recall("onto.theme", "light")' in _SRC["app.js"])
_sig = _SRC["render.js"].split("function theme_apply_sigma", 1)[1].split("\n}", 1)[0]
show("① sigma에 넘기는 색이 **CSS 변수에서만** 온다 (라벨 색 리터럴 0)",
     "labelColor" in _sig and _sig.count("cssVar(") >= 4
     and not _re.search(r"#[0-9a-fA-F]{3,6}", _sig), _sig.count("cssVar("))
_restyle = _SRC["render.js"].split("function restyle(", 1)[1].split("\n}", 1)[0]
_rebuild = _SRC["render.js"].split("function rebuild(", 1)[1].split("\n}\n", 1)[0]
show("② 다시 칠하기는 **좌표도 인스턴스도 건드리지 않는다** (검색이 타는 길)",
     "positions(" not in _restyle and "new (" not in _restyle
     and "refresh(" in _restyle
     and "positions(" in _rebuild and "new (window.Sigma" in _rebuild)
show("② 검색·필터·축·강조는 다시 칠하기로 간다 (배치를 다시 부르지 않는다)",
     'oninput' in _SRC["app.js"] and "setTimeout" in _SRC["app.js"]
     and "refresh()" in _SRC["app.js"].split("#search", 1)[1][:400]
     and "rebuild()" not in _SRC["app.js"].split("#search", 1)[1][:400])
show("② sigma는 한 번만 만든다 (구판은 그릴 때마다 kill + new였다)",
     _SRC["render.js"].count("new (window.Sigma") == 1
     and "if (!S.sigma)" in _rebuild and ".kill()" not in _app)
show("③ 배치는 **닫힌 둘**이고 둘 다 난수를 쓰지 않는다 (같은 입력이면 같은 그림)",
     'LAYOUTS = ["계층", "힘"]' in _SRC["render.js"]
     and "Math.random" not in _app
     and _SRC["render.js"].count("function layoutHier") == 1
     and _SRC["render.js"].count("function layoutForce") == 1)
show("③ 배치 선택과 테마는 브라우저가 기억한다 (키 둘 · 실패해도 화면은 산다)",
     'remember("onto.layout"' in _SRC["app.js"] and 'recall("onto.layout"' in _SRC["app.js"]
     and "try {" in _SRC["app.js"].split("const remember", 1)[1][:200])
show("④ 상호작용 배선 다섯 — 클릭·hover·떠남·더블클릭·드래그 (B84 ④)",
     all(k in _SRC["render.js"] for k in ('"clickNode"', '"enterNode"', '"leaveNode"',
                                          '"doubleClickNode"', '"downNode"', "mousemovebody")),
     "clickNode · enterNode · leaveNode · doubleClickNode · downNode + mousemovebody")
show("④ 상세 패널에 「이 노드로 질문」이 있고 **보내지는 않는다** (사람이 친다)",
     "이 노드로 질문" in _SRC["app.js"] and "function askAbout" in _SRC["query.js"]
     and "ask(" not in _SRC["query.js"].split("function askAbout", 1)[1])
show("⑤ 화면이 서버의 오류 키를 본다 — 답 자리에 문면 그대로 (조용히 비지 않는다)",
     "res.error" in _SRC["query.js"] and "r.status >= 400" in _SRC["query.js"]
     and "function errorCard" in _SRC["query.js"] and "card err" in _SRC["query.js"])
show("⑤ 질의 중에는 버튼이 잠긴다 — 같은 버튼을 또 눌러도 요청은 한 건",
     "S.asking" in _SRC["query.js"] and "묻는 중" in _SRC["query.js"])
show("§7 — 화면 코드 세 파일이 각각 상한(800행) 밑이다 (`app.js` 351 → 셋)",
     all(len(v.splitlines()) <= 800 for v in _SRC.values()),
     " · ".join(f"{k} {len(v.splitlines())}" for k, v in _SRC.items()))

print("\n■ B82 ⑤ — 연결 현황: 수는 대장과 큐에서")
_fn = VD.funnel()
_doc0 = _fn["rows"][0]["doc_id"] if _fn["rows"] else None
_led = ((ledger.read(_doc0) or {}).get("rows") or []) if _doc0 else []
show("깔때기의 값 수가 그 문서 대장 행 수와 같다",
     bool(_doc0) and _fn["rows"][0]["값"] == len(_led),
     f"{_doc0} · {_fn['rows'][0]['값'] if _doc0 else '-'} vs {len(_led)}")
show("NEW·불확실·orphan이 대장 verdict 집계와 같다",
     _doc0 and _fn["rows"][0]["NEW"] == sum(1 for r in _led if r.get("verdict") == "new")
     and _fn["rows"][0]["불확실"] == sum(1 for r in _led
                                      if r.get("verdict") in ("uncertain", "lowres")))
_open_orphan = [x for x in store.read(store.QUEUE, [])
                if str(x.get("kind") or "").startswith("orphan") and not x.get("resolution")]
show("orphan 표의 행 수가 열린 orphan 큐 항목 수와 같다",
     len(_fn["orphans"]) == len(_open_orphan),
     f"{len(_fn['orphans'])} vs {len(_open_orphan)}")
show("화면에 「연결」의 정의가 한 줄 있다 (붙음·auto·orphan)",
     all(w in _fn["정의"] for w in ("붙음", "auto", "orphan")))

print("\n" + "=" * 62)
print("전체 결과:", "PASS — 뷰어·trace 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
