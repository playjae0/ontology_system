# PROGRESS — B108 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B108의 본문을 여기로 옮겼다(B111 마감 때).

## B108 — 별칭 대장(쌓인 별칭이 재구축에서도 처음부터 쓰인다) · 가이드 개편(운영 런북 신설 · 2B 슬림화) (2026-10-14)

hub_87 반입(`c751670` — origin `1263c6d`(PR #85 병합) 위 · 코드 0) 위 · 순서 ①(`68e6d47` — 대장 · 쓰는 손 · bootstrap 싣기 · 처음 채움 · 거두기 · 화면 · 시험) → ②(`3748cd7` WIP · 마감 커밋 — 런북 · 2B · 걸어가기 · 상태 폴더 가이드 · 구조도 · 장부).

### 전제 대조표 6행 (`c751670` — 반입 그대로)

1 `223` / 2 `177` · `4` / 3 `74` · `117` / 4 `0` / 5 `692` / 6 반입 뒤 `4`(B105·B106·B107·B108) — 전부 기대값과 같다.

### 단위 완료

- **① 별칭 대장**(칸 0.3 · 2.8) — ③ `data/alias_book.json` · `core/state/alias_book.py`: 쓰는 손 하나 `attach`(인입 · `ops alias`의 `Builder._register` · 개명 · 이관 · 병합 · 분리가 부른다 — 노드 별칭을 붙이는 자리는 이 함수와 seed 손뿐) · 같은 표기 · 같은 대상이면 한 항목(문서 · 횟수만) · 연산이 이름을 바꾸면 대상 이름이 같이 간다(`retarget`) · **bootstrap이 골격 대상 별칭을 먼저 싣고(노드 · 사전) 스냅샷을 만든다 — 스냅샷 별칭 = seed + 대장**(`load_skeleton` · `snapshot_aliases`) · 대상 canonical이 골격에 없으면 「대상 없음」(대장은 남는다) · 처음 채움 `backfill`(공통 진입 — 대장 파일이 없을 때 · 재구축 계획 — fresh 앞) · 거두기 `ops alias-reject`(계획 먼저 · 비대화형은 계획만 · 다시 붙이지 않는다 · 재생 손) · 화면 `show aliases` · 재구축 끝 줄 「별칭 대장 n · 그래프에 있음 m · 없음 k」 · 기본 fresh 보존 다섯째(`init.kept()`). 판정은 그대로다(사전 → 재생 → LLM — 대장은 판정을 대신하지 않는다).
- **② 가이드 개편** — `docs/가이드/운영_런북.md` 신설(단계 0~7 · 할 일 → 칠 명령 → 확인할 것(화면 줄) → 막히면 — 임시 mock 상태 루트에서 처음부터 끝까지 실제로 쳐서 옮겼다) · `2B_작업가이드` 명령 사전 + §7 증상표 + 부록 A 처음 설치(692 → 359행 · 머리 가이드 목록 첫 줄이 런북) · `걸어가기_설비문서`(일반 등록·인입·확인 절차 → 런북 링크 · 설비 문서 특유만) · `상태_폴더_가이드`(③ 9종 · 보존 다섯) · 링크(README · 구조도 00 · 인입_이해) · 가이드 검사의 깨끗한 자리(2B 「시작하기」 → 런북 전체).

### 완료판정 (`tests/test_g6_alias_book.py` 출력 그대로 — 표·산문 × 층 둘)


    ■ B108 바닥 — 표 · 산문 × 층 둘 (B108TP · B108TQ · B108SP · B108SQ) → 쓰는 문서 (B108UP · B108UQ)
      첫 인입 4문서 · 사람 연산 6건 · 대장 {'total': 9, 'skeleton': 6, 'rejected': 0}

    ■ B108 ① 별칭 대장 — 쓰는 손 하나 · 이름으로 · 같은 별칭은 한 항목
      [PASS] ⓐ 인입의 LLM 매칭(골격 대상 — 표·산문 × 층 둘) · ops alias(골격 층 둘 · 엔티티) · 개명 · 병합이 만든 seed 밖 별칭이 대장에 이름으로(층 · canonical · 출처) · 골격 대상 표시 · LLM 매칭은 처음 문서  — 대장 9항목 · 기대 9 중 빠짐 0
          B108 적층 라인 → 스태킹::적층 (process) · LLM 매칭 · 골격 · 문서 ['B108TP'] · 1회
          B108 타발 공정 → 노칭::노칭 타발 (process) · LLM 매칭 · 골격 · 문서 ['B108SP'] · 1회
          노칭::B108 관리 가 → 노칭::B108 관리 가 개명 (process) · 개명 · 엔티티 · 문서 — · 1회
          B108 적층 사람 → 스태킹::적층 (process) · 사람 · 골격 · 문서 — · 2회
          B108 불남 → 화재 (quality) · LLM 매칭 · 골격 · 문서 ['B108TQ'] · 1회
          B108 쇼트 → 단락 (quality) · LLM 매칭 · 골격 · 문서 ['B108SQ'] · 1회
          B108 품질 가 → B108 산문 고장 (quality) · 병합 · 엔티티 · 문서 — · 1회
          B108 산문 고장 별칭 → B108 산문 고장 (quality) · 사람 · 엔티티 · 문서 — · 1회
          B108 화재 사람 → 화재 (quality) · 사람 · 골격 · 문서 — · 1회
      [PASS] ⓐ 같은 별칭 두 번이면 한 항목 — 다른 문서의 같은 표기(설비 열 · 사전 경로)는 문서 · 횟수만 는다(표 × 층 둘) · 같은 연산 두 번(ops alias)은 횟수만  — 'B108 적층 라인' ['B108TP', 'B108UP'] 2회 · 'B108 불남' ['B108TQ', 'B108UQ'] 2회 · 'B108 적층 사람' 2회(연산)
      [PASS] ⓐ 쓰는 손 하나(소스 대조) — 노드 별칭을 붙이는 자리는 `alias_book.attach` 한 곳 + seed 손(bootstrap) 하나뿐 · 인입 `Builder._register`와 연산 4곳(개명 · 이관 · 병합 · 분리)은 그 함수를 부른다  — 붙이는 자리 {'core/state/alias_book.py': 1, 'core/state/bootstrap.py': 1}

    ■ B108 ① 재구축 동치(별칭) — 골격 노드의 seed 밖 별칭 → bootstrap → 그 표기를 쓰는 문서 → rebuild
      [PASS] ⓑ 바닥 — 쓰는 문서의 공정명이 골격 대상 별칭(LLM 매칭 · 사람)으로 정확 일치(태깅 호출 0) · bootstrap 인입 앞 = 뒤  — 정확 일치 27 · 쓰는 문서 태깅 0 · 판 b23a26280f73c442 = b23a26280f73c442
      [PASS] ⓑ rebuild ⇒ 재구축 첫 bootstrap 스냅샷 = 재구축 전(층 둘 · 판 같음) · 태깅 정확 일치 수 같음 · 태깅 호출 0 · orphan 수 같음 · canonical 기준 상태 같음 · 재구축 뒤 bootstrap도 같은 스냅샷  — 판 b23a26280f73c442 → b23a26280f73c442 → b23a26280f73c442 · 정확 일치 27 → 27 · 태깅 0(가짜 실호출 0) · orphan 3 → 3 · 상태 같음
            별칭 대장 9(이번에 채움 0) · 골격 대상 6 — 재구축의 bootstrap이 골격 대상 별칭을 스냅샷 전에 싣는다
          [bootstrap] process: 별칭 대장 — 골격 대상 실음 3 · 이미 있음 0 · 대상 없음 0
          [bootstrap] quality: 별칭 대장 — 골격 대상 실음 3 · 이미 있음 0 · 대상 없음 0
          ■ 재구축 끝 — 문서 6(성공 6 · 실패·보류 0 · 원본 없음 0)
            LLM 호출 — 추출 0 · 판정 0 · 태깅 0 · 그 밖 0
            별칭 대장 9 · 그래프에 있음 9 · 없음 0

    ■ B108 ① 처음 채움 — 대장 없는 B108 전 모양 → 첫 실행 · 재구축 계획이 지금 그래프에서
      [PASS] ⓒ 첫 실행(공통 진입)이 지금 그래프의 seed 밖 별칭을 이름으로 채운다 — 표기 · 대상 · 출처가 지운 대장과 같다(처음 채움 표시)  — 지운 대장 9 → 채움 9 · 다른 것 0
          [별칭 대장] 지금 그래프의 seed 밖 별칭 9건을 이름으로 채웠다 — data/alias_book.json(골격 대상 6 · 기본 fresh가 남긴다 — B108 ①)
      [PASS] ⓒ 재구축 계획(fresh 앞)도 채운다 — 계획 줄 「별칭 대장 n(이번에 채움 m) · 골격 대상 g」  — 「별칭 대장 9(이번에 채움 9) · 골격 대상 6 — 재구축의 bootstrap이 골격 대상 별칭을 스냅샷 전에 싣는다」
      [PASS] ⓑ 처음 채움 뒤 rebuild ⇒ 재구축 첫 bootstrap 스냅샷 = 재구축 전(층 둘 · 판 같음) · 태깅 정확 일치 수 같음 · 태깅 호출 0 · orphan 수 같음 · canonical 기준 상태 같음 · 재구축 뒤 bootstrap도 같은 스냅샷  — 판 b23a26280f73c442 → b23a26280f73c442 → b23a26280f73c442 · 정확 일치 27 → 27 · 태깅 0(가짜 실호출 0) · orphan 3 → 3 · 상태 같음

    ■ B108 ① 거두기 — ops alias-reject (골격 · 엔티티)
      [PASS] ⓓ 비대화형은 계획만(③ 쓰기 0) · `--yes` → 노드 · 사전에서 빠지고 대장 「거부」 · 사람 판단 기록에 이름으로 · bootstrap이 다시 싣지 않는다(골격 대상 — 스냅샷에서 빠지고 판이 바뀐다) · 엔티티 대상도  — 판 b23a26280f73c442 → c2a791452b29adfd · 거부 기록 2 · 싣기 {'loaded': 0, 'already': 2, 'missing': [], 'rejected': 1}
          ■ 별칭 거두기 계획 — 'B108 적층 사람' ↛ 스태킹::적층 (Process · process · 골격)
              노드 별칭 있음 → 뺀다 · 사전 키 1(B108 적층 사람) → 걷는다 · 대장 사람 · 1회 · 살아 있음 → 거부
            (비대화형 — 계획만 · 쓰기 0) ▶ 다음 줄 — 실행: python run.py ops alias-reject process 스태킹::적층 "B108 적층 사람" --actor 시험자 --yes
          ■ 별칭 거두기 계획 — 'B108 적층 사람' ↛ 스태킹::적층 (Process · process · 골격)
              노드 별칭 있음 → 뺀다 · 사전 키 1(B108 적층 사람) → 걷는다 · 대장 사람 · 1회 · 살아 있음 → 거부
          [거둠] 'B108 적층 사람' ↛ 스태킹::적층 — 노드 · 사전에서 뺐다 · 별칭 대장 「거부」(다시 붙이지 않는다 · 재구축 뒤 ops replay가 다시 거둔다 · by 시험자)
            ▶ 다음 줄 — python run.py bootstrap   (골격 닫힌 목록에서 뺀다 — 판이 바뀐다)
      [PASS] ⓓ 재구축 뒤에도 빠져 있다(골격 — 대장이 bootstrap에서 막고 · 엔티티 — 판정 재생이 다시 붙이려 해도 쓰는 손이 막는다) · 대장은 「거부」 그대로 · 사람 판단 재생은 이미 그 상태  — 「사람 판단 재생 — 한 일 2 · 이미 그 상태 6 · 대상 없음 0 · 기록에 이름 없음 0 · 재생 안 함 0 · 거부 0」

    ■ B108 ① 화면 — show aliases · 재구축 끝 줄 · 골격 이름을 바꾼 seed
      [PASS] ⓔ `show aliases` 수 = 대장 수(출처별 · 살아 있음 · 거부) · 재구축 끝 줄 「별칭 대장 n · 그래프에 있음 m · 없음 k」(n = 대장)  — 화면 {'LLM 매칭': 4, '사람': 1, '개명': 1, '이관': 0, '병합': 1, '분리': 0, '문서': 0} · 대장 {'LLM 매칭': 4, '개명': 1, '사람': 1, '병합': 1} · 끝 줄 {'추출': 0, '판정': 0, '태깅': 1, '대장': 7, '있음': 7, '없음': 0}
          ■ 별칭 대장 — 살아 있음 7 · 거부 2 · 골격 대상 5 (data/alias_book.json — 기본 fresh가 남긴다)
            출처별 — LLM 매칭 4 · 사람 1 · 개명 1 · 이관 0 · 병합 1 · 분리 0 · 문서 0
            그래프에 있음 7 · 없음 0
            ── 노칭::노칭 타발  (Process · process · 골격)
               seed  punching · 노칭 타발 · 타발
               대장  B108 타발 공정  ← LLM 매칭 · 문서 B108SP(1) · 1회 · 살아 있음 · 처음 채움
            ── 스태킹::적층  (Process · process · 골격)
               seed  z-folding · z-stacking · 스택 적층 · 적층
               대장  B108 적층 라인  ← LLM 매칭 · 문서 B108TP → B108UP(2) · 2회 · 살아 있음 · 처음 채움
               대장  B108 적층 사람  ← 사람 · 문서 — · 1회 · 거부(시험자 · 2026-10-14T03:33:53+00:00) · 처음 채움
            ── 노칭::B108 관리 가 개명  (Property · process)
               대장  노칭::B108 관리 가  ← 개명 · 문서 — · 1회 · 살아 있음 · 처음 채움
            ── B108 산문 고장  (Failure · quality)
               대장  B108 품질 가  ← 병합 · 문서 B108TQ(1) · 1회 · 살아 있음 · 처음 채움
               대장  B108 산문 고장 별칭  ← 사람 · 문서 — · 1회 · 거부(시험자 · 2026-10-14T03:33:53+00:00) · 처음 채움
            ── 단락  (FailureEffect · quality · 골격)
               대장  B108 쇼트  ← LLM 매칭 · 문서 B108SQ(1) · 1회 · 살아 있음 · 처음 채움
            ── 화재  (FailureEffect · quality · 골격)
               대장  B108 불남  ← LLM 매칭 · 문서 B108TQ → B108UQ(2) · 2회 · 살아 있음 · 처음 채움
               대장  B108 화재 사람  ← 사람 · 문서 — · 1회 · 살아 있음 · 처음 채움
            ▶ 다음 줄 — 틀린 별칭은 거둔다: python run.py ops alias-reject <층> <대상> <표기> --actor <이름> (다시 붙이지 않는다 · 골격 대상이면 그다음 python run.py bootstrap)
      [PASS] ⓔ 골격 「스태킹::적층」의 이름을 바꾼 seed로 재구축 ⇒ 그 대상의 별칭은 bootstrap에서 「대상 없음」 · 끝 줄 없음 k ≥ 1(목록) · 대장에는 남는다(살아 있음)  — 끝 줄 {'추출': 0, '판정': 0, '태깅': 2, '대장': 8, '있음': 7, '없음': 1} · 「대상 없음 — 'B108 적층 라인' → 스태킹::적층 (Process) · LLM 매칭 · 골격에 그 이름이 없다(대장은 남는다 — 이름을 되살리면 다음 bootstrap이 싣는다)」
              대상 없음 — alias:reject · '스태킹::적층' 없음 · 시험자 · 2026-10-14T03:33:53+00:00
            별칭 대장 8 · 그래프에 있음 7 · 없음 1
              없음 — 'B108 적층 라인' → 스태킹::적층 (Process · process) · LLM 매칭 (대장에는 남는다 — 그 문서 · 이름이 돌아오면 다시 붙는다)
      [PASS] ⓔ seed를 되돌려 다시 재구축하면 그 대상의 별칭이 다시 실린다(「대상 없음」 0 · 그래프에 있음 · 판 = 거두기 뒤 판) · 개명된 seed 동안 새로 붙은 별칭(바뀐 이름 대상)은 이제 「없음」으로 대장에 남는다(지우지 않는다)  — 끝 줄 {'추출': 0, '판정': 0, '태깅': 1, '대장': 8, '있음': 7, '없음': 1} · 판 c2a791452b29adfd · 없음 '적층' → 스태킹::B108 적층 개명(LLM 매칭)

    ==============================================================
    전체 결과: PASS — G6.5 완료판정 충족

**ⓕ 가이드** — 런북 단계 0~7을 임시 mock 상태 루트(`USE_MOCK=1 · ONTO_MOCK_HOME=<임시>`)에서 처음부터 끝까지 친 실행 로그(아래 「런북 실행 로그」 — 「확인할 것」 줄은 그 로그에서 옮겼다) · `wc -l docs/가이드/2B_작업가이드.md` → `359`(692의 절반 남짓) · 검사 6종 `0 · 0 · 0 · 0 · 12 · 0`(문면 · 경로 · 문서간 · 가이드 · 자산 · 미러 — 자산 12는 지난 회차와 같은 판정 대상).

**ⓖ mock 네 벌**(기준 = `c751670`에서 같은 스크립트로 뜬 첫 인입 산출 — 벌 A 표 표본 5종 · 벌 B g65 바닥) — 그래프(층 둘 · 노드 · 엣지) · 사전 · 큐 · 판정 대장 **바이트 같음** · `data/` 파일은 **`data/alias_book.json` 더함 외 0**(A · B 둘 다).

    A 그래프 process nodes: 기준 95 · 지금 95 · 빠짐 0 · 더함 0
    A 그래프 process edges: 기준 133 · 지금 133 · 빠짐 0 · 더함 0
    A 그래프 quality nodes: 기준 47 · 지금 47 · 빠짐 0 · 더함 0
    A 그래프 quality edges: 기준 92 · 지금 92 · 빠짐 0 · 더함 0
    A 사전 같음 True
    A 큐: 기준 105 · 지금 105 · 빠짐 0 · 더함 0
    A 판정 대장: 파일 2 · 다른 파일 []
    A data 파일: 빠짐 [] · 더함 ['data/alias_book.json']
    B 그래프 process nodes: 기준 75 · 지금 75 · 빠짐 0 · 더함 0
    B 그래프 process edges: 기준 106 · 지금 106 · 빠짐 0 · 더함 0
    B 그래프 quality nodes: 기준 24 · 지금 24 · 빠짐 0 · 더함 0
    B 그래프 quality edges: 기준 44 · 지금 44 · 빠짐 0 · 더함 0
    B 사전 같음 True
    B 큐: 기준 66 · 지금 66 · 빠짐 0 · 더함 0
    B 판정 대장: 파일 6 · 다른 파일 []
    B data 파일: 빠짐 [] · 더함 ['data/alias_book.json']

### 런북 실행 로그 (요약 — 명령 · 종료 코드 · 확인 줄)

임시 mock 상태 루트(레포 `layers/` 복사 · 원본 넷 `raw/`) · 운영 명령은 `--allow-mock` · `doctor`는 레포 기본 mock 루트에서(mock doctor는 상태 루트에 표본을 넣는다 — 런북 루트와 가른다 · 사내 `USE_MOCK=0`에서는 넣지 않는다). 전문(1,500행 남짓)은 실행 세션에 있다.

- 0 `cp -r $ONTO_HOME …_bak_…` rc 0 · `python doctor.py --quick` rc 0 — 「상태 폴더 … · 모드 mock · 등록 4종(내장 4) · 층 2(상태 루트) · 좌표 층 process · 공통 config v1 · 문서 0」 · 「정합 … 큐 0 · 사전 표기 0 · 끝점 없는 엣지 0」 · `python run.py llm-check` rc 1 — 「결과: **① 설정**에서 막혔다」(설정 파일 없음 — 실호출에서만 통과 화면)
- 1 `init` rc 0 · `bootstrap --dry-run` rc 0 「쓰기 0 · 바뀔 것 없음 · 멈출 것 0건」 · `bootstrap` rc 0 「process: 노드 46 · 엣지 83」 · `skeleton-status process` rc 0 「문법 위반 0건」 · `skeleton-confirm process --by 홍길동`(터미널 · y) rc 0 「확정 기록 → layers/process/confirmations.json (1번째 …)」
- 2 `register generate rfq process RFQ01.xlsx --use-basic --sheets "2-4:prose 5:ref *:skip"` rc 0 「기계 관문(하네스): PASS — 41 PASS / 0 FAIL」 · `status rfq` rc 0 · `confirm rfq --by 홍길동` rc 0 「■ ③ 확정 — rfq 등록부 등재」 · `register generate ipqc process IPQC01.xlsx` rc 1 — 「■ 기계 관문 FAIL — ipqc · [FAIL] G13 …」(mock 표본 초안의 규약 10 — 런북 「막히면」의 실물)
- 3 `ingest-file CP01.xlsx --dry-run` rc 0 「[선택만]」 · `--step`(터미널 · c c q) rc 1 「── [3/7] 좌표 … 좌표 쌍 어긋남 2쌍(2행)」 → 「멈춤 — 좌표까지의 산출은 남았다」 · `ingest-file CP01.xlsx` rc 0 「결과 — 값 60 → 사전 연결 20 · … · 새 노드 40」 · `ingest-file RFQ01.xlsx --doc-type rfq --coord 노칭` rc 0 「문서 좌표 — 노칭 (출처: 사람)」 · 「── [4/8] 추출 예고 — 청크 10 …」 · `ingest-file PFMEA01.xlsx` rc 0 「레이저노칭 | 1」 · 「보류 4(좌표 목록 밖 1 · …)」 · `show doc CP01` rc 0
- 4 `platform queue` rc 0 · `platform queue coord_mismatch` rc 0 「쌍 묶음 — 어긋남 2쌍(2행)」 · `show learned` rc 0 · `ops review all` rc 0 · `ops confirm all --doc CP01`(계획) rc 0 → `--yes` rc 0 「auto 노드 40개 → confirmed」 · `ops alias process 노칭 "노칭 공정"` rc 0 · `show aliases` rc 0 「살아 있음 2 · … · 골격 대상 1」 · `ops alias-reject …`(계획) rc 0 「(비대화형 — 계획만 · 쓰기 0)」 → `--yes` rc 0 「[거둠] …」 · `bootstrap` rc 0 「process: 별칭 대장 — 골격 대상 실음 0 · 이미 있음 0 · 대상 없음 0 · 거부 1」
- 5 `query "노칭 다음 공정은?"` rc 0 「ⓐ 링킹 — 사전 1 · 임베딩 후보 20 → LLM 선별 0 (모드 보충)」 … 「ⓖ 노드 원 레코드 — 4건」 · `golden init` rc 0 · `golden score` rc 1 「채점할 문항이 0건이다」(문항을 채우기 전 — 정상)
- 6 seed `ALIASES` 「노칭」+「레이저노칭」 · `skeleton-status process` rc 0 · `rebuild`(계획) rc 0 「별칭 대장 1(이번에 채움 0) · 골격 대상 0 · 거부 1」 · `rebuild --yes` rc 0 — PFMEA01 「정확 일치 32 · 목록 밖 표기 0종」(고치기 전 31 · 1) · 끝 보고 「판정 — 재생 93 · 재판정 1(키 없음 1 …)」 · 「LLM 호출 — 추출 0 · 판정 0 · 태깅 0」 · 「사람 판단 재생 — 한 일 40 · 이미 그 상태 2 …」 · 「별칭 대장 1 · 그래프에 있음 1 · 없음 0」
- 7 `ls $ONTO_HOME/work/logs/` → `rebuild_20261014.log`(재구축의 fresh가 그 전 로그를 지웠다 — 런북 단계 7에 적었다) · `show aliases` rc 0 「살아 있음 1 · 거부 1」 · seed 별칭 줄 「seed  NC · notching · 레이저노칭」

### 가결정 (D-189 — 16건)

대장 = ③ `data/alias_book.json`(모듈 `core/state/alias_book.py` · 보존 다섯째 · 클린이 지운다) · 항목(표기 · 대상 이름 · id 참고 · 출처 · 골격 대상 · 별칭 레코드 · 조회 키 · 문서 처음·마지막 · 시각 · 횟수 · 상태 · 거부 · 옮긴 이력 · 처음 채움 표시) · **같은 항목 = (층 · 카테고리 · norm(canonical) · 표기)** · **횟수 = 새 문서 수 + 사람 연산 수**(재생 · 싣기 · 병합 이동은 +0) · **출처 닫힌 목록**(LLM 매칭 · 사람 · 개명 · 이관 · 병합 · 분리 · 문서 — 처음 채움은 provenance의 마지막 연산 · **「문서」는 골격 대상만**) · 쓰는 손 하나 + Builder가 사전과 같이 열고 같이 쓴다 · 연산이 이름을 바꾸면 대상 이름이 따라간다(seed 개명은 아니다) · **거부 = 다시 붙이지 않음(사전도) · 판정은 그대로 · `ops alias`가 푼다** · bootstrap 싣기는 심은 뒤 · 스냅샷 전 · 대장 파일을 늘 쓴다 · 스냅샷 별칭 = seed ∪ 대장 · 처음 채움은 공통 진입(파일 없을 때) · 재구축 계획(늘) · 손잡이 `ops alias-reject` · 화면 `show aliases` · **재생은 같은 표기 · 대상의 마지막 별칭 판단만** · 2B에서 옮긴 절 목록 · 가이드 검사의 깨끗한 자리 = 런북 전체 + 2B 증상표 — 전문은 `DECISIONS.md` D-189.

### 자체 검출

- 자체 검출 1(재생 왕복): `ops alias` → 뒤에 `ops alias-reject`한 기록을 재구축의 `ops replay`가 순서대로 다시 하면 잇기가 거부를 풀고(revive) 거두기가 다시 거부했다 — 최종 상태는 맞지만 재구축마다 대장 이력(`revived`)이 늘었다(ⓓ 스모크에서 「한 일 6」) → 같은 표기 · 같은 대상의 별칭 판단(`I6:alias` · `alias:reject`)은 마지막 것만 재생(「한 일 2 · 이미 그 상태 6」).
- 자체 검출 2(런북 실행 — B101 코드): `python run.py show learned`가 큐 `orphan_anchor`의 `rows`가 수일 때 `TypeError: object of type 'int' has no len()`로 죽었다(`coord_learn.candidates` — 큐의 정본 모양은 수 `store.enqueue_rows` · B101 시험 표본은 목록만 썼다) → 수를 그대로 더한다(옛 목록 모양도 센다).
- 자체 검출 3(런북 실행 — 가이드 문면): 2B · 걸어가기가 권하던 `python doctor.py | head -3`은 배너 세 줄만 보인다(상태 줄은 넷째 줄) · 파이프가 닫히면 `BrokenPipeError` 트레이스백이 남는다(`cli/_entry._Tee.write`) → 가이드는 `python doctor.py --quick`의 머리 상태 줄로 고쳤다 · 코드는 그대로(아래 제안).
- 관찰: 첫 시험 실행에서 병합의 남는 쪽이 id 순(상태 같음)으로 정해져 시험 기대가 틀렸다(시험 쪽 — `override`로 고정) · 산문 × process의 변형 표기가 후보 상한(12)에서 겹침이 없는 골격 노드를 놓쳤다(창작 표본의 표기를 겹침이 있는 「B108 타발 공정 → 노칭::노칭 타발」로 — 판정 경로는 그대로) · seed 개명 재구축에서 재판정이 바뀐 이름에 새 별칭을 붙였다(「적층 → 스태킹::B108 적층 개명」 — 되돌린 뒤 「없음」으로 대장에 남는다 · 시험 ⓔ가 그 성질을 잰다).

### 가이드 · 구조도

- 가이드: `운영_런북.md`(신설) · `2B_작업가이드.md`(명령 사전 + 증상표 + 부록 A · 별칭 행 둘 「재구축 뒤 쌓인 별칭이 없다」 「별칭이 틀렸다」 · §5.3 `show aliases`·`ops alias-reject` · §5.4 별칭 대장 행) · `걸어가기_설비문서.md`(설비 특유만) · `상태_폴더_가이드.md`(③ 9종 · 보존 다섯 · `rebuild`·`bootstrap`·`ops` 쓰는 곳) · `인입_이해_가이드.md`(머리 링크) · README(명령 순서 = 런북).
- 구조도: 00_칸_대장(0.3 `core/state/alias_book.py` · 2.8 `show aliases`) · 00_전체_지도(B108 행 · how-to 줄) · 02(스냅샷 별칭 = seed + 대장) · 03(쓰는 손 하나 · 저장 순서) · 06(`ops alias-reject` · `show aliases` · `ops alias` 대장 · `init --fresh` 보존 다섯 · `rebuild` 계획·끝 줄) · 10(생성).
- 검사기: `docs/회귀스위트/점검_가이드.py` ③ — 깨끗한 자리 = 운영 런북 전체 + 2B 증상표.
- 장부: `DECISIONS.md` D-189 · PROGRESS B105 → `docs/archive/장부/PROGRESS_B105.md` · `docs/안건/B105_요청문.md` 삭제.

### 실행으로 확인한 것

- **클린 회귀 2회 동일**: `[  OK ] 합계 1798/1798 PASS` ×2 · `DOCTOR_DONE rc=0` ×2 · 판정 줄 diff 0 (B107 마감 1785 + `test_g6_alias_book` 13) · 「레포 정본 자산이 레포 판이다」 · 「클린 2회 동일 그래프 (완료판정 4)」.
- 어서션 **+13 · 삭제 0 · 기대 변경 0**(`test_g6_alias_book` 13). +13이 잠그는 성질: ⓐ 대장 쓰기(LLM 매칭 골격 대상 표·산문 × 층 둘 · `ops alias` 골격·엔티티 · 개명 · 병합 — 이름 · 출처 · 골격 표시 · 처음 문서) · 같은 별칭 두 번 = 한 항목(다른 문서 = 문서·횟수 · 같은 연산 = 횟수) · 쓰는 손 하나(소스 대조) / ⓑ 바닥(쓰는 문서 정확 일치 · 태깅 0 · bootstrap 앞 = 뒤) · 재구축 동치(스냅샷 층 둘 · 판 · 정확 일치 수 · 태깅 0 · orphan 수 · canonical 상태 · 재구축 뒤 bootstrap) / ⓒ 첫 실행 채움(표기 · 대상 · 출처 = 지운 대장) · 재구축 계획 채움(계획 줄) · 그 뒤 재구축 = ⓑ / ⓓ 비대화형 계획만(쓰기 0) · `--yes` 거두기(노드 · 사전 · 거부 · 기록 이름 · 싣지 않음 · 판 바뀜 · 엔티티) · 재구축 뒤에도 빠짐(골격 · 엔티티 · 재생은 이미 그 상태) / ⓔ `show aliases` 수 = 대장 수 · 끝 줄 · seed 개명 재구축 = 「대상 없음」 + 대장에 남음 · 되돌리면 다시 실림.
- **네 벌 diff**: 위 ⓖ(대장 파일 추가 외 0 — 최종 코드로 다시 떠서 같다).
- 검사 6종: 0 · 0 · 0 · 0 · **12** · 0 — 자산 12는 지난 회차와 같은 판정 대상 · 자산 해시 0건(레포 정본 자산 변경 0). §7: 코드 지도 ⓔ 「운영 모듈 **140** · 합 **36,583행**」 · 「**파일 상한 위반 0** · **함수 상한 위반 0**」 — `core/build/build.py` 723(최장 `resolve_entity` 119) · `core/state/ops.py` 677 · `cli/show.py` 665 · `core/state/oplog.py` 415 · `core/state/alias_book.py` 339.
- `git diff c751670 -- cli/ core/ parser/ prompts/ kit/`: 16 files changed, 703 insertions(+), 60 deletions(-) — `core/`만 11 files, 542(+), 48(-) — `core/state/alias_book.py`(신설) · `core/build/build.py`(`_register` → `attach` · 거부 막기 · 대장 열기·쓰기) · `core/state/ops.py`(개명 · 이관 · 병합 · 분리 → `attach` · `retarget`) · `core/state/ops_mark.py`(`alias_reject` · `_pick` · 거부 풂) · `core/state/bootstrap.py`(싣기 · 스냅샷 별칭 · 화면 줄) · `core/state/oplog.py`(`_alias_reject` · 마지막 판단만 재생) · `core/dictionary.py`(`unregister`) · `core/state/init.py`·`store.py`·`migrate.py`(자리 · 보존 다섯) · `core/state/coord_learn.py`(자체 검출 2) / `cli/`: `show_learn.py`(`show aliases`) · `ops.py`(`alias-reject`) · `rebuild.py`(계획 채움 · 끝 줄) · `_entry.py`(처음 채움) · `show.py`(표).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 2 계약 ① 4항(28행) 「**공급 형태는 스냅샷이다**: 그래프의 골격 전 노드(auto alias 포함 — seed에 없는 파생 표기까지 …)를 한 시점에 추출해 고정한 `skeleton_closed_list.json`」 → 「… 골격 전 노드의 canonical과 **별칭 = seed `ALIASES` + 파생 auto alias(문서 3 §3.9 ⑹) + 별칭 대장의 골격 대상(살아 있는 항목)** — `bootstrap`이 골격을 심은 뒤 대장을 싣고 만든다 · 그래프의 다른 별칭은 싣지 않는다(스냅샷은 bootstrap을 언제 돌렸는지와 무관하다)」.
- 문서 2 계약 ② 2항(65행) 「닫힌 목록은 시스템이 공급한다 — 골격 전 노드(개념+극성 인스턴스)의 canonical과 alias.」 뒤에 「(alias = seed + 별칭 대장의 골격 대상 — ① 4항)」.
- 문서 4 §4.3-5(별칭 출처 넷) 끝에 「**seed 밖 별칭은 쓰는 손 하나를 지나 별칭 대장(③ `data/alias_book.json`)에 이름으로 남는다** — 표기 · 대상(층 · canonical · 카테고리 — id는 참고) · 출처(LLM 매칭 · 사람 · 개명 · 이관 · 병합 · 분리 · 문서(골격 대상만)) · 문서 · 횟수 · 상태 · 기본 fresh가 남긴다 · 사람이 거둔 별칭(`ops alias-reject`)은 다시 붙지 않는다(사전에도 — 판정은 그대로) · 대장은 판정을 대신하지 않는다(사전 → 재생 → LLM)」.
- 문서 4 §4.8-11(201행 — 재구축 한 명령) 「계획(…)」에 「· **별칭 대장 채움**(지금 그래프의 seed 밖 별칭 중 대장에 없는 것 — 「별칭 대장 n(이번에 채움 m) · 골격 대상 g」)」 · 「→ 기본 fresh → `bootstrap`」을 「→ 기본 fresh(별칭 대장은 남는다) → `bootstrap`(골격 대상 별칭을 스냅샷 전에 싣는다)」 · 끝 보고에 「· 별칭 대장 n · 그래프에 있음 m · 없음 k(목록)」 · 「사람 판단 재생은 같은 표기 · 같은 대상의 별칭 판단 중 마지막 것만 한다」.
- 문서 4 §4.9-1(「골격의 원천은 끝까지 사람의 파일이다」) 뒤에 「— 골격의 **구조**(노드 · 부모 · 이름)가 그렇다. 별칭은 쌓이는 지식이다: seed `ALIASES`(사람) + 별칭 대장의 골격 대상(판정 · 사람이 붙인 것 — `bootstrap`이 싣는다) · 대상 이름이 골격에 없으면 싣지 않고 「대상 없음」으로 센다(대장은 지우지 않고 바뀐 이름으로 옮기지 않는다)」.
- 문서 7 §7.8 상태 트리(38행) `data/` 줄 「… · coord_learned(좌표 학습 · B101) — 8종」 → 「… · coord_learned(좌표 학습 · B101) · alias_book(별칭 대장 · B108) — 9종」 · 291행 「[개정] B106 ① — 기본 `init --fresh`는 보존 넷을 빼고」 → 「보존 다섯(+ ③ `alias_book.json`)을 빼고」 · 213행 회귀 규약 「(기본 `--fresh`는 보존 넷을 남기는 …)」 → 「보존 다섯」 · ③ 표(305행 `coord_learned.json` 다음)에 행 「`alias_book.json` | 별칭 대장 — seed 밖 별칭(표기 · 대상 이름 · 출처 · 문서 · 횟수 · 상태) · 쓰는 손 하나 · 기본 fresh가 남긴다 · 지우면 골격 대상 별칭이 재구축 스냅샷에서 빠진다(그래프가 있으면 첫 실행 · 재구축 계획이 다시 채운다) | `show aliases` · `ops alias-reject`」.
- 부록 용어 — 「**별칭 대장**」 신설: 「seed 밖 별칭을 이름으로 쌓는 ③ 장부(`data/alias_book.json`) — 쓰는 손 하나 · 같은 표기 · 같은 대상이면 한 항목 · 거부 · 골격 대상은 bootstrap이 스냅샷 전에 싣는다 · 판정을 대신하지 않는다」 · 「동의어 사전」 행(20행) 「골격 alias의 원천은 seed ALIASES 블록」 → 「… seed ALIASES 블록 + 별칭 대장의 골격 대상」.
- CLAUDE.md §5(허브 관리) — 상태 다섯 단 ③ 「`data/` 8종 — 좌표 학습 `coord_learned.json` 포함(B101)」 → 「9종 — … · 별칭 대장 `alias_book.json`(B108)」 · ④ 줄 「`extract/`·`struct_maps/`·`ingest_log/`는 LLM이 든 산출이라 기본 fresh가 남긴다」 옆에 「③ `coord_learned.json` · `alias_book.json`도 남긴다(보존 다섯)」 · §6 착수 순서의 「`docs/가이드/2B_작업가이드.md` §0·§5.4」는 그대로 산다(앵커 유지) — 런북을 같이 적으려면 「운영 순서는 `docs/가이드/운영_런북.md`」.

### 제안 (이번 범위 밖 — 사유)

- `python doctor.py | head`처럼 화면을 파이프로 자르면 `BrokenPipeError` 트레이스백이 남는다(`cli/_entry._Tee.write` — 모든 진입점 공통) — 런북 · 가이드는 파이프 없는 형태로 고쳤다. 코드로 막으려면 공통 진입에서 `BrokenPipeError`를 잡아 조용히 끝내는 몇 줄이다(회차 지정이 필요 — 이번 완료판정 밖).

### 마감 뒤 — 시간 줄이기 3건 (사용자 승인 2026-10-14 · D-190)

- **클라우드 세션 시작 훅** `.claude/settings.json` → `.claude/hooks/session-start.sh` — 원격 세션에서만 선택 의존 셋(openpyxl · python-pptx · pymupdf 1.25.5)을 `python3 -m pip`로 깐다(이 이미지의 `pip`는 Python 3.13에 깐다). 실행: 셋을 지운 뒤 rc 0 · 5.3초(설치 뒤 `/usr/local/lib/python3.11/dist-packages`) · 이미 있으면 rc 0 · 0.4~0.5초 · 로컬(변수 없음) rc 0 · 0.01초 · `doctor --env` rc 0(openpyxl · pptx OK).
- **네 벌 대조 `tools/four_way.py --base <커밋> [--keep <폴더>]`** — 기준 커밋 사본과 작업 트리 사본에서 mock 첫 인입 두 바닥을 동시에 돌려 비교(레포 `state_mock/` 0). 실행: `--base c751670` rc 1 — 「A data 파일: 빠짐 [] · 더함 ['data/alias_book.json']」 · 「B data 파일: 빠짐 [] · 더함 ['data/alias_book.json']」 그 밖 전부 0(위 ⓖ와 같은 줄) · 덤프 둘이 B108 스크래치 덤프와 내용 동일 · 소요 3초 / `--base HEAD` 「전부 같다」 rc 0 / 없는 커밋 rc 2 / 옛 커밋(코드 모양이 다름) rc 2 + 로그 끝. 244행 · 최장 함수 43행.
- **마감 doctor 1회** — 요청문의 「클린(`--all`) 2회 동일」은 doctor 완료판정 4 「클린 2회 동일 그래프」가 한 실행 안에서 잰다(B106 요청문 32행이 그 판정 이름). 허브가 2회를 유지하면 되돌린다.
