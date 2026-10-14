# -*- coding: utf-8 -*-
"""칸 0.3 — **공통 진입 함수** — 진입점 전부가 이 함수 하나를 지난다 (B99 ③).

사내(2026-10-06): 하루치 로그를 문서별로 가를 수 없었다 — 실행 경계가 없고, 화면 줄 대부분이
로그에 없고, `python -m cli.register generate`는 로그 파일 자체가 없었다. 여기서 한 번에 고친다:

- **로그 설정**(`log.setup`) — 진입점이 따로 하지 않는다.
- **화면 출력 전체를 그 명령의 로그로 복사**한다(stdout·stderr · 색 코드 제거 · 사람이 친 답 포함 ·
  같은 줄 두 번 0) — 자리는 `work/logs/<명령>_<날짜>.log`. `python -m cli.<x>`와 `run.py <x>`가
  같은 이름을 쓴다(`name_of`).
- **실행 머리줄·끝줄**(`===== 실행 시작 …` / `===== 실행 끝 …`) — 하루 파일 안에서 실행이 갈린다.
- **문서 머리줄**(`doc_header`) — 문서를 다루는 명령이 부르고, 게이트웨이의 문서 문맥을 채운다.

복사는 로거 `onto.screen` 하나로 간다 — 파일에 쓰는 손이 하나라 줄 순서가 섞이지 않는다.
콘솔 로그 핸들러는 **원래 stderr**에 쓰게 해 같은 줄이 두 번 남지 않는다.
"""
from __future__ import annotations

import builtins
import io
import os
import sys
import threading
import time
from pathlib import Path

from cli import _screen
from core.state import log

_SCREEN = log.get("screen")


class _Tee(io.TextIOBase):
    """화면 스트림 + 로그 — 줄이 끝날 때마다 색을 벗겨 로거로 보낸다(화면은 그대로)."""

    def __init__(self, inner):
        self.inner, self.buf, self.gone = inner, "", False

    def write(self, s):
        # 로그가 먼저다 — 화면이 닫혀 못 나간 줄도 기록에는 남는다(B109 ②)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self._emit(line)
        self._screen(self.inner.write, s)
        return len(s)

    def _screen(self, fn, *a):
        """화면 쓰기 — 닫혔으면(`BrokenPipeError`) 표시를 남기고 `log.ScreenClosed`로 올린다."""
        if self.gone:
            raise log.ScreenClosed("화면 출력이 닫혔다")
        try:
            fn(*a)
        except BrokenPipeError:
            self.gone = True
            raise log.ScreenClosed("화면 출력이 닫혔다") from None

    def _emit(self, line):
        for part in line.split("\r"):            # 덮어쓰기 진행 줄도 한 줄씩 남긴다
            if part.strip():
                _SCREEN.info("%s", _screen.strip_ansi(part))

    def answer(self, text):
        """사람이 친 답 — 묻는 줄(아직 줄바꿈 전)에 붙여 한 줄로 남긴다."""
        self._emit(self.buf + str(text))
        self.buf = ""

    def flush(self):
        # 한 번 닫혔으면 그 뒤의 flush · 정리는 조용히 — 멈춤 신호는 쓰기만 낸다(B110 ② · Python 3.13은 끝에
        # 이 객체를 정리하며 flush를 한 번 더 부른다 — 거기서 던지면 「Exception ignored」 트레이스백이 남는다)
        if not self.gone:
            self._screen(self.inner.flush)

    def drain(self):
        if self.buf:
            self._emit(self.buf)
            self.buf = ""

    def isatty(self):
        try:
            return self.inner.isatty()
        except (AttributeError, ValueError):
            return False

    def fileno(self):
        return self.inner.fileno()

    @property
    def encoding(self):
        return getattr(self.inner, "encoding", "utf-8")


#: `python -m cli.<x>` → `run.py`와 같은 명령 이름(같은 로그 파일).
_NAMES = {"llmcheck": "llm-check", "skeleton": "skeleton-confirm"}


def name_of(module, argv):
    """모듈 이름과 인자로 명령 이름을 정한다 — `run.py <명령>`과 같은 이름."""
    short = module.rsplit(".", 1)[-1] if module != "cli.register.__main__" else "register"
    if short == "ingest":
        paths_ = [a for a in argv if not a.startswith("-")]
        return "ingest-dir" if (not paths_ or any(Path(p).is_dir() for p in paths_)) \
            else "ingest-file"
    return _NAMES.get(short, short)


