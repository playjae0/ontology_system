# PROGRESS — B106 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B106의 본문을 여기로 옮겼다(B109 마감 때).

## B106 — 재구축 보존: fresh 기본 보존 · 재구축 한 명령 · 판정 재생 · 사람 판단을 이름으로 · 문서 단위 확인 · 문서 좌표 상위 (2026-10-08)

hub_83 반입(`058a333` — origin `f6c4179` 위 · 코드 0) 위 · 순서 ①③②④(`9615f26` — 한 커밋: ③의 이름 기록이 ①의 보고와 ⓑ의 바닥이라 같이 섰다) → ⑤(`f1dff85`) → 시험 · 소속 대상 대장 행 · 문서 좌표 상위 보강 · 순서의 근거(`8ba5076`) → ⑥ 가이드·구조도 · 기대 변경 둘(`a664d9c`) → 처음 인입 셈 · D-187 · BLOCKERS 18 · B103 본문 보관 · B103 요청문 삭제(`620dddc`) → 코드 지도(`55fc985`) → 재구축이 제 명령 로그를 지우지 않는다 · 시험 18(`dd793f8`) → 마감(이 커밋). 소요 — 반입 02:44 → 마감 05:15(UTC) · 약 2시간 30분.

### 전제 대조표 8행 (`058a333` — 반입 그대로 · `git grep … 058a333`으로 잼)

1 `52` · `67` / 2 `139` · `35` / 3 `88` · `59` / 4 `25` · `556` / 5 `190` · `62` / 6 `199` · `359` / 7 `28` · `467` / 8 반입 뒤 `4`(B103·B104·B105·B106) — 전부 기대값과 같다. `f6c4179`→`058a333` 사이 `core/`·`cli/`·`parser/`·`prompts/`·`kit/` 변경 0. 전제 6의 「인입 순서 기록」은 열(`first_ingested_at`)은 있으나 값이 봉투의 `parsed_at`이고 운영 파싱은 파서 기본값(고정 문자열 `2026-01-05T00:00:00`)을 싣는다 — 시각 순서가 아니다 → 처음 인입 순서는 문서 대장의 저장 순서(새 문서는 끝에 · 재인입은 자리를 지킨다 — D-187 ②).

