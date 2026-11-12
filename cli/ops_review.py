# -*- coding: utf-8 -*-
"""칸 0.3 — **인입 뒤 한 화면 — 판단이 필요했던 것을 몰아서**(B101 ⑤ · B184 ④) — 묶음 다섯을 표로 · 한 건씩 처분(다섯째는 표만).

    python run.py ops review <층|all> --actor <이름>

| 묶음 | 처분(손) |
|---|---|
| 골격 칸 — 문에 걸린 표기 · 쌍 어긋남(B196 ③ — 문서를 넘어 한 줄) | 처분 넷 · 맞다 · 해석 고침(`cli/gate_table.loop` — 좌표 단계 · 골격 단과 같은 고리 · B202) |
| 잠정 골격 노드(좌표 층 · 「봄」은 접어 둔다) | 승격 · 합침 · 그대로(`cli/provisional_ask.decide` — 인입 `--step`과 같은 함수) |
| 애매(`uncertain_match` — 잠정 노드 것은 첫 묶음) | 합침 · 별개 · 건너뜀(`ops.merge` · `ops.confirm`) |
| 자리 추정(유일 후보 · 「맞음」은 접어 둔다) | 맞음(확인 표지) · 떼기(보류로 — `place_guess.detach`) |
| 보류(후보가 있는 것) | 후보 고르기 — 자리 없는 값은 `place_guess.pick`(출처 사람) · 골격 칸은 합침 손 |
| 같은 노드 엣지 — 표기가 다른 것(B186 ②) | 묻지 않는다 — 다음 줄(`ops split` · `ops alias-reject` — 지금 손) |

새 쓰기 손은 승격 하나다(나머지는 지금 있는 손). **비대화형(터미널 아님)은 계획만** 낸다(쓰기 0). 끝 줄은 묶음마다 처분 수 ·
재구축이 필요한 처분이 있으면 그 명령 한 줄.
"""
from __future__ import annotations

import sys

from core.state import store


# ---------------------------------------------------------------- 재료 (쓰기 0)
def items(layer=None):
    """애매 — 사람 판단이 없는 `uncertain_match`(잠정 골격 노드 것은 첫 묶음) · `layer`면 그 층(home) 것만."""
    from core.state.status import PROVISIONAL
    out = []
    for x in store.read(store.QUEUE, []):
        if x.get("kind") != "uncertain_match" or x.get("resolution"):
            continue
        pl = x.get("payload") or {}
        if pl.get(PROVISIONAL) or layer not in (None, "all") and pl.get("layer") != layer:
            continue
        near = pl.get("nearest") or {}
        score = next((t.get("score") for t in near.get("top") or [] if t.get("id") == near.get("id")), None)
        out.append({"doc_id": x.get("doc_id"), "surface": pl.get("surface"), "node_id": pl.get("node_id"),
                    "canonical": pl.get("canonical"), "layer": pl.get("layer"),
                    "near_id": near.get("id"), "near": near.get("canonical"), "score": score,
                    # 가드는 걷혔다(B172) — B172 전에 쌓인 큐 항목(③ · 누적)은 그 표지를 그대로 진다 · 읽는 자리는 이 칸 하나
                    "guard": near.get("by") == "가드"})
    return out


def provisionals(layer=None):
    """잠정 골격 노드 — `(보일 줄, 접은 수)` · 좌표 층만 · 「봄」 표지는 접는다."""
    from core.build import provisional
    from core.state import provisional_hand as PH
    from core.state.bootstrap import coord_layer
    lay = coord_layer()
    if layer not in (None, "all", lay):
        return [], 0
    from core.state.bootstrap import open_graph
    kept, g = PH.kept(), open_graph(lay)
    rows = [{"nid": e["id"], "surface": e["canonical"], "canonical": e["canonical"], "parent": e.get("parent"),
             "tier": e.get("tier"), "near": e.get("near") or [], "doc": e.get("doc"),
             "rows": sum(1 for p in (g.get(e["id"]) or {}).get("provenance") or [] if "#" in str(p))}
            for e in provisional.listing(lay)]
    return [r for r in rows if r["canonical"] not in kept], sum(1 for r in rows if r["canonical"] in kept)


def guesses(layer=None):
    """자리 추정으로 붙은 값 — `(보일 줄, 접은 수)` · 「맞음」은 접는다."""
    from core.build import place_guess
    rows = place_guess.attached(layer)
    return [r for r in rows if not r["ok"]], sum(1 for r in rows if r["ok"])


