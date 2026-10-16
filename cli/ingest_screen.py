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
             "그대로 둔다 — 인입에서 보류(orphan_anchor)로 간다. 다음은 판정 예고다(산문은 추출 예고)."),
    ("판정 예고", "개체 판정에 몇 번 부를지를 **부르기 전에** 센다. 사전이 이미 아는 "
                  "표기는 부르지 않는다. 여기서 멈추면 그래프에 쓴 것이 0이다."),
    ("판정", "표기마다 기존 노드와 같은 것인지 판정했다. 확신되면 잇고, 아니면 새 "
             "노드(auto)를 세운다. 다음은 값과 관계를 붙인다."),
    ("부착·엣지", "속성 값을 노드에 붙이고 관계 엣지를 세웠다. 좌표가 보류면 값도 "
                  "보류다(버리지 않는다). 카테고리쌍이 없는 관계는 게이트가 막는다."),
    ("큐·요약", "사람이 판정할 것을 큐에 남기고 한 줄로 요약했다. 큐는 문서 × "
                "표기/필드 단위 1건이다 — 행 수는 그 안에 있다."),
    # 산문만 지나는 두 관문(B97 ④) — 표 문서의 「판정 예고」(3) 자리를 산문은 이 둘이 맡는다
    ("추출 예고", "청크마다 LLM이 개체·관계를 뽑는다 — 몇 청크를 부를지를 **부르기 전에** "
                  "센다(참조 시트·이미 끝난 청크는 부르지 않는다). 여기서 멈추면 LLM 0 · 그래프 쓰기 0이다."),
    ("추출 결과·판정 예고", "뽑힌 개체를 보고 판정에 몇 번 부를지를 센다. 여기서 멈추면 그래프 쓰기 "
                           "0이고 추출 체크포인트는 완료로 남는다 — 같은 명령을 다시 치면 추출 재사용(LLM 0)으로 구축만 간다."),
]
#: 관문의 순서 — 표는 판정 예고(3), 산문은 추출 예고(7) → 추출 결과·판정 예고(8)
TABLE_SEQ = (0, 1, 2, 3, 4, 5, 6)
PROSE_SEQ = (0, 1, 2, 7, 8, 4, 5, 6)


#: 단계 끝 줄의 기준점 — 머리를 낼 때마다 갱신한다(문서 머리에서 비운다).
_MARK = {"t": None, "u": None}


def stage_reset():
    """문서가 바뀌면 단계 시계를 다시 잡는다(`cli/ingest._doc_header`)."""
    import time
    _MARK.update(t=time.monotonic(), u=gateway.usage_total())


def _stage_end():
    """**단계 끝 줄**(B99 ④) — 앞 머리 이후 걸린 시간 · LLM 호출 · 입력/출력(게이트웨이 누계 차)."""
    import time
    if _MARK["t"] is None:
        stage_reset()
    u = gateway.usage_total()
    line = (f"   └ {time.monotonic() - _MARK['t']:.1f}초 · LLM 호출 "
            f"{u['calls'] - _MARK['u']['calls']:,} · {_screen.tokens(u, _MARK['u'])}")
    _MARK.update(t=time.monotonic(), u=u)
    return line


def stage_head(label, detail=""):
    """번호 없는 단계 머리(사전 점검 · 마무리) — 표·산문 순서표 앞뒤에 선다(B99 ④)."""
    _screen.close()
    _screen.say(f"── [{label}]" + (f" — {detail}" if detail else ""), "head")
    _screen.say(_stage_end(), "aux")


