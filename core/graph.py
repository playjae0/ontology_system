# -*- coding: utf-8 -*-
"""GraphStore — 그래프 저장의 유일 경계 (틀 §4B-A8, 카드 B6, CH6 6.1 규약 6)

**graph.py 밖의 코드는 graph.json을 직접 열지 않는다.** run.py·viz.py·cli·테스트
전부 포함이며, 이것이 리뷰 규칙이다. 직접 여는 코드가 있으면 그 자체가 결함이다.

왜 경계가 필요한가: 저장 방식(단일 JSON → 샤딩 → SQLite)은 알람선에 도달하면
바뀔 수 있다(R10). 경계가 하나면 그날 고칠 곳이 여기 하나뿐이다.

- 직렬화는 orjson, 미설치 환경에서는 표준 json 폴백.
  "외부 패키지 0" 원칙을 폴백으로 보존한다.
- 알람선 = 층별 graph 파일 200MB 또는 build 30초. 계기판 7·8번(CH5 5.5)이
  관측하고, 도달하면 저장 전환 판정(R10)을 개시한다. 넘었다고 멈추지는 않는다 —
  판정을 개시하라는 신호다.

id 두 축 (CH6 6.1 규약 2):
  의미 축(Process·Unit·Property·Failure) = **발급**, 발급 후 불변. 방식은 ULID.
  근거 축(문서·청크·레코드) = 내용에서 계산 — core/ids.py 소관이며 여기서는 안 만든다.
"""
from __future__ import annotations

import time
from pathlib import Path

from .ids import new_ulid

try:                                    # 직렬화 — orjson 우선, 표준 json 폴백
    import orjson

    def _dumps(obj) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)

    def _loads(b: bytes):
        return orjson.loads(b)

    SERIALIZER = "orjson"
except ImportError:                     # pragma: no cover - 폴백 경로
    import json

    def _dumps(obj) -> bytes:
        return (json.dumps(obj, ensure_ascii=False, indent=2)).encode("utf-8")

    def _loads(b: bytes):
        return json.loads(b.decode("utf-8"))

    SERIALIZER = "json"


# 알람선 — 조절점(가결정, 실측 후 조정 가능). 증분0 §3 st "조절점".
ALARM_BYTES = 200 * 1024 * 1024
ALARM_BUILD_SECONDS = 30.0

# 엣지 status 어휘 (구현문서 §2.3)
STATUS_DELETED = "deleted_by_user"


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


