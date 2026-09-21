# -*- coding: utf-8 -*-
"""LLM 지점 9종 **본문 스모크** — 실호출 갈래의 함수 본문을 한 번씩 돌린다 (B79 ③ⓒ).

도달성 탐침(`tests/points_probe.py`)과 **다른 성질**이다. 탐침은 「호출자가 타는 길이
미설정 실패(`NotConfigured`)에 닿는가」까지 잰다 — 그 뒤의 본문은 한 줄도 돌지 않는다.
사내 실측(2026-09-21)이 그 틈을 보였다: `points.pick_coord` 본문의 `json`이 import되지
않은 채 **회귀 1,362가 초록**이었다(좌표 태깅 실호출 갈래는 `USE_MOCK=1`에서 실행 0).

그래서 여기서는 **게이트웨이 전송 한 곳만**(`gateway._post`) 스텁으로 갈아 끼우고
나머지는 실물 그대로 돈다 — 선례는 `tests/test_2a_gateway.py`의 ⑦ 배선 시험이다.
재는 것은 「모델이 옳게 답하는가」가 아니라 **「반환 계약대로 값이 나오는가」**다.

스텁이 아는 것은 둘이다.
  ① 응답의 **형**: `response_format`의 JSON 스키마가 요구하는 최소 인스턴스를 만든다
     (enum은 첫 값 · 배열은 원소 하나). 스키마가 없으면 텍스트 한 줄이다.
  ② 두 관용: 키 이름이 `*_json`이면 JSON 문자열, `*_py`면 파이썬 모듈 문자열이다 —
     형은 string이지만 **내용이 그 형식이어야** 하류(⑤ 생성)가 돈다.

실행: `USE_MOCK=0` + 가짜 설정으로 이 파일을 돌리면 마지막 줄이 `RESULT <json>`이다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 스텁 게이트웨이의 설정 — 값은 가짜다(전송이 스텁이라 닿지 않는다).
STUB_ENV = {"USE_MOCK": "0", "LLM_GATEWAY_URL": "http://stub.invalid/v1",
            "CHAT_MODEL": "stub-chat", "EMBED_MODEL": "stub-embed",
            "LLM_CONTEXT_TOKENS": "100000"}


# ---------------------------------------------------------------- 스텁
def instance(schema):
    """JSON 스키마가 요구하는 **최소 인스턴스**. 형만 맞춘다."""
    s = schema or {}
    if "enum" in s and s["enum"]:
        return s["enum"][0]
    t = s.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    if t == "object":
        props = s.get("properties") or {}
        return {k: _by_name(k, v) for k, v in props.items()}
    if t == "array":
        return [instance(s.get("items") or {"type": "string"})]
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return True
    return "스텁"


def _by_name(key, schema):
    """두 관용 — `*_json`은 JSON 문자열, `*_py`는 모듈 문자열."""
    if (schema or {}).get("type") == "string":
        if key.endswith("_json"):
            return "{}"
        if key.endswith("_py"):
            return 'ADAPTER = {"doc_type": "stub"}\n\n\ndef extract(raw):\n    return []\n'
    return instance(schema)


def stub_post(url, payload, key, timeout):
    """`gateway._post` 대역 — 전송만 대신한다. **인증 헤더·키는 만들지 않는다.**"""
    if str(url).rstrip("/").endswith("/embeddings"):
        return {"data": [{"embedding": [0.125] * 8}], "model": "stub-embed"}
    schema = (((payload or {}).get("response_format") or {})
              .get("json_schema") or {}).get("schema")
    content = json.dumps(instance(schema), ensure_ascii=False) if schema \
        else "스텁 응답 한 줄."
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


# ---------------------------------------------------------------- 지점 9종
def cases():
    """지점 → `(실호출 함수 본문을 부르는 것, 반환 계약 검사)`."""
    from core import matcher, paths
    from core.llm import embeddings, points, struct_map_pass
    from core.query import query as Q
    from core.state.bootstrap import load_config, open_graph

    cfg = load_config("process")
    g = open_graph("process")
    pool = [{"id": "N1", "canonical": "탭용접", "aliases": [], "category": "Unit"}]

    def _generate():
        """⑤ — 입력 패키지(사람 4 + 시스템 5)가 자리에 있어야 본문이 돈다."""
        from cli.register import draft as D
        dt = "b79smoke"
        pkg = paths.review(dt, "input_package.json")
        paths.ensure(pkg)
        pkg.write_text(json.dumps({
            "_읽는_법": "스모크",
            "human": {"doc_type": dt, "layer": "process",
                      "samples": [str(ROOT / "tests/fixtures/raw/CP01.xlsx")],
                      "hint": ""},
            "system": {"reader_head": {}, "layer_vocabulary": {"layer": "process"},
                       "blocks": {}, "skeleton_excerpt": {}, "column_profile": {}},
        }, ensure_ascii=False), encoding="utf-8")
        try:
            return D._draft_live(dt, 0)
        finally:
            shutil.rmtree(paths.review(dt), ignore_errors=True)

    return {
        "extract": (
            lambda: __import__("core.build.extract", fromlist=["x"])._candidates_for(
                "C1", {"text": "탭용접 공정에서 버가 발생한다", "process_ref": "노칭"},
                cfg, {}),
            lambda r: isinstance(r, dict) and r.get("chunk_id") == "C1"
            and all(isinstance(r.get(k), list) for k in ("entities", "relations", "attach"))),
        "judge": (
            lambda: matcher._judge_live("탭 용접", pool, "Unit", cfg),
            lambda r: isinstance(r, dict) and r.get("type") in ("match", "new", "uncertain")
            and "confidence" in r and "path" in r),
        "embed": (
            lambda: embeddings.embed("탭용접"),
            lambda r: isinstance(r, list) and r and all(isinstance(x, float) for x in r)),
        "image_summary": (
            lambda: points.summarize_image("img_001", image=b"\x89PNG",
                                           mime="image/png", context="맥락"),
            lambda r: isinstance(r, str) and r),
        # ⑤의 반환 계약은 **떨어뜨린 파일 둘**이다(어댑터·스키마).
        "generate": (_generate,
                     lambda r: isinstance(r, tuple) and len(r) == 2
                     and all(Path(x).name.startswith(("adapter", "schema")) for x in r)),
        "link": (
            lambda: Q._link_llm("노칭 다음 공정은?", {"process": g}),
            lambda r: isinstance(r, list)),
        "struct_map": (
            lambda: struct_map_pass.map_structure("D1", [(1, "1. 개요"), (2, "본문")]),
            lambda r: isinstance(r, dict) and r.get("source") == "live"
            and isinstance(r.get("rows"), list) and r["rows"]),
        "answer": (
            lambda: __import__("cli.query", fromlist=["x"]).generate(
                {"question": "탭용접 다음은?", "facts": ["탭용접 → 노칭"],
                 "chunks": [], "path": "graph_fact", "linked": [], "note": None,
                 "truncated": 0, "transit": []}),
            lambda r: isinstance(r, str) and r),
        "coord_tag": (
            lambda: points.pick_coord("탭 용접", ["탭용접", "노칭"]),
            lambda r: r is None or isinstance(r, str)),
    }


def run():
    """스모크를 **서브프로세스로** 돌려 `{지점: 결과}`를 돌려준다.

    서브프로세스인 이유는 탐침과 같다 — 모드와 설정은 진입 시점에 정해진다.
    결과는 `"OK"` · `"계약위반 <값>"` · 예외 이름 중 하나다.
    """
    with tempfile.TemporaryDirectory(prefix="smoke_home_") as home:
        shutil.copytree(ROOT / "layers", Path(home) / "layers")
        env = {**os.environ, **STUB_ENV, "ONTO_HOME": str(home),
               "ONTO_CONFIG": str(ROOT / "tests" / "fixtures" / "_no_such_llm_config.json")}
        r = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                           capture_output=True, text=True, cwd=str(ROOT), env=env)
    line = next((x for x in r.stdout.splitlines() if x.startswith("RESULT ")), None)
    return (json.loads(line[len("RESULT "):]) if line else {}), r


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from core.llm import gateway
    gateway._post = stub_post                  # **전송 한 곳만** 갈아 끼운다
    out = {}
    for name, (call, contract) in cases().items():
        try:
            got = call()
            out[name] = "OK" if contract(got) else f"계약위반 {str(got)[:80]}"
        except BaseException as e:              # 본문이 죽는 것이 이 시험의 표적이다
            out[name] = f"{type(e).__name__}: {str(e)[:80]}"
    print("RESULT " + json.dumps(out, ensure_ascii=False))
