# -*- coding: utf-8 -*-
"""칸 2.4·2.5 — **문서 구조** — 계층 사다리(문서당 1) → 목차(코드 — 모든 시트에 같게) → 시트 확인(시트당 1) (B119 ① · B132).

**최종 판단은 LLM이고 사람이 그 위다 · 코드는 재료 · 적용 · 검사**(사용자 2026-10-20 — 「룰은 LLM에 정보를 주고 LLM이 판단」):

  · 재료(파서 — 판정 0): 줄 = 행 전체 · 시작 열 · 들여쓰기 깊이 · 꼴 서명 · 서수 · 빈 행 뒤 · 보조 표시(`parser.struct_rule.labels`)
  · **계층 사다리**(지점 ⑪ · 태그 `structure` · 문서당 한 번 — `core/build/ladder.py`): 단마다 서명 · 역할 · 카테고리 + 번호 없는 제목의
    규칙 · 입력은 앞부분의 골격 보기 · 서명 통계 · 코드 사다리 — **줄 전문 0** · 실패 · mock 힌트 없음이면 **코드 사다리**(`rules`와 같은 길)
  · **목차**(파서 — `parser/ladder.apply`): 사다리 + 이어짐 · 다시 시작 + 들여쓰기 깊이 → 제목 줄마다 부모 · 역할 · 대상 + **판단 필요**
    넷(코드가 정하지 않고 표시)
  · **시트 확인**(지점 ⑪ · 시트당 한 번): 골격 보기 → 판단 필요 행마다 답 + 고침(B126 여섯 동사 · `structure_edit.apply_edits` 검사) +
    사다리 고침(문서 규칙 — 그 문서의 뒤 시트에도)

방식은 둘(사내 손잡이 `structure_mode`): **`ladder`(기본)** · `rules`(LLM 0 — 코드 사다리 · 시트 확인 0). 옛 값 `edit` · `llm`은 폐기 —
`knobs.json`에 있으면 운영 관문이 바꿀 값을 말하며 멈춘다(`core/state/knobs.RETIRED`). 보존 = 구조 지도 보존 파일 `work/struct_maps/<doc_id>.json`의
`structure[<시트>]`와 문서의 사다리(`structure["@사다리"]`) — 같은 이름표 · 같은 판이면 LLM 0 · 재구축이 재생한다.
코드에 층 어휘 0 — 카테고리는 층 config가 · 역할은 닫힌 시스템 어휘(파서 계약)가 말한다.
"""
from __future__ import annotations

import json

from core.llm import gateway
from core.state import log, store
from parser.struct_rule import FRAME_ROW, UNIT_ROLES

_LOG = log.get(__name__)

#: 지시문 이름(`prompts/3.3_outline.md` — 개요와 한 벌) · 호출 태그(지점 ⑪ — `gateway.CALL_TAGS`)
PROMPT, TAG = "outline", "structure"
#: 제목 목록(개요 — 슬라이드 · 쪽 제목) 한 줄의 글자 상한(사내 손잡이 `structure_line_chars` · 구조 호출은 골격 보기라 쓰지 않는다)
LINE_CHARS = 300
#: 덱 구조 한 호출에 싣는 양(어림 토큰 — 사내 손잡이 `structure_call_tokens` · 덱이 쓴다)
CALL_TOKENS = 40000
#: **구조 방식**(B132 ⑧ — 사내 손잡이 `structure_mode`): `ladder`(기본 — 사다리 · 시트 확인) · `rules`(코드 사다리 · LLM 0)
MODE = "ladder"
MODES = ("rules", "ladder")
#: 보존분의 문서 사다리 자리(시트 이름과 겹치지 않는 열쇠)
LADDER_KEY = "@사다리"
#: 지시문 · 스키마는 개요(제목 목록)와 한 벌 — 제목 목록만 오는 호출(`outline._ask`)의 답 꼴
SCHEMA = {
    "type": "object",
    "properties": {"headings": {"type": "array", "items": {
        "type": "object",
        "properties": {"row": {"type": "integer"}, "parent": {"type": ["integer", "null"]},
                       "role": {"type": "string", "enum": ["대상", "묶음", "주제"]},
                       "name": {"type": ["string", "null"]}, "category": {"type": ["string", "null"]}},
        "required": ["row", "parent", "role", "name", "category"], "additionalProperties": False}}},
    "required": ["headings"], "additionalProperties": False,
}


