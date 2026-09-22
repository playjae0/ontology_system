# -*- coding: utf-8 -*-
"""칸 5.1 — 뷰어 **서버** — 표준 라이브러리 HTTP · 읽기 전용 · 127.0.0.1 (B82 ①).

라우트는 전부 GET이고 **쓰기 라우트가 없다**(`do_POST`를 두지 않으면 501로 거절된다):

    /                     정적 화면 (static/index.html)
    /static/<파일>        화면 자산 — vendor 포함(외부 URL 0)
    /api/health           상태 루트·모드·등록·층·문서 (doctor 첫 줄과 같은 사실)
    /api/graph            전 층 통합 그래프 (GraphStore 경유 · 변환은 export와 한 자리)
    /api/query?q=…        질의 결과 + trace (CLI `--json`과 같은 묶음)
    /api/doc/<doc_id>     문서 대장 행 + 판정 집계 + 그 문서가 만든 노드·청크
    /api/funnel           문서 깔때기 · orphan 행
    /raw/<상대경로>       원본 파일 그대로 — `<상태>/raw/` 아래만 · 탈출 거부

**새로고침이면 최신 상태를 읽는다** — 구판은 뜬 시점의 HTML 한 장을 물고 있어
인입·재구축 뒤에 다시 띄워야 했다. 화면이 증거인 도구에서 그것은 증거가 낡는 것이다.
"""
from __future__ import annotations

import json
import mimetypes
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from cli.viewer import data as D
from core import paths
from core.llm import gateway

HOST = "127.0.0.1"          # **바깥에 열지 않는다** — 검증 도구이지 서비스가 아니다
PORT_TRIES = 40
STATIC = Path(__file__).resolve().parent / "static"


def _free_port(start):
    """빈 포트를 찾는다. `--port`를 준 자리부터 위로 훑는다."""
    for p in range(start, start + PORT_TRIES):
        with socket.socket() as s:
            try:
                s.bind((HOST, p))
                return p
            except OSError:
                continue
    raise SystemExit(f"[viewer] {start}부터 {PORT_TRIES}개를 봤지만 빈 포트가 없다\n"  # [상태]
                     f"  ▶ 다음 줄 — 빈 번호를 직접 준다:\n"
                     f"     python run.py viewer --port <번호>")


def _safe_under(root, rel):
    """`root` 아래의 실경로 — `..`·절대 경로·심볼릭 탈출은 **None**이다.

    원본을 내주는 라우트가 있으므로 이 함수가 그 문의 자물쇠다: 상태 루트 밖의
    파일이 한 번이라도 나가면 그것은 읽기 전용 도구가 아니라 파일 서버다.
    """
    try:
        base = Path(root).resolve()
        p = (base / unquote(str(rel)).lstrip("/")).resolve()
    except (OSError, ValueError):
        return None
    if p == base or base not in p.parents or not p.is_file():
        return None
    return p


class Handler(BaseHTTPRequestHandler):
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

    def _file(self, path):
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
            ctype += "; charset=utf-8"
        return self._send(200, path.read_bytes(), ctype)

    def do_GET(self):                                   # noqa: N802 (표준 서버 규약)
        u = urlparse(self.path)
        try:
            return self._route(u)
        except Exception as e:                          # noqa: BLE001
            # 사유를 화면까지 올린다 — 조용한 500은 「안 된다」로만 보이고 무엇이
            # 깨졌는지는 서버 콘솔에만 남는다.
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _route(self, u):
        if u.path in ("/", "/index.html"):
            return self._file(STATIC / "index.html")
        if u.path.startswith("/static/"):
            p = _safe_under(STATIC, u.path[len("/static/"):])
            return self._file(p) if p else self._send(404, b"404", "text/plain")
        if u.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")     # 화면 콘솔을 조용히
        if u.path == "/api/health":
            return self._json(200, D.health())
        if u.path == "/api/graph":
            return self._json(200, D.graph())
        if u.path == "/api/funnel":
            return self._json(200, D.funnel())
        if u.path.startswith("/api/doc/"):
            got = D.doc(unquote(u.path[len("/api/doc/"):]))
            return self._json(200, got) if got else self._json(
                404, {"error": "그 doc_id는 문서 대장에 없다"})
        if u.path == "/api/query":
            q = (parse_qs(u.query).get("q") or [""])[0].strip()
            if not q:
                return self._json(400, {"error": "q가 비었다"})
            # **CLI `--json`과 같은 묶음이다** — 화면이 보는 것과 CLI가 내는 것이
            # 다르면 둘 중 무엇이 맞는지 대조할 자리가 없어진다.
            from cli.query import answer, as_json
            # `as_json`이 ⑧까지 부른다 — CLI `--json`과 **같은 함수**다.
            return self._json(200, as_json(answer(q)))
        if u.path.startswith("/raw/"):
            p = _safe_under(paths.raw(), u.path[len("/raw/"):])
            return self._file(p) if p else self._send(
                404, "원본 자리(<상태>/raw/) 아래의 파일이 아니다".encode("utf-8"),
                "text/plain; charset=utf-8")
        return self._send(404, b"404", "text/plain; charset=utf-8")

    # 쓰기 라우트는 만들지 않는다 — do_POST를 두지 않으면 501로 거절된다.


def serve(port=8765):
    """서버를 띄우고 `(서버, 주소)`를 돌려준다 — 시험은 이것을 직접 부른다."""
    port = _free_port(port)
    srv = ThreadingHTTPServer((HOST, port), Handler)
    return srv, f"http://{HOST}:{port}/"


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
            raise SystemExit("[viewer] --port 뒤에 번호가 필요하다")               # [사용법]
        del args[i:i + 2]

    h = D.health()
    g = D.graph()
    srv, url = serve(port)
    print(f"[viewer] {url}")
    print(f"  모드 {h['mode']} · 노드 {len(g['nodes'])} · 엣지 {len(g['edges'])} · "
          f"층 {len(h['layers'])} · 문서 {h['docs']} · 상태 {h['home']}")
    print("  라우트: / · /api/graph · /api/query?q=… · /api/doc/<id> · "
          "/api/funnel · /raw/<경로> · /api/health   (쓰기 없음 — 읽기 전용)")
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
