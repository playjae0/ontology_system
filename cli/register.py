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
  python cli/register.py review   <doc_type> [--instruct "수정 지시"] [--rows N|all]
       --rows       리허설 파싱을 앞 N행으로 제한 (기본 200 · 전량은 all)
       --llm-coord / --no-llm-coord   좌표 LLM 보조를 미리 정한다 (기본: 물어본다)
  python cli/register.py confirm  <doc_type> --by <승인자>
  python cli/register.py list
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from core import fixtures, llm, registry, store
from parser import pipeline, preflight, reader, tagger
from parser.adapters import basic_ppt
from kit.render_review import render
from kit.run_adapter import load_blocks
from router import discover

REVIEW = ROOT / "review"
KIT = ROOT / "kit"
FIXTURES = fixtures.ROOT_DIR / "fixtures"   # 소재는 core/fixtures.py가 소유

# D-22 확장 문구 — 표본 1부 등록의 경고. **문면이 규격이다.**
SOLO_WARNING = ("표본 1부 · 변형 미관찰 — **선언된 관계는 근거 1건일 수 있음**. "
                "1부 등록의 선언 edges는 특별 확인 대상이다")
EXCERPT = 3                                   # 정상 조각 발췌 건수(전량은 접힘에 실린다)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
def draft(doc_type, revision=0):
    """어댑터·매칭 스키마 **초안** — USE_MOCK은 fixture 반환이다 (D-10 · D-26).

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
                json.loads(pkg.read_text(encoding="utf-8"))))
        for stem in ([f"{doc_type}_rev{revision}"] if revision else []) + [doc_type]:
            ad = FIXTURES / "adapters" / f"{stem}.py"
            sc = FIXTURES / "schemas" / f"{stem}.json"
            if ad.exists() and sc.exists():
                return ad, sc
        return None, None
    return _draft_live(doc_type, revision)


GENERATE_SCHEMA = {
    "type": "object",
    "properties": {"adapter_py": {"type": "string"},
                   "schema_json": {"type": "string"}},
    "required": ["adapter_py", "schema_json"], "additionalProperties": False,
}


KIT_NOTE = ("킷 조립 규칙", "킷 유지 규칙")


def _strip_kit_notes(text):
    """**킷을 고치는 사람이 읽을 것**을 조립 시점에 덜어낸다 (문서 6 §6.7 킷 #1).

    두 가지를 뺀다:
      ① 머리말 — 파일 시작부터 `## [지시]` 직전까지. **판 계보는 킷을 고치는
         사람의 것**이지 생성 세션이 읽을 것이 아니다(v0.5 실측: 1,682자 = 전체의
         14%이고 그 안에 `Process` 2·`Unit` 2·`Property` 1이 들어 있었다).
      ② 스스로 「킷 조립 규칙」·「킷 유지 규칙」이라고 표시한 인용 문단.
         그 주석은 *"LLM 지시가 아니다"*라고 말하면서 LLM에게 가고, **제외하려던
         층 어휘를 다시 실어 나른다** — v0.5 치환 결과의 잔재 3건이 전부 그 안이었다.

    **인용 블록 통째로 지우지 않는다.** 같은 `>` 블록 안에 LLM이 읽어야 하는 문단이
    섞여 있다 — 예: 「패턴표에 없는 관계를 `edges`에 쓰지 마라」. 그래서 빈 인용
    줄(`>`)로 갈라 **문단 단위**로 판정하고, **표시된 것만** 뺀다.

    **파일은 건드리지 않는다** — 제거는 조립 시점뿐이고 킷은 근거를 계속 보유한다.
    """
    lines = text.split("\n")
    head = next((i for i, ln in enumerate(lines) if ln.startswith("## [지시]")), 0)
    lines = lines[head:]

    out, para, in_q = [], [], False
    def flush():
        if para and not any(m in "".join(para) for m in KIT_NOTE):
            out.extend(para)
        para.clear()

    for ln in lines:
        q = ln.startswith(">")
        if q:
            in_q = True
            if ln.strip() == ">":            # 인용 안의 문단 경계
                flush()
                para.append(ln)
                flush()
            else:
                para.append(ln)
            continue
        if in_q:
            flush()
            in_q = False
        out.append(ln)
    flush()

    # 문단을 빼며 남은 빈 인용 줄·연속 공백 줄을 정리한다 — 화면 잡음이지 지시가 아니다.
    cleaned = []
    for ln in out:
        if ln.strip() == ">" and (not cleaned or cleaned[-1].strip() in ("", ">")):
            continue
        if ln.strip() == "" and cleaned and cleaned[-1].strip() == "":
            continue
        cleaned.append(ln)
    while cleaned and cleaned[-1].strip() == ">":
        cleaned.pop()
    return "\n".join(cleaned)


def _dump_prompt(doc_type, text):
    """`ONTO_DUMP_PROMPT=1`이면 조립된 지시문을 파일로 떨군다 — **관측용이다.**

    치환이 실제로 됐는지는 **조립된 문자열을 눈으로 봐야** 판정된다. 코드를 읽어
    「될 것이다」로 판정하면, 자리 하나가 빠져도 `{{…}}`가 그대로 모델에 나가는
    상태를 아무도 모른다 — 실제로 `{{골격_닫힌_목록}}`이 그 상태였다.
    기본은 꺼져 있다(산출물을 늘리지 않는다).
    """
    if os.environ.get("ONTO_DUMP_PROMPT") != "1":
        return None
    d = _dir(doc_type)
    out = d / "prompt_rendered.md"
    out.write_text(text, encoding="utf-8")
    print(f"   [덤프] 조립된 지시문 → {out.relative_to(ROOT)} ({len(text)}자)")
    return out


def _newest_template():
    """`kit/`의 생성 프롬프트 템플릿 중 **가장 높은 판**을 고른다.

    파일명을 코드에 박으면 판이 오를 때마다 코드가 따라 움직여야 하고, 옛 판을
    보존하는 킷 규칙(판 계보)과 겹쳐 **어느 판이 실제로 쓰이는지가 파일 목록으로는
    안 보인다.** 판 번호는 자산이 스스로 말하게 한다.
    """
    cands = sorted(KIT.glob("생성프롬프트_템플릿_v*.md"),
                   key=lambda f: [int(x) for x in
                                  re.findall(r"\d+", f.stem.split("_v")[-1])])
    if not cands:
        raise SystemExit(f"[생성] 프롬프트 템플릿이 없다: {KIT}/생성프롬프트_템플릿_v*.md")
    return cands[-1]


def _render_template(text, pkg):
    """템플릿의 주입 자리 6개를 **입력 패키지의 값으로** 치환한다.

    **왜 필요한가.** v0.4는 `Process`·`Unit`·`Property` 정의문과 `Unit part_of
    Process` 삼항을 본문에 직접 적었다. 그런데 `cmd_generate`는 같은 정보를
    `layer_vocabulary`로 이미 싣는다 — **같은 사실이 두 곳에 살고 하나가 고정**인
    상태였고, 품질층 등록에서 템플릿과 입력 패키지가 서로 다른 어휘를 말한다.
    `{{골격_닫힌_목록}}`도 치환하는 코드가 없어 **글자 그대로** 나가고 있었다.

    **값은 전부 `pkg["system"]`에 이미 있다** — 새 키를 만들지 않는다(시스템 5키가
    명세이고 회귀가 센다). 치환은 있는 값을 렌더하는 일이다.
    """
    sysd = pkg.get("system") or {}
    voc = sysd.get("layer_vocabulary") or {}

    cats = voc.get("categories") or {}
    cat_md = "\n".join(f"- `{k}` — {v}" for k, v in cats.items()) or "- (없음)"

    rows = ["| 관계 | 삼항 | 정의문 |", "|---|---|---|"]
    for r in (voc.get("relation_patterns") or []):
        sym = " · **대칭**" if r.get("symmetric") else ""
        rows.append(f"| `{r.get('rel')}`{sym} | `{r.get('src')} {r.get('rel')} "
                    f"{r.get('dst')}` | {r.get('정의문') or r.get('definition') or ''} |")
    rel_md = "\n".join(rows) if len(rows) > 2 else "(패턴 없음)"

    blocks, bl = sysd.get("blocks") or {}, []
    for name, body in blocks.items():
        # `_`로 시작하는 키는 주석·구조 메모다 — 블록이 아니므로 목록에 올리지 않는다.
        if name.startswith("_") or not isinstance(body, dict):
            continue
        fields = ", ".join(f"`{f}`" for f in body if not f.startswith("_"))
        bl.append(f"- `{name}` — 제공 필드: {fields or '(없음)'}")
    blocks_md = "\n".join(bl) or "- (이 층이 쓸 수 있는 블록이 없다)"

    surf = (sysd.get("skeleton_closed_list") or {}).get("surfaces") or []
    sk = []
    for n in surf:
        al = n.get("aliases") or []
        sk.append(f"- `{n.get('canonical')}`"
                  + (f"  (별칭: {', '.join(al)})" if al else ""))
    sk_md = "\n".join(sk) or "- (골격 닫힌 목록이 비었다)"

    # **힌트 자리도 채운다.** 요청 표에는 6개가 적혔지만 템플릿에는 자리가 일곱이고,
    # 하나라도 남으면 `{{…}}`라는 글자가 그대로 모델에 나간다 — 지시문이 스스로
    # 「여기 렌더된다」고 말하면서 렌더되지 않는 상태가 v0.4의 결함이었다.
    # 값은 `pkg["human"]["hint"]`에 이미 있다(새 키가 아니다).
    hint = (pkg.get("human") or {}).get("hint") or ""
    if isinstance(hint, dict):
        # `--interview`면 힌트는 **문답 전문**이다 — 지시문에는 사람이 준 자유
        # 텍스트와 라운드별 이해·답을 함께 싣는다(LLM이 무엇에 합의했는지가 입력이다).
        parts = [hint.get("text") or ""]
        for r in hint.get("interview") or []:
            parts.append(f"[문답 라운드 {r['round']}] 이해: {r['understanding']}")
            if r.get("answer"):
                parts.append(f"  사람의 답/교정: {r['answer']}")
        hint = "\n".join(x for x in parts if x.strip())
    text = re.sub(r"\{\{사용자 자유 텍스트[^}]*\}\}",
                  hint if hint.strip() else "(힌트 없음 — 사람이 준 자유 텍스트가 없다)",
                  text)

    layers = voc.get("layers") or []
    for mark, val in (("{{층_이름}}", str(voc.get("layer") or "")),
                      ("{{존재하는_층_목록}}", " · ".join(f"`{x}`" for x in layers)),
                      ("{{카테고리_정의문}}", cat_md),
                      ("{{관계_패턴_표}}", rel_md),
                      ("{{공용_블록_목록}}", blocks_md),
                      ("{{골격_닫힌_목록}}", sk_md)):
        text = text.replace(mark, val)
    # **치환 뒤에 덜어낸다.** 주석 안에도 주입 자리가 있어(공용 블록 절) 먼저 빼면
    # `{{…}}`가 남았는지의 판정이 흐려진다 — 치환은 전량 하고 그 뒤 걷어낸다.
    return _strip_kit_notes(text)


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


def _draft_live(doc_type, revision):
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
    system = _render_template(_newest_template().read_text(encoding="utf-8"),
                              json.loads(raw_pkg))
    _dump_prompt(doc_type, system)          # ONTO_DUMP_PROMPT=1일 때만
    out = llm.chat(
        # user 메시지는 **원본 패키지 JSON 그대로** 보낸다 — 치환은 지시문의 일이고
        # 입력의 정본은 패키지다. 둘을 섞으면 어느 쪽이 정본인지 갈린다.
        [{"role": "system", "content": system},
         {"role": "user", "content": raw_pkg}],
        json_schema=GENERATE_SCHEMA, point="generate")
    d = REVIEW / doc_type
    d.mkdir(parents=True, exist_ok=True)
    suffix = f"_rev{revision}" if revision else ""
    ad = d / f"adapter{suffix}.py"
    sc = d / f"schema{suffix}.json"
    ad.write_text(out["adapter_py"], encoding="utf-8")
    _write_schema(sc, out["schema_json"])
    return ad, sc


def basic_adapter_proposal(samples):
    """분할이 **자명한 계열**이면 기본 어댑터를 제안한다 (파서_명세 §5 규약 5 · C13).

    자명한 것을 매번 생성시키면 검수 비용만 늘고 산출은 같다. 다만 임계를 넘는
    슬라이드가 있으면 자명함이 조건부가 되므로(C13 v18) 그 사실도 함께 말한다.
    """
    if not all(str(s).lower().endswith(".pptx") for s in samples):
        return None
    # **임계는 어댑터가 소유한다**(문서 6 §6.4-5) — 판단 상수는 `ADAPTER.expects`에
    # 산다(문서 7 §7.1 관리 자산의 원칙). 여기에 숫자를 복제하면 "조정은 어댑터
    # 한 곳에서"가 깨지고, 어댑터를 고쳐도 이 화면의 판정은 옛 임계로 남는다.
    exp = basic_ppt.ADAPTER["expects"]
    max_chars, max_shapes = exp["max_chars"], exp["max_shapes"]
    over = 0
    for s in samples:
        for sl in reader.read(str(s)).get("slides", []):
            shapes = [x for x in sl.get("shapes", []) if x and x.strip()]
            if sum(len(x) for x in shapes) > max_chars or len(shapes) > max_shapes:
                over += 1
    return {"adapter": "parser/adapters/basic_ppt.py",
            "reason": "PPT는 분할이 자명하다 — 슬라이드가 청크다. 생성 세션이 필요 없다",
            "over_threshold_slides": over,
            "note": ("임계 초과 슬라이드가 있어 자명함이 조건부다 — shape 분할·지도 폴백이 "
                     "돈다(C13 v18)" if over else "전 슬라이드가 임계 이하다")}


INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        # **이해 요약이 이 설계의 심장이다** — 사람이 판정하는 대상은 "질문에 다
        # 답했나"가 아니라 **"LLM의 이해가 맞아졌나"**다.
        "understanding": {"type": "string"},
        "questions": {"type": "array", "items": {
            "type": "object",
            "properties": {"q": {"type": "string"},
                           "options": {"type": "array", "items": {"type": "string"}}},
            "required": ["q", "options"], "additionalProperties": False}},
    },
    "required": ["understanding", "questions"], "additionalProperties": False,
}

INTERVIEW_STOP = ("진행", "go", "ok", "진행해", "진행합니다")


def _interview_round(pkg, history):
    """문답 1라운드 — 이해 요약과 질문을 받는다. **종료를 결정하지 않는다.**

    LLM은 «이해했다, 진행하겠다»를 판단하지 않는다(I4: 제어 흐름은 코드+사람
    소유). 매 라운드 요약과 질문을 낼 뿐이고, **끝내는 것은 사람**이다.

    mock 갈래는 **표본 관찰 재료와 누적 답변에서 규칙으로** 요약을 만든다 —
    미리 적어 둔 문장을 되읽으면 「교정이 반영되는가」를 아무것도 검증하지 않는다.
    """
    heads = (pkg.get("system") or {}).get("reader_head") or []
    cols = []
    for h in heads:
        for sh in (h.get("head") or {}).get("sheets") or []:
            cols += [v for a, v in (sh.get("cells") or {}).items()
                     if a.endswith("1") and isinstance(v, str)]
    if llm.use_mock():
        llm.mock("generate", f"문답 라운드 {len(history) + 1} — 규칙 요약")
        base = (f"열 {len(cols)}개를 관찰했다: {', '.join(cols[:6])}"
                if cols else "표본에서 열을 관찰하지 못했다")
        fixes = [h["answer"] for h in history if h.get("answer")]
        return {"understanding": base + ("" if not fixes else
                                         " · 교정 반영: " + " / ".join(fixes)),
                "questions": ([] if fixes else
                              [{"q": "병합된 좌측 열은 어떻게 다루나",
                                "options": ["위 값 채움", "행 독립", "모름"]}])}

    convo = [{"role": "system", "content": llm.prompt("interview")},
             {"role": "user", "content": json.dumps(
                 {"입력_패키지": pkg, "지난_문답": history}, ensure_ascii=False)}]
    return llm.chat(convo, json_schema=INTERVIEW_SCHEMA, point="generate")


def _interview(pkg):
    """생성 전 문답 — **끝내는 것은 사람뿐이다.** 상한 없음(§6.5 재생성 루프와 같은 원리).

    돌려주는 것은 라운드 이력이다: 매 라운드의 요약·질문·답이 전부 남는다.
    기록이 없으면 **같은 등록을 재현할 수 없다.**
    """
    history, blanks = [], 0
    print("\n■ 생성 전 문답 — 이해 요약을 보고 교정한다. "
          f"끝내려면 «{INTERVIEW_STOP[0]}» (상한 없음)")
    while True:
        out = _interview_round(pkg, history)
        n = len(history) + 1
        print(f"\n[라운드 {n}] 이해 요약")
        print(f"   {out['understanding']}")
        for i, q in enumerate(out.get("questions") or [], 1):
            print(f"   Q{i}. {q['q']}")
            print(f"       선택지: {' · '.join(q.get('options') or [])}")
        try:
            ans = input("   답/교정 (빈 줄 2회 또는 «진행»이면 종료) > ").strip()
        except (EOFError, KeyboardInterrupt):
            ans = INTERVIEW_STOP[0]
            print(f"   (입력 없음 — {ans})")
        history.append({"round": n, "understanding": out["understanding"],
                        "questions": out.get("questions") or [], "answer": ans})
        if ans.lower() in INTERVIEW_STOP:
            print(f"   → 사람이 종료했다. 라운드 {n}회 · 생성으로 간다")
            return history
        blanks = blanks + 1 if not ans else 0
        if blanks >= 2:
            print(f"   → 빈 입력 2연속 — 종료로 읽는다. 라운드 {n}회")
            return history


def cmd_generate(doc_type, layer, samples, hint="", interview=False):
    """① 생성 — 입력 패키지를 세우고 초안을 받는다.

    **입력 패키지 = 사람 4 + 시스템 5**(증분0 §3 P3 · 카드 M10):
      사람 — 표본 · doc_type 이름 · 층 지정 · 힌트(자유 텍스트)
      시스템 — reader 원시 추출 · 골격 닫힌 목록 · 층 어휘 · 공용 블록 · 어댑터 스켈레톤
    """
    if registry.lookup(doc_type):
        raise SystemExit(f"[생성] doc_type 이름 중복 — '{doc_type}'은 이미 등록돼 있다")

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

    snap = store.read(store.SKELETON_LIST, {}).get(layer) or {}
    cfg = json.loads((ROOT / "layers" / layer / "config.json").read_text(encoding="utf-8"))
    pkg = {
        # **첫 키가 읽는 법이다** — 이 파일을 처음 여는 사람이 어디를 볼지 모른다.
        "_읽는 법": "사람이 볼 것은 human.hint(사람이 준 것)와 "
                  "system.reader_head(표본 관찰 재료)다. 나머지는 시스템이 채운다",
        "human": {"doc_type": doc_type, "layer": layer,
                  "samples": [str(s) for s in samples], "hint": hint},
        "system": {
            "reader_head": [{"path": str(s), "head": reader.head(reader.read(str(s)), 12)}
                            for s in samples],
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
            "adapter_skeleton": str((KIT / "어댑터_스켈레톤.py").relative_to(ROOT)),
        },
    }
    d = _dir(doc_type)
    (d / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부)")
    print(f"   입력 패키지: 사람 4 + 시스템 5 → {(d / 'input_package.json').relative_to(ROOT)}")

    if interview:
        # **문답은 패키지가 선 뒤다** — 문답의 입력이 그 패키지(표본 관찰 재료)다.
        # 끝나면 전문을 `human.hint`에 구조화해 다시 싣는다: 기록이 없으면 같은
        # 등록을 재현할 수 없다. **시스템 5키는 그대로다.**
        rounds = _interview(pkg)
        pkg["human"]["hint"] = {"text": hint, "interview": rounds}
        (d / "input_package.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"   문답 {len(rounds)}라운드 → human.hint 에 전문 기록")
    proposal = basic_adapter_proposal(samples)
    if proposal:
        print(f"   ▶ 기본 어댑터 적용 제안 — {proposal['reason']}")
        print(f"     {proposal['note']}")
    ad, sc = draft(doc_type)
    if ad is None:
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "
                         f"'{doc_type}' 부재 (D-10). 실물 경로는 생성 LLM 훅이다")
    print(f"   초안 수령: {ad.relative_to(ROOT)} · {sc.relative_to(ROOT)}")
    u = llm.usage_total()
    if u["calls"]:
        print(f"   LLM 사용량 — 호출 {u['calls']:,}회 · 토큰 {u['total_tokens']:,}"
              f"(입력 {u['prompt_tokens']:,} · 출력 {u['completion_tokens']:,})"
              + (f" · **응답 잘림 {u['truncated']}회**" if u["truncated"] else ""))
    _save_state(doc_type, {"doc_type": doc_type, "layer": layer,
                           "samples": [str(s) for s in samples],
                           "hint": pkg["human"]["hint"],
                           "adapter": str(ad.relative_to(ROOT)),
                           "schema": str(sc.relative_to(ROOT)),
                           "revision": 0, "instructions": [],
                           "basic_adapter_proposal": proposal})
    return 0


# ================================================================ ② 검수
def harness(adapter, schema, samples):
    """기계 관문 — **kit/run_adapter.py를 그대로 부른다**(재작성 아님)."""
    r = subprocess.run([sys.executable, str(KIT / "run_adapter.py"),
                        str(adapter), str(schema)] + [str(s) for s in samples],
                       capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode == 0, r.stdout


def role_table(schema, adapter_mod):
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
    for f in unmappable_of(schema, adapter_mod):
        rows.append({"field": f, "role": "UNMAPPABLE",
                     "reason": "5종 어디에도 맞지 않는다 — 사람 판정 대기 (D-30)"})
    return rows


def _col(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def unmappable_of(schema, adapter_mod):
    """UNMAPPABLE 열 — **어댑터가 스스로 밝힌 미매핑분**에서 판정한다.

    D-30은 "UNMAPPABLE 열은 스키마 fields에 넣지 않고 어댑터 출력에서도 제외"라고
    정한다. 그러면 그 열은 어디에도 이름이 남지 않아 배정표에서 사라지고, **6지선다의
    여섯째 경로가 화면에서 증발한다** — 사람이 판정해야 할 것이 판정 화면에 없다.

    복원 경로는 어댑터의 선언 둘의 차집합이다: `header_labels`(원본 헤더 전량 — D-29)
    에 있는데 `columns`(출력 필드명 매핑)가 가리키지 않는 열. 스키마가 `unmappable`을
    명시하면 그쪽이 이긴다 — 명시는 판정이고 차집합은 복원이다.
    """
    if schema.get("unmappable"):
        return list(schema["unmappable"])
    exp = (getattr(adapter_mod, "ADAPTER", {}) or {}).get("expects") or {}
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


def build_view(st, results, harness_ok, harness_out):
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
    for f in unmappable_of(schema, mod):
        anomalies.append({"kind": "question",
                          "message": f"'{f}' 열은 role 5종 어디에 배정합니까 — "
                                     f"생성 세션이 UNMAPPABLE로 올렸다",
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
                            "failures": sum(1 for a in anomalies if a["kind"] == "failure"),
                            "warnings": sum(1 for a in anomalies if a["kind"] == "warning"),
                            "fill_rate": fill},
                "anomalies": anomalies,
                "normal": {"excerpt": pieces[:EXCERPT], "all": pieces,
                           "columns": keys if kind == "table" else [],
                           "tree": tree if kind == "prose" else []},
            },
            "role_table": role_table(schema, mod),
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


def cmd_review(doc_type, instruct=None, rows=REHEARSAL_ROWS, llm_coord=None):
    """② 검수 — 기계 관문 → 뷰 데이터 → HTML. 지시가 오면 **재생성 루프**를 돈다.

    **상한은 없다**(§7 규약 2 · A8 — 근거 없는 수치 금지). 매회 지시가 이력에 남고
    중단은 사람 판단이다. 화면에는 강제 없는 안내만 둔다.
    """
    st = _state(doc_type)
    if not st:
        raise SystemExit(f"[검수] '{doc_type}' 생성 단계가 먼저다")

    if instruct:                                   # 재생성 루프 1회
        st["revision"] += 1
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": instruct, "at": _now()})
        ad, sc = draft(doc_type, st["revision"])
        if ad is None:
            print(f"   ⚠ 재생성 대안본 부재 — 초안을 유지한다 "
                  f"(USE_MOCK: fixture '{doc_type}_rev{st['revision']}' 없음)")
        else:
            st["adapter"], st["schema"] = (str(ad.relative_to(ROOT)),
                                           str(sc.relative_to(ROOT)))
            print(f"   재생성 {st['revision']}회째 → {ad.relative_to(ROOT)}")

    samples = st["samples"]
    print(f"■ ② 검수 — {doc_type} (표본 {len(samples)}부)")
    ok, out = harness(ROOT / st["adapter"], ROOT / st["schema"], samples)
    print(f"   기계 관문(하네스): {'PASS' if ok else 'FAIL'} — "
          f"{out.count('[PASS]')} PASS / {out.count('[FAIL]')} FAIL")

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
            out.append(pipeline.parse(
                mod, f"{doc_type.upper()}{i:02d}", s, layer=st["layer"],
                summarize=llm.image_summarizer(), pick_coord=pick,
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

    view = build_view(st, results, ok, out)
    d = _dir(doc_type)
    (d / "view.json").write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    (d / "view.html").write_text(render(view), encoding="utf-8")   # kit 렌더러 호출
    st["machine_gate"] = "PASS" if (ok and all(r.ok for r in results)) else "FAIL"
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
    at = _now()
    # **등재가 먼저, 승격이 나중이다.** 반대로 하면 등재가 거부됐을 때 승격된
    # 파일만 남아 조회에는 잡히고 등록부에는 없는 반쪽 상태가 되고, 그 이름의
    # 재등록이 「내장 중복」으로 영영 막힌다(실측).
    adapter_path, schema_path = _promote_paths(doc_type)
    entry = registry.register(
        doc_type, layer=st["layer"], adapter=adapter_path, schema=schema_path,
        adapter_version=mod.ADAPTER.get("adapter_version"),
        approved_by=approved_by, approved_at=at,
        instructions=st.get("instructions") or [])
    _promote(doc_type, st)              # 등재가 성립한 뒤에만 실물을 옮긴다
    approval = {"doc_type": doc_type,
                "adapter_version": mod.ADAPTER.get("adapter_version"),
                "승인자": approved_by, "시점": at,
                "수정 지시 이력": st.get("instructions") or []}
    (_dir(doc_type) / "approval.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"■ ③ 확정 — {doc_type} 등록부 등재 (승인 {approved_by} @ {at})")
    print(f"   어댑터·스키마 활성: {entry['adapter']} · {entry['schema']}")
    print(f"   승인 기록 → {(_dir(doc_type) / 'approval.json').relative_to(ROOT)}")
    return 0


def cmd_list():
    from cli.platform import cmd_doctypes
    return cmd_doctypes()


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd, rest = argv[0], list(argv[1:])

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
        return cmd_generate(rest[0], rest[1], rest[2:], hint, interview=interview)
    if cmd == "review":
        raw_rows = opt("--rows", str(REHEARSAL_ROWS))
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
        return cmd_review(rest[0], opt("--instruct"), rows=rows, llm_coord=coord)
    if cmd == "confirm":
        return cmd_confirm(rest[0], opt("--by"))
    if cmd == "list":
        return cmd_list()
    raise SystemExit(f"알 수 없는 명령: {cmd}\n{__doc__}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
