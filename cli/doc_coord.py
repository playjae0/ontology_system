# -*- coding: utf-8 -*-
"""칸 2.8 — **문서 좌표** — 문서 하나가 「어느 공정(스테이션)의 문서인가」를 정하는 자리 (B102 ②).

정하는 길(LLM 0): `--coord <골격 이름|none>`(사람) → **기록**(같은 doc_id 재인입은 다시 묻지 않는다 ·
`--coord`가 덮는다 · 자리는 등록 단 `registry/doc_coords.json` — 시트 역할과 같은 결) → **파일명 제안**
(구분자로 나눈 조각이 골격 이름·별칭에 맞고 가리키는 노드가 하나일 때만 — `parser.tagger.suggest_doc_coord`).
터미널이면 시트 역할 관문 자리에서 **제안이 있을 때** 한 번 묻는다 · 비대화형은 기록 → 하나뿐인 제안 → 없음.
어느 경우든 한 줄: 「문서 좌표 — X (출처: 사람 · 기록 · 파일명 · 없음)」.

문서 좌표가 있으면 파서는 시트명·제목 대조를 그 서브트리 안에서만 받고, 빈 조각은 그것을 물려받는다
(표·산문 같은 함수 — `tagger.coord_from_section`).

파싱 끝 좌표 줄 아래에 **판정 전 좌표 쌍 표**(B105 ③ — `pair_screen`)가 선다: 구축과 같은 함수·같은 해소
(`core.build.coord_scan.scan`)라 그 쌍·행 수가 구축 큐(`coord_mismatch`)의 쌍·행 수다 · 큐 0 · LLM 0.
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


def decide(doc, doc_id, spec=None, ask=True, write=True):
    """문서 좌표를 정한다 — `(canonical 또는 None, 출처)` · 한 줄을 낸다. `write=False`(`--dry-run`)면 기록하지 않는다."""
    from parser import tagger
    nodes = _nodes()
    if spec is not None:
        coord = None if spec.strip().lower() in NONE else _resolve(spec.strip(), nodes)
        if write:
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
            if write:
                record(doc_id, coord, "사람")
            src = "사람"
    print(f"   문서 좌표 — {coord or '없음'} (출처: {src})")
    return coord, src


def coord_counts(env):
    """조각 좌표의 출처별 수(B102 ⑦ — 표·산문 같은 함수) — 봉투의 `meta` 표시에서(새 계산 0)."""
    pcs = (env or {}).get("records") or (env or {}).get("chunks") or []
    out = {"조각": len(pcs), "자기": 0, "문서 좌표": 0, "태깅": 0, "없음": 0,
           "무시(문서 좌표 밖)": 0, "공유 별칭 건너뜀": 0, "공유 별칭 범위 안 해소": 0}
    for p in pcs:
        m = p.get("meta") or {}
        if not p.get("process_ref"):
            out["없음"] += 1
        elif m.get("coord_from_doc"):
            out["문서 좌표"] += 1
        elif m.get("coord_tag_source") in ("learned", "live"):
            out["태깅"] += 1
        else:
            out["자기"] += 1                       # 범위 안 해소(scope)도 자기 표기에서 온 좌표다
        if m.get("coord_tag_source") == "scope":
            out["공유 별칭 범위 안 해소"] += 1          # 원 표기는 meta.coord_tag_from (B104 ①)
        if m.get("coord_ignored"):
            out["무시(문서 좌표 밖)"] += 1
        if m.get("coord_shared_skip"):
            out["공유 별칭 건너뜀"] += 1
    return out


def pair_report(env):
    """**판정 전 좌표 쌍 표**(B105 ③) — `(쌍 표, 확인된 쌍 열쇠들)`. 구축과 같은 함수·같은 해소(좌표 층 빌더 ·
    `core.build.coord_scan.scan` — 사전 · 저해상도 사다리 · 극성 하강 · `Builder.coord_verdicts`) · 큐 0 · LLM 0."""
    from core.build import coord_scan
    from core.build.build import Builder
    from core.state import coord_acks
    from core.state.bootstrap import coord_layer, load_config, open_graph
    lay = coord_layer()
    b = Builder(open_graph(lay), load_config(lay), None, "(좌표 쌍)", lay)
    t = coord_scan.table(coord_scan.scan(env, b))
    done = coord_acks.acked()
    return t, {k for k in t["pairs"] if coord_acks.key(*k) in done}


def pair_screen(env):
    """좌표 쌍 줄 + 쌍 표 + 다음 줄 — 돌려주는 것은 관문 머리가 싣는 수(`쌍`·`행`·`상위_밖`·`확인됨`·`대조`)."""
    from parser import coord_pairs as CP
    t, acked = pair_report(env)
    live = {k: e for k, e in t["pairs"].items() if k not in acked}
    print(f"   {CP.head_line(t, acked)} · 대조 {t['checked']:,}행(상위·하위가 둘 다 골격에 맞은 행)")
    for ln in CP.pair_lines(t, acked):
        print(f"     {ln}")
    if live or t["outside"]:
        print("     ▶ 다음 줄 — 열이 뒤바뀌었으면 재등록(python -m cli.register generate "
              f"{env.get('doc_type') or '<dt>'} <층> <표본> --revise --hint "
              "\"상위(process_group)·하위(process_ref) 열 매핑을 바로잡는다\" — 가이드 §4 재등록 순서) · "
              "골격이 틀렸으면 seed(부모·이름 변경은 재구축 — 가이드 §7) · "
              "별칭이면 ALIASES + python run.py bootstrap · 이대로 두려면 쌍 확인"
              "(python run.py platform queue coord_mismatch)")
    return {"쌍": len(live), "행": sum(e["rows"] for e in live.values()), "상위_밖": len(t["outside"]),
            "확인됨": len(acked), "대조": t["checked"]}


def coord_line(env):
    c = coord_counts(env)
    return ("   좌표 — " + f"조각 {c['조각']:,} · "
            + " · ".join(f"{k} {v:,}" for k, v in c.items() if k != "조각"))
