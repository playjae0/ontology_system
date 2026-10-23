# -*- coding: utf-8 -*-
"""칸 0.3 — **[5/8] 사람 후보 관문**(B140 ①②) — 이름 없는 대상의 목록(늘) · `--step`이면 고르고 · 보고 · OK.

재료는 `core/build/human.Board`(읽기만 — LLM 0 · 그래프 쓰기 0) · 기록은 `core/state/human_candidates`(OK 즉시 ②등록) · 그래프는
[6/8]이 쓴다(추출 후보에 한 줄 — 노드는 평소 길이 세운다). 묻는 함수는 `_screen.answer` 하나(구조 확인과 같다) · 비대화형은 묻지
않는다(EOF = 계속) · 입력은 번호 · Enter 중심(긴 이름을 붙여 넣지 않아도 된다 — 「직접」만 이름).

    lines(board, step)   [5/8] 머리 아래 줄 — 지난 기록 · 이름 없는 대상(잃을 것이 많은 차례 · 위 10 — `-v`면 전부) · 꼬리 · 안내
    ask(board)           `--step`의 물음 — `[계속 c / 멈춤 q / 더하기 n <번호> / 같은 것 s <번호> / 지우기 d <번호>]`
"""
from __future__ import annotations

from cli import _screen
from core.build import human
from core.state import human_candidates as HC

PROMPT = "   [계속 c / 멈춤 q / 더하기 n <번호> / 같은 것 s <번호> / 지우기 d <번호>] "
HELP = "   c(ㅊ) 계속 · q(ㅂ) 멈춤 · n <번호> 더하기 · s <번호> 같은 것 · d <번호> 지우기 — 다시 친다"
DETAIL = "     [OK o / 위 노드 p / 카테고리 k / 취소 x] "
#: 한글 자판 그대로(같은 자리의 글쇠 — B118 ④)
KEYS = {"ㅜ": "n", "ㄴ": "s", "ㅇ": "d", "ㅐ": "o", "ㅔ": "p", "ㅏ": "k", "ㅌ": "x"}


def _key(a):
    a = (a or "").strip()
    return KEYS.get(a[:1], a[:1].lower()), a[1:].strip()


def _rec_line(i, r):
    if r.get("kind") == HC.SAME:
        return f"     ✓{i} 같은 것 {r['name']} → {(r.get('target') or {}).get('name')}"
    u = r.get("upper") or {}
    return f"     ✓{i} 새것 {r['name']}[{r.get('category')}] — 위 노드 {u.get('name')}({u.get('kind')})"


def lines(board, step=False):
    """[5/8] 머리 아래 줄들 — `--step`이 아니면 끝에 다시 넣는 안내."""
    rows, tail = board.rows()
    recs = HC.of(board.doc_id)
    out = []
    if recs:
        out.append(f"   사람 기록 {len(recs)} — 적용(묻지 않는다 · 걷으려면 --step에서 d <번호>)")
        out += [_rec_line(i, r) for i, r in enumerate(recs, 1)]
    if rows:
        out.append(f"   이름 없는 대상 {len(rows)} — 소속 {sum(x['소속'] for x in rows):,} · 관계 {sum(x['관계'] for x in rows):,} · "
                   f"다른 문서 고아 {sum(sum(x['고아'].values()) for x in rows):,}(잃을 것이 많은 차례)")
        top = rows if _screen.VERBOSE else rows[:human.TOP]
        for i, it in enumerate(top, 1):
            out.append(f"     {i}. {'✓ ' if it['rec'] else ''}{it['name']} — 소속 {it['소속']}(개체 소실 {it['소실']}) · "
                       f"관계 {it['관계']} · 다른 문서 고아 {sum(it['고아'].values())} · 청크 {len(it['청크'])}")
        if len(rows) > len(top):
            out.append(f"     … 외 {len(rows) - len(top)}(-v면 전부)")
    if tail["종"]:
        out.append(f"   본문에 없는 이름 {tail['종']}종(관계 {tail['관계']}) — 더할 수 없다")
    if rows and not step:
        out.append("   살리려면 --step으로 다시 넣어 [5/8]에서 더한다 — 추출은 다시 쓴다(LLM 0)")
    return out


def _cmd(a):
    """물음의 답 — `(명령, 번호)` 또는 None(다시 묻는다)."""
    k, rest = _key(a)
    if k in ("n", "s", "d") and rest.isdigit():
        return k, int(rest)
    return None


def ask(board):
    """`--step`의 물음 — 계속(True) · 멈춤(False) · 더하기 · 같은 것 · 지우기(그 뒤 목록을 다시 센다)."""
    while True:
        got = _screen.answer(PROMPT, "go", eof=True, other=_cmd, hint=HELP)
        if got is True or got is False:
            return got
        k, i = got
        rows, _tail = board.rows()
        if k == "d":
            gone = HC.drop(board.doc_id, i)
            print(f"   지움 — {_rec_line(i, gone).strip()}" if gone else f"   기록 {i}번이 없다")
        elif not 1 <= i <= len(rows):
            print(f"   {i}번이 목록에 없다")
        elif k == "n":
            _add(board, rows[i - 1])
        else:
            _same(board, rows[i - 1])
        for ln in lines(board, step=True):
            print(ln)


