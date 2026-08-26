# -*- coding: utf-8 -*-
"""모델 게이트웨이 — **LLM 설정 접근이 이 파일 하나로 수렴한다** (문서 7 §7.6-B-1).

    from core import llm
    if llm.use_mock():
        out = <mock 갈래>
    else:
        out = llm.chat(messages, json_schema=SCHEMA)

**왜 이 파일이 있어야 하나.** 명세가 요구한 이 파일이 국면 1의 정본에서 누락된 채
아무도 신고하지 않아 **LLM 연결이 통째로 없는 시스템이 완료판정을 통과했다.** 그
판정은 "mock 위에서 메커니즘이 도는 것"이었고 실 연결(§7.6-B)은 그 범위 밖이었다.

**호출부는 설정을 직접 읽지 않는다.** 수렴점이 없으면 지점마다 다른 규칙으로 붙는다 —
어떤 지점은 환경변수를, 어떤 지점은 config를, 어떤 지점은 상수를 읽게 된다.

## 설정 (환경변수)

| 변수 | 무엇 | 없으면 |
|---|---|---|
| `USE_MOCK` | `1`(기본)이면 전 지점이 mock 갈래 | mock으로 돈다 |
| `LLM_GATEWAY_URL` | 사내 게이트웨이 주소 | USE_MOCK=0에서 **명시적 실패** |
| `LLM_API_KEY` | 인증 | 게이트웨이가 요구하면 실패 |
| `CHAT_MODEL` | 모델명 | USE_MOCK=0에서 **명시적 실패** |
| `EMBED_MODEL` | 임베딩 모델명 | 임베딩 지점에서 실패 |
| `LLM_TIMEOUT` | 초 (기본 60) | 60 |
| `LLM_RETRY` | 재시도 횟수 (기본 2) | 2 |

**기본 명칭은 명세가 정한다**(§7.6-B-1) — 사내 게이트웨이가 다른 이름을 쓰면 그때
대체하되 **이름을 비워 두지 않는다**: 이름이 없으면 구현자가 임의로 만들고, 같은
배포 환경에서 한쪽만 `USE_MOCK=0` 실호출에 연결된다.

**실명칭은 [사내 확인]이다** — 사내 게이트웨이 실물이 아직 없다. 그래서 이 파일이
세우는 것은 **이음매**이고, 프로토콜은 OpenAI 호환 `/chat/completions`를 기본으로
가정한다. 다르면 `_post()` 하나만 고친다 — 그 국지성이 수렴점의 값이다.

## 조용히 mock으로 떨어지지 않는다

`USE_MOCK=0`에서 설정이 비어 있으면 **명시적 실패**로 끝낸다(§7.6-B-4). 폴백을
두면 실 연결이 안 된 상태가 통과하고, 그것이 국면 1에서 실제로 일어난 일이다.

표준 라이브러리만 쓴다(`urllib`) — 코어의 외부 의존 0(문서 1 B12)을 지킨다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from . import log

_LOG = log.get(__name__)

# LLM 지점 **9종** — §7.6-B-2. **이 목록이 점검의 분모다.**
# ⑨좌표 태깅이 목록에 있는 이유: **대체가 선언되지 않은 LLM 지점은 USE_MOCK=1에서
# 실호출로 흘러** 외부 의존 0(문서 1 B12)이 깨지고 미설치 환경에서 실행이 죽는다.
# USE_MOCK 대체는 §7.1 표 — **닫힌 목록 스냅샷의 정확 일치 대조이며 모델을 부르지
# 않는다.** 목록에 있다는 것과 mock에서 모델을 부른다는 것은 다른 말이다.
POINTS = {
    "extract": "①비정형 추출",
    "judge": "②개체 동일성 판정",
    "embed": "③임베딩",
    "image_summary": "④이미지 요약",
    "generate": "⑤구축 모드 생성 (어댑터·매칭 스키마)",
    "link": "⑥질의 링킹 (사전 스캔 → LLM 폴백 → 임베딩 훅 3단)",
    "struct_map": "⑦구조 지도 패스",
    "answer": "⑧답변 생성",
    "coord_tag": "⑨좌표 태깅 (닫힌 목록 선택 또는 null)",
}


def use_mock():
    """mock 갈래인가. **판독은 이 함수 하나가 한다** — 지점마다 읽으면 갈린다."""
    return os.environ.get("USE_MOCK", "1") == "1"


def mock(point, detail=""):
    """mock 갈래에 들어섰음을 로그로 남긴다 (§7.8 로그 3종 중 MOCK 경고).

    표준출력으로만 나가면 자동 점검이 세지 못해 **비어 있는 지점이 구현된 것으로
    보고된다** — 그것이 "훅 5곳"이 전부 주석이었던 사고의 구조다.
    """
    log.mock_warn(_LOG, POINTS.get(point, point), detail)


# ---------------------------------------------------------------- 설정
def config():
    """게이트웨이 설정. **비어 있으면 그 사실을 그대로 돌려준다** — 여기서 채우지 않는다."""
    return {"url": os.environ.get("LLM_GATEWAY_URL", "").rstrip("/"),
            "key": os.environ.get("LLM_API_KEY", ""),
            "model": os.environ.get("CHAT_MODEL", ""),
            "embed_model": os.environ.get("EMBED_MODEL", ""),
            "timeout": float(os.environ.get("LLM_TIMEOUT", "60")),
            "retry": int(os.environ.get("LLM_RETRY", "2"))}


class NotConfigured(RuntimeError):
    """실호출 경로가 비어 있다 — **조용히 mock으로 떨어지지 않는다**(§7.6-B-4)."""


def require(point, *, need=("url", "model")):
    """실호출 직전의 관문. 설정이 없으면 명시적 실패다.

    `point`를 받는 이유: 어느 LLM 지점이 미설정으로 막혔는지가 실측으로 쌓여야
    한다(§7.4 — 명시적 실패는 장부에도 병기한다).
    """
    cfg = config()
    missing = [k for k in need if not cfg.get(k)]
    if missing:
        env = {"url": "LLM_GATEWAY_URL", "model": "CHAT_MODEL",
               "embed_model": "EMBED_MODEL", "key": "LLM_API_KEY"}
        names = ", ".join(env.get(m, m) for m in missing)
        reason = (f"{POINTS.get(point, point)} — 실호출 경로가 비어 있다: {names} 미설정. "
                  f"USE_MOCK=0에서는 조용히 mock으로 떨어지지 않는다 (문서 7 §7.6-B-4)")
        log.explicit_fail(_LOG, f"core.llm[{point}]", reason)
        raise NotConfigured(reason)
    return cfg


# ---------------------------------------------------------------- 호출
PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def prompt(name):
    """지시문 템플릿을 **파일에서 읽는다** (문서 7 §7.6-B-5).

    *"프롬프트 템플릿은 파일이 정본이고 코드가 그것을 읽는다 — 버전 문자열을 코드에
    적어 두고 템플릿 파일을 읽지 않는 구조를 두지 않는다."* 판단·성능에 영향을 주는
    자산은 **코드 안에 박지 않고 자산별 지정 파일**로 둔다(§7.1 관리 자산의 원칙).

    파일이 없으면 **명시적 실패**다 — 조용히 기본 문안으로 떨어지면 그 호출은
    자산이 정하지 않은 지시로 돌고, 파일을 고쳐도 동작이 바뀌지 않는다.
    """
    p = os.path.join(PROMPTS_DIR, f"{name}.md")
    if not os.path.exists(p):
        log.explicit_fail(_LOG, f"core.llm.prompt[{name}]",
                          f"지시문 템플릿이 없다: {p} — 파일이 정본이다(§7.6-B-5)")
        raise FileNotFoundError(f"지시문 템플릿 없음: {p}")
    with open(p, encoding="utf-8") as f:
        return f.read()


def prompt_version(name):
    """그 템플릿의 판본 — 머리말 `version:` 줄이 정본이다."""
    for line in prompt(name).splitlines()[:10]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    log.explicit_fail(_LOG, f"core.llm.prompt_version[{name}]",
                      f"{name}.md 머리말에 version: 줄이 없다")
    raise ValueError(f"{name}.md: 머리말 version: 줄이 없다")


def _post(url, payload, key, timeout):
    """게이트웨이 HTTP 1회. 표준 urllib만 쓴다 — 코어 외부 의존 0."""
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(messages, *, model=None, json_schema=None, point="chat", temperature=0):
    """모델 호출 + JSON 파싱 + 재시도. **돌려주는 것은 dict다.**

    `json_schema`를 주면 구조화 출력을 요청하고 **파싱까지 여기서 한다** — 파싱을
    호출부에 두면 지점마다 다른 관용도로 깨진 JSON을 다루게 되고, mock 갈래와
    반환 계약이 갈린다(§7.6-B-3: 소비부는 어느 쪽인지 몰라야 한다).

    재시도는 **전송·파싱 실패에만** 한다. 모델이 규칙을 어긴 내용(목록 밖 카테고리
    등)은 재시도가 아니라 하류의 게이트·큐가 처리한다 — 파이프라인을 LLM이
    조종하지 않는다(§7.3-4).
    """
    cfg = require(point)
    payload = {"model": model or cfg["model"],
               "messages": messages, "temperature": temperature}
    if json_schema:
        payload["response_format"] = {"type": "json_schema",
                                      "json_schema": {"name": "out",
                                                      "schema": json_schema,
                                                      "strict": True}}
    last = None
    for attempt in range(cfg["retry"] + 1):
        try:
            raw = _post(f"{cfg['url']}/chat/completions", payload,
                        cfg["key"], cfg["timeout"])
            text = raw["choices"][0]["message"]["content"]
            return json.loads(text) if json_schema else {"text": text}
        except (urllib.error.URLError, KeyError, IndexError,
                json.JSONDecodeError, TimeoutError) as e:
            last = e
            _LOG.warning("LLM %s 시도 %d/%d 실패 — %s: %s",
                         POINTS.get(point, point), attempt + 1,
                         cfg["retry"] + 1, type(e).__name__, e)
            if attempt < cfg["retry"]:
                time.sleep(2 ** attempt)
    reason = f"{POINTS.get(point, point)} — 재시도 소진: {type(last).__name__}: {last}"
    log.explicit_fail(_LOG, f"core.llm[{point}]", reason)
    raise RuntimeError(reason)


# ---------------------------------------------------------------- 지점별 얇은 배선
def summarize_image(image_ref):
    """지점 ④ 이미지 요약의 **실호출 갈래**.

    파서는 `core/`를 import하지 않으므로(P1) 이 함수는 **주입되어** 파서에 들어간다 —
    주입하는 쪽이 인입·파싱 진입점이다. mock 갈래는 파서 안의 고정 문자열이고
    `meta.image_summary_source`가 어느 갈래인지 데이터로 남긴다(§7.6-B-4).
    """
    out = chat([{"role": "system", "content": prompt("image_summary")},
                {"role": "user", "content": f"이미지 참조: {image_ref}"}],
               point="image_summary")
    return out["text"]


def image_summarizer():
    """USE_MOCK이면 None(파서가 고정 문자열을 쓴다), 아니면 실호출 함수.

    **None을 돌려주는 것이 mock 갈래의 표현이다** — 파서의 `complete_images`가
    `summarize=None` + `allow_mock`으로 그 분기를 이미 갖고 있다.
    """
    if use_mock():
        return None
    require("image_summary")        # 미설정이면 파싱 전에 명시적으로 실패한다
    return summarize_image


COORD_SCHEMA = {
    "type": "object",
    "properties": {"canonical": {"type": ["string", "null"]}},
    "required": ["canonical"], "additionalProperties": False,
}


def pick_coord(surface, choices):
    """지점 ⑨ 좌표 태깅의 **실호출 갈래** — 닫힌 목록에서 고르거나 null.

    **고르는 것이지 만드는 것이 아니다.** 목록 밖 답은 호출부(파서)가 버린다 —
    모델이 지어낸 좌표가 태깅되면 인입의 orphan_anchor가 그것을 골격으로 착각한다.
    """
    out = chat([{"role": "system", "content":
                 "문서가 말한 공정 이름이 아래 목록의 어느 항목인지 고른다. "
                 "표기가 다를 뿐 같은 것이면 고르고, **목록에 없으면 null**이다. "
                 "목록에 없는 이름을 지어내지 않는다."},
                {"role": "user", "content": json.dumps(
                    {"surface": surface, "choices": choices}, ensure_ascii=False)}],
               json_schema=COORD_SCHEMA, point="coord_tag")
    return out.get("canonical")


def coord_picker():
    """USE_MOCK이면 None(닫힌 목록 정확 일치 — **모델을 부르지 않는다**), 아니면 실호출.

    `image_summarizer()`와 같은 형태다 — **None이 mock 갈래의 표현이고**, 파서의
    `tag()`가 그 분기를 이미 갖고 있다.
    """
    if use_mock():
        return None
    require("coord_tag")
    return pick_coord
