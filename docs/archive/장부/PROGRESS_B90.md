# PROGRESS — B90 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B90의 본문을 여기로 옮겼다(B93 마감 때).

## B90 — 층 겹침을 한 노드로: 공통 config(카테고리 카탈로그) · 전역 해소 · 주·겸 · 걸침 엣지 문장화 · 등록 스키마 재대조 · registry 원자 쓰기 (2026-09-29)

순서 ① → ⑦. 가결정 D-171. 수치의 출처는 전부 **창작 표본**(mock + 테스트 전용 층 덧칠 `tests/fixtures/layers_b90/overlay.json`) — 메커니즘 확인이다([정정] 50). 레포 mock `layers/`에는 겹침·겸을 넣지 않았다(`common.json` = 기존 선언의 복사).

### 전제 대조표 14행 (origin `3363b8f` 위 `adde731`)

1~14행 기대값과 전부 일치(105·93 · 19 · 125 · 368·399 · 50·51 · 311·333 · 223 · `layers/process/config.json:31` 한 줄 · `[]` · 365·161 · 103·80·100 · 235·112 · 249 · 4).

### ① 층 공통 config — 카테고리 카탈로그 (칸 0.1)

- `core/state/catalog.py`(읽기·초안·거부) · 자리 `paths.common()` · `layer_of_category` = 카탈로그 `home` · `coord_layer` = `Process`의 집 ·
  `canonical_scope`는 `layers/common.json` 한 곳(레포 `layers/process/config.json`에서 옮김 — `load_config`가 층 config에 얹는다).
- 거부 다섯 갈래 화면(`bootstrap` — 층을 심기 전):
  - ⓐ `[bootstrap] [상태] 층 공통 config가 없다 — layers/common.json` / `초안을 만들었다 → layers/common.draft.json` /
    `Unit home (빈칸 — 여러 층이 선언했다 ['process', 'quality'] — home을 그중 하나로 채운다)` / `canonical_scope ← 층 config에서 옮김` /
    `▶ 다음 줄: 빈칸을 채워 common.json으로 저장 → python run.py bootstrap` (rc 1 · 두 번째 실행은 「이미 있다(덮지 않았다)」)
  - ⓑ `층 ['quality']의 카테고리 'Tool'가 공통 config에 없다 — "Tool": {"home": "<층>"}를 더한다`
  - ⓒ `'Failure'의 home 'process'는 그 카테고리를 선언하지 않은 층이다 — 선언한 층 ['quality']` · 빈칸이면 `'Unit'의 home이 빈칸이다 — …`
  - ⓓ `층 process의 config에 canonical_scope가 남아 있다 — 공통 config로 옮겼다(두 곳 0) · layers/process/config.json에서 지운다`
  - ⓔ `'Process'의 also가 카탈로그에 없는 카테고리 'Tool'를 가리킨다` · `'Process'의 also['Unit']의 단 ['floor']가 main·sub·detail 밖이다`
- 초안 파일(겹침 루트 — quality도 `Unit` 선언): `{"common_version": 1, "categories": {"Failure": {"home": "quality"}, "FailureEffect": {"home": "quality"},
  "Process": {"home": "process"}, "Property": {"home": "process"}, "Unit": {"home": ""}}, "canonical_scope": {…}, "_빈칸": {"Unit": "…"}}` — 채워 저장하면 `bootstrap` rc 0.
- `doctor` 첫 줄: `… · 층 2(상태 루트) · 좌표 층 process · 공통 config v1 · 문서 0`.

### ② 전역 해소 — table·prose 한 길 (칸 3.2 · 3.4 · 3.5)

- `Builder.resolve_at_home`(집 빌더에서 매칭·생성) — prose `_build_prose_pass1`과 table `loop.h_entity`가 같은 함수 · 좌표 조회(`_graph_for`)도 집 ·
  prose Pass 2 엣지·부착은 끝점의 제 그래프를 건넨다(걸침 엣지) · 예고(`_plan_hit`)도 집 · `target_layer ≠ 집` → 등록 관문 G4C 상세.
- 테스트 세트(quality가 `Unit`도 선언 · 카탈로그 `Unit.home = process`) — CP01 뒤 품질 prose 한 청크(「노칭 프레스」 기존 · 「노칭 커터」 신규 · 「칼날 마모」 occurs_in 둘):

