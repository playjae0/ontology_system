# PROGRESS — B89 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B89의 본문을 여기로 옮겼다(B92 마감 때).

## B89 — 사내 산문 엑셀 등록 결함: 셀 안 줄바꿈의 locator · 관문 ③④의 시트 역할 · 형태 판정의 시트 역할 (2026-09-29)

순서 ① → ② → ③ → ⑥ → ⑦. 가결정 D-170. 수치의 출처는 전부 **창작 표본**(mock · `tests/fixtures/make_b89.py`)이다 — 메커니즘 확인일 뿐 상수 근거가 아니다([정정] 50).

### 전제 대조표 15행 (origin `3e365e1` 위 `a353b15`)

1~14행 기대값과 전부 일치(516 · 487·538 · 447 · 432 · 0칸 · 100 · 554·453 · 558·559 · 432·552·558 · 38·100 · 611 · 1(141행) · 294 · 256·270). 15행은 **4** — B89 요청문을 커밋한 뒤에 쟀기 때문(커밋 전 3).

### ① 셀 안 줄바꿈 — locator를 행에서 (칸 2.5 · `parser/struct_map.py`)

- `_resplit`: 청크의 `_lines`(행 번호 · 셀 글)로 자른다 — 역매핑 `row_of` 삭제 · 쪼개기 판정은 **행 수**(`len(c["_lines"])`) ·
  `cap_chars`의 두 갈래(487·538 「행 없으면 원래 locator」) 삭제 → 행 목록 없는 청크는 `ValueError`(D-170 ①).
- 표본 `NL01.xlsx`(시트 「사양」 · 짧은 1레벨 절 셋 + 2레벨 제목을 품은 긴 1레벨 절 · 셀 안 줄바꿈 → 청크 R29-R49 = 행 21 · 글 줄 87 · 「1. 기계」 부분 3,365자 · 「해당 없음」 3행).
- **전** (`register generate nl01 process NL01.xlsx --use-basic`): 관문 36 PASS / **2 FAIL** — `[FAIL] G35 중복 1건` ·
  `[FAIL] G52 … source_locator가 문서 내 유일하지 않다 — ['사양!R30']`. 조각 locator: `R2-R9 · R11-R18 · R20-R27 · R29-R49(173자) ·
  R30(2,945자) · R30(419자) · R39(1,205자) · R45-R49` — 중복 `R30` 둘 · 틀린 범위 셋(`R29-R49`는 한 셀, `R39`는 여섯 행).
- **후**: 관문 **39 PASS / 0 FAIL** · `G35 중복 0건` · `G52` PASS. 조각 `R2-R9 · R11-R18 · R20-R27 · R29 · R30-R37 · R38 · R39-R44 · R45-R49`.
- 기존 표본 diff: xlsx·docx 15벌의 산문 어댑터 산출(49조각) **바이트 동일**(vs `a353b15`) · 동작 등가 네 벌 diff 0(아래).

### ② 관문 ③④가 ⑤와 같은 시트 역할로 (칸 1.5 · `kit/run_adapter.py`)

- `raw = read(d)` 뒤 `apply_roles` — 역할 표의 그 표본 몫으로 `parser.pipeline.drop_skipped` · 추출 뒤 `mark_roles`. 역할 표가 없으면 지금과 같다.
- 표본 `SKIP01.xlsx`(「사양」 산문 + 「메모」 한 칸 「상동」 — skip이면 안 봐야 할 시트). `--sheets "1:prose 2:skip"`:
  **전** ③ `G33 조각 4건` · `[FAIL] G38 1건 잔존` · ⑤ 조각 3건 → 관문 FAIL / **후** 「시트 역할 적용 — skip 1장 뺐다」 · ③ `G33 조각 3건` · G38 PASS · ⑤ 3건 → **39 PASS / 0 FAIL**.
  킷 단독(역할 표 없음)은 전과 같이 4건 · G38 FAIL · rc 1.

### ③ 형태 판정이 시트 역할을 따른다 (칸 2.3 · 등록 입구)

- `form.judge_sheets`(시트마다 · 빈 시트 제외) → `samples._kind_of`는 시트 ≥2면 **전부 table일 때만** table.
  `draft.read_sample` 한 자리가 역할 기록을 읽는다 — 형태 판정(`form_block`·`payload_kind_of_samples`)은 prose 시트만, 제안 계산은 skip을 뺀 시트.
  `state.json` `form.sheets` · 화면 「판정 시트 n장(역할 prose)」.
- 표본 `MIX01.xlsx` 시트별 판정: 가격 table · 일정 table · 도면목록 table · 사양 prose → **통합문서 전체 table**(찬성 3 · 반대 0).
- **전**: 플래그 없이 → 형태 판정 table · 시트 관문 없음 → LLM 생성(mock `초안을 얻지 못했다`) · `--sheets "4:prose *:ref" --use-basic` →
  `--sheets` 무시 · `고정 어댑터 거부 — 분할 자명 계열이 아니다`.
