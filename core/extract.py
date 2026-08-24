# -*- coding: utf-8 -*-
"""n3 추출 단계 — 파싱과 구축 사이의 **독립 단계** (CH3A 3.1·3.11, 틀 Q1).

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

from . import log, store
from .ids import norm

ROOT = Path(__file__).resolve().parent.parent
EXTRACT_DIR = ROOT / "extract"
HINTS_DIR = ROOT / "mock" / "extract_hints"

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
    p = PROMPTS_DIR / f"{name}.md"
    if not p.exists():
        log.explicit_fail(_LOG, "core.extract.prompt_version",
                          f"지시문 템플릿이 없다: {p} — prompt_version의 정본은 "
                          "파일이다(문서 7 §7.6-B-5)")
        raise FileNotFoundError(f"지시문 템플릿 없음: {p}")
    for line in p.read_text(encoding="utf-8").splitlines()[:10]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    log.explicit_fail(_LOG, "core.extract.prompt_version",
                      f"{p} 머리말에 version: 줄이 없다")
    raise ValueError(f"{p}: 머리말 version: 줄이 없다")


def checkpoint_path(doc_id):
    return EXTRACT_DIR / f"{doc_id}.json"


def has_checkpoint(doc_id):
    return checkpoint_path(doc_id).exists()


def invalidate(doc_id):
    """재인입 — 청크가 바뀌었으므로 체크포인트를 버린다 (규약 7)."""
    p = checkpoint_path(doc_id)
    if p.exists():
        p.unlink()


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


def _mock_candidates(chunk_id, text, cfg, vocab):
    """문형 규칙 폴백. 카테고리는 config 정의문 예시·사전 매칭으로 정한다.

    **USE_MOCK 한정이다.** 경계가 코드에 없어 실LLM 경로에서도 이 규칙이 돌았다
    (G6.5 E3이 이 게이트를 세웠다). 실물 경로는 미구현이므로 **명시적으로 실패**한다.
    """
    if os.environ.get("USE_MOCK", "1") != "1":
        raise NotImplementedError(
            "문형 폴백은 USE_MOCK 한정이다 (한시 예외 3호) — "
            "실LLM 추출 경로는 미구현이다. HOOK: 여기에 추출 에이전트를 붙인다")
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
    p = HINTS_DIR / f"{doc_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def extract(env, cfg, chunk_ids_by_locator, vocab):
    """계약 JSON(prose) → extract/{doc_id}.json. 이미 있으면 만들지 않는다."""
    doc_id = env["doc_id"]
    if has_checkpoint(doc_id):
        return json.loads(checkpoint_path(doc_id).read_text(encoding="utf-8")), False

    hints = _load_hints(doc_id)
    candidates = []
    for c in env.get("chunks", []):
        cid = chunk_ids_by_locator.get(c.get("source_locator"))
        if cid is None:
            continue
        if hints and c.get("source_locator") in hints:
            h = hints[c["source_locator"]]
            candidates.append({"chunk_id": cid,
                               "entities": h.get("entities", []),
                               "relations": h.get("relations", []),
                               "attach": h.get("attach", [])})
        else:
            candidates.append(_mock_candidates(cid, c.get("text", ""), cfg, vocab))

    out = {
        "doc_id": doc_id,
        "stage": "extract",
        "adapter_version": env.get("adapter_version"),
        "prompt_version": prompt_version(),
        "config_version": cfg.get("config_version") or cfg.get("skeleton_version"),
        "layer": cfg["layer"],
        "extracted_at": env.get("parsed_at"),
        "candidates": candidates,
    }
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path(doc_id).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out, True
