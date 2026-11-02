# -*- coding: utf-8 -*-
"""칸 0.3 — **config 지도 내보내기**(B173 · 읽기만 · ⑤파생 `export/`): 모델(`cli.config_map`)을 HTML 한 장 · 화면 요약 ·
JSON으로 낸다 · 두 모델의 뜻 차이를 잰다.

    python run.py export config [경로]              HTML 한 장(기본 export/config_map.html) + 화면 요약
    python run.py export config --json [경로]       같은 모델을 JSON으로(기본 export/config_map.json — 이름순 · 결정적)
    python run.py export config --diff a.json b.json  두 모델의 뜻 차이만(카테고리 · 집 · 겸 · 이름 규칙 · 관계 패턴 ·
                                                     위아래 매핑 · 연결 포인트) — 같으면 rc 0 · 다르면 rc 1

**관계 그림은 지금 뷰어를 다시 쓴다**(`cli.export.build_html` — 카테고리 하나 = 점 하나(집 층) · 관계 패턴 하나 = 엣지
하나(선언한 층) · 끝점의 층이 다르면 뷰어 규칙 그대로 붉은 점선). 뷰어 쪽은 한 화면을 다 쓰는 그림이라 표와 한 장에
싣지 못하므로 `iframe srcdoc`으로 품는다 — 외부 주소 0 · 파일 하나로 열린다. 바깥 장은 보는 쪽 테마를 따른다.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from types import SimpleNamespace

from core import paths
from cli import config_map as M
from cli.export import build_html, out_path

#: 뜻 차이를 재는 칸 — 정의문 글 · 렌즈 · 골격 노드 수 · 점검 문면은 뜻이 아니다(모양 이전의 대조 대상 밖)
_DIFF_LAYER = ("categories", "patterns", "pair_map")
_DIFF_CAT = ("home", "also", "naming")


def model_json(model):
    """모델 JSON 글 — 이름순 · 결정적(같은 상태면 바이트가 같다)."""
    return json.dumps(model, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- 뜻 차이
def _rows(model):
    """모델 → 뜻 행 집합 `{(갈래, 글)}` — 대조는 이 집합의 차이다."""
    out = set()
    for lay, d in (model.get("layers") or {}).items():
        out |= {("층 카테고리", f"{lay}: {c}") for c in d.get("categories") or {}}
        out |= {("관계 패턴", f"{lay}: {p['src']} -{p['rel']}-> {p['dst']}" + (" (대칭)" if p.get("symmetric") else ""))
                for p in d.get("patterns") or []}
        out |= {("위아래 매핑", f"{lay}: {k} → {v}") for k, v in (d.get("pair_map") or {}).items()}
    for c, v in (model.get("categories") or {}).items():
        out.add(("카테고리", c))
        out.add(("집", f"{c} → {v.get('home')}"))
        out |= {("겸", f"{c} 겸 {o} {'·'.join(sorted(t))}") for o, t in (v.get("also") or {}).items()}   # 단은 포함만 본다(순서 뜻 0)
        out.add(("이름 규칙", f"{c}: {v.get('naming')}"))
    lk = model.get("links") or {}
    out |= {("걸침", f"{x['layer']}: {x['src']} -{x['rel']}-> {x['dst']} · 끝 {x['category']}(집 {x['home']}) · {x['from']}")
            for x in lk.get("cross") or []}
    out |= {("선언 없이 씀", f"{x['layer']}: {x['category']}(집 {x['home']}) · {'·'.join(x['via'])}")
            for x in lk.get("uses") or []}
    out |= {("여러 층 선언", f"{x['category']} {x['layers']} 집 {x['home']}") for x in lk.get("shared") or []}
    return out


def diff(a, b):
    """두 모델의 뜻 차이 — `[줄]`(`- ` a에만 · `+ ` b에만 · 갈래순) · 같으면 빈 목록."""
    ra, rb = _rows(a), _rows(b)
    return ([f"- {k} — {t}" for k, t in sorted(ra - rb)] + [f"+ {k} — {t}" for k, t in sorted(rb - ra)])


# ---------------------------------------------------------------- 관계 그림 (지금 뷰어)
def _world(model):
    """뷰어가 먹는 월드 — 카테고리 = 점(집 층 · 골격 카테고리는 seed) · 관계 패턴 = 엣지(선언한 층)."""
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
                              "provenance": [f"{lay} 관계 패턴"]} for p in d["patterns"]]
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
iframe{width:100%;height:560px;border:1px solid var(--line);border-radius:6px;background:#0f1115}"""


def _e(v):
    return html.escape("" if v is None else str(v))


def _table(head, rows, cls=None):
    if not rows:
        return '<p class="none">없음</p>'
    tr = "".join(f'<tr{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>' + "".join(f"<td>{_e(c)}</td>" for c in r)
                 + "</tr>" for r in rows)
    return ('<div class="wrap"><table><tr>' + "".join(f"<th>{_e(h)}</th>" for h in head) + "</tr>" + tr
            + "</table></div>")