# ---------------------------------------------------------------- 판 · 카테고리
def _cfgs(layers):
    from core.state.bootstrap import coord_layer, load_config
    out = {}
    for lay in list(layers or []) or [coord_layer()]:
        try:
            out[lay] = load_config(lay)
        except (OSError, ValueError, KeyError) as e:
            _LOG.warning("문서 구조 — 층 %s config를 읽지 못했다: %s", lay, e)
    return out


def categories(cfgs):
    """닫힌 카테고리 + 정의문 — 렌즈가 여럿이면 층마다의 합(구조는 문서마다 한 번이다)."""
    from core.build.extract import categories_with_also
    out = {}
    for cfg in cfgs.values():
        for k, v in categories_with_also(cfg).items():
            out.setdefault(k, v)
    return out


def key(cfgs):
    """보존분 재사용의 판 — 지시문 판 · 층 config 판(층마다 추출 갈래 칸의 해시 — B120 ③ · 추출과 같은 함수) · 방식."""
    from core.build.extract import prompt_version
    from core.state import config_scope
    return {"prompt_version": prompt_version(PROMPT),
            "config_extract": " · ".join(f"{k}:{config_scope.extract_key(c)}" for k, c in sorted(cfgs.items())),
            "mode": MODE}                                    # 방식을 바꾸면 다시 묻는다 (B126 ①)


# ---------------------------------------------------------------- 문서 사다리 (문서당 한 번)
#: 이 프로세스의 문서 사다리 `{doc_id: {base, ladder, code, source, calls, failed, dropped, counts}}` — 시트 함수가 읽는다
DOCL = {}


def _ladder(doc_id, frames, cfgs, cats, live, ctx):
    """문서 사다리 — LLM(실호출) · 힌트(mock) · 코드 사다리(`rules` · 실패 · 힌트 없음) · 사다리 고침(문서 규칙)은 그 위에."""
    from core.build import ladder as LA
    from parser import ladder as PL
    code = PL.code(frames)
    counts = PL.doc_counts(frames)
    built = {n: PL.apply(labs, code, counts) for n, labs in frames.items()}
    raw, src, calls, failed, dropped = None, "코드", 0, None, []
    if MODE == "ladder":
        if live:
            gateway.require(TAG)                    # 부르기 직전의 관문(설정 없음 = 명시적 실패 · 조립은 막지 않는다)
            calls = 1
            try:
                raw = LA.ask_ladder(frames, built, code, cats, cfgs, ctx, doc_state(doc_id)["hints"])
            except gateway.GatewayError as e:
                store.append_defect(f"{doc_id}: 계층 사다리 호출 실패 — {e} → 코드 사다리")
                failed = f"{type(e).__name__}: {str(e)[:120]}"
        else:
            raw = LA.hint_ladder(doc_id)
    lad = None
    if raw is not None:
        lad, dropped = LA.check_ladder(doc_id, raw, frames, cats)
        src = ("LLM" if live else "힌트") if lad else "코드(답 버림)"
    elif MODE == "ladder":
        src = "코드(호출 실패)" if failed else ("코드(힌트 없음)" if not live else "코드")
    base = {**(lad or code), "by": src}
    return {"base": base, "code": code, "source": src, "calls": calls, "failed": failed, "dropped": dropped,
            "counts": counts}


def ladder_now(doc_id, cats):
    """그 문서의 지금 사다리 — 바탕 사다리 + 사다리 고침(확정 기록의 문서 규칙 + 이 프로세스의 구조 확인 · 위에서 아래로)."""
    from core.build import ladder as LA
    d = DOCL.get(doc_id) or {}
    rules = doc_state(doc_id)["rules"]
    return LA.fix_ladder(d.get("base"), rules, cats) if rules else d.get("base")


