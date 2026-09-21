# -*- coding: utf-8 -*-
"""칸 0.3 — **옛 배치 → 5단 배치 이관** (B78 1b · 문서 7 §7.8).

옛 배치는 상태가 코드 폴더 안에 흩어져 있었다 — `data/`(진실+등록+장부) ·
`review/` · `parsed/` · `extract/` · `llm.local.json`. 코드를 새로 가져오면 그
다섯을 **손으로 같이 옮겨야** 정상이 됐고, 하나를 빠뜨린 실측이 B77 ③의 재료였다
(`review/`만 옮기고 `data/doc_types.json`을 안 옮겨 등록부가 비었다).

이 모듈이 하는 일은 셋이다.

1. **감지** — `legacy_root()` · `needs_migration()`. 옛 자리에 등록부가 있는데 새
   상태 루트가 비어 있으면 「이관 전」이다. **조용히 옛 자리를 읽지 않는다**:
   사람이 치는 진입이 그 문면으로 멈춘다(`cli/_gate.py::_migrate_message`).
2. **계획** — `plan()`. 무엇이 어느 단으로 가는지의 전수 표다. 화면이 먼저 이것을
   보여 주고(`--dry-run`), 복사는 그 표대로만 한다.
3. **이관** — `run()`. **복사다(옛 폴더는 그대로 둔다)** · 등록부의 경로를 새 자리
   기준으로 재작성 · `work/migrate.log`에 「무엇을 어디로, 해시」를 남긴다.

**판정만 하고 화면은 갖지 않는다**(D-149 ③) — `SystemExit`을 던지는 것은 CLI다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from core import paths
from core.state import log, store

ROOT = paths.ROOT                  # 레포 루트는 자리 소유자가 안다 (B78)
_LOG = log.get(__name__)

#: 원본 문서의 확장자 — **파서가 읽는 포맷**(`parser/reader.SUPPORTED`)과 같다.
#: 킷·파서를 import하지 않는다(core의 의존 방향) — 목록이 갈리면 회귀가 잡는다.
DOC_EXT = (".xlsx", ".xlsm", ".pptx", ".pdf", ".csv", ".tsv")

#: 옛 배치의 표식 — 등록부가 진실 옆에 있던 자리다.
LEGACY_MARK = ("data", "doc_types.json")

#: ③진실에 남는 파일 **7종**(허브 확정 2026-09-17 — 층 등록부 `registry.json`을 포함해
#: `<층>/graph.json`까지 세면 8종이다). 층 폴더는 아래에서 따로 훑는다.
TRUTH_FILES = (store.DICTIONARY, store.CHUNKS, store.QUEUE,
               store.DOC_REGISTRY, store.OPS_LOG, store.SKELETON_LIST,
               store.REGISTRY)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def legacy_root(root=None):
    """옛 배치의 뿌리 — 없으면 None. 표식은 `data/doc_types.json` 하나다."""
    r = Path(root) if root else ROOT
    return r if (r / LEGACY_MARK[0] / LEGACY_MARK[1]).is_file() else None


def needs_migration():
    """이 실행이 **이관 전인가** — `(옛 루트, 새 루트)` 또는 None.

    mock 세계는 대상이 아니다(자리가 `state_mock/`으로 아예 다르다). 새 루트에
    등록부가 이미 있으면 이관은 끝났다 — 옛 폴더가 남아 있어도 다시 묻지 않는다.
    """
    if paths.is_mock_home():
        return None
    home = paths.home()
    if (home / "registry" / store.DOC_TYPES).is_file():
        return None
    old = legacy_root()
    return (old, home) if old else None


def _registered_paths(old):
    """옛 등록부가 가리키는 (키, 상대 경로) 전량 — 스키마 선별의 재료다."""
    try:
        reg = json.loads((old / LEGACY_MARK[0] / LEGACY_MARK[1])
                         .read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}
    return {dt: {k: (e or {}).get(k) for k in ("adapter", "schema")}
            for dt, e in (reg or {}).items()}


def plan(old, home):
    """이관 표 — `(src, dst, 단)`의 전수 목록. **여기 없는 것은 옮기지 않는다.**

    스키마는 **등록부가 가리키는 것만** 옮긴다: 레포가 싣고 나온 내장(mock)은
    등록이 아니라 픽스처이고(B78 1b — 자리로 가른다), 등록 자리에 섞이면 그것이
    바로 「mock이 이름만 다르게 숨어 있다」의 재발이다.
    """
    old, home = Path(old), Path(home)
    out = []

    def add(src, dst, tier):
        # **락은 상태가 아니다**(허브 확정 2026-09-17) — `.<이름>.lock`은 원자 쓰기의
        # 부산물이고, 옮기면 새 자리에 남의 프로세스 락이 유령으로 선다.
        if src.is_file() and not src.name.endswith(".lock"):
            out.append((src, dst, tier))

    def add_tree(src_dir, dst_dir, tier):
        if src_dir.is_dir():
            for p in sorted(src_dir.rglob("*")):
                # 파이썬 캐시는 상태가 아니다 — 옮기면 새 자리에서 옛 바이트코드를 문다.
                if p.is_file() and "__pycache__" not in p.parts:
                    add(p, dst_dir / p.relative_to(src_dir), tier)

    reg_dir, data_dir, work_dir = home / "registry", home / "data", home / "work"

    # ②등록 — 사람 승인 1회. 재생성되지 않는다.
    add(old / LEGACY_MARK[0] / LEGACY_MARK[1], reg_dir / store.DOC_TYPES, "등록")
    add_tree(old / "review", reg_dir / "review", "등록")
    for p in sorted((old / "adapters").glob("*.py")) if (old / "adapters").is_dir() else []:
        add(p, reg_dir / "adapters" / p.name, "등록")
    for rels in _registered_paths(old).values():
        for key, rel in rels.items():
            if not rel or key != "schema":
                continue
            src = (old / rel) if not Path(rel).is_absolute() else Path(rel)
            add(src, reg_dir / "schemas" / Path(rel).name, "등록")

    # ③진실 — 누적. 층 폴더는 이름을 코드가 정하지 않는다(`data/` 아래 폴더 전부).
    for name in TRUTH_FILES:
        add(old / "data" / name, data_dir / name, "진실")
    if (old / "data").is_dir():
        for d in sorted(x for x in (old / "data").iterdir() if x.is_dir()):
            if d.name == "ingest_log":
                continue
            add_tree(d, data_dir / d.name, "진실")

    # ④작업·장부 — 재생성 가능. 그래도 옮긴다(판정 이력이라 대조에 쓴다).
    add_tree(old / "data" / "ingest_log", work_dir / "ingest_log", "작업")
    add_tree(old / "parsed", work_dir / "parsed", "작업")
    add_tree(old / "extract", work_dir / "extract", "작업")
    for name in store.WORK_FILES:
        add(old / "data" / name, work_dir / name, "작업")

    # ⓪원본 — **파서가 읽는 포맷만**(B79 ②). 옛 코드 폴더의 `docs/`는 이 레포에서
    # **명세 폴더**이기도 하다: 통째로 옮기면 정제본·가이드가 원본 자리에 앉고
    # 인자 없는 `ingest-dir`가 그것을 문서로 집는다. 그래서 확장자로 가른다 —
    # 옮기는 것은 「사람이 넣은 실물 문서」뿐이다(D-160 ②).
    if (old / "docs").is_dir():
        for s in sorted((old / "docs").rglob("*")):
            if s.is_file() and s.suffix.lower() in DOC_EXT:
                add(s, home / "docs" / s.relative_to(old / "docs"), "원본")

    # ②등록 — **층 자산**(B79 ①). 사내가 공정 체계로 고쳐 승인 1회 한 것이라
    # 코드 폴더에 두면 코드 교체가 사내 골격을 레포 seed 판으로 되돌린다.
    add_tree(old / "layers", home / "layers", "층")

    # ⑤골든셋 — 사람이 쓴 문항이다(재생성되지 않는다).
    add_tree(old / "golden", home / "golden", "골든")

    # 설정 — `llm.local.json`은 옛 자리에서도 그대로 읽히므로 **덮지 않는다**.
    if not (home / "llm.json").exists():
        add(old / "llm.local.json", home / "llm.json", "설정")
    return out


def assets(src=None, dst=None, *, dry_run=False):
    """**층 자산만** 옮긴다 — 이미 이관한 사람용 (B79 ① · `migrate --assets`).

    B78 이관은 `layers/`를 옮기지 않았다(①자산으로 봤다). 그래서 먼저 이관한
    사람의 상태 루트에는 층 자산이 없고, 코드 폴더의 것이 정본인 채로 남아 있다.
    이 함수가 그 한 칸을 메운다.

    **다르면 덮지 않는다.** 같은 이름의 파일이 상태 루트에 이미 있고 내용이 다르면
    「어느 것이 사내 판인가」는 기계가 정할 일이 아니다 — 목록을 돌려주고 멈춘다.
    """
    old = Path(src).expanduser().resolve() if src else legacy_root()
    if old is None:
        return {"ok": False, "reason": "옛 코드 폴더를 못 찾았다 — "
                                       "--from <옛 코드 폴더>를 적는다"}
    home = Path(dst).expanduser().resolve() if dst else paths.home()
    src_dir = old / "layers"
    if not src_dir.is_dir():
        return {"ok": False, "reason": f"{src_dir}가 없다 — 옮길 층 자산이 없다"}
    rows, conflict = [], []
    for s in sorted(src_dir.rglob("*")):
        if not s.is_file() or "__pycache__" in s.parts or s.name.endswith(".lock"):
            continue
        d = home / "layers" / s.relative_to(src_dir)
        if d.is_file():
            if _sha(d) != _sha(s):
                conflict.append((s, d))
            continue                       # 같으면 할 일이 없다
        rows.append((s, d, "층"))
    if conflict:
        return {"ok": False, "conflict": conflict, "src": old, "home": home,
                "reason": "상태 루트의 층 자산이 옛 폴더의 것과 **다르다** — "
                          "사람이 정한다(덮지 않았다)"}
    if dry_run:
        return {"ok": True, "dry_run": True, "rows": rows, "home": home, "src": old}
    lines = []
    for s, d, _tier in rows:
        paths.ensure(d)
        shutil.copy2(s, d)
        lines.append(f"층\t{s}\t→\t{d}\t{_sha(d)[:12]}\t{d.stat().st_size}B")
    logp = paths.ensure(home / "work" / "migrate.log")
    with open(logp, "a", encoding="utf-8") as f:
        f.write(f"# migrate --assets {store._now()} — {src_dir} → {home / 'layers'}\n")
        f.write(("\n".join(lines) + "\n") if lines else "# 옮길 것 없음\n")
    _LOG.info("migrate --assets: %s → %s · 파일 %d", src_dir, home / "layers", len(rows))
    return {"ok": True, "src": old, "home": home, "files": len(rows), "log": logp}


def _rewrite_registry(home, moved):
    """등록부의 경로를 **새 자리 기준 상대 경로**로 고친다 — 절대 경로·`..`는 남기지 않는다.

    `moved`는 `옛 실물 → 새 실물`이다. 옛 항목이 어디를 가리켰든(레포 기준·절대),
    그 실물이 이관 표에 있으면 새 자리의 `registry/` 기준 상대 경로가 된다.
    못 찾은 항목은 **고치지 않고 센다** — 조용히 지어내면 「있는데 없는」 등록이 된다.
    """
    p = home / "registry" / store.DOC_TYPES
    if not p.is_file():
        return 0, []
    reg = json.loads(p.read_text(encoding="utf-8"))
    fixed, missing = 0, []
    for dt, e in (reg or {}).items():
        for key in ("adapter", "schema"):
            rel = (e or {}).get(key)
            if not rel:
                continue
            new = moved.get(str(rel))
            if new is None:
                missing.append(f"{dt}.{key}={rel}")
                continue
            new_rel = str(Path(new).relative_to(home / "registry"))
            if new_rel != rel:
                e[key] = new_rel
                fixed += 1
    p.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    return fixed, missing


def run(src=None, dst=None, *, dry_run=False):
    """이관 — **복사**다. 옛 폴더는 그대로 둔다(되돌릴 자리를 없애지 않는다).

    돌려주는 것은 요약이고, 무엇이 어디로 갔는지의 전수는 `work/migrate.log`에 있다.
    """
    old = Path(src) if src else legacy_root()
    if dst is None and paths.is_mock_home():
        # **mock 루트로 운영 상태를 옮기지 않는다**(B78 1b — 자리로 가른다).
        return {"ok": False, "reason":
                f"지금 상태 루트가 mock({paths.home()})이다 — 이관 대상이 아니다\n"
                f"  ▶ 다음 줄:  USE_MOCK=0 python run.py platform migrate "
                f"--from <옛 코드 폴더>   (또는 --to <새 루트>를 적는다)"}
    home = Path(dst).expanduser().resolve() if dst else paths.home()
    if old is None:
        return {"ok": False, "reason": "옛 배치를 찾지 못했다 — "
                                       f"{LEGACY_MARK[0]}/{LEGACY_MARK[1]} 없음"}
    old = Path(old).expanduser().resolve()
    rows = plan(old, home)
    if dry_run:
        return {"ok": True, "dry_run": True, "rows": rows, "home": home, "src": old}

    moved, lines, per_tier = {}, [], {}
    for s, d, tier in rows:
        paths.ensure(d)
        shutil.copy2(s, d)
        moved[str(s)] = d
        # 옛 항목이 레포 기준 상대 경로로 적혀 있던 길도 같은 표에서 찾게 한다.
        try:
            moved[str(s.relative_to(old))] = d
        except ValueError:
            pass
        per_tier[tier] = per_tier.get(tier, 0) + 1
        lines.append(f"{tier}\t{s}\t→\t{d}\t{_sha(d)[:12]}\t{d.stat().st_size}B")
    fixed, missing = _rewrite_registry(home, moved)
    logp = paths.ensure(home / "work" / "migrate.log")
    with open(logp, "a", encoding="utf-8") as f:
        f.write(f"# migrate {store._now()} — {old} → {home}\n")
        f.write("\n".join(lines) + "\n")
        f.write(f"# 등록부 경로 재작성 {fixed}건 · 실물을 못 찾은 항목 "
                f"{len(missing)}건 {missing or ''}\n")
    _LOG.info("migrate: %s → %s · 파일 %d · 등록부 재작성 %d · 미해결 %d",
              old, home, len(rows), fixed, len(missing))
    paths.reset()                      # 이관 뒤의 조회는 새 자리를 본다
    return {"ok": True, "src": old, "home": home, "files": len(rows),
            "per_tier": per_tier, "rewritten": fixed, "missing": missing,
            "log": logp}
