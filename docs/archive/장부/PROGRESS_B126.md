# PROGRESS — B126 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B126의 본문을 여기로 옮겼다(B129 마감 때).

## B126 — 구조는 규칙 나무가 기준 · LLM은 고칠 곳만 이유와 함께 · 시트마다 구조 확인(힌트로 다시) · 구조까지만 (2026-10-19 · 동작 변경 — 산문 구조 기본 방식 · 화면 · 지시문 o-3.2)

> 요청문 `docs/안건/B126_요청문.md` · hub_101 반입 `f5bf643` 위 · 가벼운 회차(개발 중 doctor 전체 0 · 고른 실행만).

- 전제 4행 — `0` · `2` · `0` · `96` (기대 그대로)
- 마감 한 줄 2회 — 1회: doctor 1969/1970(`test_p3_register` — 새 시험이 등록한 `b126_process`를 치우지 않아 등록부 대조가 붉었다 · 시험 끝 정리 추가) · 2회: 전부 PASS(doctor 1970/1970 · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 위반 0 · 자산 해시 같다 · 소요 556초)
- ⓐ 바닥 — PASS: `rules` = 구조 함수 없는 파싱(B118 청크 바이트 동일) · 고침 없는 `edit` = `rules` · rules도 구조 셈에 규칙 나무
- ⓑ 고침 — PASS(가짜 게이트웨이): 대상 · 제목 더함 · 부모 바꿈 → 「속도」 사슬에 유닛 공급부 · 「메모」는 시트 바로 아래 · 이유가 md에 · 시트에 없는 줄 고침만 버림(3 선다 · 1 버림)
- ⓒ 확인 고리 — PASS: 힌트 → 둘째 호출 입력에 `previous` + `hints` · 다시 전부 찍음 · `c` → `registry/structure_confirmed.json`(힌트 포함) · 보존분 없이 다시 파싱해도 구조 LLM 0 · 같은 나무
- ⓓ 형태 단서 — PASS: LLM 입력에 「'1.' 8행 — '가.'(7행) 아래에서 다시 시작」 · 공통사양 「'1)' 2~12행 11개 이어짐」
- ⓔ 방식 — PASS: 규칙 나무가 빈 시트(메모)만 llm · 나머지 edit · `structure_mode=llm`이면 전부 llm(edit 입력 0)
- ⓕ `--split-only` — PASS: 데이터 해시 그대로(그래프 쓰기 0) · 추출 0 · `export/split_<doc_id>.md`에 고침 이유 · 행 상태 「구조까지」
- ⓖ 네 벌 — 전부 같다(A · B · C — mock 옛 꼴 힌트는 llm 답으로 읽어 C 그대로)
- 어서션 +6(`test_g6_split`) · 기대 변경 1(`test_g6_structure` — llm 방식을 잰다고 고정) · 삭제 0
- 가결정 D-206(10건 — 고침 목록 꼴 · 형태 단서 꼴 · 확정 기록 자리 · 단계 이름 「구조 확인」 · rules의 셈 · 붙임의 자르기 · 한 호출 · mock 꼴 · 옛 줄 고침 · 다시 묻기의 자리) · 명세 패치 `docs/안건/B126_명세패치.md` 12항목 `--check` 통과(문서 6 §6.3 · §6.4-5 넷 · 문서 1 M23 · 문서 7 §7.5 · §7.6-B-2 · §7.8 셋 · 부록 용어 다섯 — 문서 7 34행은 B125 패치와 같은 줄)
- 바뀐 자리 — `core/build/structure_edit.py`(새 — 형태 단서 · 고침 검사) · `structure.structurer`(방식 셋 · 확정 기록 · `reask`) · `struct_rule.structure_hook`(확정 재생 · rules 셈) · `frame_chunks`(붙임) · `struct_map.cap_chars`(붙임 상한 · 형제 나눔) · `cli/structure_screen.gate`(시트마다 확인 고리) · `cli/split_report.py`(새 — 화면 · md 한 함수) · `cli/ingest --split-only` · 지시문 o-3.2 · 손잡이 `structure_mode`
- 사내 config 줄 — 없음(기본 `edit` · 비교할 때만 `knobs.json` `"structure_mode": "rules"` 또는 `"llm"` → 같은 문서를 `ingest-file … --step --split-only`로 돌려 `export/split_<doc_id>.md` 비교)
- 소요 약 52분 — 반입 1분 · 읽기 3분 · 구현 12분(① → ② → ③ → ④ · 옛 시험 고침 포함) · 시험 작성 6분 · 문서 · 명세 패치 · 장부 7분 · 마감 한 줄 2회 각 9분(사이 고침 1분) · 장부 마감 3분