def holds(layer=None):
    """후보가 있는 보류 — 자리 없는 값(`missing_field` 표지 후보) · 골격 칸(`orphan_anchor` — 같은 이름의 골격 노드가 있다)."""
    from core.build import place_guess
    from parser.namefold import key
    out = [dict(r, kind="값") for r in place_guess.held() if layer in (None, "all", r["layer"])]
    from core.state.bootstrap import COORD_CATEGORY, coord_layer, open_graph
    lay = coord_layer()
    if layer not in (None, "all", lay):
        return out
    from core.state import catalog
    g, sep = open_graph(lay), catalog.sep()
    names = {}
    for n in g.nodes.values():
        if n.get("category") == COORD_CATEGORY and n.get("status") == "seed":
            for s in {n["canonical"].rsplit(sep, 1)[-1]} | {a["surface"] for a in n.get("aliases") or []}:
                names.setdefault(key(s), set()).add(n["canonical"])
    seen = set()
    for x in store.read(store.QUEUE, []):
        pl = x.get("payload") or {}
        if x.get("kind") != "orphan_anchor" or x.get("resolution") or pl.get("category") != COORD_CATEGORY \
                or pl.get("gate") is not None or pl.get("pair") is not None:      # 문 · 쌍은 골격 칸 묶음(B196 ③)
            continue
        c = sorted(names.get(key(pl.get("surface") or ""), ()))
        if c and pl.get("surface") not in seen:
            seen.add(pl["surface"])
            out.append({"kind": "골격 칸", "doc": x.get("doc_id"), "surface": pl["surface"], "candidates": c,
                        "why": x.get("reason", "")[:40], "layer": lay})
    return out


def same_nodes(layer=None):
    """**같은 노드 엣지 — 표기가 다른 것**(B186 ②) — 관문 거부 기록에서 두 표기가 다른데 한 노드로 풀린 엣지(같은지 판단 확인 거리) ·
    표기가 같은 것(문서의 두 칸에 같은 글)은 고칠 것이 없어 올리지 않는다."""
    from core.build import gate
    from parser.namefold import key
    out, seen = [], set()
    for x in store.read(store.GATE_REJECTS, {"rejects": []}).get("rejects") or []:
        sf = x.get("surfaces") or []
        if x.get("verdict") != gate.SAME_NODE or len({key(t or "") for t in sf}) < 2:
            continue
        lay = x.get("node_layer") or x.get("layer")
        k = (x.get("node"), tuple(sf), x.get("doc_id"), x.get("rel"))
        if layer in (None, "all", lay) and k not in seen:
            seen.add(k)
            out.append({"node": x.get("node"), "layer": lay, "surfaces": sf, "doc": x.get("doc_id"), "rel": x.get("rel")})
    return out


# ---------------------------------------------------------------- 표
def _cut(s, n):
    s = str(s if s is not None else "—")
    return s[:n] + " " * max(0, n - len(s))


#: 골격 칸 묶음의 표 머리
GATE_TITLE = "골격 칸 — 문에 걸린 표기(표기 + 들어온 자리) · 쌍 어긋남 — 문서를 넘어 한 줄 · 행 수는 합"


