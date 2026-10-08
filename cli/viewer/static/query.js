/* 칸 5.3 — 뷰어 **질의 콘솔**: 링크 결과(ⓐ~ⓔ)와 LLM 답(ⓕ)을 나란히 · 경로 오버레이 · 오류 문면 · LLM 배지
 * (B82 ④ · B84 ⑤ · B103 ⑤ · B104 ④).
 *
 * `app.js`에서 떼어냈다(B84 — §7 상한). 여기가 아는 것은 **받은 답을 어떻게 보이나**다 —
 * 질의의 계산은 서버가 시스템 함수로 한다(PF11). 칸마다 **trace·묶음에 있는 것만** 싣는다(새 계산 0):
 *   ⓐ 링킹(노드 · 어디의 무엇 · 단계 · 점수 · 선별 이유) ⓑ 확장 경로(홉 엣지) ⓒ 그래프 사실(쓴 것 표시)
 *   ⓓ 노드 근거 청크 ⓔ 문서 검색 청크(점수 · 쓴 것 표시) ⓕ LLM 답 — CLI `query`와 같은 묶음이다.
 *
 * **조용히 비지 않는다**(B84 ⑤): 사내 첫 실측에서 게이트웨이가 `temperature` 때문에
 * HTTP 400으로 죽었는데 브라우저에는 아무것도 안 떴다 — 서버는 이미
 * `500 {"error": "GatewayError: … POST <url> …"}`를 내고 있었고 화면이 그 키를 보지
 * 않았을 뿐이다. 문면은 **서버가 준 그대로** 싣는다(화면이 고쳐 쓰지 않는다).
 */
"use strict";

const Q_BOXES = ["#qfacts", "#qchunks", "#qlinked", "#qmiss", "#qpath", "#qhops", "#qdocs", "#qllm"];

function errorCard(text) {
  const ans = $("#qanswer"); ans.innerHTML = "";
  ans.append(el("div", "card err", text));
  Q_BOXES.forEach((s) => { if ($(s)) $(s).innerHTML = ""; });
}

function asking(on) {
  S.asking = on;
  const b = $("#qform button");
  if (b) { b.disabled = on; b.textContent = on ? "묻는 중…" : "묻는다"; }
}