def _code_rev():
    """코드 판 — git HEAD 짧은 해시(없으면 「모름」). 읽기만 한다."""
    root = Path(__file__).resolve().parent.parent
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = root / ".git" / head.split(" ", 1)[1]
            head = ref.read_text(encoding="utf-8").strip() if ref.exists() else head
        return head[:7]
    except OSError:
        return "모름"


def _usage_tail():
    from core.llm import gateway
    by = gateway.usage_by()
    if not by:
        return "LLM 0"
    return " · ".join(f"{pt} 호출 {v['calls']:,} · 입력 {v['prompt']:,} · 출력 {v['completion']:,}"
                      for pt, v in sorted(by.items()))


def doc_header(doc_id, doc_type=None, kind=None, lenses=None):
    """**문서 머리줄**(B99 ③) — 문서를 다루는 명령 전부가 이 함수를 부른다 · 게이트웨이 문서 문맥을 채운다."""
    from core.llm import gateway
    gateway.set_doc(doc_id)
    bits = [f"── 문서 {doc_id}"]
    if doc_type:
        bits.append(f"doc_type {doc_type}")
    if kind:
        bits.append(f"형태 {kind}")
    if lenses:
        bits.append(f"렌즈 {' · '.join(lenses)}")
    _screen.say("   " + " · ".join(bits), "head")


def _adopt_ops_log():
    """**사람 판단 기록의 옛 자리**(③ `data/ops_log.json`)를 ②등록으로 — 첫 실행에서 한 번(B106 ③ · 두 벌 금지)."""
    try:
        from core.state import oplog
        r = oplog.adopt_legacy()
    except Exception as e:                          # noqa: BLE001 — 옮기지 못해도 명령은 돈다(문면으로 말한다)
        print(f"[사람 판단 기록] 옛 자리 옮김(이름 채움 포함)에서 멈췄다 — {e} · 다음 실행 · "
              "python run.py ops replay all --actor <사람> --dry-run · 재구축 계획이 다시 한다")
        return
    if r:
        from cli.ops import backfill_lines
        from core import paths
        from core.state import store
        print(f"[사람 판단 기록] 옛 자리 data/ops_log.json의 {r['moved']:,}건을 ②등록 "
              f"{paths.show(store.path(store.OPS_LOG))}로 옮겼다(재구축 · fresh가 지우지 않는다 — B106 ③)")
        for ln in backfill_lines(r):                # 옮길 때 이름을 채운다(B107 ① — 그래프가 아직 그 id를 안다)
            print("[사람 판단 기록] " + ln)


def _fill_alias_book():
    """**별칭 대장 처음 채움**(B108 ①) — 대장 파일이 아직 없으면(B108 전 상태의 첫 실행) 지금 그래프의 seed 밖
    별칭을 이름으로 채운다 — 지우기 전에. 채울 것이 없으면 파일을 만들지 않는다(bootstrap이 만든다)."""
    try:
        from core.state import alias_book
        if alias_book.AliasBook.exists():
            return
        r = alias_book.backfill()
    except Exception as e:                          # noqa: BLE001 — 채우지 못해도 명령은 돈다(문면으로 말한다)
        print(f"[별칭 대장] 처음 채움에서 멈췄다 — {e} · 재구축 계획이 다시 채운다(python run.py rebuild)")
        return
    if r["filled"]:
        from core import paths
        from core.state import store
        print(f"[별칭 대장] 지금 그래프의 seed 밖 별칭 {r['filled']:,}건을 이름으로 채웠다 — "
              f"{paths.show(store.path(store.ALIAS_BOOK))}(골격 대상 {r['skeleton']:,} · 기본 fresh가 남긴다 — B108 ①)")


