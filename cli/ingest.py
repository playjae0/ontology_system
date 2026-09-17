# -*- coding: utf-8 -*-
"""일괄 투입 — 파일 하나 또는 경로 하나로 **선택 → 파싱 → 인입**을 잇는다 (문서 6 §6.4 · B46).

  python run.py ingest-file <문서> [--doc-type X] [--dry-run] [--coord-llm off|<종수>]
                                  [--step] [--step-every N] [--narrow embed|overlap]
  python run.py ingest-dir  <경로> [--doc-type X] [--dry-run] [--coord-llm off|<종수>]
                                  [--narrow embed|overlap]

기존 `parse run`·`build`는 그대로다 — 이것은 그 **위**의 편의 명령이고 같은 코드를 부른다
(`cli.parse.run_parse` · `core.pipeline.run_document`).

**선택의 규칙**(B46 조건 셋):
  ① 무엇으로 골랐는지 화면과 인입 기록(`doc_registry.json`의 `routing`)에 남긴다.
  ② `--dry-run`은 선택 결과만 보이고 파싱·인입을 하지 않는다.
  ③ 유일 일치만 자동으로 간다 — **둘 이상·0건이면 사람에게 올리고 멈춘다**(미선택).
`--coord-llm`은 좌표 태깅에서 **묻는 표기 종수의 상한**이다(기본 100 · `off`면 0회).
행 수가 아니다 — 같은 표기를 여러 행이 써도 묻는 것은 한 번이다(B69 ①). 상한을 넘는
표기는 묻지 않고 목록 밖 그대로 둔다(인입의 `orphan_anchor`) — 배치는 멈추지 않는다.
`--doc-type`을 주면 스캔하지 않고 그것으로 본다(사람 지정 — 기본 경로). 비정형(pptx)은
헤더 지문이 없어 스캔 대상이 아니다 — 지정 없이 오면 미선택으로 남는다.

**문서 단위 독립**(C14의 연장) — 한 건의 실패가 나머지를 멈추지 않고, 끝에 성공·실패·
미선택 목록을 모아 보인다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from cli import scan as scan_mod
from cli._gate import require_live_or_allow    # mock 관문 (B48)
from cli.parse import COORD_CAP, coord_cap_of, run_parse
from core.llm import llm
from core.state import log, registry, store
from core.build.pipeline import finalize, run_document

ROOT = Path(__file__).resolve().parent.parent

# **진행 줄은 로그에도 남는다**(B75 ③ⓑ) — 화면을 놓치면 기록이 없다.
_LOG = log.get("cli.ingest")

# reader가 여는 포맷 — 그 밖은 「지원 밖」으로 목록에만 남긴다.
# **목록은 리더가 소유한다**(B53) — 여기에 복제하면 리더에 포맷을 더해도 투입이 막는다.
from parser.reader import GRID_EXT, PROSE_EXT, SUPPORTED   # noqa: E402,F401
from parser import form as form_mod, reader as reader_mod  # noqa: E402

OK, FAIL, SKIP = "성공", "실패", "미선택"


def _norm_path(p):
    """경로 비교용 정규화 — 상대/절대·`./`·심볼릭 링크 차이로 헛경고를 내지 않는다."""
    try:
        return str(Path(p).resolve())
    except OSError:
        return str(Path(p).absolute())


def doc_id_of(path):
    """**같은 문서는 항상 같은 doc_id** (재인입 계약) — 파일명 stem, 공백은 `_`.

    경로는 넣지 않는다 — 폴더를 옮겨도 같은 문서다(D-110). 대신 **다른 폴더의 같은
    이름은 같은 문서로 취급된다** — 그 경우 인입은 「개정」으로 돌고, 이 명령은 등록
    대장의 `source_path`가 다르면 화면에 경고한다.
    """
    return re.sub(r"\s+", "_", Path(path).stem.strip())


def form_of(doc):
    """형태 판정(table/prose) — **격자 포맷만**. `.pptx`·`.pdf`는 포맷이 prose를 함의한다.

    선택 근거(`basis`)에 실어 인입 기록으로 보낸다 — **기록이 이 기능의 절반이다**
    (문서 1 C37): 문턱 조정과 애매 구간 측정의 유일한 재료이고, 그 크기가 재어진
    뒤에야 LLM 보조를 검토한다.

    판정이 **선택을 바꾸지는 않는다** — doc_type이 정해지면 어댑터가 갈래를 이미
    말한다. 여기서 하는 일은 ①기록 ②그 둘이 어긋날 때 화면 경고다. 판정으로
    어댑터를 갈아 끼우면 사람이 지정한 doc_type이 조용히 무시된다.
    """
    p = Path(doc)
    if p.suffix.lower() not in GRID_EXT:
        return None
    try:
        return form_mod.judge(reader_mod.read(str(p)))
    except Exception as e:                       # 판정 실패가 인입을 막지 않는다
        return {"verdict": None, "auto": False, "signals": {},
                "why": f"형태 판정 불가 — {type(e).__name__}: {e}"}


def select(doc, doc_type=None, adapter_paths=None):
    """doc_type 선택 — 파싱하지 않는다. 결과 `status`는 chosen · ambiguous · none · unsupported.

    `basis`가 **선택 근거**다(B46 ①): 사람 지정이면 `by=human`, 스캔이면 `by=scan`과
    일치 내역(`header_labels` 완전 일치 — 누락 0·잉여 0)이 함께 실린다.
    """
    p = Path(doc)
    out = {"doc": str(p), "doc_id": doc_id_of(p), "doc_type": None, "adapter": None,
           "basis": None, "candidates": [], "reason": None}
    if p.suffix.lower() not in SUPPORTED:
        return {**out, "status": "unsupported",
                "reason": f"지원하지 않는 포맷 {p.suffix!r} — reader가 여는 것은 {SUPPORTED}"}
    if doc_type:
        if registry.schema_of(doc_type) is None:
            return {**out, "status": "none",
                    "reason": f"미등록 doc_type '{doc_type}' — 구축 모드(register) 대상이다"}
        # 어댑터 실물은 **지문 스캔과 같은 소재지**에서 찾는다(등록부 + 기본 소재지) —
        # 등록부만 보면 내장 doc_type(스키마만 싣고 어댑터는 mock 트랙)이 지정으로도 안 간다.
        found = {m.ADAPTER.get("doc_type"): f for f, m in scan_mod.adapters(adapter_paths)}
        if doc_type not in found:
            return {**out, "status": "none", "doc_type": doc_type,
                    "reason": f"'{doc_type}'의 어댑터 실물이 소재지에 없다 — "
                              f"`parse run <어댑터> …`로 직접 넣거나 register로 어댑터를 등록한다"}
        return {**out, "status": "chosen", "doc_type": doc_type,
                "adapter": Path(found[doc_type]),
                "basis": {"by": "human", "doc_type": doc_type,
                          "form": form_of(p)}}
    res = scan_mod.scan(p, adapter_paths)
    cands = res["candidates"]
    out["candidates"] = cands
    if len(cands) == 1:
        dt = cands[0]
        f, _mod = res["_mods"][dt]
        d = next(x for x in res["details"] if x["doc_type"] == dt)
        if registry.schema_of(dt) is None:
            return {**out, "status": "none", "doc_type": dt,
                    "reason": f"지문은 '{dt}'와 유일 일치지만 **등록부에 없다** — "
                              f"인입이 미등록 doc_type을 거부한다(B3). register로 확정하라"}
        rejected = [f"{x['doc_type']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
                    for x in res["details"] if x.get("eligible") and not x.get("candidate")]
        return {**out, "status": "chosen", "doc_type": dt, "adapter": Path(f),
                "basis": {"by": "scan", "doc_type": dt,
                          "match": f"header_labels 완전 일치 {d['matched']}/{d['declared']} "
                                   f"(누락 0 · 잉여 0)",
                          "rejected": rejected, "form": form_of(p)}}
    if len(cands) > 1:
        return {**out, "status": "ambiguous",
                "reason": f"지문이 {len(cands)}개 어댑터와 일치 {cands} — 사람이 --doc-type으로 고른다"}
    # **미선택은 네 갈래다**(B66 ② · B61 계약) — 구판은 한 문면(「대조할 정형
    # 어댑터가 없다」)이 서로 다른 넷을 덮었고, CSV가 대조조차 안 된 것(①)이 그
    # 문면으로 나와 사람은 **어댑터가 없다고 읽었다**. 재료는 이미 `scan()`이 낸다 —
    # 읽지 않던 키를 읽을 뿐이고 **새 계산 0**이다.
    if res.get("not_fingerprintable"):
        return {**out, "status": "none",
                "reason": f"비정형({res['not_fingerprintable']}) — 헤더 지문이 없다. "
                          f"다음: --doc-type <dt> 지정 투입"}
    if not res["details"]:
        return {**out, "status": "none",
                "reason": "대조할 어댑터 0건 — 소재지가 비었다. "
                          "다음: python -m cli.register generate <dt> <층> <문서>"}
    eligible = [x for x in res["details"] if x.get("eligible")]
    if not eligible:
        why = " · ".join(f"{x['doc_type']}: {x.get('note') or '자격 없음'}"
                         for x in res["details"])
        return {**out, "status": "none",
                "reason": f"자격 있는 어댑터 0건 — {why}. "
                          f"다음: --doc-type <dt> 또는 "
                          f"python -m cli.register generate <dt> --revise"}
    # 차이 내역은 **개수만** — 열 이름 전부를 문서마다 늘어놓으면 목록이 읽히지 않는다.
    # 자세한 내역은 `run.py scan <문서>`가 낸다(같은 대조).
    diffs = [f"{x['doc_type']}(누락 {len(x['missing'])}·잉여 {len(x['extra'])})"
             for x in eligible]
    return {**out, "status": "none",
            "reason": f"지문 일치 0건 — {' · '.join(diffs)} — "
                      f"상세: python run.py scan {p}"}


def _basis_line(sel):
    b = sel.get("basis") or {}
    if b.get("by") == "human":
        out = f"사람 지정 --doc-type {b['doc_type']}"
    elif b.get("by") == "scan":
        out = f"지문 스캔 유일 일치 → {b['doc_type']} · {b['match']}" + (
            f" · 불일치 {b['rejected']}" if b.get("rejected") else "")
    else:
        return "-"
    # **어느 파일이 골라졌나**(B66 ④) — 어댑터는 등록부(`adapters/<dt>.py`)를 먼저
    # 보고 없으면 내장 doc_type의 소재지를 본다. 화면이 그것을 말하지 않으면 사람은
    # 「mock 소재지가 뭐냐」를 묻게 된다(사내 실측) — 경로 한 조각이 답이다.
    if sel.get("adapter"):
        try:
            _p = Path(sel["adapter"]).resolve().relative_to(ROOT)
        except ValueError:
            _p = Path(sel["adapter"])
        out += f"  ← {_p}"
    return out + _form_line(b.get("form"))


def _form_line(f):
    """형태 판정의 화면 한 줄 — **신호값 다섯을 그대로** 싣는다(문서 1 C37).

    요약만 보이면 문턱이 왜 그렇게 갈렸는지 사람이 판단할 재료가 없다. 사람에게
    올라온 문서는 특히 그렇다 — 그가 보고 정할 것이 이 다섯 값이다.
    """
    if not f:
        return ""
    head = f["verdict"] or "**사람 판정 대상**"
    line = f"\n     형태 판정: {head} ({'자동' if f.get('auto') else '자동 아님'}) — {f['why']}"
    if f.get("signals"):
        line += "\n     신호값: " + " · ".join(
            f"{k}={f['signals'][k]}[{(f.get('votes') or {}).get(k, '?')[0]}]"
            for k in form_mod.SIGNALS if k in f["signals"])
    return line


# ── 인입 실패 화면 — 이유와 행이 **화면에** 뜬다 (B61 ③ · 칸 3.1 · C14) ────────
#
# 사람은 `ingest-file`을 치고 **화면을 본다** — 큐를 먼저 열지 않는다. 사유는 이미 큐
# payload에 있으므로 **같은 재료를 화면에도 찍는다**(두 자리에 두 사실이 아니라 한
# 재료의 두 표시다). 태그(`P##`)는 관문의 `G##`·골격의 `K##`과 같은 방식이고 **정본은
# 여기 한 자리**다 — 앞자리가 단이다: 2 어댑터/지문 · 3 계약(validator) · 4 구조 ·
# 5 인입 보류.

FAIL_TAGS = {"adapter_mismatch": "P21",        # 지문이 어긋났다 (양식 표류)
             "parse_failure": "P31",           # 계약 self-check — validator 결함
             "hierarchy_unresolved": "P41"}    # 구조 미확정 (평면 폴백)
HELD_TAG = "P51"                               # 인입 보류 — 중복·미등록·payload_kind


def fail_rows(failures):
    """`ParseResult.failures` → 화면 줄의 재료 `[{tag, kind, reason}]`.

    **결함 전건을 편다** — validator는 `detail.defects`에 여러 건을 담는다. 한 줄로
    합쳐 300자에서 자르면 두 번째 결함이 화면에서 사라지고, 사람은 하나를 고친 뒤
    같은 명령을 다시 쳐서 다음 것을 만난다(골격 ②와 같은 병).
    """
    rows = []
    for f in failures or []:
        tag = FAIL_TAGS.get(f.get("kind"), "P01")
        defects = ((f.get("detail") or {}).get("defects")) or []
        if defects:
            rows += [{"tag": tag, "kind": f["kind"], "reason": d} for d in defects]
        else:
            rows.append({"tag": tag, "kind": f.get("kind", "?"),
                         "reason": f.get("reason", "")})
    return rows


def fail_block(doc, doc_id, rows, *, doc_type=None, queued=0):
    """인입 실패 블록 — 화면 문면 한 자리."""
    out = [f"■ 인입 실패 — {Path(doc).name} (doc_id {doc_id})"]
    for r in rows:
        out.append(f"  [FAIL] {r['tag']}  {r['kind']} — {r['reason']}")
    if queued:
        out.append(f"  큐: parse_failure {queued}건 (같은 내용)")
    out.append("  ▶ 다음 줄:")
    out.append(f"     (문서를 고친 뒤)      python run.py ingest-file {doc}")
    out.append(f"     양식이 바뀐 거면:     python -m cli.register generate "
               f"{doc_type or '<doc_type>'} --revise")
    return "\n".join(out)


def _orphan_next(doc_id):
    """`orphan_anchor`가 있으면 **다음 줄**을 큐 줄 옆에 붙인다 (B72 ③).

    화면은 한 벌이다 — 문면의 자리는 `cli/platform.py::orphan_next_lines` 하나이고
    `platform queue orphan_anchor`가 같은 것을 낸다.
    """
    from cli.platform import orphan_next_lines
    items = [x for x in store.read(store.QUEUE, [])
             if x.get("kind") == "orphan_anchor"
             and (doc_id is None or x.get("doc_id") == doc_id)]
    for x in items[:1]:                  # 표기가 여럿이어도 처방은 하나다
        pl = x.get("payload") or {}
        print(f"   보류 {len(items)}표기 — 골격 밖 좌표는 드랍이 아니다"
              f"(alias가 생기면 다음 인입이 붙인다): "
              f"{[ (y.get('payload') or {}).get('key') for y in items[:3] ]}")
        print(orphan_next_lines(x))


# **단계 문면의 자리는 여기 하나다**(B72 ④ — `kit/`이 아니라 진입점 옆). 사람이
# 「무엇을 했고 다음이 무엇인지」를 읽고 멈출 수 있어야 한다: 지금은 자동화보다
# 이해가 먼저다(사용자). 순서는 실제 파이프라인의 순서와 같다.
STEPS = [
    ("선택", "어느 어댑터로 읽을지 정했다. 지문 스캔이 골랐으면 근거가, 사람이 "
             "지정했으면 그 사실이 위에 있다. 다음은 그 어댑터로 문서를 읽는다."),
    ("파싱", "어댑터가 문서를 조각(행·청크)으로 만들었다. 아직 그래프에 아무것도 "
             "쓰지 않았다 — 계약 JSON(parsed/)까지다. 다음은 좌표를 맞춘다."),
    ("좌표", "조각의 공정좌표를 골격 닫힌 목록과 맞췄다. 목록 밖 표기는 고치지 않고 "
             "그대로 둔다 — 인입에서 보류(orphan_anchor)로 간다. 다음은 판정 예고다."),
    ("판정 예고", "개체 판정에 몇 번 부를지를 **부르기 전에** 센다. 사전이 이미 아는 "
                  "표기는 부르지 않는다. 여기서 멈추면 그래프에 쓴 것이 0이다."),
    ("판정", "표기마다 기존 노드와 같은 것인지 판정했다. 확신되면 잇고, 아니면 새 "
             "노드(auto)를 세운다. 다음은 값과 관계를 붙인다."),
    ("부착·엣지", "속성 값을 노드에 붙이고 관계 엣지를 세웠다. 좌표가 보류면 값도 "
                  "보류다(버리지 않는다). 카테고리쌍이 없는 관계는 게이트가 막는다."),
    ("큐·요약", "사람이 판정할 것을 큐에 남기고 한 줄로 요약했다. 큐는 문서 × "
                "표기/필드 단위 1건이다 — 행 수는 그 안에 있다."),
]


def _step_gate(i, detail=""):
    """한 단계를 찍고 `[계속 c / 멈춤 q]`를 묻는다 — 돌려주는 것은 계속 여부다.

    **비대화형이면 묻지 않는다**(`--step` 무시 · 한 줄로 그 사실을 말한다) —
    묻고 EOF를 받아 멈추면 일괄 실행이 전부 중단된다.
    """
    name, why = STEPS[i]
    print(f"\n── [{i + 1}/{len(STEPS)}] {name}" + (f" — {detail}" if detail else ""))
    print(f"   {why}")
    try:
        ans = input("   [계속 c / 멈춤 q] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return True
    if ans in ("q", "quit", "n"):
        print(f"   멈춤 — {name}까지의 산출은 남았다(parsed/ · extract/ 체크포인트).")
        print(f"   ▶ 다음 줄 — 이어서 넣는다: python run.py ingest-file <문서> "
              f"--doc-type <dt>")
        print(f"      고치고 넣는다: layers/<층>/skeleton.json alias · "
              f"schemas/<dt>.json 수정 뒤 같은 명령")
        return False
    return True


def judge_progress(total, stage=None, every=0):
    """판정 진행 줄 — 보폭마다 **새 줄로** 남긴다 (B73 ① · B75 ③ⓑ).

    2만 토큰을 쓰고 나서야 비용을 알았다는 것이 이 줄이 생긴 이유다. 좌표 태깅
    진행 줄(B69 ②)과 같은 자리·같은 결이다.

    **`\r` 덮어쓰기를 버렸다**(B75 ③ⓑ): 같은 줄을 덮으면 터미널 스크롤에도, 로그
    파일에도 남지 않는다 — 중단된 실행에서 「어디까지 얼마를 썼나」를 사후에 볼 수
    없었다(사내 실측 열넷째). 로그로도 같은 줄을 남긴다.

    `every`가 있으면 값 N개마다 **묻는다**(`--step-every`) — 비용이 쌓이는 단계는
    판정 하나뿐이라 멈춤 자리도 여기 하나다. `q`면 `Stopped`를 던지고, 그 문서는
    그래프·사전·큐 쓰기 0이다(되돌림은 `pipeline.run_document`가 한다).
    """
    def line(n, u):
        return (f"   [판정] 값 {n:,}/{total:,} · 호출 {n:,} · 누적 토큰 "
                f"{u.get('total_tokens', 0):,}"
                f"(입력 {u.get('prompt_tokens', 0):,} · 출력 "
                f"{u.get('completion_tokens', 0):,})")

    def progress(stats):
        n = stats.get("판정", 0)
        if stage is not None:
            stage["값"] = n
        u = llm.usage_total()
        stride = max(1, (total or 1) // 10)
        if n == 1 or n % stride == 0:
            print(line(n, u), flush=True)
            _LOG.info("판정 진행 — 값 %d/%d · 호출 %d · 누적 토큰 %d",
                      n, total or 0, n, u.get("total_tokens", 0))
        if every and n % every == 0 and n < (total or 0):
            _judge_gate(n, total, u)
    return progress


def _judge_gate(n, total, u):
    """판정 **안**의 멈춤 자리 (B75 ③ⓒ). 비대화형이면 묻지 않는다."""
    if not sys.stdin.isatty():
        return
    left = max(0, (total or 0) - n)
    print(f"   [판정] 값 {n:,}/{total:,} · 호출 {n:,} · 누적 토큰 "
          f"{u.get('total_tokens', 0):,} · 남은 값 {left:,}", flush=True)
    try:
        ans = input("   [계속 c / 멈춤 q] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if ans in ("q", "quit", "n"):
        from core.build.pipeline import Stopped
        raise Stopped(f"사람이 멈췄다 — 판정 값 {n}/{total} (그래프 쓰기 0 · "
                      f"체크포인트는 남는다)")


def build_screen(step=False):
    """인입 화면 — **판정 예고**와 **끝 요약 한 줄** (B72 ②).

    예고는 판정 **전에** 무LLM으로 센 수다(B22·B69와 같은 규율): 「표기 k종 중
    사전이 h종을 이미 안다 → 최대 k−h회」. 요약은 그래프·큐의 **실물 수**다 —
    화면이 제 계산을 하지 않는다.

    큐는 **집계 단위**로 말한다(B72 ②): `unknown_field 1종(meta 118행)`. 행마다
    한 건이면 사람이 판정할 하나가 118건 밑에 묻힌다.
    """
    def notice(info):
        if info.get("단계") == "판정예고":
            if step:
                return          # 단계 모드에서는 4단계가 이미 같은 수를 찍었다
            print(f"   판정 예고 — entity 값 {info['값_수']:,}건"
                  f"(표기 {info['표기_종수']:,}종 · 사전 히트 "
                  f"{info['사전_히트']:,}건) · 목록 밖 좌표 "
                  f"{info['목록밖_좌표']:,}표기 → LLM ≤ {info['예상_호출']:,}회")
            return
        q = info.get("큐") or {}
        head = " · ".join(f"{k} {n}종({rows}행)" for k, (n, rows) in sorted(q.items()))
        j = info.get("판정") or {}
        if j.get("조립"):
            # **어떻게 좁혔나를 화면이 말한다**(B73 ①) — 후보가 전량이던 시절의
            # 비용은 화면 어디에도 없었다.
            from core.matcher import CANDIDATE_TOP_N
            # **좁힘을 갈라 적는다**(B75 ①) — 임베딩으로 골랐는지 겹침으로 골랐는지가
            # 같은 문서를 두 설정으로 넣어 견줄 때의 유일한 표지다.
            # `스코프로 끝`은 **판정 없이** 끝난 수다(B75 ② — 같은 부모 아래 0개).
            print(f"   판정 — 호출 {j.get('판정', 0):,} · 사전 {j.get('사전', 0):,} · "
                  f"스코프로 끝 {j.get('스코프끝', 0):,} · "
                  f"좁힘 — 임베딩 {j.get('임베딩', 0):,} · 겹침 {j.get('겹침', 0):,} · "
                  f"후보 평균 {j['후보합'] / max(1, j['조립']):.1f}"
                  f"(상한 {CANDIDATE_TOP_N})")
        if step:
            u2 = llm.usage_total()
            _step_gate(4, f"새 노드(auto) {info.get('auto', 0)} · "
                          f"LLM 호출 {u2['calls']:,}")
            _step_gate(5, f"엣지 +{info.get('엣지', 0)} · 저해상도 부착 "
                          f"{info.get('저해상도', 0)}행")
            _step_gate(6, head or "큐 0")
        _orphan_next(info.get("doc_id"))
        u = llm.usage_total()
        print(f"   인입 끝 — 노드 +{info.get('노드', 0):,}"
              f"(auto {info.get('auto', 0):,}) · 엣지 +{info.get('엣지', 0):,} · "
              f"저해상도 부착 {info.get('저해상도', 0):,}행"
              + (f" · 큐: {head}" if head else " · 큐 0")
              + f" · LLM 호출 {u['calls']:,} · 토큰 "
              f"{u.get('total_tokens', 0):,}")
    return notice


def narrow_notice():
    """후보 좁히기가 **무엇으로** 도는지 — 임베딩이 없어도 인입은 선다(B75 ①).

    사내 실측 열넷째: 임베딩 모델 미설정이 인입을 통째로 세웠다. 이제 겹침으로
    떨어지되 **그 사실을 말한다** — 말하지 않으면 같은 문서의 두 산출이 왜 다른지
    사람이 모른다.
    """
    mode, why = llm.narrow_choice()
    if why == "미설정":
        print("   임베딩 미설정 — 겹침으로 좁힌다(--narrow embed로 강제 가능)")
    elif why == "플래그":
        print(f"   후보 좁히기 — {mode} (플래그가 설정을 이긴다)")


def ingest_file(doc, doc_type=None, dry_run=False, adapter_paths=None,
                finalize_after=True, coord_cap=COORD_CAP, step=False,
                step_every=0):
    """문서 1건 — 선택 → 파싱 → 인입. 돌려주는 것은 결과 1행(dict)이다. **예외를 밖으로
    던지지 않는다** — 문서 단위 독립(C14)이라 실패는 행에 적힌다."""
    sel = select(doc, doc_type, adapter_paths)
    row = {"doc": str(doc), "doc_id": sel["doc_id"], "doc_type": sel.get("doc_type"),
           "basis": _basis_line(sel), "status": SKIP, "reason": sel.get("reason")}
    # **어디까지 갔는지**를 들고 다닌다(B75 ③ⓐ) — 실패 줄이 그것을 말한다.
    stage = {"이름": "선택", "값": 0, "총": 0}
    print(f"[투입] {Path(doc).name} → doc_id {sel['doc_id']}")
    narrow_notice()
    if sel["status"] != "chosen":
        print(f"   미선택 — {sel['reason']}")
        return row
    print(f"   선택 근거: {row['basis']}")
    # **`--step`은 대화형에서만 산다**(B72 ④) — 비대화형·일괄에서 묻고 EOF를 받으면
    # 실행 전체가 첫 단계에서 멈춘다. 무시하되 **그 사실을 말한다.**
    if step and not sys.stdin.isatty():
        print("   (--step 무시 — 비대화형이다. 단계별로 보려면 터미널에서 돌린다)")
        step = False
    if step and not _step_gate(0, row["basis"]):
        row.update(status=SKIP, reason="사람이 멈췄다 — 선택까지")
        return row
    # **판정과 어댑터가 어긋나면 말한다** — 조용히 넘기면 관리계획서가 산문으로,
    # 목차 보고서가 표로 읽히고 그 사실이 어디에도 남지 않는다. 막지는 않는다:
    # 사람이 지정한 doc_type을 판정이 뒤집으면 지정이 무의미해진다(C37은 「어느
    # 갈래로 읽는가」를 정할 뿐 「사람의 지정을 이긴다」고 하지 않는다).
    _f = (sel.get("basis") or {}).get("form") or {}
    _kind = (registry.schema_of(sel["doc_type"]) or {}).get("payload_kind")
    if _f.get("verdict") and _kind and _f["verdict"] != _kind:
        print(f"   ⚠ 형태 판정({_f['verdict']})과 어댑터의 payload_kind({_kind})가 "
              f"어긋난다 — 지정대로 진행하되 이 사실이 인입 기록에 남는다")
    prev = store.read(store.DOC_REGISTRY, {}).get(sel["doc_id"])
    # **경로 전체를 비교한다**(B55 ⑧). 구판은 **파일명**을 비교했는데 doc_id가
    # 파일명 stem 파생이라(D-110) 같은 doc_id면 파일명이 항상 같다 — 조건이 참이 될
    # 수 없어, 「다른 폴더의 같은 이름」이라는 D-110의 **대가**가 화면에 뜬 적이 없다.
    if prev and prev.get("source_path") and _norm_path(prev["source_path"]) != _norm_path(doc):
        print(f"   ⚠ 같은 doc_id가 다른 경로에서 인입된 적 있다({prev['source_path']}) — "
              f"개정(재인입)으로 취급된다(D-110)")
    if dry_run:
        row["status"] = "선택만"
        print("   (dry-run — 파싱·인입 안 함)")
        return row
    try:
        stage["이름"] = "파싱"
        res, out = run_parse(str(sel["adapter"]), sel["doc_id"], str(doc),
                             coord_cap=coord_cap)
        if not res.ok:
            rows = fail_rows(res.failures)
            # **큐에도 싣는다**(C14 — 문서 단위 실패는 큐로 드러난다). 구판은 이
            # 경로에서 화면에만 한 줄 찍고 큐가 비어 있었다: 「화면을 놓치면 기록이
            # 없다」가 되어, 일괄 투입에서 실패가 조용히 지나갔다.
            store.enqueue("parse_failure", "; ".join(r["reason"] for r in rows)[:300],
                          sel["doc_id"], {"doc_type": sel.get("doc_type"),
                                          "source_path": str(doc),
                                          "defects": [r["reason"] for r in rows]})
            row.update(status=FAIL, reason="파싱 실패 — " + "; ".join(
                f"[{r['kind']}] {r['reason']}" for r in rows)[:300])
            print(fail_block(doc, sel["doc_id"], rows,
                             doc_type=sel.get("doc_type"), queued=1))
            return row
        if step:
            _rep = res.report or {}
            if not _step_gate(1, f"조각 {_rep.get('pieces', len(res.envelope.get('records') or res.envelope.get('chunks') or []))}건 · "
                              f"{res.envelope.get('payload_kind')}"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 파싱까지")
                return row
            _ct = _rep.get("coord_tag") or {}
            if not _step_gate(2, f"정확 일치 {_ct.get('정확_일치', 0)} · "
                              f"목록 밖 표기 {_ct.get('표기_종수', 0)}종 · "
                              f"LLM 호출 {_ct.get('호출', 0)}"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 좌표까지")
                return row
            # **판정 예고에서 멈추면 그래프에 쓴 것이 0이다** — 그 자리가 이 단계다.
            from core.build.pipeline import _entity_surfaces, decision_plan
            _sc = registry.schema_of(sel["doc_type"]) or {}
            _pl = decision_plan(
                _entity_surfaces(res.envelope, _sc),
                [x.get("process_ref") for x in (res.envelope.get("records") or [])
                 if x.get("process_ref")], _sc.get("layer") or "process")
            if not _step_gate(3, f"값 {_pl['값_수']}건 · 표기 {_pl['표기_종수']}종 "
                              f"· 사전 히트 {_pl['사전_히트']}건 → LLM ≤ "
                              f"{_pl['예상_호출']}회"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 판정 예고까지 "
                                               "(그래프 쓰기 0)")
                return row
        _u0 = llm.usage_total()["calls"]
        from core import matcher as _mt
        _plan_n = len((res.envelope.get("records") or [])) * 2 or 1
        stage["이름"], stage["총"] = "판정", _plan_n
        _mt.PROGRESS = judge_progress(_plan_n, stage=stage, every=step_every)
        try:
            r, m, _extracted = run_document(res.envelope, routing=sel["basis"],
                                            notice=build_screen(step=step))
        finally:
            _mt.PROGRESS = None
        if r.status == "held":
            # **단계를 올리지 않는다** — 판정에서 멈춘 것을 「부착까지 갔다」고
            # 적으면 비용 줄이 거짓말을 한다.
            row.update(status=FAIL, reason=f"보류 — {r.reason}")
            print("   " + spend_line(stage))
            print(fail_block(doc, sel["doc_id"],
                             [{"tag": HELD_TAG, "kind": "인입 보류", "reason": r.reason}],
                             doc_type=sel.get("doc_type"), queued=1))
            return row
        stage["이름"] = "부착"
        # **추출을 다시 돌렸나**를 말한다 — 등록 검수의 리허설이 남긴 체크포인트를
        # 운영이 재사용하면 LLM 호출이 0회다(B51). 그 사실이 화면에 없으면 「리허설과
        # 운영이 같은 함수」가 지켜졌는지 사람이 볼 수 없다.
        row.update(status=OK, reason=f"record {len(r.record_ids)} · chunk {len(r.chunk_ids)}"
                   + (f" · 그래프 노드 {m['nodes']}" if m else "")
                   + ("  [추출 실행]" if _extracted else "  [추출 체크포인트 재사용]"))
        print(f"   인입 — {row['reason']} → {out}")
        if finalize_after:
            finalize()
        return row
    except Exception as e:                       # 문서 단위 독립 — 나머지를 멈추지 않는다
        # **같은 경계다**(B76 ③) — 한 줄에 **파일:줄**이 있고 traceback은
        # `defects.log`로 간다. 여기는 이미 한 줄이었지만 자리를 말하지 않았다.
        _line = log.defect(e, stage=f"단계 {stage.get('이름', '?')}",
                           extra=f"doc_id {sel['doc_id']}")
        row.update(status=FAIL, reason=f"{type(e).__name__}: {e}"[:300])
        print("   " + _line)
        # **비용은 실패해도 보인다**(B75 ③ⓐ) — 사내 실측 열넷째는 첫 판정 호출
        # 전에 서서 진행 줄도 토큰 줄도 없이 끝났다. 무엇을 썼는지 모르면
        # 「다시 돌려도 되나」를 판단할 재료가 없다.
        print("   " + spend_line(stage))
        return row


def spend_line(stage):
    """`이 문서까지 — LLM 호출 k · 토큰 t(…) · 멈춘 단계 …` (B75 ③ⓐ).

    수는 `llm.usage_total()` 그대로다 — 화면이 제 계산을 하지 않는다.
    """
    u = llm.usage_total()
    where = stage.get("이름", "선택")
    if where == "판정" and stage.get("총"):
        where = f"판정 값 {stage.get('값', 0)}/{stage['총']}"
    return (f"이 문서까지 — LLM 호출 {u['calls']:,} · 토큰 "
            f"{u.get('total_tokens', 0):,}(입력 {u.get('prompt_tokens', 0):,} · "
            f"출력 {u.get('completion_tokens', 0):,}) · 멈춘 단계 {where}")


def ingest_dir(path, doc_type=None, dry_run=False, adapter_paths=None,
               coord_cap=COORD_CAP):
    """경로의 문서를 **하위 폴더 없이** 순회한다(D-110 — 하위 폴더는 별도 투입).

    `--doc-type`을 주면 그 경로 전부를 그것으로 본다(비정형 폴더 단위 지정 — B46).
    """
    p = Path(path)
    if not p.is_dir():
        raise SystemExit(f"[투입] 경로가 아니다: {p} — "                          # [상태]
                         f"폴더가 아니거나 없다\n"
                         f"  ▶ 다음 줄 — 문서 한 건이면:\n"
                         f"     python run.py ingest-file {p}")
    files = sorted(x for x in p.iterdir() if x.is_file() and not x.name.startswith(("~", ".")))
    rows = []
    u0 = llm.usage_total()
    for f in files:
        rows.append(ingest_file(f, doc_type, dry_run, adapter_paths,
                                finalize_after=False, coord_cap=coord_cap))
    if not dry_run and any(r["status"] == OK for r in rows):
        finalize()                              # 빌드 말미 패스는 전 문서 뒤 1회
    print(summary(rows))
    if not dry_run:
        # **총계 한 줄**(B73 ①) — 문서마다의 요약은 위에 있고, 배치의 비용은
        # 여기서만 보인다. 사람이 「이 폴더를 넣으면 얼마」를 알 자리다.
        u = llm.usage_total()
        print(f"  전체 — 문서 {len(rows):,} · LLM 호출 {u['calls'] - u0['calls']:,} · "
              f"토큰 {u.get('total_tokens', 0) - u0.get('total_tokens', 0):,}"
              f"(입력 {u.get('prompt_tokens', 0) - u0.get('prompt_tokens', 0):,})")
    return rows


def summary(rows):
    """끝에 모아 보이는 목록 — 성공 · 실패 · 미선택 (dry-run은 선택만)."""
    groups = {}
    for r in rows:
        groups.setdefault(r["status"], []).append(r)
    lines = [f"■ 일괄 투입 결과 — {len(rows)}건: " + " · ".join(
        f"{k} {len(v)}" for k, v in groups.items())]
    for k in (OK, "선택만", FAIL, SKIP):
        for r in groups.get(k, []):
            lines.append(f"  [{k}] {Path(r['doc']).name:<24} doc_id {r['doc_id']:<18} "
                         f"{('doc_type ' + r['doc_type']) if r.get('doc_type') else '':<20} "
                         f"{r.get('reason') or ''}")
    return "\n".join(lines)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit(__doc__)                                         # [사용법]
    args = require_live_or_allow(argv, command="ingest")   # mock 관문 (B48)
    dry = "--dry-run" in args
    if dry:
        args.remove("--dry-run")
    step = "--step" in args
    if step:
        args.remove("--step")
    # **판정 안에서 멈추는 자리**(B75 ③ⓒ) — `--step`과 독립이고 같이 줄 수 있다.
    step_every = 0
    if "--step-every" in args:
        i = args.index("--step-every")
        raw = args[i + 1] if i + 1 < len(args) else ""
        if not str(raw).isdigit() or int(raw) < 1:
            raise SystemExit("[투입] --step-every 뒤에 1 이상의 수가 필요하다")   # [사용법]
        step_every = int(raw)
        del args[i:i + 2]
    # **후보 좁히기 손잡이**(B75 ①) — 플래그가 설정을 이긴다(한 문서만 바꿔 비교).
    if "--narrow" in args:
        i = args.index("--narrow")
        mode = args[i + 1] if i + 1 < len(args) else ""
        if mode not in ("embed", "overlap", "auto"):
            raise SystemExit("[투입] --narrow는 embed|overlap|auto 중 하나다: "   # [사용법]
                             f"{mode!r}")
        llm.set_narrow(mode)
        del args[i:i + 2]
    dt = None
    if "--doc-type" in args:
        i = args.index("--doc-type")
        dt = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    paths = None
    if "--adapters" in args:
        i = args.index("--adapters")
        paths = [args[i + 1]] if i + 1 < len(args) else None
        del args[i:i + 2]
    # **상한 손잡이는 인입에도 있다**(B69 ③) — 배치라 동의 프롬프트를 두지 않는다.
    args, cap = coord_cap_of(args)
    if not args:
        raise SystemExit("[투입] 대상(문서 또는 경로)이 없다\n" + __doc__)             # [사용법]
    target = Path(args[0])
    if target.is_dir():
        if step:
            # **일괄에는 단계가 없다**(B72 ④) — 문서마다 멈추면 배치가 아니다.
            print("[투입] --step 무시 — ingest-dir는 일괄이다 "
                  "(단계별로 보려면 ingest-file 하나씩)")
        if step_every:
            print("[투입] --step-every 무시 — ingest-dir는 일괄이다 "
                  "(판정 안에서 멈추려면 ingest-file 하나씩)")
        rows = ingest_dir(target, dt, dry, paths, coord_cap=cap)
    else:
        rows = [ingest_file(target, dt, dry, paths, coord_cap=cap, step=step,
                            step_every=step_every)]
        print(summary(rows))
    return 0 if all(r["status"] in (OK, "선택만") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
