# -*- coding: utf-8 -*-
"""칸 0.3 — **좌표 어긋남 큐 화면 · 쌍 확인** — `coord_mismatch`를 쌍 단위로 보이고 쌍 단위로 확인한다 (B105 ④).

    python run.py platform queue coord_mismatch                         쌍 묶음(행 수 · 문서 · 예시 위치 · 확인 여부)
    python run.py ops coord-ack   all "<상위>" "<하위>" --actor <이름> [--reason "<메모>"]
    python run.py ops coord-ack   all "<극성>" "<노드>" --polarity --actor <이름>
    python run.py ops coord-unack all "<상위>" "<하위>" --actor <이름>          (확인 취소 — 다시 보인다)

큐 항목은 지금처럼 **행마다 하나**다(저장 모양 불변) — 묶는 것은 화면이고, 열쇠는 payload의 쌍
(`parser.coord_pairs.pair_of` — 확인 기록과 같은 열쇠). 확인은 ②등록 `registry/coord_acks.json`에 남고
(`core/state/coord_acks`) 그 쌍은 화면 수에서 빠진다(목록에는 「확인됨」으로 남는다). 「골격 수정」은 명령이
아니라 다음 줄 안내다(seed · `bootstrap` · 재인입 — 골격의 부모·이름 변경은 재구축).
"""
from __future__ import annotations

from core import paths
from core.state import coord_acks as CA, store
from parser import coord_pairs as CP


def _cmd(op, kind, pair, extra=""):
    pol = " --polarity" if kind == CP.POLARITY else ""
    return f'python run.py ops {op} all "{pair[0]}" "{pair[1]}"{pol} --actor <이름>{extra}'


def groups():
    """`[((종류, 쌍), {rows, docs, locs, open, done, rec})]` — 열린 행이 많은 쌍부터 · 확인된 쌍은 뒤."""
    acks = CA.acked()
    out = {}
    for x in store.read(store.QUEUE, []):
        if x.get("kind") != CA.KIND:
            continue
        k = CP.pair_of(x.get("payload"))
        e = out.setdefault(k, {"rows": 0, "docs": [], "locs": [], "open": 0, "done": 0, "other": 0,
                               "rec": acks.get(CA.key(*k))})
        e["rows"] += 1
        if x.get("doc_id") and x["doc_id"] not in e["docs"]:
            e["docs"].append(x["doc_id"])
        loc = str((x.get("payload") or {}).get("provenance") or "").split("#", 1)[-1]
        if loc and len(e["locs"]) < CP.LOCS:
            e["locs"].append(loc)
        dec = (x.get("resolution") or {}).get("decision")
        if dec is None:
            e["open"] += 1
        elif dec == CA.DECISION:
            e["done"] += 1
        else:
            e["other"] += 1
    return sorted(out.items(), key=lambda kv: (kv[1]["open"] == 0, -kv[1]["open"], -kv[1]["rows"],
                                               kv[0][0], str(kv[0][1])))


def show():
    """`platform queue coord_mismatch`의 본문 — 쌍 묶음 · 확인 여부 · 다음 줄."""
    gs = groups()
    live = [(k, e) for k, e in gs if e["open"]]
    done = [(k, e) for k, e in gs if not e["open"] and e["rec"]]
    print(f"\n[{CA.KIND}] 쌍 묶음 — 어긋남 {len(live):,}쌍({sum(e['open'] for _k, e in live):,}행) · "
          f"확인된 쌍 {len(done):,}({sum(e['done'] for _k, e in done):,}행) · 큐 항목 {sum(e['rows'] for _k, e in gs):,}")
    for (kind, pair), e in gs:
        what = (f"상위 '{pair[0]}' ↛ 하위 '{pair[1]}'" if kind == CP.GROUP
                else f"극성 '{pair[0]}' ↛ 노드 '{pair[1]}'(극성 다름)")
        if e["rec"]:
            r = e["rec"]
            state = f"확인됨({r['actor']} · {r['at']}" + (f" · {r['note']}" if r.get("note") else "") + ")"
        else:
            state = "확인 안 함" if e["open"] else "종결"
        print(f"  · [{kind}] {what} · {e['rows']:,}행 · 문서 {', '.join(e['docs'][:5])}"
              f"{' 외' if len(e['docs']) > 5 else ''} · 예 {', '.join(e['locs'])} · {state}"
              + (f" · 열린 행 {e['open']:,}" if e["open"] and e["rec"] else ""))
        if e["open"]:
            print("     ▶ 이대로 둔다(확인함): " + _cmd("coord-ack", kind, pair, ' [--reason "<메모>"]'))
        elif e["rec"]:
            print(f"     ▶ 확인 취소: {_cmd('coord-unack', kind, pair)}")
    if live:
        print("  ▶ 다음 줄 — 고치는 길: 상위·하위 열이 뒤바뀌었으면 재등록(python -m cli.register review <dt> "
              "--instruct \"상위·하위 열 매핑을 바로잡는다\") · 골격 트리가 틀렸으면 seed를 고치고 python run.py bootstrap "
              "(부모·이름 변경은 재구축 — 가이드 §7) · 표기가 다른 이름이면 ALIASES + python run.py bootstrap → 재인입")


def run_ops(a):
    """`ops coord-ack|coord-unack` — `(상위, 하위)` 또는 `--polarity`면 `(극성, 노드)` · `--actor` 필수 · 비대화형 그대로."""
    if len(a.args) != 2:
        print(f'■ 거부 — 쌍 둘을 달라: python run.py ops {a.op} all "<상위>" "<하위>" --actor <이름> '
              f'(극성이면 "<극성>" "<노드>" --polarity)')
        return 2
    kind = CP.POLARITY if getattr(a, "polarity", False) else CP.GROUP
    pair = (a.args[0], a.args[1])
    try:
        if a.op == "coord-ack":
            rec, n = CA.ack(kind, pair, a.actor, a.reason)
            print(f"[확인] {kind} '{pair[0]}' · '{pair[1]}' — 큐 {n:,}행을 「{CA.DECISION}」으로 닫았다 · "
                  f"문서 {', '.join(rec['docs'])} · 기록 {paths.show(CA.path())}(재인입 · 다른 문서의 같은 쌍도 확인됨)")
            print(f"  ▶ 되돌리려면: {_cmd('coord-unack', kind, pair)}")
        else:
            rec, n = CA.unack(kind, pair, a.actor)
            print(f"[확인 취소] {kind} '{pair[0]}' · '{pair[1]}' — 기록을 지우고 큐 {n:,}행을 다시 열었다")
    except CA.AckRefused as e:
        print(f"■ 거부 — {e}")
        return 2
    return 0
