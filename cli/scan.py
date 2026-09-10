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

**형태 판정은 다른 판정이다**(문서 1 C37): 여기가 「어느 어댑터인가」라면 그쪽은
「이 문서를 table로 읽을 것인가 prose로 읽을 것인가」다. 두 판정을 한 명령에 두는
것은 **같은 문서를 한 번 읽어 둘 다 답하기** 위해서이지 하나로 합치기 위해서가 아니다.

사용: python cli/scan.py <문서.xlsx> [--adapters 경로...] [--confirm <doc_type>]
      python cli/scan.py --form <문서...|디렉터리>   ← 형태 판정표 (C37)
      (또는 python -m cli.scan ...)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from core import fixtures
from parser.normalizer import _col
from parser.reader import GRID_EXT, read
from parser import form as form_mod

# **등록부가 정본**이다(n6 확정분 — P3). 등록부에 어댑터가 없는 내장 doc_type을 위해
# mock 소재지를 뒤에 둔다 — P트랙 이전의 잔재이고, 등록이 쌓이면 자연히 비어 간다.
# **존재하는 것만 돌려준다** — 구판은 없는 디렉터리를 그대로 glob해 모듈로
# 로드하려다 하드 크래시했다(§2-4 실측). 참조 어댑터는 픽스처이고, 사내에서는
# 없는 것이 정상이다 — 정본 어댑터는 등록부가 가리킨다.
ADAPTER_DIRS = fixtures.dirs(fixtures.ADAPTERS, fixtures.FIXTURE_ADAPTERS)


def _load(path):
    spec = importlib.util.spec_from_file_location(f"scan_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def adapters(paths=None):
    """어댑터 실물 목록 — 경로가 오면 그것만, 없으면 **등록부 + 기본 소재지**.

    등록부가 앞에 온다 — 같은 doc_type이 양쪽에 있으면 등록된 실물이 정본이다.
    """
    from core.registry import adapter_paths
    files = []
    if paths is None:
        files += [p for _dt, p in adapter_paths()]
    for p in (paths or ADAPTER_DIRS):
        p = Path(p)
        files += sorted(p.glob("*.py")) if p.is_dir() else [p]
    out, seen = [], set()
    for f in files:
        if f.stem.startswith("_") or f.resolve() in seen:
            continue
        seen.add(f.resolve())
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
        v = cells.get(f"{_col(col)}{header_row}")
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


# 헤더 지문이 성립하는 **문서 포맷**. 지문은 「헤더 행의 문자열 배열」이라
# 행·열이 있는 포맷에서만 뜻이 있다(파서_명세 §5).
FINGERPRINTABLE = ("xlsx",)


def scan(doc_path, adapter_paths=None):
    """일괄 대조 — 후보 목록을 돌려줄 뿐 **파싱하지 않는다**(자동 라우팅 금지)."""
    raw = read(str(doc_path))
    # **PDF·PPTX는 지문 대상이 아니다**(B53) — 헤더 행이라는 것이 없다. 그대로
    # 대조하면 전 표 어댑터에 대해 「누락 13건」이 줄줄이 떠서, 화면이 「맞는 게
    # 하나도 없다」로 보인다 — 실은 **물어볼 수 없는 질문**을 한 것이다.
    if raw.get("format") not in FINGERPRINTABLE:
        return {"doc": str(doc_path), "details": [], "candidates": [],
                "not_fingerprintable": raw.get("format"), "_mods": {}}
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
    if res.get("not_fingerprintable"):
        raise SystemExit(f"[scan] {res['not_fingerprintable']}는 지문 대상이 아니다 — "
                         f"확정할 지문이 없다. doc_type 지정 투입 또는 --use-basic 등록이다")
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
    fmt = res.get("not_fingerprintable")
    if fmt:
        lines.append(f"  · {fmt} — **지문 대상이 아니다.** 헤더 행이 없는 포맷이라")
        lines.append("    대조할 것이 없다(비정형). doc_type을 지정해 투입하거나,")
        lines.append("    기본 어댑터로 등록한다: register generate <이름> <층> <표본> --use-basic")
        return "\n".join(lines)
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


def form_table(docs):
    """형태 판정표 — **신호값 다섯을 그대로** 보인다 (문서 1 C37 · 문서 6 §6.4).

    요약만 보이면 문턱이 왜 그렇게 갈렸는지 사람이 판단할 재료가 없다. 이 화면이
    문턱 조정의 재료이자, 사람에게 올라온 문서를 사람이 정하는 자리다.
    """
    rows = []
    for d in docs:
        p = Path(d)
        if p.is_dir():
            rows += [x for x in sorted(p.iterdir())
                     if x.suffix.lower() in GRID_EXT]
        elif p.suffix.lower() in GRID_EXT:
            rows.append(p)
    out = ["■ 형태 판정 — table이냐 prose냐 (결정적 · LLM 0 — 문서 1 C37)",
           f"   문턱 {json.dumps(form_mod.THRESHOLDS, ensure_ascii=False)}",
           f"   자동 조건: 찬성 ≥{form_mod.AUTO_MIN_FOR} · 반대 "
           f"{form_mod.AUTO_MAX_AGAINST} — 그 외는 **사람**",
           "",
           f"   {'문서':24}{'판정':8}{'자동':6}" + "".join(f"{k:>19}" for k in form_mod.SIGNALS)]
    # **문서마다 한 번만 판정한다** — 집계에서 다시 부르면 같은 파일을 몇 번씩
    # 읽는다(실측: CSV 리더 로그가 4회씩 찍혔다). 판정은 결정적이라 결과가
    # 달라지지는 않지만, 재는 일에 값을 치를 이유가 없다.
    judged = [(p, form_mod.judge(read(str(p)))) for p in rows]
    for p, r in judged:
        sg, v = r["signals"], r["votes"]
        out.append(f"   {p.name:24}{(r['verdict'] or '사람'):8}"
                   f"{('예' if r['auto'] else '**아니오**'):6}"
                   + "".join(f"{str(sg[k]) + '[' + v[k][0] + ']':>19}"
                             for k in form_mod.SIGNALS))
    out += ["", f"   {len(judged)}건 — " + " · ".join(
        f"{k}: {sum(1 for _p, r in judged if (r['verdict'] or '사람') == k)}건"
        for k in ("table", "prose", "사람"))]
    return "\n".join(out)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "--form":
        print(form_table(argv[1:] or [ROOT / "tests" / "fixtures" / "raw"]))
        return
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
