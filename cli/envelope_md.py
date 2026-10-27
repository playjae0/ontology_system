# -*- coding: utf-8 -*-
"""칸 0.3 — **봉투 → 사람용 md**(B143 ④) — parsed JSON(봉투) **하나만** 읽어 `export/split_<doc_id>.md`를 찍는 포맷 공통 꼴.

md는 보기다 — **md에만 있는 정보 0** · LLM은 md를 읽지 않는다(호출 입력은 봉투에서 조립한다). 꼴은 포맷을 가리지 않는다:

    머리      문서 · 단위 수 · 조각 수 · 문서 좌표 · 개요 · 캡처
    단위 표   단위마다 한 줄 — 번호 · 제목(초안 → 판단) · 이어짐 · 다루는 것 · 공정(문서 표기 → 골격) · 개체 없음 · 근거 조각 · 글자
    단위마다  경로 · 공정 · 쪽 · 버림 · 사람 고침 + 근거 조각 원문(`[본문]` · `[표 …]` · `[차트 …]` · `[그림 요약 …]` — 묶음 머리는
              추출 입력과 같은 손 `core/build/extract_unit._tag`) · `[노트]`(한 번) · `[판독]`(쪽 판독 — `cli/reading_md` · B156 ⑥)

단위 표의 판단 칸은 봉투의 블록이 준다 — PPT는 덱 블록(`deck.slides[]` — B143 ②) · 엑셀 · Word는 구조 블록(`structure.units[]` —
B146 ① · 시트마다 목차 나무 · 청크 경계 · 판단 기록 — 꼴은 `cli/split_report.md_lines`의 시트 덩어리)이고, 두 블록은 같은 읽기 함수
(`units` — 단위 → 그 근거 청크)로 읽힌다 · 블록이 없는 봉투는 쓰지 않는다(None). 쓰는 자리는 이 모듈의 `write` 하나 · 부르는 자리는
`cli/structure_screen`(인입 · `--split-only` · 배치 · 재구축 · 구조 확인 관문이 같은 길) — 보고 · 캐시를 읽지 않는다(B146 ②).
"""
from __future__ import annotations

from pathlib import PurePath

from cli import reading_md as RM


