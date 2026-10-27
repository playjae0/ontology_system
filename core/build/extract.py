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

from parser.normalizer import coord_text
from core import paths
from core.llm import gateway
from core.state import log, store
from core.state.ids import doc_hash, fold_latin, norm
from core.build import extract_ctx

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


def _now_key(env, cfg=None, outline=None):
    """재사용 조건의 지금 값 — **문서 해시 · 어댑터 판 · 지시문 판 · 층 config 판**(B102 ⑥) + **개요의 대상
    제목**(B115 ③ — 추출 입력의 넷째 소속 출처라 바뀌면 다시 뽑는다 · 대상이 없으면 None이라 옛 체크포인트와 같다).
    층 config 판은 **추출 갈래 칸의 해시**다(B120 ③ — `config_scope.extract_key` · 사람이 적는 `config_version`은 기록만).
    `cfg`가 없으면(층을 모르는 호출) 층 config 판은 대조하지 않는다."""
    from core.build import outline as OL
    from core.state import config_scope
    now = {"doc_hash": doc_hash(env), "adapter_version": env.get("adapter_version"),
           "prompt_version": prompt_version()}
    if cfg is not None:
        now["config_extract"] = config_scope.extract_key(cfg)
    now["outline"] = OL.targets_key(outline)
    return now


_LABEL = {"doc_hash": "문서", "adapter_version": "어댑터", "prompt_version": "지시문",
          "config_extract": "층 config(추출 칸)", "outline": "목차 노드화"}


def reuse_check(env, lens=None, cfg=None, outline=None, p=None):
    """이 체크포인트를 **재사용해도 되는가** — 돌려주는 둘째 값이 「왜 못 쓰는가」다.

    조건은 **문서 해시 · 어댑터 판 · 지시문 판 · 층 config 판이 모두 같을 때**다(B78 1b · B102 ⑥). 구판은
    앞의 둘만 대조하고 나머지는 기록만 했다 — 지시문이 바뀌어도 옛 추출을 썼다. 이유는 「지시문 e-1.3 →
    e-1.4」처럼 바뀐 축과 두 값을 말한다(예고 줄이 그대로 싣는다). `p`를 주면 그 파일(리허설 산출 · B116 ②)을 본다.
    """
    p = p or checkpoint_path(env["doc_id"], lens)
    if not p.exists():
        return False, "체크포인트 없음"
    try:
        cp = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        return False, f"체크포인트를 읽지 못했다 — {type(e).__name__}"
    for k, v in _now_key(env, cfg, outline).items():
        if (cp.get(k) or None) != (v or None):
            return False, (f"{_LABEL[k]} {str(cp.get(k))[:12] or '없음'} → {str(v)[:12] or '없음'}")
    return True, ""


