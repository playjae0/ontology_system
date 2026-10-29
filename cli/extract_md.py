# -*- coding: utf-8 -*-
"""칸 0.3 — **추출 확인 md**(B155 ② · B167 ③) — 봉투(`parsed/`) · 추출 체크포인트 · 목차 노드화 체크포인트 · 판정 대장(중간 저장 —
없으면 확정 대장)에서 `export/extract_<doc_id>.md`를 찍는다.

md는 보기다 — **md에만 있는 정보 0** · 되돌려 읽지 않는다 · 쓰는 자리는 구조 확인 md와 같은 한 자리(`envelope_md.save`). 재료는
`material` 하나 — `show extract <doc_id>`가 같은 함수로 청크를 찾는다(판정까지면 청크 쓰기 0이라 원문은 봉투에서 · B155 ①).

    머리      문서 · doc_type · 렌즈(층) · 지시문 판 · 단위 수(부름 · 재사용 · 개체 없음으로 건너뜀 · 실패)
    한눈에    단위 × 층 — 개체 · 관계 · 관련 링크 · 부른 단위인데 개체 0이면 ⚠
    판정      층마다 — 기존 노드 · 새 노드 · 보류(사유) 수 + 값마다 「표기 → 기존 노드 X | 새 노드 | 보류」 · 후보 수 · 근거(경로 ·
              확신) — 대장 행 그대로(값 판정의 역할 — 개체 · 소속 대상 · 제목 개체)
    단위마다  추출이 받은 것(맥락 줄 · 구조 사슬 · 부착 후보 · 부모 후보 · 캡처) · 그 쪽 판독(이름표 줄 — B169) · 원문 · 층마다 개체 표(글에서 찾은 자리 · 판정 예고) ·
              관계 · 관련 링크

단위는 추출 호출 단위다(청크 `meta.extract_unit` — PPT 슬라이드 · PDF 쪽 · 없으면 청크 하나) — 형태로 가르지 않는다.
"""
from __future__ import annotations

import json

from core import paths


def material(doc_id):
    """`{env, chunks: {chunk_id: 조각}, checkpoints: [(층, 렌즈, 체크포인트)], stale}` — 원문은 봉투에서 · 봉투가 체크포인트와 다른 판
    (문서 해시가 다르다 — 인입 뒤 고친 문서를 `--split-only`로 다시 파싱)이면 체크포인트의 청크 id가 사는 저장된 청크에서(`stale` 참 —
    머리가 그 사실을 말한다 · 저장된 청크가 없으면 단위가 빈다)."""
    from core.build import extract as EX
    from core.build.ingest import prose_chunk_ids
    from core.state import store
    from core.state.ids import doc_hash
    pp = paths.parsed(f"{doc_id}.json")
    env = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
    cks = []
    for p in EX.checkpoint_files(doc_id):
        ck = json.loads(p.read_text(encoding="utf-8"))
        cks.append((ck.get("layer"), ck.get("lens"), ck))
    dh = doc_hash(env) if env.get("chunks") else None
    stale = bool(dh) and any(ck.get("doc_hash") not in (None, dh) for _l, _z, ck in cks)
    chunks = dict((cid, c) for c, cid in prose_chunk_ids(env)) if dh and not stale else {
        cid: c for cid, c in (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}).items() if c.get("doc_id") == doc_id}
    from core.build import ledger
    led = ledger.read_partial(doc_id) or ledger.read(doc_id) or {}
    return {"doc_id": doc_id, "env": env, "chunks": chunks, "checkpoints": cks, "stale": stale,
            "rows": led.get("rows") or [], "partial": ledger.read_partial(doc_id) is not None}


def _units(mat):
    """추출 호출 단위 — `[(단위 이름, [chunk_id …])]` 봉투 차례 그대로 · 어느 체크포인트에도 후보가 없는 조각(ref 시트)은 뺀다."""
    called = {c.get("chunk_id") for _l, _z, ck in mat["checkpoints"] for c in ck.get("candidates") or []}
    out = {}
    for cid, c in mat["chunks"].items():
        if cid not in called:
            continue
        key = (c.get("meta") or {}).get("extract_unit") or c.get("source_locator") or cid
        out.setdefault(str(key), []).append(cid)
    return list(out.items())


