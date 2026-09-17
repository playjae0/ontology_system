# -*- coding: utf-8 -*-
"""개체 판정 — "그것이 기존의 무엇인가" (CH3A 3.3).

    표면형 → ①사전 조회 → (미스) ②후보 검색 → ③LLM 동일성 판정 → 3분기

3분기 (규약 1):
    매칭(≥0.85)  → 기존 노드에 alias 자동 누적
    신규         → 자동 생성 (status=auto + provenance + auto_node 큐)
    불확실       → **신규로 생성** + uncertain_match 큐

불확실을 신규로 보내는 것은 비대칭 설계다 — **병합은 쉽고 분리는 어렵기 때문**이다
(I3가 "자동 불가"인 것과 같은 이유). 잘못 합치면 사람이 배분표를 써야 하지만,
잘못 나누면 병합 도구가 자동으로 되돌린다.

USE_MOCK=1에서는 ③이 문자열 정규화 규칙이다(구현문서 §8) — 네트워크·키 없이
전 루프가 돌아야 하기 때문이며, 실물 LLM 경로와 **분기점이 같다**.
"""
from __future__ import annotations

import json

from core.llm import gateway, narrow
from core.state import log
from core.state.ids import norm
from core.build.naming import POLARITY_NONE
from core.state.status import is_live

# 판정 임계 — **층 config `match_threshold`가 소유한다**(문서 3 §3.1 키 일람).
# 판단에 영향을 주는 자산은 코드에 박지 않는다(문서 7 §7.1 관리 자산의 원칙).
# 아래 상수는 config가 그 키를 선언하지 않았을 때의 폴백이다.
THRESHOLD = 0.85


def threshold(cfg=None):
    """이 층의 판정 임계. 세분화는 판정 보류율이 쌓인 뒤에만(P7·E2)."""
    if cfg is None:
        return THRESHOLD
    v = cfg.get("match_threshold")
    return float(v) if v is not None else THRESHOLD

MATCH = "match"
NEW = "new"
UNCERTAIN = "uncertain"

# 판정 반환의 정본 형태 — 문서 4 §4.3-6. 두 갈래가 이것을 함께 지킨다.
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"type": {"type": "string", "enum": [MATCH, NEW, UNCERTAIN]},
                   "matched_id": {"type": ["string", "null"]},
                   "confidence": {"type": "number"}},
    "required": ["type", "matched_id", "confidence"], "additionalProperties": False,
}

_LOG = log.get(__name__)


def _similarity(a, b):
    """USE_MOCK 판정 규칙 — 공백 제거 후 동일/포함이면 0.95 (구현문서 §8).

    "노칭정밀도"와 "노칭 정밀도"는 표기 차이라 붙어야 하고,
    "cathode 노칭 프레스"와 "anode 노칭 프레스"는 다른 실물이라 붙으면 안 된다.
    후자는 표면형 자체가 다르므로 이 규칙으로도 갈린다.
    """
    x, y = norm(a).replace(" ", ""), norm(b).replace(" ", "")
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    if x in y or y in x:
        return 0.95
    return 0.0


def _pol(value):
    """polarity 필드의 정규형. 필드가 없는 노드는 `none`으로 읽는다(닫힌 4값)."""
    return value or POLARITY_NONE


# **판정에 올리는 후보의 상한**(B73 ① · 06 대장 3.4). 사내 실측 열두째: 후보가
# 카테고리·층 **전량**이라 노드가 늘수록 매 판정의 입력이 커졌다(입력 토큰 2만,
# 출력 40 이하). 명세는 처음부터 다르게 말한다 — 문서 4 §4.2 ②「후보 검색 — 사전
# 미스 시 임베딩 유사도」. 상한 하나가 그 구현의 손잡이다.
CANDIDATE_TOP_N = 12

