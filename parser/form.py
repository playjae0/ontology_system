# -*- coding: utf-8 -*-
"""칸 2.3 — 형태 판정 — 이 문서를 **table로 읽을 것인가 prose로 읽을 것인가** (문서 1 C37 · 문서 6 §6.4).

**doc_type 식별과 다른 판정이다**: 지문 스캔(C15)이 「어느 어댑터인가」를 정한다면
여기는 「어느 갈래로 읽는가」다. 대상은 **xlsx·csv**뿐 — `.pptx`·`.pdf`는 포맷이
이미 prose를 함의한다(경계는 `reader.GRID_EXT`가 갖는다).

**이 자리에 LLM을 두지 않는다** — 근거는 멱등성이다(문서 4 §4.8-6). 라우터가
비결정적이면 같은 파일이 회차마다 다른 갈래로 가 청크가 통째로 달라지고,
**멱등성이 깨지는 것이 아니라 잴 수 없게 된다**(문서 7 완료판정 4가 상시 실패).
비결정성은 어디에 있어도 나쁘지만 **입구에 있으면 뒤의 모든 단계가 그 위에 선다.**

    신호 다섯 · 각 3값(table / prose / 기권) · **찬성 ≥2 · 반대 0이면 자동, 그 외는 사람.**

**AND가 아니고 가중치도 없다.** 신호가 서로 중복이라 AND는 하나가 흔들릴 때
나머지를 거부권으로 뒤집어 견고함이 도리어 준다. 반대표 0은 남긴다 — 열이 열둘인데
indent가 85%인 시트는 실제로 이상하고 사람이 봐야 한다. 가중치를 두지 않는 것은
**문턱 둘씩이 전부라야 화면이 판정 근거를 그대로 보이기** 때문이다.

**중간 구간은 기권한다** — 없으면 열 서넛짜리 산문에서 열 신호가 판정을 뒤집는다.

**기록이 이 기능의 절반이다.** 판정마다 신호값 다섯·자동 판정·사람이 고른 값을
인입 기록에 남긴다(`cli/ingest.py`의 `routing`). 문턱 조정과 **애매 구간의 실제
크기**를 재는 유일한 재료이고, 그것이 재어진 뒤에야 LLM 보조를 검토한다 — 그때도
자리는 라우터가 아니라 사람에게 올리는 화면의 보조 제안이다.
"""
from __future__ import annotations

import re

TABLE, PROSE, ABSTAIN = "table", "prose", "abstain"

# **문턱은 코어 상수 한 자리다** — 층 config 키가 아니다(문서 3 §3.1 키 일람 19종 밖).
# 흩어지면 조정이 코드 수색이 되고, 층에 두면 같은 판정기가 층마다 다르게 돈다.
#
# 값의 뜻: `(prose_쪽, table_쪽)`. 신호값이 prose 쪽을 **넘거나 같으면** prose,
# table 쪽을 **밑돌거나 같으면** table, 사이면 기권이다. 방향은 신호마다 다르므로
# 두 수의 대소가 그것을 말한다 — 열 개수는 `(2, 5)`로 작을수록 prose이고,
# indent 비율은 `(0.30, 0.05)`로 클수록 prose다.
#
# **초기값이다**(창작 픽스처 9건에서 뽑았다 — table 7·prose 2가 전 신호에서 겹침
# 없이 갈렸다). 조정의 재료는 위 「기록」이다 — 감이 아니다(P7).
THRESHOLDS = {
    "column_count": (2, 5),             # 열 개수                    ≤2 prose · ≥5 table
    "min_unique_ratio": (0.90, 0.50),   # 최소 고유값 비율          ≥0.9 prose · ≤0.5 table
    "max_text_share": (0.80, 0.40),     # 최대 열의 텍스트 점유율   ≥0.8 prose · ≤0.4 table
    "indent_share": (0.30, 0.05),       # indent 있는 셀 비율       ≥0.3 prose · ≤0.05 table
    "numbered_rows": (5, 1),            # 번호 패턴 행 수           ≥5  prose · ≤1  table
}
SIGNALS = tuple(THRESHOLDS)             # 화면·기록의 순서 — 표와 같다

# 고유값 비율을 재는 열의 최소 값 개수. 값이 두셋뿐인 열은 비율이 튄다.
MIN_VALUES_FOR_UNIQUE = 4
_NUM = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+\S")
_CELL = re.compile(r"^([A-Z]+)(\d+)$")

AUTO_MIN_FOR = 2                        # 찬성 최소 — 「≥2」
AUTO_MAX_AGAINST = 0                    # 반대 최대 — 「반대 0」


