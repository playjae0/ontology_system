# PROGRESS — B120 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B120의 본문을 여기로 옮겼다(B125 마감 때).

## B120 — 산문의 값: 「항목 = 값」을 주인 아래 노드의 속성으로 · 값을 받는 카테고리 선언 · 추출 판은 config 칸 해시 (2026-10-19 · 동작 변경)

> 요청문 `docs/안건/B120_요청문.md` · hub_99 반입 `729b246` 위 · 가벼운 회차 첫 적용(개발 중 doctor 전체 0 · 고른 실행 3회).

- 전제 3행 — `0` · `122` / `93` · `21` / `True` (기대 그대로)
- 마감 한 줄 2회 — 1회: doctor 1949/1950(새 시험이 등록한 문서 종류를 남겨 `test_p3_register` 등록부 대조 FAIL → 시험 끝에 치움) · 2회: 코드 지도 그대로 · 사전 점검 118/118 · 문서 검사 일곱 위반 0 · **doctor 1950/1950 · 클린 2회 동일 그래프** · §7 상한 위반 0 · 자산 해시 같음 · 네 벌 「다르다」(아래 ⓓ — 기대)
- ⓐ 값 — PASS: `노칭::언와인더 unit::장력` = 30N · `노칭::리와인더 unit::장력` = 20N(각자 출처 청크 · 충돌 0) · 같은 청크의 날짜 · 쪽수는 어디에도 값이 아니다
- ⓑ 버림 · 충돌 — PASS: 원문에 없는 값(85ppm)은 노드 attrs 0 · 행 `value.verdict` 버림 · 결함 로그 · 요약 `값 4 = 실림 3 · 버림 1 · 충돌 0` / 다른 문서의 35N은 `spec_conflict`(있던 30N 그대로)
- ⓒ 선언 · 판 — PASS: `relation_patterns` · `config_version`만 바꾸면 추출 재사용(힌트를 지워도 값 그대로) · 정의문을 바꾸면 다시 뽑는다 · 선언을 지우면 힌트에 값이 있어도 0
- ⓓ 재구축 — PASS: 값 재생 · LLM 호출 추출 0 · 판정 0 / 네 벌 A · B 그래프 · 사전 · 큐 · 대장 전부 같음 · C는 산문 사양 노드 8의 attrs(값)와 대장 FWC1 · FWC3(`value` 키)만 다름 · 엣지 · 사전 · 큐 같음
- 어서션 +4(`test_g6_values` — ⓐ · ⓑ · ⓒⓓ · ⓒ) · 기대 변경 3(`test_g6_belongs` 지시문 판 e-1.8 · 층 config 판 = 정의문이면 다시 · config_version만은 그대로 / `test_g6_numbers` ⓕ 라벨) · 삭제 0
- 가결정 D-202(7건) · 명세 패치 `docs/안건/B120_명세패치.md` 7항목 `--check` 통과(문서 3 §3.1 · 문서 4 §4.6-1 · §4.10-4 · §4.10-13 · 문서 7 §7.8 셋)
- 바뀐 자리 — 새 `core/build/values.py`(산문 값 — 원문 대조 · 표와 같은 `Builder.put_attribute` · 결과를 돌려준다) · `config_scope.extract_key`(추출 · 개요 · 구조 판 한 함수) · 추출 계약 `value` · 지시문 3.3 e-1.8 · 선언 검사 ⓖ(`catalog.problems`) · 맞춤표 `값(산문)` · 한 줄 요약 값 칸 · mock 공정층 `value_categories` · 가이드(config작성 §1-b 넷 줄 · 20종 · 런북 값 · 충돌 큐) · 구조도
- 사내 config 줄(공정층 · mock 이름) — `"value_categories": {"Property": "spec"}`(속성 이름은 사내 CP 스키마 규격 열의 `attr_name`과 같게) · `relation_patterns`에 `{"src": "Unit", "rel": "has_property", "dst": "Property"}` 확인(없으면 한 줄) · B119의 Unit 정의문 · 공통 `nest_categories: ["Property"]` · `config_version`은 올리지 않는다(자동) → `python run.py bootstrap` → `python run.py rebuild`(지시문 판이 올라 산문은 한 번 다시 뽑는다 — LLM · 표는 0)
- 소요 약 40분 — 읽기 4분(00:26~00:30) · 구현 6분(③ → ② → ①) · 시험 작성 5분(고른 실행 3회 포함) · 문서 · 장부 6분 · 마감 한 줄 2회(7분 27초 · 7분 23초 — 사이 고침 1분) · 보고 2분
