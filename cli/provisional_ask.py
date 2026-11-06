# -*- coding: utf-8 -*-
"""칸 0.3 — **잠정 골격 노드 한 줄의 물음 — 승격 / 합침 / 그대로**(B184 ②③④) — 묻는 자리 하나 · 손은 `core/state/provisional_hand`.

부르는 자리 둘이 같은 함수 `decide`를 지난다 — 인입 `--step` 좌표 단계(`step_rows` — 이 문서에서 세울 잠정 · 정한 것은 그 문서의
나머지 행부터 · 재구축 0)와 인입 뒤 한 화면(`ops review` 첫 묶음 — 이미 세운 잠정 · 합침은 재구축 한 길). 답은 묻는 한 함수
(`_screen.answer`) — `p` 승격 · `m` 합침(`m <이름>`이면 그 골격 노드로) · `k` 그대로(「봄」) · 그 밖(빈 Enter)은 건너뜀.
"""
from __future__ import annotations

from cli import _screen
from core import paths

PROMPT = "[승격 p / 합침 m [이름] / 그대로 k / 건너뜀 Enter] "
#: 한글 자판 그대로(같은 자리의 글쇠 — B118 ④)
KEYS = {"ㅔ": "p", "ㅡ": "m", "ㅏ": "k"}
DONE = ("승격", "합침", "그대로", "건너뜀")


def _key(a):
    a = (a or "").strip()
    return KEYS.get(a[:1], a[:1].lower()), a[1:].strip()


def decide(row, actor, ask=None, indent="     ", answer=None):
    """한 줄 — `row` `{surface, canonical, nid?, parent?, near?}` · `answer`가 있으면 묻지 않고 그 답(`--step` 관문의 `p 1` 꼴의 뒤).
    돌려주는 것 `(한 일, 재구축 필요)`."""
    from core.state import provisional_hand as PH
    ask = ask or (lambda q: _screen.answer(q, "text", eof=""))
    k, rest = _key(answer if answer is not None else ask(f"{indent}'{row['canonical']}' {PROMPT}"))
    try:
        if k == "p":
            parent = row.get("parent") or (ask(f"{indent}  부모 미정 — 부모(골격 노드 이름 · Enter = 건너뜀): ") or "").strip()
            if not parent:
                return "건너뜀", False
            r = PH.promote(actor, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"], parent=parent)
            print(f"{indent}승격 — 골격 파일에 ({r['parent']} › {r['canonical']}) · 사람 고정 · 노드 그대로({str(r['id'])[:8]}) · "
                  f"{paths.show(r['file'])}")
            if r["polarity"]:
                print(f"{indent}  {PH.POLARITY_LINE}")
            return "승격", False
        if k == "m":
            target = rest or next(iter(row.get("near") or []), None) or \
                (ask(f"{indent}  합칠 골격 노드 이름(Enter = 건너뜀): ") or "").strip()
            if not target:
                return "건너뜀", False
            r = PH.merge(actor, target=target, nid=row.get("nid"), surface=None if row.get("nid") else row["surface"])
            print(f"{indent}합침 — '{' · '.join(r['surfaces'])}' → {r['target']} 골격 ALIASES · "
                  + (f"재구축이 필요하다 — {PH.REBUILD}" if r["rebuild"] else "이 문서의 나머지 행부터 그 골격 노드로"))
            return "합침", r["rebuild"]
        if k == "k" and row.get("nid"):
            PH.keep(actor, row["nid"])
            print(f"{indent}그대로 — 「봄」 표지(다음 화면은 접어 둔다)")
            return "그대로", False
        if k == "k":
            return "그대로", False
    except PH.Refused as e:
        print(f"{indent}[거부] {e}")
    return "건너뜀", False


def step_rows(env):
    """**`--step` 좌표 단계의 잠정 줄**(B184 ③) — 이 문서에서 세울 잠정(계획 `provisional.preview` — 쓰기 0 · 같은 표기는 한 줄)."""
    from core.build import provisional
    rows, seen = [], set()
    for e in provisional.preview(env):
        if e["act"] == "new" and e["surface"] not in seen:
            seen.add(e["surface"])
            rows.append({"surface": e["surface"], "canonical": e.get("canonical") or e["surface"],
                         "parent": e.get("up_name"), "near": e.get("near")})
    return rows


#: `--step` 좌표 단계의 물음 — 지금 관문 답 규칙(계속은 c(ㅊ)만 · 멈춤 q) + 잠정 줄의 처분(번호 — 사람 후보 관문 [5/8]과 같은 꼴)
GATE_PROMPT = "   [계속 c / 멈춤 q / 승격 p <번호> / 합침 m <번호> [이름] / 그대로 k <번호>] "
GATE_HELP = "   c(ㅊ) 계속 · q(ㅂ) 멈춤 · p <번호> 승격 · m <번호> [골격 이름] 합침 · k <번호> 그대로 — 다시 친다"


def _gate_cmd(a):
    k, rest = _key(a)
    num, _sp, name = rest.partition(" ")
    if k in ("p", "m", "k") and num.isdigit():
        return k, int(num), name.strip()
    return None


def gate(env):
    """**`--step` 좌표 단계의 물음**(B184 ③) — 잠정 줄이 있으면 번호로 처분(정한 것은 그 문서의 나머지 행부터 · 재구축 0) → 계속 /
    멈춤. 행위자는 셸 사용자 이름(인입 명령에 `--actor`가 없다 — D-269)."""
    import getpass
    try:
        actor = f"{getpass.getuser()}(--step)"
    except Exception:                                # noqa: BLE001 — 사용자 이름을 못 읽는 환경
        actor = "사람(--step)"
    while True:
        rows = step_rows(env)
        for i, r in enumerate(rows, 1):
            print(f"     {i}. {r['canonical']} — 부모 {r['parent'] or '미정'} · 합칠 후보 {' · '.join(r['near'] or []) or '—'}")
        got = _screen.answer(GATE_PROMPT if rows else "   [계속 c / 멈춤 q] ", "go", eof=True,
                             other=_gate_cmd if rows else None, hint=GATE_HELP)
        if got is True or got is False:
            return got
        k, i, name = got
        if not 1 <= i <= len(rows):
            print(f"     {i}번이 목록에 없다")
            continue
        decide(rows[i - 1], actor, answer=f"{k} {name}".strip())
