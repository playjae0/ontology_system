# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 표 · 물음 — 한 표 함수 · 한 고리**(B202 ③④ — 표 [3/7] 문 · 쌍 · 산문 [3/8] · [5/8] · `ops review` 첫 묶음).

판단은 LLM이(`core/state/gate_judge` — 골격 목록을 보고 · 후보 순위) · 사람 말도 LLM이 읽고(`core/state/gate_say` — 연결 처분 ·
해석 고침) · 확정은 사람이(해석을 보이고 Enter 뒤에만 쓴다) · 코드는 검사만. **처분 말 다섯**(B203 ④ — 말은 `gate_say.KEYS` 한 자리):

| 처분 | 글쇠 | 쓰는 손 |
|---|---|---|
| 그대로 연결 | `a` — 쌍 줄 | 지금 골격 노드에(`coord_acks.ack`) |
| 새로 만들기 | `k [번호]` — 번호면 그 노드 밑 · 쌍 줄은 문서의 상위 밑 | 잠정 골격 노드(`seed` — 쌍 줄은 + `coord_acks.fix`) |
| 같은 것으로 | `m [번호|이름]` | 골격 `ALIASES`(`provisional_hand.merge`) · 쌍 정정(`coord_acks.fix`) |
| 위로 | `u` — 겸 값 줄만 | 노드 0 · 값은 위 공정(`raise_up`) |
| 버리기 | `d <사유>` | 세우지 않는다(`drop`) |

