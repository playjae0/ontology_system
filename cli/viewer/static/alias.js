/* 칸 5.3 곁 — 뷰어 **「동의어」 탭**(B200 ③ · 결정 `결정_동의어_점검.md` §2 6 · 7): 점검 상태를 보이고 · LLM 검토를 시작하고 ·
 * 사람이 승인한다. 계산은 서버(`/api/aliases` — 시스템 함수)가 하고 여기는 받은 것을 그린다(PF11).
 *
 *   맨 위 「LLM이 빼자는 것」(틀림 · 붙은 행 수 큰 차례) → 노드 경로마다 별칭 표 → 보류 표기(별칭 후보)
 *   거르기: 틀림 · 애매 · 공유 · 겹침 의심 · 죽은 별칭 · 후보 · 검토 안 됨
 *   승인: 줄마다 처분 넷 · **일괄 승인 + 예외만 끄기**(기본은 LLM 제안 그대로 · 맞음은 「유지」) · 행위자 이름 칸 필수
 *   쓰기는 둘뿐 — `POST /api/aliases/review` · `/api/aliases/approve` · 진행은 `/api/status`의 `aliases`(질의 창과 같은 폴링)
 */
"use strict";

const AL = { data: null, filter: new Set(), poll: null, choice: {} };
const AL_FILTERS = ["틀림", "애매", "공유", "겹침 의심", "죽은 별칭", "후보", "검토 안 됨"];

function alKey(r) { return JSON.stringify([r.surface, r.target.layer, r.target.category, r.target.canonical]); }

/** 기본 처분 — LLM 제안 그대로(맞음 = 유지 · 틀림 = 제안이 있으면 다른 노드로 · 없으면 지움 · 후보 = 제안이 있으면 받기) · 그 밖은 없음. */
function alDefault(r) {
  if (r.human) return null;
  if (r.kind === "후보") return r.suggest ? "후보 받기" : null;
  if (r.verdict === "맞음") return "유지";
  if (r.verdict === "틀림") return r.suggest ? "다른 노드로" : "지움";
  return null;
}

function alShown(r) {
  if (!AL.filter.size) return true;
  const tags = new Set();
  if (r.verdict === "틀림") tags.add("틀림");
  if (r.verdict === "애매") tags.add("애매");
  if (r.shared.length) tags.add("공유");
  if (r.overlap.length || r.dict_miss) tags.add("겹침 의심");
  if (r.dead) tags.add("죽은 별칭");
  if (r.kind === "후보") tags.add("후보");
  if (!r.reviewed) tags.add("검토 안 됨");
  return [...AL.filter].some((f) => tags.has(f));
}

/** 한 줄 — 표기 · 출처 · 공유 · 판정 · 까닭 · 제안 · 붙은 행 · 처분 · 포함(일괄 승인) · 표본(펼침). */
function alRow(r, withPath) {
  const tr = el("tr");
  const c = AL.choice[alKey(r)] || (AL.choice[alKey(r)] = { on: !!alDefault(r), how: alDefault(r) || "", to: r.suggest || "" });
  if (withPath) tr.append(el("td", "", r.path || r.target.canonical || "—"));
  const s = el("td");
  s.append(el("strong", "", r.surface));
  if (r.samples.length) {
    const d = el("details"); d.append(el("summary", "muted", `표본 ${r.samples.length}`));
    r.samples.forEach((x) => d.append(el("div", "muted", x))); s.append(d);
  }
  const shared = r.shared.length ? `공유 ${r.shared.join(" · ")}` : "";
  const over = (r.overlap.length ? `겹침 ${r.overlap.join(" · ")}` : "") + (r.dict_miss ? " 사전 어긋남" : "");
  const rows = r.kind === "후보" ? `${r.rows}(보류)` : (r.dead ? "0 — 죽은 별칭" : String(r.rows))
    + (r.unknown.length ? ` · 모른다 ${r.unknown.join(" · ")}` : "");
  const v = r.human ? `사람 ${r.human}${r.human_by ? `(${r.human_by})` : ""}` : (r.verdict || "검토 안 됨");
  tr.append(s, el("td", "", r.kind === "후보" ? (r.reason || "후보") : (r.source || "")),
    el("td", "", [shared, over].filter(Boolean).join(" / ") || "—"),
    el("td", r.verdict === "틀림" ? "err" : "", v), el("td", "muted", r.why || ""),
    el("td", "", r.suggest || "—"), el("td", "", rows));
  const sel = el("select");
  [""].concat(r.kind === "후보" ? ["후보 받기"] : ["지움", "다른 노드로", "유지"]).forEach((d) => {
    const o = el("option", "", d || "—"); o.value = d; if (d === c.how) o.selected = true; sel.append(o);
  });
  const to = el("input"); to.placeholder = "노드 canonical"; to.value = c.to; to.size = 14;
  to.hidden = !["다른 노드로", "후보 받기"].includes(c.how);
  sel.onchange = () => { c.how = sel.value; c.on = !!sel.value; box.checked = c.on;
    to.hidden = !["다른 노드로", "후보 받기"].includes(c.how); };
  to.oninput = () => { c.to = to.value.trim(); };
  const box = el("input"); box.type = "checkbox"; box.checked = c.on && !!c.how;
  box.onchange = () => { c.on = box.checked; };
  const td = el("td"); td.append(sel, to); tr.append(td);
  const tb = el("td"); tb.append(box); tr.append(tb);
  return tr;
}

