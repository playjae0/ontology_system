# -*- coding: utf-8 -*-
"""칸 0.3 — **추출 확인 md**(B155 ②) — 봉투(`parsed/`) · 추출 체크포인트 · 목차 노드화 체크포인트에서 `export/extract_<doc_id>.md`를 찍는다.

md는 보기다 — **md에만 있는 정보 0** · 되돌려 읽지 않는다 · 쓰는 자리는 구조 확인 md와 같은 한 자리(`envelope_md.save`). 재료는
`material` 하나 — `show extract <doc_id>`가 같은 함수로 청크를 찾는다(추출까지만이면 청크 쓰기 0이라 원문은 봉투에서 · B155 ①).

    머리      문서 · doc_type · 렌즈(층) · 지시문 판 · 단위 수(부름 · 재사용 · 개체 없음으로 건너뜀 · 실패)
    한눈에    단위 × 층 — 개체 · 관계 · 관련 링크 · 부른 단위인데 개체 0이면 ⚠
    판정 예고 층마다 — 사전 일치 · 판정에 오름 · 보류 예상 · 검사에서 버려짐 + 판정에 오를 표기(LLM 0 · 쓰기 0 — 새 노드인지
              일치인지는 판정이 정한다)
    단위마다  추출이 받은 것(맥락 줄 · 구조 사슬 · 부착 후보 · 부모 후보 · 캡처) · 원문 · 층마다 개체 표(글에서 찾은 자리 · 판정 예고) ·
              관계 · 관련 링크

단위는 추출 호출 단위다(청크 `meta.extract_unit` — PPT 슬라이드 · PDF 쪽 · 없으면 청크 하나) — 형태로 가르지 않는다.
"""
from __future__ import annotations

import json

from core import paths


def material(doc_id):
    """`{env, chunks: {chunk_id: 조각}, checkpoints: [(층, 렌즈, 체크포인트)]}` — 원문은 봉투(없으면 저장된 청크)에서."""
    from core.build import extract as EX
    from core.build.ingest import prose_chunk_ids
    from core.state import store
    pp = paths.parsed(f"{doc_id}.json")
    env = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
    chunks = dict((cid, c) for c, cid in prose_chunk_ids(env)) if env.get("chunks") else {
        cid: c for cid, c in (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}).items() if c.get("doc_id") == doc_id}
    cks = []
    for p in EX.checkpoint_files(doc_id):
        ck = json.loads(p.read_text(encoding="utf-8"))
        cks.append((ck.get("layer"), ck.get("lens"), ck))
    return {"doc_id": doc_id, "env": env, "chunks": chunks, "checkpoints": cks}


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
    from core.build import belongs, extract as EX
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
    if e.get("parent") and e["parent"] not in EX.parent_candidates(chunk):
        drop.append("부모 후보 밖")
    from core.build.naming import scope_categories
    b = mat["builders"][layer]
    refs = coord_refs(chunk.get("process_ref"))
    if _plan_hit(b, {"surface": e.get("surface"), "category": e.get("category"), "ref": chunk.get("process_ref"),
                     "electrode_type": chunk.get("electrode_type")}, layer):
        way = "사전 일치"
    elif e.get("category") in scope_categories(b.cfg) and not refs:   # 이름에 좌표(부모)가 붙는 카테고리만 좌표를 기다린다
        way = "보류 예상(좌표 없음)"
    elif e.get("category") in scope_categories(b.cfg) and not any(mat["closed"][layer](r) for r in refs):
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


def _plans(mat):
    out = []
    for lay, _lens, ck in mat["checkpoints"]:
        tally, judged = {"사전 일치": 0, "판정에 오름": 0, "보류 예상": 0, "검사에서 버려짐": 0}, []
        for c in ck.get("candidates") or []:
            ch = mat["chunks"].get(c.get("chunk_id")) or {}
            for e in c.get("entities") or []:
                way, drop = _plan(mat, lay, ch, e)
                tally["보류 예상" if way.startswith("보류") else way] += 1
                tally["검사에서 버려짐"] += bool(drop)
                if way == "판정에 오름" and e.get("surface") not in judged:
                    judged.append(e.get("surface"))
        out += [f"## 판정 예고 — 층 {lay} (LLM 0 · 쓰기 0)", "",
                "- " + " · ".join(f"{k} {v:,}" for k, v in tally.items()),
                "- 판정에 오를 표기(새 노드인지 일치인지는 판정이 정한다): " + (" · ".join(map(str, judged)) or "없음"), ""]
    return out


def _unit(mat, name, cids):
    from core.build import extract as EX, outline as OL
    from core.build import extract_ctx
    from core.build.extract_unit import text_of
    chunks = [mat["chunks"][x] for x in cids]
    c0 = chunks[0]
    pages = set((mat["env"].get("capture") or {}).get("pages") or [])
    page = (c0.get("meta") or {}).get("page_no")
    out = [f"### {name}", "",
           f"- 맥락 줄: {extract_ctx.context_line(c0, mat['doc']) or '—'}"]
    for lay, lens, _ck in mat["checkpoints"]:
        ch = OL.structure_chain(OL.load(mat["doc_id"], lens), c0.get("source_locator"))
        if ch:
            out.append(f"- 구조 사슬({lay}): " + " › ".join(x.get("text") or "" for x in ch))
    att = EX.attach_candidates(c0.get("process_ref"))
    out += [f"- 부착 후보 {len(att):,}" + (f": {' · '.join(att[:5])}" + (" …" if len(att) > 5 else "") if att else ""),
            f"- 부모 후보: {' · '.join(EX.parent_candidates(c0)) or '없음'}",
            f"- 캡처: {f'붙음(쪽 {page})' if page in pages else '없음'}", ""]
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
    out = _head(mat) + _glance(mat, units) + _plans(mat) + ["## 단위마다", ""]
    for name, cids in units:
        out += _unit(mat, name, cids)
    return "\n".join(out) + "\n"


def write(doc_id):
    """`export/extract_<doc_id>.md` — 쓴 자리 · 체크포인트가 없으면 None(쓰지 않는다)."""
    from cli import envelope_md
    body = text(doc_id)
    return envelope_md.save(f"extract_{doc_id}.md", body) if body else None
