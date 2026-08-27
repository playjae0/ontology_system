# -*- coding: utf-8 -*-
"""어댑터 스켈레톤 양식 (킷 구성물 ②) — **빈칸을 채우는 방식**으로 생성한다.

자유 작문보다 검수가 쉽다: 무엇이 어디 있어야 하는지가 이미 정해져 있으므로
검수자는 "형태가 맞나"가 아니라 **"값이 맞나"**만 보면 된다.

계약 (파서_명세 §5): 어댑터는 doc_type당 **1모듈 · 선언 1개 + 함수 1개**다.
  · ADAPTER  — 관찰 상수 선언. 어댑터의 "무엇을 기대하는가"가 전부 여기 있다.
  · extract  — `raw` → 정규 조각 리스트. **순수 함수**다.

──────────────────────────────────────────────────────────────────────────
빈칸 상태로 하네스에 넣으면 무엇이 나오나  [사람용 안내 — 실측 08-19]
──────────────────────────────────────────────────────────────────────────
이 파일을 **그대로** 하네스(`kit/run_adapter.py`)에 넣으면 아래가 나온다. 생성 LLM이
아니라 **사람이 읽는 안내**다 — 스켈레톤이 어디까지 통과하는지 알아야 "아직 안 채운
것"과 "잘못 채운 것"을 구별할 수 있다.

  ① 로드    PASS 6 / **FAIL 2**
              FAIL: `payload_kind가 닫힌 2값` (None — 아직 안 골랐다)
              FAIL: `adapter.doc_type == schema.doc_type` (빈 문자열)
              ※ `필수 키 4종`은 **PASS다** — 키가 있는지만 보고 값은 안 본다.
                 "선언 자리가 다 있는가"와 "값이 채워졌는가"는 다른 검사다.
  ② preflight  **FAIL 1** — `expects.header_row 선언됨` (expects가 비었다)
  ③ extract    PASS 2 — 예외 없이 돌고 `list[dict]`를 낸다. **조각은 0건**이다.
                 (조각 0건 자체는 여기서 FAIL로 찍히지 않는다 — 뒤 검사가 비어 돌 뿐)
  ④ 스키마     **FAIL 1** — `payload_kind가 …선언됨` (fields 판정의 전제가 없다)

즉 **빈칸 상태의 정상 결과는 FAIL 4건**이고, 그 넷이 전부 "아직 안 채웠다"의 신호다.
**FAIL이 4건보다 많거나 종류가 다르면 스켈레톤을 잘못 고친 것**이고, 그것이 이 안내의
쓸모다. 채우기 시작하면 ①②④의 FAIL이 먼저 사라지고 ③의 조각 수가 붙는다.
(대조 스키마는 아무 table 스키마나 쓰면 된다 — 위 수치는 `schemas/cp.json` 기준이다.)
"""
import re  # noqa: F401  — 열 매핑·패턴이 필요하면 쓴다. 안 쓰면 지워도 된다.

# **공용 코어를 부른다 — 직접 구현하지 마라**(문서 6 §6.2).
# 병합 전개·상동 치환·복수값 전개·열문자 변환은 `parser.normalizer`가 소유한다.
# 어댑터가 재구현하면 어댑터마다 같은 일을 하는 다른 코드가 쌓이고, 병합 처리에
# 버그가 나오면 **어댑터 전부를 고쳐야 한다.** 참조 어댑터 3종이 실제로 그 상태였다.
# `parser.normalizer` import는 순수성 위반이 아니다 — 파서 내부의 순수 함수다.
from parser import normalizer