# **판정의 계측** — 화면이 「어떻게 좁혔고 몇 번 불렀나」를 세는 재료다(B73 ①).
# 세는 자리가 **그 일을 하는 자리**와 같아야 화면과 실물이 갈리지 않는다.
STATS = {"판정": 0, "사전": 0, "스코프": 0, "스코프끝": 0, "임베딩": 0, "겹침": 0,
         "그대로": 0, "후보합": 0, "조립": 0}

# 진행 콜백 — 호출부가 꽂는다(기본 없음). **판정 중에도 비용이 보인다**(사용자
# 요청 2026-09-16): 좌표 태깅 진행 줄(B69 ②)과 같은 결이고, 자리는 부르는 자리다.
PROGRESS = None


def reset_stats():
    for k in STATS:
        STATS[k] = 0
    return STATS


def _bigrams(text):
    """정규화 문자 2-gram 집합 — mock의 결정적 유사도 재료."""
    t = norm(text).replace(" ", "")
    return {t[i:i + 2] for i in range(len(t) - 1)} or ({t} if t else set())


def _overlap(a, b):
    """2-gram 교집합 비율 — **mock 전용**. 결정적이고 LLM·임베딩을 부르지 않는다.

    mock의 `embed()`는 sha256 해시라 유사도가 아무 뜻이 없다(가짜 확신 — §7.5-1).
    회귀가 도는 세계에서는 **어휘 겹침**으로 고르고, 실호출 세계에서만 임베딩이
    돈다. 둘의 반환 계약은 같다: 점수로 정렬한 상위 N.
    """
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / max(1, len(x | y))


def scope_filter(pool, parent, scope_cats, category):
    """**스코프는 하드 필터다** — 부모가 다른 노드는 후보에 **넣지 않는다** (B75 ②).

    D-152 ①이 적은 규율의 실물이다. 구판은 「상한을 넘을 때만」 부모로 좁혔고, 그
    결과 둘이 새어 나갔다: ⓐ후보가 12개 이하면 다른 공정의 노드가 그대로 판정에
    올랐다 ⓑ같은 부모 아래가 **0개면** 필터를 건너뛰어 **다른 공정 전량**이
    임베딩→판정에 올랐다 — 답이 NEW로 정해져 있는 새 공정의 첫 값들이 매번 모델을
    불렀다(사내 실측 열넷째: 목록 밖 53종 · 새 공정 다수).

    부모가 다르면 다른 실물이다(문서 4 §4.5-6). 그래서 **0개면 후보 0**이고,
    `match`가 그 자리에서 NEW를 낸다 — LLM 0 · 임베딩 0.

    부모가 없는 값(좌표 미해소)은 거르지 않는다 — 모르는 것을 근거로 버리지 않는다.
    """
    if not parent or category not in (scope_cats or ()):
        return pool, False
    return [c for c in pool if c.get("parent") == parent], True


def _narrow(surface, pool, top_n, *, scoped=False):
    """후보를 **상한 안으로 좁힌다** — 임베딩 또는 겹침 (B73 ① · B75 ①).

    스코프 하드 필터는 이 함수 **앞**에서 이미 걸렸다(`scope_filter`) — 여기 오는
    것은 「같은 자리의 후보」이고, 그것이 상한을 넘을 때만 유사도가 돈다.

    **무엇으로 좁히는지는 설정이 정한다**(`CANDIDATE_NARROW` — B75 ①): 임베딩은
    선택이고, 없으면 **정규화 문자 2-gram 겹침**으로 고른다. 겹침은 mock의 sha256
    벡터(가짜 확신 — D-152 ②)와 다르다: 실제 문자 기반이고 결정적이다.

    **자르는 것은 판정이 아니라 조립이다** — 잘린 후보는 판정에 오르지 않을 뿐
    노드로는 살아 있고, 사전 히트는 애초에 여기 오지 않는다(상한과 무관).
    """
    if len(pool) <= top_n:
        return pool, ("스코프" if scoped else "그대로")
    mode, _why = narrow.narrow_choice()
    if mode == "overlap":
        scored = sorted(pool, key=lambda c: -_overlap(surface, c["canonical"]))
        return scored[:top_n], "겹침"
    # **임베딩 대상은 canonical과 정의문이다**(문서 4 §4.2 ② — 정의문이 빠지면
    # 카테고리 경계가 벡터에 실리지 않는다). 벡터는 저장하지 않는다(P5).
    from core.llm import embeddings
    qv = embeddings.embed(surface)
    scored = sorted(
        pool, key=lambda c: -embeddings.cosine(
            qv, embeddings.embed(" ".join(
                [c["canonical"], c.get("정의문") or c.get("definition") or ""]).strip())))
    return scored[:top_n], "임베딩"


