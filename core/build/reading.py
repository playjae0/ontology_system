# -*- coding: utf-8 -*-
"""칸 2.4 · ④ — **쪽 판독**(B156 ② ④ — 지점 ④ 그림 · 쪽 판독의 판독 몫 · 호출 태그 `reading` · 지시문 `2.4_reading.md`) — 쪽 문서(PPT ·
PDF)의 한 쪽을 캡처 · 그림 원본 · 상자 목록 · 덱 판단의 그 장 칸으로 읽어 그림마다 · 배치 관계 · 쪽 요약을 낸다.

    입력  쪽 캡처(주 입력) + 그 쪽 그림 원본 + 상자 목록 + 덱 판단의 그 장 칸(PPT) + 앞 장 쪽 요약(이어진 장) + 읽기 지식 + 사람 힌트
          — **층 config · 골격 목록 0**(메타는 층과 무관하다 — B148 대전제)
    출력  {figures: [{box, kind, labels, seen: [{text, basis}], meaning, unreadable}], relations: [{from, to, relation}],
           summary: [{text, boxes}]}
    검사  상자 id 실재 · 종류 · 관계 이름은 닫힌 목록 · 보이는 것의 근거는 보임/추론 · 요약 문장마다 근거 id ≥ 1 — 어긋난 칸만 버리고
          결함 로그(코드는 검사만) · 그림 속 글자는 그 쪽 상자 글에 있으면 `labels_in_text`에 표시(없어도 버리지 않는다)

**읽기 지식**(④ — `registry/reading_knowledge.md` · 등록 단 사람 자산 하나 · 층 무관 · 없으면 일반 지식만)은 지시문 끝에 붙고 그
해시가 보존 열쇠에 든다(고치면 그 뒤 판독은 다시 부른다). 파서는 LLM을 부르지 않으므로 이 함수가 주입된다(`cli.parse.injections`) ·
mock은 힌트 `<doc_id>@reading.json`(`{"pages": {"<쪽>": 답}}` · 사람 힌트가 있으면 그 쪽의 `again`)만 — 없으면 판독 없음.
사람의 고침(`<쪽> 다시 <힌트>` · `<쪽> 지움`)은 `registry/structure_fixes.json`의 `@판독` 프레임(덱 고침 `@덱`과 같은 파일 · 같은 손).
"""
from __future__ import annotations

import hashlib
import json

from core.llm import gateway
from core.state import fixtures as _fx
from core.state import log, store
from core.state.ids import norm

_LOG = log.get(__name__)

PROMPT = "reading"
TAG = "reading"
FRAME = "@판독"
#: 읽기 지식 파일 — 등록 단 사람 자산(레포에는 빈 틀 `kit/읽기지식_틀.md`)
KNOWLEDGE = "reading_knowledge.md"
KINDS = ("사진", "도면", "그래프", "흐름도", "스크린샷", "전후 비교", "그 밖")
RELATIONS = ("설명", "가리킴", "라벨", "전후 비교", "순서", "원인→결과", "비교")
BASIS = ("보임", "추론")

SCHEMA = {
    "type": "object",
    "properties": {
        "figures": {"type": "array", "items": {
            "type": "object",
            "properties": {"box": {"type": "string"}, "kind": {"type": "string"},
                           "labels": {"type": "array", "items": {"type": "string"}},
                           "seen": {"type": "array", "items": {
                               "type": "object", "properties": {"text": {"type": "string"}, "basis": {"type": "string"}},
                               "required": ["text", "basis"], "additionalProperties": False}},
                           "meaning": {"type": ["string", "null"]}, "unreadable": {"type": "boolean"}},
            "required": ["box", "kind", "labels", "seen", "meaning", "unreadable"], "additionalProperties": False}},
        "relations": {"type": "array", "items": {
            "type": "object", "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "relation": {"type": "string"}},
            "required": ["from", "to", "relation"], "additionalProperties": False}},
        "summary": {"type": "array", "items": {
            "type": "object", "properties": {"text": {"type": "string"}, "boxes": {"type": "array", "items": {"type": "string"}}},
            "required": ["text", "boxes"], "additionalProperties": False}}},
    "required": ["figures", "relations", "summary"], "additionalProperties": False,
}


