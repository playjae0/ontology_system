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
    inh = {**inherit(doc_type), "decisions": _decisions(doc_type)}
    if inh["blind"]:
        print(f"    ※ 헤더 대응을 셀 수 없는 변형 {inh['blind']} — 물려받는 몫 0(expects.header_labels · columns가 없다)")
    return {"doc_type": doc_type, "name": name, "work": work(doc_type, name), "layer": entry.get("layer"),
            "schema": str(draft_mod._rel(schema)), "nearest": {"name": nm, "adapter": str(draft_mod._rel(ad))},
            "inherit": inh}


def pairs(adapter_path):
    """어댑터 하나의 `(원본 헤더 차례, {헤더: 필드})` — `expects.header_labels`(A열부터) × `columns`({필드: 열문자}) · 셀 수 없으면 None."""
    from parser.normalizer import _col
    from parser.reader import norm_label
    try:
        exp = _load(Path(adapter_path), f"pairs_{Path(adapter_path).stem}").ADAPTER.get("expects") or {}
    except Exception:
        return None
    labels, cols = exp.get("header_labels"), exp.get("columns")
    if not isinstance(labels, list) or not isinstance(cols, dict):
        return None
    at = {str(c): f for f, c in cols.items()}
    hs = [norm_label(h) for h in labels]
    return hs, {h: at[_col(i)] for i, h in enumerate(hs, 1) if h and _col(i) in at}


def inherit(doc_type):
    """**물려받는 대응**(B213 ②) — 등록된 변형 전부의 「헤더 → 필드」 합 · 같은 헤더가 변형마다 다른 필드면 고르지 않고 `conflicts`."""
    seen, names, blind = {}, [], []
    for name, v in registry.variants_of(doc_type):
        names.append(name)
        pr = pairs(registry.at(v["adapter"]))
        if pr is None:
            blind.append(name)
            continue
        for h in filter(None, pr[0]):                      # 읽지 않는 헤더는 「」(읽지 않음)로 · 다른 변형이 읽으면 그쪽
            seen.setdefault(h, {}).setdefault(pr[1].get(h, ""), []).append(name)
    seen = {h: ({f: ns for f, ns in fs.items() if f} or fs) for h, fs in seen.items()}
    one = {h: next(iter(fs.items())) for h, fs in seen.items() if len(fs) == 1}
    return {"from": names, "blind": blind, "headers": {h: f for h, (f, _n) in one.items()},
            "at": {h: ns for h, (_f, ns) in one.items()}, "conflicts": {h: fs for h, fs in seen.items() if len(fs) > 1}}


def _decisions(doc_type):
    """그 doc_type의 작업 자리 전부(기본 · 변형)의 확정 문답 — stale · 버린 문답은 뺀다(B213 ③)."""
    from cli.register import interview as ivlog
    return [d for name, _v in registry.variants_of(doc_type)
            for b in ivlog.prior_interview(REVIEW / (doc_type if name == registry.BASE_VARIANT else work(doc_type, name))
                                           / "input_package.json")
            if not b.get("stale") and not b.get("dropped") for d in (b.get("decisions") or [])]


def _told(st):
    """사람이 지시(`--instruct` · 문답)로 부른 글 — 그 안에 이름이 나온 헤더 · 필드는 잠금에서 뺀다(자동 지시는 세지 않는다)."""
    return " ".join(str(i.get("instruction") or "") for i in (st or {}).get("instructions") or []
                    if str(i.get("by") or "").startswith("사람"))


def match(name, adapter_path, st=None):
    """**헤더 4갈래**(B213 ②) — 물려받은 대응 × 초안 어댑터의 대응(결정적). 「이름 바뀜」은 물려받은 쪽에서 빠진 헤더가 가던 필드로
    초안이 새 헤더를 읽은 짝 · 충돌은 변형마다 다른 필드로 확정된 헤더 · 사람이 지시로 부른 헤더는 `told`."""
    inh = (of(name) or {}).get("inherit") or {}
    H, C = inh.get("headers") or {}, inh.get("conflicts") or {}
    labels, D = pairs(adapter_path) or ([], {})
    labels = [h for h in labels if h]
    kept = {D.get(h) for h in labels if h in H}
    gone = {H[h]: h for h in H if h not in labels and H[h] and H[h] not in kept}
    rest = [h for h in labels if h not in H and h not in C]
    ren = [(h, gone[D[h]]) for h in rest if D.get(h) in gone]
    told = _told(st)
    return {"from": inh.get("from") or [], "same": [h for h in labels if h in H], "renamed": ren,
            "new": [h for h in rest if h not in dict(ren)], "gone": [h for f, h in gone.items() if f not in {D[a] for a, _ in ren}],
            "conflict": [h for h in labels if h in C], "H": H, "C": C, "D": D, "at": inh.get("at") or {},
            "told": {h for h in labels if h in told}}


