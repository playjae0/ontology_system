# -*- coding: utf-8 -*-
"""칸 3.4 곁 — **후보 좁히기 선택**(auto·embed·overlap) (B75 ① · 문서 4 §4.2).

임베딩은 선택이고 폴백이 정답인 유일한 지점이다 — 판정 LLM의 규율(§7.6-B-4)과
가르는 자리가 여기다. 인입 플래그(`--narrow`)가 설정을 이긴다.
"""
from __future__ import annotations

from core.llm import gateway


# **임베딩은 선택이다**(B75 ① · 사내 실측 열넷째). 후보를 상한 안으로 고르는 보조
# 수단이지 판정이 아니다 — 그것이 없다고 인입이 서면, 「모델 없이도 전 파이프라인이
# 돈다」가 거짓이 된다. §7.6-B-4의 「조용히 mock으로 떨어지지 않는다」는 **판정
# LLM**의 규율이고, 여기서는 폴백이 정답이다(임베딩 정확도 이득은 아직 측정이 없다 — P7).
NARROW_MODES = ("auto", "embed", "overlap")

# 인입 플래그가 꽂는 자리 — **플래그가 설정을 이긴다**(한 문서만 바꿔 비교한다).
_NARROW_OVERRIDE = None


def set_narrow(mode):
    """`--narrow embed|overlap` 이 꽂는다. `None`이면 설정으로 되돌린다."""
    global _NARROW_OVERRIDE
    if mode is not None and str(mode).lower() not in NARROW_MODES:
        raise ValueError(f"CANDIDATE_NARROW는 {NARROW_MODES} 중 하나다: {mode!r}")
    _NARROW_OVERRIDE = str(mode).lower() if mode is not None else None
    return _NARROW_OVERRIDE


def narrow_choice():
    """이 실행이 후보를 **무엇으로 좁히나** — `("embed"|"overlap", 사유)`.

    사유는 화면이 쓴다 — 「임베딩 미설정이라 겹침으로 돌았다」를 사람이 알아야
    같은 산출을 다른 설정의 산출과 견줄 수 있다(B75 ①의 비교가 그것이다).
    """
    want = (_NARROW_OVERRIDE or gateway.config().get("narrow") or "auto").lower()
    if want not in NARROW_MODES:
        want = "auto"
    if want != "auto":
        return want, ("플래그" if _NARROW_OVERRIDE else "설정")
    if gateway.use_mock():
        # mock `embed()`는 sha256이라 유사도가 가짜다(D-152 ②) — 회귀 세계의
        # 기본은 겹침이고, 그것이 `auto`의 답이다.
        return "overlap", "mock"
    return ("embed", "설정") if gateway.config().get("embed_model") else ("overlap", "미설정")
