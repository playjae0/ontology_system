# -*- coding: utf-8 -*-
"""칸 0.3 — 산출물 열람 — **시각화 없이 텍스트로 본다** (명세 §11 · 카드 P5).

    python -m cli.show tree   [층]           골격 트리 (사내 공정이 맞게 섰나)
    python -m cli.show node   <이름>          노드 하나 전부 — 값·별칭·출처·연결
    python -m cli.show doc    <doc_id>        그 문서가 만든 것 전부 (역추적)
    python -m cli.show report <doc_id> [--json]  그 문서의 **행별 판정 대장** (눈 검수)
    python -m cli.show report --diff <a.json> <b.json>   두 대장의 **다른 행만** (설정 비교)
    python -m cli.show chunk  <doc_id|id>     청크 원문 (답의 근거로 실린 그 문장)
    python -m cli.show edges  [층] [관계]      엣지 목록
    python -m cli.show schema <doc_type>      매칭 스키마 — 필드→role 배정표
    python -m cli.show meta                   메타데이터 계약 3층을 실물로

**진실은 `data/`의 JSON이다.** Cypher·Mermaid·임베딩은 전부 거기서 파생되는
재생성 가능물이고(P5), 이 파일은 그 JSON을 **사람이 읽는 모양으로** 옮길 뿐이다.
Neo4j에 올려 보려면 `run.py export cypher`.

**읽기 전용이다.** 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from collections import Counter

from cli import _screen
from core import paths
from core.build import ledger
from core.state import registry, store
from core.state import sheets as _sheets
from core.state.bootstrap import load_config, open_graph
from core.state.ids import norm
from core.state.status import is_live
from router import discover


def _graphs():
    return {lay: open_graph(lay) for lay in discover()}


def _find(name):
    """이름으로 노드를 찾는다 — canonical·alias·사전 순으로. 여러 개면 전부 돌려준다."""
    hits = []
    for lay, g in _graphs().items():
        for n in g.nodes.values():
            if not is_live(n):
                continue
            surfaces = {norm(n["canonical"])} | {norm(a["surface"]) for a in n["aliases"]}
            if norm(name) in surfaces:
                hits.append((lay, g, n))
    return hits


def _prov(items, limit=6):
    items = list(items or [])
    tail = f" 외 {len(items) - limit}건" if len(items) > limit else ""
    return ", ".join(items[:limit]) + tail


# ---------------------------------------------------------------- tree
def cmd_tree(args):
    """골격 트리 — **seed 교체가 제대로 됐는지 눈으로 확인하는 자리**다.

    골격만 그린다(문서가 만든 auto 노드는 뺀다) — 여기서 봐야 할 것은 "우리 공정
    체계가 맞게 섰나"이고, 그 판정에 문서 유래 노드는 잡음이다.
    """
    lay = args[0] if args else "process"
    g, cfg = open_graph(lay), load_config(lay)
    child = ((cfg.get("skeleton") or {}).get("relations") or {}).get("child")
    sib = ((cfg.get("skeleton") or {}).get("relations") or {}).get("sibling")
    if not child:
        print(f"[{lay}] 골격 선언이 없는 층이다 (config에 skeleton 없음)")
        return 0

    seed = {i: n for i, n in g.nodes.items() if n.get("status") == "seed"}
    parent = {e["src"]: e["dst"] for e in g.edges
              if e["rel"] == child and e["src"] in seed and e["dst"] in seed}
    kids = {}
    for c, p in parent.items():
        kids.setdefault(p, []).append(c)
    nxt = {e["src"]: e["dst"] for e in g.edges if e["rel"] == sib}

    print(f"■ {lay} 골격 — 노드 {len(seed)} (문서 유래 {len(g.nodes) - len(seed)}는 제외)\n")

    def draw(nid, pre="", mark="", child_pre=""):
        n = seed[nid]
        pol = n.get("polarity")
        tag = f"[{n.get('tier')}" + (f"·{pol}" if pol and pol != "none" else "") + "]"
        alias = [a["surface"] for a in n["aliases"]
                 if norm(a["surface"]) != norm(n["canonical"])]
        name = n["canonical"].split("::")[-1]
        print(f"{pre}{mark}{name}  {tag}"
              + (f"   ({', '.join(alias[:3])})" if alias else "")
              + (f"   → {seed[nxt[nid]]['canonical'].split('::')[-1]}"
                 if nid in nxt and nxt[nid] in seed else ""))
        ch = sorted(kids.get(nid, []), key=lambda i: seed[i]["canonical"])
        for i, c in enumerate(ch):
            last = (i == len(ch) - 1)
            draw(c, child_pre, "└─ " if last else "├─ ",
                 child_pre + ("   " if last else "│  "))

    roots = [i for i in seed if i not in parent]
    for r in sorted(roots, key=lambda i: seed[i]["canonical"]):
        draw(r)
    print(f"\n  → 는 대표 흐름(`{sib}`) · [tier·극성] · (별칭)")
    return 0


# ---------------------------------------------------------------- node
def cmd_node(args):
    """노드 하나 전부 — **값·별칭·출처·연결**. 질의 답의 뒷면이 여기다."""
    if not args:
        raise SystemExit("이름을 달라: run.py show node '노칭 정밀도'")             # [사용법]
    name = " ".join(args)
    hits = _find(name)
    if not hits:
        print(f"'{name}' 없음. 부분 일치 후보:")
        for lay, g in _graphs().items():
            for n in g.nodes.values():
                if is_live(n) and norm(name) in norm(n["canonical"]):
                    print(f"  · [{lay}] {n['canonical']}")
        return 1

    for lay, g, n in hits:
        print(f"\n■ {n['canonical']}   [{lay} · {n['category']} · {n['status']}]")
        print(f"  id        {n['id']}")
        if n.get("polarity") and n["polarity"] != "none":
            print(f"  극성       {n['polarity']}")
        al = [a["surface"] for a in n["aliases"]]
        print(f"  별칭       {', '.join(al) if al else '(없음)'}")
        print(f"  출처       {_prov(n['provenance'])}")

        attrs = n.get("attrs") or {}
        if attrs:
            print("\n  ── 값 ──")
        for k, v in attrs.items():
            items = v if isinstance(v, list) else [v]
            for it in items:
                # **열람은 진실을 판정하지 않는다.** 값 항목의 정본 형태는
                # `{value, provenance}` 또는 `{context, value, provenance}`이고
                # (문서 2 · §7.2), 그 형태가 아닌 것이 실려 있으면 그것은 쓰기
                # 측의 결함이다 — 여기서 죽으면 **그 결함을 볼 창구가 함께
                # 사라진다.** 그래서 있는 대로 보여주고 형태가 다른 것은
                # 다르다고 표시한다.
                if not isinstance(it, dict):
                    print(f"    {k:<12} {it!r}   ← 값 항목 형태 아님 (쓰기 측 결함)")
                    continue
                ctx = it.get("context") or {}
                ctx_s = f"[{', '.join(f'{a}={b}' for a, b in ctx.items())}] " if ctx else ""
                print(f"    {k:<12} {ctx_s}{it.get('value')}"
                      f"   ({_prov(it.get('provenance'), 3)})")

        print("\n  ── 연결 ──")
        gs = _graphs()
        found = False
        for glay, gg in gs.items():
            for e in gg.edges:
                if n["id"] not in (e["src"], e["dst"]):
                    continue
                if e.get("status") == "deleted_by_user":
                    continue
                other_id = e["dst"] if e["src"] == n["id"] else e["src"]
                other, olay = None, None
                for l2, g2 in gs.items():
                    if other_id in g2.nodes:
                        other, olay = g2.nodes[other_id], l2
                        break
                if not other:
                    continue
                arrow = "→" if e["src"] == n["id"] else "←"
                cross = f" [{olay}]" if olay != lay else ""
                print(f"    {arrow} {e['rel']:<14} {other['canonical']}{cross}"
                      f"   ({_prov(e.get('provenance'), 2)})")
                found = True
        if not found:
            print("    (없음)")

        ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
        linked = [d["chunk_id"] for d in ch["describes"] if d["node_id"] == n["id"]]
        if linked:
            print(f"\n  ── 근거 청크 {len(linked)}건 ── (원문은 show chunk <id>)")
            for cid in linked[:5]:
                c = ch["chunks"].get(cid, {})
                print(f"    · {cid}  {(c.get('text') or '')[:60]}")
    return 0


# ---------------------------------------------------------------- doc
def cmd_doc(args):
    """문서 하나가 만든 것 전부 — **역추적**. 인입이 무엇을 했는지 한눈에 본다."""
    if not args:
        docs = store.read(store.DOC_REGISTRY, {})
        print("인입된 문서:")
        for d, m in docs.items():
            print(f"  · {d:<10} {m.get('doc_type'):<12} rev {m.get('revision')} "
                  f"· {m.get('source_path')}")
        return 0
    doc = args[0]
    meta = store.read(store.DOC_REGISTRY, {}).get(doc)
    if not meta:
        print(f"'{doc}' 인입 기록 없음")
        return 1
    print(f"■ {doc}   [{meta.get('doc_type')} · rev {meta.get('revision')}]")
    print(f"  원본       {paths.from_home(meta['source_path'])}"
          if meta.get("source_path") else "  원본       —")
    print(f"  doc_hash   {meta.get('doc_hash', '')[:16]}…")
    print(f"  최초 인입   {meta.get('first_ingested_at')}")

    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    mine = {cid: c for cid, c in ch["chunks"].items() if c.get("doc_id") == doc}
    linked = sum(1 for c in mine.values() if c.get("linked"))
    ref = sum(1 for c in mine.values()
              if (c.get("meta") or {}).get("sheet_role") == "ref")
    print(f"\n  청크 {len(mine)}건 (그래프에 연결 {linked}"
          + (f" · 참조 {ref}" if ref else "") + ")")
    # **시트 역할은 사람이 한 번 정한 것이다**(B83 ④) — 무엇을 읽지 않았는지가
    # 문서 열람에 보여야 한다. 기록이 없으면 줄도 없다(시트 하나짜리 문서).
    _sr = _sheets.read(doc)
    if _sr:
        print(f"  시트 역할   {_sheets.summary(_sr.get('sheets') or {})} "
              f"({_sr.get('decided_by')} · {_sr.get('at')})")
        for _n, _r in (_sr.get("sheets") or {}).items():
            print(f"    · {_screen.pad(_n, 20)}{_r}")

    for lay, g in _graphs().items():
        nodes = [n for n in g.nodes.values() if is_live(n)
                 and any(str(p).startswith(doc) for p in n.get("provenance") or [])]
        edges = [e for e in g.edges
                 if any(str(p).startswith(doc) for p in e.get("provenance") or [])]
        if nodes or edges:
            print(f"\n  [{lay}] 노드 {len(nodes)} · 엣지 {len(edges)}")
            for n in nodes[:12]:
                print(f"    · {n['canonical']}  ({n['category']})")
            if len(nodes) > 12:
                print(f"    … 외 {len(nodes) - 12}건")

    q = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc]
    if q:
        from collections import Counter
        print(f"\n  수정 큐 {len(q)}건 — {dict(Counter(x['kind'] for x in q))}")
    if paths.extract(f"{doc}.json").exists():
        print(f"  추출 체크포인트 — extract/{doc}.json (show 없이 그대로 읽어도 된다)")
    # **행별은 다른 명령이다** — 새 최상위 진입점을 늘리지 않는다(문서 7 §7.1).
    print(f"\n  행별 판정(값마다 어떻게 해소했나) — python run.py show report {doc}")
    return 0


# ---------------------------------------------------------------- report
def cmd_report(args):
    """**행별 판정 대장** — 사람이 문서를 옆에 놓고 정합성을 행 단위로 본다 (B74 ④).

    평가의 단위가 행이다: 「몇 개가 로직이고 몇 개가 LLM인가」도, 「이 칸의 값이
    어디에 붙었나」도 합계로는 답해지지 않는다. 재료는 인입이 남긴 대장
    (`data/ingest_log/<doc_id>.json`)이고 **여기서 새로 세지 않는다.**
    """
    if "--diff" in args:
        return _report_diff([a for a in args if a != "--diff"])
    if not args:
        raise SystemExit("doc_id를 달라: run.py show report CP01")          # [사용법]
    doc = args[0]
    as_json = "--json" in args
    data = ledger.read(doc)
    if data is None:
        _refuse_no_ledger(doc)
    rows = data.get("rows") or []
    if as_json:
        print(json.dumps({"doc_id": doc, "rows": rows,
                          "summary": ledger.summary(rows)},
                         ensure_ascii=False, indent=1))
        return 0
    su = ledger.summary(rows)
    kinds = Counter(r.get("role") for r in rows)
    print(f"■ {doc} 판정 대장 — 행 {len(rows)}건 "
          f"(entity {kinds.get('entity', 0)} · anchor {kinds.get('anchor', 0)} · "
          f"부착 {kinds.get('attribute', 0) + kinds.get('content', 0) + kinds.get('attach', 0)})")
    print(f"  값 {su['값']} · 사전 {su['사전']} · 스코프→판정 {su['스코프']} · "
          f"임베딩→판정 {su['임베딩']} · 겹침→판정 {su['겹침']} · 신규 {su['신규']} · "
          f"불확실 {su['불확실']} · 보류 {su['보류']} · LLM 호출 {su['호출']} · "
          f"토큰 {su['토큰']}")
    print("\n  " + _screen.pad("locator", 18) + _screen.pad("필드", 12)
          + _screen.pad("표기 → canonical", 46) + _screen.pad("경로", 15)
          + _screen.pad("판정", 11) + "큐")
    for r in rows:
        left = (r.get("surface") or "—")
        right = r.get("canonical") or "—"
        nid = (r.get("node_id") or "")[:6]
        arrow = f"{left} → {right}" + (f" ({nid})" if nid else "")
        print("  " + _screen.pad(r.get("locator") or "—", 18)
              + _screen.pad(r.get("field") or "—", 12) + _screen.pad(_screen.cut(arrow, 44), 46)
              + _screen.pad(r.get("path"), 15) + _screen.pad(r.get("verdict"), 11)
              + (r.get("queue_kind") or ""))
    return 0


def _report_diff(args):
    """두 대장의 **다른 행만** 본다 — 설정을 바꿔 넣은 두 산출의 비교 (B75 ①).

    비교 단위는 값이다(`locator · 필드 · 표기`). **다름의 기준은 판정과 node**이지
    경로가 아니다 — 경로는 「무엇으로 골랐나」이고, 그것이 달라도 답이 같으면
    그 값에서 임베딩과 겹침의 차이는 없었다는 뜻이다. 어느 쪽이 맞는지는 사람이
    본다 — 도구는 차이만 보인다.

    **node의 동일성은 canonical로 본다** — 의미 축 id는 ULID라 클린 재실행마다
    다르고(문서 7 §7.2), 그것을 비교하면 **전 행이 다르다**고 나온다. 사람이
    「같은 것에 붙었나」를 묻는 단위는 이름이다.
    """
    if len(args) < 2:
        raise SystemExit(                                                # [사용법]
            "두 대장을 달라: run.py show report --diff a.json b.json\n"
            "  (각각 run.py show report <doc_id> --json > a.json 으로 만든다)")
    a, b = (_load_ledger_json(x) for x in args[:2])

    def key(r):
        return (r.get("locator"), r.get("field"), r.get("surface"))

    ai = {key(r): r for r in a["rows"]}
    bi = {key(r): r for r in b["rows"]}
    keys = list(ai) + [k for k in bi if k not in ai]
    diff = [k for k in keys
            if (ai.get(k) or {}).get("verdict") != (bi.get(k) or {}).get("verdict")
            or _node_of(ai.get(k)) != _node_of(bi.get(k))]
    ta = sum(_tok(r) for r in a["rows"])
    tb = sum(_tok(r) for r in b["rows"])
    print(f"■ 판정 대장 비교 — 다른 행 {len(diff)} / 전체 {len(keys)} · "
          f"토큰 {ta:,} vs {tb:,}")
    print(f"  A {args[0]}  ·  B {args[1]}")
    if not diff:
        print("\n  다른 행 없음 — 두 설정이 같은 답을 냈다(비용만 다르다).")
        return 0
    print("\n  " + _screen.pad("locator", 16) + _screen.pad("필드", 11) + _screen.pad("표기", 22)
          + _screen.pad("A 경로 · 판정 · node · 후보", 50) + "B 경로 · 판정 · node · 후보")
    for k in diff:
        print("  " + _screen.pad(k[0] or "—", 16) + _screen.pad(k[1] or "—", 11)
              + _screen.pad(_screen.cut(k[2] or "—", 20), 22)
              + _screen.pad(_side(ai.get(k)), 50) + _side(bi.get(k)))
    return 0


def _node_of(r):
    """비교용 노드 동일성 — canonical이 정본이고 없으면 id다(ULID는 실행마다 다르다)."""
    if not r:
        return None
    return r.get("canonical") or r.get("node_id")


def _side(r):
    if not r:
        return "(없음)"
    return (f"{r.get('path')} · {r.get('verdict')} · "
            f"{_screen.cut(_node_of(r) or '—', 18)} · 후보 {r.get('candidates_n', 0)}")


def _tok(r):
    u = r.get("llm") or {}
    return int(u.get("in_tokens") or 0) + int(u.get("out_tokens") or 0)


def _load_ledger_json(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"[대장] 파일이 없다: {p}\n"                      # [상태]
                         f"  ▶ 다음 줄 — 대장을 파일로 낸다: "
                         f"python run.py show report <doc_id> --json > {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    if "rows" not in d:
        raise SystemExit(f"[대장] 행이 없는 파일이다: {p}\n"                # [상태]
                         f"  ▶ 다음 줄 — 대장을 파일로 낸다: "
                         f"python run.py show report <doc_id> --json > {p}")
    return d


def _refuse_no_ledger(doc):
    """대장이 없다 — **원인 + 그대로 칠 수 있는 다음 줄**(B61 계약)."""
    meta = store.read(store.DOC_REGISTRY, {}).get(doc)
    src = (meta or {}).get("source_path")
    dt = (meta or {}).get("doc_type")
    raise SystemExit(                                                    # [상태] 문면=_refuse_no_ledger
        f"[대장] '{doc}'의 판정 대장이 없다 — data/ingest_log/{doc}.json "
        f"(인입 기록은 {'있다' if meta else '없다'} · 대장 파일 "
        f"{len(list((ROOT / 'data' / 'ingest_log').glob('*.json'))) if (ROOT / 'data' / 'ingest_log').exists() else 0}건)\n"
        + (f"  ▶ 다음 줄 — 그 문서를 다시 넣으면 대장이 생긴다: "
           f"python run.py ingest-file {src} --doc-type {dt}"
           if meta and src and dt else
           "  ▶ 다음 줄 — 인입된 문서를 먼저 본다: python run.py show doc"))


# ---------------------------------------------------------------- chunk
def cmd_chunk(args):
    """청크 원문 — **질의가 '문서 근거'로 내놓는 그 문장**이다."""
    if not args:
        raise SystemExit("doc_id 또는 chunk_id를 달라")                        # [사용법]
    key = args[0]
    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    hit = {cid: c for cid, c in ch["chunks"].items()
           if cid == key or c.get("doc_id") == key}
    if not hit:
        print(f"'{key}' 청크 없음")
        return 1
    by_node = {}
    for d in ch["describes"]:
        by_node.setdefault(d["chunk_id"], []).append(d["node_id"])
    gs = _graphs()
    for cid, c in list(hit.items())[:20]:
        names = []
        for nid in by_node.get(cid, []):
            for g in gs.values():
                if nid in g.nodes:
                    names.append(g.nodes[nid]["canonical"])
        # 연결 노드 이름을 함께 보여야 "이 문장이 무엇의 근거인지"가 보인다
        print(f"\n── {cid}   [{c.get('doc_id')} · {c.get('source_locator')}]")
        if c.get("section"):
            print(f"   구획: {c['section']}")
        print(f"   연결: {', '.join(names) if names else '(없음 — 링킹 안 됨)'}")
        print(f"\n   {c.get('text', '')}")
    if len(hit) > 20:
        print(f"\n… 외 {len(hit) - 20}건")
    return 0


# ---------------------------------------------------------------- edges
def cmd_edges(args):
    lay = args[0] if args else "process"
    want = args[1] if len(args) > 1 else None
    g = open_graph(lay)
    gs = _graphs()
    from collections import Counter
    cnt = Counter(e["rel"] for e in g.edges if e.get("status") != "deleted_by_user")
    print(f"■ {lay} 엣지 {sum(cnt.values())} — {dict(cnt)}\n")
    for e in g.edges:
        if e.get("status") == "deleted_by_user" or (want and e["rel"] != want):
            continue
        def nm(i):
            for l2, g2 in gs.items():
                if i in g2.nodes:
                    return g2.nodes[i]["canonical"] + (f"[{l2}]" if l2 != lay else "")
            return i
        print(f"  {nm(e['src'])}  -{e['rel']}→  {nm(e['dst'])}"
              f"   ({e['status']} · {_prov(e.get('provenance'), 2)})")
    return 0


# ---------------------------------------------------------------- schema
def cmd_schema(args):
    """매칭 스키마 — **필드 → role 배정표**. 문서의 열이 그래프의 무엇이 되는지."""
    if not args:
        print("등록된 doc_type:")
        for dt, m in sorted(registry.all_doc_types().items()):
            print(f"  · {dt:<14} {m['status']:<10} 층={m.get('layer')}")
        return 0
    dt = args[0]
    s = registry.schema_of(dt)
    if not s:
        print(f"'{dt}' 미등록 — 등록은 python -m cli.register")
        return 1
    print(f"■ {dt}   [층 {s.get('layer')} · schema v{s.get('schema_version')}"
          f" · 블록 {s.get('use_blocks')}]\n")
    print(f"  {'필드':<22} {'role':<11} {'대상/부착':<18} 비고")
    print(f"  {'─' * 70}")
    for f, spec in (s.get("fields") or {}).items():
        tgt = spec.get("category") or spec.get("target_category") \
            or spec.get("attach_to_field") or ""
        note = []
        if spec.get("optional"):
            note.append("선택")
        if spec.get("contextual"):
            note.append("맥락형")
        if spec.get("target_layer"):
            note.append(f"→{spec['target_layer']}층")
        if spec.get("attr_name") and spec["attr_name"] != f:
            note.append(f"저장명 {spec['attr_name']}")
        print(f"  {f:<22} {spec.get('role', ''):<11} {tgt:<18} {' · '.join(note)}")
    if s.get("edges"):
        print(f"\n  ── 선언 엣지 ──")
        for e in s["edges"]:
            print(f"    {e['from']}  -{e['relation']}→  {e['to']}"
                  + ("   (선택)" if e.get("optional") else ""))
    print(f"\n  공용 블록이 주는 필드는 여기 없다 — schemas/blocks.json이 소유한다")
    return 0


# ---------------------------------------------------------------- meta
def cmd_meta(args):
    """메타데이터 계약 3층을 **실물로** 보여준다 (CH2 2.2).

    문서로 읽으면 추상적이고, 실물 한 건을 펼치면 즉시 이해된다.
    """
    docs = store.read(store.DOC_REGISTRY, {})
    doc = args[0] if args else (list(docs) or [None])[0]
    print("■ 파서 출력 계약 3층 (CH2 2.2) — 실물로 본다\n")
    print("  ① 문서 봉투 (doc 1개당 1회) — 재인입의 단위")
    m = docs.get(doc) or {}
    print(f"     doc_id={doc} · doc_type={m.get('doc_type')} · revision={m.get('revision')}")
    print(f"     source_path={m.get('source_path')} · doc_hash={str(m.get('doc_hash'))[:16]}…")
    print("     + payload_kind · parsed_at · parser_version · adapter_version · context?\n")

    ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    c = next((v for v in ch.values() if v.get("doc_id") == doc), None)
    print("  ② 조각 공통 (모든 record/chunk가 달고 온다)")
    if c:
        print(f"     source_locator={c.get('source_locator')} · doc_type={c.get('doc_type')}")
        print(f"     process_group/process_ref = 공정좌표 · electrode_type · context?")
    print("     ※ chunk_id·record_id·doc_hash는 **에이전트가 계산**한다 (파서가 안 만든다)\n")

    print("  ③ payload — doc_type별")
    print("     table → records[] (행 = record)")
    print("     prose → chunks[]  (text · section · meta / 이미지는 image_ref)")
    if c:
        print(f"\n  ── 실물 청크 1건 ──")
        print("     " + json.dumps({k: (str(v)[:60] + "…" if isinstance(v, str) and len(v) > 60
                                        else v) for k, v in c.items()},
                                   ensure_ascii=False, indent=2).replace("\n", "\n     "))
    print("\n  정본: docs/CH2_문서계약.md 2.2 · 주입용 발췌: kit/표적출력_정의.md")
    return 0


# ---------------------------------------------------------------- log
LOGS = {
    "defects": (store.DEFECTS, "결함 로그", "조용히 버리지 않기 위한 자리"),
    "gate": (store.GATE_REJECTS, "게이트 거부", "큐가 아니라 **관측 신호**다 (D-7)"),
    "link_miss": (store.LINK_MISS, "링킹 미스", "**계기판 5**의 재료 (문서 5 §5.5)"),
    "truncated": (store.CHUNK_TRUNCATED, "청크 잘림", "**계기판 4**의 재료"),
}


def _json_items(p):
    """JSON 로그의 **항목 배열**을 꺼낸다.

    형태가 둘이다 — 배열 그대로인 것과 `{rejects: [...], counts: {...}}`처럼
    묶음인 것. 파일마다 다른 것은 각 로그의 소유자가 정한 형태이고, 열람이
    그것을 알아서 편다.
    """
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("rejects", "items", "entries"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


def _json_counts(p):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return d.get("counts") if isinstance(d, dict) else None


def cmd_log(args):
    """로그 열람 — **문서가 「직접 열람」이라 적은 자리에 명령이 없었다**.

        run.py show log                 4종 요약
        run.py show log <이름> [N]      그 로그 마지막 N줄 (기본 40)

    이름: `defects` · `gate` · `link_miss` · `truncated`.

    **두 계기판 로그는 별도 파일이다**(문서 7 §7.1·§7.8) — 한 파일에 섞으면
    잘림 1건이 링킹 미스율의 분자로 잡힌다. 그래서 여기서도 각각 연다.

    **로그는 사건이 있어야 생긴다**(§7.8) — 없으면 그런 일이 없었다는 뜻이지
    고장이 아니다. 그 구분을 화면이 말한다.
    """
    if not args:
        print("로그 4종 — 사건이 있어야 생긴다 (없음 = 그런 일이 없었다)\n")
        for key, (name, label, why) in LOGS.items():
            p = store.path(name)
            if not p.exists():
                print(f"  {key:<10} {label:<10} (없음)          {why}")
                continue
            if name.endswith(".json"):
                n = len(_json_items(p))
            else:
                n = sum(1 for _ in p.read_text(encoding="utf-8").splitlines() if _.strip())
            print(f"  {key:<10} {label:<10} {n:>5}건        {why}")
        print("\n  내용: run.py show log <이름> [줄수]")
        return 0

    key = args[0]
    if key not in LOGS:
        print(f"알 수 없는 로그: {key} — {', '.join(LOGS)}")
        return 1
    name, label, why = LOGS[key]
    n = int(args[1]) if len(args) > 1 else 40
    p = store.path(name)
    print(f"■ {label}  ({name})   {why}")
    if not p.exists():
        print("  (없음) — 그런 사건이 없었다는 뜻이다. 고장이 아니다.")
        return 0
    if name.endswith(".json"):
        items = _json_items(p)
        print(f"  {len(items)}건 · 마지막 {min(n, len(items))}건\n")
        for it in items[-n:]:
            if isinstance(it, dict):
                head = it.get("reason") or it.get("verdict") or it.get("rel") or ""
                rest = {k: v for k, v in it.items() if k not in ("reason", "verdict")}
                print(f"  · {head}")
                print(f"      {json.dumps(rest, ensure_ascii=False)[:150]}")
            else:
                print(f"  · {it}")
        counts = _json_counts(p)
        if counts:
            print("\n  사유별 건수: " + " · ".join(f"{k} {v}" for k, v in counts.items()))
    else:
        lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        print(f"  {len(lines)}줄 · 마지막 {min(n, len(lines))}줄\n")
        for x in lines[-n:]:
            print(f"  · {x}")
    return 0


# ---------------------------------------------------------------- extract
def cmd_extract(args):
    """추출 체크포인트 — **존재 여부가 아니라 내용**을 본다.

        run.py show extract              문서별 상태 (파일 존재 = 추출 완료)
        run.py show extract <doc_id>     그 문서의 후보 전량

    `extract/{doc_id}.json`이 추출↔구축의 **계약 B**다(문서 4 §4.10) — 구축이
    무엇을 받았는지가 여기 있고, 그래프에 뜻대로 안 실렸을 때 **파서가 잘못
    냈는지 구축이 잘못 읽었는지**를 가르는 자리다. 상태만 보여서는 그것을
    가릴 수 없다.

    **후보는 표면형만이다** — 노드 id가 들어가면 추출이 그래프 상태에 의존해
    체크포인트의 독립성이 깨진다(§4.10-1).
    """
    ext = paths.extract()
    if not args:
        docs = store.read(store.DOC_REGISTRY, {})
        print("추출 체크포인트 — 파일 존재 = **추출 완료**(§7.8 · P-1)\n")
        for doc_id in docs:
            p = ext / f"{doc_id}.json"
            if not p.exists():
                print(f"  {doc_id:<10} ―  (추출 경로 아님 — 정형 인입)")
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            c = d.get("candidates") or []
            n_e = sum(len(x.get("entities") or []) for x in c)
            n_r = sum(len(x.get("relations") or []) for x in c)
            n_a = sum(len(x.get("attach") or []) for x in c)
            print(f"  {doc_id:<10} 청크 {len(c):>2} · 개체 {n_e:>2} · 관계 {n_r:>2} "
                  f"· 부착 {n_a:>2}   [{d.get('prompt_version')} / "
                  f"{d.get('config_version')}]")
        print("\n  내용: run.py show extract <doc_id>")
        return 0

    doc_id = args[0]
    p = ext / f"{doc_id}.json"
    if not p.exists():
        print(f"'{doc_id}' 추출 체크포인트 없음 — 정형 인입이거나 아직 안 돌았다")
        return 1
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"■ {doc_id}   [{d.get('stage')} · 층 {d.get('layer')}]")
    print(f"  재현성 3입력   adapter {d.get('adapter_version')} · "
          f"prompt {d.get('prompt_version')} · config {d.get('config_version')}")
    print(f"  추출 시점      {d.get('extracted_at')}")
    ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    for c in d.get("candidates") or []:
        cid = c.get("chunk_id")
        text = (ch.get(cid, {}).get("text") or "")[:60]
        print(f"\n  ── {cid} ──  {text}")
        for e in c.get("entities") or []:
            print(f"     개체  {e.get('surface')}  ({e.get('category')})")
        for r in c.get("relations") or []:
            print(f"     관계  {r.get('src')} ─{r.get('rel')}→ {r.get('dst')}")
        for a in c.get("attach") or []:
            tgt = a.get("attach_to")
            tgt_s = (f"{tgt.get('name')} ({tgt.get('category') or '카테고리 미정'})"
                     if isinstance(tgt, dict) else (tgt or "null"))
            print(f"     부착  {a.get('surface')} → {tgt_s}")
    return 0


def cmd_bm25(args):
    """BM-25 **대조군**의 상위 k를 사람이 직접 보는 창구 (문서 5 §5.5-3).

    질의 경로가 아니다 — 여기서 나온 것은 답이 아니라 **비교 기준**이다.
    그래프·사전을 읽지 않으므로 「키워드만으로 어디까지 되나」가 그대로 보인다.
    """
    if not args:
        raise SystemExit('사용: run.py show bm25 "<질문>" [k]')               # [사용법]
    from core.query import bm25
    q = args[0]
    k = int(args[1]) if len(args) > 1 and args[1].isdigit() else 8
    ch = store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}
    hits = bm25.search(q, k)
    print(f"BM-25 대조군 — {q!r}   (청크 {len(ch)}건 인덱스 · 상위 {k})")
    print("  ※ **대조군이다** — 그래프·사전·LLM을 쓰지 않는다. 질의의 답이 아니다")
    if not hits:
        print("  일치 0건 — 질문의 토큰이 어느 청크에도 없다")
        return 0
    for cid, sc in hits:
        c = ch.get(cid) or {}
        print(f"  {sc:6.2f}  {cid}")
        print(f"          ({c.get('doc_id')} {c.get('source_locator')}) "
              f"{(c.get('text') or '')[:64]}")
    return 0


def main(argv):
    if not argv:
        raise SystemExit(__doc__)                                         # [사용법]
    cmd, rest = argv[0], argv[1:]
    table = {"tree": cmd_tree, "node": cmd_node, "doc": cmd_doc, "chunk": cmd_chunk,
             "edges": cmd_edges, "schema": cmd_schema, "meta": cmd_meta,
             "log": cmd_log, "extract": cmd_extract, "bm25": cmd_bm25,
             "report": cmd_report}
    if cmd not in table:
        raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")                  # [사용법]
    return table[cmd](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