def invalidate(doc_id, lens=None):
    """재인입 — 청크가 바뀌었으므로 체크포인트를 버린다 (규약 7). 렌즈를 안 주면 렌즈 판도 전부.
    **호출 보존(`extract_calls`)은 버리지 않는다** — 열쇠가 보낸 입력이라 바뀐 청크는 저절로 다시 부르고 그대로인 청크는 다시 쓴다
    (B135 ①) · B135 전의 부분 파일(`*.partial.jsonl`)은 읽는 곳이 없어 함께 지운다."""
    p = checkpoint_path(doc_id, lens)
    if p.exists():
        p.unlink()
    if EXTRACT_DIR.exists():
        pats = ([f"{doc_id}@*.json"] if lens is None else []) + [f"{doc_id}*.partial.jsonl"]
        for pat in pats:
            for q in EXTRACT_DIR.glob(pat):
                q.unlink()


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
        # **개체별 소속**(B102 ③) — 그 개체가 「무엇의 일부 · 무엇의 특성인가」. 이름은 부착 후보 ·
        # 청크 본문 · 맥락 줄(경로·시트·공정)에서만 고른다 · `from`이 그 출처 · 어디에도 없으면 null
        # (지어내지 않는다 — 구축이 출처를 다시 대조해 밖이면 버린다). 카테고리는 층 닫힌 목록(못 고르면
        # null). 옛 `attach`(관계를 못 고를 때의 부착 이름)는 이것으로 흡수됐다 — 옛 체크포인트의 `attach`는
        # 같은 뜻으로 읽는다(`core/build/belongs.belongs_of`).
        "entities": {"type": "array", "items": {
            "type": "object",
            "properties": {"surface": {"type": "string"},
                           "category": {"type": "string"},
                           "parent": {"type": ["string", "null"]},
                           # **값**(B120 ①) — 값을 받는 카테고리(`value_categories`)의 개체만 · 청크 원문 글자 그대로 ·
                           # 없으면 null(선택 필드 — 옛 체크포인트 · mock은 키가 없고 「없음」으로 읽는다)
                           "value": {"type": ["string", "null"]},
                           "belongs_to": {
                               "type": ["object", "null"],
                               "properties": {"name": {"type": "string"},
                                              "category": {"type": ["string", "null"]},
                                              "from": {"type": "string",
                                                       "enum": ["본문", "경로", "시트", "공정", "제목"]}},
                               "required": ["name", "category", "from"],
                               "additionalProperties": False}},
            "required": ["surface", "category", "parent", "belongs_to", "value"],
            "additionalProperties": False}},
        "relations": {"type": "array", "items": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "rel": {"type": "string"},
                           "dst": {"type": "string"}},
            "required": ["src", "rel", "dst"], "additionalProperties": False}},
        # **관련 링크**(B91 ③) — 이 청크가 「무엇에 관한 글인가」(표면형 + 카테고리 · 0~N ·
        # 층 카테고리 안). 조회 전용이다 — 구축이 사전·이 문서의 해소 결과로 찾고 노드를
        # 만들지 않는다(못 찾으면 버리고 기록). 선택 필드 — 없으면 「없음」.
        "about": {"type": "array", "items": {
            "type": "object",
            "properties": {"surface": {"type": "string"}, "category": {"type": "string"}},
            "required": ["surface", "category"], "additionalProperties": False}},
    },
    "required": ["entities", "relations", "about"], "additionalProperties": False,
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
    from parser.normalizer import coord_refs
    snap = (store.read(store.SKELETON_LIST, {}).get(layer or coord_layer()) or {})
    nodes = snap.get("nodes") or []
    refs = coord_refs(process_ref)
    if len(refs) > 1:
        # **공정 목록**(B125 ④) — 목록 공정들의 하위 트리 합 · 하나도 안 서면 세부공정 목록(하나일 때와 같다)
        got = [x for r in refs for x in _subtree(r, nodes)]
        return sorted(set(got)) if got else sorted({n["canonical"] for n in nodes if n.get("tier") == "sub"})
    if not refs:
        # 좌표 null — **세부공정 목록만**. tier는 스냅샷이 이미 싣고 있다.
        return sorted({n["canonical"] for n in nodes if n.get("tier") == "sub"})
    got = _subtree(refs[0], nodes)
    return got if got else sorted({n["canonical"] for n in nodes if n.get("tier") == "sub"})


def _subtree(process_ref, nodes):
    """공정 하나 → 그 골격 노드와 하위 part_of 골격 노드의 canonical(정렬) · 목록에 없으면 빈 목록."""
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
        return []
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
    """새 선택 필드(`parent`·`belongs_to`·`value`·`about`)는 **값이 있을 때만** 싣는다 — 비면 체크포인트가 지금과 같다."""
    ents = [{k: v for k, v in e.items()
             if not ((k in ("parent", "belongs_to") and v is None) or (k == "value" and v in (None, "")))}
            for e in out.get("entities", [])]
    extra = {"about": out["about"]} if out.get("about") else {}
    return ents, extra


#: 지금 추출하는 문서의 맥락 칸 재료(B102 ① — `extract()`가 문서마다 채운다 · 서명은 그대로)
_DOC = {}
#: 지금 추출하는 문서의 조각별 제목 개체(B115 ③ — `{위치: [{name, category}]}` · `extract()`가 개요에서 채운다)
_HEADS = {}
#: 위치 → 구조 사슬(B119 ② — 그 조각 위의 제목 줄 위에서 아래로 · 역할 · 대상)
_CHAIN = {}


