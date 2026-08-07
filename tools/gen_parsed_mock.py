# -*- coding: utf-8 -*-
"""mock/parsed/*.json 생성기 — raw 실물의 prefix에서 계약 JSON을 파생시킨다.

증분0 §4.1(v1.4)은 이 절을 "마이그레이션"이 아니라 **신규 작성**으로 정정했다.
기준 원문은 구현문서 §6의 mock 전문이고, §4.1의 4항을 처음부터 적용한다:
  ① 조각 필드 chunk_id → source_locator (role=meta)
  ② 봉투에 adapter_version 추가
  ③ provenance 표기는 source_locator 기반 유지
  ④ CP01은 parsed·raw 모두 11 record가 prefix

**raw에서 파생시키는 이유**: 손으로 쓰면 raw와 어긋날 수 있고, 그것이 곧
D-18(역산 정합 = prefix 일치)의 무효화다. 여기서 뽑아내면 정합이 구성상 보장된다.
prose(PPT01·PPT03)는 대응하는 raw가 없으므로 구현문서 §6.3·증분0 §4.2가 정본이다.

사용: python tools/gen_parsed_mock.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
OUT = ROOT / "mock" / "parsed"

# tests/verify_roundtrip.py의 참조 구현(reader+normalizer)을 그대로 쓴다 —
# 파서가 실제로 내놓을 값과 parsed mock이 같은 함수에서 나와야 정합이 성립한다.
_src = (ROOT / "tests" / "verify_roundtrip.py").read_text(encoding="utf-8")
_ns = {"__name__": "_vr", "__file__": str(ROOT / "tests" / "verify_roundtrip.py")}
exec(compile(_src.split("\nallok = True")[0], "_vr", "exec"), _ns)
read_table, normalize = _ns["read_table"], _ns["normalize"]

COMMON = {"공정구분": "process_group", "공정번호": "process_no",
          "공정명": "process_ref", "극성": "electrode_type"}


def envelope(doc_id, doc_type, source_path, revision, kind, payload_key, payload):
    return {
        "doc_id": doc_id, "doc_type": doc_type, "source_path": source_path,
        "revision": revision, "parsed_at": "2026-01-05T00:00:00",
        "parser_version": "mock-0.1",
        "adapter_version": "mock-1.0",          # §4.1-2 (카드 C9 · 틀 A7-3)
        "context": {"model": "M1"},
        "payload_kind": kind,
        payload_key: payload,
    }


def build(doc_id, xlsx, entity_cols, required, field_map, prefix_n, tag,
          model_col="적용모델", extra_cols=()):
    h, rows, _ = read_table(ROOT / "mock" / "raw" / xlsx)
    recs, fails, _ = normalize(h, rows, entity_cols, required)
    assert not fails, f"{doc_id}: 자기완결 실패 {fails}"
    out = []
    for i, (_, r) in enumerate(recs[:prefix_n], 1):
        rec = {"source_locator": f"{doc_id}-{tag}{i}"}   # §4.1-1
        for ko, en in COMMON.items():
            if r.get(ko) is not None:
                rec[en] = r[ko]
        for ko, en in field_map.items():
            if r.get(ko) is not None:
                rec[en] = r[ko]
        for ko in extra_cols:                            # unknown_field 재료 등
            if r.get(ko) is not None:
                rec[ko] = r[ko]
        if model_col and r.get(model_col):               # 봉투 context를 record가 덮음
            rec["context"] = {"model": r[model_col]}
        out.append(rec)
    return out


def write(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = len(obj.get("records") or obj.get("chunks"))
    print(f"  {name:<16} {n:>2}건")


def main():
    # ---- CP01 : 11 record prefix (C1~C11) ----
    cp = build("CP01", "CP01.xlsx", ["설비", "관리항목"],
               ["공정명", "설비", "관리항목"],
               {k: k for k in ["설비", "관리항목", "규격", "측정방법", "대응계획"]},
               11, "C")
    write("CP01.json", envelope("CP01", "cp", "mock/raw/CP01.xlsx", "R3",
                                "table", "records", cp))

    # ---- CP01B : CP01과 records 동일 · doc_id만 다름 (S5 doc_hash 차단) ----
    b = envelope("CP01B", "cp", "CP_사본.xlsx", "R3", "table", "records",
                 [dict(r, source_locator=r["source_locator"].replace("CP01-", "CP01B-"))
                  for r in cp])
    write("CP01B.json", b)

    # ---- PFMEA01 : 13 record prefix (R1~R13) ----
    fm = build("PFMEA01", "PFMEA01.xlsx", ["고장모드", "고장원인"],
               ["공정명", "고장모드", "고장원인"],
               {"고장모드": "failure_mode", "고장원인": "cause",
                "심각도": "severity", "영향분류": "effect_category",
                "관리항목(모드)": "control_item_for_fm",
                "관리항목(원인)": "control_item_for_cause",
                "예방관리": "prevention_control", "검출관리": "detection_control"},
               13, "R", model_col=None, extra_cols=("비고",))
    write("PFMEA01.json", envelope("PFMEA01", "pfmea", "mock/raw/PFMEA01.xlsx",
                                   "R3", "table", "records", fm))
    return cp, fm


if __name__ == "__main__":
    print("mock/parsed 생성:")
    main()