ADAPTER = {
    # ── 신원 ────────────────────────────────────────────────────────────
    "doc_type": "",              # [빈칸] 등록 이름. 기존 doc_type과 중복 불가.
    "adapter_version": "1.0",    # 개정 시 수동 증가 — 봉투에 1회 기록된다(A7-3).

    # ── payload_kind: 닫힌 2값 ──────────────────────────────────────────
    # "table" = 행이 record다.  "prose" = 문단·슬라이드가 chunk다.
    # 이 값이 **매칭 스키마의 fields 정답을 정한다**(D-31):
    #   table → fields 선언 필요 / prose → fields는 빈 목록 `{}`
    "payload_kind": None,        # [빈칸] "table" 또는 "prose"

    # ── expects: 관찰 상수 ──────────────────────────────────────────────
    # **표본을 보고 관찰한 것만** 적는다. 추측해 적으면 preflight가 헛돈다.
    "expects": {
        # ▼ table 계열 ────────────────────────────────────────────────
        # "header_row": 0,            # [빈칸] 헤더가 있는 행 번호(1부터)
        # "data_start_row": 0,        # [빈칸] 데이터 첫 행
        # **header_labels는 table 필수다**(D-29) — preflight의 양식 표류 감지가
        # 이것으로 돈다. `columns`는 출력 필드명 매핑이라 대조에 쓸 수 없다:
        # 프롬프트가 필드명 변환을 지시한 순간 표류 감지가 무력화되기 때문이다.
        # "header_labels": [],        # [빈칸] 원본 헤더 문자열의 **순서 배열**
        # "columns": {},              # [빈칸] {출력 필드명: 열문자}

        # ▼ prose 계열 ────────────────────────────────────────────────
        # 분할 신호 상수를 적는다(헤더 행이 없으므로 preflight가 이것을 본다).
        # "heading_pattern": r"",     # [빈칸] 헤딩 판정 정규식
        # "section_sep": " > ",       # 헤딩 경로 구분자
        # 구조가 판본마다 다른 계열이면 상수 대신 **힌트**만 둔다 — 분할은
        # 코어의 구조 지도 패스가 한다(D-58). 힌트는 강제가 아니라 프라이어다.

        # ▼ 공통 ──────────────────────────────────────────────────────
        # "ditto_mark": "〃",         # 상동 기호(관찰된 것만)
        # "multi_value_seps": [",", "/", "\n"],   # D-12 기본 닫힌 목록
        # "multi_value_fields": [],   # 한 칸에 복수값이 오는 필드
        # "required": [],             # 자기완결 필수 필드 — 결측이면 문서 단위 실패(C14)
    },
}


def extract(raw) -> list[dict]:
    """`raw`(reader 원시 추출물) → 정규 조각 리스트.

    **순수 함수다** — 네트워크·LLM·파일 쓰기 금지(§5 규약 2). 하네스 ①단이 검사한다.

    지켜야 할 것 넷:
      1. 조각마다 `source_locator` — **문서 내 유일**해야 한다. 복수값을 행으로
         전개했다면 `#1`·`#2` 접미로 유일성을 지킨다.
      2. **정본 id를 부여하지 않는다** — `chunk_id`·`record_id`·`doc_hash`는
         에이전트가 계산한다(틀 A7-1). 여기서 만들면 하네스 ③단이 FAIL이다.
      3. **자기완결** — 상동 기호("〃")를 남기지 않는다. 병합 셀은 전개한다.
      4. prose 조각은 `text` 또는 `image_ref` 중 하나를 반드시 갖는다.

    빈 행 판정 주의: **전 열이 빈 행만 빈 행이다.** 일부만 비었으면 그것은 여백이
    아니라 결측이고, 빈 행으로 삼키면 그 행이 조용히 사라진다(C14 위반).
    """
    exp = ADAPTER["expects"]
    fragments = []

    # ── table 계열 뼈대 ─────────────────────────────────────────────
    # **채우는 것은 「이 문서의 열이 어디 있고 무엇인가」뿐이다.**
    # 병합·상동·복수값·열문자는 아래 공용 코어 호출이 이미 처리한다.
    for sheet in (raw.get("sheets") or []):
        cells = normalizer.expand_merged(sheet)       # ② 병합 전개 — 직접 짜지 않는다
        rows = []
        for row in range(exp.get("data_start_row", 1),
                         int(sheet.get("max_row", 0)) + 1):
            rec = {}
            for field, col in (exp.get("columns") or {}).items():   # [빈칸] columns
                v = cells.get(f"{col}{row}", "")
                rec[field] = "" if v is None else str(v).strip()
            if all(v == "" for v in rec.values()):
                continue                  # 전 열이 빈 행만 빈 행이다 (C14)
            rows.append((row, rec))

        recs, _d = normalizer.resolve_ditto(          # ① 상동 — 직접 짜지 않는다
            [r for _n, r in rows],
            marks={exp["ditto_mark"]} if exp.get("ditto_mark") else None)
        for (row, _r0), rec in zip(rows, recs or []):
            miss = [c for c in (exp.get("required") or []) if rec.get(c, "") == ""]
            if miss:
                raise ValueError(f"자기완결 실패 row {row}: 필수 결측 {miss} (C14)")
            # [빈칸] 이 문서만의 후처리 — 예: context를 딕셔너리로 감싼다
            rec["source_locator"] = f"{sheet.get('name', 'sheet')}!R{row}"
            fragments.append(rec)

    # ── prose 계열 뼈대 ─────────────────────────────────────────────
    for _slide in (raw.get("slides") or []):
        # [빈칸] 분할 단위마다 {text, section, meta, source_locator}
        pass

    if exp.get("multi_value_fields"):
        fragments, _m = normalizer.split_multi(       # ③ 복수값 — 직접 짜지 않는다
            fragments, exp["multi_value_fields"], exp.get("multi_value_seps"))
    return fragments
