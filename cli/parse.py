# -*- coding: utf-8 -*-
"""파서 CLI — 운영 파싱 + 구축 모드 3단 배선 (파서_명세 §6 · 증분0 §3 P1).

모든 단계는 **CLI 진입점 + 파일 입출력**이다(§16.1 계약 1) — 플랫폼이 subprocess로
부른다. 파서는 별도 프로그램이고 에이전트와의 결합은 **계약 JSON 하나**다(D-9).

  python cli/parse.py run   <어댑터.py> <doc_id> <문서> [출력.json]   운영 파싱 1회
  python cli/parse.py head  <문서> [N]                                관찰 재료(등록 세션 공급)
  python cli/parse.py build <어댑터.py> <doc_type> <표본...>          구축 모드 3단 배선

**구축 모드 3단의 경계**: 여기는 **배선**까지다 — 생성(어댑터 초안)·검수 뷰 렌더·
등록부 등재는 P2·P3의 몫이다. 이 자리가 하는 일은 "세 단계가 실제로 이어지는가"를
파일로 드러내는 것이고, 각 단계의 산출을 `review/{doc_type}/`에 남긴다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from core import llm
from parser import pipeline, preflight, reader, validator

REVIEW = ROOT / "review"


def load_adapter(path):
    spec = importlib.util.spec_from_file_location(f"ad_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_run(args):
    adapter_path, doc_id, doc = args[0], args[1], args[2]
    out = args[3] if len(args) > 3 else None
    # 이미지 요약(LLM 지점 ④)의 실호출 경로는 **주입**한다 — 파서는 core를
    # import하지 않는다(P1). USE_MOCK이면 None이 오고 파서가 고정 문자열을 쓴다.
    res = pipeline.parse(load_adapter(adapter_path), doc_id, doc,
                         summarize=llm.image_summarizer())
    print(f"[parse] {res}")
    for f in res.failures:
        print(f"   [{f['kind']}] {f['reason']}")
        if f["detail"]:
            print(f"      {json.dumps(f['detail'], ensure_ascii=False)[:300]}")
    if res.report:
        print(f"   report: {json.dumps(res.report, ensure_ascii=False)}")
    if res.ok and out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res.envelope, ensure_ascii=False, indent=2)
                             + "\n", encoding="utf-8")
        print(f"   → {out}")
    return 0 if res.ok else 1


def cmd_head(args):
    """등록 세션에 공급하는 관찰 재료 — **reader는 두 모드에서 같은 코드다**(§3 규약 4)."""
    n = int(args[1]) if len(args) > 1 else 12
    print(json.dumps(reader.head(reader.read(args[0]), n), ensure_ascii=False,
                     indent=2)[:4000])


def cmd_build(args):
    """구축 모드 3단 — **생성 → 검수 → 확정**의 배선 (파서_명세 §6).

    ①생성: 표본의 관찰 재료(reader head)를 모아 어댑터 초안의 입력 패키지를 만든다.
      USE_MOCK에서 초안 자체는 fixture가 대신한다(D-10·D-26) — 여기서는 인자로 받는다.
    ②검수: 실행 하네스에 해당하는 **기계 관문**을 통과시킨다 — preflight + 파싱 +
      계약 self-check를 표본 전부에 대해 돌리고 결과를 뷰 데이터로 남긴다.
    ③확정: 승인 기록을 남긴다. **registry 등재는 P3의 몫**이라 여기서는 하지 않는다.

    표본 1부면 경고를 뷰 데이터에 싣는다(D-22 확장 문구) — 변형을 관찰하지 못했다는
    사실 자체가 검수자의 판단 재료다.
    """
    adapter_path, doc_type, samples = args[0], args[1], args[2:]
    mod = load_adapter(adapter_path)
    outdir = REVIEW / doc_type
    outdir.mkdir(parents=True, exist_ok=True)

    view = {"doc_type": doc_type, "adapter": str(adapter_path),
            "adapter_version": mod.ADAPTER.get("adapter_version"),
            "payload_kind": mod.ADAPTER.get("payload_kind"),
            "samples": [], "warnings": []}

    if len(samples) < 2:
        view["warnings"].append(
            "표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음** (D-22). "
            "1부 등록의 선언 edges는 특별 확인 대상이다")

    print(f"■ 구축 모드 — {doc_type} · 표본 {len(samples)}부")
    print("\n① 생성 — 관찰 재료 수집 (reader head · 두 모드 공용 코어)")
    pkg = {"doc_type": doc_type, "samples": []}
    for s in samples:
        raw = reader.read(s)
        pkg["samples"].append({"path": s, "head": reader.head(raw, 12)})
        print(f"   {Path(s).name}: {raw['format']} · "
              f"{len(raw.get('sheets') or raw.get('slides') or [])} 단위")
    (outdir / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n② 검수 — 기계 관문 (preflight → 파싱 → 계약 self-check)")
    allok = True
    for i, s in enumerate(samples, 1):
        raw = reader.read(s)
        pf_ok, pf_detail = preflight.check(mod, raw)
        res = pipeline.parse(mod, f"{doc_type.upper()}{i:02d}", s,
                             summarize=llm.image_summarizer())
        allok &= bool(pf_ok and res.ok)
        print(f"   {Path(s).name}: preflight {'OK' if pf_ok else 'MISMATCH'} · "
              f"파싱 {'OK' if res.ok else 'FAIL'} · 조각 {res.report.get('pieces', 0)}")
        for f in res.failures:
            print(f"      [{f['kind']}] {f['reason']}")
        view["samples"].append({
            "path": s, "preflight": pf_ok, "preflight_detail": pf_detail,
            "parsed": res.ok, "failures": res.failures, "report": res.report,
            # 검수 뷰 3층 표시의 데이터 — **렌더는 P2 몫**이다(경계)
            "envelope_head": ({k: v for k, v in (res.envelope or {}).items()
                               if k not in ("records", "chunks")} if res.ok else None),
            "pieces_head": ((res.envelope.get("records")
                             or res.envelope.get("chunks"))[:3] if res.ok else []),
        })
    (outdir / "view.json").write_text(
        json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   → {outdir / 'view.json'}  (검수 뷰 **데이터** — HTML 렌더는 P2)")
    for w in view["warnings"]:
        print(f"   ⚠ {w}")

    print("\n③ 확정 — 승인 기록 (registry 등재는 P3의 몫이다)")
    approval = {"doc_type": doc_type, "adapter_version": mod.ADAPTER.get("adapter_version"),
                "machine_gate": "PASS" if allok else "FAIL",
                "approved_by": None, "approved_at": None,
                "instructions": [],
                "note": "승인자·시점은 사람이 채운다. 기계 관문 통과가 승인의 전제다"}
    (outdir / "approval.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   → {outdir / 'approval.json'}  (기계 관문 {approval['machine_gate']})")
    return 0 if allok else 1


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    return {"run": cmd_run, "head": cmd_head, "build": cmd_build}[argv[0]](argv[1:]) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
