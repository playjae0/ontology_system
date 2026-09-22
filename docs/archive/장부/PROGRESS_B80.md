# PROGRESS — B80 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B80의 본문을 여기로 옮겼다.

## B80 — 요청의 손잡이 · 임베딩 백엔드 둘 · 원본 자리 이름 (2026-09-22)

**출처는 사내 실측이다**: ⓐ새 모델이 `temperature`를 받지 않아 막혔는데 코드가 그것을
**모든 요청에 고정으로** 실었다(끌 자리 0) ⓑ`EMBED_MODEL`에 로컬 모델 폴더를 넣자
`HTTP 404` — 임베딩을 **게이트웨이 API 하나로만** 알았고, 오류 문면이 **어느 주소를
쳤는지 말하지 않았다** ⓒ원본 자리 이름 `docs/`가 레포의 명세 폴더와 겹쳤다.

### ① `CHAT_TEMPERATURE` · 요청 조립은 한 자리

- 설정 키 신설. **기본은 「싣지 않는다」** — 받지 않는 모델에 실으면 400이고, 받는
  모델은 기본값으로 돈다. 숫자가 아니면 명시적 실패. 우선순위는 **인자 > 설정 > 없음**
  (`gateway.UNSET`이 「미지정」과 「끄라」를 가른다 · D-161 ①).
- **`gateway._payload()` 하나가 조립한다** — `chat()`과 `llm-check`의 탐침 셋(②③④ 왕복 ·
  ⑤ 구조화 출력 · ⑦ 이미지)이 전부 그것을 부른다. `grep '"messages":' core cli` →
  **`core/llm/gateway.py` 1곳**.
- `llm-check` ①설정 줄에 `temperature <값|안 싣는다>` · 재현성 문면 2곳을
  「`CHAT_TEMPERATURE=0`이면 같다 — 기본은 모델 몫」으로.

### ③ 임베딩 백엔드 `gateway | local`

- `EMBED_BACKEND`(기본 `gateway`) · `EMBED_GATEWAY_URL`(없으면 채팅 base). **갈래가
  갈리는 자리는 `embeddings.embed()` 하나**이고 소비부는 `list[float]`만 받는다.
- `local`: `EMBED_MODEL`이 **모델 폴더 경로** · `sentence_transformers`를 **함수 안
  지연 import** · **프로세스당 1회 로드**(`(경로, 모델)` 쌍) · 패키지/폴더 없음은
  `NotConfigured`(문면이 `pip install`·경로를 준다) · 모르는 백엔드 값도 명시적 실패.
- `GatewayError` 문면에 **`POST <url>`** — 404는 「그 주소에 그 경로가 없다」다.
- `llm-check` ⑥과 ⑧ 탐침이 **`embeddings.embed()`를 부른다**(자체 조립 둘 삭제) ·
  ①설정 줄에 `embed <backend> <model|폴더> [url]`.
- `requirements.txt`에 선택 의존 등재 · doctor 선택 의존 점검을 **`find_spec`**으로
  (부르지 않고 본다 — 점검기가 스스로 지연 import 규율을 어기지 않게 · D-161 ⑥).

### ② 원본 자리 `docs/` → `raw/`

- `paths.raw()` · 옛 이름은 `paths.legacy_raw()`가 안다. 옛 이름에 문서가 있으면
  무인자 `ingest-dir`가 **상태 거부**하고 `mv` 줄을 준다(0건으로 끝내지 않는다).
- 선별 기준은 **`reader.SUPPORTED` 하나**(`_is_doc`) — 메모·임시파일은 배치가 아니다.
- **이관에서 원본이 빠졌다** — 이름이 갈리자 B79의 확장자 예외(D-160 ④)가 사라졌다.

### 실행으로 확인한 것

- 회귀 **1,392 → 1,410/1,410** · FAIL 0 · 클린 2회 동일 그래프 OK · doctor EXIT=0.
  순증 18 · 삭제 0 (①6 · ②3 · ③9).
