# -*- coding: utf-8 -*-
"""B88 ①②③ — 리더의 폭과 그림 이해: 엑셀 그림 → ④ · Word(docx) · 등록 doc_type 재확인 (칸 1.x · 2.1 · 2.2 · 2.5 · ④).

표본은 `tests/fixtures/raw/IMG01.xlsx`·`DOC01.docx`·`DOC02.docx`(`tests/fixtures/make_b88.py`).
잠그는 성질:
  ① prose 시트 그림마다 image 조각 1 · ref·skip 시트 그림 0 · 계약 JSON에 바이트 0 · 재인입 호출 0 ·
     WMF는 변환기가 있으면 요약, 없으면 건너뜀 줄에 사유 · `--no-images`는 호출 0 + 기록 · 예고가 먼저
  ② 개요 수준대로 section(스타일 id 로캘 무관 · 상속) · 개요 없으면 번호 패턴 · 표는 행마다 한 줄 ·
     그림은 ④ 조각 · 머리글·삭제 글자 0 · `.doc` 거부 문면 · 선택 의존 0 · 킷 관문 PASS
  ③ 등록된 doc_type의 `status`는 운영 어댑터를 읽는다 · 다음 줄에 `confirm` 0
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, done   # noqa: F401

from parser import ooxml, render                                       # noqa: E402
from parser.adapters import basic_docx as DX, basic_prose_xlsx as BX   # noqa: E402

IMG, DOC1, DOC2 = RAW / "IMG01.xlsx", RAW / "DOC01.docx", RAW / "DOC02.docx"
ROLES = {"사양": "prose", "도면": "ref"}
ENV = {**os.environ, "USE_MOCK": "1", "NO_COLOR": "1"}


def _parse(path, adapter, doc_id, **kw):
    struct_map.invalidate(doc_id)
    return pipeline.parse(adapter, doc_id, str(path), closed_list=[], **kw)


def _imgs(res):
    return [c for c in res.envelope["chunks"] if c.get("image_ref")]


def _run(*argv):
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                       cwd=str(ROOT), env=ENV, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


# ────────────────────────────────────────────────────────────── ①
print("\n■ B88 ① 엑셀 그림 → ④ 이미지 요약")
_fake_png = lambda data, mime: (b"\x89PNG-converted", None)            # noqa: E731
_orig_png = render.to_png
render.to_png = _fake_png
try:
    _r = _parse(IMG, BX, "B88IMG", sheet_roles=ROLES)
finally:
    render.to_png = _orig_png
_ir = {c["image_ref"]: c for c in _imgs(_r)}
show("① prose 시트 그림마다 image 조각 1 — PNG · WMF(변환) 둘 다 · section은 앉은 행의 청크",
     set(_ir) == {"img_001", "img_002"}
     and _ir["img_001"]["section"] == "1. 개요" and _ir["img_002"]["section"] == "2. 설비"
     and _ir["img_002"]["meta"].get("image_converted_from") == "image/x-wmf",
     str({k: (v["section"], v["meta"].get("image_mime")) for k, v in _ir.items()}))
_skip = _parse(IMG, BX, "B88IMGS", sheet_roles={"사양": "prose", "도면": "skip"})
show("① ref · skip 시트의 그림은 조각 0 (참조 = LLM 0 · skip은 읽지 않는다)",
     "img_003" not in _ir and "img_003" not in {c["image_ref"] for c in _imgs(_skip)})
_js = json.dumps(_r.envelope, ensure_ascii=False, default=str)
show("① 계약 JSON에 바이트 0 (`_images`·바이트 표기 없음 — 바이트는 raw에만)",
     "_images" not in _js and "b'" not in _js and "\\x89" not in _js)

_calls, _order = [], []


def _summ(ref, image=None, mime=None, context="", page=None):
    _calls.append((ref, mime, len(image or b"")))
    _order.append("요약")
    return f"요약 {ref}"


render.to_png = _fake_png
try:
    _l1 = _parse(IMG, BX, "B88LIVE", sheet_roles=ROLES, summarize=_summ,
                 image_notice=lambda info: _order.append(("예고", info["새"])))
    _first, _ord1 = list(_calls), list(_order)
    _calls.clear()
    pipeline.parse(BX, "B88LIVE", str(IMG), closed_list=[], sheet_roles=ROLES,
                   summarize=_summ, image_notice=lambda info: None)
finally:
    render.to_png = _orig_png
show("① 예고가 부르기 전에 온다 · 새 그림 수만큼 부른다 (보내는 것은 PNG 바이트)",
     _ord1[0] == ("예고", 2) and len(_first) == 2
     and all(m == "image/png" and n > 0 for _r2, m, n in _first), str(_ord1))
show("① 같은 파일 재인입은 호출 0 (보존된 요약 재사용)", not _calls, str(_calls))

_saved = render.shutil.which
render.shutil.which = lambda _n: None                   # 변환기 없는 사내
try:
    _nr = _parse(IMG, BX, "B88NOCONV", sheet_roles=ROLES)
finally:
    render.shutil.which = _saved
_rw = _nr.report.get("read_warnings") or {}
from cli import parse as _cp                                           # noqa: E402
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _cp.print_read_warnings(_nr.report)
show("① 변환기가 없으면 WMF만 건너뛴다 — 건너뜀 줄에 형식과 사유",
     {c["image_ref"] for c in _imgs(_nr)} == {"img_001"}
     and _rw.get("images_dropped") == {"WMF": 1} and render.NO_CONVERTER in _buf.getvalue(),
     _buf.getvalue().strip())
_calls.clear()
_ni = _parse(IMG, BX, "B88NOIMG", sheet_roles=ROLES, summarize=_summ, no_images=True)
show("① `--no-images`면 그림 호출 0 · 조각 0 · 보고에 수와 사유",
     not _calls and not _imgs(_ni)
     and _ni.report.get("images") == {"요약_안_함": 2, "사유": "--no-images"})
_rc, _o = _run("-m", "cli.parse", "run", "parser/adapters/basic_prose_xlsx.py", str(IMG),
               str(Path(tempfile.gettempdir()) / "b88_noimg.json"), "--doc-id", "B88NOIMG2",
               "--sheets", "1:prose 2:ref", "--no-images", "--allow-mock")
_env = json.loads((Path(tempfile.gettempdir()) / "b88_noimg.json").read_text(encoding="utf-8"))
from core.build import ingest as _ing                                  # noqa: E402
_ing.register_doc(_env, "b88", routing=None)
_rc2, _o2 = _run("run.py", "show", "doc", "B88NOIMG2")
show("① `--no-images`는 인입 기록과 `show doc`에 남는다 (조용한 건너뜀 0)",
     _env.get("context", {}).get("images_skipped") == {"n": 2, "why": "--no-images"}
     and "2장 요약 안 함(--no-images)" in _o2, [l.strip() for l in _o2.splitlines() if "그림" in l][:1])
_plain = read(str(RAW / "RFQ01.xlsx"))
show("① 그림 없는 엑셀은 판독에 그림 키가 없고 그림 조각도 0이다",
     "_images" not in _plain and not any(s.get("images") for s in _plain["sheets"])
     and not any(p.get("image_ref") for p in BX.extract(_plain)))

# ────────────────────────────────────────────────────────────── ②
print("\n■ B88 ② Word(docx) — 표준 라이브러리 · B87 분할 엔진")
_d1 = read(str(DOC1))
_rows1 = DX._rows(_d1, DX._lines(_d1))
_t1 = {p["index"]: p["text"] for p in _d1["paragraphs"]}
_heads1 = [(_t1[r["row"]], r["level"]) for r in _rows1 if r["heading"]]
show("② 한글 스타일(id `1`·`2`)의 제목이 **개요 수준**대로 선다 — 상속한 스타일까지",
     _heads1 == [("개요", 1), ("적용 범위", 2), ("기계 사양", 1), ("프레스", 2), ("정리", 1)],
     str(_heads1))
_d2 = read(str(DOC2))
_rows2 = DX._rows(_d2, DX._lines(_d2))
_t2 = {p["index"]: p["text"] for p in _d2["paragraphs"]}
_heads2 = [(_t2[r["row"]], r["level"]) for r in _rows2 if r["heading"]]
show("② 스타일 없이 번호만 있는 문서는 B87 번호 패턴으로 선다 · 번호 목록(`w:numPr`)은 제목 아님",
     _heads2 == [("1. 개요", 1), ("1.1 적용 범위", 2), ("2. 사양", 1)], str(_heads2))
_p1 = DX.extract(_d1)
_txt = "\n".join(p.get("text") or "" for p in _p1)
show("② 표는 행마다 한 줄 `셀 | 셀 | …`로 그 절의 본문에 든다",
     "가압력 | 120 kN | 이상" in _txt.splitlines()
     and any("정밀도 | ±0.05 mm | 이내" in (p.get("text") or "") and p["section"] == "개요"
             for p in _p1))
_dimg = [p for p in _p1 if p.get("image_ref")]
show("② 그림은 ④ 조각 — 같은 절의 section · context",
     len(_dimg) == 1 and _dimg[0]["section"] == "개요" and _dimg[0]["context"]
     and "D-IMG001" in (_d1.get("_images") or {}), str([(p["image_ref"], p["section"]) for p in _dimg]))
show("② 머리글·변경 추적 삭제 글자는 본문에 0",
     "머리글" not in _txt and "삭제된 옛 문장" not in _txt and "분말 고속도강" in _txt)
_old = Path(tempfile.gettempdir()) / "b88_옛문서.doc"
_old.write_bytes(b"\xd0\xcf\x11\xe0")
try:
    read(str(_old))
    _msg = ""
except ValueError as e:
    _msg = str(e)
_rc, _o = _run("run.py", "ingest-file", str(_old), "--allow-mock")
show("② `.doc`(옛 이진 형식)는 거부 — 문면이 「`.docx`로 저장해 다시 넣는다」",
     "`.docx`로 저장해 다시 넣는다" in _msg and "`.docx`로 저장해 다시 넣는다" in _o, _msg[:60])
_imp = [f"{f.relative_to(ROOT)}:{i}" for f in (ROOT / "parser").rglob("*.py")
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if ln.strip().startswith(("import docx", "from docx"))]
show("② docx는 선택 의존 0 — `import docx` 0 · requirements에 없다",
     not _imp and "docx" not in (ROOT / "requirements.txt").read_text(encoding="utf-8").lower(),
     str(_imp))
from cli.register import gate as _gate                                   # noqa: E402
_sch = Path(tempfile.gettempdir()) / "b88_docx_schema.json"
_sch.write_text(json.dumps({"doc_type": "prose_docx_basic", "schema_version": 1,
                            "layer": "process", "payload_kind": "prose",
                            "use_blocks": ["common_core", "process_coord"],
                            "fields": {}, "edges": []}, ensure_ascii=False), encoding="utf-8")
_ok, _out = _gate.harness(ROOT / "parser/adapters/basic_docx.py", _sch, [str(DOC1), str(DOC2)])
show("② 킷 관문 전 구간 PASS — 기본 docx 어댑터 · 표본 둘",
     _ok and "[FAIL]" not in _out, f"PASS {_out.count('[PASS]')}")

# ────────────────────────────────────────────────────────────── ③
print("\n■ B88 ③ 등록된 doc_type 재확인 — 지금 코드 · 운영 어댑터")
_run("-m", "cli.register", "generate", "b88docx", "process", str(DOC1), "--allow-mock")
_run("-m", "cli.register", "confirm", "b88docx", "--by", "시험", "--allow-mock")
_rc, _st = _run("-m", "cli.register", "status", "b88docx")
_rev = _P.review("b88docx", "adapter.py")
_keep = _rev.read_text(encoding="utf-8")
_rev.write_text("이것은 파이썬이 아니다(\n", encoding="utf-8")         # 검수 사본을 망가뜨린다
_rc2, _st2 = _run("-m", "cli.register", "status", "b88docx")
_rev.write_text(_keep, encoding="utf-8")
_ops = _P.registry("adapters", "b88docx.py")
_keep_ops = _ops.read_text(encoding="utf-8")
_ops.write_text("이것은 파이썬이 아니다(\n", encoding="utf-8")          # 운영 어댑터를 망가뜨린다
_rc3, _st3 = _run("-m", "cli.register", "status", "b88docx")
_ops.write_text(_keep_ops, encoding="utf-8")
show("③ 등록된 doc_type의 `status`는 **운영 어댑터**로 돈다 — 검수 사본을 바꿔도 불변 · 운영을 바꾸면 FAIL",
     _rc == 0 and "지금 코드로 관문 PASS" in _st and _rc2 == 0 and "PASS" in _st2
     and _rc3 != 0 and "관문 FAIL" in _st3,
     [l.strip() for l in (_st + _st3).splitlines() if l.startswith("■")][:2])
show("③ 다음 줄에 `confirm`이 없다 (이미 등록됐다)",
     "cli.register confirm" not in _st and "cli.register confirm" not in _st3)
import shutil                                                          # noqa: E402
shutil.rmtree(_P.review("b88docx"), ignore_errors=True)
for _f in (_ops, _P.registry("schemas", "b88docx.json")):
    Path(_f).unlink(missing_ok=True)
_dts = store.read(store.DOC_TYPES, {})
_dts.pop("b88docx", None)
store.write(store.DOC_TYPES, _dts)

done()
