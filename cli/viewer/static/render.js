/* 칸 5.2 — 뷰어 **렌더러**: 색·좌표 배치 둘 · 리듀서 · 상호작용 (B82 ② · B84 ①②③④).
 *
 * `app.js` 351행을 셋으로 가른 것 중 하나다(B84 — §7 상한). 가르는 선은
 * **「그림」과 「상태·배선」과 「질의」**다: 여기는 받은 데이터를 어떻게 그리는가만 안다.
 *
 * 두 자리로 갈라 둔다(B84 ②):
 *   · `rebuild()`  — 그래프를 다시 만든다(데이터·배치가 바뀔 때만)
 *   · `restyle()`  — 리듀서만 다시 돌린다(검색·강조·필터·테마 — 좌표를 건드리지 않는다)
 * 검색은 글자마다 `restyle()`이다 — 구판은 `draw()`가 레이아웃을 다시 계산하고
 * sigma를 죽였다 죽여 다시 만들었다(사내 실측: 「글자를 칠 때마다 화면이 돈다」).
 *
 * **계측을 남긴다**(`RSTAT`) — 「검색 중 배치 0회 · sigma 생성 1회」를 시험이 수로 잰다.
 * 주석이 아니라 실행이 판정한다.
 */
"use strict";

/* 값 → 색: **결정적**이다(같은 값이면 어느 실행에서나 같은 색).
 *
 * **16진으로 낸다**(B84 ①): 벤더링한 렌더러의 색 파서가 `hsl()`을 읽지 못해 WebGL에서
 * 전부 검정으로 떨어졌다(브라우저 실측 — 범례만 색이 있고 점은 까맸다). 계산은 그대로다.
 */
