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
**한 줄씩**(B204 ⑥) — `i/n` 한 줄을 묻고 처분하면 다음 줄(처분한 줄은 다시 그리지 않는다 · 결과 · 거부 · 해석은 물음 바로 위) · 줄 번호는
받지 않는다(`k` 제안 밑 · `k <번호>` 고를 곳 그 번호 밑) · `s` 건너뛰기 · 끝에 요약 한 줄 + 번호로 그 줄 다시 열기 · 「다시」 = 다시 판단(LLM 1).
"""
from __future__ import annotations

import re

from cli import _screen

#: 골격 목록 줄에 보이는 수(나머지는 `?`)
SHOW = 6
#: 처분이 쓴 것(`provisional_ask.decide`의 한 일) — 이것이면 처분 칸을 채운다
DONE = ("합침", "정정", "새로", "drop", "올림", "확인")
#: 요약 줄의 이름(한 일 → 처분 말)
SAID = {"합침": "같은 것으로", "정정": "같은 것으로", "새로": "새로 만들기", "drop": "버리기", "올림": "위로", "확인": "그대로 연결",
        "자동": "자동"}
_KEY = re.compile(r"^(\S)(?:\s+(.*))?$")
_KEYS = ("m", "k", "d", "u", "a", "p", "r")
#: 「다시」 — 그 줄을 다시 판단(LLM 1 · 판단 기억은 덮지 않는다 — 사람 말 길)
AGAIN = "다시"


def _parse(text):
    """**입력 한 줄 → (글쇠 | None, 나머지)** — 한 줄씩이라 줄 번호는 없다(`k 3` = 고를 곳 3번 밑 · B204 ⑥) · 글쇠가 아니면 말."""
    from cli.provisional_ask import key_of
    m = _KEY.match(text)
    k = key_of(m.group(1)) if m else None
    return (k, (m.group(2) or "").strip()) if k in _KEYS else (None, text)


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


def suggested(r):
    """LLM의 「새로라면 어디 밑」(B204 ② — `gate_judge`의 `under`) · 없으면 None."""
    return (r.get("llm") or {}).get("under")


def acts(i, r, indent="   "):
    """**그 줄의 동작 줄**(B203 ④) — 쓸 수 있는 글쇠만 · 실제 이름으로 · 새로 만들기는 LLM 제안이 있으면 그 밑(B204 ②)."""
    from core.state.gate_say import allowed
    pair, w, u = r.get("kind") == "pair", _words(), suggested(r)
    up = r.get("up") if pair else r.get("up_name")
    k = (f"→ {short(u['path'])} 밑 (LLM 제안 · {u['why'] or '까닭 없음'}) · 다른 곳: k <번호>" if u and u.get("host")
         else f"→ {up or '부모 미정'} › {r.get('surface')} (잠정 · k <번호>면 그 번호 밑에)")
    say = {"a": f"→ {short(r.get('real_up'))} › {r.get('surface')}", "k": k,
           "m": "→ m <번호>", "u": f"→ {up}", "d": "→ d <사유>"}
    return [f"{indent}     {k} {w[k]} {say[k]}" for k in allowed(r)]


def kind_of(r):
    """종류 칸(B204 ④) — 공정 표기(문) · 공정 짝 어긋남 · 이름(겸 값)."""
    return "공정 짝 어긋남" if r.get("kind") == "pair" else f"이름({r['also']})" if r.get("also") else "공정 표기"


def _tone(r):
    """판단 칸의 색 — 같다는 붙음 색 · 다르다 · 애매는 새로 생김 색(결과 색 표 그대로 — 새 색 0)."""
    v = (r.get("llm") or {}).get("verdict") or {"match": "같다"}.get(r.get("answer"))
    return "match" if v == "같다" else "new"


def row_lines(i, r, indent="   "):
    """한 줄 + 고를 곳(후보 · 골격 목록 — 이어지는 번호) + 동작 줄 · 색은 터미널일 때만(`_screen.paint`)."""
    from core.state import gate_judge as GJ
    pair, P = r.get("kind") == "pair", _screen.paint
    up = r.get("up") if pair else r.get("up_name")
    place = r.get("where") or ("행" if pair or not r.get("also") else "—")
    judged = _judged(r) + (f" · 실제 위 {r.get('real_up')}" if pair else "")
    out = [indent + _screen.pad(i, 3) + _cut(kind_of(r), 14) + _cut(r.get("surface"), 18) + _cut(place, 10)
           + _cut(up or "미정", 10) + P(_cut(judged, 48), _tone(r)) + (P(r["done"], "match") if r.get("done") else "—")]
    ps = GJ.picks(r)
    head = "후보(LLM 순위)" if r.get("llm") else "후보(첫 판단)"
    for j, x in enumerate(p for p in ps if p["cand"]):
        out.append(indent + "     " + _screen.pad("고를 곳 ─ " + head if j == 0 else "", 26)
                   + P(f"{_no(x['n'])} {short(x['path'])}" + (f" — {x['why']}" if x.get("why") else ""), "prog"))
    rest = [x for x in ps if not x["cand"]]
    if rest:
        out.append(indent + "     " + _screen.pad("" if len(rest) < len(ps) else "고를 곳 ─", 26) + P(f"골격({up or '좌표 층'} 아래) "
                   + "  ".join(f"{_no(x['n'])} {x['name']}" for x in rest[:SHOW]) + ("  … (? = 전부 번호로)" if len(rest) > SHOW else ""), "aux"))
    if r.get("llm") and r.get("llm0"):                    # 판단 기억 — 칸이 잘려도 안내는 한 줄로(B204 ⑥)
        out.append(P(f"{indent}     LLM 0 — 지난 판단({r['llm'].get('at') or '날짜 모름'}) · 새로 보려면 「{AGAIN}」", "aux"))
    return out + acts(i, r, indent)


def _head(indent="   "):
    return _screen.paint(indent + _screen.pad("#", 3) + _screen.pad("종류", 14) + _screen.pad("표기", 18) + _screen.pad("자리", 10)
                         + _screen.pad("위 공정", 10) + _screen.pad("판단(LLM)", 48) + "처분", "head")


def lines(rows, title, indent="   "):
    """**한 표 함수** — 머리 줄 + 열 + 줄마다(후보 · 골격 목록) — 사람 없는 실행 · 보고."""
    out = [_screen.paint(f"{indent}{title}", "head"), _head(indent)]
    for i, r in enumerate(rows, 1):
        out += row_lines(i, r, indent)
    return out


def prompt(r):
    """한 줄의 물음 — 그 줄에 쓸 수 있는 글쇠만(B204 ⑥)."""
    from core.state.gate_say import allowed
    ks = {"a": "a", "k": "k (제안 밑) · k <번호>" if suggested(r) else "k · k <번호>", "m": "m <번호>", "u": "u", "d": "d <사유>"}
    return f"   [계속 c / 멈춤 q / 말 또는 글쇠 — {' · '.join(ks[k] for k in allowed(r))} · {AGAIN} · ? 전부 · 건너뛰기 s] "   # 머리는 관문 물음과 같다


HELP = ("   말(LLM이 읽는다 — 해석을 보이고 Enter 뒤에 쓴다) 또는 글쇠 — a 그대로 연결(공정 짝 어긋남 줄) · k [번호] 새로 만들기 · "
        f"m [번호|이름] 같은 것으로 · u 위로(겸 값 줄) · d <사유> 버리기 · {AGAIN} 다시 판단 · ? 고를 곳 전부 · s 건너뛰기 · c 계속 · q 멈춤")


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
    return "\n".join([_screen.paint(f"   [거부] {i}번({kind_of(r)})에는 '{k}' — 이 줄은:", "fail")] + acts(i, r))


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
        print(f"     {rest}번이 고를 곳에 없다 — ?로 목록")
        return None
    hit = GJ.find(rest, ps)
    if len(hit) == 1:
        return next(x for x in ps if x["canonical"] == hit[0])
    if hit:
        print(f"     '{rest}'가 여럿 — " + " · ".join(f"{j}.{h}" for j, h in enumerate(hit, 1)) + " — m <전체 이름>으로 다시")
    else:
        print(f"     '{rest}'가 {r.get('up_name') or r.get('up') or '좌표 층'} 아래 골격에 없다 — ?로 목록")
    return None


def _apply(i, r, k, arg, who):
    """처분 한 줄 — 쓰는 손은 `provisional_ask.decide`(같은 함수) · 처분 칸에 실제 경로(B203 ④)."""
    from cli import provisional_ask as PA
    from core.state import gate_judge as GJ
    x = _target(i, r, arg) if k == "m" or (k == "k" and arg) else None
    u = suggested(r)
    if k == "k" and not arg and u and u.get("host"):              # `k`만 — LLM 제안 밑(B204 ②)
        x = next((y for y in GJ.picks(r) if y["canonical"] == u["canonical"]), None)
    if (k == "m" or (k == "k" and arg)) and not x:
        return
    if k == "k" and x and x.get("host") is False:
        ok = [str(y["n"]) for y in GJ.picks(r) if y.get("host")]
        print(f"   [거부] {i}번 — {x['n']}번 {short(x['path'])} — 골격 맨 아래 단(그 밑에 잠정 노드가 설 수 없다) · 설 수 있는 번호: "
              + (" · ".join(ok) or "없음"))
        return
    if k == "d" and not arg:
        print("   [거부] 버리기는 사유가 있어야 한다 — d <사유>")
        return
    did, _rb = PA.decide(r, who, answer="k" if k == "k" else f"{k} {x['canonical'] if x else arg or ''}".strip(),
                         under=x["canonical"] if k == "k" and x else None)
    if did in DONE:
        r["did"] = did                             # 끝 줄의 셈(`ops_review._did`)은 이 이름을 읽는다
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


def auto(r, who):
    """**맨 아래 단 밑 제안은 처분 대상이 아니다**(B204 ② · A″) — 겸 값 줄의 제안 부모가 골격 맨 아래 단이면 그 노드를 위 공정으로 고쳐 적고
    (`provisional_hand.reread` — 판정이 그 노드 아래 개체로 세운다) 처분 칸 「자동」으로 닫는다."""
    from core.state import provisional_hand as PH
    u = suggested(r)
    if r.get("done") or not r.get("also") or not u or u.get("host") is not False:
        return
    PH.reread(who, r["surface"], r.get("up_name"), up=u["canonical"], before=r.get("up_name"), reason="LLM 제안 — 맨 아래 단 아래는 자동")
    r["done"], r["did"] = f"✓ 자동 → {short(u['path'])} 아래 개체로(처분 없음)", "자동"


def _picks(r):
    from core.state import gate_judge as GJ
    for x in GJ.picks(r):
        print(f"     {_no(x['n'])} {x['name']} — {short(x['path'])} · 단 {x.get('tier') or '—'}" + (" · 후보" if x["cand"] else "")
              + ("" if x.get("host") is not False else " · 맨 아래 단(밑에 새로 만들기 0)"))


def _one(rows, i, who, ask):
    """**한 줄** — `i/n` + 그 줄(고를 곳 · 동작) → 처분할 때까지 묻는다 · `None` 다음 줄 · `True` 계속 · `False` 멈춤."""
    from core.state import gate_judge as GJ
    from core.state.gate_say import allowed
    r, nxt = rows[i - 1], None
    for ln in [_screen.paint(f"   ── {i}/{len(rows)} · {kind_of(r)}", "head"), _head()] + row_lines(i, r):
        _screen.say(ln)
    while not r.get("done"):
        got, nxt = (_read(prompt(r), ask) if nxt is None else nxt), None
        if got is True or got is False:
            return got
        text = got.strip()
        if text.lower() in ("s", "ㄴ"):
            print(f"   {i}/{len(rows)} 건너뜀 — 끝에서 번호로 다시 연다")
            return None
        if text.startswith("?"):
            _picks(r)
            continue
        if text == AGAIN:                                 # 다시 판단 — LLM 1 · 기억은 덮지 않는다(사람 말 길)
            GJ.judge([r], live=True, hint="사람이 다시 판단하라고 했다 — 지난 판단을 보지 말고 처음부터")
            for ln in row_lines(i, r):
                _screen.say(ln)
            continue
        k, rest = _parse(text)
        if k:
            print(_reject(i, r, k)) if k not in allowed(r) else _apply(i, r, k, rest, who)
            continue
        nxt = _say(i, r, text, who, ask)
    print(_screen.paint(f"   {i}/{len(rows)} {r['done']}", "match"))
    return None


def loop(rows, who, *, title, ask=None):
    """**한 고리** — LLM 판단 → 한 줄씩(B204 ⑥) → 끝에 요약 + 번호로 다시 열기 · `True` 계속 · `False` 멈춤."""
    from core.state import gate_judge as GJ
    GJ.judge(rows, live=True)
    for r in rows:
        auto(r, who)
    _screen.say(_screen.paint(f"   {title}", "head"))
    todo = [i for i, r in enumerate(rows, 1) if not r.get("done")]
    while True:
        for i in todo:
            go = _one(rows, i, who, ask)
            if go is not None:
                return go
        tally = {}
        for r in rows:
            w = SAID.get(r.get("did"), "해석 고침") if r.get("done") else "남음"
            tally[w] = tally.get(w, 0) + 1
        print("   처분 요약 — " + " · ".join(f"{w} {c}" for w, c in tally.items()))
        a = _read(f"   [계속 c / 멈춤 q / 고칠 것이 있으면 번호(1~{len(rows)})] ", ask)
        if a is True or a is False:
            return a
        n = int(a) if a.strip().isdigit() and 1 <= int(a) <= len(rows) else None
        if n and rows[n - 1].get("did") in ("합침", "정정"):
            print("   같은 것으로 처분은 별칭이 남는다 — 되돌림은 run.py ops(별칭 해제) · 새 처분이 뒤에 적힌다")
        if n:
            rows[n - 1].update(done=None, did=None)
        todo = [n] if n else []


def show(rows, title):
    """사람 없는 실행 — 표만(LLM 0 · 쓰기 0)."""
    from core.state import gate_judge as GJ
    GJ.judge(rows, live=False)
    for ln in lines(rows, title):
        _screen.say(ln)
