# -*- coding: utf-8 -*-
"""동의어 사전 — **접근의 단일 관문** (문서 7 §7.1 core 접근 경계 3종).

    from core.dictionary import Dictionary
    d = Dictionary.open()
    d.register("노칭정밀도", nid, provenance="CP01-C1")
    d.lookup("노칭 정밀도")      # → [node_id, …]
    d.save()

**왜 관문이 필요한가.** 층 그래프 저장에는 접근 경계가 있는데(문서 1 B6) 영속
지식(P4)인 사전에는 없었다 — 접근이 관문 없이 5곳(bootstrap·build·ops×3·query)으로
흩어져 있었고, **등재 시 provenance 필수는 그중 한 곳만 지켰다**(build). 관문이 없으면
아래 셋을 강제할 자리가 없어 노드 증식 결함의 재발 경로가 코드 배치 수준에서 열린다:

1. **등재 시 provenance 필수** — 자동 생성물에 provenance 예외를 두지 않는다(문서 1 G2).
2. **키는 `norm()`된 표면형** — 등재부와 조회부가 같은 규칙을 써야 한다. 규칙이 갈리면
   등재된 표기가 조회에서 미스가 되고, 미스는 신규 노드 생성으로 이어진다.
3. **alias는 정확 일치만** 매칭한다 — 문자열 포함 규칙은 canonical에만 적용한다.

**전 층 단일 자원이다**(§7.1) — 층 간 표면형 충돌은 사전이 허용하고 호출자가
카테고리·층으로 선별한다. 그래서 `lookup`은 **후보 목록**을 돌려주고 하나를 고르지
않는다: 관문이 조용히 첫 히트를 고르면 그것이 판정을 대신하게 된다.

**이 모듈은 노드를 만지지 않는다.** alias 항목(`{surface, provenance}`)은 노드 레코드에
살고 그 소유는 GraphStore다 — 사전은 `표면형 → [node_id]` 색인만 갖는다. 둘을 한
모듈에 합치면 사전이 그래프를 쓰게 되어 저장 계층 경계가 무너진다.
"""
from __future__ import annotations

from . import log, store
from .ids import norm

_LOG = log.get(__name__)


class Dictionary:
    """`표면형(norm) → [node_id, …]`. 형태는 문서 7 §7.2의 `dictionary.json={}`이다."""

    def __init__(self, entries=None):
        self._d = entries if entries is not None else {}

    # ------------------------------------------------------------ 열기·저장
    @classmethod
    def open(cls):
        """사전을 여는 **유일한 입구**."""
        return cls(store.read(store.DICTIONARY, {}))

    def save(self):
        store.write(store.DICTIONARY, self._d)
        return self._d

    def entries(self):
        """읽기 전용 열람용 — 순회가 필요한 창구(플랫폼·열람 명령)를 위해 낸다.

        **쓰기용으로 쓰지 않는다.** 돌려주는 것은 내부 dict 자신이라 고치면 관문을
        우회한 등재가 된다 — 그래서 쓰기는 `register`·`redirect`·`drop`뿐이다.
        """
        return self._d

    # ------------------------------------------------------------ 등재
    def register(self, surface, node_id, *, provenance):
        """표면형을 등재한다. **provenance 없이는 등재하지 않는다.**

        여기가 그 강제의 단일 지점이다 — 5곳으로 흩어져 있던 동안 이 조건을 지킨
        곳은 한 곳뿐이었다. 근거 없는 등재를 허용하면 재인입 회수(문서 4)가 무엇을
        걷어야 하는지 판정할 수 없다.
        """
        if not provenance:
            log.explicit_fail(_LOG, "core.dictionary.register",
                              f"provenance 없는 등재 시도 — '{surface}' → {node_id}")
            raise ValueError(
                f"사전 등재에는 provenance가 필수다 (문서 1 G2) — '{surface}'")
        key = norm(surface)
        ids = self._d.setdefault(key, [])
        if node_id not in ids:
            ids.append(node_id)
        return key

    # ------------------------------------------------------------ 조회
    def lookup(self, surface):
        """**후보 목록**을 돌려준다 — 하나를 고르지 않는다.

        고르는 것은 판정의 몫이고 그 자리는 `core/matcher.py`다. 관문이 첫 히트를
        조용히 고르면 카테고리 불일치 안전망·극성 후보 제외·생존 판정이 판정 전
        필터가 아니라 사후 필터로 밀려난다.
        """
        return list(self._d.get(norm(surface), []))

    def surfaces(self):
        """등재된 표면형 전부 — **사전 스캔**(질의 링킹 1단)의 정식 입구다.

        링킹은 "질문 안에 등재된 표기가 있나"를 긴 표기 우선으로 훑는다(문서 5) —
        관문을 우회해 dict를 직접 순회하면 그 스캔이 사전 형태에 결합된다.
        """
        return list(self._d.keys())

    def surfaces_of(self, node_id):
        """이 노드를 가리키는 표면형 전부 — 회수·리다이렉트가 대상을 찾을 때."""
        return [k for k, v in self._d.items() if node_id in v]

    # ------------------------------------------------------------ I축 연산
    def redirect(self, old_id, new_id):
        """옛 id를 가리키던 표기를 새 id로 옮긴다 (I2 병합).

        `new_id`가 None이면 **걷어만 낸다**(I3 분리) — 배분표가 각 표기를 자기
        타깃에 이미 등재했으므로 병합용 리다이렉트를 그대로 쓰면 다른 타깃에
        배분된 표기까지 첫 산출물을 가리켜 한 표기가 두 노드를 동시에 가리킨다.
        """
        moved = 0
        for key, ids in list(self._d.items()):
            if old_id not in ids:
                continue
            ids.remove(old_id)
            if new_id is not None and new_id not in ids:
                ids.append(new_id)
            if not ids:
                del self._d[key]
            moved += 1
        return moved

    def drop(self, node_id):
        """이 노드를 가리키는 표기를 전부 걷는다."""
        return self.redirect(node_id, None)


# ---------------------------------------------------------------- 편의
def lookup(surface):
    """한 번 조회하고 끝나는 읽기 전용 호출부용(질의 등)."""
    return Dictionary.open().lookup(surface)
