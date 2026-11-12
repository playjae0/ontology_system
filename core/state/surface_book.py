# -*- coding: utf-8 -*-
"""칸 0.3 — **표기 대장** — 좌표 학습 기록과 별칭을 **대장 하나로**(B179 ② · 결정 세부 「사전 · 기록」).

    <상태>/data/surface_book.json     ③진실 — 기본 fresh가 남긴다(`init.kept()`) · `--all`(클린)이 지운다

항목마다 같은 머리 — **지위**(사람 보증 | 기계 판단) · **곳**(골격 칸 | 닫힌 분류 | 개체) · 표기 · 대상(층 · canonical ·
카테고리 — 「목록 밖」은 없음) · 출처 · 갈래(좌표 학습 | 목록 밖 | 별칭) · 기록(그 갈래의 손이 쓰는 칸 그대로).

  · 지위 — 출처가 사람 연산(사람 · 개명 · 이관 · 병합 · 분리)이면 사람 보증 · 그 밖(LLM 좌표 학습 · LLM 매칭 · 문서)은
    기계 판단. 사람이 골격으로 승격한 표기(`ops learn-promote`)는 골격 `ALIASES`로 가고 대장에서 빠진다
  · 곳 — 좌표 학습 · 목록 밖은 골격 칸 · 별칭은 대상이 골격(seed) 노드면 좌표 층이면 골격 칸 · 다른 층이면 닫힌 분류 ·
    아니면 개체
  · **쓰는 손은 둘 그대로**다 — 좌표 학습(파서 주입 `tagger.use_learned` · `coord_learn`)은 `learned` · `write_learned`
    (모양 `{"채택", "목록밖"}`), 별칭(`alias_book.AliasBook`)은 `alias_rows` · `write_aliases`. 쓰는 손은 파일을 다시
    읽어 **제 갈래만** 바꿔 쓴다(다른 갈래는 디스크의 것 그대로)
  · **이전**(`migrate`) — 대장이 없고 옛 두 파일(`coord_learned.json` · `alias_book.json`)이 있으면 처음 읽을 때 옮긴다 ·
    항목 수 앞뒤 같음(다르면 멈춘다 · 쓰기 0) · 옛 파일은 지우지 않는다(보관 — fresh도 남긴다 · 보존 수 밖) · 대장이
    있으면 다시 옮기지 않는다(다시 돌려도 같다)

코드에 층 어휘 0 — 좌표 층은 `bootstrap.coord_layer()`가 답한다.
"""
from __future__ import annotations

from pathlib import Path

from core.state import log, store

_LOG = log.get(__name__)

#: 옛 두 파일 — 이전의 원천 · 보관(읽는 곳은 `migrate` 하나)
LEGACY = (store.COORD_LEARNED, store.ALIAS_BOOK)
HUMAN, MACHINE = "사람 보증", "기계 판단"
SKELETON, CLOSED, ENTITY = "골격 칸", "닫힌 분류", "개체"
LEARN, MISS, ALIAS = "좌표 학습", "목록 밖", "별칭"
#: **별칭 검토**(B200 ②) — 동의어 점검의 판정 목록(LLM 판정 · 사람 처분) · 쓰는 손은 `core/state/alias_review`의 `write_review` 하나
REVIEW = "별칭 검토"
#: 사람 보증인 별칭 출처(`alias_book.SOURCES`의 사람 연산)
HUMAN_SOURCES = ("사람", "개명", "이관", "병합", "분리")
#: 별칭 갈래를 한 번이라도 썼다(처음 채움이 끝났다 — 옛 `alias_book.json`이 있던 것과 같은 표지)
FILLED = "별칭 채움 끝"


class MigrateRefused(RuntimeError):
    """옛 두 파일의 항목 수와 옮긴 항목 수가 다르다 — 쓰지 않고 멈춘다."""


