# -*- coding: utf-8 -*-
"""칸 0.3 — 사내 이식 점검기 — **가져온 것이 온전한가 · 다음에 무엇을 해야 하는가** (국면 2 진입 도구).

    python doctor.py            전체 (환경 → 자체 검증 → 상태 → 사내 전환 판정)
    python doctor.py --quick    회귀 생략 (느린 기계용 — 전체도 보통 20초 안이다)
    python doctor.py --env      환경만 (반입 직후 첫 실행 — 30초)
    python doctor.py --only <스위트…>          고른 스위트만 (개발 중 · **판정 아님** — B117 ①)
    python doctor.py --changed [<기준 커밋>]   바뀐 파일을 읽는 스위트만 (개발 중 · **판정 아님** · 고를 수 없으면 전체)
    … --list                                   고르기만 보고 돌리지 않는다

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
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 회귀 10종 — **각각을 클린 상태에서 단독 실행**한다(증분0 §8 실행 규약).
# 연속 실행은 판정 규격이 아니다: 스위트가 `data/`를 공유해 순서 의존이 관측됐다.
SUITES = [
    ("test_g1_g2", 86, "저장 계층 · 근거 축 id · 부트스트랩 · 런타임 경계 · core 경계 3종 · GraphStore 전용 · 저장 레코드 스키마 · 진입점 계약"),
    # **자리는 따로 돈다**(B79 — `test_g1_g2` 834행 분할): 저장·주소 규격과 자리
    # 배치는 바뀌는 이유가 다르다.
    ("test_places", 32, "자리 소유자·자리가 가른다·모듈 머리말·코드 지도 재생성 · B79 층 자산 상태 루트·미정의 이름 0·루트 출처·레포 정본 자산 해시 · B80 ⓪원본 `raw/`"),
    ("test_g3", 82, "인입 계약 v2 · 추출 분리 · 커밋 게이트 · 하강 부착"),
    ("test_g4", 97, "질의 4단 · 품질층 등록 · 재인입 회귀 · query --json · viewer 서버(B82 ①) · 골든셋 채점 · BM-25"),
    ("test_g5", 64, "I축 4연산 + 이관 · 운영 도구 · B73 ops confirm(큐 종결) · B74 ops alias"),
    ("test_g6_platform", 20, "플랫폼 창구 · 2층+cross 표시 · 큐 열람 · 계기판 8종"),
    ("test_g6_scan", 16, "지문 스캔(S11) · mock 격리"),
    ("test_g6_batch", 27, "일괄 투입 조건 셋 · 상태 거부 문면의 계약 · B79 원본 자리(⓪)·기록 표기 · B80 `raw/` 개명·옛 이름 거부"),
    ("test_g6_registry", 10, "내장은 mock일 때만 · 등록부 결손은 상태 거부"),
    ("test_g6_ingest", 38, "인입 화면 — 예고·큐 집계·다음 줄·--step · B81 값 줄(대장의 투영)·로그는 파일·색은 특이점·보폭 손잡이"),
    ("test_g6_sheets", 27, "시트 역할 관문(B83) — 기록·파서 인자 · 표와 규칙 제안 · 관문/거부/플래그 · 참조 청크의 처지"),
    ("test_g6_coord_layer", 14, "좌표 층의 이름 해방(B85) — 카테고리로 찾는다 · 골격 파일 부재 거부 · 이름 박은 자리 0 · 이름 바꾼 루트에서 전 구간 등가"),
    # **사내 모양을 상시로 돈다**(B86) — 상태가 코드 밖 · 좌표 층 이름이 다르다.
    ("test_g6_shanae_parts", 16, "사내 모양 잔여(B86) — 화면 경로 한 자리 · 파서 자리 주입 · 대장 자리 · 선택 의존 거부·버린 그림 한 줄 · 등록 표본 시트 관문"),
    ("test_g6_shanae_root", 13, "사내 모양 루트(B86 ⑥) — 레포 밖 상태 루트에서 등록부터 뷰어·doctor --quick까지 · 기본 루트와 canonical·엣지·큐·질의 등가"),
    ("test_g6_catalog", 21, "층 공통 config(B90) — 카탈로그 거부 다섯·초안 흐름 · 전역 해소(table·prose 한 길) · 주·겸·자기 좌표 · 걸침 엣지 문장화 · 등록 스키마 재대조 · registry 원자 쓰기"),
    ("test_g6_catalog_sync", 21, "공통 config 맞추기(B92~B95) — 골격 카테고리의 어긋난 집 노드 0이면 자동 교정·이름 규칙 줄 · used_by 결과 기록·새 카테고리 경고·골격 카테고리 개체 조회 전용 · 골격 카테고리 집 = 골격 층 자동·골격 모순 거부·겸 상태 표시 · 한 층 선언은 자동 추가 · 겹침은 빈칸+멈춤 · 선언·노드 없으면 제거 · 노드 남으면 멈춤 · 사람 값 불변 · 집 변경 막기 · --dry-run 쓰기 0 · 운영 처음 바로 생성"),
    ("test_g6_dryrun_fold", 7, "B96 — dry-run은 실제와 같은 검사(ⓓ·골격 문법) · show tree 흐름 순서 · 사용량 줄(관문·뷰 확인) · 라틴 대소문자 2차 대조(하나일 때만) · norm 불변"),
    ("test_g6_extract_view", 6, "B97 — 산문 추출을 보이게: 추출 예고 · 청크별 메타 줄 · 시간 기준 누적 줄 · 청크 단위 이어 쓰기(중단·조건 불일치) · --step 산문 두 관문"),
    ("test_g6_preflight_view", 9, "B98 — 비용 전 사전 점검(임베딩·그림·공통 config · 실행당 1회) · 설정 파일 읽음/무시됨 · 토큰 입력/출력 한 함수 · 구축 실패 줄 · 이어지는 표(80칸·줄바꿈·박자 행) · 색 세 층(ESC 0)"),
    ("test_g6_safe_log", 8, "B99 ①~⑥ — 층 이름 = 폴더 이름(소실 0 · 거부 셋) · 같은 층 둘째 열기 결함 · 어떤 예외든 되돌림(유령 큐 0) · 화면 전체를 명령 로그로(진입점 15) · 사용량 줄의 문서 · 단계 머리·끝 줄 · 결과표(층별 합·이번/이전 큐) · 재시도 줄 — 표·산문 × 층 둘"),
    ("test_g6_diag", 4, "B99 ⑦~⑩ — 산문 판정 총수 = 개체 수 · 값 표 위치 · 좌표 진단 표 · 후보 임베딩 메모리 1회 · 판정 근거(가드·LLM 가장 가까운 후보) · 정합 점검·정리(계획/--apply) · 스키마 재대조 — 표·산문 × 층 둘"),
    ("test_g6_struct", 8, "B100 ①~⑥ — 재시도 되살아남 0(남음 = 대상 − 연결) · 등록 골격 목록 = 좌표 층 몫 + 자기 골격(생성·검수 뷰·하네스) · 관문 G4H(골격 값 열 entity → FAIL · 문턱 손잡이) · 지시문 1.4·1.3 · 집 이동 동치(ops 9·질의 확장·show·내보내기) · 미러 규칙 ≠ 집 경고 · 골격 밖 반복 판정 기억 · 골격·사전 판 재시도 — 표·산문 × 층 둘"),
    ("test_g6_synonym", 6, "B101 — 같은 문서 auto 매칭(가드 예외) · 좌표 학습 보존(바로 사용 · 거부 · 승격) · 새 공정 후보 · 별칭 출처 · 불확실 일괄 검토 · 극성 values 경고 — 표·산문 × 층 둘"),
    ("test_g6_belongs", 17, "B102 — 맥락 줄(한 함수) · 문서 좌표(서브트리 · 공유 별칭 · 파일명 · 기록) · 소속(belongs_to · 옛 attach) · 이름에 소속 · 좌표 없는 스코프 개체 0 · 재사용 조건 · 붙은 곳 화면 · 보존물·동명 — 엑셀·Word·표 × 층 둘"),
    ("test_g6_coord_pairs", 9, "B105 — 상위를 범위로 하위 해소(보류·어긋남은 그대로) · 등록 관문 G4I(맞바꿈 FAIL · 일부 경고 · 골격 밖 · 문턱 손잡이 · 검수 같은 표) · 판정 전 쌍 표 = 구축 큐 · --step 좌표 관문 쓰기 0 · 쌍 묶음·확인함·재인입·다른 문서·fresh·취소 · 질의 ⓖ 원 레코드·상한 — 표·산문 × 층 둘"),
    ("test_g6_rebuild", 18, "B106 — fresh 보존 넷(추출·지도·판정 대장·좌표 학습) · --all 클린 · 재구축 한 명령(동치 · LLM 0 · 기록 불변 · 처음 인입 순서) · 판정 재생(표·산문·소속 대상) · 대상 없음(골격 이름 변경 · 되돌리면 재생) · --no-replay · ops replay 멱등 · 문서 단위 확인 · 문서 좌표 상위 — 표·산문 × 층 둘"),
    ("test_g6_alias_book", 13, "B108 — 별칭 대장(쓰는 손 하나 · 이름으로 · 같은 별칭 한 항목 · LLM 매칭 · 사람 · 개명 · 병합) · 재구축 동치(스냅샷 = seed + 대장 · 판 같음 · 태깅 0 · bootstrap 앞뒤 같음) · 처음 채움(공통 진입 · 재구축 계획) · 거두기(alias-reject · 비대화형 계획만 · 다시 싣지 않는다) · show aliases · 재구축 끝 줄 · 골격 개명 대상 없음 — 표·산문 × 층 둘"),
    ("test_g6_log_pipe", 8, "B109 — 명령 로그 보존(재구축 · 기본 fresh가 남기고 클린만 지운다) · 화면이 닫혀도 트레이스백 0(읽기 — run.py · python -m cli.* · doctor.py · 화면 스레드 · 쓰기 — 141 · 멈춤 줄 · ③은 시작 전 · 문서 끝 · 마무리까지 중 하나 · 줄 위치 표본 · 재인입은 회수 그래프까지 되돌림) — 표·산문 × 층 둘"),
    ("test_g6_stop_chunks", 5, "B110 — 시험·doctor의 하위 프로세스는 표준입력을 물려받지 않는다(소스 대조 0) · 닫힌 화면의 flush·close는 조용히 · 사람이 멈춘 문서(--step q · --step-every q)는 청크·그래프·사전·큐가 시작 전 · 문서 대장·체크포인트는 남고 다시 치면 추출 재사용으로 같은 결과 — 표·산문 × 층 둘"),
    ("test_g6_ops_root", 16, "B111 — 운영 상태 폴더는 점검이 읽기만 한다(doctor --quick 두 갈래 · 설정 파일/환경변수 · 폴더 지문 전후 같다 · 격리는 한 함수) · 운영 루트의 클린은 묻는다(비대화형 거부 · 터미널 n · --yes · mock 루트와 기본 fresh는 그대로 · 코드 거부) · 재구축은 지우기 전에 사전 점검(실호출 설정 없음 · 지문 불변) · 끝나지 않은 재구축은 계획 파일에서 이어 간다(kill -9 · 중단 · 문서 실패 · 사전 점검 실패 → 같은 그래프 · 끝) — 표·산문 × 층 둘"),
    ("test_g6_reconcile", 17, "B112 — 맞춤표(식마다 칸 합 = 전체 · 값 = 대장 개체 행 · 보류 = 결과 묶음 · 인입 · show report · 재구축 재생 · 명령 로그 · 깨뜨린 묶음 [결함]) · 시트 숨김(표 · 기본 skip · LLM 0 · --sheets로 살림 · 기록이 있어도 표) · 청크 목차(행 = 청크 · 상태 합 · 라벨 엑셀·PPT · 개체 0 목록) · 소속 대상 합 · 엣지 없는 노드 = 그래프 · 대장 dir = 엣지 방향 · 문서 좌표 경고·후보 · 체크포인트 자리·없으면 [결함] — 표·산문 × 층 둘"),
    ("test_g6_relink", 11, "B113 — 다른 공정 골격 이름은 노드 0 · 관련 링크(about) · 대장 mention · 맞춤 칸(산문 × 층 둘 · 표) · 빈칸 표시(개체 칸 개체 0 · 좌표 칸은 문서 좌표 · 값 칸은 그대로 + 표지 · 목록은 공통 config) · 재연결(좌표 미해소 보류 행이 ops relink로 선다 · 추출 LLM 0 · 되살린 노드는 사전에 남는다 · 뒤 청크 유닛에 앞 개체가 다음 바퀴에 · 붙음 0에서 멈춤 · 클린 2회 같다)"),
    ("test_g6_outline", 5, "B115 — 문서 개요(대상 제목만 노드 · 주제 0 · 제목에 없는 이름 · 목록 밖 카테고리 버림 · 같은 제목이면 재사용 LLM 0 · 추출 입력에 조상 제목 개체) · 상위로 올라가는 폴백 사슬(NG unit → 추출부 → 공정 · 대장 폴백(제목 n단) · 맞춤 제목 폴백 · 소속 대상 제목 개체) · 연결 보강(엣지 없는 · 공정에만 붙은 개체 · 후보 안 · 근거 문장 · 버림 · 재구축 재생 LLM 0 · 상한 손잡이 · mock 판정 없음) · 엑셀 · Word · PPT 같은 함수 · 표는 개요 0 — 표·산문 × 층 둘"),
    ("test_g6_rehearsal", 22, "B116 — 추출 리허설은 임시 상태 루트(하위 실행 · 운영은 읽기만): 이미 인입된 문서(렌즈판이 있는 루트)를 표본으로 등록 세 단계 전후 운영 지문 같음(층 둘) · ②구획 채워짐 · 리허설 산출 자리(추출 · 개요) · 안내 줄 · 같은 조건(실호출 · 상태 루트 llm.json · 손잡이) · 새 종류 인입 추출 · 개요 LLM 0 · 원래 종류는 지금 규칙 · 부분 · 실패 · 중단(Ctrl-C) 흔적 0"),
    ("test_g6_numbers", 18, "B118 — 숫자와 기준이 보이게: 문서 한 줄 요약 = 맞춤표 · show summary = 그래프 · 대장 · --diff 바뀐 줄만 · 점수표(--template 행 = 개체 행 · 맞음/틀림/빈칸 · 재구축 뒤 같은 수) · 위치 두 칸 · 묻는 자리(c·ㅊ만 계속 · ㅂ·Ctrl-C·q 멈춤 = 시작 전 · 다시 묻기 · 저장 뒤 관문 · y/N) · 보강 버림 재생(제안 · 패턴 더하면 LLM 0으로 붙음) · 거부 묶음 · 영향 범위 — 표·산문 × 층 둘"),
    ("test_g6_structure", 14, "B119 — 문서 구조(시트마다 LLM · 번호 없는 유닛 줄이 트리 · 경로에 · 한 유닛 아래 청크 둘이 한 노드 · 번호 표본은 고정 규칙과 같은 트리 · 같은 파일 LLM 0 · 검사 · 실패 초안) · 소속(주인 있는 개체는 유닛에 · 주인 없는 것만 공정 · 지어낸 이름 버림 · 추출 입력에 사슬 · 가드 부딪힘 셈) · 구조 관문(고침 기록 · 다시 파싱 · 재구축 재생 · 약한 구조 신호) · 이름(공정::유닛::사양 · 표 불변) · 값 표 칸 — 표본 셋 × 층 둘"),
    ("test_g6_values", 4, "B120 — 산문의 값(유닛마다 같은 이름 사양이 각자 원문 값 · 출처 청크 · 날짜 · 쪽수는 값이 아니다) · 버림(원문 밖 · 결함 로그 · 맞춤표 수) · 충돌(spec_conflict · 덮어쓰기 0) · 추출 판 = config 추출 칸 해시(relation_patterns · config_version만 → 재사용 · 정의문 → 다시) · 선언 없음 → 값 0 · 재구축 재생 LLM 0"),
    ("test_g6_judge2", 4, "B123 — 2단 판정(1차 불확실 → 청크 문장으로 2차 매칭 · 2차도 불확실이면 신규 + uncertain_match · 2차는 불확실에만 · 재구축 재생 LLM 0) · md 보고서(값 표 행 = 대장 개체 행 · 잘림 0 · 카테고리 쌍 합 = 문서 몫 엣지) · 붙은 자리 칸에 관계(연결 하나면 └ 줄 0)"),
    ("test_g6_structure2", 5, "B124 — 구조 v2: 같은 번호 꼴 형제 · 부모(가) 나)는 10)의 자식 · 한 구간 · 넘으면 형제 줄에서만 나뉜다 · 글 그대로) · 이름 줄(가. · 요약 줄은 본문 · 빈 줄 표시) · 시트 = 대상 · 층 중립(힌트 없으면 지시문에 층 어휘 0 · quality 층 · 형제 신호) · 폴백 · 재생(구간 검사 어긋난 시트만 지금 방식 · 같은 파일 LLM 0)"),
    ("test_g6_deck", 6, "B125 — PPT: 슬라이드 = 추출 1회(상자 분할 0) · 같은 슬라이드(본문 · 표 · 노트 한 입력 · 그림 요약 값 버림) · 캡처(그림 무관 · 렌더 없으면 none + 수) · 덱 구조(글 상자 제목 · (계속) · 덱 개요 · 골격 밖 공정 버림) · 다공정(제 공정 아래 · 언급은 관련 링크 · --coord 없이 ingest-dir) · 고침 · 재생(LLM 0)"),
    ("test_g6_split", 8, "B126 · B127 — 구조 edit: 바닥(rules = B118 청크 · 고침 없는 edit = rules) · 고침(제목 더함 · 부모 바꿈 · 대상 → 사슬 · 이유 md · 어긋난 고침만 버림) · 시트마다 확인(힌트 → 앞 출력 + 힌트로 다시 · c 확정 → 재생 LLM 0) · 형태 단서(다시 시작 · 이어짐) · 빈 규칙 나무만 llm · --split-only(추출 0 · 쓰기 0 · md) · 확정한 시트도 힌트로 다시(기록된 힌트 + 새 힌트 · c 덮음 · q 그대로)"),
    ("test_g6_replay2", 3, "B127 — 재생의 불확실은 2차를 한 번(2차 기록 없는 불확실만 · 매칭이면 그 노드 · 큐 0 · 기록이 남는다) · 2차 기록이 있으면 재생 LLM 0 · 한 번 더 재구축 판정 LLM 0"),
    ("test_g6_capture", 9, "B128 · B129 — PPT 캡처 실경로(렌더 · 판정 함수 대역 없음): 옆 PDF · PDF 문서(soffice 없는 PATH에서 호출마다 캡처 1장) · 캡처 길이 없으면 사전 점검에서 멈춤(파싱 0 · --no-capture면 진행 + 기록) · 그림 입력 거부면 그림 없는 PPT도 멈춤 · soffice면 PPTX만으로(숨김 슬라이드 쪽 맞음) · doctor --env 줄 · import pymupdf · soffice 찾기 한 함수(PATH 밖 표준 자리 · SOFFICE_PATH 지정 · 없으면 찾아본 자리 · 그림 형식 변환 · doctor 같은 답)"),
    ("test_g6_close", 19, "B117 — 마감 도구는 판정을 느슨하게 하지 않는다: 네 벌 C 같은 커밋 같다 · 폴백 사슬 끈 사본 C만 다르다 · doctor --only 하나만 · 머리 · 합계 · 로그에 「고른 실행 — 판정 아님」 · 모르는 이름 rc 2 · --changed ⊇ 실행 기록 표본(레포 사본 core 하나 · 자산 폴더 → 전체) · 마감 한 줄 일곱 단계 끝까지 · FAIL rc 1 · 명세 패치 --check 항목 이름 · --apply 어긋나면 쓰기 0 · 명세 모양 늘면 위반 · 줄면 내림"),
    ("test_g6_rebuild_memory", 11, "B107 — 옛 사람 판단 기록에 이름 채우기(옮길 때 · ops replay 계획 · 재구축 계획 · 그때의 이름 · 그래프에 없는 id는 목록) · 좌표 태깅 null 답 기억(닫힌 목록 내용 해시 · 지우는 손잡이 · 별칭이 판을 바꾼다 · 실호출 모양 재구축 태깅 0) · 재시도가 판정 대장을 갱신(같은 키 · by retry · 인입과 같은 하강 · 재구축 재생) — 표·산문 × 층 둘"),
    ("test_g6_hybrid", 15, "B104 — 공유 별칭의 범위 안 해소(보류 문면 표기 모호) · 링킹 임베딩 후보 + LLM 선별(후보 밖 0 · 보충/폴백 · 미스율 사전 단) · 문서 검색 채널(근거 없음은 둘 다 빌 때 · 벡터 캐시 재사용·몫만·판) · 짧은 답·쓴 근거·CLI ⓐ~ⓕ = --json · 채점 두 축 · 쓰기 0 — 표·산문 × 층 둘"),
    ("test_g6_lens", 18, "추출 입구(B91) — 사내 손잡이(값·출처·거부·분포) · 렌즈(층 목록·거름·예고·상한) · 시트 두 모드(로직·LLM·자동·승격 후보) · 개체별 부모·관련 링크·근거 순위 · ref 근처 [관련 원문] · 겸 집 경고"),
    ("test_g6_narrow", 54, "후보 상한·조건부 retry·auto · 사전 키=조회 키·판정 대장·뷰어 · 임베딩 선택·스코프 필터·실패 비용"),
    ("test_g65_contract", 28, "재인입·인입 검증 계약 · 닫힌 계약 배선 · 병합 무손실"),
    ("test_g65_cross", 10, "걸침층 배선 · mock 비계 최소 · 인입 순서 무관 결정성"),
    ("test_g65_prov", 18, "provenance {doc_id}#{locator} · 좌표 부재의 처분 사다리"),
    ("test_g65_rules", 20, "반대 방향 연속 적용 금지 · 빌드 소요 계측 · 재등록 승인 누적"),
    # **P1도 칸별이다**(B78 2c) — 합은 그대로다.
    ("test_p1_core6", 42, "골격 스냅샷 · 코어 6종 계약 · preflight/계약 위반 · 기본 어댑터 · 역산 정합 · 지도 경로"),
    ("test_p1_wiring", 21, "파서 무판독 · ⑦ 예산 초과 폴백 · 생성 하네스 3단 · 조각 공통 층"),
    ("test_p1_csv", 54, "CSV reader 구조 등가 · 인코딩·구분자 판정 · PPT/PDF 임계 경로"),
    ("test_p1_form", 35, "스프레드시트 산문 레벨 규칙 · 형태 판정(시트 역할 — 입구는 시트마다 · 역할 뒤 prose 시트) · 관문 ③④의 시트 역할 · 큐 case 두 값"),
    ("test_p1_coord", 26, "시스템이 아는 값은 LLM이 쓰지 않는다 · 분할 기준 · 좌표 태깅 상한"),
    ("test_p1_hier", 24, "산문 엑셀 계층(B87) — 번호 군·첫 등장 레벨 · 글자 상한(행 경계·무손실) · 규칙 선언(안 선 시트만·기록·재사용·ref/mock/리허설 호출 0) · 셀 안 줄바꿈의 locator(B89 — 행이 단위)"),
    ("test_p1_media", 19, "리더의 폭(B88) — 엑셀 그림 → ④(ref·skip 0 · 변환·건너뜀 사유 · --no-images 기록 · 재사용) · docx(개요 수준·번호·표·그림·삭제 0·.doc 거부) · 등록 doc_type status(운영 어댑터)"),
    ("test_p2", 68, "어댑터 생성 킷 6종 · 검수 뷰 렌더러 · 지도 필드 셋 · B76 스켈레톤 최소 어댑터·형 검사 G4F · B77 전시물 실행 관문"),
    # **P3는 파일 여덟이다**(B78 2b) — 등록 파이프라인의 칸별로 갈랐고 합은 그대로다.
    ("test_p3_register", 73, "등록부 조회 · 구축 모드 전 과정(S1) · 1부 경고 · 정형 등록(S15)"),
    ("test_p3_prompt", 60, "골격 확정 · 전송 프롬프트 · 문답 어휘 주입 · 열 프로파일 · 예산"),
    ("test_p3_gate", 77, "스키마 strict · 오류 본문 · 분할 레벨 · mock 관문 · --resume"),
    ("test_p3_view", 34, "모든 열은 판정을 갖는다 · 하네스 자동 갈래 · 추출 리허설"),
    ("test_p3_recover", 38, "재생성 지시 · 문답 누적 · 청크 단위 실패 · 지도 무효화 · llm-check"),
    ("test_p3_screen", 52, "관문 전 구간 · 막는 이유와 다음 줄 · status·confirm 재실행 · 확정 요약"),
    ("test_p3_ledger", 46, "관문이 채우고 찍는다 · columns 값 셋 · 어휘 정적 대조 · 형태 판정 문의"),
    ("test_p3_flow", 65, "지문·미선택 갈래 · CSV 등가 · 열 판정 대장 · 분할 줄 · 좌표 예고 · G39·G4G"),
    ("test_2a_gateway", 76, "게이트웨이 골조 — 12지점 도달 가능성 · **12지점 본문 스모크**(B79 ③ⓒ · ⑩시트 역할 B91 · ⑪문서 개요 · ⑫연결 보강 B115) · ⑦ 배선 · 변이 시험 · B63 대장 잠금 · **B80 요청 조립(CHAT_TEMPERATURE)·임베딩 백엔드 gateway|local**"),
    # **뷰어는 세미 플랫폼이다**(B82) — headless로 잰다(브라우저 의존 0).
    ("test_viewer", 60, "뷰어 서버(쓰기 0 · 자리 탈출 거부) · 벤더링 렌더러 · 질의 trace 계측 · 연결 현황 · B84 테마 대비·다시 칠하기·상호작용·오류 문면 · B103 배치 셋·닻·연결 없는 노드·이웃·노드 상세의 근거 · B114 힘 배치 워커(시간 끊기 0 · 난수 0) · 크기 계단 · 힘 손잡이 · 벡터 이어 만들기 · 진행 줄 · 질의 단계 · 상태 라우트 GET만"),
    ("verify_roundtrip", 50, "raw 실물 ↔ 계약 JSON 역산 정합"),
    # **사내 조건을 상시로 돈다**(B71 ②) — 나머지 전부가 `USE_MOCK=1`이라,
    # 사내에서 처음 밟는 자리를 사용자가 찾아 왔다(B70 · 실측 열째).
    ("test_onsite", 27, "사내 조건 — USE_MOCK=0 · 픽스처 없음 · 등록 산출만 (내장 섞임 0 · 결손 거부 · 추출 힌트 가드 · B78 1b 이관 등가·이관 전 거부 · B79 층 자산 관문·migrate --assets·원본 포맷 가름)"),
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

    반환은 `(returncode, 잔재 경로 목록)`이다.

    여기서 rmtree를 제 손으로 하면 "클린"의 정의가 doctor와 테스트와 완료판정에서
    각자 달라진다. subprocess로 부르는 이유는 doctor가 core를 import하기 전에도
    돌아야 하기 때문이다 — 반입 직후 첫 확인이 이 파일의 일이다.
    """
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "init", "--fresh", "--all"],
                       capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)
    # **지운 결과를 실제로 확인한다.** `core/init.fresh()`는 `ignore_errors=True`로
    # 지우므로 권한 문제로 실패해도 조용하다 — 그러면 체크포인트가 살아남아
    # 「클린 단독 실행」이라는 판정의 바닥이 무너진다(회귀 규약 §7.5-7).
    # **자리는 `core/paths.py`가 안다**(B78) — 옛 배치의 `parsed/`·`extract/`를 보면
    # 이관 전 클론에 남은 폴더를 「클린 실패」로 읽는다(실측).
    sys.path.insert(0, str(ROOT))
    from core import paths                                          # noqa: E402
    residue = [d.name for d in (paths.parsed(), paths.extract())
               if d.exists() and any(d.iterdir())]
    return r.returncode, residue


