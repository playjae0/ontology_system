# -*- coding: utf-8 -*-
"""생성 지시문 **조립** — 템플릿·주입·스트립·크기 (문서 6 §6.7 킷 #1 · B29~B41).

`cli/register.py`에서 떼어냈다: 등록 흐름(생성·검수·확정)과 「지시문을 어떻게 조립하나」는
바뀌는 이유가 다르다 — 앞은 명세 §6.5의 절차가, 뒤는 템플릿 판과 주입 자리가 바꾼다.
한 파일에 있으면 템플릿 판을 올릴 때 확정 로직 옆을 지나가야 한다.

**규칙은 그대로다**: 판 선택은 `kit/`의 최신 판 · 킷 유지 주석은 조립 시 제거 ·
스켈레톤은 모듈 docstring을 위치로 떼고 본문만 · 참조 어댑터는 reader 형식으로 1종.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from core import llm

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
REVIEW = ROOT / "review"


def _dir(doc_type):
    d = REVIEW / doc_type
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def _strip_module_doc(src):
    """모듈 docstring을 떼고 그 뒤만 돌려준다 — **위치로 판정한다.**

    스켈레톤 머리의 「사람용 안내」(빈칸 상태 FAIL 4건 실측 등)는 **킷을 고치는
    사람이 읽을 것**이지 생성 세션이 읽을 것이 아니다. `_strip_kit_notes`와 같은
    원리이되 판정 기준이 다르다: 저기는 **스스로 표시한 문면**을, 여기는
    **구문상의 자리**(모듈 docstring)를 본다.

    **내용 문자열로 판정하지 않는다** — 「FAIL 4건」 같은 낱말을 세면 안내를 고칠
    때마다 이 코드가 따라 움직이고, 안내가 바뀌면 조용히 안 떼어진다.
    """
    tree = ast.parse(src)
    doc = ast.get_docstring(tree, clean=False)
    if doc is None or not tree.body:
        return src
    first = tree.body[0]
    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)):
        return src
    lines = src.split("\n")
    return "\n".join(lines[first.end_lineno:]).lstrip("\n")


def _reference_adapter(samples):
    """표본의 **reader 형식**으로 few-shot 전시물 1종을 고른다.

    payload_kind는 아직 생성 세션이 판정하기 전이다 — 그래서 이미 아는 것으로
    고른다: reader가 무엇으로 읽었는가. 혼재면 **첫 표본** 기준이다(둘을 다 실으면
    프롬프트가 두 배가 되고, 어느 쪽이 모범인지도 흐려진다).
    """
    first = str(samples[0]).lower() if samples else ""
    name = "toc_report.py" if first.endswith((".pptx", ".ppt")) else "cp.py"
    p = KIT / "참조어댑터" / name
    return name, (p.read_text(encoding="utf-8") if p.exists() else "")


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

    # **참조 어댑터 few-shot**(B29 ★②) — 표본의 reader 형식으로 1종을 고른다.
    # 전시물 머리의 출처 표기(B27)는 **함께 싣는다**: 킷 유지 규칙이 아니라
    # 전시물의 일부이고, 「이것은 다른 문서의 것」이라는 사실 자체가 지시다.
    _human = pkg.get("human") or {}
    # **끈 사실이 패키지에 남는다**(B30) — 재현 조건이다. 같은 표본으로 다시 돌려도
    # 이 값이 없으면 왜 전시물이 빠졌는지 되짚을 수 없다.
    _hint = _human.get("hint")
    _off = isinstance(_hint, dict) and _hint.get("no_fewshot")
    _name, _body = ("(없음)", "") if _off else \
        _reference_adapter(_human.get("samples") or [])
    ref_md = (f"```python\n# ── {_name} (kit/참조어댑터/{_name})\n{_body}```"
              if _body else
              "(이번 조립은 참조 어댑터를 싣지 않았다 — `--no-fewshot`. "
              "규약 10의 실물이 없으므로 규약 문면과 스켈레톤 뼈대만 보고 낸다)"
              if _off else
              "(참조 어댑터를 찾지 못했다 — kit/참조어댑터/ 확인)")

    layers = voc.get("layers") or []
    for mark, val in (("{{참조_어댑터}}", ref_md),
                      ("{{층_이름}}", str(voc.get("layer") or "")),
                      ("{{존재하는_층_목록}}", " · ".join(f"`{x}`" for x in layers)),
                      ("{{카테고리_정의문}}", cat_md),
                      ("{{관계_패턴_표}}", rel_md),
                      ("{{공용_블록_목록}}", blocks_md),
                      ("{{골격_닫힌_목록}}", sk_md)):
        text = text.replace(mark, val)
    # **치환 뒤에 덜어낸다.** 주석 안에도 주입 자리가 있어(공용 블록 절) 먼저 빼면
    # `{{…}}`가 남았는지의 판정이 흐려진다 — 치환은 전량 하고 그 뒤 걷어낸다.
    return _strip_kit_notes(text)


VOCAB_SECTIONS = ("## [role 어휘", "## [role 배정 대상이 아닌 필드", "## [층 어휘")


def _vocab_excerpt(pkg):
    """생성 템플릿에서 **판정 어휘 세 구획**을 발췌한다 (B32).

    **두 지시문에 같은 어휘를 따로 적지 않는다** — 정본은 생성 템플릿 하나이고,
    문답 지시문(`prompts/interview.md`)에는 *"판정 어휘가 뒤에 붙어 온다"*는 전제만
    있다. 따로 적으면 한쪽이 낡고, 그때 문답이 묻는 어휘와 생성이 쓰는 어휘가
    갈린다 — 이 프로젝트가 세 번 실측한 미러 실패의 구조다.

    **발췌는 구획 제목 앵커로** 한다: 렌더 뒤라 층 이름이 이미 치환돼 있어
    (`## [층 어휘 — quality 층]`) 접두 일치가 유일하게 안전한 판정이다.
    """
    doc = _render_template(_newest_template().read_text(encoding="utf-8"), pkg)
    lines = doc.split("\n")
    starts = [i for i, ln in enumerate(lines)
              if any(ln.startswith(s) for s in VOCAB_SECTIONS)]
    out = []
    for i in starts:
        j = next((k for k in range(i + 1, len(lines))
                  if lines[k].startswith("## [")), len(lines))
        out.append("\n".join(lines[i:j]).rstrip())
    return "\n\n".join(out)


def _sent_size(msgs, label, _n_samples=1):
    """전송 크기를 화면에 1줄 (B30) — **부르기 직전에** 잰다.

    게이트웨이 컨텍스트를 넘기면 응답이 잘리는 게 아니라 **요청이 거부된다** —
    `finish_reason=length` 경고는 응답 쪽이라 그것을 잡지 못한다. 사람이 보내기
    전에 크기를 알아야 전시물을 끄든 표본을 줄이든 판단할 수 있다.
    """
    sys_b = sum(len(m["content"].encode("utf-8"))
                for m in msgs if m["role"] == "system")
    usr_b = sum(len(m["content"].encode("utf-8"))
                for m in msgs if m["role"] != "system")
    tot = sys_b + usr_b
    # 한글 혼재 기준의 **거친 어림**이다(3바이트/토큰) — 정밀 계수는 게이트웨이 몫.
    est = tot // 3          # 한글 혼재의 거친 어림 — 정밀 계수는 게이트웨이 몫
    lim = llm.context_limit()
    print(f"   [전송] {label} — system {sys_b:,}B + user {usr_b:,}B "
          f"= {tot:,}B (약 {est:,} 토큰"
          + (f" / 한도 {lim:,})" if lim else ")"), flush=True)
    if lim and est > lim:
        # **초과면 보내지 않고 멈춘다** — 컨텍스트 초과는 응답이 잘리는 게 아니라
        # 요청이 거부되고, 그 거부는 게이트웨이마다 문면이 달라 원인이 안 보인다.
        # 감축 수단을 **순서대로** 낸다: 싸고 손실 적은 것부터.
        raise SystemExit(
            f"[전송] 예산 초과 — 약 {est:,} 토큰 > 한도 {lim:,}. 보내지 않았다.\n"
            f"   감축 순서:\n"
            f"     ① --no-fewshot        참조 어댑터 주입을 끈다 (약 −2,100 토큰)\n"
            f"     ② 프로파일 대표값 축소   parser/profile.py의 FULL_LIST_MAX·"
            f"SAMPLE_VALUES를 줄인다 (열당 약 −30 토큰)\n"
            f"     ③ 표본 부수 축소        표본 1부당 약 −{usr_b // 3 // max(1, _n_samples):,} 토큰\n"
            f"   한도는 llm.json의 \"LLM_CONTEXT_TOKENS\"다 — 지우면 대조하지 않는다")
    return tot
