# -*- coding: utf-8 -*-
"""G6 ㉕ 별칭 대장 — 쌓인 별칭이 재구축에서도 처음부터 쓰인다 (B108 ①).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) × 층(process · quality):
표 B108TP(cp 어댑터 · 설비 열 = 골격 카테고리 Process · process) · B108TQ(같은 어댑터 · 설비 열 = 골격 카테고리 FailureEffect ·
quality) · 산문 B108SP(prose 엑셀 · process · 조각 개체 Process) · B108SQ(같은 통합문서 사본 · quality · 조각 개체 FailureEffect)
→ 쓰는 문서 B108UP · B108UQ(표 — 공정명 열에 그 별칭 · 설비 열에 같은 별칭 한 번 더). 판정 점수는 유사도 함수에 주입한다(LLM
판정 대역 — 변형 표기 ↔ 골격 이름 0.9) · 좌표 태깅 `pick`은 가짜 실호출(사용량에 센다 · 답은 늘 null).

잠그는 성질:
  ⓐ 대장 쓰기: 인입의 LLM 매칭(골격 대상 — 표·산문 × 층 둘) · `ops alias`(골격 · 엔티티) · 개명 · 병합이 만든 seed 밖 별칭이
     대장에 이름으로(출처) · 같은 별칭 두 번(다른 문서 · 같은 연산)이면 한 항목(횟수 · 문서) · 쓰는 손 하나(소스 대조)
  ⓑ 재구축 동치: 골격 노드에 seed 밖 별칭 → bootstrap → 그 표기를 쓰는 문서 인입 → `rebuild` ⇒ 재구축 첫 bootstrap의 스냅샷
     = 재구축 전 스냅샷(판 같음 · 층 둘) · 태깅 정확 일치 수 같음 · 태깅 호출 0 · orphan 수 같음 · canonical 기준 상태 같음 ·
     bootstrap을 인입 앞 · 뒤 어느 쪽에 돌려도 스냅샷 같음
  ⓒ 처음 채움: 대장 없는 B108 전 모양 → 첫 실행(공통 진입)이 지금 그래프에서 이름으로 채운다 · 재구축 계획(fresh 앞)도 →
     그 뒤 재구축이 ⓑ와 같다
  ⓓ 거두기: `alias-reject` 비대화형은 계획만(쓰기 0) · `--yes` → 노드 · 사전에서 빠지고 대장 「거부」 · bootstrap이 다시 싣지
     않는다(골격 대상 — 판이 바뀐다) · 재구축 뒤에도 빠져 있다(골격 · 엔티티)
  ⓔ 화면: `show aliases` 수 = 대장 수(출처별) · 재구축 끝 줄 「별칭 대장 n · 그래프에 있음 m · 없음 k」 · 골격 이름을 바꾼 seed로
     재구축하면 그 대상의 별칭이 「대상 없음」(대장에는 남는다) · 되돌리면 다시 실린다
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import re
import tempfile
from pathlib import Path

sys_path = __import__("sys").path
sys_path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done   # noqa: F401
from g6_common import DT, RFQ, _register, _run, _unregister   # noqa: E402 — 산문 엑셀 표본 · 등록 · CLI

import run as RUN                                                  # noqa: E402
from cli import ingest as IG, rebuild as RB                        # noqa: E402
from core import matcher as MT                                     # noqa: E402
from core.dictionary import Dictionary                             # noqa: E402
from core.llm import gateway, points                               # noqa: E402
from core.state import alias_book as AB, bootstrap as BS, oplog    # noqa: E402
from core.state import fixtures as FXA                             # noqa: E402 — 표본 어댑터 자리
from core.state.bootstrap import coord_layer                       # noqa: E402
from core.state.status import is_live                              # noqa: E402
from core.state.world import World                                 # noqa: E402
from openpyxl import Workbook                                      # noqa: E402
from parser import tagger as TG                                    # noqa: E402

FX = ROOT / "tests" / "fixtures"
from core.state import fixtures as _FXR                   # noqa: E402 — 픽스처 뿌리(회귀는 스위트마다 사본 — B133)
HINTS = _FXR.EXTRACT_HINTS
A = "시험자"
X = "노칭"                                           # 산문 둘의 문서 좌표
_hinted = []

# ── 판정 대역: 변형 표기 ↔ 골격 이름(표·산문 × 층 둘) — 그 쌍만 0.9(임계 이상 · 1.0 미만) · 나머지는 원래 함수
VAR = {"B108 적층 라인": "스태킹::적층", "B108 불남": "화재",            # 표 × process · 표 × quality
       "B108 타발 공정": "노칭::노칭 타발", "B108 쇼트": "단락"}        # 산문 × process · 산문 × quality
HUM_P, HUM_Q = "B108 적층 사람", "B108 화재 사람"                         # 사람 `ops alias` — 골격 대상 층 둘
_real_sim = MT._similarity


def _sim(a, b):
    return 0.9 if VAR.get(str(a)) == str(b) else _real_sim(a, b)


MT._similarity = _sim

# ── 가짜 게이트웨이 — 판정·추출은 mock 호출 수 · 좌표 태깅은 실호출 모양(사용량에 센다 · 답 null)
CALLS, PICKED = {}, []
_mock0 = gateway.mock


def _counted(point, detail=""):
    CALLS[point] = CALLS.get(point, 0) + 1
    return _mock0(point, detail)


def _fake_pick(surface, choices):
    gateway._account("coord_tag", {"usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}})
    PICKED.append(surface)
    return None


gateway.mock = _counted
points.coord_picker = lambda: _fake_pick


def _quiet(f, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(*a, **k)
    return r, buf.getvalue()


def _hint(doc_id, by_loc):
    (HINTS / f"{doc_id}.json").write_text(json.dumps(by_loc, ensure_ascii=False), encoding="utf-8")
    _hinted.append(doc_id)


def _reg_table(dt, layer, cat, cat2):
    """cp 어댑터 그대로 · 스키마는 설비 열을 골격 카테고리로(엣지 없음) — 등록 단에 세운다."""
    sch = json.loads(_P.fixture_schemas("cp.json").read_text(encoding="utf-8"))
    sch.update(doc_type=dt, layer=layer, edges=[])
    sch["fields"]["설비"] = {"role": "entity", "category": cat}
    sch["fields"]["관리항목"] = {"role": "entity", "category": cat2}
    p = _P.schemas(f"{dt}.json")
    _P.ensure(p)
    p.write_text(json.dumps(sch, ensure_ascii=False, indent=2), encoding="utf-8")
    ad = _P.adapters(f"{dt}.py")
    _P.ensure(ad)
    ad.write_text("import importlib.util as _u\n"
                  f"_s = _u.spec_from_file_location('ad_cp_{dt}', {str(FXA.ADAPTERS / 'cp.py')!r})\n"
                  "_m = _u.module_from_spec(_s)\n_s.loader.exec_module(_m)\n"
                  f"ADAPTER = {{**_m.ADAPTER, 'doc_type': {dt!r}}}\nextract = _m.extract\n", encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[dt] = {"doc_type": dt, "status": "registered", "layer": layer, "schema": f"schemas/{dt}.json",
               "adapter": str(ad), "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _xlsx(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "관리계획서"
    ws.append(["B108 시험 관리계획서"])
    ws.append(["문서번호: B108"])
    ws.append(["공정구분", "공정번호", "공정명", "극성", "설비", "관리항목", "규격", "측정방법", "대응계획", "적용모델", "개정일"])
    for r in rows:
        ws.append(list(r))
    wb.save(path)


def _snap():
    """canonical 기준 상태 — 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 큐(id는 이름으로 · 시각 뺌) + 결정."""
    w = World()
    nm = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in w.nodes()}

    def canon(x):
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items() if k not in ("created", "at", "first_seen", "last_seen")}
        if isinstance(x, list):
            return [canon(v) for v in x]
        return nm.get(x, x) if isinstance(x, str) else x
    return {"노드": sorted(f"{lay}:{n['canonical']}|{n['category']}|{n['status']}|"
                          + json.dumps(n.get("attrs") or {}, ensure_ascii=False, sort_keys=True)
                          for lay, n in w.nodes()),
            "별칭": sorted(f"{lay}:{n['canonical']}|{a['surface']}|{a.get('by')}" for lay, n in w.nodes()
                          for a in n.get("aliases") or []),
            "엣지": sorted(f"{e['rel']}|{nm.get(e['src'], e['src'])}|{nm.get(e['dst'], e['dst'])}|{e.get('status')}"
                          for g in w.graphs.values() for e in g.edges),
            "큐": sorted(json.dumps([x["kind"], x.get("doc_id"), canon(x.get("payload")),
                                    (x.get("resolution") or {}).get("decision")], ensure_ascii=False, sort_keys=True)
                        for x in store.read(store.QUEUE, []))}


def _diff(a, b):
    return {k: (sorted(set(a[k]) - set(b[k]))[:3], sorted(set(b[k]) - set(a[k]))[:3]) for k in a if a[k] != b[k]}


def _skel():
    """스냅샷(층 둘) — 노드마다 canonical · 별칭 · 판(좌표 층 `list_version`)."""
    s = store.read(store.SKELETON_LIST, {})
    return ({lay: sorted((n["canonical"], tuple(n["aliases"])) for n in v["nodes"]) for lay, v in s.items()},
            TG.list_version(TG.closed_list(coord_layer())))


def _exact(out):
    """화면의 좌표 단계 줄 「좌표 — 정확 일치 n」의 합(문서마다 한 줄)."""
    return sum(int(m.group(1).replace(",", "")) for m in re.finditer(r"좌표 — 정확 일치 ([\d,]+)", out))


def _orphans():
    """열린 `orphan_anchor`의 행 수(항목의 `rows` — 수 또는 목록)."""
    n = 0
    for x in store.read(store.QUEUE, []):
        if x.get("kind") == "orphan_anchor" and not x.get("resolution"):
            rows = (x.get("payload") or {}).get("rows")
            n += rows if isinstance(rows, int) else len(rows or [1])
    return n


def _rebuild():
    CALLS.clear()
    PICKED.clear()
    return _quiet(RB.main, ["--allow-mock", "--yes"], bootstrap=RUN.cmd_bootstrap, screen=RUN.fresh_screen)


def _end(out):
    m = re.search(r"LLM 호출 — 추출 ([\d,]+) · 판정 ([\d,]+) · 태깅 ([\d,]+)", out)
    b = re.search(r"별칭 대장 ([\d,]+) · 그래프에 있음 ([\d,]+) · 없음 ([\d,]+)", out)
    n = [int(x.replace(",", "")) for x in (m.groups() if m else ()) + (b.groups() if b else ())]
    return dict(zip(("추출", "판정", "태깅", "대장", "있음", "없음"), n))


def _live():
    return {(r["surface"], r["target"]["layer"], r["target"]["canonical"], r["source"])
            for r in AB.AliasBook.open().rows if r["status"] == AB.LIVE}


def _node(lay, canon):
    return next(n for _l, n in World().nodes() if _l == lay and n["canonical"] == canon and is_live(n))


def _data_hash():
    d = _P.home() / "data"
    return hashlib.sha256(b"".join(p.read_bytes() for p in sorted(d.rglob("*"))
                                   if p.is_file() and not p.name.endswith(".lock"))).hexdigest()


# ────────────────────────────────────────────────────────────── 바닥 — 표 · 산문 × 층 둘
print("\n■ B108 바닥 — 표 · 산문 × 층 둘 (B108TP · B108TQ · B108SP · B108SQ) → 쓰는 문서 (B108UP · B108UQ)")
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
    RUN.cmd_bootstrap([])
QDT = "b108pq"
_register("process", DT)
_register("quality", QDT)
_reg_table("b108tp", "process", "Process", "Property")
_reg_table("b108tq", "quality", "FailureEffect", "Failure")
TMP = Path(tempfile.mkdtemp(prefix="b108_"))
_xlsx(TMP / "B108TP.xlsx", [("조립", "OP-10", "노칭", "both", "B108 적층 라인", "B108 관리 가"),
                            ("조립", "OP-20", "스태킹", "both", "B108 미지 설비", "B108 관리 나")])
_xlsx(TMP / "B108TQ.xlsx", [("조립", "OP-10", "노칭", "both", "B108 불남", "B108 품질 가")])
shutil.copy(RFQ, TMP / "B108SP.xlsx")
shutil.copy(RFQ, TMP / "B108SQ.xlsx")
_hint("B108SP", {"사양_기계!R8-R17": {"entities": [{"surface": "B108 타발 공정", "category": "Process"},
                                                   {"surface": "B108 산문 속성", "category": "Property"}],
                                      "relations": []}})
_hint("B108SQ", {"사양_기계!R8-R17": {"entities": [{"surface": "B108 쇼트", "category": "FailureEffect"},
                                                   {"surface": "B108 산문 고장", "category": "Failure"}],
                                      "relations": []}})
SHEETS = "2-4:prose 5:ref *:skip"
FIRST = [("B108TP", "b108tp", None, None), ("B108TQ", "b108tq", None, None),
         ("B108SP", DT, SHEETS, X), ("B108SQ", QDT, SHEETS, X)]
OUT0 = ""
for did, dt, sh, co in FIRST:
    _r, _o = _quiet(IG.ingest_file, str(TMP / f"{did}.xlsx"), dt, ask=False, sheets=sh, coord=co)
    OUT0 += _o
    assert _r.get("status") == "성공", (did, _r)
with contextlib.redirect_stdout(io.StringIO()):
    ops.alias("process", _node("process", "스태킹::적층")["id"], HUM_P, A, "B108 표기(골격 · 표)")
    ops.alias("process", _node("process", "스태킹::적층")["id"], HUM_P, A, "B108 같은 표기 두 번")
    ops.alias("quality", _node("quality", "화재")["id"], HUM_Q, A, "B108 표기(골격 · 산문 층)")
    ops.alias("quality", _node("quality", "B108 산문 고장")["id"], "B108 산문 고장 별칭", A, "B108 표기(엔티티 · 산문)")
    ops.rename("process", _node("process", "노칭::B108 관리 가")["id"], "노칭::B108 관리 가 개명", A, "B108 개명(표)")
    _keep = _node("quality", "B108 산문 고장")["id"]
    ops.merge("quality", _node("quality", "B108 품질 가")["id"], _keep, A, override=_keep,
              reason="B108 병합(표 → 산문)")
B_ALL = AB.AliasBook.open()
print(f"  첫 인입 4문서 · 사람 연산 {len(oplog.read())}건 · 대장 {AB.counts(B_ALL)}")

# ────────────────────────────────────────────────────────────── ⓐ 대장 쓰기
print("\n■ B108 ① 별칭 대장 — 쓰는 손 하나 · 이름으로 · 같은 별칭은 한 항목")
_want = {("B108 적층 라인", "process", "스태킹::적층", "LLM 매칭"), ("B108 불남", "quality", "화재", "LLM 매칭"),
         ("B108 타발 공정", "process", "노칭::노칭 타발", "LLM 매칭"), ("B108 쇼트", "quality", "단락", "LLM 매칭"),
         (HUM_P, "process", "스태킹::적층", "사람"), (HUM_Q, "quality", "화재", "사람"),
         ("B108 산문 고장 별칭", "quality", "B108 산문 고장", "사람"),
         ("노칭::B108 관리 가", "process", "노칭::B108 관리 가 개명", "개명"),
         ("B108 품질 가", "quality", "B108 산문 고장", "병합")}
_have = _live()
_rows = {(r["surface"], r["target"]["canonical"]): r for r in B_ALL.rows}
show("ⓐ 인입의 LLM 매칭(골격 대상 — 표·산문 × 층 둘) · ops alias(골격 층 둘 · 엔티티) · 개명 · 병합이 만든 seed 밖 별칭이 "
     "대장에 이름으로(층 · canonical · 출처) · 골격 대상 표시 · LLM 매칭은 처음 문서",
     _want <= _have and all(_rows[(s, c)]["skeleton"] for s, _l, c, src in _want if src == "LLM 매칭" or s in (HUM_P, HUM_Q))
     and _rows[("B108 적층 라인", "스태킹::적층")]["first_doc"] == "B108TP",
     f"대장 {len(_have)}항목 · 기대 {len(_want)} 중 빠짐 {sorted(_want - _have)[:3] or '0'}")
for r in sorted(B_ALL.rows, key=lambda r: (r["target"]["layer"], r["source"], r["surface"])):
    print(f"      {r['surface']} → {r['target']['canonical']} ({r['target']['layer']}) · {r['source']}"
          f" · {'골격' if r['skeleton'] else '엔티티'} · 문서 {r['docs'] or '—'} · {r['count']}회")

# ── 쓰는 문서 — 그 표기를 공정명 · 설비 열에(같은 별칭 두 번째 문서)
with contextlib.redirect_stdout(io.StringIO()):
    RUN.cmd_bootstrap([])
S0, V0 = _skel()
_xlsx(TMP / "B108UP.xlsx", [("조립", "OP-20", "B108 적층 라인", "both", "B108 적층 라인", "B108 관리 다"),
                            ("조립", "OP-21", HUM_P, "both", "B108 미지 설비 둘", "B108 관리 라"),
                            ("조립", "OP-30", "B108 타발 공정", "both", "B108 미지 설비 셋", "B108 관리 마")])
_xlsx(TMP / "B108UQ.xlsx", [("조립", "OP-21", HUM_P, "both", "B108 불남", "B108 품질 나")])
PICKED.clear()
for did, dt in (("B108UP", "b108tp"), ("B108UQ", "b108tq")):
    _r, _o = _quiet(IG.ingest_file, str(TMP / f"{did}.xlsx"), dt, ask=False)
    OUT0 += _o
    assert _r.get("status") == "성공", (did, _r)
P_USE = list(PICKED)
_b2 = AB.AliasBook.open()
_e1 = _b2.get("B108 적층 라인", AB.name(_node("process", "스태킹::적층")))
_e2 = _b2.get(HUM_P, AB.name(_node("process", "스태킹::적층")))
_e3 = _b2.get("B108 불남", AB.name(_node("quality", "화재")))
show("ⓐ 같은 별칭 두 번이면 한 항목 — 다른 문서의 같은 표기(설비 열 · 사전 경로)는 문서 · 횟수만 는다(표 × 층 둘) · 같은 "
     "연산 두 번(ops alias)은 횟수만",
     sum(1 for r in _b2.rows if r["surface"] == "B108 적층 라인") == 1
     and _e1["docs"] == ["B108TP", "B108UP"] and _e1["count"] == 2 and _e1["last_doc"] == "B108UP"
     and _e3["docs"] == ["B108TQ", "B108UQ"] and _e3["count"] == 2 and _e2["count"] == 2 and not _e2["docs"],
     f"'B108 적층 라인' {_e1['docs']} {_e1['count']}회 · 'B108 불남' {_e3['docs']} {_e3['count']}회 · "
     f"'{HUM_P}' {_e2['count']}회(연산)")
_src = {}
for p in sorted((ROOT / "core").rglob("*.py")) + sorted((ROOT / "cli").rglob("*.py")) + sorted((ROOT / "parser").rglob("*.py")):
    t = p.read_text(encoding="utf-8")
    n = len(re.findall(r"aliases\"?\]?\.append\(", t)) + len(re.findall(r"aliases=\[\{", t))
    if n:
        _src[p.relative_to(ROOT).as_posix()] = n
show("ⓐ 쓰는 손 하나(소스 대조) — 노드 별칭을 붙이는 자리는 `alias_book.attach` 한 곳 + seed 손(bootstrap) 하나뿐 · "
     "인입 `Builder._register`와 연산 4곳(개명 · 이관 · 병합 · 분리)은 그 함수를 부른다",
     _src == {"core/state/alias_book.py": 1, "core/state/bootstrap.py": 1}
     and all("alias_book.attach(" in (ROOT / f).read_text(encoding="utf-8")
             for f in ("core/build/build.py", "core/state/ops.py")),
     f"붙이는 자리 {_src}")

# ────────────────────────────────────────────────────────────── ⓑ 재구축 동치
print("\n■ B108 ① 재구축 동치(별칭) — 골격 노드의 seed 밖 별칭 → bootstrap → 그 표기를 쓰는 문서 → rebuild")
with contextlib.redirect_stdout(io.StringIO()):
    RUN.cmd_bootstrap([])                              # 인입 뒤 bootstrap — 스냅샷은 인입 앞(S0)과 같아야 한다
S0b, V0b = _skel()
X0, O0, ST0 = _exact(OUT0), _orphans(), _snap()


def _equiv(tag, out):
    s1, v1 = _skel()
    e = _end(out)
    with contextlib.redirect_stdout(io.StringIO()):
        RUN.cmd_bootstrap([])                          # 재구축(인입) 뒤 bootstrap
    s2, v2 = _skel()
    d = _diff(ST0, _snap())
    ok = (s1 == S0 and v1 == V0 and s2 == s1 and _exact(out) == X0 and e.get("태깅") == 0 and not PICKED
          and _orphans() == O0 and not d)
    show(f"ⓑ {tag} ⇒ 재구축 첫 bootstrap 스냅샷 = 재구축 전(층 둘 · 판 같음) · 태깅 정확 일치 수 같음 · 태깅 호출 0 · orphan 수 같음 · "
         "canonical 기준 상태 같음 · 재구축 뒤 bootstrap도 같은 스냅샷",
         ok, f"판 {V0} → {v1} → {v2} · 정확 일치 {X0} → {_exact(out)} · 태깅 {e.get('태깅')}(가짜 실호출 {len(PICKED)}) · "
             f"orphan {O0} → {_orphans()} · 상태 {'같음' if not d else d}")
    return ok


show("ⓑ 바닥 — 쓰는 문서의 공정명이 골격 대상 별칭(LLM 매칭 · 사람)으로 정확 일치(태깅 호출 0) · bootstrap 인입 앞 = 뒤",
     not P_USE and S0b == S0 and V0b == V0 and X0 > 0,
     f"정확 일치 {X0} · 쓰는 문서 태깅 {len(P_USE)} · 판 {V0} = {V0b}")
_rc, OUT_B = _rebuild()
_equiv("rebuild", OUT_B)
for ln in OUT_B.splitlines():
    if ln.startswith("  별칭 대장") or ln.startswith("[bootstrap] process: 별칭") or ln.startswith("[bootstrap] quality: 별칭") \
            or ln.startswith("■ 재구축 끝") or ln.startswith("  LLM 호출"):
        print(f"      {ln}")

# ────────────────────────────────────────────────────────────── ⓒ 처음 채움
print("\n■ B108 ① 처음 채움 — 대장 없는 B108 전 모양 → 첫 실행 · 재구축 계획이 지금 그래프에서")
L0 = _live()
store.path(store.ALIAS_BOOK).unlink()
_oc = _run("show", "aliases")                         # 아무 명령 — 공통 진입이 채운다
L1 = _live()
show("ⓒ 첫 실행(공통 진입)이 지금 그래프의 seed 밖 별칭을 이름으로 채운다 — 표기 · 대상 · 출처가 지운 대장과 같다(처음 채움 표시)",
     L1 == L0 and all(r.get("filled") == AB.FILLED for r in AB.AliasBook.open().rows) and "[별칭 대장]" in _oc,
     f"지운 대장 {len(L0)} → 채움 {len(L1)} · 다른 것 {sorted(L0 ^ L1)[:3] or '0'}")
for ln in _oc.splitlines():
    if ln.startswith("[별칭 대장]"):
        print(f"      {ln}")
store.path(store.ALIAS_BOOK).unlink()
_pl, _po = _quiet(RB.make_plan)
_, _ps = _quiet(RB.show_plan, _pl)
_pline = next((ln.strip() for ln in _ps.splitlines() if ln.strip().startswith("별칭 대장")), "")
show("ⓒ 재구축 계획(fresh 앞)도 채운다 — 계획 줄 「별칭 대장 n(이번에 채움 m) · 골격 대상 g」",
     _live() == L0 and _pl["alias_book"]["filled"] == len(L0) and f"별칭 대장 {len(L0)}(이번에 채움 {len(L0)})" in _pline,
     f"「{_pline}」")
_rc, OUT_C = _rebuild()
_equiv("처음 채움 뒤 rebuild", OUT_C)

# ────────────────────────────────────────────────────────────── ⓓ 거두기
print("\n■ B108 ① 거두기 — ops alias-reject (골격 · 엔티티)")
_h0 = _data_hash()
_od = _run("ops", "alias-reject", "process", "스태킹::적층", HUM_P, "--actor", A)
_h1 = _data_hash()
_oy = _run("ops", "alias-reject", "process", "스태킹::적층", HUM_P, "--actor", A, "--yes")
_oe = _run("ops", "alias-reject", "quality", "B108 산문 고장", "B108 산문 고장 별칭", "--actor", A, "--yes")
_n, _nq = _node("process", "스태킹::적층"), _node("quality", "B108 산문 고장")
_r = AB.AliasBook.open().get(HUM_P, AB.name(_n))
_rec = [x for x in oplog.read() if x.get("op") == "alias:reject"]


def _gone(n, s):
    return (not any(a["surface"] == s for a in n["aliases"])) and n["id"] not in Dictionary.open().lookup(s)


with contextlib.redirect_stdout(io.StringIO()):
    RUN.cmd_bootstrap([])
S3, V3 = _skel()
show("ⓓ 비대화형은 계획만(③ 쓰기 0) · `--yes` → 노드 · 사전에서 빠지고 대장 「거부」 · 사람 판단 기록에 이름으로 · bootstrap이 "
     "다시 싣지 않는다(골격 대상 — 스냅샷에서 빠지고 판이 바뀐다) · 엔티티 대상도",
     _h0 == _h1 and "(비대화형 — 계획만" in _od and "[거둠]" in _oy and _gone(_n, HUM_P) and _gone(_nq, "B108 산문 고장 별칭")
     and _r and _r["status"] == AB.REJECTED and len(_rec) == 2 and _rec[0]["names"]["node"]["canonical"] == "스태킹::적층"
     and V3 != V0 and HUM_P not in dict(S3["process"])["스태킹::적층"] and BS.ALIAS_LOAD["process"]["rejected"] >= 1,
     f"판 {V0} → {V3} · 거부 기록 {len(_rec)} · 싣기 {BS.ALIAS_LOAD.get('process')}")
for ln in (_od + _oy).splitlines():
    if ln.strip() and not ln.startswith("[실행") and "=====" not in ln:
        print(f"      {ln}")
_rc, OUT_D = _rebuild()
_n, _nq = _node("process", "스태킹::적층"), _node("quality", "B108 산문 고장")
_rep = next((ln.strip() for ln in OUT_D.splitlines() if ln.strip().startswith("사람 판단 재생")), "")
show("ⓓ 재구축 뒤에도 빠져 있다(골격 — 대장이 bootstrap에서 막고 · 엔티티 — 판정 재생이 다시 붙이려 해도 쓰는 손이 막는다) · "
     "대장은 「거부」 그대로 · 사람 판단 재생은 이미 그 상태",
     _rc == 0 and _gone(_n, HUM_P) and _gone(_nq, "B108 산문 고장 별칭") and _skel()[1] == V3
     and AB.AliasBook.open().get(HUM_P, AB.name(_n))["status"] == AB.REJECTED,
     f"「{_rep}」")

# ────────────────────────────────────────────────────────────── ⓔ 화면
print("\n■ B108 ① 화면 — show aliases · 재구축 끝 줄 · 골격 이름을 바꾼 seed")
_os = _run("show", "aliases")
_m = re.search(r"출처별 — (.+)", _os)
_shown = dict((k, int(v.replace(",", ""))) for k, v in (x.rsplit(" ", 1) for x in _m.group(1).split(" · "))) if _m else {}
_by = {}
for r in AB.AliasBook.open().rows:
    if r["status"] == AB.LIVE:
        _by[r["source"]] = _by.get(r["source"], 0) + 1
_ed = _end(OUT_D)
show("ⓔ `show aliases` 수 = 대장 수(출처별 · 살아 있음 · 거부) · 재구축 끝 줄 「별칭 대장 n · 그래프에 있음 m · 없음 k」(n = 대장)",
     all(_shown.get(s, 0) == _by.get(s, 0) for s in AB.SOURCES)
     and f"살아 있음 {sum(_by.values())} · 거부 2" in _os and _ed.get("대장") == sum(_by.values())
     and _ed.get("있음", -1) + _ed.get("없음", -1) == _ed.get("대장"),
     f"화면 {_shown} · 대장 {_by} · 끝 줄 {_ed}")
for ln in _os.splitlines():
    if ln.strip() and not ln.startswith("[실행") and "=====" not in ln:
        print(f"      {ln}")
SK = _P.layers("process", "skeleton.json")
_SK0 = SK.read_bytes()
_sk = json.loads(_SK0.decode("utf-8"))
OLD, NEW = "적층", "B108 적층 개명"


def _rn(node):
    if isinstance(node, list):
        return [_rn(x) for x in node]
    if isinstance(node, dict):
        return {(NEW if k == OLD else k): _rn(v) for k, v in node.items()}
    return NEW if node == OLD else node


_sk["TREE"] = _rn(_sk["TREE"])
_sk["ALIASES"] = {(NEW if k == OLD else k): v for k, v in _sk["ALIASES"].items()}
SK.write_text(json.dumps(_sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
_rc, OUT_E = _rebuild()
_ee = _end(OUT_E)
_miss = [ln.strip() for ln in OUT_E.splitlines() if ln.strip().startswith("대상 없음 — 'B108 적층 라인'")]
_left = AB.AliasBook.open().get("B108 적층 라인", {"layer": "process", "category": "Process", "canonical": "스태킹::적층"})
show("ⓔ 골격 「스태킹::적층」의 이름을 바꾼 seed로 재구축 ⇒ 그 대상의 별칭은 bootstrap에서 「대상 없음」 · 끝 줄 없음 k ≥ 1(목록) · "
     "대장에는 남는다(살아 있음)",
     _rc == 0 and _miss and _ee.get("없음", 0) >= 1 and "없음 — 'B108 적층 라인'" in OUT_E
     and _left and _left["status"] == AB.LIVE,
     f"끝 줄 {_ee} · 「{_miss[0] if _miss else ''}」")
for ln in OUT_E.splitlines()[next((i for i, ln in enumerate(OUT_E.splitlines()) if ln.startswith("■ 재구축 끝")), 0):]:
    if "별칭 대장" in ln or "없음 —" in ln:
        print(f"      {ln}")
SK.write_bytes(_SK0)
_rc, OUT_F = _rebuild()
_ef, _gone_f = _end(OUT_F), AB.presence()["missing"]
show("ⓔ seed를 되돌려 다시 재구축하면 그 대상의 별칭이 다시 실린다(「대상 없음」 0 · 그래프에 있음 · 판 = 거두기 뒤 판) · 개명된 seed "
     "동안 새로 붙은 별칭(바뀐 이름 대상)은 이제 「없음」으로 대장에 남는다(지우지 않는다)",
     _rc == 0 and not [ln for ln in OUT_F.splitlines() if ln.strip().startswith("대상 없음 — 'B108 적층 라인'")]
     and any(a["surface"] == "B108 적층 라인" for a in _node("process", "스태킹::적층")["aliases"]) and _skel()[1] == V3
     and _ef.get("없음") == len(_gone_f) and all(r["target"]["canonical"].startswith("스태킹::" + NEW) for r in _gone_f),
     f"끝 줄 {_ef} · 판 {_skel()[1]} · 없음 " + (" · ".join(f"'{r['surface']}' → {r['target']['canonical']}({r['source']})"
                                                         for r in _gone_f) or "0"))

for d in _hinted:
    (HINTS / f"{d}.json").unlink(missing_ok=True)
for dt in (DT, QDT, "b108tp", "b108tq"):
    _unregister(dt)
shutil.rmtree(TMP, ignore_errors=True)
MT._similarity = _real_sim
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
done()
