# -*- coding: utf-8 -*-
"""2A 게이트웨이 골조 — LLM 지점 8종의 mock/실호출 분기 (문서 7 §7.6-B).

**이 스위트가 잠그는 것**: USE_MOCK=0에서 설정이 비어 있을 때 9지점이 각각
**명시적으로 실패하는가**. 조용히 mock으로 떨어지는 지점이 하나라도 있으면 그것이
"모델 미연결 상태가 완료판정을 통과하는" 경로다 — 국면 1에서 실제로 일어난 일이다.

주석을 세지 않는다. **분기를 실행해서 확인한다.**
"""
from __future__ import annotations

import os
import shutil as _shutil
import subprocess
import sys
import tempfile
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

from core.llm import embeddings, gateway as llm, points, struct_map_pass                                 # noqa: E402

show("core/llm/gateway.py — chat(messages, *, model, json_schema)",
     hasattr(llm, "chat")
     and {"model", "json_schema"} <= set(llm.chat.__code__.co_varnames))
show("core/llm/embeddings.py — embed(text) -> vector", hasattr(embeddings, "embed"))
show("LLM 지점 목록이 닫힌 **9종**이다 (§7.6-B-2 — ⑨좌표 태깅 포함)",
     len(llm.POINTS) == 9 and {"answer", "coord_tag"} <= set(llm.POINTS), ", ".join(llm.POINTS))

# 설정 접근이 이 파일 하나로 수렴하는가 — 호출부가 환경변수를 직접 읽지 않는다.
_ENV = ("LLM_GATEWAY_URL", "LLM_API_KEY", "CHAT_MODEL", "EMBED_MODEL")
leaks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).rglob("*.py")) if "core/llm/" not in p.as_posix()
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if any(e in ln for e in _ENV) and not ln.lstrip().startswith("#")
         and "|" not in ln]
show("LLM 설정 접근이 core/llm/ 하나로 수렴한다 (§7.6-B-1)", not leaks, str(leaks))

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
# **주입 서명은 계약이다** — B53에서 `summarize(ref, image=, mime=, context=, page=)`로
# 넓어졌다(구판은 참조 문자열 1인자라 모델이 그림을 못 봤다 — 개정대장 §AJ).
live = tagger.complete_images(
    [{"source_locator": "S", "image_ref": "i1", "context": "맥락"}],
    lambda r, *, image=None, mime=None, context="", page=None: f"요약({r}·{context})",
    images={"i1": (b"\x89PNG", "image/png")})[0]
show("실호출 갈래는 source=live로 갈린다 — 두 갈래가 같은 반환 계약",
     live["meta"]["image_summary_source"] == "live"
     and set(m["meta"]) <= set(live["meta"]))
show("주입 서명이 바이트·맥락을 받는다 (B53 — 참조 문자열만 보내지 않는다)",
     live["text"] == "요약(i1·맥락)" and live["meta"]["image_bytes_len"] == 4)

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

# ============================================================ 요청 조립
# **요청 모양에 손잡이가 있고, 조립은 한 자리다**(B80 ①). 사내 실측(2026-09-22):
# 새 모델이 `temperature`를 받지 않아 막혔는데 코드는 그것을 **모든 요청에 고정으로**
# 싣고 설정으로 끌 자리가 없었다. 게다가 `llm-check`의 탐침이 payload를 따로 조립해
# 손잡이를 더해도 「점검은 통과, 인입은 400」이 날 자리였다.
print("\n■ 요청 조립 — CHAT_TEMPERATURE · payload는 한 자리 (B80 ①)")
import request_probe as _RP                                      # noqa: E402

_pay_none, _got_none = _RP.chat_payload()
_pay_03, _ = _RP.chat_payload({"CHAT_TEMPERATURE": "0.3"})
_pay_arg, _ = _RP.chat_payload({"CHAT_TEMPERATURE": "0.3"}, extra=", temperature=0")
show("설정이 비면 payload에 temperature 키가 없다 (모델 기본값으로 간다)",
     "temperature" not in _pay_none and _got_none["error"] is None, str(_pay_none))
