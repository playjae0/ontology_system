# -*- coding: utf-8 -*-
"""칸 3.1 · 3.8 · 1.6 — **시트 역할 관문 한 벌**: 인입 · `parse run` · 등록 표본이 같은 함수를 부른다 (B83 ③ · B86 ⑤).

시트 여럿인 prose 엑셀은 문서마다 시트의 역할이 다르다 — 사람이 **문서마다 한 번**
정하고(`read`·`ref`·`skip`), 답은 `registry/sheet_roles/<doc_id>.json`에 남는다.

`cli/ingest.py`에서 떼어냈다(B86 ⑤): 등록 표본에도 같은 관문을 걸어야 했고(B83 누락 —
등록 리허설·킷 관문이 시트 전부를 돌았다), 그 파일이 775행이었다(§7 상한 800).
**관문 함수는 `gate()` 하나다** — 호출자가 셋이어도 묻는 말·기록·거부 문면이 갈리지
않는다. 호출자가 다른 것은 두 가지뿐이다: 갈래(`kind`)를 어디서 아는가(인입은 등록부,
등록은 초안 스키마)와 거부 문면의 다음 줄(무엇을 다시 치면 되나).

**두 모드**(B91 ② · 칸 3.8): **사람 지정 = 기본**(표에 로직 제안과 LLM 제안을 나란히 —
어긋나면 기본 제안은 `ref` · 사람이 정한다 · `--no-sheet-llm`이면 로직만) · **자동**
(`--sheets auto` — 합의하면 자동, 어긋나면 `ref` + 승격 후보). **판정은 층을 모른다**(B148 ④ — 로직은 모양만 ·
LLM은 표본 줄만 · 층과 그래프 상태가 바뀌어도 같은 시트의 제안이 같다 · 층마다 볼 시트를 정하는 확장은 이 회차 밖).
기록은 로직 · LLM · 최종 · 결정 주체.
"""
from __future__ import annotations

import sys
from pathlib import Path

from cli import sheet_screen as SCR
from core.state import log
from parser import form as form_mod, reader as reader_mod
from parser.reader import GRID_EXT

_LOG = log.get("cli.sheet_gate")

#: 관문이 멈춘 두 모양 — 호출자가 제 화면의 상태로 옮긴다.
REFUSED, STOPPED = "refused", "stopped"
#: 자동 모드의 `--sheets` 값(B91 ②) — 역할 문법에는 `:`가 있어야 하므로 겹치지 않는다.
AUTO = "auto"
#: 명령줄 선택 — LLM 제안 끄기(`--no-sheet-llm` · 손잡이가 아니라 플래그 · B91 ②).
_OPTS = {"llm": True}


def judge(rows, llm=True):
    """두 제안을 행에 단다 — `logic`(모양만) · `llm`(+ `llm_reason` — 표본 줄만) — 그리고 기본
    제안 `suggest`: 둘이 같으면 그것 · LLM이 없으면 로직 · **어긋나면 `ref`**(모르면 ref).

    돌려주는 것은 LLM 갈래 — `live` · `mock`(로직과 같은 답 · 호출 0 · 결정적) · `off`.
    빈 시트(`skip`)는 부르지 않는다.
    """
    fn, by = None, "off"
    if llm:
        from core.llm import points
        fn = points.sheet_judge()
        by = "live" if fn else "mock"
    for r in rows:
        r["logic"] = r.get("logic") or r["suggest"]
        r["llm"], r["llm_reason"] = None, None
        if by == "off":
            pass
        elif r.get("state", "visible") != "visible":
            r["llm"], r["llm_reason"] = "skip", "숨김 시트 — 부르지 않았다(살리려면 --sheets <번호>:read)"
        elif r["logic"] == "skip":
            r["llm"], r["llm_reason"] = "skip", "빈 시트 — 부르지 않았다"
        elif fn is None:
            r["llm"], r["llm_reason"] = r["logic"], "mock — 로직과 같은 답(호출 0)"
        else:
            out = fn(r["name"], r.get("sample") or [])
            r["llm"], r["llm_reason"] = form_mod.role_of(out["role"]), out["reason"]
        r["suggest"] = r["logic"] if r["llm"] in (None, r["logic"]) else "ref"
    return by


def judged(rows, by, promote=None):
    """기록에 싣는 두 제안(`sheets.write(judged=)`) — 로직 · LLM · 이유 · LLM 갈래 · 승격 후보."""
    return {"logic": {r["name"]: r["logic"] for r in rows},
            "llm": ({r["name"]: r["llm"] for r in rows} if by != "off" else None),
            "llm_reason": ({r["name"]: r["llm_reason"] for r in rows if r.get("llm_reason")}
                           if by == "live" else None),
            "llm_by": by, "promote": promote}


