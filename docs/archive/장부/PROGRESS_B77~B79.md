# PROGRESS 보존분 — B77 ~ B79 (2026-09-17 ~ 09-21)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). 아래는 옮겨온 본문이고,
> 살아 있는 장부의 색인에 한 줄로 남는다.

## B77 — 정리 회차: 자산 짝 맞추기 · 같은 기능 한 자리 · 근거 자리 · 어서션 감사 (2026-09-17)

요청문 `docs/안건/B77_요청문.md` · 전제 대조표 8항목 전부 일치 · 순서 ②→④→③→①.
**동작 0 변경**이 이 회차의 바닥이다 — 그래프(process 75/105 · quality 24/44)와 큐 66건이
전·후 동일하다.

### ② 자산 짝 맞추기 — 전시물과 표본

`kit/참조어댑터/cp.{py,json}`이 `CP01.xlsx`에 없는 K열(`개정일` · role: meta)을 내서
G26/G52 FAIL이던 것을 **표본을 맞춰** 해소했다. 고친 표본은 **cp 계열 넷 전부**다
(D-156 ③) — 하나만 고치면 나머지 셋이 지문 불일치가 되어 인입 선택이 끊긴다.
어서션 하나로 상시: 전시물 3쌍이 제 표본으로 관문 전 구간을 **실행으로** 지난다.

### ④ 같은 기능은 한 자리 — 폴더 만들기

| 목적 | 전 | 후 |
|---|---|---|
| `review/<dt>/` | 5곳(`register._dir`·`prompt._dir`·인라인 3) | **1** — `cli/prompt._dir`(D-156 ①) |
| `data/` | 4곳(`init` 2 · `store` 2) | **1** — `store.append_line`(원자 쓰기 부모는 별 목적) |
| `export/` | 3곳 | **1** — `cli/export.out_path` |
| 나머지 7 목적 | 각 1곳 | 그대로 |

### ③ 상태 거부는 **근거 자리**를 말한다

B61 계약에 ④근거(「무엇을 보고 그렇게 판정했나」)를 더했다 — 12곳을 고쳤고
스캐너(`tests/exits_scan.py::no_evidence`)가 **경로 문자열 ≥1**을 상시로 잰다.
`platform doctypes`에 **역방향 대조**(승인 산출은 있는데 등록부에 없는 이름)를 더했다.

### ① 어서션 감사

`tools/assert_audit.py` 신설 — `show(...)`의 **판정식**을 읽어 분류한다(표 전량은
`docs/회귀스위트/자산/어서션_감사.json`). 1,300 호출 자리:
성질 1,061 · 문면:수 148 · 문면:화면 67 · 픽스처 18 · 겹침 6 · **중복 0**.
삭제는 어서션 0건(증명은 D-156 ⑤) · **읽는 곳 0 공개 함수 2건 삭제**
(`register.decisions_of` · `form.table_line` — 세 조건 전부 충족).
픽스처 폴더 reader 표: 전 폴더 ≥1 → **삭제 대상 0**.

### 결과

- 회귀 **1,340 → 1,343/1,343** (순증 3 = ② 1 · ③ 2 · 어서션 삭제 0).
- 재조준 4건(수 불변): 자산에서 파생하도록 — `verify_roundtrip` 헤더 ·
  `test_g6` 지문 일치/선택 근거 · `test_p3` 열 프로파일.
- 검사 4종 통과 · 클린 2회 동일 그래프 OK · 그래프·큐 불변 ·
  상태 거부 스캐너 70곳(수 불변) · 근거 없음 0 · 계약 위반 0.

---

## B78 (1a·1b) — 상태의 자리는 한 모듈이 안다 · 다섯 단 배치 · 이관 (2026-09-17)

요청문 `docs/안건/B78_요청문.md` · 단계 0 → 1a → 1b(진행) · **동작 0 변경**이 바닥이다 —
그래프(process 75/105 · quality 24/44)와 큐 66건이 전·후 동일하다.

### 1a — 자리 소유자 (태그 `B78-1a` · 8c1d2f5)

