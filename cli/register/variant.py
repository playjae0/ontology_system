# -*- coding: utf-8 -*-
"""칸 1.1·1.7 — **변형 등록**(B190 · 문서 6 §6.5 — 스키마 1 + 어댑터 N): 같은 종류의 다른 양식은 **같은 doc_type에 어댑터를 더한다**.

    python -m cli.register generate <dt> <층> <표본…> --variant [이름]   → 검수 자리 review/<dt>@<이름>/
    python -m cli.register confirm <dt>@<이름> --by <승인자>              → 등록부 <dt> 항목의 variants에 더한다

**스키마는 고정 입력이다** — 등록된 그 doc_type의 매칭 스키마를 바이트 그대로 쓰고 LLM은 어댑터만 쓴다(가장 가까운 변형의
어댑터 전문이 생성 입력 — B37 차분). 초안의 스키마가 병합 키(fields 키 · role · attr_name · category)에서 다르면 **쓰지 않고
「판정 불가」로 멈춘다**(§6.5-1 — 그것은 변형이 아니라 doc_type의 변경이다). 검수 · 승인은 변형마다(§6.5-2) · 고르는 것은 지문(§6.5-3 —
`cli/ingest_select.py`) · 이름 · 자리 규칙은 등록부(`core/state/registry.py` — `BASE_VARIANT` · `variant_adapter`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core import paths
from core.state import registry, store
from cli.register import REVIEW, _load, write_file


def work(doc_type, name):
    """검수 자리 이름 — `<doc_type>@<변형>`(사람이 `confirm` · `status`에 치는 이름이기도 하다)."""
    return f"{doc_type}{registry.VARIANT_SEP}{name}"


def split(name):
    """검수 자리 이름 → `(doc_type, 변형)` · 변형이 아니면 `(name, None)`."""
    dt, sep, v = str(name).partition(registry.VARIANT_SEP)
    return (dt, v) if sep and v else (name, None)


def default_name(samples):
    """이름을 주지 않으면 첫 표본의 파일 이름(확장자 뺌) — `@` · 빈칸은 `_`로."""
    stem = Path(str(samples[0])).stem if samples else "새양식"
    return re.sub(r"[\s@/\\]+", "_", stem).strip("_") or "새양식"


def _refuse(doc_type, why, layer, samples):
    raise SystemExit(f"[생성] --variant는 **등록된 표 doc_type**에만 쓴다 — '{doc_type}' {why}\n"            # [상태]
                     f"  근거 — {store.path(store.DOC_TYPES)}\n"
                     f"  ▶ 다음 줄 — 그 종류를 처음 등록한다:\n"
                     f"     python -m cli.register generate {doc_type} {layer or '<층>'} "
                     f"{' '.join(str(s) for s in samples) or '<표본...>'}")


def nearest(doc_type, sample):
    """그 doc_type의 변형 중 표본 헤더와 가장 가까운 것 `(이름, 실물 자리, 누락+잉여)` — 지문 대조와 같은 연산(`cli.scan.match_detail`)."""
    from cli import scan as scan_mod
    from parser.reader import read
    raw = read(str(sample))
    best = None
    for name, v in registry.variants_of(doc_type):
        p = registry.at(v["adapter"])
        d = scan_mod.match_detail(raw, scan_mod._load(p)) if p.exists() else {}
        cost = len(d.get("missing") or []) + len(d.get("extra") or []) if d.get("eligible") else 10 ** 6
        if best is None or cost < best[2]:
            best = (name, p, cost)
    return best


def prepare(doc_type, layer, samples, name=None):
    """`--variant`의 입구 — 등록된 표 doc_type인가 · 이름 · 층 · 가장 가까운 변형. 돌려주는 것은 패키지 `human.hint.variant`의 재료."""
    entry = (store.read(store.DOC_TYPES, {}) or {}).get(doc_type)
    if not entry:
        _refuse(doc_type, "내장(mock 자산)이라 등록부에 어댑터가 없다" if registry.lookup(doc_type)
                else "은 등록돼 있지 않다", layer, samples)
    schema = registry.schema_path(doc_type)
    sc = json.loads(schema.read_text(encoding="utf-8")) if schema and schema.exists() else {}
    if sc.get("payload_kind") == "prose" or not entry.get("adapter"):
        _refuse(doc_type, "은 산문(고정 어댑터)이다 — 산문은 헤더 지문이 없어 변형을 고르지 않는다(--as <새이름>)",
                layer, samples)
    name = name or default_name(samples)
    if name == registry.BASE_VARIANT or registry.VARIANT_SEP in name:
        raise SystemExit(f"[생성] 변형 이름 '{name}'은 쓸 수 없다 — '{registry.BASE_VARIANT}'은 지금 등록분의 이름이다 · "  # [사용법]
                         f"'{registry.VARIANT_SEP}' 없이\n"
                         f"  ▶ 다음 줄: python -m cli.register generate {doc_type} {entry.get('layer')} <표본...> --variant <이름>")
    if layer and layer != entry.get("layer"):
        print(f"   ※ 층 '{layer}'는 쓰지 않는다 — 변형은 그 doc_type의 층 '{entry.get('layer')}' 그대로다")
    nm, ad, cost = nearest(doc_type, samples[0]) if samples else (registry.BASE_VARIANT, registry.at(entry["adapter"]), 0)
    known = dict(registry.variants_of(doc_type))
    from cli.register import draft as draft_mod
    print(f"  ▶ 같은 종류의 다른 양식 — '{doc_type}'의 스키마는 그대로(바이트) · 어댑터만 새로 · 변형 '{name}'"
          + (" (이미 있다 — 확정하면 그 변형의 새 판)" if name in known else ""))
    print(f"    가장 가까운 변형 '{nm}'(헤더 누락+잉여 {cost if cost < 10 ** 6 else '—'})의 어댑터 전문이 생성 입력이다 · "
          f"작업 자리 {paths.show(REVIEW / work(doc_type, name))}")
    return {"doc_type": doc_type, "name": name, "work": work(doc_type, name), "layer": entry.get("layer"),
            "schema": str(draft_mod._rel(schema)), "nearest": {"name": nm, "adapter": str(draft_mod._rel(ad))}}


def of(name):
    """검수 자리의 변형 재료(`human.hint.variant`) 또는 None — 초안 · 관문 · 확정 · 지시문이 이 한 함수로 묻는다."""
    try:
        pkg = json.loads((REVIEW / name / "input_package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    hint = (pkg.get("human") or {}).get("hint")
    v = hint.get("variant") if isinstance(hint, dict) else None
    return v if isinstance(v, dict) and v.get("doc_type") else None


def identity(schema):
    """**병합 키** — `{필드: (role, attr_name, category)}`(§6.5 — 이것이 같으면 같은 doc_type이다)."""
    return {k: (f.get("role"), f.get("attr_name"), f.get("category"))
            for k, f in ((schema or {}).get("fields") or {}).items()}


def schema_diff(fixed, proposed):
    """스키마 정합(§6.5-1 · 하네스 ④의 자리) — 병합 키가 다른 줄 `[글]` · 같으면 빈 목록."""
    a, b = identity(fixed), identity(proposed)
    out = [f"+ 필드 {k}" for k in sorted(set(b) - set(a))] + [f"- 필드 {k}" for k in sorted(set(a) - set(b))]
    out += [f"~ 필드 {k} — (role, attr_name, category) {a[k]} → {b[k]}" for k in sorted(set(a) & set(b)) if a[k] != b[k]]
    return out


def settle(name, adapter, proposed_schema):
    """초안을 받은 뒤 — 초안의 스키마가 병합 키에서 등록 스키마와 다르면 **판정 불가**로 멈춘다(쓰지 않는다) · 같으면 등록 스키마를
    **바이트 그대로** 검수 자리에 두고 `(어댑터, 그 스키마)`를 돌려준다(스키마 문면이 달라도 등록 판이 정본이다)."""
    v = of(name)
    from cli.register import draft as draft_mod
    fixed_p = draft_mod._at(v["schema"])
    fixed = json.loads(fixed_p.read_text(encoding="utf-8"))
    if proposed_schema is not None and Path(proposed_schema).exists():
        try:
            prop = json.loads(Path(proposed_schema).read_text(encoding="utf-8"))
        except ValueError:
            prop = {}
        diff = schema_diff(fixed, prop)
        if diff:
            raise SystemExit(                                                                               # [상태]
                f"[생성] 판정 불가 — '{v['doc_type']}'의 스키마를 바꿔야 맞는 양식이다 · 초안을 쓰지 않았다"
                f"(변형은 스키마를 그대로 쓴다 — 병합 키가 갈리면 doc_type의 변경이다 · 문서 6 §6.5-1)\n"
                + "".join(f"  {d}\n" for d in diff[:8]) + (f"  … 외 {len(diff) - 8}줄\n" if len(diff) > 8 else "")
                + f"  근거 — 등록 스키마 {paths.show(fixed_p)} ↔ 초안 {paths.show(proposed_schema)}\n"
                f"  ▶ 다음 줄 — 사람이 정한다:\n"
                f"     (다른 종류의 문서다 — 새 doc_type)  python -m cli.register generate {v['doc_type']} {v['layer']} "
                f"<표본...> --as <새이름>\n"
                f"     (이 종류의 스키마를 바꾼다 — 이미 넣은 문서와 병합 키가 갈린다)  "
                f"python -m cli.register generate {v['doc_type']} {v['layer']} <표본...> --schema-only")
    dst = REVIEW / name / "schema.json"
    write_file(dst, fixed_p.read_bytes())
    return adapter, dst


def notes(name, st, samples):
    """관문 화면의 한 줄(가결정 D-274) — **이 양식에 없는 필드**(그 문서에서는 비어 들어온다) · **스키마 밖 열**(읽지 않는다 ·
    스키마는 그대로). 변형이 아니면 None."""
    if not of(name):
        return None
    from cli.register import draft as draft_mod
    from parser.reader import read
    from parser import preflight
    try:
        mod = _load(draft_mod._at(st["adapter"]), f"variant_{name}")
        fields = set((json.loads(draft_mod._at(st["schema"]).read_text(encoding="utf-8")).get("fields") or {}))
        exp = mod.ADAPTER.get("expects") or {}
        cols = exp.get("columns") or {}
        labels = preflight.header_labels(read(str(samples[0])), exp.get("header_row")) if samples else []
    except Exception:
        return None
    from parser.normalizer import _col
    used = {str(c) for c in cols.values()}
    absent = sorted(fields - set(cols))
    extra = [lab for i, lab in enumerate(labels, 1) if lab and _col(i) not in used]
    return (f"   변형 열 대조 — 스키마 필드 {len(fields)} 중 이 양식이 읽는 것 {len(fields & set(cols))} · "
            f"이 양식에 없는 필드 {len(absent)}" + (f" {absent} — 그 문서에서는 값이 비어 들어온다" if absent else "") + " · "
            f"스키마 밖 열 {len(extra)}" + (f" {extra} — 읽지 않는다(스키마는 그대로 · 살리려면 doc_type의 변경)" if extra else ""))


def gate_all(doc_type, schema_path, skip=()):
    """그 doc_type의 변형마다 운영 어댑터 + `schema_path`로 하네스 — `[(이름, ok, 표본 수, out)]`(표본은 그 변형 검수 자리의 것).
    `status <dt>` · 스키마만 새 판의 확정이 부른다(§6.5-1 — 스키마는 전 변형이 공유한다)."""
    from cli.register import gate
    from cli.register import _state
    out = []
    for name, v in registry.variants_of(doc_type):
        if name in skip:
            continue
        w = doc_type if name == registry.BASE_VARIANT else work(doc_type, name)
        smp = (_state(w) or {}).get("samples") or []
        ok, txt = gate.harness(registry.at(v["adapter"]), schema_path, smp,
                               package=REVIEW / w / "input_package.json", doc_type=w)
        out.append((name, ok, len(smp), txt))
    return out


def confirm(name, st, approved_by, mod, at):
    """③ 확정(변형) — 스키마 바이트가 등록 판과 같은지 다시 보고 · 어댑터를 `adapters/<dt>@<이름>.py`로 · 등록부 그 항목에 더한다."""
    from cli.register import draft as draft_mod
    v = of(name)
    dt, vname = v["doc_type"], v["name"]
    reg_sc = registry.schema_path(dt)
    if not reg_sc or draft_mod._at(st["schema"]).read_bytes() != reg_sc.read_bytes():
        raise SystemExit(f"[확정] 판정 불가 — 작업 자리의 스키마가 '{dt}'의 등록 스키마와 바이트가 다르다(변형은 스키마를 바꾸지 않는다)\n"  # [상태]
                         f"  근거 — {paths.show(draft_mod._at(st['schema']))} ↔ {paths.show(reg_sc) if reg_sc else '등록 스키마 없음'}\n"
                         f"  ▶ 다음 줄 — 변형을 다시 만든다: python -m cli.register generate {dt} {v['layer']} <표본...> "
                         f"--variant {vname}")
    rel = registry.variant_adapter(dt, vname)
    entry = registry.add_variant(dt, vname, adapter=rel, adapter_version=mod.ADAPTER.get("adapter_version"),
                                 approved_by=approved_by, approved_at=at, instructions=st.get("instructions") or [])
    dst = paths.registry() / rel
    paths.ensure(dst)
    write_file(dst, draft_mod._at(st["adapter"]).read_bytes())      # 등재가 성립한 뒤에만 옮긴다(기본 확정과 같은 차례)
    ap = REVIEW / name / "approval.json"
    prev = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else None
    write_file(ap, json.dumps({"doc_type": dt, "variant": vname, "adapter_version": mod.ADAPTER.get("adapter_version"),
                               "승인자": approved_by, "시점": at, "revision": entry["revision"],
                               "수정 지시 이력": st.get("instructions") or [],
                               **({"이전 승인": ((prev or {}).pop("이전 승인", None) or []) + [prev]} if prev else {})},
                              ensure_ascii=False, indent=2) + "\n")
    print(f"■ ③ 확정 — {dt} **변형 '{vname}' 등재** (revision {entry['revision']} · 승인 {approved_by} @ {at})")
    print(f"   어댑터 {rel} · 스키마 그대로 {paths.show(reg_sc)} · 이 doc_type의 변형 "
          f"{len(registry.variants_of(dt))}({' · '.join(n for n, _ in registry.variants_of(dt))})")
    print(f"   승인 기록 → {paths.show(ap)}")
    print("   다음 — 인입 (지문이 변형을 고른다):")
    print(f"     python run.py ingest-file <문서> --dry-run   ← 선택 근거에 「변형 {vname}」")
    print(f"     python run.py ingest-file <문서> --doc-type {dt}")
    return 0
