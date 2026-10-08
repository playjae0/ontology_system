# -*- coding: utf-8 -*-
"""칸 0.5 — **사내 손잡이** — 사내 실측으로 정할 값은 사내에서 바꿀 수 있어야 한다 (B91 ⑤).

사내 실측은 이 레포로 가져올 수 없다 — 그래서 값을 정할 **분포는 사내 화면에** 보이고
(`python run.py show knobs` → 손잡이마다 분포를 보는 명령), 값은 **상태 루트의 한 파일**
`$ONTO_HOME/knobs.json`으로 바꾼다. 없으면 전부 기본값이고 **기본값 = 코드 상수**다(값의
자리는 코드 한 곳 — 두 벌 0).

**닫힌 목록이다** — 모르는 키 · 형이 다른 값은 거부한다(`KnobError` — 문면 + 다음 줄).
조용히 무시하면 사람은 바꾼 줄 알고 결과는 그대로다.

전달 두 갈래:
- **파서 손잡이**(청크를 가르는 셋 · 형태 판정 · 시트 제안) — 파서는 core를 모르므로
  `parser.tuning.apply`로 **주입**한다(상태 루트가 정해질 때 한 번 — `paths.home()`).
  킷(subprocess)은 `--knobs <파일>`로 같은 값을 받는다.
- **core 손잡이**(근거 수집 상한 · 렌즈 · 시트 자동 · ref 근처) — 쓰는 자리가 `get(이름)`으로
  읽는다(기본값은 그 모듈의 상수).

**기록**: 산출을 바꾸는 값은 그때 쓴 값과 출처(`default`/`file`)를 인입 기록에 남긴다
(`record()` — 손잡이 파일이 있을 때만 · 없으면 기록 모양이 지금과 같다).
"""
from __future__ import annotations

import importlib
import json

from core import paths

