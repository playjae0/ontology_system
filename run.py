# -*- coding: utf-8 -*-
"""칸 0.3 — 파이프라인 진입점 — CLI+파일 (구현문서 §0).

모든 단계는 subprocess로 호출 가능해야 한다(§16.1 플랫폼화 인지 계약).
**build는 직렬 실행**이다 — 저장이 비원자적이라 호출부가 직렬화를 보장한다.

사용:
  **mock 관문**: 사람이 치는 운영 명령(register generate/review/confirm · parse run ·
  build · ingest-file/ingest-dir · query)은 mock 모드에서 실행 전에 멈춘다 —
  계속하려면 `--allow-mock`을 적는다 (문서 7 §7.6-B-1 · B48).

  python run.py init [--fresh]     클린 상태 — data/ 하위를 빈 상태로 생성·재생성
  python run.py bootstrap [--dry-run]  층 공통 config 맞추기 + 층 골격 심기 (n10 · --dry-run은 계획만)
  python run.py build <parsed.json...> [--allow-duplicate]
                                   계약 JSON 인입 — **플랫폼 계약 이름**(§7.1).
                                   --allow-duplicate는 duplicate_doc_hold 보류의
                                   ㉡ 해제다(다른 문서로 인정 — 문서 2 §2.7-①)
  python run.py ingest <파일...>   상동 (구 이름 — 같은 기능을 두 이름으로 두지 않으려
                                   남기되, 계약 이름은 build다)
  python run.py all                bootstrap + 픽스처 계약 JSON 전량 인입
  python run.py golden init        골든셋 빈 문항 틀 (기준 120건 · 문서 5 §5.5-2)
  python run.py golden score [--set F] [--k 8] [--json]
                                  채점 4축 + BM-25 대조군 (LLM 0 — answer()까지만)
  python run.py show bm25 "<질문>" [k]
                                  BM-25 대조군을 직접 본다 (그래프·사전 안 읽는다)
  python run.py viewer [--port N] [--no-browser]
                                  그래프 뷰어 + 질문 칸 (읽기 전용 · 표준 라이브러리만)
  python run.py query "<질문>" [--json]
                                  질의 4단 (cli/query.py 라우터로 위임).
                                  --json = 답 묶음을 stdout에 한 덩어리로 (모드 줄은 stderr)
  python run.py ops <연산> ...     I축 4연산 (cli/ops.py로 위임)
  python run.py gauges             계기판 8종 (cli/platform.py로 위임)
  python run.py platform <명령>    플랫폼 창구 4′ (cli/platform.py로 위임)
  python run.py scan <문서> ...    n9 지문 스캔 (cli/scan.py로 위임)
  python run.py parse <명령> ...   파서 n7 (cli/parse.py로 위임 — run·head·build)
                                   run은 `<어댑터.py> <문서> [출력.json] [--doc-id X]` —
                                   doc_id 생략 시 파일명에서 파생(ingest-file과 같은 규칙)
  python run.py register <명령>    n6 구축 모드 등록 (cli.register 패키지로 위임)
  python run.py ingest-file <문서> [--doc-type X] [--dry-run]
                                   일괄 투입 1건 — 선택(지문 스캔 유일 일치 또는 지정)
                                   → 파싱 → 인입 (B46 · cli/ingest.py로 위임)
                                   시트 둘 이상인 prose 엑셀은 **시트 역할 관문**을 지난다
                                   (`--sheets "2-3:prose 4:ref *:ref"` · 자동 `--sheets auto`)
  python run.py ingest-dir <경로> [--doc-type X] [--dry-run]
                                   경로의 문서 전부를 문서 단위 독립으로 투입
  python run.py skeleton-status <층>
                                   골격 seed 문법 판정만 — 확정·뷰 없음 (칸 0.1)
  python run.py skeleton-confirm <층> --by <이름>
                                   골격 확정 — 판정 → 뷰 대조 → 기록
  python run.py show <명령> ...    산출물 열람 — tree·node·doc·report·chunk·edges·schema·meta
  python run.py export <형식>      파생물 — cypher · csv · mermaid
"""
import json
import sys
from pathlib import Path

from core.state import log, store
from core.state.bootstrap import bootstrap, open_graph
from core.state.skeleton import SeedError
from core.build.entry import run_document
from router import discover

ROOT = Path(__file__).resolve().parent


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cmd_init(args):
    """클린 상태의 **단일 정의**. 회귀 규약과 완료판정 4번이 같은 바닥을 쓰게 한다."""
    from core.state.init import init
    made = init("--fresh" in args)
    print(f"[init] 빈 상태 {len(made)}개 — {', '.join(made) or '이미 있음'}")