def _closed(layer):
    """좌표 목록 — 판정 예고(`entry.decision_plan`)와 같은 셈: 사전이 아는 골격 · 확인된 노드의 표기."""
    from core.dictionary import Dictionary
    from core.state.bootstrap import open_graph
    dic, g = Dictionary.open(), open_graph(layer)
    return lambda r: any(nid in g.nodes and (g.get(nid) or {}).get("status") in ("seed", "confirmed") for nid in dic.lookup(r))


def _where(text, word):
    """글에서 찾은 자리 — 그 표기가 원문에 있는 첫 줄(`줄 n 「…」`) · 없으면 「글에 없음」(값 글자 대조와 같은 손)."""
    from core.build.values import verbatim
    for n, ln in enumerate(str(text or "").splitlines(), 1):
        if verbatim(word, ln):
            return f"줄 {n} 「{ln.strip()[:40]}」"
    return "글에 없음" if not verbatim(word, text) else "여러 줄에 걸침"


def _plan(mat, layer, chunk, e):
    """개체 하나의 판정 예고 — `(갈래, [검사 버림])`: 갈래 = 보류 예상(좌표 없음 · 좌표 목록 밖) · 사전 일치 · 판정에 오름."""
    from core.build import belongs
    from core.build.entry import _plan_hit
    from core.build.extract_unit import _is_image, text_of
    from core.build.values import verbatim
    from parser.normalizer import coord_refs
    drop = []
    if e.get("value") not in (None, "") and not verbatim(e["value"], "" if _is_image(chunk) else text_of(chunk)):
        drop.append("값 글자")
    bel = e.get("belongs_to") or {}
    if bel.get("name") and belongs.source_of(bel["name"], chunk, mat["doc"]) is None:
        drop.append("소속 출처")
    from core.build.naming import scope_categories
    from core.build.prose import parent_hit
    b = mat["builders"][layer]
    pid, pg = parent_hit(b, e, chunk, "(추출 확인)", {}, defer=[])     # 개체 부모가 주 좌표를 이긴다 — 구축과 같은 손(쓰기 0)
    if e.get("parent") and not pid:
        drop.append("부모 후보 밖")                                    # 구축은 null로 읽고 주 좌표를 쓴다
    ref = pg.get(pid)["canonical"] if pid else chunk.get("process_ref")
    refs = coord_refs(ref)
    if _plan_hit(b, {"surface": e.get("surface"), "category": e.get("category"), "ref": ref,
                     "electrode_type": chunk.get("electrode_type")}, layer):
        way = "사전 일치"
    elif e.get("category") in scope_categories(b.cfg) and not refs:   # 이름에 좌표(부모)가 붙는 카테고리만 좌표를 기다린다
        way = "보류 예상(좌표 없음)"
    elif e.get("category") in scope_categories(b.cfg) and not pid and not any(mat["closed"][layer](r) for r in refs):
        way = "보류 예상(좌표 목록 밖)"
    else:
        way = "판정에 오름"
    return way, drop


def _cell(x):
    from cli.envelope_md import _cell as c
    return c(x)


def _head(mat):
    from core.build import extract as EX
    env = mat["env"]
    out = [f"# 추출 확인 — {mat['doc_id']}", "",
           f"- 문서 {env.get('source_path') or '—'} · doc_type {env.get('doc_type') or '—'} · 지시문 판 "
           + " · ".join(dict.fromkeys(str(ck.get("prompt_version")) for _l, _z, ck in mat["checkpoints"]) or ["—"])]
    if mat.get("stale"):
        out.append("- ⚠ 봉투(parsed/)가 추출 체크포인트와 다른 판이다(문서 해시가 다르다) — 원문은 저장된 청크에서 찍었다(없는 단위는 빠진다) · "
                   "같은 문서를 --extract-only로 다시 치면 맞는다")
    for lay, lens, ck in mat["checkpoints"]:
        cs = ck.get("candidates") or []
        run = EX.RUN.get((mat["doc_id"], lens or "")) or {}
        out.append(f"- 층 {lay}{' (렌즈)' if lens else ''} — 단위 {len(cs):,} · 부름 {run.get('부름', '—')} · 재사용 {run.get('재사용', '—')} · "
                   f"개체 없음으로 건너뜀 {sum(1 for c in cs if c.get('no_entities')):,} · 실패 {sum(1 for c in cs if c.get('failed')):,}")
    return out + [""]


