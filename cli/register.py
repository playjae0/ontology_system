# -*- coding: utf-8 -*-
"""n6 구축 모드 등록 파이프라인 — doc_type 등록의 3단 (파서_명세 §6·§7 · 틀 §2).

    ① 생성  입력 패키지(사람 4 + 시스템 5) → reader head 공급 → 어댑터·스키마 초안
    ② 검수  실행 하네스(기계 관문) → 뷰 데이터 JSON → 렌더러로 HTML → 재생성 루프
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

from core import fixtures, llm, registry, store
from parser import pipeline, preflight, profile, reader, tagger
from parser.normalizer import _col
from parser.adapters import basic_ppt, basic_prose_xlsx
from kit.render_review import render
from kit.run_adapter import load_blocks
from router import discover

# **분할 뒤 재수출** — 등록 흐름은 여기 남고, 조립·문답은 제 모듈로 갔다.
# 이름을 그대로 내보내는 이유: 테스트와 외부가 `cli.register.<이름>`으로 부른다.
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, _newest_template, _render_template, _vocab_excerpt, _sent_size)
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.parse import injections               # 주입 조립은 한 자리다(B48)
from cli.interview import (  # noqa: F401
    INTERVIEW_SCHEMA, INTERVIEW_STOP, _interview_round, _prof_hint, _interview)

REVIEW = ROOT / "review"
KIT = ROOT / "kit"
FIXTURES = fixtures.ROOT_DIR / "fixtures"   # 소재는 core/fixtures.py가 소유

# D-22 확장 문구 — 표본 1부 등록의 경고. **문면이 규격이다.**
SOLO_WARNING = ("표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음**. "
                "1부 등록의 선언 edges는 특별 확인 대상이다")
EXCERPT = 3                                   # 정상 조각 발췌 건수(전량은 접힘에 실린다)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dir(doc_type):
    d = REVIEW / doc_type
    d.mkdir(parents=True, exist_ok=True)
    return d


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

        python run.py register roles <문서.xlsx> [헤더행]

    **실행만 하고 등록부는 건드리지 않는다.** 문서의 열 이름 전량에 role 5종 +
    UNMAPPABLE 배정을 시도해 보고, **어디서 막히는지**를 먼저 본다. 이것 없이
    `register generate`로 가면 생성 세션이 무엇을 물어볼지 모른 채 시작한다.

    **추측을 답으로 내놓지 않는다** — 여기서 나오는 것은 **제안**이고, 확정은
    검수 뷰의 6지선다에서 사람이 한다(문서 6 §6.5). 그래서 확신이 없는 열은
    `UNMAPPABLE`로 남기고 **질문 형태로** 표시한다.
    """
    if not args:
        raise SystemExit("문서를 달라: run.py register roles <문서.xlsx> [헤더행]")
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

    blocks = json.loads((ROOT / "schemas" / "blocks.json").read_text(encoding="utf-8"))
    block_fields = {f for b, spec in blocks.items() if not b.startswith("_")
                    for f in spec}

    print(f"■ role 배정 실험 — {path} (헤더 {hrow}행 · {len(labels)}열)")
    print("  **실행만 한다 — 등록부를 건드리지 않는다.** 확정은 검수 뷰의 6지선다다.\n")
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
                _newest_template().read_text(encoding="utf-8"),
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


def _rel(p):
    """레포 기준 상대 경로 — **밖이면 절대 경로 그대로**다.

    `ONTO_FIXTURES`는 「사내에서 mock을 통째로 들어내고 실자산으로 갈아 끼울 때의
    손잡이」(core/fixtures.py)라 레포 밖을 가리킬 수 있다. 그때 `relative_to`는
    `ValueError`로 죽는다 — 손잡이를 실제로 당기면 생성이 크래시했다(실측).
    `ROOT / <절대 경로>`는 절대 경로를 그대로 돌려주므로 상태에 실어도 안전하다.
    """
    try:
        return p.relative_to(ROOT)
    except ValueError:
        return p


