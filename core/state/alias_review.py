# -*- coding: utf-8 -*-
"""칸 0.3 — **동의어 점검 · LLM 검토와 판정 목록**(B200 ② · 결정 `결정_동의어_점검.md` §2 3 ~ 5).

    <상태>/data/surface_book.json의 「별칭 검토」 갈래   ③진실 — 표기 대장 하나(B179 ②) · 사람 처분이 담긴다(지우지 않는 기록)

  · 열쇠 (표기, 층, 카테고리, canonical) — 보류 표기(별칭 후보)는 canonical 없이(붙을 노드 미정)
  · 칸 — LLM 판정(맞음 · 틀림 · 애매) · 까닭 · 제안(다른 노드 canonical | 없음) · 모델 · 시각 · 사람 처분(`human` — 처분 · 행위자 · 시각) ·
    상태(열림 · 없어짐 · 다시)
  · **묻는 것은 판정 목록에 없는 짝만**(처음은 전체) · 사람이 「유지」로 승인한 짝은 다시 묻지 않는다 · 골격 · 대장에서 빠진 짝은
    「없어짐」으로 닫는다(다시 나타나면 「다시」 — 다시 묻는다) · 노드 이름이 바뀌면 열쇠가 따라간다(`retarget` — 개명은 판정 그대로 ·
    병합은 「다시」)
  · LLM은 **제안만** — 골격 · 사전 · 대장은 사람 승인(`alias_approve`)으로만 바뀐다

LLM 지점은 ②개체 동일성 판정의 호출 태그 `alias_review`(「이 표기가 이 노드와 같은 것인가」 — 닫힌 12 그대로 · `gateway.CALL_TAGS`) ·
지시문 `prompts/0.3_alias_review.md` · 50짝 묶음 · mock은 픽스처 `alias_review.json`의 창작 답(없으면 전부 맞음).
코드에 층 어휘 0.
"""
from __future__ import annotations

import json
import math

from core.state import alias_audit as AA, alias_book as AB, store, surface_book as SB

PROMPT, TAG = "alias_review", "alias_review"
BATCH = 50
RIGHT, WRONG, UNSURE = "맞음", "틀림", "애매"
VERDICTS = (RIGHT, WRONG, UNSURE)
OPEN, GONE, AGAIN = "열림", "없어짐", "다시"
PAIR, CANDIDATE = "짝", "후보"
KEEP = "유지"
#: 답 모양 — 묶음 하나의 답(짝마다 id · 판정 · 까닭 · 제안)
SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "verdict": {"type": "string", "enum": list(VERDICTS)},
                                     "why": {"type": "string"}, "suggest": {"type": ["string", "null"]}},
    "required": ["id", "verdict", "why", "suggest"], "additionalProperties": False}}},
    "required": ["answers"], "additionalProperties": False}       # 엄격 규칙(B200 ⓪ — 제안 없으면 null · `gateway.strict_issues`)
#: 진행(뷰어의 폴링 · CLI) — `{state, done, total, batches, calls}`
PROGRESS = {"state": "idle", "done": 0, "total": 0, "batches": 0, "calls": 0}




