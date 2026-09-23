# -*- coding: utf-8 -*-
"""칸 0.3 — 내보내기 — 시각화·외부 도구용 **파생물** (명세 §11 · 카드 P5).

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
import re
import sys
from pathlib import Path


from core import paths
from core.build import ledger
from core.state import store
from core.state.bootstrap import coord_layer, open_graph
from core.state.status import is_live
from router import discover


def _q(v):
    """Cypher 문자열 리터럴 — 작은따옴표·역슬래시·개행을 이스케이프한다."""
    s = "" if v is None else str(v)
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _world():
    return {lay: open_graph(lay) for lay in discover()}


# ---------------------------------------------------------------- cypher
def out_path(arg, default, *, as_dir=False):
    """파생물 산출 자리 — **`export/`를 만드는 자리는 여기 하나다**(B77 ④).

    구판은 세 명령이 각자 만들었다. 파생물은 상태 5단의 ⑤단이고(문서 7 §7.8),
    그 단의 자리를 아는 코드가 흩어지면 자리를 옮길 때 한 곳이 남는다.
    """
    p = Path(arg) if arg else paths.export(default)
    paths.ensure(p if as_dir else p.parent)
    return p


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
    out = out_path(args[0] if args else None, "graph.cypher")
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
    print(f"[export] 노드 {n_node} · 엣지 {n_edge} → {paths.show(out)}")
    print("  적재: cypher-shell -f " + str(paths.show(out)))
    print("  ※ 파생물이다 — 여기서 고친 것은 돌아오지 않는다. 고치려면 run.py ops")
    return 0


# ---------------------------------------------------------------- csv
def cmd_csv(args):
    """`nodes.csv` · `edges.csv` — Gephi·엑셀·pandas용. 표로 훑어보기 좋다."""
    import csv
    d = out_path(args[0] if args else None, "", as_dir=True)
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

    print(f"[export] {paths.show(d)}/nodes.csv · edges.csv  (엑셀용 BOM 포함)")
    return 0


# ---------------------------------------------------------------- mermaid
def cmd_mermaid(args):
    """골격 다이어그램 — **보고서에 붙이는 용도**다.

        python run.py export mermaid [층]          골격 대표 흐름
        python run.py export mermaid cross         **걸침 관계** (층 구분 표기)

    전체 그래프를 그리면 읽을 수 없으므로 **골격만·대표 흐름만** 그린다.
    (문서가 만든 수십~수백 노드는 그림으로 볼 것이 아니라 질의로 볼 것이다 —
    전량을 눈으로 보려면 `export html`이다)

    **빈 출력을 성공으로 내지 않는다.** 층이 골격 관계를 선언하지 않으면(품질층은
    `skeleton.relations`가 없다) 그릴 것이 없는데, 구판은 빈 코드펜스를 찍고
    exit 0으로 끝냈다 — **빈 출력은 성공이 아니다.** 왜 비었는지를 말하고 무엇을
    대신 쓰면 되는지 알려준 뒤 실패로 끝낸다.
    """
    if args and args[0] == "cross":
        return _mermaid_cross()
    lay = args[0] if args else coord_layer()   # 기본은 **좌표 층**이다(B85 ②)
    g = open_graph(lay)
    from core.state.bootstrap import load_config
    cfg = load_config(lay)
    skel = cfg.get("skeleton") or {}
    sib = (skel.get("relations") or {}).get("sibling")
    if not sib:
        print(f"[export] '{lay}' 층은 골격 **관계**를 선언하지 않는다 "
              f"(skeleton.type={skel.get('type')!r} · relations 없음).")
        print("  대표 흐름 다이어그램은 그릴 것이 없다 — 빈 출력을 내지 않는다.")
        print(f"  대신: `run.py export mermaid cross`(걸침 관계) · "
              f"`run.py export html`(전량) · `run.py show tree {lay}`")
        return 1

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
    if not used:
        print(f"[export] '{lay}' 층에 대표 흐름(`{sib}`) 엣지가 없다 — "
              f"골격이 아직 심기지 않았거나 순서 선언이 비어 있다.")
        print("  빈 다이어그램을 내지 않는다. `run.py bootstrap`을 먼저 돌려라.")
        return 1
    print("\n".join(L))
    print(f"\n// 대표 흐름({sib}) {len(used)}노드 — 개념 레벨만. "
          f"걸침 관계는 `export mermaid cross`, 전량은 `export html`")
    return 0


def _mermaid_cross():
    """**걸침 관계 다이어그램** — 층 구분을 표기해 그린다 (갭 `spec-12-16-80`).

    occurs_in·controlled_by 같은 브리지가 **이 시스템의 존재 이유**인데(문서 7
    §7.8), 층별 골격 흐름만 그리면 그것이 어느 그림에도 없다. 여기서는 반대로
    **걸침 엣지만** 그리고 층을 `subgraph`로 갈라 표기한다.

    끝점이 서로 다른 층에 있는 엣지가 걸침이다 — 엣지 레코드에 `layer` 필드가
    없으므로(파일 위치로만 안다) 노드의 층으로 판정한다.
    """
    world = _world()
    layer_of = {i: lay for lay, g in world.items() for i in g.nodes}
    names = {i: n["canonical"] for g in world.values() for i, n in g.nodes.items()}
    live = {i for g in world.values() for i, n in g.nodes.items() if is_live(n)}

    cross = []
    for lay, g in world.items():
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            if e["src"] not in live or e["dst"] not in live:
                continue
            if layer_of.get(e["src"]) != layer_of.get(e["dst"]):
                cross.append(e)
    if not cross:
        print("[export] 걸침 엣지가 없다 — 층이 하나거나 브리지가 아직 서지 않았다.")
        print("  빈 다이어그램을 내지 않는다.")
        return 1

    by_layer = {}
    for e in cross:
        for side in ("src", "dst"):
            by_layer.setdefault(layer_of[e[side]], set()).add(e[side])

    L = ["```mermaid", "graph LR"]
    for lay in sorted(by_layer):
        L.append(f'  subgraph {lay}["{lay} 층"]')
        for nid in sorted(by_layer[lay], key=lambda i: names[i]):
            L.append(f'    {nid[-6:]}["{names[nid].split("::")[-1]}"]')
        L.append("  end")
    for e in sorted(cross, key=lambda x: (x["rel"], names[x["src"]])):
        L.append(f'  {e["src"][-6:]} -.->|{e["rel"]}| {e["dst"][-6:]}')
    L.append("```")
    print("\n".join(L))
    rels = sorted({e["rel"] for e in cross})
    print(f"\n// 걸침 {len(cross)}엣지 · 관계 {', '.join(rels)} · "
          f"층 {len(by_layer)} — 점선이 층 경계를 넘는 연결이다")
    return 0


def main(argv):
    if not argv:
        raise SystemExit(__doc__)                                         # [사용법]
    table = {"cypher": cmd_cypher, "csv": cmd_csv, "mermaid": cmd_mermaid,
             "html": cmd_html}
    cmd, rest = argv[0], argv[1:]
    if cmd not in table:
        raise SystemExit(f"알 수 없는 형식: {cmd}\n{__doc__}")                  # [사용법]
    return table[cmd](rest)


# ---------------------------------------------------------------- html
# **템플릿은 파일이다**(B78 2b) — 900행 파일의 3분의 2가 HTML·CSS·JS 문자열이었고,
# 그 안은 파이썬 도구가 읽지 못한다(문법 강조도 검사도 없다). 자리는 `cli/viewer.html`
# 하나이고, 이 파일은 **자리를 채우는 일**만 한다. CDN은 그대로 0이다.
VIEWER_HTML = Path(__file__).resolve().parent / "viewer.html"
_SECTION = re.compile(r"^<!--#SECTION ([a-z_]+)-->$", re.M)


def _sections():
    """`cli/viewer.html`을 구획으로 읽는다 — `{이름: 본문}`.

    구획 표시 줄의 앞뒤 줄바꿈 **한 개씩**만 걷는다: 본문 안의 빈 줄은 산출의
    일부이고(옛 문자열 상수가 그대로 싣던 것), 그것을 지우면 파생물이 한 글자
    달라진다 — 화면이 증거인 자리에서 그 한 글자를 또 누가 대조하게 된다.
    """
    parts = _SECTION.split(VIEWER_HTML.read_text(encoding="utf-8"))
    return {name: body.removeprefix("\n").removesuffix("\n")
            for name, body in zip(parts[1::2], parts[2::2])}


_SLOTS = ("/*__PANEL_CSS__*/", "<!--__PANEL_HTML__-->", "/*__HL_BEFORE__*/",
          "/*__HL_AFTER__*/", "/*__PANEL_JS__*/")


def _queue_state():
    """미종결 큐의 `node_id → kind` (B74 ③). 종결분(`resolution`)은 세지 않는다."""
    out = {}
    for x in store.read(store.QUEUE, []):
        if x.get("kind") not in ("auto_node", "uncertain_match"):
            continue
        if x.get("resolution"):
            continue
        nid = (x.get("payload") or {}).get("node_id")
        if nid:
            out.setdefault(nid, x["kind"])
    return out


def _docs_of(provenance):
    """이 노드를 만든 문서들 — provenance 접두다(`CP01#…`·`CP01:…`).

    근거가 회수돼 provenance가 빈 노드는 **`(없음)`으로 센다** — 빈 목록으로 두면
    문서 필터가 그것을 영영 못 켜서 「전부 켰는데 안 보이는 노드」가 생긴다.
    """
    out = []
    for p in provenance or []:
        d = str(p).split("#")[0].split(":")[0]
        if d and d not in out:
            out.append(d)
    return out or ["(없음)"]


def graph_data(world):
    """월드 → 화면이 먹는 nodes/edges 배열. **변환 지점 둘은 여기 하나뿐이다.**

    엣지가 `status`·`prov`·`id`를 지고 간다(B74 ③) — 저장에는 있는데 화면에는
    없었다. 노드는 `made_by`(②의 대장이 말하는 **생성 경로**)·별칭 수·값 수·큐를
    더 지고 간다: 「몇 개가 로직이고 몇 개가 LLM인가」를 그림 위에서 세려면 그 사실이
    점 하나하나에 붙어 있어야 한다.
    """
    live = {i for g in world.values() for i, n in g.nodes.items() if is_live(n)}
    layer_of = {i: lay for lay, g in world.items() for i in g.nodes}
    made = ledger.made_by()
    queued = _queue_state()

    nodes = []
    for lay, g in world.items():
        for n in g.nodes.values():                  # ① id-keyed dict → 배열
            if not is_live(n):
                continue
            prov = n.get("provenance") or []
            nodes.append({
                "id": n["id"], "name": n["canonical"], "layer": lay,
                "category": n["category"], "status": n.get("status"),
                "tier": n.get("tier"), "polarity": n.get("polarity"),
                "prov": ", ".join(prov[:4]),
                # 대장이 모르는 노드는 골격(seed)이거나 대장 이전의 것이다 —
                # 둘을 섞지 않는다: 「모른다」가 「골격이다」로 읽히면 집계가 거짓말한다.
                "made_by": made.get(n["id"]) or (
                    "seed" if n.get("status") == "seed" else "unknown"),
                "aliases": len(n.get("aliases") or []),
                "attrs": len(n.get("attrs") or {}),
                "queue": queued.get(n["id"]),
                "docs": _docs_of(prov),
            })

    edges = []
    for lay, g in world.items():
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            if e["src"] not in live or e["dst"] not in live:
                continue
            edges.append({                          # ② layer 주입 + cross 표시
                "id": f"{e['src']}|{e['rel']}|{e['dst']}",
                "src": e["src"], "dst": e["dst"], "rel": e["rel"], "layer": lay,
                "status": e.get("status"),
                "prov": ", ".join((e.get("provenance") or [])[:4]),
                "cross": layer_of.get(e["src"]) != layer_of.get(e["dst"]),
            })
    return nodes, edges


def build_html(world, *, query_panel=False):
    """**템플릿은 하나다** — 파일로 저장하는 `export html`과 뷰어가 같은 것을 쓴다.

    복제하면 한쪽만 고쳐지고, 그 순간 「뷰어에서 본 그림」과 「내보낸 그림」이 다른
    것이 된다 — 화면이 증거인 시스템에서 그것은 증거가 갈리는 것이다.

    `query_panel`은 **자리 5개를 채우느냐 비우느냐** 하나다. 끄면 옛 산출과
    한 글자도 다르지 않다(질문 패널도 `highlight`도 들어가지 않는다).
    """
    nodes, edges = graph_data(world)
    n_cross = sum(1 for e in edges if e["cross"])
    sec = _sections()
    html = (sec["page"].replace("__TITLE__", "온톨로지 그래프")
            .replace("__SUB__", f"노드 {len(nodes)} · 엣지 {len(edges)} · "
                                f"걸침 {n_cross} · 층 {len(world)}")
            .replace("/*__DATA__*/", json.dumps({"nodes": nodes, "edges": edges},
                                                ensure_ascii=False)))
    fill = ((sec["panel_css"], sec["panel_html"], sec["hl_before"],
             sec["hl_after"], sec["panel_js"]) if query_panel else ("",) * 5)
    for slot, code in zip(_SLOTS, fill):
        assert slot in html, slot          # 자리가 사라지면 조용히 빈 화면이 된다
        if not code:
            # 빈 자리는 **줄째로** 걷어낸다 — 빈 줄이 남으면 「패널을 끄면 옛 산출
            # 그대로」가 참이 아니게 되고, 그 한 글자를 누가 또 대조하게 된다.
            html = re.sub(r"^[ \t]*" + re.escape(slot) + r"\n", "", html, flags=re.M)
        html = html.replace(slot, code)
    return html


def cmd_html(args):
    """**그래프 뷰어** — 단일 HTML 파일 (문서 7 §7.8 시각화 3형태 중 html).

    **외부 CDN을 쓰지 않는다.** vis.js·cytoscape를 CDN에서 불러오면 사내망에서
    화면이 비어 뜬다 — 그래서 렌더러를 인라인으로 싣는다(canvas + 결정적 배치).
    파일 하나면 열린다: 서버도, 설치도, 네트워크도 필요 없다.

    **GraphStore 경유로 읽는다**(문서 1 B6) — 저장 파일을 직접 열지 않는다.
    파생물도 예외가 아니다(§7.7-2).

    **변환 지점 둘**:
      ① 저장 레코드의 노드는 배열이 아니라 **id-keyed dict**다 → 배열로 편다.
      ② **엣지에 `layer` 필드가 없다** — 어느 층 파일에 있느냐로만 층을 안다.
         그래서 합칠 때 주입하고, 끝점이 다른 층이면 `cross`로 표시한다.

    **걸러 그리더라도 cross-layer 엣지는 화면에 남긴다**(§7.8) — 층간 연결이 이
    시스템의 존재 이유이고, 그것이 화면에 안 나오면 그 동작을 텍스트 열람으로만
    증명하게 된다. 뷰어에서 붉은 점선으로 그린다.

    필터·색상 축 5종: `layer` · `category` · `status` · `tier` · `polarity`.
    """
    out = out_path(args[0] if args else None, "graph.html")

    world = _world()
    nodes, edges = graph_data(world)
    n_cross = sum(1 for e in edges if e["cross"])
    # **질문 패널 없이 낸다** — 파일 하나로 열리는 산출이라 물어볼 서버가 없다.
    # 패널을 넣으면 열리기는 하되 모든 질문이 실패하는 화면이 된다(B52).
    out.write_text(build_html(world, query_panel=False), encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"[export] 노드 {len(nodes)} · 엣지 {len(edges)} "
          f"(걸침 {n_cross}) → {paths.show(out)}  [{size:.0f}KB]")
    print(f"  브라우저로 연다: file://{out}")
    print("  ※ 외부 CDN 없음 — 사내망·오프라인에서 그대로 열린다")
    print("  ※ 파생물이다 — 여기서 고친 것은 돌아오지 않는다(P5). 고치려면 run.py ops")
    return 0


# **진입점은 파일 끝이다.** 중간에 두면 그 아래 정의된 명령(cmd_html)이 `main()`의
# 디스패치 표를 만들 때 아직 없어 NameError로 죽는다 — import 경로는 파일을 끝까지
# 읽으므로 회귀가 이것을 못 잡았다(실측: `python -m cli.export html` → NameError).
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
