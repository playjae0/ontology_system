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
    """mock 갈래인가. **판독은 이 함수 하나가 한다** — 지점마다 읽으면 갈린다.

    **환경변수 > 설정 파일 > mock**(B42 · `config()`와 같은 우선순위). 설정 파일을
    지원하는 이유는 실측이다 — 운영자가 `llm.json`을 만들어 두고도 `USE_MOCK`을
    export하지 않아 mock 고정 문안을 실호출 오동작으로 읽었다. **읽는 곳은
    여전히 여기 하나다.**

    둘 다 없으면 mock이다(조항 B12 — 외부 의존 0으로 전 경로가 돈다).
    """
    v = os.environ.get("USE_MOCK")
    if v is None or v == "":
        try:
            v = _from_file()[0].get("USE_MOCK")
        except NotConfigured:
            v = None        # 설정 파일이 깨진 것은 config()가 시끄럽게 말한다
    return "1" if v is None else str(v) == "1"


def mode_line():
    """LLM을 부를 수 있는 화면 명령의 **머리 한 줄**(B42 ⑤).

    실측: 설정 파일을 만든 운영자가 **mock 문답의 고정 문안을 실호출 오동작으로
    읽었다.** 어느 갈래로 도는지가 화면 첫 줄에 없으면 사람은 자기가 켠 줄 안다.
    """
    if use_mock():
        return ('모드: mock (기본 — 실호출은 llm.json의 "USE_MOCK": 0 또는 '
                'USE_MOCK=0)')
    src, _warn = file_state()
    return f"모드: 실호출 (게이트웨이 설정: {src or '환경변수'})"


def mock(point, detail=""):
    """mock 갈래에 들어섰음을 로그로 남긴다 (§7.8 로그 3종 중 MOCK 경고).

    표준출력으로만 나가면 자동 점검이 세지 못해 **비어 있는 지점이 구현된 것으로
    보고된다** — 그것이 "훅 5곳"이 전부 주석이었던 사고의 구조다.
    """
    log.mock_warn(_LOG, POINTS.get(point, point), detail)


# ---------------------------------------------------------------- 설정
class NotConfigured(RuntimeError):
    """실호출 경로가 비어 있다 — **조용히 mock으로 떨어지지 않는다**(§7.6-B-4)."""


# 설정 파일을 찾는 자리 — **순서가 곧 우선순위**다. `config()` 하나만 이것을 안다.
CONFIG_ENV = "ONTO_CONFIG"
CONFIG_PATHS = ("~/.onto/llm.json", "llm.local.json")


def config_file():
    """실제로 읽을 설정 파일 경로 — **없으면 None**이다.

    없는 것이 정상이다(환경변수로만 쓰는 사람이 있고, 회귀·CI가 그 경로로 돈다).
    """
    # **`ONTO_CONFIG`를 지정했으면 그것만 본다.** 지정한 경로가 없다고 다른 파일로
    # 넘어가면, 「이 설정으로 돌려라」가 조용히 무시되고 **엉뚱한 자리의 설정이
    # 이긴다** — 회귀가 운영자의 `~/.onto/llm.json`을 물어 「설정 없음」 판정이
    # 통째로 무너진 실측이 그 형태다.
    explicit = os.environ.get(CONFIG_ENV)
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    cand = [os.path.expanduser(CONFIG_PATHS[0]),
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), CONFIG_PATHS[1])]
    for c in cand:
        if c and os.path.isfile(c):
            return c
    return None


