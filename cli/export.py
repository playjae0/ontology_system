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
from core.status import is_live
from router import discover


def _q(v):
    """Cypher 문자열 리터럴 — 작은따옴표·역슬래시·개행을 이스케이프한다."""
    s = "" if v is None else str(v)
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _world():
    return {lay: open_graph(lay) for lay in discover()}


# ---------------------------------------------------------------- cypher
def _short(p):
    """출력 경로 표기 — **레포 밖이면 절대 경로 그대로 낸다.**

    `Path.relative_to`는 밖의 경로에 ValueError를 던진다. 산출은 이미 끝난 뒤라
    **파일은 만들어졌는데 화면이 크래시하는** 모양이 된다(실측).
    """
    try:
        return Path(p).resolve().relative_to(ROOT)
    except ValueError:
        return Path(p).resolve()


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
    print(f"[export] 노드 {n_node} · 엣지 {n_edge} → {_short(out)}")
    print("  적재: cypher-shell -f " + str(_short(out)))
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

    print(f"[export] {_short(d)}/nodes.csv · edges.csv  (엑셀용 BOM 포함)")
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
    lay = args[0] if args else "process"
    g = open_graph(lay)
    from core.bootstrap import load_config
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
        raise SystemExit(__doc__)
    table = {"cypher": cmd_cypher, "csv": cmd_csv, "mermaid": cmd_mermaid,
             "html": cmd_html}
    cmd, rest = argv[0], argv[1:]
    if cmd not in table:
        raise SystemExit(f"알 수 없는 형식: {cmd}\n{__doc__}")
    return table[cmd](rest)


# ---------------------------------------------------------------- html
_HTML_HEAD = """<!doctype html>
<meta charset="utf-8">
<title>온톨로지 그래프 — {title}</title>
<style>
 :root{{--bg:#0f1115;--fg:#e6e6e6;--dim:#8b93a1;--line:#2a2f3a;--panel:#161a22}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--bg);color:var(--fg);
   font:13px/1.5 -apple-system,"Segoe UI","Noto Sans KR",sans-serif;overflow:hidden}}
 #wrap{{display:flex;height:100vh}}
 #side{{width:280px;flex:0 0 280px;background:var(--panel);border-right:1px solid var(--line);
   padding:14px;overflow:auto}}
 #side h1{{font-size:14px;margin:0 0 4px}}
 #side .sub{{color:var(--dim);font-size:11px;margin-bottom:14px}}
 fieldset{{border:1px solid var(--line);border-radius:6px;margin:0 0 12px;padding:8px 10px}}
 legend{{color:var(--dim);font-size:11px;padding:0 4px}}
 label{{display:flex;align-items:center;gap:6px;padding:2px 0;cursor:pointer}}
 label .sw{{width:10px;height:10px;border-radius:2px;flex:0 0 10px}}
 label .n{{margin-left:auto;color:var(--dim);font-size:11px}}
 #stat{{color:var(--dim);font-size:11px;margin-top:10px;line-height:1.7}}
 #stage{{flex:1;position:relative}}
 canvas{{display:block;cursor:grab}} canvas.drag{{cursor:grabbing}}
 #tip{{position:absolute;pointer-events:none;background:#000c;border:1px solid var(--line);
   border-radius:6px;padding:8px 10px;max-width:340px;display:none;font-size:12px}}
 #tip b{{color:#fff}} #tip .k{{color:var(--dim)}}
 #hint{{position:absolute;left:12px;bottom:10px;color:var(--dim);font-size:11px}}
</style>
<div id="wrap"><div id="side">
 <h1>{title}</h1><div class="sub">{sub}</div>
 <div id="filters"></div>
 <div id="stat"></div>
</div><div id="stage"><canvas id="cv"></canvas><div id="tip"></div>
<div id="hint">드래그 = 이동 · 휠 = 확대 · 노드 클릭 = 고정/해제</div></div></div>
<script>
const DATA = """

