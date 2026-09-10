# 원본: tests/fixtures/fixtures/adapters/toc_report.py (외부 LLM 실산출 스냅샷)
# — prose 계열이라 병합·상동·복수값 로직이 없다: 규약 10 전환 대상이 아니다(B27).
# 스냅샷 원문은 fixture가 보관한다 — 여기는 **모범 전시장**이다.
import re

from parser import struct_map

ADAPTER = {
    "doc_type": "toc_report",
    "adapter_version": "1.0",
    "payload_kind": "prose",              # 목차형 보고서 — 행=record 아님
    "expects": {                          # 분할 신호 상수 (관찰 기록)
        "title_row": 1,                   # 힌트: 1행은 문서 제목 → meta로만 소비
        "content_column": "A",            # 두 표본 모두 max_col=1, 단일 열
        "heading_pattern": r"^(\d+(?:\.\d+)*)\.?\s+\S",  # "1." / "1.1" / "1.1.1" — 두 표본에서 3계층 반복 관찰
        "section_sep": " > ",             # section 헤딩 경로 구분자
        # **분할 레벨 상수는 없다**([정정] 46). 구판 전시물은 여기에
        # `"split_level": 1`을 박고 「결정은 등록 때 한 번이다」라고 적었는데,
        # 그 설계가 뒤집혔다 — **레벨은 인입마다 규칙이 계산한다.**
        #
        # 근거는 실측이다: 같은 doc_type의 두 표본이 이미 갈렸다.
        #   TOC01 · 레벨 1의 평균 5.3행 — 목표 구간(5~40) **안**
        #   TOC02 · 레벨 1의 평균 4.3행 — 목표 구간 **밖**(최근접으로 떨어진다)
        # 판본마다 목차 세밀도가 다르면 등록 때 박은 상수는 구조적으로 못 따라간다.
        # 규칙은 `parser.struct_map.choose_level` 하나이고 **재구현하지 않는다**
        # (규약 10과 같은 결 — 두 벌이면 화면의 레벨과 자른 레벨이 갈린다).
        "max_col": 1,
    },
}

_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
_CELL_RE = re.compile(r"^[A-Z]+(\d+)$")


def extract(raw) -> list[dict]:
    """reader 원시 추출물 → 정규 조각(청크) 리스트. 조각마다 source_locator 포함.

    분할 규칙(관찰 근거):
    - 헤딩 판정은 번호 패턴만 사용한다. bold(표본1 A4·A7 헤딩이 비굵음)와
      indent(표본1 A12=5 등 잡음)는 두 표본에서 비신뢰로 관찰되어 쓰지 않는다.
    - 같은 헤딩 아래 연속 본문 행은 하나의 청크로 묶는다.
    - 이미지는 placeholder 조각 {source_locator, image_ref, section}으로만 낸다.
    - 1행 제목은 청크가 아니라 각 조각 meta.doc_title로만 실린다.
    """
    fragments = []
    for sheet in raw["sheets"]:
        name = sheet["name"]
        cells = sheet["cells"]

        images_by_row = {}
        for img in sheet.get("images", []):
            m = _CELL_RE.match(img["cell"])
            if m:
                images_by_row.setdefault(int(m.group(1)), []).append(img)

        # **레벨은 자르기 전에 규칙이 정한다**([정정] 46) — 줄 목록과 헤딩 레벨을
        # 먼저 훑어 분포를 세고, `choose_level`이 고른다. 매 문서 모델을 부르지
        # 않으므로 「규칙 고정 → 결정적 실행」이 유지된다.
        _lines, _rows = [], []
        for _r in range(2, sheet["max_row"] + 1):
            _v = cells.get(f"A{_r}")
            _t = "" if _v is None else str(_v).strip()
            if not _t:
                continue
            _lines.append((_r, _t))
            _m = _HEADING_RE.match(_t)
            _rows.append({"row": _r, "heading": bool(_m),
                          "level": len(_m.group(1).split(".")) if _m else 0})
        lvl, _why, _oor = struct_map.choose_level(
            struct_map.level_stats({"rows": _rows}, _lines))

        title = str(cells.get("A1", "")).strip()
        stack = []   # [(depth, heading_text)] — 현재 헤딩 경로
        buf = []     # [(row, text)] — 현재 청크로 모이는 본문 행

        def section_path():
            return " > ".join(h for _, h in stack)

        def flush():
            if not buf:
                return
            start, end = buf[0][0], buf[-1][0]
            loc = f"{name}!A{start}" if start == end else f"{name}!A{start}:A{end}"
            meta = {"doc_title": title, "split_level": lvl}
            if _oor:
                # 규칙이 목표 구간을 못 맞춰 최근접으로 떨어졌다 — 인입이 이
                # 표시를 보고 `hierarchy_unresolved` 큐를 단다([정정] 46).
                meta["split_level_out_of_range"] = True
            fragments.append({
                "text": "\n".join(t for _, t in buf),
                "section": section_path(),
                "meta": meta,
                "source_locator": loc,
            })
            buf.clear()

        for row in range(2, sheet["max_row"] + 1):
            if row in images_by_row:
                flush()
                for img in images_by_row[row]:
                    fragments.append({
                        "source_locator": f"{name}!{img['cell']}",
                        "image_ref": img["ref"],
                        "section": section_path(),
                    })
            val = cells.get(f"A{row}")
            if val is None or str(val).strip() == "":
                continue  # 빈 행 = 구획 여백, 신호 없음
            text = str(val).strip()
            m = _HEADING_RE.match(text)
            if m:
                depth = len(m.group(1).split("."))
                # **규칙이 고른 레벨 이하에서만 자른다.** 헤딩이 없어 규칙이
                # 고를 것이 없으면(`None`) 종전 동작인 전 헤딩 분할이다.
                # **`section` 경로는 레벨과 무관하게 전 헤딩을 반영한다** —
                # 자르지 않은 깊은 헤딩도 경로에는 남는다(좌표 파생 B43의 재료다).
                if lvl is None or depth <= lvl:
                    flush()
                while stack and stack[-1][0] >= depth:
                    stack.pop()
                stack.append((depth, text))
            else:
                buf.append((row, text))
        flush()
    return fragments
