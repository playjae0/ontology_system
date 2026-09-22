# -*- coding: utf-8 -*-
"""칸 1.1·1.2 — **① 생성 흐름**: 입력 패키지 → 초안 → 관문 (`register generate`)."""

from __future__ import annotations

from cli.interview import (  # noqa: F401
    INTERVIEW_SCHEMA, INTERVIEW_STOP, _interview_round, _prof_hint, _interview,
    finalize as iv_finalize)
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core import paths
from core.llm import check, gateway, points
from core.state import fixtures, log, registry, store
from parser import pipeline, preflight, profile, reader, tagger
from pathlib import Path
from router import discover
import json
from cli.register import draft as draft_mod
from cli.register import gate
from cli.register import interview as ivlog
from cli.register import ledger
from cli.register import KIT, REVIEW, ROOT, _save_state, _state


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


def _cmd_generate_revise(doc_type, layer):
    """⓪ **새 판**(`--revise`)의 전제 — 등록분인가 · 고정 어댑터가 아닌가.

    `cmd_generate`에서 단계로 떼어냈다(B78 2c) — 한 함수가 404행이면 어느 단계에서
    막혔는지를 사람이 줄 번호로 찾게 된다.
    """
    # **새 판** — 이름은 그대로다. 확정이 정본을 교체하고 revision을 올린다.
    _st_prev = _state(doc_type) or {}
    if _st_prev.get("use_basic"):
        draft_mod.refuse_regenerate(doc_type, _st_prev, "생성")    # B65 ④
    if not registry.lookup(doc_type):
        raise SystemExit(f"[생성] --revise는 **등록분**에만 쓴다 — "            # [상태]
                         f"'{doc_type}'은 등록돼 있지 않다\n"
                         f"  근거 — {store.path(store.DOC_TYPES)}(키 없음)"
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


def _cmd_generate_resume(doc_type, layer, samples, no_fewshot):
    """⓪ **이어하기**(`--resume`) — 기존 패키지로 초안만 다시 받는다. 여기서 끝난다."""
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
    print(f"  {gateway.mode_line()}")
    print(f"■ ① 생성 (이어하기) — {doc_type} · 기존 패키지 재사용")
    # **옛 패키지의 인라인 전문을 로그로 옮긴다**(B62 ②) — 로드 시 한 번.
    _mv = ivlog.migrate_rounds(doc_type, pkg)
    if _mv:
        print(_mv)
        pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    _wn = ivlog.warn_no_decisions(doc_type, pkg)
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
        _bs = ivlog._hint_batches(_r)
        _lg = ivlog.read_log(doc_type)
        print(f"   문답 묶음 {len(_bs)}개 · 확정 사항 "
              f"{sum(len(b.get('decisions') or []) for b in _bs)}항목 "
              f"(라운드 전문 "
              f"{sum(len(_lg.get(b.get('at')) or []) for b in _bs)}건은 "
              f"{ivlog.INTERVIEW_LOG})")
    # **이어하기는 코드가 아니라 판단을 이어받는다**(B67 ①).
    #
    # 구판은 `draft_mod.draft(doc_type)`를 지시·이력 **없이** 불렀다. 생성은
    # `CHAT_TEMPERATURE=0`이면 같은 입력이 같은 코드를 낸다(기본은 모델 몫 — B80 ①).
    # 그래서 사내에서 G31(`AttributeError`)로 끝난 등록을 이어가자 **같은 G31**이 났다 —
    # 이어하기가 재생성이 아니라 **재현**이었다. 초안이 이미 있으면:
    #   ① 관문을 먼저 돌린다(B60 ① — 저장 판정을 믿지 않는다 · LLM 0)
    #   ② FAIL이면 그 판정 문면과 지시 이력을 재생성 지시로 **싣는다**
    #   ③ PASS면 초안을 다시 받지 않는다 — 통과한 것을 이유 없이 갈지 않는다
    print("   이어하기 = 같은 입력 + 지난 실패 · 처음부터 = --resume 없이")
    st = _state(doc_type) or {}
    st.setdefault("samples", pkg["human"]["samples"])
    _prior = draft_mod._at(st["adapter"]) if st.get("adapter") else None
    _instruction = None
    if _prior and _prior.exists() and st.get("schema"):
        if gate.regate(doc_type, st) == "PASS":
            print("   [이어하기] 지난 초안이 관문 PASS — 초안을 다시 받지 "
                  "않는다 (LLM 호출 0). 갈 곳은 검수·확정이다")
            st = {**st, "doc_type": doc_type, "layer": pkg["human"]["layer"],
                  "samples": pkg["human"]["samples"], "hint": pkg["human"]["hint"]}
            _save_state(doc_type, st)
            return gate._finish_generate(doc_type, st, st["samples"], pkg)
        _fails = gate.fail_lines(st.get("harness_out") or "")
        _auto, _ask = gate.classify_failures(st.get("harness_out") or "")
        _instruction = "\n".join(_auto + _ask)
        print(f"   [이어하기] 지난 초안 관문 FAIL {len(_fails)}건"
              f"({' · '.join(c for c, _l, _d in _fails) or '판정 줄 없음'})을 "
              f"지시로 싣는다 · 지시 이력 {len(st.get('instructions') or [])}건")
    if _instruction:
        st["revision"] = st.get("revision", 0) + 1
        st.setdefault("instructions", []).append(
            {"n": st["revision"], "instruction": _instruction,
             "at": store._now(), "by": "자동(이어하기 — 지난 관문 판정)"})
        ad, sc = draft_mod.draft(doc_type, st["revision"], instruction=_instruction,
                       history=st.get("instructions"))
    else:
        ad, sc = draft_mod.draft(doc_type)
    if ad is None:
        _want = f"{doc_type}_rev{st['revision']}" if _instruction else doc_type
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "       # [상태]
                         f"'{_want}' 부재 (D-10). mock에 이 이름의 초안이 "
                         f"없다\n"
                         f"  ▶ 다음 줄 — 실호출로 돌린다:\n"
                         f"     python run.py llm-check\n"
                         f"     USE_MOCK=0 python -m cli.register generate "
                         f"{doc_type} --resume")
    print(f"   초안 수령: {draft_mod._rel(ad)} · {draft_mod._rel(sc)}")
    st = {**st, "doc_type": doc_type, "layer": pkg["human"]["layer"],
          "samples": pkg["human"]["samples"], "hint": pkg["human"]["hint"],
          "adapter": str(draft_mod._rel(ad)),
          "schema": str(draft_mod._rel(sc)),
          "revision": st.get("revision", 0),
          "instructions": st.get("instructions", [])}
    _save_state(doc_type, st)
    return gate._finish_generate(doc_type, st, st["samples"], pkg)


