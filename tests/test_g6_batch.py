# -*- coding: utf-8 -*-
"""G6 ③ 일괄 투입 — ingest-file·ingest-dir 조건 셋 · 상태 거부 문면의 계약(B61 ①)."""
from __future__ import annotations

import os
import subprocess as _sp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ B46 — 일괄 투입 ingest-file · ingest-dir (문서 6 §6.4 · 조건 셋)")
from cli import ingest as IG                                      # noqa: E402
import tempfile as _tf                                            # noqa: E402
_RAW = ROOT / "tests" / "fixtures" / "raw"
show("doc_id 파생 — 파일명 stem · 공백은 _ · 경로 무관 (D-110)",
     IG.doc_id_of("/a/b/관리 계획서 v3.xlsx") == "관리_계획서_v3"
     and IG.doc_id_of("x/CP01.xlsx") == IG.doc_id_of("y/CP01.xlsx") == "CP01")
_sel = IG.select(_RAW / "CP04_unlabeled.xlsx")
show("선택 — 유일 일치는 자동 (cp) · 근거가 실린다 (조건 ①)",
     _sel["status"] == "chosen" and _sel["doc_type"] == "cp" and _sel["basis"]["by"] == "scan"
     and "완전 일치" in _sel["basis"]["match"], str(_sel["basis"])[:80])
show("선택 — 표류 문서는 0건 → 사람에게 (조건 ③)",
     IG.select(_RAW / "CP02_drift.xlsx")["status"] == "none")
show("선택 — 비정형(pptx)은 스캔하지 않는다 · 지정 필수",
     IG.select(_RAW / "PPT_basic.pptx")["status"] == "none"
     and IG.select(_RAW / "PPT_basic.pptx", doc_type="ppt_quality")["status"] == "none")  # 내장 스키마만 · 어댑터 없음
# **`form`이 근거에 붙었다**(B58 ④ · 문서 1 C37) — 형태 판정은 선택을 바꾸지
# 않지만 **기록은 남긴다**: 문턱 조정과 애매 구간 측정의 유일한 재료다.
# 키 집합을 못박는 것은 몰래 늘어나는 것을 막는 장치라, 늘릴 때 이름을 적는다.
_hsel = IG.select(_RAW / "CP02_drift.xlsx", doc_type="cp")
show("선택 — --doc-type 지정은 스캔 없이 그것으로 (사람 지정 기록)",
     _hsel["status"] == "chosen"
     and {k: v for k, v in _hsel["basis"].items() if k != "form"}
     == {"by": "human", "doc_type": "cp"},
     str(_hsel["basis"])[:60])
show("선택 — 근거에 형태 판정이 함께 남는다 (C37 — 기록이 이 기능의 절반이다)",
     (_hsel["basis"].get("form") or {}).get("verdict") == "table"
     and len((_hsel["basis"]["form"].get("signals") or {})) == 5)
# 다중 일치 — 같은 지문의 어댑터 둘
_td = Path(_tf.mkdtemp(prefix="multi_"))
_src = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
for _nm in ("cp_a", "cp_b"):
    (_td / f"{_nm}.py").write_text(_src.replace('"doc_type": "cp"', f'"doc_type": "{_nm}"', 1), encoding="utf-8")
_amb = IG.select(_RAW / "CP04_unlabeled.xlsx", adapter_paths=[str(_td)])
show("다중 일치 — 둘 이상이면 자동으로 넘기지 않고 사람에게 올린다 (조건 ③)",
     _amb["status"] == "ambiguous" and sorted(_amb["candidates"]) == ["cp_a", "cp_b"], str(_amb["candidates"]))
shutil.rmtree(_td, ignore_errors=True)
# dry-run — 선택만
_before = data_hash()
_row = IG.ingest_file(_RAW / "CP04_unlabeled.xlsx", dry_run=True)
show("--dry-run — 선택 결과만 · 파싱·인입 0 (조건 ②)",
     _row["status"] == "선택만" and data_hash() == _before
     and not (_P.parsed() / "CP04_unlabeled.json").exists())
