# -*- coding: utf-8 -*-
"""검수 뷰 렌더러 (킷 구성물 ⑤) — 뷰 데이터 JSON → **정적 HTML** (파서_명세 §7 · 카드 M11).

    view.json  ──(이 파일)──▶  view.html   ← 브라우저로 열고 CLI로 승인한다

**사람이 코드를 읽지 않게 하는 장치다.** 틀 §2가 정한 검수 수준은 "결과 뷰를 보고
승인 1회"이고, 어댑터 코드를 읽게 만드는 순간 그 수준이 깨진다.

**데이터와 표현을 가른다**(§7 규약 3 · P-2). 이 파일은 `view.json`만 읽고 아무것도
계산하지 않는다 — 채움율도 이상 신호 판정도 **산출자(P3 n6)의 몫**이다. 렌더러가
계산하기 시작하면 "렌더러만 교체되고 데이터 계약은 불변"이 깨지고, 나중에 플랫폼
화면이 같은 JSON을 읽어도 다른 화면이 나온다.

**3구획 · 3층**은 payload_kind와 무관하게 같다. 다른 것은 구획 1의 렌더뿐이다 —
table은 레코드 표, prose는 계층 트리. 화면의 목적은 "모든 행이 맞는가"가 아니라
**"규칙이 맞는가"**이기 때문이다.

사용: python kit/render_review.py <view.json> [출력.html]
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

KIND_LABEL = {"failure": "실패", "question": "판정 불가", "warning": "경고"}

CSS = """
:root { --bd:#d8dce3; --mut:#5b6270; --bg2:#f6f7f9; --warn:#b45309; --fail:#b91c1c;
        --ask:#1d4ed8; }
body { font: 15px/1.65 -apple-system,'Segoe UI','Noto Sans KR',sans-serif;
       margin: 0 auto; max-width: 1080px; padding: 24px 20px 64px; color:#12151a; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 32px 0 10px; padding-bottom: 6px;
     border-bottom: 2px solid #12151a; }
.sub { color: var(--mut); margin: 0 0 8px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 14px;
        display: block; overflow-x: auto; }
th, td { border: 1px solid var(--bd); padding: 6px 9px; text-align: left;
         vertical-align: top; }
th { background: var(--bg2); white-space: nowrap; }
.stat { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
.stat div { border: 1px solid var(--bd); border-radius: 6px; padding: 8px 14px;
            background: var(--bg2); }
.stat b { display: block; font-size: 20px; }
.anom { border-left: 4px solid var(--bd); padding: 8px 12px; margin: 8px 0;
        background: var(--bg2); }
td.warn { color: var(--warn); font-weight: 600; }
.anom.failure { border-color: var(--fail); } .anom.warning { border-color: var(--warn); }
.anom.question { border-color: var(--ask); }
.tag { font-size: 12px; font-weight: 700; letter-spacing: .04em; }
.failure .tag { color: var(--fail); } .warning .tag { color: var(--warn); }
.question .tag { color: var(--ask); }
.where { color: var(--mut); font-size: 12px; }
details { margin: 10px 0; border: 1px solid var(--bd); border-radius: 6px;
          padding: 8px 12px; }
summary { cursor: pointer; font-weight: 600; }
pre { background: var(--bg2); padding: 10px; overflow-x: auto; font-size: 13px;
      border-radius: 4px; }
.tree li { margin: 3px 0; } .tree .loc { color: var(--mut); font-size: 12px; }
.none { color: var(--mut); font-style: italic; }
footer { margin-top: 40px; color: var(--mut); font-size: 12px;
         border-top: 1px solid var(--bd); padding-top: 10px; }
"""


def e(x):
    return html.escape("" if x is None else str(x))


# ---------------------------------------------------------------- 구획 1
def _summary(s):
    cells = [("표본", s.get("samples", 0)), ("조각", s.get("pieces", 0)),
             ("실패", s.get("failures", 0)), ("경고", s.get("warnings", 0))]
    out = ["<div class='stat'>"]
    out += [f"<div><b>{e(v)}</b>{e(k)}</div>" for k, v in cells]
    out.append("</div>")
    fill = s.get("fill_rate") or {}
    if fill:
        out.append("<table><tr><th>필드</th>"
                   + "".join(f"<th>{e(k)}</th>" for k in fill) + "</tr>"
                   "<tr><td>채움율</td>"
                   + "".join(f"<td>{v * 100:.0f}%</td>" for v in fill.values())
                   + "</tr></table>")
    return "\n".join(out)


def _anomalies(items):
    """② **전량 표시**다 — 여기에 접힘을 쓰지 않는다(§7 규약 1)."""
    if not items:
        return "<p class='none'>이상 신호 없음</p>"
    out = []
    for a in items:
        kind = a.get("kind", "warning")
        out.append(
            f"<div class='anom {e(kind)}'>"
            f"<span class='tag'>{e(KIND_LABEL.get(kind, kind))}</span> "
            f"{e(a.get('message'))}"
            + (f" <span class='where'>({e(a.get('where'))})</span>"
               if a.get("where") else "")
            + (f"<pre>{e(json.dumps(a['detail'], ensure_ascii=False, indent=2))}</pre>"
               if a.get("detail") else "")
            + "</div>")
    return "\n".join(out)


def _records(rows, columns):
    if not rows:
        return "<p class='none'>표시할 조각 없음</p>"
    cols = columns or sorted({k for r in rows for k in r})
    head = "".join(f"<th>{e(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{e(r.get(c))}</td>" for c in cols) + "</tr>"
                   for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _tree(nodes):
    if not nodes:
        return "<p class='none'>계층 없음</p>"
    out = ["<ul class='tree'>"]
    for n in nodes:
        pad = "&nbsp;" * 4 * max(0, int(n.get("depth") or 0))
        out.append(f"<li>{pad}<b>{e(n.get('section'))}</b> "
                   f"<span class='loc'>{e(n.get('locator'))}</span><br>{pad}"
                   f"{e(n.get('excerpt'))}</li>")
    out.append("</ul>")
    return "\n".join(out)


def _normal(normal, kind):
    """③ 발췌 기본 + **전량 접힘**. payload_kind가 렌더만 가른다."""
    excerpt, allrows = normal.get("excerpt") or [], normal.get("all") or []
    if kind == "prose":
        shown = _tree(normal.get("tree") or [])
        full = _tree([{"section": r.get("section"), "locator": r.get("source_locator"),
                       "excerpt": r.get("text")} for r in allrows])
    else:
        shown = _records(excerpt, normal.get("columns"))
        full = _records(allrows, normal.get("columns"))
    return (f"<h3 style='font-size:15px;margin:16px 0 4px'>정상 조각 — 발췌</h3>{shown}"
            f"<details><summary>전량 보기 ({len(allrows)}건)</summary>{full}</details>")


# ---------------------------------------------------------------- 구획 2·3
def _roles(rows):
    if not rows:
        return "<p class='none'>배정표 없음 — prose는 fields가 빈 목록이다 (D-31)</p>"
    head = "<tr><th>필드</th><th>role</th><th>카테고리</th><th>부착</th><th>근거</th></tr>"
    body = "".join(
        "<tr>"
        f"<td>{e(r.get('field'))}</td><td><b>{e(r.get('role'))}</b>"
        + (f" <span class='where'>({e(r['from_block'])})</span>"
           if r.get("from_block") else "")
        + f"</td><td>{e(r.get('category'))}</td><td>{e(r.get('attach_to'))}</td>"
          f"<td>{e(r.get('reason'))}</td></tr>" for r in rows)
    return f"<table>{head}{body}</table>"


def _adapter(a):
    out = [f"<p class='sub'>adapter_version <b>{e(a.get('adapter_version'))}</b></p>",
           "<pre>" + e(json.dumps(a.get("expects") or {}, ensure_ascii=False, indent=2))
           + "</pre>"]
    if a.get("source"):
        out.append(f"<details><summary>어댑터 코드 전문 (접힘)</summary>"
                   f"<pre>{e(a['source'])}</pre></details>")
    return "\n".join(out)


def _regen(items):
    if not items:
        return ""
    rows = "".join(f"<tr><td>{e(r.get('n'))}</td><td>{e(r.get('instruction'))}</td>"
                   f"<td>{e(r.get('at'))}</td></tr>" for r in items)
    note = (f"<p class='sub'>재생성 {len(items)}회째 — 표본·힌트 변경을 고려. "
            f"<b>상한은 없다</b>(중단은 사람 판단).</p>")
    return ("<h2>재생성 이력</h2>" + note
            + f"<table><tr><th>#</th><th>수정 지시</th><th>시점</th></tr>{rows}</table>")


# ---------------------------------------------------------------- 진입점
def _split(rows):
    """분할 크기 분포 (B45) — **그리기만 한다.** 값은 산출자가 채웠다.

    상수가 부적절해 한 줄짜리 청크가 쏟아지는 것을 **등록 시점에** 보이는 자리다.
    목표 구간 밖을 짧은 쪽·긴 쪽으로 갈라 보이는 이유는 처방이 다르기 때문이다.
    """
    if not rows:
        return ""
    out = ['<h3 style="font-size:15px;margin:16px 0 4px">분할 크기 분포</h3>',
           '<table><tr><th>문서</th><th>청크</th><th>행수 최소~최대(평균)</th>'
           '<th>목표 구간</th><th>너무 짧음</th><th>너무 긺</th></tr>']
    for r in rows:
        g = r.get("목표구간") or []
        warn = ' class="warn"' if (r.get("너무_짧은_청크") or 0) else ""
        out.append(
            f'<tr><td>{e(r.get("doc_id"))}</td><td>{e(r.get("청크수"))}</td>'
            f'<td>{e(r.get("행수_최소"))}~{e(r.get("행수_최대"))}'
            f' ({e(r.get("행수_평균"))})</td>'
            f'<td>{e(g[0] if g else "")}~{e(g[1] if len(g) > 1 else "")}</td>'
            f'<td{warn}>{e(r.get("너무_짧은_청크"))}</td>'
            f'<td>{e(r.get("너무_긴_청크"))}</td></tr>')
    out.append("</table>")
    for r in rows:
        for pick in (r.get("레벨_선택") or []):
            out.append(f'<p class="sub">지도 경로 — 고른 레벨 '
                       f'<b>{e(pick.get("분할_레벨"))}</b>: '
                       f'{e(pick.get("분할_레벨_사유"))}</p>')
            dist = pick.get("레벨_분포") or {}
            if dist:
                out.append('<table><tr><th>레벨</th><th>청크</th>'
                           '<th>행수 최소~최대(평균)</th><th>구간내</th></tr>')
                for lv, d in dist.items():
                    out.append(
                        f'<tr><td>{e(lv)}</td><td>{e(d.get("청크수"))}</td>'
                        f'<td>{e(d.get("행수_최소"))}~{e(d.get("행수_최대"))}'
                        f' ({e(d.get("행수_평균"))})</td>'
                        f'<td>{e(d.get("구간내_청크수"))}</td></tr>')
                out.append("</table>")
    return "\n".join(out)


def render(view):
    """뷰 데이터 → HTML 문자열. **계산하지 않는다** — 있는 것을 그린다."""
    s = view["sections"]
    pr = s["parse_result"]
    kind = view.get("payload_kind")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>검수 뷰 — {e(view.get('doc_type'))}</title><style>{CSS}</style></head><body>
<h1>검수 뷰 — {e(view.get('doc_type'))}</h1>
<p class="sub">payload_kind <b>{e(kind)}</b> · adapter_version
   <b>{e(view.get('adapter_version'))}</b></p>
<p class="sub">이 화면은 어댑터 성능 평가가 아니라 <b>등록 승인의 근거 확인</b>이다.
   목적은 "모든 행이 맞는가"가 아니라 <b>"규칙이 맞는가"</b>다.</p>

<h2>구획 1 · 파싱 결과</h2>
{_summary(pr.get('summary') or {})}
<h3 style="font-size:15px;margin:16px 0 4px">이상 신호 — 전량</h3>
{_anomalies(pr.get('anomalies') or [])}
{_split((pr.get('summary') or {}).get('split') or [])}
{_normal(pr.get('normal') or {}, kind)}

<h2>구획 2 · 필드 → role 배정표</h2>
{_roles(s.get('role_table') or [])}

<h2>구획 3 · 어댑터 요약</h2>
{_adapter(s.get('adapter_summary') or {})}
{_regen(view.get('regenerations') or [])}

<footer>검수 뷰 렌더러 (킷 ⑤) · 데이터 계약 = <code>kit/검수뷰_데이터스키마.json</code>
 · 규격 정본 = 파서_명세 §7 · 카드 M11<br>
 승인은 CLI/파일로 한다 — "무수정 = 자동 통과"는 금지다.</footer>
</body></html>"""


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    src = Path(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else src.with_suffix(".html")
    out.write_text(render(json.loads(src.read_text(encoding="utf-8"))),
                   encoding="utf-8")
    print(f"[render] {src} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