def _cmd_generate_guard(doc_type, layer, samples, revise):
    """① 전제 검사 — 이름 중복 · 표본 실재 · 층 실재. 막을 것만 막는다."""
    if registry.lookup(doc_type) and not revise:
        # **막다른 길만 말하지 않는다**(H27) — 구판은 여기서 끝이라, 어댑터를 고쳐
        # 다시 등록할 길이 아예 없었다. 두 경로가 있고 화면이 그것을 알려 준다.
        _docs = registry.ingested_docs(doc_type)
        raise SystemExit(                                                 # [상태]
            f"[생성] '{doc_type}'은 이미 등록돼 있다 "
            f"(근거 {store.path(store.DOC_TYPES)}). 두 길 중 하나를 고른다:\n"
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


def _cmd_generate_form(doc_type, layer, samples, hint, use_basic, no_basic, revise):
    """② 형태 판정과 고정 어댑터 권유 — **끝나면 `None`**, 고정 어댑터로 가면 그 결과.

    돌려주는 값이 `None`이 아니면 호출부는 그대로 돌려준다(그 길에서 등록이 끝난다).
    """
    if use_basic:
        # **제안이 서지 않는 표본에는 거부한다** — 조용히 LLM 생성으로 떨어지면 사람은
        # «기본 어댑터로 등록됐다»고 믿는다. 거부는 사유를 들고 멈춘다.
        proposal = draft_mod.basic_adapter_proposal(samples)
        if proposal is None:
            draft_mod._refuse_basic(doc_type, layer, samples)
        return _use_basic(doc_type, layer, samples, hint, proposal, revise)

    # **산문 포맷이면 고정 어댑터를 먼저 권한다**(B59 ③) — 그 길로 안 들어가게 하는
    # 것이 먼저다. 실측: 사내가 PPT 하나 넣으려고 LLM 생성으로 갔고, 관문 FAIL →
    # 막다른 길이었다. 고정 어댑터는 생성 LLM 0회이고 관문을 그냥 지난다.
    # **형태 판정을 화면에 올린다**(B65 ⑤ · C37) — 자동으로 섰든 아니든 신호·투표를
    # 보인다. 안 섰으면 **사람에게 묻는다**: 구판은 아무것도 묻지 않고 LLM 생성으로
    # 갔고(실측: xlsx 산문이 생성에 들어가 「공정 좌표가 무엇인가」를 되물었다),
    # 판정이 안 선 것은 **모른다는 뜻**이지 table이라는 뜻이 아니다.
    _flines, _judged = draft_mod.form_block(samples)
    for _ln in _flines:
        print(_ln)
    _by = "auto"
    if _judged and all(j.get("verdict") is None for j in _judged) \
            and not use_basic and not no_basic:
        _ans = draft_mod.ask_form(doc_type, layer, samples, _judged)
        _by = "human"
        for _j in _judged:
            _j["verdict"] = _ans
        if _ans == "prose":
            # **답이 곧 `--use-basic`이다** — 제안이 서지 않으면 그 플래그와 **같은
            # 거부**를 낸다(문면 한 자리). 조용히 LLM 생성으로 흘리지 않는다: 사람은
            # 「산문이라고 답했다」고 믿는데 LLM이 도는 것이 이 항목이 없애려는 상태다.
            _prop = draft_mod.basic_adapter_proposal(samples)
            draft_mod.save_form(doc_type, _judged, _by)
            if not _prop:
                draft_mod._refuse_basic(doc_type, layer, samples)
            return _use_basic(doc_type, layer, samples, hint, _prop, revise)
        else:
            no_basic = True          # 사람이 표라고 정했다 — 권유를 다시 하지 않는다
    draft_mod.save_form(doc_type, _judged, _by)

    if not no_basic:
        _prop = draft_mod.basic_adapter_proposal(samples)
        if _prop and draft_mod._all_prose(samples):
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
    return None


def _cmd_generate_package(doc_type, layer, samples, hint, no_fewshot,
                          interview, drop_interview):
    """③ 입력 패키지 — 사람 4 + 시스템 5를 세운다. 돌려주는 것은 `(pkg, 자리)`."""
    snap = store.read(store.SKELETON_LIST, {}).get(layer) or {}
    cfg = json.loads(paths.layers(layer, "config.json").read_text(encoding="utf-8"))
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
    prior = ivlog.prior_interview(d / "input_package.json")
    # **옛 패키지는 로드 시 한 번 옮긴다**(B62 ②) — 여기도 로드 경로다.
    if prior and any(b.get("rounds") for b in prior):
        _old_pkg = json.loads((d / "input_package.json").read_text(encoding="utf-8"))
        _mv = ivlog.migrate_rounds(doc_type, _old_pkg)
        if _mv:
            print(_mv)
            (d / "input_package.json").write_text(
                json.dumps(_old_pkg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            prior = ivlog.prior_interview(d / "input_package.json")
    if prior and drop_interview:
        _lg = ivlog.read_log(doc_type)
        print(f"   ⚠ 이전 문답 "
              f"{sum(len(_lg.get(b.get('at')) or []) for b in prior)}라운드를 "
              f"**버린다** (--drop-interview)")
    elif prior:
        if ivlog._keep_prior(prior, ivlog.read_log(doc_type)):
            kept = ivlog._age_rounds(prior, [str(x) for x in samples])
            pkg["human"]["hint"] = ivlog._merge_hint(pkg["human"]["hint"], kept)
        else:
            print("   → 이전 문답을 버리고 새로 시작한다")
    if not interview:
        # **문답을 열지 않는 실행에서만 말한다**(B62 ②ⓓ) — 바로 문답이 열리면
        # 「결정을 세워라」가 아니라 열리는 문답이 답이다.
        _wn = ivlog.warn_no_decisions(doc_type, pkg)
        if _wn:
            print(_wn)
    (d / "input_package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"  {gateway.mode_line()}")          # B42 ⑤ — 어느 갈래로 도는지 먼저
    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부)")
    print(f"   입력 패키지: 사람 4 + 시스템 5 → {(d / 'input_package.json').relative_to(ROOT)}")
    return pkg, d


def _cmd_generate_interview(doc_type, samples, hint, pkg, d, interview):
    """③-b 문답 — 패키지가 선 뒤에 돈다. 전문은 로그에, 확정은 패키지에 실린다."""
    if interview:
        # **문답은 패키지가 선 뒤다** — 문답의 입력이 그 패키지(표본 관찰 재료)다.
        # 끝나면 전문을 `human.hint`에 구조화해 다시 싣는다: 기록이 없으면 같은
        # 등록을 재현할 수 없다. **시스템 5키는 그대로다.**
        # **라운드마다 즉시 저장한다**(B43 ⑤) — 전 라운드가 끝나야 쓰면 중간에
        # 죽었을 때 전부 잃는다. 사람의 답은 다시 만들 수 없는 재료다.
        _batch = ivlog._new_batch([str(x) for x in samples])

        def _persist(rounds):
            # **전문은 로그, 판단은 패키지**(B62 ②) — 쓰는 자리에서 가른다.
            ivlog.write_rounds(doc_type, _batch["at"], _batch["samples"], rounds)
            pkg["human"]["hint"] = ivlog._merge_hint(
                pkg["human"]["hint"],
                [b for b in ivlog._hint_batches(pkg["human"]["hint"])
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
        ledger.apply_decisions_to_ledger(doc_type, _batch["decisions"])
        _persist(rounds)
        _log = ivlog.read_log(doc_type)
        _old = sum(len(_log.get(b.get("at")) or [])
                   for b in ivlog._hint_batches(pkg["human"]["hint"]) if b is not _batch)
        print(f"   문답 {len(rounds)}라운드 → {ivlog.log_path(doc_type).relative_to(ROOT)} · "
              f"확정 사항 {len(_batch['decisions'])}항목 → human.hint"
              + (f" (이전 {_old}라운드 유지)" if _old else ""))
    elif (hint or "").strip():
        # **문답 없이 힌트만** — 힌트 문장이 그대로 한 항목의 확정 사항이다. 자리는
        # 항상 있어야 하므로 여기서 묶음을 세운다(사람 4키는 그대로 — `hint` 안이다).
        _hb = ivlog._new_batch([str(x) for x in samples])
        _hb["decisions"] = ivlog.hint_only_decisions(hint)
        pkg["human"]["hint"] = ivlog._merge_hint(
            pkg["human"]["hint"], ivlog._hint_batches(pkg["human"]["hint"]) + [_hb])
        (d / "input_package.json").write_text(
            json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _cmd_generate_draft(doc_type, layer, samples, pkg, revise):
    """④ 초안 — LLM 생성 갈래. 상태를 쓰고 관문으로 넘긴다."""
    proposal = draft_mod.basic_adapter_proposal(samples)
    if proposal:
        print(f"   ▶ 기본 어댑터 적용 제안 — {proposal['reason']}")
        print(f"     {proposal['note']}")
    ad, sc = draft_mod.draft(doc_type)
    if ad is None:
        raise SystemExit(f"[생성] 초안을 얻지 못했다 — USE_MOCK fixture "           # [상태]
                         f"'{doc_type}' 부재 (D-10). 실물 경로는 생성 LLM 훅이다\n"
                         f"  ▶ 다음 줄 — 실호출로 돌린다:\n"
                         f"     python run.py llm-check\n"
                         f"     USE_MOCK=0 python -m cli.register generate "
                         f"{doc_type} --resume")
    print(f"   초안 수령: {draft_mod._rel(ad)} · {draft_mod._rel(sc)}")
    u = gateway.usage_total()
    if u["calls"]:
        print(f"   LLM 사용량 — 호출 {u['calls']:,}회 · 토큰 {u['total_tokens']:,}"
              f"(입력 {u['prompt_tokens']:,} · 출력 {u['completion_tokens']:,})"
              + (f" · **응답 잘림 {u['truncated']}회**" if u["truncated"] else ""))
    st = {"doc_type": doc_type, "layer": layer,
          "samples": [str(s) for s in samples],
          "hint": pkg["human"]["hint"],
          "adapter": str(draft_mod._rel(ad)),
          "schema": str(draft_mod._rel(sc)),
          "revision": 0, "instructions": [],
          "revise_of": doc_type if revise else None,   # **새 판인가**(H27)
          "basic_adapter_proposal": proposal}
    _save_state(doc_type, st)
    return gate._finish_generate(doc_type, st, samples, pkg)


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
        _cmd_generate_revise(doc_type, layer)
    if resume:
        return _cmd_generate_resume(doc_type, layer, samples, no_fewshot)
    _cmd_generate_guard(doc_type, layer, samples, revise)
    _r = _cmd_generate_form(doc_type, layer, samples, hint, use_basic, no_basic, revise)
    if _r is not None:
        return _r
    pkg, d = _cmd_generate_package(doc_type, layer, samples, hint, no_fewshot,
                                   interview, drop_interview)
    _cmd_generate_interview(doc_type, samples, hint, pkg, d, interview)
    return _cmd_generate_draft(doc_type, layer, samples, pkg, revise)



def _use_basic(doc_type, layer, samples, hint, proposal, revise=False):
    """② 기본 어댑터 수용 — **LLM 호출 0회**로 검수 자리에 정본 후보를 놓는다 (§6.4-5).

    어댑터는 코어의 `parser/adapters/basic_ppt.py`를 **위임하는 래퍼**다 — 복사하지
    않는다. 봉투 doc_type은 `ADAPTER["doc_type"]`에서 오므로(parser/pipeline) 이름만
    이 doc_type으로 바꾸고 임계·분할은 코어 어댑터 한 곳에 남긴다(D-111: 조정은 그 어댑터
    1곳의 개정이고 doc_type별로 갈리지 않는다 — §6.4-5). 매칭 스키마는 prose 계약대로
    `fields {}`다. **검수·승인 1회는 생략하지 않는다**(M4) — 다음은 `review`다.
    """
    u0 = gateway.usage_total()["calls"]          # 이 명령이 부른 횟수를 재려면 시작점이 필요하다
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
           if hasattr(draft_mod._ad_mod(mod), "level_report") else ""), encoding="utf-8")
    draft_mod._write_schema(sc, json.dumps(
        {"doc_type": doc_type, "schema_version": 1, "layer": layer,
         "payload_kind": "prose", "use_blocks": ["common_core", "process_coord"],
         "_note": "비정형 — role 매핑 표가 없다. 층 선언이 계약의 전부다(B1)",
         "fields": {}, "edges": []}, ensure_ascii=False))
    print(f"  {gateway.mode_line()}")
    print(f"■ ① 생성 — {doc_type} (층 {layer} · 표본 {len(samples)}부) — **기본 어댑터 경로**")
    print(f"   ▶ {proposal['reason']}")
    print(f"     {proposal['note']}")
    print(f"   어댑터(위임 래퍼) · 스키마: {ad.relative_to(ROOT)} · {sc.relative_to(ROOT)}")
    u = gateway.usage_total()
    print(f"   LLM 사용량 — 이 명령에서 호출 {u['calls'] - u0:,}회 "
          f"(기본 어댑터 — 생성 세션 없음 · 프로세스 누계 {u['calls']:,}회)")
    print(f"   다음: python -m cli.register review {doc_type}  (뷰 확인·승인 1회는 그대로다 — M4)")
    st = {"doc_type": doc_type, "layer": layer,
          "samples": [str(s) for s in samples],
          "hint": pkg["human"]["hint"],
          "adapter": str(draft_mod._rel(ad)),
          "schema": str(draft_mod._rel(sc)),
          "revision": 0, "instructions": [],
          "revise_of": doc_type if revise else None,   # **새 판인가**(H27)
          "basic_adapter_proposal": proposal, "use_basic": True}
    # **형태 판정 기록을 잃지 않는다**(B65 ⑤) — 이 자리가 상태를 새로 쓰므로,
    # 앞에서 남긴 `form`(판정 · 누가 정했나)을 이어 싣는다. 뷰·리허설이 읽는 값이다.
    _prev_form = (_state(doc_type) or {}).get("form")
    if _prev_form:
        st["form"] = _prev_form
    _save_state(doc_type, st)
    return gate._finish_generate(doc_type, st, samples, pkg)
