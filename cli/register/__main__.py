# -*- coding: utf-8 -*-
"""칸 1.1~1.8 **진입점** — `python -m cli.register <명령>` (이름 불변).

사용법 문면의 정본은 **패키지 머리말**(`cli/register/__init__.py`)이다 — 명령 표면을
한 자리에서 읽게 한다. 여기서는 그것을 화면으로 옮기기만 한다.
"""

from __future__ import annotations

import cli.register as _pkg

from cli._gate import require_live_or_allow
from core.state import fixtures, log, registry, store
import json
import sys
from cli.register import confirm
from cli.register import draft as draft_mod
from cli.register import generate
from cli.register import view
from cli.register import _save_state, _state


def main(argv):
    """진입점 — **미포착 예외는 문면으로 죽는다** (B76 ③).

    관문 FAIL·상태 거부(`SystemExit`)는 **판정**이라 그대로 지난다. 여기서 잡는
    것은 파이썬 예외뿐이고, 화면에는 한 줄(`[결함] 파일:줄 · 예외: 메시지 · 단계 …`)
    · `defects.log`에는 traceback 전문이다. 사내 실측 열다섯째의 화면은 traceback
    이었고 사람이 프레임을 읽어야 했다 — 그것이 M9 위반이다.
    """
    from parser.reader import MissingDependency
    from cli._gate import require_knobs
    require_knobs()                 # 손잡이 파일이 어긋나면 먼저 문면으로 (B91 ⑤)
    try:
        return _run(argv)
    except SystemExit:
        raise                       # 관문 FAIL·상태 거부는 판정이다 — 그대로
    except MissingDependency:
        raise                       # 선택 의존 부재는 **상태**다 — `cli` 훅이 설치 줄로 낸다 (B86 ④)
    except Exception as e:
        print(log.defect(e, stage=f"단계 {argv[0] if argv else '?'}",
                         extra=(f"doc_type {argv[1]}" if len(argv) > 1 else "")))
        return 1                    # 상태 거부와 같은 종료 코드 (B61 계약)


def _lens_arg(v):
    return "all" if v.strip() == "all" else [x.strip() for x in v.split(",") if x.strip()]


def _cmd_lenses(rest):
    """`register lenses <dt> [<층,층>|all]` — 렌즈를 보거나 바꾼다 (B91 ① · 등록부 원자 쓰기)."""
    from core.state import registry
    if not rest:
        raise SystemExit("[사용법] python -m cli.register lenses <doc_type> [<층,층> | all]")  # [사용법]
    dt = rest[0]
    if not registry.lookup(dt):
        raise SystemExit(f"[상태] '{dt}'은 등록돼 있지 않다 — 근거 registry/doc_types.json\n"  # [상태]
                         f"  ▶ 다음 줄: python -m cli.register list")
    if len(rest) > 1:
        try:
            registry.set_lenses(dt, _lens_arg(rest[1]))
        except ValueError as e:
            raise SystemExit(f"[사용법] {e}")                                  # [사용법]
    e = registry.lookup(dt)
    print(f"■ 렌즈 — {dt}: {registry.lenses_of(dt)}"
          + (" (all — 층 전부 · 비용 장치가 붙는다)" if e.get("lenses") == "all" else "")
          + ("" if e.get("lenses") else " (기본 — 등록 층 하나)"))
    return 0


