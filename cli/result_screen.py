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
    out = [f"   결과 — 값 {res['값']:,} → 사전 연결 {res['사전 연결']:,} · 경로 연결 {res.get('경로 연결', 0):,} · "
           f"LLM 연결 {res['LLM 연결']:,} · "
           f"새 노드 {res['새 노드']:,} · 불확실 {res['불확실']:,} · 보류 {sum(hold.values()):,}"
           + (f"({_kinds(hold)})" if hold else "")]
    if res.get("관계 버림"):
        out.append("     관계 버림(관문) — " + " · ".join(f"{t} {n:,}" for t, n in res["관계 버림"]))
    for lay, d in sorted((res.get("층") or {}).items()):
        out.append(f"     층 {lay} — 노드 {d['노드']:+,}(auto {d['auto']:+,}) · 엣지 {d['엣지']:+,}")
    out.append(f"     큐 — 이번 실행 {_kinds(res.get('큐 이번'))} · 이전 실행이 남긴 것 "
               f"{_kinds(res.get('큐 이전'))}")
    # 동의어 학습(B101 ①②④) — 판정이 사전을 키운 만큼 · 가드 · 좌표 학습 (옛 대장엔 키가 없다 — 그때는 줄도 없다)
    if "같은 문서 auto 매칭" in res:
        cl = res.get("좌표 학습") or {}
        out.append(f"     동의어 — 같은 문서 auto에 매칭 {res['같은 문서 auto 매칭']:,} · "
                   f"가드로 내려간 것 {res.get('가드(다른 문서 auto)', 0):,}(다른 문서 auto) · "
                   f"이번 실행이 사전에 더한 별칭 {res.get('LLM 별칭', 0):,}(LLM 매칭) · "
                   f"좌표 학습 새로 {cl.get('새로', 0):,} · 적중 {cl.get('적중', 0):,}")
    if "엣지 없는 노드" in res:                      # 붙은 곳 끝 요약 (B102 ⑦)
        at = res.get("부착") or {}
        so = " · ".join(f"{k[3:]} {v:,}" for k, v in sorted(at.items()) if k.startswith("소속 "))
        out.append(f"     부착 — 소속({so or '0'}) · 관계 {at.get('관계', 0):,} · 좌표 폴백 {at.get('폴백', 0):,} · "
                   f"보류 {at.get('보류', 0):,} · 엣지 없는 노드 {res['엣지 없는 노드']:,}")
        if res.get("소속 없음 비율"):
            out.append("     소속 없음 비율 — " + " · ".join(
                f"{w} {a:,}/{n:,}" for w, a, n in res["소속 없음 비율"]))
        bo = res.get("본문에 없는 개체") or {}
        if bo.get("n"):
            out.append(f"     청크 본문에 글자 그대로 없는 개체 {bo['n']:,} · 그림 요약에서 {bo.get('그림', 0):,}")
    out += _screen.usage_table_lines(table_of(res), "LLM 끝 표(이 문서)")
    return out


def table_of(res):
    """결과 묶음의 끝 표 줄 — `LLM 갈래`(B139 ⑤) · 그 키가 없는 옛 대장은 지점별(`LLM`)을 갈래 = 지점으로."""
    if "LLM 갈래" in (res or {}):
        return res["LLM 갈래"]
    rows = [{"갈래": pt, "지점": pt, "calls": u["calls"], "prompt": u["prompt"], "completion": u["completion"]}
            for pt, u in ((res or {}).get("LLM") or {}).items()]
    tot = sum(o["prompt"] + o["completion"] for o in rows)
    return [{**o, "몫": round(100.0 * (o["prompt"] + o["completion"]) / tot, 1) if tot else None} for o in rows]


def show(res):
    for ln in lines(res):
        _screen.say(ln, "head" if ln.startswith("   결과") else None)


