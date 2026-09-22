# -*- coding: utf-8 -*-
"""G6 ⑤ 인입 화면 — 판정 예고 · 큐 집계 · 다음 줄 · `--step`(B72)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import (_P, _ctx, _io, _env72, _run72, _sp72, done,   # noqa: F401
                       os, shutil, store)   # `*`는 밑줄 이름을 건너뛴다


print("\n■ B72 ②③④ — 인입 화면(예고 · 큐 집계 · 다음 줄 · --step)")

from core.build import entry as _PL72                                 # noqa: E402

init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)


def _q72(kind, doc_id=None):
    return [x for x in store.read(store.QUEUE, [])
            if x["kind"] == kind and (doc_id is None or x["doc_id"] == doc_id)]


# ② 같은 필드 N행 → 큐 1건 · rows == N
_meta72 = _env72("B72META", 6)
for _r in _meta72["records"]:
    _r["meta"] = {"개정일": "2026-01-01"}          # 사내가 받은 그 산출의 모양
_run72(_meta72)
_uf72 = _q72("unknown_field", "B72META")
show("② 같은 필드 N행 → 큐 **1건**이고 rows == N (사람이 판정할 것은 하나다)",
     len(_uf72) == 1 and (_uf72[0]["payload"] or {}).get("rows") == 6
     and _uf72[0]["payload"].get("key") == "meta",
     f"{len(_uf72)}건 · rows {(_uf72[0]['payload'] or {}).get('rows') if _uf72 else '-'}")
show("② 값과 발자국을 버리지 않는다 — items[]·locators에 남는다 (G5)",
     len((_uf72[0]["payload"] or {}).get("items") or []) == 6
     and (_uf72[0]["payload"] or {}).get("locators"),
     str((_uf72[0]["payload"] or {}).get("locators"))[:60])

# ② orphan 표기 k종 → k건
_o72 = _env72("B72ORPH", 6)
for _i, _r in enumerate(_o72["records"]):
    _r["process_ref"] = "없는공정ZZ" if _i % 2 else "없는공정YY"
_run72(_o72)
_oa72 = _q72("orphan_anchor", "B72ORPH")
show("② 목록 밖 좌표 k표기 → 큐 k건 (행이 아니라 표기가 단위다)",
     len(_oa72) == 2
     and {(x["payload"] or {}).get("key") for x in _oa72} == {"없는공정ZZ", "없는공정YY"},
     f"{len(_oa72)}건 · {sorted((x['payload'] or {}).get('key') for x in _oa72)}")
show("② 행 단위 재시도 재료는 그대로 남는다 (items[]에 행마다)",
     all(len((x["payload"] or {}).get("items") or []) == 3 for x in _oa72),
     str([len((x['payload'] or {}).get('items') or []) for x in _oa72]))
show("② 큐 kind는 닫힌 20종 그대로다 (집계는 세는 단위만 바꾼다)",
     len(PF.QUEUE_KINDS) == 20 and not PF.queue_view()["alien"],
     str(PF.queue_view()["alien"]))

# ② 예고 종수 == 실제 판정 호출 수 (사전 히트 제외)
from core import matcher as _MT72                                  # noqa: E402
_calls72 = []
_m0 = _MT72.match


def _spy72(surface, *a, **k):
    _calls72.append(surface)
    return _m0(surface, *a, **k)


_plan72 = {}
_MT72.match = _spy72
try:
    _e72 = _env72("B72PLAN", 8)
    _run72(_e72, notice=lambda i: _plan72.update(i) if i.get("단계") == "판정예고" else None)
finally:
    _MT72.match = _m0
# **예고는 덜 말하면 안 된다** — 상한이 실제를 덮는다. 개체 판정은 행마다 돌고
# (스코프가 행마다 다르다) — 좌표 태깅(B69)의 표기 dedupe를 여기에 그대로 적용할
# 수 없는 이유다(D-151 ②). **재는 단위는 판정 함수 도달이다**(B74 ①): 사전 히트는
# `match`를 지나지만 exact에서 끊겨 LLM을 부르지 않고, 예고는 그 수를 같은 키로
# 세어 빼기 때문에 상한이 「호출」을 말한다.
show("② 예고의 상한이 실제 판정 호출을 덮는다 (덜 말하지 않는다)",
     _plan72 and _MT72.STATS["판정"] <= _plan72["예상_호출"],
     f"예고 ≤{_plan72.get('예상_호출')} · 실제 {_MT72.STATS['판정']} "
     f"(match 도달 {len(_calls72)} · 사전 {_MT72.STATS['사전']} "
     f"· 표기 {_plan72.get('표기_종수')}종)")
show("② 예고가 표기 종수·사전 히트를 함께 낸다 (반복되는 문서인지가 판단 재료다)",
     _plan72.get("표기_종수") and _plan72["표기_종수"] <= _plan72["값_수"])

# ② 요약 줄의 수가 그래프·큐 실물과 같다
_sum72 = {}
_g0 = len(open_graph("process").nodes)
_e72b = _env72("B72SUM", 4)
_run72(_e72b, notice=lambda i: _sum72.update(i) if i.get("단계") == "끝" else None)
show("② 요약의 노드 증분이 그래프 실물과 같다 (화면이 제 계산을 하지 않는다)",
     _sum72.get("노드") == len(open_graph("process").nodes) - _g0,
     f"요약 +{_sum72.get('노드')} · 실물 +{len(open_graph('process').nodes) - _g0}")
show("② 요약의 큐 집계가 큐 실물과 같다",
     _sum72.get("큐") == _PL72.doc_queue_summary("B72SUM"))

# ③ orphan_anchor의 다음 줄 — **보류이지 드랍이 아니다**
_next72 = PF.orphan_next_lines(_oa72[0])
show("③ 다음 줄이 세 줄이다 — alias 추가 · bootstrap · 재인입",
     "skeleton.json" in _next72 and "run.py bootstrap" in _next72
     and "ingest-file" in _next72)
show("③ 그대로 칠 수 있다 — 층·문서·doc_type이 자리표시자가 아니다",
     "layers/process/skeleton.json" in _next72 and "<층>" not in _next72
     and "--doc-type cp" in _next72,
     [l.strip() for l in _next72.splitlines() if "ingest-file" in l][:1])
show("③ `init --fresh`를 시키지 않는다 (그래프·사전을 지운다 — 가이드 §7 정정)",
     "--fresh" not in _next72)

# ③ⓑ alias 추가 + bootstrap(fresh 없이) → 노드·사전 불변 · 재인입이 보류분을 붙인다
_seed72 = _P.layers("process", "skeleton.json")   # 층 자산은 상태 루트다(B79 ①)
_orig72 = _seed72.read_text(encoding="utf-8")
_n72 = len(open_graph("process").nodes)
try:
    _sd = json.loads(_orig72)
    _sd.setdefault("ALIASES", {}).setdefault("노칭", []).append("없는공정ZZ")
    _seed72.write_text(json.dumps(_sd, ensure_ascii=False, indent=2), encoding="utf-8")
    bootstrap("process", echo=False)
    show("③ⓑ alias만 더하고 bootstrap하면 노드 수가 그대로다 (지우지 않는다)",
         len(open_graph("process").nodes) == _n72,
         f"{_n72} → {len(open_graph('process').nodes)}")
    _re72 = _env72("B72ORPH", 6)          # 같은 문서 재인입 — 보류분이 붙는다
    for _i, _r in enumerate(_re72["records"]):
        _r["process_ref"] = "없는공정ZZ" if _i % 2 else "없는공정YY"
    _run72(_re72)
    _PL72.finalize()
    _left72 = {(x["payload"] or {}).get("key") for x in _q72("orphan_anchor", "B72ORPH")}
    show("③ⓑ 재인입 뒤 이어진 표기의 보류가 내려간다 (남는 것은 아직 없는 표기뿐)",
         "없는공정ZZ" not in _left72 and "없는공정YY" in _left72, str(sorted(_left72)))
finally:
    _seed72.write_text(_orig72, encoding="utf-8")
    bootstrap("process", echo=False)

# ④ --step — 단계 7 · 비대화형 무시 · q에서 그래프 쓰기 0
from cli import ingest as _IG72                                    # noqa: E402
from cli import ingest_screen as _SCR72                            # noqa: E402
show("④ 단계는 7이고 문면의 자리는 진입점 옆 상수 하나다",
     len(_SCR72.STEPS) == 7 and all(len(x) == 2 and x[1] for x in _SCR72.STEPS),
     str([n for n, _w in _SCR72.STEPS]))
_r72 = _sp72.run([sys.executable, str(ROOT / "run.py"), "ingest-file",
                  str(ROOT / "tests/fixtures/raw/CP01.xlsx"), "--doc-type", "cp",
                  "--step", "--allow-mock"], capture_output=True, text=True,
                 cwd=str(ROOT), stdin=_sp72.DEVNULL)
show("④ 비대화형에서는 무시하고 **그 사실을 말한다** (묻고 EOF로 멈추지 않는다)",
     "--step 무시" in _r72.stdout and _r72.returncode == 0,
     [l.strip() for l in _r72.stdout.splitlines() if "--step" in l][:1])
# **q에서 멈추면 그래프 쓰기 0** — 판정 예고까지는 읽기만 한다. 대화형이어야
# `--step`이 사므로 pty로 띄운다(비대화형은 위에서 무시를 잰다).
def _step_run72(answers):
    import os, pty
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, str(ROOT / "run.py"), "ingest-file",
                                  str(ROOT / "tests/fixtures/raw/CP01.xlsx"),
                                  "--doc-type", "cp", "--step", "--allow-mock"])
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
    os.waitpid(pid, 0)
    return out.decode("utf-8", "replace")


init.init(fresh_=True)
for _lay in ("process", "quality"):
    bootstrap(_lay, echo=False)
_n72q = len(open_graph("process").nodes)
_scr72 = _step_run72("c\nc\nc\nq\n")
show("④ 판정 예고에서 q → 그래프 쓰기 0 (읽기만 한 자리에서 멈춘다)",
     len(open_graph("process").nodes) == _n72q and "[4/7]" in _scr72
     and "멈춤 —" in _scr72,
     f"노드 {_n72q} → {len(open_graph('process').nodes)}")
show("④ 멈춘 화면이 **이어서 넣는 다음 줄**을 준다 (막다른 길 0 · B61)",
     "ingest-file" in _scr72.split("멈춤 —")[-1]
     and "skeleton.json" in _scr72.split("멈춤 —")[-1])
_scr72c = _step_run72("c\nc\nc\nc\nc\nc\nc\n")
show("④ 끝까지 가면 7단계가 다 뜨고 인입이 끝난다",
     all(f"[{i}/7]" in _scr72c for i in range(1, 8)) and "인입 끝" in _scr72c,
     [l.strip() for l in _scr72c.splitlines() if "인입 끝" in l][:1])

# ── B73 ①②③ — 후보는 전량이 아니다 · retry는 조건부 · auto는 표시된다 ─────
#
# 사내 실측 열두째: 판정 호출의 **입력 토큰이 누적 2만**(출력 40 이하). 후보가
# 카테고리·층 전량이라 노드가 늘수록 매 호출이 커졌다. 명세는 처음부터 다르게
# 말한다 — 문서 4 §4.2 ②「후보 검색 — 사전 미스 시 임베딩 유사도」.

# ── B81 ①②③④ — 화면은 대장의 투영 · 로그는 파일 · 색은 특이점에만 ─────────
#
# 사내 실측(2026-09-22): 「화면에 눈에 들어오는 게 없다」 — INFO 로그가 값마다 두 줄씩
# 흐르고, 사람이 알고 싶은 것(붙었나·새로 생겼나·불확실한가)이 그 사이에 묻혔다.
print("\n■ B81 — 값 줄 · 로그 파일 · 색 · 보폭 (인입 화면)")
from cli import _screen as SC                                         # noqa: E402
from cli import ingest as IG81                                        # noqa: E402
from cli import ingest_screen as SCR81                                # noqa: E402
from core.build import ledger as LG81                                 # noqa: E402

# ③ 색은 **특이점에만** · 비-tty면 ESC 0. (여기 stdout은 파이프다 — 회귀가 그 조건이다.)
_row_new = {"canonical": "노칭::버 높이", "verdict": "new", "candidates_n": 0,
            "path": "skeleton", "llm": {"calls": 0}, "queue_kind": "auto_node"}
_row_dict = {"canonical": "노칭", "verdict": "match", "candidates_n": 1,
             "path": "dictionary", "llm": {"calls": 0}, "queue_kind": None}
_row_unc = {"canonical": "패키징::실링 온도", "verdict": "uncertain", "candidates_n": 3,
            "path": "scope+judge", "llm": {"calls": 1}, "confidence": 0.41,
            "queue_kind": "uncertain_match"}
_line_new = SCR81.value_line(_row_new)
show("③ 파이프로 나가는 화면에 ESC가 0바이트다 (색이 문면을 바꾸지 않는다)",
     "\033" not in _line_new and SC.strip_ansi(_line_new) == _line_new, repr(_line_new[:20]))
show("③ 색을 벗긴 문자열이 원본과 같다 (어서션·스캐너가 같은 것을 읽는다)",
     SC.strip_ansi(SC.paint("x", "new")) == "x"
     and SC.paint("x", "없는종류") == "x")
# ③ tty면 특이점에 색이 붙는다 — **스텁 스트림으로** 잰다(회귀는 파이프로 돈다).
class _TTY81:
    def isatty(self):
        return True


_tty81 = _TTY81()
show("③ tty에서는 특이점에만 색이 붙는다 (new 노랑 · 불확실 빨강 · 사전 무색)",
     "\033[33m" in SC.paint("x", "new", stream=_tty81)
     and "\033[31m" in SC.paint("x", "uncertain", stream=_tty81)
     and SC.paint("x", None, stream=_tty81) == "x"
     and "\033[7m" in SC.banner("x", stream=_tty81))
_keep_nc = os.environ.get("NO_COLOR")
os.environ["NO_COLOR"] = "1"
try:
    _nc81 = SC.paint("x", "new", stream=_tty81)
finally:
    os.environ.pop("NO_COLOR", None) if _keep_nc is None else os.environ.__setitem__(
        "NO_COLOR", _keep_nc)
show("③ NO_COLOR=1이면 tty에서도 ESC 0 (표준 환경변수를 존중한다)", _nc81 == "x", repr(_nc81))

show("① 값 줄이 대장 행의 값을 그대로 낸다 (새 정보 0 · 화면은 투영이다)",
     "new" in _line_new and "노칭::버 높이" in _line_new
     and "후보 0" in _line_new and "→ 큐 auto_node" in _line_new
     and "?" not in _line_new, _line_new.strip())
show("① LLM이 든 값은 후보 수와 확신을 낸다",
     all(x in SCR81.value_line(_row_unc) for x in ("uncertain", "LLM", "후보 3", "0.41")),
     SCR81.value_line(_row_unc).strip())
show("① 사전으로 끝난 값은 줄을 찍지 않는다 (판단이 갈린 자리만 — 수로만 센다)",
     not SCR81._loud(_row_dict) and SCR81._loud(_row_new) and SCR81._loud(_row_unc))
# ① 집계는 대장 행에서 — 콜백을 직접 돌려 잰다(화면과 같은 함수).
_on = SCR81.row_printer()
_buf81 = _io.StringIO()
with _ctx.redirect_stdout(_buf81):
    for _r in (_row_dict, _row_new, _row_unc):
        _on(_r)
_out81 = _buf81.getvalue()
show("① 집계가 대장 행에서 나온다 (사전 1 · NEW 1 · 불확실 1 · 큐 2)",
     SCR81.TALLY == {"값": 3, "사전": 1, "NEW": 1, "불확실": 1, "큐": 2, "orphan": 0},
     str(SCR81.TALLY))
show("① 찍힌 줄은 판단이 갈린 둘뿐이다 (사전 히트는 화면에 없다)",
     len([l for l in _out81.splitlines() if l.strip()]) == 2
     and "노칭::버 높이" in _out81 and "dictionary" not in _out81)

# ②④ 실행 화면 — 기본과 `-v`, 보폭 둘
_raw81 = _P.raw()
_raw81.mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "tests" / "fixtures" / "raw" / "CP01.xlsx", _raw81 / "CP01.xlsx")


def _run81(*argv):
    return _sp72.run([sys.executable, str(ROOT / "run.py"), *argv],
                     capture_output=True, text=True, cwd=str(ROOT),
                     env={**os.environ, "USE_MOCK": "1"}, stdin=_sp72.DEVNULL)


def _ing81(*extra):
    """**같은 바닥에서 잰다** — 클린 + 골격 뒤 인입. 두 실행을 비교하려면 시작이 같아야
    하고(사전이 차면 판정이 0회가 된다), 클린은 진입점이 만든다(§7.6-4)."""
    _run81("init", "--fresh")
    _run81("bootstrap")
    r = _run81("ingest-dir", "--allow-mock", *extra)
    return r.stdout + r.stderr


_scr81 = _ing81("--progress-every", "10")
_led81 = (LG81.read("CP01") or {}).get("rows") or []
_vals81 = [l for l in _scr81.splitlines()
           if l.strip()[:1] in ("✓", "+", "?", "✗", "·")]
show("① 값 줄 수 == 대장 행 중 판단이 갈린 수 (두 벌이 갈리지 않는다)",
     len(_vals81) == sum(1 for r in _led81 if SCR81._loud(r)),
     f"화면 {len(_vals81)} · 대장 LOUD {sum(1 for r in _led81 if SCR81._loud(r))}"
     f" / 전체 {len(_led81)}")
show("② 기본 화면에 INFO 로그 줄이 0이다 (화면은 판단이 갈린 값만)",
     not [l for l in _scr81.splitlines() if l.startswith("INFO")],
     str([l for l in _scr81.splitlines() if l.startswith("INFO")][:1]))
show("③ 실행 출력 전체에 ESC가 0바이트다 (파이프에는 색을 내지 않는다)",
     "\033" not in _scr81)
_logp81 = _P.work("logs")
_logs81 = sorted(_logp81.glob("ingest-dir_*.log")) if _logp81.is_dir() else []
_ltxt81 = _logs81[-1].read_text(encoding="utf-8") if _logs81 else ""
show("② 같은 실행의 로그 파일에 그 INFO가 남는다 (MOCK·큐 적재 — §7.8 로그 규격)",
     bool(_logs81) and "INFO" in _ltxt81
     and ("MOCK" in _ltxt81 or "큐 " in _ltxt81)
     and str(_P.home()) in str(_logs81[-1]),
     f"{_logs81[-1].name if _logs81 else '없음'} · {len(_ltxt81.splitlines())}줄")
show("② 끝 요약이 로그 자리를 말한다",
     "로그 " in _scr81 and "logs" in _scr81,
     [l.strip() for l in _scr81.splitlines() if l.strip().startswith("로그")][:1])
_scrv81 = _ing81("-v")
_valsv81 = [l for l in _scrv81.splitlines()
            if l.strip()[:1] in ("✓", "+", "?", "✗", "·")]
show("② -v면 콘솔에도 INFO가 돌아온다 (지금까지의 화면)",
     bool([l for l in _scrv81.splitlines() if l.startswith("INFO")]))
show("① -v면 값 줄이 대장 행 전부다",
     len(_valsv81) >= len(_vals81) and len(_valsv81) == len(
         (LG81.read("CP01") or {}).get("rows") or []),
     f"-v {len(_valsv81)} · 기본 {len(_vals81)} · 대장 {len(_led81)}")
# ④ 보폭 — 작게 주면 진행 줄이 늘고, 줄의 값 n이 보폭 규칙을 지킨다.
_prog = lambda s: [l for l in s.splitlines() if "[판정] 값" in l]
_scr5 = _ing81("--progress-every", "5")
_ns5 = [int(l.split("값")[1].split("/")[0].strip().replace(",", "")) for l in _prog(_scr5)]
show("④ 보폭이 작으면 진행 줄이 늘고, 값 번호가 보폭 규칙을 지킨다",
     len(_prog(_scr5)) > len(_prog(_scr81))
     and all(n == 1 or n % 5 == 0 for n in _ns5), f"보폭5 {_ns5} · 보폭10 {len(_prog(_scr81))}줄")
show("④ 진행 줄이 누적과 대장 집계를 함께 낸다",
     all(x in _prog(_scr5)[-1] for x in ("누적 토큰", "사전", "NEW", "불확실", "큐")),
     _prog(_scr5)[-1].strip())
show("④ 보폭 손잡이는 잘못된 값을 거부한다 (사용법 거부)",
     "--progress-every" in _ing81("--progress-every", "0"))
shutil.rmtree(_raw81, ignore_errors=True)

done()
