# -*- coding: utf-8 -*-
"""G6 — **골격 칸의 문 — LLM이 골격 목록을 보고 판단 · 사람 말을 LLM이 읽는다 · 처분 넷 · 한 표 한 고리 · 청크 화면 둘** (B202).

창작 표본(패키징 꼴 — 위 공정 「패키징」 아래 하위 공정 26 · 셋째 단 이름 `패키징::…` · 제목 「Side Sealing unit」(언어만 다름 — mock 겹침 판정은 띄어쓰기만 다른 「사이드실링 unit」을 바로 붙여 문에 걸리지 않는다) ·
「실링 지그」(부품) · 「검사 항목」(노드 아님)) · mock(창작 답 `tests/fixtures/gate_judge.json` · `gate_say.json` — 수치는 근거가
아니다 [정정] 50) · 물음은 진짜 고리(`cli/gate_table.loop`)에 답을 넣는다. 대표 사례 하나씩:
  ⓐ 첫 판단 다르다(관문 끝 — LLM 0) → LLM 판단 같다 · 후보 ① 패키징::사이드 실링 · 목록 밖 후보 버림
  ⓑ 말 → 해석 같은 것으로 → Enter → 골격 ALIASES · 처분 칸 ✓ 같은 것으로 → <경로>(고침 B203 — 처분 말 다섯)
  ⓒ 말 「이건 부품이야」 → 해석 고침(카테고리) → 문 떠남 · ✎ · 기록 · 지금의 판정 길(그 카테고리 노드)
  ⓓ 이름 셋 → 같은 노드 · 여럿이면 목록
  ⓔ 문 줄의 `r` · `p` 거부(기록 0) · 줄 하나에 `k` 단독
  ⓕ 확인이 Enter가 아니면 쓰기 0 · 사람 없는 실행은 LLM 0 · 쓰기 0
  ⓖ 같은 문서 재인입 → 판단 기억(LLM 0) · 같은 판단
  ⓗ 청크 목차 라벨 132칸 가운데 줄임 · 추출 진행 표 「붙을 노드」
네 벌(ⓘ)은 마감 한 줄의 네 벌 단계가 잰다.
"""
from __future__ import annotations

import contextlib
import io
import json

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g65_common import *          # noqa: F401,F403 — 바닥은 하나다
from g65_common import _P, done, overlay   # noqa: F401

from cli import _screen, gate_table as GT, ingest_screen as IS, extract_screen as XS   # noqa: E402
from core.build.entry import run_document                                              # noqa: E402
from core.state import fixtures as _FXR, gate_judge as GJ, gate_say as GS, oplog, provisional_hand as PH   # noqa: E402
from core.state.bootstrap import bootstrap, open_graph                                 # noqa: E402
from core.state.status import is_live                                                  # noqa: E402
from parser import tagger as TG                                                        # noqa: E402

print("\n■ B202 — 골격 칸의 문: LLM이 골격 목록을 보고 판단 · 사람 말을 LLM이 읽는다 · 처분 넷 · 표 · 청크 화면 둘")
HINTS = _FXR.EXTRACT_HINTS
_made = []
overlay(component=True, also=True)               # 공정이 sub · detail 단에서 Unit을 겸한다 · Component는 공정층 카테고리
_SUBS = ["파우치 포밍", "스택 삽입", "사이드 실링", "전해액 주액", "프리 실링", "탑 실링", "디개싱", "메인 실링", "폴딩", "외관 검사",
         "치수 검사", "절연 검사", "라벨링", "트레이 적재", "에이징 투입", "파우치 커팅", "파우치 공급", "탭 정렬", "실링 냉각",
         "리크 검사", "두께 측정", "중량 측정", "마킹", "세척", "건조", "포장"]
_sp = _P.layers("process", "skeleton.json")
_seed = json.loads(_sp.read_text(encoding="utf-8"))
for _it in _seed["TREE"][0]["조립"]:
    if isinstance(_it, dict) and "패키징" in _it:
        _it["패키징"] = list(_SUBS)
_sp.write_text(json.dumps(_seed, ensure_ascii=False, indent=2), encoding="utf-8")
bootstrap("process", echo=False)


