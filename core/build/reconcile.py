# -*- coding: utf-8 -*-
"""칸 3.x — **문서 끝 맞춤표** — 줄마다 단위 · 같은 단위는 합 = 전체 (B112 ①④⑤).

사내(2026-10-15): 결과 줄 `값 377 → 사전 연결 22 · LLM 연결 1 · 새 노드 102 · 불확실 27 · 보류 320`의 합이 472라
현황을 셀 수 없었다 — `값`은 개체 행 · `보류`는 모든 행의 사유 · `LLM 연결`은 이번 실행에 LLM을 부른 일치뿐이었다.
여기서는 **한 줄이 한 단위**다(청크 · 조각 · 개체 행 · 행 · 노드 · 큐 항목) — 그 단위의 것 하나가 칸 하나에 들고
(닫힌 표 · 표에 없는 조합은 `그 밖(경로:판정)`으로 보이게), 칸의 합을 전체와 대조한다(어긋나면 화면이 `[결함]`).

**화면은 장부의 투영이다 — 새 판정 0 · 새로 저장하는 것 0**: 재료는 판정 대장 행 · 봉투 · 추출 체크포인트 ·
그래프 · 큐다. 인입 끝(실행 사실 `run` — 부름/재사용 · 층 전 수 · 이번/이전 큐)과 `show report`(장부만)가
**같은 함수**를 지난다 — 표 · 산문 · 렌즈 · 층 전부.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePath

from core.build.result import hold_reason
from parser.struct_rule import ROLES

#: 판정 경로(`core.matcher.PATHS`) 중 **판정을 부른 길** — 후보를 좁혀 판정(LLM · mock)에 맡긴 것
JUDGE_PATHS = ("scope+judge", "embedding+judge", "overlap+judge")
#: 판정 → 결말 칸(닫힌 표 · 밖이면 `그 밖`)
OUTCOME = {"match": "일치", "new": "새", "uncertain": "불확실", "lowres": "불확실"}
#: 구조 역할 줄의 칸 순서(B119 ① — 닫힌 다섯 + 역할 없음)
ROLE_ORDER = ROLES + ("역할 없음",)
#: 판정 → 결말 줄의 칸(개체 행 하나 → 칸 하나 — 보류가 먼저 · `mention` 다른 공정 언급 · `blank` 빈칸 표시 — B113)
END = {"match": "일치", "new": "새 노드", "uncertain": "불확실", "lowres": "불확실",
       "mention": "다른 공정 언급", "blank": "빈칸 표시"}
#: 행 역할 → 보류 줄의 행 종류
ROW_KIND = {"anchor": "좌표 행", "entity": "개체 행", "belongs": "소속 행",
            "attribute": "속성·내용 행", "content": "속성·내용 행"}


#: 합 밖 표시의 꼬리 — 수 뒤에 붙는 뜻(B157 ③ — 조각 좌표 줄 · 인입 좌표 줄이 같은 이름)
SIDE_TAIL = {"다른 공정 구간": "(쌍 대조로)", "위 공정 표기": "(문서 좌표 그대로)"}


def _sub(cnt):
    return " · ".join(f"{k} {n:,}{SIDE_TAIL.get(k, '')}" for k, n in cnt.items() if n)


def line(label, total, cells, note=""):
    """`{"줄", "전체", "칸": [(이름, 수, 세부)], "합", "맞음"}` — 칸은 0이 아닌 것만 화면에."""
    s = sum(n for _k, n, _d in cells)
    return {"줄": label, "전체": total, "칸": cells, "합": s, "맞음": s == total, "덧": note}


# ---------------------------------------------------------------- 청크(산문)
def chunk_line(ck, run=None, lens=None):
    """`청크(산문) N = 부름 + ref + 거름 + 재사용` · `부름(+재사용) = 개체 있음 + 개체 0 + 실패` — 체크포인트에서
    (부름 · 재사용은 그 실행의 사실 `run` — 없으면 「뽑음」 하나)."""
    cands = (ck or {}).get("candidates") or []
    ref = int((ck or {}).get("ref_skipped") or 0)
    lens_sk = sum(1 for c in cands if c.get("lens_skipped"))
    got = [c for c in cands if not c.get("lens_skipped")]
    has = sum(1 for c in got if not c.get("failed") and c.get("entities"))
    zero = sum(1 for c in got if not c.get("failed") and not c.get("entities"))
    fail = sum(1 for c in got if c.get("failed"))
    n = len(cands) + ref
    if run:
        called, reused = int(run.get("부름", 0)), int(run.get("재사용", 0))
        head = [("부름", called, ""), ("ref", ref, ""), ("거름", lens_sk, ""), ("재사용", reused, "")]
        who = "부름" + (" + 재사용" if reused else "")
    else:
        head = [("뽑음", len(got), ""), ("ref", ref, ""), ("거름", lens_sk, "")]
        who = "뽑음"
    lab = "청크(산문" + (f" · 렌즈 {lens}" if lens else "") + ")"
    return [line(lab, n, head),
            line(f"  {who}", len(got), [("개체 있음", has, ""), ("개체 0", zero, ""), ("실패", fail, "")])]


# ---------------------------------------------------------------- 조각 좌표
def coord_cells(env):
    """조각 좌표의 출처 — `(조각 수, Counter(자기 · 문서 좌표 · 학습 · LLM 태깅 · 없음), 합 밖 Counter)`.
    봉투의 `meta` 표시에서(태깅이 남긴 것 · 새 계산 0) — 표 · 산문 같은 함수."""
    pcs = (env or {}).get("records") or (env or {}).get("chunks") or []
    cell, side = Counter(), Counter()
    for p in pcs:
        m = p.get("meta") or {}
        if not p.get("process_ref"):
            cell["없음"] += 1
        elif m.get("coord_from_doc"):
            cell["문서 좌표"] += 1
        elif m.get("coord_tag_source") == "learned":
            cell["학습"] += 1
        elif m.get("coord_tag_source") == "live":
            cell["LLM 태깅"] += 1
        else:
            cell["자기"] += 1                       # 범위 안 해소(scope)도 자기 표기에서 온 좌표다
        if m.get("coord_other"):                  # 줄기 밖 공정 이름 구간 — 그 공정 좌표(합 안에서는 자기 · B157 ③)
            side["다른 공정 구간"] += 1
        if m.get("coord_ignored"):                # 조상 표기 — 문서 좌표 그대로
            side["위 공정 표기"] += 1
        if m.get("coord_shared_skip"):
            side["공유 별칭 건너뜀"] += 1
        if m.get("null_marked"):                  # 좌표 칸의 빈칸 표시를 비웠다(B113 ② — 문서 좌표를 물려받는다)
            side["빈칸 표시로 비움"] += 1
    return len(pcs), cell, side


def coord_line(env):
    n, cell, side = coord_cells(env)
    order = ("자기", "문서 좌표", "학습", "LLM 태깅", "없음")
    return line("조각 좌표", n, [(k, cell.get(k, 0), "") for k in order],
                note=(_sub(side) + " — 합 밖") if side else "")


# ---------------------------------------------------------------- 값(개체 행)
def value_cell(r):
    """개체 행 하나 → `(칸, 세부)` — **닫힌 표**(요청문 ①의 칸 순서): 사전 · 골격 · 재생(결말) · 기억(결말) ·
    LLM 일치 · 새 노드(LLM 판정 · 후보 없음) · 불확실 · 보류(사유) · 그 밖(경로:판정).
    보류가 먼저다(어느 경로로 왔든 노드가 서지 않았다). `LLM`은 판정 길(`JUDGE_PATHS` — mock에서는 mock 판정)."""
    why = hold_reason(r)
    if why:
        return "보류", why
    path, verdict = r.get("path") or "none", r.get("verdict")
    if verdict in ("mention", "blank"):           # 다른 공정 이름 — 관련 링크 · 빈칸 표시 — 개체 0 (B113 ①②)
        return END[verdict], ""
    out = OUTCOME.get(verdict)
    if path == "dictionary":
        return "사전", out or verdict
    if path == "path_compat":                     # 경로 호환 같은 이름(B142 ② — LLM 0)
        return "경로", out or verdict
    if path in ("skeleton", "self_coord"):
        return "골격", out or verdict
    if path == "replay" and out:
        return "재생", out
    if path == "memo" and out:
        return "기억", out
    if path in JUDGE_PATHS and out:
        return {"일치": ("LLM 일치", ""), "새": ("새 노드", "LLM 판정")}.get(out, ("불확실", ""))
    if path == "none" and verdict == "new":
        return "새 노드", "후보 없음"
    return "그 밖", f"{path}:{verdict}"


VALUE_ORDER = ("사전", "골격", "경로", "재생", "기억", "LLM 일치", "새 노드", "불확실", "다른 공정 언급", "빈칸 표시",
               "보류", "그 밖")


def value_lines(rows):
    ent = [r for r in rows if r.get("role") == "entity"]
    cells, subs = Counter(), {}
    for r in ent:
        k, d = value_cell(r)
        cells[k] += 1
        if d:
            subs.setdefault(k, Counter())[d] += 1
    det = {k: _sub(c) for k, c in subs.items() if k not in ("사전", "골격", "경로")}
    ends = Counter("보류" if hold_reason(r) else END.get(r.get("verdict"), "그 밖") for r in ent)
    return [line("값(개체 행)", len(ent), [(k, cells.get(k, 0), det.get(k, "")) for k in VALUE_ORDER]),
            line("결말(개체 행)", len(ent),
                 [(k, ends.get(k, 0), "") for k in ("일치", "새 노드", "불확실", "다른 공정 언급", "빈칸 표시",
                                                     "보류", "그 밖")])]


def prose_value_line(rows):
    """`값(산문) n = 실림 + 버림 + 충돌` — 값을 낸 개체 행에서(B120 ① · `core/build/values.counts`) · 값이 없으면 줄 0."""
    from core.build import values
    c = values.counts(rows)
    n = sum(c.values())
    return [line("값(산문)", n, [(k, c[k], "") for k in values.VERDICTS])] if n else []


# ---------------------------------------------------------------- 보류(행 종류별)
def hold_line(rows):
    held = [r for r in rows if hold_reason(r)]
    by = {}
    for r in held:
        by.setdefault(ROW_KIND.get(r.get("role"), "그 밖 행"), Counter())[hold_reason(r)] += 1
    order = ("좌표 행", "개체 행", "소속 행", "속성·내용 행", "그 밖 행")
    return line("보류(행)", len(held), [(k, sum((by.get(k) or {}).values()), _sub(by.get(k) or Counter()))
                                       for k in order])


# ---------------------------------------------------------------- 부착 · 소속 대상
def _is_belongs(a):
    return str(a.get("path") or "").startswith("소속")


def heading_names(rows):
    """이 문서의 **제목 개체** canonical(B115 ② — 대장의 `heading` 행이 붙은 노드)."""
    return {r.get("target") for r in rows if r.get("role") == "heading" and r.get("node_id") and r.get("target")}


def _kind(other, skeleton, heads):
    """소속 대상의 종류 — 제목 개체가 먼저(B115 — 골격이기도 한 제목도 제목 개체로 센다) · 골격 · 그 밖 노드."""
    return "제목 개체" if other in heads else ("공정" if other in skeleton else "유닛·부품")


def attach_line(rows, skeleton):
    """`부착(개체 행) N = 소속 엣지(제목 개체 · 공정 · 유닛·부품) + 관계만 + 제목 폴백 + 좌표 폴백 + 관련 링크 + 빈칸 표시 +
    엣지 없음 + 노드 없음` — 대상 종류는 상대 이름이 제목 개체인가 · 골격 이름인가로 가른다(`skeleton` — 좌표 층 골격
    canonical). 제목 폴백은 상위로 올라가는 사슬이 제목 개체에 붙인 것(B115 ③ — 세부는 단)."""
    ent = [r for r in rows if r.get("role") == "entity"]
    heads = heading_names(rows)
    c, kind, depth = Counter(), Counter(), Counter()
    for r in ent:
        att = r.get("attached") or []
        bel = [a for a in att if _is_belongs(a)]
        hf = [a for a in att if str(a.get("path") or "").startswith("폴백(")]
        if bel:
            c["소속 엣지"] += 1
            kind[_kind(bel[0].get("other"), skeleton, heads)] += 1
        elif any(a.get("path") == "관계" for a in att):
            c["관계만"] += 1
        elif any(a.get("path") == "보강" for a in att):
            c["연결 보강"] += 1                   # 마무리의 연결 보강이 이었다(B115 ④ — 지점 ⑫)
        elif hf:
            c["제목 폴백"] += 1
            depth[str(hf[0]["path"])[len("폴백("):-1].replace("제목 ", "")] += 1
        elif any(a.get("path") == "폴백" for a in att):
            c["좌표 폴백"] += 1
        elif r.get("verdict") == "mention":       # 다른 공정 언급 — 노드 대신 관련 링크(B113 ①)
            c["관련 링크"] += 1
        elif r.get("verdict") == "blank":         # 빈칸 표시 — 개체 0(B113 ②)
            c["빈칸 표시"] += 1
        elif r.get("node_id"):
            c["엣지 없음"] += 1
        else:
            c["노드 없음"] += 1
    order = ("소속 엣지", "관계만", "연결 보강", "제목 폴백", "좌표 폴백", "관련 링크", "빈칸 표시", "엣지 없음",
             "노드 없음")
    sub = {"소속 엣지": _sub(kind), "제목 폴백": _sub(Counter(dict(sorted(depth.items()))))}
    return line("부착(개체 행)", len(ent), [(k, c.get(k, 0), sub.get(k, "")) for k in order])


def declared_belongs(cks, chunk_loc):
    """체크포인트에서 소속을 낸 개체 — `Counter((위치, 표기))` · 이름 `{(위치, 표기): 소속 이름}`.
    `chunk_loc`은 청크 id → 위치(봉투의 `source_locator` — 대장 행의 위치와 같은 열쇠)."""
    from core.state.ids import norm
    cnt, name = Counter(), {}
    for ck in cks or []:
        for c in ck.get("candidates") or []:
            loc = chunk_loc.get(c.get("chunk_id"), c.get("chunk_id"))
            for e in c.get("entities") or []:
                b = e.get("belongs_to")
                if isinstance(b, dict) and b.get("name"):
                    k = (loc, norm(e.get("surface") or ""))
                    cnt[k] += 1
                    name[k] = b["name"]
    return cnt, name


def belongs_line(rows, cks, chunk_loc, skeleton, orphans):
    """`소속 대상(소속을 낸 개체) N = 공정(골격) + 유닛·부품(노드) + 버림(출처 없음) + 미해소 + 매핑 없음 + 노드 없음`.
    `orphans`는 그 문서의 `orphan_attach` 큐 표기 집합(정규화)."""
    from core.state.ids import norm
    decl, _names = declared_belongs(cks, chunk_loc)
    left = Counter(decl)
    c = Counter()
    heads = heading_names(rows)
    cell = {"제목 개체": "제목 개체", "공정": "공정(골격)", "유닛·부품": "유닛·부품(노드)"}
    for r in rows:
        if r.get("role") != "entity":
            continue
        k = (r.get("locator"), norm(r.get("surface") or ""))
        if not left.get(k):
            continue
        left[k] -= 1
        if not r.get("from") or r.get("from") == "옛 attach":
            c["버림(출처 없음)"] += 1
            continue
        bel = [a for a in r.get("attached") or [] if _is_belongs(a)]
        if bel:
            c[cell[_kind(bel[0].get("other"), skeleton, heads)]] += 1
        elif not r.get("node_id"):
            c["노드 없음"] += 1
        elif k[1] in orphans:
            c["미해소(orphan_attach)"] += 1
        else:
            c["매핑 없음"] += 1
    c["그 밖(대장 행 없음)"] += sum(left.values())
    order = ("공정(골격)", "제목 개체", "유닛·부품(노드)", "버림(출처 없음)", "미해소(orphan_attach)", "매핑 없음",
             "노드 없음", "그 밖(대장 행 없음)")
    return line("소속 대상(소속을 낸 개체)", sum(decl.values()), [(k, c.get(k, 0), "") for k in order])


def outline_lines(doc_id, cks, rows):
    """`목차 노드화(제목) N = 대상 + 주제 + 버림`(렌즈마다 — 목차 노드화 체크포인트 · B148 이름) · `제목 개체(행) n = 값 칸`(대장의 `heading` 행 —
    값 줄과 같은 닫힌 표) (B115 ①②). 목차 노드화가 없으면(표 · 제목 없는 산문 · mock 힌트 없음) 줄 0."""
    from core.build import outline as OL
    out = []
    for lens, _ck in cks:
        ol = OL.load(doc_id, lens)
        if not ol:
            continue
        hs = ol.get("headings") or []
        tg = sum(1 for h in hs if h.get("target"))
        dr = sum(1 for h in hs if h.get("dropped"))
        out.append(line("목차 노드화(제목" + (f" · 렌즈 {lens}" if lens else "") + ")", len(hs),
                        [("대상", tg, ""), ("주제", len(hs) - tg - dr, ""), ("버림", dr, "")]))
        if any("struct" in h or h.get("role") for h in hs):   # 문서 구조의 역할(B119 ①) — 같은 제목의 다른 가름
            rc = Counter(h.get("role") or "역할 없음" for h in hs)
            out.append(line("  구조(역할)", len(hs), [(k, rc.get(k, 0), "") for k in ROLE_ORDER]))
        cl = guard_clashes(ol, rows)
        if cl:
            out.append(line("  구조 · 다른 공정 가드", len(cl), [("부딪힘", len(cl), " · ".join(cl[:5]))]))
    hr = [r for r in rows if r.get("role") == "heading"]
    if hr:
        cells = Counter(value_cell(r)[0] for r in hr)
        out.append(line("  제목 개체(행)", len(hr), [(k, cells.get(k, 0), "") for k in VALUE_ORDER]))
    return out


def guard_clashes(ol, rows):
    """**구조 판정과 다른 공정 가드가 부딪힌 제목**(B119 ②) — 구조가 설비 · 유닛으로 세웠는데 그 이름이 다른 공정의 골격
    이름 · 별칭이라 가드가 노드 대신 관련 링크로 보낸 것(대장의 `heading` 행 · 판정 `mention`) — `[경로 → 그 공정]`. 처분은 허브."""
    from parser.struct_rule import UNIT_ROLES
    role = {h["path"]: h.get("role") for h in (ol or {}).get("headings") or []}
    return [f"{r.get('locator')} → {r.get('canonical')}" for r in rows
            if r.get("role") == "heading" and r.get("verdict") == "mention" and role.get(r.get("locator")) in UNIT_ROLES]


def reinforce_line(rows):
    """`연결 보강(대상 개체) N = 붙음 + 재생 + 못 고름 + 버림` — 대장의 `link` 행(B115 ④ · 마무리가 적는다 — 인입 끝의
    묶음에는 아직 없고 `show report`에 보인다). 행이 없으면 줄 0."""
    lk = [r for r in rows if r.get("role") == "link"]
    if not lk:
        return []
    c = Counter("재생" if r.get("path") == "replay" else
                {"attached": "붙음", "pending": "못 고름", "gate_reject": "버림"}.get(r.get("verdict"), "그 밖")
                for r in lk)
    return [line("연결 보강(대상 개체)", len(lk), [(k, c.get(k, 0), "") for k in ("붙음", "재생", "못 고름", "버림", "그 밖")])]


def belongs_trace(r, names, skeleton, orphans, heads=None):
    """`show report --trace`의 한 행 — `소속 '<이름>' → <대상>(종류) → <결과>` (소속을 낸 개체만 · 아니면 None)."""
    from core.state.ids import norm
    k = (r.get("locator"), norm(r.get("surface") or ""))
    name = names.get(k)
    if not name:
        return None
    bel = [a for a in r.get("attached") or [] if _is_belongs(a)]
    if not r.get("from") or r.get("from") == "옛 attach":
        return f"소속 '{name}' → 버림(출처 없음 — 본문 · 경로 · 시트 · 공정에 없는 이름)"
    if bel:
        a = bel[0]
        kind = "공정 · 골격" if a.get("other") in skeleton else "유닛·부품 · 노드"
        if a.get("other") in (heads or ()):
            kind = "제목 개체"
        return f"소속 '{name}'({r['from']}) → {a.get('other')}({kind}) → 엣지 {a.get('rel')} {a.get('dir')}"
    if not r.get("node_id"):
        return f"소속 '{name}'({r['from']}) → 노드 없음(이 개체가 보류 — 엣지를 걸 노드가 없다)"
    if k[1] in orphans:
        return f"소속 '{name}'({r['from']}) → 미해소(orphan_attach — 다음 인입 마무리가 다시 찾는다)"
    return f"소속 '{name}'({r['from']}) → 매핑 없음(카테고리쌍 매핑에 없다 — 좌표 폴백 · 결함 로그)"


# ---------------------------------------------------------------- 엣지 없는 노드
def edgeless(rows, graphs, doc_id, names, skeleton, orphans):
    """**이 문서가 만든 노드 중 엣지 없는 것**과 사유 — `[(층, canonical, 카테고리, 사유)]` (B102 ⑦ 수와 같은 집합)."""
    pre = f"{doc_id}#"
    ends = set()
    for g in graphs.values():
        for e in g.edges:
            ends |= {e["src"], e["dst"]}
    by_node = {}
    for r in rows:
        if r.get("role") == "entity" and r.get("node_id"):
            by_node.setdefault(r["node_id"], []).append(r)
    out = []
    for lay, g in sorted(graphs.items()):
        for nid, n in g.nodes.items():
            if nid in ends or not any(str(p) == doc_id or str(p).startswith(pre)
                                      for p in n.get("provenance") or []):
                continue
            why = []
            for r in by_node.get(nid) or [{}]:
                t = belongs_trace(r, names, skeleton, orphans, heading_names(rows)) if r else None
                why.append(t.split(" → ", 1)[1] if t else "소속 없음")
            why = sorted(set(why)) + ["관계 없음", "좌표 폴백 없음"]
            out.append((lay, n.get("canonical"), n.get("category"), " · ".join(why)))
    return out


# ---------------------------------------------------------------- 문서 좌표 경고 (⑤)
def _fold(s):
    from core.state.ids import fold_latin, norm
    return fold_latin(norm(s or "")).replace(" ", "")


def near_coords(source_path, nodes, top=5):
    """파일 이름에 **띄어쓰기 · 라틴 대소문자를 무시하고** 든 골격 이름(canonical · 별칭 — `--coord`가 받는 이름) →
    그 노드의 canonical — 보여만 준다(자동 적용 0 · 정확 대조는 `parser.tagger.suggest_doc_coord`가 이미 했다)."""
    stem = _fold(PurePath(str(source_path or "")).stem)
    for ch in "_-.()[]":
        stem = stem.replace(ch, "")
    hits = {}
    for n in nodes or []:
        for k in [n.get("canonical")] + list(n.get("aliases") or []):
            f = _fold(k)
            if k and len(f) >= 2 and f in stem:
                hits[n["canonical"]] = max(hits.get(n["canonical"], 0), len(f))
    return sorted(hits, key=lambda c: (-hits[c], c))[:top]


def by_locator(env):
    """봉투의 조각 — 위치 → 조각(대장 행의 `locator`와 같은 열쇠)."""
    return {p.get("source_locator"): p for p in ((env or {}).get("records") or (env or {}).get("chunks") or [])}


def row_coord(r, by_loc):
    """행의 좌표 — 좌표 행이면 그 표기 자체 · 아니면 그 조각의 좌표(없으면 None) (B112 ④⑤ — 보류 목록 · 경고 같은 함수)."""
    if r.get("role") == "anchor":
        return r.get("surface")
    from parser.normalizer import coord_text
    return coord_text((by_loc.get(r.get("locator")) or {}).get("process_ref")) or None


# ---------------------------------------------------------------- 그래프 · 큐
def graph_lines(res, after, before=None):
    """층마다 `노드 전 → 후 (이 문서 +n)` — 전 수는 그 실행의 사실(없으면 지금 수와 이 문서 몫만).
    층은 전부(이 문서가 건드리지 않은 층은 +0)."""
    out = []
    mine = (res or {}).get("층") or {}
    for lay in sorted(set(mine) | set(after)):
        d = mine.get(lay) or {"노드": 0, "엣지": 0}
        a = after.get(lay, (0, 0, 0))
        if before is not None:
            b = before.get(lay, (0, 0, 0))
            out.append(f"그래프 {lay} — 노드 {b[0]:,} → {a[0]:,}(이 문서 {d['노드']:+,}) · "
                       f"엣지 {b[1]:,} → {a[1]:,}(이 문서 {d['엣지']:+,})")
        else:
            out.append(f"그래프 {lay} — 이 문서 노드 {d['노드']:+,} · 엣지 {d['엣지']:+,}(지금 층 전체 노드 {a[0]:,} · "
                       f"엣지 {a[1]:,})")
    return out


def _rows(x):
    v = (x.get("payload") or {}).get("rows", 1)
    return v if isinstance(v, int) else len(v or [1])


def queue_text(entries):
    """`kind n(m행)` — 항목 수와 그 항목이 든 행 수."""
    c, r = Counter(), Counter()
    for x in entries:
        c[x["kind"]] += 1
        r[x["kind"]] += _rows(x)
    return (f"{len(c)}종 {sum(c.values()):,}항목({sum(r.values()):,}행)"
            + (" — " + " · ".join(f"{k} {c[k]:,}({r[k]:,}행)" for k in sorted(c)) if c else ""))


# ---------------------------------------------------------------- 문서 한 줄 요약 (B118 ①)
#: 유닛 이하 — 소속 대상 줄에서 공정보다 아래에 붙은 칸(제목 개체 · 유닛·부품 노드)
UNDER_UNIT = ("유닛·부품(노드)", "제목 개체")


def _cells(lines, label):
    ln = next((x for x in lines if x["줄"].strip() == label), None)
    return (ln["전체"], {k: n for k, n, _d in ln["칸"]}, {k: d for k, _n, d in ln["칸"]}) if ln else (0, {}, {})


def summary(lines, res, after, before=None):
    """**문서 한 줄 요약의 재료** — 맞춤표의 같은 줄에서(새 계산 0): 결말(개체 행) · 값 줄의 보류 사유 · 소속 대상 줄 ·
    이 문서의 엣지 · 노드 수(층 합). `유닛 이하 비율` = 소속 대상 중 (유닛·부품(노드) + 제목 개체) / 소속을 낸 개체."""
    n, end, _d = _cells(lines, "결말(개체 행)")
    _n, _v, vdet = _cells(lines, "값(개체 행)")
    bn, bel, _bd = _cells(lines, "소속 대상(소속을 낸 개체)")
    mine = (res or {}).get("층") or {}
    under = sum(bel.get(k, 0) for k in UNDER_UNIT)
    return {"개체": n, "새 노드": end.get("새 노드", 0), "기존 연결": end.get("일치", 0), "불확실": end.get("불확실", 0),
            "보류": end.get("보류", 0), "보류 사유": vdet.get("보류", ""), "다른 공정": end.get("다른 공정 언급", 0),
            "빈칸": end.get("빈칸 표시", 0), "그 밖": end.get("그 밖", 0),
            "엣지": sum(int(d.get("엣지", 0)) for d in mine.values()),
            "노드 전": (sum(v[0] for v in before.values()) if before is not None else None),
            "노드 후": sum(v[0] for v in (after or {}).values()), "이 문서 노드": sum(int(d.get("노드", 0)) for d in mine.values()),
            "소속": bn, "유닛 이하": under, "유닛 이하 비율": (round(100.0 * under / bn, 1) if bn else None),
            "가드 부딪힘": _cells(lines, "구조 · 다른 공정 가드")[0], "값": _cells(lines, "값(산문)")[:2]}


def owner_counts(rows):
    """**같은 이름 · 다른 소유자**(B142 ⑥) — `(새 노드 중 같은 이름이 같은 공정 줄기의 다른 소유자 아래 있는 것 k, 예 셋,
    소유자 이름 비슷 → 판정에 오른 개체 행 n)` · 대장 행의 `apart` · `similar`에서(새 계산 0 · 사람이 `ops merge`로 본다)."""
    ent = [r for r in rows or [] if r.get("role") in ("entity", "belongs", "heading")]
    apart = [r for r in ent if r.get("verdict") in ("new", "uncertain") and r.get("apart")]
    ex = [f"{r.get('canonical')} ↔ {r['apart'][0]}" for r in apart[:3]]
    return len(apart), ex, sum(1 for r in ent if r.get("similar"))


def second_counts(rows):
    """2차 판정(B123 ③) — `(이번에 부른 개체 행 n, 매칭으로 바뀐 m)` · 대장 행의 `judge2`에서(새 계산 0 · 재생이 옮긴 지난 기록은
    빼고 재생의 2차(`judge2.replay`)는 넣는다)."""
    got = [r.get("judge2") for r in rows or [] if r.get("role") == "entity" and r.get("judge2")
           and (r.get("path") != "replay" or r["judge2"].get("replay"))]
    return len(got), sum(1 for j in got if j.get("now") == "match")


def replay_second_counts(rows):
    """재생의 불확실(B127 ①) — `(재생된 불확실 n, 그중 2차를 부른 m, 매칭으로 바뀐 k)` · 대장 행에서(새 계산 0)."""
    rp = [r for r in rows or [] if r.get("role") == "entity" and r.get("path") == "replay"
          and (r.get("verdict") == "uncertain" or (r.get("judge2") or {}).get("replay"))]
    j2 = [r["judge2"] for r in rp if (r.get("judge2") or {}).get("replay")]
    return len(rp), len(j2), sum(1 for j in j2 if j.get("now") == "match")


def summary_text(doc_id, s):
    """`<doc_id> — 개체 n → 새 노드 a · 기존 연결 b · 보류 c(사유별) · 다른 공정 d · 빈칸 e | 엣지 +k | 그래프 노드 N → N′ |
    유닛 이하 비율 r%` — 칸이 0이면 그 칸을 뺀다(불확실 · 그 밖은 0이 아닐 때만 — 합 = 개체)."""
    cells = [("새 노드", s["새 노드"]), ("기존 연결", s["기존 연결"]), ("불확실", s["불확실"]), ("보류", s["보류"]),
             ("다른 공정", s["다른 공정"]), ("빈칸", s["빈칸"]), ("그 밖", s["그 밖"])]
    body = " · ".join(f"{k} {v:,}" + (f"({s['보류 사유']})" if k == "보류" and s["보류 사유"] else "")
                      for k, v in cells if v or k in ("새 노드", "기존 연결", "보류"))
    nodes = (f"{s['노드 전']:,} → {s['노드 후']:,}" if s["노드 전"] is not None
             else f"{s['노드 후']:,}(이 문서 {s['이 문서 노드']:+,})")
    ratio = (f"{s['유닛 이하 비율']}%({s['유닛 이하']:,}/{s['소속']:,})" if s["유닛 이하 비율"] is not None
             else "—(소속을 낸 개체 0)")
    return (f"{doc_id} — 개체 {s['개체']:,} → {body} | 엣지 {s['엣지']:+,} | 그래프 노드 {nodes} | "
            f"유닛 이하 비율 {ratio}" + (f" | 구조 · 가드 부딪힘 {s['가드 부딪힘']:,}" if s.get("가드 부딪힘") else "")
            + _value_text(s.get("값"))
            + (f" | 2차 {s['2차'][0]:,} → 바뀜 {s['2차'][1]:,}" if (s.get("2차") or (0,))[0] else "")
            + (" | 재생 불확실 {:,} → 2차 {:,} → 바뀜 {:,}".format(*s["재생 2차"]) if (s.get("재생 2차") or (0,))[0] else "")
            + (" | 캡처 끔" if s.get("캡처 끔") else ""))


def _value_text(v):
    """` | 값 n = 실림 a · 버림 b · 충돌 c` — 값을 낸 개체가 없으면 빈 글(B120 ①)."""
    n, c = v or (0, {})
    return (f" | 값 {n:,} = 실림 {c.get('실림', 0):,} · 버림 {c.get('버림', 0):,} · 충돌 {c.get('충돌', 0):,}"
            if n else "")


# ---------------------------------------------------------------- 한 묶음
def table(doc_id, rows, res, env, cks, graphs, queue, nodes, run=None):
    """맞춤표 한 묶음 — 화면(`cli/result_screen.reconcile_lines`)이 줄로 옮긴다.

    `cks`는 `[(렌즈 또는 None, 체크포인트)]` · `queue`는 그 문서의 큐 항목 · `nodes`는 좌표 층 골격 스냅샷의
    노드(`canonical` · `aliases`) · `run`(인입 끝만)은 `{"청크": {렌즈: {부름, 재사용}}, "층 전": …,
    "큐 이번": [...], "큐 이전": [...]}`."""
    from core.build.result import layer_counts
    from core.state import store
    # 청크 id → 위치 — 체크포인트는 청크 id를, 대장 행은 위치를 든다(청크 저장소가 둘을 잇는다)
    chunk_loc = {cid: c.get("source_locator") for cid, c in
                 (store.read(store.CHUNKS, {"chunks": {}}).get("chunks") or {}).items() if c.get("doc_id") == doc_id}
    orphans = {(x.get("payload") or {}).get("surface") for x in queue if x.get("kind") == "orphan_attach"}
    from core.state.ids import norm
    orphans = {norm(s or "") for s in orphans if s}
    skeleton = skeleton_names(nodes)
    names = {}
    for _l, ck in cks:
        names.update(declared_belongs([ck], chunk_loc)[1])
    lines = []
    for lens, ck in cks:
        lines += chunk_line(ck, ((run or {}).get("청크") or {}).get(lens or ""), lens)
    lines.append(coord_line(env))
    lines += outline_lines(doc_id, cks, rows)
    lines += value_lines(rows)
    lines += prose_value_line(rows)
    lines.append(hold_line(rows))
    lines.append(attach_line(rows, skeleton))
    lines.append(belongs_line(rows, [ck for _l, ck in cks], chunk_loc, skeleton, orphans))
    lines += reinforce_line(rows)
    q_new, q_old = (run or {}).get("큐 이번"), (run or {}).get("큐 이전")
    after = layer_counts(graphs)
    return {"doc_id": doc_id, "줄": lines,
            "소유자": owner_counts(rows),
            "요약": {**summary(lines, res, after, (run or {}).get("층 전")), "2차": second_counts(rows),
                     "재생 2차": replay_second_counts(rows),
                     "캡처 끔": bool(((env or {}).get("context") or {}).get("capture_off"))},
            "그래프": graph_lines(res, after, (run or {}).get("층 전")),
            "큐": ({"이번 실행": queue_text(q_new), "이전 실행이 남긴 것": queue_text(q_old)} if q_new is not None
                  else {"지금 이 문서의 것": queue_text(queue)}),
            "엣지 없는 노드": edgeless(rows, graphs, doc_id, names, skeleton, orphans),
            "소속 이름": names, "고아": orphans, "제목 개체": heading_names(rows)}


# ---------------------------------------------------------------- 재료 모으기 (인입 끝 · show report)
def _checkpoints(doc_id):
    """그 문서의 추출 체크포인트 `[(렌즈 또는 None, dict)]` — 기본판 · 렌즈판(파일 이름 `<doc>@<렌즈>.json`)."""
    import json
    from core.build import extract
    out = []
    for p in extract.checkpoint_files(doc_id):
        lens = p.stem.split("@", 1)[1] if "@" in p.stem else None
        try:
            out.append((lens, json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def skeleton_nodes():
    """좌표 층 골격의 노드 — 소속 대상의 종류(공정)와 문서 좌표 후보의 재료(스냅샷에서 · 새 계산 0)."""
    from core.state import store
    from core.state.bootstrap import NoCoordLayer, coord_layer
    try:
        lay = coord_layer()
    except NoCoordLayer:
        return set()
    snap = store.read(store.SKELETON_LIST, {}).get(lay) or {}
    return [n for n in snap.get("nodes") or [] if n.get("canonical")]


def skeleton_names(nodes=None):
    """골격 canonical 이름 집합(소속 대상이 공정인가)."""
    return {n["canonical"] for n in (skeleton_nodes() if nodes is None else nodes)}


def for_build(doc_id, rows, res, env, graphs, run):
    """인입 끝 — 그 실행의 사실(`run`)과 함께."""
    from core.state import store
    q = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc_id]
    return table(doc_id, rows, res, env, _checkpoints(doc_id), graphs, q, skeleton_nodes(), run)


def for_report(doc_id, data):
    """`show report <doc_id>` — 장부만(대장 · 파싱 봉투 · 체크포인트 · 지금 그래프 · 지금 큐)."""
    import json
    from core import paths
    from core.state import store
    from core.state.bootstrap import open_graph
    from router import discover
    p = paths.parsed(f"{doc_id}.json")
    env = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    q = [x for x in store.read(store.QUEUE, []) if x.get("doc_id") == doc_id]
    return table(doc_id, data.get("rows") or [], data.get("result") or {}, env, _checkpoints(doc_id),
                 {lay: open_graph(lay) for lay in discover()}, q, skeleton_nodes())
