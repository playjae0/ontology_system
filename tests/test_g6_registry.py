# -*- coding: utf-8 -*-
"""G6 ④ 등록부 — 내장은 mock일 때만 · 등록부 결손은 상태 거부(B70)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ B70 ①② — 내장은 mock일 때만 · 등록부 결손은 상태 거부")

from core.llm import gateway as _L70                                       # noqa: E402
from core.state import registry as _RG                                   # noqa: E402

_um70 = _L70.use_mock
_reg70 = dict(store.read(store.DOC_TYPES, {}))


def _live70(on):
    """`use_mock()`만 뒤집는다 — 실호출은 하지 않는다(설정도 건드리지 않는다)."""
    _L70.use_mock = (lambda: not on)


try:
    _live70(True)                                   # USE_MOCK=0 세계
    show("① USE_MOCK=0이면 doc_type은 **등록부가 전부**다 (내장 mock 자산 제외)",
         set(_RG.all_doc_types()) == set(_reg70),
         f"조회 {sorted(_RG.all_doc_types())} · 등록부 {sorted(_reg70)}")
    show("① USE_MOCK=0이면 스캔의 대조 목록도 등록부뿐이다 (기본 소재지 제외)",
         {str(f) for f, _m in SC.adapters()}
         == {str(_P.registry(e["adapter"])) for e in _reg70.values() if e.get("adapter")},
         str(sorted(Path(f).name for f, _m in SC.adapters()))[:80])
    show("① 사람이 준 경로는 그대로 쓴다 — 명시는 의도다",
         [f.name for f, _m in SC.adapters(
             [str(ROOT / "tests/fixtures/adapters/cp.py")])] == ["cp.py"])
    _live70(False)                                  # USE_MOCK=1 — 지금과 같다
    show("① USE_MOCK=1은 지금 그대로다 (내장 + 기본 소재지 · 회귀가 이 세계에서 돈다)",
         {"cp", "pfmea"} <= set(_RG.all_doc_types())
         and any(f.name == "cp.py" for f, _m in SC.adapters()))

    # ② **결손은 빼지 않고 막는다** — 빼면 지금과 같은 「조용한 화면」이다.
    _ad70 = _P.adapters() / "b70x.py"
    _sc70 = _P.schemas() / "b70x.json"
    # **등재가 먼저다** — `schemas/b70x.json`이 먼저 있으면 그 파일의 실재가 곧
    # 내장 등록이라 `register`가 이름 중복으로 막는다(그 규칙은 그대로 옳다).
    _RG.register("b70x", layer="process", adapter="adapters/b70x.py",
                 schema="schemas/b70x.json", adapter_version="1.0",
                 approved_by="홍길동", approved_at="2026-09-15T00:00:00+00:00")
    _ad70.parent.mkdir(exist_ok=True)
    _ad70.write_text("ADAPTER = {}\n", encoding="utf-8")
    _sc70.write_text(json.dumps({"doc_type": "b70x"}, ensure_ascii=False),
                     encoding="utf-8")
    show("② 실물이 있으면 결손 0이다 (시험의 전제)", not _RG.missing_assets())
    _ad70.unlink()                                  # 이식에서 빠진 그 상태
    _miss70 = _RG.missing_assets()
    show("② 등록부가 가리키는 실물이 없으면 결손으로 잡힌다 (조회처는 하나다)",
         [(m["doc_type"], m["kind"]) for m in _miss70] == [("b70x", "adapter")],
         str(_miss70))
    try:
        SC.adapters()
        _rc70 = ""
    except SystemExit as e:
        _rc70 = str(e)
    show("② scan·인입 진입이 **상태 거부**다 — 이름과 다음 줄이 문면에 있다",
         "b70x" in _rc70 and "adapters/b70x.py" in _rc70
         and "python -m cli.register generate b70x" in _rc70,
         _rc70.splitlines()[0] if _rc70 else "거부 없음")
    show("② 승인자·등록 시점을 함께 말한다 (누가 언제 등록한 것이 비었나)",
         "홍길동" in _rc70 and "2026-09-15" in _rc70)
    _b70 = _io.StringIO()
    with _ctx.redirect_stdout(_b70):
        PF.cmd_doctypes()
    show("② platform doctypes가 실물 유무를 표시한다 (✗가 화면에 뜬다)",
         "adapter ✗" in _b70.getvalue() and "실물 없는 등록" in _b70.getvalue(),
         [l.strip() for l in _b70.getvalue().splitlines() if "b70x" in l][:1])
finally:
    _L70.use_mock = _um70
    _RG.unregister("b70x")
    for _p70 in (_P.adapters() / "b70x.py", _P.schemas() / "b70x.json"):
        _p70.unlink(missing_ok=True)
show("② 뒷정리 — 결손 0 · 등록부 원상 (회귀가 남기는 것 0)",
     not _RG.missing_assets() and set(store.read(store.DOC_TYPES, {})) == set(_reg70))

# ── B72 ②③④ — 인입 화면: 예고 · 큐는 사실 단위 · 다음 줄 · 단계 ──────────
#
# 사내 첫 실인입에서 드러난 것 넷: ①「스키마에 없는 필드 'meta'」가 **행마다**
# ②골격 밖 좌표가 몇 개인지·드랍인지·어떻게 잇는지 화면이 말하지 않았다
# ③「선택만」의 뜻이 없었다 ④2만 토큰을 쓰고 나서야 비용을 알았다.

done()
