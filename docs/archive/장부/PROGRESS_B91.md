# PROGRESS — B91 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B91의 본문을 여기로 옮겼다(B94 마감 때).

## B91 — 추출 입구: 사내 손잡이 · 렌즈(doc_type의 층 목록) · 시트 두 모드 · prose 좌표 셋 · ref 노드 근처 · 겸 집 불일치 경고 (2026-09-29)

순서 ⑤ → ① → ② → ③ → ④ → ⑥ → ⑦. 가결정 D-172(14건). 수치의 출처는 전부 **창작 표본**(mock · 테스트 전용 덧칠 · 추출 스텁) — 메커니즘 확인이다([정정] 50). 새 기본값(`sheet_min_hits` 1 · `lens_min_score` 1 · `lens_call_cap` 2000 · `ref_limit` 3)은 창작이고 사내 실측(`show dist …`)으로 `knobs.json`에서 정한다.

### 전제 대조표 9행 (origin `f98d277` 위 `e49999a`)

1~9행 기대값과 전부 일치(156·302·306 · 57·173 · 26 · 42 · 263 · 233 · 120 · 190 · 223 · 226 · 130 · 38 · 56 · 322 · 안건 4).

### ⑤ 사내 손잡이 (칸 0.5 — 새 칸)

- `$ONTO_HOME/knobs.json`(`paths.knobs()`) · 닫힌 목록 10(`core/state/knobs.py::KNOBS` — 기존 상수 여섯 `heading_max_chars`·`chunk_rows`·`chunk_max_chars`·`sheet_thresholds`·`form_auto`·`collect_limit` + 새 값 넷 `sheet_min_hits`·`lens_min_score`·`lens_call_cap`·`ref_limit`) · 기본값 = 주인 모듈 상수(두 벌 0) · `_` 키는 주석.
- 파서는 `parser/tuning.apply`로 주입(루트가 정해질 때 한 번) · 킷은 `--knobs <파일>`(관문이 있을 때만) · core 값은 `knobs.get`.
- 어긋난 파일: 루트 결정에서 올리지 않고 기억 → 운영 관문(`require_knobs`)·값 읽기에서 문면으로 멈춘다(`모르는 키 [...] · 아는 키 … · ▶ 다음 줄` / `형 밖이다 — 기대 range · 기본값 [5, 40]`). traceback 0.
- 기록: 파일이 있을 때만 `context.knobs = {이름: {value, from}}`(파싱) → 인입 등록부 항목(`doc_registry[…].knobs`). 파일 없음 = 기록 모양 불변.
- 화면 `show knobs`(값 · [출처] · 기본 · 무엇 · 분포 명령) · 분포 `show dist chunks|headings|forms|sheets|evidence|lens|ref`(읽기 전용) · doctor `[1″]` 한 줄.

### ① 렌즈 (칸 3.3)

- 등록부 `lenses`(없으면 등록 층 하나 — 키 없음) · `register lenses <dt> [<층,층>|all]` · `generate --lenses` · `register status`·`show schema`에 렌즈 줄.
- `core/build/lens.py` — 렌즈가 등록 층 하나면 거치지 않는다(지금과 같다). 여럿이면 뿌리 빌더 하나를 `for_layer`로 나눠 렌즈마다 그 층 어휘로 추출(체크포인트 `extract/<doc>@<렌즈>.json`) · 개체는 집에서 해소 · 엣지는 렌즈 층.
- 비용 장치: 관련성 거름(그 층 어휘 = 사전 표기 중 그 층 카테고리 노드 + `relevance_terms` · 종 수 < `lens_min_score`면 LLM 0 · `lens_skipped` 무후보로 남김) · 예고 `렌즈 예고 — 렌즈 k(…) × 청크 n → 거름 뒤 LLM ≤ m회` · 상한 `lens_call_cap`(tty면 [y/N] · 비대화형은 보류 `lens_call_cap`).

### ② 시트 두 모드 (칸 3.1 관문 · 3.8 판정 — 새 칸 · 지점 ⑩)