def batch(rows):
    """일괄 투입 끝 — 문서별 한 줄(호출 · 입력 · 출력) + 전체 합(층별 합) + 끝 표(이 실행의 갈래 전부 · B139 ⑤)."""
    from core.build.result import totals
    got = [r for r in rows if r.get("result")]
    if not got:
        return
    _screen.say("   문서별 결과", "head")
    from core.llm import gateway
    tn = te = 0
    for r in got:
        res = r["result"]
        n, e, _a = totals(res)
        tn, te = tn + n, te + e
        u = [sum(x[k] for x in table_of(res)) for k in ("calls", "prompt", "completion")]
        print(f"     {r['doc_id']:<20} 값 {res['값']:,} · 새 노드 {res['새 노드']:,} · 불확실 "
              f"{res['불확실']:,} · 보류 {sum((res.get('보류') or {}).values()):,} · 노드 {n:+,} · "
              f"엣지 {e:+,} · LLM 호출 {u[0]:,} · 입력 {u[1]:,} · 출력 {u[2]:,}")
    print(f"     전체 — 문서 {len(got):,} · 노드 {tn:+,} · 엣지 {te:+,}")
    for ln in _screen.usage_table_lines(gateway.usage_table(), "LLM 끝 표(이 배치 — 문서 밖 호출 포함)"):
        print(ln)


# ---------------------------------------------------------------- 맞춤표 (B112 ①④⑤)
def _formula(ln):
    cells = " + ".join(f"{k} {n:,}" + (f"({d})" if d else "") for k, n, d in ln["칸"])
    return f"{ln['줄']} {ln['전체']:,} = {cells}" + (f"  ({ln['덧']})" if ln.get("덧") else "")


def reconcile_lines(mt, limit=None):
    """맞춤표 묶음(`core/build/reconcile.table`) → 줄들. 같은 단위의 칸 합이 전체와 다르면 그 줄 아래 `[결함]`.
    `limit`이면 엣지 없는 노드 목록을 그 줄까지(전체는 `show report`)."""
    if not mt:
        return []
    from core.build import reconcile as RC
    out = []
    if mt.get("요약"):                     # 문서 한 줄 요약(B118 ① — 아래 맞춤표의 같은 수)
        out.append("   요약 — " + RC.summary_text(mt["doc_id"], mt["요약"]))
    out.append("   맞춤 — 줄마다 단위 · 같은 단위는 합 = 전체")
    for ln in mt["줄"]:
        out.append("     " + _formula(ln))
        if not ln["맞음"]:
            out.append(f"     [결함] {ln['줄'].strip()} 합 {ln['합']:,} ≠ 전체 {ln['전체']:,}")
    k, ex, sim = mt.get("소유자") or (0, [], 0)
    if k or sim:                           # 같은 이름 · 다른 소유자(B142 ⑥ — 전체 목록은 show report --md · 합칠 것이면 ops merge)
        out.append(f"     같은 이름 · 다른 소유자 — 새 노드 중 같은 공정 줄기의 다른 소유자 아래 같은 이름이 있는 것 {k:,}"
                   + (f"(예 {' · '.join(ex)})" if ex else "") + f" · 소유자 이름 비슷 → LLM {sim:,}"
                   + (f" — 전체 python run.py show report {mt['doc_id']} --md" if k or sim else ""))
    for g in mt.get("그래프") or []:
        out.append("     " + g)
    out.append("     큐 — " + " · ".join(f"{k} {v}" for k, v in (mt.get("큐") or {}).items()))
    el = mt.get("엣지 없는 노드") or []
    out.append(f"     엣지 없는 노드 {len(el):,}(이 문서가 만든 노드)" + (" — 사유" if el else ""))
    for lay, canon, cat, why in el[:limit]:
        out.append(f"       {lay}:{canon}({cat}) — {why}")
    if limit is not None and len(el) > limit:
        out.append(f"       … 외 {len(el) - limit:,} — 전체는 python run.py show report {mt['doc_id']}")
    dc = mt.get("문서 좌표")
    if dc:
        out.append(f"     문서 좌표 없음 — 좌표 미해소 보류 {dc['행']:,}행 · ▶ python run.py ingest-file <문서> "
                   f"--coord <골격 이름>")
        out.append("       가까운 골격 이름(띄어쓰기 · 대소문자 무시 — 보여만 준다): "
                   + (" · ".join(dc["후보"]) if dc["후보"] else "없음"))
    return out


def show_reconcile(mt, limit=None):
    for ln in reconcile_lines(mt, limit):
        _screen.say(ln, "fail" if "[결함]" in ln else ("head" if ln.startswith(("   맞춤", "   요약")) else None))
