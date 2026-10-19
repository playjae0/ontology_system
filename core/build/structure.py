# -*- coding: utf-8 -*-
"""칸 2.4·2.5 — **문서 구조** — 산문 시트(프레임)마다 LLM이 **무조건** 줄 이름표를 보고 제목 줄의 단 · 역할 · 대상을 (B119 ①).

사내(2026-10-16): 고정 규칙이 **일부만** 맞는 문서(가장 흔한 경우)가 LLM 없이 통과해 번호 없는 유닛 줄이 트리에
없었다(`시트 › 지정사양` — 유닛이 경로에서 사라졌다). 고정 규칙은 **초안**이고 판정은 이 호출이 한다:

  · 입력 = 시트의 **줄 전체**(행 · 줄당 `LINE_CHARS`자까지 · 표시 — 굵게 · 들여쓰기 · 병합 · 번호 꼴 · 다른 열 · 빈 줄) + **고정
    규칙의 초안 단** + **형태 요약**(번호 꼴 가족 · 들여쓰기 단 · 빈 줄 — 코드가 센다 · B124 ①) + 층의 닫힌 카테고리 · 정의문 +
    층 힌트(`prompts.structure`). 긴 시트는 어림 `CALL_TOKENS`씩 나눠 부르고 뒤 묶음에는 앞에서 열린 제목(`open`)을 싣는다.
  · 출력 = 제목 줄마다 `{row, parent, role, name, category}`(역할은 닫힌 셋 · 층 중립 — `parser.struct_rule.ROLES`) + **청크
    구간** `[{from_row, to_row, owner_row}]`(B124 ② — 코드는 검사만 `check_chunks` · 어긋나면 그 시트만 지금 방식).
  · **문서 개요(⑪)와 구조 규칙(⑦ `struct_rule`)을 한 호출로 합쳤다** — 지시문은 개요의 것(`prompts/3.3_outline.md`
    o-2.0 — 제목 목록만 오는 문서도 같은 지시문 · 같은 검사) · 호출 태그 `structure`는 지점 ⑪이다(지점 수 불변).
  · 검사(`check` — 결정적): 목록 밖 줄 · 역할 밖 · 앞에 없는 부모는 그 줄을 버리고 **초안으로**(초안이 제목이면 초안의
    단 · 역할 없음) · 이름이 줄 글자 밖이거나 카테고리가 목록 밖이면 **대상만** 버린다(역할은 그대로) · 전부 결함 로그.
    호출이 실패하면 그 시트는 초안 그대로(`failed` — 보존하지 않는다 · 화면에 수).
  · 보존 = 구조 지도 보존 파일 `work/struct_maps/<doc_id>.json`의 `structure[<시트>]`(원본 바이트 해시 · 이름표 해시 ·
    판 — 지시문 · 층 config). 같은 파일이면 LLM 0 · 재구축이 재생한다 · 등록 리허설 산출도 같은 파일(B116 ②).
  · mock — 힌트 `tests/fixtures/extract_hints/<doc_id>@structure.json`(`{시트: [{text, depth, role, name?, category?}]}`
    — 줄 글자 · 단으로 적는다 · 0단 = 시트 자신)만 · 없으면 None(판정 없음 — 고정 규칙 그대로 · 호출 0).

코드에 층 어휘 0 — 카테고리는 층 config가 · 역할은 닫힌 시스템 어휘(파서 계약)가 말한다.
"""
from __future__ import annotations

import json

from core.llm import gateway
from core.state import log, store
from parser.struct_rule import FRAME_ROW, ROLES, TARGET_ROLES, UNIT_ROLES

_LOG = log.get(__name__)

#: 지시문 이름(`prompts/3.3_outline.md` — 개요와 한 벌) · 호출 태그(지점 ⑪ — `gateway.CALL_TAGS`)
PROMPT, TAG = "outline", "structure"
#: 줄 하나에 싣는 글자 수 — **줄 전체**가 원칙이고 이것은 상한이다(B124 ① — 사내 손잡이 `structure_line_chars` · 창작 기본값)
LINE_CHARS = 300
#: 한 호출에 싣는 양(어림 토큰 — 줄 JSON 글자 수 / 2) — 넘으면 나눠 부르고 뒤 묶음에 열린 제목을 싣는다(사내 손잡이
#: `structure_call_tokens` · 기본값은 RFQ 시트 한 장이 한 번에 드는 크기 · 창작 기본값)
CALL_TOKENS = 40000

