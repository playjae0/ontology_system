"""칸 1.1~4.4 — 사람이 치는 진입점 모음(CLI). 각 모듈이 한 칸의 화면을 맡는다."""
import sys as _sys


def _state_refusal_hook(tp, val, tb, _prev=_sys.excepthook):
    """**선택 의존 부재는 상태 거부다** — traceback이 아니라 설치 줄이다 (B86 ④).

    잡는 자리가 여기 하나인 이유: 진입점이 둘이고(`run.py` · `python -m cli.*`) 명령이
    스물이 넘는다. 명령마다 `try`를 두면 새 명령이 빠뜨린다. 그 밖의 예외는 원래대로
    흐른다(결함은 결함의 문면으로).
    """
    from parser.reader import MissingDependency
    if isinstance(tp, type) and issubclass(tp, MissingDependency):
        _sys.stderr.write(
            f"[상태] {val}\n"
            f"  ▶ 다음 줄 — 설치한 뒤 같은 명령을 다시 친다 "
            f"(새 코드 폴더 = 새 파이썬 환경이면 선택 의존도 다시다)\n")
        return
    _prev(tp, val, tb)


_sys.excepthook = _state_refusal_hook