def _path(path=None):
    return Path(path) if path is not None else store.path(store.SURFACE_BOOK)


def _write(data, path=None):
    store.atomic_write_bytes(_path(path), store._dumps(data))


def _read(path=None):
    p = _path(path)
    if path is None and not p.is_file():
        migrate()
    return store._loads(p.read_bytes()) if p.is_file() else {"entries": []}


def standing(source):
    """출처 → 지위."""
    return HUMAN if source in HUMAN_SOURCES else MACHINE


def _coord():
    from core.state.bootstrap import COORD_CATEGORY, coord_layer
    try:
        return coord_layer(), COORD_CATEGORY
    except Exception:                               # noqa: BLE001 — 좌표 층이 없는 루트(킷 · 빈 시험)는 곳을 개체 · 닫힌 분류로만
        return None, COORD_CATEGORY


def _learn_entries(view, coord):
    lay, cat = coord
    from parser.tagger import LEARN_SOURCE
    out = [{"갈래": LEARN, "지위": MACHINE, "곳": SKELETON, "표기": s,
            "대상": {"layer": r.get("layer") or lay, "canonical": r.get("canonical"), "category": cat},
            "출처": LEARN_SOURCE, "기록": r} for s, r in (view.get("채택") or {}).items()]
    return out + [{"갈래": MISS, "지위": MACHINE, "곳": SKELETON, "표기": s, "대상": None, "출처": LEARN_SOURCE, "기록": r}
                  for s, r in (view.get("목록밖") or {}).items()]


def _alias_entry(row, coord):
    t = row.get("target") or {}
    where = (SKELETON if t.get("layer") == coord[0] else CLOSED) if row.get("skeleton") else ENTITY
    return {"갈래": ALIAS, "지위": standing(row.get("source")), "곳": where, "표기": row["surface"], "대상": t,
            "출처": row.get("source"), "기록": {k: v for k, v in row.items() if k not in ("surface", "target")}}


# ---------------------------------------------------------------- 좌표 학습 갈래 (파서 주입 · coord_learn)
def learned(path=None):
    """좌표 학습 갈래 — `{"채택": {표기: 기록}, "목록밖": {표기: 기록}}`(옛 `coord_learned.json`과 같은 모양)."""
    out = {"채택": {}, "목록밖": {}}
    for e in _read(path).get("entries") or []:
        if e.get("갈래") in (LEARN, MISS):
            out["채택" if e["갈래"] == LEARN else "목록밖"][e["표기"]] = e.get("기록") or {}
    return out


def write_learned(view, path=None):
    """좌표 학습 갈래를 `view`로 바꿔 쓴다 — 별칭 갈래 · 표지는 디스크의 것 그대로."""
    data = _read(path)
    keep = [e for e in data.get("entries") or [] if e.get("갈래") not in (LEARN, MISS)]
    _write({**data, "entries": _learn_entries(view or {}, _coord()) + keep}, path)


# ---------------------------------------------------------------- 별칭 갈래 (alias_book)
def alias_rows():
    """별칭 갈래의 항목 — 옛 `alias_book.json`의 `entries`와 같은 모양의 행 목록."""
    return [{"surface": e["표기"], "target": e.get("대상"), **(e.get("기록") or {})}
            for e in _read().get("entries") or [] if e.get("갈래") == ALIAS]


def alias_filled():
    """별칭 갈래를 한 번이라도 썼나(처음 채움이 끝났다는 표지)."""
    return bool(_read().get(FILLED))


def write_aliases(rows):
    """별칭 갈래를 `rows`로 바꿔 쓴다 — 좌표 학습 갈래는 디스크의 것 그대로 · 처음 채움 표지를 남긴다."""
    data = _read()
    coord = _coord()
    keep = [e for e in data.get("entries") or [] if e.get("갈래") != ALIAS]
    _write({**data, "entries": keep + [_alias_entry(r, coord) for r in rows], FILLED: True})


