# -*- coding: utf-8 -*-
"""P3 ③ 관문 — 스키마 strict · 오류 본문 · 분할 레벨 · mock 관문 · --resume."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src            # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

from core.llm import gateway

setup()


print("\n■ B43·B44 — 스키마 strict · 오류 본문 · 분할 레벨 · section 좌표")
import importlib as _il                                             # noqa: E402
from parser import struct_map as _SM, tagger as _TG                 # noqa: E402


def _strict(s, path="$"):
    """구조화 출력의 strict 요건 — 모든 object에서 properties == required ·
    additionalProperties is False · **자유 키 사전 없음**."""
    bad = []
    if isinstance(s, dict):
        if s.get("type") == "object" or "properties" in s:
            if set(s.get("properties") or {}) != set(s.get("required") or []):
                bad.append(f"{path}: properties != required")
            ap = s.get("additionalProperties")
            if ap is not False:
                bad.append(f"{path}: additionalProperties={ap!r}"
                           + (" (자유 키 사전)" if isinstance(ap, dict) else ""))
        for k, v in (s.get("properties") or {}).items():
            bad += _strict(v, f"{path}.{k}")
        if "items" in s:
            bad += _strict(s["items"], f"{path}[]")
    return bad


# ① **코드의 전 json_schema**를 훑는다 — 하나라도 어기면 그 지점이 400으로 죽는다
_schemas = []
for _m in ("cli.register", "cli.query", "core.query", "core.llm", "core.matcher"):
    _mod = _il.import_module(_m)
    for _n in dir(_mod):
        if _n.endswith("_SCHEMA") and isinstance(getattr(_mod, _n), dict):
            _schemas.append((f"{_m}.{_n}", getattr(_mod, _n)))
_viol = [(n, b) for n, s in _schemas for b in [_strict(s, n)] if b]
show(f"① 전 구조화 출력 스키마 {len(_schemas)}종이 strict 요건을 지킨다",
     not _viol, str(_viol))
show("① 자유 키 사전이 0건이다 (role_counts는 고정 키)",
     Rdraft.GENERATE_SCHEMA["properties"]["role_counts"]["additionalProperties"] is False
     and set(Rdraft.GENERATE_SCHEMA["properties"]["role_counts"]["properties"]) == set(Rdraft._ROLES))
show("① 못 채울 수 있는 필드는 required에서 빼지 않고 null을 연다",
     Rdraft.GENERATE_SCHEMA["properties"]["confidence_cut"]["type"] == ["integer", "null"]
     and "confidence_cut" in Rdraft.GENERATE_SCHEMA["required"])
show("① 한글 키 `근거`가 `reason`으로 바뀌었다 (소비처 포함)",
     Rdraft.GENERATE_SCHEMA["properties"]["attribute_ranking"]["items"]["required"]
     == ["field", "rank", "reason"])

# ② 오류 본문 보존 — 키는 남기지 않는다
show("② GatewayError가 상태 코드와 본문을 지닌다",
     hasattr(gateway, "GatewayError") and hasattr(gateway, "LAST_ERROR")
     and "e.read()" in (ROOT / "core/llm/gateway.py").read_text(encoding="utf-8"))
show("② 4xx는 재시도하지 않는다 (같은 400을 세 번 받지 않는다)",
     "except GatewayError:" in (ROOT / "core/llm/gateway.py").read_text(encoding="utf-8"))
show("② 본문은 길이 상한으로 자른다", isinstance(gateway.ERR_BODY_MAX, int))

# ③ 분할 레벨 — 결정적이고 근거가 지도에 남는다
def _mk(fine):
    ls, n = [], 0
    for i in range(3):
        n += 1; ls.append((n, f"{i+1}. 대절"))
        if fine:
            for k in range(4):
                n += 1; ls.append((n, f"{i+1}.{k+1} 소절"))
                for j in range(2):
                    n += 1; ls.append((n, f"본문{i}{k}{j}"))
        else:
            for j in range(12):
                n += 1; ls.append((n, f"본문{i}{j}"))
    return ls


def _rows(ls):
    out = []
    for n, x in ls:
        h = x[0].isdigit() and "." in x.split()[0]
        out.append({"row": n, "heading": h,
                    "level": (x.split()[0].rstrip(".").count(".") + 1) if h else 0})
    return out


_fine = _mk(True)
_smap = {"rows": _rows(_fine)}
_st43 = _SM.level_stats(_smap, _fine)
# **[정정] 46이 규칙을 바꿨다** — 「구간에 가장 많이 드는 레벨」에서 「구간 안의
# 레벨 중 중앙 최근접」으로. 돌려주는 것도 `(레벨, 사유, 구간밖)` 3짝이다.
_pick, _why, _oor = _SM.choose_level(_st43)
_loc = lambda a, b: f"L{a}-{b}"
_before = len(_SM.split({"rows": _smap["rows"], "분할_레벨": None}, _fine, _loc))
_after = len(_SM.split({**_smap, "분할_레벨": _pick}, _fine, _loc))
show("③ 레벨별 분포를 센다 (청크 수·행 수)",
     set(_st43) == {1, 2} and _st43[2]["청크수"] > _st43[1]["청크수"], str(_st43))
show("③ 구간 중앙에 평균이 가장 가까운 레벨을 고른다 ([정정] 46)",
     _pick == 1 and not _oor, f"{_pick} — {_why}")
show("③ 세밀 헤딩에서 청크가 합쳐진다 (부서지지 않는다)",
     _before == 12 and _after == 3, f"{_before} → {_after}")
_coarse = _mk(False)
_p2, _w2, _oor2 = _SM.choose_level(_SM.level_stats({"rows": _rows(_coarse)}, _coarse))
# **레벨이 하나뿐이어도 그 레벨을 고른다** — 자르는 결과는 전 헤딩 분할과 같지만
# (`l <= pick`이 전부를 포함한다), 구간 밖이면 그 사실이 화면·큐로 나가야 한다.
# 구판은 여기서 `None`을 돌려줘 「고르지 않았다」로 남았고, 그러면 구간 밖 표시도
# 함께 사라졌다.
show("③ 레벨이 하나뿐이면 그 레벨을 고른다 — 분할 결과는 같고 구간밖은 드러난다",
     _p2 == 1
     and len(_SM.split({"rows": _rows(_coarse), "분할_레벨": _p2}, _coarse, _loc))
     == len(_SM.split({"rows": _rows(_coarse), "분할_레벨": None}, _coarse, _loc)),
     f"{_p2} · 구간밖={_oor2} — {_w2[:40]}")
show("③ 선택 근거가 지도에 보존된다 (같은 지도 → 같은 분할)",
     "분할_레벨" in _SM.apply("T43", _fine, _loc)[1]
     and "레벨_분포" in _SM.apply("T43", _fine, _loc)[1])
show("③ 목표 구간은 가결정 상수다 (D-106)",
     isinstance(_SM.CHUNK_MIN, int) and isinstance(_SM.CHUNK_MAX, int))

# ④ section 좌표 — 정확 일치만·가장 깊은 것·덮지 않음
_nodes = _TG.closed_list("process")
_out = _TG.coord_from_section(
    [{"section": "조립 > 노칭 > 노칭 타발", "source_locator": "S1"},
     {"section": "없는절 > 또없는절", "source_locator": "S2"},
     {"section": "조립 > 노칭", "process_ref": "스태킹", "source_locator": "S3"}],
    layer="process", nodes=_nodes)
show("④ 경로에 일치가 여럿이면 **가장 깊은 것**", _out[0]["process_ref"] == "노칭 타발")
show("④ 일치 없으면 비운다 (추론·문자열 파싱 금지)",
     not _out[1].get("process_ref"))
show("④ 이미 값이 있으면 덮지 않는다", _out[2]["process_ref"] == "스태킹")
show("④ 대조는 좌표 태깅과 **같은 연산**을 재사용한다 (새로 짜지 않았다)",
     "surfaces(nodes)" in (ROOT / "parser/tagger.py").read_text(encoding="utf-8"))

# ⑤⑥ resume · 진행 · 근거
_src5 = _reg_src()
_src5i = (ROOT / "cli/interview.py").read_text(encoding="utf-8")   # 문답은 제 모듈로 갔다
show("⑤ --resume이 사용법과 파싱에 있다",
     "--resume" in _src5 and "resume=resume" in _src5)
show("⑤ 문답이 라운드마다 즉시 저장된다 (중간에 죽어도 잃지 않는다)",
     "on_round(history)" in _src5i)
show("⑥ 문답 스키마가 진행 재료와 중요도를 요구한다",
     "progress" in R.INTERVIEW_SCHEMA["required"]
     and "importance" in R.INTERVIEW_SCHEMA["properties"]["questions"]["items"]["required"])
show("⑥ 판정 근거(프로파일)를 사람 화면에도 낸다", "_prof_hint(pkg)" in _src5i)

# ============================================================ B45 분할 분포
print("\n■ B45 — 분할 크기 분포를 검수 뷰에 (자르는 규칙은 안 건드린다)")
run("generate", "toc_report", "process", str(RAW / "TOC01.xlsx"),
    str(RAW / "TOC02.xlsx"), "--hint", "목차형")
run("review", "toc_report")
_v45 = view_of("toc_report")
_sp = (_v45["sections"]["parse_result"]["summary"] or {}).get("split") or []
show("① 분포가 뷰 데이터에 실린다 (표본마다 1건)", len(_sp) == 2, str(len(_sp)))
show("① 청크 수·행수(최소·최대·평균)·목표 구간 밖(짧음/긺)이 전부 있다",
     all(k in _sp[0] for k in ("청크수", "행수_최소", "행수_최대", "행수_평균",
                               "목표구간", "너무_짧은_청크", "너무_긴_청크")),
     str({k: _sp[0][k] for k in ("청크수", "행수_평균", "너무_짧은_청크")}))
show("① 상수가 부적절하면 화면에 드러난다 (한 줄짜리 청크가 짧음으로 집계)",
     _sp[0]["너무_짧은_청크"] > 0,
     f"{_sp[0]['doc_id']}: 짧음 {_sp[0]['너무_짧은_청크']}/{_sp[0]['청크수']}")
_html45 = (REVIEW / "toc_report" / "view.html").read_text(encoding="utf-8")
show("② 렌더러는 **그리기만** 한다 (계산은 산출자 · §6.6-3)",
     "분할 크기 분포" in _html45
     and "너무_짧은_청크" not in (ROOT / "kit/render_review.py").read_text(
         encoding="utf-8").split("def _split")[1].split("return")[0].replace(
         'r.get("너무_짧은_청크")', ""))
show("② 구획 1의 3층 계약을 지킨다 (split은 summary 안이다 — D-79)",
     set(_v45["sections"]["parse_result"]) == {"summary", "anomalies", "normal"})
# ⓑ 어댑터 경로는 바뀌지 않는다 — 고를 레벨이 없기 때문이다(B45 판정)
_ref45 = [x for x in _il.import_module("tests.fixtures.fixtures.adapters.toc_report")
          .extract(reader.read(str(RAW / "TOC01.xlsx"))) if "text" in x]
show("③ 어댑터 경로 산출은 바뀌지 않는다 (굵기 교정의 정본은 어댑터 개정)",
     len(_ref45) == 9, f"TOC01 어댑터 청크 {len(_ref45)}")

# ============================================================ B45 정정
print("\n■ B45 정정 — 어댑터 경로에도 분할 레벨 상수 (판정이 뒤집혔다)")
import importlib.util as _iu45                                      # noqa: E402


def _load45(path, name):
    s = _iu45.spec_from_file_location(name, ROOT / path)
    m = _iu45.module_from_spec(s); s.loader.exec_module(m); return m


_old45 = _load45("tests/fixtures/fixtures/adapters/toc_report.py", "t45o")  # 스냅샷
_new45 = _load45("kit/참조어댑터/toc_report.py", "t45n")                      # 전시물
# **[정정] 46이 판단 상수를 폐지했다** — 구판 전시물은 `expects.split_level=1`을
# 박고 「결정은 등록 때 한 번」이라 적었다. 지금 전시물은 규칙을 부른다.
show("① 전시물에 분할 레벨 상수가 없다 ([정정] 46 — 레벨은 인입마다 규칙이 센다)",
     "split_level" not in _new45.ADAPTER["expects"]
     and "split_level" not in _old45.ADAPTER["expects"])
show("① 전시물이 규칙을 **부른다** (재구현하지 않는다 — 규약 10과 같은 결)",
     "struct_map.choose_level(" in
     (ROOT / "kit" / "참조어댑터" / "toc_report.py").read_text(encoding="utf-8"))


def _d45(mod, doc):
    ch = [x for x in mod.extract(reader.read(str(RAW / f"{doc}.xlsx")))
          if "text" in x]
    sz = [len(x["text"].split("\n")) for x in ch]
    return ch, len(ch), sum(1 for s in sz if s < _SM.CHUNK_MIN)


_a01, _n01, _s01 = _d45(_old45, "TOC01")
_b01, _m01, _t01 = _d45(_new45, "TOC01")
show("ⓐ 규칙이 고른 레벨에서만 자른다 — 청크가 굵어진다",
     _m01 < _n01 and _t01 < _s01, f"청크 {_n01}→{_m01} · 짧음 {_s01}→{_t01}")
show("ⓑ 규칙을 부르지 않는 구판 스냅샷은 종전 동작 그대로다 (전 헤딩 분할)",
     _n01 == 9, f"{_n01}")
show("ⓒ 산출 유실 0 — 내용이 하나도 새지 않는다",
     not [x for x in _a01 if x["text"] not in "\n".join(y["text"] for y in _b01)])
show("ⓒ `section` 경로는 상수와 무관하게 전 헤딩을 반영한다 (좌표 파생의 재료)",
     max(len(x["section"].split(" > ")) for x in _b01) == 3,
     f"최대 깊이 {max(len(x['section'].split(' > ')) for x in _b01)}단")
show("④ 어댑터 경로도 레벨별 분포를 낸다 (지도 경로와 같은 형태)",
     (lambda r: bool((r.report.get("split") or {}).get("레벨_선택")))(
         pipeline.parse(_new45, "T45", str(RAW / "TOC01.xlsx"))))
# **화면이 「규칙이 고른 레벨」을 밝힌다**(§6.6-1) — 구판은 여기서
# `expects.split_level=1`이라는 **폐지된 상수**를 찍었다. 사유가 상수를 가리키면
# 승인자는 규칙이 무엇을 골랐는지 끝내 못 본다.
_pk45 = pipeline.parse(_new45, "T45", str(RAW / "TOC01.xlsx")
                       ).report["split"]["레벨_선택"][0]
show("④ 화면이 규칙이 고른 레벨과 그 사유를 밝힌다 (폐지된 상수를 읽지 않는다)",
     _pk45["분할_레벨"] == 1 and "구간" in _pk45["분할_레벨_사유"]
     and _pk45["분할_레벨_구간밖"] is False
     and "split_level=" not in str(_pk45),
     _pk45["분할_레벨_사유"][:44])
# **같은 doc_type의 다른 판본이 갈린다** — 상수를 버린 근거가 바로 이것이다.
_pk46 = pipeline.parse(_new45, "T46", str(RAW / "TOC02.xlsx")
                       ).report["split"]["레벨_선택"][0]
show("④ 같은 어댑터의 다른 판본이 갈린다 (상수를 버린 근거 — [정정] 46)",
     _pk46["분할_레벨_구간밖"] is True and _pk45["분할_레벨_구간밖"] is False,
     f"TOC01 구간내 · TOC02 {_pk46['분할_레벨_사유'][:30]}")
show("fixture는 손대지 않았다 (D-26)", "split_level" not in
     (ROOT / "tests/fixtures/fixtures/adapters/toc_report.py").read_text(
         encoding="utf-8"))

# ============================================================ 등록개선 5건 (②·③·⑤)
print("\n■ 등록개선 — ② --use-basic · ③ 확정 안내 · ⑤ 문답 번호 선택지")
import contextlib as _ctx                                           # noqa: E402
import io as _io                                                    # noqa: E402
from cli import interview as _IV                                    # noqa: E402
from core.state import registry as _REG                                   # noqa: E402
_PPT = str(ROOT / "tests/fixtures/raw/PPT_basic.xlsx").replace(".xlsx", ".pptx")
# ② 거부 — 제안이 서지 않는 표본(정형)
try:
    Rgen.cmd_generate("cpx_basic", "process", [str(RAW / "CP01.xlsx")], use_basic=True)
    show("② 제안 없는 표본에 --use-basic은 거부된다", False)
except SystemExit as e:
    # **문면을 세지 않는다** — 잠글 성질은 「거부 + 사유(어느 표본) + 다음 줄」이다.
    # 계열 이름을 박으면 계열이 늘 때(B58 ③이 격자 산문을 더했다) 이 줄이 깨진다.
    show("② 제안 없는 표본에 --use-basic은 거부되고 사유를 말한다",
         "거부" in str(e) and "CP01.xlsx" in str(e) and "--no-basic" in str(e))
show("② 거부는 검수 자리를 만들지 않는다", not (_P.review() / "cpx_basic").exists())
# ② 수용 — PPT 표본: LLM 호출 0회로 생성 → 검수 → 확정
_calls0 = gateway.usage_total()["calls"]
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    Rgen.cmd_generate("pptb_t", "quality", [_PPT], use_basic=True)
_gen = _buf.getvalue()
show("② --use-basic — 위임 래퍼 어댑터가 검수 자리에 선다 (상수는 basic_ppt 한 곳 — D-111)",
     "from parser.adapters import basic_ppt" in _P.review("pptb_t", "adapter.py").read_text(encoding="utf-8")
     and "max_chars" not in _P.review("pptb_t", "adapter.py").read_text(encoding="utf-8"))
show("② 매칭 스키마는 prose 계약 — fields {} · layer 선언",
     (lambda s: s["fields"] == {} and s["layer"] == "quality" and s["doc_type"] == "pptb_t")(
         json.loads(_P.review("pptb_t", "schema.json").read_text(encoding="utf-8"))))
show("② 화면이 «호출 0회»를 말한다 (사용량으로 증명)", "호출 0회" in _gen)
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    Rview.cmd_review("pptb_t", llm_coord=False)
show("② 검수·승인 1회는 생략하지 않는다 — 기계 관문 PASS가 확정의 전제 (M4)",
     R._state("pptb_t").get("machine_gate") == "PASS", str(R._state("pptb_t").get("machine_gate")))
show("② 생성+검수 동안 LLM 호출 0회 (usage_total 불변)",
     gateway.usage_total()["calls"] == _calls0, f"{_calls0} → {gateway.usage_total()['calls']}")
_buf = _io.StringIO()
with _ctx.redirect_stdout(_buf):
    Rconfirm.cmd_confirm("pptb_t", "테스트")
_conf = _buf.getvalue()
show("② 확정 — 등록부 등재 + adapters/·schemas/ 정본",
     _REG.lookup("pptb_t") is not None and _P.adapters("pptb_t.py").exists()
     and _P.schemas("pptb_t.json").exists())
# ③ 확정 화면의 「다음」 = 가이드가 시키는 인입 흐름 (B66 ③)
#
# 구판은 화면에 있는 **명령 이름**(`parse run` · `build parsed/`)을 셌다. 문면은 한
# 글자만 바꿔도 통과하고, 그 셋은 가이드 §4·§5에 없는 명령이라 사내에서 「가이드에
# 없는 명령」으로 읽혔다. 잠글 성질은 **사람이 그대로 칠 수 있는 인입 줄을 방금
# 확정한 doc_type으로 준다**이지 어느 명령이 적혀 있느냐가 아니다.
_next3 = [l.strip() for l in _conf.splitlines() if "run.py ingest-file" in l]
show("③ 확정 화면이 인입 줄을 준다 — 방금 확정한 doc_type이 박혀 있고 먼저 보는 줄이 있다",
     len(_next3) >= 2 and all("--doc-type pptb_t" in l for l in _next3)
     and any("--dry-run" in l for l in _next3), str(_next3))
# 정리 — 회귀가 남기는 것 0
_REG.unregister("pptb_t")
for _p in (_P.adapters("pptb_t.py"), _P.schemas("pptb_t.json")):
    _p.unlink(missing_ok=True)
shutil.rmtree(_P.review("pptb_t"), ignore_errors=True)
shutil.rmtree(_P.review("cpx_basic"), ignore_errors=True)
# ⑤ 번호 선택지
_opts = ["위 값 채움", "행 독립", "모름"]
show("⑤ 번호만 쳐도 통한다 — «1» → 첫째", _IV._pick_option("1", _opts) == "위 값 채움")
show("⑤ 문장으로 써도 통한다 — «2번으로 진행» → 둘째", _IV._pick_option("2번으로 진행", _opts) == "행 독립")
show("⑤ «3)»·«3.» 표기도", _IV._pick_option("3)", _opts) == "모름" and _IV._pick_option("3.", _opts) == "모름")
show("⑤ 범위 밖·비번호는 문장 그대로 (None)", _IV._pick_option("9", _opts) is None
     and _IV._pick_option("병합은 위 값", _opts) is None)
show("⑤ 중요도 정렬 — 높음이 앞", [q["q"] for q in sorted(
    [{"q": "b", "importance": "낮음"}, {"q": "a", "importance": "높음 — 좌표"}, {"q": "c"}], key=_IV._rank)] == ["a", "b", "c"])
_feed = iter(["1", "", "진행"])
_orig_ask = _IV._ask
_IV._ask = lambda prompt="": next(_feed)
_buf = _io.StringIO()
# 패키지는 최소형 — 문답 화면·번호 풀이를 재는 것이지 관찰 재료를 재는 것이 아니다
_pkg = {"human": {"doc_type": "ivx", "layer": "quality", "samples": [], "hint": ""},
        "system": {"reader_head": [], "skeleton_closed_list": {}, "layer_vocabulary": {},
                   "blocks": {}, "adapter_skeleton": ""}}
with _ctx.redirect_stdout(_buf):
    _hist = _IV._interview(_pkg)
_IV._ask = _orig_ask
_scr = _buf.getvalue()
show("⑤ 화면 — 질문마다 구분선 + 번호 선택지 «1) …  2) …»", "─" in _scr and "1) " in _scr and "2) " in _scr)
show("⑤ 번호 답이 선택지 본문으로 풀려 기록된다 (모델은 «1»이 무엇인지 모른다)",
     _hist[0]["answers"][0]["answer"] == "1" and _hist[0]["answers"][0]["chosen"] == _hist[0]["questions"][0]["options"][0]
     and _hist[0]["questions"][0]["options"][0] in _hist[0]["answer"])
show("⑤ «진행»은 어느 자리에서든 종료다 — 라운드 2에서 멈춤", len(_hist) == 2)

# ============================================================ mock 관문 (B48 ③)
print("\n■ mock 관문 — 운영 명령은 mock에서 실행 전에 멈춘다 (문서 7 §7.6-B-1)")
from cli import _gate as _G                                         # noqa: E402
_bare = subprocess.run([sys.executable, "-m", "cli.register", "generate", "gate_t", "process"],
                       capture_output=True, text=True, cwd=str(ROOT))
show("③ 설정 없이 register generate → 종료 코드 ≠ 0", _bare.returncode != 0, str(_bare.returncode))
show("③ 문면이 --allow-mock과 켜는 법을 함께 말한다",
     "--allow-mock" in _bare.stdout and "실산출이 아닙니다" in _bare.stdout
     and "USE_MOCK" in _bare.stdout, _bare.stdout.strip().splitlines()[-1:][0][:70]
     if _bare.stdout.strip() else "(빈 출력)")
show("③ 모드 표시 다음에 멈춘다 (B42 ⑤ → 관문)", "모드:" in _bare.stdout)
show("③ 멈춘 명령은 아무것도 만들지 않았다 — LLM 지점 호출 0회",
     not (_P.review() / "gate_t").exists())
_allowed = run("generate", "gate_t", "process", str(RAW / "CP01.xlsx"))
show("③ --allow-mock을 붙이면 종전대로 진행한다",
     (_P.review() / "gate_t" / "input_package.json").exists(), _allowed.stdout[-80:])
shutil.rmtree(_P.review() / "gate_t", ignore_errors=True)
for _c in ("init", "bootstrap"):
    _r = subprocess.run([sys.executable, str(ROOT / "run.py"), _c],
                        capture_output=True, text=True, cwd=str(ROOT))
    show(f"③ {_c}은 관문 비대상 — 플래그 없이 종전대로", _r.returncode == 0, str(_r.returncode))
show("③ 관문 대상 목록이 코드에 있다 — register는 생성·검수·확정만(열람은 아니다)",
     Rconfirm.GATED == ("generate", "review", "confirm"))
# **관문의 자리는 CLI 진입점이다**(§7.6-B-1) — 지점마다 두면 판독처가 다시 여럿이
# 되고, 그것이 판정필요-15가 신고한 병(파서가 따로 읽어 갈렸다)의 재발이다.
_gcalls = [f"{f.relative_to(ROOT)}:{i}"
           for f in [ROOT / "run.py", *sorted((ROOT / "cli").rglob("*.py")),
                     *sorted((ROOT / "core").rglob("*.py")),
                     *sorted((ROOT / "parser").glob("*.py"))]
           for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if "require_live_or_allow(" in ln and "def " not in ln
           and not ln.lstrip().startswith(("#", "from", "import"))]
show("③ 관문 호출은 CLI 진입점 4곳뿐이다 — core·parser에는 없다",
     len(_gcalls) == 4 and not any(g.startswith(("core/", "parser/")) for g in _gcalls),
     str(_gcalls))

# ============================================================ --resume 인자 (후속 ①)
print("\n■ --resume은 층·표본을 요구하지 않는다 (실사용 IndexError 수리)")
_r1 = run("generate", "toc_report", "--resume")
show("① doc_type 하나로 돈다 (IndexError 0)",
     _r1.returncode == 0 and "이어하기" in _r1.stdout, _r1.stderr.strip()[-70:])
_r2 = run("generate", "toc_report", "quality", str(RAW / "TOC01.xlsx"), "--resume")
show("① 층·표본을 줘도 돌고, 무시한다는 경고가 뜬다 (침묵으로 넘기지 않는다)",
     _r2.returncode == 0 and "층·표본 인자는 무시한다" in _r2.stdout
     and "layer=" in _r2.stdout,
     [l for l in _r2.stdout.splitlines() if "무시한다" in l][:1])
_r3 = run("generate")
show("① 위치 인자 0개면 죽지 않고 사용법을 낸다",
     "generate <doc_type>" in (_r3.stdout + _r3.stderr))
show("① 사용법에 resume 단독 줄이 있다",
     "generate <doc_type> --resume" in _reg_src())

# ============================================================ B49 전 열 판정
print("\n■ B49 — 모든 열은 판정을 갖는다 (C19 개정 · 부재로 추론하지 않는다)")
_DEMO = _P.review() / "b49demo"
_DEMO.mkdir(parents=True, exist_ok=True)
(_DEMO / "adapter.py").write_text(
    '# -*- coding: utf-8 -*-\n'
    'ADAPTER = {"doc_type": "b49demo", "adapter_version": "1.0", "payload_kind": "table",\n'
    '           "expects": {"header_row": 1,\n'
    '                       "header_labels": ["공정명", "규격", "비고", "최근 불량 이력", "신규 열"],\n'
    '                       "columns": {"process_ref": "A", "규격": "B"}}}\n'
    'def extract(raw):\n    return []\n', encoding="utf-8")
_dsch = {"doc_type": "b49demo", "schema_version": 1, "layer": "quality",
         "payload_kind": "table", "use_blocks": [],
         "fields": {"규격": {"role": "attribute", "attr_name": "규격",
                           "attach_to_field": "process_ref"}},
         "edges": [],
         "unmappable": [
             {"field": "최근 불량 이력", "kind": "excluded",
              "reason": "집계 이력 — 개체도 값도 아니고 시점마다 바뀐다"},
             {"field": "비고", "kind": "undecided",
              "reason": "표본 3부 전부 비어 있어 무엇이 오는지 관찰되지 않았다"}]}
(_DEMO / "schema.json").write_text(json.dumps(_dsch, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
_dst = {"doc_type": "b49demo", "layer": "quality",
        "samples": [str(RAW / "IPQC01.xlsx")],
        "adapter": "review/b49demo/adapter.py", "schema": "review/b49demo/schema.json"}
_dmod = R._load(Rdraft._at(_dst["adapter"]), "reg_b49demo_t")
_ex, _un, _orp = Rledger.unmappable_of(_dsch, _dmod)
show("① 셋으로 갈린다 — excluded · undecided · orphan (구판은 셋이 같은 질문이었다)",
     [u["field"] for u in _ex] == ["최근 불량 이력"]
     and [u["field"] for u in _un] == ["비고"]
     and [u["field"] for u in _orp] == ["신규 열"],
     f"{[u['field'] for u in _ex]} / {[u['field'] for u in _un]} / {[u['field'] for u in _orp]}")
_dv = Rview.build_view(_dst, [], True, "")
_dpr = _dv["sections"]["parse_result"]
show("① excluded는 anomalies에 0건이다 — 판정이 끝난 열은 질문이 아니다",
     not [a for a in _dpr["anomalies"] if "최근 불량 이력" in a["message"]]
     and [u["field"] for u in _dpr["normal"]["excluded"]] == ["최근 불량 이력"])
show("① undecided는 question이다 — 사유가 문면에 실린다",
     any(a["kind"] == "question" and "'비고'" in a["message"]
         and "표본 3부 전부 비어" in a["message"] for a in _dpr["anomalies"]))
show("① orphan은 failure다 — 「사람이 판정할 것」이 아니라 「대장이 어긋났다」",
     any(a["kind"] == "failure" and "'신규 열'" in a["message"]
         and "스키마 대장에 없다" in a["message"] for a in _dpr["anomalies"]))
show("① 배정표(6지선다)에는 undecided만 오른다",
     [r["field"] for r in _dv["sections"]["role_table"] if r.get("role") == "UNMAPPABLE"]
     == ["비고"])
show("① orphan이 있으면 기계 관문이 막힌다 (하네스·파싱이 통과여도)",
     Rledger.gate_verdict(True, True, _orp) == "FAIL"
     and Rledger.gate_verdict(True, True, []) == "PASS")
_legacy = {**_dsch}
del _legacy["unmappable"]
_lex, _lun, _lorp = Rledger.unmappable_of(_legacy, _dmod)
show("① 구판 스키마(키 없음)는 차집합 전량을 undecided로 — 기존 등록분이 안 깨진다",
     not _lex and not _lorp
     and sorted(u["field"] for u in _lun) == sorted(
         ["비고", "신규 열", "최근 불량 이력"]),
     str([u["field"] for u in _lun]))
show("① kind가 닫힌 2값 밖이면 undecided로 받는다 (모르면 묻는다)",
     Rledger.unmappable_of({**_dsch, "unmappable": [{"field": "X", "kind": "몰라", "reason": ""}]},
                     _dmod)[1][0]["kind"] == "undecided")
show("① 생성 스키마가 unmappable을 required로 요구한다 (strict — B44)",
     "unmappable" in Rdraft.GENERATE_SCHEMA["required"]
     and Rdraft.GENERATE_SCHEMA["properties"]["unmappable"]["items"]["properties"]["kind"]
     ["enum"] == ["excluded", "undecided"])
# **판 번호를 박지 않는다**(B63 ① — 지시문은 이제 한 판이다). 잠글 성질은 그대로다:
# 「쓰지 않기로 한 열」을 스키마에 싣도록 지시문이 말한다.
show("① 생성 지시문이 UNMAPPABLE을 스키마에 싣도록 지시한다 (산출물 3만 적던 것을 고쳤다)",
     (lambda t: "쓰지 않기로 한 열" in t and '"kind": "excluded"' in t
      and "스키마·출력에는 넣지 않는다" not in t)(R.generate_template()))
shutil.rmtree(_DEMO, ignore_errors=True)

# ============================================================ B50 생성 안의 관문

done()