def _doc(did, heads, coord="패키징"):
    """산문 — 문서 좌표 패키징 · 제목마다 Unit(목차 노드화 힌트) · 본문 한 줄."""
    chunks = [(f"H-{i}", f"{i}. {h}", f"{h}의 조건은 5N이다.") for i, h in enumerate(heads, 1)]
    (HINTS / f"{did}.json").write_text(json.dumps({loc: {"entities": [], "relations": []} for loc, _p, _t in chunks},
                                                  ensure_ascii=False), encoding="utf-8")
    (HINTS / f"{did}@outline.json").write_text(json.dumps({p: {"name": p.split(". ", 1)[1], "category": "Unit"}
                                                           for _l, p, _t in chunks}, ensure_ascii=False), encoding="utf-8")
    _made.append(did)
    pcs = [{**C1, "source_locator": loc, "doc_type": "ppt_process", "process_ref": coord, "text": t,
            "meta": {"section_path": path}} for loc, path, t in chunks]
    return {**PROSE, "doc_id": did, "doc_type": "ppt_process", "source_path": f"{did}.pptx", "doc_coord": coord,
            "chunks": TG.tag(pcs, nodes=TG.closed_list("process"), doc_type="ppt_process")}


def _go(env, answers=(), keep=None):
    """인입 — 골격 단 줄이 서면 진짜 고리에 `answers`를 차례로(끝나면 c) · 알림 · 화면 · 그 줄을 돌려준다."""
    notes, box, feed = [], io.StringIO(), list(answers)

    def nt(info):
        notes.append(info)
        if info.get("단계") == "골격단":
            if keep is not None:
                keep.extend(info["rows"])
            return GT.loop(info["rows"], "B202시험", title="골격 단 — 시험", ask=lambda q: feed.pop(0) if feed else "c")
        return None
    with contextlib.redirect_stdout(box):
        run_document(env, notice=nt, allow_duplicate=True)
    return notes, box.getvalue()


def _alias(name):
    return json.loads(_sp.read_text(encoding="utf-8")).get("ALIASES", {}).get(name, [])


def _ops():
    return len(oplog.read())


# ⓕ 사람 없는 실행 — 표만(LLM 0 · 쓰기 0) · ⓐ 첫 판단 · LLM 판단 · 후보 · 목록 밖 버림
_e1 = _doc("B202A", ["Side Sealing unit", "실링 지그", "검사 항목"])
_rows0, _all0 = [], []
with contextlib.redirect_stdout(io.StringIO()):
    run_document(_e1, notice=lambda i: (_all0.append(i), _rows0.extend(i["rows"]) if i.get("단계") == "골격단" else None)[1],
                 allow_duplicate=True)
_c0, _o0, _m0 = dict(GJ.CALLS), _ops(), GJ._memo_path().exists()
_b0 = io.StringIO()
with contextlib.redirect_stdout(_b0):
    GT.show([dict(r) for r in _rows0], "골격 단 — 시험")
show("B202 ⓕ 사람 없는 실행 — 골격 단 줄 셋은 표만(판단 칸 「LLM 0 — 사람 없는 실행」) · LLM 0 · 쓰기 0(판단 기억 · 사람 판단 기록)",
     len(_rows0) == 3 and GJ.CALLS == _c0 and _ops() == _o0 and not _m0 and not GJ._memo_path().exists()
     and _b0.getvalue().count("LLM 0 — 사람 없는 실행") == 3,
     f"줄 {[r['surface'] for r in _rows0]} · 호출 {GJ.CALLS}")
_sr = next((r for r in _rows0 if r["surface"] == "Side Sealing unit"), {})
_j = GJ.judge([dict(_sr)])[0]
show("B202 ⓐ 「Side Sealing unit」 — 지금 코드의 첫 판단은 다르다(이름 겹침 0 — 코드 판정은 같은 것을 보지 못한다) · LLM 판단 같다 · 후보 ① 패키징::사이드 실링 · "
     "확실도 · 까닭 · 목록 밖 후보 버림 · LLM이 본 목록 = 패키징 아래 26",
     _sr.get("answer") == "new" and _j["llm"]["verdict"] == "같다" and _j["candidates"][0]["name"] == "패키징::사이드 실링"
     and _j["llm"]["confidence"] > 0.5 and _j["llm"]["why"] and _j["llm"]["dropped"] == ["없는 노드"] and len(_j["skeleton"]) == 26,
     f"첫 판단 {_sr.get('answer')} · LLM {_j['llm']['verdict']} {_j['llm']['confidence']} · 후보 {[c['name'] for c in _j['candidates']]}")

