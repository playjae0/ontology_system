# -*- coding: utf-8 -*-
"""칸 2.4·3.3 — **문서 개요** — 제목 계층만 보고 제목마다 「대상인가 · 주제인가」 (B115 ① · LLM 지점 ⑪).

사내(2026-10-15): 청크 본문에 유닛 이름이 없으면 추출이 고를 소속 이름이 맥락 줄의 공정뿐이라 소속이 공정으로
몰렸다(`공정 70 · 좌표 폴백 23`). 제목(`3. 추출부 › 2) NG unit`)에 적힌 유닛은 맥락 줄에 있지만 「맥락 줄의 말은
개체 후보가 아니다」(지시문 3.3)라 노드가 되지 않았다. 여기서 제목 계층을 **문서당 한 번**(렌즈마다) 본다:

  · 입력 = **제목 계층만**(청크의 시트 이름 · `meta.section_path` — 엑셀 · Word · PDF · PPT 같은 함수 `parts`) + 층의
    닫힌 카테고리 · 정의문. 본문 0(다른 청크의 본문을 넣지 않는다 — 사용자 2026-10-15).
  · 출력 = 제목마다 대상 `{name, category}` 또는 null(주제). **부모는 제목 트리가 정한다**(LLM이 바꾸지 않는다).
  · 대조(`_check`) — 이름은 제목 글자 안에 있어야 한다(밖이면 버림 · 결함 로그) · 카테고리는 닫힌 목록 안(밖이면
    버림 · 결함 로그) · 빈칸 표시는 주제다. 버린 제목은 주제와 같이 읽는다(하류가 그 위로 올라간다).
  · 체크포인트 `work/extract/outline/<doc_id>.json`(렌즈 `<doc_id>@<렌즈>.json` — 추출 폴더 안이라 기본 fresh가
    남긴다) · 재사용 조건 = **제목 계층 해시 · 지시문 판(`3.3_outline.md`) · 층 config 판**. 추출 체크포인트와 다른
    폴더라 재인입이 추출 체크포인트를 버려도 제목이 같으면 그대로 쓴다(LLM 0).
  · mock — 힌트 `tests/fixtures/extract_hints/<doc_id>@outline.json`(`{제목 경로 또는 제목: {name, category}}`)만 ·
    없으면 전부 주제(호출 0 · 체크포인트 0 — 판정이 없었다).

소비부 셋: 제목 개체 노드(`core/build/heading.land`) · 추출 입력의 소속 후보(`heading_candidates` — 넷째 출처
`제목`) · 상위로 올라가는 폴백 사슬과 연결 보강의 후보 범위(`ancestors` · `subtree`).
"""
from __future__ import annotations

import hashlib
import json
import time

from core.llm import gateway
from core.state import log, store
from core.state.ids import fold_latin, norm

_LOG = log.get(__name__)

#: 체크포인트 폴더 — 추출 폴더(`work/extract/`) 안의 하위 폴더(추출 체크포인트의 glob `<doc>@*.json`에 걸리지 않는다)
SUBDIR = "outline"
#: 지시문 이름(`prompts/3.3_outline.md`) · LLM 지점 이름(`gateway.POINTS`)
PROMPT = POINT = "outline"

SCHEMA = {
    "type": "object",
    "properties": {"headings": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"},
                       "target": {"type": ["object", "null"],
                                  "properties": {"name": {"type": "string"},
                                                 "category": {"type": "string"}},
                                  "required": ["name", "category"], "additionalProperties": False}},
        "required": ["id", "target"], "additionalProperties": False}}},
    "required": ["headings"], "additionalProperties": False,
}


# ---------------------------------------------------------------- 제목 트리 (포맷 전부 한 함수)
def parts(chunk):
    """조각 하나의 제목 사슬 — `[시트, 제목1, 제목2, …]`. 시트 이름(있으면) + `meta.section_path`를 ` › `로 자른 것.

    구획 경로가 **프레임 이름 그 자체**면(제목 없는 구간 — 어댑터가 프레임 이름으로 채운다) 제목이 아니다 —
    시트는 시트 칸이 따로 싣는다(맥락 줄 `extract_ctx.context_fields`와 같은 규칙). 연속 중복은 접는다."""
    from core.build import extract_ctx
    m = chunk.get("meta") or {}
    sheet, path = m.get("sheet"), m.get("section_path")
    out = [str(sheet)] if sheet else []
    if path and str(path) not in (str(sheet or ""), str(m.get("frame") or "")):
        for p in extract_ctx._path(path).split(extract_ctx.PATH_SEP):
            p = p.strip()
            if p and (not out or out[-1] != p):
                out.append(p)
    return out


