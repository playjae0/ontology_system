# PROGRESS — B200 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B200의 본문을 여기로 옮겼다(B203 마감 때).

## B200 — 동의어 점검: 규칙 점검 · LLM 검토 · 뷰어 「동의어」 탭 · 사람 승인 · 골격에서 빠진 seed 별칭 걷기 · 공유 별칭 보류 문면 (2026-11-12 · 칸 0.3 · 3.4 · 5.1 · 문서)

> 요청문 `docs/안건/B200_요청문.md`(hub_188 반입 `7b42aba` · B199 머지 `0c05539` · hub_186 `d9b3b7e` 위) · 단독 · 큼.

- 전제 10행 — 같다(1행 맨 위 hub_188 반입 · 그 아래 hub_186 머지 — hub_187 반입 없음 · 2행 `show aliases` 6행(docstring) · 4행 재현: 골격에서 `cathode 탭용접`을 지우고 bootstrap → 노드 별칭 7개 · 사전 키 그대로)
- 마감 한 줄 2회 — 1회 FAIL 3(gateway 801행 · ops main 121행 · 칸 대장 지시문 · core/llm 밖 설정 접근 · 시험의 graph.json 경로 · 런북 대조 3줄 · 옛 「쓰기 라우트 없음」 어서션 둘) → 2회 FAIL 0 · doctor 2245(기대 2240 +5) · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 상한 0
- ⓐ PASS mock bootstrap 「동의어 — 공유 3 · 검토 안 된 짝 103 — 뷰어 「동의어」」 · 공유 「비전 검사」 노드 셋 · 뷰어 묶음 공유 수 같다 · 점검 · 화면 그래프 바이트 0
- ⓑ PASS ⑤ 뒤 노드 「탭용접」 별칭에 `cathode 탭용접` 0 · 사전 키 0 · 「골격에서 빠진 seed 별칭 1 걷음 — 붙어 있던 행 1(문서 CP01)」 · CP01 재인입 C12 보류 「사람 확인 전 공정 표기 — 'cathode 탭용접'」
- ⓒ PASS LLM 검토(mock) 첫 실행 102짝(유지 짝 제외 · 맞음 99 · 틀림 1 · 애매 2 · 호출 3) · 둘째 물음 0 · 호출 0 · 개명 뒤 열쇠가 따라간다(판정 그대로)
- ⓓ PASS 대장 지움 → 거부 · seed 지움 → `skeleton.json` · 노드 · 사전에서 빠짐 · 후보 받기(인라인 골격 → `ops alias`) → 마무리에 사전 연결 · 행위자 없음 거부 · 손으로 고친 골격 → 「골격이 바뀜 — 다시 점검 1」 · `ops replay`가 「유지」를 다시 적는다
- ⓔ PASS 쓰기 라우트 둘 밖 POST 501 · 진행 중 둘째 검토 409 + 거절 문면 · `/api/aliases` GET 200
- ⓕ PASS 「표기 모호 — '비전 검사'의 노드 여럿(노칭::비전검사 · 스태킹::비전검사 · 탭용접::vision check) · 이 행의 범위(패키징)에 없다」 · 범위 없는 행 「· 범위 없음 — 문서 좌표(--coord) 또는 상위 칸」
- ⓖ PASS 네 벌 전부 같다(mock 바닥은 골격 seed = 노드 — 걷음 0)
- ⓗ PASS 명세 패치 `--apply`(+716자 · 문서 3 · 4 · 7 — 6항목) · 문서 1 B14(뷰어 쓰기 예외)는 `B200_명세패치_허브.md`(적용 안 함)
- ② 비용 실측(창작 mock) — 짝 103 · 묶음 3(50) · 예상 입력 약 15,877 · 출력 약 4,120 토큰(어림 — 글자 / 2) · `ops alias-audit --llm` 실경로
- 뷰어 — Playwright로 「동의어」 탭(mock — 「LLM이 빼자는 것 1」 폴딩 → 스택 삽입 · 공유 「비전 검사」 · 봉투 없는 문서는 「모른다」)
- 가결정(D-281) — LLM 지점은 ② 안의 태그 `alias_review`(닫힌 12 그대로) · 판정 목록 칸 · 붙은 행 셈 · 개명은 따라감 / 병합은 다시 · 인라인 골격은 `ops alias` · 골격 `ALIASES` 두 손이 층을 받는다 · 보류 문면 셋째(범위 안에도 여럿) · 쓰기 자물쇠 하나 · 진행은 `/api/status` · 「유지」 재생 `alias:keep`
- 어서션 +5 · 삭제 0 · 고침 3 — +ⓐⓑⓒⓓⓕ(test_judge — 동의어 조각) · 고침: test_viewer 「쓰기 라우트 없음」 → ⓔ(둘 밖 501 · 진행 중 409 · 읽기 200) · test_viewer ⑥ · part_g4 「쓰기 라우트 없음」 → 「둘 밖 501 · WRITES 둘」
- 바꾼 파일 — 새: `core/state/alias_{audit,review,approve}.py` · `cli/viewer/alias.py` · `cli/viewer/static/alias.js` · `prompts/0.3_alias_review.md` · `tests/fixtures/alias_review.json` · 고침: `core/state/{bootstrap,alias_book,surface_book,provisional_hand,oplog}.py` · `core/build/{build_coord,table,coord_scan}.py` · `core/llm/{gateway,points,preflight}.py` · `cli/ops.py` · `cli/viewer/{server.py,static/index.html,static/app.js,static/style.css}` · `run.py` · 시험 · 명세 · 런북 · 칸 대장
- 보인 것 — mock `all`은 봉투를 `work/parsed/`에 두지 않아 mock 화면의 붙은 행은 대개 「모른다」(사내 실경로는 인입이 남긴다) · 골격 팩에 「승인 · bootstrap이 ALIASES를 고친다」 한 줄이 빠졌다(결정 §4 — 다음 회차 가이드)
- 사내 config 줄 — 0 · 머지 뒤 반입 → `bootstrap`(걷음 줄 · 동의어 한 줄) → 뷰어 「동의어」 → 「LLM 검토」(처음 한 번 전체 — 비용 미리보기) → 승인 → 「다시 붙일 행」이 있으면 그 문서 재인입
- ⓪ 긴급(hub_192 · `8645815` 위) — `cli/split_report.py` 목차 접기 KeyError 고침은 #159로 이미 머지(zip과 같은 바이트 · MD5 `0cec73d9…`) · 이번엔 회귀 어서션 셋으로 맞춤(test_structure — 1 재현 10~13행 제목 + 14행 판단 필요 → 14행이 13행 아래 · 「외 2줄(R11~R12)」 · 2 판단 필요를 빼면 「외 3줄(R11~R13)」 · 3 무작위 나무 3000 예외 0) · 어서션 +2(앞 회차의 한 개를 1로 고침) · 삭제 0 · 마감 한 줄 1회 FAIL 0 · doctor 2252(기대 2250 +2) · 네 벌 전부 같다 · 바꾼 파일 `tests/part_g6_split.py` · 소요 약 25분(읽기 5 · 시험 10 · 마감 한 줄 4)
- ⓪ 긴급 둘(사내 [3/8] HTTP 400 「additionalProperties is required」 · B202 머지 `538cb56` 위) — 원인 B202 `gate_judge.SCHEMA` 맨 바깥 · `candidates[]`에 `additionalProperties` 없음(표 [3/7] · 산문 [3/8] 골격 칸 줄이 사람이 있을 때 부른다) · 같은 꼴 `gate_say`(B202) · `alias_review`(B200) — 셋 엄격(뜻 그대로) · 검사 한 자리 `gateway.strict_issues`(`_payload`가 보내기 전 `SchemaError` — 400 대신 지점 · 칸) · 옛 회귀 test_p3_gate ①은 손 모듈 목록 · `_SCHEMA` 이름만 훑어 `core/state`를 못 봤다(같은 함수로 고침) · 회귀 자동 수집 `tests/strict_probe.py`(mock 끔 · `_post`만 — CP01 · PFMEA01 · RFQ01 --step · 시트 역할 · alias-audit --llm · 뷰어 검토 — 잡힌 자리 9 위반 0 · 옛 꼴 schema를 넣으면 「[결함] schema 엄격 규칙 위반 — gate_judge」로 막힌다) · 어서션 +2(test_2a_gateway) · 고침 1(test_p3_gate 검사 함수) · 삭제 0 · D-285 · 명세 패치 `B200_⓪_명세패치.md` +91자(문서 7) · 마감 한 줄 1회 FAIL 0 · doctor 2264 · 네 벌 같다
- 소요 약 4시간 30분(어림) — 전제 · 읽기 40분 · ⑤⑥ 30분 · ①② 50분 · ③④ 60분 · 시험 작성 · 고침 50분 · 명세 · 장부 20분 · 마감 한 줄 2회 각 3분
