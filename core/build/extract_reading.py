# -*- coding: utf-8 -*-
"""칸 3.3 — **판독을 추출에**(B170) — 쪽 문서(PPT · PDF)의 판독(봉투 `reading` — 칸 2.4)을 **판독이 있는 청크에만** 추출 입력에 싣는다.

    begin(env)            문서마다 한 번 — 쪽(슬라이드 · 쪽 번호) → 판독 칸(읽은 쪽만 · 지운 · 건너뛴 쪽은 없음)
    apply(unit)           한 호출 단위 → `(단위, [판독] 묶음 또는 None)` — 그림 청크의 글은 판독 그림 칸(첫 줄 · 그림 속 글자)으로 ·
                          묶음 = 쪽 요약 · 배치 · 단위에 그림 청크가 없는 그림의 칸
    system(tmpl, chunk)   판독이 있는 청크면 지시문 끝에 판독 절(`prompts/3.3_extract_reading.md`) · 없으면 그대로
    schema(base, chunk)   판독이 있는 청크면 소속 출처 `from` 닫힌 값에 `판독`
    doc_key(env)          재사용 열쇠의 판독 몫 — 읽은 쪽이 있을 때만(판독 칸 · 판독 절 판의 해시) · 없으면 None(열쇠 그대로)
    labels(src, doc)      소속 출처 재검사의 판독 몫 — 그 청크 쪽의 그림 속 글자(`doc_info`의 `reading`)

**판독이 없는 문서 · 청크는 바이트 그대로다**(사용자 2026-10-27 「추출 결과가 바뀌지 않는 관점으로」) — 지시문 · 사용자 글 · 답 꼴 ·
호출 열쇠 · 체크포인트 · 재사용 열쇠가 B170 전과 같다. 이름의 출처는 **그림 속 글자만**(외형으로 알아본 이름 — 첫 줄 · 보이는 것의
`추론` — 은 맥락이지 출처가 아니다 · 10-27 확정) · 값은 계속 본문 글자에서만. 실호출 입력만이다 — mock(문형 규칙)은 지금 그대로.
"""
from __future__ import annotations

import hashlib
import json

PROMPT = "extract_reading"
#: 이 문서의 판독 — `{(쪽 종류, 번호): 판독 칸}`
_PAGES = {}
#: 판독이 있는 청크의 표지(사용자 글에 나가지 않는 칸)
MARK = "_reading"
FIG = "_reading_fig"


def _read(e):
    return bool(e) and "source" in e and not e.get("deleted") and not e.get("skipped")


def _key_of(meta):
    m = meta or {}
    if m.get("slide") is not None:
        return ("slide", m["slide"])
    p = m.get("page") or m.get("page_no")
    return ("page", p) if p is not None else None


def pages_of(env):
    """`{(쪽 종류, 번호): 판독 칸}` — 읽은 쪽만(PPT는 슬라이드 번호 · PDF는 쪽 번호)."""
    out = {}
    for e in ((env or {}).get("reading") or {}).get("pages") or []:
        if _read(e):
            out[("slide", e["slide"]) if e.get("slide") is not None else ("page", e.get("page"))] = e
    return out


def begin(env):
    _PAGES.clear()
    _PAGES.update(pages_of(env))


def _fig_text(f):
    labels = " ".join(f"「{x}」" for x in f.get("labels") or [])
    return "\n".join(x for x in (f.get("what") or "", f"그림 속 글자: {labels}" if labels else "") if x)


def apply(unit):
    """`[(cid, 청크)]` → `(단위, 묶음)` — 판독이 없는 쪽이면 단위 그대로 · None."""
    e = next((_PAGES.get(_key_of(c.get("meta"))) for _cid, c in unit if _PAGES.get(_key_of(c.get("meta")))), None)
    if e is None:
        return unit, None
    figs = {f.get("box"): f for f in e.get("figures") or []}
    out, used = [], set()
    for cid, c in unit:
        f = figs.get(c.get("source_locator"))
        if f is not None:
            used.add(c.get("source_locator"))
            c = {**c, "text": _fig_text(f), FIG: True}
        out.append((cid, {**c, MARK: True}))
    lines = [f"- 쪽 요약: {' '.join(s.get('text') or '' for s in e.get('summary') or [])}"] if e.get("summary") else []
    if e.get("relations"):
        lines.append("- 배치: " + " · ".join(f"{r['from']} → {r['to']} {r['relation']}" for r in e["relations"]))
    lines += [f"- 그림 {b}: " + _fig_text(f).replace("\n", " · ") for b, f in figs.items() if b not in used]
    return out, ("[판독]\n" + "\n".join(lines)) if lines else None


def system(tmpl, chunk):
    if not chunk.get(MARK):
        return tmpl
    from core.llm import gateway
    body = gateway.prompt(PROMPT).split("---", 2)[-1].strip()       # 머리말 뒤 — 판은 열쇠가 본다
    return f"{tmpl}\n\n{body}"


def schema(base, chunk):
    if not chunk.get(MARK):
        return base
    s = json.loads(json.dumps(base))
    bel = s["properties"]["entities"]["items"]["properties"]["belongs_to"]["properties"]["from"]
    bel["enum"] = list(bel["enum"]) + ["판독"]
    return s


def version():
    from core.build.extract import prompt_version
    return prompt_version(PROMPT)


def doc_key(env):
    ps = pages_of(env)
    if not ps:
        return None
    raw = json.dumps([version(), sorted(([k[0], k[1], {f: e.get(f) for f in ("figures", "relations", "summary")}]
                                         for k, e in ps.items()), key=lambda x: (x[0], x[1]))],
                     ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def doc_labels(env):
    """`doc_info`의 `reading` 칸 — `{"slide:N" | "page:N": [그림 속 글자 …]}` · 읽은 쪽이 없으면 None."""
    out = {f"{k[0]}:{k[1]}": [x for f in e.get("figures") or [] for x in f.get("labels") or []]
           for k, e in pages_of(env).items()}
    return {k: v for k, v in out.items() if v} or None


def labels(src, doc):
    k = _key_of((src or {}).get("meta"))
    return ((doc or {}).get("reading") or {}).get(f"{k[0]}:{k[1]}") or [] if k else []
