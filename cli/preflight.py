# -*- coding: utf-8 -*-
"""칸 0.4 — 사전 점검의 **화면** (B98 ①) — 판정은 `core/llm/preflight.run` 하나다.

통과면 한 줄, 실패면 첫 실패의 원인과 **그대로 칠 다음 줄**을 내고 멈춘다(파싱 0 ·
LLM 추가 0 · 쓰기 0). 거는 자리: `ingest-file`·`ingest-dir`(실행당 1회) · `cli.extract` ·
`register generate`·`review` — 선택·시트 역할 다음, **파싱 전**.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from cli import _screen
from core.llm import preflight


def has_images(path):
    """문서에 그림이 있나 — **읽기만**(zip 안의 `media/` · PDF의 이미지 객체). 모르면 False."""
    p = Path(path)
    try:
        if zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as z:
                return any("/media/" in n for n in z.namelist())
        if p.suffix.lower() == ".pdf":
            return b"/Subtype /Image" in p.read_bytes() or b"/Subtype/Image" in p.read_bytes()
    except OSError:
        return False
    return False


def gate(*, chat=True, embed=False, images=False, catalog=True):
    """사전 점검을 돌리고 그린다 — 돌려주는 것은 통과 여부."""
    r = preflight.run(chat=chat, embed=embed, images=images, catalog=catalog)
    names = []
    for s in r["stages"]:
        tag = s["tag"] if s["ok"] is None else s.get("tag")
        names.append(s["label"] + (f"({tag})" if tag else ""))
    if r["ok"]:
        from core.llm import gateway
        _screen.say(f"   사전 점검 — {' · '.join(names)} — 통과 ({r['secs']:.1f}초 · "
                    f"{_screen.tokens(gateway.usage_total(), r['since'])})", "head")
        return True
    bad = r["stages"][-1]
    _screen.say(f"   사전 점검 — **{bad['label']}**에서 멈춘다 (파싱 0 · LLM 추가 0 · 쓰기 0)",
                "fail")
    for ln in str(bad["detail"]).split("\n"):
        if ln.strip():
            print(f"     {ln.strip()}")
    if bad["next"]:
        print(f"   ▶ 다음 줄 — {bad['next']}")
    return False
