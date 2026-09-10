# -*- coding: utf-8 -*-
"""기본 어댑터 (xlsx/csv 산문) — **줄 목록 + 계층 신호**가 전부다 (B58 ③ · 문서 6 §6.4-5).

`.pptx`는 슬라이드가, `.pdf`는 쪽이 경계를 준다. 스프레드시트에는 그런 경계가 없어
**계층을 읽어야** 자를 자리가 나온다. 읽을 재료는 리더가 이미 전부 준다
(`parser/reader.py` — `indent`·`bold`·`merged` + 셀 문자열의 번호 패턴).

**doc_type마다 만들지 않는다**([개정] B58-2) — 어댑터가 분할하지 않는 이상 prose
어댑터에 남는 일은 **포맷별 줄 목록 만들기**뿐이고, 그것은 doc_type이 아니라 포맷이
정한다. 등재는 `basic_ppt`·`basic_pdf`와 같은 **위임 래퍼**다(B47 · D-111).

**LLM 0회다.** 계층 판정도 레벨 선택도 결정적 연산이고, 지도 패스(⑦)를 부르지
않는다 — 부르면 인입마다 비용이 조용히 붙는다([개정] B58-1). 자르는 일은
`parser.struct_map`의 공용 함수가 한다: 규약 10과 같은 결이다 — **재구현하지 않는다.**
분할 규칙이 두 벌이면 지도 경로와 어댑터 경로의 청크가 갈린다.

**대가**: preflight 양식 표류 감지를 포기한다. 구조 가변 prose는 「판본마다 구조가
다른 것이 기본값」이라 표류라는 개념이 성립하지 않는다(§6.4-5).
"""
from __future__ import annotations

import re

from parser import struct_map

ADAPTER = {
    "doc_type": "prose_xlsx_basic",
    "adapter_version": "1.0",
    "payload_kind": "prose",
    "expects": {
        # 분할 신호 상수 — preflight가 보는 지문(prose는 헤더 행이 없다).
        # **레벨은 여기 없다**([정정] 46) — 인입마다 규칙이 계산한다. 상수로 박으면
        # 같은 doc_type의 판본마다 다른 목차 세밀도를 구조적으로 못 따라간다.
        "split_on": "heading",
        "heading_pattern": r"^(\d+(?:\.\d+)*)[.)]?\s+",
        "heading_signals": ["번호", "굵게", "들여쓰기", "가로병합"],
        "section_sep": " > ",
        "frame_format": "{sheet}!R{a}",
    },
}

PATH_HEADING = "heading"        # 계층 분할 — 정상 경로
PATH_FLAT = "flat"              # 헤딩 0건 — 시트 통째 (조용한 오파싱을 만들지 않는다)

_NUM = re.compile(ADAPTER["expects"]["heading_pattern"])
_CELL = re.compile(r"^([A-Z]+)(\d+)$")

# **가로 병합만 구획 제목의 신호다.** 세로 병합(`A4:A31`)은 표의 상동 셀이지
# 제목이 아니다 — 둘을 섞으면 관리계획서의 공정구분 열이 통째로 헤딩이 된다.
MIN_MERGE_COLS = 2


def _addr(a):
    m = _CELL.match(a)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def _content_column(sheet):
    """본문 열 — **글자가 가장 많이 든 열**. 동점은 앞 열(결정적).

    산문 스프레드시트는 한 열에 글이 흐른다. 열을 `A`로 박지 않는 이유는 표지·번호
    열이 앞에 붙은 판본이 흔하기 때문이고, 「가장 긴 열」이 아니라 「가장 많이 든
    열」인 이유는 한 셀에 통째로 붙은 열이 뽑히면 줄 목록이 한 줄이 되기 때문이다.
    """
    tally = {}
    for a, v in (sheet.get("cells") or {}).items():
        col, _row = _addr(a)
        if col and str(v).strip():
            tally[col] = tally.get(col, 0) + 1
    if not tally:
        return None
    return min(sorted(tally), key=lambda c: -tally[c])


def _wide_merges(sheet):
    """가로로 2열 이상 걸친 병합의 **시작 행 집합** — 구획 제목의 신호."""
    out = set()
    for rng in sheet.get("merged") or []:
        try:
            lo, hi = rng.split(":")
        except ValueError:
            continue
        c1, r1 = _addr(lo)
        c2, _r2 = _addr(hi)
        if c1 and c2 and r1 and len(c2) * 26 + ord(c2[-1]) - (len(c1) * 26 + ord(c1[-1])) \
                >= MIN_MERGE_COLS - 1:
            out.add(r1)
    return out


