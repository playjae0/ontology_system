# -*- coding: utf-8 -*-
"""칸 0.3 — doctor의 **운영 상태 폴더 화면** — 읽기만 (B111 ① · `doctor.py`에서 나눴다 — §7 파일 상한).

    python -m cli.doctor_view <head|config|transition>      (doctor가 셸 환경 그대로 부른다)

**왜 따로 도나.** doctor 본체는 격리 환경(mock · 기본 mock 루트 — `gateway.isolate`)에서 돌고 그 아래 실행이
전부 그 환경을 물려받는다. 운영 루트에 대해 하는 일 — 머리 상태 줄 · 층 이름 · 정합 · 설정 파일 줄 · 사내 전환
판정 — 은 **셸 환경 그대로의 프로세스 하나**가 읽어야 한다: 루트는 프로세스당 한 번 정해지고 모듈 상수가 그 자리를
잡으므로 한 프로세스가 두 루트를 오가지 않는다. 이 진입은 **공통 진입(`cli/_entry`)을 지나지 않는다** — 로그 ·
대장 채움을 운영 루트에 쓰지 않는다. 끝 줄이 [필요] 수다(`NG_TAIL`).

화면 원자(마크 · `line` · `head`)도 여기 산다 — doctor 본체와 이 화면이 같은 것을 쓴다(두 벌 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK, WARN, NG = "  OK ", " 주의 ", " 필요 "
# **[다음]은 결함이 아니다.** §④는 「사내에서 남은 작업」을 적는 자리인데 §①②③과
# 같은 [주의]를 쓰고 있었고, 실제로 사용자가 그것을 고장으로 읽었다(2B 실사고).
# 마크를 갈라 「할 일」과 「고장」이 화면에서 구분되게 한다. `_fail`은 [필요]만 센다.
NEXT = " 다음 "
_fail = 0

#: 끝 줄 — doctor 본체가 이 화면의 [필요] 수를 받는다.
NG_TAIL = "@@doctor-ng "


def line(mark, label, detail=""):
    global _fail
    if mark == NG:
        _fail += 1
    print(f"  [{mark}] {label}" + (f"\n         {detail}" if detail else ""))


def head(title):
    print(f"\n{'─' * 66}\n■ {title}\n{'─' * 66}")


def fails():
    """지금까지의 [필요] 수."""
    return _fail


def add(n):
    """하위 화면의 [필요] 수를 더한다(doctor 본체가 받는다)."""
    global _fail
    _fail += n


# ================================================================ ④ 사내 전환
def transition():
    head("④ 사내 전환 — 다음에 무엇을 해야 하나 (실측 판정)")
    print("  아래는 결함이 아니라 사내에서 남은 작업이다. `[필요]`가 뜨면 그때가 고장이다.\n")
    from core import paths                                              # noqa: E402
    from core.state import registry, store                              # noqa: E402

    # ── 1. 골격 seed ──────────────────────────────────────────────
    # **좌표 층은 이름이 아니라 카테고리로 찾는다**(B85 ②) — 폴더가 `equipment`여도
    # 여기가 그 층을 본다. 좌표 층이 없으면 그 사실을 한 줄로 말하고 지나간다.
    from core.state.bootstrap import NoCoordLayer, coord_layer, load_config  # noqa: E402
    try:
        _coord = coord_layer()
    except NoCoordLayer:
        _coord = None
    _src = ((load_config(_coord).get("skeleton") or {}).get("source")
            if _coord else None)
    _seed_p = paths.layers(_coord, _src) if (_coord and _src) else None
    seed = (json.loads(_seed_p.read_text(encoding="utf-8"))
            if _seed_p and _seed_p.exists() else {})
    snap = (store.read(store.SKELETON_LIST, {}).get(_coord) or {}) if _coord else {}
    line(NEXT, f"[1] 골격 seed가 아직 창작 mock이다 — 노드 {snap.get('count', '?')} · "
               f"seed 문법 v{seed.get('seed_format')}",
         "**사내 첫 작업이 이것이다.** 층 자산은 상태 루트에 산다(B79 ①) —\n"
         f"         {_seed_p or paths.layers('<좌표 층>', '<skeleton.source>')}\n"
         "         을 사내 공정 체계로 바꾸고 `python run.py bootstrap`.\n"
         "         코드는 한 줄도 안 바뀐다 — seed는 데이터다.\n"
         "         형식은 docs/skeleton_seed.md · 마커 4종(:: · @split · @unordered · @noflow)")

    # ── 1′. role 배정 실험 ────────────────────────────────────────
    # **등록 세션 진입 전에 이것이 먼저다**(갭 spec-A-201 · role-136).
    # 실험 없이 register generate로 가면 생성 세션이 무엇을 물어볼지 모른 채
    # 시작한다 — 6지선다의 여섯째 경로(UNMAPPABLE)가 무엇인지를 먼저 본다.
    line(NEXT, "[1′] 사내 문서로 **role 배정 실험**을 먼저 돌린다",
         "`python run.py register roles <문서.xlsx> [헤더행]`\n"
         "         실행만 하고 등록부는 건드리지 않는다 — 어느 열이 UNMAPPABLE로\n"
         "         떨어지는지가 **생성 세션의 첫 안건**이다. 답을 준비하고 [2]로 간다")

    # ── 2. doc_type 등록 ──────────────────────────────────────────
    reg = [k for k, v in registry.all_doc_types().items() if v["status"] == "registered"]
    line(NEXT if not reg else OK,
         f"[2] 사내 doc_type 등록 {len(reg)}종",
         "표본 2부를 골라 `python run.py register generate <이름> <층> <표본...>` →\n"
         "         `review` → `confirm --by <승인자>`. 검수 뷰 HTML을 브라우저로 연다"
         if not reg else f"등록됨: {reg}")

    # ── 1″. 사내 손잡이 (B91 ⑤) ──────────────────────────────────
    # 사내 실측으로 정할 값의 파일 — 있으면 기본과 다른 값이 몇인지. 분포는 `show knobs`가 가리킨다.
    from core.state import knobs as _kn                                  # noqa: E402
    if _kn.error() is not None:
        line(NG, "[1″] 사내 손잡이 파일이 어긋났다 — 운영 명령이 멈춘다", str(_kn.error()))
    else:
        _kr = _kn.rows()
        _kd = [r["name"] for r in _kr if r["value"] != r["default"]]
        line(OK, f"[1″] 사내 손잡이 — 파일 {'있음' if paths.knobs().exists() else '없음(전부 기본값)'}"
                 f" · 기본과 다른 값 {len(_kd)}", (", ".join(_kd) + " — python run.py show knobs")
             if _kd else "값과 분포: python run.py show knobs")

    # ── 2′. 등록 스키마 재대조 (B90 ⑤) ───────────────────────────
    # **config를 바꾸면 이미 등록된 스키마가 어휘 밖으로 떨어질 수 있다** — 관문과 같은
    # 함수(G4C·G4D·G4E)로 등록 전부를 다시 대조한다. 어긋난 것은 doc_type을 고칠 일이다.
    from cli.register import recheck                                     # noqa: E402
    _rc = recheck.run()
    _bad = [l for _dt, ok, l in _rc if not ok]
    line(OK if not _bad else NEXT,
         f"[2′] 등록 스키마 재대조 — {len({dt for dt, _o, _l in _rc})}종 · 어긋남 {len(_bad)}",
         "\n         ".join(_bad) if _bad else "")

    # ── 3. LLM 지점 10종의 **도달 가능성** ─────────────────────────
    # **문자열을 세지 않는다.** 여태 이 자리가 소스에 `use_mock`·`allow_mock` 같은
    # 낱말이 있는지를 보고 「분기가 서 있다」로 보고했다 — 그래서 ⑦구조 지도가
    # **어느 설정에서도 모델을 부를 수 없는 상태로 9/9 초록**이었다(B48).
    # 이제 재는 것은 「실 호출 경로를 타서 미설정 실패에 닿는가」이고, 판정은
    # 회귀와 **같은 탐침 파일**(tests/points_probe.py)을 실행해서 한다.
    from core.llm.gateway import POINTS                                   # noqa: E402
    import importlib.util as _ilu                                 # noqa: E402
    _spec = _ilu.spec_from_file_location("points_probe",
                                         ROOT / "tests" / "points_probe.py")
    _pp = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_pp)
    res, _r = _pp.run()
    reached = [POINTS[k] for k in POINTS if res.get(k) == "NotConfigured"]
    missing = [f"{POINTS[k]} — {res.get(k, '(미실행)')}"
               for k in POINTS if res.get(k) != "NotConfigured"]
    line(OK if not missing else NG,
         f"[3] LLM 지점 {len(reached)}/{len(POINTS)}종의 실호출 갈래가 호출자로부터 "
         f"도달 가능하다",
         ("게이트웨이 골조는 섰고 **설정만 비어 있다** — 게이트웨이 주소·채팅 모델을\n"
          "         주면 USE_MOCK=0으로 돈다. 미설정 상태의 USE_MOCK=0은 조용히 mock으로\n"
          "         떨어지지 않고 명시적으로 실패한다(문서 7 §7.6-B-4).\n"
          "         **모델 없이도 전 파이프라인이 돈다** — 정밀도만 규칙 수준이다\n"
          "         연결 확인: python run.py llm-check"
          ) if not missing else
         ("실 경로가 미설정 실패에 닿지 않는 지점 — 「통과」는 대체 갈래가 돌았다는\n"
          "         뜻이고, 그것은 배선이 있다는 뜻이 아니다(문서 7 §7.6-B-2):\n"
          + "\n".join(f"         · {m}" for m in missing)))

    # ── 4. 계기판 첫 측정 ─────────────────────────────────────────
    line(NEXT, "[4] 계기판은 mock 수치다 — 품질 측정이 아니다",
         "실데이터 인입 후 `python run.py gauges`가 첫 진짜 측정이다.\n"
         "         그 수치가 P7 판정(하이브리드·랭킹·저장 전환)의 근거가 된다")

    # ── 5. 반출입 경계 ────────────────────────────────────────────
    line(OK, "[5] 반출입 경계 — 코드는 들어가고, 실물 문서는 나오지 않는다",
         "이 레포에 사내 유래 정보가 0이다(mock은 전량 창작). 반입은 자유롭고,\n"
         "         사내에서 만든 어댑터·seed·문서는 **밖으로 내보내지 않는다**")

    print(f"\n  {'권장 순서':<10} ① seed 교체 → bootstrap  ② doc_type 1종 등록  "
          f"③ 실문서 인입  ④ 질의  ⑤ 계기판")
    print(f"  {'더 볼 것':<10} docs/이연대장.md §2 — 사내 반영 수준 · 사내에서 확인할 것 · 남은 일")


# ================================================================ 머리 · 설정
def config_lines():
    """운영 셸의 **모드 · 설정 파일**(B98 ④ · B111 ①) — 처음 찾은 파일 하나만 읽는다 · 무시된 파일을 말한다.

    모드는 점검의 하위 실행과 무관하다(그것들은 격리 환경 — 머리말) — 여기는 사람이 운영 명령을 칠 때의 모드다.
    """
    from core.llm import gateway as _gw                                   # noqa: E402
    try:
        _src = _gw.config_sources()
        line(WARN if _src["ignored"] else OK, "LLM 설정 파일", _gw.sources_line())
        live = not _gw.use_mock()
    except _gw.NotConfigured as e:
        line(WARN, "LLM 설정 파일", str(e))
        live = None
    _sub = ("점검의 하위 실행(클린 · 회귀 · 미설치 모사 · run.py all · 질의)은 이와 무관하게 mock 격리\n"
            "         루트에서 돈다 — 운영 상태 폴더는 읽기만 한다")
    if live is not None:
        line(OK, f"운영 명령의 모드 — {'실호출' if live else 'mock'}",
             ("실호출 = 게이트웨이를 부른다(연결 확인: python run.py llm-check)" if live else
              "mock = LLM 없이 전 경로가 로컬로 돈다(네트워크 0) · 실호출은 llm.json의 \"USE_MOCK\": 0")
             + "\n         " + _sub)


def layer_name_line():
    """**층 이름 = 폴더 이름**(B99 ①) — `bootstrap`·사전 점검과 같은 함수(`catalog.layer_name_problems`)."""
    from core.state import catalog as _cat99                              # noqa: E402
    try:
        _ln = _cat99.layer_name_problems()
        line(NG if _ln else OK, "층 config \"layer\" = 폴더 이름",
             "\n         ".join(_ln) if _ln else "층 전부 일치")
    except (OSError, ValueError) as e:
        line(WARN, "층 config \"layer\" = 폴더 이름", f"층 config를 읽지 못했다 — {e}")


def integrity_line():
    """**정합**(B99 ⑩) — 사라진 노드를 가리키는 큐 항목 · 사전 표기 · 끝점 없는 엣지(층별). 정리는 `ops tidy`."""
    from core.state import integrity                                      # noqa: E402
    try:
        found, _g = integrity.state_scan()
    except Exception as e:                                                # noqa: BLE001
        line(WARN, "정합 — 사라진 노드를 가리키는 것", f"재지 못했다 — {type(e).__name__}: {e}")
        return
    nq, nd, ne = integrity.count(found)
    per = " · ".join(f"{k} {len(v)}" for k, v in sorted(found["edges"].items()))
    line(NG if (nq or nd or ne) else OK, "정합 — 사라진 노드를 가리키는 것",
         f"큐 {nq} · 사전 표기 {nd} · 끝점 없는 엣지 {ne}" + (f"({per})" if per else "")
         + ("\n         ▶ 다음 줄 — 계획: python run.py ops tidy all --actor <이름> · 지운다: … --apply"
            if (nq or nd or ne) else ""))


def state_line():
    """머리 한 줄 — **지금 어느 상태를 보고 있나**(B78 1b · 요청문 ②).

    화면 맨 앞이 자리를 말해야 「어느 폴더의 수를 본 것인가」가 갈리지 않는다.
    이관 전이면 그 사실도 여기서 말한다 — 수가 0인 이유가 「비었다」가 아니라
    「아직 옮기지 않았다」일 수 있다.
    """
    from core import paths           # noqa: E402
    from core.llm import gateway
    from core.state import migrate, registry, store
    from router import discover                                     # noqa: E402
    dts = registry.all_doc_types()
    builtin = sum(1 for v in dts.values() if v.get("status") == "builtin")
    # **좌표 층의 이름을 첫 줄에 싣는다**(B85 ②) — 폴더 이름을 바꾼 사람이
    # 「지금 어느 층이 좌표 층인가」를 여기서 확인한다. 없으면 없다고 말한다.
    from core.state.bootstrap import NoCoordLayer, coord_layer       # noqa: E402
    try:
        _coord = coord_layer()
    except NoCoordLayer:
        _coord = "**없다**"
    # **층 공통 config의 판을 같은 줄에**(B90 ①) — 집·겸·이름 규칙이 어느 판으로 도는가.
    from core.state import catalog as _catalog                      # noqa: E402
    _cv = _catalog.version()
    _common = (f"v{_cv}" if _cv is not None
               else "없다 — bootstrap이 초안을 만든다" if not gateway.use_mock()
               else "없다(mock — 층 선언에서 세운다)")
    print(f"  상태 폴더 {paths.home()}{paths.home_note()} · 모드 "
          f"{'mock' if gateway.use_mock() else '실호출'} · 등록 {len(dts)}종"
          + (f"(내장 {builtin})" if builtin else "")
          + f" · 층 {len(discover())}(상태 루트)"
          + f" · 좌표 층 {_coord}"
          + f" · 공통 config {_common}"
          + f" · 문서 {len(store.read(store.DOC_REGISTRY, {}))}")
    try:
        for _w in _catalog.warnings():               # 겸 집 불일치 — 경고 (B91 ⑥)
            print(f"  ⚠ 공통 config 겸 {_w}")
        for _w, _nx in _catalog.mirror_warnings():   # 미러 규칙 ≠ 집 — 경고 (B100 ④)
            print(f"  ⚠ 미러 규칙 {_w}\n    ▶ 다음 줄 — {_nx}")
        from core.state import catalog_sync as _cs   # 겸 상태 — 골격 카테고리마다 (B93 ③)
        for _warn, _m in _cs.coord_status():
            print(f"  {'⚠' if _warn else '·'} {_m}")
    except _catalog.CatalogError:
        pass                                         # 카탈로그 거부는 bootstrap이 말한다
    if migrate.needs_migration():
        print("  ⚠ 이관 전이다 — python run.py platform migrate "
              "--from <옛 코드 폴더>  (그 전까지 운영 명령은 멈춘다)")


def _head_view():
    state_line()
    layer_name_line()
    integrity_line()


#: 운영 루트를 읽는 화면 — doctor 본체의 `operating()`이 이름으로 부른다.
VIEWS = {"head": _head_view, "config": config_lines, "transition": transition}


def main(argv):
    """화면 하나를 그리고 끝 줄에 [필요] 수."""
    part = argv[0] if argv else ""
    if part not in VIEWS:
        print(f"모르는 화면 {part!r} — {', '.join(VIEWS)}", file=sys.stderr)
        return 2
    VIEWS[part]()
    print(f"{NG_TAIL}{_fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
