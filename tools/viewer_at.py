# -*- coding: utf-8 -*-
"""뷰어를 **다른 상태 폴더**(백업 등)에서 띄운다 — 지금 `ONTO_HOME`은 건드리지 않는다.

    python tools/viewer_at.py <상태 폴더> [--port N] [--no-browser] [--in-place] [--warm]

- 기본: 그 폴더를 임시 사본으로 복사하고(원본 문서 `raw/`는 링크 — 링크를 못 만들면 원본 열람만 빠진다) 사본에서 띄운다.
  백업 폴더는 한 바이트도 바뀌지 않는다 — 질의가 만드는 벡터 · 기록은 사본에 쌓이고 끝나면 지운다.
- `--in-place`: 사본 없이 그 폴더에서 바로(질의 창을 쓰면 그 폴더의 `work/vectors/` 등이 바뀐다).
- `--warm`: 띄울 때 질의 벡터 미리 만들기를 켠다(임베딩 호출 — 비용). 기본은 끔 — 질의 창을 쓰면 그때 만든다.
- `--port` · `--no-browser`는 `run.py viewer`와 같다. 뷰어 자체는 읽기 전용이다(쓰기 라우트 0 — `cli/viewer/server.py`).
"""
from __future__ import annotations

import atexit
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = "사용: python tools/viewer_at.py <상태 폴더> [--port N] [--no-browser] [--in-place] [--warm]"


def _take(args, flag):
    hit = flag in args
    while flag in args:
        args.remove(flag)
    return hit


def _copy(src):
    """임시 사본 — `raw/`는 링크(크다 · 읽기만) · 나머지는 복사. 돌려주는 것은 사본 폴더."""
    tmp = Path(tempfile.mkdtemp(prefix="onto_view_"))
    atexit.register(shutil.rmtree, tmp, True)
    signal.signal(signal.SIGTERM, lambda *_a: sys.exit(0))       # 창을 닫아 끝나도 사본을 지운다
    dst = tmp / src.name
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("raw"), symlinks=True)
    raw = src / "raw"
    if raw.is_dir():
        try:
            (dst / "raw").symlink_to(raw, target_is_directory=True)
        except OSError:
            print("[viewer_at] raw/ 링크를 만들지 못했다 — 원본 문서 열람(/raw)만 빠진다 · 그래프 · 노드 · 문서 화면은 그대로")
    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file() and not f.is_symlink())
    print(f"[viewer_at] 사본 {dst} · {size / 1e6:,.1f}MB (끝나면 지운다)")
    return dst


def main(argv):
    args = list(argv)
    if not args or args[0].startswith("-"):
        raise SystemExit(USAGE)
    src = Path(args.pop(0)).expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"[viewer_at] 폴더가 없다 — {src}\n{USAGE}")
    if not ((src / "data").is_dir() or (src / "layers").is_dir()):
        raise SystemExit(f"[viewer_at] 상태 폴더가 아니다(data/ · layers/ 없음) — {src}")
    in_place, warm = _take(args, "--in-place"), _take(args, "--warm")
    home = src if in_place else _copy(src)
    os.environ["ONTO_HOME"] = str(home)
    os.environ["USE_MOCK"] = "0"                       # mock 모드는 ONTO_HOME을 무시한다
    sys.path.insert(0, str(ROOT))
    from cli.viewer import server as S
    if not warm:
        S._warm = lambda: print("  [viewer] 벡터 미리 만들기 끔(--warm으로 켠다) — 질의 창을 쓰면 그때 만든다", flush=True)
    print(f"[viewer_at] 상태 {src}" + (" — 그 폴더 그대로(--in-place)" if in_place else " — 사본에서 (원본 그대로)"))
    return S.main(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
