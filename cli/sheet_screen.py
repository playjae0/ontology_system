# -*- coding: utf-8 -*-
"""칸 3.1 — **시트 역할 관문의 화면** (B83 ②③ · B91 ② · B112 ②) — `cli/ingest_screen.py`에서 떼어냈다(§7 상한 800).

판정은 `cli/sheet_gate.py`(관문 한 벌) · 표의 재료는 `parser/form.sheet_table()`(리더가 낸 값의 투영 — 새 판독 0)이다.
여기는 줄만 그린다: 표 · 자동 모드 줄 · 기록 줄 · 묻기 · 비대화형 거부 문면.
"""
from __future__ import annotations

from pathlib import Path

from cli import _screen
from core import paths

# ── 시트 역할 관문 (B83 ②③ · 칸 2.2 · 3.1) ──────────────────────────────────
# **묻는 자리는 하나다** — 시트가 여러 장인 엑셀을 prose로 넣을 때, 문서마다 사람이
# 한 번 정한다. 표의 재료는 `parser/form.sheet_table()`이고 **여기서 새로 판독하지
# 않는다**(reader가 이미 낸 값의 투영 — 화면이 제 계산을 하지 않는다는 B81 ①과 같다).
#
# 제안은 **두 벌**이다(B91 ②): 로직(모양만 · LLM 0)과 LLM(표본 줄만 · 지점 ⑩) — 둘 다 층을 모른다(B148 ④).
# 마지막 열 「제안」은 둘이 같으면 그것, 어긋나면 `ref`다(모르면 ref) — 사람이 표를
# 보고 고치고, 그 답이 기록이 된다(`core/state/sheets.py`).
SHEET_HEAD = "   " + (_screen.pad("#", 4) + _screen.pad("시트", 20)
                      + _screen.pad("행", 6) + _screen.pad("열", 5)
                      + _screen.pad("숨김", 10) + _screen.pad("글자셀", 8)
                      + _screen.pad("앞부분", 34) + _screen.pad("로직", 7)
                      + _screen.pad("LLM", 7) + "제안")


#: 시트 상태(openpyxl `sheet_state`) → 표의 숨김 칸
STATE_LABEL = {"visible": "-", "hidden": "숨김", "veryHidden": "아주 숨김"}


def sheet_again_line(doc, rows, flag_cmd=None):
    """기록대로 진행할 때 **다시 고르는 명령줄 한 줄**(B112 ②) — 지금 기록 그대로의 문자열을 싣는다."""
    from core.state import sheets as SH
    sug = " ".join(f"{r['no']}:{r['suggest']}" for r in rows)
    cmd = (flag_cmd or f'python run.py ingest-file {doc} --sheets "{{sheets}}"').replace("{sheets}", sug)
    hid = [f"{r['no']} {r['name']}" for r in rows if r.get("state", "visible") != "visible"]
    return (f"   ▶ 다시 고르려면 — {cmd}  (기록을 덮는다 · 지금 제안)"
            + (f" · 숨김 시트 {len(hid)}장: {' · '.join(hid)}" if hid else ""))


def sheet_pieces_line(env, roles):
    """**파싱 끝 — 시트별 조각 수**(역할과 함께 · B112 ②) — 봉투의 조각이 든 `meta.sheet`에서(새 판독 0)."""
    from collections import Counter
    pcs = (env or {}).get("records") or (env or {}).get("chunks") or []
    n = Counter((p.get("meta") or {}).get("sheet") for p in pcs)
    parts = [f"{name}({role}) {n.get(name, 0):,}" for name, role in (roles or {}).items()]
    other = sum(v for k, v in n.items() if k not in (roles or {}))
    return ("   시트별 조각 — " + " · ".join(parts) + (f" · 시트 표시 없음 {other:,}" if other else ""))


def sheet_note(rec, pend):
    """머리의 괄호 — **기록의 상태를 말한다**(처음인가 · 미결이 있나)."""
    if not rec:
        return "기록 없음 — 이 문서는 처음이다"
    return (f"기록 있음({rec.get('decided_by')} · {rec.get('at')})"
            + (f" · **미결 {len(pend)}장** — 새 시트가 생겼다" if pend
               else " — 다시 묻지 않는다"))


def sheet_row(r, known=None):
    """표 한 줄 — 값은 `form.sheet_table()`이 낸 것 그대로."""
    role = (known or {}).get(r["name"])
    hid = r.get("state", "visible") != "visible"
    last = (f"기록 {role}" if role else r["suggest"]) + ("  ⚠ 기록 prose · 숨김 시트" if hid and role == "prose" else "")
    return "   " + (_screen.pad(r["no"], 4)
                    + _screen.pad(_screen.cut(r["name"], 18), 20)
                    + _screen.pad(f"{r['rows']:,}", 6) + _screen.pad(r["cols"], 5)
                    + _screen.pad(STATE_LABEL.get(r.get("state", "visible"), r.get("state")), 10)
                    + _screen.pad(f"{int(round(r['text_ratio'] * 100))}%", 8)
                    + _screen.pad(_screen.cut("「" + (r["head"] or "—") + "」", 32), 34)
                    + _screen.pad(r.get("logic") or r["suggest"], 7)
                    + _screen.pad(r.get("llm") or "끔", 7)
                    + last)


