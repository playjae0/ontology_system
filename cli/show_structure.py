# -*- coding: utf-8 -*-
"""칸 0.3 — **구조 전후 비교**(B148 ③) — 저장해 둔 봉투 폴더와 지금 봉투(`work/parsed/`)를 문서 · 시트마다 대조한다.

    python run.py show structure --diff <저장 폴더>

문서마다 한 줄(시트 수 · 청크 경계가 바뀐 시트 수 · 시트 역할이 바뀐 시트 수) + 합 한 줄. 새 계산 0 — 시트마다 청크 경계는 구조
블록 읽기 함수(`cli/envelope_md.units` — 단위 → 그 근거 청크)의 청크 위치 차례 · 구조 블록이 없는 봉투(표 · 옛 봉투)는 청크의 시트
칸으로 묶는다 · 시트 역할은 청크 `meta.sheet_role`(`ref`)과 시트 유무(`skip` — 어댑터가 보지 않아 봉투에 없다)다. 쓰기 0.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import paths


def sheets(env):
    """봉투 → `{시트: (청크 위치 차례, 역할)}` — 역할은 `prose` · `ref`(봉투에 없는 시트는 `skip` — 비교가 가른다)."""
    from cli import envelope_md as EM
    env = env or {}
    out = {}
    for c in env.get("chunks") or []:
        m = c.get("meta") or {}
        s = m.get("sheet") or m.get("frame")
        if s is None:
            continue
        locs, role = out.get(s, ((), "prose"))
        out[s] = (locs + (c.get("source_locator"),), "ref" if m.get("sheet_role") == "ref" else role)
    for u, cs in EM.units(env, "structure"):             # 구조 블록의 단위 — 그 단위의 청크 위치 차례가 경계다 (B146 ①)
        name = u.get("unit")
        if name in out:
            out[name] = (tuple(c.get("source_locator") for c in cs), out[name][1])
    return out


def compare(old, now):
    """`{시트 수, 경계, 역할}` — 두 봉투의 시트를 대조(한쪽에만 있는 시트는 역할이 바뀐 시트 — skip ↔ 읽음)."""
    a, b = sheets(old), sheets(now)
    names = set(a) | set(b)
    cut = sum(1 for s in names if s in a and s in b and a[s][0] != b[s][0])
    role = sum(1 for s in names if (a.get(s) or (None, "skip"))[1] != (b.get(s) or (None, "skip"))[1])
    return {"시트": len(names), "경계": cut, "역할": role}


def _read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def diff(saved):
    """저장 폴더 vs 지금 봉투 — `[(doc_id, 결과 또는 None, 메모)]`(문서 이름 차례 · 한쪽에만 있으면 결과 None)."""
    old = {p.stem: p for p in Path(saved).glob("*.json")}
    now = {p.stem: p for p in paths.work("parsed").glob("*.json")} if paths.work("parsed").exists() else {}
    rows = []
    for d in sorted(set(old) | set(now)):
        if d not in now or d not in old:
            rows.append((d, None, "저장본에만" if d not in now else "지금에만"))
            continue
        rows.append((d, compare(_read(old[d]), _read(now[d])), ""))
    return rows


def main(args):
    """`show structure --diff <저장 폴더>`."""
    args = list(args)
    if args[:1] != ["--diff"] or len(args) < 2:
        raise SystemExit("[사용법] python run.py show structure --diff <저장해 둔 봉투 폴더(work/parsed 사본)>")   # [사용법]
    saved = Path(args[1])
    if not saved.is_dir():
        raise SystemExit(f"[사용법] 저장 폴더가 없다 — {saved}")                                              # [사용법]
    rows = diff(saved)
    print(f"구조 전후 비교 — 저장 {saved} ↔ 지금 {paths.show(paths.work('parsed'))} · 문서 {len(rows)}")
    tot = {"시트": 0, "경계": 0, "역할": 0}
    for d, r, why in rows:
        if r is None:
            print(f"   {d} — {why}")
            continue
        tot = {k: tot[k] + r[k] for k in tot}
        print(f"   {d} — 시트 {r['시트']} · 청크 경계가 바뀐 시트 {r['경계']} · 시트 역할이 바뀐 시트 {r['역할']}")
    print(f"   합 — 시트 {tot['시트']} · 청크 경계가 바뀐 시트 {tot['경계']} · 시트 역할이 바뀐 시트 {tot['역할']}")
    return 0
