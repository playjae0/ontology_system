# 참조 어댑터 예시 — few-shot 3종 (킷 구성물 ④)

생성 프롬프트에 **few-shot 재료**로 동봉한다. 어댑터 하나당 **어댑터 코드 + 매칭 스키마**가
한 쌍이다 — 둘이 어떻게 맞물리는지가 이 예시의 핵심이고, 코드만 보여 주면 LLM이
스키마를 따로 지어낸다.

## 3종과 선택 근거

| # | doc_type | payload_kind | 출처 | 왜 이것인가 |
|---|---|---|---|---|
| 1 | `ipqc` | **table** | **fixture** — 외부 세션의 LLM 실산출(3차 블라인드) | **"이렇게 내면 통과한다"의 실증**이다. 공식 하네스 전항 PASS 로그가 봉인돼 있다(`mock/fixtures/log/harness_ipqc_공식.txt`). 16열로 table의 어려운 지점을 한 번에 보여 준다 — 복수값 전개·상동 해소·`context` 기본값 파싱·**UNMAPPABLE 2열 제외**(D-30) |
| 2 | `toc_report` | **prose** | **fixture** — 상동 | **prose 필수 1종.** 헤더 행이 없는 계열이 무엇을 `expects`에 싣는지(분할 신호 상수)와, 헤딩 경로를 `section`으로 쌓는 법·이미지 placeholder 조각을 보여 준다. **`fields`가 빈 목록 `{}`인 스키마**의 실례이기도 하다(D-31) |
| 3 | `cp` | **table** | **참조** — 사람 작성(D-76) | **가장 단순한 table의 정석.** 앞의 둘이 복잡한 경우를 덮으므로 셋째는 "군더더기 없는 기본형"이 낫다. 10열·복수값 2필드·`ditto_mark`. 그리고 **`context`를 임의 딕셔너리로 내는 실례**(`context_key`)라 템플릿 v0.4의 처방 ⓐ와 짝이 맞는다 |

**조건 충족**: table 2 · prose 1 — 요청된 "table 1·prose 1 포함"을 만족한다.

**떨어진 후보**: `pfmea`(table, 참조). 셋째 자리를 `cp`와 다투었고, 같은 table 정석이면서
열이 더 많아(13열) "단순한 기본형" 역할에는 `cp`가 낫다고 봤다. 숫자형 보존(`int_fields`)이
필요해지면 그때 넣는다 — few-shot은 많을수록 좋은 것이 아니라 **각각이 다른 것을 보여줘야**
한다.

## 원본과의 관계 — 복사본이다 (D-26)

`ipqc.py` · `toc_report.py`는 **`mock/fixtures/`의 봉인 산출물을 바이트 그대로 복사**한 것이다.
`cp.py`는 `mock/adapters/`의 참조 어댑터 복사본이다.

- **원본은 손대지 않는다.** fixture는 "미리 만든 정답"이 아니라 **외부 세션에서 실제 LLM이
  산출한 결과물의 스냅샷**이고, 손대는 순간 그 리허설이 아무것도 검증하지 않게 된다.
- 원본이 개정되면 **여기를 다시 복사**한다. 여기서 고쳐 원본과 갈라지면 few-shot이
  실물과 다른 것을 가르치게 된다.
- 대조: `cmp mock/fixtures/adapters/ipqc.py kit/참조어댑터/ipqc.py` → 차이 0.

## 읽는 순서 (프롬프트에 넣을 때)

1. `cp.py` + `cp.json` — 기본형. 어댑터와 스키마의 대응을 먼저 잡는다.
2. `ipqc.py` + `ipqc.json` — 어려운 table. 복수값·상동·UNMAPPABLE.
3. `toc_report.py` + `toc_report.json` — prose. `fields {}` 와 분할 신호.

**원천**: 파서_명세 §9 킷 ④ · D-26(fixture 정의) · D-76(참조 어댑터 소재지)
