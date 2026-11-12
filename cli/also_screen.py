# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 단의 화면**(B197 ②③④) — 문에 걸린 겸 값의 표와 처분 · 확정한 공정 줄 · 쌍별 예고 · 쓰기 전 판정 결과.

core는 사실만 낸다(`core/build/entry.heading_gate` · `_notice_plan` · `_pre_write`의 `notice`) — 화면이 그리고 `--step`이면 묻는다.
문의 표 · 물음은 골격 칸의 한 고리(`cli/gate_table` — LLM 판단 · 말 또는 글쇠 · 처분 넷 · B202) · 사람 없는 실행은 표만(LLM 0).
"""
from __future__ import annotations

import sys

from cli import _screen

#: 이 화면이 맡는 단계
STAGES = ("골격단", "확정공정", "판정결과")
#: 쓰기 전 판정 결과를 이 문서에서 물었나(물었으면 저장 뒤 [판정] 머리는 묻지 않는다)
ASKED = {"판정결과": False}
#: 이 문서의 쌍별 예고 md 몸(`export/plan_<doc>.md` — 판정 결과의 자리 바뀐 값을 끝 절로 더해 다시 쓴다 · B199 ①②)
PLAN = {}


def plan_md_name(doc_id):
    return f"plan_{doc_id}.md"


def _save_plan(doc_id, extra=()):
    from cli import envelope_md
    body = PLAN.get(doc_id) or [f"# 쌍별 예고 — {doc_id}", ""]
    return envelope_md.save(plan_md_name(doc_id), "\n".join(list(body) + list(extra)) + "\n")


def preview_screen(groups, doc_id, indent="     "):
    """쌍별 예고 — 화면은 쌍마다 요약(`also_stage.preview_lines`) · 전부는 md(`export/plan_<doc>.md` · 원자 쓰기 한 자리 — B199 ①)."""
    from core import paths
    from core.build import also_stage as AS
    full = AS.preview_lines(groups, indent="", full=True)
    PLAN[doc_id] = [f"# 쌍별 예고 — {doc_id}", "", "붙을 자리는 판정 전 이름 부모다(판정 뒤 자리는 끝 절).", "", "```"] + full + ["```"]
    p = _save_plan(doc_id)
    vals = sum(len(v) for v in groups.values())
    shown = sum(min(AS.TOP, sum(1 for r in v if AS._kind(r["plan"]) == AS.PLAN_KINDS[2][0])) for v in groups.values())
    return ([f"   쌍별 예고 — 쌍 {len(groups):,} · 표기 {vals:,}(같은 표기 · 자리는 한 번) · 붙을 자리(판정 전) · 판정 예정(쓰기 0 · LLM 0)"]
            + AS.preview_lines(groups, indent=indent)
            + [f"{indent}… 그 밖 {max(0, vals - shown):,}줄 — {paths.show(p)}"])


def moved_lines(info, indent="   "):
    """판정 결과 아래 — 자리가 바뀐 값 위 `TOP`(행 수 큰 차례) · 전부는 쌍별 예고 md의 끝 절(B199 ②)."""
    from cli.ingest_screen import PATH_SHORT
    from core import paths
    from core.build import also_stage as AS
    rows = info.get("자리") or []
    if not rows:
        return []

    def one(x):
        return f"{x['surface']}: {x['before']} → {x['after']}({PATH_SHORT.get(x.get('path'), x.get('path') or '—')})"
    doc = info.get("doc_id")
    out = [f"{indent}자리 바뀜(판정 전 → 판정 뒤) {len(rows):,}"]
    out += [f"{indent}  {one(x)}" for x in sorted(rows, key=lambda x: -x["n"])[:AS.TOP]]
    if doc:
        p = _save_plan(doc, ["", "## 판정 뒤 자리가 바뀐 값", ""] + [f"- {x['pair']} · {one(x)} · 행 {x['n']}" for x in rows])
        out.append(f"{indent}  전부 — {paths.show(p)}")
    return out


def _title(rows, where):
    return f"골격 단 — {where}의 겸 값 {len(rows):,}종이 문에 걸렸다(사람 확인 전 — 노드 0 · 그 아래 값도 보류)"


def ask_rows(rows, where="값"):
    """처분 — 골격 칸의 한 고리(번호 + 말 또는 글쇠 → 처분 → 표 다시) → 계속 c / 멈춤 q."""
    from cli import gate_table, provisional_ask as PA
    for r in rows:
        r.setdefault("where", where)
    return gate_table.loop(rows, PA.actor(), title=_title(rows, where))


def notice(info, step=False):
    """골격 단 화면 — `False`면 멈춤."""
    k = info["단계"]
    if k == "골격단":
        where = info.get("자리") or "값"
        if step and sys.stdin.isatty():
            return ask_rows(info["rows"], where)
        from cli import gate_table
        for r in info["rows"]:
            r.setdefault("where", where)
        gate_table.show(info["rows"], _title(info["rows"], where))
        return None
    if k == "확정공정":
        _screen.say(f"   {info['줄']}", "head")
        return None
    if k == "판정결과":
        _screen.close()
        _screen.say(f"   판정 결과 — 쓰기 전{' (판정까지)' if info.get('판정까지') else ''} — "
                    f"match {info['합']['match']:,} · new {info['합']['new']:,} · uncertain {info['합']['uncertain']:,}"
                    + (f" · 문에 걸림 {info['합']['문']:,}" if info["합"]["문"] else ""), "head")
        for ln in info["줄"] + moved_lines(info):
            print(ln)
        if step and not info.get("판정까지") and sys.stdin.isatty():
            ASKED["판정결과"] = True
            print("   c는 쓴다(그 뒤 [부착·엣지] · [큐·요약] 그대로) · q는 쓰지 않고 멈춘다(그래프 0 · 판정은 대장 중간 저장 — 다시 넣으면 LLM 0)")
            go = _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True)
            if not go:
                print("   멈춤 — 쓰지 않았다(그래프 · 사전 · 큐 0 · 판정은 대장 중간 저장 — 같은 명령을 다시 치면 LLM 0)")
            return go
        return None
    return None


def plan_lines(info, live=False):
    """[5/8] 머리 아래 — 쌍별 예고(③ — 요약 · 전부는 md) · 본문 값의 골격 단 문(② — 사람이 있으면 물음 고리가 그린다 · 없으면
    표만(LLM 0))."""
    out = []
    if info.get("쌍별"):
        out += preview_screen(info["쌍별"], info.get("doc_id") or "문서")
    if info.get("골격단"):
        from cli import gate_table
        from core.state import gate_judge
        rows = info["골격단"]
        for r in rows:
            r.setdefault("where", "본문")
        if live:
            out.append(f"   {_title(rows, '본문')} — 표는 물음에서")
        else:
            gate_judge.judge(rows, live=False)
            out += gate_table.lines(rows, _title(rows, "본문"))
    return out


def step8(info, step):
    """[5/8] 머리 아래 줄과 물음 — 쌍별 예고 · 골격 단 줄(처분 먼저) · 사람 후보(B140 — 다음) · `(줄, 물음 함수 또는 None)`."""
    from cli import human_gate
    hb = info.get("사람후보")
    rows = info.get("골격단") or []

    def ask():
        if rows and not ask_rows(rows, "본문"):
            return False
        return human_gate.ask(hb) if hb else True
    live = bool(step and rows and sys.stdin.isatty())
    return plan_lines(info, live) + (human_gate.lines(hb, step) if hb else []), (ask if (hb or rows) else None)


def asked_pop():
    """쓰기 전 판정 결과를 이 문서에서 물었나 — 읽고 지운다(다음 문서는 새로)."""
    v = ASKED.get("판정결과", False)
    ASKED["판정결과"] = False
    return v
