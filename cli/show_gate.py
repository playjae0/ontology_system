# -*- coding: utf-8 -*-
"""칸 0.3 — **게이트 거부 묶음** — `show log gate --by-pattern` (B118 ⑥ · 사내 2026-10-16 「설비 사양이 게이트에서 막히는데
무엇을 고치면 되는지 안 보인다」).

거부 로그(`work/gate_rejects.json` — 큐가 아니라 관측 신호 · D-7)를 **(출발 카테고리, 관계, 도착 카테고리)별 건수**로 묶고(출처 칸 —
추출 · 보강 · 정형 · 자동 · 층 칸 — 판정한 config의 층), 묶음마다 **넣을 config 줄을 그대로 제안**한다(`relation_patterns` 한 줄 —
자동 적용 0). 제안은 패턴이 없어서 막힌 것(`invalid_pattern` · `undeclared_relation`)에만 — 끝점 미해소는 config로 풀리지 않는다.
그 줄은 게이트만 바꾼다(`core/state/config_scope` 「구축」 갈래) — 재구축이 LLM 0으로 다시 판정한다.
"""
from __future__ import annotations

import json
from collections import Counter

from core.state import store

#: 패턴 줄로 풀리는 거부(그 밖은 제안하지 않는다)
FIXABLE = ("invalid_pattern", "undeclared_relation")


def groups(items=None):
    """`[(키 (src, rel, dst), 건수, {출처: n}, {판정: n}, {층: n})]` — 건수 많은 것부터."""
    items = items if items is not None else _items()
    by, src, ver, lay = Counter(), {}, {}, {}
    for it in items:
        k = (it.get("src_cat"), it.get("rel"), it.get("dst_cat"))
        by[k] += 1
        src.setdefault(k, Counter())[it.get("source") or it.get("path") or "?"] += 1
        ver.setdefault(k, Counter())[it.get("verdict") or "?"] += 1
        lay.setdefault(k, Counter())[it.get("layer") or "?"] += 1      # 판정한 config의 층 — 패턴 줄을 넣을 자리
    return [(k, n, dict(src[k]), dict(ver[k]), dict(lay[k])) for k, n in by.most_common()]


def _items():
    d = store.read(store.GATE_REJECTS, {"rejects": []})
    return d.get("rejects") if isinstance(d, dict) else (d or [])


def suggest(key, verdicts):
    """제안 줄 — 패턴이 없어서 막힌 묶음만(`FIXABLE`) · 그 밖은 None."""
    if not any(v in FIXABLE for v in verdicts):
        return None
    s, r, d = key
    if "?" in (s, d) or not r:
        return None
    return json.dumps({"src": s, "rel": r, "dst": d}, ensure_ascii=False)


def main(args):
    gs = groups()
    total = sum(n for _k, n, *_r in gs)
    print(f"■ 게이트 거부 묶음 — {total:,}건 · 삼항 {len(gs):,}종 (출발 카테고리, 관계, 도착 카테고리) · 큐가 아니라 관측 신호")
    if not gs:
        print("  (없음) — 게이트가 막은 관계가 없다")
        return 0
    for i, (k, n, src, ver, lay) in enumerate(gs, 1):
        print(f"  {i:>3}. ({k[0]}, {k[1]}, {k[2]}) — {n:,}건 · 출처 "
              + " · ".join(f"{a} {b:,}" for a, b in sorted(src.items()))
              + " · 판정 " + " · ".join(f"{a} {b:,}" for a, b in sorted(ver.items()))
              + " · 층 " + " · ".join(f"{a} {b:,}" for a, b in sorted(lay.items())))
        line = suggest(k, ver)
        if line:
            print(f"       ▶ 그 층 config의 relation_patterns에 넣을 줄: {line}")
        elif any(v == "unresolved_endpoint" for v in ver):
            print("       (끝점 미해소 — 패턴이 아니라 끝점 노드가 없다 · 재연결이 다시 찾는다)")
    print("  이 줄은 게이트만 바꾼다 — 추출은 다시 뽑지 않는다(판은 자동) · 넣은 뒤 python run.py bootstrap(영향 범위 줄) → "
          "python run.py rebuild(LLM 0으로 다시 판정)")
    return 0
