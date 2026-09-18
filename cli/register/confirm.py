# -*- coding: utf-8 -*-
"""칸 1.7 — **③ 확정**: 승인 1회 → 등록부 등재 → 정본 승격 (`register confirm`)."""

from __future__ import annotations

from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core.state import fixtures, log, registry, store
import json
from cli.register import draft as draft_mod
from cli.register import gate
from cli.register import view
from cli.register import ROOT, _load, _state


# ================================================================ ③ 확정
def cmd_confirm(doc_type, approved_by):
    """③ 확정 — 승인 1회로 등록부에 등재한다.

    **기계 관문 통과가 승인의 전제**다. "무수정 = 자동 통과"는 금지이므로 승인자가
    없으면 등재하지 않는다(틀 §2).
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[확정] '{doc_type}'의 생성이 먼저다 — "                 # [상태]
                         f"근거 review/{doc_type}/state.json 없음\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")
    # **저장된 PASS만으로 확정하지 않는다**(B60 ①) — 지금 코드의 관문을 지난다.
    if gate.regate(doc_type, st) != "PASS":
        # **막되 막다른 길로 두지 않는다**(B59 ①) — 이유와 칠 수 있는 다음 줄을 준다.
        gate.gate_block(doc_type, st)
        return 1
    if not approved_by:
        raise SystemExit("[확정] 승인자 미지정 — 무수정 자동 통과는 금지다 (틀 §2)")          # [사용법]

    mod = _load(draft_mod._at(st["adapter"]), f"reg_{doc_type}")
    at = store._now()
    # **등재가 먼저, 승격이 나중이다.** 반대로 하면 등재가 거부됐을 때 승격된
    # 파일만 남아 조회에는 잡히고 등록부에는 없는 반쪽 상태가 되고, 그 이름의
    # 재등록이 「내장 중복」으로 영영 막힌다(실측).
    adapter_path, schema_path = view._promote_paths(doc_type)
    # **새 판이면 교체다**(H27 · B58 ①) — 이름 중복 거부가 아니라 정본 교체이고
    # `revision`이 오른다. 승인 기록은 덮지 않고 누적한다(옛 판으로 인입된 문서의
    # 근거가 사라지면 안 된다).
    _revising = bool(st.get("revise_of")) and bool(registry.lookup(doc_type))
    _fn = registry.revise if _revising else registry.register
    _kw = {} if _revising else {"layer": st["layer"]}
    entry = _fn(
        doc_type, adapter=adapter_path, schema=schema_path,
        adapter_version=mod.ADAPTER.get("adapter_version"),
        approved_by=approved_by, approved_at=at,
        instructions=st.get("instructions") or [], **_kw)
    view._promote(doc_type, st)              # 등재가 성립한 뒤에만 실물을 옮긴다
    approval = {"doc_type": doc_type,
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "승인자": approved_by, "시점": at,
                "수정 지시 이력": st.get("instructions") or []}
    # **무엇이 뽑히는 것을 보고 승인했나**(B51) — prose의 승인 근거는 추출 리허설이다.
    _vw = _dir(doc_type) / "view.json"
    if _vw.exists():
        _ex = ((json.loads(_vw.read_text(encoding="utf-8")).get("sections") or {})
               .get("extract_rehearsal") or {})
        if _ex:
            approval["추출 리허설"] = {k: _ex.get(k) for k in
                                   ("source", "prompt_version", "config_version",
                                    "totals", "category_counts")}
    _ap = _dir(doc_type) / "approval.json"
    if _ap.exists():
        # **덮지 않는다** — 판마다 무엇을 보고 승인했나가 이력이다.
        try:
            _prev = json.loads(_ap.read_text(encoding="utf-8"))
            approval["이전 승인"] = ((_prev.pop("이전 승인", None) or []) + [_prev])[-20:]
        except json.JSONDecodeError:
            pass
    approval["revision"] = entry.get("revision", 0)
    _ap.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    if _revising:
        print(f"■ ③ 확정 — {doc_type} **새 판 등재** "
              f"(revision {entry.get('revision')} · 승인 {approved_by} @ {at})")
        print(f"   승인 이력 {len(entry.get('approvals') or [])}건 — 덮지 않고 쌓는다")
    else:
        print(f"■ ③ 확정 — {doc_type} 등록부 등재 (승인 {approved_by} @ {at})")
    print(f"   어댑터·스키마 활성: {entry['adapter']} · {entry['schema']}")
    # **자동 재인입은 없다**(문서 4 §4.8-7) — 무엇이 옛 판으로 들어와 있는지 보인다.
    _ing = registry.ingested_docs(doc_type)
    if _ing:
        print(f"   이 doc_type으로 인입된 문서 {len(_ing)}건 — "
              f"**재인입은 사람이 정한다**(자동으로 다시 읽지 않는다)")
        print(f"     {', '.join(_ing[:8])}" + (f" 외 {len(_ing) - 8}건" if len(_ing) > 8 else ""))
    print(f"   승인 기록 → {(_dir(doc_type) / 'approval.json').relative_to(ROOT)}")
    # **등록은 여기서 끝이고 인입은 자동으로 이어지지 않는다** — 그래프까지 간 줄 알고
    # 멈춘 실측이 있어 다음 두 줄을 그대로 낸다(등록개선 ③).
    # **가이드가 사람에게 시키는 흐름 그대로다**(B66 ③) — 구판은 `parse run`·`build`
    # 두 줄을 먼저 냈는데 가이드 §4·§5에는 없는 명령이라 사내에서 「가이드에 없는
    # 명령」으로 읽혔다. 부품 명령은 가이드 §5 표에 남고 **확정 화면에서만 뺀다.**
    # `--doc-type`을 붙여 안내한다: 스캔으로도 고르지만(B66 ①) **방금 확정한
    # doc_type을 사람이 아는 자리**라 지정이 맞다(P7 — 자동 라우팅 금지와 같은 결).
    print("   다음 — 인입 (등록이 그래프를 만들지는 않는다):")
    print(f"     python run.py ingest-file <문서> --doc-type {doc_type} --dry-run"
          f"   ← 선택·형태 판정만 본다")
    print(f"     python run.py ingest-file <문서> --doc-type {doc_type}")
    return 0


def cmd_list():
    from cli.platform import cmd_doctypes
    return cmd_doctypes()


#: mock 관문 대상 — 사람이 치는 운영 명령(§7.6-B-1 · B48). `roles`·`list`는 열람이다.
GATED = ("generate", "review", "confirm")