show("CHAT_TEMPERATURE=0.3이면 그 값을 싣는다",
     _pay_03.get("temperature") == 0.3, str(_pay_03.get("temperature")))
show("인자가 설정을 이긴다 (지점마다 정할 자리는 남긴다)",
     _pay_arg.get("temperature") == 0, str(_pay_arg.get("temperature")))
_chk_none, _got_chk = _RP.check_payloads()
_chk_03, _ = _RP.check_payloads({"CHAT_TEMPERATURE": "0.3"})
show("llm-check 탐침도 같은 조립을 쓴다 (점검과 인입이 같은 모양을 보낸다)",
     _chk_none and all("temperature" not in x for x in _chk_none)
     and _chk_03 and all(x.get("temperature") == 0.3 for x in _chk_03),
     f"미설정 {[x.get('temperature') for x in _chk_none]} · "
     f"0.3 {[x.get('temperature') for x in _chk_03]}")
show("게이트웨이 단계가 전부 돌았다 (탐침이 완주 — 조립 교체가 단계를 줄이지 않았다)",
     _got_chk["value"] == ["①", "②", "③", "④", "⑤", "⑥", "⑦"], str(_got_chk["value"]))
# **조립하는 자리는 하나다** — `"messages":`를 코드에서 세어 잰다(문면이 아니라 AST의 결).
# **줄 번호를 세지 않는다** — 재는 것은 「그 일을 하는 파일이 몇이냐」다.
_msg_hits = sorted({f"{p.relative_to(ROOT)}"
                    for d in ("core", "cli")
                    for p in sorted((ROOT / d).rglob("*.py"))
                    if "__pycache__" not in p.parts
                    for line in p.read_text(encoding="utf-8").splitlines()
                    if '"messages":' in line and not line.lstrip().startswith("#")})
show("게이트웨이 요청을 조립하는 자리가 한 곳이다 (탐침이 따로 짜지 않는다)",
     _msg_hits == ["core/llm/gateway.py"], str(_msg_hits))

# ============================================================ 임베딩 백엔드
# **임베딩은 게이트웨이 API만이 아니다**(B80 ③ · 사내 실측 2026-09-22): 사내 모델은
# 디스크의 폴더였고, 코드가 그 경로를 모델 이름으로 삼아 POST해 404를 받았다.
print("\n■ 임베딩 백엔드 — gateway | local · 주소 · 오류 문면 (B80 ③)")
_gw1, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_MODEL": "bge-m3"})
_gw2, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_MODEL": "bge-m3",
                                   "EMBED_GATEWAY_URL": "http://embed.stub/v1"})
show("gateway 갈래는 EMBED_GATEWAY_URL을 base로 쓴다 (없으면 채팅 base)",
     _gw1["cap"][0]["url"] == "http://chat.stub/v1/embeddings"
     and _gw2["cap"][0]["url"] == "http://embed.stub/v1/embeddings",
     f"{_gw1['cap'][0]['url']} · {_gw2['cap'][0]['url']}")
_dir80 = Path(tempfile.mkdtemp(prefix="b80model_"))
_loc, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_BACKEND": "local",
                                   "EMBED_MODEL": str(_dir80)}, stub_local=True)
show("local 갈래는 로컬 모델을 부르고 게이트웨이에 닿지 않는다",
     _loc["value"] == [0.1, 0.2, 0.3] and not _loc["cap"]
     and _loc["stub"]["encode"] == 2, f"{_loc['value']} · 전송 {len(_loc['cap'])}")
show("로컬 모델은 프로세스당 한 번 로드한다 (판정마다 다시 읽지 않는다)",
     _loc["stub"]["init"] == 1, f"생성자 {_loc['stub']['init']}회 · encode {_loc['stub']['encode']}회")
_nopkg, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_BACKEND": "local",
                                     "EMBED_MODEL": str(_dir80)})
