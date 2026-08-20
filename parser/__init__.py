# -*- coding: utf-8 -*-
"""파서 공용 코어 (n7) — **별도 패키지**다 (D-9).

에이전트 코어의 "외부 패키지 0" 원칙은 여기 적용되지 않는다: 파서는 사내 실행
별도 프로그램이고 결합은 JSON 계약뿐이다(P1). openpyxl·python-pptx를 쓴다.

    reader     원본 → 원시 추출        (포맷별 — xlsx/pptx. 08-01 참조 구현 채택 확정)
    preflight  실행 전 정합 검사        (문서 지문 ↔ ADAPTER.expects 결정적 대조)
    struct_map 구조 지도 패스           (구조 가변 prose 한정 — 지도는 데이터, 분할은 코드)
    adapter    원시 → 정규 조각         (doc_type별 — LLM 생성 또는 코어 기본 어댑터)
    normalizer 자기완결 보정            (상동·병합 전개·복수값·nested)
    tagger     정규 → 계약 JSON         (좌표 태깅·봉투·이미지 요약)
    validator  계약 self-check          (3층 구조·좌표 존재·자기완결·payload_kind)

**포맷 의존은 reader에만, doc_type 의존은 adapter에만.** 나머지는 전부 공용이고
사람이 1회 작성·유지한다 — LLM이 생성하는 것은 adapter뿐이다(§3 규약 1).
"""
