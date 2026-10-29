# PROGRESS — B164 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B164의 본문을 여기로 옮겼다(B163 마감 때).

## B164 — anchor의 `target_category` 생략 = 좌표 카테고리(명세대로) · 값이 하나도 대상 목록에 없는 anchor 열은 등록 관문 G4K가 막는다 (2026-10-29 · 칸 3.2 · 1.5 · 문서)

> 요청문 `docs/안건/B164_요청문.md`(hub_140 반입 `c57be6e` = 시작 커밋 · PR #118 머지 `104e0a8` 위) · 단독 · 마감 한 줄 1회 · 구현 `d2e6374`.

- 전제 10행 — 같은 명령: `104e0a8` Merge #118 · 378 · 86 · 59 · 112 · 76 · 4 · 4 · `loop.py:378` · `bootstrap.py:87` · `cli/show.py:385`(`.get`) 셋 · 265 · 426 · 192 · 13 · 166 · 168 — 전부 요청문과 같다
- **본문 전제 하나가 실물과 다르다 — BLOCKERS 20**: 요청문 ② 「`doctor` [2′]가 같은 판정을 다시 돈다(지금 구조 그대로)」 — [2′]는 `kit/check_vocab.py`로 **스키마만** 대조한다(표본 0 · 어댑터 실행 0). G4K는 표본 값으로 재므로 [2′]에서 서지 않는다 · 만들지 않았다(선택지 셋 · 귀결은 BLOCKERS 20) · ① · ②의 나머지는 이것과 무관해 진행
- 마감 한 줄 2회 — 첫 회 FAIL 2(① test_p3_screen ②ⓑ — 목록 값을 싣는 깨지는 검체 `gate_break_tagger`를 G4K가 ④단에서 먼저 잡았다 → G4K는 낱값만 센다(목록 · 구조체는 ⑤단 G52의 몫) ② 경로 검사 — 시험 줄의 `"schemas" / "pfmea.json"` 표기 → `_P.fixture_schemas`) · 고친 뒤 둘째 FAIL 0 · 135초 · doctor 2122/2119 · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 상한 위반 0 · 문서 검사 일곱 0 · 자산 해시 다시 씀(`kit/` 셋)
- ⓐ PASS 좌표(`process_group` · `process_ref`)를 블록 없이 `fields`에 직접 적고 `target_category`를 뺀 스키마(임시 doc_type)로 PFMEA01 구축 — 예외 0 · 좌표 골격 노드로 가는 엣지 11/11이 블록 판과 같다
- ⓑ PASS 공정 아닌 anchor 열(`effect_category`)에서 `target_category`를 빼면 「[FAIL] G4K … anchor 열 'effect_category'의 값 0/32이 Process 목록에 있다 (target_category 생략 — 좌표 카테고리) — `target_category`를 그 값의 골격 카테고리로(공정이 아니면 반드시 적는다) · 골격이 없으면 골격부터」 · 원래 스키마는 PASS · 목록 · 좌표 층을 건네지 않은 킷 단독 실행은 「G4K 대조 생략」
- ⓒ PASS G4K FAIL 줄이 `classify_failures`의 자동 갈래(문답 0)
- ⓓ PASS 마감 한 줄 FAIL 0(둘째) · 네 벌 같다
- 어서션 +3 · 삭제 0 · 고침 0 — 더함: part_g6_struct B164 ⓐ ⓑ ⓒ(성질 — 생략이 좌표 카테고리로 해소된다 · 값이 대상 목록에 하나도 없으면 관문이 막고 문면이 고칠 키를 말한다 · 그 문면은 자동 지시)
- 가결정 D-247(킷이 좌표 카테고리를 받는 길 `--coord-category` · 대상 목록 · 판정 · 자동 지시 · 시험 자리 · [2′])
- 명세 패치 0(요청문대로)
- 보인 것(고치지 않음) — 가이드 `2B_작업가이드.md` §4 관문 태그 표(121행 근방)에 G4K 줄이 없다(자동 지시라 사람이 칠 명령은 그대로 — 요청문 「가이드 그대로」)
- 사내 config 줄 — 없음 · 사내 영향 — 재구축 불요
- 사내 다음 줄 — 반입 → `python doctor.py`(**[2′]에는 G4K가 서지 않는다** — BLOCKERS 20) → `python -m cli.register generate pfmea <층> <표본> --schema-only --hint "…"`(예방 · 검출 content · 영향 명칭 `target_category: FailureEffect` — 좌표의 `target_category`는 이제 적지 않아도 된다 · 관문에 G4K 줄이 선다) → `show schema pfmea` 앞뒤 대조 → confirm → `ingest-file`(KeyError 없이 판정 단계를 지나는지)
- PR #119 리뷰 고침(Codex P2 둘 — 머지 뒤라 새 PR · 사용자 확정) — ①목록 자리에 파일이 없으면(bootstrap 전) 모든 anchor 열이 0/n FAIL로 자동 재생성에 갔다 → 생략 줄 ②대상 카테고리의 집이 등록 층 · 좌표 층 밖이면 구축은 푸는 값을 G4K가 막았다 → 대상 노드를 스냅샷의 층 전부에서 고른다 · 어서션 +1(part_g6_struct B164 ⓓ — 성질: 집이 다른 층인 대상도 맞춘다 · 파일 없으면 생략) · D-247 ⑦ · 마감 한 줄 1회 FAIL 0 · doctor 2126/2125 · 네 벌 같음
- 소요 약 16분(이 기계 시각 07:43 → 07:59) — 반입 · 전제 · 코드 읽기 4분 · 구현(생략 규칙 · G4K · 플래그) 2분 · 시험 작성 · 고른 스위트 2회 3분 · 구조도 · 가결정 · BLOCKERS 1분 · 마감 한 줄 2회 4분(첫 회 FAIL 고침 2분 포함 · 기다리는 동안 B165 코드 읽기)