def tables(b, live=False):
    """묶음의 표 — 머리 · 줄(번호는 묶음 안에서) · 골격 칸은 사람이 있으면 물음 고리가 그린다(`live` — 표는 거기서 · B202 ④)."""
    from cli import gate_table
    rows, folded = b["잠정"]
    gate = b["골격 칸"]
    print(f"■ 인입 뒤 한 화면 — 골격 칸 {len(gate):,}(문에 걸림 {sum(1 for r in gate if r['kind'] == 'gate'):,} · 쌍 어긋남 "
          f"{sum(1 for r in gate if r['kind'] == 'pair'):,}) · 잠정 골격 노드 {len(rows):,}" + (f"(봄 {folded:,} 접음)" if folded else "")
          + f" · 애매 {len(b['애매']):,} · 자리 추정 {len(b['추정'][0]):,}"
          + (f"(맞음 {b['추정'][1]:,} 접음)" if b["추정"][1] else "") + f" · 후보 있는 보류 {len(b['보류']):,}"
          + (f" · 같은 노드 엣지(표기가 다른 것) {len(b['같은 노드']):,}" if b["같은 노드"] else ""))
    if gate and not live:
        gate_table.show(gate, GATE_TITLE)
    if rows:
        print(f"  ── 잠정 골격 노드 — {'#':>3} {'표기':<18} {'부모':<14} {'단':<6} {'행 수':>4} {'합칠 후보':<16} 처음 본 문서")
        for i, r in enumerate(rows, 1):
            print(f"     {i:>3} {_cut(r['canonical'], 18)} {_cut(r['parent'] or '부모 미정', 14)} {_cut(r['tier'] or '미정', 6)} "
                  f"{r['rows']:>4} {_cut(' · '.join(r['near']) or '—', 16)} {r['doc'] or '—'}")
    if b["애매"]:
        print(f"  ── 애매 — {'#':>3} {'표기':<18} {'새 노드':<22} {'가장 가까운 후보':<22} {'점수':>6}  {'문서':<12} 가드")
        for i, r in enumerate(b["애매"], 1):
            sc = "" if r["score"] is None else f"{r['score']:.2f}"
            print(f"     {i:>3} {_cut(r['surface'], 18)} {_cut(r['canonical'], 22)} {_cut(r['near'] or '(없음)', 22)} {sc:>6}  "
                  f"{_cut(r['doc_id'], 12)} {'예' if r['guard'] else ''}")
    if b["추정"][0]:
        print(f"  ── 자리 추정(유일 후보) — {'#':>3} {'값':<18} {'붙은 노드':<24} {'문서':<12} 부딪힌 값")
        for i, r in enumerate(b["추정"][0], 1):
            print(f"     {i:>3} {_cut(r['surface'], 18)} {_cut(r['canonical'], 24)} {_cut(r['doc'], 12)} "
                  f"{' · '.join(r['conflict']) or '—'}")
    if b["보류"]:
        print(f"  ── 보류(후보 있음) — {'#':>3} {'칸':<6} {'표기':<18} {'후보':<30} 문서")
        for i, r in enumerate(b["보류"], 1):
            print(f"     {i:>3} {_cut(r['kind'], 6)} {_cut(r['surface'], 18)} "
                  f"{_cut(' · '.join(f'{j}.{c}' for j, c in enumerate(r['candidates'], 1)), 30)} {r['doc']}")
    if b["같은 노드"]:
        print(f"  ── 같은 노드 엣지(표기가 다른 것 — 같은지 판단 확인) — {'#':>3} {'노드':<20} {'두 표기':<26} {'관계':<12} 문서")
        for i, r in enumerate(b["같은 노드"], 1):
            print(f"     {i:>3} {_cut(r['node'], 20)} {_cut(' ↔ '.join(r['surfaces']), 26)} {_cut(r['rel'], 12)} {r['doc']}")
            print(f"         ▶ 다른 것이면 python run.py ops split {r['layer']} <id> <배분표.json> --actor <이름> · "
                  f"표기 하나가 틀렸으면 python run.py ops alias-reject {r['layer']} \"{r['node']}\" \"<표기>\" --actor <이름>")


# ---------------------------------------------------------------- 처분
def decide(r, ans, actor):
    """애매 한 건 — `m`(합침 · 가까운 후보로) · `c`(별개 · 확정) · 그 밖(건너뜀). 돌려주는 것은 한 일."""
    from core.state import ops
    if ans == "m" and r["near_id"]:
        ops.merge(r["layer"], r["node_id"], r["near_id"], actor, reason="ops review — 합침")
        store.resolve_item("uncertain_match", lambda p, _n=r["node_id"]: p.get("node_id") == _n,
                           actor=actor, decision="merged", at=store._now(), note="ops review")
        # **사람이 닫은 큐도 이름으로 남긴다**(B106 ③) — 재구축 뒤 `ops replay`가 같은 결정으로 닫는다
        from core.state import oplog
        oplog.append("queue:resolve", actor, [r["node_id"]], "ops review — 합침",
                     {"kind": "uncertain_match", "decision": "merged"},
                     {"node": {"layer": r["layer"], "canonical": r["canonical"], "category": None}})
        return "합침"
    if ans == "c":
        ops.confirm(r["layer"], r["node_id"], actor, reason="ops review — 별개")
        return "별개"
    return "건너뜀"


def _guess(r, ans, actor):
    from core.build import place_guess
    if ans == "o":
        place_guess.confirm(r["layer"], r["node_id"], r["prov"], r["surface"], actor, "ops review — 맞음")
        return "맞음"
    if ans == "d":
        place_guess.detach(r["layer"], r["node_id"], r["prov"], r["surface"], actor, "ops review — 떼기")
        return "떼기"
    return "건너뜀"


def _hold(r, ans, actor):
    """보류 한 건 — 번호(후보 고르기) · 그 밖(그대로)."""
    if not ans.isdigit() or not 1 <= int(ans) <= len(r["candidates"]):
        return "그대로", False
    c = r["candidates"][int(ans) - 1]
    if r["kind"] == "값":
        from core.build import place_guess
        return ("고름" if place_guess.pick(r, c, actor, "ops review — 후보 고르기") else "그대로"), False
    from core.state import provisional_hand as PH
    PH.merge(actor, target=c, surface=r["surface"], reason="ops review — 골격 칸 후보")
    print(f"     골격 칸 '{r['surface']}' → {c} 골격 ALIASES — 재연결(다음 인입 마무리 · python run.py ops relink all --actor {actor} --apply)이 그 행을 잇는다")
    return "고름", False


