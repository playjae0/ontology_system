# -*- coding: utf-8 -*-
"""칸 0.4 — **요청 조립과 임베딩 백엔드 탐침** (B80 ①③).

무엇을 재나: ①게이트웨이로 **실제로 나가는 payload**(`temperature`를 싣는가)
②임베딩이 **어느 갈래로** 도는가(게이트웨이 API · 로컬 모델 폴더)와 그때의 주소.

**서브프로세스로 돈다.** 모드와 설정은 진입 시점에 정해지고(`use_mock()`·`paths.home()`),
설정 키를 프로세스 안에서 갈아 끼우면 뒤따르는 판정이 앞의 환경에 딸린다 —
`points_probe`·`points_smoke`와 같은 규율이다.

**실제 패키지 없이 로컬 갈래를 잰다**: `sentence_transformers` 스텁 모듈을
`sys.modules`에 심는다(요청문 ③ 완료판정). 그래서 이 탐침은 무거운 의존을
설치하지 않은 환경에서도 로컬 갈래의 본문을 실행한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 스텁 설정 — 전송이 스텁이라 값은 가짜여도 된다.
BASE_ENV = {"USE_MOCK": "0", "LLM_GATEWAY_URL": "http://chat.stub/v1",
            "CHAT_MODEL": "m1", "ONTO_CONFIG": str(ROOT / "tests" / "fixtures"
                                                   / "_no_such_llm_config.json")}
#: 지울 키 — 남으면 탐침이 «설정된 상태»로 돈다.
CLEAR = ("CHAT_TEMPERATURE", "EMBED_BACKEND", "EMBED_GATEWAY_URL", "EMBED_MODEL",
         "LLM_API_KEY", "ONTO_HOME")

_RUNNER = r'''
import json, sys, types
sys.path.insert(0, %(root)r)
from core.llm import gateway

CAP = []
def _post(url, payload, key, timeout):
    CAP.append({"url": url, "payload": payload})
    if str(url).rstrip("/").endswith("/embeddings"):
        return {"data": [{"embedding": [0.5, 0.5]}]}
    return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
gateway._post = _post

STUB = {"init": 0, "encode": 0}
if %(stub_local)r:
    class _ST:
        device = "cpu"          # 실제 모델이 갖는 속성 — 화면 조각이 이것을 읽는다
        def __init__(self, path):
            STUB["init"] += 1
            self.path = path
        def encode(self, text, normalize_embeddings=False):
            STUB["encode"] += 1
            return [0.1, 0.2, 0.3]
    m = types.ModuleType("sentence_transformers")
    m.SentenceTransformer = _ST
    sys.modules["sentence_transformers"] = m

out = {"cap": CAP, "stub": STUB, "error": None, "value": None}
try:
    %(body)s
except BaseException as e:
    out["error"] = f"{type(e).__name__}: {e}"
out["st_imported"] = "sentence_transformers" in sys.modules
print("RESULT " + json.dumps(out, ensure_ascii=False, default=str))
'''

CHAT_BODY = 'out["value"] = gateway.chat([{"role": "user", "content": "ping"}]%(extra)s)'
CHECK_BODY = ('from core.llm import check\n'
              '    out["value"] = [s["id"] for s in check.probe()]')
EMBED_BODY = ('from core.llm import embeddings\n'
              '    out["value"] = embeddings.embed("가")\n'
              '    out["value2"] = embeddings.embed("나")')


def run(body, env_extra=None, *, stub_local=False):
    """탐침 1회 — `{cap, stub, error, value, st_imported}`."""
    env = {k: v for k, v in os.environ.items() if k not in CLEAR}
    env.update(BASE_ENV)
    env.update(env_extra or {})
    code = _RUNNER % {"root": str(ROOT), "body": body, "stub_local": stub_local}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(ROOT), env=env)
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT ")), None)
    if not line:
        return {"cap": [], "stub": {}, "error": f"(탐침 실패) {r.stderr[-300:]}",
                "value": None, "st_imported": False}, r
    return json.loads(line[len("RESULT "):]), r


def chat_payload(env_extra=None, *, extra=""):
    """`chat()` 한 번이 보낸 payload."""
    got, _r = run(CHAT_BODY % {"extra": extra}, env_extra)
    return (got["cap"][0]["payload"] if got["cap"] else {}), got


def check_payloads(env_extra=None):
    """`llm-check` 탐침 전부가 보낸 payload 목록 — **조립이 한 자리인가**를 잰다."""
    got, _r = run(CHECK_BODY, env_extra)
    return [c["payload"] for c in got["cap"]
            if str(c["url"]).endswith("/chat/completions")], got
