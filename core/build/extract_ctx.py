# -*- coding: utf-8 -*-
"""칸 3.3 — **청크 맥락 줄** — 추출에 넘기는 청크 머리 한 줄 (B102 ①).

「이 청크가 어디를 말하는가」를 판단할 재료를 한 줄로 준다:
`[문서: <파일 이름> · 개요: <문서 개요> · 공정: <조각 공정(목록) 또는 문서 좌표> · 시트: <엑셀 시트> · 경로: <상위 제목 › … › 구획>]`.
개요 칸은 문서 구조가 문서에 낸 개요가 있을 때만(PPT 덱 개요 — B125 ③ · 다른 포맷은 없으면 칸 없음).
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
    from core.build.extract_reading import doc_labels
    src = (env or {}).get("source_path") or ""
    lab = doc_labels(env)                    # 판독의 그림 속 글자(B170 — 소속 출처 재검사 · 읽은 쪽이 있을 때만 칸)
    return {"name": PurePath(str(src)).name if src else None,
            "coord": (env or {}).get("doc_coord"),
            # 문서 개요 — 봉투 덱 블록(B143 ② · 덱 구조 — 없으면 칸 없음) · 옛 키 `doc_overview`는 재파싱 전 봉투
            "overview": ((env or {}).get("deck") or {}).get("overview") or (env or {}).get("doc_overview"),
            **({"reading": lab} if lab else {})}


def _path(p):
    s = str(p)
    for sep in _SEPS:
        s = s.replace(sep, PATH_SEP)
    return s


def context_fields(chunk, doc=None):
    """맥락 칸 `[(이름, 값)]` — 값이 있는 칸만 · 순서 문서 → 개요 → 공정 → 시트 → 경로 → 다루는 것(PPT 덱 판단의 `meta.subject` —
    B151 ③ · 덱 블록이 정본)."""
    m = chunk.get("meta") or {}
    sheet = m.get("sheet")
    path = m.get("section_path")
    from parser.normalizer import coord_text
    coord = coord_text(chunk.get("process_ref")) or (doc or {}).get("coord")      # 공정은 목록 (B125 ④)
    out = [("문서", (doc or {}).get("name")), ("개요", (doc or {}).get("overview")), ("공정", coord), ("시트", sheet)]
    # 경로가 시트 이름 그 자체면(제목 없는 시트) 두 번 싣지 않는다
    if path and str(path) != str(sheet or ""):
        out.append(("경로", _path(path)))
    out.append(("다루는 것", m.get("subject")))
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


def around(text, surface, chars):
    """**표기 앞뒤 글**(B123 ③ — 2차 판정의 문장) — `{"text", "span": [시작, 끝]}` · 청크 원문에서 그 표기가 처음 나온 자리의
    앞뒤 `chars`자(표기 그대로 → 라틴 대소문자 무시 순) · 없거나 `chars`가 0이면 None(2차를 부르지 않는다)."""
    text, surface = str(text or ""), str(surface or "").strip()
    if not text or not surface or not chars:
        return None
    i = text.find(surface)
    if i < 0:
        i = text.lower().find(surface.lower())
    if i < 0:
        return None
    a, b = max(0, i - chars), min(len(text), i + len(surface) + chars)
    return {"text": text[a:b], "span": [a, b]}


def place(chunk):
    """**위치 두 칸**(B118 ③) — `(시트, 청크)`: 시트 이름(없으면 빈칸) · 청크 = **경로 끝 제목**(경로가 없으면 조각의 구획
    · 그것도 없으면 위치). 가운데 경로는 생략한다 — 전체는 라벨(`chunk_label`)이 들고 명령 로그에 그대로다.
    화면의 판정 예고 값 표 · 추출 청크 표가 이 함수 하나를 쓴다(포맷 전부)."""
    f = dict(context_fields(chunk))
    path = f.get("경로")
    loc = str(chunk.get("source_locator") or "")
    sheet = str(f.get("시트") or "")
    if not sheet and not path and "!" in loc:      # 표의 행 — 시트가 위치 안에 있다(`시트!R12`)
        sheet, _sep, loc = loc.rpartition("!")
    end = (str(path).split(PATH_SEP)[-1] if path else "") or str(chunk.get("section") or "") or loc
    return sheet, end


def chunk_label(chunk):
    """**청크의 라벨** — 화면의 청크 목차 · 추출 표의 위치 칸(B112 ③). 맥락 칸에서 문서 · 공정을 뺀 것 —
    엑셀 `시트 › 목차 경로` · Word/PDF `제목 경로` · 시트도 경로도 없으면 조각의 구획(PPT `슬라이드 n`) ·
    그것도 없으면 위치. 포맷 전부 이 함수 하나다(셀 범위 위치는 로그가 든다)."""
    f = dict(context_fields(chunk))
    parts = [v for k, v in (("시트", f.get("시트")), ("경로", f.get("경로"))) if v]
    return (PATH_SEP.join(str(x) for x in parts) or str(chunk.get("section") or "")
            or str(chunk.get("source_locator") or ""))