SCHEMA = {
    "type": "object",
    "properties": {"headings": {"type": "array", "items": {
        "type": "object",
        "properties": {"row": {"type": "integer"},
                       "parent": {"type": ["integer", "null"]},
                       "role": {"type": "string", "enum": list(ROLES)},
                       "name": {"type": ["string", "null"]},
                       "category": {"type": ["string", "null"]}},
        "required": ["row", "parent", "role", "name", "category"], "additionalProperties": False}},
        # **청크 구간**(B124 ② — 나무와 함께 · 제목 목록만 오는 호출은 빈 목록) — 코드는 검사만 한다(`check_chunks`)
        "chunks": {"type": "array", "items": {
            "type": "object",
            "properties": {"from_row": {"type": "integer"}, "to_row": {"type": "integer"},
                           "owner_row": {"type": ["integer", "null"]}},
            "required": ["from_row", "to_row", "owner_row"], "additionalProperties": False}}},
    "required": ["headings", "chunks"], "additionalProperties": False,
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
    """보존분 재사용의 판 — 지시문 판 · 층 config 판(층마다 추출 갈래 칸의 해시 — B120 ③ · 추출과 같은 함수)."""
    from core.build.extract import prompt_version
    from core.state import config_scope
    return {"prompt_version": prompt_version(PROMPT),
            "config_extract": " · ".join(f"{k}:{config_scope.extract_key(c)}" for k, c in sorted(cfgs.items()))}


# ---------------------------------------------------------------- 실호출
def _line(x):
    return {"row": x["row"], "draft": x.get("draft") or 0, "marks": x.get("marks") or [],
            "text": str(x.get("text") or "")[:LINE_CHARS]}


def form_summary(labs):
    """**형태 요약**(B124 ① — 코드가 센다 · 판정 아님): 번호 꼴 가족별 줄 목록과 개수 · 들여쓰기 단별 줄 · 빈 줄 자리."""
    fam, ind, gap = {}, {}, []
    for x in labs:
        for m in x.get("marks") or []:
            if m.startswith("번호"):
                fam.setdefault(m[2:], []).append(x["row"])
            elif m.startswith("들여쓰기"):
                ind.setdefault(m[4:], []).append(x["row"])
            elif m == "빈 줄":
                gap.append(x["row"])
    return {"번호 꼴": [{"꼴": k, "수": len(v), "줄": v} for k, v in sorted(fam.items(), key=lambda kv: kv[1][0])],
            "들여쓰기": [{"단": k, "수": len(v), "줄": v} for k, v in sorted(ind.items())],
            "빈 줄 아래": gap}


def _size_hint():
    from parser import struct_map
    return struct_map.CHUNK_MAX_CHARS


def ask_lines(frame, lines, cats, open_=(), form=None, cfgs=None):
    """지점 ⑪(태그 `structure`) 한 호출 — `(제목 [{row, parent, role, name, category}], 청크 구간 [{from_row, to_row, owner_row}])`.
    지시문 + 층 힌트(`prompts.structure` — `gateway.prompt_for` 한 함수 · B124 ③)."""
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(PROMPT, cfgs or {}, "structure")},
         {"role": "user", "content": json.dumps(
             {"categories": cats, "frame": frame, "open": list(open_), "form": form or {},
              "size_hint": _size_hint(), "lines": lines},
             ensure_ascii=False)}],
        json_schema=SCHEMA, point="structure")
    return ([h for h in (out or {}).get("headings") or [] if isinstance(h, dict)],
            [c for c in (out or {}).get("chunks") or [] if isinstance(c, dict)])


def _open(acc, labs_by_row, before):
    """뒤 묶음에 싣는 **열린 제목** — 앞 묶음의 마지막 제목에서 위로(위에서 아래 순)."""
    last = [r for r in acc if r != FRAME_ROW and r < before]
    out, cur, n = [], (max(last) if last else None), 0
    while cur is not None and cur in acc and n < 64:
        out.append({"row": cur, "text": str(labs_by_row[cur]["text"])[:LINE_CHARS], "role": acc[cur].get("role")})
        cur, n = acc[cur].get("parent"), n + 1
    return list(reversed(out))


def _batches(labs):
    """한 호출에 실을 줄 묶음 — 어림 토큰(줄 JSON 글자 수 / 2)이 `CALL_TOKENS`를 넘기 전에 끊는다(시트 한 장이면 대개 한 묶음)."""
    out, cur, size = [], [], 0
    for x in labs:
        t = len(json.dumps(_line(x), ensure_ascii=False)) // 2 + 1
        if cur and size + t > CALL_TOKENS:
            out.append(cur)
            cur, size = [], 0
        cur.append(x)
        size += t
    return out + ([cur] if cur else [])


