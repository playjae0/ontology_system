# -*- coding: utf-8 -*-
"""G6 ㉓ 재구축 — fresh 보존 · 재구축 한 명령 · 판정 재생 · 사람 판단 재생 · 문서 단위 확인 · 문서 좌표 상위 (B106).

창작 표본(mock · 시험 주입)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50). 형태(표·산문) × 층(process ·
quality): 표 CP01(cp · process) · PFMEA01(pfmea · quality) · 산문 RFQ01(prose 엑셀 · process · 문서 좌표 노칭) ·
B106Q(같은 통합문서의 사본 · quality · 문서 좌표 노칭). 산문 개체는 mock 추출 힌트(문서 7 §7.5 대체 표 「추출」 행 —
힌트가 없는 청크는 mock 추출을 부른다)이고 하나는 소속(`belongs_to`)이 골격 밖 새 노드다. LLM 호출 수는 가짜
게이트웨이(`gateway.mock`)를 지난 수다 — mock 좌표 태깅은 정확 일치만이라 태깅 호출은 첫 인입에도 0이다(이 축은
mock에서 비어 있다).

잠그는 성질:
  ⓐ fresh 보존: 기본 fresh 뒤 넷(추출 · 지도 · 판정 대장 · 좌표 학습)과 ②등록 · ⓪원본이 바이트 그대로 · 그 밖 ③④⑤는
     빈 상태(재구축 안의 fresh와 CLI `init --fresh` 둘 다) · 화면 「남긴 것 · 지운 것 · --all」 / `--all` 뒤는 클린
     (doctor 잔재 0 · 빈 상태) / 회귀·doctor·시험의 기본 fresh 호출 0(소스 대조 — 이 시험의 대상 호출은 뺀다)
  ⓑ 재구축 동치: 인입(표·산문 × 층 둘) → 사람 연산(confirm · merge · alias · obsolete · edge 삭제 · 큐 종결 · 쌍 확인 ·
     문서 단위 확인) → `rebuild --yes` ⇒ canonical 기준 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 큐
     항목(쌍 키 — payload의 id는 이름으로) · resolution이 같다 · 재인입 LLM 호출(판정 · 추출 · 태깅) 0 · 사람 판단 기록
     수 불변 · 끝 줄의 수 = 실행 누계 = 대장 행 수 · 산문 판정과 소속 대상 판정도 재생
  ⓒ 대상 없음: 골격 노드 하나(「스태킹」)의 이름을 바꾼 seed로 재구축 ⇒ 재판정 행이 전부 그 노드 아래 · 화면 수 =
     대장의 재판정 행 수 · 그 이름을 쓰던 사람 연산은 「대상 없음」 · 기록은 남는다 / seed를 되돌려 재구축하면 그
     연산이 재생된다
  ⓓ `--no-replay` ⇒ 판정 LLM 호출 > 0 · 대장 경로에 재생 0 / 재구축 순서 = 처음 인입 순서(문서 대장의 저장 순서를
     뒤집어도) / `ops replay` 두 번 = 한 번
  ⓔ 문서 단위 확인: 계획 수 = 그 문서 실행이 만든 auto 노드 수(노드 출처의 첫 문서 · 불확실 제외) · 비대화형은
     계획만(쓰기 0) · `--yes` 뒤 전부 confirmed · 다른 문서의 auto 그대로 · 재구축 뒤에도 confirmed
  ⓕ 문서 좌표 상위(표·산문 × 층 둘 · 태깅을 지난 조각): 상위 없는 행 + 문서 좌표 X + 하위 Y가 X 밖 ⇒ 쌍 표·큐에
     「문서 좌표 'X' ↛ 하위 'Y'」 · 좌표 단계 쌍·행 수 = 구축 큐 / Y가 X 안이면 0 / 행에 상위가 있으면 그 상위로만 ·
     하위는 그대로 / `coord-ack` 같은 쌍
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
from g65_common import _P, done, overlay   # noqa: F401
from g6_common import DT, RFQ, _register, _run, _unregister   # noqa: E402 — 산문 엑셀 표본 · 등록 · CLI

import run as RUN                                                                    # noqa: E402
from cli import coord_queue as CQU, doc_coord as DC, ingest as IG, ops_review as OR  # noqa: E402
from cli import rebuild as RB                                                        # noqa: E402
from core.build import ledger as LG, replay as RP                                    # noqa: E402
from core.graph import GraphStore                                                    # noqa: E402
from core.llm import gateway                                                         # noqa: E402
from core.state import coord_acks as CA, oplog                                       # noqa: E402
from core.state.ids import norm as _norm                                             # noqa: E402
from core.state.status import is_live                                                # noqa: E402
from core.state.world import World                                                   # noqa: E402
from parser import coord_pairs as CP, tagger as TG                                   # noqa: E402

FX = ROOT / "tests" / "fixtures"
RAW = FX / "raw"
HINTS = FX / "extract_hints"
A = "시험자"
X = "노칭"                                         # 문서 좌표 — 산문 둘 · ⓕ
_hinted = []

# ── 가짜 게이트웨이 호출 수 — 지점별(판정 · 추출 · 태깅)
CALLS = {}
_mock0 = gateway.mock


def _counted(point, detail=""):
    CALLS[point] = CALLS.get(point, 0) + 1
    return _mock0(point, detail)


gateway.mock = _counted


def _quiet(f, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(*a, **k)
    return r, buf.getvalue()


def _hint(doc_id, by_loc):
    (HINTS / f"{doc_id}.json").write_text(json.dumps(by_loc, ensure_ascii=False), encoding="utf-8")
    _hinted.append(doc_id)


def _q(kind, did):
    return [x for x in store.read(store.QUEUE, []) if x["kind"] == kind and x["doc_id"] == did]


# ────────────────────────────────────────────────────────────── ⓕ
print("\n■ B106 ⑤ 문서 좌표를 상위로 — 상위 열이 없는 행 (표 · 산문 × 층 둘 · 태깅을 지난 조각)")
overlay()                                          # 품질층이 Unit을 렌즈로 쓴다(층 둘) · 클린 포함
CA.path().unlink(missing_ok=True)
#: A 상위 없음 · 하위가 X 밖 / B 상위 없음 · 하위가 X 안 / C 행에 상위(맞음) / D 행에 상위(어긋남)
FROWS = [("A", None, "적층"), ("B", None, "노칭 타발"), ("C", "스태킹", "적층"), ("D", "탭용접", "적층")]
Y = "스태킹::적층"
_fdts = []


def _ftable(lay):
    dt = f"b106t{lay[0]}"
    p = _P.schemas(f"{dt}.json")
    _P.ensure(p)
    p.write_text(json.dumps({"doc_type": dt, "schema_version": 1, "layer": lay,
                             "use_blocks": ["common_core", "process_coord"],
                             "fields": {"개체": {"role": "entity", "category": "Unit"}}, "edges": []},
                            ensure_ascii=False), encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[dt] = {"doc_type": dt, "status": "registered", "layer": lay, "schema": f"schemas/{dt}.json",
               "adapter": "-", "schema_version": 1}
    store.write(store.DOC_TYPES, dts)
    _fdts.append(dt)
    return dt


def _fenv(form, lay, did):
    """봉투 하나 — 조각은 파서와 같은 함수(`tagger.tag` · 문서 좌표도 넘긴다)를 지난다 · 조각마다 meta는 따로."""
    nodes = TG.closed_list("process")
    if form == "표":
        dt = _ftable(lay)
        base = {k: v for k, v in CPREC.items() if k not in ("설비", "관리항목", "process_group")}
        pcs = [dict(base, source_locator=f"{did}-{t}", doc_type=dt, process_ref=r, 개체=f"B106 카메라 {t}",
                    meta={}, **({"process_group": g} if g else {})) for t, g, r in FROWS]
        env = {**TABLE, "doc_id": did, "doc_type": dt,
               "records": TG.tag(pcs, nodes=nodes, doc_type=dt, doc_coord=X)}
    else:
        dt = f"ppt_{lay}"
        base = {k: v for k, v in C1.items() if k not in ("process_group", "meta")}
        pcs = [dict(base, source_locator=f"{did}-{t}", doc_type=dt, process_ref=r, meta={},
                    text=f"{t} 행 — B106 카메라 {t}를 쓴다.", **({"process_group": g} if g else {}))
               for t, g, r in FROWS]
        _hint(did, {p["source_locator"]: {"entities": [{"surface": f"B106 카메라 {p['source_locator'][-1]}",
                                                        "category": "Unit"}], "relations": [], "attach": []}
                    for p in pcs})
        env = {**PROSE, "doc_id": did, "doc_type": dt, "source_path": f"{did}.pptx",
               "chunks": TG.tag(pcs, nodes=nodes, doc_type=dt, doc_coord=X)}
    env["doc_coord"] = X
    return env


_ff, _envs, _lines = [], {}, []
for form in ("표", "산문"):
    for lay in ("process", "quality"):
        did = f"B106F{'T' if form == '표' else 'P'}{lay[0].upper()}"
        env = _envs[did] = _fenv(form, lay, did)
        pcs = {p["source_locator"][-1]: p for p in env.get("records") or env.get("chunks")}
        with contextlib.redirect_stdout(io.StringIO()):
            t, _acked = DC.pair_report(env)          # 판정 전 — 구축과 같은 함수 · 큐 0
            run_document(env)
        tab = {(CP.ack_kind(k), pr): e["rows"] for (k, pr), e in t["pairs"].items()}
        que = {}
        for x in _q("coord_mismatch", did):
            que[CP.pair_of(x["payload"])] = que.get(CP.pair_of(x["payload"]), 0) + 1
        ups = {x["payload"]["provenance"][-1]: x["payload"].get("upper") for x in _q("coord_mismatch", did)}
        led = {r.get("surface"): r.get("target") for r in (LG.read(did) or {}).get("rows") or []
               if r.get("role") == "entity"}
        _lines += [f"{form}×{lay} {ln}" for ln in CP.pair_lines(t)]
        _ff.append((form, lay, tab, que, ups, led, pcs))
show("ⓕ 상위 없는 행(태깅이 하위에서 딴 상위 · meta.group_from_ref) + 문서 좌표 X + 하위 Y가 X 밖 → 쌍 표·큐에 "
     "「문서 좌표 'X' ↛ 하위 'Y'」(payload upper) · 좌표 단계 쌍·행 수 = 구축 큐 (표·산문 × 층 둘)",
     all(tab == que and tab.get((CP.GROUP, (X, Y))) == 1 and ups.get("A") == CP.DOC_GROUP
         and (pcs["A"].get("meta") or {}).get("group_from_ref") for _f, _l, tab, que, ups, _d, pcs in _ff)
     and sum(f"문서 좌표 '{X}' ↛ 하위 '{Y}'" in ln for ln in _lines) == 4,
     " ‖ ".join(f"{f}×{l} 쌍 표 {sorted((k[1][0] + '>' + k[1][1], v) for k, v in tab.items())} = 큐 "
                f"{sorted((k[1][0] + '>' + k[1][1], v) for k, v in que.items())}"
                for f, l, tab, que, _u, _d, _p in _ff))
show("ⓕ Y가 X 안이면 0(B) · 행에 상위가 있으면 그 상위로만(C 맞음 0 · D는 「상위 '탭용접'」 쌍 하나 — 문서 좌표 대조 없음) · "
     "하위는 그대로(A의 개체가 Y 아래)",
     all(set(ups) == {"A", "D"} and ups["D"] is None and tab.get((CP.GROUP, ("탭용접", Y))) == 1 and len(tab) == 2
         and not (pcs["C"].get("meta") or {}).get("group_from_ref")
         and str(led.get("B106 카메라 A") or "").startswith(Y + "::") for _f, _l, tab, _q2, ups, led, pcs in _ff),
     " ‖ ".join(f"{f}×{l} 어긋난 행 {sorted(ups)} · A → {led.get('B106 카메라 A')}" for f, l, _t, _q2, ups, led, _p in _ff))
for ln in _lines:
    print(f"      {ln}")
_qv = _quiet(CQU.show)[1]
_ack = _run("ops", "coord-ack", "all", X, Y, "--actor", A, "--reason", "B106 쌍 확인")
_after = [x for d in _envs for x in _q("coord_mismatch", d) if x["payload"].get("upper") == CP.DOC_GROUP]
_t2, _acked2 = DC.pair_report(_envs["B106FTP"])
show("ⓕ 큐 화면이 「문서 좌표 'X' ↛ 하위 'Y'」로 묶고 · `ops coord-ack all X Y`(상위 쌍과 같은 열쇠)가 그 쌍을 닫는다 · "
     "좌표 단계 쌍 표도 확인됨",
     f"문서 좌표 '{X}' ↛ 하위 '{Y}'" in _qv and "큐 4행" in _ack and len(_after) == 4
     and all((x.get("resolution") or {}).get("decision") == CA.DECISION for x in _after)
     and (CP.DOC_GROUP, (X, Y)) in _acked2,
     next((ln.strip() for ln in _ack.splitlines() if ln.startswith("[확인]")), _ack.strip()[:160]))
for ln in _qv.splitlines():
    if X in ln and Y in ln:
        print(f"      {ln.strip()}")
for _dt in _fdts:
    dts = store.read(store.DOC_TYPES, {})
    dts.pop(_dt, None)
    store.write(store.DOC_TYPES, dts)
    _P.schemas(f"{_dt}.json").unlink(missing_ok=True)
CA.path().unlink(missing_ok=True)


# ────────────────────────────────────────────────────────────── 재구축 바닥 — 표 · 산문 × 층 둘
def _snap():
    """canonical 기준 상태 — 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 큐(kind · 문서 · payload — id는
    이름으로 · 시각은 뺀다) + resolution 결정."""
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
    """다른 칸만 — `{칸: (앞에만 3, 뒤에만 3)}`."""
    return {k: (sorted(set(a[k]) - set(b[k]))[:3], sorted(set(b[k]) - set(a[k]))[:3]) for k in a if a[k] != b[k]}


def _sizes(s):
    return " · ".join(f"{k} {len(v)}" for k, v in s.items())


def _tree():
    """상태 루트의 파일 → 바이트 해시(락 제외)."""
    home = _P.home()
    return {p.relative_to(home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(home.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}


def _rel(p):
    return Path(p).resolve().relative_to(_P.home().resolve()).as_posix()


KEPT = [_rel(p) for _l, p in init.kept()]
EMPTY = {_rel(store.path(n)): v for n, v in init.EMPTY.items()}


def _under(f, roots):
    return any(f == r or f.startswith(r + "/") for r in roots)


def _empty_now():
    """지금 ③이 빈 상태인가 — §7.2 빈 파일 형태 그대로 · 층 그래프는 전부 노드 0 · 엣지 0(`init.ensure`가 만든다)."""
    return (all(store.read(n, None) == v for n, v in init.EMPTY.items())
            and all(not g.nodes and not g.edges for g in World().graphs.values()))


def _empty_file(f):
    """빈 상태가 만드는 파일 — §7.2 빈 파일 · 층 그래프 파일(이름은 `GraphStore`가 안다) · 그 명령 자신의 로그."""
    return (f in EMPTY or (f.startswith("data/") and f.endswith("/" + GraphStore.FILENAME))
            or f.startswith("work/logs/init_"))


def _fresh_ok(before, after, empty, extra=()):
    """기본 fresh 판정 — `(맞음, 설명)`: ③④⑤ 밖과 남길 넷(+`extra`)은 바이트 그대로 · 그 밖 ③④⑤는 빈 상태뿐
    (`empty`는 fresh 직후에 잰 `_empty_now()`)."""
    wipe = ("data", "work", "export")
    hold = KEPT + list(extra)
    moved = [f for f, h in before.items() if (not _under(f, wipe) or _under(f, hold)) and after.get(f) != h]
    left = [f for f in after if _under(f, wipe) and not _under(f, hold) and not _empty_file(f)]
    kept = {r: sum(1 for f in before if _under(f, [r])) for r in KEPT}
    return (not moved and not left and empty and all(kept.values()),
            f"남긴 넷 {kept} · 바뀐 것 {moved[:3]} · 남은 ③④⑤ {left[:3]} · 빈 상태 {empty}")


def _ledger_rows(dids):
    return [dict(r, _doc=d) for d in dids for r in (LG.read(d) or {}).get("rows") or []]


def _end_numbers(out):
    """끝 줄 「판정 — 재생 n · 재판정 m(키 없음 a · 대상 없음 b · 끔 c)」의 수."""
    m = re.search(r"판정 — 재생 ([\d,]+) · 재판정 ([\d,]+)\(키 없음 ([\d,]+) · 대상 없음 ([\d,]+) · 끔 ([\d,]+)\)", out)
    keys = ("재생", "재판정", "키 없음", "대상 없음", "끔")
    return dict(zip(keys, (int(x.replace(",", "")) for x in m.groups()))) if m else {}


def _screen(out):
    """재구축 화면 — 계획 · fresh · 문서마다 판정 재생 줄 · 끝 보고(문서마다의 인입 화면은 뺀다)."""
    lines = out.splitlines()
    i0 = next((i for i, ln in enumerate(lines) if ln.startswith("■ 재구축 계획")), 0)
    i1 = next((i for i, ln in enumerate(lines) if ln.startswith("[재구축 fresh]")), i0)
    i2 = next((i for i, ln in enumerate(lines) if ln.startswith("■ 재구축 끝")), len(lines))
    return (lines[i0:i1] + [ln for ln in lines if ln.startswith("[재구축 fresh]")]
            + [ln for ln in lines[i1:i2] if "판정 재생 —" in ln] + lines[i2:])


def _rebuild(*flags, screen=None):
    CALLS.clear()
    rc, out = _quiet(RB.main, ["--allow-mock", "--yes", *flags], bootstrap=RUN.cmd_bootstrap,
                     screen=screen or RUN.fresh_screen)
    return rc, out, dict(CALLS)


print("\n■ B106 재구축 — 표 · 산문 × 층 둘 (CP01 · RFQ01 · PFMEA01 · B106Q)")
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)                 # 클린 — ⓕ의 덧칠도 걷힌다(mock 루트 seed 다시)
    RUN.cmd_bootstrap([])
QDT = "b106pq"
_register("process", DT)
_register("quality", QDT)
TMP = Path(tempfile.mkdtemp(prefix="b106_"))          # 클린(init --fresh)이 지우지 않는 자리
QX = TMP / "B106Q.xlsx"
shutil.copy(RFQ, QX)
_hint("RFQ01", {
    "사양_기계!R2-R6": {"entities": [{"surface": "이송 속도", "category": "Property",
                                     "belongs_to": {"name": "이송 장치", "category": "Unit", "from": "본문"}}],
                       "relations": []},
    "사양_기계!R8-R17": {"entities": [{"surface": "노칭 프레스기", "category": "Unit"},
                                      {"surface": "가압력", "category": "Property"},
                                      {"surface": "금형 클리어런스", "category": "Property"}],
                        "relations": [{"src": "노칭 프레스기", "rel": "has_property", "dst": "가압력"}]},
    "사양_기계!R19-R23": {"entities": [{"surface": "노칭 정밀도", "category": "Property"},
                                       {"surface": "버 높이", "category": "Property"}], "relations": []},
    "요구사항!R2-R3": {"entities": [{"surface": "적층 정렬도", "category": "Property"}], "relations": []}})
_hint("B106Q", {
    "사양_기계!R8-R17": {"entities": [{"surface": "가압력 부족", "category": "Failure"},
                                      {"surface": "금형 클리어런스 과다", "category": "Failure"}],
                        "relations": [{"src": "금형 클리어런스 과다", "rel": "causes", "dst": "가압력 부족"}]},
    "사양_기계!R19-R23": {"entities": [{"surface": "버 발생량 과다", "category": "Failure"}], "relations": []},
    "사양_전장!R5-R6": {"entities": [{"surface": "전원 차단 실패", "category": "Failure"}], "relations": []}})
SHEETS = "2-4:prose 5:ref *:skip"
DOCS = [("CP01", RAW / "CP01.xlsx", "cp", None, None), ("RFQ01", RFQ, DT, SHEETS, X),
        ("PFMEA01", RAW / "PFMEA01.xlsx", "pfmea", None, None), ("B106Q", QX, QDT, SHEETS, X)]
DIDS = [d[0] for d in DOCS]
CALLS.clear()
_first = {}
for did, f, dt, sh, co in DOCS:
    _r, _o = _quiet(IG.ingest_file, str(f), dt, ask=False, sheets=sh, coord=co)
    _first[did] = _r.get("status")
C_FIRST = dict(CALLS)
print(f"  첫 인입 — {_first} · 가짜 게이트웨이 호출 {C_FIRST}")

# ── 사람 연산 — 표·산문 × 층 둘에서 하나 이상씩
_w = World()
_by = {(lay, n["canonical"]): n["id"] for lay, n in _w.nodes() if is_live(n)}


def _id(lay, canon):
    return _by[(lay, canon)]


def _live_edge(src, rel=None, dst=None):
    return next((e for g in World().graphs.values() for e in g.edges if e["src"] == src
                 and e.get("status") != "deleted_by_user" and rel in (None, e["rel"]) and dst in (None, e["dst"])), None)


with contextlib.redirect_stdout(io.StringIO()):
    ops.confirm("process", _id("process", "노칭::노칭 프레스"), A, "B106 확인")
    ops.merge("process", _id("process", "노칭::cathode::금형 클리어런스"), _id("process", "노칭::금형 클리어런스"), A,
              reason="B106 합침(표)")
    ops.merge("process", _id("process", "노칭::버 높이"), _id("process", "노칭::anode::버 높이"), A,
              reason="B106 합침(산문 → 표)")
    ops.alias("process", _id("process", "노칭::노칭 정밀도"), "노칭 정확도", A, "B106 표기(표)")
    ops.alias("quality", _id("quality", "전원 차단 실패"), "전원 차단 불량", A, "B106 표기(산문)")
    ops.obsolete("process", _id("process", "스태킹::스태커"), A, reason="B106 폐기")
    _e1 = _live_edge(_id("process", "패키징::사이드 실링::실러"))
    ops.delete_edge("process", _e1["src"], _e1["rel"], _e1["dst"], A, "B106 엣지 삭제(표)")
    _e2 = _live_edge(_id("process", "노칭::이송 장치"), "has_property", _id("process", "노칭::이송 속도"))   # 산문 소속 엣지
    ops.delete_edge("process", _e2["src"], _e2["rel"], _e2["dst"], A, "B106 엣지 삭제(산문 소속)")
    _ur = next(r for r in OR.items("all") if r["surface"] == "버 발생량 과다")
    _dec = OR.decide(_ur, "m", A)                         # 큐 종결 — ops review 합침(queue:resolve 기록)
    CA.ack(CP.GROUP, ("스태킹", "노칭"), A, "B106 쌍 확인")
_unc = next((r for r in OR.items("all") if r["doc_id"] == "RFQ01"), None)


# ── ⓔ 문서 단위 확인 — 계획 · 비대화형 쓰기 0 · --yes
def _made_by_doc(did):
    """그 문서 실행이 만든 auto 노드(독립 경로 — 노드 출처의 첫 문서 · 열린 불확실 항목의 노드는 뺀다)."""
    unc = {(x.get("payload") or {}).get("node_id") for x in _q("uncertain_match", did) if not x.get("resolution")}
    return sorted(n["canonical"] for _l, n in World().nodes() if is_live(n) and n.get("status") == "auto"
                  and str((n.get("provenance") or [""])[0]).startswith(f"{did}#") and n["id"] not in unc)


def _state_hash():
    t = _tree()
    return hashlib.sha256(json.dumps({f: h for f, h in t.items() if _under(f, ("data", "registry"))},
                                     sort_keys=True).encode("utf-8")).hexdigest()


_mine, _cp_auto = _made_by_doc("RFQ01"), _made_by_doc("CP01")
_h0 = _state_hash()
_plan = _run("ops", "confirm", "all", "--doc", "RFQ01", "--actor", A)
_h1 = _state_hash()
_n_plan = int((re.search(r"auto 노드 ([\d,]+)\(", _plan) or [0, "-1"])[1].replace(",", ""))
show("ⓔ 문서 단위 확인 계획 — 수 = 그 문서 실행이 만든 auto 노드 수(출처의 첫 문서 · 불확실 제외 — 다음 줄은 ops review) · "
     "비대화형은 계획만(③·② 쓰기 0)",
     _n_plan == len(_mine) > 0 and _h0 == _h1 and "(비대화형 — 계획만 · 쓰기 0)" in _plan
     and "ops review" in _plan and _unc is not None,
     f"계획 {_n_plan} = 독립 계수 {len(_mine)} {_mine} · 불확실 '{(_unc or {}).get('canonical')}' 제외 · 쓰기 "
     f"{'0' if _h0 == _h1 else '있음'}")
for ln in _plan.splitlines():
    if ln.strip() and not ln.startswith("[실행"):
        print(f"      {ln}")
_yes = _run("ops", "confirm", "all", "--doc", "RFQ01", "--actor", A, "--yes")
_st = {n["canonical"]: n["status"] for _l, n in World().nodes()}
show("ⓔ --yes 뒤 그 노드 전부 confirmed · 다른 문서(CP01)의 auto는 그대로",
     all(_st.get(c) == "confirmed" for c in _mine) and _made_by_doc("CP01") == _cp_auto and _made_by_doc("RFQ01") == [],
     next((ln.strip() for ln in _yes.splitlines() if ln.startswith("[확정]")), _yes.strip()[:160])
     + f" · CP01 auto {len(_cp_auto)} 그대로")

# ── ⓑ 재구축 동치 — 남길 넷이 비지 않게 탐침(지도 · 좌표 학습 — mock 실행은 만들지 않는다)
_probe_map = _P.work("struct_maps", "_B106_PROBE.json")
_P.ensure(_probe_map)
_probe_map.write_text('{"doc_id": "_B106_PROBE", "maps": {}}\n', encoding="utf-8")
_book = store.read(store.COORD_LEARNED, {}) or {}
_book.setdefault("채택", {})["B106 탐침 표기"] = {"canonical": X, "layer": "process", "doc_id": "_B106_PROBE",
                                               "hits": 0, "출처": "시험 탐침"}
_book.setdefault("목록밖", {})
store.write(store.COORD_LEARNED, _book)
S1, N_OPS = _snap(), len(oplog.read())
_T0, _PROBE = _tree(), {}


def _probe(rep, all_, head):
    _PROBE["tree"], _PROBE["empty"] = _tree(), _empty_now()       # fresh 직후 · bootstrap 전
    RUN.fresh_screen(rep, all_, head)


_rc, OUT_B, C_B = _rebuild(screen=_probe)
S2, _J = _snap(), dict(RP.STATS)
_d = _diff(S1, S2)
show("ⓑ 재구축 동치 — canonical 기준 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 큐 항목(쌍 키)과 "
     "resolution이 재구축 전과 같다 (표·산문 × 층 둘 · 사람 연산 10가지 뒤)",
     _rc == 0 and not _d, f"{_sizes(S1)}" + (f" · 다른 것 {_d}" if _d else " · 같음"))
_rows_b = _ledger_rows(DIDS)
_nb = _end_numbers(OUT_B)
show("ⓑ 재인입 LLM 호출 0(판정 · 추출 · 태깅 — 첫 인입은 판정·추출 > 0) · 사람 판단 기록 수 불변 · 끝 줄의 수 = 실행 누계 = "
     "대장 행 수(재생 = 경로 replay 행 · 재판정 = 사유가 적힌 행)",
     C_B.get("judge", 0) == C_B.get("extract", 0) == C_B.get("coord_tag", 0) == 0
     and C_FIRST.get("judge", 0) > 0 and C_FIRST.get("extract", 0) > 0 and len(oplog.read()) == N_OPS
     and _nb == {k: _J[k] for k in _nb} and _nb.get("재생") == sum(r.get("path") == "replay" for r in _rows_b)
     and _nb.get("재판정") == sum(bool(r.get("replay")) for r in _rows_b),
     f"첫 인입 {C_FIRST} → 재구축 {C_B or '{}'} · 기록 {N_OPS} → {len(oplog.read())} · 끝 줄 {_nb}")
_pr = [r for r in _rows_b if r["_doc"] in ("RFQ01", "B106Q") and r.get("path") == "replay"]
show("ⓑ 산문 판정도 재생(층 둘) · 소속 대상 판정(대장 역할 belongs)도 재생 · 별칭 출처는 그때 경로대로",
     {r["_doc"] for r in _pr} == {"RFQ01", "B106Q"} and any(r.get("role") == "belongs" for r in _pr),
     f"산문 재생 {len(_pr)}행 — " + " · ".join(f"{r['_doc']} {r['surface']}({r.get('role')} · {r.get('verdict')})"
                                             for r in _pr[:8]))
_fresh, _why = _fresh_ok(_T0, _PROBE.get("tree") or {}, _PROBE.get("empty"), extra=[_rel(RB.plan_path())])
show("ⓐ 재구축 안의 기본 fresh — 넷(추출 · 지도 · 판정 대장 · 좌표 학습)과 ②등록 · ⓪원본은 바이트 그대로 · 그 밖 ③④⑤는 빈 상태",
     _fresh, _why)
_st2 = {n["canonical"]: n["status"] for _l, n in World().nodes() if is_live(n)}
show("ⓔ 재구축 뒤에도 문서 단위 확인이 confirmed(사람 판단 기록의 이름으로 되살렸다)",
     all(_st2.get(c) == "confirmed" for c in _mine), f"{len(_mine)}개 — " + " · ".join(_mine))
print("  ── 재구축 화면(계획 · fresh · 문서마다 판정 재생 · 끝 보고 — 잘리지 않은 줄)")
for ln in _screen(OUT_B):
    print(f"      {ln}")

# ── ⓓ 순서 — 재구축이 넣은 순서(화면 계획 · 새 문서 대장)
_order = [m.group(1) for m in re.finditer(r"^\s+\d+\. (\S+)", OUT_B, re.M)]
_reg2 = list(store.read(store.DOC_REGISTRY, {}))

# ── ⓒ 대상 없음 — 골격 노드 하나의 이름을 바꾼 seed
SK = _P.layers("process", "skeleton.json")
_SK0 = SK.read_bytes()
OLD, NEW = "스태킹", "스태킹 공정"


def _rename(node):
    if isinstance(node, list):
        return [_rename(x) for x in node]
    if isinstance(node, dict):
        return {(NEW if k == OLD else k): _rename(v) for k, v in node.items()}
    return node


_sk = json.loads(_SK0.decode("utf-8"))
_sk["TREE"] = _rename(_sk["TREE"])
_sk["ALIASES"] = {(NEW if k == OLD else (NEW + k[len(OLD):] if k.startswith(OLD + "::") else k)): v
                  for k, v in _sk["ALIASES"].items()}
_sk["ALIASES"][NEW] = list(_sk["ALIASES"].get(NEW) or []) + [OLD]      # 옛 이름은 별칭 — 행은 새 이름 노드로 간다
SK.write_text(json.dumps(_sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
_rc, OUT_C, C_C = _rebuild()
_rows_c = _ledger_rows(DIDS)
_rj = [r for r in _rows_c if r.get("replay")]
_nc = _end_numbers(OUT_C)


def _below(r):
    return any(str(r.get(k) or "").startswith(NEW + "::") for k in ("canonical", "target"))


_miss = [ln for ln in OUT_C.splitlines() if "대상 없음" in ln and "스태킹::스태커" in ln]
show("ⓒ 골격 「스태킹」→「스태킹 공정」(seed) 재구축 — 재판정 행이 전부 그 노드 아래 · 화면 수 = 대장의 재판정 행 수 · "
     "그 이름을 쓰던 사람 연산(폐기 '스태킹::스태커')은 「대상 없음」 · 기록은 그대로",
     _rc == 0 and _rj and all(_below(r) for r in _rj) and _nc.get("재판정") == len(_rj) == _nc.get("대상 없음")
     + _nc.get("키 없음") and _miss and len(oplog.read()) == N_OPS
     and any((x.get("names") or {}).get("node", {}).get("canonical") == "스태킹::스태커" for x in oplog.read()),
     f"재판정 {len(_rj)}행(대상 없음 {_nc.get('대상 없음')} · 키 없음 {_nc.get('키 없음')}) — 예 "
     + " · ".join(f"{r['surface']} → {r.get('canonical')}" for r in _rj[:4]) + f" · LLM {C_C or '{}'} · 「{_miss[0].strip() if _miss else ''}」")
print("  ── ⓒ 재구축 끝 보고")
for ln in OUT_C.splitlines()[next((i for i, ln in enumerate(OUT_C.splitlines()) if ln.startswith("■ 재구축 끝")), 0):]:
    print(f"      {ln}")
SK.write_bytes(_SK0)
_rc, OUT_C2, _c = _rebuild()
_n3 = next((n for _l, n in World().nodes() if n["canonical"] == "스태킹::스태커"), {})
S3 = _snap()
show("ⓒ seed를 되돌려 다시 재구축하면 그 연산이 재생된다(폐기 · 「대상 없음」 0) · 상태가 첫 재구축 전과 같다",
     _rc == 0 and _n3.get("status") == "obsolete" and not [ln for ln in OUT_C2.splitlines() if "대상 없음 —" in ln]
     and not _diff(S1, S3),
     f"'스태킹::스태커' {_n3.get('status')} · 다른 것 {_diff(S1, S3) or '없음'}")

# ── ⓓ --no-replay · 순서(가장 최근에 다시 넣은 문서도 처음 자리) · ops replay 멱등
_r, _o = _quiet(IG.ingest_file, str(RFQ), DT, ask=False, sheets=SHEETS)      # 재인입 — 문서 좌표는 기록대로
_reg3 = list(store.read(store.DOC_REGISTRY, {}))
_rc, OUT_D, C_D = _rebuild("--no-replay")
_rows_d = _ledger_rows(DIDS)
_order_d = [m.group(1) for m in re.finditer(r"^\s+\d+\. (\S+)", OUT_D, re.M)]
show("ⓓ --no-replay ⇒ 판정이 LLM으로(호출 > 0) · 대장 경로에 재생 0 · 끝 줄 「끔」 / 재구축 순서 = 처음 인입 순서(화면 계획 · "
     "새 문서 대장 · RFQ01을 마지막에 다시 넣어도 그 자리)",
     _rc == 0 and _r.get("status") == "성공" and C_D.get("judge", 0) > 0
     and not any(r.get("path") == "replay" for r in _rows_d) and RP.STATS["끔"] > 0 and RP.STATS["재생"] == 0
     and DIDS == _order == _reg2 == _reg3 == _order_d == list(store.read(store.DOC_REGISTRY, {})),
     f"LLM {C_D} · 끔 {RP.STATS['끔']} · 처음 인입 {DIDS} · 계획 {_order} → {_order_d} · 대장 {_reg2}")
S4, _n4 = _snap(), len(oplog.read())
_again = oplog.replay()
show("ⓓ `ops replay` 두 번 = 한 번(재구축이 한 번 돌린 뒤 · 할 것 0 · 상태 · 기록 수 그대로)",
     not _again["done"] and not _diff(S4, _snap()) and len(oplog.read()) == _n4,
     " · ".join(f"{k} {len(v)}" for k, v in _again.items()))

# ── ⓐ CLI — 기본 fresh(보존) · --all(클린) · 기본 호출 0
_T1 = _tree()
_o1 = _run("init", "--fresh")
_ok1, _why1 = _fresh_ok(_T1, _tree(), _empty_now())
show("ⓐ `init --fresh`(기본) — 넷과 ②등록 · ⓪원본은 바이트 그대로 · 그 밖 ③④⑤는 빈 상태 · 화면 「남긴 것 · 지운 것 · --all」",
     _ok1 and "남긴 것 —" in _o1 and "지운 것 —" in _o1 and "전부 지우려면 --all" in _o1, _why1)
for ln in _o1.splitlines():
    if ln.startswith("[init"):
        print(f"      {ln}")
_o2 = _run("init", "--fresh", "--all")
_T2 = _tree()
_left2 = [f for f in _T2 if _under(f, ("data", "work", "export")) and not _empty_file(f)]
_res = [d.name for d in (_P.parsed(), _P.extract()) if d.exists() and any(d.iterdir())]
show("ⓐ `init --fresh --all` — 클린(doctor 잔재 0 · ③④⑤는 빈 상태뿐 · 사람 판단 기록 0)",
     not _left2 and not _res and _empty_now() and not oplog.read() and "(전부 — 클린)" in _o2,
     f"잔재 {_res or 0} · 남은 ③④⑤ {_left2[:3] or 0} · 기록 {len(oplog.read())}")
_pat = re.compile(r'init\(fresh_=True(?![^)]*all_=True)|"init", "--fresh"(?!, "--all")|init\.fresh\((?![^)]*all_=True)')
_files, _left = [], []
for _p in sorted((ROOT / "tests").rglob("*.py")) + [ROOT / "doctor.py"]:
    if _p.resolve() == Path(__file__).resolve():
        continue                                      # 이 시험의 기본 fresh는 시험 대상이다(클린 호출이 아니다)
    _src = _p.read_text(encoding="utf-8")
    if re.search(r'fresh_=True|"--fresh"|init\.fresh\(', _src):
        _files.append(_p.name)
    _left += [f"{_p.name}:{i}" for i, ln in enumerate(_src.splitlines(), 1)
              if _pat.search(ln) and not ln.lstrip().startswith("#")]          # 주석의 언급은 호출이 아니다
show("ⓐ 회귀 · doctor · 시험의 클린 호출은 전부 --all — 기본 fresh 호출 0(소스 대조)",
     not _left and _files, f"클린을 부르는 파일 {len(_files)} · 기본 호출 {_left or 0}")

# ── 뒷정리 — 시험이 세운 것은 시험이 치운다
for _d in _hinted:
    (HINTS / f"{_d}.json").unlink(missing_ok=True)
_unregister(DT)
_unregister(QDT)
CA.path().unlink(missing_ok=True)
SK.write_bytes(_SK0)
shutil.rmtree(TMP, ignore_errors=True)
with contextlib.redirect_stdout(io.StringIO()):
    init.init(fresh_=True, all_=True)
done()
