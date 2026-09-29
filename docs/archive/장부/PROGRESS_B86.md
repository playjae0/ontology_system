# PROGRESS — B86 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B86의 본문을 여기로 옮겼다(B89 마감 때).

## B86 — 「사내 모양」 잔여: 상태가 코드 밖이어도 등록부터 뷰어까지 돈다 (2026-09-23)

출처는 사내 실측 셋 — ⓐ상태 루트를 가이드대로 코드 밖에 두자 산문 `register generate`가
`… is not in the subpath of …`로 죽었다 ⓑ새 코드 폴더(새 파이썬 환경)에서 `openpyxl` 부재가
원인 문면 없이 죽고 WMF 그림 경고가 날것으로 흘렀다 ⓒ시트 수십 장 산문 엑셀을 등록하면
검수·킷 관문이 시트 전부를 돌았다(B83 누락). 판정·저장 형식 변경 0 · 가결정 D-167.

### ① 화면 경로는 한 함수 — `paths.show`

- `core/paths.show(p)`: 상태 안 → 상태 기준 · 레포 안 → 레포 기준 · 밖 → 절대 경로 · 예외 0.
  기록용 `rel_to_home`과 따로 둔다(D-167 ①).
- `relative_to(ROOT)` **21 → 0**(`cli/register/*` 일곱 · `cli/prompt` · `cli/skeleton` ·
  `cli/export._short`·`cli/golden._rel` 삭제 · `cli/ingest` 선택 근거 줄 · 내장 스키마 기록
  `core/state/registry._repo_rel`). `draft._rel`은 기록이라 그대로 — 기준 순서(상태 → 레포)는 같다.

### ② 파서는 레포 자리를 모른다 — 킷은 플래그로

- `parser/tagger.SNAPSHOT`·`struct_map.KEEP_DIR`(레포 기본값) 삭제 — 주입 없으면 `[파서] …`
  문면 있는 실패. 킷: `--closed-list <파일>`(등록 관문이 상태의 골격 목록을 건넨다 · 없으면
  좌표 대조 생략 한 줄) · 구조 지도 보존은 킷 실행마다 임시 폴더 · 킷 최상단 `openpyxl` import 제거.

### ③ 대장의 자리

- `show report`의 대장 없음 문면이 `store.path(ledger.DIR)`에서 경로·수를 낸다(구판은 옛 자리를
  적고 거기서 세어 늘 0건) · `core/build/ledger.py` 머리말.
- `점검_경로`: `data/ingest_log` 추가(35종) + **토큰이 갈린 형태**(`ROOT / 'data' / 'ingest_log'`)도
  잡는다 · 의도적 옛 배치 픽스처는 `# 옛 배치` 표시(D-167 ⑧).

### ④ 선택 의존 부재 · 읽기 경고

- `parser/reader.MissingDependency(ImportError)` + `_need()` 한 자리 → CLI 훅이 `` [상태] `.xlsx`를
  읽으려면 `openpyxl`이 필요하다 — pip install openpyxl `` + 다음 줄(인입 · `parse run` · `scan` ·
  등록 · Traceback 0) · 인입은 문서 단위 FAIL 행 + 끝 요약.
- xlsx 읽기 경고를 잡아 `read_warnings`(있을 때만) → 화면 한 줄 `그림 n개를 읽지 못해
  건너뜀(WMF k)` · 원문은 로그 파일 · stderr 0.

### ⑤ 등록 표본의 시트 관문

- 관문 한 벌을 `cli/sheet_gate.py`로 뗐다(호출자 셋: 인입 · `parse run` · 등록) ·
  `cli/register/samples.py` — `generate` 입구에서 표본마다 관문, 기록은 인입과 같은 자리,
  `--sheets`(표본 하나일 때) · 관문·리허설·킷이 기록을 읽는다(`--sheet-roles <임시 표>`).
- 같은 파일을 나중에 인입하면 「시트 역할 — 기록대로 진행」(관문 0).

### ⑥ 사내 모양 회귀 루트 — `tests/test_g6_shanae_root.py`

