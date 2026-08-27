# -*- coding: utf-8 -*-
"""게이트웨이 연결 확인 — **붙었는가를 한 줄로 묻는 명령** (문서 7 §7.6-B).

    python run.py llm-check            설정 확인 + 최소 왕복 1회
    python run.py llm-check --all      9지점 전부 얕게 (비용 주의 — 지점당 1회)

**왜 이 명령이 있나.** 게이트웨이를 붙인 뒤 확인할 방법이 `register generate`를
돌려 보는 것뿐이었다 — 실패하면 원인이 게이트웨이인지 프롬프트인지 표본인지
갈리지 않는다. 이 명령은 **어디까지 갔는지**를 단계로 끊어 보여준다.

**사내망은 출력을 밖으로 가져올 수 없다** — 그래서 화면이 스스로 원인을 말한다
(`doctor.py`와 같은 원칙).

**비밀은 찍지 않는다.** API 키는 설정 여부와 길이만 나온다 — 값도, 앞뒤 일부도
만들지 않는다(`core/llm.py::key_state`). 화면 캡처가 밖으로 나갈 수 있다.

**환경변수 이름조차 이 파일에 적지 않는다** — 설정 접근의 수렴(§7.6-B-1)은
읽는 코드만이 아니라 **아는 코드**를 세는 규율이고, 회귀가 이름으로 센다.

**판정 자체는 `core/llm.py::probe()`가 한다** — 게이트웨이 주소·인증·경로를 아는
코드는 그 파일 하나여야 한다(§7.6-B-1 수렴). 이 파일은 단계 기록을 화면으로
옮기기만 한다.
"""
from __future__ import annotations

import sys

from core import llm

MARK = {True: "  OK ", False: " 필요 ", None: " 다음 "}


def main(argv):
    every = "--all" in argv
    print("=" * 66)
    print("  게이트웨이 연결 확인 — 실호출 왕복 (문서 7 §7.6-B)")
    print("=" * 66)
    # **USE_MOCK과 무관하게 실호출한다** — 이 명령의 목적이 그것이다. 다만
    # 지금 값이 무엇인지는 밝힌다: mock=1인 채로 확인만 하는 경우가 정상이다.
    print(f"  {llm.mock_state()} (이 명령은 값과 무관하게 실호출을 시도한다)")
    print(f"  API 키 {llm.key_state()}\n")

    points = list(llm.POINTS) if every else []
    if every:
        print(f"  --all: 지점 {len(points)}종을 각 1회씩 더 부른다 (비용)\n")

    stages = llm.probe(points)
    fatal = None
    for s in stages:
        print(f"  [{MARK[s['ok']]}] {s['id']} {s['label']}")
        for ln in str(s["detail"]).split("\n"):
            if ln.strip():
                print(f"         {ln}")
        if s["ok"] is False and s["fatal"]:
            fatal = s

    print(f"\n{'=' * 66}")
    if fatal:
        print(f"결과: **{fatal['id']} {fatal['label']}**에서 막혔다 — 위 문장이 원인이다")
        print("=" * 66)
        return 1
    warn = [s for s in stages if s["ok"] is False]
    if warn:
        print(f"결과: 왕복은 된다. 다만 {len(warn)}건이 [필요] — 치명은 아니지만 "
              f"그 지점의 정밀도가 떨어진다")
    else:
        print("결과: **붙었다.** 위 ④의 응답 텍스트가 그 증거다")
    print("=" * 66)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