def _live(doc_id, frame, labs, cats, cfgs=None):
    """묶음마다 한 호출 — `(답, 청크 구간, 호출 수, 실패 사유 또는 None)` · 형태 요약은 시트 전체로 한 번 센다."""
    by_row = {x["row"]: x for x in labs}
    form = form_summary(labs)
    answers, chunks, calls, done = [], [], 0, 0
    for batch in _batches(labs):
        acc = {a["row"]: a for a in answers if isinstance(a.get("row"), int) and a.get("row") in by_row}
        calls += 1
        try:
            hs, cs = ask_lines(frame, [_line(x) for x in batch], cats,
                               _open(acc, by_row, batch[0]["row"]) if done else (), form, cfgs)
        except gateway.GatewayError as e:
            store.append_defect(f"{doc_id}: 문서 구조 호출 실패 — 시트 '{frame}' {done + 1}~{done + len(batch)}줄 — {e} → 초안")
            return answers, [], calls, f"{type(e).__name__}: {str(e)[:120]}"
        answers += hs
        chunks += cs
        done += len(batch)
    return answers, chunks, calls, None


# ---------------------------------------------------------------- mock
def hint_answers(doc_id, frame, labs):
    """mock — 힌트를 답의 꼴로 · 없으면 None(판정 없음). 시트마다 `[{text, depth, role, name?, category?}]`(제목만) 또는
    `{"headings": [...], "chunks": [{from_row, to_row, owner_row}]}`(청크 구간까지 — B124 ②) — 돌려주는 것은 `(제목, 구간)`."""
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@structure.json"
    if not p.exists():
        return None
    hint = json.loads(p.read_text(encoding="utf-8")).get(frame)
    if hint is None:
        return None
    gateway.mock(TAG, f"힌트 {p.name} · {frame}")
    chunks = list(hint.get("chunks") or []) if isinstance(hint, dict) else []
    hint = hint.get("headings") or [] if isinstance(hint, dict) else hint
    rows = [x for x in labs if x["row"] != FRAME_ROW]
    out, stack, at = [], [], 0
    for e in hint:
        d = int(e.get("depth") or 0)
        if d == 0:
            out.append({"row": FRAME_ROW, "parent": None, "role": e.get("role"), "name": e.get("name"),
                        "category": e.get("category")})
            continue
        want = str(e.get("text") or "").strip()
        i = next((j for j in range(at, len(rows)) if str(rows[j]["text"]).strip() == want), None)
        if i is None:
            _LOG.warning("문서 구조 힌트 — 시트 '%s'에 없는 줄 %r (건너뜀)", frame, want)
            continue
        at = i + 1
        while stack and stack[-1][0] >= d:
            stack.pop()
        out.append({"row": rows[i]["row"], "parent": stack[-1][1] if stack else None, "role": e.get("role"),
                    "name": e.get("name"), "category": e.get("category")})
        stack.append((d, rows[i]["row"]))
    return out, chunks


# ---------------------------------------------------------------- 검사 (결정적)
def check(doc_id, frame, labs, answers, cats):
    """답의 검사 — `(제목 줄 [{row, parent, role, name, category}], 버림 [{row, why, target?}])` · 이름표 순서.

    줄을 버린 것(목록 밖 · 역할 밖 · 앞에 없는 부모)은 **초안으로**(초안이 제목이면 초안의 단 · 역할 없음) · 대상만 버린
    것(줄 글자 밖 이름 · 목록 밖 카테고리)은 역할을 남긴다. 전부 결함 로그."""
    from core.build.outline import _span
    from parser.normalizer import null_marker
    by_row = {x["row"]: x for x in labs}
    order = {x["row"]: i for i, x in enumerate(labs)}
    acc, dropped = {}, []

    def drop(r, why, target=False):
        store.append_defect(f"{doc_id}: 문서 구조 — {why} (시트 '{frame}' {r}행) → "
                            + ("대상을 버렸다(역할은 그대로)" if target else "초안으로"))
        dropped.append({"row": r, "why": why, **({"target": True} if target else {})})

    for a in sorted(answers or [], key=lambda a: order.get(a.get("row"), len(order))):
        r, role, p = a.get("row"), a.get("role"), a.get("parent")
        if r not in by_row or r in acc:
            drop(r, "목록 밖 줄" if r not in by_row else "같은 줄을 두 번 냈다")
            continue
        if role not in ROLES:
            drop(r, f"역할 밖 '{role}'")
            continue
        p = None if r == FRAME_ROW or p == FRAME_ROW else p
        if p is not None and (p not in acc or order[p] >= order[r]):
            drop(r, f"부모 {p}행이 앞의 제목이 아니다")
            continue
        h = {"row": r, "parent": p, "role": role, "name": None, "category": None}
        if role in TARGET_ROLES and (a.get("name") or a.get("category")):
            got = _span(a.get("name"), by_row[r]["text"])
            if got is None or null_marker(got):
                drop(r, f"줄 글자 밖 이름 '{a.get('name')}'", target=True)
            elif a.get("category") not in cats:
                drop(r, f"닫힌 목록 밖 카테고리 '{a.get('category')}'", target=True)
            else:
                h.update(name=got, category=a["category"])
        acc[r] = h
    _to_draft(labs, acc, {d["row"] for d in dropped if not d.get("target")})
    return [acc[x["row"]] for x in labs if x["row"] in acc], dropped