def _live(rows, visible=True):
    """비어 있지 않은 시트 — 관문을 띄우는 셈은 숨김도 센다(B214 ① — 형태와 상관없이 둘 이상이면 묻는다 · 숨김을 살리는 자리 B112 ②) ·
    읽음 제안은 보이는 시트만."""
    return [r for r in rows if r.get("values") and (not visible or r.get("state", "visible") == "visible")]


def _named(adapter):
    """어댑터의 `expects.sheet`(표 시트 이름) 또는 None."""
    from cli import scan as scan_mod
    try:
        return (scan_mod._load(Path(adapter)).ADAPTER.get("expects") or {}).get("sheet")
    except Exception:                            # noqa: BLE001 — 못 읽으면 이름이 없는 것으로(관문이 묻는다)
        return None


def suggest_read(doc, rows, kind, adapters=()):
    """**읽음 제안**(B214 ③) — 등록된 doc_type이면 그 어댑터(변형 포함) 헤더 지문과 맞는 시트 → `read` · 아니면 글 규칙으로
    `read`가 하나도 없을 때 형태가 table인 시트 중 값이 가장 많은 것 → `read`(산문 통합문서의 제안은 그대로) · 산문 계열은 손대지 않는다."""
    if kind == form_mod.PROSE or not rows:
        return rows
    raw = reader_mod.read(str(doc))
    if adapters:
        from cli import scan as scan_mod
        mods = [scan_mod._load(Path(a)) for a in adapters]
        hit = {sh.get("name") for sh in raw.get("sheets") or [] for m in mods
               if scan_mod.match_detail({**raw, "sheets": [sh]}, m).get("candidate")}
        pick = [r for r in _live(rows) if r["name"] in hit]
    elif any(r["suggest"] == "read" for r in rows):
        pick = []
    else:
        per = form_mod.judge_sheets(raw)
        pick = sorted((r for r in _live(rows) if per.get(r["name"]) == form_mod.TABLE), key=lambda r: -r["values"])[:1]
    for r in pick:
        r["suggest"] = "read"
    return rows


def one_form(doc, roles, kind, flag_cmd=None):
    """**한 doc_type은 한 형태다**(B214 ①) — 읽음 시트가 표 + 글로 섞이거나 표 계열인데 둘 이상이면 멈춤 dict · 아니면 None.
    형태는 등록 · 초안 스키마가 있으면 그것(판정 0) · 없으면 읽음 시트만 판정한다."""
    reads = [n for n, r in (roles or {}).items() if r == "read"]
    if kind == form_mod.PROSE or len(reads) < 2:
        return None
    per = {} if kind else form_mod.judge_sheets(reader_mod.read(str(doc)))
    tab = [n for n in reads if kind == form_mod.TABLE or per.get(n) == form_mod.TABLE]
    txt = [n for n in reads if not kind and per.get(n) == form_mod.PROSE]
    if tab and txt:
        why = f"한 doc_type은 한 형태다 — 읽음 시트 {' · '.join(tab)}는 표 · {' · '.join(txt)}는 글 · 하나를 ref로"
    elif len(tab) > 1:
        why = f"표 계열은 읽음 시트가 하나다(어댑터는 한 시트를 읽는다) — 읽음 시트 {' · '.join(tab)}는 표 · 하나만 read로"
    else:
        return None
    nxt = (flag_cmd or '<명령> --sheets "{sheets}"').replace("{sheets}", "<번호>:read *:ref")
    print(f"   [상태] {why}\n  ▶ 다음 줄: {nxt}")
    return {"kind": REFUSED, "reason": why}


def rows_of(doc):
    """시트 표의 재료 — **읽기 실패는 조용하다**(같은 이유로 파싱이 곧 실패한다).

    표는 `reader`가 이미 내는 값의 투영이다(새 판독 0). 통합문서를 여는 일은 형태
    판정과 겹치지만 **판정의 산출에 시트별 통계가 없다** — 값을 기록에 실어 나르면
    근거와 화면이 갈린다(신호 다섯과 같은 병). 선택 의존 부재는 조용하지 않다 —
    호출자까지 올라가 상태 거부가 된다(B86 ④).
    """
    if Path(doc).suffix.lower() not in GRID_EXT:
        return []
    try:
        return form_mod.sheet_table(reader_mod.read(str(doc)))
    except reader_mod.MissingDependency:
        raise
    except Exception as e:                       # noqa: BLE001
        _LOG.info("시트 표를 만들지 못했다 — %s (%s: %s)", doc, type(e).__name__, e)
        return []