- 로직 = 모양 AND + 사전 적중(`form.sheet_table(raw, vocab=)` · 어휘는 `sheet_gate.lens_info` — 렌즈 거름과 같은 `lens.layer_vocab`) · 적중 < `sheet_min_hits`면 `ref`.
- LLM = `points.judge_sheet`(태그 `sheet_role` · `prompts/3.8_sheet_role.md` sh-1.0 · 입력 = 시트 이름 + 앞 60행×80자 + 렌즈 층 정의문·관련어 · 출력 prose/ref + 이유 · 닫힌 둘 밖이면 ref) · 팩토리 `sheet_judge()`(mock → None → 로직과 같은 답 · 호출 0).
- 제안 = 같으면 그것 · 어긋나면 `ref` · 빈 시트만 `skip`. 표 열 `적중 · 로직 · LLM · 제안`(마지막 열 = 제안 — 기존 파싱 어서션 유지) · 어긋난 시트는 이유 줄.
- 사람 지정(기본): LLM은 물을 때만(tty) · dry-run·거부 문면은 실호출 0 · `--no-sheet-llm`이면 「끔」. 자동 `--sheets auto`(`ingest-file`·`ingest-dir`·`parse run`·`register generate`): 합의 → 자동 · 어긋남 → `ref` + 승격 후보 · 기록이 있으면 기록대로 · LLM 끔과 함께면 `[사용법]`.
- 기록 `registry/sheet_roles/<doc_id>.json` += `logic` · `llm` · `llm_reason`(live) · `llm_by` · `promote` · `decided_by: auto` — 역할 문자열(`flag`)은 두 제안 키 없음(모양 불변).
- **바뀐 제안 목록**(mock · 층 전부 어휘 · 창작 표본): RFQ01 `사양_전장` prose → **ref**(적중 0) · HIER01 `장문` prose → **ref**(적중 0). 나머지 동일(RFQ01 7장 · HIER01 2장 · CP01 1장). 제안은 화면 값 — 기록·산출 불변(네 벌 diff 아래).
- 힌트 문면 `*:skip` → `*:ref`(관문 입력 예 · 미정 시트 안내 · 사용법 예).

### ③ prose 좌표 셋 (칸 3.3 · 3.4)

- 추출 스키마: entity `parent`(string|null) · 최상위 `about`([{surface, category}]) — strict라 모델에게는 필수(널·빈 허용) · 계약상 선택: 값이 있을 때만 체크포인트에 싣는다(`_optional`) · 옛 체크포인트·mock은 「없음」. 지시문 e-1.3(규약 7·8 · `{{parent_candidates}}` 자리).
- `extract.parent_candidates(chunk)` = 좌표 서브트리 + 본문에 나오는 골격 이름(canonical·별칭 · 2자 이상) — 골격 스냅샷(결정적) · 구축이 같은 함수로 다시 센다.
- 구축 Pass 1 `_entity_parent`(이름 전에 · 후보 안이고 골격 해소되면 이름 부모 · 극성 하강 · 밖이면 null + `defects.log`) · Pass 2 `_link_about`(버퍼 → 사전 · 카테고리 안 · 유일할 때만 · 노드 0 · 못 찾으면 기록) → `chunks.json`의 `about`(있을 때만).
- 수집 tier: describes 직접 1 > 확장 2 > about 직접 3 > 확장 4 · 같은 청크는 앞 tier 한 번 · trace `channel`.

### ④ ref 노드 근처 (칸 4.3 · 4.4)

- `query.ref_near(direct, graphs)` — 직접 링킹 노드의 표기(정식 이름 · `::` 끝 조각 · 별칭 · 2자 이상)가 든 `meta.sheet_role == ref` 청크를 읽을 때 찾는다(저장 0 · 확장 노드 0) · 순위 담은 표기 종 수 → 최신 → id · tier 5 · 상한 `ref_limit`.
- 묶음 `related`(있을 때만) · mock 렌더 `[관련 원문] (doc loc) text` · 실호출 입력 `관련_원문` · 지시문 `4.4_answer.md` a-1.1 한 줄 · 뷰어 수집 카드에 「관련 원문」/「관련 링크」 표시.

### ⑥ 겸 집 불일치 경고 (칸 0.1)

- `catalog.warnings()` — 주 C가 X를 겸하는데 집이 다르면 한 줄 · `bootstrap` ⚠(rc 0 · 거부 아님) · doctor ⚠.

### ⑦ 가이드 · 구조도