def check_chunks(doc_id, frame, labs, heads, chunks):
    """청크 구간의 검사(B124 ② — 결정적 · 코드는 검사만) — `(구간 [{from_row, to_row, owner_row}] 또는 None, 버린 사유)`.

    모든 줄이 한 구간에 · 겹침 0 · 주인(`owner_row`)은 그 구간 위쪽(또는 첫 줄)의 제목 줄이거나 시트(0 · null) · 어긋나면 그 시트만
    지금 방식으로 자른다(결함 로그 · 구조 표의 수). 크기는 여기서 보지 않는다 — 넘는 구간은 자르는 자리(`parser.struct_rule.
    range_chunks`)가 형제 줄 앞에서 나눈다. 구간을 내지 않았으면 `(None, None)`(지금 방식 · 버림 아님)."""
    if not chunks:
        return None, None
    rows = [x["row"] for x in labs if x["row"] != FRAME_ROW]
    heads_at = {h["row"] for h in heads}
    got, why = [], None
    for c in sorted(chunks, key=lambda c: (c.get("from_row") if isinstance(c.get("from_row"), int) else -1)):
        a, b, o = c.get("from_row"), c.get("to_row"), c.get("owner_row")
        if not isinstance(a, int) or not isinstance(b, int) or a > b:
            why = f"구간 꼴이 아니다 {c}"
            break
        if o not in (None, FRAME_ROW) and (o not in heads_at or o > a):
            why = f"{a}~{b}행의 주인 {o}행이 그 위쪽 제목 줄이 아니다"
            break
        got.append({"from_row": a, "to_row": b, "owner_row": o})
    if why is None:
        hit = {r: sum(1 for g in got if g["from_row"] <= r <= g["to_row"]) for r in rows}
        miss, dup = [r for r, n in hit.items() if n == 0], [r for r, n in hit.items() if n > 1]
        why = (f"구간 밖 줄 {len(miss)}(첫 {miss[0]}행)" if miss else
               f"겹친 줄 {len(dup)}(첫 {dup[0]}행)" if dup else None)
    if why:
        store.append_defect(f"{doc_id}: 문서 구조 — 청크 구간을 버렸다({why}) · 시트 '{frame}' → 지금 방식으로 자른다")
        return None, why
    return got, None


def _to_draft(labs, acc, rows):
    """버린 줄이 초안의 제목이면 초안의 단으로 — 부모 = 앞의 제목 중 단이 더 얕은 가장 가까운 것."""
    depth = {}
    for x in labs:
        r = x["row"]
        if r in acc and r != FRAME_ROW:
            p = acc[r].get("parent")
            depth[r] = depth.get(p, 0) + 1 if p is not None else 1
        elif r in rows and (x.get("draft") or 0) and r not in acc:
            lv = x["draft"]
            prev = [q for q in depth if q in acc and depth[q] < lv]
            acc[r] = {"row": r, "parent": prev[-1] if prev else None, "role": None, "name": None,
                      "category": None, "draft": True}
            depth[r] = depth.get(acc[r]["parent"], 0) + 1