def _cell(x):
    return str(x if x not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def procs_cell(s):
    """공정 칸(덱 블록 슬라이드 하나) — 문서 표기 그대로 · 골격에 맞은 표기는 `표기 → canonical`(블록의 `matched` — 태깅과 같은 색인) ·
    안 맞은 표기는 `표기(?)`(그래프 단계에서 해소 · 큐) · None = 판정 없음(—) · [] = 없음 (B151 ④). 화면 · md가 이 손 하나."""
    ps = s.get("processes")
    if ps is None:
        return "—"
    got = list(s.get("matched") or []) + [None] * len(ps)
    return " · ".join((p if c == p else f"{p} → {c}") if c else f"{p}(?)" for p, c in zip(ps, got)) or "없음"


def _title(s, chunks):
    draft, judged = s.get("title_draft"), s.get("title")
    base = judged or draft or next((c.get("section") for c in chunks if c.get("section")), None) or "—"
    if judged and draft and judged != draft:
        base = f"{draft} → {judged}"
    elif judged and not draft:
        base = f"(없음) → {judged}"
    return base + ("*" if s.get("fixed") else "")


#: 봉투의 판단 블록 — 블록 이름 → 단위 목록 칸(B146 ① — 두 블록이 같은 꼴: 단위 → 판단 + 청크 위치 `chunks`)
BLOCKS = {"deck": "slides", "structure": "units"}


def units(env, kind=None):
    """`[(단위 판단, [청크 …])]` — 블록(`kind` — `deck` · `structure` · None이면 둘 다)의 단위마다 그 근거 청크(블록이 든 위치 차례
    그대로) · 블록이 없으면 빈 목록. 덱 블록의 슬라이드와 구조 블록의 단위(시트 · Word 구획)를 같은 함수가 읽는다."""
    by = {c.get("source_locator"): c for c in env.get("chunks") or []}
    return [(s, [by[x] for x in s.get("chunks") or [] if x in by])
            for k, f in BLOCKS.items() if kind in (None, k) for s in ((env.get(k) or {}).get(f)) or []]


def _body(c):
    from core.build.extract_unit import _tag
    head = _tag(c) or "[본문]"
    return [head, "```text", (c.get("text") or "").rstrip(), "```"]


def lines(env):
    """봉투 → md 줄들(봉투 밖을 읽지 않는다)."""
    doc_id = env.get("doc_id")
    us = units(env, "deck")
    chunks = env.get("chunks") or []
    src = env.get("source_path")
    dk = env.get("deck") or {}
    cap = (env.get("capture") or {}).get("pages")
    out = [f"# 구조 확인 — {doc_id}", "",
           f"- 문서 {PurePath(str(src)).name if src else '—'} · 슬라이드 {len(us)} · 조각 {len(chunks)} · "
           f"문서 좌표 {env.get('doc_coord') or '없음'}",
           f"- 덱 개요 — {dk.get('overview') or '없음'}"]
    if cap:
        out.append(f"- 캡처 — 보이는 쪽 {cap}(문서마다 한 번 뜬다 · 보관은 손잡이 keep_page_captures — ④작업 work/captures/)")
    if RM.head(env):
        out.append(RM.head(env))                        # 쪽 판독 (B156 ⑥ — [그림 요약]과 나란히)
    out += ["", "## 슬라이드 표", "",
            "| 번호 | 제목(초안 → 판단) | 이어짐 | 다루는 것 | 공정 | 개체 없음 | 근거 조각 | 글자 |",
            "|---:|---|---:|---|---|---|---:|---:|"]
    for s, cs in us:
        out.append("| " + " | ".join(_cell(x) for x in (
            s.get("slide"), _title(s, cs), s.get("continues"), s.get("subject"), procs_cell(s),
            "예" if s.get("no_entities") else "",
            len(cs), sum(len(c.get("text") or "") for c in cs))) + " |")
    out += ["", "공정 — 문서 표기 그대로 · `표기 → 골격` = 골격에 맞았다 · `표기(?)` = 안 맞았다(그래프 단계에서 해소 · 큐) · "
                "— = 판정 없음 · 없음 = 공정을 말하지 않는다(둘 다 경로 · 문서 좌표) · * = 사람이 고친 칸이 있다", ""]
    for s, cs in us:
        m0 = (cs[0].get("meta") or {}) if cs else {}
        out += [f"## 슬라이드 {s.get('slide')} — {_title(s, cs)}", "",
                f"- 쪽 {s.get('page')} · 경로 {m0.get('section_path') or '—'} · 다루는 것 {s.get('subject') or '—'} · "
                f"공정 {procs_cell(s)}"
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
        out += RM.block(env, RM.entry(env, slide=s.get("slide")))
    return out


def text(doc_id, env):
    """봉투 → md 글 전체(쓰지 않는다) — 구조 블록(엑셀 · Word)이면 시트 덩어리(`split_report.md_lines`) · 덱 블록(PPT)이면 위 꼴 ·
    블록이 없으면 None."""
    env = env or {}
    if env.get("deck"):
        ls = lines(env)
    elif env.get("structure"):
        from cli import split_report as SR
        ls = SR.md_lines(doc_id, env)
    elif env.get("reading"):
        ls = RM.page_md(doc_id, env)                     # 덱 블록이 없는 쪽 문서(PDF) — 쪽마다 원문 + [판독] (B156 ⑥)
    else:
        return None
    return "\n".join(ls) + "\n" if ls else None


def save(name, body):
    """사람용 md를 `export/<name>`에 쓰는 **한 자리**(원자 쓰기 — 구조 확인 md · 추출 확인 md `cli/extract_md` · B155 ②) — 쓴 자리."""
    from core import paths
    from core.state import store
    p = paths.export(name)
    paths.ensure(p)
    store.atomic_write_bytes(p, body.encode("utf-8"))
    return p


def write(doc_id, env):
    """`export/split_<doc_id>.md`에 쓴다(원자 쓰기) — 쓴 자리 · 블록이 없으면 None(쓰지 않는다)."""
    body = text(doc_id, env)
    return None if body is None else save(f"split_{doc_id}.md", body)
