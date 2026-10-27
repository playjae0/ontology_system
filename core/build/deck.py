# -*- coding: utf-8 -*-
"""칸 2.4 · ⑪ — **덱 구조**(B125 ③ · B151 ①) — PPT 덱 한 벌을 한 번에 보고 슬라이드마다 제목 · 구획 · 이어짐 · 다루는 것 ·
다루는 공정(문서 표기) · 개체 없음과 덱 개요를 정한다(지점 ⑪ 문서 구조의 PPT 입력 꼴 — 호출 태그 `deck` · 지시문 `2.4_deck.md`).

    입력  슬라이드마다 상자 글(시각 순서 · placeholder 제목 표시 = 힌트) · 노트 앞부분 · 표 · 차트 머리 + 앞 묶음 판단의 끝
          — **층 · 골격 · 문서 좌표를 모른다**(메타는 층과 무관하다 — B148 대전제 · B151 ①)
    출력  {slides: [{slide, title, section, continues, subject, processes, no_entities}], overview}
    검사  제목은 그 슬라이드 상자 글 안 · 다루는 것의 명사구는 그 슬라이드(이어짐이면 묶음) 글 안 · 구획 · 공정 표기는 덱 글 안 ·
          이어짐은 앞 슬라이드 — 어긋난 것만 버리고 결함 로그(코드는 검사만) · 버린 칸은 그 슬라이드 판단의 `dropped`에

**공정은 참고값이다**(B151 ②) — 문서에 적힌 표기 그대로(골격 이름으로 바꾸지 않는다) · 골격에 거는 일은 표와 같은 길(파서의
좌표 태깅 → 그래프 단계 해소)이 한다. 파서는 LLM을 부르지 않으므로 이 함수가 주입된다(`cli.parse.injections`) · mock은 힌트
`<doc_id>@deck.json`만(없으면 판정 없음 — 지금 방식).
"""
from __future__ import annotations

import json

from core.build import structure as ST
from core.llm import gateway
from core.state import fixtures as _fx
from core.state import log, store
from core.state.ids import norm

_LOG = log.get(__name__)

PROMPT = "deck"
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
                           "subject": {"type": ["string", "null"]},
                           "processes": {"type": "array", "items": {"type": "string"}},
                           "no_entities": {"type": "boolean"}},
            "required": ["slide", "title", "section", "continues", "subject", "processes", "no_entities"],
            "additionalProperties": False}},
        "overview": {"type": "string"}},
    "required": ["slides", "overview"], "additionalProperties": False,
}

#: 덱 개요의 글자 상한 — 맥락 줄의 칸이라 한 단락(창작 기본값)
OVERVIEW_CHARS = 600
#: 다루는 것 · 공정 표기의 이음 — 명사구가 여럿이면 이것으로(맥락 줄 · 화면과 같은 이음)
JOIN = " · "


def key():
    """보존분 재사용의 판 — **덱 지시문 판(`2.4_deck.md`)만**(B151 ① — 입력에 층 · 골격이 없어 층 config · 골격을 바꿔도 다시 묻지
    않는다 · 입력은 보존분의 `labels`가 잰다)."""
    from core.build.extract import prompt_version
    return {"prompt_version": prompt_version(PROMPT)}


def _boxes_text(s):
    return "\n".join(b.get("text") or "" for b in s.get("boxes") or [] if b.get("kind") not in ("table", "chart"))


def deck_text(slides):
    """**덱 글** — 구획 · 공정 표기 검사의 자리(덱 판단의 검사 · 사람의 공정 고침이 같은 글 · 같은 정규화)."""
    return norm("\n".join(_boxes_text(s) for s in slides))


def in_text(phrase, text):
    """표기가 글 안인가(같은 정규화 — 구획 검사와 같은 손)."""
    return isinstance(phrase, str) and bool(phrase.strip()) and norm(phrase) in text


def _phrases(v):
    return [x.strip() for x in str(v or "").split(JOIN.strip()) if x.strip()]


