# -*- coding: utf-8 -*-
"""2A 게이트웨이 골조 — LLM 지점 8종의 mock/실호출 분기 (문서 7 §7.6-B).

**이 스위트가 잠그는 것**: USE_MOCK=0에서 설정이 비어 있을 때 8지점이 각각
**명시적으로 실패하는가**. 조용히 mock으로 떨어지는 지점이 하나라도 있으면 그것이
"모델 미연결 상태가 완료판정을 통과하는" 경로다 — 국면 1에서 실제로 일어난 일이다.

주석을 세지 않는다. **분기를 실행해서 확인한다.**
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # 테스트는 파일로 직접 실행된다(회귀 10종 관례)

_fail = 0


def show(label, ok, detail=""):
    global _fail
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _fail += 1
    return ok


# ============================================================ 게이트웨이 2파일
print("\n■ 게이트웨이 2파일 (§7.6-B-1)")

from core import embeddings, llm                                 # noqa: E402

show("core/llm.py — chat(messages, *, model, json_schema)",
     hasattr(llm, "chat")
     and {"model", "json_schema"} <= set(llm.chat.__code__.co_varnames))
show("core/embeddings.py — embed(text) -> vector", hasattr(embeddings, "embed"))
show("LLM 지점 목록이 닫힌 8종이다 (§7.6-B-2)",
     len(llm.POINTS) == 8 and "answer" in llm.POINTS, ", ".join(llm.POINTS))

# 설정 접근이 이 파일 하나로 수렴하는가 — 호출부가 환경변수를 직접 읽지 않는다.
_ENV = ("ONTO_LLM_URL", "ONTO_LLM_KEY", "ONTO_LLM_MODEL", "ONTO_EMBED_MODEL")
leaks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).glob("*.py")) if p.name != "llm.py"
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if any(e in ln for e in _ENV) and not ln.lstrip().startswith("#")
         and "|" not in ln]
show("LLM 설정 접근이 core/llm.py 하나로 수렴한다 (§7.6-B-1)", not leaks, str(leaks))

# ============================================================ mock 갈래
print("\n■ mock 갈래 — 결정성이 우선이다 (§7.5-1)")

v1, v2 = embeddings.embed("노칭 정밀도"), embeddings.embed("노칭 정밀도")
show("임베딩 mock이 결정적이다 (sha256 → 정규화 벡터)", v1 == v2 and len(v1) == 64)
show("자기 유사도 1.0 · 다른 텍스트는 낮다",
     abs(embeddings.cosine(v1, v1) - 1.0) < 1e-9
     and embeddings.cosine(v1, embeddings.embed("버 발생")) < 0.5)

from parser import tagger                                        # noqa: E402

m = tagger.complete_images([{"source_locator": "S", "image_ref": "i1"}])[0]
show("이미지 요약 mock이 데이터로 표시된다 (§7.6-B-4)",
     m["meta"].get("image_summary") is True
     and m["meta"].get("image_summary_source") == "mock", str(m["meta"]))
live = tagger.complete_images([{"source_locator": "S", "image_ref": "i1"}],
                              lambda r: f"요약({r})")[0]
show("실호출 갈래는 source=live로 갈린다 — 두 갈래가 같은 반환 계약",
     live["meta"]["image_summary_source"] == "live"
     and set(m["meta"]) == set(live["meta"]))

# ============================================================ USE_MOCK=0
print("\n■ USE_MOCK=0 + 설정 미설정 → 8지점 각각 명시적 실패 (§7.6-B-4 · 완료판정 5)")

PROBE = r'''
import json, sys
from core import embeddings, llm, matcher, query as Q
from core.bootstrap import open_graph
from core.dictionary import Dictionary
from parser import struct_map, tagger
g = open_graph("process")
n = {"id": "N1", "canonical": "나", "aliases": [], "category": "Unit", "exact": False}
CASES = {
 "extract":       lambda: __import__("core.extract", fromlist=["x"])._candidates_for(
                      "C1", {"text": "가"}, {"categories": {}, "relations": []}, {}),
 "judge":         lambda: matcher.match("가", [n], "Unit"),
 "embed":         lambda: embeddings.embed("가"),
 "image_summary": lambda: tagger.complete_images(
                      [{"source_locator": "S", "image_ref": "i1"}], None, allow_mock=False),
 "generate":      lambda: __import__("cli.register", fromlist=["x"])._draft_live("cp", 0),
 "link":          lambda: Q.link("노칭", Dictionary({}), {"process": g}),
 "struct_map":    lambda: struct_map.propose("D1", [(1, "1. 가")]),
 "answer":        lambda: __import__("cli.query", fromlist=["x"]).generate(
                      {"question": "가", "facts": [], "chunks": [], "path": "graph_fact",
                       "linked": [], "note": None, "truncated": 0, "transit": []}),
}
out = {}
for k, fn in CASES.items():
    try:
        fn(); out[k] = "통과"
    except BaseException as e:
        out[k] = type(e).__name__
print("RESULT " + json.dumps(out, ensure_ascii=False))
'''

env = dict(os.environ, USE_MOCK="0")
for e in _ENV:
    env.pop(e, None)
r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True,
                   cwd=str(ROOT), env=env)
import json                                                      # noqa: E402

line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")), None)
res = json.loads(line[len("RESULT "):]) if line else {}
show("8지점 전부가 실행됐다 (탐침이 완주)", len(res) == 8,
     r.stderr.strip().splitlines()[-1:] and r.stderr.strip().splitlines()[-1] or "")
for key, label in llm.POINTS.items():
    got = res.get(key, "(미실행)")
    show(f"{label} → 조용한 통과가 아니다", got != "통과", got)

# ============================================================ 분기 실물
print("\n■ 분기가 실물로 서 있는가 — 주석을 세지 않는다 (§7.6-B-2)")

WIRED = {"extract": ("core/extract.py", "_candidates_for"),
         "judge": ("core/matcher.py", "_judge_live"),
         "embed": ("core/embeddings.py", "llm.require"),
         "image_summary": ("parser/tagger.py", "allow_mock"),
         "generate": ("cli/register.py", "_draft_live"),
         "link": ("core/query.py", "_link_deep"),
         "struct_map": ("parser/struct_map.py", "ask is None"),
         "answer": ("cli/query.py", "def generate")}
for key, (where, needle) in WIRED.items():
    src = (ROOT / where).read_text(encoding="utf-8")
    show(f"{llm.POINTS[key]} — 실호출 갈래가 {where}에 있다", needle in src)

hooks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).glob("*.py"))
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if "HOOK:" in ln]
show("주석 훅 표시가 0건이다 — 주석은 실행되지 않는다", not hooks, str(hooks))

print("\n" + "=" * 62)
print(f"전체 결과: {'PASS — 게이트웨이 골조 성립' if not _fail else f'FAIL {_fail}건'}")
sys.exit(1 if _fail else 0)
