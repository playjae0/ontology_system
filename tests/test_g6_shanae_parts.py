# -*- coding: utf-8 -*-
"""B86 ①~⑤ — 「사내 모양」 잔여 다섯의 잠금 (⑥ 전 구간은 `test_g6_shanae_root`).

잠그는 성질:
  ① 화면의 경로는 `paths.show` 하나가 적는다 — `relative_to(ROOT)` 0 · 세 갈래 무예외
  ② 파서는 레포 자리를 모른다 — 주입이 없으면 문면 있는 실패 · 킷은 플래그로 받는다
  ③ 대장 없음 문면의 경로 == 실제 자리 · 점검_경로가 갈린 토큰 형태도 잡는다
  ④ 선택 의존 부재는 **상태 거부**(설치 줄) · 버린 그림은 한 줄 · stderr 경고 0
  ⑤ 등록 표본에도 시트 관문 — 한 번 묻고 기록 · 두 번째는 기록대로 · skip 시트는 킷에 없다
"""
from __future__ import annotations

import importlib.util
import io
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _sp72, done, json, os, store)   # noqa: F401

from cli import _screen                                              # noqa: E402
from core.build import ledger as LEDGER                              # noqa: E402
from core.state import sheets as SH                                  # noqa: E402

RFQ = ROOT / "tests" / "fixtures" / "raw" / "RFQ01.xlsx"
TOC = ROOT / "tests" / "fixtures" / "raw" / "TOC01.xlsx"
DT = "b86_rfq_sample"            # 등록 표본 시험의 doc_type — 끝나면 치운다
DT2 = "b86_rfq_again"            # 같은 파일을 다른 종류로 — 기록은 문서의 것이다
ENV = {**os.environ, "USE_MOCK": "1", "NO_COLOR": "1"}
ENV.pop("ONTO_MOCK_HOME", None)


def _sp(*argv, env=None, cwd=None):
    r = _sp72.run([sys.executable, *argv], capture_output=True, text=True,
                  cwd=str(cwd or ROOT), env=env or ENV, stdin=_sp72.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def _pty(*argv, answers=""):
    """관문은 tty에서만 산다 — `test_g6_sheets`와 같은 방식."""
    import pty
    pid, fd = pty.fork()
    if pid == 0:                                             # pragma: no cover
        os.environ.update({"USE_MOCK": "1", "NO_COLOR": "1"})
        os.chdir(str(ROOT))
        os.execv(sys.executable, [sys.executable, *argv])
    os.write(fd, answers.encode())
    out = b""
    try:
        while True:
            d = os.read(fd, 4096)
            if not d:
                break
            out += d
    except OSError:
        pass
    _p, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st), _screen.strip_ansi(out.decode("utf-8", "replace"))


def _untracked():
    """코드 폴더의 변경 — 상태 루트(`state_mock/`)는 git이 무시한다."""
    r = _sp72.run(["git", "status", "--porcelain", "-uall"], capture_output=True,
                  text=True, cwd=str(ROOT))
    return set(r.stdout.splitlines())


def _clean_dt():
    for d in (DT, DT2):
        shutil.rmtree(_P.registry() / "review" / d, ignore_errors=True)
    SH.path("RFQ01").unlink(missing_ok=True)
    SH.path("TOC01").unlink(missing_ok=True)


_sp("run.py", "init", "--fresh")
_sp("run.py", "bootstrap")
_clean_dt()

# ────────────────────────────────────────────────────────────── ①
print("\n■ B86 ① 화면의 경로 — `paths.show` 한 자리")
_hits = []
for base in ("cli", "core", "kit", "doctor.py", "run.py"):
    for p in ([ROOT / base] if base.endswith(".py") else sorted((ROOT / base).rglob("*.py"))):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "relative_to(ROOT)" in ln:
                _hits.append(f"{p.relative_to(ROOT).as_posix()}:{i}")
show("① 운영 코드에 `relative_to(ROOT)`가 **0**이다 (상태가 코드 밖이면 죽던 자리)",
     not _hits, str(_hits[:3]))
_out = Path(tempfile.gettempdir()) / "b86_없는_폴더" / "a.json"
_three = [_P.show(_P.registry() / "doc_types.json"),
          _P.show(ROOT / "kit" / "run_adapter.py"), _P.show(_out)]
show("① 세 갈래 — 상태 안은 상태 기준 · 레포 안은 레포 기준 · 밖은 절대 경로 (예외 0)",
     _three[0] == "registry/doc_types.json" and _three[1] == "kit/run_adapter.py"
     and Path(_three[2]).is_absolute(), str(_three))

# ────────────────────────────────────────────────────────────── ②
print("\n■ B86 ② 파서는 레포 자리를 모른다 — 킷은 플래그로 받는다")
_proot = [f"{p.relative_to(ROOT).as_posix()}:{i}"
          for p in sorted((ROOT / "parser").rglob("*.py"))
          for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
          if re.search(r"\bROOT\s*/", ln) and not ln.lstrip().startswith("#")]