def table(name, m):
    """매칭표 줄 — `generate --variant` · `review <dt>@<이름>` · `status`가 관문 화면에서 같은 함수로."""
    dt, vn = split(name)
    mark = lambda h: " (지시로 바꿈)" if h in m["told"] else ""                          # noqa: E731
    out = [f"   헤더 매칭 — {dt} · 새 양식 {vn} (물려받은 변형 {len(m['from'])}: {' · '.join(m['from'])})",
           f"     같은 헤더 {len(m['same'])}   물려받음(묻지 않음 · 잠금): "
           + " · ".join(f"{h}→{m['H'][h] or '읽지 않음'}{mark(h)}" for h in m["same"]),
           f"     이름 바뀜 {len(m['renamed'])}   " + " · ".join(f"{h} → {o}" for h, o in m["renamed"])
           + ("   (초안이 낸 짝 — 사람이 확정)" if m["renamed"] else ""),
           f"     새 헤더   {len(m['new'])}   " + " · ".join(f"{h} → {m['D'].get(h) or '읽지 않음'}" for h in m["new"])
           + ("   (그래프에 넣으려면 --instruct \"'<헤더>'를 <role>로 더한다\")" if m["new"] else ""),
           f"     사라짐    {len(m['gone'])}   " + " · ".join(m["gone"]),
           f"     충돌      {len(m['conflict'])}   " + " · ".join(
               f"{h} — " + " · ".join(f"{f}({'·'.join(ns)})" for f, ns in m["C"][h].items()) + mark(h) for h in m["conflict"])
           + ("   (확정 전에 사람이 고른다 — --instruct로 그 헤더를)" if m["conflict"] else "")]
    return [ln.rstrip() for ln in out]


def lock(name, st, ok, out):
    """**G4V 잠금**(B213 ③) — 물려받은 헤더를 초안이 다른 필드로 읽으면 FAIL(사람이 지시로 부른 헤더는 뺀다) · `(ok, out)`."""
    if not (of(name) or {}).get("inherit"):
        return ok, out
    from cli.register import draft as draft_mod
    m = match(name, draft_mod._at(st["adapter"]), st)
    bad = [h for h in m["same"] if m["D"].get(h, "") != m["H"][h] and h not in m["told"]]
    det = " ‖ ".join(f"'{h}'는 {'·'.join(m['at'].get(h) or m['from'])}에서 '{m['H'][h] or '읽지 않음'}'로 확정 — 초안은 '{m['D'].get(h) or '읽지 않음'}' · "
                     f"바꾸려면 --instruct로 그 까닭을" for h in bad)
    line = (f"  [{'FAIL' if bad else 'PASS'}] G4V  물려받은 헤더는 확정된 필드 그대로  — "
            + (det or f"같은 헤더 {len(m['same'])} · 지시로 바꿈 {len(m['told'] & set(m['same']))}"))
    return ok and not bad, out.rstrip("\n") + "\n" + line + "\n"


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


def added(fixed, prop, history=None, adapter=None):
    """**칸 더하기**(B213 ④) — 초안이 등록 스키마의 기존 칸을 그대로(필드 정의 같음) 두고 새 칸만 더했고 그 칸(필드 키 · 그 칸의
    원본 헤더)을 사람이 지시로 불렀으면 `{새 필드: 정의}` · 아니면 None(판정 불가 — 지금 그대로)."""
    a, b = (fixed or {}).get("fields") or {}, (prop or {}).get("fields") or {}
    new = {k: b[k] for k in b if k not in a}
    if not new or any(b.get(k) != a[k] for k in a):
        return None
    told = _told({"instructions": history})
    head = {f: h for h, f in ((pairs(adapter) or ([], {}))[1]).items()} if adapter else {}
    return new if all(k in told or (head.get(k) and head[k] in told) for k in new) else None


