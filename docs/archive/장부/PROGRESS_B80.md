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