#: 손잡이 — 이름: (주인 모듈, 속성들, 형, 무엇, 분포를 보는 자리)
#: 형: `int`(≥1) · `int0`(≥0) · `range`([작은, 큰] 정수 · 1 ≤ 작은 < 큰) ·
#:     `pair0`([≥1 정수, ≥0 정수]) · `dict`(기본값과 같은 키 · 수) · `pct`(1~100 정수) ·
#:     `choice:<값|값…>`(닫힌 문자열 — B104 ②)
KNOBS = {
    "heading_max_chars": ("parser.struct_map", ("HEADING_MAX_CHARS",), "int",
                          "제목 후보의 최대 글자 — 넘는 번호 행은 제목이 아니다",
                          "python run.py show dist headings"),
    "chunk_rows": ("parser.struct_map", ("CHUNK_MIN", "CHUNK_MAX"), "range",
                   "청크 목표 행 구간 — 분할 레벨 선택의 기준",
                   "python run.py show dist chunks"),
    "chunk_max_chars": ("parser.struct_map", ("CHUNK_MAX_CHARS",), "int",
                        "청크 글자 상한 — 넘는 청크만 행 경계로 가른다",
                        "python run.py show dist chunks"),
    "sheet_thresholds": ("parser.form", ("SHEET_THRESHOLDS",), "dict",
                         "시트 역할 로직 제안의 문턱(글자비 · 행 · 평균 길이)",
                         "python run.py show dist sheets"),
    "form_auto": ("parser.form", ("AUTO_MIN_FOR", "AUTO_MAX_AGAINST"), "pair0",
                  "형태 판정 자동 조건 [찬성 최소, 반대 최대]",
                  "python run.py show dist forms"),
    "sheet_min_hits": ("parser.form", ("SHEET_MIN_HITS",), "int0",
                       "시트 로직 제안의 사전 적중 문턱 — 모양이 산문이어도 렌즈 층 어휘가 이만큼(종) "
                       "안 나오면 ref · 자동 모드는 로직과 LLM이 합의해야 자동",
                       "python run.py show dist sheets"),
    "skeleton_column_pct": ("parser.tagger", ("SKELETON_COLUMN_PCT",), "pct",
                            "등록 관문 골격 값 열 문턱(%) — entity 열의 값이 이 비율 이상 골격 목록에 있으면 "
                            "FAIL(좌표·anchor로 매핑해야 한다)",
                            "등록 관문 화면 G4H 줄 — 열마다 골격 값 k/n"),
    "collect_limit": ("core.query.query", ("COLLECT_LIMIT",), "int",
                      "근거 수집 상한(청크)", "python run.py show dist evidence"),
    "ref_limit": ("core.query.query", ("REF_LIMIT",), "int0",
                  "ref 노드 근처 상한 — 링킹 노드 표기가 든 참조 시트 청크 [관련 원문] 몇 건(0=끔)",
                  "python run.py show dist ref"),
    "lens_min_score": ("core.build.lens", ("LENS_MIN_SCORE",), "int0",
                       "렌즈 관련성 문턱 — 청크에 그 층 어휘가 몇 종 나와야 부르나(렌즈 둘 이상 · 0=거르지 않음)",
                       "python run.py show dist lens"),
    "lens_call_cap": ("core.build.lens", ("LENS_CALL_CAP",), "int",
                      "문서당 렌즈 호출 상한 — 넘으면 묻는다(비대화형은 멈춘다)",
                      "python run.py show dist lens"),
    # ── 질의 하이브리드(B104 ②③) — 기본값은 창작 기본값이다(사내 질문으로 `golden score` 전후를 보고 정한다)
    "query_link_top_k": ("core.query.hybrid", ("LINK_TOP_K",), "int",
                         "질의 링킹 후보 수 — 질문 벡터에 가까운 노드 k개만 LLM 선별에 보낸다(노드 전부를 보내지 않는다)",
                         "python run.py golden score — 링킹(사전만 · 보충)"),
    "query_link_mode": ("core.query.hybrid", ("LINK_MODE",), "choice:보충|폴백",
                        "질의 링킹 단계 — 보충(사전이 잡아도 임베딩 후보 + LLM 선별로 더 찾는다) · 폴백(사전 미스일 때만)",
                        "python run.py golden score — 링킹(사전만 · 보충)"),
    "query_doc_top_k": ("core.query.hybrid", ("DOC_TOP_K",), "int",
                        "문서 검색 채널 — 임베딩 상위 k + BM25 상위 k(합쳐 중복 제거)",
                        "python run.py golden score — doc@k (BM25 대조군 옆)"),
    "query_doc_min_sim": ("core.query.hybrid", ("DOC_MIN_SIM",), "pct",
                          "문서 검색 채널의 임베딩 유사도 문턱(%) — 넘는 청크만 · BM25는 공유 토큰이 있을 때만 · "
                          "둘 다 비면 「근거 없음」(모델마다 점수 분포가 다르다)",
                          "python run.py query \"<질문>\" — [문서 검색] 줄의 점수"),
    "viewer_explore_threshold": ("cli.viewer.data", ("EXPLORE_THRESHOLD",), "int",
                                 "뷰어 탐색 모드 문턱 — 노드가 이보다 많으면 첫 화면을 골격 뿌리부터 "
                                 "탐색 모드로 연다(이웃 펼쳐 보기 · B103 ③)",
                                 "python run.py viewer — 머리 줄 노드 수"),
}
PARSER_KNOBS = tuple(k for k, v in KNOBS.items() if v[0].startswith("parser."))

_STATE = {"values": {}, "loaded": False, "error": None}


class KnobError(ValueError):
    """손잡이 파일이 닫힌 목록·형 밖이다 — 문면에 다음 줄이 있다."""


def default(name):
    owner, attrs, *_ = KNOBS[name]
    if owner.startswith("parser."):
        from parser import tuning
        return tuning.defaults()[name]
    mod = importlib.import_module(owner)
    vals = [getattr(mod, a) for a in attrs]
    return vals[0] if len(vals) == 1 else list(vals)


def _check(name, v, dflt):
    kind = KNOBS[name][2]

    def _int(x, lo):
        return isinstance(x, int) and not isinstance(x, bool) and x >= lo
    ok = {"int": lambda: _int(v, 1), "int0": lambda: _int(v, 0),
          "pct": lambda: _int(v, 1) and v <= 100,
          "range": lambda: isinstance(v, list) and len(v) == 2 and all(_int(x, 1) for x in v)
          and v[0] < v[1],
          "pair0": lambda: isinstance(v, list) and len(v) == 2 and _int(v[0], 1) and _int(v[1], 0),
          "dict": lambda: isinstance(v, dict) and set(v) == set(dflt)
          and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v.values()),
          }[kind]() if not kind.startswith("choice:") else v in kind[len("choice:"):].split("|")
    if not ok:
        raise KnobError(
            f"[상태] 손잡이 '{name}'의 값 {json.dumps(v, ensure_ascii=False)}가 형 밖이다 — "
            f"기대 {kind} · 기본값 {json.dumps(dflt, ensure_ascii=False)}\n"
            f"  근거 — {paths.show(paths.knobs())}\n"
            f"  ▶ 다음 줄: 그 값을 고치거나 키를 지운다(기본값으로 돈다) → python run.py show knobs")


