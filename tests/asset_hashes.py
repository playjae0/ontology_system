# -*- coding: utf-8 -*-
"""칸 0.3 — **레포 정본 자산의 해시 기록** (B79 ④).

사용자 확정(2026-09-21): `prompts/`·`kit/`·`schemas/blocks.json`·(레포)`layers/`는
**레포가 정본이고 사내에서 고치지 않는다** — 고칠 것이 있으면 허브로 요청한다.
지시문·킷을 현장에서 고치면 「어느 판으로 잰 결과인가」가 사라지고, 판정이 좋아진
것인지 문면이 달라진 것인지 아무도 가를 수 없다.

규율만으로는 검출되지 않으므로 **기계가 잰다**: 이 파일이 해시를 재고,
`docs/회귀스위트/자산/자산_해시.json`이 기록이다. `doctor`가 둘을 대조해 다르면
⚠를 낸다. 기록 갱신은 **구현 세션이 회차마다** 한다(`--write`) — 사내는 갱신하지
않는다(그것이 규율의 자리다).

레포 `layers/`는 **seed**다(사내 판은 상태 루트에 있다 · B79 ①) — 여기서 재는 것은
seed가 레포 판인가이고, 사내가 고친 층 자산은 대상이 아니다.

사용:
    python tests/asset_hashes.py            대조 (다르면 exit 1)
    python tests/asset_hashes.py --write    기록 갱신 (구현 세션만)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "회귀스위트" / "자산" / "자산_해시.json"

#: 레포 정본 자산 — 폴더는 전수, 파일은 그 파일.
ASSETS = ("prompts", "kit", "schemas/blocks.json", "layers")
SKIP = ("__pycache__", ".lock")


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def files():
    """대상 파일 전수 — 레포 기준 상대 경로 순."""
    out = []
    for a in ASSETS:
        p = ROOT / a
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += [x for x in sorted(p.rglob("*"))
                    if x.is_file() and not any(s in x.as_posix() for s in SKIP)]
    return sorted(out)


def compute():
    """`{상대경로: sha256}` — 지금 레포의 실물."""
    return {p.relative_to(ROOT).as_posix(): _sha(p) for p in files()}


def record():
    """기록 — 없으면 빈 dict."""
    if not RECORD.is_file():
        return {}
    return json.loads(RECORD.read_text(encoding="utf-8")).get("files") or {}


def diff():
    """`(달라진 것, 기록에 없는 것, 사라진 것)` — 전부 상대 경로."""
    now, was = compute(), record()
    changed = sorted(k for k in now if k in was and now[k] != was[k])
    added = sorted(k for k in now if k not in was)
    gone = sorted(k for k in was if k not in now)
    return changed, added, gone


def write():
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    now = compute()
    RECORD.write_text(json.dumps({"자산": list(ASSETS), "files": now},
                                 ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    return len(now)


def main():
    if "--write" in sys.argv[1:]:
        print(f"자산 해시 기록 갱신 — 파일 {write()} → {RECORD.relative_to(ROOT)}")
        return 0
    changed, added, gone = diff()
    print(f"레포 정본 자산 — 파일 {len(compute())} · 기록 {len(record())}")
    for k in changed:
        print(f"  다름   {k}")
    for k in added:
        print(f"  기록 없음 {k}")
    for k in gone:
        print(f"  사라짐 {k}")
    bad = changed + added + gone
    print(f"총 {len(bad)}건" + (" — 레포 판과 같다" if not bad else
                                " — 사내에서 고치지 않는다(허브로 요청한다)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
