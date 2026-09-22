/* 칸 5.2~5.4 — 뷰어 **상태·배선**: 탭 · 조절 UI · 상세 · 문서 · 연결 현황 (B82 · B84).
 *
 * **화면은 엔진을 갖지 않는다**(PF11): 질의·판정·집계는 서버가 시스템 함수로 하고
 * 여기서는 받은 것을 그린다. 계산이라고 부를 만한 것은 좌표 배치 둘이고(`render.js`)
 * 그마저 **결정적**이다(같은 입력이면 같은 그림 · 사람이 위치로 기억한다).
 *
 * 파일 셋으로 가른다(B84 — §7 상한 · 351행): `render.js`(그림 — 배치·리듀서·상호작용)
 * `query.js`(질의 콘솔) 이 파일(상태·탭·조절 UI·상세·문서·현황).
 * 렌더러는 여전히 자리 둘 뒤에 있다 — `rebuild()`와 `restyle()`.
 */
"use strict";

const S = {                      // 상태 — 화면이 아는 전부
  graph: { nodes: [], edges: [], layers: [], rels: [] },
  axis: "category",              // 색 축 기본값(B82 ②)
  rels: new Set(), docs: new Set(), filters: {},
  obsolete: false, alwaysCross: true, search: "",
  layout: "계층",                 // 배치 선택 — `localStorage`가 기억한다(B84 ③)
  theme: "light",                // 밝은 테마가 기본이다(B84 ① — 사내 실측)
  pinned: {},                    // 사람이 끌어다 둔 점 — 그 세션 동안 그 자리
  highlight: { nodes: {} }, pathKeys: new Set(),
  hover: null, neighbors: null, focus: null, drag: null, asking: false,
  trace: null, sigma: null, gr: null, pos: {},
};

const $ = (s) => document.querySelector(s);
const el = (tag, cls, txt) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (txt !== undefined) e.textContent = txt; return e; };

/** 응답을 **상태와 함께** 돌려준다 — 오류 문면을 화면에 싣기 위해서다(B84 ⑤). */
async function fetchJSON(p) {
  const r = await fetch(p);
  let data = {};
  try { data = await r.json(); } catch (err) { data = { error: `응답을 읽지 못했다 — ${err}` }; }
  return { status: r.status, ok: r.ok, data };
}
const get = (p) => fetchJSON(p).then((r) => r.data);

/** 브라우저 기억 — 없거나 막혀 있으면 **기본값으로 간다**(화면이 죽지 않는다). */
const remember = (k, v) => { try { localStorage.setItem(k, v); } catch (err) { /* 무시 */ } };
const recall = (k, dflt) => {
  try { return localStorage.getItem(k) || dflt; } catch (err) { return dflt; }
};

/* ── 테마 — 색의 정본은 CSS 변수다 (B84 ①) ────────────────────────────── */
function applyTheme(t) {
  S.theme = t === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = S.theme;
  remember("onto.theme", S.theme);
  const b = $("#theme-toggle");
  if (b) b.textContent = S.theme === "dark" ? "밝게" : "어둡게";
  theme_apply_sigma();            // sigma의 라벨·엣지 색도 그 변수에서 다시 읽는다
}

/* ── 머리 줄의 수 · 범례 ──────────────────────────────────────────────── */
function stats() {
  const n = S.graph.nodes.filter(passes).length;
  const e = S.graph.edges.filter(
    (x) => edgeShown(x) && x._src && x._dst && passes(x._src) && passes(x._dst)).length;
  $("#head-stat").textContent =
    `노드 ${n}/${S.graph.nodes.length} · 엣지 ${e}/${S.graph.edges.length}`
    + ` · 배치 ${S.layout}`;
}

function legend() {
  const box = $("#legend"); box.innerHTML = "";
  const cnt = {};
  S.graph.nodes.filter(passes).forEach((n) => {
    const v = axisValue(n, S.axis); cnt[v] = (cnt[v] || 0) + 1;
  });
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

/** 검색·필터·강조 — **그림은 리듀서만** 다시 돈다(B84 ②). */
function refresh() { restyle(); stats(); legend(); }

/* ── 노드 상세 — provenance → 문서·행 → 원본 ─────────────────────────── */
async function detail(n) {
  const box = $("#detail"); box.innerHTML = "";
  if (!n) { box.append(el("p", "muted", "점을 고르면 상세가 뜬다.")); return; }
  box.append(el("h3", "", n.name));
  // 「이 노드로 질문」 — 질의 탭으로 옮기고 canonical을 칸에 넣는다(전송은 사람이).
  const askLink = el("a", "", "이 노드로 질문");
  askLink.href = "#";
  askLink.onclick = (ev) => { ev.preventDefault(); askAbout(n.name); };
  box.append(askLink);
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
    r.onchange = () => { S.axis = a; refresh(); };
    l.append(r, document.createTextNode(" " + a)); ax.append(l);
  });
  // 배치 선택 — 계층 | 힘. **기억한다**(B84 ③).
  const lb = $("#layout-pick"); lb.innerHTML = "";
  LAYOUTS.forEach((k) => {
    const l = el("label"); const r = el("input");
    r.type = "radio"; r.name = "layoutkind"; r.value = k; r.checked = k === S.layout;
    r.onchange = () => { S.layout = k; remember("onto.layout", k); rebuild(); stats(); };
    l.append(r, document.createTextNode(" " + k)); lb.append(l);
  });
  $("#relayout").onclick = () => { S.pinned = {}; rebuild(); stats(); };
  const rt = $("#rel-toggles"); rt.innerHTML = "";
  S.graph.rels.forEach((rel) => {
    const l = el("label", "chk"); const c = el("input");
    c.type = "checkbox"; c.checked = true; S.rels.add(rel);
    c.onchange = () => { c.checked ? S.rels.add(rel) : S.rels.delete(rel); refresh(); };
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
        refresh();                                  // 좌표는 그대로 — 숨기기만 한다
      };
      l.append(c, document.createTextNode(" " + v)); fb.append(l);
    });
  });
  $("#show-obsolete").onchange = (e) => { S.obsolete = e.target.checked; refresh(); };
  $("#always-cross").onchange = (e) => { S.alwaysCross = e.target.checked; refresh(); };
  // 검색 — **강조/흐림만**이고 150ms 디바운스다(B84 ②).
  let timer = null;
  $("#search").oninput = (e) => {
    const v = e.target.value;
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { S.search = v; refresh(); }, 150);
  };
  $("#theme-toggle").onclick = () => applyTheme(S.theme === "dark" ? "light" : "dark");
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
  S.theme = recall("onto.theme", "light");
  S.layout = LAYOUTS.includes(recall("onto.layout", "계층")) ? recall("onto.layout", "계층") : "계층";
  document.documentElement.dataset.theme = S.theme;
  const h = await get("/api/health");
  $("#badge-mode").textContent = h.mode;
  S.graph = await get("/api/graph");
  const byId = {};
  S.graph.nodes.forEach((n) => { byId[n.id] = n; });
  S.graph.edges.forEach((e) => { e._src = byId[e.src]; e._dst = byId[e.dst]; });
  controls();
  applyTheme(S.theme);
  rebuild();
  stats();
  legend();
})();
