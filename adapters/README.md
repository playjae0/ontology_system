# `adapters/` — 확정 어댑터의 **정본 자리**

문서 6 §6.4·§6.5. `run.py register confirm`이 검수 산출(`review/{doc_type}/`)에서
여기로 **옮긴다**. 매칭 스키마의 짝은 `schemas/{doc_type}.json`이고, 등록부
(`data/doc_types.json`) 등재가 그 **활성화**다.

**여기 있는 것은 추적한다.** `review/`는 실행 산출물이라 추적하지 않으므로, 확정본이
거기 남으면 재생성 시 함께 사라진다 — 그것이 이행이 필요한 이유다.

- 실물은 각자 파일로 살고, **목록·버전의 한눈 파악은 등록부**가 담당한다.
- 어댑터는 doc_type당 1모듈 — **선언 1개(`ADAPTER`) + 함수 1개(`extract`)**.
- `run.py register confirm`의 짝은 `core.registry.unregister`다 — 등재를 지우면
  여기 승격된 실물도 함께 걷는다(등재 없이 파일만 남으면 조회에는 잡히면서
  등록부에는 없는 반쪽 상태가 된다).
- 레포가 싣고 나온 mock 참조 어댑터는 `mock/adapters/`, 외부 LLM 실산출 스냅샷은
  `mock/fixtures/adapters/`다 — **디렉터리 경계가 지위 경계다**(문서 7 §7.5-4).
