# -*- coding: utf-8 -*-
"""n6 구축 모드 등록 파이프라인 — doc_type 등록의 3단 (파서_명세 §6·§7 · 틀 §2).

    ① 생성  입력 패키지(사람 4 + 시스템 5) → reader head 공급 → 어댑터·스키마 초안
    ② 뷰 확인  기계 관문(실행 하네스)이 먼저 거르고, 사람은 그 뒤 뷰를 본다 → 재생성 루프
    ③ 확정  승인 1회 → doc_type 등록부 등재

**틀 §2가 정한 검수 수준**: 사람은 코드가 아니라 **결과 뷰**를 보고, 통과는 승인 1회다.
그래서 ②가 두 겹이다 — **기계가 먼저 거르고**(하네스), 사람은 그 뒤에 뷰를 본다.
기계 관문이 없으면 사람이 문법 오류를 읽는 자리로 내려앉는다.

**"무수정 = 자동 통과"는 금지다.** 승인자 없이는 등재하지 않는다.

경계:
  · 하네스는 `kit/run_adapter.py`를 **호출**한다 — 재작성하지 않는다.
  · 렌더러는 `kit/render_review.py`를 **호출**한다 — 뷰 데이터 스키마(D-79)가 계약이고
    여기는 산출자다. 스키마가 부족하면 고치는 것이 아니라 멈추고 보고할 자리다.
  · **층 초안 구획은 없다** — 층 등록(R1)은 국면 2 게이트이고 여기는 doc_type 전용이다.

사용:
  python cli/register.py generate <doc_type> <층> <표본...> [--hint "..."] [--interview]
       --hint       자유 텍스트. 표본만으로 안 보이는 것을 적는다("3~7행 병합은 위 값 채움")
       --interview  생성 전에 LLM의 **이해 요약**을 보고 교정한다 — 끝내는 것은 사람이다
       --no-fewshot 참조 어댑터 주입을 끈다(스켈레톤 본문은 유지) — 컨텍스트가 좁을 때
       --resume     기존 입력 패키지로 **초안만** 다시 받는다 (문답을 다시 하지 않는다)
  python cli/register.py generate <doc_type> --resume
       └ resume은 **doc_type 하나만** 필요하다 — 층·표본은 패키지에서 읽는다
       --no-basic   표본이 전부 산문 포맷이어도 **LLM 생성으로 간다** — 기본은 고정
                    어댑터를 권하고 묻는다(B59 ③). 비대화형이면 고정 어댑터로 간다
       --use-basic  분할 자명 계열(PPT)은 LLM 생성을 건너뛰고 **기본 어댑터를 정본으로**
                    등재 경로에 놓는다 (§6.4-5) — 검수·승인 1회는 그대로다(M4)
       --drop-interview  이전 문답을 **버린다.** 기본은 이어가기다 — 사람의 답은
                    다시 만들 수 없는 재료라, 버리는 쪽이 명시를 요구한다(B55)
       --revise     **등록분의 새 판.** 이름은 그대로이고 확정이 정본을 교체하며
                    revision이 오른다. 승인 기록은 누적한다 (H27)
       --as <이름>  **변형 등록.** 기존 doc_type은 그대로 두고 새 이름으로 간다
  python cli/register.py review   <doc_type> [--instruct "수정 지시"] [--rows N|all]
       --rows       리허설 파싱을 앞 N행으로 제한 (기본 200 · 전량은 all)
       --llm-coord / --no-llm-coord   좌표 LLM 보조를 미리 정한다 (기본: 물어본다)
       --extract / --no-extract       prose 추출 리허설을 미리 정한다 (기본: 물어본다)
  python cli/register.py confirm  <doc_type> --by <승인자>
  python cli/register.py status   <doc_type>   ← 관문이 막는 이유와 **다음 줄**
  python cli/register.py list
"""
from __future__ import annotations

import importlib.util
import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from core import paths
from core.llm import llm
from core.state import fixtures, log, registry, store
from parser import pipeline, preflight, profile, reader, tagger
from parser.normalizer import _col
from parser import form
from parser.adapters import basic_ppt, basic_prose_xlsx
from kit.render_review import render
from kit.run_adapter import load_blocks
from router import discover

# **분할 뒤 재수출** — 등록 흐름은 여기 남고, 조립·문답은 제 모듈로 갔다.
# 이름을 그대로 내보내는 이유: 테스트와 외부가 `cli.register.<이름>`으로 부른다.
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.parse import injections               # 주입 조립은 한 자리다(B48)
from cli.interview import (  # noqa: F401
    INTERVIEW_SCHEMA, INTERVIEW_STOP, _interview_round, _prof_hint, _interview,
    finalize as iv_finalize)

REVIEW = paths.review()
KIT = ROOT / "kit"
FIXTURES = fixtures.ROOT_DIR / "fixtures"   # 소재는 core/state/fixtures.py가 소유

# D-22 확장 문구 — 표본 1부 등록의 경고. **문면이 규격이다.**
SOLO_WARNING = ("표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음**. "
                "1부 등록의 선언 edges는 특별 확인 대상이다")
EXCERPT = 3                                   # 정상 조각 발췌 건수(전량은 접힘에 실린다)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _state(doc_type):
    p = _dir(doc_type) / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_state(doc_type, st):
    (_dir(doc_type) / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ================================================================ ⓪ role 실험
ROLE_HINTS = {
    "anchor": ("공정·설비 좌표", ("공정", "라인", "설비", "호기", "process")),
    "entity": ("이름을 갖고 구별되는 것", ("항목", "설비", "모드", "원인", "부품")),
    "attribute": ("값", ("규격", "값", "치수", "온도", "압력", "속도", "주기",
                         "기준", "심각도", "등급", "번호")),
    "content": ("자유 서술", ("조치", "대응", "계획", "설명", "비고", "내용", "방법")),
    "meta": ("관리 정보", ("작성", "승인", "판번", "개정", "일자", "문서번호")),
}

# **자재 열은 개체로 만들지 않는다** (갭 spec-A-103 · role-104).
# 자재/BOM은 **3번째 층 후보**이고(미결 R5) 지금 층에는 대응 카테고리가 없다 —
# Property로 배정하면 "관리·측정되는 항목"이 아닌 것이 그 카테고리에 섞이고,
# entity로 배정하면 층이 서기 전에 노드가 생겨 나중에 이관 대상이 된다.
# **관찰 항목이다**: 자재 열이 실제로 얼마나 자주 나오는지가 R5 판정의 재료다.
MATERIAL_KEYS = ("자재", "소재", "부품", "원료", "BOM", "품번", "자재번호")


def cmd_roles(args):
    """**⓪ role 배정 실험** — 등록 세션 **진입 전에** 돈다 (갭 spec-A-201 · role-136).

        python -m cli.register roles <문서.xlsx> [헤더행]

    **실행만 하고 등록부는 건드리지 않는다.** 문서의 열 이름 전량에 role 5종 +
    UNMAPPABLE 배정을 시도해 보고, **어디서 막히는지**를 먼저 본다. 이것 없이
    `register generate`로 가면 생성 세션이 무엇을 물어볼지 모른 채 시작한다.

    **추측을 답으로 내놓지 않는다** — 여기서 나오는 것은 **제안**이고, 확정은
    검수 뷰의 6지선다에서 사람이 한다(문서 6 §6.5). 그래서 확신이 없는 열은
    `UNMAPPABLE`로 남기고 **질문 형태로** 표시한다.
    """
    if not args:
        raise SystemExit("문서를 달라: python -m cli.register roles <문서.xlsx> [헤더행]")  # [사용법]
    path = args[0]
    hrow = int(args[1]) if len(args) > 1 else 3
    raw = reader.read(path)
    from parser.preflight import header_labels
    try:
        labels = header_labels(raw, hrow)
    except Exception as e:
        print(f"[roles] 헤더를 못 읽었다 ({type(e).__name__}: {e}) — 헤더 행을 지정해라")
        return 1
    if not labels:
        print(f"[roles] {hrow}행에 헤더가 없다 — 비정형이거나 행 번호가 다르다")
        return 1

    blocks = json.loads(paths.blocks().read_text(encoding="utf-8"))
    block_fields = {f for b, spec in blocks.items() if not b.startswith("_")
                    for f in spec}

    print(f"■ role 배정 실험 — {path} (헤더 {hrow}행 · {len(labels)}열)")
    print("  **실행만 한다 — 등록부를 건드리지 않는다.** 확정은 **뷰 확인**의 6지선다다.\n")
    rows, unmapped, materials = [], [], []
    for lab in labels:
        s = str(lab)
        best, why = None, None
        for role, (desc, keys) in ROLE_HINTS.items():
            if any(k in s for k in keys):
                best, why = role, desc
                break
        if any(k in s for k in MATERIAL_KEYS):
            best, why = ("content", "**자재 열** — 개체로 만들지 않는다 "
                                    "(3번째 층 후보 · 미결 R5). meta도 가능")
            materials.append(s)
        if s in block_fields or any(k in s for k in ("공정구분", "공정명", "공정번호")):
            best, why = "(공용 블록)", "process_coord·common_core가 준다 — 스키마에 다시 안 쓴다"
        if best is None:
            unmapped.append(s)
            best, why = "UNMAPPABLE", "**사람에게 질문** — 5종 어디에도 안 맞는다"
        rows.append((s, best, why))
    w = max(len(r[0]) for r in rows) + 2
    for s, role, why in rows:
        print(f"  {s:<{w}} {role:<12} {why}")

    print(f"\n  배정 제안 {len(rows) - len(unmapped)}/{len(rows)} · "
          f"**UNMAPPABLE {len(unmapped)}**")
    if materials:
        print(f"  **자재 열 관찰 {len(materials)}건**: " + " · ".join(materials))
        print("  → 개체로 만들지 않는다. 빈도가 쌓이면 3번째 층(R5) 판정의 재료다.")
    if unmapped:
        print("  질문할 열: " + " · ".join(unmapped))
        print("  → 이 열들이 생성 세션의 첫 안건이다. 답을 준비하고 register generate로.")
    else:
        print("  → 막히는 열이 없다. register generate로 진행해도 된다.")
    return 0


# ================================================================ ① 생성
def draft(doc_type, revision=0, *, instruction=None, history=None):
    """어댑터·매칭 스키마 **초안** — USE_MOCK은 fixture 반환이다 (D-10 · D-26).

    **`instruction`은 모델에 닿아야 한다**(B55 ①). 구판은 지시를 `st["instructions"]`에
    **기록만** 하고 `draft(doc_type, revision)`로 넘겨, 실호출 갈래는 같은 입력 패키지를
    다시 받았다 — 「실패 문면을 그대로 지시로」(문서 6 §6.5)와 「지시는 사람 것이지만
    산출은 LLM 것이다」([정정] 40)가 둘 다 공문이었다. mock은 `{doc_type}_rev{N}`이라는
    **다른 파일**을 돌려주므로 루프가 도는 것처럼 보였고 그래서 어서션이 초록이었다.

    `history`는 누적 지시 전량이다 — 2회차 지시가 1회차를 덮으면 사람이 같은 교정을
    다시 적게 된다.

    fixture는 "미리 만든 정답"이 아니라 **외부 세션에서 실제 LLM이 산출한 결과물의
    스냅샷**이다. 사람이 손으로 써서 넣으면 그 리허설은 아무것도 검증하지 않는다.
    재생성 지시가 오면 대안본(`…_rev1`)을 반환해 **루프 배선을 검증**한다.

    분기는 `if USE_MOCK: <fixture> else: <실호출>`이고 **반환 형태가 같다** —
    `(어댑터 경로, 스키마 경로)`. 소비 쪽(하네스·검수 뷰)은 출처를 몰라도 된다.
    실호출 갈래도 파일로 떨어뜨린다: 하네스가 실행으로 판정하는 대상이 파일이고,
    승인 기록(approval.json)이 가리키는 것도 파일이다.
    """
    if llm.use_mock():
        llm.mock("generate", f"fixture {doc_type} rev{revision}")
        # **mock에서도 지시문을 조립해 덤프한다**(플래그가 켜졌을 때만) — 조립이
        # 맞는지는 실호출 여부와 무관한 관측 대상이고, 사내에서 실호출 전에
        # 확인할 수 있어야 한다. fixture 반환 자체는 바뀌지 않는다.
        pkg = REVIEW / doc_type / "input_package.json"
        if os.environ.get("ONTO_DUMP_PROMPT") == "1" and pkg.exists():
            _dump_prompt(doc_type, _render_template(
                generate_template(),
                json.loads(pkg.read_text(encoding="utf-8")),
                regeneration=instruction_items(instruction, history)))
        for stem in ([f"{doc_type}_rev{revision}"] if revision else []) + [doc_type]:
            ad = FIXTURES / "adapters" / f"{stem}.py"
            sc = FIXTURES / "schemas" / f"{stem}.json"
            if ad.exists() and sc.exists():
                return ad, sc
        return None, None
    return _draft_live(doc_type, revision,
                       instruction=instruction, history=history)


# **구조화 출력의 strict 요건**(B44): 최상위·중첩을 막론하고 모든 object에서
# `required`가 `properties`의 전 키를 포함해야 하고 `additionalProperties: false`여야
# 한다. **자유 키 사전은 쓸 수 없다** — 실측 400: *"'required' is required to be
# supplied and to be an array including every key in properties.
# Missing 'attribute_ranking'"*.
#
# **못 채울 수 있는 필드는 required에서 빼지 않고 타입을 null 허용으로 연다** —
# 빼면 그 순간 strict 위반이 되고, 게이트웨이는 그 이유를 400 본문에만 적는다.
_ROLES = ("anchor", "entity", "attribute", "content", "meta", "unmappable")

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "adapter_py": {"type": "string"},
        "schema_json": {"type": "string"},
        # 자유 키 사전 → **고정 키**(B44). role은 닫힌 6종이라 고정할 수 있다.
        "role_counts": {
            "type": "object",
            "properties": {r: {"type": "integer"} for r in _ROLES},
            "required": list(_ROLES),
            "additionalProperties": False,
        },
        "attribute_ranking": {
            "type": "array",
            "items": {
                "type": "object",
                # 한글 키 `근거` → `reason` (B44 — 소비처도 함께 고쳤다)
                "properties": {"field": {"type": "string"},
                               "rank": {"type": "integer"},
                               "reason": {"type": "string"}},
                "required": ["field", "rank", "reason"],
                "additionalProperties": False,
            },
        },
        "confidence_cut": {"type": ["integer", "null"]},
        # **안 쓰는 열도 판정을 갖는다**(C19 개정 · B49). 부재로 추론하지 않는다 —
        # 차집합은 「판정해서 뺀 열」·「판단이 안 선 열」·「생성이 빠뜨린 열」 셋을
        # 가르지 못한다. `kind`의 닫힌 2값은 **enum으로 잠그고 코드가 다시 검증한다**
        # (게이트웨이가 enum을 무시해도 조용히 흐르지 않게 — `unmappable_of`).
        "unmappable": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"field": {"type": "string"},
                               "kind": {"type": "string",
                                        "enum": ["excluded", "undecided"]},
                               "reason": {"type": "string"}},
                "required": ["field", "kind", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["adapter_py", "schema_json", "role_counts",
                 "attribute_ranking", "confidence_cut", "unmappable"],
    "additionalProperties": False,
}

# **role 집계 3종** — 「어느 열이 무슨 role인가」를 재는 값들이라 **표 계열에서만
# 뜻이 있다.** prose 조각에는 열이 없다(고정 키 4종은 payload 구조 필드다 — D-31).
ROLE_KEYS = ("role_counts", "attribute_ranking", "confidence_cut")


def generate_schema(payload_kind):
    """계열별 산출 스키마 (B58 ⑥) — **prose에서는 role 집계를 요구하지 않는다.**

    구판은 한 벌뿐이었고 `required`가 셋을 강제했다. **스키마 `required`는 모델이
    빠져나갈 수 없는 자리라**, 열이라는 것이 없는 산문 문서에서 모델이 **있지도
    않은 role 집계를 지어내야 했다.** 템플릿 문면과 달리 이것은 실해악이다 —
    지어낸 값이 검수 뷰의 「갈린 열」·「경계선 부근」 화면에 그대로 실린다.

    **`required`에서만 빼지 않고 `properties`에서도 뺀다.** strict 요건이
    「`required`는 `properties`의 전 키를 포함」이라(B44 실측 400), 한쪽만 줄이면
    게이트웨이가 요청을 통째로 거부한다. 「선택 항목」이라는 개념이 없는 스키마다.

    계열의 출처는 **형태 판정 하나다**(문서 1 C37) — 여기서 따로 재지 않는다.
    """
    if payload_kind == "table":
        return GENERATE_SCHEMA
    return {**GENERATE_SCHEMA,
            "properties": {k: v for k, v in GENERATE_SCHEMA["properties"].items()
                           if k not in ROLE_KEYS},
            "required": [k for k in GENERATE_SCHEMA["required"]
                         if k not in ROLE_KEYS]}


def payload_kind_of_samples(samples):
    """표본의 계열 — `table` · `prose` · `None`(판정이 안 섰다).

    **판정기는 한 자리다**(`parser/form.py`) — 계열을 여기서 따로 재면 등록
    화면·인입 기록·산출 스키마가 서로 다른 답을 낼 수 있다.

    `.pptx`·`.pdf`는 포맷이 이미 prose를 함의한다(§6.4-5). 격자 포맷인데 판정이
    자동으로 서지 않으면 `None`이고, **그때도 role 집계를 강요하지 않는다** —
    산문일 수 있는 문서에 지어내게 하는 것이 이 항목이 없애려는 해악이고,
    표라면 모델이 못 채워도 검수 뷰가 그 자리를 비워 둘 뿐이다(복구 가능).
    """
    kinds = set()
    for smp in samples:
        sfx = Path(str(smp)).suffix.lower()
        if sfx in reader.PROSE_EXT:
            kinds.add("prose")
            continue
        if sfx not in reader.GRID_EXT:
            kinds.add(None)
            continue
        try:
            kinds.add(form.judge(reader.read(str(smp)))["verdict"])
        except Exception:
            kinds.add(None)
    return kinds.pop() if len(kinds) == 1 else None


def _rel(p):
    """상태에 싣는 경로 — **자리 기준의 상대 경로**다(B78 1b · 상태 루트 무관).

    `registry/` 아래면 registry 기준, 레포 아래면 레포 기준, 둘 다 아니면 절대 경로
    그대로다(`ONTO_FIXTURES`는 레포 밖을 가리킬 수 있고 구판은 그때 `relative_to`가
    죽었다 — 실측). 되읽는 자리는 `_at()` 하나다.
    """
    for base in (paths.registry(), ROOT):
        try:
            return p.relative_to(base)
        except ValueError:
            continue
    return p


_at = registry.at      # 되읽는 규칙의 자리는 등록부 소유자다(쓰는 쪽과 갈리지 않게)