def load():
    """파일의 값(검증 뒤) — 없으면 `{}`. 모르는 키 · 형 밖은 `KnobError`."""
    p = paths.knobs()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise KnobError(f"[상태] 손잡이 파일이 JSON이 아니다 — {paths.show(p)} ({e})\n"
                        f"  ▶ 다음 줄: 파일을 고치거나 지운다(기본값으로 돈다)") from e
    if not isinstance(raw, dict):
        raise KnobError(f"[상태] 손잡이 파일은 {{이름: 값}} 한 벌이다 — {paths.show(p)}")
    vals = {k: v for k, v in raw.items() if not k.startswith("_")}   # `_`로 시작하면 주석
    bad = sorted(set(vals) - set(KNOBS))
    if bad:
        raise KnobError(
            f"[상태] 손잡이 파일에 모르는 키 {bad} — {paths.show(p)}\n"
            f"  아는 키: {' · '.join(KNOBS)}\n"
            f"  ▶ 다음 줄: 그 키를 지우거나 이름을 고친다 → python run.py show knobs")
    for k, v in vals.items():
        _check(k, v, default(k))
    return vals


def apply():
    """파일을 읽어 **파서에 주입**하고 core 값을 기억한다 — 상태 루트가 정해질 때 한 번."""
    from parser import tuning
    vals = load()
    tuning.apply({k: v for k, v in vals.items() if k in PARSER_KNOBS})
    _STATE.update(values=vals, loaded=True)
    return vals


def apply_safe():
    """상태 루트가 정해질 때 — 어긋난 파일은 **오류를 기억하고 기본값으로** 둔다(여기서 올리지
    않는다: 루트는 import 시점에도 정해진다). 멈추는 자리는 `error()`를 보는 관문과 값을 읽는 자리다."""
    try:
        apply()
        _STATE["error"] = None
    except KnobError as e:
        from parser import tuning
        tuning.apply({})
        _STATE.update(values={}, loaded=True, error=e)


def error():
    """어긋난 손잡이 파일의 `KnobError` 또는 `None`."""
    return _STATE["error"]


def _raise_if_bad():
    if _STATE["error"] is not None:
        raise _STATE["error"]


def reset():
    """시험의 문 — 주입을 기본값으로 되돌리고 다시 읽게 한다."""
    from parser import tuning
    tuning.apply({})
    _STATE.update(values={}, loaded=False)


def get(name):
    """core 손잡이의 지금 값 — 파일에 있으면 그것, 없으면 주인 모듈의 상수."""
    if not _STATE["loaded"]:
        paths.home()                       # 첫 결정이 apply를 부른다
    _raise_if_bad()                        # 어긋난 파일로 조용히 기본값을 쓰지 않는다
    return _STATE["values"].get(name, default(name))


def source(name):
    return "file" if name in _STATE["values"] else "default"


def record(names):
    """인입·파싱 기록에 실을 `{이름: {value, from}}` — **손잡이 파일이 없으면 `None`**
    (기록 모양이 지금과 같다 — 파일 없음 = 산출 불변)."""
    if not paths.knobs().exists():
        return None
    _raise_if_bad()
    return {n: {"value": get(n) if not KNOBS[n][0].startswith("parser.") else _parser_now(n),
                "from": source(n)} for n in names}


def _parser_now(name):
    from parser import tuning
    return tuning.current()[name]


def rows():
    """화면 표 — 손잡이마다 이름 · 값 · 출처 · 기본값 · 무엇 · 분포 자리."""
    paths.home()
    _raise_if_bad()
    out = []
    for n, (_owner, _attrs, kind, what, dist) in KNOBS.items():
        now = _parser_now(n) if n in PARSER_KNOBS else get(n)
        out.append({"name": n, "value": now, "from": source(n), "default": default(n),
                    "kind": kind, "what": what, "dist": dist})
    return out


#: 인입 기록에 싣는 손잡이 — 청크를 가르는 셋 · 형태·시트 판정
PARSE_RECORD = ("heading_max_chars", "chunk_rows", "chunk_max_chars", "form_auto",
                "sheet_thresholds", "sheet_min_hits")
