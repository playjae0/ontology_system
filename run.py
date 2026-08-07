# -*- coding: utf-8 -*-
"""파이프라인 진입점 — CLI+파일 (구현문서 §0).

모든 단계는 subprocess로 호출 가능해야 한다(§16.1 플랫폼화 인지 계약).
**build는 직렬 실행**이다 — 저장이 비원자적이라 호출부가 직렬화를 보장한다.

사용:
  python run.py bootstrap          층 골격 심기 (n10)
  python run.py ingest <파일...>   계약 JSON 인입 (n2 → n1)
  python run.py all                bootstrap + mock/parsed 전량 인입
  python run.py gauges             계기판 7·8 출력
"""
import json
import sys
from pathlib import Path

from core import store
from core.bootstrap import bootstrap, open_graph
from core.pipeline import run_document
from router import discover

ROOT = Path(__file__).resolve().parent


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cmd_bootstrap():
    for layer in discover():
        g, m, ids = bootstrap(layer)
        if g is None:
            print(f"[bootstrap] {layer}: 골격 선언 없음 — 내장 층이 아니다 (J10)")
            continue
        print(f"[bootstrap] {layer}: 노드 {m['nodes']} · 엣지 {m['edges']}")
        print(f"            계기판 7 graph {m['gauge7_graph_mb']}MB "
              f"({m['serializer']}) · 8 build {m['gauge8_build_seconds']}s")


def cmd_ingest(paths):
    for p in paths:
        r, m, extracted = run_document(_load(p))
        mark = "보류" if r.status == "held" else "인입"
        tail = f"  ({r.reason})" if r.reason else (
            "  [추출 실행]" if extracted else "  [추출 체크포인트 재사용]")
        print(f"[{mark}] {r.doc_id}: record {len(r.record_ids)} · "
              f"chunk {len(r.chunk_ids)}{tail}")


def cmd_all():
    cmd_bootstrap()
    mock = sorted((ROOT / "mock" / "parsed").glob("*.json"))
    order = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
    idx = {n: i for i, n in enumerate(order)}
    cmd_ingest(sorted([p for p in mock if p.stem != "CP01B"],
                      key=lambda p: idx.get(p.stem, 99)))


def cmd_gauges():
    for layer in discover():
        g = open_graph(layer)
        g.build_begin()
        m = g.build_end()
        flag = "  ⚠ 알람선 초과 → R10 판정 개시" if (
            m["gauge7_over_alarm"] or m["gauge8_over_alarm"]) else ""
        print(f"{layer}: 계기판7 {m['gauge7_graph_mb']}MB · "
              f"계기판8 {m['gauge8_build_seconds']}s · "
              f"노드 {m['nodes']} 엣지 {m['edges']}{flag}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"bootstrap": lambda: cmd_bootstrap(),
     "ingest": lambda: cmd_ingest(sys.argv[2:]),
     "all": lambda: cmd_all(),
     "gauges": lambda: cmd_gauges()}[cmd]()