def _step_gate(i, detail="", prose=False, ask=True, body=None, saved=False):
    """**단계 머리**를 찍고(`--step`이 아니어도 — B99 ④) `ask`면 `[계속 c / 멈춤 q]`를 묻는다.

    머리 아래 **단계 끝 줄**(걸린 시간 · LLM 호출 · 입력/출력)이 붙는다 — `--step`은 같은 머리에
    묻기만 더한다(한 함수). 돌려주는 것은 계속 여부다. **비대화형이면 묻지 않는다** — 묻고 EOF를
    받아 멈추면 일괄 실행이 전부 중단된다. 번호는 표·산문 순서표(`TABLE_SEQ`·`PROSE_SEQ`)의 자리다.
    답은 묻는 한 자리(`_screen.answer` — 계속은 c(ㅊ)만 · 멈춤 q · ㅂ · Ctrl-C · 그 밖은 다시 묻는다 · B118 ④).
    `saved`면 **저장 표지 뒤**의 머리(판정 · 부착·엣지 · 큐) — 멈춤은 남은 머리를 묻지 않는 것뿐이다(되돌림 0 · B109 ②).
    """
    name, why = STEPS[i]
    seq = PROSE_SEQ if prose else TABLE_SEQ
    _screen.close()
    _screen.say(("\n" if ask else "") + f"── [{seq.index(i) + 1}/{len(seq)}] {name}"
                + (f" — {detail}" if detail else ""), "head")
    _screen.say(_stage_end(), "aux")
    for ln in body or []:                     # 머리 아래 표(청크 목차 — B112 ③) — 묻기 전에
        print(ln)
    if not ask:
        return True
    print(f"   {why}")
    if not _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True):
        if saved:                              # 저장 표지 뒤 — 끝난 문서다(B109 ②) · 되돌리지 않는다
            print(f"   멈춤 — 이 문서는 이미 저장됐다(되돌리지 않는다) · 남은 머리는 묻지 않는다")
            return False
        print(f"   멈춤 — {name}까지의 산출은 남았다(parsed/ · extract/ 체크포인트).")
        if i == 8:
            print("   ▶ 추출은 완료로 남았다 — 같은 명령을 다시 치면 추출 재사용(LLM 0)으로 구축만 간다")
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
              "embedding+judge": "임베딩", "overlap+judge": "겹침", "self_coord": "자기 좌표",
              "memo": "기억", "replay": "재생", "none": "—"}

#: 줄을 찍는 자리 — **판단이 갈린 값**이다(사용자 확정 2026-09-22).
LOUD_VERDICTS = ("new", "uncertain", "orphan", "lowres", "gate_reject", "mention")   # mention — 다른 공정 언급(B113 ①)

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
    # 표기 → **붙은 노드**(B102 ⑦ — 조회 키가 아니라 실제 노드 · 없으면 조회 이름)
    name = (f"{row.get('surface')} → {row['target']}"
            if row.get("target") and row.get("surface") and row["target"] != row["surface"]
            else (row.get("target") or row.get("canonical") or row.get("surface") or "—"))
    q = f"   → 큐 {row['queue_kind']}" if row.get("queue_kind") else ""
    if v == "mention":                                       # 다른 공정 이름 — 노드 0 · 관련 링크(B113 ①)
        return _screen.paint(f"    ↗ {row.get('surface')} → 관련 링크 {row.get('canonical')} "
                             f"(다른 공정 언급 — 노드 0)", None)
    text = f"    {MARKS.get(v, '·')} {name:<28} {v:<10} {how}{q}"
    return _screen.paint(text, v if v in _screen.KINDS else None)


def row_printer(env=None):
    """대장 행 콜백 — 집계하고, 판단이 갈린 값만 찍는다(`-v`면 전부)."""
    for k in TALLY:
        TALLY[k] = 0

    def on_edge(row, info):
        # 붙은 자리 한 줄(B102 ⑦) — 그 값이 찍힌 줄 아래 · 로그에는 자르지 않은 줄
        if _screen.VERBOSE or _loud(row) or info["path"] != "관계":
            ln = (f"     └ {row.get('surface') or row.get('canonical')} · {info['rel']} {info['dir']} "
                  f"{info['other']} ({info['path']})")
            _LOG.info("붙은 자리 %s", ln.strip())
            if _screen.VERBOSE or _loud(row):
                print(ln)
    from core.build import ledger as _lg
    _lg.ON_EDGE = on_edge

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
            lab = labels.get(row.get("locator"))          # 자르지 않은 줄 · 전체 경로는 명령 로그에(B118 ③)
            _LOG.info("값 %s%s", value_line(row).strip(), f" · 자리 {lab}" if lab else "")
            table.row(*value_cells(row, places))
    # 위치 두 칸의 재료(B118 ③) — 봉투의 조각마다 `(시트, 경로 끝)` · 대장 행의 위치로 찾는다(새 판정 0)
    from core.build import extract_ctx as _xc
    pieces = [c for c in ((env or {}).get("chunks") or []) + ((env or {}).get("records") or [])
              if c.get("source_locator")]
    places = {c["source_locator"]: _xc.place(c) for c in pieces}
    labels = {c["source_locator"]: _xc.chunk_label(c) for c in pieces}
    table = value_table(list(places.values()))
    return on_row


