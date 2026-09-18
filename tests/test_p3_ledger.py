# -*- coding: utf-8 -*-
"""P3 ⑦ 대장 — 관문이 채우고 찍는다 · columns 값 셋 · 어휘 정적 대조 · 형태 판정 문의."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_common import *                       # noqa: F401,F403 — 바닥은 하나다
from p3_common import _P, _reg_src            # noqa: F401 — `*`는 밑줄 이름을 건너뛴다

from parser import form as _FORM
import os as _os
import tempfile as _tf

setup()


print("\n■ B62 — 관문이 채우고 찍는다 · 재시도의 기본은 이어가기")

_fx63 = Path(_tf.mkdtemp(prefix="fx63_", dir=str(ROOT)))
(_fx63 / "fixtures/adapters").mkdir(parents=True)
(_fx63 / "fixtures/schemas").mkdir(parents=True)
# **LLM이 쓴 header_labels에 한 글자 오타**가 있는 어댑터 — ①-a 이전 코드의 산출이다.
_AD63 = '''# -*- coding: utf-8 -*-
from parser import normalizer

ADAPTER = {
    "doc_type": "%s",
    "adapter_version": "1.0",
    "payload_kind": "table",
    "expects": {
        "header_row": 1,
        "data_start_row": 2,
        "header_labels": ["대공정", "세부공정", "공정번호", "설비",
                          "관리항목", "규격", "측정방"],
        "columns": {"process_group": "A", "process_ref": "B", "process_no": "C",
                    "설비": "D", "관리항목": "E", "규격": "F", "측정방법": "G"},
        "multi_value_seps": [",", "/"],
        "multi_value_fields": ["설비"],
        "required": ["process_ref", "설비", "관리항목"],
    },
}


def extract(raw) -> list[dict]:
    exp = ADAPTER["expects"]
    out = []
    for sheet in raw.get("sheets", []):
        cells = normalizer.expand_merged(sheet)
        for row in range(exp["data_start_row"], int(sheet.get("max_row", 0)) + 1):
            rec = {f: str(cells.get("%%s%%d" %% (c, row), "") or "").strip()
                   for f, c in exp["columns"].items()}
            if all(v == "" for v in rec.values()):
                continue
            rec["source_locator"] = "%%s!R%%d" %% (sheet.get("name", "sheet"), row)
            out.append(rec)
    out, _ = normalizer.split_multi(out, exp["multi_value_fields"], exp["multi_value_seps"])
    return out
'''
_SC63 = {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")),
         "fields": {"설비": {"role": "entity", "category": "Unit"},
                    "관리항목": {"role": "entity", "category": "Property"},
                    "규격": {"role": "attribute", "attach_to_field": "관리항목",
                           "attr_name": "spec", "contextual": True, "optional": True},
                    "측정방법": {"role": "attribute", "attach_to_field": "관리항목",
                              "optional": True}},
         "edges": []}
for _dt in ("csv63", "csv63_rev1"):
    (_fx63 / f"fixtures/adapters/{_dt}.py").write_text(_AD63 % "csv63", encoding="utf-8")
    (_fx63 / f"fixtures/schemas/{_dt}.json").write_text(
        json.dumps({**_SC63, "doc_type": "csv63"}, ensure_ascii=False), encoding="utf-8")
_e63 = {**_os.environ, "ONTO_FIXTURES": str(_fx63)}
_CSV63 = str(RAW / "CSV05_wide.csv")


def _reg63(*a):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *a,
                           "--allow-mock"], capture_output=True, text=True,
                          cwd=str(ROOT), env=_e63, stdin=subprocess.DEVNULL)


reset("csv63")
_g63 = _reg63("generate", "csv63", "process", _CSV63, "--no-basic")
_st63 = json.loads((REVIEW / "csv63" / "state.json").read_text(encoding="utf-8"))
_mod63 = R._load(Rdraft._at(_st63["adapter"]), "b62_csv63")
_actual63 = _PF63 = None
from parser import preflight as _PFM                              # noqa: E402
_actual63 = _PFM.header_labels(reader.read(_CSV63), 1, _mod63.ADAPTER["expects"])
# ①ⓐ **CSV table 어댑터가 관문을 지난다** — 구판은 무조건 G52 adapter_mismatch였다.
show("①ⓐ CSV 표본으로 관문 PASS · orphan 0 (구판은 무조건 adapter_mismatch)",
     _g63.returncode == 0 and _st63["machine_gate"] == "PASS"
     and not Rgate.fail_lines(_g63.stdout), str(Rgate.fail_lines(_g63.stdout)[:1]))
show("①ⓐ 어댑터의 header_labels가 표본 실물과 같다 (LLM 오타를 시스템이 덮었다)",
     _mod63.ADAPTER["expects"]["header_labels"] == _actual63
     and "측정방" not in _mod63.ADAPTER["expects"]["header_labels"],
     str(_actual63))
# **원본은 손대지 않는다** — fixture는 외부 LLM 실산출 스냅샷이다(D-26).
show("① 채우기는 작업 사본에만 한다 (fixture 원본 무손질 · D-26)",
     "시스템이 채운다" not in (_fx63 / "fixtures/adapters/csv63.py").read_text(encoding="utf-8")
     and str(_st63["adapter"]).startswith("review/"))
# ③ **판 번호는 시스템이 찍는다** — state.revision과 같은 카운터 하나다.
show("③ adapter_version 끝자리 == state.revision (LLM이 쓴 1.0을 무시한다)",
     _mod63.ADAPTER["adapter_version"] == f"1.{_st63['revision']}",
     f"{_mod63.ADAPTER['adapter_version']} · revision {_st63['revision']}")
# ①ⓓ **①-a 이전 코드로 만든 review/를 그대로 두고** status → confirm. LLM 0.
_old63 = REVIEW / "csv63old"
_old63.mkdir(parents=True, exist_ok=True)
(_old63 / "adapter.py").write_text(_AD63 % "csv63old", encoding="utf-8")
(_old63 / "schema.json").write_text(
    json.dumps({**_SC63, "doc_type": "csv63old"}, ensure_ascii=False), encoding="utf-8")
(_old63 / "input_package.json").write_text(json.dumps(
    {"human": {"doc_type": "csv63old", "layer": "process", "samples": [_CSV63],
               "hint": ""},
     "system": {"reader_head": [], "skeleton_closed_list": {}, "layer_vocabulary": {},
                "blocks": {}, "adapter_skeleton": ""}}, ensure_ascii=False), encoding="utf-8")
(_old63 / "state.json").write_text(json.dumps(
    {"doc_type": "csv63old", "layer": "process", "samples": [_CSV63],
     "adapter": "review/csv63old/adapter.py", "schema": "review/csv63old/schema.json",
     "revision": 0, "instructions": [], "machine_gate": "FAIL",
     "harness_out": "  [FAIL] 계약 self-check 통과  — adapter_mismatch"},
    ensure_ascii=False), encoding="utf-8")
_s63 = _reg63("status", "csv63old")
_c63 = _reg63("confirm", "csv63old", "--by", "사내")
show("①ⓓ 옛 review/를 그대로 두고 status → PASS · confirm 성공 (재생성 없이)",
     _s63.returncode == 0 and _c63.returncode == 0
     and registry.lookup("csv63old") is not None,
     f"status rc={_s63.returncode} · confirm rc={_c63.returncode}")
show("①ⓓ 그 경로에 LLM 호출 0 (mock 로그 0줄)",
     "MOCK" not in _s63.stdout and "MOCK" not in _c63.stdout)
reset("csv63old")

# ④ **재시도의 기본은 이어가기** — 구판은 기본값이 막다른 길이었다.
_RSRC63 = _reg_src()
_ask63 = _RSRC63.split("def _ask_more")[1].split("\ndef ")[0]
show("④ⓑ 비대화형 기본이 Y다 (구판은 N — 기본값이 막다른 길이었다)",
     'ans not in ("n", "no")' in _ask63 and "[Y/n]" in _ask63)
show("④ⓑ GATE_SELF만 남으면 _ask_more를 부르지 않는다",
     "all(c in GATE_SELF for c in _codes)" in _RSRC63
     and _RSRC63.index("all(c in GATE_SELF for c in _codes)")
     < _RSRC63.index("if tries >= 1 and not _ask_more("))
shutil.rmtree(_fx63, ignore_errors=True)
reset("csv63")


# ── B62 ② 라운드 전문은 패키지 밖으로 ────────────────────────────────────
print("\n■ B62 ② — 대화는 이력(로그), 판단은 정본(패키지)")

_fx64 = Path(_tf.mkdtemp(prefix="fx64_", dir=str(ROOT)))
(_fx64 / "fixtures/adapters").mkdir(parents=True)
(_fx64 / "fixtures/schemas").mkdir(parents=True)
(_fx64 / "fixtures/adapters/b64.py").write_text(
    (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
    .replace('"doc_type": "cp"', '"doc_type": "b64"', 1), encoding="utf-8")
(_fx64 / "fixtures/schemas/b64.json").write_text(json.dumps(
    {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")),
     "doc_type": "b64"}, ensure_ascii=False), encoding="utf-8")
_e64 = {**_os.environ, "ONTO_FIXTURES": str(_fx64)}


def _reg64(*a, feed=""):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", *a,
                           "--allow-mock"], capture_output=True, text=True,
                          cwd=str(ROOT), env=_e64, input=feed)


reset("b64")
_reg64("generate", "b64", "process", str(RAW / "CP01.xlsx"), "--interview", "--no-basic",
       feed="1\n\n헤더는 3행이다\n진행\nY\n")
_pk64 = json.loads((REVIEW / "b64" / "input_package.json").read_text(encoding="utf-8"))
_lg64 = json.loads((REVIEW / "b64" / "interview_log.json").read_text(encoding="utf-8"))
_b64 = Rivlog._hint_batches(_pk64["human"]["hint"])[-1]

# ⓑ **패키지에 전문이 없다** — 생성 user 메시지가 패키지 원문 통째이므로
# 패키지가 깨끗해야 보내는 것이 깨끗하다(걷어내는 방식은 잊을 자리를 만든다).
show("②ⓑ 패키지 묶음에 rounds가 없다 (전문은 로그로 갔다)",
     "rounds" not in _b64 and set(_b64) == {"samples", "at", "decisions"},
     str(sorted(_b64)))
show("②ⓑ 로그에 전문이 그대로 있다 — at으로 짝이 맞는다 (버린 것이 아니다)",
     sum(len(b["rounds"]) for b in _lg64["batches"]) >= 2
     and {b["at"] for b in _lg64["batches"]} >= {_b64["at"]})
show("②ⓑ decisions는 패키지에 그대로다 (생성이 읽는 것이 그것이다)",
     len(_b64["decisions"]) >= 1
     and all({"topic", "decision", "reason"} <= set(d) for d in _b64["decisions"]))
# ⓒ **렌더가 전문을 알지 못한다** — 자리가 없으면 되살아날 길이 없다.
show("②ⓒ 렌더러가 rounds를 모른다 (cli/prompt.py에 그 문자열 0줄)",
     '"rounds"' not in (ROOT / "cli" / "prompt.py").read_text(encoding="utf-8"))

# ⓐ **라운드가 30개 늘어도 보내는 크기가 같다** — 전문이 입력이 아니기 때문이다.
def _sent64():
    _raw = (REVIEW / "b64" / "input_package.json").read_text(encoding="utf-8")
    _sys = _PR64._render_template(_PR64.generate_template(),
                                  json.loads(_raw), regeneration=[])
    return len(_sys.encode("utf-8")), len(_raw.encode("utf-8"))


from cli import prompt as _PR64                                   # noqa: E402
_before64 = _sent64()
_lg64["batches"][0]["rounds"] += [
    {"round": i, "understanding": "열별 판독 선언 " * 40, "questions": [],
     "answers": [], "answer": "답" * 60, "progress": {}} for i in range(50, 80)]
(REVIEW / "b64" / "interview_log.json").write_text(
    json.dumps(_lg64, ensure_ascii=False), encoding="utf-8")
_after64 = _sent64()
show("②ⓐ 로그에 라운드 30개를 더해도 생성이 보내는 크기가 같다",
     _before64 == _after64 and _before64[1] > 0,
     f"user {_before64[1]:,}B → {_after64[1]:,}B")

# ⓓ **B60 이전 패키지** — 이관 한 줄 + 확정 사항 없음 경고 + **진행은 된다**.
reset("b64old")
(_fx64 / "fixtures/adapters/b64old.py").write_text(
    (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
    .replace('"doc_type": "cp"', '"doc_type": "b64old"', 1), encoding="utf-8")
(_fx64 / "fixtures/schemas/b64old.json").write_text(json.dumps(
    {**json.loads((ROOT / "tests/fixtures/schemas/cp.json").read_text(encoding="utf-8")),
     "doc_type": "b64old"}, ensure_ascii=False), encoding="utf-8")
_d64 = REVIEW / "b64old"
_d64.mkdir(parents=True, exist_ok=True)
(_d64 / "input_package.json").write_text(json.dumps(
    {"human": {"doc_type": "b64old", "layer": "process",
               "samples": [str(RAW / "CP01.xlsx")],
               "hint": {"text": "", "interview": [
                   {"samples": [str(RAW / "CP01.xlsx")], "at": "2026-09-01T00:00:00+00:00",
                    "rounds": [{"round": i, "understanding": f"이해 {i}", "questions": [],
                                "answers": [], "answer": f"답 {i}", "progress": {}}
                               for i in (1, 2, 3)]}]}},
     "system": {"reader_head": [], "skeleton_closed_list": {}, "layer_vocabulary": {},
                "blocks": {}, "adapter_skeleton": ""}}, ensure_ascii=False),
    encoding="utf-8")
_r64 = _reg64("generate", "b64old", "--resume")
_pk64o = json.loads((_d64 / "input_package.json").read_text(encoding="utf-8"))
_b64o = Rivlog._hint_batches(_pk64o["human"]["hint"])[0]
_lg64o = json.loads((_d64 / "interview_log.json").read_text(encoding="utf-8"))
show("②ⓑ 옛 꼴 패키지를 읽으면 로그가 생기고 패키지에서 rounds가 사라진다",
     "rounds" not in _b64o
     and sum(len(b["rounds"]) for b in _lg64o["batches"]) == 3
     and _lg64o["batches"][0]["at"] == _b64o["at"])
# **죽지 않는다** — 경고이지 거부가 아니다. 다음 줄 둘이 함께 온다.
_nx64 = [l for l in _r64.stdout.splitlines() if "register review b64old" in l
         or "register generate b64old" in l]
show("②ⓓ decisions 없는 옛 패키지 — 경고가 뜨고 **진행은 된다** (다음 줄 둘)",
     _r64.returncode == 0 and not _b64o.get("decisions") and len(_nx64) >= 2,
     f"rc={_r64.returncode} · 다음 줄 {len(_nx64)}개")
# **이어하기 화면이 전문 건수를 안다** — 패키지에 없는 것을 패키지에서 세지 않는다.
_n64 = [l for l in _r64.stdout.splitlines() if "라운드 전문" in l]
show("②ⓑ 이어하기 화면의 라운드 건수가 로그에서 온다 (패키지에는 전문이 없다)",
     len(_n64) == 1
     and str(sum(len(b["rounds"]) for b in _lg64o["batches"])) in _n64[0]
     and "rounds" not in _b64o,
     _n64[0].strip() if _n64 else "(줄 없음)")
# **힌트만 준 패키지는 해당 없음** — `hint_only_decisions`가 이미 한 항목을 세운다.
show("②ⓓ 힌트만 준 패키지는 경고 대상이 아니다 (결정이 이미 있다)",
     Rivlog.warn_no_decisions("x", {"human": {"hint": {"text": "h", "interview": [
         {"samples": [], "at": "t", "decisions": Rivlog.hint_only_decisions("h")}]}}}) is None)
reset("b64old")
reset("b64")
shutil.rmtree(_fx64, ignore_errors=True)


# ── B64 ①②③ columns는 시스템이 해석한다 ─────────────────────────────────
print("\n■ B64 — columns 값 셋(열문자·라벨·합치기)을 시스템이 열문자로 확정한다")

from parser import preflight as _PF64                             # noqa: E402

# 같은 라벨이 두 열(D·G)에 있는 표본을 만든다 — 사내 실측의 모양이다.
_d64 = Path(_tf.mkdtemp(prefix="b64_", dir=str(ROOT)))
_csv64 = _d64 / "dup64.csv"
_csv64.write_text("대공정,세부공정,공정번호,Center,관리항목,규격,Center\n"
                  "조립,노칭,OP-10,노칭 프레스,노칭 정밀도,±0.05mm,\n"
                  "조립,노칭,OP-10,,버 높이,10um 이하,비전 측정기\n"
                  "조립,스태킹,OP-20,스태커,적층 정렬도,±0.1mm,\n", encoding="utf-8")
_raw64 = reader.read(str(_csv64))
_exp64 = {"header_row": 1,
          "columns": {"a": "대공정", "center": ["Center", "G"], "amb": "Center",
                      "empty": "ZZ", "nope": "없는이름"}}
_cols64, _bad64 = _PF64.resolve_columns(_raw64, _exp64)
_by64 = {b["field"]: b for b in _bad64}

# ③ **대응은 리스트다** — 같은 라벨의 둘째 열이 사라지지 않는다.
_lab64 = _PF64.label_columns(_raw64, _exp64)
show("③ 중복 헤더 라벨의 대응이 열 전부를 담는다 (둘째 열이 사라지지 않는다)",
     _lab64.get("Center") == ["D", "G"] and _lab64.get("대공정") == ["A"],
     str(_lab64.get("Center")))
# ①ⓑ **라벨 → 열문자 확정** · **합치기 리스트는 펼쳐진다**
show("①ⓑ 헤더 라벨이 열문자로 확정된다 (세는 일은 시스템 몫)",
     _cols64["a"] == "A" and "a" not in _by64)
show("①ⓑ 합치기 리스트의 라벨은 그 이름의 열 전부로 펼쳐진다 (중복 제거)",
     _cols64["center"] == ["D", "G"])
# ①ⓑ **원인 셋이 서로 다르다** — 「header_row 의심」 하나로 뭉치지 않는다(②ⓑ).
show("②ⓑ 세 원인이 서로 다른 코드로 갈린다 (중복·없음·빈 헤더)",
     _by64["amb"]["reason"] == "ambiguous" and _by64["nope"]["reason"] == "not_found"
     and _by64["empty"]["reason"] == "empty"
     and _by64["amb"]["candidates"] == ["D", "G"],
     " · ".join(f"{k}:{v['reason']}" for k, v in sorted(_by64.items())))
show("①ⓑ 중복 라벨의 상세에 후보 열문자 목록이 있다 (다음 값이 문면에 있다)",
     _by64["amb"].get("candidates") and _by64["nope"].get("headers"))
# **멱등** — 열문자로 확정된 뒤 다시 지나도 같다(관문 입구 → 하네스 두 번 지난다).
show("① 해석은 멱등이다 (열문자를 다시 해석해도 같다)",
     _PF64.resolve_columns(_raw64, {**_exp64, "columns": _cols64})[0] == _cols64)
# ①ⓑ **합치기** — 앞에서부터 첫 비지 않은 값. D가 비면 G를 쓴다.
_sk64 = {"header_row": 1, "data_start_row": 2, "columns": {"center": ["D", "G"]}}
_cells64 = (_raw64["sheets"][0].get("cells") or {})
_merge64 = []
for _r in (2, 3, 4):
    _v = ""
    for _c in _sk64["columns"]["center"]:
        _v = _cells64.get(f"{_c}{_r}", "")
        if _v is not None and str(_v).strip():
            break
    _merge64.append(str(_v).strip())
show("①ⓑ 합치기는 앞에서부터 첫 비지 않은 값이다 (D가 비면 G)",
     _merge64 == ["노칭 프레스", "비전 측정기", "스태커"], str(_merge64))
# ①ⓑ **orphan 집합이 리스트를 펼친다** — 합쳐진 둘째 열은 쓴 열이다.
show("①ⓑ 쓴 열 집합이 리스트를 펼친다 (합쳐진 열은 orphan이 아니다)",
     Rledger.col_values({"x": ["D", "G"], "y": "A"}) == {"D", "G", "A"})

# ── ⑤ C38 잠금 — 시스템 필드는 LLM 출력과 무관하다 (문서 1 C38 · 칸 1.5) ──────
#
# **LLM은 고르고, 시스템이 쓴다.** 초안이 무엇을 썼든 저장본의 시스템 필드는
# **표본에서 독립적으로 재계산한 값**이다. 시스템 필드가 늘면 아래 표에 행을 더한다.
_draft64 = _d64 / "c38_draft.py"
_draft64.write_text(
    "ADAPTER = {\n"
    "    'doc_type': 'c38t', 'adapter_version': '9.9', 'payload_kind': 'table',\n"
    "    'expects': {'header_row': 1, 'data_start_row': 2,\n"
    "                'header_labels': ['대공정', '세부공정', '공정번호', 'Centre',\n"
    "                                  '관리항목', '규격', 'Centre'],\n"
    "                'columns': {'process': '대공정', 'center': ['Center', 'G'],\n"
    "                            'item': '관리항목'}},\n"
    "}\n\n\n"
    "def extract(raw, struct_map_fn=None):\n"
    "    return []\n", encoding="utf-8")
_st64 = {"doc_type": "c38t", "adapter": str(_draft64.relative_to(ROOT)), "revision": 0}
Rgate.stamp_system_fields(_st64, [str(_csv64)])
_after64 = R._load(Rdraft._at(_st64["adapter"]), "c38_after").ADAPTER
_exp_after = _after64["expects"]


def _recompute64():
    """표본에서 **독립적으로** 다시 센다 — 저장본을 읽지 않는다."""
    raw = reader.read(str(_csv64))
    draft = R._load(_draft64, "c38_draft_ro").ADAPTER["expects"]
    return {"header_labels": _PF64.header_labels(raw, draft["header_row"], draft),
            "adapter_version": f"1.{_st64.get('revision', 0)}",
            "columns": _PF64.resolve_columns(raw, draft)[0]}


_re64 = _recompute64()
show("⑤ C38 — 저장본의 시스템 필드가 표본 재계산값과 같다 (LLM 출력과 무관)",
     _exp_after["header_labels"] == _re64["header_labels"]
     and _after64["adapter_version"] == _re64["adapter_version"]
     and _exp_after["columns"] == _re64["columns"],
     f"판 {_after64['adapter_version']} · center {_exp_after['columns'].get('center')}")
# **초안이 틀린 값을 써도 붉어지지 않는다 — 덮는 것이 성질이다.**
_dr64 = R._load(_draft64, "c38_draft_chk").ADAPTER
show("⑤ 초안의 틀린 값 셋이 저장본에 남지 않는다 (오타 라벨 · 9.9 · 라벨 표기)",
     "Centre" in _dr64["expects"]["header_labels"]
     and "Centre" not in _exp_after["header_labels"]
     and _dr64["adapter_version"] == "9.9" and _after64["adapter_version"] == "1.0"
     and _dr64["expects"]["columns"]["center"] == ["Center", "G"]
     and _exp_after["columns"]["center"] == ["D", "G"])
# **변이 — 스탬프를 끄면 붉어진다**(그리고 되돌린다). 스탬프가 없으면 관문이 읽는
# 것은 초안 그대로이고, 그 값은 재계산값과 다르다 — 그것이 C38이 막는 상태다.
_st64["adapter"] = str(_draft64.relative_to(ROOT))     # 작업 사본 이전으로 되돌린다
shutil.rmtree(R.REVIEW / "c38t", ignore_errors=True)
_keep64, Rgate.stamp_system_fields = Rgate.stamp_system_fields, lambda st, samples: None
try:
    Rgate.stamp_system_fields(_st64, [str(_csv64)])
    _off64 = R._load(Rdraft._at(_st64["adapter"]), "c38_off").ADAPTER
finally:
    Rgate.stamp_system_fields = _keep64
show("⑤ 변이 — 스탬프를 끄면 초안 값이 남아 붉어진다 (되돌리면 초록)",
     _off64["adapter_version"] == "9.9"
     and "Centre" in _off64["expects"]["header_labels"]
     and _off64["expects"]["columns"]["center"] == ["Center", "G"]
     and _recompute64()["adapter_version"] == "1.0")
_sh64 = shutil.rmtree(_d64, ignore_errors=True)

# ── B65 ①② 하네스가 LLM 산출을 실행 전에 어휘로 거른다 ──────────────────
print("\n■ B65 — 어휘가 닫힌 자리는 실행 전에 정적으로 대조한다")

_d65 = Path(_tf.mkdtemp(prefix="b65_", dir=str(ROOT)))
_cp65 = (ROOT / "tests/fixtures/adapters/cp.py").read_text(encoding="utf-8")
_sc65 = _P.fixture_schemas("cp.json")


def _gate65(adapter_src, schema=_sc65, name="a"):
    """어댑터 원문으로 관문을 한 번 돌린다 — 판정 줄만 돌려준다."""
    f = _d65 / f"{name}.py"
    f.write_text(adapter_src, encoding="utf-8")
    _ok, _out = Rgate.harness(f, schema, [RAW / "CP01.xlsx"])
    return {c: (l, d) for c, l, d in Rgate.fail_lines(_out)}, _out


# ①ⓑ **없는 이름은 로드 단계에서 잡힌다** — 실행(G31)까지 가지 않는다.
_bad65, _out65 = _gate65(
    _cp65.replace("    fragments = []",
                  "    fragments = []\n    _x = normalizer.col_to_letter(3)", 1),
    name="badcall")
show("①ⓑ 없는 normalizer 이름이 로드 단계에서 FAIL이다 (실행 전에 걸린다)",
     "G1B" in _bad65 and "G31" not in _bad65,
     f"{sorted(_bad65)} · 상세 {_bad65.get('G1B', ('', ''))[1][:40]}")
show("①ⓑ 상세가 있는 것의 목록을 담는다 (AUTO_FIX — 사람이 통역하지 않는다)",
     all(k in _bad65["G1B"][1] for k in ("col_to_letter", "expand_merged", "split_multi"))
     and not Rgate.classify_failures(_out65)[1])
# **비공개 이름도 FAIL** — 오늘 도는 것이 다음 판에 사라져도 약속 위반이 아니다.
_priv65, _ = _gate65(
    _cp65.replace("    fragments = []",
                  "    fragments = []\n    _x = normalizer._col(3)", 1), name="priv")
show("①ⓑ 밑줄 이름(비공개) 참조도 FAIL이다", "G1B" in _priv65)
# **있는 이름만 쓰면 PASS** — 시험 자체가 늘 붉는 것이 아니다.
_good65, _ = _gate65(_cp65, name="good")
show("①ⓑ 있는 이름만 쓴 어댑터는 G1B가 뜨지 않는다", "G1B" not in _good65,
     str(sorted(_good65)))

# ②ⓑ **어휘 셋** — 목록 밖 값은 FAIL이고 문면이 목록을 담는다.
_pf65 = json.loads((ROOT / "tests/fixtures/schemas/pfmea.json").read_text(encoding="utf-8"))
_pfa65 = ROOT / "tests/fixtures/adapters/pfmea.py"


def _vgate65(mut, name):
    sch = json.loads(json.dumps(_pf65))
    mut(sch)
    f = _d65 / f"s_{name}.json"
    f.write_text(json.dumps(sch, ensure_ascii=False), encoding="utf-8")
    _ok, _out = Rgate.harness(_pfa65, f, [RAW / "PFMEA01.xlsx"])
    return {c: (l, d) for c, l, d in Rgate.fail_lines(_out)}, _out


def _set_cat(s):
    s["fields"]["cause"]["category"] = "Cause"


def _set_rel(s):
    s["edges"][0]["relation"] = "cause_of"


def _set_tri(s):
    s["edges"][1]["to"] = "cause"


_c65, _co65 = _vgate65(_set_cat, "cat")
_r65, _ro65 = _vgate65(_set_rel, "rel")
_t65, _to65 = _vgate65(_set_tri, "tri")
show("②ⓑ 층 목록 밖 category가 FAIL이고 있는 것이 문면에 있다 (G4C)",
     "G4C" in _c65 and "Cause" in _c65["G4C"][1] and "Failure" in _c65["G4C"][1],
     _c65.get("G4C", ("", ""))[1][:70])
show("②ⓑ 층 목록 밖 relation이 FAIL이고 있는 것이 문면에 있다 (G4D)",
     "G4D" in _r65 and "cause_of" in _r65["G4D"][1] and "affects" in _r65["G4D"][1],
     _r65.get("G4D", ("", ""))[1][:70])
show("②ⓑ 패턴표 밖 삼항이 FAIL이고 허용 삼항이 문면에 있다 (G4E)",
     "G4E" in _t65 and "affects" in _t65["G4E"][1]
     and "FailureEffect" in _t65["G4E"][1],
     _t65.get("G4E", ("", ""))[1][:70])
show("②ⓑ 셋 다 AUTO_FIX 갈래다 (문면이 목록을 담는다)",
     all(not Rgate.classify_failures(o)[1] for o in (_co65, _ro65, _to65)))
# **걸침 필드는 대상 층의 목록으로 · `@좌표필드`는 블록의 target_category로 판정**
_ok65, _ = Rgate.harness(_pfa65, ROOT / "tests/fixtures/schemas/pfmea.json", [RAW / "PFMEA01.xlsx"]), None
_pass65, _pout65 = Rgate.harness(_pfa65, ROOT / "tests/fixtures/schemas/pfmea.json", [RAW / "PFMEA01.xlsx"])
_codes65 = [c for c, _l, _d in Rgate.fail_lines(_pout65)]
show("②ⓑ 걸침 필드(target_layer)·@좌표필드가 있는 스키마가 초록이다 "
     "(다른 층 카테고리를 오판하지 않는다)",
     not [c for c in _codes65 if c in ("G4C", "G4D", "G4E")], str(_codes65))
shutil.rmtree(_d65, ignore_errors=True)

# ── B65 ④⑤ 형태 판정은 사람에게 · 고정 어댑터는 재생성 대상이 아니다 ────────
print("\n■ B65 ⑤ — 형태 판정이 안 서면 사람에게 묻는다 (C37 「그 외는 사람」)")

_d66 = Path(_tf.mkdtemp(prefix="b65f_", dir=str(ROOT)))
_amb66 = _d66 / "amb.csv"
_rows66 = [["내용", "비고", "쪽"]]
for _i in range(1, 5):
    _rows66.append([f"{_i}. 장 제목 {_i}", "", ""])
    for _j in range(1, 4):
        _rows66.append([f"{_i}.{_j} 절 제목 {_j}", "", ""])
        for _k in range(3):
            _rows66.append([f"본문 문장 {_i}-{_j}-{_k} — 설명이 길게 이어지는 줄이다",
                            "", ""])
_amb66.write_text("\n".join(",".join(r) for r in _rows66) + "\n", encoding="utf-8")

_j66 = _FORM.judge(reader.read(str(_amb66)))
show("⑤ 표본이 자동 판정되지 않는다 (시험의 전제 — 찬성≥2·반대0 미충족)",
     _j66["verdict"] is None and not _j66["auto"], _j66["why"][:50])


def _gen66(*args, feed=""):
    return subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "generate",
                           "b65f", "process", str(_amb66), *args, "--allow-mock"],
                          capture_output=True, text=True, cwd=str(ROOT), input=feed)


reset("b65f")
_r66 = _gen66(feed="prose\n")
_st66 = json.loads((REVIEW / "b65f" / "state.json").read_text(encoding="utf-8"))
# ⓑ **판정이 안 서면 draft 전에 사람 입력 또는 플래그가 있어야 한다.**
show("⑤ⓑ 판정이 안 서면 화면이 신호·투표를 보이고 묻는다",
     "형태 판정" in _r66.stdout and "자동 판정 불가" in _r66.stdout
     and "[table/prose]" in _r66.stdout)
show("⑤ⓑ prose 답이면 고정 어댑터로 가고 LLM 호출 0이다",
     _st66.get("use_basic") is True and "호출 0회" in _r66.stdout,
     f"use_basic={_st66.get('use_basic')}")
show("⑤ⓑ 판정과 **누가 정했나**가 상태에 남는다 (form.verdict · form.by)",
     (_st66.get("form") or {}).get("verdict") == "prose"
     and (_st66.get("form") or {}).get("by") == "human",
     str(_st66.get("form", {}).get("by")))
# ⓑ **비대화형은 상태 거부**(B61 계약) — 조용히 LLM 생성으로 가지 않는다.
reset("b65f")
_r66n = _gen66(feed="")
show("⑤ⓑ 비대화형은 상태 거부이고 다음 줄 둘을 준다 (조용히 생성으로 가지 않는다)",
     _r66n.returncode != 0 and "--use-basic" in _r66n.stdout + _r66n.stderr
     and "--no-basic" in _r66n.stdout + _r66n.stderr,
     f"rc={_r66n.returncode}")
# ⓑ **`--use-basic`은 verdict와 무관하게 prose다** — 사람이 플래그로 이긴다.
reset("b65f")
_r66b = _gen66("--use-basic")
_st66b = json.loads((REVIEW / "b65f" / "state.json").read_text(encoding="utf-8"))
show("⑤ⓑ --use-basic은 묻지 않고 고정 어댑터다 (판정과 무관)",
     _st66b.get("use_basic") is True and "[table/prose]" not in _r66b.stdout)

print("\n■ B65 ④ — 고정 어댑터 doc_type은 재생성 대상이 아니다")

_rv66 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "review",
                        "b65f", "--instruct", "레벨을 2로", "--allow-mock"],
                       capture_output=True, text=True, cwd=str(ROOT))
_rr66 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "generate",
                        "b65f", "process", str(_amb66), "--revise", "--allow-mock"],
                       capture_output=True, text=True, cwd=str(ROOT))
_both66 = _rv66.stdout + _rv66.stderr + _rr66.stdout + _rr66.stderr
show("④ⓑ instruct·revise 둘 다 거부이고 다음 줄 셋을 준다",
     "재생성 대상이 아니다" in _rv66.stdout + _rv66.stderr
     and "재생성 대상이 아니다" in _rr66.stdout + _rr66.stderr
     and all(k in _both66 for k in ("의 상수", "schemas/b65f.json", "--as <새이름>")))
# **LLM 0** — 거부이므로 생성 세션이 돌지 않는다.
show("④ⓑ 거부 경로에 LLM 호출이 없다 (draft를 부르지 않는다)",
     "MOCK ⑤구축 모드 생성" not in _both66 and "초안 수령" not in _both66)
# **status·confirm·플래그 없는 review는 그대로다** — 막는 것은 재생성뿐이다.
_sv66 = subprocess.run([sys.executable, str(ROOT / "run.py"), "register", "status",
                        "b65f", "--allow-mock"], capture_output=True, text=True,
                       cwd=str(ROOT))
show("④ⓑ status는 그대로 돈다 (막는 것은 재생성뿐)",
     "재생성 대상이 아니다" not in _sv66.stdout + _sv66.stderr
     and _sv66.returncode == 0, f"rc={_sv66.returncode}")
reset("b65f")
shutil.rmtree(_d66, ignore_errors=True)


# ── B66 ①② — 헤더 지문은 포맷을 보지 않는다 · 미선택은 네 갈래다 ──────────
#
# **셋째 자리였다.** `preflight.header_labels`의 `format != "xlsx"`(B62 ①-a) ·
# `cli/scan.py::_header_actual`의 복제본 · `FINGERPRINTABLE = ("xlsx",)`. 앞의 둘을
# 고치고도 CSV가 지문 대조에서 빠진 채 남은 이유는 **CSV 표본으로 스캔을 돌리는
# 어서션이 하나도 없어서**다. 여기가 그 자리다 — 포맷이 판정에 안 들어가는 것이
# 성질이고, 다시 들어오면 이 세 줄이 붉어진다.
from cli import scan as _s66                                       # noqa: E402
from cli import ingest as _i66                                     # noqa: E402

done()
