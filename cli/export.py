# -*- coding: utf-8 -*-
"""내보내기 — 시각화·외부 도구용 **파생물** (명세 §11 · 카드 P5).

    python -m cli.export cypher [출력.cypher]    Neo4j 적재용
    python -m cli.export csv    [출력디렉터리]    nodes.csv · edges.csv (Gephi·엑셀)
    python -m cli.export mermaid [층]            보고서용 다이어그램 (골격)

**여기서 나오는 것은 전부 파생물이다.** 진실은 `data/`의 JSON 그래프 + 청크 저장소이고
(P5), 이 파일들은 언제든 다시 만들 수 있다 — 그래서 **되돌려 읽지 않는다.** 시각화
도구에서 고친 것을 다시 가져오는 경로는 없다. 고치는 것은 I축 도구(`run.py ops`)다.

**질의에는 필요 없다.** `run.py query`는 JSON을 직접 읽는다 — Neo4j는 사람이 눈으로
보려고 올리는 것이지 파이프라인의 일부가 아니다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from core import store
from core.bootstrap import open_graph
from core.ops import is_live
from router import discover


def _q(v):
    """Cypher 문자열 리터럴 — 작은따옴표·역슬래시·개행을 이스케이프한다."""
    s = "" if v is None else str(v)
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _world():
    return {lay: open_graph(lay) for lay in discover()}


# ---------------------------------------------------------------- cypher
def cmd_cypher(args):
    """Neo4j 적재 스크립트.

    **매핑 규칙**
      · 노드 라벨 = `category` (Process · Unit · Property · Failure …) + `:Node`
      · 노드 키   = `id`(ULID) — 층이 달라도 유일하다
      · 엣지 타입 = `rel`(part_of · has_property · causes …)
      · attribute는 **노드 속성으로 펴지 않는다** — 맥락·출처가 딸린 구조라
        평탄화하면 그 둘이 사라진다. JSON 문자열로 통째 싣고 원본은 data/에 둔다.

    **툼스톤·사람 삭제 엣지는 내보내지 않는다** — 화면에 살아 있는 것만 띄운다.
    """
    out = Path(args[0]) if args else ROOT / "export" / "graph.cypher"
    out.parent.mkdir(parents=True, exist_ok=True)
    L, n_node, n_edge = [], 0, 0

    L += ["// 온톨로지 그래프 — data/의 JSON에서 파생 (P5: 재생성 가능물)",
          "// 적재:  cypher-shell -f graph.cypher   또는 Neo4j Browser에 붙여넣기",
          "",
          "// 기존 것을 지우고 새로 올린다 — 이 파일이 진실이 아니므로 덮어써도 된다",
          "MATCH (n:Node) DETACH DELETE n;",
          "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE;",
          ""]

    for lay, g in _world().items():
        L.append(f"// ── {lay} 노드 ──")
        for n in g.nodes.values():
            if not is_live(n):
                continue                       # 툼스톤은 화면에 올리지 않는다
            props = [f"id: {_q(n['id'])}", f"name: {_q(n['canonical'])}",
                     f"layer: {_q(lay)}", f"status: {_q(n.get('status'))}"]
            if n.get("polarity") and n["polarity"] != "none":
                props.append(f"polarity: {_q(n['polarity'])}")
            if n.get("tier"):
                props.append(f"tier: {_q(n['tier'])}")
            if n.get("aliases"):
                props.append("aliases: [" + ", ".join(
                    _q(a["surface"]) for a in n["aliases"]) + "]")
            if n.get("provenance"):
                props.append("provenance: [" + ", ".join(
                    _q(p) for p in n["provenance"]) + "]")
            if n.get("attrs"):
                props.append("attrs_json: " + _q(
                    json.dumps(n["attrs"], ensure_ascii=False)))
            L.append(f"CREATE (:{n['category']}:Node {{{', '.join(props)}}});")
            n_node += 1
        L.append("")

    live = {i for g in _world().values() for i, n in g.nodes.items() if is_live(n)}
    for lay, g in _world().items():
        L.append(f"// ── {lay} 엣지 (걸침 포함) ──")
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue                       # 사람이 지운 것은 되살리지 않는다
            if e["src"] not in live or e["dst"] not in live:
                continue
            props = [f"status: {_q(e.get('status'))}"]
            if e.get("provenance"):
                props.append("provenance: [" + ", ".join(
                    _q(p) for p in e["provenance"]) + "]")
            L.append(f"MATCH (a:Node {{id: {_q(e['src'])}}}), "
                     f"(b:Node {{id: {_q(e['dst'])}}}) "
                     f"CREATE (a)-[:{e['rel']} {{{', '.join(props)}}}]->(b);")
            n_edge += 1
        L.append("")

    L += ["// 볼 만한 질의 몇 개",
          "//   MATCH (p:Process)-[:part_of]->(q:Process) RETURN p, q;",
          "//   MATCH (n)-[r]-(m) WHERE n.name CONTAINS '노칭' RETURN n, r, m;",
          "//   MATCH (f:Failure)-[:occurs_in]->(p:Process) RETURN f.name, p.name;"]

    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[export] 노드 {n_node} · 엣지 {n_edge} → {out.relative_to(ROOT)}")
    print("  적재: cypher-shell -f " + str(out.relative_to(ROOT)))
    print("  ※ 파생물이다 — 여기서 고친 것은 돌아오지 않는다. 고치려면 run.py ops")
    return 0


# ---------------------------------------------------------------- csv
def cmd_csv(args):
    """`nodes.csv` · `edges.csv` — Gephi·엑셀·pandas용. 표로 훑어보기 좋다."""
    import csv
    d = Path(args[0]) if args else ROOT / "export"
    d.mkdir(parents=True, exist_ok=True)
    world = _world()
    live = {i for g in world.values() for i, n in g.nodes.items() if is_live(n)}

    with (d / "nodes.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "category", "layer", "status", "polarity", "tier",
                    "aliases", "provenance", "attrs_json"])
        for lay, g in world.items():
            for n in g.nodes.values():
                if not is_live(n):
                    continue
                w.writerow([n["id"], n["canonical"], n["category"], lay,
                            n.get("status"), n.get("polarity"), n.get("tier"),
                            " | ".join(a["surface"] for a in n["aliases"]),
                            " | ".join(n.get("provenance") or []),
                            json.dumps(n.get("attrs") or {}, ensure_ascii=False)])

    names = {i: n["canonical"] for g in world.values() for i, n in g.nodes.items()}
    with (d / "edges.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["src_id", "src_name", "rel", "dst_id", "dst_name",
                    "layer", "status", "provenance"])
        for lay, g in world.items():
            for e in g.edges:
                if e.get("status") == "deleted_by_user":
                    continue
                if e["src"] not in live or e["dst"] not in live:
                    continue
                w.writerow([e["src"], names.get(e["src"], ""), e["rel"],
                            e["dst"], names.get(e["dst"], ""), lay,
                            e.get("status"), " | ".join(e.get("provenance") or [])])

    print(f"[export] {d.relative_to(ROOT)}/nodes.csv · edges.csv  (엑셀용 BOM 포함)")
    return 0


# ---------------------------------------------------------------- mermaid
def cmd_mermaid(args):
    """골격 다이어그램 — **보고서에 붙이는 용도**다.

    전체 그래프를 그리면 읽을 수 없으므로 **골격만·대표 흐름만** 그린다.
    (문서가 만든 수십~수백 노드는 그림으로 볼 것이 아니라 질의로 볼 것이다)
    """
    lay = args[0] if args else "process"
    g = open_graph(lay)
    from core.bootstrap import load_config
    cfg = load_config(lay)
    sib = ((cfg.get("skeleton") or {}).get("relations") or {}).get("sibling")
    seed = {i: n for i, n in g.nodes.items() if n.get("status") == "seed"}

    L = ["```mermaid", "graph LR"]
    used = set()
    for e in g.edges:
        if e["rel"] != sib or e["src"] not in seed or e["dst"] not in seed:
            continue
        a, b = seed[e["src"]], seed[e["dst"]]
        if a.get("polarity") not in (None, "none"):
            continue                            # 개념 레벨만 — 축 인스턴스는 뺀다
        ida, idb = a["id"][-6:], b["id"][-6:]
        L.append(f'  {ida}["{a["canonical"].split("::")[-1]}"]'
                 f' --> {idb}["{b["canonical"].split("::")[-1]}"]')
        used |= {ida, idb}
    L.append("```")
    print("\n".join(L))
    print(f"\n// 대표 흐름({sib}) {len(used)}노드 — 개념 레벨만. "
          f"전체 그래프는 export cypher로 Neo4j에")
    return 0


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    table = {"cypher": cmd_cypher, "csv": cmd_csv, "mermaid": cmd_mermaid}
    cmd, rest = argv[0], argv[1:]
    if cmd not in table:
        raise SystemExit(f"알 수 없는 형식: {cmd}\n{__doc__}")
    return table[cmd](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