def _vote(name, value):
    """신호값 하나 → 3값. **문턱 둘의 대소가 방향을 말한다**(머리말 참조)."""
    if value is None:
        return ABSTAIN
    lo, hi = THRESHOLDS[name]
    if lo <= hi:                                  # 작을수록 prose (열 개수)
        return PROSE if value <= lo else (TABLE if value >= hi else ABSTAIN)
    return PROSE if value >= lo else (TABLE if value <= hi else ABSTAIN)


def signals(raw):
    """신호 다섯의 **값** — 판정 이전이다. 화면과 기록이 이 값을 그대로 싣는다.

    문서 전체(전 시트)를 한 벌로 본다 — 시트마다 갈리면 「이 문서를 어느 갈래로
    읽는가」가 답이 둘이 되고, 어댑터는 문서 하나에 하나다.
    """
    cols, rows_seen = {}, set()
    indented = total_cells = numbered = 0
    for sh in raw.get("sheets") or []:
        cells = sh.get("cells") or {}
        ind = sh.get("indent") or {}
        by_row = {}
        for a, v in cells.items():
            m = _CELL.match(a)
            if not m:
                continue
            col, row = m.group(1), int(m.group(2))
            text = "" if v is None else str(v).strip()
            if not text:
                continue
            total_cells += 1
            cols.setdefault(col, []).append(text)
            rows_seen.add((sh.get("name"), row))
            by_row.setdefault(row, []).append((col, text))
            if int(ind.get(a, 0) or 0) > 0:
                indented += 1
        for _row, items in by_row.items():
            # 번호 패턴은 **행의 첫 열**에서 센다 — 표의 비고란에 든 「1) …」이
            # 헤딩으로 세어지면 관리계획서가 산문으로 넘어간다.
            first = min(items)[1]
            if _NUM.match(first):
                numbered += 1
    if not total_cells:
        return {k: None for k in SIGNALS}
    lens = {c: sum(len(t) for t in v) for c, v in cols.items()}
    chars = sum(lens.values())
    uniq = [len(set(v)) / len(v) for v in cols.values()
            if len(v) >= MIN_VALUES_FOR_UNIQUE]
    return {
        "column_count": len(cols),
        "min_unique_ratio": round(min(uniq), 3) if uniq else None,
        "max_text_share": round(max(lens.values()) / chars, 3) if chars else None,
        "indent_share": round(indented / total_cells, 3),
        "numbered_rows": numbered,
    }


def judge(raw):
    """`{signals, votes, for, against, abstain, verdict, auto, why}`.

    `verdict`는 `table`·`prose`·`None`이고 **`None`이면 사람에게 올린다.**
    `auto`가 그 사실의 이름이다 — 화면과 기록이 둘을 함께 싣는다.
    """
    sig = signals(raw)
    votes = {k: _vote(k, sig[k]) for k in SIGNALS}
    tally = {v: [k for k, x in votes.items() if x == v]
             for v in (TABLE, PROSE, ABSTAIN)}
    out = {"signals": sig, "votes": votes,
           "table": tally[TABLE], "prose": tally[PROSE], "abstain": tally[ABSTAIN]}
    for side, other in ((TABLE, PROSE), (PROSE, TABLE)):
        if len(tally[side]) >= AUTO_MIN_FOR and len(tally[other]) <= AUTO_MAX_AGAINST:
            return {**out, "verdict": side, "auto": True,
                    "why": (f"{side} 찬성 {len(tally[side])}({', '.join(tally[side])}) · "
                            f"반대 0 · 기권 {len(tally[ABSTAIN])}")}
    return {**out, "verdict": None, "auto": False,
            "why": (f"자동 조건(찬성 ≥{AUTO_MIN_FOR} · 반대 {AUTO_MAX_AGAINST}) 미충족 — "
                    f"table {len(tally[TABLE])} · prose {len(tally[PROSE])} · "
                    f"기권 {len(tally[ABSTAIN])}. **사람이 정한다**")}


# ================================================================ 시트 역할 (B83 ②)
# **다른 판정이다** — 위가 「이 문서를 table로 읽을까 prose로 읽을까」라면 여기는
# 「이 **시트**를 지식으로 읽을까, 참조로 둘까, 읽지 말까」다. 문서마다 시트 이름과
# 자리가 달라 어댑터(doc_type)에 적을 수 없고, 결정 단위가 **문서 하나**다.
#
# **제안은 규칙이다 — LLM 지점을 늘리지 않는다**(B83 ②): 사람이 어차피 고치는 제안에
# 지점 하나(지시문·mock·실호출·도달성 어서션)를 열 이유가 없다. 규칙이 못 미치면
# 사람이 고치고, 그 답이 기록이 된다.
SHEET_ROLES = ("prose", "ref", "skip")