- **후**: ⓐ 플래그 없이 → `■ 시트 역할 미정 — MIX01.xlsx (시트 4장…)` + `--sheets "1:ref 2:ref 3:ref 4:prose"` 줄(비대화형 상태 거부)
  ⓑ `--sheets "4:prose *:ref"` → `판정 시트 1장(역할 prose): 사양` · prose 찬성 4 → 「고정 어댑터로 갈까?」(비대화형 → 고정)
  ⓒ 스키마 `use_blocks ['common_core', 'process_coord']` · 관문 **39 PASS / 0 FAIL** · G49 PASS · `form.sheets ['사양']`.
  전 시트가 표인 표본: CP01 등 단일 시트 표본 전부 그대로 table · MIX01에서 사양을 뺀 3시트 사본도 table(관문 없음).

### ⑥ registry 점검 — 조사만 (바꾼 것 0)

루트: 코드 사본 + `ONTO_MOCK_HOME`(코드 밖) + 층 자산 복사. 돌린 것: rfq(prose · RFQ01 · `--use-basic --sheets`) generate→status→confirm ·
ipqc(table · mock 초안 G13·G14 FAIL — 확정 거부가 계약) generate→status→confirm(거부)→`--revise`(거부 — 미등록) ·
toc_report(table · `--no-basic` LLM 초안) generate→review `--instruct`→status→confirm→`--revise`→status. 생긴 것 전부:

| 자리 | 쓰는 곳 | 읽는 곳 (이름 · `.이름(`) | 다시 만드나 | 단 | 의견 |
|---|---|---|---|---|---|
| `doc_types.json` | `core/state/store.py` 원자 쓰기 ← `registry.py:233·273·309` | `store.read(store.DOC_TYPES` 7 · `.lookup(` 4 · `.schema_of(` 7 · `all_doc_types(` 8 — 운영/구축 모드를 가름 | 아니오 | ② | 둔다 |
| `.doc_types.json.lock` · `sheet_roles/.<id>.json.lock` | `store.py:122-125`(flock) | 코드 0 · 이관 제외(`migrate.py:97·174`) | 예(빈 부산물) | 상태 아님 | 둔다(지우는 코드 0) |
| `adapters/<dt>.py` · `schemas/<dt>.json` | 확정 `view._promote`(`view.py:573-595` — 바이트 복사) | 운영 인입(`scan.py:95`) · 등록분 `status`(`view.py:607`) | 아니오 | ② 정본 | 둔다 |
| `review/<dt>/adapter.py` | 고정 `generate.py:589` · 실호출 `draft.py:371` · mock 스탬프 `gate.py:524-528` | `st["adapter"]` 경유 7곳(`gate.py:612` 관문 · `view.py:191` · `confirm.py:40` · `generate.py:197` resume …) | 아니오 | ② 작업 중 | **확정 직후는 정본과 바이트 같다**(rfq 실측) · `--revise` 뒤엔 다음 판 초안이라 다르다(toc_report 실측) — 확정 때 걷을지는 「새 판 초안의 자리」와 함께(B90) |
| `review/<dt>/schema.json` | 고정 `generate.py:609` · 실호출 `draft.py:368` | `st["schema"]` 경유(`ledger.py:298` · 관문 · 확정) | 아니오 | ② 작업 중 | 위와 같다 · **mock LLM 경로엔 없다** — state가 fixture 경로를 가리킨다(toc_report 실측) |
| `review/<dt>/state.json` | `__init__.py:102-104`(`write_text` — 원자 아님) · 10곳 | `_state(` 11 — confirm 전제·status·resume·`--revise` 차단 | 일부(samples·form.by·instructions는 사람) | ② | 둔다 · **원자 쓰기 아님**(CLAUDE.md §5와 대조 과제) |
| `review/<dt>/input_package.json` | `generate.py:444` 등 7 · `gate.py:401` · `interview.py:191` | 10 — 관문 `--package`(`gate.py:616`) · `--revise`/resume의 `.prior_interview(`(`generate.py:416·426`) | system 5키는 예 · `human.hint` 결정은 아니오 | ② | 둔다 |
| `review/<dt>/columns.json` | `ledger.py:230-234` ← `gate.py:614·633` · `view.py:388` · `generate.py:481` | `read_ledger(` 6 · `ledger_path` → 킷 `--ledger`(G4G) | 사람 행은 아니오 | ② | 둔다 · `--revise` 진입은 안 읽고 뒤이은 관문이 이어 쓴다 |
| `review/<dt>/view.json` | `view.py:543` | `confirm.py:63-70`(추출 리허설 요약을 approval로) · 그 외 사람 | 예(`review` — prose는 리허설 비용) | 파생 성격 | 둔다(승인 근거가 approval에 요약된다) |
| `review/<dt>/view.html` | `view.py:545` | 코드 0(경로 표시만) | 예(view.json에서) | ⑤ | 옮긴다 후보(`export/`) — 사람 창구라 둘 수도 |
| `review/<dt>/approval.json` | `confirm.py:80`(`write_text` · 이력 누적) | `confirm.py:72-76` · `registry.orphan_reviews`(`registry.py:197`) | **아니오** | ② 정본 | 둔다 · 옛 `cli.parse build`(`parse.py:366`)도 형식이 다른 것을 쓴다 — orphan 판정이 그것을 승인으로 센다 |
| `review/<dt>/__pycache__/` | 어댑터 import 부산물(`__init__.py:90-94` · 킷) | 코드 0 · 이관 제외(`migrate.py:104`) | 예 | 상태 아님 | 지운다 후보(적재 때 바이트코드 끄기) |
| `sheet_roles/<doc_id>.json` | `sheets.py:50-63`(원자) ← `sheet_gate.py:83·130` | `SH.read(` 2(관문 · `draft.sample_roles_of`) + 표시 2 | **아니오**(사람 답) | ②(명세 명시) | 둔다 — doc_id 키라 **인입 문서 수만큼** 는다 · 등록 표본도 운영 doc_id로 한 건 |
| (이번엔 안 생김) `interview_log.json` | `interview.py:48-68` | `read_log(` 5 — 다음 문답에 이전 라운드(동작) | 아니오 | ② | 둔다 |
| (안 생김) `last_error.json` | `draft.py:225-239`(실호출 예외만) | 코드 0 | 아니오(진단) | ④ | 옮긴다 후보 → `work/logs/` |
| (안 생김) `prompt_rendered.md` | `cli/prompt.py:100-114`(`ONTO_DUMP_PROMPT=1`) | 코드 0 | 예 | ④ | 옮긴다 후보 → `work/` |