### 완료판정 (`tests/test_g6_rebuild.py` 출력 그대로 — 표·산문 × 층 둘)

    ■ B106 ⑤ 문서 좌표를 상위로 — 상위 열이 없는 행 (표 · 산문 × 층 둘 · 태깅을 지난 조각)
      [PASS] ⓕ 상위 없는 행(태깅이 하위에서 딴 상위 · meta.group_from_ref) + 문서 좌표 X + 하위 Y가 X 밖 → 쌍 표·큐에 「문서 좌표 'X' ↛ 하위 'Y'」(payload upper) · 좌표 단계 쌍·행 수 = 구축 큐 (표·산문 × 층 둘)  — 표×process 쌍 표 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] = 큐 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] ‖ 표×quality 쌍 표 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] = 큐 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] ‖ 산문×process 쌍 표 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] = 큐 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] ‖ 산문×quality 쌍 표 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)] = 큐 [('노칭>스태킹::적층', 1), ('탭용접>스태킹::적층', 1)]
      [PASS] ⓕ Y가 X 안이면 0(B) · 행에 상위가 있으면 그 상위로만(C 맞음 0 · D는 「상위 '탭용접'」 쌍 하나 — 문서 좌표 대조 없음) · 하위는 그대로(A의 개체가 Y 아래)  — 표×process 어긋난 행 ['A', 'D'] · A → 스태킹::적층::B106 카메라 A ‖ 표×quality 어긋난 행 ['A', 'D'] · A → 스태킹::적층::B106 카메라 A ‖ 산문×process 어긋난 행 ['A', 'D'] · A → 스태킹::적층::B106 카메라 A ‖ 산문×quality 어긋난 행 ['A', 'D'] · A → 스태킹::적층::B106 카메라 A
          표×process 문서 좌표 '노칭' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FTP-A
          표×process 상위 '탭용접' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FTP-D
          표×quality 문서 좌표 '노칭' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FTQ-A
          표×quality 상위 '탭용접' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FTQ-D
          산문×process 문서 좌표 '노칭' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FPP-A
          산문×process 상위 '탭용접' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FPP-D
          산문×quality 문서 좌표 '노칭' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FPQ-A
          산문×quality 상위 '탭용접' ↛ 하위 '스태킹::적층' · 1행 · 예 B106FPQ-D
      [PASS] ⓕ 큐 화면이 「문서 좌표 'X' ↛ 하위 'Y'」로 묶고 · `ops coord-ack all X Y`(상위 쌍과 같은 열쇠)가 그 쌍을 닫는다 · 좌표 단계 쌍 표도 확인됨  — [확인] 상위 '노칭' · '스태킹::적층' — 큐 4행을 「좌표 쌍 확인」으로 닫았다 · 문서 B106FPP, B106FPQ, B106FTP, B106FTQ · 기록 registry/coord_acks.json(재인입 · 다른 문서의 같은 쌍도 확인됨)
          · [상위] 문서 좌표 '노칭' ↛ 하위 '스태킹::적층' · 4행 · 문서 B106FTP, B106FTQ, B106FPP, B106FPQ · 예 B106FTP-A, B106FTQ-A, B106FPP-A · 확인 안 함
          ▶ 이대로 둔다(확인함): python run.py ops coord-ack all "노칭" "스태킹::적층" --actor <이름> [--reason "<메모>"]

    ■ B106 재구축 — 표 · 산문 × 층 둘 (CP01 · RFQ01 · PFMEA01 · B106Q)
      첫 인입 — {'CP01': '성공', 'RFQ01': '성공', 'PFMEA01': '성공', 'B106Q': '성공'} · 가짜 게이트웨이 호출 {'judge': 76, 'extract': 11}
      [PASS] ⓔ 문서 단위 확인 계획 — 수 = 그 문서 실행이 만든 auto 노드 수(출처의 첫 문서 · 불확실 제외 — 다음 줄은 ops review) · 비대화형은 계획만(③·② 쓰기 0)  — 계획 4 = 독립 계수 4 ['노칭::가압력', '노칭::이송 속도', '노칭::이송 장치', '노칭::적층 정렬도'] · 불확실 '노칭::노칭 프레스기' 제외 · 쓰기 0
          ■ 문서 단위 확인 계획 — RFQ01: auto 노드 4(Property 3 · Unit 1)
              · 노칭::이송 장치  (Unit · process · 01M4CXNT)
              · 노칭::이송 속도  (Property · process · 01M4CXNT)
              · 노칭::가압력  (Property · process · 01M4CXNT)
              · 노칭::적층 정렬도  (Property · process · 01M4CXNT)
              불확실 1건은 넣지 않는다(고르는 일) ▶ python run.py ops review all --actor 시험자
            (비대화형 — 계획만 · 쓰기 0) ▶ 다음 줄 — 실행: python run.py ops confirm all --doc RFQ01 --actor 시험자 --yes
      [PASS] ⓔ --yes 뒤 그 노드 전부 confirmed · 다른 문서(CP01)의 auto는 그대로  — [확정] RFQ01 — auto 노드 4개 → confirmed (by 시험자) · 큐 종결 auto_node · CP01 auto 38 그대로
      [PASS] ⓑ 재구축 동치 — canonical 기준 노드(카테고리 · status · 값) · 별칭(출처) · 엣지(status) · 큐 항목(쌍 키)과 resolution이 재구축 전과 같다 (표·산문 × 층 둘 · 사람 연산 10가지 뒤)  — 노드 151 · 별칭 191 · 엣지 232 · 큐 119 · 같음
      [PASS] ⓑ 재인입 LLM 호출 0(판정 · 추출 · 태깅 — 첫 인입은 판정·추출 > 0) · 사람 판단 기록 수 불변 · 끝 줄의 수 = 실행 누계 = 대장 행 수(재생 = 경로 replay 행 · 재판정 = 사유가 적힌 행)  — 첫 인입 {'judge': 76, 'extract': 11} → 재구축 {} · 기록 14 → 14 · 끝 줄 {'재생': 102, '재판정': 0, '키 없음': 0, '대상 없음': 0, '끔': 0}
      [PASS] ⓑ 산문 판정도 재생(층 둘) · 소속 대상 판정(대장 역할 belongs)도 재생 · 별칭 출처는 그때 경로대로  — 산문 재생 9행 — RFQ01 이송 장치(belongs · new) · RFQ01 이송 속도(entity · new) · RFQ01 노칭 프레스기(entity · uncertain) · RFQ01 가압력(entity · new) · RFQ01 버 높이(entity · new) · RFQ01 적층 정렬도(entity · new) · B106Q 금형 클리어런스 과다(entity · new) · B106Q 버 발생량 과다(entity · uncertain)
      [PASS] ⓐ 재구축 안의 기본 fresh — 넷(추출 · 지도 · 판정 대장 · 좌표 학습)과 ②등록 · ⓪원본은 바이트 그대로 · 그 밖 ③④⑤는 빈 상태  — 남긴 넷 {'work/extract': 2, 'work/struct_maps': 1, 'work/ingest_log': 4, 'data/coord_learned.json': 1} · 바뀐 것 [] · 남은 ③④⑤ [] · 빈 상태 True
      [PASS] ⓔ 재구축 뒤에도 문서 단위 확인이 confirmed(사람 판단 기록의 이름으로 되살렸다)  — 4개 — 노칭::가압력 · 노칭::이송 속도 · 노칭::이송 장치 · 노칭::적층 정렬도
      ── 재구축 화면(계획 · fresh · 문서마다 판정 재생 · 끝 보고 — 잘리지 않은 줄)
          ■ 재구축 계획 — 문서 4(다시 넣을 것 4 · 원본 없음 0)
            지울 것 — ③진실 data/ · ④작업 work/ · ⑤파생 export/ (아래 남길 것 빼고)
            남길 것 — 산문 추출 work/extract · 구조 지도 work/struct_maps · 판정 대장 work/ingest_log · 좌표 학습 data/coord_learned.json · ②등록 registry/(사람 판단 기록 14건) · layers/ · ⓪원본 raw/ · golden/
            다시 넣을 순서(처음 인입 순서):
                1. CP01                 cp         /home/user/ontology_system/tests/fixtures/raw/CP01.xlsx
                2. RFQ01                prose_xlsx_basic /home/user/ontology_system/tests/fixtures/raw/RFQ01.xlsx
                3. PFMEA01              pfmea      /home/user/ontology_system/tests/fixtures/raw/PFMEA01.xlsx
                4. B106Q                b106pq     /tmp/b106_rsyikuel/B106Q.xlsx
          [재구축 fresh] 남긴 것 — 산문 추출 2파일 4KB · 구조 지도 1파일 38B · 판정 대장 4파일 267KB · 좌표 학습 1파일 209B
          [재구축 fresh] 지운 것 — data/ 8파일 316KB · work/ 8파일 55KB · export/ 0파일 0B
          [재구축 fresh] 전부 지우려면 --all (클린 — 회귀 바닥 · 추출·판정을 처음부터 다시)
             판정 재생 — 재생 40 · 재판정 0(키 없음 0 · 대상 없음 0 · 끔 0)
             판정 재생 — 재생 6 · 재판정 0(키 없음 0 · 대상 없음 0 · 끔 0)
             판정 재생 — 재생 53 · 재판정 0(키 없음 0 · 대상 없음 0 · 끔 0)
             판정 재생 — 재생 3 · 재판정 0(키 없음 0 · 대상 없음 0 · 끔 0)
          ■ 재구축 끝 — 문서 4(성공 4 · 실패·보류 0 · 원본 없음 0)
            판정 — 재생 102 · 재판정 0(키 없음 0 · 대상 없음 0 · 끔 0)
            LLM 호출 — 추출 0 · 판정 0 · 태깅 0 · 그 밖 0
            사람 판단 재생 — 한 일 14 · 이미 그 상태 0 · 대상 없음 0 · 기록에 이름 없음 0 · 재생 안 함 0 · 거부 0
      [PASS] ⓒ 골격 「스태킹」→「스태킹 공정」(seed) 재구축 — 재판정 행이 전부 그 노드 아래 · 화면 수 = 대장의 재판정 행 수 · 그 이름을 쓰던 사람 연산(폐기 '스태킹::스태커')은 「대상 없음」 · 기록은 그대로  — 재판정 7행(대상 없음 7 · 키 없음 0) — 예 스태커 → 스태킹 공정::스태커 · 적층 정렬도 → 스태킹 공정::적층 정렬도 · 분리막 언와인더 → 스태킹 공정::분리막 언와인더 · 분리막 장력 → 스태킹 공정::분리막 장력 · LLM {'judge': 4} · 「대상 없음 — I4:obsolete · '스태킹::스태커' 없음 · 시험자 · 2026-10-08T04:52:20+00:00 · B106 폐기」
      ── ⓒ 재구축 끝 보고
          ■ 재구축 끝 — 문서 4(성공 4 · 실패·보류 0 · 원본 없음 0)
            판정 — 재생 95 · 재판정 7(키 없음 0 · 대상 없음 7 · 끔 0)
            LLM 호출 — 추출 0 · 판정 0 · 태깅 0 · 그 밖 0
            사람 판단 재생 — 한 일 13 · 이미 그 상태 0 · 대상 없음 1 · 기록에 이름 없음 0 · 재생 안 함 0 · 거부 0
              대상 없음 — I4:obsolete · '스태킹::스태커' 없음 · 시험자 · 2026-10-08T04:52:20+00:00 · B106 폐기
              ▶ 기록은 남았다 — 이름을 되살리면(seed를 되돌리고 python run.py rebuild) 다음 재생이 다시 한다
      [PASS] ⓒ seed를 되돌려 다시 재구축하면 그 연산이 재생된다(폐기 · 「대상 없음」 0) · 상태가 첫 재구축 전과 같다  — '스태킹::스태커' obsolete · 다른 것 없음
      [PASS] ⓓ --no-replay ⇒ 판정이 LLM으로(호출 > 0) · 대장 경로에 재생 0 · 끝 줄 「끔」 / 재구축 순서 = 처음 인입 순서(화면 계획 · 새 문서 대장 · RFQ01을 마지막에 다시 넣어도 그 자리)  — LLM {'judge': 76} · 끔 102 · 처음 인입 ['CP01', 'RFQ01', 'PFMEA01', 'B106Q'] · 계획 ['CP01', 'RFQ01', 'PFMEA01', 'B106Q'] → ['CP01', 'RFQ01', 'PFMEA01', 'B106Q'] · 대장 ['CP01', 'RFQ01', 'PFMEA01', 'B106Q']
      [PASS] ⓓ `ops replay` 두 번 = 한 번(재구축이 한 번 돌린 뒤 · 할 것 0 · 상태 · 기록 수 그대로)  — done 0 · already 14 · missing 0 · no_names 0 · skipped 0 · refused 0
      [PASS] ⓑ 재구축 명령(CLI) — 비대화형은 계획만(③·② 쓰기 0 · 다음 줄 `--yes`) · `--yes`면 계획 줄부터 끝 보고까지 명령 로그에 남는다(보존 fresh가 그 실행의 로그를 지우지 않는다) · 상태는 재구축 전과 같다  — 계획만 — 쓰기 0 · 로그 rebuild_20261008.log(계획 줄 있음 · 끝 줄 있음) · 다른 것 없음
      [PASS] ⓐ `init --fresh`(기본) — 넷과 ②등록 · ⓪원본은 바이트 그대로 · 그 밖 ③④⑤는 빈 상태 · 화면 「남긴 것 · 지운 것 · --all」  — 남긴 넷 {'work/extract': 2, 'work/struct_maps': 1, 'work/ingest_log': 4, 'data/coord_learned.json': 1} · 바뀐 것 [] · 남은 ③④⑤ [] · 빈 상태 True
          [init --fresh] 남긴 것 — 산문 추출 2파일 4KB · 구조 지도 1파일 38B · 판정 대장 4파일 265KB · 좌표 학습 1파일 209B
          [init --fresh] 지운 것 — data/ 8파일 316KB · work/ 10파일 183KB · export/ 0파일 0B
          [init --fresh] 전부 지우려면 --all (클린 — 회귀 바닥 · 추출·판정을 처음부터 다시)
          [init] 빈 상태 7개 — chunks.json, dictionary.json, review_queue.json, registry.json, doc_registry.json, process 그래프, quality 그래프
      [PASS] ⓐ `init --fresh --all` — 클린(doctor 잔재 0 · ③④⑤는 빈 상태뿐 · 사람 판단 기록 0)  — 잔재 0 · 남은 ③④⑤ 0 · 기록 0
      [PASS] ⓐ 회귀 · doctor · 시험의 클린 호출은 전부 --all — 기본 fresh 호출 0(소스 대조)  — 클린을 부르는 파일 34 · 기본 호출 0

    ==============================================================
    전체 결과: PASS — G6.5 완료판정 충족