`core/paths.py` 신설. 상태 경로 상수 26곳(운영)·56곳(테스트)·`mkdir` 9곳이 이 모듈을
지난다. **파일은 옮기지 않았다**(배치 변경은 1b). 어서션 +2.

### 1b — 다섯 단 배치 · mock은 자리로 가른다 · 이관

| 단 | 자리 | 무엇 |
|---|---|---|
| ②등록 | `<루트>/registry/` | `doc_types.json` · `adapters/<dt>.py` · `schemas/<dt>.json` · `review/<dt>/` |
| ③진실 | `<루트>/data/` | `<층>/graph.json` · 사전 · 청크 · 큐 · 문서 대장 · `ops_log` · 골격 스냅샷 (+ 층 등록부 `registry.json` — 아래 미완) |
| ④작업·장부 | `<루트>/work/` | `parsed/` · `extract/` · `ingest_log/` · `struct_maps/` · `gate_rejects` · `*.log` · `migrate.log` |
| ⑤파생·골든 | `<루트>/export/` · `golden/` | 재생성 가능 · 사람이 쓴 문항 |

- **루트**: `ONTO_HOME` → 없으면 `./state`. **`USE_MOCK=1`이면 `./state_mock`**(`ONTO_HOME`을
  무시한다 — 운영 상태에 한 바이트도 쓰지 않는다). `.gitignore`에 둘 다.
- **mock은 자리로 가른다**: 내장 스키마 4종을 `schemas/` → `tests/fixtures/schemas/`로 옮겼다
  (레포 `schemas/`에는 `blocks.json`만). `_builtin()`이 그 자리를 읽는다.
- **등록부·검수 상태의 경로는 자리 기준 상대**다 — `cli/register._rel`(쓰기)과
  `core/registry.at`(읽기)이 한 규칙이다. 상태 루트를 옮겨도 등록부를 고칠 필요가 없다.
- **파서 경계는 주입으로 풀었다**(문서 6 §6.7 우선) — `struct_map.use_dir` ·
  `tagger.use_snapshot`이 **함수**를 받고 `paths.bind_parser()` 하나가 넣는다.
  `kit/run_adapter`는 예외에서 빠졌다: 그 상수는 상태가 아니라 ①자산(`schemas/blocks.json`)이다.
- **이관** `python run.py platform migrate [--from R] [--to H] [--dry-run]` — 복사(옛 폴더 보존) ·
  등록부 경로 재작성 · `work/migrate.log`(무엇을 어디로 · 해시 · 크기).
- **이관 전 실행은 상태 거부**(원인 · 지금 잰 것 · 근거 · 다음 줄) — 판정은 `core/migrate`,
  문면은 `cli/_gate._migrate_message`. 이관 명령 자신은 관문 밖이다.
- 설정 파일 자리 **셋 → 넷**(`$ONTO_HOME/llm.json`) · `mode_line()`에 상태 루트 병기 ·
  `doctor` 첫 줄 `상태 폴더 … · 모드 … · 등록 n종 · 층 k · 문서 m`.
- **체크포인트 재사용은 `doc_hash` + `adapter_version` 둘 다 같을 때만**(`extract.reuse_check`),
  깨지면 버리고 다시 뽑는다.
- `init --fresh`는 `data/`·`work/`·`export/`를 폴더째 지운다 — `KEEP_IN_DATA` 예외 삭제.

### 실행으로 확인한 것

- 회귀 **1,345 → 1,358/1,358** · FAIL 0 (순증 13 = test_g1_g2 +5 · test_onsite +8) ·
  클린 2회 동일 그래프 OK · 상시 어서션(중복 canonical 0) 12종 전부.
- 검사 4종: 문면 0 · 문서간 0 · 미러 0 · 자산 **13 → 14건**(신규 1 = 명세가
  `schemas/pfmea.json`을 이름으로 지목 — 낡은 절, 개정 요청).
