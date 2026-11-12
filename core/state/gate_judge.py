# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 판단 — LLM이 골격 목록을 본다**(B202 ① · 원칙: 판단은 LLM이 · 확정은 사람이 · 코드는 검사만).

문에 걸린 줄(골격 칸 — 산문 [3/8] 제목 · [5/8] 본문 · 표 [3/7] · `ops review` 첫 묶음)마다 LLM 한 번 — 입력은 표기 · 들어온 자리 ·
카테고리 · 맥락 한 줄 · **위 공정 아래 골격 노드 전부**(짧은 이름 · 경로 · 단 — 닫힌 목록 · 코드가 미리 걸러 빼지 않는다) · 위 공정이
미정이면 좌표 층 골격 전부. 답은 같다 · 다르다 · 애매 + 확실도 + 까닭 + 후보 순위(최대 5 · 목록 안에서만). 코드는 이름이 목록
안인가만 본다(밖이면 버린다 · 결함 로그).

    <상태>/work/extract/gate_judge.json   ④작업 — 판단 기억(재생성 = 재판단 · 기본 fresh가 남기는 `extract/` 안)

  · 열쇠 (표기 키, 위 공정, 골격 판) — 같으면 다시 부르지 않는다(재구축 LLM 0 · 판정 기억과 같은 규율) · 골격 판 = 그 목록의 지문
  · 사람 없는 실행은 부르지 않는다(「LLM 0 — 사람 없는 실행」 · 쓰기 0)

