# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 확인의 시트 한 덩어리**(B126 ③) — 화면과 `export/split_<doc_id>.md`가 같은 함수로 같은 내용을 낸다.

    ⓐ LLM에 준 것 — 규칙 나무(행 · 단 · 글) · 형태 단서(번호 꼴 · 번호 이어짐 · 다시 시작)
    ⓑ LLM의 판단 — 고침 목록과 이유 · 버린 고침 · 제목마다 역할 · 대상 · 이유
    ⓒ 고친 뒤의 나무 — 행 · 단 · 역할 · 대상
    ⓓ 청크마다 첫 줄 · 끝 줄 · 사슬(라벨 잘림 없이 — 좁은 화면이면 줄이 접힌다)

판정 0 — 파싱의 구조 셈(`report["structure"]`)과 봉투 청크를 읽기만 한다.
"""
from __future__ import annotations

from core.build import structure_edit as SE
from parser.struct_rule import FRAME_ROW, draft_structure


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


def sheet_block(frame, fr, chunks):
    """시트 한 덩어리의 줄 목록(앞 공백 없이 — 화면은 들여 찍고 md는 그대로) · `fr`은 구조 셈의 그 시트 · `chunks`는 그 시트의 청크."""
    labs = fr.get("labels") or []
    text = {x["row"]: str(x.get("text") or "") for x in labs}
    draft = draft_structure(labs)
    head = (f"시트 '{frame}' · 방식 {fr.get('mode') or 'llm'}" + (" · 확정 기록 재생" if fr.get("confirmed") else "")
            + f" · 고침 {len(fr.get('edits') or [])} · 버림 {len(fr.get('edits_dropped') or [])}"
            + f" · 붙임 {len(fr.get('joins') or [])} · 힌트 {len(fr.get('hints') or [])} · 청크 {len(chunks)}")
    out = [head, "ⓐ LLM에 준 것 — 규칙 나무 " + (f"{len(draft)}줄" if draft else "없음(그 시트만 llm)")]
    out += [f"  {'  ' * (x['depth'] - 1)}{x['row']}행 {x['text']}" for x in SE.rules_tree(labs, draft)]
    runs = SE.run_lines(SE.number_runs(labs))
    out += ["  형태 단서 — " + (" · ".join(runs) if runs else "번호 이어짐 없음")]
    out.append("ⓑ LLM의 판단")
    out += [f"  고침 — {_edit_line(e)}" for e in fr.get("edits") or []] or ["  고침 — 없음(규칙 나무 그대로)"]
    out += [f"  버림 — {_edit_line(e)} · 사유 {e.get('버림')}" for e in fr.get("edits_dropped") or []]
    for h in fr.get("headings") or []:
        if h.get("why"):
            out.append(f"  제목 {h['row']}행 {h.get('role') or '—'}{_target(h)} — {h['why']}")
    out.append("ⓒ 고친 뒤의 나무")
    dep = _depths(fr.get("headings") or [])
    for h in fr.get("headings") or []:
        label = frame if h["row"] == FRAME_ROW else text.get(h["row"], "")
        out.append(f"  {'  ' * max(0, dep.get(h['row'], 1) - 1)}{h['row']}행 {h.get('role') or '—'}{_target(h)} · {label}"
                   + (" *" if h.get("by") else ""))
    out.append(f"ⓓ 청크 {len(chunks)}")
    for i, c in enumerate(chunks, start=1):
        body = [ln for ln in str(c.get("text") or "").splitlines() if ln.strip()] or [""]
        chain = " › ".join(x.get("text") or "" for x in (c.get("meta") or {}).get("structure") or []) \
            or str((c.get("meta") or {}).get("section_path") or c.get("section") or "")
        out.append(f"  {i}. {c.get('source_locator')} · 첫 줄 '{body[0].strip()}' · 끝 줄 '{body[-1].strip()}' · 사슬 {chain}")
    return out


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
        lines += [f"## {blk[0]}", ""] + [f"- {x}" if not x.startswith("  ") else f"  - {x.strip()}" for x in blk[1:]] + [""]
    p = paths.export(f"split_{doc_id}.md")
    paths.ensure(p)
    store.atomic_write_bytes(p, ("\n".join(lines) + "\n").encode("utf-8"))
    return p
