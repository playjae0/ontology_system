# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 확인의 시트 한 덩어리**(B126 ③ · B132 ⑦) — 화면과 `export/split_<doc_id>.md`가 같은 함수로 같은 내용을 낸다.

    머리 — 방식 · 사다리의 출처 · 판단 필요 · 답 빠짐 · 고침 · 버림 · 붙임 · 힌트 · 청크 (답 꼴이 어긋나 버린 칸이 있으면 그 한 줄)
    계층 사다리: 시트 › 9. › 가.(대상 · Unit) › 9)(묶음) › A.   (단마다 서명 · 역할 · 카테고리 · 번호 없는 제목의 규칙)
    목차 — 들여쓰기 = 목차 깊이 · 서명 · 역할 · 대상 · 사다리 목차와 달라진 줄은 `← 바뀜`
    판단 필요 — 행마다 이유와 답(제목 · 부모 · 역할 · 이유 — 답이 없으면 「답 없음」) · 고침 · 버린 고침 · 사다리 고침(적용 n줄 / 전체 m줄)
    청크 — 첫 줄 · 끝 줄 · 전체 경로(시트 › … › 자기 제목 — 라벨 잘림 없이)
md도 들여쓰기를 지킨다(B130 ③). 판정 0 — 파싱의 구조 셈(`report["structure"]`)과 봉투 청크를 읽기만 한다.
"""
from __future__ import annotations

from parser.struct_rule import FRAME_ROW


def _target(h):
    return f" {h['name']}({h['category']})" if h.get("name") and h.get("category") else ""


def _edit_line(e):
    what = e.get("what")
    par = f"{e['parent']}행" if e.get("parent") else "시트"
    extra = {"제목 더함": f"(부모 {par})", "부모 바꿈": f"(→ 부모 {par})",
             "역할": f"(→ {e.get('role')})", "대상": f"(→ {e.get('name')} · {e.get('category')})",
             "붙임": f"(~{e.get('to_row')}행)"}.get(what, "")
    return f"{e.get('row')}행 {what}{extra} — {e.get('why') or '이유 없음'}"


def _depths(heads):
    d = {}
    for h in heads:
        p = h.get("parent")
        d[h["row"]] = 0 if h["row"] == FRAME_ROW else (d.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1)
    return d


def ladder_line(ladder):
    """「계층 사다리: 시트 › 9. › 가.(대상 · Unit) › 9)(묶음) › A.」 + 번호 없는 제목의 규칙."""
    parts = []
    for lv in (ladder or {}).get("levels") or []:
        tag = " · ".join(x for x in (lv.get("role"), lv.get("category")) if x)
        parts.append(" · ".join(lv.get("sigs") or []) + (f"({tag})" if tag else ""))
    rules = [f"{' · '.join(u.get('when') or [])} → 단 {u.get('level')}" + (f"({u['role']})" if u.get("role") else "")
             for u in (ladder or {}).get("unnumbered") or []]
    return "계층 사다리: " + " › ".join(["시트"] + parts) + (f" · 번호 없는 제목 — {' / '.join(rules)}" if rules else "")


def sheet_block(frame, fr, chunks):
    """시트 한 덩어리의 줄 목록(앞 공백 없이 — 화면은 들여 찍고 md는 그대로) · `fr`은 구조 셈의 그 시트 · `chunks`는 그 시트의 청크."""
    labs = fr.get("labels") or []
    by = {x["row"]: x for x in labs}
    heads = fr.get("headings") or []
    needs = fr.get("needs") or []
    ans = {a.get("row"): a for a in ((fr.get("answer") or {}).get("answers") or [])}
    head = (f"시트 '{frame}' · 방식 {fr.get('mode') or '-'} · 사다리 {fr.get('ladder_source') or '-'}"
            + (" · 확정 기록 재생" if fr.get("confirmed") else "")
            + f" · 판단 필요 {len(needs)} · 답 빠짐 {len(fr.get('missing') or [])} · 고침 {len(fr.get('edits') or [])}"
            + f" · 버림 {len(fr.get('edits_dropped') or [])} · 붙임 {len(fr.get('joins') or [])} · 힌트 {len(fr.get('hints') or [])}"
            + f" · 청크 {len(chunks)}")
    out = [head, ladder_line(fr.get("ladder"))]
    if fr.get("shape_dropped"):                                       # 답 꼴이 어긋나 버린 칸 (B134 ②)
        out.append(f"시트 확인 답 버림 — 꼴이 어긋남 {' · '.join(fr['shape_dropped'])} → 사다리 목차 그대로(판단 필요는 남는다)")
    was = {h["row"]: h.get("parent") for h in fr.get("toc0") or heads}
    dep = _depths(heads)
    out.append(f"목차 — 제목 {len([h for h in heads if h['row'] != FRAME_ROW])}줄")
    for h in heads:
        x = by.get(h["row"]) or {}
        label = frame if h["row"] == FRAME_ROW else str(x.get("text") or "")
        moved = h["row"] != FRAME_ROW and (h["row"] not in was or was[h["row"]] != h.get("parent"))
        out.append(f"  {'  ' * max(0, dep.get(h['row'], 1) - 1)}{h['row']}행 {x.get('sig') or '·'} {label} — "
                   f"{h.get('role') or '역할 없음'}{_target(h)}" + (" *" if h.get("by") == "사람" else "")
                   + (" ← 바뀜" if moved else ""))
    gone = [r for r in was if r not in {h["row"] for h in heads}]
    if gone:
        out.append("  목차에서 뺀 줄 — " + " · ".join(f"{r}행 {(by.get(r) or {}).get('text', '')}" for r in gone))
    out.append(f"판단 필요 {len(needs)}")
    for n in needs:
        a = ans.get(n["row"])
        said = ("답 — " + ("제목" + (f"(부모 {a.get('parent')}행" if a.get("parent") else "(부모 시트") + f" · {a.get('role') or '역할 없음'})"
                           if a.get("heading") else "본문") + f" · {a.get('why') or ''}") if a else "답 없음"
        out.append(f"  {n['row']}행 {n['kind']} {n['why']} · '{str((by.get(n['row']) or {}).get('text') or '')[:40]}' — {said}")
    for x in fr.get("rules") or []:                                   # 사다리 고침 — 문서 규칙 (B130 ④ · B132 ⑦)
        what = " · ".join(v for v in (x.get("role"), x.get("category"), f"부모 서명 '{x['parent_shape']}'" if x.get("parent_shape") else None) if v)
        out.append(f"  사다리 고침 — 서명 '{x.get('shape')}' {what} 「{x.get('said') or ''}」 → 적용 {x.get('적용', 0)}줄 / 그 서명 전체 "
                   f"{x.get('전체', 0)}줄")
    out += [f"  고침 — {_edit_line(e)}" for e in fr.get("edits") or []]
    out += [f"  버림 — {_edit_line(e)} · 사유 {e.get('버림')}" for e in fr.get("edits_dropped") or []]
    out.append(f"청크 {len(chunks)}")
    for i, c in enumerate(chunks, start=1):
        body = [ln for ln in str(c.get("text") or "").splitlines() if ln.strip()] or [""]
        out.append(f"  {i}. {c.get('source_locator')} · 첫 줄 '{body[0].strip()}' · 끝 줄 '{body[-1].strip()}' · 경로 "
                   + path_of(frame, c))
    return out


def path_of(frame, c):
    """청크의 전체 경로 — 시트 › … › 자기 제목(목차의 부모 사슬 — B130 ②)."""
    m = c.get("meta") or {}
    sec = str(m.get("section_path") or c.get("section") or "")
    parts = [p.strip() for p in sec.replace(" › ", " > ").split(" > ") if p.strip() and p.strip() != frame]
    return " › ".join([frame] + parts)


def chunks_of(env, frame):
    return [c for c in (env or {}).get("chunks") or [] if (c.get("meta") or {}).get("frame") == frame]


def write_md(doc_id, report, env):
    """`export/split_<doc_id>.md` — 시트마다 같은 덩어리(원자 쓰기) · 쓴 경로를 돌려준다(구조가 없으면 None)."""
    from core import paths
    from core.state import store
    frames = ((report or {}).get("structure") or {}).get("프레임") or {}
    if not frames:
        return None
    lines = [f"# 구조 확인 — {doc_id}", ""]
    for frame, fr in frames.items():
        blk = sheet_block(frame, fr, chunks_of(env, frame))
        # 들여쓰기를 지킨다(나무 — B130 ③): 앞 공백 두 칸이 한 단
        lines += [f"## {blk[0]}", ""] + [f"{'  ' * ((len(x) - len(x.lstrip())) // 2)}- {x.strip()}" for x in blk[1:]] + [""]
    p = paths.export(f"split_{doc_id}.md")
    paths.ensure(p)
    store.atomic_write_bytes(p, ("\n".join(lines) + "\n").encode("utf-8"))
    return p