def _from_file():
    """설정 파일의 내용. **키 이름은 환경변수와 같다** — 둘을 외우게 하지 않는다.

    **파싱 실패는 명시적 실패다.** 조용히 무시하면 파일을 만들어 둔 사람이 왜
    안 붙는지 알 방법이 없다 — 그 상태가 「조용히 mock으로 떨어진다」와 같은 구조다
    (§7.6-B-4). 없는 파일은 실패가 아니다.
    """
    path = config_file()
    if not path:
        return {}, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        reason = (f"설정 파일을 읽지 못했다: {path} — {type(e).__name__}: {e}. "
                  f"키 이름은 환경변수와 같다(LLM_GATEWAY_URL·LLM_API_KEY·CHAT_MODEL)")
        log.explicit_fail(_LOG, "core.llm.config", reason)
        raise NotConfigured(reason) from e
    if not isinstance(data, dict):
        reason = f"설정 파일의 최상위가 객체가 아니다: {path} ({type(data).__name__})"
        log.explicit_fail(_LOG, "core.llm.config", reason)
        raise NotConfigured(reason)
    return data, path


def file_state():
    """설정 파일의 **자리와 권한**만. 값은 만들지 않는다 — 화면 캡처가 밖으로 나간다."""
    path = config_file()
    if not path:
        return None, None
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        return path, None
    return path, ("그룹·타인이 읽을 수 있다(권한 %o) — chmod 600 을 권한다" % mode
                  if mode & 0o077 else None)


def config():
    """게이트웨이 설정. **비어 있으면 그 사실을 그대로 돌려준다** — 여기서 채우지 않는다.

    **우선순위: 환경변수 > 설정 파일 > 빈 값.** 환경변수 갈래를 그대로 남기는 이유는
    회귀·CI가 그것으로 돌기 때문이다 — 파일을 더하는 것이지 바꾸는 것이 아니다.

    **파일을 여는 코드는 여기 하나다**(§7.6-B-1 수렴). 호출부가 각자 열면 우선순위가
    지점마다 갈리고, 그때 "왜 이 지점만 안 붙나"의 답이 코드 전체에 흩어진다.
    """
    f, _src = _from_file()

    def get(name, default=""):
        v = os.environ.get(name)
        if v is None or v == "":
            v = f.get(name, default)
        return default if v is None else v

    return {"url": str(get("LLM_GATEWAY_URL")).rstrip("/"),
            "key": str(get("LLM_API_KEY")),
            "model": str(get("CHAT_MODEL")),
            "embed_model": str(get("EMBED_MODEL")),
            "timeout": float(get("LLM_TIMEOUT", 60)),
            "retry": int(get("LLM_RETRY", 2))}


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


def has_prompt(name):
    """지시문 파일이 있는가 — **묻기만 하고 실패를 기록하지 않는다.**

    `prompt()`는 없으면 「명시적 실패」를 로그에 남긴다(그것이 호출 경로의 규율이다).
    연결 확인처럼 **있는지 물어보는 것이 목적인 자리**가 그 함수를 부르면, 정상
    경로가 ERROR 세 줄로 화면에 뜬다 — 실측으로 그랬고, 사내에서 그것은 고장으로
    읽힌다. 묻는 것과 쓰는 것을 가른다.
    """
    return os.path.exists(os.path.join(PROMPTS_DIR, f"{name}.md"))


def prompt_version(name):
    """그 템플릿의 판본 — 머리말 `version:` 줄이 정본이다."""
    for line in prompt(name).splitlines()[:10]:
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    log.explicit_fail(_LOG, f"core.llm.prompt_version[{name}]",
                      f"{name}.md 머리말에 version: 줄이 없다")
    raise ValueError(f"{name}.md: 머리말 version: 줄이 없다")


# 세션 누계 — `register generate`가 끝에 한 줄로 보고한다. **프로세스 수명 동안만**
# 산다: 파일로 남기면 «측정»이 아니라 «장부»가 되고, 그것은 이 파일의 일이 아니다.
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
         "total_tokens": 0, "truncated": 0}


def usage_total():
    """세션 누계 스냅샷. 호출부가 화면에 한 줄로 낸다."""
    return dict(USAGE)


