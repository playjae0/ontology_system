# -*- coding: utf-8 -*-
"""칸 0.3 — 클린 상태를 만드는 **단일 정의** — `run.py init [--fresh]` (문서 7 §7.6-4).

**왜 진입점이어야 하나.** 클린 판정이 걸린 곳이 둘이다 — 회귀 규약(§7.5-7 "클린 상태
단독 실행")과 완료판정 4번("클린 2회 동일 그래프"). 클린을 `rm -rf data`로 각자
만들면 "클린"의 정의가 실행마다 달라져 두 판정이 서로 다른 바닥 위에서 내려진다.
실제로 이 레포는 그 상태였다 — doctor와 테스트 10종이 `shutil.rmtree`를 제 손으로
반복하고, 그 결과 클린이 **"파일 없음"**이었다.

**빈 상태는 "파일 없음"이 아니라 "빈 파일"이다**(§7.2 말미). 그 형태가 아래 `EMPTY`다.
읽기 코드가 `read(name, default)`로 기본값을 갖고 있어 둘이 대체로 같게 동작하지만,
**대체로 같은 것은 판정의 바닥이 될 수 없다.**

    python run.py init                  빈 상태를 만든다 (있으면 그대로 둔다)
    python run.py init --fresh          지우고 다시 만든다 — **비용이 든 산출 넷은 남긴다**(B106 ①)
    python run.py init --fresh --all    전부 지운다 — **클린**(회귀 바닥 · doctor · 시험)

**fresh 기본은 재구축의 바닥이다**(B106 ① · 사용자 결정 2026-10-08): 산문 추출(`work/extract/`) ·
구조 지도(`work/struct_maps/`) · 판정 대장(`work/ingest_log/` — 판정 재생의 재료) · 좌표 학습
(`data/coord_learned.json`)을 남기고 나머지 ③④⑤를 지운다 — 다시 넣을 때 LLM을 처음부터 부르지 않게.
남긴 것의 재사용 판정은 각자의 것 그대로다(추출 = 문서 해시·어댑터·지시문·config 판 · 해시 없는 지도는
재사용 안 함 · 좌표 학습은 대상이 골격에 있을 때만). **클린은 `--all`**이고 정의는 B78 그대로다.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from core import paths
from core.state import log, store
from core.graph import GraphStore
from router import discover

ROOT = paths.ROOT                  # 레포 루트는 자리 소유자가 안다 (B78)
_LOG = log.get(__name__)

# 클린의 범위 — **문서 7 §7.6-4가 이번 개정에서 확정했다.**
#
#   `data/` 전체 (**예외: `doc_types.json`**) + `parsed/` + `extract/` 전체.
#   `review/`는 지우지 않는다. `export/`는 파생물이라 어느 쪽이든 무해하다.
#
# **`parsed/`·`extract/`는 체크포인트다** — 파일이 남으면 다음 실행이 앞 단계
# (파싱·추출)를 건너뛰어, 회귀 규약(§7.5-7)이 막으려는 순서 의존이 그대로 생긴다.
#
# **`doc_types.json`은 예외다** — 등록 파이프라인이 **승인 1회로** 등재한 것이라
# 재생성되지 않으며 `review/{doc_type}/approval.json`과 한 쌍이다. 지우면 사람 쪽과
# 시스템 쪽이 등록 여부를 다르게 알게 되고, 다음 인입이 그 문서를 "미등록 →
# 구축 모드"로 되돌린다.
#
# **`review/{doc_type}/approval.json`도 재생성되지 않는 사람 판단 기록이다**(§7.8).
# 클린이 그것을 지우면 `init --fresh` 한 번에 승인 이력이 사라진다 — 실증했다.
# **지우는 것은 폴더 둘이다**(B78 1b) — ③진실(`data/`)과 ④작업(`work/`).
# `registry/`(등록 — 사람 승인 1회)와 설정은 **지우지 않는다**: 재생성되지 않는다.
# 파생(`export/`)도 지운다 — 되돌려 읽지 않는 것이라 지워도 무해하고, 옛 판이
# 남아 있으면 사람이 그것을 지금 상태로 읽는다.
#
# **`KEEP_IN_DATA` 예외가 사라졌다**(B78 1b): 등록부가 진실 옆에 있어서 생긴
# 예외였고, 이제 등록은 다른 폴더다 — 예외 없이 폴더째 지운다.
WIPE_TIERS = ("data", "work", "export")

# 빈 상태의 형태 — 문서 7 §7.2 말미가 정본이다.
EMPTY = {
    store.CHUNKS: {"chunks": {}, "describes": []},
    store.DICTIONARY: {},
    store.QUEUE: [],
    # **층 등록부와 문서 대장도 빈 객체로 초기화한다**(문서 7 §7.2 빈 상태 불릿) —
    # 전자는 부트스트랩이 매 실행 재생성하고, 후자는 인입이 채운다. 파일이 아예
    # 없으면 클린의 대조 단위가 "파일 없음"과 "빈 파일"로 갈린다.
    store.REGISTRY: {},
    store.DOC_REGISTRY: {},
}


def kept():
    """**fresh 기본이 남기는 것** 넷(B106 ①) — `[(표기, 경로)]`. 자리는 소유자에게 묻는다(경로 조립 0)."""
    return [("산문 추출", paths.extract()), ("구조 지도", paths.work("struct_maps")),
            ("판정 대장", store.path("ingest_log")), ("좌표 학습", store.path(store.COORD_LEARNED))]


def _size(p):
    """`(파일 수, 바이트)` — 락 파일은 세지 않는다(상태가 아니다)."""
    p = Path(p)
    if p.is_file():
        return (0, 0) if p.name.endswith(".lock") else (1, p.stat().st_size)
    n = b = 0
    for f in p.rglob("*") if p.is_dir() else ():
        if f.is_file() and not f.name.endswith(".lock"):
            n, b = n + 1, b + f.stat().st_size
    return n, b


def fresh(all_=False, keep=(), report=None):
    """지운다 — **기본은 비용이 든 산출 넷(`kept()`)과 `keep`을 남기고**, `all_`이면 `data/`·`work/`·`export/`를
    폴더째(클린 — 회귀 바닥).

    등록(`registry/`)과 설정은 어느 쪽이든 남는다: 사람 승인 1회의 산출이라 재생성되지 않는다
    (구판의 `KEEP_IN_DATA` 예외가 그 사실을 파일 단위로 흉내 내던 것이다). `report`(dict)를 주면
    `kept`·`wiped`에 `[(표기, 파일 수, 바이트)]`를 채운다 — 화면이 「남긴 것 · 지운 것 · 크기」를 말한다.

    **mock 루트의 클린은 사람 판단 기록도 비운다**(B106 ③) — `ops_log.json`이 ②등록으로 옮겨 클린이
    지우지 않게 됐는데, 회귀 바닥은 기록 0에서 시작해야 한다(옮기기 전 정의 그대로 · `seed_layers`와 같은 결 —
    운영 루트의 ②등록은 클린도 건드리지 않는다).
    """
    rep = report if report is not None else {}
    rep["kept"], rep["wiped"] = [], []
    hold = [] if all_ else [p for _l, p in kept()] + [Path(k) for k in keep]
    for label, p in ([] if all_ else kept()):
        n, b = _size(p)
        if n:
            rep["kept"].append((label, n, b))
    for tier in WIPE_TIERS:
        root = getattr(paths, tier)()
        n, b = _size(root)
        if all_:
            shutil.rmtree(root, ignore_errors=True)
        else:
            k_n = sum(_size(h)[0] for h in hold if _under(h, root))
            k_b = sum(_size(h)[1] for h in hold if _under(h, root))
            n, b = n - k_n, b - k_b
            _wipe_except(root, hold)
        rep["wiped"].append((f"{tier}/", n, b))
    if all_ and paths.is_mock_home():
        store.path(store.OPS_LOG).unlink(missing_ok=True)
    return rep


def _under(p, root):
    try:
        Path(p).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _wipe_except(root, hold):
    """`root` 아래를 지우되 `hold`(남길 경로)와 그 조상 폴더는 남긴다."""
    root = Path(root)
    if not root.is_dir():
        return
    hold = [Path(h).resolve() for h in hold]
    for child in sorted(root.iterdir()):
        c = child.resolve()
        if any(c == h for h in hold):
            continue                                        # 남길 것 자체
        if child.is_dir() and any(_under(h, c) for h in hold):
            _wipe_except(child, hold)                       # 남길 것의 조상 — 안으로
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def seed_layers(force=False):
    """**층 자산의 seed 심기** — mock 루트에만 한다 (B79 ①).

    층 자산(`layers/<층>/{config,skeleton}.json`)은 ②등록 단이다 — 사내가 고쳐
    승인 1회 하는 것이라 **운영 루트에서는 클린이 건드리지 않는다**(문서 7 §7.6-4).
    mock 루트는 반대다: 회귀의 바닥이므로 **언제나 레포 seed 판**이어야 한다.
    그래서 자리로 가른다 — 모드 분기가 아니라 「어느 루트인가」로.

    `force`면 지우고 다시 심는다(`--fresh`). 아니면 없을 때만 심는다.
    """
    if not paths.is_mock_home():
        return None                      # 운영 ②등록 — 사람이 넣고 migrate가 옮긴다
    dst = paths.layers()
    if force:
        shutil.rmtree(dst, ignore_errors=True)
    if dst.exists():
        return None
    shutil.copytree(paths.seed_layers(), dst,
                    ignore=shutil.ignore_patterns("__pycache__", ".*"))
    return dst


def ensure():
    """빈 상태를 만든다 — 이미 있는 파일은 건드리지 않는다.

    층 그래프는 `GraphStore` 경유로 만든다(문서 1 B6) — **저장 파일의 경로도 이름도
    이 모듈이 알지 않는다.** 경로를 직접 조립하면 저장 계층 경계가 "여는 코드"만 막고
    "저장 위치를 아는 코드"를 놓친 상태로 되돌아간다 — 회귀 st가 그것을 잡는다.
    """
    made = []          # 폴더는 store의 쓰기가 만든다 (B77 ④ — 자리 소유는 하나)
    for name, empty in EMPTY.items():
        if not store.path(name).exists():
            store.write(name, empty)
            made.append(name)
    for layer in discover():
        g = GraphStore.for_layer(layer)
        if not g.exists():
            g.load()                 # nodes={}, edges=[]
            g.save()
            made.append(f"{layer} 그래프")
    return made


def init(fresh_=False, all_=False, keep=(), report=None):
    """`fresh_` — 지우고 다시 만든다(기본은 보존 넷을 남긴다 · `all_`이면 클린 · `keep`은 더 남길 경로 —
    재구축 계획 파일). 돌려주는 것은 새로 만든 빈 상태 목록이다."""
    if fresh_:
        fresh(all_=all_, keep=keep, report=report)
    # **층 자산이 먼저다** — `ensure()`가 층마다 빈 그래프를 만들고, 층 목록은
    # 상태 루트의 `layers/`가 정한다(B79 ①). mock 루트의 seed 되심기는 **클린의 몫**이다(B106 ① —
    # 기본 fresh는 재구축의 바닥이라 ②등록을 건드리지 않는다: 사람이 고친 seed로 재구축한다).
    seeded = seed_layers(force=fresh_ and all_)
    made = ensure()
    if seeded:
        made.append(f"층 seed {seeded.name}/")
    _LOG.info("init%s — 빈 상태 %d개 생성 (%s)",
              (" --fresh --all" if all_ else " --fresh") if fresh_ else "", len(made),
              ", ".join(made) or "없음")
    return made
