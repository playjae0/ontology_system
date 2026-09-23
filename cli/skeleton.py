# -*- coding: utf-8 -*-
"""칸 0.1 — 골격 seed 확정 — **생성은 밖에, 확정만 시스템 안에** (문서 3 §3.7 규약 3 · B25).

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

from core import paths
from core.state import skeleton as SK
from core.state.bootstrap import load_config, load_seed
from core.graph import GraphStore
from core.state.skeleton import plant

ROOT = Path(__file__).resolve().parent.parent
# 층 자산은 상태 루트에 산다(B79 ①) — 자리는 `paths.layers()`에 묻는다.
RECORD = "confirmations.json"
PREV = "skeleton.prev.json"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_path(layer):
    """확정 대상 파일 — **config가 값으로 가리킨다**(D-42). 경로를 코드가 짓지 않는다."""
    skel = (load_config(layer) or {}).get("skeleton") or {}
    src = skel.get("source")
    return paths.layers(layer, src) if src else None


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


# ── 골격 문법 판정 — `status`·`confirm`이 **같은 함수**를 부른다 (B61 ②) ──────
#
# **막는 건 맞다. 어느 줄이 어느 규칙인지를 안 말하는 것이 틀렸다.**
# 태그(`K##`)는 관문의 `G##`과 같은 방식이다 — 정본은 여기 한 자리이고, 사내는
# 복사가 안 되는 환경이라 **읽어서 전달**한다.
#
# **loader의 판정을 다시 쓰지 않는다**(미러 금지) — 「무엇이 canonical인가」는
# `core/state/skeleton.py`가 갖고, 여기는 **파일의 어디가 어긋났나**만 본다: 줄 번호는
# 파일에만 있고 loader는 그것을 모른다. loader가 먼저 죽는 위반은 그 문면 그대로
# `K09`로 싣는다 — 같은 사실을 두 곳이 말하면 하나가 낡는다.

K_READ = "K01"      # seed를 읽지 못했다 (JSON 문법)
K_DUP = "K02"       # 같은 자리에 같은 이름이 둘 (main·sub 충돌의 원천)
K_MARK = "K05"      # 마커 어휘 밖 (`::축값` 오타 · `@마커` 오타)
K_LOAD = "K09"      # loader가 낸 위반 — 문면은 loader의 것

_MARKERS = {SK.MARK_SPLIT, SK.MARK_UNORDERED, SK.MARK_NOFLOW}


def _tree_span(text):
    """TREE 블록의 줄 범위 — 이름이 ALIASES에도 나오므로 **선언 자리만** 센다."""
    lines = text.splitlines()
    lo = next((i for i, ln in enumerate(lines, 1) if f'"{SK.KEY_TREE}"' in ln), 1)
    hi = next((i for i, ln in enumerate(lines, 1)
               if i > lo and f'"{SK.KEY_ALIASES}"' in ln), len(lines) + 1)
    return lo, hi


def _lines_of(text, token, span=None):
    """그 이름이 **선언된** 줄 번호 전부 — 없으면 빈 목록."""
    lo, hi = span or (1, len(text.splitlines()) + 1)
    return [i for i, ln in enumerate(text.splitlines(), 1)
            if lo <= i < hi and f'"{token}"' in ln]


def _names(node, depth, out):
    """TREE를 훑어 `(이름, 깊이)`와 마커 문자열을 모은다 — 판정은 부르는 쪽이 한다."""
    if isinstance(node, list):
        for item in node:
            _names(item, depth, out)
    elif isinstance(node, dict):
        for k, v in node.items():
            out.append((k, depth))
            _names(v, depth + 1, out)
    elif isinstance(node, str):
        out.append((node, depth))


def check(layer):
    """골격 seed의 문법 판정 — **위반 전건**을 `[{tag, label, lines}]`로 돌려준다.

    첫 하나에서 멈추지 않는다: 사람이 seed를 고치고 다시 돌렸을 때 다음 위반이
    처음 보이면, 고치는 왕복이 위반 수만큼 는다.
    """
    src = seed_path(layer)
    if src is None:
        return []                      # 파일 seed가 아닌 층(인라인) — 호출부가 따로 말한다
    if not src.exists():
        # **가리키는 파일이 없으면 위반이다**(B85 ①) — 구판은 빈 목록을 돌려줘
        # `skeleton-status`가 「위반 0건」이라고 말했다(실측).
        from core.state.bootstrap import seed_missing_note
        return [{"tag": K_READ, "label": "골격 파일이 없다",
                 "detail": seed_missing_note(layer, src), "lines": []}]
    text = src.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [{"tag": K_READ, "label": "seed를 읽지 못했다 (JSON 문법)",
                 "detail": f"{e.msg}", "lines": [e.lineno]}]

    out = []
    span = _tree_span(text)
    labels = set((data.get(SK.KEY_LABELS) or {}))
    pairs = []
    _names(data.get(SK.KEY_TREE) or [], 1, pairs)

    # K05 — 마커 어휘. 코드가 아는 것은 구문 마커 4종뿐이다(문서 1).
    for name, _d in pairs:
        if name.startswith(SK.MARK_PREFIX):
            if name not in _MARKERS and name[1:] not in labels:
                out.append({"tag": K_MARK, "label": "마커 어휘 밖",
                            "detail": f"'{name}' — 마커는 {sorted(_MARKERS)} "
                                      f"또는 @<축값> {sorted(labels)}",
                            "lines": _lines_of(text, name, span)})
        elif name.startswith("::"):
            if name[2:] not in labels:
                out.append({"tag": K_MARK, "label": "극성 마커 문법",
                            "detail": f"'{name}' — 축값은 {sorted(labels)}뿐이다",
                            "lines": _lines_of(text, name, span)})

    # K02 — main·sub 자리의 같은 이름. canonical이 짧은 이름 그대로라 충돌하면
    # 두 개념이 한 노드가 된다(loader `_check_name_collision`이 막는 그 자리).
    seen = {}
    for name, d in pairs:
        if d > 2 or name.startswith(("@", "::")):
            continue
        seen.setdefault(name, 0)
        seen[name] += 1
    for name, n in seen.items():
        if n > 1:
            out.append({"tag": K_DUP, "label": "canonical 중복",
                        "detail": f"'{name}' — main·sub 자리에 {n}번",
                        "lines": _lines_of(text, name, span)})

    # K09 — 위 셋이 못 본 위반은 loader가 낸다. **문면을 새로 짓지 않는다.**
    if not out:
        try:
            _view(layer)
        except Exception as e:
            out.append({"tag": K_LOAD, "label": f"{type(e).__name__}",
                        "detail": str(e), "lines": []})
    return out


def block(layer, rows, title="골격 확정 거부"):
    """거부 블록 — 화면 문면 한 자리 (B59 관문 블록과 같은 꼴)."""
    lines = [f"■ {title} — {layer}"]
    for r in rows:
        loc = (" (" + " · ".join(f"{n}행" for n in r["lines"]) + ")") if r["lines"] else ""
        lines.append(f"  [FAIL] {r['tag']}  {r['label']} — {r['detail']}{loc}")
    lines.append("  ▶ 다음 줄:")
    lines.append(f"     (seed의 위 줄을 고친 뒤)  python run.py skeleton-status {layer}")
    lines.append(f"     (판정이 비면)            python run.py skeleton-confirm "
                 f"{layer} --by <이름>")
    return "\n".join(lines)


def cmd_status(argv):
    """**확정 없이 판정만** (B61 ②) — 뷰도 기록도 없다. 위반이 있으면 rc=1."""
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        raise SystemExit("사용: python run.py skeleton-status <층>")             # [사용법]
    layer = args[0]
    if not paths.layers(layer).is_dir():
        _ls = sorted(p.name for p in paths.layers().iterdir() if p.is_dir()) \
            if paths.layers().exists() else []
        raise SystemExit(f"[골격 판정] 없는 층: {layer} — 현재 층: {_ls}\n"        # [상태]
                         f"  ▶ 다음 줄:\n"
                         f"     python run.py skeleton-status "
                         f"{_ls[0] if _ls else '<층>'}")
    rows = check(layer)
    if not rows:
        src = seed_path(layer)
        print(f"■ 골격 판정 — {layer}: 문법 위반 0건"
              + (f" · {src.relative_to(ROOT)}" if src else " (파일 seed 없음)"))
        print(f"  ▶ 다음 줄:\n"
              f"     python run.py skeleton-confirm {layer} --by <이름>")
        return 0
    print(block(layer, rows, f"골격 판정 · 위반 {len(rows)}건"))
    return 1


def _record_path(layer):
    return paths.layers(layer, RECORD)


def cmd_confirm(argv):
    """확정 — 검증 → 뷰 대조 → 기록. **세 관문 중 하나라도 못 지나면 기록하지 않는다.**"""
    args = [a for a in argv if not a.startswith("--")]
    by = None
    if "--by" in argv:
        i = argv.index("--by")
        by = argv[i + 1] if i + 1 < len(argv) else None
    if not args:
        raise SystemExit(__doc__)                                         # [사용법]
    layer = args[0]

    # ── 관문 ① 확정자 ─────────────────────────────────────────────
    # **`--by` 없이는 기록하지 않는다**(§3.7 조건 ① · 등록 `confirm --by`와 같은 원리).
    # 여기서 막는 이유: 뷰를 보여 준 뒤에 거절하면 사람이 대조를 한 번 헛한다.
    if not by:
        raise SystemExit("[골격 확정] --by <확정자>가 필요하다 — "                    # [사용법]
                         "확정자가 기록에 남지 않으면 확정이 아니다 (문서 3 §3.7)")

    if not paths.layers(layer).is_dir():
        _ls = sorted(p.name for p in paths.layers().iterdir() if p.is_dir()) \
            if paths.layers().exists() else []
        raise SystemExit(f"[골격 확정] 없는 층: {layer} — 현재 층: {_ls}\n"       # [상태]
                         f"  ▶ 다음 줄:\n"
                         f"     python run.py skeleton-confirm {_ls[0] if _ls else '<층>'}"
                         f" --by <이름>")

    # ── 관문 ② 문법 검증 — **`status`와 같은 함수**다 (B61 ②) ────
    # 위반 전건을 줄 번호와 함께 낸다. 첫 하나에서 멈추면 사람이 고치는 왕복이
    # 위반 수만큼 는다. 판정이 두 벌이면 status가 초록인데 confirm이 막는 날이 온다.
    _bad = check(layer)
    if _bad:
        raise SystemExit(block(layer, _bad))                # [상태] 문면=block
    try:
        seed, flow = _view(layer)
    except Exception as e:
        raise SystemExit(f"[골격 확정] seed를 읽지 못했다 — {type(e).__name__}: {e}\n"  # [상태]
                         f"  ▶ 다음 줄:\n"
                         f"     (seed를 고친 뒤)  python run.py skeleton-status {layer}")
    if seed is None:
        raise SystemExit(f"[골격 확정] '{layer}' 층은 골격을 선언하지 않는다 "            # [상태]
                         f"(config.skeleton 없음) — 확정할 것이 없다\n"
                         f"  ▶ 다음 줄:\n"
                         f"     (층 등록부를 본다)  "
                         f"python run.py platform registry")

    src = seed_path(layer)
    if src is None:
        raise SystemExit(                                                 # [상태]
            f"[골격 확정] '{layer}' 층은 골격을 **config 안에 인라인**으로 선언한다 "
            f"(config.skeleton.source 없음) — 확정 대상 파일이 없다. "
            f"이 명령은 파일 seed를 쓰는 층의 것이다\n"
            f"  ▶ 다음 줄:\n"
            f"     (문법 판정만 본다)  python run.py skeleton-status {layer}")

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
        raise SystemExit(                                                 # [상태]
            f"\n[골격 확정] 비대화형이라 확정하지 않았다 — "
            f"뷰 대조는 건너뛸 수 없다(문서 3 §3.7 조건 ③).\n"
            f"  ▶ 다음 줄:\n"
            f"     (터미널에서)  python run.py skeleton-confirm {layer} --by <이름>")
    try:
        ans = input("\n  이 흐름이 근거 문서와 맞습니까? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans not in ("y", "yes"):
        raise SystemExit(f"[골격 확정] 확정하지 않았다 — 사람이 뷰 대조에서 "    # [상태]
                         f"N을 골랐다 (문서 3 §3.7 조건 ③)\n"
                         f"  ▶ 다음 줄:\n"
                         f"     (seed를 고친 뒤 문법만 본다)  "
                         f"python run.py skeleton-status {layer}\n"
                         f"     (그 판정이 비면)              "
                         f"python run.py skeleton-confirm {layer} --by <이름>")

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
    paths.layers(layer, PREV).write_bytes(blob)

    # ── 확정 기록 ─────────────────────────────────────────────────
    entry = {"by": by, "at": _now(), "seed_sha256": sha}
    prior.append(entry)
    rec_path.write_text(json.dumps(prior, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n  확정 기록 → {rec_path.relative_to(ROOT)} "
          f"({len(prior)}번째 · {by} · {sha[:12]}…)")
    print(f"  확정본 사본 → {paths.layers(layer, PREV)} "
          f"(다음 판을 놓은 뒤 «확정된 것은 무엇이었나»를 답한다)")
    print(f"  다음: python run.py init --fresh && python run.py bootstrap")
    return 0


def main(argv):
    return cmd_confirm(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
