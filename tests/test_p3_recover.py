# -*- coding: utf-8 -*-
"""P3 ⑤ 되돌림 — 재생성 지시 · 문답 누적 · 청크 단위 실패 · 지도 무효화 · llm-check."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src            # noqa: F401 — `*`는 밑줄 이름을 건너뛴다
from core.state.bootstrap import coord_layer      # 좌표 층은 묻는다 (B85)

from cli import interview as _IV
import contextlib as _ctx
import io as _io
from core.llm import gateway as _llm
from core.llm import check
from core.llm import gateway

setup()


print("\n■ B55 ① — 재생성 지시가 조립 메시지에 실린다")

_b55_sent = {}
_b55_post, _b55_req, _b55_mock = _llm._post, _llm.require, _llm.use_mock


def _b55_capture():
    _llm.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                               "timeout": 5, "retry": 0}
    _llm.use_mock = lambda: False
    _llm._post = lambda u, p, k, t: _b55_sent.update(payload=p) or {
        "choices": [{"message": {"content": json.dumps(
            {"adapter_py": "# x\nADAPTER = {}\ndef extract(raw):\n    return []",
             "schema_json": "{}"})}}]}


def _b55_restore():
    _llm._post, _llm.require, _llm.use_mock = _b55_post, _b55_req, _b55_mock


def _b55_system(**kw):
    """`draft`를 태워 **전송 직전 dict**의 system 메시지를 돌려준다."""
    _b55_sent.clear()
    Rdraft.draft("b55i", kw.pop("revision", 0), **kw)
    return _b55_sent["payload"]["messages"][0]["content"]


_b55_dir = R._dir("b55i")
_b55_dir.mkdir(parents=True, exist_ok=True)
(_b55_dir / "input_package.json").write_text(json.dumps(
    {"human": {"doc_type": "b55i", "layer": "process",
               "samples": ["tests/fixtures/raw/CP01.xlsx"], "hint": ""},
     "system": {"reader_head": [], "skeleton_closed_list": {},
                "layer_vocabulary": {"layer": "process"}, "blocks": {},
                "adapter_skeleton": ""}}, ensure_ascii=False), encoding="utf-8")
_b55_capture()
try:
    _sys0 = _b55_system()                                   # 초회 — 지시 없음
    _hist2 = [{"n": 1, "instruction": "헤더는 2행이다", "by": "사람(검수 지시)"},
              {"n": 2, "instruction": "극성 열은 쓰지 않는다", "by": "자동(하네스 문면)"}]
    _sys2 = _b55_system(revision=2, instruction="극성 열은 쓰지 않는다",
                        history=_hist2)
finally:
    _b55_restore()

# ①ⓐ **둘 다 실린다** — 2회차 지시가 1회차를 덮으면 사람이 같은 교정을 두 번 적는다.
show("① 지시가 조립된 system에 **실제로 실린다** (기록이 아니라 전송분)",
     "헤더는 2행이다" in _sys2 and "극성 열은 쓰지 않는다" in _sys2,
     f"{len(_sys2.encode()):,}B")
show("① 누적 2회 — 앞 지시가 뒤 지시에 덮이지 않는다",
     _sys2.index("헤더는 2행이다") < _sys2.index("극성 열은 쓰지 않는다"))
# ①ⓒ 초회에는 구획 자체가 없다
show("① 초회에는 지시 구획이 없다 (없는 것을 빈 칸으로 넣지 않는다)",
     "헤더는 2행이다" not in _sys0
     and len(_sys0.encode()) < len(_sys2.encode()),
     f"{len(_sys0.encode()):,}B → {len(_sys2.encode()):,}B")
# **전송 크기(B30)가 지시 구획을 포함한다** — 사람이 보내기 전에 크기를 알아야 한다
show("① 전송 크기 표시가 지시 구획을 포함한다 (부르기 직전에 잰다)",
     len(_sys2.encode()) - len(_sys0.encode())
     >= len("극성 열은 쓰지 않는다".encode()) + len("헤더는 2행이다".encode()))
shutil.rmtree(_b55_dir, ignore_errors=True)

# ①-후속-2 — **고정 문장은 템플릿의 것이다** (문서 7 §7.6-B-5 · B18 경계).
#
# 문구를 grep으로 잠그면 **성질이 아니라 글자**를 잠근다 — 한 글자만 바꿔 코드로
# 되돌리면 통과한다. 그래서 **템플릿에서 그 문장만 지운 사본**으로 렌더해
# ①문장이 사라지고 ②주입된 지시는 그대로인지를 본다(둘째가 없으면 「렌더가 깨진
# 것」과 구분되지 않는다).
_b55_tmpl = R.generate_template()
_b55_pkgmin = {"human": {"doc_type": "t", "layer": "process", "samples": ["s"],
                         "hint": ""},
               "system": {"reader_head": [], "skeleton_closed_list": {},
                          "layer_vocabulary": {"layer": "process"}, "blocks": {},
                          "adapter_skeleton": ""}}
_b55_items = Rdraft.instruction_items(
    "극성 열은 쓰지 않는다",
    [{"n": 1, "instruction": "헤더는 2행이다", "by": "사람(검수 지시)"}])
_B55_FIXED = "앞 초안이 아래 지시를 받았다"
_b55_full = R._render_template(_b55_tmpl, _b55_pkgmin, regeneration=_b55_items)
_b55_cut = R._render_template(_b55_tmpl.replace(_B55_FIXED, ""), _b55_pkgmin,
                              regeneration=_b55_items)
show("①-후속-2 구획의 고정 문장이 **템플릿에서** 온다 "
     "(문장을 지운 사본으로 렌더하면 사라진다)",
     _B55_FIXED in _b55_full and _B55_FIXED not in _b55_cut)
show("①-후속-2 그때도 **주입된 지시 목록은 그대로다** (렌더가 깨진 것과 구분)",
     "헤더는 2행이다" in _b55_cut and "극성 열은 쓰지 않는다" in _b55_cut
     and "## [재생성 지시]" in _b55_cut)
show("①-후속-2 지시가 없으면 구획째 빠진다 (빈 칸을 남기지 않는다)",
     "## [재생성 지시]" not in
     R._render_template(_b55_tmpl, _b55_pkgmin, regeneration=[]))
show("①-후속-2 치환 누락 0 — 지시 자리가 늘어도 `{{` 잔존 0",
     "{{" not in _b55_full)
# **판 계보의 자리가 바뀌었다**(B63 ① — 파일 12개 → git 이력). 여기서 잠그는 성질도
# 뒤집힌다: 「옛 판을 남긴다」가 아니라 **「쓰이는 판이 하나이고 그 자리가 보인다」**.
# 판 번호는 여전히 박지 않는다 — 박으면 판이 오를 때마다 이 줄이 깨진다.
_tmpls = sorted(R.KIT.glob("생성프롬프트_템플릿_v*.md"))
show("①-후속-2 생성 지시문은 한 자리다 (킷 glob 폐지 · 이름으로 집는다)",
     not _tmpls
     and gateway.prompt_path("generate").endswith("/1.4_generate.md")
     and "{{재생성_지시}}" in R.generate_template(),
     f"kit 템플릿 {len(_tmpls)}개 · {Path(gateway.prompt_path('generate')).name}")

# ── B55 ② 문답은 누적된다 — 재현 조건의 그릇은 `human.hint`다 (B36 · §6.5) ──
print("\n■ B55 ② — 문답 묶음이 쌓이고 표본이 바뀌면 stale로 남는다")

# **먼저 지운다** — 앞선 실행의 패키지가 남아 있으면 「이어 붙인다」를 재는 검사가
# 그 잔재까지 세어, 묶음 수가 실행 이력에 따라 달라진다(단독 실행이 판정 규격이다).
shutil.rmtree(R._dir("b55iv"), ignore_errors=True)
# 세션마다 「답 · 진행 · **Y**」다 — 「진행」 뒤에 확정 요약 확인이 한 번 더 온다(B60 ②).
_b55_feed = iter(["표본은 CP 양식이다", "진행", "Y", "헤더는 4행이다", "진행", "Y",
                  "다른 문서다", "진행", "Y"])
_b55_ask = _IV._ask
_IV._ask = lambda prompt="": next(_b55_feed)
_CP1 = str(RAW / "CP01.xlsx")
_PF1 = str(RAW / "PFMEA01.xlsx")
_b55_buf = _io.StringIO()
try:
    def _b55_gen(samples):
        # **패키지는 draft보다 먼저 쓰인다** — fixture가 없어 초안 단계에서 멈춰도
        # 여기서 재는 것(문답이 패키지에 남았나)은 이미 결정돼 있다.
        try:
            with _ctx.redirect_stdout(_b55_buf):
                Rgen.cmd_generate("b55iv", "process", samples, "", interview=True)
        except SystemExit:
            pass
        return json.loads((R._dir("b55iv") / "input_package.json")
                          .read_text(encoding="utf-8"))

    _pk1 = _b55_gen([_CP1])
    _pk2 = _b55_gen([_CP1])
    _pk3 = _b55_gen([_PF1])
finally:
    _IV._ask = _b55_ask


def _b55_batches(pk):
    return Rivlog._hint_batches((pk["human"] or {}).get("hint"))


# ②ⓐ **재실행이 덮지 않는다** — 구판은 이번 실행분으로 치환했다.
show("② --interview 2회 — 묶음이 **둘 다 남는다** (덮지 않는다)",
     len(_b55_batches(_pk1)) == 1 and len(_b55_batches(_pk2)) == 2,
     f"{len(_b55_batches(_pk1))} → {len(_b55_batches(_pk2))}묶음")
# **자리가 옮겨졌다**(B62 ②) — 전문은 로그에, 판단은 패키지에. 잠글 성질은
# 그대로다: **사람의 답은 다시 못 만드니 사라지지 않는다.**
_b55_log = Rivlog.read_log("b55iv")
show("② 1회차 답이 그대로 있다 — 전문은 로그에 (사람의 답은 다시 못 만든다)",
     any("표본은 CP 양식이다" in (r.get("answer") or "")
         for rounds in _b55_log.values() for r in rounds),
     f"로그 묶음 {len(_b55_log)}개")
# ②ⓒ 표본이 바뀌면 **표시하되 지우지 않는다**
_b55_stale = [b for b in _b55_batches(_pk3) if b.get("stale")]
show("② 표본을 바꾸면 이전 묶음이 **stale로 남는다** (지워지지 않는다)",
     len(_b55_batches(_pk3)) == 3 and len(_b55_stale) == 2
     and all(b["samples"] == [_CP1] for b in _b55_stale),
     f"묶음 {len(_b55_batches(_pk3))} · stale {len(_b55_stale)}")
show("② 묶음마다 그때의 표본과 시각을 단다 (재현 조건)",
     all(b.get("samples") is not None and b.get("at") for b in _b55_batches(_pk3)))
# ②ⓕ **키 수가 명세다** — 항목으로 늘고 키로 늘지 않는다(B36)
show("② 사람 4키·시스템 5키 불변 — 문답은 hint 그릇 **안에서** 는다",
     all(len(p["human"]) == 4 and len(p["system"]) == 5
         for p in (_pk1, _pk2, _pk3)),
     f"human {len(_pk3['human'])} · system {len(_pk3['system'])}")
# ②-2 **모델도 그것을 본다** — 저장만 이어 붙이면 사람이 두 번 답한다
# **B62 ②가 이 자리를 좁혔다** — 이전 표본(stale)의 **전문**은 싣지 않는다.
# 같은 전문이 패키지와 이 자리 둘로 나가던 것을 끊었고, 이전 표본의 **판단**은
# `decisions`로 남아 생성 지시문이 표시해서 싣는다.
_b55_fresh = _IV._prior_rounds(_pk3)
show("② 문답 세션이 **현재 표본 묶음의** 이전 라운드만 받는다 (전문은 로그에서)",
     len(_b55_fresh) == 1 and "다른 문서다" in (_b55_fresh[0].get("answer") or ""),
     f"현재 {len(_b55_fresh)}라운드")
show("② 이전 표본의 판단은 decisions로 남는다 (전문이 아니라 결정이 건너간다)",
     all(b.get("decisions") is not None for b in _b55_batches(_pk3) if b.get("stale")))
shutil.rmtree(R._dir("b55iv"), ignore_errors=True)


# ── B55 ③~⑩ 감사 2차 A군 수리 ─────────────────────────────────────────────
print("\n■ B55 ③ — 추출 실패의 처분은 청크 단위다 (문서 4 §4.10 규약 9)")

from core.build import extract as _EX                                   # noqa: E402

_b55_env = {"doc_id": "B55FAIL", "adapter_version": "1.0", "parsed_at": "t",
            "chunks": [{"source_locator": f"L{i}", "text": f"노칭 공정 {i}"}
                       for i in (1, 2, 3)]}
_b55_ids = {f"L{i}": f"B55FAIL:c{i}" for i in (1, 2, 3)}
_b55_cfg = {"layer": "process", "config_version": "1", "categories": {}, "relations": []}
_b55_real = _EX._candidates_for


def _b55_one_bad(cid, chunk, cfg, vocab):
    if cid.endswith("c2"):
        raise ValueError("주입한 실패")
    return _b55_real(cid, chunk, cfg, vocab)


_EX.checkpoint_path("B55FAIL").unlink(missing_ok=True)
_b55_d = store.path(store.DEFECTS)
_b55_b0 = _b55_d.stat().st_size if _b55_d.exists() else 0
_EX._candidates_for = _b55_one_bad
try:
    _b55_out, _b55_made = _EX.extract(_b55_env, _b55_cfg, _b55_ids, {})
finally:
    _EX._candidates_for = _b55_real
_b55_ok = [c for c in _b55_out["candidates"] if not c.get("failed")]
_b55_bad = [c for c in _b55_out["candidates"] if c.get("failed")]
# ③ⓐ **한 청크의 예외가 문서를 죽이지 않는다** — 3천 청크 문서가 한 줄로 통째로 빠지면
# 그 문서는 영영 안 들어간다.
show("③ⓐ 청크 하나가 실패해도 나머지는 산출된다",
     len(_b55_ok) == 2 and len(_b55_bad) == 1, f"성공 {len(_b55_ok)} · 실패 {len(_b55_bad)}")
# ③ⓑ **무후보와 구분한다** — `entities: []`는 「봤는데 없었다」, `failed`는 「보지 못했다」.
show("③ⓑ 체크포인트에 failed가 사유와 함께 남는다 (무후보와 구분)",
     _b55_bad[0]["failed"].startswith("ValueError")
     and _b55_bad[0]["entities"] == [], _b55_bad[0]["failed"])
show("③ⓒ defects.log에 남는다 — 큐가 아니라 결함 로그다 (새 kind 0)",
     (_b55_d.stat().st_size if _b55_d.exists() else 0) > _b55_b0
     and "추출 실패" in _b55_d.read_text(encoding="utf-8"))
show("③ 구축이 failed 청크를 건너뛴다 (결함이 「후보 0건」 통계에 녹지 않는다)",
     "if not c.get(\"failed\")" in
     ' '.join(_p.read_text(encoding="utf-8")
                for _p in sorted((ROOT / "core" / "build").glob("*.py"))))
# ③ⓓ **전건 실패면 체크포인트를 쓰지 않는다** — 「파일 존재 = 추출 완료」(P-1).
_EX.checkpoint_path("B55FAIL").unlink(missing_ok=True)
_EX._candidates_for = lambda *a, **k: (_ for _ in ()).throw(ValueError("전건"))
try:
    _b55_all, _b55_made2 = _EX.extract(
        dict(_b55_env, doc_id="B55ALL"), _b55_cfg,
        {f"L{i}": f"B55ALL:c{i}" for i in (1, 2, 3)}, {})
finally:
    _EX._candidates_for = _b55_real
show("③ⓓ 전 청크 실패면 체크포인트를 남기지 않는다 (재시도가 막히지 않는다)",
     not _EX.checkpoint_path("B55ALL").exists()
     and _b55_all.get("all_failed") is True and _b55_made2 is False)

print("\n■ B55 ④ — 프레임 지도가 source_hash 무효화를 우회하지 않는다 (§6.3 · B16)")

import shutil as _b55_sh                                          # noqa: E402
from parser import struct_map as _SM, tagger as _tagger                              # noqa: E402
from parser.adapters import basic_ppt as _BP                      # noqa: E402

_b55_src = _P.data() / "_b55_map.pptx"
_b55_sh.copy(RAW / "PPT_basic.pptx", _b55_src)
_b55_calls = []


def _b55_ask(doc_id, lines):
    _b55_calls.append(doc_id)
    return {"doc_id": doc_id, "source": "live", "prompt_version": "s-1.0",
            "rows": [{"row": n, "heading": t.strip()[:2] in ("1.", "2.", "3."),
                      "level": 1 if t.strip()[:2] in ("1.", "2.", "3.") else 0}
                     for n, t in lines]}


def _b55_parse():
    _b55_calls.clear()
    pipeline.parse(_BP, "B55MAP", str(_b55_src), map_structure=_b55_ask,
        layer=coord_layer())
    return len(_b55_calls)


_b55_sh.rmtree(_SM.keep_dir(), ignore_errors=True)
_b55_n1 = _b55_parse()
_b55_files = sorted(p.name for p in _SM.keep_dir().glob("*"))
_b55_n2 = _b55_parse()                       # 같은 원본 — 재사용
_b55_src.write_bytes(_b55_src.read_bytes() + b"\x00")   # 1바이트 변경
_b55_n3 = _b55_parse()
# ④ⓑ **문서당 파일 하나**다 — 구판은 `{doc_id}:{프레임}.json`을 따로 만들었다.
show("④ⓑ 보존 파일은 {doc_id}.json 하나다 (프레임은 그 안의 maps[키])",
     _b55_files == ["B55MAP.json"], str(_b55_files))
show("④ⓒ 같은 원본 재파싱은 재사용한다 (LLM 0회)",
     _b55_n1 == 1 and _b55_n2 == 0, f"1회차 {_b55_n1} · 2회차 {_b55_n2}")
# ④ⓐ **원본이 바뀌면 옛 지도가 살아나지 않는다** — 구판은 프레임 지도를 해시 대조
# 없이 읽어 영영 옛 분할을 썼고, chunk_id 결정성의 근거가 무너졌다.
show("④ⓐ 원본 1바이트 변경 → 지도를 새로 산출한다 (해시 대조를 우회하지 않는다)",
     _b55_n3 == 1, f"3회차 {_b55_n3}회")
_b55_kept = json.loads((_SM.keep_dir() / "B55MAP.json").read_text(encoding="utf-8"))
show("④ 보존 파일이 source_hash와 maps를 함께 갖는다",
     bool(_b55_kept.get("source_hash")) and bool(_b55_kept.get("maps")),
     f"프레임 {sorted(_b55_kept.get('maps') or {})}")
_b55_src.unlink(missing_ok=True)
_b55_sh.rmtree(_SM.keep_dir(), ignore_errors=True)

print("\n■ B55 ⑤ — 리허설 파싱도 운영 doc_id를 쓴다 (§6.6 B51-2)")

from cli.ingest import doc_id_of as _b55_did                      # noqa: E402

show("⑤ 리허설 파싱이 doc_id_of(표본)를 쓴다 ({DOC_TYPE}NN이 아니다)",
     "mod, doc_id_of(s), s, layer=" in
     _reg_src())
# **키가 같아야 재사용이 성립한다** — 구판은 리허설이 다른 이름으로 써서 못 만났다.
_b55_sh.rmtree(_SM.keep_dir(), ignore_errors=True)
_b55_sh.copy(RAW / "PPT_basic.pptx", _b55_src)
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask,
        layer=coord_layer())
_b55_rehearsal = len(_b55_calls)
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask,
        layer=coord_layer())
show("⑤ⓐ 리허설이 남긴 지도를 운영 인입이 찾는다 (재사용 — LLM 0회)",
     _b55_rehearsal == 1 and len(_b55_calls) == 0)
_b55_sh.rmtree(_SM.keep_dir(), ignore_errors=True)
_b55_calls.clear()
pipeline.parse(_BP, "B55OLD01", str(_b55_src), map_structure=_b55_ask,
        layer=coord_layer())   # 구판 이름
_b55_calls.clear()
pipeline.parse(_BP, _b55_did(str(_b55_src)), str(_b55_src), map_structure=_b55_ask,
        layer=coord_layer())
show("⑤ [대조] 이름이 다르면 못 찾는다 — 고친 것이 이것이다",
     len(_b55_calls) == 1)
_b55_src.unlink(missing_ok=True)
_b55_sh.rmtree(_SM.keep_dir(), ignore_errors=True)

print("\n■ B55 ⑥ — PDF 쪽 렌더가 ④에 닿는다")

from parser.adapters import basic_pdf as _BPDF                    # noqa: E402


def _b55_sum(ref, *, image=None, mime=None, context="", page=None):
    return f"요약(page={'있음' if page else '없음'})"


_b55_pdf = pipeline.parse(_BPDF, "B55PDF", str(RAW / "PDF_basic.pdf"),
                          summarize=_b55_sum,
        layer=coord_layer())
_b55_pic = [c for c in _b55_pdf.envelope["chunks"]
            if (c.get("meta") or {}).get("shape_kind") == "picture"][0]
# 구판은 `meta["slide"]`만 봐서 PDF는 늘 `pages.get(None)` → 항상 none이었다.
show("⑥ⓐ PDF 그림 청크의 slide_render가 page다 (meta.page를 본다)",
     _b55_pic["meta"]["slide_render"] == "page"
     and _b55_pic["meta"].get("page") is not None,
     f"page={_b55_pic['meta'].get('page')} · {_b55_pic['meta']['slide_render']}")
show("⑥ 조회 키 결정은 한 자리다 (tagger._page_no)",
     _tagger._page_no({"meta": {"slide": 3}}) == 3
     and _tagger._page_no({"meta": {"page": 7}}) == 7
     and _tagger._page_no({"meta": {}}) is None)

print("\n■ B55 ⑦ — llm-check의 401/403이 ③인증으로 간다")

_b55_req, _b55_cfgf, _b55_postf = gateway.require, gateway.config, gateway._post
try:
    gateway.require = lambda pt: {"url": "https://x", "model": "m", "key": "k",
                              "timeout": 5, "retry": 0}
    gateway.config = lambda: {"url": "https://x", "model": "m", "key": "k",
                          "timeout": 5, "retry": 0, "embed_model": None}

    def _b55_probe(exc):
        gateway._post = lambda u, p, k, t: (_ for _ in ()).throw(exc)
        return {s["id"]: s for s in check.probe()}

    _p401 = _b55_probe(gateway.GatewayError(401, "invalid api key", "u"))
    _p500 = _b55_probe(gateway.GatewayError(500, "upstream boom", "u"))
    _purl = _b55_probe(__import__("urllib.error", fromlist=["x"]).URLError("no route"))
finally:
    gateway.require, gateway.config, gateway._post = _b55_req, _b55_cfgf, _b55_postf
# **어디까지 갔는지가 곧 원인이다**(B19) — 키가 틀렸는데 「주소에 못 닿았다」고
# 말하면 사람이 엉뚱한 곳을 고친다.
show("⑦ⓐ 401 → ②도달 PASS · ③인증 FAIL",
     _p401["②"]["ok"] is True and _p401["③"]["ok"] is False
     and "401" in _p401["③"]["detail"])
show("⑦ⓑ 500 → ③이 「인증 문제는 아니다」라고 말한다",
     _p500["③"]["ok"] is False and "인증 문제는 아니다" in _p500["③"]["detail"]
     and "upstream boom" in _p500["③"]["detail"])
show("⑦ⓒ URLError → ②도달 FAIL 그대로 (③은 아예 나오지 않는다)",
     _purl["②"]["ok"] is False and "③" not in _purl)
# **`_post`의 HTTPError 포착은 남는다** — 거기가 GatewayError로 바꿔 던지는 자리다.
# 죽어 있던 것은 `probe` 안의 갈래이고, 그 함수 본문만 본다.
# `probe`는 연결 확인의 자리다 — 분할 뒤 `core/llm/check.py`가 소유한다(B78 2b).
_b55_chksrc = (ROOT / "core" / "llm" / "check.py").read_text(encoding="utf-8")
_b55_llmsrc = (ROOT / "core" / "llm" / "gateway.py").read_text(encoding="utf-8")
_b55_probe_src = _b55_chksrc[_b55_chksrc.index("def probe("):]
_b55_end = _b55_probe_src.find("\ndef ", 1)          # 파일 끝이면 그대로 (분할 뒤 마지막 함수다)
_b55_probe_src = _b55_probe_src[:_b55_end] if _b55_end > 0 else _b55_probe_src
# **주석은 코드가 아니다** — 무엇이 왜 죽어 있었는지 적은 문장이 그 자리에 있고,
# 문자열로 세면 그 설명이 위반으로 잡힌다(§7.5 「주석을 구현으로 세지 않는다」의 역).
_b55_probe_code = "\n".join(
    ln for ln in _b55_probe_src.split("\n") if not ln.strip().startswith("#"))
show("⑦ probe에 죽은 HTTPError 갈래가 없다 (GatewayError로 받는다)",
     "except urllib.error.HTTPError" not in _b55_probe_code
     and "GatewayError as e" in _b55_probe_code
     and "e.status" in _b55_probe_code)
show("⑦ _post의 HTTPError 포착은 그대로다 (바꿔 던지는 자리다)",
     "except urllib.error.HTTPError" in _b55_llmsrc
     and "raise GatewayError(e.code, body, url) from e" in _b55_llmsrc)

print("\n■ B55 ⑧⑨ — 경로 경고 · 멱등 계측 · 골든셋 유형")

from cli import ingest as _ING                                    # noqa: E402

# doc_id가 파일명 stem 파생이라(D-110) **파일명 비교는 참이 될 수 없었다**.
show("⑧ 경로 비교가 파일명이 아니라 전체 경로다 (D-110의 대가가 화면에 뜬다)",
     "_norm_path(prev[\"source_path\"]) != _norm_path(doc)" in
     (ROOT / "cli" / "ingest.py").read_text(encoding="utf-8")
     and _ING._norm_path("./a/x.xlsx") != _ING._norm_path("./b/x.xlsx")
     and _ING._norm_path("a/x.xlsx") == _ING._norm_path("./a/x.xlsx"))
# `return` 아래가 통째로 도달 불가였다 — 완료판정 4가 한 번도 계측된 적이 없다.
_b55_doc = (ROOT / "doctor.py").read_text(encoding="utf-8")
show("⑨ 멱등 계측이 도달 가능하다 (헬퍼 `_clean()`을 부르고 2회 실행·비교한다)",
     "rc, residue = _clean()" in _b55_doc
     and _b55_doc.index("rc, residue = _clean()")
     < _b55_doc.index("g1, q1, r1 = snap()")
     and "클린 2회 동일 그래프" in _b55_doc)
# **문면을 조각으로 쓴다** — 이 줄이 「층 그래프 파일을 아는 코드」 검사(test_g1_g2)에
# 걸리지 않게. `doctor.py`가 같은 이유로 `"graph" + ".json"`을 쓴다(레포의 관용).
show("⑨ snap()이 층 그래프 파일을 바이트로 여는 근거가 주석에 있다 (B6 예외 명시)",
     "B6(GraphStore 경유)의 예외이고" in _b55_doc)

# ── B58 ② 기계 관문의 범위 = 파서 전 구간 ────────────────────────────────

done()