| | process 노드 · 엣지 · Unit | quality 노드 · 엣지 · Unit | 큐 auto_node (layer, 표기) |
|---|---|---|---|
| 옛 코드 `3363b8f`(같은 덧칠) | 63 · 100 · 7 | 7 · 2 · **2** | (quality 노칭 커터) · (**quality 노칭 프레스**) · (quality 칼날 마모) |
| 새 코드 | 64 · 100 · 8 | 5 · 2 · **0** | (**process** 노칭 커터) · (quality 칼날 마모) |

  ⓐ 「노칭 프레스」는 CP01이 만든 `노칭::노칭 프레스`에 매칭(출처에 CP01·XB90P 둘) ⓑ 「노칭 커터」는 process 그래프에 · 큐 `layer=process`
  ⓒ occurs_in 두 엣지는 quality 그래프에 · 끝점은 process 노드 ⓓ 같은 내용을 table 문서(`build_table` · quality 스키마)로 — 스냅샷이 prose와 같다 · `target_layer=quality`(Unit의 집 process)면 `[FAIL] G4C … unit.target_layer='quality'는 Unit의 집 'process'와 다르다`.

### ③ 주·겸 카테고리 · 자기 좌표 규칙 (칸 3.3 · 3.4 · 3.6)

- 겸은 노드에 저장하지 않는다 — `catalog.categories_of(node)` = 주 ∪ `also[주]`(단 = 노드 `tier`). 매칭 후보(`matcher` 세 자리 · `prose._dict_hit`) ·
  삼항 게이트(주 쌍이 통과 못 하면 겸 조합) · 자기 좌표(`Builder._self_coord` — 키 조립 전 · 대장 `path=self_coord`) · 추출 어휘 한 줄(`extract.categories_with_also` ·
  지시문 e-1.2 규약 7 일반 문장) · `show node` 「겸 Unit」 · JSON 반출 `also`.
- 테스트 세트(`also: {"Unit": ["sub","detail"]}` · 「노칭」(sub) 별칭 「노칭 unit」 · process에 `Component part_of Unit`):
  ⓐ 좌표 「노칭」 아래 「노칭 unit」(Unit) → 스테이션 자신 · 새 Unit 0 · 대장 `self_coord` ⓑ 「칼날 part_of 노칭 unit」 → 엣지 `part_of → 노칭`(Process — 겸으로 통과)
  ⓒ `also`를 지우면 새 Unit `노칭::노칭 unit` · 대장 `none` · 엣지는 그 노드로 ⓓ 카테고리 거름 자리 전수:

| 자리 | 무엇을 거르나 | 겸 | 이유 |
|---|---|---|---|
| `core/matcher.py` `dict_hits`(사전 exact 후보) | 후보 카테고리 = C | **넣었다** | ⓐ 매칭 후보 — C로 해소할 때 C를 겸하는 노드도 후보 |
| `core/matcher.py` `candidates`(후보 검색 풀) | 후보 카테고리 = C | **넣었다** | 같음 |
| `core/matcher.py` `match`(판정 입력 재확인) | 후보 카테고리 = C | **넣었다** | 후보가 `also`를 지고 오면 통과(겸 후보가 판정 전에 버려지지 않게) |
| `core/build/prose.py` `_dict_hit`(attach 대상 해소) | 대상 카테고리 = C | **넣었다** | 부착 대상도 매칭 후보의 한 자리 — 「노칭 unit에 붙인다」가 스테이션에 닿는다 |
| `core/build/gate.py` `commit_edge`(삼항) | 끝점 카테고리 쌍 | **넣었다** | ⓑ 주 쌍이 통과 못 하면 주 ∪ 겸 조합 |
| `core/build/build.py` `resolve_anchor`(좌표 조회) | 골격 노드 카테고리 = Process | 뺐다 | 좌표는 골격 **조회 전용** — 주 카테고리로만 찾는다(겸으로 좌표를 넓히면 Unit 표기가 좌표가 된다) |
| `core/build/build.py` `descend_anchor`(극성 하강) | 골격 카테고리 | 뺐다 | 골격 구조 — 주 카테고리 |
| `core/build/retry.py:269`(재시도 좌표 재조회) | 좌표 카테고리 | 뺐다 | 좌표 조회와 같은 규칙 |
| `core/state/bootstrap.py:184`(옛 골격 잔존) | seed 카테고리 | 뺐다 | 골격 심기의 대조 — 주 카테고리 |
| `core/state/skeleton.py:333`(골격 이름 조회) | seed 카테고리 | 뺐다 | 같음 |
| `core/state/ops.py:127`·`:230`(스코프 자식·이관 이름) | `bind_categories` | 뺐다 | 이름 규칙은 주 카테고리로 정한다(키가 계산값에 따라 바뀌면 안 된다) |
| `core/state/ops.py:169`(이관 — 좌표 직접 부착) | 부모와 같은 카테고리 | 뺐다 | 구조 연산 — 사람 도구는 주 카테고리 동일성으로 |
| `core/state/ops.py:285`(개명 충돌) · `:678`(alias 충돌) | 같은 카테고리의 같은 이름 | 뺐다 | 같은 주 카테고리의 이름 충돌만이 충돌이다 |
| `core/build/build.py` `entity_key`·`loop._scoped_category`(스코프 판정) | `bind_categories` | 뺐다 | 이름 규칙 — 주 카테고리 |
| `core/build/gate.py` `pair_relation`(규칙 B 폴백) | 카테고리쌍 매핑 | 뺐다 | 폴백 관계는 주 쌍 표 한 벌(겸 조합을 섞으면 한 쌍이 관계 둘을 낸다) |

