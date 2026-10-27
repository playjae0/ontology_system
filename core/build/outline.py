# -*- coding: utf-8 -*-
"""칸 3.3 — **목차 노드화**(문서 개요 — B115 ① · B148 ②) — 메타의 목차를 보고 대상 제목마다 「이 층의 노드(카테고리)」 · 「좌표」 ·
「이 층의 노드 아님」을 정한다 (LLM 지점 ⑪ · 태그 `outline`).

**한 길**(B148 ② — 사용자 확정 2026-10-26 「메타는 범용 조건에서 쓴 문서 · 카테고리는 그래프 단계」): 엑셀 · Word · PPT · PDF 모든
형식의 제목이 이 함수 하나를 지난다(파서가 정한 제목을 옮기는 갈래 0) · 문서당 · 층(렌즈)당 한 번.

  · 입력 = **메타의 목차**(제목 경로 · 부모 · 깊이 · 메타가 정한 역할 · 이름 — `parts_info` · 없으면(구조 없는 슬라이드 · 쪽 제목) 이
    호출이 역할 · 이름도 정한다) + 항목마다 아래 청크 수 · 본문 줄 수 + 그 층의 닫힌 카테고리 · 정의문 + 층 힌트(층 config
    `prompts.structure` — 그것을 읽는 자리는 여기 하나다 · 덱은 회차 ④까지 따로). **본문 내용 0**.
  · **골격 이름 제목은 좌표** — LLM 판정 **앞에** 대상 제목의 이름을 골격 닫힌 목록에 대조한다(산문 소속 조회의 골격 단계와 같은
    함수 `Builder.resolve_anchor` — 사전 정확 · 별칭 · 라틴 접기 · Tier1 · 조회만 · LLM 0 · 큐 0) — 맞으면 좌표(`coord`)로 정하고
    묻지 않는다 · 착지는 지금 길(`heading.land` — 다른 공정 가드 · 골격 자신 · 트리 엣지 · 폴백 0).
  · 출력 = 제목마다 역할 · 대상 `{name, category}`(이름은 메타의 이름 그대로 — 메타에 없으면 답의 이름을 제목 글자와 대조) 또는 null ·
    좌표면 `coord: true`. **부모는 제목 트리가 정한다**(LLM이 바꾸지 않는다).
  · 대조(`_check`) — 이름은 제목 글자 안(밖이면 버림 · 결함 로그) · 카테고리는 닫힌 목록 안(밖이면 버림 · 결함 로그) · 빈칸 표시는
    주제다. 버린 제목은 주제와 같이 읽는다(하류가 그 위로 올라간다).
  · 체크포인트 `work/extract/outline/<doc_id>.json`(렌즈 `<doc_id>@<렌즈>.json` — 추출 폴더 안이라 기본 fresh가 남긴다) · 재사용
    조건 = **제목 계층 해시 · 메타 구조 해시 · 지시문 판(`3.3_outline.md`) · 층 config 판** — 층 config를 바꾸면 이 단계만 다시 묻는다
    (구조 판단은 보존분 재사용 — B148 ①).
  · mock — 힌트 `tests/fixtures/extract_hints/<doc_id>@outline.json`(`{제목 경로 또는 제목: {name?, category}}` 또는 `{role, name?,
    category?}`)만 · 없으면 판정 없음(메타의 역할 · 이름 그대로 · 대상 0 — 골격 대조는 돈다).

소비부 셋: 제목 개체 노드(`core/build/heading.land`) · 추출 입력의 소속 후보(`heading_candidates` — 넷째 출처 `제목`) · 상위로
올라가는 폴백 사슬과 연결 보강의 후보 범위(`ancestors` · `subtree`).
"""
from __future__ import annotations

import hashlib
import json
import time

from core.llm import gateway
from core.state import log, store
from core.state.ids import fold_latin, norm

_LOG = log.get(__name__)

