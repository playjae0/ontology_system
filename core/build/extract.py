# -*- coding: utf-8 -*-
"""칸 3.3 — n3 추출 단계 — 파싱과 구축 사이의 **독립 단계** (CH3A 3.1·3.11, 틀 Q1).

파서↔에이전트에 계약 A(CH2 2.2)가 있듯, 추출↔구축에는 **계약 B**가 있다.
산출물 `extract/{doc_id}.json`의 **존재가 곧 "추출 완료" 상태**다(P-1) —
구축은 이 파일만 읽고, 있으면 추출을 다시 부르지 않는다.

계약 (CH3A 3.11 규약):
  1. **후보는 표면형으로만 말한다.** 노드 id 참조 금지 — "그것이 기존의 무엇인가"는
     구축(판정)의 몫이다. 추출 파일에 노드 id가 들어가는 순간 추출이 그래프 상태에
     의존하게 되어 체크포인트가 재현 불가능해진다.
  2. **confidence를 두지 않는다.** 판정·게이트가 별도 단계로 있으므로 추출 자신의
     확신도는 소비처가 없다 — 쓰이지 않는 숫자는 언젠가 잘못 쓰인다(P7).
  3. **span·오프셋도 두지 않는다.** LLM이 내는 오프셋은 자주 틀려 검증 코드가 또
     필요해지고, 청크는 이미 작은 근거 단위다.
  4. **재현성 3입력을 전부 기록한다** — adapter_version(봉투에서 복사) ·
     prompt_version(지시문 템플릿) · config_version(층 어휘). 따로 개정되므로 따로 적는다.
  7. **재인입 시 그 doc_id의 체크포인트는 무효화·재생성**한다 — 청크가 바뀌었으므로.

**파서는 이 파일을 읽지도 쓰지도 않는다.**
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from core import paths
from core.llm import gateway
from core.state import log, store
from core.state.ids import doc_hash, fold_latin, norm

ROOT = paths.ROOT                  # 레포 루트는 자리 소유자가 안다 (B78)
EXTRACT_DIR = paths.extract()   # 자리는 core/paths.py가 안다 (B78 1a)
# 픽스처 소재는 `core/state/fixtures.py`가 소유한다 — 코어 본체가 mock 경로를
# 무조건 상수로 알면 그 자산을 들어낼 때 코어가 죽는다(§2-4 격리).
from core.state import fixtures as _fx

HINTS_DIR = _fx.EXTRACT_HINTS

_LOG = log.get(__name__)

PROMPTS_DIR = ROOT / "prompts"


def prompt_version(name="extract"):
    """지시문 템플릿의 판본 — **파일에서 읽는다**(문서 7 §7.6-B-5).

    코드에 버전 문자열을 박아 두면 템플릿이 개정돼도 체크포인트에는 옛 번호가
    남고, 템플릿이 아예 없어도 있는 것처럼 기록된다 — **실체 없는 버전이 재현성
    기록에 남는 것**이 그 결함이다. 그래서 정본은 파일 머리말의 `version:`이다.

    파일이 없으면 **명시적 실패**다(§7.6-B-4) — 재현성 기록의 근거가 없는데 조용히
    기본값을 적으면 그 체크포인트로는 추출을 재현할 수 없다.
    """
    # **파일을 찾는 자리는 게이트웨이 하나다**(B63 ① — 칸 ID가 파일 이름에 붙었고,
    # 여기에 두 번째 해석기를 두면 한쪽만 고쳐지는 날 이 함수가 조용히 죽는다).
    p = gateway.prompt_path(name)
    if not p:
        log.explicit_fail(_LOG, "core.extract.prompt_version",
                          f"지시문 템플릿이 없다: {PROMPTS_DIR}/<칸ID>_{name}.md — "
                          "prompt_version의 정본은 파일이다(문서 7 §7.6-B-5)")
        raise FileNotFoundError(f"지시문 템플릿 없음: <칸ID>_{name}.md")
    p = Path(p)
    for line in p.read_text(encoding="utf-8").splitlines()[:10]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    log.explicit_fail(_LOG, "core.extract.prompt_version",
                      f"{p} 머리말에 version: 줄이 없다")
    raise ValueError(f"{p}: 머리말 version: 줄이 없다")


def checkpoint_path(doc_id, lens=None):
    """체크포인트 자리 — **렌즈가 키에 든다**(B91 ① — 같은 청크 · 다른 렌즈 = 다른 체크포인트).
    렌즈를 주지 않으면(한 층 — 기본) 지금 자리 그대로다."""
    return EXTRACT_DIR / (f"{doc_id}@{lens}.json" if lens else f"{doc_id}.json")


def has_checkpoint(doc_id, lens=None):
    return checkpoint_path(doc_id, lens).exists()


def reuse_check(env, lens=None):
    """이 체크포인트를 **재사용해도 되는가** — 돌려주는 둘째 값이 「왜 못 쓰는가」다.

    조건은 **`doc_hash`와 `adapter_version`이 둘 다 같을 때**다(B78 1b). 구판의
    조건은 「파일이 있다」 하나였고, 그래서 어댑터 새 판(`register generate --revise`)
    뒤에도 옛 추출이 그대로 재사용됐다 — **바뀐 분할로 만든 청크에 옛 판의 후보가
    붙는다.** 규약 7이 재인입에서 막던 것과 같은 축인데 어댑터 축이 비어 있었다.
    """
    p = checkpoint_path(env["doc_id"], lens)
    if not p.exists():
        return False, "체크포인트 없음"
    try:
        cp = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        return False, f"체크포인트를 읽지 못했다 — {type(e).__name__}"
    now = {"doc_hash": doc_hash(env), "adapter_version": env.get("adapter_version")}
    for k, v in now.items():
        if (cp.get(k) or None) != (v or None):
            return False, (f"{k} 불일치 — 체크포인트 {str(cp.get(k))[:12] or '없음'} "
                           f"≠ 지금 문서 {str(v)[:12] or '없음'}")
    return True, ""


def invalidate(doc_id, lens=None):
    """재인입 — 청크가 바뀌었으므로 체크포인트를 버린다 (규약 7). 렌즈를 안 주면 렌즈 판도 전부.
    부분 파일(B97 ③)도 같이 버린다 — 바뀐 청크에 옛 청크의 후보를 이어 붙이지 않는다."""
    for p in (checkpoint_path(doc_id, lens), partial_path(doc_id, lens)):
        if p.exists():
            p.unlink()
    if lens is None and EXTRACT_DIR.exists():
        for pat in (f"{doc_id}@*.json", f"{doc_id}@*.partial.jsonl"):
            for q in EXTRACT_DIR.glob(pat):
                q.unlink()


# ---------------------------------------------------------------- 이어 쓰기 (B97 ③)
def partial_path(doc_id, lens=None):
    """이어 쓰기 **부분 파일** — 최종 체크포인트와 **다른 이름**이다(「파일 존재 = 추출 완료」 불변).

    확장자가 `.jsonl`이라 체크포인트를 찾는 glob(`*@*.json` · `<doc>@*.json`)에 걸리지 않는다.
    첫 줄은 재사용 조건(문서 해시 · 어댑터 판 · 렌즈), 다음 줄부터 끝난 청크 하나씩이다.
    """
    return EXTRACT_DIR / (f"{doc_id}@{lens}.partial.jsonl" if lens
                          else f"{doc_id}.partial.jsonl")


def _partial_key(env, lens):
    return {"doc_hash": doc_hash(env), "adapter_version": env.get("adapter_version"),
            "lens": lens}


def _partial_load(env, lens):
    """끝난 청크 `{chunk_id: 후보}` — 조건이 다르면 **버리고** 로그 한 줄(빈 dict).

    줄 단위 덧붙임이라 쓰다 끊긴 마지막 줄은 읽지 못한다 — 그 청크는 다시 부른다
    (반쯤 쓰인 후보를 쓰지 않는다 · 원자 단위가 줄이다).
    """
    p = partial_path(env["doc_id"], lens)
    if not p.exists():
        return {}
    lines = p.read_text(encoding="utf-8").splitlines()
    try:
        head = json.loads(lines[0]) if lines else None
    except ValueError:
        head = None
    if head != _partial_key(env, lens):
        _LOG.info("extract: %s 부분 파일 폐기 — 재사용 조건(문서 해시·어댑터 판·렌즈) 불일치",
                  env["doc_id"])
        p.unlink()
        return {}
    done = {}
    for ln in lines[1:]:
        try:
            e = json.loads(ln)
        except ValueError:
            break
        done[e["chunk_id"]] = e
    return done


def _partial_append(env, lens, entry):
    """끝난 청크 하나를 줄로 덧붙인다 — flush + fsync(끊겨도 앞 줄은 남는다)."""
    p = paths.ensure(partial_path(env["doc_id"], lens))
    head = "" if p.exists() else json.dumps(_partial_key(env, lens), ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(head + json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# ---------------------------------------------------------------- USE_MOCK
# 증분0 §5-1: 힌트 파일이 있으면 그 내용을 후보로 반환(결정적 — 게이트·구축 검증용).
# 없으면 문형 규칙 폴백. mock 텍스트는 이 규칙이 잡는 통제 문형으로 창작한다(D-10).
#
# **규칙 표는 층 config가 소유한다** — 관계 이름(`causes`·`affects`)은 층 어휘이고
# 코드에 있으면 그 자체가 B1 위반이다(예외 3호가 그것이었다). 카드가 적어 둔 해소
# 경로가 "문형 규칙의 config 이동"이고 여기가 그 자리다(n7 — parser 정비의 첫 자리).
# 코드가 아는 것은 **정규식이 구문이라는 것**뿐이고 무엇을 뜻하는지는 데이터가 말한다.


def _patterns(cfg):
    return [(re.compile(p["pattern"]), p["rel"])
            for p in (cfg.get("extract_patterns") or [])]


# 지점 ① 비정형 추출 — `if USE_MOCK: <mock> else: <실호출>` (문서 7 §7.6-B-3).
# **두 갈래가 같은 반환 계약을 지킨다** — {chunk_id, entities, relations, attach}.
# 소비부(구축)는 어느 쪽인지 몰라야 하고, 그래야 mock 회귀가 실 연결에도 유효하다.
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        # **개체별 부모**(B91 ③) — 골격 canonical을 부모 후보(`parent_candidates`) **안에서만**
        # 고른다 · 못 고르면 null(주 좌표가 부모다). 계약상 선택 필드다 — 옛 체크포인트·mock은
        # 키가 없고 「없음」으로 읽는다(strict 스키마라 모델에게는 null 허용 필수 키다).
        "entities": {"type": "array", "items": {
            "type": "object",
            "properties": {"surface": {"type": "string"},
                           "category": {"type": "string"},
                           "parent": {"type": ["string", "null"]}},
            "required": ["surface", "category", "parent"], "additionalProperties": False}},
        "relations": {"type": "array", "items": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "rel": {"type": "string"},
                           "dst": {"type": "string"}},
            "required": ["src", "rel", "dst"], "additionalProperties": False}},
        # **`attach_to`는 이름과 카테고리를 함께 낸다**(문서 4 §4.10 규약 8 — B11).
        # 판정기 계약(§4.3)이 `category`를 필수로 받는데 비정형에서 뽑은 이름에는
        # 카테고리가 없어, 없이 두면 **후보 검색이 전 카테고리를 훑고 선언 순서가
        # 답을 정한다**(2A P-B 실측: `정밀 노칭 프레스`가 Process·Unit 양쪽에 0.95).
        # 카테고리는 층 어휘의 닫힌 목록에서만 고르고, **고르지 못하면 null**로 내어
        # 규칙 B 폴백으로 보낸다 — 추측해서 채우지 않는다.
        "attach": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "surface": {"type": "string"},
                "attach_to": {
                    "type": ["object", "null"],
                    "properties": {"name": {"type": "string"},
                                   "category": {"type": ["string", "null"]}},
                    "required": ["name", "category"], "additionalProperties": False},
            },
            "required": ["surface", "attach_to"], "additionalProperties": False}},
        # **관련 링크**(B91 ③) — 이 청크가 「무엇에 관한 글인가」(표면형 + 카테고리 · 0~N ·
        # 층 카테고리 안). 조회 전용이다 — 구축이 사전·이 문서의 해소 결과로 찾고 노드를
        # 만들지 않는다(못 찾으면 버리고 기록). 선택 필드 — 없으면 「없음」.
        "about": {"type": "array", "items": {
            "type": "object",
            "properties": {"surface": {"type": "string"}, "category": {"type": "string"}},
            "required": ["surface", "category"], "additionalProperties": False}},
    },
    "required": ["entities", "relations", "attach", "about"], "additionalProperties": False,
}


def attach_candidates(process_ref, layer=None):
    """프롬프트에 삽입할 **부착 후보 목록** (문서 4 §4.10).

    무엇을 넣나 — 그 청크의 `process_ref`가 가리키는 **골격 노드와 그 하위
    part_of 골격 노드(세부공정)의 canonical**. **좌표가 null이면 세부공정 목록만**
    넣는다.

    **설비는 골격에 없으므로 후보 목록에 오르지 않는다** — 산문에서 발견된 설비의
    표기 통일은 §4.10 규약 8의 「목록에 없으면 본문의 이름 그대로(발견 보존)」
    갈래가 맡고, 재해소는 orphan_attach 재시도 배치(§4.7-5)가 한다. 설비를 후보로
    적으면 읽기 원천(seed)에 그것이 없어 구현이 사전·그래프 폴백으로 샌다.

    **읽기 원천은 골격 스냅샷(`status="seed"` 노드)뿐이다 — 현재 사전도 현재
    그래프도 읽지 않는다.** 그것을 읽으면 그 시점까지의 인입 상태에 의존해 문서
    순서가 바뀔 때 추출 경계가 달라지고 체크포인트가 그 우연을 고정한다(실측:
    정순 66 · 역순 65 노드로 갈렸다). 멱등성(§4.8-6)의 전제다.
    **층은 좌표 층이다**(B85 ② — 문서의 층이 아니다): `process_ref`가 가리키는 것은
    좌표 층의 골격이라, 품질층 doc_type이 제 층의 스냅샷을 읽으면 후보가 빈다.
    """
    from core.state.bootstrap import coord_layer     # 좌표 층을 묻는 자리는 하나다
    snap = (store.read(store.SKELETON_LIST, {}).get(layer or coord_layer()) or {})
    nodes = snap.get("nodes") or []
    if not process_ref:
        # 좌표 null — **세부공정 목록만**. tier는 스냅샷이 이미 싣고 있다.
        return sorted({n["canonical"] for n in nodes if n.get("tier") == "sub"})
    key = norm(process_ref)
    ref = next((n for n in nodes
                if norm(n["canonical"]) == key or key in
                {norm(a) for a in (n.get("aliases") or [])}), None)
    if ref is None:
        # 2차 — 라틴 대소문자 무시 · 대상이 하나일 때만 (B96 ④)
        fk = fold_latin(process_ref)
        hits = [n for n in nodes
                if fk in {fold_latin(x) for x in [n["canonical"], *(n.get("aliases") or [])]}]
        ref = hits[0] if len(hits) == 1 else None
    if ref is None:
        return sorted({n["canonical"] for n in nodes if n.get("tier") == "sub"})
    out = {ref["canonical"]}
    # 하위 part_of 골격 노드 — 스냅샷의 `parent` 링크로 훑는다(그래프를 읽지 않는다).
    frontier = {ref["canonical"]}
    while frontier:
        nxt = {n["canonical"] for n in nodes if n.get("parent") in frontier}
        nxt -= out
        out |= nxt
        frontier = nxt
    return sorted(out)


def parent_candidates(chunk, layer=None):
    """**부모 후보** — 좌표 서브트리(`attach_candidates`) + **청크 본문에 나오는 골격 이름**
    (canonical·별칭의 사전 스캔 — 결정적 · 전 골격을 넣지 않는다 · B91 ③).

    읽기 원천은 부착 후보와 같은 골격 스냅샷이다(멱등 — 인입 순서에 흔들리지 않는다).
    구축(`prose`)이 같은 함수로 다시 계산해 추출이 고른 부모가 이 안인지 본다.
    """
    from core.state.bootstrap import coord_layer
    out = set(attach_candidates(chunk.get("process_ref"), layer))
    snap = (store.read(store.SKELETON_LIST, {}).get(layer or coord_layer()) or {})
    text = norm(chunk.get("text", ""))
    low = fold_latin(text)                           # 2차 — 라틴 대소문자 무시 (B96 ④)
    for n in snap.get("nodes") or []:
        names = [n["canonical"], *(n.get("aliases") or [])]
        if any(len(norm(x)) >= 2 and (norm(x) in text or fold_latin(x) in low)
               for x in names if x):
            out.add(n["canonical"])
    return sorted(out)


def _optional(out):
    """새 선택 필드(`parent`·`about`)는 **값이 있을 때만** 싣는다 — 비면 체크포인트가 지금과 같다."""
    ents = [{k: v for k, v in e.items() if not (k == "parent" and v is None)}
            for e in out.get("entities", [])]
    extra = {"about": out["about"]} if out.get("about") else {}
    return ents, extra


def _candidates_for(chunk_id, chunk, cfg, vocab):
    """추출 후보 1청크 — mock/실호출 분기의 **단일 지점**이다.

    후보는 **표면형만** 낸다(문서 4 §4.10-1) — 노드 id가 들어가면 추출이 그래프
    상태에 의존해 체크포인트의 독립성이 깨진다. `confidence`·`span`도 두지 않는다.
    """
    if gateway.use_mock():
        gateway.mock("extract", f"문형 규칙 · {chunk_id}")
        return _mock_candidates(chunk_id, chunk.get("text", ""), cfg, vocab)

    # 실호출 — 지시문 템플릿(파일) + 층 어휘(config) + **부착 후보 목록**을 실행 시
    # 조립한다(문서 4 §4.10). 세 자산은 **각자 제자리에서 각자 버전을 갖는다**(B9).
    tmpl = gateway.prompt("extract")
    out = gateway.chat(
        [{"role": "system", "content": tmpl},
         {"role": "user", "content": json.dumps(
             {"categories": categories_with_also(cfg),
              "relations": cfg.get("relations"),
              # 층을 넘기지 않는다 — 후보는 **좌표 층**의 골격에서 온다(B85 ②).
              "attach_candidates": attach_candidates(chunk.get("process_ref")),
              "parent_candidates": parent_candidates(chunk),
              "chunk": _with_path(chunk)}, ensure_ascii=False)}],
        json_schema=EXTRACT_SCHEMA, point="extract")
    ents, extra = _optional(out)
    return {"chunk_id": chunk_id,
            "entities": ents,
            "relations": out.get("relations", []),
            "attach": out.get("attach", []), **extra}


def categories_with_also(cfg):
    """층 카테고리 어휘 + **겸 한 줄**(B90 ③) — 문안은 공통 config `also`에서 렌더한다.

    템플릿에는 층 어휘를 적지 않는다(B9) — 겸도 층 사이의 데이터라 여기서 정의문 끝에
    붙인다. 겸이 없으면 층 config 값 그대로다.
    """
    from core.state import catalog
    cats = dict(cfg.get("categories") or {})
    try:
        lines = catalog.also_lines()
    except catalog.CatalogError:
        return cats
    for c, line in lines.items():
        if c in cats:
            cats[c] = f"{cats[c]} {line}"
    return cats


def _with_path(chunk):
    """청크 텍스트 앞에 `section_path` 한 줄 — **문서 안 어디인가**를 준다(B53).

    prose 청크는 슬라이드 한 장 분량이라 그 자체로는 「무엇에 대한 글인가」가
    자주 빠진다(「20±2㎛로 관리한다」가 어느 공정인지 본문에 없다). 경로는
    **앞뒤 슬라이드 본문을 넣지 않고** 그 자리를 메우는 값싼 맥락이다 —
    본문을 넣으면 비용이 3배가 되고 잡음이 함께 들어온다(문서 6 §6.4-5).
    """
    text = chunk.get("text", "")
    path = (chunk.get("meta") or {}).get("section_path")
    return f"[{path}]\n{text}" if path else text


def _mock_candidates(chunk_id, text, cfg, vocab):
    """문형 규칙 폴백. 카테고리는 config 정의문 예시·사전 매칭으로 정한다.

    **USE_MOCK 한정이다.** 경계가 코드에 없어 실LLM 경로에서도 이 규칙이 돌았다
    (G6.5 E3이 이 게이트를 세웠다). 실물 경로는 미구현이므로 **명시적으로 실패**한다.
    """
    if not gateway.use_mock():
        raise NotImplementedError(
            "문형 폴백은 USE_MOCK 한정이다 — 실호출 갈래는 `_candidates_for`가 "
            "`core.llm`을 부른다. 이 함수가 USE_MOCK=0에서 불렸다면 분기를 "
            "우회한 호출부가 있다는 뜻이다")
    entities, relations = [], []

    def cat_of(surface):
        return vocab.get(norm(surface))

    for pat, rel in _patterns(cfg):
        m = pat.search(text)
        if not m:
            continue
        src, dst = norm(m.group(1)), norm(m.group(2))
        for s in (src, dst):
            c = cat_of(s)
            if c and not any(e["surface"] == s for e in entities):
                entities.append({"surface": s, "category": c})
        relations.append({"src": src, "rel": rel, "dst": dst})
        break                                    # 청크당 한 관계 — 과추출 금지(3.1 규약 3)

    for surface, c in vocab.items():             # 주제 언급 — 사전에 있는 표면형만
        if surface and surface in norm(text):
            if not any(e["surface"] == surface for e in entities):
                entities.append({"surface": surface, "category": c})
    return {"chunk_id": chunk_id, "entities": entities,
            "relations": relations, "attach": []}


def _load_hints(doc_id):
    """추출 힌트 — **mock 자산이다**(문서 7 §7.5 대체 표 「추출」 행 · B71 ①).

    `USE_MOCK=0`이면 파일이 있어도 읽지 않는다. 구판은 모드와 무관하게 먼저 봐서,
    사내 `doc_id`가 픽스처 이름(`PPT02`·`QPPT01`)과 겹치는 날 **실호출 결과가
    조용히 mock 힌트로 바뀐다** — B70이 걷어낸 것과 같은 병이고, 조용한 쪽이
    더 나쁘다(틀린 답이 성공으로 보인다).
    """
    if not gateway.use_mock():
        return None
    p = HINTS_DIR / f"{doc_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _chunk_info(entry, i, m, locator, tokens, lens):
    """청크 하나의 화면 재료 — 개체는 **전부**(표기·카테고리) · 관계·부착·부모는 수 (B97 ②)."""
    ents = entry.get("entities") or []
    return {"단계": "추출청크", "렌즈": lens, "i": i, "m": m, "locator": locator,
            "개체": [(e.get("surface"), e.get("category")) for e in ents],
            "관계": len(entry.get("relations") or []), "부착": len(entry.get("attach") or []),
            "부모": sum(1 for e in ents if e.get("parent")), "토큰": tokens,
            "실패": entry.get("failed")}


def _call_chunk(doc_id, cid, c, cfg, vocab, hints):
    """청크 1개의 후보 — 실패는 청크 단위로 남긴다(문서 4 §4.10 규약 9)."""
    try:
        if hints and c.get("source_locator") in hints:
            h = hints[c["source_locator"]]
            ents, extra = _optional(h)
            return {"chunk_id": cid, "entities": ents, "relations": h.get("relations", []),
                    "attach": h.get("attach", []), **extra}
        return _candidates_for(cid, c, cfg, vocab)
    except Exception as e:                              # noqa: BLE001
        # **무후보와 구분한다** — `entities: []`는 「봤는데 없었다」이고 `failed`는
        # 「보지 못했다」다. 둘을 같은 모양으로 두면 구축이 「후보 0건인 청크」로 세어
        # 결함이 통계에 녹는다.
        why = f"{type(e).__name__}: {e}"
        store.append_defect(f"{doc_id}: 추출 실패 {cid} — {why}")
        return {"chunk_id": cid, "failed": why, "entities": [], "relations": [], "attach": []}


def _todo(env, chunk_ids_by_locator, skip, done):
    """부를 청크와 건너뛸 청크를 **부르기 전에** 가른다 — 예고와 루프가 같은 표를 쓴다."""
    rows, ref, lens_sk, resumed = [], 0, 0, 0
    for c in env.get("chunks", []):
        cid = chunk_ids_by_locator.get(c.get("source_locator"))
        if cid is None:
            continue
        # **관련성 거름으로 건너뛴 청크**(B91 ① — 렌즈가 둘 이상일 때만 · LLM 0) — 이 렌즈에서
        # 무후보다. 건너뛴 수는 체크포인트에 남는다(렌즈별 호출 분포의 재료).
        if cid in skip:
            lens_sk += 1
            rows.append(("skip", cid, c))
        # **참조 시트의 청크는 부르지 않는다**(B83 ④) — 청크 자체는 남아 있다
        # (`chunks.json` · `linked=false` · 열람·bm25에는 보인다).
        elif (c.get("meta") or {}).get("sheet_role") == "ref":
            ref += 1
        elif cid in done:
            resumed += 1
            rows.append(("done", cid, c))
        else:
            rows.append(("call", cid, c))
    return rows, ref, lens_sk, resumed


_STOP_NAME = {"추출예고": "추출 예고", "추출이어서": "추출 이어서"}


def _say(notice, info):
    """화면 콜백 — **`False`를 돌려받으면 사람이 멈춘 것**이다(`--step` · 그래프 쓰기 0)."""
    if notice is not None and notice(info) is False:
        from core.build.entry import StepStop
        raise StepStop(f"사람이 멈췄다 — {_STOP_NAME.get(info['단계'], info['단계'])}까지 "
                       f"(LLM 0 · 그래프 쓰기 0)")


def extract(env, cfg, chunk_ids_by_locator, vocab, *, lens=None, skip=(), notice=None):
    """계약 JSON(prose) → extract/{doc_id}.json. 이미 있으면 만들지 않는다.

    **실패의 처분은 청크 단위다**(문서 4 §4.10 규약 9) — 실패한 청크는 `failed`로 체크포인트에
    남기고 처분 급은 결함 로그다(새 큐 kind 0). **전 청크가 실패하면 체크포인트를 쓰지
    않는다** — 「파일 존재 = 추출 완료」(P-1)라 아무것도 못 뽑은 상태를 완료로 남기면
    재시도가 영영 막힌다.

    **보이게 한다**(B97): 부르기 전에 예고(`추출예고` — 청크 · ref · 이어서 제외 → LLM ≤ m) ·
    청크마다 메타(`추출청크`) · 끝(`추출끝`)을 `notice`로 낸다 — 화면은 진입점이 그린다.
    **청크 단위 이어 쓰기**(B97 ③): 끝난 청크는 부분 파일에 줄로 덧붙이고, 다시 돌면 조건이
    같을 때 끝난 청크를 부르지 않는다 · 다 끝나면 체크포인트로 올리고 부분 파일을 지운다.
    """
    doc_id = env["doc_id"]
    ok, why = reuse_check(env, lens)             # doc_hash + adapter_version (B78 1b)
    if ok:
        _say(notice, {"단계": "추출재사용", "렌즈": lens})
        return json.loads(checkpoint_path(doc_id, lens).read_text(encoding="utf-8")), False
    if has_checkpoint(doc_id, lens):
        # **조용히 옛 판을 쓰지 않는다** — 조건이 깨졌으면 버리고 다시 뽑는다.
        _LOG.info("extract: %s 체크포인트 폐기 — %s", doc_id, why)
        checkpoint_path(doc_id, lens).unlink()

    hints = _load_hints(doc_id)
    done = _partial_load(env, lens)
    rows, ref_skipped, lens_skipped, resumed = _todo(env, chunk_ids_by_locator, skip, done)
    m = sum(1 for r in rows if r[0] == "call")
    if resumed:
        _say(notice, {"단계": "추출이어서", "렌즈": lens, "끝난": resumed, "남은": m})
    _say(notice, {"단계": "추출예고", "렌즈": lens, "청크": len(rows) + ref_skipped,
                  "ref": ref_skipped, "거름": lens_skipped, "재사용": resumed, "호출": m})
    u0 = gateway.usage_total()
    candidates, i = [], 0
    for kind, cid, c in rows:
        if kind == "skip":
            candidates.append({"chunk_id": cid, "entities": [], "relations": [], "attach": [],
                               "lens_skipped": True})
            continue
        if kind == "done":
            candidates.append(done[cid])
            continue
        i += 1
        t0 = gateway.usage_total().get("total_tokens", 0)
        entry = _call_chunk(doc_id, cid, c, cfg, vocab, hints)
        candidates.append(entry)
        _partial_append(env, lens, entry)
        # 관계 쌍은 화면이 아니라 명령 로그로 간다(수만 화면에)
        _LOG.info("추출 %s %s · 관계 %s", doc_id, c.get("source_locator"),
                  [(r.get("src"), r.get("rel"), r.get("dst")) for r in entry.get("relations") or []])
        _say(notice, _chunk_info(entry, i, m, c.get("source_locator"),
                                 gateway.usage_total().get("total_tokens", 0) - t0, lens))
    called = [x for x in candidates if not x.get("lens_skipped")]
    failed = sum(1 for x in called if x.get("failed"))
    _say(notice, {"단계": "추출끝", "렌즈": lens, "청크": len(called), "실패": failed,
                  "개체": sum(len(x.get("entities") or []) for x in called),
                  "관계": sum(len(x.get("relations") or []) for x in called), "since": u0})

    # **전건 실패면 체크포인트도 부분 파일도 남기지 않는다** — 「파일 존재 = 추출 완료」(P-1)
    # · 실패만 든 부분 파일을 이어 쓰면 재시도가 영영 막힌다.
    if candidates and failed == len(candidates):
        store.append_defect(
            f"{doc_id}: 전 청크 추출 실패 {failed}건 — 체크포인트를 쓰지 않는다")
        partial_path(doc_id, lens).unlink(missing_ok=True)
        return {"doc_id": doc_id, "stage": "extract", "candidates": candidates,
                "all_failed": True}, False
    out = _write_checkpoint(env, cfg, lens, candidates, ref_skipped, lens_skipped)
    partial_path(doc_id, lens).unlink(missing_ok=True)       # 올린 뒤에 지운다 — 순서가 계약이다
    return out, True


def _write_checkpoint(env, cfg, lens, candidates, ref_skipped, lens_skipped):
    """최종 체크포인트 — 이 파일이 생기면 추출 완료다(부분 파일은 그 뒤에 지운다)."""
    out = {
        "doc_id": env["doc_id"],
        "stage": "extract",
        "adapter_version": env.get("adapter_version"),
        # **재사용 조건의 둘째 축**(B78 1b) — 봉투가 바뀌면 청크가 바뀐다.
        "doc_hash": doc_hash(env),
        "prompt_version": prompt_version(),
        "config_version": cfg.get("config_version") or cfg.get("skeleton_version"),
        "layer": cfg["layer"],
        "extracted_at": env.get("parsed_at"),
        "candidates": candidates,
    }
    if ref_skipped:
        # 키는 **있을 때만** 단다 — 역할 없는 문서의 체크포인트가 바이트로 갈리지 않는다.
        out["ref_skipped"] = ref_skipped
    if lens:
        out["lens"] = lens                                   # 렌즈 판 (B91 ①)
        out["lens_skipped"] = lens_skipped
    paths.ensure(EXTRACT_DIR)          # 폴더를 만드는 자리는 하나다 (B78 1a)
    checkpoint_path(env["doc_id"], lens).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
