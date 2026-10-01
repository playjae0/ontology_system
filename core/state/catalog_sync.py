# -*- coding: utf-8 -*-
"""칸 0.1 — **카탈로그 맞추기** — 층 config에서 기계적으로 따라 나오는 공통 config 줄은 `bootstrap`이 쓴다 (B92).

층 config는 사람이 문서를 보고 확정한 것이다 — 거기서 **결정적으로** 따라 나오는 공통 config
항목(한 층만 선언한 카테고리의 집 · 아무 층도 선언하지 않고 노드도 없는 카테고리의 제거)까지
사람에게 다시 시키지 않는다. **새 결정은 사람에게 남긴다** — 여러 층이 선언한 카테고리의 집 ·
겸(`also`) · 이미 정한 값의 변경. 그래서 이미 있는 항목의 `home`·`also`는 **건드리지 않는다.**

규칙은 닫힌 다섯이다(요청문 B92 ①):

| 경우 | 처리 |
|---|---|
| 카탈로그에 없고 **한 층만** 선언 | 자동 추가 — 집 = 그 층 |
| 카탈로그에 없고 **여러 층이** 선언 | 집 빈칸으로 추가 + 멈춤(사람이 고른다) |
| 카탈로그에 있고 **어느 층도 선언 안 함** | 집 그래프에 그 카테고리 노드 0이면 자동 제거 · 있으면 멈춤 |
| 카탈로그에 있고 선언도 있음 | 건드리지 않는다(`catalog.problems`의 ⓒ·ⓔ 검사는 그대로) |
| 파일이 없다(운영 처음) | 같은 규칙으로 `common.json`을 바로 만든다 · 이름 규칙은 층 config에서 옮긴다 |

그리고 **집 변경 막기**(②): 이미 노드가 있는 카테고리의 집을 사람이 바꿨으면 멈춘다 — 옛 집은
**그 카테고리 노드가 실제로 있는 다른 그래프**로 판정한다(이전 값을 따로 저장하지 않는다).
노드 수는 GraphStore 경유로 센다(접근 경계 — 카탈로그 모듈은 그래프를 열지 않는다).
"""
from __future__ import annotations

import json

from core import paths
from core.state import catalog, log, store

_LOG = log.get(__name__)


def count_nodes(layer, category):
    """층 그래프의 그 **주 카테고리** 노드 수 — 그래프가 아직 없으면 0."""
    from core.state.bootstrap import open_graph
    try:
        g = open_graph(layer)
    except FileNotFoundError:
        return 0
    return sum(1 for n in g.nodes.values() if n.get("category") == category)


def plan(configs=None, current=None, counter=count_nodes):
    """맞추기 계획 — 쓰지 않는다. `current`가 `None`이면 파일이 없다(처음).

    돌려주는 dict: `new`(파일이 없었다) · `add`[(카테고리, 층)] · `ask`[(카테고리, 층들)] ·
    `drop`[카테고리] · `stuck`[(카테고리, 집, 노드 수)] · `moved`[(카테고리, 새 집, 옛 그래프, 노드 수)] ·
    `catalog`(맞춘 뒤의 카탈로그 — 변경이 없으면 `current`와 같다).
    """
    from router import discover
    configs = configs or catalog._layer_configs()
    decl = catalog.declared_by(configs)
    out = {"new": current is None, "add": [], "ask": [], "drop": [], "stuck": [], "moved": []}
    if current is None:
        cat = catalog.draft(configs)
        cat.pop("_빈칸", None)
        out["ask"] = [(c, lays) for c, lays in sorted(decl.items()) if len(lays) > 1]
        out["add"] = [(c, lays[0]) for c, lays in sorted(decl.items()) if len(lays) == 1]
        out["catalog"] = cat
        return out
    cat = json.loads(json.dumps(current))              # 깊은 사본 — 원본은 비교용
    cats = cat.setdefault("categories", {})
    for c, lays in sorted(decl.items()):
        if c in cats:
            continue
        if len(lays) == 1:
            cats[c] = {"home": lays[0]}
            out["add"].append((c, lays[0]))
        else:
            cats[c] = {"home": ""}
            out["ask"].append((c, lays))
    for c in sorted(list(cats)):
        if c in decl:
            continue
        home = (cats[c] or {}).get("home")
        n = counter(home, c) if home else 0
        if n:
            out["stuck"].append((c, home, n))
        else:
            del cats[c]
            out["drop"].append(c)
    # ② 집 변경 — 집 밖 그래프에 그 카테고리 노드가 남아 있으면 옛 집이다
    for c, v in sorted(cats.items()):
        home = (v or {}).get("home")
        if not home or c not in decl:
            continue
        for lay in discover():
            if lay != home:
                n = counter(lay, c)
                if n:
                    out["moved"].append((c, home, lay, n))
    out["catalog"] = cat
    return out


def changed(p):
    """파일에 쓸 변경이 있나 — 처음이거나 더함·빈칸·제거가 있으면."""
    return p["new"] or bool(p["add"] or p["ask"] or p["drop"])


def blocked(p):
    """멈춰야 하나 — 사람이 정할 것(빈칸·노드가 남은 제거·집 변경)이 있으면."""
    return bool(p["ask"] or p["stuck"] or p["moved"])


def apply(p):
    """계획을 쓴다 — 원자 쓰기 · `common_version` +1(처음이면 1) · 로그에 근거 한 줄씩."""
    cat = p["catalog"]
    if not p["new"]:
        cat["common_version"] = int(cat.get("common_version") or 0) + 1
    target = paths.common()
    paths.ensure(target)
    store.atomic_write_bytes(target, (json.dumps(cat, ensure_ascii=False, indent=2)
                                      + "\n").encode("utf-8"))
    for c, lay in p["add"]:
        _LOG.info("공통 config + %s (home %s — %s만 선언)", c, lay, lay)
    for c, lays in p["ask"]:
        _LOG.info("공통 config + %s (home 빈칸 — 여러 층이 선언 %s)", c, lays)
    for c in p["drop"]:
        _LOG.info("공통 config − %s (어느 층도 선언하지 않고 노드 0)", c)
    _LOG.info("공통 config 저장 — v%s · %s", cat.get("common_version"), target)
    return cat
