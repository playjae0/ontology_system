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