### ④ 걸침 엣지 문장화 (칸 4.3)

- 재현 먼저(테스트 세트 — quality가 `occurs_in`을 층 안 확장에 넣고 `칼날 마모 occurs_in 노칭 프레스`가 quality에 저장된 걸침 엣지):
  `query "칼날 마모는 어디서 생기나" --json` **전 `facts []`** → **후 `['칼날 마모는 노칭::노칭 프레스 공정에서 발생한다']`**.
  원인: 층 안 확장이 반대 끝점까지 데려오면 `facts`는 「이 층에 없는 끝점」, 다리는 「출발 집합으로 되돌아옴」으로 서로 미뤘다.
- `query.stranded`(양끝이 그 층 수집에 들고 한쪽이 다른 그래프) → `cross_facts`(저장한 층의 템플릿) · 다리로도 닿은 같은 엣지는 한 번(두 끝점을 다 링킹한 질문에서 1회) ·
  mock 질의 스모크 불변(회귀 · 네 벌 diff 0).

### ⑤ config를 바꾸면 등록 스키마를 다시 대조한다 (칸 0.1 · 1.x)

- `kit/check_vocab.py`(관문과 같은 `gate_checks.check_vocab`) ← `cli/register/recheck.py` ← `bootstrap` 끝 · `doctor` `[2′]`.
- mock: `cp PASS — 층 process 어휘 안` · `pfmea PASS` · `ppt_process PASS` · `ppt_quality PASS`.
- process에서 `Property`를 지우면(선언과 삼항): `cp FAIL — G4C … 관리항목.category='Property'는 process 카테고리에 없다 …` /
  `다음 줄: layers/process/config.json의 categories(또는 relation_patterns) · 또는 python -m cli.register generate cp --revise` · `cp FAIL — G4E …` ·
  `pfmea FAIL — G4C … control_item_for_fm …` / `다음 줄: layers/process/config.json의 …`(걸침 필드는 그 층) → 되돌리면 넷 다 PASS.
- quality에서 `Process`를 부르는 삼항을 빼면: `ppt_quality FAIL — G4C …` + `ppt_quality ⚠ 층 quality이 Process를 말하지 않는다 … 이 층의 prose 문서는 좌표를 못 단다`.

### ⑥ registry — 원자적 쓰기 · 디버그 파일 자리 (칸 1.x)

- `cli/register/__init__.write_file`(→ `store.atomic_write_bytes`) 한 자리로 바꾼 쓰기 23곳: `__init__`(state.json) 1 · `confirm`(approval.json) 1 ·
  `generate`(input_package.json 6 · 고정 어댑터 래퍼 1) 7 · `view`(view.json · view.html · 리허설 임시 파일 · 확정 복사 어댑터·스키마 2) 5 ·
  `draft`(초안 스키마 2 · 어댑터 1 · last_error 1) 4 · `gate`(input_package 1 · 스탬프 어댑터 1) 2 · `interview`(interview_log · input_package) 2 · `ledger`(columns.json) 1.
  AST로 잰 직접 쓰기 호출 0. `review/<dt>/`에 `.<이름>.lock`이 생긴다(store의 락 파일 규칙).
- `last_error.json` · `prompt_rendered.md` → `work/register/<dt>/`(`paths.register_debug`) · 화면 경로도 따라감.

### ⑦ 가이드·구조도 (전후)

- `config작성_가이드`: §0-a 신설(층 config = 렌즈 · 공통 config의 집·겸·이름 규칙 · 초안 흐름 · 거부 표 · 재대조) · §1-a·§5 `canonical_scope` 자리 ·
  249행 전 「값에 기종어(프레스·기·장치·머신·로봇·설비)가 섞이면 Unit 쪽이다」 → 후 「스테이션 이름 + 설비어(「노칭 unit」·「노칭 설비」)는 스테이션 자신이다(공통 config의 겸 …) · 스테이션 아래 구성 기계(프레스·커터·로봇)는 Unit이다」.
