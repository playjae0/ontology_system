# -*- coding: utf-8 -*-
"""칸 0.3 — **문서 끝 결과표**의 화면 (B99 ⑤) — 재료는 `core/build/result.collect` 하나다.

인입 끝(문서마다) · 일괄 투입 끝(문서별 한 줄 + 전체 합) · `show report <doc_id>`가 같은 함수를 쓴다.
화면이 제 계산을 하지 않는다 — 결과 묶음의 값을 줄로 옮길 뿐이다.
"""
from __future__ import annotations

from cli import _screen


def _kinds(d):
    return " · ".join(f"{k} {n:,}" for k, n in sorted((d or {}).items())) or "0"


def lines(res):
    """결과 묶음 → 화면 줄들(들여쓰기 포함)."""
    if not res:
        return []
    hold = res.get("보류") or {}
    out = [f"   결과 — 값 {res['값']:,} → 사전 연결 {res['사전 연결']:,} · LLM 연결 {res['LLM 연결']:,} · "
           f"새 노드 {res['새 노드']:,} · 불확실 {res['불확실']:,} · 보류 {sum(hold.values()):,}"
           + (f"({_kinds(hold)})" if hold else "")]
    if res.get("관계 버림"):
        out.append("     관계 버림(관문) — " + " · ".join(f"{t} {n:,}" for t, n in res["관계 버림"]))
    for lay, d in sorted((res.get("층") or {}).items()):
        out.append(f"     층 {lay} — 노드 {d['노드']:+,}(auto {d['auto']:+,}) · 엣지 {d['엣지']:+,}")
    out.append(f"     큐 — 이번 실행 {_kinds(res.get('큐 이번'))} · 이전 실행이 남긴 것 "
               f"{_kinds(res.get('큐 이전'))}")
    for pt, u in sorted((res.get("LLM") or {}).items()):
        out.append(f"     LLM {pt} — 호출 {u['calls']:,} · 입력 {u['prompt']:,} · 출력 {u['completion']:,} · "
                   f"1회 평균 {u['avg']:,} · 1회 최대 {u['max']:,}")
    return out


def show(res):
    for ln in lines(res):
        _screen.say(ln, "head" if ln.startswith("   결과") else None)


def batch(rows):
    """일괄 투입 끝 — 문서별 한 줄 + 전체 합(층별 합 · 지점별 합)."""
    from core.build.result import totals
    got = [r for r in rows if r.get("result")]
    if not got:
        return
    _screen.say("   문서별 결과", "head")
    tn = te = 0
    calls = {}
    for r in got:
        res = r["result"]
        n, e, _a = totals(res)
        tn, te = tn + n, te + e
        c = sum(u["calls"] for u in (res.get("LLM") or {}).values())
        for pt, u in (res.get("LLM") or {}).items():
            calls[pt] = calls.get(pt, 0) + u["calls"]
        print(f"     {r['doc_id']:<20} 값 {res['값']:,} · 새 노드 {res['새 노드']:,} · 불확실 "
              f"{res['불확실']:,} · 보류 {sum((res.get('보류') or {}).values()):,} · 노드 {n:+,} · "
              f"엣지 {e:+,} · LLM 호출 {c:,}")
    print(f"     전체 — 문서 {len(got):,} · 노드 {tn:+,} · 엣지 {te:+,} · LLM 호출 "
          + (" · ".join(f"{pt} {n:,}" for pt, n in sorted(calls.items())) or "0"))
