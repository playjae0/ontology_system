# -*- coding: utf-8 -*-
"""칸 0.4 — **연결 확인**(`run.py llm-check`)이 단계를 끊어 보는 자리 (문서 7 §7.6-B).

`gateway.chat()`을 쓰지 않는다 — chat은 재시도를 삼키고 실패를 한 문장으로 뭉쳐서
「어디까지 갔는가」가 사라진다. 사내망은 화면 밖으로 출력을 못 가져오므로 화면이
스스로 원인을 갈라야 한다(doctor.py와 같은 원칙). CLI는 `probe()`의 단계 기록을
**화면으로 옮기기만** 한다.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from core.llm import gateway
from core.state import log

_LOG = log.get(__name__)


# **연결 확인은 여기 산다** — 게이트웨이 주소·인증·경로 조립을 아는 코드는 이 파일
# 하나여야 한다(§7.6-B-1 수렴). CLI는 아래 `probe()`가 돌려준 단계 기록을 **화면으로
# 옮기기만** 한다. 여기 없이 CLI가 직접 `gateway._post`를 부르면 수렴점이 둘이 되고, 사내
# 게이트웨이가 비호환일 때 고칠 자리가 한 곳이라는 보장이 깨진다.
#
# **`gateway.chat()`을 쓰지 않는 이유**: chat은 재시도를 삼키고 실패를 한 문장으로 뭉친다 —
# 그러면 «어디까지 갔는가»가 사라진다. 사내망은 출력을 밖으로 가져올 수 없으므로
# 화면이 스스로 원인을 갈라야 한다(doctor.py와 같은 원칙).

PING = "ping"


def mock_state():
    """지금 mock인가를 **문장으로** 돌려준다 — 호출부가 환경변수를 읽지 않게.

    판독은 `gateway.use_mock()` 하나가 한다(§7.6-B-1). 화면에 값을 찍자고 호출부가
    `os.environ`을 열면 수렴점이 둘이 된다.
    """
    return f"USE_MOCK={'1' if gateway.use_mock() else '0'}"


def context_limit():
    """컨텍스트 한도 — **설정 파일의 선택 키**(B41). 없으면 `None`이고 대조는 생략된다.

    **기본값을 코드에 박지 않는다.** 게이트웨이마다 다르고, 박아 둔 수치는 틀렸을 때
    「보내도 되는데 막는」 쪽으로도 「막아야 하는데 보내는」 쪽으로도 조용히 틀린다.
    운영자가 자기 게이트웨이의 수치를 적을 때만 대조가 산다.
    """
    try:
        v = os.environ.get("LLM_CONTEXT_TOKENS") or gateway._from_file()[0].get(
            "LLM_CONTEXT_TOKENS")
    except gateway.NotConfigured:
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
        k = gateway.config()["key"]
    except gateway.NotConfigured:
        return "판독 불가 (설정 파일 오류 — ① 참조)"
    return f"설정됨(길이 {len(k)})" if k else "미설정"


def _proxy_env():
    """프록시 환경변수의 **이름만** 모은다 — 값에 자격증명이 실릴 수 있다."""
    names = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
             "http_proxy", "https_proxy", "no_proxy")
    return [n for n in names if os.environ.get(n)]


def embed_line(cfg):
    """① 설정 줄의 임베딩 조각 — `embed <backend> <model|폴더> [url]` (B80 ③).

    주소를 함께 내는 이유: 임베딩이 채팅과 **다른 base**를 쓸 수 있게 됐고
    (`EMBED_GATEWAY_URL`), 어디를 쳤는지가 화면에 없으면 404를 사람이 못 짚는다.
    """
    backend = cfg.get("embed_backend") or "gateway"
    model = cfg.get("embed_model") or "미설정"
    where = f" {cfg.get('embed_url')}" if backend == "gateway" else ""
    return f"embed {backend} {model}{where}"


def _probe_embed(cfg, add):
    """⑥⑦ — 임베딩과 이미지 입력. **미설정이 정상**이고, 막히면 그 사실만 말한다.

    `probe`에서 단계로 떼어냈다(B78 2c) — 단계마다 함수가 있으면 「어디서 끊겼나」가
    호출 순서로도 보인다.
    """
    # ⑥ 임베딩 — **미설정이 정상이다**. 후보 좁히기는 겹침으로 떨어지고 인입은 선다.
    if not cfg["embed_model"]:
        add("⑥", "임베딩", None,
            "EMBED_MODEL 미설정 — **겹침 폴백.** 후보 좁히기는 정규화 문자 2-gram "
            "겹침으로 돌고 인입은 끝까지 간다(B75 ①). 임베딩으로 강제하려면 "
            "CANDIDATE_NARROW=embed 또는 ingest-file --narrow embed — 그때는 "
            "여기서 막힌다. 질의 3단은 「구현하지 않는다」가 명세다(§5.1-4 · P7)")
    else:
        try:
            # **탐침도 실물을 부른다**(B80 ③) — 여기서 payload를 따로 짜면
            # 게이트웨이/로컬 갈래가 두 자리로 갈리고, 점검이 통과한 뒤 인입이
            # 막힌다(①과 같은 병). `embed()`가 갈래를 아는 유일한 자리다.
            from core.llm import embeddings as _EM
            v = _EM.embed(PING)
            # **비용을 숫자로 보인다**(B80 ③ 개정) — local이면 장치·로드·인코딩까지.
            add("⑥", "임베딩", True,
                f"{cfg['embed_backend']} · {cfg['embed_model']} — {_EM.cost_line()}")
        except Exception as e:
            add("⑥", "임베딩", False, f"{type(e).__name__}: {e}")

    # ⑦ 이미지 입력 — **④가 실제로 쓰는 형태**를 1×1 PNG 한 장으로 왕복시킨다.
    #
    # ④는 바이트를 보낸다(B53). 게이트웨이가 멀티모달 content를 안 받으면 그
    # 사실이 **사내 첫 파싱에서** 드러나는데, 그때는 이미 문서를 돌린 뒤다.
    # 여기서 1회에 판정한다 — 실패해도 치명은 아니다(그림 없는 문서는 돈다).
    try:
        gateway._post(
            f"{cfg['url']}/chat/completions",
            gateway._payload(cfg, [{"role": "user", "content": [
                {"type": "text", "text": "이 그림에 무엇이 보이나?"},
                {"type": "image_url",
                 "image_url": {"url": gateway._data_uri(gateway._PING_PNG,
                                                        "image/png")}}]}]),
            cfg["key"], cfg["timeout"])
        add("⑦", "이미지 입력", True,
            "멀티모달 content 통과 — ④이미지 요약이 바이트를 보낼 수 있다")
    except gateway.GatewayError as e:
        add("⑦", "이미지 입력", False,
            f"HTTP {e.code} — 게이트웨이가 이미지 입력을 받지 않는다. "
            f"④는 이 상태에서 NotConfigured로 멈춘다(요약을 지어내지 않는다). "
            f"**치명 아님** — 그림 없는 문서는 그대로 돈다")
    except Exception as e:                                  # noqa: BLE001
        add("⑦", "이미지 입력", False, f"{type(e).__name__}: {e}")


def _probe_points(cfg, points, add):
    """⑧ 지점별 얕은 왕복 — `--all`일 때만. **지점당 1회**다(비용)."""

    # ⑧ 지점별 얕은 왕복 — `--all`일 때만. **지점당 1회**다(비용).
    #
    # 지시문 파일이 있는 지점은 그것을 실어 보낸다 — 프롬프트가 게이트웨이를
    # 통과하는지까지 봐야 «붙었다»가 실전 의미를 갖는다. 파일이 없는 지점
    # (⑤생성·⑦구조지도·⑨좌표)은 지시문 없이 왕복만 시험한다.
    for pt in (points or []):
        label = f"지점 {gateway.POINTS.get(pt, pt)}"
        try:
            if pt == "embed":
                if not cfg["embed_model"]:
                    add("·", label, None, "EMBED_MODEL 미설정 — 이연 항목(⑥ 참조)")
                    continue
                from core.llm import embeddings as _EM     # 갈래는 한 자리다(B80 ③)
                _EM.embed(PING)
                add("·", label, True, f"{cfg['embed_backend']} · {_EM.cost_line()}")
                continue
            msgs = ([{"role": "system", "content": gateway.prompt(pt)}]
                    if gateway.has_prompt(pt) else [])
            msgs.append({"role": "user", "content": PING})
            out = gateway.chat(msgs, point=pt)
            add("·", label, True,
                f"응답 앞 40자: {str(out.get('text'))[:40]!r}"
                + ("" if gateway.has_prompt(pt) else "  (지시문 파일 없는 지점 — 왕복만)"))
        except Exception as e:
            add("·", label, False, f"{type(e).__name__}: {e}")


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

    # **설정 파일이 깨진 것도 ①의 실패다.** 여기서 잡지 않으면 `gateway.config()`가 던지는
    # NotConfigured가 CLI를 뚫고 생 traceback으로 나간다 — 「화면이 원인을 말한다」는
    # 이 명령의 취지가 바로 그 자리에서 깨진다(실측).
    try:
        cfg = gateway.config()
    except gateway.NotConfigured as e:
        add("①", "설정", False, str(e), fatal=True)
        return S
    if timeout:
        cfg = {**cfg, "timeout": timeout}

    # ① 설정 — 실패 문장은 gateway.require()가 이미 만든다. 여기서 새로 짓지 않는다.
    src, warn = gateway.file_state()
    where = f"설정 파일 {src}" if src else "설정 파일 없음 (환경변수만)"
    try:
        gateway.require("chat")
        add("①", "설정", True, f"CHAT_MODEL={cfg['model']} · "
                              f"temperature {gateway.temperature_line(cfg)} · "
                              f"LLM_API_KEY {key_state()} · {embed_line(cfg)} · "
                              f"{where}"
                              + (f"\n{warn}" if warn else ""))
    except gateway.NotConfigured as e:
        # **파일로 넣는 법을 함께 낸다** — 변수 이름만 말하면 매 세션 export를
        # 다시 하는 상태가 계속된다(사내 실측).
        add("①", "설정", False,
            f"{e}\n{where}\n"
            f"설정 자리: ~/.onto/llm.json (또는 {gateway.CONFIG_ENV} 지정 · "
            f"레포 루트 llm.local.json) · 환경변수도 그대로 쓸 수 있다\n"
            f'형태: {{"LLM_GATEWAY_URL": "…", "LLM_API_KEY": "…", "CHAT_MODEL": "…"}}',
            fatal=True)
        return S

    # ②③④ 한 번의 왕복이 셋을 가른다 — 어디서 끊겼는지가 곧 원인이다.
    url = f"{cfg['url']}/chat/completions"
    # **조립은 `gateway._payload` 하나다**(B80 ①) — 탐침이 따로 짜면 손잡이를 더해도
    # 점검은 옛 모양을 보내고 인입만 400이 난다.
    payload = gateway._payload(cfg, [{"role": "user", "content": PING}])
    raw = None
    try:
        raw = gateway._post(url, payload, cfg["key"], cfg["timeout"])
        add("②", "도달", True, f"{cfg['url']} — 응답 받음")
        add("③", "인증", True, f"LLM_API_KEY {key_state()}")
    except gateway.GatewayError as e:
        # **`gateway._post`가 `HTTPError`를 `GatewayError`로 바꿔 던진다**(:352) — 구판은
        # `except urllib.error.HTTPError`라 **도달하지 않았고**, 401/403이 아래
        # `except Exception`으로 떨어져 「②도달 실패」로 보고됐다. 키가 틀렸는데
        # 화면은 「주소에 못 닿았다」고 말했다 — B19의 「어디까지 갔는지가 곧
        # 원인이다」가 이 자리에서 거짓말했다(B55 ⑦).
        add("②", "도달", True, f"{cfg['url']} — HTTP {e.status}")
        if e.status in (401, 403):
            add("③", "인증", False,
                f"HTTP {e.status} — LLM_API_KEY {key_state()}. "
                f"키가 맞는지·게이트웨이가 다른 헤더를 쓰는지 확인한다 "
                f"(헤더는 core/llm/gateway.py::_post)", fatal=True)
        else:
            add("③", "인증", False,
                f"HTTP {e.status} — 인증 문제는 아니다. 응답 본문: {str(e.body)[:120]} · "
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
            f"고칠 곳은 core/llm/gateway.py 한 파일(_post와 chat의 응답 파싱)이다",
            fatal=True)
        return S

    # ⑤ 구조화 출력 — 안 먹어도 치명은 아니다(대안이 있다).
    sch = {"type": "object", "properties": {"ok": {"type": "boolean"}},
           "required": ["ok"], "additionalProperties": False}
    try:
        r2 = gateway._post(
            url,
            gateway._payload(cfg, [{"role": "user",
                                    "content": 'reply {"ok": true}'}],
                             json_schema=sch),
            cfg["key"], cfg["timeout"])
        json.loads(r2["choices"][0]["message"]["content"])
        add("⑤", "구조화 출력", True, "response_format.json_schema 통과")
    except Exception as e:
        add("⑤", "구조화 출력", False,
            f"{type(e).__name__}: {e} — **치명 아님.** 다만 판정 지점(②개체 판정·"
            f"⑧답변·⑨좌표)이 JSON을 요구하므로, 게이트웨이가 스키마를 안 받으면 "
            f"프롬프트 지시로 대신해야 한다(core/llm/gateway.py::chat)")

    _probe_embed(cfg, add)
    _probe_points(cfg, points, add)
    return S