show("② `parser/`에 `ROOT / …` 경로 조립이 **0**이다", not _proot, str(_proot[:3]))
_r1 = _sp("-c", "from parser import tagger; tagger.snapshot_path()")
_r2 = _sp("-c", "from parser import struct_map; struct_map.keep_dir()")
show("② 주입 없이 부르면 **문면 있는 실패**다 (레포 기본값으로 조용히 떨어지지 않는다)",
     _r1[0] != 0 and "[파서]" in _r1[2] and "--closed-list" in _r1[2]
     and _r2[0] != 0 and "[파서]" in _r2[2],
     [l for l in (_r1[2] + _r2[2]).splitlines() if "[파서]" in l][:1])

# ────────────────────────────────────────────────────────────── ③
print("\n■ B86 ③ 대장의 자리 — 문면 == 실제 · 점검이 갈린 형태도 잡는다")
_rc, _o, _e = _sp("run.py", "show", "report", "ZZ_B86")
_want = _P.show(store.path(LEDGER.name_of("ZZ_B86")))
_dir = store.path(LEDGER.DIR)
_n = len(list(_dir.glob("*.json"))) if _dir.exists() else 0
show("③ 대장 없음 문면의 경로가 **store가 아는 자리**이고 대장 수도 거기서 센다",
     _want in (_o + _e) and f"대장 파일 {_n}건" in (_o + _e) and "Traceback" not in _e,
     _want)
_spec = importlib.util.spec_from_file_location(
    "chk_path", ROOT / "docs" / "회귀스위트" / "점검_경로.py")
_chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_chk)
_rx = _chk._split_form("data/ingest_log")   # 옛 배치
show("③ 점검_경로가 **토큰이 갈린 옛 자리**를 잡는다 (변이) · 지금 자리는 잡지 않는다",
     "data/ingest_log" in _chk.MOVED and _rx is not None   # 옛 배치
     and _rx.search("ROOT / 'data' / 'ingest_log'")   # 옛 배치
     and _rx.search('ROOT/"data"/"ingest_log"')   # 옛 배치
     and not _rx.search("ROOT / 'work' / 'ingest_log'"))

# ────────────────────────────────────────────────────────────── ④
print("\n■ B86 ④ 선택 의존 부재는 상태 거부 · 버린 그림은 한 줄")
_tmp = Path(tempfile.mkdtemp(prefix="b86_"))
(_tmp / "openpyxl").mkdir()
(_tmp / "openpyxl" / "__init__.py").write_text(
    "raise ImportError('B86 시험 — openpyxl을 가린다')\n", encoding="utf-8")
_blind = {**ENV, "PYTHONPATH": str(_tmp)}
_rc, _o, _e = _sp("run.py", "ingest-file", str(ROOT / "tests/fixtures/raw/CP01.xlsx"),
                  "--allow-mock", env=_blind)
_rcp, _op, _ep = _sp("-m", "cli.parse", "run", "parser/adapters/basic_prose_xlsx.py",
                     str(RFQ), str(_tmp / "out.json"), "--allow-mock", env=_blind)
show("④ openpyxl을 가리면 인입·파싱 둘 다 **설치 줄**이고 Traceback 0",
     "pip install openpyxl" in (_o + _e) and "pip install openpyxl" in (_op + _ep)
     and "Traceback" not in (_e + _ep) and _rcp != 0,
     [l.strip() for l in (_op + _ep).splitlines() if "pip install" in l][:1])
_rk = _sp("-c", "import run_adapter, parser.reader",
          env={**_blind, "PYTHONPATH": f"{_tmp}{os.pathsep}{ROOT / 'kit'}"})
show("④ 가려도 **import는 선다** (지연 import 격리 — 킷·리더 모듈)", _rk[0] == 0, _rk[2][-120:])


def _wmf_xlsx(dst):
    """그림 하나가 WMF인 통합문서 — openpyxl이 읽다가 그림을 버린다(PIL 없이 조립)."""
    from openpyxl import Workbook
    wb = Workbook()
    wb.active["A1"], wb.active["A2"] = "1. 개요", "본문"
    buf = io.BytesIO()
    wb.save(buf)
    head = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, 0, 0, 100, 100, 1440, 0)
    chk = 0
    for i in range(0, 20, 2):
        chk ^= struct.unpack("<H", head[i:i + 2])[0]
    wmf = head + struct.pack("<H", chk) + struct.pack("<HHHIHIH", 1, 9, 0x0300, 12, 0, 3, 0) \
        + struct.pack("<IH", 3, 0)
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    drawing = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        f'xmlns:r="{rel}"><xdr:oneCellAnchor><xdr:from><xdr:col>2</xdr:col><xdr:colOff>0'
        '</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
        '<xdr:ext cx="95250" cy="95250"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="1" name="p"/>'
        '<xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId1"/>'
        '<a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect">'
        '<a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>'
        '</xdr:wsDr>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="{t}" Target="{g}"/></Relationships>')
    zin = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == "[Content_Types].xml":
                data = data.decode().replace(
                    "</Types>",
                    '<Default Extension="wmf" ContentType="image/x-wmf"/>'
                    '<Override PartName="/xl/drawings/drawing1.xml" ContentType='
                    '"application/vnd.openxmlformats-officedocument.drawing+xml"/></Types>').encode()
            if it.filename == "xl/worksheets/sheet1.xml":
                data = data.decode().replace(
                    "</worksheet>", f'<drawing xmlns:r="{rel}" r:id="rId1"/></worksheet>').encode()
            z.writestr(it, data)
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels",
                   rels.format(t=rel + "/drawing", g="../drawings/drawing1.xml"))
        z.writestr("xl/drawings/drawing1.xml", drawing)
        z.writestr("xl/drawings/_rels/drawing1.xml.rels",
                   rels.format(t=rel + "/image", g="../media/image1.wmf"))
        z.writestr("xl/media/image1.wmf", wmf)


