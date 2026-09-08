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

print("\n" + "=" * 62)
print("전체 결과:", "PASS — G4 완료판정 충족" if allok else "FAIL")
sys.exit(0 if allok else 1)