def _capture_lines():
    """**PPT · PDF 캡처**(B128 ③) — soffice(Impress · 실제 변환)와 판정 한 자리(`parser.render.capture_path`)의 답 한 줄.
    실호출 PPT · PDF 인입은 사전 점검이 같은 함수로 멈추므로 여기 답이 곧 그 답이다(문서마다 옆 PDF는 따로 잰다)."""
    from core import paths                                  # noqa: F401 — 파서 주입(soffice 지정 자리 — B129 ①)
    from parser import render
    exe, where, tried = render.find_soffice()               # 찾기 한 함수 (B129 ①)
    ok, route, miss = render.capture_path(probe=True)
    line(OK if exe else WARN, f"soffice {'있음 — ' + exe + '(' + where + ')' if exe else '없음'}",
         "LibreOffice — PPTX → PDF 변환(캡처 길 하나 · Impress 포함 · 실제 변환으로 쟀다)" if exe
         else f"찾아본 자리: {tried} — LibreOffice(Impress 포함)를 표준 자리에 깔거나 다른 자리면 셸 설정 파일에 "
              f"{render.SOFFICE_ENV}=<soffice 경로> · 또는 PowerPoint에서 PDF로 저장해 같은 폴더 · 같은 이름으로")
    line(OK if ok else WARN, f"PPT 캡처 — {'가능(' + route + ')' if ok else '불가'}",
         "PPT · PDF 실호출 인입은 사전 점검에서 이 길과 그림 입력(llm-check ⑦)을 잰다" if ok
         else f"빠진 것: {miss} — 실호출 PPT 인입은 사전 점검에서 멈춘다(캡처 없이는 --no-capture)")