# **생성 경로의 닫힌 값**(B74 ②) — 대장이 적는 `path`가 여기 밖이면 FAIL이다.
# 코드가 아는 사실만 적는다(LLM 산출이 아니다 — C38의 결).
PATHS = ("skeleton", "dictionary", "scope+judge", "embedding+judge",
         "overlap+judge", "none")

# 좁힌 방법 → 경로 이름. `그대로`(좁힐 것도 없었다)는 **그 실행이 고른 방법**의
# 이름으로 적는다 — 후보를 무엇으로 고르는 세계였는지가 그 자리의 사실이다(B75 ①).
_HOW_PATH = {"스코프": "scope+judge", "스코프+": "scope+judge",
             "임베딩": "embedding+judge", "겹침": "overlap+judge"}


def _path_of(pool):
    """이 판정이 **어떻게 여기까지 왔는가** — 후보가 지고 온 사실로 답한다(B74 ②)."""
    how = next((c.get("how") for c in pool if c.get("how")), None)
    if how in _HOW_PATH:
        return _HOW_PATH[how]
    return ("embedding+judge" if narrow.narrow_choice()[0] == "embed"
            else "overlap+judge")


def _cand(nid, n, exact=False):
    """후보 하나의 형태 — 명세가 정한다(문서 4 §4.3-6). 조립 두 갈래가 이것을 쓴다."""
    return {"id": nid, "canonical": n["canonical"],
            "aliases": [a["surface"] for a in n.get("aliases") or []],
            "category": n["category"], "layer": n.get("layer"),
            "parent": n.get("parent") or n.get("mirror_scope"),
            "scoped": bool(n.get("_scoped")),
            "polarity": _pol(n.get("polarity")),
            # **아직 사람이 확인하지 않은 노드인지 판정이 알아야 한다**(B73 ③).
            # 오판 하나가 다음 문서를 끌어당기는 연쇄를 여기서 끊는다.
            "status": n.get("status"),
            "evidence": len(n.get("provenance") or []),
            "exact": exact}


def dict_hits(surface, category, layer, graph, dictionary, *, polarity=None,
              parent=None, scope_cats=()):
    """**사전 exact 후보** — 결정적·무LLM. 후보 조립 ①이고 예고가 같이 쓴다(B74 ①).

    **키가 갈리면 사전은 영영 히트하지 않는다.** 등재는 원 표기로 하고 조회는
    스코프 canonical로 하던 구판이 그랬다 — 예고는 「사전 히트 31종」이라 하고
    판정은 「사전 0」이었다(허브 실측 열셋째). 고친 자리는 둘이다: 등재가 두 키를
    모두 넣고(`build._register`), **세는 함수를 하나로 둔다**(여기).

    안전망 하나를 더 건다 — **부모가 다르면 exact가 아니다**(스코프 카테고리 한정).
    원 표기 키로 부르는 경로(재시도 `_pick_*`·병합 후보)가 `노칭::cutter`와
    `세퍼레이터::cutter`를 같은 것으로 올리지 못하게 한다. 부모를 모르는 호출
    (`parent=None`)은 거르지 않는다 — 모르는 것을 근거로 버리지 않는다.
    """
    want = _pol(polarity)
    scoped_cat = category in (scope_cats or ())
    out = []
    for nid in dictionary.lookup(surface):
        n = graph.get(nid)
        if not n or n["category"] != category or n["layer"] != layer:
            continue
        if _pol(n.get("polarity")) != want:
            continue
        if scoped_cat and parent is not None \
                and (n.get("parent") or n.get("mirror_scope")) != parent:
            continue
        out.append(_cand(nid, n, exact=True))
    return out


