# -*- coding: utf-8 -*-
"""G6 ⑬ dry-run은 실제와 같은 검사 · show tree는 흐름 순서 · 사용량 줄 · 대소문자 2차 대조 (B96).

창작 표본(mock 덧칠 · 시험 전용 사전)으로 메커니즘을 잰다 — 수치는 근거가 아니다([정정] 50).

잠그는 성질:
  ⓐ 층 config에 canonical_scope가 남으면 --dry-run도 rc 1 · 실제 실행과 같은 ⓓ 문면
  ⓑ 골격 문법 위반이면 --dry-run rc 1 · 태그
  ⓒ --dry-run을 통과한 같은 상태에서 실제 bootstrap rc 0
  ⓓ show tree 형제 순서 = precedes 사슬 · 흐름 밖은 뒤
  ⓔ 뷰 확인 · 시트 역할 관문 끝에 사용량 줄
  ⓕ 라틴 대소문자만 다른 표기가 사전 조회·적중·좌표에서 맞는다 · 둘 이상을 가리키면 미스
  ⓖ norm·문서 id는 그대로다
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, _rw, done    # noqa: F401


def _run(*args):
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), *args], cwd=str(ROOT),
                       env={**os.environ, "USE_MOCK": "1"}, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout + r.stderr


print("\n■ B96 ① dry-run = 실제 실행과 같은 검사 · 쓰기만 0")
init.init(fresh_=True)
_rw(_P.layers("process", "config.json"),
    lambda c: c.update(canonical_scope={"bind_categories": ["Property"], "sep": "::"}))
_rcd, _od = _run("bootstrap", "--dry-run")
_rcr, _or = _run("bootstrap")
_line = [l for l in _od.splitlines() if "canonical_scope가 남아 있다" in l]
show("ⓐ 층 config에 canonical_scope가 남으면 --dry-run도 rc 1 · 실제 실행과 같은 ⓓ 문면",
     _rcd != 0 and _rcr != 0 and _line and _line[0] in _or and "멈출 것 1건" in _od,
     (_line or [""])[0][:90])
init.init(fresh_=True)
_seed = _P.layers("process", "skeleton.json")
_seed.write_text(_seed.read_text(encoding="utf-8").replace('"노칭"', '"@노칭오타"', 1),
                 encoding="utf-8")
_rcd, _od = _run("bootstrap", "--dry-run")
show("ⓑ 골격 문법 위반이면 --dry-run rc 1 · 태그·줄",
     _rcd != 0 and "K05" in _od and "멈출 것" in _od,
     [l.strip()[:70] for l in _od.splitlines() if "K05" in l][:1])
init.init(fresh_=True)
_rcd, _od = _run("bootstrap", "--dry-run")
_rcr, _or = _run("bootstrap")
show("ⓒ --dry-run을 통과한 같은 상태에서 실제 bootstrap rc 0",
     _rcd == 0 and "멈출 것 0건" in _od and _rcr == 0, _od.strip().splitlines()[-1][:80])

print("\n■ B96 ② show tree는 흐름 순서")
_rc, _ot = _run("show", "tree")
_lines = _ot.splitlines()


def _pos(name, after=0):
    return next((i for i, l in enumerate(_lines) if i >= after and f"─ {name}  [" in l), -1)


_n = next(i for i, l in enumerate(_lines) if "─ 노칭  [" in l)
_order = [_pos(x, _n) for x in ("전극 언와인딩", "노칭 타발", "비전검사", "전극 리와인딩", "anode")]
show("ⓓ show tree 형제 순서 = precedes 사슬(이름순 아님) · 흐름 밖(극성 인스턴스)은 뒤",
     _rc == 0 and all(a < b for a, b in zip(_order, _order[1:])) and -1 not in _order
     and "순서 = 흐름" in _ot, str(_order))

print("\n■ B96 ③ 사용량 줄")
from cli import sheet_gate as SG   # noqa: E402
import contextlib, io               # noqa: E402,E401
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    SG.gate(str(ROOT / "tests/fixtures/raw/RFQ01.xlsx"), "XB96", "prose", dry_run=True,
            lenses=["process"])
_rg, _og = _run("register", "generate", "b96toc", "quality", str(ROOT / "tests/fixtures/raw/TOC01.xlsx"), "--allow-mock")
_rv, _ov = _run("register", "review", "b96toc", "--no-llm-coord", "--allow-mock")
show("ⓔ 시트 역할 관문 · 뷰 확인 끝에 사용량 줄(mock이면 0)",
     "LLM 사용량 — 호출 0회" in _buf.getvalue() and "LLM 사용량 — 호출" in _ov,
     [l.strip() for l in _ov.splitlines() if "LLM 사용량" in l][:1])
shutil.rmtree(_P.registry("review", "b96toc"), ignore_errors=True)

print("\n■ B96 ④ 라틴 대소문자 무시 2차 대조")
from core.dictionary import Dictionary as _D        # noqa: E402
from core.build import extract as _EX               # noqa: E402
from core.build.lens import score as _score         # noqa: E402
from core.state.ids import doc_hash as _dh          # noqa: E402
from parser import form as _FORM, tagger as _TG     # noqa: E402
_d = _D({})
_d.register("Notching", "N1", provenance="t")
_d.register("NC", "A", provenance="t")
_d.register("nc", "B", provenance="t")
_nodes = [{"canonical": "노칭", "aliases": ["Notching"], "tier": "sub"}]
_plans = []
_TG.tag([{"process_ref": "NOTCHING"}], nodes=_nodes, notice=_plans.append)
_run("bootstrap")
show("ⓕ 대소문자만 다른 표기가 사전·적중·좌표에서 맞는다(하나일 때만) · 둘 이상이면 미스",
     _d.lookup("notching") == ["N1"] and _d.lookup("Nc") == [] and _d.lookup("NC") == ["A"]
     and _score("NOTCHING 공정", {"notching"}) == 1
     and _FORM._hits({"cells": {"A1": "NOTCHING 사양"}}, {"notching"}) == 1
     and _plans and _plans[0]["정확_일치"] == 1 and _plans[0]["표기_종수"] == 0
     and "노칭" in _EX.attach_candidates("NOTCHING"),
     f"{_d.lookup('notching')} · {_EX.attach_candidates('NOTCHING')[:2]}")
show("ⓖ norm·문서 id는 그대로다(대소문자를 접지 않는다)",
     norm("Notching") == "Notching"
     and _dh({"doc_type": "t", "chunks": [{"text": "Notching"}]})
     != _dh({"doc_type": "t", "chunks": [{"text": "notching"}]}))
init.init(fresh_=True)

done()
