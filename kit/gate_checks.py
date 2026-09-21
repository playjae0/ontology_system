# -*- coding: utf-8 -*-
"""칸 1.5 — **④ 스키마 정합**: 형 검사(G4F) · 대장 커버리지(G4G) · 어휘 · role 드라이런.

표는 `kit/gate_tables.py`가 갖고, 화면은 `kit/gate_screen.py`가 낸다 — 여기는
**재는 일**만 한다.
"""
from __future__ import annotations

import json
from pathlib import Path

from gate_screen import show
import gate_screen
import gate_tables as tables
from gate_tables import (BLOCKS_PATH, structural_fields, ROLES, SHAPE_ADAPTER, SHAPE_KNOWN_ADAPTER,
                         SHAPE_KNOWN_SCHEMA, SHAPE_SCHEMA, SHAPE_SCHEMA_ENUM,
                         STRUCT_ONLY, load_blocks)

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- ④ 스키마 정합
def payload_kind_of(schema, mod):
    """payload_kind의 선언처 — **스키마 우선, 없으면 어댑터**.

    둘 다 계약 선언물이고 하네스는 doc_type이 일치하는 한 쌍만 받는다(main의 대조).
    스키마가 선언하지 않는 경우가 실재하므로(3차 산출 fixture 2종 모두 미선언) 폴백을
    둔다 — 어느 쪽도 선언하지 않으면 분기 자체가 불가능하니 그때는 명시적 실패다.
    **값으로 분기하고 doc_type 이름으로 분기하지 않는다**(B1).
    """
    return schema.get("payload_kind") or (mod.ADAPTER or {}).get("payload_kind")


def _vocab(layer):
    """층 어휘 — **패키지가 먼저다**(B65 ② — 새 계산 0), 없으면 층 config를 읽는다.

    패키지 `system.layer_vocabulary`는 등록 시점의 스냅샷이고 config는 실물이다.
    둘은 같은 자산이라 어느 쪽을 읽어도 판정이 갈리지 않는다 — 관문이 패키지 없이
    돌 때(회귀·수동 실행)도 대조가 살아 있어야 하므로 폴백을 둔다.
    """
    pkg_v = {}
    if tables.PACKAGE and Path(tables.PACKAGE).exists():
        try:
            lv = ((json.load(open(tables.PACKAGE, encoding="utf-8")).get("system") or {})
                  .get("layer_vocabulary") or {})
            if lv.get("layer") == layer and lv.get("categories"):
                pkg_v = lv
        except Exception:
            pkg_v = {}
    if pkg_v:
        return pkg_v
    cfg = tables.layers_dir() / str(layer) / "config.json"
    if not cfg.exists():
        return {}
    try:
        c = json.load(open(cfg, encoding="utf-8"))
    except Exception:
        return {}
    return {"layer": layer, "categories": c.get("categories"),
            "relations": c.get("relations"),
            "relation_patterns": c.get("relation_patterns")}


def _cat_of(fields, name):
    """필드 이름(또는 `@좌표필드`) → 카테고리. 모르면 `None`."""
    f = fields.get(str(name).lstrip("@")) or {}
    return f.get("category") or f.get("target_category")


def _walk(obj, path):
    """경로가 가리키는 `(표시경로, 값)` 목록. **없는 자리는 건너뛴다**(형 검사다)."""
    if not path:
        return [("", obj)]
    head, _, rest = path.partition(".")
    out = []
    if head == "*":
        for k, v in (obj or {}).items() if isinstance(obj, dict) else []:
            out += [(f"{k}" + ("." + p if p else ""), x) for p, x in _walk(v, rest)]
        return out
    if head.endswith("[]"):
        key = head[:-2]
        seq = (obj or {}).get(key) if isinstance(obj, dict) else None
        if key and not isinstance(seq, list):
            return []
        for i, v in enumerate(seq or []):
            out += [(f"{key}[{i}]" + ("." + p if p else ""), x)
                    for p, x in _walk(v, rest)]
        return out
    if not isinstance(obj, dict) or head not in obj:
        return []
    return [(head + ("." + p if p else ""), x) for p, x in _walk(obj[head], rest)]


def _type_name(v):
    return type(v).__name__


