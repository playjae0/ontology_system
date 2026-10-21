# -*- coding: utf-8 -*-
"""칸 0.3 · 2.4 — **구조 확인의 시트 한 덩어리**(B126 ③ · B132 ⑦ · B137 ⑥⑦) — 화면과 `export/split_<doc_id>.md`가 같은 함수로 같은 내용을 낸다.

    머리 — 방식 · 사다리의 출처 · 판단 필요 · 답 빠짐 · 고침 · 버림 · 붙임 · 힌트 · 청크 (답 꼴이 어긋나 버린 칸이 있으면 그 한 줄)
    계층 사다리: 시트 › 1. › 가.(대상 · Unit) › 1)(묶음) › A.   (서명의 숫자는 첫 서수로 · 단마다 역할 · 카테고리 · 번호 없는 제목의 규칙)
    LLM — 판단 필요 답 a/b · 규칙 r · 줄 고침 e(적용 x · 버림 y — 이유별 수)   (시트마다 한 줄 · 규칙마다 아래 한 줄)
    시트 확인 — 호출 1 · 입력 c · 출력 d · 초안과 다른 줄 x/제목 y
    목차 — 들여쓰기 = 목차 깊이 · 첫 서수 표기 · 역할 · 대상 · LLM이 바꾼 줄 ✎ · 판단 필요는 그 줄에 ⚠ 한 마디 + 답(줄 끝) ·
           하위가 없는 형제 줄이 셋 이상 이어지면 첫 줄 + 「… 외 n줄(2)~11))」(판단 필요 · 바뀐 줄은 접지 않는다)
    청크 — 첫 줄 · 끝 줄 · 전체 경로(시트 › … › 자기 제목 — 라벨 잘림 없이)
md도 들여쓰기를 지킨다(B130 ③) · 고침과 버린 고침의 상세는 md 끝 절에만(`detail_lines`). 판정 0 — 파싱의 구조 셈(`report["structure"]`)과
봉투 청크를 읽기만 한다.
"""
from __future__ import annotations

from parser import sig as SG
from parser.ladder import TITLE
from parser.struct_rule import FRAME_ROW

#: 판단 필요 표지 · 접는 형제 줄 수(화면 박자 — 손잡이 아님)
NEED_MARK = "⚠"
FOLD_MIN = 3


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


def _sigs(sigs):
    return " · ".join(SG.show(s) for s in sigs or [])


def ladder_line(ladder):
    """「계층 사다리: 시트 › 1. › 가.(대상 · Unit) › 1)(묶음) › A.」 + 번호 없는 제목의 규칙 + 첫 서수 목록 규칙 — 서명은 첫 서수 표기."""
    parts = []
    for lv in (ladder or {}).get("levels") or []:
        tag = " · ".join(x for x in (lv.get("role"), lv.get("category")) if x)
        parts.append(_sigs(lv.get("sigs")) + (f"({tag})" if tag else ""))
    rules = [f"{' · '.join(u.get('when') or [])} → 단 {u.get('level')}" + (f"({u['role']})" if u.get("role") else "")
             for u in (ladder or {}).get("unnumbered") or []]
    lists = [f"{SG.show(u.get('parent_shape'))} 아래 첫 서수 {SG.show(u.get('shape'))} 목록" + (f"({u['role']})" if u.get("role") else "")
             for u in (ladder or {}).get("lists") or []]
    return ("계층 사다리: " + " › ".join(["시트"] + parts) + (f" · 번호 없는 제목 — {' / '.join(rules)}" if rules else "")
            + (f" · 규칙 — {' / '.join(lists)}" if lists else ""))


def _reasons(bad):
    tally = {}
    for e in bad:
        tally[e.get("버림") or "사유 없음"] = tally.get(e.get("버림") or "사유 없음", 0) + 1
    return " · ".join(f"{k} {n}" for k, n in tally.items())


