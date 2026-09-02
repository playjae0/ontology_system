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


def source_hash(path):
    """**원본 파일의 바이트 해시** — 파서의 지도 재사용 판정에 쓴다.

    `doc_hash`와 **다른 값이고 다른 이름이다**(2A P-D 허브 판정):

    | | 소유 | 무엇 | 언제 |
    |---|---|---|---|
    | `source_hash` | **파서** | 원본 파일 바이트 | 파싱 시점 |
    | `doc_hash` | **에이전트** | 문서 전체 내용 해시(청크 해시의 부산물) | 인입 시점 |

    **파싱은 인입보다 먼저 돈다** — 파서가 지도 재사용을 판단할 시점에 `doc_hash`는
    아직 없다. 그래서 파서는 자기가 볼 수 있는 것으로 판단한다(§2.7-①: "진입 검증은
    파서가 하지 않는다 — 파서는 다른 문서의 존재를 알 필요가 없다").

    **두 값을 같은 이름으로 부르지 않는다** — 같은 이름이면 한쪽 구현이 다른 쪽 값을
    쓰게 되고, 정규화 전후가 달라 재사용 판정이 어긋난다.
    """
    import hashlib
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_kept(doc_id, src_hash=None):
    """보존된 지도를 읽는다 — **`source_hash`가 같을 때만** 재사용한다(문서 6 §6.3).

    같은 지도 → 같은 분할 → 같은 chunk_id다. 매 인입 새로 산출하면 그 문서의
    chunk_id가 전량 이동해 재인입 멱등성이 깨진다. 파일이 바뀌면 무효화되고
    추출 체크포인트도 함께 버려진다(§4.8-8과 같은 손잡이).
    """
    p = keep_path(doc_id)
    if not p.exists():
        return None
    m = json.loads(p.read_text(encoding="utf-8"))
    if src_hash is not None and m.get("source_hash") not in (None, src_hash):
        return None
    return m


def keep(doc_id, m, src_hash=None):
    """지도를 보존한다. **보존 자리는 클린 범위(`extract/`) 안이다**(§6.3).

    밖에 두면 「클린 2회 동일 그래프」가 1회차 지도를 물고 통과해 멱등성의 전면
    검증이 거짓 통과한다.
    """
    KEEP_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(m)
    if src_hash is not None:
        out["source_hash"] = src_hash       # **파서 소유** — doc_hash와 다른 값이다
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
def propose(doc_id, lines, ask=None, src_hash=None):
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
    kept = load_kept(doc_id, src_hash)
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
        return keep(doc_id, m, src_hash)     # 실산출은 보존한다(§6.3)
    # **USE_MOCK 갈래는 보존하지 않는다** — 지도가 **고정 파일**이라 같은 입력이면
    # 늘 같은 지도가 나오고, 보존은 그 위에 아무것도 더하지 않는다(§6.3이 그
    # 사실을 명시한다: "mock만으로는 이 결함이 드러나지 않는다"). 보존이 필요한
    # 것은 **매 인입 새로 산출되는** 실호출 갈래다.
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
# 분할 레벨 선택의 목표 구간 — **가결정**(D-106 · 실측 후 조정 대상).
# 명세는 값을 정하지 않는다(허브 참고치 5~40행).
CHUNK_MIN, CHUNK_MAX = 5, 40


def level_stats(smap, lines):
    """레벨 1..N 각각의 **청크 수와 청크별 행 수 분포** — 결정적·무LLM.

    「어느 레벨에서 자르면 청크가 몇 개고 얼마나 굵은가」를 세어 놓는다. 그것이
    레벨 선택의 근거이고, **지도에 함께 보존해야 같은 지도 → 같은 분할**이 성립한다.
    """
    heads = [(r["row"], r.get("level") or 0)
             for r in (smap.get("rows") or []) if r.get("heading")]
    rows = [n for n, _t in lines]
    if not heads or not rows:
        return {}
    out = {}
    for lv in sorted({l for _r, l in heads}):
        cuts = sorted(n for n, l in heads if l <= lv)
        sizes, i = [], 0
        bounds = cuts + [rows[-1] + 1]
        for a, b in zip(bounds, bounds[1:]):
            body = [n for n in rows if a < n < b and n not in dict(heads)]
            if body:
                sizes.append(len(body))
        if not sizes:
            continue
        out[lv] = {"청크수": len(sizes),
                   "행수_최소": min(sizes), "행수_최대": max(sizes),
                   "행수_평균": round(sum(sizes) / len(sizes), 1),
                   "구간내_청크수": sum(1 for s in sizes
                                   if CHUNK_MIN <= s <= CHUNK_MAX)}
    return out


