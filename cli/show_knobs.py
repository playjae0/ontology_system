# -*- coding: utf-8 -*-
"""칸 0.x — **사내 손잡이 화면**: 값 · 출처 · 그 값을 정할 분포 (B91 ⑤ · 읽기 전용).

사내 실측은 이 레포로 가져올 수 없다 — 그래서 값을 정할 **분포는 사내 화면에** 보여야
한다. `show knobs`가 손잡이마다 「분포를 보는 명령」을 가리키고, 그 명령이 이 파일의
`show dist <무엇>`이다. 여기는 **쓰지 않는다**(값은 사람이 `$ONTO_HOME/knobs.json`에 쓴다).

    python run.py show knobs
    python run.py show dist chunks|headings|forms|sheets|evidence|lens|ref
"""
from __future__ import annotations

import json

from core import paths
from core.state import knobs, store


def _q(xs, p):
    """분위 — 정렬된 목록의 p(0~1) 자리(보간 없음 · 표본이 작아도 결정적)."""
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]


def _dist_line(label, xs):
    if not xs:
        return f"  {label:<14} (재료 없음)"
    return (f"  {label:<14} n {len(xs)} · 최소 {min(xs)} · p50 {_q(xs, .5)} · p90 {_q(xs, .9)} · "
            f"p99 {_q(xs, .99)} · 최대 {max(xs)}")


def cmd_knobs(args):
    p = paths.knobs()
    print(f"■ 사내 손잡이 — {paths.show(p)} "
          f"{'있음' if p.exists() else '없음 (전부 기본값 = 코드 상수)'}")
    for r in knobs.rows():
        mark = "*" if r["from"] == "file" else " "
        print(f" {mark}{r['name']:<18} {json.dumps(r['value'], ensure_ascii=False):<44} "
              f"[{r['from']}] 기본 {json.dumps(r['default'], ensure_ascii=False)}")
        print(f"   {'':<18} {r['what']} — 분포: {r['dist']}")
    print("  바꾸려면: 위 파일에 {\"이름\": 값} — 닫힌 목록 · 모르는 키와 형 밖은 거부한다 · "
          "`_`로 시작하는 키는 주석")
    return 0


# ---------------------------------------------------------------- 분포 (읽기 전용)
def _chunks():
    return (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}).values()


def dist_chunks():
    cs = [c for c in _chunks() if c.get("text")]
    lens = [len(c["text"]) for c in cs]
    cap = knobs._parser_now("chunk_max_chars")
    parts = sum(1 for c in cs if (c.get("meta") or {}).get("char_cap_from"))
    over = sum(1 for c in cs if (c.get("meta") or {}).get("over_char_cap"))
    oor = sum(1 for c in cs if (c.get("meta") or {}).get("split_level_out_of_range"))
    print("■ 청크 글자 수 — chunk_max_chars · chunk_rows")
    print(_dist_line("글자", lens))
    print(f"  지금 상한 {cap}자 · 넘는 청크 {sum(1 for x in lens if x > cap)} · 상한으로 가른 조각 "
          f"{parts} · 혼자 넘는 행 {over} · 레벨 구간 밖 청크 {oor} "
          f"(구간 {knobs._parser_now('chunk_rows')})")
    return 0


def dist_headings():
    names = [h.strip() for c in _chunks() for h in (c.get("section") or "").split(" > ") if h.strip()]
    uniq = sorted(set(names))
    cap = knobs._parser_now("heading_max_chars")
    print("■ 제목 길이 — heading_max_chars (청크 section 경로의 제목들)")
    print(_dist_line("글자", [len(h) for h in uniq]))
    near = [h for h in uniq if cap - 10 <= len(h) <= cap]
    print(f"  지금 상한 {cap}자 · 상한 근처(−10자 안) {len(near)}"
          + (f" — 예: {near[0][:40]}" if near else ""))
    return 0


