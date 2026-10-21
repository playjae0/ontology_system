# -*- coding: utf-8 -*-
"""칸 3.3 — **추출 호출 보존** — 실호출 하나의 답을 그 호출에 실제로 보낸 입력의 해시로 둔다 · 같은 입력이면 다시 쓴다 (B135 ①②).

  열쇠 = 지시문 이름 + 판 + 모델 · 온도 + 보낸 입력(사용자 글 · 층 힌트 · 답 꼴 · 그림 해시)의 해시 — **지시문 문면은 열쇠가 아니다**
        (판이 사람이 올리는 의미의 선언 · 문면 해시는 기록 · B135 ③) · 빠뜨릴 축이 없게 보낸 것 전부를 잡는다
  자리 = ④작업 `work/extract/calls/<doc_id>[@<렌즈>]/<열쇠>.json` — 열쇠마다 한 파일(원자 쓰기 · 통째 다시 쓰기 0 · 프로세스 사이 안전) ·
        추출 폴더 안이라 기본 fresh가 남긴다(보존 여섯 그대로 · 새 단 0) · 파생물(지우면 비용만 든다)
  담는 것 = 그 호출의 답(선택 칸을 정리한 답 — 근거 청크로 나누기 · 거름 · 정규화 · 맞춤표는 다시 돈다) + 지시문 표지 ·
        실패한 호출은 담지 않는다(다음에 다시 부른다) · 끝까지 돈 추출은 그 실행이 쓰지 않은 답을 지운다(자란 채 남지 않게)
  씨앗 = 문서 단위 체크포인트의 재사용 조건이 지금과 같으면(도입 — 호출 0) 그 청크 몫의 답을 지금 조립한 입력의 열쇠로 담는다
        (청크 하나 = 호출 하나이고 캡처가 없을 때만 — 슬라이드 · 쪽 묶음은 씨앗 0)

mock(USE_MOCK=1)은 담지 않는다 — 문형 규칙 · 힌트는 호출 비용이 없고 결정적이다(같은 입력 → 같은 답이 이미 성립한다).
"""
from __future__ import annotations

import hashlib
import json

from core import paths
from core.llm import gateway
from core.state import log, store

_LOG = log.get(__name__)

SUBDIR = "calls"


def key(material):
    """열쇠 — 보낸 입력 전부의 해시(앞 32자)."""
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def folder(doc_id, lens=None):
    from core.build import extract as EX
    return EX.EXTRACT_DIR / SUBDIR / (f"{doc_id}@{lens}" if lens else str(doc_id))


def get(doc_id, lens, k):
    """그 열쇠의 답 또는 None — 지시문 판이 같고 문면만 다르면 화면 한 줄(재호출 0 · `gateway.prompt_drift`)."""
    p = folder(doc_id, lens) / f"{k}.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("answer"), dict):
        return None
    gateway.prompt_drift(d.get("prompt") or "extract", d)
    return d["answer"]


def put(doc_id, lens, k, answer, stamp):
    p = folder(doc_id, lens) / f"{k}.json"
    store.atomic_write_bytes(p, (json.dumps({**stamp, "answer": answer}, ensure_ascii=False) + "\n").encode("utf-8"))


def count(doc_id):
    """그 문서(렌즈 전부)에 남은 답 수 — 「남은 것」 화면이 읽는다."""
    from core.build import extract as EX
    d = EX.EXTRACT_DIR / SUBDIR
    if not d.exists():
        return 0
    return sum(1 for f in d.iterdir() if f.is_dir() and (f.name == str(doc_id) or f.name.startswith(f"{doc_id}@"))
               for _ in f.glob("*.json"))


def prune(doc_id, lens, used):
    """끝까지 돈 추출 — 이 실행이 쓰지 않은 답을 지운다(지운 수). 쓴 답 = 부른 것 + 다시 쓴 것 + 씨앗."""
    d = folder(doc_id, lens)
    if not d.exists():
        return 0
    gone = 0
    for f in d.iterdir():
        name = f.name[1:].split(".json", 1)[0] if f.name.startswith(".") else f.stem
        if name not in used:
            f.unlink(missing_ok=True)
            gone += 1 if not f.name.startswith(".") else 0
    return gone