def choose_level(stats):
    """**목표 구간에 가장 많이 드는 레벨**을 고른다. 돌려주는 것은 `(레벨, 사유)`.

    어느 레벨에서도 구간에 들지 않으면 `None`이다 — 그때는 **지금 동작(전 헤딩
    분할)을 유지한다.** 무리한 병합은 하지 않는다: 잘못 묶은 청크는 근거 인용이
    통째로 어긋나고, 그것은 잘게 자른 것보다 되돌리기 어렵다.
    """
    if not stats:
        return None, "헤딩 없음"
    best = max(stats.items(), key=lambda kv: (kv[1]["구간내_청크수"], -kv[0]))
    if best[1]["구간내_청크수"] == 0:
        return None, f"어느 레벨도 목표 구간({CHUNK_MIN}~{CHUNK_MAX}행)에 들지 않는다"
    if len(stats) == 1:
        return None, "헤딩 레벨이 하나뿐이다 — 고를 것이 없다"
    return best[0], (f"레벨 {best[0]}이 목표 구간에 {best[1]['구간내_청크수']}청크로 "
                     f"가장 많이 든다 (전체 {best[1]['청크수']})")


def split(smap, lines, locator, sep=" > "):
    """지도를 적용해 자른다 — **여기에 LLM은 없다.** 같은 지도면 같은 분할이다.

    헤딩 행은 청크가 아니라 `section` 경로를 만들고, 그 아래 연속 본문이 청크다.

    **모든 헤딩에서 자르지 않는다**(B43): 세밀한 헤딩 문서에서는 청크가 한두 줄로
    부서져 근거로 쓸 수 없다. 레벨별 분포를 세어 **목표 구간에 가장 많이 드는
    레벨까지만** 자르고, 그 레벨에서도 상한을 크게 넘는 청크는 **한 단계만** 더
    쪼갠다(재귀 금지 — 재귀는 다시 부수는 길이다).
    """
    stats = smap.get("레벨_분포") or level_stats(smap, lines)
    pick = smap.get("분할_레벨")
    if pick is None and "분할_레벨" not in smap:
        pick, _why = choose_level(stats)
    all_head = {r["row"]: (r.get("level") or 0) for r in smap.get("rows") or []
                if r.get("heading")}
    level_of = ({n: l for n, l in all_head.items() if l <= pick}
                if pick else dict(all_head))
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

    # **상한을 크게 넘는 청크만 한 단계 더 쪼갠다** — 재귀하지 않는다.
    if pick and any(len(c["text"].split("\n")) > CHUNK_MAX * 2 for c in out):
        deeper = {n: l for n, l in all_head.items() if l == pick + 1}
        if deeper:
            out = _resplit(out, deeper, lines, locator, sep)
    return out