def candidates(surface, category, layer, graph, dictionary, *, scoped=True,
               polarity=None, parent=None, cfg=None, top_n=None):
    """**후보 조립** — 판정과 분리한다 (문서 7 §7.1 · 문서 4 §4.3-6).

    후보 하나의 형태는 명세가 정한다 — `canonical` · `aliases` · **부착 위치
    (부모·스코프)** · `category`. 부착 위치가 입력에서 빠지면 부모 미해소 노드의
    병합 금지와 극성 후보 제외를 판정기가 알 수 없어, 두 안전망이 판정 **전**
    필터가 아니라 사후 필터로 밀려난다.

    안전망 넷은 **후보에 넣지 않는 것**으로 건다 — 감점이 아니라 제외다:

    1. **툼스톤 제외**(`is_live`) — 사람이 지운 것을 판정이 되살리지 않는다.
    2. **카테고리 불일치**(규약 3) — "노칭"(Process)과 "노칭 정밀도"(Property)가
       유사도로 붙는 사고의 구조적 차단.
    3. **극성 불일치**(D-40) — "cathode 노칭 프레스"와 "anode 노칭 프레스"는 표기
       차이가 아니라 다른 실물이다. 근거는 canonical 문자열이 아니라 `polarity`
       **필드**다(A11-8).
    4. **부모 미해소 ↔ 스코프 노드**(문서 4 §4.5-6) — 좌표를 모른 채 만든 노드를
       유사도로 합치면 오병합이다.

    사전 히트는 **`exact` 표시를 달아** 앞에 둔다 — 결정적·무LLM 경로라 판정이
    그것을 1.0으로 인정할 근거가 후보에 남아야 한다.
    """
    want = _pol(polarity)
    scope_cats = ((cfg or {}).get("canonical_scope") or {}).get("bind_categories", [])

    # ① 사전 조회 — 결정적·무LLM. **예고와 판정이 같은 함수를 쓴다**(B74 ①).
    out = dict_hits(surface, category, layer, graph, dictionary,
                    polarity=polarity, parent=parent, scope_cats=scope_cats)
    seen = {c["id"] for c in out}

    # ② 후보 검색 — 위 안전망 넷으로 걸러 담고, **상한 안으로 좁힌다**(B73 ①).
    pool = []
    for nid, n in graph.nodes.items():
        if nid in seen or not is_live(n):
            continue
        if n["category"] != category or n["layer"] != layer:
            continue
        if not scoped and n.get("_scoped"):
            continue
        if _pol(n.get("polarity")) != want:
            continue
        pool.append(_cand(nid, n))
    # **스코프 하드 필터가 먼저다**(B75 ②) — 상한 이하 여부와 무관하다.
    pool, scoped_hard = scope_filter(pool, parent, scope_cats, category)
    if scoped_hard and not pool and not out:
        # 같은 부모 아래가 없다 — 답은 NEW로 정해져 있다. 여기서 끝낸다.
        STATS["스코프끝"] += 1
    # **후보 전량을 판정에 올리지 않는다**(B73 ①) — 상한 안으로 좁힌다.
    kept, how = _narrow(surface, pool, top_n or CANDIDATE_TOP_N,
                        scoped=scoped_hard)
    STATS["조립"] += 1
    STATS["후보합"] += len(out) + len(kept)
    STATS[how] = STATS.get(how, 0) + 1
    for c in kept:
        # **어떻게 좁혔는가를 후보가 지고 온다**(B74 ②) — 판정이 경로를 적을 때
        # 그 사실을 다시 계산하지 않는다. 계산한 자리가 아는 것을 실어 올린다.
        c["how"] = how
    return out + kept


