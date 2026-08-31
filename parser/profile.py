# -*- coding: utf-8 -*-
"""열 프로파일 — **전 행을 스캔한 결정적 통계** (문서 6 B39).

등록 세션의 관찰 재료는 지금까지 **앞 N줄의 원문**뿐이었다. 그 창으로는
「이 열은 행마다 고유한가 반복하는가」·「거의 비어 있는가」가 보이지 않고, 그러면
LLM은 근거 없이 배정한다(실측: 사내 CP 50열 중 attribute 25).

**전 행을 센다 — 그것이 이 모듈의 전부다.** 통계는 상수 크기라 수천 행 표본에서도
프롬프트가 커지지 않는다. **LLM을 부르지 않고 결정적이다.**

`reader_head` **그릇 안의 항목**으로 실린다 — 시스템 5키를 늘리지 않는다(B36).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

# ── 기계 제안의 임계 (가결정 — DECISIONS D-104 · 실측 후 조정 대상) ──────
SPARSE_EMPTY_RATIO = 0.7      # 빈 셀이 이 비율을 넘으면 「판정 보류 제안」
SAMPLE_VALUES = 4             # 대표값 개수
SAMPLE_CHARS = 30             # 대표값 1개의 최대 길이
SEQ_PATTERN = re.compile(r"^\s*(no\.?|#)?\s*\d{1,6}\s*$", re.I)
NUM_UNIT = re.compile(r"^\s*[±<>~]?\s*-?\d+(\.\d+)?\s*[^\d\s]{0,6}\s*$")

_ADDR = re.compile(r"^([A-Z]+)(\d+)$")


def _split(addr):
    m = _ADDR.match(addr)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def columns(sheet, *, header_row=None, data_start=None):
    """시트의 열별 값 목록 — `{열문자: [(행, 값), …]}`. 헤더 행은 뺀다."""
    out = defaultdict(list)
    for addr, v in (sheet.get("cells") or {}).items():
        col, row = _split(addr)
        if col is None or v is None or str(v).strip() == "":
            continue
        if header_row and row <= header_row:
            continue
        if data_start and row < data_start:
            continue
        out[col].append((row, str(v).strip()))
    return dict(out)


def _shape(vals):
    """값 형태 — **간단한 것만**(명세 문면 그대로: 수치+단위 비율·평균 길이)."""
    if not vals:
        return {}
    num = sum(1 for v in vals if NUM_UNIT.match(v))
    return {"수치단위_비율": round(num / len(vals), 2),
            "평균_길이": round(sum(len(v) for v in vals) / len(vals), 1),
            "최대_길이": max(len(v) for v in vals)}


def _coord_variation(colvals, coord_col, rows_total):
    """**좌표 기준 변동성** — 같은 좌표 그룹 안에서 값이 변하는가.

    좌표 열을 식별하지 못하면 **내지 않는다.** 추측한 통계는 지어낸 근거와 같다
    (명세 B39 — 「식별 못 하면 생략」).
    """
    if not coord_col or coord_col not in colvals:
        return None
    coord = dict(colvals[coord_col])
    out = {}
    for col, pairs in colvals.items():
        if col == coord_col:
            continue
        groups = defaultdict(set)
        for row, v in pairs:
            c = coord.get(row)
            if c is not None:
                groups[c].add(v)
        if not groups:
            continue
        varying = sum(1 for s in groups.values() if len(s) > 1)
        out[col] = {"좌표그룹수": len(groups), "그룹내_값변동": varying}
    return out or None


def profile(sheet, *, header_row=None, data_start=None, coord_col=None):
    """열 프로파일 + 기계 제안. **무LLM · 결정적.**

    `coord_col`은 좌표 열의 열문자다 — 어댑터가 아직 없는 등록 시점에는 대개
    모르고, 그때는 `좌표기준_변동성`이 빠진다(위 함수 주석).
    """
    colvals = columns(sheet, header_row=header_row, data_start=data_start)
    if not colvals:
        return {}
    rows = {r for pairs in colvals.values() for r, _ in pairs}
    total = len(rows)
    coord_var = _coord_variation(colvals, coord_col, total)

    prof = {}
    for col in sorted(colvals, key=lambda c: (len(c), c)):
        vals = [v for _r, v in colvals[col]]
        uniq = Counter(vals)
        filled = len(vals)
        rep = [v[:SAMPLE_CHARS] for v, _ in uniq.most_common(SAMPLE_VALUES)]
        item = {
            "비지_않은_행수": filled,
            "고유값수": len(uniq),
            "빈셀비율": round(1 - filled / total, 2) if total else 0.0,
            "대표값": rep,
            "형태": _shape(vals),
            "기계제안": _suggest(filled, len(uniq), total, vals),
        }
        if coord_var and col in coord_var:
            item["좌표기준_변동성"] = coord_var[col]
        prof[col] = item
    return {"전체_행수": total, "열수": len(prof), "열": prof}


def _suggest(filled, uniq, total, vals):
    """기계 제안 — **판정이 아니라 재료다**(명세 B39 ②: 제안은 재료다).

    임계는 가결정이다(D-104) — 실측 후 조정 대상이고, 그래서 숫자를 이 모듈
    머리의 상수 하나로 모아 둔다.
    """
    if total and filled and uniq == 1:
        return {"제안": "meta", "사유": "전 행 동일 — 문서의 속성이지 노드의 속성이 아니다"}
    if total and (1 - filled / total) > SPARSE_EMPTY_RATIO:
        return {"제안": "판정 보류",
                "사유": f"빈 셀 비율 {round(1 - filled / total, 2)} — 값이 거의 없다"}
    if total and filled == uniq == total and all(SEQ_PATTERN.match(v) for v in vals):
        return {"제안": "UNMAPPABLE", "사유": "행마다 고유한 연번·페이지 계열"}
    return {"제안": "role 판정 대상", "사유": ""}


def summary(prof):
    """제안 분포 한 줄 — 화면과 보고에 쓴다."""
    c = Counter(v["기계제안"]["제안"] for v in (prof.get("열") or {}).values())
    return dict(c)