#: 위치 두 칸의 폭 상한(B118 ③ — 표가 시작될 때 봉투 · 목차의 가장 긴 것에 맞춘다 · 그보다 길면 이 폭에서 `…`)
PLACE_MAX = (24, 32)


def place_widths(places):
    """위치 두 칸 `(시트, 청크)`의 폭 — 이 문서의 가장 긴 것(머리글 폭 이상 · `PLACE_MAX` 이하)."""
    ws = [max([_screen.w(str(p[i])) for p in places or []] + [4]) for i in (0, 1)]
    return tuple(min(wd, cap) for wd, cap in zip(ws, PLACE_MAX))


def value_table(places=None):
    """판정 값 표(B98 ⑥) — 기호 · 시트 · 청크 · 표기 · 카테고리/열 · 판정 · 경로 · 확신 · 노드/큐."""
    # 고정 칸은 좁게(경로 · 큐는 `…`로 잘려도 대장·로그에 전부 있다) — 표기 칸이 남게 (B99 ⑦⑨) · 위치 두 칸은 이 문서 폭
    ws, wc = place_widths(places)
    return _screen.Table([("", 1, False), ("시트", ws, False), ("청크", wc, False), ("표기", 40, False),
                          ("카테고리/열", 10, False),
                          ("판정", 9, False), ("경로", 13, False), ("확신", 4, True),
                          ("임베딩", 5, True), ("노드/큐", 16, False)], flex=3, keep=(1, 2))


def where_cells(locator, places=None):
    """**위치 두 칸**(B118 ③) — `(시트, 청크 끝)`: 봉투의 그 조각이면 `extract_ctx.place` · 아니면 위치 `시트!행`을 가른다
    (표 문서의 행 위치). 가운데 경로는 생략 — 전체 경로는 명령 로그의 값 줄에 그대로."""
    loc = str(locator or "")
    if places and loc in places:
        return places[loc]
    sheet, _, rest = loc.rpartition("!")
    return (sheet, rest) if sheet else ("", loc)


def value_cells(row, places=None):
    """대장 행 하나 → 표의 칸(값 · 색 층). **새 정보 0** — 행의 값을 그대로 옮긴다(B81 ①)."""
    v = row.get("verdict") or "pending"
    calls = (row.get("llm") or {}).get("calls", 0)
    n = row.get("candidates_n") or 0
    how = (f"LLM · 후보 {n}" if calls
           else f"후보 {n} ({PATH_SHORT.get(row.get('path'), row.get('path'))})")
    conf = f"{row.get('confidence', 0):.2f}" if calls else ""
    # 표기 → **붙은 노드**(B102 ⑦ — 조회 키가 아니라 실제 노드 · 없으면 조회 이름)
    name = (f"{row.get('surface')} → {row['target']}"
            if row.get("target") and row.get("surface") and row["target"] != row["surface"]
            else (row.get("target") or row.get("canonical") or row.get("surface") or "—"))
    where = (f"→ 큐 {row['queue_kind']}" if row.get("queue_kind")
             else ("노드" if row.get("node_id") else ""))
    near = row.get("nearest") or {}
    if near.get("canonical"):                      # 불확실의 가장 가까운 후보 (B99 ⑨)
        where += f" · 가까움({near.get('by')}) {near['canonical']}"
    emb = f"{row['emb_top']:.2f}" if row.get("emb_top") is not None else ""
    k = v if v in _screen.KINDS else None
    if v in ("mention", "blank"):                  # 노드 0 — 표기 그대로 · 관련 링크 대상(B113 ①②)
        name, how = row.get("surface") or "—", ("다른 공정" if v == "mention" else "빈칸 표시")
        where = f"관련 링크 {row.get('canonical')}" if v == "mention" else "개체 0"
    # 위치 = 대장 행의 locator(산문이면 지금 청크 · 표면 행 — B99 ⑦)
    sheet, end = where_cells(row.get("locator"), places)
    return ([MARKS.get(v, "·"), sheet, end, name, row.get("field") or "", v, how,
             conf, emb, where], [k, "aux", "aux", k, "aux", k, "aux", "aux", "aux", "aux"])