/** 원문 카드 — 머리 한 줄 + 접어 둔 원문 전부(누르면 펼친다) · 「원본」은 문서 패널을 연다. */
function chunkCard(head, text, docId, cls) {
  const card = el("details", "card" + (cls ? " " + cls : ""));
  card.append(el("summary", "", head), el("pre", "src", text || ""));
  const a = el("a", "", "원본"); a.href = "#";
  a.onclick = (ev) => { ev.preventDefault(); openDoc(docId); };
  card.append(a);
  return card;
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
  S.res = res;
  const tr = S.trace || {};
  $("#qpath").innerHTML = "";
  $("#qpath").append(el("span", "badge", `경로 ${res.path}`),
                     el("span", "muted", ` · 의도 ${tr.intent || "—"}`));
  llmBadges(tr);
  // ⓐ 링킹 — 사전 칩 · LLM이 고른 칩(점선 · 점수 · 이유)
  const lk = $("#qlinked"); lk.innerHTML = "";
  (tr.linking || []).forEach((l) => {
    const pick = l.method === "embed+llm";
    const c = el("span", "chip" + (pick ? " pick" : ""),
                 `${l.canonical} [${l.layer}·${l.method}${pick ? ` · ${l.score}` : ""}]`);
    if (pick) c.title = `${l.where || ""}${l.why ? " — " + l.why : ""}`;
    c.onclick = () => detail(S.graph.nodes.find((n) => n.id === l.node_id));
    lk.append(c);
    if (pick && l.why) lk.append(el("div", "muted", `└ ${l.canonical}: ${l.why}`));
  });
  // ⓑ 확장 경로 — 홉마다 엣지(이름은 서버가 단 것)
  const hb = $("#qhops"); hb.innerHTML = "";
  const edges = (tr.hops || []).flatMap((h) => (h.edges || []).map((e) => [h.label, e]));
  edges.slice(0, 30).forEach(([lab, e]) =>
    hb.append(el("div", "", `${lab} · ${e.src_name || e.src} —${e.rel}→ ${e.dst_name || e.dst}`)));
  if (edges.length > 30) hb.append(el("div", "muted", `… 엣지 ${edges.length - 30}개 더`));
  if (!edges.length) hb.append(el("div", "muted", "(확장 없음)"));
  // ⓒ 그래프 사실 — 쓴 것 표시
  const fb = $("#qfacts"); fb.innerHTML = "";
  (tr.facts || []).forEach((f) => {
    const c = el("div", "card" + (f.used ? " used" : ""), f.text);
    c.onclick = () => flash(tr.hops || []);
    fb.append(c);
  });
  // ⓓ 노드 근거 청크 — 수집(잘림 회색 · 쓴 것 표시) · 원문은 묶음의 chunks/related에서
  const texts = {};
  [...(res.chunks || []), ...(res.related || []), ...(res.doc_search || [])]
    .forEach((c) => { texts[c.chunk_id] = c.text; });
  const cb = $("#qchunks"); cb.innerHTML = "";
  (tr.collection || []).forEach((c) => {
    const head = `${c.doc_id} ${c.source_locator || ""} · tier ${c.tier}`
                 + (c.channel && c.channel !== "describes" ? ` · ${c.channel === "ref" ? "관련 원문" : "관련 링크"}` : "")
                 + (c.kept ? "" : " · 상한에서 잘림") + (c.used ? " · ✓ 답에 씀" : "");
    const card = chunkCard(head, texts[c.chunk_id] || "(상한에서 잘려 원문을 싣지 않았다)", c.doc_id,
                           (c.kept ? "" : "dropped") + (c.used ? " used" : ""));
    card.onclick = () => detail(S.graph.nodes.find((n) => n.id === c.via_node));
    cb.append(card);
  });
  // ⓔ 문서 검색 — 질문으로 찾은 청크(점수 · 노드 근거와 겹침 · 쓴 것)
  const db = $("#qdocs"); db.innerHTML = "";
  (tr.doc_search || []).forEach((c) => {
    const sc = [c.embed != null ? `임베딩 ${c.embed}` : "", c.bm25 != null ? `BM25 ${c.bm25}` : "",
                c.ref ? "찾아볼 시트" : "", c.in_graph ? "노드 근거와 겹침" : "",
                c.used ? "✓ 답에 씀" : ""].filter(Boolean).join(" · ");
    db.append(chunkCard(`${c.rank}. ${c.doc_id} ${c.source_locator || ""} · ${sc}`, texts[c.chunk_id],
                        c.doc_id, c.used ? "used" : (c.in_graph ? "dropped" : "")));
  });
  if (!(tr.doc_search || []).length) db.append(el("div", "muted", "(문서 검색 0 — 두 채널이 다 비면 「근거 없음」)"));
  // ⓕ LLM 답 — 텍스트 · 줄 수 · 쓴 근거 수
  const ans = $("#qanswer"); ans.innerHTML = "";
  const A = tr.answer || {};
  ans.append(el("div", "card", A.text || res.answer || "—"));
  if (A.mode === "live")
    ans.append(el("div", "muted", `LLM(live) · ${A.lines || 0}줄 · 쓴 사실 ${(tr.facts || []).filter((f) => f.used).length}`
                                    + ` · 쓴 청크 ${(A.used_chunks || []).length}`));
  else ans.append(el("div", "muted", "(mock — 답은 정형 나열 · 문장 생성 없음)"));
  const ms = $("#qmiss"); ms.innerHTML = "";
  if ((tr.miss || []).length) ms.append(el("p", "note", `미스(사전 단): ${tr.miss.join(" · ")}`));
  if (res.truncated) ms.append(el("p", "note", `근거 ${res.truncated}건이 상한에서 잘렸다`));
  const hi = { nodes: {} };
  (tr.linking || []).forEach((l) => { hi.nodes[l.node_id] = l.method === "embed+llm" ? "pick" : "link"; });
  (tr.hops || []).forEach((h) => (h.nodes || []).forEach((n) => { hi.nodes[n] = hi.nodes[n] || "reach"; }));
  paint(hi, tr.hops || []);
}

/** **무엇이 LLM이었나**(B103 ⑤ · B104 ②) — 모드 · 링킹(사전 / 임베딩 후보 + LLM 선별) · 답변(LLM / 정형 나열).
 * trace에 있는 것만 싣는다(새 계산 0 — 셈은 trace 행의 `method`를 센 것). 질의의 LLM 자리는
 * 명세대로 링킹 선별과 답변 두 곳이다(문서 5 머리 — 근거 고르기는 코드). */
function llmBadges(tr) {
  const box = $("#qllm"); if (!box) return;
  box.innerHTML = "";
  const mode = (tr.answer && tr.answer.mode) || $("#badge-mode").textContent || "—";
  const lk = tr.linking || [];
  const st = tr.link_stage || {};
  const fb = lk.filter((l) => l.method === "embed+llm").length;
  box.append(el("span", "badge mode-" + mode, mode),
             el("span", "", ` 링킹 — 사전 ${lk.length - fb} · 임베딩 후보 ${(st.candidates || []).length}`
                            + ` → LLM 선별 ${fb} (모드 ${st.mode || "—"})`),
             el("span", "", ` · 답변 — ${!tr.answer ? "—" : tr.answer.mode === "live" ? "LLM(live)" : "정형 나열(mock)"}`));
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
