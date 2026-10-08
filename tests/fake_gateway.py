# -*- coding: utf-8 -*-
"""시험용 **가짜 게이트웨이** — 질의의 실호출 갈래를 네트워크 없이 돈다 (B104).

대역은 전송(`_post` — 임베딩)과 채팅(`chat`)과 설정(`require`·`config`)뿐이다 — 지시문 · 요청 조립 · 스키마 ·
벡터 캐시 · 후보 밖 id 거르기는 실물이다.
  · 임베딩: 동의어 표(`SYN` — 창작)를 아는 결정적 64차 벡터 — 같은 개념은 강하게 · 글자 2-gram은 약하게
  · 선별(지점 link): 후보 중 이름에 `pick`이 든 첫 노드(`pick=None`이면 첫 후보) + 후보 밖 id 하나(버려져야 한다)
  · 답변(지점 answer): 세 줄 · 사실 0과 청크 0을 썼다고 돌려준다
창작 표본이다 — 점수는 메커니즘 확인이지 근거가 아니다([정정] 50).

    with Live():            # 안에서는 gateway.use_mock() == False
        ...
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from core.llm import gateway

#: 동의어 표(창작) — 임베딩 대역이 「같은 개념」으로 보는 말들
SYN = {"틈새": "클리어런스", "간극": "클리어런스", "클리어런스": "클리어런스", "펀칭": "타발", "타발": "타발"}
CFG = {"url": "http://fake.gw/v1", "key": "", "model": "fake-chat", "embed_model": "fake-embed",
       "embed_backend": "gateway", "embed_url": "http://fake.gw/v1", "timeout": 5}
#: 채팅 호출 기록 — `[(지점, 받은 user 본문)]`
CALLS = []


def vec(text):
    """개념(동의어 표)은 강하게 · 글자 2-gram은 약하게 — 결정적 64차 정규화 벡터."""
    v = [0.0] * 64
    for k, c in SYN.items():
        if k in text:
            v[int(hashlib.sha256(c.encode()).hexdigest(), 16) % 64] += 5.0
    t = re.sub(r"\s+", "", text)
    for i in range(len(t) - 1):
        v[int(hashlib.sha256(t[i:i + 2].encode()).hexdigest(), 16) % 64] += 0.2
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _post(url, payload, key, timeout):
    assert str(url).endswith("/embeddings"), url
    return {"data": [{"embedding": vec(payload["input"])}]}


class Live:
    """`with Live(pick=…):` 안에서는 실호출 갈래가 가짜 게이트웨이로 돈다(나오면 원래대로)."""

    def __init__(self, pick="클리어런스"):
        self.pick = pick

    def chat(self, messages, json_schema=None, point=None, **kw):
        body = json.loads(messages[1]["content"])
        CALLS.append((point, body))
        if point == "link":
            cands = [c for c in body["candidates"] if self.pick is None or self.pick in c["canonical"]]
            picks = [{"id": c["id"], "why": f"질문의 표현이 이 노드({c['canonical']})와 같은 뜻"} for c in cands[:1]]
            return {"picks": picks + [{"id": "NOPE-밖", "why": "지어낸 id"}]}
        if point == "answer":
            return {"answer": "가짜 답 첫 줄 [사실 0]\n둘째 줄 [청크 0]\n셋째 줄",
                    "used_facts": [0] if body.get("그래프_사실") else [], "used_chunks": [0]}
        return {}

    def __enter__(self):
        self.keep = (gateway.use_mock, gateway.require, gateway.config, gateway._post, gateway.chat)
        gateway.use_mock = lambda: False
        gateway.require = lambda *a, **k: dict(CFG)
        gateway.config = lambda: dict(CFG)
        gateway._post = _post
        gateway.chat = self.chat
        del CALLS[:]
        return self

    def __exit__(self, *a):
        (gateway.use_mock, gateway.require, gateway.config, gateway._post, gateway.chat) = self.keep
