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

# reader가 여는 포맷 — 그 밖은 「지원 밖」으로 목록에만 남긴다
SUPPORTED = (".xlsx", ".xlsm", ".pptx", ".csv", ".tsv")
PROSE_EXT = (".pptx",)                    # 헤더 지문이 없는 포맷 — 지정 필수

OK, FAIL, SKIP = "성공", "실패", "미선택"


def doc_id_of(path):
    """**같은 문서는 항상 같은 doc_id** (재인입 계약) — 파일명 stem, 공백은 `_`.

    경로는 넣지 않는다 — 폴더를 옮겨도 같은 문서다(D-110). 대신 **다른 폴더의 같은
    이름은 같은 문서로 취급된다** — 그 경우 인입은 「개정」으로 돌고, 이 명령은 등록
    대장의 `source_path`가 다르면 화면에 경고한다.
    """
    return re.sub(r"\s+", "_", Path(path).stem.strip())


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
                "basis": {"by": "human", "doc_type": doc_type}}
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
                          "rejected": rejected}}
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
        return f"사람 지정 --doc-type {b['doc_type']}"
    if b.get("by") == "scan":
        return f"지문 스캔 유일 일치 → {b['doc_type']} · {b['match']}" + (
            f" · 불일치 {b['rejected']}" if b.get("rejected") else "")
    return "-"


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
    prev = store.read(store.DOC_REGISTRY, {}).get(sel["doc_id"])
    if prev and prev.get("source_path") and Path(prev["source_path"]).name != Path(doc).name:
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
        r, m, _ex = run_document(res.envelope, routing=sel["basis"])
        if r.status == "held":
            row.update(status=FAIL, reason=f"보류 — {r.reason}")
            print(f"   {row['reason']}")
            return row
        row.update(status=OK, reason=f"record {len(r.record_ids)} · chunk {len(r.chunk_ids)}"
                   + (f" · 그래프 노드 {m['nodes']}" if m else ""))
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