def tree(env):
    """봉투 → 제목 트리 — `{"headings": [{id, text, parent, depth, path}], "of": {위치: 가장 깊은 제목 id}}`.

    id는 처음 나온 순서(1부터)라 부모가 자식보다 앞이다. 같은 사슬 = 같은 제목(경로가 열쇠)."""
    from core.build import extract_ctx
    heads, by_key, of = [], {}, {}
    for c in (env or {}).get("chunks") or []:
        ps = parts(c)
        pid = None
        for i in range(len(ps)):
            key = tuple(ps[:i + 1])
            if key not in by_key:
                by_key[key] = len(heads) + 1
                heads.append({"id": by_key[key], "text": ps[i], "parent": pid, "depth": i + 1,
                              "path": extract_ctx.PATH_SEP.join(key)})
            pid = by_key[key]
        if pid is not None and c.get("source_locator"):
            of[c["source_locator"]] = pid
    return {"headings": heads, "of": of}


def heading_hash(heads):
    """제목 계층 해시 — 사슬(경로)의 목록만 · 재사용 조건의 첫 축."""
    raw = json.dumps([h["path"] for h in heads], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- 체크포인트
def checkpoint_path(doc_id, lens=None):
    from core.build import extract as EX
    return EX.EXTRACT_DIR / SUBDIR / (f"{doc_id}@{lens}.json" if lens else f"{doc_id}.json")


def _now_key(heads, cfg):
    from core.build import extract as EX
    return {"heading_hash": heading_hash(heads), "prompt_version": EX.prompt_version(PROMPT),
            "config_version": cfg.get("config_version") or cfg.get("skeleton_version")}


_LABEL = {"heading_hash": "제목 계층", "prompt_version": "지시문", "config_version": "층 config"}


def _reuse(doc_id, lens, now):
    """`(체크포인트 또는 None, 못 쓰는 이유)`."""
    p = checkpoint_path(doc_id, lens)
    if not p.exists():
        return None, "체크포인트 없음"
    try:
        ck = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"체크포인트를 읽지 못했다 — {type(e).__name__}"
    for k, v in now.items():
        if (ck.get(k) or None) != (v or None):
            return None, f"{_LABEL[k]} {str(ck.get(k))[:12] or '없음'} → {str(v)[:12] or '없음'}"
    return ck, ""


def load(doc_id, lens=None):
    """저장된 개요(맞춤표 · 연결 보강이 읽는다) — 없으면 None."""
    p = checkpoint_path(doc_id, lens)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def load_any(doc_id):
    """그 문서의 개요 하나 — 기본판 → 렌즈판(이름 순 첫 것). 제목 트리는 렌즈가 달라도 같다(대상만 렌즈마다)."""
    got = load(doc_id)
    if got is not None:
        return got
    d = checkpoint_path(doc_id).parent
    for p in sorted(d.glob(f"{doc_id}@*.json")) if d.exists() else []:
        got = load(doc_id, p.stem.split("@", 1)[1])
        if got is not None:
            return got
    return None


def _write(doc_id, lens, cfg, now, heads, of, source):
    from core import paths
    out = {"doc_id": doc_id, "stage": "outline", **now, "layer": cfg.get("layer"),
           "source": source, "headings": heads, "of": of}
    if lens:
        out["lens"] = lens
    p = checkpoint_path(doc_id, lens)
    paths.ensure(p)                        # 폴더를 만드는 자리는 하나다 (B78 1a)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return out


# ---------------------------------------------------------------- 판정 · 대조
def _ask(heads, cfg):
    """지점 ⑪ 실호출 — `{id: target 또는 None}`."""
    from core.build.extract import categories_with_also
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt(PROMPT)},
         {"role": "user", "content": json.dumps(
             {"categories": categories_with_also(cfg),
              "headings": [{k: h[k] for k in ("id", "text", "parent", "depth")} for h in heads]},
             ensure_ascii=False)}],
        json_schema=SCHEMA, point="outline")
    return {x.get("id"): x.get("target") for x in out.get("headings") or [] if isinstance(x, dict)}


def _mock(doc_id, heads):
    """mock — 힌트 파일만(경로 또는 제목 글자가 열쇠) · 없으면 None(판정 없음)."""
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@outline.json"
    if not p.exists():
        return None
    hint = json.loads(p.read_text(encoding="utf-8"))
    gateway.mock(POINT, f"힌트 {p.name}")
    return {h["id"]: hint.get(h["path"], hint.get(h["text"])) for h in heads}


def _span(name, text):
    """제목 글자 안의 그 이름 — 정확(`norm`) → 라틴 대소문자 무시(B96 ④ · 제목의 글자로 돌려준다) · 없으면 None."""
    n, t = norm(name or ""), norm(text or "")
    if not n:
        return None
    if n in t:
        return n
    i = fold_latin(t).find(fold_latin(n))
    return t[i:i + len(n)] if i >= 0 else None


def _check(doc_id, h, target, cats):
    """답 하나의 대조 — `(target 또는 None, 버린 이유 또는 None)`."""
    from parser.normalizer import null_marker
    if not target:
        return None, None
    name, cat = target.get("name"), target.get("category")
    got = _span(name, h["text"])
    if got is None or null_marker(got):
        why = f"제목에 없는 이름 '{name}'"
    elif cat not in cats:
        why = f"닫힌 목록 밖 카테고리 '{cat}'"
    else:
        return {"name": got, "category": cat}, None
    store.append_defect(f"{doc_id}: 개요 — {why} (제목 '{h['path']}') → 버렸다(주제로 읽는다)")
    return None, why


