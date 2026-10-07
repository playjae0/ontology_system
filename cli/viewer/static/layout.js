/* 칸 5.3 — 뷰어 **배치** — 골격 + 위성 · 계층 · 힘 (B103 ①② · B84 ③).
 *
 * `render.js`에서 떼어냈다(B103 — 배치 셋이 한 파일이면 §7 상한을 넘는다). 셋 다 **결정적**이다 —
 * 난수 0 · 같은 입력이면 같은 그림(사람이 위치로 기억하고, 회귀가 좌표를 비교한다).
 *
 * 닻(골격 밖 노드가 붙은 골격 노드)은 **서버가 준다**(`/api/graph`의 `anchor` · `cli/viewer/anchor.py`) —
 * 화면은 그 사실을 자리로 옮길 뿐이다(PF11).
 */
"use strict";

/* 배치 셋 — 이름이 곧 선택 값이다(`localStorage`에 이 문자열이 남는다). */
const LAYOUTS = ["골격+위성", "계층", "힘"];
const LSTAT = { forceIter: 0, forceCut: false, forceMs: 0 };

/* ── ⓐ 골격 + 위성 ──────────────────────────────────────────────────────────
 * 골격(seed)은 `part_of` 나무로 층층이 — 잎 순서가 가로 자리, 깊이가 세로 자리. 위성은 그
 * host(닻 또는 앞 위성) 둘레의 고리에 — 고리 반경은 자식 덩어리의 크기에서 나온다(풍선 배치).
 * 골격 사이 간격은 각자 덩어리 반경의 합보다 넓다 → 위성은 늘 제 닻이 가장 가깝다. */
const SAT_GAP = 1.2, NODE_R = 0.6, SKEL_GAP = 2.0, ROW_GAP = 2.0;

function _byName(a, b) {
  return (a.category || "").localeCompare(b.category || "") || a.name.localeCompare(b.name)
    || a.id.localeCompare(b.id);
}

/** host 아래 덩어리 — 상대 좌표와 반경 (재귀 · 자식 순서는 카테고리 → 이름). */
function _balloon(id, kids, byId) {
  const ch = (kids[id] || []).map((k) => byId[k]).sort(_byName);
  if (!ch.length) return { r: NODE_R, rel: { [id]: [0, 0] } };
  const subs = ch.map((c) => ({ id: c.id, ..._balloon(c.id, kids, byId) }));
  const arc = subs.reduce((s, b) => s + 2 * b.r + SAT_GAP, 0);
  const R = Math.max(NODE_R + SAT_GAP + subs[0].r, arc / (2 * Math.PI));
  const rel = { [id]: [0, 0] };
  let acc = 0, rmax = 0;
  subs.forEach((b) => {
    const w = 2 * b.r + SAT_GAP;
    const ang = -Math.PI / 2 + ((acc + w / 2) / arc) * 2 * Math.PI;
    acc += w;
    const cx = R * Math.cos(ang), cy = R * Math.sin(ang);
    Object.entries(b.rel).forEach(([k, p]) => { rel[k] = [cx + p[0], cy + p[1]]; });
    rmax = Math.max(rmax, R + b.r);
  });
  return { r: rmax, rel };
}

