# -*- coding: utf-8 -*-
"""같은 표의 두 포맷이 같은 지식이 되는가 — 전 구간 스냅샷 (B66 ⑤).

`CP01.xlsx`와 그 시트를 그대로 옮긴 `CP01.csv`를 **각각 클린에서** 인입하고,
봉투 · 그래프 · 스모크 질의의 답을 한 덩어리 JSON으로 찍는다. 비교는 부르는
쪽(`test_p3`)이 한다.

**왜 별도 프로세스인가.** 한 프로세스에서 두 번 인입하면 앞 판의 그래프·사전·
체크포인트가 살아 있어 「둘째 판이 첫 판을 봤다」가 된다. 회귀 판정의 기준은
클린 단독 실행이다(문서 7 §7.6-4).

**무엇을 빼고 비교하나.** 포맷이 다르면 태생적으로 다른 것이 셋이다:

  * `source_path` — 봉투에 `format` 키는 없다. 포맷은 경로의 확장자로만 남는다.
  * `source_locator`의 **시트 이름** — xlsx는 시트명(`관리계획서`), CSV는 파일명
    (`CP01`)이다. 행 번호 뒤는 같다.
  * 근거 id — `chunk_id`는 `section`(= 시트 이름을 포함한 로케이터)의 해시라
    위의 제외가 id 안쪽에 박힌다. **되돌릴 수 없으니 재계산한다** — 근거를
    「가리키는 자리」(층·표제어 · 로케이터·본문)로 비교한다. 노드 id는 ULID라
    같은 문서를 두 번 돌려도 다르다(D-146).

사용: python tests/csv_equiv.py <문서> [--mut]   ← `--mut`은 헤더 한 셀 변이
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import ingest as I, query as R                      # noqa: E402
from core import init                                        # noqa: E402
from core import paths as _P               # 상태 자리는 한 모듈이 안다 (B78 1a)
from core.bootstrap import bootstrap, open_graph             # noqa: E402
from router import discover                                  # noqa: E402
from parser import reader                                    # noqa: E402

QUERIES = json.loads((ROOT / "tests" / "fixtures" / "queries.json")
                     .read_text(encoding="utf-8"))["queries"]
MUT_LABEL = "관리항목"


def mutate():
    """`reader.read_csv`가 헤더 한 셀을 바꾸도록 심는다 — 변이 시험용.

    등가 어서션이 **정말 두 판을 비교하는지**를 재는 자리다. 여기서 비교가
    초록으로 남으면 그 어서션은 아무것도 잠그지 않는다.
    """
    orig = reader.read_csv

    def patched(path):
        raw = orig(path)
        for sh in raw["sheets"]:
            for ref, v in sh["cells"].items():
                if v == MUT_LABEL:
                    sh["cells"][ref] = v + "_변이"
                    return raw
        return raw

    reader.read_csv = patched


def sheetless(loc):
    """로케이터에서 시트 이름을 뗀다 — `관리계획서!R4` · `CP01!R4` → `R4`."""
    return loc.split("!", 1)[-1] if isinstance(loc, str) and "!" in loc else loc


# 사실 문장에 실리는 출처(`CP01#관리계획서!R19`)에도 시트 이름이 박힌다 —
# 로케이터가 어디에 나타나든 같은 제외를 적용한다.
_LOC = re.compile(r"#[^()\s#]*!(R\d+)")


def sheetless_text(s):
    return _LOC.sub(r"#\1", s)


def envelope(doc_id):
    """계약 JSON — 포맷 태생의 차이 셋을 뺀 판."""
    p = _P.parsed() / f"{doc_id}.json"
    if not p.exists():
        return None
    env = json.loads(p.read_text(encoding="utf-8"))
    env.pop("source_path", None)
    env.pop("doc_id", None)
    for key in ("records", "chunks"):
        for item in env.get(key) or []:
            if isinstance(item, dict) and item.get("source_locator"):
                item["source_locator"] = sheetless(item["source_locator"])
            if isinstance(item, dict) and item.get("section"):
                item["section"] = sheetless(item["section"])
    return env


def graph():
    """층별 노드 수 · 엣지 수 · 카테고리별 수."""
    out = {}
    for layer in discover():
        g = open_graph(layer)
        cats = {}
        for n in g.nodes.values():
            cats[n["category"]] = cats.get(n["category"], 0) + 1
        out[layer] = {"nodes": len(g.nodes), "edges": len(g.edges), "categories": cats}
    return out


def evidence(res):
    """근거가 **가리키는 자리** — id 문자열이 아니다(위 「무엇을 빼고」)."""
    ev = [f"node|{n['layer']}|{n['canonical']}" for n in res.get("linked_nodes") or []]
    ev += [f"chunk|{c.get('tier')}|{sheetless(c.get('source_locator'))}|{c.get('text')}"
           for c in res.get("chunks") or []]
    return sorted(ev)


def queries():
    return [{"id": q["id"], "path": (r := R.answer(q["q"]))["path"],
             "facts": sorted(sheetless_text(f) for f in r["facts"]),
             "evidence": evidence(r)}
            for q in QUERIES]


def main(argv):
    doc = argv[0]
    if "--mut" in argv:
        mutate()
    buf = io.StringIO()                  # 인입 화면은 스냅샷이 아니다
    with contextlib.redirect_stdout(buf):
        init.init(fresh_=True)
        for layer in discover():
            bootstrap(layer, echo=False)
        row = I.ingest_file(doc, doc_type="cp")
    snap = {"doc": doc, "ingest": row["status"], "reason": row["reason"],
            "envelope": envelope(row["doc_id"]), "graph": graph(), "queries": queries()}
    print(json.dumps(snap, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
