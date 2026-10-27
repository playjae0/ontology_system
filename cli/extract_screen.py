# -*- coding: utf-8 -*-
"""칸 3.3 — 산문 **추출 화면**: 추출 예고 · 청크 표 · 끝 · 목차 노드화 줄 (B97 ①② · B98 ⑥ · B115 ① · B148 ②).

`cli/ingest_screen.py`에서 떼어냈다(B150 — 800행 상한). 세 진입(인입 한 렌즈 · 렌즈마다 · `cli.extract`)이 같은 함수다 ·
화면은 core가 낸 사실(`notice`)의 투영이다(새 계산 0).
"""
from __future__ import annotations

import sys

from cli import _screen
from cli.ingest_screen import _step_gate, end_lists, place_widths, toc_lines, where_cells
from core import paths
from core.llm import gateway
from core.state import log

_LOG = log.get(__name__)


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
            what = "추출" if k == "추출리허설" else "목차 노드화"
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
            _screen.say(f"   추출 {lz}— 체크포인트 재사용(LLM 0) · {paths.show(info['자리'])}"
                        + (f" · 호출 보존 씨앗 {info['씨앗']:,}" if info.get("씨앗") else ""), "head")
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
        elif k == "추출예고":
            box["t"], box["u0"] = extract_table(info.get("자리목록")), gateway.usage_total()
            if stage is not None:
                import time
                stage.update({"이름": "추출", "값": 0, "총": info["호출"], "t0": time.monotonic()})
            if info.get("렌즈여럿"):
                return None                       # 렌즈 예고가 같은 자리를 맡았다(두 줄 0)
            head = (f"추출 예고 {lz}— 청크 {info['청크']:,}(ref 시트 {info['ref']:,}) → 부를 {info['호출']:,} · "
                    f"다시 씀 {info['재사용']:,}(같은 입력 — LLM 0) → LLM ≤ {info['호출']:,}회")
            if info.get("다시"):                    # 옛 추출을 다시 뽑는 이유(B102 ⑥)
                head += f" · 다시 뽑는다 — {info['다시']}"
            if info.get("개체없음"):                # 덱 구조의 「개체 없음」 슬라이드 — 부르지 않는다 (B125 ①)
                head += f" · 개체 없음 {info['개체없음']:,}"
            cp = info.get("캡처")                   # 슬라이드 · 쪽 캡처 (B125 ②)
            if cp:
                _screen.say(f"   캡처 — 있음 {cp['있음']:,} · 없음 {cp['없음']:,}"
                            + (f"({cp['사유']})" if cp.get("사유") and cp["없음"] else ""), "warn" if cp["없음"] else "head")
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
    """**목차 노드화 줄**(B115 ① · B148 ②) — 예고(제목 n · 좌표 c → LLM ≤ 1회) · 끝(대상 · 주제 · 버림 + 대상 목록) · 재사용(LLM 0).
    `--step`이면 실호출이 있을 때 예고에서 묻는다(비용 전에 멈춘다 — `False`면 그래프 쓰기 0 · LLM 0)."""
    k = info["단계"]
    if k == "개요예고":
        if stage is not None:
            import time
            stage.update({"이름": "목차 노드화", "값": 0, "총": info["호출"], "t0": time.monotonic()})
        head = (f"목차 노드화 예고 {lz}— 제목 {info['제목']:,}(골격 이름 {info.get('좌표', 0):,} — 묻지 않는다) → LLM ≤ "
                f"{info['호출']:,}회(목차 · 항목 아래 청크 수 · 본문 0)")
        if info.get("다시"):
            head += f" · 다시 묻는다 — {info['다시']}"
        _screen.say(f"   {head}", "head")
        if step and info["호출"] and sys.stdin.isatty():
            if not _screen.answer("   [계속 c / 멈춤 q] ", "go", eof=True):
                print("   멈춤 — 목차 노드화 예고까지(LLM 0 · 그래프 쓰기 0) ▶ 같은 명령을 다시 친다")
                return False
        return None
    cnt = (f"제목 {info['제목']:,} = 대상 {info['대상']:,} + 주제 {info['주제']:,} + 버림 {info['버림']:,}")
    if k == "개요재사용":
        _screen.say(f"   목차 노드화 {lz}— 체크포인트 재사용(LLM 0) · {cnt} · {paths.show(info['자리'])}", "head")
    else:
        where = f" · {paths.show(info['자리'])}" if info.get("자리") else " · 판정 없음(mock · 힌트 없음 — 전부 주제)"
        _screen.say(f"   목차 노드화 끝 {lz}— {cnt} · {_screen.usage_line(info.get('since'))}{where}", "head")
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
