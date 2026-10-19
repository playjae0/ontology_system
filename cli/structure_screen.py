# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 표 · 구조 관문** — LLM이 세운 문서 구조를 보이고, 사람이 줄 번호로 고친다 (B119 ③).

    파싱 끝 (산문 · 구조가 섰을 때)
      ├ 약한 구조 신호 — 늘 크게(`[약한 구조]`) · 비대화형이면 기록(인입 기록 · `show summary`)에 남기고 진행
      └ `--step`이면 구조 표(번호 · 시트 · 행 · 단 · 역할 · 대상 · 줄 · 초안과 다름)를 보이고 묻는다
          `c` 계속 · `q` 멈춤 · 고침 `<번호> <카테고리>`(대상 + 그 카테고리) · `<번호> 묶음` · `<번호> 주제` · `<번호> 본문`
          → 고침은 `registry/structure_fixes.json`(등록 단 — 사람 판단 · 재생성 불가) → 같은 문서를 다시 파싱(LLM 0 —
            구조 보존분 위에 고침을 덮는다) → 표를 다시 보인다. 재구축도 같은 고침을 쓴다.

명령은 짧게(사내는 복붙이 안 된다) — 이름은 줄 글자에서 번호를 뗀 것 · `<번호> 대상`이면 카테고리는 같은 역할의 다른 줄이 쓴 것.
"""
from __future__ import annotations

from cli import _screen
from core.build import structure as ST
from parser import struct_map
from parser.struct_rule import BODY, ROLES, TARGET_ROLES

PROMPT = "   [계속 c / 멈춤 q / 고침 <번호> <카테고리|묶음|주제|본문>] "
HELP = ("   c(ㅊ)는 계속 · q(ㅂ)는 멈춤 · 고침은 「<번호> <카테고리>」(대상 + 그 카테고리 · 「<번호> 대상」이면 같은 역할의 "
        "다른 줄이 쓴 카테고리) · 「<번호> " + "」 · 「<번호> ".join([r for r in ROLES if r not in TARGET_ROLES] + [BODY])
        + "」 — 다시 친다")


def weak_lines(weak):
    return [f"   [약한 구조] 시트 '{fr}' — " + " · ".join(sig) for fr, sig in (weak or {}).items()]


def _target(r):
    if r.get("이름") and r.get("카테고리"):
        return f"{r['이름']}({r['카테고리']})"
    return "—"


def print_table(rows):
    t = _screen.Table([("번호", 4, True), ("시트", 14, False), ("행", 5, True), ("단", 3, True), ("역할", 10, False),
                       ("대상", 28, False), ("줄", 40, False), ("초안", 10, False)], flex=6, keep=(4, 5))
    for r in rows:
        diff = (("다름 " if r.get("다름") else "") + (f"초안{r['초안']} " if r.get("초안") else "")
                + (f"형제 「{r['형제']}」" if r.get("형제") else ""))
        role = "(본문)" if r.get("본문") else (r.get("역할") or "—") + ("*" if r.get("by") else "")
        t.row([r["번호"], r["시트"], r["행"] if r["행"] else "시트", r["단"] or "", role, _target(r), r.get("글") or "",
               diff.strip()], [None, None, "aux", "aux", "warn" if r.get("by") else None, None, "aux",
                               "warn" if r.get("다름") else "aux"])
    t.end()
    print("   * = 사람이 고친 줄 · 다름 = 고정 규칙 초안의 단과 다르다(초안n = 초안의 단 · (본문) = 초안은 제목인데 구조가 뺐다) · "
          "형제 「꼴」 = 같은 번호 꼴 줄의 단 · 역할이 갈렸다")


def parse_fix(answer, rows, cats):
    """`<번호> <카테고리>` · `<번호> 대상 [카테고리]` · `<번호> 묶음|주제|본문` → `(행 표의 줄, 고침)` · 못 읽으면 None."""
    toks = answer.split()
    if len(toks) < 2 or not toks[0].isdigit():
        return None
    row = next((r for r in rows if r["번호"] == int(toks[0])), None)
    if row is None or not row["행"]:
        return None
    rest = " ".join(toks[1:])
    target = TARGET_ROLES[0]
    if rest in [r for r in ROLES if r not in TARGET_ROLES] + [BODY]:
        return row, {"role": rest}
    cat = rest if rest in cats else (" ".join(toks[2:]) or _likely_category(rows, target) if toks[1] == target else None)
    if cat not in cats:
        print(f"   카테고리를 친다 — 「{toks[0]} <카테고리>」 · 목록: {' · '.join(sorted(cats))}")
        return None
    return row, {"role": target, "name": struct_map.strip_number(row.get("글")), "category": cat}


def _likely_category(rows, role):
    """같은 역할의 다른 줄이 가장 많이 쓴 카테고리(없으면 대상이 있는 줄 전부에서)."""
    for pool in ([r for r in rows if r.get("역할") == role], rows):
        got = {}
        for r in pool:
            if r.get("카테고리"):
                got[r["카테고리"]] = got.get(r["카테고리"], 0) + 1
        if got:
            return max(sorted(got), key=lambda k: got[k])
    return None


def gate(res, doc_id, reparse, *, ask=True, layers=None):
    """파싱 끝의 구조 관문 — `(res, 계속?)`. 고치면 기록하고 `reparse()`로 다시 파싱해 새 결과로 돈다."""
    from core.state.bootstrap import coord_layer
    coord_in = coord_layer() in (layers or [coord_layer()])
    while True:
        if not res.ok:                       # 고친 뒤 다시 파싱이 실패했다 — 진행하지 않는다
            print("   다시 파싱 실패 — " + "; ".join(f["reason"] for f in res.failures)[:200])
            return res, False
        st = (res.report or {}).get("structure")
        if not st:
            return res, True
        weak = ST.weak(st, (res.envelope or {}).get("chunks") or [], coord_in)
        for ln in weak_lines(weak):
            _screen.say(ln, "warn")
        res.envelope.setdefault("context", {})["structure"] = {**ST.counts(st), "약한": weak}
        if not ask:
            return res, True
        rows = ST.table(st)
        print_table(rows)
        for ln in ST.range_lines(st):                # 청크 구간 · 버린 사유 (B124 ②)
            print(ln)
        cats = ST.categories(ST._cfgs(layers))
        got = _screen.answer(PROMPT, "go", eof=True, other=lambda a: parse_fix(a, rows, cats), hint=HELP)
        if got is True or got is False:
            if got is False:
                print("   멈춤 — 구조까지(파싱 산출 parsed/ · 구조 보존분은 남았다 · 그래프 쓰기 0)")
            return res, got
        row, fix = got
        ST.record_fix(doc_id, row["시트"], row["행"], fix)
        print(f"   고침 — {row['시트']} {row['행']}행 → {fix['role']}"
              + (f" '{fix['name']}'({fix['category']})" if fix.get("name") else "")
              + f" · 기록 {ST.fixes_path().name} · 다시 파싱한다(LLM 0)")
        res = reparse()
