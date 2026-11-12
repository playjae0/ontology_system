# PROGRESS — B196 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B196의 본문을 여기로 옮겼다(B199 마감 때).

## B196 — 골격 칸의 문: 잠정 골격 노드는 사람이 정한 것만 · 좌표 쌍 어긋남은 확인 전 보류 · 골격 칸 검토 줄 · 연결 표지 (2026-11-11 · 칸 3.4 · 0.3 · 문서)

> 요청문 `docs/안건/B196_요청문.md`(hub_177 반입 `aa55776` · B195 머지 `56feec6` 위) · 단독 · 대 · 결정 기준 `결정_동의어_골격수준.md` §1 A′.

- 전제 16행 — 같다(B195 머지 판 `56feec6`에서 다시 잼 · 줄 번호 그대로: provisional 287 · 312 · build 556 · table 62 · prose 342 · 240 · 28~30 · 0 · 74 · 50 · 54 · 28 · ingest 216 · 224 · ops_review 58 · 69 · retry 235 · coord_scan 21 · 61 · table 132 · coord_acks 67 · tagger 651 · provisional 200 · loop 205 · table 181 · loop 462~464 · table 349 · reconcile 218 · 시험 9파일) · 명세 자리 6 같다(0 33 · 2 72 · 115 · 70 · 3 15 · 117)
- 마감 한 줄 2회 — 1회 FAIL 2(시험의 기본 fresh 호출 — 내 시험 ⓔ · 네 벌) → 2회 FAIL 1(네 벌 — 의도된 차이) · doctor 2241/2234 · 클린 2회 동일 그래프 · §7 상한 0 · 층 어휘 0(예외 1) · 레포 쓰기 0 · 문서 검사 일곱 0 · 기대 수 test_coord +7
- ⓐ PASS 표 행 「노칭공정X」(골격 밖) · 사람 없는 실행 → 잠정 노드 0 · 그 행들 보류 「사람 확인 전 공정 표기」 · 보류 재료에 들어온 자리 · 판단 · 후보
- ⓑ PASS 좌표 단계 처분(같은 함수 `provisional_ask.decide` — `--step` 관문의 `m 1` 꼴) — 합침(후보 1 → 스태킹 별칭 · 그 행은 스태킹) · 새로(잠정 노드 하나) · drop 「오기」(노드 0 · 보류 「사람 drop」 · 재연결이 열지 않는다) · `--step` 실경로는 B184 ⓔ(PFMEA01 `p 1` · `m 1 노칭`)가 새 줄 위에서 그대로 초록
- ⓒ PASS 산문 청크의 골격 카테고리 개체(`from_entity` — catalog ⓔ 고침: 사람 확인 전 노드 0 · 「새로」 뒤 다시 넣으면 선다) · PPT 조각 좌표 · 목차는 구축 앞 패스(`settle`) 한 길이라 표와 같은 판단
- ⓓ PASS 처분 없이 끝난 문서 둘 → `ops review` 골격 칸 한 줄(문서 둘 · 행 3) → 합침 → `ops relink`가 보류 행을 잇는다 · 남은 보류 0 · 추출 LLM 0
- ⓔ PASS 「봄」 기록(세움 기록 없이 — 이 회차 전에 선 잠정 노드) → 그래프를 비우고 다시 넣어도 그 노드가 선다 · 세움 기록 재구축은 judge B182 ⓕ(고침)가 잰다
- ⓕ PASS 쌍 어긋남(상위 스태킹 · ref 노칭) → 확인 전 보류 · a → 노칭 · r 1 → 노칭 아래 후보(개념 노드) · 극성 쌍은 지금처럼 붙고 큐만
- ⓖ PASS 골격 칸 머리 줄의 수(공정 표기 1종 · 골격 0 · 문 1종 2행 · 쌍 0 · ref 빈 행 0 · 판단 못 받음 0) · 후보 차례(판단 후보 → 자식 종류 수 → 행 수)
- ⓗ PASS 연결 칸 `connect`(rel_fallback) · `show report` 머리 「연결 미성립 n(소유자 미해소 · 관계 폴백 · 소속 폴백)」 · 「ref 빈 행 n」 · 인입 끝 줄 「… · 좌표 폴백 n · ref 빈 행 n」(옛 「저해상도 부착 n행」) · 연결 표지가 노드 · 엣지를 바꾸지 않는다(네 벌 C · D 같음 — A · B 차이는 ① ②의 몫)
- ⓘ PASS 표기가 모두 골격에 있는 문서 — 네 벌 C(산문 엑셀) · D(덱) 같다 · A · B(CP01 · PFMEA01)만 다르다: 노드 process 96 → 93 · 76 → 73 · quality 53 → 51 · 28 → 26 · 엣지 process 134 → 132 · 107 → 105 · quality 97 → 93 · 49 → 45 — PFMEA01 「레이저노칭」(골격 밖)이 서지 않고 그 행 보류 · CP01 R14(스태킹 ↛ 노칭) 쌍 보류
- ⓙ 명세 패치 `--apply`(+351자 · 문서 0 · 2 · 3 · 4 · 7 — 12항목 · 재봉인 0) · 문서 1 D4는 허브(`B196_명세패치_허브.md` — 적용하지 않음) · 마감 FAIL은 네 벌의 의도된 차이 하나
- 가결정(D-277) — 기록 자리: 표기는 사람 판단 기록(`ops_log` — `provisional:seed` · `provisional:drop` · 「봄」 `keep`은 세움 · 새 저장소 0) · 쌍은 `registry/coord_acks.json` 한 파일(확인 · 정정 `fixes{target}` · drop `drops`) · 키 `(표기 키, 부모 이름)` · 정정의 길은 범위 별칭이 아니라 구축 앞 패스가 그 쌍의 행을 정정 노드에 세운다(범위 별칭은 그 표기를 다른 문서에서 전역 모호로 만든다) · 글쇠 합침 `m [후보|이름]` · 새로 `k` · 승격 `p` · drop `d <사유>` · 확인 `a` · 정정 `r <후보|이름>`(한글 짝 ㅡ ㅏ ㅔ ㅇ ㅁ ㄱ) · 연결 칸 이름 `connect`(대장 역할 `link`와 다른 이름) · 후보는 개념 노드만
- 바뀐 시험 기대(전제 16 — 자동 생성에서 보류로) — judge(B182 · B184 · B181 표본에 사람 「새로」를 먼저 · B182 ⓑ 후보 둘 · ⓒ 출현 수 손잡이 → 「새로」 1행) · g3(레이저노칭 「새로」 · orphan_anchor 셋 · coord_mismatch 둘에 쌍 보류 행) · catalog_sync(ⓔ ⓕ — 사람 확인 전 노드 0 → 「새로」 뒤 선다) · narrow(B144 ⓖ — CP01 쌍 확인 먼저) · belongs · outline · deck(줄기 밖 공정 구간 — 쌍 확인 먼저) · rebuild(ⓕ — 어긋난 행 보류 · 재구축 동치는 쌍 확인을 인입 앞으로) · g65_common(도우미 `say_new` · `say_new_env` — 사람 「새로」 기록) · ingest · safe_log · struct · synonym은 바꾸지 않았다(초록 그대로)
- 어서션 +7 · 삭제 0 · 고침 7 — +B196 ⓐ ⓖ ⓑ ⓓ ⓔ ⓕ ⓗ(test_coord) · 고침: judge B182 ⓑ ⓒ · g3 orphan_anchor · coord_mismatch · catalog ⓔ ⓕ · rebuild ⓕ
- 바꾼 파일 — `core/build/{provisional,skeleton_review(새),coord_scan,build,build_coord,retry,loop,ledger,entry}.py` · `core/state/{provisional_hand,coord_acks,oplog}.py` · `cli/{provisional_ask,ops_review,ingest,ingest_screen,report_cause}.py` · 시험 열(새 스위트 0) · 가이드 넷(운영 런북 · 2B · 역할 판정 · 인입 이해) · 명세 5 · 코드 지도 · DECISIONS
- 보인 것 — 재시도가 보류 재료의 값을 그 행의 대상 열이 아니라 좌표 노드에 실었다(옛 결함 — 확인 뒤 재연결에서 재구축 동치를 깼다 → 대상 열로 고침) · 인입 뒤에 쌍을 확인하고 재연결하면 뒤 문서의 판정 근거가 바뀌어 재구축이 다시 묻는다(B167 「근거 바뀜」 그대로 — 처분은 좌표 단계에서 하면 0) · 손잡이 `provisional_min_mentions`는 효과가 없다(걷을지 허브) · 옛 「보류 k표기 — 골격 밖 좌표는…」 줄은 골격 칸 보류를 따로 낸다
- 사내 config 줄 — 0 · 머지 뒤 반입 → 그래프를 CP 전까지 다시(런북 6 · 사람 기록은 산다) → 문서마다 `ingest-file … --step` 좌표 단계에서 처분 또는 끝난 뒤 `ops review all` → `ops relink all --apply`
- 소요 약 90분(03:00 무렵 → 04:28 · 시작은 어림) — 전제 · 읽기 12분 · ① 문 12분 · ② 쌍 10분 · ③ 검토 줄 · 물음 · ops review 15분 · ④ 연결 표지 6분 · 옛 시험 고침(아홉 스위트) 20분 · 새 시험 6분 · 런북 · 가이드 · 패치 · 결정 8분 · 마감 한 줄 2회 각 3분