def _note_error(doc_type, e):
    """실패하면 **원인이 적힌 유일한 자리**를 남긴다 — `review/{}/last_error.json`.

    게이트웨이의 400 본문은 화면을 스쳐 지나가고 로그는 다음 실행에 묻힌다.
    검수 디렉터리에 남겨야 사람이 그 문서를 다시 볼 때 함께 본다.
    **인증 헤더·키는 남기지 않는다** — `core/llm.py`가 애초에 담지 않는다.
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
    `data/` 저장 레코드는 이 함수를 타지 않는다(`core/store.py`의 소관이고,
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
        raise SystemExit(f"[생성] 입력 패키지가 없다: {pkg} — 생성 전에 서야 한다")
    raw_pkg = pkg.read_text(encoding="utf-8")
    # **지시는 지시문의 자리에 «치환»된다** — user는 패키지 JSON 그대로여야 「입력의
    # 정본은 패키지」가 유지되고(아래 주석), 지시는 그 입력을 어떻게 다시 다루라는
    # 말이라 지시문의 몫이다. 렌더 뒤에 이어 붙이면 그 문장이 다시 템플릿 밖에
    # 사는 것이고, 그것이 이 회차가 고친 결함이다.
    system = _render_template(_newest_template().read_text(encoding="utf-8"),
                              json.loads(raw_pkg),
                              regeneration=instruction_items(instruction, history))
    _dump_prompt(doc_type, system)          # ONTO_DUMP_PROMPT=1일 때만
    # user 메시지는 **원본 패키지 JSON 그대로** 보낸다 — 치환은 지시문의 일이고
    # 입력의 정본은 패키지다. 둘을 섞으면 어느 쪽이 정본인지 갈린다.
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": raw_pkg}]
    _sent_size(msgs, f"생성 초안 {doc_type}")
    try:
        out = llm.chat(msgs, json_schema=GENERATE_SCHEMA, point="generate")
    except Exception as e:
        _note_error(doc_type, e)
        raise
    d = REVIEW / doc_type
    d.mkdir(parents=True, exist_ok=True)
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
    frames, picks, oor, chunks = 0, [], 0, 0
    for s in samples:
        raw = reader.read(str(s))
        rep = basic_prose_xlsx.level_report(raw)
        frames += len(rep)
        picks += [r["분할_레벨"] for r in rep]
        oor += sum(1 for r in rep if r["분할_레벨_구간밖"])
        chunks += len(basic_prose_xlsx.extract(raw))
    if not frames or chunks <= len(samples):
        return None                     # 시트당 1청크 = 분할이 서지 않았다
    return {"adapter": "parser/adapters/basic_prose_xlsx.py",
            "reason": ("스프레드시트 산문 — 계층 신호(번호·굵게·들여쓰기·가로병합)로 "
                       "레벨이 정해진다. 생성 세션이 필요 없다"),
            "frames": frames, "chunks": chunks,
            "levels": sorted({p for p in picks if p}),
            "out_of_range_frames": oor,
            "note": (f"프레임 {frames}개 · 청크 {chunks}건 · 고른 레벨 {sorted({p for p in picks if p})}"
                     + (f" · **목표 구간 밖 {oor}프레임** — 최근접 레벨로 떨어졌다"
                        f"(검수 화면과 큐에 남는다)" if oor else ""))}


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
# `human.hint.interview` 안에서 산다. 묶음 하나 = `{samples, at, stale?, rounds[]}`.

def _keep_prior(prior):
    """**멈추고 묻는다**(B55 ②-4) — 사람의 답은 다시 만들 수 없는 재료다.

    기본은 이어가기다: 비대화형에서 조용히 버리면 그것이 바로 이 회차가 고치는
    병이다(구판은 경고 한 줄 없이 덮어썼다). 버리려면 사람이 답하거나
    `--drop-interview`를 적어야 한다.
    """
    n = sum(len(b.get("rounds") or []) for b in prior)
    print(f"\n   이 등록에 **이전 문답 {n}라운드**가 남아 있다 "
          f"(묶음 {len(prior)}개).")
    for b in prior[-3:]:
        print(f"     · {b.get('at', '?')[:19]} · 표본 "
              f"{[Path(x).name for x in (b.get('samples') or [])]} · "
              f"{len(b.get('rounds') or [])}라운드")
    try:
        ans = input("   이어갈까? [Y/n]  (n이면 버린다 · 사람의 답은 다시 못 만든다) "
                    ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("   (비대화형 — **이어간다.** 버리려면 --drop-interview)")
        return True
    return ans not in ("n", "no")


def _new_batch(samples):
    return {"samples": sorted(samples), "at": store._now(), "rounds": []}


def _hint_batches(hint):
    """`hint`가 어떤 꼴이든 문답 묶음 리스트를 돌려준다.

    옛 꼴 셋을 다 받는다 — ①문자열 힌트 ②`{text, interview: [라운드…]}`(B55 이전)
    ③`{text, interview: [묶음…]}`(지금). ②는 묶음 하나로 감싼다: **옛 패키지를
    읽지 못해 이전 문답을 잃는 것이 바로 이 회차가 고치는 병이다.**
    """
    if not isinstance(hint, dict):
        return []
    iv = hint.get("interview") or []
    if iv and isinstance(iv[0], dict) and "rounds" not in iv[0]:
        return [{"samples": [], "at": None, "rounds": iv}]      # 옛 꼴 → 묶음 1개
    return [b for b in iv if isinstance(b, dict) and "rounds" in b]


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
                 drop_interview=False, revise=False, as_name=None):
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
        if not registry.lookup(doc_type):
            raise SystemExit(f"[생성] --revise는 **등록분**에만 쓴다 — "
                             f"'{doc_type}'은 등록돼 있지 않다 (그냥 generate로 간다)")
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
            raise SystemExit(f"[생성] --resume 인데 입력 패키지가 없다: {pkg_path}\n"
                             f"        먼저 --resume 없이 한 번 돌린다")
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        print(f"  {llm.mode_line()}")
        print(f"■ ① 생성 (이어하기) — {doc_type} · 기존 패키지 재사용")
        if layer or samples:
            # **무시하되 말한다** — 사람이 준 값이 안 쓰였다는 사실을 침묵으로
            # 넘기면, 층을 바꾸려고 다시 준 사람이 바뀐 줄 안다.
            print(f"   [생성] --resume — 층·표본 인자는 무시한다 (패키지의 값을 쓴다: "
                  f"layer={pkg['human']['layer']}, "
                  f"표본 {len(pkg['human']['samples'])}건)")
        _r = (pkg.get("human") or {}).get("hint")
        if isinstance(_r, dict) and _r.get("interview"):
            print(f"   문답 {len(_r['interview'])}라운드가 패키지에 남아 있다")
        ad, sc = draft(doc_type)
        if ad is None:
            raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "
                             f"'{doc_type}' 부재 (D-10)")
        print(f"   초안 수령: {_rel(ad)} · {_rel(sc)}")
        st = _state(doc_type) or {}
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
        raise SystemExit(
            f"[생성] '{doc_type}'은 이미 등록돼 있다. 두 길 중 하나를 고른다:\n"
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
        raise SystemExit(
            f"[생성] 표본 자리에 파일이 아닌 값이 있다: {bad}\n"
            f"        힌트라면 --hint \"…\" 로 준다 (따옴표로 묶는다):\n"
            f"        python -m cli.register generate {doc_type} {layer} "
            f"<표본.xlsx> --hint \"{' '.join(str(b) for b in bad)[:60]}\"")
    layers = discover()
    if layer not in layers:                       # ⑵-③ 층 선행 완결
        raise SystemExit(f"[생성] 존재하지 않는 층 '{layer}' — 층 등록(R1)은 국면 2다. "
                         f"현재 층: {layers}")
    if use_basic:
        # **제안이 서지 않는 표본에는 거부한다** — 조용히 LLM 생성으로 떨어지면 사람은
        # «기본 어댑터로 등록됐다»고 믿는다. 거부는 사유를 들고 멈춘다.
        proposal = basic_adapter_proposal(samples)
        if proposal is None:
            raise SystemExit(
                f"[생성] --use-basic 거부 — 기본 어댑터 제안이 서지 않는 표본이다: "
                f"분할 자명 계열(pptx)이 아니다 {[Path(s).name for s in samples]}. "
                f"LLM 생성 경로(--use-basic 없이)로 등록한다 (§6.4-5)")
        return _use_basic(doc_type, layer, samples, hint, proposal, revise)

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
            "blocks": json.loads((ROOT / "schemas" / "blocks.json")
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
    if prior and drop_interview:
        print(f"   ⚠ 이전 문답 {sum(len(b['rounds']) for b in prior)}라운드를 **버린다** "
              f"(--drop-interview)")
    elif prior:
        if _keep_prior(prior):
            kept = _age_rounds(prior, [str(x) for x in samples])
            pkg["human"]["hint"] = _merge_hint(pkg["human"]["hint"], kept)
        else:
            print("   → 이전 문답을 버리고 새로 시작한다")
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
            _batch["rounds"] = rounds
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
        _persist(rounds)
        _old = sum(len(b["rounds"]) for b in _hint_batches(pkg["human"]["hint"])
                   if b is not _batch)
        print(f"   문답 {len(rounds)}라운드 → human.hint 에 전문 기록"
              + (f" (이전 {_old}라운드 유지)" if _old else ""))
    proposal = basic_adapter_proposal(samples)
    if proposal:
        print(f"   ▶ 기본 어댑터 적용 제안 — {proposal['reason']}")
        print(f"     {proposal['note']}")
    ad, sc = draft(doc_type)
    if ad is None:
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "
                         f"'{doc_type}' 부재 (D-10). 실물 경로는 생성 LLM 훅이다")
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
        f"extract = {mod}.extract\n", encoding="utf-8")
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
    print(f"   다음: python run.py register review {doc_type}  (검수·승인 1회는 그대로다 — M4)")
    st = {"doc_type": doc_type, "layer": layer,
          "samples": [str(s) for s in samples],
          "hint": pkg["human"]["hint"],
          "adapter": str(_rel(ad)),
          "schema": str(_rel(sc)),
          "revision": 0, "instructions": [],
          "revise_of": doc_type if revise else None,   # **새 판인가**(H27)
          "basic_adapter_proposal": proposal, "use_basic": True}
    _save_state(doc_type, st)
    return _finish_generate(doc_type, st, samples, pkg)


# ================================================================ ② 검수
def harness(adapter, schema, samples):
    """기계 관문 — **kit/run_adapter.py를 그대로 부른다**(재작성 아님)."""
    r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                        str(adapter), str(schema)] + [str(s) for s in samples],
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


def _orphan_of(st):
    """스키마 대장에 없는 열 — 관문의 셋째 조건(B49). 어댑터를 못 읽으면 빈 목록이다
    (그 경우 하네스가 이미 FAIL이므로 여기서 다시 말할 것이 없다)."""
    try:
        mod = _load(ROOT / st["adapter"], f"gate_{st['doc_type']}")
        schema = json.loads((ROOT / st["schema"]).read_text(encoding="utf-8"))
        return unmappable_of(schema, mod)[2]
    except Exception:
        return []


def _ask_more(n):
    """1회 재생성 뒤에도 실패하면 **묻고 진행한다** — 비용 동의(좌표 보조와 동형)."""
    try:
        ans = input(f"   1회 재생성 후에도 FAIL {n}건이다. 더 돌릴까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("   (비대화형 — 끄고 실패로 끝낸다)")
        ans = ""
    return ans in ("y", "yes")


def _failure_persist(doc_type, pkg, samples, ask):
    """실패 뒤 문답의 라운드 저장기 — 패키지의 `human.hint`에 **이어 붙인다.**

    묶음에 `context`를 달아 생성 전 문답과 구분한다: 같은 그릇이지만 물은 이유가
    다르고, 재현할 때 「무엇을 보고 답했나」가 달라진다.
    """
    d = _dir(doc_type)
    path = d / "input_package.json"
    batch = _new_batch([str(x) for x in (samples or [])])
    batch["context"] = "기계 관문 실패"

    def _persist(rounds):
        try:
            obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() \
                else {"human": {"hint": {}}}
        except (OSError, json.JSONDecodeError):
            return                              # 패키지를 못 읽으면 조용히 지나간다
        batch["rounds"] = rounds
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
        print(f"   기계 관문 PASS — 검수로 넘어간다: "
              f"python run.py register review {doc_type}")
        return 0
    print(f"   기계 관문 FAIL — **검수로 넘어가지 않았다.** 산출은 "
          f"{(REVIEW / doc_type).relative_to(ROOT)}에 남겼다")
    print(f"   같은 표본으로 다시 시도: python run.py register generate "
          f"{doc_type} --resume")
    return 1


def machine_gate(doc_type, st, samples, pkg=None):
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
    tries = 0
    while True:
        ok, out = harness(ROOT / st["adapter"], ROOT / st["schema"], samples)
        print(f"   기계 관문(하네스): {'PASS' if ok else 'FAIL'} — "
              f"{out.count('[PASS]')} PASS / {out.count('[FAIL]')} FAIL")
        orphan = _orphan_of(st)
        if orphan:
            print(f"   스키마 대장에 없는 열 {len(orphan)}건 — "
                  f"{[u['field'] for u in orphan]}")
        verdict = gate_verdict(ok, True, orphan)
        st["harness_out"] = out
        if verdict == "PASS":
            return verdict
        auto, ask = classify_failures(out)
        for ln in auto + ask:
            print(f"     {ln}")
        if orphan and not (auto or ask):
            # 하네스는 통과했는데 대장만 어긋났다 — 재생성 지시가 될 문면이 있다.
            auto = [f"[FAIL] 원본 헤더의 열 {[u['field'] for u in orphan]}이 스키마의 "
                    f"fields에도 unmappable에도 없다 — 전 열이 둘 중 하나에 있어야 한다"]
        if tries >= 1 and not _ask_more(len(auto) + len(ask)):
            return "FAIL"
        tries += 1
        if ask:
            print(f"   → 문면이 답을 담지 않는 실패 {len(ask)}건 — 문답을 연다")
            # **여기도 라운드마다 즉시 저장한다**(B55 ②-3) — 구판은 `st`에 한 줄
            # 요약만 남기고 전문이 사라졌으며, 라운드 저장이 없어 중간에 죽으면
            # 전량 유실이었다. B43 ⑤가 생성 전 문답에서 막은 것과 같은 유실이다.
            rounds = _interview(pkg or {}, context=ask,
                                on_round=_failure_persist(doc_type, pkg, samples, ask))
            answered = "; ".join(h["answer"] for h in rounds if h.get("answer"))
            instruction = ("사람 문답: " + answered) if answered else "\n".join(ask)
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
            return "FAIL"
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
    sug = {}
    for s in (prof or []):
        for col, v in (s.get("열") or {}).items():
            sug[col] = (v.get("기계제안") or {}).get("제안")
    for r in rows:
        marks = []
        # 열문자 매핑은 어댑터의 columns가 갖는다 — 없으면 이름으로 맞춰 본다.
        col = (getattr(adapter_mod, "ADAPTER", {}).get("expects", {})
               .get("columns", {}) or {}).get(r["field"])
        s = sug.get(col) if col else None
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
    used = set(cols.values())
    pos = _label_columns(exp, adapter_mod)
    if pos:
        return [lab for lab, letter in pos.items() if letter not in used]
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
    """헤더 라벨 → **실제 열 문자**. 실물을 못 읽으면 빈 dict."""
    sample = getattr(adapter_mod, "SAMPLE", None) or exp.get("sample_path")
    if not sample or not Path(sample).exists():
        return {}
    try:
        raw = reader.read(str(sample))
        hr = exp.get("header_row")
        cells = (raw.get("sheets") or [{}])[0].get("cells") or {}
        out = {}
        for addr, v in cells.items():
            letters = "".join(ch for ch in str(addr) if ch.isalpha())
            digits = "".join(ch for ch in str(addr) if ch.isdigit())
            if digits and int(digits) == hr and v is not None:
                out[str(v)] = letters
        return out
    except Exception:
        return {}


def gate_verdict(harness_ok, parses_ok, orphan):
    """기계 관문의 판정 — **셋이 모두 참이어야 PASS**다 (§6.6-6 · B49).

    `orphan`(스키마 대장에 없는 열)이 여기 있는 이유: 판정되지 않은 열이 있는 채로
    확정되면 **그 열은 영영 안 보인다** — 등록부에 오른 스키마가 그 열을 모르므로
    인입도, 검수도, 질의도 그 열을 지나친다. 사람이 판정할 것이 아니라 대장이
    어긋난 것이므로 질문이 아니라 관문이다.
    """
    return "PASS" if (harness_ok and parses_ok and not orphan) else "FAIL"


def build_view(st, results, harness_ok, harness_out, rehearsal=None):
    """뷰 데이터 산출 — **D-79 스키마가 계약**이고 여기가 산출자다.

    렌더러는 아무것도 계산하지 않으므로 **채움율·이상 신호 판정을 여기서 다 채운다.**
    """
    schema = json.loads((ROOT / st["schema"]).read_text(encoding="utf-8"))
    mod = _load(ROOT / st["adapter"], f"reg_{st['doc_type']}")
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
                "source": (ROOT / st["adapter"]).read_text(encoding="utf-8"),
            },
        },
    }


REHEARSAL_ROWS = 200        # 부분 리허설 기본값 — `--rows all`이면 전량


def _gateway_ready():
    """리허설 파싱 **전에** 게이트웨이 왕복 1회. 실패면 그 자리에서 멈춘다(2B ⑥-1).

    이것이 없으면 사내에서 무슨 일이 나나: 리허설 파싱은 좌표 미스 행마다 실호출을
    한다 — 게이트웨이가 안 닿으면 **타임아웃 60초 × 재시도 × 미스 행 수**를 말없이
    기다린다. 사용자는 «멈췄다»고 읽고, 실제로 몇 시간을 기다렸다(실측).
    **판정은 `core/llm.py::probe()`가 한다** — llm-check가 쓰는 그 함수다.
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
    raise SystemExit("[검수] 게이트웨이가 준비되지 않았다 — "
                     "`python run.py llm-check`로 단계별 원인을 본다. "
                     "USE_MOCK=1로 돌리면 LLM 없이 리허설만 볼 수 있다")