**ⓖ mock 네 벌**: `FOUR_SAME`(그래프·사전·큐·판정 대장 — `그래프:process` canonical 95 · 엣지 133 · `그래프:quality` 47 · 92 · 사전 306 · 큐 107 · 판정 대장 399 — 기준 파일과 바이트 같음). 첫 인입 산출이 바뀌는 것 전수: 네 벌 0 · **판정 재생 0**(지난 대장이 없다 — 처음 인입은 세지도 행에 적지도 않는다 · 대장 `replay` 열 0행 · 경로 `replay` 0행 · 판정 끝 줄 없음) · **문서 좌표 상위 0**(네 벌 표본에 문서 좌표가 없다 — 큐 `upper` 0) · 소속 대상 행 `belongs` 0(네 벌 표본에 골격 밖 소속이 없다). 더해지는 것은 둘뿐이다 — 대장 행의 열 `category`(150행)·`scope`(86행 — 이름 규칙 카테고리일 때만 · 판정 재생의 키 몫) · 조각의 `meta.group_from_ref`(태깅이 하위에서 상위를 딴 조각 — 네 벌 표본은 행마다 상위 열이 있어 0 — 쌍 대조가 「상위 없음」으로 읽는 표시 · 문서 좌표가 없으면 대조는 지금과 같다).

