# PROGRESS — B179 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B179의 본문을 여기로 옮겼다(B182 마감 때).

## B179 — 동의어 · 골격 이행 D1: 이름 ↔ 이름 표기 대조 한 함수(공백 무시 · 대소문자 · 전각) · 좌표 학습 기록 + 별칭 대장 = 표기 대장 하나(사람 보증 / 기계 판단) · 소유자 이름 비슷 판정 삭제 (2026-11-04 · 칸 0.3 · 0.5 · 2.8 · 3.4 · 문서)

> 요청문 `docs/안건/B179_요청문.md`(hub_154 반입 `04af539` · 시작 커밋 B178 머지 `987f116`) · 단독 · 새 스위트 0 · ① ② ③마다 커밋(`5e8b362` · `89a8504` · `1aa76f8`) · 마감 한 줄 회차는 아래.

- 전제 10행 — 같은 명령: hub_154 위 B178 머지 / 54 · 63 / 224 · 231 · 345 · 362 / 318 / 91 · 96 / belongs 34 · reconcile 381 · result 96 · matcher 159 · report_cause 86 / 전제 6 열넷 / 62 · 63 / 25 · 30 · 36 · 61 · 83 / 234 · 252 · 295 / 402 / 82 · 83 / 37 · 42 · 151 · 254 · 256 / 125 / 9 · 166 · 220 / 위반 0건 — 요청문과 같다
- 마감 한 줄 2회 — 1회 FAIL 3(test_places — `retry` 판 지문이 사전 파일을 이름으로 직접 읽는 꼴 → 이름 묶음 반복 그대로 · test_build B112 ⓔ — 표본 파일명 조각이 ①로 골격 이름에 맞아 제안이 섰다 → 표본 고침 · 네 벌) → 2회 FAIL 1(네 벌 — 의도된 차이: data 파일 이름 하나 · 네 벌 넷 다) · doctor 2174/2172(+2) · 클린 2회 동일 그래프 · §7 상한 0 · 문서 검사 일곱 0 · 층 어휘 0 · 바뀐 지시문 없음
- ⓐ PASS 「노칭 커터」 = 「노칭커터」 · 「ＣＵＴＴＥＲ」 = 「cutter」 · 「커터 설비」 ≠ 「커터」 — 사전(core) · 소유자 이름(core) · 파서 2차 대조가 같은 함수(`parser.namefold.key`)
- ⓑ PASS 옛 두 파일 → 표기 대장 항목 수 = 옛 합(창작 13 = 좌표 학습 2 + 별칭 11) · 옛 파일 보관(fresh가 남기는 자리) · 두 번째 실행 바이트 같다 · 지위 사람 보증 6 / 기계 판단 7 · 두 갈래가 옛 모양 그대로 읽힌다
- ⓒ PASS 소유자가 다른 노드인 같은 이름 관리항목 → LLM 0 · 다른 노드 · 대장 `apart` · 손잡이 파일의 `owner_similar_pct` → 「폐기한 키」 · 다음 줄로 멈춘다
- ⓓ PASS 명세 패치 `--apply` · 층 어휘 0 · 네 벌 — 그래프 · 사전 · 큐 · 판정 대장 전부 같다 · 다른 것은 data 파일 이름 하나(`alias_book.json` → `surface_book.json` — 네 벌 넷 다 · ② 의도)
- mock 표기 대조로 새로 「같다」 0 · 이름 비슷 판정 사라짐 0(네 벌 — 창작 표본에 공백 · 전각만 다른 이름도, 소유자 이름 비슷 판정도 없었다) · 시험 표본 B142 ⓓ 사본 1 → 0
- 글 속 찾기 자리(이 회차 밖 · `fold_latin` 그대로): query 162 · 163(질의 링킹 — `fold_groups(fold_latin)`) · 473 · 474(참고 청크) · lens 51 · 52(렌즈 어휘) · extract 276 · 279(본문의 골격 이름) · outline 249(제목 글자 안 위치) · show_report 250 · 251(보고 강조) / 전제 6에 있었으나 이름 ↔ 이름이라 바꾼 둘: extract 248 · 250(`_subtree` 공정 표기 ↔ 골격 이름) · prose 159 · 163(`parent_hit` 부모 표기 ↔ 부모 후보)
- 대장 이전 줄(실경로 · 임시 mock 루트) — `[표기 대장] 옛 두 파일을 옮겼다 — 좌표 학습 채택 1 · 목록 밖 1 + 별칭 대장 2 = 4항목 → data/surface_book.json 4항목(사람 보증 1 · 기계 판단 3) · 옛 파일은 보관 data/coord_learned.json · data/alias_book.json(지우지 않는다 — B179 ②)`
- ③ 삭제 세 조건 — 읽는 곳 0(`SIMILAR` · `owner_similar` · `_emb_similar` · `OWNER_SIMILAR_PCT` · `.similar` · `similar=` grep 0 — 폐기 키 표의 글만) · 회귀 영향 0(마감 한 줄) · 명세 §7.8 손잡이 줄은 이 회차 패치가 지웠다 / 남긴 것 — `scope_path.names_of`(같은 이름 · 기다리는 소유자) · 대장 `apart` · 인입 끝 「같은 이름 · 다른 소유자」 줄 · md 표(열 하나 뺌)
- 어서션 +2 · 삭제 0 · 고침 5 — +B179 ⓐ(test_catalog) · ⓑ(test_rebuild) / 고침 B142 ⓓ → B179 ⓒ(test_judge — 기능 지움) · B108 ⓒ 준비 둘(옛 파일 지우기 → 별칭 갈래 빼기) · B111 ⓑ 보존 이름(표기 대장) · B106 ⓑ 탐침 준비(좌표 학습 갈래)
- 가결정 D-263(표기 대조 키 자리 · 글 속 찾기와 가름 · 표기 대장 모양 · 이전 · 보관 · 이름 비슷 삭제의 남김)
- 명세 패치 `B179_명세패치.md`(21항목 · +27자 — 문서 2 §2.4 ① · 문서 4 §4.2 · §4.3-5 · §4.3-7 · §4.3-8 · 문서 7 §7.5 · §7.6-4 · §7.8 · 부록) `--check` → `--apply` · 문서 1 0 · 재봉인 0 · 표 밖 자리 둘(4:56 「라틴 대소문자」 · 7:393 「보존 일곱」) 같은 처분 · 그대로 둔 표의 자리 15(갈래 이름이라 참)
- 바꾼 파일 — `parser/namefold.py`(새) · `core/state/surface_book.py`(새) · tagger · coord_pairs · dictionary · matcher · belongs · reconcile · result · scope_path · extract · prose · report_cause · query · ids(문서) · coord_learn · alias_book · store · paths · retry · rehearsal(core · cli) · migrate · init · oplog · _entry · rebuild · show_learn · knobs · ledger · build · heading · result_screen · report_md · 명세 2 · 4 · 7 · 부록 · 가이드(런북 · 2B · 인입 이해 · 상태 폴더) · 구조도(00 · 02 · 03 · 06 · 11) · CLAUDE.md(§5 한 자리 목록 · §7 ③진실 · fresh 보존) · 시험(dryrun_fold · alias_book · rebuild · ops_root · narrow) · DECISIONS
- 어서션 고침 하나 더 — B112 ⓔ 표본 파일명(`B112_전극리와인딩_사양` → `B112전극리와인딩사양` — 조각이 아닌 글 속의 가까운 이름을 잰다 · 기능 그대로)
- 사내 config 줄 — 0 · 머지 뒤 첫 실행이 「[표기 대장] 옛 두 파일을 옮겼다 …」 한 줄(옛 파일 보관) · `knobs.json`에 `owner_similar_pct`가 있으면 첫 실행이 「폐기한 키」로 멈춘다(그 줄을 지우고 다시)
- 소요 약 35분(이 기계 시각 05:56 반입 → 06:31) — 전제 · 읽기 4분 · ① 구현 · 시험 6분 · ② 설계 · 구현 9분 · ② 조각 실행 · 고침 7분(순환 import 하나 · 시험 셋) · ③ 구현 · 시험 4분 · 명세 패치 · 문서 5분 · 마감 한 줄 2회(각 2분 남짓) + 고침 둘
