# PROGRESS — B118 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B118의 본문을 여기로 옮겼다(B123 마감 때).

## B118 — 숫자와 기준이 보이게: 숫자 세 층 · 점수표 · 위치 칸 둘 · 묻는 자리 · 보강 버림 재생 · 거부 묶음 · 영향 범위 (2026-10-16 · 동작 불변 — 그래프 쓰기는 ⑤ 보강 재생 한 곳)

> 요청문 `docs/안건/B118_요청문.md` · hub_98 반입 `0947fc4` 위 · 마감 커밋 — **사내로 가져갈 커밋**.

### 전제 대조표 5행 (`0947fc4` — hub_98은 문서만이라 `4dfd718`과 같다)

1 `255` · `436` / 2 `158` · `160` · `14` / 3 `259` · `310` / 4 `120` · `438` / 5 `655` · `0` — 기대값 그대로.

### 단위 완료(순서 ④ → ⑤ → ③ → ① → ② → ⑥ → ⑦)

- ④ **묻는 자리 한 함수** `cli/_screen.answer(prompt, kind, eof)` — 입력은 `_screen.ask` 한 줄 · 갈래 넷(`go` 계속/멈춤 · `yes` [y/N] · `Yes` [Y/n] · `text`). 계속은 `c`(`ㅊ`)뿐 · `q` · `quit` · `n`(`ㅂ` · `ㅜ`) · Ctrl-C는 멈춤 · 빈 Enter와 그 밖은 다시 묻는다 · [y/N]은 `y`(`ㅛ`)만 예 · [Y/n]은 Enter · `y` 예 · `n` 아니오 · 그 밖 다시 · Ctrl-C 명령 멈춤 · EOF는 그 자리의 비대화형 값. 인입 화면 네 자리 · 문답 · 등록(문답 · 관문 · 초안 · 검수 뷰 · 생성) · 골격 · 시트 화면 · 문서 좌표 · 관문 도우미가 전부 이 함수를 지난다(`cli/`의 `except (EOFError, KeyboardInterrupt):` 14 → 2 — 남은 둘은 `cli/interview.py` 문답의 「멈춤」 자리). 저장 표지 뒤 머리(표 5~7 · 산문 6~8)에서 멈추면 「이미 저장됐다(되돌리지 않는다)」 · 남은 머리를 묻지 않는다.
- ⑤ **보강 버림 재생** — 대장 열 `proposal {target, rel}` · 재생은 제안 대상을 지금 후보에서 찾아 같은 함수(`_apply`)로 지금 config의 게이트를 다시 돈다(`by: replay` · 마무리 줄 「재생 중 버림→붙음 n」) · 제안 없는 버림은 그대로 · 보강의 게이트 실패도 거부 로그에(출처 「보강」).
- ③ **위치 칸 둘** `core/build/extract_ctx.place`(시트 · 경로 끝 — 표의 행은 `시트!R12`를 가른다) 한 함수를 판정 예고 값 표 · 추출 청크 표가 쓴다 · 폭 = 그 문서의 가장 긴 것(상한 24 · 32) · 좁은 화면에서는 다른 고정 칸을 먼저 줄인다(`_screen.Table(keep=…)`) · 전체 라벨은 명령 로그.
- ① **숫자 세 층** — 맞춤표 위 「요약 — <doc_id> — …」 한 줄(`core/build/reconcile.summary` — 맞춤표의 같은 줄 · 새 계산 0 · `show report`에도) · `python run.py show summary`(새 파일 `cli/show_summary.py` — 층 · 문서별 · 큐 · 보류 · 재연결 · 불확실 · 값) · `--save <이름>` → `golden/summary/<이름>.json` · `--diff <이름1> <이름2>`(`지금` = 지금 판).
- ② **점수표** `python run.py show score <doc_id> [--template] | --all`(새 파일 `cli/show_score.py`) — `golden/score/<doc_id>.csv`(UTF-8 BOM · CP949도 읽는다 · 있으면 덮지 않는다) · 맞음 표시 `=` · `'=` · `o` · `ㅇ` · `맞음` · 재구축 뒤 행 찾기 = 위치키 → 위치 → 시트.
- ⑥ **거부 묶음 · 영향 범위** — 거부 로그 항목에 `source` · `layer` · `python run.py show log gate --by-pattern`(새 파일 `cli/show_gate.py` — (출발, 관계, 도착)별 · 패턴 없음 · 미선언 관계 묶음에 넣을 `relation_patterns` 줄 · 자동 적용 0) · 갈래 표 `core/state/config_scope.py`(새 파일 — 추출 · 구축 · 그 밖) · 인입이 문서 대장에 `config_parts`(칸 지문) · `bootstrap` 끝 줄 「[bootstrap] config 영향 — …」.
- ⑦ 운영 런북(§3 묻는 자리 · 위치 두 칸 · 한 줄 요약 · §4 새 절 「숫자 · 점수 · 거부 묶음」 — mock 실화면) · 2B 작업가이드(§5.3 명령 세 줄 · §7 증상 네 줄) · 구조도 `05_조절_지도.md`(열 「바꾸면 다시 도는 범위」) · `06_손잡이_대장.md`(다섯 줄) · 시험 `tests/test_g6_numbers.py`(새 스위트 18).

