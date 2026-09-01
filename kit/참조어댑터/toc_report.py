# 원본: tests/fixtures/fixtures/adapters/toc_report.py (외부 LLM 실산출 스냅샷)
# — prose 계열이라 병합·상동·복수값 로직이 없다: 규약 10 전환 대상이 아니다(B27).
# 스냅샷 원문은 fixture가 보관한다 — 여기는 **모범 전시장**이다.
import re

ADAPTER = {
    "doc_type": "toc_report",
    "adapter_version": "1.0",
    "payload_kind": "prose",              # 목차형 보고서 — 행=record 아님
    "expects": {                          # 분할 신호 상수 (관찰 기록)
        "title_row": 1,                   # 힌트: 1행은 문서 제목 → meta로만 소비
        "content_column": "A",            # 두 표본 모두 max_col=1, 단일 열
        "heading_pattern": r"^(\d+(?:\.\d+)*)\.?\s+\S",  # "1." / "1.1" / "1.1.1" — 두 표본에서 3계층 반복 관찰
        "section_sep": " > ",             # section 헤딩 경로 구분자
        # **판단 상수 — preflight 지문이 아니다**(문서 6 §6.4-4). 값이 달라도
        # `adapter_mismatch`를 내지 않는다: 「이 양식이 맞나」가 아니라 「얼마나
        # 굵게 자르나」의 선택이다.
        #
        # **1을 고른 근거 — 레벨별 분포 실측**(B45 분포 화면):
        #   TOC01 · 레벨 1: 3청크 2~10행(평균 5.3) · 구간(5~40)내 1
        #           레벨 2: 7청크 1~4행(2.3) · 구간내 0 / 레벨 3: 9청크 1~2행 · 0
        #   TOC02 · 레벨 1: 3청크 2~7행(4.3) · 구간내 1 / 레벨 2: 8청크 1~3행 · 0
        # 레벨 2·3에서는 **한 청크가 1~4행**이라 근거로 못 쓴다. 레벨 1만이
        # 목표 구간에 든다. **결정은 등록 때 한 번이다** — 매 문서 모델이 고르지 않는다.
        "split_level": 1,
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
            fragments.append({
                "text": "\n".join(t for _, t in buf),
                "section": section_path(),
                "meta": {"doc_title": title},
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
                # **상수 이하 깊이에서만 자른다**(B45 정정). 상수가 없으면 종전
                # 동작(전 헤딩 분할) — 기존 어댑터가 깨지지 않아야 한다.
                # **`section` 경로는 상수와 무관하게 전 헤딩을 반영한다** —
                # 자르지 않은 깊은 헤딩도 경로에는 남는다(좌표 파생 B43의 재료다).
                lvl = ADAPTER["expects"].get("split_level")
                if lvl is None or depth <= lvl:
                    flush()
                while stack and stack[-1][0] >= depth:
                    stack.pop()
                stack.append((depth, text))
            else:
                buf.append((row, text))
        flush()
    return fragments