- 코드 사본 둘(기본 · 사내 모양) — 사내 모양은 **상태 루트가 코드 밖**(`ONTO_MOCK_HOME` 시험 훅 ·
  D-167 ⑨) + 좌표 층 `equipment`. 등록(산문 RFQ01 생성→상태→확정 · 표 ipqc) → 인입 → 질의 12 →
  반출 → 골든 → 뷰어 API → `doctor --quick`.
- 대조: **canonical 99 = 99 · 엣지 149 = 149(걸침 11) · 큐 kind별 같음 · 질의 12 같은 경로 ·
  뷰어 노드 90 = 90 · doctor --quick 0 · 0 · 코드 폴더 새 파일 0 · 예외 0**.

### 실행으로 확인한 것

- 회귀 **1,517 → 1,546/1,546** · FAIL 0 · 클린 2회 동일 · doctor EXIT=0.
  순증 29(신설 `test_g6_shanae_parts` 16 · `test_g6_shanae_root` 13) · 삭제 0 ·
  `test_p1_wiring` 1건은 잠그는 성질을 새 자리로 옮겼다(`KEEP_DIR` → `keep_dir`·`use_dir`).
- 동작 등가 **네 벌 diff 0**(vs `046c05d` — 사전 306 · 대장 399 · 엣지 133/92 · 노드 95/47 · 큐 107).
- 검사 5종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13 · 자산 해시 갱신(킷) · 코드 지도 재생성 ·
  §7 상한 위반 0(함수 셋 분할 — D-167 ⑪) · 미정의 이름 0 · 상태 거부 근거 없음 0.
- `git diff core/`: `paths.py`(+`show` · 시험 훅) · `state/registry.py`(`_repo_rel`) ·
  `build/ledger.py`(머리말).
- **표 밖에서 같이 고친 자리**: `cli/platform.cmd_accuracy`의 `G._rel`(지운 도우미의 속성 접근 —
  회귀가 잡았다 · D-167 ⑫) · 함수 상한 셋 · `test_onsite` 옛 배치 표시.
- 가이드·구조도(같은 커밋 · 사용자 확정): `2B_작업가이드` §0·§4·§4.1·§7 · `걸어가기_설비문서` §2 ·
  `상태_폴더_가이드` §5 · 구조도 `00`(1.1·1.6·2.1·3.1·0.3 Code) · `01`(0″ · 관문 a) · `02` · `06`(0.3 둘 ·
  1.5 · 2.1 · 2.2) · `10`(생성물).
- 소요: 1회차.

### 허브 마감 판정 · 문서 몫 (hub_52 · 2026-09-23)
- B86 닫음. D-167 ①~⑫ 확정 — 개정대장 §BU. 문서 7 §7.1·§7.5·§7.6-B-6·§7.8 · 문서 6 §6.4·§6.7 · CLAUDE.md §5.
- B87 전제 11행 d409440 재확인(4행 229 · 8행 80). 범위 불변.

### 허브 발주 — B88 · 주간 논의 마감 (hub_53 · 2026-09-23)
- B88 = 리더의 폭과 그림 이해: 엑셀 그림 → ④ · docx · register status 재확인 · 가이드 정리(시작하기 · 증상표 · 점검_가이드). B87 뒤.
- 결정(개정대장 §BV): 큐 처리 화면은 플랫폼으로 · OCR 엔진 보류 · D-164 ② 확정 · 혼재 보류.

### 허브 — 문서 구조 정리 · B88 ④ 개정 (hub_54 · 2026-09-28)
- 문서는 다섯 갈래 · 새 파일은 사용자 확정 때만 · 안건은 살아 있는 것 + 최근 마감 3 (CLAUDE.md §7 · 개정대장 §BW).
- 00_칸_대장 Role 열(옛 07_칸_해설 흡수 · Card 열 폐기) · 09_부품_해설 534 → 101행.
- B88 ④ = 가이드·문서 정리(새 파일 0 · 안건 40개와 멈춘 장부 넷 삭제 · 태그 pre-doc-cleanup · 점검_가이드). B88은 착수 전이다.
- 순서: B87 → B88.