### 회귀 · 기대 변경

- 회귀 **+18 · 삭제 0 · 기대 변경 6**(4파일): `test_g6_rebuild` 18 — ⓕ 상위 없는 행(태깅이 딴 상위) + 문서 좌표 → 「문서 좌표 'X' ↛ 하위 'Y'」 쌍 표 = 구축 큐(표·산문 × 층 둘) · 안이면 0 · 행의 상위가 있으면 그것으로만 · 하위 그대로 · 큐 화면 · `coord-ack` 같은 열쇠 / ⓔ 계획 수 = 그 문서 실행이 만든 auto(독립 계수 — 노드 출처의 첫 문서) · 비대화형 쓰기 0 · `--yes` 뒤 confirmed · 다른 문서 auto 그대로 · 재구축 뒤에도 confirmed / ⓑ canonical 기준 동치(노드·값·status · 별칭·출처 · 엣지·status · 큐 쌍 키·resolution) · 재구축 LLM 0 · 기록 수 불변 · 끝 줄 = 누계 = 대장 행 수 · 산문(층 둘)·소속 대상 재생 · CLI `rebuild` 비대화형은 계획만(쓰기 0) · `--yes`면 계획 줄부터 끝 보고까지 명령 로그에 / ⓐ 재구축 안의 fresh · CLI `init --fresh` · `--all` 클린 · 기본 fresh 호출 0(소스) / ⓒ 이름 바꾼 seed → 재판정은 그 노드 아래만 · 화면 수 = 대장 · 「대상 없음」 · 되돌리면 재생 · 상태 같음 / ⓓ `--no-replay` · 처음 인입 순서(다시 넣은 문서도 제자리) · `ops replay` 두 번 = 한 번.
- 기대 변경: `test_g5` 1(확정의 손이 `core/state/ops_mark.py`로 — 파일 분할) · `test_p3_gate` 1(mock 관문 진입점 넷 → 다섯 — `cli/rebuild.main`) · `test_g6_catalog_sync` 3(bootstrap 멈춤의 다음 줄 「재빌드」 → 「재구축(`python run.py rebuild`)」) · `test_g6_batch` 1(하위 폴더 인입 줄 — 구판은 화면에 원본 자리 경로가 있는지를 쟀는데 다른 시험(`test_viewer`)이 원본 자리에 남긴 파일의 실패 블록이 그 경로를 찍을 때만 초록이던 회차 간 순서 의존이었다(단독 실행은 B105 코드로도 붉다) → 기록이 그 자리를 가리키는지로).
- **클린 호출 전환 35 → 0**: 시험 33 + doctor = 34파일 · 88곳(`init(fresh_=True, all_=True)` 76 · `"init", "--fresh", "--all"` 12 — doctor `_clean` 포함) · 전제 2의 35파일 중 `test_g6_belongs`는 주석의 언급뿐 · 남은 기본 호출 0(ⓐ 마지막 줄이 소스로 잰다 — 이 시험의 기본 fresh는 시험 대상이라 뺀다) · doctor의 클린 문면 셋도 `--fresh --all`로.
- 자체 검출 1: `store.path("ingest_log")`가 ③을 가리켜 `ledger.made_by()`(뷰어 「만든 경로」)가 B78 이래 늘 비었다 → ④.
- 자체 검출 2: ⑤가 실제 파싱 흐름에서는 걸리지 않았다 — 태깅이 하위의 main 조상으로 상위를 채워(`tagger._apply` · 문서 2 계약 ②-3) 구축 단계에서 「행에 상위 없음」이 사라진다 → 딴 상위에 `meta.group_from_ref`(조각끼리 meta dict를 나눠 쓰는 표본이 있어 복사해서 단다) · 쌍 대조는 그 행을 「상위 없음」으로.
- 자체 검출 3: 산문 소속 대상의 판정(골격·버퍼·사전에 없어 새로 해소)은 대장 행이 없어 재구축마다 LLM을 불렀다 → 대장 행(역할 `belongs` · 열 `소속`) · 재생 재료.
- 자체 검출 4: 처음 인입의 판정이 전부 「재판정(키 없음)」으로 세어져 첫 인입 대장에 `replay` 93행 · 판정 끝 줄이 붙었다(네 벌 상태에서 발견) → 지난 대장이 없는 문서는 재생 대상이 아니다(재구축 · `--no-replay` 실행은 센다).
- 자체 검출 5: 가이드의 「`init --fresh` → `bootstrap` → 재인입」(§0 5단계 이관 뒤 재구축 · 사내 복구 · 층 이름 바꾸기 · 골격 이름 변경 …)이 이제 옛 판정 대장을 재생한다 — 「중복 노드를 안고 가지 않는다」의 뜻과 갈린다 → 이관 뒤는 `ingest-dir --no-replay` · 그 밖은 `rebuild` 한 명령으로.
- 자체 검출 6: 재구축의 보존 fresh가 그 실행의 명령 로그(`work/logs/rebuild_<날짜>.log`)까지 지워, 다시 열린 파일에 계획 줄이 없었다(「화면에 나온 것은 로그에도」) → 보존 fresh의 `keep`에 그 실행의 로그(`log.LOG_PATH`).
- 자체 검출 7: 좌표 태깅의 「목록에 없음」(null) 답은 기록되지만 다음 파싱이 다시 묻는다 — 실호출 재구축의 태깅 호출이 0이 아니다(mock 태깅은 호출 0이라 시험이 못 본다) → `BLOCKERS.md` 18(판정 필요 · 선택지 셋).

