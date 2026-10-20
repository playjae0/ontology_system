# -*- coding: utf-8 -*-
"""칸 0.3 — 사내 이식 점검기 — **가져온 것이 온전한가 · 다음에 무엇을 해야 하는가** (국면 2 진입 도구).

    python doctor.py            점검 (환경 → 머리 상태 · 정합 · 설정 파일 → 상태 → 사내 전환 판정 — **회귀 0 · 몇 초** · B133 ③)
    python doctor.py --regress  점검 + 회귀 (반입 직후 한 번 — 36스위트 · 완료판정 4 · 기대 수 대조 · 몇 분)
    python doctor.py --env      환경만 (반입 직후 첫 실행 — 30초)
    python doctor.py --quick    기본과 같다(옛 이름 — 받고 한 줄로 알린다)
    python doctor.py --only <스위트…>          고른 스위트만 (개발 중 · **판정 아님** — B117 ①)
    python doctor.py --changed [<기준 커밋>]   바뀐 파일을 읽는 스위트만 (개발 중 · **판정 아님** · 고를 수 없으면 전체)
    … --list                                   고르기만 보고 돌리지 않는다
    … --serial · --jobs N                      회귀를 직렬로(레포 mock 루트) · 병렬 수(기본 4 근방 — 스위트마다 임시 자리 · B131 ①)
    … --why <스위트>=<사유>                    기대 수보다 적은 스위트를 사유와 함께 지나가게(기록은 마감 한 줄 · B131 ②)
    (회귀 쪽 선택지 — `--serial` · `--jobs` · `--why` · `--result` — 가 있으면 `--regress`를 친 것과 같다)

**왜 이 파일이 있나.** 레포를 사내로 옮기면 받는 사람은 "무엇부터 돌려야 하나"를 모른다.
문서를 다 읽게 하는 것은 답이 아니다 — **한 줄을 돌리면 현재 위치와 다음 한 걸음이
나오는 것**이 답이다. 그래서 이 파일은 설명하지 않고 **측정**한다.

**네트워크를 쓰지 않는다.** `USE_MOCK=1`(기본)에서 전 경로가 로컬로 돈다 — 사내 폐쇄망
에서 그대로 돌아간다는 것이 이 점검의 첫 결론이다.

**아무것도 고치지 않는다.** 읽고 재고 보고할 뿐이다. 상태 폴더는 회귀가 쓰고 지운다.

**운영 상태 폴더는 읽기만 한다**(B111 ① · 사내 실측 2026-10-15 — 실호출 셸에서 친 doctor의 클린이
`$ONTO_HOME`에서 돌았다). 진입점이 이 프로세스를 **격리 환경**으로 바꾼다(`gateway.isolate` — mock ·
기본 mock 루트 · `ONTO_*`·설정 파일·게이트웨이 키를 빼고) → 클린 · 시험 · 미설치 모사 · `run.py all` ·
질의 · 이 실행의 로그가 전부 그 환경을 물려받는다. 운영 루트에 대해 하는 일(머리 상태 줄 · 층 이름 ·
정합 · 설정 파일 줄 · 사내 전환 판정)은 **셸 환경 그대로의 하위 실행 하나**(`python -m cli.doctor_view <화면>` —
공통 진입을 지나지 않는다: 로그도 운영 루트에 쓰지 않는다)가 읽어 화면에 싣는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 회귀 스위트 — **각각을 클린 상태에서 단독 실행**한다(증분0 §8 실행 규약 · 병렬이면 스위트마다 제 임시 루트 — B131 ①).
# 연속 실행은 판정 규격이 아니다: 스위트가 `data/`를 공유해 순서 의존이 관측됐다.
# `(이름, 무엇)` 또는 합친 스위트는 `(이름, 무엇, 앞 이름들)` — **기대 수는 여기 없다**(생성물 `docs/회귀스위트/기대_수.json` ·
# 마감 한 줄이 쓴다 · B131 ②).
SUITES = [
    ("test_g1_g2", "저장 계층 · 근거 축 id · 부트스트랩 · 런타임 경계 · core 경계 3종 · GraphStore 전용 · 저장 레코드 스키마 · 진입점 계약"),
    # **자리는 따로 돈다**(B79 — `test_g1_g2` 834행 분할): 저장·주소 규격과 자리
    # 배치는 바뀌는 이유가 다르다.
    ("test_places", "자리 소유자·자리가 가른다·모듈 머리말·코드 지도 재생성 · B79 층 자산 상태 루트·미정의 이름 0·루트 출처·레포 정본 자산 해시 · B80 ⓪원본 `raw/`"),
    ("test_g3", "인입 계약 v2 · 추출 분리 · 커밋 게이트 · 하강 부착"),
    ("test_query", "질의 4단 · 품질층 · 재인입 회귀 · query --json · 뷰어 서버 · 골든셋 · BM-25 · 공유 별칭 범위 해소 · 링킹 임베딩 후보 + LLM 선별 · 문서 검색 채널 · 짧은 답 · 채점",
     ("test_g4", "test_g6_hybrid",)),
    ("test_ops", "I축 4연산 + 이관 · ops confirm · ops alias · 플랫폼 창구 · 2층+cross 표시 · 큐 열람 · 계기판 8종",
     ("test_g5", "test_g6_platform",)),
    ("test_intake", "지문 스캔 · mock 격리 · 일괄 투입 조건 · 상태 거부 문면 · 원본 자리 · 내장은 mock일 때만 · 등록부 결손 거부 · 시트 역할 관문 · 렌즈 · 시트 두 모드 · 사내 손잡이",
     ("test_g6_scan", "test_g6_batch", "test_g6_registry", "test_g6_sheets", "test_g6_lens",)),
    ("test_ingest_view", "인입 화면(예고 · 큐 집계 · 다음 줄 · --step · 값 줄) · 추출 예고 · 청크 메타 · 이어 쓰기 · 비용 전 사전 점검 · 설정 파일 줄 · 숫자와 기준(한 줄 요약 = 맞춤표 · 점수표 · 묻는 자리 · 거부 묶음)",
     ("test_g6_ingest", "test_g6_extract_view", "test_g6_preflight_view", "test_g6_numbers",)),
    ("test_coord", "좌표 층 이름 해방(카테고리로 찾는다 · 이름 바꾼 루트 등가) · 좌표 쌍(상위를 범위로 하위 해소 · 관문 G4I · 확인함) · 시스템이 아는 값은 LLM이 쓰지 않는다 · 좌표 태깅 상한",
     ("test_g6_coord_layer", "test_g6_coord_pairs", "test_p1_coord",)),
    ("test_catalog", "카탈로그 거부 · 초안 · 전역 해소 · 주 · 겸 · 맞추기 · dry-run 같은 검사 · 라틴 2차 대조 · 재시도 되살아남 0 · 등록 골격 목록 · 관문 G4H · 집 이동 동치 · 골격 밖 반복 판정 기억",
     ("test_g6_catalog", "test_g6_catalog_sync", "test_g6_dryrun_fold", "test_g6_struct",)),
    ("test_safety", "층 이름 = 폴더 이름 · 어떤 예외든 되돌림 · 화면 전체를 명령 로그로 · 로그 보존 · 화면이 닫혀도 트레이스백 0 · 하위 실행 표준입력 0 · 사람이 멈춘 문서는 시작 전 · 운영 폴더는 점검이 읽기만 · 운영 루트 클린은 묻는다 · 재구축 사전 점검 · 이어 가기",
     ("test_g6_safe_log", "test_g6_log_pipe", "test_g6_stop_chunks", "test_g6_ops_root",)),
    ("test_judge", "판정 진단 · 같은 문서 auto 매칭 · 좌표 학습 · 2단 판정 · md 보고서 · 재생의 불확실은 2차 한 번 · 후보 상한 · 조건부 retry · 판정 대장 · 임베딩 선택",
     ("test_g6_diag", "test_g6_synonym", "test_g6_judge2", "test_g6_replay2", "test_g6_narrow",)),
    ("test_build", "맥락 줄 · 문서 좌표 · 소속 · 산문의 값 · 다른 공정 이름은 관련 링크 · 빈칸 표시 · 재연결 · 맞춤표 · 시트 숨김 · 청크 목차",
     ("test_g6_belongs", "test_g6_values", "test_g6_relink", "test_g6_reconcile",)),
    ("test_rebuild", "fresh 보존 · --all 클린 · 재구축 한 명령(동치 · LLM 0) · 판정 재생 · 옛 기록에 이름 채우기 · 태깅 null 기억 · 별칭 대장 · 재구축 동치",
     ("test_g6_rebuild", "test_g6_rebuild_memory", "test_g6_alias_book",)),
    ("test_g6_rehearsal", "B116 — 추출 리허설은 임시 상태 루트(하위 실행 · 운영은 읽기만): 이미 인입된 문서(렌즈판이 있는 루트)를 표본으로 등록 세 단계 전후 운영 지문 같음(층 하나) · ②구획 채워짐 · 리허설 산출 자리(추출 · 개요) · 안내 줄 · 같은 조건(실호출 · 상태 루트 llm.json · 손잡이) · 새 종류 인입 추출 · 개요 LLM 0 · 원래 종류는 지금 규칙 · 부분 · 실패 · 중단(Ctrl-C) 흔적 0"),
    ("test_structure", "문서 구조(시트마다 · 검사 · 구조 관문) · 구조 v2 · edit · 구조 확인 · 문서 규칙 힌트 · 산문 엑셀 계층 · 목차 · 청크 경로 · 글자 상한 · 문서 개요 · 폴백 사슬 · 연결 보강 · PPT 덱 구조",
     ("test_g6_structure", "test_g6_structure2", "test_g6_split", "test_p1_hier", "test_g6_outline", "test_g6_deck",)),
    ("test_g6_capture", "B128 · B129 — PPT 캡처 실경로(렌더 · 판정 함수 대역 없음): 옆 PDF · PDF 문서(soffice 없는 PATH에서 호출마다 캡처 1장) · 캡처 길이 없으면 사전 점검에서 멈춤(파싱 0 · --no-capture면 진행 + 기록) · 그림 입력 거부면 그림 없는 PPT도 멈춤 · soffice면 PPTX만으로(숨김 슬라이드 쪽 맞음) · doctor --env 줄 · import pymupdf · soffice 찾기 한 함수(PATH 밖 표준 자리 · SOFFICE_PATH 지정 · 없으면 찾아본 자리 · 그림 형식 변환 · doctor 같은 답)"),
    ("test_g6_close", "B117 · B121 — 마감 도구는 판정을 느슨하게 하지 않는다: 네 벌 C 같은 커밋 같다 · 폴백 사슬 끈 사본 C만 다르다 · doctor --only 하나만 · 머리 · 합계 · 로그에 「고른 실행 — 판정 아님」 · 모르는 이름 rc 2 · --changed ⊇ 실행 기록 표본(레포 사본 core 하나 · 자산 폴더 → 전체) · 마감 한 줄 여덟 단계 끝까지 · FAIL rc 1 · 명세 패치 --check 항목 이름 · --apply 어긋나면 쓰기 0 · 명세 패치 미러 재봉인 알림(다른 검사가 늘면 쓰기 0) · 층 어휘 정적 점검(지금 0 · 사본 core에 넣으면 붉다) · 명세 모양 늘면 위반 · 줄면 내림"),
    ("test_contract", "재인입 · 인입 검증 계약 · 닫힌 계약 배선 · 병합 무손실 · 걸침층 배선 · 인입 순서 무관 결정성 · provenance · 좌표 부재 처분 · 반대 방향 연속 금지 · 빌드 소요 · 재등록 승인",
     ("test_g65_contract", "test_g65_cross", "test_g65_prov", "test_g65_rules",)),
    # **P1 · P3는 칸별이다**(B78 2b · 2c) · 회차 이름 스위트는 칸 하나로 합쳤다(B131 ④ — 조각은 `tests/part_*.py`).
    ("test_p1_core6", "골격 스냅샷 · 코어 6종 계약 · preflight/계약 위반 · 기본 어댑터 · 역산 정합 · 지도 경로"),
    ("test_p1_wiring", "파서 무판독 · ⑦ 예산 초과 폴백 · 생성 하네스 3단 · 조각 공통 층"),
    ("test_p1_csv", "CSV reader 구조 등가 · 인코딩·구분자 판정 · PPT/PDF 임계 경로"),
    ("test_p1_form", "스프레드시트 산문 레벨 규칙 · 형태 판정(시트 역할 — 입구는 시트마다 · 역할 뒤 prose 시트) · 관문 ③④의 시트 역할 · 큐 case 두 값"),
    ("test_p1_media", "리더의 폭(B88) — 엑셀 그림 → ④(ref·skip 0 · 변환·건너뜀 사유 · --no-images 기록 · 재사용) · docx(개요 수준·번호·표·그림·삭제 0·.doc 거부) · 등록 doc_type status(운영 어댑터)"),
    ("test_p2", "어댑터 생성 킷 6종 · 검수 뷰 렌더러 · 지도 필드 셋 · B76 스켈레톤 최소 어댑터·형 검사 G4F · B77 전시물 실행 관문"),
    ("test_p3_register", "등록부 조회 · 구축 모드 전 과정(S1) · 1부 경고 · 정형 등록(S15)"),
    ("test_p3_prompt", "골격 확정 · 전송 프롬프트 · 문답 어휘 주입 · 열 프로파일 · 예산"),
    ("test_p3_gate", "스키마 strict · 오류 본문 · 분할 레벨 · mock 관문 · --resume"),
    ("test_p3_view", "모든 열은 판정을 갖는다 · 하네스 자동 갈래 · 추출 리허설"),
    ("test_p3_recover", "재생성 지시 · 문답 누적 · 청크 단위 실패 · 지도 무효화 · llm-check"),
    ("test_p3_screen", "관문 전 구간 · 막는 이유와 다음 줄 · status·confirm 재실행 · 확정 요약"),
    ("test_p3_ledger", "관문이 채우고 찍는다 · columns 값 셋 · 어휘 정적 대조 · 형태 판정 문의"),
    ("test_p3_flow", "지문·미선택 갈래 · CSV 등가 · 열 판정 대장 · 분할 줄 · 좌표 예고 · G39·G4G"),
    ("test_2a_gateway", "게이트웨이 골조 — 12지점 도달 가능성 · **12지점 본문 스모크**(B79 ③ⓒ · ⑩시트 역할 B91 · ⑪문서 개요 · ⑫연결 보강 B115) · ⑦ 배선 · 변이 시험 · B63 대장 잠금 · **B80 요청 조립(CHAT_TEMPERATURE)·임베딩 백엔드 gateway|local**"),
    # **뷰어는 세미 플랫폼이다**(B82) — headless로 잰다(브라우저 의존 0).
    ("test_viewer", "뷰어 서버(쓰기 0 · 자리 탈출 거부) · 벤더링 렌더러 · 질의 trace 계측 · 연결 현황 · B84 테마 대비·다시 칠하기·상호작용·오류 문면 · B103 배치 셋·닻·연결 없는 노드·이웃·노드 상세의 근거 · B114 힘 배치 워커(시간 끊기 0 · 난수 0) · 크기 계단 · 힘 손잡이 · 벡터 이어 만들기 · 진행 줄 · 질의 단계 · 상태 라우트 GET만"),
    ("verify_roundtrip", "raw 실물 ↔ 계약 JSON 역산 정합"),
    # **사내 조건 · 사내 모양을 상시로 돈다**(B71 ② · B86) — 나머지 전부가 `USE_MOCK=1`이라 사내에서 처음 밟는 자리를 사용자가 찾아 왔다.
    ("test_site", "USE_MOCK=0 · 픽스처 없음 · 등록 산출만 · 이관 등가 · 사내 모양 잔여(화면 경로 · 파서 자리 주입 · 등록 표본 시트 관문) · 레포 밖 상태 루트에서 등록부터 뷰어 · doctor --quick까지 등가",
     ("test_onsite", "test_g6_shanae_parts", "test_g6_shanae_root",)),
]

# **필수는 없다.** 문서 포맷 패키지는 **선택 의존**이다(문서 7 §7.1) — 지연 import로
# 격리돼 있어 `USE_MOCK=1` 전 경로가 이것들 없이 완주한다. 아래 「미설치 실측」이
# 그것을 매번 실행으로 확인한다. REQUIRED로 두면 폐쇄망 반입 첫 화면이 실제로는
# 없어도 되는 것을 [필요]로 띄워 다음 사람을 헛되이 멈춰 세운다.
REQUIRED = []
OPTIONAL = [("orjson", "그래프 직렬화 가속 — 없으면 표준 json으로 돈다"),
            ("openpyxl", "xlsx 읽기 — 파서 전용·지연 import"),
            ("pptx", "pptx 읽기 — 파서 전용·지연 import (패키지명 python-pptx)"),
            ("pymupdf", "PDF 읽기 · 쪽 렌더(PPT · PDF 캡처) — 지연 import (패키지명 PyMuPDF · 옛 판은 fitz)"),
            # **로컬 임베딩**(B80 ③) — `EMBED_BACKEND=local`일 때만 부른다.
            ("sentence_transformers",
             "로컬 임베딩 — EMBED_BACKEND=local일 때만 · 지연 import "
             "(패키지명 sentence-transformers)")]

# 화면 원자 — 마크 · `line` · `head` · [필요] 수는 운영 화면과 같은 것을 쓴다 (`cli/doctor_view` · B111 ①)
from cli import doctor_view as V                                     # noqa: E402 — core를 import하지 않는다
from cli import doctor_select as sel                                 # noqa: E402 — 고르기(B117 ① · 판정 아님)
from cli.doctor_view import NEXT, NG, OK, WARN, head, line           # noqa: E402,F401

# 격리 전의 셸 환경 — 진입점이 남긴다. `None`이면 이 프로세스가 곧 셸 환경이다(`main`을 바로 부른 시험).
_SHELL_ENV = None


def operating(part):
    """**운영 상태 폴더를 읽는 화면 하나**(B111 ①) — 셸 환경 그대로의 하위 실행에서 그리고 여기 싣는다.

    이 프로세스는 격리 환경이라(머리말) 운영 루트를 모른다 — 루트는 프로세스당 한 번 정해지고 모듈 상수가
    그 자리를 잡으므로, 같은 프로세스에서 두 루트를 오가지 않고 셸 환경의 프로세스 하나가 읽는다. 그 하위
    실행은 공통 진입을 지나지 않는다(로그 · 대장 채움을 운영 루트에 쓰지 않는다). [필요] 수는 끝 줄로 받는다.
    """
    if _SHELL_ENV is None:
        V.VIEWS[part]()
        return
    r = subprocess.run([sys.executable, "-m", "cli.doctor_view", part],
                       capture_output=True, text=True, cwd=str(ROOT), env=_SHELL_ENV,
                       stdin=subprocess.DEVNULL)
    out = r.stdout.splitlines()
    if r.returncode == 0 and out and out[-1].startswith(V.NG_TAIL):
        if out[:-1]:
            print("\n".join(out[:-1]))
        V.add(int(out[-1][len(V.NG_TAIL):]))
        return
    if out:
        print("\n".join(out))
    err = (r.stderr or "").strip().splitlines()
    line(NG, f"운영 상태 폴더 읽기({part})가 끝나지 않았다 — rc={r.returncode}",
         err[-1] if err else "(stderr 없음)")


def _clean():
    """클린 상태 — **`run.py init --fresh --all`이 정의한다**(문서 7 §7.6-4 · B106 ① — 기본 fresh는 보존이다).

    반환은 `(returncode, 잔재 경로 목록)`이다. 여기서 rmtree를 제 손으로 하면 "클린"의 정의가 doctor와 테스트와
    완료판정에서 각자 달라진다 — 한 자리(`cli/doctor_run.clean`)가 부르고 지운 결과를 실제로 확인한다
    (fresh의 지우기는 `ignore_errors=True`라 권한 문제로 실패해도 조용하다 — 회귀 규약 §7.5-7).
    """
    sys.path.insert(0, str(ROOT))
    from cli import doctor_run                                      # noqa: E402
    return doctor_run.clean()


def _capture_lines(probe=True):
    """**PPT · PDF 캡처**(B128 ③) — soffice(Impress · 실제 변환)와 판정 한 자리(`parser.render.capture_path`)의 답 한 줄.
    실호출 PPT · PDF 인입은 사전 점검이 같은 함수로 멈추므로 여기 답이 곧 그 답이다(문서마다 옆 PDF는 따로 잰다)."""
    from core import paths                                  # noqa: F401 — 파서 주입(soffice 지정 자리 — B129 ①)
    from parser import render
    exe, where, tried = render.find_soffice()               # 찾기 한 함수 (B129 ①)
    ok, route, miss = render.capture_path(probe=probe)      # 실제 변환은 `--env`만(몇 초 — 전체 · --quick은 Impress 구성 요소로)
    line(OK if exe else WARN, f"soffice {'있음 — ' + exe + '(' + where + ')' if exe else '없음'}",
         ("LibreOffice — PPTX → PDF 변환(캡처 길 하나 · Impress 포함 · " + ("실제 변환으로 쟀다)" if probe else
                                                                     "구성 요소로 쟀다 — 실제 변환은 --env)")) if exe
         else f"찾아본 자리: {tried} — LibreOffice(Impress 포함)를 표준 자리에 깔거나 다른 자리면 셸 설정 파일에 "
              f"{render.SOFFICE_ENV}=<soffice 경로> · 또는 PowerPoint에서 PDF로 저장해 같은 폴더 · 같은 이름으로")
    line(OK if ok else WARN, f"PPT 캡처 — {'가능(' + route + ')' if ok else '불가'}",
         "PPT · PDF 실호출 인입은 사전 점검에서 이 길과 그림 입력(llm-check ⑦)을 잰다" if ok
         else f"빠진 것: {miss} — 실호출 PPT 인입은 사전 점검에서 멈춘다(캡처 없이는 --no-capture)")


# ================================================================ ① 환경
def check_env(probe=False):
    head("① 환경 — 이 기계에서 돌아가는가")

    v = sys.version_info
    line(OK if v >= (3, 10) else NG, f"Python {platform.python_version()}",
         "3.10 이상이 필요하다 — 코드가 sys.stdlib_module_names(3.10 신설)를\n         쓴다. 개발·검증은 3.11에서 했다"
         if v >= (3, 10) else "3.10 미만이면 돌지 않는다 (문서 7 §7.1 런타임 전제)")

    for mod, why in REQUIRED:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "")
            line(OK, f"{mod} {ver}".strip(), why)
        except ImportError:
            line(NG, f"{mod} 없음", f"{why} — 없으면 파서(parser/)가 돌지 않는다. "
                                    f"코어·질의는 이것 없이도 돈다")
    # **있는지만 본다 — 부르지 않는다**(B80 ③): 선택 의존은 지연 import가 규율이고
    # (문서 7 §7.1), 점검기가 그것을 통째로 import하면 「USE_MOCK=1 경로에서
    # import 0」을 재는 자리가 스스로 그 규율을 어긴다. 로컬 임베딩 모델 패키지는
    # 무겁기도 하다 — 없는지 있는지는 `find_spec`으로 답이 난다.
    import importlib.util as _ilu                                   # noqa: E402
    for mod, why in OPTIONAL:
        try:
            found = _ilu.find_spec(mod) is not None or (mod == "pymupdf" and _ilu.find_spec("fitz") is not None)
        except (ImportError, ValueError):
            found = False
        line(OK, f"{mod} (선택)" if found else f"{mod} 없음 (선택 — 문제 아님)", why)
    _capture_lines(probe)
    # **CSV는 의존이 없다** — 표준 `csv` 모듈이라 선택 의존 목록에 오르지 않는다.
    line(OK, "csv/tsv 읽기 (표준 라이브러리)",
         "reader가 받는 포맷: .xlsx · .xlsm · .pptx · .csv · .tsv — "
         "CSV는 설치할 것이 없다")

    # **코어는 stdlib만 쓴다** — 반입에서 가장 중요한 사실이라 실측해 보인다.
    # 선택 의존(`try: import … except ImportError:` 폴백)은 필수가 아니므로 뺀다 —
    # 없어도 도는 것을 "예상 밖"이라 부르면 그 경고가 다음 사람을 헛되이 멈춰 세운다.
    # **포맷 패키지 미설치 상태로 전 경로가 완주하는가** — 실측한다(문서 7 §7.1).
    # "요구하지 않는다"까지만 두면 모듈 최상단 import가 문면상 위반이 아니게 되어,
    # 미설치 환경에서 USE_MOCK=1 전체 실행이 ImportError로 죽는 것을 아무도 모른다.
    guard = Path(tempfile.mkdtemp(prefix="doctor_noformat_"))   # 함께 도는 doctor끼리 갈리게(B131 ①)
    (guard / "sitecustomize.py").write_text(
        "import builtins\n_real = builtins.__import__\n"
        "def _g(n, *a, **k):\n"
        "    if n.split('.')[0] in ('openpyxl', 'pptx'):\n"
        "        raise ImportError('미설치 모사: ' + n)\n"
        "    return _real(n, *a, **k)\n"
        "builtins.__import__ = _g\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(guard), USE_MOCK="1")
    _clean()
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                       capture_output=True, text=True, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    q = subprocess.run([sys.executable, str(ROOT / "run.py"), "query",
                        "노칭 다음 공정은?", "--allow-mock"],   # 진단은 관문 비대상
                       capture_output=True, text=True, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    shutil.rmtree(guard, ignore_errors=True)
    ok_np = r.returncode == 0 and q.returncode == 0 and "[그래프 사실]" in q.stdout
    line(OK if ok_np else NG,
         "포맷 패키지 미설치 상태로 전 경로 완주" + ("" if ok_np else " — 실패"),
         "openpyxl·python-pptx를 import 불가로 막고 build+query를 실행했다 — "
         "선택 의존이 실제로 격리돼 있다" if ok_np
         else (r.stderr or q.stderr).strip().splitlines()[-1:] and
              (r.stderr or q.stderr).strip().splitlines()[-1])

    optional = {m for m, _why in OPTIONAL}
    hard = set()
    for f in (ROOT / "core").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for m in re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", src, re.M):
            hard.add(m)
    hard -= {"core", "router"} | optional | set(sys.stdlib_module_names)
    line(OK if not hard else WARN,
         f"코어 필수 외부 의존 {len(hard)}종",
         "core/는 표준 라이브러리만 쓴다 — **폐쇄망에서 설치 없이 돈다**"
         + (f" (선택 의존 {sorted(optional)}는 폴백 있음)" if optional else "")
         if not hard else f"예상 밖: {sorted(hard)}")

    operating("config")         # 운영 셸의 모드 · 설정 파일 — 읽기만 (B111 ①)

    # **레포 정본 자산이 레포 판인가**(B79 ④ · 사용자 확정 2026-09-21) —
    # `prompts/`·`kit/`·`schemas/blocks.json`·(레포)`layers/`는 사내에서 고치지 않는다.
    # 고치면 「어느 판으로 잰 결과인가」가 사라진다 — 고칠 것은 허브로 요청한다.
    sys.path.insert(0, str(ROOT / "tests"))
    from asset_hashes import diff as _asset_diff, RECORD as _asset_rec  # noqa: E402
    _chg, _add, _gone = _asset_diff()
    if not (_chg or _add or _gone):
        line(OK, "레포 정본 자산이 레포 판이다",
             f"prompts · kit · schemas/blocks.json · layers(seed) — 기록 {_asset_rec.name}")
    else:
        line(WARN, "레포 정본 자산이 레포 판과 다르다 — 사내에서 고치지 않는다(허브로 요청)",
             " · ".join([f"다름 {x}" for x in _chg] + [f"기록 없음 {x}" for x in _add]
                        + [f"사라짐 {x}" for x in _gone])[:400])

    try:
        fd, probe = tempfile.mkstemp(dir=str(ROOT), prefix=".doctor_write_probe_")   # 이름은 실행마다(B131 ①)
        os.close(fd)
        os.unlink(probe)
        line(OK, "레포 쓰기 권한", "상태 폴더(등록·진실·작업)를 만들 수 있다")
    except OSError as e:
        line(NG, "레포 쓰기 권한 없음", f"{e} — 실행 산출물을 만들 수 없다")

    return V.fails() == 0


def _idempotent(serial=True):
    """**클린 2회 동일 그래프** — 구현 국면 완료판정 4번 (문서 7 §7.6-4) · `(통과, 덧말)`.

    이 판정을 세는 것이 여태 없었다. 시나리오 통과만 세면 멱등성이 조용히 깨진 상태로도 판정이 통과한다(B55 ⑨ — 클린 함수의
    복사본이 이 계측을 도달 불가로 만들고 있었다). 대조 단위는 셋 — 그래프는 바이트 동일 · 큐는 `(kind, doc_id, payload)`
    **집합**(재인입이 비상시 큐를 회수한 뒤 다시 싣는다 — 증식 · 유실이 없다는 것이 멱등성) · 거부 로그는 관측 신호라 계수만.
    병렬이면 제 임시 루트에서 스위트와 함께 돈다(`cli/doctor_run.idempotent` — B131 ①).
    """
    from cli import doctor_run
    return doctor_run.idempotent(serial)


# ================================================================ ② 자체 검증
def _why(name, r, p, expect):
    """실패한 스위트의 **원인을 화면에 낸다** — 사내망은 출력을 밖으로 못 가져온다.

    구판은 원인을 숨겼다: ①`[PASS]`가 하나라도 찍히면(`p > 0`) stderr를 아예 안 냈고
    ②내더라도 **마지막 1줄**이라 traceback의 원인 줄(ImportError·UnicodeEncodeError)이
    화면에 오지 않았다. 그래서 "8건 [필요]"만 뜨고 왜인지 알 방법이 없었다.
    """
    fails = [ln.strip()[:110] for ln in r.stdout.splitlines() if "[FAIL]" in ln]
    for ln in fails[:5]:
        print(f"           {ln}")
    if len(fails) > 5:
        print(f"           … 외 {len(fails) - 5}건")

    err = (r.stderr or "").strip()
    if err and (r.returncode or p != expect):
        # **마지막 15줄** — 원인 줄은 traceback 끝에 있다. p>0인지와 무관하게 낸다:
        # 스위트가 중간에 크래시하면 앞선 [PASS]가 남은 채 죽는다.
        tail = err.splitlines()[-15:]
        print(f"           ── stderr (마지막 {len(tail)}줄) ──")
        for ln in tail:
            print(f"           {ln}")
    elif not err and p < expect:
        # stderr가 비었는데 PASS가 모자라면 **조용한 조기 종료**다 —
        # 어디까지 갔는지는 stdout 끝에만 남아 있다.
        tail = r.stdout.strip().splitlines()[-10:]
        print(f"           ── stdout 끝 {len(tail)}줄 (조용한 조기 종료) ──")
        for ln in tail:
            print(f"           {ln}")
    print(f"           재현: python tests/{name}.py")


def _env_diff(clean_rc, residue):
    """②가 실패했을 때만 내는 **환경 차이 표** — 사람이 판단할 재료다.

    같은 커밋이 한 기계에서 526/526이고 다른 기계에서 아니면 원인은 코드가 아니라
    환경이다. 그 후보를 화면이 스스로 지목한다 — 사내망에서는 출력을 밖으로 가져와
    물어볼 수 없으므로, **진단이 화면에서 끝나야 한다.**
    """
    print("\n  ── 환경 차이 점검 (② 실패 시에만 낸다) ──")
    rows = []

    enc = (sys.stdout.encoding or "").lower()
    rows.append((OK if "utf" in enc else WARN, "표준 출력 인코딩", enc or "(불명)",
                 "utf-8이 아니면 한글 출력에서 스위트가 죽는다 — "
                 "PYTHONIOENCODING=utf-8 로 다시 돌려 본다"
                 if "utf" not in enc else "한글 출력이 안전하다"))

    fse = (sys.getfilesystemencoding() or "").lower()
    rows.append((OK if "utf" in fse else WARN, "파일시스템 인코딩", fse or "(불명)",
                 "한글 경로·파일명 자산이 있다 — utf-8이 아니면 못 연다"
                 if "utf" not in fse else "한글 경로를 연다"))

    v = sys.version_info
    rows.append((OK if v >= (3, 10) else NG, "Python 버전", platform.python_version(),
                 "3.10 미만은 문법부터 죽는다" if v < (3, 10) else "개발·검증은 3.11"))

    crlf = None
    for f in sorted((ROOT / "tests").glob("*.py")):
        crlf = b"\r\n" in f.read_bytes()
        break
    rows.append((WARN if crlf else OK, "줄바꿈", "CRLF" if crlf else "LF",
                 "git autocrlf가 켜져 파일이 바뀌었다 — core.autocrlf=false 로 다시 클론"
                 if crlf else "원본 그대로다"))

    cwd = os.getcwd()
    same = Path(cwd).resolve() == ROOT
    rows.append((OK if same else NG, "작업 디렉터리", cwd,
                 "레포 루트가 아니다 — 상대 경로가 깨진다. 루트에서 다시 돌린다"
                 if not same else "레포 루트와 같다"))

    rows.append((OK if (clean_rc == 0 and not residue) else NG,
                 "작업 단(parsed·extract) 잔재",
                 "없음" if not residue else ", ".join(residue),
                 "클린이 조용히 실패했다(권한?) — 순서 의존이 살아 있어 "
                 "단독 실행 판정이 성립하지 않는다"
                 if (clean_rc or residue) else "run.py init --fresh --all이 실제로 비웠다"))

    # 한글은 터미널에서 **두 칸**을 먹는다 — `len()`으로 맞추면 열이 어긋난다.
    def _w(s):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

    w = max(_w(a) for _m, a, _b, _c in rows)
    for mark, what, val, why in rows:
        print(f"  [{mark}] {what}{' ' * (w - _w(what))}  {val}")
        print(f"         {why}")


def run_suites(quick=False, names=None, serial=False, jobs=None, why=None, result=None):
    """회귀 — `names`를 주면 그 스위트만(고른 실행 — 판정 아님 · 완료판정 4 「클린 2회」는 재지 않는다).

    병렬(기본)은 스위트마다 제 임시 mock 루트 · 직렬(`serial`)은 레포 mock 루트에서 차례로(B131 ①) · 기대 수는 기록 파일
    (`cli/doctor_run` 머리말 ⓐ~ⓓ — B131 ②) · `result`가 있으면 스위트마다 수를 그 파일에 적는다(마감 한 줄이 기록을 쓴다)."""
    from cli import doctor_run as DR
    why = why or {}
    head(("② 자체 검증 — 회귀는 따로 부른다" if quick else "② 자체 검증 — 가져온 것이 온전한가 (회귀 전체)") if names is None
         else f"② 고른 스위트 {len(names)}종 — {sel.HEAD_LINE}")
    if quick:
        print(f"  회귀는 따로 부른다 — {REGRESS_CMD}(반입 직후 한 번 · 몇 분) · 기본 doctor는 점검만(회귀 0)")
        return None
    jobs = jobs or DR.JOBS
    pruned = DR.prune_red()
    tree0 = DR.repo_tree()
    print("  각 스위트를 **클린 상태에서 단독 실행**한다 — 연속 실행은 판정 규격이 아니다\n"
          + (f"  직렬 — 레포 mock 루트 하나에서 차례로(--serial)\n" if serial else
             f"  병렬 {jobs} — 스위트마다 제 임시 mock 루트(직렬은 --serial)\n"))
    rec = DR.load()
    picked = [x for x in SUITES if names is None or x[0] in names]
    total_ok, results = True, []
    clean_rc, residue, dup = 0, [], []
    idem = None
    for res in DR.run([x[0] for x in picked], serial, jobs, rec,
                      extra=(lambda: _idempotent(serial)) if names is None else None):
        if isinstance(res, tuple):
            idem = res[1]
            continue
        x = next(y for y in picked if y[0] == res["name"])
        name, what, was = x[0], x[1], (x[2] if len(x) > 2 else ())
        clean_rc = clean_rc or res["clean_rc"]
        residue = residue or res["residue"]              # 한 번이라도 남았으면 그것이 신호다
        exp = DR.expected(name, was, rec)
        ok, note = DR.verdict(res["p"], res["f"], res["r"].returncode, exp, why.get(name))
        total_ok &= ok
        results.append((name, res["p"], res["f"], exp if exp is not None else res["p"], ok, res["secs"]))
        line(OK if ok else NG, f"{name:<17} {res['p']:>3} PASS / {res['f']} FAIL   ({res['secs']:.0f}s)  {what}", note)
        if not ok:
            _why(name, res["r"], res["p"], exp or 0)
        if res["dup"] != 0:                                 # **상시 어서션**(B74 ①) — 스위트가 무엇을 돌렸든 끝에 한 번
            dup.append(name)
            total_ok = False
            line(NG, f"{name:<17} 중복 canonical", res["dup_out"].splitlines()[0] if res["dup_out"] else "")
        red = DR.settle(res, ok and res["dup"] == 0 and not res["residue"])   # 붉으면 임시 자리 + 출력 전문을 남긴다 (B133 ②)
        if red:
            print(f"         붉은 기록 — {red}(임시 루트 · 출력.txt)")
    gone = DR.removed(SUITES, rec, why) if names is None else []
    for n, k, ok, note in gone:
        total_ok &= ok
        line(OK if ok else NG, f"{n:<17} 기록 {k} PASS — 스위트 목록에 없다", note)
    got = sum(r[1] for r in results)
    want = sum(r[3] for r in results)
    same, tnote = DR.tree_diff(tree0, DR.repo_tree())          # 레포는 시험이 읽기만 한다 — 남은 쓰기 (B133 ①)
    line(OK if same is not False else NG, "레포 작업 트리 — 회귀 앞뒤", tnote + (f" · 지난 붉은 기록 {pruned}개 정리" if pruned else ""))
    total_ok &= same is not False
    if idem is not None:
        line(OK if idem[0] else NG, "클린 2회 동일 그래프 (완료판정 4)", idem[1])
        total_ok &= idem[0]
    if result:
        Path(result).write_text(json.dumps({
            "suites": {r[0]: {"n": r[1], "fail": r[2], "ok": r[4], "secs": round(r[5])} for r in results},
            "removed": [g[0] for g in gone], "why": why, "serial": serial, "whole": names is None,
            "idempotent": idem[0] if idem is not None else None}, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    line(OK if not dup else NG,
         f"상시 어서션 — 중복 canonical 0 (회귀 {len(results)}종 전부)",
         "" if not dup else f"위반: {', '.join(dup)} (B74 ①)")
    line(OK if total_ok else NG, f"합계 {got}/{want} PASS" + (f" — {sel.HEAD_LINE}" if names is not None else ""),
         ("기대 수 기록과 맞는다(늘어난 수 · 사유 있는 감소 포함 — 기록은 마감 한 줄)" if names is None
          else "고른 스위트의 기대 수와 맞는다 — 마감은 전체 doctor")
         if total_ok else "기대 수 기록과 다르다 — 반입이 온전하지 않거나 환경이 다르다")
    if not total_ok:
        # **성공하면 화면을 늘리지 않는다** — 실패할 때만 원인 후보를 낸다.
        _env_diff(clean_rc, residue)
    _clean()
    return total_ok


# ================================================================ ③ 현재 상태
def show_state():
    head("③ 현재 상태 — 무엇이 들어 있나")
    sys.path.insert(0, str(ROOT))
    from core.state import registry, store                              # noqa: E402
    from core.state.bootstrap import bootstrap, open_graph              # noqa: E402
    from router import discover                                   # noqa: E402

    _clean()
    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)

    layers = discover()
    print(f"  층 {len(layers)}개 — {', '.join(layers)}")
    for lay in layers:
        g = open_graph(lay)
        seed = sum(1 for n in g.nodes.values() if n.get("status") == "seed")
        print(f"    · {lay:<10} 노드 {len(g.nodes):>3} (골격 seed {seed}) · 엣지 {len(g.edges)}")

    dts = registry.all_doc_types()
    builtin = [k for k, v in dts.items() if v["status"] == "builtin"]
    reg = [k for k, v in dts.items() if v["status"] == "registered"]
    print(f"\n  doc_type {len(dts)}종 — 내장 {len(builtin)} {builtin}")
    print(f"                    등록 {len(reg)} {reg or '(아직 없음 — n6로 등록한다)'}")

    q = store.read(store.QUEUE, [])
    from collections import Counter
    kinds = Counter(x["kind"] for x in q)
    print(f"\n  수정 큐 {len(q)}건 — {dict(kinds)}")
    print(f"  (mock 기준선 69. 사내 실데이터를 넣으면 당연히 달라진다)")

    docs = store.read(store.DOC_REGISTRY, {})
    print(f"\n  인입 문서 {len(docs)}건 — {list(docs)}")
    print("  ⚠ 전부 mock이다(mock/parsed·mock/raw). 사내 문서로 교체하는 것이 국면 2다")


# ================================================================ 진입점
def _picked(argv):
    """`--only` · `--changed` → `(스위트 이름 목록 또는 None(전체), 머리 줄 또는 None, 멈춤 rc 또는 None)`."""
    only, changed = sel.parse_args(argv)
    names = [x[0] for x in SUITES]
    if only is not None:
        got, unknown = sel.pick_only(names, only)
        if unknown or not got:
            print(f"[사용법] --only — 모르는 스위트 {unknown or only} · 스위트: {' · '.join(names)}")
            return None, None, 2
        return got, f"{sel.HEAD_LINE} — --only {' '.join(only)} → {len(got)}종", None
    if changed is not None:
        files, why = sel.changed_files(changed)
        if why:
            return None, f"--changed {changed} — 고를 수 없어 전체를 돈다: {why}", None
        got, lines = sel.pick_changed(names, files)
        detail = "\n".join(f"     {ln}" for ln in lines) or "     (바뀐 파일 없음)"
        if got is None:
            if "--list" in argv:
                print(f"--changed {changed} — 고를 수 없다 → 전체\n{detail}")
                return None, None, 0
            return None, f"--changed {changed} — 고를 수 없어 전체를 돈다\n{detail}", None
        return got, f"{sel.HEAD_LINE} — --changed {changed} · 바뀐 파일 {len(files)} → {len(got)}종\n{detail}", None
    return None, None, None


def _run_opts(argv):
    """`--serial` · `--jobs N` · `--why <스위트>=<사유>` · `--result <파일>`(B131 ①②)."""
    from cli import doctor_run as DR
    jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv and argv.index("--jobs") + 1 < len(argv) else None
    res = argv[argv.index("--result") + 1] if "--result" in argv and argv.index("--result") + 1 < len(argv) else None
    return {"serial": "--serial" in argv, "jobs": jobs, "why": DR.parse_why(argv), "result": res}


#: 회귀 명령(B133 ③ — 기본 doctor는 점검만) · 회귀 쪽 선택지(이것이 있으면 회귀를 돈다)
REGRESS_CMD = "python doctor.py --regress"
REGRESS_OPTS = ("--regress", "--serial", "--why", "--jobs", "--result")


def main(argv):
    names, sel_head, stop = _picked(argv)
    if stop is not None:
        return stop
    if names is not None:
        print("=" * 66)
        print(f"  온톨로지 시스템 — {sel_head}")
        print("=" * 66)
        if "--list" in argv:        # 고르기만 본다(돌리지 않는다)
            print("  고른 스위트 — " + (" · ".join(names) or "없음"))
            return 0
        if not names:
            print("  고른 스위트 0종 — 바뀐 파일을 읽는 스위트가 없다")
            return 0
        ok = run_suites(names=names, **_run_opts(argv))
        print(f"\n{'=' * 66}\n결과: {sel.HEAD_LINE} — 고른 {len(names)}종 {'통과' if ok else '실패'} · 마감은 전체 doctor\n{'=' * 66}")
        return 0 if ok else 1
    only_env = "--env" in argv
    regress = any(a in argv for a in REGRESS_OPTS) and not only_env
    quick = not regress                     # 기본 doctor는 점검만 — 회귀는 `--regress`(B133 ③ · 옛 `--quick`은 기본과 같다)

    print("=" * 66)
    print("  온톨로지 시스템 — 사내 이식 점검  (국면 1 완료본)" + ("  · 회귀 포함" if regress else ""))
    print("=" * 66)
    if "--quick" in argv:
        print(f"  --quick은 기본 doctor와 같다(기본이 점검만 — 회귀 0) · 회귀는 {REGRESS_CMD}")
    if sel_head:                # 고르려 했으나 고를 수 없었다 — 전체를 돈다(그 사실을 머리에)
        print(f"  {sel_head}")
    # 상태 줄 · 층 이름(B99 ①) · 정합(B99 ⑩) — 운영 루트를 읽기만 (B111 ①)
    operating("head")

    env_ok = check_env(probe=only_env)
    if only_env:
        print(f"\n{'=' * 66}")
        print("환경 점검만 수행했다. 전체는 `python doctor.py`")
        return 0 if env_ok else 1

    suites_ok = run_suites(quick, **_run_opts(argv))
    show_state()
    operating("transition")    # 사내 전환 판정 — 운영 루트를 읽기만 (B111 ①)

    print(f"\n{'=' * 66}")
    if V.fails():
        print(f"결과: **{V.fails()}건이 조치 필요**다 — 위 [{NG.strip()}] 항목을 먼저 해결한다")
    else:
        verdict = "온전하다" if suites_ok else (f"점검 통과(회귀는 {REGRESS_CMD} — 반입 직후 한 번)" if quick else "회귀 실패")
        print(f"결과: 반입물은 {verdict}. 다음은 ④의 권장 순서다")
    print("=" * 66)
    return 1 if V.fails() else 0


if __name__ == "__main__":
    # **하위 실행의 환경은 한 자리가 정한다**(B111 ①) — 셸 환경은 운영 화면(`cli/doctor_view`)에만 넘기고, 이 프로세스와
    # 그 아래는 격리
    _SHELL_ENV = dict(os.environ)
    from core.llm import gateway
    gateway.isolate()
    # **공통 진입 함수 하나**(B99 ③) — 로그 설정 · 화면 전체를 명령 로그로 · 실행 머리/끝 줄
    from cli import _entry
    sys.exit(_entry.run("doctor", main))
