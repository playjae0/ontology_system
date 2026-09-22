/* 칸 5.2~5.4 — 뷰어 화면 (B82 ②④⑤).
 *
 * **화면은 엔진을 갖지 않는다**(PF11): 질의·판정·집계는 서버가 시스템 함수로 하고
 * 여기서는 받은 것을 그린다. 계산이라고 부를 만한 것은 좌표 배치 하나다 —
 * 그마저 **결정적**이다(같은 입력이면 같은 그림 · 사람이 위치로 기억한다).
 *
 * 렌더러는 인터페이스 하나 뒤에 있다: `render({nodes, edges, highlight, paths,
 * filters, onSelect})`. 교체하려면 그 함수 하나를 갈아 끼운다.
 */
"use strict";

const S = {                      // 상태 — 화면이 아는 전부
  graph: { nodes: [], edges: [], layers: [], rels: [] },
  axis: "category",              // 색 축 기본값(요청문 ②)
  rels: new Set(), docs: new Set(), filters: {},
  obsolete: false, force: false, alwaysCross: true, search: "",
  trace: null, sigma: null, gr: null,
};

const $ = (s) => document.querySelector(s);
const el = (tag, cls, txt) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (txt !== undefined) e.textContent = txt; return e; };
const get = (p) => fetch(p).then((r) => r.json());

/* 값 → 색: **결정적**이다(같은 값이면 어느 실행에서나 같은 색). */
function colorOf(v) {
  const s = String(v == null ? "—" : v);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return `hsl(${h}, 62%, 58%)`;
}
const AXES = ["layer", "category", "status", "tier", "polarity", "made_by"];
const axisValue = (n, ax) => (n[ax] == null || n[ax] === "" ? "—" : String(n[ax]));