class Review:
    """판정 목록 — 여는 입구 `open` · 쓰기 `save`(바뀐 것이 있을 때만 · 제 갈래만)."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.idx = {AB.pair_key(r["surface"], r.get("target")): r for r in self.rows}
        self.dirty = False

    @classmethod
    def open(cls):
        return cls(SB.review_rows())

    def save(self):
        if self.dirty:
            SB.write_review(self.rows)
            self.dirty = False

    def get(self, k):
        return self.idx.get(k)

    def put(self, k, surface, target, where, kind, **cells):
        r = self.idx.get(k)
        if r is None:
            r = {"surface": surface, "target": dict(target or {}), "where": where, "kind": kind, "state": OPEN}
            self.rows.append(r)
            self.idx[k] = r
        r.update(cells)
        self.dirty = True
        return r

    def retarget(self, old, new, *, again=False):
        """대상 이름이 바뀌었다(같은 노드) — 열쇠가 따라간다 · `again`(병합)이면 판정 · 처분을 걷고 「다시」. 돌려주는 것은 옮긴 수."""
        ko = AB.target_key(old)
        moved = 0
        for r in list(self.rows):
            t = r.get("target") or {}
            if AB.target_key(t) != ko:
                continue
            del self.idx[AB.pair_key(r["surface"], t)]
            r["target"] = {**t, **{k: new.get(k) for k in ("layer", "canonical", "category")}}
            if again:
                for c in ("verdict", "why", "suggest", "human"):
                    r.pop(c, None)
                r["state"] = AGAIN
            self.idx[AB.pair_key(r["surface"], r["target"])] = r
            moved += 1
        self.dirty = self.dirty or bool(moved)
        return moved


# ---------------------------------------------------------------- 지금 짝 ↔ 판정 목록
def _where(p):
    return SB.place(p.get("kind") == CANDIDATE or p.get("skeleton"), p.get("layer"))


def items(ps=None, pend=None, w=None):
    """지금 점검 대상 — 짝(`alias_audit.pairs`) + 보류 표기(`alias_audit.pending` — 후보) · 항목마다 `k`(판정 목록 열쇠)."""
    from core.state.world import World
    w = w or World()
    ps = AA.pairs(w) if ps is None else ps
    pend = AA.pending() if pend is None else pend
    out = []
    for p in ps:
        n = w.get(p["node_id"]) or {}
        t = {"layer": p["layer"], "canonical": p["canonical"], "category": p["category"]}
        out.append({**p, "kind": PAIR, "target": t, "k": AB.pair_key(p["surface"], t), "skeleton": n.get("status") == "seed"})
    for e in pend:
        t = {"layer": e["layer"], "canonical": None, "category": e["category"]}
        out.append({**e, "kind": CANDIDATE, "target": t, "k": AB.pair_key(e["surface"], t)})
    return out


def sync(rv, its):
    """판정 목록이 지금을 따라간다 — 지금 없는 열쇠는 「없어짐」 · 「없어짐」이 다시 나타나면 「다시」. 돌려주는 것은 닫은 수."""
    now = {it["k"] for it in its}
    closed = 0
    for r in rv.rows:
        k = AB.pair_key(r["surface"], r.get("target"))
        if k not in now and r.get("state") != GONE:
            r["state"] = GONE
            closed += 1
            rv.dirty = True
        elif k in now and r.get("state") == GONE:
            r["state"] = AGAIN
            rv.dirty = True
    return closed


def asked(r):
    """이미 판정이 있어 다시 묻지 않는 행인가 — 사람 「유지」는 늘 · LLM 판정은 「다시」가 아닐 때."""
    if r is None:
        return False
    if (r.get("human") or {}).get("disposition") == KEEP and r.get("state") != AGAIN:
        return True
    return bool(r.get("verdict")) and r.get("state") == OPEN


def targets(rv, its):
    """LLM에 물을 항목 — 판정 목록에 없거나(처음은 전체) 「다시」인 것."""
    return [it for it in its if not asked(rv.get(it["k"]))]


def state():
    """**점검 상태 한 자리**(bootstrap 끝 줄 · 뷰어 · `ops alias-audit` · 배경 검토) — 그래프를 한 번 연다 · 쓰기 0.
    `{pairs, items, review, targets, counts}`."""
    from core.state.world import World
    w = World()
    ps = AA.pairs(w)
    its = items(ps, w=w)
    rv = Review.open()
    tg = targets(rv, its)
    return {"pairs": ps, "items": its, "review": rv, "targets": tg, "counts": AA.counts(ps, len(tg))}


def summary_line():
    """bootstrap 끝 한 줄(`alias_audit.line`) — 짝 · 보류 표기를 지금 세고 판정 목록과 맞춘다(쓰기 0)."""
    return AA.line(state()["counts"])


# ---------------------------------------------------------------- LLM 입력 · 미리보기
def payload(i, it):
    if it["kind"] == CANDIDATE:
        return {"id": i, "종류": CANDIDATE, "표기": it["surface"], "카테고리": it.get("category"),
                "보류 사유": it.get("reason"), "후보 노드": it.get("candidates") or [], "행 수": it.get("rows")}
    return {"id": i, "종류": PAIR, "표기": it["surface"], "노드": it.get("path") or it.get("canonical"),
            "canonical": it.get("canonical"), "카테고리": it.get("category"), "형제": it.get("siblings") or [],
            "그 노드의 다른 별칭": it.get("others") or [], "같은 표기를 쓰는 다른 노드": it.get("shared") or [],
            "표본": (it.get("samples") or [])[:2]}


def batches(tg):
    return [tg[i:i + BATCH] for i in range(0, len(tg), BATCH)]


def preview(tg):
    """비용 미리보기 — `{pairs, batches, in_tokens, out_tokens}`(어림 토큰 = 글자 / 2 — `deck`과 같은 어림 · 출력은 짝당 40)."""
    from core.llm import gateway
    try:
        head = len(gateway.prompt(PROMPT))
    except Exception:                                       # noqa: BLE001 — 지시문 없는 루트(시험) — 본문만
        head = 0
    bs = batches(tg)
    chars = sum(head + len(json.dumps([payload(i, it) for i, it in enumerate(b)], ensure_ascii=False)) for b in bs)
    return {"pairs": len(tg), "batches": len(bs), "in_tokens": math.ceil(chars / 2), "out_tokens": 40 * len(tg)}


def preview_line(pv):
    return (f"LLM 검토 — 짝 {pv['pairs']:,} · 묶음 {pv['batches']:,}(묶음당 {BATCH}) · 예상 입력 약 {pv['in_tokens']:,} · "
            f"출력 약 {pv['out_tokens']:,} 토큰(어림 — 글자 / 2)")


# ---------------------------------------------------------------- 묻기 (실호출 · mock)
def _mock(batch):
    """mock — 픽스처의 창작 답(`{"틀림": [{표기, canonical, 까닭, 제안}], "애매": [...], "후보": [{표기, 제안, 까닭}]}`) · 그 밖은 맞음."""
    from core.llm import gateway
    from core.state import fixtures
    gateway.mock(TAG, f"{len(batch)}짝")
    book = fixtures.answers("alias_review")
    out = []
    for i, it in enumerate(batch):
        hit = None
        for verdict in (WRONG, UNSURE, CANDIDATE):
            for e in book.get(verdict) or []:
                if e.get("표기") == it["surface"] and (verdict == CANDIDATE or e.get("canonical") == it.get("canonical")):
                    hit = (verdict, e)
        if hit is None:
            out.append({"id": i, "verdict": RIGHT if it["kind"] == PAIR else UNSURE,
                        "why": "mock — 창작 답 없음", "suggest": None})
        else:
            v, e = hit
            out.append({"id": i, "verdict": UNSURE if v == CANDIDATE else v, "why": e.get("까닭") or "mock",
                        "suggest": e.get("제안")})
    return out


def _ask(batch):
    from core.llm import gateway
    from core.llm import points
    out = gateway.ask(TAG, PROMPT, [payload(i, it) for i, it in enumerate(batch)], SCHEMA,
                      mock=lambda: {"answers": _mock(batch)})
    return list(out.get("answers") or []), None if gateway.use_mock() else points.chat_model()


def run(tg=None, *, its=None, on_batch=None):
    """LLM 검토 — 묶음마다 묻고 판정 목록에 적는다(묶음마다 저장 — 끊겨도 앞 묶음은 남는다). `{asked, wrong, unsure, right,
    closed, calls}`. 진행은 `PROGRESS`(뷰어 폴링)."""
    rv = Review.open()
    its = items() if its is None else its
    closed = sync(rv, its)
    tg = targets(rv, its) if tg is None else tg
    bs = batches(tg)
    PROGRESS.update(state="running", done=0, total=len(tg), batches=len(bs), calls=0)
    tally = {RIGHT: 0, WRONG: 0, UNSURE: 0}
    try:
        for b in bs:
            ans, model = _ask(b)
            PROGRESS["calls"] += 1
            by = {a.get("id"): a for a in ans if isinstance(a, dict)}
            for i, it in enumerate(b):
                a = by.get(i) or {}
                v = a.get("verdict") if a.get("verdict") in VERDICTS else UNSURE
                tally[v] += 1
                rv.put(it["k"], it["surface"], it["target"], _where(it), it["kind"], verdict=v,
                       why=str(a.get("why") or "답 없음")[:200], suggest=a.get("suggest") or None,
                       model=model or "mock", at=store._now(), state=OPEN,
                       rows=it.get("rows", 0))
            rv.save()
            PROGRESS["done"] += len(b)
            if on_batch:
                on_batch(PROGRESS)
        rv.save()
    finally:
        PROGRESS["state"] = "idle"
    return {"asked": len(tg), "right": tally[RIGHT], "wrong": tally[WRONG], "unsure": tally[UNSURE],
            "closed": closed, "calls": len(bs)}
