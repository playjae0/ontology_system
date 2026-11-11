# -*- coding: utf-8 -*-
"""칸 3.4 — **극성은 값의 한정어다**(B198 · 결정 `결정_극성_값단.md` 2-3 ~ 2-8) — 노드를 가르지 않는다.

극성이 들어가는 자리는 셋이고 뜻은 하나다 — **비면 공통**:

| 자리 | 무엇 |
|---|---|
| 값 | 값 항목의 `context.polarity`(`Builder.put_attribute` — 값 충돌은 같은 context끼리만) |
| 엣지 · 노드 | 필요할 때만 생기는 칸 `FIELD` = `{출처: 극성}`(극성이 적힌 출처만) · 칸이 없으면 공통(극성 없는 엣지 · 노드는 바이트 그대로) |
| 보이는 극성 | `visible` 하나(엣지 · 노드 공용) — 모든 출처가 같은 한 극성이면 그 극성 · 그 밖은 공통(None) |

극성은 **시스템이 쓴다**(B7) — 행 · 청크의 구조 필드 `electrode_type`(C10)에서 옮겨 적는다(LLM · 스키마 · attribute 핸들러가 쓰지 않는다).
값의 이름은 골격 `AXIS_LABELS`의 키(닫힌 목록 — 골격 닫힌 목록 스냅샷의 `axis`가 그 사본이다 · 코드에 축 값 0).
출처 → 극성은 그 문서의 봉투(레코드 · 청크의 `source_locator` · `electrode_type`)에서 읽는다 — 구축 중에는 `begin`이 실은 것 ·
그 밖(재시도 · 사람 도구)은 `parsed/<문서>.json`. 노드 · 엣지의 칸은 **그래프 저장 앞 한 자리**(`GraphStore.save` → `stamp_graphs`)가 적는다.
"""
from __future__ import annotations

#: 엣지 · 노드의 출처별 극성 칸(B198 가결정 — 칸 이름)
FIELD = "polarity_by"
#: 값 항목 context의 극성 열쇠
CTX = "polarity"

#: 문서 → `{출처: 극성}` — 구축 중인 문서의 봉투에서(`begin`) · 없으면 `parsed/`에서(파일 판으로 기억)
_ROWS, _FILE = {}, {}
_AXIS = {}


def axis():
    """극성 값의 닫힌 목록 `{값: 표시 이름}` — 골격 `AXIS_LABELS`(골격 닫힌 목록 스냅샷 `axis` · 층마다 합친다 · 파일 판으로 기억)."""
    from core.state import store
    p = store.path(store.SKELETON_LIST)
    key = (str(p), p.stat().st_mtime_ns if p.exists() else None)
    if key not in _AXIS:
        out = {}
        for snap in (store.read(store.SKELETON_LIST, {}) or {}).values():
            out.update((snap or {}).get("axis") or {})
        _AXIS.clear()
        _AXIS[key] = out
    return _AXIS[key]


def of(value):
    """행 · 청크의 `electrode_type` → 극성 값(닫힌 목록 안일 때만) · 그 밖(빈칸 · 공통 표기 · 목록 밖)은 None = 공통."""
    return value if value and value in axis() else None


def _rows_of(env):
    doc = env.get("doc_id")
    out = {}
    for x in list(env.get("records") or []) + list(env.get("chunks") or []):
        loc, pol = x.get("source_locator"), of(x.get("electrode_type"))
        if loc and pol:
            out[f"{doc}#{loc}"] = pol
    return out


def begin(env):
    """구축할 문서의 출처 → 극성을 싣는다(문서 시작 — `entry.run_document`)."""
    if env and env.get("doc_id"):
        _ROWS[env["doc_id"]] = _rows_of(env)
        _FILE.pop(env["doc_id"], None)


