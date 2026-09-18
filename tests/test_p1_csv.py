# -*- coding: utf-8 -*-
"""P1 ③ CSV — reader가 xlsx와 같은 구조를 낸다 · 인코딩·구분자 판정 · 전 구간 등가."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_common import *          # noqa: F401,F403 — 바닥은 하나다
from p1_common import _P, _reg_src, done    # noqa: F401 — `*`는 밑줄 이름을 건너뛴다


print("\n■ CSV reader — xlsx와 같은 구조 · 인코딩·구분자 판정")
_RAW = ROOT / "tests" / "fixtures" / "raw"
_c1 = reader.read(str(_RAW / "CSV01.csv"))
_s1 = _c1["sheets"][0]
show("format은 'csv'다 (xlsx로 위장하지 않는다)", _c1["format"] == "csv", _c1["format"])
show("xlsx와 같은 시트 구조 (cells·merged·indent·bold·images 키 존재)",
     all(k in _s1 for k in ("name", "max_row", "max_col", "cells",
                            "merged", "indent", "bold", "images")))
show("CSV에 없는 개념은 빈 값이되 키는 둔다",
     _s1["merged"] == [] and _s1["indent"] == {} and _s1["bold"] == []
     and _s1["images"] == [])
show("셀은 열문자 표기다 (A1 · C2)",
     _s1["cells"].get("A1") == "대공정" and _s1["cells"].get("C2") == "노칭 정밀도")
show("빈 셀은 cells에 넣지 않는다 (xlsx와 같게)", "D4" not in _s1["cells"])
show("max_col은 **최장 행** 기준이다 (짧은 행이 있어도 4)", _s1["max_col"] == 4,
     f"max_row={_s1['max_row']} max_col={_s1['max_col']}")

_c2 = reader.read(str(_RAW / "CSV02_cp949.csv"))
show("cp949 CSV를 읽는다 (BOM utf-8과 같은 결과)",
     _c2["encoding"] == "cp949"
     and _c2["sheets"][0]["cells"] == _s1["cells"], _c2["encoding"])
show("utf-8-sig(BOM) CSV의 첫 셀에 BOM이 남지 않는다",
     _c1["encoding"] == "utf-8-sig" and _s1["cells"]["A1"] == "대공정")

# **탭 파일이 한 열로 뭉개지지 않는다** — csv.Sniffer가 작은 표에서 실제로
# 실패했다(실측: 4행 탭 파일). 확장자·빈도 판정이 그 자리를 받는다.
_c3 = reader.read(str(_RAW / "CSV03_tab.tsv"))
show("탭 구분(.tsv)이 한 열로 뭉개지지 않는다",
     _c3["delimiter"] == "\t" and _c3["sheets"][0]["max_col"] == 4,
     f"delim={_c3['delimiter']!r} max_col={_c3['sheets'][0]['max_col']}")
_c4 = reader.read(str(_RAW / "CSV04_tab_in_csv.csv"))
show("확장자가 .csv인 탭 파일도 갈라 읽는다 (Sniffer/빈도)",
     _c4["delimiter"] == "\t" and _c4["sheets"][0]["max_col"] == 3)

show("head()가 csv에서 죽지 않는다 (분기는 이름이 아니라 구조)",
     "sheets" in reader.head(_c1, 2) and len(reader.head(_c1, 2)["sheets"]) == 1)
try:
    reader.read(str(_RAW / "CP01.xlsx") + ".zzz")
    _unsup = False
except ValueError as e:
    _unsup = "csv" in str(e) and "tsv" in str(e)
show("지원 포맷 목록이 실패 문장에 나온다 (.csv·.tsv 포함)", _unsup)


# ── B53 a. 결정적 판독 — 표·차트·그림·그룹·시각순서·숨김 ────────────────────
print("\n[B53 a] PPT 판독 — 텍스트 프레임과 노트만이 아니다")

import shutil as _sh                                              # noqa: E402
from core.llm import gateway, points, struct_map_pass                                              # noqa: E402
from parser import render                                         # noqa: E402
from parser.adapters import basic_pdf                             # noqa: E402
from cli import register as _reg, scan as _scan_mod               # noqa: E402
from cli.register import draft as Rdraft   # noqa: E402
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_pdf, make_ppt                                         # noqa: E402

_PPTX = _RAW / "PPT_shapes.pptx"
# **생성기보다 낡은 픽스처는 다시 만든다**(B78 2c 실측) — 「없으면 만든다」만 두면
# 생성기가 개정돼도 옛 파일이 살아남아, 그 파일로 잰 어서션이 조용히 붉는다
# (B53의 이미지 바이트가 그렇게 0바이트였다).
if not _PPTX.exists() or _PPTX.stat().st_mtime < Path(make_ppt.__file__).stat().st_mtime:
    make_ppt.build(_PPTX)
_praw = reader.read(str(_PPTX))
_by_id = {r["id"]: r for s in _praw["slides"] for r in s["shapes"]}
_kinds = {r["kind"] for r in _by_id.values()}

show("shape 레코드로 낸다 — 문자열 배열이 아니다",
     all(isinstance(r, dict) and "id" in r and "kind" in r for r in _by_id.values()))
show("표를 읽는다 — 행 단위 ` | ` 이음 · 행·열 수",
     _by_id["S4-TB1"]["kind"] == "table" and _by_id["S4-TB1"]["rows"] == 5
     and _by_id["S4-TB1"]["cols"] == 2
     and "항목 | 규격" in _by_id["S4-TB1"]["text"])
# a-ⓑ **값이 원문 그대로다** — 반올림하면 정확도를 버린다(그림으로 찍지 않는 이유).
_ch = _by_id["S5-CH1"]["text"]
show("차트 계열 값이 원문 그대로 실린다 (반올림 0)",
     all(v in _ch for v in ("0.8", "1.1", "0.95", "1.2", "0.7", "1.05"))
     and "월별 불량률" in _ch and "1월" in _ch, _ch.split("\n")[1][:40])
show("차트 종류가 실린다", _by_id["S5-CH1"].get("chart_type") == "LINE")
show("그림은 바이트를 raw에만 싣는다 — 계약 JSON에는 image_ref만",
     _praw["_images"].get("S6-P1") is not None
     and _by_id["S6-P1"]["image_ref"] == "S6-P1"
     and "blob" not in _by_id["S6-P1"] and _by_id["S6-P1"]["bytes_len"] > 0)
show("그룹을 재귀한다 — 자식 id가 그룹 경로를 갖는다",
     "S7-G1-B1" in _by_id and "S7-G1-B2" in _by_id)
# a-ⓒ **시각 순서** — 픽스처는 아래 상자를 XML 앞에 두었다.
_s8 = [r for r in _praw["slides"][7]["shapes"] if r["kind"] == "text"]
show("shape 순서는 XML이 아니라 시각 순서(top→left)다",
     _s8[0]["text"].startswith("위 상자") and _s8[1]["text"].startswith("아래 상자"),
     " → ".join(x["text"][:6] for x in _s8))
show("숨김 슬라이드를 데이터로 표시한다 (리더는 빼지 않는다)",
     _praw["slides"][9]["hidden"] is True
     and sum(1 for s in _praw["slides"] if s.get("hidden")) == 1)

_pc = basic_ppt.extract(_praw)
_locs = {c["source_locator"]: c for c in _pc}
# a-ⓓ 숨김은 **청크에 없다**
show("숨김 슬라이드는 청크에 없다",
     not [c for c in _pc if (c["meta"].get("slide")) == 10]
     and not [c for c in _pc if "어느 청크에도 없어야" in (c.get("text") or "")])
show("표·차트는 **각각 별도 청크**다 — 근거 좌표가 shape까지 내려간다",
     _locs["S4-TB1"]["meta"]["shape_kind"] == "table"
     and _locs["S5-CH1"]["meta"]["shape_kind"] == "chart"
     and _locs["S6-P1"]["meta"]["shape_kind"] == "picture")
show("section은 슬라이드 제목이다 (없으면 「슬라이드 N」)",
     _locs["슬라이드 3"]["section"] == "노칭 설비 구성")
# a-ⓔ 구획 헤더 뒤 슬라이드에 3단 경로가 붙는다
show("section_path 3단 — 덱 › 구획 › 슬라이드 제목",
     _locs["슬라이드 3"]["meta"]["section_path"]
     == "조립 공정 판독 시험 › 노칭 구획 › 노칭 설비 구성",
     _locs["슬라이드 3"]["meta"]["section_path"])
show("구획이 없으면 경로가 두 단으로 **줄어든다** (빈 칸을 만들지 않는다)",
     _locs["슬라이드 1"]["meta"]["section_path"] == "조립 공정 판독 시험")
show("본문 청크가 표·차트보다 앞에 온다 (읽는 순서)",
     [c["source_locator"] for c in _pc].index("슬라이드 4")
     < [c["source_locator"] for c in _pc].index("S4-TB1"))

# a-ⓕ **기존 산출과 바이트 동일** — 텍스트만 있는 슬라이드는 한 글자도 안 바뀐다.
_b = basic_ppt.extract(reader.read(str(_RAW / "PPT_basic.pptx")))
_want = {("슬라이드 1", "조립공정 설비 현황\n2026년 상반기 · 조립 1라인 · 조립기술팀"),
         ("슬라이드 10#1", None)}
_got = {(c["source_locator"], c.get("text")) for c in _b}
show("기존 PPT 픽스처 — 조각 수·locator가 그대로다 (16조각)",
     len(_b) == 16 and "슬라이드 10#6" in {c["source_locator"] for c in _b})
show("기존 텍스트 청크가 **바이트 동일**하다 (회귀 유지)",
     ("슬라이드 1", "조립공정 설비 현황\n2026년 상반기 · 조립 1라인 · 조립기술팀") in _got)
show("[의도된 변화] 제목 있는 슬라이드는 section이 제목이 된다 — chunk_id가 옮겨간다",
     {c["source_locator"]: c["section"] for c in _b}["슬라이드 2"] == "노칭 공정")

# 계약 A — `shape_kind`는 **닫힌 8종**이고 validator가 검사한다
show("shape_kind 닫힌 8종 (문서 2 계약 A)",
     validator.SHAPE_KINDS == ("text", "title", "table", "chart", "picture",
                               "smartart", "notes", "page"))


# ── B53 b. ④ 이미지 요약 = 바이트 + 맥락 ──────────────────────────────────
print("\n[B53 b] ④ 이미지 요약 — 참조 문자열이 아니라 바이트")

_seen = {}


def _spy(ref, *, image=None, mime=None, context="", page=None):
    _seen.update(ref=ref, image=image, mime=mime, context=context, page=page)
    return "요약(시험)"


_res = pipeline.parse(basic_ppt, "B53PPT", str(_PPTX), summarize=_spy)
_pic = [c for c in _res.envelope["chunks"]
        if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
show("④가 **바이트**를 받는다 (구판은 참조 문자열이었다 — 개정대장 §AJ)",
     isinstance(_seen.get("image"), bytes) and len(_seen["image"]) > 0
     and _seen["mime"] == "image/png", f"{len(_seen.get('image') or b'')}바이트")
show("④가 **맥락**을 받는다 — 같은 슬라이드의 텍스트",
     _seen.get("context") == "노칭 프레스 외관")
show("④가 쪽 전체 그림을 함께 받는다 (있을 때)",
     isinstance(_seen.get("page"), bytes) and _seen["page"][:4] == b"\x89PNG")
# b-ⓐ **mock에서도** 바이트 도달을 잰다 — 실호출 없이 재는 유일한 자리다.
_mres = pipeline.parse(basic_ppt, "B53PPTM", str(_PPTX))
_mpic = [c for c in _mres.envelope["chunks"]
         if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
show("mock 갈래도 image_bytes_len을 남긴다 (바이트가 tagger까지 왔다)",
     _mpic["meta"]["image_summary_source"] == "mock"
     and _mpic["meta"]["image_bytes_len"] > 0, str(_mpic["meta"]["image_bytes_len"]))
show("쪽 렌더 여부가 데이터에 남는다 — page | none",
     _pic["meta"]["slide_render"] in validator.SLIDE_RENDER
     and _mpic["meta"]["slide_render"] in validator.SLIDE_RENDER)

# b-ⓑ chat() 멀티모달 페이로드 — 전송 직전 dict를 잡는다
_sent = {}
_real_post, _real_req = gateway._post, gateway.require
try:
    gateway._post = lambda u, p, k, t: _sent.update(payload=p) or {
        "choices": [{"message": {"content": "요약"}}]}
    gateway.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                              "timeout": 5, "retry": 0}
    points.summarize_image("R1", image=b"\x89PNG\x00", mime="image/png",
                        context="맥락", page=b"\x89PNGpage")
    _parts = _sent["payload"]["messages"][-1]["content"]
    _imgs = [p for p in _parts if p.get("type") == "image_url"]
    show("chat() 멀티모달 — content가 리스트이고 image_url이 base64 data URI다",
         isinstance(_parts, list) and len(_imgs) == 2
         and _imgs[0]["image_url"]["url"].startswith("data:image/png;base64,"),
         _imgs[0]["image_url"]["url"][:40] if _imgs else "")
    show("맥락 텍스트가 같은 메시지에 실린다",
         any(p.get("type") == "text" and "맥락" in p.get("text", "") for p in _parts))

    # b-ⓕ 게이트웨이가 이미지를 400으로 거절하면 **NotConfigured**로 멈춘다
    def _p400(u, p, k, t):
        raise gateway.GatewayError(400, "unsupported content type: image_url", u)
    gateway._post = _p400
    try:
        points.summarize_image("R1", image=b"\x89PNG", mime="image/png")
        _nc = "통과했다"
    except gateway.NotConfigured as e:
        _nc = str(e)
    except Exception as e:                                        # noqa: BLE001
        _nc = f"{type(e).__name__}"
    show("게이트웨이 400(이미지 거부) → NotConfigured — 요약을 지어내지 않는다",
         "게이트웨이가 이미지 입력을 받지 않는다" in _nc, _nc[:52])
    try:                       # 이미지 없는 400은 설정 결함이 아니다 — 그대로 올린다
        points.summarize_image("R1", context="c")
        _tc = "통과"
    except gateway.NotConfigured:
        _tc = "NotConfigured(과잉)"
    except gateway.GatewayError:
        _tc = "GatewayError"
    show("이미지 없는 400은 NotConfigured로 바꾸지 않는다 (원인을 옮기지 않는다)",
         _tc == "GatewayError", _tc)
finally:
    gateway._post, gateway.require = _real_post, _real_req

# b-ⓓ soffice가 없어도 **문서는 완주한다**
_realwhich = _sh.which
try:
    _sh.which = lambda n, *a, **k: None if "office" in n else _realwhich(n, *a, **k)
    _nres = pipeline.parse(basic_ppt, "B53NOSO", str(_PPTX), summarize=_spy)
    _npic = [c for c in _nres.envelope["chunks"]
             if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
    show("soffice 없으면 slide_render=none이고 **문서는 완주한다**",
         _nres.ok and _npic["meta"]["slide_render"] == "none"
         and len(_nres.envelope["chunks"]) == 12)
    show("렌더 부재는 진단으로 드러난다 (조용히 다르게 돌지 않는다)",
         render.available()[0] is False and "soffice" in render.available()[1])
finally:
    _sh.which = _realwhich

# b-ⓒ **표시** — 실호출로만 검증되는 항목(§7.5). mock에서 재는 것은 배관까지다.
show("[표시 · §7.5] ④ 실호출 요약 **품질**은 mock으로 판정하지 않는다 — "
     "사내 첫 실행에서 사람이 본다. 여기서 잰 것은 바이트·맥락·쪽이 ④에 닿았는가다",
     _mpic["meta"]["image_summary_source"] == "mock"
     and _pic["meta"]["image_summary_source"] == "live")
# **같은 봉투의 한 글자만 바꿔 대조한다** — 다른 이유로 붉어지면 이 검사가
# 무엇을 쟀는지 알 수 없다.
_env_ok = _mres.envelope                     # 방금 통과한 진짜 봉투
_ok_g, _ = validator.check(_env_ok)
import copy as _copy                                              # noqa: E402
_env_bad = _copy.deepcopy(_env_ok)
_env_bad["chunks"][0]["meta"]["shape_kind"] = "그림"
_ok_b, _d_b = validator.check(_env_bad)
show("닫힌 목록 밖 shape_kind를 잡는다 (검사하는 자리가 있어야 닫힌 것이다)",
     _ok_g and not _ok_b and len(_d_b) == 1 and "shape_kind" in _d_b[0],
     _d_b[0][:64] if _d_b else "")

# **경로를 박지 않는다**(B63 ① — 지시문 파일에 칸 ID가 붙었다). 잠글 성질은 그대로다:
# 두 지시문의 판이 그때 올랐고 **판은 파일이 말한다**(§7.6-B-5).
show("지시문 판이 올랐다 — image_summary i-2.0 · extract e-1.1",
     "version: i-2.0" in gateway.prompt("image_summary")
     and "version: e-1.1" in gateway.prompt("extract"))

# ── B53 c. 기본 PDF 어댑터 ────────────────────────────────────────────────
print("\n[B53 c] 기본 PDF 어댑터 — 쪽이 청크다")

_PDF = _RAW / "PDF_basic.pdf"
if not _PDF.exists() or _PDF.stat().st_mtime < Path(make_pdf.__file__).stat().st_mtime:
    make_pdf.build(_PDF)
_draw = reader.read(str(_PDF))
show(".pdf가 reader의 지원 목록에 있다 (목록의 정본은 reader다)",
     ".pdf" in reader.SUPPORTED and _draw["format"] == "pdf")
show("PDF 목차를 읽는다", [t["title"] for t in _draw["toc"]] == ["1. Notching", "2. Stacking"])
_dc = basic_pdf.extract(_draw)
_pages = [c for c in _dc if c["meta"]["shape_kind"] == "page"]
_phs = [c for c in _dc if c["meta"]["shape_kind"] == "picture"]
show("페이지 청크 3 + 그림 placeholder 1", len(_pages) == 3 and len(_phs) == 1,
     f"{len(_pages)} + {len(_phs)}")
show("source_locator가 쪽이다 — P1 · P2 · P3",
     [c["source_locator"] for c in _pages] == ["P1", "P2", "P3"])
# c-ⓑ **section이 toc에서 온다**
show("section이 목차에서 온다 (없으면 「페이지 N」)",
     _pages[0]["section"] == "1. Notching" and _pages[1]["section"] == "2. Stacking")
show("목차가 없으면 「페이지 N」으로 떨어진다 (조용히 비우지 않는다)",
     basic_pdf.extract({"pages": [{"index": 7, "text": "t", "images": []}],
                        "toc": []})[0]["section"] == "페이지 7")
# 스캔본 — 텍스트 0자 쪽은 그림 placeholder 하나로만 (빈 청크 0)
_scan = basic_pdf.extract({"toc": [], "pages": [
    {"index": 1, "text": "", "images": [
        {"id": "P1-P1", "kind": "picture", "image_ref": "P1-P1",
         "mime": "image/png", "bytes_len": 9}]}]})
show("스캔본(텍스트 0자)은 그림 placeholder 하나로 낸다 — 빈 청크를 만들지 않는다",
     len(_scan) == 1 and _scan[0]["meta"]["page_text_empty"] is True
     and _scan[0]["meta"]["shape_kind"] == "picture")
show("PDF는 지문 대상이 아니다 — 표 어댑터와 대조하지 않는다",
     _scan_mod.scan(str(_PDF)).get("not_fingerprintable") == "pdf")
show("--use-basic이 .pdf 전부에 뜬다 (섞이면 뜨지 않는다)",
     (Rdraft.basic_adapter_proposal([str(_PDF)]) or {}).get("adapter")
     == "parser/adapters/basic_pdf.py"
     and Rdraft.basic_adapter_proposal([str(_PDF), str(_PPTX)]) is None)
show("위임 래퍼가 제안이 정한 어댑터를 문다 (PDF가 PPT 어댑터를 물지 않는다)",
     "basic_pdf" in _reg_src()
     and 'mod = Path(proposal["adapter"]).stem'
     in _reg_src())

# ── B58 ③ 고정 prose xlsx 어댑터 + 레벨 규칙 ([정정] 46) ──────────────────

done()
