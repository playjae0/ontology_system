#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""칸 0.3 — **옛 경로 문자열 0** (B78 3).

B78이 코드와 상태의 자리를 옮겼다. 자리가 바뀌면 **그 자리를 부르던 문장**이 남고,
남은 문장은 사람을 옛 자리로 보낸다 — 「있는데 없는」 파일을 찾게 만드는 것이 그
비용이다. 그래서 옮긴 이름을 기계가 훑는다.

**보는 범위**: 레포의 `.py`·`.md`·`.json` 전부 — 코드도 주석도 정본 문서도 같이 본다.
**보지 않는 범위 — 이력과 재생성물**: ①`docs/archive/`·개정대장·회차 요청문
(`docs/안건/`)·`DECISIONS.md`·`PROGRESS.md`·실측 대장·감사 결과 — 전부 **과거를 적은
장부**이고, 과거의 자리를 옛 이름으로 부르는 것이 맞다. 여기를 고치면 이력이 거짓이 된다.
②재생성 산출·기준선 스냅샷(명세에서 뽑으므로 명세가 고쳐지면 같이 고쳐진다)
③등록 자산(`adapters/`·`review/` — 사람 승인 1회 · 재생성 불가)과 지시문 자산
(`prompts/` — **사람 확정 관리 자산**이고 문면 한 줄이 판단을 바꾼다 · 고치려면
`version:` 개정이다) ④상태·파생·LLM 실산출.

**붉은 것이 곧 개정 목록이다** — 정본 `docs/spec/`의 낡은 절은 이 세션이 고치지
않는다(허브 소관 · CLAUDE.md §8). 여기 뜨는 줄이 그 목록의 기계 판이다.

사용: python docs/회귀스위트/점검_경로.py     (위반이 있으면 exit 1)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

#: 옮긴 자리 — `옛 이름` → 지금 자리(화면에 함께 낸다).
MOVED = {
    "core/llm.py": "core/llm/gateway.py", "core/embeddings.py": "core/llm/embeddings.py",
    "core/store.py": "core/state/store.py", "core/registry.py": "core/state/registry.py",
    "core/skeleton.py": "core/state/skeleton.py", "core/init.py": "core/state/init.py",
    "core/bootstrap.py": "core/state/bootstrap.py", "core/ops.py": "core/state/ops.py",
    "core/migrate.py": "core/state/migrate.py", "core/ids.py": "core/state/ids.py",
    "core/log.py": "core/state/log.py", "core/status.py": "core/state/status.py",
    "core/fixtures.py": "core/state/fixtures.py",
    "core/pipeline.py": "core/build/{loop,table,prose,entry}.py",
    "core/build.py": "core/build/build.py", "core/gate.py": "core/build/gate.py",
    "core/ingest.py": "core/build/ingest.py", "core/extract.py": "core/build/extract.py",
    "core/ledger.py": "core/build/ledger.py", "core/retry.py": "core/build/retry.py",
    "core/naming.py": "core/build/naming.py",
    "core/query.py": "core/query/query.py", "core/bm25.py": "core/query/bm25.py",
    "cli/register.py": "cli/register/(패키지)",
    "tests/test_p3.py": "tests/test_p3_*.py", "tests/test_p1.py": "tests/test_p1_*.py",
    "tests/test_g6.py": "tests/test_g6_*.py", "tests/test_g6_5.py": "tests/test_g65_*.py",
    "schemas/pfmea.json": "tests/fixtures/schemas/pfmea.json",
    "schemas/cp.json": "tests/fixtures/schemas/cp.json",
    "schemas/ppt_process.json": "tests/fixtures/schemas/ppt_process.json",
    "schemas/ppt_quality.json": "tests/fixtures/schemas/ppt_quality.json",
    "data/doc_types.json": "<상태>/registry/doc_types.json",
    "extract/struct_maps/": "<상태>/work/struct_maps/",
    # B78 1b에 ④단으로 옮겼다 — 문면과 **대장 수를 세는 자리**가 옛 이름으로 남아
    # 늘 0건이었다(B86 ③ 실측 · `cli/show.py`).
    "data/ingest_log": "<상태>/work/ingest_log/",
}

#: 보지 않는 자리 — 이력·자동 생성물·등록 자산·상태·스냅샷.
SKIP_DIRS = ("docs/archive/", "docs/안건/", "docs/회귀스위트/자산/", ".git/",
             "__pycache__/", "state/", "state_mock/", "tests/fixtures/fixtures/",
             "adapters/", "review/", "export/", "golden/", "data/", "work/",
             "prompts/")
SKIP_FILES = ("docs/spec/개정대장.md", "DECISIONS.md", "PROGRESS.md",     # 이력이다
              "docs/실측_대장.md",
              "docs/구조도/구조_추출.json", "docs/구조도/부품카드.md",
              "docs/구조도/부품카드.json", "docs/구조도/구조_지도.md",
              "docs/회귀스위트/점검_경로.py")                # 표가 여기 있다
EXT = (".py", ".md", ".json")

#: **옛 배치를 일부러 세우는 줄**의 표지 — 이관 시험(`tests/test_onsite.py`)은 옛
#: 코드 폴더의 모양을 만들어야 이관을 잴 수 있다. 줄에 이 표지가 있으면 비킨다 —
#: 폴더 통째로 빼면 새로 박힌 옛 자리까지 같이 빠진다(B86 ③).
LEGACY_MARK = "# 옛 배치"


def targets():
    """훑을 파일 — 레포 전부에서 위 두 목록을 뺀다."""
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix not in EXT:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(s in rel + "/" for s in SKIP_DIRS) or rel in SKIP_FILES:
            continue
        out.append(p)
    return out


def _split_form(old):
    """**토큰이 갈린 형태** — `ROOT / 'data' / 'ingest_log'`처럼 조각을 `/`로 잇는 코드.

    B78 뒤에도 그 형태 하나가 살아남았다(B86 ③): 경로 **문자열**만 보면 조각 셋이
    각각 흔한 낱말이라 한 번도 걸리지 않는다. 따옴표 조각이 옛 이름의 순서대로
    `/`로 이어져 있으면 같은 옛 자리다.
    """
    parts = [x for x in old.rstrip("/").split("/") if x]
    if len(parts) < 2:
        return None
    q = r"""['"]"""
    return re.compile(r"\s*/\s*".join(q + re.escape(x) + q for x in parts))


def scan():
    """`[(파일, 줄, 옛 이름, 지금 자리, 원문)]` — 파일 순·줄 순."""
    pats = {old: re.compile(r'(?<![\w/])' + re.escape(old)) for old in MOVED}
    split = {old: rx for old in MOVED if (rx := _split_form(old))}
    hits = []
    for p in targets():
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, ln in enumerate(lines, 1):
            if LEGACY_MARK in ln:
                continue
            for old in MOVED:
                if pats[old].search(ln) or (old in split and split[old].search(ln)):
                    hits.append((p.relative_to(ROOT).as_posix(), i, old, MOVED[old],
                                 ln.strip()[:90]))
    return hits


def main():
    hits = scan()
    print(f"옛 경로 문자열 — 대상 {len(targets())}파일 · 옮긴 이름 {len(MOVED)}종")
    for f, i, old, now, txt in hits:
        print(f"  {f}:{i}  {old} → {now}\n      {txt}")
    print(f"\n총 {len(hits)}건" + (" — 통과" if not hits else " — 옛 자리를 가리킨다"))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