def _sync_screen(p):
    """맞추기 계획을 한 줄씩 — 무엇을 더하고 지우고 무엇을 사람에게 묻나."""
    from core import paths
    head = "[bootstrap] 공통 config"
    if p["new"]:
        print(f"{head} 없음 — 층 config에서 만든다 → {paths.show(paths.common())}")
    for c, lay, skel in p["add"]:
        print(f"{head} + '{c}' (home {lay} — " + (f"골격이 {lay}에 있다)" if skel else f"{lay}만 선언)"))
    for c, lay in p["fill"]:
        print(f"{head} '{c}' home 빈칸 → {lay} (골격이 {lay}에 있다)")
    _fresh = [c for c, have, _w in p["used"] if have is None and not p["new"]
              and c not in {x for x, *_ in p["add"] + p["ask"]}]
    if _fresh:
        print(f"{head} used_by 채움 — {len(_fresh)}개 카테고리에 쓰는 층을 적었다(층 config에서 · "
              f"사람이 관리하지 않는다)")
    for c, have, want in p["used"]:
        if p["new"] or have is None:
            continue                                   # 새 항목은 + 줄이 말한다
        plus, minus = sorted(set(want) - set(have or [])), sorted(set(have or []) - set(want))
        print(f"{head} used_by '{c}'" + "".join(f" + {x}" for x in plus)
              + "".join(f" − {x}" for x in minus) + " (used_by는 층 config에서 온다)")
    for c in p["drop"]:
        print(f"{head} − '{c}' (어느 층도 선언하지 않고 노드 0)")
    _new_category_warning(p)
    for c, lays in p["sk_dup"]:
        print(f"{head} [상태] 골격 카테고리 '{c}'를 층 {lays}의 골격이 함께 가진다 — 같은 뜻 노드가 "
              f"두 그래프에 두 벌 생긴다 · 골격은 한 층만 갖는다")
    for c, home, lay in p["sk_home"]:
        print(f"{head} [상태] '{c}'의 home은 {home}인데 골격은 {lay}에 있다 — 골격 노드는 {lay} "
              f"그래프에 심긴다 · home을 {lay}로 고친다")
    for c, lays in p["ask"]:
        print(f"{head} [상태] '{c}' home 빈칸 — 여러 층이 선언했다 {lays} — 그중 하나로 채운다")
    for c, home, n in p["stuck"]:
        print(f"{head} [상태] '{c}'를 어느 층도 선언하지 않는데 {home} 그래프에 노드 {n}개가 "
              f"남아 있다 — 층 config에 되살리거나 재빌드(init --fresh → bootstrap → 재인입)")
    for c, home, old, n in p["moved"]:
        print(f"{head} [상태] '{c}'의 home을 {old} → {home}로 바꿨지만 {old} 그래프에 {c} 노드 "
              f"{n}개가 있다 — 재빌드(init --fresh → bootstrap → 재인입) 또는 home을 되돌린다")
    if p["new"] and p["catalog"].get("canonical_scope"):
        print(f"{head} canonical_scope ← 층 config에서 옮김 (층 config에서는 지운다 — 두 곳 0)")


def _new_category_warning(p):
    """**새 카테고리 경고**(B94 ②) — 없던 카테고리를 더할 때 기존 카탈로그를 보인다(표시 · rc 불변).

    같은 뜻을 다른 이름으로 선언하면 두 종류로 갈려 층 사이 호환이 끊긴다 — 사람이 알아챌
    자리가 여기다. 같은 뜻인지는 사람이 본다(유사도·LLM 판정 0).
    """
    from core.state import catalog_sync, log as _log
    lines = catalog_sync.existing_lines(p)
    if not lines:
        return
    _lg = _log.get("run.bootstrap")
    for c, lays in catalog_sync.new_categories(p):
        msg = (f"새 카테고리 '{c}'({', '.join(lays)}) — 같은 뜻의 기존 카테고리가 있으면 그 이름을 "
               f"쓴다(같은 이름이어야 노드 하나로 모인다):")
        print(f"[bootstrap] {msg}")
        _lg.info(msg)
        for ln in lines:
            print(f"     {ln}")
            _lg.info("  기존 %s", ln)