# ---------------------------------------------------------------- 주입 함수
def structurer(layers=None):
    """파서에 내려보낼 **문서 구조 함수** `fn(doc_id, frame, labels)` — 실호출이면 ⑪(태그 `structure`) · mock이면 힌트.

    `fn.key()`가 보존분의 판(지시문 · 층 config)이다 · 돌려주는 것은 검사가 끝난 구조 또는 None(판정 없음)."""
    cfgs = _cfgs(layers)
    cats = categories(cfgs)
    live = not gateway.use_mock()

    def fn(doc_id, frame, labs):
        from core.build.extract import prompt_version
        if live:
            gateway.require(TAG)                    # 부르기 직전의 관문(설정 없음 = 명시적 실패 · 조립은 막지 않는다)
            answers, chunks, calls, failed = _live(doc_id, frame, labs, cats, cfgs)
            source = "live"
        else:
            got = hint_answers(doc_id, frame, labs)
            if got is None:
                return None
            (answers, chunks), calls, failed = got, 0, None
            source = "hint"
        heads, dropped = check(doc_id, frame, labs, answers if not failed else [], cats)
        if failed:                                  # 호출 실패 — 그 시트는 초안 그대로(보존 0 · 다음 인입이 다시 묻는다)
            from parser.struct_rule import draft_structure
            heads, chunks = draft_structure(labs), []
        ranges, why = check_chunks(doc_id, frame, labs, heads, chunks)
        _LOG.info("문서 구조 %s · %s — 제목 %d · 버림 %d · 구간 %s · 호출 %d%s", doc_id, frame, len(heads), len(dropped),
                  len(ranges) if ranges else (f"버림({why})" if why else 0), calls, f" · 실패 {failed}" if failed else "")
        return {"headings": heads, "dropped": dropped, "calls": calls, "source": source,
                "prompt_version": prompt_version(PROMPT), **({"chunks": ranges} if ranges else {}),
                **({"chunks_dropped": why} if why else {}), **({"failed": failed} if failed else {})}
    fn.key = lambda: key(cfgs)
    return fn


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


# ---------------------------------------------------------------- 구조 표 · 약한 구조 신호 (화면 · 기록의 재료)
def sibling_clash(fr):
    """**같은 번호 꼴 형제의 단 · 역할이 다르다**(B124 ② — 약한 구조 신호 · 자동으로 고치지 않는다) — `{꼴: [행 …]}`.
    꼴(`번호<꼴>` 표시)이 같은 줄이 둘 이상인데 (단, 역할)이 갈린 꼴만 · 제목이 아닌 줄은 (0, 없음)."""
    depth = {h["row"]: d for h, d in zip(fr.get("headings") or [], _depth_list(fr.get("headings") or []))}
    role = {h["row"]: h.get("role") for h in fr.get("headings") or []}
    fam = {}
    for x in fr.get("labels") or []:
        for m in x.get("marks") or []:
            if m.startswith("번호"):
                fam.setdefault(m[2:], []).append(x["row"])
    return {k: v for k, v in fam.items()
            if len(v) > 1 and len({(depth.get(r, 0), role.get(r)) for r in v}) > 1}


def _depth_list(heads):
    depth = {}
    for h in heads:
        p = h.get("parent")
        depth[h["row"]] = 0 if h["row"] == FRAME_ROW else (depth.get(p, 0) + 1 if p not in (None, FRAME_ROW) else 1)
    return [depth[h["row"]] for h in heads]


def range_lines(report):
    """구조 표 아래 줄 — 시트마다 청크 구간(`a~b행(주인 r행 '글')`) 또는 버린 사유(지금 방식으로 잘랐다)."""
    out = []
    for frame, fr in ((report or {}).get("프레임") or {}).items():
        text = {x["row"]: str(x.get("text") or "") for x in fr.get("labels") or []}
        if fr.get("chunks"):
            parts = [f"{g['from_row']}~{g['to_row']}행(주인 " + (f"{g['owner_row']}행 '{text.get(g['owner_row'], '')[:20]}'"
                     if g.get("owner_row") not in (None, FRAME_ROW) else "시트") + ")" for g in fr["chunks"]]
            out.append(f"   청크 구간 — 시트 '{frame}' {len(parts)}: " + " · ".join(parts))
        elif fr.get("chunks_dropped"):
            out.append(f"   청크 구간 버림 — 시트 '{frame}' ({fr['chunks_dropped']}) → 지금 방식으로 잘랐다")
    return out