#: 체크포인트 폴더 — 추출 폴더(`work/extract/`) 안의 하위 폴더(추출 체크포인트의 glob `<doc>@*.json`에 걸리지 않는다)
SUBDIR = "outline"
#: 지시문 이름(`prompts/3.3_outline.md`) · LLM 지점 이름(`gateway.POINTS`)
PROMPT = POINT = "outline"
#: 목차 노드화 답 꼴(B148 ② — 제목 id마다 역할 · 이름 · 카테고리 · 대상이 아니거나 이 층의 노드가 아니면 이름 · 카테고리 null)
SCHEMA = {
    "type": "object",
    "properties": {"headings": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "role": {"type": ["string", "null"]},
                       "name": {"type": ["string", "null"]}, "category": {"type": ["string", "null"]}},
        "required": ["id", "role", "name", "category"], "additionalProperties": False}}},
    "required": ["headings"], "additionalProperties": False,
}


# ---------------------------------------------------------------- 제목 트리 (포맷 전부 한 함수)
def parts(chunk):
    """조각 하나의 제목 사슬 — `[시트, 제목1, 제목2, …]`. 시트 이름(있으면) + `meta.section_path`를 ` › `로 자른 것.

    구획 경로가 **프레임 이름 그 자체**면(제목 없는 구간 — 어댑터가 프레임 이름으로 채운다) 제목이 아니다 —
    시트는 시트 칸이 따로 싣는다(맥락 줄 `extract_ctx.context_fields`와 같은 규칙). 연속 중복은 접는다."""
    from core.build import extract_ctx
    m = chunk.get("meta") or {}
    sheet, path = m.get("sheet"), m.get("section_path")
    out = [str(sheet)] if sheet else []
    if path and str(path) not in (str(sheet or ""), str(m.get("frame") or "")):
        for p in extract_ctx._path(path).split(extract_ctx.PATH_SEP):
            p = p.strip()
            if p and (not out or out[-1] != p):
                out.append(p)
    return out


def parts_info(chunk):
    """`parts(chunk)`와 같은 길이의 **구조** — 제목마다 메타가 단 역할 · 이름(`{row, text, role, name?}`) 또는 None.

    시트 칸은 `meta.structure_frame`(시트 자신 — 0행) · 경로 칸은 `meta.structure`를 글자로 차례대로 맞춘다(접힌 중복에도
    어긋나지 않게). 구조가 없는 조각(슬라이드 · 쪽 · mock 힌트 없음)은 전부 None."""
    from parser.struct_rule import chain_items
    return chain_items(parts(chunk), chunk.get("meta") or {})       # 시트명 · 제목 대조와 같은 손 (B157 ①)


def tree(env):
    """봉투 → 제목 트리 — `{"headings": [{id, text, parent, depth, path, struct?}], "of": {위치: 가장 깊은 제목 id}}`.

    id는 처음 나온 순서(1부터)라 부모가 자식보다 앞이다. 같은 사슬 = 같은 제목(경로가 열쇠). `struct`는 메타(문서 구조)가 그
    제목에 단 역할 · 이름(B119 ①) — 목차 노드화의 입력이다(옮기지 않는다 — B148 ②)."""
    from core.build import extract_ctx
    heads, by_key, of = [], {}, {}
    for c in (env or {}).get("chunks") or []:
        ps, info = parts(c), parts_info(c)
        pid = None
        for i in range(len(ps)):
            key = tuple(ps[:i + 1])
            if key not in by_key:
                by_key[key] = len(heads) + 1
                h = {"id": by_key[key], "text": ps[i], "parent": pid, "depth": i + 1,
                     "path": extract_ctx.PATH_SEP.join(key)}
                if info[i] is not None and info[i].get("role"):   # 역할이 선 제목만 — 역할 없는 사다리 단(코드)은 이 호출이 역할도 정한다 (B132)
                    h["struct"] = info[i]
                heads.append(h)
            pid = by_key[key]
        if pid is not None and c.get("source_locator"):
            of[c["source_locator"]] = pid
    return {"headings": heads, "of": of}