def _account(point, raw):
    """응답 1건의 사용량을 누계에 더하고 로그로 남긴다.

    **게이트웨이가 `usage`를 안 주면 조용히 넘어간다** — OpenAI 호환이라도 필드가
    선택인 구현이 있다. 다만 `calls`는 언제나 센다: 「몇 번 불렀나」는 usage 없이도
    알 수 있고, ⑥의 「몇천 회 호출」 문제에서 그 수가 판단 재료다.
    """
    USAGE["calls"] += 1
    u = (raw or {}).get("usage") if isinstance(raw, dict) else None
    fin = None
    try:
        fin = raw["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        pass
    if isinstance(u, dict):
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = u.get(k)
            if isinstance(v, (int, float)):
                USAGE[k] += int(v)
    if fin == "length":
        USAGE["truncated"] += 1
    log.llm_usage(_LOG, POINTS.get(point, point), u if isinstance(u, dict) else None, fin)


ERR_BODY_MAX = 1200          # 오류 본문 보존 상한 — 로그가 본문으로 덮이지 않게
LAST_ERROR = {}              # 마지막 실패의 재료 — 호출부가 파일로 떨군다(B44)


class GatewayError(RuntimeError):
    """게이트웨이가 **이유를 말한** 실패 — 상태 코드와 본문을 지닌다."""

    def __init__(self, status, body, url):
        self.status, self.body, self.url = status, body, url
        super().__init__(f"HTTP {status} — {body}")


def _post(url, payload, key, timeout):
    """게이트웨이 HTTP 1회. 표준 urllib만 쓴다 — 코어 외부 의존 0.

    **오류 본문을 버리지 않는다**(B44). `urlopen`은 4xx/5xx에 `HTTPError`를 던지는데,
    그것을 잡지 않으면 `HTTPError.read()`가 호출되지 않아 **게이트웨이가 적어 보낸
    이유가 통째로 사라진다** — 실측: 400 본문에 *"Missing 'attribute_ranking'"*이
    적혀 있었는데 화면에는 `HTTP Error 400: Bad Request`만 떴다.

    **인증 헤더·키는 남기지 않는다** — 본문과 상태 코드까지다.
    """
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body_bytes,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = "(본문을 읽지 못했다)"
        body = body[:ERR_BODY_MAX] + ("…(잘림)" if len(body) > ERR_BODY_MAX else "")
        LAST_ERROR.clear()
        LAST_ERROR.update({"status": e.code, "url": url,
                           "요청_바이트": len(body_bytes),
                           "응답_본문": body,
                           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        _LOG.error("게이트웨이 HTTP %s — %s", e.code, body)
        raise GatewayError(e.code, body, url) from e


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
            _account(point, raw)          # 파싱 전에 센다 — 잘린 응답도 사용량이다
            text = raw["choices"][0]["message"]["content"]
            return json.loads(text) if json_schema else {"text": text}
        except GatewayError:
            # **4xx는 재시도로 낫지 않는다** — 같은 요청을 세 번 보내 같은 400을
            # 받고 그 사이 화면은 「재시도 중」만 말한다. 즉시 올린다.
            raise
        except (urllib.error.URLError, KeyError, IndexError,
                json.JSONDecodeError, TimeoutError) as e:
            last = e
            _LOG.warning("LLM %s 시도 %d/%d 실패 — %s: %s",
                         POINTS.get(point, point), attempt + 1,
                         cfg["retry"] + 1, type(e).__name__, e)
            if attempt < cfg["retry"]:
                # **재시도 중임이 화면에 보여야 한다**(⑥-5) — 로그 레벨이 낮으면
                # 사람은 «멈췄다»고 읽는다. 실측: 게이트웨이 무응답에서 사용자가
                # 타임아웃×재시도×건수를 말없이 기다렸다.
                print(f"   ⏳ 재시도 {attempt + 2}/{cfg['retry'] + 1} — "
                      f"{POINTS.get(point, point)}: {type(e).__name__}", flush=True)
                time.sleep(2 ** attempt)
    reason = f"{POINTS.get(point, point)} — 재시도 소진: {type(last).__name__}: {last}"
    log.explicit_fail(_LOG, f"core.llm[{point}]", reason)
    raise RuntimeError(reason)


# ---------------------------------------------------------------- 연결 확인
# **연결 확인은 여기 산다** — 게이트웨이 주소·인증·경로 조립을 아는 코드는 이 파일
# 하나여야 한다(§7.6-B-1 수렴). CLI는 아래 `probe()`가 돌려준 단계 기록을 **화면으로
# 옮기기만** 한다. 여기 없이 CLI가 직접 `_post`를 부르면 수렴점이 둘이 되고, 사내
# 게이트웨이가 비호환일 때 고칠 자리가 한 곳이라는 보장이 깨진다.
#
# **`chat()`을 쓰지 않는 이유**: chat은 재시도를 삼키고 실패를 한 문장으로 뭉친다 —
# 그러면 «어디까지 갔는가»가 사라진다. 사내망은 출력을 밖으로 가져올 수 없으므로
# 화면이 스스로 원인을 갈라야 한다(doctor.py와 같은 원칙).

PING = "ping"


def mock_state():
    """지금 mock인가를 **문장으로** 돌려준다 — 호출부가 환경변수를 읽지 않게.

    판독은 `use_mock()` 하나가 한다(§7.6-B-1). 화면에 값을 찍자고 호출부가
    `os.environ`을 열면 수렴점이 둘이 된다.
    """
    return f"USE_MOCK={'1' if use_mock() else '0'}"


def context_limit():
    """컨텍스트 한도 — **설정 파일의 선택 키**(B41). 없으면 `None`이고 대조는 생략된다.

    **기본값을 코드에 박지 않는다.** 게이트웨이마다 다르고, 박아 둔 수치는 틀렸을 때
    「보내도 되는데 막는」 쪽으로도 「막아야 하는데 보내는」 쪽으로도 조용히 틀린다.
    운영자가 자기 게이트웨이의 수치를 적을 때만 대조가 산다.
    """
    try:
        v = os.environ.get("LLM_CONTEXT_TOKENS") or _from_file()[0].get(
            "LLM_CONTEXT_TOKENS")
    except NotConfigured:
        return None
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def key_state():
    """`LLM_API_KEY`의 **설정 여부와 길이만.** 값도, 앞뒤 일부도 내지 않는다.

    사내 화면 캡처가 밖으로 나갈 수 있다 — 마스킹이 아니라 **아예 만들지 않는다.**
    """
    try:
        k = config()["key"]
    except NotConfigured:
        return "판독 불가 (설정 파일 오류 — ① 참조)"
    return f"설정됨(길이 {len(k)})" if k else "미설정"


def _proxy_env():
    """프록시 환경변수의 **이름만** 모은다 — 값에 자격증명이 실릴 수 있다."""
    names = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
             "http_proxy", "https_proxy", "no_proxy")
    return [n for n in names if os.environ.get(n)]


def probe(points=None, *, timeout=None):
    """게이트웨이 왕복을 **단계별로 끊어** 확인한다. 돌려주는 것은 단계 기록이다.

    각 단계는 `{"id","label","ok","detail","fatal"}`이고, 치명 단계에서 멈춘다.
    `points`를 주면 그 지점들을 **얕게 1회씩** 더 시험한다(지점당 호출 1회).

    **`USE_MOCK` 값과 무관하게 실호출을 시도한다** — 이 함수의 목적이 그것이다.
    """
    S = []

    def add(i, label, ok, detail="", fatal=False):
        S.append({"id": i, "label": label, "ok": ok,
                  "detail": detail, "fatal": fatal})
        return ok

    # **설정 파일이 깨진 것도 ①의 실패다.** 여기서 잡지 않으면 `config()`가 던지는
    # NotConfigured가 CLI를 뚫고 생 traceback으로 나간다 — 「화면이 원인을 말한다」는
    # 이 명령의 취지가 바로 그 자리에서 깨진다(실측).
    try:
        cfg = config()
    except NotConfigured as e:
        add("①", "설정", False, str(e), fatal=True)
        return S
    if timeout:
        cfg = {**cfg, "timeout": timeout}

    # ① 설정 — 실패 문장은 require()가 이미 만든다. 여기서 새로 짓지 않는다.
    src, warn = file_state()
    where = f"설정 파일 {src}" if src else "설정 파일 없음 (환경변수만)"
    try:
        require("chat")
        add("①", "설정", True, f"CHAT_MODEL={cfg['model']} · "
                              f"LLM_API_KEY {key_state()} · {where}"
                              + (f"\n{warn}" if warn else ""))
    except NotConfigured as e:
        # **파일로 넣는 법을 함께 낸다** — 변수 이름만 말하면 매 세션 export를
        # 다시 하는 상태가 계속된다(사내 실측).
        add("①", "설정", False,
            f"{e}\n{where}\n"
            f"설정 자리: ~/.onto/llm.json (또는 {CONFIG_ENV} 지정 · "
            f"레포 루트 llm.local.json) · 환경변수도 그대로 쓸 수 있다\n"
            f'형태: {{"LLM_GATEWAY_URL": "…", "LLM_API_KEY": "…", "CHAT_MODEL": "…"}}',
            fatal=True)
        return S

    # ②③④ 한 번의 왕복이 셋을 가른다 — 어디서 끊겼는지가 곧 원인이다.
    url = f"{cfg['url']}/chat/completions"
    payload = {"model": cfg["model"], "temperature": 0,
               "messages": [{"role": "user", "content": PING}]}
    raw = None
    try:
        raw = _post(url, payload, cfg["key"], cfg["timeout"])
        add("②", "도달", True, f"{cfg['url']} — 응답 받음")
        add("③", "인증", True, f"LLM_API_KEY {key_state()}")
    except urllib.error.HTTPError as e:
        add("②", "도달", True, f"{cfg['url']} — HTTP {e.code}")
        if e.code in (401, 403):
            add("③", "인증", False,
                f"HTTP {e.code} — LLM_API_KEY {key_state()}. "
                f"키가 맞는지·게이트웨이가 다른 헤더를 쓰는지 확인한다 "
                f"(헤더는 core/llm.py::_post)", fatal=True)
        else:
            add("③", "인증", False,
                f"HTTP {e.code} {e.reason} — 인증 문제는 아니다. "
                f"모델명({cfg['model']})·경로(/chat/completions)를 확인한다",
                fatal=True)
        return S
    except Exception as e:                       # URLError·timeout·그 밖
        px = _proxy_env()
        add("②", "도달", False,
            f"{cfg['url']} — {type(e).__name__}: {e} · "
            f"프록시 환경변수 {', '.join(px) if px else '없음'} · "
            f"타임아웃 {cfg['timeout']}초", fatal=True)
        return S

    # ④ 응답 형태 — OpenAI 호환인가. **값이 아니라 키 목록만** 낸다.
    try:
        text = raw["choices"][0]["message"]["content"]
        add("④", "응답 형태", True,
            f"choices[0].message.content 실재 — 앞 40자: {str(text)[:40]!r}")
    except (KeyError, IndexError, TypeError):
        add("④", "응답 형태", False,
            f"choices[0].message.content 경로가 없다. "
            f"응답 최상위 키: {sorted(raw) if isinstance(raw, dict) else type(raw).__name__} — "
            f"사내 게이트웨이가 OpenAI 호환이 아니다. "
            f"고칠 곳은 core/llm.py 한 파일(_post와 chat의 응답 파싱)이다",
            fatal=True)
        return S

    # ⑤ 구조화 출력 — 안 먹어도 치명은 아니다(대안이 있다).
    sch = {"type": "object", "properties": {"ok": {"type": "boolean"}},
           "required": ["ok"], "additionalProperties": False}
    try:
        r2 = _post(url, {**payload, "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": sch, "strict": True}},
            "messages": [{"role": "user",
                          "content": 'reply {"ok": true}'}]},
            cfg["key"], cfg["timeout"])
        json.loads(r2["choices"][0]["message"]["content"])
        add("⑤", "구조화 출력", True, "response_format.json_schema 통과")
    except Exception as e:
        add("⑤", "구조화 출력", False,
            f"{type(e).__name__}: {e} — **치명 아님.** 다만 판정 지점(②개체 판정·"
            f"⑧답변·⑨좌표)이 JSON을 요구하므로, 게이트웨이가 스키마를 안 받으면 "
            f"프롬프트 지시로 대신해야 한다(core/llm.py::chat)")

    # ⑥ 임베딩 — **미설정이 정상이다**(호출부 0건의 이연 항목).
    if not cfg["embed_model"]:
        add("⑥", "임베딩", None,
            "EMBED_MODEL 미설정 — **정상이다.** 임베딩은 호출부가 0건인 이연 "
            "항목이고 질의 3단은 「구현하지 않는다」가 명세다(§5.1-4 · P7)")
    else:
        try:
            e_raw = _post(f"{cfg['url']}/embeddings",
                          {"model": cfg["embed_model"], "input": PING},
                          cfg["key"], cfg["timeout"])
            v = e_raw["data"][0]["embedding"]
            add("⑥", "임베딩", True, f"{cfg['embed_model']} — {len(v)}차 벡터")
        except Exception as e:
            add("⑥", "임베딩", False, f"{type(e).__name__}: {e}")

    # ⑦ 지점별 얕은 왕복 — `--all`일 때만. **지점당 1회**다(비용).
    #
    # 지시문 파일이 있는 지점은 그것을 실어 보낸다 — 프롬프트가 게이트웨이를
    # 통과하는지까지 봐야 «붙었다»가 실전 의미를 갖는다. 파일이 없는 지점
    # (⑤생성·⑦구조지도·⑨좌표)은 지시문 없이 왕복만 시험한다.
    for pt in (points or []):
        label = f"지점 {POINTS.get(pt, pt)}"
        try:
            if pt == "embed":
                if not cfg["embed_model"]:
                    add("·", label, None, "EMBED_MODEL 미설정 — 이연 항목(⑥ 참조)")
                    continue
                e_raw = _post(f"{cfg['url']}/embeddings",
                              {"model": cfg["embed_model"], "input": PING},
                              cfg["key"], cfg["timeout"])
                add("·", label, True,
                    f"{len(e_raw['data'][0]['embedding'])}차 벡터")
                continue
            msgs = ([{"role": "system", "content": prompt(pt)}]
                    if has_prompt(pt) else [])
            msgs.append({"role": "user", "content": PING})
            out = chat(msgs, point=pt)
            add("·", label, True,
                f"응답 앞 40자: {str(out.get('text'))[:40]!r}"
                + ("" if has_prompt(pt) else "  (지시문 파일 없는 지점 — 왕복만)"))
        except Exception as e:
            add("·", label, False, f"{type(e).__name__}: {e}")
    return S


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


