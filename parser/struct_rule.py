# -*- coding: utf-8 -*-
"""칸 2.4·2.6 — **계층 규칙 선언** — 고정 규칙이 못 세우는 시트만 LLM이 규칙을 **데이터로** 낸다 (B87 ②).

    고정 규칙(번호 군 · 가로병합 · 굵게) → 계층이 안 선 시트만
      → 훅 `struct_rule_fn(frame, sample)` — 코어가 주입한다(⑦ 안의 호출 태그 `struct_rule`)
      → 선언 검사(결정적 — 여기) → 고정 어댑터가 선언을 **적용**
      → 선언은 구조 지도 보존 파일 `rules[<시트>]`에 원본 해시와 함께 남는다

**LLM이 코드를 짜서 실행하지 않는다**(사용자 확정 2026-09-23) — 문서마다 사람 확인
없는 코드 실행은 관문 우회이고, 버리면 재인입마다 경계가 달라져 chunk_id가 움직인다.
선언은 정규식 몇 개와 플래그 둘이다: 적용하는 것은 코드다.

**파서는 core를 import하지 않는다** — 모델을 부르는 함수는 주입으로 오고(`infer_rules`),
여기는 그 함수를 감싸 **재사용·검사·셈**만 한다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

from . import struct_map

_LOG = logging.getLogger("onto.parser.struct_rule")

# 모델이 보는 것 — 그 시트 본문 열 **앞 N행**(비어 있지 않은 행)이다. 문서 전체가 아니다:
# 비용이 문서 크기와 무관해야 예고(「LLM ≤ n회」)가 약속이 된다. 러프하게 60(요청문).
RULE_SAMPLE_ROWS = 60
RULE_SAMPLE_CHARS = 80          # 한 행의 앞자리 — ⑦ 지도 패스의 첫 폭과 같다

# 선언 검사의 문턱 — 넘으면 선언을 버린다(로그) · 통째 + 큐.
MAX_PATTERNS = 8
MAX_PATTERN_LEN = 120
LEVELS = range(1, 7)
_COL = re.compile(r"^[A-Z]{1,3}$")


def check(decl):
    """선언 검사 — 사유 목록(빈 목록이면 적용한다). **결정적**이다.

    정규식은 컴파일되고 `^`로 시작해야 한다(행 머리를 보는 규칙만 — 본문 한가운데를
    잡는 패턴은 제목 판정이 아니다) · 길이 ≤ 120 · 패턴 ≤ 8 · 레벨 1~6.
    """
    if not isinstance(decl, dict):
        return ["선언이 객체가 아니다"]
    out = []
    pats = decl.get("heading_patterns")
    if not isinstance(pats, list):
        return ["heading_patterns가 목록이 아니다"]
    if len(pats) > MAX_PATTERNS:
        out.append(f"패턴 {len(pats)}개 > {MAX_PATTERNS}")
    for i, p in enumerate(pats, 1):
        m, lv = (p or {}).get("match"), (p or {}).get("level")
        if not isinstance(m, str) or not m.startswith("^"):
            out.append(f"패턴 {i} — `^`로 시작하지 않는다: {str(m)[:40]!r}")
            continue
        if len(m) > MAX_PATTERN_LEN:
            out.append(f"패턴 {i} — 길이 {len(m)} > {MAX_PATTERN_LEN}")
        try:
            re.compile(m)
        except re.error as e:
            out.append(f"패턴 {i} — 컴파일 실패: {e}")
        if not isinstance(lv, int) or isinstance(lv, bool) or lv not in LEVELS:
            out.append(f"패턴 {i} — 레벨 {lv!r}는 1~6 밖")
    for k in ("bold_is_heading", "merge_is_heading"):
        if not isinstance(decl.get(k), bool):
            out.append(f"{k}가 참/거짓이 아니다")
    col = decl.get("heading_column")
    if col is not None and not (isinstance(col, str) and _COL.match(col)):
        out.append(f"heading_column {col!r}는 열 문자가 아니다")
    if not (pats or decl.get("bold_is_heading") or decl.get("merge_is_heading")):
        out.append("제목을 세울 규칙이 하나도 없다")
    return out


def hook(ask, *, kept=None, made=None, skip=(), tally=None):
    """어댑터에 건넬 훅 — **보존분이 있으면 그것**(호출 0), 없으면 `ask` 한 번.

    `skip`은 부르지 않는 프레임이다 — **`ref` 시트는 LLM 0**(B83 — 저장만 한다).
    검사에 떨어진 선언은 `made`에 담지 않는다(보존하면 재인입이 영영 그것을 쓴다 —
    ⑦의 사유 지도와 같은 규칙 · 문서 6 §6.3). 적용해도 계층이 안 선 선언은 담는다:
    같은 파일이면 같은 결과이고, 다시 불러도 비용만 든다(두 번째 호출 없음).
    """
    kept = kept or {}
    tally = tally if tally is not None else {}

    def fn(frame, sample):
        if frame in skip:
            return None
        if frame in kept:
            tally["재사용"] = tally.get("재사용", 0) + 1
            return kept[frame]
        tally["호출"] = tally.get("호출", 0) + 1
        decl = ask(frame, sample)
        why = check(decl)
        if why:
            tally.setdefault("버림", []).append({"프레임": frame, "사유": why})
            _LOG.warning("계층 규칙 선언을 버린다 — %s: %s", frame, "; ".join(why))
            return {"_rejected": why}
        if made is not None:
            made[frame] = decl
        return decl
    return fn


def patterns_of(decl):
    """화면·검수 뷰에 적는 선언의 모양 — 패턴 목록 + 플래그."""
    pats = [f"{p['match']}→{p['level']}" for p in decl.get("heading_patterns") or []]
    if decl.get("bold_is_heading"):
        pats.append("굵게")
    if decl.get("merge_is_heading"):
        pats.append("가로병합")
    return pats


def summary(pieces, tally, targets):
    """시트마다 「고정 규칙 / 선언(패턴 목록) / 통째」 + 예고와 결과의 수.

    재료는 조각의 `meta`다(새 계산 0) — 어댑터가 `split_path`로 무엇으로 잘랐는지 말한다.
    """
    sheets = {}
    for p in pieces:
        m = p.get("meta") or {}
        fr = m.get("frame")
        if not fr or fr in sheets:
            continue
        path = m.get("split_path")
        sheets[fr] = ("선언(" + " · ".join(m.get("rule_patterns") or []) + ")"
                      if path == "rule" else "통째" if path == "flat" else "고정 규칙")
    applied = sum(1 for f in targets if sheets.get(f, "").startswith("선언"))
    return {"대상": len(targets), "대상_시트": list(targets), "재사용": tally.get("재사용", 0),
            "호출": tally.get("호출", 0), "버림": tally.get("버림") or [],
            "적용": applied, "통째": sum(1 for f in targets if sheets.get(f) == "통째"),
            "시트": sheets}


# ---------------------------------------------------------------- 프레임 한 벌 (B88 ② — 엑셀·Word가 같이 쓴다)
def fixed_ok(rows):
    """고정 규칙으로 계층이 섰나 — 제목이 있고 레벨이 단조다(⑦ 타당성 검사와 같은 규칙)."""
    return any(r["heading"] for r in rows) and not struct_map.monotonic_reasons(rows)


def apply(lines, marks, decl, *, max_chars=None):
    """선언을 **데이터로** 적용한다 — `rows`. 판정 순서는 고정 규칙과 같다(패턴 > 가로병합 > 굵게).

    `marks[행] = {"head": 패턴을 댈 글, "bold", "indent", "merge"}` — 포맷마다 어댑터가 채운다.
    제목 후보는 짧은 행만(`struct_map.HEADING_MAX_CHARS`).
    """
    cap = max_chars or struct_map.HEADING_MAX_CHARS
    pats = [(re.compile(p["match"]), p["level"]) for p in decl.get("heading_patterns") or []]
    rows = []
    for r, _text in lines:
        mk = marks.get(r) or {}
        head = mk.get("head") or ""
        lv, sig = 0, None
        if head and len(head) <= cap:
            lv = next((l for rx, l in pats if rx.match(head)), 0)
            sig = SIG_RULE if lv else None
        if not lv and decl.get("merge_is_heading") and mk.get("merge"):
            lv, sig = 1, "가로병합"
        if not lv and decl.get("bold_is_heading") and mk.get("bold"):
            lv, sig = int(mk.get("indent") or 0) + 1, "굵게+들여쓰기"
        rows.append({"row": r, "heading": bool(lv), "level": lv, "signal": sig})
    return rows


SIG_RULE = "규칙 선언"


def _ask(fn, name, sample, by_rule):
    decl = fn(name, sample)
    if not decl:
        return None, None, None, None                   # 부르지 않았다(ref 시트 등)
    if decl.get("_rejected"):
        return None, None, None, "규칙 선언을 버렸다 — " + "; ".join(decl["_rejected"])[:200]
    lines, rows = by_rule(decl)
    if fixed_ok(rows):
        return lines, rows, decl, None
    return None, None, None, "규칙 선언을 적용해도 계층이 서지 않는다"


def frame_chunks(name, lines, rows, locator, sep, base_meta, *, rule_fn=None,
                 sample_fn=None, by_rule=None, structure_fn=None, marks_fn=None, sheet=True,
                 flat_reason="계층 신호 0건 — 통째로 실었다"):
    """프레임(시트·문서 본문) 하나의 글 조각 — **문서 구조**(B119 ① — 주입되면 무조건) → 고정 규칙 → (안 서면) 규칙
    선언 → 통째 또는 분할.

    **포맷이 달라도 한 벌이다**(B88 ② — 분할 규칙 두 벌 금지): 어댑터는 줄 목록·판정
    rows·선언 적용 함수 · 줄 표시(`marks_fn`)만 댄다. 자르는 것은 `struct_map.split`, 레벨은 `choose_level` —
    구조가 섰으면 **설비 · 유닛 · 사양 묶음 줄 아래에서는 반드시 자른다**(같은 유닛 아래 청크가 전부 경로에 그 유닛을 든다).
    `base_meta`는 포맷의 표시(엑셀의 `content_column` 등)다. `sheet`면 이름표 0행이 시트 이름이다(Word는 없다).
    """
    path, decl, why, info = "heading", None, None, {}
    if structure_fn is not None:
        st = structure_fn(name, labels(name, lines, rows, marks_fn() if marks_fn else {}, sheet))
        if st is not None:
            rows, info = structure_rows(lines, st)
            path = PATH_STRUCT
            if st.get("failed"):
                why = f"구조 호출 실패 — 초안 {st['failed'][:120]}"
    if not info and rule_fn is not None and not fixed_ok(rows):
        l2, r2, decl, why = _ask(rule_fn, name, sample_fn(), by_rule)
        if decl:
            lines, rows, path = l2, r2, "rule"
    frame_info = _chain_item(info[FRAME_ROW], name) if info.get(FRAME_ROW) else None
    if not any(r["heading"] for r in rows):
        # **헤딩 0건 — 통째로 낸다.** 빈 산출도, 지어낸 분할도 만들지 않는다.
        meta = {"split_path": "flat", "frame": name, "section_path": name,
                **base_meta, "hierarchy_unresolved": True,
                "unresolved_reason": flat_reason + (f" · {why}" if why else "")}
        if info:
            meta["structure"] = []
        if frame_info:
            meta["structure_frame"] = frame_info
        return [{
            "source_locator": locator(lines[0][0], lines[-1][0]),
            "section": name,
            "text": "\n".join(t for _r, t in lines),
            "meta": meta,
        }]
    smap = {"rows": rows}
    stats = struct_map.level_stats(smap, lines)
    pick, reason, oor = struct_map.choose_level(stats)
    if info:
        pick, reason, oor = _cut_level(info, stats, pick, reason, oor)
    smap.update({"레벨_분포": stats, "분할_레벨": pick,
                 "분할_레벨_사유": reason, "분할_레벨_구간밖": oor})
    text_of = dict(lines)
    out = []
    for c in struct_map.split(smap, lines, locator, sep, heads=bool(info)):
        hs = c.pop("_heads", None)
        meta = {**(c.get("meta") or {}), "split_path": path, "frame": name, **base_meta,
                "split_level": pick, "section_path": c.get("section") or name}
        if decl:
            meta["rule_patterns"] = patterns_of(decl)
        if info:
            meta["structure"] = [_chain_item(info.get(r) or {}, text_of[r].strip(), r) for r in hs or []]
        if frame_info:
            meta["structure_frame"] = frame_info
        out.append({**c, "section": c.get("section") or name, "meta": meta})
    return out


# ---------------------------------------------------------------- 문서 구조 (B119 ① — 시트마다 LLM이 무조건)
#: 구조 역할 — **닫힌 다섯**(LLM 계약의 열거 · 줄의 쓰임을 말하는 시스템 어휘 — 층 어휘가 아니다 · D-201)
ROLES = ("설비", "유닛", "사양 묶음", "항목", "주제")
#: 대상(이름 · 카테고리)을 갖는 역할 — 그 밖의 역할은 대상이 없다
TARGET_ROLES = ("설비", "유닛", "항목")
#: 청크를 **반드시 그 아래에서** 자르는 역할 — 같은 유닛 아래 청크가 전부 경로에 그 유닛을 든다
CUT_ROLES = ("설비", "유닛", "사양 묶음")
#: 주인 줄(설비 · 유닛) — 약한 구조 신호 「설비 · 유닛 0」이 센다
UNIT_ROLES = ("설비", "유닛")
SIG_STRUCT = "구조"
PATH_STRUCT = "structure"
#: 이름표의 0행 — 프레임(시트) 이름 그 자체(시트가 대상일 때의 역할 · 대상)
FRAME_ROW = 0
#: 사람이 고친 줄의 「제목 아님」
BODY = "본문"


def labels(name, lines, rows, marks, sheet=True):
    """줄 이름표 — `[{row, text, marks, draft}]`(줄마다 · `sheet`면 0행 = 시트 이름). `draft`는 고정 규칙 초안의 단(0 = 제목 아님).

    `marks[행]`은 어댑터가 채운 표시(굵게 · 들여쓰기n · 병합 · 다른 열 …) — 번호 꼴은 여기서 단다(포맷 전부 한 벌).
    글 전체를 싣는다 — 보내는 쪽(core)이 앞 글자만 보내고 대상 이름은 전체 글자와 대조한다."""
    draft = {r["row"]: (r.get("level") or 0) for r in rows if r.get("heading")}
    out = [{"row": FRAME_ROW, "text": name, "marks": ["시트"], "draft": 0}] if sheet else []
    for n, t in lines:
        mk = list(marks.get(n) or [])
        hf = struct_map.heading_family(t)
        if hf:
            mk.append(f"번호{struct_map.FAMILY_LABEL.get(hf[0], hf[0])}")
        out.append({"row": n, "text": t, "marks": mk, "draft": draft.get(n, 0)})
    return out


def labels_hash(labs):
    raw = json.dumps([(x["row"], x["text"], x["marks"], x["draft"]) for x in labs], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def draft_structure(labs):
    """고정 규칙 초안을 구조의 꼴로 — 역할 없음 · 부모 = 앞의 더 얕은 초안 제목(판정이 없을 때 · 고침의 바탕)."""
    out, stack = [], []
    for x in labs:
        lv = x.get("draft") or 0
        if x["row"] == FRAME_ROW or not lv:
            continue
        while stack and stack[-1][0] >= lv:
            stack.pop()
        out.append({"row": x["row"], "parent": stack[-1][1] if stack else None, "role": None,
                    "name": None, "category": None})
        stack.append((lv, x["row"]))
    return out


def apply_fixes(st, fixes, labs):
    """사람의 고침(등록 단 · `{행: {role, name, category} | {role: "본문"}}`)을 구조 위에 — 결정적(재구축이 같은 고침을 쓴다).

    고칠 수 있는 것은 **역할과 대상**이다(단은 그대로) — 제목이 아니던 줄을 고치면 그 앞 제목의 형제로 선다."""
    if not fixes:
        return st
    st = dict(st or {"headings": draft_structure(labs), "source": "draft"})
    heads = {h["row"]: dict(h) for h in st.get("headings") or []}
    order = [x["row"] for x in labs]
    for k, fx in fixes.items():
        r = int(k)
        if r not in order:
            continue
        if fx.get("role") == BODY:
            heads.pop(r, None)
            for h in heads.values():
                if h.get("parent") == r:
                    h["parent"] = None
            continue
        if r not in heads:
            prev = [x for x in order[:order.index(r)] if x in heads and x != FRAME_ROW]
            heads[r] = {"row": r, "parent": heads[prev[-1]].get("parent") if prev else None}
        heads[r].update(role=fx.get("role"), name=fx.get("name"), category=fx.get("category"), by="사람")
    st["headings"] = [heads[r] for r in order if r in heads]
    st["fixed"] = len(fixes)
    return st


def structure_rows(lines, st):
    """검사된 구조 → `(rows, info)` — rows는 고정 규칙과 같은 꼴(단 = 부모 사슬의 깊이 · 신호 `구조`) ·
    info는 `{행: {row, parent, role, name, category, depth}}`(0행 = 시트 자신)."""
    present = {n for n, _t in lines}
    info, depth = {}, {}
    for h in st.get("headings") or []:
        r, p = h.get("row"), h.get("parent")
        if r == FRAME_ROW:
            info[r] = {**h, "depth": 0}
            continue
        if r not in present:
            continue
        depth[r] = depth.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1
        info[r] = {**h, "depth": depth[r]}
    rows = [{"row": n, "heading": n in depth, "level": depth.get(n, 0),
             "signal": SIG_STRUCT if n in depth else None} for n, _t in lines]
    return rows, info


def _cut_level(info, stats, pick, reason, oor):
    """구조가 선 프레임의 분할 레벨 — 크기로 고른 레벨과 **설비 · 유닛 · 사양 묶음 줄의 가장 깊은 단** 중 깊은 것."""
    need = max((v["depth"] for r, v in info.items() if r != FRAME_ROW and v.get("role") in CUT_ROLES), default=0)
    if pick is None or need <= pick:
        return pick, reason, oor
    st = (stats or {}).get(need) or {}
    avg = st.get("행수_평균")
    oor = avg is None or not (struct_map.CHUNK_MIN <= avg <= struct_map.CHUNK_MAX)
    return need, (f"구조 — {' · '.join(CUT_ROLES)} 줄 아래에서 자른다(단 {need}"
                  + (f" · 평균 {avg}행" if avg is not None else "") + f") · 크기로는 레벨 {pick}"), oor


def _chain_item(h, text, row=None):
    out = {"row": h.get("row", row), "text": text, "role": h.get("role")}
    if h.get("name") and h.get("category"):
        out.update(name=h["name"], category=h["category"])
    if h.get("by"):
        out["by"] = h["by"]
    return out


def structure_hook(ask, doc_id, *, kept=None, made=None, tally=None, fixes=None, skip=()):
    """어댑터에 건넬 **구조 훅** — 보존분(같은 원본 · 같은 이름표 · 같은 판)이면 그것(호출 0) · 아니면 `ask` 한 번.

    `ask(doc_id, frame, labels)` → 검사가 끝난 구조 `{headings: [{row, parent, role, name, category}], dropped, calls,
    failed?}` 또는 None(판정 없음 — mock 힌트 없음). `ask.key()`가 판(지시문 · config)을 말한다 · `skip`(`ref` 시트)은
    부르지 않는다. 사람의 고침(`fixes[frame]` — 등록 단)은 그 위에 덮는다. 실패한 판정은 보존하지 않는다(다음 인입이 다시 묻는다)."""
    kept, fixes = kept or {}, fixes or {}
    tally = tally if tally is not None else {}
    key = ask.key() if callable(getattr(ask, "key", None)) else None

    def fn(frame, labs):
        if frame in skip:
            return None
        h = labels_hash(labs)
        hit = kept.get(frame)
        if hit and hit.get("labels") == h and hit.get("key") == key:
            tally["재사용"] = tally.get("재사용", 0) + 1
            st = hit
        else:
            st = ask(doc_id, frame, labs)
            if st is not None:
                tally["호출"] = tally.get("호출", 0) + int(st.get("calls") or 0)
                st = {**st, "labels": h, "key": key}
                if made is not None and not st.get("failed"):
                    made[frame] = st
        st = apply_fixes(st, fixes.get(frame), labs)
        if st is not None:
            tally.setdefault("프레임", {})[frame] = {
                "labels": labs, "headings": st.get("headings") or [], "dropped": st.get("dropped") or [],
                "failed": st.get("failed"), "source": st.get("source"), "fixed": st.get("fixed", 0)}
        return st
    return fn
