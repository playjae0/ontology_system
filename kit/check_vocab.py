# -*- coding: utf-8 -*-
"""칸 1.5 — **등록 스키마의 층 어휘 재대조** — 관문 G4C·G4D·G4E를 스키마만으로 (B90 ⑤).

config(층 · 공통)를 바꾸면 이미 등록된 doc_type의 스키마가 새 어휘 밖으로 떨어질 수
있다 — 인입 때 커밋 게이트가 조용히 거르거나, prose는 좌표 블록이 `Process`를 못 불러
관문 FAIL로 그 자리에 선다. `bootstrap`·`doctor`가 이 스크립트로 **관문과 같은 함수**
(`gate_checks.check_vocab`)를 다시 돌린다 — 두 벌 0. 킷은 core를 모르므로 CLI가
subprocess로 부른다(`--layers`로 층 자리를 건넨다 — 관문과 같은 결).

사용: python kit/check_vocab.py [--layers DIR] <schema.json> [<schema.json> ...]
      → 스키마마다 JSON 한 줄 {"schema", "ok", "lines": [판정 줄 …]}
"""
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))            # run_adapter.py와 같은 결 — 킷은 단독 실행 도구다

import gate_screen                        # noqa: E402
import gate_tables as tables              # noqa: E402
from gate_checks import check_vocab       # noqa: E402
from gate_tables import load_blocks       # noqa: E402


def one(path):
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    fields, _blocks = load_blocks(schema)
    gate_screen.ok_all = True
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = check_vocab(schema, fields, Path(path).name)
    return {"schema": str(path), "ok": bool(ok),
            "lines": [ln.strip() for ln in buf.getvalue().splitlines() if ln.strip()]}


def main(argv):
    if tables.LAYERS_FLAG in argv:
        i = argv.index(tables.LAYERS_FLAG)
        tables.LAYERS_DIR = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i:i + 2]
    for p in argv:
        try:
            print(json.dumps(one(p), ensure_ascii=False))
        except Exception as e:                          # noqa: BLE001 — 한 스키마의 실패는 그 줄로
            print(json.dumps({"schema": p, "ok": False,
                              "lines": [f"스키마를 읽지 못했다 — {type(e).__name__}: {e}"]},
                             ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
