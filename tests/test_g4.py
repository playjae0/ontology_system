# -*- coding: utf-8 -*-
"""G4 완료판정 — 정지점 4의 어서션을 실행 가능한 검사로.

  2′  : 질의 4단 + 이원 근거 채널 (queries.json 12문항 · 2홉 도달 · flow 특례
        · 링킹 미스 로그) + **순서 파생 3분기와 해상도 표기**(D-44 · CH5 5.1 규약 8)
  3′  : 품질층 = 신규 층 등록 절차의 첫 검증 대상(J10) — 수동 config 경로.
        causes 사슬 · cross 질의 · **Q1~8 회귀 무오염**(§8-6 채널분리)
  3.5′: 재인입 회귀 — 노드 중복 0 · provenance 복원 · run.py all 2회 동일 그래프

사용: python tests/test_g4.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import query as R                              # noqa: E402
from core import init, query as Q                             # noqa: E402
from core import store                                  # noqa: E402
from core.bootstrap import bootstrap, load_config, open_graph   # noqa: E402
from core.extract import EXTRACT_DIR                    # noqa: E402
from core.pipeline import finalize, run_document                  # noqa: E402

allok = True


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / "parsed" / name).read_text(encoding="utf-8"))


DOCS = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
QUERIES = json.loads((ROOT / "tests" / "fixtures" / "queries.json").read_text(encoding="utf-8"))


def full_run():
    init.init(fresh_=True)          # 클린의 정의는 진입점이 갖는다 (문서 7 §7.6-4)
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)
    for d in DOCS:
        run_document(load(f"{d}.json"))
    finalize()                          # 빌드 말미 패스 — 전역 재평가는 여기서 돈다


full_run()
P, QG = open_graph("process"), open_graph("quality")
CFG = load_config("process")

# ============================================================ 2′
print("\n■ 2′ — 질의 4단 + 이원 근거 채널 (CH5 5.1·5.2)")
results = {q["id"]: R.answer(q["q"]) for q in QUERIES["queries"]}
bad = [(q["id"], q["expected_path"], results[q["id"]]["path"])
       for q in QUERIES["queries"] if results[q["id"]]["path"] != q["expected_path"]]
show("queries.json 12문항이 expected_path대로 응답", not bad, str(bad))

show("flow 질의(5번)가 골격 대표 흐름을 통째로 공급",
     len(results[5]["facts"]) == sum(1 for e in P.edges if e["rel"] == "precedes"
                                     and P.get(e["src"])["polarity"] == "none"),
     f"{len(results[5]['facts'])}줄")
show("flow는 개념 레벨이다 — 축 인스턴스는 흐름에 없다 (J12)",
     not any("::cathode" in f or "::anode" in f for f in results[5]["facts"]))

# 2홉 도달: 공정 →(part_of 하향)→ 설비 →(has_property)→ 인자. 프론티어 전파의 실증.
show("2홉 도달 — part_of 하향으로 닿은 설비의 has_property 인자까지 수집",
     any("스태커의 관리인자" in f for f in results[4]["facts"]),
     str([f for f in results[4]["facts"] if "관리인자" in f][:2]))

show("링킹 미스 로그 기록 (하이브리드 도입 판정 데이터 — 5.4)",
     store.path(store.LINK_MISS).exists()
     and "리튬이온" in store.path(store.LINK_MISS).read_text(encoding="utf-8"))
show("답변 3단 — 근거 없음은 [일반지식] 표시와 함께 답한다",
     "[일반지식" in (results[12]["note"] or "") and not results[12]["facts"])
show("질의는 읽기 전용 (P6) — 질문 표기를 사전에 배우지 않는다",
     "리튬이온 배터리" not in store.read(store.DICTIONARY, {}))
show("precedes·mirrors는 기본 확장에서 제외 (5.1 규약 4)",
     "precedes" not in (CFG["query_traverse"] or {})
     and "mirrors" not in (CFG["query_traverse"] or {}))

# ---- 순서 파생 3분기 (D-44 · 틀 §4B-A11-5) ----
print("\n■ 2′ — 순서 파생 3분기와 해상도 표기 (M2 · CH5 5.1 규약 8)")
D = QUERIES["_derived_order"]
o = {k: R.answer(v) for k, v in D.items() if not k.startswith("_")}


def fact(key):
    """순서 답만 골라 본다 — 브리지는 순서 질문에도 상시 적용되므로(명세 §8-6)
    같은 답변에 걸침 사실이 함께 실린다. 그 딸림은 정상이고 판정 대상이 아니다."""
    return " / ".join(f for f in o[key]["facts"]
                      if "다음 공정" in f or "순서 정보 없음" in f)


show("① 자기 선언 — 그대로 답하고 해상도를 덧붙이지 않는다",
     fact("self") == "노칭 다음 공정은 스태킹이다", fact("self"))
show("② 부모 파생 + 동일 축값 인스턴스 하강",
     "탭용접::pre vision::cathode" in fact("derived_instance"), fact("derived_instance"))
show("② 파생 답에 **해상도 표기**", "기준)" in fact("derived_instance"))
show("② 공유 스텝 합류 자동 — 후속에 동일 축값이 없으면 개념 노드로 답한다",
     "탭용접::bead press" in fact("derived_merge"), fact("derived_merge"))
show("③ 조상까지 선언이 없으면 '순서 정보 없음' (추측 금지)",
     "순서 정보 없음" in fact("none"), fact("none"))

# ============================================================ 3′
print("\n■ 3′ — 품질층 = 신규 층 등록 절차의 첫 검증 대상 (J10 · 수동 config 경로)")
reg = store.read(store.REGISTRY, {})
show("품질층이 registry에 등록됨 (status=registered)",
     reg.get("quality", {}).get("status") == "registered", str(sorted(reg)))
show("등록 후에도 builtin 층은 공정층 1개",
     sum(1 for v in reg.values() if v["status"] == "builtin") == 1,
     str([k for k, v in reg.items() if v["status"] == "builtin"]))
show("층 등록에 코드가 없다 — config가 선언한 관계·카테고리로 registry가 선다",
     set(reg["quality"]["relations"]) == set(load_config("quality")["relations"]))

qcanon = {n["canonical"] for n in QG.nodes.values()}
show("causes 사슬 존재 (이물 유입 → 절연 파괴 → 내부 단락)",
     {"이물 유입", "절연 파괴", "내부 단락"} <= qcanon
     and any(QG.get(e["src"])["canonical"] == "절연 파괴"
             and QG.get(e["dst"])["canonical"] == "내부 단락"
             for e in QG.edges if e["rel"] == "causes"))
show("cross 9번 — occurs_in 역방향으로 노칭의 Failure들이 나온다",
     len([f for f in results[9]["facts"] if "공정에서 발생" in f]) >= 3,
     str([f for f in results[9]["facts"] if "공정에서 발생" in f][:2]))
show("cross 10번 — affects 역방향 직접 결과 + 수집 노드 간 causes 문장화",
     any("(으)로 이어질 수 있다" in f for f in results[10]["facts"])
     and any("원인이 될 수 있다" in f for f in results[10]["facts"]))
show("걸침 엣지는 출발 층(품질층) 템플릿으로 문장화 (§8-R4)",
     any("공정에서 발생한다" in f for f in results[9]["facts"]))

# ---- Q1~8 회귀 무오염 (§8-6 채널분리) ----
# 브리지를 끈 상태(= 단계 2 baseline)와 켠 상태를 대조한다. 1홉은 딸림 자체를 막지
# 못하므로(명세 §8-6) 판정은 "Failure가 안 딸려온다"가 아니라 **"직접 근거가 밀려나지
# 않는다"**다 — 브리지는 tier2로만 들어오고 잘림은 바깥부터다.
_real = Q.bridge
Q.bridge = lambda *a, **k: ({}, [])
base = {q["id"]: R.answer(q["q"]) for q in QUERIES["queries"][:8]}
Q.bridge = _real


def tier1(res):
    return {c["chunk_id"] for c in res["chunks"] if c["tier"] == 1}


drift = [q["id"] for q in QUERIES["queries"][:8]
         if base[q["id"]]["path"] != results[q["id"]]["path"]
         or tier1(base[q["id"]]) != tier1(results[q["id"]])]
show("Q1~8 회귀 무오염 — cross-layer on/off에서 경로·직접 근거 동일",
     not drift, str(drift))
show("브리지 유래 근거는 tier2로만 들어온다 (직접 근거를 밀어내지 않는다)",
     all(c["tier"] == 2 for r in results.values() for c in r["chunks"]
         if c["doc_id"] == "PFMEA01" and r is not results[9]))

# ============================================================ 3.5′
print("\n■ 3.5′ — 재인입 회귀 (노드 유일성 P4)")
before_n = len(P.nodes)
before_prov = {n["canonical"]: sorted(n["provenance"]) for n in P.nodes.values()}
for d in DOCS:
    run_document(load(f"{d}.json"))
finalize()
P2 = open_graph("process")
show("재인입 후 노드 수 불변 (중복 0)", len(P2.nodes) == before_n,
     f"{before_n} → {len(P2.nodes)}")
show("사전 재매칭으로 provenance 복원 (잃은 출처 0)",
     all(set(before_prov.get(n["canonical"], [])) <= set(n["provenance"])
         for n in P2.nodes.values()),
     str([n["canonical"] for n in P2.nodes.values()
          if not set(before_prov.get(n["canonical"], [])) <= set(n["provenance"])][:3]))
# 큐는 조건의 화면이지 이력이 아니다 — 재인입이 같은 조건을 다시 싣지 않아야 하고
# (중복 제거), 재계산하는 쪽은 해소된 조건을 내려야 한다(self-heal). 둘 다 3.5 규약 6.
q_after = store.read(store.QUEUE, [])
for d in DOCS:
    run_document(load(f"{d}.json"))
finalize()
q_again = store.read(store.QUEUE, [])
show("재인입이 큐를 증식시키지 않는다 (중복 제거 — 3.5 규약 6)",
     len(q_again) == len(q_after), f"{len(q_after)} → {len(q_again)}")
show("미검토 작업목록은 재인입에도 보존된다 (auto_node — 재검출되지 않는 상시 조건)",
     sum(1 for x in q_again if x["kind"] == "auto_node") ==
     sum(1 for x in q_after if x["kind"] == "auto_node"),
     str(sum(1 for x in q_again if x["kind"] == "auto_node")))
show("재인입 후에도 질의 응답 동일 (판정 무오염)",
     {i: R.answer(q["q"])["path"] for i, q in
      zip([q["id"] for q in QUERIES["queries"]], QUERIES["queries"])}
     == {i: r["path"] for i, r in results.items()})

# ============================================================ 근거 정렬 결정성
print("\n■ 근거 청크 정렬 — 결정적인가 (문서 5 §5.1-6)")
# 정렬 키 셋: ①tier(1이 앞) ②parsed_at 내림차순 ③chunk_id 사전순.
# 기준이 없으면 상한 8이 **무작위 축에서** 잘리고, 그 차이는 계기판 4에 잡히지
# 않는다 — 잘린 건수는 같고 잘린 대상만 다르기 때문이다.
_runs = [tuple(c["chunk_id"] for c in R.answer("노칭에서 발생할 수 있는 불량은?")["chunks"])
         for _ in range(5)]
show("같은 질문 5회의 근거 청크 집합·순서가 동일하다", len(set(_runs)) == 1,
     f"{len(set(_runs))}가지")
_res = R.answer("노칭에서 발생할 수 있는 불량은?")
_tiers = [c.get("tier") for c in _res["chunks"]]
show("tier1이 항상 tier2보다 앞이다 (정렬은 tier 안에서만)",
     _tiers == sorted(_tiers), str(_tiers))

# ============================================================ 관측 창구
print("\n■ 관측 창구 — 문서가 「직접 열람」이라 적은 자리에 명령이 있는가 (문서 7 §7.8)")
import subprocess as _sp2                                       # noqa: E402
def _run(*a):
    return _sp2.run([sys.executable, str(ROOT / "run.py"), *a],
                    capture_output=True, text=True, cwd=str(ROOT))

_ls = _run("show", "log")
show("show log — 로그 4종 요약이 돈다", _ls.returncode == 0
     and all(k in _ls.stdout for k in ("defects", "gate", "link_miss", "truncated")))
show("show log gate — 게이트 거부를 연다 (큐가 아니라 관측 신호)",
     _run("show", "log", "gate").returncode == 0)
show("show log link_miss / truncated — **두 계기판 로그를 각각** 연다",
     _run("show", "log", "link_miss").returncode == 0
     and _run("show", "log", "truncated").returncode == 0)
_se = _run("show", "extract")
show("show extract — 상태가 아니라 **내용**을 연다 (계약 B)",
     _se.returncode == 0 and "청크" in _se.stdout
     and _run("show", "extract", "PPT02").returncode == 0
     and "부착" in _run("show", "extract", "PPT02").stdout)
# **문자열 "cdn"을 세지 않는다.** 노드 id가 ULID(Crockford base32)라 26자 안에
# "CDN"이 우연히 들어간다 — 실측: 20회 중 1회 `01M10DM4QSCDN9YQP6PC35RADS`.
# 그 어서션은 무작위로 붉어져 526 기준선을 흔들었다. 재는 것은 이름이 아니라
# **바깥을 부르는 행위**다(§7.8 — 사내망에서 화면이 비어 뜨는 것을 막는 요구).
_EXTERNAL = ("http://", "https://", "//cdn", "@import", "fetch(",
             "xmlhttprequest", "<script src", "<link ")
_html = ROOT / "export" / "graph.html"
_hrc = _run("export", "html").returncode
_htxt = _html.read_text(encoding="utf-8").lower() if _html.exists() else ""
show("export html — 실물 파일을 낸다 (외부 자원 호출 0)",
     _hrc == 0 and _html.exists()
     and not [m for m in _EXTERNAL if m in _htxt],
     "" if _html.exists() else "파일 없음")
show("export mermaid quality — **빈 출력을 성공으로 내지 않는다**",
     _run("export", "mermaid", "quality").returncode != 0)
show("export mermaid cross — 걸침 관계를 층 구분과 함께 그린다",
     "occurs_in" in _run("export", "mermaid", "cross").stdout)


# ── B52 ① `query --json` 출력 계약 (문서 5 §5.2-6) ─────────────────────────
print("\n[B52 ①] query --json — 답 묶음 출력 계약")

from core import llm as llm_mod                                  # noqa: E402
from cli.export import _world, build_html, graph_data            # noqa: E402

_w = _world()


def _raises(fn):
    try:
        fn()
    except BaseException:                                        # noqa: BLE001
        return True
    return False

_J = {q["q"]: R.as_json(R.answer(q["q"])) for q in QUERIES["queries"]}
_T = {q["q"]: R.generate(R.answer(q["q"])) for q in QUERIES["queries"]}


def _count(text, marker):
    return sum(1 for ln in text.split("\n") if ln.strip().startswith(marker))


# **두 출력이 같은 것을 세는가**가 이 계약의 전부다. 화면(JSON)이 사람이 읽은
# 텍스트보다 넓거나 좁으면 「이 답의 근거」가 거짓이 된다.
_bad_f = [q for q, j in _J.items() if len(j["facts"]) != _count(_T[q], "[그래프 사실]")]
_bad_c = [q for q, j in _J.items() if len(j["chunks"]) != _count(_T[q], "[문서 근거]")]
_bad_p = [q for q, j in _J.items() if f"[경로] {j['path']}" not in _T[q]]
_bad_l = [q for q, j in _J.items()
          if j["linked"] and f"[링킹] {', '.join(j['linked'])}" not in _T[q]]
show(f"--json facts 건수 = 텍스트 [그래프 사실] 줄 수 (12문항)", not _bad_f, str(_bad_f[:2]))
show(f"--json chunks 건수 = 텍스트 [문서 근거] 줄 수 (12문항)", not _bad_c, str(_bad_c[:2]))
show(f"--json path = 텍스트 [경로] (12문항)", not _bad_p, str(_bad_p[:2]))
show(f"--json linked = 텍스트 [링킹] (12문항)", not _bad_l, str(_bad_l[:2]))

# `linked`(문자열)를 지우지 않았고, `linked_nodes`가 그것과 같은 것을 가리킨다.
_ln_ok = all(len(j["linked_nodes"]) == len(j["linked"])
             and all(f"{n['layer']}:{n['canonical']}" == s
                     for n, s in zip(j["linked_nodes"], j["linked"]))
             for j in _J.values())
show("linked_nodes = linked와 같은 수·같은 순서 (옛 키를 지우지 않았다)", _ln_ok)

_G = {i for g in _w.values() for i in g.nodes}
_nid_ok = all(n["node_id"] in _G for j in _J.values() for n in j["linked_nodes"])
show("linked_nodes[].node_id가 실제 그래프 노드다 (화면이 칠할 수 있다)", _nid_ok)

show("--json 묶음에 answer(생성된 답 텍스트)가 실린다",
     all(isinstance(j.get("answer"), str) and j["answer"] for j in _J.values()))

# **stdout에는 묶음 하나뿐**이다 — 모드 줄이 섞이면 파이프가 깨진다.
_jr = _run("query", "노칭 다음 공정은?", "--json", "--allow-mock")
try:
    _jp = json.loads(_jr.stdout)
except Exception as _e:                                          # noqa: BLE001
    _jp, _e = None, _e
show("run.py query --json — stdout이 JSON 한 덩어리다 (모드 줄은 stderr)",
     _jr.returncode == 0 and isinstance(_jp, dict) and _jp.get("path") == "graph_fact",
     _jr.stdout[:80])
show("--json 모드 줄이 stderr로 간다", "모드:" in _jr.stderr and "모드:" not in _jr.stdout)

# ③ 텍스트 경로는 변하지 않았다 — 플래그가 없으면 옛 화면 그대로다.
_tr = _run("query", "노칭 다음 공정은?", "--allow-mock")
show("--json 없으면 텍스트 경로 그대로 (모드 줄 + Q. 로 시작)",
     _tr.returncode == 0 and "모드:" in _tr.stdout and "\nQ. 노칭 다음 공정은?" in _tr.stdout)

# ── B52 ② run.py viewer — 검증 뷰어 ────────────────────────────────────────
print("\n[B52 ②] run.py viewer — 그래프 위의 질의")

import threading as _th                                          # noqa: E402
import urllib.error as _ue                                       # noqa: E402
import urllib.parse as _up                                       # noqa: E402
import urllib.request as _ur                                     # noqa: E402
from http.server import ThreadingHTTPServer                      # noqa: E402

from cli import viewer as V                                      # noqa: E402

_pg_on = build_html(_w, query_panel=True)
_pg_off = build_html(_w, query_panel=False)

# ⓒ **같은 템플릿, 플래그 하나** — 끄면 옛 산출과 한 글자도 다르지 않아야 한다.
_exported = (ROOT / "export" / "graph.html")
show("build_html(query_panel=False) == export html 산출 (템플릿은 하나다)",
     _exported.exists() and _exported.read_text(encoding="utf-8") == _pg_off)
_MARKS = ("qside", "highlight", "/api/query", "focusNode")
show("뷰어 HTML에 질문 패널·highlight 코드가 있다",
     all(m in _pg_on for m in _MARKS))
show("export html 산출에는 **없다** (파일 하나로 여는 산출은 물어볼 서버가 없다)",
     not [m for m in _MARKS if m in _pg_off])

# ⓔ 외부 자원 0 — 사내망에서 화면이 비어 뜨지 않는다.
_src = "".join((ROOT / "cli" / f).read_text(encoding="utf-8")
               for f in ("viewer.py", "export.py"))
# **재는 것은 이름이 아니라 바깥을 부르는 행위다** — 위 `_EXTERNAL` 주석이 말한
# 그대로다. 이 두 파일에는 「CDN을 쓰지 않는다」는 **문면**이 있고, 문자열 "cdn"을
# 세면 그 문면이 위반으로 잡힌다. `http://127.0.0.1`도 뷰어 제 주소이지 바깥이
# 아니다. 그래서 자원을 실제로 불러오는 구문과 절대 URL만 센다.
_out = [ln.strip()[:70] for ln in _src.split("\n")
        if any(m in ln.lower() for m in ("https://", "@import", "<script src", "<link "))
        or ("http://" in ln and "127.0.0.1" not in ln and "{HOST}" not in ln)
        or ('fetch("' in ln and 'fetch("/' not in ln)]
show("cli/viewer.py · cli/export.py — 바깥 자원을 부르는 자리 0", not _out, str(_out[:2]))

# ⓑ 서버를 빈 포트에 띄워 `/api/query`가 `--json`과 같은 묶음을 내는지 대조한다.
_port = V._free_port(8790)
_health = {"mode": "mock" if llm_mod.use_mock() else "실호출",
           "nodes": len(graph_data(_w)[0]), "edges": len(graph_data(_w)[1]),
           "layers": len(_w)}
_srv = ThreadingHTTPServer((V.HOST, _port), V._handler(_pg_on.encode("utf-8"), _health))
_th.Thread(target=_srv.serve_forever, daemon=True).start()


def _get(path, data=None, method="GET"):
    req = _ur.Request(f"http://{V.HOST}:{_port}{path}", data=data, method=method)
    try:
        with _ur.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8")
    except _ue.HTTPError as e:
        return e.code, e.read().decode("utf-8")


try:
    _q = "노칭 다음 공정은?"
    _sc, _body = _get("/api/query?q=" + _up.quote(_q))
    _api = json.loads(_body) if _sc == 200 else {}
    show("/api/query — --json과 **키 집합이 같다**",
         _sc == 200 and set(_api) == set(_J[_q]), f"{_sc} · {sorted(set(_api) ^ set(_J[_q]))}")
    show("/api/query — 같은 질문에 같은 값 (path·facts·chunks·linked_nodes)",
         _sc == 200 and all(_api.get(k) == _J[_q][k]
                            for k in ("path", "facts", "chunks", "linked_nodes")))
    _sc_h, _body_h = _get("/api/health")
    _h = json.loads(_body_h) if _sc_h == 200 else {}
    show("/api/health — mode·nodes·edges·layers",
         _sc_h == 200 and set(_h) == {"mode", "nodes", "edges", "layers"}
         and _h["nodes"] == _health["nodes"] and _h["mode"] in ("mock", "실호출"))
    show("/ — 뷰어 HTML을 낸다", _get("/")[0] == 200)
    show("q가 비면 400 (조용히 빈 답을 내지 않는다)", _get("/api/query?q=")[0] == 400)
    show("그 밖의 경로는 404", _get("/nope")[0] == 404)
    # **쓰기 라우트가 없다** — 파생물에서 그래프를 고치는 경로는 없다(문서 1 P5).
    show("쓰기 라우트 없음 — POST는 501로 거절된다",
         _get("/", data=b"{}", method="POST")[0] == 501
         and not hasattr(V._handler(b"", {}), "do_POST"))
finally:
    _srv.shutdown()
    _srv.server_close()

show("--port 뒤 번호가 없으면 멈춘다 (조용히 기본 포트로 가지 않는다)",
     _raises(lambda: V.main(["--port"])))


# ── B54 골든셋 채점기 · BM-25 대조군 (문서 5 §5.5-2·3·4) ────────────────────
print("\n[B54] 골든셋 채점기 · BM-25 상시 대조군")

import ast as _ast                                                # noqa: E402
from collections import Counter                                    # noqa: E402
from core import bm25 as _bm                                      # noqa: E402
from cli import golden as _G                                      # noqa: E402

# ③ **대조군의 정의는 「무엇을 안 읽는가」다** — 그래프·사전·골격을 읽으면
# 대조군이 아니라 이 시스템의 일부가 되어 비교의 뜻이 사라진다.
_src = (ROOT / "core" / "bm25.py").read_text(encoding="utf-8")
_imported = set()
for _n in _ast.walk(_ast.parse(_src)):
    if isinstance(_n, _ast.ImportFrom) and (_n.module or "").startswith("core"):
        _imported |= {a.name for a in _n.names}
    elif isinstance(_n, _ast.Import):
        _imported |= {a.name.split(".")[1] for a in _n.names
                      if a.name.startswith("core.")}
show("core/bm25.py가 import하는 core 모듈은 store 하나다 (대조군의 정의)",
     _imported == {"store"}, str(sorted(_imported)))
show("그래프·사전·골격·임베딩·LLM을 읽지 않는다",
     not [w for w in ("graph", "dictionary", "skeleton", "matcher",
                      "embeddings", "llm") if f"core import {w}" in _src
          or f"core.{w}" in _src])
show("BM-25 상수가 한 곳에 있다 (k1·b)",
     _src.count("K1 = ") == 1 and _src.count("B = ") == 1
     and _bm.K1 == 1.5 and _bm.B == 0.75)
# 토큰화 — CJK 2-gram의 근거가 실제로 성립하는가
_t1, _t2 = set(_bm.tokens("노칭 프레스")), set(_bm.tokens("노칭프레스"))
show("CJK 2-gram — 「노칭 프레스」와 「노칭프레스」가 토큰을 공유한다",
     len(_t1 & _t2) >= 3, f"{sorted(_t1 & _t2)}")
show("영숫자는 단어로, CJK는 2-gram으로 가른다",
     "cp01" in _bm.tokens("CP01 노칭") and "노칭" in _bm.tokens("CP01 노칭"))
show("한 글자 낱말은 그 자체가 토큰이다 (2-gram이 삼키지 않는다)",
     _bm.tokens("탭 용접")[:1] == ["탭"] or "탭" in _bm.tokens("탭 용접"))
_idx = _bm.build()
show("인덱스는 청크 텍스트로 선다 (store 경유)", len(_idx.ids) > 0 and _idx.avg > 0,
     f"청크 {len(_idx.ids)} · 어휘 {len(_idx.idf)}")
_h1 = _bm.search("노칭 프레스 금형 관리", 5, index=_idx)
show("search가 상위 k를 점수 내림차순으로 낸다",
     len(_h1) == 5 and all(_h1[i][1] >= _h1[i + 1][1] for i in range(4)))
show("동점은 chunk_id로 갈라 결정적이다 (같은 입력 → 같은 출력)",
     _bm.search("노칭", 8, index=_idx) == _bm.search("노칭", 8, index=_idx))
show("docs_of가 chunk_id에서 doc_id를 뽑는다 ({doc_id}:… 계약)",
     _bm.docs_of([("CP01:abc", 1.0), ("PPT01:x-y", 0.5)]) == ["CP01", "PPT01"])
show("인덱스를 저장하지 않는다 (파생물 — P5)",
     not (ROOT / "data" / "bm25_index.json").exists()
     and "atomic_write" not in _src and "store.write" not in _src)

# ① 문항 틀 — §5.5-2 기준 구성
_blank = _G.blank_set()
_bt = Counter(q["type"] for q in _blank["queries"])
show("golden init 틀이 기준 120건이다 (§5.5-2)", len(_blank["queries"]) == 120,
     str(len(_blank["queries"])))
show("유형 구성 — 지원 6종 각 15 · noanswer/multihop/out 각 10",
     all(_bt[t] == 15 for t in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q8"))
     and all(_bt[t] == 10 for t in ("noanswer", "multihop", "out")))
show("expected_path가 유형에서 파생된다 (§5.3 유형표 대응)",
     _G.TYPE_PATH["Q1"] == "chunk" and _G.TYPE_PATH["Q2"] == "graph_fact"
     and _G.TYPE_PATH["Q8"] == "general_knowledge"
     and _G.TYPE_PATH["multihop"] == "both"
     and _G.TYPE_PATH["noanswer"] == _G.TYPE_PATH["out"] == "general_knowledge")
show("expected_path는 닫힌 4값 안이다 (문서 7 §7.6)",
     set(_G.TYPE_PATH.values()) <= set(_G.PATHS) and len(_G.PATHS) == 4)

# 형식 검사는 **문항 단위**다 — 사내가 채워 가는 중간 상태를 허용한다
_mixed = ROOT / "data" / "_b54_mixed.json"
_mixed.write_text(json.dumps({"version": 1, "queries": [
    {"id": "OK1", "type": "Q1", "q": "노칭 다음 공정은?", "expected_path": "chunk"},
    {"id": "EMPTY", "type": "Q1", "q": "  ", "expected_path": "chunk"},
    {"id": "BADT", "type": "Q9", "q": "x", "expected_path": "chunk"},
    {"id": "BADP", "type": "Q1", "q": "x", "expected_path": "없는경로"},
]}, ensure_ascii=False), encoding="utf-8")
_okq, _skip = _G.load(_mixed)
show("형식 밖 문항은 **건너뛰고 파일 전체를 거부하지 않는다**",
     [q["id"] for q in _okq] == ["OK1"] and len(_skip) == 3)
show("건너뛴 사유를 문항마다 남긴다 (조용히 빠뜨리지 않는다)",
     all(w for _, w in _skip)
     and any("닫힌 값 밖" in w for _, w in _skip)
     and any("q가 비었다" in w for _, w in _skip), str(_skip[1])[:52])
_mixed.unlink()

# ② 채점 4축 — expected_*가 없으면 그 축은 **채점하지 않는다**(0점이 아니다)
_gs = ROOT / "tests" / "fixtures" / "golden_sample.json"
_gq, _ = _G.load(_gs)
_rows = _G.score_set(_gq, 8)
_agg = _G.aggregate(_rows, 8)
show("골든셋 3문항이 4축 전부 채점된다",
     _agg["n"] == 3 and _agg["path_n"] == 3 and _agg["evidence_n"] == 3
     and _agg["bm25_n"] == 3 and _agg["linking_n"] == 3)
# ⓒ **둘 다 계산되고 서로 다른 값을 낸다** — 같으면 대조군이 의미 없다.
show("evidence@k와 bm25@k가 **둘 다 계산된다**",
     _agg["evidence_at_k"] is not None and _agg["bm25_at_k"] is not None,
     f"evidence {_agg['evidence_at_k']} · bm25 {_agg['bm25_at_k']}")
show("두 축이 **다른 값**이다 — 대조군이 들러리가 아니다",
     _agg["evidence_at_k"] != _agg["bm25_at_k"])
show("대조군이 이기는 문항도 있다 (한쪽으로만 기울면 비교가 아니다)",
     any(r["bm25"]["ok"] and not r["evidence"]["ok"] for r in _rows)
     and any(r["evidence"]["ok"] and not r["bm25"]["ok"] for r in _rows))
_noexp = _G.score_set([{"id": "N", "type": "Q1", "q": "노칭 다음 공정은?",
                        "expected_path": "graph_fact"}], 8)
show("expected_linked/docs가 없으면 그 축은 None이다 (0점이 아니다)",
     _noexp[0]["linking"] is None and _noexp[0]["evidence"] is None
     and _noexp[0]["bm25"] is None and _noexp[0]["path"]["ok"] is True)
show("linking은 부분집합 판정이다 — 기대가 실제에 다 들어야 ok",
     _G._grade({"type": "Q1", "q": "x", "expected_path": "chunk",
                "expected_linked": ["a", "b"]},
               {"path": "chunk", "linked": ["a"], "chunks": []},
               _idx, 8)["linking"]["ok"] is False)

# ⓔ 측정이 재료 로그를 오염시키지 않는다 (§5.5 규율 4)
_lm = store.path(store.LINK_MISS)
_b = _lm.stat().st_size if _lm.exists() else 0
_G.score_set(_gq + [{"id": "MISS", "type": "out", "q": "탕수육 부먹 찍먹?",
                     "expected_path": "general_knowledge"}], 8)
_a = _lm.stat().st_size if _lm.exists() else 0
show("채점 중 link_miss가 늘지 않는다 (측정이 제 흔적을 세지 않는다)", _a == _b,
     f"{_b} → {_a}")
# **끄는 것은 재료 로그뿐이다** — 결함까지 죽이면 G5를 측정이 우회한다.
_df = store.path(store.DEFECTS)
_b2 = _df.stat().st_size if _df.exists() else 0
with store.muted_material_logs():
    store.append_line(store.LINK_MISS, "MUTED")
    store.append_line(store.DEFECTS, "B54 뮤트 시험 — 결함은 살아야 한다")
show("뮤트는 재료 로그만 끈다 — defects는 살아 있다 (G5를 우회하지 않는다)",
     _df.stat().st_size > _b2 and (_lm.stat().st_size if _lm.exists() else 0) == _a)
show("뮤트가 끝나면 원래 함수로 복구된다",
     store.append_line.__name__ == "append_line")
show("스위치는 store 하나다 — 계기판이 제 벌을 들지 않는다",
     "muted_material_logs" in (ROOT / "cli" / "platform.py").read_text(encoding="utf-8")
     and "store.append_line = " not in
     (ROOT / "cli" / "platform.py").read_text(encoding="utf-8"))

# 채점은 answer()까지다 — ⑧(답변 생성)을 부르지 않는다
show("채점기가 generate(⑧)를 부르지 않는다 (재는 것은 근거 선택이지 문장이 아니다)",
     "generate" not in (ROOT / "cli" / "golden.py").read_text(encoding="utf-8"))
# 같은 계산이 두 벌이 되지 않는다
_plat = (ROOT / "cli" / "platform.py").read_text(encoding="utf-8")
show("cmd_accuracy가 채점기를 부른다 (경로 일치를 다시 세지 않는다)",
     "G.score_set" in _plat and "G.render" in _plat)
show("계기판 1 분모가 골든셋이 서면 바뀐다 (§5.5-1)",
     "골든셋 {len(smoke)}문항" in _plat and "_basis" in _plat)

# 로그는 **명령**이 쓴다 — CLI를 실제로 돌려 잰다(정의만 보고 세지 않는다).
_n0 = len(store.read(_G.LOG, []))
_gr = _run("golden", "score", "--set", str(_gs))
_log = store.read(_G.LOG, [])
show("golden score가 돈다 — 4축 표와 「메커니즘 점검」 문면",
     _gr.returncode == 0 and "bm25@k" in _gr.stdout
     and "메커니즘 점검" in _gr.stdout and "대조군 대비" in _gr.stdout)
show("golden_log.json이 한 줄씩 쌓인다 (로그이지 큐가 아니다 · 최근 50)",
     len(_log) == _n0 + 1 and len(_log) <= 50
     and {"at", "set", "n", "k", "path_rate", "linking_recall",
          "evidence_at_k", "bm25_at_k", "by_type"} <= set(_log[-1]),
     f"{_n0} → {len(_log)}")
_gj = _run("golden", "score", "--set", str(_gs), "--json")
show("--json이 같은 것을 JSON으로 낸다",
     _gj.returncode == 0
     and set(json.loads(_gj.stdout)) == {"summary", "rows", "skipped"}
     and json.loads(_gj.stdout)["summary"]["bm25_at_k"] == _agg["bm25_at_k"])
_gi = _run("golden", "init", str(ROOT / "data" / "_b54_init.json"))
_made = json.loads((ROOT / "data" / "_b54_init.json").read_text(encoding="utf-8"))
show("golden init이 120건 틀을 쓰고 유형 분포를 찍는다",
     _gi.returncode == 0 and len(_made["queries"]) == 120
     and "유형 분포" in _gi.stdout and "기대 경로" in _gi.stdout)
_gi2 = _run("golden", "init", str(ROOT / "data" / "_b54_init.json"))
show("이미 있으면 **덮지 않는다** (사내가 채운 문항을 지우는 명령이 아니다)",
     "덮지 않는다" in _gi2.stdout
     and json.loads((ROOT / "data" / "_b54_init.json").read_text(encoding="utf-8"))
     == _made)
(ROOT / "data" / "_b54_init.json").unlink()
_sb = _run("show", "bm25", "노칭 프레스 금형 관리", "3")
show("show bm25 — 대조군을 사람이 직접 본다",
     _sb.returncode == 0 and "대조군이다" in _sb.stdout
     and "그래프·사전·LLM을 쓰지 않는다" in _sb.stdout)

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G4 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