- 이관 실측(옛 배치 32파일 → 등록 4 · 진실 10 · 작업 18): `platform doctypes` 1종 ·
  실물 ✓✓ · **역방향 누락 0** · 이관 전 실행 rc=1(거부 문면 4요소).
- `USE_MOCK=1` 변이 — 운영 루트(`ONTO_HOME`)에 감시 파일을 두고 돌려도 파일 목록 불변.

### 허브 판정 반영 (1b 보정)

- 층 등록부 `registry.json`은 **③진실에 남는다 — `data/` 8종**으로 확정(bootstrap 산출 ·
  사람 승인 아님). 문면의 「7종」을 8종으로 고쳤다.
- **락 파일 `.<이름>.lock`은 이관 제외**(원자 쓰기의 부산물 — 옮기면 유령 락이 선다).
  이관 줄의 「진실 10」이 목록 8과 어긋난 원인이 이것이었다(`migrate.log` 실측 — 층 폴더의
  락 2개가 섞였다). 어서션 +1: 이관 대상에 락 0.
- 골든셋(`golden/`) 이관 유지 · **`export/`만 이관 제외**(파생).
- 회귀 **1,358 → 1,359/1,359**.

### 미완

- `cli/register.py` 3,302행(상한 위반 지속 · 분할은 B78-2) — 이 회차 순증 +1행.

---

## B78 단계 2 — 파트 폴더 · 비대 파일 분할 (2026-09-17)

**2a 이동 · 2b 분할**의 두 단계. 동작 등가는 기계가 쟀다 — `046c05d`(pre-B78)와
그래프·사전·큐·판정 대장 **네 벌 diff 0**, 대표 명령 12종 화면 diff 0.

### 2a — core를 파트 폴더로 (이동만)

`core/` 최상위에는 접근 경계 3모듈(`graph`·`dictionary`·`matcher`)과 자리 소유자
(`paths`)만 남는다. 나머지 23파일이 `core/{build,llm,query,state}/`로 갔고
**별칭·재수출은 두지 않는다** — 부르는 쪽이 어느 파트의 코드인지 import 줄에서 본다.

이동이 강제한 본문 줄(import 외) 전수: ROOT 재산정 6 · 레포 루트 계산 2 ·
`glob→rglob` 6 · 코드·시험의 파일 경로 문자열 58 · `.gitignore` 앵커 1
(`state/`가 `core/state/`를 삼켰다).

### 2b — 비대 4파일 분할 (def·class 1:1)

| 전 | 후 | 사라진 def |
|---|---|---|
| `core/llm/llm.py` 957 | gateway 484 · check 261 · struct_map_pass 125 · points 93 · narrow 46 | 0 |
| `core/build/pipeline.py` 1,328 | loop 431 · entry 449 · table 315 · prose 190 | 0 |
| `cli/export.py` 900 | export 476 + **`cli/viewer.html` 436** | 0 |
| `cli/register.py` 3,304 | 패키지 8모듈(draft 608 · gate 659 · generate 587 · view 572 · ledger 428 · interview 246 · __main__ 134 · __init__ 104) | 0 |
| `tests/test_p3.py` 3,484 | 칸별 8스위트 + `p3_common` (어서션 445 불변) | — |

- 형제 모듈은 **모듈로** import한다 — 시험이 갈아 끼우는 자리가 그대로 살아야 한다.
- 모듈 머리말 81종이 **칸 번호로 시작**한다(단계 3 코드 지도의 재료).

### 실행으로 확인한 것

- 회귀 **1,359 → 1,361/1,361** · FAIL 0 · 클린 2회 동일 그래프 OK · doctor EXIT=0.
- 코드 표면: def·class 653 → 654(**사라진 이름 0** · 신설 1 = `_paths_root`).
- 명령 표면(run.py 서브커맨드 · cli 플래그 트리): 1b 대비 **diff 0**.
- 검사 4종: 문면 0 · 문서간 0 · 미러 0 · 자산 19건(낡은 절 — 명세가 옛 경로를 지목).

### 미완 (허브 판정 요청)

