#!/bin/bash
# 클라우드 세션 시작 훅 — 선택 의존 셋(문서 읽기: openpyxl · python-pptx · PyMuPDF)을 깐다.
#   왜: 컨테이너가 다시 뜨면 pip로 깐 것이 사라지고, 회귀(doctor)의 xlsx·pptx·pdf 시험이 빠진다.
#   로컬·사내에서는 아무것도 하지 않는다(CLAUDE_CODE_REMOTE=true일 때만) — 사내 설치는 requirements.txt.
#   이미 import되면 바로 끝난다(재개·압축 뒤에도 돈다).
#   `pip`가 아니라 `python3 -m pip` — 이 이미지의 `pip`는 다른 Python(3.13)에 깐다.
#   PyMuPDF는 1.25.5로 묶는다 — 더 새 판은 `import fitz`에 폐기 경고를 내 화면 출력이 달라진다.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if python3 -c "import openpyxl, pptx, fitz" 2>/dev/null; then
  exit 0
fi

python3 -m pip install -q --disable-pip-version-check --root-user-action=ignore \
  openpyxl python-pptx "pymupdf==1.25.5"
python3 -c "import openpyxl, pptx, fitz"