def _coord_misses(results, layer):
    """좌표가 **닫힌 목록과 정확히 일치하지 않는** 조각을 센다 — LLM을 부르지 않는다.

    이 수가 곧 «LLM 보조를 켜면 몇 회 부르는가»다(tagger는 미스 행마다 pick를 부른다).
    **몇천 회 호출은 사람이 모르고 시작하면 안 된다** — 그래서 먼저 세고 물어본다.
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
    **미스 수만큼 실호출**이다.
    """
    n = len(misses)
    if n == 0:
        return False
    sample = ", ".join(sorted(set(misses))[:5])
    print(f"   좌표 미스 {n:,}건 (예: {sample}{' …' if len(set(misses)) > 5 else ''})")
    if assume is not None:
        print(f"   → LLM 보조 {'켬' if assume else '끔'} (인자로 지정됨)")
        return assume
    if llm.use_mock():
        return False
    try:
        ans = input(f"   LLM 보조를 켜면 최대 {n:,}회 호출한다. 켤까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""                       # 대화형이 아니면 **끄고 진행**한다
    on = ans in ("y", "yes")
    print(f"   → LLM 보조 {'켬' if on else '끔 (미스는 인입에서 orphan_anchor로 간다)'}")
    return on


def _progress(i, total, calls, *, label=""):
    """진행 한 줄 — **주기 갱신**. 매 행 찍으면 그것이 잡음이 된다.

    보폭은 **최소 50행**이다: 33행짜리 표본까지 한 줄씩 찍으면 화면이 진행 표시로
    덮여 정작 읽어야 할 이상 신호가 밀려난다(실측). 큰 표본에서는 10회 안팎으로
    갱신된다. `\r` 덮어쓰기는 터미널일 때만 — 파이프로 받으면 매 줄이 남는다.
    """
    stride = max(50, total // 10)
    if not (i == 1 or i == total or i % stride == 0):
        return
    tty = sys.stdout.isatty()
    print(f"   파싱 {label} · 행 {i:,}/{total:,} · LLM 호출 {calls:,}회",
          end="\r" if (tty and i < total) else "\n", flush=True)


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
    from core import extract as EX
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
        raise SystemExit(f"[검수] '{doc_type}' 생성 단계가 먼저다")

    from cli.ingest import doc_id_of            # 리허설도 운영 doc_id다 (B51-2 · B55 ⑤)

    if instruct:                                   # 재생성 루프 1회
        st["revision"] += 1
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": instruct, "at": store._now(),
             "by": "사람(검수 지시)"})
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
                print(f"   기계 관문 FAIL — **검수 뷰를 만들지 않았다.** 산출은 "
                      f"{(REVIEW / doc_type).relative_to(ROOT)}에 남겼다")
                print(f"   지시를 바꿔 다시: python run.py register review "
                      f"{doc_type} --instruct \"…\"")
                return 1

    samples = st["samples"]
    print(f"  {llm.mode_line()}")          # B42 ⑤
    print(f"■ ② 검수 — {doc_type} (표본 {len(samples)}부)")
    # **하네스는 여기서 돌지 않는다**(M9 개정 · B50) — 생성이 이미 돌려 통과분만
    # 넘겼다. 검수는 **내용 판단**이다: role 배정·제외 열·분할을 사람이 본다.
    ok = st.get("machine_gate") == "PASS"
    out = st.get("harness_out", "")
    print(f"   기계 관문: 생성 단계에서 {'PASS' if ok else 'FAIL'} "
          f"(하네스는 생성이 돌린다 — 검수는 내용을 본다)")

    mod = _load(ROOT / st["adapter"], f"reg_{doc_type}")

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
        json.loads((ROOT / st["schema"]).read_text(encoding="utf-8")), mod)[2]
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