_wx = _tmp / "WMF01.xlsx"
_wmf_xlsx(_wx)
_rc, _o, _e = _sp("-m", "cli.parse", "run", "parser/adapters/basic_prose_xlsx.py",
                  str(_wx), str(_tmp / "wmf.json"), "--allow-mock")
_lines = [l.strip() for l in _o.splitlines() if "읽지 못해 건너뜀" in l]
show("④ 버린 그림은 **한 줄**이고 종류가 붙는다 · 원문 경고는 stderr에 0",
     len(_lines) == 1 and "WMF 1" in _lines[0]
     and "not supported" not in _e and "Warning" not in _e and _rc == 0,
     _lines[:1] or _e[-160:])
shutil.rmtree(_tmp, ignore_errors=True)

# ────────────────────────────────────────────────────────────── ⑤
print("\n■ B86 ⑤ 등록 표본의 시트 관문 — 인입과 같은 함수 · 같은 기록")
_gen = ("-m", "cli.register", "generate", DT, "process")
_before = _untracked()
_rc, _o, _e = _sp(*_gen, str(RFQ), "--allow-mock")
_names = ["표지", "사양_기계", "사양_전장", "요구사항", "도면목록", "가격", "일정"]
show("⑤ 비대화형 등록은 **상태 거부** — 시트 전부 · 등록 명령의 `--sheets` 줄 · 기록 0",
     _rc != 0 and all(n in _o for n in _names)
     and f"python -m cli.register generate {DT}" in _o and "--sheets" in _o
     and not SH.path("RFQ01").exists() and not (_P.registry() / "review" / DT).exists(),
     [l.strip() for l in _o.splitlines() if "[등록]" in l][:1])
_rc, _o, _e = _sp(*_gen, str(RFQ), "--allow-mock", "--sheets", "2-4:prose 5:ref *:skip")
_rec = SH.read("RFQ01") or {}
_skip = {n for n, r in (_rec.get("sheets") or {}).items() if r == "skip"}
_split = [l for l in _o.splitlines() if l.strip().startswith("분할 —")]
show("⑤ `--sheets`로 준 답은 **인입과 같은 기록**이고 킷의 분할에 skip 시트가 없다",
     _rc == 0 and _rec.get("decided_by") == "flag" and _skip and _split
     and not any(s in l for s in _skip for l in _split),
     f"skip {sorted(_skip)} · 분할 {len(_split)}줄")
_view = json.loads((_P.registry() / "review" / DT / "view.json").read_text(encoding="utf-8"))
show("⑤ 검수 리허설에도 skip 시트의 조각이 **0**이다",
     not any(s in json.dumps(_view, ensure_ascii=False) for s in _skip), sorted(_skip))
_clean_dt()
_rc, _o = _pty(*_gen, str(RFQ), "--allow-mock", answers="\n\n")
_rec = SH.read("RFQ01") or {}
_rc2, _o2, _e2 = _sp("-m", "cli.register", "generate", DT2, "process", str(RFQ),
                     "--allow-mock")
show("⑤ tty에서는 **한 번 묻고** 기록한다 · 다시 치면 **기록대로**(관문 0)",
     _rc == 0 and "■ 시트 역할" in _o and _rec.get("decided_by") == "gate"
     and "기록대로 진행" in _o2 and "■ 시트 역할" not in _o2,
     [l.strip() for l in _o2.splitlines() if "기록대로" in l][:1])
_rc, _o, _e = _sp(*_gen, str(RFQ), str(TOC), "--allow-mock", "--sheets", "*:prose")
show("⑤ 표본이 여럿이면 `--sheets`는 **사용법 거부**다 (문서마다 시트 자리가 다르다)",
     _rc != 0 and "표본이 하나일 때만" in (_o + _e))
_clean_dt()
_rc, _o, _e = _sp(*_gen, str(TOC), "--allow-mock")
show("⑤ 시트 하나인 표본은 표도 관문도 없다 (지나간다)",
     "■ 시트 역할" not in _o and not SH.path("TOC01").exists(), f"rc={_rc}")
show("⑤ 등록 관문·킷이 코드 폴더에 남긴 파일 0", _untracked() == _before,
     str(sorted(_untracked() - _before)[:3]))
_clean_dt()

done()