def _glance(mat, units):
    out = ["## 한눈에", "", "| 단위 | 층 | 개체 | 관계 | 관련 링크 | ⚠ |", "|---|---|---|---|---|---|"]
    for name, cids in units:
        for lay, _lens, ck in mat["checkpoints"]:
            cs = [c for c in ck.get("candidates") or [] if c.get("chunk_id") in cids]
            if not cs:
                continue
            n_e = sum(len(c.get("entities") or []) for c in cs)
            called = [c for c in cs if not (c.get("no_entities") or c.get("lens_skipped") or c.get("failed"))]
            warn = "⚠ 부른 단위인데 개체 0" if called and not n_e else ("실패" if any(c.get("failed") for c in cs) else "")
            out.append(f"| {_cell(name)} | {lay} | {n_e} | {sum(len(c.get('relations') or []) for c in cs)} | "
                       f"{sum(len(c.get('about') or []) for c in cs)} | {warn} |")
    return out + [""]


def verdict_of(r):
    """대장 행 하나의 판정 — `(갈래, 글)`: 갈래 = 기존 노드 · 새 노드 · 보류 · 글 = 「기존 노드 X」 · 「새 노드」 · 「보류(사유)」."""
    v = r.get("verdict")
    if v == "match":
        return "기존 노드", f"기존 노드 {r.get('target') or r.get('canonical')}" + (" (이 문서에서 선 노드)" if r.get("same_doc") else "")
    if v in ("new", "uncertain"):
        near = (r.get("nearest") or {}).get("canonical") if v == "uncertain" else None
        return "새 노드", "새 노드" + (f" (불확실 — 가까운 후보 {near})" if near else " (불확실)" if v == "uncertain" else "")
    return "보류", f"보류({r.get('hold') or r.get('queue_kind') or v})"


def _judged(mat):
    """**판정** 절(B167 ③) — 층마다 수와 값마다 판정 · 대장 행 그대로(md에만 있는 정보 0)."""
    from core.build.replay import ROLES
    rows = [r for r in mat["rows"] if r.get("role") in ROLES]
    if not rows:
        return ["## 판정", "", "- 판정 대장이 없다 — 판정 전에 멈췄다(--step) 또는 판정에 오른 값 0", ""]
    out = []
    for lay in dict.fromkeys(r.get("layer") or "—" for r in rows):
        mine = [(r, *verdict_of(r)) for r in rows if (r.get("layer") or "—") == lay]
        tally = {k: sum(1 for _r, w, _t in mine if w == k) for k in ("기존 노드", "새 노드", "보류")}
        why = {}
        for _r, w, txt in mine:
            if w == "보류":
                why[txt[3:-1]] = why.get(txt[3:-1], 0) + 1
        out += [f"## 판정 — 층 {lay}" + (" (확정 전 · 중간 저장)" if mat.get("partial") else ""), "",
                "- " + " · ".join(f"{k} {v:,}" for k, v in tally.items())
                + (" (" + " · ".join(f"{k} {v:,}" for k, v in why.items()) + ")" if why else ""), "",
                "| 표기 | 판정 | 후보 | 근거 |", "|---|---|---|---|"]
        out += [f"| {_cell(r.get('surface'))} | {_cell(txt)} | {int(r.get('candidates_n') or 0)} | "
                f"{_cell(r.get('path'))} · {float(r.get('confidence') or 0):.2f} |" for r, _w, txt in mine] + [""]
    return out