ADAPTERS_DIR = ROOT / "adapters"        # 확정 어댑터의 **정본 자리** (문서 6 §6.4·§6.5)


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
    src_a, src_s = ROOT / st["adapter"], ROOT / st["schema"]
    dst_a, dst_s = ROOT / a_rel, ROOT / s_rel
    dst_a.parent.mkdir(parents=True, exist_ok=True)
    dst_s.parent.mkdir(parents=True, exist_ok=True)
    if src_a.resolve() != dst_a.resolve():
        dst_a.write_bytes(src_a.read_bytes())
    if src_s.resolve() != dst_s.resolve():
        dst_s.write_bytes(src_s.read_bytes())
    return (a_rel, s_rel)


# ================================================================ ③ 확정
def cmd_confirm(doc_type, approved_by):
    """③ 확정 — 승인 1회로 등록부에 등재한다.

    **기계 관문 통과가 승인의 전제**다. "무수정 = 자동 통과"는 금지이므로 승인자가
    없으면 등재하지 않는다(틀 §2).
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[확정] '{doc_type}' 생성·검수가 먼저다")
    if st.get("machine_gate") != "PASS":
        raise SystemExit(f"[확정] 기계 관문 미통과 — 검수를 먼저 통과시켜라 "
                         f"(현재 {st.get('machine_gate')})")
    if not approved_by:
        raise SystemExit("[확정] 승인자 미지정 — 무수정 자동 통과는 금지다 (틀 §2)")

    mod = _load(ROOT / st["adapter"], f"reg_{doc_type}")
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
    print("   다음 — 인입은 이 명령으로 (등록이 그래프를 만들지는 않는다):")
    print(f"     python run.py parse run {entry['adapter']} <doc_id> <문서>")
    print("     python run.py build parsed/<doc_id>.json")
    print(f"     (한 번에: python run.py ingest-file <문서> --doc-type {doc_type})")
    return 0


def cmd_list():
    from cli.platform import cmd_doctypes
    return cmd_doctypes()


#: mock 관문 대상 — 사람이 치는 운영 명령(§7.6-B-1 · B48). `roles`·`list`는 열람이다.
GATED = ("generate", "review", "confirm")


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
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
            raise SystemExit(__doc__)
        return cmd_generate(rest[0], rest[1] if len(rest) > 1 else None, rest[2:],
                            hint, interview=interview,
                            no_fewshot=no_few, resume=resume, use_basic=use_basic,
                            drop_interview=drop_iv, revise=revise, as_name=as_name)
    if cmd == "review":
        # **prose의 리허설 기본은 전량이다**(B51) — 부분 리허설의 근거(좌표 미스
        # 비용)는 table의 것이고 prose엔 해당 없다. table 기본 200행은 그대로다.
        _st0 = _state(rest[0]) if rest else None
        _prose = bool(_st0) and str(_st0.get("schema", "")).endswith(".json") and (
            (json.loads((ROOT / _st0["schema"]).read_text(encoding="utf-8"))
             .get("payload_kind") == "prose") if (ROOT / _st0["schema"]).exists() else False)
        raw_rows = opt("--rows", "all" if _prose else str(REHEARSAL_ROWS))
        if str(raw_rows).lower() == "all":
            rows = None                      # 전량 — 자르지 않는다
        else:
            try:
                rows = int(raw_rows)
            except (TypeError, ValueError):
                raise SystemExit(f"[검수] --rows 는 정수 또는 all 이다: {raw_rows!r}")
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
    if cmd == "list":
        return cmd_list()
    raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
