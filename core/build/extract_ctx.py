# -*- coding: utf-8 -*-
"""칸 3.3 — **청크 맥락 줄** — 추출에 넘기는 청크 머리 한 줄 (B102 ①).

「이 청크가 어디를 말하는가」를 판단할 재료를 한 줄로 준다:
`[문서: <파일 이름> · 공정: <조각 좌표 또는 문서 좌표> · 시트: <엑셀 시트> · 경로: <상위 제목 › … › 구획>]`.
없는 칸은 뺀다. **포맷 전부 한 함수**(엑셀·Word·PDF·PPT) — 포맷의 차이는 조각이 든 값(`meta.sheet` ·
`meta.section_path` · `process_ref`)이 말한다. 엑셀은 **제목이 있어도 시트명을 늘 싣는다** — 시트가
유닛·부품 단위인 문서에서 「어디의 것인가」의 첫 근거다. 앞뒤 청크 본문은 넣지 않는다(문서 6 §6.4-5).
"""
from __future__ import annotations

from pathlib import PurePath

#: 경로 칸 구분자 — 어댑터의 구획 구분자(` > ` 등)를 화면용 ` › `로 맞춘다.
PATH_SEP = " › "
_SEPS = (" > ", " / ")


def doc_info(env):
    """봉투에서 맥락 줄의 문서 칸 재료 — `{"name": 파일 이름, "coord": 문서 좌표}`."""
    src = (env or {}).get("source_path") or ""
    return {"name": PurePath(str(src)).name if src else None,
            "coord": (env or {}).get("doc_coord")}


def _path(p):
    s = str(p)
    for sep in _SEPS:
        s = s.replace(sep, PATH_SEP)
    return s


def context_fields(chunk, doc=None):
    """맥락 칸 `[(이름, 값)]` — 값이 있는 칸만 · 순서 문서 → 공정 → 시트 → 경로."""
    m = chunk.get("meta") or {}
    sheet = m.get("sheet")
    path = m.get("section_path")
    coord = chunk.get("process_ref") or (doc or {}).get("coord")
    out = [("문서", (doc or {}).get("name")), ("공정", coord), ("시트", sheet)]
    # 경로가 시트 이름 그 자체면(제목 없는 시트) 두 번 싣지 않는다
    if path and str(path) != str(sheet or ""):
        out.append(("경로", _path(path)))
    return [(k, v) for k, v in out if v]


def context_line(chunk, doc=None):
    """맥락 줄 한 줄(칸이 없으면 빈 문자열)."""
    f = context_fields(chunk, doc)
    return ("[" + " · ".join(f"{k}: {v}" for k, v in f) + "]") if f else ""


def with_context(chunk, doc=None):
    """추출 입력 — 맥락 줄 + 본문(맥락 칸이 없으면 본문 그대로)."""
    text = chunk.get("text", "")
    line = context_line(chunk, doc)
    return f"{line}\n{text}" if line else text
