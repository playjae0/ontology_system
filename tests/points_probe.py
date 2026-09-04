# -*- coding: utf-8 -*-
"""LLM 지점 9종 **도달 가능성** 탐침 (문서 7 §7.6-B-2 · B48).

재는 것은 *"분기가 있는가"*가 아니라 **"실 호출 경로를 타서 미설정 실패
(`NotConfigured`)에 닿는가"**다. 파라미터만 있고 값이 올 통로가 없으면 배선이
아니다 — ⑦구조 지도가 그랬고(`propose(ask=)`만 있고 `apply()`에 통로 없음),
탐침이 그것을 **직접 호출**해 「명시적 실패 준수」로 세는 바람에 미배선이 초록이었다.

**파서 3지점(④·⑦·⑨)은 팩토리로 잰다.** 파서 함수를 직접 부르면 §7.1 대체 갈래가
정상으로 돌아 「통과」가 되는데, 그것은 파서가 옳게 동작한 것이지 배선이 있다는
뜻이 아니다. 실제 호출자(`cli/parse.py`)가 타는 길은 `llm.<x>er()` 팩토리다.

**이 파일이 정본이고 둘이 같은 것을 실행한다** — `tests/test_2a_gateway.py`와
`doctor.py`. 두 벌로 두면 한쪽만 고쳐지는 날이 오고, 그날 화면은 초록인데 배선은 없다.

실행: `USE_MOCK=0` + 설정 없음으로 이 파일을 돌리면 마지막 줄이 `RESULT <json>`이다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 설정을 지울 때 함께 비워야 하는 환경변수 — 남으면 탐침이 «설정된 상태»로 돈다.
ENV_KEYS = ("LLM_GATEWAY_URL", "LLM_API_KEY", "CHAT_MODEL", "EMBED_MODEL")


def cases():
    """지점 → 「호출자가 타는 길」. **팩토리가 있는 지점은 팩토리를 부른다.**

    core 6지점은 **종전 방식 그대로**다(인라인 분기 — 팩토리로 옮기는 것은 다음 회차).
    """
    from core import embeddings, llm, matcher, query as Q
    from core.bootstrap import load_config, open_graph
    from core.dictionary import Dictionary

    g = open_graph("process")
    # **표면형과 다른 canonical이어야 한다** — 같으면 정확 일치 규칙이 먼저 답해
    # 모델을 부르지 않고, 그 「통과」가 미설정 실패로 잘못 세어진다.
    n = {"id": "N1", "canonical": "나", "aliases": [], "category": "Unit", "exact": False}
    return {
        # ── core 6지점 — 인라인 분기(다음 회차에 팩토리로 옮긴다)
        # **실물 config를 쓴다** — 축약 dict를 넘기면 프롬프트 조립이 `cfg["layer"]`에서
        # 먼저 깨져 KeyError가 나고, 그것이 「명시적 실패」로 잘못 세어진다(실측).
        "extract": lambda: __import__("core.extract", fromlist=["x"])._candidates_for(
            "C1", {"text": "가", "process_ref": "노칭"}, load_config("process"), {}),
        "judge": lambda: matcher.match("가", [n], "Unit"),
        "embed": lambda: embeddings.embed("가"),
        "generate": lambda: __import__("cli.register", fromlist=["x"])._draft_live("cp", 0),
        "link": lambda: Q.link("노칭", Dictionary({}), {"process": g}),
        "answer": lambda: __import__("cli.query", fromlist=["x"]).generate(
            {"question": "가", "facts": [], "chunks": [], "path": "graph_fact",
             "linked": [], "note": None, "truncated": 0, "transit": []}),
        # ── 파서 3지점 — **팩토리로 잰다**(B48). 파서 함수 직접 호출이 아니다.
        "image_summary": llm.image_summarizer,
        "struct_map": llm.struct_mapper,
        "coord_tag": llm.coord_picker,
    }


def probe_env(base=None):
    """설정이 **확실히 없는** 실호출 모드 환경.

    환경변수를 지우는 것만으로는 성립하지 않는다 — 설정 파일 갈래(B42)가 있어
    운영자 기계에 `~/.onto/llm.json`이 있으면 탐침이 «설정된 상태»로 돈다(실측).
    없는 경로를 명시해 그 갈래를 끈다.
    """
    env = dict(base or os.environ, USE_MOCK="0",
               ONTO_CONFIG=str(ROOT / "tests" / "fixtures" / "_no_such_llm_config.json"))
    for e in ENV_KEYS:
        env.pop(e, None)
    return env


def run():
    """탐침을 **서브프로세스로** 돌려 `{지점: 결과}`를 돌려준다.

    서브프로세스인 이유: 이 프로세스는 이미 설정을 읽었을 수 있고, 모드는 진입 시점에
    정해진다. 결과값은 `NotConfigured` 같은 **예외 이름** 또는 `"통과"`(= 조용한 통과)다.
    """
    r = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                       capture_output=True, text=True, cwd=str(ROOT), env=probe_env())
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT ")), None)
    return (json.loads(line[len("RESULT "):]) if line else {}), r


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    out = {}
    for k, fn in cases().items():
        try:
            fn()
            out[k] = "통과"
        except BaseException as e:            # 무엇에 닿았는지가 판정이다
            out[k] = type(e).__name__
    print("RESULT " + json.dumps(out, ensure_ascii=False))
