# -*- coding: utf-8 -*-
"""2A 게이트웨이 골조 — LLM 지점 8종의 mock/실호출 분기 (문서 7 §7.6-B).

**이 스위트가 잠그는 것**: USE_MOCK=0에서 설정이 비어 있을 때 9지점이 각각
**명시적으로 실패하는가**. 조용히 mock으로 떨어지는 지점이 하나라도 있으면 그것이
"모델 미연결 상태가 완료판정을 통과하는" 경로다 — 국면 1에서 실제로 일어난 일이다.

주석을 세지 않는다. **분기를 실행해서 확인한다.**
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # 테스트는 파일로 직접 실행된다(회귀 10종 관례)

_fail = 0


def show(label, ok, detail=""):
    global _fail
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _fail += 1
    return ok


# ============================================================ 게이트웨이 2파일
print("\n■ 게이트웨이 2파일 (§7.6-B-1)")

from core import embeddings, llm                                 # noqa: E402

show("core/llm.py — chat(messages, *, model, json_schema)",
     hasattr(llm, "chat")
     and {"model", "json_schema"} <= set(llm.chat.__code__.co_varnames))
show("core/embeddings.py — embed(text) -> vector", hasattr(embeddings, "embed"))
show("LLM 지점 목록이 닫힌 **9종**이다 (§7.6-B-2 — ⑨좌표 태깅 포함)",
     len(llm.POINTS) == 9 and {"answer", "coord_tag"} <= set(llm.POINTS), ", ".join(llm.POINTS))

# 설정 접근이 이 파일 하나로 수렴하는가 — 호출부가 환경변수를 직접 읽지 않는다.
_ENV = ("LLM_GATEWAY_URL", "LLM_API_KEY", "CHAT_MODEL", "EMBED_MODEL")
leaks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).glob("*.py")) if p.name != "llm.py"
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if any(e in ln for e in _ENV) and not ln.lstrip().startswith("#")
         and "|" not in ln]
show("LLM 설정 접근이 core/llm.py 하나로 수렴한다 (§7.6-B-1)", not leaks, str(leaks))

# ============================================================ mock 갈래
print("\n■ mock 갈래 — 결정성이 우선이다 (§7.5-1)")

v1, v2 = embeddings.embed("노칭 정밀도"), embeddings.embed("노칭 정밀도")
show("임베딩 mock이 결정적이다 (sha256 → 정규화 벡터)", v1 == v2 and len(v1) == 64)
show("자기 유사도 1.0 · 다른 텍스트는 낮다",
     abs(embeddings.cosine(v1, v1) - 1.0) < 1e-9
     and embeddings.cosine(v1, embeddings.embed("버 발생")) < 0.5)

from parser import tagger                                        # noqa: E402

m = tagger.complete_images([{"source_locator": "S", "image_ref": "i1"}])[0]
show("이미지 요약 mock이 데이터로 표시된다 (§7.6-B-4)",
     m["meta"].get("image_summary") is True
     and m["meta"].get("image_summary_source") == "mock", str(m["meta"]))
live = tagger.complete_images([{"source_locator": "S", "image_ref": "i1"}],
                              lambda r: f"요약({r})")[0]
show("실호출 갈래는 source=live로 갈린다 — 두 갈래가 같은 반환 계약",
     live["meta"]["image_summary_source"] == "live"
     and set(m["meta"]) == set(live["meta"]))

# ============================================================ USE_MOCK=0
print("\n■ USE_MOCK=0 + 설정 미설정 → 9지점 각각 명시적 실패 (§7.6-B-4 · 완료판정 5)")

# **탐침은 `tests/points_probe.py` 하나다**(B48) — `doctor.py`가 같은 파일을 실행한다.
# 두 벌로 두면 한쪽만 고쳐지는 날이 오고, 그날 화면은 초록인데 배선은 없다.
sys.path.insert(0, str(ROOT / "tests"))
from points_probe import run as _probe                           # noqa: E402

res, _r = _probe()
show(f"{len(llm.POINTS)}지점 전부가 실행됐다 (탐침이 완주)",
     len(res) == len(llm.POINTS),
     _r.stderr.strip().splitlines()[-1:] and _r.stderr.strip().splitlines()[-1] or "")
for key, label in llm.POINTS.items():
    got = res.get(key, "(미실행)")
    # **재는 것은 「도달 가능성」이다**(§7.6-B-2) — 조용한 통과가 아닌 것만으로는
    # 모자라다: 파서 3지점은 대체 갈래가 정상으로 도는 것이 「통과」이므로, 실제
    # 호출자가 타는 길(팩토리)이 **미설정 실패에 닿는가**를 잰다.
    show(f"{label} → 실 호출 경로가 NotConfigured에 닿는다", got == "NotConfigured", got)

# ============================================================ 지점 ⑦ 변환
print("\n■ ⑦구조 지도 — 변환은 코어가 한다 (파서는 LLM 스키마를 모른다 · B48 ②)")
_lines = [(2, "1. 개요"), (3, "본문 한 줄"), (4, "1.1 절"), (5, "또 본문")]
_fake = {"headings": [{"row": 2, "level": 1, "title": "1. 개요"},
                      {"row": 4, "level": 2, "title": "1.1 절"},
                      {"row": 99, "level": 1, "title": "입력에 없는 행"},
                      {"row": 3, "level": 0, "title": "급이 0"}],
         "note": "위계가 뒤섞여 급을 매길 수 없음"}
_ochat = llm.chat
llm.chat = lambda *a, **k: _fake            # 게이트웨이 없이 변환만 잰다
try:
    _sm = llm.map_structure("D1", _lines)
finally:
    llm.chat = _ochat
show("headings → 파서 지도 형식(rows) — 목록에 있는 행만 heading=true",
     [(r["row"], r["heading"], r["level"]) for r in _sm["rows"]]
     == [(2, True, 1), (3, False, 0), (4, True, 2), (5, False, 0)],
     str(_sm["rows"]))
show("지어낸 행과 급 0을 버리고 센다 — meta.dropped (지시문 규약 4)",
     _sm["meta"]["dropped"] == 2, str(_sm["meta"]))
show("note를 meta로 실어 하류가 「판정 불가」로 올릴 수 있다 (문서 6 §6.2)",
     _sm["meta"]["note"] == "위계가 뒤섞여 급을 매길 수 없음")
show("재현 조건 — source=live · 지시문 판본이 지도에 남는다 (B36 동형)",
     _sm["source"] == "live" and _sm["prompt_version"] == llm.prompt_version("struct_map"),
     f"{_sm['source']} · {_sm.get('prompt_version')}")
show("입력 본문은 «행번호<TAB>앞N자» 목록이다",
     llm._map_lines([(7, "가나다라마바사")], 3) == "7\t가나다")
show("크기 예산은 감축 사다리를 탄다 — 행을 빼지 않고 앞자리를 줄인다 (B41)",
     llm.MAP_LINE_WIDTHS[0] == 80 and list(llm.MAP_LINE_WIDTHS) == sorted(
         llm.MAP_LINE_WIDTHS, reverse=True))

# ============================================================ 분기 실물
print("\n■ 분기가 실물로 서 있는가 — 주석을 세지 않는다 (§7.6-B-2)")

# core 6지점 — **종전 방식 유지**(인라인 분기. 팩토리로 옮기는 것은 다음 회차)
WIRED = {"extract": ("core/extract.py", "_candidates_for"),
         "judge": ("core/matcher.py", "_judge_live"),
         "embed": ("core/embeddings.py", "llm.require"),
         "generate": ("cli/register.py", "_draft_live"),
         "link": ("core/query.py", "_link_llm"),
         "answer": ("cli/query.py", "def generate")}
for key, (where, needle) in WIRED.items():
    src = (ROOT / where).read_text(encoding="utf-8")
    show(f"{llm.POINTS[key]} — 실호출 갈래가 {where}에 있다", needle in src)

# 파서 3지점 — **문자열이 아니라 통로를 잰다**(B48). 파서에는 판독이 없으므로
# 「분기가 있다」로는 셀 것이 없고, 팩토리 → 주입 조립 → 파서 인자가 이어져야 배선이다.
import inspect                                                   # noqa: E402
from cli.parse import injections as _inj                         # noqa: E402
from parser import pipeline as _PL                               # noqa: E402

_pv = set(inspect.signature(_PL.parse).parameters)
_asm = _inj()
for key, factory, kw in (("image_summary", "image_summarizer", "summarize"),
                         ("struct_map", "struct_mapper", "map_structure"),
                         ("coord_tag", "coord_picker", "pick_coord")):
    show(f"{llm.POINTS[key]} — 팩토리→주입 조립→파서 인자가 이어진다 "
         f"(llm.{factory}() → {kw}=)",
         callable(getattr(llm, factory, None)) and kw in _asm and kw in _pv)

# ── 변이 시험 — **배선을 하나 빼면 붉는가**(§7.6-B-2 · B48 ④-2)
# 잡는 자리는 주입 조립 지점이다: 파서는 모드를 모르므로 「실호출 모드인데 함수가
# 없다」를 알 수 있는 것은 만드는 쪽뿐이다. 이 어서션이 곧 「진입점이 한 번 정해
# 전부 내려보낸다」의 기계 판정이다.
_orig = (llm.use_mock, llm.image_summarizer, llm.coord_picker, llm.struct_mapper)
llm.use_mock = lambda: False
llm.image_summarizer = lambda: (lambda ref: "요약")
llm.coord_picker = lambda: (lambda s, c: None)
llm.struct_mapper = lambda: None                # ← ⑦ 배선을 뺀다
try:
    _inj()
    _mut = "통과 — 붉지 않았다"
except llm.NotConfigured as e:
    _mut = f"NotConfigured — {str(e)[:60]}"
llm.struct_mapper = lambda: (lambda d, l: {"rows": []})   # ← 되돌린다
_back = "통과" if _inj().get("map_structure") else "여전히 None"
llm.use_mock, llm.image_summarizer, llm.coord_picker, llm.struct_mapper = _orig
show("변이 — ⑦ 주입을 빼면 실호출 모드에서 붉는다 (조용한 휴리스틱 폴백 0)",
     _mut.startswith("NotConfigured"), _mut)
show("변이 — 되돌리면 초록이다 (시험 자체가 늘 붉는 것이 아니다)", _back == "통과", _back)

hooks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).glob("*.py"))
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if "HOOK:" in ln]
show("주석 훅 표시가 0건이다 — 주석은 실행되지 않는다", not hooks, str(hooks))

print("\n" + "=" * 62)
print(f"전체 결과: {'PASS — 게이트웨이 골조 성립' if not _fail else f'FAIL {_fail}건'}")
sys.exit(1 if _fail else 0)