def _up(u):
    return f"{u['name']}({u['kind']})" if u else "없음"


def _detail(board, it, up, cat):
    print(f"   ── 더하기 — '{it['name']}'")
    print(f"     위 노드 — {_up(up)} · 카테고리 — {cat}")
    why = board.why_not(up, cat)
    if why:
        print(f"     ✗ {why} — 위 노드 p · 카테고리 k로 바꾼다")
        return why
    pv = board.preview(it, up, cat)
    print(f"     만들 노드 — {pv['node']}")
    print(f"     들어갈 것 — 소속 {len(pv['belongs'])} · 관계 {len(pv['relations'])} · "
          f"다른 문서 고아 {sum(pv['orphans'].values())}")
    for item, place in pv["belongs"]:
        print(f"       소속 {item} · 지금 {place}")
    for line, fate in pv["relations"]:
        print(f"       관계 {line} — {fate}")
    if pv["orphans"]:
        top = sorted(pv["orphans"].items(), key=lambda x: (-x[1], x[0]))[:2]
        print("       다른 문서 고아 — " + " · ".join(f"{d} {n}" for d, n in top))
    return None


def _pick(title, items, label, rec):
    """번호 고르기 — Enter = 추천(`rec`) · 번호 · 그 밖의 글은 None과 그 글(「직접」)."""
    print(f"     {title}")
    for j, x in enumerate(items, 1):
        print(f"       {j}. {label(x)}" + ("  ← 추천" if x == rec else ""))
    a = _screen.answer("     번호(Enter = 추천 · 직접은 이름): ", "text", eof="")
    if not a:
        return rec, None
    if a.isdigit() and 1 <= int(a) <= len(items):
        return items[int(a) - 1], None
    return None, a


def _add(board, it):
    """더하기 — 상세 화면 · OK면 기록(목록을 다시 센다)."""
    up, cat = board.recommend(it)
    while True:
        why = _detail(board, it, up, cat)
        k, _rest = _key(_screen.answer(DETAIL, "text", eof="x"))
        if k == "o" and not why:
            HC.add(board.doc_id, {"kind": HC.NEW, "name": it["name"], "category": cat,
                                  "upper": {"name": up["name"], "category": up["category"], "kind": up["kind"]}})
            print(f"   기록 — 새것 {it['name']}[{cat}] · 위 노드 {_up(up)} — [6/8]이 노드를 세운다 · {HC.path().name}")
            return
        if k == "p":
            ups = board.uppers(it)
            rec = next((u for u in ups if board.why_not(u, cat) is None), None)
            got, typed = _pick("위 노드 — 그 이름이 나온 청크 위(가까운 제목 개체 → 좌표)", ups,
                               lambda u: f"{_up(u)} · {u['n']}청크" + ("" if board.why_not(u, cat) is None else " ✗ 매핑 없음"),
                               rec)
            if typed:
                got, err = board.direct(typed)
                if err:
                    print(f"     ✗ {err}")
            up = got or up
        elif k == "k":
            cats = board.categories()
            got, _typed = _pick("카테고리", cats, lambda c: c + ("" if board.why_not(up, c) is None else " ✗ 매핑 없음"),
                                cat if cat in cats else None)
            cat = got or cat
        elif k in ("x", ""):
            print("   취소 — 기록 0")
            return


def _same(board, it):
    """같은 것 — 대상(이번에 더한 이름 · 사전에서 맞는 노드 · 직접) · `ops alias`와 같은 검사 · OK면 기록."""
    ts = board.same_targets(it)
    got, typed = _pick(f"같은 것 — '{it['name']}'는 무엇의 다른 이름인가", ts,
                       lambda t: f"{t['name']}" + (" (이번에 더한 새것)" if t.get("new") else f" [{t.get('category')}]"),
                       ts[0] if ts else None)
    if typed:
        hit, err = board.direct(typed)
        if err:
            print(f"     ✗ {err}")
            return
        got = {"name": hit["name"], "layer": hit.get("layer"), "category": hit["category"]}
    if not got:
        print("   대상이 없다 — 기록 0")
        return
    why = board.same_check(it, got)
    if why:
        print(f"     ✗ {why} — 기록 0(합칠 것이면 ops merge)")
        return
    k, _rest = _key(_screen.answer(f"     같은 것 — '{it['name']}' → '{got['name']}' [OK o / 취소 x] ", "text", eof="x"))
    if k != "o":
        print("   취소 — 기록 0")
        return
    HC.add(board.doc_id, {"kind": HC.SAME, "name": it["name"],
                          "target": {"name": got["name"], "layer": got.get("layer"), "category": got.get("category")}})
    print(f"   기록 — 같은 것 {it['name']} → {got['name']} — [6/8]이 별칭으로 단다 · {HC.path().name}")


def end_line(s):
    """인입 끝의 사람 후보 한 줄(재료 `human.summary`)."""
    return (f"   사람 후보 — 새것 {s['새것']}(새 노드 {s['새 노드']} · 있는 노드로 {s['있는 노드로']} · 못 섬 {s['못 섬']}) · "
            f"같은 것 {s['같은 것']} · 이 문서에서 붙음 — 소속 {s['소속 붙음']} · 관계 {s['관계 붙음']}")