- 동작 등가 네 벌 **diff 0**(vs `046c05d`) · 대표 명령 12종 화면 **diff 0** ·
  명령 표면 diff 0 · 코드 표면 **사라진 이름 1 = `paths.docs`**(②의 개명 · 신설 11).
- 검사 5종: 경로 0 · 문면 0 · 문서간 0 · 미러 0 · 자산 13 · §7 상한 위반 0.

## B80 후속(요청문 개정) · B81 — 인입 화면 (2026-09-22)

### B80 ③ 개정 — 임베딩 비용을 숫자로

`llm-check` ⑥이 local일 때 `<backend> · <n>차 · <device> · 로드 s · 인코딩 ms`를 낸다
(`embeddings.STATS`·`cost_line()`). GPU를 요구하지 않는 대신 **CPU로 돌고 있고 얼마
걸린다**를 화면이 말한다. 어서션 +1(스텁 모델에 `device`를 달아 실측).

### B81 — 값마다 결과 한 줄 · 로그는 파일 · 색은 특이점 · 보폭 손잡이

- **② 로그**: 콘솔 WARNING · 파일 INFO를 `work/logs/<명령>_<날짜>.log`에 **언제나**
  (`log.log_path()` · 자리는 `paths.work`가 안다 · 폴더는 `paths.ensure`). `-v`면 콘솔도
  INFO. 끝 요약에 「로그 <경로>」.
- **③ 색**: `cli/_screen.py` — `paint`·`banner`·`strip_ansi`·`take_flags`. 켜지는 조건 셋
  (tty · `NO_COLOR` 없음 · `--no-color` 없음). 색은 **특이점에만**(new 노랑 · 불확실·
  orphan 빨강 · LLM match 초록 · 요약은 반전).
- **① 값 줄**: `ledger.ON_ROW` 콜백 — 대장 행이 기록될 때 CLI가 한 줄 찍는다. 찍는 것은
  **판단이 갈린 값**(LLM 경로 ∪ new·uncertain·orphan·lowres·gate_reject) · 나머지는 수로만 ·
  `-v`면 전부. 기호는 verdict의 닫힌 표에서.
- **④ 보폭·누적**: `--progress-every N`(기본 25 · 설정 키 `PROGRESS_EVERY`)가 `total//10`을
  대체. 진행 줄에 대장 집계(사전·NEW·불확실·큐)를 더하고 배경 반전으로.

### 실행으로 확인한 것

- 화면 전·후(같은 문서 CP01 · 클린+골격 뒤): **84줄 → 54줄** — INFO 40줄이 파일로 가고
  값 줄 40이 들어왔다. `-v`는 옛 화면 + 값 줄 전량(180).
- 회귀 **1,410 → 1,430/1,430** · FAIL 0 · 클린 2회 동일 그래프 · doctor EXIT=0.
  순증 20 · 삭제 0 (B80 개정 1 · B81 19).
- 파이프 출력에 **ESC 0바이트** · tty 스텁에서는 new 노랑·불확실 빨강 · `NO_COLOR=1`이면 0.
- 검사 5종 초록 · §7 상한 위반 0.

## B82 — 뷰어를 세미 플랫폼으로 · 질의 trace (2026-09-22)

순서 ③ → ① → ② → ④ → ⑤ 그대로.

### ③ 질의 trace — `answer()` 계측 (판단 0 · 새 순회 0)

- `graph.neighbors(…, trace=)`가 **한 바퀴마다** 규칙·도달 노드·쓴 엣지를 적는다 ·
  `expand`·`collect_chunks`가 그것을 받아 넘기고 `link`는 방법(dict|llm_fallback)을 단다.
- `--json`에 `trace{intent, linking, hops, collection, facts, answer, miss}` — 기존 키 불변.
  `used`는 ⑧이 되돌려 준 번호에서(mock은 전부 true).

### ① 서버 — 데이터는 서버가 준다

