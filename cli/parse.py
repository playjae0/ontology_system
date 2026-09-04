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
PARSED_DIR = ROOT / "parsed"   # 운영 산출 자리 (문서 7 §7.8 — 파일 존재 = 파싱 완료)

from cli._gate import require_live_or_allow    # mock 관문 (B48)
from core import llm
from parser import pipeline, preflight, reader, validator

REVIEW = ROOT / "review"


def injections():
    """파서에 내려보낼 **LLM 함수 3종을 한 번에 만든다** (문서 7 §7.6-B-1 · B48).

    **모드는 여기서 한 번 정하고 아래로 내려간다.** 파서에는 「지금 mock인가」라는
    질문이 없으므로(파서 무판독), 「실호출 모드인데 함수가 안 왔다」를 잡을 수 있는
    자리는 **만드는 쪽**뿐이다. 그 검사가 아래 assert이고, 그것이 곧
    「진입점이 한 번 정해 전부 내려보낸다」의 기계 판정이다(§7.6-B-2 도달 가능성).

    팩토리는 실호출 모드에서 미설정이면 `require()`로 이미 멈춘다 — 그래서 여기
    None은 **mock 모드에서만** 온다. 배선이 하나 빠지면(팩토리가 없거나 주입을
    빠뜨리면) 실호출 모드에서 None이 남아 이 자리가 붉는다.
    """
    fns = {"summarize": llm.image_summarizer(),
           "pick_coord": llm.coord_picker(),
           "map_structure": llm.struct_mapper()}
    if not llm.use_mock():
        missing = [k for k, v in fns.items() if v is None]
        if missing:
            raise llm.NotConfigured(
                f"실호출 모드인데 파서 주입 함수가 비어 있다: {missing} — "
                f"휴리스틱으로 조용히 떨어지면 그 지도가 청크 경계를 정하고, "
                f"바뀐 경계는 chunk_id를 바꿔 재인입 멱등까지 흔든다 (문서 7 §7.6-B-2)")
    return fns


def load_adapter(path):
    spec = importlib.util.spec_from_file_location(f"ad_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_parse(adapter_path, doc_id, doc, out=None):
    """운영 파싱 1회 — **출력 경로는 인자이고, 운영 산출 자리는 `parsed/{doc_id}.json`이다**
    (문서 7 §7.1 진입점 계약 · §7.8). **파일 존재 = 파싱 완료**이므로 자리가 정해져
    있어야 플랫폼이 그 상태를 파일로 판정할 수 있다.

    `parse run`과 일괄 투입(`ingest-file`·`ingest-dir`)이 **같은 함수**를 부른다 —
    두 벌이면 주입(이미지 요약·좌표)이 한쪽에서 빠지는 날이 온다.
    돌려주는 것은 `(ParseResult, 쓴 경로 또는 None)`이다.
    """
    out = out or str(PARSED_DIR / f"{doc_id}.json")
    # LLM 3지점(④·⑦·⑨)의 실호출 경로는 **주입**한다 — 파서는 core를 import하지
    # 않는다(A1). mock이면 None이 오고 파서가 §7.1 대체를 쓴다.
    res = pipeline.parse(load_adapter(adapter_path), doc_id, doc, **injections())
    written = None
    if res.ok and out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res.envelope, ensure_ascii=False, indent=2)
                             + "\n", encoding="utf-8")
        written = out
    return res, written


def cmd_run(args):
    adapter_path, doc_id, doc = args[0], args[1], args[2]
    res, out = run_parse(adapter_path, doc_id, doc, args[3] if len(args) > 3 else None)
    print(f"[parse] {res}")
    for f in res.failures:
        print(f"   [{f['kind']}] {f['reason']}")
        if f["detail"]:
            print(f"      {json.dumps(f['detail'], ensure_ascii=False)[:300]}")
    if res.report:
        print(f"   report: {json.dumps(res.report, ensure_ascii=False)}")
    if out:
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
        pkg["samples"].append({"path": s, "head": reader.head(raw)})
        print(f"   {Path(s).name}: {raw['format']} · "
              f"{len(raw.get('sheets') or raw.get('slides') or [])} 단위")
    (outdir / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n② 검수 — 기계 관문 (preflight → 파싱 → 계약 self-check)")
    allok = True
    for i, s in enumerate(samples, 1):
        raw = reader.read(s)
        pf_ok, pf_detail = preflight.check(mod, raw)
        res = pipeline.parse(mod, f"{doc_type.upper()}{i:02d}", s, **injections())
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
    cmd, rest = argv[0], list(argv[1:])
    if cmd == "run":                       # 운영 파싱 — mock 관문 대상(B48)
        rest = require_live_or_allow(rest, command="parse run")
    return {"run": cmd_run, "head": cmd_head, "build": cmd_build}[cmd](rest) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
