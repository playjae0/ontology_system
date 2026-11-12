# PROGRESS — B199 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B199의 본문을 여기로 옮겼다(B202 마감 때).

## B199 — 줄이기 · 정제: 쌍별 예고 축약 · 붙는 자리 · 거부 근거 · 같은 값 접기 · 극성 칸 지키기 · 혼자 넘는 행 옆 조각 · 폐기 노드 연산 · 죽은 함수 (2026-11-12 · 칸 0.3 · 2.6 · 3.4 · 문서)

> 요청문 `docs/안건/B199_요청문.md`(hub_185 반입 `064642b` · B198 머지 `f810465` 위 — hub_184 대신 누적본) · 단독 · 중간.

- 전제 11행 — 같다(1행은 hub_184 반입 커밋 없음 — hub_185가 대신 · 9행 KeyError 'merged_into' 재현)
- 마감 한 줄 2회 — 1회 FAIL 1(doctor — 기본 화면의 └ 줄을 재던 시험 둘 · 고침) → 2회 FAIL 0 · doctor 2240(기대 2233 +7) · 클린 2회 동일 그래프 · 네 벌 전부 같다 · 사전 점검 116/116
- ⓐ PASS mock PFMEA01 --step [4/7] ~ 판정 결과 241줄 → 39줄 · `export/plan_PFMEA01.md`에 쌍별 예고 전부 · -v면 지금 진행 줄 그대로
- ⓑ PASS 판정 결과 「용접 진폭: 탭용접 → 탭용접::초음파 융착기(경로)」 꼴 위 3 · 쌍 줄 끝 「자리 바뀜 k」 · 값 0인 쌍 줄 0
- ⓒ PASS 층 config에 polarity 키 → 근거 「layers/process/config.json」(공통 config 근거 0)
- ⓓ PASS show node 노칭 정밀도 — 측정방법 「비전 측정기 (공통 · 양극 · 음극)」 한 줄 · spec 「±0.1mm (공통 · 양극)」 · 「[음극] ±0.12mm」(mock 원본)
- ⓔ PASS 봉투를 못 읽게 한 문서(CP01) 출처의 극성 칸이 다른 문서 저장 뒤 그대로 · 「극성 출처 못 읽음 1(문서 CP01)」
- ⓕ PASS 「작은 본문 · 4,005자 행 · 작은 꼬리」 → 한 조각(S!R1-R3) · 작은 쪽 400자(하한 300 이상) → 셋
- ⓖ PASS 폐기 노드에 rename · obsolete → 「폐기 노드다 — 되살리지 않는다 · … ops merge · … 다시 넣는다」 · KeyError 0(CLI는 지금 거부 관례 rc 2)
- ⓗ PASS `_is_toc` · `_style_outlines` grep 0(옆 상수 `_TOC_TITLE`도 읽는 곳 0이라 지움) · 네 벌 전부 같다 · 상한 이하 청크 바이트 같음(③ 시험)
- ⓘ PASS 명세 패치 `--apply`(+418자 · 문서 3 · 4 · 5 · 6 · 7 — 7항목 · 문서 1 항목 0 · 재봉인 0)
- ⑧ 확인 — 시험만 부르는 함수: `ops.merge_targets` · `ops.edge_keys` · `platform.extract_view` · `vectors.fingerprint` · `ids.is_ulid` — 운영 경로(core · cli · parser · kit · tools · run · doctor) 호출 0(지우지 않음 · 보고만) · `loop.py` 주석 20종 → 19종
- 가결정(D-280) — 예고 요약은 쌍 줄 + 판정 대상 위 3 한 줄 · 자리 바뀐 값 위 3은 문서 전체 · 쌍마다 진행 줄은 넣지 않음(40줄 한도) · md 한 자리(`envelope_md.save`) · 값 접기 `query.fold_values` · `value_text` 한 벌(옛 `_ctx` 지움) · 극성 못 읽음은 그래프 출처의 봉투를 지금 읽어 센다(문서 수) · 하한 = 상한 ÷ 10(코드 상수) · 거부 rc는 지금 관례 2
- 바뀐 시험 기대 — ingest_view ① 둘(기본 값 줄 0) · coord B197 ⓖ(예고 전부는 `full=True` · 칸 이름 「붙을 자리(판정 전)」) · g3 B198 ⓔ(값 줄 머리 「[공통 · 양극, …]」) · hier ③(넘는 조각 = 그 행 + 하한 미만 이웃) · judge2 ⓑ · belongs ⓖ(└ 줄은 -v로)
- 어서션 +7 · 삭제 0 · 고침 7 — +ⓐⓑ(test_g6_close) · ①md(test_coord) · ⓒ(test_catalog) · ⓓⓔ(test_g3) · ⓕ(test_structure) · ⓖ(test_ops)
- 바꾼 파일 — `core/build/{also_stage,polarity,reconcile,loop}.py` · `core/query/query.py` · `core/state/{ops,status}.py` · `parser/{struct_map,ooxml}.py` · `parser/adapters/basic_ppt.py` · `cli/{also_screen,ingest,ingest_screen,show,export,result_screen}.py` · `cli/viewer/static/app.js` · `run.py` · 시험 · 명세
- 보인 것 — 질의 값 줄 · `show node`의 공통이 단독일 때는 표지 없음(물음에 극성이 걸릴 때만 「공통」) · 뷰어 노드 상세의 값 칸은 접은 줄을 이어 붙인 글(표 칸 하나)
- 사내 config 줄 — 0 · 머지 뒤 반입(PFMEA 전) — 동작은 같고 화면 · 문면만 · PFMEA --step 화면이 쌍별 요약으로 · 전부는 `export/plan_<doc>.md`
- 소요 약 3시간 30분(어림) — 전제 · 읽기 30분 · ①② 70분 · ③④⑤ 50분 · ⑥⑦⑧ 30분 · 시험 고침 · 대표 어서션 30분 · 명세 패치 15분 · 마감 한 줄 2회 각 3분
