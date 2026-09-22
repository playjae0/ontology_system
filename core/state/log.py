# -*- coding: utf-8 -*-
"""칸 0.3 — 로깅 — 표준 `logging`, 레벨 INFO (문서 7 §7.8 「로그 규격」).

**반드시 로그로 남기는 3종**이 있다:

| 종류 | 함수 | 왜 로그여야 하나 |
|---|---|---|
| MOCK 경고 | `mock_warn` | 표준출력으로만 나가면 자동 점검이 세지 못해 **비어 있는 지점을 구현된 것으로 보고한다**(§7.6-B-2) |
| 큐 적재 | `queue_put` | 무엇이 언제 사람 판정 대기로 갔는지가 큐 파일의 현재 상태로만 남는다 |
| 명시적 실패 | `explicit_fail` | 예외 메시지로만 남으면 "어느 결정점이 config로 표현되지 않았나"의 실측이 축적되지 않는다(§7.4) |

`logging`은 **표준 라이브러리다** — 코어의 외부 의존 0(문서 1 B12)을 깨지 않는다.

**설정은 진입점이 한다.** 라이브러리 코드가 `basicConfig`를 부르면 그것을 부르는
호스트(플랫폼·테스트)의 로깅 설정을 덮어쓴다 — 그래서 `setup()`은 `run.py`·`doctor.py`
같은 진입점만 부르고, 모듈은 `get(__name__)`으로 로거만 얻는다.

**화면과 파일을 가른다**(B81 ② · 사내 실측 2026-09-22): 콘솔은 기본 **WARNING**이고
파일은 **언제나 INFO**다(`work/logs/<명령>_<날짜>.log`). 「남긴다」는 로그 규격의 요구는
파일에서 그대로 성립한다 — 화면에 값마다 두 줄씩 흐르면 사람이 알고 싶은 것
(붙었나·새로 생겼나·불확실한가)이 그 사이에 묻힌다.

손잡이 둘은 그대로다: `ONTO_LOG_LEVEL`(콘솔 레벨) · `ONTO_LOG_FILE`(파일 자리를
직접 지정). `-v`는 진입점이 `setup(console="INFO")`로 옮긴다.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

ROOT_NAME = "onto"
_configured = False


#: 마지막 `setup()`이 만든 로그 파일 — 화면 끝 요약이 「로그 <경로>」로 낸다.
LOG_PATH = None


def log_path(command=None):
    """이번 실행의 로그 파일 자리 — `work/logs/<명령>_<YYYYMMDD>.log` (B81 ②).

    **자리는 자리 소유자가 안다**(`core/paths.py`) — mock 실행은 mock 루트 아래로
    가고 운영 로그와 섞이지 않는다. `ONTO_LOG_FILE`을 주면 그 파일이 이긴다.
    """
    direct = os.environ.get("ONTO_LOG_FILE")
    if direct:
        return Path(direct)
    from core import paths                  # 함수 안 import — 모듈 수준 순환 방지
    name = (command or "onto").replace("/", "_")
    return paths.work("logs", f"{name}_{time.strftime('%Y%m%d')}.log")


def setup(level=None, *, force=False, console=None, command=None):
    """진입점에서 1회. 두 번 불러도 핸들러가 겹쳐 쌓이지 않는다.

    **콘솔은 WARNING · 파일은 INFO**가 기본이다(B81 ②). `console`을 주면 그 레벨로
    (진입점의 `-v`가 `"INFO"`를 준다), `ONTO_LOG_LEVEL`이 있으면 그것이 이긴다.
    파일 핸들러는 **언제나** 붙는다 — 자리를 못 만들면 조용히 콘솔만 남긴다
    (읽기 전용 배포에서 로깅 때문에 명령이 죽는 쪽이 더 나쁘다).
    """
    global _configured, LOG_PATH
    if _configured and not force:
        return logging.getLogger(ROOT_NAME)
    lg = logging.getLogger(ROOT_NAME)
    lg.setLevel(level or "INFO")           # 로거는 INFO를 통과시키고, 갈래는 핸들러가 정한다
    for h in list(lg.handlers):
        lg.removeHandler(h)
    con = logging.StreamHandler()
    con.setFormatter(logging.Formatter("%(levelname)-7s %(name)s  %(message)s"))
    con.setLevel(os.environ.get("ONTO_LOG_LEVEL", console or "WARNING").upper())
    lg.addHandler(con)
    try:
        path = log_path(command)
        from core import paths                # 폴더를 만드는 자리는 하나다(B77 ④)
        paths.ensure(path)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s  %(message)s"))
        fh.setLevel("INFO")
        lg.addHandler(fh)
        LOG_PATH = path
    except OSError:
        LOG_PATH = None
    lg.propagate = False
    _configured = True
    return lg


def get(name=None):
    """모듈용 로거. 이름은 `onto.<모듈>` 아래로 모인다."""
    if not name or name == ROOT_NAME:
        return logging.getLogger(ROOT_NAME)
    short = name.split(".")[-1] if name.startswith(("core.", "cli.", "parser.")) else name
    return logging.getLogger(f"{ROOT_NAME}.{short}")


# ------------------------------------------------------------------ 3종
def mock_warn(logger, point, detail=""):
    """MOCK 대체가 실제로 돈 자리 — **지점 이름을 남긴다**(§7.6-B-2의 8지점 명칭)."""
    logger.info("MOCK %s%s", point, f" — {detail}" if detail else "")


def queue_put(logger, kind, reason, doc_id=None):
    logger.info("큐 %s%s — %s", kind, f" [{doc_id}]" if doc_id else "", reason)


def llm_usage(logger, point, usage, finish=None):
    """LLM 1회 호출의 토큰 사용량 — **지점 이름과 함께** 남긴다(§7.8 로그).

    `usage`가 없는 게이트웨이도 있다 — **없으면 조용히 넘어간다**(치명 아님).
    다만 `finish_reason == "length"`는 **경고**다: 응답이 잘렸다는 뜻이고, 그러면
    산출물이 불완전한 채로 하류에 흘러간다 — 조용하면 아무도 그것을 모른다.
    """
    if usage:
        logger.info("LLM 사용량 %s — 입력 %s · 출력 %s · 합계 %s", point,
                    usage.get("prompt_tokens", "?"), usage.get("completion_tokens", "?"),
                    usage.get("total_tokens", "?"))
    if finish == "length":
        logger.warning("LLM 응답 잘림 %s — finish_reason=length. "
                       "산출물이 불완전하다(최대 토큰을 올리거나 입력을 줄인다)", point)


def explicit_fail(logger, point, reason):
    """config로 표현되지 않아 core가 시끄럽게 실패하는 지점.

    **raise 전에 부른다** — 예외가 어디서 잡혀도 로그에는 남아야 한다.
    """
    logger.error("명시적 실패 %s — %s", point, reason)


def defect(e, *, stage="", extra=""):
    """**미포착 예외는 문면으로 죽는다** — 한 줄을 돌려주고 장부에 전문을 남긴다.

    사내 실측 열다섯째: 등록 흐름이 `TypeError` traceback으로 죽었고, 사람이
    스크롤을 올려 프레임을 읽어야 원인 자리가 나왔다(M9 「실패는 문면이 답을
    담는다」 위반). 화면은 **한 줄**이고 전체 traceback은 `defects.log`에 간다
    (문서 7 §7.4 — 명시적 실패는 장부에도 병기한다).

    `ONTO_TRACEBACK=1`이면 전문을 화면에도 낸다(개발용).

    **돌려주는 것은 화면 한 줄이다** — 찍는 것은 호출부가 한다: 진입점마다
    종료 코드 규약이 다르고(상태 거부와 같은 코드 — B61), 그 판단은 여기 것이 아니다.
    """
    import os
    import traceback
    from pathlib import Path
    tb = traceback.extract_tb(e.__traceback__)
    where = ""
    if tb:
        fr = tb[-1]
        where = f"{Path(fr.filename).name}:{fr.lineno} · "
    line = (f"[결함] {where}{type(e).__name__}: {str(e)[:120]}"
            + (f" · {stage}" if stage else "") + (f" · {extra}" if extra else ""))
    full = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    try:
        from core.state import store
        store.append_defect(line)
        for ln in full.rstrip().splitlines():
            store.append_defect("    " + ln)
    except Exception:                        # pragma: no cover — 장부가 막혀도 문면은 낸다
        pass
    # **로거로 또 찍지 않는다** — 화면은 한 줄이고(호출부가 찍는다) 장부는
    # `defects.log`다(§7.8의 「조용히 버리지 않기 위한 자리」). 둘 다 찍으면
    # 같은 줄이 두 번 나와 사람이 두 사건으로 읽는다.
    if os.environ.get("ONTO_TRACEBACK") == "1":
        print(full)
    return line
