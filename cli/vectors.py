# -*- coding: utf-8 -*-
"""칸 0.3 · 4.3 — **벡터 단독 명령** — 지금 상태 폴더의 노드 · 청크 벡터를 만든다 (B136 ④).

    python run.py vectors                         노드 · 청크
    python run.py vectors --only nodes|chunks     한 종류만
    python run.py vectors --gc                    색인을 맞춘 뒤 참조 없는 벡터(이 판)를 지운다

질의의 벡터 준비(`core/query/hybrid.warm`)와 **같은 재료 · 같은 저장**(`core/query/vectors` — 글이 같으면 다시 쓴다 · 바뀐 것만
만든다) · 그래프를 만드는 터미널과 따로 돈다(저장이 프로세스 사이 동시 쓰기를 받는다) · LLM 호출 0(실호출이면 사전 점검은 임베딩
설정만) · 끊고 다시 치면 남은 것만(묶음마다 커밋) · 진행 줄(저장마다 n/m · 남은 예상) · 끝 줄(만든 수 · 다시 쓴 수 · 시간 · 판 ·
색인 그대로 / 다시 씀 · 참조 없는 벡터 · 입력 한도와 넘어 자른 글 — B153 ③ · B161). 지우는 길은 `--gc` 하나다(종류 둘의 색인을 다
맞춘 뒤 — `--only`와 함께 쓰지 않는다 · 다른 판의 행은 그대로).
"""
from __future__ import annotations

import time

KINDS = ("nodes", "chunks")
_LABEL = {"nodes": "노드", "chunks": "청크"}


def end_line(stats, secs, fit="", index="", orphans=None):
    """끝 줄 — 「벡터 끝 — 노드 만든 a · 다시 씀 b · 청크 만든 c · 다시 씀 d · n.n초 · 판 <판> · <색인 조각> · 참조 없는 벡터 n(이 판) ·
    <한도 조각>」(한도 조각 — B153 ③ · 색인 · 참조 없는 벡터 — B161)."""
    parts = [f"{_LABEL.get(k, k)} 만든 {s['made']:,} · 다시 씀 {s['reused']:,}" for k, s in sorted(stats.items(), reverse=True)]
    bid = next(iter(stats.values()))["backend"] if stats else "-"
    return (f"벡터 끝 — {' · '.join(parts) or '만들 것 0'} · {secs:.1f}초 · 판 {bid}" + (f" · {index}" if index else "")
            + (f" · 참조 없는 벡터 {orphans:,}(이 판)" if orphans is not None else "") + (f" · {fit}" if fit else ""))


def main(argv):
    only = None
    gc = "--gc" in argv
    argv = [a for a in argv if a != "--gc"]
    if "--only" in argv:
        i = argv.index("--only")
        only = argv[i + 1] if i + 1 < len(argv) else None
        if only not in KINDS or gc:
            print(f"[사용법] python run.py vectors [--only {'|'.join(KINDS)}] | --gc (--gc는 종류 둘을 다 맞춘 뒤 지운다)")
            return 2
    from core import paths
    from core.llm import gateway
    if not gateway.use_mock():
        from cli.preflight import gate
        if not gate(chat=False, embed=True, catalog=False):          # LLM 0 — 임베딩 설정만 잰다
            return 1
    from core.query import hybrid as H, vectors as V
    V.ON_PROGRESS = lambda line: print(f"   {line}", flush=True)
    V.begin()
    t0 = time.monotonic()
    try:
        got = H.warm(kinds=(only,) if only else None)
    finally:
        V.ON_PROGRESS = None
    print("   시작할 때 있던 것 — " + " · ".join(f"{_LABEL[k]} {a:,}/{n:,}" for k, (a, n) in sorted(got.items(), reverse=True))
          if got else "   계획 — 벡터를 만들 노드 · 청크 0(그래프 · 청크가 비었다)")
    if gc:
        print(f"   정리 — 지운 벡터 {V.gc():,}(이 판 · 참조 없는 것 · 다른 판은 그대로)")
    print(f"   {end_line(V.STATS, time.monotonic() - t0, V.fit_line() if V.STATS else '', V.index_line(), V.orphans())} · "
          f"저장 {paths.show(paths.vectors(V.DB))}")
    return 0
