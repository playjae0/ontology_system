# 온톨로지 시스템 — 사내 문서에서 지식 그래프를 세우고 질문에 답한다

사내 문서(관리계획서·PFMEA·검사 성적서·보고서…)를 읽어 **공정 지식 그래프**를 만들고,
그 위에서 질문에 **출처와 함께** 답한다. 답의 근거는 두 채널이다 — 그래프 사실과 문서 원문.

**현재: 국면 1 완료 (2026-08-20).** 외부에서 mock으로 전 기능을 구현·검증했다.
다음은 국면 2 — 사내 이식이다.

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
platform · scan · parse · register`.

## 환경

| | |
|---|---|
| Python | **3.9+** (개발·검증은 3.11) |
| 코어 의존 | **없다.** `core/`는 표준 라이브러리만 쓴다 — 폐쇄망에서 설치 없이 돈다 |
| 파서 의존 | `openpyxl` · `python-pptx` (xlsx·pptx 읽기 전용) |
| 선택 | `orjson` (직렬화 가속 — 없으면 표준 json 폴백) |
| 네트워크 | **불필요.** `USE_MOCK=1`(기본)에서 전 경로가 로컬로 돈다 |

## 무엇이 진짜고 무엇이 mock인가

**전부 진짜다 — 데이터만 창작이다.** 파이프라인·계약·판정은 실물이고, 들어 있는 문서와
공정 체계가 창작 표본이다. 사내 유래 정보는 이 레포에 **한 글자도 없다**.

LLM이 붙을 자리 5곳은 비어 있고 규칙 폴백이 대신한다(`grep -rn HOOK core/ parser/ cli/`).
**없어도 전 파이프라인이 돈다** — 추출·판정의 정밀도만 규칙 수준일 뿐이다.

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
tests/          회귀 10종 (423 PASS)
docs/           정본 — 틀 · 불변식 카드 · 용어 대장 · CH1~CH7 · 파서 명세 · 증분0
```

## 읽는 순서 (문서)

1. `docs/CH1_기반.md` — 목적 · PoC 범위 · **불변 원칙 P1~P7**
2. `docs/00_틀_확정본.md` — 돌아오는 기준점
3. `docs/00_불변식_카드.md` — 압축 검사기 (설계가 어긋나면 여기서 걸린다)
4. `docs/증분0_구현.md` §3 — 단위별 정의와 완료판정
5. `CLAUDE.md` — 세션 진행 규칙 · 판본 기준점

장부 둘: `DECISIONS.md`(가결정 82건) · `BLOCKERS.md`(멈춤 0). 진행 이력은 `PROGRESS.md`.

## 설계 원칙 (P1~P7 요약 — 정본은 CH1)

| | |
|---|---|
| **P1** | 단계 간 결합은 **파일 계약(JSON)**으로만 |
| **P2** | 골격·유형은 **사람이 고정**, 인스턴스는 자동 생성 |
| **P3** | 코어는 최소·안정, **사람이 전부 파악** |
| **P4** | **id 불변**, 동의어 사전이 영속 지식 |
| **P5** | 진실 = **그래프 + 청크 원문**(전 청크 보존) |
| **P6** | 질의는 **읽기 전용** |
| **P7** | **측정이 복잡도를 정당화한다** — 근거 없는 구조 선반영 금지 |
