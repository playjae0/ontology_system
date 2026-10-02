# PROGRESS — B93 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B93의 본문을 여기로 옮겼다(B96 마감 때).

## B93 — 뼈대 맞추기 보강: 골격 카테고리의 집은 골격 층 · 골격 모순 거부 · 겸 상태 표시 · 뼈대층 구성 가이드 (2026-10-01)

순서 ① → ② → ③ → ④. 가결정 D-174(6건). 작업 브랜치가 PR #73으로 main에 머지·삭제돼 있어 같은 이름으로 최신 main(`fc0552d` — 트리 = `ef5a63b`)에서 다시 시작했다 · hub_65 반입 `0f92022`. 수치의 출처는 **창작 표본**(mock 층 덧칠) — 메커니즘 확인이다([정정] 50).

### 전제 대조표 7행 (origin `44e36f5` 기준 · 반입 뒤 `0f92022`)

1~7행 기대값과 전부 일치(0 · 249·227 · 64 · 190 · 127 · 84·골격작성 82·config작성 309 · 안건 4).

### ① 골격 카테고리의 집은 골격 층 — 자동

- `catalog_sync.skeleton_layers`(층 config `skeleton.category`) · `plan`이 골격 카테고리를 먼저 본다: 없으면 추가(여러 층이 선언해도) · 빈칸이면 채운다 · 처음(파일 없음)도 같은 한 길.
- 화면(창작 — 품질층도 `Process`를 선언): `[bootstrap] 공통 config + 'Process' (home process — 골격이 process에 있다)` · 빈칸이면 `[bootstrap] 공통 config 'Process' home 빈칸 → process (골격이 process에 있다)`(판 +1 · 로그) · `--dry-run`도 같은 계획(쓰기 0).

### ② 골격 모순 거부 — 심기 전에

- ⓕ `[bootstrap] 공통 config [상태] 골격 카테고리 'Process'를 층 ['process', 'quality']의 골격이 함께 가진다 — 같은 뜻 노드가 두 그래프에 두 벌 생긴다 · 골격은 한 층만 갖는다`
- ⓖ `[bootstrap] 공통 config [상태] 'Process'의 home은 quality인데 골격은 process에 있다 — 골격 노드는 process 그래프에 심긴다 · home을 process로 고친다` — **첫 실행에서** 멈춘다(그래프의 Process 노드 0 · B92 「바꿨지만」 문면 없음).

### ③ 겸 상태 — `bootstrap` 끝 · `doctor`

- 꺼짐(mock 기본): `[bootstrap] 골격 'Process'(process): 겸 없음 — 골격 노드 이름 + 다른 카테고리 표기는 새 노드가 된다(자기 좌표 규칙 꺼짐)` · `골격 'FailureEffect'(quality): 겸 없음 — …`
- 켜짐(창작 — `Process.also = {"Unit": ["sub","detail"]}`): `[bootstrap] 골격 'Process'(process): 겸 Unit(sub·detail) · 겸 단 별칭 n개`
- 반쪽(창작 — `FailureEffect.also = {"Failure": ["main"]}` · 별칭 없는 flat 골격): `[bootstrap] ⚠ 골격 'FailureEffect'(quality): 겸 Failure(main)인데 겸 단 별칭 0 — 별칭이 없으면 자기 좌표 규칙이 돌지 않는다`
- 종료 코드 0 · `doctor` 첫 블록에 같은 줄(`·`/`⚠`).

### ④ 가이드 · 구조도

- `골격작성` **§3-a 신설 「뼈대층(설비·공정)을 처음 세울 때 — 이 절은 그때만 쓴다」**(한정 머리 · 두 단 · 나누는 기준 · ALIASES · 그 아래부터 Component/Property · 공정층은 Process 골격 없음 · 겸을 켜는 셋과 확인법 · 사내 LLM 요청문 틀 — 예시 이름 창작) · §3 표 82행을 둘로(하위 공정 unit = 골격 · 그 아래 구성 기계·부품 = Component) · 「설비를 골격에 넣기」 행에 두 단 포인터.
- `config작성` §0-a(§3-a 가리키는 한 줄 · 맞추기 표에 골격 행 · 멈춤 표 ⓕⓖ · 겸 상태) · Process 정의문 예시 309행(구성 기계는 Unit → 하위 공정은 골격 · 그 아래 Component · 골격 밖 설비 표기는 인입이 Unit).
- `2B` 시작하기 2′ · `걸어가기` §1-a(ⓖ 문면 · 겸 상태 화면). 구조도 `06` 0.1 · `00_칸_대장` 0.1 · `10`(생성). 런타임 `prompts/`·레포 mock `layers/`는 손대지 않았다(자산 해시 불변).

### 실행으로 확인한 것

- **클린 회귀 2회 동일**: **1650/1650 PASS** ×2(B92 1645 + 5). **네 벌 diff 0**(기준선과 같다).
- 검사 6종: 0 · 0 · 0 · 0 · 12(기대값) · 0. §7 상한 위반 0. 자산 해시 변화 없음(33).
- 어서션 **+5 · 삭제 0**(`test_g6_catalog_sync` 8 → 13): ⓐ 골격 카테고리 겹쳐 선언해도 집 = 골격 층 자동 / ⓑ 빈칸 채움·판 +1·로그 + ⓖ `--dry-run` 같은 계획·쓰기 0 / ⓒ 두 층 골격 같은 카테고리 멈춤 / ⓓ 채운 집 ≠ 골격 층 — 첫 실행 멈춤·그래프 쓰기 0 / ⓕ 겸 상태 세 갈래·rc 0·doctor 같은 줄. ⓔ(골격 밖 겹침은 빈칸 + 멈춤)는 B92 어서션 ⓑ가 그대로 잠근다. 기대 변경 0.
- `git diff core/`(fc0552d 대비):  1 file changed, 90 insertions(+), 22 deletions(-) — `catalog_sync.py`(골격 · 겸 상태).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 3 §3.1 맞추기 규칙: 골격 카테고리 행(집 = 골격 층 · 빈칸도 채움 — 규칙 ④·D-173 ②의 예외) · 거부 ⓕ(두 층 골격 같은 카테고리) · ⓖ(집 ≠ 골격 층 — 첫 실행) · 겸 상태 표시(켜짐·꺼짐·반쪽 — 거부 아님).
