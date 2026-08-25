# 온톨로지 시스템 — 사내 문서에서 지식 그래프를 세우고 질문에 답한다

사내 문서(관리계획서·PFMEA·검사 성적서·보고서…)를 읽어 **공정 지식 그래프**를 만들고,
그 위에서 질문에 **출처와 함께** 답한다. 답의 근거는 두 채널이다 — 그래프 사실과 문서 원문.

**현재: 국면 2A 진행.** 국면 1(mock 전 기능 구현·검증)은 2026-08-20에 닫혔고
(태그 `phase1-complete`), 지금은 명세↔코드 갭을 메우며 실 모델을 연결하는 중이다.

---

## 3분 만에 확인하기

```bash
python doctor.py          # 환경 · 회귀 10종 · 현재 상태 · 다음 할 일  (약 20초)
```

이 한 줄이 **"가져온 것이 온전한가"와 "다음에 무엇을 해야 하는가"**를 실측해서 알려준다.
설명을 읽기 전에 이것부터 돌려라. 문제가 있으면 `[ 필요 ]`로 뜬다.

```bash
python doctor.py --env    # 환경만 (반입 직후 첫 확인)
python doctor.py --quick  # 회귀 생략 (느린 기계)
```

셋이 답하는 것이 다르다 — **README**는 "어떻게 시작하나", **`doctor.py`**는 "이 클론의
지금 상태", **[`구현현황.md`](구현현황.md)**는 "무엇이 어디까지 되어 있고 무엇을 언제
업데이트하나". 사내에 무엇이 반영돼 있는지는 마지막 것을 본다.

## 돌려보기

```bash
python run.py init --fresh                # 클린 상태 (이것이 "클린"의 정의다)
python run.py all                        # 골격 심기 + mock 문서 전량 인입
python run.py query "노칭 다음 공정은?"    # 질의 4단
python run.py show tree                  # 골격 트리 (텍스트)
python run.py show node "노칭 정밀도"      # 노드 하나 전부 — 값·출처·연결
python run.py platform queue             # 수정 큐 (닫힌 20종)
python run.py gauges                     # 계기판 8종
python run.py export cypher              # Neo4j용 (파생물 — 진실은 data/의 JSON이다)
```

**결과는 `data/`의 JSON**이고 시각화 없이 전부 텍스트로 본다 — `run.py show` 7종.
어디에 무엇이 떨어지는지는 [`산출물_지도.md`](산출물_지도.md).

`run.py`가 단일 진입점이고 전 단계가 CLI + 파일 입출력이다 — 플랫폼은 이것을
subprocess로 부른다. 하위 명령: `bootstrap · ingest · all · query · ops · gauges ·
platform · scan · parse · register · show · export`.
`init`이 클린의 단일 정의다 — 회귀 규약과 멱등성 판정이 같은 바닥을 쓴다.

## 환경

| | |
|---|---|
| Python | **3.10+** (개발·검증은 3.11) — `sys.stdlib_module_names`를 쓴다 |
| 코어 의존 | **없다.** `core/`는 표준 라이브러리만 쓴다 — 폐쇄망에서 설치 없이 돈다 |
| 파서 의존 | `openpyxl` · `python-pptx` — **선택**이다(지연 import). 없어도 `USE_MOCK=1` 전 경로가 완주한다 |
| 선택 | `orjson` (직렬화 가속 — 없으면 표준 json 폴백). 전량은 `requirements.txt` |
| 실 모델 | `USE_MOCK=0` + `LLM_GATEWAY_URL 등` 4종. 미설정이면 **명시적 실패**(조용한 폴백 없음) |
| 네트워크 | **불필요.** `USE_MOCK=1`(기본)에서 전 경로가 로컬로 돈다 |

## 무엇이 진짜고 무엇이 mock인가

**전부 진짜다 — 데이터만 창작이다.** 파이프라인·계약·판정은 실물이고, 들어 있는 문서와
공정 체계가 창작 표본이다. 사내 유래 정보는 이 레포에 **한 글자도 없다**.

