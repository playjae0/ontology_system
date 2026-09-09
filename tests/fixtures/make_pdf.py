# -*- coding: utf-8 -*-
"""판독 픽스처 생성 — PDF (B53 완료판정 c-ⓐ).

`make_ppt.py`와 같은 이유로 **코드로 만든다** — 바이너리를 커밋하지 않고 무엇이
들었는지가 diff에 보인다.

만드는 것 — 3페이지: 목차 2항목 · 그림 1. 전 쪽에 텍스트가 있다.
(스캔본 = 텍스트 0자 쪽은 파일 없이 어댑터에 합성 raw를 직접 먹여 검사한다.)

사용: python tests/fixtures/make_pdf.py [출력경로]
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent / "raw" / "PDF_basic.pdf"


def _png(w=80, h=60, rgb=(0xB5, 0x74, 0x2E)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def build(out=OUT):
    import fitz                                             # PyMuPDF

    doc = fitz.open()

    # 1쪽 — 노칭
    p = doc.new_page()
    p.insert_text((72, 90), "1. Notching", fontsize=18)
    p.insert_text((72, 130),
                  "The notching press punches the electrode foil.", fontsize=11)
    p.insert_text((72, 150),
                  "Die clearance is managed at 20 +/- 2 um.", fontsize=11)

    # 2쪽 — 스태킹 + 그림
    p = doc.new_page()
    p.insert_text((72, 90), "2. Stacking", fontsize=18)
    p.insert_text((72, 130),
                  "The stacker alternates separator and electrode.", fontsize=11)
    p.insert_image(fitz.Rect(72, 160, 232, 280), stream=_png())

    # 3쪽 — 텍스트만
    p = doc.new_page()
    p.insert_text((72, 90), "3. Tab welding", fontsize=18)
    p.insert_text((72, 130),
                  "The ultrasonic welder joins tabs by polarity.", fontsize=11)

    # 목차 2항목 — `section`이 여기서 온다(c-ⓑ)
    doc.set_toc([[1, "1. Notching", 1], [1, "2. Stacking", 2]])

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    doc.close()
    return out


if __name__ == "__main__":
    p = build(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print(f"[fixture] {p}  [{p.stat().st_size / 1024:.0f}KB]")