### 완료판정 — 마감 한 줄의 요약 화면(두 번째 실행 · 잘리지 않은 출력)

`python tools/close.py --base 0947fc4` — 첫 실행은 FAIL 1(마감 doctor 1927/1931 — `test_g6_batch` 종료 문구 점검 3: `cli/show_score.py` · `cli/show_summary.py`의 `raise SystemExit(` 표지가 다음 줄에 있었고 「상태」 문구에 다음 명령 줄이 없었다 · `test_p3_ledger` ④ⓑ 1: 묻는 자리의 문면 점검이 옛 꼴을 찾았다 — 같은 성질을 실행으로 재게 바꿨다(기대 변경)) · 고친 뒤 규칙대로 한 번 더:

```
마감 한 줄 요약 — 기준 0947fc4 · HEAD 0947fc4 · 커밋 안 한 변경 42
[갱신] 코드 지도 다시 만들기 — 바뀌었다 — 커밋에 넣는다
[PASS] 사전 점검 test_g1_g2 · test_places — 118/118 PASS
[PASS] 문서 검사 일곱 — 문면 문서 10종 · 부정형 문면 791개 · 위반 0건 · 경로 총 0건 — 통과 · 문서간 총 0건 — 통과 · 가이드 총 0건 — 통과 · 자산 총 12건 — 판정 대상 · 미러 미러 쌍 7 · 위반 0건 — 통과 · 모양 취소선 10 · 1500자+ 줄 16 · 표 칸 밖 6 (기준 10 · 16 · 6) · 위반 0건
[PASS] 마감 doctor 1회 — 합계 1931/1931 PASS · 클린 2회 동일 그래프 (완료판정 4) · rc 0
[PASS] 네 벌 — 전부 같다 · 소요 4초 (rc 0)
[PASS] §7 상한 — 파일 위반 0 · 함수 위반 0
[PASS] 자산 해시 — 기록과 같다
FAIL 0 · 소요 483초 · 단계 전문 /tmp/onto_close_ov4moqgf
```

**ⓐ~ⓕ** `python tests/test_g6_numbers.py`(새 스위트 18 · 표 · 산문 × 층 둘):