def _candidates_for(chunk_id, chunk, cfg, vocab, image=None):
    """추출 후보 1청크 — mock/실호출 분기의 **단일 지점**이다.

    후보는 **표면형만** 낸다(문서 4 §4.10-1) — 노드 id가 들어가면 추출이 그래프
    상태에 의존해 체크포인트의 독립성이 깨진다. `confidence`·`span`도 두지 않는다.
    """
    if gateway.use_mock():
        gateway.mock("extract", f"문형 규칙 · {chunk_id}")
        return _mock_candidates(chunk_id, chunk.get("text", ""), cfg, vocab)

    # 실호출 — 지시문 템플릿(파일) + 층 어휘(config) + **부착 후보 목록**을 실행 시
    # 조립한다(문서 4 §4.10). 세 자산은 **각자 제자리에서 각자 버전을 갖는다**(B9).
    tmpl = gateway.prompt_for("extract", {cfg.get("layer") or "-": cfg}, "extract")   # 층 힌트 한 함수 (B124 ③)
    user = _payload(chunk, cfg)
    # **캡처**(B125 ② — 그 슬라이드 · 쪽의 렌더 · 있을 때만): 배치 · 화살표 · 붙음을 보는 근거 — 이름과 값은 글자에서
    from core.state.captures import mime
    content = [{"type": "text", "text": user}, gateway._image_part(image, mime(image))] if image else user   # 보관분은 JPEG (B156 ⑤)
    try:
        out = gateway.chat([{"role": "system", "content": tmpl}, {"role": "user", "content": content}],
                           json_schema=EXTRACT_SCHEMA, point="extract")
    except gateway.GatewayError as e:
        if image and getattr(e, "status", None) == 400:
            raise RuntimeError("추출: 게이트웨이가 캡처(이미지 입력)를 받지 않는다 — 그림 없이 넣으려면 "
                               "`--no-images`(캡처도 끈다 · 인입 기록에 남는다)") from e
        raise
    ents, extra = _optional(out)
    return {"chunk_id": chunk_id,
            "entities": ents,
            "relations": out.get("relations", []),
            "attach": [], **extra}                  # 소속은 개체의 `belongs_to`가 말한다(B102 ③)


def _payload(chunk, cfg):
    """실호출 사용자 글 — **조립은 여기 하나**(호출 보존의 열쇠가 같은 글을 해시한다 · B135 ①)."""
    return json.dumps(
             {"categories": categories_with_also(cfg),
              "relations": cfg.get("relations"),
              # **값을 받는 카테고리**(B120 ② — 층 config 선언 · 없으면 빈 목록 = 값 0)
              "value_categories": sorted((cfg.get("value_categories") or {}).keys())
              if isinstance(cfg.get("value_categories"), dict) else [],
              # 층을 넘기지 않는다 — 후보는 **좌표 층**의 골격에서 온다(B85 ②).
              "attach_candidates": attach_candidates(chunk.get("process_ref")),
              "parent_candidates": parent_candidates(chunk),
              # **넷째 소속 출처**(B115 ③) — 이 청크 위의 제목 개체(개요가 대상으로 정한 제목 · 가까운 것부터)
              "heading_candidates": _HEADS.get(chunk.get("source_locator")) or [],
              # **구조 사슬**(B119 ②) — 이 청크 위의 제목 줄(역할 · 글자 · 대상) 위에서 아래로 · 가장 구체적인 주인을 고르는 재료
              "structure_chain": _CHAIN.get(chunk.get("source_locator")) or [],
              # 청크 머리는 **맥락 줄 하나**(B102 ① — 문서 · 공정 · 시트 · 경로 · 포맷 전부 한 함수)
              "chunk": extract_ctx.with_context(chunk, _DOC)}, ensure_ascii=False)


# ---------------------------------------------------------------- 호출 보존 (B135 ① — 실호출만 · `extract_calls`)
#: 지금 추출하는 문서의 호출 보존 재료 `{doc, lens, used, base}` — `extract()`가 채운다(mock이면 비어 있다)
_CALLS = {}


def _calls_begin(doc_id, lens, cfg):
    """호출 보존의 문서 재료 — 열쇠의 고정 몫(지시문 이름 · 판 · 모델 · 온도 · 층 힌트 · 답 꼴)을 한 번 센다 · mock이면 비운다."""
    import hashlib
    _CALLS.clear()
    if gateway.use_mock():
        return
    g = gateway.config()
    hints = gateway.prompt_for("extract", {cfg.get("layer") or "-": cfg}, "extract")[len(gateway.prompt("extract")):]
    _CALLS.update({"doc": doc_id, "lens": lens, "used": set(), "stamp": gateway.prompt_stamp("extract"),
                   "base": {"prompt": "extract", "version": prompt_version(), "model": g.get("model"),
                            "temperature": gateway.temperature_line(g), "layer_hints": hints,
                            "schema": hashlib.sha256(json.dumps(EXTRACT_SCHEMA, sort_keys=True).encode()).hexdigest()[:16]}})


def _call_key(chunk, cfg, image=None):
    """그 호출의 열쇠 — 실제로 보낼 사용자 글 · 그림 해시 + 고정 몫 · mock이면 None."""
    if not _CALLS:
        return None
    import hashlib
    from core.build import extract_calls as EC
    return EC.key({**_CALLS["base"], "user": _payload(chunk, cfg),
                   "image": hashlib.sha256(image).hexdigest()[:16] if image else None})


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


