# -*- coding: utf-8 -*-
"""실행 하네스 — LLM이 산출한 adapter 코드와 매칭 스키마를 **실제로 돌려** 검증한다.

새 성공 판정(사용자 확정, 2026-08-01):
  "LLM이 코드 안에서 도는가"가 아니라
  "LLM이 내놓은 schema/adapter를 넣었을 때 파이프라인이 실제로 도는가"

검사 4단
  ① adapter 로드    — 문법 오류·ADAPTER 선언 형식·순수성(금지 import) 검사
  ② preflight       — ADAPTER.expects ↔ 실물 지문 대조
  ③ extract 실행    — 조각 산출 · 계약 3층 구조 self-check(validator)
  ④ 스키마 정합     — 스키마 fields ↔ 조각 필드 대조 + role 루프 드라이런
                     (fields의 정답은 payload_kind가 정한다 — prose는 `{}`가 정답, D-31)

사용: python run_adapter.py <adapter.py> <schema.json> <문서.xlsx> [문서2.xlsx ...]
"""
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

from openpyxl.utils import range_boundaries, get_column_letter

# 레포 루트를 import 경로에 넣는다 — 이 파일은 kit/ 에 있으므로 부모가 루트다.
# (구판의 절대경로 sys.path 하드코딩을 대체 — 08-07 13회차 판정)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser.reader import read

ROLES = {"anchor", "entity", "attribute", "content", "meta"}
STRUCT_FIELDS = {"process_group", "process_ref", "process_no",
                 "electrode_type", "context", "source_locator", "doc_type"}
BANNED_IMPORTS = {"requests", "urllib", "httpx", "openai", "anthropic", "socket"}

ok_all = True


