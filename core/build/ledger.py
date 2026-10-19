# -*- coding: utf-8 -*-
"""칸 3.4 — 판정 대장 — **문서마다, 값마다, 어떻게 해소했는가** (B74 ② · 문서 7 §7.8).

    <상태>/work/ingest_log/{doc_id}.json      (④단 — B78 1b · 자리는 `store.path`가 안다)

정본이 아니라 **장부**다: 재인입이 덮고, 그래프를 되돌려 읽지 않는다. 있는 이유는
하나다 — 「몇 개가 로직이고 몇 개가 LLM인가」와 「이 행이 어디에 붙었나」를 **사후에
셀 수 있어야** 평가가 성립한다(사용자 2026-09-16). 지금까지 판정 경로는
`matcher.STATS`(문서 단위 합계)와 로그로만 흐르고 사라졌다.

**코드가 아는 사실만 적는다** — `path`·`verdict`는 닫힌 값이고 LLM 산출이 아니다
(C38 「LLM은 고르고, 시스템이 쓴다」의 결). 적는 자리는 인입의 행 루프 하나다.
"""
from __future__ import annotations

from core.state import store
from core.matcher import PATHS

DIR = "ingest_log"

# 닫힌 값 — 밖이면 FAIL이다(완료판정 ②). 종류 열이 anchor·부착까지 같은 표에 담는다.
VERDICTS = ("match", "new", "uncertain", "anchor", "lowres", "orphan",
            "attached", "pending", "gate_reject",
            "mention",      # 다른 공정의 골격 이름 — 노드 0 · 관련 링크 (B113 ①)
            "blank")        # 빈칸 표시(`-` · `N/A` …) — 개체 0 (B113 ②)

_KEYS = ("locator", "field", "role", "surface", "canonical", "layer", "path",
         "verdict", "node_id", "candidates_n", "confidence", "llm", "queue_kind",
         "narrow", "emb_top", "nearest", "same_doc", "target", "from", "attached", "hold",
         "category", "scope", "replay",   # 판정 재생의 키 몫 · 재판정 사유(B106 ② · 있을 때만)
         "by",                            # 그 행을 적은 손이 인입 루프가 아닐 때(B107 ③ — "retry")
         "blank",                         # 값 칸이 빈칸 표시였다 — 원문은 그대로 · 표지만(B113 ②)
         "evidence",                      # 연결 보강의 근거 문장 — 청크 원문 그대로(B115 ④ · 역할 link)
         "proposal",                      # 연결 보강 버림의 제안 `{target, rel}` — 재생이 지금 config로 게이트를 다시 돈다(B118 ⑤)
         "belongs_to",                    # 산문 개체가 낸 소속 이름(B119 ⑤ — 화면의 소속(출처) 칸 · 출처는 `from`)
         "value")                         # 산문 개체의 값 `{attr, value, verdict}`(B120 ① — `core/build/values.land`가 단다)


# 행 콜백 — 호출부가 꽂는다(기본 없음). **화면은 대장의 투영이다**(B81 ①):
# 값 줄의 재료를 화면이 따로 계산하면 두 벌이 갈리고, 그때 「화면은 붙었다는데
# 대장은 아니다」가 된다. core는 화면을 갖지 않으므로(D-149 ③) 찍는 것은 CLI다.
ON_ROW = None


#: 붙은 자리 콜백(B102 ⑦) — 엣지가 생겨 행에 `attached`가 붙을 때 · 화면이 행 아래 한 줄을 낸다.
ON_EDGE = None

#: 조각 하나의 부착이 끝났다(B119 ⑤) — 산문 화면이 그 조각의 값 행을 붙은 자리와 함께 낸다(위치 · None = 남은 전부).
ON_CHUNK = None


def chunk_done(locator=None):
    if ON_CHUNK is not None:
        ON_CHUNK(locator)


def attach(row, rel, other, how, arrow):
    """대장 행에 **이 값이 만든 엣지**를 단다 — `{rel, other, path(소속|관계|폴백), dir}` · 표·산문·폴백 한 손."""
    if row is None or not rel:
        return
    info = {"rel": rel, "other": other, "path": how, "dir": arrow}
    row.setdefault("attached", []).append(info)
    if ON_EDGE is not None:
        ON_EDGE(row, info)


def name_of(doc_id):
    return f"{DIR}/{doc_id}.json"