def _shape_ok(v, want):
    if want == "str":
        return isinstance(v, str)
    if want == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if want == "str[]":
        return isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v)
    if want == "str|str[]":
        return _shape_ok(v, "str") or _shape_ok(v, "str[]")
    return True


def check_shapes(schema, mod):
    """**G4F — 키마다 허용 형** (B76 ①). 형이 다르면 FAIL, 표 밖의 키는 보고한다."""
    A = getattr(mod, "ADAPTER", {}) if mod is not None else {}
    bad, extra = [], []
    for obj, table, enums in ((schema or {}, SHAPE_SCHEMA, SHAPE_SCHEMA_ENUM),
                              (A, SHAPE_ADAPTER, {})):
        for path, want in table.items():
            for shown, v in _walk(obj, path):
                if v is None:
                    continue
                if not _shape_ok(v, want):
                    bad.append(f"{shown} — 받은 형 {_type_name(v)} · 허용 {want} · "
                               f"값 {str(v)[:60]}")
                    continue
                allowed = enums.get(path)
                if allowed and v not in allowed:
                    bad.append(f"{shown} — 받은 값 {str(v)[:60]} · "
                               f"허용 {list(allowed)}")
    extra += [f"스키마.{k}" for k in (schema or {}) if k not in SHAPE_KNOWN_SCHEMA]
    extra += [f"ADAPTER.{k}" for k in A if k not in SHAPE_KNOWN_ADAPTER]
    show("G4F  LLM 산출의 키마다 허용 형 (닫힌 표 — 06 대장 1.5)",
         not bad, " ‖ ".join(bad))
    if extra:
        # **판정이 아니라 보고다** — 모양이 늘었다는 사실은 사람이 볼 것이고,
        # 표에 없다는 이유로 막으면 명세가 자라는 길이 막힌다.
        print(f"      [모양] 표에 없는 키 {len(extra)}종 — {', '.join(extra[:8])}")
    return not bad


def check_ledger_coverage(schema, mod):
    """**G4G — 스키마 `fields` 전부에 대장 행이 있는가** (B76 ②).

    대장(B67)은 열 프로파일로만 세워져, 어댑터가 쓰는 열이 프로파일 밖이면
    **스키마에 있어도 행이 없는 필드**가 생겼다. 그 필드는 기계 제안 대조와
    「이어가기」에서 빠진다 — 사람이 판정한 것이 아니라 **기계가 빠뜨린 것**이라
    질문이 아니라 FAIL이다(사내 실측 열다섯째의 둘째 원인).

    대장 경로가 없으면 대상이 아니다(킷 단독 실행).
    """
    if not tables.LEDGER or not Path(tables.LEDGER).exists():
        return True
    try:
        rows = json.load(open(tables.LEDGER, encoding="utf-8"))
        # 대장 파일의 실물 키는 `columns`다(등록이 쓰는 꼴) — 목록으로 주는
        # 호출도 받는다(킷을 단독으로 쓰는 자리).
        if isinstance(rows, dict):
            rows = rows.get("columns") or rows.get("rows") or []
    except Exception as e:
        return show("G4G  열 판정 대장이 스키마 필드 전부를 덮는다",
                    False, f"대장을 읽지 못했다 — {type(e).__name__}: {e}")
    fields, _blocks = load_blocks(schema)
    if not fields:
        return True
    have = {r.get("field") for r in (rows or []) if r.get("field")}
    cols = (getattr(mod, "ADAPTER", {}).get("expects") or {}).get("columns") or {}
    struct = structural_fields()
    miss = [f for f in sorted(fields) if f not in have and f not in struct]
    det = " ‖ ".join(
        f"대장에 없는 필드 {f} — 어댑터 columns {cols.get(f)!r} · 프로파일 밖"
        for f in miss)
    return show("G4G  열 판정 대장이 스키마 필드 전부를 덮는다", not miss, det)


