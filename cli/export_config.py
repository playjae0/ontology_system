# -*- coding: utf-8 -*-
"""칸 0.3 — **config 지도 내보내기**(B173 · 읽기만 · ⑤파생 `export/`): 모델(`cli.config_map`)을 HTML 한 장 · 화면 요약 ·
JSON으로 낸다 · 두 모델의 뜻 차이를 잰다.

    python run.py export config [경로]              HTML 한 장(기본 export/config_map.html) + 화면 요약
    python run.py export config --json [경로]       같은 모델을 JSON으로(기본 export/config_map.json — 이름순 · 결정적)
    python run.py export config --from <layers 폴더> …  그 폴더(제안 — `work/config_next/layers`)를 읽는다(상태 루트 쓰기 0)
    python run.py export config --diff a.json b.json  두 모델의 뜻 차이만(category · home · also · name form · 층 categories ·
                                                     relation_patterns · pairs · 층에 걸린 pairs · uses · cross-layer edge) —
                                                     같으면 rc 0 · 다르면 rc 1 (B177 ① — 층 걸림도 잰다)

**화면 낱말은 config 키 이름**(B177 ① · 사용자 확정 2026-11-02 — 고칠 자리를 그 이름으로 찾는다 · 한국어는 설명에만) · 층은
`<층 layer>` 머리와 색 띠(그림의 점 색 = home 층 — 같은 색).

**관계 그림은 지금 뷰어를 다시 쓴다**(`cli.export.build_html` — 카테고리 하나 = 점 하나(home 층 · 색 축 `layer`) · 관계 패턴 하나 =
엣지 하나(선언한 층) · 끝점의 층이 다르면 뷰어 규칙 그대로 붉은 점선). 뷰어 쪽은 한 화면을 다 쓰는 그림이라 표와 한 장에
싣지 못하므로 `iframe srcdoc`으로 품는다 — 외부 주소 0 · 파일 하나로 열린다. 바깥 장은 보는 쪽 테마를 따른다.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from types import SimpleNamespace

from core import paths
from core.state import catalog
from cli import config_map as M
from cli.export import build_html, node_color, out_path

#: 뜻 차이에서 빼는 것 — 정의문 글 · 렌즈 · 골격 노드 수 · 점검 문면 · 경로 사유 · 쌍에서 온 cross-layer edge(층 걸림 행이 잰다)
#: 연결 포인트의 출처 → config 키(화면 · 대조)
FROM_KEY = {"관계 패턴": "relation_patterns", "위아래 쌍": "pairs"}
#: 점검 갈래 → 화면 낱말
LEVEL_KEY = {"거부": "reject", "경고": "warn", "표시": "info"}


def from_key(where):
    """연결 포인트 출처 → config 키 — 관계 패턴 `relation_patterns` · 위아래 쌍 `pairs` · 스키마 `schema: <doc_type>`."""
    return FROM_KEY.get(where) or (f"schema: {where.split(' ', 1)[1]}" if where.startswith("스키마 ") else where)


def cross_edges(model):
    """층을 넘는 엣지 — **엣지 하나에 한 줄**(B177 ① · 모델은 끝마다) `[(layer, src, rel, dst, 출처, [(끝, home)])]`."""
    by = {}
    for x in (model.get("links") or {}).get("cross") or []:
        by.setdefault((x["layer"], x["src"], x["rel"], x["dst"], x["from"]), []).append((x["end"], x["home"]))
    return [(*k, v) for k, v in by.items()]


def end_text(ends):
    """`end → home` 칸 — 한 끝이면 `dst → process` · 두 끝이 같은 층이면 `두 끝 → process` · 다르면 끝마다."""
    if len(ends) > 1 and len({h for _e, h in ends}) == 1:
        return f"두 끝 → {ends[0][1]}"
    return " · ".join(f"{e} → {h}" for e, h in ends)


def model_json(model):
    """모델 JSON 글 — 이름순 · 결정적(같은 상태면 바이트가 같다)."""
    return json.dumps(model, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- 뜻 차이
def _rows(model):
    """모델 → 뜻 행 집합 `{(갈래, 글)}` — 대조는 이 집합의 차이다 · 갈래는 config 키 이름(B177 ①)."""
    out = set()
    for lay, d in (model.get("layers") or {}).items():
        out |= {("categories", f"{lay}: {c}") for c in d.get("categories") or {}}
        out |= {("relation_patterns", f"{lay}: {p['src']} -{p['rel']}-> {p['dst']}" + (" (symmetric)" if p.get("symmetric") else ""))
                for p in d.get("patterns") or []}
        out |= {("uses", f"{lay}: {c}") for c in d.get("uses") or []}
        out |= {("pairs (layer)", f"{lay}: {s} -{r}-> {t}") for s, r, t in d.get("pairs") or []}   # 층 걸림(B177 ①)
    out |= {("pairs", f"{s} -{r}-> {t}") for s, r, t in model.get("pairs") or []}
    for c, v in (model.get("categories") or {}).items():
        out.add(("category", c))
        out.add(("home", f"{c} → {v.get('home')}"))
        out |= {("also", f"{c} also {o} {'·'.join(sorted(t))}") for o, t in (v.get("also") or {}).items()}   # 단은 포함만 본다(순서 뜻 0)
        out.add(("name form", f"{c}: {v.get('name_form')}"))
    lk = model.get("links") or {}
    out |= {("cross-layer edge", f"{x['layer']}: {x['src']} -{x['rel']}-> {x['dst']} · {x['end']} {x['category']} → home "
                                 f"{x['home']} · {from_key(x['from'])}")
            for x in lk.get("cross") or [] if x["from"] != "위아래 쌍"}
    out |= {("declared_by", f"{x['category']} {x['layers']} home {x['home']}") for x in lk.get("shared") or []}
    return out


def diff(a, b):
    """두 모델의 뜻 차이 — `[줄]`(`- ` a에만 · `+ ` b에만 · 갈래순) · 같으면 빈 목록."""
    ra, rb = _rows(a), _rows(b)
    return ([f"- {k} — {t}" for k, t in sorted(ra - rb)] + [f"+ {k} — {t}" for k, t in sorted(rb - ra)])


# ---------------------------------------------------------------- 관계 그림 (지금 뷰어)
def _world(model):
    """뷰어가 먹는 월드 — 카테고리 = 점(home 층 · 골격 카테고리는 seed) · relation_patterns · pairs = 엣지(그 층)."""
    world = {lay: SimpleNamespace(nodes={}, edges=[]) for lay in model["layers"]}
    for c, v in model["categories"].items():
        lay = v["home"] if v["home"] in world else next(iter(v["declared_by"]), None)
        if lay not in world:
            continue
        world[lay].nodes[f"C:{c}"] = {
            "id": f"C:{c}", "canonical": c, "category": c, "status": "seed" if v["skeleton_of"] else "confirmed",
            "aliases": [], "attrs": {},
            "provenance": [f"{d}: {model['layers'][d]['categories'].get(c, '')}" for d in v["declared_by"]]}
    for lay, d in model["layers"].items():
        world[lay].edges += [{"src": f"C:{p['src']}", "dst": f"C:{p['dst']}", "rel": p["rel"], "status": "confirmed",
                              "provenance": [f"{lay} relation_patterns"]} for p in d["patterns"]]
        world[lay].edges += [{"src": f"C:{s}", "dst": f"C:{t}", "rel": r, "status": "confirmed",
                              "provenance": [f"{lay} pairs (common.json)"]} for s, r, t in d["pairs"]]
    return world


# ---------------------------------------------------------------- HTML
_CSS = """:root{--bg:#ffffff;--fg:#1d2330;--dim:#5b6475;--line:#d8dce4;--panel:#f5f6f8;--bad:#c62828;--warn:#9a6700}
@media (prefers-color-scheme: dark){:root{--bg:#0f1115;--fg:#e6e6e6;--dim:#8b93a1;--line:#2a2f3a;--panel:#161a22;
--bad:#ff6b6b;--warn:#e0af68}}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);
font:13px/1.55 -apple-system,"Segoe UI","Noto Sans KR",sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px} h1{font-size:18px;margin:0 0 4px} h2{font-size:15px;margin:22px 0 8px}
h3{font-size:13px;margin:14px 0 6px} .sub{color:var(--dim)} .wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:4px 0 10px} th,td{border:1px solid var(--line);padding:4px 8px;
text-align:left;vertical-align:top} th{background:var(--panel);font-weight:600} code{font-size:12px}
.bad td{color:var(--bad);font-weight:600} .warn td{color:var(--warn)} .none{color:var(--dim)}
iframe{width:100%;height:560px;border:1px solid var(--line);border-radius:6px;background:#0f1115}
.band{border-left:6px solid var(--c);padding-left:8px} .chip{display:inline-block;width:10px;height:10px;border-radius:50%;
background:var(--c);margin:0 4px 0 6px;vertical-align:baseline}
.keys{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:10px 0}
.keys dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:6px 0 0} .keys dt{font-family:monospace}
.keys dd{margin:0;color:var(--dim)}"""


def _e(v):
    return html.escape("" if v is None else str(v))


def _table(head, rows, cls=None):
    if not rows:
        return '<p class="none">없음</p>'
    tr = "".join(f'<tr{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>' + "".join(f"<td>{_e(c)}</td>" for c in r)
                 + "</tr>" for r in rows)
    return ('<div class="wrap"><table><tr>' + "".join(f"<th>{_e(h)}</th>" for h in head) + "</tr>" + tr
            + "</table></div>")


#: 칸 이름 → 뜻 한 줄(설명 상자 — 칸 이름은 config 키 · 한국어는 설명에만 · B177 ①)
KEYS = (("home", "그 카테고리의 노드가 사는 층 (common.json)"),
        ("used_by", "그 카테고리를 쓰는 층 — 정의(home) ∪ uses · 자동 기록"),
        ("also", "겸 — 그 단의 노드가 다른 카테고리이기도 함"),
        ("no_path", "이름에 공정 경로를 안 붙임 + 사유 · 비어 있으면 붙임(기본)"),
        ("skeleton", "사람이 고정한 나무 · 목록 (층 config) — 이름 그대로"),
        ("pairs", "위아래 쌍 — lower · upper · rel · src(엣지가 떠나는 끝) · 정의문 (common.json 한 곳)"),
        ("uses", "그 층 문서가 쓰는 다른 층 카테고리 (층 config)"),
        ("name form", f"그 카테고리 노드의 이름 꼴 — {M.COORD_TOKEN}는 좌표 · 그 사이 자리는 위 노드(upper)"),
        ("relation_patterns", "그 층이 허용하는 (src, rel, dst) · symmetric = 대칭"))


def _chip(lay):
    return f'<span class="chip" style="--c:{node_color(lay)}"></span>{_e(lay)}'


def _layer_html(lay, d, coord):
    """층 하나 — `<층 layer>` 머리 · 색 띠(그림의 점 색) · categories · relation_patterns · key/value."""
    sk = d["skeleton"] or {}
    pol = d["polarity"] or {}
    only = {tuple(e) for e in d.get("pairs_only") or []}
    pairs = " · ".join(f"{s} -{r}-> {t}" + (" (pairs에서)" if (s, r, t) in only else "") for s, r, t in d["pairs"])
    note = "coord layer — 좌표 골격을 가진 층" if lay == coord else "좌표는 coord layer 골격에서"
    return (f'<h3 class="band" style="--c:{node_color(lay)}">&lt;{_e(lay)} layer&gt;</h3><p class="sub">{note}</p>'
            + _table(("categories", "정의문 첫 줄"), list(d["categories"].items()))
            + _table(("src", "rel", "dst", "symmetric"),
                     [(p["src"], p["rel"], p["dst"], "✓" if p["symmetric"] else "") for p in d["patterns"]])
            + _table(("key", "value"), [
                ("skeleton", f"{sk.get('type')} · {sk.get('category')} · nodes {sk.get('nodes')}" if sk else "—"),
                ("uses", " · ".join(d["uses"]) or "—"),
                ("relations", " · ".join(d["relations"]) or "—"),
                ("pairs (이 층에 걸린 것)", pairs or "—"),
                ("polarity", f"{' · '.join(pol.get('bind_categories') or [])} — {' · '.join(pol.get('values') or [])}"
                 if pol else "—"),
                ("mirrors", "declared" if d["mirrors"] else "—"),
                ("lenses (doc_type)", " · ".join(d["lenses"]) or "—")]))


def _no_path(v):
    """`no_path` 칸 — 사유 · 비면 「— (경로 붙임)」 · 골격이면 「(skeleton)」(모델의 경로 값에서)."""
    p = v["path"]
    return "(skeleton)" if p == "골격" else "— (경로 붙임)" if p == "씀" else p.split(" — ", 1)[-1] if p.startswith("안 씀") else p


def _pair_rows(model):
    """`pairs` 표 — 공통 정의 그대로(lower · upper · rel · src · 정의문) + 이름에 주는 것 · 옛 층 매핑에서만 온 엣지는 그 표시."""
    cats = model["categories"]
    sk = {c for c, v in cats.items() if v["skeleton_of"]}
    defs = model.get("pair_defs") or []
    rows = []
    for p in defs:
        if p["upper"] in sk:
            gives = "좌표 아래 (upper가 skeleton)"
        elif str((cats.get(p["lower"]) or {}).get("path") or "").startswith("안 씀"):
            gives = "— (lower가 no_path)"
        else:
            gives = f"upper 노드 아래 — {M.COORD_TOKEN}::<{p['upper']}>::{M.NAME_TOKEN}"
        rows.append((p["lower"], p["upper"], p["rel"], p.get("src") or "lower", p.get("정의문") or "", gives))
    seen = {catalog.pair_edge(p) for p in defs}
    return rows + [("—", "—", r, f"{s} → {t}", "(옛 층 매핑)", "—") for s, r, t in model["pairs"] if (s, r, t) not in seen]


def _uses_rows(model):
    """`uses` 표 — 층 · 쓰는 카테고리 · home · 쓰는 자리(그 층에서 그 카테고리가 끝인 엣지의 rel (출처))."""
    cross = (model.get("links") or {}).get("cross") or []
    out = []
    for x in (model.get("links") or {}).get("uses") or []:
        at = dict.fromkeys(f"{c['rel']} ({from_key(c['from'])})" for c in cross
                           if c["layer"] == x["layer"] and c["category"] == x["category"])
        out.append((x["layer"], x["category"], x["home"], " · ".join(at) or "—"))
    return out


def _checks_html(chk):
    out = ""
    for lv, cls in (("거부", "bad"), ("경고", "warn"), ("표시", None)):
        out += f"<h3>{LEVEL_KEY[lv]} {len(chk[lv])}</h3>" + _table(("from", "line"), [(x["from"], x["line"]) for x in chk[lv]], cls)
    return out


def head(model):
    """머리 요약 — `layers · categories · relation_patterns · pairs · cross-layer edges(엣지 수) · uses · reject · warn · info ·
    coord layer`(B177 ①)."""
    n = M.counts(model)
    co = model["coord"]
    return (" · ".join(f"{k} {v}" for k, v in (
        ("layers", n["층"]), ("categories", n["카테고리"]), ("relation_patterns", n["관계 패턴"]), ("pairs", n["위아래 쌍"]),
        ("cross-layer edges", len(cross_edges(model))), ("uses", n["쓰는 카테고리"]),
        ("reject", n["거부"]), ("warn", n["경고"]), ("info", n["표시"])))
        + f" · coord layer {co['layer']} ({co['category']})")


def render_html(model):
    """HTML 한 장 — 요약 · 설명 상자 · 관계 그림(지금 뷰어 · 색 = home 층) · layers · categories · pairs · cross-layer links · checks."""
    lk = model["links"]
    viewer = build_html(_world(model), query_panel=False, title="config map — categories · relation_patterns · pairs",
                        color_axis="layer")
    body = (f"<h1>config map</h1><div class=\"sub\">{_e(model.get('shape'))} · {_e(head(model))} · 읽기만(지금 config · "
            "카탈로그 · 등록부가 읽힌 그대로)</div>"
            '<div class="keys"><b>칸 이름은 config 키 그대로</b> — 고칠 자리를 그 이름으로 찾는다<dl>'
            + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in KEYS) + "</dl></div>"
            "<h2>graph — categories · relation_patterns · pairs</h2><p class=\"sub\">점 = 카테고리 · 색 = home 층 "
            + " ".join(_chip(lay) for lay in model["layers"])
            + " · 엣지 = relation_patterns · pairs · 층을 넘는 엣지는 붉은 점선</p>"
            f"<iframe title=\"graph\" srcdoc=\"{html.escape(viewer, quote=True)}\"></iframe>"
            "<h2>layers</h2>" + "".join(_layer_html(lay, d, model["coord"]["layer"]) for lay, d in model["layers"].items())
            + "<h2>categories — common.json</h2>"
            + _table(("category", "home", "used_by", "also", "no_path", "skeleton", "name form"),
                     [(c, v["home"], " · ".join(v["used_by"]),
                       " · ".join(f"{o}({'·'.join(t)})" for o, t in v["also"].items()) or "—", _no_path(v),
                       " · ".join(v["skeleton_of"]), v["name_form"]) for c, v in model["categories"].items()])
            + "<h2>pairs — common.json</h2>"
            + _table(("lower", "upper", "rel", "src", "정의문", "이름에 주는 것"), _pair_rows(model))
            + "<h2>cross-layer links</h2><h3>층을 넘는 엣지 — 엣지 하나에 한 줄 · 끝 카테고리의 home이 그 층이 아니다</h3>"
            + _table(("layer", "src", "rel", "dst", "end → home", "from"),
                     [(lay, s, r, t, end_text(ends), from_key(w)) for lay, s, r, t, w, ends in cross_edges(model)])
            + "<h3>uses — 층이 쓰는 다른 층 카테고리(누락은 checks)</h3>"
            + _table(("layer", "uses", "home", "쓰는 자리"), _uses_rows(model))
            + "<h3>여러 층이 정의한 카테고리 — 정의문은 home 한 곳</h3>"
            + _table(("category", "declared_by", "home"), [(x["category"], " · ".join(x["layers"]), x["home"]) for x in lk["shared"]])
            + "<h2>checks</h2>" + _checks_html(model["checks"]))
    return (f"<!doctype html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>config map</title><style>{_CSS}</style></head><body><main>{body}</main></body></html>\n")


# ---------------------------------------------------------------- 명령
def summary(model, where):
    """화면 요약 몇 줄 — 수 · 이름 꼴 · reject 문면(앞 다섯) · 파일 자리."""
    out = [f"[export] config map({model.get('shape')}) — {head(model)}"]
    out += [f"  name form — {c}: {v['name_form']}" for c, v in model["categories"].items()]
    bad = model["checks"]["거부"]
    out += [f"  [reject] {x['line']}" for x in bad[:5]]
    if len(bad) > 5:
        out.append(f"  … reject {len(bad) - 5} 더 — HTML checks 표")
    out.append(f"  → {paths.show(where)}")
    return out


def _read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(args):
    if args[:1] == ["--diff"]:
        if len(args) != 3:
            raise SystemExit("사용법: python run.py export config --diff a.json b.json")      # [사용법]
        lines = diff(_read(args[1]), _read(args[2]))
        print(f"[export] config map 대조 — {args[1]} ↔ {args[2]} · " + (f"다름 {len(lines)}" if lines else "같다"))
        for ln in lines:
            print(f"  {ln}")
        return 1 if lines else 0
    src = None
    if "--from" in args:
        i = args.index("--from")
        if i + 1 >= len(args):
            raise SystemExit("사용법: python run.py export config --from <layers 폴더> [--json 경로 | 경로]")   # [사용법]
        src, args = args[i + 1], args[:i] + args[i + 2:]
    model = M.build(src)
    if args[:1] == ["--json"]:
        out = out_path(args[1] if len(args) > 1 else None, "config_map.json")
        out.write_text(model_json(model), encoding="utf-8")
    else:
        out = out_path(args[0] if args else None, "config_map.html")
        out.write_text(render_html(model), encoding="utf-8")
    for ln in summary(model, out):
        print(ln)
    print("  ※ 읽기만 — config · 그래프 · 등록부 쓰기 0 · 외부 주소 0 · 파생물이다(고치는 자리는 config · bootstrap)")
    return 0