**LLM 지점 8종은 골조가 서 있고 설정만 비어 있다** — 각 지점이
`if USE_MOCK: <mock> else: <실호출>`로 갈리고 두 갈래가 같은 반환 계약을 지킨다.
연결은 환경변수 4종(`LLM_GATEWAY_URL`·`LLM_API_KEY`·`CHAT_MODEL`·`EMBED_MODEL`)
+ `USE_MOCK=0`이고 **코드 수정은 0**이다. `doctor.py` ④절이 8/8을 매번 실측한다.
**USE_MOCK=1에서는 없어도 전 파이프라인이 돈다** — 정밀도만 규칙 수준일 뿐이다.
미설정 상태의 `USE_MOCK=0`은 조용히 mock으로 떨어지지 않고 **명시적으로 실패한다**.

## 사내 이식 — 권장 순서

`doctor.py`의 ④절이 각 단계의 현재 상태를 실측해 보여준다.

1. **골격 seed 교체** ← 첫 작업. `layers/process/skeleton.json`을 사내 공정 체계로 바꾸고
   `python run.py bootstrap`. **코드는 한 줄도 안 바뀐다** — seed는 데이터다.
2. **doc_type 등록** — 표본 2부로 구축 모드 3단:
   `run.py register generate <이름> <층> <표본...>` → `review` → `confirm --by <승인자>`.
   검수 뷰 HTML이 `review/<이름>/view.html`에 나온다 — 브라우저로 열어 승인한다.
3. **실문서 인입** → `run.py query`로 답이 서는지 확인
4. **계기판 첫 측정** — `run.py gauges`. 이 수치가 이후 도입 판정(P7)의 근거가 된다.
5. **LLM 훅 연결** — 사내 게이트웨이가 서면. 급하지 않다(4번까지 없어도 된다).

## 구조

```
run.py          단일 진입점 (전 단계 CLI + 파일)
doctor.py       사내 이식 점검기
core/           에이전트 코어 — 인입·추출·판정·게이트·질의·I축 도구  (외부 의존 0)
parser/         파서 공용 코어 6종 + 구조 지도 + 기본 어댑터        (openpyxl·python-pptx)
cli/            창구 — query · ops · platform · scan · parse · register
kit/            어댑터 생성 킷 6종 (외부 전달물 — 사내 반입 폴더)
layers/         층 선언 — config.json + skeleton.json  (코드 아님, 데이터)
schemas/        doc_type 매칭 스키마 · 공용 블록
mock/           창작 표본 — raw 문서 10종 · 계약 JSON · fixture
tests/          회귀 11종 (461 PASS)
docs/spec/      **정본 명세 11종** — 0 기반·1 금지와불변·2 계약·3 구조·4 쓰기·5 읽기·
                6 파서와구축모드·7 구현규격 + README·부록_용어·개정대장
docs/회귀스위트/  명세 문면 기계 점검 + 자산
```

## 읽는 순서 (문서)

**명세는 `docs/spec/` 11종뿐이다.** 옛 챕터군(CH1~CH7·틀·카드·증분0·파서 명세)은
정제본으로 통합돼 제거됐다 — 돌아갈 좌표는 태그 `phase1-complete`다.

1. `docs/spec/README.md` — 11종의 지도와 소유 경계
2. `docs/spec/0_기반과원칙.md` — 목적 · 범위 · **불변 원칙 P1~P7**
3. `docs/spec/1_금지와불변.md` — 압축 검사기 (설계가 어긋나면 여기서 걸린다)
4. `docs/spec/7_구현규격과검증.md` — 코드 배치 · id 산식 · 완료판정 · 산출물 표
5. `CLAUDE.md` — 세션 진행 규칙

**명세가 답하지 않는 지점은 추측으로 메우지 않는다** — `BLOCKERS.md`에 신고하고 멈춘다.
장부 둘: `DECISIONS.md`(가결정) · `BLOCKERS.md`(멈춤). 진행 이력은 `PROGRESS.md`.

## 설계 원칙 (P1~P7 요약 — 정본은 `docs/spec/0_기반과원칙.md`)

| | |
|---|---|
| **P1** | 단계 간 결합은 **파일 계약(JSON)**으로만 |
| **P2** | 골격·유형은 **사람이 고정**, 인스턴스는 자동 생성 |
| **P3** | 코어는 최소·안정, **사람이 전부 파악** |
| **P4** | **id 불변**, 동의어 사전이 영속 지식 |
| **P5** | 진실 = **그래프 + 청크 원문**(전 청크 보존) |
| **P6** | 질의는 **읽기 전용** |
| **P7** | **측정이 복잡도를 정당화한다** — 근거 없는 구조 선반영 금지 |
