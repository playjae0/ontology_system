# PROGRESS — B96 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B96의 본문을 여기로 옮겼다(B99 마감 때).

## B96 — dry-run은 실제 실행과 같은 검사 · show tree는 흐름 순서 · LLM 사용량 줄 전수 · 영문 대소문자 무시 2차 대조 · 언어 병기 가이드 (2026-10-01)

순서 ① → ② → ③ → ④ → ⑤. 가결정 D-177(5건). B95 마감 `df452e6` 위. 수치의 출처는 **창작 표본**(mock 덧칠 · 시험 전용 사전) — 메커니즘 확인이다([정정] 50).

### 전제 대조표 7행 (B95 마감 `df452e6` 기준)

1~7행 기대값과 일치(166·177 · 176·118 · 102·109 · 0·0·3 · 87·234·51 · 58 · 4).

### ① dry-run = 같은 검사 · 쓰기만 0

- `_catalog_gate(dry_run)`: 맞춘 뒤 계획의 카탈로그로 `catalog.problems(cat=)` + 층마다 `cli/skeleton.check`(`skeleton-status`와 같은 함수·문면) · 끝 줄 `[bootstrap] --dry-run — 쓰기 0 · 바뀔 것 있음|없음 · 멈출 것 n건` · n>0이면 rc 1.
- 화면(창작): 층 config에 `canonical_scope`가 남으면 dry-run도 `[bootstrap] [상태] 공통 config ⓓ 층 process의 config에 canonical_scope가 남아 있다 …`(실제 실행과 같은 줄) · 골격 `"@노칭오타"`면 `[FAIL] K05 마커 어휘 밖` · 통과 상태는 `… 멈출 것 0건` → 실제 rc 0.

### ② show tree 흐름 순서

- 형제·뿌리 = precedes 사슬(머리는 선언 순서) · 흐름 밖은 뒤에 이름순 · 머리 줄 「순서 = 흐름(precedes) · 흐름 밖은 뒤에 이름순」.

### ③ LLM 사용량 줄

- `cli/_screen.usage_line(since)` 하나 — `register generate`·`review` · 시트 역할 관문(`auto`·`gate` 모든 출구) · `query`(`--json`이면 stderr) · `llm-check` · `parse` · `extract`. 인입(파일·폴더)은 기존 요약 줄.

### ④ 영문 대소문자 2차 대조

- `ids.fold_latin`(라틴만 · `norm` 뒤) · 정확 미스일 때만 · 대상이 하나일 때만(둘 이상이면 미스 + 로그). 자리: 사전 `lookup` · 적중 `form._hits`·`lens.score` · `extract.attach_candidates`·`parent_candidates` · `prose._entity_parent` · `tagger` · `query` 링크·`ref_near`. 접지 않는 자리: `norm`·문서 id · `ops` 이름 지정 · 등재 비교 · matcher 규칙 · 스캔 지문.

### ⑤ 가이드 · 구조도

- 골격작성 §1(언어 병기 · 별칭 체크리스트) · §3-a 3 · 함정 표 · config작성 §6-a · 2B(dry-run 끝 줄 · 사용량 줄 행 · `show tree` 순서) · 구조도 `00`·`02`·`03`·`06` · `10`(생성).

### 실행으로 확인한 것

- **클린 회귀 2회 동일**: **1665/1665 PASS** ×2(B95 1658 + 7 · 차이는 소요 초뿐). **네 벌 diff 0**(④로 새로 맞은 mock 표기 없음 — 창작 표본은 대소문자 변형을 담지 않는다).
- 검사 6종: 0 · 0 · 0 · 0 · 12 · 0. §7 상한 위반 0(`cmd_review` 121행 → import를 머리로 옮겨 해소). 자산 해시 재기록.
- 어서션 **+7 · 삭제 0**(새 묶음 `test_g6_dryrun_fold`): ⓐ 거부 남은 상태 dry-run rc 1·같은 문면 / ⓑ 골격 문법 위반 dry-run rc 1·태그 / ⓒ dry-run 통과 → 실제 rc 0 / ⓓ 형제 순서 = precedes / ⓔ 관문·뷰 확인 끝 사용량 줄 / ⓕ 대소문자 2차 대조(하나일 때만) / ⓖ `norm`·문서 id 불변.
- `git diff core/`(df452e6 대비): 8 files changed, 105 insertions(+), 13 deletions(-) — `dictionary` · `state/ids` · `state/catalog` · `state/catalog_sync` · `build/{extract,lens,prose}` · `query/query`.

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 3 §3.1: 「`--dry-run`은 계획만」 → 「실제 실행과 같은 검사(카탈로그 거부 · 골격 문법) · 쓰기만 0 · 멈출 것 n건이면 rc 1」.
- 문서 4 §4.2 ① 사전 조회: 「정확 미스면 영문 대소문자 무시 2차 대조 — 대상이 하나일 때만 채택」.
