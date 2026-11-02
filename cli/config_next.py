# -*- coding: utf-8 -*-
"""칸 0.1 — **옛 모양 config → 새 모양 제안 → 멈춤**(B174 ③): `bootstrap`이 옛 키를 보면 제안 · 보고를 ④작업
`work/config_next/`에 쓰고 멈춘다(그래프 · config · 등록부 쓰기 0). 사람이 지도로 앞뒤를 맞추고 복사한다.

옛 키(`catalog.old_shape` — 공통 `canonical_scope` · 층 `category_pair_map` · 집이 아닌 층의 카테고리 정의)를 읽는 자리는
옛 모양 감지와 여기(제안 짓기)뿐이다. 제안 규칙:
  ⓐ 옛 이름 규칙 목록(`bind` ∪ `nest`)에 없던 카테고리(골격 제외)는 경로 「안 씀」 + 사유 「이전 판 그대로 …」
  ⓑ 층 `category_pair_map`의 쌍은 위아래 쌍으로(엣지 방향 그대로) — 위 · 아래는 골격이 위 · 옛 nest가 아래 · 둘 다 아니면 키
     앞이 위(판단을 보고에 적는다) · **층끼리 같은 쌍에 다른 관계면 제안을 쓰지 않고 그 쌍을 문면으로**(사람이 고른다)
  ⓒ 집이 아닌 층의 카테고리 정의는 그 층 `uses`로 · 정의문은 집 층 것을 두고 다른 층 정의문은 보고에 나란히
  ⓓ 관계 패턴 · 등록 스키마(공용 좌표 블록 포함)에만 나오던 다른 층 카테고리도 `uses`로(골격 카테고리 포함)
  ⓔ 위아래 쌍과 같은 삼항은 층 `relation_patterns`에서 뺀다(정의문은 쌍으로) — 층 `relations` · 정의문 · 추출 입력 칸은 그대로
보고에는 **이름이 바뀌는 카테고리**(위가 일반 노드인 쌍의 아래인데 옛 nest에 없던 것 — 앞뒤 이름 꼴 · 노드 수)와 **층마다 새로
걸리는 위아래 쌍**(그 층이 두 카테고리를 다 말하는데 옛 그 층 매핑에 없던 것)이 먼저 보인다.
"""
from __future__ import annotations

import json
import shutil

from core import paths
from core.state import catalog

#: ⓐ의 사유 — 사람이 고쳐 쓴다
WHY_KEPT = "이전 판 그대로 — 사유를 적거나 지워서 「씀」으로"


def _old_rule(common, configs):
    sc = common.get("canonical_scope") or next((c["canonical_scope"] for _l, c in sorted(configs.items())
                                                 if c.get("canonical_scope")), {})
    return set(sc.get("bind_categories") or []), set(sc.get("nest_categories") or []), sc.get("sep") or "::"


def _schema_cats(schemas):
    """`{층: {카테고리}}` — 등록 스키마가 말하는 카테고리(공용 블록 필드 포함 · `target_layer` 필드는 그 층 몫이라 뺀다)."""
    from kit.gate_tables import load_blocks
    out = {}
    for sc in schemas:
        fields, _b = load_blocks(sc)
        for f in fields.values():
            for k in ("category", "target_category"):
                if isinstance(f, dict) and f.get(k) and not f.get("target_layer"):
                    out.setdefault(sc.get("layer"), set()).add(f[k])
    return out


def _pairs(configs, sk, nest):
    """ⓑ 층 `category_pair_map` → 위아래 쌍 · `(쌍 목록, 판단 줄, 멈춤 줄)`."""
    seen, stops = {}, []
    for lay, cfg in sorted(configs.items()):
        for k, rel in sorted((cfg.get("category_pair_map") or {}).items()):
            s, _, d = k.partition(",")
            seen.setdefault((s, d), {}).setdefault(rel, []).append(lay)
    out, why = [], []
    for (s, d), rels in sorted(seen.items()):
        if len(rels) > 1:
            stops.append(f"쌍 {s},{d}의 관계가 층마다 다르다 — " + " · ".join(f"{r}({'·'.join(ls)})" for r, ls in sorted(rels.items()))
                         + " · 한 관계로 고친 뒤 다시 bootstrap(추측하지 않는다)")
            continue
        rel = next(iter(rels))
        if (s in sk) != (d in sk):
            up, how = (s, d) if s in sk else (d, s), "골격이 위"
        elif (s in nest) != (d in nest):
            up, how = (d, s) if s in nest else (s, d), "옛 nest가 아래"
        else:
            up, how = (s, d), "키 앞이 위(판단 — 다르면 lower · upper를 바꿔 적는다)"
        upper, lower = up
        defs = [p.get("정의문") for c in configs.values() for p in c.get("relation_patterns") or []
                if (p.get("src"), p.get("rel"), p.get("dst")) == (s, rel, d) and p.get("정의문")]
        pair = {"lower": lower, "upper": upper, "rel": rel, "src": "upper" if s == upper else "lower"}
        if defs:
            pair["정의문"] = defs[0]
        out.append(pair)
        why.append(f"{s} -{rel}-> {d} → 아래 {lower} · 위 {upper} ({how})")
    return out, why, stops