def _resplit(chunks, deeper, lines, locator, sep):
    """상한 초과 청크를 **바로 아래 레벨의 헤딩에서만** 한 번 더 가른다."""
    text_of = dict(lines)
    row_of = {v: k for k, v in text_of.items()}
    out = []
    for c in chunks:
        body = c["text"].split("\n")
        if len(body) <= CHUNK_MAX * 2:
            out.append(c)
            continue
        rows = [row_of.get(x) for x in body]
        cur, seg = [], []
        for r, x in zip(rows, body):
            if r in deeper and seg:
                cur.append(seg); seg = []
            seg.append((r, x))
        if seg:
            cur.append(seg)
        if len(cur) <= 1:
            out.append(c)
            continue
        for part in cur:
            rs = [r for r, _x in part if r is not None]
            out.append({**c,
                        "source_locator": locator(rs[0], rs[-1]) if rs
                        else c["source_locator"],
                        "text": "\n".join(x for _r, x in part)})
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
    # **선택 근거를 지도에 보존한다**(B43 ③) — 같은 지도 → 같은 분할이 성립해야
    # 재인입 멱등이 유지된다. 보존분을 재사용할 때 레벨을 다시 고르면, 표본이
    # 조금만 달라져도 분할이 흔들려 chunk_id가 전량 이동한다.
    if "분할_레벨" not in smap:
        stats = level_stats(smap, lines)
        pick, why = choose_level(stats)
        smap["레벨_분포"] = stats
        smap["분할_레벨"] = pick
        smap["분할_레벨_사유"] = why
    return split(smap, lines, locator, sep), smap, []


# ---------------------------------------------------------------- 분포 (B45)
def split_stats(pieces, map_picks):
    """분할 산출의 크기 분포 (B45) — **보이기만 한다.**

    상수가 부적절해 한 줄짜리 청크가 쏟아져도 지금은 등록 시점에 드러나지 않는다:
    사람이 상수를 고칠 판단 재료가 화면에 없었다. 목표 구간 밖을 **짧은 쪽·긴 쪽
    각각** 세는 이유는 처방이 다르기 때문이다 — 짧으면 분할 신호가 과하고, 길면
    모자라다.
    """
    sizes = [len(str(p.get("text") or "").split("\n"))
             for p in pieces if p.get("text")]
    out = {"청크수": len(sizes), "레벨_선택": map_picks or None}
    if sizes:
        lo, hi = CHUNK_MIN, CHUNK_MAX
        out.update({"행수_최소": min(sizes), "행수_최대": max(sizes),
                    "행수_평균": round(sum(sizes) / len(sizes), 1),
                    "목표구간": [lo, hi],
                    "너무_짧은_청크": sum(1 for s in sizes if s < lo),
                    "너무_긴_청크": sum(1 for s in sizes if s > hi)})
    return out


def adapter_level_picks(adapter, raw):
    """어댑터 경로의 레벨별 분포 — **지도 경로와 같은 계산**(`level_stats`)을 쓴다.

    어댑터가 `expects.heading_pattern`으로 헤딩을 알아보므로, 그 패턴으로 레벨을
    읽어 지도 경로와 **같은 형태**의 분포를 낸다. 새로 짜지 않는 이유는 화면이
    둘로 갈리지 않게 하기 위해서다.

    패턴이 없거나 헤딩이 안 잡히면 **아무것도 내지 않는다** — 지어낸 분포는
    사람이 상수를 고를 재료가 못 된다.
    """
    exp = adapter.get("expects") or {}
    pat = exp.get("heading_pattern")
    if not pat or not raw.get("sheets"):
        return []
    rx = re.compile(pat)
    col = exp.get("content_column", "A")
    out = []
    for sh in raw["sheets"]:
        cells = sh.get("cells") or {}
        lines = [(r, str(cells[f"{col}{r}"]).strip())
                 for r in range(1, int(sh.get("max_row") or 0) + 1)
                 if cells.get(f"{col}{r}") and str(cells[f"{col}{r}"]).strip()]
        rows = []
        for n, txt in lines:
            m = rx.match(txt)
            lvl = len(m.group(1).split(".")) if (m and m.groups()) else 0
            rows.append({"row": n, "heading": bool(m), "level": lvl})
        st = level_stats({"rows": rows}, lines)
        if st:
            out.append({"프레임": sh.get("name"),
                        "분할_레벨": exp.get("split_level"),
                        "분할_레벨_사유": (
                            f"어댑터 상수 expects.split_level={exp['split_level']}"
                            if exp.get("split_level") is not None else
                            "상수 없음 — 전 헤딩 분할(종전 동작)"),
                        "레벨_분포": st})
    return out