def _catalog_gate(dry_run=False):
    """**층 공통 config 먼저** (B90 ① · B92) — 층 config와 맞추고, 어긋나면 층을 심기 전에 멈춘다.

    한 층만 선언한 카테고리는 자동으로 더하고 · 선언도 노드도 없는 카테고리는 지운다 ·
    새 결정(여러 층이 선언한 카테고리의 집 · 노드가 남은 제거 · 집 변경)은 사람에게 묻고
    멈춘다(`core/state/catalog_sync.py`). 이미 있는 항목의 `home`·`also`는 건드리지 않는다.
    `dry_run`이면 계획만 보이고 아무것도 쓰지 않는다. 멈추면 1.
    """
    from core import paths
    from core.state import catalog, catalog_sync
    if paths.common(draft=True).exists():
        print(f"[bootstrap] {paths.show(paths.common(draft=True))}는 쓰지 않는 파일이다(지워도 된다)")
    exists = paths.common().exists()
    if exists or not paths.is_mock_home():            # mock 루트에 파일이 없으면 층 선언에서 세운다
        cur = json.loads(paths.common().read_text(encoding="utf-8")) if exists else None
        p = catalog_sync.plan(current=cur)
        _sync_screen(p)
        if dry_run:
            print(f"[bootstrap] --dry-run — 계획만 보였다(공통 config·그래프 쓰기 0) · "
                  f"{'바뀔 것 있음' if catalog_sync.changed(p) else '바뀔 것 없음'}"
                  f"{' · 멈출 것 있음' if catalog_sync.blocked(p) else ''}")
            return 1 if catalog_sync.blocked(p) else 0
        if catalog_sync.changed(p):
            catalog_sync.apply(p)
        if catalog_sync.blocked(p):
            print(f"  근거 — {paths.show(paths.common())}\n"
                  f"  ▶ 다음 줄: 위 줄을 고치고 python run.py bootstrap   (미리 보기: --dry-run)")
            return 1
    elif dry_run:
        print("[bootstrap] --dry-run — mock 루트 · 공통 config 없음(층 선언에서 세운다) · 쓰기 0")
        return 0
    try:
        bad = catalog.problems()
    except catalog.CatalogError as e:
        print(f"[bootstrap] {e}")
        return 1
    for tag, msg in bad:
        print(f"[bootstrap] [상태] 공통 config {tag} {msg}")
    if bad:
        print(f"  근거 — {paths.show(paths.common())}\n"
              f"  ▶ 다음 줄: 위 줄을 고치고 python run.py bootstrap")
        return 1
    for msg in catalog.warnings():                 # 겸 집 불일치 — 경고만 (B91 ⑥)
        print(f"[bootstrap] ⚠ 공통 config 겸 {msg}\n"
              f"  ▶ 의도가 아니면: 두 카테고리의 home을 같은 층으로 맞춘다 — {paths.show(paths.common())}")
    return 0


def cmd_bootstrap(args=()):
    dry = "--dry-run" in args
    rc = _catalog_gate(dry_run=dry)
    if rc or dry:
        return rc
    for layer in discover():
        try:
            g, m, ids, _flow = bootstrap(layer)      # 파생 흐름은 loader가 출력한다
        except SeedError as e:                       # 골격 파일 부재·문법 — 문면으로 (B85 ①)
            print(f"[bootstrap] {layer}: [상태] {e}")
            rc = 1
            continue
        if g is None:
            print(f"[bootstrap] {layer}: 골격 선언 없음 — 내장 층이 아니다 (J10)")
            continue
        print(f"[bootstrap] {layer}: 노드 {m['nodes']} · 엣지 {m['edges']}")
        print(f"            계기판 7 graph {m['gauge7_graph_mb']}MB "
              f"({m['serializer']}) · 8 build {m['gauge8_build_seconds']}s")
    # **config를 바꾸면 등록 스키마를 다시 대조한다**(B90 ⑤) — 층은 섰다(rc는 층의 것).
    # FAIL은 doc_type을 고칠 일이지 층 적재의 실패가 아니다 — 줄과 다음 줄로 말한다.
    from cli.register import recheck
    recheck.screen()
    # **겸 상태**(B93 ③) — 골격 카테고리마다 자기 좌표 규칙이 켜졌나 · 표시일 뿐(rc 불변)
    from core.state import catalog_sync
    for warn, msg in catalog_sync.coord_status():
        print(f"[bootstrap] {'⚠ ' if warn else ''}{msg}")
    return rc


