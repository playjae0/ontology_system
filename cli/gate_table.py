# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 표 · 물음 — 한 표 함수 · 한 고리**(B202 ③④ — 표 [3/7] 문 · 쌍 · 산문 [3/8] · [5/8] · `ops review` 첫 묶음).

판단은 LLM이(`core/state/gate_judge` — 골격 목록을 보고 · 후보 순위) · 사람 말도 LLM이 읽고(`core/state/gate_say` — 연결 처분 ·
해석 고침) · 확정은 사람이(해석을 보이고 Enter 뒤에만 쓴다) · 코드는 검사만. 처분 넷:

| 처분 | 글쇠 | 쓰는 손 |
|---|---|---|
| 같다 | `m [후보 번호|이름]` — 쌍 줄의 정정도 이것 | 골격 `ALIASES`(`provisional_hand.merge`) · 쌍 정정(`coord_acks.fix`) |
| 새로 | `k` | 잠정 골격 노드(`seed`) |
| 버림 | `d <사유>` | 세우지 않는다(`drop`) |
| 위로 | `u` — 겸 값 줄만 | 노드 0 · 값은 위 공정(`raise_up`) |

쌍 줄의 「지금 자리가 맞다」는 `a` 또는 말 「맞다」. 그 줄에 쓸 수 없는 글쇠는 거부(기록 0 · 다시 묻는다). 처분 · 해석 고침 뒤 표를
다시 그린다. 사람 없는 실행은 표만(LLM 0 · 쓰기 0).
"""
from __future__ import annotations

import re

from cli import _screen

#: 골격 목록 줄에 보이는 수(나머지는 `? <줄>`)
SHOW = 6
#: 처분 이름 → 처분 칸
DONE = {"합침": "✓ 합침 → {t}(사람)", "정정": "✓ 합침 → {t}(사람)", "새로": "✓ 새로(잠정)", "drop": "✓ 버림({r})",
        "올림": "✓ 위로 → {u}", "확인": "✓ 맞다(지금 자리)"}
_NAMES = {"m": "같다", "k": "새로", "d": "버림", "u": "위로", "a": "맞다"}
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


def row_lines(i, r, indent="   "):
    """한 줄 + 후보(한 줄에 하나) + 골격 목록 한 줄."""
    pair = r.get("kind") == "pair"
    up = r.get("up") if pair else r.get("up_name")
    place = r.get("where") or ("행" if pair or not r.get("also") else "—")
    judged = _judged(r) + (f" · 실제 위 {r.get('real_up')}" if pair else "")
    out = [indent + _screen.pad(i, 3) + _cut(r.get("surface"), 18) + _cut(place, 6) + _cut("좌표 쌍" if pair else r.get("also") or "좌표", 10)
           + _cut(up or "미정", 10) + _cut(judged, 48) + (r.get("done") or "—")]
    marks = "①②③④⑤⑥⑦⑧⑨"
    for j, c in enumerate(r.get("candidates") or []):
        head = "후보(LLM 순위)" if r.get("llm") else "후보(첫 판단)"
        out.append(indent + "     " + _screen.pad(head if j == 0 else "", 15) + f"{marks[j] if j < len(marks) else j + 1} "
                   + f"{c['name']}" + (f" — {c['why']}" if c.get("why") else ""))
    lst = r.get("skeleton") or []
    if lst:
        names = " ".join(f"{x['no']}.{x['name']}" for x in lst[:SHOW])
        out.append(indent + f"     골격 — {up or '좌표 층'} 아래 {len(lst):,}: {names}"
                   + (f" … (전부: ? {i})" if len(lst) > SHOW else ""))
    return out


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
    tail = " · 쌍 줄은 맞다 a" if pair else ""
    if len(rows) == 1:                      # 머리는 관문 물음과 같다(「[계속 c / 멈춤 q」)
        return f"   [계속 c / 멈춤 q / 말 또는 글쇠 (예: 사이드 실링이랑 같은 거 · k · d 설계 항목 · 이건 부품이야{tail})] "
    return (f"   [계속 c / 멈춤 q / 번호 + 말 또는 글쇠 (예: 1 사이드 실링이랑 같은 거 · 1 새로 · 1 버려 설계 항목 · "
            f"1 이건 부품이야{tail})] ")


HELP = ("   번호 + 말(LLM이 읽는다 — 해석을 보이고 Enter 뒤에 쓴다) 또는 글쇠 — m [후보|이름] 같다 · k 새로 · d <사유> 버림 · "
        "u 위로(겸 값 줄) · a 맞다(쌍 줄) · ? <줄> 골격 전부 · c 계속 · q 멈춤")


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
    from core.state.gate_say import allowed
    what = "쌍" if r.get("kind") == "pair" else "문"
    if k == "p":
        return f"   [거부] {i}번({what})에는 'p'를 쓸 수 없다 — 승격은 인입 뒤 ops review(잠정 골격 노드) · 여기서는 k"
    if k == "r":
        return f"   [거부] {i}번({what})에는 'r'을 쓸 수 없다 — 쌍 정정은 m <후보|이름>"
    return f"   [거부] {i}번({what})에는 '{k}'를 쓸 수 없다 — {' · '.join(allowed(r))}"


def _target(i, r, rest):
    """합칠 대상 — 후보 번호 · 이름(띄어쓰기 · 대소문자 · `상위::` 무시 — 위 공정 범위 안) · 없으면 첫 후보. 여럿이면 목록을 보이고 None."""
    from core.state import gate_judge as GJ
    cands = r.get("candidates") or []
    if not rest:
        return cands[0]["name"] if cands else None
    if rest.isdigit():
        k = int(rest)
        return cands[k - 1]["name"] if 1 <= k <= len(cands) else None
    hit = GJ.find(rest, r.get("skeleton") or [])
    if len(hit) == 1:
        return hit[0]
    if hit:
        print(f"     '{rest}'가 여럿 — " + " · ".join(f"{j}.{h}" for j, h in enumerate(hit, 1)) + f" — m {i} <전체 이름>으로 다시")
    else:
        print(f"     '{rest}'가 {r.get('up_name') or r.get('up') or '좌표 층'} 아래 골격에 없다 — ? {i}로 목록")
    return None


def _apply(i, r, k, arg, who):
    """처분 한 줄 — 쓰는 손은 `provisional_ask.decide`(같은 함수) · 처분 칸을 채운다."""
    from cli import provisional_ask as PA
    if k == "m":
        arg = _target(i, r, arg)
        if not arg:
            return
    if k == "d" and not arg:
        print(f"   [거부] 버림은 사유가 있어야 한다 — d {i} <사유>")
        return
    did, _rb = PA.decide(r, who, answer=f"{k} {arg or ''}".strip())
    if did in DONE:
        r["done"] = DONE[did].format(t=arg, r=arg, u=r.get("up_name"))


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
        what = got.get("target") or got.get("reason") or (r.get("up_name") if got["key"] == "u" else "")
        print(f"   해석(LLM) — {i}번 = {_NAMES[got['key']]}" + (f" → {what}" if what else "") + f"{conf} · {got['why']}")
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
        _apply(i, r, got["key"], got.get("target") or got.get("reason"), who)
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
            for x in (r or {}).get("skeleton") or []:
                print(f"     {x['no']}. {x['name']} — {x['path']} · 단 {x['tier'] or '—'}")
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
            print(f"   {i}번에 할 말 또는 글쇠 — " + " · ".join(allowed(r)))
            continue
        again = _say(i, r, rest, who, ask)
        nxt = f"{i} {again}" if again else None


def show(rows, title):
    """사람 없는 실행 — 표만(LLM 0 · 쓰기 0)."""
    from core.state import gate_judge as GJ
    GJ.judge(rows, live=False)
    for ln in lines(rows, title):
        _screen.say(ln, "warn" if ln == f"   {title}" else None)
