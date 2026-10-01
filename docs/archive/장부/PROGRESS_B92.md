# PROGRESS — B92 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B92의 본문을 여기로 옮겼다(B95 마감 때).

## B92 — 층 공통 config를 bootstrap이 층 config에서 맞춘다: 한 층 선언은 자동 · 겹침·겸·집 변경은 사람 (2026-10-01)

순서 ① → ② → ③. 가결정 D-173(7건). 수치의 출처는 **창작 표본**(테스트 전용 층 `b92eq` · 카테고리 `Gear`·`Tool`) — 메커니즘 확인이다([정정] 50).

### 전제 대조표 6행 (origin `955bea8` 위 `895f1cb`)

1~6행 기대값과 전부 일치(77·88 · 117·294 · 60·174·224 · 184·190 · 0 · 안건 4).

### ① 카탈로그 맞추기 — `bootstrap` 입구 (칸 0.1)

- 새 `core/state/catalog_sync.py` — `plan`(규칙 닫힌 다섯 · 쓰기 0) · `apply`(원자 쓰기 · `common_version` +1 · 로그 `work/logs/bootstrap_<날짜>.log`에 근거 한 줄씩) · 노드 수는 GraphStore 경유. 화면은 `run.py::_catalog_gate`.
- 처음(운영 · 파일 없음): 같은 규칙으로 `common.json`(v1)을 바로 쓴다 · 빈칸이면 멈춘다 · `common.draft.json`은 더 쓰지 않는다(남아 있으면 「쓰지 않는 파일이다(지워도 된다)」 한 줄) · `catalog.write_draft` 삭제(부르는 곳 0).
- `bootstrap --dry-run` — 계획만 · 쓰기 0 · 멈출 것이 있으면 rc 1. 화면(창작 — 새 층 `b92eq`가 `Gear`를, `b92eq`·`quality`가 함께 `Tool`을 선언):
  `[bootstrap] 공통 config + 'Gear' (home b92eq — b92eq만 선언)` /
  `[bootstrap] 공통 config [상태] 'Tool' home 빈칸 — 여러 층이 선언했다 ['b92eq', 'quality'] — 그중 하나로 채운다` /
  `[bootstrap] --dry-run — 계획만 보였다(공통 config·그래프 쓰기 0) · 바뀔 것 있음 · 멈출 것 있음` (rc 1) → 실제 실행 뒤 `Gear {"home": "b92eq"}` · `Tool {"home": ""}` · v2 · 멈춤.
- mock: 레포 `layers/common.json`이 층 선언과 이미 맞아 변경 0(`bootstrap --dry-run` 「바뀔 것 없음」 · 파일 md5 불변).

### ② 노드가 있는 카테고리의 집 변경을 막는다

- 집이 아닌 층 그래프에 그 주 카테고리 노드가 있으면 멈춘다: `[bootstrap] 공통 config [상태] 'Unit'의 home을 process → quality로 바꿨지만 process 그래프에 Unit 노드 7개가 있다 — 재빌드(init --fresh → bootstrap → 재인입) 또는 home을 되돌린다`(창작 — CP01 뒤).
- 층에서 지운 카테고리에 노드가 남으면: `'Property'를 어느 층도 선언하지 않는데 process 그래프에 노드 10개가 남아 있다 — 층 config에 되살리거나 재빌드…`(창작).

### ③ 가이드 · 구조도

- `config작성` §0-a(초안 흐름 → 맞추기 표 · 사람 몫 · `--dry-run` · 멈춤 표 ⓐⓑ 행) · §1-a 표(Component 줄은 자동) · `2B` 시작하기 2′ · `걸어가기` §1-a 다음 문단·§1 · `상태_폴더`(등록(층) 행 · `bootstrap` 행 — 초안 없어짐 · 로그 · dry-run).
- 구조도 `06` 0.1 공통 config 행 · `00_칸_대장` 0.1 Code 열(`catalog_sync.py` · `run.py::_catalog_gate`) · `10`(생성).

### 실행으로 확인한 것

- **클린 회귀 2회 동일**: **1645/1645 PASS** ×2(B91 1637 + 8). **네 벌 diff 0**(기준선과 같다).
- 검사 6종: 0 · 0 · 0 · 0 · 13(순증 0) · 0. §7 상한 위반 0. 자산 해시 변화 없음(33).
- 어서션 **+8 · 삭제 0** — `test_g6_catalog_sync`: ⓐ 한 층 선언 자동 추가·판 +1·로그 / ⓓ 사람 값(home·also) 불변 / ⓑ 새 겹침 빈칸+멈춤 / ⓒ 선언·노드 없으면 제거(층째 지워도) / ⓒ 노드 남으면 멈춤 / ⓔ 집 변경 막기 / ⓕ dry-run 쓰기 0 / ⓖ 운영 처음 바로 생성·초안 0·채우면 선다. **기대 변경 1**: `test_g6_catalog` ①ⓐ(초안 파일 → `common.json` 바로 생성 · 「초안을 덮지 않는다」 성질은 대상이 없어 빠짐 — 수는 21 그대로).
- `git diff core/`(895f1cb 대비):  3 files changed, 132 insertions(+), 20 deletions(-) — 새 `catalog_sync.py` · `catalog.py`(초안 함수 삭제·문면) · `paths.py`(docstring).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 3 §3.1 공통 config 문단: 거부 ⓐ 「초안을 만들어 보이고 멈춘다 · 자동 채택 0」 → 「`bootstrap`이 층 config에서 맞춘다(규칙 닫힌 다섯) · 처음이면 바로 만든다 · 빈칸이면 멈춘다」 · ⓑ 「사람이 줄을 더한다」 → 자동 맞추기 · 집 변경 막기 · `--dry-run`.
- 문서 7 §7.8 ②등록 `layers/common.draft.json` 언급 삭제 · `bootstrap` 로그 근거.