def sheet_table_block(rows, *, file, rec=None, pend=None):
    """시트 **전부**의 표 — 이름을 다 보여 주고 묻는다(사용자 확정).

    `--dry-run`도 이것만 찍는다(묻지 않는다 · 기록 0).
    """
    out = [f"■ 시트 역할 — {Path(file).name} · {len(rows)}장 "
           f"({sheet_note(rec, pend or [])})", SHEET_HEAD]
    known = (rec or {}).get("sheets") or {}
    out += [sheet_row(r, known) for r in rows]
    why = [f"      {r['no']} {r['name']} — LLM: {r['llm_reason']}" for r in rows
           if r.get("llm_reason") and r.get("llm") != r.get("logic")]
    return "\n".join(out + why)


def sheet_auto_line(roles, promote, by):
    """자동 모드의 한 줄 — 합의로 정한 수 · **승격 후보**(어긋나 `ref`로 둔 시트)."""
    from core.state import sheets as SH
    return (f"   자동 모드 — {SH.summary(roles)} (LLM {by})"
            + (f" · **승격 후보 {len(promote)}장**: {' · '.join(promote)} "
               f"(로직과 LLM이 어긋나 ref로 두었다 — 올리려면 --sheets \"<번호>:prose\")"
               if promote else " · 승격 후보 0"))


def sheet_roles_line(roles, doc_id):
    """답이 기록이 된 뒤의 한 줄 — 무엇이 몇이고 어디에 남았나."""
    from core.state import sheets as SH
    return (f"   시트 역할 — {SH.summary(roles)} → "
            f"{paths.rel_to_home(SH.path(doc_id))}")


def sheet_gate(rows, *, file, doc_id, rec=None):
    """관문 — 표를 보이고 한 줄을 받는다. 돌려주는 것은 `{시트: 역할}` 또는 `None`(중단).

    **조용한 기본값이 없다**(요청문 ③): Enter는 「제안 그대로」라고 화면이 말한 뒤에만
    제안이 되고, 역할이 안 정해진 시트가 남으면 다시 묻는다. `q`는 그 문서 중단이고
    그래프·기록 쓰기가 0이다.
    """
    from parser.form import parse_sheet_spec
    from core.state import sheets as SH
    names = [r["name"] for r in rows]
    roles = dict((rec or {}).get("sheets") or {})
    pend = SH.pending(roles, names)
    print(sheet_table_block(rows, file=file, rec=rec, pend=pend))
    while True:
        ans = _screen.answer("\n   역할 — 번호:역할 (예 2-3:prose 4:ref *:ref · Enter=제안대로 · q=중단): ", "text")
        if ans is None:
            return None                       # 비대화형 · Ctrl-C — 같은 처분(조용히 넘기지 않는다)
        if ans.lower() in ("q", "ㅂ", "quit"):
            print(f"   중단 — {Path(file).name}은 읽지 않았다(그래프·기록 쓰기 0).")
            return None
        if not ans:                           # Enter = 제안 그대로 (미결 시트만)
            got = {r["name"]: r["suggest"] for r in rows if r["name"] in pend}
        else:
            got, err = parse_sheet_spec(ans, names)
            if err:
                print(f"   [사용법] {err}")
                continue
        merged = {**roles, **got}
        left = SH.pending(merged, names)
        if left:
            print(f"   역할이 안 정해진 시트가 남았다 — {' · '.join(left)} "
                  f"(`*:ref`처럼 나머지를 한 번에 줄 수 있다)")
            roles, pend = merged, left
            continue
        return merged


def sheets_refusal(doc, rows, *, pend=None, rec=None, retry=None, flag_cmd=None):
    """**비대화형이면 묻지 않고 상태 거부**다 — 문면에 시트 이름 **전부**와 다음 줄을 싣는다.

    묻고 EOF를 받아 조용히 제안대로 넣으면, 가격 시트가 그래프에 들어간 사실이
    어디에도 남지 않는다(요청문의 출처). 배치에서는 **그 문서만** 실패한다.

    다음 줄은 **호출자가 안다**(B86 ⑤) — 인입이면 `ingest-file`, 등록이면
    `register generate`다. 없으면 인입의 줄이다.
    """
    from parser.form import SHEET_ROLES
    names = [r["name"] for r in rows]
    what = (f"기록에 없는 시트 {len(pend)}장 — {' · '.join(pend)}" if pend
            else f"시트 {len(names)}장의 역할이 정해지지 않았다")
    sug = " ".join(f"{r['no']}:{r['suggest']}" for r in rows
                   if not pend or r["name"] in pend)
    retry_line = retry or f"python run.py ingest-file {doc}"
    flag_line = (flag_cmd or f'python run.py ingest-file {doc} --sheets "{{sheets}}"'
                 ).replace("{sheets}", sug)
    return "\n".join([
        f"■ 시트 역할 미정 — {Path(doc).name} ({what})",
        "   시트: " + " · ".join(f"{r['no']} {r['name']}" for r in rows),
        "   비대화형이라 묻지 않는다 — 조용한 기본값은 없다(역할 없이 읽으면 "
        "가격·일정 시트까지 그래프 후보가 된다).",
        "   ▶ 다음 줄:",
        f"     터미널에서:          {retry_line}",
        f"     역할을 바로 주려면:   {flag_line}",
        f"     자동 모드(로직·LLM 합의만 자동 · 어긋나면 ref): "
        f"{flag_line.split(' --sheets ')[0]} --sheets auto",
        f"     (제안대로 넣으려면 위 문자열 그대로 · 역할은 "
        f"{'|'.join(SHEET_ROLES)})",
    ])