def propose(common, configs, schemas=()):
    """**제안**(순수 함수 — 쓰지 않는다) — `{"common", "layers", "stops", "report"}` · `stops`가 있으면 제안을 쓰지 않는다."""
    common, configs = json.loads(json.dumps(common or {})), json.loads(json.dumps(configs or {}))
    sk = catalog.skeleton_categories(configs)
    bind, nest, sep = _old_rule(common, configs)
    cats = common.setdefault("categories", {})
    rep = {"안 씀": [], "쌍": [], "uses": [], "정의문": [], "패턴 뺌": [], "이름 바뀜": [], "새로 걸림": []}
    for c, v in sorted(cats.items()):                                          # ⓐ
        if c not in sk and c not in bind | nest and not (v or {}).get("no_path"):
            cats[c] = {**(v or {}), "no_path": WHY_KEPT}
            rep["안 씀"].append(c)
    pairs, rep["쌍"], stops = _pairs(configs, sk, nest)                       # ⓑ
    edges = {catalog.pair_edge(p) for p in pairs}
    old_pair = {lay: {(k.partition(",")[0], r, k.partition(",")[2]) for k, r in (c.get("category_pair_map") or {}).items()}
                for lay, c in configs.items()}
    sc_cats = _schema_cats(schemas)
    for lay, cfg in sorted(configs.items()):
        own = cfg.get("categories") or {}
        uses = list(cfg.get("uses") or [])
        for c in sorted(own):                                                  # ⓒ
            h = (cats.get(c) or {}).get("home")
            if h and h != lay:
                rep["정의문"].append(f"'{c}' — 집 {h}: {(configs.get(h, {}).get('categories') or {}).get(c, '')} ‖ "
                                     f"{lay}: {own[c]} (이 층 추출이 다시 돈다)")
                del own[c]
                uses.append(c)
        talk = {x for p in cfg.get("relation_patterns") or [] for x in (p.get("src"), p.get("dst")) if x}
        for c in sorted((talk | sc_cats.get(lay, set())) - set(own) - set(uses)):   # ⓓ
            uses.append(c)
        if uses:
            rep["uses"].append(f"{lay}: {' · '.join(uses)}")
        keep = [p for p in cfg.get("relation_patterns") or [] if (p.get("src"), p.get("rel"), p.get("dst")) not in edges]
        rep["패턴 뺌"] += [f"{lay}: {p['src']} -{p['rel']}-> {p['dst']}" for p in cfg.get("relation_patterns") or []
                          if p not in keep]
        new = {}
        for k, v in cfg.items():                                               # 키 차례를 지킨다 — 매핑 자리에 uses
            if k in catalog.OLD_LAYER_KEYS:
                if k == "category_pair_map":
                    new["uses"] = uses
                continue
            new[k] = keep if k == "relation_patterns" else v
        new.setdefault("uses", uses)
        configs[lay] = new
        spk = catalog.spoken(new)
        rep["새로 걸림"] += [f"{lay}: {s} -{r}-> {d}" for s, r, d in sorted(edges)
                           if {s, d} <= spk and (s, r, d) not in old_pair.get(lay, set())]
    for k in catalog.OLD_COMMON_KEYS:
        common.pop(k, None)
    common["pairs"], common["sep"] = pairs, sep
    for p in pairs:                                                            # 이름이 바뀌는 카테고리
        if p["upper"] not in sk and p["lower"] not in nest:
            rep["이름 바뀜"].append((p["lower"], p["upper"]))
    return {"common": common, "layers": configs, "stops": stops, "report": rep}


def _counts(cat_names):
    from core.state.catalog_sync import count_nodes
    return {c: count_nodes(catalog.home(c), c) if catalog.home(c) else 0 for c in cat_names}


