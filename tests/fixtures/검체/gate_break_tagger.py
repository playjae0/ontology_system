# -*- coding: utf-8 -*-
"""**깨지는 검체** — extract는 멀쩡하고 tagger에서 깨진다 (B58 ② 완료판정 ⓑ).

관문이 `extract`까지만 보던 구판에서 **이 어댑터는 PASS로 통과했다.** 조각이 나오고,
`source_locator`가 유일하고, 스키마 밖 필드도 없다 — ①~④가 볼 수 있는 것은 거기까지다.
깨지는 자리는 그 **다음**이다: `process_ref`에 문자열 대신 리스트를 실어, 좌표 태깅이
닫힌 목록과 대조하는 순간 `TypeError: unhashable type: 'list'`가 난다.

실제로 흔한 결함이다 — 복수값 셀(`노칭, 코팅`)을 전개하지 않고 통째로 담으면 이 모양이
된다. 구판에서 이것을 처음 만나는 자리가 **사람의 검수 화면**이었고, 사내는 거기서
「unhashable type」을 자연어로 통역해 되돌려야 했다(C27: 사내는 코딩하지 않는다).

**정상 어댑터가 아니다** — few-shot에도 참조 전시장에도 넣지 않는다.

**자리가 `tests/fixtures/검체/`인 이유**: `tests/fixtures/adapters/`는 **지문 스캔의
소재지**다(`cli/scan.py ADAPTER_DIRS`). 지문이 `cp`와 같으니 거기 두면 CP 문서의
후보가 둘이 되어 「유일 일치만 자동으로 간다」(B46 조건 ③)가 깨진다 — 실측으로
`test_g6` 8건이 붉었다. 깨지라고 만든 검체가 **다른 것을 깨는 자리**에 있으면 안 된다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_CP = Path(__file__).resolve().parent.parent / "adapters" / "cp.py"
_spec = importlib.util.spec_from_file_location("_gate_break_base", _CP)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

# **지문은 cp 그대로다** — preflight(②)를 통과해야 ⑤까지 닿는다. 깨지는 자리를
# 앞단이 가로막으면 「⑤가 잡는다」를 보일 수 없다.
ADAPTER = {**_base.ADAPTER, "doc_type": "gate_break_tagger"}


def extract(raw, struct_map_fn=None) -> list[dict]:
    """cp 어댑터의 산출을 그대로 받아 **`process_ref`만 리스트로 만든다.**"""
    out = []
    for p in _base.extract(raw):
        p = dict(p)
        if p.get("process_ref") is not None:
            p["process_ref"] = [p["process_ref"]]     # ← 여기가 결함이다
        out.append(p)
    return out
