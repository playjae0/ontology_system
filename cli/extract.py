# -*- coding: utf-8 -*-
"""추출 단계 진입점 — **플랫폼 계약**(문서 7 §7.1).

    python -m cli.extract <parsed.json ...>

파이프라인은 3단이고 **각 단계는 CLI 진입점 + 파일 입출력**이다(§7.3-1). 파싱과
구축에는 진입점이 있는데 그 사이의 추출만 없으면, 플랫폼이 "추출만 다시 돌린다"를
할 수 없고 체크포인트(`extract/{doc_id}.json`)를 만드는 손이 구축 안에만 있게 된다.

**산출은 체크포인트다** — `extract/{doc_id}.json`이고 **파일 존재 = 추출 완료**다
(§7.8). 구축 재실행은 추출을 다시 부르지 않는다.

**비정형(prose)만 대상이다** — 정형은 행 문맥이 명확해 추출 단계를 지나지 않는다
(문서 4 §4.1). 정형 파일을 주면 건너뛰었다고 밝히고 넘어간다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from core import extract as EX
from core import log, store
from core.bootstrap import load_config
from core.ingest import ingest, load_schema

ROOT = Path(__file__).resolve().parent.parent


def run(paths, *, force=False):
    rc = 0
    for p in paths:
        env = json.loads(Path(p).read_text(encoding="utf-8"))
        doc_id = env["doc_id"]
        if env.get("payload_kind") != "prose":
            print(f"[건너뜀] {doc_id}: payload_kind={env.get('payload_kind')} "
                  f"— 추출은 비정형만이다 (문서 4 §4.1)")
            continue
        schema = load_schema(env.get("doc_type"))
        if schema is None:
            print(f"[실패] {doc_id}: 미등록 doc_type '{env.get('doc_type')}' "
                  f"— 구축 모드 대상이다")
            rc = 1
            continue
        if force:
            EX.invalidate(doc_id)
        if EX.has_checkpoint(doc_id):
            print(f"[재사용] {doc_id}: 체크포인트가 이미 있다 "
                  f"({EX.checkpoint_path(doc_id).relative_to(ROOT)}) — --force로 재생성")
            continue
        # 추출은 **청크 id를 입력으로 받는다** — 근거 축 id는 인입이 계산한다(§7.2).
        # 그래서 이 진입점은 인입(id 계산·청크 적재)을 선행시킨 뒤 추출만 돈다.
        # 인입은 멱등하므로(같은 내용 → 같은 id) 이미 들어와 있어도 안전하다.
        res = ingest(env)
        if res.status == "held":
            print(f"[보류] {doc_id}: {res.reason}")
            rc = 1
            continue
        ch = store.read(store.CHUNKS, {"chunks": {}})["chunks"]
        loc2id = {c["source_locator"]: cid for cid, c in ch.items()
                  if c.get("doc_id") == doc_id}
        cfg = load_config(schema.get("layer") or "process")
        from core.pipeline import _vocab
        out, made = EX.extract(env, cfg, loc2id, _vocab(cfg))
        n = sum(len(c.get("entities", [])) for c in out["candidates"])
        print(f"[추출] {doc_id}: 청크 {len(out['candidates'])} · 개체 후보 {n} "
              f"→ {EX.checkpoint_path(doc_id).relative_to(ROOT)}")
    return rc


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    force = "--force" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        raise SystemExit("계약 JSON 경로를 달라\n" + __doc__)
    return run(paths, force=force)


if __name__ == "__main__":
    log.setup()
    sys.exit(main(sys.argv[1:]) or 0)