show("패키지가 없으면 명시적 실패다 — 문면이 설치 줄을 준다 (조용히 안 떨어진다)",
     "NotConfigured" in (_nopkg["error"] or "")
     and "pip install sentence-transformers" in (_nopkg["error"] or ""),
     (_nopkg["error"] or "")[:60])
_nodir, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_BACKEND": "local",
                                     "EMBED_MODEL": str(_dir80 / "없는폴더")},
                    stub_local=True)
show("모델 폴더가 없으면 명시적 실패다 — 문면이 그 경로를 말한다",
     "NotConfigured" in (_nodir["error"] or "") and "없는폴더" in (_nodir["error"] or ""),
     (_nodir["error"] or "")[:60])
_bad, _ = _RP.run(_RP.EMBED_BODY, {"EMBED_BACKEND": "wat", "EMBED_MODEL": "x"})
show("EMBED_BACKEND는 닫힌 2종이다 (모르는 값은 명시적 실패)",
     "NotConfigured" in (_bad["error"] or "") and "gateway | local" in (_bad["error"] or ""),
     (_bad["error"] or "")[:60])
# **비용을 숫자로 보인다**(B80 ③ 개정) — GPU를 요구하지 않는 대신 장치와 시간을 낸다.
_c6, _ = _RP.run(
    'from core.llm import check\n'
    '    out["value"] = [s["detail"] for s in check.probe() if s["id"] == "⑥"]',
    {"EMBED_BACKEND": "local", "EMBED_MODEL": str(_dir80)}, stub_local=True)
_c6d = (_c6["value"] or [""])[0]
show("local ⑥ 문면이 장치·로드·인코딩을 숫자로 낸다 (CPU로 돈다는 것과 그 비용)",
     all(x in _c6d for x in ("local", "cpu", "로드", "인코딩", "차")), _c6d)
_shutil.rmtree(_dir80, ignore_errors=True)
show("임베딩 요청을 조립하는 자리가 한 곳이다 (탐침이 따로 짜지 않는다)",
     [f"{p.relative_to(ROOT)}"
      for d in ("core", "cli") for p in sorted((ROOT / d).rglob("*.py"))
      if "__pycache__" not in p.parts and "/embeddings" in p.read_text(encoding="utf-8")]
     == ["core/llm/embeddings.py"])
# **오류 문면이 주소를 말한다** — 404는 「그 주소에 그 경로가 없다」다.
_ge = llm.GatewayError(404, "not found", "http://embed.stub/v1/embeddings")
show("GatewayError 문면에 POST 주소가 있다 (M9 — 어디를 쳤는지 모르면 설정을 못 고친다)",
     "POST http://embed.stub/v1/embeddings" in str(_ge), str(_ge))
# **USE_MOCK=1 경로는 선택 의존을 import하지 않는다**(문서 7 §7.1).
show("mock 갈래는 sentence_transformers를 import하지 않는다 (선택 의존 격리)",
     "sentence_transformers" not in sys.modules
     and isinstance(embeddings.embed("가"), list),
     str(sorted(m for m in sys.modules if "sentence" in m)))

# ============================================================ 본문 스모크
# **도달과 실행은 다르다**(B79 ③ⓒ). 위의 탐침은 `require`의 `NotConfigured`까지
# 재고 본문은 한 줄도 돌지 않는다 — 사내 실측(2026-09-21)에서 `pick_coord` 본문의
# `json` 미import가 **회귀 1,362 초록인 채로** 사내 파싱을 죽였다. 여기서는 전송
# 한 곳(`gateway._post`)만 스텁으로 갈고 **9지점 본문을 실제로 돌린다.**
print("\n■ 9지점 **본문** 스모크 — 전송만 스텁 · 반환 계약을 잰다 (B79 ③ⓒ)")
from points_smoke import run as _smoke                           # noqa: E402

_sres, _sr = _smoke()
show("9지점 본문이 전부 실행됐다 (스모크가 완주)",
     len(_sres) == len(llm.POINTS) and set(_sres) == set(llm.POINTS),
     _sr.stderr.strip().splitlines()[-1:] and _sr.stderr.strip().splitlines()[-1] or "")