def report_md(prop, counts=None):
    """보고 md 글 — 이름이 바뀌는 카테고리 · 새로 걸리는 쌍 먼저 · ⓐ ~ ⓔ."""
    rep, counts = prop["report"], counts or {}
    L = ["# config 새 모양 제안 — 보고 (B174 ③)", "",
         "> 제안은 `layers/`와 같은 모양이다 · 옛 파일은 `옛/`에 남았다 · 지도로 앞뒤를 맞춘 뒤 복사한다(화면의 다음 줄).", "",
         "## 이름이 바뀌는 카테고리 (재구축이 필요하다)", ""]
    L += [f"- `{lo}` — 지금 `<공정>::<이름>` → 제안 `<공정>::<{up}>::<이름>`(위 {up}가 이어지면) · 노드 {counts.get(lo, 0):,} · "
          f"새 인입 전에 python run.py rebuild" for lo, up in rep["이름 바뀜"]] or ["- 없음"]
    L += ["", "## 층마다 새로 걸리는 위아래 쌍 (그 층이 두 카테고리를 다 말한다 — 옛 그 층 매핑에는 없었다)", ""]
    L += [f"- {x}" for x in rep["새로 걸림"]] or ["- 없음"]
    for title, key in (("ⓐ 경로 「안 씀」(옛 이름 규칙 밖 — 사유를 적거나 지워서 「씀」으로)", "안 씀"),
                       ("ⓑ 위아래 쌍(옛 층 매핑에서 — 위 · 아래 판단)", "쌍"), ("ⓒ 집이 아닌 층의 정의문(집 층 것을 둔다 — 나란히)", "정의문"),
                       ("ⓓ uses(층이 쓰는 다른 층 카테고리 — 골격 포함)", "uses"), ("ⓔ 층 패턴에서 뺀 삼항(위아래 쌍과 같다)", "패턴 뺌")):
        L += ["", f"## {title}", ""] + ([f"- {x}" for x in rep[key]] or ["- 없음"])
    return "\n".join(L) + "\n"


def write(prop):
    """제안 · 옛 사본 · 보고를 `work/config_next/`에 쓴다(상태 루트의 `layers/`는 건드리지 않는다) — 보고 파일 자리."""
    root = paths.config_next()
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(paths.layers(), paths.config_next("옛", "layers"))
    shutil.copytree(paths.layers(), paths.config_next("layers"))
    paths.config_next("layers", "common.json").write_text(
        json.dumps(prop["common"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for lay, cfg in prop["layers"].items():
        paths.config_next("layers", lay, "config.json").write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rp = paths.config_next("보고.md")
    rp.write_text(report_md(prop, _counts([lo for lo, _u in prop["report"]["이름 바뀜"]])), encoding="utf-8")
    return rp


def _state():
    """상태 루트의 옛 config 그대로 — `(공통, {층: 층 config}, 등록 스키마들)`."""
    from core.state import registry
    common = json.loads(paths.common().read_text(encoding="utf-8")) if paths.common().exists() else {}
    schemas = [s for dt in sorted(registry.all_doc_types()) for s in [registry.schema_of(dt)] if s]
    return common, catalog._layer_configs(), schemas


def screen(dry_run=False):
    """`bootstrap`의 옛 모양 관문 — 옛 모양이 아니면 None(지나간다) · 옛 모양이면 제안 · 보고를 쓰고(--dry-run은 쓰지 않는다) 1."""
    common, configs, schemas = _state()
    olds = catalog.old_shape(configs, common)
    if not olds:
        return None
    print(f"[bootstrap] 옛 모양 config — {len(olds)}곳 · 새 모양(공통 config: 카테고리 경로 · 위아래 쌍 / 층 config: 집 "
          f"카테고리 정의문 · uses)으로 옮긴다")
    for m in olds:
        print(f"  · {m}")
    prop = propose(common, configs, schemas)
    for m in prop["stops"]:
        print(f"[bootstrap] [멈춤] {m}")
    if prop["stops"]:
        return 1
    if dry_run:
        print("  (--dry-run — 제안을 쓰지 않는다 · --dry-run 없이 치면 work/config_next/에 제안 · 보고를 쓴다)")
        return 1
    rp = write(prop)
    nxt, lay = paths.config_next(), paths.layers()                 # 셸 위치와 무관하게 — 절대 경로
    rep = prop["report"]
    print(f"[bootstrap] 제안 → {paths.show(nxt)} · 보고 {paths.show(rp)} · 이름이 바뀌는 카테고리 {len(rep['이름 바뀜'])} · "
          f"층마다 새로 걸리는 쌍 {len(rep['새로 걸림'])} · 그래프 · config · 등록부 쓰기 0")
    print("  ▶ 다음 줄 — 보고를 읽고 지도로 앞뒤를 맞춘 뒤 복사한다:")
    print(f"     python run.py export config --json {nxt}/지금.json")
    print(f"     python run.py export config --from {nxt}/layers --json {nxt}/제안.json")
    print(f"     python run.py export config --diff {nxt}/지금.json {nxt}/제안.json")
    print(f"     cp -r {nxt}/layers/. {lay}/      (옛 파일은 {nxt}/옛/에 남아 있다)")
    print("     python run.py bootstrap")
    return 1