# ================================================================ ① 환경
def check_env():
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
    _capture_lines()
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
    guard = ROOT / "doctor_noformat"
    guard.mkdir(exist_ok=True)
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
        probe = ROOT / ".doctor_write_probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        line(OK, "레포 쓰기 권한", "상태 폴더(등록·진실·작업)를 만들 수 있다")
    except OSError as e:
        line(NG, "레포 쓰기 권한 없음", f"{e} — 실행 산출물을 만들 수 없다")

    return V.fails() == 0


def _idempotent():
    """**클린 2회 동일 그래프** — 구현 국면 완료판정 4번 (문서 7 §7.6-4).

    이 판정을 세는 것이 여태 없었다. 시나리오 통과만 세면 멱등성이 조용히 깨진
    상태로도 판정이 통과한다.

    대조 단위를 셋으로 나눈다:

    - **그래프**: 바이트 동일이어야 한다. 다르면 노드가 증식했거나 id가 재발급됐다.
    - **큐**: `(kind, doc_id, payload)` **집합**으로 본다. 순서까지 같기를 요구하지
      않는 것은 재인입이 그 문서의 비상시(non-STANDING) 큐를 회수한 뒤 다시 싣기
      때문이다 — 살아남은 상시 항목은 제자리에 있고 회수분은 뒤에 붙어 순서가
      바뀐다. 증식·유실이 없다는 것이 멱등성이고, 파일 안 배열 순서는 아니다.
    - **거부 로그**: 큐가 아니라 관측 신호다(§7.8) — 계수만 본다.
    """
    def snap():
        # **여기서만 `graph.json`을 바이트로 연다** — B6(GraphStore 경유)의 예외이고
        # 그 근거를 남긴다: 재는 것이 **파일 바이트의 동일성**이기 때문이다.
        # GraphStore로 읽으면 그 계층이 정규화·정렬해 돌려주므로, 지금 잡으려는
        # 차이(노드 증식·id 재발급으로 생긴 바이트 차)가 바로 그 정규화에 지워진다.
        # 이것은 그래프를 **쓰거나 해석하는** 경로가 아니라 진단의 측정이다 —
        # 파생물에서 그래프를 고치는 경로는 여전히 없다(P5).
        from core import paths as _paths      # 상태 자리는 한 모듈이 안다 (B78 1a)
        graphs, queue, rejects = {}, set(), 0
        for f in sorted(_paths.data().rglob("*.json")):
            rel = str(f.relative_to(_paths.data()))
            if rel.endswith("graph" + ".json"):
                graphs[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        for x in json.loads(_paths.data("review_queue.json").read_text(encoding="utf-8")):
            queue.add((x["kind"], x["doc_id"],
                       json.dumps(x["payload"], sort_keys=True, ensure_ascii=False)))
        rj = _paths.data("gate_rejects.json")
        if rj.exists():
            rejects = len(json.loads(rj.read_text(encoding="utf-8")))
        return graphs, queue, rejects

    # **클린은 `_clean()`이 정의한다** — 여기 있던 것은 그 함수 본문의 **복사본**이고,
    # 그 복사본의 `return`이 아래 계측 전부를 도달 불가로 만들고 있었다(B55 ⑨).
    # 구현 국면 완료판정 4가 **한 번도 계측된 적이 없다** — 두 번 돌려 비교하는
    # 코드가 통째로 죽어 있었고, 화면에 그 줄이 뜨지 않는다는 사실로만 드러났다.
    rc, residue = _clean()
    if rc or residue:
        line(NG, "클린 2회 동일 그래프 (완료판정 4)",
             f"클린을 못 만들어 재지 않았다 — init --fresh --all rc={rc} · 잔재 {residue}")
        return

    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)
    g1, q1, r1 = snap()
    subprocess.run([sys.executable, str(ROOT / "run.py"), "all"],
                   capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)
    g2, q2, r2 = snap()

    same_g, same_q = g1 == g2, q1 == q2
    detail = (f"그래프 {len(g1)}층 바이트 동일 · 큐 {len(q1)}항목 집합 동일 · "
              f"거부 로그 {r1}→{r2}") if same_g and same_q else (
              f"그래프 {'동일' if same_g else '다름'} · "
              f"큐 1회만 {len(q1 - q2)}건 / 2회만 {len(q2 - q1)}건")
    line(OK if same_g and same_q else NG,
         "클린 2회 동일 그래프 (완료판정 4)", detail)


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