def check(doc_id, slides, ans):
    """검사(결정적) — `{slides: {번호: 판단}, overview, dropped: {칸: 수}}` · 어긋난 것만 버린다(결함 로그)."""
    by = {s["slide"]: s for s in slides}
    order = [s["slide"] for s in slides]
    whole = deck_text(slides)
    out, drop = {}, {"슬라이드": 0, "제목": 0, "구획": 0, "이어짐": 0, "다루는 것": 0, "공정": 0}
    drops = {}                                     # 슬라이드마다 버린 칸 — 봉투 덱 블록의 `dropped`(B143 ②)

    def bad(what, n, why):
        drop[what] += 1
        drops.setdefault(n, []).append(what)
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
            if in_text(sec, whole):
                d["section"] = sec.strip()
            else:
                bad("구획", n, f"'{sec[:40]}'가 덱 글에 없다")
        c = a.get("continues")
        if c is not None:
            if c in by and order.index(c) < order.index(n):
                d["continues"] = c
            else:
                bad("이어짐", n, f"{c}는 앞 슬라이드가 아니다")
        # 다루는 것 — 명사구마다 그 슬라이드(이어짐이면 이어진 묶음) 글 안 · 밖인 것만 버린다
        group = norm("\n".join(_boxes_text(by[k]) for k in _chain(n, d.get("continues"), out)))
        sub = _phrases(a.get("subject"))
        keep = [x for x in sub if in_text(x, group)]
        if len(keep) < len(sub):
            bad("다루는 것", n, " · ".join(x for x in sub if x not in keep) + " — 그 슬라이드 글에 없다")
        if keep:
            d["subject"] = JOIN.join(dict.fromkeys(keep))
        # 공정 — **문서 표기 그대로**(골격에 거는 것은 파서의 좌표 태깅 · 그래프 단계) · 표기마다 덱 글 안 · 밖인 것만 버린다
        procs = [p.strip() for p in a.get("processes") or [] if isinstance(p, str) and p.strip()]
        ok = [p for p in procs if in_text(p, whole)]
        if len(ok) < len(procs):
            bad("공정", n, " · ".join(p for p in procs if p not in ok) + " — 덱 글에 없다")
        if isinstance(a.get("processes"), list):
            d["processes"] = list(dict.fromkeys(ok))
        if a.get("no_entities") is True:
            d["no_entities"] = True
        if drops.get(n):
            d["dropped"] = list(drops[n])
        out[n] = d
    ov = " ".join(str((ans or {}).get("overview") or "").split())[:OVERVIEW_CHARS] or None
    return {"slides": out, "overview": ov, "dropped": {k: v for k, v in drop.items() if v}}


def _chain(n, cont, out):
    """그 슬라이드와 이어진 앞 슬라이드들(이어짐 사슬 — 검사가 이미 받은 이어짐만)."""
    seq, cur = [n], cont
    while cur is not None and cur not in seq and len(seq) < 64:
        seq.append(cur)
        cur = (out.get(cur) or {}).get("continues")
    return seq


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


def _live(doc_id, slides):
    """덱 한 벌 — 묶음마다 한 호출 · 뒤 묶음에는 앞 판단의 끝(제목 · 구획 · 다루는 것 · 공정)을 넘긴다 · 지시문은 층 힌트 없이
    (B151 ① — 층 어휘 0 · 일반 지식만). 실패면 `(None, 호출 수, 사유)`."""
    got, overview, calls, prev = [], "", 0, None
    for batch in _batches(slides):
        try:
            out = gateway.chat(
                [{"role": "system", "content": gateway.prompt(PROMPT)},
                 {"role": "user", "content": json.dumps({"deck": True, "previous": prev, "slides": batch},
                                                        ensure_ascii=False)}],
                json_schema=SCHEMA, point=TAG)
        except Exception as e:                                       # noqa: BLE001 — 그 덱은 지금 방식
            store.append_defect(f"{doc_id}: 덱 구조 호출 실패 — {type(e).__name__}: {e} → 지금 방식")
            return None, calls + 1, f"{type(e).__name__}: {e}"
        calls += 1
        got += out.get("slides") or []
        overview = overview or out.get("overview") or ""
        last = (out.get("slides") or [None])[-1]
        prev = ({k: last.get(k) for k in ("slide", "title", "section", "subject", "processes")} if last else prev)
    return {"slides": got, "overview": overview}, calls, None


def hint_answer(doc_id):
    """mock 힌트 `<doc_id>@deck.json` — 없으면 None(판정 없음 · 지금 방식)."""
    p = _fx.EXTRACT_HINTS / f"{doc_id}@deck.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def decker():
    """파서에 내려보낼 **덱 구조 함수** `fn(doc_id, slides)` — 실호출이면 ⑪(태그 `deck`) · mock이면 힌트 · 돌려주는 것은 검사가
    끝난 판단 또는 None(판정 없음). `fn.key()`가 보존분의 판이다 · 층 인자 없음(B151 ①)."""
    live = not gateway.use_mock()

    def fn(doc_id, slides):
        if live:
            gateway.require(TAG)
            ans, calls, failed = _live(doc_id, slides)
            if failed:
                return {"slides": {}, "overview": None, "dropped": {}, "calls": calls, "failed": failed,
                        "source": "live", **gateway.prompt_stamp(PROMPT)}
            source = "live"
        else:
            ans, calls, source = hint_answer(doc_id), 0, "hint"
            if ans is None:
                return None
        out = check(doc_id, slides, ans)
        _LOG.info("덱 구조 %s — 슬라이드 %d · 버림 %s · 호출 %d", doc_id, len(out["slides"]), out["dropped"], calls)
        return {**out, "calls": calls, "source": source, **gateway.prompt_stamp(PROMPT)}   # 판 · 문면 해시 (B135 ③)
    fn.key = key
    fn.drift = lambda rec: gateway.prompt_drift(PROMPT, rec)     # 보존분을 다시 쓸 때 — 판 그대로 · 문면만 바뀜 한 줄
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