# ---------------------------------------------------------------- 주입 함수
def structurer(layers=None):
    """파서에 내려보낼 **문서 구조 함수** `fn(doc_id, frame, labels)` + `fn.prepare(doc_id, frames)`(문서 사다리 — 시트보다 먼저 한 번).

    `fn.key()`가 보존분의 판이다 · 돌려주는 것은 검사가 끝난 구조(제목 · 판단 필요 · 사다리 · 시트 확인의 답)."""
    cfgs = _cfgs(layers)
    cats = categories(cfgs)
    live = not gateway.use_mock()

    def prepare(doc_id, frames, ctx=None):
        DOCL[doc_id] = _ladder(doc_id, frames, cfgs, cats, live, ctx)
        return DOCL[doc_id]

    def adopt(doc_id, kept):
        DOCL[doc_id] = {**kept, "calls": 0, "source": f"{kept.get('source') or '코드'} · 재사용"}
        return DOCL[doc_id]

    def fn(doc_id, frame, labs, ctx=None, hints=None, prev=None, mode=None):
        from core.build import ladder as LA
        from core.build import structure_edit as SE
        from core.build.extract import prompt_version
        from parser import ladder as PL
        if hints is None:
            hints = doc_state(doc_id)["hints"] or None    # 힌트는 문서 규칙 — 그 문서의 모든 시트에 (B130 ④)
        if doc_id not in DOCL:
            prepare(doc_id, {frame: labs}, ctx)           # 사다리를 먼저 세우지 않은 부르기(한 프레임 문서 · 고리) — 이 프레임으로
        d = DOCL[doc_id]
        ladder = ladder_now(doc_id, cats)
        built = PL.apply(labs, ladder, d["counts"])
        st = {"headings": built["headings"], "toc0": built["headings"], "needs": built["needs"], "ladder": ladder,
              "ladder_source": d["source"],
              "mode": mode or MODE, "calls": 0, "source": "code", "prompt_version": prompt_version(PROMPT),
              **({"hints": list(hints)} if hints else {})}
        if (mode or MODE) == "rules":
            return {**st, "doc_hints": list(hints or [])}
        failed = None
        if live:
            gateway.require(TAG)
            st.update(calls=1, source="live")
            try:
                out = LA.ask_check(frame, labs, built, ladder, cats, cfgs, ctx, hints, prev)
            except gateway.GatewayError as e:
                store.append_defect(f"{doc_id}: 시트 확인 호출 실패 — 시트 '{frame}' — {e} → 사다리 목차 그대로")
                out, failed = {"answers": [], "edits": [], "rules": []}, f"{type(e).__name__}: {str(e)[:120]}"
        else:
            out = LA.hint_check(doc_id, frame, labs, built["headings"])
            if out is None:
                return {**st, "doc_hints": list(hints or [])}     # 판정 없음 — 사다리 목차 그대로(판단 필요는 남는다)
            st["source"] = "hint"
        mine = [x for x in out.get("rules") or [] if x.get("shape")]
        if mine:                                            # 사다리 고침 — 문서 규칙(뒤 시트에도) · 이 시트는 고친 사다리로 다시 세운다
            DOC.setdefault(doc_id, {"hints": [], "rules": []})["rules"] = _merge_rules(DOC[doc_id].get("rules"), mine)
            ladder = ladder_now(doc_id, cats)
            built = PL.apply(labs, ladder, d["counts"])
        edits, missing, stray = LA.answers_to_edits(doc_id, frame, built["headings"], built["needs"], out.get("answers"))
        heads, joins, took, bad = SE.apply_edits(doc_id, frame, labs, built["headings"],
                                                 {"edits": edits + list(out.get("edits") or []), "headings": []}, cats)
        _LOG.info("시트 확인 %s · %s — 판단 필요 %d · 답 빠짐 %d · 고침 %d · 버림 %d", doc_id, frame, len(built["needs"]),
                  len(missing), len(took), len(bad))
        return {**st, "headings": heads, "toc0": built["headings"], "needs": built["needs"], "ladder": ladder,
                "joins": joins, "edits": took,
                "edits_dropped": bad, "answer": out, "missing": missing, "stray": stray,
                "rules": LA.rule_counts(labs, heads, mine), "doc_hints": list(hints or []),
                **({"failed": failed} if failed else {})}
    fn.key = lambda: key(cfgs)
    fn.takes_ctx = True
    fn.doc_state = doc_state
    fn.prepare = prepare
    fn.adopt = adopt
    fn.ladder_of = lambda doc_id: ladder_now(doc_id, cats) if doc_id in DOCL else None
    return fn