def _unit(mat, name, cids):
    from core.build import extract as EX, outline as OL
    from core.build import extract_ctx
    from core.build.extract_unit import text_of
    chunks = [mat["chunks"][x] for x in cids]
    c0 = chunks[0]
    n_cap = (mat["env"].get("capture") or {}).get("pages") or 0      # 보이는 쪽 수(정수 — 추출이 쪽마다 캡처를 붙인다)
    m0 = c0.get("meta") or {}
    page = m0.get("page_no")
    from cli import reading_md as RM
    rd = (RM.entry(mat["env"], page=page) if page                     # 그 쪽 판독 — 보이는 쪽 번호 · 없으면 슬라이드 번호(B169 ②)
          else RM.entry(mat["env"], slide=m0.get("slide")) if m0.get("slide") is not None else None)
    link = f" · [보관 캡처]({RM._UP}{rd['capture']})" if rd and rd.get("capture") else ""
    out = [f"### {name}", "",
           f"- **맥락 줄**: {extract_ctx.context_line(c0, mat['doc']) or '—'}"]
    for lay, lens, _ck in mat["checkpoints"]:
        ch = OL.structure_chain(OL.load(mat["doc_id"], lens), c0.get("source_locator"))
        if ch:
            out.append(f"- 구조 사슬({lay}): " + " › ".join(x.get("text") or "" for x in ch))
    att = EX.attach_candidates(c0.get("process_ref"))
    out += [f"- 부착 후보 {len(att):,}" + (f": {' · '.join(att[:5])}" + (" …" if len(att) > 5 else "") if att else ""),
            f"- 부모 후보: {' · '.join(EX.parent_candidates(c0)) or '없음'}",
            f"- 캡처: {f'붙음(쪽 {page})' if page and page <= n_cap else '없음'}{link}"]
    out += RM.block(mat["env"], rd, capture=False) or [""]       # 그 쪽 판독 — 봉투 `reading` 그대로(B169 ②)
    from cli.envelope_md import _body                 # 원문 묶음 — 구조 확인 md와 같은 손(머리 · 본문)
    notes = None
    for c in chunks:
        out += _body(c) + [""]
        notes = notes or (c.get("meta") or {}).get("notes")
    if notes:
        out += ["[노트]", "```text", str(notes).rstrip(), "```", ""]
    text = "\n".join(text_of(c) for c in chunks)
    for lay, _lens, ck in mat["checkpoints"]:
        cs = [c for c in ck.get("candidates") or [] if c.get("chunk_id") in cids]
        ents = [(c, e) for c in cs for e in c.get("entities") or []]
        if not cs:
            continue
        out += [f"#### 층 {lay} — 개체 {len(ents):,}", ""]
        if ents:
            out += ["| 표기 | 카테고리 | 소속(출처) | 부모 | 값 | 글에서 찾은 자리 | 판정 예고 |", "|---|---|---|---|---|---|---|"]
        for c, e in ents:
            ch = mat["chunks"].get(c.get("chunk_id")) or c0
            way, drop = _plan(mat, lay, ch, e)
            bel = e.get("belongs_to") or {}
            found = _where(text, e.get("surface"))
            if e.get("value") not in (None, ""):
                found += f" · 값 {_where(text, e['value'])}"
            own = f"{bel['name']}({bel.get('from') or '?'})" if bel.get("name") else None
            out.append(f"| {_cell(e.get('surface'))} | {_cell(e.get('category'))} | {_cell(own)} | "
                       f"{_cell(e.get('parent'))} | {_cell(e.get('value'))} | {_cell(found)} | "
                       f"{_cell(way + (' · 검사 버림(' + ' · '.join(drop) + ')' if drop else ''))} |")
        rels = [r for c in cs for r in c.get("relations") or []]
        abouts = [a for c in cs for a in c.get("about") or []]
        out += [""] + [f"- 관계 {r.get('src')} ─{r.get('rel')}→ {r.get('dst')}" for r in rels] \
            + [f"- 관련 링크 {a.get('name') if isinstance(a, dict) else a}" for a in abouts] + ([""] if rels or abouts else [])
    return out


def text(doc_id, mat=None):
    """추출 확인 md 글 전체(쓰지 않는다) — 추출 체크포인트가 없으면 None."""
    from core.build import extract_ctx
    from core.build.build import Builder
    from core.state.bootstrap import load_config, open_graph
    mat = mat or material(doc_id)
    if not mat["checkpoints"]:
        return None
    mat["doc"] = extract_ctx.doc_info(mat["env"])
    lays = {lay for lay, _z, _c in mat["checkpoints"]}
    mat["closed"] = {lay: _closed(lay) for lay in lays}
    mat["builders"] = {lay: Builder(open_graph(lay), load_config(lay), None, "(추출 확인)", lay) for lay in lays}
    units = _units(mat)
    out = _head(mat) + _glance(mat, units) + _judged(mat) + ["## 단위마다", ""]
    for name, cids in units:
        out += _unit(mat, name, cids)
    return "\n".join(out) + "\n"


def write(doc_id):
    """`export/extract_<doc_id>.md` — 쓴 자리 · 체크포인트가 없으면 None(쓰지 않는다)."""
    from cli import envelope_md
    body = text(doc_id)
    return envelope_md.save(f"extract_{doc_id}.md", body) if body else None