def row(*, locator=None, field=None, role=None, surface=None,
        canonical=None, layer=None, path="none", verdict="pending",
        node_id=None, candidates_n=0, confidence=0.0, llm=None,
        queue_kind=None, narrow=None, emb_top=None, nearest=None, same_doc=None,
        target=None, belongs_from=None, hold=None, category=None, scope=None, replay=None, by=None,
        blank=None, evidence=None, proposal=None, belongs_to=None):
    """행 하나 = entity 값 하나(anchor·부착 결과도 같은 표에 — role이 가른다) — **행의 모양은 이 함수 하나**다
    (인입 루프 `Ledger.add` · 재시도 `put_row`가 같이 쓴다 — B107 ③)."""
    if path not in PATHS:
        raise ValueError(f"대장 path가 닫힌 값 밖이다: {path!r}")
    if verdict not in VERDICTS:
        raise ValueError(f"대장 verdict가 닫힌 값 밖이다: {verdict!r}")
    r = {"locator": locator, "field": field, "role": role,
         "surface": surface, "canonical": canonical, "layer": layer,
         "path": path, "verdict": verdict, "node_id": node_id,
         "candidates_n": int(candidates_n or 0),
         "confidence": round(float(confidence or 0.0), 4),
         "llm": dict(llm or {"calls": 0, "in_tokens": 0, "out_tokens": 0}),
         "queue_kind": queue_kind}
    # 판정 근거(B99 ⑨) — **있을 때만** 단다(근거 없는 행의 대장 바이트는 그대로)
    # 같은 문서 auto에 붙은 매칭(B101 ①) — 그때만 `same_doc: true`
    for k, v in (("narrow", narrow), ("emb_top", emb_top), ("nearest", nearest),
                 ("same_doc", same_doc or None),
                 # 붙은 노드 · 소속 출처(B102 ⑦) — 붙은 자리(`attached`)는 엣지를 단 뒤 호출부가 단다
                 ("target", target), ("from", belongs_from),
                 # 보류 사유가 목록 밖이 아닐 때(B104 ① — 「표기 모호」) — 그때만 단다
                 ("hold", hold),
                 # 판정 재생의 키 몫(B106 ②) — 카테고리 · 이름 규칙의 부모(스코프 카테고리일 때만)
                 ("category", category), ("scope", scope),
                 # 재생하지 못한 사유(B106 ② — 키 없음 · 대상 없음 · 끔) — 재판정 행만
                 ("replay", replay),
                 # 인입 루프가 아닌 손(B107 ③ — 재시도가 판정해 갈아 끼운 행)
                 ("by", by),
                 # 값 칸의 빈칸 표시(B113 ② — 값은 그대로 · 그 표시를 함께)
                 ("blank", blank),
                 # 연결 보강의 근거 문장(B115 ④ — 청크 원문 그대로 · 재구축 재생이 같은 근거로 다시 붙인다)
                 ("evidence", evidence),
                 # 연결 보강 버림의 제안(B118 ⑤ — 대상 이름 · 관계) · 재생이 LLM 0으로 게이트를 다시 돈다
                 ("proposal", proposal),
                 # 산문 개체가 낸 소속 이름(B119 ⑤ — 소속(출처) 칸의 재료)
                 ("belongs_to", belongs_to)):
        if v is not None:
            r[k] = v
    return r


def judged(last, *, locator, field, surface, layer, target):
    """판정 하나(`Builder.last`) → 개체 행 인자 — 표의 행 루프(`loop._ledger_entity`)와 재시도가 같은 손으로 옮긴다."""
    from core.build.loop import _VERDICT
    return dict(locator=locator, field=field, role="entity", surface=surface,
                canonical=last.get("canonical"), layer=last.get("layer") or layer,
                path=last.get("path") or "none", verdict=_VERDICT.get(last.get("verdict"), "pending"),
                node_id=last.get("node_id"), candidates_n=last.get("candidates_n", 0),
                confidence=last.get("confidence", 0.0), llm=last.get("llm"),
                queue_kind=last.get("queue_kind"), narrow=last.get("narrow"),
                emb_top=last.get("emb_top"), nearest=last.get("nearest"), same_doc=last.get("same_doc"),
                target=target, category=last.get("category"), scope=last.get("scope"),
                replay=last.get("replay"))


