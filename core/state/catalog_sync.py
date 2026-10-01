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


def skeleton_layers(configs=None):
    """골격 카테고리 → 그 골격을 가진 층 목록(B93 ①) — 층 config `skeleton.category`.

    `bootstrap`은 골격 노드를 **그 골격을 가진 층의 그래프에** 심는다 — 그래서 골격 카테고리의
    집은 골격이 이미 정했다(사람에게 물을 것이 아니다).
    """
    out = {}
    for lay, cfg in sorted((configs or catalog._layer_configs()).items()):
        c = (cfg.get("skeleton") or {}).get("category")
        if c:
            out.setdefault(c, []).append(lay)
    return out


def plan(configs=None, current=None, counter=count_nodes):
    """맞추기 계획 — 쓰지 않는다. `current`가 `None`이면 파일이 없다(처음).

    돌려주는 dict: `new`(파일이 없었다) · `add`[(카테고리, 층, 골격인가)] · `fill`[(카테고리, 층)]
    (빈칸을 골격 층으로) · `ask`[(카테고리, 층들)] · `drop`[카테고리] · `stuck`[(카테고리, 집, 노드 수)] ·
    `moved`[(카테고리, 새 집, 옛 그래프, 노드 수)] · `sk_dup`[(카테고리, 골격 층들)] ·
    `sk_home`[(카테고리, 채운 집, 골격 층, 그 집의 노드 수)] · `fix`[(카테고리, 옛 집, 골격 층)]
    (어긋난 집 — 노드 0이라 고쳤다 · B95) · `catalog`(맞춘 뒤의 카탈로그).

    **골격 카테고리가 먼저다**(B93): 골격이 한 층에 있으면 집은 그 층 — 여러 층이 선언해도
    자동 추가 · 빈칸이면 채운다 · 채운 집이 다르면 멈춘다(ⓖ — 집 변경 검사보다 먼저) · 두 층의
    골격이 같은 카테고리면 멈춘다(ⓕ). 나머지 카테고리는 B92 규칙 그대로다.
    """
    from router import discover
    configs = configs or catalog._layer_configs()
    decl = catalog.declared_by(configs)
    sk = skeleton_layers(configs)
    out = {"new": current is None, "add": [], "fill": [], "ask": [], "drop": [], "stuck": [],
           "moved": [], "sk_dup": [], "sk_home": [], "fix": [], "used": [], "before": current}
    if current is None:                                 # 처음 — 층 선언에서 같은 규칙으로 세운다
        current = catalog.draft(configs)
        current.pop("_빈칸", None)
        current["categories"] = {}
    cat = json.loads(json.dumps(current))              # 깊은 사본 — 원본은 비교용
    cats = cat.setdefault("categories", {})
    for c, lays in sorted(sk.items()):
        if len(lays) > 1:
            out["sk_dup"].append((c, lays))
            continue
        home = (cats.get(c) or {}).get("home")
        if c not in cats:
            cats[c] = {"home": lays[0]}
            out["add"].append((c, lays[0], True))
        elif not home:
            cats[c]["home"] = lays[0]
            out["fill"].append((c, lays[0]))
        elif home != lays[0]:
            # **어긋난 집 그래프에 그 카테고리 노드가 0이면 고친다**(B95 ①) — 골격 노드는 늘 골격
            # 층 그래프에 심기므로 옛 집 값일 뿐이다. 노드가 있으면 멈춘다(ⓖ — 노드 수를 말한다).
            n = counter(home, c)
            if n:
                out["sk_home"].append((c, home, lays[0], n))
            else:
                cats[c]["home"] = lays[0]
                out["fix"].append((c, home, lays[0]))
    for c, lays in sorted(decl.items()):
        if c in cats or c in sk:
            continue
        if len(lays) == 1:
            cats[c] = {"home": lays[0]}
            out["add"].append((c, lays[0], False))
        else:
            cats[c] = {"home": ""}
            out["ask"].append((c, lays))
    for c in sorted(list(cats)):
        if c in decl or c in sk:
            continue
        home = (cats[c] or {}).get("home")
        n = counter(home, c) if home and not out["new"] else 0
        if n:
            out["stuck"].append((c, home, n))
        else:
            del cats[c]
            out["drop"].append(c)
    # ② 집 변경 — 집 밖 그래프에 그 카테고리 노드가 남아 있으면 옛 집이다
    #    (골격 모순이 있는 카테고리는 그 문면이 원인을 말한다 — 여기서 겹쳐 말하지 않는다)
    _sk_bad = {c for c, *_ in out["sk_dup"] + out["sk_home"]}
    for c, v in sorted(cats.items()):
        home = (v or {}).get("home")
        if not home or c not in decl or c in _sk_bad or out["new"]:
            continue
        for lay in discover():
            if lay != home:
                n = counter(lay, c)
                if n:
                    out["moved"].append((c, home, lay, n))
    # **쓰는 층(`used_by`)은 결과 기록이다**(B94 ①) — 위 판정은 이것을 읽지 않는다(낡은 값이
    # 판정을 이기지 않게). 층 config의 선언에서 다시 적는다 · 손으로 고친 값도 되돌린다.
    for c in sorted(cats):
        want = list(decl.get(c, []))
        have = (cats[c] or {}).get("used_by")
        if have != want:
            cats[c]["used_by"] = want
            out["used"].append((c, have, want))
    out["catalog"] = cat
    return out


