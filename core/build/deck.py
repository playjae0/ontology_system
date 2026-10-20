# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **덱 구조**(B125 ③) — PPT 덱 한 벌을 한 번에 보고 슬라이드마다 제목 · 구획 · 이어짐 · 다루는 공정 ·
언급 공정 · 개체 없음과 덱 개요를 정한다(지점 ⑪ 문서 구조의 PPT 입력 꼴 — 호출 태그 `deck` · 지시문 `3.3_outline.md`).

    입력  슬라이드마다 상자 글(시각 순서 · placeholder 제목 표시 = 힌트) · 노트 앞부분 · 표 · 차트 머리
          + 문서 좌표(있으면 힌트) + 골격 닫힌 목록 + 층 힌트(`prompts.structure`)
    출력  {slides: [{slide, title, section, continues, processes, mentions, no_entities}], overview}
    검사  제목은 그 슬라이드 상자 글 안 · 구획은 덱 글 안 · 이어짐은 앞 슬라이드 · 공정 · 언급은 골격 닫힌 목록 안
          (하나라도 밖이면 그 슬라이드의 공정은 지금 방식) — 어긋나면 그 칸만 버리고 결함 로그(코드는 검사만)

**LLM이 보고 판단한다** — placeholder 제목 · 문서 좌표는 힌트이고 강제하지 않는다. 파서는 LLM을 부르지 않으므로 이 함수가
주입된다(`cli.parse.injections` — 문서 구조와 같은 결) · mock은 힌트 `<doc_id>@deck.json`만(없으면 판정 없음 — 지금 방식).
"""
from __future__ import annotations

import json

from core.build import structure as ST
from core.llm import gateway
from core.state import fixtures as _fx
from core.state import log, store
from core.state.ids import norm

_LOG = log.get(__name__)

PROMPT = "outline"
TAG = "deck"

SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {"type": "array", "items": {
            "type": "object",
            "properties": {"slide": {"type": "integer"},
                           "title": {"type": ["string", "null"]},
                           "section": {"type": ["string", "null"]},
                           "continues": {"type": ["integer", "null"]},
                           "processes": {"type": "array", "items": {"type": "string"}},
                           "mentions": {"type": "array", "items": {"type": "string"}},
                           "no_entities": {"type": "boolean"}},
            "required": ["slide", "title", "section", "continues", "processes", "mentions", "no_entities"],
            "additionalProperties": False}},
        "overview": {"type": "string"}},
    "required": ["slides", "overview"], "additionalProperties": False,
}

#: 덱 개요의 글자 상한 — 맥락 줄의 칸이라 한 단락(창작 기본값)
OVERVIEW_CHARS = 600


def _closed():
    from core.state.bootstrap import coord_layer
    from parser import tagger
    nodes = tagger.closed_list(coord_layer())
    return nodes, tagger.scoped_index(nodes)[0]


def key(cfgs):
    """보존분 재사용의 판 — 덱 지시문 판(`3.3_outline.md`) · 층 config 추출 칸 · 골격 닫힌 목록 판(산문 구조의 판 · 방식과 무관 — B132)."""
    from core.build.extract import prompt_version
    from core.state import config_scope
    from parser import tagger
    nodes, _idx = _closed()
    return {"prompt_version": prompt_version(PROMPT),
            "config_extract": " · ".join(f"{k}:{config_scope.extract_key(c)}" for k, c in sorted(cfgs.items())),
            "skeleton": tagger.list_version(nodes)}


def _canon(name, idx):
    from parser import tagger
    if not isinstance(name, str) or not name.strip():
        return None
    n = idx.get(name.strip()) or tagger.fold_hit(name.strip(), idx)
    return n["canonical"] if n else None


def _boxes_text(s):
    return "\n".join(b.get("text") or "" for b in s.get("boxes") or [] if b.get("kind") not in ("table", "chart"))


def check(doc_id, slides, ans, idx):
    """검사(결정적) — `{slides: {번호: 판단}, overview, dropped: {칸: 수}}` · 어긋난 칸만 버린다(결함 로그)."""
    by = {s["slide"]: s for s in slides}
    order = [s["slide"] for s in slides]
    deck_text = norm("\n".join(_boxes_text(s) for s in slides))
    out, drop = {}, {"슬라이드": 0, "제목": 0, "구획": 0, "이어짐": 0, "공정": 0, "언급": 0}

    def bad(what, n, why):
        drop[what] += 1
        store.append_defect(f"{doc_id}: 덱 구조 — 슬라이드 {n} {what} 버림({why}) → 지금 방식")

    for a in (ans or {}).get("slides") or []:
        n = a.get("slide")
        if n not in by or n in out:
            drop["슬라이드"] += 1
            continue
        d = {}
        t = a.get("title")
        if isinstance(t, str) and t.strip():
            if norm(t) in norm(_boxes_text(by[n])):
                d["title"] = t.strip()
            else:
                bad("제목", n, f"'{t[:40]}'가 그 슬라이드 글에 없다")
        sec = a.get("section")
        if isinstance(sec, str) and sec.strip():
            if norm(sec) in deck_text:
                d["section"] = sec.strip()
            else:
                bad("구획", n, f"'{sec[:40]}'가 덱 글에 없다")
        c = a.get("continues")
        if c is not None:
            if c in by and order.index(c) < order.index(n):
                d["continues"] = c
            else:
                bad("이어짐", n, f"{c}는 앞 슬라이드가 아니다")
        procs = [p for p in a.get("processes") or [] if isinstance(p, str) and p.strip()]
        canon = [_canon(p, idx) for p in procs]
        if any(x is None for x in canon):
            bad("공정", n, " · ".join(p for p, x in zip(procs, canon) if x is None) + " 골격 밖")
        else:
            d["processes"] = list(dict.fromkeys(canon))
        ms = [(m, _canon(m, idx)) for m in a.get("mentions") or [] if isinstance(m, str) and m.strip()]
        for m, x in ms:
            if x is None:
                bad("언급", n, f"'{m}' 골격 밖")
        d["mentions"] = [x for x in dict.fromkeys(x for _m, x in ms if x) if x not in (d.get("processes") or [])]
        if a.get("no_entities") is True:
            d["no_entities"] = True
        out[n] = d
    ov = " ".join(str((ans or {}).get("overview") or "").split())[:OVERVIEW_CHARS] or None
    return {"slides": out, "overview": ov, "dropped": {k: v for k, v in drop.items() if v}}


# ---------------------------------------------------------------- 실호출 · mock
def _batches(slides):
    """한 호출에 실을 슬라이드 묶음 — 어림 토큰(JSON 글자 / 2)이 `structure.CALL_TOKENS`를 넘기 전에 끊는다."""
    out, cur, size = [], [], 0
    for s in slides:
        t = len(json.dumps(s, ensure_ascii=False)) // 2
        if cur and size + t > ST.CALL_TOKENS:
            out.append(cur)
            cur, size = [], 0
        cur.append(s)
        size += t
    return out + ([cur] if cur else [])


def _live(doc_id, slides, doc_coord, nodes, cfgs):
    """덱 한 벌 — 묶음마다 한 호출 · 뒤 묶음에는 앞 판단의 끝(제목 · 구획 · 공정)을 넘긴다. 실패면 `(None, 호출 수, 사유)`."""
    procs = [{"name": n["canonical"], "parent": n.get("parent"), "aliases": n.get("aliases") or []} for n in nodes]
    got, overview, calls, prev = [], "", 0, None
    for batch in _batches(slides):
        try:
            out = gateway.chat(
                [{"role": "system", "content": gateway.prompt_for(PROMPT, cfgs or {}, "structure")},
                 {"role": "user", "content": json.dumps(
                     {"deck": True, "processes": procs, "doc_coord": doc_coord, "previous": prev,
                      "slides": batch}, ensure_ascii=False)}],
                json_schema=SCHEMA, point=TAG)
        except Exception as e:                                       # noqa: BLE001 — 그 덱은 지금 방식
            store.append_defect(f"{doc_id}: 덱 구조 호출 실패 — {type(e).__name__}: {e} → 지금 방식")
            return None, calls + 1, f"{type(e).__name__}: {e}"
        calls += 1
        got += out.get("slides") or []
        overview = overview or out.get("overview") or ""
        last = (out.get("slides") or [None])[-1]
        prev = ({k: last.get(k) for k in ("slide", "title", "section", "processes")} if last else prev)
    return {"slides": got, "overview": overview}, calls, None


def hint_answer(doc_id):
    """mock 힌트 `<doc_id>@deck.json` — 없으면 None(판정 없음 · 지금 방식)."""
    p = _fx.EXTRACT_HINTS / f"{doc_id}@deck.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def decker(layers=None):
    """파서에 내려보낼 **덱 구조 함수** `fn(doc_id, slides, doc_coord=None)` — 실호출이면 ⑪(태그 `deck`) · mock이면 힌트 ·
    돌려주는 것은 검사가 끝난 판단 또는 None(판정 없음). `fn.key()`가 보존분의 판이다."""
    cfgs = ST._cfgs(layers)
    live = not gateway.use_mock()

    def fn(doc_id, slides, doc_coord=None):
        from core.build.extract import prompt_version
        nodes, idx = _closed()
        if live:
            gateway.require(TAG)
            ans, calls, failed = _live(doc_id, slides, doc_coord, nodes, cfgs)
            if failed:
                return {"slides": {}, "overview": None, "dropped": {}, "calls": calls, "failed": failed,
                        "source": "live", "prompt_version": prompt_version(PROMPT)}
            source = "live"
        else:
            ans, calls, source = hint_answer(doc_id), 0, "hint"
            if ans is None:
                return None
        out = check(doc_id, slides, ans, idx)
        _LOG.info("덱 구조 %s — 슬라이드 %d · 버림 %s · 호출 %d", doc_id, len(out["slides"]), out["dropped"], calls)
        return {**out, "calls": calls, "source": source, "prompt_version": prompt_version(PROMPT)}
    fn.key = lambda: key(cfgs)
    return fn


# ---------------------------------------------------------------- 사람의 고침 (구조 표 — 등록 단)
FRAME = "@덱"


def record_fix(doc_id, slide, fix):
    """덱 고침 한 칸 — `registry/structure_fixes.json`의 `@덱` 프레임(슬라이드 번호 · 0 = 덱 개요) · 같은 슬라이드는 칸을 합친다."""
    from datetime import datetime, timezone
    from core import paths
    d = ST._fixes_all()
    row = d.setdefault(doc_id, {}).setdefault(FRAME, {}).setdefault(str(slide), {})
    row.update({**fix, "by": "사람", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    p = ST.fixes_path()
    paths.ensure(p)
    store.atomic_write_bytes(p, (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