def _chunk_info(entry, i, m, locator, label, tokens, lens, place=None):
    """청크 하나의 화면 재료 — 개체는 **전부**(표기·카테고리) · 관계·부착·부모는 수 (B97 ②).

    `tokens`는 이 청크의 사용량 차이(`prompt_tokens`·`completion_tokens`·`total_tokens` — B98 ③)."""
    ents = entry.get("entities") or []
    return {"단계": "추출청크", "렌즈": lens, "i": i, "m": m, "locator": locator, "라벨": label, "자리": place,
            "개체": [(e.get("surface"), e.get("category")) for e in ents],
            "관계": len(entry.get("relations") or []), "부착": len(entry.get("attach") or []),
            "부모": sum(1 for e in ents if e.get("parent")), "토큰": tokens,
            "실패": entry.get("failed")}


def _call_unit(doc_id, unit, cfg, vocab, hints, pages):
    """**추출 단위 하나**(B125 ① — 슬라이드 · 쪽 = 한 호출 · 그 밖은 청크 하나) — 근거 청크마다의 항목 목록.

    mock · 힌트는 청크마다 지금 그대로(한 호출로 센다) · 실호출은 묶음을 합친 한 청크 + 캡처(있으면)로 한 번 묻고 답을 근거
    청크로 나눈다(`extract_unit.split` — 개체는 그 글자가 든 청크 · 관계 · 관련 링크는 본문 청크)."""
    from core.build import extract_unit as EU
    img = (pages or {}).get(EU.page_of(unit))
    if gateway.use_mock() or hints or (len(unit) == 1 and img is None):
        return [_call_chunk(doc_id, cid, c, cfg, vocab, hints) for cid, c in unit]
    chunk, bid = EU.merged(unit)
    entry = _call_chunk(doc_id, bid, chunk, cfg, vocab, None, image=img)
    entry["capture"] = "page" if img is not None else "none"      # 그 호출이 캡처를 봤나 (B125 ② — slide_render)
    return EU.split(entry, unit, bid)


def _call_chunk(doc_id, cid, c, cfg, vocab, hints, image=None):
    """청크 1개의 후보 — 실패는 청크 단위로 남긴다(문서 4 §4.10 규약 9)."""
    try:
        if hints and c.get("source_locator") in hints:
            h = hints[c["source_locator"]]
            ents, extra = _optional(h)
            return {"chunk_id": cid, "entities": ents, "relations": h.get("relations", []),
                    "attach": h.get("attach", []), **extra}
        from core.build import extract_calls as EC
        k = _call_key(c, cfg, image)
        got = EC.get(_CALLS["doc"], _CALLS["lens"], k) if k else None
        if got is not None:                             # 같은 입력 — 그 답을 다시 쓴다(LLM 0 · B135 ①)
            _CALLS["used"].add(k)
            return {"chunk_id": cid, **got}
        # 캡처가 있을 때만 그림을 넘긴다 — 없으면 지금 서명 그대로(바꿔 끼운 대역 · 확장이 같은 손을 쓴다)
        res = _candidates_for(cid, c, cfg, vocab, image=image) if image is not None else _candidates_for(cid, c, cfg, vocab)
        if k:                                           # 끝난 호출은 바로 담는다 — 끊겨도 다음에 다시 부르지 않는다
            EC.put(_CALLS["doc"], _CALLS["lens"], k, {x: v for x, v in res.items() if x != "chunk_id"}, _CALLS["stamp"])
            _CALLS["used"].add(k)
        return res
    except Exception as e:                              # noqa: BLE001
        # **무후보와 구분한다** — `entities: []`는 「봤는데 없었다」이고 `failed`는
        # 「보지 못했다」다. 둘을 같은 모양으로 두면 구축이 「후보 0건인 청크」로 세어
        # 결함이 통계에 녹는다.
        why = f"{type(e).__name__}: {e}"
        store.append_defect(f"{doc_id}: 추출 실패 {cid} — {why}")
        return {"chunk_id": cid, "failed": why, "entities": [], "relations": [], "attach": []}


_TOC_STATE = {"call": "부름", "ref": "ref", "skip": "거름", "none": "개체 없음"}


