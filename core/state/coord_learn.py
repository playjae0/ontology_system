# -*- coding: utf-8 -*-
"""칸 2.8 — **좌표 학습 기록의 사람 손** — 목록 · 승격 · 거부 · 새 공정 후보 (B101 ②③).

좌표 태깅(⑨)이 목록 밖 표기를 골격 노드로 채택하면 파서가 그 대응을 학습 기록(③진실
`data/coord_learned.json`)에 남기고 **다음부터 바로 쓴다**(LLM 0). 사람 보증은 아니다 —
여기서 사람이 보고 **승격**(골격 `ALIASES`로 — 다음 줄 `bootstrap`)하거나 **거부**(기록을 지운다 —
다음엔 다시 묻는다)한다. 「목록에 없음」(null) 답은 해소에 쓰지 않고 **새 공정 후보**로만 보인다 —
골격을 넓힐지는 사람이 정한다(문서 3 §3.6 원칙 9).

코드에 층 어휘 0 — 좌표 층은 `bootstrap.coord_layer()`가 답한다.
"""
from __future__ import annotations

import json

from core import paths
from core.state import store


class LearnRefused(Exception):
    """승격·거부 거부 — 문면에 다음 줄이 있다."""


def book():
    d = store.read(store.COORD_LEARNED, {}) or {}
    return {"채택": dict(d.get("채택") or {}), "목록밖": dict(d.get("목록밖") or {})}


def rows():
    """학습 기록 — `[(표기, 기록)]` (적중 많은 순 · 표기 순)."""
    b = book()["채택"]
    return sorted(b.items(), key=lambda kv: (-int(kv[1].get("hits") or 0), kv[0]))


def candidates():
    """**새 공정 후보** — 태깅이 「목록에 없음」으로 답한 표기 · 행 수 · 문서 · 처음 본 때 +
    그 표기의 `orphan_anchor` 행 수(큐) — `[(표기, 기록, 큐 행)]` (행 많은 순)."""
    q = {}
    for x in store.read(store.QUEUE, []):
        if x.get("kind") == "orphan_anchor" and not x.get("resolution"):
            pl = x.get("payload") or {}
            s = pl.get("surface")
            if s:
                q[s] = q.get(s, 0) + len(pl.get("rows") or [1])
    out = [(s, r, q.get(s, 0)) for s, r in book()["목록밖"].items()]
    return sorted(out, key=lambda t: (-int(t[1].get("rows") or 0), t[0]))


def _skeleton_file():
    from core.state.bootstrap import coord_layer, load_config
    lay = coord_layer()
    src = ((load_config(lay).get("skeleton") or {}).get("source"))
    if not src:
        raise LearnRefused(
            f"[상태] 좌표 층 {lay}의 골격이 파일이 아니다(config 인라인) — 승격할 `ALIASES` 자리가 없다\n"
            f"  ▶ 다음 줄 — 표기를 노드에 사람이 잇는다: python run.py ops alias {lay} <노드> <표기> --actor <이름>")
    return lay, paths.layers(lay, src)


def promote(surface, actor):
    """**승격** — 학습 기록을 골격 `ALIASES`로 옮긴다(사람 보증) · 기록은 지운다 · 다음 줄 `bootstrap`."""
    if not actor:
        raise LearnRefused("행위자 미지정 — 승격은 로그에 행위자를 남긴다")
    b = book()
    rec = b["채택"].get(surface)
    if not rec:
        raise LearnRefused(f"학습 기록에 '{surface}'가 없다 — python run.py show learned")
    lay, p = _skeleton_file()
    seed = json.loads(p.read_text(encoding="utf-8"))
    al = seed.setdefault("ALIASES", {}).setdefault(rec["canonical"], [])
    if surface not in al:
        al.append(surface)
    store.atomic_write_bytes(p, (json.dumps(seed, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    b["채택"].pop(surface)
    store.write(store.COORD_LEARNED, b)
    from core.state.ops import log_op
    log_op("learn:promote", actor, [rec.get("id") or rec["canonical"]], "",
           {"surface": surface, "canonical": rec["canonical"], "skeleton": paths.show(p)})
    return {"surface": surface, "canonical": rec["canonical"], "layer": lay, "file": p}


def reject(surface, actor):
    """**거부** — 학습 기록을 지운다(다음엔 다시 묻는다) · 로그에 남긴다."""
    if not actor:
        raise LearnRefused("행위자 미지정 — 거부는 로그에 행위자를 남긴다")
    b = book()
    rec = b["채택"].pop(surface, None)
    if rec is None:
        raise LearnRefused(f"학습 기록에 '{surface}'가 없다 — python run.py show learned")
    store.write(store.COORD_LEARNED, b)
    from core.state.ops import log_op
    log_op("learn:reject", actor, [rec.get("id") or rec["canonical"]], "",
           {"surface": surface, "canonical": rec["canonical"]})
    return {"surface": surface, "canonical": rec["canonical"]}


def sources_for(node):
    """`show node`의 좌표 학습 표기 — 이 골격 노드를 가리키는 학습 기록 `[(표기, 기록)]`."""
    return [(s, r) for s, r in book()["채택"].items()
            if r.get("canonical") == node.get("canonical")]
