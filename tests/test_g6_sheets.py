# -*- coding: utf-8 -*-
"""G6 ⑦ 시트 역할 관문 — 시트 여러 장 엑셀을 prose로 넣을 때 **문서마다 한 번** (B83).

표본은 `tests/fixtures/raw/RFQ01.xlsx`(7시트 · `tests/fixtures/make_rfq.py`가 만든다).
잠그는 성질 넷: ①기록과 파서(`skip`은 어댑터가 보지 않고 `ref`는 표시가 붙는다)
②표와 제안(규칙 · LLM 0) ③관문(물을 수 있으면 묻고 없으면 거부) ④참조 청크의 처지
(추출 0 · 큐 0 · 열람에는 보인다 · 답의 근거는 아니다).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _sp72, done, json, os, store)   # noqa: F401

from cli import _screen                                              # noqa: E402
from cli import ingest_screen as SCR                                 # noqa: E402
from core.state import sheets as SH                                  # noqa: E402
from parser import form as FORM, reader as READER                    # noqa: E402
from parser import pipeline as PIPE                                  # noqa: E402

RFQ = ROOT / "tests" / "fixtures" / "raw" / "RFQ01.xlsx"
DT = "prose_xlsx_basic"          # 레포의 기본 prose 엑셀 어댑터 — 표본용으로 등록한다
SCHEMA = {"doc_type": DT, "schema_version": 1, "layer": "process",
          "payload_kind": "prose", "use_blocks": ["common_core", "process_coord"],
          "_note": "B83 회귀 — 시트 역할 관문의 표본은 prose 엑셀이다",
          "fields": {}, "edges": []}


def _register():
    """표본 doc_type을 **등록 단에 세운다** — 인입은 미등록을 거부한다(B3).

    내장(`tests/fixtures/schemas/`)에 넣지 않는 이유: 내장 목록은 `doctor`·
    `platform doctypes` 화면에 그대로 뜬다 — 회귀용 이름을 거기 얹지 않는다.
    """
    p = _P.schemas(f"{DT}.json")
    _P.ensure(p)
    p.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    dts = store.read(store.DOC_TYPES, {})
    dts[DT] = {"doc_type": DT, "status": "registered", "layer": "process",
               "schema": f"schemas/{DT}.json",
               "adapter": str(ROOT / "parser" / "adapters" / "basic_prose_xlsx.py"),
               "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _unregister():
    dts = store.read(store.DOC_TYPES, {})
    dts.pop(DT, None)
    store.write(store.DOC_TYPES, dts)
    _P.schemas(f"{DT}.json").unlink(missing_ok=True)


def _run(*argv, answers=None):
    """`run.py`를 돌린다 — `answers`가 있으면 **pty**로(관문은 tty에서만 산다)."""
    if answers is None:
        r = _sp72.run([sys.executable, str(ROOT / "run.py"), *argv],
                      capture_output=True, text=True, cwd=str(ROOT),
                      env={**os.environ, "USE_MOCK": "1"}, stdin=_sp72.DEVNULL)
        return r.stdout + r.stderr
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                             # pragma: no cover
        os.environ["USE_MOCK"] = "1"
        os.chdir(str(ROOT))
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), *argv])
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    os.waitpid(pid, 0)
    return _screen.strip_ansi(out.decode("utf-8", "replace"))


def _ingest(*extra, answers=None):
    return _run("ingest-file", str(RFQ), "--doc-type", DT, "--allow-mock",
                *extra, answers=answers)


def _chunks():
    ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    return {cid: c for cid, c in ch.items() if c.get("doc_id") == "RFQ01"}


def _fresh():
    """클린 + 골격 + 표본 등록 — 두 실행을 비교하려면 시작이 같아야 한다."""
    _run("init", "--fresh")
    _run("bootstrap")
    _register()
    SH.path("RFQ01").unlink(missing_ok=True)


print("\n■ B83 ① 역할 셋과 기록 — `registry/sheet_roles/<doc_id>.json`")
_fresh()
_rows = FORM.sheet_table(READER.read(str(RFQ)))
_names = [r["name"] for r in _rows]

# ① 파서는 역할을 **데이터로 받을 뿐**이다 — 없으면 한 글자도 다르지 않다.
_raw = READER.read(str(RFQ))
_pieces = [{"meta": {"frame": "가격"}}]
show("① `sheet_roles=None`이면 파서의 두 자리가 **같은 객체를 그대로** 돌려준다",
     PIPE.drop_skipped(_raw, None) is _raw and PIPE.mark_roles(_pieces, None) is _pieces)
show("① 전부 `prose`인 역할은 역할 없음과 산출이 같다 (없는 키가 기본이다)",
     PIPE.drop_skipped(_raw, {n: "prose" for n in _names}) is _raw
     and PIPE.mark_roles(_pieces, {n: "prose" for n in _names})[0]["meta"]
     == {"frame": "가격"})

_out = _ingest("--sheets", "2-4:prose 5:ref *:skip")
_rec = SH.read("RFQ01")
show("① 기록은 ②등록 단이다 — `registry/` 아래 파일 하나(mock은 상태 루트 mock)",
     SH.path("RFQ01").exists()
     and SH.path("RFQ01").parent.parent == _P.registry()
     and _P.rel_to_home(SH.path("RFQ01")).startswith("registry/"),
     _P.rel_to_home(SH.path("RFQ01")))
show("① 기록은 사람의 답이다 — doc_id·file·decided_by·at·sheets 다섯",
     set(_rec) == {"doc_id", "file", "decided_by", "at", "sheets"}
     and _rec["decided_by"] == "flag" and set(_rec["sheets"]) == set(_names),
     f"{_rec['decided_by']} · {SH.summary(_rec['sheets'])}")
_mine = _chunks()
_frames = {(c.get("meta") or {}).get("frame", "?").split("!")[0] for c in _mine.values()}
_skips = {n for n, r in _rec["sheets"].items() if r == "skip"}
_refs = {n for n, r in _rec["sheets"].items() if r == "ref"}
show("① `skip` 시트의 조각은 **하나도 없다** (어댑터가 보기 전에 뺀다)",
     not (_frames & _skips) and _frames, f"프레임 {sorted(_frames)}")
show("① `ref` 시트의 청크는 전부 `meta.sheet_role == 'ref'`이고 `prose`에는 키가 없다",
     all((c.get("meta") or {}).get("sheet_role") == "ref"
         for c in _mine.values()
         if (c.get("meta") or {}).get("frame", "?").split("!")[0] in _refs)
     and all("sheet_role" not in (c.get("meta") or {})
             for c in _mine.values()
             if (c.get("meta") or {}).get("frame", "?").split("!")[0] not in _refs),
     f"참조 청크 {sum(1 for c in _mine.values() if (c.get('meta') or {}).get('sheet_role') == 'ref')}"
     f" / 전체 {len(_mine)}")

print("\n■ B83 ② 시트 표와 제안 — 규칙으로, LLM 0")
show("② 표의 행 수 == 통합문서의 시트 수이고 각 행의 이름이 시트 이름이다",
     len(_rows) == len(_raw["sheets"])
     and [r["name"] for r in _rows] == [s["name"] for s in _raw["sheets"]],
     f"{len(_rows)}행 · {_names}")
show("② 값 있는 셀 0인 시트의 제안은 `skip`이다 (읽을 것이 없다)",
     FORM.suggest_role(FORM.sheet_stats({"name": "빈", "max_row": 9, "max_col": 3,
                                         "cells": {"A1": None, "B2": "  "}})) == "skip")
show("② 제안은 닫힌 셋 안이고 문턱은 상수 셋이다 (LLM 지점 0 — 규칙이다)",
     {r["suggest"] for r in _rows} <= set(FORM.SHEET_ROLES)
     and set(FORM.SHEET_THRESHOLDS) == {"text_ratio", "rows", "avg_len"},
     f"{FORM.SHEET_THRESHOLDS} · 제안 {sorted({r['suggest'] for r in _rows})}")
_blk = _screen.strip_ansi(SCR.sheet_table_block(_rows, file=str(RFQ)))
_parsed = [l.split() for l in _blk.splitlines()[2:]]
show("② 표는 **색을 벗긴 문자열에서 파싱된다** (어서션·문면 검사가 읽는다)",
     len(_parsed) == len(_rows)
     and [p[1] for p in _parsed] == _names
     and [p[-1] for p in _parsed] == [r["suggest"] for r in _rows],
     _blk.splitlines()[2].strip()[:60])
_fresh()
_dry = _ingest("--dry-run")
show("② `--dry-run`은 표를 **보여만 준다** — 묻지 않고 기록 파일도 만들지 않는다",
     "■ 시트 역할" in _dry and "dry-run" in _dry
     and not SH.path("RFQ01").exists())
_solo = _run("ingest-file", str(ROOT / "tests/fixtures/raw/TOC01.xlsx"),
             "--doc-type", DT, "--allow-mock")
show("② 시트 하나면 표도 관문도 없다 (지나간다)",
     "■ 시트 역할" not in _solo and not SH.path("TOC01").exists()
     and "성공" in _solo, [l for l in _solo.splitlines() if "[성공]" in l][:1])

print("\n■ B83 ③ 관문 — 물을 수 있으면 묻고, 없으면 거부")
_fresh()
_n0 = len(open_graph("process").nodes)
_ref = _ingest()
show("③ 비대화형이면 **상태 거부**이고 문면에 시트 이름이 전부 있다",
     "시트 역할 미정" in _ref and all(n in _ref for n in _names)
     and "ingest-file" in _ref and "--sheets" in _ref,
     [l.strip() for l in _ref.splitlines() if "시트 역할 미정" in l][:1])
show("③ 거부는 쓰기 0이다 — 그래프·청크·기록 어디에도 남지 않는다",
     not SH.path("RFQ01").exists() and not _chunks()
     and len(open_graph("process").nodes) == _n0,
     f"노드 {_n0} · 청크 {len(_chunks())}")
_bad = _ingest("--sheets", "2:없는역할")
show("③ 문법 오류는 `[사용법]`이다 (조용히 기본값으로 떨어지지 않는다)",
     "--sheets" in _bad and "닫힌 셋" in _bad and not SH.path("RFQ01").exists(),
     [l.strip() for l in _bad.splitlines() if "[투입]" in l][:1])
_left = _ingest("--sheets", "2:prose")
show("③ 미정 시트가 남은 `--sheets`도 `[사용법]`이다",
     "역할이 없는 시트가 남았다" in _left and not SH.path("RFQ01").exists())
_q = _ingest(answers="q\n")
show("③ tty에서 `q`는 그 문서 중단 — 쓰기 0 (표와 질문은 떴다)",
     "■ 시트 역할" in _q and "중단 —" in _q
     and not SH.path("RFQ01").exists() and not _chunks())
_ent = _ingest(answers="\n")
_rec_e = SH.read("RFQ01")
show("③ tty에서 Enter는 **제안과 같은 기록**이다 (`decided_by: gate`)",
     _rec_e and _rec_e["decided_by"] == "gate"
     and _rec_e["sheets"] == {r["name"]: r["suggest"] for r in _rows},
     SH.summary((_rec_e or {}).get("sheets") or {}))
_again = _ingest()
show("③ 같은 문서 재인입은 관문 0이다 — 기록이 있으면 표도 질문도 없다(비tty에서도 간다)",
     "■ 시트 역할" not in _again and "기록대로 진행" in _again and "성공" in _again,
     [l.strip() for l in _again.splitlines() if "기록대로" in l][:1])
_h1 = {c["source_locator"] for c in _chunks().values()}
_again2 = _ingest()
show("③ 멱등 — 두 번째 인입의 청크 자리가 같다",
     {c["source_locator"] for c in _chunks().values()} == _h1)
SH.write("RFQ01", "RFQ01.xlsx",
         {n: r for n, r in _rec_e["sheets"].items() if n != "일정"}, "flag")
_newsheet = _ingest()
_sug = ([l for l in _newsheet.splitlines() if "역할을 바로 주려면" in l] or [""])[0]
show("③ 기록에 없는 시트가 생기면 **그 시트만** 문면에 싣고 거부한다(미결)",
     "기록에 없는 시트 1장 — 일정" in _newsheet and '"7:ref"' in _sug
     and "prose" not in _sug and all(n in _newsheet for n in _names),
     [l.strip() for l in _newsheet.splitlines() if "기록에 없는" in l][:1])

print("\n■ B83 ④ 참조 청크의 처지 — 추출 0 · 큐 0 · 열람에는 보인다")
_fresh()
_ingest("--sheets", "2-4:prose 5:ref *:skip")
_mine = _chunks()
_refids = {cid for cid, c in _mine.items()
           if (c.get("meta") or {}).get("sheet_role") == "ref"}
_ex = json.loads(_P.extract("RFQ01.json").read_text(encoding="utf-8"))
_cand = {c["chunk_id"] for c in _ex["candidates"]}
show("④ 참조 청크는 추출에 **부르지 않는다** — 후보 목록에 0건이고 건너뛴 수가 남는다",
     _refids and not (_refids & _cand) and _ex.get("ref_skipped") == len(_refids),
     f"참조 {len(_refids)} · ref_skipped {_ex.get('ref_skipped')} · 후보 {len(_cand)}")
show("④ 청크 자체는 남는다 — `chunks.json`에 있고 `linked == false`다",
     all(_mine[cid].get("linked") is False for cid in _refids))
_qrows = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == "RFQ01"]
show("④ 큐에 참조 청크 유래 항목 0 (후보 0건이 결함으로 세어지지 않는다)",
     not [x for x in _qrows
          if str((x.get("payload") or {}).get("chunk_id") or "") in _refids],
     f"큐 {len(_qrows)}건 — {sorted({x['kind'] for x in _qrows})}")
_showdoc = _run("show", "doc", "RFQ01")
show("④ `show doc`에 역할 요약과 참조 청크 수가 뜬다",
     "시트 역할" in _showdoc and "참조" in _showdoc,
     [l.strip() for l in _showdoc.splitlines() if "시트 역할" in l][:1])
from cli.viewer import data as VD                                    # noqa: E402
_api = VD.doc("RFQ01")
show("④ `/api/doc`의 청크 목록에 `sheet_role`이 있고 기록이 실린다",
     all("sheet_role" in c for c in _api["chunks"])
     and _api["sheet_roles"] == (SH.read("RFQ01") or {}).get("sheets")
     and sum(1 for c in _api["chunks"] if c["sheet_role"] == "ref") == len(_refids))
from cli import query as QR                                          # noqa: E402
_ans = QR.answer("노칭 설비의 사양은?")
show("④ `answer()`의 근거 청크에 참조 청크가 0이다 (노드에 안 붙은 청크는 답이 아니다)",
     not (_refids & {c.get("chunk_id") for c in (_ans.get("chunks") or [])}),
     f"근거 청크 {len(_ans.get('chunks') or [])}")

_unregister()
done()