function hslHex(h, s, l) {
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(255 * c).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function colorOf(v) {
  const s = String(v == null ? "—" : v);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return hslHex(h, 0.62, 0.48);
}
const AXES = ["layer", "category", "status", "tier", "polarity", "made_by"];
const axisValue = (n, ax) => (n[ax] == null || n[ax] === "" ? "—" : String(n[ax]));

/* 배치 두 종 — 이름이 곧 선택 값이다(`localStorage`에 이 문자열이 남는다). */
const LAYOUTS = ["계층", "힘"];

/* 테마 색은 **CSS 변수 하나가 정본**이다 — sigma에 넘길 때도 거기서 읽는다(B84 ①).
 * 라벨 색을 코드에 박으면 테마를 바꿀 때 라벨만 남는다(사내 실측: 어두운 배경 + 검정
 * 라벨 = 글씨가 안 보인다). */
const cssVar = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/* 계측 — 시험이 센다(B84 ② 완료판정). */
const RSTAT = { layout: 0, sigma: 0, rebuild: 0, restyle: 0 };

/* ── 배치 ⓐ 계층 좌표 — `part_of` 트리·층·tier·부모 순 (결정적) ─────────── */
function layoutHier(nodes, edges) {
  const parent = {};
  edges.forEach((e) => { if (e.rel === "part_of") parent[e.src] = e.dst; });
  const depth = (id, seen = new Set()) => {
    let d = 0, cur = id;
    while (parent[cur] && !seen.has(cur)) { seen.add(cur); cur = parent[cur]; d++; }
    return d;
  };
  const rows = {};
  nodes.forEach((n) => {
    const d = depth(n.id);
    (rows[d] = rows[d] || []).push(n);
  });
  // 한 층(깊이)이 길면 **접어서** 둔다 — 한 줄로 늘어놓으면 화면이 가로 띠가 된다.
  const pos = {};
  let y = 0;
  Object.keys(rows).sort((a, b) => a - b).forEach((d) => {
    const list = rows[d].sort((a, b) =>
      (a.layer + a.category + a.name).localeCompare(b.layer + b.category + b.name));
    const per = Math.max(6, Math.ceil(Math.sqrt(list.length) * 2));
    list.forEach((n, i) => {
      const col = i % per, line = Math.floor(i / per);
      pos[n.id] = { x: (col - per / 2) * 1.6, y: -(y + line) * 1.6 };
    });
    y += Math.ceil(list.length / per) + 1.4;          // 깊이 사이에 한 줄 띄운다
  });
  return pos;
}

/* ── 배치 ⓑ 힘 배치 — **난수 0 · 고정 반복** (B84 ③) ───────────────────────
 *
 * 직접 짰다(D-165 ①): `graphology-layout-forceatlas2`는 npm 배포에 브라우저 번들이
 * 없고(CommonJS `index.js` + `graphology-utils` 요구) 번들러를 들이지 않고는
 * `<script>`로 못 싣는다 — 요청문이 준 대안이다.
 *
 * 결정적이어야 하는 이유는 계층 좌표와 같다: 사람이 **위치로 기억**하고, 회귀가
 * 좌표를 비교한다. 그래서 난수를 한 번도 쓰지 않는다 — 겹친 점은 **지표(index)로**
 * 가른다. 초기값은 계층 좌표다(같은 그림에서 출발한다).
 */
function layoutForce(nodes, edges, seed) {
  const N = nodes.length;
  if (!N) return {};
  const at = new Map(nodes.map((n, i) => [n.id, i]));
  const x = new Float64Array(N), y = new Float64Array(N);
  // 초기값(계층 좌표)을 **같은 크기로 줄여** 넣는다 — 그래프가 크면 계층 좌표가 이미
  // 넓어서, 그 위에서 밀어내면 점들이 가장자리 띠로만 몰린다(실측).
  let rmax = 0;
  nodes.forEach((n) => {
    const p = seed[n.id] || { x: 0, y: 0 };
    rmax = Math.max(rmax, Math.hypot(p.x, p.y));
  });
  const k = rmax > 0 ? 20 / rmax : 1;
  nodes.forEach((n, i) => {
    const p = seed[n.id] || { x: 0, y: 0 };
    x[i] = p.x * k; y[i] = p.y * k;
  });
  const deg = new Float64Array(N);
  const E = [];
  edges.forEach((e) => {
    const a = at.get(e.src), b = at.get(e.dst);
    if (a === undefined || b === undefined || a === b) return;
    E.push([a, b]); deg[a] += 1; deg[b] += 1;
  });
  // 반발이 O(N²)라 큰 그래프에서는 **반복을 줄인다**(끝나지 않는 화면을 만들지 않는다).
  const ITER = N <= 300 ? 300 : N <= 900 ? 120 : 40;
  // 상수는 **표본에서 골랐다**(B84 ③ — 99노드·149엣지 mock 그래프): 반경 25%/50%/최대
  // 67/103/179 · 엣지 길이 평균 42 · 점 사이 최소 간격 6.7(겹침 0).
  const REP = 1.2, SPRING = 0.06, GRAV = 0.06, MAXSTEP = 1.2;
  const fx = new Float64Array(N), fy = new Float64Array(N);
  for (let it = 0; it < ITER; it++) {
    fx.fill(0); fy.fill(0);
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        let dx = x[i] - x[j], dy = y[i] - y[j];
        let d2 = dx * dx + dy * dy;
        if (d2 < 1e-6) {                 // 겹친 점 — **난수 대신 지표로** 가른다
          dx = (i - j) * 1e-3; dy = (i + j) * 1e-3; d2 = dx * dx + dy * dy;
        }
        const f = REP * (deg[i] + 1) * (deg[j] + 1) / d2;
        fx[i] += dx * f; fy[i] += dy * f;
        fx[j] -= dx * f; fy[j] -= dy * f;
      }
    }
    for (const [a, b] of E) {
      const dx = x[b] - x[a], dy = y[b] - y[a];
      fx[a] += dx * SPRING; fy[a] += dy * SPRING;
      fx[b] -= dx * SPRING; fy[b] -= dy * SPRING;
    }
    const cool = 1 - it / (ITER + 1);              // 식힌다 — 끝에서 흔들리지 않게
    for (let i = 0; i < N; i++) {
      fx[i] -= x[i] * GRAV; fy[i] -= y[i] * GRAV;
      const len = Math.hypot(fx[i], fy[i]) || 1;
      const step = Math.min(len, MAXSTEP) * cool;
      x[i] += (fx[i] / len) * step;
      y[i] += (fy[i] / len) * step;
    }
  }
  const pos = {};
  nodes.forEach((n, i) => { pos[n.id] = { x: x[i], y: y[i] }; });
  return pos;
}

function positions(nodes, edges, kind) {
  RSTAT.layout += 1;
  const hier = layoutHier(nodes, edges);
  const pos = kind === "힘" ? layoutForce(nodes, edges, hier) : hier;
  // **사람이 옮긴 점은 그 자리에 남는다**(B84 ③④ — 그 세션 동안).
  Object.entries(S.pinned || {}).forEach(([id, p]) => { if (pos[id]) pos[id] = p; });
  return pos;
}

/* ── 보이는 것 · 검색에 걸리는 것 — **판정은 한 자리** ────────────────────── */
function passes(n) {
  if (!S.obsolete && n.status === "obsolete") return false;
  for (const [ax, keep] of Object.entries(S.filters))
    if (keep.size && !keep.has(axisValue(n, ax))) return false;
  return true;
}

/** 검색 술어 — **이름·id**다(별칭 문자열은 `/api/graph`에 없다 · D-165 ③). */
function searchHit(n, q) {
  if (!q) return false;
  return String(n.name).toLowerCase().includes(q)
    || String(n.id).toLowerCase() === q;
}