def existing_lines(p, configs=None):
    """새 카테고리 경고의 재료(B94 ②) — **기존 카탈로그**를 카테고리마다 한 줄:
    `home` · `used_by` · 선언한 층들의 정의문 앞부분. 처음(기존 없음)이면 빈 목록이다.

    표시일 뿐이다 — 유사도·LLM 판정은 하지 않는다(같은 뜻인지는 사람이 본다).
    """
    before = (p.get("before") or {}).get("categories") or {}
    if p["new"] or not before:
        return []
    configs = configs or catalog._layer_configs()
    decl = catalog.declared_by(configs)
    out = []
    for c, v in sorted(before.items()):
        defs = []
        for lay in decl.get(c, []):
            d = ((configs.get(lay) or {}).get("categories") or {}).get(c)
            if d:
                defs.append(f"{lay}: {' '.join(str(d).split())[:40]}")
        out.append(f"'{c}' home {(v or {}).get('home') or '(빈칸)'} · used_by {decl.get(c, [])}"
                   + (f" — {' / '.join(defs)}" if defs else ""))
    return out


def scope_line(p, category):
    """새 카테고리의 **이름 규칙 상태** 한 줄(B95 ②) — 표시일 뿐(자동 추정 0).

    `canonical_scope.bind_categories` 안이면 이름에 공정 접두가 붙는다(공정이 다르면 다른 노드 ·
    좌표 미해소면 노드를 만들지 않는다). 판정 기준은 질문 하나 — 공정을 모르면 뜻이 없는가.
    """
    bind = ((p["catalog"].get("canonical_scope") or {}).get("bind_categories") or [])
    if category in bind:
        return f"이름 규칙: '{category}'는 공정 스코프 적용(bind_categories 안)"
    return (f"이름 규칙: '{category}'는 미적용 — 공정을 모르면 뜻이 없는 것(공정마다 다른 실물·값)이면 "
            f"공통 config canonical_scope.bind_categories에 넣는다 · 노드가 생기기 전에 정한다")


def new_categories(p):
    """카탈로그에 **없던** 카테고리 — `[(카테고리, 선언한 층들)]`(더함 · 빈칸 더함 · 골격 모두)."""
    decl = catalog.declared_by()
    added = [c for c, *_ in p["add"]] + [c for c, _l in p["ask"]]
    return [(c, decl.get(c, [])) for c in added]


def changed(p):
    """파일에 쓸 변경이 있나 — 처음이거나 더함·채움·빈칸·제거·쓰는 층 변경이 있으면."""
    return p["new"] or bool(p["add"] or p["fill"] or p["fix"] or p["ask"] or p["drop"] or p["used"])


