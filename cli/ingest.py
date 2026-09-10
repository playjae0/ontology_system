# -*- coding: utf-8 -*-
"""일괄 투입 — 파일 하나 또는 경로 하나로 **선택 → 파싱 → 인입**을 잇는다 (문서 6 §6.4 · B46).

  python run.py ingest-file <문서> [--doc-type X] [--dry-run]
  python run.py ingest-dir  <경로> [--doc-type X] [--dry-run]

기존 `parse run`·`build`는 그대로다 — 이것은 그 **위**의 편의 명령이고 같은 코드를 부른다
(`cli.parse.run_parse` · `core.pipeline.run_document`).

**선택의 규칙**(B46 조건 셋):
  ① 무엇으로 골랐는지 화면과 인입 기록(`doc_registry.json`의 `routing`)에 남긴다.
  ② `--dry-run`은 선택 결과만 보이고 파싱·인입을 하지 않는다.
  ③ 유일 일치만 자동으로 간다 — **둘 이상·0건이면 사람에게 올리고 멈춘다**(미선택).
`--doc-type`을 주면 스캔하지 않고 그것으로 본다(사람 지정 — 기본 경로). 비정형(pptx)은
헤더 지문이 없어 스캔 대상이 아니다 — 지정 없이 오면 미선택으로 남는다.

**문서 단위 독립**(C14의 연장) — 한 건의 실패가 나머지를 멈추지 않고, 끝에 성공·실패·
미선택 목록을 모아 보인다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from cli import scan as scan_mod
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.parse import run_parse
from core import registry, store
from core.pipeline import finalize, run_document

ROOT = Path(__file__).resolve().parent.parent

# reader가 여는 포맷 — 그 밖은 「지원 밖」으로 목록에만 남긴다.
# **목록은 리더가 소유한다**(B53) — 여기에 복제하면 리더에 포맷을 더해도 투입이 막는다.
from parser.reader import GRID_EXT, PROSE_EXT, SUPPORTED   # noqa: E402,F401
from parser import form as form_mod, reader as reader_mod  # noqa: E402

OK, FAIL, SKIP = "성공", "실패", "미선택"


def _norm_path(p):
    """경로 비교용 정규화 — 상대/절대·`./`·심볼릭 링크 차이로 헛경고를 내지 않는다."""
    try:
        return str(Path(p).resolve())
    except OSError:
        return str(Path(p).absolute())


def doc_id_of(path):
    """**같은 문서는 항상 같은 doc_id** (재인입 계약) — 파일명 stem, 공백은 `_`.

    경로는 넣지 않는다 — 폴더를 옮겨도 같은 문서다(D-110). 대신 **다른 폴더의 같은
    이름은 같은 문서로 취급된다** — 그 경우 인입은 「개정」으로 돌고, 이 명령은 등록
    대장의 `source_path`가 다르면 화면에 경고한다.
    """
    return re.sub(r"\s+", "_", Path(path).stem.strip())


def form_of(doc):
    """형태 판정(table/prose) — **격자 포맷만**. `.pptx`·`.pdf`는 포맷이 prose를 함의한다.

    선택 근거(`basis`)에 실어 인입 기록으로 보낸다 — **기록이 이 기능의 절반이다**
    (문서 1 C37): 문턱 조정과 애매 구간 측정의 유일한 재료이고, 그 크기가 재어진
    뒤에야 LLM 보조를 검토한다.

    판정이 **선택을 바꾸지는 않는다** — doc_type이 정해지면 어댑터가 갈래를 이미
    말한다. 여기서 하는 일은 ①기록 ②그 둘이 어긋날 때 화면 경고다. 판정으로
    어댑터를 갈아 끼우면 사람이 지정한 doc_type이 조용히 무시된다.
    """
    p = Path(doc)
    if p.suffix.lower() not in GRID_EXT:
        return None
    try:
        return form_mod.judge(reader_mod.read(str(p)))
    except Exception as e:                       # 판정 실패가 인입을 막지 않는다
        return {"verdict": None, "auto": False, "signals": {},
                "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}


def select(doc, doc_type=None, adapter_paths=None):
    """doc_type 선택 — 파싱하지 않는다. 결과 `status`는 chosen · ambiguous · none · unsupported.

    `basis`가 **선택 근거**다(B46 ①): 사람 지정이면 `by=human`, 스캔이면 `by=scan`과
    일치 내역(`header_labels` 완전 일치 — 누락 0·잉여 0)이 함께 실린다.
    """
    p = Path(doc)
    out = {"doc": str(p), "doc_id": doc_id_of(p), "doc_type": None, "adapter": None,
           "basis": None, "candidates": [], "reason": None}
    if p.suffix.lower() not in SUPPORTED:
        return {**out, "status": "unsupported",
                "reason": f"지원하지 않는 포맷 {p.suffix!r} — reader가 여는 것은 {SUPPORTED}"}
    if doc_type:
        if registry.schema_of(doc_type) is None:
            return {**out, "status": "none",
                    "reason": f"미등록 doc_type '{doc_type}' — 구축 모드(register) 대상이다"}
        # 어댑터 실물은 **지문 스캔과 같은 소재지**에서 찾는다(등록부 + 기본 소재지) —
        # 등록부만 보면 내장 doc_type(스키마만 싣고 어댑터는 mock 트랙)이 지정으로도 안 간다.
        found = {m.ADAPTER.get("doc_type"): f for f, m in scan_mod.adapters(adapter_paths)}
        if doc_type not in found:
            return {**out, "status": "none", "doc_type": doc_type,
                    "reason": f"'{doc_type}'의 어댑터 실물이 소재지에 없다 — "
                              f"`parse run <어댑터> …`로 직접 넣거나 register로 어댑터를 등록한다"}
        return {**out, "status": "chosen", "doc_type": doc_type,
                "adapter": Path(found[doc_type]),
                "basis": {"by": "human", "doc_type": doc_type,
                          "form": form_of(p)}}
    if p.suffix.lower() in PROSE_EXT:
        return {**out, "status": "none",
                "reason": "비정형(pptx) — 헤더 지문이 없어 스캔 대상이 아니다. --doc-type 지정 필수"}
    res = scan_mod.scan(p, adapter_paths)
    cands = res["candidates"]
    out["candidates"] = cands
    if len(cands) == 1:
        dt = cands[0]
        f, _mod = res["_mods"][dt]
        d = next(x for x in res["details"] if x["doc_type"] == dt)
        if registry.schema_of(dt) is None:
            return {**out, "status": "none", "doc_type": dt,
                    "reason": f"지문은 '{dt}'와 유일 일치지만 **등록부에 없다** — "
                              f"인입이 미등록 doc_type을 거부한다(B3). register로 확정하라"}
        rejected = [f"{x['doc_type']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
                    for x in res["details"] if x.get("eligible") and not x.get("candidate")]
        return {**out, "status": "chosen", "doc_type": dt, "adapter": Path(f),
                "basis": {"by": "scan", "doc_type": dt,
                          "match": f"header_labels 완전 일치 {d['matched']}/{d['declared']} "
                                   f"(누락 0 · 잉여 0)",
                          "rejected": rejected, "form": form_of(p)}}
    if len(cands) > 1:
        return {**out, "status": "ambiguous",
                "reason": f"지문이 {len(cands)}개 어댑터와 일치 {cands} — 사람이 --doc-type으로 고른다"}
    # 차이 내역은 **개수만** — 열 이름 전부를 문서마다 늘어놓으면 목록이 읽히지 않는다.
    # 자세한 내역은 `run.py scan <문서>`가 낸다(같은 대조).
    diffs = [f"{x['doc_type']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
             for x in res["details"] if x.get("eligible")]
    return {**out, "status": "none",
            "reason": "지문 일치 0건 — " + (" · ".join(diffs) + " — 상세: run.py scan <문서>"
                                        if diffs else "대조할 정형 어댑터가 없다")}


def _basis_line(sel):
    b = sel.get("basis") or {}
    if b.get("by") == "human":
        out = f"사람 지정 --doc-type {b['doc_type']}"
    elif b.get("by") == "scan":
        out = f"지문 스캔 유일 일치 → {b['doc_type']} · {b['match']}" + (
            f" · 불일치 {b['rejected']}" if b.get("rejected") else "")
    else:
        return "-"
    return out + _form_line(b.get("form"))


def _form_line(f):
    """형태 판정의 화면 한 줄 — **신호값 다섯을 그대로** 싣는다(문서 1 C37).

    요약만 보이면 문턱이 왜 그렇게 갈렸는지 사람이 판단할 재료가 없다. 사람에게
    올라온 문서는 특히 그렇다 — 그가 보고 정할 것이 이 다섯 값이다.
    """
    if not f:
        return ""
    head = f["verdict"] or "**사람 판정 대상**"
    line = f"\n     형태 판정: {head} ({'자동' if f.get('auto') else '자동 아님'}) — {f['why']}"
    if f.get("signals"):
        line += "\n     신호값: " + " · ".join(
            f"{k}={f['signals'][k]}[{(f.get('votes') or {}).get(k, '?')[0]}]"
            for k in form_mod.SIGNALS if k in f["signals"])
    return line


def ingest_file(doc, doc_type=None, dry_run=False, adapter_paths=None, finalize_after=True):
    """문서 1건 — 선택 → 파싱 → 인입. 돌려주는 것은 결과 1행(dict)이다. **예외를 밖으로
    던지지 않는다** — 문서 단위 독립(C14)이라 실패는 행에 적힌다."""
    sel = select(doc, doc_type, adapter_paths)
    row = {"doc": str(doc), "doc_id": sel["doc_id"], "doc_type": sel.get("doc_type"),
           "basis": _basis_line(sel), "status": SKIP, "reason": sel.get("reason")}
    print(f"[투입] {Path(doc).name} → doc_id {sel['doc_id']}")
    if sel["status"] != "chosen":
        print(f"   미선택 — {sel['reason']}")
        return row
    print(f"   선택 근거: {row['basis']}")
    # **판정과 어댑터가 어긋나면 말한다** — 조용히 넘기면 관리계획서가 산문으로,
    # 목차 보고서가 표로 읽히고 그 사실이 어디에도 남지 않는다. 막지는 않는다:
    # 사람이 지정한 doc_type을 판정이 뒤집으면 지정이 무의미해진다(C37은 「어느
    # 갈래로 읽는가」를 정할 뿐 「사람의 지정을 이긴다」고 하지 않는다).
    _f = (sel.get("basis") or {}).get("form") or {}
    _kind = (registry.schema_of(sel["doc_type"]) or {}).get("payload_kind")
    if _f.get("verdict") and _kind and _f["verdict"] != _kind:
        print(f"   ⚠ 형태 판정({_f['verdict']})과 어댑터의 payload_kind({_kind})가 "
              f"어긋난다 — 지정대로 진행하되 이 사실이 인입 기록에 남는다")
    prev = store.read(store.DOC_REGISTRY, {}).get(sel["doc_id"])
    # **경로 전체를 비교한다**(B55 ⑧). 구판은 **파일명**을 비교했는데 doc_id가
    # 파일명 stem 파생이라(D-110) 같은 doc_id면 파일명이 항상 같다 — 조건이 참이 될
    # 수 없어, 「다른 폴더의 같은 이름」이라는 D-110의 **대가**가 화면에 뜬 적이 없다.
    if prev and prev.get("source_path") and _norm_path(prev["source_path"]) != _norm_path(doc):
        print(f"   ⚠ 같은 doc_id가 다른 경로에서 인입된 적 있다({prev['source_path']}) — "
              f"개정(재인입)으로 취급된다(D-110)")
    if dry_run:
        row["status"] = "선택만"
        print("   (dry-run — 파싱·인입 안 함)")
        return row
    try:
        res, out = run_parse(str(sel["adapter"]), sel["doc_id"], str(doc))
        if not res.ok:
            row.update(status=FAIL, reason="파싱 실패 — " + "; ".join(
                f"[{f['kind']}] {f['reason']}" for f in res.failures)[:300])
            print(f"   {row['reason']}")
            return row
        r, m, _extracted = run_document(res.envelope, routing=sel["basis"])
        if r.status == "held":
            row.update(status=FAIL, reason=f"보류 — {r.reason}")
            print(f"   {row['reason']}")
            return row
        # **추출을 다시 돌렸나**를 말한다 — 등록 검수의 리허설이 남긴 체크포인트를
        # 운영이 재사용하면 LLM 호출이 0회다(B51). 그 사실이 화면에 없으면 「리허설과
        # 운영이 같은 함수」가 지켜졌는지 사람이 볼 수 없다.
        row.update(status=OK, reason=f"record {len(r.record_ids)} · chunk {len(r.chunk_ids)}"
                   + (f" · 그래프 노드 {m['nodes']}" if m else "")
                   + ("  [추출 실행]" if _extracted else "  [추출 체크포인트 재사용]"))
        print(f"   인입 — {row['reason']} → {out}")
        if finalize_after:
            finalize()
        return row
    except Exception as e:                       # 문서 단위 독립 — 나머지를 멈추지 않는다
        row.update(status=FAIL, reason=f"{type(e).__name__}: {e}"[:300])
        print(f"   실패 — {row['reason']}")
        return row


def ingest_dir(path, doc_type=None, dry_run=False, adapter_paths=None):
    """경로의 문서를 **하위 폴더 없이** 순회한다(D-110 — 하위 폴더는 별도 투입).

    `--doc-type`을 주면 그 경로 전부를 그것으로 본다(비정형 폴더 단위 지정 — B46).
    """
    p = Path(path)
    if not p.is_dir():
        raise SystemExit(f"[투입] 경로가 아니다: {p}")
    files = sorted(x for x in p.iterdir() if x.is_file() and not x.name.startswith(("~", ".")))
    rows = []
    for f in files:
        rows.append(ingest_file(f, doc_type, dry_run, adapter_paths, finalize_after=False))
    if not dry_run and any(r["status"] == OK for r in rows):
        finalize()                              # 빌드 말미 패스는 전 문서 뒤 1회
    print(summary(rows))
    return rows


def summary(rows):
    """끝에 모아 보이는 목록 — 성공 · 실패 · 미선택 (dry-run은 선택만)."""
    groups = {}
    for r in rows:
        groups.setdefault(r["status"], []).append(r)
    lines = [f"■ 일괄 투입 결과 — {len(rows)}건: " + " · ".join(
        f"{k} {len(v)}" for k, v in groups.items())]
    for k in (OK, "선택만", FAIL, SKIP):
        for r in groups.get(k, []):
            lines.append(f"  [{k}] {Path(r['doc']).name:<24} doc_id {r['doc_id']:<18} "
                         f"{('doc_type ' + r['doc_type']) if r.get('doc_type') else '':<20} "
                         f"{r.get('reason') or ''}")
    return "\n".join(lines)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit(__doc__)
    args = require_live_or_allow(argv, command="ingest")   # mock 관문 (B48)
    dry = "--dry-run" in args
    if dry:
        args.remove("--dry-run")
    dt = None
    if "--doc-type" in args:
        i = args.index("--doc-type")
        dt = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    paths = None
    if "--adapters" in args:
        i = args.index("--adapters")
        paths = [args[i + 1]] if i + 1 < len(args) else None
        del args[i:i + 2]
    if not args:
        raise SystemExit("[투입] 대상(문서 또는 경로)이 없다\n" + __doc__)
    target = Path(args[0])
    if target.is_dir():
        rows = ingest_dir(target, dt, dry, paths)
    else:
        rows = [ingest_file(target, dt, dry, paths)]
        print(summary(rows))
    return 0 if all(r["status"] in (OK, "선택만") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