### 가이드 · 구조도

- `2B_작업가이드` §0 단 표(②등록 `ops_log.json` · ③ 8종 · 「돌아온다 — rebuild」 · ④ LLM이 든 산출 셋 · `rebuild/plan.json`) · 「`init --fresh`는 넷을 남기고 · 클린은 `--all`」 · §0 5단계(이관 뒤 `ingest-dir --no-replay`) · §2 흐름 증상 · §5.2 사내 복구 순서(`rebuild`) · §5.4 이력 표(`registry/ops_log.json` · `ops replay --dry-run`) · §5.5 골격 구조 행(재구축 한 명령) · 함정 문단(fresh 기본과 `--all`) · §7 증상표 새 줄 넷 — **「골격의 부모·이름을 고쳤다 — 재구축 순서」**(모은다 → seed → `skeleton-status` → `rebuild` 계획 → `--yes` → 끝 보고의 재판정·대상 없음·원본 없음 처리) · **「재구축 뒤 사람이 한 것이 없다」**(→ `ops replay` · 대상 없음 목록 · split) · 「재구축이 LLM을 다시 부른다」 · 「검수 끝난 문서의 auto를 한 번에」(→ `ops confirm all --doc`) + 이름 규칙 줄 둘 · 좌표 어긋남 줄(「문서 좌표 'X' ↛ 하위 'Y'」) · 체크포인트 재사용 줄(판정 재생 · `--no-replay`).
- `상태_폴더_가이드`(②등록 `ops_log.json` · ③ 8종 · ④ 보존 셋 · `rebuild/plan.json` · 명령 표 `init --fresh` / `--all` / `rebuild` / `ops confirm --doc` / `ops replay` · 이관 블록 `--no-replay` · 백업 줄) · `인입_이해_가이드`(판정 재생 줄 · 경로 `재생` · 사유 셋 · 소속 대상 행 · 좌표 쌍 「문서 좌표 ↛」 · 큐 표 · §6) · `config작성_가이드`·`골격작성_가이드`·`걸어가기_설비문서`(「재빌드(`init --fresh` → … 재인입)」 → 재구축 한 명령).
- 구조도 03(판정 입구의 재생 ①′ · anchor 행의 문서 좌표 상위) · 06(`init --fresh [--all]` · `rebuild` · `ops replay` · `ops confirm --doc` · `--no-replay` · 대장이 재생의 재료 · `init --fresh` 후 → 재구축 후) · 00_칸_대장(0.3 `cli/rebuild.py` · `core/state/oplog.py` · `core/state/ops_mark.py` · 3.1 `cli/ingest_batch.py` · 3.4 `core/build/replay.py` · 소속 대상 대장 행) · 00_전체_지도(B106 행) · 10(생성).