# ---------------------------------------------------------------- 지점 ⑦ 구조 지도
STRUCT_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "headings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"row": {"type": "integer"},
                               "level": {"type": "integer"},
                               "title": {"type": "string"}},
                "required": ["row", "level", "title"],
                "additionalProperties": False,
            },
        },
        "note": {"type": ["string", "null"]},
    },
    "required": ["headings", "note"],
    "additionalProperties": False,
}

# 행 앞자리의 **감축 사다리**(B41 — 싸고 손실 적은 것부터). 제목은 짧으므로 앞자리를
# 줄여도 제목 판정은 산다 — 행을 빼는 것은 수단이 아니다(행 번호가 판정의 재료다).
MAP_LINE_WIDTHS = (80, 40, 20)


def _map_lines(lines, width):
    """`행번호<TAB>앞N자` — 모델에 보내는 입력 본문."""
    return "\n".join(f"{n}\t{str(t or '')[:width]}" for n, t in lines)


def map_structure(doc_id, lines):
    """지점 ⑦ 구조 지도 패스의 **실호출 갈래** — 지도(데이터)를 받아 파서 형식으로 바꾼다.

    **변환이 여기 있는 이유**: 파서는 LLM 스키마를 모른다(A1 — 결합은 파일 계약뿐).
    모델은 `headings`(제목 행만)를 내고, 파서가 소비하는 것은 전 행의
    `{row, heading, level}`이다. 그 사이를 코어가 메운다.

    **지어낸 행은 버린다**(지시문 규약 4): 입력에 없는 `row`와 `level < 1`은 세어서
    `meta.dropped`에 남긴다 — 조용히 통과시키면 없는 행에 청크 경계가 생긴다.
    `note`는 `meta.note`로 실어 하류가 「판정 불가」로 올릴 수 있게 한다(문서 6 §6.2).
    """
    sys_msg = prompt("struct_map")
    lim = context_limit()
    body = width = est = None
    for w in MAP_LINE_WIDTHS:                 # **감축 순서**(B41) — 앞자리부터 줄인다
        body, width = _map_lines(lines, w), w
        est = (len(sys_msg.encode("utf-8")) + len(body.encode("utf-8"))) // 3
        if not lim or est <= lim:
            break
    if lim and est > lim:
        # **보내지 않고 멈춘다**(B41) — 컨텍스트 초과는 응답이 잘리는 게 아니라
        # 요청이 거부되고, 그 거부는 게이트웨이마다 문면이 달라 원인이 안 보인다.
        reason = (f"{POINTS['struct_map']} — 크기 예산 초과: 약 {est:,} 토큰 > "
                  f"한도 {lim:,} (행 {len(lines):,}개를 앞 {width}자로 줄인 뒤에도). "
                  f"보내지 않았다")
        log.explicit_fail(_LOG, "core.llm[struct_map]", reason)
        raise RuntimeError(reason)
    out = chat([{"role": "system", "content": sys_msg},
                {"role": "user", "content": body}],
               json_schema=STRUCT_MAP_SCHEMA, point="struct_map")

    known = {n for n, _ in lines}
    heads, dropped = {}, 0
    for h in out.get("headings") or []:
        r, lv = h.get("row"), h.get("level")
        if r not in known or not isinstance(lv, int) or lv < 1:
            dropped += 1                      # 입력에 없는 행·잘못된 급 — 버린다
            continue
        heads[r] = lv
    return {
        "doc_id": doc_id, "source": "live",
        "rows": [{"row": n, "heading": n in heads, "level": heads.get(n, 0)}
                 for n, _ in lines],
        # 재현 조건 — 어느 판본의 지시문이 이 지도를 만들었나(B36과 동형)
        "prompt_version": prompt_version("struct_map"),
        "meta": {"dropped": dropped, "note": out.get("note"),
                 "행_앞자리": width,
                 "감축": (f"앞 {MAP_LINE_WIDTHS[0]}자 → {width}자 (크기 예산 B41)"
                        if width != MAP_LINE_WIDTHS[0] else None)},
    }


def struct_mapper():
    """mock이면 None(파서가 번호 패턴 휴리스틱을 쓴다), 아니면 실호출 함수.

    `image_summarizer()`·`coord_picker()`와 **같은 모양이다** — 파서는 「지금
    mock인가」를 묻지 않고 **함수가 왔는가**만 본다(문서 7 §7.6-B-1 · B48).
    """
    if use_mock():
        return None
    require("struct_map")        # 미설정이면 파싱 전에 명시적으로 실패한다
    return map_structure
