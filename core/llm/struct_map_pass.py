# -*- coding: utf-8 -*-
"""칸 2.4 — **구조 지도 패스**(지점 ⑦): 산문의 제목 표시를 모델이 고른다 (문서 6 §6.3).

자르지 않는다 — 지도는 **데이터**이고 분할은 파서의 코드다. 크기 예산을 넘으면
보내지 않고 그 사실을 말한다(평면 인입 + `hierarchy_unresolved` 큐).
"""
from __future__ import annotations

from core.llm import check
from core.llm import gateway
from core.state import log

_LOG = log.get(__name__)


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
    sys_msg = gateway.prompt("struct_map")
    lim = check.context_limit()
    body = width = est = None
    for w in MAP_LINE_WIDTHS:                 # **감축 순서**(B41) — 앞자리부터 줄인다
        body, width = _map_lines(lines, w), w
        est = (len(sys_msg.encode("utf-8")) + len(body.encode("utf-8"))) // 3
        if not lim or est <= lim:
            break
    if lim and est > lim:
        # **보내지 않되 문서를 죽이지 않는다**(문서 6 §6.3 · [정정] 39 — D-113 조정).
        # 컨텍스트 초과는 응답이 잘리는 게 아니라 요청이 거부되므로 보내지 않는다.
        # 다만 여기서 예외를 올리면 어댑터 예외가 되어 **문서 단위 실패**(§6.4-7)로
        # 떨어지고, 지도 없이도 성립하는 평면 인입 + 좌표 태깅까지 함께 잃는다 —
        # §6.2가 그 폴백을 이미 정해 두었다. 그래서 **지도 형태로 사유를 돌려준다**:
        # `unavailable` 키가 있으면 「지도 없음 + 사유」이고, 파서는 그것을 타당성
        # 실패로 받아 평면 폴백 + 큐로 보낸다. 관측(explicit_fail)은 그대로다.
        # **관측은 행동으로 이어져야 한다** — 생성 경로(`cli/prompt._sent_size`)가
        # 감축 3단을 내듯, 여기도 「그래서 무엇이 되고 무엇을 하면 되는가」를 낸다.
        # 이 문면 그대로 `explicit_fail` 로그와 큐 사유(`unavailable`)에 실린다.
        reason = (f"{gateway.POINTS['struct_map']} — 크기 예산 초과: 약 {est:,} 토큰 > "
                  f"한도 {lim:,} (행 {len(lines):,}개를 앞 {width}자로 줄인 뒤에도). "
                  f"보내지 않았다\n"
                  f"   이 문서는 평면으로 인입된다(구조 지도 없이 · "
                  f"hierarchy_unresolved 큐).\n"
                  f"   줄이려면: ①LLM_CONTEXT_TOKENS가 게이트웨이 실제 한도와 "
                  f"맞는지 확인\n"
                  f"             ②문서를 시트·슬라이드 단위로 나눠 인입")
        log.explicit_fail(_LOG, "core.llm[struct_map]", reason)
        return {"doc_id": doc_id, "source": "live", "rows": [],
                "unavailable": reason,
                "prompt_version": gateway.prompt_version("struct_map"),
                "meta": {"dropped": 0, "note": None, "행_앞자리": width,
                         "감축": (f"앞 {MAP_LINE_WIDTHS[0]}자 → {width}자 (크기 예산 B41)"
                                if width != MAP_LINE_WIDTHS[0] else None)}}
    out = gateway.chat([{"role": "system", "content": sys_msg},
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
        "prompt_version": gateway.prompt_version("struct_map"),
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
    if gateway.use_mock():
        return None
    gateway.require("struct_map")        # 미설정이면 파싱 전에 명시적으로 실패한다
    return map_structure