for _key, _label in llm.POINTS.items():
    show(f"{_label} → 본문이 반환 계약대로 값을 돌려준다",
         _sres.get(_key) == "OK", _sres.get(_key, "(미실행)"))

# **⑨는 닫힌 목록에서 고른 값을 돌려준다** — 스텁 응답이 `canonical`로 나온다.
import points_smoke as _PS                                       # noqa: E402
import json as _json79                                           # noqa: E402
_coord_stub = _PS.stub_post("http://stub/v1/chat/completions",
                            {"response_format": {"json_schema": {"schema": {
                                "type": "object",
                                "properties": {"canonical": {"type": ["string", "null"]}},
                                "required": ["canonical"]}}}}, None, 1)
show("⑨ 스텁 응답이 canonical 한 키다 (지점의 반환 계약과 같은 모양)",
     set(_json79.loads(_coord_stub["choices"][0]["message"]["content"])) == {"canonical"})

# ============================================================ 지점 ⑦ 변환
print("\n■ ⑦구조 지도 — 변환은 코어가 한다 (파서는 LLM 스키마를 모른다 · B48 ②)")
_lines = [(2, "1. 개요"), (3, "본문 한 줄"), (4, "1.1 절"), (5, "또 본문")]
_fake = {"headings": [{"row": 2, "level": 1, "title": "1. 개요"},
                      {"row": 4, "level": 2, "title": "1.1 절"},
                      {"row": 99, "level": 1, "title": "입력에 없는 행"},
                      {"row": 3, "level": 0, "title": "급이 0"}],
         "note": "위계가 뒤섞여 급을 매길 수 없음"}
_ochat = llm.chat
llm.chat = struct_map_pass.chat = lambda *a, **k: _fake            # 게이트웨이 없이 변환만 잰다
try:
    _sm = struct_map_pass.map_structure("D1", _lines)
finally:
    llm.chat = struct_map_pass.chat = _ochat
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
     struct_map_pass._map_lines([(7, "가나다라마바사")], 3) == "7\t가나다")
show("크기 예산은 감축 사다리를 탄다 — 행을 빼지 않고 앞자리를 줄인다 (B41)",
     struct_map_pass.MAP_LINE_WIDTHS[0] == 80 and list(struct_map_pass.MAP_LINE_WIDTHS) == sorted(
         struct_map_pass.MAP_LINE_WIDTHS, reverse=True))

# ============================================================ 분기 실물
print("\n■ 분기가 실물로 서 있는가 — 주석을 세지 않는다 (§7.6-B-2)")