**번호 하나** — 그 줄의 고를 곳(후보 다음 골격 목록 · `gate_judge.picks`)을 `m` · `k` · 말이 같은 번호로. 그 줄에 쓸 수 없는 글쇠는
거부(기록 0 · 동작 줄을 다시). 처분 칸 · 화면에 실제 경로. 사람 없는 실행은 표만(LLM 0 · 쓰기 0).
"""
from __future__ import annotations

import re

from cli import _screen

#: 골격 목록 줄에 보이는 수(나머지는 `? <줄>`)
SHOW = 6
#: 처분이 쓴 것(`provisional_ask.decide`의 한 일) — 이것이면 처분 칸을 채운다
DONE = ("합침", "정정", "새로", "drop", "올림", "확인")
_NUM = re.compile(r"^(\d+)\s*(.*)$")
#: 글쇠 먼저 꼴(`m 1 사이드실링` · `p 1` · `d 1 사유`) — 지금 물음과 같은 꼴
_KEYNUM = re.compile(r"^(\S)\s+(\d+)(?:\s+(.*))?$")
_KEY = re.compile(r"^(\S)(?:\s+(.*))?$")
_KEYS = ("m", "k", "d", "u", "a", "p", "r")


def _parse(text, n):
    """**입력 한 줄 → (번호, 글쇠 | None, 나머지)** 한 자리 — 글쇠 + 번호 먼저(`m 1 …` · `1 m …`) · 아니면 말(`1 <말>`) ·
    줄이 하나면 번호 생략 · 번호를 못 정하면 None."""
    from cli.provisional_ask import key_of
    m = _KEYNUM.match(text)
    if m and key_of(m.group(1)) in _KEYS:
        return int(m.group(2)), key_of(m.group(1)), (m.group(3) or "").strip()
    m = _NUM.match(text)
    if not m and n != 1:
        return None
    i, rest = (int(m.group(1)), m.group(2).strip()) if m else (1, text)
    km = _KEY.match(rest)
    k = key_of(km.group(1)) if km else None
    return (i, k, (km.group(2) or "").strip()) if k in _KEYS else (i, None, rest)


def _cut(s, n):
    return _screen.pad(_screen.cut(str(s if s is not None else "—"), n - 1), n)


def _judged(r):
    lm = r.get("llm")
    if lm:
        cell = f"{lm['verdict']} · 확실 {lm['confidence']:.2f} · {lm['why']}"
        return cell + (" (LLM 0 — 판단 기억)" if r.get("llm0") else "")
    first = {"uncertain": "애매", "new": "다르다", "match": "같다"}.get(r.get("answer"), r.get("answer") or "—")
    return f"LLM 0 — {r.get('llm0') or '사람 없는 실행'} · 첫 판단 {first}"


def _no(n):
    return "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"[n - 1] if 1 <= n <= 20 else f"({n})"


def short(path):
    """화면의 경로 — 마디마다 짧은 이름(`상위::` 접두를 뗀다 · 화면만)."""
    from core.state import catalog
    return " › ".join(x.rsplit(catalog.sep(), 1)[-1] for x in str(path or "").split(" › "))


def _words():
    from core.state.gate_say import KEYS
    return {v: k for k, v in KEYS.items()}


def acts(i, r, indent="   "):
    """**그 줄의 동작 줄**(B203 ④) — 쓸 수 있는 글쇠만 · 실제 이름으로."""
    from core.state.gate_say import allowed
    pair, w = r.get("kind") == "pair", _words()
    up = r.get("up") if pair else r.get("up_name")
    say = {"a": f"→ {short(r.get('real_up'))} › {r.get('surface')}",
           "k": f"→ {up or '부모 미정'} › {r.get('surface')} (잠정 · k {i} <번호>면 그 번호 밑에)",
           "m": f"→ m {i} <번호>", "u": f"→ {up}", "d": f"→ d {i} <사유>"}
    return [f"{indent}     {k} {w[k]} {say[k]}" for k in allowed(r)]


def row_lines(i, r, indent="   "):
    """한 줄 + 고를 곳(후보 · 골격 목록 — 이어지는 번호) + 동작 줄."""
    from core.state import gate_judge as GJ
    pair = r.get("kind") == "pair"
    up = r.get("up") if pair else r.get("up_name")
    place = r.get("where") or ("행" if pair or not r.get("also") else "—")
    judged = _judged(r) + (f" · 실제 위 {r.get('real_up')}" if pair else "")
    out = [indent + _screen.pad(i, 3) + _cut(r.get("surface"), 18) + _cut(place, 6) + _cut("좌표 쌍" if pair else r.get("also") or "좌표", 10)
           + _cut(up or "미정", 10) + _cut(judged, 48) + (r.get("done") or "—")]
    ps = GJ.picks(r)
    head = "후보(LLM 순위)" if r.get("llm") else "후보(첫 판단)"
    for j, x in enumerate(p for p in ps if p["cand"]):
        out.append(indent + "     " + _screen.pad("고를 곳 ─ " + head if j == 0 else "", 26) + f"{_no(x['n'])} {short(x['path'])}"
                   + (f" — {x['why']}" if x.get("why") else ""))
    rest = [x for x in ps if not x["cand"]]
    if rest:
        out.append(indent + "     " + _screen.pad("" if len(rest) < len(ps) else "고를 곳 ─", 26) + f"골격({up or '좌표 층'} 아래) "
                   + "  ".join(f"{_no(x['n'])} {x['name']}" for x in rest[:SHOW]) + (f"  … (? {i} = 전부 번호로)" if len(rest) > SHOW else ""))
    return out + acts(i, r, indent)


def lines(rows, title, indent="   "):
    """**한 표 함수** — 머리 줄 + 열 + 줄마다(후보 · 골격 목록)."""
    out = [f"{indent}{title}",
           indent + _screen.pad("#", 3) + _screen.pad("표기", 18) + _screen.pad("자리", 6) + _screen.pad("카테고리", 10)
           + _screen.pad("위 공정", 10) + _screen.pad("판단(LLM)", 48) + "처분"]
    for i, r in enumerate(rows, 1):
        out += row_lines(i, r, indent)
    return out


def prompt(rows):
    pair = any(r.get("kind") == "pair" for r in rows)
    tail = " · 쌍 줄은 그대로 연결 a" if pair else ""
    if len(rows) == 1:                      # 머리는 관문 물음과 같다(「[계속 c / 멈춤 q」)
        return f"   [계속 c / 멈춤 q / 말 또는 글쇠 (예: 사이드 실링이랑 같은 거 · k · d 설계 항목 · 이건 부품이야{tail})] "
    return (f"   [계속 c / 멈춤 q / 번호 + 말 또는 글쇠 (예: 1 사이드 실링이랑 같은 거 · k 1 · k 1 3 · d 1 설계 항목 · "
            f"1 이건 부품이야{tail})] ")


HELP = ("   번호 + 말(LLM이 읽는다 — 해석을 보이고 Enter 뒤에 쓴다) 또는 글쇠 — a 그대로 연결(쌍 줄) · k [번호] 새로 만들기 · "
        "m [번호|이름] 같은 것으로 · u 위로(겸 값 줄) · d <사유> 버리기 · ? <줄> 고를 곳 전부 · c 계속 · q 멈춤")


def _read(q, ask):
    """`True` 계속 · `False` 멈춤 · 글(처분 · 말)."""
    if ask is None:
        return _screen.answer(q, "go", eof=True, other=lambda a: a, hint=HELP)
    a = (ask(q) or "").strip()
    if not a or a.lower() in _screen.GO:
        return True
    if a.lower() in _screen.STOP:
        return False
    return a


def _reject(i, r, k):
    return "\n".join([f"   [거부] {i}번({'쌍' if r.get('kind') == 'pair' else '문'})에는 '{k}' — 이 줄은:"] + acts(i, r))


def _target(i, r, rest):
    """고를 곳 하나 — 번호(후보 · 골격 목록이 이어지는 번호) · 이름(띄어쓰기 · 대소문자 · `상위::` 무시 — 같은 목록) · 없으면 첫 후보.
    여럿이거나 없으면 말하고 None."""
    from core.state import gate_judge as GJ
    ps = GJ.picks(r)
    if not rest:
        return next((x for x in ps if x["cand"]), None)
    if rest.isdigit():
        if 1 <= int(rest) <= len(ps):
            return ps[int(rest) - 1]
        print(f"     {rest}번이 고를 곳에 없다 — ? {i}로 목록")
        return None
    hit = GJ.find(rest, ps)
    if len(hit) == 1:
        return next(x for x in ps if x["canonical"] == hit[0])
    if hit:
        print(f"     '{rest}'가 여럿 — " + " · ".join(f"{j}.{h}" for j, h in enumerate(hit, 1)) + f" — m {i} <전체 이름>으로 다시")
    else:
        print(f"     '{rest}'가 {r.get('up_name') or r.get('up') or '좌표 층'} 아래 골격에 없다 — ? {i}로 목록")
    return None


def _apply(i, r, k, arg, who):
    """처분 한 줄 — 쓰는 손은 `provisional_ask.decide`(같은 함수) · 처분 칸에 실제 경로(B203 ④)."""
    from cli import provisional_ask as PA
    from core.state import gate_judge as GJ
    x = _target(i, r, arg) if k == "m" or (k == "k" and arg) else None
    if (k == "m" or (k == "k" and arg)) and not x:
        return
    if k == "k" and x and x.get("host") is False:
        ok = [str(y["n"]) for y in GJ.picks(r) if y.get("host")]
        print(f"   [거부] {i}번 — {x['n']}번 {short(x['path'])} — 골격 맨 아래 단(그 밑에 잠정 노드가 설 수 없다) · 설 수 있는 번호: "
              + (" · ".join(ok) or "없음"))
        return
    if k == "d" and not arg:
        print(f"   [거부] 버리기는 사유가 있어야 한다 — d {i} <사유>")
        return
    did, _rb = PA.decide(r, who, answer="k" if k == "k" else f"{k} {x['canonical'] if x else arg or ''}".strip(),
                         under=x["canonical"] if k == "k" and x else None)
    if did in DONE:
        up = (r.get("up") if r.get("kind") == "pair" else r.get("up_name")) or "부모 미정"
        r["done"] = "✓ " + _words()[k] + {"m": f" → {short((x or {}).get('path'))}",
                                          "k": f" → {short((x or {}).get('path') or up)} › {r.get('surface')} (잠정)",
                                          "a": f" → {short(r.get('real_up'))} › {r.get('surface')}", "u": f" → {r.get('up_name')}",
                                          "d": f"({arg})"}[k]


def _say(i, r, text, who, ask):
    """**사람 말** — LLM 해석 → 보이고 확인(Enter) → 쓴다 · 아니면 다시 말하기(그 줄) · 돌려주는 것은 다음 말(없으면 None)."""
    from core.state import gate_judge as GJ, gate_say as GS
    from core.state import provisional_hand as PH
    got, why = GS.read(text, r)
    if got is None:
        print(f"   [해석 못 함] {why} — 다시 말하기")
        return None
    conf = f" · 확실 {got['confidence']:.2f}"
    if got["kind"] == GS.LINK:
        ps = GJ.picks(r)
        up = short(ps[got["under"] - 1]["path"]) if got.get("under") else (r.get("up") if r.get("kind") == "pair" else r.get("up_name"))
        what = f"{up} › {r.get('surface')} (잠정)" if got["key"] == "k" else \
            got.get("target") or got.get("reason") or (r.get("up_name") if got["key"] == "u" else "")
        print(f"   해석(LLM) — {i}번 = {_words()[got['key']]}" + (f" → {what}" if what else "") + f"{conf} · {got['why']}")
    elif got["field"] == "카테고리":
        print(f"   해석(LLM) — {i}번 해석 고침: 카테고리 {r.get('also')} → {got['value']} · 문 떠남{conf} · {got['why']}")
    else:
        tmp = dict(r, up_name=got["value"], llm=None, done=None)
        GJ.judge([tmp], live=True, hint=text)
        print(f"   해석(LLM) — {i}번 해석 고침: 위 공정 {r.get('up_name')} → {got['value']}{conf} · {got['why']} — 다시 판단:")
        for ln in row_lines(i, tmp):
            print(ln)
    a = _screen.answer("   [맞으면 Enter / 아니면 다시 말하기] ", "text", eof=None) if ask is None else (ask("   [맞으면 Enter / 아니면 다시 말하기] ") or "")
    if a is None:
        print("   확인 없음 — 쓰지 않았다")
        return None
    if a.strip():
        return a.strip()
    if got["kind"] == GS.LINK:
        _apply(i, r, got["key"], str(got["under"]) if got.get("under") else got.get("target") or got.get("reason"), who)
    elif got["field"] == "카테고리":
        PH.reread(who, r["surface"], r.get("up_name"), category=got["value"], before=r.get("also"), reason=text)
        r["done"] = f"✎ 해석 고침(카테고리 {r.get('also')} → {got['value']}) → 문 떠남"
        print(f"   해석 고침 — '{r['surface']}' 카테고리 {got['value']} · 그 자리의 문을 떠난다(지금의 판정 길로 · 사람 판단 기록에 한 줄)")
    else:
        PH.reread(who, r["surface"], r.get("up_name"), up=got["value"], before=r.get("up_name"), reason=text)
        r.update(tmp, done=None)
        r["note"] = f"✎ 위 공정 → {got['value']}"
        print(f"   해석 고침 — '{r['surface']}' 위 공정 {got['value']} · 그 자리로 다시 판단했다(처분은 이 줄에서)")
    return None


def loop(rows, who, *, title, ask=None):
    """**한 고리** — LLM 판단 → 표 → 번호 + 말 또는 글쇠 → (말이면 해석 · 확인) → 처분 → 표 다시 · `True` 계속 · `False` 멈춤."""
    from core.state import gate_judge as GJ
    from core.state.gate_say import allowed
    GJ.judge(rows, live=True)
    nxt = None
    while True:
        if nxt is None:
            for ln in lines(rows, title):
                _screen.say(ln, "warn" if ln == f"   {title}" else None)
            got = _read(prompt(rows), ask)
        else:
            got, nxt = nxt, None
        if got is True or got is False:
            return got
        text = got.strip()
        if text.startswith("?"):
            n = text[1:].strip()
            r = rows[int(n) - 1] if n.isdigit() and 1 <= int(n) <= len(rows) else (rows[0] if len(rows) == 1 else None)
            for x in GJ.picks(r or {}):
                print(f"     {_no(x['n'])} {x['name']} — {short(x['path'])} · 단 {x.get('tier') or '—'}" + (" · 후보" if x["cand"] else "")
                      + ("" if x.get("host") is not False else " · 맨 아래 단(밑에 새로 만들기 0)"))
            continue
        got = _parse(text, len(rows))
        if got is None:
            print("   번호를 먼저 — 예: 1 사이드 실링이랑 같은 거 · 1 k")
            continue
        i, k, rest = got
        if not 1 <= i <= len(rows):
            print(f"   {i}번이 목록에 없다")
            continue
        r = rows[i - 1]
        if r.get("done"):
            print(f"   {i}번은 이미 처분했다 — {r['done']}")
            continue
        if k:
            if k not in allowed(r):
                print(_reject(i, r, k))
            else:
                _apply(i, r, k, rest, who)
            continue
        if not rest:
            print("\n".join([f"   {i}번에 할 말 또는 글쇠 —"] + acts(i, r)))
            continue
        again = _say(i, r, rest, who, ask)
        nxt = f"{i} {again}" if again else None


def show(rows, title):
    """사람 없는 실행 — 표만(LLM 0 · 쓰기 0)."""
    from core.state import gate_judge as GJ
    GJ.judge(rows, live=False)
    for ln in lines(rows, title):
        _screen.say(ln, "warn" if ln == f"   {title}" else None)