def show(label, ok, detail=""):
    global ok_all
    ok_all = ok_all and bool(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    return bool(ok)


# ---------------------------------------------------------------- ① 로드
def load_adapter(path):
    src = open(path, encoding="utf-8").read()
    print("\n① adapter 로드")
    try:
        tree = ast.parse(src)
        show("문법 오류 없음", True)
    except SyntaxError as e:
        show("문법 오류 없음", False, str(e))
        return None
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imports.add(n.module.split(".")[0])
    show("순수 함수 계약 — 네트워크/LLM 호출 없음 (§5 규약 2)",
         not (imports & BANNED_IMPORTS), str(sorted(imports & BANNED_IMPORTS)))
    spec = importlib.util.spec_from_file_location("gen_adapter", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        show("import 성공", False, f"{type(e).__name__}: {e}")
        return None
    show("import 성공", True)
    A = getattr(mod, "ADAPTER", None)
    show("ADAPTER 선언 존재", isinstance(A, dict))
    if isinstance(A, dict):
        show("필수 키 4종 (doc_type·adapter_version·payload_kind·expects)",
             {"doc_type", "adapter_version", "payload_kind", "expects"} <= set(A))
        show("payload_kind가 닫힌 2값", A.get("payload_kind") in ("table", "prose"),
             str(A.get("payload_kind")))
    show("extract 함수 존재", callable(getattr(mod, "extract", None)))
    show("locate 함수 없음 (§5 규약 1 — 폐지된 인터페이스)",
         not hasattr(mod, "locate"))
    return mod


# ---------------------------------------------------------------- ② preflight
def _flatten_strings(obj):
    """expects 안에 등장하는 모든 문자열(키·값·중첩 포함)을 모은다."""
    out = set()
    if isinstance(obj, str):
        out.add(obj.strip())
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out |= _flatten_strings(k) | _flatten_strings(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out |= _flatten_strings(v)
    return out


def preflight(mod, raw, label):
    """preflight의 기능은 '양식 표류 감지'다. 특정 키 배치를 요구하지 않고
    **표류를 감지할 수 있는 지문이 expects에 실려 있는가**를 검사한다."""
    print(f"\n② preflight — {label}")
    exp = mod.ADAPTER.get("expects", {})
    pk = mod.ADAPTER.get("payload_kind")
    strings = _flatten_strings(exp)

    if pk == "prose":
        signals = {"heading_pattern", "split_on", "indent", "bold", "text_column",
                   "level", "pattern", "number", "section"}
        has = any(any(sg in str(k).lower() for sg in signals) for k in exp)
        return show("분할 신호 상수가 expects에 선언됨 (prose는 header_row 대상 아님)",
                    has, f"keys={list(exp)[:6]}")

    if raw["format"] != "xlsx":
        return show("xlsx 아님 — 헤더 지문 대조 대상 아님", True)
    sh = raw["sheets"][0]
    hr = exp.get("header_row")
    if not hr:
        return show("expects.header_row 선언됨", False, "선언 없음")
    actual = [str(sh["cells"].get(f"{get_column_letter(c)}{hr}", "")).strip()
              for c in range(1, sh["max_col"] + 1)]
    actual = [a for a in actual if a]
    show(f"header_row {hr}행에 헤더 {len(actual)}개 존재", len(actual) >= 5, str(actual[:4]))
    missing = [a for a in actual if a not in strings]
    show("원본 헤더 문자열이 전부 expects에 실림 → 표류 감지 가능",
         not missing, f"미포함 {len(missing)}개: {missing}")
    return not missing


# ---------------------------------------------------------------- ③ extract
def run_extract(mod, raw, label):
    print(f"\n③ extract 실행 — {label}")
    try:
        pieces = mod.extract(raw)
    except Exception as e:
        show("예외 없이 실행", False, f"{type(e).__name__}: {e}")
        return None
    show("예외 없이 실행", True)
    show("list[dict] 반환", isinstance(pieces, list) and all(isinstance(p, dict) for p in pieces),
         f"{type(pieces).__name__} / {len(pieces) if isinstance(pieces, list) else '-'}건")
    if not pieces:
        return pieces
    show(f"조각 {len(pieces)}건 산출 (0건 아님)", len(pieces) > 0)
    locs = [p.get("source_locator") for p in pieces]
    show("전 조각에 source_locator 존재", all(locs))
    show("source_locator가 문서 내 유일 (§5 규약 1)", len(set(locs)) == len(locs),
         f"중복 {len(locs) - len(set(locs))}건")
    show("정본 id를 파서가 부여하지 않음 (chunk_id/record_id 부재 — 틀 A7-1)",
         not any({"chunk_id", "record_id", "doc_hash"} & set(p) for p in pieces))
    pk = mod.ADAPTER["payload_kind"]
    if pk == "prose":
        show("prose 조각에 text 또는 image_ref 존재",
             all(("text" in p) or ("image_ref" in p) for p in pieces))
    # 자기완결성 — 값이 상동 기호/미전개 병합 흔적을 남기지 않았는가
    ditto = [p for p in pieces for v in p.values()
             if isinstance(v, str) and v.strip() in {"〃", "〝", "상동"}]
    show("상동 기호가 해소됨 (계약 ③)", not ditto, f"{len(ditto)}건 잔존")
    return pieces


# ---------------------------------------------------------------- ④ 스키마 정합
def payload_kind_of(schema, mod):
    """payload_kind의 선언처 — **스키마 우선, 없으면 어댑터**.

    둘 다 계약 선언물이고 하네스는 doc_type이 일치하는 한 쌍만 받는다(main의 대조).
    스키마가 선언하지 않는 경우가 실재하므로(3차 산출 fixture 2종 모두 미선언) 폴백을
    둔다 — 어느 쪽도 선언하지 않으면 분기 자체가 불가능하니 그때는 명시적 실패다.
    **값으로 분기하고 doc_type 이름으로 분기하지 않는다**(B1).
    """
    return schema.get("payload_kind") or (mod.ADAPTER or {}).get("payload_kind")


def check_schema(schema, pieces, label, payload_kind=None):
    print(f"\n④ 매칭 스키마 정합 — {label}")
    show("헤더 4키 (doc_type·schema_version·layer·use_blocks)",
         {"doc_type", "schema_version", "layer"} <= set(schema))
    fields = schema.get("fields", {})
    # **fields의 정답은 payload_kind가 정한다** [D-31 확정 — 카드 C17 · CH2 2.5/2.6].
    # prose 조각의 고정 키 4종(text·section·meta·image_ref)은 **payload 구조 필드**라
    # role 배정 대상이 아니고, 그래서 prose 매칭 스키마의 fields는 `{}`가 정답이다 —
    # 층·블록 선언이 계약의 전부다. 구판은 이 정답을 FAIL로 찍었다(3차 로그의 유일한 FAIL).
    if payload_kind == "prose":
        show("prose 스키마의 fields는 비어 있음 (D-31 — 고정 키는 payload 구조 필드)",
             not fields, f"{len(fields)}개")
    elif payload_kind == "table":
        show("table 스키마의 fields 선언 존재", bool(fields), f"{len(fields)}개")
    else:
        show("payload_kind가 스키마 또는 어댑터에 선언됨 (fields 판정의 전제)",
             False, str(payload_kind))
    badrole = {k: v.get("role") for k, v in fields.items() if v.get("role") not in ROLES}
    show("전 필드의 role이 닫힌 5종 안", not badrole, str(badrole))
    noecat = [k for k, v in fields.items() if v.get("role") == "entity" and not v.get("category")]
    show("entity 필드에 category 필수", not noecat, str(noecat))
    # edges 참조 무결성
    edges = schema.get("edges", [])
    refs = set()
    for e in edges:
        for side in ("from", "to"):
            t = str(e.get(side, ""))
            refs.add(t[1:] if t.startswith("@") else t)
    unknown = sorted(r for r in refs if r and r not in fields and r not in STRUCT_FIELDS)
    show(f"edges {len(edges)}건의 from/to가 전부 선언된 필드", not unknown, str(unknown))
    # 조각 ↔ 스키마 대조 (인입 검증 ③단계의 드라이런)
    if pieces:
        piece_keys = set().union(*[set(p) for p in pieces])
        unknown_field = sorted(piece_keys - set(fields) - STRUCT_FIELDS
                               - {"text", "section", "meta", "image_ref"})
        show("파서 출력에 스키마 밖 필드 없음 (unknown_field 큐 예상분)",
             not unknown_field, str(unknown_field))
        missing = sorted(k for k, v in fields.items()
                         if not v.get("optional") and k not in STRUCT_FIELDS
                         and not any(p.get(k) not in (None, "") for p in pieces))
        show("필수 필드가 조각에 실제로 채워짐 (missing_field 큐 예상분)",
             not missing, str(missing))
    # role 루프 드라이런 — 핸들러 분기가 전부 도는가
    HANDLED = {r: 0 for r in ROLES}
    unmapped_in_fields = [k for k, v in fields.items() if v.get("role") == "UNMAPPABLE"]
    show("UNMAPPABLE 필드가 스키마 fields에 들어가지 않음 (등록 제외 대상)",
         not unmapped_in_fields, str(unmapped_in_fields))
    for p in (pieces or []):
        for k, spec in fields.items():
            if k in p and p[k] is not None and spec.get("role") in HANDLED:
                HANDLED[spec["role"]] += 1
    print(f"      role 루프 드라이런: " +
          " · ".join(f"{r}={HANDLED[r]}" for r in ["anchor", "entity", "attribute", "content", "meta"]))
    return True


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    adapter_path, schema_path, *docs = sys.argv[1:]
    print("=" * 66)
    print(f"실행 하네스 — {adapter_path}  +  {schema_path}")
    print("=" * 66)
    mod = load_adapter(adapter_path)
    schema = json.load(open(schema_path, encoding="utf-8"))
    if mod is None:
        sys.exit(1)
    show("adapter.doc_type == schema.doc_type",
         mod.ADAPTER.get("doc_type") == schema.get("doc_type"),
         f'{mod.ADAPTER.get("doc_type")} / {schema.get("doc_type")}')
    for d in docs:
        raw = read(d)
        label = d.split("/")[-1]
        preflight(mod, raw, label)
        pieces = run_extract(mod, raw, label)
        check_schema(schema, pieces, label, payload_kind_of(schema, mod))
        if pieces:
            print(f"\n      [조각 1 표본] {json.dumps(pieces[0], ensure_ascii=False)[:300]}")
    print("\n" + "=" * 66)
    print("실행 하네스 결과:", "PASS — 산출물이 파이프라인에서 동작함" if ok_all
          else "FAIL — 위 항목 확인 필요")
    sys.exit(0 if ok_all else 1)
