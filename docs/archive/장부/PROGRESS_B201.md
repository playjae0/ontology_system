# PROGRESS — B201 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B201의 본문을 여기로 옮겼다(B204 마감 때).

## B201 — 산문 값 칸은 카테고리 home의 선언을 따른다(읽는 층과 무관) (2026-11-12 · 칸 3.3 · 0.1 · 문서)

> 요청문 `docs/안건/B201_요청문.md`(hub_191 반입 `869afde` · B200 머지 `64e28a2` 위) · 단독 · 작음.

- 전제 8행 — 같다(1행 맨 위 hub_191 반입 · 그 아래 B200 머지 · 8행 `attributes`는 81행)
- 마감 한 줄 1회 — FAIL 0 · doctor 2248(기대 2245 +3) · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 상한 0
- ⓐ PASS 품질층(uses Property · 선언 없음)으로 같은 창작 표본을 읽은 산문의 Property 값(30N · 20N · 100ppm)이 노드 `설비사양` 칸(home의 칸 이름)에 · 렌즈 없음 · 값 카테고리 목록 ['Property']
- ⓑ PASS Property를 uses에 두지 않은 층 — 목록 [] · Process · Unit 칸 이름 없음
- ⓒ PASS home 선언의 칸 이름을 바꾸면 빌린 층 `extract_key`가 바뀐다 · 되돌리면 그대로 · uses 없는 층 판 바이트 같다
- ⓓ PASS 지시문 바이트 같음(마감 「바뀐 지시문 — 없음」 · 자산 해시 같음) · 층 config 키 일람 같음(`config_scope` 표 그대로) · 새 키 · 새 단계 · 새 화면 0
- ⓔ PASS 네 벌 전부 같다 — 차이 목록 0(mock 바닥에 빌린 층으로 읽는 산문의 Property 값이 없다 · 표의 값 · 노드 · 엣지 같음)
- ⓕ PASS 명세 패치 `--apply`(+106자 · 문서 3 · 4 — 3항목 · 문서 1 항목 0) · 마감 FAIL 0
- 가결정(D-282) — 자리 하나 `catalog.value_attr` · `values.attr_name`(칸 이름) · `values.categories`(추출 입력) · `uses_view` 「값 칸」(선언 없으면 칸 없음 — 판 바이트 그대로) · 읽는 층이 말하지 않는 카테고리는 home 선언이 있어도 값 아님
- 어서션 +3 · 삭제 0 · 고침 0 — B201 ⓐⓑⓒ(test_build — 산문 값 조각)
- 바꾼 파일 — `core/state/{catalog,config_scope}.py` · `core/build/{values,extract}.py` · `tests/part_g6_values.py` · 명세 · DECISIONS
- 가이드(③ — 허브 몫): 층config 팩 §4 `value_categories` 줄 · 바탕층 메모 「렌즈에 공정층」 · 런북 2의 렌즈 줄은 손대지 않았다
- 사내 config 줄 — 공정층 config에 `"value_categories": {"<관리항목 카테고리>": "설비사양"}`(없으면 한 줄) → `bootstrap`(빌린 층의 「추출 다시」 알림) → 설비층 산문도 렌즈 없이 값이 실린다
- 소요 약 1시간(어림) — 반입 · 런북 합치기 15분 · 전제 · 읽기 10분 · 구현 15분 · 시험 15분 · 명세 · 장부 5분 · 마감 한 줄 1회 4분