def dist_forms():
    reg = store.read(store.DOC_REGISTRY, {})
    forms = [(d, (v.get("routing") or {}).get("form") or {}) for d, v in reg.items()]
    forms = [(d, f) for d, f in forms if f]
    auto = sum(1 for _d, f in forms if f.get("auto"))
    print(f"■ 형태 판정 — form_auto {knobs._parser_now('form_auto')} · 문서 {len(forms)} · "
          f"자동 {auto} · 사람 {len(forms) - auto}")
    for d, f in forms[:20]:
        print(f"  {d:<20} {f.get('verdict')!s:<6} {'자동' if f.get('auto') else '사람'} · "
              f"table {len(f.get('table') or [])} · prose {len(f.get('prose') or [])} · "
              f"기권 {len(f.get('abstain') or [])}")
    return 0


def dist_sheets():
    d = paths.registry("sheet_roles")
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] \
        if d.exists() else []
    agree = total = llm_agree = llm_total = 0
    for r in recs:
        for name, final in (r.get("sheets") or {}).items():
            lg = (r.get("logic") or {}).get(name)
            lm = (r.get("llm") or {}).get(name)
            if lg:
                total += 1
                agree += lg == final
            if lm:
                llm_total += 1
                llm_agree += lm == final
    print(f"■ 시트 판정 — sheet_thresholds {knobs._parser_now('sheet_thresholds')} · 기록 {len(recs)}건")
    print(f"  로직 제안 = 최종 {agree}/{total}" + (f" ({agree / total:.0%})" if total else "")
          + f" · LLM 제안 = 최종 {llm_agree}/{llm_total}"
          + (f" ({llm_agree / llm_total:.0%})" if llm_total else ""))
    return 0


def dist_evidence():
    p = store.path(store.CHUNK_TRUNCATED)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    cut = [int(l.split("건")[0]) for l in lines if l.split("건")[0].isdigit()]
    print(f"■ 근거 수집 잘림 — collect_limit {knobs.get('collect_limit')}")
    print(f"  잘린 질의 {len(cut)} · " + _dist_line("잘린 청크", cut).strip())
    return 0


def dist_lens():
    """렌즈별 호출 — 렌즈 체크포인트(`extract/<doc>@<렌즈>.json`)의 부른 청크 · 거른 청크."""
    from core.build import extract as EX
    rows = []
    for p in sorted(EX.EXTRACT_DIR.glob("*@*.json")) if EX.EXTRACT_DIR.exists() else []:
        ck = json.loads(p.read_text(encoding="utf-8"))
        called = sum(1 for c in ck.get("candidates") or [] if not c.get("lens_skipped"))
        rows.append((ck.get("doc_id"), ck.get("lens"), called, ck.get("lens_skipped", 0)))
    print(f"■ 렌즈별 호출 — lens_min_score {knobs.get('lens_min_score')} · "
          f"lens_call_cap {knobs.get('lens_call_cap')} · 렌즈 체크포인트 {len(rows)}")
    for d, lz, called, sk in rows[:40]:
        print(f"  {d:<20} {lz:<12} 부름 {called} · 거름 {sk}")
    if rows:
        print(f"  합 — 부름 {sum(r[2] for r in rows)} · 거름 {sum(r[3] for r in rows)}")
    return 0


def dist_ref():
    """참조 시트 청크 — 문서별 수 · 글자 분포(ref 노드 근처 [관련 원문]의 재료 · 읽기 전용)."""
    refs = [c for c in _chunks() if (c.get("meta") or {}).get("sheet_role") == "ref"]
    by_doc = {}
    for c in refs:
        by_doc[c.get("doc_id")] = by_doc.get(c.get("doc_id"), 0) + 1
    print(f"■ ref 근처 — ref_limit {knobs.get('ref_limit')} · 참조 청크 {len(refs)} · 문서 {len(by_doc)}")
    print(_dist_line("글자", [len(c.get("text") or "") for c in refs]))
    for d, n in sorted(by_doc.items(), key=lambda x: -x[1])[:20]:
        print(f"  {d:<20} 참조 청크 {n}")
    return 0


DIST = {"lens": dist_lens, "ref": dist_ref, "chunks": dist_chunks, "headings": dist_headings, "forms": dist_forms,
        "sheets": dist_sheets, "evidence": dist_evidence}


def cmd_dist(args):
    if not args or args[0] not in DIST:
        raise SystemExit(f"[사용법] python run.py show dist <{'|'.join(DIST)}>")   # [사용법]
    return DIST[args[0]]()
