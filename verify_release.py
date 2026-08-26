from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4


def main(path: str) -> int:
    pdf = Path(path)
    if not pdf.exists() or pdf.stat().st_size < 10_000:
        raise SystemExit(f"Release PDF missing or unexpectedly small: {pdf}")
    reader = PdfReader(pdf)
    if len(reader.pages) != 12:
        raise SystemExit(f"Expected 12 pages, got {len(reader.pages)}")
    for index, page in enumerate(reader.pages, 1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        valid_a4 = (abs(width - A4[0]) <= .2 and abs(height - A4[1]) <= .2) or (abs(width - A4[1]) <= .2 and abs(height - A4[0]) <= .2)
        if not valid_a4:
            raise SystemExit(f"Page {index} is not A4: {width} x {height} pt")
    first_page = reader.pages[0].extract_text() or ""
    if "January" not in first_page and "Январь" not in first_page:
        raise SystemExit("January heading was not extractable in English or Russian")
    print(f"Verified {pdf}: 12 A4 pages, readable vector text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