def put_row(doc_id, new, old=None):
    """**재시도도 판정이다**(B107 ③) — 그 문서 대장에서 같은 키(위치 · 열 · 표기 · 층 · 역할 — 카테고리는 같거나 비었을
    때 · B106 재생 키)의 행을 그 판정으로 갈아 끼운다 · 없으면 더한다. 쓰기는 문서 하나 원자 쓰기(지금 대장 손 —
    재시도가 따로 파일을 쓰지 않는다) · 돌려주는 것은 「갱신」 또는 「더함」. `old`(행 → 참)를 주면 그 행을 갈아 끼운다
    (좌표 행 — 못 풀린 행은 층이 비어 키가 다르다 · B113 ③)."""
    from core.build.replay import key
    data = read(doc_id) or {"doc_id": doc_id, "rows": []}
    rows = data.setdefault("rows", [])
    k = key(new["locator"], new["field"], new["surface"], new["layer"])
    i = next((i for i, r in enumerate(rows) if (old(r) if old is not None else (
              r.get("role") == new["role"]
              and key(r.get("locator"), r.get("field"), r.get("surface"), r.get("layer")) == k
              and r.get("category") in (None, new.get("category"))))), None)
    if i is None:
        rows.append(new)
    else:
        rows[i] = new
    store.write(name_of(doc_id), data)
    return "더함" if i is None else "갱신"


class Ledger:
    """문서 하나의 대장. **행을 모으고 한 번에 쓴다** — 쓰기는 원자적이다(§7.1)."""

    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.rows: list[dict] = []

    def add(self, **kw):
        """행 하나를 모은다(모양은 `row`) — 화면 콜백(`ON_ROW`)이 그 행을 받는다."""
        self.rows.append(row(**kw))
        if ON_ROW is not None:
            ON_ROW(self.rows[-1])
        return self.rows[-1]

    def save(self):
        """**재인입이 덮는다** — 이전 대장이 남지 않는다(완료판정 ②)."""
        store.write(name_of(self.doc_id),
                    {"doc_id": self.doc_id, "rows": self.rows})
        return len(self.rows)


def attach_result(doc_id, result):
    """문서 끝 결과(B99 ⑤ — `core/build/result.collect`)를 대장 파일에 붙인다 · `show report`가 읽는다."""
    data = read(doc_id) or {"doc_id": doc_id, "rows": []}
    data["result"] = result
    store.write(name_of(doc_id), data)


def read(doc_id):
    """그 문서의 대장. 없으면 None — 「인입 기록은 있는데 대장이 없다」를 가른다."""
    p = store.path(name_of(doc_id))
    if not p.exists():
        return None
    return store.read(name_of(doc_id), None)


def summary(rows):
    """머리 집계 — `show report`와 어서션이 **같은 함수로** 센다(B22의 결)."""
    ent = [r for r in rows if r.get("role") == "entity"]
    out = {"값": len(ent), "사전": 0, "스코프": 0, "임베딩": 0, "겹침": 0,
           "신규": 0, "불확실": 0, "보류": 0, "호출": 0, "토큰": 0}
    for r in rows:
        u = r.get("llm") or {}
        out["호출"] += int(u.get("calls") or 0)
        out["토큰"] += int(u.get("in_tokens") or 0) + int(u.get("out_tokens") or 0)
    for r in ent:
        p, v = r.get("path"), r.get("verdict")
        if p == "dictionary":
            out["사전"] += 1
        elif p == "scope+judge":
            out["스코프"] += 1
        elif p == "embedding+judge":
            out["임베딩"] += 1
        elif p == "overlap+judge":
            out["겹침"] += 1
        if v == "new":
            out["신규"] += 1
        elif v == "uncertain":
            out["불확실"] += 1
    out["보류"] = sum(1 for r in rows if r.get("verdict") in ("pending", "orphan"))
    return out


def made_by():
    """`node_id → 그 노드를 처음 만든 행의 path` (B74 ③ — 뷰어가 읽는다).

    「몇 개가 로직이고 몇 개가 LLM인가」를 **노드 위에서** 답하는 자리다. 대장이
    없는 노드는 여기 없다 — 호출부가 seed/unknown으로 가른다(뷰어가 그 둘을 안다).
    """
    out = {}
    d = store.path(DIR)
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        data = store.read(f"{DIR}/{f.name}", None) or {}
        for r in data.get("rows") or []:
            nid = r.get("node_id")
            if nid and r.get("verdict") in ("new", "uncertain") and nid not in out:
                out[nid] = r.get("path") or "none"
    return out