def _run(argv):
    if not argv:
        raise SystemExit(_pkg.__doc__)                                    # [사용법]
    cmd, rest = argv[0], list(argv[1:])
    if cmd in confirm.GATED:
        rest = require_live_or_allow(rest, command=f"register {cmd}")

    def opt(name, default=None):
        if name in rest:
            i = rest.index(name)
            v = rest[i + 1] if i + 1 < len(rest) else default
            del rest[i:i + 2]
            return v
        return default

    if cmd == "roles":
        # **⓪ 등록 세션 진입 전** — 실행만 하고 등록부는 건드리지 않는다.
        return generate.cmd_roles(rest)
    if cmd == "generate":
        hint = opt("--hint", "")
        interview = "--interview" in rest
        if interview:
            rest.remove("--interview")
        no_few = "--no-fewshot" in rest
        if no_few:
            rest.remove("--no-fewshot")
        resume = "--resume" in rest
        if resume:
            rest.remove("--resume")
        no_basic = "--no-basic" in rest
        if no_basic:
            rest.remove("--no-basic")
        use_basic = "--use-basic" in rest
        if use_basic:
            rest.remove("--use-basic")
        # **사람의 답을 버리려면 적어야 한다**(B55 ②-4) — 기본은 이어가기다.
        drop_iv = "--drop-interview" in rest
        if drop_iv:
            rest.remove("--drop-interview")
        # **재등록 두 경로**(H27 · B58 ①)
        revise = "--revise" in rest
        if revise:
            rest.remove("--revise")
        as_name = opt("--as", None)
        # **렌즈**(B91 ①) — prose 추출이 보는 층 목록(`a,b` 또는 `all`) · 없으면 등록 층 하나
        lenses = opt("--lenses", None)
        # **표본의 시트 역할**(B86 ⑤) — 인입과 같은 문법 · 표본이 하나일 때만.
        from cli import sheet_gate as SG
        rest, sheets = SG.flag(rest)
        # **위치 인자가 모자라면 죽지 말고 사용법을 낸다.** `--resume`은 doc_type
        # 하나만 필요하다 — 층·표본은 패키지에 이미 있고 resume 갈래가 그것을
        # 읽는다(실사고: `generate <doc_type> --resume`이 IndexError로 죽었다).
        if not rest or (not resume and len(rest) < 2):
            raise SystemExit(_pkg.__doc__)                                # [사용법]
        _rv = generate.cmd_generate(rest[0], rest[1] if len(rest) > 1 else None, rest[2:],
                            hint, interview=interview,
                            no_fewshot=no_few, resume=resume, use_basic=use_basic,
                            drop_interview=drop_iv, revise=revise, as_name=as_name,
                            no_basic=no_basic, sheets=sheets)
        if lenses:
            _dt = as_name or rest[0]
            _st = _state(_dt)
            if _st:                          # 확정이 등록부로 옮긴다 (confirm)
                _st["lenses"] = _lens_arg(lenses)
                _save_state(_dt, _st)
                print(f"   렌즈 — {_st['lenses']} (확정 때 등록부에 실린다)")
        return _rv
    if cmd == "lenses":
        return _cmd_lenses(rest)
    if cmd == "review":
        # **prose의 리허설 기본은 전량이다**(B51) — 부분 리허설의 근거(좌표 미스
        # 비용)는 table의 것이고 prose엔 해당 없다. table 기본 200행은 그대로다.
        _st0 = _state(rest[0]) if rest else None
        _prose = bool(_st0) and str(_st0.get("schema", "")).endswith(".json") and (
            (json.loads((draft_mod._at(_st0["schema"])).read_text(encoding="utf-8"))
             .get("payload_kind") == "prose") if (draft_mod._at(_st0["schema"])).exists() else False)
        raw_rows = opt("--rows", "all" if _prose else str(view.REHEARSAL_ROWS))
        if str(raw_rows).lower() == "all":
            rows = None                      # 전량 — 자르지 않는다
        else:
            try:
                rows = int(raw_rows)
            except (TypeError, ValueError):
                raise SystemExit(f"[뷰 확인] --rows 는 정수 또는 all 이다: {raw_rows!r}")  # [사용법]
        # 좌표 LLM 보조는 **기본이 「묻는다」**이고, 스크립트용으로만 미리 정한다.
        coord = True if "--llm-coord" in rest else (
            False if "--no-llm-coord" in rest else None)
        for f in ("--llm-coord", "--no-llm-coord"):
            if f in rest:
                rest.remove(f)
        # 추출 리허설도 **기본은 「묻는다」**이고 스크립트용으로만 미리 정한다.
        ex = True if "--extract" in rest else (
            False if "--no-extract" in rest else None)
        for f in ("--extract", "--no-extract"):
            if f in rest:
                rest.remove(f)
        return view.cmd_review(rest[0], opt("--instruct"), rows=rows, llm_coord=coord,
                          extract=ex)
    if cmd == "confirm":
        return confirm.cmd_confirm(rest[0], opt("--by"))
    if cmd == "status":
        return view.cmd_status(rest[0])
    if cmd == "list":
        return confirm.cmd_list()
    raise SystemExit(f"알 수 없는 명령: {cmd}\n{_pkg.__doc__}")                      # [사용법]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