def heading_hash(heads):
    """제목 계층 해시 — 사슬(경로)의 목록만 · 재사용 조건의 첫 축."""
    raw = json.dumps([h["path"] for h in heads], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- 체크포인트
def checkpoint_path(doc_id, lens=None):
    from core.build import extract as EX
    return EX.EXTRACT_DIR / SUBDIR / (f"{doc_id}@{lens}.json" if lens else f"{doc_id}.json")


def structure_hash(heads):
    """메타(문서 구조)가 단 몫(경로 · 역할 · 이름 · 사람 고침)의 해시 — 구조가 없으면 None(옛 체크포인트와 같다)."""
    got = [(h["path"], (h["struct"] or {}).get("role"), (h["struct"] or {}).get("name"),
            (h["struct"] or {}).get("by")) for h in heads if "struct" in h]
    if not got:
        return None
    return hashlib.sha256(json.dumps(got, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _now_key(heads, cfg):
    """재사용 판 — 층 config 판은 추출 갈래 칸의 해시(B120 ③ — 추출과 같은 함수)."""
    from core.build import extract as EX
    from core.state import config_scope
    return {"heading_hash": heading_hash(heads), "prompt_version": EX.prompt_version(PROMPT),
            "config_extract": config_scope.extract_key(cfg), "structure": structure_hash(heads)}


_LABEL = {"heading_hash": "제목 계층", "prompt_version": "지시문", "config_extract": "층 config(추출 칸)",
          "structure": "문서 구조"}


def _reuse(doc_id, lens, now, p=None):
    """`(체크포인트 또는 None, 못 쓰는 이유)` — `p`를 주면 그 파일(리허설 산출 · B116 ②)을 같은 조건으로 본다."""
    p = p or checkpoint_path(doc_id, lens)
    if not p.exists():
        return None, "체크포인트 없음"
    try:
        ck = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"체크포인트를 읽지 못했다 — {type(e).__name__}"
    for k, v in now.items():
        if (ck.get(k) or None) != (v or None):
            return None, f"{_LABEL[k]} {str(ck.get(k))[:12] or '없음'} → {str(v)[:12] or '없음'}"
    return ck, ""


def load(doc_id, lens=None):
    """저장된 개요(맞춤표 · 연결 보강이 읽는다) — 없으면 None."""
    p = checkpoint_path(doc_id, lens)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def load_any(doc_id):
    """그 문서의 개요 하나 — 기본판 → 렌즈판(이름 순 첫 것). 제목 트리는 렌즈가 달라도 같다(대상만 렌즈마다)."""
    got = load(doc_id)
    if got is not None:
        return got
    d = checkpoint_path(doc_id).parent
    for p in sorted(d.glob(f"{doc_id}@*.json")) if d.exists() else []:
        got = load(doc_id, p.stem.split("@", 1)[1])
        if got is not None:
            return got
    return None


def _write(doc_id, lens, cfg, now, heads, of, source):
    from core import paths
    out = {"doc_id": doc_id, "stage": "outline", **now, "prompt": PROMPT,
           "prompt_text": gateway.prompt_text_hash(PROMPT),          # 지시문 이름 · 문면 해시 — 기록만 (B135 ③)
           "layer": cfg.get("layer"),
           "source": source, "headings": heads, "of": of}
    if lens:
        out["lens"] = lens
    p = checkpoint_path(doc_id, lens)
    paths.ensure(p)                        # 폴더를 만드는 자리는 하나다 (B78 1a)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return out


# ---------------------------------------------------------------- 판정 · 대조
def _stats(env, of):
    """제목 id → `(아래 청크 수, 본문 줄 수)` — 그 제목이 가장 깊은 제목인 청크만(내용 0 · 수만)."""
    out = {}
    by = {c.get("source_locator"): c for c in (env or {}).get("chunks") or []}
    for loc, hid in (of or {}).items():
        n, k = out.get(hid, (0, 0))
        text = str((by.get(loc) or {}).get("text") or "")
        out[hid] = (n + 1, k + sum(1 for ln in text.splitlines() if ln.strip()))
    return out


def _toc(heads, stats):
    """입력의 목차 — 제목마다 id · 경로 · 글 · 부모 · 깊이 · 메타의 역할 · 이름 · 아래 청크 수 · 본문 줄 수(본문 내용 0)."""
    from core.build import structure as ST
    out = []
    for h in heads:
        st = h.get("struct") or {}
        n, k = stats.get(h["id"], (0, 0))
        out.append({"id": h["id"], "path": h["path"], "text": h["text"][:ST.LINE_CHARS], "parent": h["parent"],
                    "depth": h["depth"], "role": st.get("role"), "name": st.get("name"), "chunks": n, "body_lines": k})
    return out


def _ask(heads, cfg, stats):
    """지점 ⑪ 실호출(목차 노드화 — 좌표가 아닌 제목 전부 · 문서당 · 층당 한 번) — `{id: {id, role, name, category}}`.

    층 힌트(`prompts.structure`)를 읽는 자리는 여기 하나다(B148 ⑤)."""
    from core.build.extract import categories_with_also
    out = gateway.chat(
        [{"role": "system", "content": gateway.prompt_for(PROMPT, {cfg.get("layer") or "-": cfg}, "structure")},
         {"role": "user", "content": json.dumps({"categories": categories_with_also(cfg), "toc": _toc(heads, stats)},
                                                ensure_ascii=False)}],
        json_schema=SCHEMA, point="outline")
    return {x.get("id"): x for x in (out or {}).get("headings") or [] if isinstance(x, dict)}


def _mock(doc_id, heads):
    """mock — 힌트 파일만(경로 또는 제목 글자가 열쇠 · 값 = 대상 `{name?, category}` 또는 `{role, name?, category?}`) ·
    없으면 None(판정 없음)."""
    from core.state import fixtures as _fx
    p = _fx.EXTRACT_HINTS / f"{doc_id}@outline.json"
    if not p.exists():
        return None
    hint = json.loads(p.read_text(encoding="utf-8"))
    gateway.mock(POINT, f"힌트 {p.name}")
    return {h["id"]: hint.get(h["path"], hint.get(h["text"])) for h in heads}


def _span(name, text):
    """제목 글자 안의 그 이름 — 정확(`norm`) → 라틴 대소문자 무시(B96 ④ · 제목의 글자로 돌려준다) · 없으면 None."""
    n, t = norm(name or ""), norm(text or "")
    if not n:
        return None
    if n in t:
        return n
    i = fold_latin(t).find(fold_latin(n))
    return t[i:i + len(n)] if i >= 0 else None


def _check(doc_id, h, target, cats):
    """답 하나의 대조 — `(target 또는 None, 버린 이유 또는 None)`."""
    from parser.normalizer import null_marker
    if not target:
        return None, None
    name, cat = target.get("name"), target.get("category")
    got = _span(name, h["text"])
    if got is None or null_marker(got):
        why = f"제목에 없는 이름 '{name}'"
    elif cat not in cats:
        why = f"닫힌 목록 밖 카테고리 '{cat}'"
    else:
        return {"name": got, "category": cat}, None
    store.append_defect(f"{doc_id}: 목차 노드화 — {why} (제목 '{h['path']}') → 버렸다(주제로 읽는다)")
    return None, why


def _role_target(doc_id, h, v):
    """답 하나 → `(역할, 대상)` — **메타가 역할을 정한 제목은 그 역할 · 이름 그대로**(답은 카테고리만 — B148 ②) · 메타에 역할이 없으면
    답이 역할 · 이름도 정한다(역할이 닫힌 셋 밖이면 역할 없음 · 결함 로그) · 대상이 아닌 역할이면 대상 0 · 옛 꼴(`{name, category}` —
    역할 없음)은 대상 그대로."""
    from parser.struct_rule import ROLES, TARGET_ROLES
    st = h.get("struct") or {}
    if st.get("role"):
        cat = v.get("category") if isinstance(v, dict) else None
        tgt = {"name": st.get("name"), "category": cat} if st["role"] in TARGET_ROLES and st.get("name") and cat else None
        return st["role"], tgt
    if not isinstance(v, dict):
        return None, None
    if "role" not in v:
        return None, v
    role = v.get("role")
    if role is not None and role not in ROLES:
        store.append_defect(f"{doc_id}: 목차 노드화 — 역할 밖 '{role}' (제목 '{h['path']}') → 역할 없음")
        role = None
    tgt = ({"name": v.get("name"), "category": v.get("category")}
           if (role is None or role in TARGET_ROLES) and v.get("name") else None)
    return role, tgt


def judge(doc_id, heads, cfg, answers):
    """답(`{id: 답}`)을 제목마다 대조해 싣는다 — 목록 밖 id는 버린다(결함 로그)."""
    cats = set((cfg.get("categories") or {}).keys())
    ids = {h["id"] for h in heads}
    for k in sorted(set(answers) - ids, key=str):
        store.append_defect(f"{doc_id}: 목차 노드화 — 목록 밖 제목 id {k!r} → 버렸다")
    out = []
    for h in heads:
        role, tgt = _role_target(doc_id, h, answers.get(h["id"]))
        t, why = _check(doc_id, h, tgt, cats)
        out.append({**h, "role": role, "target": t, **({"dropped": why} if why else {})})
    return out


def _skeleton(doc_id):
    """골격 대조 함수 `이름 → 골격 노드 id 또는 None` — 산문 소속 조회의 골격 단계와 같은 함수(`Builder.resolve_anchor` — 조회만 ·
    큐 0 · LLM 0 · 표기 모호면 None)."""
    from core.build.build import Builder
    from core.state.bootstrap import COORD_CATEGORY, coord_layer, load_config, open_graph
    lay = coord_layer()
    b = Builder(open_graph(lay), load_config(lay), None, doc_id, lay)
    return lambda name: b.resolve_anchor(name, COORD_CATEGORY, None, defer=[])[0]


def coords(doc_id, heads, skeleton=None):
    """**골격 이름 제목**(B148 ②) — `{제목 id: 대상}` — 대상이 될 수 있는 제목(메타 역할이 대상이거나 역할 없음)의 이름(메타의 이름 ·
    없으면 제목 글에서 번호 머리를 뗀 것)이 골격 노드에 맞으면 좌표 카테고리 · `coord: true`."""
    from core.state.bootstrap import COORD_CATEGORY
    from parser.struct_rule import heading_name
    look, out = None, {}
    for h in heads:
        name = heading_name(h["text"], h.get("struct"))   # 이름 고르기 한 손 — 파싱의 시트명 · 제목 대조와 같다 (B157 ①)
        if not name:
            continue
        look = look or skeleton or _skeleton(doc_id)
        if look(name):
            out[h["id"]] = {"name": name, "category": COORD_CATEGORY}
    return out


# ---------------------------------------------------------------- 한 문서 한 번
def _say(notice, info):
    from core.build.extract import _say as _s
    _s(notice, info)


def run(env, cfg, *, lens=None, notice=None, skeleton=None):
    """문서(렌즈) 하나의 목차 노드화 — `{"headings": [... target], "of": {위치: 제목 id}, "source"}`.

    재사용(조건이 같다 → LLM 0) · 골격 대조(LLM 0) · mock(힌트만) · 실호출(한 번). 예고 → (누적 줄) → 끝을 `notice`로 낸다."""
    doc_id = env["doc_id"]
    t = tree(env)
    heads = t["headings"]
    if not heads:
        return {"headings": [], "of": {}, "source": "none"}
    now = _now_key(heads, cfg)
    _carry(env, lens, now, notice)                 # 그 종류 등록 검수의 리허설 산출 — 조건이 같으면 운영 자리로 (B116 ②)
    ck, why = _reuse(doc_id, lens, now)
    if ck is not None:
        gateway.prompt_drift(PROMPT, ck)               # 판 그대로 · 문면만 바뀜이면 한 줄 (B135 ③)
        _say(notice, {"단계": "개요재사용", "렌즈": lens, "자리": checkpoint_path(doc_id, lens),
                      **_counts(ck["headings"])})
        return ck
    live = not gateway.use_mock()
    co = coords(doc_id, heads, skeleton)                     # 골격 이름 제목 — 묻지 않는다 (B148 ②)
    rest = [h for h in heads if h["id"] not in co]
    _say(notice, {"단계": "개요예고", "렌즈": lens, "제목": len(heads), "구조": sum(1 for h in heads if "struct" in h),
                  "좌표": len(co), "호출": 1 if (live and rest) else 0, "다시": why if why != "체크포인트 없음" else None})
    u0, t0 = gateway.usage_total(), time.monotonic()
    answers = (_ask(rest, cfg, _stats(env, t["of"])) if live else _mock(doc_id, rest)) if rest else {}
    judged = {h["id"]: h for h in judge(doc_id, rest, cfg, answers or {})}
    merged = [{**h, "role": (h.get("struct") or {}).get("role") or "대상", "target": co[h["id"]], "coord": True}
              if h["id"] in co else judged[h["id"]] for h in heads]
    if answers is None and not co and not any("struct" in h for h in heads):   # mock · 힌트 없음 · 구조 없음 — 판정이 없었다(체크포인트 0)
        out = {"headings": merged, "of": t["of"], "source": "mock"}
    else:
        src = "live" if (live and rest) else "hint" if answers else "structure" if not co else "skeleton"
        out = _write(doc_id, lens, cfg, now, merged, t["of"], src)
    _LOG.info("목차 노드화 %s%s · 대상 %s", doc_id, f"@{lens}" if lens else "",
              [(h["path"], h["target"]) for h in out["headings"] if h.get("target")])
    _say(notice, {"단계": "개요끝", "렌즈": lens, "since": u0, "초": round(time.monotonic() - t0, 1),
                  "자리": checkpoint_path(doc_id, lens) if out.get("source") != "mock" else None,
                  **_counts(out["headings"])})
    return out


def _carry(env, lens, now, notice):
    """리허설 산출의 개요(그 doc_type · 그 문서 · 그 렌즈)가 있으면 — 지금 조건과 같을 때 옮기고, 다르면 쓰지 않고 지운다."""
    from core.state import rehearsal as RH
    dst = checkpoint_path(env["doc_id"], lens)
    src = RH.carried(env.get("doc_type"), env["doc_id"], RH.OUTLINE, dst.name)
    if src is None:
        return
    ck, why = _reuse(env["doc_id"], lens, now, src)
    RH.take(src, dst if ck is not None else None)
    _say(notice, {"단계": "개요리허설", "렌즈": lens, "쓴다": ck is not None, "이유": why, "자리": dst,
                  "종류": env.get("doc_type")})


def _counts(heads):
    tg = [h for h in heads if h.get("target")]
    roles = {}
    for h in heads:
        if h.get("role"):
            roles[h["role"]] = roles.get(h["role"], 0) + 1
    return {"제목": len(heads), "대상": len(tg), "버림": sum(1 for h in heads if h.get("dropped")),
            "주제": sum(1 for h in heads if not h.get("target") and not h.get("dropped")),
            "역할": roles, "구조": sum(1 for h in heads if "struct" in h), "좌표": sum(1 for h in heads if h.get("coord")),
            "대상목록": [(h["path"], h["target"]["name"], h["target"]["category"]) for h in tg]}


# ---------------------------------------------------------------- 소비부의 질문
def by_id(ol):
    return {h["id"]: h for h in (ol or {}).get("headings") or []}


def chain_of(ol, hid):
    """그 제목과 그 위 — 가까운 것부터 `[제목]`(주제 포함 · 맨 위까지)."""
    hs = by_id(ol)
    out, cur = [], hid
    while cur is not None and cur in hs and len(out) < 64:
        out.append(hs[cur])
        cur = hs[cur].get("parent")
    return out


def chain(ol, locator):
    """그 조각 위의 제목 — 가까운 것부터 `[제목]`(주제 포함 · 맨 위까지)."""
    return chain_of(ol, ((ol or {}).get("of") or {}).get(locator))


def ancestors(ol, locator):
    """그 조각 위의 **제목 개체**(대상으로 정해진 제목만) — 가까운 것부터 `[제목]`."""
    return [h for h in chain(ol, locator) if h.get("target")]


def heading_candidates(ol, locator):
    """추출 입력의 넷째 소속 출처 — `[{name, category}]` 가까운 것부터(비면 빈 목록)."""
    return [dict(h["target"]) for h in ancestors(ol, locator)]


def structure_chain(ol, locator):
    """추출 · 연결 보강 입력의 **구조 사슬**(B119 ②) — 그 조각 위의 제목 줄 위에서 아래로 `[{role, text, name?, category?}]`."""
    out = []
    for h in reversed(chain(ol, locator)):
        x = {"role": h.get("role"), "text": h["text"]}
        if h.get("target"):
            x.update(name=h["target"]["name"], category=h["target"]["category"])
        out.append(x)
    return out


def targets_key(ol):
    """추출 재사용 조건의 개요 몫 — 역할 · 대상이 선 제목(경로 · 역할 · 이름 · 카테고리)의 해시 · 없으면 None(옛 체크포인트와 같다)."""
    tg = [(h["path"], h.get("role"), (h.get("target") or {}).get("name"), (h.get("target") or {}).get("category"))
          for h in (ol or {}).get("headings") or [] if h.get("target") or h.get("role")]
    if not tg:
        return None
    return hashlib.sha256(json.dumps(tg, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