def settle(name, adapter, proposed_schema, history=None):
    """초안을 받은 뒤 — 초안의 스키마가 병합 키에서 등록 스키마와 다르면 **판정 불가**로 멈춘다(쓰지 않는다) · 같으면 등록 스키마를
    **바이트 그대로** 검수 자리에 두고 `(어댑터, 그 스키마)`를 돌려준다(스키마 문면이 달라도 등록 판이 정본이다) · 사람이 지시한
    새 칸만 더했으면 등록 스키마 + 그 칸(`schema_version` + 1 — 확정이 모든 변형을 다시 관문에 · B213 ④)."""
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
        add = added(fixed, prop, history, adapter) if diff else None
        if add:
            out = {**fixed, "schema_version": int(fixed.get("schema_version") or 1) + 1,
                   "fields": {**fixed["fields"], **add}}
            print(f"   칸 더하기 — 등록 스키마 + {sorted(add)} (기존 칸 그대로 · schema_version {out['schema_version']}) — "
                  f"확정이 이 doc_type의 모든 변형을 새 스키마로 다시 관문에 세운다")
            dst = REVIEW / name / "schema.json"
            write_file(dst, json.dumps(out, ensure_ascii=False, indent=2) + "\n")
            return adapter, dst
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
    tb = "\n".join(table(name, match(name, draft_mod._at(st["adapter"]), st))) + "\n" if of(name).get("inherit") else ""
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
    return tb + (f"   변형 열 대조 — 스키마 필드 {len(fields)} 중 이 양식이 읽는 것 {len(fields & set(cols))} · "
            f"이 양식에 없는 필드 {len(absent)}" + (f" {absent} — 그 문서에서는 값이 비어 들어온다" if absent else "") + " · "
            f"스키마 밖 열 {len(extra)}" + (f" {extra} — 읽지 않는다(스키마는 그대로 · 더하려면 --instruct)" if extra else ""))


def gate_all(doc_type, schema_path, skip=(), ledger=True):
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
                               package=REVIEW / w / "input_package.json", doc_type=w if ledger else None)
        out.append((name, ok, len(smp), txt))
    return out


def confirm(name, st, approved_by, mod, at):
    """③ 확정(변형) — 스키마 바이트가 등록 판과 같은지 다시 보고 · 어댑터를 `adapters/<dt>@<이름>.py`로 · 등록부 그 항목에 더한다."""
    from cli.register import draft as draft_mod
    v = of(name)
    dt, vname = v["doc_type"], v["name"]
    reg_sc = registry.schema_path(dt)
    m = match(name, draft_mod._at(st["adapter"]), st)
    open_c = [h for h in m["conflict"] if h not in m["told"]]
    if open_c:
        print(f"■ 확정 멈춤 — 헤더 충돌 {len(open_c)} {open_c}: 변형마다 다른 필드로 확정돼 있다 — 사람이 고른다")
        for h in open_c:
            print(f"     {h} — " + " · ".join(f"{f}({'·'.join(ns)})" for f, ns in m["C"][h].items()))
        print(f"  ▶ 다음 줄: python -m cli.register review {name} --instruct \"'{open_c[0]}'는 <필드>로 읽는다\"")
        return 1
    mine = json.loads(draft_mod._at(st["schema"]).read_text(encoding="utf-8"))
    add = added(json.loads(reg_sc.read_text(encoding="utf-8")), mine, st.get("instructions"), draft_mod._at(st["adapter"])) \
        if reg_sc and draft_mod._at(st["schema"]).read_bytes() != reg_sc.read_bytes() else None
    if add:
        bad = [x for x in gate_all(dt, draft_mod._at(st["schema"]), ledger=False) if not x[1]]   # 더한 칸은 다른 변형의 열 대장 밖
        if bad:
            print(f"■ 확정 멈춤 — 칸 더한 스키마로 변형 {len(bad)}개가 관문 FAIL ({' · '.join(n for n, *_r in bad)}) — 쓰지 않았다")
            from cli.register import gate
            for n, _ok, _k, o in bad:
                for code, label, detail in gate.fail_lines(o)[:3]:
                    print(f"  [FAIL] {n} · {code or ''}  {label}" + (f" — {detail}" if detail else ""))
            return 1
        write_file(reg_sc, draft_mod._at(st["schema"]).read_bytes())
        print(f"   칸 더하기 — {dt} 스키마 새 판(schema_version {mine.get('schema_version')}) · 더한 칸 {sorted(add)} · "
              f"모든 변형 관문 PASS {len(registry.variants_of(dt))}")
        print("   이미 넣은 문서는 다시 넣지 않아도 된다 — 더한 칸만 비어 있다 · 채우려면 그 양식 문서를 다시 넣는다")
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
