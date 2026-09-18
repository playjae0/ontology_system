# -*- coding: utf-8 -*-
"""G6 ⑤ 인입 화면 — 판정 예고 · 큐 집계 · 다음 줄 · `--step`(B72)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g6_common import *          # noqa: F401,F403 — 바닥은 하나다
from g6_common import _P, _ctx, _io, _env72, _run72, _sp72, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


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
_seed72 = ROOT / "layers" / "process" / "skeleton.json"
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
show("④ 단계는 7이고 문면의 자리는 진입점 옆 상수 하나다",
     len(_IG72.STEPS) == 7 and all(len(x) == 2 and x[1] for x in _IG72.STEPS),
     str([n for n, _w in _IG72.STEPS]))
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

done()