#: 문턱 — **표본 관찰로 정했다**(B83 · 보고에 근거를 적는다).
#: 산문 시트는 「문장이 여러 줄」이고 참조 시트는 「짧은 항목이 줄줄이」다.
#: 실측(tests/fixtures/raw/RFQ01.xlsx · TOC01 · CP01):
#:   사양_기계 23행·글자비 1.00·평균 21.3 / 사양_전장 9·1.00·22.3 / 요구사항 8·1.00·20.6
#:   도면목록 30·1.00·**7.0** / 가격 13·**0.31**·2.9 / 일정 6·0.62·2.0 / 표지 4·1.00·11.2
#:   (대조군) TOC01 보고서 33·1.00·21.2 = 산문 · CP01 관리계획서 33·1.00·**6.4** = 표
#: 산문 최소 20.6 vs 참조 최대 11.2 사이에서 **15**를, 행은 표지(4) 위 **8**을 잡았다.
#: 세 문턱을 **AND로** 본다 — 도면목록은 글자비 1.00·행 30이지만 평균 7.0에서 갈린다.
SHEET_THRESHOLDS = {"text_ratio": 0.8, "rows": 8, "avg_len": 15}


def sheet_stats(sheet):
    """시트 하나의 **이미 읽은 사실**만 — 새 판독 0 (reader가 낸 것에서 센다)."""
    cells = (sheet or {}).get("cells") or {}
    vals = [v for v in cells.values() if v is not None and str(v).strip() != ""]
    txt = [v for v in vals if not isinstance(v, (int, float))]
    head = [str(v).strip() for v in list(cells.values())[:3]
            if v is not None and str(v).strip()]
    return {"name": sheet.get("name"), "rows": sheet.get("max_row") or 0,
            "cols": sheet.get("max_col") or 0, "values": len(vals),
            "text_ratio": round(len(txt) / len(vals), 2) if vals else 0.0,
            "avg_len": round(sum(len(str(v)) for v in txt) / len(txt), 1) if txt else 0.0,
            "head": " / ".join(h[:28] for h in head)}


def suggest_role(stat, thresholds=None):
    """제안 하나 — `prose` · `ref` · `skip`. **제안은 제안이다**(기록은 사람의 답)."""
    th = thresholds or SHEET_THRESHOLDS
    if not stat.get("values"):
        return "skip"                      # 빈 시트는 읽을 것이 없다
    if (stat["text_ratio"] >= th["text_ratio"] and stat["rows"] >= th["rows"]
            and stat["avg_len"] >= th["avg_len"]):
        return "prose"
    return "ref"


def sheet_table(raw, thresholds=None):
    """통합문서의 **시트 전부**를 표로 — 번호·이름·크기·글자비·앞부분·제안."""
    rows = []
    for i, sh in enumerate((raw or {}).get("sheets") or [], start=1):
        st = sheet_stats(sh)
        st["no"] = i
        st["suggest"] = suggest_role(st, thresholds)
        rows.append(st)
    return rows


def parse_sheet_spec(spec, names):
    """`2-3:prose 4:ref *:skip` → `({시트: 역할}, 오류 문면 또는 None)`.

    문법의 자리는 여기 하나다 — 관문의 한 줄 입력과 `--sheets` 플래그가 **같은 문법**을
    쓴다(③). 선택은 표의 번호(`2` · `2-3` · `2,3,7`) 또는 시트 이름이고 `*`는 「나머지」다.
    **조용히 떨어지지 않는다**: 모르는 번호·이름·역할은 오류 문면으로 돌려주고 호출부가
    `[사용법]`으로 낸다.
    """
    names = list(names)
    roles, rest = {}, None
    for tok in (spec or "").split():
        if ":" not in tok:
            return None, f"토큰 {tok!r}에 ':'이 없다 — 문법은 <선택>:<역할>이다"
        sel, role = tok.rsplit(":", 1)
        if role not in SHEET_ROLES:
            return None, f"역할 {role!r}는 닫힌 셋 밖이다 — {'|'.join(SHEET_ROLES)}"
        if sel == "*":
            rest = role                       # 「나머지」는 토큰 전부를 본 뒤에 적용한다
            continue
        for part in [x.strip() for x in sel.split(",") if x.strip()]:
            m = re.fullmatch(r"(\d+)-(\d+)", part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if not (1 <= a <= b <= len(names)):
                    return None, f"범위 {part!r}가 시트 번호 1~{len(names)} 밖이다"
                picked = names[a - 1:b]
            elif part.isdigit():
                i = int(part)
                if not 1 <= i <= len(names):
                    return None, f"번호 {part!r}가 시트 번호 1~{len(names)} 밖이다"
                picked = [names[i - 1]]
            elif part in names:
                picked = [part]
            else:
                return None, (f"{part!r}는 이 문서의 시트 번호도 이름도 아니다 — "
                              f"시트: {' · '.join(names)}")
            for n in picked:
                roles[n] = role
    if rest:
        for n in names:
            roles.setdefault(n, rest)
    return roles, None