# ---------------------------------------------------------------- 별칭 검토 갈래 (alias_review · B200 ②)
def review_rows():
    """별칭 검토 갈래의 항목 — `{surface, target, where, **기록}` 행 목록(대상의 canonical이 None이면 보류 표기 — 붙을 노드 미정)."""
    return [{"surface": e["표기"], "target": e.get("대상"), "where": e.get("곳"), **(e.get("기록") or {})}
            for e in _read().get("entries") or [] if e.get("갈래") == REVIEW]


def write_review(rows):
    """별칭 검토 갈래를 `rows`로 바꿔 쓴다 — 다른 갈래 · 표지는 디스크의 것 그대로. 지위는 사람 처분이 있으면 사람 보증."""
    data = _read()
    keep = [e for e in data.get("entries") or [] if e.get("갈래") != REVIEW]
    new = [{"갈래": REVIEW, "지위": HUMAN if (r.get("human") or {}).get("disposition") else MACHINE,
            "곳": r.get("where") or ENTITY, "표기": r["surface"], "대상": r.get("target"), "출처": "LLM 검토",
            "기록": {k: v for k, v in r.items() if k not in ("surface", "target", "where")}} for r in rows]
    _write({**data, "entries": keep + new})


# ---------------------------------------------------------------- 대장 전체 (화면 · 수)
def entries():
    """항목 전부(머리 포함) — 화면 · 수."""
    return list(_read().get("entries") or [])


def counts():
    """`{합, 사람 보증, 기계 판단, 갈래: {좌표 학습, 목록 밖, 별칭}}`."""
    es = entries()
    return {"합": len(es), HUMAN: sum(1 for e in es if e.get("지위") == HUMAN),
            MACHINE: sum(1 for e in es if e.get("지위") == MACHINE),
            "갈래": {k: sum(1 for e in es if e.get("갈래") == k) for k in (LEARN, MISS, ALIAS, REVIEW)}}


def legacy_paths():
    """남아 있는 옛 두 파일의 자리(보관 — fresh가 남긴다)."""
    return [store.path(n) for n in LEGACY if store.path(n).is_file()]


# ---------------------------------------------------------------- 이전 (옛 두 파일 → 대장)
def migrate():
    """대장이 없고 옛 두 파일이 있으면 옮긴다(처음 한 번) — 돌려주는 것은 옮겼으면
    `{채택, 목록 밖, 별칭, 앞, 뒤, 사람 보증, 기계 판단, 옛}` · 할 일이 없으면 None. 옛 파일은 그대로 둔다."""
    if _path().is_file() or not legacy_paths():
        return None
    old = store.read(store.COORD_LEARNED, {}) or {}
    view = {"채택": dict(old.get("채택") or {}), "목록밖": dict(old.get("목록밖") or {})}
    ab = store.read(store.ALIAS_BOOK, None)
    rows = list((ab or {}).get("entries") or [])
    coord = _coord()
    es = _learn_entries(view, coord) + [_alias_entry(r, coord) for r in rows]
    before = len(view["채택"]) + len(view["목록밖"]) + len(rows)
    if len(es) != before:
        raise MigrateRefused(f"옛 두 파일 {before:,}항목 → 대장 {len(es):,}항목 — 수가 다르다 · 쓰지 않았다")
    data = {"entries": es, **({FILLED: True} if ab is not None else {})}
    _write(data)
    rep = {"채택": len(view["채택"]), "목록 밖": len(view["목록밖"]), "별칭": len(rows), "앞": before, "뒤": len(es),
           HUMAN: sum(1 for e in es if e["지위"] == HUMAN), MACHINE: sum(1 for e in es if e["지위"] == MACHINE),
           "옛": [p for p in legacy_paths()]}
    _LOG.info("표기 대장 이전 — 옛 두 파일 %d항목 → %d항목(옛 파일 보관)", before, len(es))
    return rep