function layoutSkel(nodes, edges, anchor) {
  const byId = {};
  nodes.forEach((n) => { byId[n.id] = n; });
  const sk = nodes.filter((n) => n.status === "seed");
  const skSet = new Set(sk.map((n) => n.id));
  // 골격 나무 — 골격 사이 `part_of`(자식 → 부모)
  const parent = {};
  edges.forEach((e) => {
    if (e.rel === "part_of" && skSet.has(e.src) && skSet.has(e.dst) && !(e.src in parent))
      parent[e.src] = e.dst;
  });
  const tkids = {};
  sk.forEach((n) => { const p = parent[n.id]; if (p) (tkids[p] = tkids[p] || []).push(n.id); });
  // 위성 — host 아래 자식(서버가 준 닻 사실 그대로)
  // host가 지금 안 보이면(탐색 모드) 보이는 가장 가까운 앞 노드로 — 닻까지 다 안 보이면 놓지 않는다(띠로)
  const kids = {};
  nodes.forEach((n) => {
    let a = anchor[n.id], h = a && a.host, guard = 0;
    while (a && h !== n.id && h && !byId[h] && guard++ < 64) h = (anchor[h] || {}).host;
    if (a && h && h !== n.id && byId[h]) (kids[h] = kids[h] || []).push(n.id);
  });
  const ball = {};
  sk.forEach((n) => { ball[n.id] = _balloon(n.id, kids, byId); });
  // 깊이별 줄 높이 = 그 깊이 덩어리 반경의 최대
  const depth = {};
  const dep = (id, seen = new Set()) => {
    if (id in depth) return depth[id];
    if (seen.has(id) || !parent[id]) return (depth[id] = 0);
    seen.add(id);
    return (depth[id] = dep(parent[id], seen) + 1);
  };
  sk.forEach((n) => dep(n.id));
  // 줄 사이 = 두 줄 덩어리 반경 최대의 두 배 + 틈 — 위성은 아래·위 줄의 골격보다 제 닻이 가깝다
  const rowR = {};
  sk.forEach((n) => { const d = depth[n.id]; rowR[d] = Math.max(rowR[d] || 0, ball[n.id].r); });
  const rowY = {};
  let y = 0;
  Object.keys(rowR).map(Number).sort((a, b) => a - b).forEach((d, i) => {
    if (i) y -= 2 * Math.max(rowR[d - 1] || 0, rowR[d]) + ROW_GAP;
    rowY[d] = y;
  });
  // 가로 자리 — 잎 순서 · 부모는 자식들의 가운데 · **같은 줄 이웃 사이 ≥ 2·max(r) + 틈**
  // (덩어리 반경 r 안의 위성이 이웃 골격보다 제 닻에 가깝다 — 완료판정 ⓐ의 성질)
  const xs = {}, last = {};
  const room = (id, x) => {
    const d = depth[id], p = last[d];
    return p ? Math.max(x, p.x + 2 * Math.max(p.r, ball[id].r) + SKEL_GAP) : x;
  };
  const shift = (id, dx) => {
    xs[id] += dx;
    const p = last[depth[id]];
    if (p && p.id === id) p.x = xs[id];
    (tkids[id] || []).forEach((k) => shift(k, dx));
  };
  const place = (id) => {
    const ch = (tkids[id] || []).map((k) => byId[k]).sort((a, b) => a.name.localeCompare(b.name));
    if (!ch.length) {
      xs[id] = room(id, 0);
    } else {
      ch.forEach((c) => place(c.id));
      const mid = (xs[ch[0].id] + xs[ch[ch.length - 1].id]) / 2;
      const want = room(id, mid);
      if (want > mid) ch.forEach((c) => shift(c.id, want - mid));   // 부모 자리가 모자라면 자식째 민다
      xs[id] = want;
    }
    last[depth[id]] = { id, x: xs[id], r: ball[id].r };
  };
  sk.filter((n) => !parent[n.id]).sort((a, b) => a.name.localeCompare(b.name)).forEach((r) => place(r.id));
  const pos = {};
  sk.forEach((n) => {
    const cx = xs[n.id], cy = rowY[depth[n.id]];
    Object.entries(ball[n.id].rel).forEach(([k, p]) => { pos[k] = { x: cx + p[0], y: cy + p[1] }; });
  });
  return pos;
}

/** 닻 없는 노드의 띠 — 나무 아래 격자(카테고리 → 이름 순). */
function bandBelow(pos, list) {
  const ys = Object.values(pos).map((p) => p.y);
  const xs = Object.values(pos).map((p) => p.x);
  const y0 = (ys.length ? Math.min(...ys) : 0) - 4, x0 = xs.length ? Math.min(...xs) : 0;
  const per = Math.max(8, Math.ceil(Math.sqrt(list.length) * 2));
  list.slice().sort(_byName).forEach((n, i) => {
    pos[n.id] = { x: x0 + (i % per) * 1.6, y: y0 - Math.floor(i / per) * 1.6 };
  });
  return pos;
}

/* ── ⓑ 계층 — `part_of` 깊이별 줄 (B84 그대로) ──────────────────────────── */
function layoutHier(nodes, edges) {
  const parent = {};
  edges.forEach((e) => { if (e.rel === "part_of") parent[e.src] = e.dst; });
  const depth = (id, seen = new Set()) => {
    let d = 0, cur = id;
    while (parent[cur] && !seen.has(cur)) { seen.add(cur); cur = parent[cur]; d++; }
    return d;
  };
  const rows = {};
  nodes.forEach((n) => { const d = depth(n.id); (rows[d] = rows[d] || []).push(n); });
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
    y += Math.ceil(list.length / per) + 1.4;
  });
  return pos;
}