def _toc(rows, env):
    """**청크 목차**(B112 ③) — 청크 전부 `[(번호, 라벨, 좌표, 상태, 글자 수)]` · 부르기 전에 예고가 싣는다."""
    coord = (env or {}).get("doc_coord")
    return [(n, extract_ctx.chunk_label(c), coord_text(c.get("process_ref")) or coord or "-", _TOC_STATE[k],
             len(c.get("text") or "")) for n, (k, _cid, c) in enumerate(rows, start=1)]


def _todo(env, chunk_ids_by_locator, skip):
    """부를 청크와 건너뛸 청크를 **부르기 전에** 가른다 — 예고와 루프가 같은 표를 쓴다(다시 쓸 호출은 단위가 가른다 — `_unit_hit`)."""
    rows, ref, lens_sk = [], 0, 0
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
            rows.append(("ref", cid, c))         # 목차에만 든다(B112 ③) — 부르지도 후보를 남기지도 않는다
        elif (c.get("meta") or {}).get("no_entities"):
            rows.append(("none", cid, c))        # 덱 구조가 「개체 없음」(표지 · 제목만)으로 표시 — 부르지 않는다 (B125 ①)
        else:
            rows.append(("call", cid, c))
    return rows, ref, lens_sk


def _unit_keys(unit, cfg, hints, pages):
    """그 단위의 호출 열쇠 — `_call_unit`과 같은 갈래(청크 하나 · 캡처 없음 = 청크의 열쇠 · 그 밖은 합친 청크 + 캡처) · mock · 힌트면 None."""
    from core.build import extract_unit as EU
    if not _CALLS or hints:
        return None
    img = (pages or {}).get(EU.page_of(unit))
    if len(unit) == 1 and img is None:
        return [_call_key(unit[0][1], cfg)]
    chunk, _bid = EU.merged(unit)
    return [_call_key(chunk, cfg, img)]


def _unit_hit(unit, cfg, hints, pages):
    """그 단위를 **다시 쓰는가**(보낼 입력이 같은 답이 남아 있다 — LLM 0 · B135 ①)."""
    from core.build import extract_calls as EC
    ks = _unit_keys(unit, cfg, hints, pages)
    return bool(ks) and all((EC.folder(_CALLS["doc"], _CALLS["lens"]) / f"{k}.json").exists() for k in ks)


def _seed(env, ck, cfg, chunk_ids_by_locator, skip):
    """**도입 씨앗**(B135 ②) — 문서 단위 체크포인트가 지금 조건과 같아 그대로 쓸 때, 그 청크 몫의 답을 지금 조립한 입력의 열쇠로 담는다
    (청크 하나 = 호출 하나 · 캡처 없음만 — 슬라이드 · 쪽 묶음 · 실패 · 거름 · 개체 없음은 담지 않는다) · 담은 수."""
    from core.build import extract_calls as EC
    from core.build import extract_unit as EU
    if not _CALLS:
        return 0
    rows, _r, _l = _todo(env, chunk_ids_by_locator, skip)
    by = {c.get("chunk_id"): c for c in ck.get("candidates") or []}
    n = 0
    for unit in EU.group(rows):
        if len(unit) != 1 or (env.get("capture") and EU.page_of(unit) is not None):
            continue
        cid, c = unit[0]
        cand = by.get(cid)
        if not cand or any(cand.get(x) for x in ("failed", "lens_skipped", "no_entities")) or "capture" in cand:
            continue
        k = _call_key(c, cfg)
        if not (EC.folder(_CALLS["doc"], _CALLS["lens"]) / f"{k}.json").exists():
            EC.put(_CALLS["doc"], _CALLS["lens"], k, {x: v for x, v in cand.items() if x != "chunk_id"}, _CALLS["stamp"])
            n += 1
    return n


_STOP_NAME = {"추출예고": "추출 예고", "개요예고": "개요 예고"}


#: 이 프로세스가 돈 추출의 사실 — `{(doc_id, 렌즈 또는 ""): {부름, 재사용}}` (B112 ① — 문서 끝 맞춤표의 청크 줄 ·
#: 체크포인트에는 싣지 않는다: 재사용 판정의 바이트가 그대로여야 한다)
RUN = {}


def _say(notice, info):
    """화면 콜백 — **`False`를 돌려받으면 사람이 멈춘 것**이다(`--step` · 그래프 쓰기 0)."""
    if notice is not None and notice(info) is False:
        from core.build.entry import StepStop
        raise StepStop(f"사람이 멈췄다 — {_STOP_NAME.get(info['단계'], info['단계'])}까지 "
                       f"(LLM 0 · 그래프 쓰기 0)")


