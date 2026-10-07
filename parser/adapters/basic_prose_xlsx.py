# -*- coding: utf-8 -*-
"""칸 2.6 — 기본 어댑터 (xlsx/csv 산문) — **줄 목록 + 계층 신호**가 전부다 (B58 ③ · 문서 6 §6.4-5).

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

from parser import struct_map, struct_rule

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
PATH_RULE = "rule"              # 규칙 선언을 적용해 계층이 섰다 (B87 ②)
PATH_IMAGE = "image"            # 시트 그림 — ④ 이미지 요약 placeholder (B88 ①)
CONTEXT_CHARS = 1500            # 그림에 딸려 보내는 맥락 — 같은 청크 본문 앞부분 (PDF 쪽 맥락과 같은 폭)

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


# 헤딩 신호의 이름 — 화면·기록이 같은 말을 쓴다 (B68 ①)
SIG_NUM, SIG_MERGE, SIG_BOLD = "번호", "가로병합", "굵게+들여쓰기"
SIG_RULE = struct_rule.SIG_RULE  # B87 ② — 선언의 패턴으로 잡은 제목
MAP_SOURCE = "adapter:basic_prose_xlsx"


def _rows_of(sheet, col):
    """`(줄 목록, 헤딩 판정 rows)` — **신호 넷의 우선순위는 명시적이다.**

    | 신호 | 레벨 | 왜 이 순서인가 |
    |---|---|---|
    | 번호 패턴 군(B87 ①) | 점 번호는 점의 개수 · 다른 군은 시트 안 첫 등장 순서 | 사람이 **직접 적은** 깊이다 — 가장 강한 근거 |
    | 가로 병합 | 1 | 구획 제목의 관용 서식. 깊이 정보는 없다 |
    | 굵게 | 들여쓰기 + 1 | 서식은 깊이를 말하지 않으므로 들여쓰기가 보탠다 |
    | 들여쓰기만 | — | **헤딩이 아니다.** 본문 인용도 들여쓴다 |

    들여쓰기 단독을 헤딩으로 치지 않는 것이 핵심이다 — 치면 인용문 한 줄이 구획을
    열어 그 아래 본문이 통째로 엉뚱한 `section`을 얻는다. 번호 군과 짧은 행 조건
    (`struct_map.HEADING_MAX_CHARS`)은 `parser.struct_map`이 소유한다 — 패턴이 두 벌이면
    어댑터와 지도 경로의 제목이 갈린다.
    """
    cells = sheet.get("cells") or {}
    bold = set(sheet.get("bold") or [])
    indent = sheet.get("indent") or {}
    wide = _wide_merges(sheet)
    lines = []
    for r in range(1, int(sheet.get("max_row") or 0) + 1):
        text = str(cells.get(f"{col}{r}", "")).strip()
        if text:
            lines.append((r, text))
    nums = struct_map.number_levels(lines)
    rows = []
    for r, _text in lines:
        a = f"{col}{r}"
        if r in nums:
            lv, fam = nums[r]
            sig = _num_signal(fam)
        elif r in wide:
            lv, sig = 1, SIG_MERGE
        elif a in bold:
            lv, sig = int(indent.get(a, 0)) + 1, SIG_BOLD
        else:
            lv, sig = 0, None
        # **무엇으로 정했는지를 남긴다**(B68 ①) — 판정 규칙도 순서도 그대로다.
        # 구판은 결과(level)만 남기고 신호를 버려서, 사람이 「무엇을 기준으로
        # 잘랐나」를 화면 어디에서도 볼 수 없었다(사내 실측 여덟째).
        rows.append({"row": r, "heading": bool(lv), "level": lv, "signal": sig})
    return lines, rows


def _num_signal(fam):
    """신호 이름에 **군**을 싣는다(B87 ①) — 점 번호는 구판 이름 그대로(`번호`)."""
    if fam == struct_map.DOTTED:
        return SIG_NUM
    return f"{SIG_NUM}({struct_map.FAMILY_LABEL.get(fam, fam)})"


def split_basis(rows):
    """`분할_기준` 문면 — 헤딩을 **어느 신호로** 잡았나를 신호별 수로.

    합이 헤딩 수와 같다(성질) — 신호 없이 헤딩이 된 행은 없다.
    """
    cnt = {}
    for r in rows:
        if r.get("heading") and r.get("signal"):
            cnt[r["signal"]] = cnt.get(r["signal"], 0) + 1
    # 순서: 점 번호 → 다른 번호 군(처음 나온 순) → 가로병합 → 굵게 (B87 ①)
    keys = ([SIG_NUM] + [k for k in cnt if k.startswith(SIG_NUM + "(")]
            + [SIG_RULE, SIG_MERGE, SIG_BOLD])
    inner = " · ".join(f"{k} {cnt[k]}" for k in keys if cnt.get(k))
    return f"어댑터 신호: {inner or '없음'}"


def rule_frames(raw):
    """**고정 규칙으로 안 선 시트** — 규칙 선언의 대상이다(B87 ②). 예고와 검수가 읽는다.

    `size_out_of_band`(계층은 섰는데 크기가 구간 밖)는 대상이 아니다 — 큐만 뜬다.
    """
    out = []
    for sh in raw.get("sheets") or []:
        col = _content_column(sh)
        if not col:
            continue
        lines, rows = _rows_of(sh, col)
        if lines and not struct_rule.fixed_ok(rows):
            out.append(sh.get("name") or "Sheet1")
    return out


def rule_sample(sheet, col):
    """모델이 보는 재료 — 본문 열 **앞 N행**의 글과 표시(굵게 · 들여쓰기 · 가로병합 시작).

    글자 크기는 리더가 내지 않는다(D-168 ⑤) — 여기 없는 표시는 모델도 보지 않는다.
    """
    cells = sheet.get("cells") or {}
    bold = set(sheet.get("bold") or [])
    indent = sheet.get("indent") or {}
    wide = _wide_merges(sheet)
    out = []
    for r in range(1, int(sheet.get("max_row") or 0) + 1):
        a = f"{col}{r}"
        text = str(cells.get(a, "")).strip()
        if not text:
            continue
        out.append({"row": r, "text": text[:struct_rule.RULE_SAMPLE_CHARS],
                    "bold": a in bold, "indent": int(indent.get(a, 0) or 0),
                    "merge": r in wide})
        if len(out) >= struct_rule.RULE_SAMPLE_ROWS:
            break
    return out


def _rows_by_rule(sheet, col, decl):
    """선언 적용의 엑셀 몫 — 줄 목록과 표시(제목 열 · 굵게 · 들여쓰기 · 가로병합)를 대고
    판정은 `struct_rule.apply`가 한다(엑셀·Word 한 벌 · B88 ②)."""
    cells = sheet.get("cells") or {}
    bold = set(sheet.get("bold") or [])
    indent = sheet.get("indent") or {}
    wide = _wide_merges(sheet)
    hcol = decl.get("heading_column") or col
    lines, marks = [], {}
    for r in range(1, int(sheet.get("max_row") or 0) + 1):
        body = str(cells.get(f"{col}{r}", "")).strip()
        head = str(cells.get(f"{hcol}{r}", "")).strip() if hcol != col else body
        text = body or head
        if not text:
            continue
        lines.append((r, text))
        marks[r] = {"head": head, "bold": f"{hcol}{r}" in bold,
                    "indent": int(indent.get(f"{hcol}{r}", 0) or 0), "merge": r in wide}
    return lines, struct_rule.apply(lines, marks, decl)


def extract(raw, struct_map_fn=None, struct_rule_fn=None) -> list[dict]:
    """reader 원시 추출물 → 청크 리스트. **시트가 프레임이다.**

    `struct_map_fn`은 받되 **부르지 않는다** — 계약(§6.4-2)의 서명을 맞추기 위한
    것이고, 이 계열은 규칙이 레벨을 정하므로 지도 패스가 필요 없다([개정] B58-1).

    `struct_rule_fn(frame, sample)`은 **고정 규칙으로 안 선 시트에서만** 부른다(B87 ②) —
    코어가 주입하는 훅이고(⑦ 호출 태그 `struct_rule`), 돌아온 선언을 **데이터로** 적용한다.
    없으면(mock · 등록 리허설 · 킷 관문) **구판과 같은 동작**이다. 선언이 안 서면 구판의
    길로 떨어진다 — 제목 0건이면 통째 + 큐, 비단조면 고정 규칙 분할.
    """
    out = []
    for sh in raw.get("sheets") or []:
        mine = _sheet_chunks(sh, struct_rule_fn)
        out += mine + _image_pieces(sh, mine)
    return out


_ROWS = re.compile(r"!R(\d+)(?:-R(\d+))?$")


def _image_pieces(sheet, chunks):
    """시트 그림 = **placeholder 조각**(B88 ①) — 요약은 코어(tagger)가 ④로 한다(규약 3).

    `section`은 그림이 앉은 행이 속한 청크의 것이고 `context`는 그 청크 본문 앞부분이다 —
    PPT의 「같은 슬라이드 텍스트」와 같은 뜻. 그림 앞 청크가 없으면 첫 청크를 쓴다.
    `ref` 시트의 그림을 빼는 것은 파이프라인이다(시트 역할은 어댑터가 모른다).
    """
    name = sheet.get("name") or "Sheet1"
    spans = []
    for c in chunks:
        m = _ROWS.search(c.get("source_locator") or "")
        if m:
            spans.append((int(m.group(1)), int(m.group(2) or m.group(1)), c))
    out = []
    for im in sheet.get("images") or []:
        row = int("".join(ch for ch in str(im.get("cell") or "1") if ch.isdigit()) or 1)
        host = next((c for a, b, c in spans if a <= row <= b), None) \
            or next((c for a, _b, c in reversed(spans) if a <= row), None) \
            or (spans[0][2] if spans else None)
        section = (host or {}).get("section") or name
        meta = {"split_path": PATH_IMAGE, "frame": name, "shape_kind": "picture",
                "shape_id": im["ref"], "cell": im.get("cell"), "section_path": section, "sheet": name}
        if im.get("mime"):
            meta["image_mime"] = im["mime"]
        out.append({"source_locator": f"{name}!{im.get('cell')}#{im['ref']}",
                    "section": section, "image_ref": im["ref"],
                    "context": ((host or {}).get("text") or "")[:CONTEXT_CHARS],
                    "meta": meta})
    return out


def _sheet_chunks(sh, struct_rule_fn):
    """시트 하나의 글 조각 — 순서는 `struct_rule.frame_chunks` 한 벌이다(엑셀·Word 같이)."""
    exp = ADAPTER["expects"]
    name = sh.get("name") or "Sheet1"
    col = _content_column(sh)
    if not col:
        return []
    lines, rows = _rows_of(sh, col)
    if not lines:
        return []

    def locator(a, b, _n=name):
        base = exp["frame_format"].format(sheet=_n, a=a)
        return base if a == b else f"{base}-R{b}"

    return struct_rule.frame_chunks(
        # 시트명은 늘 싣는다(B102 ① — 맥락 줄의 시트 칸 · 제목이 있으면 구획 경로에 시트가 없다)
        name, lines, rows, locator, exp["section_sep"], {"content_column": col, "sheet": name},
        rule_fn=struct_rule_fn, sample_fn=lambda: rule_sample(sh, col),
        by_rule=lambda decl: _rows_by_rule(sh, col, decl),
        flat_reason="계층 신호 0건 — 시트를 통째로 실었다")


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
                    "분할_레벨_구간밖": oor,
                    # **한 필드 이름, 두 경로**(B68 ①) — 지도 경로의 pick도 같은
                    # 키를 낸다. 이름이 갈리면 화면이 둘로 갈린다.
                    "분할_기준": split_basis(rows),
                    "지도_출처": MAP_SOURCE})
    return out