function edgeShown(e) {
  return (e.cross && S.alwaysCross) || S.rels.has(e.rel);
}

/* ── 크기·색 — tier가 크기를 정한다(B84 ①) ───────────────────────────────── */
const TIER_SIZE = { main: 8, sub: 6, detail: 4 };
const sizeOf = (n) => TIER_SIZE[n.tier] || 5;

function nodeColor(n) {
  const hi = (S.highlight.nodes || {})[n.id];
  if (hi === "link") return cssVar("--hi");
  if (hi === "reach") return cssVar("--hi2");
  return colorOf(axisValue(n, S.axis));
}

/* ── 리듀서 — 검색·강조·hover·필터는 **여기서만** 갈린다 (B84 ②④) ───────── */
function nodeReducer(id, attrs) {
  const n = attrs._node;
  const res = { ...attrs, size: sizeOf(n), color: nodeColor(n), zIndex: 1 };
  if (!passes(n)) { res.hidden = true; return res; }
  const q = (S.search || "").trim().toLowerCase();
  if (q) {
    if (searchHit(n, q)) { res.size = sizeOf(n) + 4; res.zIndex = 3; res.highlighted = true; }
    else { res.color = cssVar("--faint"); res.label = ""; }
  }
  if (S.hover) {
    if (id === S.hover) { res.zIndex = 4; res.highlighted = true; }
    else if (!(S.neighbors || new Set()).has(id)) { res.color = cssVar("--faint"); res.label = ""; }
  }
  if ((S.highlight.nodes || {})[n.id]) { res.size = Math.max(res.size, 9); res.zIndex = 3; }
  return res;
}

function edgeReducer(key, attrs) {
  const e = attrs._edge;
  const res = { ...attrs };
  if (!edgeShown(e) || !passes(e._src) || !passes(e._dst)) { res.hidden = true; return res; }
  const onPath = S.pathKeys && S.pathKeys.has(`${e.src}|${e.rel}|${e.dst}`);
  res.color = onPath ? cssVar("--hi") : e.cross ? cssVar("--cross") : cssVar("--line");
  res.size = onPath ? 3 : 1;
  if (S.hover && !(e.src === S.hover || e.dst === S.hover)) res.color = cssVar("--faint");
  return res;
}

/* ── 그래프를 다시 만든다 — 데이터·배치가 바뀔 때만 (B84 ②) ───────────────── */
function rebuild() {
  const wrap = $("#canvas");
  $("#webgl-warn").hidden = true;       // 그릴 수 있으면 경고는 없다
  if (!window.Sigma || !window.graphology) { $("#webgl-warn").hidden = false; return; }
  RSTAT.rebuild += 1;
  const R0 = window.Sigma.rendering || {};
  // 테두리 프로그램이 **있을 때만** seed에 테두리를 준다 — 없는 프로그램 이름을
  // 노드에 달면 sigma가 그리다 죽는다(B82의 「dashed」와 같은 사고).
  const hasBorder = !!(R0.createNodeBorderProgram && R0.NodeCircleProgram);
  const G = window.graphology.MultiDirectedGraph || window.graphology.Graph;
  const nodes = S.graph.nodes, edges = S.graph.edges;
  const pos = positions(nodes, edges, S.layout);
  S.pos = pos;
  const g = S.gr && S.sigma ? S.gr : new G();
  g.clear();
  const byId = {};
  nodes.forEach((n) => { byId[n.id] = n; });
  nodes.forEach((n) => {
    g.addNode(n.id, {
      label: n.name, size: sizeOf(n), color: colorOf(axisValue(n, S.axis)),
      x: pos[n.id] ? pos[n.id].x : 0, y: pos[n.id] ? pos[n.id].y : 0,
      // seed(골격)는 **테두리**로 가른다 — 크기는 tier가 쓴다(B84 ①).
      type: hasBorder ? (n.status === "seed" ? "bordered" : "circle") : undefined,
      borderColor: cssVar("--fg"),
      zIndex: 1, _node: n,
    });
  });
  edges.forEach((e) => {
    if (!g.hasNode(e.src) || !g.hasNode(e.dst)) return;
    // **걸침은 곡선 + 별색**이다(B82 ②). 벤더링한 렌더러에 점선 프로그램이 없다 —
    // 없는 것을 있다고 부르면 화면이 통째로 죽는다(실측).
    g.addEdge(e.src, e.dst, {
      label: e.rel, size: 1, type: e.cross ? "curve" : "line",
      color: cssVar("--line"),
      _edge: { ...e, _src: byId[e.src], _dst: byId[e.dst] },
    });
  });
  S.gr = g;
  if (!S.sigma) {
    // **sigma는 한 번만 만든다**(B84 ②) — 구판은 그릴 때마다 kill+new였다.
    try {
      const R = R0;
      RSTAT.sigma += 1;
      S.sigma = new (window.Sigma.Sigma || window.Sigma)(g, wrap, {
        renderEdgeLabels: true, defaultEdgeType: "line", labelDensity: 0.6,
        nodeReducer, edgeReducer,
        nodeProgramClasses: nodePrograms(R),
        edgeProgramClasses: R.EdgeCurveProgram ? { curve: R.EdgeCurveProgram } : undefined,
      });
    } catch (err) {                   // WebGL이 없거나 렌더러가 깨졌다 — 숨기지 않는다
      console.error("render 실패:", err);
      $("#webgl-warn").hidden = false;
      $("#webgl-warn").textContent = "그래프를 그리지 못했다 — " + err;
      S.sigma = null;
      return;
    }
    interactions();
  }
  theme_apply_sigma();
  restyle();
}

