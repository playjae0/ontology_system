# PROGRESS — B85 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B85의 본문을 여기로 옮겼다(B88 마감 때).

## B85 — 좌표 층의 이름 해방: 골격 층은 `Process`를 선언한 층이지 폴더 `process`가 아니다 (2026-09-22)

사내가 골격 층을 **설비층**(`equipment`)으로 세우자 문서의 좌표가 **전부 목록 밖**이
됐다 — 명세는 좌표 층을 「카테고리를 선언한 층」으로 정했는데 코드가 폴더 이름을
일곱 자리에 박고 있었다. 판정·저장 형식 변경 0.

### ① 묻는 자리 하나 — `coord_layer()`

- `core/state/bootstrap.coord_layer()` = `layer_of_category(COORD_CATEGORY)` ·
  없으면 `NoCoordLayer`로 **시끄럽게 실패**(문면에 다음 줄). 캐시 키는
  **(상태 루트, 층 목록)**이라 스스로 낡는다.
- `COORD_CATEGORY`의 자리를 `core/build/loop.py` → `bootstrap.py`로 옮겼다(D-166 ①) —
  `blocks.json`에서 좌표 카테고리를 꺼내는 자리는 **하나**다(회귀가 잰다).
- **골격 파일 부재는 문면 있는 거부**: `load_seed`가 `SeedError(seed_missing_note(…))`를
  던지고 `bootstrap`·`skeleton-status`(K01)·`skeleton-confirm` 셋이 같은 말을 한다 —
  경로 · config 키 · 끄는 법 · 「이 층은 좌표 층이라 골격을 끌 수 없다」. Traceback 0.

### ② 이름을 박은 자리를 푼다

`parser/tagger.closed_list`·`coord_from_section`·`tag` · `parser/pipeline.parse`는
**기본값 없음**(문면 있는 실패 — D-166 ③) · 호출자(`cli/parse` 둘 · `register/view` ·
킷 `--coord-layer`)가 `coord_layer()`를 넘긴다. `doctor`(골격 절 + 첫 줄
`좌표 층 <이름>`) · `cli/platform`(계기판) · `bootstrap(layer)` · `cli/extract`·`show`·
`export`의 기본값 · `cli/ingest`의 판정 예고 · `core/build/extract.attach_candidates`.
**운영 코드의 `"process"`는 `generate.py:28`(낱말 후보) 하나만 남았다** — 회귀가 센다.

### ③ 이름이 다른 좌표 층에서 전 구간이 돈다

레포를 임시 자리에 복사해 `layers/process` → `layers/equipment`(config·doc_type 스키마의
층 키까지) → 클린 → 골격 → 인입 셋(공정층 표 · 품질층 표 · CSV) → 질의 →
`doctor --quick`. **canonical 142 · 엣지 225(걸침 19) · 큐 5종이 `process`일 때와 같다.**

### 실행으로 확인한 것

- 회귀 **1,503 → 1,517/1,517** · FAIL 0 · 클린 2회 동일 · doctor EXIT=0.
  순증 14(신설 `test_g6_coord_layer`) · 삭제 0.
- 동작 등가 **네 벌 diff 0**(vs `046c05d` · 이름 `process` 루트 — 사전 306 · 대장 399 ·
  엣지 133/92 · 노드 95/47 · 큐 107).
- 화면 diff는 **doctor 첫 줄 한 조각**뿐(`· 좌표 층 process`).
- 검사 5종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13 · 자산 해시 갱신(킷 2파일) ·
  코드 지도 재생성 diff 0 · §7 상한 위반 0.
- `git diff core/`: `bootstrap.py`(+coord_layer·상수 이사·골격 문면) ·
  `build/{loop,table,prose,entry}.py`(import 자리) · `build/extract.py`(좌표 층).
- **같은 병의 나머지 둘을 고쳤다**(D-166 ④): 리허설과 추출 프롬프트가 좌표 스냅샷을
  **문서의 층**으로 읽고 있었다 — 품질층 doc_type에서 후보가 비던 자리다.
- 소요: 반나절 1회차.

### 허브 마감 판정 · 문서 몫 · 회차 재정렬 (hub_51 · 2026-09-23)

- **B85 닫음**(hub_47 판 그대로). D-166 ①~⑨ 확정 — 개정대장 §BT. 문서 7 §7.1(좌표 층 규칙) · 문서 6(파서 진입점 `layer` 필수) · CLAUDE.md §5 · 06 0.1 · 골격작성 §1 · 걸어가기 §0·§1-a(이름 바꾸기 절차 — 등록 스키마 층 키 포함 · D-166 ⑨) · 상태_폴더 · B85 요청문 사내 절차.
- **회차 꼬임 정리**: hub_49·50의 넓힌 B85는 무효(③④는 B85가 했다). 남은 것 → **B86 「사내 모양」 잔여**(`paths.show` · 킷 `--closed-list` · `data/ingest_log` · 선택 의존 문면 · 등록 표본 시트 관문 · 레포 밖 상태 루트 회귀) → **B87 산문 엑셀 계층**(고정 규칙 확장 · 규칙 선언 LLM · 행 우선 청크) → **B88 큐 처리 화면 + 별칭 검색**. B86·B87은 등록·인입 구조가 바뀌어 **가이드·구조도를 구현 세션이 같은 커밋에서** 고친다(사용자 확정 2026-09-23).