# 실제 — 파일 1건
_row = IG.ingest_file(_RAW / "CP04_unlabeled.xlsx")
_reg = store.read(store.DOC_REGISTRY, {}).get("CP04_unlabeled") or {}
show("ingest-file — 선택 → 파싱 → 인입 완주 (record 12)", _row["status"] == "성공" and "record 12" in _row["reason"])
show("인입 기록에 선택 근거가 남는다 — doc_registry.routing (조건 ① · 오배정률의 재료)",
     _reg.get("routing", {}).get("by") == "scan" and _reg["routing"]["doc_type"] == "cp", str(_reg.get("routing"))[:80])
# 경로 — 문서 단위 독립 · 성공/실패/미선택
_bd = Path(_tf.mkdtemp(prefix="batch_"))
for _f in ("CP01.xlsx", "CP03_bad.xlsx", "CP04_unlabeled.xlsx", "TOC01.xlsx"):
    shutil.copy(_RAW / _f, _bd / _f)
# **블록은 사람 화면의 것이다** — 스위트 stdout에 `[FAIL]`이 섞이면 doctor가
# 그것을 스위트의 실패로 센다(계수는 줄머리로 한다). 받아서 검사만 한다.
_buf6 = _io.StringIO()
with _ctx.redirect_stdout(_buf6):
    _rows = IG.ingest_dir(_bd)
_out6 = _buf6.getvalue()
_st = {r["doc_id"]: r["status"] for r in _rows}
show("ingest-dir — 4건 순회 · 성공 2 · 실패 1(C14 파싱 실패) · 미선택 1(지문 0건)",
     _st == {"CP01": "성공", "CP03_bad": "실패", "CP04_unlabeled": "성공", "TOC01": "미선택"}, str(_st))
show("한 건의 실패가 나머지를 멈추지 않는다 — 실패 뒤의 문서도 인입됐다",
     [r["doc_id"] for r in _rows].index("CP03_bad") < [r["doc_id"] for r in _rows].index("CP04_unlabeled")
     and _st["CP04_unlabeled"] == "성공")
# ── B79 ② — **원본 자리(⓪)와 기록 표기** ──────────────────────────────
# 사내 물음: 「원본 문서도 ONTO_HOME에 있어야 하는 것 아닌가」. 그렇다 — 그리고
# 대장의 표기가 절대 경로면 루트를 옮긴 다음 전건이 「다른 경로」로 뜬다.
_dz = _P.raw("사내", "가지")
_dz.mkdir(parents=True, exist_ok=True)
shutil.copy(_RAW / "CP01.xlsx", _dz / "CP01.xlsx")
_buf79 = _io.StringIO()
with _ctx.redirect_stdout(_buf79):
    _rows79 = IG.main(["--allow-mock"])          # 인자 없이 = 원본 자리 전체
_out79 = _buf79.getvalue()
_reg79 = store.read(store.DOC_REGISTRY, {}).get("CP01") or {}
show("② 인자 없는 ingest-dir가 원본 자리를 **재귀로** 돈다 (하위 폴더에 넣는다)",
     str(_P.raw()) in _out79 and "CP01" in _out79,
     str(_reg79.get("source_path")))
show("② 상태 루트 아래 문서의 기록은 루트 기준 상대다 (절대 경로 0 — 옮겨도 낡지 않는다)",
     not Path(_reg79.get("source_path", "/x")).is_absolute()
     and _reg79["source_path"].startswith("raw/"),
     str(_reg79.get("source_path")))
# 밖의 문서는 절대 경로다 — 옮길 수 있는 자리가 아니다.
_out_reg = store.read(store.DOC_REGISTRY, {}).get("CP04_unlabeled") or {}
show("② 상태 루트 밖의 문서는 절대 경로로 남는다 (되돌릴 기준이 없다)",
     Path(_out_reg.get("source_path", "x")).is_absolute(), str(_out_reg.get("source_path")))
