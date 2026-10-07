# -*- coding: utf-8 -*-
"""칸 2.8 — **문서 좌표** — 문서 하나가 「어느 공정(스테이션)의 문서인가」를 정하는 자리 (B102 ②).

정하는 길(LLM 0): `--coord <골격 이름|none>`(사람) → **기록**(같은 doc_id 재인입은 다시 묻지 않는다 ·
`--coord`가 덮는다 · 자리는 등록 단 `registry/doc_coords.json` — 시트 역할과 같은 결) → **파일명 제안**
(구분자로 나눈 조각이 골격 이름·별칭에 맞고 가리키는 노드가 하나일 때만 — `parser.tagger.suggest_doc_coord`).
터미널이면 시트 역할 관문 자리에서 **제안이 있을 때** 한 번 묻는다 · 비대화형은 기록 → 하나뿐인 제안 → 없음.
어느 경우든 한 줄: 「문서 좌표 — X (출처: 사람 · 기록 · 파일명 · 없음)」.

문서 좌표가 있으면 파서는 시트명·제목 대조를 그 서브트리 안에서만 받고, 빈 조각은 그것을 물려받는다
(표·산문 같은 함수 — `tagger.coord_from_section`).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import paths
from core.state import store

NONE = ("none", "-", "없음")
FLAG = "--coord"


def _file():
    return paths.registry("doc_coords.json")


def recorded(doc_id):
    """기록 — `{coord, by, at}` 또는 None."""
    p = _file()
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return d.get(doc_id)


def record(doc_id, coord, by):
    p = _file()
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    d[doc_id] = {"coord": coord, "by": by,
                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    paths.ensure(p)
    store.atomic_write_bytes(p, (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def flag(args):
    """`--coord <이름|none>`을 뗀다 — `(남은 인자, 값 또는 None)`."""
    if FLAG not in args:
        return args, None
    i = args.index(FLAG)
    v = args[i + 1] if i + 1 < len(args) else ""
    if not v:
        raise SystemExit("[투입] --coord 뒤에 골격 이름 또는 none이 필요하다")        # [사용법]
    return args[:i] + args[i + 2:], v


def _nodes():
    from core.state.bootstrap import coord_layer
    from parser import tagger
    return tagger.closed_list(coord_layer())


def _resolve(name, nodes):
    """사람이 친 이름 → canonical(정확 · 라틴 대소문자 2차 · 공유 별칭이면 거부)."""
    from parser import tagger
    idx, shared, _a = tagger.scoped_index(nodes)
    if name in shared:
        raise SystemExit(f"[상태] 문서 좌표 '{name}'는 골격 노드 여럿이 나눠 가진 별칭이다 — "  # [상태]
                         f"골격 이름(canonical)을 준다: python run.py show tree")
    n = idx.get(name) or tagger.fold_hit(name, idx)
    if n is None:
        raise SystemExit(f"[상태] 문서 좌표 '{name}'가 골격 목록에 없다 — "                    # [상태]
                         f"python run.py show tree 의 이름을 주거나 --coord none")
    return n["canonical"]


def decide(doc, doc_id, spec=None, ask=True):
    """문서 좌표를 정한다 — `(canonical 또는 None, 출처)` · 한 줄을 낸다."""
    from parser import tagger
    nodes = _nodes()
    if spec is not None:
        coord = None if spec.strip().lower() in NONE else _resolve(spec.strip(), nodes)
        record(doc_id, coord, "사람")
        src = "사람"
    elif recorded(doc_id) is not None:
        coord, src = recorded(doc_id).get("coord"), "기록"
    else:
        sug, part = tagger.suggest_doc_coord(Path(str(doc)).name, nodes)
        coord, src = sug, ("파일명" if sug else "없음")
        # 터미널은 **제안이 있을 때만** 묻는다(수락 확인) — 제안이 없으면 없음(바꾸려면 --coord)
        if ask and sug and sys.stdin.isatty():
            ans = input(f"   문서 좌표 — 제안 '{sug}'(파일명 조각 '{part}') · Enter=수락 · 이름 · -=없음 > ").strip()
            if ans:
                coord = None if ans.lower() in NONE else _resolve(ans, nodes)
            record(doc_id, coord, "사람")
            src = "사람"
    print(f"   문서 좌표 — {coord or '없음'} (출처: {src})")
    return coord, src