class GraphStore:
    """층 하나의 그래프 파일을 소유한다. 층별로 인스턴스를 만든다.

    **파일 이름도 이 클래스가 소유한다.** 밖에서 경로를 조립해 넘기면
    저장 방식을 바꾸는 날(R10) 고칠 곳이 다시 여러 군데가 된다 —
    경계는 "여는 코드"만이 아니라 "어디에 있는지 아는 코드"까지다.
    """

    FILENAME = "graph.json"

    @classmethod
    def for_layer(cls, layer, data_dir=None):
        """층 그래프를 여는 **유일한 입구**."""
        base = Path(data_dir) if data_dir else _default_data_dir()
        return cls(base / layer / cls.FILENAME, layer)

    def __init__(self, path, layer):
        self._path = Path(path)
        self.layer = layer
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self._tombstones: set[tuple[str, str, str]] = set()
        self._build_started: float | None = None
        self.metrics: dict = {}

    # ---------- 수명주기 ----------
    def load(self):
        if self._path.exists():
            data = _loads(self._path.read_bytes())
            self.nodes = data.get("nodes", {})
            self.edges = data.get("edges", [])
        else:
            self.nodes, self.edges = {}, []
        self._reindex_tombstones()
        return self

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(_dumps({"nodes": self.nodes, "edges": self.edges}))
        return self._path.stat().st_size

    def _reindex_tombstones(self):
        self._tombstones = {
            (e["src"], e["rel"], e["dst"])
            for e in self.edges if e.get("status") == STATUS_DELETED
        }

    # ---------- 쓰기 ----------
    def add_node(self, canonical, category, status, attrs=None,
                 provenance=None, aliases=None, **extra):
        """노드를 발급하고 id를 돌려준다. id는 ULID이며 발급 후 불변(P4).

        의미 축은 개명·alias가 있어 해시로 만들 수 없다 — 그래서 발급이다.
        ULID는 중앙 카운터(구 id_seq.json) 없이 유일하므로 그 파일을 만들지 않는다.
        """
        nid = new_ulid()
        node = {
            "id": nid, "canonical": canonical, "category": category,
            "layer": self.layer, "status": status,
            "attrs": attrs or {}, "aliases": aliases or [],
            "provenance": list(provenance or []),
        }
        node.update(extra)                      # electrode_type 등 구조 필드
        self.nodes[nid] = node
        return nid

    def add_edge(self, src, rel, dst, status, provenance=None):
        """중복은 무시하고, 사람이 지운 툼스톤 (src,rel,dst)는 건너뛴다.

        건너뛰기가 필요한 이유: 재인입이 사람의 삭제를 되살리면 안 된다
        (명세 §5.5-3). 툼스톤은 graph.json에 영속한다.
        """
        if (src, rel, dst) in self._tombstones:
            return False
        for e in self.edges:
            if e["src"] == src and e["rel"] == rel and e["dst"] == dst:
                for p in (provenance or []):    # 중복 엣지는 provenance만 합집합
                    if p not in e["provenance"]:
                        e["provenance"].append(p)
                return False
        self.edges.append({"src": src, "rel": rel, "dst": dst,
                           "status": status, "provenance": list(provenance or [])})
        return True

    def update_node(self, nid, **changes):
        self.nodes[nid].update(changes)

    # ---------- 읽기 ----------
    def get(self, nid):
        return self.nodes.get(nid)

    def find(self, **cond):
        return [n for n in self.nodes.values()
                if all(n.get(k) == v for k, v in cond.items())]

    def neighbors(self, ids, traverse_spec):
        """프론티어 큐(BFS) 전파 — 명세 §5.6.2 v1.17.

        `recursive: false`는 "같은 관계를 연달아 재추적하지 않음"일 뿐이다.
        다른 관계로 도달한 노드에 그 관계를 적용하는 것은 막지 않는다 —
        공정→(part_of 하향)→설비→(has_property)→인자 2홉이 성립하는 근거다.
        traverse_spec의 내용은 config가 소유하고 여기서는 인자로 받는다(B).
        """
        seen, frontier = set(ids), list(ids)
        while frontier:
            nxt = []
            for e in self.edges:
                if e.get("status") == STATUS_DELETED:
                    continue
                for spec in (traverse_spec.get(e["rel"]) or {}).values():
                    d, rec = spec.get("direction", "both"), spec.get("recursive", False)
                    hits = []
                    if d in ("out", "both") and e["src"] in frontier:
                        hits.append(e["dst"])
                    if d in ("in", "both") and e["dst"] in frontier:
                        hits.append(e["src"])
                    for h in hits:
                        if h not in seen:
                            seen.add(h)
                            if rec:
                                nxt.append(h)
                            else:
                                seen.add(h)
            frontier = nxt
        return seen

    # ---------- 계기판 7·8 (CH5 5.5) ----------
    def build_begin(self):
        self._build_started = time.monotonic()

    def build_end(self):
        """build 말미에 계기판 7·8을 기록한다. 알람선 초과는 R10 판정 개시 신호."""
        size = self.save()
        secs = (time.monotonic() - self._build_started) if self._build_started else 0.0
        self.metrics = {
            "layer": self.layer,
            "serializer": SERIALIZER,
            "gauge7_graph_bytes": size,
            "gauge7_graph_mb": round(size / 1024 / 1024, 3),
            "gauge7_over_alarm": size > ALARM_BYTES,
            "gauge8_build_seconds": round(secs, 3),
            "gauge8_over_alarm": secs > ALARM_BUILD_SECONDS,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
        }
        return self.metrics
