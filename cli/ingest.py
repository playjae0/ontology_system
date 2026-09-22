# -*- coding: utf-8 -*-
"""칸 3.1 — 일괄 투입 — 파일 하나 또는 경로 하나로 **선택 → 파싱 → 인입**을 잇는다 (문서 6 §6.4 · B46).

  python run.py ingest-file <문서> [--doc-type X] [--dry-run] [--coord-llm off|<종수>]
                                  [--step] [--step-every N] [--narrow embed|overlap]
                                  [--progress-every N] [-v] [--no-color]
  python run.py ingest-dir  [<경로>] [--doc-type X] [--dry-run] [--coord-llm off|<종수>]
                                  [--narrow embed|overlap] [--progress-every N]
                                  (경로를 생략하면 ⓪원본 자리 `<상태>/raw/` 전체)

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
from cli import _screen
from cli import ingest_screen as SCR
from core import paths
from core.llm import gateway, narrow
from core.state import log, registry, store
from core.build import ledger as _ledger
from core.build.entry import finalize, run_document

ROOT = Path(__file__).resolve().parent.parent

# **진행 줄은 로그에도 남는다**(B75 ③ⓑ) — 화면을 놓치면 기록이 없다.
_LOG = log.get("cli.ingest")

# reader가 여는 포맷 — 그 밖은 「지원 밖」으로 목록에만 남긴다.
# **목록은 리더가 소유한다**(B53) — 여기에 복제하면 리더에 포맷을 더해도 투입이 막는다.
from parser.reader import GRID_EXT, PROSE_EXT, SUPPORTED   # noqa: E402,F401
from parser import form as form_mod, reader as reader_mod  # noqa: E402

OK, FAIL, SKIP = "성공", "실패", "미선택"


def _norm_path(p):
    """경로 비교용 정규화 — 상대/절대·`./`·심볼릭 링크 차이로 헛경고를 내지 않는다.

    대장의 표기는 **상태 루트 기준 상대**일 수 있다(B79 ②) — 되돌려서 비교한다.
    그러지 않으면 이사 한 번에 「다른 경로에서 인입된 적 있다」가 전건 뜬다.
    """
    try:
        return str(paths.from_home(p).resolve())
    except OSError:
        return str(paths.from_home(p).absolute())


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
            u2 = gateway.usage_total()
            SCR._step_gate(4, f"새 노드(auto) {info.get('auto', 0)} · "
                          f"LLM 호출 {u2['calls']:,}")
            SCR._step_gate(5, f"엣지 +{info.get('엣지', 0)} · 저해상도 부착 "
                          f"{info.get('저해상도', 0)}행")
            SCR._step_gate(6, head or "큐 0")
        SCR._orphan_next(info.get("doc_id"))
        u = gateway.usage_total()
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
    mode, why = narrow.narrow_choice()
    if why == "미설정":
        print("   임베딩 미설정 — 겹침으로 좁힌다(--narrow embed로 강제 가능)")
    elif why == "플래그":
        print(f"   후보 좁히기 — {mode} (플래그가 설정을 이긴다)")


def _ingest_file_select(doc, sel, row, dry_run, step):
    """선택 판정과 그 앞 검사 — 형태 대조 · 경로 경고 · `--dry-run`.

    `ingest_file`에서 단계로 떼어냈다(B78 2c). 돌려주는 값이 `None`이 아니면
    호출부는 그 행을 그대로 돌려준다(여기서 끝난다). `step`은 **되돌려 준다** —
    비대화형이면 여기서 꺼지고, 그 사실이 호출부에도 반영돼야 한다.
    """
    stage = {"이름": "선택", "값": 0, "총": 0}
    print(f"[투입] {Path(doc).name} → doc_id {sel['doc_id']}")
    narrow_notice()
    if sel["status"] != "chosen":
        print(f"   미선택 — {sel['reason']}")
        return row, None, step
    print(f"   선택 근거: {row['basis']}")
    # **`--step`은 대화형에서만 산다**(B72 ④) — 비대화형·일괄에서 묻고 EOF를 받으면
    # 실행 전체가 첫 단계에서 멈춘다. 무시하되 **그 사실을 말한다.**
    if step and not sys.stdin.isatty():
        print("   (--step 무시 — 비대화형이다. 단계별로 보려면 터미널에서 돌린다)")
        step = False
    if step and not SCR._step_gate(0, row["basis"]):
        row.update(status=SKIP, reason="사람이 멈췄다 — 선택까지")
        return row, None, step
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
        return row, None, step
    return None, stage, step


def ingest_file(doc, doc_type=None, dry_run=False, adapter_paths=None,
                finalize_after=True, coord_cap=COORD_CAP, step=False,
                step_every=0, progress_every=None):
    """문서 1건 — 선택 → 파싱 → 인입. 돌려주는 것은 결과 1행(dict)이다. **예외를 밖으로
    던지지 않는다** — 문서 단위 독립(C14)이라 실패는 행에 적힌다."""
    sel = select(doc, doc_type, adapter_paths)
    row = {"doc": str(doc), "doc_id": sel["doc_id"], "doc_type": sel.get("doc_type"),
           "basis": _basis_line(sel), "status": SKIP, "reason": sel.get("reason")}
    # **어디까지 갔는지**를 들고 다닌다(B75 ③ⓐ) — 실패 줄이 그것을 말한다.
    _r, stage, step = _ingest_file_select(doc, sel, row, dry_run, step)
    if _r is not None:
        return _r
    try:
        stage["이름"] = "파싱"
        res, out = run_parse(str(sel["adapter"]), sel["doc_id"], str(doc),
                             coord_cap=coord_cap)
        if not res.ok:
            rows = SCR.fail_rows(res.failures)
            # **큐에도 싣는다**(C14 — 문서 단위 실패는 큐로 드러난다). 구판은 이
            # 경로에서 화면에만 한 줄 찍고 큐가 비어 있었다: 「화면을 놓치면 기록이
            # 없다」가 되어, 일괄 투입에서 실패가 조용히 지나갔다.
            store.enqueue("parse_failure", "; ".join(r["reason"] for r in rows)[:300],
                          sel["doc_id"], {"doc_type": sel.get("doc_type"),
                                          "source_path": str(doc),
                                          "defects": [r["reason"] for r in rows]})
            row.update(status=FAIL, reason="파싱 실패 — " + "; ".join(
                f"[{r['kind']}] {r['reason']}" for r in rows)[:300])
            print(SCR.fail_block(doc, sel["doc_id"], rows,
                             doc_type=sel.get("doc_type"), queued=1))
            return row
        if step:
            _rep = res.report or {}
            if not SCR._step_gate(1, f"조각 {_rep.get('pieces', len(res.envelope.get('records') or res.envelope.get('chunks') or []))}건 · "
                              f"{res.envelope.get('payload_kind')}"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 파싱까지")
                return row
            _ct = _rep.get("coord_tag") or {}
            if not SCR._step_gate(2, f"정확 일치 {_ct.get('정확_일치', 0)} · "
                              f"목록 밖 표기 {_ct.get('표기_종수', 0)}종 · "
                              f"LLM 호출 {_ct.get('호출', 0)}"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 좌표까지")
                return row
            # **판정 예고에서 멈추면 그래프에 쓴 것이 0이다** — 그 자리가 이 단계다.
            from core.build.entry import _entity_surfaces, decision_plan
            _sc = registry.schema_of(sel["doc_type"]) or {}
            _pl = decision_plan(
                _entity_surfaces(res.envelope, _sc),
                [x.get("process_ref") for x in (res.envelope.get("records") or [])
                 if x.get("process_ref")], _sc.get("layer") or "process")
            if not SCR._step_gate(3, f"값 {_pl['값_수']}건 · 표기 {_pl['표기_종수']}종 "
                              f"· 사전 히트 {_pl['사전_히트']}건 → LLM ≤ "
                              f"{_pl['예상_호출']}회"):
                row.update(status=SKIP, reason="사람이 멈췄다 — 판정 예고까지 "
                                               "(그래프 쓰기 0)")
                return row
        _u0 = gateway.usage_total()["calls"]
        from core import matcher as _mt
        _plan_n = len((res.envelope.get("records") or [])) * 2 or 1
        stage["이름"], stage["총"] = "판정", _plan_n
        _mt.PROGRESS = SCR.judge_progress(_plan_n, stage=stage, every=step_every,
                                      stride=progress_every)
        # **값 줄은 대장 행이 낸다**(B81 ①) — 화면은 대장의 투영이다.
        _ledger.ON_ROW = SCR.row_printer()
        try:
            r, m, _extracted = run_document(res.envelope, routing=sel["basis"],
                                            notice=build_screen(step=step))
        finally:
            _mt.PROGRESS = None
            _ledger.ON_ROW = None
        if r.status == "held":
            # **단계를 올리지 않는다** — 판정에서 멈춘 것을 「부착까지 갔다」고
            # 적으면 비용 줄이 거짓말을 한다.
            row.update(status=FAIL, reason=f"보류 — {r.reason}")
            print("   " + spend_line(stage))
            print(SCR.fail_block(doc, sel["doc_id"],
                             [{"tag": SCR.HELD_TAG, "kind": "인입 보류", "reason": r.reason}],
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

    수는 `gateway.usage_total()` 그대로다 — 화면이 제 계산을 하지 않는다.
    """
    u = gateway.usage_total()
    where = stage.get("이름", "선택")
    if where == "판정" and stage.get("총"):
        where = f"판정 값 {stage.get('값', 0)}/{stage['총']}"
    return (f"이 문서까지 — LLM 호출 {u['calls']:,} · 토큰 "
            f"{u.get('total_tokens', 0):,}(입력 {u.get('prompt_tokens', 0):,} · "
            f"출력 {u.get('completion_tokens', 0):,}) · 멈춘 단계 {where}")