def of_prov(prov):
    """출처 하나의 극성(없으면 None) — 출처 꼴 `{문서}#{위치}`(`loop._prov`) · 그 밖(`seed` · `auto:…`)은 None."""
    if not prov or "#" not in str(prov):
        return None
    doc = str(prov).split("#", 1)[0]
    if doc in _ROWS:
        return _ROWS[doc].get(prov)
    from core import paths
    p = paths.parsed(f"{doc}.json")
    key = (str(p), p.stat().st_mtime_ns if p.exists() else None)
    if (_FILE.get(doc) or (None,))[0] != key:
        rows = {}
        if key[1] is not None:
            try:
                import json
                rows = _rows_of(json.loads(p.read_text(encoding="utf-8")))
            except Exception:                               # 읽지 못하는 봉투는 공통으로(극성을 지어내지 않는다)
                rows = {}
        _FILE[doc] = (key, rows)
    return _FILE[doc][1].get(prov)


def stamp(obj):
    """엣지 · 노드 하나의 칸을 지금 출처로 다시 적는다 — 출처마다 `of_prov` · 빠진 출처의 칸은 걷는다 · 비면 칸 없음."""
    provs = list(obj.get("provenance") or [])
    m = {p: of_prov(p) for p in provs}
    m = {p: v for p, v in m.items() if v}
    if m:
        obj[FIELD] = m
    else:
        obj.pop(FIELD, None)


def stamp_graphs(graphs):
    """그래프들의 노드 · 엣지 전부 — 문서 끝 저장 앞 한 자리(`entry._finish_build` · 표 · 산문 · 렌즈)."""
    for g in graphs:
        for n in g.nodes.values():
            stamp(n)
        for e in g.edges:
            stamp(e)


def visible(obj):
    """**보이는 극성**(엣지 · 노드 공용 — 결정 2-6) — 모든 출처가 같은 한 극성이면 그 극성 · 그 밖은 None(공통).

    두 극성이 다 나오거나 극성 없이 말한 출처가 하나라도 있으면 공통 · 넣는 차례와 무관(집합) · 출처가 빠지면 남은 출처로 센다."""
    provs = list((obj or {}).get("provenance") or [])
    m = (obj or {}).get(FIELD) or {}
    if not provs or not m:
        return None
    got = {m.get(p) for p in provs}
    return next(iter(got)) if len(got) == 1 and None not in got else None


def of_value(item):
    """값 항목의 극성(없으면 None = 공통)."""
    return ((item or {}).get("context") or {}).get(CTX)


def label(value):
    """극성 값의 표시 이름(골격 `AXIS_LABELS`) — 공통(None)은 None."""
    return axis().get(value, value) if value else None


def asked(question):
    """물음에 걸린 극성 — 축 값 또는 그 표시 이름이 글 속에 있으면 그 값(둘 이상이면 None — 거르지 않는다)."""
    from core.state.ids import fold_latin
    q = fold_latin(question or "")
    hit = {v for v, lab in axis().items() if fold_latin(v) in q or (lab and fold_latin(lab) in q)}
    return next(iter(hit)) if len(hit) == 1 else None


def keeps(pol, want):
    """질의 거르기 — 물음의 극성이 없거나 · 공통이거나 · 그 극성이면 남긴다(결정 2-10)."""
    return want is None or pol is None or pol == want


def concept_name(name, sep=None):
    """**옛 극성 이름 → 개념 이름**(B198 ④ — 사람 기록 재생 · 대장 싣기 · 쌍 확인이 한 함수) — 마디가 축 값이면 그 마디를 빼고
    (`<공정>::<축값>`) · 마디가 `<축값> <이름>`이면 축 값을 뗀다(옛 결합 이름) · 바뀐 것이 없으면 그대로. 축 값은 데이터(`axis`)."""
    if not name:
        return name
    if sep is None:
        from core.state import catalog
        sep = catalog.sep()
    vals = list(axis())
    out = []
    for part in str(name).split(sep):
        if part in vals:
            continue
        for v in vals:
            if part.startswith(v + " "):
                part = part[len(v) + 1:]
                break
        out.append(part)
    return sep.join(out) or name