function alTable(rows, withPath) {
  const t = el("table"), h = el("tr");
  (withPath ? ["노드"] : []).concat(["표기", "출처", "공유 · 겹침", "판정", "까닭", "제안", "붙은 행", "처분", "포함"])
    .forEach((x) => h.append(el("th", "", x)));
  t.append(h);
  rows.filter(alShown).forEach((r) => t.append(alRow(r, withPath)));
  return t;
}

async function aliasTab() {
  const main = $("#alias-main"); main.hidden = false; main.innerHTML = "";
  main.append(el("p", "muted", "읽는 중…"));
  AL.data = await get("/api/aliases");
  const d = AL.data; main.innerHTML = "";
  if (d.error && !d.groups) { main.append(el("div", "card err", d.error)); return; }
  const c = d.counts;
  main.append(el("h3", "", `동의어 — 짝 ${c.pairs} · 공유 ${c.shared} · 겹침 의심 ${c.overlap} · 죽은 별칭 ${c.dead} · `
    + `검토 안 된 짝 ${c.unreviewed} · 보류 표기 ${c.pending}`));
  if (d.error) main.append(el("div", "card err", `지난 LLM 검토 실패 — ${d.error}`));
  const bar = el("div", "albar");
  const rv = el("button", "", "LLM 검토"); rv.onclick = aliasReview;
  const who = el("input"); who.id = "al-actor"; who.placeholder = "행위자 이름(필수)"; who.value = recall("onto.actor", "");
  const ap = el("button", "", "일괄 승인(포함 줄)"); ap.onclick = aliasApprove;
  bar.append(rv, el("span", "muted", ` ${d.preview.line} `), who, ap);
  main.append(bar, el("div", "note", "기본은 LLM 제안 그대로(맞음 = 유지 · 틀림 = 지움 또는 다른 노드로 · 후보 = 받기) — 예외만 「포함」을 끈다. "
    + "지우거나 옮긴 별칭으로 이미 붙은 행은 승인만으로 떨어지지 않는다(끝 화면의 명령 한 줄)."));
  const st = el("div", "note"); st.id = "al-status"; main.append(st);
  const fl = el("div", "radios");
  AL_FILTERS.forEach((f) => {
    const l = el("label", "chk inline"), b = el("input"); b.type = "checkbox"; b.checked = AL.filter.has(f);
    b.onchange = () => { if (b.checked) AL.filter.add(f); else AL.filter.delete(f); aliasRender(); };
    l.append(b, document.createTextNode(" " + f)); fl.append(l);
  });
  main.append(fl, el("div", "", "")); main.lastChild.id = "al-body";
  aliasRender();
}

function aliasRender() {
  const d = AL.data, body = $("#al-body"); if (!d || !body) return;
  body.innerHTML = "";
  body.append(el("h3", "", `LLM이 빼자는 것 ${d.wrong.length}`));
  body.append(d.wrong.length ? alTable(d.wrong, true) : el("p", "muted", "없음(검토 전이면 「LLM 검토」)"));
  d.groups.forEach((g) => {
    const rows = g.pairs.filter(alShown); if (!rows.length) return;
    body.append(el("h3", "", `${g.path} (${g.canonical})`), alTable(g.pairs, false));
  });
  body.append(el("h3", "", `보류 표기(별칭 후보) ${d.pending.length}`));
  body.append(d.pending.length ? alTable(d.pending, false) : el("p", "muted", "없음"));
}

async function aliasReview() {
  const d = AL.data;
  if (!window.confirm(`${d.preview.line}\n실행할까?`)) return;
  const r = await fetch("/api/aliases/review", { method: "POST" });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { $("#al-status").textContent = j.error || `HTTP ${r.status}`; return; }
  if (AL.poll) clearInterval(AL.poll);
  AL.poll = setInterval(async () => {
    const s = await get("/api/status"); const a = (s && s.aliases) || {};
    $("#al-status").textContent = `LLM 검토 ${a.state === "running" ? "중" : "끝"} — ${a.done || 0}/${a.total || 0}짝 · 호출 ${a.calls || 0}/${a.batches || 0}`;
    if (a.state !== "running") { clearInterval(AL.poll); AL.poll = null; aliasTab(); }
  }, QPOLL_MS);
}

async function aliasApprove() {
  const actor = $("#al-actor").value.trim();
  if (!actor) { $("#al-status").textContent = "행위자 이름을 적는다 — 승인은 이름으로 남는다"; return; }
  remember("onto.actor", actor);
  const all = AL.data.wrong.concat(...AL.data.groups.map((g) => g.pairs), AL.data.pending);
  const seen = new Set(), decisions = [];
  all.forEach((r) => {
    const k = alKey(r), c = AL.choice[k]; if (seen.has(k) || !c || !c.on || !c.how) return;
    seen.add(k); decisions.push({ surface: r.surface, target: r.target, kind: r.kind, disposition: c.how, to: c.to || null });
  });
  const r = await fetch("/api/aliases/approve", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor, stamp: AL.data.stamp, decisions }) });
  const j = await r.json().catch(() => ({}));
  const st = $("#al-status"); st.innerHTML = "";
  if (!r.ok) { st.append(el("div", "card err", j.error || `HTTP ${r.status}`)); return; }
  const card = el("div", "card used");
  card.append(el("div", "", j.line));
  if (j.next) card.append(el("div", "", j.next));
  (j.stale || []).forEach((s) => card.append(el("div", "muted", `골격이 바뀜 — 다시 점검: ${s}`)));
  (j.refused || []).forEach(([s, why]) => card.append(el("div", "err", `거부 — ${s}: ${why}`)));
  AL.choice = {};
  await aliasTab();
  $("#al-status").append(card);
}