# ---------------------------------------------------------------- 문서 규칙 (B130 ④ — 힌트는 문서 규칙 · 사다리 고침으로 되말한다)
#: 이 프로세스의 구조 확인에서 받은 문서 힌트 · 사다리 고침 `{doc_id: {hints, rules}}` — 확정 기록이 문서 힌트로 남긴다
DOC = {}
RULE_KEYS = ("shape", "role", "category", "parent_shape", "said")


def _merge_rules(old, new):
    """서명마다 하나 — 뒤의 규칙이 이긴다(같은 서명을 다시 말했다)."""
    out = {x.get("shape"): {k: x.get(k) for k in RULE_KEYS} for x in old or []}
    for x in new or []:
        out[x.get("shape")] = {k: x.get(k) for k in RULE_KEYS}
    return list(out.values())


def doc_state(doc_id):
    """그 문서의 문서 힌트 · 사다리 고침 — 확정 기록(목차 판이 같은 것) + 이 프로세스의 구조 확인 · 위에서 아래로."""
    from parser.toc import TOC_VERSION
    hints, rules = [], []
    for v in (_confirmed_all().get(doc_id) or {}).values():
        if v.get("toc") == TOC_VERSION:
            hints += [h for h in v.get("doc_hints") or [] if h not in hints]
            rules = _merge_rules(rules, v.get("doc_rules"))
    now = DOC.get(doc_id) or {}
    hints += [h for h in now.get("hints") or [] if h not in hints]
    return {"hints": hints, "rules": _merge_rules(rules, now.get("rules"))}


def add_doc_hint(doc_id, text):
    DOC.setdefault(doc_id, {"hints": [], "rules": []})["hints"].append(text)


# ---------------------------------------------------------------- 확정 기록 (B126 ③ — 등록 단 · 사람 판단 · 재생성 불가)
def confirmed_path():
    from core import paths
    return paths.registry("structure_confirmed.json")


def _confirmed_all():
    p = confirmed_path()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


#: 구조 확인 고리에서 **비켜 둔 확정 시트** `{(doc_id, 시트)}`(B127 ③ — 확정한 시트에 사람이 다시 힌트를 줬다 · 그 고리 동안만 ·
#: `c`면 새 확정이 기록을 덮고 `q`면 옛 기록 그대로)
SUSPENDED = set()


def confirmed_of(doc_id):
    """그 문서의 확정 시트 `{시트: {labels, mode, headings, joins, hints, prompt_version, by, at}}` — 파서가 데이터로 받는다
    (비켜 둔 시트는 뺀다)."""
    return {f: v for f, v in (_confirmed_all().get(doc_id) or {}).items() if (doc_id, f) not in SUSPENDED}


