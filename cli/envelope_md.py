# -*- coding: utf-8 -*-
"""칸 0.3 — **봉투 → 사람용 md**(B143 ④) — parsed JSON(봉투) **하나만** 읽어 `export/split_<doc_id>.md`를 찍는 포맷 공통 꼴.

md는 보기다 — **md에만 있는 정보 0** · LLM은 md를 읽지 않는다(호출 입력은 봉투에서 조립한다). 꼴은 포맷을 가리지 않는다:

    머리      문서 · 단위 수 · 조각 수 · 문서 좌표 · 개요 · 캡처
    단위 표   단위마다 한 줄 — 번호 · 제목(초안 → 판단) · 이어짐 · 다루는 공정 · 언급 · 개체 없음 · 근거 조각 · 글자
    단위마다  경로 · 공정 · 쪽 · 버림 · 사람 고침 + 근거 조각 원문(`[본문]` · `[표 …]` · `[차트 …]` · `[그림 요약 …]` — 묶음 머리는
              추출 입력과 같은 손 `core/build/extract_unit._tag`) · `[노트]`(한 번)

단위 표의 판단 칸은 봉투의 구조 블록이 준다 — 지금은 PPT 덱 블록(`deck.slides[]` — B143 ②)이고, 블록이 없는 봉투는 쓰지 않는다
(None — 엑셀 · Word의 구조 확인 md는 `cli/split_report.write_md`가 그대로 쓴다 · 같은 꼴로 옮기는 것은 다음 회차). 쓰는 자리는
`cli/structure_screen.md_of` 한 자리다(인입 · `--split-only` · 배치 · 재구축이 같은 길).
"""
from __future__ import annotations

from pathlib import PurePath


def _cell(x):
    return str(x if x not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def _procs(ps):
    return "—" if ps is None else (" · ".join(ps) or "없음")


def _title(s, chunks):
    draft, judged = s.get("title_draft"), s.get("title")
    base = judged or draft or next((c.get("section") for c in chunks if c.get("section")), None) or "—"
    if judged and draft and judged != draft:
        base = f"{draft} → {judged}"
    elif judged and not draft:
        base = f"(없음) → {judged}"
    return base + ("*" if s.get("fixed") else "")


def units(env):
    """`[(단위 판단, [청크 …])]` — 구조 블록의 단위마다 그 근거 청크(블록이 든 위치 차례 그대로) · 블록이 없으면 빈 목록."""
    by = {c.get("source_locator"): c for c in env.get("chunks") or []}
    return [(s, [by[x] for x in s.get("chunks") or [] if x in by]) for s in ((env.get("deck") or {}).get("slides")) or []]


def _body(c):
    from core.build.extract_unit import _tag
    head = _tag(c) or "[본문]"
    return [head, "```text", (c.get("text") or "").rstrip(), "```"]


def lines(env):
    """봉투 → md 줄들(봉투 밖을 읽지 않는다)."""
    doc_id = env.get("doc_id")
    us = units(env)
    chunks = env.get("chunks") or []
    src = env.get("source_path")
    dk = env.get("deck") or {}
    cap = (env.get("capture") or {}).get("pages")
    out = [f"# 구조 확인 — {doc_id}", "",
           f"- 문서 {PurePath(str(src)).name if src else '—'} · 슬라이드 {len(us)} · 조각 {len(chunks)} · "
           f"문서 좌표 {env.get('doc_coord') or '없음'}",
           f"- 덱 개요 — {dk.get('overview') or '없음'}"]
    if cap:
        out.append(f"- 캡처 — 보이는 쪽 {cap}(추출이 원본에서 뜬다 · 저장 0)")
    out += ["", "## 슬라이드 표", "",
            "| 번호 | 제목(초안 → 판단) | 이어짐 | 다루는 공정 | 언급 | 개체 없음 | 근거 조각 | 글자 |",
            "|---:|---|---:|---|---|---|---:|---:|"]
    for s, cs in us:
        out.append("| " + " | ".join(_cell(x) for x in (
            s.get("slide"), _title(s, cs), s.get("continues"), _procs(s.get("processes")),
            " · ".join(s.get("mentions") or []), "예" if s.get("no_entities") else "",
            len(cs), sum(len(c.get("text") or "") for c in cs))) + " |")
    out += ["", "다루는 공정 — = 판정 없음(경로 · 문서 좌표) · 없음 = 덱 구조가 「공정 없음」 · * = 사람이 고친 칸이 있다", ""]
    for s, cs in us:
        m0 = (cs[0].get("meta") or {}) if cs else {}
        out += [f"## 슬라이드 {s.get('slide')} — {_title(s, cs)}", "",
                f"- 쪽 {s.get('page')} · 경로 {m0.get('section_path') or '—'} · 다루는 공정 {_procs(s.get('processes'))}"
                + (f" · 언급 {' · '.join(s['mentions'])}" if s.get("mentions") else "")
                + (f" · 이어짐 ← 슬라이드 {s['continues']}" if s.get("continues") is not None else "")
                + (" · 개체 없음" if s.get("no_entities") else "")]
        if cap and m0.get("page_no"):
            out.append(f"- 캡처 쪽 {m0['page_no']}")
        if s.get("dropped") or s.get("fixed"):
            out.append(f"- 버림 {' · '.join(s.get('dropped') or []) or '없음'} · 사람 고침 "
                       f"{' · '.join(s.get('fixed') or []) or '없음'}")
        out.append("")
        notes = None
        for c in cs:
            out += _body(c) + [""]
            notes = notes or (c.get("meta") or {}).get("notes")
        if notes:
            out += ["[노트]", "```text", str(notes).rstrip(), "```", ""]
    return out


def write(doc_id, env):
    """`export/split_<doc_id>.md`에 쓴다(원자 쓰기) — 쓴 자리 · 구조 블록이 없으면 None(쓰지 않는다)."""
    if not (env or {}).get("deck"):
        return None
    from core import paths
    from core.state import store
    p = paths.export(f"split_{doc_id}.md")
    paths.ensure(p)
    store.atomic_write_bytes(p, ("\n".join(lines(env)) + "\n").encode("utf-8"))
    return p