# ⓖ 같은 문서 재인입 → 판단 기억(LLM 0) · 같은 판단 (처분 없이 c)
_k1 = []
_go(_e1, [], keep=_k1)
_c1 = GJ.CALLS["첫 판단"]
_k2 = []
_go(_e1, [], keep=_k2)
show("B202 ⓖ 같은 문서 재인입 — 판단 기억(표기 · 위 공정 · 골격 판)으로 LLM 0 · 같은 판단 · 판단 칸 「LLM 0 — 판단 기억」",
     len(_k2) == 3 and GJ.CALLS["첫 판단"] == _c1 and [r["llm"] for r in _k1] == [r["llm"] for r in _k2]
     and all(r.get("llm0") == "판단 기억" for r in _k2),
     f"호출 {GJ.CALLS} · 기억 {[r.get('llm0') for r in _k2]}")

# ⓔ 문 줄의 r · p → 거부(기록 0) · ⓕ 확인이 Enter가 아니면 쓰기 0 · ⓑ 말 → 같다 → Enter → ALIASES · ✓ · ⓒ 해석 고침
_o1, _a1 = _ops(), list(_alias("패키징::사이드 실링"))
_n, _out = _go(_e1, ["r 1", "p 1", "1 사이드 실링이랑 같은 거", "아니", "1 사이드 실링이랑 같은 거", "", "2 이건 부품이야", ""])
show("B202 ⓔ 문 줄에 `r 1` · `p 1` → 거부 문면(그 줄 · 쓸 수 있는 것) · 기록 0 · 다시 묻는다",
     "[거부] 1번(문)에는 'r'" in _out and "[거부] 1번(문)에는 'p'" in _out
     and not any(r.get("op") == "provisional:promote" for r in oplog.read()[_o1:]), _out[:0])
show("B202 ⓕ 해석을 보인 뒤 Enter가 아니면(「아니」 — 다시 말하기) 쓰기 0 · 다음 말로 간다",
     "[해석 못 함]" in _out and _out.index("[해석 못 함]") < _out.index("같은 것으로 —"), "")
_g = open_graph("process")
show("B202 ⓑ 말 「1 사이드 실링이랑 같은 거」 → 해석(LLM) 같다 → 패키징::사이드 실링 → Enter → 골격 ALIASES에 그 표기(합침과 같은 기록) · "
     "처분 칸 「✓ 같은 것으로 → 조립 › 패키징 › 사이드 실링」(고침 B203)",
     "해석(LLM) — 1번 = 같은 것으로 → 패키징::사이드 실링" in _out and "Side Sealing unit" in _alias("패키징::사이드 실링")
     and not _a1 and "✓ 같은 것으로 → 조립 › 패키징 › 사이드 실링" in _out
     and any(r.get("op") == PH.OP_MERGE for r in oplog.read()[_o1:]), "")
_rr = [r for r in oplog.read()[_o1:] if r.get("op") == PH.OP_REREAD]
_jig = [n for n in _g.nodes.values() if is_live(n) and n["canonical"].endswith("실링 지그")]
show("B202 ⓒ 말 「2 이건 부품이야」(「실링 지그」) → 해석 고침 카테고리 Unit → Component · Enter → 문 떠남 · 표 「✎ 해석 고침」 · "
     "기록 한 줄(표기 · 자리 · 고친 칸) · 지금의 판정 길로 그 카테고리 노드",
     "✎ 해석 고침(카테고리 Unit → Component) → 문 떠남" in _out and len(_rr) == 1
     and _rr[0]["detail"]["category"] == "Component" and _rr[0]["detail"]["parent"] == "패키징"
     and [n["category"] for n in _jig] == ["Component"],
     f"기록 {[r['detail'] for r in _rr]} · 노드 {[(n['canonical'], n['category']) for n in _jig]}")