def build_screen(step=False, stage=None, prose=False):
    """인입 화면 — **판정 예고**와 **끝 요약 한 줄** (B72 ②).

    예고는 판정 **전에** 무LLM으로 센 수다(B22·B69와 같은 규율): 「표기 k종 중
    사전이 h종을 이미 안다 → 최대 k−h회」. 요약은 그래프·큐의 **실물 수**다 —
    화면이 제 계산을 하지 않는다.

    큐는 **집계 단위**로 말한다(B72 ②): `unknown_field 1종(meta 118행)`. 행마다
    한 건이면 사람이 판정할 하나가 118건 밑에 묻힌다.
    """
    _ex = extract_screen(step=step, stage=stage)
    _judge = dict(stage or {})

    def notice(info):
        if str(info.get("단계", "")).startswith(("추출", "개요")):
            # 산문 추출 화면은 세 진입이 같은 함수다 (B97 ①②)
            out = _ex(info)
            if info["단계"] == "추출끝" and stage is not None:
                stage.update(_judge)              # 누적 줄·비용 줄이 다시 판정을 가리킨다
            return out
        if info.get("단계") == "렌즈예고":
            # **호출 전 예고**(B91 ①) — 렌즈가 둘 이상일 때만 온다 · 거름은 LLM 0 ·
            # 이 줄이 추출 예고의 자리다(B97 ① — 두 줄 0) · `--step`이면 여기서 묻는다
            head = (f"렌즈 {len(info['렌즈'])}({' · '.join(info['렌즈'])}) × 청크 "
                    f"{info['청크']:,} → 거름 뒤 LLM ≤ {info['호출']:,}회 "
                    f"(관련성 문턱 {info['문턱']} · 건너뜀 {info['거름']:,})")
            # 머리는 늘(B99 ④) — `--step`이면 묻는다
            return _step_gate(7, f"렌즈 예고 — {head}", prose=True, ask=step)
        if info.get("단계") == "렌즈상한":
            # **넘으면 묻는다** — 비대화형이면 멈춘다(조용한 절단 0 · 문서는 보류로 남는다)
            print(f"   렌즈 호출 상한 {info['상한']:,} 초과 — 예상 {info['호출']:,}회")
            if not sys.stdin.isatty():
                print("     비대화형이라 멈춘다 — 손잡이 lens_call_cap을 올리거나 렌즈를 줄인다 "
                      "(python run.py show knobs · python -m cli.register lenses <dt>)")
                return False
            return _screen.answer("     그래도 부를까? [y/N] ", "yes", eof=False)
        if info.get("단계") == "판정예고":
            lz = f"[{info['렌즈']}] " if info.get("렌즈") else ""
            body = (f"entity 값 {info['값_수']:,}건"
                    f"(표기 {info['표기_종수']:,}종 · 사전 히트 "
                    f"{info['사전_히트']:,}건) · 목록 밖 좌표 "
                    f"{info['목록밖_좌표']:,}표기 → LLM ≤ {info['예상_호출']:,}회")
            if info.get("추출뒤") and stage is not None:
                # 산문 판정의 총수 = 추출이 낸 개체 수(B99 ⑦ — 레코드 수가 아니다)
                stage.update({"이름": "판정", "값": 0, "총": info["값_수"], "t0": None})
                _judge.update(stage)
            if info.get("추출뒤"):
                # 산문은 **추출 뒤 단계 머리**가 이 줄이다(B97 ④ · 늘 — B99 ④) — `--step`이면 묻는다
                return _step_gate(8, lz + body, prose=True, ask=step)
            if step:
                return          # 표 문서 — 관문 3(판정 예고)이 이미 같은 수를 찍었다
            _screen.say(f"   판정 예고 {lz}— {body}", "head")
            return
        _screen.close()                              # 끝 요약 앞에서 값 표를 닫는다 (B98 ⑥)
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
        rp = info.get("재생") or {}
        if any(rp.values()):
            # **판정 재생**(B106 ②) — 지난 대장으로 붙인 값과 다시 판정한 값(사유별)
            print(f"   판정 재생 — 재생 {rp.get('재생', 0):,} · 재판정 {rp.get('재판정', 0):,}(키 없음 "
                  f"{rp.get('키 없음', 0):,} · 대상 없음 {rp.get('대상 없음', 0):,} · 끔 {rp.get('끔', 0):,})")
        # 결과만 보이는 세 머리(판정 · 부착·엣지 · 큐) — 늘 낸다(B99 ④) · `--step`이면 묻는다
        u2 = gateway.usage_total()
        # 이 셋은 **저장 뒤**다(B109 ② — 멈춰도 되돌리지 않는다): 멈추면 남은 머리는 묻지 않고 내기만 한다(B118 ④)
        go = _step_gate(4, prose=prose, ask=step, saved=True, detail=f"새 노드(auto) {info.get('auto', 0)} · "
                        f"LLM 호출 {u2['calls']:,}")
        _hf = f" · 제목 개체 폴백 {info['제목폴백']:,}행" if info.get("제목폴백") else ""   # 상위 사슬 (B115 ③)
        go = _step_gate(5, prose=prose, ask=step and go, saved=True, detail=f"엣지 +{info.get('엣지', 0)} · "
                        f"저해상도 부착 {info.get('저해상도', 0)}행{_hf}") and go
        _step_gate(6, head or "큐 0", prose=prose, ask=step and go, saved=True)
        _orphan_next(info.get("doc_id"))
        u = gateway.usage_total()
        print(f"   인입 끝 — 노드 +{info.get('노드', 0):,}"
              f"(auto {info.get('auto', 0):,}) · 엣지 +{info.get('엣지', 0):,} · "
              f"저해상도 부착 {info.get('저해상도', 0):,}행{_hf}"
              + (f" · 큐: {head}" if head else " · 큐 0")
              + f" · LLM 호출 {u['calls']:,} · {_screen.tokens(u)}")
        # **문서 끝 결과표**(B99 ⑤) — 층별 증감 · 이번/이전 큐 · LLM 지점별
        from cli import result_screen
        LAST_RESULT["res"] = info.get("결과")
        result_screen.show(info.get("결과"))
        result_screen.show_reconcile(info.get("맞춤"), limit=LIST_LIMIT)     # 맞춤표 (B112 ①④⑤)
        # **인입 끝 목록**(B102 ⑦) — 불확실 · 보류 · `show report`와 같은 함수 · 줄 상한
        _doc = (info.get("결과") or {}).get("doc_id")
        if _doc:
            from cli.show_report import hold_unc_lines
            from core.build import ledger as _lg
            _ln = hold_unc_lines((_lg.read(_doc) or {}).get("rows") or [], limit=LIST_LIMIT, doc=_doc)
            for ln in _ln:
                print(ln)
            if _ln:
                print(f"    전체는 python run.py show report {_doc}")
    return notice