def cmd_ingest(paths, finalize=True, allow_duplicate=False):
    """`finalize`는 전 문서 인입 뒤 도는 빌드 말미 패스다 — 낱개 인입에서도 기본 수행한다."""
    for p in paths:
        from cli.ingest import build_screen        # 화면은 한 벌이다 (B72 ②)
        r, m, extracted = run_document(_load(p), allow_duplicate=allow_duplicate,
                                       notice=build_screen())
        mark = "보류" if r.status == "held" else "인입"
        tail = f"  ({r.reason})" if r.reason else (
            "  [추출 실행]" if extracted else "  [추출 체크포인트 재사용]")
        print(f"[{mark}] {r.doc_id}: record {len(r.record_ids)} · "
              f"chunk {len(r.chunk_ids)}{tail}")
    if finalize:
        from core.build.entry import finalize as _fin
        _fin()


def cmd_all():
    from core.llm import gateway
    print(f"  {gateway.mode_line()}")          # B42 ⑤
    cmd_bootstrap()
    from core.state import fixtures
    # **없으면 조용히 아무것도 안 하지 않는다** — 구판은 빈 glob로 0건 인입하고
    # 성공처럼 끝났다(§2-4 실측). 픽스처는 사내에서 없는 것이 정상이므로
    # 실패가 아니라 **말하고** 끝낸다.
    if not fixtures.PARSED.is_dir():
        print(f"[all] 인입할 계약 JSON이 없다 — {fixtures.PARSED}가 없다.")
        print("      사내에서는 정상이다: `run.py parse run …`으로 실문서를 파싱한 뒤")
        print("      `run.py build parsed/<doc_id>.json`으로 넣는다.")
        return
    mock = sorted(fixtures.PARSED.glob("*.json"))
    order = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
    idx = {n: i for i, n in enumerate(order)}
    cmd_ingest(sorted([p for p in mock if p.stem != "CP01B"],
                      key=lambda p: idx.get(p.stem, 99)))


def cmd_query(args):
    """질의는 **라우터가 단일 진입점**이다(§8-R1) — 여기서는 위임만 한다.

    출력 갈래(텍스트/`--json`)도 라우터가 갖는다 — 여기서 갈래를 만들면
    `-m cli.query`와 `run.py query`가 다른 것을 내게 된다(B52).
    """
    from cli.query import main
    return main(args)


def cmd_golden(args):
    """골든셋 틀·채점 — 위임만 한다(B54)."""
    from cli.golden import main
    return main(args)


def cmd_viewer(args):
    """검증 뷰어 — 그래프 위에서 질의가 도는지 본다(B52). 위임만 한다."""
    from cli.viewer.server import main
    return main(args)


def cmd_ops(args):
    """I축 도구도 subprocess 진입점을 갖는다(§16.1) — 위임만 한다."""
    from cli.ops import main
    return main(args)


def cmd_gauges():
    """계기판은 8종 전부가 현행이다(CH5 5.5) — 별도 호출로 계산한다(4′)."""
    from cli.platform import cmd_gauges as full
    full()


def cmd_platform(args):
    from cli.platform import main
    return main(args)


def cmd_scan(args):
    from cli.scan import main
    return main(args)


def cmd_parse(args):
    """파서는 별도 패키지지만 진입점은 하나로 모은다(§16.1 계약 1)."""
    from cli.parse import main
    return main(args)


def cmd_register(args):
    """n6 구축 모드 — 생성 → 검수 → 확정."""
    from cli.register.__main__ import main
    return main(args)


def cmd_ingest_batch(args):
    """일괄 투입 — `parse run` + `build` 위의 편의 명령(B46). 같은 코드를 부른다."""
    from cli.ingest import main
    return main(args)


def cmd_show(args):
    """산출물 열람 — 읽기 전용, 시각화 없이 텍스트로."""
    from cli.show import main
    return main(args)


def cmd_export(args):
    """파생물 내보내기 — 진실은 data/의 JSON이다(P5)."""
    from cli.export import main
    return main(args)


def cmd_skeleton_status(args):
    """골격 문법 판정만 — 확정도 뷰도 없다 (B61 ② · 칸 0.1)."""
    from cli.skeleton import cmd_status
    return cmd_status(args)


def cmd_skeleton_confirm(args):
    """골격 seed 확정 — 검증·뷰 대조·기록만. **파일은 사람이 놓는다**(문서 3 §3.7)."""
    from cli.skeleton import main
    return main(args)


def cmd_llm_check(args):
    """게이트웨이 연결 확인 — 붙었는가를 단계로 끊어 본다(문서 7 §7.6-B)."""
    from cli.llmcheck import main
    return main(args)