# ⓓ 이름 직접 — 셋 다 같은 노드 · 여럿이면 목록 · ⓔ 줄 하나에 k 단독
_row = {"kind": "gate", "surface": "x", "up_name": "패키징", "skeleton": GJ.listing("패키징"), "candidates": []}
_b = io.StringIO()
with contextlib.redirect_stdout(_b):
    _t3 = [GT._target(1, _row, n) for n in ("사이드실링", "패키징::사이드 실링", "사이드 실링")]
    _many = GT._target(1, dict(_row, up_name="조립", skeleton=GJ.listing("조립")), "비전검사")
show("B202 ⓓ 이름 직접 `m 1 사이드실링` · `m 1 패키징::사이드 실링` · `m 1 사이드 실링` → 셋 다 같은 노드(띄어쓰기 · 대소문자 · 상위 접두 무시) · "
     "여럿(비전검사 — 조립 아래 둘)이면 목록을 보이고 다시",
     [(x or {}).get("canonical") for x in _t3] == ["패키징::사이드 실링"] * 3 and _many is None and "여럿 — 1." in _b.getvalue(), f"{_t3} · {_b.getvalue().strip()}")
_e2 = _doc("B202K", ["열 압착부"])
_n2, _out2 = _go(_e2, ["k"])
show("B202 ⓔ 줄이 하나면 번호 생략 — `k` 단독 = `k 1`(잠정 「새로 만들기」 기록 · 처분 칸에 경로 — 고침 B203)",
     PH.decided(PH.decisions(), "열 압착부", "패키징") == PH.SEEDED and "✓ 새로 만들기 → 패키징 › 열 압착부 (잠정)" in _out2, "")

_o3 = _ops()
_k3 = []
_n3, _out3 = _go(_doc("B202U", ["프레스 지그"]), ["이건 조립 아래야", ""], keep=_k3)
_ru = [r["detail"] for r in oplog.read()[_o3:] if r.get("op") == PH.OP_REREAD]
show("B202 ⓒ′ 말 「이건 조립 아래야」 → 해석 고침 위 공정 패키징 → 조립 · 그 자리로 다시 판단(조립 아래 골격 목록) · Enter → 기록 한 줄(위 공정)",
     len(_k3) == 1 and _k3[0]["up_name"] == "조립" and _k3[0]["skeleton"] == GJ.listing("조립") and (_k3[0]["llm"] or {}).get("verdict")
     and [(d["surface"], d["parent"], d["up"]) for d in _ru] == [("프레스 지그", "패키징", "조립")], f"기록 {_ru}")

# B203 ⓗ~ⓚ — 번호 하나 · 어디 밑으로(조립 아래 — 공정 단은 설 수 있고 그 아래 단은 없다) · 말로도 같은 곳 · 다섯 말
from parser.namefold import key as _key203                         # noqa: E402


def _go203(did, head, say):
    """골격 단 줄 하나 — `say(줄)`이 첫 답(판단 뒤 그 줄의 고를 곳을 보고) · 다음은 Enter · c."""
    box, rows, n = io.StringIO(), [], [0]

    def ask(q):
        n[0] += 1
        return say(rows[0]) if n[0] == 1 else "" if n[0] == 2 else "c"

    def nt(info):
        if info.get("단계") == "골격단":
            rows.extend(info["rows"])
            return GT.loop(info["rows"], "B203시험", title="골격 단 — 시험", ask=ask)
    with contextlib.redirect_stdout(box):
        run_document(_doc(did, [head], coord="조립"), notice=nt, allow_duplicate=True)
    return rows, box.getvalue()


def _n203(r, name):
    return next(x["n"] for x in GJ.picks(r) if x["name"] == name)

_seen = {}
_rh, _oh = _go203("B203H", "B203 지그", lambda r: _seen.update(row=dict(r)) or f"k 1 {_n203(r, '스태킹')}")
_ph = PH.placed().get((_key203("B203 지그"), "조립")) or {}
_rq = dict(_seen["row"], done=None)
with contextlib.redirect_stdout(io.StringIO()) as _bq:
    GT._apply(1, _rq, "k", str(_n203(_rq, "비전검사")), "시험")