/** seed 테두리 프로그램 — **있는 것만 쓴다**(없으면 기본 원으로 떨어진다). */
function nodePrograms(R) {
  const circle = R.NodeCircleProgram, make = R.createNodeBorderProgram;
  if (!circle || !make) return undefined;
  const bordered = make({
    borders: [{ color: { attribute: "borderColor", defaultValue: "#000000" }, size: { value: 0.18 } },
              { color: { attribute: "color" }, size: { fill: true } }],
  });
  return { circle, bordered };
}

/* ── 리듀서만 다시 — 검색·강조·테마·필터 (좌표 0 · 생성 0) ────────────────── */
function restyle() {
  if (!S.sigma) return;
  RSTAT.restyle += 1;
  S.sigma.refresh({ skipIndexation: true });
}

/** sigma에 넘기는 **색은 CSS 변수에서 읽는다**(B84 ①) — 테마를 바꾸면 라벨도 따라간다. */
function theme_apply_sigma() {
  if (!S.sigma) return;
  S.sigma.setSetting("labelColor", { color: cssVar("--fg") });
  S.sigma.setSetting("edgeLabelColor", { color: cssVar("--dim") });
  S.sigma.setSetting("defaultEdgeColor", cssVar("--line"));
  S.sigma.setSetting("defaultNodeColor", cssVar("--dim"));
  restyle();
}

/* ── 상호작용 — 드래그 · hover · 더블클릭 (B84 ④ · 서버 요청 0) ───────────── */
function neighborsOf(id) {
  const set = new Set([id]);
  S.graph.edges.forEach((e) => {
    if (e.src === id) set.add(e.dst);
    if (e.dst === id) set.add(e.src);
  });
  return set;
}

function interactions() {
  const sg = S.sigma, g = S.gr;
  sg.on("clickNode", ({ node }) => detail(g.getNodeAttribute(node, "_node")));
  sg.on("enterNode", ({ node }) => {
    S.hover = node; S.neighbors = neighborsOf(node); restyle();
  });
  sg.on("leaveNode", () => { S.hover = null; S.neighbors = null; restyle(); });
  sg.on("doubleClickNode", (e) => {
    // 초점 — 카메라를 **그 점의 자리로** 옮긴다. 좌표계는 sigma가 그리는 자리
    // (`getNodeDisplayData`)이고 카메라가 쓰는 것과 같다 — 그래프 좌표를 그대로
    // 넣으면 엉뚱한 곳으로 간다(실측). 기본 더블클릭 확대는 막는다(둘이 싸운다).
    const node = e.node;
    const d = sg.getNodeDisplayData(node) || { x: 0.5, y: 0.5 };
    if (e.preventSigmaDefault) e.preventSigmaDefault();
    sg.getCamera().animate({ x: d.x, y: d.y, ratio: 0.35 }, { duration: 250 });
    S.focus = { node, x: d.x, y: d.y };
    detail(g.getNodeAttribute(node, "_node"));
  });
  // 드래그 — 잡은 동안 카메라를 잠근다(안 잠그면 화면이 함께 끌린다).
  sg.on("downNode", ({ node }) => {
    S.drag = node;
    g.setNodeAttribute(node, "highlighted", true);
  });
  const mouse = sg.getMouseCaptor();
  mouse.on("mousemovebody", (e) => {
    if (!S.drag) return;
    const p = sg.viewportToGraph(e);
    g.setNodeAttribute(S.drag, "x", p.x);
    g.setNodeAttribute(S.drag, "y", p.y);
    S.pinned[S.drag] = { x: p.x, y: p.y };     // 그 세션 동안 그 자리
    e.preventSigmaDefault();
    e.original.preventDefault();
    e.original.stopPropagation();
  });
  const drop = () => {
    if (!S.drag) return;
    g.setNodeAttribute(S.drag, "highlighted", false);
    S.drag = null;
  };
  mouse.on("mouseup", drop);
  mouse.on("mouseleave", drop);
}