- **CLAUDE.md §7 상한 위반이 남는다** — 파일 4종(`tests/test_p1` 1,182 ·
  `tests/test_g6` 1,157 · `kit/run_adapter` 993 · `tests/test_g6_5` 812) ·
  함수 9종(최대 `cli/register/generate.py::cmd_generate` 404행). 요청문의 분할 표에
  없어 손대지 않았다(D-158 ⑦).

## B78 단계 2c·3 — 상한 위반 0 · 코드 지도는 생성물이다 (2026-09-18)

### 2c — 상한 13건 → 0

| 전 (5c23fe1) | 후 |
|---|---|
| `tests/test_p1.py` 1,182 | `p1_common` + 칸별 5(core6 43 · wiring 21 · csv 54 · form 29 · coord 26 = **173 불변**) |
| `tests/test_g6.py` 1,157 | `g6_common` + 칸별 6(platform 20 · scan 16 · batch 21 · registry 10 · ingest 19 · narrow 54 = **140 불변**) |
| `tests/test_g6_5.py` 812 | `g65_common` + 칸별 4(contract 28 · cross 10 · prov 18 · rules 20 = **76 불변**) |
| `kit/run_adapter.py` 993 | 표 `gate_tables` 149 · 검사 `gate_checks` 305 · 화면 `gate_screen` 67 · 실행기 `run_adapter` 532 |
| 함수 9종(최대 `cmd_generate` 404) | 하위 함수 **19개 추출**(`_<원함수>_<단계>`) — 최장 `machine_gate` 119 |

- 코드 표면: **사라진 이름 0** · 신설은 추출 하위 함수 19뿐(`_cmd_generate_{revise,resume,guard,form,package,interview,draft}` · `_probe_{embed,points}` · `_cmd_review_{instruct,rehearsal}` · `_gauges_{smoke,size}` · `_parse_{images,coord}` · `_build_prose_pass1` · `_build_view_anomalies` · `_transfer_edges` · `_ingest_file_select`).
- **전수 실측**: 파일 위반 0 · 함수 위반 0 (운영 93모듈 23,801행 · 시험 포함).

### 3 코드 몫 — 옛 경로 검사 · 코드 지도 생성기

- `docs/회귀스위트/점검_경로.py` 신설(검사 5종째) — 옮긴 이름 34종을 레포 전체에서
  훑는다. 이력(archive·안건·DECISIONS·PROGRESS·실측대장·기준선)과 재생성물·등록
  자산·`prompts/`는 뺀다. **코드·자산 0건** / 문서 115건은 허브 개정 목록이다.
- `docs/구조도/10_코드_지도.md` 신설(258행) — `추출_구조.py`가 AST·파일시스템에서
  뽑는다(손으로 쓰는 문장 0): ⓐ폴더=파트 ⓑ진입점(run.py 21 · `-m` 14) ⓒ접근 경계 4
  ⓓ상태 자리 14 ⓔ크기(위반 0). 생성기가 `ONTO_HOME`·`USE_MOCK`을 고정해 **환경이
  달라도 같은 표**를 낸다.
- 화면 문면 3자리 수리: `cli/register` 사용법 6줄이 **돌지 않는 명령**
  (`python cli/register.py …`)을 가리켰다 → `python -m cli.register` · run.py 위임 줄 ·
  등록부 근거 줄 3곳은 잰 경로(`store.path(store.DOC_TYPES)`)로 낸다.

### 실행으로 확인한 것

- 회귀 **1,361 → 1,362/1,362** · FAIL 0 (순증 1 = 코드 지도 재생성 diff 0 · 삭제 0).
  붉음 확인: 지도에 한 줄을 더하면 그 어서션이 FAIL로 뒤집힌다.
- 클린 2회 동일 그래프 OK · `doctor.py` EXIT=0 · `git diff core/` 없음(커밋 완료).
- 동작 등가 네 벌 **diff 0**(vs `046c05d` — 사전 250 · 대장 196 · 엣지 105/44 ·
  노드 75/24 · 큐 66) · 대표 명령 12종 화면 **diff 0** · 명령 표면 diff 0 ·
  코드 표면 HEAD 대비 증감 0(3의 변경은 전부 문면·주석).