def run_suites(quick=False, names=None):
    """회귀 — `names`를 주면 그 스위트만(고른 실행 — 판정 아님 · 완료판정 4 「클린 2회」는 재지 않는다)."""
    head("② 자체 검증 — 가져온 것이 온전한가 (회귀 10종)" if names is None
         else f"② 고른 스위트 {len(names)}종 — {sel.HEAD_LINE}")
    if quick:
        print("  (--quick: 건너뛴다. 반입 직후에는 반드시 한 번 돌려라)")
        return None

    print("  각 스위트를 **클린 상태에서 단독 실행**한다 — 연속 실행은 판정 규격이 아니다\n"
          "  (증분0 §8 실행 규약: 스위트가 data/를 공유해 순서 의존이 관측됐다)\n")
    total_ok, results = True, []
    clean_rc, residue, dup = 0, [], []
    for name, expect, what in SUITES:
        if names is not None and name not in names:
            continue
        rc, res = _clean()
        clean_rc = clean_rc or rc
        residue = residue or res              # 한 번이라도 남았으면 그것이 신호다
        t0 = time.time()
        r = subprocess.run([sys.executable, str(ROOT / "tests" / f"{name}.py")],
                           capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)
        dt = time.time() - t0
        # **판정 줄만 센다** — 어서션의 **세부 문면**에 `[FAIL]`이 들어갈 수 있다
        # (하네스 실패 문면을 그대로 싣는 자리가 그렇다 — B50). 부분 문자열을 세면
        # 통과한 검사가 실패로 세어진다(실측: test_p3의 지시 이력 어서션).
        _lines = [ln.strip() for ln in r.stdout.splitlines()]
        p = sum(1 for ln in _lines if ln.startswith("[PASS]"))
        f = sum(1 for ln in _lines if ln.startswith("[FAIL]"))
        ok = (f == 0 and p == expect)
        total_ok &= ok
        results.append((name, p, f, expect, ok))
        mark = OK if ok else NG
        note = "" if ok else f"기대 {expect} PASS · FAIL 0"
        line(mark, f"{name:<17} {p:>3} PASS / {f} FAIL   ({dt:.0f}s)  {what}", note)
        if not ok:
            _why(name, r, p, expect)
        # **상시 어서션**(B74 ①) — 스위트가 무엇을 돌렸든 끝에 한 번 본다.
        d = subprocess.run([sys.executable, str(ROOT / "tests" / "dup_scan.py")],
                           capture_output=True, text=True, cwd=str(ROOT), stdin=subprocess.DEVNULL)
        if d.returncode != 0:
            dup.append(name)
            total_ok = False
            line(NG, f"{name:<17} 중복 canonical",
                 (d.stdout or "").strip().splitlines()[0] if d.stdout else "")

    got = sum(p for _n, p, _f, _e, _o in results)
    want = sum(e for _n, _p, _f, e, _o in results)
    if names is None:
        _idempotent()

    print()
    line(OK if not dup else NG,
         f"상시 어서션 — 중복 canonical 0 (회귀 {len(results)}종 전부)",
         "" if not dup else f"위반: {', '.join(dup)} (B74 ①)")
    line(OK if total_ok else NG, f"합계 {got}/{want} PASS" + (f" — {sel.HEAD_LINE}" if names is not None else ""),
         ("국면 1 완료판정의 회귀 기준선과 일치한다" if names is None else "고른 스위트의 기대 수와 같다 — 마감은 전체 doctor")
         if total_ok else "기준선과 다르다 — 반입이 온전하지 않거나 환경이 다르다")
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
    names = [n for n, _e, _w in SUITES]
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
        ok = run_suites(names=names)
        print(f"\n{'=' * 66}\n결과: {sel.HEAD_LINE} — 고른 {len(names)}종 {'통과' if ok else '실패'} · 마감은 전체 doctor\n{'=' * 66}")
        return 0 if ok else 1
    only_env = "--env" in argv
    quick = "--quick" in argv or only_env

    print("=" * 66)
    print("  온톨로지 시스템 — 사내 이식 점검  (국면 1 완료본)")
    print("=" * 66)
    if sel_head:                # 고르려 했으나 고를 수 없었다 — 전체를 돈다(그 사실을 머리에)
        print(f"  {sel_head}")
    # 상태 줄 · 층 이름(B99 ①) · 정합(B99 ⑩) — 운영 루트를 읽기만 (B111 ①)
    operating("head")

    env_ok = check_env()
    if only_env:
        print(f"\n{'=' * 66}")
        print("환경 점검만 수행했다. 전체는 `python doctor.py`")
        return 0 if env_ok else 1

    suites_ok = run_suites(quick)
    show_state()
    operating("transition")    # 사내 전환 판정 — 운영 루트를 읽기만 (B111 ①)

    print(f"\n{'=' * 66}")
    if V.fails():
        print(f"결과: **{V.fails()}건이 조치 필요**다 — 위 [{NG.strip()}] 항목을 먼저 해결한다")
    else:
        verdict = "온전하다" if suites_ok else ("회귀 미수행" if quick else "회귀 실패")
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
