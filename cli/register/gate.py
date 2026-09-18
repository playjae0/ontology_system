# -*- coding: utf-8 -*-
"""칸 1.5 — **기계 관문**: 하네스 실행 · 실패 분류(AUTO_FIX·문답·GATE_SELF) · 화면."""

from __future__ import annotations

from cli.interview import (  # noqa: F401
    INTERVIEW_SCHEMA, INTERVIEW_STOP, _interview_round, _prof_hint, _interview,
    finalize as iv_finalize)
from cli.prompt import (  # noqa: F401
    KIT_NOTE, VOCAB_SECTIONS, _dir, _strip_kit_notes, _dump_prompt, _strip_module_doc,
    _reference_adapter, generate_template, _render_template, _vocab_excerpt, _sent_size)
from core.state import fixtures, log, registry, store
from parser import pipeline, preflight, profile, reader, tagger
from pathlib import Path
import json
import re
import subprocess
import sys
from cli.register import draft as draft_mod
from cli.register import interview as ivlog
from cli.register import ledger
from cli.register import view
from cli.register import KIT, REVIEW, ROOT, _load, _save_state, _state


# ================================================================ ② 검수
def harness(adapter, schema, samples, package=None, doc_type=None):
    """기계 관문 — **kit/run_adapter.py를 그대로 부른다**(재작성 아님).

    `package`는 입력 패키지 경로다(B64 ②) — 관문이 FAIL 줄에 **열 프로파일**을 실을
    때 쓴다. 관문은 계산하지 않는다: 그 값은 패키지 조립이 이미 전 행 스캔으로 냈다.

    `doc_type`이 오면 **열 판정 대장의 자리**도 넘긴다(B76 ② — G4G). 관문이 대장을
    만들지는 않는다: 읽고 커버리지만 판정한다.
    """
    pkg = ([("--package"), str(package)] if package and Path(package).exists() else [])
    led = ledger.ledger_path(doc_type) if doc_type else None
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

    import이 아니라 문면 추출인 이유: 킷은 **독립 실행 스크립트**라
    import하면 그 머리의 `sys.path` 조작과 `openpyxl` 지연 import가 여기로 끌려온다.
    뽑는 것은 상수 한 줄이고, 없으면 시끄럽게 실패한다(조용한 폴백을 두지 않는다).
    """
    src = (KIT / "gate_screen.py").read_text(encoding="utf-8")
    m = re.search(r'^LINE_RE = r"(.+)"$', src, re.M)
    if not m:
        raise SystemExit("[관문] kit/gate_screen.py의 LINE_RE를 찾지 못했다 — "    # [상태]
                         "판정 줄 문면 규격이 정본에서 사라졌다 (관문 자체 결함 — "
                         "어댑터 잘못이 아니다)\n"
                         "  ▶ 다음 줄 — 반입물이 온전한지 본다:\n"
                         "     python doctor.py")
    return m.group(1)


# 하네스 판정 줄의 문면 규격 — **정본은 `kit/gate_screen.py`의 `LINE_RE`다.**
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
# 프레임별 pick)을 한 줄 JSON으로 낸다(`kit/gate_screen.py::SPLIT_MARK`). 여기서
# 다시 파싱하면 같은 계산이 두 벌이 되고, 한쪽만 고쳐지는 날 화면이 갈린다.
def _kit_split_mark():
    """분할 요약 줄의 표시 — **킷에서 읽는다**(정본이 거기다 · `_kit_line_re`와 같은 결)."""
    m = re.search(r'^SPLIT_MARK = "(.+)"$',
                  (KIT / "gate_screen.py").read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("[관문] kit/gate_screen.py의 SPLIT_MARK를 찾지 못했다 — "  # [상태]
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
        prop = draft_mod.basic_adapter_proposal(samples)
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
        mod = _load(draft_mod._at(st["adapter"]), f"gate_{st['doc_type']}")
        schema = json.loads((draft_mod._at(st["schema"])).read_text(encoding="utf-8"))
        return ledger.unmappable_of(schema, mod)[2]
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
    batch = ivlog._new_batch([str(x) for x in (samples or [])])
    batch["context"] = "기계 관문 실패"

    def _persist(rounds, decisions=None):
        # **전문은 로그로**(B62 ②) — 패키지를 못 읽어도 전문은 남아야 한다.
        ivlog.write_rounds(doc_type, batch["at"], batch["samples"], rounds)
        try:
            obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() \
                else {"human": {"hint": {}}}
        except (OSError, json.JSONDecodeError):
            return                              # 패키지를 못 읽으면 조용히 지나간다
        if decisions is not None:
            batch["decisions"] = decisions      # 확정 요약(B60 ②) — 판단은 패키지에
        hint = (obj.get("human") or {}).get("hint")
        keep = [b for b in ivlog._hint_batches(hint) if b.get("at") != batch["at"]]
        obj.setdefault("human", {})["hint"] = ivlog._merge_hint(hint, keep + [batch])
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
        # **뷰를 만드는 함수는 하나다** — `view.cmd_review`를 그대로 부른다. 두 벌이면
        # 「생성이 보여 준 화면」과 「검수가 보여 주는 화면」이 갈리고, 사람이 승인한
        # 것이 어느 쪽인지 사후에 못 가린다.
        #
        # **여기서는 LLM을 켜지 않는다**(`llm_coord=False` · `extract=False`) —
        # 생성은 사람이 아직 아무것도 고르지 않은 자리이고, 비용 관문은 사람이
        # 켜는 것이다. 켜려면 `review`로 들어간다 — 그것이 그 명령이 남는 이유다.
        rc = view.cmd_review(doc_type, llm_coord=False, extract=False)
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
    path = draft_mod._at(st["adapter"])
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
        st["adapter"] = str(draft_mod._rel(path))
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
    blk = ledger.ledger_block(doc_type)
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
        ledger.sync_ledger(doc_type, st, samples)
        ok, out = harness(draft_mod._at(st["adapter"]), draft_mod._at(st["schema"]), samples,
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
        verdict = ledger.gate_verdict(ok, True, orphan)
        st["harness_out"] = out
        # 판정이 어느 열을 말하면 그 행이 미해결이다 — 대장만 보고 넘어가지 않게.
        ledger.mark_ledger_fails(doc_type, fail_lines(out))
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
        # `draft_mod.draft`가 같은 초안을 돌려줘 루프가 끝나지 않았다).
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
            ledger.apply_decisions_to_ledger(doc_type, _dec)
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
        ad, sc = draft_mod.draft(doc_type, st["revision"], instruction=instruction,
                       history=st.get("instructions"))
        if ad is None:
            print(f"   재생성 초안을 얻지 못했다 — "
                  f"fixture '{doc_type}_rev{st['revision']}' 없음")
            return _gate_done(doc_type, "FAIL")
        st["adapter"] = str(draft_mod._rel(ad))
        st["schema"] = str(draft_mod._rel(sc))
        print(f"   재생성 {st['revision']}회째 → {draft_mod._rel(ad)}")
