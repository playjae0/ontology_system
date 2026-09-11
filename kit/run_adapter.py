# -*- coding: utf-8 -*-
"""실행 하네스 — LLM이 산출한 adapter 코드와 매칭 스키마를 **실제로 돌려** 검증한다.

새 성공 판정(사용자 확정, 2026-08-01):
  "LLM이 코드 안에서 도는가"가 아니라
  "LLM이 내놓은 schema/adapter를 넣었을 때 파이프라인이 실제로 도는가"

검사 5단
  ① adapter 로드    — 문법 오류·ADAPTER 선언 형식·순수성(금지 import) 검사
  ② preflight       — ADAPTER.expects ↔ 실물 지문 대조
  ③ extract 실행    — 조각 산출 · 계약 3층 구조 self-check(validator)
  ④ 스키마 정합     — 스키마 fields ↔ 조각 필드 대조 + role 루프 드라이런
                     (fields의 정답은 payload_kind가 정한다 — prose는 `{}`가 정답, D-31)
  ⑤ 파서 전 구간    — `parser.pipeline.parse`를 그대로 돌린다 (B58 ②)

**⑤가 있는 이유** — ①~④는 `extract`까지만 봤다. 그 뒤의 normalizer·tagger·envelope·
validator는 검수 화면에서 처음 돌았고, 거기서 깨지면 **사내가 기계 오류를 자연어로
통역해 되돌려야** 했다(C27: 사내는 코딩하지 않는다). 관문이 파서 전 구간을 돌면
**검수에서 기계 오류가 날 자리가 없다** — 남으면 그것이 결함이다.

⑤는 **LLM을 부르지 않는다.** 세 지점(④이미지 요약·⑦구조 지도·⑨좌표 태깅)을 주입 없이
돌려 §7.1 무LLM 대체 경로로 보낸다 — 좌표는 닫힌 목록 정확 일치만, 이미지 요약은
고정 문자열이다. **비용 관문은 검수에 그대로 남는다**: 여기서 표본마다 몇천 회를
부르면 관문이 관문이 아니라 청구서가 된다.

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
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from parser.reader import read

ROLES = {"anchor", "entity", "attribute", "content", "meta"}
BANNED_IMPORTS = {"requests", "urllib", "httpx", "openai", "anthropic", "socket"}

# 규약 10(B31) — 자기완결 연산을 어댑터가 재구현하면 여기서 잡는다.
# **AST로 함수 정의를 본다**(문자열 검색이 아니다): 주석·docstring에 이름이 나오는
# 것과 실제로 정의한 것은 다르고, 이 프로젝트는 문자열을 세어 있는 것처럼 보고한
# 실사고를 겪었다.
SELFMADE = {"_expand_merged", "_col_to_idx", "_idx_to_col", "_col", "_resolve_ditto",
            "_split_multi", "_ditto", "_expand_multi"}

# 구조 필드 — role 배정 대상이 아닌 것들(C17). 공용 블록이 선언하지 **않는** 것만 여기 둔다.
# `process_group`·`process_ref`·`process_no`·`source_locator`는 `schemas/blocks.json`이
# 소유하므로 아래에 중복해 적지 않는다 — 적어 두면 블록 파일이 바뀌어도 하네스가 모른다.
STRUCT_ONLY = {"electrode_type", "context", "doc_type", "section"}
BLOCKS_PATH = Path(__file__).resolve().parent.parent / "schemas" / "blocks.json"


def load_blocks(schema, path=None):
    """`use_blocks` 로더 — 스키마가 선언한 공용 블록을 **전개해서** 합친다.

    실행검증_1차 §4.4의 처방이다: 좌표 필드를 `process_coord`에 위임한 스키마는
    `fields`에 좌표가 없어 **role 루프 드라이런의 `anchor`가 0으로 찍혔다**. 스키마는
    옳고 하네스가 미완이었다 — 블록을 조립하지 않으면 anchor 경로가 검사되지 않는다.

    돌려주는 것은 `(합쳐진 fields, 블록 유래 필드명 집합)`이다. 블록 유래 필드는
    **선언된 필드**이므로 `unknown_field` 계산에서 빠지고, role 루프에는 **들어간다.**
    """
    p = Path(path or BLOCKS_PATH)
    blocks = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    merged, from_blocks = dict(schema.get("fields") or {}), set()
    for name in schema.get("use_blocks") or []:
        blk = blocks.get(name)
        if not isinstance(blk, dict):
            continue
        for f, spec in blk.items():
            if f.startswith("_") or not isinstance(spec, dict):
                continue
            from_blocks.add(f)
            merged.setdefault(f, spec)          # 스키마 선언이 블록을 이긴다
    return merged, from_blocks

ok_all = True


# **판정 줄의 문면 규격** (B59 ①) — `[FAIL] G13  <라벨>  — <상세>`.
#
# 코드는 **라벨에 붙은 고정값**이고 순번이 아니다: 단이 늘어도 기존 코드가 밀리지
# 않는다. 있는 이유는 하나다 — **사내는 복사·붙여넣기가 안 되는 환경이라** 실패
# 줄을 밖으로 가져올 수 없었다(실측). 세 글자는 사람이 읽어서 전달할 수 있다.
LINE_RE = r"^\s*\[(PASS|FAIL)\]\s+(G[0-9A-Z]{2})\s\s(.*?)(?:\s\s—\s(.*))?$"


def show(label, ok, detail=""):
    """판정 한 줄. **라벨은 `G\d\w  `로 시작한다** — 그것이 코드다.

    코드 없는 라벨을 만들지 않는다: 화면이 「무엇이 막았나」를 사람이 전달할 수
    있는 형태로 말해야 하고, 빠진 한 줄은 그 줄에서만 조용히 안 말한다.
    """
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
        show("G11  문법 오류 없음", True)
    except SyntaxError as e:
        show("G11  문법 오류 없음", False, str(e))
        return None
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imports.add(n.module.split(".")[0])
    show("G12  순수 함수 계약 — 네트워크/LLM 호출 없음 (§5 규약 2)",
         not (imports & BANNED_IMPORTS), str(sorted(imports & BANNED_IMPORTS)))

    # 규약 10 (B31) — 공용 코어 호출 의무. **기계가 사람 앞에 선다.**
    defs = {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    remade = sorted(defs & SELFMADE)
    show("G13  규약 10 — 자기완결 연산을 재구현하지 않았다 (parser.normalizer 몫)",
         not remade,
         (f"재구현 정의 {remade} — 병합/상동/복수값/열변환은 "
          f"normalizer.expand_merged·resolve_ditto·split_multi를 부른다") if remade else "")
    _kind = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                getattr(x, "id", "") == "ADAPTER" for x in n.targets) and \
                isinstance(n.value, ast.Dict):
            for k, v in zip(n.value.keys, n.value.values):
                if getattr(k, "value", None) == "payload_kind":
                    _kind = getattr(v, "value", None)
    # **table 계열만 의무다** — prose에는 병합·상동·복수값 개념이 없다.
    #
    # **호출을 센다 — 문자열이 아니다.** `"normalizer" in src`로 재면 머리 주석의
    # 「규약 10(공용 코어 호출)」 같은 문면이 잡혀, normalizer를 하나도 부르지 않는
    # 어댑터가 통과한다(실측: 검체 nocore가 그렇게 PASS했다). import는 있는데
    # 부르지 않는 것도 구현이 아니다 — 이 레포의 규율 그대로다.
    calls = sorted({n.func.attr for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and getattr(n.func.value, "id", "") == "normalizer"})
    show("G14  규약 10 — table 계열은 parser.normalizer를 **부른다** (prose는 의무 없음)",
         _kind != "table" or bool(calls),
         f"payload_kind={_kind} · 호출 {calls or '0건'}")
    spec = importlib.util.spec_from_file_location("gen_adapter", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        show("G15  import 성공", False, f"{type(e).__name__}: {e}")
        return None
    show("G15  import 성공", True)
    A = getattr(mod, "ADAPTER", None)
    show("G16  ADAPTER 선언 존재", isinstance(A, dict))
    if isinstance(A, dict):
        show("G17  필수 키 4종 (doc_type·adapter_version·payload_kind·expects)",
             {"doc_type", "adapter_version", "payload_kind", "expects"} <= set(A))
        show("G18  payload_kind가 닫힌 2값", A.get("payload_kind") in ("table", "prose"),
             str(A.get("payload_kind")))
    show("G19  extract 함수 존재", callable(getattr(mod, "extract", None)))
    show("G1A  locate 함수 없음 (§5 규약 1 — 폐지된 인터페이스)",
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
        return show("G21  분할 신호 상수가 expects에 선언됨 (prose는 header_row 대상 아님)",
                    has, f"keys={list(exp)[:6]}")

    if raw["format"] != "xlsx":
        return show("G22  xlsx 아님 — 헤더 지문 대조 대상 아님", True)
    sh = raw["sheets"][0]
    hr = exp.get("header_row")
    if not hr:
        return show("G23  expects.header_row 선언됨", False, "선언 없음")
    actual = [str(sh["cells"].get(f"{get_column_letter(c)}{hr}", "")).strip()
              for c in range(1, sh["max_col"] + 1)]
    actual = [a for a in actual if a]
    show(f"G24  header_row {hr}행에 헤더 {len(actual)}개 존재", len(actual) >= 5, str(actual[:4]))
    missing = [a for a in actual if a not in strings]
    show("G25  원본 헤더 문자열이 전부 expects에 실림 → 표류 감지 가능",
         not missing, f"미포함 {len(missing)}개: {missing}")
    return not missing


# ---------------------------------------------------------------- ③ extract
def run_extract(mod, raw, label):
    print(f"\n③ extract 실행 — {label}")
    try:
        pieces = mod.extract(raw)
    except Exception as e:
        show("G31  예외 없이 실행", False, f"{type(e).__name__}: {e}")
        return None
    show("G31  예외 없이 실행", True)
    show("G32  list[dict] 반환", isinstance(pieces, list) and all(isinstance(p, dict) for p in pieces),
         f"{type(pieces).__name__} / {len(pieces) if isinstance(pieces, list) else '-'}건")
    # **판정이 먼저고 조기 반환이 나중이다.** 구판은 0건일 때 이 줄에 닿기 전에
    # 돌아가서, **아무것도 추출하지 못한 어댑터가 PASS로 통과했다**(실측 — B50에서
    # 「조각 0건」 갈래를 시험하다 드러났다). 검사를 건너뛰는 조기 반환은 그 검사를
    # 없앤 것과 같다.
    show(f"G33  조각 {len(pieces)}건 산출 (0건 아님)", len(pieces) > 0)
    if not pieces:
        return pieces
    locs = [p.get("source_locator") for p in pieces]
    show("G34  전 조각에 source_locator 존재", all(locs))
    show("G35  source_locator가 문서 내 유일 (§5 규약 1)", len(set(locs)) == len(locs),
         f"중복 {len(locs) - len(set(locs))}건")
    show("G36  정본 id를 파서가 부여하지 않음 (chunk_id/record_id 부재 — 틀 A7-1)",
         not any({"chunk_id", "record_id", "doc_hash"} & set(p) for p in pieces))
    pk = mod.ADAPTER["payload_kind"]
    if pk == "prose":
        show("G37  prose 조각에 text 또는 image_ref 존재",
             all(("text" in p) or ("image_ref" in p) for p in pieces))
    # 자기완결성 — 값이 상동 기호/미전개 병합 흔적을 남기지 않았는가
    ditto = [p for p in pieces for v in p.values()
             if isinstance(v, str) and v.strip() in {"〃", "〝", "상동"}]
    show("G38  상동 기호가 해소됨 (계약 ③)", not ditto, f"{len(ditto)}건 잔존")
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
    unknown = sorted(r for r in refs if r and r not in fields and r not in struct)
    show(f"G48  edges {len(edges)}건의 from/to가 전부 선언된 필드", not unknown, str(unknown))
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


# ------------------------------------------------- ⑤ 파서 전 구간 (B58 ②)
# **LLM 지점 3종은 주입하지 않는다** — 이름을 여기 적어 두는 이유는, 나중에 누가
# 「관문에서도 실호출로 봐야 정확하다」며 하나를 꽂으면 관문이 청구서가 되기
# 때문이다. 안 부르는 것이 규격이고, 그 사실을 아래 어서션이 매번 확인한다.
NO_LLM_POINTS = ("summarize", "pick_coord", "map_structure")


def run_pipeline(mod, schema, doc, label):
    """⑤ — `parser.pipeline.parse`를 **그대로** 돌린다. 재구현하지 않는다.

    범위가 ③(extract)에서 여기까지 넓어진 것이 B58 ②다. 관문이 보지 않던
    normalizer·tagger·envelope·validator가 이제 관문 안에서 돈다.

    `doc_id`는 **관문 전용 이름**을 쓴다 — 운영 `doc_id`를 그대로 쓰면 관문이 그
    문서의 구조 지도 보존(`extract/struct_maps/`)을 덮어써, 아직 등록도 안 된
    어댑터의 산출이 운영 인입의 chunk_id를 흔든다. 관문이 남긴 자리는 관문이 치운다.
    """
    from parser import pipeline as parser_pipeline      # 지연 import — ①~④는 필요 없다
    from parser import struct_map

    print(f"\n⑤ 파서 전 구간(pipeline.parse) — {label}")
    doc_id = "_gate_" + re.sub(r"[^0-9A-Za-z_]+", "_", f'{schema.get("doc_type")}_{Path(doc).stem}')
    try:
        res = parser_pipeline.parse(mod, doc_id, doc,
                                    layer=schema.get("layer") or "process")
    except Exception as e:
        show("G51  파서 전 구간이 예외 없이 완주 (normalizer·tagger·envelope·validator)",
             False, f"{type(e).__name__}: {e}")
        return None
    finally:
        struct_map.keep_path(doc_id).unlink(missing_ok=True)

    show("G51  파서 전 구간이 예외 없이 완주 (normalizer·tagger·envelope·validator)", True)
    fails = {f["kind"] for f in res.failures}
    # **구조 미확정은 표시이지 실패가 아니다**(D-5) — 문서는 들어가고 큐가 뜬다.
    # 관문이 이것으로 막으면 지도 폴백을 쓰는 문서는 영영 등록되지 못한다.
    blocking = sorted(fails - {"hierarchy_unresolved"})
    # **결함 원문을 판정 줄에 싣는다**(B59 ②) — 구판은 종류 이름(`['adapter_mismatch']`)만
    # 실었고 사유·상세는 **`[FAIL]`이 아닌 줄**에 찍혀, 문답에 넘어가는 context에
    # 들어가지 않았다. 문답 LLM이 보는 것은 `[FAIL]` 줄뿐이라 「무엇이 어긋났나」를
    # 모른 채 통역해야 했고, 그 통역을 사람에게 떠넘기는 것이 C27 위반이다.
    _why = "; ".join(
        f"[{f['kind']}] {f['reason']}"
        + (f" {json.dumps(f['detail'], ensure_ascii=False)[:200]}" if f.get("detail") else "")
        for f in res.failures if f["kind"] in blocking)
    show("G52  계약 self-check 통과 — validator 결함 0 (뷰 확인에서 날 기계 오류가 여기서 난다)",
         res.ok and not blocking, _why or (str(blocking) if blocking else ""))
    for f in res.failures:
        print(f"      [{f['kind']}] {f['reason']}")
        if f.get("detail"):
            print(f"        {json.dumps(f['detail'], ensure_ascii=False)[:240]}")
    if res.ok:
        env = res.envelope or {}
        show("G53  봉투 3층이 섰다 (header·payload·evidence 또는 그 계약 자리)",
             isinstance(env, dict) and bool(env), f'키 {sorted(env)[:6]}')
        rep = res.report or {}
        co = rep.get("coords") or {}
        # 좌표 목록 밖 이름은 **인입 소관**(orphan_anchor)이라 관문의 실패가 아니다 —
        # 세어서 보이기만 한다. 여기서 막으면 골격에 아직 없는 신설 공정을 담은
        # 문서가 어댑터 결함으로 오인된다.
        print(f"      조각 {rep.get('pieces')}건 · 좌표 보고 {json.dumps(co, ensure_ascii=False)[:200]}")
        sp = rep.get("split") or {}
        if sp:
            print(f"      분할 분포 {json.dumps(sp, ensure_ascii=False)[:240]}")
    # **LLM 0** — 주입이 하나도 없었고 게이트웨이 모듈은 적재조차 되지 않았다.
    # 문자열이 아니라 **적재된 모듈**을 본다: 「부르지 않는다」는 주석은 아무것도
    # 막지 않는다(이 레포가 겪은 실사고 그대로).
    show("G54  관문이 LLM을 부르지 않는다 — core.llm 미적재 · 지점 3종 주입 0",
         "core.llm" not in sys.modules and not (set(sys.modules) & {"openai", "anthropic"}),
         str(sorted(m for m in sys.modules if m.startswith("core"))))
    return res

def _where():
    """**어느 폴더의 어느 판으로 돌았나** — 한 줄 (B59 ④).

    사내가 코드 폴더를 나눠 가며 갱신한다. 같은 표본에서 다른 결과가 나오면 가장
    먼저 가려야 할 것이 「어느 사본이 돌았나」인데, 상대 경로만 남으면 그것이
    갈리지 않는다. 그래서 **절대 경로 + 커밋**을 관문 산출의 첫 줄에 박는다.

    `state.json`의 경로가 상대인 것은 그대로 둔다 — 그건 옳다(폴더를 옮겨도 같은
    문서다 · D-110). 여기 찍는 것은 **실행 환경의 신원**이지 자산의 주소가 아니다.

    git이 없거나 레포가 아니어도 조용히 넘어간다 — 관문이 이것 때문에 멈추면 안 된다.
    """
    rev = ""
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5,
                           cwd=str(ROOT))
        if r.returncode == 0 and r.stdout.strip():
            rev = r.stdout.strip()
            d = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=5,
                               cwd=str(ROOT))
            if d.returncode == 0 and d.stdout.strip():
                rev += "+dirty"          # 커밋만 찍으면 미커밋 수정이 숨는다
    except Exception:
        pass
    return f"[관문] ROOT={ROOT}" + (f" · git {rev}" if rev else " · git 미확인")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    adapter_path, schema_path, *docs = sys.argv[1:]
    print(_where())
    print("=" * 66)
    print(f"실행 하네스 — {adapter_path}  +  {schema_path}")
    print("=" * 66)
    mod = load_adapter(adapter_path)
    schema = json.load(open(schema_path, encoding="utf-8"))
    if mod is None:
        sys.exit(1)
    show("G01  adapter.doc_type == schema.doc_type",
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
        run_pipeline(mod, schema, d, label)          # ⑤ 파서 전 구간 (B58 ②)
    print("\n" + "=" * 66)
    print("실행 하네스 결과:", "PASS — 산출물이 파이프라인에서 동작함" if ok_all
          else "FAIL — 위 항목 확인 필요")
    sys.exit(0 if ok_all else 1)
