# PROGRESS — B128 (옮겨진 회차 · 본문)

> `PROGRESS.md`는 최근 3회차만 싣는다(CLAUDE.md §7). B128의 본문을 여기로 옮겼다(B130 마감 때).

## B128 — PPT 캡처가 실제로 돌게: 캡처 가능 판정 한 자리 · 실호출 PPT · PDF는 파싱 전에 그림 입력과 캡처 길 · 필요한 것은 한 곳 (2026-10-20 · 동작 변경 — 사전 점검 · 캡처 · 환경 점검)

> 요청문 `docs/안건/B128_요청문.md` · hub_103 반입 `eb9e50a` 위 · 가벼운 회차(개발 중 doctor 전체 0 · 고른 실행만).

- 전제 6행 — `112` · `113` · `613` · `148` · `0` · `render.py 65 · 110 · reader.py 448` (기대 그대로)
- 구현 환경 — PyMuPDF 1.25.5 · LibreOffice 24.2(`/usr/bin/soffice` · Impress 있음) · python-pptx 1.0.2 — 설치 없이 실경로가 돌았다
- 마감 한 줄 1회 — 전부 PASS(doctor 1980/1980 · 클린 2회 동일 그래프 · 네 벌 전부 같다 · §7 위반 0 · 자산 해시 같다 · 소요 490초)
- ⓐ PASS(실경로 · soffice를 뺀 PATH의 하위 실행): PPTX + 더 최신 PDF → 추출 호출 5 · 호출마다 캡처 1장 · PDF 문서도 같다(5쪽 · 각 1장 · PyMuPDF만으로)
- ⓑ PASS: soffice 없음 · 옆 PDF 없음 · 실호출 → 사전 점검 「캡처」에서 멈춤(파싱 0 · 빠진 것 「LibreOffice(Impress 포함 — soffice) 또는 … 더 최신 PDF」 · 다음 줄 `--no-capture`) · 같은 명령에 `--no-capture` → 진행 · 문서 대장 `capture_off` · 추출 입력에 그림 0
- ⓒ PASS: 게이트웨이가 그림을 거부(HTTP 400)하면 박힌 그림이 없는 PPT도 사전 점검 「그림」에서 멈춘다(다음 줄 `llm-check ⑦` · `--no-capture`)
- ⓓ PASS(이 기계에 soffice 있음): PPTX만으로 추출 호출마다 캡처 1장 · 숨김 슬라이드 하나를 더해도 렌더 5쪽 = 보이는 5장
- ⓔ PASS: `doctor --env`에 `pymupdf (선택)` · `soffice 있음 — /usr/bin/soffice`(실제 변환으로 쟀다) · `PPT 캡처 — 가능(soffice)` · `render.pymupdf()`가 `pymupdf` 모듈 · 폐기 경고 0
- ⓕ 네 벌 — 전부 같다(A · B · C — mock은 사전 점검 · 캡처를 타지 않는다)
- 실경로가 잡은 결함 하나 — `llm-check` ⑦의 거부 갈래가 `GatewayError.code`(없는 속성)를 읽어 그 자리에서 죽었다 → `status`(B128 전부터의 결함 — 실호출 400에서만 드러난다)
- 어서션 +5(`test_g6_capture`) · 기대 변경 2(`test_g6_deck` · `test_p1_csv` — 판정 함수의 이름 · 답 꼴) · 삭제 0
- 가결정 D-208(7건 — 판정 함수 자리 · soffice 변환 재는 법 · ⑦ 그림 만드는 법 · 사전 점검의 자리 · `--no-capture` 기록 · PyMuPDF 이름 · 시험의 실경로) · 명세 패치 `docs/안건/B128_명세패치.md` 4항목 `--check` 통과(문서 6 §6.4 규약 5 둘 · 문서 7 §7.6-B-0′ · §7.6-B-6)
- 바뀐 자리 — `parser/render.capture_path` · `pymupdf` · `render_pages`(길 그대로) · `parser/reader.read_pdf` · `extract_unit.capture` · `pipeline._page_map` · `core/llm/preflight`(단계 「캡처」 · 그림 입력 조건) · `cli/preflight.capture_docs` · `cli/ingest` · `ingest_batch` · `parse` · `rebuild`(`--no-capture` · 기록) · `core/llm/check`(⑦ 캡처 크기 그림) · `doctor --env` · `requirements.txt` · 런북 · 2B 증상표 · 구조도 02
- 사내 설치 줄 — `python -m pip install -r requirements.txt` + LibreOffice(Impress 포함 — 또는 PowerPoint에서 PDF로 저장해 같은 폴더 · 같은 이름으로) → `python doctor.py --env`의 `PPT 캡처 — 가능(…)` · `python run.py llm-check` ⑦ 통과
- 소요 약 23분 — 반입 1분 · 읽기 · 전제 · 환경 2분 · 구현 ①②③ 4분 · 시험 작성 · 실경로 디버그 4분 · 문서 · 명세 패치 · 장부 3분 · 마감 한 줄 1회 8분 · 장부 마감 1분
