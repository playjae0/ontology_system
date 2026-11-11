# -*- coding: utf-8 -*-
"""칸 0.3 — **좌표 쌍 확인 기록** — 사람이 「이 어긋남은 봤고 이대로 둔다」고 한 쌍 (B105 ④).

자리는 ②등록 `registry/coord_acks.json`이다 — 사람 판단이라 재생성되지 않고 `init --fresh`에도 산다(원자 쓰기).
모양: `{"pairs": {열쇠: {kind, a, b, actor, at, note, docs}}}` · 열쇠는 `종류|가|나`(상위·하위 또는 극성·노드 —
`parser.coord_pairs.pair_of`가 큐 payload에서 읽는 그 쌍).

  · **확인**(`ack`) — 기록을 남기고 그 쌍의 지금 큐 항목 전부에 `resolution`(지금 장치 — `store.resolve_item`)
  · **다시 실릴 때**(`enqueue` — 구축 말미 · 재인입 · 다른 문서) — 같은 쌍이면 확인됨(`resolution`)으로 싣는다 →
    화면 수에서 빠지고 목록에는 남는다
  · **취소**(`unack`) — 기록을 지우고 **이 손잡이가 단** `resolution`만 걷는다(다른 사람 판단은 그대로) → 다시 보인다

자동으로 고치지 않는다 — 골격도 문서도 바꾸지 않는다(판단은 사람).

**쌍 어긋남의 문**(B196 ② · 결정 A′) — 확인 전에는 그 행을 붙이지 않고 보류한다(구축 앞 패스 `provisional.settle`이 읽는다).
처분은 넷이다: 확인(`ack` — ref 자리에) · 정정(`fix` — 「그 상위 아래의 이 ref 표기 = 그 노드」 · `fixes`) · drop(`drop` — 사유 ·
`drops`) · 건너뜀(기록 없음 — 보류). 같은 파일 · 같은 열쇠(상위 쌍)다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from core import paths
from core.state import store

KIND = "coord_mismatch"
DECISION = "좌표 쌍 확인"


class AckRefused(Exception):
    """확인·취소를 하지 않은 사유 — 화면이 그 문면을 그대로 낸다."""


def path():
    return paths.registry("coord_acks.json")


def load():
    p = path()
    if not p.exists():
        return {"pairs": {}}
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("pairs", {})
    return d


def answers():
    """쌍의 사람 답(B196 ② — 쓰기 0) — `{열쇠: ("ack"|"fix"|"drop", 기록)}` · 확인이 정정 · drop보다 앞이 아니다(나중 기록이 이긴다).
    옛 극성 이름을 가리키는 쌍(B198 ④ — `<공정>::<축값>`)은 개념 이름의 열쇠로 읽는다(기록은 그대로)."""
    from core.build import polarity
    d = load()
    out = {}
    for name in ("pairs", "fixes", "drops"):
        for k, rec in (d.get(name) or {}).items():
            tag = {"pairs": "ack", "fixes": "fix", "drops": "drop"}[name]
            if rec.get("a") is not None and rec.get("kind"):
                k = key(rec["kind"], (polarity.concept_name(rec["a"]), polarity.concept_name(rec.get("b"))))
            if k not in out or str(rec.get("at") or "") >= str(out[k][1].get("at") or ""):
                out[k] = (tag, rec)
    return out


def _decide(name, kind, pair, actor, note, **extra):
    from core.state.ops import log_op
    if not actor:
        raise AckRefused("행위자가 없다 — --actor <이름>")
    k = key(kind, pair)
    d = load()
    for other in ("pairs", "fixes", "drops"):
        (d.get(other) or {}).pop(k, None)
    rec = {"kind": kind, "a": pair[0], "b": pair[1], "actor": actor, "at": _now(), "note": note or "", **extra}
    d.setdefault(name, {})[k] = rec
    _save(d)
    log_op("coord:" + {"fixes": "fix", "drops": "drop"}[name], actor, [], note or "", dict(rec), None)
    _reopen(k)
    return rec


def fix(kind, pair, target, actor, note=""):
    """**정정**(B196 ②) — 상위가 맞다: 그 상위 아래에서 이 ref 표기는 `target`(골격 노드 canonical) · 재연결 · 다음 인입이 그 노드에."""
    if not target:
        raise AckRefused("정정할 노드가 없다 — r <줄> <후보 번호|이름>")
    return _decide("fixes", kind, pair, actor, note, target=target)


def drop(kind, pair, actor, note=""):
    """**drop**(B196 ② — 사유 필수) — 그 쌍의 행은 붙이지 않는다(재연결이 다시 열지 않는다)."""
    if not (note or "").strip():
        raise AckRefused("drop은 사유가 있어야 한다 — d <줄> <사유>")
    return _decide("drops", kind, pair, actor, note)


def _reopen(k):
    """처분 뒤 그 쌍의 보류 행은 다시 시도할 거리다 — 지난 시도의 지문을 걷는다."""
    q, hit = store.read(store.QUEUE, []), False
    for x in q:
        pr = (x.get("payload") or {}).get("pair")
        if x.get("kind") == "orphan_anchor" and pr and key(pr["kind"], (pr["up"], pr["ref"])) == k:
            x.pop("last_fp", None)
            hit = True
    if hit:
        store.write(store.QUEUE, q)


def _save(d):
    store.atomic_write_bytes(path(), (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def key(kind, pair):
    from parser import coord_pairs as CP
    return f"{CP.ack_kind(kind)}|{pair[0]}|{pair[1]}"           # 문서 좌표 상위도 상위 쌍이다 (B106 ⑤)


def key_of(pl):
    from parser import coord_pairs as CP
    return key(*CP.pair_of(pl))


def acked():
    """`{열쇠: 기록}` — 지금 확인된 쌍."""
    return load()["pairs"]


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ack(kind, pair, actor, note="", seen=False):
    """쌍 하나를 확인한다 — `(기록, 종결한 큐 항목 수)`. 지금 큐에 그 쌍이 없으면 거부(지어낸 쌍을 남기지 않는다) — `seen`(좌표 단계가
    이 문서에서 본 쌍 · B196 ②)이면 큐 앞이라도 받는다."""
    if not actor:
        raise AckRefused("행위자가 없다 — --actor <이름>")
    k = key(kind, pair)
    items = [x for x in store.read(store.QUEUE, []) if x.get("kind") == KIND and key_of(x.get("payload")) == k]
    if not items and not seen:
        raise AckRefused(f"큐에 그 쌍이 없다 — {kind} '{pair[0]}' · '{pair[1]}' "
                         f"(python run.py platform queue {KIND} 의 쌍을 그대로 준다)")
    d = load()
    rec = {"kind": kind, "a": pair[0], "b": pair[1], "actor": actor, "at": _now(), "note": note or "",
           "docs": sorted({x.get("doc_id") for x in items if x.get("doc_id")})}
    for other in ("fixes", "drops"):
        (d.get(other) or {}).pop(k, None)
    d["pairs"][k] = rec
    _save(d)
    _reopen(k)
    n = store.resolve_item(KIND, lambda pl: key_of(pl) == k, actor=actor, decision=DECISION,
                           at=rec["at"], note=rec["note"])
    return rec, n


def unack(kind, pair, actor):
    """확인을 되돌린다 — `(지운 기록, 다시 열린 큐 항목 수)`. 기록이 없으면 거부."""
    if not actor:
        raise AckRefused("행위자가 없다 — --actor <이름>")
    k = key(kind, pair)
    d = load()
    rec = d["pairs"].pop(k, None)
    if rec is None:
        raise AckRefused(f"확인 기록에 그 쌍이 없다 — {kind} '{pair[0]}' · '{pair[1]}'")
    _save(d)
    n = store.clear_resolution(KIND, lambda pl: key_of(pl) == k, decision=DECISION)
    return rec, n


def enqueue(reason, doc_id, payload):
    """`coord_mismatch` 한 항목 — 확인된 쌍이면 확인됨으로(같은 항목은 `store.enqueue`가 다시 싣지 않는다)."""
    item = store.enqueue(KIND, reason, doc_id, payload)
    rec = acked().get(key_of(payload))
    if rec and not item.get("resolution"):
        store.resolve_item(KIND, lambda pl: pl == payload, actor=rec["actor"], decision=DECISION,
                           at=rec["at"], note=rec.get("note") or "")
    return item