def llm_line(fr):
    """시트마다 LLM 한 줄 — 판단 필요 답 · 규칙 · 줄 고침(적용 · 버림 — 이유별 수) · 답에서 나온 고침의 버림(없으면 None — 판정 없음)."""
    if fr.get("source") not in ("live", "hint") and not fr.get("answer"):
        return None
    needs, missing = fr.get("needs") or [], fr.get("missing") or []
    line = [e for e in fr.get("edits") or [] if e.get("src") != "답"]
    bad = [e for e in fr.get("edits_dropped") or [] if e.get("src") != "답"]
    abad = [e for e in fr.get("edits_dropped") or [] if e.get("src") == "답"]
    rb = fr.get("rules_dropped") or []
    return (f"LLM — 판단 필요 답 {len(needs) - len(missing)}/{len(needs)}" + (f"(버림 {len(abad)} — {_reasons(abad)})" if abad else "")
            + f" · 규칙 {len(fr.get('rules') or [])}" + (f"(버림 {len(rb)} — {_reasons(rb)})" if rb else "")
            + f" · 줄 고침 {len(line) + len(bad)}(적용 {len(line)} · 버림 {len(bad)}" + (f" — {_reasons(bad)}" if bad else "") + ")")


def usage_line(fr):
    """「시트 확인 — 호출 1 · 입력 c · 출력 d · 초안과 다른 줄 x/제목 y」(B137 ⑦) · 판정이 없는 시트는 None."""
    if fr.get("mode") == "rules" or fr.get("source") not in ("live", "hint", "confirmed") and not fr.get("answer"):
        return None
    u = fr.get("usage")
    heads = [h for h in fr.get("headings") or [] if h["row"] != FRAME_ROW]
    tail = f"초안과 다른 줄 {len(fr.get('changed') or [])}/제목 {len(heads)}"
    if fr.get("confirmed"):
        return f"시트 확인 — 확정 기록 재생(호출 0) · {tail}"
    if u is None:
        return f"시트 확인 — 재사용(호출 0) · {tail}"
    if fr.get("source") == "hint":
        return f"시트 확인 — mock 힌트(호출 0) · {tail}"
    return f"시트 확인 — {spent(u)} · {tail}"


def spent(u):
    """사용량 조각 — 「호출 n · 입력 a · 출력 b」(게이트웨이가 입출력을 주지 않으면 그 사실을)."""
    u = u or {}
    io_ = (f"입력 {u.get('prompt', 0):,} · 출력 {u.get('completion', 0):,}" if u.get("prompt") or u.get("completion") or not u.get("total")
           else f"토큰 {u['total']:,}(입출력 구분 없음)")
    return f"호출 {u.get('calls', 0)} · {io_}"


def _num(x):
    """줄 머리의 번호 글자(접힘 표기 — 「2)」) · 번호가 없으면 「R행」."""
    t = str(x.get("text") or "").strip()
    h = SG._head(t)
    return t[:h[2]].strip() if h and x.get("sig") else f"R{x['row']}"


def _answer_tail(a, by, who):
    if a is None:
        return " → 답 없음"
    if not a.get("heading"):
        return f" → 본문({who})"
    p = a.get("parent")
    if p in (None, FRAME_ROW):
        return f" → 맨 위({who})"
    px = by.get(p) or {}
    return f" → {SG.show(px.get('sig')) + '(' + str(p) + '행)' if px.get('sig') else str(p) + '행'} 아래({who})"


def toc_lines(frame, fr):
    """목차 줄 — 제목 · 판단 필요 줄 · LLM이 뺀 줄을 이름표 순으로 · 형제 줄 접기(B137 ⑥) — `[(줄, 판단 필요인가)]`."""
    labs = fr.get("labels") or []
    by = {x["row"]: x for x in labs}
    heads = fr.get("headings") or []
    head = {h["row"]: h for h in heads}
    need = {n["row"]: n for n in fr.get("needs") or []}
    ans = {a.get("row"): a for a in ((fr.get("answer") or {}).get("answers") or [])}
    draft = {h["row"] for h in fr.get("toc0") or heads}
    changed = set(fr.get("changed") or [])
    who = "힌트" if fr.get("source") == "hint" else "LLM"
    dep = _depths(heads)
    kids = {h.get("parent") for h in heads}
    order = [x["row"] for x in labs if x["row"] != FRAME_ROW and (x["row"] in head or x["row"] in need or x["row"] in draft)]
    rows, cur = [], 0
    for r in order:
        x = by.get(r) or {}
        h = head.get(r)
        d = dep.get(r, 1) if h else cur + 1
        if h:
            cur = dep.get(r, 1)
        label = frame if r == FRAME_ROW else str(x.get("text") or "")
        if h:
            body = (f"{h.get('role') or '역할 없음'}{_target(h)}" + (" · 시트 제목" if h.get("sig") == TITLE else "")
                    + (" *" if h.get("by") == "사람" else "") + (" ✎" if r in changed else ""))
        else:
            body = "본문" + (" ✎" if r in changed else "")
        ln = f"{'  ' * max(0, d - 1)}{r}행 {SG.show(x.get('sig')) or '·'} {label} — {body}"
        n = need.get(r)
        if n:
            ln += f"  {NEED_MARK} {n.get('tag') or n['kind']}" + _answer_tail(ans.get(r), by, who)
        foldable = bool(h) and r not in kids and not n and r not in changed and h.get("sig") != TITLE
        rows.append({"row": r, "line": ln, "need": bool(n), "fold": foldable, "parent": h.get("parent") if h else ("본문", r)})
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1]["fold"] and rows[i]["fold"] and rows[j + 1]["parent"] == rows[i]["parent"]:
            j += 1
        if j - i + 1 >= FOLD_MIN:
            ind = rows[i]["line"][:len(rows[i]["line"]) - len(rows[i]["line"].lstrip())]
            out += [(rows[i]["line"], False),
                    (f"{ind}… 외 {j - i}줄({_num(by[rows[i + 1]['row']])}~{_num(by[rows[j]['row']])})", False)]
        else:
            out += [(rw["line"], rw["need"]) for rw in rows[i:j + 1]]
        i = j + 1
    return out