- `골격작성_가이드` §3 「스테이션을 몇 단에 두나 = 겸이 걸리는 단」(… unit · … 설비 표기는 ALIASES) · `걸어가기_설비문서` §0(공정 = 설비는 겸 · Property는 공정층) ·
  §1-a(`common.json` home도 따라 바꾼다 · 초안 흐름) · §1(공통 config 줄) · §2(`generate rfq <골격 층>`) · `2B` 시작하기 2′ 공통 config · 반입 뒤 4 ·
  `상태_폴더_가이드`(`layers/common.json` · `work/register/<dt>/`).
- 구조도: `03_구축`(집에서 해소 · 자기 좌표 → 겸 포함 후보 · 엣지는 뽑은 층 · 게이트 주 ∪ 겸) · `04_질의` ③′ · `06_손잡이_대장` 0.1 공통 config 행 · 3.4 · `05_조절_지도` ·
  `00_칸_대장` 0.1·1.5 Code 열 · `10_코드_지도` 재생성.

### 실행으로 확인한 것

- 어서션 **+21 · 삭제 0** — 신설 `test_g6_catalog`(① 5 · ② 5 · ③ 4 · ④ 2 · ⑤ 3 · ⑥ 2 — 각 성질은 파일 머리말). 기대값을 바꾼 곳:
  `test_onsite` ①(층 자산 관문이 열리는 성질을 잰다 — 다음 멈춤은 공통 config 초안) · `test_p1_csv`(지시문 판 e-1.2) · `test_g6_coord_layer`·`test_g6_shanae_root`
  (층 폴더 이름을 바꾸는 사본에서 `common.json`의 home도 바꾼다 — 사내 절차 그대로).
- 회귀 **1,596 → 1,617/1,617** · FAIL 0 · 클린 2회 동일 · doctor EXIT=0.
- 동작 등가 **네 벌 diff 0**(vs B89 기준 — 그래프 process 95/133 · quality 47/92 · 사전 306 · 큐 107 · 판정대장 399, 창작 표본).
- 검사 6종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 **12**(13 → 12: `canonical_scope`가 층 키가 아니게 돼 「층별 차이」 한 줄이 빠졌다) · 가이드 0 · 코드 지도 재생성 · §7 위반 0 · 자산 해시 갱신(kit · prompts · layers seed).
- `git diff core/`: `paths`(common · register_debug) · `state/catalog.py`(신설) · `state/bootstrap`(load_config · layer_of_category · coord_layer) · `state/registry`(schema_path) ·
  `build/build`(집 라우팅 · 자기 좌표) · `build/loop`·`prose`·`entry`(같은 함수) · `build/gate`(겸 삼항) · `build/extract`(겸 한 줄) · `matcher`(겸 후보 · PATHS) · `query/query`(stranded).
- 소요: 1회차. 사고 1건 — 회귀가 도는 중에 `git stash`로 트리를 잠깐 되돌렸다 → 그 회귀를 멈추고 클린에서 다시 돌렸다(위 수치는 다시 돈 것).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

1. **문서 3 §3.1** 층 config 키 일람 — `canonical_scope`가 층 키에서 빠지고 **공통 config `layers/common.json`**(카테고리 `home`·`also` · `canonical_scope` · `common_version`)이 생긴다 · 층 config `categories`는 층의 렌즈(겹침 허용).
2. **문서 3 §3.6** 걸침 — 도착점은 카테고리의 집 · 겸(주 ∪ 겸)이 삼항 판정에 든다.
3. **문서 4 §4.2·§4.3** 해소 경로 — 집 빌더에서 매칭·생성(table·prose 한 길 · `target_layer` = 집) · 자기 좌표 규칙(키 조립 전 · `path=self_coord`) · 겸 포함 후보 · 대장 `path` 닫힌 값에 `self_coord`.
4. **문서 5 §5.2-1** 문장화 — 층 안 확장으로 닿은 걸침 엣지도 저장한 층의 템플릿으로 · 한 번만.
5. **문서 6 §6.5** 등록 관문 G4C — `target_layer`가 집과 다르면 FAIL · `bootstrap`/`doctor`의 등록 스키마 재대조(같은 판정).
6. **문서 7 §7.1** 모듈(`core/state/catalog.py` · `kit/check_vocab.py` · `cli/register/recheck.py`) · **§7.8** 자산 자리(`layers/common.json` ②등록 · `work/register/<dt>/` 디버그 ④) · registry 쓰기 원자성.
7. **CLAUDE.md §5** 좌표 층 — 「`Process` 카테고리를 선언한 층」 → 「공통 config에서 `Process`의 집」.
8. 추출 지시문 판 **e-1.2**(규약 7 — 겸 한 줄) — 프롬프트 판 기록.