show("B203 ⓗ `k 1 <번호>`(골격 목록의 스태킹) → 스태킹 밑에 잠정 · 처분 칸에 경로 · 골격 단 밖 번호(비전검사 — 맨 아래 단) → 거부 · 설 수 있는 번호",
     _ph.get("under") == "스태킹" and "B203 지그" in [x["name"] for x in GJ.listing("스태킹")]
     and "✓ 새로 만들기 → 조립 › 스태킹 › B203 지그 (잠정)" in _oh and "설 수 있는 번호:" in _bq.getvalue() and not _rq.get("done"),
     f"자리 {_ph} · 스태킹 번호 {_n203(_seen['row'], '스태킹')} · {_bq.getvalue().strip()[:120]}")
_pk = GJ.picks(_seen["row"])
_b2 = io.StringIO()
with contextlib.redirect_stdout(_b2):
    GT.loop([dict(_seen["row"], done=None)], "B203시험", title="t", ask=lambda q, _f=["? 1", "c"]: _f.pop(0))
_t5 = GT._target(1, _seen["row"], "5")
show("B203 ⓘ `m 1 5` · `k 1 5`가 같은 번호 목록(후보 다음 골격 · 이어지는 번호) · `? 1` 펼친 뒤에도 번호 같음",
     [x["n"] for x in _pk] == list(range(1, len(_pk) + 1)) and _t5 == _pk[4] and f"{GT._no(5)} {_pk[4]['name']} —" in _b2.getvalue(),
     f"5 = {(_t5 or {}).get('name')}")
_rj, _oj = _go203("B203J", "B203 받침", lambda r: "1 스태킹 밑에 새로")
_pj = PH.placed().get((_key203("B203 받침"), "조립")) or {}
show("B203 ⓙ 말 「1 스태킹 밑에 새로」 → 해석 = 새로 만들기 · 부모 번호 → Enter → ⓗ와 같은 기록(스태킹 밑)",
     "1번 = 새로 만들기 → 조립 › 스태킹 › B203 받침 (잠정)" in _oj and _pj.get("under") == "스태킹", f"{_pj}")
_w5 = list(GS.KEYS)
_docs = [(ROOT / "docs" / "가이드" / f).read_text(encoding="utf-8") for f in ("운영_런북.md", "인입_이해_가이드.md")]
_rx = GT._reject(1, dict(_seen["row"]), "a")
show("B203 ⓚ 처분 말 다섯이 화면(동작 줄) · 처분 칸 · 거부 문면 · 런북 · 인입 이해 가이드에서 같다 · 쓸 수 없는 글쇠 → 동작 줄을 다시",
     all(all(w in d for w in _w5) for d in _docs) and all(any(w in ln for ln in GT.acts(1, _rg)) for _rg in ([_seen["row"]]) for w in _w5[:3])
     and "이 줄은:" in _rx and all(w in _rx for w in ("새로 만들기", "같은 것으로", "버리기")), _rx)

# ⓗ 청크 목차 라벨 200자 → 132칸 안 앞 · 끝 · 가운데 … · 추출 진행 표에 「붙을 노드」(청크 목차의 좌표와 같은 값)
_lab = "앞머리" + "가" * 194 + "끝꼬리"
_tl = IS.toc_lines({"목차": [(1, _lab, "패키징", "부름", 10)]})[1]
_cell = _screen.cut_mid(_lab, IS.LABEL_W)
_xn = [i for i in _all0 if i.get("단계") == "추출청크"]
show("B202 ⓗ 청크 목차 라벨 200자 → 132칸 안에 앞 · 끝이 남고 가운데 「…」 · 추출 진행 표에 「붙을 노드」 칸 · 청크마다 그 값 = 청크 목차의 좌표",
     _cell.startswith("앞머리") and _cell.endswith("끝꼬리") and "…" in _cell and _screen.w(_cell) <= IS.LABEL_W and _cell in _tl
     and "붙을 노드" in [c[0] for c in XS.extract_table().cols] and _xn and all(i.get("좌표") == "패키징" for i in _xn),
     f"폭 {_screen.w(_cell)} · 좌표 {[i.get('좌표') for i in _xn][:3]}")

init.init(fresh_=True, all_=True)
for d in set(_made):
    (HINTS / f"{d}.json").unlink(missing_ok=True)
    (HINTS / f"{d}@outline.json").unlink(missing_ok=True)
done()
