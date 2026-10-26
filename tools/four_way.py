# -*- coding: utf-8 -*-
"""네 벌 대조 — 기준 커밋과 지금 작업 트리의 **mock 첫 인입 산출**을 벌마다 비교한다 (D-190).

    python tools/four_way.py --base <커밋>                 기준 vs 지금 — 다른 것의 수와 앞 견본
    python tools/four_way.py --base <커밋> --keep <폴더>    덤프 둘(base.json · now.json)을 남긴다

회차 요청문 마감 줄의 「네 벌 diff」를 회차마다 손으로 다시 짜던 것을 한 자리로 모았다.

**네 벌** = 그래프(층마다 노드 · 엣지) · 사전 · 큐 · 판정 대장(`work/ingest_log/`) — 덧붙여 ③진실
`data/`의 파일 목록(새 파일이 생기면 여기 뜬다). 시각·횟수 키는 빼고, 의미 축 id는 그 노드의
`층:canonical`로 바꿔 대조한다(ULID는 실행마다 다르다).

**네 바닥** — 같은 표본을 같은 순서로 넣는다:
  A: `init --fresh --all` → bootstrap → 표 표본 다섯(`TABLE`)을 하나씩 `ingest_file`(비대화형 —
     선택이 안 되는 표본은 「미선택」 그대로가 대조 대상이다)
  B: 회귀 바닥 `tests/g65_common.fresh()`(CP01 · PFMEA01 · PPT01~03 · QPPT01 + finalize)
  C: **산문 엑셀**(B117 ④ — 창작 `PROSE` 둘: 시트 › 제목 사슬 · 제목에 유닛 이름 · 빈칸 표시 · 다른 공정 이름 · 문서 좌표 하나 ·
     좌표가 서지 않는 문서 하나) — 이 스크립트가 사본 안에서 엑셀 · mock 힌트(개요 `<doc>@outline.json` · 추출)를 만들고 연결
     보강 선별 규칙(`reinforce.SELECT` — 첫 후보)을 주입해 `ingest_file`(마무리 포함)로 넣는다. 기준 커밋에 표본이 없어도 된다
     (재료가 이 파일에 있다). B113~B116 몫(다른 공정 가드 · 빈칸 · 재연결 · 개요 · 제목 개체 · 폴백 사슬 · 연결 보강)이 대조에 보인다.
  D: **사내 꼴 표**(B147 ⑤ — 창작 `CPU_ROWS`): 유닛 열 없는 CP — 상위 좌표 = 공정 · 하위 좌표 = 골격의 자식 단(사내의 유닛 단과
     같은 자리) · 관리항목 entity · 규격 · 측정방법 attribute → 관리항목 · 대응계획 content → 관리항목 · 엣지 `@process_ref
     has_property 관리항목`. 스키마 · 어댑터를 등록 단에 직접 두고(등록 LLM 0) 엑셀을 만들어 `ingest_file`(마무리 포함 · 보강
     선별 규칙 주입)로 넣는다 — 기준 커밋에 표본이 없어도 된다(재료가 이 파일에 있다).

**자리를 가른다**: 기준은 `git archive`로, 지금은 작업 트리(커밋 안 한 변경 포함 · 무시 파일 제외)를
임시 폴더에 복사하고, 사본마다 **자기 `state_mock/`**에서 돈다 — 레포의 `state_mock/`은 건드리지
않는다. `ONTO_MOCK_HOME`은 쓰지 않는다 — 그 문은 `init --fresh`가 층 자산을 seed로 덮지 않게
바꾼다(`core/paths.py` 머리말). 덤프는 **이 파일 하나**를 두 사본에 넣어 돌린다(같은 스크립트 —
기준 커밋에 이 파일이 없어도 된다). 두 사본은 동시에 돈다. 임시 폴더는 `TMPDIR` 아래에
만들고 끝나면 지운다.

종료 코드: 0 = 전부 같다 · 1 = 다른 것이 있다(기대한 변화인지는 보고가 말한다) · 2 = 못 돌았다.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 실행마다 달라지는 키 — 대조에서 뺀다.
TS = ("created", "at", "first_seen", "last_seen", "last_tried", "last_fp", "attempts", "obsoleted_at",
      "confirmed_at", "parsed_at", "first_ingested_at", "ingested_at", "updated_at", "last_hit")
#: 바닥 A의 표 표본 — 넣는 순서 그대로.
TABLE = ("CP01.xlsx", "CP02_drift.xlsx", "PFMEA01.xlsx", "IPQC01.xlsx", "CSV01.csv")
#: 바닥 C의 산문 표본(창작 — 근거가 아니다) — `{doc_id: (문서 좌표, {시트: [행 …]})}`
PROSE = {
    "FWC1": ("노칭", {"추출 사양": ["1. 개요", "센서가 셀 위치를 본다.", "2. 추출부", "추출부는 셀을 꺼낸다.",
                                  "2.1 NG unit", "모터 회전수는 3000rpm이다.", "실린더 행정은 50mm다.",
                                  "2.2 스태킹 연계", "스태킹 공정과 맞물린다.", "3. 이송부", "벨트 장력은 2kN이다."],
                     "부록": ["1. 비고", "N/A"]}),
    "FWC2": (None, {"이송 사양": ["1. 이송부", "벨트 장력은 3kN이다.", "2. 점검", "센서 점검 주기는 1주다."]}),
    # B119 ⑥ ⓑ — 번호 없는 유닛 줄 + 유닛마다 되풀이되는 번호 소제목(TW 꼴 · 창작) — 고정 규칙은 소제목만 세운다
    "FWC3": ("노칭", {"TW 사양": ["언와인더 unit", "1) 기본사양", "속도는 100ppm이다.", "하중은 5kN이다.",
                                 "2) 지정사양", "장력은 30N이다.", "리와인더 unit", "1) 기본사양", "속도는 80ppm이다.",
                                 "2) 지정사양", "장력은 20N이다."]}),
}
#: 문서 구조 mock 힌트(B119 ① — 지금 사본만 읽는다 · 기준 사본에는 구조 단계가 없다) — `{doc_id: {시트: [{text, depth, role, …}]}}`
PROSE_STRUCTURE = {"FWC3": {"TW 사양": [
    {"text": "언와인더 unit", "depth": 1, "role": "대상", "name": "언와인더 unit", "category": "Unit"},
    {"text": "1) 기본사양", "depth": 2, "role": "묶음"}, {"text": "2) 지정사양", "depth": 2, "role": "묶음"},
    {"text": "리와인더 unit", "depth": 1, "role": "대상", "name": "리와인더 unit", "category": "Unit"},
    {"text": "1) 기본사양", "depth": 2, "role": "묶음"}, {"text": "2) 지정사양", "depth": 2, "role": "묶음"}]}}
#: 목차 노드화 mock 힌트 — 제목 글자 → 대상(카테고리의 출처 — B148 ② · 메타가 대상으로 정한 제목은 카테고리만 쓴다)
PROSE_OUTLINE = {"2. 추출부": {"name": "추출부", "category": "Unit"}, "2.1 NG unit": {"name": "NG unit", "category": "Unit"},
                 "3. 이송부": {"name": "이송부", "category": "Unit"}, "1. 이송부": {"name": "이송부", "category": "Unit"},
                 "언와인더 unit": {"name": "언와인더 unit", "category": "Unit"},
                 "리와인더 unit": {"name": "리와인더 unit", "category": "Unit"}}
#: 추출 mock 힌트 — 조각 글에 든 말 → 개체(소속 없음 · 폴백 사슬 · 보강의 재료)
PROSE_WORDS = (("모터 회전수", "Property"), ("실린더 행정", "Property"), ("벨트 장력", "Property"),
               ("스태킹", "Process"), ("센서", "Unit"), ("N/A", "Property"), ("속도", "Property"),
               ("하중", "Property"), ("장력", "Property"))
PROSE_DT = "fw_prose"
#: 바닥 D의 사내 꼴 표(창작 — 근거가 아니다) — 같은 좌표 둘 이상 · 같은 관리항목 이름이 다른 좌표에 하나
CPU_DT = "fw_cp_unit"
CPU_HEAD = ("공정구분", "공정명", "관리항목", "규격", "측정방법", "대응계획")
CPU_ROWS = (("노칭", "노칭 타발", "버 높이", "10um 이하", "현미경", "금형 재연마"),
            ("노칭", "노칭 타발", "타발 치수", "0.1mm 이내", "캘리퍼", "금형 점검"),
            ("노칭", "전극 리와인딩", "버 높이", "12um 이하", "현미경", "재검"),
            ("노칭", "전극 리와인딩", "권취 장력", "30N", "로드셀", "장력 조정"))
CPU_SCHEMA = {"doc_type": CPU_DT, "schema_version": 1, "layer": "process", "payload_kind": "table",
              "use_blocks": ["common_core", "process_coord"],
              "fields": {"관리항목": {"role": "entity", "category": "Property"},
                         "규격": {"role": "attribute", "attach_to_field": "관리항목", "attr_name": "spec", "contextual": True,
                                "optional": True},
                         "측정방법": {"role": "attribute", "attach_to_field": "관리항목", "optional": True},
                         "대응계획": {"role": "content", "attach_to_field": "관리항목", "optional": True}},
              "edges": [{"from": "@process_ref", "relation": "has_property", "to": "관리항목"}]}
CPU_ADAPTER = '''from parser import normalizer

ADAPTER = {"doc_type": %r, "adapter_version": "fw-1", "payload_kind": "table",
           "expects": {"header_row": 1, "data_start_row": 2, "header_labels": %r,
                       "columns": {"process_group": "A", "process_ref": "B", "관리항목": "C", "규격": "D", "측정방법": "E",
                                   "대응계획": "F"}}}


def extract(raw):
    exp, out = ADAPTER["expects"], []
    for sheet in raw.get("sheets", []):
        cells = normalizer.expand_merged(sheet)
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {f: str(cells.get("%%s%%d" %% (c, row)) or "").strip() for f, c in exp["columns"].items()}
            if any(rec.values()):
                rec["source_locator"] = "%%s!R%%d" %% (sheet.get("name", "sheet"), row)
                out.append(rec)
    return out
''' % (CPU_DT, list(CPU_HEAD))
SAMPLES = 3                          # 다른 것마다 보이는 견본 수
CUT = 300                            # 견본 한 줄 길이


# ---------------------------------------------------------------- 덤프 (사본 안에서 돈다)
def _state():
    """지금 상태 루트의 네 벌 + `data/` 파일 목록 — id·시각 없이."""
    from core import paths as P
    from core.state import store
    from core.state.world import World
    w = World()
    name = {n["id"]: f"{lay}:{n['canonical']}" for lay, n in w.nodes()}

    def canon(x):
        if isinstance(x, dict):
            return {k: canon(v) for k, v in x.items() if k not in TS}
        if isinstance(x, list):
            return [canon(v) for v in x]
        return name.get(x, x) if isinstance(x, str) else x

    def line(x):
        return json.dumps(canon(x), ensure_ascii=False, sort_keys=True)

    led = P.work("ingest_log")
    return {
        "graph": {lay: {"nodes": sorted(line(dict(n, id=None)) for n in g.nodes.values()),
                        "edges": sorted(line(e) for e in g.edges)}
                  for lay, g in sorted(w.graphs.items())},
        "dict": line(store.read(store.DICTIONARY, {})),
        "queue": sorted(line(x) for x in store.read(store.QUEUE, [])),
        "ledger": ({f.name: canon(json.loads(f.read_text(encoding="utf-8")))
                    for f in sorted(led.glob("*.json"))} if led.exists() else {}),
        "files": sorted(P.rel_to_home(x) for x in P.data().rglob("*")
                        if x.is_file() and not x.name.endswith(".lock")),
    }


def dump(out):
    """두 바닥을 차례로 세우고 덤프를 `out`에 쓴다 — 이 파일이 놓인 사본의 코드로."""
    os.environ["USE_MOCK"] = "1"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))          # 바닥 B(g65_common)
    import run as RUN
    from cli import ingest as IG
    from core.state import fixtures, init
    quiet = contextlib.redirect_stdout
    res, st = {}, {}
    with quiet(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
    for f in TABLE:
        try:
            with quiet(io.StringIO()):
                r = IG.ingest_file(str(fixtures.RAW / f), None, ask=False)
            st[f] = (r or {}).get("status")
        except SystemExit as e:
            st[f] = f"exit {e.code}"
    res["A_status"], res["A"] = st, _state()
    import g65_common as G
    with quiet(io.StringIO()):
        G.fresh()
    res["B"] = _state()
    res["C_status"], res["C"] = _prose(quiet)
    res["D_status"], res["D"] = _cp_unit(quiet)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return 0


def _select(payload):
    """연결 보강 mock 선별 규칙 — 첫 후보 · 근거는 조각 첫 문장(결정적 · 창작)."""
    cands = payload.get("candidates") or []
    text = str(payload.get("chunk") or "").split("\n", 1)[-1]
    first = text.split(".")[0].strip()
    return {"id": cands[0]["id"] if cands else None, "rel": None, "evidence": first}


def _structure_kw():
    """문서 구조 주입(B119 ① — 그 사본의 파서가 받을 때만 · 기준 사본에는 없다)."""
    import inspect
    from parser import pipeline
    if "structure" not in inspect.signature(pipeline.parse).parameters:
        return {}
    from core.build import structure as ST
    return {"structure": ST.structurer()}


def _roles_of_copy(hint):
    """표본 힌트의 역할을 **그 사본의 말로** — 역할 셋(대상 · 묶음 · 주제 — B124 ③)을 모르는 옛 사본이면 옛 이름으로 바꿔 쓴다
    (두 사본이 같은 구조를 보게 — 바뀐 몫만 다르게)."""
    from parser import struct_rule
    if "대상" in struct_rule.ROLES:
        return hint
    old = {"대상": "유닛", "묶음": "사양 묶음"}
    return {fr: [{**x, "role": old.get(x.get("role"), x.get("role"))} for x in rows] for fr, rows in hint.items()}


def _value(word, cat, text):
    """값(B120 ① — 지시문 「그 항목에 건 값 · 원문 글자 그대로」의 창작 대역): 사양 말 뒤의 「숫자+단위」 · 없으면 키 없음."""
    m = re.search(re.escape(word) + r"\S*\s*(\d[\d.,]*\s*[A-Za-z%]+)", text or "") if cat == "Property" else None
    return {"value": m.group(1)} if m else {}


def _prose(quiet):
    """바닥 C — 클린 → bootstrap → 산문 종류 등록 → 표본 엑셀 · 힌트를 만들고 넣는다(마무리 포함)."""
    import run as RUN
    from openpyxl import Workbook
    from cli import ingest as IG
    from core import paths as P
    from core.build import reinforce
    from core.state import fixtures, init
    from parser import pipeline, tuning
    from parser.adapters import basic_prose_xlsx as BX
    import g6_common as G6
    with quiet(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
        G6._register("process", PROSE_DT)
    tuning.apply({"chunk_rows": [1, 2]})               # 제목이 구획 경로에 서게(창작 표본의 손잡이 — 근거가 아니다)
    reinforce.SELECT = _select
    st = {}
    for did, (coord, sheets) in PROSE.items():
        wb = Workbook()
        wb.remove(wb.active)
        for name, rows in sheets.items():
            ws = wb.create_sheet(title=name)
            for r, v in enumerate(rows, 1):
                ws.cell(row=r, column=1, value=v)
        path = P.ensure(P.raw(f"{did}.xlsx"))
        wb.save(path)
        roles = {n: "prose" for n in sheets}
        fixtures.EXTRACT_HINTS.mkdir(parents=True, exist_ok=True)
        if did in PROSE_STRUCTURE:
            (fixtures.EXTRACT_HINTS / f"{did}@structure.json").write_text(
                json.dumps(_roles_of_copy(PROSE_STRUCTURE[did]), ensure_ascii=False), encoding="utf-8")
        env = pipeline.parse(BX, did, str(path), sheet_roles=roles, closed_list=[], **_structure_kw()).envelope
        hints = {}
        for c in env.get("chunks") or []:
            # 소속 = 그 조각의 구조 사슬에서 대상이 선 가장 깊은 줄(지시문 「가장 구체적인 주인」의 창작 대역 · 구조가 없으면 없음)
            own = next((x for x in reversed((c.get("meta") or {}).get("structure") or []) if x.get("name")), None)
            cat = (PROSE_OUTLINE.get(str((own or {}).get("text") or "")) or {}).get("category")   # 카테고리는 목차 노드화 몫 (B148 ②)
            bel = {"name": own["name"], "category": cat, "from": "제목"} if own and cat else None
            words = [(w, cat) for w, cat in PROSE_WORDS if w in (c.get("text") or "")]
            words = [(w, cat) for w, cat in words if not any(w != v and w in v for v, _c in words)]   # 긴 말이 이긴다
            ents = [{"surface": w, "category": cat, **({"belongs_to": bel} if bel else {}), **_value(w, cat, c.get("text"))}
                    for w, cat in words]
            if ents:
                hints[c["source_locator"]] = {"entities": ents, "relations": [], "attach": []}
        (fixtures.EXTRACT_HINTS / f"{did}.json").write_text(json.dumps(hints, ensure_ascii=False), encoding="utf-8")
        (fixtures.EXTRACT_HINTS / f"{did}@outline.json").write_text(json.dumps(PROSE_OUTLINE, ensure_ascii=False),
                                                                   encoding="utf-8")
        spec = " ".join(f"{i}:prose" for i in range(1, len(sheets) + 1))
        with quiet(io.StringIO()):
            r = IG.ingest_file(str(path), PROSE_DT, ask=False, sheets=spec, coord=coord or "none")
        st[did] = (r or {}).get("status")
    reinforce.SELECT = None
    return st, _state()


def cpu_setup(schema=None):
    """사내 꼴 표 종류(`CPU_DT`)를 지금 상태 루트의 등록 단에 직접 세우고(등록 LLM 0) 표본 엑셀을 원본 자리에 쓴다 — 엑셀 자리.
    바닥 D와 시험(B147 ⓑⓒ — 스키마를 바꿔 넣는다)이 같은 재료를 쓴다."""
    from openpyxl import Workbook
    from core import paths as P
    from core.state import store
    sp, ap = P.ensure(P.schemas(f"{CPU_DT}.json")), P.ensure(P.adapters(f"{CPU_DT}.py"))
    sp.write_text(json.dumps(schema or CPU_SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ap.write_text(CPU_ADAPTER, encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[CPU_DT] = {"doc_type": CPU_DT, "status": "registered", "layer": "process", "schema": f"schemas/{CPU_DT}.json",
                   "adapter": str(ap), "schema_version": 1}
    store.write(store.DOC_TYPES, dts)
    wb = Workbook()
    ws = wb.active
    ws.title = "CP"
    for r, row in enumerate((CPU_HEAD,) + CPU_ROWS, 1):
        for c, v in enumerate(row, 1):
            ws.cell(row=r, column=c, value=v)
    path = P.ensure(P.raw("FWCPU.xlsx"))
    wb.save(path)
    return path


def _cp_unit(quiet):
    """바닥 D — 클린 → bootstrap → 사내 꼴 표 종류를 등록 단에 직접 → 엑셀을 만들고 넣는다(마무리 포함 · 보강 선별 주입)."""
    import run as RUN
    from cli import ingest as IG
    from core.build import reinforce
    from core.state import init
    with quiet(io.StringIO()):
        init.init(fresh_=True, all_=True)
        RUN.cmd_bootstrap([])
    path = cpu_setup()
    reinforce.SELECT = _select
    try:
        with quiet(io.StringIO()):
            r = IG.ingest_file(str(path), CPU_DT, ask=False)
        st = {"FWCPU": (r or {}).get("status")}
    except SystemExit as e:
        st = {"FWCPU": f"exit {e.code}"}
    reinforce.SELECT = None
    return st, _state()


# ---------------------------------------------------------------- 사본 · 실행
def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def _copy_base(commit, dest):
    """기준 — 그 커밋의 추적 파일 그대로."""
    kw = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
    with tarfile.open(fileobj=io.BytesIO(_git("archive", "--format=tar", commit))) as t:
        t.extractall(dest, **kw)


def _copy_now(dest):
    """지금 — 작업 트리의 추적 파일 + 새 파일(무시 파일 제외 · 커밋 안 한 변경 포함)."""
    for rel in filter(None, _git("ls-files", "-z", "-co", "--exclude-standard").split(b"\0")):
        src = ROOT / os.fsdecode(rel)
        if src.is_file():                            # 지운 추적 파일은 목록에만 남는다
            dst = dest / os.fsdecode(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _run(work, trees):
    """사본마다 덤프를 동시에 돌린다 — 격리 환경(`gateway.isolated_env` — doctor · 시험과 같은 함수 · B111 ①)에서
    mock 세계의 시험 문까지 빼고(사본마다 기본 mock 루트) · 출력은 로그 파일로."""
    sys.path.insert(0, str(ROOT))
    from core.llm import gateway
    env = {k: v for k, v in gateway.isolated_env().items() if k not in gateway.MOCK_WORLD_ENV}
    procs = {}
    for side, tree in trees.items():
        me = tree / "tools" / Path(__file__).name
        me.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(__file__, me)
        with open(work / f"{side}.log", "w", encoding="utf-8") as fh:
            procs[side] = subprocess.Popen([sys.executable, str(me), "--dump", str(work / f"{side}.json")],
                                           cwd=tree, env=env, stdout=fh, stderr=subprocess.STDOUT)
    rc = {side: p.wait() for side, p in procs.items()}
    return {side: (rc[side], (work / f"{side}.log").read_text(encoding="utf-8")) for side in trees}


# ---------------------------------------------------------------- 대조
def _summary(label, d):
    out = []
    for side in [x for x in ("A", "B", "C", "D") if x in d]:
        g = d[side]
        out.append(f"{label} {side}" + (f" 넣기 {d[side + '_status']}" if side + "_status" in d else "")
                   + f" · 노드 { {k: len(v['nodes']) for k, v in g['graph'].items()} }"
                   + f" · 엣지 { {k: len(v['edges']) for k, v in g['graph'].items()} }"
                   + f" · 큐 {len(g['queue'])} · 대장 행 {sum(len(v.get('rows') or []) for v in g['ledger'].values())}")
    return out


def _diff(label, p, q):
    """`(줄들, 다른가)` — 목록 둘을 중복까지 센다(빠짐 = 기준에만 · 더함 = 지금에만)."""
    gone, new = Counter(p) - Counter(q), Counter(q) - Counter(p)
    out = [f"{label}: 기준 {len(p)} · 지금 {len(q)} · 빠짐 {sum(gone.values())} · 더함 {sum(new.values())}"]
    out += [f"    - {s[:CUT]}" for s in sorted(gone)[:SAMPLES]]
    out += [f"    + {s[:CUT]}" for s in sorted(new)[:SAMPLES]]
    return out, bool(gone or new)


def compare(a, b):
    """벌마다 다른 것 — `(줄들, 다른 것이 있는가)`."""
    same = all(a.get(f"{s}_status") == b.get(f"{s}_status") for s in ("A", "C", "D"))
    lines, differs = [f"A · C · D 넣기 결과 같음 {same}"], not same
    for side in [x for x in ("A", "B", "C", "D") if x in a or x in b]:
        if side not in a or side not in b:
            lines.append(f"{side} 한쪽에만 있다 — 기준 {side in a} · 지금 {side in b}")
            differs = True
            continue
        x, y = a[side], b[side]
        for lay in sorted(set(x["graph"]) | set(y["graph"])):
            for part in ("nodes", "edges"):
                ls, d = _diff(f"{side} 그래프 {lay} {part}", x["graph"].get(lay, {}).get(part, []),
                              y["graph"].get(lay, {}).get(part, []))
                lines, differs = lines + ls, differs or d
        same = x["dict"] == y["dict"]
        lines, differs = lines + [f"{side} 사전 같음 {same}"], differs or not same
        ls, d = _diff(f"{side} 큐", x["queue"], y["queue"])
        lines, differs = lines + ls, differs or d
        dl = sorted(k for k in set(x["ledger"]) | set(y["ledger"]) if x["ledger"].get(k) != y["ledger"].get(k))
        lines.append(f"{side} 판정 대장: 파일 {len(y['ledger'])} · 다른 파일 {dl}")
        fx, fy = set(x["files"]), set(y["files"])
        lines.append(f"{side} data 파일: 빠짐 {sorted(fx - fy)} · 더함 {sorted(fy - fx)}")
        differs = differs or bool(dl) or fx != fy
    return lines, differs


def main(argv=None):
    ap = argparse.ArgumentParser(description="네 벌 대조 — 기준 커밋 vs 지금 작업 트리(mock 첫 인입)")
    ap.add_argument("--base", help="기준 커밋 — 회차 반입 커밋 등")
    ap.add_argument("--keep", help="덤프 둘(base.json · now.json)을 남길 폴더")
    ap.add_argument("--dump", help=argparse.SUPPRESS)          # 사본 안에서 부르는 문
    a = ap.parse_args(argv)
    if a.dump:
        return dump(a.dump)
    if not a.base:
        ap.error("--base <커밋>이 필요하다")
    try:
        sha = _git("rev-parse", "--verify", "--short", f"{a.base}^{{commit}}").decode().strip()
    except subprocess.CalledProcessError:
        print(f"기준 커밋을 찾지 못했다: {a.base}")
        return 2
    dirty = len(_git("status", "--porcelain").decode().splitlines())
    print(f"기준 {sha} {_git('log', '-1', '--format=%s', sha).decode().strip()[:70]}")
    print(f"지금 작업 트리 — HEAD {_git('rev-parse', '--short', 'HEAD').decode().strip()} · 커밋 안 한 변경 {dirty}")
    t0, work = time.time(), Path(tempfile.mkdtemp(prefix="four_way_"))
    try:
        trees = {"base": work / "base", "now": work / "now"}
        _copy_base(sha, trees["base"])
        _copy_now(trees["now"])
        res = _run(work, trees)
        bad = [side for side, (rc, _) in res.items() if rc]
        for side in bad:
            print(f"── {side} 실행 실패 rc={res[side][0]} — 로그 끝 20줄")
            print("\n".join(res[side][1].splitlines()[-20:]))
        if bad:
            return 2
        d = {side: json.loads((work / f"{side}.json").read_text(encoding="utf-8")) for side in trees}
        if a.keep:
            keep = Path(a.keep)
            keep.mkdir(parents=True, exist_ok=True)
            for side in trees:
                shutil.copy2(work / f"{side}.json", keep / f"{side}.json")
        lines, differs = compare(d["base"], d["now"])
        print("\n".join(_summary("기준", d["base"]) + _summary("지금", d["now"]) + lines))
        print(f"{'다른 것이 있다' if differs else '전부 같다'} · 소요 {time.time() - t0:.0f}초"
              + (f" · 덤프 {a.keep}" if a.keep else ""))
        return 1 if differs else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
