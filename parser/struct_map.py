# -*- coding: utf-8 -*-
"""struct-map — 구조 지도 패스 (틀 v2.8 §4-Q2 · D-58 · R18 · 파서_명세 v0.6 §2·§3).

    LLM이 **지도**를 낸다(데이터: 행 → 헤딩 여부·레벨)
      → 타당성 검사(결정적)
      → 결정적 분할기가 지도를 적용
      → 지도는 산출물과 함께 **보존**한다

**왜 있나.** Q2("분할 규칙은 등록 상수")의 전제는 "같은 doc_type이면 같은 양식"인데,
구조 가변 prose(RFQ류)에서 그것이 성립하지 않는다 — 판본마다 heading pattern이 다르다.
그렇다고 LLM에게 청크를 직접 자르게 하면 §4의 금지("청크 직접 분할")를 깬다.
그래서 **LLM은 지도까지, 자르는 것은 코드**로 가른다.

**안전망 3겹**: ①타당성 검사가 결정적이다(헤딩 0건·레벨 비단조·커버리지 이상)
②실패는 평면 폴백이고 그 사실이 큐로 뜬다(`hierarchy_unresolved` — 신설 0)
③지도를 보존하므로 같은 지도 → 같은 분할 → 같은 chunk_id다(재현성).

**어댑터가 아니라 코어가 소유한다** — 어댑터는 순수 함수 계약(C11)이고 LLM 호출을
하지 않는다. 지도 패스는 운영 매 문서 LLM을 부르므로 코어의 몫이다.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# **파서는 `core/`를 import하지 않는다**(P1) — 그래서 같은 환경변수를 여기서도
# 읽는다. 픽스처가 없으면 번호 패턴 휴리스틱으로 간다(크래시 아님).
MAPS_DIR = Path(os.environ.get("ONTO_FIXTURES")
                or (ROOT / "tests" / "fixtures")) / "struct_maps"
KEEP_DIR = ROOT / "extract" / "struct_maps"       # **보존 자리** (문서 6 §6.3)


def keep_path(doc_id):
    return KEEP_DIR / f"{doc_id}.json"


def load_kept(doc_id, doc_hash=None):
    """보존된 지도를 읽는다 — **doc_hash가 같을 때만** 재사용한다(문서 6 §6.3).

    같은 지도 → 같은 분할 → 같은 chunk_id다. 매 인입 새로 산출하면 그 문서의
    chunk_id가 전량 이동해 재인입 멱등성이 깨진다. doc_hash가 바뀌면 추출
    체크포인트와 함께 무효화된다(§4.8-8과 같은 손잡이).
    """
    p = keep_path(doc_id)
    if not p.exists():
        return None
    m = json.loads(p.read_text(encoding="utf-8"))
    if doc_hash is not None and m.get("doc_hash") not in (None, doc_hash):
        return None
    return m


def keep(doc_id, m, doc_hash=None):
    """지도를 보존한다. **보존 자리는 클린 범위(`extract/`) 안이다**(§6.3).

    밖에 두면 「클린 2회 동일 그래프」가 1회차 지도를 물고 통과해 멱등성의 전면
    검증이 거짓 통과한다.
    """
    KEEP_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(m)
    if doc_hash is not None:
        out["doc_hash"] = doc_hash
    keep_path(doc_id).write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def invalidate(doc_id):
    """재인입으로 doc_hash가 바뀌면 보존분을 버린다 — 추출 체크포인트와 같은 손잡이."""
    p = keep_path(doc_id)
    if p.exists():
        p.unlink()

# 결정적 휴리스틱 폴백 — **현행 toc 어댑터의 heading_pattern 로직을 코어로 이관**한 것이다
# (복제가 아니다). 번호 패턴은 **구문 마커**이지 층 어휘가 아니다.
HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")

FLAT = "flat"                 # 평면 폴백 — 헤딩 없이 통으로
MAPPED = "mapped"


# ---------------------------------------------------------------- ① 지도 산출
def propose(doc_id, lines, ask=None, doc_hash=None):
    """지도 산출 — USE_MOCK은 파일 우선, 없으면 결정적 휴리스틱 (증분0 §5-4).

    지도 형식: `{"doc_id":…, "source":…, "rows":[{"row":n, "heading":bool, "level":int}]}`
    **레벨은 1부터**이고 본문 행은 `heading=false · level=0`이다.

    분기는 `if USE_MOCK: <파일·휴리스틱> else: <실호출>`이고 **반환 형식이 같다** —
    지도는 데이터이므로 소비 쪽(타당성 검사·분할기)은 출처를 몰라도 된다.
    `source` 필드가 어느 갈래인지 데이터로 남긴다: `mock_file` · `heuristic` · `live`.

    파서는 `core/`를 import하지 않으므로(P1) 실호출 경로는 **주입**받는다 —
    `propose(doc_id, lines, ask=…)`. USE_MOCK=0인데 `ask`가 없으면 **명시적
    실패**다: 휴리스틱으로 조용히 떨어지면 그 지도가 청크 경계를 정하고, 잘못된
    경계는 chunk_id를 바꿔 재인입 멱등성까지 흔든다(문서 7 §7.6-B-4).
    """
    kept = load_kept(doc_id, doc_hash)
    if kept is not None:
        kept["source"] = kept.get("source", "kept")
        return kept                          # **보존분 재사용** — 같은 분할·같은 chunk_id
    if os.environ.get("USE_MOCK", "1") != "1":
        if ask is None:
            raise RuntimeError(
                f"구조 지도 실호출 경로가 비어 있다 (doc_id={doc_id}) — "
                "USE_MOCK=0에서는 ask를 주입해야 한다 (문서 7 §7.6-B-4)")
        m = ask(doc_id, lines)
        m.setdefault("doc_id", doc_id)
        m["source"] = "live"
        return keep(doc_id, m, doc_hash)     # 실산출은 보존한다(§6.3)
    p = MAPS_DIR / f"{doc_id}.json"
    if p.exists():
        m = json.loads(p.read_text(encoding="utf-8"))
        m.setdefault("source", "mock_file")
        return m
    rows = []
    for n, text in lines:
        m = HEADING_RE.match((text or "").strip())
        rows.append({"row": n, "heading": bool(m),
                     "level": len(m.group(1).split(".")) if m else 0})
    return {"doc_id": doc_id, "source": "heuristic", "rows": rows}


# ---------------------------------------------------------------- ② 타당성 검사
def validate(smap, lines):
    """결정적 타당성 검사 — 사유 목록을 돌려준다(빈 목록이면 유효).

    셋을 본다: ①헤딩 0건 ②레벨 비단조(1 → 3처럼 건너뜀, 또는 첫 헤딩이 1이 아님)
    ③커버리지 이상(지도가 가리키는 행 집합이 실물 행 집합과 다르다).
    """
    reasons = []
    rows = smap.get("rows") or []
    heads = [r for r in rows if r.get("heading")]
    if not heads:
        reasons.append("헤딩 0건 — 지도가 구조를 못 찾았다")

    prev = 0
    for r in heads:
        lv = r.get("level") or 0
        if lv < 1:
            reasons.append(f"헤딩인데 레벨이 없다 (row {r.get('row')})")
        elif lv > prev + 1:
            reasons.append(f"레벨 비단조 — {prev} → {lv} (row {r.get('row')})")
        prev = max(lv, 0) if lv >= 1 else prev

    want = {n for n, _ in lines}
    got = {r.get("row") for r in rows}
    if got != want:
        reasons.append(f"커버리지 이상 — 지도 {len(got)}행 ↔ 실물 {len(want)}행 "
                       f"(누락 {sorted(want - got)[:5]} · 잉여 {sorted(got - want)[:5]})")
    return reasons


# ---------------------------------------------------------------- ③ 결정적 분할기
def split(smap, lines, locator, sep=" > "):
    """지도를 적용해 자른다 — **여기에 LLM은 없다.** 같은 지도면 같은 분할이다.

    헤딩 행은 청크가 아니라 `section` 경로를 만들고, 그 아래 연속 본문이 청크다.
    """
    level_of = {r["row"]: (r.get("level") or 0) for r in smap.get("rows") or []
                if r.get("heading")}
    text_of = dict(lines)
    out, stack, buf = [], [], []

    def flush():
        if not buf:
            return
        out.append({"source_locator": locator(buf[0], buf[-1]),
                    "section": sep.join(h for _, h in stack),
                    "text": "\n".join(text_of[n] for n in buf),
                    "meta": {}})
        buf.clear()

    for n, text in lines:
        if n in level_of:
            flush()
            depth = level_of[n]
            while stack and stack[-1][0] >= depth:
                stack.pop()
            stack.append((depth, text.strip()))
        else:
            buf.append(n)
    flush()
    return out


def flat(lines, locator):
    """평면 폴백 — 자르지 않고 통으로 낸다. **표시는 호출부가 큐로 한다.**"""
    if not lines:
        return []
    ns = [n for n, _ in lines]
    return [{"source_locator": locator(ns[0], ns[-1]), "section": "",
             "text": "\n".join(t for _, t in lines),
             "meta": {"hierarchy_unresolved": True}}]


# ---------------------------------------------------------------- 진입점
def apply(doc_id, lines, locator, sep=" > "):
    """지도 패스 1회 — `(chunks, smap, reasons)`.

    `reasons`가 비어 있지 않으면 **평면 폴백**이고, 호출부가 그것을 큐로 올린다.
    지도는 실패해도 함께 돌려준다 — 무엇을 보고 실패했는지가 판정 재료다.
    """
    smap = propose(doc_id, lines)
    reasons = validate(smap, lines)
    smap["verdict"] = FLAT if reasons else MAPPED
    smap["reasons"] = reasons
    if reasons:
        return flat(lines, locator), smap, reasons
    return split(smap, lines, locator, sep), smap, []