def sheet_block(frame, fr, chunks):
    """시트 한 덩어리의 줄 목록(앞 공백 없이 — 화면은 들여 찍고 md는 그대로) · `fr`은 구조 셈의 그 시트 · `chunks`는 그 시트의 청크.
    판단 필요 줄은 `NEED_MARK`를 단다(화면이 그 줄만 칠한다 — 터미널일 때만)."""
    heads = fr.get("headings") or []
    needs = fr.get("needs") or []
    head = (f"시트 '{frame}' · 방식 {fr.get('mode') or '-'} · 사다리 {fr.get('ladder_source') or '-'}"
            + (" · 확정 기록 재생" if fr.get("confirmed") else "")
            + f" · 판단 필요 {len(needs)} · 답 빠짐 {len(fr.get('missing') or [])} · 고침 {len(fr.get('edits') or [])}"
            + f" · 버림 {len(fr.get('edits_dropped') or [])} · 붙임 {len(fr.get('joins') or [])} · 힌트 {len(fr.get('hints') or [])}"
            + f" · 청크 {len(chunks)}")
    out = [head, ladder_line(fr.get("ladder"))]
    if fr.get("shape_dropped"):                                       # 답 꼴이 어긋나 버린 칸 (B134 ②)
        out.append(f"시트 확인 답 버림 — 꼴이 어긋남 {' · '.join(fr['shape_dropped'])} → 사다리 목차 그대로(판단 필요는 남는다)")
    for ln in (llm_line(fr), usage_line(fr)):
        if ln:
            out.append(ln)
    for x in fr.get("rules") or []:                                   # 사다리 고침 — 문서 규칙 (B130 ④ · B132 ⑦ · B137 ⑤)
        scope = (f"{SG.show(x.get('parent_shape'))} 아래 첫 서수 목록" if x.get("scope") == "첫 서수 목록"
                 else f"부모 서명 '{SG.show(x['parent_shape'])}'" if x.get("parent_shape") else None)
        what = " · ".join(v for v in (x.get("role"), x.get("category"), scope) if v)
        out.append(f"  규칙 — 서명 '{SG.show(x.get('shape'))}' {what} 「{x.get('said') or ''}」 → 적용 {x.get('적용', 0)}줄 / 그 서명 전체 "
                   f"{x.get('전체', 0)}줄")
    out.append(f"목차 — 제목 {len([h for h in heads if h['row'] != FRAME_ROW])}줄 · 판단 필요 {len(needs)}({NEED_MARK})")
    out += [f"  {ln}" for ln, _n in toc_lines(frame, fr)]
    out.append(f"청크 {len(chunks)}")
    for i, c in enumerate(chunks, start=1):
        body = [ln for ln in str(c.get("text") or "").splitlines() if ln.strip()] or [""]
        out.append(f"  {i}. {c.get('source_locator')} · 첫 줄 '{body[0].strip()}' · 끝 줄 '{body[-1].strip()}' · 경로 "
                   + path_of(frame, c))
    return out