def _context(env, outline):
    """추출 입력의 문서 칸 — 맥락 줄(B102 ①) · 개요의 제목 개체(B115 ③) · 구조 사슬(B119 ②) · 호출 보존의 열쇠가 같은 재료를 본다."""
    from core.build import outline as OL
    _DOC.clear()
    _DOC.update(extract_ctx.doc_info(env))
    _HEADS.clear()
    _HEADS.update({c.get("source_locator"): OL.heading_candidates(outline, c.get("source_locator"))
                   for c in env.get("chunks", [])})
    _CHAIN.clear()
    _CHAIN.update({c.get("source_locator"): OL.structure_chain(outline, c.get("source_locator"))
                   for c in env.get("chunks", [])})


def extract(env, cfg, chunk_ids_by_locator, vocab, *, lens=None, skip=(), notice=None, outline=None):
    """계약 JSON(prose) → extract/{doc_id}.json. 이미 있으면 만들지 않는다.

    **실패의 처분은 청크 단위다**(문서 4 §4.10 규약 9) — 실패한 청크는 `failed`로 체크포인트에
    남기고 처분 급은 결함 로그다(새 큐 kind 0). **전 청크가 실패하면 체크포인트를 쓰지
    않는다** — 「파일 존재 = 추출 완료」(P-1)라 아무것도 못 뽑은 상태를 완료로 남기면
    재시도가 영영 막힌다.

    **보이게 한다**(B97): 부르기 전에 예고(`추출예고` — 청크 · ref · 이어서 제외 → LLM ≤ m) ·
    청크마다 메타(`추출청크`) · 끝(`추출끝`)을 `notice`로 낸다 — 화면은 진입점이 그린다.
    **호출 단위 재사용**(B135 ① — 실호출): 호출마다 보낸 입력의 해시로 답을 담고(`extract_calls` — 끝난 호출은 바로) 다시 돌면
    입력이 같은 호출은 부르지 않고 그 답을 쓴다 — 청크 하나의 경로만 바뀌면 그 청크만 부른다 · 끊긴 뒤 다시 쳐도 끝난 호출은
    부르지 않는다(이어 쓰기를 흡수했다) · 문서 단위 체크포인트는 「추출 완료」 표시 · 구축이 읽는 후보 · 조건이 같으면 그대로 쓰는
    빠른 길(그때 씨앗을 담는다 — B135 ②)이다.
    """
    doc_id = env["doc_id"]
    _carry(env, lens, cfg, outline, notice)          # 그 종류 등록 검수의 리허설 산출 — 조건이 같으면 운영 자리로 (B116 ②)
    _context(env, outline)
    _calls_begin(doc_id, lens, cfg)                  # 호출 보존 — 실호출만 (B135 ①)
    ok, why = reuse_check(env, lens, cfg, outline)   # 문서 · 어댑터 · 지시문 · 층 config (B102 ⑥) · 개요 (B115 ③)
    if ok:
        ck = json.loads(checkpoint_path(doc_id, lens).read_text(encoding="utf-8"))
        gateway.prompt_drift("extract", ck)          # 판 그대로 · 문면만 바뀜 — 한 줄 (B135 ③)
        seeded = _seed(env, ck, cfg, chunk_ids_by_locator, skip)
        _say(notice, {"단계": "추출재사용", "렌즈": lens, "자리": checkpoint_path(doc_id, lens), "씨앗": seeded})
        RUN[(doc_id, lens or "")] = {"부름": 0, "재사용": sum(1 for c in ck.get("candidates") or []
                                                         if not c.get("lens_skipped"))}
        return ck, False
    if has_checkpoint(doc_id, lens):
        # **조용히 옛 판을 쓰지 않는다** — 조건이 깨졌으면 버리고 다시 뽑는다(같은 입력의 호출은 보존이 다시 쓴다 · B135 ①).
        _LOG.info("extract: %s 체크포인트 폐기 — %s", doc_id, why)
        checkpoint_path(doc_id, lens).unlink()

    hints = _load_hints(doc_id)
    rows, ref_skipped, lens_skipped = _todo(env, chunk_ids_by_locator, skip)
    from core.build import extract_unit as EU
    units = EU.group(rows)                              # 추출 단위 — 슬라이드 · 쪽은 한 호출 (B125 ①)
    pages, cap_why = EU.capture(env) if (units and not gateway.use_mock()) else ({}, None)
    cap = None
    if env.get("capture") and units and not gateway.use_mock():
        has = sum(1 for u in units if pages.get(EU.page_of(u)) is not None)
        cap = {"있음": has, "없음": len(units) - has, **({"사유": cap_why} if cap_why else {})}
    again = {n for n, u in enumerate(units) if _unit_hit(u, cfg, hints, pages)}     # 다시 쓸 단위 (B135 ①)
    first = {u[0][0]: (n, u) for n, u in enumerate(units)}
    m = len(units) - len(again)
    reused = sum(len(units[n]) for n in again)
    _say(notice, {"단계": "추출예고", "렌즈": lens, "청크": len(rows),
                  "다시": (why if why and why != "체크포인트 없음" else None),
                  "ref": ref_skipped, "거름": lens_skipped, "재사용": reused, "호출": m, "캡처": cap,
                  "개체없음": sum(1 for r in rows if r[0] == "none"),
                  "목차": _toc(rows, env), "자리목록": [extract_ctx.place(c) for _k, _cid, c in rows]})
    u0 = gateway.usage_total()
    candidates, i = [], 0
    for kind, cid, c in rows:
        if kind == "ref":
            continue
        if kind == "skip":
            candidates.append({"chunk_id": cid, "entities": [], "relations": [], "attach": [],
                               "lens_skipped": True})
            continue
        if kind == "none":                              # 개체 없음(덱 구조) — 부르지 않는다 · 체크포인트에는 남는다
            candidates.append({"chunk_id": cid, "entities": [], "relations": [], "attach": [], "no_entities": True})
            continue
        if cid not in first:
            continue                                    # 단위의 나머지 청크 — 첫 청크의 호출이 함께 받았다
        n, unit = first[cid]
        if n in again:                                  # 같은 입력 — 남은 답을 다시 쓴다(LLM 0 · 청크마다 줄 0)
            candidates += _call_unit(doc_id, unit, cfg, vocab, hints, pages)
            continue
        i += 1
        t0 = gateway.usage_total()
        entries = _call_unit(doc_id, unit, cfg, vocab, hints, pages)
        candidates += entries
        entry = {"entities": [e for en in entries for e in en.get("entities") or []],
                 "relations": [r for en in entries for r in en.get("relations") or []],
                 "attach": [a for en in entries for a in en.get("attach") or []],
                 "failed": next((en["failed"] for en in entries if en.get("failed")), None)}
        # 관계 쌍은 화면이 아니라 명령 로그로 간다(수만 화면에)
        _LOG.info("추출 %s %s · 관계 %s", doc_id, c.get("source_locator"),
                  [(r.get("src"), r.get("rel"), r.get("dst")) for r in entry.get("relations") or []])
        t1 = gateway.usage_total()
        _say(notice, _chunk_info(entry, i, m, c.get("source_locator"), extract_ctx.chunk_label(c),
                                 {k: t1.get(k, 0) - t0.get(k, 0) for k in
                                  ("prompt_tokens", "completion_tokens", "total_tokens")},
                                 lens, extract_ctx.place(c)))
    called = [x for x in candidates if not x.get("lens_skipped")]
    failed = sum(1 for x in called if x.get("failed"))
    RUN[(doc_id, lens or "")] = {"부름": i, "재사용": reused}
    _by = {cid: c for _k, cid, c in rows}
    _say(notice, {"단계": "추출끝", "렌즈": lens, "청크": len(called), "실패": failed,
                  "개체": sum(len(x.get("entities") or []) for x in called),
                  "관계": sum(len(x.get("relations") or []) for x in called), "since": u0,
                  # 개체 0 · 실패 청크 목록(B112 ③) — 라벨 + 앞부분
                  "개체0": [(extract_ctx.chunk_label(_by.get(x["chunk_id"]) or {}),
                             " ".join(str((_by.get(x["chunk_id"]) or {}).get("text") or "").split())[:40])
                            for x in called if not x.get("failed") and not x.get("entities")],
                  "실패목록": [(extract_ctx.chunk_label(_by.get(x["chunk_id"]) or {}), x["failed"])
                               for x in called if x.get("failed")]})

    # **전건 실패면 체크포인트를 남기지 않는다** — 「파일 존재 = 추출 완료」(P-1) · 실패한 호출은 보존에 없다(다시 부른다).
    if candidates and failed == len(candidates):
        store.append_defect(
            f"{doc_id}: 전 청크 추출 실패 {failed}건 — 체크포인트를 쓰지 않는다")
        _say(notice, {"단계": "추출저장", "렌즈": lens, "자리": checkpoint_path(doc_id, lens), "있음": False,
                      "전실패": True})
        return {"doc_id": doc_id, "stage": "extract", "candidates": candidates,
                "all_failed": True}, False
    out = _write_checkpoint(env, cfg, lens, candidates, ref_skipped, lens_skipped, outline)
    if _CALLS:                                               # 끝까지 돌았다 — 이 실행이 쓰지 않은 답을 지운다 (B135 ①)
        from core.build import extract_calls as EC
        EC.prune(doc_id, lens, _CALLS["used"])
    _say(notice, {"단계": "추출저장", "렌즈": lens, "자리": checkpoint_path(doc_id, lens),
                  "있음": saved(doc_id, lens)})
    return out, True