- `cli/viewer/` 패키지: `server.py`(179) · `data.py`(122) · `static/`. 라우트 여덟, 전부 GET.
  `/api/graph`·`/api/doc/<id>`·`/api/funnel`·`/raw/<경로>` 신설. **쓰기 0**(해시 불변 실측) ·
  127.0.0.1 바인드 · `/raw/`는 `_safe_under()` 하나가 잠근다.

### ② 그래프 — 벤더링 WebGL

- `static/vendor/`에 sigma 3.0.1 · graphology 0.25.4(**npm 레지스트리 tarball** · MIT ·
  LICENSE·출처·sha256 동봉). 외부 URL 0. 렌더러는 `render({nodes, edges, …})` 하나 뒤.
- 색 축 6(기본 category) · 범례(값·수·견본) · 엣지 rel 토글 · 걸침은 **곡선+별색**
  (점선 프로그램이 없다 — D-163 ②) · 필터 5축 · 검색 · obsolete 토글 · 결정적 계층 좌표.

### ④ 질의 콘솔 · ⑤ 연결 현황

- 링킹 칩(사전/폴백) · 경로 배지 · 두 채널 카드 · `kept=false` 회색 · 미스 패널 ·
  답변(mock 표시) · 노드→provenance→`/api/doc`→`/raw/` 원본 열기.
- `/api/funnel`: 문서마다 값→사전·스코프·LLM붙음·NEW·불확실·orphan·큐 + orphan 행 표.

### 실행으로 확인한 것

- 회귀 **1,430 → 1,460/1,460** · FAIL 0 · 클린 2회 동일 그래프 · doctor EXIT=0.
  순증 30 · 삭제 0 (`test_viewer` 29 · test_g4 +1).
- 브라우저 실측(Playwright·Chromium): 콘솔 오류 0 · 그래프 99노드/149엣지 렌더 ·
  질의 3종(단일·극성 3노드·미스) 오버레이 · 연결 현황 표.
- 네 벌 diff 0 · 화면 12종 diff 0 · 코드 표면 사라진 이름 13(전부 이동: `cli/viewer.py`→
  패키지 · 화면 함수 9 → `ingest_screen`) · 신설 21.
- **§7 상한**: `cli/ingest.py` 855 → 631 + `ingest_screen.py` 245 · `answer()` 144 → 79
  (+`_answer_expand` 47 · `_answer_collect` 25). 위반 0.

### 허브 마감 판정 · 문서 몫 (hub_43 · 2026-09-22)

- **가결정 확정**: D-161 ③(`_payload`가 ⑤ 탐침까지) · ⑥(`find_spec`) · D-162 ②(`ONTO_LOG_LEVEL` = 콘솔 레벨) · ③(`PROGRESS_EVERY`는 `gateway.config()` — 설정 파일을 여는 자리는 하나) · D-163 ②(걸침은 곡선+별색 — 규격은 「한눈에 다른 선」이라는 성질) · ③(벤더 출처 npm 레지스트리 tarball — CDN 0은 실행 시 외부 내려받기 금지). 개정대장 §BQ.
- **문서 개정(허브)**: 문서 7 §7.1(`raw/` · `work/logs/` · `cli/viewer/`·`_screen`·`ingest_screen` · 대체 표 임베딩 행 · 자리 규칙 `raw()`)·§7.6-B-1(설정 키 넷 · `_payload` · 오류 URL)·§7.6-B-6(선택 의존 · 벤더링)·§7.8(표 · 시각화 세미 플랫폼 · 로그 규격) · 문서 5 §5.2-6(`trace`) · CLAUDE.md §7 · 칸 대장(파트 5 신설 · 0.3 · 3.1) · 06 · 구조도 03·04 · 가이드 §0·§1·§5·§6·§7 · 상태_폴더 §1~§5 · 인입_이해 §3 · 구조 추출 재생성.
- **B83 발주** — 시트 역할 관문(`docs/안건/B83_요청문.md` · 전제 11행 실행 확인). B84 = 큐 처리 화면.

