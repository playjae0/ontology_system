# PROGRESS — B129 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B129의 본문을 여기로 옮겼다(B131 마감 때).

## B129 — soffice 찾기 한 함수: 지정 · PATH · 표준 설치 자리(macOS · Windows · Linux) · 캡처 · 그림 형식 변환 · 환경 점검이 같은 답 (2026-10-20 · 동작 변경 — soffice를 찾는 자리)

> 요청문 `docs/안건/B129_요청문.md` · hub_104 반입 `682151f` 위(브랜치는 병합된 main `f9f3fd8`에서 다시 시작) · 가벼운 회차.

- 전제 3행 — `47` · `render.py 194 · doctor.py 205` · `65` (기대 그대로)
- 마감 한 줄 2회 — 1회: doctor 1980/1984(옛 시험 셋이 `shutil.which`만 막고 「soffice 없음」을 쟀는데 표준 자리로 찾아졌다 — 기대 변경 둘 · `test_p1_wiring` 「파서 무판독」이 파서의 환경 읽기를 잡았다 → 지정 자리는 `bind_parser` 주입으로) · 2회: 전부 PASS(doctor 1984/1984 · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 위반 0 · 자산 해시 같다 · 소요 454초)
- ⓐ PASS(실경로 · soffice만 뺀 PATH의 하위 실행): 표준 자리 `/usr/lib/libreoffice/program/soffice`로 찾아 PPTX만으로 추출 호출 5 · 호출마다 캡처 1장
- ⓑ PASS: PATH · 표준 자리(후보 목록을 비워 가림)에 없고 `SOFFICE_PATH`=임시 폴더의 링크 → 「지정」으로 찾아 호출마다 캡처 1장
- ⓒ PASS: 셋 다 없으면 사전 점검 「캡처」 단계가 멈추고 「빠진 것」에 찾아본 자리(PATH · 표준 자리 · `SOFFICE_PATH`)
- ⓓ PASS: 같은 하위 환경에서 그림 형식 변환(BMP → PNG)이 같은 soffice로 돌고(가리면 「변환기 없음」) · `doctor --env`가 `soffice 있음 — /usr/lib/libreoffice/program/soffice(표준 자리)`
- ⓔ 네 벌 — 전부 같다(A · B · C)
- 어서션 +4(`test_g6_capture` 5 → 9) · 기대 변경 3(`test_g6_capture` B128 ⓑ · `test_p1_media` · `test_p1_csv` — 표준 자리 목록도 비운다) · 삭제 0
- 가결정 D-209(6건 — 찾기 함수 · 지정 자리의 이름 `SOFFICE_PATH` · 순서 지정 → PATH → 표준 자리 · 표준 자리 목록 · 시험의 가림 · 주입) · 명세 패치 `docs/안건/B129_명세패치.md` 1항목 `--check` 통과(문서 7 §7.6-B-6)
- 바뀐 자리 — `parser/render.find_soffice` · `SOFFICE_PLACES` · `use_soffice_given` · `_soffice` · `to_png` · `capture_path`(찾아본 자리) · `core/paths.bind_parser` · `doctor --env` · `requirements.txt` · 런북 · 2B 증상표 · 구조도 02
- 사내 설정 줄 — 표준 자리에 깔았으면 없음 · 다른 자리면 셸 설정 파일에 `SOFFICE_PATH=<soffice 경로>`(Windows는 환경 변수 설정에) → `python doctor.py --env`의 `soffice 있음 — <경로>(지정)`
- 소요 약 23분 — 반입 · 브랜치 다시 시작 2분 · 읽기 · 전제 1분 · 구현 ①② 2분 · 시험 작성 · 실경로(그림자 PATH) 2분 · 문서 · 명세 패치 · 장부 2분 · 마감 한 줄 2회 각 8분(사이 고침 — 주입 · 옛 시험 둘 1분)