def _carry(env, lens, cfg, outline, notice):
    """리허설 산출의 추출 체크포인트(그 doc_type · 그 문서 · 그 렌즈)가 있으면 — **인입이 앞세운 회수 뒤**(재인입은
    문서 해시가 바뀌면 운영 체크포인트를 버린다 · `ingest.py`) 여기서 지금 조건과 대조해 옮기고, 다르면 쓰지 않고 지운다."""
    from core.state import rehearsal as RH
    dst = checkpoint_path(env["doc_id"], lens)
    src = RH.carried(env.get("doc_type"), env["doc_id"], RH.EXTRACT, dst.name)
    if src is None:
        return
    ok, why = reuse_check(env, lens, cfg, outline, src)
    RH.take(src, dst if ok else None)
    _say(notice, {"단계": "추출리허설", "렌즈": lens, "쓴다": ok, "이유": why, "자리": dst,
                  "종류": env.get("doc_type")})


def saved(doc_id, lens=None):
    """**추출이 끝난 뒤 체크포인트가 그 자리에 있나**(B112 ⑦) — 없으면 결함이다(로그 · 결함 장부에도).

    사내 실측(2026-10-15): 그래프는 다 섰는데 `work/extract/`가 없었다(원인 미상 — 쓰는 자리는 `_write_checkpoint`
    하나). 끝 줄이 자리와 있음/없음을 말하면 다음에 같은 일이 생긴 그 실행이 결함으로 남는다.
    """
    p = checkpoint_path(doc_id, lens)
    if p.exists():
        return True
    msg = f"{doc_id}: 추출이 끝났는데 체크포인트가 없다 — {paths.show(p)}"
    _LOG.error("[결함] %s", msg)
    store.append_defect(msg)
    return False