### ⑦ 2B 증상표 G4C 행 (`docs/가이드/2B_작업가이드.md` 294행)

- 전: 「스키마의 카테고리·관계·삼항이 층 config 목록 밖이다. 자동 재생성. 그 값이 정말 필요하면 … config.json에 더한다」
- 후: 갈래로 가른다 — **table**: 자동 재생성(지금 문면) · **prose**: 스키마가 고정 틀이라 재생성이 없다 — 고칠 곳은 등록한 층의 config.
  `process_coord` 블록이 `Process`를 부르므로 등록 층이 `Process`를 `categories`에 선언하거나 `relation_patterns`에서 불러야 한다
  (고친 뒤 `python run.py bootstrap` → `register status <dt>`).

### 실행으로 확인한 것

- 어서션 **+9 · 삭제 0** — `test_p1_hier` +3(① 글자 상한 갈래: 조각 글 = locator 행 범위의 온전한 셀 · locator 유일 · validator 0 /
  한 단계 더 쪼개기 갈래: 같은 성질(합성 줄 목록 — 행 86) / 행 목록 없는 청크는 예외) · `test_p1_form` +6(② 역할 표 있으면 ③ 조각 = ⑤ 조각 ·
  없으면 지금과 같다 / ③ 입구 시트마다 판정 / 역할 뒤 prose 시트 판정 + 제안 / 제안 계산은 skip 뺀 시트 / 혼합 표본이 `--sheets` 뒤
  고정 어댑터·관문 PASS·판정 시트 기록). 기대값 넓힌 곳 하나: `test_p1_form` ④ⓐⓑ 표본 이름표에 새 표본 셋.
  ① 두 어서션은 **고치기 전 코드에서 붉었다**(NL01 어긋남 6 · 합성 5 → 후 0).
- 회귀 **1,587 → 1,596/1,596** · FAIL 0 · 클린 2회 동일 · doctor EXIT=0.
- 동작 등가 **네 벌 diff 0**(vs `a353b15` — 그래프 process 95/133 · quality 47/92 · 사전 306 · 큐 107 · 판정대장 399, 창작 표본).
- 검사 6종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13 · 가이드 0 · 코드 지도 재생성 · §7 위반 0 · 자산 해시 갱신(킷).
- `git diff core/`: 없음.
- 구조도: `01_등록_흐름`(입구 시트별 판정 · 역할 뒤 prose 시트 · 킷 ③④) · `02_파싱과_추출`(행이 단위) · `00_칸_대장` 2.3 Code 열.
- 안건: `B86_요청문.md` 지움(살아 있는 B89 + 최근 마감 B87·B88 · B86은 PROGRESS 본문과 함께 archive).
- 소요: 1회차.

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

1. **문서 6 §6.4 141행** 「표로 판정된 표본만 건너뛰고」 → 「시트가 둘 이상이면 시트마다 판정해 비어 있지 않은 시트 전부가 table일 때만 건너뛴다 ·
   역할이 정해진 뒤의 형태 판정은 prose 역할 시트만 · 고정 어댑터 제안 계산은 skip을 뺀 시트」(D-170 ④~⑧).
2. **문서 6 §6.3 쪼개기 단위** — 「한 단계 더 쪼개기」의 판정과 글자 상한의 단위는 **행(셀 하나)**이고, 조각의 locator는 조각의 첫 행~끝 행이다(셀 안 줄바꿈은 행을 늘리지 않는다) · 행 없는 청크는 결함(D-170 ①).

---