def _layer_html(lay, d):
    sk = d["skeleton"] or {}
    pol = d["polarity"] or {}
    return (f"<h3>층 {_e(lay)}</h3>"
            + _table(("카테고리", "정의문 첫 줄"), [(c, t) for c, t in d["categories"].items()])
            + _table(("출발", "관계", "도착", "대칭"),
                     [(p["src"], p["rel"], p["dst"], "대칭" if p["symmetric"] else "") for p in d["patterns"]])
            + _table(("항목", "값"), [
                ("골격", f"{sk.get('type')} · {sk.get('category')} · 노드 {sk.get('nodes')}" if sk else "없음"),
                ("관계 목록", " · ".join(d["relations"]) or "없음"),
                ("위아래 매핑", " · ".join(f"{k} → {v}" for k, v in d["pair_map"].items()) or "없음"),
                ("극성", f"{' · '.join(pol.get('bind_categories') or [])} — {' · '.join(pol.get('values') or [])}"
                 if pol else "없음"),
                ("미러", "선언" if d["mirrors"] else "없음"),
                ("렌즈로 쓰는 doc_type", " · ".join(d["lenses"]) or "없음")]))


def _checks_html(chk):
    out = ""
    for lv, cls in (("거부", "bad"), ("경고", "warn"), ("표시", None)):
        out += f"<h3>{lv} {len(chk[lv])}</h3>" + _table(("출처", "문면"), [(x["from"], x["line"]) for x in chk[lv]], cls)
    return out


def render_html(model):
    """HTML 한 장 — 요약 · 관계 그림(지금 뷰어) · 층 · 카테고리 · 연결 포인트 · 점검."""
    n = M.counts(model)
    lk = model["links"]
    viewer = build_html(_world(model), query_panel=False, title="config 지도 — 카테고리 · 관계 패턴")
    head = " · ".join(f"{k} {v}" for k, v in n.items())
    body = (f"<h1>config 지도</h1><div class=\"sub\">{_e(head)} · 좌표 층 {_e(model['coord']['layer'])}"
            f"({_e(model['coord']['category'])}) · 읽기만(지금 config · 카탈로그 · 등록부가 읽힌 그대로)</div>"
            "<h2>관계 그림</h2><p class=\"sub\">카테고리 = 점(집 층) · 관계 패턴 = 엣지(선언한 층) · 층을 넘는 엣지는 "
            "붉은 점선(걸침이 될 수 있는 자리)</p>"
            f"<iframe title=\"관계 그림\" srcdoc=\"{html.escape(viewer, quote=True)}\"></iframe>"
            "<h2>층</h2>" + "".join(_layer_html(lay, d) for lay, d in model["layers"].items())
            + "<h2>카테고리</h2>"
            + _table(("카테고리", "집", "선언한 층", "겸", "이름 규칙", "골격"),
                     [(c, v["home"], " · ".join(v["declared_by"]),
                       " · ".join(f"{o}({'·'.join(t)})" for o, t in v["also"].items()), v["naming"],
                       " · ".join(v["skeleton_of"])) for c, v in model["categories"].items()])
            + "<h2>층 사이 연결 포인트</h2><h3>걸침이 될 수 있는 엣지 — 끝 카테고리의 집이 그 층이 아니다</h3>"
            + _table(("층", "출발", "관계", "도착", "끝", "끝의 집", "출처"),
                     [(x["layer"], x["src"], x["rel"], x["dst"], x["category"], x["home"], x["from"]) for x in lk["cross"]])
            + "<h3>선언 없이 관계 패턴에서만 쓰는 카테고리</h3>"
            + _table(("층", "카테고리", "집", "관계"), [(x["layer"], x["category"], x["home"], " · ".join(x["via"]))
                                                   for x in lk["uses"]])
            + "<h3>여러 층이 선언한 카테고리(렌즈 겹침 — 노드는 집 하나)</h3>"
            + _table(("카테고리", "선언한 층", "집"), [(x["category"], " · ".join(x["layers"]), x["home"]) for x in lk["shared"]])
            + "<h2>점검</h2>" + _checks_html(model["checks"]))
    return (f"<!doctype html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>config 지도</title><style>{_CSS}</style></head><body><main>{body}</main></body></html>\n")


# ---------------------------------------------------------------- 명령
def summary(model, where):
    """화면 요약 몇 줄 — 수 · 거부 문면(앞 다섯) · 파일 자리."""
    n = M.counts(model)
    out = [f"[export] config 지도 — 층 {n['층']} · 카테고리 {n['카테고리']} · 관계 패턴 {n['관계 패턴']} · 연결 포인트 "
           f"걸침 {n['걸침']} · 선언 없이 씀 {n['선언 없이 씀']} · 여러 층 선언 {n['여러 층 선언']} · 거부 {n['거부']} · "
           f"경고 {n['경고']} · 표시 {n['표시']}"]
    bad = model["checks"]["거부"]
    out += [f"  [거부] {x['line']}" for x in bad[:5]]
    if len(bad) > 5:
        out.append(f"  … 거부 {len(bad) - 5} 더 — HTML 점검 표")
    out.append(f"  → {paths.show(where)}")
    return out


def _read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(args):
    if args[:1] == ["--diff"]:
        if len(args) != 3:
            raise SystemExit("사용법: python run.py export config --diff a.json b.json")      # [사용법]
        lines = diff(_read(args[1]), _read(args[2]))
        print(f"[export] config 지도 대조 — {args[1]} ↔ {args[2]} · " + (f"다름 {len(lines)}" if lines else "같다"))
        for ln in lines:
            print(f"  {ln}")
        return 1 if lines else 0
    model = M.build()
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
