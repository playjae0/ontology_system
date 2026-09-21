# -*- coding: utf-8 -*-
"""자리와 경계 — 상태의 자리 소유자 · 모듈 머리말 · 코드 지도 · 층 자산 (칸 0.3).

**무엇을 재나**: B78이 세운 자리 규율(①상태의 자리를 아는 모듈은 하나 ②자리가
가른다 — 모드가 아니라 ③모듈은 제 칸을 한 줄로 말한다 ④코드 지도는 생성물이다)과
B79가 더한 것(①층 자산은 상태 루트에 산다 ③ⓑ미정의 이름 0 ④루트의 출처를 화면이
말한다 · 레포 정본 자산이 레포 판인가).

`test_g1_g2.py`에서 갈라져 나왔다(B79 — 834행). 저장·주소 규격과 자리 배치는
**바뀌는 이유가 다르다.**

사용: python tests/test_places.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g1_common import *          # noqa: F401,F403 — 바닥은 하나다
from g1_common import (_P, _ast78, _re, _shutil2, done, reset,  # noqa: F401
                       show, ROOT, init, store)

print("\n■ 자리 — 상태의 자리를 아는 모듈은 하나다 (B78 1a·1b · B79 ①)")
reset()                          # 클린 + 골격 — 자리 판정의 바닥도 클린이다

# ── B78 1a — **상태의 자리를 아는 모듈은 하나다** ────────────────────────
# 코드를 새로 가져올 때 `review/`·`data/`·`parsed/`를 전부 같이 옮겨야 했던 이유가
# 이것이다: 자리를 아는 코드가 26곳(운영)에 복사돼 있었다. 자리를 한 모듈이 알면
# **코드 교체와 상태 이사가 갈린다**(B78 1a · 칸 0.4).
#
# 경계 예외 셋은 **이름으로** 허용한다 — 늘어나면 붉는다:
#   · `parser/`  2곳 — 파서는 외부 전달물이라 core를 import하지 않는다(문서 6 §6.7)
#   · `kit/`     1곳 — 킷도 같다(관문 G54가 `core.llm` 미적재를 상시로 잰다).
#                 2c에서 표가 갈리며 그 한 곳이 `kit/gate_tables.py`(공용 블록의 자리)다.
import re as _re                                  # noqa: E402
_STATE = "|".join(("data", "review", "parsed", "extract", "export",
                   "golden", "adapters", "schemas"))
_SPAT = _re.compile(r'(ROOT|parent\.parent)\s*/\s*"(?:' + _STATE + r')"')
_ALLOW = {"core/paths.py", "parser/struct_map.py", "parser/tagger.py",
          "kit/gate_tables.py"}
_state_hits = [f"{p.relative_to(ROOT)}:{i}"
               for d in ("core", "cli", "parser", "kit")
               for p in sorted((ROOT / d).rglob("*.py"))
               if "__pycache__" not in p.parts
               and str(p.relative_to(ROOT)) not in _ALLOW
               for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if _SPAT.search(line) and not line.lstrip().startswith("#")]
for _f in ("run.py", "doctor.py"):
    _state_hits += [f"{_f}:{i}" for i, line in enumerate(
        (ROOT / _f).read_text(encoding="utf-8").splitlines(), 1)
        if _SPAT.search(line) and not line.lstrip().startswith("#")]
show("상태 경로를 조립하는 코드가 core/paths.py 밖에 없다 (경계 예외 3곳 제외)",
     not _state_hits, str(_state_hits))

# **폴더를 만드는 자리도 하나다**(B77 ④의 연장) — 자리를 옮길 때 한 곳이 남으면
# 그것이 옛 자리를 되살린다. doctor의 시험 보조 폴더는 상태가 아니다.
_MPAT = _re.compile(r"\.mkdir\(")
_MKALLOW = {"core/paths.py", "parser/struct_map.py"}
_mk_hits = [f"{p.relative_to(ROOT)}:{i}"
            for d in ("core", "cli", "parser", "kit")
            for p in sorted((ROOT / d).rglob("*.py"))
            if "__pycache__" not in p.parts
            and str(p.relative_to(ROOT)) not in _MKALLOW
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _MPAT.search(line) and not line.lstrip().startswith("#")]
show("폴더를 만드는 코드가 core/paths.py 밖에 없다 (파서 경계 1곳 제외)",
     not _mk_hits, str(_mk_hits))

# ── B78 1b — **자리가 가른다**(모드가 아니라) ────────────────────────────
# ①mock 자산은 픽스처 폴더에만 ②등록은 `registry/`에만 ③mock 실행은 mock 루트에만.
# 구판은 같은 폴더에 두고 모드로 갈랐고, 그래서 「mock이 이름만 다르게 숨어 있다」였다.
_repo_schema_dt = sorted(
    p.name for p in (ROOT / "schemas").glob("*.json")
    if "doc_type" in json.loads(p.read_text(encoding="utf-8")))
show("레포 schemas/에 doc_type 키를 가진 파일 0 (공용 블록만 남는다)",
     not _repo_schema_dt, str(_repo_schema_dt))

show("등록부는 등록 단에 있다 — 진실과 함께 지워지지 않는다",
     store.path(store.DOC_TYPES).is_relative_to(_P.registry())
     and not store.path(store.DOC_TYPES).is_relative_to(_P.data()))

_keep_owners = [m for m in (init, store)
                if any("KEEP_IN" + "_DATA" == n for n in dir(m))]
show("이름으로 지켜 내는 예외가 코드에 없다 — 자리가 갈리면 규칙이 준다",
     not _keep_owners, str(_keep_owners))

# **파서는 core를 import하지 않는다**(문서 6 §6.7) — 그래서 자리를 **주입으로** 받는다.
# 값이 아니라 함수를 받아야 상태 루트가 갈릴 때 파서도 같이 움직인다.
from parser import struct_map as _SM2, tagger as _TG2            # noqa: E402
_psrc = "".join((ROOT / "parser" / f).read_text(encoding="utf-8")
                for f in ("struct_map.py", "tagger.py"))
show("파서의 상태 자리 둘이 주입으로 상태 루트를 따른다 (파서는 core를 모른다)",
     _SM2.keep_dir().is_relative_to(_P.work())
     and _TG2.snapshot_path() == store.path(store.SKELETON_LIST)
     and "import core" not in _psrc and "from core" not in _psrc,
     f"{_SM2.keep_dir()} · {_TG2.snapshot_path()}")

# **변이 — 운영 루트에 감시 파일을 두고 mock으로 돌린다.** 한 바이트도 닿지 않아야 한다.
_watch = Path(tempfile.mkdtemp(prefix="b78watch_"))
(_watch / "감시.txt").write_text("touched?", encoding="utf-8")
_before = sorted(str(p.relative_to(_watch)) for p in _watch.rglob("*"))
_mockrun = subprocess.run(
    [sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
    capture_output=True, text=True, cwd=str(ROOT),
    env=dict(os.environ, USE_MOCK="1", ONTO_HOME=str(_watch)),
    stdin=subprocess.DEVNULL)
_after = sorted(str(p.relative_to(_watch)) for p in _watch.rglob("*"))
show("USE_MOCK=1 실행이 ONTO_HOME(운영 루트)에 쓰지 않는다 — 자리로 끊는다",
     _mockrun.returncode == 0 and _before == _after and _P.is_mock_home(),
     f"{_after} · rc={_mockrun.returncode}")
_shutil2.rmtree(_watch, ignore_errors=True)

# ── B78 2b — **모듈은 자기 자리를 한 줄로 말한다** ────────────────────────
# 단계 3의 코드 지도 생성기가 이 첫 줄을 읽는다. 없으면 그 자리는 지도에서 이름만
# 남고, 「어느 칸의 코드인가」를 사람이 파일을 열어 추측하게 된다.
import ast as _ast78                                                # noqa: E402
_mods78 = [p for d in ("core", "cli", "parser", "kit")
           for p in sorted((ROOT / d).rglob("*.py")) if "__pycache__" not in p.parts]
_mods78 += [ROOT / "run.py", ROOT / "doctor.py", ROOT / "router.py"]
_nodoc78 = [str(p.relative_to(ROOT)) for p in _mods78
            if not _ast78.get_docstring(_ast78.parse(p.read_text(encoding="utf-8")))]
show("운영 모듈 중 머리말 없는 파일 0 (자리를 한 줄로 말한다)", not _nodoc78, str(_nodoc78))
_nokan78 = [str(p.relative_to(ROOT)) for p in _mods78
            if not (_ast78.get_docstring(_ast78.parse(p.read_text(encoding="utf-8")))
                    or "").startswith("칸 ")]
show("머리말 첫 줄이 칸 번호로 시작한다 (칸 대장과 코드가 같은 번호를 쓴다)",
     not _nokan78, str(_nokan78[:5]))

# **cli/에 sys.path 조작이 없는가** (문서 7 §7.1 패키지화).
# 조작으로 붙이면 CLI가 실행 위치에 의존해 "subprocess로 호출 가능한 CLI+파일"이
# 호출부의 작업 디렉터리에 따라 깨진다. 실행 규약은 `python -m cli.{진입점}`이다.
PATH_HACK = "sys" + r"\.path\.insert"
import re as _re
_pat = _re.compile(PATH_HACK)
cli_hits = [f"{p.relative_to(ROOT)}:{i}"
            for p in sorted((ROOT / "cli").glob("*.py"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _pat.search(line) and not line.lstrip().startswith("#")]
show("cli/ 8종에 sys.path 조작 0지점 — 실행은 python -m cli.{진입점}",
     not cli_hits, str(cli_hits))

# **원자적 쓰기가 배선돼 있는가** (문서 7 §7.1 저장 계층).
# 직접 덮어쓰면 build가 쓰기 도중 죽었을 때 진실이 반쯤 쓰인 채 남는다 —
# data/는 백업 대상이지 재생성 대상이 아니라 복구가 불가능하다.
_src = (ROOT / "core" / "state" / "store.py").read_text(encoding="utf-8")
_gsrc = (ROOT / "core" / "graph.py").read_text(encoding="utf-8")
show("저장 쓰기가 tmp+os.replace·flock 경유다 (직접 덮어쓰기 0)",
     "os.replace" in _src and "flock" in _src
     and "atomic_write_bytes" in _gsrc
     and "write_bytes(_dumps(" not in _gsrc)

# **빈 상태의 형태가 §7.2 말미와 같은가** — 클린의 정의가 하나여야
# 회귀 규약(§7.5-7)과 완료판정 4번이 같은 바닥 위에 선다.
from core.state import init as _init                                # noqa: E402
_init.init(fresh_=True)
_want = {store.CHUNKS: {"chunks": {}, "describes": []},
         store.DICTIONARY: {}, store.QUEUE: []}
_got = {n: store.read(n, "없음") for n in _want}
show("run.py init --fresh 의 빈 상태 형태가 명세와 일치 (§7.2)",
     _got == _want, str(_got))

# **클린이 승인 기록을 지우지 않는가** (§7.8 — 사람 판단 기록은 재생성되지 않는다).
# `review/{doc_type}/approval.json`이 승인의 물리 정본이라, 클린이 그것을 지우면
# 사내에서 `init --fresh` 한 번에 승인 이력이 사라진다(실증된 결함).
from core.state import init as _init2                                 # noqa: E402
_probe = _P.review() / "_clean_probe"
_probe.mkdir(parents=True, exist_ok=True)
(_probe / "approval.json").write_text('{"approved_by": "시험자"}', encoding="utf-8")
_init2.init(fresh_=True)
_kept = (_probe / "approval.json").exists()
show("run.py init --fresh 가 review/의 승인 기록을 지우지 않는다 (§7.8)",
     _kept and "registry" not in _init2.WIPE_TIERS, str(_init2.WIPE_TIERS))
import shutil as _sh
_sh.rmtree(_probe, ignore_errors=True)

# **core 접근 경계 3종이 관문으로 서 있는가** (문서 7 §7.1).
# 자산에 파일과 의미론만 있고 관문이 없으면 호출부마다 제 규칙으로 붙는다 —
# 실제로 사전 접근이 5곳으로 흩어져 있었고 provenance 필수는 한 곳만 지켰다.
_DICT_KEY = "store" + r"\.(?:read|write)\(store\.DICTIONARY"
import re as _re2
_dp = _re2.compile(_DICT_KEY)
_bypass = [f"{p.relative_to(ROOT)}:{i}"
           for p in sorted(list((ROOT / "core").rglob("*.py")) + list((ROOT / "cli").glob("*.py")))
           if p.name != "dictionary.py"
           for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
           if _dp.search(line) and not line.lstrip().startswith("#")]
show("core/dictionary.py 밖에서 사전을 직접 여는 코드 0지점", not _bypass, str(_bypass))

from core.dictionary import Dictionary                          # noqa: E402
_d = Dictionary()
try:
    _d.register("표기", "N1", provenance=None)
    _prov_forced = False
except ValueError:
    _prov_forced = True
show("사전 등재의 provenance 필수가 관문에서 강제된다 (문서 1 G2)", _prov_forced)

from core import matcher as _M                                  # noqa: E402
show("matcher가 match(surface, candidates, category) 계약을 갖는다 (§7.1)",
     all(hasattr(_M, f) for f in ("match", "candidates", "resolve"))
     and list(_M.match.__code__.co_varnames[:3]) == ["surface", "candidates", "category"])
_v = _M.match("가", [{"id": "N9", "canonical": "가", "aliases": [],
                      "category": "Unit", "exact": False}], "Unit")
# **계약 세 키는 그대로이고, 생성 경로 한 키가 더 붙는다**(B74 ② — 명세가 허용한
# 유일한 추가다). 「정확히 3키」로 잠그면 대장이 판정의 사실을 옮길 통로가 없어
# 호출부가 경로를 **다시 계산하게** 된다 — 그 복제가 예고와 판정을 갈라 놓았다.
show("판정 반환이 {type, matched_id, confidence} 세 키를 지킨다 + path (문서 4 §4.3-6)",
     set(_v) == {"type", "matched_id", "confidence", "path"}
     and _v["matched_id"] == "N9" and _v["path"] in _M.PATHS, str(_v))
show("카테고리 불일치는 후보에서 제외된다 — 판정이 재확인한다 (규약 3)",
     _M.match("가", [{"id": "N9", "canonical": "가", "aliases": [],
                      "category": "Property", "exact": False}], "Unit")["type"] == _M.NEW)

import core.state.skeleton as _SK                                     # noqa: E402
show("골격 심기가 core/state/skeleton.py에 산다 (§7.1 — 파생이 loader에 섞이지 않는다)",
     all(hasattr(_SK, f) for f in ("plant", "_plant_tree", "_link_seed_mirrors"))
     and "_TreeParser" in dir(_SK))
_bsrc = (ROOT / "core" / "state" / "bootstrap.py").read_text(encoding="utf-8")
show("bootstrap에 트리 파싱·모양 분기가 남아 있지 않다",
     "_TreeParser" not in _bsrc and "TYPE_FLAT" not in _bsrc)

from core.state import ops as _OPS                                    # noqa: E402
show("I2 병합 후보가 판정 경유로 제안된다 (문서 4 §4.3 재사용 3지점 중 하나)",
     hasattr(_OPS, "merge_targets"))


# ── B79 ① — **층 자산은 상태 루트에 산다** ─────────────────────────────
# 사내 실측(2026-09-21): 층 자산은 사내가 공정 체계로 고쳐 승인 1회 하는 것인데
# 코드 폴더에 살았다 — 코드를 갈아 끼우면 사내 골격이 레포 seed 판으로 되돌아간다.
# **AST로 잰다**(문면을 세지 않는다): 경로 조립 = `… / "layers"` 또는 통째로
# 경로인 문자열(`layers/process/config.json`). 화면 문면·docstring은 경로가 아니다.
def _lay_joins79(path):
    _tree = _ast78.parse(path.read_text(encoding="utf-8"))
    _docs = {id(n.value) for n in _ast78.walk(_tree)
             if isinstance(n, _ast78.Expr) and isinstance(n.value, _ast78.Constant)
             and isinstance(n.value.value, str)}
    _out = []
    for _n in _ast78.walk(_tree):
        if isinstance(_n, _ast78.BinOp) and isinstance(_n.op, _ast78.Div) and any(
                isinstance(s, _ast78.Constant) and s.value == "layers"
                for s in (_n.left, _n.right)):
            _out.append(_n.lineno)
        if (isinstance(_n, _ast78.Constant) and isinstance(_n.value, str)
                and id(_n) not in _docs
                # 낱말 `"layers"` 하나는 화면 데이터의 **키**다 — 경로가 아니다.
                and _re.fullmatch(r'layers/[\w<>{}.*-]+(/[\w<>{}.*-]+)*', _n.value)):
            _out.append(_n.lineno)
    return _out

_lay_hits = sorted({p.relative_to(ROOT).as_posix()
                    for d in ("core", "cli", "parser", "kit")
                    for p in sorted((ROOT / d).rglob("*.py"))
                    if "__pycache__" not in p.parts and _lay_joins79(p)})
# 셋만 조립한다 — 자리 소유자 · 이관(옛 폴더와 새 루트 **양쪽**을 다룬다) ·
# 킷(단독 실행 기준은 레포다 — 킷은 `core`를 import하지 않는다).
show("층 경로를 조립하는 파일이 셋뿐이다 (자리 소유자 · 이관 · 킷 단독 기준)",
     _lay_hits == ["core/paths.py", "core/state/migrate.py", "kit/gate_tables.py"],
     str(_lay_hits))
from router import discover as _disc79                            # noqa: E402
show("층 발견은 상태 루트를 본다 (레포 고정 상수가 아니다)",
     _P.layers().is_relative_to(_P.home()) and _disc79()
     and all((_P.layers(l) / "config.json").is_file() for l in _disc79()),
     f"{_P.layers()} · {_disc79()}")
# **자리가 가른다 — mock은 seed를 심고 운영은 손대지 않는다.**
# 감시 파일을 운영 루트의 층에 두고 mock으로 `init --fresh`를 돌린다.
_wl79 = Path(tempfile.mkdtemp(prefix="b79watch_"))
(_wl79 / "layers" / "process").mkdir(parents=True)
(_wl79 / "layers" / "process" / "config.json").write_text('{"layer": "process"}',
                                                          encoding="utf-8")
(_wl79 / "layers" / "감시.txt").write_text("touched?", encoding="utf-8")
_before79 = sorted((p.relative_to(_wl79).as_posix(), p.read_bytes() if p.is_file() else b"")
                   for p in _wl79.rglob("*"))
_fresh79 = subprocess.run(
    [sys.executable, str(ROOT / "run.py"), "init", "--fresh"],
    capture_output=True, text=True, cwd=str(ROOT),
    env={**os.environ, "USE_MOCK": "1", "ONTO_HOME": str(_wl79)})
_after79 = sorted((p.relative_to(_wl79).as_posix(), p.read_bytes() if p.is_file() else b"")
                  for p in _wl79.rglob("*"))
show("init --fresh는 mock 루트에만 seed를 심는다 (운영 층 자산에 한 바이트도 닿지 않는다)",
     _fresh79.returncode == 0 and _before79 == _after79
     and (_P.layers("process") / "config.json").is_file(),
     f"rc={_fresh79.returncode} · 감시 {len(_after79)}개")
_shutil2.rmtree(_wl79, ignore_errors=True)

# ── B79 ③ⓑ — **미정의 이름 0** ────────────────────────────────────────
# 사내 실측(2026-09-21): 분할이 `import json`을 두고 가 `ingest-file`이 파싱에서
# 죽었는데 회귀 1,362는 초록이었다 — 그 줄이 `USE_MOCK=1`에서 안 돌기 때문이다.
# **실행되지 않는 줄은 읽어서** 잰다(표준 라이브러리 AST · 외부 의존 0).
sys.path.insert(0, str(ROOT / "tests"))
import names_scan as _NS79                                          # noqa: E402
_bad79 = _NS79.scan()
show("운영 모듈에 미정의 이름 0 (실행되지 않는 줄도 이름이 묶여 있다)",
     not _bad79, " · ".join(f"{f}:{ln} {n}" for f, ln, n in _bad79[:3]))
# **변이 — 검사기가 실제로 붉어지는가.** 같은 파일에서 import 한 줄을 빼고 잰다.
with tempfile.TemporaryDirectory() as _td79:
    _dst79 = Path(_td79) / "core" / "llm"
    _dst79.mkdir(parents=True)
    _src79 = (ROOT / "core" / "llm" / "points.py").read_text(encoding="utf-8")
    (_dst79 / "points.py").write_text(_src79.replace("\nimport json\n", "\n", 1),
                                      encoding="utf-8")
    _mut79 = _NS79.scan(_td79)
show("import 한 줄을 빼면 그 줄을 짚어 붉어진다 (검사기가 실제로 잰다)",
     any(n == "json" and f.endswith("points.py") for f, _l, n in _mut79),
     str(_mut79[:3]))

# ── B79 ④ — **루트의 출처를 화면이 말한다 · 자산은 레포 판인가** ────────
# 사내 실측: 새 터미널에서 `export ONTO_HOME=…`이 빠져 **다른 루트**를 보며
# 「가져온 게 사라졌다」로 읽었다. 거부가 아니라 표시다 — 기본 루트도 정당하다.
def _mode79(env):
    return subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.');"
         "from core.llm import gateway; print(gateway.mode_line())"],
        capture_output=True, text=True, cwd=str(ROOT),
        env={k: v for k, v in env.items() if v is not None}).stdout
_env_no = {**os.environ, "USE_MOCK": "0"}
_env_no.pop("ONTO_HOME", None)
_line_no = _mode79(_env_no)
_line_yes = _mode79({**_env_no, "ONTO_HOME": str(Path(tempfile.gettempdir()) / "b79home")})
show("ONTO_HOME 미설정은 모드 줄이 말한다 (설정하면 그 조각이 없다)",
     "미설정" in _line_no and "미설정" not in _line_yes,
     _line_no.strip().split("·")[-1].strip())
show("mock 루트에서는 그 조각이 없다 (mock은 ONTO_HOME을 무시한다 — 물을 것이 없다)",
     "미설정" not in _mode79({**os.environ, "USE_MOCK": "1"}))

import asset_hashes as _AH79                                        # noqa: E402
_chg79, _add79, _gone79 = _AH79.diff()
show("레포 정본 자산의 해시 기록이 실물과 같다 (prompts·kit·blocks·layers seed)",
     not (_chg79 or _add79 or _gone79),
     f"다름 {_chg79} · 기록 없음 {_add79} · 사라짐 {_gone79}")
# **변이 — 지시문 한 줄을 고치면 잡히는가.** 되돌린다(자산은 고치지 않는다).
_pr79 = ROOT / "prompts" / "2.8_coord_tag.md"
_keep79 = _pr79.read_bytes()
try:
    _pr79.write_bytes(_keep79 + "\n<!-- 변이 -->\n".encode("utf-8"))
    _chg2 = _AH79.diff()[0]
finally:
    _pr79.write_bytes(_keep79)
show("지시문을 고치면 대조가 그 파일을 짚는다 (사내에서 고치지 않는 것을 기계가 잰다)",
     _chg2 == ["prompts/2.8_coord_tag.md"] and not _AH79.diff()[0], str(_chg2))

# ── B78 3 — **코드 지도는 생성물이다** ────────────────────────────────
# 손으로 쓴 구조 설명은 코드가 움직이면 낡고, 낡은 지도는 사람을 없는 자리로 보낸다.
# 그래서 다시 만들어 레포의 것과 **대조한다** — 다르면 지도가 낡았다는 뜻이고,
# 고치는 방법은 문장을 손보는 것이 아니라 생성기를 다시 돌리는 것이다.
_map78 = ROOT / "docs" / "구조도" / "10_코드_지도.md"
with tempfile.TemporaryDirectory() as _td78:
    _gen78 = subprocess.run(
        [sys.executable, str(ROOT / "docs" / "회귀스위트" / "추출_구조.py")],
        capture_output=True, text=True, cwd=str(ROOT),
        env={**os.environ, "STRUCT_DIR": _td78, "REFINED_DIR": "docs/spec"})
    _fresh78 = Path(_td78) / "10_코드_지도.md"
    _same78 = (_fresh78.exists() and _map78.exists()
               and _fresh78.read_text(encoding="utf-8") == _map78.read_text(encoding="utf-8"))
    # 자리 설명은 **임시 폴더가 살아 있는 동안** 잰다(밖에서 재면 늘 「없음」이 뜬다).
    _det78 = f"rc={_gen78.returncode} · 생성 {_fresh78.exists()} · 줄 {len(_fresh78.read_text(encoding='utf-8').splitlines()) if _fresh78.exists() else 0}"
show("코드 지도를 다시 만들면 레포의 것과 같다 (지도가 코드보다 낡지 않는다)",
     _same78, _det78)


done("자리·경계 충족")
