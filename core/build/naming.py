# -*- coding: utf-8 -*-
"""칸 3.4 — 이름 규칙 — canonical 스코프 (CH3B 3.5, 틀 §4B-A11-8).

"같은 것은 한 노드로, 다른 것은 섞이지 않게"(P4·A5)를 이름으로 지키는 장치다.
노드의 대표 이름은 표면형 그대로가 아니라 **규칙으로 조립**된다 — 부모 경로 접두(스코프).

**원칙: 코드는 canonical 문자열을 파싱해서 판정하지 않는다**(A11-8) — 부모 경로 · 맨 이름은 조립 시점에 칸으로 적는다
(`scope` · `base_name`). **극성은 이름에 들어가지 않는다**(B198 — 값 · 엣지 · 노드의 한정어 `core/build/polarity`).

**코드에 층 어휘 0**(B1) — 어떤 카테고리에 스코프가 붙는지, 구분자가 무엇인지는 전부 config가 값으로 준다.
여기는 조립 절차만 갖는다.
"""
from __future__ import annotations


def scope_categories(cfg=None):
    """**이름에 부모가 붙는 카테고리** — 공통 config의 경로 「씀」 ∪ `parent_pairs`의 nest(B174 ① · `catalog.naming_rule` — 데이터 ·
    코드가 카테고리 이름을 모른다). 한 자리에서 읽는다(판정 · 막이 · 연쇄) · `cfg`는 부르는 모양을 지키는 자리(읽지 않는다)."""
    from core.state import catalog
    rule = catalog.naming_rule()
    return list(dict.fromkeys(rule["path"] + rule["nest"]))


def nest_categories(cfg=None):
    """소속이 골격 밖 노드로 해소되면 **그 노드의 canonical을 이름 부모로** 쓰는 카테고리 — `parent_pairs`에서 위가 일반 노드인 아래
    카테고리(B102 ⑤ · B174 ① — 목록 없이 쌍에서)."""
    from core.state import catalog
    return list(catalog.naming_rule()["nest"])


#: 부모 경로 · 맨 이름 칸 — 새 칸 앞, 옛 칸 뒤(B142 ⑤ — 재구축 전 그래프는 옛 칸만 있다 · 옛 `parent`는 시험 노드의 칸)
SCOPE_FIELDS = ("scope", "mirror_scope", "parent")
BASE_FIELDS = ("base_name", "mirror_name")


def scope_of(node):
    """노드의 **부모 경로** — 이름 부모 canonical 글자(`노칭::실린더`) · 없으면 None. 읽는 자리는 이 함수 하나(B142 ⑤)."""
    return next((node.get(k) for k in SCOPE_FIELDS if (node or {}).get(k)), None) if node else None


def base_name_of(node):
    """노드의 **맨 이름** — 주소 접두를 뺀 자기 이름부(정규화 표기) · 없으면 None(골격 · 옛 노드는 canonical로 본다)."""
    return next((node.get(k) for k in BASE_FIELDS if (node or {}).get(k)), None) if node else None


def set_scope(node, scope):
    """부모 경로를 새 칸에 쓰고 옛 칸을 걷는다(개명 연쇄 — 한 노드의 부모 경로 칸은 하나)."""
    for k in SCOPE_FIELDS[1:]:
        node.pop(k, None)
    node["scope"] = scope


def name_parent(category, owner_canonical, coord_parent, cfg):
    """**이름 부모 한 함수**(B119 ④ · B144 ②) — 소유자가 **골격 밖 노드**(유닛 · 제목 개체)로 해소된 개체의 이름 부모.

    `nest_categories`에 든 카테고리(사양 · 값)면 그 노드의 canonical(`노칭::언와인더 unit::속도`) · 아니면 좌표의 부모 그대로
    (`노칭::속도`). 소유자는 문서 형태와 무관하다 —
    산문은 소속 대상 · 표는 같은 행의 소유 엣지 개체(`scope_path.owner_parent` — CP의 설비 → 관리항목 · PFMEA처럼 소유 엣지가 없는
    표는 공정 아래) · 제목은 위 제목 개체. 소유자가 골격(공정)이면 이 함수를 부르지 않고 좌표가 부모다 · 부모 노드가 없으면 좌표 그대로."""
    if owner_canonical and category in nest_categories(cfg):
        return owner_canonical
    return coord_parent


def scope_canonical(surface, category, parent_canonical, cfg):
    """canonical 스코프 — `{부모}::{표면형}` (CH3B 3.5 규약 4).

    **부모는 이름 부모 한 함수(`name_parent`)가 정한다**(B144 ②) — 세부공정이거나, 소유자를 아는 값(`nest_categories`)이면
    그 소유자(`노칭::설비::관리항목`). 표 · 산문이 같은 규칙이라 같은 것은 같은 이름(사전 키)으로 만나고, 소유자를 모르는 값은
    세부공정 바로 아래에 선다 — 이름이 갈리는 남은 경우는 관문(공정 줄기)과 경로 호환이 잇는다(`scope_path`).

    부모가 미해소면 스코프를 붙이지 않는다. 좌표를 모른 채 만든 노드를
    스코프 붙은 노드와 합치면 오병합이므로, 후보에서도 제외된다(규약 5).
    """
    if category not in scope_categories(cfg):
        return surface, True
    if not parent_canonical:
        return surface, False                            # 미해소 — 병합 금지 표시
    from core.state import catalog
    sep = catalog.sep()
    if sep in surface:                                   # 이미 스코프가 붙어 있음
        return surface, True
    return f"{parent_canonical}{sep}{surface}", True