#: 인입 끝 목록의 줄 상한(목록마다) — 전체는 `show report`.
LIST_LIMIT = 8

#: 마지막 문서의 결과 묶음 — 일괄 투입 끝 줄이 문서별로 모은다(`cli/ingest.ingest_file`).
LAST_RESULT = {"res": None}


def toc_lines(info):
    """**청크 목차**(B112 ③) — 청크 전부 · `# · 라벨 · 좌표 · 상태 · 글자 수` + 표 아래 청크 맞춤 줄."""
    toc = info.get("목차") or []
    if not toc:
        return []
    out = ["   " + _screen.pad("#", 5) + _screen.pad("라벨", 44) + _screen.pad("좌표", 18)
           + _screen.pad("상태", 8) + "글자"]
    for n, lab, co, st, ch in toc:
        out.append("   " + _screen.pad(n, 5) + _screen.pad(_screen.cut(lab, 42), 44)
                   + _screen.pad(_screen.cut(str(co), 16), 18) + _screen.pad(st, 8) + f"{ch:,}")
    from collections import Counter
    c = Counter(st for *_x, st, _ch in toc)
    out.append(f"   청크(산문) {len(toc):,} = 부름 {c.get('부름', 0):,} + ref {c.get('ref', 0):,} + "
               f"거름 {c.get('거름', 0):,} + 재사용 {c.get('재사용', 0):,}")
    return out


def end_lists(info):
    """추출 끝의 **개체 0 청크 · 실패 청크 목록**(라벨 + 앞부분 40자 · B112 ③)."""
    out = []
    if info.get("개체0"):
        out.append(f"   개체 0 청크 {len(info['개체0']):,} — 라벨 · 앞부분")
        out += [f"     {_screen.pad(_screen.cut(lab, 40), 42)}「{head}」" for lab, head in info["개체0"]]
    if info.get("실패목록"):
        out.append(f"   실패 청크 {len(info['실패목록']):,} — 라벨 · 사유")
        out += [f"     {_screen.pad(_screen.cut(lab, 40), 42)}{why}" for lab, why in info["실패목록"]]
    return out


