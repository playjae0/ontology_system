# -*- coding: utf-8 -*-
"""칸 2.8 — **좌표 태깅의 행 손**(B181 — `tagger.py`가 800행 상한을 넘어 나눴다) — 목록 좌표 펴기 · 접기 · 골격 칸 판단의 후보.

`tagger.tag`가 부른다(같은 함수 · 같은 동작). 골격 칸 판단의 후보(`choices`)는 닫힌 분류도 같은 함수로 짓는다(core가 부른다 —
파서는 core를 import하지 않는다 · P1).
"""
from __future__ import annotations

#: 조상 추적 깊이 제한(순환 방어) — 골격 부모 사슬을 걷는 자리(`tagger.group_of` · `choices`)가 같이 쓴다
MAX_UP = 16


def choices(nodes):
    """**골격 칸 판단의 후보**(B181 ②) — 닫힌 목록 노드마다 `{id, canonical, aliases, path}`(부모 경로 — 위에서부터 · 스냅샷의
    `parent` 링크로 · 문자열 파싱 0) · `(후보들, id → 노드)`. id가 없는 목록(킷)은 canonical이 id다."""
    by_canon = {n["canonical"]: n for n in nodes}
    out, by_id = [], {}
    for n in nodes:
        up, cur, seen = [], by_canon.get(n.get("parent")), set()
        while cur is not None and cur["canonical"] not in seen and len(up) < MAX_UP:
            seen.add(cur["canonical"])
            up.append(cur["canonical"])
            cur = by_canon.get(cur.get("parent"))
        nid = n.get("id") or n["canonical"]
        out.append({"id": nid, "canonical": n["canonical"], "aliases": list(n.get("aliases") or []),
                    "path": list(reversed(up))})
        by_id[nid] = n
    return out, by_id



def ask_all(ask, pieces, refs, nodes, idx, pick, home, *, ref_field, doc_coord, notice=None, progress=None):
    """**(표기, 공정 칸)마다 한 번 묻는다**(B69 ① · B203 ②) — 행의 공정 칸(`process_group`)이 골격 노드 하나로 풀리면(`home`) 후보는
    그 노드와 그 아래 먼저 · 같다가 없을 때만 전체로 한 번 더(공정 칸이 틀린 행을 놓치지 않는다). 판단은 주입된 `pick` 한 자리(B181 ①
    — 같다 · 다르다 · 애매) · 같다만 쓴다(목록 밖 id는 버린다). `(memo {(표기, 공정 칸): canonical | None}, judged {(표기, 공정 칸):
    답 꼴 + 범위}, 호출, 채택)`."""
    memo, judged, calls, adopted = {}, {}, 0, 0
    cands, by_id = choices(nodes) if ask else ([], {})
    first, want = {}, set(ask)
    for p, r in zip(pieces, refs):
        if r in want:
            first.setdefault((r, p.get("process_group")), p)
    for n, (ref, g) in enumerate(first, 1):
        up = home(g)
        sub = [c for c in cands if up and (c["canonical"] == up or up in c["path"])]
        for pool in ([sub] if 0 < len(sub) < len(cands) else []) + [cands]:
            v = pick(ref, pool, row=first[(ref, g)], field=ref_field, doc_coord=doc_coord) or {}
            calls += 1
            if v.get("type") == "match":
                break
        hit = by_id.get(v.get("matched_id")) if v.get("type") == "match" else None
        memo[(ref, g)] = hit["canonical"] if hit is not None and hit["canonical"] in idx else None
        if v.get("type"):                                  # 답이 없으면(빈 주입) 표지 0
            judged[(ref, g)] = {**{k: v[k] for k in ("type", "confidence", "candidates", "second") if v.get(k) is not None},
                                "asked": ref, "scope": f"{up} 아래 {len(pool)}" if pool is sub else f"전체 {len(pool)}"}
        adopted += int(bool(memo[(ref, g)]))
        if notice is not None:                             # 표기 하나 = 표의 한 행(B98 ⑥)
            notice({"단계": "행", "i": n, "총": len(first), "표기": ref, "공정 칸": g,
                    "행_수": sum(1 for p, r in zip(pieces, refs) if r == ref and p.get("process_group") == g),
                    "결과": memo[(ref, g)], **{k: judged.get((ref, g), {}).get(k) for k in ("type", "confidence", "scope")}})
        if progress is not None:
            progress(n, len(first), adopted)
    return memo, judged, calls, adopted


#: 판단 답 꼴 → [1/7] 결과 말
VERDICT = {"match": "LLM 같다", "new": "LLM 다르다", "uncertain": "애매"}