def match(surface, candidates, category, cfg=None):
    """**개체 판정은 이 함수 하나로 수렴한다** (문서 7 §7.1 core 접근 경계).

    입력은 `mention` + 후보들, 출력은 `{"type", "matched_id", "confidence"}`다
    (문서 4 §4.3-6). 반환 형식이 정해져 있어야 USE_MOCK 갈래와 실호출 갈래가
    같은 반환 계약을 지킬 수 있고, 그래야 mock 회귀가 실 연결에도 유효하다.

    `category`는 **안전망의 재확인**이다 — 후보 조립이 이미 걸렀지만, 이 함수는
    attach_to 해소·병합 후보처럼 다른 곳에서 조립된 후보로도 불린다. 조립을
    믹지 않는 것이 관문의 일이다.

    3분기의 비대칭(규약 1): 불확실은 **신규로 만들고 표시한다** — 병합은 쉽고
    분리는 어렵다. 잘못 합치면 사람이 배분표를 써야 하지만, 잘못 나누면 병합
    도구가 자동으로 되돌린다.
    """
    pool = [c for c in candidates if c.get("category") == category]
    for c in pool:
        if c.get("exact"):                           # 사전 히트 — 결정적·무LLM 경로
            STATS["사전"] += 1
            return {"type": MATCH, "matched_id": c["id"], "confidence": 1.0,
                    "path": "dictionary"}
    if not pool:
        return {"type": NEW, "matched_id": None, "confidence": 0.0,
                "path": "none"}
    path = _path_of(pool)
    STATS["판정"] += 1
    if PROGRESS is not None:
        PROGRESS(dict(STATS))

    if not gateway.use_mock():
        return _judge_live(surface, pool, category, cfg, path=path)
    gateway.mock("judge", f"'{surface}' vs 후보 {len(pool)}")

    best, score = None, 0.0
    for c in pool:
        # canonical에는 포함 규칙까지 적용하지만(표기 변형 흡수 — "노칭정밀도" ↔
        # "노칭::노칭 정밀도"), **alias에는 정확 일치만** 적용한다. alias는 조립 전
        # 표면형이라("노칭 프레스") 포함 규칙을 걸면 "cathode 노칭 프레스"가 무극성
        # 노드에 흡수된다 — 다른 실물이 한 노드가 되는 사고다(D-39).
        s = max([_similarity(surface, c["canonical"])]
                + [1.0 for a in c.get("aliases") or []
                   if norm(a) == norm(surface)])
        if s > score:
            best, score = c["id"], s

    if score >= threshold(cfg):
        return _guard_auto({"type": MATCH, "matched_id": best,
                            "confidence": score, "path": path}, pool)
    if score > 0.0:
        # 임계 아래인데 0은 아닌 구간 — 확신이 없으므로 신규로 만들고 표시한다.
        return {"type": UNCERTAIN, "matched_id": None, "confidence": score,
                "path": path}
    return {"type": NEW, "matched_id": None, "confidence": 0.0, "path": path}


def _guard_auto(verdict, pool):
    """**auto 노드에 붙는 매칭은 표기가 같을 때만**이다 (B73 ③).

    `status: auto`는 아직 사람이 확인하지 않은 노드다. 그것에 유사도로 붙이면
    **오판 하나가 다음 문서를 끌어당기는 연쇄**가 된다 — 판정이 자기 산출을
    근거로 삼는 꼴이다. 확신 1.0(표기 동일·사전 히트)이 아니면 `uncertain`으로
    내린다. 계약은 닫힌 3값 그대로이고(`uncertain`은 신규+표시 — 규약 1의
    비대칭), 큐 kind도 `uncertain_match` 그대로다.
    """
    c = next((x for x in pool if x["id"] == verdict.get("matched_id")), None)
    if c and c.get("status") == "auto" and float(verdict.get("confidence") or 0) < 1.0:
        return {"type": UNCERTAIN, "matched_id": None,
                "confidence": verdict.get("confidence", 0.0),
                "path": verdict.get("path")}
    return verdict


