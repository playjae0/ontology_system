# -*- coding: utf-8 -*-
"""n9 지문 스캔 — doc_type 미지정 **정형** 문서의 후보 제안 (파서_명세 §5 · 카드 C15).

    문서 헤더 지문 ↔ 어댑터 expects.header_labels 일괄 대조 (결정적 — LLM 아님)
    → 후보 목록(일치 내역 포함) → **사람 확정(CLI 1클릭)** → 그때부터 파싱

**유일 일치여도 자동 라우팅하지 않는다**(P7 — 오배정률 측정 후 승격). 비정형(prose)
어댑터는 헤더 지문의 변별력이 없어 대조 대상이 아니다 — 지정 필수.

대조는 preflight와 같은 연산의 재사용이다: 어댑터가 선언한 header_row의 실물
헤더 문자열을 header_labels와 맞춰 본다. **스캔은 어떤 데이터도 쓰지 않는다.**

어댑터 소재지: 등록부(P3 n6)가 서기 전에는 CLI 인자·기본 소재지 목록이 그 자리를
대신한다. 등록부가 서면 registry의 expects가 정본이 된다.

사용: python cli/scan.py <문서.xlsx> [--adapters 경로...] [--confirm <doc_type>]
      (또는 python run.py scan ...)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser.reader import read                          # noqa: E402

# 등록부 이전의 어댑터 소재지 (P3 후 registry가 정본)
ADAPTER_DIRS = [ROOT / "mock" / "adapters", ROOT / "mock" / "fixtures" / "adapters"]


def _load(path):
    spec = importlib.util.spec_from_file_location(f"scan_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def adapters(paths=None):
    """어댑터 실물 목록 — 경로가 오면 그것만, 없으면 기본 소재지를 전부 훑는다."""
    files = []
    for p in (paths or ADAPTER_DIRS):
        p = Path(p)
        files += sorted(p.glob("*.py")) if p.is_dir() else [p]
    out = []
    for f in files:
        if f.stem.startswith("_"):
            continue
        mod = _load(f)
        if isinstance(getattr(mod, "ADAPTER", None), dict):
            out.append((f, mod))
    return out


def _header_actual(raw, header_row):
    """그 행의 실물 헤더 문자열 배열 — preflight가 보는 것과 같은 지문."""
    if raw.get("format") != "xlsx" or not raw.get("sheets"):
        return []
    cells = raw["sheets"][0]["cells"]
    out = []
    for col in range(1, raw["sheets"][0]["max_col"] + 1):
        s = ""
        n = col
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        v = cells.get(f"{s}{header_row}")
        if v is not None and str(v).strip():
            out.append(str(v).strip())
    return out


def match_detail(raw, mod):
    """어댑터 1개와의 대조 내역 — 후보 판정은 **완전 일치**(누락 0·잉여 0)다."""
    a = mod.ADAPTER
    if a.get("payload_kind") != "table":
        return {"doc_type": a.get("doc_type"), "eligible": False,
                "note": "비정형(prose) — 헤더 지문 대상 아님(지정 필수)"}
    exp = a.get("expects", {})
    declared = exp.get("header_labels") or []
    hr = exp.get("header_row")
    if not declared or not hr:
        return {"doc_type": a.get("doc_type"), "eligible": False,
                "note": "expects에 header_labels/header_row 없음 — 대조 불가"}
    actual = _header_actual(raw, hr)
    missing = [h for h in declared if h not in actual]
    extra = [h for h in actual if h not in declared]
    return {"doc_type": a.get("doc_type"), "eligible": True,
            "declared": len(declared), "matched": len(declared) - len(missing),
            "missing": missing, "extra": extra,
            "candidate": not missing and not extra}


def scan(doc_path, adapter_paths=None):
    """일괄 대조 — 후보 목록을 돌려줄 뿐 **파싱하지 않는다**(자동 라우팅 금지)."""
    raw = read(str(doc_path))
    details, mods = [], {}
    for f, mod in adapters(adapter_paths):
        d = match_detail(raw, mod)
        d["adapter_path"] = str(f)
        details.append(d)
        mods[d["doc_type"]] = (f, mod)
    return {"doc": str(doc_path),
            "details": details,
            "candidates": [d["doc_type"] for d in details if d.get("candidate")],
            "_mods": mods}


def confirm(doc_path, doc_type, adapter_paths=None):
    """사람 확정 후에만 여기로 온다 — 이후는 preflight부터의 정상 경로다."""
    res = scan(doc_path, adapter_paths)
    if doc_type not in res["_mods"]:
        raise SystemExit(f"[scan] '{doc_type}' 어댑터를 소재지에서 찾지 못했다")
    f, mod = res["_mods"][doc_type]
    detail = next(d for d in res["details"] if d["doc_type"] == doc_type)
    if not detail.get("candidate"):
        raise SystemExit(f"[scan] '{doc_type}'은 지문 불일치다 — 확정 거부 "
                         f"(누락 {detail.get('missing')} · 잉여 {detail.get('extra')}). "
                         f"양식 표류면 어댑터 개정, 새 양식이면 신규 doc_type 등록이다 (C15)")
    pieces = mod.extract(read(str(doc_path)))
    return res, pieces


def render(res):
    lines = [f"지문 스캔 — {res['doc']}"]
    for d in res["details"]:
        if not d["eligible"]:
            lines.append(f"  · {d['doc_type']:<12} 대상 아님 — {d['note']}")
            continue
        mark = "◎ 후보" if d["candidate"] else "  불일치"
        lines.append(f"  {mark} {d['doc_type']:<12} 일치 {d['matched']}/{d['declared']}"
                     + (f" · 누락 {d['missing']}" if d["missing"] else "")
                     + (f" · 잉여 {d['extra']}" if d["extra"] else ""))
    if res["candidates"]:
        lines.append(f"  → 후보 {res['candidates']} — 확정은 사람 몫이다: "
                     f"--confirm <doc_type> (유일 일치여도 자동 라우팅하지 않는다 — P7)")
    else:
        lines.append("  → 후보 없음 — 신규 doc_type 등록(구축 모드) 또는 지정 투입 대상")
    return "\n".join(lines)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    doc = argv[0]
    paths, confirm_to = [], None
    it = iter(argv[1:])
    for a in it:
        if a == "--adapters":
            pass
        elif a == "--confirm":
            confirm_to = next(it, None)
        else:
            paths.append(a)
    if confirm_to:
        res, pieces = confirm(doc, confirm_to, paths or None)
        print(render(res))
        print(f"\n[확정] doc_type={confirm_to} — 정상 파싱 {len(pieces)} record")
        print(f"  [조각 1 표본] {json.dumps(pieces[0], ensure_ascii=False)[:200]}")
    else:
        print(render(scan(doc, paths or None)))


if __name__ == "__main__":
    main(sys.argv[1:])
