/* 칸 5.3 — 뷰어 **탐색 모드 · 연결 없는 노드 · 노드 상세의 근거** (B103 ①③④).
 *
 * 이웃은 **서버가 준다**(`/api/neighbors/<id>` — 화면이 확장을 다시 하지 않는다 · PF11) · 근거·닻까지의 길·
 * 붙은 자리도 서버가 모은 것(`/api/node/<id>`)을 그대로 싣는다. 여기는 무엇을 보일지(보이는 집합)만 안다.
 */
"use strict";

/** 지금 그릴 노드 — 탐색 모드면 펼친 집합 · 연결 없는 노드는 토글이 켜졌을 때만. */
function shownNodes() {
  const anc = S.graph.anchor || {};
  return S.graph.nodes.filter((n) =>
    (!S.explore || S.explore.shown.has(n.id)) && (S.showDetached || anc[n.id]));
}

function _recompute() {
  const shown = new Set();
  S.explore.trail.forEach((t) => { shown.add(t.id); t.added.forEach((i) => shown.add(i)); });
  S.explore.shown = shown;
}

/** 여기서 펼치기 — 그 노드 + 1홉 이웃. 이미 펼친 노드면 다시 펼치지 않는다. */
async function exploreFrom(id) {
  if (S.explore && S.explore.trail.some((t) => t.id === id)) return;
  const r = await get(`/api/neighbors/${encodeURIComponent(id)}`);
  if (r.error) return;
  if (!S.explore) S.explore = { shown: new Set(), trail: [] };
  S.explore.trail.push({ id, added: r.neighbors || [] });
  _recompute();
  crumbs(); rebuild(); stats(); legend();
}

/** 접기 — 마지막 펼침을 되돌린다(다른 펼침이 쓰는 노드는 남는다). */
function collapse() {
  if (!S.explore || !S.explore.trail.length) return;
  S.explore.trail.pop();
  if (!S.explore.trail.length) { exitExplore(); return; }
  _recompute(); crumbs(); rebuild(); stats(); legend();
}

/** 빵부스러기의 k번째로 돌아간다 — 그 뒤 펼침은 접는다. */
function crumbTo(k) {
  S.explore.trail = S.explore.trail.slice(0, k + 1);
  _recompute(); crumbs(); rebuild(); stats(); legend();
}

function exitExplore() {
  S.explore = null; crumbs(); rebuild(); stats(); legend();
}

/** 골격 뿌리부터 연다 — 노드 수가 문턱(`viewer_explore_threshold`)을 넘을 때 첫 화면. */
async function exploreRoots() {
  for (const id of S.graph.roots || []) await exploreFrom(id);
}

function crumbs() {
  const box = $("#crumbs"); if (!box) return;
  box.innerHTML = "";
  box.hidden = !S.explore;
  if (!S.explore) return;
  const byId = {};
  S.graph.nodes.forEach((n) => { byId[n.id] = n; });
  box.append(el("span", "muted", "탐색 — "));
  S.explore.trail.forEach((t, k) => {
    const a = el("a", "crumb", (byId[t.id] || {}).name || t.id);
    a.href = "#"; a.onclick = (ev) => { ev.preventDefault(); crumbTo(k); };
    box.append(a, el("span", "muted", " › "));
  });
  const c = el("button", "", "접기"); c.onclick = collapse;
  const all = el("button", "", "전체"); all.onclick = exitExplore;
  box.append(c, all);
}

/** 연결 없는 노드 토글 — 수는 서버가 센 것(엣지 없음 · 골격에 안 닿는 덩어리). */
function detachedToggle() {
  const d = S.graph.detached || { edgeless: [], island: [] };
  const n = d.edgeless.length + d.island.length;
  const lab = $("#detached-label");
  if (lab) lab.textContent = ` 연결 없는 노드 ${n} (엣지 없음 ${d.edgeless.length} · 골격에 안 닿는 덩어리 ${d.island.length})`;
  const c = $("#show-detached");
  if (c) c.onchange = (e) => { S.showDetached = e.target.checked; rebuild(); stats(); legend(); };
}

/* ── 노드 상세의 근거 — 닻까지의 길 · 근거 원문 · 문서마다 붙은 자리 (B103 ④) ── */
async function evidence(n, box) {
  const d = await get(`/api/node/${encodeURIComponent(n.id)}`);
  if (!d || d.error) return;
  box.append(el("h3", "", "닻까지의 길"));
  const ap = d.anchor_path;
  if (!ap) box.append(el("p", "muted", "닻 없음 — 골격에 닿는 엣지가 없다(연결 없는 노드)"));
  else if (!ap.steps.length) box.append(el("p", "muted", "골격 노드다"));
  else {
    const p = el("div", "card path");
    p.append(el("div", "", `닻 ${ap.anchor_name} · ${ap.hops}홉`));
    ap.steps.forEach((s) => p.append(el("div", "", `${s.src_name} —${s.rel}→ ${s.dst_name}`)));
    box.append(p);
  }
  box.append(el("h3", "", `근거 원문 ${d.evidence_total}`));
  if (!d.evidence.length) box.append(el("p", "muted", "(근거 청크 없음)"));
  d.evidence.forEach((c) => {
    const det = el("details", "card");
    const sum = el("summary", "",
      `${c.doc_id} · ${c.locator || c.chunk_id}${c.section ? ` · ${c.section}` : ""}${c.image ? " · 그림 요약" : ""}`);
    det.append(sum, el("pre", "src", c.text));
    box.append(det);
  });
  if (d.evidence_total > d.evidence.length)
    box.append(el("p", "muted", `${d.evidence_total - d.evidence.length}건 더 — python run.py show node ${n.name}`));
  box.append(el("h3", "", `붙은 자리 ${d.landed.length}`));
  d.landed.forEach((r) => {
    const c = el("div", "card");
    c.append(el("div", "", `${r.doc_id} · ${r.locator || ""} · ${r.surface} → ${r.target || "—"}`
      + ` [${r.verdict || "—"} · ${r.path || "—"}${r.from ? ` · 소속 출처 ${r.from}` : ""}]`));
    (r.attached || []).forEach((a) =>
      c.append(el("div", "muted", `└ ${a.rel} ${a.dir || "→"} ${a.other} (${a.path})`)));
    box.append(c);
  });
}