def flag(args):
    """`--sheets "<문법>"`를 args에서 떼어 `(남은 args, 문자열 또는 None)`.

    `--coord-llm`과 같은 결이다 — 떼어내지 않으면 문자열이 경로 자리로 흘러간다.
    """
    args = list(args)
    if "--no-sheet-llm" in args:                 # LLM 제안 끄기 — 로직 제안만 본다
        args.remove("--no-sheet-llm")
        _OPTS["llm"] = False
    if "--sheets" not in args:
        return args, None
    i = args.index("--sheets")
    spec = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    if not spec or spec.startswith("--"):
        raise SystemExit('[투입] --sheets 뒤에 역할 문자열 또는 auto가 필요하다 — '  # [사용법]
                         '예: --sheets "2-3:read 4:ref *:ref" · --sheets auto')
    return args, spec


def _usage0():
    from core.llm import gateway
    return gateway.usage_total()


def _usage_end(u0):
    """시트 역할 관문 끝의 사용량 한 줄(B96 ③ — 문구는 `_screen.usage_line` 하나)."""
    from cli import _screen
    print(f"   {_screen.usage_line(u0)}")


def auto(doc, doc_id, *, dry_run=False, kind=None, adapters=()):
    """**자동 모드**(`--sheets auto` · B91 ②) — 로직과 LLM이 **합의하면 그 역할**, 어긋나면
    `ref` + 「승격 후보」(화면과 기록). 기록이 있고 미결이 없으면 기록대로다(다시 부르지 않는다).

    합의가 조건이라 LLM을 끄면(`--no-sheet-llm`) 자동 모드가 성립하지 않는다 — `[사용법]`.
    """
    from core.state import sheets as SH
    if not _OPTS["llm"]:
        raise SystemExit("[투입] --sheets auto는 로직과 LLM의 **합의**다 — "          # [사용법]
                         "--no-sheet-llm과 함께 줄 수 없다(사람 지정 모드는 --sheets 없이)")
    rec = SH.read(doc_id)
    rows = rows_of(doc)
    names = [r["name"] for r in rows]
    if rec and not SH.pending(rec.get("sheets") or {}, names):
        judge(rows, False)                 # 기록대로 — 표는 보이고 묻지 않는다(LLM 0 · B112 ②)
        print(SCR.sheet_table_block(rows, file=doc, rec=rec, pend=[]))
        print(f"   시트 역할 — 기록대로 진행({SH.summary(rec['sheets'])} · {rec.get('decided_by')})")
        print(SCR.sheet_again_line(doc, rows))
        return dict(rec["sheets"])
    rows = suggest_read(doc, rows, kind, adapters)
    _u0 = _usage0()
    by = judge(rows, True)
    roles = {r["name"]: (r["logic"] if r["llm"] == r["logic"] else "ref") for r in rows}
    promote = [r["name"] for r in rows if r["llm"] != r["logic"]]
    print(SCR.sheet_table_block(rows, file=doc, rec=rec, pend=None))
    print(SCR.sheet_auto_line(roles, promote, by))
    if not dry_run:
        SH.write(doc_id, Path(doc).name, roles, "auto", judged=judged(rows, by, promote))
        print(SCR.sheet_roles_line(roles, doc_id))
    _usage_end(_u0)
    return roles


def by_flag(doc, doc_id, spec, *, names=None, dry_run=False, kind=None, adapters=()):
    """`--sheets`로 받은 역할 — 관문을 건너뛰고 **같은 기록**을 쓴다(`decided_by: flag`).

    문법의 자리는 `form.parse_sheet_spec` 하나이고 기록의 자리는
    `core/state/sheets.py` 하나다. 미정 시트가 남으면 `[사용법]`이다(조용한 기본값 0).
    `auto`면 자동 모드다(`auto()`).
    """
    from core.state import sheets as SH
    if spec == AUTO:
        return auto(doc, doc_id, dry_run=dry_run, kind=kind, adapters=adapters)
    names = list(names or [r["name"] for r in rows_of(doc)])
    got, err = form_mod.parse_sheet_spec(spec, names)
    if err:
        raise SystemExit(f"[투입] --sheets {err}\n"                           # [사용법]
                         f'  예: --sheets "2-3:read 4:ref *:ref" · --sheets auto')
    left = SH.pending(got, names)
    if left:
        raise SystemExit(f"[투입] --sheets에 역할이 없는 시트가 남았다 — "       # [사용법]
                         f"{' · '.join(left)}\n"
                         f'  나머지를 한 번에: --sheets "{spec} *:ref"')
    if not dry_run:
        SH.write(doc_id, Path(doc).name, got, "flag")
        print(SCR.sheet_roles_line(got, doc_id))
    return got