/* ── ⓒ 힘 — 연결 덩어리마다 따로 · Barnes–Hut · 겹치지 않게 붙인다 (B103 ②) ──────
 *
 * 구판(B84 ③)은 전체를 한 판에 놓고 O(N²) 반발 + 중심 중력이라 엣지 없는 점·작은 덩어리가 원판·고리로
 * 몰렸고, 반복을 노드 수로 줄였다(900 초과면 40회). 지금: ①덩어리(연결 성분)마다 따로 돌린다(중력은
 * 덩어리 중심으로) ②반발은 Barnes–Hut 사분 나무(θ 0.9 · O(N log N)) ③반복은 **고정 ITER**이고 **시간 예산**은
 * 안전 상한이다 — 예산 안이면 같은 입력 같은 좌표 · 예산에 걸리면 그 사실을 머리 줄이 말한다(결정성을
 * 잃는 유일한 경우를 숨기지 않는다) ④덩어리를 크기 순으로 줄에 붙인다(경계 상자 겹침 0). */
const FORCE_ITER = 300, FORCE_BUDGET_MS = 4000, THETA = 0.9;
const REP = 1.2, SPRING = 0.06, GRAV = 0.02, MAXSTEP = 1.2, PACK_GAP = 4;

function _components(nodes, edges) {
  const at = new Map(nodes.map((n, i) => [n.id, i]));
  const up = nodes.map((_, i) => i);
  const find = (i) => { while (up[i] !== i) { up[i] = up[up[i]]; i = up[i]; } return i; };
  edges.forEach((e) => {
    const a = at.get(e.src), b = at.get(e.dst);
    if (a === undefined || b === undefined) return;
    const ra = find(a), rb = find(b);
    if (ra !== rb) up[Math.max(ra, rb)] = Math.min(ra, rb);
  });
  const groups = {};
  nodes.forEach((n, i) => { const r = find(i); (groups[r] = groups[r] || []).push(n); });
  return Object.values(groups).sort((a, b) => b.length - a.length || a[0].id.localeCompare(b[0].id));
}

/** 사분 나무 반발 — 각 점에 대해 멀리 있는 칸은 질량 중심 하나로 본다(θ). 난수 0. */
function _repulse(x, y, w, fx, fy) {
  const N = x.length;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < N; i++) {
    x0 = Math.min(x0, x[i]); y0 = Math.min(y0, y[i]); x1 = Math.max(x1, x[i]); y1 = Math.max(y1, y[i]);
  }
  const cell = (cx0, cy0, s) => ({ x0: cx0, y0: cy0, s, m: 0, cx: 0, cy: 0, body: -1, kids: null });
  const root = cell(x0, y0, Math.max(x1 - x0, y1 - y0, 1e-3));
  const add = (c, i) => {
    const m = c.m + w[i];
    c.cx = (c.cx * c.m + x[i] * w[i]) / m; c.cy = (c.cy * c.m + y[i] * w[i]) / m; c.m = m;
  };
  const child = (c, i) => c.kids[(x[i] >= c.x0 + c.s / 2 ? 1 : 0) + (y[i] >= c.y0 + c.s / 2 ? 2 : 0)];
  const insert = (c, i, d) => {
    if (c.kids === null) {
      if (c.m === 0) { c.body = i; add(c, i); return; }
      if (d > 40) { add(c, i); c.body = -2; return; }        // 같은 자리에 쌓인 점 — 한 칸에 모은다
      const h = c.s / 2;
      c.kids = [0, 1, 2, 3].map((q) => cell(c.x0 + (q & 1) * h, c.y0 + (q >> 1) * h, h));
      const j = c.body; c.body = -1;
      if (j >= 0) insert(child(c, j), j, d + 1);              // 질량은 이미 c에 있다
    }
    add(c, i);
    insert(child(c, i), i, d + 1);
  };
  for (let i = 0; i < N; i++) insert(root, i, 0);
  const walk = (c, i) => {
    if (c.m === 0 || (c.kids === null && c.body === i)) return;
    let dx = x[i] - c.cx, dy = y[i] - c.cy;
    let d2 = dx * dx + dy * dy;
    if (c.kids !== null && (c.s * c.s) >= THETA * THETA * d2) { c.kids.forEach((k) => walk(k, i)); return; }
    if (d2 < 1e-6) { dx = ((i % 7) - 3) * 1e-3 + 1e-4; dy = ((i % 5) - 2) * 1e-3 + 1e-4; d2 = dx * dx + dy * dy; }
    const f = REP * w[i] * c.m / d2;
    fx[i] += dx * f; fy[i] += dy * f;
  };
  for (let i = 0; i < N; i++) walk(root, i);
}