def detail_lines(frame, fr):
    """md 끝 절 — 그 시트의 고침 · 버린 고침 · 버린 규칙의 상세(화면에는 없다 · B137 ⑥)."""
    out = [f"고침 — {_edit_line(e)}" for e in fr.get("edits") or []]
    out += [f"버림 — {_edit_line(e)} · 사유 {e.get('버림')}" for e in fr.get("edits_dropped") or []]
    out += [f"버린 규칙 — 서명 '{SG.show(x.get('shape'))}' 「{x.get('said') or ''}」 · 사유 {x.get('버림')}" for x in fr.get("rules_dropped") or []]
    return out


def path_of(frame, c):
    """청크의 전체 경로 — 시트 › … › 자기 제목(목차의 부모 사슬 — B130 ②)."""
    m = c.get("meta") or {}
    sec = str(m.get("section_path") or c.get("section") or "")
    parts = [p.strip() for p in sec.replace(" › ", " > ").split(" > ") if p.strip() and p.strip() != frame]
    return " › ".join([frame] + parts)


def chunks_of(env, frame):
    return [c for c in (env or {}).get("chunks") or [] if (c.get("meta") or {}).get("frame") == frame]


def ladder_usage(st):
    """「사다리 — 호출 1 · 입력 a · 출력 b」(B137 ⑦ — 문서당 한 번 · 재사용 · 확정이면 호출 0)."""
    src = (st or {}).get("사다리") or "-"
    u = (st or {}).get("사다리_사용")
    if not u or not u.get("calls"):
        return f"사다리 — {src}(호출 0)"
    return f"사다리 — {src} · {spent(u)}"


def toc_field_line(st):
    """「목차 필드 — n줄 거름(목차 재료 · 청크에서 뺐다)」(B138 ③ — 리더가 거른 목차 필드의 결과 줄) · 없으면 None."""
    n = (st or {}).get("목차 필드")
    return f"목차 필드 — {n}줄 거름(목차 재료 · 청크에서 뺐다)" if n else None


def total_usage(st):
    """문서 끝 구조 합계 — 사다리 + 시트 확인의 호출 · 입출력 · 초안과 다른 줄(B137 ⑦)."""
    frames = ((st or {}).get("프레임") or {}).values()
    us = [(st or {}).get("사다리_사용") or {}] + [f.get("usage") or {} for f in frames]
    tot = {k: sum(int(u.get(k) or 0) for u in us) for k in ("calls", "prompt", "completion", "total")}
    ch = sum(len(f.get("changed") or []) for f in frames)
    hs = sum(len([h for h in f.get("headings") or [] if h["row"] != FRAME_ROW]) for f in frames)
    return f"구조 합계 — {spent(tot)} · 초안과 다른 줄 {ch}/제목 {hs}"


def write_md(doc_id, report, env):
    """`export/split_<doc_id>.md` — 시트마다 같은 덩어리 + 끝 절(고침 상세)(원자 쓰기) · 쓴 경로를 돌려준다(구조가 없으면 None)."""
    from core import paths
    from core.state import store
    st = (report or {}).get("structure") or {}
    frames = st.get("프레임") or {}
    if not frames:
        return None
    lines = [f"# 구조 확인 — {doc_id}", "", f"- {ladder_usage(st)}", f"- {total_usage(st)}"] + (
        [f"- {toc_field_line(st)}"] if toc_field_line(st) else []) + [""]
    for frame, fr in frames.items():
        blk = sheet_block(frame, fr, chunks_of(env, frame))
        # 들여쓰기를 지킨다(나무 — B130 ③): 앞 공백 두 칸이 한 단
        lines += [f"## {blk[0]}", ""] + [f"{'  ' * ((len(x) - len(x.lstrip())) // 2)}- {x.strip()}" for x in blk[1:]] + [""]
    detail = [(frame, detail_lines(frame, fr)) for frame, fr in frames.items()]
    if any(d for _f, d in detail):
        lines += ["## 고침 상세(적용 · 버림)", ""]
        for frame, d in detail:
            lines += [f"- 시트 '{frame}'"] + [f"  - {x}" for x in d] if d else []
        lines.append("")
    p = paths.export(f"split_{doc_id}.md")
    paths.ensure(p)
    store.atomic_write_bytes(p, ("\n".join(lines) + "\n").encode("utf-8"))
    return p