def confirm(doc_id, frame, st, hints=None):
    """시트 하나 확정 — 최종 나무 · 붙임 · 준 힌트 · 방식 · 판 · 이름표 해시(원자 쓰기) · 재구축 · 재인입이 그대로 재생(LLM 0).
    목차 규칙 판(`toc`) · LLM 답(고침 목록 · 이해한 규칙) · 문서 힌트 · 문서 규칙도 남긴다(B130 ⑤ — 판이 다른 옛 확정은 재생하지 않는다 ·
    다시 힌트로 열면 앞 출력이 앞 판단 전체다)."""
    from datetime import datetime, timezone
    from core import paths
    from parser.toc import TOC_VERSION
    doc = doc_state(doc_id)
    d = _confirmed_all()
    d.setdefault(doc_id, {})[frame] = {
        "labels": st.get("labels"), "mode": st.get("mode"), "headings": st.get("headings") or [],
        "joins": st.get("joins") or [], "chunks": st.get("chunks") or [], "hints": list(hints or st.get("hints") or []),
        "prompt_version": st.get("prompt_version"), "toc": TOC_VERSION, "answer": st.get("answer"),
        "rules": st.get("rules") or [], "doc_hints": doc["hints"], "doc_rules": doc["rules"], "ladder": st.get("ladder"),
        "by": "사람",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = confirmed_path()
    paths.ensure(p)
    store.atomic_write_bytes(p, (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def reask(doc_id, frame, labs, src_path, *, hints=None, prev=None, mode=None, layers=None, ctx=None):
    """구조 확인의 고리(B126 ③) — 그 시트를 같은 방식(또는 `mode`)으로 다시 부르고(앞 출력 + 힌트 전부) 구조 보존분의 그 시트
    자리에 둔다 → 다시 파싱이 그것을 쓴다(LLM 0). 돌려주는 것은 새 구조 또는 None."""
    from parser import struct_map
    from parser.struct_rule import labels_hash
    fn = structurer(layers)
    st = fn(doc_id, frame, labs, ctx=ctx, hints=hints, prev=prev, mode=mode)
    if not st or st.get("skip"):
        return st
    src = struct_map.source_hash(src_path)
    kept = struct_map.load_kept(doc_id, src) or {}
    s = dict(kept.get("structure") or {})
    s[frame] = {**st, "labels": labels_hash(labs), "key": fn.key()}
    struct_map.keep(doc_id, {**kept, "doc_id": doc_id, "structure": s}, src)
    return st


# ---------------------------------------------------------------- 사람의 고침 (B119 ③ — 등록 단 · 재생성 불가)
def fixes_path():
    from core import paths
    return paths.registry("structure_fixes.json")


def _fixes_all():
    p = fixes_path()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


#: **옛 고침 기록의 역할 이름**(B119 판 — 다섯) → 지금 역할(B124 ③ — 셋 · 층 중립). 읽을 때 옮긴다(재구축 재생 그대로 · 이 표 밖에서
#: 옛 이름을 읽는 곳은 없다).
_LEGACY_ROLES = {"설비": "대상", "유닛": "대상", "항목": "대상", "사양 묶음": "묶음"}


def _migrated(fx):
    return {**fx, "role": _LEGACY_ROLES.get(fx.get("role"), fx.get("role"))} if isinstance(fx, dict) else fx


def fixes_of(doc_id):
    """그 문서의 고침 `{시트: {행: {role, name, category}}}` — 파서가 데이터로 받는다(구조 위에 덮는다) · 옛 역할 이름은 옮겨 읽는다."""
    return {fr: {int(r): _migrated(fx) for r, fx in rows.items()}
            for fr, rows in (_fixes_all().get(doc_id) or {}).items()}


def record_fix(doc_id, frame, row, fix):
    """고침 한 줄 — `registry/structure_fixes.json`(사람 판단 · 원자 쓰기). 같은 줄은 덮는다."""
    from datetime import datetime, timezone
    from core import paths
    d = _fixes_all()
    d.setdefault(doc_id, {}).setdefault(frame, {})[str(row)] = {
        **fix, "by": "사람", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = fixes_path()
    paths.ensure(p)
    store.atomic_write_bytes(p, (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


# ---------------------------------------------------------------- 약한 구조 신호 · 셈 (화면 · 기록의 재료)
def sibling_clash(fr):
    """**같은 서명 형제의 단 · 역할이 다르다**(B124 ② — 약한 구조 신호 · 자동으로 고치지 않는다) — `{서명: [행 …]}`.
    서명이 같은 짧은 줄이 둘 이상인데 (목차 깊이, 역할)이 갈린 서명만 · 제목이 아닌 줄은 (0, 없음)."""
    depth = _depths(fr.get("headings") or [])
    role = {h["row"]: h.get("role") for h in fr.get("headings") or []}
    fam = {}
    for x in fr.get("labels") or []:
        if x.get("sig") and x["row"] != FRAME_ROW:
            fam.setdefault(x["sig"], []).append(x["row"])
    return {k: v for k, v in fam.items()
            if len(v) > 1 and len({(depth.get(r, 0), role.get(r)) for r in v}) > 1}


def weak(report, pieces=(), coord_in=True):
    """**약한 구조 신호**(B119 ③ — 구현이 센다) — 시트마다 `{시트: [신호 문장]}`(없으면 빈 dict).

    ①대상 0 — 제목이 둘 이상인데 대상 역할이 0(문서의 층에 좌표 층이 있을 때 — `coord_in`) ②판단 필요가 남았다 · 답 빠짐 ③상한에서
    잘린 청크 ④같은 서명 형제의 단 · 역할이 다름 ⑤호출 실패 · 사다리가 코드로 섰다(실호출에서)."""
    out = {}
    cut = {}
    for c in pieces or []:
        m = c.get("meta") or {}
        if m.get("char_cap_from") or m.get("over_char_cap"):
            cut[m.get("frame")] = cut.get(m.get("frame"), 0) + 1
    for frame, fr in ((report or {}).get("프레임") or {}).items():
        heads = [h for h in fr.get("headings") or [] if h["row"] != FRAME_ROW]
        got = []
        if coord_in and len(heads) >= 2 and not any(h.get("role") in UNIT_ROLES for h in heads):
            got.append(f"대상 0(제목 {len(heads)})")
        if fr.get("needs") and fr.get("mode") != "rules":
            n = len(fr["needs"]) if fr.get("source") == "code" else len(fr.get("missing") or [])
            if n:
                got.append(f"판단 필요 {len(fr['needs'])} · 답 없음 {n}")
        if cut.get(frame):
            got.append(f"글자 상한에서 잘린 청크 {cut[frame]}")
        for k, rows in sibling_clash(fr).items():
            got.append(f"같은 서명 「{k}」 형제 {len(rows)}줄의 단 · 역할이 다르다")
        if fr.get("failed"):
            got.append("시트 확인 호출 실패 — 사다리 목차 그대로")
        if got:
            out[frame] = got
    return out


def _depths(heads):
    depth = {}
    for h in heads:
        p = h.get("parent")
        depth[h["row"]] = depth.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1
    return depth


def counts(report):
    """구조 끝 줄의 수 — 시트 · 제목 · 역할별 · 호출 · 재사용 · 판단 필요 · 답 빠짐 · 실패 · 사람 고침 · 사다리의 출처."""
    fr = (report or {}).get("프레임") or {}
    heads = [h for f in fr.values() for h in f.get("headings") or [] if h["row"] != FRAME_ROW]
    roles = {}
    for h in heads:
        roles[h.get("role") or "역할 없음"] = roles.get(h.get("role") or "역할 없음", 0) + 1
    return {"시트": len(fr), "제목": len(heads), "역할": roles, "호출": (report or {}).get("호출", 0),
            "재사용": (report or {}).get("재사용", 0), "사다리": (report or {}).get("사다리") or "",
            "판단 필요": sum(len(f.get("needs") or []) for f in fr.values()),
            "답 빠짐": sum(len(f.get("missing") or []) for f in fr.values()),
            "버림": sum(len(f.get("edits_dropped") or []) for f in fr.values()),
            "실패": sum(1 for f in fr.values() if f.get("failed")),
            "고침": sum(int(f.get("fixed") or 0) for f in fr.values()),
            "옛 확정": len((report or {}).get("옛 확정") or [])}