def skeleton_cells(layer=None):
    """골격 칸 묶음(B196 ③) — 좌표 층만 · 문에 걸린 표기 + 쌍 어긋남(`skeleton_review` — 좌표 단계와 같은 줄)."""
    from cli import provisional_ask
    from core.build import skeleton_review as SR
    from core.state.bootstrap import coord_layer
    if layer not in (None, "all", coord_layer()):
        return []
    return provisional_ask.rows_of({"held": SR.held_from_queue(), "pairs": SR.pairs_from_queue()})


def _did(r):
    """표 고리의 처분 칸 → 끝 줄의 셈 이름."""
    cell = str(r.get("done") or "")
    if cell.startswith("✎"):
        return "해석 고침"
    word = cell[2:].split(" ", 1)[0].split("(", 1)[0] if cell.startswith("✓") else ""
    return {"버림": "drop", "위로": "올림", "맞다": "확인"}.get(word, word) if word else "건너뜀"


def bundles(layer):
    return {"골격 칸": skeleton_cells(layer), "잠정": provisionals(layer), "애매": items(layer), "추정": guesses(layer), "보류": holds(layer),
            "같은 노드": same_nodes(layer)}


def run(a, ask=None):
    """`ops review` — 묶음 넷의 표 · 한 건씩 묻기(`ask(문면) -> 답`) · 비대화형은 계획만."""
    from cli import _screen, provisional_ask
    b = bundles(a.layer)
    live = ask is not None or sys.stdin.isatty()
    tables(b, live)
    n = len(b["골격 칸"]) + len(b["잠정"][0]) + len(b["애매"]) + len(b["추정"][0]) + len(b["보류"])
    if not n:
        return 0
    if not live:
        print("  (비대화형 — 계획만 · 쓰기 0) ▶ 다음 줄 — 터미널에서: "
              f"python run.py ops review {a.layer} --actor {a.actor}")
        return 0
    ask = ask or (lambda q: _screen.answer(q, "text", eof=""))
    done = {"골격 칸": {k: 0 for k in provisional_ask.DONE}, "잠정": {k: 0 for k in provisional_ask.DONE},
            "애매": {"합침": 0, "별개": 0, "건너뜀": 0},
            "추정": {"맞음": 0, "떼기": 0, "건너뜀": 0}, "보류": {"고름": 0, "그대로": 0}}
    rebuild = False
    if b["골격 칸"]:                                 # 한 고리(B202 — 표 · 말 또는 글쇠 · 처분 뒤 다시 그림 · q면 검토 끝)
        from cli import gate_table
        go = gate_table.loop(b["골격 칸"], a.actor, title=GATE_TITLE, ask=ask)
        for r in b["골격 칸"]:
            done["골격 칸"][_did(r)] += 1
        if go is False:
            b["잠정"], b["애매"], b["추정"], b["보류"] = ([], 0), [], ([], 0), []
    for r in b["잠정"][0]:
        did, rb = provisional_ask.decide(r, a.actor, ask, indent="  ")
        done["잠정"][did] += 1
        rebuild |= rb
    for i, r in enumerate(b["애매"], 1):
        q = f"  [애매 {i}/{len(b['애매'])}] '{r['surface']}' — 합침(m: → {r['near'] or '후보 없음'}) / 별개(c) / 건너뜀(s) > "
        try:
            did = decide(r, (ask(q) or "").strip().lower()[:1], a.actor)
        except Exception as e:                      # noqa: BLE001 — 거부는 그 건만 건너뛴다
            print(f"     [거부] {e}")
            did = "건너뜀"
        done["애매"][did] += 1
    for i, r in enumerate(b["추정"][0], 1):
        q = f"  [자리 추정 {i}/{len(b['추정'][0])}] '{r['surface']}' → {r['canonical']} — 맞음(o) / 떼기(d · 보류로) / 건너뜀 > "
        done["추정"][_guess(r, (ask(q) or "").strip().lower()[:1], a.actor)] += 1
    for i, r in enumerate(b["보류"], 1):
        q = f"  [보류 {i}/{len(b['보류'])}] '{r['surface']}' — 후보 번호(1~{len(r['candidates'])}) / 그대로 Enter > "
        did, rb = _hold(r, (ask(q) or "").strip(), a.actor)
        done["보류"][did] += 1
        rebuild |= rb
    print("■ 검토 끝 — " + " | ".join(f"{k} " + " · ".join(f"{x} {v:,}" for x, v in d.items() if v or x == "건너뜀")
                                     for k, d in done.items()))
    if sum(v for x, v in done["골격 칸"].items() if x != "건너뜀") or done["보류"]["고름"]:
        print(f"  ▶ 다음 줄 — 처분한 보류 행을 잇는다(추출 LLM 0): python run.py ops relink all --actor {a.actor} --apply")
    if rebuild:
        print("  ▶ 재구축이 필요하다(합친 표기의 아래 노드 이름이 바뀐다) — python run.py rebuild")
    return 0