### 실행으로 확인한 것

- **클린 회귀 2회 동일**: `[  OK ] 합계 1774/1774 PASS` ×2 · `DOCTOR_DONE rc=0` ×2 · 판정 줄 diff 0 (B105 마감 1756 + `test_g6_rebuild` 18).
- **네 벌 diff** `FOUR_SAME`(위 ⓖ — 네 벌 스크립트의 클린 호출만 `--fresh --all`로 바꾼 사본).
- 검사 6종: 0 · 0 · 0 · 0 · **12** · 0 — 자산 12는 지난 회차와 같은 판정 대상 · 자산 해시 0건(레포 정본 자산 변경 0). §7: 코드 지도 ⓔ 「운영 모듈 **139** · 합 **35,682행**」 · 「**파일 상한 위반 0** · **함수 상한 위반 0**」(최장 `core/build/build.py::resolve_entity` 119).
- `git diff 058a333 -- cli/ core/ parser/ prompts/ kit/`: 30 files changed, 1311 insertions(+), 334 deletions(-) — `core/`만 17 files, 854(+), 199(-) — 신설 `core/build/replay.py`(판정 재생) · `core/state/oplog.py`(사람 판단 기록 · 재생) · `core/state/ops_mark.py`(확정·별칭·엣지 삭제·문서 단위 확인 — `ops.py`에서 분할) · `init.py`(보존 fresh · `kept` · 보고) · `store.py`(대장 자리 ④ · 기록 자리 ②) · `build.py`(판정 입구의 재생 한 자리) · `belongs.py`(소속 대상 대장 행) · `coord_scan.py`(문서 좌표 상위). `cli/`: 신설 `rebuild.py` · `ingest_batch.py`(일괄 — `ingest.py`에서 분할). `parser/`: `tagger.py`(`meta.group_from_ref`) · `coord_pairs.py`(`DOC_GROUP` · `describe` · `ack_kind`).

