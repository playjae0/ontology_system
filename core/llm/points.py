# -*- coding: utf-8 -*-
"""칸 2.8·④⑨ — **지점별 얇은 배선**: 이미지 요약 · 좌표 태깅 (문서 6 §6.1·§6.4).

여기 있는 것은 «무엇을 보내고 무엇을 받는가»뿐이다 — 설정·재시도·전송은
`gateway`가 안다. 파서는 이 모듈을 import하지 않는다: 팩토리가 함수를 주입한다
(문서 6 §6.7 외부 전달물 경계).
"""
from __future__ import annotations

from core.llm import gateway


def summarize_image(image_ref, *, image=None, mime=None, context="", page=None):
    """지점 ④ 이미지 요약의 **실호출 갈래** — 보내는 것은 **바이트 + 맥락**이다.

    **구판은 `"이미지 참조: img_001"` 문자열을 보냈다**(개정대장 §AJ). 모델은 그림을
    본 적이 없으므로 요약을 지어냈고, 그 문장이 청크 텍스트가 되어 답변의 「문서
    근거」로 되돌아왔다 — 크래시가 아니라 **조용한 오염**이다. 「9종 도달 가능」
    어서션은 통과했다: **도달과 내용은 다르다.**

    `context`는 같은 슬라이드/페이지의 텍스트다 — 그림만 보내면 「무엇의 그림인가」를
    모델이 지어낸다(문서 6 §6.1). `page`가 있으면 슬라이드 **전체 그림**을 둘째
    이미지로 함께 보낸다 — 잘라낸 그림 하나로는 축·범례가 화면 밖에 있다.

    파서는 `core/`를 import하지 않으므로(P1) 이 함수는 **주입되어** 파서에 들어간다.
    gateway.mock 갈래는 파서 안의 고정 문자열이고 `meta.image_summary_source`가 어느 갈래인지
    데이터로 남긴다(§7.6-B-4).
    """
    parts = [{"type": "text",
              "text": (f"[맥락] {context}\n\n" if context else "")
                      + f"[그림] {image_ref}"}]
    if image:
        parts.append(gateway._image_part(image, mime))
    if page:
        parts.append({"type": "text", "text": "[전체 화면] 위 그림이 실린 쪽 전체다."})
        parts.append(gateway._image_part(page, "image/png"))
    try:
        out = gateway.chat([{"role": "system", "content": gateway.prompt("image_summary")},
                    {"role": "user", "content": parts}],
                   point="image_summary")
    except gateway.GatewayError as e:
        # **이미지를 못 받는 게이트웨이는 설정 결함이다** — 조용히 텍스트만 보내
        # 「요약했다」고 하면 그 문장이 근거가 된다. `gateway.require()`와 같은 결로 멈춘다.
        if e.status == 400 and image:
            raise gateway.NotConfigured(
                "image_summary: 게이트웨이가 이미지 입력을 받지 않는다 — "
                "HTTP 400. `python run.py llm-check`의 ⑦ 단계로 확인한다") from e
        raise
    return out["text"]


def image_summarizer():
    """USE_MOCK이면 None(파서가 고정 문자열을 쓴다), 아니면 실호출 함수.

    **None을 돌려주는 것이 gateway.mock 갈래의 표현이다** — 파서의 `complete_images`가
    `summarize=None` + `allow_mock`으로 그 분기를 이미 갖고 있다.
    """
    if gateway.use_mock():
        return None
    gateway.require("image_summary")        # 미설정이면 파싱 전에 명시적으로 실패한다
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
    out = gateway.chat([{"role": "system", "content": gateway.prompt("coord_tag")},
                {"role": "user", "content": json.dumps(
                    {"surface": surface, "choices": choices}, ensure_ascii=False)}],
               json_schema=COORD_SCHEMA, point="coord_tag")
    return out.get("canonical")


def coord_picker():
    """USE_MOCK이면 None(닫힌 목록 정확 일치 — **모델을 부르지 않는다**), 아니면 실호출.

    `image_summarizer()`와 같은 형태다 — **None이 gateway.mock 갈래의 표현이고**, 파서의
    `tag()`가 그 분기를 이미 갖고 있다.
    """
    if gateway.use_mock():
        return None
    gateway.require("coord_tag")
    return pick_coord