def ingest_dir(path, doc_type=None, dry_run=False, adapter_paths=None,
               coord_cap=COORD_CAP, recurse=False, progress_every=None):
    """경로의 문서를 **하위 폴더 없이** 순회한다(D-110 — 하위 폴더는 별도 투입).

    `--doc-type`을 주면 그 경로 전부를 그것으로 본다(비정형 폴더 단위 지정 — B46).

    `recurse`는 **원본 자리(⓪)를 돌 때만** 참이다(B79 ②): 그 폴더는 사람이 제
    분류로 하위 폴더를 만들어 넣는 자리라 한 겹만 보면 대부분을 지나친다. 경로를
    직접 준 경우는 D-110 그대로다 — 사람이 적은 범위를 넓히지 않는다.
    """
    p = Path(path)
    if not p.is_dir():
        raise SystemExit(f"[투입] 경로가 아니다: {p} — "                          # [상태]
                         f"폴더가 아니거나 없다\n"
                         f"  ▶ 다음 줄 — 문서 한 건이면:\n"
                         f"     python run.py ingest-file {p}")
    _it = p.rglob("*") if recurse else p.iterdir()
    files = sorted(x for x in _it if x.is_file()
                   and not x.name.startswith(("~", "."))
                   and "__pycache__" not in x.parts)
    rows = []
    u0 = gateway.usage_total()
    for f in files:
        rows.append(ingest_file(f, doc_type, dry_run, adapter_paths,
                                finalize_after=False, coord_cap=coord_cap,
                                progress_every=progress_every))
    if not dry_run and any(r["status"] == OK for r in rows):
        finalize()                              # 빌드 말미 패스는 전 문서 뒤 1회
    print(summary(rows))
    if not dry_run:
        # **총계 한 줄**(B73 ①) — 문서마다의 요약은 위에 있고, 배치의 비용은
        # 여기서만 보인다. 사람이 「이 폴더를 넣으면 얼마」를 알 자리다.
        u = gateway.usage_total()
        print(_screen.banner(
            f"  전체 — 문서 {len(rows):,} · LLM 호출 {u['calls'] - u0['calls']:,} · "
            f"토큰 {u.get('total_tokens', 0) - u0.get('total_tokens', 0):,}"
            f"(입력 {u.get('prompt_tokens', 0) - u0.get('prompt_tokens', 0):,})"))
        if log.LOG_PATH:
            print(f"  로그 {log.LOG_PATH}  (INFO 전량 · 화면은 판단이 갈린 값만)")
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