def _judge_live(surface, pool, category, cfg=None, *, path=None):
    """지점 ② 개체 동일성 판정의 실호출 갈래 — **반환 계약이 mock과 같다.**

    입력은 `mention` + 후보들이고 후보 하나는 `canonical`·`aliases`·부착 위치·
    `category`로 구성한다(문서 4 §4.3-6). 정의문과 비대칭 기준은 층 config가
    프롬프트로 주입하는데, 그 주입 통로는 별개 갭 항목이다 — 여기서는 이음매를
    세우고 후보 형태와 반환 계약을 지킨다.

    **판정기가 후보 밖의 id를 답하면 버린다.** 모델이 지어낸 id가 엣지 끝점이
    되면 그래프에 없는 노드를 가리키는 엣지가 선다.
    """
    ids = {c["id"] for c in pool}
    out = gateway.chat(
        # **지시문은 파일이 정본이다**(§7.6-B-5). 층 어휘(정의문·비대칭 기준)는
        # config `prompts.judge`가 소유하고 실행 시 조립된다(B9).
        [{"role": "system",
          "content": gateway.prompt("judge")
          + ("\n\n## 층 어휘\n" + (cfg or {}).get("prompts", {}).get("judge", "")
             if (cfg or {}).get("prompts", {}).get("judge") else "")},
         {"role": "user", "content": json.dumps(
             {"mention": surface, "category": category, "candidates": pool},
             ensure_ascii=False)}],
        json_schema=JUDGE_SCHEMA, point="judge")
    vtype = out.get("type")
    mid = out.get("matched_id")
    conf = float(out.get("confidence") or 0.0)
    path = path or _path_of(pool)
    if vtype == MATCH and mid not in ids:
        _LOG.warning("판정이 후보 밖 id를 답했다 — 버리고 uncertain으로 둔다: %r", mid)
        return {"type": UNCERTAIN, "matched_id": None, "confidence": conf,
                "path": path}
    if vtype == MATCH and conf < threshold(cfg):
        return {"type": UNCERTAIN, "matched_id": None, "confidence": conf,
                "path": path}
    if vtype == MATCH:
        return _guard_auto({"type": MATCH, "matched_id": mid,
                            "confidence": conf, "path": path}, pool)
    if vtype not in (MATCH, NEW, UNCERTAIN):
        _LOG.warning("판정 분기가 닫힌 3값 밖이다 — uncertain으로 둔다: %r", vtype)
        return {"type": UNCERTAIN, "matched_id": None, "confidence": conf,
                "path": path}
    return {"type": vtype,
            "matched_id": mid if vtype == MATCH else None,
            "confidence": conf, "path": path}


def resolve(surface, category, layer, graph, dictionary, *, scoped=True,
            polarity=None, parent=None):
    """후보 조립 + 판정의 2단을 한 번에 — Pass 1 entity 경로의 편의 형태다.

    돌려주는 것은 `(분기, node_id 또는 None, 점수, 판정 dict)` 튜플이다 — 네 번째는
    `match`의 반환 그대로이고, 대장이 적을 사실(경로·후보 수)이 거기 있다(B74 ②). **계약의 정본은
    `match`의 dict**이고 이것은 그 위의 얇은 껍데기다 — 판정 로직을 여기 두면
    재사용 지점마다 별도 판정 코드가 생긴다(그것이 고친 결함이다).
    """
    from core.state.bootstrap import load_config
    cfg = load_config(layer)
    cands = candidates(surface, category, layer, graph, dictionary,
                       scoped=scoped, polarity=polarity, parent=parent, cfg=cfg)
    v = match(surface, cands, category, cfg)
    # **후보 수는 판정의 반환이 아니라 조립의 사실이다** — 계약(문서 4 §4.3-6)의
    # 세 키에 `path` 하나만 더한다(B74 ②). 대장이 적을 나머지는 여기서 싣는다.
    v["candidates_n"] = len(cands)
    return v["type"], v["matched_id"], v["confidence"], v