def extract_table(places=None):
    """추출 청크 표(B98 ⑥) — 번호 · 시트 · 청크(경로 끝) · 개체 수 · 개체(카테고리) · 관계 · 입력 · 출력 · 누적."""
    ws, wc = place_widths(places)
    return _screen.Table([("번호", 7, True), ("시트", ws, False), ("청크", wc, False), ("개체", 4, True),
                          ("개체(카테고리)", 60, False), ("관계", 4, True), ("입력", 6, True),
                          ("출력", 6, True), ("누적", 8, True)], flex=4, keep=(1, 2))


def extract_screen(step=False, stage=None):
    """**산문 추출 화면** (B97 ①② · 표 B98 ⑥) — 세 진입(한 렌즈 · 렌즈마다 · `cli.extract`)이 같은 함수다.

    core는 사실만 낸다(`core/build/extract.extract`의 `notice`) — 예고 · 청크마다 메타 ·
    끝. 화면은 예고·끝은 줄로, 청크는 **이어지는 표**로 그리고, `--step`이면 추출 예고에서
    묻는다(`False` = 멈춤). `stage`를 주면 누적 줄(`_screen.ticker`)이 읽는 「어디」를 갱신한다.
    """
    box = {"t": None, "u0": None}

    def notice(info):
        k = info.get("단계")
        lz = f"[{info['렌즈']}] " if info.get("렌즈") else ""
        if k in ("추출리허설", "개요리허설"):           # 등록 검수의 리허설 산출 (B116 ②)
            what = "추출" if k == "추출리허설" else "개요"
            if info["쓴다"]:
                _screen.say(f"   {what} {lz}— 리허설 산출({info['종류']} 등록 검수)을 운영 자리로 옮겼다 · "
                            f"{paths.show(info['자리'])}", "head")
            else:
                _screen.say(f"   {what} {lz}— 리허설 산출({info['종류']})을 쓰지 않는다: {info['이유']} "
                            f"(그 자리에서 지웠다 · 지금 조건으로 다시 판정)", "aux")
            return None
        if k in ("개요예고", "개요끝", "개요재사용"):
            return _outline_line(info, lz, stage, step)
        if k == "추출재사용":
            _screen.say(f"   추출 {lz}— 체크포인트 재사용(LLM 0) · {paths.show(info['자리'])}", "head")
        elif k == "추출저장":                        # 끝난 뒤 그 자리에 있나 (B112 ⑦)
            where = paths.show(info["자리"])
            if info.get("전실패"):
                _screen.say(f"   추출 체크포인트 {lz}— 쓰지 않았다(전 청크 실패 — 다시 치면 처음부터) · 자리 {where}",
                            "fail")
            elif info["있음"]:
                _screen.say(f"   추출 체크포인트 {lz}— {where} (있음)", "head")
            else:
                _screen.say(f"   [결함] 추출이 끝났는데 체크포인트가 없다 {lz}— {where} (로그 · 결함 장부에도)",
                            "fail")
        elif k == "추출이어서":
            _screen.say(f"   추출 이어서 {lz}— 끝난 청크 {info['끝난']:,} · "
                        f"남은 {info['남은']:,}", "head")
        elif k == "추출예고":
            box["t"], box["u0"] = extract_table(info.get("자리목록")), gateway.usage_total()
            if stage is not None:
                import time
                stage.update({"이름": "추출", "값": 0, "총": info["호출"], "t0": time.monotonic()})
            if info.get("렌즈여럿"):
                return None                       # 렌즈 예고가 같은 자리를 맡았다(두 줄 0)
            head = (f"추출 예고 {lz}— 청크 {info['청크']:,}(ref 시트 {info['ref']:,} · "
                    f"체크포인트 재사용 {info['재사용']:,} 제외) → LLM ≤ {info['호출']:,}회")
            if info.get("다시"):                    # 옛 추출을 다시 뽑는 이유(B102 ⑥)
                head += f" · 다시 뽑는다 — {info['다시']}"
            # 머리는 늘(B99 ④) — `--step`이면 묻는다 · 머리 아래 청크 목차 + 청크 맞춤 줄(B112 ③)
            return _step_gate(7, head.split("— ", 1)[1], prose=True, ask=step, body=toc_lines(info))
        elif k == "추출청크":
            if stage is not None:
                stage["값"] = info["i"]
            _chunk_row(box, info, lz)
        elif k == "추출끝":
            if box["t"] is not None:
                box["t"].end()
            _screen.say(f"   추출 끝 {lz}— 청크 {info['청크']:,} · 개체 {info['개체']:,} · "
                        f"관계 {info['관계']:,} · 실패 {info['실패']:,} · "
                        f"{_screen.usage_line(info.get('since'))}", "head")
            for ln in end_lists(info):                    # 개체 0 · 실패 청크 목록 (B112 ③)
                _screen.say(ln, "fail" if ln.startswith("   실패 청크") else None)
        return None
    return notice


