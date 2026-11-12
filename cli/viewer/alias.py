# -*- coding: utf-8 -*-
"""칸 5.1 곁 — 뷰어 **「동의어」 탭의 서버 몫**(B200 ③ · 결정 `결정_동의어_점검.md` §2 6 · 7 · 9).

    GET  /api/aliases            점검 화면 — 판 · 수 · 「LLM이 빼자는 것」 · 노드 경로마다 별칭 표 · 보류 표기 · 비용 미리보기
    POST /api/aliases/review     LLM 검토 시작(배경 — 진행은 `/api/status`의 `aliases`)
    POST /api/aliases/approve    승인 묶음(행위자 · 화면의 판 · 처분들) → 반영 · 끝 화면 한 덩이

**쓰기 라우트는 이 둘뿐이다** — 그 밖의 POST는 거절(서버 `do_POST`) · 둘은 한 번에 하나(진행 중이면 거절 문면 · `BUSY`).
계산은 시스템 함수(`core/state/alias_audit` · `alias_review` · `alias_approve`)가 하고 여기서는 묶을 뿐이다(PF11).
"""
from __future__ import annotations

import threading

from core.state import alias_approve as AP, alias_audit as AA, alias_review as AR

#: 쓰기 둘의 자물쇠 — 진행 중이면 거절(같은 판정 목록을 두 손이 쓰지 않는다)
BUSY = threading.Lock()
LAST = {"review": None, "error": None}
BUSY_TEXT = "다른 쓰기가 진행 중이다 — LLM 검토 · 승인은 한 번에 하나(끝난 뒤 다시)"


def _row(it, rv):
    r = rv.get(it["k"]) or {}
    h = r.get("human") or {}
    return {"surface": it["surface"], "target": it["target"], "kind": it["kind"], "source": it.get("source"),
            "path": it.get("path"), "shared": it.get("shared") or [], "overlap": it.get("overlap") or [],
            "dict_miss": it.get("dict_miss", False), "rows": it.get("rows", 0), "docs": it.get("docs") or [],
            "unknown": it.get("unknown") or [], "samples": it.get("samples") or [], "dead": it.get("dead", False),
            "reason": it.get("reason"), "candidates": it.get("candidates") or [],
            "verdict": r.get("verdict"), "why": r.get("why"), "suggest": r.get("suggest"),
            "state": r.get("state"), "reviewed": AR.asked(r), "human": h.get("disposition"),
            "human_by": h.get("actor"), "human_to": h.get("to")}


def aliases():
    """점검 화면의 묶음 — 짝 · 보류 표기를 지금 세고 판정 목록을 붙인다(쓰기 0)."""
    from core.state.world import World
    ps = AA.pairs(World())
    its = AR.items(ps)
    rv = AR.Review.open()
    tg = AR.targets(rv, its)
    rows = [_row(it, rv) for it in its]
    groups = {}
    for r in rows:
        if r["kind"] == AR.PAIR:
            groups.setdefault((r["path"], r["target"]["canonical"]), []).append(r)
    c = AA.counts(ps, len(tg))
    pv = AR.preview(tg)
    return {"stamp": AP.stamp(), "counts": {**c, "pending": sum(1 for r in rows if r["kind"] == AR.CANDIDATE)},
            "line": AA.line(c), "preview": {**pv, "line": AR.preview_line(pv)},
            "wrong": sorted([r for r in rows if r["kind"] == AR.PAIR and r["verdict"] == AR.WRONG and not r["human"]],
                            key=lambda r: (-r["rows"], r["surface"])),
            "groups": [{"path": p, "canonical": c_, "pairs": rs} for (p, c_), rs in sorted(groups.items())],
            "pending": [r for r in rows if r["kind"] == AR.CANDIDATE],
            "dispositions": list(AP.DISPOSITIONS), "progress": dict(AR.PROGRESS),
            "last": LAST["review"], "error": LAST["error"]}


def start_review():
    """LLM 검토를 배경으로 — `(코드, 몸)` · 진행 중이면 409."""
    if not BUSY.acquire(blocking=False):
        return 409, {"error": BUSY_TEXT}
    tg = AR.targets(AR.Review.open(), AR.items())
    pv = AR.preview(tg)
    LAST["error"] = None

    def work():
        try:
            LAST["review"] = AR.run(tg)
        except Exception as e:                              # noqa: BLE001 — 사유를 화면까지(조용히 비지 않는다)
            LAST["error"] = f"{type(e).__name__}: {e}"
        finally:
            BUSY.release()
    AR.PROGRESS.update(state="running", done=0, total=len(tg), batches=pv["batches"], calls=0)
    threading.Thread(target=work, daemon=True).start()
    return 202, {"started": True, "preview": {**pv, "line": AR.preview_line(pv)}}


def approve(body):
    """승인 묶음 — `(코드, 몸)` · 행위자 없음 · 진행 중이면 거절."""
    actor = str((body or {}).get("actor") or "").strip()
    if not actor:
        return 400, {"error": "행위자 이름을 적는다 — 승인은 이름으로 남는다"}
    if not BUSY.acquire(blocking=False):
        return 409, {"error": BUSY_TEXT}
    try:
        out = AP.approve(list((body or {}).get("decisions") or []), actor, made=(body or {}).get("stamp"))
    except AP.Refused as e:
        return 400, {"error": str(e)}
    finally:
        BUSY.release()
    return 200, {**out, "refused": [list(x) for x in out["refused"]]}