- 검사 5종: 문면 0 · 문서간 0 · 미러 0 · 자산 19건 · **경로 115건**(전부 낡은 절).

### 3 문서 몫 — 허브 (2026-09-18 · hub_30)

- 옛 경로 문자열 **115 → 0**(`점검_경로.py`) · 검사 5종 전부 통과(자산 13건은 층 config 키 vs 명세 — 이전과 같음) · 미러 7쌍 재봉인(C38의 `stamp_system_fields` 자리) · 구조 추출 재생성 diff 0(`추출_구조.py` 자산 접두에 `registry/`·`work/`·`export/`·`golden/`·`tests/fixtures/` 추가).
- 개정: 문서 7 §7.1(코드·상태 두 뿌리 트리 · 자리 규칙 · 이관 · 태그)·§7.5 경로 규약·§7.6-4 클린 범위(단)·§7.8(5단 표 · data 8종 · work · registry 표) · 문서 1·2·5·6·부록·README 경로 · 개정대장 §BO([개정] 155) · CLAUDE.md §2·§5·§7 · 칸 대장(파트=폴더 · Code 열 전부) · 06(0.4 상태 루트 · migrate 행 · 1.5 관문 표 자리 넷 · 경로) · 구조도 01~05·09 · 가이드 §0(5단 표 · 반입 6단계)·§1(설정 넷째 자리)·§5.4·§7 · 인입_이해·역할_판정 · **`가이드/상태_폴더_가이드.md` 신설**.
- 남은 코드 항목 1(반입 문안): `golden_log.json`을 `data/` → `work/`로(로그는 ④단).
- **그 항목 닫음(구현)**: 단을 가르는 자리 하나(`store.WORK_FILES`)에 이름을 얹고, 화면은
  자리를 물어서 말한다(`cli/golden.py`의 `data/` 하드코딩 제거). 실측 —
  `golden score --set tests/fixtures/golden_sample.json` 뒤 파일은
  `state_mock/work/golden_log.json`이고 `data/`에 없다. `data/`는 8종 그대로
  (사전·청크·문서대장·층 등록부·큐·골격 스냅샷 + `<층>/graph.json` 2).
- 반입 뒤 실행: 검사 5종(경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13) · 회귀
  **1,362/1,362** · doctor EXIT=0 · 클린 2회 동일 그래프 · 구조 추출·부품카드·코드 지도
  재생성 **diff 0**.

## B79 — 사내 첫 반입이 드러낸 넷 (2026-09-21)

**출처는 사내 실측이다**(2026-09-21): ⓐ`points.py`의 `import json` 누락으로 `ingest-file`이
파싱에서 죽었다(**회귀 1,362 초록인 채로**) ⓑ가이드 예시 루트를 그대로 쳐서 공용 디스크에
상태가 생기고 새 터미널이 다른 루트를 봤다 ⓒ층 자산이 코드 폴더에 살아서 **코드 교체가
사내 골격을 mock seed 판으로 되돌릴 수 있었다.**

### ① 층 자산은 상태 루트에 산다 — `$ONTO_HOME/layers/` (②등록 단)

- `paths.layers()`가 자리 소유자다. 옛 상수 **6곳**이 그것을 부른다:
  `core/state/bootstrap.py`(2 읽기) · `cli/skeleton.py`(6 자리) · `cli/register/generate.py` ·
  `doctor.py` · `router.py`(`LAYERS` 상수 삭제) · `kit/gate_checks.py`(**`--layers` 플래그** —
  킷은 `core`를 import하지 않는다 · D-160 ①).
- `init --fresh`는 **mock 루트에만** 레포 seed를 심는다(운영 ②등록은 클린 밖 · §7.6-4).
- `USE_MOCK=0`에서 층이 비면 **상태 거부**(원인·지금 잰 것·근거·다음 줄). `platform migrate`가
  `layers/`를 옮기고, 이미 이관한 사람은 `platform migrate --assets --from <옛 코드 폴더>` —
  **다르면 덮지 않고 멈춘다.**
