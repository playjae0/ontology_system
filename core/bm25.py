# -*- coding: utf-8 -*-
"""BM-25 상시 대조군 (문서 5 §5.5-3).

**대조군이지 기능이 아니다.** 재는 것은 「이 시스템이 키워드 검색보다 나은가」이고,
그 답이 데이터로 남아야 «도입 판정»이 인상이 아니라 측정이 된다. 그래서 규율이 하나다:

    **그래프·사전·골격·임베딩·LLM을 읽지 않는다.**

읽는 것은 `data/chunks.json`의 청크 텍스트뿐이고, core 모듈 중 import하는 것은
`store` 하나다(회귀가 검사한다). 하나라도 더 읽으면 그 순간 대조군이 아니라
**이 시스템의 일부**가 되어 비교의 뜻이 사라진다.

**BM-25 대조군 ≠ 하이브리드 서치**(§5.5 경계) — 대조군은 시스템 밖의 비교 기준이고,
하이브리드는 시스템 안의 확장 기능이다. 여기 코드가 질의 경로에 불려 들어가면
그 경계가 무너진다.

**인덱스는 저장하지 않는다**(파생물 — 문서 1 P5). 호출 때 메모리에 만든다: 청크
수천 건이면 밀리초이고, 저장하면 청크와 인덱스가 어긋나는 날이 온다.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from core import store

# BM-25 상수 — **한 곳에만 있다.** 흩어지면 조정이 코드 수색이 된다.
K1 = 1.5
B = 0.75

_WORD = re.compile(r"[0-9a-z]+")
# CJK(한중일) 음절 — 형태소 분석기 없이 한국어를 다루는 최소 장치의 재료다.
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def tokens(text):
    """소문자화 → 영숫자 연속은 단어, **CJK는 문자 2-gram**.

    형태소 분석기를 쓰지 않는 이유는 의존을 늘리지 않기 위해서만이 아니다 —
    대조군은 **누구나 30줄로 다시 만들 수 있어야** 비교 기준의 자격이 있다.

    2-gram인 근거: 「노칭프레스」와 「노칭 프레스」가 같은 2-gram 집합
    (`노칭`·`칭프`·`프레`·`레스`)을 대부분 공유한다. 1-gram은 변별력이 없고
    (「공정」의 `공`이 「공구」에도 있다), 3-gram은 짧은 명사를 통째로 놓친다.
    """
    t = (text or "").lower()
    out = _WORD.findall(t)
    cjk = _CJK.findall(t)
    # 연속한 CJK 음절만 이어 붙인다 — 사이에 공백·기호가 끼면 다른 낱말이다.
    run = []
    for ch in t:
        if _CJK.match(ch):
            run.append(ch)
            continue
        out += _bigrams(run)
        run = []
    out += _bigrams(run)
    return out


def _bigrams(run):
    if len(run) == 1:
        return run[:]                      # 한 글자 낱말은 그 자체가 토큰이다
    return ["".join(run[i:i + 2]) for i in range(len(run) - 1)]


class Index:
    """전 청크 텍스트의 BM-25 인덱스. **호출 때 만들고 버린다.**"""

    def __init__(self, docs):
        # docs: {chunk_id: text}
        self.ids = list(docs)
        self.tf = {}
        self.len = {}
        df = Counter()
        for cid in self.ids:
            tk = tokens(docs[cid])
            c = Counter(tk)
            self.tf[cid] = c
            self.len[cid] = len(tk)
            df.update(c.keys())
        n = len(self.ids) or 1
        self.avg = (sum(self.len.values()) / n) if self.ids else 0.0
        # **표준 BM-25 idf**(+0.5 평활). 전 문서에 있는 토큰은 0에 가까워진다.
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def score(self, query):
        q = [t for t in tokens(query) if t in self.idf]
        out = {}
        for cid in self.ids:
            tf, dl = self.tf[cid], self.len[cid]
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if not f:
                    continue
                denom = f + K1 * (1 - B + B * (dl / self.avg if self.avg else 1))
                s += self.idf[t] * f * (K1 + 1) / denom
            if s:
                out[cid] = s
        return out


def _corpus():
    """**청크 텍스트만** 읽는다 — store 경유. 그래프는 열지 않는다."""
    ch = store.read(store.CHUNKS, {"chunks": {}})
    return {cid: (c.get("text") or "") for cid, c in (ch.get("chunks") or {}).items()}


def build():
    return Index(_corpus())


def search(query, k=8, index=None):
    """`[(chunk_id, score)]` 상위 k. 동점은 chunk_id로 갈라 **결정적**이다."""
    idx = index if index is not None else build()
    sc = idx.score(query)
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


def docs_of(hits):
    """청크 id → doc_id. `{doc_id}:{…}` 꼴이 계약이다(문서 7 §7.2)."""
    return [cid.split(":", 1)[0] for cid, _ in hits]
