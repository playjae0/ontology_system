# PROGRESS — 회차 일지 (살아있는 부분)

> **규칙**(B77): 이 파일은 **최근 3회차**만 싣는다. 회차가 마감돼 개정대장에 반영되면 그 본문은
> `docs/archive/장부/PROGRESS_<범위>.md`로 옮기고 아래 색인에 한 줄만 남는다. 회차 보고의
> 내용 규격은 CLAUDE.md §4(단위 완료·테스트 결과·`git diff core/` 상태·소요) 그대로다.

## 색인 — 옮겨진 회차 (본문은 `docs/archive/장부/PROGRESS_A0~B76.md`)

- A0 (G0) — 레포 상태 회수 + 계수 3종 · 2026-08-07 · **완료**
- G1 + G2 — 저장 계층 · 주소 체계 · 부트스트랩 · 2026-08-07 · **완료**
- G3 — 계약 v2 정합 · 추출 분리 · 게이트 · 2026-08-08 · **완료**
- M2 반입 — 0~2단계 · 2026-08-10 · **완료** (3~4단계는 별도 세션)
- M2 반입 — 3·4단계 · 2026-08-12 · **완료** (G4는 별도 승인)
- M2 후속 — G4 전 정리 · 2026-08-13 · **완료** (G4는 별도 승인)
- G4 0단계 — 판정필요-5 종결 + 장부 정리 · 2026-08-13 · **완료**
- G4 본편 — 2′ 질의 회귀 · 3′ 품질층 · 3.5′ 재인입 회귀 · 2026-08-13 · **완료**
- 20회차 반입 후속 — 하네스 수정 · A-3 재실행 · A-4 관통 · 큐 멱등화 · 2026-08-18 · **완료**
- G5 — n5 I축 도구 4연산 + 전역 재평가 이설 · 2026-08-19 · **완료**
- G6 — 4′ 플랫폼 연동 + 계기판 8종 · n9 지문 스캔 · 2026-08-19 · **완료**
- G6.5 — 계약 미배선 24건 수리 · 2026-08-19 · **완료**
- 21회차 반입 + P1 — n7 파서 공용 코어 · 2026-08-19 · **완료**
- P2 — n8 어댑터 생성 킷 6종 · 2026-08-19 · **완료**
- P3 — n6 구축 모드 등록 파이프라인 · 2026-08-19 · **완료**
- B77 — 정리 회차(자산 짝·같은 기능 한 자리·근거 자리·어서션 감사) · 2026-09-17 · **완료**
- B78 — 상태의 자리·다섯 단 배치·이관 · 파트 폴더·분할 · 코드 지도 · 2026-09-17~18 · **완료**
- B79 — 층 자산은 상태 루트에 · 원본의 자리 · 정적 검사와 스모크 · 2026-09-21 · **완료**
- B80 — 요청의 손잡이 · 임베딩 백엔드 둘 · 원본 자리 이름 · 2026-09-22 · **완료** (본문 `docs/archive/장부/PROGRESS_B80.md`)
- B81 — 인입 화면(값 줄·로그 파일·색·보폭) + B80 후속 · 2026-09-22 · **완료** (본문 `docs/archive/장부/PROGRESS_B80.md`)
- B82 — 뷰어를 세미 플랫폼으로 · 질의 trace · 2026-09-22 · **완료** (본문 `docs/archive/장부/PROGRESS_B80.md`)
  (본문은 `docs/archive/장부/PROGRESS_B77~B79.md`)