def checkpoint_files(doc_id):
    """그 문서의 추출 체크포인트 — 기본 + 렌즈판(호출 보존 `calls/`는 하위 폴더라 걸리지 않는다). 성공 줄이 자리를 말한다(B112 ⑦)."""
    if not EXTRACT_DIR.exists():
        return []
    return sorted(EXTRACT_DIR.glob(f"{doc_id}.json")) + sorted(EXTRACT_DIR.glob(f"{doc_id}@*.json"))


def _write_checkpoint(env, cfg, lens, candidates, ref_skipped, lens_skipped, outline=None):
    """최종 체크포인트 — 이 파일이 생기면 추출 완료다."""
    from core.build import outline as OL
    from core.state import config_scope
    out = {
        "doc_id": env["doc_id"],
        "stage": "extract",
        "adapter_version": env.get("adapter_version"),
        # **재사용 조건의 둘째 축**(B78 1b) — 봉투가 바뀌면 청크가 바뀐다.
        "doc_hash": doc_hash(env),
        "prompt_version": prompt_version(),
        "prompt": "extract", "prompt_text": gateway.prompt_text_hash("extract"),     # 지시문 이름 · 문면 해시 — 기록만 (B135 ③)
        "config_version": cfg.get("config_version") or cfg.get("skeleton_version"),   # 기록만(B120 ③)
        "config_extract": config_scope.extract_key(cfg),     # 재사용의 층 config 판 — 추출 갈래 칸의 해시(B120 ③)
        "layer": cfg["layer"],
        "extracted_at": env.get("parsed_at"),
        "candidates": candidates,
    }
    if ref_skipped:
        # 키는 **있을 때만** 단다 — 역할 없는 문서의 체크포인트가 바이트로 갈리지 않는다.
        out["ref_skipped"] = ref_skipped
    if OL.targets_key(outline):
        out["outline"] = OL.targets_key(outline)             # 재사용 조건의 개요 몫(B115 ③ — 대상이 있을 때만)
    if lens:
        out["lens"] = lens                                   # 렌즈 판 (B91 ①)
        out["lens_skipped"] = lens_skipped
    paths.ensure(EXTRACT_DIR)          # 폴더를 만드는 자리는 하나다 (B78 1a)
    checkpoint_path(env["doc_id"], lens).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