def knowledge():
    """읽기 지식 `(글 또는 None, 해시 또는 None)` — 파일이 없거나 비면 둘 다 None(일반 지식만)."""
    from core import paths
    p = paths.registry(KNOWLEDGE)
    try:
        t = p.read_text(encoding="utf-8") if p.exists() else None
    except OSError:
        t = None
    if not (t or "").strip():
        return None, None
    return t, hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]


def key():
    """보존분 재사용의 판 — 판독 지시문 판 · 읽기 지식 해시(입력은 쪽마다 열쇠가 잰다 · 층 config · 골격은 입력이 아니다)."""
    from core.build.extract import prompt_version
    return {"prompt_version": prompt_version(PROMPT), "knowledge": knowledge()[1]}


def check(doc_id, inp, ans, text=""):
    """검사(결정적) — `{figures, relations, summary, dropped: {칸: 수}}` · 어긋난 칸만 버린다(결함 로그)."""
    ids = {b["id"] for b in inp.get("boxes") or []}
    drop = {}
    page, whole = inp.get("page"), norm(text or "")

    def bad(what, why):
        drop[what] = drop.get(what, 0) + 1
        store.append_defect(f"{doc_id}: 쪽 판독 — 쪽 {page} {what} 버림({why})")

    figs = []
    for f in (ans or {}).get("figures") or []:
        if f.get("box") not in ids:
            bad("그림", f"상자 '{str(f.get('box'))[:40]}'가 그 쪽에 없다")
            continue
        kind = f.get("kind")
        if kind not in KINDS:
            bad("종류", f"'{str(kind)[:20]}'는 닫힌 목록 밖")
            kind = None
        seen = []
        for st in f.get("seen") or []:
            t = str((st or {}).get("text") or "").strip()
            if t and st.get("basis") in BASIS:
                seen.append({"text": t, "basis": st["basis"]})
            else:
                bad("보이는 것", f"근거 '{str((st or {}).get('basis'))[:10]}'는 보임 · 추론 밖이거나 글이 비었다")
        labels = [str(x).strip() for x in f.get("labels") or [] if str(x).strip()]
        figs.append({"box": f["box"], "kind": kind, "labels": labels,
                     "labels_in_text": [x for x in labels if norm(x) in whole],
                     "seen": seen, "meaning": str(f.get("meaning") or "").strip() or None,
                     "unreadable": bool(f.get("unreadable"))})
    rels = []
    for r in (ans or {}).get("relations") or []:
        if r.get("from") in ids and r.get("to") in ids and r.get("relation") in RELATIONS:
            rels.append({"from": r["from"], "to": r["to"], "relation": r["relation"]})
        else:
            bad("관계", f"{r.get('from')} → {r.get('to')} '{r.get('relation')}' — 없는 상자이거나 목록 밖 관계")
    summ = []
    for s in (ans or {}).get("summary") or []:
        t = str((s or {}).get("text") or "").strip()
        bs = [b for b in (s or {}).get("boxes") or [] if b in ids]
        if t and bs:
            summ.append({"text": t, "boxes": bs})
        else:
            bad("요약", f"'{t[:40]}' — 근거 상자가 없다")
    return {"figures": figs, "relations": rels, "summary": summ, "dropped": drop}


# ---------------------------------------------------------------- 실호출 · mock
def _live(doc_id, inp, capture, images, hint):
    from core.state.captures import mime
    sys_ = gateway.prompt(PROMPT)
    kt, _kh = knowledge()
    if kt:
        sys_ += "\n\n## 읽기 지식(사내)\n" + kt.strip()
    parts = [{"type": "text", "text": json.dumps({"page": inp, **({"hint": hint} if hint else {})}, ensure_ascii=False)}]
    if capture:
        parts.append(gateway._image_part(capture, mime(capture)))
    for ref, blob, mm in images or ():
        parts += [{"type": "text", "text": f"[그림 {ref}]"}, gateway._image_part(blob, mm)]
    return gateway.chat([{"role": "system", "content": sys_}, {"role": "user", "content": parts}],
                        json_schema=SCHEMA, point="reading")      # 호출 지점 이름은 글자로(칸 대장 L칸 대조 — TAG와 같다)


