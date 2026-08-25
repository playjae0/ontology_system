# -*- coding: utf-8 -*-
"""파이프라인 진입점 — CLI+파일 (구현문서 §0).

모든 단계는 subprocess로 호출 가능해야 한다(§16.1 플랫폼화 인지 계약).
**build는 직렬 실행**이다 — 저장이 비원자적이라 호출부가 직렬화를 보장한다.

사용:
  python run.py init [--fresh]     클린 상태 — data/ 하위를 빈 상태로 생성·재생성
  python run.py bootstrap          층 골격 심기 (n10)
  python run.py build <parsed.json...>  계약 JSON 인입 — **플랫폼 계약 이름**(§7.1)
  python run.py ingest <파일...>   상동 (구 이름 — 같은 기능을 두 이름으로 두지 않으려
                                   남기되, 계약 이름은 build다)
  python run.py all                bootstrap + mock/parsed 전량 인입
  python run.py query "<질문>"     질의 4단 (cli/query.py 라우터로 위임)
  python run.py ops <연산> ...     I축 4연산 (cli/ops.py로 위임)
  python run.py gauges             계기판 8종 (cli/platform.py로 위임)
  python run.py platform <명령>    플랫폼 창구 4′ (cli/platform.py로 위임)
  python run.py scan <문서> ...    n9 지문 스캔 (cli/scan.py로 위임)
  python run.py parse <명령> ...   파서 n7 (cli/parse.py로 위임 — run·head·build)
  python run.py register <명령>    n6 구축 모드 등록 (cli/register.py로 위임)
  python run.py show <명령> ...    산출물 열람 — tree·node·doc·chunk·edges·schema·meta
  python run.py export <형식>      파생물 — cypher · csv · mermaid
"""
import json
import sys
from pathlib import Path

from core import log, store
from core.bootstrap import bootstrap, open_graph
from core.pipeline import run_document
from router import discover

ROOT = Path(__file__).resolve().parent


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cmd_init(args):
    """클린 상태의 **단일 정의**. 회귀 규약과 완료판정 4번이 같은 바닥을 쓰게 한다."""
    from core.init import init
    made = init("--fresh" in args)
    print(f"[init] 빈 상태 {len(made)}개 — {', '.join(made) or '이미 있음'}")


def cmd_bootstrap():
    for layer in discover():
        g, m, ids, _flow = bootstrap(layer)          # 파생 흐름은 loader가 출력한다
        if g is None:
            print(f"[bootstrap] {layer}: 골격 선언 없음 — 내장 층이 아니다 (J10)")
            continue
        print(f"[bootstrap] {layer}: 노드 {m['nodes']} · 엣지 {m['edges']}")
        print(f"            계기판 7 graph {m['gauge7_graph_mb']}MB "
              f"({m['serializer']}) · 8 build {m['gauge8_build_seconds']}s")


def cmd_ingest(paths, finalize=True):
    """`finalize`는 전 문서 인입 뒤 도는 빌드 말미 패스다 — 낱개 인입에서도 기본 수행한다."""
    for p in paths:
        r, m, extracted = run_document(_load(p))
        mark = "보류" if r.status == "held" else "인입"
        tail = f"  ({r.reason})" if r.reason else (
            "  [추출 실행]" if extracted else "  [추출 체크포인트 재사용]")
        print(f"[{mark}] {r.doc_id}: record {len(r.record_ids)} · "
              f"chunk {len(r.chunk_ids)}{tail}")
    if finalize:
        from core.pipeline import finalize as _fin
        _fin()


def cmd_all():
    cmd_bootstrap()
    mock = sorted((ROOT / "mock" / "parsed").glob("*.json"))
    order = ["CP01", "PFMEA01", "PPT01", "PPT02", "PPT03", "QPPT01"]
    idx = {n: i for i, n in enumerate(order)}
    cmd_ingest(sorted([p for p in mock if p.stem != "CP01B"],
                      key=lambda p: idx.get(p.stem, 99)))


def cmd_query(args):
    """질의는 **라우터가 단일 진입점**이다(§8-R1) — 여기서는 위임만 한다."""
    from cli.query import answer, generate
    print(generate(answer(" ".join(args))))


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
    from cli.register import main
    return main(args)


def cmd_show(args):
    """산출물 열람 — 읽기 전용, 시각화 없이 텍스트로."""
    from cli.show import main
    return main(args)


def cmd_export(args):
    """파생물 내보내기 — 진실은 data/의 JSON이다(P5)."""
    from cli.export import main
    return main(args)


if __name__ == "__main__":
    log.setup()          # 로깅 설정은 **진입점만** 한다 (문서 7 §7.8)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"init": lambda: cmd_init(sys.argv[2:]),
     "bootstrap": lambda: cmd_bootstrap(),
     # **`build`가 계약 이름이다**(문서 7 §7.1 진입점 계약) — 플랫폼이 subprocess로
     # 부르는 이름은 계약의 일부다. `ingest`는 같은 함수의 옛 이름이다.
     "build": lambda: cmd_ingest(sys.argv[2:]),
     "ingest": lambda: cmd_ingest(sys.argv[2:]),
     "all": lambda: cmd_all(),
     "query": lambda: cmd_query(sys.argv[2:]),
     "ops": lambda: cmd_ops(sys.argv[2:]),
     "gauges": lambda: cmd_gauges(),
     "platform": lambda: cmd_platform(sys.argv[2:]),
     "scan": lambda: cmd_scan(sys.argv[2:]),
     "parse": lambda: cmd_parse(sys.argv[2:]),
     "register": lambda: cmd_register(sys.argv[2:]),
     "show": lambda: cmd_show(sys.argv[2:]),
     "export": lambda: cmd_export(sys.argv[2:])}[cmd]()
