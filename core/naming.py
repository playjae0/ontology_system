# -*- coding: utf-8 -*-
"""이름 규칙 — 극성 결합과 canonical 스코프 (CH3B 3.5).

"같은 것은 한 노드로, 다른 것은 섞이지 않게"(P4·A5)를 이름으로 지키는 장치다.
노드의 대표 이름은 표면형 그대로가 아니라 **규칙으로 조립**된다.

**코드에 층 어휘 0**(B1) — 어떤 카테고리가 극성 결합 대상인지, 구분자가 무엇인지는
전부 층 config가 값으로 준다. 여기는 조립 절차만 갖는다.
"""
from __future__ import annotations


def bind_polarity(surface, category, electrode_type, cfg):
    """극성 결합 — 조건 **3개를 전부** 만족할 때만 한다 (CH3B 3.5 규약 1).

    ①카테고리가 config의 bind_categories에 있고
    ②그 행의 극성이 확정값(cathode/anode)이고
    ③층 config가 polarity를 선언했을 때.

    하나라도 어긋나면 결합하지 않는다 — 표기 편의가 아니라 **노드 정체성 규칙**이라
    함부로 붙이면 다른 실물이 한 노드로 합쳐진다.
    """
    pol = cfg.get("polarity")
    if not pol:                                          # ③ 층이 선언하지 않음
        return surface
    if category not in pol.get("bind_categories", []):   # ①
        return surface
    if electrode_type not in pol.get("values", []):      # ② both·무표기는 결합 안 함
        return surface
    for v in pol["values"]:                              # 이중 접두 방어 (규약 6)
        if surface.startswith(v + " "):
            return surface
    return f"{electrode_type} {surface}"


def strip_polarity(canonical, cfg):
    """극성 제거 표면형 — mirrors 짝 찾기와 극성 모호 판정에 쓴다."""
    pol = cfg.get("polarity") or {}
    for v in pol.get("values", []):
        if canonical.startswith(v + " "):
            return canonical[len(v) + 1:]
    return canonical


def scope_canonical(surface, category, parent_canonical, cfg):
    """canonical 스코프 — `{부모}::{표면형}` (CH3B 3.5 규약 4).

    **부모는 세부공정이지 설비가 아니다.** 관리항목은 세부공정 단위로 관리되고
    CP와 PFMEA가 같은 키로 만나야 하기 때문이다 — 스코프 기준을 설비로 바꾸면
    걸침 문서의 병합 키가 갈라진다(그 변경은 스키마 한 줄이지만 지뢰다).

    부모가 미해소면 스코프를 붙이지 않는다. 좌표를 모른 채 만든 노드를
    스코프 붙은 노드와 합치면 오병합이므로, 후보에서도 제외된다(규약 5).
    """
    sc = cfg.get("canonical_scope")
    if not sc or category not in sc.get("bind_categories", []):
        return surface, True
    if not parent_canonical:
        return surface, False                            # 미해소 — 병합 금지 표시
    sep = sc.get("sep", "::")
    if sep in surface:                                   # 이미 스코프가 붙어 있음
        return surface, True
    return f"{parent_canonical}{sep}{surface}", True
