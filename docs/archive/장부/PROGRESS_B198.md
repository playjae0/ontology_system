# PROGRESS — B198 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B198의 본문을 여기로 옮겼다(B201 마감 때).

## B198 — 극성은 값의 한정어(P1 — 코드 · 명세): 골격 분기 · 하강 부착 · 이름 결합 · 짝 기구 · 극성 좌표 쌍 걷기 · 세 자리 · 질의 거르기 · 펼친 흐름 (2026-11-11 · 칸 3.4 · 3.6 · 0.3 · 문서)

> 요청문 `docs/안건/B198_요청문.md`(hub_182 반입 `5816f9c` · B197 머지 `dadf1b6` 위) · 단독 · 대 · 결정 `결정_극성_값단.md` · 전수 목록 `극성P1_전수목록.md` · 기대 차이 `B198_기대차이.json`.

- 전제 11행 — 같다(2행 전수 grep 376줄 · 59파일) — 멈춤 없음
- 마감 한 줄 2회 — 1회 FAIL 2(사전 점검 116/117 — 줄어든 기대 수는 사전 점검이 `--why`를 받지 않아 붉다 · 그 회의 doctor가 새 기대 수를 썼다 / 네 벌 — ⓑ의 의도된 차이) · doctor 2233/2252(줄어든 19는 사유) · 클린 2회 동일 그래프 → 2회 FAIL 1(네 벌 — ⓑ의 의도된 차이 하나) · 사전 점검 116/116 · doctor 2233/2233 · 클린 2회 동일 그래프 · 기대 수 바뀐 스위트 없음
- ⓐ PASS 전제 3의 grep 86 → 6 — 남은 6은 옛 마커 거부의 검출기(`skeleton.OLD_SPLIT` · 그 docstring 셋 · `cli/skeleton` K05 주석 — ⓖ가 쓴다)와 `catalog.legacy_rule`의 옛 config 키 `canonical_scope.bind_categories`(B174 옛 모양 제안 · 극성 결합 함수가 아니다)
- ⓑ 기대 차이 — C · D 노드 · 엣지 같다 · A process 노드 64(기대 69) · B 49(기대 52) — 결정 2-1로 PFMEA 관리항목이 CP의 설비 아래 같은 관리항목으로 맞는다(A 5 · B 3 — 품질 엣지도 그 노드로) · 엣지는 층마다 기대보다 8 적다 — 허브 계산이 인스턴스 → 개념 part_of 8(개념 이름으로 옮기면 자기 고리 — 같은 노드 엣지 거부)을 셌다 · 극성 한정 값 A 16 · B 8 같다 · mirrors 0 · `mirror_asymmetry` 0 · coord_mismatch 2 → 1(극성 쌍 지움)
- ⓒ PASS 「노칭::노칭 프레스::노칭 정밀도」 노드 하나 · 값 셋(없음 · anode · cathode) · 값 충돌 0
- ⓓ PASS anode → anode · anode + cathode → 공통 · anode + 빈칸 → 공통 · 차례 무관 · 극성 없는 출처를 걷으면 anode · 극성 없는 출처뿐인 엣지 · 노드는 칸 없음
- ⓔ PASS 「양극 탭용접 불량의 원인은?」 → cathode · anode만인 엣지 5 빠짐 · cathode · 공통 18 남음 · 값 줄 `[공통]` · `[양극]` (요청문의 「음극」은 `AXIS_LABELS`에서 anode다 — 요청문 기대 꼴에 맞춰 「양극」으로 쟀다)
- ⓕ PASS 펼친 흐름 한 줄 · 「흐름 밖 2(스태킹 › 분리막 공급 · 스태킹 › 전극 시트 공급)」
- ⓖ PASS 트리 `::cathode` + ALIASES `노칭::anode` → bootstrap 거부 「지울 줄 2」 · 그래프 쓰기 0
- ⓗ PASS 기록 이름 「노칭::anode::노칭 프레스」 → 개념 이름으로 찾음 1 · 「노칭::cathode::B198 없는 설비」 → 자리 없음 목록 · 쓰기 0
- ⓘ PASS 재구축 동치(test_rebuild) · 클린 2회 동일 그래프 · 층 어휘 0
- ⓙ 명세 패치 `--apply`(−4,587자 · 문서 0 · 2 · 3 · 4 · 5 · 7 · README · 부록 — 77항목) · 허브 몫(`B198_명세패치_허브.md` — 문서 1 C3 · F1 · F2 · F3 · F11 · J23 · 문서 4 F1 봉인 문단 §4.5-3 · 4 · 7 · 8 · 경계 — 12항목 · 재봉인 대상 F1 — 적용하지 않았다)
- 가결정(D-279) — 칸 이름 `polarity_by` · 값 `context.polarity` · 극성 값 목록은 골격 `AXIS_LABELS` 하나(스냅샷 `axis`) · 층 config `polarity` · `mirrors`는 폐기 키 · 적는 자리 `GraphStore.save` 앞 한 자리 · 극성 수식 표기는 자동으로 짓지 않고 사람이 ALIASES에 · 킷 `_axis`는 G5와 함께 지움 · G4L은 행 극성을 맥락 열쇠로 · 질의 극성은 하나일 때만 · 화면 문구
- 바뀐 시험 기대 — test_g3(노드 하나 · 값 셋 · coord_mismatch 1 · Units 1/1) · test_g1_g2(Process 30 · part_of 29 · tier 1/4/25) · part_g4(펼친 흐름 · 부모 파생 「(탭용접 기준)」) · 런북 「확인할 것」 14줄(mock 수) · rebuild B167 ⓒ(근거 바뀜 = 「노칭」 아래 값 전부) · rebuild_memory B107 ③(재생 또는 「근거 바뀜」만 다시 묻기 — 위 사람 연산의 개명 · 폐기가 재시도 때와 재구축 때 후보를 가른다) · B106 · B107 「버 높이」 합침 지움(산문이 표 노드에 바로 붙는다) · narrow B142 ⓕ · contract C1~C6 이름
- 어서션 +5 · 삭제 24 · 고침 다수 — +ⓓ ⓔ(test_g3) · ⓖ(test_g1_g2) · ⓗ(test_rebuild) · ⓕ(test_query) · 지움: 극성 인스턴스 · 하강 · 짝 · polarity 칸 · 미러 경고 · 극성 values 경고(test_g3 −14 · test_g1_g2 −1 · test_query −3 · test_catalog −1 · test_judge −1 — 기능을 걷었다 · 그 자리의 성질은 ⓒ ~ ⓗ와 네 벌이 잡는다)
- 바꾼 파일 — `core/build/{polarity(새),build,entry,heading,prose,table,loop,retry,belongs,human,also_gate,also_stage,place_guess,provisional,skeleton_review,coord_scan,build_coord,cardinality,naming}.py` · `core/{graph,matcher}.py` · `core/query/{query,records}.py` · `core/state/{skeleton,bootstrap,catalog,config_grammar,config_scope,ops,provisional_hand,oplog,alias_book,coord_acks,store}.py` · `parser/coord_pairs.py` · `kit/gate_checks.py` · `cli/*`(query · ops · ingest · show · export · skeleton · platform · coord_queue · config_map · export_config · ontology_map · doctor_view · provisional_ask · register/view) · `run.py` · mock `layers/{process,quality}` · 시험 · 런북 「확인할 것」 · 명세
- 보인 것 — 문서 3 §3.6 ⑷ 앞 근거 문단(극성 형제 · 병렬 체인)과 문서 4 §4.7 머리(「닫힌 20종」) · 가이드 · 팩의 `@split` · `polarity` · `mirrors` · `coord-ack --polarity`는 P2 몫으로 두었다 · CLAUDE.md의 「큐 kind 닫힌 20종」은 19종이 됐다 · 이연대장 §4 15(펼친 흐름)는 이 회차가 구현했다
- 사내 config 줄 — 머지 뒤 반입 → 골격 `skeleton.json`에서 `@split` · `::축값` · `@축값`(과 ALIASES `이름::축값` 열쇠)을 지운다(bootstrap이 지울 줄을 보인다) · 극성 수식 표기는 개념 노드 ALIASES로 · 층 config `polarity` · `mirrors` 키를 지운다(문법이 폐기 키로 멈춘다) → bootstrap → 그래프를 다시
- 소요 약 7시간(어림) — 전제 · 읽기 40분 · G1 ~ G5 걷기 150분 · G6 세 자리 · 질의 · 흐름 · 재생 80분 · 시험 고침 · 대표 어서션 120분 · 명세 패치 40분 · 마감 한 줄 2회 각 3분
