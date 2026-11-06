# -*- coding: utf-8 -*-
"""칸 0.3 — **config 지도 내보내기**(B173 · 읽기만 · ⑤파생 `export/`): 모델(`cli.config_map`)을 HTML 한 장 · 화면 요약 ·
JSON으로 낸다 · 두 모델의 뜻 차이를 잰다.

    python run.py export config [경로]              HTML 한 장(기본 export/config_map.html) + 화면 요약
    python run.py export config --json [경로]       같은 모델을 JSON으로(기본 export/config_map.json — 이름순 · 결정적)
    python run.py export config --from <layers 폴더> …  그 폴더(제안 — `work/config_next/layers`)를 읽는다(상태 루트 쓰기 0)
    python run.py export config --diff a.json b.json  두 모델의 뜻 차이만(category · home · also · name form · 층 categories ·
                                                     relation_patterns · parent_pairs · 층에 걸린 parent_pairs · uses · cross-layer edge ·
                                                     온톨로지 맵의 선(종류 · 출처) · attributes) — 같으면 rc 0 · 다르면 rc 1
                                                     (실제 엣지 수는 상태마다 달라 뺀다 · B186 ①)

**화면 낱말은 config 키 이름**(B177 ① · 사용자 확정 2026-11-02 — 고칠 자리를 그 이름으로 찾는다 · 한국어는 설명에만) · 층은
`<층 layer>` 머리와 색 띠(그림의 점 색 = home 층 — 같은 색).

**관계 그림은 온톨로지 맵이다**(`cli.ontology_map` — B186 ①): 카테고리 수준의 지도를 인라인 SVG로 그린다(점 = 카테고리 · 색 = home
층 · 선 = 종류 색 · 층을 넘는 관계는 점선 · 같은 카테고리끼리의 선은 고리) — 인스턴스 뷰어의 거름판(status · made_by · 문서)은 지도에
뜻이 없어 쓰지 않는다 · 외부 주소 0 · 파일 하나로 열린다. 바깥 장은 보는 쪽 테마를 따른다.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from core import paths
from core.state import catalog
from cli import config_map as M, ontology_map as OM
from cli.export import out_path

#: 뜻 차이에서 빼는 것 — 정의문 글 · 렌즈 · 골격 노드 수 · 점검 문면 · 경로 사유 · 쌍에서 온 cross-layer edge(층 걸림 행이 잰다)
#: 연결 포인트의 출처 → config 키(화면 · 대조)
FROM_KEY = {"관계 패턴": "relation_patterns", "parent_pairs": "parent_pairs"}
#: 점검 갈래 → 화면 낱말
LEVEL_KEY = {"거부": "reject", "경고": "warn", "표시": "info"}


def from_key(where):
    """연결 포인트 출처 → config 키 — 관계 패턴 `relation_patterns` · `parent_pairs` `parent_pairs` · 스키마 `schema: <doc_type>`."""
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
        out |= {("parent_pairs (layer)", f"{lay}: {s} -{r}-> {t}") for s, r, t in d.get("pair_edges") or []}   # 층 걸림(B177 ①)
    out |= {("parent_pairs", f"{s} -{r}-> {t}") for s, r, t in model.get("pair_edges") or []}
    onto = model.get("ontology") or {}
    out |= {("ontology line", f"{x['src']} -{x['rel']}-> {x['dst']} · {x['kind']}" + (f" · {OM.CROSS}" if x["cross"] else "")
             + (" · symmetric" if x["symmetric"] else "") + f" · {' · '.join(x['sources'])}") for x in onto.get("lines") or []}
    out |= {("attributes", f"{x['category']}.{x['attribute']} · {x['where']}" + (" · 맥락형" if x["contextual"] else ""))
            for x in onto.get("attributes") or []}
    for c, v in (model.get("categories") or {}).items():
        out.add(("category", c))
        out.add(("home", f"{c} → {v.get('home')}"))
        out |= {("also", f"{c} also {o} {'·'.join(sorted(t))}") for o, t in (v.get("also") or {}).items()}   # 단은 포함만 본다(순서 뜻 0)
        out.add(("name form", f"{c}: {v.get('name_form')}"))
    lk = model.get("links") or {}
    out |= {("cross-layer edge", f"{x['layer']}: {x['src']} -{x['rel']}-> {x['dst']} · {x['end']} {x['category']} → home "
                                 f"{x['home']} · {from_key(x['from'])}")
            for x in lk.get("cross") or [] if x["from"] != "parent_pairs"}
    out |= {("declared_by", f"{x['category']} {x['layers']} home {x['home']}") for x in lk.get("shared") or []}
    return out


def renamed(model):
    """**옛 판 모델을 지금 판 이름으로 읽은 사본**(B188 ⓪ — `config_scope.renamed`와 같은 꼴 · 원본은 그대로) — 판 5 앞은 쌍에서 온
    연결 포인트의 출처가 한국어 설명 이름이었다: 그 판의 출처는 관계 패턴 · 쌍 · 스키마 셋뿐이라 관계 패턴 · 스키마 밖은 `parent_pairs`."""
    if (model.get("map_version") or 0) >= 5:
        return model
    lk = dict(model.get("links") or {})
    lk["cross"] = [x if x["from"] in FROM_KEY or x["from"].startswith("스키마 ") else {**x, "from": "parent_pairs"}
                   for x in lk.get("cross") or []]
    return {**model, "links": lk}


def version_note(a, b):
    """두 모델의 판이 다르면 한 줄(뜻 비교는 그대로 — 옛 판은 `renamed`로 읽었다) · 같으면 None."""
    va, vb = a.get("map_version"), b.get("map_version")
    return None if va == vb else f"  ※ 판이 다르다 — 판 {va} ↔ 판 {vb} · 옛 판의 이름은 지금 이름으로 읽어 견준다(뜻 비교는 그대로)"


def diff(a, b):
    """두 모델의 뜻 차이 — `[줄]`(`- ` a에만 · `+ ` b에만 · 갈래순) · 같으면 빈 목록 · 옛 판은 지금 이름으로 읽는다(`renamed`)."""
    ra, rb = _rows(renamed(a)), _rows(renamed(b))
    return ([f"- {k} — {t}" for k, t in sorted(ra - rb)] + [f"+ {k} — {t}" for k, t in sorted(rb - ra)])


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
.omap{max-width:900px;display:block;margin:6px auto;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
.omap .lab{font-size:10px;fill:var(--dim)} .omap .name{font-size:12px;fill:var(--fg);font-weight:600}
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
        ("parent_pairs", "카테고리 사이의 소속 관계 — lower · upper · rel · src(엣지가 떠나는 끝) · 정의문 (common.json 한 곳)"),
        ("uses", "그 층 문서가 쓰는 다른 층 카테고리 (층 config)"),
        ("name form", f"그 카테고리 노드의 이름 꼴 — {M.COORD_TOKEN}는 좌표 · 그 사이 자리는 위 노드(upper)"),
        ("relation_patterns", "그 층이 허용하는 (src, rel, dst) · symmetric = 대칭"))


def _chip(lay, color):
    return f'<span class="chip" style="--c:{color}"></span>{_e(lay)}'


def _layer_html(lay, d, coord, color):
    """층 하나 — `<층 layer>` 머리 · 색 띠(그림의 점 색) · categories · relation_patterns · key/value."""
    sk = d["skeleton"] or {}
    pol = d["polarity"] or {}
    only = {tuple(e) for e in d.get("pair_edges_only") or []}
    pairs = " · ".join(f"{s} -{r}-> {t}" + (" (parent_pairs에서)" if (s, r, t) in only else "") for s, r, t in d["pair_edges"])
    note = "coord layer — 좌표 골격을 가진 층" if lay == coord else "좌표는 coord layer 골격에서"
    return (f'<h3 class="band" style="--c:{color}">&lt;{_e(lay)} layer&gt;</h3><p class="sub">{note}</p>'
            + _table(("categories", "정의문 첫 줄"), list(d["categories"].items()))
            + _table(("src", "rel", "dst", "symmetric"),
                     [(p["src"], p["rel"], p["dst"], "✓" if p["symmetric"] else "") for p in d["patterns"]])
            + _table(("key", "value"), [
                ("skeleton", f"{sk.get('type')} · {sk.get('category')} · nodes {sk.get('nodes')}" if sk else "—"),
                ("uses", " · ".join(d["uses"]) or "—"),
                ("relations", " · ".join(d["relations"]) or "—"),
                ("parent_pairs (이 층에 걸린 것)", pairs or "—"),
                ("polarity", f"{' · '.join(pol.get('bind_categories') or [])} — {' · '.join(pol.get('values') or [])}"
                 if pol else "—"),
                ("mirrors", "declared" if d["mirrors"] else "—"),
                ("lenses (doc_type)", " · ".join(d["lenses"]) or "—")]))


def _no_path(v):
    """`no_path` 칸 — 사유 · 비면 「— (경로 붙임)」 · 골격이면 「(skeleton)」(모델의 경로 값에서)."""
    p = v["path"]
    return "(skeleton)" if p == "골격" else "— (경로 붙임)" if p == "씀" else p.split(" — ", 1)[-1] if p.startswith("안 씀") else p


def _pair_rows(model):
    """`parent_pairs` 표 — 공통 정의 그대로(lower · upper · rel · src · 정의문) + 이름에 주는 것 · 옛 층 매핑에서만 온 엣지는 그 표시."""
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
    return rows + [("—", "—", r, f"{s} → {t}", "(옛 층 매핑)", "—") for s, r, t in model["pair_edges"] if (s, r, t) not in seen]


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
    """머리 요약 — `layers · categories · relation_patterns · parent_pairs · cross-layer edges(엣지 수) · uses · reject · warn · info ·
    coord layer`(B177 ①)."""
    n = M.counts(model)
    co = model["coord"]
    return (" · ".join(f"{k} {v}" for k, v in (
        ("layers", n["층"]), ("categories", n["카테고리"]), ("relation_patterns", n["관계 패턴"]), ("parent_pairs", n["parent_pairs"]),
        ("cross-layer edges", len(cross_edges(model))), ("uses", n["쓰는 카테고리"]),
        ("reject", n["거부"]), ("warn", n["경고"]), ("info", n["표시"])))
        + f" · coord layer {co['layer']} ({co['category']})")


def _map_html(model):
    """**온톨로지 맵**(B186 ①) — 그림 한 장 + 선 표(relations) + 값 칸 표(attributes)."""
    onto = model.get("ontology") or {}
    n = OM.counts(onto)
    legend = " · ".join(f'<span style="color:{OM.COLORS[k]}">━</span> {k} {n[k]}' for k in OM.KINDS)
    rows = [(x["src"], x["rel"], x["dst"], x["kind"] + (f" · {OM.CROSS}" if x["cross"] else ""), " · ".join(x["sources"]),
             " · ".join(x["layers"]) or "—", "✓" if x["symmetric"] else "",
             "—" if x["edges"] is None else ("0 (선언만)" if x["edges"] == 0 else f"{x['edges']:,}"), x["same_node"] or "")
            for x in onto.get("lines") or []]
    return ("<h2>ontology map — 카테고리 수준의 지도</h2><p class=\"sub\">점 = 카테고리 · 색 = home 층 "
            + " ".join(_chip(lay, c) for lay, c in OM.layer_colors(model).items())
            + f" · 선 = (src, rel, dst) 하나 — {legend} · 점선 = {OM.CROSS} {n[OM.CROSS]} · 고리 {n['고리']} = 같은 카테고리끼리의 관계"
            f"(실제 그래프에서는 다른 두 노드) · 선언만 {n['선언만']}(그래프에 엣지 0) · 선 {n['선']}</p>"
            + OM.svg(model)
            + "<h3>relations — 선 하나에 한 줄(출처가 여럿이면 함께)</h3>"
            + _table(("src", "rel", "dst", "종류", "출처(config 키)", "층", "symmetric", "실제 엣지", "같은 노드 엣지"), rows)
            + "<h3>attributes — 값 칸</h3>"
            + _table(("category", "attribute", "정의한 자리", "맥락형"),
                     [(x["category"], x["attribute"], x["where"], "✓" if x["contextual"] else "")
                      for x in onto.get("attributes") or []]))


def render_html(model):
    """HTML 한 장 — 요약 · 설명 상자 · 온톨로지 맵(그림 · relations · attributes) · layers · categories · parent_pairs · cross-layer links · checks."""
    lk = model["links"]
    body = (f"<h1>config map</h1><div class=\"sub\">{_e(model.get('shape'))} · {_e(head(model))} · 읽기만(지금 config · "
            "카탈로그 · 등록부가 읽힌 그대로)</div>"
            '<div class="keys"><b>칸 이름은 config 키 그대로</b> — 고칠 자리를 그 이름으로 찾는다<dl>'
            + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in KEYS) + "</dl></div>"
            + _map_html(model)
            + "<h2>layers</h2>" + "".join(_layer_html(lay, d, model["coord"]["layer"], OM.layer_colors(model)[lay]) for lay, d in model["layers"].items())
            + "<h2>categories — common.json</h2>"
            + _table(("category", "home", "used_by", "also", "no_path", "skeleton", "name form"),
                     [(c, v["home"], " · ".join(v["used_by"]),
                       " · ".join(f"{o}({'·'.join(t)})" for o, t in v["also"].items()) or "—", _no_path(v),
                       " · ".join(v["skeleton_of"]), v["name_form"]) for c, v in model["categories"].items()])
            + "<h2>parent_pairs — common.json</h2>"
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
        a, b = _read(args[1]), _read(args[2])
        lines, note = diff(a, b), version_note(a, b)
        print(f"[export] config map 대조 — {args[1]} ↔ {args[2]} · " + (f"다름 {len(lines)}" if lines else "같다"))
        if note:
            print(note)
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
