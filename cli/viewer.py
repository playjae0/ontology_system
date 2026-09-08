# -*- coding: utf-8 -*-
"""검증 뷰어 — 그래프 그림 위에서 질의가 도는지 보는 창구 (문서 7 시각화 3형태 · B52).

**플랫폼이 아니다.** 사내 서비스 창구는 별도 레포이고, 이것은 **이 시스템 안에서
「그래프와 답이 서로 맞는가」를 눈으로 보는 검증 도구**다. 그래서 규율이 다르다:

- **읽기만 한다.** 쓰기 라우트가 없다 — 그래프·큐·사전에 한 줄도 쓰지 않는다.
  파생물에서 그래프를 고치는 경로는 없다(문서 1 P5)는 것이 화면에도 적용된다.
- **표준 라이브러리만.** CDN 0 · pip 0. 사내망에서 화면이 비어 뜨는 일이 없어야
  검증 도구로 쓸 수 있다(`export html`이 인라인 렌더러를 싣는 이유와 같다).
- **템플릿은 `cli/export.py`의 것 하나다.** 여기서 HTML을 다시 쓰지 않는다 —
  복제하면 「뷰어에서 본 그림」과 「내보낸 그림」이 갈린다.
- **mock 관문 비대상**이다. 관측 창구라 `doctor`와 같은 자리에 선다. 대신 모드를
  숨기지 않는다 — 화면 머리에 `mock`/`실호출` 배지가 상시 뜬다(B42 ⑤의 취지).

사용: python run.py viewer [--port N] [--no-browser]
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core import llm

HOST = "127.0.0.1"          # **바깥에 열지 않는다** — 검증 도구이지 서비스가 아니다
PORT_TRIES = 40


def _free_port(start):
    """빈 포트를 찾는다. `--port`를 준 자리부터 위로 훑는다."""
    for p in range(start, start + PORT_TRIES):
        with socket.socket() as s:
            try:
                s.bind((HOST, p))
                return p
            except OSError:
                continue
    raise SystemExit(f"[viewer] {start}부터 {PORT_TRIES}개를 봤지만 빈 포트가 없다")


def _world_snapshot():
    """뜬 시점의 그래프 한 장. **질의와 달리 매번 다시 읽지 않는다** —
    화면의 그림은 스냅샷이고, 그 사실을 칩의 「그래프에 없음」이 드러낸다."""
    from cli.export import _world, build_html, graph_data
    world = _world()
    nodes, edges = graph_data(world)
    return build_html(world, query_panel=True).encode("utf-8"), nodes, edges, len(world)


def _handler(page, health):
    class H(BaseHTTPRequestHandler):
        # 요청 로그는 stderr로 새 줄을 계속 뱉는다 — 주소 한 줄만 남기려고 끈다.
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(200, page, "text/html; charset=utf-8")
            if u.path == "/api/health":
                return self._json(200, health)
            if u.path == "/api/query":
                q = (parse_qs(u.query).get("q") or [""])[0].strip()
                if not q:
                    return self._json(400, {"error": "q가 비었다"})
                # **`--json`과 같은 묶음이다** — 화면이 보는 것과 CLI가 내는 것이
                # 다르면 둘 중 무엇이 맞는지 대조할 자리가 없어진다.
                from cli.query import answer, as_json
                try:
                    return self._json(200, as_json(answer(q)))
                except Exception as e:                  # noqa: BLE001
                    # 사유를 화면까지 올린다 — 조용한 500은 「질의가 안 된다」로만
                    # 보이고 무엇이 깨졌는지는 서버 콘솔에만 남는다.
                    return self._json(500, {"error": f"{type(e).__name__}: {e}"})
            return self._send(404, b"404", "text/plain; charset=utf-8")

        # 쓰기 라우트는 만들지 않는다 — do_POST를 두지 않으면 501로 거절된다.
    return H


def main(args):
    args = list(args)
    no_browser = "--no-browser" in args
    while "--no-browser" in args:
        args.remove("--no-browser")
    port = 8765
    if "--port" in args:
        i = args.index("--port")
        try:
            port = int(args[i + 1])
        except (IndexError, ValueError):
            raise SystemExit("[viewer] --port 뒤에 번호가 필요하다")
        del args[i:i + 2]

    mode = "mock" if llm.use_mock() else "실호출"
    page, nodes, edges, n_layers = _world_snapshot()
    health = {"mode": mode, "nodes": len(nodes), "edges": len(edges),
              "layers": n_layers}
    port = _free_port(port)
    srv = ThreadingHTTPServer((HOST, port), _handler(page, health))
    url = f"http://{HOST}:{port}/"

    print(f"[viewer] {url}")
    print(f"  모드 {mode} · 노드 {len(nodes)} · 엣지 {len(edges)} · 층 {n_layers}")
    print("  라우트: / · /api/query?q=… · /api/health   (쓰기 없음 — 읽기 전용)")
    print("  Ctrl+C로 멈춘다")
    if not no_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[viewer] 멈췄다")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    main(sys.argv[1:])
