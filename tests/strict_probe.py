# -*- coding: utf-8 -*-
"""시험용 **엄격 규칙 수집 도우미**(B200 ⓪ — 사내 [3/8] HTTP 400 「additionalProperties is required」) — 실호출 길을 네트워크 없이 돈다.

mock을 끄고(`gateway.use_mock`) **전송 `_post`만** 가로챈다 — 요청 조립(`_payload` · 엄격 규칙 막음) · 지시문 · 검사는 실물이다.
가로챈 요청마다 `response_format.json_schema`와 부른 자리(파일:행)를 적고, 답은 그 schema에서 지은 가장 작은 값이다(창작 —
흐름을 끝까지 돌리는 재료일 뿐 근거가 아니다 [정정] 50). 도는 길: CP01(표) · PFMEA01(표) · RFQ01(산문 — 겸 단 선언으로 골격 단 줄)
을 `--step`(tty 답 — 골격 칸 물음에는 말 한 번) · `ops alias-audit --llm` · 뷰어 「LLM 검토」(`/api/aliases/review`의 함수).
보내기 전 막음(`gateway.SchemaError`)에 걸린 것은 `errors`에 — 그 호출은 전송되지 않는다.

    from strict_probe import run
    got = run()      # {"calls": [{site, schema, strict}], "errors": [str], "flows": {이름: 결과}}
"""
from __future__ import annotations

import builtins
import contextlib
import inspect
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tests")):            # 시험 파일 관례(직접 실행 — test_2a_gateway와 같다)
    if _p not in sys.path:
        sys.path.insert(0, _p)
FX = ROOT / "tests" / "fixtures"
ENV = {"LLM_GATEWAY_URL": "http://fake.gw/v1", "CHAT_MODEL": "fake-chat", "EMBED_MODEL": "fake-embed",
       "EMBED_BACKEND": "gateway", "LLM_RETRY": "0", "LLM_TIMEOUT": "5"}


def synth(s):
    """schema에서 가장 작은 답 — 칸 전부(enum은 첫 값 · 배열은 빈 것 · 비워도 되는 칸은 null)."""
    if not isinstance(s, dict):
        return None
    t = s.get("type")
    ts = t if isinstance(t, list) else [t]
    if s.get("enum"):
        return next((e for e in s["enum"] if e is not None), None)
    if "object" in ts or "properties" in s:
        return {k: synth(v) for k, v in (s.get("properties") or {}).items()}
    if "array" in ts:
        return []
    if "null" in ts:
        return None
    if "string" in ts:
        return ""
    if "integer" in ts or "number" in ts:
        return 0
    if "boolean" in ts:
        return False
    return synth((s.get("anyOf") or [None])[0])


def _site():
    """부른 자리 — 게이트웨이 밖의 첫 프레임(레포 상대 파일:행)."""
    for f in inspect.stack()[2:]:
        p = Path(f.filename)
        if p.name not in ("gateway.py", "strict_probe.py"):
            try:
                return f"{p.resolve().relative_to(ROOT)}:{f.lineno}"
            except ValueError:
                return f"{p.name}:{f.lineno}"
    return "?"


def _answers():
    """tty 답 — 골격 칸 물음에는 말 한 번(사람 말 길) · 확인 물음은 Enter · 예/아니오는 예 · 그 밖은 c · 끝없는 물음은 EOF."""
    state = {"n": 0, "said": False}

    def ask(q=""):
        state["n"] += 1
        if state["n"] > 400:
            raise EOFError
        if "말 또는 글쇠" in q and not state["said"]:
            state["said"] = True
            return "1 이것과 같은 거"
        if "[Y/n]" in q or "맞으면 Enter" in q:
            return ""
        if "[y/N]" in q:
            return "y"
        return "c"
    return ask


def _flows(errors):
    import run as RUN
    from cli import ingest as IG
    from cli.ops import _alias_audit
    from cli.viewer import alias as VA
    from core.llm import gateway
    from core.state import alias_review as AR
    out = {}

    def go(name, fn):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                out[name] = fn()
        except gateway.SchemaError as e:
            errors.append(f"{name}: {e}")
        except BaseException as e:                       # noqa: BLE001 — 흐름이 끝까지 못 가도 잡힌 호출은 남는다
            out[name] = f"{type(e).__name__}: {str(e)[:120]}"
        errors.extend(f"{name}: {ln.strip()}" for ln in buf.getvalue().splitlines() if "schema 엄격 규칙 위반" in ln)
    with contextlib.redirect_stdout(io.StringIO()):
        RUN.cmd_bootstrap([])
    _register()
    go("CP01 --step", lambda: IG.ingest_file(str(FX / "raw" / "CP01.xlsx"), "cp", step=True))
    go("PFMEA01 --step", lambda: IG.ingest_file(str(FX / "raw" / "PFMEA01.xlsx"), "pfmea", step=True))
    go("RFQ01 --step", lambda: IG.ingest_file(str(FX / "raw" / "RFQ01.xlsx"), DT, step=True,
                                              sheets="2-4:prose 5:ref *:skip", coord="노칭"))   # 시트 역할 호출은 관문 앞에서 잡힌다
    from cli import sheet_gate as SG
    go("시트 역할(RFQ01)", lambda: SG.judge(SG.rows_of(str(FX / "raw" / "RFQ01.xlsx")), True))   # 시트 관문의 LLM 제안 — 위 인입은 --sheets
    go("ops alias-audit --llm", lambda: _alias_audit(["--llm"]))

    def viewer():
        code, body = VA.start_review()
        t0 = time.time()
        while VA.BUSY.locked() and time.time() - t0 < 60:
            time.sleep(0.05)
        return code, VA.LAST.get("error"), AR.PROGRESS.get("calls")
    go("뷰어 /api/aliases/review", viewer)
    return out