# **루트를 옮겨도 같은 문서다** — 기록이 상대라 비교가 새 루트에서 맞는다.
# (mock 루트는 자리가 고정이므로 루트 갈아 끼우기는 `USE_MOCK=0`으로 잰다 —
#  재는 것은 경로 비교 하나이고 게이트웨이는 필요 없다.)
_moved = Path(_tf.mkdtemp(prefix="b79move_"))
(_moved / "raw" / "사내" / "가지").mkdir(parents=True)
shutil.copy(_RAW / "CP01.xlsx", _moved / "raw" / "사내" / "가지" / "CP01.xlsx")
_keepenv = {k: os.environ.get(k) for k in ("ONTO_HOME", "USE_MOCK")}
try:
    os.environ.update(ONTO_HOME=str(_moved), USE_MOCK="0")
    _P.reset()
    _same79 = (IG._norm_path(_reg79["source_path"])
               == IG._norm_path(_moved / "raw" / "사내" / "가지" / "CP01.xlsx"))
finally:
    for _k, _v in _keepenv.items():
        os.environ.pop(_k, None) if _v is None else os.environ.__setitem__(_k, _v)
    _P.reset()
show("② 루트를 옮겨도 기록이 같은 문서를 가리킨다 (「다른 경로」 경고가 뜨지 않는다)",
     _same79, f"{_reg79['source_path']} ↔ {_moved}")
shutil.rmtree(_moved, ignore_errors=True)
shutil.rmtree(_P.raw(), ignore_errors=True)

# **옛 이름(`docs/`)에 넣은 사람은 0건이 아니라 문면을 본다**(B80 ②).
_old_raw = _P.home() / "docs"
(_old_raw / "사내").mkdir(parents=True, exist_ok=True)
shutil.copy(_RAW / "CP01.xlsx", _old_raw / "사내" / "CP01.xlsx")
try:
    IG._raw_target()
    _msg80 = ""
except SystemExit as e:
    _msg80 = str(e)
show("② 옛 이름에 문서가 있으면 상태 거부다 — 문면이 `mv`를 준다 (0건으로 끝내지 않는다)",
     "raw/`로 바뀌었다" in _msg80 and f"mv {_old_raw}" in _msg80
     and str(_P.raw()) in _msg80, _msg80.splitlines()[:1])
shutil.rmtree(_old_raw, ignore_errors=True)
# 파서가 읽지 않는 포맷만 있으면 「문서가 없다」다 — 기준은 reader.SUPPORTED 하나다.
_P.raw().mkdir(parents=True, exist_ok=True)
(_P.raw() / "메모.txt").write_text("사람의 메모", encoding="utf-8")
try:
    IG._raw_target()
    _msg81 = ""
except SystemExit as e:
    _msg81 = str(e)
show("② 선별 기준은 파서가 읽는 포맷 하나다 (메모·임시파일은 배치가 아니다)",
     "넣을 문서가 없다" in _msg81
     and all(x in _msg81 for x in IG.SUPPORTED), _msg81.splitlines()[:1])
shutil.rmtree(_P.raw(), ignore_errors=True)

show("③ 실패 문서의 화면에 블록이 떴다 (태그·다음 줄 — B61)",
     "[FAIL] P31" in _out6 and "▶ 다음 줄" in _out6
     and "python -m cli.register" in _out6)
show("끝에 모아 보이는 목록 — 성공·실패·미선택 3구획",
     all(k in IG.summary(_rows) for k in ("[성공]", "[실패]", "[미선택]")))
with _ctx.redirect_stdout(_io.StringIO()):
    _dry = IG.ingest_dir(_bd, dry_run=True)
show("ingest-dir --dry-run — 전부 선택만/미선택, 인입 0",
     all(r["status"] in ("선택만", "미선택") for r in _dry))
shutil.rmtree(_bd, ignore_errors=True)
for _f in ("CP01", "CP03_bad", "CP04_unlabeled"):
    (_P.parsed() / f"{_f}.json").unlink(missing_ok=True)

# ── B61 ① 상태 거부는 원인과 다음 줄을 낸다 ──────────────────────────────
print("\n■ B61 ① — 상태 거부 문면의 계약 (사람이 치는 자리 전수)")

sys.path.insert(0, str(ROOT / "tests"))
import exits_scan as _EX                                         # noqa: E402

_rows61 = _EX.scan()
_st61 = [r for r in _rows61 if r["mark"] == "상태"]
# ⓑ **상태 거부 전건이 계약을 지킨다** — 원인만 말하고 끝내지 않는다.
def _at61(rows):
    return [r["file"] + ":" + str(r["line"]) for r in rows]


