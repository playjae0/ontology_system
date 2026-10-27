# -*- coding: utf-8 -*-
"""칸 0.3 — **판독 블록 → 사람용 줄**(B156 ⑥) — 봉투의 판독 블록(`reading.pages[]`)과 상자 목록(`boxes`)**만** 읽는다(md에만 있는 정보 0).

    head(env)            md 머리 한 줄 — 쪽 · 판독 · 그림 · 관계 · 지움 · 건너뜀 · 지시문 판 · 읽기 지식
    block(env, e)        쪽 하나의 [판독] 블록 — 그림마다(종류 · 그림 속 글자 · 보이는 것 보임/추론 · 의미) · 배치 관계 · 쪽 요약(근거 상자) ·
                         버림 · 사람 고침 · 캡처 링크(보관분 — md 자리에서 상대 경로)
    page_md(doc_id, env) PDF처럼 덱 블록이 없는 쪽 문서 — 쪽마다 원문 + [판독]

split md(`cli/envelope_md`)의 슬라이드 절 · PDF 쪽 md · `--step` 판독 표(`cli/reading_screen`)가 같은 줄을 쓴다 — 지금 [그림 요약] 블록은
그대로 두고 나란히 본다(판독은 메타에 더하기만 — 추출 입력 불변).
"""
from __future__ import annotations

#: md(`export/`)에서 상태 루트 기준 표기로 가는 앞머리 — md는 `$ONTO_HOME/export/`에 산다
_UP = "../"


def pages(env):
    return ((env or {}).get("reading") or {}).get("pages") or []


def entry(env, *, slide=None, page=None):
    """그 슬라이드(또는 쪽)의 판독 칸 — 없으면 None."""
    return next((e for e in pages(env) if (slide is not None and e.get("slide") == slide)
                 or (slide is None and e.get("page") == page)), None)


def head(env):
    rd = (env or {}).get("reading") or {}
    ps = pages(env)
    if not ps:
        return None
    got = [e for e in ps if "source" in e]
    return (f"- 판독 — 쪽 {len(ps)} · 판독 {len(got)} · 그림 {sum(len(e.get('figures') or []) for e in got)} · "
            f"관계 {sum(len(e.get('relations') or []) for e in got)} · 지움 {sum(1 for e in ps if e.get('deleted'))} · "
            f"건너뜀 {sum(1 for e in ps if e.get('skipped') and not e.get('deleted'))} · 지시문 판 {rd.get('prompt_version') or '—'} · "
            f"읽기 지식 {'있음' if rd.get('knowledge') else '없음'}")


def short(e, n=48):
    """판독 표 · md의 쪽 요약 앞부분."""
    if e.get("deleted"):
        return "(지움)"
    if e.get("skipped"):
        return f"(건너뜀 — {e['skipped']})"
    t = " ".join(s.get("text") or "" for s in e.get("summary") or [])
    return (t[:n] + "…") if len(t) > n else (t or "—")


def _fig(f):
    labels = " ".join(f"「{x}」" for x in f.get("labels") or []) or "없음"
    inside = f.get("labels_in_text") or []
    out = [f"- 그림 {f.get('box')} — 종류 {f.get('kind') or '—'} · 그림 속 글자 {labels}"
           + (f"(상자 글에도: {' · '.join(inside)})" if inside else "") + (" · 읽을 수 없음" if f.get("unreadable") else "")]
    out += [f"  - {s['basis']}: {s['text']}" for s in f.get("seen") or []]
    if f.get("meaning"):
        out.append(f"  - 의미(추론): {f['meaning']}")
    return out


def block(env, e):
    """쪽 하나의 [판독] 블록 줄들(봉투 밖을 읽지 않는다)."""
    if e is None:
        return []
    if e.get("deleted"):
        return ["[판독] 지움(사람 — 이 장 판독을 쓰지 않는다)", ""]
    if e.get("skipped"):
        return [f"[판독] 건너뜀 — {e['skipped']}", ""]
    out = [f"[판독] 출처 {e.get('source') or '—'}" + (" · 재사용" if e.get("reused") else "")
           + (f" · 사람 힌트 「{e['hint']}」" if e.get("hint") else "") + (f" · 실패 {e['failed']}" if e.get("failed") else "")]
    if e.get("capture"):
        out.append(f"- 캡처 [쪽 {e.get('page')}]({_UP}{e['capture']})")
    for f in e.get("figures") or []:
        out += _fig(f)
    for r in e.get("relations") or []:
        out.append(f"- 배치 — {r['from']} → {r['to']} {r['relation']}")
    for s in e.get("summary") or []:
        out.append(f"- 쪽 요약 — {s['text']} (근거 {' · '.join(s.get('boxes') or [])})")
    if e.get("dropped"):
        out.append("- 버림 — " + " · ".join(f"{k} {v}" for k, v in e["dropped"].items()))
    return out + [""]


def page_md(doc_id, env):
    """덱 블록이 없는 쪽 문서(PDF)의 md 줄들 — 쪽마다 원문(그 쪽 청크) + [판독] · 판독 블록이 없으면 None."""
    from pathlib import PurePath
    from cli.envelope_md import _body
    if not pages(env):
        return None
    src = env.get("source_path")
    by = {}
    for c in env.get("chunks") or []:
        m = c.get("meta") or {}
        by.setdefault(m.get("page") or m.get("slide"), []).append(c)
    out = [f"# 구조 확인 — {doc_id}", "", f"- 문서 {PurePath(str(src)).name if src else '—'} · 쪽 {len(pages(env))} · "
           f"조각 {len(env.get('chunks') or [])} · 문서 좌표 {env.get('doc_coord') or '없음'}", head(env), ""]
    for e in pages(env):
        out += [f"## 쪽 {e['page']}", ""]
        for c in by.get(e["page"]) or []:
            out += _body(c) + [""]
        out += block(env, e)
    return out