LLM 지점은 ②개체 동일성 판정의 호출 태그 `gate_judge`(닫힌 12 그대로) · 지시문 `prompts/0.3_gate_judge.md` · mock은 픽스처
`gate_judge.json`의 창작 답(없으면 애매 · 후보는 첫 판단의 가까운 것). 코드에 층 어휘 0.
"""
from __future__ import annotations

import hashlib
import json

from core import paths
from core.state import log, store

_LOG = log.get(__name__)

PROMPT, TAG = "gate_judge", "gate_judge"
SAME, DIFF, UNSURE = "같다", "다르다", "애매"
VERDICTS = (SAME, DIFF, UNSURE)
#: 후보 상한(사람이 보는 순위)
TOP = 5
#: 판단 기억 — 단계 산출(④) · 이름은 이 모듈만 안다
MEMO = ("extract", "gate_judge.json")
#: 답 모양
SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": list(VERDICTS)}, "confidence": {"type": "number"}, "why": {"type": "string"},
    "candidates": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name"]}}},
    "required": ["verdict", "confidence", "why", "candidates"]}
#: 이 실행의 호출 수 — 보고 · 화면(첫 판단 · 다시 판단)
CALLS = {"첫 판단": 0, "다시 판단": 0}


# ---------------------------------------------------------------- 골격 목록 (닫힌 목록 — 코드가 거르지 않는다)
def listing(up, sk=None):
    """위 공정 아래 골격 노드 전부 — `[{no, name, canonical, path, tier}]`(골격 순서 — 그래프에 심긴 차례) · 위 공정이 골격에 없으면
    (미정) 좌표 층 골격 전부."""
    from core.build import skeleton_review as SR
    from core.state import catalog
    sk = sk or SR._Sk()
    nid = sk.by_name.get(up) if up else None
    want = set(sk.under(nid)) if nid else set(sk.sk)
    sep = catalog.sep()
    out = []
    for i in (x for x in sk.g.nodes if x in want):
        n = sk.g.get(i)
        out.append({"no": len(out) + 1, "name": n["canonical"].rsplit(sep, 1)[-1], "canonical": n["canonical"],
                    "path": sk.path(i), "tier": n.get("tier")})
    return out


def version(lst):
    """골격 판 — 그 목록의 지문(이름 · 경로 · 단)."""
    raw = json.dumps([(x["canonical"], x["path"], x["tier"]) for x in lst], ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def find(name, lst):
    """이름 → 목록 안 canonical들 — 띄어쓰기 · 대소문자 · 전각 · `상위::` 접두 무시(별칭 찾기와 같은 규칙 `namefold.key`)."""
    from core.state import catalog
    from parser.namefold import key
    k = key(str(name or "").rsplit(catalog.sep(), 1)[-1])
    full = key(str(name or ""))
    hit = [x["canonical"] for x in lst if key(x["canonical"]) == full]
    return hit or [x["canonical"] for x in lst if key(x["name"]) == k] if k else []


# ---------------------------------------------------------------- 판단 기억
def _memo_path():
    return paths.work(*MEMO)


def _read():
    p = _memo_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001 — 깨진 기억은 없는 것(다시 묻는다)
        return {}


def _write(book):
    p = paths.ensure(_memo_path())
    store.atomic_write_bytes(p, (json.dumps(book, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def memo_key(row, ver):
    from parser.namefold import key
    return "|".join((key(row.get("surface") or ""), str(row.get("up_name") or row.get("up") or ""), ver))


# ---------------------------------------------------------------- 묻기 (실호출 · mock)
def payload(row, lst, hint=None):
    return {"표기": row.get("surface"), "자리": row.get("where") or ("행" if row.get("kind") == "pair" or not row.get("also") else "—"),
            "카테고리": row.get("also") or row.get("category") or "좌표",
            "위 공정": row.get("up_name") or row.get("up") or "미정",
            "맥락": row.get("place") or " · ".join(row.get("docs") or []) or "—",
            "첫 판단": {"answer": row.get("answer"), "가까운 것": row.get("near") or []},
            "사람 말": hint, "골격": [{"번호": x["no"], "이름": x["name"], "경로": x["path"], "단": x["tier"]} for x in lst]}


def _mock(row, lst, hint):
    from core.llm import gateway
    from core.state import fixtures
    gateway.mock(TAG, str(row.get("surface")))
    p = fixtures.ROOT_DIR / "gate_judge.json"
    try:
        book = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except Exception:                                    # noqa: BLE001 — 깨진 창작 답 — 없는 것
        book = {}
    got = book.get(f"{row.get('surface')}@{hint}") if hint else None
    got = got or book.get(str(row.get("surface")))
    if got:
        return got
    return {"verdict": UNSURE, "confidence": 0.0, "why": "mock — 창작 답 없음",
            "candidates": [{"name": n, "why": "첫 판단의 가까운 것"} for n in row.get("near") or []]}


def _ask(row, lst, hint):
    from core.llm import gateway
    if gateway.use_mock():
        return _mock(row, lst, hint)
    gateway.require(TAG)
    return gateway.chat([{"role": "system", "content": gateway.prompt(PROMPT)},
                         {"role": "user", "content": json.dumps(payload(row, lst, hint), ensure_ascii=False)}],
                        json_schema=SCHEMA, point=TAG)


def check(ans, lst):
    """코드는 검사만 — 판단이 셋 안인가 · 후보 이름이 목록 안인가(밖이면 버림 · 결함 로그) · 확실도 0~1. `{verdict, confidence, why,
    candidates: [{canonical, path, why}], dropped}`."""
    by = {x["canonical"]: x for x in lst}
    v = ans.get("verdict") if ans.get("verdict") in VERDICTS else UNSURE
    try:
        conf = max(0.0, min(1.0, float(ans.get("confidence") or 0)))
    except (TypeError, ValueError):
        conf = 0.0
    cands, dropped = [], []
    for c in ans.get("candidates") or []:
        hit = find((c or {}).get("name"), lst) if isinstance(c, dict) else []
        if len(hit) != 1:
            dropped.append(str((c or {}).get("name") if isinstance(c, dict) else c))
            continue
        if hit[0] not in [x["canonical"] for x in cands]:
            cands.append({"canonical": hit[0], "path": by[hit[0]]["path"], "why": str(c.get("why") or "")[:120]})
    if dropped:
        _LOG.warning("[결함] 골격 칸 판단 — 목록 밖 후보 버림 %s", dropped)
    return {"verdict": v, "confidence": conf, "why": str(ans.get("why") or "")[:200], "candidates": cands[:TOP],
            "dropped": dropped}


def judge(rows, *, live=True, hint=None, again=False):
    """**문에 걸린 줄마다 판단**(쓰기는 판단 기억 하나) — 줄에 `skeleton`(목록) · `llm`(판단) 또는 `llm0`(안 부른 사유)를 단다 ·
    `live=False`(사람 없는 실행)면 부르지 않는다. `hint`(사람 말)가 있으면 다시 판단이다(기억을 보지 않고 묻는다 · 기억은 덮지 않는다)."""
    from core.build import skeleton_review as SR
    sk = SR._Sk()
    book, dirty = _read(), False
    for r in rows:
        if r.get("nid") or r.get("done"):
            continue
        lst = listing(r.get("up_name") or r.get("up"), sk)
        r["skeleton"] = lst
        k = memo_key(r, version(lst))
        if not hint and not again and k in book:
            r["llm"], r["llm0"] = book[k], "판단 기억"
        elif not live:
            r["llm"], r["llm0"] = None, "사람 없는 실행"
            continue
        else:
            r["llm"], r["llm0"] = check(_ask(r, lst, hint), lst), None
            CALLS["다시 판단" if hint or again else "첫 판단"] += 1
            if not hint:
                book[k], dirty = r["llm"], True
        r["candidates"] = [{"name": c["canonical"], "path": c["path"], "why": c["why"]} for c in r["llm"]["candidates"]]
    if dirty:
        _write(book)
    return rows
