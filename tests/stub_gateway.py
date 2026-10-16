# -*- coding: utf-8 -*-
"""시험용 **HTTP 가짜 게이트웨이** — 하위 프로세스까지 닿는 실호출 모양 (B116 ⓒ).

`tests/fake_gateway.Live`는 이 프로세스의 함수를 바꿔 끼운다 — 등록 검수의 추출 리허설은 **임시 상태 루트의 하위
프로세스**가 돌아(B116 ①) 그 바꿔 끼움이 닿지 않는다. 그래서 OpenAI 호환 주소 하나를 로컬에 띄우고, 상태 루트의
`llm.json`이 그 주소를 가리키게 한다(사내와 같은 길 — 설정 파일 · 전송 · 응답 파싱은 실물이다).

  · 지점은 **system 지시문의 내용**으로 안다(`prompts/<칸>_<이름>.md`의 전문과 같으면 그 이름 · 아니면 `chat`).
  · 응답은 `by[지점](user 본문 dict) -> dict` · 없으면 판정(`judge`)은 「새 것」 · 그 밖은 스키마의 최소 값.
  · `calls` — 지점별 호출 수(시험이 「추출 · 개요 LLM 0」을 잰다) · 임베딩은 `embed`.
창작 표본이다 — 수는 메커니즘 확인이지 근거가 아니다([정정] 50).

    with Stub(by={"extract": fn}) as gw:
        gw.config(home)          # home/llm.json — 실호출 · 이 주소
        ...
        gw.calls["extract"]
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _prompts():
    out = {}
    for p in (ROOT / "prompts").glob("*.md"):
        out[p.read_text(encoding="utf-8")] = p.stem.split("_", 1)[1]
    return out


def minimal(sch):
    """스키마의 최소 값 — null을 받으면 null · 객체는 필수 키만 · 배열은 빈 배열."""
    t = (sch or {}).get("type")
    if isinstance(t, list):
        if "null" in t:
            return None
        t = t[0]
    if t == "object":
        props = sch.get("properties") or {}
        return {k: minimal(props.get(k) or {}) for k in sch.get("required") or []}
    if t == "array":
        return []
    if t == "string":
        return (sch.get("enum") or [""])[0]
    if t in ("integer", "number"):
        return 0
    if t == "boolean":
        return False
    return None


def vec(text):
    v = [0.0] * 64
    for i in range(len(text) - 1):
        v[int(hashlib.sha256(text[i:i + 2].encode()).hexdigest(), 16) % 64] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Stub:
    def __init__(self, by=None):
        self.by, self.calls, self.prompts = dict(by or {}), {}, _prompts()
        self.server = self.thread = None
        #: 지점 → HTTP 상태(그 지점이 오면 오류로 답한다 — 실패 시험) · 지점 → 초(답하기 전에 기다린다 — 중단 시험)
        self.fail, self.delay = {}, {}
        self.seen = threading.Event()             # `delay` 지점이 처음 왔다
        self.stop = threading.Event()             # 끝 — 기다리던 답을 풀어 준다

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def config(self, home, **extra):
        """상태 루트에 `llm.json` — 실호출 · 이 주소(키 없음)."""
        cfg = {"USE_MOCK": "0", "LLM_GATEWAY_URL": self.url, "CHAT_MODEL": "stub-chat",
               "EMBED_MODEL": "stub-embed", "EMBED_BACKEND": "gateway", "EMBED_GATEWAY_URL": self.url,
               "LLM_TIMEOUT": "10", "LLM_RETRY": "0", **extra}
        Path(home).mkdir(parents=True, exist_ok=True)
        (Path(home) / "llm.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return Path(home) / "llm.json"

    def answer(self, payload):
        msgs = payload.get("messages") or []
        sysmsg = next((m["content"] for m in msgs if m.get("role") == "system"), None)
        point = self.prompts.get(sysmsg, "chat") if isinstance(sysmsg, str) else "chat"
        self.calls[point] = self.calls.get(point, 0) + 1
        if point in self.delay:
            self.seen.set()
            self.stop.wait(self.delay[point])
        if point in self.fail:
            return self.fail[point]
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        try:
            body = json.loads(user) if isinstance(user, str) else {}
        except ValueError:
            body = {"text": user}
        sch = ((payload.get("response_format") or {}).get("json_schema") or {}).get("schema")
        if point in self.by:
            out = self.by[point](body)
        elif point == "judge":
            out = {"type": "new", "matched_id": None, "confidence": 0.9}
        elif sch:
            out = minimal(sch)
        else:
            out = "pong"
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    def __enter__(self):
        stub = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                if self.path.endswith("/embeddings"):
                    stub.calls["embed"] = stub.calls.get("embed", 0) + 1
                    inp = payload.get("input")
                    texts = inp if isinstance(inp, list) else [inp]
                    res = {"data": [{"embedding": vec(str(t))} for t in texts]}
                else:
                    res = stub.answer(payload)
                code = res if isinstance(res, int) else 200
                blob = json.dumps({"error": "stub"} if code != 200 else res, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                try:
                    self.wfile.write(blob)
                except (BrokenPipeError, ConnectionResetError):
                    pass                          # 부른 쪽이 멈췄다(중단 시험)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()
        return False