### 정제본 개정이 필요한 곳 (허브 몫 — 보고만)

- 문서 7 §7.6 완료판정 4(234행 — 요청문의 「§7.5 완료판정 4」) 「**클린 상태는 `run.py init --fresh`가 만든다** … ③진실·④작업·⑤파생을 폴더째 지우고 ②등록·⓪·`golden/`은 남긴다 … mock 루트에서는 `init --fresh`가 레포 `layers/`를 복사」 → 「**클린 상태는 `run.py init --fresh --all`이 만든다** — 기본 `init --fresh`는 재구축의 바닥이라 LLM이 든 산출 넷(④ `work/extract/`·`work/struct_maps/`·`work/ingest_log/` · ③ `data/coord_learned.json`)을 남긴다(B106 ①) · mock 루트의 클린은 레포 seed를 다시 심고 사람 판단 기록(②)을 비운다 · 기본 fresh는 `layers/`가 없을 때만 심는다」. §7.5-7(213행) 회귀 실행 규약의 「클린 상태」에도 같은 정의를 건다.
- 문서 7 21행 「`init --fresh`가 mock 루트에만 이것을 복사한다」 → 「mock 루트에만 복사한다(없을 때 · `init --fresh --all`이면 다시)」.
- 문서 7 §7.8 단 표(286~289행) — ②등록 `registry/` 행 + `ops_log.json`(사람 판단 기록 — 연산마다 행위자 · 시각 · 사유 · 대상의 층·canonical·카테고리 · `ops replay`가 이름으로 되살린다 · 옛 `data/ops_log.json`은 첫 실행이 옮긴다) / ③진실 행 「9종 · 돌아오긴 한다(bootstrap + 전량 재인입) — 그러나 재판정이라 LLM 비용이 다시 들고 큐·ops에서 사람이 한 판정은 돌아오지 않는다」 → 「8종 · 돌아온다 — 재구축 한 명령(`rebuild`): 판정은 ④ 판정 대장에서 재생(LLM 0) · 사람 판단은 ② 기록에서 이름으로 · 대장이 없거나 이름이 바뀐 값만 재판정(보고에 사유별 수)」 / ④ 행 「아무 일도 없다 — 다음 인입이 다시 만든다」 → 「다음 인입이 다시 만든다 — `extract/`·`struct_maps/`·`ingest_log/`는 LLM이 든 산출이라 지우면 다시 부른다(기본 fresh가 남긴다)」 + `rebuild/plan.json`(재구축 계획 — 지우기 전에 남긴 문서 목록). 그 아래 문단(291행) 「`init --fresh`는 ③④⑤를 지우고 ⓪②·`golden/`을 남긴다(7.6-4)」 → 「… 지우되 LLM이 든 산출 넷을 남긴다 · 클린은 `--all`(7.6-4)」 · ③ 표(9종)의 `ops_log.json` 행은 ②등록으로.
- 문서 7 314행 판정 대장 「`path`(닫힌 6값: skeleton·dictionary·scope+judge·embedding+judge·overlap+judge·none)」 → 실물 `matcher.PATHS` 9값(skeleton · dictionary · scope+judge · embedding+judge · overlap+judge · self_coord · memo · **replay** · none) — `replay` = 판정 재생(행에 `replayed_path` — 그때의 경로) · 열 + `category`·`scope`(있을 때 — 판정 재생의 키 몫) · `replay`(재판정 사유 — 키 없음 · 대상 없음 · 끔) · 역할 + `belongs`(소속 대상 판정 · 열 `소속`) · 「장부이지 정본이 아니다 — 재인입이 덮는다」 뒤에 「**판정 재생의 재료다**(지난 대장 — 기본 fresh가 남긴다 · 처음 인입은 재생 대상이 아니다)」.
- 문서 4 §4.8(186행~) + 9항 「**재인입의 값 판정은 그 문서의 지난 판정 대장에서 재생한다** — 순서는 골격 · 사전 → 재생 → 좁히기 + LLM · 열쇠는 (위치 · 열 · 표기 · 층) + 카테고리 + 이름 키(부모 좌표가 든 canonical) · `match`는 그 노드를 이름으로 다시 찾고 `new`·`uncertain`은 지금처럼(LLM 0) · 열쇠가 대장에 없거나(키 없음) 이름 키가 달라졌거나(대상 없음 — 골격 이름·부모 변경) 끄면(`--no-replay`) 지금처럼 판정한다 · 처음 인입은 대상이 아니다」 + 10항 「**사람 판단은 ②등록 기록에 대상의 이름으로 남고** 재구축 뒤 `ops replay`가 기록 순서대로 지금 손으로 다시 한다 — 이미 그 상태면 건너뜀 · 이름이 없으면 「대상 없음」 목록(기록은 지우지 않는다) · `split`은 재생하지 않는다 · 재생은 기록을 늘리지 않는다」 + 11항 「**재구축 한 명령**(`rebuild`) — 계획(지우기 전 · 처음 인입 순서 = 문서 대장 저장 순서) → 보존 fresh → bootstrap → 같은 순서 재인입 → 사람 판단 재생 → 보고(재생 · 재판정 사유별 · LLM 지점별 · 대상 없음 · 원본 없음) · 비대화형은 계획만」.
- 문서 4 §4.7(174행) 「연산 로그(ops_log 5요소: 연산·행위자·시점·대상·사유)」 → + 「대상의 이름(층 · canonical · 카테고리 — 재생의 열쇠 · id는 참고) · 자리는 ②등록」 · 160행 상시 kind 종결 경로 문단에 + 「문서 단위 확인 `ops confirm all --doc <doc_id>` — 그 문서 실행이 만든 auto 전부(불확실 제외 → `ops review`) · 비대화형은 계획만」.
- 문서 2 계약 ②-3(65행) 「process_group은 … 선택 노드의 tier:main 조상에서 파생한다」 + 「파생한 상위는 조각에 표시한다(`meta.group_from_ref`) — 행이 가져온 상위가 아니다」 · ②-4(67행) 「… process_ref의 골격 조상 대조(검증)이며, 어긋나면 `coord_mismatch` 큐로」 + 「**행에 상위가 없으면(파생 포함) 문서 좌표를 상위로 같은 판정에 넣는다** — 하위가 문서 좌표 노드 자신·그 아래면 맞음 · 밖이면 「문서 좌표 'X' ↛ 하위 'Y'」(payload `upper` · 쌍 열쇠는 상위와 같아 `ops coord-ack`도 같은 쌍) · 행이 가져온 상위가 있으면 그것으로만 · 하위는 바꾸지 않는다 · 등록 관문 G4I는 그대로」.
- 부록_용어: + 「재구축」(한 명령 `rebuild` — 보존 fresh · 처음 인입 순서 재인입 · 판정 재생 · 사람 판단 재생 · 보고) · 「판정 재생」 · 「대상 없음」(이름이 지금 그래프에 없다 — 재판정 · 사람 연산 목록) · 「클린」(= `init --fresh --all`).
- CLAUDE.md §4 「클린은 `run.py init --fresh`가 만든다」 → 「`run.py init --fresh --all`이 만든다」 · §7 「③진실(`data/` 9종 — …)」 → 8종 + ②등록 목록에 `ops_log.json`(사람 판단 기록 — B106) · ④에 `rebuild/plan.json` · §5에 한 줄 「재구축은 한 명령(`rebuild`) — 판정은 대장에서 재생 · 사람 판단은 이름으로 되살린다 · fresh 기본은 LLM이 든 산출 넷을 남기고 클린은 `--all`」.
