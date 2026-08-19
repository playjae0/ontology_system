# -*- coding: utf-8 -*-
"""공유 자원 파일 입출력 — 층 그래프 파일을 **제외한** data/ 전부.

층 그래프는 여기서 절대 다루지 않는다. 그것은 core/graph.py(GraphStore)의
단독 소유이며 파일 이름조차 그쪽이 갖는다 — 경계를 둘로 쪼개면 경계가 아니다(카드 B6).

공유 자원은 전 층 단일이다(CH6 6.1 규약 1, 카드 B4): 동의어 사전 · 청크 저장소 ·
수정 큐. 층 간 표면형 충돌은 사전이 허용하고 호출자가 카테고리·층으로 선별한다.
"""
from __future__ import annotations

from pathlib import Path

try:
    import orjson

    def _dumps(o) -> bytes:
        return orjson.dumps(o, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)

    def _loads(b: bytes):
        return orjson.loads(b)
except ImportError:                     # pragma: no cover - 폴백 경로
    import json

    def _dumps(o) -> bytes:
        return json.dumps(o, ensure_ascii=False, indent=2).encode("utf-8")

    def _loads(b: bytes):
        return json.loads(b.decode("utf-8"))

DATA = Path(__file__).resolve().parent.parent / "data"

# data/ 파일 이름 (증분0 §6-7 파일 트리 증분)
CHUNKS = "chunks.json"
DICTIONARY = "dictionary.json"
QUEUE = "review_queue.json"
REGISTRY = "registry.json"            # 층 등록부 (D-8)
DOC_REGISTRY = "doc_registry.json"    # doc_id → doc_hash 대장 (D-8)
OPS_LOG = "ops_log.json"              # I축 연산 로그 (D-8)
GATE_REJECTS = "gate_rejects.json"    # 게이트 거부 로그 — 큐가 아니다 (D-7)
DEFECTS = "defects.log"               # 결함 로그 (n1 id 충돌 등)
LINK_MISS = "link_miss.log"           # 질의 링킹 미스·수집 잘림 (CH5 5.1 규약 6·5.2 규약 3)


def path(name) -> Path:
    return DATA / name


def read(name, default):
    p = path(name)
    return _loads(p.read_bytes()) if p.exists() else default


def write(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    path(name).write_bytes(_dumps(obj))


def append_line(name: str, line: str):
    """줄 단위 로그는 덮지 않고 쌓는다 — 조용히 버리지 않는다(G5)."""
    DATA.mkdir(parents=True, exist_ok=True)
    with path(name).open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def append_defect(line: str):
    """결함 로그 — 처리 대상이 아니라 관측 신호다(계기판 재료)."""
    append_line(DEFECTS, line)


def drop(kind, match):
    """그 kind의 큐 항목 중 `match(payload)`가 참인 것을 걷어낸다 — **self-heal**의 손이다.

    CH3B 3.5 규약 6은 mirrors에 대해 *"매 빌드마다 재평가하고 대칭이 회복되면 큐에서
    제거한다"*고 요구한다. 재평가가 새 항목을 쌓기만 하면 **고쳐진 조건이 화면에서
    영영 사라지지 않는다** — 큐는 조건의 화면이지 이력이 아니다(P-3).
    재계산하는 쪽이 자기 소관 범위를 걷어내고 현재 스냅샷을 다시 싣는다.
    """
    q = read(QUEUE, [])
    kept = [x for x in q if not (x.get("kind") == kind and match(x.get("payload") or {}))]
    if len(kept) != len(q):
        write(QUEUE, kept)
    return len(q) - len(kept)


def enqueue(kind, reason, doc_id, payload):
    """수정 큐. 처리 못 한 것은 전부 종류가 붙은 큐 항목이 된다 —
    실패는 예외가 아니라 등급이다(CH3B 3.7 규약 2).

    **같은 항목을 두 번 싣지 않는다** (3.5 규약 6 "큐는 쌍 키로 중복 제거"). 조건은
    빌드마다 다시 판정되므로 중복 방지가 없으면 같은 조건이 재인입마다 증식한다
    (실측: `run.py all` 1회 3항목 → 2회 7 → 3회 11). 동일성 기준은 **(kind, doc_id,
    payload)** — payload의 node_id는 재인입에도 불변이라(P4) 결정적이다.

    회수(=조건이 해소되어 화면에서 내리는 것)는 여기가 아니라 `drop()`이 한다 —
    싣는 쪽과 내리는 쪽을 가르지 않으면 **재검출되지 않는 상시 조건**(auto_node 같은
    미검토 작업목록)까지 재인입이 지워 버린다.
    """
    q = read(QUEUE, [])
    item = {"kind": kind, "payload": payload, "reason": reason,
            "doc_id": doc_id, "created": "2026-01-05T00:00:00"}
    for x in q:
        if (x.get("kind"), x.get("doc_id"), x.get("payload")) \
                == (kind, doc_id, payload):
            return x
    q.append(item)
    write(QUEUE, q)
    return item
