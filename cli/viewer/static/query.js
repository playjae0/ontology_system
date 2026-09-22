/* 칸 5.3 — 뷰어 **질의 콘솔**: 경로 오버레이 · 두 채널 · 미스 · 오류 문면 (B82 ④ · B84 ⑤).
 *
 * `app.js`에서 떼어냈다(B84 — §7 상한). 여기가 아는 것은 **받은 답을 어떻게 보이나**다 —
 * 질의의 계산은 서버가 시스템 함수로 한다(PF11).
 *
 * **조용히 비지 않는다**(B84 ⑤): 사내 첫 실측에서 게이트웨이가 `temperature` 때문에
 * HTTP 400으로 죽었는데 브라우저에는 아무것도 안 떴다 — 서버는 이미
 * `500 {"error": "GatewayError: … POST <url> …"}`를 내고 있었고 화면이 그 키를 보지
 * 않았을 뿐이다. 문면은 **서버가 준 그대로** 싣는다(화면이 고쳐 쓰지 않는다).
 */
"use strict";

function errorCard(text) {
  const ans = $("#qanswer"); ans.innerHTML = "";
  ans.append(el("h3", "", "답변"), el("div", "card err", text));
  ["#qfacts", "#qchunks", "#qlinked", "#qmiss", "#qpath"].forEach((s) => {
    $(s).innerHTML = "";
  });
}

function asking(on) {
  S.asking = on;
  const b = $("#qform button");
  if (b) { b.disabled = on; b.textContent = on ? "묻는 중…" : "묻는다"; }
}

async function ask(q) {
  if (!q || S.asking) return;            // **요청은 한 건**이다(같은 버튼을 또 눌러도)
  asking(true);
  let r;
  try {
    r = await fetchJSON(`/api/query?q=${encodeURIComponent(q)}`);
  } catch (err) {                        // 서버가 끊겼다 — 그 사실을 쓴다
    asking(false);
    errorCard(`요청이 닿지 않았다 — ${err}`);
    return;
  }
  asking(false);
  const res = r.data || {};
  // 서버 문면 그대로 — `error` 키 또는 HTTP ≥ 400.
  if (res.error || r.status >= 400) {
    errorCard(res.error || `HTTP ${r.status} — 서버가 답을 주지 않았다`);
    return;
  }
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
  paint(hi, tr.hops || []);
}

/** 오버레이는 **리듀서만** 바꾼다(B84 ② — 좌표를 다시 계산하지 않는다). */
function paint(highlight, paths) {
  S.highlight = highlight || { nodes: {} };
  S.pathKeys = new Set();
  (paths || []).forEach((h) => (h.edges || []).forEach(
    (e) => S.pathKeys.add(`${e.src}|${e.rel}|${e.dst}`)));
  restyle();
}

function flash(hops) { paint(S.highlight, hops); }

/** 상세 패널의 「이 노드로 질문」 — **전송은 사람이** 한다(B84 ④). */
function askAbout(name) {
  document.querySelector('#tabs button[data-tab="query"]').click();
  $("#q").value = name;
  $("#q").focus();
}
