# -*- coding: utf-8 -*-
"""공유 자원 파일 입출력 — 층 그래프 파일을 **제외한** data/ 전부.

층 그래프는 여기서 절대 다루지 않는다. 그것은 core/graph.py(GraphStore)의
단독 소유이며 파일 이름조차 그쪽이 갖는다 — 경계를 둘로 쪼개면 경계가 아니다(카드 B6).

공유 자원은 전 층 단일이다(CH6 6.1 규약 1, 카드 B4): 동의어 사전 · 청크 저장소 ·
수정 큐. 층 간 표면형 충돌은 사전이 허용하고 호출자가 카테고리·층으로 선별한다.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import log

try:
    import fcntl
except ImportError:                     # pragma: no cover - 비 POSIX
    fcntl = None

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
REGISTRY = "registry.json"            # **층** 등록부 (D-8)
DOC_TYPES = "doc_types.json"          # **doc_type** 등록부 (D-8 · n6이 등재)
DOC_REGISTRY = "doc_registry.json"    # doc_id → doc_hash 대장 (D-8)
OPS_LOG = "ops_log.json"              # I축 연산 로그 (D-8)
GATE_REJECTS = "gate_rejects.json"    # 게이트 거부 로그 — 큐가 아니다 (D-7)
SKELETON_LIST = "skeleton_closed_list.json"   # 골격 닫힌 목록 스냅샷 (D-11 확정)
DEFECTS = "defects.log"               # 결함 로그 (n1 id 충돌 등)
LINK_MISS = "link_miss.log"           # 질의 링킹 미스·수집 잘림 (CH5 5.1 규약 6·5.2 규약 3)

_LOG = log.get(__name__)


def path(name) -> Path:
    return DATA / name


# ---------------------------------------------------------------- 원자적 쓰기
def atomic_write_bytes(target: Path, data: bytes) -> int:
    """**진실을 반쯤 쓰인 채로 남기지 않는다** (문서 7 §7.1 저장 계층).

    `data/`는 백업 대상이지 재생성 대상이 아니다 — 사전·큐의 사람 판단 기록과
    승인 기록은 재생성되지 않는다(§7.7·§7.8). 그래서 대상 파일을 직접 덮어쓰면
    build가 쓰기 도중 죽었을 때 **진실이 복구 불가로 유실된다.**

    두 장치를 함께 건다:

    1. **같은 디렉터리의 tmp + `os.replace`** — 같은 파일시스템이라야 rename이
       원자적이다. `/tmp`에 쓰고 옮기면 크로스 디바이스 복사가 되어 원자성이 깨진다.
    2. **`fcntl.flock`** — 직렬 실행(§7.3-3③)은 *호출부의 약속*이고 저장 측 방어가
       0이면 호출부가 계약을 어겼을 때 막을 것이 없다. 락은 별도 `.lock` 파일에
       건다: 대상 파일에 걸면 replace가 그 inode를 갈아치워 락이 허공에 남는다.

    이것은 성능의 선반영(P7)이 아니라 **정합성 요구**다.

    `fcntl`이 없는 플랫폼(Windows)에서는 락만 생략하고 원자적 교체는 유지한다 —
    락 부재로 원자성까지 포기하면 방어가 0으로 되돌아간다.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / f".{target.name}.lock"   # 숨은 이름 — data/ 열람의 잡음이 아니게
    lf = None
    try:
        lf = lock.open("a+b")
        if fcntl is not None:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent),
                                   prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())            # 교체 전에 내용이 디스크에 닿아야 한다
            os.replace(tmp, target)             # 원자적 — 독자는 옛 판 또는 새 판만 본다
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    finally:
        if lf is not None:
            if fcntl is not None:
                try:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                except OSError:                  # pragma: no cover
                    pass
            lf.close()
    return len(data)


def read(name, default):
    p = path(name)
    return _loads(p.read_bytes()) if p.exists() else default


def write(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path(name), _dumps(obj))


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


def resolve_item(kind, match, *, actor, decision, at, note=""):
    """큐 항목에 **사람의 판단을 기록한다** (문서 7 §7.2 `resolution`).

    `resolution`이 있는 항목이 「사람의 판단이 기록된 항목」이고, 재인입 회수가
    그것을 **보존한다**(문서 4 §4.8-2③ · 문서 1 H6). 표시 필드가 없으면 회수가
    kind 화이트리스트로 대신하는데, 그것은 "재검출되지 않는 상시 목록"이지 "사람이
    판단한 항목"이 아니어서 사람의 판정이 조용히 지워진다.

    항목을 **내리지 않는다** — 내리는 것은 조건이 해소됐을 때 `drop`의 일이고,
    여기는 "봤고 이렇게 판단했다"를 남기는 자리다.
    """
    q = read(QUEUE, [])
    n = 0
    for x in q:
        if x.get("kind") != kind or not match(x.get("payload") or {}):
            continue
        x["resolution"] = {"actor": actor, "at": at, "decision": decision,
                           "note": note}
        n += 1
    if n:
        write(QUEUE, q)
        _LOG.info("큐 판정 %s — %s가 %d건을 '%s'로", kind, actor, n, decision)
    return n


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
    log.queue_put(_LOG, kind, reason, doc_id)   # 문서 7 §7.8 로그 3종
    write(QUEUE, q)
    return item