- `platform`의 반환값을 `main`이 삼켜 실패가 exit 0으로 나가던 것을 같이 고쳤다.

### ② 원본 문서의 자리 — `$ONTO_HOME/docs/` (⓪)

- `paths.docs()` 신설 · 인자 없는 `ingest-dir`가 그 자리를 **재귀로** 돈다(경로를 직접 준
  경우는 D-110 그대로) · 비면 상태 거부.
- `doc_registry.source_path`는 **상태 루트 기준 상대**로 기록한다(밖이면 절대) — 비교하는
  곳은 `paths.from_home()`으로 되돌린다. 루트를 옮겨도 「다른 경로」 경고가 0이다.
- 이관은 **파서가 읽는 확장자만** 옮긴다 — 옛 코드 폴더의 `docs/`는 이 레포에서 **명세
  폴더**라 통째로 옮기면 정제본이 원본 자리에 앉는다(D-160 ④).

### ③ 실호출 갈래를 정적 검사와 스모크가 잠근다

- ⓐ `core/llm/points.py`에 `import json`(사내 임시 패치와 같은 줄).
- ⓑ `tests/names_scan.py` — **미정의 이름 0**(표준 라이브러리 AST · 외부 의존 0 · 운영 93모듈).
  변이 확인: 그 한 줄을 빼면 `core/llm/points.py:79 json`으로 붉어진다.
- ⓒ `tests/points_smoke.py` — **9지점 본문 스모크**. 전송 한 곳(`gateway._post`)만 스텁으로
  갈고 본문을 실제로 돌려 반환 계약을 잰다. 9/9 OK · 변이 확인: `import json`을 빼면
  `coord_tag: NameError`.

### ④ 루트 미설정은 화면이 말한다 · 자산은 레포 판인가

- `paths.home_note()` — `USE_MOCK=0` + `ONTO_HOME` 없음이면 모드 줄·doctor 첫 줄에
  「(ONTO_HOME 미설정 — 기본 루트 …)」. 거부가 아니라 표시다.
- `tests/asset_hashes.py` + `docs/회귀스위트/자산/자산_해시.json`(29파일) — doctor가
  `prompts/`·`kit/`·`schemas/blocks.json`·(레포)`layers/`를 대조해 다르면 ⚠.

### 실행으로 확인한 것

- 회귀 **1,362 → 1,392/1,392** · FAIL 0 · 클린 2회 동일 그래프 OK · doctor EXIT=0.
  순증 30 · 삭제 0 (①8 · ②5 · ③13 · ④4).
- 동작 등가 네 벌 **diff 0**(vs `046c05d`) · 화면 12종 diff **4곳(전부 의도)** ·
  코드 표면 **사라진 이름 0**(743 → 755) · 명령 표면 `+--assets` `+--layers`.
- 검사 5종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13.
- **§7 상한**: `tests/test_g1_g2.py`가 834행이 되어 같은 회차에서 나눴다 —
  `g1_common`(56) + `test_g1_g2`(486) + `test_places`(362). 위반 0.

### B79 문서 몫 — 허브 (2026-09-21 · hub_33)

- D-160 9건 확정(④ 포맷 가름 · ③ 관문 예외 셋 포함). 개정: 문서 7 §7.1(⓪원본·②층 행 · 자리 규칙 예외 둘 · 층 자산 관문 · 정본 자산 규율)·§7.6-4(mock/운영 갈림)·§7.8(5단 표·백업 다섯·source_path 표기) · 문서 6 §6.7(하네스 `--layers` · 관문 표 자리) · 개정대장 §BP([개정] 159) · CLAUDE.md §5·§7 · 06 0.4·0.1·0.3·1.5 · 칸 대장 0.1 · 가이드 §0·§2 · 상태_폴더_가이드 §1~§5 · 부품카드 재생성. 검사 5종 통과 · `test_g1_g2` PASS.