/* ── 계층 좌표 — `part_of` 트리·층·tier·부모 순 (결정적) ───────────────── */
function layout(nodes, edges) {
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

/* ── 렌더러 인터페이스 하나 — 교체 가능 ────────────────────────────────── */
function render({ nodes, edges, highlight = {}, paths = [], onSelect = null }) {
  const wrap = $("#canvas");
  $("#webgl-warn").hidden = true;       // 그릴 수 있으면 경고는 없다
  if (!window.Sigma || !window.graphology) { $("#webgl-warn").hidden = false; return; }
  const G = window.graphology.MultiDirectedGraph || window.graphology.Graph;
  const g = new G();
  const pos = layout(nodes, edges);
  nodes.forEach((n) => {
    const hi = highlight.nodes && highlight.nodes[n.id];
    g.addNode(n.id, {
      label: n.name, size: hi ? 9 : (n.status === "seed" ? 6 : 4),
      color: hi === "link" ? "#ffd166" : hi === "reach" ? "#9ad" : colorOf(axisValue(n, S.axis)),
      x: pos[n.id] ? pos[n.id].x : Math.random(), y: pos[n.id] ? pos[n.id].y : Math.random(),
      zIndex: hi ? 2 : 1, _node: n,
    });
  });
  const onPath = new Set();
  paths.forEach((h) => (h.edges || []).forEach((e) => onPath.add(`${e.src}|${e.rel}|${e.dst}`)));
  edges.forEach((e) => {
    if (!g.hasNode(e.src) || !g.hasNode(e.dst)) return;
    const key = `${e.src}|${e.rel}|${e.dst}`;
    // **걸침은 곡선 + 별색**이다(B82 ②). 요청문은 「점선」이라 적었지만 벤더링한
    // 렌더러에 점선 프로그램이 없다 — 없는 것을 있다고 부르면 화면이 통째로 죽는다
    // (실측: `edge type "dashed"` 프로그램 없음). 가르는 성질(한눈에 다른 선)은 같다.
    g.addEdge(e.src, e.dst, {
      label: e.rel, size: onPath.has(key) ? 3 : 1,
      type: e.cross ? "curve" : "line",
      color: onPath.has(key) ? "#ffd166" : e.cross ? "#c792ea" : "#3a4152",
    });
  });
  if (S.sigma) { S.sigma.kill(); S.sigma = null; }
  try {
    const R = window.Sigma.rendering || {};
    S.sigma = new (window.Sigma.Sigma || window.Sigma)(g, wrap, {
      renderEdgeLabels: true, defaultEdgeType: "line", labelDensity: 0.6,
      edgeProgramClasses: R.EdgeCurveProgram ? { curve: R.EdgeCurveProgram } : undefined,
    });
  } catch (err) {                       // WebGL이 없거나 렌더러가 깨졌다 — 숨기지 않는다
    console.error("render 실패:", err);
    $("#webgl-warn").hidden = false;
    $("#webgl-warn").textContent = "그래프를 그리지 못했다 — " + err;
    return;
  }
  S.gr = g;
  if (onSelect) S.sigma.on("clickNode", ({ node }) => onSelect(g.getNodeAttribute(node, "_node")));
}

/* ── 보이는 것 고르기 — 필터·검색·obsolete·엣지 토글 ──────────────────── */
function visible() {
  const q = S.search.trim().toLowerCase();
  const nodes = S.graph.nodes.filter((n) => {
    if (!S.obsolete && n.status === "obsolete") return false;
    for (const [ax, keep] of Object.entries(S.filters))
      if (keep.size && !keep.has(axisValue(n, ax))) return false;
    if (q && !(String(n.name).toLowerCase().includes(q) || String(n.id).toLowerCase() === q))
      return false;
    return true;
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = S.graph.edges.filter((e) =>
    ids.has(e.src) && ids.has(e.dst)
    && ((e.cross && S.alwaysCross) || S.rels.has(e.rel)));
  return { nodes, edges };
}

function draw(highlight, paths) {
  const { nodes, edges } = visible();
  $("#head-stat").textContent =
    `노드 ${nodes.length}/${S.graph.nodes.length} · 엣지 ${edges.length}/${S.graph.edges.length}`;
  render({ nodes, edges, highlight: highlight || {}, paths: paths || [], onSelect: detail });
  legend(nodes);
}

/* ── 범례 — 값·수·견본 ────────────────────────────────────────────────── */
function legend(nodes) {
  const box = $("#legend"); box.innerHTML = "";
  const cnt = {};
  nodes.forEach((n) => { const v = axisValue(n, S.axis); cnt[v] = (cnt[v] || 0) + 1; });
  const rows = Object.entries(cnt).sort((a, b) => b[1] - a[1]);
  $("#legend-n").textContent = `(${S.axis} · ${rows.length}값)`;
  rows.forEach(([v, n]) => {
    const r = el("div", "row");
    const sw = el("span", "sw"); sw.style.background = colorOf(v);
    r.append(sw, el("span", "", v), el("span", "muted", ` ${n}`));
    box.append(r);
  });
  $("#tier-note").hidden = S.axis !== "tier";
}

/* ── 노드 상세 — provenance → 문서·행 → 원본 ─────────────────────────── */
async function detail(n) {
  const box = $("#detail"); box.innerHTML = "";
  if (!n) { box.append(el("p", "muted", "점을 고르면 상세가 뜬다.")); return; }
  box.append(el("h3", "", n.name));
  const t = el("table");
  [["layer", n.layer], ["category", n.category], ["status", n.status], ["tier", n.tier],
   ["polarity", n.polarity], ["made_by", n.made_by], ["alias", n.aliases],
   ["attrs", n.attrs], ["큐", n.queue || "—"], ["id", n.id]]
    .forEach(([k, v]) => { const tr = el("tr"); tr.append(el("td", "", k), el("td", "", String(v ?? "—"))); t.append(tr); });
  box.append(t);
  box.append(el("h3", "", "provenance"));
  const docs = String(n.prov || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!docs.length) box.append(el("p", "muted", "(없음)"));
  for (const p of docs) {
    const docId = p.split("#")[0].split(":")[0];
    const line = el("div", "row");
    const a = el("a", "", p); a.href = "#"; a.onclick = (ev) => { ev.preventDefault(); openDoc(docId); };
    line.append(a); box.append(line);
  }
  box.append(el("h3", "", "인접"));
  S.graph.edges.filter((e) => e.src === n.id || e.dst === n.id).slice(0, 40).forEach((e) => {
    const other = e.src === n.id ? e.dst : e.src;
    const o = S.graph.nodes.find((x) => x.id === other);
    const b = el("div", "row");
    const a = el("a", "", `${e.rel} → ${o ? o.name : other}`);
    a.href = "#"; a.onclick = (ev) => { ev.preventDefault(); detail(o); };
    b.append(a); box.append(b);
  });
}

/* ── 문서 패널 — 대장 집계 · 청크 · 원본 링크 ─────────────────────────── */
async function openDoc(docId) {
  const d = await get(`/api/doc/${encodeURIComponent(docId)}`);
  const box = $("#detail"); box.innerHTML = "";
  if (d.error) { box.append(el("p", "muted", d.error)); return; }
  box.append(el("h3", "", `문서 ${d.doc_id}`));
  if (d.raw_rel) {
    const a = el("a", "", "원본 열기"); a.href = `/raw/${d.raw_rel}`; a.target = "_blank";
    box.append(a);
  } else {
    box.append(el("p", "muted", "원본이 상태 루트의 raw/ 아래가 아니다 — 링크 없음"));
  }
  const t = el("table");
  Object.entries(d.tally).forEach(([k, v]) => {
    const tr = el("tr"); tr.append(el("td", "", k), el("td", "", String(v))); t.append(tr);
  });
  box.append(el("h3", "", `판정 대장 ${d.rows}행`), t);
  box.append(el("h3", "", `노드 ${d.nodes.length}`));
  d.nodes.slice(0, 50).forEach((n) => box.append(el("div", "row", `${n.canonical} [${n.layer}]`)));
  /* 시트 역할 — 사람이 한 번 정한 기록 그대로(B83 ④). 없으면 줄도 없다. */
  const roles = Object.entries(d.sheet_roles || {});
  if (roles.length) {
    box.append(el("h3", "", `시트 역할 ${roles.length}장`));
    roles.forEach(([n, r]) => box.append(el("div", "row", `${n} — ${r}`)));
  }
  const nref = d.chunks.filter((c) => c.sheet_role === "ref").length;
  box.append(el("h3", "", `청크 ${d.chunks.length}` + (nref ? ` · 참조 ${nref}` : "")));
  d.chunks.slice(0, 20).forEach((c) =>
    box.append(el("div", "card", `${c.source_locator || ""}${c.sheet_role ? ` [${c.sheet_role}]` : ""} ${String(c.text).slice(0, 120)}`)));
}

/* ── 질의 콘솔 — 경로 오버레이 · 두 채널 · 미스 (설계_03 §3) ──────────── */
async function ask(q) {
  const res = await get(`/api/query?q=${encodeURIComponent(q)}`);
  S.trace = res.trace || null;
  const tr = S.trace || {};
  $("#qpath").innerHTML = "";
  $("#qpath").append(el("span", "badge", `경로 ${res.path}`),
                     el("span", "muted", ` · 의도 ${tr.intent || "—"}`));
  const lk = $("#qlinked"); lk.innerHTML = "";
  (tr.linking || []).forEach((l) => {
    const c = el("span", "chip" + (l.method === "llm_fallback" ? " fallback" : ""),
                 `${l.canonical} [${l.layer}·${l.method}]`);
    c.onclick = () => detail(S.graph.nodes.find((n) => n.id === l.node_id));
    lk.append(c);
  });
  const ans = $("#qanswer"); ans.innerHTML = "";
  ans.append(el("h3", "", "답변"),
             el("div", "card", (tr.answer && tr.answer.text) || res.answer || "—"),
             el("span", "muted", tr.answer ? `(${tr.answer.mode})` : ""));
  const fb = $("#qfacts"); fb.innerHTML = "";
  (tr.facts || []).forEach((f) => {
    const c = el("div", "card" + (f.used ? " used" : ""), f.text);
    c.onclick = () => flash(tr.hops || []);
    fb.append(c);
  });
  const cb = $("#qchunks"); cb.innerHTML = "";
  (tr.collection || []).forEach((c) => {
    const card = el("div", "card" + (c.kept ? "" : " dropped"));
    const head = `${c.doc_id} ${c.source_locator || ""} · tier ${c.tier}`
                 + (c.kept ? "" : " · 상한에서 잘림");
    card.append(el("div", "", head));
    const a = el("a", "", "원본"); a.href = "#";
    a.onclick = (ev) => { ev.preventDefault(); openDoc(c.doc_id); };
    card.append(a);
    card.onclick = () => detail(S.graph.nodes.find((n) => n.id === c.via_node));
    cb.append(card);
  });
  const ms = $("#qmiss"); ms.innerHTML = "";
  if ((tr.miss || []).length) ms.append(el("p", "note", `미스: ${tr.miss.join(" · ")}`));
  if (res.truncated) ms.append(el("p", "note", `근거 ${res.truncated}건이 상한에서 잘렸다`));
  const hi = { nodes: {} };
  (tr.linking || []).forEach((l) => { hi.nodes[l.node_id] = "link"; });
  (tr.hops || []).forEach((h) => (h.nodes || []).forEach((n) => { hi.nodes[n] = hi.nodes[n] || "reach"; }));
  draw(hi, tr.hops || []);
}

function flash(hops) { draw(null, hops); }

/* ── 연결 현황 ────────────────────────────────────────────────────────── */
async function funnel() {
  const f = await get("/api/funnel");
  $("#funnel-def").textContent = f["정의"];
  const box = $("#funnel"); box.innerHTML = "";
  const t = el("table"), hr = el("tr");
  hr.append(el("th", "", "문서"), ...f.keys.map((k) => el("th", "", k)));
  t.append(hr);
  f.rows.forEach((r) => {
    const tr = el("tr");
    tr.append(el("td", "", r.doc_id), ...f.keys.map((k) => el("td", "", String(r[k]))));
    t.append(tr);
  });
  const tot = el("tr");
  tot.append(el("th", "", "합계"), ...f.keys.map((k) => el("th", "", String(f.total[k]))));
  t.append(tot); box.append(t);
  const ob = $("#orphans"); ob.innerHTML = "";
  if (!f.orphans.length) ob.append(el("p", "muted", "열린 orphan 행 0"));
  f.orphans.forEach((o) => ob.append(el("div", "card",
    `${o.doc_id} · ${o.surface || ""} · ${o.reason || ""} · 재시도 ${o.attempts}`)));
}

/* ── 조절 UI ──────────────────────────────────────────────────────────── */
function controls() {
  const ax = $("#color-axes"); ax.innerHTML = "";
  AXES.forEach((a) => {
    const l = el("label"); const r = el("input");
    r.type = "radio"; r.name = "axis"; r.value = a; r.checked = a === S.axis;
    r.onchange = () => { S.axis = a; draw(); };
    l.append(r, document.createTextNode(" " + a)); ax.append(l);
  });
  const rt = $("#rel-toggles"); rt.innerHTML = "";
  S.graph.rels.forEach((rel) => {
    const l = el("label", "chk"); const c = el("input");
    c.type = "checkbox"; c.checked = true; S.rels.add(rel);
    c.onchange = () => { c.checked ? S.rels.add(rel) : S.rels.delete(rel); draw(); };
    l.append(c, document.createTextNode(" " + rel)); rt.append(l);
  });
  const fb = $("#filters"); fb.innerHTML = "";
  ["layer", "category", "status", "tier", "polarity"].forEach((axis) => {
    const vals = [...new Set(S.graph.nodes.map((n) => axisValue(n, axis)))].sort();
    if (vals.length > 12) return;
    S.filters[axis] = new Set();
    const h = el("div", "note", axis); fb.append(h);
    vals.forEach((v) => {
      const l = el("label", "chk"); const c = el("input");
      c.type = "checkbox"; c.checked = true;
      c.onchange = () => {
        const keep = S.filters[axis];
        c.checked ? keep.delete(v) : keep.add(v);   // 체크 해제 = 그 값만 숨긴다
        S.filters[axis] = new Set(vals.filter((x) => !keep.has(x)));
        if (S.filters[axis].size === vals.length) S.filters[axis] = new Set();
        draw();
      };
      l.append(c, document.createTextNode(" " + v)); fb.append(l);
    });
  });
  $("#show-obsolete").onchange = (e) => { S.obsolete = e.target.checked; draw(); };
  $("#force-layout").onchange = (e) => { S.force = e.target.checked; draw(); };
  $("#always-cross").onchange = (e) => { S.alwaysCross = e.target.checked; draw(); };
  $("#search").oninput = (e) => { S.search = e.target.value; draw(); };
  $("#qform").onsubmit = (e) => { e.preventDefault(); ask($("#q").value.trim()); };
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      ["graph", "query", "funnel"].forEach((t) => { $(`#pane-${t}`).hidden = t !== b.dataset.tab; });
      if (b.dataset.tab === "funnel") funnel();
    };
  });
  const ex = $("#examples"); ex.innerHTML = "예: ";
  ["노칭 다음 공정은?", "탭용접 설비의 인자는?", "노칭에서 나는 불량은?",
   "전체 공정 흐름은?", "실링 온도 규격은?"].forEach((q) => {
    const c = el("span", "chip", q);
    c.onclick = () => { $("#q").value = q; ask(q); };
    ex.append(c);
  });
}

/* ── 기동 ─────────────────────────────────────────────────────────────── */
(async function boot() {
  const h = await get("/api/health");
  $("#badge-mode").textContent = h.mode;
  S.graph = await get("/api/graph");
  controls();
  draw();
})();