def table(report):
    """구조 표의 행 — `[{번호, 시트, 행, 단, 역할, 이름, 카테고리, 초안, 다름, 형제, by}]`(제목 줄 · 시트 줄 포함 · 이름표 순)."""
    out = []
    for frame, fr in ((report or {}).get("프레임") or {}).items():
        clash = {r: k for k, rows in sibling_clash(fr).items() for r in rows}
        labs = {x["row"]: x for x in fr.get("labels") or []}
        depth = {}
        for h in fr.get("headings") or []:
            r, p = h["row"], h.get("parent")
            d = 0 if r == FRAME_ROW else (depth.get(p, 0) + 1 if p is not None else 1)
            depth[r] = d
            x = labs.get(r) or {}
            dr = x.get("draft") or 0
            out.append({"번호": len(out) + 1, "시트": frame, "행": r, "단": d, "역할": h.get("role"),
                        "이름": h.get("name"), "카테고리": h.get("category"), "글": x.get("text") or "",
                        "초안": dr, "다름": r != FRAME_ROW and dr != d, "형제": clash.get(r), "by": h.get("by")})
        for x in fr.get("labels") or []:            # 초안은 제목인데 구조가 뺀 줄 — 다름으로 보인다
            if (x.get("draft") or 0) and x["row"] not in depth:
                out.append({"번호": len(out) + 1, "시트": frame, "행": x["row"], "단": 0, "역할": None,
                            "이름": None, "카테고리": None, "글": x.get("text") or "", "초안": x["draft"],
                            "다름": True, "by": None, "본문": True})
    return out


def weak(report, pieces=(), coord_in=True):
    """**약한 구조 신호**(B119 ③ — 구현이 센다) — 시트마다 `{시트: [신호 문장]}`(없으면 빈 dict).

    ①대상 0 — 제목이 둘 이상인데 대상 역할이 0(문서의 층에 좌표 층이 있을 때 — `coord_in`) ②초안과 다름 —
    경계(제목 줄 집합)가 다른 줄 수 · 단 수 ③상한에서 잘린 청크 ④같은 번호 꼴 형제의 단 · 역할이 다름(B124 ②) ⑤청크 구간
    버림(B124 ②) ⑥호출 실패 · 버린 줄."""
    out = {}
    cut = {}
    for c in pieces or []:
        m = c.get("meta") or {}
        if m.get("char_cap_from") or m.get("over_char_cap"):
            cut[m.get("frame")] = cut.get(m.get("frame"), 0) + 1
    for frame, fr in ((report or {}).get("프레임") or {}).items():
        heads = [h for h in fr.get("headings") or [] if h["row"] != FRAME_ROW]
        labs = fr.get("labels") or []
        got = []
        if coord_in and len(heads) >= 2 and not any(h.get("role") in UNIT_ROLES for h in heads):
            got.append(f"대상 0(제목 {len(heads)})")
        draft = {x["row"] for x in labs if x.get("draft")}
        mine = {h["row"] for h in heads}
        diff = len(draft ^ mine)
        if diff:
            d_lv = len({x["draft"] for x in labs if x.get("draft")})
            s_lv = len({d for d in _depths(heads).values()})
            got.append(f"초안과 경계 다름 {diff}줄 · 단 수 {d_lv} → {s_lv}")
        if cut.get(frame):
            got.append(f"글자 상한에서 잘린 청크 {cut[frame]}")
        for k, rows in sibling_clash(fr).items():
            got.append(f"같은 번호 꼴 「{k}」 형제 {len(rows)}줄의 단 · 역할이 다르다")
        if fr.get("chunks_dropped"):
            got.append(f"청크 구간 버림({fr['chunks_dropped']}) — 지금 방식으로 잘랐다")
        if fr.get("failed"):
            got.append("구조 호출 실패 — 초안 그대로")
        elif fr.get("dropped"):
            got.append(f"버린 줄 {len(fr['dropped'])}(초안 · 대상 버림)")
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
    """구조 끝 줄의 수 — 시트 · 제목 · 역할별 · 호출 · 재사용 · 버림 · 실패 · 사람 고침."""
    fr = (report or {}).get("프레임") or {}
    heads = [h for f in fr.values() for h in f.get("headings") or [] if h["row"] != FRAME_ROW]
    roles = {}
    for h in heads:
        roles[h.get("role") or "역할 없음"] = roles.get(h.get("role") or "역할 없음", 0) + 1
    return {"시트": len(fr), "제목": len(heads), "역할": roles, "호출": (report or {}).get("호출", 0),
            "재사용": (report or {}).get("재사용", 0),
            "버림": sum(len(f.get("dropped") or []) for f in fr.values()),
            "실패": sum(1 for f in fr.values() if f.get("failed")),
            "고침": sum(int(f.get("fixed") or 0) for f in fr.values())}
