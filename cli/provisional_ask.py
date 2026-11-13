# -*- coding: utf-8 -*-
"""칸 0.3 — **골격 칸의 물음**(B184 ②③④ · B196 ③) — 묻는 자리 하나 · 손은 `core/state/provisional_hand`(표기) · `core/state/coord_acks`(쌍).

부르는 자리 둘이 같은 함수 `decide`를 지난다 — 인입 `--step` 좌표 단계(`step_rows` — 이 문서의 문에 걸린 표기 · 쌍 어긋남 · 정한 것은
그 문서의 나머지 행부터 · 재구축 0)와 인입 뒤 한 화면(`ops review` 첫 묶음 — 문서를 넘어 · 이미 세운 잠정 노드 포함). 줄은 셋이다:

| 줄 | 처분(글쇠) |
|---|---|
| 문에 걸린 표기(`kind: gate`) | 같은 것으로 `m [번호|이름]` · 새로 만들기 `k [번호]` · 버리기 `d <사유>` · 위로 `u`(겸 값 줄만) |
| 쌍 어긋남(`kind: pair`) | 그대로 연결 `a` · 새로 만들기 `k [번호]`(문서의 상위 밑) · 같은 것으로 `m <번호|이름>`(정정) · 버리기 `d <사유>` |
| 이미 세운 잠정 노드(`nid`) | 승격 `p` · 합침 `m [이름]` · 그대로 `k`(「봄」) · 건너뜀 |

문 · 쌍 줄의 표와 물음(한 줄씩 말 또는 글쇠 — 말은 LLM이 읽는다)은 한 고리 `cli/gate_table.loop`(B202) · 잠정 노드 줄은 `ops review`의
물음 · 한글 자판 짝 그대로(B118 ④).
"""
from __future__ import annotations

from cli import _screen
from core import paths

PROMPT = "[승격 p / 합침 m [이름] / 그대로 k / 건너뜀 Enter] "
#: 한글 자판 그대로(같은 자리의 글쇠 — B118 ④)
KEYS = {"ㅔ": "p", "ㅡ": "m", "ㅏ": "k", "ㅇ": "d", "ㅁ": "a", "ㄱ": "r", "ㅕ": "u"}
DONE = ("승격", "합침", "그대로", "새로", "drop", "올림", "확인", "정정", "해석 고침", "자동", "건너뜀")


def key_of(ch):
    """글쇠 하나 — 한글 자판 짝 그대로."""
    return KEYS.get(ch, (ch or "").lower())


def _key(a):
    a = (a or "").strip()
    return key_of(a[:1]), a[1:].strip()


def _pick(rest, cands):
    """후보 번호(1 · 2) 또는 이름 — 없으면 첫 후보."""
    if rest.isdigit():
        i = int(rest)
        return cands[i - 1]["name"] if 1 <= i <= len(cands) else None
    return rest or (cands[0]["name"] if cands else None)


