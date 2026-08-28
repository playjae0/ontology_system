# -*- coding: utf-8 -*-
"""골격 seed 확정 — **생성은 밖에, 확정만 시스템 안에** (문서 3 §3.7 규약 3 · B25).

    python run.py skeleton-confirm <층> --by <확정자>

**왜 이 명령이 있나.** seed 초안은 시스템 밖에서 만들고(§3.7 조건 ②) 파일은 사람이
직접 놓는다 — 그 흐름은 그대로다. 그런데 **파일 복사에는 `--by`가 없어서** 누가 언제
이 골격을 확정했는지 되짚을 수 없었다. §3.7이 요구하는 확정 행위의 조건 셋 —
①확정자가 기록에 남고 ②건마다 확정하며 ③확정 전 파생 흐름 뷰 대조를 건너뛸 수
없어야 한다 — 을 채우는 자리가 이 명령이다.

**이 명령은 `skeleton.json`을 쓰지 않는다.** 검증·대조·기록·보존만 한다. 파일을 놓는
것은 여전히 사람이고, 그래서 *"사람의 확정 없이 seed가 기록되는 경로는 어떤 부품에도
없다"*(§3.7)가 기계로 판정된다 — 레포에 그 파일을 쓰기 모드로 여는 경로가 0이다.

**그래프를 건드리지 않는다.** 뷰는 `bootstrap`이 쓰는 것과 **같은 파생기**(`plant`)를
임시 그래프에 돌려 얻는다 — 확정 전에 `data/`가 바뀌면 「확정 안 된 골격이 이미
심겨 있는」 상태가 되고, 그 상태에서 사람이 N을 눌러도 되돌릴 것이 없다.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from core.bootstrap import load_config, load_seed
from core.graph import GraphStore
from core.skeleton import plant

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT / "layers"
RECORD = "confirmations.json"
PREV = "skeleton.prev.json"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_path(layer):
    """확정 대상 파일 — **config가 값으로 가리킨다**(D-42). 경로를 코드가 짓지 않는다."""
    skel = (load_config(layer) or {}).get("skeleton") or {}
    src = skel.get("source")
    return (LAYERS / layer / src) if src else None


def _view(layer):
    """파생 대표 흐름 — `bootstrap`의 n10과 **같은 파생기**로 얻되 아무것도 쓰지 않는다.

    임시 디렉터리의 그래프에 심고 버린다: `save()`·`build_end()`를 부르지 않으므로
    `data/`에도 사전에도 닿지 않는다. 뷰만 필요한 자리에서 부트스트랩 전체를 돌리면
    **확정 전에 골격이 심겨** 사람이 N을 눌러도 되돌릴 것이 없다.
    """
    cfg = load_config(layer)
    skel = cfg.get("skeleton")
    if not skel:
        return None, []
    seed = load_seed(layer, skel)
    with tempfile.TemporaryDirectory() as tmp:
        g = GraphStore.for_layer(layer, data_dir=tmp)
        _ids, _parsed, _pairs, flow = plant(g, seed, skel, cfg, lambda s, n: None)
    return seed, flow


def _record_path(layer):
    return LAYERS / layer / RECORD


def cmd_confirm(argv):
    """확정 — 검증 → 뷰 대조 → 기록. **세 관문 중 하나라도 못 지나면 기록하지 않는다.**"""
    args = [a for a in argv if not a.startswith("--")]
    by = None
    if "--by" in argv:
        i = argv.index("--by")
        by = argv[i + 1] if i + 1 < len(argv) else None
    if not args:
        raise SystemExit(__doc__)
    layer = args[0]

    # ── 관문 ① 확정자 ─────────────────────────────────────────────
    # **`--by` 없이는 기록하지 않는다**(§3.7 조건 ① · 등록 `confirm --by`와 같은 원리).
    # 여기서 막는 이유: 뷰를 보여 준 뒤에 거절하면 사람이 대조를 한 번 헛한다.
    if not by:
        raise SystemExit("[골격 확정] --by <확정자>가 필요하다 — "
                         "확정자가 기록에 남지 않으면 확정이 아니다 (문서 3 §3.7)")

    if not (LAYERS / layer).is_dir():
        raise SystemExit(f"[골격 확정] 없는 층: {layer} — "
                         f"현재 층: {sorted(p.name for p in LAYERS.iterdir() if p.is_dir())}")

    # ── 관문 ② 문법 검증 — loader를 그대로 재사용한다 ────────────
    # 실패 문면을 여기서 새로 짓지 않는다: loader가 이미 「어느 키가 왜 틀렸나」를
    # 말한다. 다시 쓰면 같은 사실을 두 곳이 말하고 하나가 낡는다.
    try:
        seed, flow = _view(layer)
    except Exception as e:
        raise SystemExit(f"[골격 확정] seed를 읽지 못했다 — {type(e).__name__}: {e}")
    if seed is None:
        raise SystemExit(f"[골격 확정] '{layer}' 층은 골격을 선언하지 않는다 "
                         f"(config.skeleton 없음) — 확정할 것이 없다")

    src = seed_path(layer)
    if src is None:
        raise SystemExit(
            f"[골격 확정] '{layer}' 층은 골격을 **config 안에 인라인**으로 선언한다 "
            f"(config.skeleton.source 없음) — 확정 대상 파일이 없다. "
            f"이 명령은 파일 seed를 쓰는 층의 것이다")

    print("=" * 66)
    print(f"  골격 확정 — {layer} · {src.relative_to(ROOT)}")
    print("=" * 66)
    print(f"  seed_format {seed.get('seed_format')} · {src.stat().st_size:,}B")

    # ── 관문 ③ 뷰 대조 — 우회 불가 ────────────────────────────────
    print(f"\n[n10] {layer} — 파생 대표 흐름 (seed 선언의 사람 대조용)")
    for ln in flow:
        print(ln)
    print("\n  ※ 뷰는 **있는 것**의 검증이다 — 빠진 공정은 잡지 못한다. "
          "문서의 공정 수와 노드 수를 한 번 세어 맞춘다")

    if not sys.stdin.isatty():
        # **비대화형은 확정하지 않는다**(§3.7 조건 ③ — 뷰 대조 우회 불가).
        # 파이프로 y를 먹이면 「사람이 뷰를 봤다」가 거짓이 된다.
        raise SystemExit(
            "\n[골격 확정] 비대화형이라 확정하지 않았다 — "
            "뷰 대조는 건너뛸 수 없다(문서 3 §3.7 조건 ③). "
            "터미널에서 다시 실행한다")
    try:
        ans = input("\n  이 흐름이 근거 문서와 맞습니까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans not in ("y", "yes"):
        raise SystemExit("[골격 확정] 확정하지 않았다 — seed를 고쳐 다시 실행한다")

    # ── 확정본 보존 (1세대 — 더 깊은 이력은 git 몫) ───────────────
    # **`skeleton.prev.json`은 「마지막으로 확정된 seed의 사본」이다.**
    # 확정 시점에는 그것이 `skeleton.json`과 같지만, 사람이 다음 판을 파일에 놓는
    # 순간 갈린다 — 그때 이 사본이 **「확정된 것은 무엇이었나」**를 답한다. 확정
    # 전의 옛 내용을 여기서 만들어 낼 수는 없다: 이 명령은 파일을 쓰지 않으므로
    # 이전 판이 이미 사라진 뒤에 불린다.
    blob = src.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    rec_path = _record_path(layer)
    prior = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else []
    (LAYERS / layer / PREV).write_bytes(blob)

    # ── 확정 기록 ─────────────────────────────────────────────────
    entry = {"by": by, "at": _now(), "seed_sha256": sha}
    prior.append(entry)
    rec_path.write_text(json.dumps(prior, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n  확정 기록 → {rec_path.relative_to(ROOT)} "
          f"({len(prior)}번째 · {by} · {sha[:12]}…)")
    print(f"  확정본 사본 → {(LAYERS / layer / PREV).relative_to(ROOT)} "
          f"(다음 판을 놓은 뒤 «확정된 것은 무엇이었나»를 답한다)")
    print(f"  다음: python run.py init --fresh && python run.py bootstrap")
    return 0


def main(argv):
    return cmd_confirm(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
