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


#: 쌍 상위의 출처 둘 — 행(표의 상위 열 · 극성 · 상위 이름 골격 밖) · 문서 좌표(행에 상위가 없어 문서 좌표로 잰 쌍 — B106 ⑤)
ROW, DOC = "행", "문서 좌표"


def next_lines(kinds, doc=None, dt=None):
    """좌표 쌍 **다음 줄 한 자리**(B154 ① — 판정 전 쌍 화면 · 큐 화면이 같이 부른다) — 쌍의 상위가 어디서 왔나(`ROW` · `DOC`)로
    고른다(문서 형태 · doc_type으로 가르지 않는다) · 섞이면 종류마다 한 줄 · `doc` · `dt`가 있으면 그대로 쳐서 도는 꼴로 채운다."""
    ack = "이대로 두려면 쌍 확인(python run.py platform queue coord_mismatch)"
    out = []
    if ROW in kinds:
        out.append(f"▶ 다음 줄(행의 상위) — 열이 뒤바뀌었으면 재등록(python -m cli.register generate {dt or '<dt>'} <층> <표본> "
                   "--revise --hint \"상위(process_group)·하위(process_ref) 열 매핑을 바로잡는다\" — 가이드 §4 재등록 순서) · "
                   "골격이 틀렸으면 seed(부모·이름 변경은 재구축 — 가이드 §7) · 별칭이면 ALIASES + python run.py bootstrap · " + ack)
    if DOC in kinds:
        out.append(f"▶ 다음 줄(문서 좌표 상위) — 여러 공정을 다루는 문서면 문서 좌표를 상위 공정으로 다시(python run.py ingest-file "
                   f"{doc or '<문서>'} --doc-type {dt or '<dt>'} --coord <상위 공정>) · 표기가 다른 이름이면 골격 ALIASES + "
                   "python run.py bootstrap · " + ack)
    return out


def groups():
    """`[((종류, 쌍), {rows, docs, locs, open, done, rec})]` — 열린 행이 많은 쌍부터 · 확인된 쌍은 뒤."""
    acks = CA.acked()
    out = {}
    for x in store.read(store.QUEUE, []):
        if x.get("kind") != CA.KIND:
            continue
        k = CP.pair_of(x.get("payload"))
        e = out.setdefault(k, {"rows": 0, "docs": [], "locs": [], "open": 0, "done": 0, "other": 0,
                               "doc_upper": 0, "rec": acks.get(CA.key(*k))})
        e["rows"] += 1
        e["doc_upper"] += 1 if (x.get("payload") or {}).get("upper") == CP.DOC_GROUP else 0
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
        # 문서 좌표를 상위로 삼은 행(B106 ⑤)은 그 말로 — 섞였으면 둘 다
        what = (CP.describe(CP.DOC_GROUP, pair) if kind == CP.GROUP and e["doc_upper"] == e["rows"]
                else (f"상위·문서 좌표 '{pair[0]}' ↛ 하위 '{pair[1]}'" if kind == CP.GROUP and e["doc_upper"]
                      else CP.describe(kind, pair)))
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
    kinds = {k for (kind, _p), e in live for k in ((DOC,) if kind == CP.GROUP and e["doc_upper"] == e["rows"]
                                                   else (ROW, DOC) if kind == CP.GROUP and e["doc_upper"] else (ROW,))}
    docs = sorted({d for (kind, _p), e in live if kind == CP.GROUP and e["doc_upper"] for d in e["docs"]})
    reg = store.read(store.DOC_REGISTRY, {}).get(docs[0]) or {} if len(docs) == 1 else {}
    for ln in next_lines(kinds, paths.from_home(reg["source_path"]) if reg.get("source_path") else None, reg.get("doc_type")):
        print(f"  {ln}")


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