def _rows_of(sheet, col):
    """`(줄 목록, 헤딩 판정 rows)` — **신호 넷의 우선순위는 명시적이다.**

    | 신호 | 레벨 | 왜 이 순서인가 |
    |---|---|---|
    | 번호 패턴 `1.2.3` | 점의 개수 | 사람이 **직접 적은** 깊이다 — 가장 강한 근거 |
    | 가로 병합 | 1 | 구획 제목의 관용 서식. 깊이 정보는 없다 |
    | 굵게 | 들여쓰기 + 1 | 서식은 깊이를 말하지 않으므로 들여쓰기가 보탠다 |
    | 들여쓰기만 | — | **헤딩이 아니다.** 본문 인용도 들여쓴다 |

    들여쓰기 단독을 헤딩으로 치지 않는 것이 핵심이다 — 치면 인용문 한 줄이 구획을
    열어 그 아래 본문이 통째로 엉뚱한 `section`을 얻는다.
    """
    cells = sheet.get("cells") or {}
    bold = set(sheet.get("bold") or [])
    indent = sheet.get("indent") or {}
    wide = _wide_merges(sheet)
    lines, rows = [], []
    for r in range(1, int(sheet.get("max_row") or 0) + 1):
        a = f"{col}{r}"
        text = str(cells.get(a, "")).strip()
        if not text:
            continue
        lines.append((r, text))
        m = _NUM.match(text)
        if m:
            lv = len(m.group(1).split("."))
        elif r in wide:
            lv = 1
        elif a in bold:
            lv = int(indent.get(a, 0)) + 1
        else:
            lv = 0
        rows.append({"row": r, "heading": bool(lv), "level": lv})
    return lines, rows


def extract(raw, struct_map_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. **시트가 프레임이다.**

    `struct_map_fn`은 받되 **부르지 않는다** — 계약(§6.4-2)의 서명을 맞추기 위한
    것이고, 이 계열은 규칙이 레벨을 정하므로 지도 패스가 필요 없다([개정] B58-1).
    """
    exp = ADAPTER["expects"]
    sep = exp["section_sep"]
    out = []
    for sh in raw.get("sheets") or []:
        name = sh.get("name") or "Sheet1"
        col = _content_column(sh)
        if not col:
            continue
        lines, rows = _rows_of(sh, col)
        if not lines:
            continue

        def locator(a, b, _n=name, _c=col):
            base = exp["frame_format"].format(sheet=_n, a=a)
            return base if a == b else f"{base}-R{b}"

        if not any(r["heading"] for r in rows):
            # **헤딩 0건 — 통째로 낸다.** 빈 산출도, 지어낸 분할도 만들지 않는다.
            out.append({
                "source_locator": locator(lines[0][0], lines[-1][0]),
                "section": name,
                "text": "\n".join(t for _r, t in lines),
                "meta": {"split_path": PATH_FLAT, "frame": name,
                         "section_path": name, "content_column": col,
                         "hierarchy_unresolved": True,
                         "unresolved_reason": "계층 신호 0건 — 시트를 통째로 실었다"},
            })
            continue

        smap = {"rows": rows}
        stats = struct_map.level_stats(smap, lines)
        pick, why, oor = struct_map.choose_level(stats)
        smap.update({"레벨_분포": stats, "분할_레벨": pick,
                     "분할_레벨_사유": why, "분할_레벨_구간밖": oor})
        for c in struct_map.split(smap, lines, locator, sep):
            meta = {**(c.get("meta") or {}), "split_path": PATH_HEADING,
                    "frame": name, "content_column": col,
                    "split_level": pick, "section_path": c.get("section") or name}
            out.append({**c, "section": c.get("section") or name, "meta": meta})
    return out


def level_report(raw):
    """레벨 선택의 **판단 재료** — 검수 화면과 큐가 읽는다. `extract`와 같은 계산이다.

    프레임(시트)마다 `{프레임, 분할_레벨, 분할_레벨_사유, 레벨_분포, 구간밖}`.
    `struct_map.adapter_level_picks`와 **같은 형태**를 낸다 — 화면이 둘로 갈리지 않게.
    """
    out = []
    for sh in raw.get("sheets") or []:
        col = _content_column(sh)
        if not col:
            continue
        lines, rows = _rows_of(sh, col)
        if not lines or not any(r["heading"] for r in rows):
            continue
        stats = struct_map.level_stats({"rows": rows}, lines)
        pick, why, oor = struct_map.choose_level(stats)
        out.append({"프레임": sh.get("name"), "분할_레벨": pick,
                    "분할_레벨_사유": why, "레벨_분포": stats,
                    "분할_레벨_구간밖": oor})
    return out