show("①ⓑ 상태 거부 전건에 그대로 칠 수 있는 다음 줄이 있다",
     _st61 and not _EX.broken(_rows61),
     f"상태 {len(_st61)}곳 · 위반 {_at61(_EX.broken(_rows61))}")
# ⓒ **분류 없는 거부가 0이다** — 새 `SystemExit`은 목록에 들거나 사용법으로 표시돼야
# 한다. 이것이 **다음 자리를 잡는 장치**다: 자리마다 고치면 다음 자리에서 또 난다.
show("①ⓒ 분류 없는 SystemExit이 0건이다 (새 거부는 표시해야 통과한다)",
     not _EX.unmarked(_rows61),
     f"{len(_rows61)}곳 전수 · 미분류 {_at61(_EX.unmarked(_rows61))}")
# ⓓ **변이** — 표시 없는 거부를 하나 넣으면 붉어진다(그리고 되돌린다).
_p61 = ROOT / "cli" / "viewer.py"
_src61 = _p61.read_text(encoding="utf-8")
_p61.write_text(_src61 + '\n\ndef _b61_probe():\n'
                         '    raise SystemExit("표시 없는 거부")\n', encoding="utf-8")
try:
    _mut61 = len(_EX.unmarked())
finally:
    _p61.write_text(_src61, encoding="utf-8")
show("①ⓓ 표시 없는 거부를 하나 넣으면 붉어진다 (되돌리면 초록)",
     _mut61 == 1 and not _EX.unmarked(), f"심었을 때 미분류 {_mut61}건")

# ── B69 ④ 다음 줄의 명령이 **실재하는가** ────────────────────────────────
#
# B68 회차 실측: `python run.py doctor`를 다음 줄로 주던 거부가 있었다 — 그런 명령이
# 없어 치면 `KeyError`다. 스캐너가 **접두만** 봐서 초록이었다. 「그대로 칠 수 있는
# 다음 줄」은 **칠 수 있어야** 계약이다(B61). 문면을 세지 않는다 — 이름의 실재만.
show("④ 다음 줄의 명령이 전부 실재한다 (run.py 명령표 · cli 모듈 · 파일)",
     not _EX.unknown_next(_rows61),
     str([r["file"] + ":" + str(r["line"]) + " " + r["cmd"]
          for r in _EX.unknown_next(_rows61)][:3]))
show("④ 명령 이름의 정본은 run.py의 명령표다 (문면을 읽지 않는다)",
     {"ingest-file", "register", "scan"} <= _EX.run_commands()
     and "doctor" not in _EX.run_commands(), f"{len(_EX.run_commands())}개")
# ⓑ **변이** — 없는 명령을 하나 심으면 붉어진다(그리고 되돌린다).
_src69 = _p61.read_text(encoding="utf-8")
_p61.write_text(_src69 + '\n\ndef _b69_probe():\n'
                         '    raise SystemExit("[viewer] 없다\\n'
                         '  ▶ 다음 줄:\\n     python run.py nosuch")  # [상태]\n',
                encoding="utf-8")
try:
    _mut69 = _EX.unknown_next()
finally:
    _p61.write_text(_src69, encoding="utf-8")
show("④ⓑ 없는 명령을 다음 줄로 주면 붉어진다 (되돌리면 초록)",
     len(_mut69) == 1 and _mut69[0]["cmd"] == "run:nosuch"
     and not _EX.unknown_next(), str([r["cmd"] for r in _mut69]))


# ── B70 ①② — mock 자산은 운영 경로에 섞이지 않는다 · 결손은 막는다 ────────
#
# 이식 직후 사내 화면이 **cp·pfmea·ipqc**를 대조 목록에 띄웠다(실측 열째 — 「mock이랑
# 비교 돌아가는 거 뭐야」). 내장 소재지(픽스처 어댑터 폴더·`schemas/*.json`)가
# `USE_MOCK`과 무관하게 열렸기 때문이다. mock 트랙은 남는다 — 섞이는 것만 걷는다.

done()
