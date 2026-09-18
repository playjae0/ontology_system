# -*- coding: utf-8 -*-
"""G6 ⑥ 후보와 대장 — 상한·조건부 retry·auto 표시(B73) · 사전 키=조회 키·판정 대장·뷰어(B74) · 임베딩 선택·스코프 필터·실패 비용(B75)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, _env72, _run72, _sp72, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exits_scan as _EX                                           # noqa: E402

_rows61 = _EX.scan()                      # 이 스위트의 재료 — 제 손으로 잰다
_st61 = [r for r in _rows61 if r["mark"] == "상태"]


def _at61(rows):
    return [r["file"] + ":" + str(r["line"]) for r in rows]


print("\n■ B73 ①②③ — 후보 상한 · 조건부 retry · auto 표시")

from core import matcher as _MT73                                  # noqa: E402
from core.dictionary import Dictionary as _DIC73                   # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_g73 = open_graph("process")
_cfg73 = load_config("process")
_dic73 = _DIC73.open()
# **스코프 단계의 재료는 이 스위트가 만든다**(B78 2c) — 상한 안의 스코프 pool은
# 노드를 불리기 전에 잡아야 한다(불린 뒤에는 「겹침」으로 갈린다).
_MT73.candidates("노칭::금형 클리어런스XX", "Property", "process", _g73, _dic73,
                 parent="노칭", cfg=_cfg73)
# 같은 카테고리에 노드를 많이 세운다 — 「전량이면 커진다」를 재는 조건.
for _i in range(60):
    _g73.add_node(f"노칭::설비{_i:02d}", "Unit", "auto", provenance=["t"],
                  parent="노칭" if _i % 2 else "스태킹", _scoped=True)
_g73.save()
_c73 = _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73)
show("① 후보 수가 상한 안이다 (전량이 아니다)",
     len(_c73) <= _MT73.CANDIDATE_TOP_N,
     f"후보 {len(_c73)} · 상한 {_MT73.CANDIDATE_TOP_N} · 층 노드 {len(_g73.nodes)}")
show("① 상한이 손잡이 하나다 (코드에 흩어져 있지 않다)",
     isinstance(_MT73.CANDIDATE_TOP_N, int) and _MT73.CANDIDATE_TOP_N > 0)
# **스코프 근처가 먼저다** — 같은 부모 아래 노드가 다른 부모보다 앞선다.
_cs73 = _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73,
                         parent="노칭", cfg=_cfg73)
show("① 같은 부모 아래 후보가 있으면 다른 부모는 먼저 오지 않는다 (스코프 근처)",
     _cs73 and all(c.get("parent") == "노칭" for c in _cs73),
     f"{len(_cs73)}건 · 부모 {sorted({c.get('parent') for c in _cs73})}")
show("① 스코프 단계는 임베딩을 부르지 않는다 (LLM·임베딩 0)",
     (_MT73.STATS.get("스코프", 0) + _MT73.STATS.get("스코프+", 0)) >= 1
     and _MT73.STATS.get("임베딩", 0) == 0,
     str({k: v for k, v in _MT73.STATS.items() if v}))
# **입력 크기가 노드 수와 무관하다** — 판정에 올라가는 후보 JSON의 바이트.
_b1 = len(json.dumps(_MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73),
                     ensure_ascii=False).encode())
for _i in range(60, 500):
    _g73.add_node(f"노칭::설비{_i:03d}", "Unit", "auto", provenance=["t"])
_g73.save()
_b2 = len(json.dumps(_MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73),
                     ensure_ascii=False).encode())
show("① 노드가 8배로 늘어도 판정 입력 크기가 그대로다 (비용이 그래프에 비례하지 않는다)",
     _b2 <= _b1 * 1.2, f"노드 {len(_g73.nodes)} · {_b1:,}B → {_b2:,}B")
# **사전 히트는 상한과 무관하게 포함된다** — 결정적 경로가 잘리면 안 된다.
_nid73 = _g73.add_node("노칭::사전설비", "Unit", "auto", provenance=["t"])
_dic73.register("노칭::사전설비", _nid73, provenance="t")
_ce73 = _MT73.candidates("노칭::사전설비", "Unit", "process", _g73, _dic73)
show("① 사전 히트는 상한과 무관하게 포함된다 (결정적 경로를 자르지 않는다)",
     any(c.get("exact") and c["id"] == _nid73 for c in _ce73))
show("① mock 세계에서 좁히기에 LLM 0 (어휘 겹침으로 고른다)",
     _MT73.STATS.get("겹침", 0) >= 1 and _MT73.STATS.get("임베딩", 0) == 0,
     str({k: v for k, v in _MT73.STATS.items() if v}))
# **실호출 갈래는 임베딩을 부른다** — 배선의 증거는 미설정 실패(NotConfigured)다.
# **조건이 옮겨졌다**(B75 ①): `auto`에서는 임베딩이 없으면 겹침으로 떨어지는 것이
# 정답이라 이 지점에 닿지 않는다. 그래서 **사람이 켰을 때**(`CANDIDATE_NARROW=embed`)
# 로 잰다 — 어서션을 지우지 않고 조건을 옮긴다(문서 7 §7.6-2의 9지점 도달성).
_um73 = _MT73.gateway.use_mock
_MT73.gateway.use_mock = lambda: False
_MT73.narrow.set_narrow("embed")
try:
    _MT73.candidates("노칭::설비XX", "Unit", "process", _g73, _dic73)
    _emb73 = "불렀는데 조용히 통과"
except Exception as _e73:
    _emb73 = type(_e73).__name__
finally:
    _MT73.narrow.set_narrow(None)
    _MT73.gateway.use_mock = _um73
show("① 실호출 경로가 embed()에 닿는다 (CANDIDATE_NARROW=embed · 미설정이면 시끄럽게)",
     _emb73 == "NotConfigured", _emb73)

# ③ 후보에 status — auto는 표시되고, 유사도 매칭은 uncertain으로 내려간다
show("③ 후보가 status와 근거 건수를 싣는다 (판정이 auto를 안다)",
     all("status" in c and "evidence" in c for c in _ce73))
_auto73 = [c for c in _MT73.candidates("노칭::설비00", "Unit", "process", _g73, _dic73)
           if c.get("status") == "auto" and not c.get("exact")]
_v73 = _MT73.match("노칭::설비0", _auto73, "Unit", _cfg73)
show("③ auto 후보에 **유사도로는 붙지 않는다** (uncertain — 연쇄를 끊는다)",
     _v73["type"] == _MT73.UNCERTAIN or _v73["matched_id"] is None, str(_v73))
_conf73 = [dict(c, status="confirmed") for c in _auto73]
_v73b = _MT73.match("노칭::설비0", _conf73, "Unit", _cfg73)
show("③ confirmed 후보는 지금과 같다 (사람이 확인한 노드에는 붙는다)",
     _v73b["type"] == _MT73.MATCH, str(_v73b))
show("③ 지시문이 그 규칙을 말하고 판이 올랐다",
     "status" in (ROOT / "prompts/3.4_judge.md").read_text(encoding="utf-8")
     and "version: j-1.1" in (ROOT / "prompts/3.4_judge.md").read_text(encoding="utf-8"))

# ② retry는 조건부다 — 후보 집합이 그대로면 LLM 0
from core.build import retry as _RT73                                    # noqa: E402
init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_e73 = json.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
_e73["doc_id"], _e73["records"] = "B73ORPH", _e73["records"][:4]
for _r in _e73["records"]:
    _r["process_ref"] = "없는공정QQ"
_run72(_e73)
_RT73.retry_orphans()
_it73 = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
_at1 = _it73[0].get("attempts") if _it73 else None
_RT73.retry_orphans()                      # 그래프 불변 — 다시 돌 이유가 없다
_it73b = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
_at2 = _it73b[0].get("attempts") if _it73b else None
show("② 후보 집합이 그대로면 재시도가 돌지 않는다 (같은 답을 비용으로 바꾸지 않는다)",
     _at1 == _at2 and _at1, f"attempts {_at1} → {_at2}")
show("② 항목이 이력을 갖는다 — attempts · first_seen · last_tried",
     all(k in _it73b[0] for k in ("attempts", "first_seen", "last_tried")),
     str({k: v for k, v in _it73b[0].items()
          if k in ("attempts", "first_seen")})[:80])
# **이력은 payload 밖이다** — payload는 동일성 키이고 거기에 시각이 들어가면
# 「클린 2회 동일 그래프」가 깨진다(이 회차에서 한 번 깼다 · D-152).
show("② 이력이 payload를 오염시키지 않는다 (멱등 판정의 대조 단위)",
     not any(k in (_it73b[0]["payload"] or {})
             for k in ("attempts", "last_tried", "last_fp")))
_it73b[0].update({"attempts": _RT73.ATTEMPT_MAX, "last_fp": ""})
store.write(store.QUEUE, _it73b + [x for x in store.read(store.QUEUE, [])
                                   if x["kind"] != "orphan_anchor"])
_RT73.retry_orphans()
_it73c = [x for x in store.read(store.QUEUE, []) if x["kind"] == "orphan_anchor"]
show("② 상한을 넘으면 더 돌지 않는다 (사람 판정 대기)",
     _it73c[0].get("attempts") == _RT73.ATTEMPT_MAX)
_qb73 = _io.StringIO()
with _ctx.redirect_stdout(_qb73):
    PF.cmd_queue("orphan_anchor")
show("② 화면이 이력을 말한다 (몇 회 돌았고 끝났는지)",
     "회 재시도" in _qb73.getvalue() and "사람 판정 대기" in _qb73.getvalue(),
     [l.strip() for l in _qb73.getvalue().splitlines() if "재시도" in l][:1])
# ── B77 ③ 상태 거부는 **근거 자리**를 말한다 · 등록 넷의 역방향 ──────────
# B61 계약에 ④근거가 붙었다: 「무엇을 보고 그렇게 판정했나」. 사내 실측에서
# `--revise`가 「등록돼 있지 않다」만 말해, 사람이 `review/`·`data/`를 옮기고도
# **시스템이 어느 파일을 보는지** 몰랐다. 문면을 세지 않는다 — 경로가 있는가다.
show("③ `[상태]` 거부 전부가 근거 자리(경로)를 말한다 (B61 계약 ④)",
     not _EX.no_evidence(_rows61),
     f"상태 {len(_st61)}곳 · 근거 없음 {_at61(_EX.no_evidence(_rows61))}")
_orp77 = _P.review() / "옮기다빠진ZZ"
_orp77.mkdir(parents=True, exist_ok=True)
(_orp77 / "approval.json").write_text(
    json.dumps({"doc_type": "옮기다빠진ZZ", "approved_by": "시험자"},
               ensure_ascii=False), encoding="utf-8")
_b77 = _io.StringIO()
try:
    with _ctx.redirect_stdout(_b77):
        PF.cmd_doctypes()
finally:
    shutil.rmtree(_orp77, ignore_errors=True)
show("③ 승인 산출만 있고 등록부에 없는 이름을 화면이 낸다 (역방향 대조)",
     "옮기다빠진ZZ" in _b77.getvalue()
     and "review/옮기다빠진ZZ/approval.json" in _b77.getvalue(),
     [l.strip() for l in _b77.getvalue().splitlines() if "옮기다빠진ZZ" in l][:1])

# ════════════════════════════════════════════════════════════════════
# B74 — 사전 키 = 조회 키 · 판정 대장 · 뷰어 재료 · 행별 report
# ════════════════════════════════════════════════════════════════════
print("\n── B74 ① 사전이 실제로 히트한다 (키 = 조회 키) ──")
from core.build import ledger as _LG74                                   # noqa: E402
from core import matcher as _MT74                                  # noqa: E402
from core.llm import gateway as _LL74, narrow                                      # noqa: E402
from core.build.build import entity_key as _KEY74                        # noqa: E402
from core.dictionary import Dictionary as _DIC74                   # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _ingest74(doc_id, n=6):
    """같은 문서를 두 번 넣는 자리 — 예고·판정·실호출 사용량을 같이 받는다."""
    seen = {"쓴_호출": _LL74.usage_total()["calls"]}
    _run72(_env72(doc_id, n), notice=lambda i: seen.setdefault(i["단계"], i))
    seen["쓴_호출"] = _LL74.usage_total()["calls"] - seen["쓴_호출"]
    return seen


_a74 = _ingest74("B74DOC")
_s1 = dict(_MT74.STATS)
_b74 = _ingest74("B74DOC")
_s2 = dict(_MT74.STATS)
show("① 2회째 인입은 **판정 함수에 도달하지 않는다** (전부 exact 경로)",
     _s2["판정"] == 0 and _s2["사전"] > 0,
     f"1회차 판정 {_s1['판정']}·사전 {_s1['사전']} → 2회차 판정 {_s2['판정']}"
     f"·사전 {_s2['사전']}")
show("① 예고의 사전 히트 == 판정의 사전 경로 수 (같은 키·같은 함수)",
     _b74["판정예고"]["사전_히트"] == _s2["사전"],
     f"예고 {_b74['판정예고']['사전_히트']} · 판정 {_s2['사전']}")
show("① 예고의 상한이 실제 호출을 덮는다 (처음 인입 — 사전이 도는 중에 찬다)",
     _a74["판정예고"]["예상_호출"] >= _s1["판정"],
     f"예고 ≤{_a74['판정예고']['예상_호출']} · 실제 {_s1['판정']}")

_g74 = open_graph("process")
_cfg74 = load_config("process")
_dic74 = _DIC74.open()
_u74 = next(n for n in _g74.nodes.values()
            if n.get("category") == "Unit" and n.get("status") == "auto")
_pa74 = _u74.get("parent") or _u74.get("mirror_scope")
_sc74 = (_cfg74.get("canonical_scope") or {}).get("bind_categories", [])
_k74, _pol74, _, _ = _KEY74(_u74["canonical"].split("::")[-1], "Unit", _cfg74,
                            parent_canonical=_pa74)
show("① 등재된 키가 **해소가 여는 키**다 (exact 후보가 선다)",
     any(c["id"] == _u74["id"] for c in
         _MT74.dict_hits(_k74, "Unit", "process", _g74, _dic74,
                         polarity=_pol74, parent=_pa74, scope_cats=_sc74)),
     f"키 {_k74!r}")
show("① 같은 표기·**다른 부모**는 exact에 들지 않는다 (notching/separator의 cutter)",
     not _MT74.dict_hits(_k74, "Unit", "process", _g74, _dic74,
                         polarity=_pol74, parent="다른공정XX",
                         scope_cats=_sc74))
show("① 원 표기 키는 그대로 남는다 (질의 링킹의 표면형 스캔)",
     any(_n74 == _u74["canonical"].split("::")[-1]
         for _n74 in _dic74.surfaces()),
     f"사전 표기 {len(list(_dic74.surfaces()))}종")
_dup74 = _sp72.run([sys.executable, str(ROOT / "tests/dup_scan.py")],
                   capture_output=True, text=True, cwd=str(ROOT))
show("① 같은 층·같은 canonical·live 노드는 하나뿐이다 (상시 어서션)",
     _dup74.returncode == 0, (_dup74.stdout or "").strip().splitlines()[-1][:70])

print("\n── B74 ② 판정 대장 ──")
_led74 = _LG74.read("B74DOC")
_rows74 = (_led74 or {}).get("rows") or []
_env74 = _env72("B74DOC", 6)
_sch74 = json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8"))
_f74 = _sch74["fields"]
_vals74 = sum(1 for r in _env74["records"] for f, sp in _f74.items()
              if sp.get("role") == "entity" and isinstance(r.get(f), str)
              and r[f].strip())
_anc74 = len(_env74["records"])
_att74 = sum(1 for r in _env74["records"] for f, sp in _f74.items()
             if sp.get("role") in ("attribute", "content")
             and r.get(f) not in (None, "")
             and r.get(sp.get("attach_to_field")) not in (None, ""))
show("② 행 수 == entity 값 수 + anchor 행 수 + 부착 시도 수",
     len(_rows74) == _vals74 + _anc74 + _att74,
     f"{len(_rows74)} == {_vals74}+{_anc74}+{_att74}")
show("② path·verdict가 닫힌 값 밖이면 없다",
     all(r["path"] in _MT74.PATHS and r["verdict"] in _LG74.VERDICTS
         for r in _rows74),
     f"path {sorted({r['path'] for r in _rows74})}")
show("② 재인입 뒤 이전 대장이 남지 않는다 (덮는다 — 정본이 아니라 장부다)",
     all(r["verdict"] != "new" for r in _rows74)
     and sum(1 for r in _rows74 if r["role"] == "entity") == _vals74,
     f"판정 {sorted({r['verdict'] for r in _rows74})}")
show("② 대장의 llm.calls 합 == 그 인입이 실제로 부른 수 (mock 세계는 0이다)",
     sum((r.get("llm") or {}).get("calls", 0) for r in _rows74) == _b74["쓴_호출"],
     f"대장 {sum((r.get('llm') or {}).get('calls', 0) for r in _rows74)} "
     f"· 실제 {_b74['쓴_호출']}")
_v74 = _MT74.match("아무것도없는표기ZZ", [], "Unit", _cfg74)
show("② 판정 반환에 path 한 키가 늘고 계약 3키는 그대로다 (문서 4 §4.3-6)",
     set(_v74) >= {"type", "matched_id", "confidence", "path"}
     and _v74["path"] in _MT74.PATHS, str(_v74))

print("\n── B74 ③ 뷰어 재료 ──")
from cli import export as _EXP74                                   # noqa: E402
_nd74, _ed74 = _EXP74.graph_data(_EXP74._world())
show("③ 엣지가 status·prov·id를 지고 간다 (저장에는 있었는데 화면에 없었다)",
     all({"status", "prov", "id"} <= set(e) for e in _ed74))
show("③ 노드의 made_by가 닫힌 집합 ∪ {seed, unknown}이다",
     all(n["made_by"] in tuple(_MT74.PATHS) + ("seed", "unknown")
         for n in _nd74),
     str(sorted({n["made_by"] for n in _nd74})))
_html74 = _EXP74.build_html(_EXP74._world())
show("③ html의 DATA에 rel·made_by가 실리고 외부 CDN이 0이다",
     '"rel"' in _html74 and '"made_by"' in _html74
     and 'src="http' not in _html74 and 'href="http' not in _html74)
_doc74 = "B74DOC"
_filtered = {n["id"] for n in _nd74 if _doc74 in (n.get("docs") or [])}
_showdoc = {n["id"] for _l, _gg in _EXP74._world().items()
            for n in _gg.nodes.values()
            if ops.is_live(n) and any(str(p).startswith(_doc74)
                                  for p in n.get("provenance") or [])}
show("③ 문서 필터로 거른 노드 집합 == show doc의 노드 집합",
     _filtered == _showdoc and _filtered,
     f"{len(_filtered)}개")

print("\n── B74 ④ 행별 show report ──")
from cli import show as _SH74                                      # noqa: E402
_buf74 = _io.StringIO()
with _ctx.redirect_stdout(_buf74):
    _SH74.cmd_report([_doc74])
_out74 = _buf74.getvalue()
_su74 = _LG74.summary(_rows74)
show("④ 머리 집계의 각 수 == 대장에서 센 수",
     all(f"{k} {v}" in _out74 for k, v in
         (("값", _su74["값"]), ("사전", _su74["사전"]), ("신규", _su74["신규"]),
          ("불확실", _su74["불확실"]))),
     _out74.splitlines()[1].strip()[:70])
_jb74 = _io.StringIO()
with _ctx.redirect_stdout(_jb74):
    _SH74.cmd_report([_doc74, "--json"])
show("④ --json의 행 수 == 대장 행 수",
     len(json.loads(_jb74.getvalue())["rows"]) == len(_rows74))
try:
    _SH74.cmd_report(["없는문서ZZ"])
    _ref74 = ""
except SystemExit as e:
    _ref74 = str(e)
show("④ 없는 doc_id는 **상태 거부**다 (원인 + 칠 수 있는 다음 줄)",
     "대장" in _ref74 and "▶ 다음 줄" in _ref74
     and ("python run.py" in _ref74 or "python -m cli." in _ref74),
     _ref74.splitlines()[0][:70] if _ref74 else "거부하지 않았다")
_db74 = _io.StringIO()
with _ctx.redirect_stdout(_db74):
    _SH74.cmd_doc([_doc74])
show("④ show doc 끝이 행별 명령을 가리킨다 (진입점을 늘리지 않는다)",
     f"show report {_doc74}" in _db74.getvalue(),
     _db74.getvalue().strip().splitlines()[-1].strip()[:70])

# ════════════════════════════════════════════════════════════════════
# B75 — 임베딩은 선택 · 스코프는 하드 필터 · 비용은 실패해도 보인다
# ════════════════════════════════════════════════════════════════════
print("\n── B75 ① 임베딩은 선택이다 ──")
from core.llm import embeddings as _EM75                              # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _env75(doc_id, names, ref="노칭"):
    """같은 공정 아래 **서로 다른 관리항목 N개** — 후보가 상한을 넘게 만드는 재료."""
    e = json.loads((ROOT / "tests/fixtures/parsed/CP01.json").read_text(encoding="utf-8"))
    base = dict(e["records"][0])
    e["doc_id"] = doc_id
    e["records"] = []
    for i, nm in enumerate(names):
        r = dict(base)
        r.update({"source_locator": f"X{i}", "process_ref": ref,
                  "process_group": "조립", "관리항목": nm, "설비": "노칭 프레스"})
        e["records"].append(r)
    return e


# 상한(12)을 넘는 후보를 같은 부모 아래 세운다 — 여기서만 좁히기가 돈다.
_run72(_env75("B75SEED", [f"노칭 항목{i:02d}" for i in range(20)]))
_MT74.reset_stats()
_run72(_env75("B75AUTO", [f"노칭 항목{i:02d}변형" for i in range(6)]))
_led75 = (_LG74.read("B75AUTO") or {}).get("rows") or []
_paths75 = {r["path"] for r in _led75}
show("① 임베딩 미설정·auto에서 인입이 끝까지 돌고 겹침으로 좁힌다",
     "overlap+judge" in _paths75 and "embedding+judge" not in _paths75
     and _MT74.STATS["겹침"] >= 1,
     f"path {sorted(_paths75)} · 겹침 {_MT74.STATS['겹침']} · "
     f"임베딩 {_MT74.STATS['임베딩']}")
show("① mock의 기본은 겹침이다 (회귀 세계 불변 — sha256 벡터를 쓰지 않는다)",
     narrow.narrow_choice() == ("overlap", "mock"), str(narrow.narrow_choice()))

_seen75 = []
_e0 = _EM75.embed
_EM75.embed = lambda t: _seen75.append(t) or _e0(t)
_um75 = _MT74.gateway.use_mock
_MT74.gateway.use_mock = lambda: False          # 실호출 세계 — 좁히기는 설정이 가른다
_MT74.narrow.set_narrow("overlap")
try:
    _MT74.reset_stats()
    _cdo75 = _MT74.candidates("노칭::항목없음ZZ", "Property", "process",
                              open_graph("process"), _DIC74.open(),
                              parent="노칭", cfg=load_config("process"))
    _over75 = "돌았다"
except Exception as _x75:
    _over75 = f"{type(_x75).__name__}: {_x75}"
finally:
    _MT74.narrow.set_narrow(None)
    _MT74.gateway.use_mock = _um75
    _EM75.embed = _e0
show("① `overlap` 강제면 **실호출 모드에서도** embed()에 닿지 않는다",
     _over75 == "돌았다" and not _seen75 and _MT74.STATS["겹침"] >= 1,
     f"{_over75} · embed 호출 {len(_seen75)} · 겹침 {_MT74.STATS['겹침']}")

import os as _os75                                                # noqa: E402
_os75.environ["CANDIDATE_NARROW"] = "embed"
try:
    _cfg75 = _LL74.config()["narrow"]
    narrow.set_narrow("overlap")
    _won75 = narrow.narrow_choice()
finally:
    narrow.set_narrow(None)
    del _os75.environ["CANDIDATE_NARROW"]
show("① 플래그가 설정을 이긴다 (한 문서만 바꿔 비교한다)",
     _cfg75 == "embed" and _won75 == ("overlap", "플래그"),
     f"설정 {_cfg75} · 플래그 뒤 {_won75}")

# --diff — 다름의 기준은 판정과 node다
_a75 = {"doc_id": "A", "rows": [
    {"locator": "R1", "field": "관리항목", "surface": "가", "canonical": "노칭::가",
     "path": "overlap+judge", "verdict": "match", "node_id": "N1",
     "candidates_n": 3, "llm": {"in_tokens": 10, "out_tokens": 5}},
    {"locator": "R2", "field": "관리항목", "surface": "나", "canonical": "노칭::나",
     "path": "overlap+judge", "verdict": "new", "node_id": "N2",
     "candidates_n": 3, "llm": {"in_tokens": 10, "out_tokens": 5}}]}
_b75 = json.loads(json.dumps(_a75))
_b75["rows"][1].update(verdict="match", canonical="노칭::다", node_id="N9",
                       path="embedding+judge")
(_P.data() / "b75a.json").write_text(json.dumps(_a75, ensure_ascii=False),
                                         encoding="utf-8")
(_P.data() / "b75b.json").write_text(json.dumps(_b75, ensure_ascii=False),
                                         encoding="utf-8")
_db75 = _io.StringIO()
with _ctx.redirect_stdout(_db75):
    _SH74.cmd_report(["--diff", str(_P.data("b75a.json")),
                      str(_P.data("b75b.json"))])
_want75 = sum(1 for x, y in zip(_a75["rows"], _b75["rows"])
              if x["verdict"] != y["verdict"] or x["canonical"] != y["canonical"])
show("① `--diff`의 행 수 == 판정 또는 node가 다른 값의 수",
     f"다른 행 {_want75} / 전체 2" in _db75.getvalue(),
     _db75.getvalue().splitlines()[0][:70])
show("① 경로만 달라도 답이 같으면 다른 행이 아니다 (도구는 차이만 보인다)",
     "다른 행 1 /" in _db75.getvalue())
for _f75 in ("b75a.json", "b75b.json"):
    (_P.data() / _f75).unlink(missing_ok=True)      # 시험 재료는 남기지 않는다

print("\n── B75 ② 스코프는 하드 필터다 ──")
_g75 = open_graph("process")
_dic75 = _DIC74.open()
_cfg75b = load_config("process")
_sc75 = (_cfg75b.get("canonical_scope") or {}).get("bind_categories", [])
_cd75 = _MT74.candidates("노칭::없는항목ZZ", "Property", "process", _g75, _dic75,
                         parent="노칭", cfg=_cfg75b)
show("② 판정에 오른 후보 전부 parent가 값의 parent와 같다",
     _cd75 and all(c.get("parent") == "노칭" for c in _cd75),
     f"후보 {len(_cd75)}개 · 부모 {sorted({c.get('parent') for c in _cd75})}")
_MT74.reset_stats()
_cd75b = _MT74.candidates("새공정::없는항목ZZ", "Property", "process", _g75, _dic75,
                          parent="아무도없는공정ZZ", cfg=_cfg75b)
_v75 = _MT74.match("새공정::없는항목ZZ", _cd75b, "Property", _cfg75b)
show("② 같은 부모 아래가 0개면 후보 0 · LLM 0 · NEW (답이 정해져 있다)",
     not _cd75b and _v75["type"] == _MT74.NEW and _MT74.STATS["판정"] == 0
     and _MT74.STATS["스코프끝"] == 1,
     f"후보 {len(_cd75b)} · {_v75['type']} · 판정 {_MT74.STATS['판정']}")
_cd75c = _MT74.candidates("떠도는항목ZZ", "Property", "process", _g75, _dic75,
                          parent=None, cfg=_cfg75b)
show("② 부모 없는 값은 거르지 않는다 (모르는 것을 근거로 버리지 않는다)",
     len(_cd75c) > 0 and len({c.get("parent") for c in _cd75c}) >= 1,
     f"후보 {len(_cd75c)}개")
_non75 = _MT74.candidates("버 발생ZZ", "Failure", "quality", open_graph("quality"),
                          _dic75, parent="노칭", cfg=load_config("quality"))
show("② 스코프 없는 카테고리는 이전과 같다 (하드 필터는 스코프 카테고리의 것이다)",
     isinstance(_non75, list), f"후보 {len(_non75)}개")

print("\n── B75 ③ 비용은 실패해도 보인다 ──")
from cli import ingest as _IG75                                   # noqa: E402

_stage75 = {"이름": "판정", "값": 7, "총": 60}
_line75 = _IG75.spend_line(_stage75)
_u75 = _LL74.usage_total()
show("③ 실패 줄이 비용을 말하고 그 수가 `llm.usage_total()`과 같다",
     f"호출 {_u75['calls']:,}" in _line75
     and f"토큰 {_u75.get('total_tokens', 0):,}" in _line75
     and "판정 값 7/60" in _line75, _line75[:80])
_pb75 = _io.StringIO()
with _ctx.redirect_stdout(_pb75):
    _IG75.judge_progress(20)({"판정": 1})
    _IG75.judge_progress(20)({"판정": 2})
show("③ 진행 줄은 덮어쓰지 않는다 (스크롤·로그에 남는다)",
     "\r" not in _pb75.getvalue() and _pb75.getvalue().count("[판정]") == 2,
     repr(_pb75.getvalue()[:40]))
_ni75 = _io.StringIO()
with _ctx.redirect_stdout(_ni75):
    _IG75.judge_progress(20, every=1)({"판정": 5})
show("③ 비대화형에서는 묻지 않는다 (일괄이 첫 값에서 서지 않는다)",
     "[계속 c / 멈춤 q]" not in _ni75.getvalue())

# `q` — 그래프·사전·큐 쓰기 0
def _truth75():
    """되돌림의 대상 셋 — **그래프·사전·큐**다(체크포인트·인입 기록은 남는다)."""
    return (json.dumps([[sorted(open_graph(l).nodes), len(open_graph(l).edges)]
                        for l in ("process", "quality")], ensure_ascii=False),
            json.dumps(store.read(store.QUEUE, []), ensure_ascii=False,
                       sort_keys=True),
            json.dumps(_DIC74.open().entries(), ensure_ascii=False, sort_keys=True))


_before75 = _truth75()
from core.build.entry import Stopped as _ST75                        # noqa: E402


def _stop75(stats):
    if stats.get("판정", 0) >= 3:
        raise _ST75("사람이 멈췄다 — 판정 값 3/20 (그래프 쓰기 0)")


_MT74.PROGRESS = _stop75
try:
    _r75, _m75, _ = _run72(_env75("B75STOP", [f"멈춤항목{i:02d}" for i in range(8)]))
finally:
    _MT74.PROGRESS = None
_after75 = _truth75()
show("③ 판정 도중 멈추면 **그래프·큐 쓰기 0**이다 (부분 쓰기 없음)",
     _r75.status == "held" and _before75[:2] == _after75[:2],
     f"{_r75.status} · 그래프 {'같다' if _before75[0] == _after75[0] else '다르다'}"
     f" · 큐 {'같다' if _before75[1] == _after75[1] else '다르다'}")
show("③ 사전도 그대로다 (판정이 남긴 등재가 되돌려진다)",
     _before75[2] == _after75[2])

done()