def _is_doc(p):
    """파서가 읽는 포맷의 파일인가 — **기준은 `reader.SUPPORTED` 하나다**(B80 ②).

    ⓪원본 자리에는 사람이 자기 분류로 아무것이나 넣는다(메모·이미지·엑셀 임시파일).
    선별 기준을 여기서 새로 쓰면 파서가 여는 목록과 갈린다 — 그래서 그 목록을 묻는다.
    """
    return (p.is_file() and p.suffix.lower() in SUPPORTED
            and not p.name.startswith(("~", ".")))


def _raw_target():
    """인자 없는 `ingest-dir`의 대상 — ⓪원본 자리 (B80 ②).

    두 가지를 말한다. ①자리가 비면 **빈 배치로 조용히 끝내지 않는다** ②옛 이름
    (`docs/`)에 문서가 있으면 **상태 거부**다 — 이름이 `raw/`로 바뀐 것을 모르는
    사람에게 「0건」만 보여 주면 자기 문서가 왜 안 들어가는지 알 길이 없다.
    """
    raw = paths.raw()
    old = paths.legacy_raw()          # 옛 이름도 자리 소유자가 안다(B80 ②)
    if not raw.is_dir() or not any(_is_doc(p) for p in raw.rglob("*")):
        if old.is_dir() and any(_is_doc(p) for p in old.rglob("*")):
            raise SystemExit(                                             # [상태]
                f"[투입] 원본 자리가 `raw/`로 바뀌었다 — 옛 이름에 문서가 있다"
                f"(B80 ②)\n"
                f"  지금 잰 것 — {old} 문서 "
                f"{sum(1 for p in old.rglob('*') if _is_doc(p))}건 · "
                f"{raw} {'비어 있다' if raw.is_dir() else '없다'}\n"
                f"  근거 — 인자 없는 ingest-dir는 `<상태>/raw/`를 돈다"
                f"(`core/paths.raw()`) · 레포의 `docs/`는 명세 폴더라 이름이 갈렸다\n"
                f"  ▶ 다음 줄 — 옮기고 다시 돌린다:\n"
                f"     mv {old} {raw}\n"
                f"     python run.py ingest-dir")
        raise SystemExit(                                                 # [상태]
            f"[투입] 넣을 문서가 없다 — {raw}가 "
            f"{'비어 있다' if raw.is_dir() else '없다'}\n"
            f"  지금 잰 것 — 원본 자리(⓪) {raw} · 파서가 읽는 포맷 "
            f"{' '.join(SUPPORTED)}\n"
            f"  근거 — 인자 없는 ingest-dir는 원본 자리 전체를 돈다"
            f"(`core/paths.raw()`)\n"
            f"  ▶ 다음 줄 — 원본을 넣고 다시 돌린다:\n"
            f"     mkdir -p {raw} && cp <문서...> {raw}\n"
            f"     python run.py ingest-dir            (또는 경로를 직접 적는다)")
    return raw


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit(__doc__)                                         # [사용법]
    # 전역 화면 플래그 — `python -m cli.ingest`로 직접 부를 때의 자리(B81 ②③).
    # `run.py`가 이미 뗐으면 여기서는 아무것도 없다(같은 함수라 두 번 불러도 같다).
    argv, _ = _screen.take_flags(list(argv))
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
    # **진행 보폭 손잡이**(B81 ④) — 값 N개마다 진행 줄. 플래그가 설정을 이긴다.
    prog_every = None
    if "--progress-every" in args:
        i = args.index("--progress-every")
        raw = args[i + 1] if i + 1 < len(args) else ""
        if not str(raw).isdigit() or int(raw) < 1:
            raise SystemExit("[투입] --progress-every 뒤에 1 이상의 수가 "   # [사용법]
                             "필요하다 (기본 25 · 설정 키 PROGRESS_EVERY)")
        prog_every = int(raw)
        del args[i:i + 2]
    # **후보 좁히기 손잡이**(B75 ①) — 플래그가 설정을 이긴다(한 문서만 바꿔 비교).
    if "--narrow" in args:
        i = args.index("--narrow")
        mode = args[i + 1] if i + 1 < len(args) else ""
        if mode not in ("embed", "overlap", "auto"):
            raise SystemExit("[투입] --narrow는 embed|overlap|auto 중 하나다: "   # [사용법]
                             f"{mode!r}")
        narrow.set_narrow(mode)
        del args[i:i + 2]
    dt = None
    if "--doc-type" in args:
        i = args.index("--doc-type")
        dt = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    # 이름은 `adapter_paths`다 — `paths`로 두면 자리 소유자 모듈을 가린다(B79 ②).
    adapter_paths = None
    if "--adapters" in args:
        i = args.index("--adapters")
        adapter_paths = [args[i + 1]] if i + 1 < len(args) else None
        del args[i:i + 2]
    # **상한 손잡이는 인입에도 있다**(B69 ③) — 배치라 동의 프롬프트를 두지 않는다.
    args, cap = coord_cap_of(args)
    # **인자가 없으면 ⓪원본 폴더 전체다**(B79 ② · 자리 이름은 B80 ②) — 사람이
    # `<상태>/raw/`에 넣고 명령은 그 자리를 안다. 비어 있으면 그 사실을 말한다.
    if not args:
        args, _from_raw = [str(_raw_target())], True
    else:
        _from_raw = False
    target = Path(args[0])
    if target.is_dir():
        if step:
            # **일괄에는 단계가 없다**(B72 ④) — 문서마다 멈추면 배치가 아니다.
            print("[투입] --step 무시 — ingest-dir는 일괄이다 "
                  "(단계별로 보려면 ingest-file 하나씩)")
        if step_every:
            print("[투입] --step-every 무시 — ingest-dir는 일괄이다 "
                  "(판정 안에서 멈추려면 ingest-file 하나씩)")
        rows = ingest_dir(target, dt, dry, adapter_paths, coord_cap=cap,
                          recurse=_from_raw, progress_every=prog_every)
    else:
        rows = [ingest_file(target, dt, dry, adapter_paths, coord_cap=cap, step=step,
                            step_every=step_every, progress_every=prog_every)]
        print(summary(rows))
    return 0 if all(r["status"] in (OK, "선택만") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)