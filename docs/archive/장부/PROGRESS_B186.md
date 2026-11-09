# PROGRESS — B186 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B186의 본문을 여기로 옮겼다(B190 마감 때).

## B186 — 온톨로지 맵(config 지도의 관계 그림을 카테고리 수준 지도로) · 두 끝이 같은 노드인 엣지는 세우지 않는다 + 정리 마감에서 잰 셋 (2026-11-06 · 칸 0.1 · 0.3 · 2.x · 3.4 · 문서)

> 요청문 `docs/안건/B186_요청문.md`(hub_163 반입 `bcf1db0` · B185 머지 `5031e0a` 위) · 단독 · 새 스위트 0 · 중간 · 트랙 마지막 구현 회차.

- 전제 10행 — 같다(28 · 135 · 305 / 33 · 240 · 419 / 255 · 266(순서만 — log_reject 255 · commit_edge 266) / 83 / 24 · 181 / 94 · 156 · 37 / 값 칸 자리 / 층 어휘 「위반 0건」) · 9행은 이 기계 파이썬 3.11이라 `SyntaxWarning` 대신 `DeprecationWarning`으로 같은 `\d`(3.12 · 3.13에서는 SyntaxWarning — 세 판 다 쟀다)
- ⓪ 별도 커밋 `92c77de` — ①옛 키 보고: `config_scope.renamed()` 한 자리로 「지금」도 새 키로 읽는다 → 키만 `pairs`인 사본의 보고는 「키 이름 바뀜」 한 묶음(이름 바뀜 0 · 새로 걸림 0 · 재구축 줄 0) · 지도 `--diff` 같다 ②`kit/gate_screen.py` 독스트링 raw · B185 ⓓ가 두 경고 다 잡고 `git ls-files -z`(한글 경로를 건너뛰던 것) — 3.11 · 3.12 · 3.13 모두 342파일 경고 0 ③test_g6_capture 「변환 실패」 원인 — **같은 사용자 프로필의 soffice 동시 실행은 나중 것이 결과 없이 rc 1**(결정적 재현 — 같은 프로세스 동시 변환 4 중 2 실패 · 매번) · 고친 자리 `render.run_soffice`(부를 때마다 자기 프로필) → 같은 재현 0/4 · 고친 것을 빼면 새 어서션이 붉다 · 전체 회귀 연속 3회 초록(2203/2201 · FAIL 0 ×3)
- 마감 한 줄 1회 — FAIL 0 · doctor 2208/2201 · 클린 2회 동일 그래프 · 네 벌 같다 · §7 상한 0 · 층 어휘 0 · 레포 쓰기 0 · 문서 검사 일곱 0 · 자산 해시 같다
- ⓐ PASS ⓪ 셋(위)
- ⓑ PASS 지도 — mock 고리 여섯(Failure causes · Property mirrors · Unit mirrors · 공정 part_of · precedes · 골격 극성 짝 mirrors) · controlled_by · occurs_in은 선 하나에 출처 둘(relation_patterns · schema: pfmea) · 종류 넷 · 그림의 고리는 점 밖이고 서로 40px 넘게 떨어진다(SVG 좌표로 잼)
- ⓒ PASS 실제 엣지 수 — CP01 · PFMEA01 상태에서 Failure causes Failure 32 = 그래프 32 · Unit part_of Process 13 = 13 · 0인 선은 「0 (선언만)」 · 클린(그래프 노드 0)은 수 칸 빔
- ⓓ PASS attributes — spec(cp · 맥락형) · 측정방법(cp) · 설비사양(value_categories) · severity(pfmea)
- ⓔ PASS 같은 노드 엣지 — PFMEA 사본(R4 원인 = 모드)에서 causes 엣지 0 · 거부 1(same_node · 두 표기 「전극 치수 불량」) · 인입 끝까지 · 그 노드의 affects · occurs_in 그대로 · 끝 줄 「같은 노드 엣지 1(표기가 다른 것 0)」 / 원인 칸을 사전 별칭으로 한 노드에 이은 사본은 「표기가 다른 것 1」 · `ops review` 다섯째 묶음 1줄(두 표기 · 다음 줄 `ops split` · `ops alias-reject`)
- ⓕ PASS 명세 패치 `--apply` · 층 어휘 0 · 마감 FAIL 0 · 네 벌 전부 같다(A 96/134 · 53/97 · 큐 112 · B 76/107 · 28/49 · 큐 71 · C 60/98 · 4/0 · 큐 15 · D 50/87 · 4/0 · 큐 4)
- 지도(mock 골격 상태) — 선 12 · 고리 6 · 골격 관계 3 · 소속 3 · 사실 관계 6 · 층을 넘는 관계 2 · 선언만 9(골격 상태 — 골격 관계 셋만 엣지 있음: part_of 45 · precedes 22 · mirrors 16) · attributes 6
- 어서션 +7 · 삭제 0 · 고침 5 — +B186 ⓐ ⓪(test_catalog — 키만 pairs) · ⓪ 동시 변환(test_g6_capture) · ⓑ ⓒ ⓓ(test_catalog) · ⓔ 둘(test_judge) · 고침: B185 ⓓ(두 경고 · -z) · B173 ⓒ(--diff에 그 선 줄) · B173 ⓓ(iframe → 지도 SVG) · B174 ⓑ(선 출처 줄은 「패턴 뺌」 삼항만) · B177 ⓑ(지운 color_axis 대신 점 색 = 칩 색 함수)
- 가결정 D-271(옛 키 읽기 자리 · soffice 프로필 · 경고 점검 · 그림 · 선의 종류 · 엣지 수 · 같은 노드 엣지의 기록 · 다섯째 묶음)
- 명세 패치 `B186_명세패치.md`(4항목 · +638자) `--check` → `--apply` · 문서 0 · 1 항목 0 · 재봉인 알림 0 · 표 밖 자리 0
- 보인 것 — 뷰어 `build_html(color_axis)`는 지도만 쓰던 인자라 지웠다(읽는 곳 0) · `title` 인자는 기본값으로만 남았다(그대로) · 지도 모델의 「선」이 옛 모양 → 제안 `--diff`에 「패턴 뺌」만큼 출처 변화를 낸다(제안 보고와 같은 사실)
- 사내 config 줄 — 0 · `python run.py export config`로 사내 층의 온톨로지 맵(실제 엣지 수 포함)
- 소요 약 30분(반입 02:24 → 마감 02:53 · 커밋 시각) — 전제 · 읽기 3분 · ⓪ 재현 · 고침 · 시험 7분 · 회귀 3회 7분(그동안 ①② 읽기 · 초안) · ①② 구현 6분 · 시험 작성 · 고침 4분 · 명세 · 가이드 2분 · 마감 한 줄 1회 2분