def _outline_line(info, lz, stage, step=False):
    """**문서 개요 줄**(B115 ①) — 예고(제목 n → LLM ≤ 1회) · 끝(대상 · 주제 · 버림 + 대상 목록) · 재사용(LLM 0).
    `--step`이면 실호출이 있을 때 예고에서 묻는다(비용 전에 멈춘다 — `False`면 그래프 쓰기 0 · LLM 0)."""
    k = info["단계"]
    if k == "개요예고":
        if stage is not None:
            import time
            stage.update({"이름": "개요", "값": 0, "총": info["호출"], "t0": time.monotonic()})
        head = f"개요 예고 {lz}— 제목 {info['제목']:,} → LLM ≤ {info['호출']:,}회(제목 계층만 · 본문 0)"
        if info.get("다시"):
            head += f" · 다시 묻는다 — {info['다시']}"
        _screen.say(f"   {head}", "head")
        if step and info["호출"] and sys.stdin.isatty():
            if not _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True):
                print("   멈춤 — 개요 예고까지(LLM 0 · 그래프 쓰기 0) ▶ 같은 명령을 다시 친다")
                return False
        return None
    cnt = (f"제목 {info['제목']:,} = 대상 {info['대상']:,} + 주제 {info['주제']:,} + 버림 {info['버림']:,}")
    if k == "개요재사용":
        _screen.say(f"   개요 {lz}— 체크포인트 재사용(LLM 0) · {cnt} · {paths.show(info['자리'])}", "head")
    else:
        where = f" · {paths.show(info['자리'])}" if info.get("자리") else " · 판정 없음(mock · 힌트 없음 — 전부 주제)"
        _screen.say(f"   개요 끝 {lz}— {cnt} · {_screen.usage_line(info.get('since'))}{where}", "head")
    for path, name, cat in info.get("대상목록") or []:
        _screen.say(f"     제목 개체 {name}[{cat}] ← {path}", "aux")
    return None


def _chunk_row(box, info, lz):
    """청크 한 행 — 개체는 전부(칸이 좁으면 `…` · `-v`면 행 아래 전체 · 전체는 늘 로그와 체크포인트)."""
    t = box["t"] or extract_table()
    box["t"] = t
    ents = " · ".join(f"{s}[{c}]" for s, c in info["개체"])
    tok = info.get("토큰") or {}
    cum = _screen.tokens(gateway.usage_total(), box["u0"]).split("(")[0].replace("토큰 ", "")
    if info.get("실패"):
        cell, kind = f"✗ 실패 — {info['실패']}", "fail"
    else:
        cell, kind = ents or "— (개체 0)", (None if ents else "aux")
    sheet, end = info.get("자리") or where_cells(info["locator"])
    t.row([f"{info['i']}/{info['m']}", lz + sheet, end, len(info["개체"]), cell,
           info["관계"], f"{tok.get('prompt_tokens', 0):,}", f"{tok.get('completion_tokens', 0):,}",
           cum],
          ["prog", "aux", "aux", "aux" if not info["개체"] else None, kind, None, "aux", "aux", "aux"],
          extra=(ents if _screen.VERBOSE and ents else None))
    _LOG.info("추출 %s %s(%s) · 개체 %s · %s", info["i"], info["locator"], info.get("라벨") or "", ents,
              _screen.tokens(tok))


