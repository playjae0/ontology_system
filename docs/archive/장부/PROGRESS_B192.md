# PROGRESS — B192 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B192의 본문을 여기로 옮겼다(B197 마감 때).

## B192 — 층 호환 고침: config 문법 단 · 미리보기의 config · 지시문의 mock 예시와 위계 가정 · 화면 낱말 「골격 아래」 (2026-11-09 · 칸 0.1 · 0.3 · 3.x · 지시문 · 문서)

> 요청문 `docs/안건/B192_요청문.md`(hub_170 반입 `232cfef` · B190 머지 `b96b94a` 위) · 단독 · 중간.

- 전제 17행 — 같다(94 · 439 · 102 · catalog 9 · 80 · 113~139 · sync 138~140 · skeleton 49~51 · graph 246 · config_map 255 · bootstrap 68 · catalog 61 · 234 · 270 · 404 · 422 · human 182 · 184 · prompt_for 다섯 · 지시문 줄 · 등재 예외 넷 · 판 넷 · mock 힌트 · reconcile · show_summary · extract 212)
- 마감 한 줄 3회 — 1회 FAIL 2(참조 거부가 재대조 문면을 가로챔 · 상태 폴더 이름 문자열 · 시험 둘) → 2회 FAIL 1(시험 import) → 3회 FAIL 0 · doctor 2229/2222 · 클린 2회 동일 그래프 · 네 벌 같다 · §7 상한 0 · 층 어휘 0(예외 1) · 레포 쓰기 0 · 문서 검사 일곱 0
- ⓐ PASS 문법 단 — 층 키 오타(`relation_patern`) · 공통 `parent_pair` · 골격 `ALIAS` · `direction: "upward"` · JSON 쉼표 빠짐 → `bootstrap --dry-run` · `bootstrap` · `export config`가 같은 거부 문면(파일 · 키 · 가장 가까운 아는 키 · 다음 줄) · 인입(사전 점검)도 같은 줄 · rc 1 · 레포 mock 자산 거부 0 · 고침을 빼면 붉다(문면 0)
- ⓑ PASS 관계 패턴이 쓰는 카테고리가 categories · uses에 없다 → 거부(ⓘ · 세 명령 같은 줄)
- ⓒ PASS 미리보기 이름 = 인입 길(문서 층 quality ≠ home process · 극성 결합) — 고침을 빼면 붉다(극성이 빠진 이름)
- ⓓ PASS 지시문 — 층 어휘 점검 위반 0 · 예외 1 · 판 넷 오름 · 「이송 유닛」 예시는 mock 공정층 `prompts.extract` · 네 벌 같다
- ⓔ PASS 화면 — 인입 끝 한 줄 · `show summary` 문서 줄 「골격 아래」 · 옛 낱말로 저장된 요약 `--diff` 바뀐 줄 0
- ⓕ PASS ⓪ 둘 — 명세 패치 「지움」(표 행 · 줄바꿈까지 · 증감 −) · 동률이면 doctype 전부 이름순 한 줄씩
- ⓖ PASS 마감 FAIL 0 · 네 벌 전부 같다
- 이미 있던 것 / 새로 넣은 것 — 있던 것: 층 아는 키 `config_scope.layer_keys` · 뜻 검사 `catalog.problems` ⓑ~ⓖ · 겸 · 미러 경고 · 골격 트리 `SeedError` · `skeleton.type` 명시적 실패 · 스키마 쪽 참조(재대조 G4C — uses를 말하는 FAIL) · 옛 키 관문(옛 모양 · 손잡이로 옮긴 키) · 영향 범위 `RENAMED` 꼴 / 새로: 공통 아는 키 `config_scope.common_keys` · `COMMON_OTHER` · `PAIR_ITEM_KEYS` · `seed_keys` · 판정 `core/state/config_grammar`(ⓗ 문법 · ⓘ 관계 패턴 참조 · `read_json` · `syntax_errors` · `closed`) · 닫힌 값 상수 `graph.DIRECTIONS` · `catalog.PAIR_SRC` · `show_summary.RENAMED` · `spec_patch` 지움 항목
- 정한 것(D-275) — 아는 키는 영향 범위 표와 한 자리(`config_scope`) · 판정은 `catalog.problems`의 ⓗ ⓘ(네 자리 같은 함수) · 닫은 칸 7(`query_traverse` · `cross_layer_traverse`의 direction · recursive · `relation_patterns[].symmetric` · `mirrors.enabled` · `parent_pairs[].src`) · 참조는 관계 패턴만(스키마 몫은 G4C) · 화면 낱말 「골격 밖 노드」 · 「골격 아래 비율」
- 명세 패치 적용(+291자 · 문서 0 · 1 항목 0 · 재봉인 0) — 문서 7 §7.8(표 밖의 키 거부 · 낱말 셋) · 지시문 지금 판(e-2.2 · rf-1.3) · 문서 3 §3.1(dry-run 검사에 ⓗ ⓘ) · 부록(골격 아래 비율 · 한 줄 요약)
- 지시문 판 — 3.3 e-2.1 → e-2.2 · 3.4 rf-1.2 → rf-1.3 · 1.3 iv-2.1 → iv-2.2 · 1.4 1.11 → 1.12 · 사내 영향: 산문 추출 다시(반입 뒤 `rebuild`가 어차피 다시 뽑는다 — 같은 반입이면 더 드는 호출 0)
- 어서션 +8 · 삭제 0 · 고침 4 — +B192 ⓪ 둘 · ⓐ ⓑ(part_g6_catalog) · ②(part_g6_belongs) · ⓓ(test_g6_close) · ⓔ(part_g6_numbers) · 고침: B94 used_by(Property → Unit — 관계 패턴이 쓰는 카테고리를 빼면 이제 거부) · B170 ⓑ(지시문 파일 해시 고정 걷음 — 판독 절 0은 남은 대조가 잰다) · 구조 ⓑ · 맞춤 ⓓ(키 새 낱말)
- 바꾼 파일 — `core/state/config_grammar.py`(새) · `config_scope.py` · `catalog.py` · `bootstrap.py` · `core/graph.py` · `core/build/human.py` · `reconcile.py` · `extract.py`(주석) · `core/llm/gateway.py`(주석) · `cli/config_map.py` · `config_next.py` · `export_config.py` · `show_summary.py` · `ingest_select.py` · `run.py` · `tools/spec_patch.py` · `tools/layer_words.py` · 지시문 넷 · `layers/process/config.json` · 시험 일곱 · 가이드 넷 · 구조도 06 · 코드 지도
- 보인 것 — 추출 지시문 규약 11의 값 예(「장력」 · 「집진 용량」)와 생성 지시문 182행 「탭용접」은 mock 어휘 예시다(층 어휘 점검은 카테고리 이름만 센다) · 문서 4 25 · 282행의 「지시문 e-2.1」은 도입 판 표기
- 사내 config 줄 — 0(이 회차는 단일 반입에 든다)
- 소요 약 30분(반입 10:37 → 마감 11:07 · 커밋 시각) — 전제 · 읽기 4분 · 문법 단 9분 · 미리보기 4분 · 지시문 · 낱말 5분 · 시험 · 패치 · 문서 4분 · 마감 한 줄 3회 각 3분 + 고침 4분
