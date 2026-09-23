# -*- coding: utf-8 -*-
"""칸 3.1 · 1.6 — **시트 역할 관문 한 벌**: 인입 · `parse run` · 등록 표본이 같은 함수를 부른다 (B83 ③ · B86 ⑤).

시트 여럿인 prose 엑셀은 문서마다 시트의 역할이 다르다 — 사람이 **문서마다 한 번**
정하고(`prose`·`ref`·`skip`), 답은 `registry/sheet_roles/<doc_id>.json`에 남는다.

`cli/ingest.py`에서 떼어냈다(B86 ⑤): 등록 표본에도 같은 관문을 걸어야 했고(B83 누락 —
등록 리허설·킷 관문이 시트 전부를 돌았다), 그 파일이 775행이었다(§7 상한 800).
**관문 함수는 `gate()` 하나다** — 호출자가 셋이어도 묻는 말·기록·거부 문면이 갈리지
않는다. 호출자가 다른 것은 두 가지뿐이다: 갈래(`kind`)를 어디서 아는가(인입은 등록부,
등록은 초안 스키마)와 거부 문면의 다음 줄(무엇을 다시 치면 되나).
"""
from __future__ import annotations

import sys
from pathlib import Path

from cli import ingest_screen as SCR
from core.state import log
from parser import form as form_mod, reader as reader_mod
from parser.reader import GRID_EXT

_LOG = log.get("cli.sheet_gate")

#: 관문이 멈춘 두 모양 — 호출자가 제 화면의 상태로 옮긴다.
REFUSED, STOPPED = "refused", "stopped"


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
    if "--sheets" not in args:
        return args, None
    i = args.index("--sheets")
    spec = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
    if not spec or spec.startswith("--"):
        raise SystemExit('[투입] --sheets 뒤에 역할 문자열이 필요하다 — '        # [사용법]
                         '예: --sheets "2-3:prose 4:ref *:skip"')
    return args, spec


def by_flag(doc, doc_id, spec, *, names=None, dry_run=False):
    """`--sheets`로 받은 역할 — 관문을 건너뛰고 **같은 기록**을 쓴다(`decided_by: flag`).

    문법의 자리는 `form.parse_sheet_spec` 하나이고 기록의 자리는
    `core/state/sheets.py` 하나다. 미정 시트가 남으면 `[사용법]`이다(조용한 기본값 0).
    """
    from core.state import sheets as SH
    names = list(names or [r["name"] for r in rows_of(doc)])
    got, err = form_mod.parse_sheet_spec(spec, names)
    if err:
        raise SystemExit(f"[투입] --sheets {err}\n"                           # [사용법]
                         f'  예: --sheets "2-3:prose 4:ref *:skip"')
    left = SH.pending(got, names)
    if left:
        raise SystemExit(f"[투입] --sheets에 역할이 없는 시트가 남았다 — "       # [사용법]
                         f"{' · '.join(left)}\n"
                         f'  나머지를 한 번에: --sheets "{spec} *:skip"')
    if not dry_run:
        SH.write(doc_id, Path(doc).name, got, "flag")
        print(SCR.sheet_roles_line(got, doc_id))
    return got


def gate(doc, doc_id, kind, *, spec=None, dry_run=False, ask=True, retry=None,
         flag_cmd=None):
    """역할을 정해 돌려준다 — `(roles 또는 None, 멈춤 또는 None)`.

    조건 넷(B83 ③): 격자 포맷 · **prose로 읽히는 갈래**(`kind`) · 시트 ≥ 2 · 기록 없음
    (또는 미결 시트 있음). 하나라도 아니면 `(None, None)`으로 지나간다 — 시트 하나면
    표도 질문도 없다. 멈춤은 `{"kind": REFUSED|STOPPED, "reason": …}`이다.

    `retry`·`flag_cmd`는 **거부 문면의 다음 줄**이다(호출자가 무엇을 다시 치면 되는지
    안다) — `flag_cmd`는 `{sheets}` 자리에 제안 문자열이 들어간다.
    """
    from core.state import sheets as SH
    if kind != "prose":
        return None, None
    rows = rows_of(doc)
    if len(rows) < 2:
        return None, None
    names = [r["name"] for r in rows]
    rec = SH.read(doc_id)
    roles = dict((rec or {}).get("sheets") or {})
    for n in SH.stale(roles, names):
        _LOG.info("시트 역할 기록에 있으나 문서에 없다 — %s · %s (무시)", doc_id, n)
    if spec:
        return by_flag(doc, doc_id, spec, names=names, dry_run=dry_run), None
    pend = SH.pending(roles, names)
    if rec and not pend:
        print(f"   시트 역할 — 기록대로 진행({SH.summary(roles)} · "
              f"{rec.get('decided_by')})")
        return roles, None
    if dry_run:                          # 보여만 준다 — 묻지 않고 기록도 쓰지 않는다
        print(SCR.sheet_table_block(rows, file=doc, rec=rec, pend=pend))
        return None, None
    if not (ask and sys.stdin.isatty()):
        # **상태 거부**다 — 조용한 기본값 없이 멈추고, 문면이 다음 줄을 싣는다.
        print(SCR.sheets_refusal(doc, rows, pend=pend if rec else None, rec=rec,
                                 retry=retry, flag_cmd=flag_cmd))
        return None, {"kind": REFUSED,
                      "reason": f"시트 역할 미정 — 시트 {len(rows)}장 "
                                f"(--sheets 또는 터미널에서 관문)"}
    got = SCR.sheet_gate(rows, file=doc, doc_id=doc_id, rec=rec)
    if got is None:
        return None, {"kind": STOPPED, "reason": "사람이 멈췄다 — 시트 역할 관문"}
    SH.write(doc_id, Path(doc).name, got, "gate")
    print(SCR.sheet_roles_line(got, doc_id))
    return got, None
