# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 물음**(B184 ②③④ · B196 ③) — 묻는 자리 하나 · 손은 `core/state/provisional_hand`(표기) · `core/state/coord_acks`(쌍).

부르는 자리 둘이 같은 함수 `decide`를 지난다 — 인입 `--step` 좌표 단계(`step_rows` — 이 문서의 문에 걸린 표기 · 쌍 어긋남 · 정한 것은
그 문서의 나머지 행부터 · 재구축 0)와 인입 뒤 한 화면(`ops review` 첫 묶음 — 문서를 넘어 · 이미 세운 잠정 노드 포함). 줄은 셋이다:

| 줄 | 처분(글쇠) |
|---|---|
| 문에 걸린 표기(`kind: gate`) | 합침 `m [후보 번호|이름]` · 새로 `k` · 승격 `p` · drop `d <사유>` · 올림 `u`(골격 단 값만 — B197) · 건너뜀 |
| 쌍 어긋남(`kind: pair`) | 확인 `a` · 정정 `r <후보 번호|이름>` · drop `d <사유>` · 건너뜀 |
| 이미 세운 잠정 노드(`nid`) | 승격 `p` · 합침 `m [이름]` · 그대로 `k`(「봄」) · 건너뜀 |

답은 묻는 한 함수(`_screen.answer`) · 한글 자판 짝 그대로(B118 ④).
"""
from __future__ import annotations

from cli import _screen
from core import paths

PROMPT = "[승격 p / 합침 m [이름] / 그대로 k / 건너뜀 Enter] "
PROMPT_GATE = "[합침 m [후보|이름] / 새로 k / 승격 p / drop d <사유> / 올림 u / 건너뜀 Enter] "
PROMPT_PAIR = "[확인 a / 정정 r <후보|이름> / drop d <사유> / 건너뜀 Enter] "
#: 한글 자판 그대로(같은 자리의 글쇠 — B118 ④)
KEYS = {"ㅔ": "p", "ㅡ": "m", "ㅏ": "k", "ㅇ": "d", "ㅁ": "a", "ㄱ": "r", "ㅕ": "u"}
DONE = ("승격", "합침", "그대로", "새로", "drop", "올림", "확인", "정정", "건너뜀")


def _key(a):
    a = (a or "").strip()
    return KEYS.get(a[:1], a[:1].lower()), a[1:].strip()


def _pick(rest, cands):
    """후보 번호(1 · 2) 또는 이름 — 없으면 첫 후보."""
    if rest.isdigit():
        i = int(rest)
        return cands[i - 1]["name"] if 1 <= i <= len(cands) else None
    return rest or (cands[0]["name"] if cands else None)


def decide(row, actor, ask=None, indent="     ", answer=None):
    """한 줄 — `answer`가 있으면 묻지 않고 그 답(`--step` 관문의 `m 1 1` 꼴의 뒤). 돌려주는 것 `(한 일, 재구축 필요)`."""
    from core.state import coord_acks
    from core.state import provisional_hand as PH
    ask = ask or (lambda q: _screen.answer(q, "text", eof=""))
    kind = row.get("kind")
    q = {"gate": PROMPT_GATE, "pair": PROMPT_PAIR}.get(kind, PROMPT)
    name = f"'{row['up']}' · '{row['surface']}'" if kind == "pair" else f"'{row.get('canonical') or row['surface']}'"
    k, rest = _key(answer if answer is not None else ask(f"{indent}{name} {q}"))
    try:
        if kind == "pair":
            return _pair(row, k, rest, actor, indent, coord_acks)
        if k == "d" and kind == "gate":
            PH.drop(actor, row["surface"], row.get("up_name"), rest)
            print(f"{indent}drop — '{row['surface']}'({row.get('up_name') or '부모 미정'}) 세우지 않는다 · 사유 {rest} · 재연결이 다시 열지 않는다")
            return "drop", False
        if k == "u" and kind == "gate":
            if not row.get("also"):
                print(f"{indent}[거부] 올림은 골격 단 값(겸)의 줄만 — 공정 표기는 합침 · 새로 · 승격 · drop")
                return "건너뜀", False
            PH.raise_up(actor, row["surface"], row.get("up_name"), rest)
            print(f"{indent}올림 — '{row['surface']}' 노드 0 · 그 값과 딸린 값은 위 공정 {row.get('up_name')}에 바로(재연결이 보류 행을 잇는다)")
            return "올림", False
        if k == "k" and kind == "gate":
            PH.seed(actor, row["surface"], row.get("up_name"))
            print(f"{indent}새로 — '{row['surface']}'(부모 {row.get('up_name') or '미정'}) 잠정 골격 노드로 선다(그 문서의 나머지 행부터 · "
                  "재연결이 보류 행을 잇는다)")
            return "새로", False
        if k == "p":
            parent = row.get("parent") or row.get("up_name") or \
                (ask(f"{indent}  부모 미정 — 부모(골격 노드 이름 · Enter = 건너뜀): ") or "").strip()
            if not parent:
                return "건너뜀", False
            r = PH.promote(actor, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"], parent=parent)
            print(f"{indent}승격 — 골격 파일에 ({r['parent']} › {r['canonical']}) · 사람 고정 · 노드 그대로({str(r['id'])[:8]}) · "
                  f"{paths.show(r['file'])}")
            if r["polarity"]:
                print(f"{indent}  {PH.POLARITY_LINE}")
            return "승격", False
        if k == "m":
            target = _pick(rest, row.get("candidates") or []) if kind == "gate" else \
                (rest or next(iter(row.get("near") or []), None))
            target = target or (ask(f"{indent}  합칠 골격 노드 이름(Enter = 건너뜀): ") or "").strip()
            if not target:
                return "건너뜀", False
            r = PH.merge(actor, target=target, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"])
            print(f"{indent}합침 — '{' · '.join(r['surfaces'])}' → {r['target']} 골격 ALIASES · "
                  + (f"재구축이 필요하다 — {PH.REBUILD}" if r["rebuild"] else "이 문서의 나머지 행부터 그 골격 노드로"))
            return "합침", r["rebuild"]
        if k == "k" and row.get("nid"):
            PH.keep(actor, row["nid"])
            print(f"{indent}그대로 — 「봄」 표지(다음 화면은 접어 둔다 · 재구축 뒤에도 그 노드가 선다)")
            return "그대로", False
    except (PH.Refused, coord_acks.AckRefused) as e:
        print(f"{indent}[거부] {e}")
    return "건너뜀", False


def _pair(row, k, rest, actor, indent, coord_acks):
    pair = (row["up"], row["ref"])
    if k == "a":
        coord_acks.ack(row["pair_kind"], pair, actor, seen=True)
        print(f"{indent}확인 — '{row['ref']}' 자리 그대로 붙인다(이 쌍은 다시 묻지 않는다)")
        return "확인", False
    if k == "r":
        target = _pick(rest, row.get("candidates") or [])
        if not target:
            print(f"{indent}[거부] 정정할 노드가 없다 — r <줄> <후보 번호|이름>")
            return "건너뜀", False
        coord_acks.fix(row["pair_kind"], pair, target, actor)
        print(f"{indent}정정 — '{row['up']}' 아래의 '{row['surface']}' = {target}(그 행들은 그 노드에)")
        return "정정", False
    if k == "d":
        coord_acks.drop(row["pair_kind"], pair, actor, rest)
        print(f"{indent}drop — 그 쌍의 행은 붙이지 않는다 · 사유 {rest}")
        return "drop", False
    return "건너뜀", False


def rows_of(rv):
    """검토 재료(`skeleton_review.review` · 큐에서) → 묻는 줄 — 문에 걸린 표기 먼저 · 쌍 어긋남 뒤(번호는 한 줄 차례)."""
    out = [dict(e, kind="gate") for e in rv.get("held") or []]
    out += [dict(p, kind="pair", pair_kind=p["kind"]) for p in rv.get("pairs") or []]
    return out


def step_rows(env):
    """**`--step` 좌표 단계의 줄**(B196 ③) — 이 문서의 문에 걸린 표기 · 쌍 어긋남(계획 — 쓰기 0)."""
    from core.build import skeleton_review
    return rows_of(skeleton_review.review(env))


def show_rows(rows, indent="     "):
    """줄 표 — 문에 걸린 표기(번호 · 표기 · 들어온 자리 · 행 수 · 판단 · 후보 둘) · 쌍 어긋남(번호 · 상위 · ref · 실제 위 · 행 수 · 후보)."""
    for i, r in enumerate(rows, 1):
        cands = " · ".join(f"{j}.{c['name']}(경로 {c['path']} · 행 {c['rows']} · 자식 {c['kinds']}종)"
                           for j, c in enumerate(r.get("candidates") or [], 1)) or "—"
        if r["kind"] == "gate":
            ans = {"uncertain": "애매", "new": "다르다"}.get(r.get("answer"), r.get("answer") or "—")
            conf = r.get("confidence")
            print(f"{indent}{i}. 문 — {r['surface']} · 들어온 자리 {r.get('up_name') or '미정'} · 행 {r['rows']} · 판단 {ans}"
                  + (f"(확실도 {conf:.2f})" if isinstance(conf, (int, float)) else "") + f" · 후보 {cands}"
                  + (f" · 문서 {' · '.join(r['docs'])}" if r.get("docs") else ""))
        else:
            print(f"{indent}{i}. 쌍 — 상위 {r['up']} · ref {r['surface']} · 실제 위 {r['real_up']} · 행 {r['rows']} · 후보 {cands}"
                  + (f" · 문서 {' · '.join(r['docs'])}" if r.get("docs") else ""))


#: `--step` 좌표 단계의 물음 — 지금 관문 답 규칙(계속은 c(ㅊ)만 · 멈춤 q) + 줄의 처분(번호 — 사람 후보 관문 [5/8]과 같은 꼴)
GATE_PROMPT = ("   [계속 c / 멈춤 q / 합침 m <줄> [후보|이름] / 새로 k <줄> / 승격 p <줄> / drop d <줄> <사유> / 올림 u <줄> / "
               "쌍 확인 a <줄> / 쌍 정정 r <줄> <후보|이름>] ")
GATE_HELP = ("   c(ㅊ) 계속 · q(ㅂ) 멈춤 · m <줄> [후보 번호|이름] 합침 · k <줄> 새로 · p <줄> 승격 · d <줄> <사유> drop · "
             "u <줄> 올림(골격 단 값) · a <줄> 쌍 확인 · r <줄> <후보 번호|이름> 쌍 정정 — 다시 친다")


def _gate_cmd(a):
    k, rest = _key(a)
    num, _sp, name = rest.partition(" ")
    if k in ("p", "m", "k", "d", "u", "a", "r") and num.isdigit():
        return k, int(num), name.strip()
    return None


def actor():
    """행위자 — 셸 사용자 이름(인입 명령에 `--actor`가 없다 — D-269)."""
    import getpass
    try:
        return f"{getpass.getuser()}(--step)"
    except Exception:                                # noqa: BLE001 — 사용자 이름을 못 읽는 환경
        return "사람(--step)"


def gate(env):
    """**`--step` 좌표 단계의 물음**(B184 ③ · B196 ③) — 줄이 있으면 번호로 처분(정한 것은 그 문서의 나머지 행부터 · 재구축 0) → 계속 / 멈춤."""
    who = actor()
    while True:
        rows = step_rows(env)
        show_rows(rows)
        got = _screen.answer(GATE_PROMPT if rows else "   [계속 c / 멈춤 q] ", "go", eof=True,
                             other=_gate_cmd if rows else None, hint=GATE_HELP)
        if got is True or got is False:
            return got
        k, i, name = got
        if not 1 <= i <= len(rows):
            print(f"     {i}번이 목록에 없다")
            continue
        decide(rows[i - 1], who, answer=f"{k} {name}".strip())
