# -*- coding: utf-8 -*-
"""칸 0.3 — `show report <doc_id>` — **행별 판정 대장** + 문서 끝 결과표 · 보류 목록 · 불확실 목록 (B74 ④ · B99 ⑤).

재료는 인입이 남긴 대장(`<상태>/work/ingest_log/<doc_id>.json` · ④단)과 그 파일에 붙은 결과
묶음(`core/build/result.collect`)이다 — **여기서 새로 세지 않는다.** `cli/show.py`에서 떼어냈다
(그 파일이 800행을 넘는다 · B99 ⑤).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from cli import _screen
from core import paths
from core.build import ledger
from core.state import store


def cmd_report(args):
    """**행별 판정 대장** — 사람이 문서를 옆에 놓고 정합성을 행 단위로 본다 (B74 ④).

    평가의 단위가 행이다: 「몇 개가 로직이고 몇 개가 LLM인가」도, 「이 칸의 값이
    어디에 붙었나」도 합계로는 답해지지 않는다. 재료는 인입이 남긴 대장
    (`<상태>/work/ingest_log/<doc_id>.json` · ④단)이고 **여기서 새로 세지 않는다.**
    """
    if "--diff" in args:
        return _report_diff([a for a in args if a != "--diff"])
    if not args:
        raise SystemExit("doc_id를 달라: run.py show report CP01")          # [사용법]
    doc = args[0]
    as_json = "--json" in args
    data = ledger.read(doc)
    if data is None:
        _refuse_no_ledger(doc)
    rows = data.get("rows") or []
    if "--trace" in args:
        return _trace(doc, rows)
    if "--md" in args:                           # 잘리지 않는 보고서 — ⑤파생 export/ (B123 ①)
        from cli import report_md
        print(f"■ {doc} 인입 보고서 — 칸 전부(잘림 0) · 요약 · 맞춤 · 카테고리 쌍별 연결 · 추출 청크 · 판정 값")
        print(f"  보고서 {paths.show(report_md.write(doc, data))}")
        return 0
    if as_json:
        print(json.dumps({"doc_id": doc, "rows": rows,
                          "summary": ledger.summary(rows)},
                         ensure_ascii=False, indent=1))
        return 0
    su = ledger.summary(rows)
    kinds = Counter(r.get("role") for r in rows)
    print(f"■ {doc} 판정 대장 — 행 {len(rows)}건 "
          f"(entity {kinds.get('entity', 0)} · anchor {kinds.get('anchor', 0)} · "
          f"부착 {kinds.get('attribute', 0) + kinds.get('content', 0) + kinds.get('attach', 0)})")
    print(f"  값 {su['값']} · 사전 {su['사전']} · 스코프→판정 {su['스코프']} · "
          f"임베딩→판정 {su['임베딩']} · 겹침→판정 {su['겹침']} · 신규 {su['신규']} · "
          f"불확실 {su['불확실']} · 보류 {su['보류']} · LLM 호출 {su['호출']} · "
          f"토큰 {su['토큰']}")
    print("\n  " + _screen.pad("locator", 18) + _screen.pad("필드", 12)
          + _screen.pad("표기 → canonical", 46) + _screen.pad("경로", 15)
          + _screen.pad("판정", 11) + "큐")
    for r in rows:
        left = (r.get("surface") or "—")
        right = r.get("canonical") or "—"
        nid = (r.get("node_id") or "")[:6]
        arrow = f"{left} → {right}" + (f" ({nid})" if nid else "")
        print("  " + _screen.pad(r.get("locator") or "—", 18)
              + _screen.pad(r.get("field") or "—", 12) + _screen.pad(_screen.cut(arrow, 44), 46)
              + _screen.pad(r.get("path"), 15) + _screen.pad(r.get("verdict"), 11)
              + (r.get("queue_kind") or ""))
    _report_extra(data, rows)                    # 결과표 · 보류 · 불확실 (B99 ⑤⑨)
    return 0


def _report_diff(args):
    """두 대장의 **다른 행만** 본다 — 설정을 바꿔 넣은 두 산출의 비교 (B75 ①).

    비교 단위는 값이다(`locator · 필드 · 표기`). **다름의 기준은 판정과 node**이지
    경로가 아니다 — 경로는 「무엇으로 골랐나」이고, 그것이 달라도 답이 같으면
    그 값에서 임베딩과 겹침의 차이는 없었다는 뜻이다. 어느 쪽이 맞는지는 사람이
    본다 — 도구는 차이만 보인다.

    **node의 동일성은 canonical로 본다** — 의미 축 id는 ULID라 클린 재실행마다
    다르고(문서 7 §7.2), 그것을 비교하면 **전 행이 다르다**고 나온다. 사람이
    「같은 것에 붙었나」를 묻는 단위는 이름이다.
    """
    if len(args) < 2:
        raise SystemExit(                                                # [사용법]
            "두 대장을 달라: run.py show report --diff a.json b.json\n"
            "  (각각 run.py show report <doc_id> --json > a.json 으로 만든다)")
    a, b = (_load_ledger_json(x) for x in args[:2])

    def key(r):
        return (r.get("locator"), r.get("field"), r.get("surface"))

    ai = {key(r): r for r in a["rows"]}
    bi = {key(r): r for r in b["rows"]}
    keys = list(ai) + [k for k in bi if k not in ai]
    diff = [k for k in keys
            if (ai.get(k) or {}).get("verdict") != (bi.get(k) or {}).get("verdict")
            or _node_of(ai.get(k)) != _node_of(bi.get(k))]
    ta = sum(_tok(r) for r in a["rows"])
    tb = sum(_tok(r) for r in b["rows"])
    print(f"■ 판정 대장 비교 — 다른 행 {len(diff)} / 전체 {len(keys)} · "
          f"토큰 {ta:,} vs {tb:,}")
    print(f"  A {args[0]}  ·  B {args[1]}")
    if not diff:
        print("\n  다른 행 없음 — 두 설정이 같은 답을 냈다(비용만 다르다).")
        return 0
    print("\n  " + _screen.pad("locator", 16) + _screen.pad("필드", 11) + _screen.pad("표기", 22)
          + _screen.pad("A 경로 · 판정 · node · 후보", 50) + "B 경로 · 판정 · node · 후보")
    for k in diff:
        print("  " + _screen.pad(k[0] or "—", 16) + _screen.pad(k[1] or "—", 11)
              + _screen.pad(_screen.cut(k[2] or "—", 20), 22)
              + _screen.pad(_side(ai.get(k)), 50) + _side(bi.get(k)))
    return 0


def _node_of(r):
    """비교용 노드 동일성 — canonical이 정본이고 없으면 id다(ULID는 실행마다 다르다)."""
    if not r:
        return None
    return r.get("canonical") or r.get("node_id")


def _side(r):
    if not r:
        return "(없음)"
    return (f"{r.get('path')} · {r.get('verdict')} · "
            f"{_screen.cut(_node_of(r) or '—', 18)} · 후보 {r.get('candidates_n', 0)}")


def _tok(r):
    u = r.get("llm") or {}
    return int(u.get("in_tokens") or 0) + int(u.get("out_tokens") or 0)


def _load_ledger_json(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"[대장] 파일이 없다: {p}\n"                      # [상태]
                         f"  ▶ 다음 줄 — 대장을 파일로 낸다: "
                         f"python run.py show report <doc_id> --json > {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    if "rows" not in d:
        raise SystemExit(f"[대장] 행이 없는 파일이다: {p}\n"                # [상태]
                         f"  ▶ 다음 줄 — 대장을 파일로 낸다: "
                         f"python run.py show report <doc_id> --json > {p}")
    return d


def _refuse_no_ledger(doc):
    """대장이 없다 — **원인 + 그대로 칠 수 있는 다음 줄**(B61 계약)."""
    meta = store.read(store.DOC_REGISTRY, {}).get(doc)
    src = (meta or {}).get("source_path")
    dt = (meta or {}).get("doc_type")
    # **대장의 자리는 store가 안다**(B86 ③) — 구판은 레포의 옛 ③단 자리를 문면에 적고
    # **대장 수도 거기서 셌다**(B78 1b에 ④단 `work/`로 옮겼다 — 늘 0건이었다).
    _dir = store.path(ledger.DIR)
    _n = len(list(_dir.glob("*.json"))) if _dir.exists() else 0
    raise SystemExit(                                                    # [상태] 문면=_refuse_no_ledger
        f"[대장] '{doc}'의 판정 대장이 없다 — {paths.show(store.path(ledger.name_of(doc)))} "
        f"(인입 기록은 {'있다' if meta else '없다'} · 대장 파일 {_n}건)\n"
        + (f"  ▶ 다음 줄 — 그 문서를 다시 넣으면 대장이 생긴다: "
           f"python run.py ingest-file {src} --doc-type {dt}"
           if meta and src and dt else
           "  ▶ 다음 줄 — 인입된 문서를 먼저 본다: python run.py show doc"))


def _report_extra(data, rows):
    """결과표(인입 끝과 같은 줄) · 보류 목록(사유별 · 표기 · 행 수) · 불확실 목록(가장 가까운 후보)."""
    from cli import result_screen
    from core.build.result import hold_reason
    if data.get("result"):
        print("")
        result_screen.show(data["result"])
        _by = sum(1 for r in rows if r.get("by") == "retry")
        if _by:                                     # 결과표는 인입 끝의 것 · 맞춤표는 지금 대장 (B113 ③)
            print(f"     (인입 뒤 재연결이 고친 행 {_by:,} — 위 「결과」는 인입 끝의 것 · 아래 맞춤 묶음은 지금 대장)")
        from core.build import reconcile
        result_screen.show_reconcile(reconcile.for_report(data.get("doc_id") or (rows[0].get("doc_id") if rows else ""),
                                                          data))    # 맞춤표 — 인입 끝과 같은 함수 (B112 ①)
    for ln in hold_unc_lines(rows, doc=data.get("doc_id")):
        print(ln)


def _hold_coord(r, by_loc):
    """보류 행의 좌표 — 좌표 행이면 그 표기 자체 · 아니면 그 조각의 좌표(없으면 「좌표 없음」) (B112 ④ ·
    `reconcile.row_coord` 하나 — 문서 좌표 경고와 같은 함수)."""
    from core.build.reconcile import row_coord
    co = row_coord(r, by_loc)
    if r.get("role") == "anchor" and co:
        return f"{co}(이 표기가 좌표)"
    return co or "좌표 없음"


def hold_unc_lines(rows, limit=None, doc=None):
    """보류 목록(**사유 → 좌표 → 표기 · 행 수** — B112 ④: 좌표가 없어서 멈춘 것임을 줄이 말한다) · 불확실 목록(가장
    가까운 후보) — `show report`와 인입 끝이 같은 함수(B102 ⑦). 좌표는 파싱 봉투의 조각에서(`doc` — 없으면 「좌표 없음」).
    `limit`이면 목록마다 그 줄까지 · 넘으면 「… 외 n — 전체는 show report」."""
    from core.build.result import hold_reason
    out = []
    by_loc = {}
    _pp = paths.parsed(f"{doc}.json") if doc else None
    if _pp is not None and _pp.exists():
        from core.build.reconcile import by_locator
        by_loc = by_locator(json.loads(_pp.read_text(encoding="utf-8")))
    held = Counter((hold_reason(r), _hold_coord(r, by_loc), r.get("surface") or r.get("canonical") or "(표기 없음)")
                   for r in rows if hold_reason(r))
    if held:
        out.append("")
        out.append("  보류 목록 — 사유 → 좌표 → 표기 · 행 수")
        items = sorted(held.items(), key=lambda x: (x[0][0], x[0][1], -x[1], x[0][2]))
        why0 = None
        for (why, co, s_), n in items[:limit]:
            if why != why0:
                out.append(f"    {why} — {sum(v for k, v in held.items() if k[0] == why):,}행")
                why0 = why
            out.append(f"      {_screen.pad(_screen.cut(co, 30), 32)}{_screen.pad(_screen.cut(s_, 40), 42)}{n:,}")
        if limit is not None and len(items) > limit:
            out.append(f"    … 외 {len(items) - limit:,}")
    unc = [r for r in rows if r.get("verdict") in ("uncertain", "lowres")]
    if unc:
        out.append("")
        out.append("  불확실 목록 — 표기 · 가장 가까운 후보(판정 · 임베딩 상위)")
        for r in unc[:limit]:
            near = r.get("nearest") or {}
            tops = " · ".join(f"{c.get('canonical')} {c.get('score', 0):.2f}"
                              for c in near.get("top") or [])
            out.append(f"    {_screen.pad(_screen.cut(r.get('surface') or '—', 30), 32)}"
                       f"{near.get('by') or '—'}: {near.get('canonical') or '—'}"
                       + (f" · 상위 {tops}" if tops else ""))
        if limit is not None and len(unc) > limit:
            out.append(f"    … 외 {len(unc) - limit:,}")
    return out


def _coord_src(meta):
    """조각 좌표의 출처 — 문서 좌표 · 제목·시트 · 학습 · 태깅 · 자기."""
    m = meta or {}
    if m.get("coord_from_doc"):
        return "문서 좌표"
    if m.get("coord_tag_source") == "scope":            # 원 표기가 공유 별칭이었다 (B104 ①)
        return ("제목·시트 · " if m.get("coord_from_section") else "") + f"공유 별칭 범위 안({m.get('coord_tag_from')})"
    if m.get("coord_from_section"):
        return "제목·시트"
    if m.get("coord_tag_source") == "learned":
        return "학습"
    if m.get("coord_tag_source"):
        return "태깅"
    return "자기"


def _trace(doc, rows, span=40):
    """**값마다 추적**(B102 ⑦ · `show report <doc_id> --trace`) — 위치 · 표기 → 붙은 노드 · 붙은 자리(관계 ·
    상대) · 좌표(출처) · 근거 문장(표기 앞뒤 ±40자 · 그림 요약이면 표시). 재료는 대장과 청크 저장소(새 계산 0)."""
    from core.state import store
    from core.state.ids import fold_latin
    ch = store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}
    by_loc = {c.get("source_locator"): c for c in ch.values() if c.get("doc_id") == doc}
    # 소속 — 이름 → 대상(종류) → 결과 (B112 ④ · 맞춤표와 같은 재료 · 같은 함수)
    from core.build import reconcile
    _mt = reconcile.for_report(doc, {"rows": rows, "result": {}})
    _sk = reconcile.skeleton_names()
    print(f"■ {doc} 값 추적 — entity {sum(1 for r in rows if r.get('role') == 'entity'):,}행")
    for r in rows:
        if r.get("role") != "entity":
            continue
        c = by_loc.get(r.get("locator")) or {}
        m = c.get("meta") or {}
        tgt = r.get("target") or r.get("canonical") or "—"
        print(f"\n  {r.get('locator') or '—'} · {r.get('surface')} → {tgt}  [{r.get('verdict')} · {r.get('path')}"
              + (f" · 소속 출처 {r['from']}" if r.get("from") else "") + "]")
        for a in r.get("attached") or []:
            print(f"     붙은 자리  {a.get('rel')} {a.get('dir')} {a.get('other')} ({a.get('path')})")
        if not r.get("attached"):
            print(f"     붙은 자리  없음" + (f" — 큐 {r['queue_kind']}" if r.get("queue_kind") else ""))
        _bt = reconcile.belongs_trace(r, _mt["소속 이름"], _sk, _mt["고아"], _mt.get("제목 개체"))
        if _bt:
            print(f"     소속       {_bt}")
        from parser.normalizer import coord_text
        print(f"     좌표       {coord_text(c.get('process_ref')) or '없음'} ({_coord_src(m)})")
        text = c.get("text") or ""
        if text and r.get("surface"):
            low = fold_latin(text)
            i = low.find(fold_latin(r["surface"]))
            frag = (text[max(0, i - span): i + len(r["surface"]) + span].replace("\n", " ")
                    if i >= 0 else "(본문에 글자 그대로 없음)")
            pic = " · 그림 요약" if (m.get("shape_kind") == "picture" or c.get("image_ref")) else ""
            print(f"     근거       …{frag}…{pic}")
    return 0

