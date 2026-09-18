# -*- coding: utf-8 -*-
"""P1 공용 재료 — 파서 공용 코어 스위트 다섯이 **같은 바닥**에서 돈다 (B78 2c).

헬퍼·픽스처 어댑터 로드가 파일마다 복제되면 그중 하나만 고쳐지는 날이 오고,
그날 두 스위트가 다른 바닥 위에서 판정한다.

    from p1_common import *
    ...
    done()
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.state import init, store                                        # noqa: E402
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.state.bootstrap import bootstrap                          # noqa: E402
from parser import (normalizer, pipeline, preflight, reader, struct_map, tagger,  # noqa: E402
                    validator)
from parser.adapters import basic_ppt                         # noqa: E402
from parser.reader import read                                # noqa: E402

allok = True
RAW = ROOT / "tests" / "fixtures" / "raw"
SKIP = {"parsed_at", "source_path", "parser_version", "adapter_version",
        "process_no", "source_locator"}


def show(label, ok, detail=""):
    global allok
    allok &= bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)

def _reg_src():
    """등록 파트의 소스 전량 — **파트가 파일 여럿이다**(B78 2b). 성질은 「등록 코드가
    그렇게 한다」이지 「어느 파일에 있다」가 아니므로, 파트를 통째로 읽는다."""
    return " ".join(_p.read_text(encoding="utf-8")
                    for _p in sorted((ROOT / "cli" / "register").glob("*.py")))


def load_adapter(path, name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = load_adapter("tests/fixtures/adapters/cp.py", "ad_cp")
PFMEA = load_adapter("tests/fixtures/adapters/pfmea.py", "ad_pfmea")
TOC = load_adapter("tests/fixtures/fixtures/adapters/toc_report.py", "ad_toc")
IPQC = load_adapter("tests/fixtures/fixtures/adapters/ipqc.py", "ad_ipqc")



# ── 구조 지도 시험 재료 — 두 스위트(core6·coord)가 같은 것을 쓴다(B78 2c)
def map_lines():
    """지도 시험의 입력 — **부르는 쪽이 새로 받는다.** 모듈 전역으로 두면 앞선
    블록이 같은 이름을 다시 묶는 날 뒤 블록이 남의 행을 본다(실측)."""
    rows = [(r, f"{r}행 본문") for r in range(2, 20)]
    for r, txt in ((2, "1. 첫 장"), (4, "1.1 절"), (7, "1.2 절"), (10, "2. 둘째 장")):
        rows[r - 2] = (r, txt)
    return rows, (lambda a, b: f"L{a}" if a == b else f"L{a}-{b}")
# **고정 지도는 시험이 주입한다**(B48 ⑤ · 문서 7 §7.1 대체 표 ⑦행) — 운영 코드는
# fixture 파일을 찾지 않는다: 미리 놓은 정답을 돌려주는 갈래는 배선이 없어도 초록이라
# 결함을 가린다(⑦ 미배선이 그렇게 숨었다). 파일은 그대로 있고 **자리만 바뀐다**(A11).
_MAPS = ROOT / "tests" / "fixtures" / "struct_maps"


def _fixed_map(name):
    """`ask=`로 주입할 고정 지도 — 실호출 경로가 타는 그 통로를 그대로 쓴다."""
    def ask(doc_id, lines):
        return json.loads((_MAPS / f"{name}.json").read_text(encoding="utf-8"))
    return ask


def done():
    """결과 줄과 종료 코드 — 스위트마다 같은 꼴이다."""
    print("\n" + "=" * 62)
    print("전체 결과:", "PASS — P1 완료판정 충족" if allok else "FAIL")
    sys.exit(0 if allok else 1)