def hint_answer(doc_id):
    """mock 힌트 `<doc_id>@reading.json` — 없으면 None(판독 없음 · 지금 방식)."""
    p = _fx.EXTRACT_HINTS / f"{doc_id}@reading.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def reader(notice=None):
    """파서에 내려보낼 **판독 함수** `fn(doc_id, 입력, capture=, images=, hint=, text=)` — 실호출이면 ④(태그 `reading`) · mock이면 힌트 ·
    돌려주는 것은 검사가 끝난 답 또는 None(판정 없음). `fn.key()`가 판 · `fn.pages`가 캡처(`core/state/captures.pages` — 추출과 같은
    판) · `fn.notice`가 예고 줄(진입점이 단다) · 층 인자 없음."""
    from core.state import captures
    live = not gateway.use_mock()

    def fn(doc_id, inp, *, capture=None, images=(), hint=None, text=""):
        if live:
            gateway.require(TAG)            # 미설정이면 명시적 실패(덱 구조와 같은 결 — 실호출 인입은 사전 점검이 먼저 멈춘다)
            try:
                ans = _live(doc_id, inp, capture, images, hint)
            except gateway.NotConfigured:
                raise
            except Exception as e:                               # noqa: BLE001 — 그 쪽은 판독 없이
                store.append_defect(f"{doc_id}: 쪽 판독 호출 실패 — 쪽 {inp.get('page')} {type(e).__name__}: {e}")
                return {"figures": [], "relations": [], "summary": [], "dropped": {}, "calls": 1,
                        "failed": f"{type(e).__name__}: {e}", "source": "live", **gateway.prompt_stamp(PROMPT)}
            calls, source = 1, "hint" if hint else "live"
        else:
            got = ((hint_answer(doc_id) or {}).get("pages") or {}).get(str(inp.get("page")))
            if got is None:
                return None
            ans, calls, source = (got.get("again") or got) if hint else got, 0, "hint" if hint else "mock"
        out = check(doc_id, inp, ans, text)
        _LOG.info("쪽 판독 %s 쪽 %s — 그림 %d · 관계 %d · 요약 %d · 버림 %s", doc_id, inp.get("page"), len(out["figures"]),
                  len(out["relations"]), len(out["summary"]), out["dropped"])
        return {**out, "calls": calls, "source": source, **gateway.prompt_stamp(PROMPT)}
    fn.key = key
    fn.live = live
    fn.pages = captures.pages
    fn.capture_ref = captures.ref
    fn.notice = notice
    fn.drift = lambda rec: gateway.prompt_drift(PROMPT, rec)
    return fn


# ---------------------------------------------------------------- 사람의 고침 (판독 표 — 등록 단)
def record_fix(doc_id, page, fix):
    """판독 고침 한 칸 — `@판독` 프레임(쪽 번호 · `{action: 다시, hint}` 또는 `{action: 지움}` — 같은 쪽은 덮는다 · 덱 고침과 같은 파일).
    `자세히` · `빼기`(B168 ③ — `{action, box}`)는 그 쪽 칸의 그림 목록(`자세히` · `빼기`)에 더한다(같은 그림은 다른 목록에서 뺀다) ·
    다시 · 지움은 그 목록을 남긴다."""
    from core.build import structure as ST
    from parser.reading import DETAIL, DROP
    cur = {k: v for k, v in ((ST.fixes_of(doc_id).get(FRAME) or {}).get(int(page)) or {}).items() if k not in ("by", "at")}
    if fix.get("action") in (DETAIL, DROP):
        other = DROP if fix["action"] == DETAIL else DETAIL
        cur[fix["action"]] = sorted(set(cur.get(fix["action"]) or []) | {fix["box"]})
        cur[other] = [x for x in cur.get(other) or [] if x != fix["box"]]
        fix = {k: v for k, v in cur.items() if v not in ([], None)}
    else:
        fix = {**{k: cur[k] for k in (DETAIL, DROP) if cur.get(k)}, **fix}
    ST.record_fix(doc_id, FRAME, page, fix)