# core 6지점 — **종전 방식 유지**(인라인 분기. 팩토리로 옮기는 것은 다음 회차)
WIRED = {"extract": ("core/build/extract.py", "_candidates_for"),
         "judge": ("core/matcher.py", "_judge_live"),
         "embed": ("core/llm/embeddings.py", "gateway.require"),
         "generate": ("cli/register/draft.py", "_draft_live"),
         "link": ("core/query/query.py", "_link_llm"),
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
    _own = struct_map_pass if factory == "struct_mapper" else points
    show(f"{llm.POINTS[key]} — 팩토리→주입 조립→파서 인자가 이어진다 "
         f"({_own.__name__.split('.')[-1]}.{factory}() → {kw}=)",
         callable(getattr(_own, factory, None)) and kw in _asm and kw in _pv)

# ── 변이 시험 — **배선을 하나 빼면 붉는가**(§7.6-B-2 · B48 ④-2)
# 잡는 자리는 주입 조립 지점이다: 파서는 모드를 모르므로 「실호출 모드인데 함수가
# 없다」를 알 수 있는 것은 만드는 쪽뿐이다. 이 어서션이 곧 「진입점이 한 번 정해
# 전부 내려보낸다」의 기계 판정이다.
_orig = (llm.use_mock, points.image_summarizer, points.coord_picker,
         struct_map_pass.struct_mapper)
llm.use_mock = lambda: False
points.image_summarizer = lambda: (lambda ref: "요약")
points.coord_picker = lambda: (lambda s, c: None)
struct_map_pass.struct_mapper = lambda: None    # ← ⑦ 배선을 뺀다
try:
    _inj()
    _mut = "통과 — 붉지 않았다"
except llm.NotConfigured as e:
    _mut = f"NotConfigured — {str(e)[:60]}"
struct_map_pass.struct_mapper = lambda: (lambda d, l: {"rows": []})   # ← 되돌린다
_back = "통과" if _inj().get("map_structure") else "여전히 None"
(llm.use_mock, points.image_summarizer, points.coord_picker,
 struct_map_pass.struct_mapper) = _orig
show("변이 — ⑦ 주입을 빼면 실호출 모드에서 붉는다 (조용한 휴리스틱 폴백 0)",
     _mut.startswith("NotConfigured"), _mut)
show("변이 — 되돌리면 초록이다 (시험 자체가 늘 붉는 것이 아니다)", _back == "통과", _back)

# ============================================================ B63 ② 대장 잠금
print("\n■ B63 ② — 코드와 칸 대장이 어긋나면 빨간불 (00_칸_대장.md이 정본)")

import re                                                        # noqa: E402

_LEDGER = ROOT / "docs" / "구조도" / "00_칸_대장.md"
_led = _LEDGER.read_text(encoding="utf-8")


def _ledger_points():
    """대장의 L칸 행에서 `point \`…\`` 를 모은다 — **대장은 파일로 읽는다.**

    문면을 코드에 복사해 두면 잠금이 스스로를 잠그는 꼴이 된다 — 대장을 고쳐도
    사본이 그대로라 초록이고, 어긋남을 잡으라고 세운 장치가 어긋남을 감춘다.
    """
    out = set()
    for ln in _led.splitlines():
        if not ln.startswith("|") or "| L |" not in ln:
            continue
        i = ln.find("point ")
        if i >= 0:
            out |= set(re.findall(r"`([a-z_]+)`", ln[i:]))
    return out


def _code_points():
    """코드가 실제로 붙이는 호출 태그 — `chat`은 게이트웨이 기본값이라 칸이 아니다(0.4)."""
    return {m for d in ("cli", "core", "parser")
            for f in sorted((ROOT / d).rglob("*.py"))      # 파트 폴더까지 훑는다(B78 2a)
            for m in re.findall(r'point="([a-z_]+)"',
                                f.read_text(encoding="utf-8"))} - {"chat"}


_cp, _lp = _code_points(), _ledger_points()
# **누락 방지의 방향**: 코드에 point가 생겼는데 대장에 없으면 빨간불이다. 반대로
# 대장에만 있는 칸은 C·H·G일 수 있으나, L칸의 point는 코드에 있어야 칸이 산다.
show("②L칸 == 호출 지점 — 코드의 point 집합이 대장 L칸과 같다",
     _cp == _lp,
     f"코드에만 {sorted(_cp - _lp)} · 대장에만 {sorted(_lp - _cp)}" if _cp != _lp
     else f"{len(_cp)}종")
_lf = set(re.findall(r"`prompts/([^`]+\.md)`", _led))
_af = {f.name for f in (ROOT / "prompts").glob("*.md")}
show("②지시문 == 파일 — 대장이 적은 prompts/ 집합이 실물과 같다",
     _lf == _af,
     f"대장에만 {sorted(_lf - _af)} · 실물에만 {sorted(_af - _lf)}" if _lf != _af
     else f"{len(_af)}개")

hooks = [f"{p.relative_to(ROOT)}:{i}"
         for d in ("core", "cli", "parser")
         for p in sorted((ROOT / d).glob("*.py"))
         for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
         if "HOOK:" in ln]
show("주석 훅 표시가 0건이다 — 주석은 실행되지 않는다", not hooks, str(hooks))

print("\n" + "=" * 62)
print(f"전체 결과: {'PASS — 게이트웨이 골조 성립' if not _fail else f'FAIL {_fail}건'}")
sys.exit(1 if _fail else 0)