def _closed(command, streams, finished):
    """**화면이 닫혔다**(B109 ②) — 트레이스백 0 · 로그에 한 줄 · 닫힌 스트림은 `os.devnull`로 돌려 끝의
    flush가 다시 죽지 않게 한다. 돌려주는 것은 종료 코드(`log.SCREEN_CLOSED`)."""
    for t in streams:
        if t.gone:
            try:
                os.dup2(os.open(os.devnull, os.O_WRONLY), t.inner.fileno())
            except (OSError, ValueError, AttributeError, io.UnsupportedOperation):
                pass
    # 쓰던 문서가 있었으면 되돌림 경계가 바로 위에 「되돌림」 · 「저장 뒤 멈춤」 줄을 남겼다(B109 ②)
    _SCREEN.warning("%s — %s · 종료 코드 %s", "화면이 닫혔다(명령은 끝까지 돌았다 — 끝 화면만 못 나갔다)"
                    if finished else "화면이 닫혀 멈췄다", command, log.SCREEN_CLOSED)
    return log.SCREEN_CLOSED


def run(command, main, argv=None):
    """진입점 하나 — 로그 설정 · 화면 복사 · 실행 머리/끝 줄 · 종료 코드. 돌려주는 것은 종료 코드."""
    argv = list(sys.argv[1:] if argv is None else argv)
    argv, flags = _screen.take_flags(argv)
    real_err = sys.stderr
    log.setup(command=command, console="INFO" if flags["verbose"] else None, force=True,
              console_stream=real_err)
    out, err = _Tee(sys.stdout), _Tee(sys.stderr)
    orig_input = builtins.input

    def _input(prompt=""):
        out.write(str(prompt))
        out.flush()
        # 답이 없으면(EOF · Ctrl-C) 묻는 줄은 버퍼에 남는다 — 화면처럼 다음 출력이 같은 줄에 붙는다
        ans = orig_input("")
        out.answer(ans)
        return ans

    from core import paths
    from core.llm import gateway
    t0 = time.monotonic()
    log.HEADER = (f"===== 실행 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} · {' '.join([command] + argv)}"
                  f" · 상태 폴더 {paths.show(paths.home())} · 모드 "
                  f"{'mock' if gateway.use_mock() else '실호출'} · 코드 판 {_code_rev()} =====")
    _SCREEN.info("%s", log.HEADER)
    sys.stdout, sys.stderr, builtins.input = out, err, _input
    rc, closed = 0, False
    hook0 = threading.excepthook
    # 화면에 쓰는 스레드(`_screen.ticker`의 30초 줄)도 닫힌 화면에서 트레이스백 없이 끝난다 — 본 흐름은 다음 줄에서 멈춘다
    threading.excepthook = lambda a: None if issubclass(a.exc_type, log.ScreenClosed) else hook0(a)
    try:
        try:
            _adopt_ops_log()
            _fill_alias_book()
            rc = main(argv) or 0
        except SystemExit as e:
            code = e.code
            if isinstance(code, str):
                print(code, file=sys.stderr)    # 거부 문면도 로그에 남는다
                rc = 1
            else:
                rc = code or 0
        except KeyboardInterrupt:
            print("\n[중단] 사람이 멈췄다(Ctrl-C)", file=sys.stderr)
            rc = 130
    except log.ScreenClosed:                    # 화면이 닫혔다 — `| head` 따위(B109 ② · 진입점 전부 이 자리)
        closed = True
        rc = _closed(command, (out, err), finished=False)
    finally:
        out.drain()
        err.drain()
        if not closed:                          # 파이프의 화면은 블록 버퍼다 — 닫힘이 끝의 flush에서야 드러난다
            try:
                out.flush()
                err.flush()
            except log.ScreenClosed:
                code = _closed(command, (out, err), finished=True)
                rc = rc or code                 # 명령 자신의 실패 코드가 먼저다
        sys.stdout, sys.stderr, builtins.input = out.inner, err.inner, orig_input
        threading.excepthook = hook0
        _SCREEN.info("===== 실행 끝 %s · 종료 코드 %s · 경과 %.1f초 · %s =====",
                     time.strftime("%Y-%m-%d %H:%M:%S"), rc, time.monotonic() - t0,
                     _usage_tail())
    return rc


def main_module(module, main):
    """`if __name__ == "__main__":` 자리 — `sys.exit(_entry.main_module(__spec__.name, main))`."""
    argv = sys.argv[1:]
    return run(name_of(module, argv), main, argv)


__all__ = ["run", "main_module", "doc_header", "name_of"]
