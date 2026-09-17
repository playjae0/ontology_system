# -*- coding: utf-8 -*-
"""이름 규칙 — 극성 결합과 canonical 스코프 (CH3B 3.5, 틀 §4B-A11-8·9).

"같은 것은 한 노드로, 다른 것은 섞이지 않게"(P4·A5)를 이름으로 지키는 장치다.
노드의 대표 이름은 표면형 그대로가 아니라 **규칙으로 조립**된다.

**원칙: 코드는 canonical 문자열을 파싱해서 판정하지 않는다**(A11-8). canonical의
축값 접두·접미는 저장 정보가 아니라 층 내 유일한 이름을 만들기 위한 표기일 뿐이고,
판정 근거는 **`polarity` 필드**다. mirrors·순서 파생·극성 필터가 전부 그 필드 위에서
돈다. (구 `strip_polarity()`는 이 원칙에 따라 폐지됐다 — 그 함수는 **앞에 붙은**
접두만 떼어낼 수 있어서 스코프가 붙은 canonical(`노칭::anode 버 높이`)에서는
조용히 실패했다.)

**코드에 층 어휘 0**(B1) — 어떤 카테고리가 극성 결합 대상인지, 축값이 무엇인지,
구분자가 무엇인지는 전부 층 config가 값으로 준다. 여기는 조립 절차만 갖는다.
남는 것은 축의 **이름**(polarity)뿐이며 그것이 B1의 명시된 예외다.
"""
from __future__ import annotations

# polarity 파생 필드의 닫힌 4값 중 축과 무관한 2값 (A11-8).
# 나머지 2값(축값 자체)은 config가 값으로 준다 — 코드에 없다.
POLARITY_NONE = "none"          # both · 무표기 — 결합할 극성이 없다
POLARITY_UNBOUND = "unbound"    # 극성 표기는 있었으나 게이팅 ①②③ 미충족


def bind_polarity(surface, category, electrode_type, cfg):
    """극성 결합 — 조건 **3개를 전부** 만족할 때만 한다 (CH3B 3.5 규약 1).

    ①카테고리가 config의 bind_categories에 있고
    ②그 행의 극성이 확정값(축값 목록 안)이고
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


def derive_polarity(category, electrode_type, cfg, anchor_polarity=None):
    """노드에 기록할 `polarity` 파생 필드 — **닫힌 4값**(A11-8).

        축값(cathode·anode) / none(both·무표기) / unbound(표기는 있었으나 미결합)

    `anchor_polarity`는 부착 골격 노드의 polarity다. 그것이 확정이면 **상속한다**
    — 극성이 이미 주소(스코프 접두)에 있으므로 표면형에 다시 붙이지 않고(A11-9 ①)
    필드만 기록하는 것이 이 경로다.

    ※ config의 `polarity.values`(축의 값)와 이 반환값(닫힌 4값)은 다른 것이다.
      전자는 "축이 가질 수 있는 값", 후자는 "노드가 기록하는 파생 상태"다.
    """
    values = (cfg.get("polarity") or {}).get("values", [])
    if anchor_polarity in values:
        return anchor_polarity
    if electrode_type not in values:                     # both · 무표기
        return POLARITY_NONE
    if category not in (cfg.get("polarity") or {}).get("bind_categories", []):
        return POLARITY_UNBOUND                          # 표기는 있었으나 게이팅 미충족
    return electrode_type


def is_bound(polarity, cfg):
    """그 polarity가 **확정 축값**인가 — none·unbound와 가르는 단일 판정점."""
    return polarity in (cfg.get("polarity") or {}).get("values", [])


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
