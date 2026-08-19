# -*- coding: utf-8 -*-
"""관통 1회 — 어댑터 산출을 **실제 파이프라인에 넣어** 인입→적재→질의까지 돌린다.

실행 하네스(kit/run_adapter.py)가 "산출물이 계약을 지키는가"를 보는 관문이라면,
이것은 **"그 산출물로 그래프가 실제로 서는가"**를 본다. 하네스는 조각까지만 보고
인입 코드를 부르지 않으므로, 하네스를 통과하고도 인입에서 죽는 조합이 있다
(A-4 실측: `context`를 스칼라로 낸 어댑터).

**층 어휘 0** — doc_type·층 이름을 인자로 받고 코드가 알지 않는다.

사용: python tools/passthrough.py <adapter.py> <schema.json> <doc_id> <문서> [질문...]
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import store                                    # noqa: E402
from core.bootstrap import bootstrap, open_graph          # noqa: E402
from core.pipeline import run_document                    # noqa: E402
from parser.reader import read                            # noqa: E402
from router import discover                               # noqa: E402


def load_adapter(path):
    spec = importlib.util.spec_from_file_location("passthrough_adapter", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def envelope(mod, doc_id, source_path, pieces):
    """봉투는 파서가 구성한다(CH2 2.2) — 여기서는 어댑터 선언값을 그대로 옮긴다."""
    key = "records" if mod.ADAPTER["payload_kind"] == "table" else "chunks"
    return {"doc_id": doc_id, "doc_type": mod.ADAPTER["doc_type"],
            "source_path": source_path, "revision": "R1",
            "parsed_at": "2026-08-18T00:00:00", "parser_version": "harness",
            "adapter_version": mod.ADAPTER.get("adapter_version"),
            "payload_kind": mod.ADAPTER["payload_kind"], key: pieces}


def main(adapter_path, schema_path, doc_id, doc, questions):
    mod = load_adapter(adapter_path)
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    layer = schema["layer"]

    for lay in discover():                                # 골격은 깨끗한 상태에서
        bootstrap(lay, echo=False)
    before = {n["id"] for n in open_graph(layer).nodes.values()}
    q_before = len(store.read(store.QUEUE, []))

    pieces = mod.extract(read(doc))
    res, metrics, _ = run_document(envelope(mod, doc_id, doc, pieces))
    g = open_graph(layer)
    new = [n for n in g.nodes.values() if n["id"] not in before]

    print(f"\n■ 인입 — {res}")
    print(f"■ 적재 — 신규 노드 {len(new)} · 카테고리 {dict(Counter(n['category'] for n in new))}")
    # 엣지의 provenance는 doc_id가 아니라 **source_locator**다(조각 공통·role=meta).
    # 이 문서의 조각 locator 집합으로 귀속을 판정한다.
    locs = {p.get("source_locator") for p in pieces}
    fresh = [e for e in g.edges
             if any(p in locs for p in e.get("provenance", []))]
    print(f"■ 적재 — 이 문서 유래 엣지 {len(fresh)} · {dict(Counter(e['rel'] for e in fresh))}")
    print("■ 스키마 edges 선언 대조")
    for dec in schema.get("edges", []):
        n = sum(1 for e in fresh if e["rel"] == dec["relation"])
        print(f"    {dec['from']} -{dec['relation']}-> {dec['to']}   실적재 {n}건")
    q = store.read(store.QUEUE, [])
    print(f"■ 큐 — 유입 {len(q) - q_before}건 · {dict(Counter(x['kind'] for x in q))}")

    if questions:
        from cli.query import answer, render
        print("\n■ 질의")
        for qq in questions:
            print(render(answer(qq)))
    return 0


if __name__ == "__main__":
    a, s, d, doc, *qs = sys.argv[1:]
    sys.exit(main(a, s, d, doc, qs))