def gate(doc, doc_id, kind, *, spec=None, dry_run=False, ask=True, retry=None,
         flag_cmd=None, adapters=()):
    """`(roles, 멈춤)` — 관문 한 벌(`_gate`) 뒤에 읽음 시트의 형태를 본다(B214 ① — 한 doc_type은 한 형태)."""
    roles, stop = _gate(doc, doc_id, kind, spec=spec, dry_run=dry_run, ask=ask, retry=retry, flag_cmd=flag_cmd,
                        adapters=adapters)
    stop = stop or (one_form(doc, roles, kind, flag_cmd) if roles else None)
    return (None, stop) if stop else (roles, None)


def _gate(doc, doc_id, kind, *, spec=None, dry_run=False, ask=True, retry=None,
          flag_cmd=None, adapters=()):
    """역할을 정해 돌려준다 — `(roles 또는 None, 멈춤 또는 None)`.

    조건(B214 ①): 격자 포맷 · 비어 있지 않은 보이는 시트 ≥ 2 · 기록 없음(또는 미결 시트 있음) — **형태와 상관없다** ·
    표 계열이고 어댑터의 `expects.sheet` 시트가 문서에 있으면 묻지 않는다(④). 하나라도 아니면 `(None, None)`으로
    지나간다. 멈춤은 `{"kind": REFUSED|STOPPED, "reason": …}`이다. `kind`가 None이면 형태는 읽음 시트에서 잰다.

    `retry`·`flag_cmd`는 **거부 문면의 다음 줄**이다(호출자가 무엇을 다시 치면 되는지
    안다) — `flag_cmd`는 `{sheets}` 자리에 제안 문자열이 들어간다.
    """
    from core.state import sheets as SH
    rows = rows_of(doc)
    names = [r["name"] for r in rows]
    if len(_live(rows, visible=False)) < 2 or (kind == form_mod.TABLE and adapters and _named(adapters[0]) in names):
        return None, None
    rec = SH.read(doc_id)
    roles = dict((rec or {}).get("sheets") or {})
    for n in SH.stale(roles, names):
        _LOG.info("시트 역할 기록에 있으나 문서에 없다 — %s · %s (무시)", doc_id, n)
    if spec:
        return by_flag(doc, doc_id, spec, names=names, dry_run=dry_run, kind=kind, adapters=adapters), None
    pend = SH.pending(roles, names)
    if rec and not pend:
        judge(rows, False)                       # 기록대로 — 표는 보이고 묻지 않는다(LLM 0 · B112 ②)
        print(SCR.sheet_table_block(rows, file=doc, rec=rec, pend=[]))
        print(f"   시트 역할 — 기록대로 진행({SH.summary(roles)} · "
              f"{rec.get('decided_by')})")
        print(SCR.sheet_again_line(doc, rows, flag_cmd))
        return roles, None
    # 두 제안(B91 ②) — 로직(모양만)은 늘 · LLM은 **물을 때만** 부른다(보여만 주는
    # dry-run과 거부 문면은 실호출 0 — mock 갈래는 호출이 없어 그대로 보인다).
    rows = suggest_read(doc, rows_of(doc), kind, adapters)
    asking = not dry_run and ask and sys.stdin.isatty()
    from core.llm import gateway
    _u0 = _usage0()
    by = judge(rows, _OPTS["llm"] and (asking or gateway.use_mock()))
    if dry_run:                          # 보여만 준다 — 묻지 않고 기록도 쓰지 않는다
        print(SCR.sheet_table_block(rows, file=doc, rec=rec, pend=pend))
        _usage_end(_u0)
        return None, None
    if not asking:
        # **상태 거부**다 — 조용한 기본값 없이 멈추고, 문면이 다음 줄을 싣는다.
        print(SCR.sheets_refusal(doc, rows, pend=pend if rec else None, rec=rec,
                                 retry=retry, flag_cmd=flag_cmd))
        _usage_end(_u0)
        return None, {"kind": REFUSED,
                      "reason": f"시트 역할 미정 — 시트 {len(rows)}장 "
                                f"(--sheets 또는 터미널에서 관문)"}
    got = SCR.sheet_gate(rows, file=doc, doc_id=doc_id, rec=rec)
    _usage_end(_u0)
    if got is None:
        return None, {"kind": STOPPED, "reason": "사람이 멈췄다 — 시트 역할 관문"}
    SH.write(doc_id, Path(doc).name, got, "gate", judged=judged(rows, by))
    print(SCR.sheet_roles_line(got, doc_id))
    return got, None
