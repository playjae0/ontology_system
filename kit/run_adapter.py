# -*- coding: utf-8 -*-
"""칸 1.5 — 실행 하네스 — LLM이 산출한 adapter 코드와 매칭 스키마를 **실제로 돌려** 검증한다.

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
from parser import normalizer as normalizer_mod, preflight as preflight_mod, reader as reader_mod
from parser.reader import read

from gate_screen import LINE_RE, SPLIT_MARK, show, _where   # 화면 규격은 저기가 정본이다
import gate_screen
import gate_tables as tables
from gate_tables import (BANNED_IMPORTS, BLOCKS_PATH, G26, G39, NORMALIZER_API,
                         ROLES, SELFMADE, STRUCT_ONLY, load_blocks,
                         structural_fields)
from gate_checks import (check_ledger_coverage, check_schema, check_shapes,
                         check_vocab, payload_kind_of)

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

    # **어휘가 닫힌 자리는 실행 전에 대조한다**(B65 ① · C38의 결). LLM이 없는 함수를
    # 불러도 여기까지는 아무도 모르고, ③단(G31)에 가서야 `AttributeError`로 터진다 —
    # 그 문면은 「무엇이 있나」를 말하지 못해 자동 수정이 안 되고 문답으로 간다
    # (사내 실측: `normalizer.col_to_letter`). 이름은 **정적으로** 대조할 수 있다.
    #
    # **밑줄 이름도 FAIL이다** — 비공개는 계약이 아니다. 오늘 도는 것이 다음 판에
    # 사라져도 아무도 약속을 어긴 것이 아니라, 그때 어댑터만 조용히 죽는다.
    refs = sorted({n.attr for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute)
                   and getattr(n.value, "id", "") == "normalizer"})
    public = sorted(x for x in dir(normalizer_mod) if not x.startswith("_"))
    unknown = [r for r in refs if r.startswith("_") or r not in public]
    show("G1B  normalizer 참조가 실재한다 (없는 이름·비공개 이름 0)",
         not unknown,
         (f"{unknown}는 parser.normalizer에 없다 · 있는 것: "
          f"{' · '.join(NORMALIZER_API)}") if unknown else f"참조 {refs or '0건'}")
    if unknown:
        # **여기서 멈춘다 — 실행할 수 없는 어댑터다.** 뒤 단계를 돌리면 같은 결함이
        # ③단의 `AttributeError`(G31)와 ⑤단의 계약 실패(G52)로 **그림자처럼** 다시
        # 뜨고, 그 줄들은 문면이 답을 담지 않아 처분이 **문답으로 간다** — 사람이
        # 기계 실패를 통역해야 하는 그 자리다(C27). 원인 한 줄만 남기면 자동 수정이
        # 목록 안에서 고른다. **뒤를 빼는 것이 아니라 앞에서 끝내는 것이다.**
        print("   → 로드 단계에서 멈춘다 — 없는 이름을 부르는 어댑터는 실행하지 않는다")
        return None
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


# **열 프로파일은 패키지에 있다**(B64 ② — 새 계산 0). 관문이 그 값을 읽어 FAIL 줄
# 아래 한 줄로 싣는다: 「한 값도 안 읽혔는지」를 사람이 화면에서 바로 안다.
# **라벨 한 자리**(B59 ①) — G26은 한 태그·한 라벨이고 원인은 상세가 가른다.
def _profiles():
    """입력 패키지의 열 프로파일 — 없으면 빈 dict. **계산하지 않는다.**"""
    if not tables.PACKAGE or not Path(tables.PACKAGE).exists():
        return {}
    try:
        pkg = json.load(open(tables.PACKAGE, encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for h in ((pkg.get("system") or {}).get("reader_head") or []):
        for pp in (h.get("열_프로파일") or []):
            for col, item in (pp.get("열") or {}).items():
                out[col] = {**item, "전체_행수": pp.get("전체_행수")}
    return out


def _profile_line(exp, item):
    """FAIL 줄에 붙는 열 프로파일 — 관련 열만, 있으면. 없으면 빈 문자열."""
    prof = _profiles()
    cands = item.get("candidates") or ([item["value"]]
                                       if item["reason"] != "not_found" else [])
    out = ""
    for c in cands:
        pp = prof.get(c)
        if not pp:
            continue
        tot = pp.get("전체_행수")
        sug = (pp.get("기계제안") or {}).get("제안")
        out += (f"\n              {c} 비지 않은 행 {pp.get('비지_않은_행수')}"
                + (f"/{tot}" if tot else "")
                + f" · 고유 {pp.get('고유값수')}"
                + (f" · 기계 제안 {sug}" if sug else ""))
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

    # **격자인가는 `sheets`가 답한다 — `format`이 아니다**(B62 ①-a). 구판은
    # `format != "xlsx"`를 보고 CSV를 통째로 건너뛰었다: 대조하지 않고 PASS를 줬으니
    # CSV table 어댑터는 여기서 초록이고 ⑤단에서 붉는, 가장 나쁜 모양이었다.
    sh, sh_err = reader_mod.sheet_of(raw, exp)
    if sh_err and not raw.get("sheets"):
        return show("G22  격자 포맷 아님 — 헤더 지문 대조 대상 아님", True)
    if sh_err:
        return show("G27  시트가 정해진다 (둘 이상이면 expects.sheet 선언)",
                    False, sh_err["reason"])
    hr = exp.get("header_row")
    if not hr:
        return show("G23  expects.header_row 선언됨", False, "선언 없음")
    # **G26은 세 원인을 가른다**(B64 ②) — 구판은 「header_row 의심」 한 문면으로
    # 「매핑이 틀렸다」와 「행이 틀렸다」를 같이 말했고, 그래서 문답 LLM이 사람에게
    # 「원본이 비었나 매핑이 비었나」를 되물었다(사내 실측). 원인마다 다른 문면 +
    # **그대로 칠 수 있는 다음 값**을 담는다(B61 계약 · AUTO_FIX 대상).
    _cols, bad = preflight_mod.resolve_columns(raw, exp)
    suspect = preflight_mod.header_row_suspect(raw, exp)
    hr_ = exp.get("header_row")
    # **라벨은 태그와 한 몸이다**(B59 ①) — 한 태그에 두 라벨을 두면 사람이 읽어
    # 전달한 코드가 두 가지를 가리킨다. 그래서 G26의 라벨은 하나이고, **원인 셋은
    # 상세가 가른다**: 없음 · 중복 · 빈 헤더.
    for it in bad:
        if it["reason"] == "not_found":
            det = (f"{it['field']}: columns 값 {it['value']!r}는 {hr_}행 헤더에 없다 "
                   f"— 헤더: {it['headers'][:8]}")
        elif it["reason"] == "ambiguous":
            det = (f"{it['field']}: columns 값 {it['value']!r}가 {hr_}행에 "
                   f"{len(it['candidates'])}개 ({' · '.join(it['candidates'])}) — "
                   f"열문자로 지정하거나 {it['candidates']!r}로 합쳐라")
        else:
            det = (f"{it['field']}: {it['value']}열 {hr_}행이 비었다 — "
                   f"header_row 의심")
        show(G26, False, det + _profile_line(exp, it))
    if not bad:
        show(G26, not suspect, (suspect or {}).get("reason", ""))
    actual = preflight_mod.header_labels(raw, hr, exp)
    show(f"G24  header_row {hr}행에 헤더 {len(actual)}개 존재", len(actual) >= 5, str(actual[:4]))
    strings = {reader_mod.norm_label(x) for x in strings}
    missing = [a for a in actual if a not in strings]
    show("G25  원본 헤더 문자열이 전부 expects에 실림 → 표류 감지 가능",
         not missing, f"미포함 {len(missing)}개: {missing}")
    return not missing and not suspect


# ---------------------------------------------------------------- ③ extract
def check_output_keys(schema, pieces, label):
    """**어댑터가 내는 키 ⊆ 스키마 `fields` ∪ 구조 필드** (B72 ① · 템플릿 규약 7).

    이 검사가 없어서 사내 첫 실인입이 「스키마에 없는 필드 'meta'」를 **행마다**
    찍었다 — 어댑터가 meta 열들을 딕셔너리 하나로 묶어 냈고 스키마에는 그 키가
    없었다. 규약 7이 문면으로만 있고 **기계가 재지 않았다**: 등록이 통과시킨 것을
    인입이 큐로 받는다(사람이 판정할 것도 아닌데).

    **문면이 답을 담는다**(AUTO_FIX) — 빠진 이름과 무엇을 하라는지를 함께 낸다.
    반대(선언됐는데 한 번도 안 나오는 필드)는 **경고**다: optional일 수 있고,
    표본에 그 열이 비었을 수도 있다 — 막을 근거가 못 된다.
    """
    if not pieces:
        return True
    fields, _blk = load_blocks(schema)
    known = set(fields) | structural_fields()
    if not structural_fields():
        return show(G39, False, "core/build/loop.py의 STRUCTURAL을 읽지 못했다 — "
                                "관문 자체 결함(어댑터 잘못이 아니다)")
    out_keys = {k for p in pieces for k in p}
    extra = sorted(out_keys - known)
    never = sorted(k for k in fields if k not in out_keys)
    if never:
        # 판정 줄이 아니다 — 앞 판정의 상세로 붙지 않게 들여쓰지 않는다(B64 ②).
        print(f"[경고] {label}: 스키마에 선언됐지만 어댑터가 한 번도 내지 않은 "
              f"필드 {len(never)}종 — {never[:6]} (표본에 그 열이 비었을 수 있다)")
    return show(G39, not extra,
                (f"{extra} · 열마다 fields에 role을 선언하라(meta면 role: meta) · "
                 f"딕셔너리로 묶지 마라 — 지금 스키마의 키: "
                 f"{sorted(fields)[:8]}") if extra else "")


def exc_where(e, mod=None):
    """예외 문면에 **어느 줄에서 죽었는지**를 싣는다 (B76 ④ⓓ).

    사내 실측 열여섯째의 화면은 `TypeError: argument of type 'NoneType' is not
    iterable` 한 줄이었다 — 사람이 원인을 짚을 수 없었고(M9 「실패는 문면이 답을
    담는다」), 허브가 traceback을 재현해서야 자리가 나왔다.

    두 자리를 낸다: **어댑터 파일 안의 마지막 프레임**(사람이 고칠 자리)과
    **traceback의 마지막 프레임**(실제로 죽은 자리 — 공용 코어일 수 있다).
    둘이 같으면 한 번만 적는다.
    """
    import linecache
    import traceback
    tb = traceback.extract_tb(e.__traceback__)
    head = f"{type(e).__name__}: {e}"
    if not tb:
        return head
    src = getattr(mod, "__file__", None)
    picks = []
    if src:
        own = [f for f in tb if Path(f.filename).name == Path(src).name]
        if own:
            picks.append(("어댑터", own[-1]))
    if not picks or tb[-1] is not picks[0][1]:
        picks.append(("마지막", tb[-1]))

    def one(tag, fr):
        line = (fr.line or linecache.getline(fr.filename, fr.lineno) or "").strip()
        return f"{tag} {Path(fr.filename).name}:{fr.lineno}" + (f" `{line[:70]}`" if line else "")

    seen, out = set(), []
    for tag, fr in picks:
        k = (fr.filename, fr.lineno)
        if k in seen:
            continue
        seen.add(k)
        out.append(one(tag, fr))
    return head + " — " + " · ".join(out)


def _none_cell_probe(mod, raw):
    """**셀 하나를 `None`으로 바꿔도 사는가** (B76 ④ⓔ).

    reader가 빈 칸을 `None`으로 주는 포맷이 있고, 어댑터가 셀에 직접
    `strip()`·`in`을 걸면 그 한 칸에 문서 전체가 죽는다. 표본에 빈 셀이 없으면
    G31이 그것을 못 잡으므로 **관문이 만들어서** 잰다.

    돌려주는 것은 `(대상인가, 살았는가, 상세)`다. 격자가 아니면 대상이 아니다.
    """
    import copy
    sheets = raw.get("sheets") or []
    if not sheets:
        return False, True, "격자 아님 — 대상 아님"
    exp = getattr(mod, "ADAPTER", {}).get("expects") or {}
    cols = set()
    for v in (exp.get("columns") or {}).values():
        cols |= set(v if isinstance(v, (list, tuple)) else [v])
    start = int(exp.get("data_start_row") or 1)
    for si, sh in enumerate(sheets):
        for key, val in sorted((sh.get("cells") or {}).items()):
            letters = "".join(ch for ch in key if ch.isalpha())
            digits = "".join(ch for ch in key if ch.isdigit())
            if not digits or (cols and letters not in cols):
                continue
            if int(digits) < start or not str(val or "").strip():
                continue
            probe = copy.deepcopy(raw)
            probe["sheets"][si]["cells"][key] = None
            try:
                mod.extract(probe)
            except Exception as e:
                return True, False, f"{key}를 None으로 두면 {exc_where(e, mod)}"
            return True, True, f"{key} → None"
    return False, True, "바꿀 셀 없음 — 대상 아님"


def run_extract(mod, raw, label, schema=None):
    print(f"\n③ extract 실행 — {label}")
    try:
        pieces = mod.extract(raw)
    except Exception as e:
        # **어디서 죽었는지를 문면이 말한다**(B76 ④ⓓ) — 예외명만으로는 고칠 자리를
        # 짚을 수 없다(사내 실측 열여섯째: G31 한 줄에 파일도 줄도 없었다).
        show("G31  예외 없이 실행", False, exc_where(e, mod))
        return None
    show("G31  예외 없이 실행", True)
    # **빈 칸 한 칸에 죽지 않는가**(B76 ④ⓔ) — 표본에 없으면 관문이 만든다.
    _apply, _alive, _det = _none_cell_probe(mod, raw)
    if _apply:
        show("G3A  셀 하나가 None이어도 산다 (reader가 빈 칸을 None으로 주는 포맷)",
             _alive, _det)
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
    if schema is not None and pk == "table":
        # **table 한정**(규약 7) — prose 조각의 키는 계약 고정 4종이라 대상이 아니다.
        check_output_keys(schema, pieces, label)
    return pieces


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
    문서의 구조 지도 보존(`<상태>/work/struct_maps/`)을 덮어써, 아직 등록도 안 된
    어댑터의 산출이 운영 인입의 chunk_id를 흔든다. 관문이 남긴 자리는 관문이 치운다.
    """
    from parser import pipeline as parser_pipeline      # 지연 import — ①~④는 필요 없다
    from parser import struct_map

    print(f"\n⑤ 파서 전 구간(pipeline.parse) — {label}")
    doc_id = "_gate_" + re.sub(r"[^0-9A-Za-z_]+", "_", f'{schema.get("doc_type")}_{Path(doc).stem}')
    try:
        # 좌표 층은 **건네받은 이름**이 먼저다(B85 ②) — 스키마의 층은 문서의 층이고,
        # 좌표는 골격 층의 닫힌 목록을 본다. 둘이 다른 층일 수 있다.
        res = parser_pipeline.parse(mod, doc_id, doc,
                                    layer=tables.COORD_LAYER or schema.get("layer"))
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
            # **화면을 가진 쪽이 그대로 읽는다**(B68 ② — 새 계산 0). 구판은 240자로
            # 자른 사람용 한 줄뿐이라, 등록 화면이 분할을 말하려면 같은 계산을 다시
            # 해야 했다. 관문은 이미 `pipeline.parse`를 돌렸고 그 산출이 여기 있다.
            # **행 머리에 공백을 두지 않는다** — 들여쓴 줄은 앞 판정 줄의 상세로
            # 붙는 규약이라(B64 ②) 이 줄이 FAIL 상세를 오염시킨다.
            print(SPLIT_MARK + json.dumps(
                {"doc": Path(doc).name,
                 "split": {k: v for k, v in sp.items() if k != "레벨_선택"},
                 "picks": sp.get("레벨_선택") or []}, ensure_ascii=False))
    # **LLM 0** — 주입이 하나도 없었고 게이트웨이 모듈은 적재조차 되지 않았다.
    # 문자열이 아니라 **적재된 모듈**을 본다: 「부르지 않는다」는 주석은 아무것도
    # 막지 않는다(이 레포가 겪은 실사고 그대로).
    show("G54  관문이 LLM을 부르지 않는다 — core.llm 미적재 · 지점 3종 주입 0",
         "core.llm" not in sys.modules and not (set(sys.modules) & {"openai", "anthropic"}),
         str(sorted(m for m in sys.modules if m.startswith("core"))))
    return res


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    _argv = sys.argv[1:]
    if tables.PKG_FLAG in _argv:
        _i = _argv.index(tables.PKG_FLAG)
        tables.PACKAGE = _argv[_i + 1] if _i + 1 < len(_argv) else None
        del _argv[_i:_i + 2]
    if tables.LEDGER_FLAG in _argv:
        _i = _argv.index(tables.LEDGER_FLAG)
        tables.LEDGER = _argv[_i + 1] if _i + 1 < len(_argv) else None
        del _argv[_i:_i + 2]
    if tables.LAYERS_FLAG in _argv:
        _i = _argv.index(tables.LAYERS_FLAG)
        tables.LAYERS_DIR = _argv[_i + 1] if _i + 1 < len(_argv) else None
        del _argv[_i:_i + 2]
    if tables.COORD_FLAG in _argv:                 # 좌표 층의 이름 (B85 ②)
        _i = _argv.index(tables.COORD_FLAG)
        tables.COORD_LAYER = _argv[_i + 1] if _i + 1 < len(_argv) else None
        del _argv[_i:_i + 2]
    adapter_path, schema_path, *docs = _argv
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
    # **형이 틀린 산출은 사람에게 올라가지 않는다**(B76 ①) — 표본보다 먼저 본다.
    check_shapes(schema, mod)
    check_ledger_coverage(schema, mod)                   # G4G (B76 ②)
    for d in docs:
        raw = read(d)
        label = d.split("/")[-1]
        preflight(mod, raw, label)
        pieces = run_extract(mod, raw, label, schema)
        check_schema(schema, pieces, label, payload_kind_of(schema, mod))
        if pieces:
            print(f"\n      [조각 1 표본] {json.dumps(pieces[0], ensure_ascii=False)[:300]}")
        run_pipeline(mod, schema, d, label)          # ⑤ 파서 전 구간 (B58 ②)
    print("\n" + "=" * 66)
    print("실행 하네스 결과:", "PASS — 산출물이 파이프라인에서 동작함" if gate_screen.ok_all
          else "FAIL — 위 항목 확인 필요")
    sys.exit(0 if gate_screen.ok_all else 1)