def _note_error(doc_type, e):
    """실패하면 **원인이 적힌 유일한 자리**를 남긴다 — `review/{}/last_error.json`.

    게이트웨이의 400 본문은 화면을 스쳐 지나가고 로그는 다음 실행에 묻힌다.
    검수 디렉터리에 남겨야 사람이 그 문서를 다시 볼 때 함께 본다.
    **인증 헤더·키는 남기지 않는다** — `core/llm/llm.py`가 애초에 담지 않는다.
    """
    if not llm.LAST_ERROR:
        return
    d = _dir(doc_type)
    (d / "last_error.json").write_text(
        json.dumps({**llm.LAST_ERROR, "예외": f"{type(e).__name__}: {e}"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   [오류] 게이트웨이 응답을 남겼다 → "
          f"{(d / 'last_error.json').relative_to(ROOT)}")


def _pretty_json(obj, indent=2):
    """**가장 안쪽 dict/list를 한 줄로** 낸 JSON 문자열 (요청 ①).

    매칭 스키마는 사람이 검수 화면과 나란히 읽는 자산이다. 표준 `indent=2`는
    `{"role": "entity", "category": "Unit"}` 같은 **잎 하나를 세 줄로** 벌려 놓아,
    열이 40개면 화면이 120줄이 된다 — 배정표를 훑는 눈이 그 사이에서 길을 잃는다.
    컨테이너를 더 품지 않은 것만 접는다: 구조는 보이고 잎은 한 줄이다.

    **`json.load` 결과는 이전과 완전히 같다** — 바뀌는 것은 공백뿐이다.
    `data/` 저장 레코드는 이 함수를 타지 않는다(`core/state/store.py`의 소관이고,
    거기는 바이트 동일 판정이 걸려 있다).
    """
    def leaf(o):
        return not any(isinstance(v, (dict, list))
                       for v in (o.values() if isinstance(o, dict) else o))

    def go(o, d):
        pad, pad2 = " " * (indent * d), " " * (indent * (d + 1))
        if isinstance(o, dict):
            if not o:
                return "{}"
            if leaf(o):
                return json.dumps(o, ensure_ascii=False)
            body = ",\n".join(f"{pad2}{json.dumps(k, ensure_ascii=False)}: "
                               f"{go(v, d + 1)}" for k, v in o.items())
            return "{\n" + body + "\n" + pad + "}"
        if isinstance(o, list):
            if not o:
                return "[]"
            if leaf(o):
                return json.dumps(o, ensure_ascii=False)
            body = ",\n".join(f"{pad2}{go(v, d + 1)}" for v in o)
            return "[\n" + body + "\n" + pad + "]"
        return json.dumps(o, ensure_ascii=False)

    return go(obj, 0) + "\n"


def _ad_mod(name):
    """코어 기본 어댑터 모듈 — 래퍼가 무엇을 위임할 수 있나를 실물에 묻는다."""
    return {"basic_ppt": basic_ppt, "basic_prose_xlsx": basic_prose_xlsx}.get(
        name) or __import__(f"parser.adapters.{name}", fromlist=[name])


def _write_schema(path, text):
    """매칭 스키마를 **사람이 읽는 표기**로 쓴다. 파싱 실패면 원문 그대로 둔다.

    LLM 산출이 깨진 JSON일 수 있다 — 그때 표기를 고치겠다고 내용을 잃으면 안 된다.
    원문 보존이 우선이고 미화는 그다음이다.
    """
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        path.write_text(text, encoding="utf-8")
        return False
    path.write_text(_pretty_json(obj), encoding="utf-8")
    return True


def instruction_items(instruction, history=None):
    """지시 **목록만** 만든다 — 구획 머리와 안내 문장은 **템플릿의 것이다**.

    모델에게 하는 말은 지시문 파일에 산다(문서 7 §7.6-B-5 · B18이 세운 「고정 문장은
    파일 · 가변 값은 주입」 경계). 코드가 채우는 것은 값뿐이고, 없으면 빈 리스트라
    렌더가 구획째 걷어낸다(초회에는 구획 자체가 없다).

    **입력 패키지 파일을 다시 쓰지 않는다.** 재현 조건의 그릇은 `human.hint`이고
    (B36), 지시는 그 그릇에 이미 `instructions`로 남아 있다 — 여기서 파일을 고치면
    「패키지가 입력의 정본」이라는 규율과 지시 이력이 두 자리로 갈린다.

    누적 지시를 **먼저** 놓고 이번 지시를 마지막에 둔다 — 모델이 가장 최근 교정을
    마지막에 읽게 하되, 앞선 교정을 잊지 않게 한다(2회차가 1회차를 덮으면 사람이
    같은 것을 두 번 적는다).
    """
    prev = [h for h in (history or [])
            if (h.get("instruction") or "").strip()
            and (h.get("instruction") or "").strip() != (instruction or "").strip()]
    items = [f"- ({h.get('n', '?')}회 · {h.get('by', '?')}) "
             f"{(h.get('instruction') or '').strip()}" for h in prev]
    if (instruction or "").strip():
        items.append(f"- **이번 지시** — {instruction.strip()}")
    return items


def _draft_live(doc_type, revision, *, instruction=None, history=None):
    """지점 ⑤의 실호출 갈래 — 생성 LLM에 입력 패키지를 넘긴다.

    입력 패키지(사람 4 + 시스템 5)는 이미 `input_package.json`으로 서 있다 —
    그것이 프롬프트의 입력이고, 여기서 새로 만들지 않는다.

    산출은 **`review/{doc_type}/`에 떨어뜨린다** — `mock/fixtures/`가 아니다.
    fixtures는 외부 LLM 실산출 스냅샷 전용이고 사람도 코드도 손대지 않는 자리다
    (문서 7 §7.5-4 — 디렉터리 경계가 지위 경계다).
    """
    llm.require("generate")          # 설정 미비를 먼저 알린다 — 준비 순서가 그쪽이 먼저다
    pkg = REVIEW / doc_type / "input_package.json"
    if not pkg.exists():
        raise SystemExit(f"[생성] 입력 패키지가 없다: {pkg} — "                  # [상태]
                         f"생성 전에 서야 한다 (근거 review/{doc_type}/"
                         f"input_package.json 없음)\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")
    raw_pkg = pkg.read_text(encoding="utf-8")
    # **지시는 지시문의 자리에 «치환»된다** — user는 패키지 JSON 그대로여야 「입력의
    # 정본은 패키지」가 유지되고(아래 주석), 지시는 그 입력을 어떻게 다시 다루라는
    # 말이라 지시문의 몫이다. 렌더 뒤에 이어 붙이면 그 문장이 다시 템플릿 밖에
    # 사는 것이고, 그것이 이 회차가 고친 결함이다.
    system = _render_template(generate_template(),
                              json.loads(raw_pkg),
                              regeneration=instruction_items(instruction, history))
    _dump_prompt(doc_type, system)          # ONTO_DUMP_PROMPT=1일 때만
    # user 메시지는 **원본 패키지 JSON 그대로** 보낸다 — 치환은 지시문의 일이고
    # 입력의 정본은 패키지다. 둘을 섞으면 어느 쪽이 정본인지 갈린다.
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": raw_pkg}]
    _sent_size(msgs, f"생성 초안 {doc_type}")
    try:
        # **계열이 스키마를 가른다**(B58 ⑥) — prose에는 role 집계를 요구하지 않는다.
        _kind = payload_kind_of_samples(
            (json.loads(raw_pkg).get("human") or {}).get("samples") or [])
        out = llm.chat(msgs, json_schema=generate_schema(_kind), point="generate")
    except Exception as e:
        _note_error(doc_type, e)
        raise
    d = _dir(doc_type)
    suffix = f"_rev{revision}" if revision else ""
    ad = d / f"adapter{suffix}.py"
    sc = d / f"schema{suffix}.json"
    ad.write_text(out["adapter_py"], encoding="utf-8")
    # **`unmappable`은 코드가 스키마에 병합한다**(B49). 모델에게 `schema_json`
    # 문자열 **안에** 직접 넣게 하면 두 자리(최상위 키와 문자열 속)가 어긋날 때
    # 어느 쪽이 정본인지 정해지지 않는다 — 산출은 최상위 키 하나로 받고 병합은
    # 결정적 코드가 한다. **깨진 JSON이면 원문을 보존한다**(_write_schema와 같은 규율).
    sc_text = out["schema_json"]
    if out.get("unmappable") is not None:
        try:
            obj = json.loads(sc_text) if isinstance(sc_text, str) else dict(sc_text)
            obj["unmappable"] = out["unmappable"]
            sc_text = json.dumps(obj, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError, ValueError):
            store.append_defect(
                f"{doc_type}: schema_json이 JSON이 아니라 unmappable을 병합하지 못했다")
    _write_schema(sc, sc_text)
    # **랭킹·경계선·통계는 산출의 일부다** — 파일 둘로는 담기지 않아 상태에 남긴다.
    # 검수 뷰가 이것으로 「갈린 열」과 「경계선 부근」을 먼저 보인다(B39 ③).
    meta = {k: out[k] for k in ("role_counts", "attribute_ranking", "confidence_cut")
            if out.get(k) is not None}
    if meta:
        st = _state(doc_type) or {}
        st["generation_report"] = meta
        _save_state(doc_type, {**st, "doc_type": doc_type})
    return ad, sc


def _all_prose(samples):
    """표본이 **전부** 산문 포맷인가 (B59 ③).

    `.pptx`·`.pdf`는 포맷이 prose를 함의하고(§6.4-5), 격자 포맷은 **형태 판정이
    prose라고 말할 때만** 그렇다(문서 1 C37). 「전부」를 요구하는 이유: 섞이면
    어느 어댑터를 위임할지가 갈리고, 그 판단은 사람 몫이다.

    계열의 출처는 형태 판정 하나다 — 여기서 다시 재지 않는다.
    """
    return bool(samples) and payload_kind_of_samples(samples) == "prose"


def refuse_regenerate(doc_type, st, what):
    """고정 어댑터 doc_type은 **재생성 대상이 아니다** — 상태 거부 (B65 ④ · §6.5).

    `generate`가 산문 포맷을 고정 어댑터로 보낸 뒤(B59 ③), 같은 doc_type에
    `review --instruct`나 `generate --revise`를 치면 구판은 `use_basic`을 보지 않고
    `draft()`로 **LLM 재생성**에 들어갔다 — 명세가 「prose는 생성 세션이 없다」고 한
    자리에서 고정 어댑터가 LLM 산출로 바뀌어치기된다.

    막되 **다음 줄 셋**을 준다(B61 계약): 분할·판독은 어댑터 상수, 매칭은 스키마,
    LLM 생성으로 가려면 새 이름이다.
    """
    mod = Path(str(st.get("adapter") or "")).name or "basic_*"
    prop = (st.get("basic_adapter_proposal") or {}).get("adapter") or ""
    base = Path(prop).name or mod
    raise SystemExit(                                                     # [상태]
        f"[{what}] 재생성 대상이 아니다 — '{doc_type}'은 고정 어댑터"
        f"({base})로 등록됐다 (§6.5 — prose는 생성 세션이 없다)\n"
        f"  ▶ 다음 줄 — 셋 중 하나:\n"
        f"     (분할·판독을 바꾼다)   {prop or 'parser/adapters/basic_*.py'} 의 상수 "
        f"— 구조도 06 손잡이 2.6\n"
        f"     (매칭 스키마를 바꾼다) {paths.schemas(doc_type + '.json')} 을 고치고  "
        f"python -m cli.register status {doc_type}\n"
        f"     (LLM 생성으로 바꾼다) python -m cli.register generate {doc_type} "
        f"{st.get('layer') or '<층>'} <표본...> --as <새이름> --no-basic")


def _refuse_basic(doc_type, layer, samples):
    """고정 어댑터 제안이 서지 않는다 — **`--use-basic`과 사람의 답이 같은 말이다**.

    문면이 한 자리인 이유(B65 ⑤): 플래그로 온 길과 물어서 온 길이 **다른 문면으로
    거부하면** 사람은 두 가지가 다른 일이라고 읽는다. 답이 곧 플래그다.
    """
    raise SystemExit(                                                     # [상태]
        f"[생성] 고정 어댑터 거부 — 기본 어댑터 제안이 서지 않는 표본이다: "
        f"분할 자명 계열이 아니다 {[Path(s).name for s in samples]} (§6.4-5)\n"
        f"  근거 — 표본의 분할 신호 · 기본 어댑터 목록 adapters/basic_*.py\n"
        f"  ▶ 다음 줄 — LLM 생성 경로로 등록한다:\n"
        f"     python -m cli.register generate {doc_type} {layer} "
        f"{' '.join(str(x) for x in samples)} --no-basic")


def form_block(samples):
    """격자 표본의 **형태 판정 화면** — 신호·투표를 그대로 보인다 (B65 ⑤ · C37).

    자동으로 섰든 아니든 찍는다: 사람이 「표로 판정됐지만 내가 보기엔 산문이다」를
    알아야 `--use-basic`으로 이길 수 있고, 지금도 이길 수 있었으나 **보이지 않았다.**
    돌려주는 것은 `(화면 줄 목록, 판정 dict 목록)`이다 — 판정은 `form.judge` 하나가
    낸다(계열의 출처는 하나 — 문서 1 C37).
    """
    lines, judged = [], []
    for smp in samples:
        if Path(str(smp)).suffix.lower() not in reader.GRID_EXT:
            continue
        try:
            res = form.judge(reader.read(str(smp)))
        except Exception as e:
            res = {"verdict": None, "auto": False, "signals": {}, "votes": {},
                   "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}
        judged.append(res)
        lines.append(f"■ 형태 판정 — {Path(str(smp)).name}")
        if res.get("signals"):
            lines.append("  신호: " + " · ".join(
                f"{k}={res['signals'][k]}[{(res.get('votes') or {}).get(k, '?')[0]}]"
                for k in form.SIGNALS if k in res["signals"]))
        lines.append(f"  투표: {res['why']}"
                     + ("" if res.get("auto") else "  →  자동 판정 불가 (C37)"))
    return lines, judged


def ask_form(doc_type, layer, samples, judged):
    """판정이 안 서면 **사람에게 묻는다** — C37 「그 외는 사람」의 자리 (B65 ⑤).

    구판은 `verdict`가 `None`이면 아무것도 묻지 않고 **LLM 생성으로 갔다**(실측:
    xlsx 산문이 생성에 들어가 「공정 좌표가 무엇인가」를 되물었다). 판정이 안 선
    것은 **모른다는 뜻**이지 table이라는 뜻이 아니다.

    **새 플래그를 만들지 않는다** — 답은 이미 있는 두 플래그와 같은 말이다:
    `--use-basic` = prose · `--no-basic` = table. 비대화형은 상태 거부(B61 계약).
    돌려주는 것은 `"prose"` · `"table"`이다.
    """
    print("  이 문서는 표(table)인가 산문(prose)인가?  "
          "table = LLM 생성 · prose = 고정 어댑터(LLM 0)")
    try:
        ans = input("  [table/prose] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans.startswith("p"):
        return "prose"
    if ans.startswith("t"):
        return "table"
    raise SystemExit(                                                     # [상태]
        f"[생성] 형태 판정이 자동으로 서지 않았고 답을 받지 못했다 "
        f"(C37 — 찬성 ≥2 · 반대 0이 아니면 사람이 정한다)\n"
        f"  근거 — 표본의 형태 신호 5종 (판정 기록은 review/{doc_type}/state.json)\n"
        f"  ▶ 다음 줄 — 둘 중 하나:\n"
        f"     (산문이다 — 고정 어댑터 · LLM 0)  python -m cli.register generate "
        f"{doc_type} {layer} {' '.join(str(x) for x in samples)} --use-basic\n"
        f"     (표다 — LLM 생성)                python -m cli.register generate "
        f"{doc_type} {layer} {' '.join(str(x) for x in samples)} --no-basic")


def save_form(doc_type, judged, by):
    """판정과 **누가 정했나**를 상태에 남긴다 (B65 ⑤) — 뷰·리허설이 읽는 그 값이다."""
    if not judged:
        return
    st = _state(doc_type) or {}
    st["form"] = {"verdict": judged[-1].get("verdict"), "by": by,
                  "why": judged[-1].get("why"),
                  "signals": judged[-1].get("signals")}
    _save_state(doc_type, {**st, "doc_type": doc_type})


def basic_adapter_proposal(samples):
    """분할이 **자명한 계열**이면 기본 어댑터를 제안한다 (파서_명세 §5 규약 5 · C13).

    자명한 것을 매번 생성시키면 검수 비용만 늘고 산출은 같다. 다만 임계를 넘는
    슬라이드가 있으면 자명함이 조건부가 되므로(C13 v18) 그 사실도 함께 말한다.
    """
    # **표본이 전부 `.pptx` 또는 전부 `.pdf`일 때다**(문서 6 §6.4-5 · B53).
    # 섞이면 어느 어댑터를 위임할지가 갈리므로 제안하지 않는다.
    kinds = {Path(str(x)).suffix.lower() for x in samples}
    if kinds == {".pdf"}:
        return _basic_pdf_proposal(samples)
    # **격자 포맷은 계층이 서야 제안이 선다**(B58 ③) — `.pptx`·`.pdf`와 달리
    # 여기엔 포맷이 주는 경계가 없어, 신호 넷으로 계층이 잡히지 않으면 「분할
    # 자명」이 성립하지 않는다. 그 판정은 어댑터가 실제로 돌려 본 결과로 한다.
    if kinds and kinds <= set(reader.GRID_EXT):
        return _basic_prose_xlsx_proposal(samples)
    if kinds != {".pptx"}:
        return None
    # **임계는 어댑터가 소유한다**(문서 6 §6.4-5) — 판단 상수는 `ADAPTER.expects`에
    # 산다(문서 7 §7.1 관리 자산의 원칙). 여기에 숫자를 복제하면 "조정은 어댑터
    # 한 곳에서"가 깨지고, 어댑터를 고쳐도 이 화면의 판정은 옛 임계로 남는다.
    exp = basic_ppt.ADAPTER["expects"]
    max_chars, max_shapes = exp["max_chars"], exp["max_shapes"]
    over = 0
    for s in samples:
        for sl in reader.read(str(s)).get("slides", []):
            if sl.get("hidden"):                    # 숨김은 청크가 아니다 (B53)
                continue
            # **임계는 본문 텍스트로 잰다** — 리더가 shape **레코드**를 내므로(B53)
            # 표·차트·그림은 각자 청크가 되고 본문 분할 판정에 들어가지 않는다.
            body = [r.get("text", "") for r in sl.get("shapes", [])
                    if r.get("kind") not in ("table", "chart", "picture")
                    and r.get("text")]
            if sum(len(x) for x in body) > max_chars or len(body) > max_shapes:
                over += 1
    return {"adapter": "parser/adapters/basic_ppt.py",
            "reason": "PPT는 분할이 자명하다 — 슬라이드가 청크다. 생성 세션이 필요 없다",
            "over_threshold_slides": over,
            "note": ("임계 초과 슬라이드가 있어 자명함이 조건부다 — shape 분할·지도 폴백이 "
                     "돈다(C13 v18)" if over else "전 슬라이드가 임계 이하다")}


def _basic_prose_xlsx_proposal(samples):
    """격자 포맷(xlsx·csv)의 위임 제안 — **계층이 서면 산문으로 읽는다** (B58 ③).

    `.pptx`(슬라이드)·`.pdf`(쪽)는 포맷이 경계를 주지만 스프레드시트는 주지 않는다.
    그래서 제안의 조건이 하나 더 있다: **어댑터를 실제로 돌려 청크가 둘 이상 서야
    한다.** 관리계획서 같은 표를 이 어댑터에 넣으면 헤딩이 굵은 머리 한 줄뿐이라
    **시트 통째로 1청크**가 나오는데, 그것은 분할이 아니라 분할 실패다.

    문면이 아니라 **산출을 본다** — 「표처럼 보인다」는 인상이 아니라 「잘리지
    않았다」는 실행 결과가 거부의 근거다. 형태 판정(table이냐 prose냐)의 정본은
    문서 6 §6.4이고 여기는 그중 **분할 신호 하나**를 볼 뿐이다.
    """
    frames, picks, oor, chunks, forms = 0, [], 0, 0, []
    for s in samples:
        raw = reader.read(str(s))
        # **형태 판정이 먼저다**(문서 1 C37) — 「어느 갈래로 읽는가」를 정하고
        # 나서야 「어느 산문 어댑터인가」가 성립한다. table으로 자동 판정된
        # 표본에 산문 어댑터를 얹으면 관리계획서가 통청크로 들어온다.
        forms.append(form.judge(raw))
        rep = basic_prose_xlsx.level_report(raw)
        frames += len(rep)
        picks += [r["분할_레벨"] for r in rep]
        oor += sum(1 for r in rep if r["분할_레벨_구간밖"])
        chunks += len(basic_prose_xlsx.extract(raw))
    if any(f["verdict"] == form.TABLE for f in forms):
        return None                     # 표로 자동 판정된 표본이 섞였다
    if not frames or chunks <= len(samples):
        return None                     # 시트당 1청크 = 분할이 서지 않았다
    _human = [f for f in forms if not f["auto"]]
    return {"adapter": "parser/adapters/basic_prose_xlsx.py",
            "form": [{"signals": f["signals"], "votes": f["votes"],
                      "verdict": f["verdict"], "auto": f["auto"], "why": f["why"]}
                     for f in forms],
            "reason": ("스프레드시트 산문 — 계층 신호(번호·굵게·들여쓰기·가로병합)로 "
                       "레벨이 정해진다. 생성 세션이 필요 없다"),
            "frames": frames, "chunks": chunks,
            "levels": sorted({p for p in picks if p}),
            "out_of_range_frames": oor,
            "note": (f"프레임 {frames}개 · 청크 {chunks}건 · 고른 레벨 {sorted({p for p in picks if p})}"
                     + (f" · **목표 구간 밖 {oor}프레임** — 최근접 레벨로 떨어졌다"
                        f"(검수 화면과 큐에 남는다)" if oor else "")
                     + (f" · **형태 판정이 사람에게 올라온 표본 {len(_human)}부** — "
                        f"신호값을 보고 정한다" if _human else ""))}


def _basic_pdf_proposal(samples):
    """PDF의 위임 제안 — **쪽이 청크다**(D-111과 같은 래퍼 방식).

    PPT의 임계 셈이 여기 없는 것은 의도다: 기본 PDF 어댑터는 쪽을 쪼개지 않으므로
    「임계 초과 쪽」이라는 판정 자체가 없다(`parser/adapters/basic_pdf.py` 머리말).
    대신 사람이 알아야 할 것 둘을 센다 — **목차 유무**(`section`이 어디서 오는가)와
    **텍스트 0자 쪽**(스캔본 — 그 쪽의 근거는 그림뿐이다).
    """
    pages = no_text = 0
    has_toc = False
    for s in samples:
        raw = reader.read(str(s))
        has_toc = has_toc or bool(raw.get("toc"))
        for pg in raw.get("pages", []):
            pages += 1
            if not (pg.get("text") or "").strip():
                no_text += 1
    return {"adapter": "parser/adapters/basic_pdf.py",
            "reason": "PDF는 분할이 자명하다 — 쪽이 청크다. 생성 세션이 필요 없다",
            "pages": pages, "no_text_pages": no_text,
            "note": (f"목차에서 section을 만든다" if has_toc
                     else "목차가 없다 — section은 「페이지 N」이 된다")
                    + (f" · 텍스트 0자 쪽 {no_text}장은 그림 요약이 유일한 근거다"
                       if no_text else "")}


# ── 문답 누적 — 「재현 조건의 자리는 `human.hint` 그릇이다」(B36 · 문서 6 §6.5) ──
#
# **키가 아니라 항목으로 는다.** 사람 4키·시스템 5키는 불변이고, 문답 묶음은 전부
# `human.hint.interview` 안에서 산다. 묶음 하나 = `{samples, at, stale?, decisions[]}` —
# **라운드 전문은 여기 없다**(B62 ②): 패키지는 생성 user 메시지에 원문 통째로 실리는
# 자리라, 전문이 살면 대화가 매 생성마다 모델에 다시 간다. 전문의 자리는 로그다.

INTERVIEW_LOG = "interview_log.json"     # `review/<doc_type>/` 안 — 라운드 전문의 자리


def _batch_at():
    """묶음의 시각 — **짝을 맞추는 키라 초 해상도로는 모자란다** (B62 ②).

    `store._now()`는 초까지다(적재 시각의 규격이다). 그 값을 묶음 키로 쓰면 **같은
    초에 만들어진 두 묶음이 한 키가 되고**, 로그가 같은 키의 앞 묶음을 치환해
    **사람의 답이 조용히 사라진다**(실측: 한 번의 검사에서 세 묶음이 한 묶음으로
    접혔다). 시각을 위조하는 것이 아니라 **같은 실제 시각을 더 잘게 읽는다.**
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def log_path(doc_type):
    return _dir(doc_type) / INTERVIEW_LOG


def read_log(doc_type):
    """`{at: [라운드…]}` — 없거나 깨졌으면 빈 dict.

    **묶음과 짝은 `at`으로 맞춘다**(B62 ②). 순서로 맞추면 묶음 하나가 지워지는 날
    전 묶음의 전문이 한 칸씩 밀려 다른 표본의 대화가 된다.
    """
    try:
        obj = json.loads(log_path(doc_type).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {b.get("at"): (b.get("rounds") or [])
            for b in (obj.get("batches") or []) if b.get("at")}


def write_rounds(doc_type, at, samples, rounds):
    """한 묶음의 라운드 전문을 로그에 쓴다 — **패키지에는 쓰지 않는다**(B62 ②).

    전문이 패키지에 살면 생성 user 메시지(패키지 원문 통째)에 그대로 실려 모델에
    간다 — 사내 실측 3천 줄이었다. B60 ②가 system 프롬프트의 힌트 자리만 요약으로
    바꿨고 **user 쪽은 그대로였다.** 보내는 쪽에서 걷어내지 않고 **패키지를
    깨끗하게** 한다: 걷어내는 방식은 잊을 자리를 하나 더 만든다.
    """
    d = _dir(doc_type)
    try:
        obj = json.loads(log_path(doc_type).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obj = {}
    batches = [b for b in (obj.get("batches") or []) if b.get("at") != at]
    batches.append({"at": at, "samples": sorted(samples or []), "rounds": rounds})
    log_path(doc_type).write_text(
        json.dumps({"_읽는 법": "문답 라운드 전문 — **이력이다.** 판단은 입력 패키지의 "
                              "human.hint.interview[].decisions에 있고 생성은 그것만 읽는다",
                    "batches": batches}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def migrate_rounds(doc_type, pkg):
    """옛 패키지의 인라인 `rounds`를 **로그로 한 번 옮긴다** (B62 ②).

    `--resume`이 이 경로로 들어온다. 옮긴 뒤 패키지 묶음은
    `{samples, at, stale?, decisions[]}`만 남는다 — 돌려주는 것은 화면 한 줄이거나
    `None`이다. 옮기는 것이지 버리는 것이 아니다: 전문은 재현 근거다.
    """
    hint = ((pkg or {}).get("human") or {}).get("hint")
    batches = _hint_batches(hint)
    moved = [b for b in batches if b.get("rounds")]
    if not moved:
        return None
    n = 0
    for b in moved:
        at = b.get("at") or _batch_at()
        b["at"] = at
        write_rounds(doc_type, at, b.get("samples") or [], b["rounds"])
        n += len(b["rounds"])
        del b["rounds"]
    pkg.setdefault("human", {})["hint"] = _merge_hint(hint, batches)
    return (f"   문답 라운드 {n}건을 로그로 옮겼다 → "
            f"{log_path(doc_type).relative_to(ROOT)}  "
            f"(패키지에는 확정 사항만 남는다 — 생성이 읽는 것이 그것이다)")


def warn_no_decisions(doc_type, pkg):
    """묶음은 있는데 **확정 사항이 하나도 없다** — B60 이전 패키지다 (B62 ②ⓓ).

    죽이지 않는다. 진행은 되지만 **생성이 읽을 판단이 없다**는 사실을 말하고, 그것을
    세울 명령 둘을 함께 준다. 힌트만 준 패키지는 해당 없다(`hint_only_decisions`가
    이미 한 항목을 세웠다).
    """
    batches = _hint_batches(((pkg or {}).get("human") or {}).get("hint"))
    if not batches or any(b.get("decisions") for b in batches):
        return None
    return (f"   ⚠ 이 패키지에 **확정 사항이 없다** — 문답 묶음 {len(batches)}개는 "
            f"있는데 결정이 비어 있다(B60 이전 산출). 생성이 읽을 판단이 없다.\n"
            f"     python -m cli.register review {doc_type} "
            f"--instruct \"<결정 한 문장>\"\n"
            f"     python -m cli.register generate {doc_type} <층> <표본...> --interview")


def _keep_prior(prior, counts=None):
    """**멈추고 묻는다**(B55 ②-4) — 사람의 답은 다시 만들 수 없는 재료다.

    기본은 이어가기다: 비대화형에서 조용히 버리면 그것이 바로 이 회차가 고치는
    병이다(구판은 경고 한 줄 없이 덮어썼다). 버리려면 사람이 답하거나
    `--drop-interview`를 적어야 한다.
    """
    counts = counts or {}
    def _n(b):
        return len(counts.get(b.get("at")) or b.get("rounds") or [])
    n = sum(_n(b) for b in prior)
    print(f"\n   이 등록에 **이전 문답 {n}라운드**가 남아 있다 "
          f"(묶음 {len(prior)}개).")
    for b in prior[-3:]:
        print(f"     · {b.get('at', '?')[:19]} · 표본 "
              f"{[Path(x).name for x in (b.get('samples') or [])]} · "
              f"{_n(b)}라운드")
    try:
        ans = input("   이어갈까? [Y/n]  (n이면 버린다 · 사람의 답은 다시 못 만든다) "
                    ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("   (비대화형 — **이어간다.** 버리려면 --drop-interview)")
        return True
    return ans not in ("n", "no")


def _new_batch(samples):
    # `decisions`가 **확정 요약의 자리**다(B60 ②) — 라운드 전문(`rounds`)은 이력으로
    # 남고, 생성 프롬프트에는 이것만 실린다. 자리는 항상 있다(빈 리스트라도).
    # **라운드 전문은 여기 없다**(B62 ②) — 로그(`interview_log.json`)로 간다.
    # 묶음이 패키지에 사는 이유는 `decisions`가 생성의 입력이기 때문이고,
    # 전문은 입력이 아니라 이력이다.
    return {"samples": sorted(samples), "at": _batch_at(), "decisions": []}


def hint_only_decisions(text):
    """문답 없이 `--hint`만 준 경우의 확정 사항 — **힌트 문장 그대로 한 항목**(B60 ②).

    자리는 항상 있어야 한다: 생성 프롬프트의 `[확정 사항]`이 「문답을 했나」에 따라
    있다 없다 하면, 모델이 없는 절을 찾거나 힌트를 결정보다 약하게 읽는다.
    """
    t = (text or "").strip()
    return [{"topic": "힌트", "decision": t, "reason": "사람 힌트(자유 텍스트)",
             "round": None}] if t else []


def apply_instruction_to_decisions(doc_type, instruction, rev):
    """`--instruct`가 **확정 사항을 갱신한다**(B60 ②) — LLM 0.

    지시와 결정이 따로 살면 다음 재생성이 옛 결정을 다시 쓴다. 규칙은 결정적이다:
    지시 문면에 **어느 항목의 `topic`이 그대로 들어 있으면** 그 항목의 `decision`을
    지시로 바꾸고 `reason`에 「사람 지시 (rev N)」를 붙인다. 어느 topic도 안 들어
    있으면 **새 항목**으로 붙인다 — 지시를 버리지 않는다(무엇에 대한 것인지 사람이
    topic을 안 적었을 뿐이다). 매칭에 LLM을 쓰지 않는 이유: 이 갱신이 판단이 되면
    「지시가 결정을 뒤집었다」가 사람 눈에 안 보이는 자리에서 일어난다.
    """
    path = REVIEW / doc_type / "input_package.json"
    if not path.exists() or not (instruction or "").strip():
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    hint = (obj.get("human") or {}).get("hint")
    batches = _hint_batches(hint)
    live = [b for b in batches if not b.get("stale")]
    if not live:
        live = [_new_batch((obj.get("human") or {}).get("samples") or [])]
        batches = batches + live
    hit = 0
    for b in live:
        for d in b.get("decisions") or []:
            t = (d.get("topic") or "").strip()
            if t and t in instruction:
                d["decision"] = instruction.strip()
                d["reason"] = f"사람 지시 (rev {rev}) — 이전: {d.get('reason', '')}"
                hit += 1
    if not hit:
        live[-1].setdefault("decisions", []).append(
            {"topic": f"지시 (rev {rev})", "decision": instruction.strip(),
             "reason": f"사람 지시 (rev {rev})", "round": None})
    obj.setdefault("human", {})["hint"] = _merge_hint(hint, batches)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hit


_BATCH_KEYS = ("decisions", "rounds", "samples")


def _hint_batches(hint):
    """`hint`가 어떤 꼴이든 문답 묶음 리스트를 돌려준다.

    옛 꼴 셋을 다 받는다 — ①문자열 힌트 ②`{text, interview: [라운드…]}`(B55 이전)
    ③`{text, interview: [묶음…]}`(지금). ②는 묶음 하나로 감싼다: **옛 패키지를
    읽지 못해 이전 문답을 잃는 것이 바로 이 회차가 고치는 병이다.**
    """
    if not isinstance(hint, dict):
        return []
    iv = hint.get("interview") or []
    # **묶음인가는 묶음 키로 가른다** — `rounds`만 보면 B62 ② 이후 묶음
    # (`{samples, at, decisions}`)을 통째로 못 읽어 확정 사항이 사라진다.
    if iv and isinstance(iv[0], dict) and not any(k in iv[0] for k in _BATCH_KEYS):
        return [{"samples": [], "at": None, "rounds": iv}]      # 옛 꼴 → 묶음 1개
    return [b for b in iv if isinstance(b, dict) and any(k in b for k in _BATCH_KEYS)]


def prior_interview(pkg_path):
    """기존 패키지의 문답 묶음. 파일이 없거나 깨졌으면 빈 리스트다."""
    try:
        old = json.loads(Path(pkg_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return _hint_batches(((old.get("human") or {}).get("hint")))


def _age_rounds(batches, samples):
    """표본이 바뀐 묶음에 `stale`을 단다. **지우지 않는다.**

    지우면 재현 조건이 사라지고(그 답으로 만들어진 산출이 왜 그렇게 됐는지 못
    되짚는다), 구분 없이 누적하면 **다른 문서에 대한 이해가 현재 판정에 섞인다.**
    그래서 남기되 표시한다 — 문답 세션은 이것을 「이전 표본에 대한 이해」로 따로 싣는다.
    """
    now = sorted(samples)
    out = []
    for b in batches:
        b = dict(b)
        if sorted(b.get("samples") or []) != now:
            b["stale"] = True
        else:
            b.pop("stale", None)
        out.append(b)
    return out


def _merge_hint(hint, batches):
    """묶음 리스트를 `hint` 그릇에 되돌린다 — **다른 키는 건드리지 않는다.**"""
    base = dict(hint) if isinstance(hint, dict) else {"text": hint or ""}
    base["interview"] = batches
    return base


def cmd_generate(doc_type, layer, samples, hint="", interview=False,
                 no_fewshot=False, resume=False, use_basic=False,
                 drop_interview=False, revise=False, as_name=None,
                 no_basic=False):
    """① 생성 — 입력 패키지를 세우고 초안을 받는다.

    **입력 패키지 = 사람 4 + 시스템 5**(증분0 §3 P3 · 카드 M10):
      사람 — 표본 · doc_type 이름 · 층 지정 · 힌트(자유 텍스트)
      시스템 — reader 원시 추출 · 골격 닫힌 목록 · 층 어휘 · 공용 블록 · 어댑터 스켈레톤

    **등록분에도 다시 들어올 수 있다**(H27 · B58 ①): `--revise`는 같은 이름의 새 판,
    `--as <이름>`은 변형 등록이다. 구판은 등록된 이름이면 통째로 거부해 **어댑터를
    고쳐 다시 등록할 길이 없었다** — 사내가 그 자리에서 멈춰 있었다.
    """
    if as_name:
        # **변형 등록** — 기존 doc_type은 손대지 않고 새 이름으로 정상 경로를 간다.
        print(f"  ▶ 변형 등록 — '{doc_type}'은 그대로 두고 '{as_name}'으로 간다")
        doc_type = as_name
    if revise:
        # **새 판** — 이름은 그대로다. 확정이 정본을 교체하고 revision을 올린다.
        _st_prev = _state(doc_type) or {}
        if _st_prev.get("use_basic"):
            refuse_regenerate(doc_type, _st_prev, "생성")    # B65 ④
        if not registry.lookup(doc_type):
            raise SystemExit(f"[생성] --revise는 **등록분**에만 쓴다 — "            # [상태]
                             f"'{doc_type}'은 등록돼 있지 않다\n"
                             f"  근거 — data/doc_types.json(키 없음)"
                             + (f" · review/{doc_type}/는 있다"
                                f"(approval.json {'있음' if (REVIEW / doc_type / 'approval.json').exists() else '없음'})"
                                " → 옛 환경의 등록부 항목을 옮기거나 아래로 신규 등록"
                                if (REVIEW / doc_type).exists() else "") + "\n"
                             f"  ▶ 다음 줄:\n"
                             f"     python -m cli.register generate {doc_type} "
                             f"{layer or '<층>'} <표본...>")
        _cur = registry.lookup(doc_type)
        _docs = registry.ingested_docs(doc_type)
        print(f"  ▶ 새 판 — '{doc_type}'의 정본을 교체한다 "
              f"(현행 revision {_cur.get('revision', 0)})")
        if _docs:
            print(f"    ※ 이 doc_type으로 인입된 문서 {len(_docs)}건 — "
                  f"확정해도 **자동 재인입은 없다**(문서 4 §4.8-7)")
    if resume:
        # **패키지 조립과 문답을 건너뛰고 draft만 한다**(B43 ⑤). 문답이 몇 라운드
        # 돌고 죽었을 때, 그 전부를 다시 하지 않으려는 자리다 — 패키지에 이미
        # 문답 전문이 실려 있다(라운드마다 즉시 저장하므로).
        pkg_path = REVIEW / doc_type / "input_package.json"
        if not pkg_path.exists():
            raise SystemExit(f"[생성] --resume 인데 입력 패키지가 없다 — "          # [상태]
                             f"근거 review/{doc_type}/input_package.json 없음\n"
                             f"  ▶ 다음 줄 — 먼저 --resume 없이 한 번 돌린다:\n"
                             f"     python -m cli.register generate {doc_type} "
                             f"<층> <표본...>")
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        print(f"  {llm.mode_line()}")
        print(f"■ ① 생성 (이어하기) — {doc_type} · 기존 패키지 재사용")
        # **옛 패키지의 인라인 전문을 로그로 옮긴다**(B62 ②) — 로드 시 한 번.
        _mv = migrate_rounds(doc_type, pkg)
        if _mv:
            print(_mv)
            pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        _wn = warn_no_decisions(doc_type, pkg)
        if _wn:
            print(_wn)
        if layer or samples:
            # **무시하되 말한다** — 사람이 준 값이 안 쓰였다는 사실을 침묵으로
            # 넘기면, 층을 바꾸려고 다시 준 사람이 바뀐 줄 안다.
            print(f"   [생성] --resume — 층·표본 인자는 무시한다 (패키지의 값을 쓴다: "
                  f"layer={pkg['human']['layer']}, "
                  f"표본 {len(pkg['human']['samples'])}건)")
        _r = (pkg.get("human") or {}).get("hint")
        if isinstance(_r, dict) and _r.get("interview"):
            # **묶음과 전문을 갈라 말한다**(B62 ②) — 구판은 묶음 수를 「라운드」라
            # 불렀고, 전문이 로그로 간 뒤에는 그 문면이 거짓이 된다. 전문 건수는
            # 로그에서 읽는다: 패키지에 없는 것을 패키지에서 세지 않는다.
            _bs = _hint_batches(_r)
            _lg = read_log(doc_type)
            print(f"   문답 묶음 {len(_bs)}개 · 확정 사항 "
                  f"{sum(len(b.get('decisions') or []) for b in _bs)}항목 "
                  f"(라운드 전문 "
                  f"{sum(len(_lg.get(b.get('at')) or []) for b in _bs)}건은 "
                  f"{INTERVIEW_LOG})")
        # **이어하기는 코드가 아니라 판단을 이어받는다**(B67 ①).
        #
        # 구판은 `draft(doc_type)`를 지시·이력 **없이** 불렀다. 생성은
        # `temperature=0`이라 같은 입력이면 같은 코드가 나오고, 그래서 사내에서
        # G31(`AttributeError`)로 끝난 등록을 이어가자 **같은 G31**이 났다 —
        # 이어하기가 재생성이 아니라 **재현**이었다. 초안이 이미 있으면:
        #   ① 관문을 먼저 돌린다(B60 ① — 저장 판정을 믿지 않는다 · LLM 0)
        #   ② FAIL이면 그 판정 문면과 지시 이력을 재생성 지시로 **싣는다**
        #   ③ PASS면 초안을 다시 받지 않는다 — 통과한 것을 이유 없이 갈지 않는다
        print("   이어하기 = 같은 입력 + 지난 실패 · 처음부터 = --resume 없이")
        st = _state(doc_type) or {}
        st.setdefault("samples", pkg["human"]["samples"])
        _prior = _at(st["adapter"]) if st.get("adapter") else None
        _instruction = None
        if _prior and _prior.exists() and st.get("schema"):
            if regate(doc_type, st) == "PASS":
                print("   [이어하기] 지난 초안이 관문 PASS — 초안을 다시 받지 "
                      "않는다 (LLM 호출 0). 갈 곳은 검수·확정이다")
                st = {**st, "doc_type": doc_type, "layer": pkg["human"]["layer"],
                      "samples": pkg["human"]["samples"], "hint": pkg["human"]["hint"]}
                _save_state(doc_type, st)
                return _finish_generate(doc_type, st, st["samples"], pkg)
            _fails = fail_lines(st.get("harness_out") or "")
            _auto, _ask = classify_failures(st.get("harness_out") or "")
            _instruction = "\n".join(_auto + _ask)
            print(f"   [이어하기] 지난 초안 관문 FAIL {len(_fails)}건"
                  f"({' · '.join(c for c, _l, _d in _fails) or '판정 줄 없음'})을 "
                  f"지시로 싣는다 · 지시 이력 {len(st.get('instructions') or [])}건")
        if _instruction:
            st["revision"] = st.get("revision", 0) + 1
            st.setdefault("instructions", []).append(
                {"n": st["revision"], "instruction": _instruction,
                 "at": store._now(), "by": "자동(이어하기 — 지난 관문 판정)"})
            ad, sc = draft(doc_type, st["revision"], instruction=_instruction,
                           history=st.get("instructions"))
        else:
            ad, sc = draft(doc_type)
        if ad is None:
            _want = f"{doc_type}_rev{st['revision']}" if _instruction else doc_type
            raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "       # [상태]
                             f"'{_want}' 부재 (D-10). mock에 이 이름의 초안이 "
                             f"없다\n"
                             f"  ▶ 다음 줄 — 실호출로 돌린다:\n"
                             f"     python run.py llm-check\n"
                             f"     USE_MOCK=0 python -m cli.register generate "
                             f"{doc_type} --resume")
        print(f"   초안 수령: {_rel(ad)} · {_rel(sc)}")
        st = {**st, "doc_type": doc_type, "layer": pkg["human"]["layer"],
              "samples": pkg["human"]["samples"], "hint": pkg["human"]["hint"],
              "adapter": str(_rel(ad)),
              "schema": str(_rel(sc)),
              "revision": st.get("revision", 0),
              "instructions": st.get("instructions", [])}
        _save_state(doc_type, st)
        return _finish_generate(doc_type, st, st["samples"], pkg)

    if registry.lookup(doc_type) and not revise:
        # **막다른 길만 말하지 않는다**(H27) — 구판은 여기서 끝이라, 어댑터를 고쳐
        # 다시 등록할 길이 아예 없었다. 두 경로가 있고 화면이 그것을 알려 준다.
        _docs = registry.ingested_docs(doc_type)
        raise SystemExit(                                                 # [상태]
            f"[생성] '{doc_type}'은 이미 등록돼 있다 "
            f"(근거 data/doc_types.json). 두 길 중 하나를 고른다:\n"
            f"   ① 같은 이름의 **새 판** — 어댑터를 고쳐 정본을 교체한다\n"
            f"        python -m cli.register generate {doc_type} {layer or '<층>'} "
            f"<표본...> --revise\n"
            f"   ② **변형 등록** — 기존은 그대로 두고 다른 이름으로 간다\n"
            f"        python -m cli.register generate {doc_type} {layer or '<층>'} "
            f"<표본...> --as <새이름>\n"
            + (f"   ※ 이 doc_type으로 인입된 문서 {len(_docs)}건이 있다 — "
               f"새 판을 확정해도 **자동 재인입은 없다**(문서 4 §4.8-7)\n"
               if _docs else ""))

    # **표본 자리의 비파일을 조용히 무시하지 않는다.** 힌트를 따옴표 없이 적으면
    # 그 단어들이 표본 목록으로 들어오고, 지금까지는 reader가 「지원하지 않는 포맷」으로
    # 죽거나 조용히 빠졌다 — 어느 쪽이든 사람은 «힌트를 줬다»고 믿는다.
    bad = [s for s in samples if not Path(s).is_file()]
    if bad:
        # **이것은 상태가 아니라 사용법이다**(B77 ③) — 시스템의 상태는 멀쩡하고
        # 사람이 인자를 잘못 쳤다. 근거 자리가 없는 것이 아니라 **없는 것이 맞다**:
        # 볼 파일이 없고 볼 것은 방금 친 명령이다(B61의 두 갈래 — D-156 ②).
        raise SystemExit(                                                 # [사용법]
            f"[생성] 표본 자리에 파일이 아닌 값이 있다: {bad}\n"
            f"        힌트라면 --hint \"…\" 로 준다 (따옴표로 묶는다):\n"
            f"        python -m cli.register generate {doc_type} {layer} "
            f"<표본.xlsx> --hint \"{' '.join(str(b) for b in bad)[:60]}\"")
    layers = discover()
    if layer not in layers:                       # ⑵-③ 층 선행 완결
        raise SystemExit(f"[생성] 존재하지 않는 층 '{layer}' — 층 등록(R1)은 국면 2다. "  # [상태]
                         f"현재 층: {layers} (근거 layers/<층>/config.json · "
                         f"data/registry.json)\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"{layers[0] if layers else '<층>'} "
                         f"{' '.join(str(x) for x in samples) or '<표본...>'}")
    if use_basic:
        # **제안이 서지 않는 표본에는 거부한다** — 조용히 LLM 생성으로 떨어지면 사람은
        # «기본 어댑터로 등록됐다»고 믿는다. 거부는 사유를 들고 멈춘다.
        proposal = basic_adapter_proposal(samples)
        if proposal is None:
            _refuse_basic(doc_type, layer, samples)
        return _use_basic(doc_type, layer, samples, hint, proposal, revise)

    # **산문 포맷이면 고정 어댑터를 먼저 권한다**(B59 ③) — 그 길로 안 들어가게 하는
    # 것이 먼저다. 실측: 사내가 PPT 하나 넣으려고 LLM 생성으로 갔고, 관문 FAIL →
    # 막다른 길이었다. 고정 어댑터는 생성 LLM 0회이고 관문을 그냥 지난다.
    # **형태 판정을 화면에 올린다**(B65 ⑤ · C37) — 자동으로 섰든 아니든 신호·투표를
    # 보인다. 안 섰으면 **사람에게 묻는다**: 구판은 아무것도 묻지 않고 LLM 생성으로
    # 갔고(실측: xlsx 산문이 생성에 들어가 「공정 좌표가 무엇인가」를 되물었다),
    # 판정이 안 선 것은 **모른다는 뜻**이지 table이라는 뜻이 아니다.
    _flines, _judged = form_block(samples)
    for _ln in _flines:
        print(_ln)
    _by = "auto"
    if _judged and all(j.get("verdict") is None for j in _judged) \
            and not use_basic and not no_basic:
        _ans = ask_form(doc_type, layer, samples, _judged)
        _by = "human"
        for _j in _judged:
            _j["verdict"] = _ans
        if _ans == "prose":
            # **답이 곧 `--use-basic`이다** — 제안이 서지 않으면 그 플래그와 **같은
            # 거부**를 낸다(문면 한 자리). 조용히 LLM 생성으로 흘리지 않는다: 사람은
            # 「산문이라고 답했다」고 믿는데 LLM이 도는 것이 이 항목이 없애려는 상태다.
            _prop = basic_adapter_proposal(samples)
            save_form(doc_type, _judged, _by)
            if not _prop:
                _refuse_basic(doc_type, layer, samples)
            return _use_basic(doc_type, layer, samples, hint, _prop, revise)
        else:
            no_basic = True          # 사람이 표라고 정했다 — 권유를 다시 하지 않는다
    save_form(doc_type, _judged, _by)

    if not no_basic:
        _prop = basic_adapter_proposal(samples)
        if _prop and _all_prose(samples):
            print(f"  표본이 전부 산문 포맷이다 — LLM 생성 대신 고정 어댑터를 "
                  f"쓰는 것이 기본이다:")
            print(f"     python -m cli.register generate {doc_type} {layer} "
                  f"{' '.join(str(x) for x in samples)} --use-basic")
            print(f"       └ {_prop['reason']}")
            print(f"  그래도 LLM 생성으로 가려면 --no-basic 을 붙여라.")
            try:
                _go = input("  고정 어댑터로 갈까? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                # **비대화형이면 고정 어댑터로 간다** — 기본값이 「안전한 쪽」이다.
                _go = ""
                print("  (비대화형 — 고정 어댑터로 간다)")
            if _go not in ("n", "no"):
                return _use_basic(doc_type, layer, samples, hint, _prop, revise)
            print("  → LLM 생성으로 간다 (사람이 골랐다)")

    snap = store.read(store.SKELETON_LIST, {}).get(layer) or {}
    cfg = json.loads((ROOT / "layers" / layer / "config.json").read_text(encoding="utf-8"))
    pkg = {
        # **첫 키가 읽는 법이다** — 이 파일을 처음 여는 사람이 어디를 볼지 모른다.
        "_읽는 법": "사람이 볼 것은 human.hint(사람이 준 것)와 "
                  "system.reader_head(표본 관찰 재료)다. 나머지는 시스템이 채운다",
        "human": {"doc_type": doc_type, "layer": layer,
                  "samples": [str(s) for s in samples],
                  # **끈 사실을 기록하되 사람 4키를 늘리지 않는다**(B30 재현 조건 ·
                  # 문서 6 §6.5 표). `hint`가 「사람이 준 것」의 자리이므로 그 안에
                  # 싣는다 — 문답 전문을 같은 자리에 실은 D-101과 같은 규칙이다.
                  "hint": ({"text": hint, "no_fewshot": True}
                           if no_fewshot else hint)},
        "system": {
            # **관찰 재료 그릇 안에 열 프로파일을 함께 싣는다**(B39·B36) —
            # 시스템 5키를 늘리지 않는다. 앞 N줄 창으로는 보이지 않는 사실(행마다
            # 고유한가·거의 비었는가)을 **전 행 스캔**으로 공짜로 준다.
            # **헤더 행은 아직 모른다** — 어댑터가 없는 시점이라 추측하지 않고
            # 포함해 세고, 그 사실을 값으로 밝힌다(추측한 통계 = 지어낸 근거).
            "reader_head": [{"path": str(s), "head": _h,
                             "열_프로파일": [
                                 {**profile.profile(sh), "시트": sh.get("name"),
                                  "헤더행_제외": False}
                                 for sh in (_raw.get("sheets") or [])]}
                            for s in samples
                            for _raw in [reader.read(str(s))]
                            for _h in [reader.head(_raw)]],
            # **원천은 골격 닫힌 목록 스냅샷의 지정 층 몫이다**(문서 6 §6.7 킷 #1 ·
            # 문서 1 M21) — 층 자산 `layers/{층}/skeleton.json`을 읽지 않는다.
            # 그 파일은 `skeleton` 선언이 `source`를 쓰는 층에만 있어(품질층은
            # 인라인) 층 자산을 읽는 구현은 그 층의 등록에서 렌더가 죽는다.
            # **canonical과 alias를 함께** 싣는다 — 표기 변형이 빠지면 생성 세션이
            # 문서의 표기를 목록 밖으로 판정해 anchor를 세우지 못한다.
            "skeleton_closed_list": {"skeleton_version": snap.get("skeleton_version"),
                                     "count": snap.get("count"),
                                     "surfaces": [
                                         {"canonical": n["canonical"],
                                          "aliases": n.get("aliases") or [],
                                          "tier": n.get("tier")}
                                         for n in (snap.get("nodes") or [])]},
            # **존재하는 층 목록은 「층 어휘」 안에 든다**(문서 6 §6.5) — 지정 층의
            # 어휘만 보내면 생성 세션이 걸침(`target_layer`)을 선언할 때 어느 층
            # 이름이 유효한지 모른 채 지어낸다. **시스템 5키를 6키로 늘리지
            # 않는다** — 그 수가 명세이고 회귀가 그것을 센다.
            "layer_vocabulary": {"layer": layer,
                                 "layers": sorted(discover()),
                                 "categories": cfg.get("categories"),
                                 "relations": cfg.get("relations"),
                                 "relation_patterns": cfg.get("relation_patterns")},
            "blocks": json.loads(paths.blocks()
                                 .read_text(encoding="utf-8")),
            # **경로가 아니라 본문을 싣는다**(B29 ★①) — 경로만 보내면 생성 세션이
            # 그 파일을 열 수 없어 뼈대를 **작문**하게 된다. 실측: 전송분의 extract가
            # 시그니처와 docstring에서 끝났다. 시스템 키는 **5 그대로**다 — 값의
            # 형태만 바뀐다(문서 6 §6.5 표).
            "adapter_skeleton": _strip_module_doc(
                (KIT / "어댑터_스켈레톤.py").read_text(encoding="utf-8")),
        },
    }
    d = _dir(doc_type)
    # **사람의 답은 다시 만들 수 없는 재료다**(B55 ②) — 재실행이 패키지를 새로
    # 조립해 덮어쓰면 이전 문답이 경고 한 줄 없이 사라진다. 이어 붙이고, 표본이
    # 바뀌었으면 지우지 않고 `stale`로 표시한다(지우면 재현 조건이 사라지고,
    # 무구분 누적이면 다른 문서에 대한 이해가 현재 판정에 섞인다).
    prior = prior_interview(d / "input_package.json")
    # **옛 패키지는 로드 시 한 번 옮긴다**(B62 ②) — 여기도 로드 경로다.
    if prior and any(b.get("rounds") for b in prior):
        _old_pkg = json.loads((d / "input_package.json").read_text(encoding="utf-8"))
        _mv = migrate_rounds(doc_type, _old_pkg)
        if _mv:
            print(_mv)
            (d / "input_package.json").write_text(
                json.dumps(_old_pkg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            prior = prior_interview(d / "input_package.json")
    if prior and drop_interview:
        _lg = read_log(doc_type)
        print(f"   ⚠ 이전 문답 "
              f"{sum(len(_lg.get(b.get('at')) or []) for b in prior)}라운드를 "
              f"**버린다** (--drop-interview)")
    elif prior:
        if _keep_prior(prior, read_log(doc_type)):
            kept = _age_rounds(prior, [str(x) for x in samples])
            pkg["human"]["hint"] = _merge_hint(pkg["human"]["hint"], kept)
        else:
            print("   → 이전 문답을 버리고 새로 시작한다")
    if not interview:
        # **문답을 열지 않는 실행에서만 말한다**(B62 ②ⓓ) — 바로 문답이 열리면
        # 「결정을 세워라」가 아니라 열리는 문답이 답이다.
        _wn = warn_no_decisions(doc_type, pkg)
        if _wn:
            print(_wn)
    (d / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"  {llm.mode_line()}")          # B42 ⑤ — 어느 갈래로 도는지 먼저
    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부)")
    print(f"   입력 패키지: 사람 4 + 시스템 5 → {(d / 'input_package.json').relative_to(ROOT)}")

    if interview:
        # **문답은 패키지가 선 뒤다** — 문답의 입력이 그 패키지(표본 관찰 재료)다.
        # 끝나면 전문을 `human.hint`에 구조화해 다시 싣는다: 기록이 없으면 같은
        # 등록을 재현할 수 없다. **시스템 5키는 그대로다.**
        # **라운드마다 즉시 저장한다**(B43 ⑤) — 전 라운드가 끝나야 쓰면 중간에
        # 죽었을 때 전부 잃는다. 사람의 답은 다시 만들 수 없는 재료다.
        _batch = _new_batch([str(x) for x in samples])

        def _persist(rounds):
            # **전문은 로그, 판단은 패키지**(B62 ②) — 쓰는 자리에서 가른다.
            write_rounds(doc_type, _batch["at"], _batch["samples"], rounds)
            pkg["human"]["hint"] = _merge_hint(
                pkg["human"]["hint"],
                [b for b in _hint_batches(pkg["human"]["hint"])
                 if b is not _batch] + [_batch])
            (d / "input_package.json").write_text(
                json.dumps(pkg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")

        # **이전 라운드를 문답에 실어 보낸다**(②-2) — 저장만 이어 붙이고 모델이
        # 처음부터 물으면 사람이 두 번 답한다.
        rounds = _interview(pkg, on_round=_persist)
        # **확정 요약이 생성의 입력이다**(B60 ②) — 전문은 이력으로 남고, 사람이
        # 화면에서 요약을 확인한다. 요약도 즉시 저장한다(라운드와 같은 이유).
        _batch["decisions"] = iv_finalize(pkg, rounds)
        # 문답이 정한 열은 대장에도 간다(B67 ②) — 판단의 자리는 하나다.
        apply_decisions_to_ledger(doc_type, _batch["decisions"])
        _persist(rounds)
        _log = read_log(doc_type)
        _old = sum(len(_log.get(b.get("at")) or [])
                   for b in _hint_batches(pkg["human"]["hint"]) if b is not _batch)
        print(f"   문답 {len(rounds)}라운드 → {log_path(doc_type).relative_to(ROOT)} · "
              f"확정 사항 {len(_batch['decisions'])}항목 → human.hint"
              + (f" (이전 {_old}라운드 유지)" if _old else ""))
    elif (hint or "").strip():
        # **문답 없이 힌트만** — 힌트 문장이 그대로 한 항목의 확정 사항이다. 자리는
        # 항상 있어야 하므로 여기서 묶음을 세운다(사람 4키는 그대로 — `hint` 안이다).
        _hb = _new_batch([str(x) for x in samples])
        _hb["decisions"] = hint_only_decisions(hint)
        pkg["human"]["hint"] = _merge_hint(
            pkg["human"]["hint"], _hint_batches(pkg["human"]["hint"]) + [_hb])
        (d / "input_package.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proposal = basic_adapter_proposal(samples)
    if proposal:
        print(f"   ▶ 기본 어댑터 적용 제안 — {proposal['reason']}")
        print(f"     {proposal['note']}")
    ad, sc = draft(doc_type)
    if ad is None:
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "           # [상태]
                         f"'{doc_type}' 부재 (D-10). 실물 경로는 생성 LLM 훅이다\n"
                         f"  ▶ 다음 줄 — 실호출로 돌린다:\n"
                         f"     python run.py llm-check\n"
                         f"     USE_MOCK=0 python -m cli.register generate "
                         f"{doc_type} --resume")
    print(f"   초안 수령: {_rel(ad)} · {_rel(sc)}")
    u = llm.usage_total()
    if u["calls"]:
        print(f"   LLM 사용량 — 호출 {u['calls']:,}회 · 토큰 {u['total_tokens']:,}"
              f"(입력 {u['prompt_tokens']:,} · 출력 {u['completion_tokens']:,})"
              + (f" · **응답 잘림 {u['truncated']}회**" if u["truncated"] else ""))
    st = {"doc_type": doc_type, "layer": layer,
          "samples": [str(s) for s in samples],
          "hint": pkg["human"]["hint"],
          "adapter": str(_rel(ad)),
          "schema": str(_rel(sc)),
          "revision": 0, "instructions": [],
          "revise_of": doc_type if revise else None,   # **새 판인가**(H27)
          "basic_adapter_proposal": proposal}
    _save_state(doc_type, st)
    return _finish_generate(doc_type, st, samples, pkg)


def _use_basic(doc_type, layer, samples, hint, proposal, revise=False):
    """② 기본 어댑터 수용 — **LLM 호출 0회**로 검수 자리에 정본 후보를 놓는다 (§6.4-5).

    어댑터는 코어의 `parser/adapters/basic_ppt.py`를 **위임하는 래퍼**다 — 복사하지
    않는다. 봉투 doc_type은 `ADAPTER["doc_type"]`에서 오므로(parser/pipeline) 이름만
    이 doc_type으로 바꾸고 임계·분할은 코어 어댑터 한 곳에 남긴다(D-111: 조정은 그 어댑터
    1곳의 개정이고 doc_type별로 갈리지 않는다 — §6.4-5). 매칭 스키마는 prose 계약대로
    `fields {}`다. **검수·승인 1회는 생략하지 않는다**(M4) — 다음은 `review`다.
    """
    u0 = llm.usage_total()["calls"]          # 이 명령이 부른 횟수를 재려면 시작점이 필요하다
    d = _dir(doc_type)
    pkg = {"_읽는 법": "기본 어댑터 경로 — 생성 세션 없음. human.hint에 그 사실이 있다",
           "human": {"doc_type": doc_type, "layer": layer,
                     "samples": [str(s) for s in samples],
                     "hint": {"text": hint, "use_basic": True, "proposal": proposal}},
           "system": {"reader_head": [], "skeleton_closed_list": {},
                      "layer_vocabulary": {"layer": layer}, "blocks": {},
                      "adapter_skeleton": ""}}
    (d / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ad, sc = d / "adapter.py", d / "schema.json"
    # **위임 대상은 제안이 정한다** — PPT면 `basic_ppt`, PDF면 `basic_pdf`(B53).
    # 여기에 이름을 박으면 PDF 등록분이 PPT 어댑터를 물어 조각 0건이 된다.
    mod = Path(proposal["adapter"]).stem
    kind = {"basic_pdf": "PDF", "basic_ppt": "PPT",
            "basic_prose_xlsx": "스프레드시트 산문"}.get(mod, mod)
    ad.write_text(
        "# -*- coding: utf-8 -*-\n"
        f"\"\"\"{doc_type} — 코어 기본 어댑터({kind})를 **그대로** 쓴다 (문서 6 §6.4-5 · D-111).\n\n"
        f"임계·분할 규칙은 `{proposal['adapter']}` 한 곳에 산다 — 여기는 doc_type 이름만\n"
        "이 등록의 것으로 바꾼 위임 래퍼다. 상수를 여기 복제하지 않는다.\n\"\"\"\n"
        f"from parser.adapters import {mod}\n\n"
        f"ADAPTER = {{**{mod}.ADAPTER, \"doc_type\": {doc_type!r}}}\n"
        f"extract = {mod}.extract\n"
        # **제 계산을 내놓는 어댑터면 그것도 위임한다**(B68 ①) — 래퍼가
        # `level_report`를 안 달면 파이프라인이 번호 패턴만 보는 대체 계산으로
        # 떨어지고, **화면의 레벨·기준이 실제로 자른 것과 갈린다**(pipeline의
        # 「어댑터가 제 계산을 내놓으면 그것이 정본이다」 — B58 ③).
        + (f"level_report = {mod}.level_report\n"
           if hasattr(_ad_mod(mod), "level_report") else ""), encoding="utf-8")
    _write_schema(sc, json.dumps(
        {"doc_type": doc_type, "schema_version": 1, "layer": layer,
         "payload_kind": "prose", "use_blocks": ["common_core", "process_coord"],
         "_note": "비정형 — role 매핑 표가 없다. 층 선언이 계약의 전부다(B1)",
         "fields": {}, "edges": []}, ensure_ascii=False))
    print(f"  {llm.mode_line()}")
    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부) — **기본 어댑터 경로**")
    print(f"   ▶ {proposal['reason']}")
    print(f"     {proposal['note']}")
    print(f"   어댑터(위임 래퍼) · 스키마: {ad.relative_to(ROOT)} · {sc.relative_to(ROOT)}")
    u = llm.usage_total()
    print(f"   LLM 사용량 — 이 명령에서 호출 {u['calls'] - u0:,}회 "
          f"(기본 어댑터 — 생성 세션 없음 · 프로세스 누계 {u['calls']:,}회)")
    print(f"   다음: python -m cli.register review {doc_type}  (뷰 확인·승인 1회는 그대로다 — M4)")
    st = {"doc_type": doc_type, "layer": layer,
          "samples": [str(s) for s in samples],
          "hint": pkg["human"]["hint"],
          "adapter": str(_rel(ad)),
          "schema": str(_rel(sc)),
          "revision": 0, "instructions": [],
          "revise_of": doc_type if revise else None,   # **새 판인가**(H27)
          "basic_adapter_proposal": proposal, "use_basic": True}
    # **형태 판정 기록을 잃지 않는다**(B65 ⑤) — 이 자리가 상태를 새로 쓰므로,
    # 앞에서 남긴 `form`(판정 · 누가 정했나)을 이어 싣는다. 뷰·리허설이 읽는 값이다.
    _prev_form = (_state(doc_type) or {}).get("form")
    if _prev_form:
        st["form"] = _prev_form
    _save_state(doc_type, st)
    return _finish_generate(doc_type, st, samples, pkg)


# ================================================================ ② 검수
def harness(adapter, schema, samples, package=None, doc_type=None):
    """기계 관문 — **kit/run_adapter.py를 그대로 부른다**(재작성 아님).

    `package`는 입력 패키지 경로다(B64 ②) — 관문이 FAIL 줄에 **열 프로파일**을 실을
    때 쓴다. 관문은 계산하지 않는다: 그 값은 패키지 조립이 이미 전 행 스캔으로 냈다.

    `doc_type`이 오면 **열 판정 대장의 자리**도 넘긴다(B76 ② — G4G). 관문이 대장을
    만들지는 않는다: 읽고 커버리지만 판정한다.
    """
    pkg = ([("--package"), str(package)] if package and Path(package).exists() else [])
    led = ledger_path(doc_type) if doc_type else None
    if led and Path(led).exists():
        pkg += ["--ledger", str(led)]
    r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                        str(adapter), str(schema)] + pkg + [str(s) for s in samples],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode == 0, r.stdout


# **실패 분류표**(B50 · 문서 6 §6.5) — 「문면이 고칠 방법을 담는가」로 가른다.
# 담으면 그 문면을 **그대로 지시로 실어** 재생성한다(사람의 통역을 거치지 않는다 —
# C27: 사내는 코딩하지 않는다). 담지 않으면 원인 규명이 필요하므로 **묻는다.**
#
# **목록 밖은 기본이 문답이다.** 새 하네스 항목이 생겨도 조용히 자동으로 흐르지
# 않는다 — 모르는 실패를 자동으로 되돌리면 같은 실패가 무한히 왕복한다.
AUTO_FIX = {
    "규약 10": "재구현 대신 무엇을 부를지가 문면에 있다 (parser.normalizer)",
    "source_locator가 문서 내 유일": "중복된 locator가 문면에 있다",
    "원본 헤더 문자열이 전부 expects에 실림": "빠진 헤더 목록이 문면에 있다",
    "전 필드의 role이 닫힌 5종 안": "닫힌 5종 밖 값이 문면에 있다",
    "파서 출력에 스키마 밖 필드 없음": "스키마 밖 필드 이름이 문면에 있다",
    "adapter.doc_type == schema.doc_type": "어긋난 두 값이 문면에 있다",
    "필수 키 4종": "빠진 키 이름이 문면에 있다",
    "헤더 4키": "빠진 키 이름이 문면에 있다",
    # **고칠 값이 문면에 있다**(B64 ②) — 후보 열문자·헤더 목록·의심 행이 상세에 있고,
    # 재생성은 그 문면을 그대로 지시로 받는다. 사람의 통역을 거치지 않는다(C27).
    "columns 값이 header_row": "고칠 값이 문면에 있다 (후보 열문자 · 헤더 목록)",
    # **형 검사**(B76 ①) — 어느 키가 어떤 형이어야 하는지가 문면에 통째로 있다.
    "키마다 허용 형": "고칠 키·받은 형·허용 형이 문면에 있다",
    # **어휘가 닫힌 자리**(B65) — 문면이 「없는 것 · 있는 것」을 담는다. 목록을
    # 그대로 지시로 실으면 재생성이 목록 안에서 고른다(사람의 통역 0 — C27).
    "normalizer 참조가 실재한다": "있는 이름 목록이 문면에 있다",
    "category가 층 목록 안": "층 카테고리 목록이 문면에 있다",
    "relation이 층 목록 안": "층 관계 목록이 문면에 있다",
    "삼항이 relation_patterns 안": "허용 삼항이 문면에 있다",
    # **어댑터가 내는 키**(B72 ①) — 빠진 이름과 무엇을 하라는지가 문면에 있다.
    # 이것이 없어서 「스키마에 없는 필드 'meta'」가 **인입에서 행마다** 떴다.
    "어댑터가 내는 키가 전부 스키마": "빠진 필드 이름과 처방이 문면에 있다",
}


# ⑤단(파서 전 구간) 판정의 처분표 — **B58 ②가 단을 더했는데 이 표가 8줄 그대로라
# 새 단의 실패가 전부 문답으로 가고 있었다**(B59 ②). 셋으로 가른다:
#
# | 처분 | 무엇 | 왜 |
# |---|---|---|
# | `AUTO_FIX` | 라벨 문면이 고칠 방법을 담는다 | 그 문면을 그대로 지시로 실어 자동 1회 |
# | `WITH_EVIDENCE` | 담지 않지만 **상세가 원문을 담는다** | 문답이 원문을 보고 통역한다 |
# | `GATE_SELF` | **어댑터 결함이 아니다 — 관문 자체다** | 재생성으로 고칠 수 없다 |
#
# ⑤단 넷 중 `AUTO_FIX`에 드는 것은 **하나도 없다** — 라벨이 「완주했다」·「결함 0」처럼
# **결과**를 말하고 처방을 말하지 않기 때문이다. 그래서 원문 동봉이 이 단의 핵이다.
WITH_EVIDENCE = {
    "G51": "예외 원문 (`{예외형}: {메시지}`)",
    "G52": "validator 결함 원문 (kind · reason · detail)",
    "G53": "봉투에 선 키 목록",
}
# **관문 자체의 결함**은 지시로 보내지 않는다 — 어댑터를 고쳐도 안 낫는다.
# 「관문이 LLM을 부르지 않는다」가 깨졌다면 깨진 것은 관문이고, 사람이 볼 곳은
# `kit/run_adapter.py`다. 이것을 문답에 보내면 모델이 어댑터를 엉뚱하게 고친다.
GATE_SELF = {
    "G54": "관문이 LLM을 불렀다 — 어댑터 결함이 아니라 관문 결함이다",
    # **대장은 산출이 아니라 관문 입구가 세운다**(B67 ② · B76 ②) — 빠진 행은
    # 생성이 잘못한 것이 아니라 **기계가 빠뜨린 것**이라 재생성이 고치지 못한다.
    "G4G": "열 판정 대장이 스키마 필드를 덮지 못했다 — 대장을 세우는 자리의 결함이다",
}


def classify_failures(harness_out):
    """하네스 `[FAIL]` 줄을 `(자동, 문답)` 둘로 가른다 (B50).

    가르는 기준은 **문면이 답을 담는가** 하나다. 「조각 0건」은 왜 0건인지를 문면이
    말하지 않으므로 자동으로 되돌릴 것이 없고, 「규약 10 재구현」은 무엇을 부르라는
    말이 문면에 이미 있다.
    """
    auto, ask = [], []
    for ln in [x.strip() for x in harness_out.splitlines() if "[FAIL]" in x]:
        (auto if any(k in ln for k in AUTO_FIX) else ask).append(ln)
    return auto, ask


def _kit_line_re():
    """하네스 판정 줄의 정규식 — **킷 모듈에서 읽는다**(정본이 거기다).

    import이 아니라 문면 추출인 이유: `kit/run_adapter.py`는 **독립 실행 스크립트**라
    import하면 그 머리의 `sys.path` 조작과 `openpyxl` 지연 import가 여기로 끌려온다.
    뽑는 것은 상수 한 줄이고, 없으면 시끄럽게 실패한다(조용한 폴백을 두지 않는다).
    """
    src = (KIT / "run_adapter.py").read_text(encoding="utf-8")
    m = re.search(r'^LINE_RE = r"(.+)"$', src, re.M)
    if not m:
        raise SystemExit("[관문] kit/run_adapter.py의 LINE_RE를 찾지 못했다 — "    # [상태]
                         "판정 줄 문면 규격이 정본에서 사라졌다 (관문 자체 결함 — "
                         "어댑터 잘못이 아니다)\n"
                         "  ▶ 다음 줄 — 반입물이 온전한지 본다:\n"
                         "     python doctor.py")
    return m.group(1)


# 하네스 판정 줄의 문면 규격 — **정본은 `kit/run_adapter.py`의 `LINE_RE`다.**
# 여기서 다시 쓰지 않는 이유: 두 벌이면 관문이 문면을 바꿀 때 이쪽이 조용히
# 아무 줄도 못 읽고, 그 결과가 「막는데 이유를 안 알려 준다」로 되돌아간다.
_GATE_LINE = re.compile(_kit_line_re())


def fail_lines(harness_out):
    """`[(코드, 라벨, 상세)]` — 하네스 산출에서 **FAIL 줄만**.

    사람이 `state.json`을 열게 하지 않으려고 있는 함수다(B59 ①). 코드가 없는
    줄은 `None`으로 온다 — 지어내지 않는다.
    """
    out = []
    for ln in harness_out.splitlines():
        m = _GATE_LINE.match(ln)
        if m:
            if m.group(1) == "FAIL":
                out.append([m.group(2), m.group(3).strip(),
                            (m.group(4) or "").strip()])
            else:
                out.append(None)          # PASS — 이어지는 줄의 주인이 아니다
            continue
        # **판정 줄에 딸린 이어지는 줄을 잃지 않는다**(B64 ②) — 관문이 FAIL 아래에
        # 열 프로파일을 한 줄 더 싣는다. 한 줄 정규식만 보면 그 줄이 화면 재구성에서
        # 사라져, 사람이 원본 화면과 `status` 화면에서 **다른 것을 본다**.
        if out and out[-1] and ln.strip() and ln.startswith(" "):
            out[-1][2] = (out[-1][2] + "\n" + ln.rstrip()).strip()
    return [tuple(x) for x in out if x]


# ================================================ 분할 요약 화면 (B68 ②)
#
# **무엇을 기준으로 잘랐나**를 등록 화면이 말한다. 사내 실측 여덟째: 산문 xlsx를
# 고정 어댑터로 등록해 관문도 통과하고 청크도 잘 잘렸는데, 「기준」이 검수 뷰에
# 없고 generate 화면에는 분할 줄이 한 줄도 없었다.
#
# **새 계산 0** — 관문이 이미 `pipeline.parse`를 돌렸고 그 산출(`report["split"]` ·
# 프레임별 pick)을 한 줄 JSON으로 낸다(`kit/run_adapter.py::SPLIT_MARK`). 여기서
# 다시 파싱하면 같은 계산이 두 벌이 되고, 한쪽만 고쳐지는 날 화면이 갈린다.
def _kit_split_mark():
    """분할 요약 줄의 표시 — **킷에서 읽는다**(정본이 거기다 · `_kit_line_re`와 같은 결)."""
    m = re.search(r'^SPLIT_MARK = "(.+)"$',
                  (KIT / "run_adapter.py").read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("[관문] kit/run_adapter.py의 SPLIT_MARK를 찾지 못했다 — "  # [상태]
                         "분할 요약 줄의 표시가 정본에서 사라졌다 (관문 자체 결함 — "
                         "어댑터 잘못이 아니다)\n"
                         "  ▶ 다음 줄 — 반입물이 온전한지 본다:\n"
                         "     python doctor.py")
    return m.group(1)


def split_rows(harness_out):
    """관문 산출에서 분할 요약을 딴다 — `[{doc, split, picks}]`."""
    mark = _kit_split_mark()
    out = []
    for ln in (harness_out or "").splitlines():
        if ln.startswith(mark):
            try:
                out.append(json.loads(ln[len(mark):]))
            except json.JSONDecodeError:
                continue                    # 지어내지 않는다 — 없으면 줄이 없다
    return out


def split_block(harness_out):
    """프레임마다 한 줄 — 기준 · 레벨 · 크기 분포 (B68 ②).

    프레임이 없으면(table이거나 헤딩 0건) 빈 문자열이다 — 없는 것을 빈 줄로
    찍지 않는다.
    """
    lines = []
    for item in split_rows(harness_out):
        sp = item.get("split") or {}
        g = sp.get("목표구간") or []
        tail = (f"청크 {sp.get('청크수')} · 행수 {sp.get('행수_최소')}~"
                f"{sp.get('행수_최대')} · 짧음 {sp.get('너무_짧은_청크')} · "
                f"긺 {sp.get('너무_긴_청크')}")
        for pick in item.get("picks") or []:
            # **평균은 고른 레벨의 것**이다 — 문서 전체 평균을 레벨 옆에 적으면
            # 「그 레벨로 자르면 이만하다」로 읽히는데 값은 다른 것을 말한다.
            lv = (pick.get("레벨_분포") or {}).get(str(pick.get("분할_레벨"))) or {}
            size = (f"평균 {lv.get('행수_평균', sp.get('행수_평균'))}행"
                    + (f" · 목표 {g[0]}~{g[1]}" if len(g) > 1 else ""))
            oor = " · 구간 밖 — 최근접 레벨" if pick.get("분할_레벨_구간밖") else ""
            lines.append(f"   분할 — {pick.get('프레임')}  "
                         f"기준 {pick.get('분할_기준') or '미상'} · "
                         f"레벨 {pick.get('분할_레벨')} ({size}) · {tail}{oor}")
    return "\n".join(lines)


def _instruct_of(fails):
    """`--instruct`에 넣을 문면 — **`AUTO_FIX`가 답을 담는다고 판정한 줄**에서 딴다.

    담지 않는 줄로 지시를 만들면 「이렇게 고쳐라」가 내용 없이 나가고, 재생성은
    같은 실패를 되풀이한다. 하나도 없으면 `None`이고 화면은 문답 경로를 권한다.
    """
    for code, label, detail in fails:
        key = next((k for k in AUTO_FIX if k in label), None)
        if key:
            return f"{label}: {detail}" if detail else label
    return None


def gate_block(doc_type, st=None, *, stream=None):
    """**관문이 막을 때 뜨는 블록** — 이유와 **칠 수 있는 다음 줄** (B59 ①).

    실측 결함이 이것이다: 관문 FAIL 뒤 `confirm`은 「검수를 먼저 통과시켜라」라고만
    했고 `review`도 막았다 — **사내는 막다른 길에 섰다.** 막는 것은 설계대로다
    (통과분만 확정 — B50). 설계대로가 아닌 것은 **왜 막는지와 무엇을 치면 되는지를
    주지 않은 화면**이고, 그것이 C27(사내는 코딩하지 않는다) 위반의 실물이다.

    **세 명령이 이 함수 하나를 부른다**(`confirm`·`review`·`status`) — 문면이 세 벌이면
    그중 하나만 고쳐지는 날이 오고, 사람은 어느 화면을 믿을지 모른다.

    `stream`은 시험용이다(기본은 화면).
    """
    pr = (lambda *a: print(*a, file=stream)) if stream else print
    st = st or _state(doc_type) or {}
    fails = fail_lines(st.get("harness_out") or "")
    pr(f"■ 기계 관문 FAIL — {doc_type}")
    for code, label, detail in fails:
        pr(f"  [FAIL] {code}  {label}" + (f"  — {detail}" if detail else ""))
    if not fails:
        # 판정 줄이 없다 — 옛 판(태그 없는 줄)이거나 관문이 예외로 죽은 경우다.
        # **여기서 지어내지 않는다** — 호출자가 `regate`로 다시 돌린 뒤 온다.
        pr("  (판정 줄을 읽지 못했다 — 관문 산출이 옛 판이거나 비어 있다)")
    pr("")
    pr("  ▶ 다음 줄:")
    for line in _next_lines(doc_type, st, fails):
        pr(f"     {line}")
    return fails


def regate(doc_type, st):
    """**관문을 지금 코드로 다시 돈다** — 저장된 판정을 믿지 않는다 (B60 ①).

    실측 둘째: B59 이전에 만든 어댑터에 `status`가 「판정 줄이 남아 있지 않다」며
    **생성부터 다시 하라고 했다.** 어댑터·표본·패키지가 전부 디스크에 있는데 다시
    만들라고 한 것이다 — 저장된 `harness_out`이 태그 없는 옛 판이었고 폴백이 막다른
    길이었다. 그 폴백 문면은 없앴다: 판정 줄이 없으면 그 자리에서 돈다.

    저장값을 믿지 않는 근거 셋:
    ① **옛 `state.json`이 막다른 길이 된다** — 판정 줄의 문면은 바뀐다(B59가 태그를 붙였다).
    ② **관문이 넓어지면 옛 PASS는 무효다** — ①~④단 PASS로 ①~⑤단 관문을 지난 셈 치면
       안 된다. `confirm`은 **지금 코드의 관문**을 지나야 한다.
    ③ **코드 폴더를 나눠 쓴다** — 어느 판으로 돌았는지는 저장값이 말하지 않는다.
       다시 돌면 첫 줄 `[관문] ROOT=… git …`이 지금 것을 찍는다.

    비용은 표본 파싱 수 초, LLM 0이다. 재생성·문답은 타지 않는다(`fix=False`).
    저장된 `harness_out`은 이력이고 새 실행이 덮는다.
    """
    pkg_path = REVIEW / doc_type / "input_package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8")) if pkg_path.exists() else None
    st["machine_gate"] = machine_gate(doc_type, st, st["samples"], pkg, fix=False)
    _save_state(doc_type, st)
    return st["machine_gate"]


def _next_lines(doc_type, st, fails):
    """칠 수 있는 **완성된 명령** 목록 — 동사가 아니라 한 줄이다.

    「검수를 통과시켜라」는 사람이 할 수 없는 일이라 문장 자체를 두지 않는다.
    """
    out = []
    inst = _instruct_of(fails)
    if inst:
        out.append(f'python -m cli.register review {doc_type} '
                   f'--instruct "{inst}"')
    else:
        # 문면이 답을 담지 않는 실패다 — 문답이 그것을 통역하는 자리다(B50).
        out.append(f"python -m cli.register review {doc_type} "
                   f"--instruct \"<무엇을 고칠지 한 줄>\"")
        out.append("     └ 위 FAIL 줄이 고칠 방법을 담지 않는다 — "
                   "문답이 예외 원문을 모델에 넘겨 통역한다")
    samples = st.get("samples") or []
    if samples and not st.get("use_basic"):
        prop = basic_adapter_proposal(samples)
        if prop:
            out.append(f"python -m cli.register generate {doc_type} "
                       f"{st.get('layer', '<층>')} "
                       f"{' '.join(str(x) for x in samples)} --use-basic")
            out.append(f"     └ {prop['reason']}")
    out.append(f"python -m cli.register status {doc_type}"
               "   (이 블록을 다시 본다)")
    return out


def _orphan_of(st):
    """스키마 대장에 없는 열 — 관문의 셋째 조건(B49). 어댑터를 못 읽으면 빈 목록이다
    (그 경우 하네스가 이미 FAIL이므로 여기서 다시 말할 것이 없다)."""
    try:
        mod = _load(_at(st["adapter"]), f"gate_{st['doc_type']}")
        schema = json.loads((_at(st["schema"])).read_text(encoding="utf-8"))
        return unmappable_of(schema, mod)[2]
    except Exception:
        return []


def _ask_more(doc_type, codes):
    """1회 재생성 뒤에도 실패하면 **묻고 진행한다** — 비용 동의(좌표 보조와 동형).

    구판은 `더 돌릴까? [y/N]` 한 줄이었다(B62 ④). 이미 한 번 고쳤다는 것, y가 무엇을
    여는지, N이 **막다른 길**이라는 것을 아무것도 말하지 않았고 **기본값이 그 막다른
    길**이었다. 기본을 y로 돌리고, n을 골라도 이어갈 명령을 함께 준다.
    """
    print(f"   자동 수정 1회 뒤에도 FAIL {len(codes)}건 ({' · '.join(codes) or '?'})")
    print(f"   [Y] 문답을 열고 재생성한다 (LLM 호출)   "
          f"[n] 여기서 끝 — 관문 FAIL이라 confirm은 막힌다.")
    print(f"       n 뒤에도 이어갈 수 있다:  "
          f"python -m cli.register review {doc_type} --instruct \"…\"")
    try:
        ans = input("   더 돌릴까? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("   (비대화형 — 기본 Y로 이어간다)")
        ans = ""
    return ans not in ("n", "no")


def _failure_persist(doc_type, pkg, samples, ask):
    """실패 뒤 문답의 라운드 저장기 — 패키지의 `human.hint`에 **이어 붙인다.**

    묶음에 `context`를 달아 생성 전 문답과 구분한다: 같은 그릇이지만 물은 이유가
    다르고, 재현할 때 「무엇을 보고 답했나」가 달라진다.
    """
    d = _dir(doc_type)
    path = d / "input_package.json"
    batch = _new_batch([str(x) for x in (samples or [])])
    batch["context"] = "기계 관문 실패"

    def _persist(rounds, decisions=None):
        # **전문은 로그로**(B62 ②) — 패키지를 못 읽어도 전문은 남아야 한다.
        write_rounds(doc_type, batch["at"], batch["samples"], rounds)
        try:
            obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() \
                else {"human": {"hint": {}}}
        except (OSError, json.JSONDecodeError):
            return                              # 패키지를 못 읽으면 조용히 지나간다
        if decisions is not None:
            batch["decisions"] = decisions      # 확정 요약(B60 ②) — 판단은 패키지에
        hint = (obj.get("human") or {}).get("hint")
        keep = [b for b in _hint_batches(hint) if b.get("at") != batch["at"]]
        obj.setdefault("human", {})["hint"] = _merge_hint(hint, keep + [batch])
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        if isinstance(pkg, dict):               # 메모리 사본도 같이 맞춘다
            pkg.setdefault("human", {})["hint"] = obj["human"]["hint"]

    return _persist


def _finish_generate(doc_type, st, samples, pkg=None):
    """생성의 끝 — **기계 관문을 세우고 그 사실을 화면이 말한다** (M9 개정 · B50).

    통과하지 못하면 산출은 `review/`에 남되 **검수로 넘어가지 않는다**: 미통과
    산출을 검수 화면에 올리면 사람이 기계의 몫을 대신 지게 된다.
    """
    st["machine_gate"] = machine_gate(doc_type, st, samples, pkg)
    _save_state(doc_type, st)
    if st["machine_gate"] == "PASS":
        print(f"   기계 관문 PASS — **뷰까지 여기서 만든다**(B58 ⑤)")
        # **뷰를 만드는 함수는 하나다** — `cmd_review`를 그대로 부른다. 두 벌이면
        # 「생성이 보여 준 화면」과 「검수가 보여 주는 화면」이 갈리고, 사람이 승인한
        # 것이 어느 쪽인지 사후에 못 가린다.
        #
        # **여기서는 LLM을 켜지 않는다**(`llm_coord=False` · `extract=False`) —
        # 생성은 사람이 아직 아무것도 고르지 않은 자리이고, 비용 관문은 사람이
        # 켜는 것이다. 켜려면 `review`로 들어간다 — 그것이 그 명령이 남는 이유다.
        rc = cmd_review(doc_type, llm_coord=False, extract=False)
        print(f"\n   ▶ 다음 두 줄이면 끝난다 — 뷰를 보고 승인한다:")
        print(f"       (뷰 확인) {(REVIEW / doc_type / 'view.html').relative_to(ROOT)}")
        print(f"       python -m cli.register confirm {doc_type} --by <승인자>")
        print(f"   고칠 것이 있을 때만: python -m cli.register review {doc_type} "
              f"--instruct \"…\"  (좌표 LLM 보조·추출 리허설도 그쪽이다)")
        return rc
    print(f"   기계 관문 FAIL — **뷰를 만들지 않았다.** 산출은 "
          f"{(REVIEW / doc_type).relative_to(ROOT)}에 남겼다\n")
    gate_block(doc_type, st)
    print(f"     python -m cli.register generate {doc_type} --resume"
          f"   (같은 표본으로 초안만 다시 받는다)")
    return 1


# 시스템이 채운 값이 사는 자리 — 어댑터 파일 **끝**의 표시 블록. 다시 채울 때
# 이 표시부터 파일 끝까지를 갈아 끼우므로 **되풀이해도 하나**다(멱등).
_FILLED_MARK = "# ── 시스템이 채운다 (B62 ①-c)"


def stamp_system_fields(st, samples):
    """**관문 입구에서 시스템이 아는 값을 시스템이 쓴다** (B62 ①-c·③).

    둘이다 — `expects.header_labels`(표본의 실물 헤더)와 `adapter_version`(판 번호).
    원리 하나로 묶인다: **시스템이 이미 아는 값은 LLM이 쓰지 않는다.** 받아 적게
    하고 글자로 대조하면 한 글자 흘린 것이 `adapter_mismatch`가 되고, 판 번호는
    템플릿 예시의 `"1.0"`이 그대로 베껴져 **아무도 안 올린다**(재생성 2회째
    `adapter_rev2.py` 안이 `1.0`이었다 — `state.revision`과 서로 모르는 두 카운터).

    LLM이 원본 헤더 문자열을 받아 적고 시스템이 그것을 글자로 대조하는 구조였다 —
    한 글자만 흘려도 `adapter_mismatch`이고, 그 값은 **시스템이 표본에서 읽으면
    되는 것**이다. 원리: **시스템이 아는 값은 LLM이 쓰지 않는다.**

    자리가 「초안 저장 시점」이 아니라 **관문 입구**인 이유 둘:
    ① 결정적·멱등이라 판단을 바꾸는 일이 아니다 — `fix` 양쪽(generate·status·confirm)
       어디서 들어와도 같은 값이 된다.
    ② **이미 만들어진 어댑터가 재생성 없이 살아난다** — ①-a 이전 코드로 생성한
       `review/<doc_type>/`가 `status` → `confirm`으로 확정될 수 있어야 하고,
       그 경로에 **LLM 호출이 0이어야** 한다.

    `table`에만 한다(`header_labels`는 D-29의 table 한정). prose 위임 래퍼는
    `ADAPTER = {**basic_ppt.ADAPTER, …}`라 `expects`가 **코어 어댑터와 같은 객체**다 —
    거기에 쓰면 코어 어댑터가 런타임에 오염된다.

    **채우기 전에 위치를 검증한다**: `columns`가 가리키는 헤더 셀이 비어 있으면
    `header_row`가 틀린 것이므로 채우지 않고 그대로 둔다 — 관문의 G26이 그것을
    말한다. 빈 배열로 덮어쓰면 표류 감지가 조용히 죽는다.

    돌려주는 것은 화면 한 줄(정보)이거나 `None`이다.
    """
    path = _at(st["adapter"])
    try:
        mod = _load(path, f"fill_{st['doc_type']}")
        a = mod.ADAPTER
    except Exception:
        return None                         # 못 읽으면 관문의 ①단이 말한다
    exp = a.get("expects") or {}
    # **판 번호는 계열과 무관하다** — prose도 판이 오른다. `1.{revision}`이고
    # `--revise`는 revision을 이어가므로 새 판이 옛 판보다 작아지지 않는다.
    want_ver = f"1.{st.get('revision', 0)}"
    if a.get("payload_kind") != "table" or not exp.get("header_row"):
        return _write_stamp(st, path, None, want_ver, a.get("adapter_version"))
    raw = None
    for smp in samples:
        try:
            raw = reader.read(str(smp))
            break
        except Exception:
            continue
    # **`columns`도 시스템이 확정한다**(B64 ①) — 값이 헤더 라벨이거나 합치기
    # 리스트여도 여기서 열문자가 된다. 원리는 header_labels와 같다: 어느 헤더인가는
    # LLM이 고르고 **어느 글자인가는 시스템이 표본에서 센다.**
    cols, bad = ({}, []) if raw is None else preflight.resolve_columns(raw, exp)
    if raw is None or bad or preflight.header_row_suspect(raw, exp) is not None:
        # **위치가 의심스러우면 채우지 않는다** — 빈 행을 읽어 `[]`로 덮어쓰면
        # 표류 감지가 조용히 죽는다. 관문의 G26이 그 사실을 말한다(해석 실패도 거기서).
        return _write_stamp(st, path, None, want_ver, a.get("adapter_version"))
    actual = preflight.header_labels(raw, exp["header_row"], exp)
    if not actual:
        return _write_stamp(st, path, None, want_ver, a.get("adapter_version"))
    declared = [reader.norm_label(x) for x in (exp.get("header_labels") or [])]
    note = _write_stamp(st, path, (actual, raw, exp, samples), want_ver,
                        a.get("adapter_version"),
                        cols if cols != (exp.get("columns") or {}) else None)
    if declared == actual:
        return note
    diff = [x for x in actual if x not in declared] + \
           [x for x in declared if x not in actual]
    return (f"   헤더 문자열은 시스템이 채운다 — LLM 선언 {len(declared)} / "
            f"실물 {len(actual)} · 다른 것 {len(diff)}: {diff[:5]}")


def _write_stamp(st, path, header, want_ver, had_ver, cols=None):
    """표시 블록을 **작업 사본**에 쓴다 — 되풀이해도 하나다(멱등).

    **원본에 쓰지 않는다.** 초안의 출처는 fixture(외부 LLM 실산출 스냅샷 · D-26)이거나
    킷 전시물일 수 있고 **그 둘은 손대지 않는 자리다**. 고치는 것은 언제나
    `review/<doc_type>/`이고, 확정이 거기서 정본으로 승격한다.
    """
    src = path.read_text(encoding="utf-8")
    if REVIEW not in path.parents:
        path = _dir(st["doc_type"]) / "adapter.py"
        st["adapter"] = str(_rel(path))
    lines = [f"{_FILLED_MARK} — 관문이 그 자리에서 채운다. 손으로 고치지 마라."]
    if header:
        actual, raw, exp, samples = header
        lines += [f"#    표본: {Path(str(samples[0])).name} · header_row "
                  f"{exp['header_row']} · 시트 "
                  f"{(reader.sheet_of(raw, exp)[0] or {}).get('name')}",
                  f"ADAPTER[\"expects\"][\"header_labels\"] = {actual!r}"]
    if cols:
        # **해석된 열문자를 쓴다**(B64 ①) — 이후 코드(스켈레톤 extract·preflight·
        # orphan)는 열문자만 본다. 라벨은 여기까지다.
        lines.append(f"ADAPTER[\"expects\"][\"columns\"] = {cols!r}")
    lines.append(f"ADAPTER[\"adapter_version\"] = {want_ver!r}"
                 f"   # state.revision = {st.get('revision', 0)}")
    head = src.split(_FILLED_MARK)[0].rstrip("\n")
    path.write_text(head + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    if had_ver and str(had_ver) != want_ver:
        return (f"   판 번호는 시스템이 찍는다 — LLM 선언 {had_ver!r} → "
                f"{want_ver!r} (state.revision {st.get('revision', 0)})")
    return None


def _gate_done(doc_type, verdict):
    """관문이 판정을 내고 **열 판정 대장을 찍는다** (B67 ③).

    자리가 관문의 반환 자리인 이유: 사람이 보는 「지금 상태」는 판정이 끝난 뒤의
    대장이다. 루프 중간마다 찍으면 재생성 전 대장이 화면에 남아 마지막 것과
    섞인다. `status`·`confirm`도 이 함수를 지나므로 **화면 한 벌**이다.
    """
    blk = ledger_block(doc_type)
    if blk:
        print(blk)
    return verdict


def machine_gate(doc_type, st, samples, pkg=None, *, fix=True):
    """**생성 안의 기계 관문** — 통과분만 검수로 넘긴다 (문서 1 M9 개정 · B50).

    구판은 하네스를 검수에서 돌려 실패를 **사람 화면에 올렸다.** 그러면 사내가
    기계 실패를 자연어로 통역해 `--instruct`로 되돌려주는 것이 유일한 해소 수단이
    되는데, **사내는 코딩하지 않는다**(C27) — 그 통역을 할 수 있는 사람이 없다.

    그래서 여기서 돌고, 실패는 **문면이 답을 담는지**로 갈라 처리한다(`AUTO_FIX`):
    담으면 그 문면을 그대로 지시로 실어 **자동 재생성 1회**, 담지 않으면 **문답**.
    1회 뒤에도 실패하면 묻고 진행한다 — 같은 항목이 또 실패하면 프롬프트가 그것을
    못 고치는 것이고, 다른 항목이 실패하면 재생성이 맞던 곳을 깬 것이라 둘 다 사람
    판단이 필요하다.
    """
    tries, prev_codes = 0, None
    while True:
        # **관문 입구다**(B62 ①-c) — `fix` 양쪽에서 돈다. 하네스가 읽기 전에 채운다.
        _info = stamp_system_fields(st, samples)
        if _info:
            print(_info)
        # **열 판정 대장은 관문 입구에서 선다**(B67 ②) — 스탬프가 `columns`를
        # 열문자로 확정한 **직후**라야 대장의 열문자가 어댑터의 것과 같다.
        sync_ledger(doc_type, st, samples)
        ok, out = harness(_at(st["adapter"]), _at(st["schema"]), samples,
                          package=REVIEW / doc_type / "input_package.json",
                          doc_type=doc_type)          # G4G 대장 커버리지 (B76 ②)
        print(f"   기계 관문(하네스): {'PASS' if ok else 'FAIL'} — "
              f"{out.count('[PASS]')} PASS / {out.count('[FAIL]')} FAIL")
        # **분할은 관문 결과 줄 다음이다**(B68 ②) — prose일 때만 줄이 난다.
        # `status`·`confirm`도 관문을 다시 도니 같은 재료로 같은 줄을 낸다.
        _sb = split_block(out)
        if _sb:
            print(_sb)
        orphan = _orphan_of(st)
        if orphan:
            print(f"   스키마 대장에 없는 열 {len(orphan)}건 — "
                  f"{[u['field'] for u in orphan]}")
        verdict = gate_verdict(ok, True, orphan)
        st["harness_out"] = out
        # 판정이 어느 열을 말하면 그 행이 미해결이다 — 대장만 보고 넘어가지 않게.
        mark_ledger_fails(doc_type, fail_lines(out))
        if verdict == "PASS":
            return _gate_done(doc_type, verdict)
        if not fix:
            # **판정만 다시 낸다**(B60 ①) — `status`·`confirm`의 갈래다. 재생성·문답을
            # 타지 않는다: 그 둘은 LLM을 부르고, 상태를 보러 온 사람이 그것을
            # 시작하게 두면 안 된다. 고치는 일은 `review --instruct`가 하고 그
            # 명령이 다음 줄로 화면에 뜬다.
            return _gate_done(doc_type, verdict)
        auto, ask = classify_failures(out)
        for ln in auto + ask:
            print(f"     {ln}")
        if orphan and not (auto or ask):
            # 하네스는 통과했는데 대장만 어긋났다 — 재생성 지시가 될 문면이 있다.
            auto = [f"[FAIL] 원본 헤더의 열 {[u['field'] for u in orphan]}이 스키마의 "
                    f"fields에도 unmappable에도 없다 — 전 열이 둘 중 하나에 있어야 한다"]
        # **관문 자체 결함만 남았으면 묻지 않는다**(B62 ④ · B59 ② `GATE_SELF`) —
        # 재생성으로 못 고치는 것을 두고 「더 돌릴까」를 묻는 것은 비용만 쓰는 질문이다.
        _codes = [c for c, _l, _d in fail_lines(out)]
        if _codes and all(c in GATE_SELF for c in _codes):
            print(f"   남은 FAIL이 관문 자체 결함뿐이다 ({' · '.join(_codes)}) — "
                  f"재생성으로 고칠 수 없어 묻지 않고 끝낸다")
            return _gate_done(doc_type, "FAIL")
        # **같은 실패가 되풀이되면 멈춘다** — 이 함수의 머리말이 이미 말하는 성질이다:
        # 「같은 항목이 또 실패하면 프롬프트가 그것을 못 고치는 것」. 기본값이 Y가
        # 되면서(B62 ④) 이 자리가 **유일한 종료 조건**이 됐다 — 없으면 비대화형
        # 실행이 같은 산출을 무한히 다시 받는다(실측: mock에서 대안본이 없으면
        # `draft`가 같은 초안을 돌려줘 루프가 끝나지 않았다).
        if tries >= 1 and _codes == prev_codes:
            print(f"   같은 FAIL이 되풀이된다 ({' · '.join(_codes) or '?'}) — "
                  f"재생성이 이것을 못 고친다. 여기서 끝낸다.")
            print(f"   이어가려면: python -m cli.register review {doc_type} "
                  f"--instruct \"…\"")
            return _gate_done(doc_type, "FAIL")
        if tries >= 1 and not _ask_more(doc_type, _codes):
            return _gate_done(doc_type, "FAIL")
        prev_codes = _codes
        tries += 1
        if ask:
            print(f"   → 문면이 답을 담지 않는 실패 {len(ask)}건 — 문답을 연다")
            # **여기도 라운드마다 즉시 저장한다**(B55 ②-3) — 구판은 `st`에 한 줄
            # 요약만 남기고 전문이 사라졌으며, 라운드 저장이 없어 중간에 죽으면
            # 전량 유실이었다. B43 ⑤가 생성 전 문답에서 막은 것과 같은 유실이다.
            _fp = _failure_persist(doc_type, pkg, samples, ask)
            rounds = _interview(pkg or {}, context=ask, on_round=_fp)
            _dec = iv_finalize(pkg or {}, rounds, context=ask)
            _fp(rounds, decisions=_dec)
            apply_decisions_to_ledger(doc_type, _dec)
            answered = "; ".join(h["answer"] for h in rounds if h.get("answer"))
            # **원문은 답이 있어도 함께 보낸다**(B59 ②). 구판은 사람이 답하면
            # `"사람 문답: …"`만 보내 **예외 원문·validator 결함 목록이 지시에서
            # 사라졌다** — 사람의 답은 「무엇을 고치고 싶다」이고, 모델이 그것을
            # 코드 수정으로 옮기려면 「무엇이 어떻게 깨졌나」가 함께 있어야 한다.
            # 둘은 대체재가 아니라 짝이다.
            instruction = ("사람 문답: " + answered + "\n\n[관문 판정 원문]\n"
                           + "\n".join(ask)) if answered else "\n".join(ask)
            by = "사람(문답)" if answered else "자동(하네스 문면 — 문답 무응답)"
        else:
            instruction, by = "\n".join(auto), "자동(하네스)"
        print(f"   → 재생성 지시 ({by}) — 보낸 문면 그대로:")
        for ln in instruction.splitlines():
            print(f"     {ln}")
        st["revision"] = st.get("revision", 0) + 1
        # **자동으로 보낸 지시도 이력에 남긴다**(B50) — 조용히 도는 구간을 두지
        # 않는다: 남지 않으면 「몇 회 만에 통과했나」가 축적되지 않아 프롬프트 품질
        # 문제와 수렴 문제를 나중에 가를 수 없다.
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": instruction,
             "at": store._now(), "by": by})
        # **지시를 넘긴다**(B55 ①) — 기록만 하고 안 넘기면 모델은 같은 입력을
        # 다시 받고, 「실패 문면을 그대로 지시로」가 공문이 된다.
        ad, sc = draft(doc_type, st["revision"], instruction=instruction,
                       history=st.get("instructions"))
        if ad is None:
            print(f"   재생성 초안을 얻지 못했다 — "
                  f"fixture '{doc_type}_rev{st['revision']}' 없음")
            return _gate_done(doc_type, "FAIL")
        st["adapter"] = str(_rel(ad))
        st["schema"] = str(_rel(sc))
        print(f"   재생성 {st['revision']}회째 → {_rel(ad)}")


def _profiles(doc_type):
    """입력 패키지의 열 프로파일 — **파일에서 읽는다**(상태에 복제하지 않는다)."""
    p = REVIEW / doc_type / "input_package.json"
    if not p.exists():
        return []
    pkg = json.loads(p.read_text(encoding="utf-8"))
    return [pp for h in ((pkg.get("system") or {}).get("reader_head") or [])
            for pp in (h.get("열_프로파일") or [])]


def role_table(schema, adapter_mod, st=None, prof=None):
    """구획 2 — 필드 → role 배정표. **근거를 병기**한다(§7 구조).

    **6지선다는 role 5종 + UNMAPPABLE**이고, 구조 필드·payload 고정 키는 그 대상이
    아니다(C17 · D-46) — 미해결이 아니라 정상·완결이라 질문거리가 아니기 때문이다.
    공용 블록 유래 필드는 배정표에 뜨되 출처를 밝힌다.
    """
    fields, from_blocks = load_blocks(schema)
    rows = []
    for f, spec in fields.items():
        rows.append({"field": f, "role": spec.get("role"),
                     "category": spec.get("category"),
                     "attach_to": spec.get("attach_to_field"),
                     "reason": spec.get("정의문")
                     or ("공용 블록이 선언한 필드다" if f in from_blocks
                         else "생성 세션의 배정 근거"),
                     **({"from_block": "공용 블록"} if f in from_blocks else {})})
    # **여섯째 경로에 올리는 것은 「판단이 안 선 열」뿐이다**(B49 · C19 개정).
    # 판정해서 뺀 열(`excluded`)은 제외 목록이 자리이고, 대장에 없는 열(`orphan`)은
    # 결함이다 — 셋을 한 표에 섞으면 구판처럼 다시 「같은 질문」이 된다.
    for u in unmappable_of(schema, adapter_mod)[1]:
        rows.append({"field": u["field"], "role": "UNMAPPABLE",
                     "reason": f"생성이 판단하지 못했다: {u.get('reason') or '사유 없음'}"})

    # ── 사람이 볼 것을 줄인다 (B39 ③ — 3단 깔때기의 셋째 단) ──────────
    # **전 열을 평평하게 보이면 이 절차의 목적이 달성되지 않는다**(실측: attribute
    # 25개가 평평하게 올라왔다). 먼저 볼 것 둘을 표시한다:
    #   ①기계 제안과 LLM 판정이 갈린 열  ②확신 경계선 부근
    rep = (st or {}).get("generation_report") or {}
    rank = {x["field"]: x["rank"] for x in (rep.get("attribute_ranking") or [])}
    cut = rep.get("confidence_cut")
    # **한 필드가 열 여럿일 수 있다**(합치기 — B64 ①). 하나로 접으면 뒤 열이
    # 조용히 사라지고, 그 자리가 이번 사고의 첫 원인이었다(B76 ①).
    _led_cols = {}
    for x in read_ledger((st or {}).get("doc_type", "")):
        if x.get("field"):
            _led_cols.setdefault(x["field"], []).append(x["col"])
    sug = {}
    for s in (prof or []):
        for col, v in (s.get("열") or {}).items():
            sug[col] = (v.get("기계제안") or {}).get("제안")
    for r in rows:
        marks = []
        # **열문자는 대장에서만 읽는다**(B67 ③ · B76 ②) — 어댑터 `columns` 폴백을
        # 두면 대장이 빈 필드가 조용히 통과하고(이번 사고의 둘째 원인), 그 값이
        # 합치기 리스트면 `sug`의 키로 들어가 죽는다(첫 원인 — 형은 G4F가 막는다).
        # 대장이 스키마 필드 전부를 덮는 것은 `G4G`가 지킨다.
        cols = _led_cols.get(r["field"]) or []
        # 합치기면 **기계 제안이 있는 첫 열**로 대조한다 — 열 하나를 가리킬 수
        # 없다는 사실이 대조를 건너뛸 이유는 아니다.
        s = next((sug.get(c) for c in cols if sug.get(c)), None)
        if s and s != "role 판정 대상" and r.get("role") != s:
            marks.append(f"기계 제안({s})과 갈림")
            r["machine_suggest"] = s
        if r["field"] in rank:
            r["rank"] = rank[r["field"]]
            if cut is not None and abs(rank[r["field"]] - cut) <= 1:
                marks.append("확신 경계선 부근")
        if marks:
            r["attention"] = " · ".join(marks)
    # **먼저 볼 것을 위로 올린다** — 화면 순서가 곧 검토 순서다.
    rows.sort(key=lambda r: (0 if r.get("attention") else 1, r.get("rank", 999)))
    return rows


def col_values(cols):
    """`columns` 값을 **열문자 집합**으로 편다 — 값 셋(열문자·라벨·리스트) 공통 (B64 ①).

    해석이 끝난 뒤에는 전부 열문자이지만, 해석 전(사람이 라벨을 적은 채)의 어댑터도
    이 함수를 지난다 — 그때는 라벨이 섞여 있고 그것은 관문이 FAIL로 답한다.
    """
    out = set()
    for v in (cols or {}).values():
        out |= {str(x) for x in v} if isinstance(v, (list, tuple)) else {str(v)}
    return out


def _unmapped_labels(exp, adapter_mod):
    """어댑터가 **출력하지 않는** 헤더 라벨 — 차집합 복원.

    구판 스키마의 복원 재료이자, 신판에서 `orphan`(대장에 없는 열)을 찾는 재료다.
    `columns`가 가리키는 열은 여기 오지 않는다 — **구조 필드**(`process_ref`·
    `electrode_type` 등)가 그 자리이고, 그것은 UNMAPPABLE이 아니라 정상·완결이다
    (D-46 · 생성 템플릿 「구조 필드는 UNMAPPABLE이 아니다」).
    """
    labels, cols = exp.get("header_labels") or [], exp.get("columns") or {}
    if not labels or not cols:
        return []
    # **위치 가정을 두지 않는다**(문서 6 §6.4-6: "빈 셀은 배열에 넣지 않는다").
    # `labels`의 i번째가 i+1번째 열이라고 보면 헤더 행에 빈 칸이 하나만 있어도
    # 그 뒤 전부가 한 칸씩 밀려 **엉뚱한 열이 UNMAPPABLE로 뜬다** — 사람이
    # 판정해야 할 것이 화면에서 바뀌는 셈이다.
    #
    # 대신 **실물 헤더에서 열 문자를 다시 읽는다.** 읽을 수 없으면(표본 경로가
    # 없거나 포맷 패키지가 없으면) 위치 가정으로 떨어지되 **그 사실을 남긴다** —
    # 조용히 틀린 답을 내지 않는다.
    # **리스트를 펼쳐 센다**(B64 ①) — `columns` 값은 열문자·라벨·리스트 셋이고,
    # 합친 열도 **쓴 열**이다. 펼치지 않으면 집합에 리스트가 들어가 계산이 깨지거나
    # (대조표 6) 합쳐진 둘째 열이 orphan으로 잘못 뜬다.
    used = col_values(cols)
    pos = _label_columns(exp, adapter_mod)
    if pos:
        # 라벨의 열 **전부**가 쓰였을 때만 쓴 것이다 — 둘 중 하나만 쓰면 나머지는
        # 판정되지 않은 열이고, 그것이 화면에서 사라지면 안 된다(D-82).
        return [lab for lab, letters in pos.items()
                if any(x not in used for x in letters)]
    store.append_defect(
        f"UNMAPPABLE 복원이 위치 가정으로 떨어졌다 — 실물 헤더를 읽지 못했다 "
        f"(doc_type={(getattr(adapter_mod, 'ADAPTER', {}) or {}).get('doc_type')})")
    return [labels[i] for i in range(len(labels)) if _col(i + 1) not in used]


def unmappable_of(schema, adapter_mod):
    """전 열의 판정 — **`(excluded, undecided, orphan)` 셋**으로 가른다 (C19 개정 · B49).

    | 갈래 | 무엇 | 화면 |
    |---|---|---|
    | `excluded` | 생성이 **판정해서 뺐다**(사유 필수) | 제외 목록 — **질문이 아니다** |
    | `undecided` | 생성이 **판단을 못 했다** | 6지선다 질문 |
    | `orphan` | 헤더에 있는데 **어느 쪽에도 없다** | 결함 — 기계 관문을 막는다 |

    셋을 가르는 이유(실측): 구판은 차집합 하나로 복원해 셋이 **같은 질문**으로 떴다.
    그래서 「생성 때 이미 판정한 열」이 검수에서 다시 물어졌고(사내 실사용 신고),
    「생성이 빠뜨린 열」은 그 질문 더미에 묻혀 보이지 않았다.

    **구판 스키마**(`unmappable` 키 없음)는 차집합 결과를 전부 `undecided`로 본다 —
    「판정해서 뺐다」고 말할 근거가 어디에도 없기 때문이다(하위 호환).
    """
    exp = (getattr(adapter_mod, "ADAPTER", {}) or {}).get("expects") or {}
    declared = schema.get("unmappable")
    if declared is None:
        return [], [{"field": f, "kind": "undecided",
                     "reason": "구판 스키마 — 판정 기록이 없다 "
                               "(generate --resume으로 다시 뽑으면 갈린다)"}
                    for f in _unmapped_labels(exp, adapter_mod)], []
    excluded, undecided = [], []
    for u in declared:
        item = dict(u) if isinstance(u, dict) else {"field": str(u), "reason": ""}
        kind = item.get("kind")
        if kind == "excluded":
            excluded.append(item)
            continue
        if kind != "undecided":
            # **모르면 묻는다** — enum 밖의 값을 조용히 「제외」로 치지 않는다.
            store.append_defect(
                f"unmappable.kind가 닫힌 2값 밖이다 — {kind!r} "
                f"(field={item.get('field')!r})")
            item = {**item, "kind": "undecided"}
        undecided.append(item)
    named = {i.get("field") for i in excluded + undecided}
    orphan = [{"field": lab, "kind": "orphan",
               "reason": "스키마 대장에 없다 — 생성이 빠뜨렸거나 문서 양식이 바뀌었다"}
              for lab in _unmapped_labels(exp, adapter_mod) if lab not in named]
    return excluded, undecided, orphan


def _label_columns(exp, adapter_mod):
    """헤더 라벨 → **실제 열 문자 리스트**. 실물을 못 읽으면 빈 dict (B64 ③)."""
    sample = getattr(adapter_mod, "SAMPLE", None) or exp.get("sample_path")
    if not sample or not Path(sample).exists():
        return {}
    try:
        raw = reader.read(str(sample))
        # **대응을 여기서 다시 짓지 않는다**(B64 ③) — 정규화도 중복 처리도 한 자리다
        # (`preflight.label_columns`). 두 벌이던 동안 한쪽은 `str(v)`, 다른 쪽은
        # `str(v).strip()`이라 같은 셀을 다르게 읽었다(B62 ①-c가 고친 자리).
        return preflight.label_columns(raw, exp)
    except Exception:
        return {}


# ================================================ 열 판정 대장 (B67 ②)
#
# **판단과 코드를 가른다.** 생성 LLM이 열마다 내린 판단(role · 필드↔열 대응 · 안 쓰는
# 열)이 지금까지 **코드 안에만** 살았다 — `adapter.py`·`schema.json`. 그래서 코드를
# 버리면 판단도 버려지고, 코드를 살리면 오류도 산다(실측: G31로 끝난 등록을
# `--resume`하면 같은 G31). 대장은 그 판단만 따로 적어 두는 자리다: 재생성은 코드를
# 새로 받되 **판단은 이어받는다.**
#
# **LLM이 대장을 쓰지 않는다**(C38 「LLM은 고르고, 시스템이 쓴다」) — 요약을 또
# 시키지 않는다. 대장은 산출·판정·지시에서 시스템이 **뽑는** 것이고 전부 결정적이다.
LEDGER_FILE = "columns.json"


def ledger_path(doc_type):
    return _dir(doc_type) / LEDGER_FILE


def read_ledger(doc_type):
    """대장 행 목록 — 없거나 깨졌으면 빈 목록이다."""
    p = ledger_path(doc_type)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("columns") or []
    except (json.JSONDecodeError, OSError):
        return []


def _save_ledger(doc_type, rows):
    ledger_path(doc_type).write_text(
        json.dumps({"doc_type": doc_type, "at": store._now(), "columns": rows},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def _col_named(text, row):
    """이 문면이 **이 열을 이름으로 부르는가** — 열문자·라벨·필드 중 하나로.

    **못 정하면 건드리지 않는다**가 규칙이라 매칭은 좁게 잡는다: 열문자는 따옴표
    안이거나 `D열`이거나 낱말 경계에 선 것만 센다. 한 글자 열문자가 아무 문장에나
    걸리면 **엉뚱한 행이 미해결로 뒤집힌다.**
    """
    text = text or ""
    for key in (row.get("label"), row.get("field")):
        if key and key in text:
            return True
    col = row.get("col") or ""
    if not col:
        return False
    if f"'{col}'" in text or f'"{col}"' in text or f"{col}열" in text:
        return True
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(col)}(?![A-Za-z0-9가-힣])",
                     text) is not None


def _labels_by_col(exp, mod, samples):
    """열문자 → 헤더 라벨. **표본에서 읽는다** — 어댑터의 `SAMPLE`은 있을 수도 없다.

    대조는 한 함수다(`preflight.label_columns` — B64 ③). 여기서 다시 짓지 않는다.
    """
    out = {}
    for smp in list(samples or []) + [None]:
        try:
            raw = reader.read(str(smp)) if smp else None
            pos = preflight.label_columns(raw, exp) if raw else _label_columns(exp, mod)
        except Exception:
            continue
        for lab, letters in (pos or {}).items():
            for c in letters:
                out.setdefault(c, lab)
        if out:
            return out
    return out


def sync_ledger(doc_type, st, samples=None):
    """산출에서 열 판정을 뽑아 대장을 다시 세운다 — **LLM 0 · 결정적**.

    자리는 **관문 입구**(`stamp_system_fields` 직후)다. 초회·재생성 매번 돌고,
    읽는 것은 셋이다: 확정된 `expects.columns`(C38 스탬프 뒤 열문자) · `schema.json`의
    필드별 role · `unmappable[]`. **행 집합은 열 프로파일이 정한다** — 표본에 있는
    열은 판정됐든 아니든 전부 한 행을 갖는다: 빠진 열이 대장에서도 빠지면
    「생성이 빠뜨렸다」가 보이지 않는다.

    **orphan을 여기서 다시 계산하지 않는다** — `unmappable_of`의 셋째 값을 읽는다.
    계산이 둘이면 한쪽만 고쳐지는 날이 오고, 그날 관문과 대장이 다른 말을 한다.

    `by`(판단 출처)는 **판단이 그대로면 그대로 둔다** — 관문을 다시 돌렸다고
    사람이 정한 열이 「생성이 정했다」로 바뀌면 안 된다.
    """
    prof = {}
    for pp in _profiles(doc_type):
        for col, item in (pp.get("열") or {}).items():
            prof.setdefault(col, item)
    try:
        mod = _load(_at(st["adapter"]), f"led_{doc_type}")
        schema = json.loads((_at(st["schema"])).read_text(encoding="utf-8"))
    except Exception:
        return read_ledger(doc_type)        # 못 읽으면 관문 ①단이 말한다
    a = getattr(mod, "ADAPTER", {}) or {}
    if a.get("payload_kind") != "table":
        # **prose에는 열이 없다** — 대장을 세우면 본문 열 하나가 「생성이 빠뜨린
        # 열」로 뜬다(거짓). `header_labels`를 table에만 채우는 것과 같은 근거다(D-29).
        ledger_path(doc_type).unlink(missing_ok=True)
        return []
    exp = a.get("expects") or {}
    fields, _blocks = load_blocks(schema)
    field_of = {}
    for f, v in (exp.get("columns") or {}).items():
        for c in (v if isinstance(v, (list, tuple)) else [v]):
            field_of.setdefault(str(c), f)
    label_of = _labels_by_col(exp, mod, samples or st.get("samples"))
    kind = {}
    for u in unmappable_of(schema, mod)[0]:
        kind[u["field"]] = ("decided", "UNMAPPABLE")
    for u in unmappable_of(schema, mod)[1]:
        kind[u["field"]] = ("open:undecided", None)
    for u in unmappable_of(schema, mod)[2]:
        kind[u["field"]] = ("open:orphan", None)
    prev = {r.get("col"): r for r in read_ledger(doc_type)}
    by_now = f"generate rev{st.get('revision', 0)}"
    rows = []
    # **프로파일 열 + 어댑터가 쓰는 열의 합집합으로 돈다**(B76 ②). 프로파일은
    # 리허설이 읽은 머리(`--rows` 안)라 어댑터가 쓰는 열이 그 밖일 수 있고, 그러면
    # **스키마에 있어도 대장에 행이 없는 필드**가 생긴다 — 그 필드는 기계 제안
    # 대조와 「이어가기」에서 조용히 빠졌다(사내 실측 열다섯째의 둘째 원인).
    # 합치기 리스트는 열마다 행 하나다(같은 `field`).
    cols = sorted(set(prof) | set(field_of),
                  key=lambda c: (len(str(c)), str(c)))
    for col in cols:
        lab, fld = label_of.get(col), field_of.get(col)
        st_role = kind.get(lab, (None, None))
        role = (fields.get(fld) or {}).get("role") if fld else st_role[1]
        status = "decided" if fld else (st_role[0] or "open:orphan")
        row = {"col": col, "label": lab, "role": role, "field": fld,
               "by": by_now, "status": status}
        old = prev.get(col)
        if old and (old.get("role"), old.get("field")) == (role, fld) and old.get("by"):
            row["by"] = old["by"]           # 판단이 그대로면 출처도 그대로
        elif old and not fld and str(old.get("by") or "").startswith(
                ("interview", "instruct")):
            # **사람이 정한 것을 산출이 지우지 않는다**(B67 ② — 이 회차의 성질).
            # 코드가 아직 그 열을 쓰지 않을 뿐이고, 그 사실은 `status`가 말한다:
            # role은 사람의 것, status는 산출의 것 — 둘이 갈린 것이 지금 상태다.
            row["role"], row["by"] = old.get("role") or role, old["by"]
        rows.append(row)
    return _save_ledger(doc_type, rows)


def mark_ledger_fails(doc_type, fails):
    """관문 FAIL이 **이름을 부른 열**에 미해결 태그를 단다 — `open:G26`.

    판정이 그 열을 말하는데 대장이 `decided`로 남아 있으면, 대장을 보고 넘어간
    사람이 막힌 자리를 못 본다.
    """
    rows = read_ledger(doc_type)
    if not rows:
        return rows
    for r in rows:
        for code, _label, detail in fails or []:
            if _col_named(detail, r):
                r["status"] = f"open:{code}"
                break
    return _save_ledger(doc_type, rows)


def apply_to_ledger(doc_type, text, by):
    """문답의 확정 사항·사람 지시를 대장에 반영한다 — **매칭은 결정적이다**.

    `apply_instruction_to_decisions`(B60 ②)와 같은 규칙이다: 문면이 어느 열을
    이름으로 부르면 그 행을, 아니면 아무 행도 건드리지 않는다. **추측으로 행을
    고치지 않는다** — 어느 열인지 못 정한 지시는 이력(`instructions`)에만 남는다.

    role 이름이 문면에 **정확히 하나** 있으면 그 행의 role로 삼는다. 둘 이상이면
    무엇을 고르는지가 판단이라 손대지 않는다.
    """
    rows = read_ledger(doc_type)
    if not rows or not (text or "").strip():
        return 0
    named = [r for r in _ROLES if re.search(rf"(?<![A-Za-z]){r}(?![A-Za-z])", text)]
    hit = 0
    for r in rows:
        if not _col_named(text, r):
            continue
        if len(named) == 1:
            r["role"] = named[0]
        r["by"], r["status"], hit = by, "decided", hit + 1
    if hit:
        _save_ledger(doc_type, rows)
    return hit


def apply_decisions_to_ledger(doc_type, decisions):
    """문답의 `decisions[]` — 항목마다 그 문면이 부른 열에 반영한다."""
    hit = 0
    for d in decisions or []:
        rd = d.get("round")
        hit += apply_to_ledger(
            doc_type, " ".join(str(d.get(k) or "") for k in ("topic", "decision")),
            f"interview r{rd}" if rd is not None else "interview")
    return hit


def ledger_block(doc_type, rows=None):
    """대장 한 줄에 한 열 — 관문 화면·`status`가 같은 블록을 쓴다 (B67 ③)."""
    rows = read_ledger(doc_type) if rows is None else rows
    if not rows:
        return ""
    out = [f"  열 판정 대장 — {len(rows)}열 "
           f"({sum(1 for r in rows if str(r.get('status')).startswith('open')) or 0}건 미해결)"
           f"  {ledger_path(doc_type).relative_to(ROOT)}"]
    for r in rows:
        out.append(f"     {r.get('col'):<3} {str(r.get('label') or '(헤더 없음)')[:16]:<18}"
                   f" role {str(r.get('role') or '—'):<11}"
                   f" 필드 {str(r.get('field') or '—')[:18]:<20}"
                   f" {r.get('status')}  ← {r.get('by')}")
    return "\n".join(out)


def gate_verdict(harness_ok, parses_ok, orphan):
    """기계 관문의 판정 — **셋이 모두 참이어야 PASS**다 (§6.6-6 · B49).

    `orphan`(스키마 대장에 없는 열)이 여기 있는 이유: 판정되지 않은 열이 있는 채로
    확정되면 **그 열은 영영 안 보인다** — 등록부에 오른 스키마가 그 열을 모르므로
    인입도, 검수도, 질의도 그 열을 지나친다. 사람이 판정할 것이 아니라 대장이
    어긋난 것이므로 질문이 아니라 관문이다.
    """
    return "PASS" if (harness_ok and parses_ok and not orphan) else "FAIL"


def _form_of_sample(sample):
    """표본 하나의 형태 판정 — 격자 포맷이 아니면 `None`.

    **판정기는 한 자리다**(`parser/form.py`) — 여기서 다시 세면 등록 화면과 인입
    기록이 다른 답을 낼 수 있고, 그때 어느 쪽이 근거인지 아무도 모른다.
    """
    if Path(sample).suffix.lower() not in reader.GRID_EXT:
        return None
    try:
        j = form.judge(reader.read(str(sample)))
    except Exception as e:                       # 판정 실패가 검수를 막지 않는다
        return {"signals": {}, "votes": {}, "verdict": None, "auto": False,
                "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}
    return {k: j[k] for k in ("signals", "votes", "verdict", "auto", "why")}


def build_view(st, results, harness_ok, harness_out, rehearsal=None):
    """뷰 데이터 산출 — **D-79 스키마가 계약**이고 여기가 산출자다.

    렌더러는 아무것도 계산하지 않으므로 **채움율·이상 신호 판정을 여기서 다 채운다.**
    """
    schema = json.loads((_at(st["schema"])).read_text(encoding="utf-8"))
    mod = _load(_at(st["adapter"]), f"reg_{st['doc_type']}")
    kind = mod.ADAPTER["payload_kind"]

    pieces = [p for r in results if r.ok
              for p in (r.envelope.get("records") or r.envelope.get("chunks"))]
    keys = sorted({k for p in pieces for k in p})
    fill = {k: round(sum(1 for p in pieces if p.get(k) not in (None, "")) / len(pieces), 3)
            for k in keys} if pieces else {}

    anomalies = []
    # **부분 리허설은 숨기지 않는다** — 이 화면이 승인 근거다. 앞 200행만 보고
    # 승인했는데 그 사실이 화면에 없으면, 승인자는 전량을 봤다고 믿는다.
    reh = {}
    for r in results:
        d = r.report.get("rehearsal") or {}
        if d.get("truncated"):
            reh = d
            anomalies.append({
                "kind": "warning",
                "message": (f"부분 리허설 — 전 {d['full_rows']:,}행 중 앞 "
                            f"{d['max_rows']:,}행만 파싱했다. 뒤 구간의 변형은 "
                            f"관찰되지 않았다"),
                "where": r.doc_id,
                "detail": {"full_rows": d["full_rows"], "rehearsed_rows": d["max_rows"],
                           "note": "전량은 `--rows all`"}})
            break

    if len(st["samples"]) < 2:                     # D-22 확장 문구 — **필수 표시**
        anomalies.append({"kind": "warning", "message": SOLO_WARNING,
                          "where": Path(st["samples"][0]).name,
                          "detail": {"declared_edges": schema.get("edges", []),
                                     "note": "위 선언 edges는 특별 확인 대상이다"}})
    if not harness_ok:
        anomalies.append({"kind": "failure", "message": "기계 관문(실행 하네스) 미통과",
                          "where": "kit/run_adapter.py",
                          "detail": {"fail_lines": [ln.strip() for ln in
                                                    harness_out.splitlines()
                                                    if "[FAIL]" in ln][:10]}})
    for r in results:
        for f in r.failures:
            anomalies.append({"kind": "failure", "message": f["reason"],
                              "where": r.doc_id, "detail": f.get("detail") or {}})
    # **셋을 갈라 낸다**(B49) — 판정된 제외는 질문이 아니고, 대장에 없는 열은 결함이다.
    excluded, undecided, orphan = unmappable_of(schema, mod)
    for u in undecided:
        anomalies.append({"kind": "question",
                          "message": f"'{u['field']}' 열은 role 5종 어디에 배정합니까 — "
                                     f"생성이 판단하지 못했다: "
                                     f"{u.get('reason') or '사유 없음'}",
                          "where": st["doc_type"]})
    for u in orphan:
        anomalies.append({"kind": "failure",
                          "message": f"'{u['field']}' 열이 스키마 대장에 없다 — "
                                     f"생성이 빠뜨렸거나 문서 양식이 바뀌었다",
                          "where": st["doc_type"]})

    # **형태 판정을 화면에 싣는다**(B58 ⑤ · 문서 1 C37) — 격자 포맷 표본만.
    # 사람에게 올라온 문서는 **이상 신호로도** 뜬다: 「이상 신호는 전량 필수
    # 표시」(§6.6-1)라 요약 표에만 두면 접힌 화면에서 사라진다.
    forms = []
    for smp in st["samples"]:
        j = _form_of_sample(smp)
        if j is None:
            continue
        forms.append({"doc": Path(smp).name, **j})
        if not j["auto"]:
            anomalies.append({
                "kind": "question",
                "message": (f"'{Path(smp).name}'의 형태 판정이 자동으로 서지 않는다 — "
                            f"table로 읽을지 prose로 읽을지 사람이 정한다: {j['why']}"),
                "where": Path(smp).name,
                "detail": {"signals": j["signals"], "votes": j["votes"],
                           "note": "신호값 다섯이 판단 재료다 — 문턱은 parser/form.py"}})
        elif j["verdict"] != kind:
            anomalies.append({
                "kind": "warning",
                "message": (f"'{Path(smp).name}'의 형태 판정({j['verdict']})이 "
                            f"이 어댑터의 payload_kind({kind})와 어긋난다 — "
                            f"지정대로 진행한다([정정] 48 ②)"),
                "where": Path(smp).name,
                "detail": {"signals": j["signals"], "votes": j["votes"]}})

    tree = [{"section": p.get("section", ""), "locator": p["source_locator"],
             "excerpt": (p.get("text") or "")[:70],
             "depth": (p.get("section") or "").count(">")} for p in pieces]
    return {
        "doc_type": st["doc_type"],
        "adapter_version": mod.ADAPTER.get("adapter_version"),
        "payload_kind": kind,
        "regenerations": st.get("instructions") or [],
        "sections": {
            "parse_result": {
                "summary": {"samples": len(st["samples"]), "pieces": len(pieces),
                            "rehearsal": reh,
                            # **분할 크기 분포**(B45) — 값은 여기서 채우고 렌더러는
                            # 그리기만 한다(§6.6-3). **`summary` 안이다**: 구획 1은
                            # `summary·anomalies·normal` 3층으로 닫혀 있어(D-79)
                            # 네 번째 키를 만들면 스키마 계약이 깨진다.
                            # 두 경로(지도·어댑터) 모두 같은 자리에 실리고, 지도
                            # 경로면 고른 레벨과 분포가 `레벨_선택`에 함께 온다.
                            "split": [{"doc_id": r.doc_id,
                                       **(r.report.get("split") or {})}
                                      for r in results if r.report.get("split")],
                            # **형태 판정**(B58 ⑤) — `split`과 같은 자리다. 구획 1은
                            # `summary·anomalies·normal` 3층으로 닫혀 있어(D-79)
                            # 네 번째 키를 만들면 스키마 계약이 깨진다.
                            "form": forms,
                            "failures": sum(1 for a in anomalies if a["kind"] == "failure"),
                            "warnings": sum(1 for a in anomalies if a["kind"] == "warning"),
                            "fill_rate": fill},
                "anomalies": anomalies,
                # **제외 목록은 정상 구획이다** — 판정이 끝난 열이라 이상 신호가
                # 아니다. 다만 화면에서 사라지면 안 된다(무엇을 뺐는지가 승인 재료다).
                "normal": {"excluded": excluded,
                           "excerpt": pieces[:EXCERPT], "all": pieces,
                           "columns": keys if kind == "table" else [],
                           "tree": tree if kind == "prose" else []},
            },
            # **②구획은 payload_kind가 가른다**(문서 6 §6.6 · B51) — table은 role
            # 배정표, prose는 추출 리허설이 **그 자리에** 선다. 화면의 목적이 같다:
            # 「무엇이 개체·값이 되는가」를 승인 **전에** 본다.
            # **구획 수는 셋 그대로다**(D-79) — 자리를 더하지 않고 갈아 끼운다.
            **({"extract_rehearsal": rehearsal or {"source": "none"}}
               if kind == "prose" else
               {"role_table": role_table(schema, mod, st,
                                         _profiles(st["doc_type"]))}),
            "adapter_summary": {
                "expects": mod.ADAPTER.get("expects") or {},
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "source": (_at(st["adapter"])).read_text(encoding="utf-8"),
            },
        },
    }


REHEARSAL_ROWS = 200        # 부분 리허설 기본값 — `--rows all`이면 전량


def _gateway_ready():
    """리허설 파싱 **전에** 게이트웨이 왕복 1회. 실패면 그 자리에서 멈춘다(2B ⑥-1).

    이것이 없으면 사내에서 무슨 일이 나나: 리허설 파싱은 좌표 미스 행마다 실호출을
    한다 — 게이트웨이가 안 닿으면 **타임아웃 60초 × 재시도 × 미스 행 수**를 말없이
    기다린다. 사용자는 «멈췄다»고 읽고, 실제로 몇 시간을 기다렸다(실측).
    **판정은 `core/llm/llm.py::probe()`가 한다** — llm-check가 쓰는 그 함수다.
    """
    if llm.use_mock():
        return True
    print("   게이트웨이 확인 중… (리허설 전 왕복 1회)")
    stages = llm.probe()
    bad = [s for s in stages if s["ok"] is False and s["fatal"]]
    if not bad:
        ok = [s for s in stages if s["ok"]]
        print(f"   게이트웨이 OK — {len(ok)}단계 통과")
        return True
    s = bad[0]
    print(f"   ✗ 게이트웨이 {s['id']} {s['label']} 실패")
    for ln in str(s["detail"]).split("\n"):
        if ln.strip():
            print(f"     {ln}")
    raise SystemExit("[뷰 확인] 게이트웨이가 준비되지 않았다 — "                          # [상태]
                     "`python run.py llm-check`로 단계별 원인을 본다. "
                     "USE_MOCK=1로 돌리면 LLM 없이 리허설만 볼 수 있다")


def _coord_misses(results, layer):
    """좌표가 **닫힌 목록과 정확히 일치하지 않는** 조각을 센다 — LLM을 부르지 않는다.

    **몇천 회 호출은 사람이 모르고 시작하면 안 된다** — 그래서 먼저 세고 물어본다.
    호출 수는 이 목록의 **길이가 아니라 종수**다(B69 ① — tagger가 표기마다 한 번
    묻는다). 목록을 그대로 돌려주는 것은 행 수와 종수를 **둘 다** 화면이 말해야
    하기 때문이다: 「3,000행이 12종이다」가 사람이 켤지 정하는 재료다.
    """
    idx = tagger.surfaces(tagger.closed_list(layer))
    miss = []
    for r in results:
        env = r.envelope or {}
        for p in (env.get("records") or env.get("chunks") or []):
            ref = p.get("process_ref")
            if ref and ref not in idx:
                miss.append(ref)
    return miss


def _ask_llm_coord(misses, assume=None):
    """LLM 좌표 보조를 켤지 **묻는다.** 기본은 끈다.

    미스를 그대로 두는 것은 오류가 아니다 — 인입에서 `orphan_anchor` 큐로 가는
    정상 경로가 있고(문서 4 §4.4), 사람이 자기 리듬으로 처리한다. 반면 켜면
    **표기 종수만큼 실호출**이다(B69 ① — 같은 표기가 여러 행에 있어도 한 번이다).
    켤지 묻는 자리이므로 **수가 맞아야 한다**: 구판은 행 수를 호출 수라고 말했고,
    그 수는 실제보다 훨씬 컸다.
    """
    n, kinds = len(misses), sorted(set(misses))
    if n == 0:
        return False
    sample = ", ".join(kinds[:5])
    print(f"   좌표 미스 {n:,}행 · 표기 {len(kinds):,}종 "
          f"(예: {sample}{' …' if len(kinds) > 5 else ''})")
    if assume is not None:
        print(f"   → LLM 보조 {'켬' if assume else '끔'} (인자로 지정됨)")
        return assume
    if llm.use_mock():
        return False
    try:
        ans = input(f"   LLM 보조를 켜면 최대 {len(kinds):,}회 호출한다(표기 종수). "
                    f"켤까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""                       # 대화형이 아니면 **끄고 진행**한다
    on = ans in ("y", "yes")
    print(f"   → LLM 보조 {'켬' if on else '끔 (미스는 인입에서 orphan_anchor로 간다)'}")
    return on


def _progress(done, total, adopted, *, label=""):
    """진행 한 줄 — **주기 갱신**. 매 번 찍으면 그것이 잡음이 된다.

    **단위는 표기다**(B69 ① — 행이 아니다): 리허설에서 도는 것은 좌표 태깅의
    표기 루프이고, 그 루프가 곧 LLM 호출이다. 부르지 않으면(정확 일치만) 진행도
    없다 — 결정적 구간은 빠르고, 조용한 것이 맞다.

    보폭은 10회 안팎으로 갱신되게 잡는다. `\r` 덮어쓰기는 터미널일 때만 —
    파이프로 받으면 매 줄이 남는다.
    """
    stride = max(1, total // 10)
    if not (done == 1 or done == total or done % stride == 0):
        return
    tty = sys.stdout.isatty()
    print(f"   좌표 태깅 {label} · 표기 {done:,}/{total:,} · 채택 {adopted:,}",
          end="\r" if (tty and done < total) else "\n", flush=True)


def _extract_rehearsal(st, results, samples, want, truncated):
    """**prose ②구획 — 층 어휘가 이 문서에 적용된 결과** (문서 6 §6.6 · B51).

    table은 role 배정표(「이 열이 attribute가 된다」)를 보고 승인한다. prose는 청크
    분할만 보고 승인해 왔다 — **층 어휘가 이 문서에 어떻게 적용되는지를 한 번도 안
    본 채** 확정되고, 그 결과를 처음 보는 시점이 운영 인입 뒤 `show extract`였다.

    **리허설은 운영과 같은 함수·같은 파일이다** — `cli.extract.run()`을 부르고 그
    체크포인트를 그대로 싣는다. 그래서 `doc_id`도 **운영의 것**(파일명 파생)을 쓴다:
    리허설 id를 따로 쓰면 확정 뒤 운영 인입이 그 체크포인트를 못 찾아 같은 문서를
    다시 뽑는다 — LLM 호출이 두 배가 되고, 두 산출이 다를 수 있다.

    **부분 리허설이면 체크포인트를 남기지 않는다** — 앞 N행만 본 추출을 운영이
    재사용하면 뒷 구간이 영영 안 뽑힌다.
    """
    from cli.extract import run as extract_run
    from cli.ingest import doc_id_of
    from core.build import extract as EX
    if not want:
        return {"source": "none", "note": "추출 리허설 없음 — 끄고 진행했다"}
    made, ids = [], []
    for r, s in zip(results, samples):
        if not r.ok:
            continue
        env = dict(r.envelope)
        env["doc_id"] = doc_id_of(s)          # **운영의 doc_id** — 재사용의 조건이다
        ids.append(env["doc_id"])
        p = _dir(st["doc_type"]) / f"_rehearsal_{env['doc_id']}.json"
        p.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
        made.append(p)
    extract_run([str(p) for p in made], layer=st["layer"])
    for p in made:
        p.unlink(missing_ok=True)
    cps = [json.loads(EX.checkpoint_path(i).read_text(encoding="utf-8"))
           for i in ids if EX.has_checkpoint(i)]
    if truncated:
        for i in ids:
            EX.invalidate(i)                  # 부분 리허설분은 운영이 재사용하면 안 된다
    if not cps:
        return {"source": "none", "note": "추출 산출이 없다 (표본 파싱 실패 또는 청크 0)"}
    # **본문은 산출자가 채운다** — 체크포인트는 후보만 담고(§4.2) 렌더러는 계산하지
    # 않는다(D-79). 청크 저장소가 그 문서의 본문·구획을 갖고 있다.
    _ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
    by_chunk, cats = [], {}
    for cp in cps:
        for c in cp.get("candidates") or []:
            for e in c.get("entities") or []:
                cats[e.get("category")] = cats.get(e.get("category"), 0) + 1
            src = _ch.get(c.get("chunk_id")) or {}
            by_chunk.append({"chunk_id": c.get("chunk_id"),
                             "section": src.get("section") or "",
                             "excerpt": (src.get("text") or "")[:60],
                             "entities": c.get("entities") or [],
                             "relations": c.get("relations") or [],
                             "attach": c.get("attach") or []})
    tot = {"chunks": len(by_chunk),
           "entities": sum(len(c["entities"]) for c in by_chunk),
           "relations": sum(len(c["relations"]) for c in by_chunk),
           "attach": sum(1 for c in by_chunk for a in c["attach"]
                         if a.get("attach_to")),
           "unresolved": sum(1 for c in by_chunk for a in c["attach"]
                             if not a.get("attach_to"))}
    return {"source": "mock" if llm.use_mock() else "live",
            "prompt_version": cps[0].get("prompt_version"),
            "config_version": cps[0].get("config_version"),
            "kept": not truncated,
            "note": ("부분 리허설이라 체크포인트를 남기지 않았다 — 운영이 다시 뽑는다"
                     if truncated else None),
            "totals": tot, "by_chunk": by_chunk, "category_counts": cats}


def cmd_review(doc_type, instruct=None, rows=REHEARSAL_ROWS, llm_coord=None,
               extract=None):
    """② 검수 — 기계 관문 → 뷰 데이터 → HTML. 지시가 오면 **재생성 루프**를 돈다.

    **상한은 없다**(§7 규약 2 · A8 — 근거 없는 수치 금지). 매회 지시가 이력에 남고
    중단은 사람 판단이다. 화면에는 강제 없는 안내만 둔다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[뷰 확인] '{doc_type}'의 생성이 먼저다 — "               # [상태]
                         f"근거 review/{doc_type}/state.json 없음\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")

    from cli.ingest import doc_id_of            # 리허설도 운영 doc_id다 (B51-2 · B55 ⑤)

    if instruct and st.get("use_basic"):
        # **고정 어댑터는 재생성하지 않는다**(B65 ④) — 여기서 막지 않으면 `draft`가
        # LLM으로 가고, 사람은 「지시를 줬다」고 믿는데 산출이 통째로 바뀐다.
        refuse_regenerate(doc_type, st, "뷰 확인")
    if instruct:                                   # 재생성 루프 1회
        st["revision"] += 1
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": instruct, "at": store._now(),
             "by": "사람(검수 지시)"})
        # **지시는 확정 사항을 갱신한다**(B60 ②) — draft가 패키지를 읽기 **전에**.
        # 지시와 결정이 따로 살면 이 재생성이 옛 결정을 다시 쓴다.
        _hit = apply_instruction_to_decisions(doc_type, instruct, st["revision"])
        if _hit is not None:
            print(f"   확정 사항 갱신 — {'항목 ' + str(_hit) + '건 교체' if _hit else '새 항목 추가'}"
                  f" (사람 지시 rev {st['revision']})")
        # **지시가 열을 이름으로 부르면 대장도 갱신한다**(B67 ②) — 못 부르면
        # 건드리지 않고 이력에만 남는다(추측으로 행을 고치지 않는다).
        _lh = apply_to_ledger(doc_type, instruct, f"instruct rev {st['revision']}")
        if _lh:
            print(f"   열 판정 대장 갱신 — {_lh}열 (instruct rev {st['revision']})")
        ad, sc = draft(doc_type, st["revision"], instruction=instruct,
                       history=st.get("instructions"))
        if ad is None:
            print(f"   ⚠ 재생성 대안본 부재 — 초안을 유지한다 "
                  f"(USE_MOCK: fixture '{doc_type}_rev{st['revision']}' 없음)")
        else:
            st["adapter"], st["schema"] = (str(_rel(ad)), str(_rel(sc)))
            print(f"   재생성 {st['revision']}회째 → {_rel(ad)}")
            # **지시는 사람 것이지만 산출은 LLM 것이다**([정정] 40 · M9). 관문을
            # 안 지난 산출이 확정되면 「통과분만 확정」(B50)이 검수 지시 한 번으로
            # 뚫린다 — 규약 10을 어긴 어댑터가 `--instruct` 한 줄로 등록부에 든다.
            # **생성 단계와 같은 함수·같은 해소 절차**(자동 1회 → 문답 → [y/N])다.
            _pkg_path = REVIEW / doc_type / "input_package.json"
            _pkg = (json.loads(_pkg_path.read_text(encoding="utf-8"))
                    if _pkg_path.exists() else None)
            st["machine_gate"] = machine_gate(doc_type, st, st["samples"], _pkg)
            _save_state(doc_type, st)
            if st["machine_gate"] != "PASS":
                print(f"   기계 관문 FAIL — **뷰를 만들지 않았다.** 산출은 "
                      f"{(REVIEW / doc_type).relative_to(ROOT)}에 남겼다\n")
                gate_block(doc_type, st)
                return 1

    samples = st["samples"]
    print(f"  {llm.mode_line()}")          # B42 ⑤
    if st.get("machine_gate") != "PASS":
        # **막는 이유와 다음 줄을 여기서도 준다**(B59 ①) — 세 명령이 같은 블록이다.
        # 뷰는 그래도 만든다: 이상 신호에 그 FAIL이 실려 있고, 사람이 **무엇이
        # 뽑혔는지**를 보고 지시를 쓸 재료가 그 화면이다. 확정은 관문이 막는다.
        gate_block(doc_type, st)
        print("")
    print(f"■ ② 뷰 확인 — {doc_type} (표본 {len(samples)}부)")
    # **하네스는 여기서 돌지 않는다**(M9 개정 · B50) — 생성이 이미 돌려 통과분만
    # 넘겼다. 검수는 **내용 판단**이다: role 배정·제외 열·분할을 사람이 본다.
    ok = st.get("machine_gate") == "PASS"
    out = st.get("harness_out", "")
    print(f"   기계 관문: 생성 단계에서 {'PASS' if ok else 'FAIL'} "
          f"(하네스는 생성이 돌린다 — 검수는 내용을 본다)")

    mod = _load(_at(st["adapter"]), f"reg_{doc_type}")

    _gateway_ready()          # ⑥-1 연결 확인이 먼저다 — 60초×N을 기다리게 하지 않는다

    # ⑥-3 **좌표 미스를 먼저 세고, LLM 보조는 물어보고 켠다.**
    #     1차는 무LLM(정확 일치 대조만) — 빠르고, 그 결과가 미스 계수의 재료다.
    # 이미지 요약(LLM 지점 ④)의 실호출 경로는 **주입**한다 — 파서는 core를
    # import하지 않는다(P1). 등록 리허설도 운영 파싱과 같은 배선을 탄다.
    def _run(pick):
        out = []
        for i, s in enumerate(samples, 1):
            lbl = f"{i}/{len(samples)} ({Path(s).name})"
            # **주입 조립은 한 자리다**(B48) — 좌표 보조만 사람이 끌 수 있으므로
            # 그 하나를 덮어쓴다. 나머지 둘은 진입점이 정한 그대로 내려간다.
            # **리허설 파싱도 운영의 doc_id를 쓴다**(문서 6 §6.6 B51-2 · B55 ⑤).
            # 구판은 `{DOC_TYPE}{i:02d}`라, 구조 지도·이미지 요약 보존분이 `CP01`
            # 대신 그 이름으로 남아 **운영 인입이 못 찾았다** — 체크포인트 키가
            # 같아야 재사용이 성립한다. `_extract_rehearsal`만 고쳐져 있었다.
            out.append(pipeline.parse(
                mod, doc_id_of(s), s, layer=st["layer"],
                **{**injections(), "pick_coord": pick},
                max_rows=rows,
                progress=lambda a, b, c, _l=lbl: _progress(a, b, c, label=_l)))
        return out

    results = _run(None)
    misses = _coord_misses(results, st["layer"])
    if _ask_llm_coord(misses, llm_coord):
        results = _run(llm.coord_picker())     # 사람이 켰을 때만 실호출이 돈다

    for r in results:
        reh = r.report.get("rehearsal") or {}
        part = (f" · **부분 리허설** 전 {reh['full_rows']:,}행 중 앞 {reh['max_rows']:,}행"
                if reh.get("truncated") else "")
        print(f"   파싱 {r.doc_id}: {'OK' if r.ok else 'FAIL'} · "
              f"조각 {r.report.get('pieces', 0)}{part}")

    # **prose ②구획 — 추출 리허설**(B51). 비용 관문은 좌표 보조와 동형이다.
    kind = mod.ADAPTER.get("payload_kind")
    _trunc = any((r.report.get("rehearsal") or {}).get("truncated") for r in results)
    rehearsal = None
    if kind == "prose" and st.get("machine_gate") == "PASS":
        n = sum(r.report.get("pieces", 0) for r in results if r.ok)
        want = extract
        if want is None:
            print(f"   추출 리허설 {n:,}청크 → LLM {n:,}회.")
            try:
                want = input("   켤까? [Y/n] ").strip().lower() not in ("n", "no")
            except (EOFError, KeyboardInterrupt):
                # **비대화형이면 끄고 그 사실을 뷰에 남긴다** — 조용히 도는 구간을
                # 두지 않는다: 승인자는 「추출을 보고 승인했다」고 믿으면 안 된다.
                want = False
                print("   (비대화형 — 끄고 진행한다. 뷰에 「추출 리허설 없음」)")
        print(f"   → 추출 리허설 {'켬' if want else '끔'}")
        rehearsal = _extract_rehearsal(st, results, samples, want, _trunc)
        if rehearsal.get("totals"):
            t = rehearsal["totals"]
            print(f"   추출 리허설({rehearsal['source']}) — 청크 {t['chunks']} · "
                  f"개체 {t['entities']} · 관계 {t['relations']} · "
                  f"부착 {t['attach']} · 미해소 {t['unresolved']}")
            if rehearsal.get("note"):
                print(f"     {rehearsal['note']}")

    view = build_view(st, results, ok, out, rehearsal)
    d = _dir(doc_type)
    (d / "view.json").write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    (d / "view.html").write_text(render(view), encoding="utf-8")   # kit 렌더러 호출
    # **판정되지 않은 열이 있는 채로 확정되면 그 열은 영영 안 보인다**(B49) —
    # orphan은 기계 관문을 막는다. 「사람이 판정할 것」이 아니라 「대장이 어긋났다」다.
    # **생성이 세운 값과 파싱 결과의 AND**(B50 ⑧) — 리허설이 깨지면 여전히 FAIL이다.
    _orphan = unmappable_of(
        json.loads((_at(st["schema"])).read_text(encoding="utf-8")), mod)[2]
    if _orphan:
        print(f"   스키마 대장에 없는 열 {len(_orphan)}건 — "
              f"{[u['field'] for u in _orphan]} (기계 관문 FAIL)")
    st["machine_gate"] = gate_verdict(ok, all(r.ok for r in results), _orphan)
    _save_state(doc_type, st)

    an = view["sections"]["parse_result"]["anomalies"]
    print(f"   뷰 데이터 → {(d / 'view.json').relative_to(ROOT)}  "
          f"(이상 신호 {len(an)}건 — 전량 표시)")
    print(f"   HTML     → {(d / 'view.html').relative_to(ROOT)}  (kit 렌더러)")
    for a in an:
        print(f"     [{a['kind']}] {a['message'][:70]}")
    if st.get("instructions"):
        print(f"   재생성 {len(st['instructions'])}회 — 상한 없음(중단은 사람 판단)")
    return 0 if st["machine_gate"] == "PASS" else 1


def _promote_paths(doc_type):
    """정본 자리의 경로 — **등재는 이 경로로 하고 복사는 그 뒤에 한다**."""
    return (f"adapters/{doc_type}.py", f"schemas/{doc_type}.json")


def _promote(doc_type, st):
    """확정 산출을 **검수 자리에서 정본 자리로 옮긴다** (문서 6 §6.5).

    어댑터는 `adapters/{doc_type}.py`, 매칭 스키마는 `schemas/{doc_type}.json`이고
    등록부 등재가 그 활성화다. `review/{doc_type}/`에 남는 것은 입력 패키지·뷰
    데이터·정적 HTML·**승인 기록**이지 정본 실물이 아니다.

    이행이 없으면 확정본이 검수 산출 디렉터리에 남는데, **그 디렉터리는 버전 추적
    대상이 아니라** 재생성 시 확정된 어댑터가 함께 사라진다.

    **원본은 지우지 않는다** — fixture(외부 LLM 실산출 스냅샷)가 원본인 경우가 있고
    그것은 손대지 않는 자리다(문서 7 §7.5-4). 복사로 이행한다.
    """
    a_rel, s_rel = _promote_paths(doc_type)
    src_a, src_s = _at(st["adapter"]), _at(st["schema"])
    dst_a, dst_s = paths.registry() / a_rel, paths.registry() / s_rel
    paths.ensure(dst_a)
    paths.ensure(dst_s)
    if src_a.resolve() != dst_a.resolve():
        dst_a.write_bytes(src_a.read_bytes())
    if src_s.resolve() != dst_s.resolve():
        dst_s.write_bytes(src_s.read_bytes())
    return (a_rel, s_rel)


def cmd_status(doc_type):
    """관문 상태 한 화면 (B59 ①) — **화면이 흘러간 뒤 다시 볼 자리.**

    찍는 것은 `gate_block`과 같은 블록이다. 통과했으면 다음 두 줄을 말한다 —
    「무엇을 치면 되는지」가 통과 쪽에서도 화면에 있어야 대칭이 선다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[상태] '{doc_type}' 생성이 먼저다 — "                  # [상태]
                         f"근거 review/{doc_type}/state.json 없음\n"
                         f"  ▶ 다음 줄:\n"
                         f"     python -m cli.register generate {doc_type} "
                         f"<층> <표본...>")
    if regate(doc_type, st) != "PASS":          # 저장값이 아니라 지금 판정이다
        gate_block(doc_type, st)
        return 1
    print(f"■ 기계 관문 PASS — {doc_type}")
    _vw = _dir(doc_type) / "view.html"
    print("")
    print("  ▶ 다음 줄:")
    if _vw.exists():
        print(f"     (뷰 확인) {_vw.relative_to(ROOT)}")
    print(f"     python -m cli.register confirm {doc_type} --by <승인자>")
    print(f"     python -m cli.register review {doc_type} --instruct \"…\""
          f"   (고칠 것이 있을 때만)")
    return 0


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
    if regate(doc_type, st) != "PASS":
        # **막되 막다른 길로 두지 않는다**(B59 ①) — 이유와 칠 수 있는 다음 줄을 준다.
        gate_block(doc_type, st)
        return 1
    if not approved_by:
        raise SystemExit("[확정] 승인자 미지정 — 무수정 자동 통과는 금지다 (틀 §2)")          # [사용법]

    mod = _load(_at(st["adapter"]), f"reg_{doc_type}")
    at = store._now()
    # **등재가 먼저, 승격이 나중이다.** 반대로 하면 등재가 거부됐을 때 승격된
    # 파일만 남아 조회에는 잡히고 등록부에는 없는 반쪽 상태가 되고, 그 이름의
    # 재등록이 「내장 중복」으로 영영 막힌다(실측).
    adapter_path, schema_path = _promote_paths(doc_type)
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
    _promote(doc_type, st)              # 등재가 성립한 뒤에만 실물을 옮긴다
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


def main(argv):
    """진입점 — **미포착 예외는 문면으로 죽는다** (B76 ③).

    관문 FAIL·상태 거부(`SystemExit`)는 **판정**이라 그대로 지난다. 여기서 잡는
    것은 파이썬 예외뿐이고, 화면에는 한 줄(`[결함] 파일:줄 · 예외: 메시지 · 단계 …`)
    · `defects.log`에는 traceback 전문이다. 사내 실측 열다섯째의 화면은 traceback
    이었고 사람이 프레임을 읽어야 했다 — 그것이 M9 위반이다.
    """
    try:
        return _run(argv)
    except SystemExit:
        raise                       # 관문 FAIL·상태 거부는 판정이다 — 그대로
    except Exception as e:
        print(log.defect(e, stage=f"단계 {argv[0] if argv else '?'}",
                         extra=(f"doc_type {argv[1]}" if len(argv) > 1 else "")))
        return 1                    # 상태 거부와 같은 종료 코드 (B61 계약)


def _run(argv):
    if not argv:
        raise SystemExit(__doc__)                                         # [사용법]
    cmd, rest = argv[0], list(argv[1:])
    if cmd in GATED:
        rest = require_live_or_allow(rest, command=f"register {cmd}")

    def opt(name, default=None):
        if name in rest:
            i = rest.index(name)
            v = rest[i + 1] if i + 1 < len(rest) else default
            del rest[i:i + 2]
            return v
        return default

    if cmd == "roles":
        # **⓪ 등록 세션 진입 전** — 실행만 하고 등록부는 건드리지 않는다.
        return cmd_roles(rest)
    if cmd == "generate":
        hint = opt("--hint", "")
        interview = "--interview" in rest
        if interview:
            rest.remove("--interview")
        no_few = "--no-fewshot" in rest
        if no_few:
            rest.remove("--no-fewshot")
        resume = "--resume" in rest
        if resume:
            rest.remove("--resume")
        no_basic = "--no-basic" in rest
        if no_basic:
            rest.remove("--no-basic")
        use_basic = "--use-basic" in rest
        if use_basic:
            rest.remove("--use-basic")
        # **사람의 답을 버리려면 적어야 한다**(B55 ②-4) — 기본은 이어가기다.
        drop_iv = "--drop-interview" in rest
        if drop_iv:
            rest.remove("--drop-interview")
        # **재등록 두 경로**(H27 · B58 ①)
        revise = "--revise" in rest
        if revise:
            rest.remove("--revise")
        as_name = opt("--as", None)
        # **위치 인자가 모자라면 죽지 말고 사용법을 낸다.** `--resume`은 doc_type
        # 하나만 필요하다 — 층·표본은 패키지에 이미 있고 resume 갈래가 그것을
        # 읽는다(실사고: `generate <doc_type> --resume`이 IndexError로 죽었다).
        if not rest or (not resume and len(rest) < 2):
            raise SystemExit(__doc__)                                     # [사용법]
        return cmd_generate(rest[0], rest[1] if len(rest) > 1 else None, rest[2:],
                            hint, interview=interview,
                            no_fewshot=no_few, resume=resume, use_basic=use_basic,
                            drop_interview=drop_iv, revise=revise, as_name=as_name,
                            no_basic=no_basic)
    if cmd == "review":
        # **prose의 리허설 기본은 전량이다**(B51) — 부분 리허설의 근거(좌표 미스
        # 비용)는 table의 것이고 prose엔 해당 없다. table 기본 200행은 그대로다.
        _st0 = _state(rest[0]) if rest else None
        _prose = bool(_st0) and str(_st0.get("schema", "")).endswith(".json") and (
            (json.loads((_at(_st0["schema"])).read_text(encoding="utf-8"))
             .get("payload_kind") == "prose") if (_at(_st0["schema"])).exists() else False)
        raw_rows = opt("--rows", "all" if _prose else str(REHEARSAL_ROWS))
        if str(raw_rows).lower() == "all":
            rows = None                      # 전량 — 자르지 않는다
        else:
            try:
                rows = int(raw_rows)
            except (TypeError, ValueError):
                raise SystemExit(f"[뷰 확인] --rows 는 정수 또는 all 이다: {raw_rows!r}")  # [사용법]
        # 좌표 LLM 보조는 **기본이 「묻는다」**이고, 스크립트용으로만 미리 정한다.
        coord = True if "--llm-coord" in rest else (
            False if "--no-llm-coord" in rest else None)
        for f in ("--llm-coord", "--no-llm-coord"):
            if f in rest:
                rest.remove(f)
        # 추출 리허설도 **기본은 「묻는다」**이고 스크립트용으로만 미리 정한다.
        ex = True if "--extract" in rest else (
            False if "--no-extract" in rest else None)
        for f in ("--extract", "--no-extract"):
            if f in rest:
                rest.remove(f)
        return cmd_review(rest[0], opt("--instruct"), rows=rows, llm_coord=coord,
                          extract=ex)
    if cmd == "confirm":
        return cmd_confirm(rest[0], opt("--by"))
    if cmd == "status":
        return cmd_status(rest[0])
    if cmd == "list":
        return cmd_list()
    raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")                      # [사용법]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
