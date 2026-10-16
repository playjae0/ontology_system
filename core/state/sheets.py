# -*- coding: utf-8 -*-
"""칸 0.3 — 시트 역할 **기록**: `registry/sheet_roles/<doc_id>.json` 읽기·쓰기 한 자리 (B83 ①).

관문(`cli/ingest_screen.py`)이 묻고 사람이 답하면 **그 답이 여기로 온다.** 읽는 곳은
셋(인입 흐름 · `parse run --sheets` · 열람)이고 쓰는 곳은 둘(관문 · `--sheets`)이라
**답하는 자리는 하나**여야 한다 — 읽기가 흩어지면 같은 문서가 명령에 따라 다른 역할로
읽힌다.

**②등록 단이다**(문서 7 §7.8) — 사람이 한 번 정한 것이라 `init --fresh`가 지우지 않고
백업·이관 대상이다. 그래서 `data/`도 `work/`도 아니라 `paths.registry()` 아래다.

역할 이름의 정본은 `parser/form.SHEET_ROLES`다 — 여기서 다시 세지 않는다(제안 규칙과
기록이 같은 셋을 봐야 한다).
"""
from __future__ import annotations

import json

from core import paths
from core.state import log, store

DIRNAME = "sheet_roles"                 # `registry/sheet_roles/<doc_id>.json`

_LOG = log.get(__name__)


#: 등록 표본의 **겹침 자리** `{doc_id: 자리}` (B116 ① — 이미 인입된 문서를 표본으로 쓰면 등록은 그 문서의 운영 기록을
#: 쓰지 않는다 · 이 실행 동안 그 등록의 검수 자리에서 읽고 쓴다 · 겹침이 비어 있으면 운영 기록을 읽기만)
_HELD = {}


def hold(mapping):
    """겹침을 건다(등록 표본 관문이 부른다 — `cli/register/samples.sample_roles`) · 빈 dict면 푼다."""
    _HELD.clear()
    _HELD.update({k: v for k, v in (mapping or {}).items()})


def operational(doc_id):
    """운영 기록의 자리 — 겹침과 무관하게(조립은 `paths.registry`가 한다 · 자리 소유자 하나)."""
    return paths.registry(DIRNAME, f"{doc_id}.json")


def path(doc_id):
    """기록 파일의 자리 — 겹침이 걸린 doc_id면 그 자리, 아니면 운영 기록."""
    return _HELD.get(doc_id) or operational(doc_id)


def read(doc_id):
    """기록 전문(dict) 또는 `None`. **깨진 파일은 없는 것으로 보고 로그를 남긴다** —
    관문이 다시 묻는다(조용히 기본값으로 떨어지지 않는다). 겹침 자리가 비었으면 운영 기록을 읽는다(쓰지 않는다)."""
    p = path(doc_id)
    if not p.exists() and doc_id in _HELD:
        p = operational(doc_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _LOG.warning("시트 역할 기록을 읽지 못했다 — %s (%s: %s)", p, type(e).__name__, e)
        return None


def roles_of(doc_id):
    """`{시트: 역할}` — 기록이 없으면 빈 dict(「역할 없음」)."""
    return dict((read(doc_id) or {}).get("sheets") or {})


def write(doc_id, file, roles, decided_by, *, judged=None):
    """기록 1건 — 원자적 쓰기는 `store`가 한다(tmp+replace+락 · 한 자리).

    `decided_by`는 `gate`(관문에서 사람이 답했다) · `flag`(`--sheets`로 받았다) ·
    `auto`(자동 모드 — 로직과 LLM이 합의했다 · B91 ②)다. **덮어쓴다** — 다시 준 것이 최신이다(③).

    `judged`(B91 ②)는 두 제안 — `{"logic": {시트: 역할}, "llm": {시트: 역할}, "llm_reason":
    {시트: 한 줄}, "llm_by": "live|mock|off", "promote": [시트…]}`. 최종은 `sheets`다
    (네 필드 = 로직 · LLM · 최종 · 결정 주체). 제안을 보지 않은 `--sheets` 역할 문자열은
    `judged`가 없다 — 기록 모양이 지금과 같다.
    """
    rec = {"doc_id": doc_id, "file": str(file), "decided_by": decided_by,
           "at": store._now(),               # 시각의 자리는 store 하나다
           "sheets": dict(roles)}
    if judged:
        rec.update({k: v for k, v in judged.items() if v is not None})
    store.atomic_write_bytes(
        path(doc_id),
        (json.dumps(rec, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    _LOG.info("시트 역할 기록 — %s · %s · %s", doc_id, decided_by, summary(rec["sheets"]))
    return rec


def pending(roles, names):
    """**미결** — 문서에 있는데 기록에 없는 시트. 관문이 그 시트만 다시 묻는다(③)."""
    return [n for n in names if n not in (roles or {})]


def stale(roles, names):
    """기록에 있는데 문서에 없는 시트 — 무시하고 로그 한 줄(①의 이름 정합)."""
    return [n for n in (roles or {}) if n not in names]


def summary(roles):
    """`prose 3 · ref 1 · skip 28` — 셋의 순서는 `form.SHEET_ROLES` 그대로."""
    from parser.form import SHEET_ROLES
    counts = {r: sum(1 for v in (roles or {}).values() if v == r) for r in SHEET_ROLES}
    return " · ".join(f"{r} {counts[r]}" for r in SHEET_ROLES)
