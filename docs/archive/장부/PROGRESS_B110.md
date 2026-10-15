# PROGRESS — B110 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B110의 본문을 여기로 옮겼다(B113 마감 때).

## B110 — 사내 반입 전 고침 셋: 시험이 표준입력을 물려받지 않는다 · 닫힌 화면의 정리는 조용히 · 사람이 멈춘 문서는 흔적이 없다 (2026-10-14)

> 요청문 `docs/안건/B110_요청문.md` · 반입 `4ecabaf`(hub_89 — 문서 6 · 코드 0 · PR #87 병합 뒤 브랜치를 main에서 다시 시작) · 커밋 `65947ba`(① ②) · `27a4ee5`(③ ④) · `3cb4084`(코드 지도) · 마감 커밋.

### 전제 대조표 5행 (`4ecabaf` — 반입 그대로)

1 `438` · `68` / 2 `68` · `69` / 3 `215` · `287` · `219` / 4 셋 다 있음 / 5 `4`(B107 · B108 · B109 · B110) — 기대값 그대로.

### 단위 완료

- ① 표준입력 — doctor · 시험의 하위 프로세스 호출 중 표준입력을 정하지 않은 50곳(doctor 8 · 시험 쪽 21파일 42)에 `stdin=DEVNULL` · 소스 대조(AST) 103호출 중 미지정 0 · pty 도우미 넷은 그대로(표준입력이 pty).
- ② 닫힌 화면 — `_Tee.flush`는 한 번 닫혔으면 아무것도 하지 않는다(쓰기만 멈춤 신호) · 3.13의 끝 정리 트레이스백 0.
- ③ 사람 · 관문의 멈춤 — 되돌림 경계 한 손(`_undo(t0, keep_registry=…)`) · 그래프 · 사전 · 큐 · 청크는 시작 전 · 문서 대장만 남김 · `Stopped` 머리말.
- ④ 가이드 — 런북 단계 3(`--step` q 뒤 · 다시 치면 재사용 · 청크는 그때 다시 선다) · 2B 명령 사전 `--step` 줄 · 구조도 00_칸_대장 · 00_전체_지도 · 03 · 코드 지도 재생성. 런북 단계 0의 doctor 줄 · 2B 증상표에 표준입력 · 3.13 우회 문장은 없었다(정리할 것 0).

### 완료판정 ⓐ ⓑ ⓒ (`tests/test_g6_stop_chunks.py` 출력 그대로 — 표·산문 × 층 둘)

```

■ B110 ① 시험은 표준입력을 물려받지 않는다 — 시험 · doctor의 하위 프로세스 호출(소스 대조)
  [PASS] ⓐ 시험 · doctor의 하위 프로세스 호출 중 표준입력을 정하지 않은 것 0(터미널에서 쳐도 숨은 질문을 기다리지 않는다)  — 호출 103 · 표준입력 미지정 0

■ B110 ② 닫힌 화면의 정리는 조용히 — 쓰기만 멈춤 신호(Python 판 무관)
  [PASS] ⓑ 한 번 닫힌 화면 — 쓰기는 멈춤 신호(ScreenClosed) · 그 뒤 flush · close(끝 정리)는 던지지 않는다  — 쓰기 멈춤 신호 · 다시 쓰기 멈춤 신호 · flush 조용 · close 조용

■ B110 ③ 사람이 멈춘 문서는 흔적이 없다 — --step q · --step-every q (표 · 산문 × 층 둘)
  [PASS] ⓒ --step 관문의 q(표 · 산문 × 층 둘) — 청크 · 그래프 · 사전 · 큐 = 시작 전 · parsed/ 남음 · 산문(구축 안의 관문 — 추출 결과)은 문서 대장 · extract/도 남음 · 표(관문 셋이 구축 전)는 문서 대장에 쓰지 않는다  — 표 · process 멈춤 True · 흔적 시작 전 True · 문서 대장 False · parsed True · extract False · 표 · quality 멈춤 True · 흔적 시작 전 True · 문서 대장 False · parsed True · extract False · 산문 · process 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract True · 산문 · quality 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract True
  [PASS] ⓒ --step-every의 q(판정 도중 · 표 · 산문 × 층 둘) — 청크 · 그래프 · 사전 · 큐 = 시작 전 · 문서 대장 항목 · parsed/ 남음 · 산문은 extract/도  — 표 · process 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract False · 표 · quality 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract False · 산문 · process 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract True · 산문 · quality 멈춤 True · 흔적 시작 전 True · 문서 대장 True · parsed True · extract True
  [PASS] ⓒ 멈춘 뒤 다시 치면 멈추지 않고 끝까지 · 산문은 추출 재사용(LLM 0) · 결과(흔적 · 판정 대장) = 멈추지 않고 넣은 것  — 표 · process(관문) 성공 True · 추출 재사용 True · 같음 True · 표 · process(값마다) 성공 True · 추출 재사용 True · 같음 True · 표 · quality(관문) 성공 True · 추출 재사용 True · 같음 True · 표 · quality(값마다) 성공 True · 추출 재사용 True · 같음 True · 산문 · process(관문) 성공 True · 추출 재사용 True · 같음 True · 산문 · process(값마다) 성공 True · 추출 재사용 True · 같음 True · 산문 · quality(관문) 성공 True · 추출 재사용 True · 같음 True · 산문 · quality(값마다) 성공 True · 추출 재사용 True · 같음 True

==============================================================
전체 결과: PASS — G6.5 완료판정 충족
```

고치기 전(반입 커밋 사본에 같은 시험): ⓐ FAIL(미지정 50) · ⓑ FAIL(`flush 멈춤 신호 · close 멈춤 신호`) · ⓒ 관문 q · `--step-every` q FAIL(산문 둘 「흔적 시작 전 False」 — 청크가 남았다) · ⓒ 다시 치기 PASS.

ⓐ 실행 — 마감 doctor를 **표준입력이 열린 채로**(`python doctor.py < <(sleep 1800)`) 돌렸다: `[  OK ] test_p3_register   73 PASS / 0 FAIL   (12s)` — 표준입력을 닫았을 때(단독 11~12초)와 같다 · 멈춤 0 · 합계 1811/1811.

ⓑ 판마다 — `tests/test_g6_log_pipe.py`의 ⓑ 다섯(출력 그대로):

Python 3.11 — 8/8 PASS

```
  [PASS] ⓑ 읽기 명령 파이프 닫힘 — 트레이스백 0 · 종료 코드 141 · 로그에 멈춤 줄(run.py · python -m cli.* · doctor.py)  — run.py show aliases rc 141 멈춤 줄 · python -m cli.platform queue rc 141 멈춤 줄 · doctor.py --quick rc 141 멈춤 줄
  [PASS] ⓑ 화면에 쓰는 스레드도 닫힌 화면에서 트레이스백 0 — 본 흐름은 멈춤 줄 · 141  — rc 141 · stderr 0줄
  [PASS] ⓑ 쓰기 명령 파이프 닫힘(표 · 산문 × 층 둘) — 트레이스백 0 · 141 · 멈춤 줄 · ③은 셋 중 하나 · 결함 장부에 화면 닫힘 0  — 표 · process rc 141 시작 전 · 표 · quality rc 141 시작 전 · 산문 · process rc 141 시작 전 · 산문 · quality rc 141 시작 전
  [PASS] ⓑ 줄 위치 표본(표 · 산문 × 층 둘) — 전부 셋 중 하나 · 「되돌림」 줄이면 시작 전 · 「저장 뒤 멈춤」 줄이면 끝난 문서 · 종류마다 둘 다 나온다  — 어긋남 0 []
  [PASS] ⓑ 재인입(개정본) 도중에 닫히면 첫 인입 뒤 판 그대로 — 회수(withdraw)가 저장한 층 그래프도 되돌린다(표 · 산문 · 층 둘)  — 표 · process rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True · 산문 · quality rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True
```

Python 3.12 — 8/8 PASS

```
  [PASS] ⓑ 읽기 명령 파이프 닫힘 — 트레이스백 0 · 종료 코드 141 · 로그에 멈춤 줄(run.py · python -m cli.* · doctor.py)  — run.py show aliases rc 141 멈춤 줄 · python -m cli.platform queue rc 141 멈춤 줄 · doctor.py --quick rc 141 멈춤 줄
  [PASS] ⓑ 화면에 쓰는 스레드도 닫힌 화면에서 트레이스백 0 — 본 흐름은 멈춤 줄 · 141  — rc 141 · stderr 0줄
  [PASS] ⓑ 쓰기 명령 파이프 닫힘(표 · 산문 × 층 둘) — 트레이스백 0 · 141 · 멈춤 줄 · ③은 셋 중 하나 · 결함 장부에 화면 닫힘 0  — 표 · process rc 141 시작 전 · 표 · quality rc 141 시작 전 · 산문 · process rc 141 시작 전 · 산문 · quality rc 141 시작 전
  [PASS] ⓑ 줄 위치 표본(표 · 산문 × 층 둘) — 전부 셋 중 하나 · 「되돌림」 줄이면 시작 전 · 「저장 뒤 멈춤」 줄이면 끝난 문서 · 종류마다 둘 다 나온다  — 어긋남 0 []
  [PASS] ⓑ 재인입(개정본) 도중에 닫히면 첫 인입 뒤 판 그대로 — 회수(withdraw)가 저장한 층 그래프도 되돌린다(표 · 산문 · 층 둘)  — 표 · process rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True · 산문 · quality rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True
```

Python 3.13 — 8/8 PASS

```
  [PASS] ⓑ 읽기 명령 파이프 닫힘 — 트레이스백 0 · 종료 코드 141 · 로그에 멈춤 줄(run.py · python -m cli.* · doctor.py)  — run.py show aliases rc 141 멈춤 줄 · python -m cli.platform queue rc 141 멈춤 줄 · doctor.py --quick rc 141 멈춤 줄
  [PASS] ⓑ 화면에 쓰는 스레드도 닫힌 화면에서 트레이스백 0 — 본 흐름은 멈춤 줄 · 141  — rc 141 · stderr 0줄
  [PASS] ⓑ 쓰기 명령 파이프 닫힘(표 · 산문 × 층 둘) — 트레이스백 0 · 141 · 멈춤 줄 · ③은 셋 중 하나 · 결함 장부에 화면 닫힘 0  — 표 · process rc 141 시작 전 · 표 · quality rc 141 시작 전 · 산문 · process rc 141 시작 전 · 산문 · quality rc 141 시작 전
  [PASS] ⓑ 줄 위치 표본(표 · 산문 × 층 둘) — 전부 셋 중 하나 · 「되돌림」 줄이면 시작 전 · 「저장 뒤 멈춤」 줄이면 끝난 문서 · 종류마다 둘 다 나온다  — 어긋남 0 []
  [PASS] ⓑ 재인입(개정본) 도중에 닫히면 첫 인입 뒤 판 그대로 — 회수(withdraw)가 저장한 층 그래프도 되돌린다(표 · 산문 · 층 둘)  — 표 · process rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True · 산문 · quality rc 141 · 첫 인입 성공 · 되돌림 줄 True · 첫 인입 뒤와 같음 True
```

고치기 전 3.13(반입 커밋 사본): 5/8 PASS — ⓑ 읽기 · 스레드 · 쓰기 파이프 셋 FAIL(허브 실측과 같다).

ⓓ 네 벌 — `python tools/four_way.py --base 4ecabaf` rc 0:

```
기준 4ecabaf hub_89 반입 — B109 마감 문서(명세 4·7 · 개정대장 · 이연대장) · CLAUDE.md · B110 요청문 (코
지금 작업 트리 — HEAD 3cb4084 · 커밋 안 한 변경 0
기준 A 넣기 {'CP01.xlsx': '성공', 'CP02_drift.xlsx': '미선택', 'CSV01.csv': '미선택', 'IPQC01.xlsx': '미선택', 'PFMEA01.xlsx': '성공'} · 노드 {'process': 95, 'quality': 47} · 엣지 {'process': 133, 'quality': 92} · 큐 105 · 대장 행 399
기준 B · 노드 {'process': 75, 'quality': 24} · 엣지 {'process': 106, 'quality': 44} · 큐 66 · 대장 행 196
지금 A 넣기 {'CP01.xlsx': '성공', 'CP02_drift.xlsx': '미선택', 'CSV01.csv': '미선택', 'IPQC01.xlsx': '미선택', 'PFMEA01.xlsx': '성공'} · 노드 {'process': 95, 'quality': 47} · 엣지 {'process': 133, 'quality': 92} · 큐 105 · 대장 행 399
지금 B · 노드 {'process': 75, 'quality': 24} · 엣지 {'process': 106, 'quality': 44} · 큐 66 · 대장 행 196
A 넣기 결과 같음 True
A 그래프 process nodes: 기준 95 · 지금 95 · 빠짐 0 · 더함 0
A 그래프 process edges: 기준 133 · 지금 133 · 빠짐 0 · 더함 0
A 그래프 quality nodes: 기준 47 · 지금 47 · 빠짐 0 · 더함 0
A 그래프 quality edges: 기준 92 · 지금 92 · 빠짐 0 · 더함 0
A 사전 같음 True
A 큐: 기준 105 · 지금 105 · 빠짐 0 · 더함 0
A 판정 대장: 파일 2 · 다른 파일 []
A data 파일: 빠짐 [] · 더함 []
B 그래프 process nodes: 기준 75 · 지금 75 · 빠짐 0 · 더함 0
B 그래프 process edges: 기준 106 · 지금 106 · 빠짐 0 · 더함 0
B 그래프 quality nodes: 기준 24 · 지금 24 · 빠짐 0 · 더함 0
B 그래프 quality edges: 기준 44 · 지금 44 · 빠짐 0 · 더함 0
B 사전 같음 True
B 큐: 기준 66 · 지금 66 · 빠짐 0 · 더함 0
B 판정 대장: 파일 6 · 다른 파일 []
B data 파일: 빠짐 [] · 더함 []
전부 같다 · 소요 3초
```

### 가결정 (D-192 — 6건)

표준입력을 닫는 자리와 소스 대조(AST · 모듈 이름 모양) · pty 도우미 넷은 그대로 · 닫힌 화면의 flush는 아무것도 하지 않는다(close도 같이) · 판 시험의 인터프리터(3.12는 스크래치 가상환경 — 시스템 3.12는 PEP 668) · **사람 멈춤은 경계 한 손 — 문서 대장만 남긴다** · 표의 `--step` 관문 셋은 구축 전이라 그 자리의 q는 문서 대장에도 쓰지 않는다. 전문은 `DECISIONS.md` D-192.

### 요청문과 다른 것

- 완료판정 ⓒ 「`--step` 관문에서 q(표 · 산문 × 층 둘) ⇒ … 문서 대장 항목과 체크포인트는 남는다」 — **표는 관문 셋(파싱 · 좌표 · 판정 예고)이 모두 구축 전**(`cli/ingest._step_stops`)이라 그 자리의 q는 인입 검사를 돌리지 않는다: 문서 대장 0 · `parsed/`만 남는다. 구축 안에서 멈추는 표의 자리는 `--step-every`이고, 거기서는 문서 대장 · `parsed/`가 남는다(시험 ⓒ 둘째). 산문은 추출 결과 관문이 구축 안이라 문서 대장 · `parsed/` · `extract/`가 남는다.

### 가이드 · 구조도

- 가이드: `운영_런북.md`(단계 3 `--step` 줄) · `2B_작업가이드.md`(명령 사전 `--step` 줄).
- 구조도: 00_칸_대장(0.3 `cli/_entry.py` — 닫힌 뒤 정리) · 00_전체_지도(B110 행) · 03(사람 · 관문의 멈춤도 같은 손) · 10 · 구조 추출(생성).
- 장부: `DECISIONS.md` D-192 · PROGRESS B107 → `docs/archive/장부/PROGRESS_B107.md` · `docs/안건/B107_요청문.md` 삭제.

### 실행으로 확인한 것

- doctor 직전 사전 점검(B109 교훈): `test_g1_g2` 86/86 · `test_places` 32/32 · 검사 6종 0 · 0 · 0 · 0 · **12** · 0(자산 12는 지난 회차와 같은 판정 대상 · 자산 해시 0건) — 12초.
- **마감 doctor 1회**: `[  OK ] 합계 1811/1811 PASS` · `DOCTOR_DONE rc=0`(324초 · 표준입력 열린 채로) · 「클린 2회 동일 그래프 (완료판정 4)」 · 「레포 정본 자산이 레포 판이다」 · B109 마감 1806 + `test_g6_stop_chunks` 5 · 첫 실행에 FAIL 0이라 1회로 끝났다.
- 어서션 **+5 · 삭제 0 · 기대 변경 0**(`test_g6_stop_chunks` 5 — ⓐ 시험 · doctor의 하위 프로세스 표준입력 미지정 0 / ⓑ 닫힌 화면 — 쓰기는 멈춤 신호 · flush · close는 조용 / ⓒ `--step` q · `--step-every` q(표 · 산문 × 층 둘) — 흔적 시작 전 · 남는 것(문서 대장 · `parsed/` · `extract/`) · 다시 치면 끝까지 · 추출 재사용 · 결과 = 멈추지 않고 넣은 것). 표준입력 50곳 · 사람 멈춤의 큐 · 청크 판은 기존 시험의 기대를 바꾸지 않았다(관련 스위트 단독 — ingest 38 · batch 27 · p3_recover 38 · rebuild 18 · extract_view 6 · log_pipe 8 · p3_register 73 전부 PASS).
- §7: 코드 지도 ⓔ 「운영 모듈 **140** · 합 **36,682행**」 · 「**파일 상한 위반 0** · **함수 상한 위반 0**」 — `run_document` 71행.
- `git diff 4ecabaf -- cli/ core/ parser/ prompts/ kit/`: 2 files changed, 31 insertions(+), 28 deletions(-) — `core/`만 1 file, 27(+), 27(-)(`core/build/entry.py`) · `cli/_entry.py` · 시험 · doctor: 23 files, 243(+), 50(-).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 4 §4.7(184행) 끝에 「**[개정] B110 ③ — 사람 · 관문의 멈춤(판정 보류 · `--step` · `--step-every`)도 같은 판이다**: 그래프 · 사전 · 큐 · **청크**는 문서 시작 전 · 차이는 하나 — **인입 기록(문서 대장)을 남긴다** · 체크포인트(`parsed/` · `extract/`)도 남아 다시 치면 추출 재사용(LLM 0) · 청크는 그때 다시 선다」.
- 문서 7 §7.2(101행) 「**[개정] B109 ② — 둘로 가른다**: 사람 · 관문의 멈춤(판정 보류 · `--step`)은 구축분을 되돌리고 인입 기록은 남긴다 · 그 밖의 예외는 문서 시작 전 판」 → 「**[개정] B110 ③ — 한 손이다**: 어떤 멈춤이든 문서 시작 전 판(그래프 · 사전 · 큐 · 청크 · 재인입 회수 그래프) · 사람 · 관문의 멈춤만 인입 기록(문서 대장)을 남긴다」 · 같은 문단의 「사람이 판정 도중 멈추면 … **그래프·사전·큐**는 그 문서 인입 전으로」에 「· 청크」 · 「`--step` 관문 — 표 문서의 관문 셋(파싱 · 좌표 · 판정 예고)은 구축 전이라 그 자리의 q는 인입 검사를 돌리지 않는다(문서 대장 0 · `parsed/`만)」.
- 문서 7 §7.5-7(213행 회귀 실행 규약)에 「**[개정] B110 ① — 시험 · doctor의 하위 프로세스는 표준입력을 물려받지 않는다**(`stdin=DEVNULL` — 터미널에서 쳐도 숨은 질문을 기다리지 않는다 · 답을 넣는 pty 도우미는 예외 · 소스 대조 0)」.
- 문서 7 §7.8 로그 규격(B109의 「화면이 닫혀도」 문장)에 「· 닫힌 뒤의 flush · 끝 정리는 던지지 않는다 — 멈춤 신호는 쓰기만(Python 판 무관 · [개정] B110 ②)」.
- CLAUDE.md §4(허브 관리) 「회귀 판정 기준은 클린 상태 단독 실행이다」 뒤에 「· 시험의 하위 프로세스는 표준입력을 물려받지 않는다(B110)」 · §5 「구축은 어떤 예외로 끝나도 되돌린다(… B109 — 문서 시작 전 판 …)」에 「· 사람 · 관문의 멈춤도 같은 판 — 인입 기록만 남김(B110)」 · 「화면이 닫혀도 공통 진입 한 자리가 받는다(B109 …)」에 「· 닫힌 뒤의 정리는 조용히 — Python 판 무관(B110)」.