def blocked(p):
    """멈춰야 하나 — 사람이 정할 것(빈칸·노드가 남은 제거·집 변경·골격 모순)이 있으면."""
    return bool(p["ask"] or p["stuck"] or p["moved"] or p["sk_dup"] or p["sk_home"])


def apply(p):
    """계획을 쓴다 — 원자 쓰기 · `common_version` +1(처음이면 1) · 로그에 근거 한 줄씩."""
    cat = p["catalog"]
    if not p["new"]:
        cat["common_version"] = int(cat.get("common_version") or 0) + 1
    target = paths.common()
    paths.ensure(target)
    store.atomic_write_bytes(target, (json.dumps(cat, ensure_ascii=False, indent=2)
                                      + "\n").encode("utf-8"))
    for c, lay, skel in p["add"]:
        _LOG.info("공통 config + %s (home %s — %s)", c, lay,
                  f"골격이 {lay}에 있다" if skel else f"{lay}만 선언")
    for c, old, lay in p["fix"]:
        _LOG.info("공통 config %s home %s → %s (골격이 %s에 있다 · %s 그래프에 %s 노드 0)",
                  c, old, lay, lay, old, c)
    for c, lay in p["fill"]:
        _LOG.info("공통 config %s home 빈칸 → %s (골격이 %s에 있다)", c, lay, lay)
    for c, lays in p["ask"]:
        _LOG.info("공통 config + %s (home 빈칸 — 여러 층이 선언 %s)", c, lays)
    for c, have, want in p["used"]:
        if p["new"] or have is None:
            continue                                   # 새 항목은 위의 + 줄이 말한다
        plus, minus = sorted(set(want) - set(have or [])), sorted(set(have or []) - set(want))
        _LOG.info("used_by '%s'%s%s (used_by는 층 config에서 온다)", c,
                  "".join(f" + {x}" for x in plus), "".join(f" − {x}" for x in minus))
    for c in p["drop"]:
        _LOG.info("공통 config − %s (어느 층도 선언하지 않고 노드 0)", c)
    _LOG.info("공통 config 저장 — v%s · %s", cat.get("common_version"), target)
    return cat


def coord_status(configs=None):
    """골격 카테고리마다 **자기 좌표 규칙이 켜졌나** — `[(경고인가, 문면)]` (B93 ③ · 표시일 뿐 거부 아님).

    규칙이 돌려면 둘이 다 있어야 한다: 공통 config의 겸(`also`) · 겸 단 골격 노드의 별칭(골격
    스냅샷 — 심은 뒤의 것). 켜짐 · 꺼짐(겸 없음) · 반쪽(겸은 있는데 겸 단 별칭 0) 셋.
    """
    snap = store.read(store.SKELETON_LIST, {})
    try:
        cats = catalog.load().get("categories") or {}
    except catalog.CatalogError:
        return []
    out = []
    for c, lays in sorted(skeleton_layers(configs).items()):
        lay = lays[0]
        also = (cats.get(c) or {}).get("also") or {}
        head = f"골격 '{c}'({lay})"
        if not also:
            out.append((False, f"{head}: 겸 없음 — 골격 노드 이름 + 다른 카테고리 표기는 새 노드가 "
                               f"된다(자기 좌표 규칙 꺼짐)"))
            continue
        tiers = {t for ts in also.values() for t in (ts or [])}
        nodes = (snap.get(lay) or {}).get("nodes") or []
        n = sum(len(x.get("aliases") or []) for x in nodes if x.get("tier") in tiers)
        what = " · ".join(f"겸 {o}({'·'.join(ts)})" for o, ts in sorted(also.items()))
        if n:
            out.append((False, f"{head}: {what} · 겸 단 별칭 {n}개"))
        else:
            out.append((True, f"{head}: {what}인데 겸 단 별칭 0 — 별칭이 없으면 자기 좌표 규칙이 "
                              f"돌지 않는다" + ("" if nodes else " (골격을 아직 심지 않았다)")))
    return out
