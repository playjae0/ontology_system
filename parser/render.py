# -*- coding: utf-8 -*-
"""쪽 전체 렌더 — ④ 이미지 요약에 **화면 전체**를 함께 주기 위한 것 (B53).

**왜 필요한가.** 슬라이드에서 잘라낸 그림 하나에는 축 이름·범례·단위가 없는 일이
흔하다. 그것만 보내면 모델이 「무엇의 그림인가」를 지어내고, 그 문장이 청크 텍스트가
되어 답변의 「문서 근거」로 되돌아온다. 쪽 전체를 함께 주면 지어낼 자리가 줄어든다.

**LibreOffice는 파이프라인 의존이 아니라 「있으면 쓰는 외부 프로그램」이다**
(문서 7 §7.6-B-6). 없으면 `None`을 돌려주고 호출부가 `slide_render="none"`을
데이터에 남긴다 — **조용히 다르게 돌지 않는다.**

**렌더 바이트는 어디에도 저장하지 않는다**(문서 5 §5.2-2 원본 바이너리 비저장).
④에 보내고 버린다. 남는 것은 요약뿐이다.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_LOG = logging.getLogger("onto.parser.render")

MAX_EDGE = 1600         # 긴 변 상한(px) — 넘으면 축소해 보낸다
SOFFICE_TIMEOUT = 180   # 변환이 걸리면 문서를 붙잡지 않고 포기한다


def _pdf_beside(path):
    """같은 폴더·같은 이름의 `.pdf`가 **원본보다 새것**이면 그것을 쓴다.

    사내에서 PPTX와 함께 배포된 PDF가 있으면 변환이 필요 없다. 오래된 PDF는
    쓰지 않는다 — 옛 판의 그림을 새 문서의 근거로 삼게 된다.
    """
    p = Path(path)
    cand = p.with_suffix(".pdf")
    try:
        if cand.exists() and cand.stat().st_mtime >= p.stat().st_mtime:
            return str(cand)
    except OSError:
        pass
    return None


def _soffice_pdf(path, outdir):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    try:
        subprocess.run([exe, "--headless", "--convert-to", "pdf",
                        "--outdir", str(outdir), str(path)],
                       check=True, capture_output=True, timeout=SOFFICE_TIMEOUT)
    except Exception as e:                                  # noqa: BLE001
        # **변환 실패는 문서 실패가 아니다** — 결함 한 줄로 남기고 계속한다.
        _LOG.warning("soffice 변환 실패 — %s: %s", type(e).__name__, e)
        return None
    out = Path(outdir) / (Path(path).stem + ".pdf")
    return str(out) if out.exists() else None


def _pdf_to_png(pdf):
    """PDF → {쪽번호: PNG 바이트}. PyMuPDF는 **지연 import**다(선택 의존)."""
    try:
        import fitz                                         # PyMuPDF
    except ImportError:
        _LOG.info("PyMuPDF 없음 — 쪽 렌더를 건너뛴다")
        return None
    try:
        doc = fitz.open(pdf)
    except Exception as e:                                  # noqa: BLE001
        _LOG.warning("PDF 열기 실패 — %s: %s", type(e).__name__, e)
        return None
    out = {}
    try:
        for i, page in enumerate(doc, start=1):
            r = page.rect
            long_edge = max(r.width, r.height) or 1
            zoom = min(1.0, MAX_EDGE / long_edge) if long_edge > MAX_EDGE else 1.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            out[i] = pix.tobytes("png")
    finally:
        doc.close()
    return out or None


def render_pages(path):
    """`{쪽번호: png 바이트}` 또는 `None`.

    순서는 **싼 것부터**다: ①옆에 있는 최신 PDF ②`soffice` 변환 ③없으면 `None`.
    `.pdf` 입력은 변환 없이 그대로 연다.
    """
    p = str(path)
    if p.lower().endswith(".pdf"):
        return _pdf_to_png(p)

    pdf = _pdf_beside(p)
    if pdf:
        return _pdf_to_png(pdf)
    with tempfile.TemporaryDirectory() as td:
        pdf = _soffice_pdf(p, td)
        if not pdf:
            return None
        return _pdf_to_png(pdf)


def available():
    """렌더가 가능한 환경인가 — 화면·진단이 쓴다. 실제 변환은 하지 않는다."""
    try:
        import fitz                                         # noqa: F401
    except ImportError:
        return False, "PyMuPDF 없음"
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        return False, "soffice 없음 (PDF는 변환 없이 열린다)"
    return True, "soffice + PyMuPDF"
