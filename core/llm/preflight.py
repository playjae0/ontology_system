# -*- coding: utf-8 -*-
"""칸 0.4 — **사전 점검** — LLM 비용을 쓰기 전에, 그 실행이 끝까지 쓸 경로를 먼저 왕복한다 (B98 ①).

사내 첫 산문 인입(2026-10-02)은 추출에 토큰 약 25만(사내 실측)을 쓴 **뒤** 구축의 후보
좁히기에서 임베딩이 막혀 실패했다. 막힐 것은 LLM을 쓰기 전에 안다 — 여기가 그 자리다.

- 항목은 **그 실행이 쓸 것만**이다(안 쓰는 갈래는 `None` = 건너뜀): ⓐ설정 · ⓑ채팅 ·
  ⓒ임베딩 · ⓓ그림 입력 · ⓔ공통 config·좌표 층 · ⓕ상태 루트 쓰기.
- **첫 실패에서 멈춘다** — 뒤 단계는 부르지 않는다(비용 0).
- 판정은 `llm-check`와 **같은 함수**다(`check.chat_roundtrip`·`embed_stage`·`image_stage` ·
  카탈로그는 `bootstrap`과 같은 `catalog.problems`) — 두 벌이면 점검이 통과한 뒤 인입이 막힌다.
  치명 여부만 그 실행의 필요로 정한다(임베딩·그림은 `llm-check`에선 경고, 여기선 쓰면 치명).
- mock: LLM 갈래(ⓑⓒⓓ)는 건너뛰고 ⓐⓔⓕ는 같다.

core는 화면을 갖지 않는다 — 단계 기록만 돌려준다(`cli/preflight.py`가 그린다).
"""
from __future__ import annotations

import os
import tempfile
import time

from core.llm import check, gateway

#: 단계 순서 — 화면의 한 줄이 이 순서다.
ORDER = ("설정", "채팅", "임베딩", "그림", "공통 config", "쓰기")


def run(*, chat=True, embed=False, images=False, catalog=True):
    """`{"stages": [...], "ok": bool, "secs": float, "since": usage}` — 단계는
    `{"label", "ok"(True/False/None), "detail", "next", "tag"}`. 첫 실패에서 멈춘다."""
    t0, u0 = time.monotonic(), gateway.usage_total()
    live = _live()
    out = []

    def done(ok):
        return {"stages": out, "ok": ok, "secs": time.monotonic() - t0, "since": u0}

    for label, fn in (("설정", lambda: _config(live, chat, embed)),
                      ("채팅", lambda: _chat() if live and chat else _skip(live)),
                      ("임베딩", lambda: _embed() if live and embed else _skip(live, embed)),
                      ("그림", lambda: _image() if live and images else _skip(live, images)),
                      ("공통 config", lambda: _catalog() if catalog else (None, "", "", "")),
                      ("쓰기", _write)):
        ok, detail, nxt, tag = fn()
        out.append({"label": label, "ok": ok, "detail": detail, "next": nxt, "tag": tag})
        if ok is False:
            return done(False)
    return done(True)


def _live():
    """실호출인가 — 판독은 `gateway.use_mock()` 하나다(시험은 이 함수만 바꿔 실호출 갈래를 잰다)."""
    return not gateway.use_mock()


def _skip(live, wanted=True):
    return None, "", "", ("mock" if not live and wanted else "건너뜀")


def _config(live, chat, embed):
    try:
        cfg = gateway.config()
    except gateway.NotConfigured as e:
        return False, str(e), "설정 파일을 고친다 — python run.py llm-check ①", ""
    src = gateway.sources_line()
    if not live:
        return True, src, "", ""
    need = (["url", "model"] if chat else []) + (["embed_model"] if embed else [])
    miss = [k for k in need if not cfg.get(k)]
    if miss:
        names = {"url": "LLM_GATEWAY_URL", "model": "CHAT_MODEL", "embed_model": "EMBED_MODEL"}
        return (False, f"필요한 키 없음 — {', '.join(names[k] for k in miss)} · {src}",
                "읽힌 설정 파일에 대문자 키로 적는다 — python run.py llm-check ①", "")
    return True, src, "", ""


def _stages():
    rec = []

    def add(i, label, ok, detail="", fatal=False):
        rec.append({"id": i, "label": label, "ok": ok, "detail": detail, "fatal": fatal})
        return ok
    return rec, add


def _chat():
    rec, add = _stages()
    cfg = gateway.config()
    raw = check.chat_roundtrip(cfg, add)
    if raw is None:
        bad = next((r for r in rec if r["ok"] is False), {"id": "", "label": "", "detail": ""})
        return (False, f"{bad['id']} {bad['label']} — {bad['detail']}",
                "python run.py llm-check   (단계별 원인)", "")
    gateway._account("chat", raw)        # 점검 왕복도 비용이다 — 끝 줄의 사용량에 든다
    return True, "", "", ""


def _embed():
    rec, add = _stages()
    cfg = gateway.config()
    check.embed_stage(cfg, add)
    r = rec[-1] if rec else {"ok": False, "detail": "단계 기록 없음"}
    if r["ok"] is not True:
        return (False, r["detail"],
                "EMBED_BACKEND·EMBED_MODEL을 확인한다(python run.py llm-check ⑥) · "
                "급하면 같은 명령에 --narrow overlap", "")
    return True, r["detail"], "", cfg.get("embed_backend") or ""


def _image():
    rec, add = _stages()
    check.image_stage(gateway.config(), add)
    r = rec[-1] if rec else {"ok": False, "detail": "단계 기록 없음"}
    if r["ok"] is not True:
        return False, r["detail"], "그림 요약 없이 넣는다 — 같은 명령에 --no-images", ""
    return True, "", "", ""


def _catalog():
    """ⓔ — `bootstrap`과 같은 판정(`catalog.problems` · 좌표 층) — 구축에서 터질 것을 앞에서."""
    from core.state import catalog
    from core.state.bootstrap import NoCoordLayer, coord_layer
    try:
        bad = catalog.problems()
        lay = coord_layer()
    except (catalog.CatalogError, NoCoordLayer) as e:
        return False, str(e), "python run.py bootstrap --dry-run   (같은 판정 · 쓰기 0)", ""
    except ValueError as e:                       # 층 config JSON이 깨졌다
        return False, f"층 config를 읽지 못했다 — {e}", "python run.py bootstrap --dry-run", ""
    if bad:
        return (False, " / ".join(f"{t} {m}" for t, m in bad),
                "python run.py bootstrap --dry-run   (같은 판정 · 쓰기 0)", "")
    return True, f"좌표 층 {lay}", "", ""


def _write():
    """ⓕ — 상태 루트에 임시 파일을 쓰고 지운다(자리는 `paths` — 폴더를 만드는 곳은 하나)."""
    from core import paths
    try:
        d = paths.ensure(paths.work())
        fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".preflight.", suffix=".tmp")
        os.close(fd)
        os.unlink(tmp)
    except OSError as e:
        return (False, f"{paths.show(paths.work())} — {type(e).__name__}: {e}",
                "상태 폴더 권한·공간을 확인한다(python doctor.py)", "")
    return True, "", "", ""