def results(keys, idx, folded, scope_at, learn, kept, memo, judged):
    """**[1/7] 표기마다 결과**(B203 ③) — (표기, 공정 칸)마다 `{표기, 공정 칸, 행 수, 결과, 이름, 확실도, 까닭}`(행 수 큰 차례 · 쓰기 0)."""
    out = {}
    for i, k in enumerate(keys):
        ref, j = k[0], judged.get(k) or {}
        if not ref:
            continue
        if k not in out:
            sc, node = scope_at[i], idx.get(ref) or folded.get(ref)
            if sc or node:
                res, name, why = "정확", (sc[0] if sc else node)["canonical"], "범위 안 공유 별칭" if sc else "닫힌 목록 이름 · 별칭"
            elif ref in learn:
                res, name, why = "학습", learn[ref], "앞 문서의 같다(좌표 학습)"
            elif ref in kept:
                res, name, why = "목록 밖 기억", None, "같은 닫힌 목록 판의 목록 밖 답"
            else:
                res, name, why = (VERDICT.get(j.get("type"), "판단 없음"), memo.get(k), j.get("scope") or "상한 · 실패 — 보류")
            out[k] = {"표기": ref, "공정 칸": k[1], "행 수": 0, "결과": res, "이름": name, "확실도": j.get("confidence"), "까닭": why}
        out[k]["행 수"] += 1
    return sorted(out.values(), key=lambda x: (-x["행 수"], x["표기"]))


def flat_rows(pieces, ref_field):
    """목록 좌표 조각을 원소마다 한 행으로 — `(행들, 행마다 조각 차례)` · 목록이 아닌 조각은 그대로 한 행(meta는 원소마다 복사 —
    태깅 표시가 다른 원소로 번지지 않게)."""
    from parser.normalizer import coord_refs
    flat, owner = [], []
    for i, p in enumerate(pieces):
        if isinstance(p.get(ref_field), list):
            for x in coord_refs(p[ref_field]) or [None]:
                flat.append({**p, ref_field: x, "meta": dict(p.get("meta") or {})})
                owner.append(i)
        else:
            flat.append(p)
            owner.append(i)
    return flat, owner


def fold_rows(pieces, owner, refs, rows, ref_field):
    """원소마다 쓴 결과를 조각마다 접는다(B151 ②) — 목록 조각의 값은 원소 값의 목록(목록 꼴 그대로 — 꼴을 고치지 않는다: 표 레코드의
    목록은 계약 검사가 잡을 결함이다) · 원소 하나라도 canonical로
    고쳐 썼으면 `meta.coord_tags`(원소마다 원 표기 · 쓴 값 · 출처 — 차례 그대로)와 조각 칸 `coord_tag_source` · `coord_tag_from`(첫
    바뀐 원소 — 셈이 조각 하나를 한 번 센다) · 상위는 원소들의 상위가 하나일 때만(둘 이상이면 비운다 · 지어내지 않는다)."""
    by = {}
    for i, ref, r in zip(owner, refs, rows):
        by.setdefault(i, []).append((ref, r))
    out = []
    for i, p in enumerate(pieces):
        got = by[i]
        if not isinstance(p.get(ref_field), list):
            out.append(got[0][1])
            continue
        r, m = dict(got[0][1]), dict(p.get("meta") or {})
        r[ref_field] = list(dict.fromkeys(e.get(ref_field) for _ref, e in got if e.get(ref_field)))
        tags = [{"from": ref, "to": e.get(ref_field),
                 **({"source": (e.get("meta") or {}).get("coord_tag_source")} if e.get(ref_field) != ref else {})}
                for ref, e in got]
        moved = [(tg, e) for tg, (_ref, e) in zip(tags, got) if "source" in tg]
        cj = {k: x for _ref, e in got for k, x in ((e.get("meta") or {}).get("coord_judge") or {}).items()}
        if cj:
            m["coord_judge"] = cj
        uj = [x for _ref, e in got for x in ((e.get("meta") or {}).get("coord_unjudged") or [])]
        if uj:
            m["coord_unjudged"] = uj                 # 판단을 받지 못한 표기(B182 ①)
        if moved:
            m["coord_tags"] = tags
            m.update(coord_tag_source=moved[0][0]["source"], coord_tag_from=moved[0][0]["from"])
            if (moved[0][1].get("meta") or {}).get("coord_tag_scope"):
                m["coord_tag_scope"] = moved[0][1]["meta"]["coord_tag_scope"]
        if not p.get("process_group"):
            gs = {e.get("process_group") for _ref, e in got}
            r["process_group"] = gs.pop() if len(gs) == 1 and None not in gs else None
            if r["process_group"]:
                m["group_from_ref"] = True
        r["meta"] = m
        out.append(r)
    return out