def check_vocab(schema, fields, label):
    """**어휘가 닫힌 자리를 등록 시점에 대조한다** (B65 ② · 칸 1.5).

    커밋 게이트(3.6)가 인입 때 같은 것을 거르지만, 그때는 문서가 이미 들어가는
    중이고 사람은 `gate_rejects.json`을 열어야 안다. **여기서 걸러야 등록이 끝나기
    전에 고친다** — 문면이 「있는 것」을 담으므로 자동 재생성이 목록 안에서 고른다.
    """
    layer = schema.get("layer")
    voc = _vocab(layer)
    if not voc.get("categories"):
        # **한 태그·한 라벨**(B59 ①) — 층 어휘를 못 읽은 것도 이 판정의 한 원인이다.
        return show("G4C  전 필드의 category가 층 목록 안", False,
                    f"층 어휘를 못 읽었다 — layers/{layer}/config.json도 패키지도 "
                    f"어휘를 주지 않는다(층 이름이 틀렸거나 층이 없다)")
    cats, rels = voc.get("categories") or {}, voc.get("relations") or {}
    pats = voc.get("relation_patterns") or []

    # G4C — category는 **그 층이 말하는 카테고리** 안이다.
    #
    # 「그 층이 말하는 것」 = 자기 `categories` + **패턴표가 이름 붙인 카테고리**다.
    # 층은 제 패턴표에서 다른 층의 카테고리를 부른다(quality의 `Failure occurs_in
    # Process`) — 좌표 블록의 `target_category`가 그 자리다. 패턴표에 없는 이름만
    # 걸리므로 오타(`Proces`)는 그대로 잡힌다. 걸침 필드(`target_layer`)는 그 층의
    # 목록으로 본다 — 사람이 층을 지정했으면 그 층이 정본이다.
    spoken = set(cats) | {p.get(k) for p in pats for k in ("src", "dst") if p.get(k)}
    bad_c = []
    for name, f in fields.items():
        for key in ("category", "target_category"):
            v = f.get(key)
            if not v:
                continue
            tl = f.get("target_layer")
            own = set(_vocab(tl).get("categories") or {}) if tl else spoken
            if v not in own:
                bad_c.append(f"{name}.{key}={v!r}는 {tl or layer} 카테고리에 없다 · "
                             f"있는 것: {' · '.join(sorted(own)) or '(어휘 없음)'}")
    show("G4C  전 필드의 category가 층 목록 안", not bad_c, " ‖ ".join(bad_c))

    edges = schema.get("edges", []) or []
    # G4D — relation은 층 관계 목록 안이다.
    bad_r = [f"{e.get('relation')!r}는 {layer} 관계에 없다 · "
             f"있는 것: {' · '.join(sorted(rels))}"
             for e in edges if e.get("relation") not in rels]
    show("G4D  전 edges의 relation이 층 목록 안", not bad_r, " ‖ ".join(sorted(set(bad_r))))

    # G4E — 삼항이 패턴표 안이다. 카테고리를 모르는 쪽은 대조하지 않는다(모르면
    # 묻지 않고 넘긴다 — G47·G48이 그 자리를 이미 본다).
    ok_tri = {(p.get("src"), p.get("rel"), p.get("dst")) for p in pats}
    bad_t = []
    for e in edges:
        src, dst = _cat_of(fields, e.get("from")), _cat_of(fields, e.get("to"))
        rel = e.get("relation")
        if not (src and dst and rel in rels):
            continue
        if (src, rel, dst) not in ok_tri:
            allow = [f"{p['src']} → {p['dst']}" for p in pats if p.get("rel") == rel]
            bad_t.append(f"({src}, {rel}, {dst})는 패턴표에 없다 · "
                         f"{rel}의 허용: {' · '.join(allow) or '(없음)'}")
    show("G4E  전 edges의 삼항이 relation_patterns 안", not bad_t, " ‖ ".join(bad_t))
    return not (bad_c or bad_r or bad_t)