def judge(doc_id, heads, cfg, answers):
    """답(`{id: target}`)을 제목마다 대조해 싣는다 — 목록 밖 id는 버린다(결함 로그)."""
    cats = set((cfg.get("categories") or {}).keys())
    ids = {h["id"] for h in heads}
    for k in sorted(set(answers) - ids, key=str):
        store.append_defect(f"{doc_id}: 개요 — 목록 밖 제목 id {k!r} → 버렸다")
    out = []
    for h in heads:
        t, why = _check(doc_id, h, answers.get(h["id"]), cats)
        out.append({**h, "target": t, **({"dropped": why} if why else {})})
    return out


# ---------------------------------------------------------------- 한 문서 한 번
def _say(notice, info):
    from core.build.extract import _say as _s
    _s(notice, info)


def run(env, cfg, *, lens=None, notice=None):
    """문서(렌즈) 하나의 개요 — `{"headings": [... target], "of": {위치: 제목 id}, "source"}`.

    재사용(조건이 같다 → LLM 0) · mock(힌트만) · 실호출(한 번). 예고 → (누적 줄) → 끝을 `notice`로 낸다."""
    doc_id = env["doc_id"]
    t = tree(env)
    heads = t["headings"]
    if not heads:
        return {"headings": [], "of": {}, "source": "none"}
    now = _now_key(heads, cfg)
    ck, why = _reuse(doc_id, lens, now)
    if ck is not None:
        _say(notice, {"단계": "개요재사용", "렌즈": lens, "자리": checkpoint_path(doc_id, lens),
                      **_counts(ck["headings"])})
        return ck
    live = not gateway.use_mock()
    _say(notice, {"단계": "개요예고", "렌즈": lens, "제목": len(heads), "호출": 1 if live else 0,
                  "다시": why if why != "체크포인트 없음" else None})
    u0, t0 = gateway.usage_total(), time.monotonic()
    answers = _ask(heads, cfg) if live else _mock(doc_id, heads)
    if answers is None:                         # mock · 힌트 없음 — 판정이 없었다(전부 주제 · 체크포인트 0)
        out = {"headings": [{**h, "target": None} for h in heads], "of": t["of"], "source": "mock"}
    else:
        out = _write(doc_id, lens, cfg, now, judge(doc_id, heads, cfg, answers), t["of"],
                     "live" if live else "hint")
    _LOG.info("개요 %s%s · 대상 %s", doc_id, f"@{lens}" if lens else "",
              [(h["path"], h["target"]) for h in out["headings"] if h.get("target")])
    _say(notice, {"단계": "개요끝", "렌즈": lens, "since": u0, "초": round(time.monotonic() - t0, 1),
                  "자리": checkpoint_path(doc_id, lens) if answers is not None else None,
                  **_counts(out["headings"])})
    return out


def _counts(heads):
    tg = [h for h in heads if h.get("target")]
    return {"제목": len(heads), "대상": len(tg), "버림": sum(1 for h in heads if h.get("dropped")),
            "주제": sum(1 for h in heads if not h.get("target") and not h.get("dropped")),
            "대상목록": [(h["path"], h["target"]["name"], h["target"]["category"]) for h in tg]}


# ---------------------------------------------------------------- 소비부의 질문
def by_id(ol):
    return {h["id"]: h for h in (ol or {}).get("headings") or []}


def chain_of(ol, hid):
    """그 제목과 그 위 — 가까운 것부터 `[제목]`(주제 포함 · 맨 위까지)."""
    hs = by_id(ol)
    out, cur = [], hid
    while cur is not None and cur in hs and len(out) < 64:
        out.append(hs[cur])
        cur = hs[cur].get("parent")
    return out


def chain(ol, locator):
    """그 조각 위의 제목 — 가까운 것부터 `[제목]`(주제 포함 · 맨 위까지)."""
    return chain_of(ol, ((ol or {}).get("of") or {}).get(locator))


def ancestors(ol, locator):
    """그 조각 위의 **제목 개체**(대상으로 정해진 제목만) — 가까운 것부터 `[제목]`."""
    return [h for h in chain(ol, locator) if h.get("target")]


def heading_candidates(ol, locator):
    """추출 입력의 넷째 소속 출처 — `[{name, category}]` 가까운 것부터(비면 빈 목록)."""
    return [dict(h["target"]) for h in ancestors(ol, locator)]


def targets_key(ol):
    """추출 재사용 조건의 개요 몫 — 대상 제목(경로 · 이름 · 카테고리)의 해시 · 대상이 없으면 None(옛 체크포인트와 같다)."""
    tg = [(h["path"], h["target"]["name"], h["target"]["category"])
          for h in (ol or {}).get("headings") or [] if h.get("target")]
    if not tg:
        return None
    return hashlib.sha256(json.dumps(tg, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
