# -*- coding: utf-8 -*-
"""산출물 열람 — **시각화 없이 텍스트로 본다** (명세 §11 · 카드 P5).

    python -m cli.show tree   [층]           골격 트리 (사내 공정이 맞게 섰나)
    python -m cli.show node   <이름>          노드 하나 전부 — 값·별칭·출처·연결
    python -m cli.show doc    <doc_id>        그 문서가 만든 것 전부 (역추적)
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

from core import registry, store
from core.bootstrap import load_config, open_graph
from core.ids import norm
from core.ops import is_live
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
        raise SystemExit("이름을 달라: run.py show node '노칭 정밀도'")
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
    print(f"  원본       {meta.get('source_path')}")
    print(f"  doc_hash   {meta.get('doc_hash', '')[:16]}…")
    print(f"  최초 인입   {meta.get('first_ingested_at')}")

    ch = store.read(store.CHUNKS, {"chunks": {}, "describes": []})
    mine = {cid: c for cid, c in ch["chunks"].items() if c.get("doc_id") == doc}
    linked = sum(1 for c in mine.values() if c.get("linked"))
    print(f"\n  청크 {len(mine)}건 (그래프에 연결 {linked})")

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
    if (ROOT / "extract" / f"{doc}.json").exists():
        print(f"  추출 체크포인트 — extract/{doc}.json (show 없이 그대로 읽어도 된다)")
    return 0


# ---------------------------------------------------------------- chunk
def cmd_chunk(args):
    """청크 원문 — **질의가 '문서 근거'로 내놓는 그 문장**이다."""
    if not args:
        raise SystemExit("doc_id 또는 chunk_id를 달라")
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
        print(f"'{dt}' 미등록 — 등록은 run.py register")
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


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, rest = argv[0], argv[1:]
    table = {"tree": cmd_tree, "node": cmd_node, "doc": cmd_doc, "chunk": cmd_chunk,
             "edges": cmd_edges, "schema": cmd_schema, "meta": cmd_meta}
    if cmd not in table:
        raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")
    return table[cmd](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