def check_schema(schema, pieces, label, payload_kind=None):
    print(f"\n④ 매칭 스키마 정합 — {label}")
    show("G41  헤더 4키 (doc_type·schema_version·layer·use_blocks)",
         {"doc_type", "schema_version", "layer"} <= set(schema))
    declared = schema.get("fields", {})
    # **공용 블록을 전개해 합친다**(§4.4 처방) — 좌표를 블록에 위임한 스키마도
    # anchor 경로가 드라이런된다. `fields` 판정(D-31)은 **스키마 선언분**으로 한다:
    # 블록은 스키마가 쓴 것이 아니라 참조한 것이므로 prose의 `{}` 정답을 흔들면 안 된다.
    fields, block_fields = load_blocks(schema)
    struct = STRUCT_ONLY | block_fields
    if block_fields:
        show(f"G42  use_blocks 전개 — {schema.get('use_blocks')} → 필드 {len(block_fields)}종 합류",
             True, str(sorted(block_fields)))
    # **fields의 정답은 payload_kind가 정한다** [D-31 확정 — 카드 C17 · CH2 2.5/2.6].
    # prose 조각의 고정 키 4종(text·section·meta·image_ref)은 **payload 구조 필드**라
    # role 배정 대상이 아니고, 그래서 prose 매칭 스키마의 fields는 `{}`가 정답이다 —
    # 층·블록 선언이 계약의 전부다. 구판은 이 정답을 FAIL로 찍었다(3차 로그의 유일한 FAIL).
    if payload_kind == "prose":
        show("G43  prose 스키마의 fields는 비어 있음 (D-31 — 고정 키는 payload 구조 필드)",
             not declared, f"{len(declared)}개")
    elif payload_kind == "table":
        show("G44  table 스키마의 fields 선언 존재", bool(declared), f"{len(declared)}개")
    else:
        show("G45  payload_kind가 스키마 또는 어댑터에 선언됨 (fields 판정의 전제)",
             False, str(payload_kind))
    badrole = {k: v.get("role") for k, v in fields.items() if v.get("role") not in ROLES}
    show("G46  전 필드의 role이 닫힌 5종 안", not badrole, str(badrole))
    noecat = [k for k, v in fields.items() if v.get("role") == "entity" and not v.get("category")]
    show("G47  entity 필드에 category 필수", not noecat, str(noecat))
    # edges 참조 무결성
    edges = schema.get("edges", [])
    refs = set()
    for e in edges:
        for side in ("from", "to"):
            t = str(e.get(side, ""))
            refs.add(t[1:] if t.startswith("@") else t)
    # **`attach_to_field`도 같은 꼴의 참조다**(B65 ② — 태그 신설 0): 선언되지 않은
    # 필드를 가리키면 부착이 조용히 사라진다. from/to와 한 줄로 본다.
    refs |= {str(v.get("attach_to_field")) for v in fields.values()
             if v.get("attach_to_field")}
    unknown = sorted(r for r in refs if r and r not in fields and r not in struct)
    # **라벨을 바꾸지 않는다** — 봉인 로그가 이 이름으로 판정을 보증한다(D-26 · B59).
    # 넓어진 범위(`attach_to_field`)는 상세가 말한다: 이름이 바뀌면 봉인은 그 판정이
    # **사라졌다**고 말하고, 그것은 거짓이다.
    show(f"G48  edges {len(edges)}건의 from/to가 전부 선언된 필드",
         not unknown, str(unknown) + " (attach_to_field 포함)")
    check_vocab(schema, fields, label)
    # 조각 ↔ 스키마 대조 (인입 검증 ③단계의 드라이런)
    if pieces:
        piece_keys = set().union(*[set(p) for p in pieces])
        unknown_field = sorted(piece_keys - set(fields) - struct
                               - {"text", "section", "meta", "image_ref"})
        show("G49  파서 출력에 스키마 밖 필드 없음 (unknown_field 큐 예상분)",
             not unknown_field, str(unknown_field))
        missing = sorted(k for k, v in fields.items()
                         if not v.get("optional") and k not in struct
                         and not any(p.get(k) not in (None, "") for p in pieces))
        show("G4A  필수 필드가 조각에 실제로 채워짐 (missing_field 큐 예상분)",
             not missing, str(missing))
    # role 루프 드라이런 — 핸들러 분기가 전부 도는가
    HANDLED = {r: 0 for r in ROLES}
    unmapped_in_fields = [k for k, v in fields.items() if v.get("role") == "UNMAPPABLE"]
    show("G4B  UNMAPPABLE 필드가 스키마 fields에 들어가지 않음 (등록 제외 대상)",
         not unmapped_in_fields, str(unmapped_in_fields))
    for p in (pieces or []):
        for k, spec in fields.items():
            if k in p and p[k] is not None and spec.get("role") in HANDLED:
                HANDLED[spec["role"]] += 1
    print(f"      role 루프 드라이런: " +
          " · ".join(f"{r}={HANDLED[r]}" for r in ["anchor", "entity", "attribute", "content", "meta"]))
    return True