```
■ ⓐ 숫자 세 층 — 문서 한 줄 요약 · 전체 판 · 전후 비교 (표 · 산문 × 층 둘)
  [PASS] ⓐ 문서 한 줄 요약의 수 = 맞춤표의 같은 줄(결말 · 보류) · 엣지 = 이 문서 몫 (표 · 산문 × 층 둘)  — 표 · process (60, 40, 20, 0, 0, 40) · 표 · quality (91, 52, 38, 0, 1, 92) · 산문 · process (8, 3, 3, 0, 0, 3) · 산문 · quality (3, 3, 0, 0, 0, 0)
  [PASS] ⓐ show summary — 층별(노드 · 골격 · auto · 엣지 없는 노드 · 관계별 엣지) · 문서별(노드 · 엣지 · 보류) = 그래프 · 대장에서 센 수  — CP01 (40, 40, 0) · PFMEA01 (65, 92, 1) · B118SP (5, 3, 0) · B118SQ (3, 0, 0)
  [PASS] ⓐ --diff는 바뀐 줄만 — 넷째 문서 줄이 더해지고 · 보인 줄은 전부 다르고 · 안 보인 줄은 같다 · 화면 「바뀐 줄 n」 = 같은 수  — 바뀐 줄 4 · 같은 줄 14
■ ⓒ 위치 칸 둘 — 시트 | 청크(경로 끝) · 잘리지 않는다
  [PASS] ⓒ 추출 청크 표 · 판정 값 표(-v)의 시트 칸 · 청크 칸 = 그 조각의 (시트, 경로 끝) · `…` 0 (표 · 산문 × 층 둘)  — 표 · process 청크 행 0 · 값 행 180 · 표 · quality 청크 행 0 · 값 행 219 · 산문 · process 청크 행 9 · 값 행 17 · 산문 · quality 청크 행 9 · 값 행 12
■ ⓑ 점수표 — 정답표 초안 · 채점 · 재구축 뒤 같은 표
  [PASS] ⓑ --template CSV의 행 = 대장의 개체 행 · 채운 표로 맞음 3(= · ㅇ · o) · 틀림 2(틀린 이름) · 빈칸 나머지 (표 · 산문)  — 표 · process (3, 2, 55) · 산문 · process (3, 2, 3)
  [PASS] ⓑ 재구축 뒤 같은 표로 같은 수(위치 · 표기로 맞춘다) · show summary에 정답률 칸  — 표 · process (3, 2, 55) · 산문 · process (3, 2, 3)
■ ⓓ 묻는 자리 한 함수 — 계속은 c(ㅊ)만 · 멈춤 q · ㅂ · Ctrl-C · 그 밖은 다시 묻는다
  [PASS] ⓓ c · ㅊ만 계속 — 관문 전부를 c와 ㅊ로 지나면 끝까지 = 멈추지 않고 넣은 것 (표 · 산문 × 층 둘)  — 표 · process 관문 7 · 표 · quality 관문 7 · 산문 · process 관문 8 · 산문 · quality 관문 8
  [PASS] ⓓ 저장 전 관문 전부(process — 관문마다 · quality — 판정 예고)에서 ㅂ · Ctrl-C · q는 멈춤 — 흔적(그래프 · 사전 · 큐 · 청크) = 시작 전  — 19회 · 어긋남 []
  [PASS] ⓓ 빈 Enter · 모르는 답은 다시 묻는다(계속으로 읽지 않는다) — 같은 관문에서 세 번 묻고 ㅂ에서 멈춤 (표 · 산문)  — [('표 · process', True), ('산문 · process', True)]
  [PASS] ⓓ 저장 뒤 관문의 멈춤 — 「이미 저장됐다(되돌리지 않는다)」 · 남은 머리는 묻지 않는다 · 문서는 끝까지(= 멈추지 않고 넣은 것)  — 묻는 줄 5
  [PASS] ⓓ y/N — ㅛ만 예 · Enter · n · Ctrl-C 아니오 / Y/n — Enter · ㅛ 예 · ㅜ 아니오 · 모르는 답 다시 · Ctrl-C 명령 멈춤 / EOF = 그 자리의 비대화형 규칙 / 글 — Ctrl-C None  — [True, False, False, False, True, True, False, True, '올림', 'EOF', None]
  [PASS] ⓓ cli/의 입력은 한 자리 — input()은 _screen.ask 하나 · _screen.ask를 부르는 자리 0(밖) · answer가 그것을 부른다  — input ['cli/_screen.py'] · 밖의 ask []
■ ⓔ 연결 보강 버림의 재생 · ⓕ 거부 묶음 · 바꾸면 무엇이 다시 도나
  [PASS] ⓔ 패턴 밖 제안은 버림 — 대장 link 행에 제안(대상 · 관계) · 거부 로그 출처 「보강」  — 제안 [{'target': '노칭::모터 회전수', 'rel': 'part_of'}]
  [PASS] ⓕ 거부 묶음의 삼항별 수 = 거부 로그에서 센 수 · 패턴 없음 묶음엔 넣을 줄  — ('Property', 'part_of', 'Unit') 1
  [PASS] ⓔ 패턴 그대로면 재구축(재생 · LLM 0)에서 다시 버림  — 버림 1 · 호출 0
  [PASS] ⓔ 제안 줄을 config에 넣고 재구축 — 그 버림이 LLM 0으로 붙는다(대장 attached · by replay · 그래프에 그 관계 엣지)  — 붙음 1 · 호출 0 · 버림→붙음 1 · 대장 1
  [PASS] ⓕ 패턴만 바꾸면 bootstrap 끝 줄 「재구축 때 LLM 0으로 다시 판정」 · 그 묶음이 재구축 뒤 0  — [bootstrap] config 영향 — 재구축 때 LLM 0으로 다시 판정: 문서 2(바뀐 칸 process.relation_patterns) · python run.py rebuild
  [PASS] ⓕ 정의문을 바꾸면 「추출 다시 — 문서 n · config_version을 올린다」(산문 문서만 센다)  — [bootstrap] config 영향 — 추출 다시: 문서 2(바뀐 칸 process.categories) · config_version을 올린다(올리지 않으면 옛 추출을 쓴다)
전체 결과: PASS — G6 완료판정 충족
```

