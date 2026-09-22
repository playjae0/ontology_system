# -*- coding: utf-8 -*-
"""칸 3.1 — 인입 **화면**: 값 줄 · 진행 줄 · 단계 예고 · 실패 블록 (B81 ①③④).

`cli/ingest.py`에서 떼어냈다(B82 — 855행). 가르는 선은 **흐름과 화면**이다:
저쪽은 「무엇을 어떤 순서로 부르나」이고 여기는 「그 결과를 사람에게 어떻게 보이나」다.
바뀌는 이유가 다르다 — 앞은 파이프라인이, 뒤는 사람이 읽는 방식이 바꾼다.

**화면은 대장의 투영이다**(B81 ①) — 값 줄의 재료는 판정 대장 행이고 여기서 새로
계산하지 않는다. 색은 특이점에만 붙는다(`cli/_screen.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path

from cli import _screen
from core import paths
from core.llm import gateway
from core.state import log, store

_LOG = log.get(__name__)

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
        print(f"      고치고 넣는다: {paths.layers('<층>', 'skeleton.json')} alias · "
              f"schemas/<dt>.json 수정 뒤 같은 명령")
        return False
    return True


# ── 값 줄 (B81 ①) ────────────────────────────────────────────────────────
#: verdict → 기호. **닫힌 표**이고 색은 특이점에만 붙는다(B81 ③ · `_screen.KINDS`).
MARKS = {"match": "✓", "attached": "✓", "new": "+", "uncertain": "?", "lowres": "?",
         "orphan": "✗", "gate_reject": "✗", "anchor": "·", "pending": "·"}

#: 경로 → 짧은 이름. 화면이 경로를 다시 해석하지 않는다(대장의 값 그대로).
PATH_SHORT = {"skeleton": "스코프", "dictionary": "사전", "scope+judge": "스코프",
              "embedding+judge": "임베딩", "overlap+judge": "겹침", "none": "—"}

#: 줄을 찍는 자리 — **판단이 갈린 값**이다(사용자 확정 2026-09-22).
LOUD_VERDICTS = ("new", "uncertain", "orphan", "lowres", "gate_reject")

#: 이번 문서의 집계 — 진행 줄이 이것을 함께 낸다(대장에서 센다 · 새 계산 0).
TALLY = {"값": 0, "사전": 0, "NEW": 0, "불확실": 0, "큐": 0, "orphan": 0}


def _loud(row):
    """이 행을 화면에 한 줄로 낼 것인가 — LLM이 든 경로거나 특이 verdict."""
    return (row.get("verdict") in LOUD_VERDICTS
            or (row.get("llm") or {}).get("calls", 0) > 0
            or "judge" in str(row.get("path") or ""))


def value_line(row):
    """대장 행 하나 → 화면 한 줄. **새 정보 0** — 행의 값을 그대로 옮긴다(B81 ①)."""
    v = row.get("verdict") or "pending"
    calls = (row.get("llm") or {}).get("calls", 0)
    n = row.get("candidates_n") or 0
    if calls:
        how = f"LLM · 후보 {n} · 확신 {row.get('confidence', 0):.2f}"
    else:
        how = f"후보 {n} ({PATH_SHORT.get(row.get('path'), row.get('path'))})"
    name = row.get("canonical") or row.get("surface") or "—"
    q = f"   → 큐 {row['queue_kind']}" if row.get("queue_kind") else ""
    text = f"    {MARKS.get(v, '·')} {name:<28} {v:<10} {how}{q}"
    return _screen.paint(text, v if v in _screen.KINDS else None)


def row_printer():
    """대장 행 콜백 — 집계하고, 판단이 갈린 값만 찍는다(`-v`면 전부)."""
    for k in TALLY:
        TALLY[k] = 0

    def on_row(row):
        TALLY["값"] += 1
        if row.get("path") == "dictionary":
            TALLY["사전"] += 1
        if row.get("verdict") == "new":
            TALLY["NEW"] += 1
        if row.get("verdict") in ("uncertain", "lowres"):
            TALLY["불확실"] += 1
        if row.get("verdict") == "orphan":
            TALLY["orphan"] += 1
        if row.get("queue_kind"):
            TALLY["큐"] += 1
        if _screen.VERBOSE or _loud(row):
            print(value_line(row), flush=True)
    return on_row


def judge_progress(total, stage=None, every=0, stride=None):
    """판정 진행 줄 — 보폭마다 **새 줄로** 남긴다 (B73 ① · B75 ③ⓑ · 보폭 B81 ④).

    보폭은 **값 N개마다**다(`--progress-every` · 설정 키 `PROGRESS_EVERY` · 기본 25).
    구판은 `total // 10`이라 문서가 크면 텀이 길고 작으면 매 값이었다 — 사람이
    기다리는 시간은 값 수에 비례하지 않는다(사내 실측 2026-09-22).


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
        # **누적에 대장 집계를 더한다**(B81 ④) — 사람이 알고 싶은 것은 토큰만이
        # 아니라 「몇이 붙고 몇이 새로 생겼나」다. 수는 대장에서 센 것 그대로다.
        return _screen.banner(
            f"   [판정] 값 {n:,}/{total:,} · 호출 {n:,} · 누적 토큰 "
            f"{u.get('total_tokens', 0):,}"
            f"(입력 {u.get('prompt_tokens', 0):,} · 출력 "
            f"{u.get('completion_tokens', 0):,})"
            f" · 사전 {TALLY['사전']:,} · NEW {TALLY['NEW']:,}"
            f" · 불확실 {TALLY['불확실']:,} · 큐 {TALLY['큐']:,}")

    step_n = max(1, int(stride or gateway.config().get("progress_every") or 25))

    def progress(stats):
        n = stats.get("판정", 0)
        if stage is not None:
            stage["값"] = n
        u = gateway.usage_total()
        if n == 1 or n % step_n == 0 or n == total:
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
        from core.build.entry import Stopped
        raise Stopped(f"사람이 멈췄다 — 판정 값 {n}/{total} (그래프 쓰기 0 · "
                      f"체크포인트는 남는다)")


