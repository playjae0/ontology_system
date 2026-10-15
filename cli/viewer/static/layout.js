/* 칸 5.3 — 뷰어 **배치** — 골격 + 위성 · 계층 · 힘 (B103 ①② · B84 ③ · 힘은 웹 워커 — B114 ①).
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
const LSTAT = { forceIter: 0, forceMax: 0, forceState: "", forceMs: 0, frames: 0 };

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

/* ── ⓒ 힘 — 웹 워커(`force_worker.js` — ForceAtlas2 계열 · Barnes–Hut) · 위치를 이어서 받는다 (B114 ①) ──
 *
 * 구판(B103 ②)은 화면 스레드에서 덩어리마다 돌리고 **시간 예산(4초)에서 끊었다** — 큰 그래프는 초기 배치(원)에
 * 가까운 채 굳었다. 지금: 시드(골격+위성 자리 · 닻 없는 노드는 그 아래 띠 — 결정적)를 워커에 넘기고, 워커가 반복
 * `FORCE_ITER`까지 돌며 `frameEvery` 반복마다 좌표를 보낸다 → 렌더러가 그 자리로 옮긴다(화면이 멈추지 않는다 ·
 * 시간으로 끊지 않는다). 같은 시드 · 같은 반복 수면 같은 좌표다(난수 0 · 걸음은 반복 수로 센다). 「멈춤」은 워커를
 * 세우고 「이어서」는 그 자리에서 잇고 「다시 배치」는 시드부터 다시. 떨어진 덩어리는 중력이 붙잡는다(한 판에). */
const FORCE_ITER = 1500;                       // 기본 — 서버가 손잡이 `viewer_force`를 주면 그것(`/api/graph`의 `force`)
const FORCE_CFG = { scaling: 2, gravity: 1, theta: 1.2, jitter: 1, frameEvery: 10 };
const FORCE = { worker: null, ids: [], at: new Map(), paused: false };

/** 힘 배치의 **시드** — 닻이 있는 노드는 골격+위성 자리 · 없는 노드는 그 아래 띠(같은 입력 같은 시드). */
function layoutForce(nodes, edges, anchor) {
  const on = nodes.filter((n) => anchor[n.id]), off = nodes.filter((n) => !anchor[n.id]);
  return bandBelow(layoutSkel(on, edges, anchor), off);
}

/** 워커를 띄운다 — `onFrame(frame, ids)`가 프레임마다 불린다(`frame.x[i]`·`frame.y[i]`는 `ids[i]`의 자리).
 * `opts` — `fixed`(고정할 점 `{id: …}`) · `scaling` · `gravity` · `iterations`(없으면 기본값). */
function forceStart(nodes, edges, seed, onFrame, opts = {}) {
  const fixed = opts.fixed || {}, maxIter = opts.iterations || FORCE_ITER;
  forceStop();
  const ids = nodes.map((n) => n.id);
  const at = new Map(ids.map((id, i) => [id, i]));
  const mass = ids.map(() => 1), E = [];
  edges.forEach((e) => {
    const a = at.get(e.src), b = at.get(e.dst);
    if (a === undefined || b === undefined || a === b) return;
    E.push([a, b]); mass[a] += 1; mass[b] += 1;                 // 질량 = 연결 수 + 1 (ForceAtlas2)
  });
  const w = new Worker("/static/force_worker.js");
  Object.assign(FORCE, { worker: w, ids, at, paused: false });
  Object.assign(LSTAT, { forceIter: 0, forceMax: maxIter, forceState: "진행", forceMs: 0, frames: 0 });
  w.onmessage = (ev) => {
    const m = ev.data || {};
    if (m.type !== "frame" || FORCE.worker !== w) return;
    Object.assign(LSTAT, { forceIter: m.iter, forceMax: m.max, forceMs: m.ms, frames: LSTAT.frames + 1,
                           forceState: m.done ? "끝" : (FORCE.paused ? "멈춤" : "진행") });
    onFrame(m, ids);
  };
  w.postMessage({ type: "start", x: ids.map((id) => (seed[id] || { x: 0 }).x), y: ids.map((id) => (seed[id] || { y: 0 }).y),
                  m: mass, edges: E, fixed: ids.map((id) => (fixed[id] ? 1 : 0)),
                  cfg: { ...FORCE_CFG, scaling: opts.scaling ?? FORCE_CFG.scaling,
                         gravity: opts.gravity ?? FORCE_CFG.gravity, maxIter } });
}

function forceStop() {
  if (FORCE.worker) FORCE.worker.terminate();
  FORCE.worker = null;
}

/** 멈춤 ↔ 이어서 — 워커는 그 자리에서 선다(좌표는 반복 수로만 정해진다). */
function forcePause(on) {
  if (!FORCE.worker) return;
  FORCE.paused = on;
  LSTAT.forceState = on ? "멈춤" : "진행";
  FORCE.worker.postMessage({ type: on ? "stop" : "resume" });
}

/** 사람이 끈 점 — 워커가 그 자리에 고정한다(B84 ④ — 그 세션 동안). */
function forcePin(id, x, y) {
  const i = FORCE.at.get(id);
  if (FORCE.worker && i !== undefined) FORCE.worker.postMessage({ type: "pin", i, x, y });
}
