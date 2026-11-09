# -*- coding: utf-8 -*-
"""칸 3.1 — **선택**(인입의 첫 단 · 파싱 0): doc_type과 **변형**을 고른다 (B46 · B190 ② — `cli/ingest.py`에서 떼었다).

지문 스캔은 **어댑터(변형) 단위**로 대조하고(`cli.scan` — 같은 doc_type의 변형이 서로 덮이지 않는다) 고른 어댑터의
doc_type · 스키마로 간다 · `--doc-type` 지정이면 그 doc_type의 변형 중에서 지문으로 고른다(변형이 하나면 지금처럼 그것) ·
일치 0건이면 가장 가까운 doc_type으로 완성된 `--variant` 등록 줄(`next`) · 고른 변형은 선택 근거(`basis.variant`)에 실려 화면과
문서 대장(`routing`)에 남는다.
"""
from __future__ import annotations

from pathlib import Path

from cli import scan as scan_mod
from core import paths
from core.state import registry
from parser import form as form_mod, reader as reader_mod
from parser.reader import GRID_EXT, LEGACY_BINARY, SUPPORTED, legacy_note


def form_of(doc):
    """형태 판정(table/prose) — **격자 포맷만**. `.pptx`·`.pdf`는 포맷이 prose를 함의한다.

    선택 근거(`basis`)에 실어 인입 기록으로 보낸다 — **기록이 이 기능의 절반이다**
    (문서 1 C37): 문턱 조정과 애매 구간 측정의 유일한 재료이고, 그 크기가 재어진
    뒤에야 LLM 보조를 검토한다.

    판정이 **선택을 바꾸지는 않는다** — doc_type이 정해지면 어댑터가 갈래를 이미
    말한다. 여기서 하는 일은 ①기록 ②그 둘이 어긋날 때 화면 경고다. 판정으로
    어댑터를 갈아 끼우면 사람이 지정한 doc_type이 조용히 무시된다.
    """
    p = Path(doc)
    if p.suffix.lower() not in GRID_EXT:
        return None
    try:
        return form_mod.judge(reader_mod.read(str(p)))
    except Exception as e:                       # 판정 실패가 인입을 막지 않는다
        return {"verdict": None, "auto": False, "signals": {},
                "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}


def select(doc, doc_type=None, adapter_paths=None):
    """doc_type 선택 — 파싱하지 않는다. 결과 `status`는 chosen · ambiguous · none · unsupported.

    `basis`가 **선택 근거**다(B46 ①): 사람 지정이면 `by=human`, 스캔이면 `by=scan`과
    일치 내역(`header_labels` 완전 일치 — 누락 0·잉여 0)이 함께 실린다.
    """
    from cli.ingest import doc_id_of             # doc_id 규칙은 인입 칸 한 자리
    p = Path(doc)
    out = {"doc": str(p), "doc_id": doc_id_of(p), "doc_type": None, "adapter": None,
           "basis": None, "candidates": [], "reason": None}
    if p.suffix.lower() in LEGACY_BINARY:        # `.doc` 등 — 무엇으로 저장하면 되나를 말한다 (B88 ②)
        return {**out, "status": "unsupported", "reason": legacy_note(p)}
    if p.suffix.lower() not in SUPPORTED:
        return {**out, "status": "unsupported",
                "reason": f"지원하지 않는 포맷 {p.suffix!r} — reader가 여는 것은 {SUPPORTED}"}
    if doc_type:
        if registry.schema_of(doc_type) is None:
            return {**out, "status": "none",
                    "reason": f"미등록 doc_type '{doc_type}' — 구축 모드(register) 대상이다"}
        # 어댑터 실물은 **지문 스캔과 같은 소재지**에서 찾는다(등록부 + 기본 소재지) —
        # 등록부만 보면 내장 doc_type(스키마만 싣고 어댑터는 mock 트랙)이 지정으로도 안 간다.
        # **등록부에 있으면 등록부의 변형만**(`cli.scan.adapters` — 같은 doc_type이 소재지에도 있으면 등록된 실물이 정본) · 없으면 소재지
        mine = [p_ for dt_, _n, p_ in registry.adapter_variants() if dt_ == doc_type] if adapter_paths is None else []
        mine = mine or [f for f, m in scan_mod.adapters(adapter_paths) if m.ADAPTER.get("doc_type") == doc_type]
        if not mine:
            return {**out, "status": "none", "doc_type": doc_type,
                    "reason": f"'{doc_type}'의 어댑터 실물이 소재지에 없다 — "
                              f"`parse run <어댑터> …`로 직접 넣거나 register로 어댑터를 등록한다"}
        basis = {"by": "human", "doc_type": doc_type, "form": form_of(p)}
        if len(mine) == 1:                       # 변형이 하나면 지금처럼 그것 (지문 대조는 preflight 몫)
            return {**out, "status": "chosen", "doc_type": doc_type, "adapter": Path(mine[0]),
                    "basis": {**basis, **_variant_of(mine[0])}}
        return _pick_variant(p, doc_type, adapter_paths, out, basis)
    res = scan_mod.scan(p, adapter_paths)
    cands = res["candidates"]
    out["candidates"] = cands
    if len(cands) == 1:
        f, _mod = res["_mods"][cands[0]]
        d = next(x for x in res["details"] if x["label"] == cands[0])
        dt = d["doc_type"]
        if registry.schema_of(dt) is None:
            return {**out, "status": "none", "doc_type": dt,
                    "reason": f"지문은 '{dt}'와 유일 일치지만 **등록부에 없다** — "
                              f"인입이 미등록 doc_type을 거부한다(B3). register로 확정하라"}
        rejected = [f"{x['label']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
                    for x in res["details"] if x.get("eligible") and not x.get("candidate")]
        return {**out, "status": "chosen", "doc_type": dt, "adapter": Path(f),
                "basis": {"by": "scan", "doc_type": dt, **_variant_of(f),
                          "match": f"header_labels 완전 일치 {d['matched']}/{d['declared']} "
                                   f"(누락 0 · 잉여 0)",
                          "rejected": rejected, "form": form_of(p)}}
    if len(cands) > 1:
        return {**out, "status": "ambiguous",
                "reason": f"지문이 {len(cands)}개 어댑터와 일치 {cands} — 사람이 --doc-type으로 고른다"}
    # **미선택은 네 갈래다**(B66 ② · B61 계약) — 구판은 한 문면(「대조할 정형
    # 어댑터가 없다」)이 서로 다른 넷을 덮었고, CSV가 대조조차 안 된 것(①)이 그
    # 문면으로 나와 사람은 **어댑터가 없다고 읽었다**. 재료는 이미 `scan()`이 낸다 —
    # 읽지 않던 키를 읽을 뿐이고 **새 계산 0**이다.
    if res.get("not_fingerprintable"):
        return {**out, "status": "none",
                "reason": f"비정형({res['not_fingerprintable']}) — 헤더 지문이 없다. "
                          f"다음: --doc-type <dt> 지정 투입"}
    if not res["details"]:
        return {**out, "status": "none",
                "reason": "대조할 어댑터 0건 — 소재지가 비었다. "
                          "다음: python -m cli.register generate <dt> <층> <문서>"}
    eligible = [x for x in res["details"] if x.get("eligible")]
    if not eligible:
        why = " · ".join(f"{x['doc_type']}: {x.get('note') or '자격 없음'}"
                         for x in res["details"])
        return {**out, "status": "none",
                "reason": f"자격 있는 어댑터 0건 — {why}. "
                          f"다음: --doc-type <dt> 또는 "
                          f"python -m cli.register generate <dt> <층> <표본...> --revise"}
    # 차이 내역은 **개수만** — 열 이름 전부를 문서마다 늘어놓으면 목록이 읽히지 않는다.
    # 자세한 내역은 `run.py scan <문서>`가 낸다(같은 대조).
    diffs = [f"{x['label']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
             for x in eligible]
    return {**out, "status": "none", "next": _variant_next(p, eligible),
            "reason": f"지문 일치 0건 — {' · '.join(diffs)} — "
                      f"상세: python run.py scan {p}"}


def _variant_of(adapter):
    """그 어댑터가 등록부의 어느 변형인가 — `{"variant": 이름}`(등록부 밖 · 내장 소재지면 빈 칸 — 지금 기록 모양 그대로)."""
    f = Path(adapter).resolve()
    for dt, name, q in registry.adapter_variants():
        if Path(q).resolve() == f:
            # 변형이 하나뿐이면(지금 등록분) 적지 않는다 — 화면 · 문서 대장 모양 그대로(③ 다시 등록 0)
            return {"variant": name} if len(registry.variants_of(dt)) > 1 else {}
    return {}


def _pick_variant(p, doc_type, adapter_paths, out, basis):
    """`--doc-type` 지정 · 그 doc_type의 변형이 둘 이상 — **지문으로 고른다**(§6.5-3). 완전 일치 하나면 그것 · 0이면 가장 가까운
    변형으로 간다(파싱 앞 preflight가 차이 내역과 함께 멈추고 큐 adapter_mismatch — 지금 지정 길과 같다) · 둘 이상이면 사람이 정한다."""
    res = scan_mod.scan(p, adapter_paths)
    ds = [d for d in res["details"] if d.get("doc_type") == doc_type and d.get("eligible")]
    full = [d for d in ds if d.get("candidate")]
    if len(full) > 1:
        return {**out, "status": "ambiguous", "doc_type": doc_type,
                "reason": f"'{doc_type}'의 변형 {len(full)}개가 지문 완전 일치 {[d['label'] for d in full]} — 사람이 정한다(같은 양식이 "
                          f"변형 둘로 등록됐다 — 하나를 거둔다)"}
    pick = full[0] if full else min(ds, key=lambda d: len(d["missing"]) + len(d["extra"]), default=None)
    if pick is None:
        return {**out, "status": "none", "doc_type": doc_type,
                "reason": f"'{doc_type}'의 변형이 지문 대조 대상이 아니다 — {[d.get('note') for d in res['details']][:2]}"}
    f, _m = res["_mods"][pick["label"]]
    how = (f"변형 지문 완전 일치 {pick['matched']}/{pick['declared']}" if full else
           f"변형 지문 완전 일치 0 — 가장 가까운 변형으로(누락 {len(pick['missing'])}·잉여 {len(pick['extra'])})")
    return {**out, "status": "chosen", "doc_type": doc_type, "adapter": Path(f),
            "basis": {**basis, **_variant_of(f), "match": how}}


def _variant_next(p, eligible):
    """일치 0건의 다음 줄 — **가장 가까운 doc_type**(누락 + 잉여가 가장 적은 것)으로 완성된 `--variant` 등록 한 줄(B190 ②) ·
    동률이면 그 doc_type 전부(이름순) 한 줄씩 — 사람이 고른다(B192 ⓪)."""
    if not eligible:
        return []
    cost = lambda x: len(x["missing"]) + len(x["extra"])      # noqa: E731
    low = min(cost(x) for x in eligible)
    near = {}
    for x in sorted(eligible, key=lambda x: x["label"]):
        if cost(x) == low:
            near.setdefault(x["doc_type"], x)
    x0 = next(iter(near.values()))
    head = (f"가장 가까운 doc_type '{x0['doc_type']}'(누락 {len(x0['missing'])}·잉여 {len(x0['extra'])})" if len(near) == 1 else
            f"가장 가까운 doc_type {len(near)}개가 동률(누락+잉여 {low}) — 그중 하나")
    out = [f"▶ 같은 종류의 다른 양식이면 — {head}에 변형으로 등록한다(스키마 그대로 · 어댑터만):"]
    for dt in sorted(near):
        out.append(f"   python -m cli.register generate {dt} {(registry.lookup(dt) or {}).get('layer') or '<층>'} {p} --variant")
    return out


def _basis_line(sel):
    b = sel.get("basis") or {}
    if b.get("by") == "human":
        out = (f"사람 지정 --doc-type {b['doc_type']}" + (f" (변형 {b['variant']})" if b.get("variant") else "")
               + (f" · {b['match']}" if b.get("match") else ""))
    elif b.get("by") == "scan":
        out = (f"지문 스캔 유일 일치 → {b['doc_type']}" + (f" (변형 {b['variant']})" if b.get("variant") else "")
               + f" · {b['match']}" + (f" · 불일치 {b['rejected']}" if b.get("rejected") else ""))
    else:
        return "-"
    # **어느 파일이 골라졌나**(B66 ④) — 어댑터는 등록부(`adapters/<dt>.py`)를 먼저
    # 보고 없으면 내장 doc_type의 소재지를 본다. 화면이 그것을 말하지 않으면 사람은
    # 「mock 소재지가 뭐냐」를 묻게 된다(사내 실측) — 경로 한 조각이 답이다.
    if sel.get("adapter"):
        out += f"  ← {paths.show(sel['adapter'])}"      # 표기는 한 자리 (B86 ①)
    return out + _form_line(b.get("form"))


def _form_line(f):
    """형태 판정의 화면 한 줄 — **신호값 다섯을 그대로** 싣는다(문서 1 C37).

    요약만 보이면 문턱이 왜 그렇게 갈렸는지 사람이 판단할 재료가 없다. 사람에게
    올라온 문서는 특히 그렇다 — 그가 보고 정할 것이 이 다섯 값이다.
    """
    if not f:
        return ""
    head = f["verdict"] or "**사람 판정 대상**"
    line = f"\n     형태 판정: {head} ({'자동' if f.get('auto') else '자동 아님'}) — {f['why']}"
    if f.get("signals"):
        line += "\n     신호값: " + " · ".join(
            f"{k}={f['signals'][k]}[{(f.get('votes') or {}).get(k, '?')[0]}]"
            for k in form_mod.SIGNALS if k in f["signals"])
    return line


# ── 인입 실패 화면 — 이유와 행이 **화면에** 뜬다 (B61 ③ · 칸 3.1 · C14) ────────
#
# 사람은 `ingest-file`을 치고 **화면을 본다** — 큐를 먼저 열지 않는다. 사유는 이미 큐
# payload에 있으므로 **같은 재료를 화면에도 찍는다**(두 자리에 두 사실이 아니라 한
# 재료의 두 표시다). 태그(`P##`)는 관문의 `G##`·골격의 `K##`과 같은 방식이고 **정본은
# 여기 한 자리**다 — 앞자리가 단이다: 2 어댑터/지문 · 3 계약(validator) · 4 구조 ·
# 5 인입 보류.