def decide(row, actor, ask=None, indent="     ", answer=None, under=None):
    """한 줄 — `answer`가 있으면 묻지 않고 그 답(문 · 쌍 줄은 늘 `answer` — 표 고리 `cli/gate_table`의 처분) · `under` = 새로 만들기의
    부모(골격 노드 canonical — B203 ④). 돌려주는 것 `(한 일, 재구축 필요)` · 그 줄에 쓸 수 없는 글쇠는 거부(기록 0 — B202 ③)."""
    from core.state import coord_acks
    from core.state import provisional_hand as PH
    from core.state.gate_say import allowed
    ask = ask or (lambda q: _screen.answer(q, "text", eof=""))
    kind = row.get("kind")
    name = f"'{row.get('canonical') or row['surface']}'"
    k, rest = _key(answer if answer is not None else ask(f"{indent}{name} {PROMPT}"))
    if kind in ("gate", "pair") and k and k not in allowed(row):
        print(f"{indent}[거부] 이 줄({'공정 짝 어긋남' if kind == 'pair' else '공정 표기'})에는 '{k}'를 쓸 수 없다 — {' · '.join(allowed(row))}")
        return "건너뜀", False
    try:
        if kind == "pair":
            return _pair(row, k, rest, actor, indent, coord_acks, under)
        if k == "d" and kind == "gate":
            PH.drop(actor, row["surface"], row.get("up_name"), rest)
            print(f"{indent}버리기 — '{row['surface']}'({row.get('up_name') or '부모 미정'}) 세우지 않는다 · 사유 {rest} · 재연결이 다시 열지 않는다")
            return "drop", False
        if k == "u" and kind == "gate":
            if not row.get("also"):
                print(f"{indent}[거부] 올림은 골격 단 값(겸)의 줄만 — 공정 표기는 합침 · 새로 · 승격 · drop")
                return "건너뜀", False
            PH.raise_up(actor, row["surface"], row.get("up_name"), rest)
            print(f"{indent}위로 — '{row['surface']}' 노드 0 · 그 값과 딸린 값은 위 공정 {row.get('up_name')}에 바로(재연결이 보류 행을 잇는다)")
            return "올림", False
        if k == "k" and kind == "gate":
            PH.seed(actor, row["surface"], row.get("up_name"), under=under)
            print(f"{indent}새로 만들기 — '{row['surface']}'(부모 {under or row.get('up_name') or '미정'}) 잠정 골격 노드로 선다(그 문서의 "
                  "나머지 행부터 · 재연결이 보류 행을 잇는다)")
            return "새로", False
        if k == "p":
            parent = row.get("parent") or row.get("up_name") or \
                (ask(f"{indent}  부모 미정 — 부모(골격 노드 이름 · Enter = 건너뜀): ") or "").strip()
            if not parent:
                return "건너뜀", False
            r = PH.promote(actor, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"], parent=parent)
            print(f"{indent}승격 — 골격 파일에 ({r['parent']} › {r['canonical']}) · 사람 고정 · 노드 그대로({str(r['id'])[:8]}) · "
                  f"{paths.show(r['file'])}")
            return "승격", False
        if k == "m":
            target = _pick(rest, row.get("candidates") or []) if kind == "gate" else \
                (rest or next(iter(row.get("near") or []), None))
            target = target or (ask(f"{indent}  합칠 골격 노드 이름(Enter = 건너뜀): ") or "").strip()
            if not target:
                return "건너뜀", False
            r = PH.merge(actor, target=target, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"])
            print(f"{indent}같은 것으로 — '{' · '.join(r['surfaces'])}' → {r['target']} 골격 ALIASES · "
                  + (f"재구축이 필요하다 — {PH.REBUILD}" if r["rebuild"] else "이 문서의 나머지 행부터 그 골격 노드로"))
            return "합침", r["rebuild"]
        if k == "k" and row.get("nid"):
            PH.keep(actor, row["nid"])
            print(f"{indent}그대로 — 「봄」 표지(다음 화면은 접어 둔다 · 재구축 뒤에도 그 노드가 선다)")
            return "그대로", False
    except (PH.Refused, coord_acks.AckRefused) as e:
        print(f"{indent}[거부] {e}")
    return "건너뜀", False


def _pair(row, k, rest, actor, indent, coord_acks, under=None):
    pair = (row["up"], row["ref"])
    if k == "a":
        coord_acks.ack(row["pair_kind"], pair, actor, seen=True)
        print(f"{indent}그대로 연결 — '{row['ref']}' 자리 그대로 붙인다(이 공정 짝은 다시 묻지 않는다)")
        return "확인", False
    if k == "k":                                      # 쌍 줄의 새로 만들기(B203 ④) — 문서의 상위(또는 고른 부모) 밑에 그 하위 이름으로
        from core.state import catalog, provisional_hand as PH
        PH.seed(actor, row["surface"], row["up"], under=under, pair=True)
        target = f"{under or row['up']}{catalog.sep()}{row['surface']}"
        coord_acks.fix(row["pair_kind"], pair, target, actor, note="새로 만들기")
        print(f"{indent}새로 만들기 — {target} 잠정 골격 노드(그 공정 짝의 행은 그 노드에 · 그 문서의 나머지 행부터)")
        return "새로", False
    if k == "m":                                      # 쌍 줄의 「같다」 = 정정(B202 ③ — 같은 뜻)
        target = _pick(rest, row.get("candidates") or [])
        if not target:
            print(f"{indent}[거부] 정정할 노드가 없다 — m <줄> <후보 번호|이름>")
            return "건너뜀", False
        coord_acks.fix(row["pair_kind"], pair, target, actor)
        print(f"{indent}같은 것으로 — '{row['up']}' 아래의 '{row['surface']}' = {target}(그 행들은 그 노드에)")
        return "정정", False
    if k == "d":
        coord_acks.drop(row["pair_kind"], pair, actor, rest)
        print(f"{indent}버리기 — 그 공정 짝의 행은 붙이지 않는다 · 사유 {rest}")
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


def actor():
    """행위자 — 셸 사용자 이름(인입 명령에 `--actor`가 없다 — D-269)."""
    import getpass
    try:
        return f"{getpass.getuser()}(--step)"
    except Exception:                                # noqa: BLE001 — 사용자 이름을 못 읽는 환경
        return "사람(--step)"


def gate(env):
    """**`--step` 좌표 단계의 물음**(B184 ③ · B196 ③ · B202 ④) — 줄이 있으면 골격 칸 표 고리(`cli/gate_table.loop` — LLM 판단 · 말 또는
    글쇠 · 처분 뒤 다시 그림 · 정한 것은 그 문서의 나머지 행부터 · 재구축 0) → 계속 / 멈춤."""
    rows = step_rows(env)
    if not rows:
        return _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True)
    from cli import gate_table
    g, p = sum(1 for r in rows if r["kind"] == "gate"), sum(1 for r in rows if r["kind"] == "pair")
    return gate_table.loop(rows, actor(), title=f"골격 칸 처분 — 추출 전(공정 표기 {g:,} · 공정 짝 어긋남 {p:,}) {len(rows):,}줄 · "
                                                 "여기서 정한 공정이 추출의 후보가 된다")