- ⓒ 표 문서의 「청크 행 0」은 표 문서에 추출 청크가 없어서다(값 표의 행만 잰다).
- ⓖ 네 벌(기준 `0947fc4` — 마감 한 줄 단계 3 전문에서):

```
A · C 넣기 결과 같음 True
A 판정 대장: 파일 2 · 다른 파일 []
B 판정 대장: 파일 6 · 다른 파일 []
C 그래프 process nodes: 기준 53 · 지금 53 · 빠짐 0 · 더함 0
C 그래프 process edges: 기준 91 · 지금 91 · 빠짐 0 · 더함 0
C 판정 대장: 파일 2 · 다른 파일 []
전부 같다 · 소요 4초
```

  mock 표본의 보강에는 버림 행이 없어 C도 같다(요청문 ⓖ 「⑤는 버림 행이 없으면 FOUR_SAME」) · 버림 → 붙음은 ⓔ가 사본에서 잰다.

### 명세 패치 — `docs/안건/B118_명세패치.md`(다섯 항목 · 구현 세션은 `--check`만)

```
■ 명세 패치 점검 — docs/안건/B118_명세패치.md
[PASS] docs/spec/4_쓰기절차.md §4.7-5 연결 보강 — 버림의 재생
[PASS] docs/spec/7_구현규격과검증.md §7.5-7 회귀 실행 규약 — 묻는 자리
[PASS] docs/spec/7_구현규격과검증.md §7.8 로그 규격 — 문서 한 줄 요약 · 전체 판 · 점수표 · 거부 묶음 · 영향 범위
[PASS] docs/spec/7_구현규격과검증.md §7.8 산출물 표 — ⑤ 행(golden 아래 정답표 · 스냅샷)
[PASS] docs/spec/부록_용어.md 용어 — 문서 한 줄 요약 · 전체 판 · 점수표 · 유닛 이하 비율 · 거부 묶음 · 영향 범위
[PASS] 사본 적용 뒤 문서 검사 일곱 — 문면 0 · 경로 0 · 문서간 0 · 가이드 0 · 자산 0 · 미러 0 · 모양 0 (그대로)
결과: 통과 · 쓰기 0(점검)
```

### 어서션 증감 — +18 · 기대 변경 3 · 삭제 0

`tests/test_g6_numbers.py` 18 — ⓐ 3(요약 = 맞춤표 / show summary = 그래프 · 대장 / `--diff` 바뀐 줄만) · ⓒ 1(시트 · 청크 끝 · `…` 0) · ⓑ 2(초안 행 = 개체 행 · 채점 / 재구축 뒤 같은 수) · ⓓ 6(c · ㅊ 끝까지 / 저장 전 멈춤 흔적 0 / 다시 묻기 / 저장 뒤 멈춤 / y/N · Y/n · EOF · 글 / 입력 한 자리) · ⓔ 3(버림에 제안 · 출처 보강 / 그대로면 다시 버림 / 넣으면 LLM 0으로 붙음) · ⓕ 3(삼항별 수 = 로그 / 패턴만 → LLM 0 / 정의문 → 추출 다시). 기대 변경 — `test_g6_extract_view` ⓑ(추출 표 열이 하나 늘어 160칸에서 잰다 · 개체 칸 인덱스) · `test_g6_diag` ⓘ(위치 두 칸) · `test_p3_ledger` ④ⓑ(문면 → 실행: EOF 예 · `ㅜ` 아니오 · Enter 예).

### 가결정 — D-200(9건)

묻는 자리의 꼴 · 보강 버림의 제안 · 위치 두 칸 · 한 줄 요약의 재료 · 전체 판의 재료와 스냅샷 자리(`golden/summary/` — 요청문은 ④단이었으나 재구축의 기본 fresh가 ④를 지워 기준선이 사라진다) · 점수표 · 거부 묶음 · 영향 범위의 자리(문서 대장 `config_parts`) · 시험의 답 넣기.

### `git diff core/` · 소요

`git diff 0947fc4 -- core/ parser/` — 파일 7 · +120 · −27(`core/build/` extract · extract_ctx · gate · ingest · ledger · reconcile · reinforce) + 새 파일 `core/state/config_scope.py` · parser 0 · 그래프 쓰기 경로의 변경은 `reinforce` 재생 하나 · 마감 한 줄 483초(doctor 포함).