_HTML_TAIL = r""";
// ── 색상: 축별 결정적 팔레트. 같은 값은 언제나 같은 색이다.
const PAL = ["#7aa2f7","#9ece6a","#e0af68","#f7768e","#bb9af7","#7dcfff",
             "#ff9e64","#73daca","#c0caf5","#f4bf75","#a6e3a1","#eba0ac"];
function color(v){let h=0; for(const c of String(v)) h=(h*31+c.charCodeAt(0))|0;
  return PAL[Math.abs(h)%PAL.length];}

const AXES = ["layer","category","status","tier","polarity"];
const state = {};          // 축 → 켜진 값 Set
const fixed = new Set();

function values(ax){const m=new Map();
  for(const n of DATA.nodes){const v=n[ax]??"(없음)"; m.set(v,(m.get(v)||0)+1);} 
  return [...m.entries()].sort((a,b)=>b[1]-a[1]);}

// 색상 축 — 값이 가장 많이 갈리는 축을 고른다. 필터를 만들기 **전에** 정한다.
const COLOR_AX = (() => {
  let best = "layer", n = 0;
  for(const ax of AXES){const c = values(ax).length; if(c > n){n = c; best = ax;}}
  return best;
})();

const fbox = document.getElementById("filters");
for(const ax of AXES){
  const vs = values(ax);
  if(vs.length<=1 && vs[0] && vs[0][0]==="(없음)") continue;
  state[ax] = new Set(vs.map(v=>v[0]));
  const fs = document.createElement("fieldset");
  fs.innerHTML = `<legend>${ax}</legend>`;
  fs.dataset.ax = ax;
  for(const [v,c] of vs){
    const l = document.createElement("label");
    // 스와치는 **색상 축에서만** 실제 색이다 — 다른 축에서 색을 칠하면 화면의
    // 색과 어긋나 범례가 거짓말을 한다.
    l.innerHTML = `<input type=checkbox checked><span class=sw data-v="${v}"></span>`
                + `<span>${v}</span><span class=n>${c}</span>`;
    l.querySelector("input").onchange = e => {
      e.target.checked ? state[ax].add(v) : state[ax].delete(v); layout(); draw();};
    fs.appendChild(l);
  }
  fbox.appendChild(fs);
}
// 색상 축의 스와치만 실제 색으로 칠하고, 나머지 축은 중립 테두리로 둔다.
for(const fs of fbox.querySelectorAll("fieldset")){
  const on = fs.dataset.ax === COLOR_AX;
  for(const sw of fs.querySelectorAll(".sw"))
    sw.style.background = on ? color(sw.dataset.v) : "transparent",
    sw.style.border = on ? "none" : "1px solid var(--line)";
  if(on) fs.querySelector("legend").textContent += " (색상)";
}

function visible(n){return AXES.every(ax => !state[ax] || state[ax].has(n[ax]??"(없음)"));}

const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const tip = document.getElementById("tip"), stage = document.getElementById("stage");
let view = {x:0,y:0,k:1}, nodes = [], edges = [], byId = new Map();

function layout(){
  nodes = DATA.nodes.filter(visible);
  byId = new Map(nodes.map(n=>[n.id,n]));
  edges = DATA.edges.filter(e => byId.has(e.src) && byId.has(e.dst));
  // 결정적 초기 배치 — 층/카테고리별 원형 클러스터. 같은 데이터는 같은 그림이다.
  const groups = new Map();
  for(const n of nodes){const g=n[COLOR_AX]??"(없음)";
    if(!groups.has(g)) groups.set(g,[]); groups.get(g).push(n);}
  const gs=[...groups.keys()].sort(), R=Math.max(260, nodes.length*3.2);
  gs.forEach((g,gi)=>{
    const cx=Math.cos(gi/gs.length*2*Math.PI)*R, cy=Math.sin(gi/gs.length*2*Math.PI)*R;
    const arr=groups.get(g), r=Math.max(70, arr.length*7);
    arr.forEach((n,i)=>{ if(fixed.has(n.id)) return;
      const a=i/arr.length*2*Math.PI;
      n.x=cx+Math.cos(a)*r; n.y=cy+Math.sin(a)*r;});
  });
  for(let it=0; it<160; it++) relax();   // 짧은 완화 — 결정적 반복 횟수
  fit();
}
function relax(){
  for(const e of edges){const a=byId.get(e.src),b=byId.get(e.dst);
    const dx=b.x-a.x, dy=b.y-a.y, d=Math.hypot(dx,dy)||1, f=(d-110)*0.012;
    if(!fixed.has(a.id)){a.x+=dx/d*f; a.y+=dy/d*f;}
    if(!fixed.has(b.id)){b.x-=dx/d*f; b.y-=dy/d*f;}}
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    const a=nodes[i],b=nodes[j],dx=b.x-a.x,dy=b.y-a.y,d2=dx*dx+dy*dy;
    if(d2>9000||d2===0) continue; const d=Math.sqrt(d2),f=(95-d)*0.03;
    if(!fixed.has(a.id)){a.x-=dx/d*f; a.y-=dy/d*f;}
    if(!fixed.has(b.id)){b.x+=dx/d*f; b.y+=dy/d*f;}}
}
function fit(){
  if(!nodes.length) return;
  const xs=nodes.map(n=>n.x), ys=nodes.map(n=>n.y);
  const w=Math.max(...xs)-Math.min(...xs)||1, h=Math.max(...ys)-Math.min(...ys)||1;
  view.k=Math.min(cv.width/(w+180), cv.height/(h+180), 2.2);
  view.x=cv.width/2-(Math.min(...xs)+w/2)*view.k;
  view.y=cv.height/2-(Math.min(...ys)+h/2)*view.k;
}
function resize(){cv.width=stage.clientWidth; cv.height=stage.clientHeight; draw();}
function P(n){return [n.x*view.k+view.x, n.y*view.k+view.y];}

function draw(){
  ctx.clearRect(0,0,cv.width,cv.height);
  for(const e of edges){
    const a=byId.get(e.src), b=byId.get(e.dst), [ax,ay]=P(a), [bx,by]=P(b);
    // **cross-layer 엣지는 걸러 그려도 화면에 남긴다**(문서 7 §7.8) — 층간 연결이
    // 이 시스템의 존재 이유이고, 그것을 눈으로 볼 창구가 여기다.
    ctx.strokeStyle = e.cross ? "#f7768ecc" : "#2a2f3a";
    ctx.lineWidth = e.cross ? 1.6 : 1;
    if(e.cross){ctx.setLineDash([5,3]);} else {ctx.setLineDash([]);}
    ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,by); ctx.stroke();
  }
  ctx.setLineDash([]);
  const deg = new Map();
  for(const e of edges){deg.set(e.src,(deg.get(e.src)||0)+1);
                        deg.set(e.dst,(deg.get(e.dst)||0)+1);}
  const taken = [];
  // 차수가 큰 노드를 먼저 그려 라벨 자리를 먼저 잡게 한다 — 허브가 이름을 갖는다.
  const order = [...nodes].sort((a,b)=>(deg.get(b.id)||0)-(deg.get(a.id)||0));
  for(const n of order){
    const [x,y]=P(n), r=(n.tier==="main"?9:n.tier==="sub"?7:5.5)*Math.min(view.k,1.6);
    ctx.fillStyle=color(n[COLOR_AX]??"(없음)");
    ctx.beginPath(); ctx.arc(x,y,r,0,7); ctx.fill();
    if(fixed.has(n.id)){ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();}
    // **라벨은 겹치면 읽을 수 없다** — 확대 전에는 골격 상위와 연결이 많은 노드만
    // 적는다(LOD). 그린 자리를 기록해 겹치는 라벨은 건너뛴다.
    const show = view.k > 1.15 || n.tier === "main" || n.tier === "sub"
                 || (deg.get(n.id) || 0) >= 4;
    if(show){
      const s = n.name.split("::").pop();
      ctx.font = "11px sans-serif";
      const w = ctx.measureText(s).width, ly = y - r - 5;
      const box = [x - w/2 - 2, ly - 10, w + 4, 13];
      if(!taken.some(b => box[0] < b[0]+b[2] && b[0] < box[0]+box[2]
                       && box[1] < b[1]+b[3] && b[1] < box[1]+box[3])){
        taken.push(box);
        ctx.fillStyle = "#0f1115d0";
        ctx.fillRect(box[0], box[1], box[2], box[3]);
        ctx.fillStyle = "#c0caf5"; ctx.textAlign = "center";
        ctx.fillText(s, x, ly);
      }
    }
  }
  const cross = edges.filter(e=>e.cross).length;
  document.getElementById("stat").innerHTML =
    `보이는 노드 <b>${nodes.length}</b> / ${DATA.nodes.length}<br>`+
    `보이는 엣지 <b>${edges.length}</b> / ${DATA.edges.length}<br>`+
    `그중 걸침(cross) <b style="color:#f7768e">${cross}</b><br>`+
    `색상 축: ${COLOR_AX}`;
}
function hit(mx,my){
  for(let i=nodes.length-1;i>=0;i--){const [x,y]=P(nodes[i]);
    if(Math.hypot(mx-x,my-y)<11) return nodes[i];}
  return null;
}
let drag=null;
cv.onmousedown=e=>{drag={x:e.offsetX,y:e.offsetY,vx:view.x,vy:view.y,moved:false};
  cv.classList.add("drag");};
cv.onmouseup=e=>{cv.classList.remove("drag");
  if(drag && !drag.moved){const n=hit(e.offsetX,e.offsetY);
    if(n){fixed.has(n.id)?fixed.delete(n.id):fixed.add(n.id); draw();}}
  drag=null;};
cv.onmouseleave=()=>{drag=null;cv.classList.remove("drag");tip.style.display="none";};
cv.onmousemove=e=>{
  if(drag){const dx=e.offsetX-drag.x, dy=e.offsetY-drag.y;
    if(Math.abs(dx)+Math.abs(dy)>3) drag.moved=true;
    view.x=drag.vx+dx; view.y=drag.vy+dy; draw(); return;}
  const n=hit(e.offsetX,e.offsetY);
  if(!n){tip.style.display="none"; return;}
  const deg=edges.filter(x=>x.src===n.id||x.dst===n.id).length;
  tip.innerHTML=`<b>${n.name}</b><br>`+
    AXES.map(a=>`<span class=k>${a}</span> ${n[a]??"—"}`).join("<br>")+
    `<br><span class=k>연결</span> ${deg}`+
    (n.prov?`<br><span class=k>출처</span> ${n.prov}`:"");
  tip.style.display="block";
  tip.style.left=Math.min(e.offsetX+14, stage.clientWidth-350)+"px";
  tip.style.top=(e.offsetY+14)+"px";
};
cv.onwheel=e=>{e.preventDefault(); const f=e.deltaY<0?1.12:1/1.12;
  view.x=e.offsetX-(e.offsetX-view.x)*f; view.y=e.offsetY-(e.offsetY-view.y)*f;
  view.k*=f; draw();};
window.onresize=resize;
resize(); layout(); draw();
</script>
"""


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
    out = Path(args[0]) if args else ROOT / "export" / "graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    world = _world()
    live = {i for g in world.values() for i, n in g.nodes.items() if is_live(n)}
    layer_of = {i: lay for lay, g in world.items() for i in g.nodes}

    nodes = []
    for lay, g in world.items():
        for n in g.nodes.values():                  # ① id-keyed dict → 배열
            if not is_live(n):
                continue
            nodes.append({
                "id": n["id"], "name": n["canonical"], "layer": lay,
                "category": n["category"], "status": n.get("status"),
                "tier": n.get("tier"), "polarity": n.get("polarity"),
                "prov": ", ".join((n.get("provenance") or [])[:4]),
            })

    edges = []
    for lay, g in world.items():
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            if e["src"] not in live or e["dst"] not in live:
                continue
            edges.append({                          # ② layer 주입 + cross 표시
                "src": e["src"], "dst": e["dst"], "rel": e["rel"], "layer": lay,
                "cross": layer_of.get(e["src"]) != layer_of.get(e["dst"]),
            })

    data = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    n_cross = sum(1 for e in edges if e["cross"])
    head = _HTML_HEAD.format(
        title="온톨로지 그래프",
        sub=f"노드 {len(nodes)} · 엣지 {len(edges)} · 걸침 {n_cross} · "
            f"층 {len(world)}")
    out.write_text(head + data + _HTML_TAIL, encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"[export] 노드 {len(nodes)} · 엣지 {len(edges)} "
          f"(걸침 {n_cross}) → {_short(out)}  [{size:.0f}KB]")
    print(f"  브라우저로 연다: file://{out}")
    print("  ※ 외부 CDN 없음 — 사내망·오프라인에서 그대로 열린다")
    print("  ※ 파생물이다 — 여기서 고친 것은 돌아오지 않는다(P5). 고치려면 run.py ops")
    return 0


# **진입점은 파일 끝이다.** 중간에 두면 그 아래 정의된 명령(cmd_html)이 `main()`의
# 디스패치 표를 만들 때 아직 없어 NameError로 죽는다 — import 경로는 파일을 끝까지
# 읽으므로 회귀가 이것을 못 잡았다(실측: `python -m cli.export html` → NameError).
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