#: 산문 표본의 문서 종류(레포의 기본 prose 엑셀 어댑터 — `g6_common`과 같은 등록 · 그 모듈은 격리를 다시 부르므로 import하지 않는다)
DT = "prose_xlsx_basic"


def _register():
    from core import paths as P
    from core.state import store
    p = P.schemas(f"{DT}.json")
    P.ensure(p)
    p.write_text(json.dumps({"doc_type": DT, "schema_version": 1, "layer": "process", "payload_kind": "prose",
                             "use_blocks": ["common_core", "process_coord"], "fields": {}, "edges": []},
                            ensure_ascii=False), encoding="utf-8")
    from core.state import registry
    dts = store.read(store.DOC_TYPES, {})
    for k, v in registry._builtin().items():                     # 실호출 길은 등록부만 본다 — 내장 표본(cp · pfmea)을 등록으로
        ad = FX / "adapters" / f"{k}.py"
        if k not in dts and ad.is_file():
            dts[k] = dict(v, status="registered", adapter=str(ad))
    dts[DT] = {"doc_type": DT, "status": "registered", "layer": "process", "schema": f"schemas/{DT}.json",
               "adapter": str(ROOT / "parser" / "adapters" / "basic_prose_xlsx.py"), "schema_version": 1}
    store.write(store.DOC_TYPES, dts)


def _also():
    """겸 단 선언(시험 덧칠 `layers_b90/overlay.json`의 also) — 산문 제목 개체가 골격 단 줄로 선다."""
    from core import paths as P
    from core.state.bootstrap import bootstrap
    ov = json.loads((FX / "layers_b90" / "overlay.json").read_text(encoding="utf-8"))
    p = P.common()
    c = json.loads(p.read_text(encoding="utf-8"))
    for k, v in ov["also"].items():
        if k in c.get("categories", {}):
            c["categories"][k]["also"] = v
    p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    for lay in ("process", "quality"):
        bootstrap(lay, echo=False)


def run():
    from core import paths
    from core.llm import gateway
    from core.state import init
    import fake_gateway as FG
    paths.home()                                         # 상태 루트는 mock 루트에 먼저 박는다(아래에서 mock을 끈다)
    with contextlib.redirect_stdout(io.StringIO()):
        init.init(fresh_=True, all_=True)
    _also()
    calls, errors = [], []

    def post(url, payload, key, timeout):
        if str(url).endswith("/embeddings"):
            inp = payload.get("input")
            return {"data": [{"embedding": FG.vec(x)} for x in (inp if isinstance(inp, list) else [inp])]}
        js = (payload.get("response_format") or {}).get("json_schema") or {}
        calls.append({"site": _site(), "schema": js.get("schema"), "strict": js.get("strict")})
        text = json.dumps(synth(js.get("schema")), ensure_ascii=False) if js else "ok"
        return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                                                       "total_tokens": 2}}
    keep = (gateway.use_mock, gateway._post, builtins.input, sys.stdin.isatty)
    env0 = {k: os.environ.get(k) for k in ENV}
    os.environ.update(ENV)
    gateway.use_mock, gateway._post = (lambda: False), post
    builtins.input, sys.stdin.isatty = _answers(), (lambda: True)
    try:
        flows = _flows(errors)
    finally:
        gateway.use_mock, gateway._post, builtins.input, sys.stdin.isatty = keep
        for k, v in env0.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return {"calls": calls, "errors": errors, "flows": flows}


if __name__ == "__main__":                                 # 손으로 — 잡힌 자리 목록
    got = run()
    from core.llm import gateway as _g
    for site in sorted({c["site"] for c in got["calls"]}):
        cs = [c for c in got["calls"] if c["site"] == site]
        bad = sorted({b for c in cs for b in _g.strict_issues(c["schema"] or {})})
        print(f"{site} · {len(cs)}회 · schema {'있음' if cs[0]['schema'] else '없음'} · 위반 {bad or 0}")
    print("막음", got["errors"] or 0)
    print("흐름", got["flows"])