function _forceOne(nodes, edges, seed, deadline) {
  const N = nodes.length;
  const at = new Map(nodes.map((n, i) => [n.id, i]));
  const x = new Float64Array(N), y = new Float64Array(N), w = new Float64Array(N);
  let mx = 0, my = 0;
  nodes.forEach((n, i) => { const p = seed[n.id] || { x: i, y: 0 }; x[i] = p.x; y[i] = p.y; mx += p.x / N; my += p.y / N; });
  let rmax = 0;
  for (let i = 0; i < N; i++) { x[i] -= mx; y[i] -= my; rmax = Math.max(rmax, Math.hypot(x[i], y[i])); }
  const k = rmax > 0 ? (2 + Math.sqrt(N) * 2) / rmax : 1;   // 초기 크기는 덩어리 크기에 맞춘다
  for (let i = 0; i < N; i++) { x[i] *= k; y[i] *= k; }
  const E = [];
  edges.forEach((e) => {
    const a = at.get(e.src), b = at.get(e.dst);
    if (a === undefined || b === undefined || a === b) return;
    E.push([a, b]); w[a] += 1; w[b] += 1;
  });
  for (let i = 0; i < N; i++) w[i] += 1;
  const fx = new Float64Array(N), fy = new Float64Array(N);
  let it = 0;
  for (; it < FORCE_ITER && N > 1; it++) {
    if (performance.now() > deadline) { LSTAT.forceCut = true; break; }
    fx.fill(0); fy.fill(0);
    _repulse(x, y, w, fx, fy);
    for (const [a, b] of E) {
      const dx = x[b] - x[a], dy = y[b] - y[a];
      fx[a] += dx * SPRING; fy[a] += dy * SPRING;
      fx[b] -= dx * SPRING; fy[b] -= dy * SPRING;
    }
    const cool = 1 - it / (FORCE_ITER + 1);
    for (let i = 0; i < N; i++) {
      fx[i] -= x[i] * GRAV; fy[i] -= y[i] * GRAV;
      const len = Math.hypot(fx[i], fy[i]) || 1;
      const step = Math.min(len, MAXSTEP) * cool;
      x[i] += (fx[i] / len) * step; y[i] += (fy[i] / len) * step;
    }
  }
  LSTAT.forceIter = Math.max(LSTAT.forceIter, it);
  const pos = {};
  nodes.forEach((n, i) => { pos[n.id] = { x: x[i], y: y[i] }; });
  return pos;
}

function layoutForce(nodes, edges, seed) {
  const t0 = performance.now();
  LSTAT.forceIter = 0; LSTAT.forceCut = false;
  const deadline = t0 + FORCE_BUDGET_MS;
  const comps = _components(nodes, edges);
  const ids = new Set(nodes.map((n) => n.id));
  const es = edges.filter((e) => ids.has(e.src) && ids.has(e.dst));
  const placed = comps.map((c) => {
    const cs = new Set(c.map((n) => n.id));
    const p = _forceOne(c, es.filter((e) => cs.has(e.src)), seed, deadline);
    const v = Object.values(p);
    const b = { x0: Math.min(...v.map((q) => q.x)), y0: Math.min(...v.map((q) => q.y)),
                x1: Math.max(...v.map((q) => q.x)), y1: Math.max(...v.map((q) => q.y)) };
    return { p, b, w: b.x1 - b.x0 + 2 * NODE_R, h: b.y1 - b.y0 + 2 * NODE_R };
  });
  // 줄 붙이기 — 큰 덩어리부터 왼쪽 → 오른쪽 · 줄 폭은 넓이 합의 제곱근 배
  const area = placed.reduce((s, c) => s + (c.w + PACK_GAP) * (c.h + PACK_GAP), 0);
  const rowW = Math.max(Math.sqrt(area) * 1.4, placed.length ? placed[0].w : 0);
  const pos = {};
  let cx = 0, cy = 0, rowH = 0;
  placed.forEach((c) => {
    if (cx > 0 && cx + c.w > rowW) { cx = 0; cy -= rowH + PACK_GAP; rowH = 0; }
    Object.entries(c.p).forEach(([id, q]) => {
      pos[id] = { x: cx + (q.x - c.b.x0) + NODE_R, y: cy - (c.b.y1 - q.y) - NODE_R };
    });
    cx += c.w + PACK_GAP; rowH = Math.max(rowH, c.h);
  });
  LSTAT.forceMs = Math.round(performance.now() - t0);
  return pos;
}
