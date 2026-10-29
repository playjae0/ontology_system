# -*- coding: utf-8 -*-
"""칸 1.5 — **attribute 기수**(B166 ① · G4L) — 표본 레코드로 attribute 열마다 「한 대상 · 한 맥락에 값 하나」를 잰다.

대상은 **구축이 그 값을 싣는 노드**다 — 붙을 대상 열의 표기를 판정 예고와 같은 길(`entry.plan_resolve` — 좌표 해소 → 하강 →
극성 상속 → 소유자 이름 부모 → `build.entity_key`)로 해소해 열쇠를 짓는다(두 번째 구현 0): 사전 · 경로 호환이 답하면 그 노드 ·
아니면 새로 설 이름(집 층과 함께) · 대상이 anchor면 골격 조회(구축과 같은 `resolve_anchor`). `contextual`이면 맥락(봉투 ∪ 레코드
— 구축과 같은 덮어쓰기)을 더한다. 값의 같음은 구축의 충돌 판정과 같다(통째 비교). 기수는 **문서 안**이다(문서 간은 충돌 시험의
몫). LLM 0 · 쓰기 0(좌표 미해소는 버리는 자루).

판정 규칙(`fails`): 값이 갈리는 대상이 **둘 이상**이고 **잴 수 있는 대상(두 행 이상 나온 대상)의 절반 이상**일 때 — 열의 성질이다.
한 건의 충돌은 정보다(인입 때 spec_conflict가 사람에게 올린다).
"""
from __future__ import annotations

import json


def measure(docs, schema):
    """`docs` = `[{"doc", "env": {"context", "records"}}]` → attribute 열마다
    `{field, target, measurable, split, splits(값이 갈린 대상 표기)}` · 붙을 대상이 선언된 열만."""
    from core.build import scope_path
    from core.build.build import Builder
    from core.state.bootstrap import load_config, open_graph
    lay = (schema or {}).get("layer")
    fields = (schema or {}).get("fields") or {}
    attrs = {f: s for f, s in fields.items()
             if (s or {}).get("role") == "attribute" and s.get("attach_to_field") in fields}
    if not attrs or not lay:
        return []
    cfg = load_config(lay)
    b = Builder(open_graph(lay), cfg, None, "(G4L)", lay)
    owners = scope_path.table_owners(schema, cfg)
    return [_one(b, f, s, fields, owners, docs) for f, s in attrs.items()]


def _one(b, f, spec, fields, owners, docs):
    from parser.normalizer import null_marker
    af = spec["attach_to_field"]
    groups = {}
    for d in docs or []:
        env = d.get("env") or {}
        base = env.get("context") if isinstance(env.get("context"), dict) else {}
        for rec in env.get("records") or []:
            tv = rec.get(af)
            if rec.get(f) in (None, "") or not isinstance(tv, str) or not tv.strip() or null_marker(tv):
                continue                              # 값 없음 · 붙을 대상 없음 — 구축도 싣지 않는다
            tid = _target(b, rec, af, fields, owners)
            if tid is None:
                continue
            rc = rec.get("context") if isinstance(rec.get("context"), dict) else {}
            ctx = {**base, **rc} if spec.get("contextual") else {}
            k = (d.get("doc"), tid, json.dumps(ctx, sort_keys=True, ensure_ascii=False, default=str))
            g = groups.setdefault(k, {"rows": 0, "vals": set(), "name": tv.strip()})
            g["rows"] += 1
            g["vals"].add(json.dumps(rec[f], sort_keys=True, ensure_ascii=False, default=str))
    meas = [g for g in groups.values() if g["rows"] >= 2]
    split = [g for g in meas if len(g["vals"]) >= 2]
    return {"field": f, "target": af, "measurable": len(meas), "split": len(split),
            "splits": [g["name"] for g in split]}


def _target(b, rec, af, fields, owners):
    """붙을 대상의 열쇠 — 구축이 그 값을 싣는 노드(판정 예고와 같은 해소) · 판정에 오르지 않으면 None."""
    from core.build.entry import plan_mention, plan_resolve
    tspec = fields.get(af) or {}
    if tspec.get("role") == "anchor":
        from core.state.bootstrap import COORD_CATEGORY
        nid, _g = b.resolve_anchor(rec[af].strip(), tspec.get("target_category") or COORD_CATEGORY, "(G4L)",
                                   defer=[])
        return ("node", nid) if nid else None
    m = plan_mention(rec, af, fields, owners)
    r = plan_resolve(b, m) if m else None
    if not r:
        return None
    hits, key, lay = r
    return ("node", hits[0]["id"]) if hits else ("key", lay, key)


def fails(m):
    """열의 성질 — 값이 갈리는 대상이 둘 이상이고 잴 수 있는 대상의 절반 이상."""
    return m["split"] >= 2 and m["split"] * 2 >= m["measurable"]
