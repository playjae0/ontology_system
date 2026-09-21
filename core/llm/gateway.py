# -*- coding: utf-8 -*-
"""칸 0.4 게이트웨이 — **LLM 설정 접근이 이 파일 하나로 수렴한다** (문서 7 §7.6-B-1).

    from core.llm import gateway
    if gateway.use_mock():
        out = <mock 갈래>
    else:
        out = gateway.chat(messages, json_schema=SCHEMA)

**이 파일이 가진 것**: 지점 목록 · 모드 판독 · 설정 · 프롬프트 파일 · 사용량 ·
`chat()`/`_post()` · 전송 헬퍼. 옆 파일들(`narrow` · `check` · `points` ·
`struct_map_pass`)이 이것을 쓴다 — 반대 방향은 없다.

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
| `CANDIDATE_NARROW` | 후보 좁히기 — `auto`(기본)·`embed`·`overlap` | auto = 임베딩 있으면 임베딩, 없으면 겹침 |
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

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

from core.state import log

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


# **호출 태그 → 지점** (B63 ② · 칸 대장 1.3·1.4). **지점은 닫힌 9종 그대로다**
# (문서 7 §7.6-B-2) — 한 지점 안에 호출이 여럿일 수 있고, 칸 대장이 칸마다 태그를
# 준다(1.3 문답 · 1.4 생성). 화면·로그는 태그를 받아도 **어느 지점인가**를 답해야
# 하므로 여기서 되돌린다: 태그를 POINTS에 넣으면 명세가 닫아 둔 9종이 흔들린다.
CALL_TAGS = {"interview": "generate"}


def point_label(point):
    """화면·로그에 쓰는 지점 이름 — 호출 태그면 그 지점의 이름으로 되돌린다."""
    return POINTS.get(point) or POINTS.get(CALL_TAGS.get(point, ""), point)


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
    from core import paths                  # 함수 안 import — 모듈 수준 순환 방지
    # 어느 상태에 쓰는지도 화면에 있다(B78 1b) + 그 자리가 **어디서 왔는지**(B79 ④)
    where = f" · 상태 폴더 {paths.home()}{paths.home_note()}"
    if use_mock():
        return ('모드: mock (기본 — 실호출은 llm.json의 "USE_MOCK": 0 또는 '
                'USE_MOCK=0)' + where)
    src, _warn = file_state()
    return f"모드: 실호출 (게이트웨이 설정: {src or '환경변수'}){where}"


def mock(point, detail=""):
    """mock 갈래에 들어섰음을 로그로 남긴다 (§7.8 로그 3종 중 MOCK 경고).

    표준출력으로만 나가면 자동 점검이 세지 못해 **비어 있는 지점이 구현된 것으로
    보고된다** — 그것이 "훅 5곳"이 전부 주석이었던 사고의 구조다.
    """
    log.mock_warn(_LOG, point_label(point), detail)


# ---------------------------------------------------------------- 설정
class NotConfigured(RuntimeError):
    """실호출 경로가 비어 있다 — **조용히 mock으로 떨어지지 않는다**(§7.6-B-4)."""


# 설정 파일을 찾는 자리 — **순서가 곧 우선순위**다. `config()` 하나만 이것을 안다.
CONFIG_ENV = "ONTO_CONFIG"
CONFIG_PATHS = ("~/.onto/llm.json", "llm.local.json", "$ONTO_HOME/llm.json")


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
    from core import paths                  # 함수 안 import — 모듈 수준 순환 방지
    # 넷째 자리는 **상태 루트**다(B78 1b) — 사내는 `ONTO_HOME`을 코드 밖에 두므로
    # 설정도 상태와 함께 이사한다. `paths.config_file()`은 `home()`을 부르지 않는다
    # (부르면 `use_mock()` → 설정 판독 → 여기로 돌아와 서로를 기다린다).
    cand = [os.path.expanduser(CONFIG_PATHS[0]),
            os.path.join(str(paths.ROOT), CONFIG_PATHS[1]),
            str(paths.config_file())]
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
            # **후보 좁히기는 선택이다**(B75 ①) — 임베딩이 없어도 인입은 선다.
            "narrow": (str(get("CANDIDATE_NARROW", "auto")).strip().lower()
                       or "auto"),
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
        reason = (f"{point_label(point)} — 실호출 경로가 비어 있다: {names} 미설정. "
                  f"USE_MOCK=0에서는 조용히 mock으로 떨어지지 않는다 (문서 7 §7.6-B-4)")
        log.explicit_fail(_LOG, f"core.llm[{point}]", reason)
        raise NotConfigured(reason)
    return cfg


# ---------------------------------------------------------------- 호출
def _paths_root():
    """레포 루트 — **자리 소유자에게 묻는다**(B78). 함수 안 import로 순환을 피한다."""
    from core import paths
    return paths.ROOT


PROMPTS_DIR = os.path.join(str(_paths_root()), "prompts")


_PROMPT_RE = re.compile(r"^\d+\.\d+_(?P<name>.+)\.md$")


def prompt_path(name):
    """`prompts/<칸ID>_<이름>.md` **하나**를 찾는다 (B63 ①).

    호출부는 **이름으로 부른다**(`prompt("interview")`) — 칸 ID가 붙거나 칸이 옮겨져도
    호출부가 따라 움직이지 않는다. 파일 이름이 칸 ID를 다는 이유는 반대쪽이다:
    **어느 칸의 지시문인지를 파일 목록이 답해야** 고칠 자리를 번호로 찾는다
    (`docs/구조도/00_칸_대장.md`).

    같은 이름이 두 파일에 있으면 **죽는다.** 조용히 첫 것을 고르면 어느 지시문이
    모델에 갔는지 화면이 답하지 못하고, 고친 파일이 안 쓰이는 상태가 보이지 않는다.
    """
    try:
        names = sorted(os.listdir(PROMPTS_DIR))
    except OSError:
        names = []
    hits = [f for f in names
            if (m := _PROMPT_RE.match(f)) and m.group("name") == name]
    if len(hits) > 1:
        reason = f"지시문 이름이 겹친다: {name} → {hits} — 이름은 하나여야 한다(B63 ①)"
        log.explicit_fail(_LOG, f"core.llm.prompt[{name}]", reason)
        raise FileNotFoundError(reason)
    return os.path.join(PROMPTS_DIR, hits[0]) if hits else None


def prompt(name):
    """지시문 템플릿을 **파일에서 읽는다** (문서 7 §7.6-B-5).

    *"프롬프트 템플릿은 파일이 정본이고 코드가 그것을 읽는다 — 버전 문자열을 코드에
    적어 두고 템플릿 파일을 읽지 않는 구조를 두지 않는다."* 판단·성능에 영향을 주는
    자산은 **코드 안에 박지 않고 자산별 지정 파일**로 둔다(§7.1 관리 자산의 원칙).

    파일이 없으면 **명시적 실패**다 — 조용히 기본 문안으로 떨어지면 그 호출은
    자산이 정하지 않은 지시로 돌고, 파일을 고쳐도 동작이 바뀌지 않는다.
    """
    p = prompt_path(name)
    if not p:
        log.explicit_fail(_LOG, f"core.llm.prompt[{name}]",
                          f"지시문 템플릿이 없다: {PROMPTS_DIR}/<칸ID>_{name}.md "
                          f"— 파일이 정본이다(§7.6-B-5)")
        raise FileNotFoundError(f"지시문 템플릿 없음: <칸ID>_{name}.md")
    with open(p, encoding="utf-8") as f:
        return f.read()


def has_prompt(name):
    """지시문 파일이 있는가 — **묻기만 하고 실패를 기록하지 않는다.**

    `prompt()`는 없으면 「명시적 실패」를 로그에 남긴다(그것이 호출 경로의 규율이다).
    연결 확인처럼 **있는지 물어보는 것이 목적인 자리**가 그 함수를 부르면, 정상
    경로가 ERROR 세 줄로 화면에 뜬다 — 실측으로 그랬고, 사내에서 그것은 고장으로
    읽힌다. 묻는 것과 쓰는 것을 가른다.
    """
    try:
        return prompt_path(name) is not None
    except FileNotFoundError:               # 이름이 겹친다 — 있다고 답하지 않는다
        return False


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
    log.llm_usage(_LOG, point_label(point), u if isinstance(u, dict) else None, fin)


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

    **`content`는 문자열이거나 리스트다**(B53). 리스트면 OpenAI 호환 멀티모달
    (`[{"type":"text",…},{"type":"image_url","image_url":{"url":"data:…;base64,…"}}]`)을
    **그대로** 전송한다 — 이 함수는 형태를 짜지 않는다. ④가 참조 문자열만 보내던
    결함(개정대장 §AJ)은 여기가 문자열만 받아서가 아니라 부르는 쪽이 그림을
    안 실어서였다: 통로는 여기에 두고 무엇을 실을지는 지점이 정한다.

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
                         point_label(point), attempt + 1,
                         cfg["retry"] + 1, type(e).__name__, e)
            if attempt < cfg["retry"]:
                # **재시도 중임이 화면에 보여야 한다**(⑥-5) — 로그 레벨이 낮으면
                # 사람은 «멈췄다»고 읽는다. 실측: 게이트웨이 무응답에서 사용자가
                # 타임아웃×재시도×건수를 말없이 기다렸다.
                print(f"   ⏳ 재시도 {attempt + 2}/{cfg['retry'] + 1} — "
                      f"{point_label(point)}: {type(e).__name__}", flush=True)
                time.sleep(2 ** attempt)
    reason = f"{point_label(point)} — 재시도 소진: {type(last).__name__}: {last}"
    log.explicit_fail(_LOG, f"core.llm[{point}]", reason)
    raise RuntimeError(reason)


# 1×1 투명 PNG — `llm-check` ⑦의 왕복 시험에만 쓴다(가장 작은 실제 이미지).
_PING_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def _data_uri(blob, mime):
    """바이트 → `data:` URI. **키·경로가 아니라 내용을 보낸다.**"""
    return f"data:{mime or 'image/png'};base64,{base64.b64encode(blob).decode()}"


def _image_part(blob, mime):
    return {"type": "image_url", "image_url": {"url": _data_uri(blob, mime)}}
