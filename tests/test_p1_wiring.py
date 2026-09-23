# -*- coding: utf-8 -*-
"""P1 ② 배선 — 파서 무판독 · ⑦ 예산 초과 폴백 · 생성 하네스 3단 · 조각 공통 층."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from core.state.bootstrap import coord_layer      # 좌표 층은 묻는다 (B85)


# 이 스위트의 바닥 — 골격 스냅샷이 서 있어야 ⑨좌표 태깅을 잰다(B78 2c)
init.init(fresh_=True)
bootstrap("process", echo=False)

print("\n■ 파서 무판독 — 모드는 진입점이 정하고 파서는 함수 유무만 본다 (문서 7 §7.6-B-1)")
_pyfiles = sorted((ROOT / "parser").rglob("*.py"))
_umock = [f"{p.relative_to(ROOT)}:{i}"
          for p in _pyfiles
          for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
          if "USE_MOCK" in ln]
show(f"파서 {len(_pyfiles)}파일 전수에 USE_MOCK 문자열 0건 (주석·docstring 포함)",
     not _umock, str(_umock[:3]))
_envread = [f"{p.relative_to(ROOT)}:{i}"
            for p in _pyfiles
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "os.environ" in ln and not ln.lstrip().startswith("#")]
show("mock 여부를 환경변수로 정하는 줄 0건 — 판독이 두 곳이면 갈린다(B42 실측)",
     not _envread, str(_envread[:3]))
_smsrc = (ROOT / "parser" / "struct_map.py").read_text(encoding="utf-8")
# 보존 자리는 **주입으로만** 온다(B86 ② — 주입 전 기본값 `KEEP_DIR`은 지웠다).
show("⑤ 운영 코드가 fixture 지도를 찾지 않는다 (MAPS_DIR 삭제 · 보존 자리는 주입으로 별개)",
     "MAPS_DIR" not in _smsrc and "struct_maps" in _smsrc
     and "def keep_dir" in _smsrc and "def use_dir" in _smsrc)
show("④·⑦·⑨가 parse()의 인자로 서 있다 — 함수가 오는 통로가 있다",
     {"summarize", "map_structure", "pick_coord"}
     <= set(pipeline.parse.__code__.co_varnames))
show("⑦의 통로가 apply()까지 이어진다 (파라미터만 있고 값이 올 길이 없으면 배선이 아니다)",
     "ask" in struct_map.apply.__code__.co_varnames
     and "ask=ask" in _smsrc)

# ============================================================ ⑦ 폴백 ([정정] 39)
print("\n■ ⑦ 예산 초과·판정 불가는 문서를 죽이지 않는다 (문서 6 §6.2·§6.3 · D-113 조정)")
from core.llm import check, gateway as _LLM, points, struct_map_pass                                        # noqa: E402
_PPTDOC = str(RAW / "PPT_basic.pptx")


def _map_run(doc_id, reply, limit):
    """실호출 갈래(`struct_map_pass.map_structure`)를 **그대로 태운다** — 가짜는 게이트웨이 응답과
    한도뿐이다. 파서에 주입되는 함수는 운영과 같은 것이라 배선까지 함께 잰다."""
    struct_map.invalidate(doc_id)
    _oc, _ol = _LLM.chat, check.context_limit
    _LLM.chat = lambda *a, **k: reply
    check.context_limit = lambda: limit
    try:
        return pipeline.parse(basic_ppt, doc_id, _PPTDOC, layer=coord_layer(),
                              map_structure=struct_map_pass.map_structure)
    finally:
        _LLM.chat, check.context_limit = _oc, _ol


def _queue_reasons(res):
    return [x for c in (res.envelope or {}).get("chunks", [])
            for x in ((c.get("meta") or {}).get("unresolved_reasons") or [])]


# ⓐ 예산 초과 — 보내지 않되 문서는 산다
_a = _map_run("PPTBUDGET", {"headings": [], "note": None}, 1)
show("ⓐ 예산 초과여도 파싱은 완주한다 (문서 단위 실패가 아니다 — §6.2 폴백)",
     _a.ok and [f["kind"] for f in _a.failures] == ["hierarchy_unresolved"],
     f"ok={_a.ok} · {[f['kind'] for f in _a.failures]}")
show("ⓐ 큐 사유에 「크기 예산 초과」가 실린다 (사람이 왜를 들고 검수 화면에 간다)",
     any("크기 예산 초과" in r for r in _queue_reasons(_a)),
     str(_queue_reasons(_a))[:100])
show("ⓐ 사유 지도는 보존하지 않는다 — 보존하면 재인입이 영영 평면이다",
     not struct_map.keep_path("PPTBUDGET").exists())
show("ⓐ 사유 문면이 **다음 행동**을 낸다 — 귀결 한 줄 + 줄이는 법 두 가지",
     any("평면으로 인입된다" in r and "LLM_CONTEXT_TOKENS가 게이트웨이" in r
         and "시트·슬라이드 단위로 나눠" in r for r in _queue_reasons(_a)),
     str(_queue_reasons(_a))[:80])

# ⓑ 한도를 올리면 다시 시도된다 (ⓐ가 보존을 안 남겼다는 증명)
_b = _map_run("PPTBUDGET", {"headings": [{"row": 1, "level": 1, "title": "제목"}],
                            "note": None}, 10 ** 6)
_kept = json.loads(struct_map.keep_path("PPTBUDGET").read_text(encoding="utf-8")) \
    if struct_map.keep_path("PPTBUDGET").exists() else {}
_maps = list((_kept.get("maps") or {}).values())
show("ⓑ 한도를 올린 재인입에서 실호출 지도가 서고 **보존된다**",
     bool(_maps) and all(m[1].get("source") == "live" and not m[1].get("unavailable")
                         for m in _maps),
     f"보존 프레임 {list((_kept.get('maps') or {}).keys())}")
struct_map.invalidate("PPTBUDGET")

# ⓒ 모델의 「판정 불가」가 큐 사유에 보인다
_c = _map_run("PPTNOTE", {"headings": [], "note": "표 하나로만 된 문서"}, 10 ** 6)
show("ⓒ 헤딩 0건 + 모델 note가 큐 사유 문면에 실린다 (§6.2 「판정 불가로 올린다」)",
     any("모델: 표 하나로만 된 문서" in r for r in _queue_reasons(_c)),
     str(_queue_reasons(_c))[:100])
struct_map.invalidate("PPTNOTE")

# ============================================================ 생성 하네스
print("\n■ 생성 하네스 — 구축 모드 3단 배선 (생성 → 검수 → 확정)")
from cli.parse import cmd_build                              # noqa: E402

rc = cmd_build(["tests/fixtures/fixtures/adapters/ipqc.py", "ipqc_p1",
                str(RAW / "IPQC01.xlsx"), str(RAW / "IPQC02.xlsx")])
outdir = _P.review() / "ipqc_p1"
show("3단이 파일로 이어진다 — 입력 패키지 · 검수 뷰 데이터 · 승인 기록",
     all((outdir / f).exists() for f in
         ("input_package.json", "view.json", "approval.json")))
view = json.loads((outdir / "view.json").read_text(encoding="utf-8"))
show("검수 뷰 **데이터**까지가 P1이다 (HTML 렌더는 P2 — 경계)",
     "samples" in view and not (outdir / "view.html").exists())
show("기계 관문이 검수 앞에 선다 (preflight + 파싱 + self-check 전 표본)",
     rc == 0 and all(s["preflight"] and s["parsed"] for s in view["samples"]))
show("표본 2부면 1부 경고가 뜨지 않는다", not view["warnings"])
cmd_build(["tests/fixtures/fixtures/adapters/ipqc.py", "ipqc_p1_solo", str(RAW / "IPQC01.xlsx")])
solo = json.loads(_P.review("ipqc_p1_solo", "view.json").read_text(encoding="utf-8"))
show("표본 1부면 '변형 미관찰 · 근거 1건일 수 있음' 경고 (D-22 확장 문구)",
     solo["warnings"] and "근거 1건" in solo["warnings"][0])
appr = json.loads((outdir / "approval.json").read_text(encoding="utf-8"))
show("확정은 승인 기록까지 — registry 등재는 P3의 몫이다 (경계 침범 0)",
     appr["machine_gate"] == "PASS" and appr["approved_by"] is None
     and "ipqc_p1" not in store.read(store.REGISTRY, {}))
shutil.rmtree(_P.review() / "ipqc_p1", ignore_errors=True)
shutil.rmtree(_P.review() / "ipqc_p1_solo", ignore_errors=True)

# ============================================================ 조각 공통 층 (§2.2 계약 ①)
print("\n■ 조각 공통 층 — 모든 record/chunk가 달고 들어온다 (문서 2 §2.2)")
import importlib.util as _iu                                    # noqa: E402
_s = _iu.spec_from_file_location("_bp", ROOT / "parser/adapters/basic_ppt.py")
_bp = _iu.module_from_spec(_s); _s.loader.exec_module(_bp)
_r = pipeline.parse(_bp, "PPTXCOMMON",
                     str(ROOT / "tests/fixtures/raw/PPT_basic.pptx"),
                     layer=coord_layer())
_COMMON = {"source_locator", "doc_type", "process_group", "process_ref",
           "electrode_type"}
show("기본 어댑터 산출도 조각 공통 5키를 전부 갖는다 (값 null 허용·키 부재 금지)",
     _r.ok and all(_COMMON <= set(c) for c in _r.envelope["chunks"]),
     str(sorted(_COMMON - set(_r.envelope["chunks"][0]))) if _r.ok else str(_r.failures))
show("validator가 조각 공통 키 부재를 잡는다 (§6.2-5 「좌표 존재」)",
     not validator.check({"doc_id": "X", "doc_type": "t", "payload_kind": "prose",
                          "source_path": "x", "revision": "R1",
                          "parsed_at": "t", "parser_version": "p",
                          "adapter_version": "a",
                          "chunks": [{"source_locator": "X-1", "text": "가"}]})[0])

# ⑨좌표 태깅의 mock 갈래는 **모델을 부르지 않는다** (조항 B12 · §7.1 대체 표)
_calls = []
from core.llm import check, gateway as _LLM, points, struct_map_pass                                    # noqa: E402
for _n in ("chat", "require", "_post"):
    _o = getattr(_LLM, _n)
    setattr(_LLM, _n, (lambda *a, _x=_n, _f=_o, **k: (_calls.append(_x), _f(*a, **k))[1]))
_nodes = tagger.closed_list("process")
_tagged = tagger.tag([{"source_locator": "T-1", "process_ref": "노칭"},
                      {"source_locator": "T-2", "process_ref": "없는공정zzz"}],
                     layer="process", nodes=_nodes, pick=points.coord_picker())
show("⑨좌표 태깅 mock 갈래가 모델을 부르지 않는다 (조항 B12)", not _calls, str(_calls))
show("⑨목록 밖 좌표는 값을 고치지 않고 그대로 둔다 (판정은 인입 소관)",
     _tagged[1]["process_ref"] == "없는공정zzz"
     and _tagged[0]["process_group"] == "조립")

# ============================================================ CSV reader (2B 신설)
# **CSV는 xlsx와 같은 구조를 낸다** — 어댑터가 포맷을 몰라도 되게(요청 §2-1).
# `format`만 "csv"로 갈라 거짓말을 하지 않는다.

done()