- 요약
- 전제 대조표 (§1 9행)
- 실행으로 확인한 것 (완료판정 §3)
- 자체 검출 — 내가 만든 결함 1건
- 회귀가 잡은 것 3건 (수리 중)
- 장부
- 미완
- 요약
- 전제 대조표 (§1 9행)
- 실행으로 확인한 것
- §2-4 대조 — 개정된 자리와 어긋난 지점 12건
- 요청문과 명세가 갈린 자리 2건 — **명세를 따랐다**(§0-1)
- 자체 검출 1건
- 장부
- 미완
- 요약
- 완료판정 10조건
- §2-4 mock 격리 — 요청문 분류를 하나 뒤집었다
- 자체 검출 3건
- 장부
- 미완
- 부록 — 2B 감사 워크플로 결과 반영 (2026-08-25)
- 2A P-D — 조용한 잔가지 6건 (2026-08-26)
- doctor.py — 실패 원인을 화면이 말하게 한다 (2026-08-26)
- 2B 가이드 3종 교체 + export 결함 3건 수리 (2026-08-27)
- `run.py llm-check` 신설 — 게이트웨이 연결 확인 (2026-08-27)
- 생성 프롬프트 v0.5 설치 + 치환 배선 · 가이드 3종 갱신 (2026-08-27)
- 킷 유지 주석을 LLM에 보내지 않는다 + 명세 동기화 (2026-08-27)
- ① LLM 설정 파일 · ② CSV 읽기 (2026-08-27 · 사내 실사용 발)
- 2B 등록 파이프라인 개선 6건 (2026-08-27)
- 후속 2건 — ipqc 전환(신고) · skeleton-confirm 신설 (2026-08-28)
- B26 Unit 스코프(기준선 재수립) · B27 참조 어댑터 전시물 전환 (2026-08-28)
- B29 — 스켈레톤 본문 주입 · 참조 어댑터 few-shot (2026-08-28)
- 등록 2차 개선 — 문답 어휘 · 크기 손잡이 · 하네스 규약 10 · 꼬리표 (2026-08-28)
- B39 — 열 프로파일 · 3단 깔때기 · 템플릿 v0.9 (2026-08-28)
- B40~B42 — 프로파일 보강 3건 · 설정 편의 2건 (2026-08-31)
- B43·B44 — 산문 분할 · 스키마 정합 · 관측 4건 (2026-08-31)
- B45 — 분할 크기 분포를 검수 뷰에 (2026-08-31)
- B45 정정 — 어댑터 경로에도 분할 레벨 상수 (2026-09-01)
- 코드 전체 검토 — 리팩터 4단계 (2026-09-02)
- 구조 진단 아티팩트 반영 — 리팩터 5·6단계 (2026-09-02)
- 등록·인입 개선 5건 (2026-09-02)
- B47 명세 배치 — 판정필요-16 해소 · 가결정 2건 승격 (2026-09-03)
- B48 — 파서 무판독 · 지점 ⑦ 배선 · mock 관문 · 도달 가능성 (2026-09-04)
- B48 후속 — D-113 조정: ⑦ 예산 초과·판정 불가는 문서를 죽이지 않는다 (2026-09-04)
- 후속 3건 — `--resume` 인자 · 검수 뷰 지도 필드 · ⑦ 예산 초과 문면 (2026-09-04)
- B49 · B50 — 판정을 올리면 답할 자리를 준다 (2026-09-07)
- [정정] 40 — `--instruct` 재생성분도 기계 관문을 지난다 · D-79에 `rehearsal` (2026-09-07)
- B51 — prose 검수 뷰 추출 리허설 · `parse run` doc_id · 구조도 배치 (2026-09-08)
- B51-2 — B51 마감 후속: 문면 2 · 경로 1 · 가이드 재작성 (2026-09-08)
- B52 — `query --json` 출력 계약 · `run.py viewer` 검증 뷰어 (2026-09-08)
- B53 — PPT 판독 전면 · ④ = 바이트+맥락 · 슬라이드 렌더 · 기본 PDF 어댑터 (2026-09-09)
- B54 — 골든셋 채점기 · BM-25 상시 대조군 (2026-09-09)
- B55 — 사람이 준 재료가 사라진다 · 감사 2차 A군 10건 (2026-09-09)
- B57 — 감사 2차 B군 코드 반영 (판정 확정본) (2026-09-09)
- B58 ① — 재등록 경로 (H27) · 2026-09-10
- B58 ② — 기계 관문의 범위를 파서 전 구간으로 · 2026-09-10
- B58 ③ — 고정 prose xlsx 어댑터 + 레벨 규칙 ([정정] 46) · 2026-09-10
- B58 ④ — 형태 판정 table/prose (문서 1 C37) · 2026-09-10
- B58 ④-후속 — case 이름과 payload를 명세에 맞춘다 ([정정] 48 ①) · 2026-09-10
- B58 ⑤ — 검수 뷰는 생성이 만든다 + 분할 분포 · 2026-09-10
- B58 ⑥ — 산출 스키마의 계열 분기 · 2026-09-10
- B59 — 기계 관문이 막을 때 사람이 다음 줄을 안다 · 2026-09-11
- B60 ① — 관문은 다시 돈다 · 2026-09-11
- B60 ② — 문답의 확정 요약이 생성의 입력이다 · 2026-09-11
- B62 ①③④ — 시스템이 아는 값은 LLM이 쓰지 않는다 · 2026-09-14
- B62 ② — 대화는 이력(로그), 판단은 정본(패키지) · 2026-09-14
- B63 ①② — 칸 번호 하나 · 지시문 한 자리 · 대장 잠금 (동작 변경 0) · 2026-09-14
- B61 ①~④ — 상태 거부는 원인과 다음 줄을 낸다 · 2026-09-14
- B64 ③①②④ — `columns`는 시스템이 해석한다 · 관문 문면에 열 프로파일 · 2026-09-15
- B64 ⑤ — C38 잠금: 시스템 필드는 LLM 출력과 무관하다 · 2026-09-15
- B65 ①②③ — 하네스가 LLM 산출을 실행 전에 어휘로 거른다 · 2026-09-15
- B65 ⑤④ — 형태 판정이 안 서면 사람에게 묻는다 · 고정 어댑터는 재생성 대상이 아니다 · 2026-09-15
- B66 ①~⑤ — 헤더 지문은 포맷을 보지 않는다 · 미선택 네 갈래 · CSV 전 구간 등가 · 2026-09-15
- B67 ②①③ — 이어하기는 코드가 아니라 판단을 이어받는다 · 열 판정 대장 · 2026-09-15
- B68 ①② — 분할이 무엇을 기준으로 잘랐는지 화면이 말한다 · 2026-09-15
- B69 ①~④ — 좌표 태깅은 표기당 한 번 묻는다 · 예고와 상한 · 2026-09-15
- B70 ①② — mock 자산은 운영 경로에 섞이지 않는다 · 등록부 결손은 막는다 · 2026-09-15
- B71 ①② — 추출 힌트도 mock 자산이다 · 사내 조건 스위트 · 2026-09-15
- B72 ①~④ — 등록이 인입을 막는다 · 인입 화면 · `--step` · 2026-09-15
- B73 ①~⑤ — 후보는 전량이 아니다 · retry는 조건부 · auto는 표시된다 · 2026-09-16
- B74 — 사전 키 = 조회 키 · 판정 대장 · 평가 뷰어 · 행별 `show report` · `ops alias` · 2026-09-16 · **완료**
- B75 — 임베딩은 선택 · 스코프는 하드 필터 · 비용은 실패해도 보인다 · 2026-09-16 · **완료**
- B76 — 모양을 관문이 잠근다 · 대장은 필드 전부를 덮는다 · 예외는 문면으로 죽는다 · 2026-09-16 · **완료**
- B77~B79 — 본문 `docs/archive/장부/PROGRESS_B77~B79.md`
- B80~B82 — 본문 `docs/archive/장부/PROGRESS_B80.md`
- B83 — 시트 역할 관문: 문서마다 한 번 정하고 기록으로 남긴다 · 2026-09-22 · **완료** — 본문 `docs/archive/장부/PROGRESS_B83.md`
- B84 — 뷰어 손보기: 대비 · 검색은 강조만 · 배치 둘 · 상호작용 · 오류 문면 · 2026-09-22 · **완료** — 본문 `docs/archive/장부/PROGRESS_B84.md`
- B85 — 좌표 층의 이름 해방 · 2026-09-22 · **완료** — 본문 `docs/archive/장부/PROGRESS_B85.md`
- B86 — 「사내 모양」 잔여: 상태가 코드 밖이어도 등록부터 뷰어까지 돈다 · 2026-09-23 · **완료** — 본문 `docs/archive/장부/PROGRESS_B86.md`
- B87 — 산문 엑셀의 계층은 시트마다: 번호 군 · 글자 상한 · 규칙 선언 · 2026-09-28 · **완료** — 본문 `docs/archive/장부/PROGRESS_B87.md`
- B88 — 리더의 폭과 그림 이해: 엑셀 그림 → ④ · Word · 등록 재확인 · 가이드·문서 정리 · 2026-09-28 · **완료** — 본문 `docs/archive/장부/PROGRESS_B88.md`

---

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