- 가이드: `2B`(시작하기 손잡이 행 · §5.1 시트 두 모드 · 자동 모드 · 플래그 둘 · 증상표 넷) · `인입_이해`(화면 줄 셋 · 산문 좌표 셋 문단 · 정본 넷에 `about`) · `config작성`(19종 = 공정 17 · 품질 16 · 선택 `relevance_terms` · `canonical_scope`는 공통 config · §6-a 관련어·렌즈) · `골격작성`(층 config 문법 키 19종) · `상태_폴더`(`knobs.json` · 백업 줄) · `걸어가기`(표 새 열 · ref [관련 원문] · 자동 모드 · 렌즈 · 시트 문턱은 손잡이).
- 구조도: `00_칸_대장`(3.8 · 0.5 신설) · `02`(시트 두 모드 절) · `03`(about · 개체별 부모 · 렌즈) · `04`(수집 tier + ref 근처 · [관련 원문] 채널) · `05`(⚙ 시트 판정 · 렌즈 · knobs) · `06`(「사내 조정 가능」 열 전 행 · 새 행 8 · 2.2 행 갱신) · `00_전체_지도`(갱신 대장 B91 행) · `부품카드.json` · `10`(생성).

### 실행으로 확인한 것

- **클린 회귀 2회 동일**(`init --fresh` → `doctor.py`): **1637/1637 PASS** ×2 · 스위트별 수 동일. 도중 1건 발견·수리: `test_p3_view` ①ⓑ(리허설 체크포인트 재사용) — 등록 층(quality)과 구축 층이 다른 doc_type이 렌즈 키 없이도 렌즈 경로(`@quality` 체크포인트)를 탔다 → 렌즈 경로는 등록부에 `lenses`가 명시됐을 때만(D-172 ④).
- **네 벌 diff 0**: process canonical 95 · 엣지 133 · quality canonical 47 · 엣지 92 · 사전 306 · 큐 107 · 판정대장 399 — 기준선(`b89/four_base.json`)과 바이트 같다(창작 표본).
- 검사 6종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13(반입 커밋 `e49999a`에서도 13 — 순증 0) · 가이드 0. §7 상한 위반 0(코드 지도 ⓔ). 자산 해시 `--write`(33).
- 어서션: **+20 · 삭제 0** — `test_g6_lens` 18(성질: 손잡이 기본=상수·파일이 청크를 바꾸고 기록에 값·출처·거부 문면·show knobs / 렌즈 수렴·거름·예고·상한 보류·등록부 항목 / 시트 두 열·기록 네 필드·자동 합의·승격 후보·LLM 끔 / 개체별 부모·후보 밖 null·관련 링크 노드 0·근거 순위 / ref 근처 직접 노드만·상한 / 겸 집 경고) · `test_2a_gateway` +2(⑩ 도달성·본문 스모크). **기대 변경 3**: `test_2a_gateway` 지점 수 9→10 · `test_p1_csv` 추출 판 `e-1.2` → `e-1.2 이상` · `test_g6_sheets` Enter=제안의 비교 재료를 관문과 같은 함수(`rows_of`+`lens_info`)로.
- `git diff core/`(e49999a 대비): 13파일 +699/−47 — 새 `core/build/lens.py`·`core/state/knobs.py` · 기존 `paths`·`entry`·`extract`·`prose`·`ingest`·`query`·`registry`·`sheets`·`catalog`·`gateway`·`points`.

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 7 §7.6-B-2 「LLM 지점 9종」 → 10종(⑩시트 역할 판정 · 태그 `sheet_role` · `prompts/3.8_sheet_role.md`) · §7.1 mock 대체 표에 ⑩(로직과 같은 답 · 호출 0).
- 문서 7 §7.8 상태 루트 파일 `knobs.json`(닫힌 목록 · 파싱·인입 기록 `context.knobs`) · `sheet_roles/<doc_id>.json` 필드(logic·llm·llm_reason·llm_by·promote · decided_by `auto`) · 체크포인트 `extract/<doc>@<렌즈>.json`.
- 문서 6 §6.4-5 판단 상수의 자리(`ADAPTER.expects` + `knobs.json` · 파서 주입 · 킷 `--knobs`) · 문서 6 시트 관문 문단(두 모드 · 제안 = 합의 또는 ref · `--sheets auto` · `--no-sheet-llm` · LLM은 물을 때만) · 「제안은 규칙 — LLM 지점을 늘리지 않는다」(B83 문장) 폐기.
- 문서 3 §3.1 층 config 키 일람에 `relevance_terms`(선택) · doc_type 등록부 `lenses`.
- 문서 4 §4.2·§4.10 추출 출력 entity `parent` · 청크 `about` · 부모 후보 정의 · 이름 전 부모 결정 · 관련 링크 조회 전용 · 렌즈 추출.
- 문서 2 청크 저장 `about`(두 번째 매달림).
- 문서 5 §5.1-6 근거 tier(describes 1·2 → about 3·4 → ref 근처 5) · §5.2 채널 [관련 원문](묶음 `related`).