if __name__ == "__main__":
    # **전역 화면 플래그를 먼저 뗀다**(B81 ②③) — `-v`는 콘솔 로그를 INFO로 올리고
    # `--no-color`는 색을 끈다. 남기면 표본 경로·질문 문장으로 흘러 들어간다.
    from cli._screen import take_flags
    sys.argv[1:], _flags = take_flags(sys.argv[1:])
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    # 로깅 설정은 **진입점만** 한다(문서 7 §7.8) · 콘솔 WARNING · 파일 INFO(B81 ②)
    log.setup(command=cmd, console="INFO" if _flags["verbose"] else None)
    # **이관 관문**(B78 1b) — 옛 배치를 조용히 읽지 않는다. 푸는 명령 자신
    # (`platform migrate`)과 연결 점검은 관문 밖이다: 걸리면 칠 다음 줄이 없다.
    if not (cmd == "llm-check" or (cmd == "platform" and "migrate" in sys.argv[2:3])):
        from cli._gate import require_migrated
        require_migrated(cmd)
    # **층 자산 관문**(B79 ①) — 상태 루트에 층이 없으면 운영 명령은 멈춘다.
    # 관문 밖: 푸는 명령(`platform`)·연결 확인·상태를 만드는 `init`(층은 사람이
    # 넣는다)·`doctor`(진단이 막히면 무엇이 빠졌는지도 못 본다 — 제 파일이다).
    if cmd not in ("llm-check", "platform", "init"):
        from cli._gate import require_layers
        require_layers(cmd)
    # **mock 관문**(B48) — 여기서 도는 것은 제 모듈 main이 없는 운영 명령뿐이다.
    # register·parse·ingest-file/dir은 그쪽 main이 관문을 지나므로 두 번 걸지 않는다.
    if cmd in ("build", "ingest", "query"):
        from cli._gate import require_live_or_allow
        sys.argv = [sys.argv[0], cmd] + require_live_or_allow(sys.argv[2:], command=cmd)
    _rc = {"init": lambda: cmd_init(sys.argv[2:]),
     "bootstrap": lambda: cmd_bootstrap(sys.argv[2:]),
     # **`build`가 계약 이름이다**(문서 7 §7.1 진입점 계약) — 플랫폼이 subprocess로
     # 부르는 이름은 계약의 일부다. `ingest`는 같은 함수의 옛 이름이다.
     # `--allow-duplicate`는 duplicate_doc_hold 보류의 **㉡ 해제**다(문서 2 §2.7-①).
     "build": lambda: cmd_ingest([a for a in sys.argv[2:] if not a.startswith("--")],
                                 allow_duplicate="--allow-duplicate" in sys.argv),
     "ingest": lambda: cmd_ingest([a for a in sys.argv[2:] if not a.startswith("--")],
                                  allow_duplicate="--allow-duplicate" in sys.argv),
     "all": lambda: cmd_all(),
     "query": lambda: cmd_query(sys.argv[2:]),
     # **관측 창구다** — mock 관문 비대상(doctor와 같은 자리). 모드는 화면 배지로 뜬다.
     "viewer": lambda: cmd_viewer(sys.argv[2:]),
     # **골든셋은 파이프라인이 아니다**(문서 5 §5.5) — 측정 장치라 관문 비대상이다.
     "golden": lambda: cmd_golden(sys.argv[2:]),
     "ops": lambda: cmd_ops(sys.argv[2:]),
     "gauges": lambda: cmd_gauges(),
     "platform": lambda: cmd_platform(sys.argv[2:]),
     "scan": lambda: cmd_scan(sys.argv[2:]),
     "parse": lambda: cmd_parse(sys.argv[2:]),
     "register": lambda: cmd_register(sys.argv[2:]),
     "ingest-file": lambda: cmd_ingest_batch(sys.argv[2:]),
     "ingest-dir": lambda: cmd_ingest_batch(sys.argv[2:]),
     "show": lambda: cmd_show(sys.argv[2:]),
     "export": lambda: cmd_export(sys.argv[2:]),
     "llm-check": lambda: cmd_llm_check(sys.argv[2:]),
     "skeleton-confirm": lambda: cmd_skeleton_confirm(sys.argv[2:]),
     "skeleton-status": lambda: cmd_skeleton_status(sys.argv[2:])}[cmd]()
    # **반환값을 종료 코드로 쓴다.** 안 그러면 실패한 명령이 exit 0으로 끝나
    # 플랫폼·스크립트가 "성공"으로 읽는다 — 실측: `export mermaid quality`가
    # 빈 다이어그램을 내고 0으로 끝났고, 그 뒤 실패 판정을 붙여도 여전히 0이었다.
    sys.exit(_rc or 0)
