# -*- coding: utf-8 -*-
"""칸 0.5 · ④작업 — **쪽 캡처 보관**(B156 ⑤) — PPT · PDF 쪽마다 캡처 한 장을 원본에서 한 번 떠서 판독 · 추출이 같은 판을 쓴다.

    pages(doc_id, path, want)    `({쪽 번호: 바이트}, 사유 또는 None)` — 이 실행의 캐시 → 보관분(원본 해시 · 쪽 수가 같을 때) → 렌더
    ref(doc_id, n)               보관 캡처 한 장의 기록 표기(봉투의 판독 블록 → md 링크) · 없으면 None
    stats()                      `[(doc_id, 쪽 수, 바이트)]` — `show dist captures`의 재료

**손잡이 `keep_page_captures`**(기본 켬 — 닫힌 목록 · 문서 7 §7.1)가 켜져 있으면 렌더한 쪽을 ④작업 단
`work/captures/<doc_id>/p001.jpg …`(JPEG · 긴 변 `MAX_EDGE`px)와 `index.json`(원본 해시 · 쪽 수)으로 두고, 다음 실행은 원본이
같으면 렌더 없이 그것을 쓴다(문서마다 렌더 한 번). 끄면 지금처럼 메모리만(보관분을 읽지도 쓰지도 않는다). **원본 바이너리 · 그림
원본은 저장하지 않는다** — 쪽 캡처는 원본(`raw/`)에서 다시 만들 수 있는 ④작업 산출이다(클린 · 기본 fresh가 지운다).
JPEG 저장은 선택 의존(Pillow · 지연 import) — 없으면 보관만 꺼지고 그 사실을 한 줄 · 판독 · 추출은 메모리 캡처(PNG)로 돈다.
"""
from __future__ import annotations

import hashlib
import io
import json

from core import paths
from core.state import log, store

_LOG = log.get(__name__)

#: 쪽 캡처 보관(사내 손잡이 `keep_page_captures` — 기본 켬)
KEEP = True
#: 보관 JPEG의 긴 변(px) · 품질(창작 기본값 — 렌더 상한과 같은 1,600)
MAX_EDGE = 1600
QUALITY = 85
INDEX = "index.json"

#: 이 실행의 캡처 — `{doc_id: ({쪽 번호: 바이트}, 사유 또는 None)}`(문서마다 한 번 — 판독 · 추출이 같은 판 · `extract_unit._PAGES`)
_PAGES = {}
_SAID = set()


def keep_on():
    from core.state import knobs
    return bool(knobs.get("keep_page_captures"))


def mime(blob):
    """캡처 바이트의 형식 — JPEG(보관분) 또는 PNG(렌더)."""
    return "image/jpeg" if (blob or b"")[:3] == b"\xff\xd8\xff" else "image/png"


def page_file(doc_id, n):
    """보관 캡처 한 장의 자리(`work/captures/<doc_id>/p001.jpg`)."""
    return paths.captures(doc_id, f"p{int(n):03d}.jpg")


def _source(path):
    from parser.struct_map import source_hash
    return source_hash(path)


def _kept(doc_id, path, want):
    """보관분 `{쪽: 바이트}` — 원본 해시 · 쪽 수가 같고 파일이 다 있을 때만(아니면 None — 다시 뜬다)."""
    idx = paths.captures(doc_id, INDEX)
    if not idx.exists():
        return None
    try:
        m = json.loads(idx.read_text(encoding="utf-8"))
        if m.get("source") != _source(path) or (want and m.get("pages") != want):
            return None
        return {n: page_file(doc_id, n).read_bytes() for n in range(1, int(m["pages"]) + 1)}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _jpeg(png):
    from PIL import Image                                   # 선택 의존 — 지연 import
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.thumbnail((MAX_EDGE, MAX_EDGE))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=QUALITY, optimize=True)
    return buf.getvalue()


def _say_once(key, line):
    if key not in _SAID:
        _SAID.add(key)
        print(line)
        _LOG.info(line.strip())


def _keep(doc_id, path, got):
    """렌더한 쪽을 JPEG로 보관하고 그 바이트를 돌려준다 — 못 바꾸면 보관 0 · 렌더 바이트 그대로."""
    try:
        jp = {n: _jpeg(b) for n, b in got.items()}
    except ImportError:
        _say_once("pil", "   캡처 보관 꺼짐 — Pillow 없음(pip install Pillow) · 판독 · 추출은 메모리 캡처로")
        return got
    except Exception as e:                                  # noqa: BLE001 — 그림이 아닌 바이트 · 깨진 렌더는 보관하지 않는다
        _LOG.info("캡처 보관 안 함 — %s: %s", type(e).__name__, e)
        return got
    for n, b in jp.items():
        p = page_file(doc_id, n)
        paths.ensure(p)
        store.atomic_write_bytes(p, b)
    m = {"doc_id": doc_id, "source": _source(path), "pages": len(jp), "max_edge": MAX_EDGE, "jpeg_q": QUALITY,
         "sha": {str(n): hashlib.sha256(b).hexdigest()[:16] for n, b in jp.items()}}
    store.atomic_write_bytes(paths.captures(doc_id, INDEX), (json.dumps(m, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return jp


def pages(doc_id, path, want=None):
    """그 문서의 캡처 `({쪽 번호: 바이트}, 사유 또는 None)` — 문서마다 한 번(이 실행의 캐시) · 보관분 → 렌더(`parser.render` 판정 한 자리) ·
    보이는 쪽 수(`want`)와 렌더 수가 다르면 붙이지 않는다(틀린 쪽을 보내느니 없는 편이 낫다)."""
    if doc_id in _PAGES:
        return _PAGES[doc_id]
    keep = keep_on()
    got, why = (_kept(doc_id, path, want) if keep else None), None
    if got is None:
        from parser import render
        ok, _route, why = render.capture_path(path)          # 캡처 가능 판정 한 자리 (B128 ①)
        if ok:
            try:
                got = render.render_pages(path)
            except Exception as e:                            # noqa: BLE001 — 캡처 없이 진행한다
                why = f"{type(e).__name__}: {e}"
        if got and want and len(got) != want:
            _LOG.warning("캡처 — 렌더 %d쪽 · 보이는 쪽 %d — 대응이 서지 않아 붙이지 않는다", len(got), want)
            got, why = None, f"렌더 {len(got)}쪽 ≠ 보이는 쪽 {want}"
        if got and keep:
            got = _keep(doc_id, path, got)
    _PAGES[doc_id] = (dict(got) if got else {}), (None if got else (why or "렌더 없음"))
    return _PAGES[doc_id]


def ref(doc_id, n):
    """보관 캡처 한 장의 기록 표기(상태 루트 기준 — `work/captures/<doc_id>/p001.jpg`) · 보관분이 없으면 None — 봉투의 판독 블록에
    실려 md가 상대 경로로 건다(md는 봉투만 읽는다)."""
    p = page_file(doc_id, n)
    return str(paths.rel_to_home(p)).replace("\\", "/") if p.exists() else None


def stats():
    """`[(doc_id, 쪽 수, 바이트)]` — 보관 캡처(문서마다) · `show dist captures`."""
    root = paths.captures()
    out = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        fs = sorted(d.glob("p*.jpg")) if d.is_dir() else []
        if fs:
            out.append((d.name, len(fs), sum(f.stat().st_size for f in fs)))
    return out