def reinforce_screen(stage=None):
    """**연결 보강 화면**(B115 ④ · 지점 ⑫) — 예고(대상 n · 재생 r → LLM ≤ k회 · 상한) · 진행(대상마다 결과 — 판정이 있었던
    것만 · `-v`면 전부) · 끝(붙음 · 재생 · 못 고름 · 버림 · 사용량). 끝 줄 전문은 마무리 줄(`reinforce.line`)이 낸다."""
    def notice(info):
        k = info.get("단계")
        if k == "보강예고":
            if stage is not None:
                import time
                stage.update({"이름": "연결 보강", "값": 0, "총": info["대상"], "t0": time.monotonic()})
            why = " · mock — 선별 규칙 없음(호출 0)" if info.get("mock") else ""
            _screen.say(f"   연결 보강 예고 — 대상 {info['대상']:,}(엣지 없는 · 공정에만 붙은 개체 · 재생 {info['재생']:,}) "
                        f"→ LLM ≤ {info['호출']:,}회(상한 reinforce_call_cap {info['상한']:,}){why}", "head")
        elif k == "보강진행":
            if stage is not None:
                stage["값"] = info["i"]
            if info.get("결과") and (_screen.VERBOSE or not str(info["결과"]).startswith("못 고름")):
                _screen.say(f"     {info['i']}/{info['m']} {info.get('표기')} — {info['결과']}", "aux")
            _LOG.info("연결 보강 %s/%s %s — %s", info["i"], info["m"], info.get("표기"), info.get("결과"))
        elif k == "보강끝":
            _screen.say(f"   연결 보강 끝 — 붙음 {info['붙음']:,} · 재생 {info['재생']:,} · 못 고름 {info['못 고름']:,} · "
                        f"버림 {info['버림']:,} · {_screen.usage_line(info.get('since'))}", "head")
        return None
    return notice


def ticker_where(stage):
    """누적 줄의 「어디」 — `stage`(이름 · 값/총)를 그대로 읽는다."""
    def where():
        import time
        n, t, t0 = stage.get("값") or 0, stage.get("총"), stage.get("t0")
        out = f"{stage.get('이름', '?')}" + (f" {n:,}/{t:,} · 남은 {max(0, t - n):,}" if t else "")
        if t and n and t0:                            # 예상 — 지금까지의 속도 그대로 (B99 ⑦)
            out += f" · 예상 {(time.monotonic() - t0) / n * max(0, t - n) / 60:.1f}분"
        return out
    return where


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
    def total_now():
        # **총수는 단계가 정한다**(B99 ⑦ — 산문은 추출이 끝나야 개체 수를 안다)
        return (stage or {}).get("총") or total

    def line(n, u):
        # **누적에 대장 집계를 더한다**(B81 ④) — 사람이 알고 싶은 것은 토큰만이
        # 아니라 「몇이 붙고 몇이 새로 생겼나」다. 수는 대장에서 센 것 그대로다.
        # 값 = **처리한 값**(대장 행 — 사전 히트 포함) / 판정 예고의 값 수 · 호출 = 판정 호출 수(B102 ⑦)
        return (f"[판정] 값 {max(TALLY['값'], 1):,}/{total_now():,} · 호출 {n:,} · 누적 {_screen.tokens(u)}"
                f" · 사전 {TALLY['사전']:,} · NEW {TALLY['NEW']:,}"
                f" · 불확실 {TALLY['불확실']:,} · 큐 {TALLY['큐']:,}")

    step_n = max(1, int(stride or gateway.config().get("progress_every") or 25))

    def progress(stats):
        n = stats.get("판정", 0)
        if stage is not None:
            stage["값"] = n
            if n == 1 or not stage.get("t0"):
                import time
                stage.setdefault("t0", time.monotonic())
        u = gateway.usage_total()
        if n == 1 or n % step_n == 0 or n == total_now():
            _screen.inline(line(n, u), "prog")      # 값 표가 이어지는 중이면 구분 행
            _LOG.info("판정 진행 — 값 %d/%d · 호출 %d · 누적 %s",
                      n, total_now() or 0, n, _screen.tokens(u))
        if every and n % every == 0 and n < (total_now() or 0):
            _judge_gate(n, total_now(), u)
    return progress


def _judge_gate(n, total, u):
    """판정 **안**의 멈춤 자리 (B75 ③ⓒ). 비대화형이면 묻지 않는다."""
    if not sys.stdin.isatty():
        return
    left = max(0, (total or 0) - n)
    _screen.say(f"   [판정] 값 {n:,}/{total:,} · 호출 {n:,} · 누적 {_screen.tokens(u)} · "
                f"남은 값 {left:,}", "prog")
    if not _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True):
        from core.build.entry import Stopped
        raise Stopped(f"사람이 멈췄다 — 판정 값 {n}/{total} (그래프 쓰기 0 · "
                      f"체크포인트는 남는다)")
