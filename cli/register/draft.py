# -*- coding: utf-8 -*-
"""칸 1.4 — **어댑터·스키마 초안**: 생성 스키마 · 실호출 갈래 · 고정 어댑터 제안."""

from __future__ import annotations

from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core import paths
from core.llm import check, gateway, points
from core.state import fixtures, log, registry, store
from parser import form
from parser import pipeline, preflight, profile, reader, tagger
from parser.adapters import basic_ppt, basic_prose_xlsx
from pathlib import Path
import json
import os
from cli.register import FIXTURES, REVIEW, ROOT, _save_state, _state


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
    if gateway.use_mock():
        gateway.mock("generate", f"fixture {doc_type} rev{revision}")
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
    **인증 헤더·키는 남기지 않는다** — `core/llm/gateway.py`가 애초에 담지 않는다.
    """
    if not gateway.LAST_ERROR:
        return
    d = _dir(doc_type)
    (d / "last_error.json").write_text(
        json.dumps({**gateway.LAST_ERROR, "예외": f"{type(e).__name__}: {e}"},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   [오류] 게이트웨이 응답을 남겼다 → "
          f"{paths.show(d / 'last_error.json')}")


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
    gateway.require("generate")          # 설정 미비를 먼저 알린다 — 준비 순서가 그쪽이 먼저다
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
        out = gateway.chat(msgs, json_schema=generate_schema(_kind), point="generate")
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
