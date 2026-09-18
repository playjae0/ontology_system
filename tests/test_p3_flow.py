# -*- coding: utf-8 -*-
"""P3 ⑧ 흐름 — 지문·미선택 갈래 · CSV 등가 · 열 판정 대장 · 분할 줄 · 좌표 예고 · G39·G4G."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src            # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

import contextlib as _ctx
from cli import ingest as _i66
import io as _io
from core.llm import gateway as _llm
import os as _os
from cli import scan as _s66
from core.llm import gateway

setup()


print("\n■ B66 ① — 지문 대상은 `sheets` 구조다 (포맷 이름이 아니다)")

_cpa66 = [str(ROOT / "tests" / "fixtures" / "adapters" / "cp.py")]
_sx66 = _s66.scan(RAW / "CP01.xlsx", _cpa66)
_sc66 = _s66.scan(RAW / "CP01.csv", _cpa66)
show("①ⓑ 같은 표의 두 포맷이 **같은 어댑터에서 같은 후보 판정**을 받는다",
     _sx66["candidates"] == _sc66["candidates"] == ["cp"]
     and _sx66["details"] == _sc66["details"],
     f"xlsx {_sx66['candidates']} · csv {_sc66['candidates']}")
_sel66 = _i66.select(RAW / "CP01.csv", adapter_paths=_cpa66)
show("①ⓒ doc-type 없이 넣은 CSV를 **스캔이** 고른다 (by == scan)",
     _sel66["status"] == "chosen" and _sel66["doc_type"] == "cp"
     and (_sel66["basis"] or {}).get("by") == "scan",
     f"{_sel66['status']} · {(_sel66.get('basis') or {}).get('by')}")

# ⓓ **포맷 이름으로 갈라지는 자리가 0이다** — 문서 6 §6.4 「포맷을 보지 않는다」.
# 주석·문자열이 아니라 **동작 줄**을 센다(CLAUDE.md 3). 읽는 쪽이 대상이다:
# reader가 `format`을 **쓰는** 것은 어댑터에게 사실을 알리는 일이라 남는다.
_fmt66 = []
for _d66 in ("cli", "core", "parser", "kit"):
    for _f66 in sorted((ROOT / _d66).rglob("*.py")):
        for _n66, _ln66 in enumerate(_f66.read_text(encoding="utf-8").splitlines(), 1):
            _code66 = _ln66.split("#")[0]
            if 'get("format")' in _code66 or '["format"]' in _code66:
                _fmt66.append(f"{_f66.relative_to(ROOT)}:{_n66}")
show("①ⓓ cli·core·parser·kit에 봉투 format을 읽는 동작 줄 0",
     not _fmt66, str(_fmt66[:4]))

print("\n■ B66 ② — 미선택 네 갈래 (「없다」는 어댑터가 0건일 때만)")
#
# 구판은 한 문면(「지문 일치 0건 — 대조할 정형 어댑터가 없다」)이 서로 다른 넷을
# 덮었다. 사내에서 CSV가 대조조차 안 된 것(①)이 그 문면으로 나왔고 사람은
# **어댑터가 없다고 읽었다.** 갈래마다 다음 수가 다르다 — 그래서 문면이 갈린다.
_d66e = _P.review() / "_b66_empty"          # 소재지는 있는데 어댑터가 0개
_d66p = _P.review() / "_b66_prose"          # 산문 어댑터만 있다 (자격 없음)
shutil.rmtree(_d66e, ignore_errors=True)
shutil.rmtree(_d66p, ignore_errors=True)
_d66e.mkdir(parents=True)
_d66p.mkdir(parents=True)
(_d66p / "b66prose.py").write_text(
    'ADAPTER = {"doc_type": "b66prose", "payload_kind": "prose", "expects": {}}\n',
    encoding="utf-8")
_cases66 = {
    "포맷":   _i66.select(RAW / "PPT_basic.pptx", adapter_paths=_cpa66),
    "소재지": _i66.select(RAW / "CP01.csv", adapter_paths=[str(_d66e)]),
    "자격":   _i66.select(RAW / "CP01.csv", adapter_paths=[str(_d66p)]),
    "일치":   _i66.select(RAW / "PFMEA01.xlsx", adapter_paths=_cpa66),
}
_why66 = {k: v["reason"] for k, v in _cases66.items()}
show("② 네 경우가 전부 미선택이고 **문면이 서로 다르다**",
     all(v["status"] == "none" for v in _cases66.values())
     and len(set(_why66.values())) == 4,
     " | ".join(f"{k}:{(v or '')[:22]}" for k, v in _why66.items()))
show("② 「소재지가 비었다」는 어댑터가 0건일 때만 난다",
     "소재지가 비었다" in _why66["소재지"]
     and not any("소재지가 비었다" in _why66[k] for k in ("포맷", "자격", "일치")))
show("② 어댑터가 하나라도 있으면 **그 이름이 문면에 있다** (무엇과 대조했나)",
     "b66prose" in _why66["자격"] and "cp" in _why66["일치"])
show("② 지문 대상이 아닌 포맷은 **무엇이라서** 아닌지를 말한다",
     "pptx" in _why66["포맷"] and "--doc-type" in _why66["포맷"])
# 네 문면 모두 B61 계약 — 원인 + 그대로 칠 수 있는 다음 줄.
show("② 네 문면 모두 다음 줄을 준다 (B61 계약)",
     all(("--doc-type" in v) or ("python " in v) for v in _why66.values()))
shutil.rmtree(_d66e, ignore_errors=True)
shutil.rmtree(_d66p, ignore_errors=True)


# ── B66 ⑤ — 같은 표는 포맷이 달라도 같은 지식이 된다 ─────────────────────
#
# 파서 뒤는 포맷을 모르니 다를 수 없다 — 그것은 **논리**이고 이 프로젝트는 실행으로
# 판정한다(CLAUDE.md 3). CSV 출처로 그래프를 세우고 질의에 답해 본 적이 한 번도
# 없었다. 표본 쌍은 `CP01.xlsx`와 그 시트를 그대로 옮긴 `CP01.csv`다.
#
# **스냅샷은 별도 프로세스가 뜬다**(`tests/csv_equiv.py`) — 한 프로세스에서 두 번
# 인입하면 앞 판의 그래프·사전이 살아 있어 둘째 판이 첫 판을 본다.
print("\n■ B66 ⑤ — CSV 전 구간 등가 (인입 → 그래프 → 질의)")


def _snap66(doc, *a):
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "csv_equiv.py"), str(doc), *a],
                       capture_output=True, text=True, cwd=str(ROOT),
                       stdin=subprocess.DEVNULL)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or r.stdout)[-300:]}


_x66 = _snap66(RAW / "CP01.xlsx")
_c66 = _snap66(RAW / "CP01.csv")
show("⑤ 두 포맷 모두 인입 성공 (등가 판정의 전제)",
     _x66.get("ingest") == _c66.get("ingest") == "성공",
     f"xlsx {_x66.get('ingest')} · csv {_c66.get('ingest')} — {_c66.get('reason')}")
show("⑤ⓐ 계약 JSON이 같다 — 포맷·시트 이름·doc_id를 뺀 전부 (records 포함)",
     _x66.get("envelope") and _x66["envelope"] == _c66.get("envelope"),
     f"records {len((_x66.get('envelope') or {}).get('records') or [])}")
# **노드 0끼리 같은 것은 판정이 아니다** — 전제를 어서션 안에 둔다.
_nodes66 = ((_x66.get("graph") or {}).get("process") or {}).get("nodes", 0)
show("⑤ⓑ 그래프의 노드 수·엣지 수·카테고리별 수가 같다 (전제: 노드 > 0)",
     _nodes66 > 0 and _x66.get("graph") == _c66.get("graph"),
     f"노드 {_nodes66} · 엣지 {((_x66.get('graph') or {}).get('process') or {}).get('edges')}"
     f" · {((_x66.get('graph') or {}).get('process') or {}).get('categories')}")
# 근거 id는 문자열이 아니라 **가리키는 자리**로 본다(D-146) — `chunk_id`는 시트
# 이름을 포함한 로케이터의 해시이고 노드 id는 ULID라 같은 문서를 두 번 돌려도 다르다.
_cp66 = [q for q in (_x66.get("queries") or []) if q["evidence"]]
show("⑤ⓒ cp 출처를 지나는 스모크 질의의 답·근거가 같다 (전제: 그런 질의 > 0)",
     len(_cp66) > 0 and _x66.get("queries") == _c66.get("queries"),
     f"근거 있는 질의 {len(_cp66)}/{len(_x66.get('queries') or [])}")
# **변이** — 어서션이 정말 두 판을 비교한다는 증거. `reader.read_csv`가 헤더 한
# 셀을 바꾸면 ⓐ가 붉어야 한다. 초록으로 남으면 그 어서션은 아무것도 잠그지 않는다.
_m66 = _snap66(RAW / "CP01.csv", "--mut")
show("⑤ 변이 — read_csv가 헤더 한 셀을 바꾸면 ⓐ가 붉어진다",
     _m66.get("envelope") != _x66.get("envelope"),
     f"{_m66.get('ingest')} — {(_m66.get('reason') or _m66.get('error') or '')[:70]}")


# ── B67 ② — 열 판정 대장: 판단과 코드를 가른다 ──────────────────────────
#
# 생성 LLM이 열마다 내린 판단(role · 필드↔열 · 안 쓰는 열)이 **코드 안에만** 살았다.
# 그래서 코드를 버리면 판단도 버려지고, 코드를 살리면 오류도 살았다 — 사내에서
# G31로 끝난 등록을 `--resume`하면 같은 G31이 났다. 대장은 그 판단만 따로 적는다.
print("\n■ B67 ② — 열 판정 대장 (columns.json)")

reset("ipqc")
run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx"))
_led67 = Rledger.read_ledger("ipqc")
_pcols67 = {c for pp in Rledger._profiles("ipqc") for c in (pp.get("열") or {})}
# **대장은 프로파일 ∪ 어댑터가 쓰는 열이다**(B76 ② — 구판은 프로파일뿐이라
# 어댑터가 프로파일 밖 열을 쓰면 그 필드의 행이 없었다).
_acols67 = Rledger.col_values((getattr(
    R._load(ROOT / R._state("ipqc")["adapter"], "p3_led67"), "ADAPTER", {})
    .get("expects") or {}).get("columns"))
show("② 대장의 행 집합 == 프로파일 열 ∪ 어댑터가 쓰는 열 (한 열에 한 행)",
     _led67 and {r["col"] for r in _led67} == (_pcols67 | _acols67),
     f"대장 {len(_led67)}행 · 프로파일 {len(_pcols67)}열 · 어댑터 {len(_acols67)}열")
show("② 한 열에 한 행 — 열문자 중복 0",
     len({r["col"] for r in _led67}) == len(_led67))
show("② 열 전량이 판정을 갖는다 — 필드·role 또는 미해결 태그",
     all(r.get("field") or r.get("role") or str(r.get("status")).startswith("open")
         for r in _led67),
     str([r["col"] for r in _led67 if not (r.get("field") or r.get("role")
                                           or str(r.get("status")).startswith("open"))]))

# ⓑ **코드만 깨뜨린다** — 판단(role·필드 대응)은 그대로여야 한다. 이것이 이 회차의
# 성질이다: 재생성은 코드를 새로 받되 판단은 이어받는다.
_judg67 = {(r["col"], r["role"], r["field"]) for r in _led67}
_ad67 = REVIEW / "ipqc" / "adapter.py"
_src67 = _ad67.read_text(encoding="utf-8")
_ad67.write_text(_src67.replace("def extract(",
                                "def _b67_broken(raw):\n"
                                "    return normalizer.no_such_helper(raw)\n\n\n"
                                "def extract(", 1), encoding="utf-8")
_calls67a = gateway.usage_total()["calls"]
_v67 = Rgate.regate("ipqc", R._state("ipqc"))       # 관문 재실행 — 재생성·문답 없음
_led67b = Rledger.read_ledger("ipqc")
show("②ⓑ 코드에 오류만 심어도 **role·필드 대응은 그대로다** (판단과 코드가 갈렸다)",
     _v67 != "PASS" and {(r["col"], r["role"], r["field"]) for r in _led67b} == _judg67,
     f"관문 {_v67} · 대장 {len(_led67b)}행")
show("②ⓑ 대장 쓰기 경로에 LLM 호출 0 (시스템이 뽑는다 — C38)",
     gateway.usage_total()["calls"] == _calls67a,
     f"{_calls67a} → {gateway.usage_total()['calls']}")

# ⓑ 지시가 열을 이름으로 부르면 그 행이 갱신되고 **출처가 사람으로 바뀐다**
_o67 = next((r for r in _led67 if str(r.get("status")).startswith("open")), _led67[-1])
run("review", "ipqc", "--instruct", f"{_o67['col']}열은 attribute다")
_row67 = next(r for r in Rledger.read_ledger("ipqc") if r["col"] == _o67["col"])
show("②ⓑ --instruct가 그 열의 행을 갱신하고 출처가 instruct rev N이 된다",
     _row67.get("role") == "attribute"
     and str(_row67.get("by", "")).startswith("instruct rev"),
     f"{_row67['col']} · role {_row67.get('role')} · by {_row67.get('by')}")
show("②ⓑ 사람이 정한 판단은 뒤 관문이 지우지 않는다 (산출이 아직 안 쓴 열이어도)",
     Rledger.sync_ledger("ipqc", R._state("ipqc"))
     and next(r for r in Rledger.read_ledger("ipqc")
              if r["col"] == _o67["col"]).get("by", "").startswith("instruct"))
show("② 열을 못 집는 지시는 **대장을 건드리지 않는다** (추측으로 행을 고치지 않는다)",
     Rledger.apply_to_ledger("ipqc", "전반적으로 더 꼼꼼히 해라", "instruct rev 99") == 0)
# prose에는 열이 없다 — 대장을 세우면 본문 열 하나가 「빠뜨린 열」로 뜬다(거짓).
reset("toc_report")
run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"), str(RAW / "TOC02.xlsx"))
show("② prose 어댑터에는 대장이 서지 않는다 (열이 없는 자리다)",
     R._state("toc_report") and not Rledger.ledger_path("toc_report").exists(),
     f"관문 {(R._state('toc_report') or {}).get('machine_gate')}")


# ── B67 ① — 이어하기는 코드가 아니라 판단을 이어받는다 ───────────────────
#
# `--resume`이 `draft(doc_type)`를 지시·이력 없이 불렀고 생성은 `temperature=0`이라
# **같은 입력 → 같은 코드 → 같은 실패**였다. 이어하기가 재생성이 아니라 재현이었다.
print("\n■ B67 ① — --resume: 관문 먼저 · 지난 실패를 지시로")

_sent67 = []
_p67, _r67, _m67 = _llm._post, _llm.require, _llm.use_mock


def _live67():
    """전송 직전 payload를 잡는다 — 「지시가 모델에 닿았나」는 전송분이 답한다."""
    _llm.require = lambda *a, **k: {"url": "http://x", "model": "m", "key": "k",
                                    "timeout": 5, "retry": 0}
    _llm.use_mock = lambda: False
    _llm._post = lambda u, p, k, t: _sent67.append(p) or {
        "choices": [{"message": {"content": json.dumps(
            {"adapter_py": "# x\nADAPTER = {}\ndef extract(raw):\n    return []",
             "schema_json": "{}"})}}]}


_live67()
# **재는 것은 이어하기가 보내는 전송분이다** — 그 뒤의 관문 루프(문답·자동 재생성)는
# 이 어서션의 대상이 아니라서 끊는다. 끊지 않으면 가짜 응답이 문답 화면으로 흘러간다.
_fin67 = Rgate._finish_generate
Rgate._finish_generate = lambda *a, **k: 0
try:
    _b67 = _io.StringIO()
    with _ctx.redirect_stdout(_b67):
        Rgen.cmd_generate("ipqc", None, [], resume=True)
finally:
    Rgate._finish_generate = _fin67
    _llm._post, _llm.require, _llm.use_mock = _p67, _r67, _m67
_scr67 = _b67.getvalue()
_sys67 = _sent67[0]["messages"][0]["content"] if _sent67 else ""
_tags67 = [c for c, _l, _d in Rgate.fail_lines(R._state("ipqc").get("harness_out") or "")]
show("①ⓑ 관문 FAIL 상태의 --resume이 **지난 판정을 전송분에 싣는다**",
     bool(_sent67) and any(t in _sys67 for t in _tags67) if _tags67 else False,
     f"태그 {_tags67} · system {len(_sys67.encode()):,}B")
show("①ⓑ 지시 이력도 함께 실린다 (앞 회차의 교정을 사람이 다시 적지 않는다)",
     bool(_sent67) and "## [재생성 지시]" in _sys67
     and _sys67.count("- ") > 0, f"전송 {len(_sent67)}회")
show("①ⓐ 화면이 지난 FAIL 건수와 이력 건수를 말한다",
     "[이어하기]" in _scr67 and "지시로 싣는다" in _scr67,
     [l.strip() for l in _scr67.splitlines() if "[이어하기]" in l][:1])

# ⓑ **PASS면 초안을 다시 받지 않는다** — 통과한 것을 이유 없이 갈지 않는다.
_drafts67 = []
_d67 = Rdraft.draft


def _spy67(doc_type, revision=0, *, instruction=None, history=None):
    _drafts67.append({"dt": doc_type, "rev": revision, "instruction": instruction,
                      "history": list(history or [])})
    return _d67(doc_type, revision, instruction=instruction, history=history)


Rdraft.draft = _spy67
try:
    with _ctx.redirect_stdout(_io.StringIO()):
        Rgen.cmd_generate("toc_report", None, [], resume=True)   # 관문 PASS 상태
    _pass67 = list(_drafts67)
    # ⓑ 초안이 없으면 초회와 같은 입력이다 (지시 없음 · rev 0)
    _drafts67.clear()
    _st67 = R._state("ipqc")
    (Rdraft._at(_st67["adapter"])).unlink(missing_ok=True)
    try:
        with _ctx.redirect_stdout(_io.StringIO()):
            Rgen.cmd_generate("ipqc", None, [], resume=True)
    except SystemExit:
        pass
    _none67 = list(_drafts67)
finally:
    Rdraft.draft = _d67
show("①ⓑ 관문 PASS 상태의 --resume은 **초안을 다시 받지 않는다** (LLM 호출 0)",
     _pass67 == [], f"draft {len(_pass67)}회")
show("①ⓑ 초안이 없는 --resume은 **초회와 같은 입력**이다 (지시 0 · rev 0)",
     _none67 and _none67[0]["instruction"] is None and _none67[0]["rev"] == 0,
     str([{k: v for k, v in c.items() if k != "history"} for c in _none67][:1]))
reset("ipqc")
reset("toc_report")


# ── B68 ② — 화면이 분할을 말한다 (generate · status · 뷰) ────────────────
#
# 재료는 관문이 이미 냈다(`pipeline.parse` → `report["split"]`). 등록 화면은 그것을
# **읽어서 찍을 뿐**이다 — 같은 계산을 다시 하면 두 벌이 되고 한쪽만 고쳐진다.
print("\n■ B68 ② — 분할 줄: 기준 · 레벨 · 크기 분포")

from parser.adapters import basic_prose_xlsx as _bx                 # noqa: E402

reset("b68")
_g68 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "generate",
                       "b68", "quality", str(RAW / "TOC01.xlsx"), str(RAW / "TOC02.xlsx"),
                       "--use-basic", "--allow-mock"],
                      capture_output=True, text=True, cwd=str(ROOT),
                      stdin=subprocess.DEVNULL)
_sl68 = [l for l in _g68.stdout.splitlines() if l.strip().startswith("분할 —")]
# prose 프레임 수 = 표본마다 헤딩이 선 시트 수 — 어댑터의 계산을 그대로 센다.
_frames68 = sum(len(_bx.level_report(reader.read(str(RAW / f))))
                for f in ("TOC01.xlsx", "TOC02.xlsx"))
show("② generate 화면의 분할 줄 수 == prose 프레임 수",
     _sl68 and len(_sl68) == _frames68, f"줄 {len(_sl68)} · 프레임 {_frames68}")
_sp68 = view_of("b68")["sections"]["parse_result"]["summary"]["split"]
show("② 줄의 청크 수 == split_stats의 청크수 (화면이 제 계산을 하지 않는다)",
     _sp68 and all(any(f"청크 {x['청크수']} ·" in l for l in _sl68) for x in _sp68),
     str([x.get("청크수") for x in _sp68]))
show("② 줄이 기준과 레벨을 함께 말한다 (레벨만으로는 무엇을 보고 골랐는지 모른다)",
     all("기준 " in l and "레벨 " in l for l in _sl68), _sl68[:1])
# **status도 같은 줄을 낸다** — 관문을 다시 도니 같은 재료가 있다.
_st68 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "status",
                        "b68", "--allow-mock"], capture_output=True, text=True,
                       cwd=str(ROOT), stdin=subprocess.DEVNULL)
show("② status도 같은 분할 줄을 낸다 (화면 한 벌)",
     [l for l in _st68.stdout.splitlines() if l.strip().startswith("분할 —")] == _sl68)
# **table 어댑터에는 줄이 없다** — 없는 것을 빈 줄로 찍지 않는다.
show("② table 등록에는 분할 줄이 없다",
     not Rgate.split_block((R._state("ipqc") or {}).get("harness_out") or ""))
# 뷰: 레벨 선택 표에 기준 열 하나. **계약이 먼저다**(D-115) — 스키마가 키를 선언한다.
_h68 = (REVIEW / "b68" / "view.html").read_text(encoding="utf-8")
show("② 뷰의 레벨 선택 표에 분할 기준 열이 있고 값이 실린다",
     "<th>분할 기준</th>" in _h68
     and all(x.get("분할_기준") in _h68
             for x in (_sp68[0].get("레벨_선택") or [])), str(_sp68[0].get("레벨_선택"))[:80])
show("② 계약이 먼저다 — 뷰 데이터 스키마가 분할_기준을 선언한다",
     "분할_기준" in (ROOT / "kit/검수뷰_데이터스키마.json").read_text(encoding="utf-8"))
# **위임 래퍼가 제 계산을 이어받는다** — 안 그러면 화면의 레벨·기준이 실제로 자른
# 것과 갈린다(파이프라인의 「어댑터가 제 계산을 내놓으면 그것이 정본이다」).
show("② 고정 어댑터 래퍼가 level_report까지 위임한다",
     "level_report = basic_prose_xlsx.level_report"
     in (REVIEW / "b68" / "adapter.py").read_text(encoding="utf-8"))
reset("b68")

# ── B69 ②③ — 인입 화면: 예고 · 진행 · 끝 · 상한 ─────────────────────────
#
# 등록 리허설에는 관문이 있었고(B22 — 앞 200행 · 기본 끔 · 동의) **운영 인입은
# 뚫려 있었다.** 배치에는 동의 프롬프트가 아니라 예고와 상한이 맞다.
print("\n■ B69 ②③ — 좌표 태깅 예고·진행·상한 (ingest-file · ingest-dir · parse run)")

from cli import parse as _PS                                       # noqa: E402

_ing69 = subprocess.run([sys.executable, str(ROOT / "run.py"), "ingest-file",
                         str(RAW / "CP01.xlsx"), "--doc-type", "cp", "--allow-mock"],
                        capture_output=True, text=True, cwd=str(ROOT),
                        stdin=subprocess.DEVNULL)
_pr69 = subprocess.run([sys.executable, str(ROOT / "run.py"), "parse", "run",
                        str(ROOT / "tests/fixtures/adapters/cp.py"),
                        str(RAW / "CP01.xlsx"), "--allow-mock"],
                       capture_output=True, text=True, cwd=str(ROOT),
                       stdin=subprocess.DEVNULL)
_dir69 = subprocess.run([sys.executable, str(ROOT / "run.py"), "ingest-dir",
                         str(RAW), "--doc-type", "cp", "--allow-mock"],
                        capture_output=True, text=True, cwd=str(ROOT),
                        stdin=subprocess.DEVNULL)


def _coord69(out):
    return [l.strip() for l in out.splitlines() if "좌표 태깅 —" in l]


show("② 세 명령 모두 좌표 태깅을 예고한다 (구판은 인입 갈래에 줄이 0이었다)",
     all(_coord69(r.stdout) for r in (_ing69, _pr69, _dir69)),
     str(_coord69(_ing69.stdout)[:1]))
show("② mock이면 예고가 LLM 0회를 말한다 (부르지 않는다는 사실이 화면에 있다)",
     all("LLM 0회" in l for r in (_ing69, _pr69) for l in _coord69(r.stdout)))
show("② 예고의 숫자가 계약 JSON의 조각 수와 맞는다 (화면이 제 계산을 하지 않는다)",
     f"조각 {len(json.loads(_P.parsed('CP01.json').read_text(encoding='utf-8'))['records']):,}"
     in _coord69(_ing69.stdout)[0], _coord69(_ing69.stdout)[0])
# ③ 상한 손잡이 — 값의 정본은 `cli/parse.py` 상수 하나다.
show("③ --coord-llm off|<종수>가 상한을 정한다 · 기본은 상수 하나",
     _PS.coord_cap_of(["x", "--coord-llm", "off"]) == (["x"], 0)
     and _PS.coord_cap_of(["x", "--coord-llm", "200"]) == (["x"], 200)
     and _PS.coord_cap_of(["x"]) == (["x"], _PS.COORD_CAP),
     f"기본 {_PS.COORD_CAP}")
# 값이 종수도 off도 아니면 **사용법 거부**다 — 조용히 기본으로 떨어지면 사람은
# 상한을 준 줄 안다.
try:
    _PS.coord_cap_of(["x", "--coord-llm", "많이"])
    _bad69 = False
except SystemExit as e:
    _bad69 = "--coord-llm" in str(e)
show("③ 종수도 off도 아닌 값은 예를 보이고 멈춘다 (기본으로 조용히 떨어지지 않는다)",
     _bad69)
# ③ 상한 초과 화면 — **막지 않고 말한다**(B61 계약: 원인 + 칠 수 있는 다음 줄).
_buf69 = _io.StringIO()
_n69, _p69 = _PS.coord_screen()
with _ctx.redirect_stdout(_buf69):
    _n69({"단계": "예고", "조각": 412, "정확_일치": 152, "표기_종수": 137,
          "미스_행": 260, "묻는_종수": 100, "상한": 100, "LLM": True})
    _p69(10, 100, 5)        # 보폭 갱신 — 매 표기 찍으면 그것이 잡음이다
    _n69({"단계": "끝", "호출": 100, "채택": 21, "목록밖": 116})
_scr69 = _buf69.getvalue()
show("③ 상한 초과 화면이 원인과 **그대로 칠 수 있는 다음 줄**을 준다",
     "상한 초과" in _scr69 and "--coord-llm 137" in _scr69
     and "orphan_anchor" in _scr69,
     [l.strip() for l in _scr69.splitlines() if "다음:" in l][:1])
show("② 진행 줄은 표기 단위이고 끝 줄이 채택·목록 밖을 센다",
     "표기 10/100" in _scr69 and "좌표 태깅 끝" in _scr69
     and "채택 21" in _scr69)
for _f69 in ("CP01", "CP02_drift", "CP03_bad", "CP04_unlabeled"):
    (_P.parsed() / f"{_f69}.json").unlink(missing_ok=True)

# ── B72 ① — 어댑터가 내는 키는 등록에서 막는다 (G39) ─────────────────────
#
# 사내 첫 실인입: `ingest-file`이 「스키마에 없는 필드 'meta'」를 **행마다** 찍었다.
# 어댑터가 meta 열들을 딕셔너리 하나로 묶어 냈고 스키마에는 그 키가 없었다.
# 템플릿 규약 7이 그것을 금지하는데 **기계가 재지 않았다** — 등록이 통과시킨 것을
# 인입이 큐로 받았다(사람이 판정할 것도 아닌데).
print("\n■ B72 ① — 산출 키 ⊆ 스키마 fields ∪ 구조 필드 (G39)")

_cpa72 = ROOT / "tests" / "fixtures" / "adapters" / "cp.py"
_cps72 = _P.fixture_schemas("cp.json")
_ok72, _out72 = Rgate.harness(_cpa72, _cps72, [RAW / "CP01.xlsx"])
show("① 정상 쌍은 G39가 초록이다 (지금 자산이 규약 7을 지킨다)",
     "[PASS] G39" in _out72 and "[FAIL] G39" not in _out72,
     [l.strip() for l in _out72.splitlines() if "G39" in l][:1])

# **변이** — meta 열들을 딕셔너리 하나로 묶는 어댑터(사내가 받은 그 산출).
_d72 = REVIEW / "_b72"
_d72.mkdir(parents=True, exist_ok=True)
_mut72 = _d72 / "cpmeta.py"
_src72 = _cpa72.read_text(encoding="utf-8")
_mut72.write_text(_src72.replace(
    "    return fragments",
    '    for f in fragments:\n        f["meta"] = {"개정일": "2026-01-01"}\n'
    "    return fragments", 1), encoding="utf-8")
_okm72, _outm72 = Rgate.harness(_mut72, _cps72, [RAW / "CP01.xlsx"])
_g39 = [(c, l, d) for c, l, d in Rgate.fail_lines(_outm72) if c == "G39"]
show("①ⓑ meta 딕셔너리를 내면 FAIL이고 **그 이름이 문면에 있다**",
     len(_g39) == 1 and "meta" in _g39[0][2],
     _g39[0][2][:70] if _g39 else "G39 FAIL 없음")
show("①ⓑ 문면이 처방을 담는다 — AUTO_FIX 갈래다 (사람의 통역 0)",
     not Rgate.classify_failures(_outm72)[1]
     and any("G39" in a for a in Rgate.classify_failures(_outm72)[0]))
show("①ⓑ 한 태그 한 라벨이다 (원인은 상세가 가른다 — B59 ①)",
     len({l for _c, l, _d in Rgate.fail_lines(_outm72) if _c == "G39"}) == 1)
# **구조 필드는 정본에서 읽는다** — 관문이 제 목록을 들면 pipeline이 자랄 때 갈린다.
import importlib.util as _iu72                                     # noqa: E402
_ra72 = _iu72.module_from_spec(_iu72.spec_from_file_location("ra72", R.KIT / "run_adapter.py"))
_ra72.__spec__.loader.exec_module(_ra72)
from core.build.loop import STRUCTURAL as _ST72                      # noqa: E402
show("① 구조 필드의 정본은 core/build/loop.py다 (관문이 베끼지 않는다)",
     _ra72.structural_fields() == set(_ST72) and _ST72,
     f"{len(_ST72)}종")
shutil.rmtree(_d72, ignore_errors=True)

# ① 템플릿·few-shot — **본보기가 규약과 같은 말을 한다**
_tpl72 = R.generate_template()
show("① 템플릿이 「meta도 role이다 · 딕셔너리로 묶지 마라」를 말한다",
     "meta`도 role이다" in _tpl72 and "묶지 마라" in _tpl72
     and "G39" in _tpl72)
show("① 템플릿 판이 올랐다 (판 번호는 머리말 하나가 말한다 — B63 ①)",
     re.search(r"^version: 1\.7$",
               (ROOT / "prompts" / "1.4_generate.md").read_text(encoding="utf-8"),
               re.M) is not None)
_ref72 = json.loads((R.KIT / "참조어댑터" / "cp.json").read_text(encoding="utf-8"))
_refmod72 = _iu72.module_from_spec(
    _iu72.spec_from_file_location("ref72", R.KIT / "참조어댑터" / "cp.py"))
_refmod72.__spec__.loader.exec_module(_refmod72)
_metaf72 = [k for k, v in _ref72["fields"].items() if v.get("role") == "meta"]
show("① 가장 단순한 few-shot(cp)이 role: meta를 보인다 (LLM이 본보기대로 낸다)",
     len(_metaf72) >= 1, str(_metaf72))
# **B73 ⑤ — B72 ①의 발견이 닫혔다.** `pfmea` 쌍의 `비고` 열이 스키마에 없어
# G39에 걸렸다(의도된 `unknown_field` 재료였다). 허브 판정 ⓐ: role: meta로
# 선언하고 시험 재료는 시험이 심는다 — **자산의 결함에 기댄 재료는 자산을 고칠
# 때마다 시험을 깨뜨린다.** 내장 참조 자산도 관문 대상이다(예외를 두지 않는다).
_pf73, _pfo73 = Rgate.harness(ROOT / "tests/fixtures/adapters/pfmea.py",
                          ROOT / "tests/fixtures/schemas/pfmea.json", [RAW / "PFMEA01.xlsx"])
show("⑤ 내장 참조 쌍(pfmea)도 관문을 통과한다 — 예외를 두지 않는다",
     "[FAIL] G39" not in _pfo73 and _pf73,
     [l.strip() for l in _pfo73.splitlines() if "G39" in l][:1])
show("① few-shot 쌍이 서로 맞는다 — 스키마의 meta 필드를 어댑터도 낸다",
     all(k in (_refmod72.ADAPTER["expects"]["columns"] or {}) for k in _metaf72),
     str(sorted(_refmod72.ADAPTER["expects"]["columns"]))[:70])
# ════════════════════════════════════════════════════════════════════
# B76 ② 대장은 스키마 fields 전부를 덮는다 · ③ 예외는 문면으로 죽는다
# ════════════════════════════════════════════════════════════════════
print("\n■ B76 ② 열 판정 대장 커버리지 (G4G)")

reset("ipqc")
run("generate", "ipqc", "process", str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx"))
_st76 = R._state("ipqc")
_sch76 = json.loads((Rdraft._at(_st76["schema"])).read_text(encoding="utf-8"))
_fld76, _ = R.load_blocks(_sch76)
from run_adapter import structural_fields as _sf76                 # noqa: E402
_struct76 = set(_sf76())
_have76 = {r.get("field") for r in Rledger.read_ledger("ipqc") if r.get("field")}
show("② 스키마 필드 전부에 대장 행이 있다 (구조 필드 제외)",
     all(f in _have76 for f in _fld76 if f not in _struct76),
     str([f for f in _fld76 if f not in _struct76 and f not in _have76]))

# **프로파일 밖 열을 쓰는 어댑터** — 패키지의 열 프로파일에서 한 열을 지운다.
_pkg76 = REVIEW / "ipqc" / "input_package.json"
_pj76 = json.loads(_pkg76.read_text(encoding="utf-8"))
# **구조 필드는 G4G의 대상이 아니다** — 스키마 `fields`가 아니라 블록의 것이다.
_drop76 = next(r["col"] for r in Rledger.read_ledger("ipqc")
               if r.get("field") and r["field"] in _fld76
               and r["field"] not in _struct76)
_field76 = next(r["field"] for r in Rledger.read_ledger("ipqc") if r["col"] == _drop76)
for _h76 in ((_pj76.get("system") or {}).get("reader_head") or []):
    for _pp76 in (_h76.get("열_프로파일") or []):
        (_pp76.get("열") or {}).pop(_drop76, None)
_pkg76.write_text(json.dumps(_pj76, ensure_ascii=False), encoding="utf-8")
Rledger.sync_ledger("ipqc", R._state("ipqc"))
show("② 프로파일 밖 열을 쓰는 어댑터도 대장 행을 갖는다 (합집합으로 돈다)",
     any(r.get("col") == _drop76 and r.get("field") == _field76
         for r in Rledger.read_ledger("ipqc")),
     f"{_drop76}열 · 필드 {_field76}")

# 대장 행을 지우면 G4G가 붉는다 — 사람이 판정한 것이 아니라 기계가 빠뜨린 것이다
_lp76 = Rledger.ledger_path("ipqc")
_save76 = _lp76.read_text(encoding="utf-8")
_led76 = json.loads(_save76)
_led76["columns"] = [r for r in _led76["columns"] if r.get("field") != _field76]
_lp76.write_text(json.dumps(_led76, ensure_ascii=False), encoding="utf-8")
_ok76g, _out76g = Rgate.harness(Rdraft._at(_st76["adapter"]), Rdraft._at(_st76["schema"]),
                            [RAW / "IPQC01.xlsx"], doc_type="ipqc")
_g4g76 = [l.strip() for l in _out76g.splitlines() if "G4G" in l]
show("② 대장에 없는 필드가 있으면 G4G FAIL이고 문면이 그 필드를 말한다",
     _g4g76 and "[FAIL]" in _g4g76[0] and _field76 in _g4g76[0],
     (_g4g76[0] if _g4g76 else "G4G 줄 없음")[:100])
show("② G4G는 재생성으로 고칠 수 없다 — 관문 자체 결함으로 분류된다",
     "G4G" in Rgate.GATE_SELF)
_lp76.write_text(_save76, encoding="utf-8")
_ok76h, _out76h = Rgate.harness(Rdraft._at(_st76["adapter"]), Rdraft._at(_st76["schema"]),
                            [RAW / "IPQC01.xlsx"], doc_type="ipqc")
show("② 대장이 덮으면 G4G PASS (관문이 대장을 만들지 않고 읽는다)",
     "[PASS] G4G" in _out76h)
show("② `role_table`이 어댑터 `columns`를 읽지 않는다 (폴백이 없다 — 둘째 원인)",
     "_led_cols.get(r[\"field\"]) or (" not in
     _reg_src())

# ① 합치기 리스트여도 기계 제안 대조가 돈다(죽지 않는다)
_mod76r = R._load(Rdraft._at(_st76["adapter"]), "p3_b76r")
_two76 = [r for r in Rledger.read_ledger("ipqc") if r.get("field")][:2]
if len(_two76) == 2:
    _rows76 = json.loads(_lp76.read_text(encoding="utf-8"))
    for r in _rows76["columns"]:
        if r.get("col") == _two76[1]["col"]:
            r["field"] = _two76[0]["field"]        # 한 필드가 열 둘 — 합치기 꼴
    _lp76.write_text(json.dumps(_rows76, ensure_ascii=False), encoding="utf-8")
_prof76b = Rledger._profiles("ipqc")
_rt76 = Rledger.role_table(_sch76, _mod76r, R._state("ipqc"), _prof76b)
show("① 한 필드가 열 여럿이어도 `role_table`이 죽지 않고 표를 낸다",
     isinstance(_rt76, list) and _rt76 and all("field" in r for r in _rt76),
     f"{len(_rt76)}행")
_lp76.write_text(_save76, encoding="utf-8")

print("\n■ B76 ③ 등록 흐름의 예외는 문면으로 죽는다")
_dl76 = store.path(store.DEFECTS)
_before76 = _dl76.read_text(encoding="utf-8") if _dl76.exists() else ""
_orig76 = Rconfirm.cmd_list


def _boom76():
    raise TypeError("unhashable type: 'list' (시험 주입)")


Rconfirm.cmd_list = _boom76
_buf76 = _io.StringIO()
with _ctx.redirect_stdout(_buf76):
    _rc76 = Rmain.main(["list"])
Rconfirm.cmd_list = _orig76
_scr76 = _buf76.getvalue()
_after76 = _dl76.read_text(encoding="utf-8") if _dl76.exists() else ""
show("③ 화면은 **한 줄**이고 파일:줄·예외·단계를 말한다",
     _scr76.count("[결함]") == 1 and "단계 list" in _scr76
     and re.search(r"\[결함\] \S+\.py:\d+ · TypeError", _scr76) is not None,
     _scr76.strip().splitlines()[0][:90] if _scr76.strip() else "화면 없음")
show("③ 화면에 traceback이 없다 (사람이 프레임을 읽지 않는다)",
     "Traceback (most recent call last)" not in _scr76)
show("③ traceback 전문은 `defects.log`에 남는다 (조용히 버리지 않는다)",
     "Traceback (most recent call last)" in _after76[len(_before76):]
     and "시험 주입" in _after76[len(_before76):])
show("③ 종료 코드는 상태 거부와 같다", _rc76 == 1, str(_rc76))

_os.environ["ONTO_TRACEBACK"] = "1"
Rconfirm.cmd_list = _boom76
_buf76b = _io.StringIO()
with _ctx.redirect_stdout(_buf76b):
    Rmain.main(["list"])
Rconfirm.cmd_list = _orig76
del _os.environ["ONTO_TRACEBACK"]
show("③ `ONTO_TRACEBACK=1`이면 화면에도 전문이 나온다 (개발용)",
     "Traceback (most recent call last)" in _buf76b.getvalue())

_sys76 = _io.StringIO()
try:
    with _ctx.redirect_stdout(_sys76):
        Rmain.main(["없는명령ZZ"])
    _se76 = "죽지 않았다"
except SystemExit as _e76:
    _se76 = str(_e76)
show("③ 상태 거부·사용법(SystemExit)은 그대로 지난다 (판정은 결함이 아니다)",
     "알 수 없는 명령" in _se76, _se76.splitlines()[0][:60])

done()
